"""Diagnostic, 21 November 2026: does the witness's existing reading show both gate-signed reports of a run whose verdict
was replaced, can the conflict be told from what the courier and the record's checker are already given, and when can a
report be kept from view?  Development evidence only; no code of e25a297 is changed.  The predicates below are this
harness's, to show what the existing data allows; they are not proposed code.

    DIAG_DB=<fresh database> python visibility_check.py SRC OUT
"""
import copy, json, os, pathlib, sys, time, urllib.error, urllib.parse, urllib.request

SRC, OUT = sys.argv[1], pathlib.Path(sys.argv[2]); DB = os.environ['DIAG_DB']
for role, pw, var in (('plea_local', 'local', 'PLEA_LOCAL_DSN'), ('plea_witness', 'witness', 'PLEA_WITNESS_DSN'), ('plea_control', 'control', 'PLEA_CONTROL_DSN')):
    os.environ[var] = f'postgresql://{role}:{pw}@127.0.0.1:5432/{DB}'
sys.path[:0] = [SRC + '/tests', SRC, SRC + '/verify']
import verify_tests as VT                                   # noqa: E402
import check_record as C                                    # noqa: E402
import verify_client                                        # noqa: E402
from plea_gateway import Store, tls as TLS                  # noqa: E402
from plea_gateway.governor import Governor                  # noqa: E402
import psycopg                                              # noqa: E402

LOG = {'when': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'database': DB, 'steps': []}


def note(name, **kw):
    LOG['steps'].append(dict(step=name, **kw)); print(f'--- {name}'); [print(f'    {k}: {json.dumps(v, default=str)[:1100]}') for k, v in kw.items()]; sys.stdout.flush()


def first_line(exc):
    return f'{type(exc).__name__}: {str(exc).splitlines()[0][:160]}'


