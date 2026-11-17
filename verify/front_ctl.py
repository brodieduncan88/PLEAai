#!/usr/bin/env python3
"""The responsible engineer's console for the front door: who may ask, and against which baseline.

    front_ctl.py enrol  HOME JOB HASH --key ENGINEER.key --ca CA.crt --ca-key CA.key --url https://HOST:PORT --out DIR [--reason "..."]
    front_ctl.py rebind HOME JOB NEWHASH --key ENGINEER.key
    front_ctl.py revoke HOME JOB --key ENGINEER.key
    front_ctl.py jobs   HOME
    front_ctl.py record HOME HASH --key ENGINEER.key --witness-key HEX --gate-key HEX --out RECORD.json

Everything here needs the engineer's key, and enrol also needs the certificate authority's key.  The assistant holds
neither.

enrol binds a job name to one baseline and issues the job's client certificate.  It writes DIR for the assistant's
side: the front door's address, the authority's certificate, and the job's certificate and key.  Nothing else is in
it: no database credential, no signing key, no copy of the check.  A job name is used once, and its certificate lasts
--days (90 unless given); renewing one is not built, so a job that outlives its certificate is enrolled again under a
new name, with a reason.

A job has one baseline in force.  rebind moves it, and only to a baseline that says it supersedes the one in force,
which means it was made with `verify_ctl.py revise`: the old budget is stopped first, the new card carries what was
run and what failed on the old one with the engineer's reason, and the new record is headed "changed after the
event".  A baseline that is merely different is refused.

enrol also refuses to open a second job for a requirement id that another job already holds under a different
baseline, unless the new baseline supersedes that one or the engineer gives --reason.  The reason is written into the
signed binding and the log.  This does not reach inside the record: the record's format is the first plug-in's,
unchanged, so a reader of one record sees a change of requirement only when it was made by revision.  The log
(HOME/front/enrolment.jsonl) is the service's own signed list of every binding, in order.

enrol and rebind also wait, for --wait seconds (15 unless given), until the gate's tool has shown that it can write a notice
to the inbox of the baseline the job is to be bound to, and refuse if it has not: a job is not opened on a baseline whose
failures might not reach its engineer (Amendment 8).  The gate shows it within a second or so of the baseline being made,
if it is running and its account can write the inbox.

revoke ends a job: its certificate is refused from the next request.

record builds the verification record exactly as verify_ctl.py does, adding the front door's own journal of what was
sent, so a run interrupted before the gate wrote anything down can still be tied to its design.
"""
import argparse
import hashlib
import json
import os
import pathlib
import sys
import time

from cryptography import x509
from cryptography.hazmat.primitives import serialization

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from plea_gateway import tls as TLS                                   # noqa: E402
from baseline import BaselineInvalid, root_for                        # noqa: E402
from front_door import JOB_NAME, RESERVED, binding_message, binding_valid, jobs_path, read_jobs   # noqa: E402
from verify_record import Key, load_envelope, now                     # noqa: E402
import verify_ctl                                                     # noqa: E402
import notices                                                        # noqa: E402  (Amendment 8: the gate's inbox-writability check)


class Refused(Exception):
    pass


def _envelope(home, baseline_hash: str, key: Key) -> dict:
    try:
        env = load_envelope(pathlib.Path(home) / 'baselines' / baseline_hash / 'baseline.json', key.public_hex)
    except (OSError, ValueError, KeyError, TypeError, BaselineInvalid) as exc:
        raise Refused(f'no baseline {baseline_hash[:16]}… signed by this engineer is held: {exc}')
    if env['baseline_sha256'] != baseline_hash:
        raise Refused('the directory holds another baseline')
    return env


def _supersedes(home, env: dict, key: Key, target: str) -> bool:
    """True if this baseline replaced `target`, directly or through earlier revisions."""
    seen = set()
    while env is not None:
        sup = env['card'].get('supersedes')
        if not sup or sup['baseline_sha256'] in seen:
            return False
        if sup['baseline_sha256'] == target:
            return True
        seen.add(sup['baseline_sha256'])
        try:
            env = _envelope(home, sup['baseline_sha256'], key)
        except Refused:
            return False
    return False


