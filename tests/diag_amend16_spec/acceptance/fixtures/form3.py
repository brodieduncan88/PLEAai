"""Form 3: items, identities, chains of items, challenge requests and statements, as the specification defines them
(5.1 to 5.6, 7.2, 11), and a test-side driver that acts as a courier against a mailbox under test.

FIXED BY THE TEXT (tests rely on these exactly):
  item fields (I-1): statement "ITEM", form 3, kind, root, chain_epoch, k, prev, identity, body, time, courier,
      signer, signature; the courier's signature covers every field but signer and signature; digest = H(item)
  A(0) = H(["PLEA-A16-CHAIN", root, chain_epoch]); A(k) = H(["PLEA-A16-ITEM", A(k-1), identity_k])        (I-3)
  identities of I-ID-1, I-ID-2, I-ID-3; EPOCH_OPEN commit = Hb(s_1); statement reveal/commit (I-E-7)

NOT FIXED BY THE TEXT (finding T5) - the Codec below names them; an implementation may override sut.codec():
  the encoding of chain_epoch (16 bytes: lower-case hex here), of s_j, reveal and commit (hex); H(name) when the name
  is null (H(null) here, finding T6); field names of bodies, of the challenge request and the challenge, receipts,
  LINKED acknowledgements, signed heads, statuses, error answers; the mailbox's signed message (canonical of every
  field but signer and signature, as I-1); the mailbox epoch a courier names before it has seen one (null here, T7).
"""
import json
import os

from fixtures.crypto import H, Hb, TestKey, canonical, verify_object

NOTICE_KINDS = ('FAIL', 'UNKNOWN', 'INVALID', 'UNVERIFIED', 'INTERRUPTED', 'NO_OUTCOME', 'REFUNDED', 'INDETERMINATE',
                'UNREADABLE', 'EQUIVOCATION')
ITEM_FIELDS = ('statement', 'form', 'kind', 'root', 'chain_epoch', 'k', 'prev', 'identity', 'body', 'time', 'courier',
               'signer', 'signature')


def A0(root, chain_epoch):
    return H(['PLEA-A16-CHAIN', root, chain_epoch])


def A_next(prev, identity):
    return H(['PLEA-A16-ITEM', prev, identity])


def id_notice(root, kind, name, basis):
    return H(['PLEA-A16-ID', root, kind, H(name), basis])            # I-ID-1; for the budget's notice name is None


def basis_outcome(outcome, decision, pair):
    return [outcome, decision, pair]


def basis_equivocation(findings):
    return sorted(f for f in findings if f != 'K-MISSING')


def id_alarm(root, token):
    return H(['PLEA-A16-ID', root, 'OBSERVATION_INCOMPLETE', token])   # I-ID-2


def id_epochal(root, kind, chain_epoch, body):
    return H(['PLEA-A16-ID', root, kind, chain_epoch, body])           # I-ID-3


