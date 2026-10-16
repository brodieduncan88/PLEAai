#!/usr/bin/env python3
"""G01: the last-slot race against a real transactional store, across processes.

Each round, on a fresh root with budget k and allowance 0:
  wave 1   W worker processes release from a barrier and each RESERVE a distinct attempt.  Exactly k are APPLIED
           and W - k are DENIED.
  crash    j of the k winners are accepted by the witness; the other k - j are left RESERVING, which is the state a
           caller leaves behind when it dies between its local commit and the witness's acceptance.
  recovery HOLD, then RECOVER(true, true): the k - j never-accepted reservations become DISCARDED and free exactly
           their slots.
  wave 2   W fresh workers RESERVE again.  Exactly k - j are APPLIED.
  checks   a reader thread observes the root throughout and checks I1, I2, I3 and I6 on every consistent snapshot;
           the audit log is replayed through the independent oracle (replay lockstep); the hash chain is verified.

usage: g01_race.py [--rounds N] [--workers W] [--k K] [--mode lock|serializable]
"""
import argparse
import json
import multiprocessing as mp
import threading
import time

from common import ADMIN_DSN, CONTROL_DSN, LOCAL_DSN, WITNESS_DSN, Store, fresh_root, invariants_ok, replay_lockstep, write_output


def worker(mode, task_q, result_q, barrier):
    store = Store(LOCAL_DSN, mode=mode)                   # a caller holds the local credential
    while True:
        task = task_q.get()
        if task is None:
            return
        root, aid, req = task
        barrier.wait()
        try:
            d, _ = store.apply(root, ('RESERVE', aid, req))
            result_q.put((aid, d.kind, d.code))
        except Exception as exc:                          # amendment 1: a worker error is a reported failure, not a hang
            result_q.put((aid, 'ERROR', repr(exc)[:160]))


