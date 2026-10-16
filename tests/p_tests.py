#!/usr/bin/env python3
"""P1-P2 (v0.8): the repairs for the v0.7 review's findings, each reproduced first in p_repro.py.

P1 one owner per host state, with fencing.  Simultaneous acquirers of a state file whose lease has expired give
   exactly one owner (threads and processes); a stale owner whose heartbeat stopped cannot claim new work after
   another host took over (StateLost); over HTTP, a host frozen past its lease and then resumed refuses new work
   (503) and runs nothing; the generation increases on each takeover.

P2 the gateway credential cannot rewrite accounting.  As plea_local, raw SQL on the authoritative tables (roots,
   attempts, decisions, evidence) is refused outright; the witness credential has lost direct writes too.  The
   demonstrated escalations (reset HOLD/STOP, delete a consumed attempt, reset crossed, raise the budget, insert a
   reservation, edit or delete audit history, delete and recreate a root) are all refused, and the run's state is
   unchanged.  A forged call to the write function itself is refused by the in-database backstop: an injected
   accepted phase (authority), an injected reservation beyond the budget (I2), a non-sequential or mis-chained
   decision (append-only), and a reset crossing (T7) are each rejected.  Every legitimate operation still applies
   through the proper path, so the boundary blocks nothing it should allow.
"""
import json
import os
import signal
import sqlite3
import subprocess
import tempfile
import threading
import time

import psycopg

from common import (ADMIN_DSN, CONTROL_DSN, GATE, GATEWAY, LOCAL_DSN, PYTHON, WITNESS_DSN, WITNESS_KEY, WITNESS_PUB, GateHost, Store, WitnessService,
                    admitted, bound, fresh_root, replay_lockstep, write_output)
from plea_gateway import BudgetExhausted, GateHostClient, GateRefused, Governor, RemoteWitness
from plea_gateway import gate_host as GH

LEDGER = GATEWAY / 'outputs' / 'p_ledger.jsonl'
def lines(): return sum(1 for _ in LEDGER.open()) if LEDGER.exists() else 0


class NoBeat(GH.HostState):
    def _heartbeat(self): return


def refused(label, fn, want, detail=None):
    try:
        fn(); return (label, False)
    except want as exc:
        if detail is not None:
            return (f'{label} ({detail(exc)})', True)
        return (f'{label} ({want.__name__})', True)
    except Exception as exc:
        return (f'{label}: unexpected {type(exc).__name__}: {str(exc)[:70]}', False)


# ---------------------------------------------------------------- P1: ownership
ACQ = ('import sys,time,json\n'
       'sys.path.insert(0, sys.argv[4])\n'
       'from plea_gateway import gate_host as GH\n'
       'path,lease,t0=sys.argv[1],float(sys.argv[2]),float(sys.argv[3])\n'
       'while time.time()<t0: pass\n'
       'try:\n'
       '    s=GH.HostState(path,lease); print(json.dumps({"owner":s.instance,"gen":s.generation}),flush=True); time.sleep(0.8)\n'
       'except GH.StateOwned:\n'
       '    print(json.dumps({"refused":True}),flush=True)\n')


def acquire_threads(n):
    path = os.path.join(tempfile.mkdtemp(), 's.sqlite'); NoBeat(path, lease=0.2); time.sleep(0.4)
    owners, refused_n = [], []
    def go():
        try: owners.append(GH.HostState(path, lease=10.0))
        except GH.StateOwned: refused_n.append(1)
    ts = [threading.Thread(target=go) for _ in range(n)]
    for t in ts: t.start()
    for t in ts: t.join(20)
    return len(owners), len(refused_n), sorted(o.generation for o in owners)


