#!/usr/bin/env python3
"""X1-X4 (v1.2): the repairs for the v1.1 independent review's findings P1-P4.  Written before the repair and run first
against the shipped v1.1 (outputs/review7/x_tests_before_v1_1.*), whose failures are kept, then against v1.2.

X1 provisioning anchor (P1, P2).  A budget's origin is part of its audit history.  plea_new_root appends an immutable
   record to the provisioning log -- the root, k, m, the issuing credential, the contract and release, the database
   time -- hash-linked to the record before it; the root's chain starts at that record's hash (its anchor), computed by
   the database: no caller supplies a starting hash.  The reviewer's probe B (a 4-argument call with a caller-chosen
   genesis) is refused.  No login role writes the log; the owner cannot rewrite or remove a record, nor change a root's
   budget; verify_chain checks the anchor and the budget against the record, and refuses an unanchored root.

X2 every operand bound (P3).  plea_write evaluates the contract's own decision for the recorded operation on the real
   state before the write, and the record must be exactly it: the kind, the code, and every row and mode the write
   changed.  So the reviewer's probes C (one attempt logged, another inserted) and D (two reservations under one
   RESERVE) are refused, and so is every forgery that names the right operation over the wrong operands (attempt,
   request, nonce, verdict, evidence label), changes part of a batch (RECOVER, REREGISTER) or one row too many, or
   applies a transition the mode forbids (TOKEN while HELD, CROSS while HELD, ...).  Each forgery passes every v1.1
   rule -- the operation name, observation and hash are right -- so only the new binding can refuse it.  A mutation
   sweep over random walks checks, for every mutated record, that the database accepts it exactly when it is the
   contract's own decision.  Systematic forgeries are written in a transaction that is rolled back; the reviewer's
   probes are committed, to show a refusal leaves no trace.

X3 refusal records (P4).  A refusal is checked as strictly as a change: the reviewer's probe E (STOP recorded as DENIED
   on an OPEN run) is refused for every credential, an invented code is refused, a refusal of a control-plane or
   witness operation can only be recorded by that credential, and a NOOP or DUPLICATE the contract would apply is
   refused.  The declared limit is shown, not hidden: a refusal the contract gives for the current state (a RESERVE
   on an exhausted budget) can still be recorded for a request that never reached the gateway.  It changes nothing.

X4 the database's contract engine.  plea_step, the contract's single-root step in PL/pgSQL, agrees with the reference
   engine (kind, code, observation) and with the independent oracle (kind, observation) on every pair of a complete
   bounded exploration; it rejects exactly the malformed operations the reference's parser rejects; and it is the
   owner's alone.
"""
import hashlib
import json
import os
import random
import subprocess
import threading
import time

import psycopg

from common import (ADMIN_DSN, CONTROL_DSN, GATEWAY, LOCAL_DSN, O, PYTHON, WITNESS_DSN, Store, replay_lockstep,
                    write_output)
from plea_gateway import AuthorityError
from plea_gateway import plea_budget_ref as ref
from plea_gateway.store import GENESIS, _canonical, _jsonable, chain_hash

admin, local, witness, control = Store(ADMIN_DSN), Store(LOCAL_DSN), Store(WITNESS_DSN), Store(CONTROL_DSN)
MCP = GATEWAY / 'mcp'
WITNESS_OPS = ('ACCEPT_RESERVATION', 'ACCEPT_INTENT', 'RELEASE', 'RECONCILE', 'CROSS')
CONTROL_OPS = ('HOLD', 'STOP', 'TERMINALISE', 'TERMINAL', 'RECOVER', 'REREGISTER')
NAMED = ('RESERVE', 'ACCEPT_RESERVATION', 'TOKEN', 'START', 'ACCEPT_INTENT', 'RECEIPT', 'CROSS', 'RELEASE', 'RECONCILE',
         'TIMEOUT', 'MISSING_RECEIPT')
ONE_AID = ('ACCEPT_RESERVATION', 'TOKEN', 'ACCEPT_INTENT', 'RECEIPT', 'CROSS', 'TIMEOUT', 'MISSING_RECEIPT')
NO_ARG = ('CRASH', 'HOLD', 'STOP', 'TERMINALISE', 'TERMINAL', 'REREGISTER')
PROVISION_FIELDS = ('record', 'seq', 'root', 'k', 'm', 'issuer', 'contract', 'release', 'created_at')


# ------------------------------------------------------------------ harness
def run(checks, label, fn):
    """One check: fn() -> (ok, detail).  An exception is a failure with its reason (so the v1.1 run completes)."""
    try:
        ok, detail = fn()
    except Exception as exc:                                             # noqa: BLE001
        ok, detail = False, f'{type(exc).__name__}: {(str(exc).splitlines() or [""])[0][:200]}'
    checks.append((label if ok else f'{label} -- {detail}', bool(ok)))
    return ok


def dsn_for(op):
    return WITNESS_DSN if op[0] in WITNESS_OPS else CONTROL_DSN if op[0] in CONTROL_OPS else LOCAL_DSN


def store_of(dsn):
    return {ADMIN_DSN: admin, LOCAL_DSN: local, WITNESS_DSN: witness, CONTROL_DSN: control}[dsn]


def allowed(op, dsn):
    """May this credential record this operation at all (applied or refused)?  Witness operations: the witness.
    Control-plane operations: the control plane (v1.2, refusals included).  The rest: any writer."""
    if op[0] in WITNESS_OPS:
        return dsn in (WITNESS_DSN, ADMIN_DSN)
    if op[0] in CONTROL_OPS:
        return dsn in (CONTROL_DSN, ADMIN_DSN)
    return True


def sql(dsn, q, params=(), fetch=False):
    with psycopg.connect(dsn) as c:
        cur = c.execute(q, params)
        res = cur.fetchall() if fetch else None
        c.commit()
        return res


def attempt_sql(dsn, q, params=()):
    """(ok, sqlstate, message): one statement, committed; never raises."""
    try:
        with psycopg.connect(dsn) as c:
            c.execute(q, params); c.commit()
        return True, None, None
    except psycopg.Error as e:
        return False, e.sqlstate, (str(e).splitlines() or [''])[0][:200]


def head(root):
    r = sql(ADMIN_DSN, 'SELECT seq, head_hash FROM roots WHERE root_id = %s', (root,), fetch=True)
    return tuple(r[0]) if r else None


def snapshot(root):
    return head(root), len(admin.audit(root)), admin.observe(root)


def provision(root, k, m, by=None):
    """A fresh root: the owner removes any earlier one, then the control plane (or `by`) provisions it."""
    sql(ADMIN_DSN, 'DELETE FROM roots WHERE root_id = %s', (root,))
    (by or control).new_root(root, k, m)


def apply(root, op):
    """The genuine path: the store of the credential that performs the operation decides and writes it."""
    d, _ = store_of(dsn_for(op)).apply(root, tuple(op))
    return d


def row_of(a):
    return {'aid': a.aid, 'req': a.req, 'phase': a.phase.value, 'nonce': a.nonce, 'receipt': a.receipt, 'crossed': a.crossed}


def payload(pre, post):
    """The rows and modes a genuine write of pre -> post carries (as Store._apply_in builds them)."""
    before = {a.aid: a for a in pre.attempts}
    rows = [row_of(a) for a in post.attempts if before.get(a.aid) != a]
    modes = None
    if (post.witness, post.business, post.reregistered) != (pre.witness, pre.business, pre.reregistered):
        modes = {'witness': post.witness.value, 'business': post.business.value, 'reregistered': post.reregistered}
    return rows, modes


def record(root, op):
    """The contract's record for op on the root's current state: rows, modes, kind, code, observation, pre, post."""
    pre, _, _ = admin.state(root)
    d, post = ref.apply(pre, ref.parse_op(tuple(op)))
    rows, modes = payload(pre, post) if d.kind.value == 'APPLIED' else ([], None)
    return rows, modes, d.kind.value, d.code, _jsonable(ref.observe(post)), pre, post


def write(dsn, root, rows, modes, op, kind, code, obs, commit=True, evidence=None):
    """A hand-written plea_write at the root's chain position, with the hash the client computes over exactly this
    record, and optionally an evidence row.  (accepted, sqlstate, message).  commit=False rolls back whatever the outcome."""
    seq, h = head(root)
    digest = chain_hash(h, seq + 1, list(op), kind, code, obs)
    try:
        with psycopg.connect(dsn) as c:
            c.execute('SELECT plea_write(%s, %s::jsonb, %s::jsonb, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s::jsonb)',
                      (root, json.dumps(rows), json.dumps(modes) if modes is not None else None, seq + 1, digest,
                       json.dumps(list(op)), kind, code, json.dumps(obs), h, json.dumps(evidence) if evidence is not None else None))
            c.commit() if commit else c.rollback()
        return True, None, None
    except psycopg.Error as e:
        return False, e.sqlstate, (str(e).splitlines() or [''])[0][:200]


