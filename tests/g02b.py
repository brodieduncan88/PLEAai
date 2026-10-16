#!/usr/bin/env python3
"""G02b: release-then-accept, raced across processes.

Each round, on a fresh root with k = 1: a1 is reserved, accepted and given its token, then START(a1, n1) is
committed locally (INTENT_PENDING).  Three processes then race:
  acceptor   the witness's ACCEPT_INTENT, after a random delay (the submission in flight);
  releaser   RELEASE(a1, BOUND_FENCE), after a random delay;
  reserver   RESERVE(a2, q2), several times, probing for a freed slot.
Expected in every interleaving: the release is DENIED (rule 3 while pending, rule 4 once consumed); the acceptance
is APPLIED; every RESERVE a2 is DENIED; the round ends with a1 CONSUMED and accepted C = 1.  The audit order
shows which came first, so both orders are counted.  Replay lockstep and the hash chain are checked every round.

usage: g02b.py [--rounds N]
"""
import argparse
import json
import multiprocessing as mp
import random
import time

from common import ADMIN_DSN, Store, fresh_root, invariants_ok, replay_lockstep, store_for, write_output


def racer(root, ops, delay, q):
    time.sleep(delay); out = []
    for op in ops:
        d, _ = store_for(op).apply(root, op)                  # the witness credential for acceptances, local otherwise
        out.append((op[0], d.kind, d.code)); time.sleep(0.001)   # amendment 1: this line had been swallowed by the comment above
    q.put(out)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--rounds', type=int, default=200); a = ap.parse_args()
    store, ctx = Store(ADMIN_DSN), mp.get_context('fork')
    rng = random.Random(20261012)
    failures, order = [], {'accept_first': 0, 'release_first': 0}
    totals = {'release_denied': 0, 'accept_applied': 0, 'reserve_probes': 0, 'reserve_denied': 0, 'final_ok': 0,
              'lockstep_ok': 0, 'chain_ok': 0, 'invariants_ok': 0}
    t0 = time.time()
    for r in range(a.rounds):
        root = f'g02b-{r}'; fresh_root(store, root, 1, 0)
        for op in (('RESERVE', 'a1', 'q1'), ('ACCEPT_RESERVATION', 'a1'), ('TOKEN', 'a1'), ('START', 'a1', 'n1')):
            d, _ = store.apply(root, op)
            if d.kind != 'APPLIED': failures.append((root, 'setup', op, d))
        q = ctx.Queue()
        procs = [ctx.Process(target=racer, args=(root, [('ACCEPT_INTENT', 'a1')], rng.uniform(0, 0.004), q)),
                 ctx.Process(target=racer, args=(root, [('RELEASE', 'a1', 'BOUND_FENCE')], rng.uniform(0, 0.004), q)),
                 ctx.Process(target=racer, args=(root, [('RESERVE', 'a2', 'q2')] * 5, 0.0, q))]
        for p in procs: p.start()
        results = [q.get() for _ in procs]
        for p in procs: p.join()
        flat = [x for res in results for x in res]
        rel = [x for x in flat if x[0] == 'RELEASE']; acc = [x for x in flat if x[0] == 'ACCEPT_INTENT']
        probes = [x for x in flat if x[0] == 'RESERVE']
        totals['reserve_probes'] += len(probes); totals['reserve_denied'] += sum(1 for x in probes if x[1] == 'DENIED')
        if rel and rel[0][1] == 'DENIED': totals['release_denied'] += 1
        else: failures.append((root, 'release', rel))
        if acc and acc[0][1] == 'APPLIED': totals['accept_applied'] += 1
        else: failures.append((root, 'accept', acc))
        if any(x[1] != 'DENIED' for x in probes): failures.append((root, 'probe', probes))
        obs = store.observe(root)
        a1 = [att for att in obs['attempts'] if att[0] == 'a1'][0]
        if a1[2] == 'CONSUMED' and obs['accepted'] == [0, 1, 0] and obs['live'] == [0, 1, 0]: totals['final_ok'] += 1
        else: failures.append((root, 'final', obs))
        ok, why = invariants_ok(obs)
        if ok: totals['invariants_ok'] += 1
        else: failures.append((root, 'invariant', why))
        log = store.audit(root)
        seq_of = {d['op'][0]: d['seq'] for d in log if d['op'][0] in ('RELEASE', 'ACCEPT_INTENT')}
        order['accept_first' if seq_of.get('ACCEPT_INTENT', 0) < seq_of.get('RELEASE', 0) else 'release_first'] += 1
        ok, why, _ = replay_lockstep(store, root, 1, 0)
        if ok: totals['lockstep_ok'] += 1
        else: failures.append((root, 'lockstep', why))
        ok, why = store.verify_chain(root)
        if ok: totals['chain_ok'] += 1
        else: failures.append((root, 'chain', why))
    out = {'rounds': a.rounds, 'seconds': round(time.time() - t0, 1), **totals, 'order': order,
           'failures': failures[:20], 'failure_count': len(failures),
           'PASS': not failures and all(totals[x] == a.rounds for x in ('release_denied', 'accept_applied', 'final_ok',
                                                                        'lockstep_ok', 'chain_ok', 'invariants_ok'))
                   and totals['reserve_denied'] == totals['reserve_probes']}
    write_output('g02b.json', out)
    print(json.dumps({k: v for k, v in out.items() if k != 'failures'}, indent=1))
    print('G02b RESULT:', 'PASS' if out['PASS'] else 'FAIL')
    raise SystemExit(0 if out['PASS'] else 1)


if __name__ == '__main__':
    main()
