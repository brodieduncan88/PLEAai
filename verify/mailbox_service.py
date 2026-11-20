#!/usr/bin/env python3
"""A mailbox for the responsible engineer: it takes notices from a courier and signs a receipt for each (Amendment 11).

    mailbox_service.py keygen KEYFILE                                  write a new mailbox key; print its public half
    mailbox_service.py serve --port P --dir DIR --key-file KEYFILE --name NAME --courier-key HEX [--courier-key HEX ...]
                     --tls-cert CERT --tls-key KEY --tls-ca CA [--tls-allow NAME ...]
    mailbox_service.py list DIR                                        the notices held, oldest first

POST /deliver  a notice, as a courier signed it (verify/courier.py), at most 64 KiB of JSON
               -> 200 a receipt signed with the mailbox's key: {"statement": "DELIVERED", "notice": the notice's digest,
                  "root", "aid", "outcome", "mailbox": NAME, "time", "signer", "signature"}
               400 not a notice   403 the client is not admitted, or the notice is not signed by a courier key given
GET  /pubkey   {"public_key": HEX, "name": NAME}

The mailbox is meant to be the engineer's, not the verification service's: to run under an account and on a machine the
engineer controls, with a key the engineer made, and its own folder.  In the demonstration it is none of these: it runs
under the same account as the service, on the same machine, and its key is made by the deployment code (deploy.py).  It
never reads the service.  It keeps each notice it takes in DIR/notices/, as DIR/notices/DIGEST.json (the notice and the
receipt) and a readable DIR/notices/DIGEST.txt, written whole and synced before the receipt is sent.  A notice delivered
again is answered with the receipt first given, and is not kept twice.  It takes notices of both forms: Amendment 11's,
and form 2 (Amendment 16), whose words show everything the service chose as data, in quotation marks.

What a receipt shows.  That this mailbox process, holding this key, had stored this exact notice, signed by a courier key it
was started with, at the time it states by its own clock.  It is not a person's acknowledgement: it does not show that the
engineer, or anyone, read the notice.  (The engineer's signed disposition of a run, verify_ctl.py acknowledge, is a separate
thing, signed with the engineer's own key.)  The mailbox is as independent of the service as the account and machine it
runs on, and the key it holds: in the demonstration, the same as everything else.

It speaks only HTTPS with a client certificate issued by --tls-ca; --tls-allow limits which client names it admits.  Each
connection is handled in its own thread, handshake included, and let go after 15 seconds of silence.  A notice's signature
must be written in lower-case hexadecimal, so one notice cannot be delivered twice under two spellings.  It
needs the Python standard library and `cryptography` (through check_record.py), and nothing from the gateway.
"""
import argparse
import json
import os
import pathlib
import ssl
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_record as C                                                  # noqa: E402

from cryptography.hazmat.primitives import serialization                  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey   # noqa: E402

MAX_NOTICE = 65536


class MailboxKey:
    def __init__(self, private_hex: str | None = None):
        self._k = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_hex)) if private_hex else Ed25519PrivateKey.generate()

    @property
    def private_hex(self) -> str:
        return self._k.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()).hex()

    @property
    def public_hex(self) -> str:
        return self._k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()

    def sign(self, message: bytes) -> str:
        return self._k.sign(message).hex()


