"""Section 8 (C-1's eight conditions, the reasons of 8.2, the status C-S-1 to C-S-3, C-4), section 9 (SAF-1 to SAF-11 at
the interface; N-1 to N-6 and C-3: no unsupported claim) and section 11's earlier forms.  Specification version 5."""
import json
import os
import re

from acc import AccTest, acc
from mbutil import refused, error, CLAIM_WORDS, FAIL_WORDS
from fixtures.crypto import Hb, H, canonical, TestKey
from fixtures.form3 import A_next
from s3util import val


class Covered(AccTest):
    @acc(id='S8-C1-1-NEVER-01', rules=['C-1.1', '8.2'], cap='NONE',
         catches='a mailbox that reports COVERED for a budget with no accepted statement, or answers an unknown budget otherwise than NEVER')
    def test_never(self):
        d, h, clock = self.mailbox()
        d.assert_not_covered('NEVER', msg='a budget with no statement')
        d.open_epoch(); d.assert_not_covered('NEVER', msg='an open epoch, no statement')

    @acc(id='S8-C1-2-EXPIRED-01', rules=['C-1.2', 'M-K-4', 'C-S-3', 'N-2', 'SAF-3'], cap='NONE',
         catches='a mailbox that needs a courier to move a budget to EXPIRED')
    def test_expired_no_courier(self):
        d, h, clock = self.covered_driver(L=60.0)
        d.assert_covered()
        clock.advance(59); d.assert_covered('just within L')
        clock.advance(2)
        d.assert_not_covered('EXPIRED', msg='nothing received; the mailbox\'s own clock (C-S-3)')

    @acc(id='S8-C1-4-ALARM-01', rules=['C-1.4', '8.2', 'SAF-7', 'O-W-1'], cap='NONE',
         catches='a mailbox that stays COVERED after an OBSERVATION_INCOMPLETE item, or does not give the alarm\'s reasons')
    def test_alarm_after(self):
        d, h, clock = self.covered_driver()
        self.assertEqual(d.deliver(d.alarm(d.token(d.challenge()), reasons=[('RUN_OVERSIZE', {'sha256': '1' * 64, 'length': 9})]))[0], 200)
        s = d.assert_not_covered('OBSERVATION_INCOMPLETE')
        self.assertIn('RUN_OVERSIZE', d.c.st_text(s), 'with the alarm\'s reasons (8.2)')

    @acc(id='S8-C1-5-REFUSED-01', rules=['C-1.5', '8.2', 'SAF-7'], cap='NONE',
         catches='a mailbox that stays COVERED after a statement is refused at 7.4')
    def test_refused_after(self):
        d, h, clock = self.covered_driver()
        ch = d.challenge()
        st, body = d.send_statement(d.statement(ch, reading='REFRESH', limits={'L': 1, 'R': 1, 'RUN_ANSWER_MAX': 1}))
        refused(self, st, body, d, 'ST-9')
        d.assert_not_covered('STATEMENT_REFUSED')

    @acc(id='S8-C1-7-STALE-01', rules=['C-1.7', '8.2', 'SAF-7'], cap='NONE',
         catches='a mailbox that checks R only when the statement is taken, not at the time of the status (M8)')
    def test_stale_carry(self):
        d, h, clock = self.covered_driver(L=60.0, R=20.0)
        old = d.last_statement
        clock.advance(10)
        ch = d.challenge()
        st, body = d.send_statement(d.statement(ch, reading='INCREMENTAL', oldest_carried=old,
                                                counts={'runs': 1, 'read': 0, 'carried': 1, 'unsettled': 0}))
        self.assertEqual(st, 200)
        d.assert_covered('the carried observation is 10 s old')
        clock.advance(15)                                                # 25 s > R, the new token 15 s < L
        d.assert_not_covered('STALE_CARRY', msg='the carried observation\'s token is older than R at the status')

    @acc(id='S8-C1-8-UNREADABLE-01', rules=['C-1.8', '8.2'], cap='CAP-OS',
         catches='a mailbox that reports COVERED when it cannot read its own record of the budget')
    def test_record_unreadable(self):
        d, h, clock = self.covered_driver()
        self.optional(h, 'corrupt_record')(d.root)
        d.assert_not_covered('RECORD_UNREADABLE')

    @acc(id='S8-C1-1-LAST-01', rules=['C-1.1', 'C-1.2'], cap='NONE',
         catches='a mailbox that judges by any accepted statement rather than the last (an old one still young keeps COVERED)')
    def test_last_statement(self):
        d, h, clock = self.covered_driver(L=60.0, TOKENS_MAX=8)
        ch_old = d.challenge()                                            # issued at t = 0
        clock.advance(50)
        ch_new = d.challenge()                                            # issued at t = 50
        st, _ = d.send_statement(d.statement(ch_new, reading='REFRESH')); self.assertEqual(st, 200)
        st, _ = d.send_statement(d.statement(ch_old, reading='REFRESH')); self.assertEqual(st, 200)   # 50 s old: within L; now the last
        clock.advance(15)
        d.assert_not_covered('EXPIRED', msg='the LAST statement\'s token is 65 s old, though an earlier one\'s is 15 s')

    @acc(id='S8-STATUS-01', rules=['C-S-1', 'C-S-2', 'SAF-8'], cap='NONE',
         catches='a status that does not carry the asker\'s nonce, the mailbox epoch, the anchor, the statement, k and A(k), L')
    def test_status_fields(self):
        d, h, clock = self.covered_driver()
        q = 'Q' + os.urandom(10).hex()
        s = d.status(nonce=q)
        txt = d.c.st_text(s)
        ce, k, A = d.c.ch_head(d.challenge())
        for what, v in (('the nonce', q), ('the mailbox epoch', d.epoch_seen), ('the anchor head', d.budget.head),
                        ('the statement digest', d.last_statement), ('the chain epoch', d.chain_epoch), ('A(k)', A)):
            self.assertIn(str(v), txt, f'the status carries {what} (C-S-1)')
        s2 = d.status()
        self.assertNotEqual(d.c.st_nonce(s2), q, 'each status carries its own asker\'s nonce: an old status cannot answer a new question')

    @acc(id='S8-STATUS-DOWN-01', rules=['C-S-2', 'M-T-3'], cap='CAP-OS',
         catches='a mailbox that, down or restarted, can be read as "still covered"')
    def test_down_not_covered(self):
        d, h, clock = self.covered_driver()
        old = d.status()
        h.stop()
        try:
            st, raw = h.request('GET', f'/status?root={d.root}&nonce=fresh', None, 'reader')
        except Exception:                                                # noqa: BLE001 - no answer at all
            st = None
        self.assertNotEqual(st, 200, 'a mailbox that is down gives no status: by C-S-2 that is NOT COVERED')
        h.start()
        d.epoch_seen = None
        d.assert_not_covered('MAILBOX_RESTARTED', msg='after it comes back')
        self.assertNotEqual(d.c.st_nonce(old), 'fresh')

    @acc(id='S8-C4-01', rules=['C-4', 'N-3', 'C-3'], cap='NONE',
         catches='a status that says a run failed (or passed) when it says NOT COVERED')
    def test_not_covered_says_no_failure(self):
        d, h, clock = self.covered_driver()
        d.deliver(d.notice('FAIL'))
        d.deliver(d.alarm(d.token(d.challenge())))
        clock.advance(10 ** 4)
        s = d.assert_not_covered()
        txt = canonical({k: v for k, v in s.items() if k not in ('signature', 'signer', 'nonce')})
        self.assertIsNone(FAIL_WORDS.search(txt), f'NOT COVERED never says that a run failed: {FAIL_WORDS.search(txt)}')


