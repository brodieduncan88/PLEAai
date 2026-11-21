"""Reviewer's experiments, phase 2 (21 November 2026).  Predicates are the reviewer's (REVIEWER_*), including a literal
reading of the gate note's rules 2.3 T1-T5 and 5.1 (a)-(c) (AUTHOR_RULE_as_read).  No code changed.  Powers: plea_local,
the governor certificate (POST /accept), the gate key, the courier certificate for readings.  No owner password.
    DIAG_DB=plea25 python -B rv_phase2.py SRC OUT
"""
import secrets
from rv_common import *                                        # noqa: F401,F403

def gen(b, e, aid, nonce):
    return isinstance(e, dict) and e.get('kind') == 'EFFECT_REPORT' and e.get('signer') == b.GATE and C.signed_by(b.GATE, e.get('signature', ''), C.evidence_message(e)) \
        and (e.get('root'), e.get('aid'), e.get('nonce')) == (b.root, aid, nonce)

def AUTHOR_RULE_as_read(b, chain, items, aid, nonce):
    """2.3: set of distinct verdict pairs over authentic reports, any decision.  5.1(a): verdict = report at the one APPLIED
    VERDICT_RECORDED decision.  5.1(c): a report at every RELEASE/RECONCILE decision for the run whose label is not NONE."""
    pairs = sorted({(i['evidence']['claim'], i['evidence'].get('result_digest')) for i in items if gen(b, i.get('evidence'), aid, nonce) and i['evidence']['claim'] in ('EFFECT', 'NO_EFFECT')})
    seqs = {i['seq'] for i in items}
    need = [d['seq'] for d in chain if d['op'][0] in ('RELEASE', 'RECONCILE') and len(d['op']) > 1 and d['op'][1] == aid and d['op'][-1] != 'NONE']
    vr = [d['seq'] for d in chain if d['op'][:2] == ['RECONCILE', aid] and (d['kind'], d['code']) == ('APPLIED', 'VERDICT_RECORDED')]
    return {'T': 'T5 conflict' if len(pairs) > 1 else 'T3/T4 one pair' if pairs else 'T1/T2', 'pairs': len(pairs), 'count_rule_missing_rows': [s for s in need if s not in seqs], 'verdict_recorded_at': vr}

def courier(b, name):
    code, summary = b.s.courier([b.root], 900, name)
    return {'exit': code, 'made': [(m.get('aid', '')[:14], m.get('outcome')) for m in summary.get('made', [])] if isinstance(summary, dict) and 'made' in summary else summary}

def forge(value):
    f = copy.deepcopy(value); f.update(verdict='PASS', reason_code='MET')
    for c in f.get('criteria') or []:
        c.update(met=True, achieved='220', margin='20')
    return f

def att_of(rec, aid):
    return next((x for x in rec.get('attempts', []) if x.get('aid') == aid), None) or {}

