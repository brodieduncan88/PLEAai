"""Section 7.3 (the strict order DL-1 to DL-6, M-D-1, M-D-2) and 7.4 (statement checks ST-1 to ST-9, one by one, and what
a refused statement does and does not do).  Specification version 5 (DL-2 and 7.4 as changed for M25 and F33)."""
import base64
import json

from acc import AccTest, acc
from mbutil import refused, error, head_k, store_text
from fixtures.crypto import TestKey, H, Hb, canonical
from fixtures.form3 import A_next


class StrictOrder(AccTest):
    @acc(id='S7-DL1-01', rules=['DL-1', 'I-1', 'I-4'], cap='CAP-DB',
         catches='a mailbox that keeps an item too large, of another form or kind, or signed by another key')
    def test_dl1(self):
        d, h, clock = self.mailbox(ITEM_MAX=4096)
        d.budget.new_run(); d.open_epoch()
        big = d.notice(extra={'pad': 'x' * 5000})
        st, _ = d.deliver(big); self.assertEqual(st, 400, 'an item larger than ITEM_MAX is 400')
        f2 = d.key.sign_object(dict({k: v for k, v in d.notice().items() if k not in ('signer', 'signature')}, form=2))
        st, _ = d.deliver(f2); self.assertEqual(st, 400, 'an item that is not of form 3 is 400')
        unk = d.item('PRAISE', H(['x']), {})
        st, _ = d.deliver(unk); self.assertEqual(st, 400, 'a kind not known is 400')
        other = d.notice(); other = TestKey().sign_object({k: v for k, v in other.items() if k not in ('signer', 'signature')})
        st, _ = d.deliver(other); self.assertEqual(st, 403, 'an item not signed by the budget\'s courier key is 403 (I-4)')
        st, _ = d.deliver(d.notice()); self.assertEqual(st, 200, 'nothing was kept: the next position is still free')

    @acc(id='S7-DL2-01', rules=['DL-2', 'I-O-2'], cap='NONE',
         catches='a mailbox that answers an item it holds with a new receipt, or takes a second position for it')
    def test_dl2_same_item(self):
        d, h, clock = self.mailbox()
        d.open_epoch()
        n = d.notice()
        st1, b1 = d.deliver(n)
        st2, b2 = d.deliver(n, advance=False)
        self.assertEqual((st1, st2), (200, 200))
        self.assertEqual(d.c.receipt_of(b2), d.c.receipt_of(b1), 'the same item is answered with its first receipt')
        st3, _ = d.deliver(d.notice()); self.assertEqual(st3, 200, 'and it took one position, not two')

    @acc(id='S7-DL2-02', rules=['DL-2', '7.4'], cap='NONE',
         catches='a mailbox that judges a refused statement again (spending another token, or accepting it later)')
    def test_dl2_refused_statement(self):
        d, h, clock = self.mailbox()
        d.budget.new_run(); d.open_epoch()
        ch = d.challenge()
        bad = d.statement(ch, limits={'L': 1, 'R': 1, 'RUN_ANSWER_MAX': 1})
        st1, b1 = d.deliver(bad)
        refused(self, st1, b1, d, 'ST-9')
        st2, b2 = d.deliver(bad)
        self.assertEqual((st2, d.c.failed_checks(b2)), (422, d.c.failed_checks(b1)), 'answered with the first 422 (DL-2)')
        d.cover()
        d.assert_covered('a good statement after the refused one sent twice')

    @acc(id='S7-DL2-03', rules=['DL-2', 'DL-3'], cap='NONE',
         catches='(version 5, M25) a mailbox that caches every refusal: an item refused for its position is refused for ever')
    def test_dl2_only_74(self):
        d, h, clock = self.mailbox()
        d.open_epoch()
        n1 = d.notice()
        n2 = d.item('FAIL', H(['n2']), d.c.notice_body('FAIL', 'n2', ['FAIL', 9, None]), k=d.k + 2, prev=A_next(d.A, n1['identity']))
        st, body = d.deliver(n2, advance=False)
        error(self, st, body, d, 409, 'CHAIN_POSITION', msg='an item beyond the next position')
        self.assertEqual(d.c.head_tuple(d.c.head_in_error(body))[1], d.k, '409 CHAIN_POSITION carries the mailbox\'s signed head')
        self.assertTrue(d.verify_mb(d.c.head_in_error(body)), 'the head is signed by the mailbox')
        self.assertEqual(d.deliver(n1)[0], 200)
        self.assertEqual(d.deliver(n2)[0], 200, 'the same bytes, now at the next position, are taken: DL-2 answers again only items held or statements refused at 7.4')

    @acc(id='S7-DL3-01', rules=['DL-3', 'M-D-1', 'M-D-2', 'SAF-2', 'I-S-1'], cap='NONE',
         catches='a mailbox that spends or uses a token when a statement arrives before an item it commits to')
    def test_statement_before_items(self):
        d, h, clock = self.mailbox()
        d.budget.new_run(); d.open_epoch()
        n = d.notice()
        ch = d.challenge()
        k0, A0_ = d.k, d.A
        d.k, d.A = k0 + 1, A_next(A0_, n['identity'])                 # build the statement as if the notice were held
        s = d.statement(ch); d.k, d.A = k0, A0_
        st, body = d.deliver(s, advance=False)
        error(self, st, body, d, 409, 'CHAIN_POSITION', msg='a statement before its items')
        self.assertEqual(d.c.head_tuple(d.c.head_in_error(body))[1], k0, 'with the mailbox\'s head')
        self.assertEqual(d.deliver(n)[0], 200)
        st, body = d.send_statement(s)
        self.assertEqual(st, 200, 'the token stayed ISSUED: the same statement is taken once its items are (M-D-1, "no token is touched")')
        d.assert_covered()

    @acc(id='S7-DL3-02', rules=['DL-3', 'I-E-1'], cap='NONE',
         catches='a mailbox that opens a chain epoch from an EPOCH_OPEN with k other than 1 or prev other than A(0)')
    def test_epoch_open_position(self):
        d, h, clock = self.mailbox()
        it, st, body = d.open_epoch(expect=None)
        self.assertEqual(st, 200)
        import os
        from fixtures.form3 import id_epochal, A0
        ce = os.urandom(16).hex(); bdy = d.c.epoch_open_body('COURIER_STATE_LOST', Hb(os.urandom(32)), d.chain_epoch)
        for k, prev in ((2, A0(d.root, ce)), (1, A0(d.root, d.chain_epoch))):
            bad = d.item('EPOCH_OPEN', id_epochal(d.root, 'EPOCH_OPEN', ce, bdy), bdy, k=k, prev=prev, chain_epoch=ce)
            st, body = d.deliver(bad, advance=False)
            self.assertIn(st, (400, 409), f'k={k}: refused at DL-3')
        self.assertEqual(d.c.ch_head(d.challenge())[0], d.chain_epoch, 'the open chain epoch is unchanged')

    @acc(id='S7-DL4-01', rules=['DL-4', 'E-B-2', 'M-D-2', 'SAF-2'], cap='CAP-DB',
         catches='a mailbox that takes a notice saying HELD for an object it does not hold')
    def test_held_not_held(self):
        d, h, clock = self.mailbox()
        d.open_epoch()
        fake = {'evidence_id': '0' * 64, 'size': 10, 'where': 'HELD'}
        e = d.equivocation('run-x', {'K-CONFLICT'}, [fake])
        st, body = d.deliver(e)
        error(self, st, body, d, 409, 'EVIDENCE_MISSING', msg='HELD for an id not held')
        self.assertEqual(d.deliver(d.notice())[0], 200, 'nothing was kept: the position is still free')

    @acc(id='S7-DL4-02', rules=['DL-4', 'E-B-2', 'E-1'], cap='CAP-DB',
         catches='a mailbox that does not check that INLINE bytes give the id the notice states')
    def test_inline_bytes(self):
        d, h, clock = self.mailbox()
        d.open_epoch()
        rep = {'kind': 'EFFECT_REPORT', 'root': d.root, 'aid': 'r', 'nonce': 'n', 'claim': 'EFFECT', 'result_digest': '1' * 64,
               'signer': '2' * 64, 'signature': '3' * 128}
        good = d.c.bound_entry(rep, 'INLINE', inline=True)
        bad = dict(good, report=dict(good['report'], claim='NO_EFFECT'))
        st, body = d.deliver(d.equivocation('run-y', {'K-CONFLICT'}, [bad]))
        self.assertEqual(st, 409, 'INLINE bytes that do not give the stated id are refused (DL-4)')
        st, body = d.deliver(d.equivocation('run-y', {'K-CONFLICT'}, [good]))
        self.assertEqual(st, 200, f'INLINE bytes that give the id are taken: {st} {str(body)[:200]}')


