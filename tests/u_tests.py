#!/usr/bin/env python3
"""U1-U2 (v1.1): the repairs for the v1.0 independent security review's two findings, each reproduced first by the
reviewer's own native probe (outputs/review6/) run on the shipped v1.0 before any repair, and re-run after.

U1 audit integrity.  The database authors the audit record.  For every decision plea_write appends: the observation
   stored is derived from the rows just written and the caller's must equal it; the kind is APPLIED exactly when the
   state changed; the operation named is the one that produces the transition performed (an insert is a RESERVE, a
   witness hold is a HOLD, ...); and the chain hash is recomputed in-database, with a canonical form identical to the
   client's, and must equal the caller's.  The reviewer's probe -- a STOP/APPLIED record with a correctly recomputed
   hash and no mode change, as plea_local -- is refused atomically: no audit entry, no head advance, the run still
   OPEN and still admitting.  Every other way of making a record disagree with its transition is refused too, as the
   owner (a rule, not an authority check), and the canonical form and hash are shown identical between the database
   and the client over random values.  Every genuine decision applies; verify_chain and replay lockstep hold.

U2 provisioning authority.  A root is a budget, and only the control plane provisions one.  The gateway and the
   witness credentials cannot create a root; the control credential can; the reviewer's probe -- a budget-one root
   exhausted, then plea_local creates a k=1000 root -- is refused and the gateway stays exhausted; a governor without
   a provisioner refuses an unprovisioned root by name; with the control credential it provisions; plea_ctl provision
   provisions through the control credential and reports an existing root.
"""
import json
import os
import random
import subprocess
import threading
import time

import psycopg

from common import (ADMIN_DSN, CONTROL_DSN, GATE, GATEWAY, LOCAL_DSN, PYTHON, WITNESS_DSN, WITNESS_KEY, WITNESS_PUB, Store,
                    WitnessService, fresh_root, replay_lockstep, write_output)
from plea_gateway import AuthorityError, Governor, RemoteWitness, UnknownRoot
from plea_gateway import plea_budget_ref as ref
from plea_gateway.store import GENESIS, _canonical, _jsonable, chain_hash

admin, local, witness, control = Store(ADMIN_DSN), Store(LOCAL_DSN), Store(WITNESS_DSN), Store(CONTROL_DSN)
MCP = GATEWAY / 'mcp'


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


def forge(dsn, root, attempts, modes, op, kind, code, observation, hash_over=None):
    """A hand-written plea_write at the right chain position, with the hash the client would compute over the given
    observation (or over `hash_over` when the caller wants the hash to disagree).  Raises the database error."""
    seq, h = head(root)
    digest = chain_hash(h, seq + 1, list(op), kind, code, observation if hash_over is None else hash_over)
    with psycopg.connect(dsn) as c:
        c.execute('SELECT plea_write(%s, %s::jsonb, %s::jsonb, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s::jsonb)',
                  (root, json.dumps(attempts), json.dumps(modes) if modes is not None else None,
                   seq + 1, digest, json.dumps(list(op)), kind, code, json.dumps(observation), h, None))
        c.commit()


def after(root, op):
    """The observation the reference engine gives after `op`, as the client would record it."""
    state, _, _ = admin.state(root)
    return _jsonable(ref.observe(ref.apply(state, ref.parse_op(op))[1]))


def row(aid, phase, nonce=None, receipt=False, crossed=False, req='q1'):
    return {'aid': aid, 'req': req, 'phase': phase, 'nonce': nonce, 'receipt': receipt, 'crossed': crossed}


def unchanged(root, before):
    seq, h = head(root)
    return (seq, h) == before[:2] and len(admin.audit(root)) == before[2] and admin.observe(root) == before[3]


def snapshot(root):
    seq, h = head(root)
    return (seq, h, len(admin.audit(root)), admin.observe(root))


