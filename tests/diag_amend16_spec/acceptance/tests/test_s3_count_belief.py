"""Section 3.1 (K-CNT-1 to 5, K-MISSING), 3.3 (belief), 3.4 (what each standing calls for), K-3, and the negatives that
MUST NOT be findings (3.6, K-2, K-7, D-2, D-3).  Negatives are CAP-DB: the honest gate host (another process) signs;
the test only replays, pads, re-sends and misdirects.  Specification version 5."""
import copy

from acc import AccTest, acc
from s3util import val, honest_run, key_budget, key_run, eid, pid, VERDICT_NOTICES
from fixtures.crypto import TestKey, rand_hex, H, canonical
import sut as SUT


class CountRule(AccTest):
    def _missing(self, j, msg, also=()):
        self.assertFindings(j, {'K-MISSING', *also}, msg)
        self.assertFalse(j.whole, f'{msg}: K-MISSING: the reading is not whole (3.4)')
        self.assertFalse(j.believed, f'{msg}: never believed with K-MISSING (K-BEL-1)')
        if not also:
            self.assertNotEqual(j.notice, 'EQUIVOCATION', f'{msg}: K-MISSING alone calls for no notice of its own (3.4)')
            self.assertNotIn(j.notice, VERDICT_NOTICES, f'{msg}: no verdict notice for a run whose answer is not whole')

    @acc(id='S3-CNT1-01', rules=['K-CNT-1', 'K-CNT-5', 'K-MISSING'], cap='CAP-OWNER',
         catches='an implementation that does not check that a labelled decision has its report')
    def test_cnt1_report_removed(self):
        b = self.new_budget()
        aid, nonce, rep, v = honest_run(self, b, 'PASS')
        b.evidence[aid] = [e for e in b.evidence[aid] if e['seq'] != b.n]        # the owner's role removes the row
        self._missing(self.judge(b, aid), 'the recorded verdict\'s report is gone')

    @acc(id='S3-CNT2-01', rules=['K-CNT-2', 'K-MISSING'], cap='CAP-OWNER',
         catches='an implementation that accepts a report at a decision that is not a RELEASE or RECONCILE of the run')
    def test_cnt2_misplaced(self):
        b = self.new_budget()
        aid, nonce, rep, v = honest_run(self, b, 'FAIL')
        cross = next(d['seq'] for d in b.decisions if d['op'][:2] == ['CROSS', aid])
        b.evidence[aid].append({'seq': cross, 'evidence': rep, 'derived': None})
        self._missing(self.judge(b, aid), 'a report at the CROSS decision')

    @acc(id='S3-CNT2-02', rules=['K-CNT-2', 'K-MISSING'], cap='CAP-OWNER',
         catches='an implementation that places a report by its aid, not by the decision at its number')
    def test_cnt2_other_runs_decision(self):
        b = self.new_budget()
        a1, n1, r1, v1 = honest_run(self, b, 'FAIL')
        a2, n2, r2, v2 = honest_run(self, b, 'PASS')
        rec2 = b.n
        b.evidence[a1].append({'seq': rec2, 'evidence': r1, 'derived': None})   # at the RECONCILE of another run
        self._missing(self.judge(b, a1), 'a report at a decision naming another run')

    @acc(id='S3-CNT3-01', rules=['K-CNT-3', 'K-MISSING'], cap='CAP-OWNER',
         catches='an implementation that believes phase EFFECT without a recorded verdict')
    def test_cnt3_effect_without_verdict(self):
        b = self.new_budget()
        aid, nonce = b.new_run(upto='CONSUMED')
        b._set(aid, 'EFFECT'); b.decide(['TIMEOUT', aid], code='ODD')                # EFFECT with no VERDICT_RECORDED
        self._missing(self.judge(b, aid), 'phase EFFECT, no recorded verdict')

    @acc(id='S3-CNT3-02', rules=['K-CNT-3', 'K-MISSING'], cap='CAP-OWNER',
         catches='an implementation that allows two recorded verdicts when their pairs agree')
    def test_cnt3_two_recorded(self):
        b = self.new_budget()
        aid, nonce, rep, v = honest_run(self, b, 'FAIL')
        b.reconcile(aid, rep, kind='APPLIED', code='VERDICT_RECORDED')
        self._missing(self.judge(b, aid), 'two VERDICT_RECORDED decisions')

    @acc(id='S3-CNT3-03', rules=['K-CNT-3', 'K-MISSING'], cap='CAP-OWNER',
         catches='an implementation that does not compare the recorded operand v with the phase and the report\'s claim')
    def test_cnt3_operand_mismatch(self):
        b = self.new_budget()
        aid, nonce = b.new_run(upto='CONSUMED')
        v = val('PASS'); rep = self.gate().run(b.root, aid, nonce, 'EFFECT', v)
        b._set(aid, 'EFFECT')
        b.decide(['RECONCILE', aid, 'NO_EFFECT', 'AUTHORISED'], 'APPLIED', 'VERDICT_RECORDED', rep, 'AUTHORISED')
        b.store_result(aid, v)
        self._missing(self.judge(b, aid), 'operand NO_EFFECT, phase EFFECT, report EFFECT')

    @acc(id='S3-CNT3-04', rules=['K-CNT-3', 'K-MISSING'], cap='CAP-OWNER',
         catches='an implementation that does not require the recorded report to be in scope')
    def test_cnt3_recorded_out_of_scope(self):
        b = self.new_budget()
        a_other, n_other, r_other, v_other = honest_run(self, b, 'PASS')
        aid, nonce = b.new_run(upto='CONSUMED')
        b._set(aid, 'EFFECT')
        b.decide(['RECONCILE', aid, 'EFFECT', 'AUTHORISED'], 'APPLIED', 'VERDICT_RECORDED', r_other, 'AUTHORISED')
        j = self.judge(b, aid)
        self.assertIn('K-MISSING', j.findings, 'the recorded report is another run\'s (a stray): not whole')
        self.assertFalse(j.believed)

    @acc(id='S3-CNT4-01', rules=['K-CNT-4', 'K-3', 'K-MISSING'], cap='NONE',
         catches='an implementation that does not see that the reader\'s gate keys are not the witness\'s')
    def test_cnt4_key_reader_lacks(self):
        b = self.new_budget()
        aid, nonce, rep, v = honest_run(self, b, 'PASS')
        j = self.judge(b, aid, keys=[TestKey().public_hex])             # the engineer configured another key (P-KEYS)
        self._missing(j, 'AUTHORISED decision, report not gate-signed under the reader\'s keys')

    @acc(id='S3-KEYS-01', rules=['K-3', 'D-3'], cap='CAP-DB',
         catches='an implementation that uses only the first gate key given')
    def test_every_key(self):
        b = self.new_budget()
        aid, nonce, rep, v = honest_run(self, b, 'FAIL')
        j = self.judge(b, aid, keys=[TestKey().public_hex, self.gate().public_key])
        self.assertFindings(j, set(), 'a report verifying under the second key given is gate-signed')
        self.assertTrue(j.believed); self.assertEqual(j.outcome, 'FAIL'); self.assertEqual(j.notice, 'FAIL')

    @acc(id='S3-MISSEQ-01', rules=['3.4', 'K-MISSING', 'K-CONFLICT', 'K-CNT-4'], cap='CAP-KEY',
         catches='an implementation that suppresses the EQUIVOCATION notice when K-MISSING also holds')
    def test_equivocation_beside_missing(self):
        s1, s2 = self.capkey_signer(), self.capkey_signer()
        b = key_budget(self, s1, s2)                                     # the witness pins both
        aid, nonce, rep, v = key_run(b, s1, 'FAIL')
        b.reconcile(aid, s2.effect(b.root, aid, nonce, 'EFFECT', val('PASS')))
        self.assertIn('K-MISSING', self.judge(b, aid, keys=[s1.public_key]).findings,
                      'the reader lacks s2: K-CNT-4 fails at the AUTHORISED decision carrying s2\'s report')
        b.reconcile(aid, s1.effect(b.root, aid, nonce, 'EFFECT', val('PASS')))    # and a conflict the reader can see
        j = self.judge(b, aid, keys=[s1.public_key])
        self.assertFindings(j, {'K-MISSING', 'K-CONFLICT'}, 'both hold')
        self.assertEqual(j.outcome, 'INCONSISTENT'); self.assertEqual(j.notice, 'EQUIVOCATION', 'one EQUIVOCATION notice beside K-MISSING (3.4)')
        self.assertFalse(j.whole)

    # ------------------------------------------------------------------ K-REC-3
    @acc(id='S3-REC3-01', rules=['K-REC-3', 'L-1', 'K-CNT-1'], cap='CAP-OWNER',
         catches='an implementation that demands a report at a decision labelled NONE (it would fail every honest record)')
    def test_none_label_may_lack_report(self):
        b = self.new_budget()
        aid, nonce, rep, v = honest_run(self, b, 'FAIL')
        b.release(aid, {'kind': 'JUNK'})                                    # label NONE, report row kept
        b.evidence[aid] = [e for e in b.evidence[aid] if e['seq'] != b.n]   # and removed: undetectable by L-1
        j = self.judge(b, aid)
        self.assertFindings(j, set(), 'a report of a decision labelled NONE may be absent')
        self.assertTrue(j.believed); self.assertEqual(j.outcome, 'FAIL')


    @acc(id='S3-CNT1-02', rules=['K-CNT-1', 'K-MISSING', 'D-11'], cap='CAP-OWNER',
         catches='an implementation that checks the report of AUTHORISED decisions only, not of BOUND_FENCE or WRONG_BINDING')
    def test_cnt1_fence_and_wrong_binding_removed(self):
        b = self.new_budget()
        aid, nonce = b.new_run(upto='CONSUMED')
        b.release(aid, self.gate().fence(b.root, aid))                      # BOUND_FENCE, DENIED (a consumed run)
        self.assertFindings(self.judge(b, aid), set(), 'precondition: a fence alone is not a finding')
        b.evidence[aid] = []
        self._missing(self.judge(b, aid), 'the BOUND_FENCE decision\'s report is gone')
        b2 = self.new_budget(tag='wb')
        a1, n1, r1, v1 = honest_run(self, b2, 'FAIL')
        a2, n2, r2, v2 = honest_run(self, b2, 'PASS')
        b2.reconcile(a1, r2)                                               # WRONG_BINDING
        self.assertEqual(b2.decisions[-1]['op'][3], 'WRONG_BINDING')
        b2.evidence[a1] = [e for e in b2.evidence[a1] if e['seq'] != b2.n]
        self._missing(self.judge(b2, a1), 'the WRONG_BINDING decision\'s report is gone')