def _deliverable(home, baseline_hash: str, wait: float) -> None:
    """Amendment 8 (D3).  Wait until the gate's tool has shown that it can write a notice to this baseline's inbox, and refuse if it
    has not within `wait` seconds.  With the console and the gate under two accounts, an inbox the gate cannot write is found
    here, before a job is opened, and not at the first failure."""
    deadline = time.time() + max(0.0, wait)
    while True:
        state, _ = notices.delivery_state(home, baseline_hash)
        if state == 'WRITABLE':
            return
        if time.time() >= deadline:
            break
        time.sleep(0.1)
    raise Refused(f'{notices.DELIVERY_WORDS[state]} ({baseline_hash[:16]}…), so a failure might not reach its engineer.  Start the gate if it is not '
                  f'running, make the inbox writable by the gate\'s account, and try again.  Nothing was changed.')


def _write(home, binding: dict) -> None:
    """The signed binding becomes the job's current one, and is added to the log.  The file is replaced whole."""
    path = jobs_path(home); path.parent.mkdir(parents=True, exist_ok=True)
    jobs = read_jobs(home); jobs[binding['job']] = binding
    tmp = path.with_suffix('.tmp'); tmp.write_text(json.dumps({'jobs': jobs}, indent=1) + '\n'); os.replace(tmp, path)
    with (path.parent / 'enrolment.jsonl').open('a') as f:
        f.write(json.dumps(binding) + '\n')


def _signed(event: str, seq: int, job: str, env: dict, cert_sha256: str, previous, note, key: Key) -> dict:
    """A binding names the baseline by its hash and the budget by its name, both taken from the baseline the engineer
    signed, and carries a number that only goes up, so an earlier binding cannot stand in for a later one."""
    b = {'event': event, 'seq': seq, 'job': job, 'baseline_sha256': env['baseline_sha256'], 'root': root_for(env['card']), 'cert_sha256': cert_sha256,
         'previous': previous, 'time': now(), 'note': note}
    return dict(b, signer=key.public_hex, signature=key.sign(binding_message(b)))


def _current(home, job: str, key: Key) -> dict:
    b = read_jobs(home).get(job)
    if b is None:
        raise Refused(f'{job} is not enrolled')
    if not binding_valid(b, (key.public_hex,)):
        raise Refused(f'the stored binding of {job} is not signed by this engineer; it is not used')
    return b


