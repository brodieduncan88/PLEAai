"""Sections 4 and 5 (and K-N-1 to K-N-3, E-B-1, E-B-6, E-X-1 to E-X-5) on the courier side: a reading driven by the courier
under test against the scripted witness and the mailbox under test (behind a logging, perturbing proxy).
Seam: sut.start_courier + sut.start_mailbox.  Specification version 5 (I-E-4, I-O-4, I-S-1 as changed for M20, M26, M29)."""
import json
import os
import re

from acc import CourierTest, acc
from s3util import val, honest_run, key_run, eid
from fixtures.crypto import H, Hb, canonical, rand_hex
from fixtures.form3 import A0, A_next, id_notice, basis_equivocation


def statements(tc, e, since=0):
    return tc.items(e, 'COVERAGE', since=since)


def reading_of(e, it):
    return e.d.c.st_reading(it['body'])


class Order(CourierTest):
    @acc(id='C4-O1-01', rules=['O-1', 'O-2', 'O-5'], cap='NONE',
         catches='a courier that asks the witness before it has a challenge, or not with the token as nonce and the anchor as at')
    def test_challenge_first(self):
        e = self.courier_env(); honest_run(self, e.b, 'PASS')
        e.read()
        ev = e.log.events
        first_w = next(i for i, x in enumerate(ev) if x['party'] == 'witness')
        ch_i = next(i for i, x in enumerate(ev) if x['party'] == 'mailbox' and x['what'] == 'POST /challenge' and x['status'] == 200)
        self.assertLess(ch_i, first_w, 'the challenge comes before any question to the witness (O-1)')
        tok = e.d.c.ch_token(ev[ch_i]['answer'])
        cps = [x for x in ev if x['party'] == 'witness' and x['what'] == '/checkpoint']
        self.assertTrue(cps and cps[0]['query'].get('nonce') == tok and cps[0]['query'].get('at') == '0', 'GET /checkpoint?nonce=TOKEN&at=N* (O-2)')
        e.d.assert_covered('after one honest reading')

    @acc(id='C4-O1-02', rules=['O-1'], cap='CAP-OS',
         catches='a courier that does not check the challenge\'s signature, budget and that it answers its own request')
    def test_challenge_checked(self):
        e = self.courier_env(); honest_run(self, e.b, 'PASS')
        forged = []
        def forge(method, path, body):
            if path.startswith('/challenge'):
                st, raw = e.h.request(method, path, json.dumps(body).encode(), 'courier')
                ch = json.loads(raw)
                if st == 200:
                    ch = dict(ch, token=ch['token'][::-1]); forged.append(ch['token'])
                return (st, ch)
        e.px.script.append(forge)
        e.read()
        self.assertFalse(statements(self, e), 'no statement on a challenge whose signature fails')
        toks = {x['query'].get('nonce') for x in e.log.of('witness', '/checkpoint')}
        self.assertFalse(toks & set(forged), 'the courier asked the witness with the token of a challenge it should have refused (O-1)')
        e.d.assert_not_covered()

    @acc(id='C4-O2-01', rules=['O-2', '4.6'], cap='CAP-OWNER',
         catches='a courier that does not check that the checkpoint signs back its token')
    def test_checkpoint_nonce(self):
        e = self.courier_env(); honest_run(self, e.b, 'PASS')
        e.w.faults[e.b.root] = {'cp_nonce': True}
        e.read()
        self.assertFalse(statements(self, e), 'no statement on a checkpoint that does not sign the token back')
        e.d.assert_not_covered()

    @acc(id='C4-O3-01', rules=['O-3', 'O-W-1', 'O-W-2', 'C-1.4'], cap='CAP-OWNER',
         catches='a courier that does not take "at is beyond the chain" as a ROLLBACK')
    def test_rollback(self):
        e = self.courier_env(); honest_run(self, e.b, 'PASS'); e.read(); e.d.assert_covered()
        n = e.b.n; honest_run(self, e.b, 'FAIL'); e.read()
        e.w.faults[e.b.root] = {'rollback_to': n - 2}
        mark = self.n_deliveries(e); e.read()
        self.assertFalse(statements(self, e, since=mark), 'a ROLLBACK ends the reading with no statement')
        self.assertIn('ROLLBACK', self.alarm_reasons(e, since=mark))
        e.d.assert_not_covered('OBSERVATION_INCOMPLETE')

    @acc(id='C4-O3-02', rules=['O-3', 'O-W-2'], cap='CAP-OWNER',
         catches='a courier that does not compare head_at with the anchor\'s head (FORK)')
    def test_fork(self):
        e = self.courier_env(); honest_run(self, e.b, 'PASS'); e.read()
        honest_run(self, e.b, 'FAIL'); e.read()
        e.w.faults[e.b.root] = {'fork': True}
        mark = self.n_deliveries(e); e.read()
        self.assertFalse(statements(self, e, since=mark)); self.assertIn('FORK', self.alarm_reasons(e, since=mark))

    @acc(id='C4-O4-01', rules=['O-4', 'O-W-2'], cap='CAP-OWNER',
         catches='a courier that does not recompute every hash (a decision left out passes)')
    def test_chain_broken(self):
        e = self.courier_env(); honest_run(self, e.b, 'PASS'); e.read()
        honest_run(self, e.b, 'FAIL'); e.w.faults[e.b.root] = {'drop_seq': e.b.n - 1}
        mark = self.n_deliveries(e); e.read()
        self.assertFalse(statements(self, e, since=mark)); self.assertIn('CHAIN_BROKEN', self.alarm_reasons(e, since=mark))

    @acc(id='C4-O6-01', rules=['O-6', 'I-S-1', 'E-B-1'], cap='CAP-KEY',
         catches='a courier that delivers a statement before the notices, or notices before their evidence')
    def test_delivery_order(self):
        s = self.capkey_signer()
        e = self.courier_env(budget_keys=[s.public_key])
        aid, nonce, rep, v = key_run(e.b, s, 'FAIL')
        e.b.reconcile(aid, s.effect(e.b.root, aid, nonce, 'EFFECT', val('PASS')))
        key_run(e.b, s, 'FAIL')
        e.read()
        seq = [(x['what'], (x['body'] or {}).get('kind') if isinstance(x['body'], dict) else None) for x in e.log.of('mailbox') if x['status'] == 200 and x['what'] != 'POST /challenge']
        rank = lambda w, k: 0 if w == 'POST /evidence' else 1 if k in ('EQUIVOCATION', 'FAIL', 'EPOCH_OPEN') else 2 if k == 'OBSERVATION_PART' else 3 if k == 'COVERAGE' else -1
        ranks = [rank(w, k) for w, k in seq if rank(w, k) >= 0 and not (k == 'EPOCH_OPEN')]
        self.assertEqual(ranks, sorted(ranks), f'evidence, then notices, then parts, then the statement (O-6): {seq}')
        self.assertIn(3, ranks)

    @acc(id='C4-O7-01', rules=['O-7', 'I-O-1'], cap='CAP-OS',
         catches='a courier that moves its cursor when its statement is refused')
    def test_state_only_on_acceptance(self):
        e = self.courier_env(); honest_run(self, e.b, 'PASS'); e.read()
        n1 = e.b.n
        honest_run(self, e.b, 'FAIL')
        e.px.script.append(lambda m, p, b: (422, {'error': 'STATEMENT_REFUSED', 'failed': ['ST-3']}) if isinstance(b, dict) and b.get('kind') == 'COVERAGE' else None)
        e.read()
        e.px.script.clear()
        mark = len(e.log.events); e.read()
        afters = [x['query'].get('after') for x in e.log.events[mark:] if x['party'] == 'witness' and x['what'] == '/chain']
        self.assertTrue(afters and afters[0] == str(n1), f'after a refused statement the cursor is unchanged: read from {n1}, got {afters}')


