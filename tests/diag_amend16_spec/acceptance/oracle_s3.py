"""TEST ORACLE - NOT AN IMPLEMENTATION, NOT FOR PRODUCTION.

A small reading of section 3 of the Amendment 16 specification (version 6), written by the test author only to show that
the section 3 acceptance tests can all pass together, and - by switching one rule off at a time (MUTANTS) - that each
planted defect is caught by at least one test.  It is not reviewed, it is not the courier, and agreement between it and
the tests says nothing about any implementation (section 12).

Bound by sut_oracle_s3.py.  ORACLE_MUTANT (environment) names one planted defect.
"""
import os

from fixtures.crypto import H, report_message, verify_sig, well_formed_digest, pair_id, evidence_id, canonical
import sut as SUT

MUTANTS = {
    'no_conflict': 'K-CONFLICT never reported',
    'no_unknown_verdict': 'K-UNKNOWN-VERDICT never reported',
    'unknown_verdict_one_order': 'K-UNKNOWN-VERDICT only when the UNKNOWN report comes first',
    'no_fence': 'K-FENCE never reported',
    'fence_in_scope_only': 'K-FENCE counts only in-scope effect reports',
    'no_phase': 'K-PHASE (runs) never reported',
    'phase_discarded_only': 'K-PHASE only for DISCARDED runs (RELEASED skipped: K-4)',
    'no_early': 'K-EARLY never reported',
    'early_needs_intent': 'K-EARLY not reported when the run has no intent acceptance',
    'no_nonce': 'K-NONCE never reported (foreign-nonce reports dropped as strays)',
    'null_nonce_in_scope': 'a report is in scope when the chain nonce is null',
    'no_digest': 'K-DIGEST never reported',
    'digest_case_insensitive': 'upper-case hex accepted as a well-formed digest',
    'no_claim': 'K-CLAIM never reported',
    'no_cnt1': 'K-CNT-1 not checked',
    'no_cnt2': 'K-CNT-2 not checked',
    'no_cnt3': 'K-CNT-3 not checked',
    'no_cnt4': 'K-CNT-4 not checked',
    'cnt1_on_none': 'K-CNT-1 also demands a report at decisions labelled NONE',
    'bytes_not_pairs': 'K-2 broken: reports compared by bytes (signature), not pairs',
    'first_key_only': 'K-3 broken: only the first gate key given is used',
    'latest_report': 'K-1 broken: the latest verdict report is taken as the recorded one',
    'include_after_n': 'reports recorded after N are not left out',
    'believe_unknown_env': "K-BEL-4 broken: an 'unknown' envelope with a matching value is believed",
    'believe_missing_outcome': "an envelope without 'outcome' is read as 'value'",
    'believe_any_report': 'K-BEL-2 broken: belief on any in-scope EFFECT digest',
    'believe_no_recorded': 'K-BEL-3 broken: verdict reports without a recorded verdict give a verdict',
    'fence_alone_finding': 'K-7 broken: a fence report alone is a finding (K-FENCE)',
    'absent_not_null': 'D-2 broken: an absent signed field is not read as null (K-CLAIM)',
    'missing_hides_equivocation': '3.4 broken: K-MISSING suppresses the EQUIVOCATION notice',
    'verdict_notice_with_finding': '3.4 broken: a verdict notice is still called for beside a finding',
    'stray_is_finding': 'D-3 broken: another run\'s genuine report counts as a foreign-nonce report',
    'other_budget_counts': 'D-3 broken: the root is not compared',
    'names_any_report': 'O-R-1 broken: any report under an unborne name is K-PHASE',
    'names_latest': 'O-R-1 broken: the budget notice binds the latest report',
    'no_names': 'O-R-1 broken: names no attempt bears are not judged',
    'bound_latest': 'I-K-1 broken: the latest reports are bound',
    'bound_no_recorded': 'I-K-1 broken: the recorded report is not preferred for K-CONFLICT',
    'unknown_alone_finding': 'K-5 broken: UNKNOWN reports alone are a finding',
    'interrupted_as_no_outcome': '3.4 broken: CONSUMED with U only reads NO_OUTCOME',
    'refunded_silent': '3.4 broken: NO_EFFECT calls no REFUNDED notice',
    'unverified_no_wait': 'K-N-3/3.4 broken: UNVERIFIED notice called for at once',
    'record_lax': 'K-REC-1 broken: the record checker reports no findings',
}
M = os.environ.get('ORACLE_MUTANT') or None
if M and M not in MUTANTS:
    raise SystemExit(f'unknown mutant {M}')
