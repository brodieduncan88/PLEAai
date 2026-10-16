#!/usr/bin/env python3
"""W3: the whole lifecycle through the witness service, with the local credential, in lockstep with the oracle.

Part A, governed calls.  Eight roots with budget 3 and allowance 1.  Each gets 10 governed calls: 6 distinct
request keys, and 4 retries of earlier keys.  Expected per root: 3 executions (the budget), 4 denials, 3 retries
answered from the stored result with no execution, and 0 re-executions.  The fourth retry is of a key that was
denied at the budget, so no attempt exists for it and the contract denies it again (amendment 2: the first
declaration miscounted this as a served retry).  The governor holds plea_local; every acceptance goes
over HTTP; every CROSS is behind a verified receipt.  Replay lockstep and the chain are checked per root.

Part B, G02b through the service.  100 rounds of the release-then-accept race where the acceptor is an HTTP call to
the service instead of an in-process transaction.  Same expectations as G02b.
"""
import json
import multiprocessing as mp
import random
import time

from common import ADMIN_DSN, GATE, LOCAL_DSN, Store, WitnessService, fresh_root, invariants_ok, replay_lockstep, write_output
from plea_gateway import BudgetExhausted, Governor, RemoteWitness


def part_a(admin, local, w):
    rows, calls_total = [], 0
    for i in range(8):
        root = f'w3a-{i}'; fresh_root(admin, root, 3, 1)
        gov = Governor(local, w, root, 3, 1, admin=admin, gate=GATE)
        executions = []
        def work(key): executions.append(key); return f'done {key}'
        keys = [f'k{i}-{j}' for j in range(6)]
        schedule = keys[:2] + [keys[0]] + keys[2:4] + [keys[1], keys[3]] + keys[4:6] + [keys[2]]   # 6 distinct, 4 retries
        outcome = {'executed': 0, 'denied': 0, 'retry_served': 0, 'retry_executed_again': 0, 'other': 0}
        seen = set()
        for key in schedule:
            retry = key in seen; seen.add(key); before = len(executions)
            try:
                gov.attempt(key, work, key)
                if retry: outcome['retry_served' if len(executions) == before else 'retry_executed_again'] += 1
                else: outcome['executed'] += 1
            except BudgetExhausted:
                outcome['denied'] += 1
            except Exception as exc:
                outcome['other'] += 1; outcome.setdefault('errors', []).append(repr(exc)[:120])
        obs = admin.observe(root)
        ok = (outcome['executed'] == 3 and outcome['denied'] == 4 and outcome['retry_served'] == 3 and outcome['retry_executed_again'] == 0   # amendment 2
              and outcome['other'] == 0 and len(executions) == 3 and obs['accepted'][1] == 3
              and all(a[5] for a in obs['attempts'] if a[2] == 'EFFECT'))
        rows.append({'root': root, **outcome, 'executions': len(executions), 'accepted_C': obs['accepted'][1],
                     'lockstep': replay_lockstep(admin, root, 3, 1)[0], 'chain': admin.verify_chain(root)[0], 'ok': ok and replay_lockstep(admin, root, 3, 1)[0]})
        calls_total += len(schedule)
    return rows, calls_total


def racer(url, pubkey, root, mode, delay, q):
    time.sleep(delay); out = []
    if mode == 'accept':
        d, _ = RemoteWitness(url, pubkey).accept_intent(root, 'a1'); out.append(('ACCEPT_INTENT', d.kind, d.code))
    elif mode == 'release':
        d, _ = RemoteWitness(url, pubkey).release(root, 'a1', GATE.fence_report(root, 'a1').to_json()); out.append(('RELEASE', d.kind, d.code))   # a genuine fence report: still DENIED by 5.8/3 or /4
    else:
        st = Store(LOCAL_DSN)
        for _ in range(5):
            d, _ = st.apply(root, ('RESERVE', 'a2', 'q2')); out.append(('RESERVE', d.kind, d.code)); time.sleep(0.001)
    q.put(out)