class Runs(CourierTest):
    @acc(id='C4-OR-01', rules=['O-R-1', 'O-R-2', 'O-R-3', 'O-C-1', '4.3'], cap='NONE',
         catches='a courier that does not read a named run, or that reads settled runs it may carry (no INCREMENTAL)')
    def test_incremental(self):
        e = self.courier_env(mb={'R': 3600.0, 'L': 7200.0})
        a, *_ = honest_run(self, e.b, 'PASS'); e.read()
        b_, *_ = honest_run(self, e.b, 'FAIL')
        mark = len(e.log.events); e.read()
        runs = self.witness_runs(e, mark)
        self.assertIn(b_, runs, 'a run named in (K, N] is read (O-R-1)')
        st = statements(self, e)[-1]
        if reading_of(e, st) == 'INCREMENTAL':
            self.assertNotIn(a, runs, 'an INCREMENTAL reading carries the settled run')

    @acc(id='C4-OR-02', rules=['O-R-4', 'O-L-2'], cap='CAP-DB',
         catches='a courier that reads INCREMENTAL across a budget-level decision')
    def test_budget_level_refresh(self):
        e = self.courier_env(mb={'R': 3600.0, 'L': 7200.0})
        a, *_ = honest_run(self, e.b, 'PASS'); e.read()
        e.b.budget_level(('CRASH',))
        mark = len(e.log.events); e.read()
        st = statements(self, e)[-1]
        self.assertIn(reading_of(e, st), ('REFRESH', 'FROM_ZERO'), 'a budget-level decision in (K, N]: REFRESH or FROM_ZERO')
        self.assertIn(a, self.witness_runs(e, mark), 'and every run is read')

    @acc(id='C4-OC-01', rules=['O-C-3', 'ST-7'], cap='NONE',
         catches='a courier that carries runs when R = 0')
    def test_r_zero(self):
        e = self.courier_env(mb={'R': 0.0})
        a, *_ = honest_run(self, e.b, 'PASS'); e.read()
        e.cclock.advance(1); e.mclock.advance(1)
        honest_run(self, e.b, 'FAIL')
        mark = len(e.log.events); e.read()
        self.assertIn(a, self.witness_runs(e, mark), 'R = 0: every reading reads every run')
        self.assertNotEqual(reading_of(e, statements(self, e)[-1]), 'INCREMENTAL')
        e.d.assert_covered()

    @acc(id='C4-OC-02', rules=['O-C-4', 'ST-7', 'M-K-5'], cap='NONE',
         catches='a courier that carries an observation across a mailbox restart')
    def test_nothing_carried_after_restart(self):
        e = self.courier_env(mb={'R': 3600.0, 'L': 7200.0})
        a, *_ = honest_run(self, e.b, 'PASS'); e.read(); e.read()
        e.h.restart()
        mark = len(e.log.events); e.read(); e.read()
        self.assertIn(a, self.witness_runs(e, mark), 'after a mailbox restart nothing is carried')
        e.d.epoch_seen = None; e.d.assert_covered('COVERED again in the new mailbox epoch')

    @acc(id='C4-OC-03', rules=['O-C-2', 'O-R-1'], cap='CAP-DB',
         catches='a courier that takes a final run as immutable: a late RELEASE report does not bring it back')
    def test_late_release(self):
        e = self.courier_env(mb={'R': 3600.0, 'L': 7200.0})
        a, n, rep, v = honest_run(self, e.b, 'PASS'); e.read(); e.read()
        e.b.release(a, rep)                                            # a late report sent with a RELEASE (label NONE)
        mark = len(e.log.events); e.read()
        self.assertIn(a, self.witness_runs(e, mark), 'the run named again is read (O-C-2)')

    @acc(id='C4-OS-01', rules=['O-S-1', '4.3', 'K-4'], cap='CAP-KEY',
         catches='a courier that settles (and carries) a run with a finding')
    def test_finding_never_settled(self):
        s = self.capkey_signer(); e = self.courier_env(budget_keys=[s.public_key], mb={'R': 3600.0, 'L': 7200.0})
        a, n, r, v = key_run(e.b, s, 'PASS'); e.b.release(a, s.fence(e.b.root, a))
        e.read()
        for _ in range(2):
            key_run(e.b, s, 'PASS')
            mark = len(e.log.events); e.read()
            self.assertIn(a, self.witness_runs(e, mark), 'a run with a finding is read at every reading')

    @acc(id='C4-OW-01', rules=['O-W-1', 'O-W-2', 'I-ID-2'], cap='CAP-OWNER',
         catches='a courier that makes a statement leaving an unreadable run out, or drops the other runs\' notices')
    def test_not_whole(self):
        e = self.courier_env()
        x, *_ = honest_run(self, e.b, 'PASS')
        y, *_ = honest_run(self, e.b, 'FAIL')
        e.w.faults[e.b.root] = {'run_status': {x: 500}}
        e.read()
        self.assertFalse(statements(self, e), 'no statement when a run could not be read (O-W-1)')
        al = self.items(e, 'OBSERVATION_INCOMPLETE')
        self.assertEqual(len(al), 1, 'one OBSERVATION_INCOMPLETE alarm for the reading')
        self.assertIn('RUN_UNREADABLE', e.d.c.alarm_reasons(al[0]['body']))
        self.assertIn(H(x), canonical(al[0]['body']), 'the alarm names the run (H(name))')
        self.assertTrue(self.items(e, 'FAIL'), 'the notice the reading called for from a run it did read is still delivered')
        e.d.assert_not_covered('OBSERVATION_INCOMPLETE')

    @acc(id='C4-OL-01', rules=['O-L-1', 'O-L-2', 'E-X-3'], cap='CAP-DB',
         catches='a courier that reads past RUN_ANSWER_MAX, or leaves the oversize run out of a statement')
    def test_run_oversize(self):
        e = self.courier_env(cc={'RUN_ANSWER_MAX': 64 << 10})
        x, n, rep, v = honest_run(self, e.b, 'PASS')
        e.b.reconcile(x, dict(rep, padding='p' * 102_681))              # Q2: 100 KB of unsigned fields
        y, *_ = honest_run(self, e.b, 'FAIL')
        e.read()
        self.assertFalse(statements(self, e))
        self.assertIn('RUN_OVERSIZE', self.alarm_reasons(e))
        self.assertTrue(any(H(x) in canonical(i['body']) for i in self.items(e, 'UNREADABLE')), 'an UNREADABLE notice for the run')
        self.assertTrue(self.items(e, 'FAIL'))
        e.d.assert_not_covered()

    @acc(id='C4-OL-02', rules=['O-L-2', 'K-2', 'E-X-5'], cap='CAP-DB',
         catches='a courier that fails or alarms on padded answers within its limit (CAP-DB could keep every budget NOT COVERED)')
    def test_padding_within_limit(self):
        e = self.courier_env()
        x, n, rep, v = honest_run(self, e.b, 'PASS')
        e.b.reconcile(x, dict(rep, padding='p' * 100_000))
        e.read()
        self.assertFalse(self.items(e, 'OBSERVATION_INCOMPLETE')); self.assertFalse(self.items(e, 'EQUIVOCATION'))
        e.d.assert_covered()
        self.assertEqual(e.d.get_evidence(eid(rep))[0], 404, 'added fields are not stored as evidence (E-X-5)')

    @acc(id='C4-OL-03', rules=['O-L-3', 'O-W-2'], cap='CAP-KEY',
         catches='a courier without NOTICES_PER_RUN_MAX: a service with the key changes the findings to flood the notice room')
    def test_notice_limit(self):
        s = self.capkey_signer(); e = self.courier_env(budget_keys=[s.public_key], cc={'NOTICES_PER_RUN_MAX': 1})
        a, n, r, v = key_run(e.b, s, 'PASS'); e.b.reconcile(a, s.effect(e.b.root, a, n, 'EFFECT', val('FAIL')))
        e.read()
        e.b.release(a, s.fence(e.b.root, a))                           # the set of findings changes
        mark = self.n_deliveries(e); e.read()
        self.assertIn('RUN_NOTICE_LIMIT', self.alarm_reasons(e, since=mark))
        self.assertFalse(statements(self, e, since=mark))
        self.assertEqual(len(self.items(e, 'EQUIVOCATION')), 1, 'no more than NOTICES_PER_RUN_MAX notices for the run')