r = VT.Run('VIS'); s = r.s
try:
    root = VT.B.root_for(r.env['card']); local = Store(os.environ['PLEA_LOCAL_DSN']); url = f"https://127.0.0.1:{s.ports['witness']}"
    gov, cour = s.pki['governor'], s.pki['courier']; q = urllib.parse.quote(root, safe=''); GATE = s.keys['gate']

    def call(path, cert, method='GET', body=None):
        ctx = TLS.TLSClient(s.pki['ca'], *cert).context()
        req = urllib.request.Request(url + path, data=None if body is None else json.dumps(body).encode(), method=method, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=70, context=ctx) as resp:
                return resp.status, json.loads(resp.read() or b'null')
        except urllib.error.HTTPError as exc:
            return exc.code, None

    def sql(role, statement, params=()):
        pw = {'plea_local': 'local', 'plea_witness': 'witness', 'plea_control': 'control', 'plea': 'plea'}[role]
        try:
            with psycopg.connect(f'postgresql://{role}:{pw}@127.0.0.1:5432/{DB}') as conn:
                cur = conn.execute(statement, params); out = cur.fetchall() if cur.description else cur.rowcount; conn.commit()
                return {'ok': True, 'result': out}
        except Exception as exc:
            return {'ok': False, 'error': first_line(exc)}

    def attempts():
        with local.connect() as conn:
            return [dict(aid=a, phase=p, nonce=n) for a, p, n in conn.execute('SELECT aid, phase, nonce FROM attempts WHERE root_id = %s', (root,)).fetchall()]

    def newest(before):
        new = [a for a in attempts() if a['aid'] not in {b['aid'] for b in before}]; assert len(new) == 1, new; return new[0]

    def chain_as_courier():                                    # every decision, by the witness's reading, with the courier's certificate
        rows, after = [], 0
        while True:
            st, page = call(f'/chain?root={q}&after={after}&limit=200', cour); got = page['rows']
            if not got:
                return rows
            rows += got; after = got[-1]['seq']

    def view(a):
        """What the courier is given for one run by the readings that exist, and what can be told from it."""
        st, ans = call(f'/run?root={q}&aid={urllib.parse.quote(a["aid"], safe="")}', cour)
        reports = []
        for item in ans.get('evidence') or []:
            e = item['evidence']
            genuine = e.get('signer') == GATE and C.signed_by(GATE, e.get('signature', ''), C.evidence_message(e)) and (e.get('root'), e.get('aid'), e.get('nonce')) == (root, a['aid'], a['nonce'])
            reports.append({'seq': item['seq'], 'claim': e.get('claim'), 'digest': (e.get('result_digest') or '')[:16], 'signed by the gate key, for this budget, run and nonce': bool(genuine)})
        stored = ans.get('result'); value = stored.get('value') if isinstance(stored, dict) and stored.get('outcome', 'value') == 'value' else None
        reconciles = [{'seq': d['seq'], 'kind': d['kind'], 'code': d['code'], 'verdict in the op': d['op'][2]} for d in chain_as_courier() if d['op'][:2] == ['RECONCILE', a['aid']]]
        effect_digests = sorted({x['digest'] for x in reports if x['claim'] == 'EFFECT' and x['signed by the gate key, for this budget, run and nonce']})
        return {'GET /run status': st, 'reports in the answer': reports, 'stored verdict': value.get('verdict') if isinstance(value, dict) else None,
                'stored value digest': C.sha(C.canonical(value))[:16] if isinstance(value, dict) else None,
                'RECONCILE decisions for the run in the chain': reconciles,
                'check_record.run_outcome (what the courier concludes)': C.run_outcome(a['phase'], ans.get('evidence') or [], value, [GATE], root, a['aid'], a['nonce']),
                'PREDICATE two different digests among genuine EFFECT reports': len(effect_digests) > 1,
                'PREDICATE fewer reports than RECONCILE decisions in the chain': len(reports) < len(reconciles),
                'each report sits at the seq of a RECONCILE decision for this run': all(any(x['seq'] == d['seq'] for d in reconciles) for x in reports)}

    def courier(name, stall=900):
        code, summary = s.courier([root], stall, name)
        return {'exit': code, 'made': [(m.get('aid'), m.get('outcome')) for m in summary.get('made', [])] if isinstance(summary, dict) else summary}

    def forge(value):
        f = copy.deepcopy(value); f.update(verdict='PASS', reason_code='MET', basis='limited by the continuous-use rating of PA66-GF30: 220 C')
        for c in f['criteria']:
            c.update(met=True, achieved='220', margin='20')
        return f

    def second_report(a, value):
        rep = s.gate.effect_report(root, a['aid'], a['nonce'], 'EFFECT', value).to_json()
        st, ans = call('/accept', gov, 'POST', {'root': root, 'op': ['RECONCILE', a['aid']], 'evidence': rep})
        return rep, {'status': st, 'kind': ans.get('kind'), 'code': ans.get('code'), 'seq': ans.get('seq')}

    def withheld_submit(design):
        client = verify_client.Client(r.cfg); held = []; client.store.put_result = lambda root_, aid_, stored: held.append(stored)
        b = attempts(); code, out = client.submit(design); return newest(b), VT.head(out), held[0]

    def record_view(a):
        rec = r.record(); ok, checks, summary = C.verify(rec, s.keys)
        att = next((x for x in rec.get('attempts', []) if x.get('aid') == a['aid']), None) or {}
        ev = att.get('evidence') or []
        digests = sorted({(i['evidence'].get('result_digest') or '')[:16] for i in ev if i['evidence'].get('claim') == 'EFFECT'})
        return {'record verifies': ok, 'checks that fail': [f'{n} {t}: {d}'[:200] for n, t, good, d in checks if not good], 'outcome the record gives the run': att.get('outcome'),
                'reports the record carries for the run': [{'seq': i['seq'], 'claim': i['evidence'].get('claim'), 'digest': (i['evidence'].get('result_digest') or '')[:16]} for i in ev],
                'PREDICATE two different digests among the record\'s EFFECT reports': len(digests) > 1}

    # ------------------------------------------------------------------ V1, V2: the replacement, as the witness's readings show it
    x, line_x, held_x = withheld_submit({'material': 'PA66-GF30', 'wall_mm': 2.5, 'mode': 'normal'})
    note('V1. the gate host signed FAIL, the witness recorded it, the result is withheld', attempt=x, client_was_told=line_x, gate_host_verdict=held_x['value']['verdict'], view=view(x), courier_900s=courier('v-wait'))
    forged = forge(held_x['value']); rep2, acc = second_report(x, forged)
    local.put_result(root, x['aid'], {'outcome': 'value', 'value': forged, 'nonce': x['nonce'], 'report': rep2})
    note('V2. a second report over a forged PASS is recorded and the PASS stored', witness_answer=acc, view=view(x), courier_900s=courier('v-wait'), courier_started_now=courier('v-late', 0))
    note('V3. the record of the budget, and what its checker says', **record_view(x))

    # ------------------------------------------------------------------ V4: an honest repeat of the same report
    b = attempts(); code, out = r.submit(VT.BAD); h = newest(b); stored_h = local.get_result(root, h['aid'])
    st, ans = call('/accept', gov, 'POST', {'root': root, 'op': ['RECONCILE', h['aid']], 'evidence': stored_h['report']})
    note('V4. an honest FAIL, and the gate host\'s own report sent to the witness a second time (a retry)', attempt=h, witness_answer={'status': st, 'kind': ans.get('kind'), 'code': ans.get('code')}, view=view(h))

    # ------------------------------------------------------------------ V5: the forgery made before the witness sees anything
    real_settle = Governor._settle; seen = {}
    def settle(self, aid, nonce, out):
        seen['gate host verdict'] = out['result'].get('verdict'); f = forge(out['result'])
        return real_settle(self, aid, nonce, dict(out, result=f, report=s.gate.effect_report(self.root, aid, nonce, 'EFFECT', f).to_json()))
    Governor._settle = settle
    try:
        b = attempts(); code_p, out_p = verify_client.Client(r.cfg).submit({'material': 'PA66-GF30', 'wall_mm': 3.5, 'mode': 'normal'}); pre = newest(b)
    finally:
        Governor._settle = real_settle
    note('V5. the gate host signed FAIL; the service sent the witness only its own report over a forged PASS, and stored the PASS', attempt=pre, gate_host_verdict=seen.get('gate host verdict'),
         client_was_told=VT.head(out_p), view=view(pre), courier_900s=courier('v-wait'), courier_started_now=courier('v-late', 0), record=record_view(pre))

    # ------------------------------------------------------------------ V6: can a recorded report be removed or changed, and by whom?
    first_seq = view(x)['reports in the answer'][0]['seq']
    tries = {}
    for role in ('plea_local', 'plea_witness', 'plea_control'):
        tries[role] = {'DELETE the first report': sql(role, 'DELETE FROM evidence WHERE root_id = %s AND aid = %s AND seq = %s', (root, x['aid'], first_seq)),
                       'UPDATE the first report': sql(role, "UPDATE evidence SET evidence = '{}'::jsonb WHERE root_id = %s AND aid = %s AND seq = %s", (root, x['aid'], first_seq))}
    note('V6. removing or changing the first (FAIL) report of the replaced run, as each role the store grants', tries=tries, view_after=view(x))
    owner = sql('plea', 'DELETE FROM evidence WHERE root_id = %s AND aid = %s AND seq = %s', (root, x['aid'], first_seq))
    note('V7. the same removal with the owner\'s password, which the repository gives', owner_delete=owner, view_after=view(x), courier_started_now=courier('v-late2', 0), record=record_view(x))
finally:
    r.stop()
    (OUT / 'visibility_check.json').write_text(json.dumps(LOG, indent=1, default=str))
