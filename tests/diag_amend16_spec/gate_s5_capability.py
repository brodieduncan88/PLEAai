"""Final specification round, 21 November 2026: which capability does S-5 (and S-1) need?
Two adversaries, kept apart:
  CAP-DB   the service's database role, its client certificate, and every report an HONEST gate host has signed.
           It does NOT hold the gate's signing key.  It can replay a genuine report anywhere it likes.
  CAP-KEY  the same, and the gate's signing key (the property file's assumption; blocker B-3).
Asked: with CAP-DB alone, can a run whose honest gate host signed FAIL be made to read PASS at e25a297, by replaying a
genuine PASS report from another attempt of the budget, or from another budget?  And the control: with CAP-KEY.
No code is changed.  DIAG_DB=<fresh database> python gate_s5_capability.py SRC OUT"""
from gate_common import *                                      # noqa: F401,F403
from plea_gateway import GateHostClient, Governor              # noqa: E402

b = Bench('GC')
try:
    s, root = b.s, b.root
    card2 = VT.draft(); env2 = s.baseline(VT.CASE, card2, alongside_reason='a second budget at the same witness'); root2 = VT.B.root_for(env2['card'])
    cfg2 = s.client_config(b.r.ws.parent / 'workspace2', env2['baseline_sha256'])
    cap = {}
    orig_call = Governor._call_host
    def capturing(self, aid, nonce, receipt, admission, tool, arguments):
        cap[aid] = dict(root=self.root, nonce=nonce, receipt=receipt, admission=admission, tool=tool, arguments=arguments); return orig_call(self, aid, nonce, receipt, admission, tool, arguments)
    Governor._call_host = capturing

    def attempts_of(r_):
        with b.local.connect() as conn:
            return [dict(aid=a, phase=p, nonce=n) for a, p, n in conn.execute('SELECT aid, phase, nonce FROM attempts WHERE root_id = %s', (r_,)).fetchall()]

    def submit(cfg, r_, design, withhold):
        client = verify_client.Client(cfg); held = []
        if withhold:
            client.store.put_result = lambda root_, aid_, stored: held.append(stored)
        before = {a['aid'] for a in attempts_of(r_)}; code, out = client.submit(design)
        new = [a for a in attempts_of(r_) if a['aid'] not in before]; assert len(new) == 1, new
        return new[0], VT.head(out), (held[0] if held else b.local.get_result(r_, new[0]['aid']))

    def reports(r_, a):
        st, ans = b.call(f'/run?root={urllib.parse.quote(r_, safe="")}&aid={urllib.parse.quote(a["aid"], safe="")}', b.cour)
        out = []
        for item in (ans or {}).get('evidence') or []:
            e = item['evidence']
            ok = isinstance(e, dict) and e.get('kind') == 'EFFECT_REPORT' and e.get('signer') == b.GATE and C.signed_by(b.GATE, e.get('signature', ''), C.evidence_message(e))
            out.append({'seq': item['seq'], 'derived': item.get('derived'), 'claim': e.get('claim') if isinstance(e, dict) else None, 'digest': (e.get('result_digest') or '')[:10] if isinstance(e, dict) else None,
                        'signed by the gate key': bool(ok), 'names this budget, run and nonce': bool(ok) and (e.get('root'), e.get('aid'), e.get('nonce')) == (r_, a['aid'], a['nonce']),
                        'names': [('this budget' if e.get('root') == r_ else 'ANOTHER budget'), ('this run' if e.get('aid') == a['aid'] else 'ANOTHER run'), ('this nonce' if e.get('nonce') == a['nonce'] else 'ANOTHER nonce')] if isinstance(e, dict) else None})
        return ans, out

    def phase_of(r_, aid):
        return next((x['phase'] for x in attempts_of(r_) if x['aid'] == aid), None)

    def outcome(r_, a, value):
        ans, reps = reports(r_, a)
        return C.run_outcome(phase_of(r_, a['aid']), (ans or {}).get('evidence') or [], value, [b.GATE], r_, a['aid'], a['nonce'])

    def accept(r_, op, evidence):
        st, ans = b.call('/accept', b.gov, 'POST', {'root': r_, 'op': list(op), 'evidence': evidence})
        return [st, (ans or {}).get('kind'), (ans or {}).get('code'), ((ans or {}).get('applied') or [None])[-1]]

    def courier(r_, name, wait=900):
        code, summary = s.courier([r_], wait, name)
        return {'exit': code, 'made': [(m.get('aid', '')[:12], m.get('outcome')) for m in summary.get('made', [])] if isinstance(summary, dict) and 'made' in summary else summary}

    def genuine_report(r_, a):
        ans, _ = reports(r_, a); return next(i['evidence'] for i in ans['evidence'] if i['evidence'].get('claim') == 'EFFECT')

    # ------------------------------------------------------------ honest runs: the genuine reports the service holds
    PASSING = {'material': 'PPS-GF40', 'wall_mm': 2.5, 'mode': 'normal'}
    p1, line_p1, res_p1 = submit(b.r.cfg, root, PASSING, False); rep_p1 = genuine_report(root, p1)
    p2, line_p2, res_p2 = submit(cfg2, root2, {'material': 'PPS-GF40', 'wall_mm': 3, 'mode': 'normal'}, False); rep_p2 = genuine_report(root2, p2)
    note('S0. the genuine PASS reports an honest gate host signed (the service holds them; it holds no gate key in CAP-DB)',
         same_budget_other_attempt={'run': p1['aid'][:14], 'client told': line_p1, 'stored verdict': res_p1['value']['verdict']},
         other_budget={'run': p2['aid'][:14], 'client told': line_p2, 'stored verdict': res_p2['value']['verdict'], 'budgets differ': root != root2})

    # ------------------------------------------------------------ CAP-DB: replay to a run whose honest gate host signed FAIL
    table = []
    for label, replayed, value, op in (('a genuine PASS report of another attempt of this budget, sent with RECONCILE', rep_p1, res_p1['value'], 'RECONCILE'),
                                       ('the same, sent with RELEASE', rep_p1, res_p1['value'], 'RELEASE'),
                                       ('a genuine PASS report of another budget, sent with RECONCILE', rep_p2, res_p2['value'], 'RECONCILE'),
                                       ('the same, sent with RELEASE', rep_p2, res_p2['value'], 'RELEASE')):
        wall = 2 + 0.25 * (len(table) + 1)
        f, line_f, held_f = submit(b.r.cfg, root, {'material': 'PA66-GF30', 'wall_mm': wall, 'mode': 'normal'}, True)
        ans = accept(root, (op, f['aid']), replayed); _, reps = reports(root, f)
        before_store = outcome(root, f, None)
        try:
            b.local.put_result(root, f['aid'], {'outcome': 'value', 'value': value, 'nonce': f['nonce'], 'report': replayed}); stored = 'accepted'
        except Exception as exc:
            stored = 'REFUSED: ' + str(exc).splitlines()[0][:120]
        got = (b.local.get_result(root, f['aid']) or {}).get('value')
        table.append({'replayed': label, 'the failing run': f['aid'][:14], 'client was told': line_f, 'witness answer [status, kind, code, label]': ans,
                      'reports the reading now gives': [(x['seq'], x['claim'], x['digest'], x['derived'], x['names'], 'COUNTS for this run' if x['names this budget, run and nonce'] else 'does not count') for x in reps],
                      'e25a297 outcome while the result is withheld': before_store, 'storing the PASS result of the other run': stored,
                      'e25a297 outcome with that PASS result stored': outcome(root, f, got), 'reads PASS': outcome(root, f, got) == 'PASS', 'courier': courier(root, f'db{len(table)}')})
    note('S1. CAP-DB: a genuine PASS report replayed onto a run whose honest gate host signed FAIL, the FAIL result withheld, the other run\'s PASS result stored', table=table,
         any_reads_PASS=any(r_['reads PASS'] for r_ in table))

    # early: replayed before the failing run's START
    planted = {}
    orig_apply = Store.apply
    def planting_apply(self, root_, op):
        if op[0] == 'START' and 'aid' not in planted:
            planted.update(aid=op[1], nonce=op[2]); planted['RELEASE'] = accept(root, ('RELEASE', op[1]), rep_p1); planted['RECONCILE'] = accept(root, ('RECONCILE', op[1]), rep_p1)
        return orig_apply(self, root_, op)
    Store.apply = planting_apply
    try:
        f, line_f, held_f = submit(b.r.cfg, root, {'material': 'PA66-GF30', 'wall_mm': 3.75, 'mode': 'normal'}, True)
    finally:
        Store.apply = orig_apply
    b.local.put_result(root, f['aid'], {'outcome': 'value', 'value': res_p1['value'], 'nonce': f['nonce'], 'report': rep_p1}); got = (b.local.get_result(root, f['aid']) or {}).get('value')
    _, reps = reports(root, f)
    note('S2. CAP-DB: the same replay made before the failing run\'s START', answers={k: v for k, v in planted.items() if k in ('RELEASE', 'RECONCILE')}, client_was_told=line_f,
         reports=[(x['seq'], x['claim'], x['digest'], x['derived'], x['names'], 'COUNTS for this run' if x['names this budget, run and nonce'] else 'does not count') for x in reps],
         e25a297_outcome_with_the_PASS_result_stored=outcome(root, f, got), courier=courier(root, 'db-early'))

    # a crafted attempt in the other budget that takes the run name and nonce of the genuine PASS report
    crafted = {'aid': p1['aid'], 'nonce': p1['nonce']}; steps = []
    d, _ = b.local.apply(root2, ('RESERVE', crafted['aid'], 'crafted-key')); steps.append(('RESERVE', d.kind, d.code))
    steps.append(('ACCEPT_RESERVATION', accept(root2, ('ACCEPT_RESERVATION', crafted['aid']), None)[1:3]))
    d, _ = b.local.apply(root2, ('TOKEN', crafted['aid'])); steps.append(('TOKEN', d.kind, d.code))
    d, _ = b.local.apply(root2, ('START', crafted['aid'], crafted['nonce'])); steps.append(('START', d.kind, d.code))
    steps.append(('ACCEPT_INTENT', accept(root2, ('ACCEPT_INTENT', crafted['aid']), None)[1:3]))
    ans = accept(root2, ('RECONCILE', crafted['aid']), rep_p1); _, reps = reports(root2, crafted)
    note('S3. CAP-DB: an attempt made in the OTHER budget with the same run name and nonce as the genuine PASS report, and that report sent to it', steps=steps, witness_answer=ans,
         phase=phase_of(root2, crafted['aid']), reports=[(x['seq'], x['claim'], x['derived'], x['names'], 'COUNTS' if x['names this budget, run and nonce'] else 'does not count') for x in reps],
         e25a297_outcome_given_the_PASS_result=outcome(root2, crafted, res_p1['value']))

    # the honest gate host, asked again and asked for something else
    f, line_f, held_f = submit(b.r.cfg, root, {'material': 'PA66-GF30', 'wall_mm': 4, 'mode': 'normal'}, True); c = cap[f['aid']]
    tls = TLS.TLSClient(s.pki['ca'], *s.pki['governor']); host = GateHostClient(f"https://127.0.0.1:{s.ports['host']}", tls=tls, public_key=b.GATE)
    again = host.run(root, f['aid'], f['nonce'], c['receipt'], c['tool'], c['arguments'], admission=c['admission'])
    first = genuine_report(root, f)
    def refused(fn):
        try:
            out = fn(); return {'answered': True, 'claim': out['report'].get('claim'), 'digest': out['report'].get('result_digest', '')[:10], 'repeat': out.get('repeat')}
        except Exception as exc:
            return {'answered': False, 'refusal': f'{type(exc).__name__}: {str(exc)[:160]}'}
    pc = cap[p1['aid']]
    other_args = refused(lambda: host.run(root, f['aid'], f['nonce'], c['receipt'], pc['tool'], pc['arguments'], admission=c['admission']))
    other_nonce = refused(lambda: host.run(root, f['aid'], p1['nonce'], c['receipt'], pc['tool'], pc['arguments'], admission=c['admission']))
    others_receipts = refused(lambda: host.run(root, f['aid'], p1['nonce'], pc['receipt'], pc['tool'], pc['arguments'], admission=pc['admission']))
    again_send = accept(root, ('RECONCILE', f['aid']), again['report'])
    note('S4. CAP-DB: the honest gate host asked again for the failing run, and asked to run a passing design under the failing run\'s name', client_was_told=line_f,
         asked_again={'repeat': again.get('repeat'), 'the same report, byte for byte': again['report'] == first, 'claim': again['report'].get('claim')},
         the_same_report_sent_to_the_witness_again=again_send,
         a_passing_design_with_the_failing_run_s_nonce_and_receipts=other_args, a_passing_design_with_its_own_nonce_and_the_failing_run_s_receipts=other_nonce,
         a_passing_design_with_its_own_nonce_and_its_own_run_s_receipts=others_receipts)

    # ------------------------------------------------------------ CAP-KEY: the control
    f, line_f, held_f = submit(b.r.cfg, root, {'material': 'PA66-GF30', 'wall_mm': 3.3, 'mode': 'normal'}, True)
    forged = copy.deepcopy(held_f['value']); forged.update(verdict='PASS', reason_code='MET')
    for crit in forged.get('criteria', []):
        crit.update(met=True, achieved='220', margin='20')
    rep_forged = b.report(f['aid'], f['nonce'], 'EFFECT', forged)                 # signed with the gate's key: CAP-KEY only
    ans = accept(root, ('RELEASE', f['aid']), rep_forged); b.local.put_result(root, f['aid'], {'outcome': 'value', 'value': forged, 'nonce': f['nonce'], 'report': rep_forged})
    _, reps = reports(root, f)
    note('S5. CAP-KEY (control): a report signed with the gate\'s key over a forged PASS result for the failing run itself, sent with RELEASE; the forged result stored', client_was_told=line_f, witness_answer=ans,
         reports=[(x['seq'], x['claim'], x['digest'], x['derived'], 'COUNTS for this run' if x['names this budget, run and nonce'] else 'does not count') for x in reps],
         e25a297_outcome=outcome(root, f, forged), courier=courier(root, 'key'))
    key_run = f['aid'][:12]
    final = courier(root, 'final', 0)                                              # a courier that waits no longer for a result
    names = {r_['the failing run'][:12]: 'CAP-DB replay' for r_ in table}; names[key_run] = 'CAP-KEY forged report'; names[p1['aid'][:12]] = 'the honest PASS run'
    note('S6. a courier that waits no longer for a stored result (waiting time 0), over the whole budget: what it makes for each run',
         made=[(aid, kind, names.get(aid, 'another run of this test')) for aid, kind in final['made']] if isinstance(final.get('made'), list) else final,
         the_CAP_KEY_run_has_a_notice=any(aid == key_run for aid, _ in final['made']) if isinstance(final.get('made'), list) else None,
         every_CAP_DB_replay_run_has_a_notice=all(any(aid == r_['the failing run'][:12] for aid, _ in final['made']) for r_ in table) if isinstance(final.get('made'), list) else None)
finally:
    Governor._call_host = orig_call
    save('gate_s5_capability.json'); b.stop()
