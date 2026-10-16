#!/usr/bin/env python3
"""W1: the authority boundary is enforced by the database, not by the gateway's code.

For each of the four acceptances and the crossing, on a state where it would be APPLIED:
  local      applying it through the plea_local credential raises AuthorityError; the state and the audit log are
             unchanged (the transaction rolled back);
  witness    applying it through the plea_witness credential is APPLIED.
v0.9: the control-plane operations (HOLD, STOP, TERMINALISE, TERMINAL, RECOVER, REREGISTER), which change a mode, are
the same way: applying one through plea_local raises AuthorityError and changes nothing, and it is APPLIED through
the plea_control credential.  Then, bypassing the application entirely, raw SQL as plea_local tries to set each
accepted phase and to insert an acceptance into the audit log: every statement is refused.  Finally, every genuine
gateway operation is shown to be APPLIED or NOOP through the plea_local credential, so the boundary blocks nothing it
should allow.  v0.7: CROSS moved from the local operations to the witnessed ones, and raw SQL setting crossed is
refused.
"""
import json
import time

import psycopg
from psycopg import errors

from common import ADMIN_DSN, CONTROL_DSN, LOCAL_DSN, WITNESS_DSN, Store, fresh_root, replay_lockstep, write_output
from plea_gateway import AuthorityError

tokened = [('RESERVE', 'a1', 'q1'), ('ACCEPT_RESERVATION', 'a1'), ('TOKEN', 'a1')]
pending = tokened + [('START', 'a1', 'n1')]
consumed = pending + [('ACCEPT_INTENT', 'a1')]
ACCEPT_CASES = [
    ('ACCEPT_RESERVATION', [('RESERVE', 'a1', 'q1')], ('ACCEPT_RESERVATION', 'a1')),
    ('ACCEPT_INTENT', pending, ('ACCEPT_INTENT', 'a1')),
    ('RELEASE', tokened, ('RELEASE', 'a1', 'BOUND_FENCE')),
    ('RECONCILE', consumed, ('RECONCILE', 'a1', 'NO_EFFECT', 'AUTHORISED')),
    ('CROSS', consumed + [('RECEIPT', 'a1')], ('CROSS', 'a1')),                 # v0.7: the crossing is witnessed
]
LOCAL_CASES = [            # the genuine gateway operations: applied through plea_local
    ('RESERVE', [], ('RESERVE', 'a1', 'q1'), 'APPLIED'),
    ('TOKEN', tokened[:2], ('TOKEN', 'a1'), 'APPLIED'),
    ('START', tokened, ('START', 'a1', 'n1'), 'APPLIED'),
    ('RECEIPT', consumed, ('RECEIPT', 'a1'), 'APPLIED'),
    ('TIMEOUT', consumed, ('TIMEOUT', 'a1'), 'NOOP'),
    ('MISSING_RECEIPT', consumed, ('MISSING_RECEIPT', 'a1'), 'NOOP'),
    ('CRASH', consumed, ('CRASH',), 'NOOP'),
]
CONTROL_CASES = [          # v0.9: the control-plane operations: refused to plea_local, applied through plea_control
    ('HOLD', pending, ('HOLD',)),
    ('STOP', consumed, ('STOP',)),
    ('TERMINALISE', consumed + [('STOP',)], ('TERMINALISE',)),
    ('TERMINAL', consumed + [('RECONCILE', 'a1', 'EFFECT', 'AUTHORISED'), ('STOP',), ('TERMINALISE',)], ('TERMINAL',)),
    ('RECOVER', pending + [('HOLD',)], ('RECOVER', True, True)),
    ('REREGISTER', consumed, ('REREGISTER',)),
]
ACCEPTED_PHASES = ('RESERVED', 'CONSUMED', 'RELEASED', 'NO_EFFECT', 'EFFECT')


def prepare(admin, root, setup):
    fresh_root(admin, root, 2, 1)
    for op in setup:
        d, _ = admin.apply(root, op); assert d.kind == 'APPLIED', (root, op, d)


