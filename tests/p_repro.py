#!/usr/bin/env python3
"""Reproduction of the v0.7 independent review's findings, before any repair.
Not a declared test.  The reviewer's own script was not available; each counterexample is re-implemented from the
review's description, and the PostgreSQL ones are carried through to the host, to see whether a tool runs.

Output file (v0.9 fix for the clobber the v0.8 review caught): this script writes to PLEA_REPRO_OUT, defaulting to
``review3_repro_against_current.json``.  Run against the unchanged v0.7 source it records the live findings and is the
script that produced the shipped ``review3_repro_v0_7.json`` (there, PLEA_REPRO_OUT=review3_repro_v0_7.json); run
against the current source it records each finding closed.  It never overwrites the shipped v0.7 evidence by default.

Part A, host-state ownership (finding 1):
  A1 two acquirers whose owner read and owner write are interleaved (the read-write window widened by a barrier);
  A2 a stampede: 4 processes released at one instant onto a state file with an expired lease, 10 trials;
  A3 a stale owner (its heartbeat stopped) writes a new running row after another host took the file over;
  A4 the same over HTTP: host A frozen past its lease, host B takes over, a /run reaches A as it resumes, 5 trials.
Part B, the local credential (finding 2), native PostgreSQL, as plea_local with raw SQL unless stated:
  B1 HOLD reset, B2 STOP reset, B3 a consumed attempt deleted, B4 crossed reset, B5 the budget raised,
  B6 RECOVER through the API, B7 a reservation inserted beyond the budget, B8 history deleted and edited,
  B9 a root deleted and recreated, B10 the database's own controls (temp tables, triggers, replication role).
"""
import json
import os
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

import psycopg

from common import (ADMIN_DSN, GATE, GATEWAY, LOCAL_DSN, PYTHON, WITNESS_KEY, WITNESS_PUB, GateHost, Store, WitnessService, admitted, bound,
                    fresh_root, write_output)
from plea_gateway import BudgetExhausted, GateHostClient, GateRefused, Governor, RemoteWitness
from plea_gateway import gate_host as GH

LEDGER = GATEWAY / 'outputs' / 'p_repro_ledger.jsonl'
def lines(): return sum(1 for _ in LEDGER.open()) if LEDGER.exists() else 0


# ---------------------------------------------------------------- part A: ownership
class Proxy:
    """A sqlite3 connection whose execute() calls a hook after the acquisition's read of the owner row."""
    def __init__(self, conn, hook): self.conn, self.hook = conn, hook
    def execute(self, sql, params=()):
        cur = self.conn.execute(sql, params)
        s = sql.lstrip().upper()
        if s.startswith('SELECT') and 'FROM OWNER' in s and 'HEARTBEAT' in s:
            self.hook()
        return cur
    def __enter__(self): self.conn.__enter__(); return self
    def __exit__(self, *a): return self.conn.__exit__(*a)
    def close(self): self.conn.close()
    def __getattr__(self, name): return getattr(self.conn, name)


def make_dead_owner(path):
    class NoBeat(GH.HostState):
        def _heartbeat(self): return
    NoBeat(path, lease=0.2); time.sleep(0.5)                 # an owner that never beats: its lease has expired


def a1_interleaved(n=2):
    path = os.path.join(tempfile.mkdtemp(), 'state.sqlite'); make_dead_owner(path)
    barrier = threading.Barrier(n)
    def hook():
        try: barrier.wait(timeout=1.5)
        except threading.BrokenBarrierError: pass
    class Hooked(GH.HostState):
        def _db(self): return Proxy(sqlite3.connect(self.path, isolation_level=None, timeout=5.0), hook)
    owners, refused, errors = [], [], []
    def go():
        try: owners.append(Hooked(path, lease=10.0))
        except GH.StateOwned: refused.append(1)
        except Exception as exc: errors.append(repr(exc)[:100])
    ts = [threading.Thread(target=go) for _ in range(n)]
    for t in ts: t.start()
    for t in ts: t.join(20)
    claims = []
    for i, o in enumerate(owners):
        try: claims.append(bool(o.claim('r', f'a{i}', 'running', f'n{i}')))
        except Exception as exc: claims.append(type(exc).__name__)
    return {'acquirers': n, 'owners': len(owners), 'refused': len(refused), 'errors': errors, 'new_running_rows_written': claims}