class Negatives(AccTest):
    """What MUST NOT be a finding (3.6 last paragraph, K-2, K-7, D-2, D-3), with honest reports only."""

    def _clean(self, j, msg, outcome=None, believed=None):
        self.assertFindings(j, set(), msg)
        if outcome is not None:
            self.assertEqual(j.outcome, outcome, f'{msg}: outcome')
        if believed is not None:
            self.assertEqual(j.believed, believed, f'{msg}: belief')
        self.assertNotEqual(j.notice, 'EQUIVOCATION', f'{msg}: no EQUIVOCATION notice')

    @acc(id='S3-NEG-PADDED-01', rules=['K-2', 'D-2', '3.6'], cap='CAP-DB',
         catches='an implementation that compares report bytes, not pairs (100 KB of unsigned fields made a "conflict")')
    def test_resent_with_fields(self):
        b = self.new_budget()
        aid, nonce, rep, v = honest_run(self, b, 'FAIL')
        padded = dict(copy.deepcopy(rep), note='x' * 100_000, claim_shown='PASS', result_digest_extra='0' * 64)
        b.reconcile(aid, padded)                                             # DUPLICATE AUTHORISED
        j = self.judge(b, aid)
        self._clean(j, 'a genuine report sent again with unsigned fields', 'FAIL', True)
        self.assertEqual(j.recorded_pair_id, pid(rep), 'the recorded pair is the signed pair (O-P-1)')

    @acc(id='S3-NEG-REPEAT-01', rules=['K-2', 'D-6'], cap='CAP-KEY',
         catches='an implementation that counts the same pair signed again with other bytes (another gate key) as two results')
    def test_same_pair_other_bytes(self):
        s1, s2 = self.capkey_signer(), self.capkey_signer(); b = key_budget(self, s1, s2)
        aid, nonce, rep, v = key_run(b, s1, 'PASS')
        again = s2.effect(b.root, aid, nonce, 'EFFECT', v)
        self.assertNotEqual(again['signature'], rep['signature'])
        b.reconcile(aid, again)
        self._clean(self.judge(b, aid), 'one pair, two signatures', 'PASS', True)

    @acc(id='S3-NEG-NULL-01', rules=['D-2', 'K-CLAIM', 'K-7'], cap='CAP-DB',
         catches='an implementation that reads a deleted null signed field as malformed (K-CLAIM at CAP-DB\'s will)')
    def test_absent_field_is_null(self):
        b = self.new_budget()
        aid, nonce = b.new_run(upto='TOKEN')
        f = self.gate().fence(b.root, aid)
        g = {k: v for k, v in f.items() if k not in ('nonce', 'result_digest')}
        b.release(aid, g)
        self.assertEqual(b.decisions[-1]['op'][2], 'BOUND_FENCE', 'precondition: the witness takes it as BOUND_FENCE')
        self._clean(self.judge(b, aid), 'a fence report with its two null fields deleted', 'RELEASED')

    @acc(id='S3-NEG-FENCE-01', rules=['K-7', '3.6'], cap='CAP-DB',
         catches='an implementation that makes a fence beside a consumed run a finding (CAP-DB could make notices at will)')
    def test_fence_alone_consumed(self):
        b = self.new_budget()
        aid, nonce = b.new_run(upto='CONSUMED')
        f = self.gate().fence(b.root, aid)                                  # the honest host never ran it (Q1)
        b.release(aid, f)
        self.assertEqual(b.decisions[-1]['op'][2], 'BOUND_FENCE')
        self._clean(self.judge(b, aid), 'a fence alone beside a consumed run')

    @acc(id='S3-NEG-STRAY-01', rules=['D-3', '3.6', 'E-X-5'], cap='CAP-DB',
         catches='an implementation that treats strays (unsigned, other key, garbage) as findings or as K-MISSING')
    def test_strays(self):
        b = self.new_budget()
        aid, nonce, rep, v = honest_run(self, b, 'FAIL')
        other = TestKey()
        strays = [{'kind': 'EFFECT_REPORT', 'root': b.root, 'aid': aid, 'nonce': nonce, 'claim': 'EFFECT', 'result_digest': H(val('PASS')),
                   'signer': other.public_hex, 'signature': '00' * 64},
                  dict(rep, signature='11' * 64, claim='NO_EFFECT'), 'not a report', {'kind': 'FENCE_REPORT'}, None]
        for x in strays:
            b.reconcile(aid, x)
        self._clean(self.judge(b, aid), 'strays at decisions labelled NONE', 'FAIL', True)

    @acc(id='S3-NEG-OTHERRUN-01', rules=['D-3', '3.6', 'K-BEL-1', 'K-BEL-2'], cap='CAP-DB',
         catches='an implementation that lets another run\'s genuine PASS report, and its result, make a FAIL run read PASS')
    def test_other_run_replayed(self):
        b = self.new_budget()
        a1, n1, r1, v1 = honest_run(self, b, 'FAIL', store=False)          # its result withheld
        a2, n2, r2, v2 = honest_run(self, b, 'PASS')
        b.reconcile(a1, r2); b.release(a1, r2)                               # WRONG_BINDING / NONE: kept, not counted
        b.store_result(a1, v2)                                               # the other run's PASS result stored
        j = self.judge(b, a1)
        self._clean(j, 'another run\'s genuine report replayed', 'UNVERIFIED', False)
        self.assertTrue(j.notice_after_wait, 'UNVERIFIED is called for after the waiting time (3.4)')

    @acc(id='S3-NEG-OTHERBUDGET-01', rules=['D-3', '3.6'], cap='CAP-DB',
         catches='an implementation that counts a genuine report of another budget bearing the same run name and nonce')
    def test_other_budget_replayed(self):
        b1, b2 = self.new_budget(tag='one'), self.new_budget(tag='two')
        a1, n1, r1, v1 = honest_run(self, b1, 'PASS')
        aid, nonce = b2.new_run(aid=a1, nonce=n1, upto='CONSUMED')          # same name and nonce, another budget
        b2.reconcile(aid, r1)
        b2.store_result(aid, v1)
        j = self.judge(b2, aid)
        self._clean(j, 'a genuine report of another budget')
        self.assertFalse(j.believed); self.assertNotEqual(j.outcome, 'PASS')
        v2 = val('FAIL'); r2 = self.gate().run(b2.root, aid, nonce, 'EFFECT', v2)   # now b2's own honest FAIL is recorded
        b2.reconcile(aid, r2); b2.results[aid] = {'outcome': 'value', 'value': v2}
        b2.reconcile(aid, r1)                                                  # and b1's PASS (same name, nonce) replayed again
        self._clean(self.judge(b2, aid), 'another budget\'s report beside a recorded verdict is no conflict', 'FAIL', True)

    @acc(id='S3-NEG-NAMES-01', rules=['D-12', 'O-R-1', '3.6'], cap='CAP-DB',
         catches='an implementation that makes a notice for names no attempt bears when they carry no gate-signed report')
    def test_names_no_run(self):
        b = self.new_budget()
        honest_run(self, b, 'PASS')
        names = ['x' * 6146, 'ghost', 'g2']
        b.unborne(names[0], None, op='TOKEN'); b.unborne(names[1], {'kind': 'EFFECT_REPORT', 'aid': 'ghost'}); b.unborne(names[2], 'junk', op='RELEASE')
        j = self.sut.judge_unborne_names(SUT.NamesInput(b.root, b.n, {n: b.run_answer(n)['evidence'] for n in names}, list(b.wgk), names))
        self.assertEqual(set(j.findings), set(), 'decisions naming no run, with strays only, are not a finding')
        self.assertIsNone(j.notice)

    @acc(id='S3-NEG-NAMES-02', rules=['D-3', 'D-12', 'O-R-1'], cap='CAP-DB',
         catches='an implementation that takes a genuine report of a REAL run, replayed under a ghost name, as K-PHASE')
    def test_names_with_replayed_genuine(self):
        b = self.new_budget()
        a, n, r, v = honest_run(self, b, 'PASS')
        b.unborne('ghost', r)                                    # r names run a, not 'ghost': a stray for 'ghost'
        j = self.sut.judge_unborne_names(SUT.NamesInput(b.root, b.n, {'ghost': b.run_answer('ghost')['evidence']}, list(b.wgk), ['ghost']))
        self.assertEqual(set(j.findings), set()); self.assertIsNone(j.notice)

    @acc(id='S3-NEG-UNKNOWN-01', rules=['K-5', '3.4', 'D-8'], cap='CAP-DB',
         catches='an implementation that treats UNKNOWN reports alone as K-UNKNOWN-VERDICT')
    def test_unknown_alone(self):
        b = self.new_budget()
        aid, nonce = b.new_run(upto='CONSUMED')
        u = self.gate().run(b.root, aid, nonce, 'UNKNOWN', None)
        b.reconcile(aid, u); b.reconcile(aid, u)
        j = self.judge(b, aid)
        self._clean(j, 'UNKNOWN reports alone', 'INTERRUPTED', False)
        self.assertEqual(j.notice, 'INTERRUPTED', 'phase CONSUMED, U, V empty: INTERRUPTED as today (3.4)')


