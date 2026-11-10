#!/usr/bin/env python3
"""Declared tests V1-V13 for the Holdout Vault demo (vault/DECLARED_VAULT.md states the expected outcomes).

    vault_tests.py [V1 V5 ...]        all thirteen by default; writes outputs/vault_tests.json; exits 1 if any test fails

Each test builds its own holdout (40 rows, classes a/b/c) in outputs/vault_tests/<test>/, starts the real services
under mutual TLS -- the v1.2.1 witness service and gate host, unchanged, and the vault's front door -- enrols
submitters with vault_ctl.py, and talks to the front door over HTTPS with the submitter's certificate, as a submitter
would.  The independent measure is the scoring tool's ledger (vault_tools.py): one line each time the tool is called,
opens the labels, or produces a score.  It is outside every PLEA store.

A test passes only if every named check in it is true; the checks and what was observed are written to the output.
"""
import hashlib
import json
import os
import pathlib
import shutil
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import threading
import urllib.request
import uuid

import psycopg

from common import GATE, GATEWAY, LOCAL_DSN, PYTHON, WITNESS_KEY, WITNESS_PUB, WitnessService, _tls_args, client_tls, server_tls   # noqa: E402
from plea_gateway import Store                    # noqa: E402
from plea_gateway import tls as TLS               # noqa: E402

VAULT = GATEWAY / 'vault'
sys.path.insert(0, str(VAULT))
import holdout as H                               # noqa: E402
import plea_verify                                # noqa: E402
import vault_ctl                                  # noqa: E402
from vault_report import ReportKey, canonical, request_key, score_arguments   # noqa: E402
from vault_service import Index                   # noqa: E402

OUT = GATEWAY / 'outputs' / 'vault_tests'
RUN = uuid.uuid4().hex[:6]                         # budgets are provisioned once, so every run names its holdouts afresh
PORTS = {'witness': 8961, 'host': 8962, 'vault': 8963}
ROWS, CLASSES = 40, ('a', 'b', 'c')
IDS = [f'r{i:03d}' for i in range(ROWS)]
LABELS = [CLASSES[i % 3] for i in range(ROWS)]
PKI = {}


def make_pki() -> dict:
    d = OUT / 'pki'
    paths = TLS.init_pki(d, servers=('witness', 'host', 'vault'), clients=('governor', 'stranger'), ca_name='plea-vault-test-ca', days=1)
    paths['dir'] = d
    paths['impostor'] = TLS.init_pki(d / 'impostor', servers=(), clients=('alice',), ca_name='impostor-ca', days=1)
    return paths


def predictions(wrong=(), extra: str = '') -> bytes:
    """A valid submission with the rows at the indices in `wrong` answered incorrectly.  `extra` is appended raw."""
    lines = ['id,prediction']
    for i, (rid, label) in enumerate(zip(IDS, LABELS)):
        lines.append(f'{rid},{CLASSES[(CLASSES.index(label) + 1) % 3] if i in wrong else label}')
    return ('\n'.join(lines) + '\n' + extra).encode()


def _why(exc) -> str:
    """A short name for a refused connection: OpenSSL's reason when there is one, else the exception's type."""
    inner = getattr(exc, 'reason', exc)
    if isinstance(inner, BaseException):
        inner = getattr(inner, 'reason', None) if isinstance(getattr(inner, 'reason', None), str) else type(inner).__name__
    return str(inner)


class Client:
    """A submitter's HTTPS client: the deployment's authority, and this submitter's certificate and key."""

    def __init__(self, base: str, ca: str, cert: str, key: str):
        self.base, self.ca, self.cert, self.key = base, ca, cert, key

    def call(self, method: str, path: str, body: bytes | None = None, json_body=None, timeout: float = 30.0):
        """(status, payload).  A refused TLS handshake or a dropped connection is (None, the exception's name)."""
        data = json.dumps(json_body).encode() if json_body is not None else body
        req = urllib.request.Request(self.base + path, data=data, method=method)
        try:
            ctx = TLS.TLSClient(self.ca, self.cert, self.key).context()
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                raw = r.read(); status = r.status
        except urllib.error.HTTPError as exc:
            raw, status = exc.read(), exc.code
        except (urllib.error.URLError, ssl.SSLError, ConnectionError, OSError) as exc:
            return None, _why(exc)
        try:
            return status, json.loads(raw)
        except ValueError:
            return status, raw.decode(errors='replace')

    def upload(self, data: bytes):  return self.call('POST', '/upload', body=data)
    def score(self, sha: str):      return self.call('POST', '/score', json_body={'sha256': sha})
    def status(self):               return self.call('GET', '/status')
    def report(self):               return self.call('GET', '/report')