def now() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def _write_whole(path: pathlib.Path, data: str) -> None:
    """Write a file so that it is either absent or whole, and synced, before this returns."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.tmp-')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        pathlib.Path(tmp).unlink(missing_ok=True); raise
    dfd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def plain(text: str) -> str:
    """A notice's words as a person reads them: its lines as they are, and every other character outside printable ASCII
    (control and format characters among them) written as \\uXXXX or \\UXXXXXXXX.  The words of a notice of form 2
    (Amendment 16) are printable ASCII on their lines already, so they are kept exactly."""
    return ''.join(ch if ch == '\n' or 0x20 <= ord(ch) <= 0x7e else ('\\u%04x' % ord(ch) if ord(ch) <= 0xffff else '\\U%08x' % ord(ch)) for ch in str(text))


def readable(notice: dict) -> str:
    """The readable copy kept beside a notice.  A notice of Amendment 11's form puts a run's name, and what the service
    chose, into its lines as they are, so its copy is opened with a line that says so."""
    words = plain(notice.get('text', ''))
    if C.notice_form(notice) == 1:
        words = ('(A notice of the first form, Amendment 11: its lines may hold words the service chose, a run\'s name among them, '
                 'which are not marked as the service\'s.)\n' + words)
    return words + '\n'


class Mailbox:
    def __init__(self, directory, key: MailboxKey, name: str, courier_keys):
        self.dir = pathlib.Path(directory) / 'notices'; self.dir.mkdir(parents=True, exist_ok=True)
        self.key, self.name, self.courier_keys = key, name, tuple(courier_keys)
        self.lock = threading.Lock()

    def take(self, notice) -> tuple[int, dict]:
        """(status, answer) for a notice delivered."""
        problems = C.notice_problems(notice, self.courier_keys)
        if problems:
            return (403 if problems == ['it is not signed by a courier key given'] else 400), {'error': 'refused: ' + '; '.join(problems)}
        digest = C.notice_digest(notice)
        kept = self.dir / f'{digest}.json'
        with self.lock:
            if kept.exists():
                try:
                    return 200, json.loads(kept.read_text())['receipt']
                except (OSError, ValueError, KeyError):
                    pass                                   # a damaged copy is written again below
            body = {'statement': 'DELIVERED', 'notice': digest, 'root': notice['root'], 'aid': notice['aid'], 'outcome': notice['outcome'],
                    'mailbox': self.name, 'time': now()}
            receipt = dict(body, signer=self.key.public_hex, signature=self.key.sign(C.canonical({k: body[k] for k in C.RECEIPT_FIELDS}).encode()))
            _write_whole(self.dir / f'{digest}.txt', readable(notice))
            _write_whole(kept, json.dumps({'notice': notice, 'receipt': receipt}, sort_keys=True) + '\n')
        return 200, receipt

    def held(self) -> list:
        out = []
        for p in self.dir.glob('*.json'):
            try:
                out.append(json.loads(p.read_text()))
            except (OSError, ValueError):
                continue
        return sorted(out, key=lambda x: (x.get('receipt', {}).get('time', ''), x.get('receipt', {}).get('notice', '')))


def make_handler(box: Mailbox, allow=()):
    class Handler(BaseHTTPRequestHandler):
        timeout = 15                                                  # a client that sends nothing is let go

        def log_message(self, *args):
            pass

        def setup(self):                                              # the handshake in this thread, never in the accept loop
            super().setup()
            self.tls_failed = False
            try:
                self.connection.do_handshake()
            except (ssl.SSLError, OSError):
                self.tls_failed = True

        def handle(self):
            if not self.tls_failed:
                super().handle()

        def _send(self, status: int, payload: dict):
            body = json.dumps(payload).encode()
            self.send_response(status); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

        def _admitted(self) -> bool:
            cert = self.connection.getpeercert() if isinstance(self.connection, ssl.SSLSocket) else None
            names = [v for rdn in (cert or {}).get('subject', ()) for k, v in rdn if k == 'commonName']
            return bool(names) and (not allow or names[0] in allow)

        def do_GET(self):
            if not self._admitted():
                return self._send(403, {'error': 'client not admitted'})
            if self.path == '/pubkey':
                return self._send(200, {'public_key': box.key.public_hex, 'name': box.name})
            self._send(404, {'error': 'not found'})

        def do_POST(self):
            if not self._admitted():
                return self._send(403, {'error': 'client not admitted'})
            if self.path != '/deliver':
                return self._send(404, {'error': 'not found'})
            try:
                n = int(self.headers.get('Content-Length', '0'))
                if not 0 < n <= MAX_NOTICE:
                    return self._send(400, {'error': 'a notice is 1 byte to 64 KiB of JSON'})
                notice = json.loads(self.rfile.read(n))
            except (ValueError, OSError):
                return self._send(400, {'error': 'malformed request'})
            status, answer = box.take(notice)
            self._send(status, answer)
    return Handler


def serve(a) -> None:
    key = MailboxKey(pathlib.Path(a.key_file).read_text().strip())
    box = Mailbox(a.dir, key, a.name, a.courier_key)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(a.tls_cert, a.tls_key); ctx.load_verify_locations(cafile=a.tls_ca); ctx.verify_mode = ssl.CERT_REQUIRED
    server = ThreadingHTTPServer((a.bind, a.port), make_handler(box, tuple(a.tls_allow)))
    server.socket = ctx.wrap_socket(server.socket, server_side=True, do_handshake_on_connect=False)
    print(json.dumps({'mailbox': a.name, 'port': a.port, 'public_key': key.public_hex, 'courier_keys': a.courier_key, 'tls_allow': a.tls_allow}), flush=True)
    server.serve_forever()


def main():
    ap = argparse.ArgumentParser(description='A mailbox for the responsible engineer, for notices from a courier (Amendment 11).  A receipt it signs says it holds a notice; it is not a person\'s acknowledgement.')
    ap.add_argument('action', choices=['keygen', 'serve', 'list']); ap.add_argument('path', nargs='?')
    ap.add_argument('--port', type=int); ap.add_argument('--bind', default='127.0.0.1'); ap.add_argument('--dir'); ap.add_argument('--key-file')
    ap.add_argument('--name', default='mailbox'); ap.add_argument('--courier-key', action='append', default=[])
    ap.add_argument('--tls-cert'); ap.add_argument('--tls-key'); ap.add_argument('--tls-ca'); ap.add_argument('--tls-allow', action='append', default=[])
    a = ap.parse_args()
    if a.action == 'keygen':
        if not a.path:
            ap.error('keygen KEYFILE')
        k = MailboxKey(); p = pathlib.Path(a.path)
        p.write_text(k.private_hex + '\n'); p.chmod(0o600)
        print(json.dumps({'mailbox_key': k.public_hex})); return
    if a.action == 'list':
        if not a.path:
            ap.error('list DIR')
        for item in Mailbox.held(type('B', (), {'dir': pathlib.Path(a.path) / 'notices'})()):
            n, r = item.get('notice') or {}, item.get('receipt') or {}
            print(f"{C.shown(r.get('time'), 40)}  {C.shown(n.get('outcome', ''), 20):<16} {C.shown(n.get('aid'), 80)}  {C.shown(n.get('root'), 200)}")   # Amendment 16: what a notice names is shown as data
        return
    if not (a.port and a.dir and a.key_file and a.courier_key and a.tls_cert and a.tls_key and a.tls_ca):
        ap.error('serve needs --port, --dir, --key-file, at least one --courier-key, and --tls-cert, --tls-key and --tls-ca')
    serve(a)


if __name__ == '__main__':
    main()