b = Bench('RV2')
try:
    s, root = b.s, b.root
    # ======== P1: the only run of a fresh budget: honest FAIL committed; a forged PASS sent with RELEASE (label NONE); the service omits it from the record
    before = b.attempts(); b.r.submit({'material': 'PA66-GF30', 'wall_mm': 3, 'mode': 'normal'}); x = b.newest(before); val = b.local.get_result(root, x['aid'])['value']
    rec0 = b.r.record(); ok0, ch0, _ = C.verify(rec0, s.keys)
    acc = b.accept(('RELEASE', x['aid']), b.report(x['aid'], x['nonce'], 'EFFECT', forge(val)))
    st, ans = b.run_reading(x['aid']); chain = b.chain()
    rec1 = b.r.record(); ok1, ch1, _ = C.verify(rec1, s.keys)
    rec2 = copy.deepcopy(rec1); a2 = att_of(rec2, x['aid']); a2['evidence'] = [i for i in a2['evidence'] if i['seq'] != acc['seq']]
    ok2, ch2, _ = C.verify(rec2, s.keys)
    note('P1. fresh budget, one honest FAIL run; then a forged PASS EFFECT report sent with RELEASE; the record as assembled, and with that report left out',
         record_before=[ok0, [f'{n} {t}: {d}'[:200] for n, t, g, d in ch0 if not g]], release_answer=[acc['kind'], acc['code'], acc['applied'][-1], acc['seq']],
         witness_reading_AUTHOR_RULE=AUTHOR_RULE_as_read(b, chain, ans['evidence'], x['aid'], x['nonce']),
         record_full=[ok1, [f'{n} {t}: {d}'[:200] for n, t, g, d in ch1 if not g]], record_full_AUTHOR_RULE=AUTHOR_RULE_as_read(b, chain, att_of(rec1, x['aid'])['evidence'], x['aid'], x['nonce']),
         record_omitted=[ok2, [f'{n} {t}: {d}'[:200] for n, t, g, d in ch2 if not g]], record_omitted_AUTHOR_RULE=AUTHOR_RULE_as_read(b, chain, a2['evidence'], x['aid'], x['nonce']),
         record_omitted_outcome=a2.get('outcome'), courier=courier(b, 'cP'))

    # ======== P2: a genuine report whose result_digest is 200,000 characters, on a second committed run
    before = b.attempts(); b.r.submit({'material': 'PA66-GF30', 'wall_mm': 2.5, 'mode': 'normal'}); y = b.newest(before)
    big = dict(b.report(y['aid'], y['nonce'], 'EFFECT', None), result_digest='a' * 200000)
    big = dict(big, signature=s.gate._key.sign(C.evidence_message(big)).hex())
    accb = b.accept(('RECONCILE', y['aid']), big); t0 = time.time(); st, ansy = b.run_reading(y['aid']); dt = time.time() - t0
    note('P2. a gate-signed EFFECT report whose signed result_digest is 200,000 characters, sent with RECONCILE to a committed FAIL run',
         answer=[accb['status'], accb['kind'], accb['code']], report_bytes=len(json.dumps(big)), GET_run=[st, len(json.dumps(ansy)), round(dt, 3)],
         authentic_for_scope=[gen(b, i['evidence'], y['aid'], y['nonce']) for i in ansy['evidence']], AUTHOR_RULE=AUTHOR_RULE_as_read(b, b.chain(), ansy['evidence'], y['aid'], y['nonce']),
         mailbox_limit=65536)

    # ======== P3: the cost of one unsettled run, inflated: a CONSUMED run given five UNKNOWN reports of 1,000,000-character digests
    a3, _ = b.synthetic('fat', 'CONSUMED'); answers = []
    for i in range(5):
        r = dict(b.report(a3['aid'], a3['nonce'], 'UNKNOWN', {'i': i}), result_digest=str(i) * 1000000); r = dict(r, signature=s.gate._key.sign(C.evidence_message(r)).hex())
        answers.append(b.accept(('RECONCILE', a3['aid']), r)['code'])
    t0 = time.time(); st, ans3 = b.run_reading(a3['aid']); dt = time.time() - t0
    note('P3. one run kept unsettled (CONSUMED, UNKNOWN reports only) with five reports of 1,000,000-character digests: the cost of re-reading it at every pass',
         answers=answers, phase=b.phase(a3['aid']), GET_run=[st, len(json.dumps(ans3)), round(dt, 3)], honest_GET_run_measured='about 2 KB, 0.03 to 0.10 s (measure.txt)')

    # ======== P4: a conflict with no VERDICT_RECORDED decision: two different EFFECT reports at INTENT_PENDING (AUTHORISED, DENIED), then the run consumed
    a4, _ = b.synthetic('nov', 'INTENT_PENDING')
    r1 = b.accept(('RECONCILE', a4['aid']), b.report(a4['aid'], a4['nonce'], 'EFFECT', {'verdict': 'FAIL'})); r2 = b.accept(('RECONCILE', a4['aid']), b.report(a4['aid'], a4['nonce'], 'EFFECT', {'verdict': 'PASS'}))
    r3 = b.accept(('ACCEPT_INTENT', a4['aid'])); st, ans4 = b.run_reading(a4['aid'])
    note('P4. two different EFFECT reports recorded while the run is INTENT_PENDING; the intent then accepted',
         answers=[[r['kind'], r['code'], (r['applied'] or [None])[-1]] for r in (r1, r2, r3)], phase=b.phase(a4['aid']),
         AUTHOR_RULE=AUTHOR_RULE_as_read(b, b.chain(), ans4['evidence'], a4['aid'], a4['nonce']),
         e25a297_run_outcome=C.run_outcome(b.phase(a4['aid']), ans4['evidence'], None, [b.GATE], root, a4['aid'], a4['nonce']))

    # ======== P5: the null-nonce scope: a released run carrying an authentic EFFECT report
    a5, _ = b.synthetic('rel', 'RESERVED')
    e5 = b.report(a5['aid'], None, 'EFFECT', {'verdict': 'PASS'}); r5 = b.accept(('RECONCILE', a5['aid']), e5)
    f5 = b.accept(('RELEASE', a5['aid']), b.s.gate.fence_report(root, a5['aid']).to_json()); st, ans5 = b.run_reading(a5['aid'])
    with b.local.connect() as conn:
        n5 = conn.execute('SELECT nonce FROM attempts WHERE root_id = %s AND aid = %s', (root, a5['aid'])).fetchone()[0]
    rec5 = b.r.record(); ok5, ch5, _ = C.verify(rec5, s.keys)
    note('P5. a run reserved (no nonce yet): an EFFECT report with a null nonce sent with RECONCILE, then the run released with a fence report',
         answers=[[r5['kind'], r5['code'], r5['applied'][-1]], [f5['kind'], f5['code'], f5['applied'][-1]]], phase=b.phase(a5['aid']), chain_nonce=n5,
         reports=[(i['seq'], (i['evidence'] or {}).get('kind'), (i['evidence'] or {}).get('claim')) for i in ans5['evidence']],
         effect_report_authentic_for_scope_null_nonce=[gen(b, i['evidence'], a5['aid'], None) for i in ans5['evidence']],
         e25a297_run_outcome_on_effect_items=C.run_outcome('EFFECT', ans5['evidence'], {'verdict': 'PASS'}, [b.GATE], root, a5['aid'], None),
         record_failures_for_this_run=[f'{n} {t}: {d}'[:220] for n, t, g, d in ch5 if not g and a5['aid'] in d], record_outcome=att_of(rec5, a5['aid']).get('outcome'),
         record_carries=[(i['seq'], i['evidence'].get('claim')) for i in att_of(rec5, a5['aid']).get('evidence', [])])
finally:
    save('rv_phase2.json'); b.stop()