class Codec:
    """Names of what the specification leaves unnamed (TR-CODEC).  Every accessor is lenient where it can be."""

    # requests
    def challenge_request(self, key: TestKey, root, mailbox_epoch, request_nonce):
        return key.sign_object({'statement': 'CHALLENGE_REQUEST', 'root': root, 'mailbox_epoch': mailbox_epoch,
                                'request_nonce': request_nonce})

    # answers
    def error(self, body):
        return body.get('error') if isinstance(body, dict) else None

    def epoch_in_error(self, body):
        return body.get('mailbox_epoch') if isinstance(body, dict) else None

    def ch_token(self, ch):
        return ch.get('token')

    def ch_epoch(self, ch):
        return ch.get('mailbox_epoch')

    def ch_anchor(self, ch):
        a = ch.get('anchor') or {}
        return a.get('n', 0), a.get('head')

    def ch_head(self, ch):
        """(chain_epoch, k, A) of the open chain epoch, or None."""
        h = ch.get('head')
        return None if not h else (h.get('chain_epoch'), h.get('k'), h.get('A'))

    def ch_gaps(self, ch):
        g = ch.get('gaps') or {}
        return list(g.get('ids') or []), g.get('more', 0)

    def ch_request(self, ch):
        return ch.get('request')

    def receipt_of(self, body):
        return body.get('receipt') if isinstance(body, dict) else None

    def linked_of(self, body):
        return body.get('linked') if isinstance(body, dict) else None

    def head_in_error(self, body):
        h = body.get('head') if isinstance(body, dict) else None
        return h

    def head_tuple(self, h):
        return None if not isinstance(h, dict) else (h.get('chain_epoch'), h.get('k'), h.get('A'))

    def failed_checks(self, body):
        f = body.get('failed') if isinstance(body, dict) else None
        return set(f or [])

    def room(self, body):
        return body.get('room') if isinstance(body, dict) else None

    # status
    def st_state(self, s):
        return s.get('state')

    def st_nonce(self, s):
        return s.get('nonce')

    def st_reasons(self, s):
        out = set()
        for r in s.get('reasons') or []:
            out.add(r if isinstance(r, str) else (r.get('reason') or r.get('code')))
        return out

    def st_reason_detail(self, s, reason):
        for r in s.get('reasons') or []:
            if isinstance(r, dict) and (r.get('reason') or r.get('code')) == reason:
                return r
        return None

    def st_field(self, s, name, default=None):
        return s.get(name, default)

    def st_text(self, s):
        return canonical(s)

    # bodies
    def epoch_open_body(self, reason, commit, closes=None):
        return {'reason': reason, 'closes': closes, 'commit': commit}      # v5 I-E-1: `closes`

    def statement_body(self, challenge, checkpoint, reading, n, head, prev_statement, reveal, commit, counts,
                       oldest_carried, limits):
        return {'challenge': challenge, 'checkpoint': checkpoint, 'reading': reading, 'n': n, 'head': head,
                'prev_statement': prev_statement, 'reveal': reveal, 'commit': commit, 'counts': counts,
                'oldest_carried': oldest_carried, 'limits': limits}

    def name_field(self, name):
        if name is None:
            return None
        s = str(name)
        return {'sha256': H(name), 'length': len(s), 'shown': s[:200]}

    def notice_body(self, kind, name, basis, extra=None):
        b = {'name': self.name_field(name), 'basis': basis}
        b.update(extra or {})
        return b

    def bound_entry(self, report, where, reason=None, inline=False):
        from fixtures.crypto import evidence_id, projection_bytes
        e = {'evidence_id': evidence_id(report), 'size': len(projection_bytes(report)), 'where': where}
        if reason:
            e['reason'] = reason
        if inline:
            e['report'] = json.loads(projection_bytes(report))
        return e

    def equivocation_body(self, name, findings, bound_entries, extra=None):
        b = {'name': self.name_field(name), 'basis': basis_equivocation(findings), 'findings': sorted(findings),
             'bound': bound_entries}
        b.update(extra or {})
        return b

    def bound_of(self, body):
        return body.get('bound') or []

    def alarm_body(self, token, reasons, n=None):
        return {'token': token, 'reasons': [{'reason': r, 'run': run} for r, run in reasons], 'more': 0, 'n': n}

    def alarm_reasons(self, body):
        return {(r.get('reason') if isinstance(r, dict) else r) for r in (body.get('reasons') or [])}

    def alarm_runs(self, body):
        return [r.get('run') for r in (body.get('reasons') or []) if isinstance(r, dict) and r.get('run')]

    def part_body(self, token, n, records, i=1, of=1):
        return {'token': token, 'n': n, 'records': records, 'part': [i, of]}

    def st_reading(self, body):
        return body.get('reading')

    def items_positions(self, ans):
        return ans.get('positions') or []

    def items_head(self, ans):
        return ans.get('head')


