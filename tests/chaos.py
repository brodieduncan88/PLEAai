#!/usr/bin/env python3
"""Chaos: kill the process at every statement boundary of the store's transaction, for every operation.

For each operation, a root is prepared so that the operation is APPLIED (so the crash matters), and a twin root
with the same preparation gives the expected post-state by applying the operation without a crash.  A child
process then applies the operation to the prepared root with PLEA_CRASH_AT set to one of six points:
  after_lock, after_decide, after_attempts, after_audit, before_commit   -> the child dies inside the transaction:
                                                                            the state must equal the pre-state;
  after_commit                                                           -> the state must equal the post-state.
After every kill: the child's exit code is 137; invariants hold; the hash chain verifies; replay lockstep against
the oracle passes; and a follow-up operation on the same root succeeds, which shows no lock was left behind.
"""
import json
import os
import subprocess
import time

from common import ADMIN_DSN, LOCAL_DSN, WITNESS_DSN, PYTHON, HERE, Store, fresh_root, invariants_ok, replay_lockstep, write_output
from plea_gateway.faults import CRASH_POINTS

K, M = 2, 1
tokened = [('RESERVE', 'a1', 'q1'), ('ACCEPT_RESERVATION', 'a1'), ('TOKEN', 'a1')]
pending = tokened + [('START', 'a1', 'n1')]
consumed = pending + [('ACCEPT_INTENT', 'a1')]
CASES = [   # (name, setup, op that is APPLIED on the prepared state)
    ('RESERVE', [], ('RESERVE', 'a1', 'q1')),
    ('ACCEPT_RESERVATION', [('RESERVE', 'a1', 'q1')], ('ACCEPT_RESERVATION', 'a1')),
    ('TOKEN', tokened[:2], ('TOKEN', 'a1')),
    ('START', tokened, ('START', 'a1', 'n1')),
    ('ACCEPT_INTENT', pending, ('ACCEPT_INTENT', 'a1')),
    ('RECEIPT', consumed, ('RECEIPT', 'a1')),
    ('CROSS', consumed + [('RECEIPT', 'a1')], ('CROSS', 'a1')),
    ('RELEASE', tokened, ('RELEASE', 'a1', 'BOUND_FENCE')),
    ('RECONCILE', consumed, ('RECONCILE', 'a1', 'NO_EFFECT', 'AUTHORISED')),
    ('HOLD', pending, ('HOLD',)),
    ('STOP', consumed, ('STOP',)),
    ('RECOVER', pending + [('HOLD',)], ('RECOVER', True, True)),
    ('REREGISTER', consumed, ('REREGISTER',)),
    ('TERMINALISE', consumed + [('STOP',)], ('TERMINALISE',)),
    ('TERMINAL', consumed + [('RECONCILE', 'a1', 'EFFECT', 'AUTHORISED'), ('STOP',), ('TERMINALISE',)], ('TERMINAL',)),
]


def prepare(store, root, setup):
    fresh_root(store, root, K, M)
    for op in setup:
        d, _ = store.apply(root, op)
        assert d.kind == 'APPLIED', (root, op, d)


def main():
    store = Store(ADMIN_DSN); rows, failures = [], []; t0 = time.time()
    for name, setup, op in CASES:
        twin = f'chaos-twin-{name}'; prepare(store, twin, setup)
        d, post = store.apply(twin, op)
        assert d.kind == 'APPLIED', (name, d)
        for point in CRASH_POINTS:
            root = f'chaos-{name}-{point}'; prepare(store, root, setup)
            pre = store.observe(root); pre_chain = len(store.audit(root))
            env = dict(os.environ, PLEA_CRASH_AT=point, PLEA_LOCAL_DSN=LOCAL_DSN, PLEA_WITNESS_DSN=WITNESS_DSN)
            proc = subprocess.run([PYTHON, '-B', str(HERE / 'apply_once.py'), root, json.dumps(op)],
                                  env=env, capture_output=True, text=True, timeout=60)
            obs = store.observe(root)
            want = post if point == 'after_commit' else pre
            row = {'op': name, 'point': point, 'exit': proc.returncode, 'state_as_expected': obs == want,
                   'invariants': invariants_ok(obs)[0], 'chain': store.verify_chain(root)[0],
                   'lockstep': replay_lockstep(store, root, K, M)[0],
                   'log_len': len(store.audit(root)), 'expected_log_len': pre_chain + (1 if point == 'after_commit' else 0)}
            try:
                d2, _ = store.apply(root, ('CRASH',))              # a NOOP fact: proves the row lock was released
                row['follow_up'] = d2.kind == 'NOOP'
            except Exception as exc:
                row['follow_up'] = False; row['follow_up_error'] = repr(exc)[:120]
            row['ok'] = (row['exit'] == 137 and row['state_as_expected'] and row['invariants'] and row['chain']
                         and row['lockstep'] and row['follow_up'] and row['log_len'] == row['expected_log_len'])
            rows.append(row)
            if not row['ok']:
                failures.append({**row, 'stderr': proc.stderr[-300:], 'pre': pre, 'post': post, 'obs': obs})
    out = {'kills': len(rows), 'ok': sum(r['ok'] for r in rows), 'seconds': round(time.time() - t0, 1),
           'by_point': {p: sum(r['ok'] for r in rows if r['point'] == p) for p in CRASH_POINTS},
           'failures': failures[:10], 'failure_count': len(failures), 'rows': rows, 'PASS': not failures}
    write_output('chaos.json', out)
    print(json.dumps({k: v for k, v in out.items() if k not in ('rows', 'failures')}, indent=1))
    if failures: print(json.dumps(failures[:3], indent=1, default=str))
    print('CHAOS RESULT:', 'PASS' if out['PASS'] else 'FAIL')
    raise SystemExit(0 if out['PASS'] else 1)


if __name__ == '__main__':
    main()
