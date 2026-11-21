"""Diagnostic, 21 November 2026: what the service's database role can change, when a verdict is committed, and whether a
run can carry two gate-signed digests.  Development evidence only; not a declared test.  No code of e25a297 is changed.

    DIAG_DB=<fresh database> python commit_check.py SRC OUT

SRC is a copy of the tree at e25a297 (git archive).  A real deployment is started from it (deploy.Services: the witness
service, the gate host and the mailbox under mutual TLS, PostgreSQL behind them), and real runs are made through the
assistant's client.  "The service" below is this script acting with what the property file gives the service: the gate's
key, the client's certificate and the database role the client is configured with (plea_local).
"""
import copy, json, os, pathlib, sys, time, traceback, urllib.error, urllib.parse, urllib.request

SRC, OUT = sys.argv[1], pathlib.Path(sys.argv[2]); DB = os.environ['DIAG_DB']
for role, pw, var in (('plea_local', 'local', 'PLEA_LOCAL_DSN'), ('plea_witness', 'witness', 'PLEA_WITNESS_DSN'), ('plea_control', 'control', 'PLEA_CONTROL_DSN')):
    os.environ[var] = f'postgresql://{role}:{pw}@127.0.0.1:5432/{DB}'
sys.path[:0] = [SRC + '/tests', SRC, SRC + '/verify']
import verify_tests as VT                                   # noqa: E402  (its Run: one deployment, one baseline, one workspace)
import check_record as C                                    # noqa: E402
import verify_client                                        # noqa: E402
from plea_gateway import Store, tls as TLS                  # noqa: E402

LOG = {'when': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'database': DB, 'steps': []}


def note(name, **kw):
    LOG['steps'].append(dict(step=name, **kw)); print(f'--- {name}'); [print(f'    {k}: {json.dumps(v, default=str)[:900]}') for k, v in kw.items()]; sys.stdout.flush()


def first_line(exc):
    return f'{type(exc).__name__}: {str(exc).splitlines()[0][:160]}'