class StatementChecks(AccTest):
    def setup_cov(self, **cfg):
        d, h, clock = self.mailbox(**cfg)
        d.budget.new_run(); d.open_epoch()
        return d, h, clock

    @acc(id='S7-ST1-01', rules=['ST-1', 'SAF-1'], cap='CAP-DB',
         catches='a mailbox that does not check its own signature on the challenge a statement carries')
    def test_st1_forged(self):
        d, h, clock = self.setup_cov()
        ch = d.challenge()
        forged = dict(ch, L=10 ** 9)
        st, body = d.send_statement(d.statement(ch=forged, cp=d.checkpoint_for(ch)))
        refused(self, st, body, d, 'ST-1', msg='a challenge altered after the mailbox signed it')

    @acc(id='S7-ST1-02', rules=['ST-1', '7.4', 'SAF-1'], cap='CAP-DB',
         catches='a mailbox that counts, or spends, another budget\'s token in this budget\'s statement')
    def test_st1_cross_budget(self):
        d, h, clock = self.mailbox(n_budgets=2)
        d2 = self.extra_drivers[0]
        for x in (d, d2):
            x.budget.new_run(); x.open_epoch()
        ch2 = d2.challenge()
        st, body = d.send_statement(d.statement(ch2, cp=d.checkpoint_for(ch2)))
        refused(self, st, body, d, 'ST-1', msg='budget 1\'s statement carrying budget 2\'s challenge')
        d2.send_statement(d2.statement(ch2))
        d2.assert_covered('budget 2\'s token was not spent by budget 1\'s refused statement')

    @acc(id='S7-ST1-03', rules=['ST-1', '7.4', 'SAF-1'], cap='NONE',
         catches='a mailbox that spends a token of another budget when one courier key serves both (M11)')
    def test_st1_cross_key(self):
        d, h, clock = self.mailbox(n_budgets=2, same_key=True)
        d2 = self.extra_drivers[0]
        for x in (d, d2):
            x.budget.new_run(); x.open_epoch()
        ch2 = d2.challenge()
        st, body = d.send_statement(d.statement(ch2, cp=d.checkpoint_for(ch2)))
        refused(self, st, body, d, 'ST-1')
        st2, b2 = d2.send_statement(d2.statement(ch2))
        self.assertEqual(st2, 200, 'the token of the other budget is still ISSUED')

    @acc(id='S7-ST1-04', rules=['ST-1', 'ST-2', 'M-K-5', 'SAF-1', 'SAF-3'], cap='NONE',
         catches='a mailbox that counts a challenge of an earlier mailbox epoch')
    def test_st1_cross_epoch(self):
        d, h, clock = self.setup_cov()
        ch = d.challenge()
        h.restart(); d.epoch_seen = None
        st, body = d.send_statement(d.statement(ch))
        refused(self, st, body, d, 'ST-1', msg='a challenge of the earlier mailbox epoch')

    @acc(id='S7-ST4-01', rules=['ST-4'], cap='CAP-DB',
         catches='a mailbox that does not check the checkpoint: witness key, budget, nonce = token, seq and head')
    def test_st4(self):
        d, h, clock = self.setup_cov()
        b = d.budget
        cases = {'another key': dict(key=TestKey()), 'nonce not the token': dict(nonce='other-nonce'),
                 'seq not N': dict(seq=b.n + 1), 'head not the statement\'s': dict(head='0' * 64)}
        for what, kw in cases.items():
            ch = d.challenge()
            cp = d.checkpoint_for(ch, **{k: v for k, v in kw.items() if k in ('key', 'nonce', 'seq', 'head')})
            st, body = d.send_statement(d.statement(ch, cp=cp))
            refused(self, st, body, d, 'ST-4', msg=what)
        other = self.new_budget(tag='other')
        ch = d.challenge()
        cp = other.checkpoint(nonce=d.token(ch), at=0, seq=b.n, head=b.head, head_at=other.head_at(0))
        st, body = d.send_statement(d.statement(ch, cp=cp))
        refused(self, st, body, d, 'ST-4', msg='a checkpoint for another budget')

    @acc(id='S7-ST5-01', rules=['ST-5', 'I-E-7', 'I-E-8', 'SAF-4'], cap='CAP-OS',
         catches='a mailbox that counts a statement without the secret committed (a courier resuming from the mailbox\'s head)')
    def test_st5(self):
        d, h, clock = self.setup_cov()
        d.cover()
        ch = d.challenge()
        import os
        for what, kw in (('a reveal not committed', dict(reveal=os.urandom(32).hex())), ('no reveal', dict(reveal=None)),
                         ('prev_statement wrong', dict(prev_statement='0' * 64)), ('prev_statement null after one', dict(prev_statement=None))):
            ch = d.challenge()
            st, body = d.send_statement(d.statement(ch, reading='REFRESH', **kw))
            refused(self, st, body, d, 'ST-5', msg=what)

    @acc(id='S7-ST6-01', rules=['ST-6', 'SAF-10', 'O-1'], cap='CAP-OWNER',
         catches='a mailbox that does not require the checkpoint to sign back the anchor (a forked witness)')
    def test_st6(self):
        d, h, clock = self.setup_cov()
        d.cover()
        an, ahead = d.c.ch_anchor(d.challenge())
        self.assertEqual((an, ahead), (d.budget.n, d.budget.head), 'the challenge carries the anchor of the accepted statement (O-1)')
        d.budget.new_run()
        for what, kw in (('at not the anchor\'s N', dict(at=an - 1, head_at=d.budget.head_at(an - 1))), ('head_at not the anchor\'s head', dict(head_at='f' * 64))):
            ch = d.challenge()
            st, body = d.send_statement(d.statement(ch, reading='REFRESH', cp=d.checkpoint_for(ch, **kw)))
            refused(self, st, body, d, 'ST-6', msg=what)

    @acc(id='S7-ST6-02', rules=['ST-6', 'ST-8', 'I-E-2', 'SAF-10', 'O-3'], cap='CAP-OWNER',
         catches='a mailbox that forgets the anchor at a new chain epoch (a fork or rollback of the witness passes)')
    def test_anchor_across_epochs(self):
        d, h, clock = self.setup_cov()
        d.cover()
        an, ahead = d.budget.n, d.budget.head
        d.open_epoch('COURIER_STATE_LOST')
        ch = d.challenge()
        self.assertEqual(d.c.ch_anchor(ch), (an, ahead), 'the anchor is kept across chain epochs (I-E-2)')
        st, body = d.send_statement(d.statement(ch, cp=d.checkpoint_for(ch, head_at='e' * 64)))
        refused(self, st, body, d, 'ST-6', msg='the witness forked below the anchor, in a new chain epoch')
        ch = d.challenge()
        low = an - 1
        cp = d.budget.checkpoint(nonce=d.token(ch), at=an, seq=low, head=d.budget.head_at(low), head_at=ahead)
        st, body = d.send_statement(d.statement(ch, n=low, head=d.budget.head_at(low), cp=cp))
        refused(self, st, body, d, 'ST-8', msg='N lower than the anchor\'s N (a rolled-back witness), in a new chain epoch')
        ch = d.challenge(); d.send_statement(d.statement(ch))
        d.assert_covered('a true statement still works after the refusals')

    @acc(id='S7-ST7-01', rules=['ST-7', 'I-E-5', 'SAF-5'], cap='NONE',
         catches='a mailbox that takes a first statement of a chain epoch that is not FROM_ZERO')
    def test_st7_first_not_from_zero(self):
        d, h, clock = self.setup_cov()
        for reading in ('REFRESH', 'INCREMENTAL'):
            ch = d.challenge()
            st, body = d.send_statement(d.statement(ch, reading=reading))
            refused(self, st, body, d, 'ST-7', msg=f'first statement of the chain epoch is {reading}')

    @acc(id='S7-ST7-02', rules=['ST-7', 'O-C-4'], cap='NONE',
         catches='a mailbox that takes an INCREMENTAL statement as the first of a mailbox epoch')
    def test_st7_first_in_mailbox_epoch(self):
        d, h, clock = self.setup_cov()
        ch, s1, _ = d.cover()
        h.restart(); d.epoch_seen = None
        ch = d.challenge()
        st, body = d.send_statement(d.statement(ch, reading='INCREMENTAL', oldest_carried=d.last_statement,
                                                counts={'runs': 1, 'read': 0, 'carried': 1, 'unsettled': 0}))
        refused(self, st, body, d, 'ST-7', msg='the first statement after a mailbox restart is INCREMENTAL')

    @acc(id='S7-ST7-03', rules=['ST-7', 'O-C-3', 'C-1.7'], cap='NONE',
         catches='a mailbox that does not bound a carried observation by R, or that lets FROM_ZERO/REFRESH carry')
    def test_st7_carry(self):
        d, h, clock = self.setup_cov(L=60.0, R=30.0)
        ch, s1, _ = d.cover()
        oldest = d.last_statement
        carry = {'runs': 1, 'read': 0, 'carried': 1, 'unsettled': 0}
        ch = d.challenge()
        st, body = d.send_statement(d.statement(ch, reading='REFRESH', counts=carry))
        refused(self, st, body, d, 'ST-7', msg='REFRESH with carried > 0')
        clock.advance(5)
        ch = d.challenge()
        st, body = d.send_statement(d.statement(ch, reading='INCREMENTAL', oldest_carried=oldest, counts=carry))
        self.assertEqual(st, 200, f'an INCREMENTAL statement within R is taken (positive control): {st} {str(body)[:200]}')
        clock.advance(30)
        ch = d.challenge()
        st, body = d.send_statement(d.statement(ch, reading='INCREMENTAL', oldest_carried=oldest, counts=carry))
        refused(self, st, body, d, 'ST-7', msg='oldest_carried names a statement whose token is older than R')

    @acc(id='S7-ST7-04', rules=['ST-7', 'O-C-3'], cap='NONE',
         catches='a mailbox that allows carrying with R = 0')
    def test_st7_r_zero(self):
        d, h, clock = self.setup_cov(R=0.0)
        d.cover(); oldest = d.last_statement
        clock.advance(1)
        ch = d.challenge()
        st, body = d.send_statement(d.statement(ch, reading='INCREMENTAL', oldest_carried=oldest,
                                                counts={'runs': 1, 'read': 0, 'carried': 1, 'unsettled': 0}))
        refused(self, st, body, d, 'ST-7', msg='R = 0 forbids carrying')

    @acc(id='S7-ST7-05', rules=['ST-7', 'O-C-3', 'O-C-4'], cap='NONE',
         catches='a mailbox that lets oldest_carried name a statement of an earlier chain epoch')
    def test_st7_other_chain_epoch(self):
        d, h, clock = self.setup_cov()
        d.cover(); old = d.last_statement
        d.open_epoch('COURIER_STATE_LOST'); d.cover('FROM_ZERO')
        ch = d.challenge()
        st, body = d.send_statement(d.statement(ch, reading='INCREMENTAL', oldest_carried=old,
                                                counts={'runs': 1, 'read': 0, 'carried': 1, 'unsettled': 0}))
        refused(self, st, body, d, 'ST-7', msg='oldest_carried of another chain epoch')

    @acc(id='S7-ST9-01', rules=['ST-9', '7.4', 'DL-6'], cap='NONE',
         catches='a mailbox that does not compare the limits a statement was made under with its own; or evaluates only the first failing check')
    def test_st9_and_all_evaluated(self):
        d, h, clock = self.setup_cov()
        ch = d.challenge()
        st, body = d.send_statement(d.statement(ch, reading='REFRESH', limits={'L': 999, 'R': 1, 'RUN_ANSWER_MAX': 1},
                                                cp=d.checkpoint_for(ch, key=TestKey())))
        refused(self, st, body, d, 'ST-4', 'ST-7', 'ST-9', msg='three checks fail: all are evaluated and named')

    @acc(id='S7-REFUSED-01', rules=['7.4', 'I-E-7', 'I-3', 'O-7', 'ST-5', 'ST-6'], cap='NONE',
         catches='a mailbox whose refused statement takes a position, moves the head, or replaces the commit or the anchor')
    def test_refused_uses_nothing(self):
        d, h, clock = self.setup_cov()
        d.cover()
        an1 = d.c.ch_anchor(d.challenge())
        d.budget.new_run(); d.budget.new_run()
        ch = d.challenge()
        st, body = d.send_statement(d.statement(ch, reading='REFRESH', limits={'L': 1, 'R': 1, 'RUN_ANSWER_MAX': 1}))
        refused(self, st, body, d, 'ST-9')
        k_after, ch = head_k(d)
        self.assertEqual(k_after, d.k, 'the refused statement took no position (the head is unchanged)')
        self.assertEqual(d.c.ch_anchor(ch), an1, 'the anchor is unchanged')
        self.assertEqual(d.deliver(d.notice())[0], 200, 'the next position is the one the refused statement was signed for')
        ch = d.challenge()
        st, body = d.send_statement(d.statement(ch, reading='REFRESH'))      # reveals s_j again: the commit is unchanged
        self.assertEqual(st, 200, f'the commit held is unchanged: the same secret is revealed again and accepted ({st} {str(body)[:200]})')

    @acc(id='S7-REFUSED-02', rules=['7.4', 'I-E-7', 'I-E-8'], cap='CAP-OS',
         catches='(version 5, F33) a mailbox that keeps a refused statement WITH its reveal, so a reader of the store holds the next secret')
    def test_refused_kept_without_reveal(self):
        d, h, clock = self.setup_cov()
        d.cover()
        secret = d.secret
        ch = d.challenge()
        st, body = d.send_statement(d.statement(ch, reading='REFRESH', limits={'L': 1, 'R': 1, 'RUN_ANSWER_MAX': 1}))
        refused(self, st, body, d, 'ST-9')
        forms = [secret.hex().encode(), secret.hex().upper().encode(), base64.b64encode(secret), base64.urlsafe_b64encode(secret).rstrip(b'='), secret]
        blob = store_text(self.mb_store)
        for f in forms:
            self.assertNotIn(f, blob, 'the refused statement\'s reveal is in the mailbox\'s durable store (7.4: kept without its reveal)')
        st, items = d.items()
        self.assertNotIn(secret.hex(), json.dumps(items), 'nor is it served to readers')
        self.assertNotIn(secret.hex(), canonical(d.status()))

    @acc(id='S7-MS2-01', rules=['M-S-2', 'DL-6'], cap='CAP-OS',
         catches='a mailbox that judges the observation (refuses a statement for its counts) instead of bindings, holdings, order and time')
    def test_ms2_not_checked(self):
        d, h, clock = self.setup_cov()
        ch = d.challenge()
        st, body = d.send_statement(d.statement(ch, counts={'runs': 999, 'read': 999, 'carried': 0, 'unsettled': 7}))
        self.assertEqual(st, 200, 'the mailbox does not check that the observation is true (M-S-2); I-E-9: it is the courier\'s word')