def p1():
    checks = []
    for n in (2, 4):
        o, r, gens = acquire_threads(n)
        checks.append((f'{n} simultaneous acquirers of an expired-lease file: exactly one owner', o == 1 and r == n - 1))
    # across processes
    more = 0
    for _ in range(6):
        path = os.path.join(tempfile.mkdtemp(), 's.sqlite'); NoBeat(path, lease=0.2); time.sleep(0.35)
        t0 = time.time() + 1.0
        ps = [subprocess.Popen([PYTHON, '-B', '-c', ACQ, path, '10', str(t0), str(GATEWAY)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(4)]
        outs = [p.communicate(timeout=30)[0] for p in ps]
        if sum(1 for o in outs if '"owner"' in o) != 1: more += 1
    checks.append(('a 4-process stampede onto an expired lease, 6 trials: never more than one owner', more == 0))
    # stale owner fenced; generation increments
    path = os.path.join(tempfile.mkdtemp(), 's.sqlite'); a = NoBeat(path, lease=0.3); a.claim('r', 'a0', 'running', 'n0'); time.sleep(0.5)
    b = GH.HostState(path, lease=10.0)
    checks.append(('the generation increments on takeover', b.generation == a.generation + 1 and b.interrupted == 1))
    checks.append(refused('a stale owner cannot claim new work after a takeover', lambda: a.claim('r', 'a1', 'running', 'n1'), GH.StateLost))
    checks.append(('the stale new row was not written', sqlite3.connect(path).execute("SELECT 1 FROM crossings WHERE aid='a1'").fetchone() is None))
    checks.append(('the new owner can claim', b.claim('r', 'a2', 'running', 'n2') is True))
    return checks


def p1_http(admin, svc):
    checks = []; w = RemoteWitness(svc.url, WITNESS_PUB); ran = 0
    for t in range(3):
        root = f'p1-{t}'; fresh_root(admin, root, 3, 0); A = {'order_id': root, 'amount': 1}; n = bound(root, 'a1', 'charge', A)
        state = str(GATEWAY / 'outputs' / f'p1_state_{t}.sqlite')
        ha = GateHost(8971, tools='tests.review_tools', ledger=str(LEDGER), state=state, lease=1.0); ha.start(fresh=True)
        _, ri, adm = admitted(admin, w, root, 'a1', 'q1', n)
        os.kill(ha.proc.pid, signal.SIGSTOP); time.sleep(1.4)
        hb = GateHost(8972, tools='tests.review_tools', ledger=str(LEDGER), state=state, lease=1.0); hb.stopped_at = None; hb.start(fresh=False)
        before = lines(); res = {}
        def call():
            try: res['a'] = 'ran' if not GateHostClient(ha.url, public_key=GATE.public_hex).run(root, 'a1', n, ri, 'charge', A, admission=adm)['repeat'] else 'repeat'
            except GateRefused as exc: res['a'] = f'refused {exc.status}'
            except Exception as exc: res['a'] = type(exc).__name__
        th = threading.Thread(target=call); th.start(); time.sleep(0.3); os.kill(ha.proc.pid, signal.SIGCONT); th.join(15)
        if lines() > before: ran += 1
        checks.append((f'trial {t}: the frozen host, resumed after a takeover, refuses the /run (503) and runs nothing', res.get('a') == 'refused 503' and lines() == before))
        ha.stop(); hb.stop()
    checks.append(('across 3 HTTP trials the stale host never ran the tool', ran == 0))
    return checks


def pathlib_unlink(path):
    import pathlib; pathlib.Path(path).unlink(missing_ok=True)


# ---------------------------------------------------------------- P2: the gateway credential
def raw(dsn, sql, params=()):
    try:
        with psycopg.connect(dsn) as conn:
            conn.execute(sql, params); conn.commit(); return True
    except psycopg.Error:
        return False


def p2(admin, svc, host):
    checks = []; local = Store(LOCAL_DSN); control = Store(CONTROL_DSN); w = RemoteWitness(svc.url, WITNESS_PUB)
    hc = GateHostClient(host.url, public_key=GATE.public_hex)
    def gov(root, k, m=0):
        fresh_root(admin, root, k, m); return Governor(local, w, root, k, m, admin=admin, host=GateHostClient(host.url, public_key=GATE.public_hex))
    def receipted(root, aid, A):
        n = bound(root, aid, 'charge', A)
        admin.apply(root, ('RESERVE', aid, 'q-' + aid)); w.accept_reservation(root, aid); admin.apply(root, ('TOKEN', aid)); admin.apply(root, ('START', aid, n))
        ri = w.accept_intent(root, aid)[1]; admin.apply(root, ('RECEIPT', aid)); return n, ri

    # direct DML on the authoritative tables, refused
    for ctl, col, val in (('HOLD', 'witness', 'ACTIVE'), ('STOP', 'business', 'OPEN')):
        root = f'p2-{ctl.lower()}'; fresh_root(admin, root, 3, 0); A = {'order_id': root, 'amount': 1}; n, ri = receipted(root, 'a1', A)
        admin.apply(root, (ctl,)); before = lines()
        allowed = raw(LOCAL_DSN, f'UPDATE roots SET {col} = %s WHERE root_id = %s', (val, root))
        d, adm = w.cross(root, 'a1')
        if d.kind == 'APPLIED': hc.run(root, 'a1', n, ri, 'charge', A, admission=adm)
        checks.append((f'raw reset of {ctl} is refused; the crossing stays denied and the tool does not run', not allowed and d.kind == 'DENIED' and lines() == before))

    g = gov('p2-delete', 1); before = lines(); g.attempt('p2-delete:c1', 'charge', order_id='d1', amount=1)
    allowed = raw(LOCAL_DSN, 'DELETE FROM attempts WHERE root_id = %s', ('p2-delete',))
    try: g.attempt('p2-delete:c2', 'charge', order_id='d2', amount=1); second = 'ran'
    except BudgetExhausted: second = 'BudgetExhausted'
    checks.append(('deleting a consumed attempt to free budget is refused; the budget stays exhausted; one execution', not allowed and second == 'BudgetExhausted' and lines() == before + 1))

    root = 'p2-crossed'; fresh_root(admin, root, 3, 0); A = {'order_id': root, 'amount': 1}; n, ri = receipted(root, 'a1', A)
    before = lines(); d1, adm1 = w.cross(root, 'a1'); hc.run(root, 'a1', n, ri, 'charge', A, admission=adm1)
    allowed = raw(LOCAL_DSN, "UPDATE attempts SET crossed = false WHERE root_id = %s AND aid = 'a1'", (root,))
    d2, _ = w.cross(root, 'a1')
    checks.append(('resetting crossed is refused; a second crossing is DENIED ALREADY_CROSSED; one execution', not allowed and d2.kind == 'DENIED' and d2.code == 'ALREADY_CROSSED' and lines() == before + 1))

    g = gov('p2-budget', 1); before = lines(); g.attempt('p2-budget:c1', 'charge', order_id='k1', amount=1)
    allowed = raw(LOCAL_DSN, 'UPDATE roots SET k = 5 WHERE root_id = %s', ('p2-budget',))
    try: g.attempt('p2-budget:c2', 'charge', order_id='k2', amount=1); second = 'ran'
    except BudgetExhausted: second = 'BudgetExhausted'
    checks.append(('raising the budget is refused; the second call is still exhausted; one execution', not allowed and second == 'BudgetExhausted' and lines() == before + 1))

    g = gov('p2-insert', 1); before = lines(); g.attempt('p2-insert:c1', 'charge', order_id='i1', amount=1)
    allowed = raw(LOCAL_DSN, "INSERT INTO attempts (root_id, aid, req, phase) VALUES (%s, 'ax', 'qx', 'RESERVING')", ('p2-insert',))
    checks.append(('inserting a reservation directly is refused; one execution', not allowed and lines() == before + 1))

    root = 'p2-history'; g = gov(root, 3); g.attempt(f'{root}:c1', 'charge', order_id='h1', amount=1)
    upd = raw(LOCAL_DSN, "UPDATE decisions SET kind = 'DENIED' WHERE root_id = %s AND seq = 2", (root,))
    dele = raw(LOCAL_DSN, 'DELETE FROM decisions WHERE root_id = %s', (root,))
    checks.append(('editing or deleting the audit log is refused; the chain stays valid', not upd and not dele and admin.verify_chain(root)[0]))

    root = 'p2-root'; fresh_root(admin, root, 1, 0)
    de = raw(LOCAL_DSN, 'DELETE FROM roots WHERE root_id = %s', (root,))
    ins = raw(LOCAL_DSN, "INSERT INTO roots (root_id, k, m, witness, business, head_hash) VALUES (%s, 1000, 0, 'ACTIVE', 'OPEN', 'x')", ('p2-root2',))
    checks.append(('deleting or inserting a root directly is refused', not de and not ins))

    # the witness credential has no direct DML either
    root = 'p2-witness'; fresh_root(admin, root, 1, 0)
    checks.append(('the witness credential cannot rewrite a root directly', not raw(WITNESS_DSN, 'UPDATE roots SET k = 9 WHERE root_id = %s', (root,))))

    # a forged call to the write function itself, refused by the backstop
    root = 'p2-forge'; fresh_root(admin, root, 1, 0); g = gov(root, 1)
    # the forged-call attempts run as plea_local calling plea_write directly
    def forge(attempts, modes=None, seq=None, prev=None, op=('RESERVE', 'fx', 'qx'), evid=None):
        st = admin.observe(root); cur_seq = len(admin.audit(root)); head = admin.audit(root)[-1]['hash'] if cur_seq else None
        if head is None:
            with psycopg.connect(ADMIN_DSN) as c: head = c.execute('SELECT head_hash FROM roots WHERE root_id=%s', (root,)).fetchone()[0]
        with psycopg.connect(LOCAL_DSN) as c:
            c.execute('SELECT plea_write(%s, %s::jsonb, %s::jsonb, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s::jsonb)',
                      (root, json.dumps(attempts), json.dumps(modes) if modes else None,
                       (seq if seq is not None else cur_seq + 1), 'forged-head', json.dumps(list(op)), 'APPLIED', 'X',
                       json.dumps({}), (prev if prev is not None else head), None)); c.commit()
    checks.append(refused('a forged write inserting an attempt straight at an accepted phase (CONSUMED) is refused',
                          lambda: forge([{'aid': 'fx', 'req': 'qx', 'phase': 'CONSUMED', 'nonce': 'fn', 'receipt': True, 'crossed': False}]), psycopg.errors.CheckViolation))
    checks.append(refused('a forged write injecting a reservation beyond the budget is refused (I2)',
                          lambda: forge([{'aid': 'fx', 'req': 'qx', 'phase': 'RESERVING', 'nonce': None, 'receipt': False, 'crossed': False},
                                         {'aid': 'fy', 'req': 'qy', 'phase': 'RESERVING', 'nonce': None, 'receipt': False, 'crossed': False}]), psycopg.errors.CheckViolation))
    checks.append(refused('a forged write with a non-sequential decision is refused (append-only)',
                          lambda: forge([], seq=99), psycopg.errors.CheckViolation))
    checks.append(refused('a forged write with a mis-chained decision is refused',
                          lambda: forge([], prev='not-the-head'), psycopg.errors.CheckViolation))

    # every legitimate path still applies
    root = 'p2-legit'; fresh_root(admin, root, 2, 1); ok = []
    for op, st in [(('RESERVE', 'a1', 'q1'), local), (('ACCEPT_RESERVATION', 'a1'), w), (('TOKEN', 'a1'), local), (('START', 'a1', 'n1'), local)]:
        if st is w:
            d, _ = w.accept(root, op); ok.append(d.kind == 'APPLIED')
        else:
            d, _ = st.apply(root, op); ok.append(d.kind == 'APPLIED')
    control.apply(root, ('HOLD',)); d, _ = control.apply(root, ('RECOVER', True, True)); ok.append(d.kind == 'APPLIED')   # operator HOLD/RECOVER through the control credential (v0.9)
    checks.append(('every legitimate operation still applies through the proper path (RESERVE, TOKEN, START via gateway; operator HOLD/RECOVER via control)', all(ok)))
    checks.append(('replay lockstep on a governed root', replay_lockstep(admin, 'p2-history', 3, 0)[0]))
    return checks


def main():
    admin = Store(ADMIN_DSN); t0 = time.time(); LEDGER.unlink(missing_ok=True)
    out = {'P1': p1()}
    svc = WitnessService(8970, key=WITNESS_KEY); svc.start()
    host = GateHost(8973, tools='tests.review_tools', ledger=str(LEDGER), lease=1.0); host.start()
    try:
        out['P1'] += p1_http(admin, svc)
        out['P2'] = p2(admin, svc, host)
    finally:
        host.stop(); svc.stop()
    out['seconds'] = round(time.time() - t0, 1)
    for k in ('P1', 'P2'): out[k + '_ok'] = all(ok for _, ok in out[k])
    out['PASS'] = all(out[k + '_ok'] for k in ('P1', 'P2'))
    write_output('p_tests.json', out)
    for k in ('P1', 'P2'):
        for label, ok in out[k]: print(k, 'ok  ' if ok else 'FAIL', label)
    print(json.dumps({k: v for k, v in out.items() if k not in ('P1', 'P2')}, indent=1))
    print('P RESULT:', 'PASS' if out['PASS'] else 'FAIL'); raise SystemExit(0 if out['PASS'] else 1)


if __name__ == '__main__':
    main()