class Deployment:
    def __init__(self, tag: str, limits: dict | None = None, decimals: int = 2):
        self.tag, self.dir = tag, OUT / tag
        shutil.rmtree(self.dir, ignore_errors=True); self.dir.mkdir(parents=True)
        labels = self.dir / 'owner_labels.csv'
        labels.write_text('id,label\n' + ''.join(f'{i},{l}\n' for i, l in zip(IDS, LABELS)))
        self.holdout = H.init(self.dir / 'holdout', f'{tag.lower()}-{RUN}', labels, decimals, list(CLASSES), limits)
        self.ledger_path = self.dir / 'ledger.jsonl'
        self.report_pub = vault_ctl.report_key(self.holdout).public_hex
        self.keys = {'witness': WITNESS_PUB, 'gate': GATE.public_hex, 'report': self.report_pub}
        self.witness = WitnessService(PORTS['witness'], key=WITNESS_KEY, gate_keys=(GATE.public_hex,),
                                      tls=server_tls(PKI, 'witness', allow=('governor',)), client=client_tls(PKI, 'governor'))
        self.host_proc = self.vault_proc = None
        self.host_stopped_at = None
        self.host_state = str(self.dir / 'gate_host.sqlite')
        self.base = f'https://127.0.0.1:{PORTS["vault"]}'
        self.store = Store(LOCAL_DSN)

    # ---------------------------------------------------------------- services
    def _await(self, proc, port: int, what: str, wait: float = 15.0) -> None:
        deadline = time.time() + wait
        while time.time() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f'{what} exited with {proc.returncode}')
            try:
                socket.create_connection(('127.0.0.1', port), timeout=0.5).close(); time.sleep(0.15); return
            except OSError:
                time.sleep(0.05)
        raise RuntimeError(f'{what} did not come up')

    def start_host(self, crash_at: str | None = None, fresh: bool = True) -> None:
        if fresh:
            pathlib.Path(self.host_state).unlink(missing_ok=True)
        elif self.host_stopped_at is not None:
            time.sleep(max(0.0, 1.5 - (time.time() - self.host_stopped_at)))       # let the dead owner's lease (1 s) expire
        cmd = [PYTHON, '-B', str(GATEWAY / 'plea_gateway' / 'gate_host.py'), '--port', str(PORTS['host']), '--tools', 'vault_tools', '--key', GATE.private_hex,
               '--state', self.host_state, '--lease', '1.0', '--witness-key', WITNESS_PUB] + _tls_args(server_tls(PKI, 'host', allow=('governor',)))
        env = dict(os.environ, PLEA_VAULT_HOLDOUT=str(self.holdout.dir), PLEA_VAULT_LEDGER=str(self.ledger_path))
        env.pop('PLEA_CRASH_AT', None)
        if crash_at:
            env['PLEA_CRASH_AT'] = crash_at
        self.host_log = open(self.dir / 'host.log', 'a')
        self.host_proc = subprocess.Popen(cmd, cwd=str(VAULT), stdout=self.host_log, stderr=self.host_log, env=env)
        self._await(self.host_proc, PORTS['host'], 'gate host')

    def stop_host(self) -> int | None:
        code = None
        if self.host_proc is not None:
            if self.host_proc.poll() is None:
                self.host_proc.kill()
            code = self.host_proc.wait(timeout=5)
        self.host_stopped_at = time.time()
        return code

    def start_vault(self) -> None:
        cmd = [PYTHON, '-B', str(VAULT / 'vault_service.py'), '--holdout', str(self.holdout.dir), '--port', str(PORTS['vault']), '--local-dsn', LOCAL_DSN,
               '--witness-url', self.witness.url, '--witness-key', WITNESS_PUB, '--gate-host', f'https://127.0.0.1:{PORTS["host"]}', '--gate-key', GATE.public_hex,
               '--tls-cert', PKI['vault'][0], '--tls-key', PKI['vault'][1], '--tls-ca', PKI['ca'], '--upstream-cert', PKI['governor'][0], '--upstream-key', PKI['governor'][1]]
        self.vault_log = open(self.dir / 'vault.log', 'a')
        self.vault_proc = subprocess.Popen(cmd, stdout=self.vault_log, stderr=self.vault_log)
        self._await(self.vault_proc, PORTS['vault'], 'front door')

    def start(self, crash_at: str | None = None) -> 'Deployment':
        self.witness.start(); self.start_host(crash_at); self.start_vault(); return self

    def stop(self) -> None:
        for proc in (self.vault_proc, self.host_proc):
            if proc is not None and proc.poll() is None:
                proc.kill(); proc.wait(timeout=5)
        self.witness.stop()
        time.sleep(0.2)

    # ---------------------------------------------------------------- the owner's actions
    def ctl(self, *args) -> dict:
        out = subprocess.run([PYTHON, '-B', str(VAULT / 'vault_ctl.py'), str(self.holdout.dir), *map(str, args)], capture_output=True, text=True)
        if out.returncode != 0:
            raise RuntimeError(f'vault_ctl {args}: {out.stderr.strip()[-300:]}')
        return json.loads(out.stdout)

    def enrol(self, name: str, budget: int, replacement: int = 0) -> Client:
        self.ctl('enrol', name, '--budget', budget, '--replacement', replacement, '--pki', PKI['dir'], '--days', 1, '--organisation', f'{name} org')
        return self.client(name)

    def client(self, name: str, pki: dict | None = None) -> Client:
        pki = pki or PKI
        cert, key = pki[name] if name in pki else (str(PKI['dir'] / f'{name}.crt'), str(PKI['dir'] / f'{name}.key'))
        return Client(self.base, PKI['ca'], cert, key)

    def plant(self, name: str, data: bytes) -> str:
        """Put a file past the front door: straight into the uploads directory and the index, with no check."""
        sha = H.sha256_hex(data)
        path = self.holdout.upload_path(name, sha); path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        Index(self.holdout.dir / 'index.sqlite').add_upload(name, sha, len(data))
        return sha

    # ---------------------------------------------------------------- what happened
    def ledger(self, event: str | None = None, sha: str | None = None) -> list:
        if not self.ledger_path.exists():
            return []
        rows = [json.loads(l) for l in self.ledger_path.read_text().splitlines() if l.strip()]
        return [r for r in rows if (event is None or r['event'] == event) and (sha is None or r.get('submission_sha256') == sha)]

    def audit(self, name: str) -> list:
        return self.store.audit(self.holdout.root(name))

    def codes(self, name: str) -> list:
        return [f"{d['op'][0]} {d['kind']} {d['code']}" for d in self.audit(name)]


