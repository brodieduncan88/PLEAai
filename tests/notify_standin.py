"""A stand-in witness and an in-process mailbox for driving the real courier without services (Amendment 16, R30).

Adapted from the diagnostic harness of 20 November (tests/diag_notify/harness.py on diagnostic-notify-2026-11-20).  The
stand-in sits below the courier's own transport: it replaces urllib.request.urlopen (and the TLS context, which needs no
files here) for the time of a pass, so courier.https and courier._https run as they are, with their deadline, their
bounded read and their reading of JSON.  The witness's answers are made and signed as the real witness makes them (the
chain hashed with check_record.chain_hash, checkpoints signed over CHECKPOINT_FIELDS), and its reading of one run refuses a
name by the witness service's own rule (witness_service.unreadable_name).  The mailbox is the real mailbox_service.Mailbox,
called in process: it has no size limit of its own (the 64 KiB limit is its HTTP handler's).

A run can be made unreadable in several ways (World.trouble[aid]):
  'too_long'  the answer is longer than courier.MAX_ANSWER (the reader is given MAX_ANSWER + 1 bytes, and no more is read)
  'dropped'   the connection is dropped while the answer is read
  'garbled'   the answer is not JSON
  'hangs'     the answer comes a byte at a time and would take `hang` seconds (it stops when the courier closes it)
  'dies'      the connection is dropped and, from then on, the witness answers nothing at all
  'knocks'    the connection is dropped and the witness answers nothing for the next `down_for` requests, then comes back
              (a run whose reading knocks the witness over, which restarts)
Every request, mailbox delivery and end of a slow answer is put in World.events, in order.  The mailbox refuses (400) a
notice whose JSON is longer than mailbox_service.MAX_NOTICE, as its HTTP handler does.
A name the reading refuses needs no trouble: the stand-in answers 400 for it, as the witness does.
"""
import contextlib
import http.client
import io
import json
import pathlib
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE.parent / 'verify'))
import check_record as C                                   # noqa: E402
import courier                                             # noqa: E402
import mailbox_service as M                                # noqa: E402
from plea_gateway.witness_service import unreadable_name   # noqa: E402

ROOT = 'REQ-T/1/' + 'ab' * 16
PROV = 'p' * 64


class Answer:
    """What urlopen gives back: a status and a body read at most n bytes at a time, as http.client's response is."""

    def __init__(self, status, body: bytes = b'', world=None, mode=None, aid=None):
        self.status, self.body, self.world, self.mode, self.aid = status, body, world, mode, aid
        self.pos, self.closed, self.started, self.ended = 0, False, time.monotonic(), False

    def _end(self, how):
        if not self.ended and self.world is not None:
            self.ended = True; self.world.events.append(('end', self.aid, how))

    def read(self, n=-1):
        if self.world is not None:
            self.world.asked_bytes.append(n)
        if self.closed:
            self._end('closed'); raise ValueError('read of a closed answer')
        if self.mode == 'too_long':
            return b' ' * (n if n is not None and n >= 0 else courier.MAX_ANSWER * 2)
        if self.mode in ('dropped', 'dies', 'knocks'):
            raise http.client.IncompleteRead(b'{"root": ')
        if self.mode == 'garbled':
            out = b'{"root": "' + ROOT.encode() + b'", "evidence": [ not json'
            self.mode = 'done-garbled'; return out
        if self.mode == 'done-garbled':
            return b''
        if self.mode == 'hangs':                                   # a byte at a time, until `hang` seconds have gone
            if time.monotonic() - self.started < self.world.hang:
                time.sleep(0.02); return b' '
            self._end('finished'); self.mode = None
        out = self.body[self.pos:] if n is None or n < 0 else self.body[self.pos:self.pos + n]
        self.pos += len(out)
        return out

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._end('left')
        return False