def part_b(admin, w, url, rounds=100):
    ctx, rng = mp.get_context('fork'), random.Random(20261012)
    totals = {'release_denied': 0, 'accept_applied': 0, 'probes': 0, 'probes_denied': 0, 'final_ok': 0, 'lockstep_ok': 0, 'chain_ok': 0}
    order, failures = {'accept_first': 0, 'release_first': 0}, []
    for r in range(rounds):
        root = f'w3b-{r}'; fresh_root(admin, root, 1, 0)
        for op in (('RESERVE', 'a1', 'q1'), ('ACCEPT_RESERVATION', 'a1'), ('TOKEN', 'a1'), ('START', 'a1', 'n1')):
            d, _ = admin.apply(root, op); assert d.kind == 'APPLIED'
        q = ctx.Queue()
        procs = [ctx.Process(target=racer, args=(url, w.public_key, root, 'accept', rng.uniform(0, 0.004), q)),
                 ctx.Process(target=racer, args=(url, w.public_key, root, 'release', rng.uniform(0, 0.004), q)),
                 ctx.Process(target=racer, args=(url, w.public_key, root, 'probe', 0.0, q))]
        for p in procs: p.start()
        flat = [x for _ in procs for x in q.get(timeout=60)]
        for p in procs: p.join()
        rel = [x for x in flat if x[0] == 'RELEASE']; acc = [x for x in flat if x[0] == 'ACCEPT_INTENT']; pr = [x for x in flat if x[0] == 'RESERVE']
        totals['release_denied'] += rel[0][1] == 'DENIED'; totals['accept_applied'] += acc[0][1] == 'APPLIED'
        totals['probes'] += len(pr); totals['probes_denied'] += sum(x[1] == 'DENIED' for x in pr)
        obs = admin.observe(root)
        a1 = [a for a in obs['attempts'] if a[0] == 'a1'][0]
        totals['final_ok'] += a1[2] == 'CONSUMED' and obs['accepted'] == [0, 1, 0] and invariants_ok(obs)[0]
        seq_of = {d['op'][0]: d['seq'] for d in admin.audit(root) if d['op'][0] in ('RELEASE', 'ACCEPT_INTENT')}
        order['accept_first' if seq_of.get('ACCEPT_INTENT', 0) < seq_of.get('RELEASE', 0) else 'release_first'] += 1
        totals['lockstep_ok'] += replay_lockstep(admin, root, 1, 0)[0]; totals['chain_ok'] += admin.verify_chain(root)[0]
        if not (rel[0][1] == 'DENIED' and acc[0][1] == 'APPLIED' and all(x[1] == 'DENIED' for x in pr)): failures.append((root, flat))
    return totals, order, failures


def main():
    admin, local = Store(ADMIN_DSN), Store(LOCAL_DSN)
    svc = WitnessService(8792); svc.start(); t0 = time.time()
    try:
        w = RemoteWitness(svc.url)
        rows, calls = part_a(admin, local, w)
        totals, order, failures = part_b(admin, w, svc.url)
    finally:
        svc.stop()
    a_ok = all(r['ok'] for r in rows)
    b_ok = not failures and all(totals[x] == 100 for x in ('release_denied', 'accept_applied', 'final_ok', 'lockstep_ok', 'chain_ok')) and totals['probes_denied'] == totals['probes']
    out = {'seconds': round(time.time() - t0, 1), 'part_a': {'roots': len(rows), 'governed_calls': calls, 'rows': rows, 'ok': a_ok},
           'part_b': {'rounds': 100, **totals, 'order': order, 'failures': failures[:5], 'ok': b_ok}, 'PASS': a_ok and b_ok}
    write_output('w3_service_lockstep.json', out)
    print(json.dumps({'seconds': out['seconds'], 'part_a_ok': a_ok, 'governed_calls': calls,
                      'part_a_totals': {k: sum(r[k] for r in rows) for k in ('executed', 'denied', 'retry_served', 'retry_executed_again', 'other')},
                      'part_b': {k: v for k, v in out['part_b'].items() if k != 'failures'}}, indent=1))
    for r in rows:
        if not r['ok']: print('FAIL A', r)
    print('W3 RESULT:', 'PASS' if out['PASS'] else 'FAIL'); raise SystemExit(0 if out['PASS'] else 1)


if __name__ == '__main__':
    main()
