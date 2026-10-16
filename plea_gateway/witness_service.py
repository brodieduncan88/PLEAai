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
import ssl
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from plea_gateway import plea_budget_ref as ref                          # noqa: E402
from plea_gateway.receipts import WITNESSED, Signer                      # noqa: E402
from plea_gateway.store import AuthorityError, Store, UnknownRoot        # noqa: E402
from plea_gateway.tls import TLSHandlerMixin, add_server_args, server_from_args, wrap_server   # noqa: E402
from plea_gateway.witness import EVIDENCE_OPS, binding_for, derive_op    # noqa: E402


def make_handler(store: Store, signer: Signer, gate_keys: tuple, chaos: bool, allow=()):
    class Handler(TLSHandlerMixin, BaseHTTPRequestHandler):
        tls_allow = tuple(allow)                                      # v0.5: client names admitted over TLS

        def log_message(self, *args):                                 # quiet
            pass

        def _send(self, status: int, payload: dict):
            body = json.dumps(payload).encode()
            self.send_response(status); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            if not self.peer_allowed():
                return self._send(403, {'error': f'client {self.peer_name!r} is not allowed'})
            if self.path == '/pubkey':
                return self._send(200, {'public_key': signer.public_hex, 'gate_keys': list(gate_keys),
                                        'tls': isinstance(self.connection, ssl.SSLSocket), 'peer': self.peer_name})
            self._send(404, {'error': 'not found'})

        def do_POST(self):
            if not self.peer_allowed():
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
    a = ap.parse_args()
    signer = Signer(a.key); tls = server_from_args(a)
    server = wrap_server(ThreadingHTTPServer((a.bind, a.port), make_handler(Store(a.dsn), signer, tuple(a.gate_key), a.chaos, tuple(a.tls_allow))), tls)
    print(json.dumps({'listening': a.port, 'public_key': signer.public_hex, 'gate_keys': a.gate_key, 'chaos': a.chaos,
                      'tls': tls is not None, 'tls_allow': a.tls_allow}), flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