def forge_named(root, true_op, named_op, commit=False):
    """The contract's record for true_op, naming named_op instead (same operation name, other operands), written by
    the credential that performs true_op.  Passes every v1.1 rule; ok when refused and nothing changed."""
    rows, modes, kind, code, obs, _, _ = record(root, true_op)
    snap = snapshot(root)
    ok, st, msg = write(dsn_for(true_op), root, rows, modes, named_op, kind, code, obs, commit=commit)
    clean = snapshot(root) == snap
    return (not ok) and clean, f'{list(named_op)} for {list(true_op)}: accepted={ok} {st} {msg} clean={clean}'


def simulate(pre, rows, modes):
    """The state a payload produces from pre (the rows upserted, the modes set).  Raises InvalidInput when invalid."""
    facts = {a.aid: a for a in pre.attempts}
    for r in rows:
        facts[r['aid']] = ref.AttemptFacts(r['aid'], r['req'], r['phase'], r['nonce'], r['receipt'], r['crossed'])
    w, b, rr = (modes['witness'], modes['business'], modes['reregistered']) if modes else (pre.witness, pre.business, pre.reregistered)
    return ref.RootState(pre.k, pre.m, w, b, tuple(facts.values()), rr)


def forge_payload(root, op, rows, modes, dsn=None, code=None, commit=False):
    """A record of op over the given payload, with the observation that payload really produces and kind APPLIED:
    consistent with every v1.1 rule when the rows are shaped right.  ok when refused and nothing changed."""
    pre, _, _ = admin.state(root)
    obs = _jsonable(ref.observe(simulate(pre, rows, modes)))
    true_code = code or ref.apply(pre, ref.parse_op(tuple(op)))[0].code
    snap = snapshot(root)
    ok, st, msg = write(dsn or dsn_for(op), root, rows, modes, op, 'APPLIED', true_code, obs, commit=commit)
    clean = snapshot(root) == snap
    return (not ok) and clean, f'{list(op)}: accepted={ok} {st} {msg} clean={clean}'