class Belief(AccTest):
    @acc(id='S3-BEL-01', rules=['K-BEL-1', '3.4'], cap='CAP-DB',
         catches='an implementation that does not believe an honest verdict (or calls a notice for a PASS)')
    def test_believed_pass_and_fail(self):
        b = self.new_budget()
        for verdict, notice in (('PASS', None), ('FAIL', 'FAIL'), ('UNKNOWN', 'UNKNOWN'), ('ODD', 'INVALID')):
            aid, nonce, rep, v = honest_run(self, b, verdict)
            j = self.judge(b, aid)
            self.assertFindings(j, set(), verdict)
            self.assertTrue(j.believed, f'{verdict}: believed (K-BEL-1)')
            self.assertEqual(j.outcome, verdict if verdict != 'ODD' else 'INVALID', 'the result\'s own verdict (3.4)')
            self.assertEqual(j.notice, notice, f'{verdict}: notice as today')
            self.assertFalse(j.notice_after_wait)
            self.assertEqual(j.recorded_pair_id, pid(rep))

    @acc(id='S3-BEL-02', rules=['K-BEL-1', 'K-BEL-4', 'D-8', 'O-C-1'], cap='CAP-DB',
         catches='an implementation that believes an envelope whose outcome is \'unknown\' because its value matches')
    def test_unknown_envelope_with_matching_value(self):
        b = self.new_budget()
        aid, nonce, rep, v = honest_run(self, b, 'PASS', store=False)
        b.store_result(aid, envelope={'outcome': 'unknown', 'detail': 'replaceable', 'value': v})
        j = self.judge(b, aid)
        self.assertFalse(j.believed, 'the stored marker (c) is never the basis of an outcome (K-BEL-4)')
        self.assertEqual(j.outcome, 'UNVERIFIED'); self.assertTrue(j.notice_after_wait)

    @acc(id='S3-BEL-03', rules=['K-BEL-1'], cap='CAP-DB',
         catches='an implementation that reads an envelope without an outcome field as \'value\' (e25a297 does)')
    def test_envelope_outcome_exactly_value(self):
        b = self.new_budget()
        for env in ({'value': None}, {'outcome': 'VALUE'}, {'outcome': 'no_effect'}):
            aid, nonce, rep, v = honest_run(self, b, 'PASS', store=False)
            e = dict(env); e['value'] = v
            b.store_result(aid, envelope=e)
            j = self.judge(b, aid)
            self.assertFalse(j.believed, f'envelope {sorted(env)} outcome {env.get("outcome")!r}: not exactly \'value\'')
            self.assertNotEqual(j.outcome, 'PASS')

    @acc(id='S3-BEL-04', rules=['K-BEL-1', '3.4', 'L-11'], cap='CAP-DB',
         catches='an implementation that believes a result that does not hash to the recorded digest')
    def test_mismatch_unverified(self):
        b = self.new_budget()
        aid, nonce, rep, v = honest_run(self, b, 'FAIL', store=False)
        b.store_result(aid, dict(v, verdict='PASS'))
        j = self.judge(b, aid)
        self.assertFindings(j, set()); self.assertFalse(j.believed)
        self.assertEqual(j.outcome, 'UNVERIFIED'); self.assertEqual(j.notice, 'UNVERIFIED'); self.assertTrue(j.notice_after_wait)

    @acc(id='S3-BEL-05', rules=['K-BEL-2', 'K-CONFLICT'], cap='CAP-KEY',
         catches='an implementation that believes a stored result matching a report other than the recorded one')
    def test_belief_only_recorded(self):
        s = self.capkey_signer(); b = key_budget(self, s)
        aid, nonce, rep, v = key_run(b, s, 'FAIL', store=False)
        v2 = val('PASS'); b.reconcile(aid, s.effect(b.root, aid, nonce, 'EFFECT', v2)); b.store_result(aid, v2)
        j = self.judge(b, aid)
        self.assertFalse(j.believed, 'a report at another decision is never the basis of belief')
        self.assertNotEqual(j.outcome, 'PASS')

    @acc(id='S3-BEL-06', rules=['K-BEL-3', 'K-CNT-3'], cap='CAP-DB',
         catches='an implementation that gives a verdict from verdict reports with no recorded verdict')
    def test_no_recorded_verdict(self):
        b = self.new_budget()
        aid, nonce = b.new_run(upto='CONSUMED')
        v = val('PASS'); rep = self.gate().run(b.root, aid, nonce, 'EFFECT', v)
        b.reconcile(aid, rep, kind='DENIED', code='HELD'); b.store_result(aid, v)
        j = self.judge(b, aid)
        self.assertFindings(j, set())
        self.assertFalse(j.believed, 'no recorded verdict: no verdict, not final (K-BEL-3)')
        self.assertNotIn(j.outcome, ('PASS', 'FAIL', 'UNKNOWN', 'INVALID'))

    @acc(id='S3-BEL-07', rules=['K-BEL-1', '3.4'], cap='CAP-DB',
         catches='an implementation that believes a NO_EFFECT run, or calls no REFUNDED notice for it')
    def test_refunded(self):
        b = self.new_budget()
        aid, nonce, rep, v = honest_run(self, b, 'PASS', claim='NO_EFFECT')
        j = self.judge(b, aid)
        self.assertFindings(j, set()); self.assertFalse(j.believed)
        self.assertEqual(j.outcome, 'REFUNDED'); self.assertEqual(j.notice, 'REFUNDED')