class Items(CourierTest):
    @acc(id='C5-I1-01', rules=['I-1', 'I-2', 'O-P-1', 'O-L-2'], cap='CAP-DB',
         catches='a courier that puts a service-chosen name (6,146 bytes) into an item whole, or makes an item larger than ITEM_MAX')
    def test_bounded_fields(self):
        e = self.courier_env(mb={'ITEM_MAX': 65536})
        long = 'L' * 6146
        aid, nonce = e.b.new_run(aid=long, upto='CONSUMED')
        v = val('FAIL'); rep = self.gate().run(e.b.root, aid, nonce, 'EFFECT', v); e.b.reconcile(aid, rep); e.b.store_result(aid, v)
        e.read()
        for it in self.items(e, ok=False):
            self.assertLessEqual(len(canonical(it).encode()), 65536, 'every item is at most ITEM_MAX (I-2)')
            self.assertNotIn('L' * 201, canonical(it), 'at most the first 200 characters of a name are shown (I-2)')
        self.assertTrue(any(H(long) in canonical(i) for i in self.items(e, 'FAIL')), 'the name is carried as its SHA-256 and length')

    @acc(id='C5-I3-01', rules=['I-3', 'I-S-3', 'I-1', 'E-R-2'], cap='NONE',
         catches='a courier whose items do not chain: prev is not A(k-1), or k skips')
    def test_chain_of_items(self):
        e = self.courier_env()
        honest_run(self, e.b, 'FAIL'); honest_run(self, e.b, 'PASS'); e.read(); honest_run(self, e.b, 'FAIL'); e.read()
        acc_items = self.items(e)
        ce = acc_items[0]['chain_epoch']
        A, k = A0(e.b.root, ce), 0
        seen = set()
        for it in acc_items:
            if H(it) in seen:
                continue
            seen.add(H(it)); k += 1
            self.assertEqual((it['chain_epoch'], it['k'], it['prev']), (ce, k, A), 'k is the next position and prev is A(k-1) (I-3)')
            A = A_next(A, it['identity'])

    @acc(id='C5-IID-01', rules=['I-ID-1', 'I-ID-4', 'I-E-4', 'I-E-5', 'I-E-6', 'K-N-1', 'O-C-4'], cap='NONE',
         catches='a courier whose notice identity depends on the epoch, k or time; or that takes state from the mailbox after losing its own')
    def test_identity_across_epochs(self):
        e = self.courier_env()
        a, *_ = honest_run(self, e.b, 'FAIL'); e.read()
        f1 = self.items(e, 'FAIL')[0]
        e.c.lose_state(e.b.root); e.cclock.advance(100)
        mark = len(e.log.events); e.read(); e.read()
        opens = [i for i in self.items(e, 'EPOCH_OPEN') if i['chain_epoch'] != f1['chain_epoch']]
        self.assertTrue(opens and opens[0]['body'].get('reason') == 'COURIER_STATE_LOST', 'a new chain epoch, reason COURIER_STATE_LOST (I-E-4)')
        afters = [x['query'].get('after') for x in e.log.events[mark:] if x['what'] == '/chain']
        self.assertEqual(afters[0], '0', 'read from decision 0 (I-E-4)')
        f2 = [i for i in self.items(e, 'FAIL') if i['chain_epoch'] != f1['chain_epoch']]
        self.assertTrue(f2 and f2[0]['identity'] == f1['identity'], 'the same identity in the new epoch (I-ID-4)')
        ans = [x for x in e.log.of('mailbox', 'POST /deliver') if x['body'] == f2[0]][0]['answer']
        self.assertTrue(e.d.c.linked_of(ans), 'and the mailbox linked it (I-E-6)')
        self.assertEqual(reading_of(e, statements(self, e)[-1]), 'FROM_ZERO')
        e.d.assert_covered()

    @acc(id='C5-IID-02', rules=['I-ID-1', 'I-ID-4', 'I-O-8'], cap='CAP-KEY',
         catches='a courier whose EQUIVOCATION identity changes when more reports are added without a new finding')
    def test_equivocation_identity_stable(self):
        s = self.capkey_signer(); e = self.courier_env(budget_keys=[s.public_key])
        a, n, r, v = key_run(e.b, s, 'PASS'); e.b.reconcile(a, s.effect(e.b.root, a, n, 'EFFECT', val('FAIL')))
        e.read()
        q1 = self.items(e, 'EQUIVOCATION')
        self.assertEqual(len(q1), 1)
        e.b.reconcile(a, s.effect(e.b.root, a, n, 'EFFECT', val('FAIL')))  # a third pair: still only K-CONFLICT
        e.read()
        self.assertEqual(len({i['identity'] for i in self.items(e, 'EQUIVOCATION')}), 1, 'no new notice: the set of findings did not change')
        e.c.lose_state(e.b.root); e.read()
        self.assertEqual({i['identity'] for i in self.items(e, 'EQUIVOCATION')}, {q1[0]['identity']}, 'the same identity in a new epoch')

    @acc(id='C5-IID-03', rules=['I-ID-2', 'O-W-1'], cap='CAP-OWNER',
         catches='a courier that deduplicates an alarm against an earlier reading\'s, or makes two for one reading')
    def test_one_alarm_per_reading(self):
        e = self.courier_env()
        x, *_ = honest_run(self, e.b, 'PASS'); e.w.faults[e.b.root] = {'run_status': {x: 500}}
        e.read(); e.read()
        al = self.items(e, 'OBSERVATION_INCOMPLETE')
        self.assertEqual(len(al), 2, 'one alarm for each reading'); self.assertNotEqual(al[0]['identity'], al[1]['identity'])

    @acc(id='C5-IE-01', rules=['I-E-1', 'I-E-5', 'I-S-2'], cap='NONE',
         catches='a courier whose first item is not EPOCH_OPEN (FIRST, closes none, commit = Hb(s_1)) or whose first statement is not FROM_ZERO')
    def test_first_epoch(self):
        e = self.courier_env(); honest_run(self, e.b, 'PASS'); e.read()
        it = self.items(e)[0]
        self.assertEqual((it['kind'], it['k'], it['body'].get('reason'), it['body'].get('closes')), ('EPOCH_OPEN', 1, 'FIRST', None))
        self.assertRegex(it['body'].get('commit', ''), r'^[0-9a-f]{64}$'); self.assertRegex(it['chain_epoch'], r'^[0-9a-f]{32}$')
        st = statements(self, e)[0]
        self.assertEqual(reading_of(e, st), 'FROM_ZERO')
        self.assertEqual(Hb(bytes.fromhex(st['body']['reveal'])), it['body']['commit'], 'statement 1 reveals s_1 (I-E-7)')

    @acc(id='C5-IE-02', rules=['I-E-4', 'I-E-8', 'O-7'], cap='CAP-OS',
         catches='a courier restored from an old copy that goes on in the old epoch (it cannot: no secret)')
    def test_restored_from_old_copy(self):
        e = self.courier_env(); honest_run(self, e.b, 'PASS'); e.read()
        snap = self.optional(e.c, 'snapshot_state')()
        honest_run(self, e.b, 'FAIL'); e.read(); e.read()
        e.c.restore_state(snap)
        mark = self.n_deliveries(e); e.read(); e.read()
        opens = [i for i in self.items(e, 'EPOCH_OPEN', since=mark)]
        self.assertTrue(opens and opens[0]['body'].get('reason') == 'COURIER_STATE_LOST', 'a new epoch, COURIER_STATE_LOST')
        e.d.assert_covered('after the FROM_ZERO reading of the new epoch')

    @acc(id='C5-IE-03', rules=['I-E-4', 'I-O-2', 'DL-2'], cap='CAP-OS',
         catches='(version 5, M26) a courier that does anything else before re-sending an unanswered EPOCH_OPEN, or reads the old head as a loss')
    def test_unanswered_epoch_open(self):
        e = self.courier_env(); honest_run(self, e.b, 'PASS'); e.read()
        e.c.lose_state(e.b.root)
        dropped = {'n': 0}
        def drop(m, p, b):
            if isinstance(b, dict) and b.get('kind') == 'EPOCH_OPEN' and dropped['n'] == 0:
                dropped['n'] += 1; return 'DROP_ANSWER'
        e.px.script.append(drop)
        mark = self.n_deliveries(e); e.read(); e.read()
        dl = e.log.of('mailbox', 'POST /deliver')[mark:]
        i = next(j for j, x in enumerate(dl) if x.get('dropped'))
        self.assertEqual(dl[i + 1]['body'], dl[i]['body'], 'the next delivery is the same EPOCH_OPEN, sent again')
        ces = {x['body']['chain_epoch'] for x in dl if isinstance(x['body'], dict) and x['body'].get('kind') == 'EPOCH_OPEN'}
        self.assertEqual(len(ces), 1, 'no second EPOCH_OPEN: the earlier epoch\'s head is not read as a loss meanwhile')
        e.d.assert_covered()

    @acc(id='C5-IE-04', rules=['I-E-4', 'I-E-3', 'O-1'], cap='CAP-OS',
         catches='(version 5) a courier that, refused as stale, sends the same EPOCH_OPEN again or opens without a new challenge')
    def test_stale_epoch_open(self):
        e = self.courier_env(); honest_run(self, e.b, 'PASS'); e.read()
        e.c.lose_state(e.b.root)
        once = {'n': 0}
        def stale(m, p, b):
            if isinstance(b, dict) and b.get('kind') == 'EPOCH_OPEN' and once['n'] == 0:
                once['n'] += 1; return (409, {'error': 'EPOCH_STALE'})
        e.px.script.append(stale)
        mark = len(e.log.events); e.read(); e.read()
        ev = [x for x in e.log.events[mark:] if x['party'] == 'mailbox']
        i = next(j for j, x in enumerate(ev) if x['status'] == 409)
        later = ev[i + 1:]
        j = next(k for k, x in enumerate(later) if isinstance(x['body'], dict) and x['body'].get('kind') == 'EPOCH_OPEN')
        self.assertTrue(any(x['what'] == 'POST /challenge' for x in later[:j]), 'a new challenge before another EPOCH_OPEN')
        self.assertNotEqual(later[j]['body']['chain_epoch'], ev[i]['body']['chain_epoch'], 'another EPOCH_OPEN, not the same one')
        e.d.assert_covered()

    @acc(id='C5-IS-01', rules=['I-S-1', 'I-O-2', 'M-D-1'], cap='CAP-OS',
         catches='(version 5, M29) a courier that sends its statement before it holds a receipt for every item it commits to')
    def test_statement_after_receipts(self):
        e = self.courier_env(); honest_run(self, e.b, 'FAIL'); honest_run(self, e.b, 'FAIL')
        n = {'c': 0}
        def drop(m, p, b):
            if isinstance(b, dict) and b.get('kind') == 'FAIL' and n['c'] < 2:
                n['c'] += 1; return 'DROP_ANSWER'
        e.px.script.append(drop)
        e.read(); e.read()
        answered = set()
        for x in e.log.of('mailbox', 'POST /deliver'):
            it = x['body']
            if not isinstance(it, dict):
                continue
            if it.get('kind') == 'COVERAGE':
                for k in range(1, it['k']):
                    self.assertIn((it['chain_epoch'], k), answered, f'statement at k={it["k"]} sent before position {k} was acknowledged')
            if x['status'] == 200 and not x.get('dropped'):
                answered.add((it['chain_epoch'], it['k']))
        self.assertTrue(statements(self, e))

    @acc(id='C5-IO-04', rules=['I-O-4a', 'L-10', 'O-W-2', 'I-E-1'], cap='CAP-OS',
         catches='a courier that does not see the mailbox behind its own receipts, or does not send the alarm right after its EPOCH_OPEN')
    def test_mailbox_behind_receipts(self):
        e = self.courier_env(); honest_run(self, e.b, 'PASS'); e.read()
        e.h.stop(); snap = self.optional(e.h, 'snapshot')(); e.h.start()
        honest_run(self, e.b, 'FAIL'); e.read()
        e.h.stop(); e.h.restore(snap); e.h.start()
        mark = self.n_deliveries(e); e.read(); e.read()
        self.assertIn('MAILBOX_ROLLBACK', self.alarm_reasons(e, since=mark))
        opens = self.items(e, 'EPOCH_OPEN', since=mark)
        self.assertTrue(opens and opens[0]['body'].get('reason') == 'MAILBOX_STATE_LOST', '(version 5) a new epoch with reason MAILBOX_STATE_LOST')
        new = [i for i in self.items(e, since=mark) if i['chain_epoch'] == opens[0]['chain_epoch']]
        self.assertEqual((new[1]['kind'], new[1]['k']), ('OBSERVATION_INCOMPLETE', 2), '(version 6) the MAILBOX_ROLLBACK alarm is the item after its EPOCH_OPEN (I-O-4a)')
        self.assertTrue(self.items(e, 'FAIL', since=mark), 'everything delivered again')
        e.d.epoch_seen = None; e.d.assert_covered()

    @acc(id='C5-IO-04B', rules=['I-O-4a', 'SAF-10', 'L-10'], cap='CAP-OS',
         catches='(versions 5, 6) a courier that takes a mailbox which lost its record as new: it holds a receipt for a statement with N above the challenge\'s anchor')
    def test_own_anchor_record_lost(self):
        e = self.courier_env()
        e.h.stop(); empty = self.optional(e.h, 'snapshot')(); e.h.start()
        honest_run(self, e.b, 'PASS'); e.read(); honest_run(self, e.b, 'PASS'); e.read()
        e.h.stop(); e.h.restore(empty); e.h.start()                    # the mailbox's record of the budget is gone
        mark = self.n_deliveries(e); e.read(); e.read()
        self.assertIn('MAILBOX_ROLLBACK', self.alarm_reasons(e, since=mark), 'a receipt for a statement whose N is above the challenge\'s anchor (0) (I-O-4a)')
        opens = self.items(e, 'EPOCH_OPEN', since=mark)
        self.assertTrue(opens and opens[0]['body'].get('reason') == 'MAILBOX_STATE_LOST')
        e.d.epoch_seen = None; e.d.assert_covered()

    @acc(id='C5-IO-04C', rules=['I-O-4', 'SAF-10', 'O-3', 'L-10'], cap='CAP-OWNER',
         catches='(versions 5, 6) a courier that does not check the chain against its own anchor when the mailbox lost the anchor')
    def test_own_anchor_fork_below(self):
        e = self.courier_env()
        e.h.stop(); empty = self.optional(e.h, 'snapshot')(); e.h.start()
        honest_run(self, e.b, 'PASS'); e.read(); honest_run(self, e.b, 'FAIL'); e.read()
        own_n = e.b.n
        e.h.stop(); e.h.restore(empty); e.h.start()
        e.b.rewrite_below(own_n - 2)                                     # and the witness forked below the courier's own anchor
        mark = self.n_deliveries(e); e.read(); e.read()
        self.assertIn('FORK', self.alarm_reasons(e, since=mark), 'the hash at the own anchor\'s N is not its head: FORK')
        self.assertFalse(statements(self, e, since=mark), 'no statement')
        e.d.epoch_seen = None; e.d.assert_not_covered()

    @acc(id='C5-IO-05', rules=['I-O-5', 'I-O-1', 'E-X-4', 'O-W-2', 'C-1.6'], cap='CAP-DB',
         catches='a courier that drops a notice refused for room, or lets it hold back the items after it')
    def test_507_notice(self):
        e = self.courier_env(mb={'NOTICE_QUOTA': 3000, 'ITEM_MAX': 65536})
        runs = [honest_run(self, e.b, 'FAIL')[0] for _ in range(6)]
        e.read()
        refused_ = [x for x in e.log.of('mailbox', 'POST /deliver') if x['status'] == 507]
        self.assertTrue(refused_, 'precondition: the notice room was too small')
        self.assertIn('NOTICE_REFUSED', self.alarm_reasons(e), 'the alarm names NOTICE_REFUSED')
        self.assertTrue(self.items(e, 'OBSERVATION_INCOMPLETE'), 'the alarm after the refused notice was taken (not held back)')
        self.assertFalse(statements(self, e))
        ob = self.optional(e.c, 'outbox')(e.b.root)
        self.assertTrue(any(isinstance(i, dict) and i.get('identity') == refused_[0]['body']['identity'] for i in ob), 'the notice stays in the outbox')
        mark = self.n_deliveries(e); e.read()
        self.assertTrue(any(isinstance(x['body'], dict) and x['body'].get('identity') == refused_[0]['body']['identity']
                            for x in e.log.of('mailbox', 'POST /deliver')[mark:]), 'and is sent again at the next reading')
        e.d.assert_not_covered('NOTICES_REFUSED')

    @acc(id='C5-IO-06', rules=['I-O-6', 'E-B-6', 'E-B-2'], cap='CAP-KEY', open_finding='T12',
         catches='a courier that, on 409 EVIDENCE_MISSING, does not store the evidence again from its own copy')
    def test_evidence_missing(self):
        s = self.capkey_signer(); e = self.courier_env(budget_keys=[s.public_key])
        a, n, r, v = key_run(e.b, s, 'PASS'); e.b.reconcile(a, s.effect(e.b.root, a, n, 'EFFECT', val('FAIL')))
        once = {'n': 0}
        def lose(m, p, b):
            if p.startswith('/evidence') and m == 'POST' and once['n'] == 0:
                once['n'] += 1; return (503, {'error': 'scripted'})
        e.px.script.append(lose)
        e.read(); e.read()
        self.assertTrue(self.items(e, 'EQUIVOCATION'), 'the notice is eventually taken')
        e.d.assert_covered('with its evidence held or inline')

    @acc(id='C5-IO-07', rules=['I-O-7', 'E-B-3', 'E-B-6', 'O-1'], cap='CAP-KEY', open_finding='T12',
         catches='a courier that does not store again the objects of the gaps the challenge lists (needs CAP-KEY for a bound report AND CAP-OS to remove it: labelled by the stronger key capability)')
    def test_gaps_reuploaded(self):
        s = self.capkey_signer(); e = self.courier_env(budget_keys=[s.public_key], cc={'INLINE_TOTAL_MAX': 0})
        a, n, r, v = key_run(e.b, s, 'PASS'); e.b.reconcile(a, s.effect(e.b.root, a, n, 'EFFECT', val('FAIL')))
        e.read(); e.d.assert_covered()
        self.optional(e.h, 'remove_evidence')(e.b.root, eid(r))
        e.d.assert_not_covered('EVIDENCE_GAP')
        e.read()
        e.d.assert_covered('the courier stored the gap\'s object again (I-O-7)')

    @acc(id='C5-IO-08', rules=['I-O-8', 'K-N-1'], cap='NONE',
         catches='a courier that sends a notice again in the same chain epoch after it has a receipt')
    def test_once_in_epoch(self):
        e = self.courier_env(); honest_run(self, e.b, 'FAIL'); e.read(); e.read(); e.read()
        self.assertEqual(len(self.items(e, 'FAIL', ok=False)), 1)