# ============================================================ X1: provisioning anchor (P1, P2)
def x1():
    checks = []

    def record_written():
        provision('x1-a', 3, 1)
        p = admin.provisioning('x1-a')
        want = {'record': 'PROVISION', 'root': 'x1-a', 'k': 3, 'm': 1, 'issuer': 'plea_control'}
        ok = p is not None and all(p.get(k) == v for k, v in want.items()) and all(p.get(k) for k in ('contract', 'release', 'created_at'))
        return ok, json.dumps(p)[:240]
    run(checks, 'provisioning by the control plane appends a record naming the root, k, m, the issuer (plea_control), the contract, the release and the database time', record_written)

    def anchor():
        p = admin.provisioning('x1-a'); seq, h = head('x1-a')
        recomputed = hashlib.sha256((p['prev_hash'] + _canonical({f: p[f] for f in PROVISION_FIELDS})).encode()).hexdigest()
        return (seq == 0 and h == p['hash'] == recomputed and h != GENESIS), f'head {h[:12]} record {p["hash"][:12]} recomputed {recomputed[:12]}'
    run(checks, "the root's chain starts at the record's hash (its anchor, never the fixed genesis), and the hash recomputes from the record outside the database", anchor)

    def linked():
        for op in [('RESERVE', 'a1', 'q1'), ('ACCEPT_RESERVATION', 'a1'), ('TOKEN', 'a1'), ('START', 'a1', 'n1'), ('ACCEPT_INTENT', 'a1'),
                   ('RECEIPT', 'a1'), ('CROSS', 'a1'), ('RECONCILE', 'a1', 'NO_EFFECT', 'AUTHORISED')]:
            apply('x1-a', op)
        log = admin.audit('x1-a'); p = admin.provisioning('x1-a')
        v, lock = admin.verify_chain('x1-a'), replay_lockstep(admin, 'x1-a', 3, 1)
        return (len(log) == 8 and log[0]['prev_hash'] == p['hash'] and v[0] and lock[0]), f'first prev {log[0]["prev_hash"][:12]} chain {v} lockstep {lock}'
    run(checks, 'the first decision links to the anchor; after a full lifecycle verify_chain and replay lockstep hold', linked)

    def probe_b():
        res = []
        for who, dsn in (('control', CONTROL_DSN), ('owner', ADMIN_DSN)):
            r = f'x1-badgen-{who}'
            sql(ADMIN_DSN, 'DELETE FROM roots WHERE root_id = %s', (r,))
            ok, st, msg = attempt_sql(dsn, 'SELECT public.plea_new_root(%s, %s, %s, %s)', (r, 1, 0, '0' * 64))
            exists = bool(sql(ADMIN_DSN, 'SELECT 1 FROM roots WHERE root_id = %s', (r,), fetch=True))
            res.append((who, ok, st, exists))
        return all(not ok and not exists for _, ok, _, exists in res), str(res)
    run(checks, "the reviewer's probe B: a caller-chosen starting hash (the 4-argument call) is refused to the control plane and to the owner, and no root exists", probe_b)

    def no_gateway():
        out = []
        for name, st in (('gateway', local), ('witness', witness)):
            sql(ADMIN_DSN, 'DELETE FROM roots WHERE root_id = %s', (f'x1-{name}',))
            try:
                st.new_root(f'x1-{name}', 5, 0); out.append((name, 'created'))
            except AuthorityError:
                out.append((name, 'refused'))
        return all(v == 'refused' for _, v in out), str(out)
    run(checks, 'the gateway and the witness credentials cannot provision', no_gateway)

    def no_direct_dml():
        res = {}
        for name, dsn in (('gateway', LOCAL_DSN), ('witness', WITNESS_DSN), ('control', CONTROL_DSN)):
            ins = attempt_sql(dsn, "INSERT INTO provisions (seq, root_id, k, m, issuer, contract, release, created_at, prev_hash, hash) "
                                   "VALUES (999999, 'x1-direct', 100, 0, 'me', 'c', 'r', 't', 'p', 'h')")
            upd = attempt_sql(dsn, 'UPDATE provisions SET k = k + 1')
            dele = attempt_sql(dsn, 'DELETE FROM provisions')
            res[name] = (ins[1], upd[1], dele[1])
        return all(all(s == '42501' for s in v) for v in res.values()), str(res)
    run(checks, 'no login role can insert, update or delete a provisioning record directly (insufficient privilege)', no_direct_dml)

    def append_only():
        before = admin.provisioning('x1-a')
        upd = attempt_sql(ADMIN_DSN, "UPDATE provisions SET k = k + 1 WHERE root_id = 'x1-a'")
        dele = attempt_sql(ADMIN_DSN, "DELETE FROM provisions WHERE root_id = 'x1-a'")
        trunc = attempt_sql(ADMIN_DSN, 'TRUNCATE provisions')
        v = admin.verify_chain('x1-a')
        return (before is not None and admin.provisioning('x1-a') == before and not upd[0] and not dele[0] and not trunc[0] and v[0]), \
            f'update {upd[1]} delete {dele[1]} truncate {trunc[1]} chain {v}'
    run(checks, 'the owner cannot rewrite, remove or truncate a provisioning record (the log is append-only)', append_only)

    def budget_fixed():
        r1 = attempt_sql(ADMIN_DSN, "UPDATE roots SET k = k + 100 WHERE root_id = 'x1-a'")
        r2 = attempt_sql(ADMIN_DSN, "UPDATE roots SET m = m + 1 WHERE root_id = 'x1-a'")
        o = admin.observe('x1-a')
        return (not r1[0] and not r2[0] and (o['k'], o['m']) == (3, 1)), f'k {r1[1]} m {r2[1]} now k={o["k"]} m={o["m"]}'
    run(checks, "the owner cannot change a provisioned root's budget k or allowance m", budget_fixed)

    def detects_budget():
        tampered, v = False, None
        try:
            with psycopg.connect(ADMIN_DSN) as c:
                c.execute('ALTER TABLE roots DISABLE TRIGGER roots_immutable')
                c.execute("UPDATE roots SET k = k + 7 WHERE root_id = 'x1-a'"); c.commit(); tampered = True
            v = admin.verify_chain('x1-a')
        finally:
            if tampered:
                with psycopg.connect(ADMIN_DSN) as c:
                    c.execute("UPDATE roots SET k = k - 7 WHERE root_id = 'x1-a'")
                    c.execute('ALTER TABLE roots ENABLE TRIGGER roots_immutable'); c.commit()
        v2 = admin.verify_chain('x1-a')
        return (v is not None and not v[0] and v2[0]), f'tampered {v} restored {v2}'
    run(checks, 'verify_chain detects a budget that differs from its provisioning record (the owner bypassing the trigger), and holds again once restored', detects_budget)

    def detects_anchor():
        provision('x1-b', 1, 0)
        sql(ADMIN_DSN, 'UPDATE roots SET head_hash = %s WHERE root_id = %s', ('0' * 64, 'x1-b'))
        v = admin.verify_chain('x1-b')
        return (not v[0]), str(v)
    run(checks, 'verify_chain detects a root whose chain no longer starts at its anchor', detects_anchor)

    def unprovisioned():
        sql(ADMIN_DSN, 'DELETE FROM roots WHERE root_id = %s', ('x1-bare',))
        ins = attempt_sql(ADMIN_DSN, "INSERT INTO roots (root_id, k, m, witness, business, head_hash) VALUES ('x1-bare', 2, 0, 'ACTIVE', 'OPEN', %s)", (GENESIS,))
        if not ins[0]:
            return True, f'the database holds no unprovisioned root ({ins[1]})'
        rows, modes, kind, code, obs, _, _ = record('x1-bare', ('RESERVE', 'a1', 'q1'))
        ok, st, msg = write(LOCAL_DSN, 'x1-bare', rows, modes, ('RESERVE', 'a1', 'q1'), kind, code, obs)
        v = admin.verify_chain('x1-bare')
        return (not ok and not v[0]), f'write accepted={ok} {st} {msg} chain {v}'
    run(checks, 'a root with no provisioning record (as a pre-v1.2 root would be) is not written to, and verify_chain refuses it', unprovisioned)

    def reprovisioned():
        provision('x1-c', 1, 0); p1 = admin.provisioning('x1-c')
        provision('x1-c', 4, 2); p2 = admin.provisioning('x1-c')
        n = sql(ADMIN_DSN, "SELECT count(*) FROM provisions WHERE root_id = 'x1-c'", fetch=True)[0][0]
        v, vp = admin.verify_chain('x1-c'), admin.verify_provisioning()
        return (p2['seq'] > p1['seq'] and (p2['k'], p2['m']) == (4, 2) and n == 2 and v[0] and vp[0]), f'seq {p1["seq"]}->{p2["seq"]} records {n} chain {v} log {vp}'
    run(checks, 'a root identity provisioned again after the owner removed the root gets a new record; the earlier one stays and the whole log verifies', reprovisioned)

    def concurrent():
        before = sql(ADMIN_DSN, 'SELECT count(*) FROM provisions', fetch=True)[0][0]
        names = [f'x1-par-{i}' for i in range(16)]
        for n in names:
            sql(ADMIN_DSN, 'DELETE FROM roots WHERE root_id = %s', (n,))
        errs = []

        def go(n):
            try:
                Store(CONTROL_DSN).new_root(n, 2, 0)
            except Exception as e:                                            # noqa: BLE001
                errs.append(repr(e)[:120])
        ts = [threading.Thread(target=go, args=(n,)) for n in names]
        [t.start() for t in ts]; [t.join() for t in ts]
        cnt, lo, hi = sql(ADMIN_DSN, 'SELECT count(*), min(seq), max(seq) FROM provisions', fetch=True)[0]
        vp = admin.verify_provisioning()
        return (not errs and cnt == before + 16 and hi - lo + 1 == cnt and vp[0]), f'errors {errs[:2]} records {before}->{cnt} seq {lo}..{hi} log {vp}'
    run(checks, '16 concurrent provisioning calls leave a contiguous, linked log', concurrent)

    def acl():
        with psycopg.connect(ADMIN_DSN) as c:
            old = c.execute("SELECT to_regprocedure('public.plea_new_root(text,integer,integer,text)')").fetchone()[0]
            new = c.execute("SELECT to_regprocedure('public.plea_new_root(text,integer,integer)')").fetchone()[0]
            grantees = c.execute("SELECT array_agg(pg_get_userbyid(grantee) ORDER BY 1) FROM aclexplode((SELECT proacl FROM pg_proc "
                                 "WHERE oid = to_regprocedure('public.plea_new_root(text,integer,integer)')))").fetchone()[0]
            pub = c.execute("SELECT has_function_privilege('public', 'public.plea_new_root(text,integer,integer)', 'EXECUTE')").fetchone()[0]
            tab = {r: c.execute("SELECT has_table_privilege(%s, 'public.provisions', 'SELECT'), has_table_privilege(%s, 'public.provisions', 'INSERT'), "
                                "has_table_privilege(%s, 'public.provisions', 'UPDATE'), has_table_privilege(%s, 'public.provisions', 'DELETE')",
                                (r, r, r, r)).fetchone() for r in ('plea_local', 'plea_witness', 'plea_control')}
        ok = old is None and new is not None and grantees == ['plea', 'plea_control'] and not pub and all(v == (True, False, False, False) for v in tab.values())
        return ok, f'old {old} new {new} grantees {grantees} public {pub} provisions {tab}'
    run(checks, 'the 4-argument signature no longer exists; plea_new_root(text,int,int) is the owner\'s and the control plane\'s only; login roles may read the log and not write it', acl)

    def ctl():
        sql(ADMIN_DSN, 'DELETE FROM roots WHERE root_id = %s', ('x1-ctl',))
        p1 = subprocess.run([PYTHON, '-B', str(MCP / 'plea_ctl.py'), 'x1-ctl', 'provision', '--budget', '2', '--control-dsn', CONTROL_DSN],
                            capture_output=True, text=True, timeout=60)
        p2 = subprocess.run([PYTHON, '-B', str(MCP / 'plea_ctl.py'), 'x1-ctl', 'provenance', '--control-dsn', CONTROL_DSN],
                            capture_output=True, text=True, timeout=60)
        rec = admin.provisioning('x1-ctl')
        ok = (p1.returncode == 0 and 'PROVISIONED' in p1.stdout and rec is not None and rec['hash'] in p1.stdout
              and p2.returncode == 0 and rec['hash'] in p2.stdout and 'chain ok' in p2.stdout)
        return ok, f'{p1.stdout.strip()[:140]} | {p2.stdout.strip()[-140:]} | {(p1.stderr + p2.stderr).strip()[-160:]}'
    run(checks, 'plea_ctl provision prints the anchor, and plea_ctl provenance prints the record and verifies the chain', ctl)
    return checks