def up(client: Client, data: bytes) -> str:
    status, body = client.upload(data)
    if status != 200:
        raise RuntimeError(f'upload refused: {status} {body}')
    return body['sha256']


def verify(report: dict, keys: dict) -> tuple[bool, list]:
    ok, checks, _ = plea_verify.verify(report, keys)
    return ok, [f'{n} {t}: {d}' for n, t, good, d in checks if not good]


# ====================================================================== the tests
def v1():
    """A fourth distinct submission is refused and the scoring tool is not run."""
    d = Deployment('V1').start(); e = {}
    try:
        alice = d.enrol('alice', 3)
        shas = [up(alice, predictions(wrong={i})) for i in range(4)]
        first = [alice.score(s) for s in shas[:3]]
        called_before = len(d.ledger('called'))
        fourth = alice.score(shas[3])
        st = alice.status()[1]
        e.update(first=[(s, b.get('outcome')) for s, b in first], fourth=fourth, called_before=called_before, called_after=len(d.ledger('called')),
                 scored=len(d.ledger('scored')), status={k: st[k] for k in ('allowed', 'used', 'refunded', 'remaining')}, last_audit=d.codes('alice')[-1])
        checks = {'three scored': all(s == 200 and b.get('outcome') == 'EFFECT' for s, b in first) and e['scored'] == 3,
                  'fourth refused for budget': fourth == (409, {'refused': 'BUDGET_EXHAUSTED'}),
                  'tool not run for the fourth': e['called_after'] == called_before == 3 and not d.ledger(sha=shas[3]),
                  'budget shows 3 used, 0 remaining': e['status'] == {'allowed': 3, 'used': 3, 'refunded': 0, 'remaining': 0},
                  'refusal is on the audit log': e['last_audit'] == 'RESERVE DENIED BUDGET_EXHAUSTED'}
    finally:
        d.stop()
    return checks, e


def v2():
    """The same submission twice: one charge, the same score."""
    d = Deployment('V2').start(); e = {}
    try:
        alice = d.enrol('alice', 3)
        data = predictions(wrong={0, 1, 2, 3})
        sha = up(alice, data)
        a, b = alice.score(sha), alice.score(sha)
        again = alice.upload(data)
        st = alice.status()[1]
        e.update(first=a, second=b, upload_again=again, opened=len(d.ledger('labels_opened')), scored=len(d.ledger('scored')), used=st['used'], attempts=len(st['uploads']))
        checks = {'both answers are the same score': a[0] == b[0] == 200 and a[1] == b[1] and a[1]['result']['score'] == '0.90',
                  'one charge': st['used'] == 1 and st['remaining'] == 2,
                  'labels opened once': e['opened'] == 1 and e['scored'] == 1,
                  'uploading the same file again stores nothing new': again == (200, {'sha256': sha, 'stored': False})}
    finally:
        d.stop()
    return checks, e


def v3():
    """The backstop: an invalid file placed past the front door gives NO_EFFECT, refunded up to the allowance, then charged."""
    d = Deployment('V3').start(); e = {}
    try:
        alice = d.enrol('alice', 3, replacement=1)
        bad1 = d.plant('alice', predictions().replace(b'r000,a', b'r000,z'))        # a class outside the manifest
        bad2 = d.plant('alice', b'id,prediction\nr000,a\n')                         # one row instead of forty
        r1 = alice.score(bad1); s1 = alice.status()[1]
        r2 = alice.score(bad2); s2 = alice.status()[1]
        good = alice.score(up(alice, predictions()))
        e.update(first=r1, after_first={k: s1[k] for k in ('used', 'refunded', 'remaining')}, second=r2, after_second={k: s2[k] for k in ('used', 'refunded', 'remaining')},
                 rejected=[(r['reason'], r['submission_sha256'][:8]) for r in d.ledger('rejected')], opened_for_bad=len(d.ledger('labels_opened', bad1)) + len(d.ledger('labels_opened', bad2)),
                 good=good[1].get('outcome'), audit_tail=d.codes('alice')[-3:])
        checks = {'both give NO_EFFECT': r1[0] == r2[0] == 200 and r1[1]['outcome'] == r2[1]['outcome'] == 'NO_EFFECT',
                  'the tool rejected them with their codes': [r['reason'] for r in d.ledger('rejected')] == ['BAD_CLASS', 'ROW_COUNT'],
                  'the labels were not opened for them': e['opened_for_bad'] == 0,
                  'the first is refunded': e['after_first'] == {'used': 0, 'refunded': 1, 'remaining': 3},
                  'beyond the allowance the second is charged': e['after_second'] == {'used': 1, 'refunded': 1, 'remaining': 2},
                  'a valid file still scores': good[0] == 200 and good[1].get('outcome') == 'EFFECT'}
    finally:
        d.stop()
    return checks, e


