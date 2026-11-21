"""Design gate, part C (21 November 2026): the release-decision path for reports.  The store keeps a report with a RELEASE
decision as well as with a RECONCILE.  Can a gate-signed verdict report be put on record that way, is it then believed,
does the chain show it to a reader that follows a cursor, and what do the Step 2 rules make of it?  No code is changed.
DIAG_DB=<fresh database> python gate_release.py SRC OUT"""
import psycopg
from gate_common import *                                      # noqa: F401,F403

OWNER = f'postgresql://plea:plea@127.0.0.1:5432/{DB}'


def forge(value):
    f = copy.deepcopy(value); f.update(verdict='PASS', reason_code='MET', basis='limited by the continuous-use rating of PA66-GF30: 220 C')
    for c in f['criteria']:
        c.update(met=True, achieved='220', margin='20')
    return f


def evidence_rows(root):
    with psycopg.connect(OWNER) as conn:
        return [dict(aid=a, seq=s_, derived=d, claim=(e or {}).get('claim') if isinstance(e, dict) else None, kind=(e or {}).get('kind') if isinstance(e, dict) else type(e).__name__)
                for a, s_, d, e in conn.execute('SELECT aid, seq, derived, evidence FROM evidence WHERE root_id = %s ORDER BY seq', (root,)).fetchall()]


def step2_view(b, a, stored_value, upto=None):
    """What the Step 2 rules (section 6) make of one run, from the witness's readings alone."""
    st, ans, reports = b.reports_of(a); chain = b.chain(); N = upto or (chain[-1]['seq'] if chain else 0)
    ops = {d['seq']: d for d in chain}
    recon_auth = [d for d in chain if d['op'][:2] == ['RECONCILE', a['aid']] and d['op'][-1] == 'AUTHORISED' and d['seq'] <= N]
    at_auth = lambda x: x['seq'] in {d['seq'] for d in recon_auth} and ops[x['seq']]['op'][2] == x['claim']
    count_ok = all(any(x['seq'] == d['seq'] and x['authentic'] and x['claim'] == d['op'][2] for x in reports) for d in recon_auth) and all(at_auth(x) for x in reports if x['seq'] <= N)
    D = verdict_pairs(reports)
    phase = b.phase(a['aid'])                                 # the chained phase, from the attempts table (run 1 took it from the reading, which does not carry it under that name)
    return {'GET /run status': st, 'phase': phase, 'reports the reading gives': [dict(x, decision=ops[x['seq']]['op'][:1] + ops[x['seq']]['op'][2:] + [ops[x['seq']]['kind'], ops[x['seq']]['code']]) for x in reports],
            'e25a297 run_outcome with the result given': C.run_outcome(phase, (ans or {}).get('evidence') or [], stored_value, [b.GATE], b.root, a['aid'], a['nonce']),
            'STEP2 count rule holds (every report at an AUTHORISED RECONCILE of its verdict)': count_ok,
            'STEP2 set D of distinct verdict pairs': D, 'STEP2 conflict': len(D) > 1,
            'STEP2 finding': 'CONFLICT' if len(D) > 1 else ('NOT OBSERVED' if not count_ok else 'one signed result' if D else 'no signed result')}


def cursor_sees(b, cursor, aid):
    new = b.chain(after=cursor)
    return {'new decisions after the cursor': len(new), 'RELEASE or RECONCILE decisions naming the run among them': [[d['seq']] + d['op'][:1] + d['op'][2:] + [d['kind'], d['code']] for d in new if d['op'][0] in ('RELEASE', 'RECONCILE') and d['op'][1] == aid],
            'the run is in the set a cursor-following reader re-reads': any(d['op'][0] in ('RELEASE', 'RECONCILE') and d['op'][1] == aid for d in new)}


def head(b):
    ch = b.chain(); return ch[-1]['seq'] if ch else 0


def record_view(b, a):
    try:
        rec = b.r.record(); ok, checks, summary = C.verify(rec, b.s.keys)
    except Exception as exc:
        return {'record could not be made or checked': f'{type(exc).__name__}: {str(exc)[:200]}'}
    att = next((x for x in rec.get('attempts', []) if x.get('aid') == a['aid']), None) or {}
    return {'record verifies at e25a297': ok, 'checks that fail': [f'{n} {t}: {d}'[:260] for n, t, good, d in checks if not good], 'outcome the record gives the run': att.get('outcome'),
            'reports the record carries for the run': [{'seq': i['seq'], 'claim': i['evidence'].get('claim'), 'digest': (i['evidence'].get('result_digest') or '')[:16]} for i in att.get('evidence') or []]}


def courier(b, name):
    code, summary = b.s.courier([b.root], 900, name)
    return {'exit': code, 'made': [(m.get('aid', '')[:12], m.get('outcome')) for m in summary.get('made', [])] if isinstance(summary, dict) and 'made' in summary else summary}