# ============================================================ X2: every operand bound (P3)
def x2():
    checks = []

    def probe_c():
        provision('x2-c', 2, 0); snap = snapshot('x2-c')
        rows, modes, kind, code, obs, _, _ = record('x2-c', ('RESERVE', 'actual-aid', 'actual-request'))
        ok, st, msg = write(LOCAL_DSN, 'x2-c', rows, modes, ('RESERVE', 'declared-aid', 'declared-request'), kind, code, obs)
        return (not ok and snapshot('x2-c') == snap), f'accepted={ok} {st} {msg}'
    run(checks, "the reviewer's probe C: a RESERVE logged for one attempt while another is inserted is refused, as plea_local, and leaves no trace", probe_c)

    def probe_d():
        provision('x2-d', 2, 0); snap = snapshot('x2-d')
        pre, _, _ = admin.state('x2-d')
        _, s1 = ref.apply(pre, ref.parse_op(('RESERVE', 'a1', 'q1'))); _, s2 = ref.apply(s1, ref.parse_op(('RESERVE', 'a2', 'q2')))
        rows, _ = payload(pre, s2)
        ok, st, msg = write(LOCAL_DSN, 'x2-d', rows, None, ('RESERVE', 'a1', 'q1'), 'APPLIED', 'RESERVATION_COMMITTED', _jsonable(ref.observe(s2)))
        return (not ok and snapshot('x2-d') == snap), f'accepted={ok} {st} {msg}'
    run(checks, "the reviewer's probe D: two reservations under one RESERVE record are refused and leave no trace", probe_d)

    # --- the right operation over the wrong operands, for every single-attempt operation
    forged, genuine = [], []

    def fg(true_op, *named):
        for n in named:
            forged.append(forge_named('x2-ops', true_op, n))
        d = apply('x2-ops', true_op); genuine.append((list(true_op), d.kind))

    def operands():
        provision('x2-ops', 6, 1)
        fg(('RESERVE', 't1', 'r1'), ('RESERVE', 't2', 'r1'), ('RESERVE', 't1', 'r9'))
        for a in ('t2', 't3', 't4'):
            apply('x2-ops', ('RESERVE', a, 'r' + a[1]))
        fg(('ACCEPT_RESERVATION', 't1'), ('ACCEPT_RESERVATION', 't2'))
        for a in ('t2', 't3', 't4'):
            apply('x2-ops', ('ACCEPT_RESERVATION', a))
        fg(('TOKEN', 't1'), ('TOKEN', 't2')); apply('x2-ops', ('TOKEN', 't2'))
        fg(('RELEASE', 't3', 'BOUND_FENCE'), ('RELEASE', 't4', 'BOUND_FENCE'), ('RELEASE', 't3', 'NONE'))
        fg(('START', 't1', 'n1'), ('START', 't2', 'n1'), ('START', 't1', 'n9')); apply('x2-ops', ('START', 't2', 'n2'))
        fg(('ACCEPT_INTENT', 't1'), ('ACCEPT_INTENT', 't2')); apply('x2-ops', ('ACCEPT_INTENT', 't2'))
        fg(('RECEIPT', 't1'), ('RECEIPT', 't2')); apply('x2-ops', ('RECEIPT', 't2'))
        fg(('CROSS', 't1'), ('CROSS', 't2')); apply('x2-ops', ('CROSS', 't2'))
        fg(('RECONCILE', 't1', 'NO_EFFECT', 'AUTHORISED'), ('RECONCILE', 't2', 'NO_EFFECT', 'AUTHORISED'),
           ('RECONCILE', 't1', 'EFFECT', 'AUTHORISED'), ('RECONCILE', 't1', 'NO_EFFECT', 'NONE'))
        bad = [d for ok, d in forged if not ok]
        return (len(forged) == 14 and not bad), f'{len(forged) - len(bad)}/{len(forged)} refused; first not refused: {bad[:2]}'
    run(checks, 'each single-attempt operation recorded over the wrong operands (another attempt, request, nonce, verdict or evidence label) is refused, by the credential that performs it, with nothing changed (14 forgeries, every v1.1 rule satisfied)', operands)
    run(checks, 'each genuine record those forgeries imitate is accepted (9 operations, all APPLIED)',
        lambda: (len(genuine) == 9 and all(k == 'APPLIED' for _, k in genuine), str([(o[0], k) for o, k in genuine])))

    def batches():
        res = []
        provision('x2-rec', 4, 0)
        apply('x2-rec', ('RESERVE', 'b1', 'q1')); apply('x2-rec', ('RESERVE', 'b2', 'q2')); apply('x2-rec', ('HOLD',))
        pre, _, _ = admin.state('x2-rec')
        b1 = row_of(pre.attempt('b1')); b1['phase'] = 'DISCARDED'
        b2 = row_of(pre.attempt('b2')); b2['phase'] = 'DISCARDED'
        active = {'witness': 'ACTIVE', 'business': 'OPEN', 'reregistered': False}
        res.append(forge_payload('x2-rec', ('RECOVER', True, True), [b1], active))               # one of two discarded
        res.append(forge_payload('x2-rec', ('RECOVER', True, False), [b1, b2], active))         # incomplete, yet reactivated
        res.append((apply('x2-rec', ('RECOVER', True, True)).kind == 'APPLIED', 'the genuine RECOVER'))
        provision('x2-rr', 4, 0)
        for op in [('RESERVE', 'c1', 'q1'), ('RESERVE', 'c2', 'q2'), ('ACCEPT_RESERVATION', 'c2'), ('TOKEN', 'c2')]:
            apply('x2-rr', op)
        pre, _, _ = admin.state('x2-rr')
        c1 = row_of(pre.attempt('c1')); c1['phase'] = 'INDETERMINATE'
        res.append(forge_payload('x2-rr', ('REREGISTER',), [c1], {'witness': 'ACTIVE', 'business': 'STOPPING', 'reregistered': True}))
        res.append((apply('x2-rr', ('REREGISTER',)).kind == 'APPLIED', 'the genuine REREGISTER'))
        provision('x2-ar', 4, 0)
        apply('x2-ar', ('RESERVE', 'd1', 'q1')); apply('x2-ar', ('RESERVE', 'd2', 'q2'))
        pre, _, _ = admin.state('x2-ar')
        d1 = row_of(pre.attempt('d1')); d1['phase'] = 'RESERVED'
        d2 = row_of(pre.attempt('d2')); d2['phase'] = 'RESERVED'
        res.append(forge_payload('x2-ar', ('ACCEPT_RESERVATION', 'd1'), [d1, d2], None))
        bad = [d for ok, d in res if not ok]
        return not bad, f'{len(res) - len(bad)}/{len(res)}; failing: {bad[:2]}'
    run(checks, 'batch semantics: a RECOVER that discards one of two reservations, an incomplete RECOVER that reactivates the witness, a REREGISTER that freezes part of the unresolved attempts, and one ACCEPT_RESERVATION accepting two are refused; the genuine batches apply', batches)

    def guards():
        res = []
        held = {'witness': 'HELD', 'business': 'OPEN', 'reregistered': False}
        provision('x2-g1', 3, 0)
        for op in [('RESERVE', 'e1', 'q1'), ('ACCEPT_RESERVATION', 'e1'), ('HOLD',)]:
            apply('x2-g1', op)
        pre, _, _ = admin.state('x2-g1'); r = row_of(pre.attempt('e1')); r['phase'] = 'TOKEN'
        res.append(forge_payload('x2-g1', ('TOKEN', 'e1'), [r], None, code='TOKEN_RELEASED'))                       # TOKEN while HELD
        provision('x2-g2', 3, 0)
        for op in [('RESERVE', 'e1', 'q1'), ('ACCEPT_RESERVATION', 'e1'), ('TOKEN', 'e1'), ('STOP',)]:
            apply('x2-g2', op)
        pre, _, _ = admin.state('x2-g2'); r = row_of(pre.attempt('e1')); r.update(phase='INTENT_PENDING', nonce='n1')
        res.append(forge_payload('x2-g2', ('START', 'e1', 'n1'), [r], None, code='INTENT_COMMITTED_LOCALLY'))      # START in STOPPING
        provision('x2-g3', 3, 0); apply('x2-g3', ('HOLD',))
        res.append(forge_payload('x2-g3', ('RESERVE', 'e1', 'q1'), [{'aid': 'e1', 'req': 'q1', 'phase': 'RESERVING', 'nonce': None, 'receipt': False, 'crossed': False}],
                                 None, code='RESERVATION_COMMITTED'))                                                # RESERVE while HELD
        provision('x2-g4', 3, 0)
        for op in [('RESERVE', 'e1', 'q1'), ('ACCEPT_RESERVATION', 'e1'), ('TOKEN', 'e1'), ('START', 'e1', 'n1'), ('ACCEPT_INTENT', 'e1'), ('RECEIPT', 'e1'), ('HOLD',)]:
            apply('x2-g4', op)
        pre, _, _ = admin.state('x2-g4'); r = row_of(pre.attempt('e1')); r['crossed'] = True
        res.append(forge_payload('x2-g4', ('CROSS', 'e1'), [r], None, code='CROSSED'))                              # CROSS while HELD
        provision('x2-g5', 3, 0)
        for op in [('RESERVE', 'e1', 'q1'), ('STOP',), ('TERMINALISE',)]:
            apply('x2-g5', op)
        res.append(forge_payload('x2-g5', ('TERMINAL',), [], {'witness': 'ACTIVE', 'business': 'TERMINAL', 'reregistered': False}, code='TERMINAL'))  # unresolved attempts
        provision('x2-g6', 3, 0)
        for op in [('RESERVE', 'e1', 'q1'), ('ACCEPT_RESERVATION', 'e1'), ('TOKEN', 'e1'), ('START', 'e1', 'n1'), ('HOLD',)]:
            apply('x2-g6', op)
        pre, _, _ = admin.state('x2-g6'); r = row_of(pre.attempt('e1')); r['phase'] = 'CONSUMED'
        res.append(forge_payload('x2-g6', ('ACCEPT_INTENT', 'e1'), [r], None, code='INTENT_ACCEPTED'))              # ACCEPT_INTENT while HELD
        bad = [d for ok, d in res if not ok]
        return not bad, f'{len(res) - len(bad)}/{len(res)}; failing: {bad[:2]}'
    run(checks, 'a transition of the right shape that the mode forbids is refused: TOKEN, RESERVE and ACCEPT_INTENT while HELD, START while STOPPING, CROSS while HELD, TERMINAL with an unresolved attempt (6 records)', guards)

    def malformed():
        provision('x2-mal', 1, 0); snap = snapshot('x2-mal'); obs = admin.observe('x2-mal'); out = []
        for op in (['RESERVE', 'a1'], ['TOKEN', 5], ['TOKEN', ''], ['RELEASE', 'a1', 'MAYBE'], ['RECOVER', 'yes', 'no'], ['STOP', 'now'],
                   ['RECONCILE', 'a1', 'EFFECT']):
            ok, st, msg = write(CONTROL_DSN if op[0] in CONTROL_OPS else LOCAL_DSN, 'x2-mal', [], None, op, 'DENIED', 'X', obs)
            out.append((op, ok, st))
        return (all(not ok for _, ok, _ in out) and snapshot('x2-mal') == snap), str([(o, s) for o, ok, s in out if ok][:3] or out[:2])
    run(checks, 'a record of a malformed operation (wrong arity, a non-string or empty identity, an unknown label, a non-boolean flag) is refused (7 records)', malformed)

    def evidence_rows():
        provision('x2-ev', 4, 0)
        for op in [('RESERVE', 'e1', 'q1'), ('ACCEPT_RESERVATION', 'e1'), ('RESERVE', 'e2', 'q2'), ('ACCEPT_RESERVATION', 'e2'), ('RESERVE', 'e3', 'q3')]:
            apply('x2-ev', op)
        res = []
        # (a) the gateway records a genuine TIMEOUT and attaches an evidence row claiming the witness's next sequence slot
        seq, _ = head('x2-ev')
        rows, modes, kind, code, obs, _, _ = record('x2-ev', ('TIMEOUT', 'e1'))
        pre_empt = write(LOCAL_DSN, 'x2-ev', rows, modes, ('TIMEOUT', 'e1'), kind, code, obs, commit=True,
                         evidence={'aid': 'e1', 'seq': seq + 2, 'evidence': {'forged': True}, 'derived': 'BOUND_FENCE'})
        res.append((not pre_empt[0], f'gateway evidence row accepted={pre_empt[0]} {pre_empt[1]} {pre_empt[2]}'))
        if not pre_empt[0]:                       # keep the chain position the attack would have taken
            apply('x2-ev', ('TIMEOUT', 'e1'))
        # the witness's genuine RELEASE with its own evidence row, at the slot the gateway tried to take
        try:
            d, _, s2, _ = witness.apply_ex('x2-ev', ('RELEASE', 'e1', 'BOUND_FENCE'), {'report': 'fence'}, 'BOUND_FENCE')
            ev = admin.evidence_for('x2-ev', 'e1')
            res.append((d.kind == 'APPLIED' and [e['seq'] for e in ev] == [s2] and ev[0]['derived'] == 'BOUND_FENCE',
                        f'genuine RELEASE {d} evidence {ev}'))
        except Exception as exc:                                              # noqa: BLE001
            res.append((False, f'the genuine RELEASE failed after the gateway row: {type(exc).__name__}: {str(exc).splitlines()[0][:120]}'))
        # (b)-(e) the witness's own forgeries of the evidence row, each on a genuine RELEASE of e2 (rolled back)
        seq, _ = head('x2-ev')
        rows, modes, kind, code, obs, _, _ = record('x2-ev', ('RELEASE', 'e2', 'BOUND_FENCE'))
        for label, ev_row in (('another attempt', {'aid': 'e1', 'seq': seq + 1, 'evidence': {'r': 1}, 'derived': 'BOUND_FENCE'}),
                              ('another sequence number', {'aid': 'e2', 'seq': seq + 3, 'evidence': {'r': 1}, 'derived': 'BOUND_FENCE'}),
                              ('another label', {'aid': 'e2', 'seq': seq + 1, 'evidence': {'r': 1}, 'derived': 'NONE'})):
            ok, st, msg = write(WITNESS_DSN, 'x2-ev', rows, modes, ('RELEASE', 'e2', 'BOUND_FENCE'), kind, code, obs, commit=False, evidence=ev_row)
            res.append((not ok, f'witness evidence for {label}: accepted={ok} {st} {msg}'))
        rows, modes, kind, code, obs, _, _ = record('x2-ev', ('ACCEPT_RESERVATION', 'e3'))
        ok, st, msg = write(WITNESS_DSN, 'x2-ev', rows, modes, ('ACCEPT_RESERVATION', 'e3'), kind, code, obs, commit=False,
                            evidence={'aid': 'e3', 'seq': seq + 1, 'evidence': {'r': 1}, 'derived': 'AUTHORISED'})
        res.append((not ok, f'evidence on an operation that takes none: accepted={ok} {st} {msg}'))
        bad = [d for ok, d in res if not ok]
        return not bad, f'{len(res) - len(bad)}/{len(res)}; failing: {bad[:2]}'
    run(checks, "an evidence row belongs to its decision: the gateway cannot attach one (it could take the witness's next sequence slot and make the witness's RELEASE fail), and the witness's must name the decision's attempt, sequence number and label, on a RELEASE or RECONCILE only; the genuine RELEASE records its evidence", evidence_rows)

    walk = mutation_sweep()
    run(checks, f"mutation sweep: over {walk['genuine']} genuine decisions on 6 random walks, {walk['mutations']} mutated records (operands, operation name, a row added or dropped); the database accepted a mutated record exactly when it is the contract's own decision ({walk['truthful']} were, {walk['untruthful']} were not)",
        lambda: (walk['mismatch'] == 0 and walk['mutations'] > 1000 and walk['untruthful'] > 500, f"mismatches {walk['mismatch']}: {walk['examples'][:3]}"))
    run(checks, 'every genuine decision of the walks was accepted as the reference decided it; every walked chain verifies and replays in lockstep through the oracle',
        lambda: (walk['genuine_ok'] and walk['chains_ok'], f"genuine_ok {walk['genuine_ok']} chains {walk['chains']}"))
    walk2 = mutation_sweep(**SWEEP_B)
    run(checks, f"second mutation sweep (v1.2.1; another seed, budgets up to k=5 and m=3): over {walk2['genuine']} genuine decisions on 6 random walks, {walk2['mutations']} mutated records; the database accepted a mutated record exactly when it is the contract's own decision ({walk2['truthful']} were, {walk2['untruthful']} were not), every genuine decision was accepted, and every chain verifies and replays",
        lambda: (walk2['mismatch'] == 0 and walk2['genuine_ok'] and walk2['chains_ok'] and walk2['mutations'] > 1000 and walk2['untruthful'] > 500, f"mismatches {walk2['mismatch']}: {walk2['examples'][:3]} genuine_ok {walk2['genuine_ok']} chains {walk2['chains']}"))
    checks_meta['X2_sweep_b'] = {k: v for k, v in walk2.items() if k != 'examples'}
    checks_meta['X2_sweep_b']['examples'] = walk2['examples'][:10]
    checks_meta['X2_sweep'] = {k: v for k, v in walk.items() if k != 'examples'}
    checks_meta['X2_sweep']['examples'] = walk['examples'][:10]
    return checks


