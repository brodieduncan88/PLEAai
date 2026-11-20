"""Throwaway harness: a fake witness and an in-process mailbox for verify/courier.py.  No services, no database."""
import json, pathlib, sys, tempfile, time, urllib.parse
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'verify'))
import check_record as C
import courier
import mailbox_service as M

ROOT = 'REQ-1/1/' + 'ab' * 16
PROV = 'p' * 64


class World:
    def __init__(self):
        self.wkey, self.gkey, self.ckey, self.mkey = M.MailboxKey(), M.MailboxKey(), M.MailboxKey(), M.MailboxKey()
        self.rows, self.runs, self.special = [], {}, {}
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix='rn-'))
        self.box = M.Mailbox(self.tmp / 'mbox', self.mkey, 'mb', [self.ckey.public_hex])
        (self.tmp / 'courier.key').write_text(self.ckey.private_hex)
        self.cfg = {'name': 'courier', 'key_file': str(self.tmp / 'courier.key'), 'state_dir': str(self.tmp / 'state'), 'stall_after': 900,
                    'witness_url': 'https://w', 'ca': '', 'cert': '', 'key': '', 'witness_keys': [self.wkey.public_hex], 'gate_keys': [self.gkey.public_hex],
                    'watches': [{'root': ROOT, 'mailbox_url': 'https://m', 'mailbox_keys': [self.mkey.public_hex]}]}
        self.mailbox_up = True

    def head(self):
        return self.rows[-1]['hash'] if self.rows else PROV

    def decide(self, attempts, op=('X',)):
        row = {'seq': len(self.rows) + 1, 'op': list(op), 'kind': 'APPLIED', 'code': 'OK',
               'observation': {'attempts': sorted(attempts), 'k': 10, 'm': 0, 'live': [0, 0, 0]}, 'prev_hash': self.head()}
        row['hash'] = C.chain_hash(row['prev_hash'], row); self.rows.append(row)

    def report(self, aid, nonce, claim, result=None):
        e = {'kind': 'EFFECT_REPORT', 'root': ROOT, 'aid': aid, 'nonce': nonce, 'claim': claim,
             'result_digest': C.sha(C.canonical(result)) if result is not None else None, 'signer': self.gkey.public_hex}
        e['signature'] = self.gkey.sign(C.evidence_message(e))
        self.runs.setdefault(aid, {'evidence': [], 'result': None})['evidence'].append({'seq': len(self.rows), 'evidence': e, 'derived': claim})

    def store(self, aid, result):
        self.runs.setdefault(aid, {'evidence': [], 'result': None})['result'] = {'outcome': 'value', 'value': result}

    def https(self, method, url, cfg, body=None, timeout=15.0):
        u = urllib.parse.urlsplit(url); q = dict(urllib.parse.parse_qsl(u.query))
        if u.netloc == 'm':
            if not self.mailbox_up:
                raise courier.Unreachable('mailbox down')
            return self.box.take(json.loads(json.dumps(body)))
        if u.path == '/checkpoint':
            seq = len(self.rows); at = int(q['at']) if 'at' in q else None
            head_at = None if at is None else (PROV if at == 0 else self.rows[at - 1]['hash'])
            cp = {'statement': 'CHECKPOINT', 'root': ROOT, 'seq': seq, 'head': self.head(), 'business': 'OPEN', 'witness': 'ACTIVE',
                  'time': courier.now(), 'nonce': q.get('nonce'), 'at': at, 'head_at': head_at}
            return 200, dict(cp, signer=self.wkey.public_hex, signature=self.wkey.sign(C.canonical({k: cp[k] for k in C.CHECKPOINT_FIELDS}).encode()))
        if u.path == '/chain':
            after, limit = int(q['after']), int(q['limit'])
            return 200, {'root': ROOT, 'after': after, 'rows': json.loads(json.dumps(self.rows[after:after + limit]))}
        if u.path == '/run':
            aid = q['aid']
            if aid in self.special:
                return self.special[aid]()
            if len(aid) > 512 or any(ord(c) < 32 or ord(c) == 127 for c in aid):    # witness_service.py:131
                return 400, {'error': 'malformed request'}
            r = self.runs.get(aid, {'evidence': [], 'result': None})
            return 200, {'root': ROOT, 'aid': aid, 'evidence': json.loads(json.dumps(r['evidence'])), 'result': r['result']}
        raise AssertionError(url)

    def run(self, clock):
        courier.https = self.https
        return courier.one_pass(self.cfg, clock)

    def held(self):
        return [(x['notice']['aid'], x['notice']['outcome']) for x in self.box.held()]


def verdict(v, reason):
    return {'format': 'verification-verdict/1', 'verdict': v, 'reason_code': reason, 'criteria': [], 'detail': 'd'}