def reader(store, current, stop, stats):
    while not stop.is_set():
        root = current.get('root')
        if root:
            try:
                obs = store.observe(root)
            except Exception as exc:                      # the root may be mid-recreation between rounds
                stats['reader_errors'] += 1; continue
            ok, why = invariants_ok(obs)
            stats['reads'] += 1
            if not ok:
                stats['violations'].append((root, why, obs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rounds', type=int, default=1000); ap.add_argument('--workers', type=int, default=16)
    ap.add_argument('--k', type=int, default=3); ap.add_argument('--mode', default='lock')
    a = ap.parse_args()
    store = Store(ADMIN_DSN, mode=a.mode); witness = Store(WITNESS_DSN, mode=a.mode); local = Store(LOCAL_DSN, mode=a.mode); control = Store(CONTROL_DSN, mode=a.mode)
    ctx = mp.get_context('fork')
    task_q, result_q, barrier = ctx.Queue(), ctx.Queue(), ctx.Barrier(a.workers)
    procs = [ctx.Process(target=worker, args=(a.mode, task_q, result_q, barrier), daemon=True) for _ in range(a.workers)]
    for p in procs: p.start()
    current, stop = {'root': None}, threading.Event()
    stats = {'reads': 0, 'violations': [], 'reader_errors': 0}
    rt = threading.Thread(target=reader, args=(Store(LOCAL_DSN), current, stop, stats), daemon=True); rt.start()

    failures, t0 = [], time.time()
    totals = {'reserve_ops': 0, 'worker_errors': 0, 'wave1_exact': 0, 'wave2_exact': 0, 'recoveries': 0, 'discarded': 0,
              'lockstep_ok': 0, 'chain_ok': 0, 'decisions_replayed': 0}
    for r in range(a.rounds):
        root = f'g01-{a.mode}-{r}'
        fresh_root(store, root, a.k, 0); current['root'] = root
        # wave 1
        for w in range(a.workers): task_q.put((root, f'a{r}-{w}', f'q{r}-{w}'))
        res = [result_q.get(timeout=120) for _ in range(a.workers)]; totals['reserve_ops'] += a.workers
        totals['worker_errors'] += sum(1 for _, kind, _ in res if kind == 'ERROR')
        winners = sorted(aid for aid, kind, _ in res if kind == 'APPLIED')
        kinds = {kind for _, kind, _ in res}
        if len(winners) == a.k and kinds <= {'APPLIED', 'DENIED'}:
            totals['wave1_exact'] += 1
        else:
            failures.append((root, 'wave1', res))
        # crash by omission, then recovery
        j = r % (a.k + 1)
        for aid in winners[:j]:
            d, _ = witness.apply(root, ('ACCEPT_RESERVATION', aid))     # only the witness credential can
            if d.kind != 'APPLIED': failures.append((root, 'accept', aid, d))
        d, _ = control.apply(root, ('HOLD',))                              # v0.9: the control plane changes modes
        if d.kind != 'APPLIED': failures.append((root, 'hold', d))
        d, obs = control.apply(root, ('RECOVER', True, True))
        if d.kind != 'APPLIED': failures.append((root, 'recover', d))     # always APPLIED: the witness becomes ACTIVE
        else: totals['recoveries'] += 1
        discarded = sum(1 for att in obs['attempts'] if att[2] == 'DISCARDED')
        totals['discarded'] += discarded
        if discarded != a.k - j or obs['live'] != [j, 0, 0] or obs['witness'] != 'ACTIVE':
            failures.append((root, 'after-recovery', j, obs))
        # wave 2
        for w in range(a.workers): task_q.put((root, f'b{r}-{w}', f'p{r}-{w}'))
        res2 = [result_q.get(timeout=120) for _ in range(a.workers)]; totals['reserve_ops'] += a.workers
        totals['worker_errors'] += sum(1 for _, kind, _ in res2 if kind == 'ERROR')
        n2 = sum(1 for _, kind, _ in res2 if kind == 'APPLIED')
        if n2 == a.k - j: totals['wave2_exact'] += 1
        else: failures.append((root, 'wave2', j, res2))
        # replay lockstep against the oracle, and the chain
        ok, why, n = replay_lockstep(store, root, a.k, 0); totals['decisions_replayed'] += n
        if ok: totals['lockstep_ok'] += 1
        else: failures.append((root, 'lockstep', why))
        ok, why = store.verify_chain(root)
        if ok: totals['chain_ok'] += 1
        else: failures.append((root, 'chain', why))
        if r % 100 == 99:
            print(f'round {r + 1}: wave1 exact {totals["wave1_exact"]}, wave2 exact {totals["wave2_exact"]}, '
                  f'reader reads {stats["reads"]}, violations {len(stats["violations"])}, failures {len(failures)}', flush=True)
    stop.set(); rt.join(timeout=5)
    for _ in procs: task_q.put(None)
    for p in procs: p.join(timeout=5)
    out = {'mode': a.mode, 'rounds': a.rounds, 'workers': a.workers, 'k': a.k, 'seconds': round(time.time() - t0, 1),
           **totals, 'reader_reads': stats['reads'], 'reader_violations': stats['violations'][:5],
           'reader_violation_count': len(stats['violations']), 'reader_errors': stats['reader_errors'],
           'failures': failures[:20], 'failure_count': len(failures),
           'PASS': not failures and not stats['violations'] and totals['worker_errors'] == 0 and totals['wave1_exact'] == a.rounds
                   and totals['wave2_exact'] == a.rounds and totals['lockstep_ok'] == a.rounds and totals['chain_ok'] == a.rounds}
    write_output(f'g01_{a.mode}.json', out)
    print(json.dumps({k: v for k, v in out.items() if k not in ('failures', 'reader_violations')}, indent=1))
    print('G01 RESULT:', 'PASS' if out['PASS'] else 'FAIL')
    raise SystemExit(0 if out['PASS'] else 1)


if __name__ == '__main__':
    main()