# ============================================================ U1: audit integrity
def u1(w):
    checks = []
    # --- the reviewer's probe, exactly: STOP/APPLIED with the reference's code, a correct hash over the unchanged state
    root = 'u1-probe'; fresh_root(admin, root, 1, 0)
    state, seq, old_hash = admin.state(root); obs_before = admin.observe(root)
    d, _ = ref.apply(state, ref.parse_op(('STOP',))); kind, code = d.kind.value, d.code
    snap = snapshot(root)
    checks.append(refused("the reviewer's probe: STOP/APPLIED with a correct hash and no mode change, as plea_local, is refused",
                          lambda: forge(LOCAL_DSN, root, [], None, ('STOP',), kind, code, obs_before), psycopg.errors.CheckViolation))
    checks.append(('atomic: no audit entry, no head advance, the run still OPEN', unchanged(root, snap) and admin.observe(root)['business'] == 'OPEN'))
    d2, _ = local.apply(root, ('RESERVE', 'a1', 'q1'))
    checks.append(('the run still admits (the false STOP did not take): RESERVE APPLIED', d2.kind == 'APPLIED'))
    checks.append(refused('the same record as the owner is refused too (a rule, not an authority check)',
                          lambda: forge(ADMIN_DSN, root, [], None, ('STOP',), 'APPLIED', 'STOPPING', admin.observe(root)), psycopg.errors.CheckViolation))

    # --- every other way a record can disagree with its transition (each as the owner, so only the rule is under test)
    root = 'u1-shape'; fresh_root(admin, root, 3, 1); snap = snapshot(root)
    obs_res = after(root, ('RESERVE', 'a1', 'q1'))
    checks.append(refused('a real change recorded as DENIED is refused (the kind is bound to the change)',
                          lambda: forge(ADMIN_DSN, root, [row('a1', 'RESERVING')], None, ('RESERVE', 'a1', 'q1'), 'DENIED', 'X', obs_res), psycopg.errors.CheckViolation))
    checks.append(refused('an observation that misdescribes the state after the change is refused',
                          lambda: forge(ADMIN_DSN, root, [row('a1', 'RESERVING')], None, ('RESERVE', 'a1', 'q1'), 'APPLIED', 'RESERVATION_COMMITTED', dict(obs_res, business='STOPPING')), psycopg.errors.CheckViolation))
    checks.append(refused('a correct record whose hash is computed over a different observation is refused',
                          lambda: forge(ADMIN_DSN, root, [row('a1', 'RESERVING')], None, ('RESERVE', 'a1', 'q1'), 'APPLIED', 'RESERVATION_COMMITTED', obs_res, hash_over=dict(obs_res, k=99)), psycopg.errors.CheckViolation))
    checks.append(refused('an insert recorded under another operation (START) is refused (the operation is bound to the transition)',
                          lambda: forge(ADMIN_DSN, root, [row('a1', 'RESERVING')], None, ('START', 'a1', 'n1'), 'APPLIED', 'X', obs_res), psycopg.errors.CheckViolation))
    checks.append(refused('an unknown decision kind is refused',
                          lambda: forge(ADMIN_DSN, root, [row('a1', 'RESERVING')], None, ('RESERVE', 'a1', 'q1'), 'GRANTED', 'X', obs_res), psycopg.errors.CheckViolation))
    checks.append(refused('an unknown operation is refused',
                          lambda: forge(ADMIN_DSN, root, [], None, ('APPROVE',), 'DENIED', 'X', admin.observe(root)), psycopg.errors.CheckViolation))
    checks.append(('none of those left a trace', unchanged(root, snap)))
    d, _ = local.apply(root, ('RESERVE', 'a1', 'q1')); snap = snapshot(root)
    checks.append(refused('an APPLIED record whose attempt payload changes nothing is refused (no change, no APPLIED)',
                          lambda: forge(ADMIN_DSN, root, [row('a1', 'RESERVING')], None, ('RESERVE', 'a1', 'q1'), 'APPLIED', 'RESERVATION_COMMITTED', admin.observe(root)), psycopg.errors.CheckViolation))
    obs_hold = after(root, ('HOLD',))
    checks.append(refused('a witness hold recorded as a STOP is refused, as the control plane (each mode change is bound to its operation)',
                          lambda: forge(CONTROL_DSN, root, [], {'witness': 'HELD', 'business': 'OPEN', 'reregistered': False}, ('STOP',), 'APPLIED', 'STOPPING', obs_hold), psycopg.errors.CheckViolation))
    checks.append(('nothing changed and the chain still verifies', unchanged(root, snap) and admin.verify_chain(root)[0]))

    # --- the canonical form and the hash are identical between the database and the client
    rnd = random.Random(1101); phases = ['RESERVING', 'RESERVED', 'TOKEN', 'INTENT_PENDING', 'CONSUMED', 'NO_EFFECT', 'EFFECT', 'INDETERMINATE', 'RELEASED', 'DISCARDED']
    specials = ['plain', 'q"uote', 'back\\slash', 'nl\n', 'tab\t', 'cr\r', 'bs\b', 'ff\f', 'ctl\x01', 'ctl\x1f', 'del\x7f', 'eé', 'euro€', 'emoji\U0001f600', '/slash', '<>&', "it's", '', ' ', 'a-1', 'a:x', 'A1', 'z' * 40]
    def rand_obs():
        atts = sorted({rnd.choice(specials) if rnd.random() < 0.3 else f'a{rnd.randrange(50)}' for _ in range(rnd.randrange(6))})
        return {'k': rnd.randrange(5), 'm': rnd.randrange(3), 'witness': rnd.choice(['ACTIVE', 'HELD']), 'business': rnd.choice(['OPEN', 'STOPPING', 'TERMINALISING', 'TERMINAL']),
                'reregistered': rnd.random() < 0.5, 'live': [rnd.randrange(4), rnd.randrange(4), rnd.randrange(2)], 'accepted': [rnd.randrange(4), rnd.randrange(4), rnd.randrange(2)],
                'credit': rnd.randrange(2), 'attempts': [[a, rnd.choice(specials), rnd.choice(phases), rnd.choice([None, 'n' + a, rnd.choice(specials)]), rnd.random() < 0.5, rnd.random() < 0.5] for a in atts]}
    def rand_op():
        return rnd.choice([['RESERVE', rnd.choice(specials), rnd.choice(specials)], ['RECOVER', rnd.random() < 0.5, rnd.random() < 0.5], ['STOP'], ['RECONCILE', 'a1', 'EFFECT', 'AUTHORISED'], ['START', 'a1', rnd.choice(specials)], [-12, 0, 7, None, True]])
    n_can = n_hash = 0; samples = []
    with admin.connect() as c:
        for _ in range(300):
            v = rnd.choice([rand_obs(), rand_op(), rnd.choice(specials), rnd.randrange(-5, 5), None, True, {'nested': {'z': [1, {'y': 'x'}], 'a': rnd.choice(specials)}}])
            samples.append(v)
            if c.execute('SELECT plea_canonical(%s::jsonb)', (json.dumps(v),)).fetchone()[0] == _canonical(v): n_can += 1
        for _ in range(100):
            prev, seq, op, kind, code, obs = rnd.choice([GENESIS, 'ab' * 32]), rnd.randrange(1, 10 ** 12), rand_op(), rnd.choice(['APPLIED', 'DENIED', 'NOOP', 'DUPLICATE']), rnd.choice(specials), rand_obs()
            body = {'seq': seq, 'op': op, 'kind': kind, 'code': code, 'observation': obs}
            if c.execute('SELECT plea_decision_hash(%s, %s::jsonb)', (prev, json.dumps(body))).fetchone()[0] == chain_hash(prev, seq, op, kind, code, obs): n_hash += 1
    checks.append((f'plea_canonical equals the client canonical form on 300 random values with special characters ({n_can}/300)', n_can == 300))
    checks.append((f'plea_decision_hash equals the client chain_hash on 100 random decision bodies ({n_hash}/100)', n_hash == 100))
    checks.append(('the database refuses a non-integer number in a canonical form (nothing to diverge on)',
                   refused('x', lambda: (lambda c: c.execute("SELECT plea_canonical('1.5'::jsonb)").fetchone())(admin.connect()), psycopg.errors.CheckViolation)[1]))

    # --- every genuine decision applies and the record it leaves is the real one
    root = 'u1-ok'; fresh_root(admin, root, 3, 1); kinds = []
    for st, op in [(local, ('RESERVE', 'a1', 'q1')), (witness, ('ACCEPT_RESERVATION', 'a1')), (local, ('TOKEN', 'a1')), (local, ('START', 'a1', 'n1')),
                   (witness, ('ACCEPT_INTENT', 'a1')), (local, ('RECEIPT', 'a1')), (witness, ('CROSS', 'a1')), (witness, ('RECONCILE', 'a1', 'EFFECT', 'AUTHORISED')),
                   (local, ('RESERVE', 'a1', 'q1')), (local, ('TIMEOUT', 'a1')), (local, ('RESERVE', 'a2', 'q2')), (witness, ('ACCEPT_RESERVATION', 'a2')),
                   (witness, ('RELEASE', 'a2', 'BOUND_FENCE')), (control, ('HOLD',)), (control, ('RECOVER', True, True)), (control, ('STOP',)),
                   (control, ('TERMINALISE',)), (control, ('TERMINAL',))]:
        d, _ = st.apply(root, op); kinds.append(d.kind)
    checks.append(('a full lifecycle, a duplicate, a no-op, a release, hold/recover and stop/terminalise/terminal all apply through their credentials',
                   kinds == ['APPLIED'] * 8 + ['DUPLICATE', 'NOOP'] + ['APPLIED'] * 8))
    log = admin.audit(root)
    checks.append(('every stored observation is the database\'s own, equal to the client\'s, and APPLIED records are exactly the ones that change it',
                   all(((log[i]['observation'] != (log[i - 1]['observation'] if i else _jsonable(ref.observe(ref.initial(3, 1))))) == (log[i]['kind'] == 'APPLIED')) for i in range(len(log)))))
    checks.append(('verify_chain and replay lockstep hold on the lifecycle root', admin.verify_chain(root)[0] and replay_lockstep(admin, root, 3, 1)[0]))
    root = 'u1-rereg'; fresh_root(admin, root, 3, 0)
    for st, op in [(local, ('RESERVE', 'a1', 'q1')), (witness, ('ACCEPT_RESERVATION', 'a1')), (local, ('TOKEN', 'a1')), (local, ('START', 'a1', 'n7')), (witness, ('ACCEPT_INTENT', 'a1'))]:
        st.apply(root, op)
    d, o = control.apply(root, ('REREGISTER',))
    checks.append(('REREGISTER (attempts to INDETERMINATE, witness ACTIVE, business STOPPING, reregistered) applies and lockstep holds',
                   d.kind == 'APPLIED' and o['business'] == 'STOPPING' and o['reregistered'] and replay_lockstep(admin, root, 3, 0)[0]))
    return checks