AIDS = ['a0', 'a1', 'a2', 'a3']


def next_op(rnd, s, aids=None):
    aids = aids or AIDS
    atts = {a.aid: a for a in s.attempts}

    def pick(phases, p=0.8):
        cands = sorted(a.aid for a in atts.values() if a.phase.value in phases)
        return rnd.choice(cands) if cands and rnd.random() < p else rnd.choice(aids + ['zz'])
    r = rnd.random()
    if r < 0.20:
        a = rnd.choice(aids)
        return ('RESERVE', a, 'q' + a if rnd.random() < 0.85 else 'q' + rnd.choice(aids))
    if r < 0.31: return ('ACCEPT_RESERVATION', pick(['RESERVING']))
    if r < 0.41: return ('TOKEN', pick(['RESERVED']))
    if r < 0.50:
        a = pick(['TOKEN'])
        return ('START', a, 'n' + a if rnd.random() < 0.85 else 'n' + rnd.choice(aids))
    if r < 0.58: return ('ACCEPT_INTENT', pick(['INTENT_PENDING']))
    if r < 0.65: return ('RECEIPT', pick(['CONSUMED', 'NO_EFFECT', 'EFFECT']))
    if r < 0.72: return ('CROSS', pick(['CONSUMED']))
    if r < 0.78: return ('RECONCILE', pick(['CONSUMED']), rnd.choice(['NO_EFFECT', 'EFFECT', 'EFFECT', 'UNKNOWN']),
                         rnd.choice(['AUTHORISED'] * 4 + ['NONE', 'WRONG_BINDING']))
    if r < 0.83: return ('RELEASE', pick(['RESERVED', 'TOKEN']), rnd.choice(['BOUND_FENCE'] * 4 + ['NONE', 'WRONG_BINDING']))
    if r < 0.86: return (rnd.choice(['TIMEOUT', 'MISSING_RECEIPT']), rnd.choice(aids + ['zz']))
    if r < 0.87: return ('CRASH',)
    if r < 0.915: return ('HOLD',)
    if r < 0.96: return ('RECOVER', rnd.random() < 0.9, rnd.random() < 0.7)
    if r < 0.975: return ('STOP',)
    if r < 0.985: return ('TERMINALISE',)
    if r < 0.995: return ('TERMINAL',)
    return ('REREGISTER',)