class Waits(CourierTest):
    def _withheld(self, e):
        aid, nonce, rep, v = honest_run(self, e.b, 'FAIL', store=False)   # the gate signed FAIL; the result is withheld
        return aid

    @acc(id='C3-KN3-01', rules=['K-N-3', 'M-T-1', '3.4'], cap='CAP-DB',
         catches='a courier that counts its waiting time with CLOCK_MONOTONIC (a suspension does not count)')
    def test_wait_boottime(self):
        e = self.courier_env(cc={'wait_seconds': 600.0})
        a = self._withheld(e); e.read()
        self.assertFalse(self.items(e, 'UNVERIFIED'), 'within the waiting time, no UNVERIFIED notice')
        e.cclock.advance(300); e.read()
        self.assertFalse(self.items(e, 'UNVERIFIED'))
        e.cclock.suspend(400); e.read()
        self.assertTrue(self.items(e, 'UNVERIFIED'), 'after 700 s by BOOTTIME (400 of them suspended): the notice')

    @acc(id='C3-KN3-02', rules=['K-N-3', 'O-W-1'], cap='CAP-DB',
         catches='a courier that keeps a withheld failing run without a notice by another run being made unreadable')
    def test_wait_over_when_not_whole(self):
        e = self.courier_env(cc={'wait_seconds': 600.0})
        a = self._withheld(e)
        x, *_ = honest_run(self, e.b, 'PASS'); e.w.faults[e.b.root] = {'pad_run': {x: 9 << 20}}
        e.read()
        self.assertTrue(any(H(a) in canonical(i['body']) for i in self.items(e, 'UNVERIFIED')), 'in a reading not whole, the wait is over at once')

    @acc(id='C3-KN3-03', rules=['K-N-3'], cap='NONE',
         catches='a courier that compares a waiting-time moment across a restart of its machine')
    def test_wait_over_after_reboot(self):
        e = self.courier_env(cc={'wait_seconds': 600.0})
        a = self._withheld(e); e.read()
        e.cclock.reboot(); self.optional(e.c, 'restart')(); e.read()
        self.assertTrue(self.items(e, 'UNVERIFIED'), 'it cannot count the time: the notice is called for at once')

    @acc(id='C3-KN3-04', rules=['K-N-3', 'I-E-4'], cap='NONE',
         catches='a courier that waits in the first reading of an epoch opened for COURIER_STATE_LOST')
    def test_wait_over_after_state_lost(self):
        e = self.courier_env(cc={'wait_seconds': 600.0})
        a = self._withheld(e); e.read()
        e.c.lose_state(e.b.root); e.read()
        self.assertTrue(self.items(e, 'UNVERIFIED'))

    @acc(id='C3-KN2-01', rules=['K-N-2', 'C-3', 'N-3'], cap='CAP-KEY',
         catches='an EQUIVOCATION notice whose words say which report is true, that the run passed or failed, or that a verdict changed')
    def test_equivocation_words(self):
        s = self.capkey_signer(); e = self.courier_env(budget_keys=[s.public_key])
        a, n, r, v = key_run(e.b, s, 'PASS'); e.b.reconcile(a, s.effect(e.b.root, a, n, 'EFFECT', val('FAIL')))
        e.read()
        q = self.items(e, 'EQUIVOCATION')[0]
        words = canonical({k: v for k, v in q['body'].items() if k not in ('bound', 'name', 'basis', 'findings')})
        m = re.search(r'\b(PASS(ED)?|FAIL(ED)?|true|genuine|forged|forgery|changed|replaced|supersede[sd]?|correct)\b', words, re.I)
        self.assertIsNone(m, f'K-N-2: the notice says {m.group(0) if m else ""!r}')