# ============================================================ U2: provisioning authority
def u2(svc):
    checks = []
    with admin.connect() as c:
        c.execute("DELETE FROM roots WHERE root_id LIKE 'u2-%'"); c.commit()
    checks.append(refused('the gateway credential cannot create a root', lambda: local.new_root('u2-gw', 5, 0), AuthorityError))
    checks.append(refused('the witness credential cannot create a root', lambda: witness.new_root('u2-wit', 5, 0), AuthorityError))
    control.new_root('u2-ctl', 2, 1); o = admin.observe('u2-ctl')
    checks.append(('the control credential provisions a root with the budget given', (o['k'], o['m']) == (2, 1)))
    checks.append(('no root exists for the refused creations', all(not _exists(r) for r in ('u2-gw', 'u2-wit'))))
    # the reviewer's probe: a budget-one root exhausted, then the gateway tries a fresh k=1000 root
    control.new_root('u2-one', 1, 0)
    first, _ = local.apply('u2-one', ('RESERVE', 'a1', 'q1')); second, _ = local.apply('u2-one', ('RESERVE', 'a2', 'q2'))
    checks.append(refused("the reviewer's probe: after exhausting a budget-one root, plea_local creating a k=1000, m=999 root is refused",
                          lambda: local.new_root('u2-extra', 1000, 999), AuthorityError))
    third, _ = local.apply('u2-one', ('RESERVE', 'a3', 'q3'))
    checks.append(('the gateway stays exhausted on its root and has no other', first.kind == 'APPLIED' and second.kind == third.kind == 'DENIED' and second.code == 'BUDGET_EXHAUSTED' and not _exists('u2-extra')))
    checks.append(refused('a governor holding only the gateway credential refuses an unprovisioned root, naming the provisioning step',
                          lambda: Governor(Store(LOCAL_DSN), None, 'u2-unprov', 3, 0, gate=GATE), UnknownRoot))
    g = Governor(Store(LOCAL_DSN), None, 'u2-byctl', 2, 1, gate=GATE, control=control); o = admin.observe('u2-byctl')
    checks.append(('a governor given the control credential provisions the root (k=2, m=1)', (o['k'], o['m']) == (2, 1)))
    Governor(Store(LOCAL_DSN), None, 'u2-byctl', 9, 9, gate=GATE, control=control); o = admin.observe('u2-byctl')
    checks.append(('a second governor on the provisioned root does not change its immutable budget', (o['k'], o['m']) == (2, 1)))
    g2 = Governor(Store(LOCAL_DSN), None, 'u2-byctl', 2, 1, gate=GATE)
    checks.append(('a gateway-only governor then runs against the provisioned root', g2.status()['k'] == 2))
    env = dict(os.environ, PLEA_CONTROL_DSN=CONTROL_DSN)
    out1 = subprocess.run([PYTHON, '-B', 'plea_ctl.py', 'u2-cli', 'provision', '--budget', '4', '--replacement', '2'], cwd=str(MCP), capture_output=True, text=True, env=env).stdout.strip()
    out2 = subprocess.run([PYTHON, '-B', 'plea_ctl.py', 'u2-cli', 'provision', '--budget', '7'], cwd=str(MCP), capture_output=True, text=True, env=env).stdout.strip()
    o = admin.observe('u2-cli')
    checks.append(('plea_ctl provision creates the root through the control credential and reports an existing one', out1.startswith('PROVISIONED') and out2.startswith('EXISTS') and (o['k'], o['m']) == (4, 2)))
    with admin.connect() as c:
        acl = {n: c.execute("SELECT EXISTS(SELECT 1 FROM aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) WHERE grantee = 0 AND privilege_type = 'EXECUTE') FROM pg_proc p WHERE p.oid = to_regprocedure(%s)", (sig,)).fetchone()[0]
               for n, sig in [('plea_new_root', 'public.plea_new_root(text,integer,integer)'), ('plea_jstr', 'public.plea_jstr(text)'), ('plea_canonical', 'public.plea_canonical(jsonb)'), ('plea_decision_hash', 'public.plea_decision_hash(text,jsonb)'), ('plea_observe', 'public.plea_observe(text)')]}
        grantees = c.execute("SELECT array_agg(pg_get_userbyid(grantee) ORDER BY 1) FROM aclexplode((SELECT proacl FROM pg_proc WHERE oid = to_regprocedure('public.plea_new_root(text,integer,integer)'))) WHERE privilege_type = 'EXECUTE'").fetchone()[0]
    checks.append(('PUBLIC holds no EXECUTE on plea_new_root nor on the four helpers; plea_new_root is granted to the owner and the control plane only',
                   all(not v for v in acl.values()) and sorted(grantees) == ['plea', 'plea_control']))
    checks.append(('no login role can call the helpers directly',
                   all(not _ok(d, 'SELECT plea_observe(%s)', ('u2-ctl',)) for d in (LOCAL_DSN, WITNESS_DSN, CONTROL_DSN))))
    # the agent-facing server holds plea_local only: it refuses an unprovisioned root and runs against a provisioned one
    env = dict(os.environ, PLEA_LOCAL_DSN=LOCAL_DSN, PLEA_ADMIN_DSN='', PLEA_CONTROL_DSN='')
    base = [PYTHON, '-B', 'plea_mcp.py', '--budget', '2', '--witness-url', svc.url, '--gate-key', GATE.private_hex, '--tools', 'demo_tools', '--local-dsn', LOCAL_DSN]
    p = subprocess.run(base + ['--root', 'u2-mcp-unprov'], cwd=str(MCP), capture_output=True, text=True, env=env, timeout=60, input='')
    checks.append(('plea_mcp.py with only the gateway credential refuses to start against an unprovisioned root, naming the provisioning step',
                   p.returncode != 0 and 'not provisioned' in (p.stderr + p.stdout) and 'plea_ctl.py u2-mcp-unprov provision' in (p.stderr + p.stdout)))
    control.new_root('u2-mcp', 2, 0)
    p = subprocess.Popen(base + ['--root', 'u2-mcp'], cwd=str(MCP), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, bufsize=1)
    got = []
    t = threading.Thread(target=lambda: got.append(p.stdout.readline()), daemon=True)
    try:
        p.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}}) + '\n'); p.stdin.flush()
        t.start(); t.join(30)
    finally:
        p.kill(); p.wait(timeout=5)
    reply = json.loads(got[0]) if got and got[0].strip() else {}
    checks.append(('plea_mcp.py with only the gateway credential starts against the provisioned root and answers initialize', reply.get('id') == 1 and 'result' in reply))
    return checks