class NonClaims(AccTest):
    @acc(id='S9-NOCLAIM-01', rules=['N-1', 'N-2', 'N-3', 'N-6', 'C-3', 'N-5'], cap='NONE',
         catches='an implementation whose status, receipts, challenges or fixed words claim liveness, notification, permanence or correctness')
    def test_no_claims(self):
        d, h, clock = self.covered_driver()
        texts = [canonical(d.challenge()), canonical(d.status())]
        st, b = d.deliver(d.notice()); texts.append(canonical(b))
        st, b = d.store_evidence(b'{"a":1}'); texts.append(canonical(b))
        st, items = d.items(); texts.append(canonical(items))
        clock.advance(10 ** 4); texts.append(canonical(d.status()))
        for t in texts:
            m = CLAIM_WORDS.search(t)
            self.assertIsNone(m, f'an unsupported claim: {m.group(0) if m else ""!r}')


class Safety(AccTest):
    """One test per SAF-1 to SAF-11 at the interface (each with its own budget)."""

    @acc(id='S9-SAF-01', rules=['SAF-1', 'ST-2', 'ST-3', 'ST-1'], cap='CAP-OS',
         catches='a mailbox that counts a statement whose token is old, used, spent, or of another budget, key or epoch')
    def test_saf1(self):
        d, h, clock = self.mailbox(n_budgets=2, L=30.0)
        d2 = self.extra_drivers[0]
        for x in (d, d2):
            x.budget.new_run(); x.open_epoch()
        old = d.challenge(); clock.advance(31)
        cases = [('old', old)]
        used, _it, _ = d.cover(); cases.append(('used', used))
        spent = d.challenge(); d.send_statement(d.statement(spent, reading='REFRESH', limits={'L': 0, 'R': 0, 'RUN_ANSWER_MAX': 0})); cases.append(('spent', spent))
        cases.append(('other budget', d2.challenge()))
        k0 = d.k
        for what, ch in cases:
            st, body = d.send_statement(d.statement(ch, reading='REFRESH', cp=d.checkpoint_for(ch)))
            self.assertEqual(st, 422, f'SAF-1: a statement on a token that is {what} was counted')

    @acc(id='S9-SAF-02', rules=['SAF-2', 'M-D-1', 'DL-4'], cap='CAP-DB',
         catches='a mailbox that counts a statement before its items, or one whose items name evidence not held')
    def test_saf2(self):
        d, h, clock = self.mailbox()
        d.budget.new_run(); d.open_epoch()
        e = d.equivocation('r', {'K-CONFLICT'}, [{'evidence_id': '9' * 64, 'size': 1, 'where': 'HELD'}])
        st, _ = d.deliver(e, advance=False); self.assertEqual(st, 409)
        k0, A_ = d.k, d.A
        d.k, d.A = k0 + 1, A_next(A_, e['identity'])
        ch = d.challenge(); s = d.statement(ch); d.k, d.A = k0, A_
        st, _ = d.deliver(s, advance=False)
        self.assertEqual(st, 409, 'the statement committing to a refused item is not counted')
        d.assert_not_covered(msg='SAF-2')
        e2 = d.equivocation('r', {'K-CONFLICT'}, [{'evidence_id': '9' * 64, 'size': 1, 'where': 'NOT_HELD', 'reason': 'UNAVAILABLE'}])
        d.deliver(e2)
        st, body = d.send_statement(d.statement(ch))
        self.assertEqual(st, 200, 'the token of the statement refused for its position was not touched (M-D-1)')
        d.assert_not_covered('EVIDENCE_GAP', msg='the token was not spent by the order of delivery; the gap keeps it NOT COVERED')

    @acc(id='S9-SAF-03', rules=['SAF-3', 'M-T-3', 'DL-2'], cap='CAP-OS',
         catches='a mailbox where a late delivery or a fresh receipt after a restart makes an old observation fresh')
    def test_saf3(self):
        d, h, clock = self.mailbox(L=60.0)
        d.budget.new_run(); d.open_epoch()
        ch = d.challenge(); it = d.statement(ch)
        clock.advance(70)
        st, body = d.send_statement(it)                                   # a late delivery
        self.assertEqual(st, 422)
        st, body = d.deliver(it, advance=False)
        self.assertEqual(st, 422, 'sent again: the first refusal, never a fresh count')
        d.assert_not_covered(msg='SAF-3')

    @acc(id='S9-SAF-04', rules=['SAF-4', 'I-E-7', 'I-E-8'], cap='CAP-OS',
         catches='a mailbox that counts a statement from a courier restored from a copy older than its last accepted statement')
    def test_saf4(self):
        d, h, clock = self.covered_driver()
        old_secret, old_last = d.secret, d.last_statement
        d.cover('REFRESH')                                                # the real courier goes on
        d.secret, d.last_statement = old_secret, old_last                  # the copy
        ch = d.challenge()
        st, body = d.send_statement(d.statement(ch, reading='REFRESH'))
        refused(self, st, body, d, 'ST-5', msg='SAF-4')

    @acc(id='S9-SAF-05', rules=['SAF-5', 'I-E-5', 'ST-7'], cap='NONE',
         catches='a mailbox COVERED after EPOCH_OPEN by a REFRESH statement of the new epoch')
    def test_saf5(self):
        d, h, clock = self.covered_driver()
        d.open_epoch('COURIER_STATE_LOST')
        ch = d.challenge(); st, body = d.send_statement(d.statement(ch, reading='REFRESH'))
        self.assertEqual(st, 422)
        d.assert_not_covered('EPOCH_OPENED', msg='SAF-5')

    @acc(id='S9-SAF-06', rules=['SAF-6', 'I-E-6'], cap='NONE',
         catches='a mailbox that, on a new epoch, stores again or removes a notice of an earlier epoch')
    def test_saf6(self):
        d, h, clock = self.covered_driver()
        n = d.notice('UNVERIFIED', name='x', basis=['UNVERIFIED', None, None]); st, b1 = d.deliver(n)
        e1 = d.chain_epoch
        d.open_epoch('COURIER_STATE_LOST')
        st, b2 = d.deliver(d.notice('UNVERIFIED', name='x', basis=['UNVERIFIED', None, None]))
        self.assertEqual(d.c.receipt_of(b2), d.c.receipt_of(b1))
        st, ans = d.items(chain_epoch=e1)
        self.assertTrue(any(p.get('item') == n for p in d.c.items_positions(ans)), 'the earlier epoch\'s notice is kept')

    @acc(id='S9-SAF-07', rules=['SAF-7', 'C-1', 'C-1.3', 'C-1.4', 'C-1.5', 'C-1.6', 'C-1.7'], cap='NONE',
         catches='a mailbox that is COVERED while any of SAF-7\'s conditions holds (each tried on its own budget)')
    def test_saf7(self):
        for cond in ('gap', 'alarm', 'refused', 'room', 'stale'):
            d, h, clock = self.covered_driver(NOTICE_QUOTA=2500, ITEM_MAX=4096, R=20.0, L=60.0)
            if cond == 'gap':
                d.deliver(d.equivocation('r', {'K-NONCE'}, [{'evidence_id': '8' * 64, 'size': 1, 'where': 'NOT_HELD', 'reason': 'UNAVAILABLE'}]))
            elif cond == 'alarm':
                d.deliver(d.alarm(d.token(d.challenge())))
            elif cond == 'refused':
                d.send_statement(d.statement(d.challenge(), reading='REFRESH', limits={'L': 0, 'R': 0, 'RUN_ANSWER_MAX': 0}))
            elif cond == 'room':
                for _ in range(20):
                    if d.deliver(d.notice(extra={'pad': 'q' * 800}))[0] == 507:
                        break
            else:
                old = d.last_statement; clock.advance(5)
                d.send_statement(d.statement(d.challenge(), reading='INCREMENTAL', oldest_carried=old,
                                             counts={'runs': 1, 'read': 0, 'carried': 1, 'unsettled': 0}))
                clock.advance(25)
            state, rs, s = d.state()
            self.assertEqual(state, 'NOT COVERED', f'SAF-7: {cond}')

    @acc(id='S9-SAF-08', rules=['SAF-8', 'C-S-1'], cap='CAP-DB',
         catches='a mailbox whose status can be replayed: it does not sign the asker\'s nonce back')
    def test_saf8(self):
        d, h, clock = self.covered_driver()
        s1 = d.status(nonce='aaaa1111')
        clock.advance(10 ** 4)
        s2 = d.status(nonce='bbbb2222')
        self.assertEqual(d.c.st_state(s2), 'NOT COVERED')
        self.assertNotEqual(d.c.st_nonce(s1), 'bbbb2222', 'the old (COVERED) status does not answer the new question')

    @acc(id='S9-SAF-09', rules=['SAF-9', 'K-BEL-1', 'K-REC-1'], cap='CAP-KEY',
         catches='an implementation that gives a verdict to a run with a finding')
    def test_saf9(self):
        s = self.capkey_signer()
        from s3util import key_budget, key_run
        b = key_budget(self, s)
        aid, nonce, rep, v = key_run(b, s, 'PASS')
        b.release(aid, s.fence(b.root, aid))
        j = self.judge(b, aid)
        self.assertTrue(j.findings); self.assertFalse(j.believed); self.assertNotIn(j.outcome, ('PASS', 'FAIL'))

    @acc(id='S9-SAF-10', rules=['SAF-10', 'ST-6', 'ST-8'], cap='CAP-OWNER',
         catches='a mailbox that counts a statement whose checkpoint does not sign back the head of the last accepted statement')
    def test_saf10(self):
        d, h, clock = self.covered_driver()
        an, ah = d.budget.n, d.budget.head
        d.open_epoch('COURIER_STATE_LOST')
        ch = d.challenge()
        st, body = d.send_statement(d.statement(ch, cp=d.checkpoint_for(ch, head_at='d' * 64)))
        self.assertEqual(st, 422, 'SAF-10, in a new chain epoch')

    @acc(id='S9-SAF-11', rules=['SAF-11', 'E-Q-6'], cap='CAP-DB',
         catches='a mailbox where evidence found held at DL-4 is gone when the item is written (orphan removal between)')
    def test_saf11(self):
        d, h, clock = self.mailbox(T_ORPHAN=1.0)
        d.open_epoch()
        maint = self.optional(h, 'run_maintenance')
        data = canonical({'kind': 'EFFECT_REPORT', 'root': d.root, 'aid': 's', 'x': os.urandom(8).hex()}).encode()
        d.store_evidence(data); clock.advance(5)
        e = d.equivocation('r', {'K-CONFLICT'}, [{'evidence_id': Hb(data), 'size': len(data), 'where': 'HELD'}])
        st, _ = d.deliver(e)
        maint()
        if st == 200:
            self.assertEqual(d.get_evidence(Hb(data))[0], 200, 'SAF-11')
        else:
            self.assertEqual(st, 409)