class Driver:
    """A test acting as the budget's courier against a mailbox under test (honest unless the test makes it otherwise).
    Every request goes through MailboxHandle.request; every answer is parsed with the codec."""

    def __init__(self, tc, handle, codec, root, courier_key: TestKey, witness_key: TestKey, budget=None,
                 client='courier', reader='reader', name='acc-courier'):
        self.tc, self.h, self.c, self.root, self.key, self.wkey = tc, handle, codec, root, courier_key, witness_key
        self.client, self.reader, self.name, self.budget = client, reader, name, budget
        self.epoch_seen = None                    # the mailbox epoch last seen
        self.chain_epoch, self.k, self.A = None, 0, None
        self.secret = None                        # s_j: to be revealed by the next statement
        self.next_secret = None
        self.last_statement = None                # digest of the last accepted statement in this chain epoch
        self.receipts = {}                        # k -> receipt

    # ------------------------------------------------------------------ transport
    def req(self, method, path, body=None, client=None):
        data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        status, raw = self.h.request(method, path, data, client or (self.client if method == 'POST' else self.reader))
        try:
            parsed = json.loads(raw) if raw else None
        except (ValueError, TypeError):
            parsed = raw
        return status, parsed

    def pubkey(self):
        return self.h.public_key

    def verify_mb(self, obj):
        return verify_object(obj, [self.h.public_key])

    # ------------------------------------------------------------------ challenge
    def request_challenge(self, epoch='AUTO', nonce=None, key=None, root=None):
        ep = self.epoch_seen if epoch == 'AUTO' else epoch
        r = self.c.challenge_request(key or self.key, root or self.root, ep, nonce or os.urandom(16).hex())
        status, body = self.req('POST', '/challenge', r)
        return status, body, r

    def challenge(self, key=None, root=None):
        """A challenge, following one 409 EPOCH (M-K-1).  Fails the test if the mailbox does not give one."""
        status, body, r = self.request_challenge(key=key, root=root)
        if status == 409 and self.c.error(body) == 'EPOCH':
            self.epoch_seen = self.c.epoch_in_error(body)
            status, body, r = self.request_challenge(key=key, root=root)
        self.tc.assertEqual(status, 200, f'POST /challenge: expected 200 and a challenge, got {status} {str(body)[:300]}')
        self.epoch_seen = self.c.ch_epoch(body)
        return body

    def token(self, ch):
        return self.c.ch_token(ch)

    # ------------------------------------------------------------------ status
    def status(self, nonce=None):
        q = nonce or os.urandom(12).hex()
        st, body = self.req('GET', f'/status?root={self.root}&nonce={q}')
        self.tc.assertEqual(st, 200, f'GET /status: expected 200, got {st} {str(body)[:300]}')
        self.tc.assertTrue(self.verify_mb(body), 'the status is not signed by the mailbox key')
        self.tc.assertEqual(self.c.st_nonce(body), q, 'the status does not carry the asker\'s nonce (C-S-1, SAF-8)')
        return body

    def state(self):
        s = self.status()
        return self.c.st_state(s), self.c.st_reasons(s), s

    def assert_not_covered(self, *reasons, msg=''):
        state, rs, s = self.state()
        self.tc.assertEqual(state, 'NOT COVERED', f'{msg}: expected NOT COVERED, status says {state} {sorted(rs)}')
        for r in reasons:
            self.tc.assertIn(r, rs, f'{msg}: NOT COVERED without the reason {r} (8.2); reasons {sorted(rs)}')
        return s

    def assert_covered(self, msg=''):
        state, rs, s = self.state()
        self.tc.assertEqual(state, 'COVERED', f'{msg}: expected COVERED, status says {state} {sorted(rs)}')
        return s

    # ------------------------------------------------------------------ items
    def item(self, kind, identity, body, k=None, prev=None, chain_epoch=None, key=None, root=None, time_=None):
        it = {'statement': 'ITEM', 'form': 3, 'kind': kind, 'root': root or self.root,
              'chain_epoch': chain_epoch or self.chain_epoch, 'k': self.k + 1 if k is None else k,
              'prev': self.A if prev is None else prev, 'identity': identity, 'body': body,
              'time': time_ or '2026-11-21T12:00:00Z', 'courier': self.name}
        return (key or self.key).sign_object(it)

    def resign(self, it, k=None, prev=None):
        """The same identity and body, signed for another position (I-3)."""
        base = {f: it[f] for f in ITEM_FIELDS if f not in ('signer', 'signature')}
        base['k'] = self.k + 1 if k is None else k
        base['prev'] = self.A if prev is None else prev
        return self.key.sign_object(base)

    def deliver(self, it, advance=True):
        st, body = self.req('POST', '/deliver', it)
        if st == 200 and advance and it.get('chain_epoch') == self.chain_epoch and it.get('k') == self.k + 1:
            self.k, self.A = it['k'], A_next(self.A, it['identity'])
            self.receipts[self.k] = self.c.receipt_of(body)
        return st, body

    def open_epoch(self, reason='FIRST', expect=200, closes='OPEN', ce=None):
        """EPOCH_OPEN (I-E-1, v5): closes = the budget's open chain epoch as this driver knows it, unless given."""
        ce = ce or os.urandom(16).hex()
        s1 = os.urandom(32)
        body = self.c.epoch_open_body(reason, Hb(s1), self.chain_epoch if closes == 'OPEN' else closes)
        it = self.item('EPOCH_OPEN', id_epochal(self.root, 'EPOCH_OPEN', ce, body), body, k=1, prev=A0(self.root, ce), chain_epoch=ce)
        old = (self.chain_epoch, self.k, self.A, self.secret, self.last_statement)
        self.chain_epoch, self.k, self.A = ce, 0, A0(self.root, ce)
        st, ans = self.deliver(it)
        if expect is not None:
            self.tc.assertEqual(st, expect, f'EPOCH_OPEN: expected {expect}, got {st} {str(ans)[:300]}')
        if st == 200:
            self.secret, self.last_statement = s1, None
            self.receipts = {1: self.c.receipt_of(ans)}
        else:
            self.chain_epoch, self.k, self.A, self.secret, self.last_statement = old
        return it, st, ans

    def notice(self, kind='FAIL', name=None, basis=None, extra=None):
        name = name if name is not None else 'run-' + os.urandom(4).hex()
        basis = basis if basis is not None else basis_outcome(kind, 7, H(['EFFECT', os.urandom(8).hex()]))
        body = self.c.notice_body(kind, name, basis, extra)
        return self.item(kind, id_notice(self.root, kind, name, basis), body)

    def equivocation(self, name, findings, bound_entries, extra=None):
        body = self.c.equivocation_body(name, findings, bound_entries, extra)
        return self.item('EQUIVOCATION', id_notice(self.root, 'EQUIVOCATION', name, basis_equivocation(findings)), body)

    def alarm(self, token, reasons=(('WITNESS_UNREACHABLE', None),), n=None):
        body = self.c.alarm_body(token, list(reasons), n)
        return self.item('OBSERVATION_INCOMPLETE', id_alarm(self.root, token), body)

    def part(self, token, n, records=None, pad=0):
        body = self.c.part_body(token, n, (records or []) + (['x' * pad] if pad else []))
        return self.item('OBSERVATION_PART', id_epochal(self.root, 'OBSERVATION_PART', self.chain_epoch, body), body)

    def checkpoint_for(self, ch, n=None, head=None, at=None, head_at=None, key=None, nonce='TOKEN', seq=None):
        """A witness checkpoint for this statement: nonce = the challenge's token, at = the anchor's N (O-2)."""
        b = self.budget
        an, ah = self.c.ch_anchor(ch)
        n = b.n if n is None else n
        head = b.head_at(n) if head is None else head
        at = an if at is None else at
        if head_at is None:
            head_at = b.head_at(at) if at is not None and at <= b.n else ah
        return b.checkpoint(nonce=self.token(ch) if nonce == 'TOKEN' else nonce, at=at, seq=n if seq is None else seq,
                            head=head, head_at=head_at, key=key)

    def statement(self, ch, reading='FROM_ZERO', n=None, head=None, cp=None, reveal='OWN', commit_secret=None,
                  prev_statement='OWN', counts=None, oldest_carried=None, limits=None, cfg=None):
        b = self.budget
        n = b.n if n is None else n
        head = b.head_at(n) if head is None else head
        cp = cp or self.checkpoint_for(ch, n=n, head=head)
        self.next_secret = commit_secret or os.urandom(32)
        cfg = cfg or self.tc.mb_config
        body = self.c.statement_body(ch, cp, reading, n, head,
                                     self.last_statement if prev_statement == 'OWN' else prev_statement,
                                     (self.secret.hex() if self.secret else None) if reveal == 'OWN' else reveal,
                                     Hb(self.next_secret),
                                     counts or {'runs': len(b.attempts), 'read': len(b.attempts), 'carried': 0, 'unsettled': 0},
                                     oldest_carried,
                                     limits or {'L': cfg.L, 'R': cfg.R, 'RUN_ANSWER_MAX': 8 << 20})
        return self.item('COVERAGE', id_epochal(self.root, 'COVERAGE', self.chain_epoch, body), body)

    def send_statement(self, it):
        st, body = self.deliver(it)
        if st == 200:
            self.secret, self.last_statement = self.next_secret, H(it)
        return st, body

    def cover(self, reading='FROM_ZERO', **kw):
        """Challenge, then an honest statement: the budget becomes COVERED if the mailbox works."""
        ch = self.challenge()
        it = self.statement(ch, reading=reading, **kw)
        st, body = self.send_statement(it)
        self.tc.assertEqual(st, 200, f'an honest statement was refused: {st} {str(body)[:400]}')
        return ch, it, body

    def store_evidence(self, data: bytes, root=None):
        return self.req('POST', f'/evidence?root={root or self.root}', data)

    def get_evidence(self, eid, root=None):
        status, raw = self.h.request('GET', f'/evidence?root={root or self.root}&id={eid}', None, self.reader)
        return status, raw

    def items(self, chain_epoch=None, after=0, limit=1000):
        return self.req('GET', f'/items?root={self.root}&chain_epoch={chain_epoch or self.chain_epoch}&after={after}&limit={limit}')