r = VT.Run('DIAG'); s = r.s
try:
    root = VT.B.root_for(r.env['card']); local = Store(os.environ['PLEA_LOCAL_DSN']); url = f"https://127.0.0.1:{s.ports['witness']}"
    gov, cour = s.pki['governor'], s.pki['courier']; q = urllib.parse.quote(root, safe='')

    def call(path, cert, method='GET', body=None):
        ctx = TLS.TLSClient(s.pki['ca'], *cert).context()
        req = urllib.request.Request(url + path, data=None if body is None else json.dumps(body).encode(), method=method, headers={'Content-Type': 'application/json'})
        t = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=70, context=ctx) as resp:
                return resp.status, json.loads(resp.read() or b'null'), round(time.monotonic() - t, 3)
        except urllib.error.HTTPError as exc:
            return exc.code, (exc.read() or b'')[:300].decode('utf-8', 'replace'), round(time.monotonic() - t, 3)
        except Exception as exc:
            return first_line(exc), None, round(time.monotonic() - t, 3)

    def sql(dsn_role, statement, params=()):
        """One statement in a transaction of its own, as the role named: what came of it."""
        pw = {'plea_local': 'local', 'plea_witness': 'witness', 'plea_control': 'control', 'plea': 'plea'}[dsn_role]
        import psycopg
        try:
            with psycopg.connect(f'postgresql://{dsn_role}:{pw}@127.0.0.1:5432/{DB}') as conn:
                cur = conn.execute(statement, params)
                out = cur.fetchall() if cur.description else cur.rowcount
                conn.commit()
                return {'ok': True, 'result': out if not isinstance(out, list) else out[:5]}
        except Exception as exc:
            return {'ok': False, 'error': first_line(exc)}

    def counts():
        with local.connect() as conn:
            return {'decisions': conn.execute('SELECT count(*) FROM decisions WHERE root_id = %s', (root,)).fetchone()[0],
                    'evidence': conn.execute('SELECT count(*) FROM evidence WHERE root_id = %s', (root,)).fetchone()[0],
                    'results': conn.execute('SELECT count(*) FROM results WHERE root_id = %s', (root,)).fetchone()[0]}

    def attempts():
        with local.connect() as conn:
            return [dict(aid=a, phase=p, nonce=n) for a, p, n in conn.execute('SELECT aid, phase, nonce FROM attempts WHERE root_id = %s', (root,)).fetchall()]

    def newest(before):
        new = [a for a in attempts() if a['aid'] not in {b['aid'] for b in before}]
        assert len(new) == 1, new
        return new[0]

    def last_decision():
        with local.connect() as conn:
            seq, op, kind, code = conn.execute('SELECT seq, op, kind, code FROM decisions WHERE root_id = %s ORDER BY seq DESC LIMIT 1', (root,)).fetchone()
        return {'seq': seq, 'op': op, 'kind': kind, 'code': code}

    def as_courier_reads(aid, nonce, phase='EFFECT'):
        st, ans, secs = call(f'/run?root={q}&aid={urllib.parse.quote(aid, safe="")}', cour)
        if st != 200:
            return {'status': st, 'answer': ans}
        stored = ans.get('result')
        value = stored.get('value') if isinstance(stored, dict) and stored.get('outcome', 'value') == 'value' else None        # as courier.run_outcome does
        ev = ans.get('evidence') or []
        return {'status': st, 'seconds': secs, 'reports': [{'seq': e['seq'], 'derived': e.get('derived'), 'claim': e['evidence'].get('claim'), 'result_digest': (e['evidence'].get('result_digest') or '')[:16]} for e in ev],
                'stored_outcome_field': stored.get('outcome') if isinstance(stored, dict) else None, 'stored_verdict': value.get('verdict') if isinstance(value, dict) else None,
                'stored_value_digest': C.sha(C.canonical(value))[:16] if isinstance(value, dict) else None,
                'check_record.run_outcome': C.run_outcome(phase, ev, value, [s.keys['gate']], root, aid, nonce)}

    def courier(name, stall):
        code, summary = s.courier([root], stall, name)
        return {'exit': code, 'made': [(m.get('aid'), m.get('outcome')) for m in summary.get('made', [])] if isinstance(summary, dict) else summary,
                'delivered': [(m.get('aid'), m.get('outcome')) for m in summary.get('delivered', [])] if isinstance(summary, dict) else None,
                'waiting': [(m.get('aid'), m.get('outcome')) for m in summary.get('waiting', [])] if isinstance(summary, dict) else None,
                'error': summary.get('error') if isinstance(summary, dict) else None}

    def mailbox_holds(aid):
        out = []
        for p in sorted((s.dir / 'mailbox' / 'notices').glob('*.json')):
            n = json.loads(p.read_text())['notice']
            if n.get('aid') == aid:
                out.append((n['courier'], n['outcome']))
        return out

    def second_report(aid, nonce, value, claim='EFFECT'):
        rep = s.gate.effect_report(root, aid, nonce, claim, value).to_json()
        before = counts()
        st, ans, _ = call('/accept', gov, 'POST', {'root': root, 'op': ['RECONCILE', aid], 'evidence': rep})
        return rep, {'witness_status': st, 'witness_answer': {k: ans.get(k) for k in ('kind', 'code', 'seq')} if isinstance(ans, dict) else ans, 'decision_recorded': last_decision(), 'rows_before': before, 'rows_after': counts()}

    # ------------------------------------------------------------------ 0. two honest runs
    b = attempts(); code_bad, out_bad = r.submit(VT.BAD); fail = newest(b)
    b = attempts(); code_good, out_good = r.submit(VT.GOOD); good = newest(b)
    res_fail, res_good = local.get_result(root, fail['aid']), local.get_result(root, good['aid'])
    PASS_VALUE = copy.deepcopy(res_good['value'])                 # a genuine PASS result of this budget, taken whole: what the service puts in a FAIL's place
    note('0. two honest runs through the client and the gate host', bad=dict(exit=code_bad, first_line=VT.head(out_bad), attempt=fail), good=dict(exit=code_good, first_line=VT.head(out_good), attempt=good),
         stored_fail_keys=sorted(res_fail), stored_fail_outcome_field=res_fail.get('outcome'), fail_value_keys=sorted(res_fail['value']), fail_value_bytes=len(json.dumps(res_fail['value'])),
         fail_as_courier_reads=as_courier_reads(fail['aid'], fail['nonce']), rows=counts(), session_user_of_the_client=sql('plea_local', 'SELECT session_user, current_user')['result'])

    # ------------------------------------------------------------------ 1. what plea_local can change directly
    a = fail['aid']
    tries = [
        ('UPDATE results', "UPDATE results SET result = jsonb_set(result, '{value,verdict}', '\"PASS\"') WHERE root_id = %s AND aid = %s", (root, a)),
        ('DELETE FROM results', 'DELETE FROM results WHERE root_id = %s AND aid = %s', (root, a)),
        ('INSERT INTO results', "INSERT INTO results (root_id, aid, result) VALUES (%s, 'zz-new', '{}'::jsonb)", (root,)),
        ('TRUNCATE results', 'TRUNCATE results', ()),
        ('UPDATE evidence', "UPDATE evidence SET derived = 'NONE' WHERE root_id = %s AND aid = %s", (root, a)),
        ('DELETE FROM evidence', 'DELETE FROM evidence WHERE root_id = %s AND aid = %s', (root, a)),
        ('INSERT INTO evidence', "INSERT INTO evidence (root_id, aid, seq, evidence, derived) VALUES (%s, %s, 999, '{}'::jsonb, 'AUTHORISED')", (root, a)),
        ('UPDATE decisions', "UPDATE decisions SET code = 'X' WHERE root_id = %s", (root,)),
        ('DELETE FROM decisions', 'DELETE FROM decisions WHERE root_id = %s', (root,)),
        ('UPDATE attempts (phase)', "UPDATE attempts SET phase = 'NO_EFFECT' WHERE root_id = %s AND aid = %s", (root, a)),
        ('DELETE FROM attempts', 'DELETE FROM attempts WHERE root_id = %s AND aid = %s', (root, a)),
        ('UPDATE roots', 'UPDATE roots SET head = head WHERE root_id = %s', (root,)),
        ('SELECT ... FOR UPDATE on results', 'SELECT 1 FROM results WHERE root_id = %s FOR UPDATE', (root,)),
        ('LOCK TABLE results IN ACCESS EXCLUSIVE MODE', 'LOCK TABLE results IN ACCESS EXCLUSIVE MODE', ()),
        ('LOCK TABLE decisions IN SHARE MODE', 'LOCK TABLE decisions IN SHARE MODE', ()),
        ('LOCK TABLE decisions IN ACCESS SHARE MODE', 'LOCK TABLE decisions IN ACCESS SHARE MODE', ()),
        ('ALTER TABLE results', 'ALTER TABLE results DISABLE TRIGGER ALL', ()),
        ('CREATE TABLE in public', 'CREATE TABLE public.zz (x int)', ()),
        ('CREATE TEMP TABLE', 'CREATE TEMP TABLE zz (x int)', ()),
        ('SET ROLE plea_witness', 'SET ROLE plea_witness', ()),
        ('SET ROLE plea', 'SET ROLE plea', ()),
        ('SET session_replication_role', "SET session_replication_role = 'replica'", ()),
        ('call plea_new_root', "SELECT plea_new_root('zz-root', 3, 0)", ()),
        ('pg_terminate_backend of the witness role', "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = 'plea_witness'", ()),
        ('pg_advisory_lock', 'SELECT pg_advisory_lock(1)', ()),
        ('see other sessions (pg_stat_activity)', "SELECT usename, state FROM pg_stat_activity WHERE datname = current_database() AND usename <> 'plea_local'", ()),
    ]
    direct = {name: sql('plea_local', stmt, params) for name, stmt, params in tries}
    with_api = {}
    for name, f in (('Store.apply_ex of a RECONCILE with evidence, as plea_local (the witness role is not used)',
                     lambda: local.apply_ex(root, ('RECONCILE', a, 'EFFECT', 'AUTHORISED'), s.gate.effect_report(root, a, fail['nonce'], 'EFFECT', PASS_VALUE).to_json(), 'AUTHORISED')),
                    ('Store.apply_ex of a RECONCILE without evidence, as plea_local', lambda: local.apply_ex(root, ('RECONCILE', a, 'EFFECT', 'AUTHORISED'))),
                    ('Store.put_evidence as plea_local', lambda: local.put_evidence(root, a, 999, {'x': 1}, 'AUTHORISED'))):
        try:
            with_api[name] = {'ok': True, 'result': str(f())[:200]}
        except Exception as exc:
            with_api[name] = {'ok': False, 'error': first_line(exc)}
    note('1. each change tried as plea_local, the role the client is configured with', direct=direct, through_the_store=with_api, rows_after=counts(),
         fail_as_courier_reads_after=as_courier_reads(fail['aid'], fail['nonce']))

    # ------------------------------------------------------------------ 2. a FAIL stored as a value: can it be replaced?
    before = local.get_result(root, a)
    rep2, acc = second_report(a, fail['nonce'], PASS_VALUE)
    try:
        local.put_result(root, a, {'outcome': 'value', 'value': PASS_VALUE, 'nonce': fail['nonce'], 'report': rep2}); put = 'no error'
    except Exception as exc:
        put = first_line(exc)
    after = local.get_result(root, a)
    note('2. the FAIL is stored as a value; the service has a second EFFECT report recorded (a PASS result\'s digest) and stores the PASS result', second_report=acc, put_result=put,
         stored_result_unchanged=(before == after), as_courier_reads=as_courier_reads(a, fail['nonce']), courier_pass=courier('c-e1', 0), mailbox_holds_for_the_run=mailbox_holds(a))
    rep3, acc3 = second_report(a, fail['nonce'], None, claim='NO_EFFECT')
    note('2b. a report with another verdict (NO_EFFECT) for the same run', second_report=acc3, as_courier_reads=as_courier_reads(a, fail['nonce']))

    # ------------------------------------------------------------------ 3. the result not yet stored: the service replaces the verdict
    def dishonest_submit(design, store_first):
        """The client's own code, in this process, with what it stores changed: nothing (store_first None), or a result marked
        'unknown'.  The gate host, the witness and the database are the real ones and are not changed."""
        client = verify_client.Client(r.cfg); held = []; real = client.store.put_result
        def put(root_, aid_, stored):
            held.append(stored)
            if store_first == 'unknown':
                real(root_, aid_, {'outcome': 'unknown', 'detail': 'held back', 'nonce': stored.get('nonce')})
        client.store.put_result = put
        b = attempts(); code, out = client.submit(design); return newest(b), code, VT.head(out), held

    x, code_x, line_x, held_x = dishonest_submit({'material': 'PA66-GF30', 'wall_mm': 2, 'mode': 'normal'}, None)      # another failing design: the client replays an identical one
    honest_value = held_x[0]['value'] if held_x else None
    step = {'attempt': x, 'client_exit': code_x, 'client_first_line': line_x, 'verdict_the_gate_host_signed_for': honest_value.get('verdict') if honest_value else None,
            'stored_result': local.get_result(root, x['aid']), 'as_courier_reads_before': as_courier_reads(x['aid'], x['nonce']),
            'courier_waiting_900s (c-wait), before': courier('c-wait', 900), 'courier_with_no_waiting_time (c-now), before': courier('c-now', 0)}
    repx, accx = second_report(x['aid'], x['nonce'], PASS_VALUE)
    local.put_result(root, x['aid'], {'outcome': 'value', 'value': PASS_VALUE, 'nonce': x['nonce'], 'report': repx})
    step.update(second_report=accx, as_courier_reads_after=as_courier_reads(x['aid'], x['nonce']), **{'courier_waiting_900s (c-wait), after': courier('c-wait', 900),
                'a courier that starts now (c-late), no waiting time': courier('c-late', 0)}, mailbox_holds_for_the_run=mailbox_holds(x['aid']))
    note('3. a FAIL signed by the gate host and recorded by the witness, the result not stored; then a second report and a PASS result', **step)

    y, code_y, line_y, held_y = dishonest_submit({'material': 'PA66-GF30', 'wall_mm': 4, 'mode': 'normal'}, 'unknown')
    step = {'attempt': y, 'client_exit': code_y, 'client_first_line': line_y, 'verdict_the_gate_host_signed_for': held_y[0]['value'].get('verdict') if held_y else None, 'stored_result_first': local.get_result(root, y['aid']), 'as_courier_reads_before': as_courier_reads(y['aid'], y['nonce'])}
    repy, accy = second_report(y['aid'], y['nonce'], PASS_VALUE)
    local.put_result(root, y['aid'], {'outcome': 'value', 'value': PASS_VALUE, 'nonce': y['nonce'], 'report': repy})
    step.update(second_report=accy, stored_outcome_field_after=local.get_result(root, y['aid']).get('outcome'), as_courier_reads_after=as_courier_reads(y['aid'], y['nonce']),
                **{'courier_waiting_900s (c-wait)': courier('c-wait', 900), 'a courier that starts now (c-late2), no waiting time': courier('c-late2', 0)}, mailbox_holds_for_the_run=mailbox_holds(y['aid']))
    note("3b. as 3, with a result marked 'unknown' stored first and then replaced", **step)

    # 3c: the PASS forged for the same design, with numbers that meet the limit (the gate's key signs it)
    z, code_z, line_z, held_z = dishonest_submit({'material': 'PA66-GF30', 'wall_mm': 2.5, 'mode': 'normal'}, None)
    forged = copy.deepcopy(held_z[0]['value'])
    forged.update(verdict='PASS', reason_code='MET', basis='limited by the continuous-use rating of PA66-GF30: 220 C')
    for c in forged['criteria']:
        c.update(met=True, achieved='220', margin='20')
    step = {'attempt': z, 'client_first_line': line_z, 'verdict_the_gate_host_signed_for': held_z[0]['value'].get('verdict'), 'achieved_the_gate_host_signed_for': [c.get('achieved') for c in held_z[0]['value']['criteria']],
            'as_courier_reads_before': as_courier_reads(z['aid'], z['nonce']), 'courier_waiting_900s (c-wait), before': courier('c-wait', 900)}
    repz, accz = second_report(z['aid'], z['nonce'], forged)
    local.put_result(root, z['aid'], {'outcome': 'value', 'value': forged, 'nonce': z['nonce'], 'report': repz})
    step.update(second_report=accz, as_courier_reads_after=as_courier_reads(z['aid'], z['nonce']), **{'courier_waiting_900s (c-wait), after': courier('c-wait', 900),
                'a courier that starts now (c-late3), no waiting time': courier('c-late3', 0)}, mailbox_holds_for_the_run=mailbox_holds(z['aid']))
    note('3c. as 3, the PASS result forged for the same design with numbers that meet the limit', **step)

    # ------------------------------------------------------------------ 4. what the record's checker says of these runs
    try:
        ok, why, summary = r.checked()
        runs = {u.get('attempt') or u.get('aid'): {k: u.get(k) for k in ('outcome', 'reason_code')} for u in summary.get('runs', [])}
        note('4. the record of this budget, built and checked as the tests do', record_verifies=ok, checks_that_fail=why, status=summary.get('status'), runs=runs,
             the_runs=dict(fail_stored_as_value=fail['aid'], good=good['aid'], replaced_before_storing=x['aid'], replaced_after_unknown=y['aid'], replaced_same_design=z['aid']))
    except Exception as exc:
        note('4. the record of this budget', error=first_line(exc), trace=traceback.format_exc()[-600:])
    note('5. all reports the witness holds for the five runs', **{k: as_courier_reads(v['aid'], v['nonce'])['reports'] for k, v in (('fail', fail), ('good', good), ('replaced_before_storing', x), ('replaced_after_unknown', y), ('replaced_same_design', z))},
         rows=counts())
    # ------------------------------------------------------------------ 6. can the role, or the account, decide when the witness answers?
    import psycopg, signal, threading
    path = f'/run?root={q}&aid={urllib.parse.quote(fail["aid"], safe="")}'
    base = [call(path, cour)[2] for _ in range(5)]
    held, err = [], None
    try:
        for _ in range(200):
            held.append(psycopg.connect(os.environ['PLEA_LOCAL_DSN']))
    except Exception as exc:
        err = first_line(exc)
    try:
        during = [call(path, cour)[::2] for _ in range(3)]
        cp_during = call(f'/checkpoint?root={q}&nonce=diag', cour)[::2]
        pass_during = courier('c-slots', 0)
    finally:
        for c in held:
            c.close()
    time.sleep(0.5)
    after_ = [call(path, cour)[::2] for _ in range(3)]
    note('6a. plea_local holds every connection slot it can get, then releases them', connections_held=len(held), stopped_by=err, get_run_seconds_before=base,
         get_run_while_held=during, checkpoint_while_held=cp_during, courier_pass_while_held=pass_during, get_run_after_release=after_)
    pid = s.procs['witness'].pid; os.kill(pid, signal.SIGSTOP); threading.Timer(5.0, os.kill, (pid, signal.SIGCONT)).start()
    stopped = call(path, cour)[::2]; time.sleep(0.3)
    note('6b. the witness process stopped for 5 seconds and continued, by the same operating-system account (the demonstration runs everything under one)',
         get_run_while_stopped=stopped, get_run_after=call(path, cour)[::2])
finally:
    r.stop()
    (OUT / 'commit_check.json').write_text(json.dumps(LOG, indent=1, default=str))
