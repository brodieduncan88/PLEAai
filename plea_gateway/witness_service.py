#!/usr/bin/env python3
"""The witness service: the only holder of the plea_witness credential and of the receipt-signing key.

    witness_service.py --port 8787 --dsn postgresql://plea_witness:...@host/plea --gate-key HEX [--key HEX] [--chaos]

POST /accept   {"root": r, "op": [...], "evidence": {...} | null}
               op is ['ACCEPT_RESERVATION', a], ['ACCEPT_INTENT', a], ['RELEASE', a], ['RECONCILE', a] or, since v0.7,
               ['CROSS', a]: the crossing is applied by the witness and receipted, and the gate host requires that
               receipt (the admission) before it runs anything.  For the
               last two the label is derived from the gate-signed evidence (G03); an op that carries a label is 400.
               -> 200 {"kind", "code", "seq", "hash", "applied": [...the labelled op...], "receipt": {...signed...}}
               400 malformed input or a supplied label  403 the database refused the role  404 unknown root
GET  /pubkey   {"public_key": hex, "gate_keys": [hex, ...], "tls": bool, "peer": the client's certificate name or null}
GET  /checkpoint?root=R[&nonce=N][&at=K]      (verification Amendment 10)
               -> 200 a signed statement of root R's chain as the witness reads it now: {"statement": "CHECKPOINT", "root",
               "seq", "head", "business", "witness", "time", "nonce", "at", "head_at", "signer", "signature"}.  seq is the
               number of decisions recorded and head the hash of the last (of the provisioning record when seq is 0).
               nonce (1 to 64 of A-Z a-z 0-9 _ -) is signed back.  at=K asks also for head_at, the head after decision K.
               It reads; it changes nothing and adds no decision.  400 malformed  404 unknown root
               --tls-allow-read NAME admits a client certificate to this path alone: it cannot POST /accept.

TLS (v0.5): with --tls-cert, --tls-key and --tls-ca the service speaks HTTPS and requires a client certificate issued
by --tls-ca; --tls-allow NAME (repeatable) admits only those client names.  Without them it speaks plain HTTP on
loopback, as before.

--gate-key may be given more than once.  --chaos honours the request header X-Plea-Crash-At, which makes this
process die at that point of the store's transaction (faults.py).  It exists for the W4 test and must never be
set in a deployed service.
"""
import argparse
import json
import os
import pathlib
import re
import ssl
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from plea_gateway import plea_budget_ref as ref                          # noqa: E402
from plea_gateway.receipts import WITNESSED, Signer, sign_checkpoint     # noqa: E402
from plea_gateway.store import AuthorityError, Store, UnknownRoot        # noqa: E402
from plea_gateway.tls import TLSHandlerMixin, add_server_args, server_from_args, wrap_server   # noqa: E402
from plea_gateway.witness import EVIDENCE_OPS, binding_for, derive_op    # noqa: E402