class World:
    def __init__(self, stall_after: float = 900, name: str = 'courier-t', roots=(ROOT,)):
        self.wkey, self.gkey, self.ckey, self.mkey = M.MailboxKey(), M.MailboxKey(), M.MailboxKey(), M.MailboxKey()
        self.rows, self.runs, self.trouble = [], {}, {}
        self.down, self.mailbox_up, self.hang = False, True, 3.0
        self.asked, self.asked_bytes, self.events, self.refuse_next, self.down_for = [], [], [], 0, 1
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix='r30-'))
        self.box = M.Mailbox(self.tmp / 'mbox', self.mkey, 'mb', [self.ckey.public_hex])
        (self.tmp / 'courier.key').write_text(self.ckey.private_hex)
        self.cfg = {'name': name, 'key_file': str(self.tmp / 'courier.key'), 'state_dir': str(self.tmp / 'state'), 'stall_after': stall_after,
                    'witness_url': 'https://w', 'ca': '', 'cert': '', 'key': '', 'witness_keys': [self.wkey.public_hex], 'gate_keys': [self.gkey.public_hex],
                    'watches': [{'root': r, 'mailbox_url': 'https://m', 'mailbox_keys': [self.mkey.public_hex]} for r in roots]}

    # ---------------------------------------------------------------- the chain, the gate's reports, the stored results
    def head(self):
        return self.rows[-1]['hash'] if self.rows else PROV

    def decide(self, attempts, op=('X',)):
        live = [0, sum(a[2] in C.LIVE_C for a in attempts), sum(a[2] == 'NO_EFFECT' for a in attempts)]
        row = {'seq': len(self.rows) + 1, 'op': list(op), 'kind': 'APPLIED', 'code': 'OK',
               'observation': {'attempts': sorted([list(a) for a in attempts]), 'k': 100, 'm': 0, 'live': live}, 'prev_hash': self.head()}
        row['hash'] = C.chain_hash(row['prev_hash'], row); self.rows.append(row)

    def report(self, aid, nonce, claim, result=None):
        e = {'kind': 'EFFECT_REPORT', 'root': ROOT, 'aid': aid, 'nonce': nonce, 'claim': claim,
             'result_digest': C.sha(C.canonical(result)) if result is not None else None, 'signer': self.gkey.public_hex}
        e['signature'] = self.gkey.sign(C.evidence_message(e))
        self.runs.setdefault(aid, {'evidence': [], 'result': None, 'request_key': None})['evidence'].append({'seq': len(self.rows), 'evidence': e, 'derived': claim})

    def store(self, aid, result):
        self.runs.setdefault(aid, {'evidence': [], 'result': None, 'request_key': None})['result'] = {'outcome': 'value', 'value': result}

    def effect(self, attempts, aid, result, nonce=None):
        """A run that ends with an effect the gate signed, and its result stored: added to `attempts` and decided."""
        nonce = nonce or 'n-' + str(len(attempts))
        attempts.append([aid, 'verify:' + str(len(attempts)), 'EFFECT', nonce, True, True])
        self.decide(attempts, ('RECONCILE', aid))
        self.report(aid, nonce, 'EFFECT', result); self.store(aid, result)
        self.runs[aid]['request_key'] = attempts[-1][1]

    # ---------------------------------------------------------------- the witness's and the mailbox's answers
    def _witness(self, path, q):
        if path == '/checkpoint':
            if q.get('root') not in [w['root'] for w in self.cfg['watches']] or q.get('root') != ROOT:
                return 404, {'error': 'unknown root'}
            seq = len(self.rows); at = int(q['at']) if 'at' in q else None
            if at is not None and at > seq:
                return 400, {'error': 'at is beyond the chain'}
            head_at = None if at is None else (PROV if at == 0 else self.rows[at - 1]['hash'])
            cp = {'statement': 'CHECKPOINT', 'root': ROOT, 'seq': seq, 'head': self.head(), 'business': 'OPEN', 'witness': 'ACTIVE',
                  'time': courier.now(), 'nonce': q.get('nonce'), 'at': at, 'head_at': head_at}
            return 200, dict(cp, signer=self.wkey.public_hex, signature=self.wkey.sign(C.canonical({k: cp[k] for k in C.CHECKPOINT_FIELDS}).encode()))
        if path == '/chain':
            after, limit = int(q['after']), int(q['limit'])
            return 200, {'root': ROOT, 'after': after, 'rows': json.loads(json.dumps(self.rows[after:after + limit]))}
        if path == '/run':
            aid = q.get('aid')
            if unreadable_name(aid):                                      # the witness service's own rule
                return 400, {'error': 'malformed request'}
            r = self.runs.get(aid, {'evidence': [], 'result': None})
            return 200, {'root': ROOT, 'aid': aid, 'evidence': json.loads(json.dumps(r['evidence'])), 'result': r['result']}
        return 404, {'error': 'not found'}

    def urlopen(self, req, timeout=None, context=None):
        url = req.full_url; u = urllib.parse.urlsplit(url); q = dict(urllib.parse.parse_qsl(u.query, keep_blank_values=True))
        self.asked.append((u.netloc, u.path, q.get('aid')))
        if u.netloc == 'm':
            if not self.mailbox_up:
                raise urllib.error.URLError(ConnectionRefusedError(111, 'Connection refused'))
            if len(req.data) > M.MAX_NOTICE:                           # as the mailbox's HTTP handler refuses it
                status, ans = 400, {'error': 'a notice is 1 byte to 64 KiB of JSON'}
            else:
                n_ = json.loads(req.data); self.events.append(('take', n_.get('aid'), n_.get('outcome')))
                status, ans = self.box.take(n_)
        else:
            self.events.append(('ask', u.path, q.get('aid')))
            if self.down:
                raise urllib.error.URLError(ConnectionRefusedError(111, 'Connection refused'))
            if self.refuse_next > 0:
                self.refuse_next -= 1
                raise urllib.error.URLError(ConnectionRefusedError(111, 'Connection refused'))
            mode = self.trouble.get(q.get('aid')) if u.path == '/run' else None
            if mode == 'dies':
                self.down = True
            if mode == 'knocks':
                self.refuse_next = self.down_for
            if mode == 'hangs':
                status, ans = self._witness(u.path, q)
                return Answer(200, json.dumps(ans).encode(), world=self, mode='hangs', aid=q.get('aid'))
            if mode:
                return Answer(200, world=self, mode=mode, aid=q.get('aid'))
            status, ans = self._witness(u.path, q)
        body = json.dumps(ans).encode()
        if status != 200:
            raise urllib.error.HTTPError(url, status, 'refused', {}, io.BytesIO(body))
        return Answer(200, body, self)

    @contextlib.contextmanager
    def wired(self):
        """For the time of the block, the courier's transport reaches this world: urlopen and the TLS context are replaced."""
        orig_open, orig_ctx = urllib.request.urlopen, courier._context
        urllib.request.urlopen, courier._context = self.urlopen, (lambda *a: None)
        try:
            yield self
        finally:
            urllib.request.urlopen, courier._context = orig_open, orig_ctx

    def run(self, clock):
        with self.wired():
            return courier.one_pass(self.cfg, clock)

    def state(self):
        return json.loads((self.tmp / 'state' / 'state.json').read_text())['roots'].get(ROOT, {})

    def status(self):
        return courier.status(self.cfg)

    def held(self):
        return [(x['notice']['aid'], x['notice']['outcome']) for x in self.box.held()]

    def held_items(self):
        return self.box.held()

    def copy_of(self, notice) -> str:
        return (self.box.dir / f'{C.notice_digest(notice)}.txt').read_text()

    def checked(self, notice, receipt):
        """What the record's checker says of a delivery of a run of this world (check_record.delivery_problem), with the
        world's chain, reports and results standing for a record's."""
        by_aid = {aid: {'evidence': r['evidence'], 'result': (r['result'] or {}).get('value'), 'request_key': r.get('request_key')} for aid, r in self.runs.items()}
        for row in self.rows:
            for a in row['observation']['attempts']:
                by_aid.setdefault(a[0], {'evidence': [], 'result': None, 'request_key': a[1]})
                by_aid[a[0]]['request_key'] = a[1]
        return C.delivery_problem({'notice': notice, 'receipt': receipt}, ROOT, self.rows, by_aid, self.gkey.public_hex, [self.ckey.public_hex], [self.mkey.public_hex])[0]


def verdict(v, reason, criteria=(), detail='d'):
    return {'format': 'verification-verdict/1', 'verdict': v, 'reason_code': reason, 'criteria': list(criteria), 'detail': detail}


FAIL = verdict('FAIL', 'LIMIT_NOT_MET', [{'id': 'service_temperature', 'achieved': '180', 'comparison': '>=', 'limit': '200', 'units': 'C', 'met': False}])
PASS = verdict('PASS', 'MET', [{'id': 'service_temperature', 'achieved': '220', 'comparison': '>=', 'limit': '200', 'units': 'C', 'met': True}])