def _exists(root):
    try:
        admin.observe(root); return True
    except UnknownRoot:
        return False


def _ok(dsn, sql, params=()):
    try:
        with psycopg.connect(dsn) as c:
            c.execute(sql, params); return True
    except psycopg.Error:
        return False


def main():
    t0 = time.time()
    svc = WitnessService(8995, key=WITNESS_KEY); svc.start(); w = RemoteWitness(svc.url, WITNESS_PUB)
    try:
        out = {'U1': u1(w), 'U2': u2(svc)}
    finally:
        svc.stop()
    out['seconds'] = round(time.time() - t0, 1)
    for k in ('U1', 'U2'):
        out[k + '_ok'] = all(ok for _, ok in out[k]); out[k + '_count'] = len(out[k])
    out['PASS'] = all(out[k + '_ok'] for k in ('U1', 'U2'))
    write_output('u_tests.json', out)
    for k in ('U1', 'U2'):
        for label, ok in out[k]:
            print(k, 'ok  ' if ok else 'FAIL', label)
    print(json.dumps({k: v for k, v in out.items() if k not in ('U1', 'U2')}, indent=1))
    print('U RESULT:', 'PASS' if out['PASS'] else 'FAIL'); raise SystemExit(0 if out['PASS'] else 1)


if __name__ == '__main__':
    main()
