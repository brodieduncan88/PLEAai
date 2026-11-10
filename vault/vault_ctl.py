#!/usr/bin/env python3
"""The owner's console for a holdout.  Everything here needs credentials a submitter never holds.

    vault_ctl.py DIR report-key                      create DIR/report.key (mode 0600) if absent; print the public key
    vault_ctl.py DIR enrol NAME --budget K [--replacement M] --pki PKI [--days 90] [--organisation ORG] [--contact WHO]
    vault_ctl.py DIR renew NAME --pki PKI [--days 90]        a new certificate for the same name and the same budget
    vault_ctl.py DIR revoke NAME                     stop the budget (audited) and refuse the certificate from now on
    vault_ctl.py DIR close                           stop every budget, then delete the uploaded files

enrol issues the submitter's client certificate from the deployment's authority (PKI/ca.key, as tls.py init wrote it),
provisions the budget HOLDOUT/NAME through the control plane (the same call as plea_ctl.py provision), and writes the
enrolment record the front door checks on every request: name, organisation, contact, certificate fingerprint, issue
and expiry dates.  One certificate per legal entity: binding a name to a real party is the owner's job, and a party
given two names has two budgets.  The certificate and key are written to PKI/NAME.crt and PKI/NAME.key for the owner to
hand over.

revoke applies STOP to the budget, which the witness honours at the next admission and the audit log records, and marks
the enrolment revoked, which the front door honours on the next request.  The budget is never reopened; a party
re-enrolled later gets a new name.

close is how a holdout ends: every budget is stopped, so nothing new can be scored, and the uploaded files are deleted.
Hashes, receipts, audit rows and reports stay in the database.  A hash that was already scored still returns its stored
score.
"""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from cryptography import x509                                    # noqa: E402
from cryptography.hazmat.primitives import serialization         # noqa: E402
from plea_gateway import RootExists, Store                       # noqa: E402
from plea_gateway import tls as TLS                              # noqa: E402
from holdout import NAME, RESERVED, Holdout                      # noqa: E402
from vault_report import ReportKey                               # noqa: E402
from vault_service import Index                                  # noqa: E402


def fingerprint(cert_pem: bytes) -> tuple[str, str, str]:
    """(sha256 of the DER certificate, not-before, not-after)."""
    cert = x509.load_pem_x509_certificate(cert_pem)
    der = cert.public_bytes(serialization.Encoding.DER)
    before = getattr(cert, 'not_valid_before_utc', None) or cert.not_valid_before       # the _utc names arrived in cryptography 42
    after = getattr(cert, 'not_valid_after_utc', None) or cert.not_valid_after
    return hashlib.sha256(der).hexdigest(), before.strftime('%Y-%m-%dT%H:%M:%SZ'), after.strftime('%Y-%m-%dT%H:%M:%SZ')


def issue(pki: pathlib.Path, name: str, days: int) -> tuple[str, str, str]:
    key, cert = TLS.issue((pki / 'ca.key').read_bytes(), (pki / 'ca.crt').read_bytes(), name, 'client', (), days)
    (pki / f'{name}.key').write_bytes(key); (pki / f'{name}.key').chmod(0o600); (pki / f'{name}.crt').write_bytes(cert)
    return fingerprint(cert)


def report_key(holdout: Holdout) -> ReportKey:
    path = holdout.dir / 'report.key'
    if not path.exists():
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(ReportKey().private_hex + '\n')
    return ReportKey(path.read_text().strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir'); ap.add_argument('action', choices=['report-key', 'enrol', 'renew', 'revoke', 'close']); ap.add_argument('name', nargs='?')
    ap.add_argument('--budget', type=int); ap.add_argument('--replacement', type=int, default=0); ap.add_argument('--pki'); ap.add_argument('--days', type=int, default=90)
    ap.add_argument('--organisation', default=''); ap.add_argument('--contact', default='')
    ap.add_argument('--control-dsn', default=os.environ.get('PLEA_CONTROL_DSN', 'postgresql://plea_control:control@127.0.0.1:5432/plea'))
    a = ap.parse_args()
    holdout = Holdout(a.dir); index = Index(holdout.dir / 'index.sqlite')
    if a.action == 'report-key':
        print(json.dumps({'report_key': report_key(holdout).public_hex})); return
    if a.action == 'close':
        store = Store(a.control_dsn)
        stopped = {name: store.apply(holdout.root(name), ('STOP',))[0].code for name in index.submitters()}
        shutil.rmtree(holdout.dir / 'uploads', ignore_errors=True); (holdout.dir / 'uploads').mkdir(exist_ok=True)
        print(json.dumps({'closed': holdout.name, 'stopped': stopped, 'uploads': 'deleted'})); return
    if not a.name or not NAME.match(a.name) or a.name in RESERVED:
        ap.error('a submitter name is needed: letters, digits, "_", "." and "-", at most 64, and not one of the deployment\'s own names')
    root = holdout.root(a.name)
    if a.action == 'revoke':
        d, obs = Store(a.control_dsn).apply(root, ('STOP',)); index.revoke(a.name)
        print(json.dumps({'revoked': a.name, 'stop': [d.kind, d.code], 'business': obs['business']})); return
    if not a.pki:
        ap.error(f'{a.action} needs --pki, the directory holding ca.key and ca.crt')
    if not 1 <= a.days <= 90:
        ap.error('--days: between 1 and 90')
    if a.action == 'renew':
        rec = index.enrolled(a.name)
        if rec is None or rec['revoked']:
            ap.error(f'{a.name} is not enrolled, or is revoked')
        fp, issued, expires = issue(pathlib.Path(a.pki), a.name, a.days)
        index.enrol(a.name, rec['organisation'], rec['contact'], fp, issued, expires)
        print(json.dumps({'renewed': a.name, 'cert_sha256': fp, 'expires': expires})); return
    if a.budget is None:
        ap.error('enrol needs --budget K')
    rec = index.enrolled(a.name)
    if rec is not None:
        ap.error(f'{a.name} is already enrolled; use renew for a new certificate, or another name for a new budget')
    try:
        prov = Store(a.control_dsn).new_root(root, a.budget, a.replacement)
    except RootExists:
        ap.error(f'the budget {root} already exists; a budget is provisioned once')
    fp, issued, expires = issue(pathlib.Path(a.pki), a.name, a.days)
    index.enrol(a.name, a.organisation, a.contact, fp, issued, expires)
    print(json.dumps({'enrolled': a.name, 'root': root, 'budget': a.budget, 'replacement': a.replacement, 'provisioning_record': prov['seq'],
                      'anchor': prov['hash'], 'cert_sha256': fp, 'expires': expires}))


if __name__ == '__main__':
    main()
