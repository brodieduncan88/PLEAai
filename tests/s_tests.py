#!/usr/bin/env python3
"""S1-S3 (v1.0): the repairs for the v0.9 independent security review's three findings, each reproduced first by the
reviewer's own native probe run unchanged (outputs/review5/native_pg_before_v0_9.json) and re-run after the repair.

S1 binding immutability.  The accepted bindings an attempt carries cannot be rewritten in place: the request binding
   (req) never changes; the nonce (the executor/action binding) is set only by START (TOKEN->INTENT_PENDING) and
   cleared only by RECOVER (INTENT_PENDING->TOKEN), and every other update -- a same-phase rewrite included -- must
   carry it unchanged.  The reviewer's exact probe (a same-phase CONSUMED write with a new nonce, as plea_local) is
   refused natively, the nonce and the audit log are unchanged, and the witness's receipts keep binding the original
   nonce.  Every legitimate nonce path still applies.

S2 authenticated replay.  A stored outcome is a cache, never trusted on its own.  The gateway credential cannot
   write the results table directly; through plea_put_result it can store an outcome only for an admitted (crossed),
   consumed attempt, and a known outcome is never rewritten.  On replay the governor requires the stored nonce to be
   this action's and re-verifies the executor's signed effect report (pinned key, root, attempt, nonce, result
   digest) before returning a value: a fabricated row with no attempt, no nonce, no report, an impostor's report, or
   a report whose digest does not cover the stored value is refused and nothing runs; a genuine outcome replays
   without a second execution.

S3 SECURITY DEFINER hardening.  All three owner-side functions are SECURITY DEFINER with search_path pinned to
   pg_catalog, pg_temp and every table reference schema-qualified: a temporary table named roots, attempts or
   results in the caller's session cannot capture a privileged write (the row lands in public; the temporary table
   stays empty).  PUBLIC's default EXECUTE is revoked on all three; neither the gateway nor the witness credential
   can create a root (v1.1: provisioning is the control plane's), neither the control plane nor the witness can store
   an outcome; no login role can create objects in public.
"""
import json
import time

import psycopg

from common import (ADMIN_DSN, CONTROL_DSN, GATE, LOCAL_DSN, WITNESS_DSN, WITNESS_KEY, WITNESS_PUB, Store, WitnessService,
                    fresh_root, replay_lockstep, write_output)
from plea_gateway import Governor, RemoteWitness, nonce_for
from plea_gateway.evidence import GateSigner, OutcomeInvalid
from plea_gateway.governor import RequestKeyReused, attempt_id

admin, local, witness, control = Store(ADMIN_DSN), Store(LOCAL_DSN), Store(WITNESS_DSN), Store(CONTROL_DSN)
FUNCS = [('plea_write', 'plea_write(text,jsonb,jsonb,bigint,text,jsonb,text,text,jsonb,text,jsonb)'),
         ('plea_new_root', 'plea_new_root(text,integer,integer)'),          # v1.2: no caller-supplied starting hash
         ('plea_put_result', 'plea_put_result(text,text,jsonb)')]


def refused(label, fn, want):
    try:
        fn(); return (f'{label}: NOT refused', False)
    except want as exc:
        return (f'{label} ({type(exc).__name__})', True)
    except Exception as exc:
        return (f'{label}: unexpected {type(exc).__name__}: {str(exc)[:80]}', False)


def head(root):
    with admin.connect() as c:
        return c.execute('SELECT seq, head_hash FROM roots WHERE root_id=%s', (root,)).fetchone()


def forge(dsn, root, attempts, modes=None, op=('RESERVE', 'x', 'x'), kind='APPLIED', code='FORGED'):
    """A hand-written plea_write over `dsn` with a valid chain position.  Raises the database error on refusal.
    v1.1: `op` must be a contract operation name (an unknown name is refused before any other rule), and each
    binding check names the operation that produces its transition, so the binding rule is what refuses it."""
    seq, h = head(root)
    with psycopg.connect(dsn) as c:
        c.execute('SELECT plea_write(%s, %s::jsonb, %s::jsonb, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s::jsonb)',
                  (root, json.dumps(attempts), json.dumps(modes) if modes is not None else None,
                   seq + 1, 'forged-' + str(seq + 1), json.dumps(list(op)), kind, code, json.dumps({}), h, None))
        c.commit()