KEEP = ('RELEASE', 'RECONCILE')


def _gate_signed(r, keys, root, aid):
    if not isinstance(r, dict) or r.get('kind') not in ('EFFECT_REPORT', 'FENCE_REPORT'):
        return False
    if M == 'absent_not_null' and any(k not in r for k in ('nonce', 'result_digest')):
        return True                                            # then judged a malformed claim below
    ks = list(keys)[:1] if M == 'first_key_only' else list(keys)
    if r.get('signer') not in ks or not verify_sig(r.get('signer', ''), r.get('signature', ''), report_message(r)):
        return False
    if M == 'other_budget_counts':
        return r.get('aid') == aid
    return r.get('root') == root and r.get('aid') == aid


def _order(rows):
    return sorted(rows, key=lambda x: (x[0], canonical(x[1])), reverse=(M in ('bound_latest',)))


def judge(root, aid, n, phase, nonce, decisions, evidence, result, keys):
    ev = [(e['seq'], e.get('evidence')) for e in evidence if isinstance(e, dict) and type(e.get('seq')) is int
          and (e['seq'] <= n or M == 'include_after_n')]
    decs = [d for d in decisions if d['seq'] <= n]
    rel = [d for d in decs if d['op'][0] in KEEP and len(d['op']) > 1 and d['op'][1] == aid]
    rel_seqs = {d['seq'] for d in rel}
    intent = min((d['seq'] for d in decs if d['op'][:2] == ['ACCEPT_INTENT', aid] and d['kind'] == 'APPLIED'), default=None)
    gs = [(s, r) for s, r in ev if _gate_signed(r, keys, root, aid)]
    if M == 'stray_is_finding':
        gs += [(s, r) for s, r in ev if isinstance(r, dict) and r.get('kind') == 'EFFECT_REPORT' and r.get('root') == root and r.get('aid') != aid
               and r.get('signer') in keys and verify_sig(r['signer'], r.get('signature', ''), report_message(r))]
    eff = [(s, r) for s, r in gs if r.get('kind') == 'EFFECT_REPORT']
    fen = [(s, r) for s, r in gs if r.get('kind') == 'FENCE_REPORT']
    scope = lambda r: (nonce is not None or M == 'null_nonce_in_scope') and r.get('nonce') == nonce
    verd = [(s, r) for s, r in eff if scope(r) and r.get('claim') in ('EFFECT', 'NO_EFFECT')]
    unk = [(s, r) for s, r in eff if scope(r) and r.get('claim') == 'UNKNOWN']
    foreign = [(s, r) for s, r in eff if not scope(r)]
    pairkey = (lambda r: r.get('signature')) if M == 'bytes_not_pairs' else (lambda r: (r.get('claim'), r.get('result_digest')))
    V = {pairkey(r) for s, r in verd}
    good_digest = (lambda d: isinstance(d, str) and len(d) == 64 and all(c in '0123456789abcdefABCDEF' for c in d)) if M == 'digest_case_insensitive' else well_formed_digest
    f, bound = set(), []

    def bind(*rows):
        for row in rows:
            if row is not None and evidence_id(row[1]) not in bound:
                bound.append(evidence_id(row[1]))

    first = lambda rows: _order(rows)[0] if rows else None
    recorded_d = [d for d in rel if d['op'][0] == 'RECONCILE' and len(d['op']) == 4 and d['op'][3] == 'AUTHORISED'
                  and d['kind'] == 'APPLIED' and d['code'] == 'VERDICT_RECORDED']
    rec_rows = [(s, r) for s, r in verd if recorded_d and s == recorded_d[0]['seq']]
    if M == 'latest_report' and verd:
        rec_rows = [_order(verd)[-1]]
    if len(V) >= 2 and M != 'no_conflict':
        f.add('K-CONFLICT')
        a = first(rec_rows) if (rec_rows and M != 'bound_no_recorded') else first(verd)
        bind(a, first([x for x in verd if pairkey(x[1]) != pairkey(a[1])]))
    if unk and verd and M != 'no_unknown_verdict' and not (M == 'unknown_verdict_one_order' and first(verd)[0] < first(unk)[0]):
        f.add('K-UNKNOWN-VERDICT'); bind(first(unk), first(verd))
    if M == 'unknown_alone_finding' and unk and not verd:
        f.add('K-UNKNOWN-VERDICT'); bind(first(unk))
    effk = [x for x in eff if scope(x[1])] if M == 'fence_in_scope_only' else eff
    if fen and (effk or M == 'fence_alone_finding') and M != 'no_fence':
        f.add('K-FENCE'); bind(first(fen), first(effk))
    if eff and M != 'no_phase' and (phase == 'DISCARDED' or (phase == 'RELEASED' and M != 'phase_discarded_only')):
        f.add('K-PHASE'); bind(first(eff))
    early = [x for x in eff if scope(x[1]) and (intent is None and M != 'early_needs_intent' or (intent is not None and x[0] < intent))]
    if early and M != 'no_early':
        f.add('K-EARLY'); bind(first(early))
    if foreign and M != 'no_nonce':
        f.add('K-NONCE'); bind(first(foreign))
    bad_d = [x for x in verd if not good_digest(x[1].get('result_digest'))]
    if bad_d and M != 'no_digest':
        f.add('K-DIGEST'); bind(first(bad_d))
    ok_claim = lambda r: (r.get('kind') == 'EFFECT_REPORT' and r.get('claim') in ('EFFECT', 'NO_EFFECT', 'UNKNOWN')) or \
        (r.get('kind') == 'FENCE_REPORT' and r.get('claim') == 'FENCED_NO_START' and r.get('nonce') is None and r.get('result_digest') is None
         and not (M == 'absent_not_null' and ('nonce' not in r or 'result_digest' not in r)))
    bad_c = [x for x in gs if not ok_claim(x[1])]
    if bad_c and M != 'no_claim':
        f.add('K-CLAIM'); bind(first(bad_c))
    # the count rule
    rows_at = lambda s: [r for t, r in ev if t == s]
    miss = False
    if M != 'no_cnt1':
        miss |= any(not rows_at(d['seq']) for d in rel if d['op'][-1] != 'NONE' or M == 'cnt1_on_none')
    if M != 'no_cnt2':
        miss |= any(s not in rel_seqs for s, r in ev)
    if M != 'no_cnt3':
        if len(recorded_d) > 1:
            miss = True
        if phase in ('EFFECT', 'NO_EFFECT') and (len(recorded_d) != 1 or recorded_d[0]['op'][2] != phase):
            miss = True
        for d in recorded_d[:1]:
            rr = [r for r in rows_at(d['seq'])]
            if not any(_gate_signed(r, keys, root, aid) and r.get('kind') == 'EFFECT_REPORT' and scope(r) and r.get('claim') == d['op'][2] for r in rr):
                miss = True
    if M != 'no_cnt4':
        miss |= any(not any(_gate_signed(r, keys, root, aid) for r in rows_at(d['seq'])) for d in rel if d['op'][-1] == 'AUTHORISED')
    if miss:
        f.add('K-MISSING')
    rec = first(rec_rows)
    rec_pair = pair_id(rec[1].get('claim'), rec[1].get('result_digest')) if rec else None
    # belief
    env = result if isinstance(result, dict) else None
    env_ok = env is not None and 'value' in env and (env.get('outcome') == 'value' or (M == 'believe_unknown_env' and env.get('outcome') == 'unknown')
                                                     or (M == 'believe_missing_outcome' and 'outcome' not in env))
    digests = [r.get('result_digest') for s, r in verd if r.get('claim') == 'EFFECT'] if M == 'believe_any_report' else \
        ([rec[1].get('result_digest')] if rec and rec[1].get('claim') == 'EFFECT' else [])
    believed = phase == 'EFFECT' and not f and env_ok and any(good_digest(d) and H(env['value']) == d for d in digests)
    if M == 'believe_no_recorded' and phase == 'CONSUMED' and not f and env_ok and verd and H(env['value']) in [r.get('result_digest') for s, r in verd]:
        believed = True
    # 3.4
    wait = False
    if f - {'K-MISSING'} and not (M == 'missing_hides_equivocation' and 'K-MISSING' in f):
        outcome, notice = 'INCONSISTENT', 'EQUIVOCATION'
        if M == 'verdict_notice_with_finding' and phase == 'EFFECT':
            notice = 'FAIL'
    elif 'K-MISSING' in f:
        outcome, notice = None, None
    elif believed:
        v = env['value'].get('verdict') if isinstance(env['value'], dict) else None
        outcome = v if v in ('PASS', 'FAIL', 'UNKNOWN') else 'INVALID'
        notice = None if outcome == 'PASS' else outcome
    elif phase == 'EFFECT':
        outcome, notice, wait = 'UNVERIFIED', 'UNVERIFIED', M != 'unverified_no_wait'
    elif phase == 'NO_EFFECT':
        outcome, notice = 'REFUNDED', (None if M == 'refunded_silent' else 'REFUNDED')
    elif phase == 'CONSUMED':
        if unk and not verd and M != 'interrupted_as_no_outcome':
            outcome, notice = 'INTERRUPTED', 'INTERRUPTED'
        else:
            outcome, notice, wait = 'NO_OUTCOME', 'NO_OUTCOME', True
    elif phase == 'INTENT_PENDING':
        outcome, notice, wait = 'NO_OUTCOME', 'NO_OUTCOME', True
    elif phase == 'INDETERMINATE':
        outcome, notice = 'INDETERMINATE', 'INDETERMINATE'
    elif phase in ('RESERVING', 'RESERVED', 'TOKEN'):
        outcome, notice = 'PENDING', None
    else:
        outcome, notice = phase, None
    return SUT.RunJudgement(frozenset(f), outcome, believed, notice, wait, tuple(bound), rec_pair, 'K-MISSING' not in f)