def mutated_ops(rnd, s, op):
    name, args = op[0], list(op[1:])
    aids = sorted({a.aid for a in s.attempts}) + ['zz']
    reqs = sorted({a.req for a in s.attempts}) + ['rz']
    nonces = sorted({a.nonce for a in s.attempts if a.nonce}) + ['nz']
    out = []

    def swap(i, pool):
        for v in pool:
            if v != args[i] or type(v) is not type(args[i]):
                out.append(tuple([name] + args[:i] + [v] + args[i + 1:]))
    if name in NAMED: swap(0, aids)
    if name == 'RESERVE': swap(1, reqs)
    if name == 'START': swap(1, nonces)
    if name == 'RELEASE': swap(1, ['BOUND_FENCE', 'NONE', 'WRONG_BINDING'])
    if name == 'RECONCILE':
        swap(1, ['NO_EFFECT', 'EFFECT', 'UNKNOWN']); swap(2, ['AUTHORISED', 'NONE', 'WRONG_BINDING'])
    if name == 'RECOVER':
        swap(0, [True, False]); swap(1, [True, False])
    if name in ONE_AID:
        out += [tuple([n] + args) for n in ONE_AID if n != name]
    if name in NO_ARG:
        out += [(n,) for n in NO_ARG if n != name]
    out = sorted(set(out), key=repr)
    rnd.shuffle(out)
    return out[:5]


def mutated_payloads(pre, rows, op):
    """Payload mutations of a genuine APPLIED record: a row dropped from a batch, or one row too many."""
    out = []
    if len(rows) > 1:
        out.append(('drop', rows[:-1]))
    if op[0] == 'RESERVE':
        out.append(('twin', rows + [{'aid': 'tw', 'req': 'qtw', 'phase': 'RESERVING', 'nonce': None, 'receipt': False, 'crossed': False}]))
    elif len(rows) == 1:
        x = pre.attempt(rows[0]['aid'])
        if x is not None:
            for y in pre.attempts:
                if y.aid != x.aid and (y.phase, y.receipt, y.crossed, y.nonce is None) == (x.phase, x.receipt, x.crossed, x.nonce is None):
                    twin = dict(rows[0], aid=y.aid, req=y.req, nonce=(y.nonce if rows[0]['nonce'] == x.nonce else 'n-twin'))
                    out.append(('twin', rows + [twin]))
                    break
    return out


RULES = [   # (a phrase of the refusal, the rule and the release that introduced it) -- for the report only
    ('the contract decides', 'v1.2 record is not the contract\'s decision (kind or code)'),
    ('does not produce the rows written', 'v1.2 rows or modes are not the named operation\'s transition'),
    ("control plane's to record", 'v1.2 control-plane operations recorded by the control plane only'),
    ('malformed operation', 'v1.2 malformed operation'),
    ('no provisioning record', 'v1.2 unprovisioned root'),
    ('decision kind', 'v1.1 kind bound to the state change'), ('recorded observation', 'v1.1 observation derived by the database'),
    ('decision hash', 'v1.1 hash recomputed by the database'), ('unknown operation', 'v1.1 operation alphabet'),
    ('does not produce the transition', 'v1.1 operation name bound to the transition'), ('does not record a receipt', 'v1.1 operation name bound to the transition'),
    ('does not record the crossing', 'v1.1 operation name bound to the transition'), ('does not hold the witness', 'v1.1 operation name bound to the mode change'),
    ('does not reactivate the witness', 'v1.1 operation name bound to the mode change'), ('does not move the run to STOPPING', 'v1.1 operation name bound to the mode change'),
    ('does not terminalise', 'v1.1 operation name bound to the mode change'), ('does not make the run terminal', 'v1.1 operation name bound to the mode change'),
    ('only REREGISTER re-registers', 'v1.1 operation name bound to the mode change'),
    ('immutable', 'v1.0 accepted bindings immutable'), ('START must bind', 'v1.0 accepted bindings immutable'), ('RECOVER clears', 'v1.0 accepted bindings immutable'),
    ('reserved to the witness', 'v0.7/v0.9 witness authority'), ('reserved to the control plane', 'v0.9 control-plane authority'),
    ('mode change is reserved', 'v0.9 control-plane authority'), ('illegal attempt transition', 'v0.9 transition relation'),
    ('illegal business transition', 'v0.9 transition relation'), ('bare reservation', 'v0.9 transition relation'), ('crossed', 'v0.9 flags'),
    ('receipt', 'v0.9 flags'), ('I1 violated', 'v0.8 invariants'), ('I2 violated', 'v0.8 invariants'),
]


def rule_of(msg):
    for phrase, rule in RULES:
        if phrase in (msg or ''):
            return rule
    return 'other: ' + (msg or '')[:60]


SWEEP_A = dict(seed=1201, budgets=[(2, 0), (3, 1), (1, 1), (4, 2), (2, 1), (3, 0)], prefix='x2-walk')
SWEEP_B = dict(seed=1301, budgets=[(5, 2), (4, 3), (3, 2), (2, 2), (1, 3), (5, 0)], prefix='x2b-walk')   # v1.2.1: other seed, larger budgets


def mutation_sweep(seed=1201, budgets=SWEEP_A['budgets'], prefix='x2-walk'):
    rnd = random.Random(seed)
    stats = {'genuine': 0, 'mutations': 0, 'truthful': 0, 'untruthful': 0, 'mismatch': 0, 'accepted_untruthful': 0, 'refused_truthful': 0,
             'genuine_ok': True, 'chains': [], 'chains_ok': True,
             'refusals_by_rule': {}, 'examples': []}
    for i, (k, m) in enumerate(budgets):
        root = f'{prefix}-{i}'
        provision(root, k, m)
        for _ in range(120):
            pre, _, _ = admin.state(root)
            op = next_op(rnd, pre)
            d, post = ref.apply(pre, ref.parse_op(op))
            kind, code = d.kind.value, d.code
            rows, modes = payload(pre, post) if kind == 'APPLIED' else ([], None)
            obs = _jsonable(ref.observe(post))
            dsn = dsn_for(op)
            candidates = []
            for mop in mutated_ops(rnd, pre, op):
                try:
                    md, mpost = ref.apply(pre, ref.parse_op(mop))
                except ref.InvalidInput:
                    continue
                truthful = (md.kind.value, md.code, _jsonable(ref.observe(mpost))) == (kind, code, obs)
                candidates.append(('operand', mop, rows, modes, obs, truthful and allowed(mop, dsn)))
            if kind == 'APPLIED':
                for how, mrows in mutated_payloads(pre, rows, op):
                    try:
                        mobs = _jsonable(ref.observe(simulate(pre, mrows, modes)))
                    except ref.InvalidInput:
                        continue
                    candidates.append((how, op, mrows, modes, mobs, False))
            for how, mop, mrows, mmodes, mobs, expect in candidates:
                ok, st, msg = write(dsn, root, mrows, mmodes, mop, kind, code, mobs, commit=False)
                stats['mutations'] += 1
                stats['truthful' if expect else 'untruthful'] += 1
                if not ok:
                    rule = rule_of(msg)
                    stats['refusals_by_rule'][rule] = stats['refusals_by_rule'].get(rule, 0) + 1
                if ok != expect:
                    stats['mismatch'] += 1
                    stats['accepted_untruthful' if ok else 'refused_truthful'] += 1
                    if len(stats['examples']) < 20:
                        stats['examples'].append({'root': root, 'how': how, 'genuine': list(op), 'record': list(mop), 'kind': kind, 'code': code,
                                                  'expected_accept': expect, 'accepted': ok, 'sqlstate': st, 'message': msg})
            try:
                got = apply(root, op)
                good = (got.kind, got.code) == (kind, code) and admin.observe(root) == obs
            except Exception as exc:                                          # noqa: BLE001
                good = False
                if len(stats['examples']) < 20:
                    stats['examples'].append({'root': root, 'genuine': list(op), 'error': repr(exc)[:200]})
            stats['genuine'] += 1
            stats['genuine_ok'] &= good
        v, lock = admin.verify_chain(root), replay_lockstep(admin, root, k, m)
        stats['chains'].append((root, v[0], lock[0], lock[2]))
        stats['chains_ok'] &= bool(v[0] and lock[0])
    return stats