def v4():
    """Scoring killed mid-run gives UNKNOWN, stays charged and is never re-run."""
    d = Deployment('V4').start(crash_at='vault_scoring'); e = {}
    try:
        alice = d.enrol('alice', 3)
        sha = up(alice, predictions(wrong={5}))
        during = alice.score(sha)
        time.sleep(0.3); exit_code = d.host_proc.poll()
        d.stop_host(); d.start_host(fresh=False)                                   # the same state file, no crash this time
        after1 = alice.score(sha); after2 = alice.score(sha)
        st = alice.status()[1]
        other = alice.score(up(alice, predictions(wrong={6})))
        rep = alice.report()[1]; ok, why = verify(rep, d.keys)
        e.update(during=during, host_exit=exit_code, after_restart=[after1, after2], opened=len(d.ledger('labels_opened', sha)), scored=len(d.ledger('scored', sha)),
                 called=len(d.ledger('called', sha)), used=st['used'], outcome_in_status=[u['outcome'] for u in st['uploads']], other=other[1].get('outcome'),
                 reconcile=[c for c in d.codes('alice') if c.startswith('RECONCILE')][:2], report_verifies=ok, why=why)
        checks = {'the host died while scoring (exit 137)': exit_code == 137 and during[0] == 503,
                  'afterwards the answer is UNKNOWN, twice': all(r == (200, {'outcome': 'UNKNOWN', 'detail': 'no score; attempt used'}) for r in (after1, after2)),
                  'never re-run: called once, labels opened once, no score': (e['called'], e['opened'], e['scored']) == (1, 1, 0),
                  'the attempt stays charged': st['used'] == 1 and e['outcome_in_status'] == ['UNKNOWN'],
                  'the witness recorded UNKNOWN stays charged': 'RECONCILE NOOP VERDICT_UNKNOWN_STAYS_CHARGED' in e['reconcile'],
                  'another file still scores, and the report verifies': other[1].get('outcome') == 'EFFECT' and ok}
    finally:
        d.stop()
    return checks, e