DRIVER = r'''
import sys, time, json
sys.path.insert(0, sys.argv[4])
from plea_gateway import gate_host as GH
path, lease, t0 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
while time.time() < t0: pass
try:
    s = GH.HostState(path, lease); print(json.dumps({'owner': s.instance, 'generation': getattr(s, 'generation', None)}), flush=True); time.sleep(1.0)
except GH.StateOwned:
    print(json.dumps({'refused': True}), flush=True)
'''


def a2_stampede(k=4, trials=10):
    per_trial = []
    for _ in range(trials):
        path = os.path.join(tempfile.mkdtemp(), 'state.sqlite'); make_dead_owner(path)
        t0 = time.time() + 1.5
        procs = [subprocess.Popen([PYTHON, '-B', '-c', DRIVER, path, '10', str(t0), str(GATEWAY)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(k)]
        outs = [p.communicate(timeout=30) for p in procs]
        owners = sum(1 for o, _ in outs if '"owner"' in o)
        per_trial.append(owners)
    return {'processes_per_trial': k, 'trials': trials, 'owners_per_trial': per_trial, 'trials_with_more_than_one_owner': sum(1 for x in per_trial if x > 1)}


def a3_stale_write():
    path = os.path.join(tempfile.mkdtemp(), 'state.sqlite')
    class NoBeat(GH.HostState):
        def _heartbeat(self): return
    a = NoBeat(path, lease=0.3); a.claim('r', 'a-running', 'running', 'n0')
    time.sleep(0.5); b = GH.HostState(path, lease=10.0)
    try: wrote = bool(a.claim('r', 'a-new', 'running', 'n1'))
    except Exception as exc: wrote = type(exc).__name__
    row = sqlite3.connect(path).execute("SELECT status FROM crossings WHERE root = 'r' AND aid = 'a-new'").fetchone()
    return {'a_noticed_loss_before_writing': a.lost, 'stale_owner_new_running_row': wrote, 'row_in_file': row[0] if row else None,
            'b_marked_interrupted': b.interrupted}


def a4_http(svc, trials=5):
    admin = Store(ADMIN_DSN); w = RemoteWitness(svc.url, WITNESS_PUB); results = []
    for t in range(trials):
        state = str(GATEWAY / 'outputs' / f'p_repro_a4_{t}.sqlite')
        ha = GateHost(8961, tools='tests.review_tools', ledger=str(LEDGER), state=state, lease=1.0); ha.start()
        root = f'p-a4-{t}'; fresh_root(admin, root, 3, 0); A = {'order_id': root, 'amount': 1}; n = bound(root, 'a1', 'charge', A)
        _, ri, adm = admitted(admin, w, root, 'a1', 'q1', n)
        os.kill(ha.proc.pid, signal.SIGSTOP); time.sleep(1.4)
        hb = GateHost(8962, tools='tests.review_tools', ledger=str(LEDGER), state=state, lease=1.0); hb.start(fresh=False)
        before = lines(); res = {}
        def call():
            try: res['answer'] = 'ran' if not GateHostClient(ha.url, public_key=GATE.public_hex).run(root, 'a1', n, ri, 'charge', A, admission=adm)['repeat'] else 'repeat'
            except GateRefused as exc: res['answer'] = f'refused {exc.status}'
            except Exception as exc: res['answer'] = type(exc).__name__
        th = threading.Thread(target=call); th.start(); time.sleep(0.3)
        os.kill(ha.proc.pid, signal.SIGCONT); th.join(15)
        results.append({'trial': t, 'stale_host_answer': res.get('answer'), 'executions_at_stale_host': lines() - before})
        ha.stop(); hb.stop()
    return {'trials': results, 'trials_where_the_stale_host_ran_the_tool': sum(1 for r in results if r['executions_at_stale_host'] > 0)}


# ---------------------------------------------------------------- part B: the local credential
def raw(sql, params=()):
    try:
        with psycopg.connect(LOCAL_DSN) as conn:
            cur = conn.execute(sql, params); n = cur.rowcount; conn.commit(); return {'allowed': True, 'rows': n}
    except psycopg.Error as exc:
        return {'allowed': False, 'error': type(exc).__name__, 'detail': str(exc).splitlines()[0][:100]}


def part_b(svc, host):
    admin, local = Store(ADMIN_DSN), Store(LOCAL_DSN); w = RemoteWitness(svc.url, WITNESS_PUB)
    hc = GateHostClient(host.url, public_key=GATE.public_hex); out = {}
    def gov(root, k, m=0):
        fresh_root(admin, root, k, m); return Governor(local, w, root, k, m, admin=admin, host=GateHostClient(host.url, public_key=GATE.public_hex))
    def receipted(root, aid, A):
        n = bound(root, aid, 'charge', A)
        admin.apply(root, ('RESERVE', aid, 'q-' + aid)); w.accept_reservation(root, aid); admin.apply(root, ('TOKEN', aid)); admin.apply(root, ('START', aid, n))
        ri = w.accept_intent(root, aid)[1]; admin.apply(root, ('RECEIPT', aid)); return n, ri
    for ctl, col, val in (('HOLD', 'witness', 'ACTIVE'), ('STOP', 'business', 'OPEN')):
        root = f'p-b-{ctl.lower()}'; fresh_root(admin, root, 3, 0); A = {'order_id': root, 'amount': 1}; n, ri = receipted(root, 'a1', A)
        admin.apply(root, (ctl,)); d0, _ = w.cross(root, 'a1'); before = lines()
        r = raw(f'UPDATE roots SET {col} = %s WHERE root_id = %s', (val, root))
        d1, adm = w.cross(root, 'a1'); ran = 0
        if d1.kind == 'APPLIED':
            hc.run(root, 'a1', n, ri, 'charge', A, admission=adm); ran = lines() - before
        out[f'B_{ctl}_reset'] = {'cross_before': [d0.kind, d0.code], 'raw_reset': r, 'cross_after': [d1.kind, d1.code], 'tool_runs': ran}
    g = gov('p-b-delete', 1); before = lines(); g.attempt('p-b-delete:c1', 'charge', order_id='d1', amount=1)
    try: g.attempt('p-b-delete:c2', 'charge', order_id='d2', amount=1); second = 'ran'
    except BudgetExhausted: second = 'BudgetExhausted'
    r = raw('DELETE FROM attempts WHERE root_id = %s', ('p-b-delete',))
    try: g.attempt('p-b-delete:c3', 'charge', order_id='d3', amount=1); third = 'ran'
    except Exception as exc: third = type(exc).__name__
    out['B_delete_consumed'] = {'budget_k': 1, 'second_call': second, 'raw_delete': r, 'third_call': third, 'tool_runs_total': lines() - before}
    root = 'p-b-crossed'; fresh_root(admin, root, 3, 0); A = {'order_id': root, 'amount': 1}; n, ri = receipted(root, 'a1', A)
    before = lines(); d1, adm1 = w.cross(root, 'a1'); hc.run(root, 'a1', n, ri, 'charge', A, admission=adm1)
    r = raw("UPDATE attempts SET crossed = false WHERE root_id = %s AND aid = 'a1'", (root,))
    d2, adm2 = w.cross(root, 'a1'); again = hc.run(root, 'a1', n, ri, 'charge', A, admission=adm2) if d2.kind == 'APPLIED' else None
    out['B_crossed_reset'] = {'first_cross': d1.kind, 'raw_reset': r, 'second_cross': [d2.kind, d2.code],
                              'host_answer_to_second': None if again is None else ('repeat' if again['repeat'] else 'ran'), 'tool_runs_total': lines() - before}
    g = gov('p-b-budget', 1); before = lines(); g.attempt('p-b-budget:c1', 'charge', order_id='k1', amount=1)
    r = raw('UPDATE roots SET k = 5 WHERE root_id = %s', ('p-b-budget',))
    try: g.attempt('p-b-budget:c2', 'charge', order_id='k2', amount=1); second = 'ran'
    except Exception as exc: second = type(exc).__name__
    out['B_budget_raised'] = {'budget_k': 1, 'raw_update_k': r, 'second_call': second, 'tool_runs_total': lines() - before}
    root = 'p-b-recover'; fresh_root(admin, root, 2, 0); admin.apply(root, ('HOLD',))
    try: d, obs = local.apply(root, ('RECOVER', True, True)); rec = [d.kind, d.code, obs['witness']]
    except Exception as exc: rec = type(exc).__name__
    out['B_recover_via_api'] = {'operator_held': True, 'plea_local_recover': rec}
    g = gov('p-b-insert', 1); before = lines(); g.attempt('p-b-insert:c1', 'charge', order_id='i1', amount=1)
    r = raw("INSERT INTO attempts (root_id, aid, req, phase) VALUES (%s, 'ax', 'qx', 'RESERVING')", ('p-b-insert',)); ran = 0
    if r['allowed']:
        A = {'order_id': 'ix', 'amount': 1}; n = bound('p-b-insert', 'ax', 'charge', A)
        w.accept_reservation('p-b-insert', 'ax'); local.apply('p-b-insert', ('TOKEN', 'ax')); local.apply('p-b-insert', ('START', 'ax', n))
        ri = w.accept_intent('p-b-insert', 'ax')[1]; local.apply('p-b-insert', ('RECEIPT', 'ax')); d, adm = w.cross('p-b-insert', 'ax')
        if d.kind == 'APPLIED': hc.run('p-b-insert', 'ax', n, ri, 'charge', A, admission=adm)
    out['B_reserving_beyond_budget'] = {'budget_k': 1, 'raw_insert': r, 'tool_runs_total': lines() - before}
    root = 'p-b-history'; g = gov(root, 3); g.attempt(f'{root}:c1', 'charge', order_id='h1', amount=1)
    upd = raw("UPDATE decisions SET kind = 'DENIED' WHERE root_id = %s AND seq = 2", (root,)); dele = raw('DELETE FROM decisions WHERE root_id = %s AND seq > 3', (root,))
    out['B_history'] = {'raw_update_decision': upd, 'raw_delete_decisions': dele, 'verify_chain_after': admin.verify_chain(root)[0]}
    root = 'p-b-root'; fresh_root(admin, root, 1, 0)
    out['B_root_recreated'] = {'raw_delete_root': raw('DELETE FROM roots WHERE root_id = %s', (root,)),
                               'raw_insert_root_k_1000': raw("INSERT INTO roots (root_id, k, m, witness, business, head_hash) VALUES (%s, 1000, 0, 'ACTIVE', 'OPEN', 'x')", (root,))}
    out['B_database_controls'] = {'create_temp_table': raw('CREATE TEMP TABLE roots (x int)'), 'drop_trigger': raw('DROP TRIGGER witness_only_phases ON attempts'),
                                  'replication_role_replica': raw("SET session_replication_role = replica")}
    return out


def main():
    LEDGER.unlink(missing_ok=True); out = {}
    out['A1_interleaved_two'] = a1_interleaved(2)
    out['A1_interleaved_four'] = a1_interleaved(4)
    out['A2_stampede'] = a2_stampede()
    out['A3_stale_write'] = a3_stale_write()
    svc = WitnessService(8960, key=WITNESS_KEY); svc.start()
    host = GateHost(8963, tools='tests.review_tools', ledger=str(LEDGER), lease=1.0); host.start()
    try:
        out['A4_stale_host_http'] = a4_http(svc)
        out.update(part_b(svc, host))
    finally:
        host.stop(); svc.stop()
    name = os.environ.get('PLEA_REPRO_OUT', 'review3_repro_against_current.json')
    write_output(name, out); print('wrote', name); print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