# ============================================================ X3: refusal records (P4)
def x3():
    checks = []

    def probe_e(dsn):
        def f():
            provision('x3-e', 1, 0); snap = snapshot('x3-e'); obs = admin.observe('x3-e')
            ok, st, msg = write(dsn, 'x3-e', [], None, ('STOP',), 'DENIED', 'SYNTHETIC_REFUSAL', obs)
            return (not ok and snapshot('x3-e') == snap), f'accepted={ok} {st} {msg}'
        return f
    run(checks, "the reviewer's probe E: STOP recorded as DENIED on an OPEN run (the contract applies it) is refused, as plea_local, and leaves no trace", probe_e(LOCAL_DSN))
    run(checks, 'the same false refusal is refused to the control plane, which may apply STOP', probe_e(CONTROL_DSN))

    def invented_code():
        provision('x3-code', 2, 0); apply('x3-code', ('STOP',)); obs = admin.observe('x3-code')
        ok, st, msg = write(CONTROL_DSN, 'x3-code', [], None, ('STOP',), 'DENIED', 'SYNTHETIC', obs)
        d = apply('x3-code', ('STOP',))
        return (not ok and (d.kind, d.code) == ('DENIED', 'NOT_OPEN')), f'invented accepted={ok} {st} {msg}; genuine {d}'
    run(checks, "a refusal the contract gives, under an invented code, is refused; the contract's own refusal (STOP on a STOPPING run: DENIED NOT_OPEN) is recorded", invented_code)

    def control_refusals_by_gateway():
        provision('x3-held', 2, 0); apply('x3-held', ('HOLD',)); out = []
        for root, op in (('x3-code', ('STOP',)), ('x3-code', ('RECOVER', True, True)), ('x3-held', ('HOLD',)), ('x3-code', ('TERMINAL',))):
            pre, _, _ = admin.state(root); d, _ = ref.apply(pre, ref.parse_op(op)); obs = admin.observe(root)
            ok, st, msg = write(LOCAL_DSN, root, [], None, op, d.kind.value, d.code, obs)
            out.append((op[0], d.kind.value, d.code, ok, st))
        return all(k == 'DENIED' and not ok and st == '42501' for _, k, _, ok, st in out), str(out)
    run(checks, "a refusal of a control-plane operation, exactly as the contract gives it, cannot be recorded by the gateway (STOP, RECOVER, HOLD, TERMINAL: insufficient privilege)", control_refusals_by_gateway)

    def witness_refusal_by_gateway():
        provision('x3-wit', 2, 0); obs = admin.observe('x3-wit')
        ok, st, msg = write(LOCAL_DSN, 'x3-wit', [], None, ('ACCEPT_INTENT', 'ghost'), 'DENIED', 'UNKNOWN_ATTEMPT', obs)
        return (not ok and st == '42501'), f'accepted={ok} {st} {msg}'
    run(checks, 'a refusal of a witness operation cannot be recorded by the gateway (the v0.7 rule, unchanged)', witness_refusal_by_gateway)

    def noop_claimed():
        provision('x3-dup', 2, 0); snap = snapshot('x3-dup'); obs = admin.observe('x3-dup'); out = []
        for op, kind, code in ((('RESERVE', 'a1', 'q1'), 'DUPLICATE', 'RESERVE_RETRY'), (('TIMEOUT', 'ghost'), 'NOOP', 'NEVER_REFUNDS'),
                               (('HOLD',), 'NOOP', 'ALREADY_HELD')):
            ok, st, msg = write(dsn_for(op), 'x3-dup', [], None, op, kind, code, obs)
            out.append((op[0], ok, st))
        return (all(not ok for _, ok, _ in out) and snapshot('x3-dup') == snap), str(out)
    run(checks, 'a no-change record the contract does not give is refused: a DUPLICATE RESERVE of an absent attempt, a NOOP TIMEOUT of an unknown one, a NOOP HOLD on an ACTIVE run', noop_claimed)

    def declared_limit():
        provision('x3-limit', 1, 0); apply('x3-limit', ('RESERVE', 'a1', 'q1')); snap = snapshot('x3-limit')
        pre, _, _ = admin.state('x3-limit'); d, _ = ref.apply(pre, ref.parse_op(('RESERVE', 'a9', 'q9')))
        ok, st, msg = write(LOCAL_DSN, 'x3-limit', [], None, ('RESERVE', 'a9', 'q9'), d.kind.value, d.code, admin.observe('x3-limit'))
        same = admin.observe('x3-limit') == snap[2]
        v, lock = admin.verify_chain('x3-limit'), replay_lockstep(admin, 'x3-limit', 1, 0)
        return (ok and (d.kind.value, d.code) == ('DENIED', 'BUDGET_EXHAUSTED') and same and v[0] and lock[0]), f'accepted={ok} {st} {msg} {d} unchanged={same} chain {v} lockstep {lock}'
    run(checks, 'the declared limit: a refusal the contract gives for the current state (RESERVE on an exhausted budget, DENIED BUDGET_EXHAUSTED) can be recorded for a request that never reached the gateway; it changes no state and replays clean -- the database proves a refusal is the contract\'s, not that it was requested', declared_limit)
    return checks


# ============================================================ X4: the database's contract engine
def all_ops(aids, reqs, nonces):
    out = []
    for a in aids:
        out += [('RESERVE', a, q) for q in reqs]
        out += [(n, a) for n in ONE_AID]
        out += [('START', a, n) for n in nonces]
        out += [('RELEASE', a, e) for e in ('BOUND_FENCE', 'NONE', 'WRONG_BINDING')]
        out += [('RECONCILE', a, v, e) for v in ('NO_EFFECT', 'EFFECT', 'UNKNOWN') for e in ('AUTHORISED', 'NONE', 'WRONG_BINDING')]
    out += [(n,) for n in NO_ARG]
    out += [('RECOVER', x, y) for x in (True, False) for y in (True, False)]
    return out


def explore(k, m, ops):
    parsed = [ref.parse_op(o) for o in ops]
    s0 = ref.initial(k, m); seen = {s0}; frontier = [s0]
    while frontier:
        nxt = []
        for s in frontier:
            for p in parsed:
                _, t = ref.apply(s, p)
                if t not in seen:
                    seen.add(t); nxt.append(t)
        frontier = nxt
    return sorted(seen, key=lambda s: json.dumps(_jsonable(ref.observe(s)), sort_keys=True))


def to_oracle(s):
    return O.Root(s.k, s.m, s.witness.value, s.business.value,
                  tuple(O.Attempt(a.aid, a.req, a.phase.value, a.nonce, a.receipt, a.crossed) for a in s.attempts), s.reregistered)


def db_steps(conn, pairs):
    out = []
    for i in range(0, len(pairs), 2000):
        chunk = pairs[i:i + 2000]
        rows = conn.execute('SELECT x.i, public.plea_step(x.o, x.p) FROM jsonb_to_recordset(%s::jsonb) AS x(i int, o jsonb, p jsonb) ORDER BY x.i',
                            (json.dumps([{'i': j, 'o': o, 'p': p} for j, (o, p) in enumerate(chunk)]),)).fetchall()
        out.extend(r[1] for r in rows)
    return out