def _leaves(node, path=()):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _leaves(v, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _leaves(v, path + (i,))
    else:
        yield path, node


def _edited(report: dict, path: tuple, value):
    copy = json.loads(json.dumps(report)); node = copy
    for p in path[:-1]:
        node = node[p]
    if isinstance(value, bool):          new = not value
    elif isinstance(value, int):         new = value + 1
    elif isinstance(value, str):         new = (('1' if value[-1] != '1' else '2') if value else 'x').join((value[:-1], ''))
    else:                                new = 'x'                                    # null
    node[path[-1]] = new
    return copy


def v5():
    """The report verifies offline; any edited field fails."""
    d = Deployment('V5').start(); e = {}
    try:
        alice = d.enrol('alice', 3, replacement=1)
        for wrong in ({1}, {1, 2}):
            alice.score(up(alice, predictions(wrong=wrong)))
        alice.score(d.plant('alice', b'id,prediction\n'))                          # one NO_EFFECT, so every kind of field is present
        alice.score(up(alice, predictions(wrong={1, 2, 3}))); alice.score(up(alice, predictions(wrong={4})))    # the last is refused: budget
        status, report = alice.report()
        ok, why = verify(report, d.keys)
        path = d.dir / 'report.json'; path.write_text(json.dumps(report, indent=1))
        cli = subprocess.run([PYTHON, '-B', str(VAULT / 'plea_verify.py'), str(path), '--witness-key', WITNESS_PUB, '--gate-key', GATE.public_hex, '--report-key', d.report_pub],
                             capture_output=True, text=True)
        unpinned = subprocess.run([PYTHON, '-B', str(VAULT / 'plea_verify.py'), str(path)], capture_output=True, text=True)
        leaves = list(_leaves(report))
        survived = ['.'.join(map(str, p)) for p, v in leaves if plea_verify.verify(_edited(report, p, v), d.keys)[0]]
        # an insider who holds the report key but not the witness or gate keys: edit one field, then sign the report again
        signer = ReportKey((d.holdout.dir / 'report.key').read_text().strip()); resigned = []
        for p, v in leaves:
            if p[0] == 'signature':
                continue
            body = {k: x for k, x in _edited(report, p, v).items() if k != 'signature'}
            forged = dict(body, signature={'signer': signer.public_hex, 'signature': signer.sign(canonical(body).encode())})
            if plea_verify.verify(forged, d.keys)[0]:
                resigned.append('.'.join(map(str, p)))
        only_report_key = sorted({r.split('.')[0] if r.split('.')[0] == 'enrolment' else r for r in resigned})
        wrong_key = plea_verify.verify(report, dict(d.keys, report=ReportKey().public_hex))[0]
        e.update(report_status=status, verifies=ok, why=why, cli_exit=cli.returncode, cli_last_line=cli.stdout.strip().splitlines()[-1][:60] if cli.stdout.strip() else '',
                 unpinned_exit=unpinned.returncode, unpinned_last=unpinned.stdout.strip().splitlines()[-1][:40] if unpinned.stdout.strip() else '',
                 fields=len(leaves), edits_that_still_verify=survived, resigned_edits_that_verify=only_report_key, outcomes=[a['outcome'] for a in report['attempts']],
                 audit_rows=len(report['audit']))
        checks = {'the report verifies, by library and by command line': ok and cli.returncode == 0 and 'VERIFIED' in cli.stdout,
                  'without pinned keys it says consistent, not verified': unpinned.returncode == 0 and 'CONSISTENT' in unpinned.stdout and 'VERIFIED' not in unpinned.stdout,
                  'every single-field edit fails': not survived and len(leaves) > 200,
                  'a wrong report key fails': not wrong_key,
                  're-signed edits verify only for fields the report key alone covers': only_report_key == ['as_of.time', 'certificate_sha256', 'enrolment']}
    finally:
        d.stop()
    return checks, e


def v6():
    """A submitter's certificate reaches the front door only: not the witness, the gate host, the database, the labels or another submitter's record."""
    d = Deployment('V6').start(); e = {}
    try:
        alice, bob = d.enrol('alice', 3), d.enrol('bob', 3)
        bob_sha = up(bob, predictions(wrong={9})); bob.score(bob_sha)
        alice.score(up(alice, predictions(wrong={8})))
        sealed = (d.holdout.dir / 'labels.sealed'); salt = sealed.read_text().splitlines()[0].split(',')[1]
        direct = Client(d.witness.url, PKI['ca'], alice.cert, alice.key).call('GET', '/pubkey')
        direct_host = Client(f'https://127.0.0.1:{PORTS["host"]}', PKI['ca'], alice.cert, alice.key).call('GET', '/tools')
        direct_run = Client(f'https://127.0.0.1:{PORTS["host"]}', PKI['ca'], alice.cert, alice.key).call('POST', '/run', json_body={'root': 'x', 'aid': 'y', 'receipt': {}})
        probes = ['/labels.sealed', '/labels', '/../labels.sealed', '/uploads/bob/' + bob_sha + '.csv', '/index.sqlite', '/report.key', '/status/bob', '/report?submitter=bob',
                  '/status?submitter=bob', '/%2e%2e/labels.sealed', '/audit', '/manifest/../labels.sealed']
        probed = {p: alice.call('GET', p) for p in probes}
        bodies = [alice.call('GET', p) for p in ('/manifest', '/ids', '/status', '/report')]
        text = json.dumps([b for _, b in bodies] + [b for _, b in probed.values()])
        stranger = [d.client('stranger').call(m, p, body=b'x' if m == 'POST' else None) for m, p in (('GET', '/status'), ('GET', '/report'), ('GET', '/manifest'), ('POST', '/upload'), ('POST', '/score'))]
        impostor = Client(d.base, PKI['ca'], *PKI['impostor']['alice']).call('GET', '/status')
        cross = alice.score(bob_sha)
        arep = alice.report()[1]
        try:                                                                       # the submitter is given a certificate and nothing else: the database has no login for it
            psycopg.connect('postgresql://alice@127.0.0.1:5432/plea', connect_timeout=3).close(); database = 'connected'
        except psycopg.OperationalError:
            database = 'refused'
        e.update(witness_direct=direct, host_direct=direct_host, host_run_direct=direct_run, probes={p: s for p, (s, _) in probed.items()}, sealed_mode=oct(sealed.stat().st_mode & 0o777),
                 report_key_mode=oct((d.holdout.dir / 'report.key').stat().st_mode & 0o777), stranger=[s for s, _ in stranger], other_ca=impostor, scoring_bobs_hash=cross,
                 alice_report_roots=sorted({arep['root']} | {r['root'] for a in arep['attempts'] for r in a['receipts'].values()}), database_as_alice=database)
        checks = {'the witness and the gate host refuse the submitter\'s certificate': direct[0] == 403 and direct_host[0] == 403 and direct_run[0] == 403,
                  'no front-door path returns anything but 404 outside the six endpoints': all(s == 404 for s, _ in probed.values()),
                  'no response holds the salt, a label row or the other submitter\'s hash': salt not in text and 'r000,a' not in text and bob_sha not in text and 'bob' not in text,
                  'the sealed labels and the report key are readable by their owner only': e['sealed_mode'] == '0o600' and e['report_key_mode'] == '0o600',
                  'an unenrolled certificate is refused everywhere': all(s == 403 for s, _ in stranger),
                  'a certificate from another authority cannot connect': impostor[0] is None and 'UNKNOWN_CA' in str(impostor[1]),
                  'scoring another submitter\'s hash is refused': cross == (404, {'refused': 'UNKNOWN_SUBMISSION'}),
                  'the report covers the caller\'s own budget only': e['alice_report_roots'] == [d.holdout.root('alice')],
                  'the database has no login for the submitter': database == 'refused'}
    finally:
        d.stop()
    return checks, e


def v7():
    """An invalid upload is rejected with its code; no attempt and no audit row is created."""
    d = Deployment('V7', limits={'max_bytes': 4096}).start(); e = {}
    try:
        alice = d.enrol('alice', 3, replacement=1)
        good = predictions()
        cases = {'TOO_LARGE': good + b'#' * 5000, 'NOT_UTF8': good[:-2] + b'\xff\n', 'BAD_HEADER': good.replace(b'id,prediction', b'id,answer'),
                 'ROW_COUNT': good.rsplit(b'\n', 2)[0] + b'\n', 'UNKNOWN_ID': good.replace(b'r005,', b'x005,'), 'DUPLICATE_ID': good.replace(b'r006,', b'r005,'),
                 'BAD_CLASS': good.replace(b'r007,b', b'r007,d')}
        got = {code: alice.upload(data) for code, data in cases.items()}
        st = alice.status()[1]
        scored = alice.score(H.sha256_hex(cases['BAD_CLASS']))
        e.update(answers={c: r for c, r in got.items()}, audit_rows=len(d.audit('alice')), ledger_lines=len(d.ledger()), status={k: st[k] for k in ('used', 'refunded', 'remaining')},
                 uploads_listed=len(st['uploads']), files=len(list((d.holdout.dir / 'uploads').rglob('*.csv'))), scoring_a_rejected_hash=scored)
        checks = {'each is rejected with its own code': all(got[c] == (400, {'rejected': c}) for c in cases) and set(cases) == set(H.CODES),
                  'no attempt, no audit row, nothing charged or refunded': e['audit_rows'] == 0 and e['status'] == {'used': 0, 'refunded': 0, 'remaining': 3},
                  'nothing was stored and the tool was never called': e['files'] == 0 and e['uploads_listed'] == 0 and e['ledger_lines'] == 0,
                  'a rejected file cannot be scored': scored == (404, {'refused': 'UNKNOWN_SUBMISSION'})}
    finally:
        d.stop()
    return checks, e


def v8():
    """The score equals the manifest's rounding at the boundaries (0, 1, ties); the result has no other label-dependent field."""
    d = Deployment('V8').start(); e = {}
    try:
        alice = d.enrol('alice', 6)
        want = {40: '0.00', 0: '1.00', 39: '0.02', 37: '0.08', 35: '0.12', 33: '0.18'}      # wrong rows -> score: 1/40, 3/40, 5/40, 7/40 are ties
        got = {}
        for n_wrong in want:
            status, body = alice.score(up(alice, predictions(wrong=set(range(n_wrong)))))
            got[n_wrong] = body.get('result') if status == 200 else body
        table = [((87, 100, 2), '0.87'), ((2, 3, 2), '0.67'), ((1, 8, 2), '0.12'), ((3, 8, 2), '0.38'), ((1, 200, 2), '0.00'), ((3, 200, 2), '0.02'),
                 ((5, 8, 1), '0.6'), ((1, 2, 0), '0'), ((3, 4, 0), '1'), ((1, 1, 3), '1.000'), ((0, 9, 4), '0.0000')]
        e.update(scores={str(40 - w): (r or {}).get('score') for w, r in got.items()}, result_keys=sorted(got[0]), unit_table=[H.round_score(*a) for a, _ in table])
        checks = {'the six scores are the declared rounding': all((got[w] or {}).get('score') == s for w, s in want.items()),
                  'the result holds exactly the six contract fields': all(set(r) == {'score', 'metric', 'decimals', 'rows', 'submission_sha256', 'manifest_sha256'} for r in got.values()),
                  'the fields other than the score do not depend on the labels': all((r['metric'], r['decimals'], r['rows'], r['manifest_sha256']) == ('accuracy', 2, 40, d.holdout.manifest_sha256) for r in got.values()),
                  'the rounding rule holds on a table of ties and edges': all(H.round_score(*a) == s for a, s in table)}
    finally:
        d.stop()
    return checks, e


def v9():
    """A report holding one each of EFFECT, NO_EFFECT, UNKNOWN and pending verifies and shows its as-of sequence number."""
    d = Deployment('V9').start(crash_at='vault_scoring'); e = {}
    try:
        alice = d.enrol('alice', 4, replacement=1)
        killed = up(alice, predictions(wrong={1})); alice.score(killed)
        d.stop_host(); d.start_host(fresh=False)
        r_unknown = alice.score(killed)
        r_effect = alice.score(up(alice, predictions(wrong={2})))
        r_none = alice.score(d.plant('alice', b'id,prediction\nnot,forty,rows\n'))
        d.witness.stop()                                                           # the next attempt reserves, then cannot reach the witness
        r_pending = alice.score(up(alice, predictions(wrong={3})))
        status, report = alice.report()
        ok, why = verify(report, d.keys)
        _, _, summary = plea_verify.verify(report, d.keys)
        st = alice.status()[1]
        e.update(answers=dict(unknown=r_unknown, effect=r_effect[1].get('outcome'), no_effect=r_none, pending=r_pending), outcomes=sorted(a['outcome'] for a in report['attempts']),
                 phases=sorted(a['phase'] for a in report['attempts']), verifies=ok, why=why, as_of_seq=report['as_of']['seq'], audit_rows=len(report['audit']),
                 summary={k: summary[k] for k in ('allowed', 'used', 'refunded', 'remaining')}, status={k: st[k] for k in ('used', 'refunded', 'remaining')})
        checks = {'the report holds one of each': e['outcomes'] == ['EFFECT', 'NO_EFFECT', 'PENDING', 'UNKNOWN'],
                  'the pending attempt answered unavailable': r_pending[0] == 503,
                  'the report verifies': ok,
                  'it shows its as-of sequence number, the number of audit rows': e['as_of_seq'] == e['audit_rows'] > 0,
                  'pending and unknown count as charged, the rejected one is refunded': e['summary'] == {'allowed': 4, 'used': 3, 'refunded': 1, 'remaining': 1}}
    finally:
        d.stop()
    return checks, e


def v10():
    """A stopped submitter is refused at admission; a revoked, expired or superseded certificate is refused at the front door."""
    d = Deployment('V10').start(); e = {}
    try:
        alice, bob = d.enrol('alice', 3), d.enrol('bob', 3)
        scored = up(alice, predictions(wrong={1})); first = alice.score(scored)
        fresh = up(alice, predictions(wrong={2}))
        stop = subprocess.run([PYTHON, '-B', str(GATEWAY / 'mcp' / 'plea_ctl.py'), d.holdout.root('alice'), 'stop'], capture_output=True, text=True)   # the v1.2.1 control plane
        called = len(d.ledger('called'))
        refused = alice.score(fresh); replay = alice.score(scored)
        called_after = len(d.ledger('called')); ran_fresh = len(d.ledger(sha=fresh))      # counted before anyone else scores
        bob_ok = bob.score(up(bob, predictions(wrong={3})))
        revoke = d.ctl('revoke', 'bob'); bob_after = [bob.status(), bob.score('a' * 64)]
        # an expired certificate, enrolled with its true fingerprint so that expiry is the only thing wrong with it
        index = Index(d.holdout.dir / 'index.sqlite'); ca_key, ca_cert = (PKI['dir'] / 'ca.key').read_bytes(), (PKI['dir'] / 'ca.crt').read_bytes()
        outcomes = {}
        for name, days in (('erin', 0), ('frank', 1)):
            key, cert = TLS.issue(ca_key, ca_cert, name, 'client', (), days)
            (PKI['dir'] / f'{name}.key').write_bytes(key); (PKI['dir'] / f'{name}.crt').write_bytes(cert)
            fp, issued, expires = vault_ctl.fingerprint(cert)
            Store(os.environ.get('PLEA_CONTROL_DSN', 'postgresql://plea_control:control@127.0.0.1:5432/plea')).new_root(d.holdout.root(name), 3, 0)
            index.enrol(name, '', '', fp, issued, expires)
            outcomes[name] = expires
        time.sleep(2.0)
        erin, frank = d.client('erin').status(), d.client('frank').status()
        # a renewed certificate replaces the old one: same name, same authority, the old fingerprint is no longer enrolled
        carol = d.enrol('carol', 3); old_dir = d.dir / 'carol_old'; old_dir.mkdir()
        for ext in ('crt', 'key'):
            shutil.copy(PKI['dir'] / f'carol.{ext}', old_dir / f'carol.{ext}')
        before = carol.status()[0]; d.ctl('renew', 'carol', '--pki', PKI['dir'], '--days', 1)
        superseded = Client(d.base, PKI['ca'], str(old_dir / 'carol.crt'), str(old_dir / 'carol.key')).status(); renewed = d.client('carol').status()[0]
        e.update(first=first[1].get('outcome'), stop=stop.stdout.strip(), refused=refused, replay=replay[1].get('result', {}).get('score') if isinstance(replay[1], dict) else replay,
                 called_before=called, called_after=called_after, ledger_lines_for_refused_file=ran_fresh, audit_tail=d.codes('alice')[-2:], bob_before=bob_ok[1].get('outcome'), revoke=revoke,
                 bob_after=bob_after, erin=erin, frank=frank[0], erin_expires=outcomes['erin'], carol=dict(before=before, old_certificate=superseded, new_certificate=renewed))
        checks = {'a stopped submitter is refused, and the tool is not run': refused == (409, {'refused': 'STOPPED'}) and called_after == called == 1 and ran_fresh == 0,
                  'the refusal is at admission, on the audit log': e['audit_tail'][-1].startswith('RESERVE DENIED') and any(c.startswith('STOP APPLIED') for c in d.codes('alice')),
                  'an already-scored hash still returns its stored score': replay[0] == 200 and replay[1] == first[1],
                  'a revoked submitter is refused at once, with no restart': all(r == (403, {'refused': 'NOT_ENROLLED'}) for r in bob_after) and bob_ok[0] == 200,
                  'an expired certificate cannot connect': erin[0] is None and 'EXPIRED' in str(erin[1]),
                  'the same enrolment with a valid certificate is served': frank[0] == 200,
                  'after renewal the old certificate is refused and the new one served': before == 200 and superseded == (403, {'refused': 'NOT_ENROLLED'}) and renewed == 200}
    finally:
        d.stop()
    return checks, e


def v11():
    """An oversize file and an eleventh unscored upload are refused."""
    d = Deployment('V11', limits={'max_bytes': 2048}).start(); e = {}
    try:
        alice = d.enrol('alice', 3)
        big = alice.upload(predictions() + b'\n' * 2000)
        ten = [alice.upload(predictions(wrong={i}))[0] for i in range(10)]
        eleventh = alice.upload(predictions(wrong={10}))
        alice.score(H.sha256_hex(predictions(wrong={0})))
        after = alice.upload(predictions(wrong={10}))
        e.update(oversize=big, ten=ten, eleventh=eleventh[0], eleventh_body=eleventh[1].get('refused'), after_scoring_one=after[0],
                 files=len(list((d.holdout.dir / 'uploads').rglob('*.csv'))))
        checks = {'an oversize file is refused with TOO_LARGE': big == (400, {'rejected': 'TOO_LARGE'}),
                  'ten unscored uploads are held': ten == [200] * 10,
                  'the eleventh is refused': eleventh[0] == 409 and eleventh[1].get('refused') == 'UPLOAD_CAP',
                  'after one is scored another upload is accepted': after[0] == 200 and after[1].get('stored') is True and e['files'] == 11}
    finally:
        d.stop()
    return checks, e


def v12():
    """Requests beyond the per-minute limit are refused, per certificate."""
    d = Deployment('V12', limits={'max_requests_per_minute': 20}).start(); e = {}
    try:
        alice, bob = d.enrol('alice', 3), d.enrol('bob', 3)
        statuses = [alice.status()[0] for _ in range(22)]
        over = alice.upload(predictions())
        bob_status = bob.status()[0]
        e.update(first_twenty=statuses[:20], next_two=statuses[20:], upload_while_limited=over, other_submitter=bob_status, audit_rows=len(d.audit('alice')))
        checks = {'twenty requests are served': statuses[:20] == [200] * 20,
                  'the next are refused with RATE_LIMIT': statuses[20:] == [429, 429] and over == (429, {'refused': 'RATE_LIMIT'}),
                  'another submitter is not affected': bob_status == 200,
                  'a refused request creates no attempt': e['audit_rows'] == 0}
    finally:
        d.stop()
    return checks, e


def v13():
    """Six different files sent at once against a budget of three: three are scored, never more."""
    d = Deployment('V13').start(); e = {}
    try:
        alice = d.enrol('alice', 3)
        shas = [up(alice, predictions(wrong={i})) for i in range(6)]
        answers, rounds = {}, 0
        def go(sha):
            answers[sha] = alice.score(sha)
        while len(answers) < 6 or any(a[1].get('refused') == 'IN_PROGRESS' for a in answers.values() if isinstance(a[1], dict)):
            todo = [s for s in shas if s not in answers or answers[s][1].get('refused') == 'IN_PROGRESS']
            threads = [threading.Thread(target=go, args=(s,)) for s in todo]
            [t.start() for t in threads]; [t.join(60) for t in threads]
            rounds += 1
            if rounds == 1:
                first_round = sorted(str(a[1].get('outcome') or a[1].get('refused')) for a in answers.values())
            if rounds > 20:
                break
        final = sorted(str(a[1].get('outcome') or a[1].get('refused')) for a in answers.values())
        st = alice.status()[1]; rep = alice.report()[1]; ok, why = verify(rep, d.keys)
        e.update(first_round=first_round, rounds=rounds, final=final, scored=len(d.ledger('scored')), opened=len(d.ledger('labels_opened')), called=len(d.ledger('called')),
                 status={k: st[k] for k in ('allowed', 'used', 'refunded', 'remaining')}, report_verifies=ok, why=why)
        checks = {'three are scored and three refused for budget': final == ['BUDGET_EXHAUSTED'] * 3 + ['EFFECT'] * 3,
                  'the labels were opened three times, never more': (e['called'], e['opened'], e['scored']) == (3, 3, 3),
                  'the budget shows 3 used, 0 remaining, and the report verifies': e['status'] == {'allowed': 3, 'used': 3, 'refunded': 0, 'remaining': 0} and ok}
    finally:
        d.stop()
    return checks, e


TESTS = {'V1': v1, 'V2': v2, 'V3': v3, 'V4': v4, 'V5': v5, 'V6': v6, 'V7': v7, 'V8': v8, 'V9': v9, 'V10': v10, 'V11': v11, 'V12': v12, 'V13': v13}


def main():
    global PKI
    wanted = [a for a in sys.argv[1:] if a in TESTS] or list(TESTS)
    OUT.mkdir(parents=True, exist_ok=True)
    PKI = make_pki()
    results, t0 = {}, time.time()
    for name in wanted:
        started = time.time()
        try:
            checks, evidence = TESTS[name]()
            ok = bool(checks) and all(checks.values())
            results[name] = {'title': TESTS[name].__doc__, 'ok': ok, 'checks': checks, 'evidence': evidence, 'seconds': round(time.time() - started, 1)}
        except Exception as exc:                                                     # a harness or service error is a failed test, never a pass
            results[name] = {'title': TESTS[name].__doc__, 'ok': False, 'checks': {}, 'error': f'{type(exc).__name__}: {exc}'[:400], 'seconds': round(time.time() - started, 1)}
        r = results[name]
        print(f"{name:<4} {'PASS' if r['ok'] else 'FAIL'}  {r['title']}" + ('' if r['ok'] else '   <- ' + (r.get('error') or ', '.join(k for k, v in r['checks'].items() if not v))), flush=True)
    passed = sum(r['ok'] for r in results.values())
    out = {'run': RUN, 'tests': results, 'passed': passed, 'of': len(results), 'seconds': round(time.time() - t0, 1), 'PASS': passed == len(results) == len(wanted)}
    (GATEWAY / 'outputs' / 'vault_tests.json').write_text(json.dumps(out, indent=1, default=str))
    print(f"VAULT RESULT: {'PASS' if out['PASS'] else 'FAIL'} ({passed} of {len(results)})")
    sys.exit(0 if out['PASS'] else 1)


if __name__ == '__main__':
    main()