b = Bench('GR')
try:
    s, root = b.s, b.root

    def withheld_submit(design):
        client = verify_client.Client(b.r.cfg); held = []; client.store.put_result = lambda root_, aid_, stored: held.append(stored)
        before = b.attempts(); code, out = client.submit(design); return b.newest(before), VT.head(out), held[0]

    # ---------------------------------------------------------------- C1: a verdict report put on record with a RELEASE, after the run is final
    x, line_x, held_x = withheld_submit({'material': 'PA66-GF30', 'wall_mm': 2.5, 'mode': 'normal'}); forged = forge(held_x['value'])
    cur = head(b); rep = b.report(x['aid'], x['nonce'], 'EFFECT', forged); acc = b.accept(('RELEASE', x['aid']), rep)
    note('C1. run X is final (the gate host signed FAIL, recorded).  A gate-signed EFFECT report for a forged PASS result is sent with a RELEASE',
         client_was_told=line_x, the_witness_answered=acc, evidence_rows_in_the_store=evidence_rows(root), cursor=cursor_sees(b, cur, x['aid']),
         with_no_stored_result=step2_view(b, x, None), courier_while_the_result_is_withheld=courier(b, 'c1'))
    b.local.put_result(root, x['aid'], {'outcome': 'value', 'value': forged, 'nonce': x['nonce'], 'report': rep})
    note('C1b. the forged PASS result is then stored as the run\'s result', with_the_forged_result=step2_view(b, x, forged), courier=courier(b, 'c1'), record=record_view(b, x))

    # ---------------------------------------------------------------- C2: the report planted before the verdict, at START, with a RELEASE
    planted = {}
    orig_apply = Store.apply
    def planting_apply(self, root_, op):
        if op[0] == 'START' and 'aid' not in planted:
            planted.update(aid=op[1], nonce=op[2], cursor=head(b))
            planted['report'] = b.report(op[1], op[2], 'EFFECT', forged); planted['answer'] = b.accept(('RELEASE', op[1]), planted['report'])
            planted['phase after'] = b.phase(op[1]); planted['seen by cursor'] = cursor_sees(b, planted['cursor'], op[1])
        return orig_apply(self, root_, op)
    Store.apply = planting_apply
    try:
        y, line_y, held_y = withheld_submit({'material': 'PA66-GF30', 'wall_mm': 3, 'mode': 'normal'})
    finally:
        Store.apply = orig_apply
    note('C2. run Y: before its START the same kind of report is sent with a RELEASE; the run then goes on and the gate host signs FAIL',
         planted={k: v for k, v in planted.items() if k != 'report'}, client_was_told=line_y, gate_host_verdict=held_y['value']['verdict'], with_no_stored_result=step2_view(b, y, None))
    b.local.put_result(root, y['aid'], {'outcome': 'value', 'value': forged, 'nonce': y['nonce'], 'report': planted['report']})
    note('C2b. the forged PASS result is stored for run Y', with_the_forged_result=step2_view(b, y, forged), courier=courier(b, 'c2'), record=record_view(b, y))

    # ---------------------------------------------------------------- C3: an honest run for comparison
    cur = head(b); z, line_z, held_z = withheld_submit({'material': 'PA66-GF30', 'wall_mm': 3.5, 'mode': 'normal'}); b.local.put_result(root, z['aid'], held_z)
    note('C3. run Z, honest: one report, one decision', cursor=cursor_sees(b, cur, z['aid']), view=step2_view(b, z, held_z['value']), record=record_view(b, z))

    rows = evidence_rows(root); chain = b.chain(); by = {d['seq']: d for d in chain}
    note('C4. every report row in the store against the chain, for this budget', report_rows=len(rows),
         every_row_sits_at_a_RELEASE_or_RECONCILE_decision_for_its_run=all(by.get(r_['seq'], {}).get('op', [None, None])[0] in ('RELEASE', 'RECONCILE') and by[r_['seq']]['op'][1] == r_['aid'] for r_ in rows),
         rows=[dict(r_, decision=by[r_['seq']]['op'][:1] + by[r_['seq']]['op'][2:] + [by[r_['seq']]['kind'], by[r_['seq']]['code']]) for r_ in rows])
finally:
    b.stop()