class EarlierForms(AccTest):
    def _form(self, form):
        k = TestKey()
        fields = ('statement', 'root', 'aid', 'request_key', 'outcome', 'reason_code', 'detail', 'result_digest', 'seq', 'head', 'time', 'courier', 'text')
        body = {'statement': 'NOTICE', 'root': 'R', 'aid': 'a-1', 'request_key': 'verify:1', 'outcome': 'FAIL', 'reason_code': 'LIMIT_NOT_MET',
                'detail': None, 'result_digest': '0' * 64, 'seq': 3, 'head': '1' * 64, 'time': '2026-11-21T12:00:00Z', 'courier': 'c', 'text': 'words'}
        if form == 2:
            body['form'] = 2; fields = fields + ('form',)
        n = dict(body, signer=k.public_hex, signature=k.sign(canonical({f: body[f] for f in fields}).encode()))
        return n, k

    @acc(id='S11-FORMS-01', rules=['11-EARLIER-FORMS'], cap='NONE',
         catches='an implementation whose checker no longer verifies notices and receipts of forms 1 and 2, or verifies altered ones')
    def test_forms_1_2(self):
        mk = TestKey()
        for form in (1, 2):
            n, k = self._form(form)
            self.assertEqual(self.sut.notice_problems(n, [k.public_hex]), [], f'a notice of form {form} verifies as it does')
            self.assertTrue(self.sut.notice_problems(dict(n, outcome='PASS'), [k.public_hex]), f'form {form}, altered: refused')
            self.assertTrue(self.sut.notice_problems(n, [TestKey().public_hex]), f'form {form}, another courier key: refused')
            rb = {'statement': 'DELIVERED', 'notice': H(n), 'root': n['root'], 'aid': n['aid'], 'outcome': n['outcome'], 'mailbox': 'm',
                  'time': '2026-11-21T12:00:01Z'}
            r = dict(rb, signer=mk.public_hex, signature=mk.sign(canonical(rb).encode()))
            self.assertEqual(self.sut.receipt_problems(r, [mk.public_hex], n), [], f'a receipt of form {form} verifies')
            self.assertTrue(self.sut.receipt_problems(r, [mk.public_hex], dict(n, seq=4)), 'a receipt naming another notice: refused')
        n1, k1 = self._form(1)
        self.assertTrue(self.sut.notice_problems(dict(n1, form=2), [k1.public_hex]), 'adding form to a form-1 notice breaks its signature')