def judge_run(inp):
    return judge(inp.root, inp.aid, inp.n, inp.phase, inp.chain_nonce, inp.decisions, inp.evidence, inp.result, inp.gate_keys)


def judge_unborne_names(inp):
    if M == 'no_names':
        return SUT.NamesJudgement(frozenset(), None, ())
    rows = []
    for name, ev in inp.answers.items():
        for e in ev:
            if isinstance(e, dict) and type(e.get('seq')) is int and e['seq'] <= inp.n:
                r = e.get('evidence')
                if _gate_signed(r, inp.gate_keys, inp.root, name) or (M == 'names_any_report' and isinstance(r, dict)):
                    rows.append((e['seq'], r))
    if not rows:
        return SUT.NamesJudgement(frozenset(), None, ())
    pick = sorted(rows, key=lambda x: (x[0], canonical(x[1])))[-1 if M == 'names_latest' else 0]
    return SUT.NamesJudgement(frozenset({'K-PHASE'}), 'EQUIVOCATION', (evidence_id(pick[1]),))


def record_judge_runs(inp):
    out = {}
    n = max((d['seq'] for d in inp.audit), default=0)
    for a in inp.attempts:
        decs = [{k: d[k] for k in ('seq', 'op', 'kind', 'code')} for d in inp.audit if len(d['op']) > 1 and d['op'][1] == a['aid']]
        j = judge(inp.root, a['aid'], n, a['phase'], a['nonce'], decs, a.get('evidence') or [], a.get('result'), inp.gate_keys)
        out[a['aid']] = frozenset() if M == 'record_lax' else j.findings
    return out