# -------------------------------------------------------------------- C5..C7: every phase and every kind of evidence, on attempts that are never run
b = Bench('GS')
try:
    root = b.root; value = {'verdict': 'PASS', 'note': 'a result of the service\'s choosing'}
    other = type(b.s.gate)() if True else None
    table = []
    for phase in ('RESERVING', 'RESERVED', 'TOKEN', 'INTENT_PENDING', 'CONSUMED'):
        for opname in ('RELEASE', 'RECONCILE'):
            a, steps = b.synthetic(f'{opname[:3].lower()}-{phase.lower()}', upto=phase); cur = head(b)
            rep = b.report(a['aid'], a['nonce'], 'EFFECT', value); acc = b.accept((opname, a['aid']), rep); st, ans, reports = b.reports_of(a)
            table.append({'phase before': phase, 'sent with': opname, 'answer': [acc['status'], acc['kind'], acc['code']], 'label derived': (acc['applied'] or [None])[-1], 'phase after': b.phase(a['aid']),
                          'report kept and given by GET /run': len(reports), 'authentic for the run\'s scope now': [x['authentic'] for x in reports], 'seen by a cursor': cursor_sees(b, cur, a['aid'])['the run is in the set a cursor-following reader re-reads']})
    note('C5. a gate-signed EFFECT report sent with RELEASE and with RECONCILE at each phase before a verdict', table=table)

    # a report recorded before its attempt exists, then the attempt made with the nonce the report names
    out = {}
    for opname in ('RELEASE', 'RECONCILE'):
        aid, nonce = f'early-{opname.lower()}', f'n-early-{opname.lower()}'; cur = head(b)
        rep = b.report(aid, nonce, 'EFFECT', value); acc = b.accept((opname, aid), rep); st0, ans0 = b.run_reading(aid)
        a = {'aid': aid, 'nonce': nonce}
        d, _ = b.local.apply(root, ('RESERVE', aid, 'key-' + aid)); b.accept(('ACCEPT_RESERVATION', aid)); b.local.apply(root, ('TOKEN', aid)); b.local.apply(root, ('START', aid, nonce)); b.accept(('ACCEPT_INTENT', aid))
        honest = {'verdict': 'FAIL', 'note': 'what an honest gate host would have signed'}
        acc2 = b.accept(('RECONCILE', aid), b.report(aid, nonce, 'EFFECT', honest))
        out[opname] = {'answer to the early report': [acc['status'], acc['kind'], acc['code'], (acc['applied'] or [None])[-1]], 'GET /run before the attempt exists': st0, 'cursor after the early report': cursor_sees(b, cur, aid),
                       'answer to the honest verdict': [acc2['kind'], acc2['code']], 'with the planted PASS result given': step2_view(b, a, value), 'with the honest FAIL result given': step2_view(b, a, honest)}
    note('C6. a report recorded before its attempt exists; the attempt is then made, and an honest FAIL recorded', by_operation=out)

    # every kind of evidence the witness can be sent (PO-8)
    kinds = []
    a, _ = b.synthetic('kinds')
    wrong_nonce = b.report(a['aid'], 'another-nonce', 'EFFECT', value); wrong_run = b.report('another-run', a['nonce'], 'EFFECT', value)
    stranger = other.effect_report(root, a['aid'], a['nonce'], 'EFFECT', value).to_json()
    tampered = dict(b.report(a['aid'], a['nonce'], 'EFFECT', value), result_digest='0' * 64)
    fence = b.s.gate.fence_report(root, a['aid']).to_json()
    cases = [('no evidence at all', None), ('text that is not a report', 'not a report'), ('an empty object', {}), ('a report signed by a key that is not the gate\'s', stranger), ('a gate report with its digest altered', tampered),
             ('a gate report for another nonce', wrong_nonce), ('a gate report for another run', wrong_run), ('a gate fence report', fence),
             ('a gate UNKNOWN report', b.report(a['aid'], a['nonce'], 'UNKNOWN', {'error': 'x'})), ('a gate NO_EFFECT report', b.report(a['aid'], a['nonce'], 'NO_EFFECT', None)),
             ('a gate EFFECT report after NO_EFFECT', b.report(a['aid'], a['nonce'], 'EFFECT', value)), ('the NO_EFFECT report again', b.report(a['aid'], a['nonce'], 'NO_EFFECT', None))]
    for opname in ('RECONCILE', 'RELEASE'):
        for name, ev in cases:
            before = len(b.reports_of(a)[2]); acc = b.accept((opname, a['aid']), ev); after = len(b.reports_of(a)[2])
            kinds.append({'sent with': opname, 'evidence': name, 'answer': [acc['status'], acc['kind'], acc['code']], 'operation recorded': acc['applied'], 'a report row was added': after - before, 'phase after': b.phase(a['aid'])})
    st, ans, reports = b.reports_of(a)
    note('C7. every kind of evidence, sent with RECONCILE and then with RELEASE, to one attempt that begins CONSUMED', table=kinds, final_reading=step2_view(b, a, None),
         decisions_without_a_report_row=[k['evidence'] + ' / ' + k['sent with'] for k in kinds if k['a report row was added'] == 0 and k['answer'][0] == 200])
    rows = evidence_rows(root); chain = b.chain(); by = {d['seq']: d for d in chain}
    note('C8. every report row in the store against the chain, for this budget', report_rows=len(rows), decisions=len(chain),
         every_row_sits_at_a_RELEASE_or_RECONCILE_decision_for_its_run=all(by.get(r_['seq'], {}).get('op', [None, None])[0] in ('RELEASE', 'RECONCILE') and by[r_['seq']]['op'][1] == r_['aid'] for r_ in rows),
         RELEASE_or_RECONCILE_decisions_with_no_row=[[d['seq']] + d['op'] + [d['kind'], d['code']] for d in chain if d['op'][0] in ('RELEASE', 'RECONCILE') and d['seq'] not in {r_['seq'] for r_ in rows}])
finally:
    save('gate_release.json'); b.stop()