def main():
    admin, local, witness, control = Store(ADMIN_DSN), Store(LOCAL_DSN), Store(WITNESS_DSN), Store(CONTROL_DSN)
    rows, failures, t0 = [], [], time.time()
    for name, setup, op in ACCEPT_CASES:
        root = f'w1-{name}'; prepare(admin, root, setup)
        pre, pre_len = admin.observe(root), len(admin.audit(root))
        try:
            local.apply(root, op); local_ok, detail = False, 'applied by plea_local'
        except AuthorityError as exc:
            local_ok, detail = True, str(exc)[:80]
        unchanged = admin.observe(root) == pre and len(admin.audit(root)) == pre_len
        d, _ = witness.apply(root, op)
        row = {'case': name, 'local_refused': local_ok, 'state_unchanged': unchanged, 'applied_by': 'witness', 'applied_kind': d.kind,
               'lockstep': replay_lockstep(admin, root, 2, 1)[0], 'detail': detail}
        row['ok'] = local_ok and unchanged and d.kind == 'APPLIED' and row['lockstep']
        rows.append(row); failures += [] if row['ok'] else [row]
    # v0.9: the control-plane operations, refused to plea_local and applied through plea_control
    for name, setup, op in CONTROL_CASES:
        root = f'w1-ctl-{name}'; prepare(admin, root, setup)
        pre, pre_len = admin.observe(root), len(admin.audit(root))
        try:
            local.apply(root, op); local_ok, detail = False, 'applied by plea_local'
        except AuthorityError as exc:
            local_ok, detail = True, str(exc)[:80]
        unchanged = admin.observe(root) == pre and len(admin.audit(root)) == pre_len
        d, _ = control.apply(root, op)
        row = {'case': name, 'local_refused': local_ok, 'state_unchanged': unchanged, 'applied_by': 'control', 'applied_kind': d.kind,
               'lockstep': replay_lockstep(admin, root, 2, 1)[0], 'detail': detail}
        row['ok'] = local_ok and unchanged and d.kind == 'APPLIED' and row['lockstep']
        rows.append(row); failures += [] if row['ok'] else [row]
    # raw SQL as plea_local, bypassing the application
    raw = []
    root = 'w1-raw'; prepare(admin, root, tokened)
    with psycopg.connect(LOCAL_DSN) as conn:
        for phase in ACCEPTED_PHASES:
            try:
                conn.execute('UPDATE attempts SET phase = %s WHERE root_id = %s AND aid = %s', (phase, root, 'a1')); conn.commit()
                raw.append({'stmt': f'UPDATE phase {phase}', 'refused': False})
            except errors.InsufficientPrivilege:
                conn.rollback(); raw.append({'stmt': f'UPDATE phase {phase}', 'refused': True})
        for phase in ACCEPTED_PHASES:
            try:
                conn.execute('INSERT INTO attempts (root_id, aid, req, phase, nonce) VALUES (%s, %s, %s, %s, %s)', (root, 'ax', 'qx', phase, 'nx' if phase in ('CONSUMED', 'NO_EFFECT', 'EFFECT') else None)); conn.commit()
                raw.append({'stmt': f'INSERT phase {phase}', 'refused': False})
            except errors.InsufficientPrivilege:
                conn.rollback(); raw.append({'stmt': f'INSERT phase {phase}', 'refused': True})
        try:                                                                    # v0.7: crossed is the witness's to set
            conn.execute('UPDATE attempts SET crossed = true WHERE root_id = %s AND aid = %s', (root, 'a1')); conn.commit()
            raw.append({'stmt': 'UPDATE crossed = true', 'refused': False})
        except errors.InsufficientPrivilege:
            conn.rollback(); raw.append({'stmt': 'UPDATE crossed = true', 'refused': True})
        for opname in ('ACCEPT_RESERVATION', 'ACCEPT_INTENT', 'RELEASE', 'RECONCILE', 'CROSS'):
            try:
                conn.execute('INSERT INTO decisions (root_id, seq, op, kind, code, observation, prev_hash, hash) VALUES (%s, 999, %s, %s, %s, %s, %s, %s)',
                             (root, json.dumps([opname, 'a1']), 'APPLIED', 'FORGED', '{}', 'x', 'y')); conn.commit()
                raw.append({'stmt': f'INSERT decision {opname}', 'refused': False})
            except errors.InsufficientPrivilege:
                conn.rollback(); raw.append({'stmt': f'INSERT decision {opname}', 'refused': True})
    raw_unchanged = admin.observe(root)['attempts'] == [['a1', 'q1', 'TOKEN', None, False, False]]
    # the local operations, through plea_local
    local_rows = []
    for name, setup, op, want in LOCAL_CASES:
        root = f'w1-local-{name}'; prepare(admin, root, setup)
        try:
            d, _ = local.apply(root, op); got = d.kind
        except AuthorityError as exc:
            got = 'AuthorityError'
        local_rows.append({'op': name, 'kind': got, 'ok': got == want})
    out = {'seconds': round(time.time() - t0, 1), 'reserved_operations': rows, 'raw_sql': raw, 'raw_state_unchanged': raw_unchanged,
           'local_operations': local_rows,
           'reserved_refused_to_local': sum(r['local_refused'] for r in rows), 'raw_statements_refused': sum(r['refused'] for r in raw),
           'local_operations_ok': sum(r['ok'] for r in local_rows),
           'PASS': all(r['ok'] for r in rows) and all(r['refused'] for r in raw) and raw_unchanged and all(r['ok'] for r in local_rows)}
    write_output('w1_authority.json', out)
    print(json.dumps({k: v for k, v in out.items() if k not in ('reserved_operations', 'raw_sql', 'local_operations')}, indent=1))
    for r in rows + raw + local_rows:
        if not r.get('ok', r.get('refused')): print('FAIL', r)
    print('W1 RESULT:', 'PASS' if out['PASS'] else 'FAIL'); raise SystemExit(0 if out['PASS'] else 1)


if __name__ == '__main__':
    main()