def x4():
    checks = []
    meta = {}

    def exhaustive():
        total, bad = 0, []
        with psycopg.connect(ADMIN_DSN) as conn:
            for (k, m, aids, reqs, nonces) in [(1, 0, ['a1', 'a2'], ['q1', 'q2'], ['n1', 'n2']), (2, 1, ['a1', 'a2'], ['q1', 'q2'], ['n1', 'n2'])]:
                ops = all_ops(aids, reqs, nonces); states = explore(k, m, ops)
                for s in states:
                    obs = _jsonable(ref.observe(s)); os_ = to_oracle(s)
                    got = db_steps(conn, [(obs, list(o)) for o in ops])
                    for o, g in zip(ops, got):
                        d, t = ref.apply(s, ref.parse_op(o)); od, ot = O.step(os_, o)
                        want = {'kind': d.kind.value, 'code': d.code, 'observation': _jsonable(ref.observe(t))}
                        total += 1
                        if g != want or od.kind != d.kind.value or _jsonable(O.observe(ot)) != g.get('observation'):
                            if len(bad) < 5:
                                bad.append({'state': obs, 'op': list(o), 'db': g, 'reference': want, 'oracle_kind': od.kind})
                meta[f'k{k}m{m}'] = {'states': len(states), 'operations': len(ops), 'pairs': len(states) * len(ops)}
            conn.rollback()
        meta['pairs'] = total; meta['mismatches'] = len(bad); meta['examples'] = bad
        return (total > 700000 and not bad), f'{total} pairs; mismatches {bad[:1]}'
    run(checks, 'over two complete bounded explorations (k=1 m=0 and k=2 m=1; two attempts, two requests, two nonces; every operation and label), the database\'s plea_step gives the reference engine\'s kind, code and observation and the independent oracle\'s kind and observation on every state and operation', exhaustive)

    def malformed():
        bad_ops = [[], ['FORGE'], ['reserve', 'a', 'q'], [1], [None], 'RESERVE', {'op': 'STOP'},
                   ['RESERVE'], ['RESERVE', 'a'], ['RESERVE', 'a', 'q', 'x'], ['RESERVE', '', 'q'], ['RESERVE', 'a', ''], ['RESERVE', 1, 'q'],
                   ['RESERVE', 'a', None], ['RESERVE', ['a'], 'q'], ['TOKEN'], ['TOKEN', True], ['TOKEN', ''], ['TOKEN', 'a', 'b'],
                   ['START', 'a'], ['START', 'a', 5], ['START', 'a', ''], ['RELEASE', 'a', 'MAYBE'], ['RELEASE', 'a', None], ['RELEASE', 'a'],
                   ['RELEASE', 'a', 'bound_fence'], ['RECONCILE', 'a', 'EFFECT'], ['RECONCILE', 'a', 'MAYBE', 'AUTHORISED'],
                   ['RECONCILE', 'a', 'EFFECT', 'SURE'], ['RECONCILE', 'a', None, 'AUTHORISED'], ['RECOVER'], ['RECOVER', 1, 0],
                   ['RECOVER', 'true', 'true'], ['RECOVER', True], ['RECOVER', True, None], ['HOLD', 'x'], ['STOP', None], ['CRASH', 'a'],
                   ['TERMINAL', ''], ['REREGISTER', False], ['TIMEOUT', ''], ['MISSING_RECEIPT'], ['CROSS', ['a']], ['ACCEPT_INTENT', {'a': 1}],
                   ['RECEIPT', 0]]
        good_ops = [['RESERVE', 'é', 'q'], ['RECOVER', False, False], ['RELEASE', 'a', 'WRONG_BINDING'], ['RECONCILE', 'a', 'UNKNOWN', 'NONE'],
                    ['START', 'a', 'n'], ['CRASH'], ['TIMEOUT', 'x'], ['REREGISTER'], ['MISSING_RECEIPT', 'q"uote'], ['RECOVER', True, False]]
        obs = _jsonable(ref.observe(ref.initial(1, 0))); disagree, parser = [], []
        for op, is_bad in [(o, True) for o in bad_ops] + [(o, False) for o in good_ops]:
            try:
                ref.parse_op(tuple(op) if isinstance(op, list) else op); py_rejects = False
            except ref.InvalidInput:
                py_rejects = True
            if py_rejects != is_bad:
                parser.append(op)                                   # the list itself must be right about the reference
            ok, st, msg = attempt_sql(ADMIN_DSN, 'SELECT public.plea_step(%s::jsonb, %s::jsonb)', (json.dumps(obs), json.dumps(op)))
            if py_rejects != (not ok) or (py_rejects and st != '23514'):
                disagree.append((op, py_rejects, ok, st, msg))
        meta['malformed'] = len(bad_ops); meta['wellformed'] = len(good_ops)
        return (not disagree and not parser and len(bad_ops) == 45 and len(good_ops) == 10), f'reference parser disagrees with the list on {parser[:3]}; database disagrees on {disagree[:3]}'
    run(checks, 'plea_step rejects exactly the operations the reference parser rejects (45 malformed: arity, types, empty identities, unknown names and labels, non-boolean flags; 10 well-formed edge cases accepted)', malformed)

    def owner_only():
        with psycopg.connect(ADMIN_DSN) as c:
            pub = {f: c.execute("SELECT has_function_privilege('public', %s, 'EXECUTE')", (f,)).fetchone()[0]
                   for f in ('public.plea_step(jsonb,jsonb)', 'public.plea_obs_of(jsonb,jsonb,text,text,boolean,jsonb)')}
        calls = {n: attempt_sql(d, """SELECT public.plea_step('{}'::jsonb, '["CRASH"]'::jsonb)""")[1]
                 for n, d in (('gateway', LOCAL_DSN), ('witness', WITNESS_DSN), ('control', CONTROL_DSN))}
        return (not any(pub.values()) and all(s == '42501' for s in calls.values())), f'public {pub} calls {calls}'
    def random_differential():
        rnd = random.Random(1401); aids6 = [f'a{i}' for i in range(6)]
        total, applied, kinds, bad = 0, 0, {}, []
        with psycopg.connect(ADMIN_DSN) as conn:
            for w in range(3000):
                k, m = rnd.randrange(0, 6), rnd.randrange(0, 4)
                st = ref.initial(k, m)
                for step in range(40):
                    op = next_op(rnd, st, aids6)
                    obs = _jsonable(ref.observe(st))
                    got = conn.execute('SELECT public.plea_step(%s::jsonb, %s::jsonb)', (json.dumps(obs), json.dumps(list(op)))).fetchone()[0]
                    d, nxt = ref.apply(st, ref.parse_op(op)); od, ot = O.step(to_oracle(st), op)
                    want = {'kind': d.kind.value, 'code': d.code, 'observation': _jsonable(ref.observe(nxt))}
                    total += 1; kinds[d.kind.value] = kinds.get(d.kind.value, 0) + 1
                    if d.kind.value == 'APPLIED': applied += 1
                    if got != want or od.kind != d.kind.value or _jsonable(O.observe(ot)) != got.get('observation'):
                        if len(bad) < 5: bad.append({'k': k, 'm': m, 'state': obs, 'op': list(op), 'db': got, 'reference': want, 'oracle_kind': od.kind})
                    st = nxt
            conn.rollback()
        meta['random_differential'] = {'walks': 3000, 'steps': total, 'by_kind': kinds, 'mismatches': len(bad), 'examples': bad}
        return (total == 120000 and not bad and applied > 10000), f'{total} steps, kinds {kinds}; mismatches {bad[:1]}'
    run(checks, 'beyond the exhaustive bound (v1.2.1): over 3,000 seeded random walks of 40 operations each, on budgets up to k=5 and m=3 with six attempt identities, plea_step gives the reference engine\'s kind, code and observation and the oracle\'s kind and observation at every one of 120,000 steps, with more than 10,000 of them applying', random_differential)

    run(checks, 'the engine and its helper are the owner\'s: PUBLIC holds no EXECUTE and no login role can call them', owner_only)
    checks_meta['X4'] = meta
    return checks


checks_meta = {}


def main():
    t0 = time.time()
    out = {}
    for name, fn in (('X1', x1), ('X2', x2), ('X3', x3), ('X4', x4)):
        t = time.time()
        out[name] = fn()
        out[name + '_seconds'] = round(time.time() - t, 1)
    out['seconds'] = round(time.time() - t0, 1)
    for k in ('X1', 'X2', 'X3', 'X4'):
        out[k + '_ok'] = all(ok for _, ok in out[k]); out[k + '_count'] = len(out[k]); out[k + '_passed'] = sum(ok for _, ok in out[k])
    out['meta'] = checks_meta
    out['PASS'] = all(out[k + '_ok'] for k in ('X1', 'X2', 'X3', 'X4'))
    write_output('x_tests.json', out)
    for k in ('X1', 'X2', 'X3', 'X4'):
        for label, ok in out[k]:
            print(k, 'ok  ' if ok else 'FAIL', label)
    print(json.dumps({k: v for k, v in out.items() if k not in ('X1', 'X2', 'X3', 'X4', 'meta')}, indent=1))
    print(json.dumps({k: v for k, v in checks_meta.get('X2_sweep', {}).items() if k in ('genuine', 'mutations', 'truthful', 'untruthful', 'mismatch', 'accepted_untruthful', 'refused_truthful', 'refusals_by_rule')}, indent=1))
    print('X RESULT:', 'PASS' if out['PASS'] else 'FAIL'); raise SystemExit(0 if out['PASS'] else 1)


if __name__ == '__main__':
    main()