class Exhaustion(CourierTest):
    def _never_leaves_out(self, e):
        for st in statements(self, e):
            c = st['body'].get('counts') or {}
            self.assertEqual(c.get('read', 0) + c.get('carried', 0), c.get('runs'), 'a statement never leaves a run out (E-X-3)')
            self.assertEqual(c.get('runs'), len(e.b.attempts))

    @acc(id='C6-EX-01', rules=['E-X-1', 'E-X-2', 'E-X-5', 'O-P-2', 'D-12'], cap='CAP-DB',
         catches='a courier whose notices or items grow with strays, added fields and names no attempt bears')
    def test_capdb_exhaustion(self):
        e = self.courier_env()
        a, n, rep, v = honest_run(self, e.b, 'FAIL')
        for i in range(30):
            e.b.unborne('g' * 6146 + str(i), {'kind': 'EFFECT_REPORT', 'pad': 'x' * 1000}, op='RECONCILE')
            e.b.reconcile(a, {'stray': i, 'pad': 'y' * 1000})
        e.read(); e.read()
        self._never_leaves_out(e)
        self.assertEqual(len(self.items(e, 'FAIL')), 1)
        self.assertFalse(self.items(e, 'EQUIVOCATION'), 'strays and unborne names call for no notice')
        for it in self.items(e, ok=False):
            self.assertLessEqual(len(canonical(it).encode()), e.d.tc.mb_config.ITEM_MAX if hasattr(e.d.tc, 'mb_config') else 65536)
        state, rs, s = e.d.state()
        if state != 'COVERED':
            self.assertTrue(self.items(e, 'OBSERVATION_INCOMPLETE'), 'NOT COVERED with an alarm, never silently (O-L-2)')

    @acc(id='C6-EX-02', rules=['E-X-3', 'E-B-1', 'E-B-4', 'E-B-5', 'E-3', 'O-W-2'], cap='CAP-KEY',
         catches='(the 200 KB report) a courier or mailbox that reaches COVERED while a finding\'s report cannot be held')
    def test_capkey_200kb(self):
        s = self.capkey_signer(); e = self.courier_env(budget_keys=[s.public_key], mb={'OBJ_MAX': 64 << 10})
        a, n, r, v = key_run(e.b, s, 'PASS')
        big = s.effect(e.b.root, a, 'n-' + 'N' * 200_000, 'UNKNOWN', None)       # K-NONCE, 200 KB under the signature
        e.b.reconcile(a, big)
        for _ in range(3):
            e.read()
            e.d.assert_not_covered(msg='never COVERED while the report is NOT_HELD')
        q = self.items(e, 'EQUIVOCATION')
        self.assertTrue(q, 'the EQUIVOCATION notice is still made')
        self.assertLessEqual(len(canonical(q[0]).encode()), 65536)
        self.assertIn('NOT_HELD', canonical(q[0]['body']))
        self.assertIn('EVIDENCE_NOT_HELD', self.alarm_reasons(e)); self.assertIn(H(a), canonical([i['body'] for i in self.items(e, 'OBSERVATION_INCOMPLETE')]))
        self._never_leaves_out(e)

    @acc(id='C6-EX-03', rules=['E-X-3', 'O-L-1', 'O-L-2'], cap='CAP-KEY',
         catches='(the 5 MB run answer) a courier that reads it whole or leaves the run out of a statement')
    def test_capkey_5mb(self):
        s = self.capkey_signer(); e = self.courier_env(budget_keys=[s.public_key], cc={'RUN_ANSWER_MAX': 1 << 20})
        a, n, r, v = key_run(e.b, s, 'PASS')
        for i in range(9):
            e.b.reconcile(a, s.sign('EFFECT_REPORT', e.b.root, a, n, 'EFFECT', 'd' * 555_000 + str(i)))
        key_run(e.b, s, 'FAIL')
        e.read()
        self.assertIn('RUN_OVERSIZE', self.alarm_reasons(e))
        self.assertIn(H(a), canonical([i['body'] for i in self.items(e, 'OBSERVATION_INCOMPLETE')]), 'the alarm names the run')
        self.assertTrue(self.items(e, 'FAIL'), 'other runs\' notices are still taken')
        self._never_leaves_out(e); e.d.assert_not_covered()

    @acc(id='C6-EB1-01', rules=['E-B-1', 'I-K-1'], cap='CAP-KEY',
         catches='a courier that puts some bound reports INLINE and others not, or INLINE beyond INLINE_TOTAL_MAX')
    def test_inline_all_or_none(self):
        s = self.capkey_signer(); e = self.courier_env(budget_keys=[s.public_key], cc={'INLINE_TOTAL_MAX': 2000})
        a, n, r, v = key_run(e.b, s, 'PASS')
        e.b.reconcile(a, s.sign('EFFECT_REPORT', e.b.root, a, n, 'EFFECT', 'q' * 3000))     # a big malformed digest: K-CONFLICT, K-DIGEST
        e.read()
        q = self.items(e, 'EQUIVOCATION')[0]
        where = [b.get('where') for b in e.d.c.bound_of(q['body'])]
        self.assertTrue(where)
        self.assertNotIn('INLINE', where, 'sizes sum beyond INLINE_TOTAL_MAX: none INLINE')
        self.assertEqual(len({x == 'INLINE' for x in where}), 1)
