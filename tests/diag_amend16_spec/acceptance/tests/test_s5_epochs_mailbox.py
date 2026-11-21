"""Section 5 at the mailbox: chain epochs (I-E-1 to I-E-8, version 5: `closes`, EPOCH_STALE, MAILBOX_STATE_LOST),
linking (I-E-6), the item chain (I-3), one courier key (I-4).  Specification version 5."""
import os

from acc import AccTest, acc
from mbutil import error, refused, head_k
from fixtures.crypto import Hb, H, canonical
from fixtures.form3 import A0, id_epochal


class Epochs(AccTest):
    @acc(id='S5-EPOCH-OPEN-01', rules=['I-E-1', 'I-E-2', 'C-1.1', '8.2', 'SAF-5'], cap='NONE',
         catches='a mailbox that is COVERED after EPOCH_OPEN before a FROM_ZERO statement of the new epoch')
    def test_epoch_opened(self):
        d, h, clock = self.covered_driver()
        d.open_epoch('COURIER_STATE_LOST')
        d.assert_not_covered('EPOCH_OPENED', msg='a new chain epoch, no FROM_ZERO statement yet')
        s = d.status()
        txt = d.c.st_text(s)
        self.assertIn('COURIER_STATE_LOST', txt, 'the status shows why each chain epoch was opened (I-E-2)')
        self.assertIn('FIRST', txt)
        d.cover('FROM_ZERO'); d.assert_covered('after the FROM_ZERO statement of the new epoch')

    @acc(id='S5-EPOCH-KNOWN-01', rules=['I-E-3', 'DL-3', 'DL-2'], cap='CAP-OS',
         catches='a mailbox where an old EPOCH_OPEN replayed closes the open chain epoch')
    def test_old_epoch_open_replayed(self):
        d, h, clock = self.mailbox()
        d.budget.new_run()
        first, st, b1 = d.open_epoch()
        st, b2 = d.deliver(first, advance=False)
        self.assertEqual((st, d.c.receipt_of(b2)), (200, d.c.receipt_of(b1)), 'the very item that opened the open epoch: its first receipt')
        d.cover()
        second, st, _ = d.open_epoch('COURIER_STATE_LOST')
        d.cover()
        st, body = d.deliver(first, advance=False)
        error(self, st, body, d, 409, 'EPOCH_KNOWN', msg='an EPOCH_OPEN of a closed epoch, replayed')
        self.assertEqual(d.c.ch_head(d.challenge())[0], d.chain_epoch, 'the open epoch is unchanged')
        d.assert_covered('the replay changed nothing')

    @acc(id='S5-EPOCH-STALE-01', rules=['I-E-1', 'I-E-2', 'I-E-3', 'DL-3', '11-INTERFACE'], cap='NONE',
         catches='(version 5, M21) a mailbox where an EPOCH_OPEN made earlier and never delivered closes an epoch opened after it')
    def test_epoch_stale(self):
        d, h, clock = self.mailbox()
        d.budget.new_run()
        d.open_epoch(); d.cover()
        e1 = d.chain_epoch
        import copy
        late_ce = os.urandom(16).hex(); s = os.urandom(32)
        body = d.c.epoch_open_body('COURIER_STATE_LOST', Hb(s), e1)
        late = d.item('EPOCH_OPEN', id_epochal(d.root, 'EPOCH_OPEN', late_ce, body), body, k=1, prev=A0(d.root, late_ce), chain_epoch=late_ce)
        d.open_epoch('COURIER_STATE_LOST', closes=e1)                      # another EPOCH_OPEN closes e1 first
        e2 = d.chain_epoch; d.cover()
        st, ans = d.deliver(late, advance=False)
        error(self, st, ans, d, 409, 'EPOCH_STALE', msg='an EPOCH_OPEN whose closes is not the open epoch')
        self.assertEqual(d.c.ch_head(d.challenge())[0], e2, 'the epoch opened after it is still open')
        d.assert_covered('a stale EPOCH_OPEN changes nothing')
        it, st, ans = d.open_epoch('COURIER_STATE_LOST', closes=None, expect=None)
        error(self, st, ans, d, 409, 'EPOCH_STALE', msg='closes = none while an epoch is open')

    @acc(id='S5-EPOCH-FIRST-01', rules=['I-E-2', 'DL-3'], cap='NONE',
         catches='a mailbox that takes an EPOCH_OPEN naming an epoch to close when the budget has none open')
    def test_first_epoch_closes_none(self):
        d, h, clock = self.mailbox()
        it, st, ans = d.open_epoch(closes=os.urandom(16).hex(), expect=None)
        error(self, st, ans, d, 409, 'EPOCH_STALE', msg='closes names an epoch the budget does not have open')
        d.open_epoch(closes=None)

    @acc(id='S5-EPOCH-KEEP-01', rules=['I-E-2', 'SAF-6'], cap='NONE',
         catches='a mailbox that drops the notices, receipts or evidence of an earlier chain epoch')
    def test_earlier_epoch_kept(self):
        d, h, clock = self.covered_driver()
        n = d.notice(); st, b = d.deliver(n)
        e1, k1 = d.chain_epoch, n['k']
        for _ in range(2):
            d.open_epoch('COURIER_STATE_LOST'); d.cover()
        st, ans = d.items(chain_epoch=e1)
        pos = [p for p in d.c.items_positions(ans) if p.get('k') == k1]
        self.assertTrue(pos and pos[0].get('item') == n and pos[0].get('receipt') == d.c.receipt_of(b),
                        'the notice and its receipt of an earlier epoch are kept')
        ce = d.c.st_field(d.status(), 'chain_epochs')
        self.assertEqual(len(ce) if isinstance(ce, list) else ce, 3, 'the status shows how many chain epochs the budget has had (I-E-2)')

    @acc(id='S5-LINK-01', rules=['I-E-6', 'SAF-6', 'DL-5', 'I-3'], cap='NONE',
         catches='a mailbox that stores a second copy of a notice of a known identity, or answers with a new receipt')
    def test_link_first_receipt(self):
        d, h, clock = self.covered_driver()
        n1 = d.notice('FAIL', name='run-L', basis=['FAIL', 4, 'p' * 64])
        st, b1 = d.deliver(n1)
        r1 = d.c.receipt_of(b1)
        d.open_epoch('COURIER_STATE_LOST')
        n2 = d.notice('FAIL', name='run-L', basis=['FAIL', 4, 'p' * 64])
        self.assertEqual(n2['identity'], n1['identity'])
        st, b2 = d.deliver(n2)
        self.assertEqual(st, 200)
        self.assertEqual(d.c.receipt_of(b2), r1, 'the FIRST receipt, unchanged (I-E-6)')
        lk = d.c.linked_of(b2)
        self.assertTrue(lk and d.verify_mb(lk), 'and a signed LINKED acknowledgement')
        self.assertIn(n2['identity'], canonical(lk)); self.assertIn(d.chain_epoch, canonical(lk))
        st, ans = d.items()
        p = [x for x in d.c.items_positions(ans) if x.get('k') == n2['k']][0]
        self.assertFalse(p.get('item'), 'no second copy of the notice is kept for the engineer')
        self.assertEqual(d.deliver(d.notice())[0], 200, 'the link took the next position and moved the head (I-3)')
        st, b3 = d.deliver(n2, advance=False)
        self.assertEqual(d.c.receipt_of(b3), r1, 'sent again: the first answer (DL-2)')

    @acc(id='S5-LINK-02', rules=['I-E-6', 'I-ID-1'], cap='NONE',
         catches='a mailbox that links within the open epoch an identity it does not hold (or links on another field than identity)')
    def test_link_only_identity(self):
        d, h, clock = self.covered_driver()
        a = d.notice('FAIL', name='run-1', basis=['FAIL', 4, None]); d.deliver(a)
        b = d.notice('FAIL', name='run-2', basis=['FAIL', 4, None])
        st, ans = d.deliver(b)
        self.assertEqual(st, 200); self.assertFalse(d.c.linked_of(ans), 'another identity is stored, not linked')

    @acc(id='S5-CONT-01', rules=['I-E-7', 'I-E-8', 'ST-5', 'SAF-4'], cap='CAP-OS',
         catches='a mailbox that counts a statement from a courier that resumes from the mailbox\'s head without the secret')
    def test_resume_from_head(self):
        d, h, clock = self.covered_driver()
        from fixtures.form3 import Driver
        intruder = Driver(self, h, d.c, d.root, d.key, d.wkey, budget=d.budget)   # holds the key, not the state
        ch = intruder.challenge()
        ce, k, A = d.c.ch_head(ch)
        intruder.chain_epoch, intruder.k, intruder.A = ce, k, A                # everything the mailbox can tell it
        intruder.last_statement = d.last_statement                          # even the last statement's digest
        st, body = intruder.send_statement(intruder.statement(ch, reading='REFRESH', reveal=os.urandom(32).hex()))
        refused(self, st, body, d, 'ST-5', msg='position and head read back from the mailbox, no secret')

    @acc(id='S5-REASON-MSL-01', rules=['I-E-1', 'I-E-2', 'I-O-4'], cap='NONE',
         catches='(version 5, M27) a mailbox that refuses or does not record the reason MAILBOX_STATE_LOST')
    def test_mailbox_state_lost_reason(self):
        d, h, clock = self.covered_driver()
        d.open_epoch('MAILBOX_STATE_LOST')
        self.assertIn('MAILBOX_STATE_LOST', d.c.st_text(d.status()), 'the status shows the reason each epoch was opened')

    @acc(id='S5-KEY-01', rules=['I-4', 'DL-1'], cap='CAP-OS',
         catches='a mailbox that takes items for a budget from a second courier key')
    def test_second_key(self):
        d, h, clock = self.mailbox(n_budgets=2)
        d2 = self.extra_drivers[0]
        d.open_epoch()
        it = d.item('FAIL', H(['x']), d.c.notice_body('FAIL', 'x', ['FAIL', 1, None]), key=d2.key)
        self.assertEqual(d.deliver(it)[0], 403, 'an item for budget 1 signed by budget 2\'s courier key')
