"""The honest gate host, in ANOTHER PROCESS (K-CAP-1).

Run as a script, it generates the gate's signing key in its own memory, never writes it anywhere, and answers JSON lines
on stdin/stdout.  It exposes only its public key.  It signs only what an honest gate host signs (spec 1.2, 3.6, D-3,
D-6, D-7):

  intent_accepted (root, aid, nonce)   it is told that the witness accepted this run's intent under this nonce
  run (root, aid, nonce, claim, result) one effect report per (budget, run, nonce), and only after intent_accepted for
                                        exactly that triple; claim one of EFFECT, NO_EFFECT, UNKNOWN; result_digest is
                                        always sha256(canonical(result)) - 64 lower-case hex.  Asked again: the same
                                        report, byte for byte (a repeat).  Refused for a run fenced, or for a second
                                        nonce of a run it has already run, or for any other claim.
  fence (root, aid)                     FENCED_NO_START with null nonce and digest, only for a run it has NOT run (any
                                        nonce); afterwards it never runs that run.  Asked again: the same report.

So a fence and an effect report are never both signed for one run, no digest is malformed, no claim is outside the
standard set, and no two verdicts are signed for one run.  A CAP-DB test receives these reports and may replay, pad,
re-send and misdirect them; it cannot sign.

The client class `HonestGate` (imported by tests) starts the process and holds only the pipe and the public key.
"""
import json
import os
import subprocess
import sys
import threading

HERE = os.path.abspath(__file__)


def _serve():                                                     # runs in the gate host's own process
    import hashlib
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.generate()                             # never leaves this process
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    canon = lambda x: json.dumps(x, sort_keys=True, separators=(',', ':'))
    accepted, ran, fenced, by_run = set(), {}, {}, {}

    def sign(kind, root, aid, nonce, claim, digest):
        body = {'kind': kind, 'root': root, 'aid': aid, 'nonce': nonce, 'claim': claim, 'result_digest': digest}
        sig = key.sign(canon(body).encode()).hex()
        return {'kind': kind, 'root': root, 'aid': aid, 'nonce': nonce, 'claim': claim, 'signer': pub, 'signature': sig,
                'result_digest': digest}

    for line in sys.stdin:
        try:
            req = json.loads(line)
            op = req.get('op')
            if op == 'pubkey':
                out = {'public_key': pub}
            elif op == 'intent_accepted':
                accepted.add((req['root'], req['aid'], req['nonce']))
                out = {'ok': True}
            elif op == 'run':
                r, a, n, claim = req['root'], req['aid'], req['nonce'], req['claim']
                if claim not in ('EFFECT', 'NO_EFFECT', 'UNKNOWN') or not isinstance(n, str):
                    out = {'refused': 'not a claim an honest gate host signs'}
                elif (r, a) in fenced:
                    out = {'refused': 'this run was fenced; it is never run'}
                elif (r, a, n) not in accepted:
                    out = {'refused': 'the witness has not accepted this intent'}
                elif (r, a) in by_run and by_run[(r, a)] != n:
                    out = {'refused': 'this run was already run under another nonce'}
                elif (r, a, n) in ran:
                    out = {'report': ran[(r, a, n)], 'repeat': True}
                else:
                    digest = hashlib.sha256(canon(req.get('result')).encode()).hexdigest()
                    ran[(r, a, n)] = sign('EFFECT_REPORT', r, a, n, claim, digest)
                    by_run[(r, a)] = n
                    out = {'report': ran[(r, a, n)], 'repeat': False}
            elif op == 'fence':
                r, a = req['root'], req['aid']
                if (r, a) in by_run:
                    out = {'refused': 'this run was run; it cannot be fenced'}
                elif (r, a) in fenced:
                    out = {'report': fenced[(r, a)], 'repeat': True}
                else:
                    fenced[(r, a)] = sign('FENCE_REPORT', r, a, None, 'FENCED_NO_START', None)
                    out = {'report': fenced[(r, a)], 'repeat': False}
            elif op == 'quit':
                break
            else:
                out = {'refused': 'unknown request'}
        except Exception as exc:                                    # noqa: BLE001 - a malformed request is answered, not fatal
            out = {'refused': f'malformed request: {exc!r}'}
        sys.stdout.write(json.dumps(out) + '\n'); sys.stdout.flush()


class GateRefused(Exception):
    pass


class HonestGate:
    """Client of the honest gate host process.  Holds no key: only a pipe and the public half."""

    def __init__(self):
        self._p = subprocess.Popen([sys.executable, HERE, '--serve'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   text=True, bufsize=1)
        self._lock = threading.Lock()
        self.public_key = self._ask({'op': 'pubkey'})['public_key']
        self.pid = self._p.pid

    def _ask(self, req):
        with self._lock:
            self._p.stdin.write(json.dumps(req) + '\n'); self._p.stdin.flush()
            line = self._p.stdout.readline()
        if not line:
            raise RuntimeError('the honest gate host process has gone')
        return json.loads(line)

    def intent_accepted(self, root, aid, nonce):
        self._ask({'op': 'intent_accepted', 'root': root, 'aid': aid, 'nonce': nonce})

    def run(self, root, aid, nonce, claim, result=None) -> dict:
        out = self._ask({'op': 'run', 'root': root, 'aid': aid, 'nonce': nonce, 'claim': claim, 'result': result})
        if 'refused' in out:
            raise GateRefused(out['refused'])
        return out['report']

    def fence(self, root, aid) -> dict:
        out = self._ask({'op': 'fence', 'root': root, 'aid': aid})
        if 'refused' in out:
            raise GateRefused(out['refused'])
        return out['report']

    def close(self):
        try:
            self._ask({'op': 'quit'})
        except Exception:                                           # noqa: BLE001
            pass
        try:
            self._p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._p.kill()


if __name__ == '__main__' and '--serve' in sys.argv:
    _serve()