def raw(dsn, sql, params=()):
    try:
        with psycopg.connect(dsn) as c:
            c.execute(sql, params); c.commit(); return True
    except psycopg.Error:
        return False


def a1(root):
    with admin.connect() as c:
        return c.execute('SELECT req, phase, nonce, receipt, crossed FROM attempts WHERE root_id=%s AND aid=%s', (root, 'a1')).fetchone()


def put_a1(root, phase, nonce=None, receipt=False, crossed=False, k=3, m=1):
    """Owner stages a1 directly at an arbitrary state, to isolate one rule of the write function."""
    fresh_root(admin, root, k, m)
    with admin.connect() as c:
        c.execute('INSERT INTO attempts (root_id, aid, req, phase, nonce, receipt, crossed) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                  (root, 'a1', 'q1', phase, nonce, receipt, crossed)); c.commit()


def row(aid, phase, nonce, receipt=False, crossed=False, req='q1'):
    return {'aid': aid, 'req': req, 'phase': phase, 'nonce': nonce, 'receipt': receipt, 'crossed': crossed}


# ============================================================ S1: binding immutability
def s1(w):
    checks = []
    # the reviewer's exact probe: a genuinely admitted attempt, then a same-phase write with a new nonce as plea_local
    root = 's1-probe'; fresh_root(admin, root, 1, 0)
    for st, op in [(local, ('RESERVE', 'a1', 'q1')), (witness, ('ACCEPT_RESERVATION', 'a1')), (local, ('TOKEN', 'a1')),
                   (local, ('START', 'a1', 'n-old')), (witness, ('ACCEPT_INTENT', 'a1')), (local, ('RECEIPT', 'a1')), (witness, ('CROSS', 'a1'))]:
        d, _ = st.apply(root, op); assert d.kind == 'APPLIED', (op, d)
    before, log_before = a1(root), len(admin.audit(root))
    checks.append(refused("the reviewer's probe: same-phase CONSUMED write with a new nonce, as plea_local, is refused",
                          lambda: forge(LOCAL_DSN, root, [row('a1', 'CONSUMED', 'n-new', True, True)], op=('RECEIPT', 'a1'), kind='DUPLICATE', code='RECEIPT_ALREADY_DELIVERED'),
                          psycopg.errors.CheckViolation))
    checks.append(('the attempt and the audit log are unchanged; the nonce is still n-old', a1(root) == before and before[2] == 'n-old' and len(admin.audit(root)) == log_before))
    d, r = w.accept_intent(root, 'a1')
    checks.append(("the witness's receipt after the refused rewrite still binds the original nonce", d.kind == 'DUPLICATE' and r.binding == 'n-old'))
    checks.append(refused('the same rewrite as the owner is refused too (the rule is not an authority check)',
                          lambda: forge(ADMIN_DSN, root, [row('a1', 'CONSUMED', 'n-new', True, True)], op=('RECEIPT', 'a1')), psycopg.errors.CheckViolation))
    checks.append(refused('a same-phase write that changes the request binding (req) is refused',
                          lambda: forge(ADMIN_DSN, root, [row('a1', 'CONSUMED', 'n-old', True, True, req='q-other')], op=('RECEIPT', 'a1')), psycopg.errors.CheckViolation))
    # a nonce change smuggled onto a legal phase change (each as the owner: only the binding rule is under test)
    put_a1('s1-smug', 'CONSUMED', 'n1', True, True)
    checks.append(refused('CONSUMED->EFFECT carrying a different nonce is refused',
                          lambda: forge(ADMIN_DSN, 's1-smug', [row('a1', 'EFFECT', 'n2', True, True)], op=('RECONCILE', 'a1', 'EFFECT', 'AUTHORISED')), psycopg.errors.CheckViolation))
    put_a1('s1-smug2', 'INTENT_PENDING', 'n1')
    checks.append(refused('INTENT_PENDING->CONSUMED carrying a different nonce is refused',
                          lambda: forge(ADMIN_DSN, 's1-smug2', [row('a1', 'CONSUMED', 'n2')], op=('ACCEPT_INTENT', 'a1')), psycopg.errors.CheckViolation))
    put_a1('s1-smug3', 'CONSUMED', 'n1', True)
    checks.append(refused('CONSUMED->INDETERMINATE dropping the nonce is refused',
                          lambda: forge(ADMIN_DSN, 's1-smug3', [row('a1', 'INDETERMINATE', None, True)], op=('REREGISTER',)), psycopg.errors.CheckViolation))
    # START must bind a fresh nonce; RECOVER must clear it
    put_a1('s1-start1', 'TOKEN', 'n-pre')
    checks.append(refused('TOKEN->INTENT_PENDING when a nonce is already bound is refused (START binds a fresh nonce)',
                          lambda: forge(ADMIN_DSN, 's1-start1', [row('a1', 'INTENT_PENDING', 'n-x')], op=('START', 'a1', 'n-x')), psycopg.errors.CheckViolation))
    put_a1('s1-start2', 'TOKEN')
    checks.append(refused('TOKEN->INTENT_PENDING without a nonce is refused',
                          lambda: forge(ADMIN_DSN, 's1-start2', [row('a1', 'INTENT_PENDING', None)], op=('START', 'a1', 'n-y')), psycopg.errors.CheckViolation))
    put_a1('s1-rec', 'INTENT_PENDING', 'n1')
    checks.append(refused('INTENT_PENDING->TOKEN keeping the nonce is refused (RECOVER clears it)',
                          lambda: forge(ADMIN_DSN, 's1-rec', [row('a1', 'TOKEN', 'n1')], op=('RECOVER', True, True)), psycopg.errors.CheckViolation))
    # every legitimate nonce path applies through the proper credentials
    root = 's1-ok'; fresh_root(admin, root, 3, 1); seen = []
    for st, op in [(local, ('RESERVE', 'a1', 'q1')), (witness, ('ACCEPT_RESERVATION', 'a1')), (local, ('TOKEN', 'a1')), (local, ('START', 'a1', 'n1')),
                   (witness, ('ACCEPT_INTENT', 'a1')), (local, ('RECEIPT', 'a1')), (witness, ('CROSS', 'a1')), (witness, ('RECONCILE', 'a1', 'EFFECT', 'AUTHORISED'))]:
        d, _ = st.apply(root, op); seen.append((d.kind, a1(root)[2]))
    checks.append(('set by START, carried unchanged through ACCEPT_INTENT, RECEIPT, CROSS and RECONCILE', [k for k, _ in seen] == ['APPLIED'] * 8 and [n for _, n in seen] == [None, None, None, 'n1', 'n1', 'n1', 'n1', 'n1']))
    root = 's1-rec-ok'; fresh_root(admin, root, 3, 0)
    for st, op in [(local, ('RESERVE', 'a1', 'q1')), (witness, ('ACCEPT_RESERVATION', 'a1')), (local, ('TOKEN', 'a1')), (local, ('START', 'a1', 'n9'))]:
        st.apply(root, op)
    control.apply(root, ('HOLD',)); d, o = control.apply(root, ('RECOVER', True, True))
    checks.append(('cleared by RECOVER (INTENT_PENDING->TOKEN) through the control credential', d.kind == 'APPLIED' and a1(root)[1] == 'TOKEN' and a1(root)[2] is None))
    root = 's1-rereg-ok'; fresh_root(admin, root, 3, 0)
    for st, op in [(local, ('RESERVE', 'a1', 'q1')), (witness, ('ACCEPT_RESERVATION', 'a1')), (local, ('TOKEN', 'a1')), (local, ('START', 'a1', 'n7')), (witness, ('ACCEPT_INTENT', 'a1'))]:
        st.apply(root, op)
    d, _ = control.apply(root, ('REREGISTER',))
    checks.append(('carried by REREGISTER (CONSUMED->INDETERMINATE)', d.kind == 'APPLIED' and a1(root)[1] == 'INDETERMINATE' and a1(root)[2] == 'n7'))
    checks.append(('replay lockstep on the lifecycle root', replay_lockstep(admin, 's1-ok', 3, 1)[0]))
    return checks


# ============================================================ S2: authenticated replay
CALLS = []


def charge(order_id, amount):
    CALLS.append((order_id, amount)); return {'charged': amount, 'order': order_id}


def s2(w):
    checks = []
    def gov(root, k=1):
        return Governor(Store(LOCAL_DSN), w, root, k, 0, admin=admin, gate=GATE)        # in-process gate: this process signs the reports
    # a genuine outcome replays from the cache without a second execution, through the same verification
    root = 's2-genuine'; fresh_root(admin, root, 1, 0); CALLS.clear()
    v1 = gov(root).attempt('s2:k1', charge, 'o1', 10)
    v2 = gov(root).attempt('s2:k1', charge, 'o1', 10)                                   # a new governor object: the result comes from the database
    stored = admin.get_result(root, attempt_id('s2:k1'))
    checks.append(('a genuine outcome runs once and replays the same value from the stored, signed outcome', v1 == v2 == {'charged': 10, 'order': 'o1'} and len(CALLS) == 1))
    checks.append(('the stored outcome carries the nonce and the gate\'s signed effect report', stored and stored.get('nonce') and isinstance(stored.get('report'), dict) and stored['report'].get('signer') == GATE.public_hex))
    # the gateway credential cannot write the cache directly, nor store an outcome for an attempt that was not admitted
    root = 's2-write'; fresh_root(admin, root, 3, 0); local.apply(root, ('RESERVE', 'a1', 'q1'))
    checks.append(('plea_local raw INSERT into results is refused', not raw(LOCAL_DSN, "INSERT INTO results (root_id, aid, result) VALUES (%s, 'a1', '{}')", (root,))))
    checks.append(refused('plea_local storing an outcome for a reserved, never-admitted attempt is refused',
                          lambda: local.put_result(root, 'a1', {'outcome': 'value', 'value': 1}), psycopg.errors.CheckViolation))
    checks.append(refused('plea_local storing an outcome for an attempt that does not exist is refused',
                          lambda: local.put_result(root, 'zz', {'outcome': 'value', 'value': 1}), psycopg.errors.CheckViolation))
    # a known outcome is never rewritten; an unknown one is replaced once
    root = 's2-first'; fresh_root(admin, root, 1, 0); CALLS.clear(); gov(root).attempt('s2:k2', charge, 'o2', 5); aid = attempt_id('s2:k2')
    genuine = admin.get_result(root, aid)
    local.put_result(root, aid, {'outcome': 'value', 'value': 999, 'nonce': genuine['nonce'], 'report': genuine['report']})
    checks.append(('a second store for a known outcome does not replace it (the first stands)', admin.get_result(root, aid) == genuine))
    with admin.connect() as c:
        c.execute("UPDATE results SET result = %s WHERE root_id=%s AND aid=%s", (json.dumps({'outcome': 'unknown', 'detail': 'staged', 'nonce': genuine['nonce']}), root, aid)); c.commit()
    local.put_result(root, aid, genuine)
    checks.append(('an unknown outcome is replaced by a known one, once', admin.get_result(root, aid) == genuine))
    # fabricated cache rows (planted by the owner, past the grant) are refused on replay and nothing runs
    def planted(label, root, key, result, want):
        fresh_root(admin, root, 1, 0); aid = attempt_id(key)
        with admin.connect() as c:
            c.execute('INSERT INTO results (root_id, aid, result) VALUES (%s, %s, %s)', (root, aid, json.dumps(result))); c.commit()
        CALLS.clear()
        lab, ok = refused(label, lambda: gov(root).attempt(key, charge, 'ox', 1), want)
        n = len(admin.state(root)[0].attempts)
        checks.append((lab + '; nothing ran, no attempt exists', ok and CALLS == [] and n == 0))
    g0 = gov('s2-tmp'); tool, arguments = g0._action(charge, ('ox', 1), {})
    def nonce_of(root, key): return nonce_for(root, attempt_id(key), GATE.public_hex, tool, arguments)
    planted("the reviewer's probe: a fabricated success with no attempt and no nonce is refused", 's2-fake1', 's2:f1',
            {'outcome': 'value', 'value': {'status': 'paid', 'amount': 999999}}, RequestKeyReused)
    planted('a fabricated success with the right nonce but no signed report is refused', 's2-fake2', 's2:f2',
            {'outcome': 'value', 'value': {'status': 'paid'}, 'nonce': nonce_of('s2-fake2', 's2:f2')}, OutcomeInvalid)
    key, root = 's2:f3', 's2-fake3'; n3 = nonce_of(root, key)
    impostor = GateSigner().effect_report(root, attempt_id(key), n3, 'EFFECT', {'status': 'paid'}).to_json()
    planted("a fabricated success with a report signed by an impostor's key is refused", root, key,
            {'outcome': 'value', 'value': {'status': 'paid'}, 'nonce': n3, 'report': impostor}, OutcomeInvalid)
    key, root = 's2:f4', 's2-fake4'; n4 = nonce_of(root, key)
    wrong_digest = GATE.effect_report(root, attempt_id(key), n4, 'EFFECT', {'status': 'paid', 'amount': 1}).to_json()
    planted("a genuine-key report whose digest does not cover the stored value is refused", root, key,
            {'outcome': 'value', 'value': {'status': 'paid', 'amount': 999999}, 'nonce': n4, 'report': wrong_digest}, OutcomeInvalid)
    key, root = 's2:f5', 's2-fake5'; n5 = nonce_of(root, key)
    no_effect_report = GATE.effect_report(root, attempt_id(key), n5, 'NO_EFFECT').to_json()
    planted("a report whose claim (NO_EFFECT) does not match the stored kind (value) is refused", root, key,
            {'outcome': 'value', 'value': {'status': 'paid'}, 'nonce': n5, 'report': no_effect_report}, OutcomeInvalid)
    checks.append(('replay lockstep on the genuine root', replay_lockstep(admin, 's2-genuine', 1, 0)[0]))
    return checks


# ============================================================ S3: SECURITY DEFINER hardening
def s3():
    checks = []
    with admin.connect() as c:
        rows = c.execute("SELECT proname, prosecdef, proconfig FROM pg_proc WHERE pronamespace = 'public'::regnamespace AND proname = ANY(%s) ORDER BY proname",
                         ([n for n, _ in FUNCS],)).fetchall()
        public_exec = {name: c.execute("SELECT EXISTS(SELECT 1 FROM aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) WHERE grantee = 0 AND privilege_type = 'EXECUTE') "
                                       "FROM pg_proc p WHERE p.oid = to_regprocedure(%s)", (f'public.{sig}',)).fetchone()[0] for name, sig in FUNCS}
    checks.append(('all three functions are SECURITY DEFINER with search_path pinned to pg_catalog, pg_temp',
                   len(rows) == 3 and all(sd and cfg == ['search_path=pg_catalog, pg_temp'] for _, sd, cfg in rows)))
    checks.append(('PUBLIC holds no EXECUTE on any of the three functions', public_exec == {n: False for n, _ in FUNCS}))
    # the reviewer's probe: a temporary roots table in the caller's session cannot capture the privileged insert
    # (v1.2: plea_new_root also writes the provisioning log, so a temporary 'provisions' is planted too)
    with admin.connect() as c:
        c.execute("DELETE FROM roots WHERE root_id IN ('s3-shadow', 's3-shadow2')"); c.commit()
    with psycopg.connect(CONTROL_DSN) as c:                                       # v1.1: the provisioning credential
        c.execute('CREATE TEMP TABLE roots (root_id text, k int, m int, witness text, business text, head_hash text, provision_seq bigint)')
        c.execute('CREATE TEMP TABLE provisions (seq bigint, root_id text, k int, m int, issuer text, contract text, release text, created_at text, prev_hash text, hash text)')
        c.execute('GRANT INSERT, SELECT ON TABLE pg_temp.roots, pg_temp.provisions TO plea')
        c.execute('SELECT public.plea_new_root(%s, %s, %s)', ('s3-shadow', 2, 0)); c.commit()
        temp_rows = c.execute("SELECT (SELECT count(*) FROM pg_temp.roots) + (SELECT count(*) FROM pg_temp.provisions)").fetchone()[0]
    with admin.connect() as c:
        pub_rows = c.execute("SELECT count(*) FROM public.roots r JOIN public.provisions p ON p.seq = r.provision_seq WHERE r.root_id = 's3-shadow'").fetchone()[0]
    checks.append(("the reviewer's probe: with a temporary 'roots' and 'provisions' in the session, plea_new_root writes public.roots and the public provisioning log; the temporary tables stay empty", temp_rows == 0 and pub_rows == 1))
    # the same for the tables the write and outcome functions touch, in one session: attempts, results
    root = 's3-shadow2'; fresh_root(admin, root, 3, 0)
    for st, op in [(local, ('RESERVE', 'a1', 'q1')), (witness, ('ACCEPT_RESERVATION', 'a1')), (local, ('TOKEN', 'a1')), (local, ('START', 'a1', 'n1')),
                   (witness, ('ACCEPT_INTENT', 'a1')), (local, ('RECEIPT', 'a1')), (witness, ('CROSS', 'a1'))]:
        st.apply(root, op)
    with psycopg.connect(LOCAL_DSN) as c:
        c.execute('CREATE TEMP TABLE attempts (root_id text, aid text, req text, phase text, nonce text, receipt boolean, crossed boolean)')
        c.execute('CREATE TEMP TABLE results (root_id text, aid text, result jsonb)')
        c.execute('GRANT ALL ON TABLE pg_temp.attempts, pg_temp.results TO plea')
        c.execute('SELECT public.plea_put_result(%s, %s, %s::jsonb)', (root, 'a1', json.dumps({'outcome': 'unknown', 'detail': 'x', 'nonce': 'n1'}))); c.commit()
        temp_res = c.execute('SELECT count(*) FROM pg_temp.results').fetchone()[0]
    with admin.connect() as c:
        pub_res = c.execute("SELECT count(*) FROM public.results WHERE root_id = %s", (root,)).fetchone()[0]
    checks.append(("with temporary 'attempts' and 'results' in the session, plea_put_result reads public.attempts and writes public.results; the temporary tables stay empty", temp_res == 0 and pub_res == 1))
    # least privilege across the functions
    checks.append(('neither the gateway nor the witness credential can create a root (v1.1: provisioning is the control plane\'s)',
                   not raw(LOCAL_DSN, 'SELECT public.plea_new_root(%s, %s, %s)', ('s3-gw', 1, 0)) and not raw(WITNESS_DSN, 'SELECT public.plea_new_root(%s, %s, %s)', ('s3-wit', 1, 0))))
    checks.append(('the control credential cannot store an outcome', not raw(CONTROL_DSN, 'SELECT public.plea_put_result(%s, %s, %s::jsonb)', (root, 'a1', '{}'))))
    checks.append(('the witness credential cannot store an outcome', not raw(WITNESS_DSN, 'SELECT public.plea_put_result(%s, %s, %s::jsonb)', (root, 'a1', '{}'))))
    checks.append(('no login role can create objects in public', not raw(LOCAL_DSN, 'CREATE TABLE public.s3_planted (x int)') and not raw(WITNESS_DSN, 'CREATE TABLE public.s3_planted (x int)') and not raw(CONTROL_DSN, 'CREATE TABLE public.s3_planted (x int)')))
    checks.append(('no login role holds direct DML on results (INSERT/UPDATE/DELETE)',
                   all(not raw(d, s, (root,)) for d in (LOCAL_DSN, WITNESS_DSN, CONTROL_DSN)
                       for s in ("INSERT INTO results (root_id, aid, result) VALUES (%s, 'zz', '{}')", "UPDATE results SET result = '{}' WHERE root_id = %s", "DELETE FROM results WHERE root_id = %s"))))
    return checks


def main():
    t0 = time.time()
    svc = WitnessService(8990, key=WITNESS_KEY); svc.start(); w = RemoteWitness(svc.url, WITNESS_PUB)
    try:
        out = {'S1': s1(w), 'S2': s2(w), 'S3': s3()}
    finally:
        svc.stop()
    out['seconds'] = round(time.time() - t0, 1)
    for k in ('S1', 'S2', 'S3'):
        out[k + '_ok'] = all(ok for _, ok in out[k]); out[k + '_count'] = len(out[k])
    out['PASS'] = all(out[k + '_ok'] for k in ('S1', 'S2', 'S3'))
    write_output('s_tests.json', out)
    for k in ('S1', 'S2', 'S3'):
        for label, ok in out[k]:
            print(k, 'ok  ' if ok else 'FAIL', label)
    print(json.dumps({k: v for k, v in out.items() if k not in ('S1', 'S2', 'S3')}, indent=1))
    print('S RESULT:', 'PASS' if out['PASS'] else 'FAIL'); raise SystemExit(0 if out['PASS'] else 1)


if __name__ == '__main__':
    main()