def make_handler(store: Store, signer: Signer, gate_keys: tuple, chaos: bool, allow=(), read_allow=()):
    class Handler(TLSHandlerMixin, BaseHTTPRequestHandler):
        tls_allow = tuple(allow)                                      # v0.5: client names admitted over TLS
        tls_read = tuple(read_allow)                                  # verification Amendment 10: names admitted to GET /checkpoint only

        def log_message(self, *args):                                 # quiet
            pass

        def _send(self, status: int, payload: dict):
            body = json.dumps(payload).encode()
            self.send_response(status); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            url = urllib.parse.urlsplit(self.path)
            reading = url.path == '/checkpoint' and self.peer_name in self.tls_read      # a reading name is admitted to this one path, and to nothing that writes
            if not (reading or self.fully_allowed()):
                return self._send(403, {'error': f'client {self.peer_name!r} is not allowed'})
            if self.path == '/pubkey':
                return self._send(200, {'public_key': signer.public_hex, 'gate_keys': list(gate_keys),
                                        'tls': isinstance(self.connection, ssl.SSLSocket), 'peer': self.peer_name})
            if url.path == '/checkpoint':                             # verification Amendment 10: a signed reading, no decision
                q = urllib.parse.parse_qs(url.query, keep_blank_values=True)
                root, nonce, at = q.get('root', [None])[-1], q.get('nonce', [None])[-1], q.get('at', [None])[-1]
                if not root or len(root) > 512 or re.search(r'[\x00-\x1f\x7f]', root) or (nonce is not None and not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', nonce)) \
                        or (at is not None and not re.fullmatch(r'[0-9]{1,12}', at)):
                    return self._send(400, {'error': 'malformed request'})
                try:
                    state, seq, head = store.state(root)
                    head_at = None
                    if at is not None:
                        at = int(at)
                        if at > seq:
                            return self._send(400, {'error': 'at is beyond the chain'})
                        head_at = head if at == seq else (store.provisioning(root) or {}).get('hash') if at == 0 else store.decision_hash(root, at)   # one row
                        if head_at is None:
                            return self._send(400, {'error': 'no decision at that number'})
                except UnknownRoot:
                    return self._send(404, {'error': 'unknown root'})
                except AuthorityError as exc:
                    return self._send(403, {'error': str(exc)})
                return self._send(200, sign_checkpoint(signer, root, seq, head, state.business.value, state.witness.value,
                                                       time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), nonce, at, head_at))
            self._send(404, {'error': 'not found'})

        def fully_allowed(self) -> bool:
            """Admitted to everything the witness does.  A name given only as a reading name is not, even where no --tls-allow
            list is set and every other certificate is."""
            return self.peer_allowed() and not (self.peer_name in self.tls_read and self.peer_name not in self.tls_allow)

        def do_POST(self):
            if not self.fully_allowed():
                return self._send(403, {'error': f'client {self.peer_name!r} is not allowed'})
            if self.path != '/accept':
                return self._send(404, {'error': 'not found'})
            try:
                raw = self.rfile.read(int(self.headers.get('Content-Length', '0')))
                body = json.loads(raw)
                root, op, evidence = body['root'], tuple(body['op']), body.get('evidence')
            except Exception:
                return self._send(400, {'error': 'malformed request'})
            if not op or op[0] not in WITNESSED:
                return self._send(400, {'error': 'not a witnessed operation'})
            if op[0] in EVIDENCE_OPS:
                if len(op) != 2:
                    return self._send(400, {'error': 'labels are derived from evidence, not supplied'})
                try:
                    op = derive_op(store, gate_keys, root, op, evidence)
                except UnknownRoot:
                    return self._send(404, {'error': 'unknown root'})
                except ref.InvalidInput as exc:
                    return self._send(400, {'error': f'invalid input: {exc}'})
            if chaos and self.headers.get('X-Plea-Crash-At'):
                os.environ['PLEA_CRASH_AT'] = self.headers['X-Plea-Crash-At']
            ev = evidence if (op[0] in EVIDENCE_OPS and evidence is not None) else None
            try:
                decision, obs, seq, digest = store.apply_ex(root, op, ev, op[-1] if ev is not None else None)   # evidence with the decision (v0.6)
            except ref.InvalidInput as exc:
                return self._send(400, {'error': f'invalid input: {exc}'})
            except UnknownRoot:
                return self._send(404, {'error': 'unknown root'})
            except AuthorityError as exc:
                return self._send(403, {'error': str(exc)})
            receipt = signer.sign(root, op[1], seq, op, decision.kind, decision.code, digest, binding_for(op, decision.kind, decision.code, obs, ev))
            self._send(200, {'kind': decision.kind, 'code': decision.code, 'seq': seq, 'hash': digest,
                             'applied': list(op), 'receipt': receipt.to_json()})
    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8787); ap.add_argument('--dsn', required=True)
    ap.add_argument('--key', default=os.environ.get('PLEA_WITNESS_KEY')); ap.add_argument('--chaos', action='store_true')
    ap.add_argument('--gate-key', action='append', default=[], help='a gate public key to pin (hex); repeatable')
    ap.add_argument('--bind', default='127.0.0.1'); add_server_args(ap)
    ap.add_argument('--tls-allow-read', action='append', default=[], help='a client name admitted to GET /checkpoint only (verification Amendment 10); repeatable')
    a = ap.parse_args()
    signer = Signer(a.key); tls = server_from_args(a)
    server = wrap_server(ThreadingHTTPServer((a.bind, a.port), make_handler(Store(a.dsn), signer, tuple(a.gate_key), a.chaos, tuple(a.tls_allow), tuple(a.tls_allow_read))), tls)
    print(json.dumps({'listening': a.port, 'public_key': signer.public_hex, 'gate_keys': a.gate_key, 'chaos': a.chaos,
                      'tls': tls is not None, 'tls_allow': a.tls_allow, 'tls_allow_read': a.tls_allow_read}), flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
