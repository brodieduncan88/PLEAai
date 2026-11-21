"""Network fixtures for courier tests: a scripted witness and a proxy in front of the mailbox under test, both plain HTTP
on loopback, both writing to one EventLog so a test can see the order of what the courier did (O-1, O-6).

ScriptedWitness serves GET /checkpoint, /chain, /run and /pubkey (the witness's interface at e25a297, unchanged by the
specification: "The witness, the gateway and the store: no change", section 11) from fixtures.chain.Budget objects, and
misbehaves on request:
    faults[root] = {'unreachable': True}           every request for the budget is answered 503 (WITNESS_UNREACHABLE)
                   {'rollback_to': n}               the chain as if it ended at n (at beyond it: 400 'at is beyond the chain')
                   {'fork': True}                   head_at signed for a different head (FORK)
                   {'drop_seq': s}                  /chain leaves decision s out (CHAIN_BROKEN)
                   {'pad_run': {aid: nbytes}}       the run's answer padded with an unsigned field of nbytes
                   {'run_status': {aid: code}}      the run's answer is that HTTP status (RUN_UNREADABLE)
                   {'cp_nonce': True}               the checkpoint signs back another nonce (O-2)
MailboxProxy forwards every request to MailboxHandle.request and records it; `script` perturbs answers:
    proxy.script.append(fn)   fn(method, path, body) -> None (forward) | 'DROP_ANSWER' (forward, then close without
                              answering: "no answer", I-O-2) | 'DROP_NO_FORWARD' (close, not forwarded; the
                              function may have done the forwarding itself) | (status, payload) (answer without forwarding)
    Every request is logged twice: party 'mailbox_begin' when it arrives, party 'mailbox' when it is answered (I-O-2).
"""
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class EventLog:
    def __init__(self):
        self._l, self._lock, self.events = threading.Lock(), threading.Lock(), []

    def add(self, party, what, **kw):
        with self._lock:
            self.events.append(dict(i=len(self.events), party=party, what=what, **kw))

    def of(self, party=None, what=None):
        return [e for e in self.events if (party is None or e['party'] == party) and (what is None or e['what'] == what)]


class _Server:
    def __init__(self, handler_cls):
        self.srv = ThreadingHTTPServer(('127.0.0.1', 0), handler_cls)
        self.srv.daemon_threads = True
        self.t = threading.Thread(target=self.srv.serve_forever, daemon=True); self.t.start()

    @property
    def url(self):
        return f'http://127.0.0.1:{self.srv.server_address[1]}'

    def close(self):
        self.srv.shutdown(); self.srv.server_close()


class ScriptedWitness(_Server):
    def __init__(self, log: EventLog, witness_key):
        self.budgets, self.faults, self.log, self.wkey = {}, {}, log, witness_key
        w = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, status, payload):
                b = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
                self.send_response(status); self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)

            def do_GET(self):
                u = urllib.parse.urlsplit(self.path); q = {k: v[-1] for k, v in urllib.parse.parse_qs(u.query, keep_blank_values=True).items()}
                w.log.add('witness', u.path, query=q)
                if u.path == '/pubkey':
                    return self._send(200, {'public_key': w.wkey.public_hex})
                b = w.budgets.get(q.get('root')); f = w.faults.get(q.get('root'), {})
                if b is None:
                    return self._send(404, {'error': 'unknown root'})
                if f.get('unreachable'):
                    return self._send(503, {'error': 'unavailable'})
                n_end = min(b.n, f.get('rollback_to', b.n))
                if u.path == '/checkpoint':
                    at = q.get('at'); at = int(at) if at is not None else None
                    if at is not None and at > n_end:
                        return self._send(400, {'error': 'at is beyond the chain'})
                    head_at = None if at is None else b.head_at(at)
                    if f.get('fork') and at is not None:
                        head_at = '0' * 64
                    nonce = 'not-' + str(q.get('nonce')) if f.get('cp_nonce') else q.get('nonce')
                    return self._send(200, b.checkpoint(nonce=nonce, at=at, seq=n_end, head=b.head_at(n_end), head_at=head_at))
                if u.path == '/chain':
                    after, limit = int(q.get('after', 0)), int(q.get('limit', 100))
                    rows = [d for d in b.decisions[after:n_end] if d['seq'] != f.get('drop_seq')][:limit]
                    return self._send(200, {'root': b.root, 'after': after, 'rows': rows})
                if u.path == '/run':
                    aid = q.get('aid')
                    code = (f.get('run_status') or {}).get(aid)
                    if code:
                        return self._send(code, {'error': 'scripted'})
                    ans = b.run_answer(aid)
                    pad = (f.get('pad_run') or {}).get(aid)
                    if pad:
                        ans['padding'] = 'p' * pad
                    return self._send(200, ans)
                self._send(404, {'error': 'not found'})
        super().__init__(H)


class MailboxProxy(_Server):
    def __init__(self, log: EventLog, handle):
        self.log, self.h, self.script, self.answers = log, handle, [], []
        p = self

        class Hd(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _relay(self, method):
                n = int(self.headers.get('Content-Length', '0') or 0)
                body = self.rfile.read(n) if n else None
                client = self.headers.get('X-Acc-Client', '')
                try:
                    parsed = json.loads(body) if body else None
                except ValueError:
                    parsed = None
                act = None
                for fn in list(p.script):
                    act = fn(method, self.path, parsed)
                    if act is not None:
                        break
                p.log.add('mailbox_begin', method + ' ' + urllib.parse.urlsplit(self.path).path, body=parsed)
                if isinstance(act, tuple):
                    status, raw = act[0], json.dumps(act[1]).encode()
                elif act == 'DROP_NO_FORWARD':
                    status, raw = 0, b''
                else:
                    status, raw = p.h.request(method, self.path, body, client)
                p.log.add('mailbox', method + ' ' + urllib.parse.urlsplit(self.path).path, path=self.path, body=parsed,
                          status=status, answer=_try(raw), dropped=(act in ('DROP_ANSWER', 'DROP_NO_FORWARD')), client=client)
                if act in ('DROP_ANSWER', 'DROP_NO_FORWARD'):
                    self.close_connection = True
                    try:
                        self.connection.shutdown(2)
                    except OSError:
                        pass
                    return
                self.send_response(status); self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)

            def do_GET(self):
                self._relay('GET')

            def do_POST(self):
                self._relay('POST')
        super().__init__(Hd)

    def delivered(self, ok_only=False):
        """Items POSTed to /deliver, in order, with the status each got."""
        return [e for e in self.log.of('mailbox', 'POST /deliver') if (not ok_only or e['status'] == 200)]


def _try(raw):
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None