def enrol(home, job: str, baseline_hash: str, key: Key, ca_cert_pem: bytes, ca_key_pem: bytes, url: str, out, reason: str | None = None, days: int = 90,
          wait: float = 15.0) -> dict:
    """Bind a new job to a baseline, issue its certificate and write its folder.  Returns the signed binding."""
    if not isinstance(job, str) or not JOB_NAME.match(job) or job in RESERVED:
        raise Refused('a job name is 2 to 41 lower-case letters, digits or hyphens, and not a service\'s own name')
    if job in read_jobs(home):
        raise Refused(f'{job} is already enrolled; a job name is used once')
    env = _envelope(home, baseline_hash, key)
    rid = env['card']['requirement']['id']
    for other, b in sorted(read_jobs(home).items()):
        if b.get('baseline_sha256') == baseline_hash or not binding_valid(b, (key.public_hex,)):
            continue                                     # a revoked job still counts: its requirement was under that baseline
        try:
            held = _envelope(home, b['baseline_sha256'], key)
        except Refused:
            continue
        if held['card']['requirement']['id'] == rid and not _supersedes(home, env, key, b['baseline_sha256']) and not (reason and reason.strip()):
            raise Refused(f'{rid} is already under baseline {b["baseline_sha256"][:16]}… on job {other}.  A change to a requirement is a revision '
                          f'(verify_ctl.py revise, then front_ctl.py rebind).  To open a separate job on purpose, give a reason.')
    out = pathlib.Path(out)
    if out.exists() and any(out.iterdir()):
        raise Refused(f'{out} is not empty')
    _deliverable(home, baseline_hash, wait)              # Amendment 8 (D3): no job on a baseline whose failures might not reach its engineer
    key_pem, cert_pem = TLS.issue(ca_key_pem, ca_cert_pem, job, 'client', (), days)
    der = x509.load_pem_x509_certificate(cert_pem).public_bytes(serialization.Encoding.DER)
    binding = _signed('ENROL', 1, job, env, hashlib.sha256(der).hexdigest(), None, reason.strip() if reason and reason.strip() else None, key)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'ca.crt').write_bytes(ca_cert_pem); (out / 'job.crt').write_bytes(cert_pem)
    fd = os.open(out / 'job.key', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(key_pem)
    (out / 'job.json').write_text(json.dumps({'job': job, 'url': url.rstrip('/'), 'ca': 'ca.crt', 'cert': 'job.crt', 'key': 'job.key'}, indent=1) + '\n')
    _write(home, binding)
    return binding


def rebind(home, job: str, new_hash: str, key: Key, wait: float = 15.0) -> dict:
    """Move a job to a revision of its baseline.  Refused unless the new baseline says it supersedes the one in force."""
    cur = _current(home, job, key)
    if cur['event'] == 'REVOKE':
        raise Refused(f'{job} was revoked')
    if new_hash == cur['baseline_sha256']:
        raise Refused(f'{job} is already bound to this baseline')
    env = _envelope(home, new_hash, key)
    sup = env['card'].get('supersedes') or {}
    if sup.get('baseline_sha256') != cur['baseline_sha256']:
        raise Refused(f'{job} is bound to {cur["baseline_sha256"][:16]}… and this baseline does not supersede it.  A job moves only to a revision of its '
                      f'own baseline (verify_ctl.py revise), so that the change and what had failed are on the record.')
    _deliverable(home, new_hash, wait)                   # Amendment 8 (D3): the same check is needed for the revision
    binding = _signed('REBIND', cur['seq'] + 1, job, env, cur['cert_sha256'], cur['baseline_sha256'], None, key)
    _write(home, binding)
    return binding


def revoke(home, job: str, key: Key) -> dict:
    cur = _current(home, job, key)
    if cur['event'] == 'REVOKE':
        raise Refused(f'{job} is already revoked')
    b = {'event': 'REVOKE', 'seq': cur['seq'] + 1, 'job': job, 'baseline_sha256': cur['baseline_sha256'], 'root': cur['root'], 'cert_sha256': cur['cert_sha256'],
         'previous': cur['baseline_sha256'], 'time': now(), 'note': None}
    binding = dict(b, signer=key.public_hex, signature=key.sign(binding_message(b)))
    _write(home, binding)
    return binding


def log(home) -> list:
    p = jobs_path(home).parent / 'enrolment.jsonl'
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def journal(home) -> pathlib.Path:
    return jobs_path(home).parent / 'submissions.jsonl'


def record(home, baseline_hash: str, key: Key, witness_key, gate_key, journals=()) -> dict:
    """The verification record, built as verify_ctl.record builds it, with the front door's journal among the candidates."""
    return verify_ctl.record(home, baseline_hash, key, witness_key, gate_key, [journal(home), *journals])


def main():
    ap = argparse.ArgumentParser(description='The responsible engineer\'s console for the front door.')
    ap.add_argument('action', choices=['enrol', 'rebind', 'revoke', 'jobs', 'record']); ap.add_argument('home'); ap.add_argument('rest', nargs='*')
    ap.add_argument('--key'); ap.add_argument('--ca'); ap.add_argument('--ca-key'); ap.add_argument('--url'); ap.add_argument('--out'); ap.add_argument('--reason')
    ap.add_argument('--days', type=int, default=90); ap.add_argument('--witness-key'); ap.add_argument('--gate-key')
    ap.add_argument('--wait', type=float, default=15.0, help='seconds enrol and rebind wait for the gate to show it can write the inbox (Amendment 8)')
    a = ap.parse_args()
    try:
        if a.action == 'jobs':
            for job, b in sorted(read_jobs(a.home).items()):
                print(f"{job:<24} {b.get('event'):<7} {str(b.get('baseline_sha256'))[:16]}…  {b.get('time')}" + (f"  note: {b['note']}" if b.get('note') else ''))
            return
        key = verify_ctl.load_key(a.key)
        if a.action == 'enrol':
            b = enrol(a.home, a.rest[0], a.rest[1], key, pathlib.Path(a.ca).read_bytes(), pathlib.Path(a.ca_key).read_bytes(), a.url, a.out, a.reason, a.days, a.wait)
        elif a.action == 'rebind':
            b = rebind(a.home, a.rest[0], a.rest[1], key, a.wait)
        elif a.action == 'revoke':
            b = revoke(a.home, a.rest[0], key)
        else:
            rec = record(a.home, a.rest[0], key, a.witness_key, a.gate_key)
            pathlib.Path(a.out).write_text(json.dumps(rec, indent=1) + '\n'); print(json.dumps({'record': a.out, 'attempts': len(rec['attempts']), 'as_of': rec['as_of']})); return
        print(json.dumps({k: b[k] for k in ('event', 'seq', 'job', 'baseline_sha256', 'root', 'previous', 'time', 'note')}))
    except (Refused, BaselineInvalid, ValueError, OSError, IndexError, TypeError) as exc:
        print(f'refused: {exc}', file=sys.stderr); sys.exit(1)


if __name__ == '__main__':
    main()
