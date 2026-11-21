"""Section 3.2: each finding that MUST hold (positives, CAP-KEY or CAP-OWNER by 3.6), and I-K-1's bound reports.
Seam: sut.judge_run / sut.judge_unborne_names.  Specification version 5."""
import random

from acc import AccTest, acc
from s3util import val, honest_run, key_budget, key_run, eid, pid, VERDICT_NOTICES
from fixtures.crypto import rand_hex
import sut as SUT


class Findings(AccTest):
    def _equivocal(self, j, findings, msg):
        self.assertFindings(j, findings, msg)
        if set(findings) - {'K-MISSING'}:
            self.assertEqual(j.outcome, 'INCONSISTENT', f'{msg}: a finding other than K-MISSING makes the run INCONSISTENT (3.4)')
            self.assertEqual(j.notice, 'EQUIVOCATION', f'{msg}: one EQUIVOCATION notice is called for (3.4)')
        self.assertFalse(j.believed, f'{msg}: a run with a finding is never believed (K-BEL-1, SAF-9)')

    # ------------------------------------------------------------------ K-CONFLICT
    @acc(id='S3-CONFLICT-01', rules=['K-CONFLICT', 'K-6', '3.4', 'K-BEL-1', 'SAF-9'], cap='CAP-KEY',
         catches='an implementation that keeps the recorded verdict and ignores a second signed result of the same run')
    def test_conflict_after_recorded(self):
        s = self.capkey_signer(); b = key_budget(self, s)
        aid, nonce, rep1, v1 = key_run(b, s, 'FAIL')
        rep2 = s.effect(b.root, aid, nonce, 'EFFECT', val('PASS'))
        b.reconcile(aid, rep2)                                   # DUPLICATE/DENIED: the witness keeps it at its decision
        j = self.judge(b, aid)
        self._equivocal(j, {'K-CONFLICT'}, 'two EFFECT reports with different digests')
        self.assertNotIn(j.notice, VERDICT_NOTICES, 'no notice that states a verdict beside a finding (3.4)')

    @acc(id='S3-CONFLICT-02', rules=['K-CONFLICT', 'K-BEL-3'], cap='CAP-KEY',
         catches='an implementation that looks for a conflict only beside a recorded verdict')
    def test_conflict_without_recorded(self):
        s = self.capkey_signer(); b = key_budget(self, s)
        aid, nonce = b.new_run(upto='CONSUMED')
        b.reconcile(aid, s.effect(b.root, aid, nonce, 'EFFECT', val('FAIL')), kind='DENIED', code='HELD')
        b.reconcile(aid, s.effect(b.root, aid, nonce, 'NO_EFFECT', None), kind='DENIED', code='HELD')
        self._equivocal(self.judge(b, aid), {'K-CONFLICT'}, 'EFFECT and NO_EFFECT, no recorded verdict')

    @acc(id='S3-CONFLICT-03', rules=['K-CONFLICT'], cap='CAP-KEY',
         catches='an implementation that compares only reports carried by RECONCILE decisions')
    def test_conflict_any_operation(self):
        s = self.capkey_signer(); b = key_budget(self, s)
        aid, nonce, rep1, v1 = key_run(b, s, 'FAIL')
        b.release(aid, s.effect(b.root, aid, nonce, 'EFFECT', val('PASS')))   # an effect report sent with a RELEASE (label NONE)
        self._equivocal(self.judge(b, aid), {'K-CONFLICT'}, 'the second result carried by a RELEASE decision')

    @acc(id='S3-CONFLICT-04', rules=['K-CONFLICT', 'K-3'], cap='CAP-KEY',
         catches='an implementation that checks reports under the first gate key only')
    def test_conflict_second_key(self):
        s1, s2 = self.capkey_signer(), self.capkey_signer(); b = key_budget(self, s1, s2)
        aid, nonce, rep1, v1 = key_run(b, s1, 'FAIL')
        b.reconcile(aid, s2.effect(b.root, aid, nonce, 'EFFECT', val('PASS')))
        self._equivocal(self.judge(b, aid), {'K-CONFLICT'}, 'second result signed by the second gate key given')

    # ------------------------------------------------------------------ K-UNKNOWN-VERDICT
    @acc(id='S3-UNKVERDICT-01', rules=['K-UNKNOWN-VERDICT', 'K-5'], cap='CAP-KEY',
         catches='an implementation that lets a verdict after an UNKNOWN report stand (the honest-sequence reading)')
    def test_unknown_then_verdict(self):
        s = self.capkey_signer(); b = key_budget(self, s)
        aid, nonce = b.new_run(upto='CONSUMED')
        b.reconcile(aid, s.effect(b.root, aid, nonce, 'UNKNOWN', None))
        v = val('PASS'); b.reconcile(aid, s.effect(b.root, aid, nonce, 'EFFECT', v)); b.store_result(aid, v)
        self._equivocal(self.judge(b, aid), {'K-UNKNOWN-VERDICT'}, 'UNKNOWN, then a PASS verdict recorded')

    @acc(id='S3-UNKVERDICT-02', rules=['K-UNKNOWN-VERDICT', 'K-5', 'K-1'], cap='CAP-KEY',
         catches='an implementation that forbids only UNKNOWN-before-verdict, not verdict-before-UNKNOWN')
    def test_verdict_then_unknown(self):
        s = self.capkey_signer(); b = key_budget(self, s)
        aid, nonce, rep, v = key_run(b, s, 'PASS')
        b.reconcile(aid, s.effect(b.root, aid, nonce, 'UNKNOWN', None))
        self._equivocal(self.judge(b, aid), {'K-UNKNOWN-VERDICT'}, 'a PASS recorded, then UNKNOWN')

    # ------------------------------------------------------------------ K-FENCE
    @acc(id='S3-FENCE-01', rules=['K-FENCE'], cap='CAP-KEY',
         catches='an implementation that ignores a fence report once the run has a verdict')
    def test_fence_beside_effect(self):
        s = self.capkey_signer(); b = key_budget(self, s)
        aid, nonce, rep, v = key_run(b, s, 'PASS')
        b.release(aid, s.fence(b.root, aid))
        self._equivocal(self.judge(b, aid), {'K-FENCE'}, 'a fence beside an in-scope EFFECT')

    @acc(id='S3-FENCE-02', rules=['K-FENCE', 'K-NONCE'], cap='CAP-KEY',
         catches='an implementation that counts only in-scope effect reports against a fence')
    def test_fence_beside_foreign_nonce(self):
        s = self.capkey_signer(); b = key_budget(self, s)
        aid, nonce = b.new_run(upto='CONSUMED')
        b.release(aid, s.fence(b.root, aid))
        b.reconcile(aid, s.effect(b.root, aid, 'n-' + rand_hex(20), 'UNKNOWN', None))
        self._equivocal(self.judge(b, aid), {'K-FENCE', 'K-NONCE'}, 'a fence beside a foreign-nonce UNKNOWN report')

    # ------------------------------------------------------------------ K-PHASE
    @acc(id='S3-PHASE-01', rules=['K-PHASE', 'K-4'], cap='CAP-KEY',
         catches='an implementation that does not read the reports of a DISCARDED run (K-4)')
    def test_phase_discarded(self):
        s = self.capkey_signer(); b = key_budget(self, s)
        aid, nonce = b.new_run(upto='ACCEPTED')
        b.discard(aid)
        b.reconcile(aid, s.effect(b.root, aid, nonce, 'EFFECT', val('PASS')))
        self._equivocal(self.judge(b, aid), {'K-PHASE'}, 'an in-scope effect report for a DISCARDED run')

    @acc(id='S3-PHASE-02', rules=['K-PHASE', 'K-4'], cap='CAP-KEY',
         catches='an implementation that does not read the reports of a RELEASED run')
    def test_phase_released(self):
        s = self.capkey_signer(); b = key_budget(self, s)
        aid, nonce = b.new_run(upto='ACCEPTED')
        b.release(aid, s.fence(b.root, aid))                     # BOUND_FENCE: RELEASED
        self.assertEqual(b.phase(aid), 'RELEASED')
        b.reconcile(aid, s.effect(b.root, aid, nonce, 'NO_EFFECT', None))
        self._equivocal(self.judge(b, aid), {'K-PHASE', 'K-FENCE'}, 'an effect report for a RELEASED (fenced) run')

    @acc(id='S3-PHASE-03', rules=['K-PHASE', 'O-R-1', 'D-12', 'I-K-1'], cap='CAP-KEY',
         catches='an implementation that ignores names no attempt bears, or makes one notice per such name')
    def test_phase_unborne_names(self):
        s = self.capkey_signer(); b = key_budget(self, s)
        honest = key_run(b, s, 'PASS')
        r1 = s.effect(b.root, 'ghost-1', 'n-' + rand_hex(20), 'EFFECT', val('PASS'))
        r2 = s.fence(b.root, 'ghost-2')
        b.unborne('ghost-1', r1); b.unborne('ghost-2', r2, op='RELEASE'); b.unborne('ghost-3', None, op='TOKEN')
        j = self.sut.judge_unborne_names(SUT.NamesInput(b.root, b.n, {n: b.run_answer(n)['evidence'] for n in ('ghost-1', 'ghost-2', 'ghost-3')},
                                                         [s.public_key], ['ghost-1', 'ghost-2', 'ghost-3']))
        self.assertEqual(set(j.findings), {'K-PHASE'}, 'a report gate-signed for a name no attempt bears is K-PHASE for the budget')
        self.assertEqual(j.notice, 'EQUIVOCATION', 'one EQUIVOCATION notice for the budget (O-R-1)')
        self.assertEqual(list(j.bound), [eid(r1)], 'the notice binds the earliest such report, once (O-R-1)')

    @acc(id='S3-PHASE-04', rules=['K-PHASE', 'O-R-1'], cap='CAP-KEY',
         catches='an implementation that judges each unborne name alone and so reports many notices, or the latest')
    def test_phase_unborne_one_notice(self):
        s = self.capkey_signer(); b = key_budget(self, s)
        reps = []
        for i in range(5):
            r = s.effect(b.root, f'g{i}', 'n-' + rand_hex(20), 'UNKNOWN', None); reps.append(r); b.unborne(f'g{i}', r)
        ans = {f'g{i}': b.run_answer(f'g{i}')['evidence'] for i in range(5)}
        names = [f'g{i}' for i in range(5)]
        j = self.sut.judge_unborne_names(SUT.NamesInput(b.root, b.n, dict(reversed(list(ans.items()))), [s.public_key], names))
        self.assertEqual(j.notice, 'EQUIVOCATION')
        self.assertEqual(list(j.bound), [eid(reps[0])], 'one notice binding the earliest report by decision, whatever the order given')

    # ------------------------------------------------------------------ K-EARLY
    @acc(id='S3-EARLY-01', rules=['K-EARLY', 'D-14'], cap='CAP-KEY',
         catches='an implementation that does not compare report numbers with the intent acceptance')
    def test_early_before_acceptance(self):
        s = self.capkey_signer(); b = key_budget(self, s)
        aid, nonce = b.new_run(upto='INTENT_PENDING')
        v = val('PASS'); r = s.effect(b.root, aid, nonce, 'EFFECT', v)
        b.reconcile(aid, r, kind='DENIED', code='NOT_CONSUMED')        # an effect before ACCEPT_INTENT
        b.decide(['ACCEPT_INTENT', aid], code='INTENT_ACCEPTED')
        b._set(aid, 'CONSUMED'); b.decide(['CROSS', aid], code='CROSSED')
        b.reconcile(aid, r); b.store_result(aid, v)                     # the same pair recorded afterwards
        self._equivocal(self.judge(b, aid), {'K-EARLY'}, 'an in-scope effect report before the intent acceptance')

    @acc(id='S3-EARLY-02', rules=['K-EARLY', 'K-4'], cap='CAP-KEY',
         catches='an implementation that skips K-EARLY when the run has no intent acceptance at all')
    def test_early_no_acceptance(self):
        s = self.capkey_signer(); b = key_budget(self, s)
        aid, nonce = b.new_run(upto='INTENT_PENDING')
        b.reconcile(aid, s.effect(b.root, aid, nonce, 'UNKNOWN', None), kind='DENIED', code='NOT_CONSUMED')
        self._equivocal(self.judge(b, aid), {'K-EARLY'}, 'an effect report for a run with no intent acceptance')

    # ------------------------------------------------------------------ K-NONCE
    @acc(id='S3-NONCE-01', rules=['K-NONCE', 'D-5'], cap='CAP-KEY',
         catches='an implementation that drops a gate-signed report of this run under another nonce as a stray')
    def test_foreign_nonce(self):
        s = self.capkey_signer(); b = key_budget(self, s)
        aid, nonce, rep, v = key_run(b, s, 'FAIL')
        b.reconcile(aid, s.effect(b.root, aid, 'n-' + rand_hex(20), 'EFFECT', val('PASS')))
        self._equivocal(self.judge(b, aid), {'K-NONCE'}, 'a report for this run under a nonce the chain does not record')

    @acc(id='S3-NONCE-02', rules=['K-NONCE', 'D-4', 'D-5'], cap='CAP-KEY',
         catches='an implementation that treats a report as in scope when the chain nonce is null')
    def test_null_chain_nonce(self):
        s = self.capkey_signer(); b = key_budget(self, s)
        aid, _ = b.new_run(upto='TOKEN')                                 # no nonce yet
        b.reconcile(aid, s.effect(b.root, aid, 'n-' + rand_hex(20), 'UNKNOWN', None), kind='DENIED', code='NOT_CONSUMED')
        j = self.judge(b, aid)
        self.assertIn('K-NONCE', j.findings, 'chain nonce null: every effect report of the run is foreign-nonce (D-5)')
        self.assertNotIn('K-EARLY', j.findings, 'K-EARLY is about in-scope reports only')
        a2, _ = b.new_run(upto='TOKEN')                                  # a report whose own nonce is null too
        b.reconcile(a2, s.sign('EFFECT_REPORT', b.root, a2, None, 'UNKNOWN', '0' * 64), kind='DENIED', code='NOT_CONSUMED')
        j2 = self.judge(b, a2)
        self.assertIn('K-NONCE', j2.findings, 'null equals null is not in scope: "the chain nonce is not null" (D-5)')
        self.assertNotIn('K-EARLY', j2.findings)

    # ------------------------------------------------------------------ K-DIGEST
    @acc(id='S3-DIGEST-01', rules=['K-DIGEST', 'D-7', 'K-BEL-1'], cap='CAP-KEY',
         catches='an implementation that accepts any string as a digest, or believes upper-case hex')
    def test_malformed_digest(self):
        s = self.capkey_signer(); b = key_budget(self, s)
        for bad in ('A' * 64, 'abc', 'g' * 64, 'a' * 65):
            aid, nonce = b.new_run(upto='CONSUMED')
            b.reconcile(aid, s.sign('EFFECT_REPORT', b.root, aid, nonce, 'EFFECT', bad))
            self._equivocal(self.judge(b, aid), {'K-DIGEST'}, f'digest {bad[:10]}...')

    # ------------------------------------------------------------------ K-CLAIM
    @acc(id='S3-CLAIM-01', rules=['K-CLAIM', 'D-3'], cap='CAP-KEY',
         catches='an implementation that drops a gate-signed report with an unknown claim as a stray')
    def test_malformed_claims(self):
        s = self.capkey_signer(); b = key_budget(self, s)
        cases = [('EFFECT_REPORT', 'PASS', True), ('EFFECT_REPORT', 'FENCED_NO_START', True), ('FENCE_REPORT', 'EFFECT', False),
                 ('FENCE_REPORT', 'FENCED_NO_START', 'nonce'), ('FENCE_REPORT', 'FENCED_NO_START', 'digest')]
        for kind, claim, mode in cases:
            aid, nonce = b.new_run(upto='CONSUMED')
            n = nonce if mode in (True, 'nonce') else None
            d = ('0' * 64) if mode in (True, 'digest') else None
            r = s.sign(kind, b.root, aid, n, claim, d)
            (b.reconcile if kind == 'EFFECT_REPORT' else b.release)(aid, r)
            j = self.judge(b, aid)
            self.assertIn('K-CLAIM', j.findings, f'{kind} {claim} ({mode}) is a claim no honest gate host signs')
            self.assertEqual(j.notice, 'EQUIVOCATION'); self.assertFalse(j.believed)

    # ------------------------------------------------------------------ I-K-1
    @acc(id='S3-BOUND-01', rules=['I-K-1', 'K-CONFLICT'], cap='CAP-KEY',
         catches='an implementation that binds the latest reports, or not the recorded one, to the EQUIVOCATION notice')
    def test_bound_conflict(self):
        s = self.capkey_signer(); b = key_budget(self, s)
        aid, nonce = b.new_run(upto='CONSUMED')
        early = s.effect(b.root, aid, nonce, 'EFFECT', val('FAIL'))
        b.reconcile(aid, early, kind='DENIED', code='HELD')
        b.reconcile(aid, s.effect(b.root, aid, nonce, 'NO_EFFECT', None), kind='DENIED', code='HELD')   # a third pair, before the recorded one
        v = val('PASS'); recorded = s.effect(b.root, aid, nonce, 'EFFECT', v); b.reconcile(aid, recorded); b.store_result(aid, v)
        for _ in range(3):
            b.reconcile(aid, s.effect(b.root, aid, nonce, 'EFFECT', val('FAIL')))
        j = self.judge(b, aid)
        self.assertEqual(set(j.bound), {eid(recorded), eid(early)},
                         'K-CONFLICT binds the recorded report and the earliest whose pair differs from it')

    @acc(id='S3-BOUND-02', rules=['I-K-1', 'K-UNKNOWN-VERDICT', 'K-FENCE'], cap='CAP-KEY',
         catches='an implementation that binds one report per finding instead of the earliest of each kind')
    def test_bound_two_kinds(self):
        s = self.capkey_signer(); b = key_budget(self, s)
        aid, nonce = b.new_run(upto='CONSUMED')
        u1 = s.effect(b.root, aid, nonce, 'UNKNOWN', None); b.reconcile(aid, u1)
        f1 = s.fence(b.root, aid); b.release(aid, f1)
        v = val('PASS'); e1 = s.effect(b.root, aid, nonce, 'EFFECT', v); b.reconcile(aid, e1); b.store_result(aid, v)
        b.reconcile(aid, s.effect(b.root, aid, nonce, 'UNKNOWN', {'later': 1}))
        j = self.judge(b, aid)
        self.assertEqual(set(j.findings), {'K-UNKNOWN-VERDICT', 'K-FENCE'})
        self.assertEqual(set(j.bound), {eid(u1), eid(e1), eid(f1)},
                         'the earliest UNKNOWN and the earliest verdict (K-UNKNOWN-VERDICT); the earliest fence and effect (K-FENCE); each once')
        self.assertLessEqual(len(j.bound), 12); self.assertEqual(len(j.bound), len(set(j.bound)), 'the same report is bound once')

    # ------------------------------------------------------------------ K-1
    @acc(id='S3-ORDER-01', rules=['K-1'], cap='CAP-KEY',
         catches='an implementation that takes "the latest report" as anything, or depends on the order of the answer')
    def test_order_independent(self):
        s = self.capkey_signer(); b = key_budget(self, s)
        builds = []
        a1, n1, r1, v1 = key_run(b, s, 'FAIL'); b.reconcile(a1, s.effect(b.root, a1, n1, 'EFFECT', val('PASS'))); builds.append(a1)
        a2, n2, r2, v2 = key_run(b, s, 'PASS'); b.reconcile(a2, s.effect(b.root, a2, n2, 'UNKNOWN', None)); builds.append(a2)
        a3, n3, r3, v3 = key_run(b, s, 'PASS'); builds.append(a3)                               # believed
        a4, n4 = b.new_run(upto='CONSUMED')
        b.reconcile(a4, s.effect(b.root, a4, n4, 'UNKNOWN', None)); b.reconcile(a4, s.effect(b.root, a4, n4, 'UNKNOWN', None)); builds.append(a4)
        rnd = random.Random(16)
        expect = {a1: {'K-CONFLICT'}, a2: {'K-UNKNOWN-VERDICT'}, a3: set(), a4: set()}
        for aid in builds:
            base = self.judge(b, aid)
            self.assertEqual(set(base.findings), expect[aid], 'precondition (non-vacuity): the findings are computed at all')
            for trial in range(6):
                inp = self.run_input(b, aid)
                rnd.shuffle(inp.evidence) if trial else inp.evidence.reverse()
                j = self.sut.judge_run(inp)
                self.assertEqual((set(j.findings), j.outcome, j.believed, j.notice, set(j.bound)),
                                 (set(base.findings), base.outcome, base.believed, base.notice, set(base.bound)),
                                 f'run {aid}: the judgement changed when the reports were given in another order')

    # ------------------------------------------------------------------ reports after N
    @acc(id='S3-AFTERN-01', rules=['K-CONFLICT', '3.1'], cap='CAP-KEY',
         catches='an implementation that judges at N with reports recorded after N')
    def test_reports_after_n_left_out(self):
        s = self.capkey_signer(); b = key_budget(self, s)
        aid, nonce, rep, v = key_run(b, s, 'PASS')
        n = b.n
        b.reconcile(aid, s.effect(b.root, aid, nonce, 'EFFECT', val('FAIL')))
        j = self.judge(b, aid, n=n)
        self.assertFindings(j, set(), 'a conflict recorded after N is not seen at N')
        self.assertTrue(j.believed, 'at N the run is believed PASS')
        self.assertIn('K-CONFLICT', self.judge(b, aid).findings, 'and at the later checkpoint it is a conflict')