class RecordChecker(AccTest):
    def _record_input(self, b, keys=None):
        atts = [{'aid': a, 'phase': b.phase(a), 'nonce': b.nonce(a), 'evidence': b.run_answer(a)['evidence'],
                 'result': b.results.get(a)} for a in b.attempts]
        return SUT.RecordRunsInput(b.root, copy.deepcopy(b.decisions), atts, list(keys or b.wgk))

    @acc(id='S3-REC1-01', rules=['K-REC-1', 'K-3', 'SAF-9'], cap='CAP-KEY',
         catches='a record checker that passes a record carrying a run with a finding, or judges by another rule than the courier')
    def test_record_same_rule(self):
        s = self.capkey_signer(); b = key_budget(self, s)
        clean = key_run(b, s, 'PASS')[0]
        a1, n1, r1, v1 = key_run(b, s, 'FAIL'); b.reconcile(a1, s.effect(b.root, a1, n1, 'EFFECT', val('PASS')))
        a2, n2 = b.new_run(upto='CONSUMED'); b.reconcile(a2, s.effect(b.root, a2, n2, 'UNKNOWN', None)); b.reconcile(a2, s.effect(b.root, a2, n2, 'NO_EFFECT', None))
        a3, n3, r3, v3 = key_run(b, s, 'PASS'); b.release(a3, s.fence(b.root, a3))
        got = self.sut.record_judge_runs(self._record_input(b))
        for aid in (clean, a1, a2, a3):
            self.assertEqual(set(got.get(aid, ())), set(self.judge(b, aid).findings),
                             f'run {aid}: the record\'s checker and the courier judge by the same rule (K-3, K-REC-1)')
        self.assertTrue(got.get(a1) and got.get(a2) and got.get(a3), 'the record fails on each of these runs')
        self.assertFalse(got.get(clean), 'and not on the clean one')

    @acc(id='S3-REC1-02', rules=['K-REC-1', 'K-MISSING'], cap='CAP-OWNER',
         catches='a record checker that does not apply K-MISSING to the reports a record carries')
    def test_record_missing(self):
        b = self.new_budget()
        aid, nonce, rep, v = honest_run(self, b, 'FAIL')
        inp = self._record_input(b)
        inp.attempts[0]['evidence'] = []                                   # a report taken out of the record's body
        self.assertIn('K-MISSING', set(self.sut.record_judge_runs(inp).get(aid, ())))

    @acc(id='S3-REC2-01', rules=['K-REC-2', '11-EARLIER-FORMS'], cap='CAP-DB',
         catches='a record checker that does not fail a record from which a report was taken after signing')
    def test_record_signature(self):
        import json, os
        here = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
        rec = json.load(open(os.path.join(here, 'record_revA.json'))); keys = json.load(open(os.path.join(here, 'keys.json')))
        ok, failed = self.sut.verify_record(copy.deepcopy(rec), keys)
        self.assertTrue(ok, f'precondition: the signed sample record of e25a297 verifies (earlier records go on verifying); failed {failed}')
        cut = copy.deepcopy(rec)
        a = next(x for x in cut['attempts'] if x.get('evidence'))
        a['evidence'] = a['evidence'][1:]
        ok2, failed2 = self.sut.verify_record(cut, keys)
        self.assertFalse(ok2, 'a report taken out of a signed record fails it'); self.assertIn(1, failed2, 'it fails the record\'s signature (check 1)')
