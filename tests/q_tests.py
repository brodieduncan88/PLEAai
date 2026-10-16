#!/usr/bin/env python3
"""Q1-Q2 (v0.9): the repairs for the v0.8 independent security review's CRITICAL finding, each reproduced first in
plan/repro_counterexamples.py (outputs/review4_repro_v0_8.json).

Q1 transition integrity.  plea_write accepts exactly the per-attempt phase transitions a contract operation
   produces and rejects every other (old -> new) pair.  The two supplied counterexamples are rejected as plea_local
   (CONSUMED->DISCARDED no longer frees a consumed budget; a forged RECOVER no longer flips the mode).  A battery of
   illegal pairs, each forged as the owner so only legality (not authority) is under test, is rejected with
   check_violation; every legal pair applies through the proper credentials; and the fact-shape rules (a new attempt
   is a bare reservation; receipt and crossed are monotone and only on a consumption phase) are enforced.

Q2 control separation.  Every mode change is reserved to the control credential (plea_control).  The gateway
   credential (plea_local) cannot change any mode by any path -- the proper apply, a forged plea_write, or raw DML --
   and its state is unchanged; the control credential can; and the control credential cannot set an accepted phase
   (still the witness's) nor write the authoritative tables directly.
"""
import json
import time

import psycopg

from common import (ADMIN_DSN, CONTROL_DSN, GATEWAY, LOCAL_DSN, WITNESS_DSN, Store,
                    fresh_root, replay_lockstep, write_output)
from plea_gateway import AuthorityError

admin, local, witness, control = Store(ADMIN_DSN), Store(LOCAL_DSN), Store(WITNESS_DSN), Store(CONTROL_DSN)


def refused(label, fn, want):
    try:
        fn(); return (f'{label}: NOT refused', False)
    except want as exc:
        return (f'{label} ({type(exc).__name__})', True)
    except Exception as exc:
        return (f'{label}: unexpected {type(exc).__name__}: {str(exc)[:70]}', False)


def head(root):
    with admin.connect() as c:
        return c.execute('SELECT seq, head_hash FROM roots WHERE root_id=%s', (root,)).fetchone()


def forge(dsn, root, attempts, modes=None, op=('RESERVE', 'x', 'x')):
    """A hand-written plea_write over `dsn`.  Raises the database error on refusal; returns None on commit.
    v1.1: `op` must be a contract operation name (an unknown name is refused before any other rule), and the
    checks that target a flag or an authority rule name the operation that produces their change."""
    seq, h = head(root)
    with psycopg.connect(dsn) as c:
        c.execute('SELECT plea_write(%s, %s::jsonb, %s::jsonb, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s::jsonb)',
                  (root, json.dumps(attempts), json.dumps(modes) if modes is not None else None,
                   seq + 1, 'forged-' + str(seq + 1), json.dumps(list(op)), 'APPLIED', 'FORGED',
                   json.dumps({}), h, None))
        c.commit()


def raw(dsn, sql, params=()):
    try:
        with psycopg.connect(dsn) as c:
            c.execute(sql, params); c.commit(); return True
    except psycopg.Error:
        return False


def build(root, k, upto, m=0):
    """Create root (k, m) and drive 'a1' up to a phase through the proper credentials.  Returns nothing."""
    fresh_root(admin, root, k, m)
    chain = [(local, ('RESERVE', 'a1', 'q1')), (witness, ('ACCEPT_RESERVATION', 'a1')), (local, ('TOKEN', 'a1')),
             (local, ('START', 'a1', 'n1')), (witness, ('ACCEPT_INTENT', 'a1'))]
    want = {'RESERVING': 1, 'RESERVED': 2, 'TOKEN': 3, 'INTENT_PENDING': 4, 'CONSUMED': 5}[upto]
    for st, op in chain[:want]:
        d, _ = st.apply(root, op); assert d.kind == 'APPLIED', (root, op, d)


def phase_of(root, aid='a1'):
    with admin.connect() as c:
        row = c.execute('SELECT phase FROM attempts WHERE root_id=%s AND aid=%s', (root, aid)).fetchone()
    return row[0] if row else None


# ============================================================ Q1: transition integrity
# illegal (old -> new) pairs: not produced by any contract operation; must be refused by legality, for everyone
ILLEGAL = [
    ('CONSUMED', 'DISCARDED'), ('CONSUMED', 'RELEASED'), ('CONSUMED', 'RESERVING'), ('CONSUMED', 'TOKEN'),
    ('RESERVED', 'DISCARDED'), ('RESERVED', 'CONSUMED'), ('TOKEN', 'CONSUMED'),
    ('NO_EFFECT', 'CONSUMED'), ('EFFECT', 'RESERVING'), ('RELEASED', 'RESERVING'),
    ('DISCARDED', 'RESERVING'), ('INDETERMINATE', 'CONSUMED'),
]
# legal (old -> new) pairs and the credential each needs
LEGAL = [
    ('RESERVING', 'RESERVED', witness), ('INTENT_PENDING', 'CONSUMED', witness),
    ('RESERVED', 'RELEASED', witness), ('TOKEN', 'RELEASED', witness),
    ('CONSUMED', 'NO_EFFECT', witness), ('CONSUMED', 'EFFECT', witness),
    ('RESERVED', 'TOKEN', local), ('TOKEN', 'INTENT_PENDING', local),
    ('RESERVING', 'DISCARDED', control), ('INTENT_PENDING', 'TOKEN', control),
    ('RESERVING', 'INDETERMINATE', control), ('CONSUMED', 'INDETERMINATE', control),
]
# which phase 'a1' must be built to, to hold each old phase for the forge
_PRIOR = {'RESERVING': 'RESERVING', 'RESERVED': 'RESERVED', 'TOKEN': 'TOKEN', 'INTENT_PENDING': 'INTENT_PENDING',
          'CONSUMED': 'CONSUMED'}


def _put_a1(root, phase, receipt=False, crossed=False, nonce=None):
    """Owner sets a1 directly to an arbitrary phase (bypassing the engine) to stage a forge's precondition."""
    fresh_root(admin, root, 3, 1)
    with admin.connect() as c:
        c.execute('INSERT INTO attempts (root_id, aid, req, phase, nonce, receipt, crossed) VALUES (%s,%s,%s,%s,%s,%s,%s) '
                  'ON CONFLICT (root_id, aid) DO UPDATE SET phase=EXCLUDED.phase, nonce=EXCLUDED.nonce, receipt=EXCLUDED.receipt, crossed=EXCLUDED.crossed',
                  (root, 'a1', 'q1', phase, nonce, receipt, crossed)); c.commit()


def q1():
    checks = []

    # --- the two supplied counterexamples, as plea_local -------------------------------------------------
    build('q1-cexA', 1, 'CONSUMED')
    checks.append(refused('counterexample A: CONSUMED->DISCARDED forged as plea_local is refused',
                          lambda: forge(LOCAL_DSN, 'q1-cexA', [{'aid': 'a1', 'req': 'q1', 'phase': 'DISCARDED', 'nonce': None, 'receipt': False, 'crossed': False}]),
                          psycopg.errors.CheckViolation))
    d, _ = local.apply('q1-cexA', ('RESERVE', 'a2', 'q2'))
    checks.append(('counterexample A: the consumed budget of one stays exhausted (extra RESERVE denied)', d.kind == 'DENIED' and d.code == 'BUDGET_EXHAUSTED' and phase_of('q1-cexA') == 'CONSUMED'))

    build('q1-cexB', 3, 'RESERVING'); admin.apply('q1-cexB', ('HOLD',))
    checks.append(refused('counterexample B: forged RECOVER mode flip as plea_local is refused',
                          lambda: forge(LOCAL_DSN, 'q1-cexB', [], {'witness': 'ACTIVE', 'business': 'OPEN', 'reregistered': False}, op=('RECOVER', True, True)),
                          psycopg.errors.InsufficientPrivilege))
    checks.append(('counterexample B: the witness stays HELD', admin.observe('q1-cexB')['witness'] == 'HELD'))

    # --- illegal transitions, forged as the OWNER so only legality is under test -------------------------
    bad = 0
    for old, new in ILLEGAL:
        root = f'q1-ill-{old}-{new}'; _put_a1(root, old)
        try:
            forge(ADMIN_DSN, root, [{'aid': 'a1', 'req': 'q1', 'phase': new, 'nonce': None, 'receipt': False, 'crossed': False}])
            ok = False                                                  # committed: the relation let an illegal pair through
        except psycopg.errors.CheckViolation:
            ok = (phase_of(root) == old)                               # refused and unchanged
        except Exception:
            ok = False
        bad += 0 if ok else 1
    checks.append((f'every illegal transition is refused as check_violation and changes nothing ({len(ILLEGAL)} pairs)', bad == 0))

    # --- a straight insert at a non-RESERVING phase is refused ------------------------------------------
    for ph in ('CONSUMED', 'RESERVED', 'TOKEN', 'DISCARDED'):
        root = f'q1-ins-{ph}'; fresh_root(admin, root, 3, 1)
        checks.append(refused(f'inserting a new attempt straight at {ph} is refused',
                              lambda r=root, p=ph: forge(ADMIN_DSN, r, [{'aid': 'ax', 'req': 'qx', 'phase': p, 'nonce': None, 'receipt': False, 'crossed': False}]),
                              psycopg.errors.CheckViolation))

    # --- every legal transition applies through the proper credential -----------------------------------
    good = 0
    for old, new, cred in LEGAL:
        root = f'q1-ok-{old}-{new}'
        if old in _PRIOR:
            build(root, 3, _PRIOR[old], m=1)
        # apply the transition via the operation that produces it, through its credential
        op = {('RESERVING', 'RESERVED'): ('ACCEPT_RESERVATION', 'a1'), ('INTENT_PENDING', 'CONSUMED'): ('ACCEPT_INTENT', 'a1'),
              ('RESERVED', 'RELEASED'): ('RELEASE', 'a1', 'BOUND_FENCE'), ('TOKEN', 'RELEASED'): ('RELEASE', 'a1', 'BOUND_FENCE'),
              ('CONSUMED', 'NO_EFFECT'): ('RECONCILE', 'a1', 'NO_EFFECT', 'AUTHORISED'), ('CONSUMED', 'EFFECT'): ('RECONCILE', 'a1', 'EFFECT', 'AUTHORISED'),
              ('RESERVED', 'TOKEN'): ('TOKEN', 'a1'), ('TOKEN', 'INTENT_PENDING'): ('START', 'a1', 'n1'),
              ('RESERVING', 'DISCARDED'): ('RECOVER', True, True), ('INTENT_PENDING', 'TOKEN'): ('RECOVER', True, True),
              ('RESERVING', 'INDETERMINATE'): ('REREGISTER',), ('CONSUMED', 'INDETERMINATE'): ('REREGISTER',)}[(old, new)]
        if op[0] in ('RECOVER', 'REREGISTER'):
            admin.apply(root, ('HOLD',)) if op[0] == 'RECOVER' else None
        d, _ = cred.apply(root, op)
        got = phase_of(root)
        good += 1 if (d.kind == 'APPLIED' and got == new) else 0
    checks.append((f'every legal transition applies through its proper credential and reaches the new phase ({len(LEGAL)} pairs)', good == len(LEGAL)))

    # --- fact-shape: a new attempt is a bare reservation ------------------------------------------------
    fresh_root(admin, 'q1-bare', 3, 1)
    checks.append(refused('a new attempt carrying crossed=true is refused',
                          lambda: forge(ADMIN_DSN, 'q1-bare', [{'aid': 'ax', 'req': 'qx', 'phase': 'RESERVING', 'nonce': None, 'receipt': False, 'crossed': True}]),
                          psycopg.errors.CheckViolation))
    fresh_root(admin, 'q1-bare2', 3, 1)
    checks.append(refused('a new attempt carrying receipt=true is refused',
                          lambda: forge(ADMIN_DSN, 'q1-bare2', [{'aid': 'ax', 'req': 'qx', 'phase': 'RESERVING', 'nonce': None, 'receipt': True, 'crossed': False}]),
                          psycopg.errors.CheckViolation))

    # --- fact-shape: receipt and crossed are monotone, and only on a consumption phase -----------------
    _put_a1('q1-rcpt', 'CONSUMED', receipt=True)
    checks.append(refused('clearing receipt (true->false) is refused',
                          lambda: forge(ADMIN_DSN, 'q1-rcpt', [{'aid': 'a1', 'req': 'q1', 'phase': 'CONSUMED', 'nonce': None, 'receipt': False, 'crossed': False}]),
                          psycopg.errors.CheckViolation))
    _put_a1('q1-cross', 'CONSUMED', receipt=True, crossed=True)
    checks.append(refused('resetting crossed (true->false, T7) is refused',
                          lambda: forge(ADMIN_DSN, 'q1-cross', [{'aid': 'a1', 'req': 'q1', 'phase': 'CONSUMED', 'nonce': None, 'receipt': True, 'crossed': False}]),
                          psycopg.errors.CheckViolation))
    _put_a1('q1-cph', 'RESERVED')
    checks.append(refused('setting crossed on a non-consumption phase (RESERVED) is refused',
                          lambda: forge(ADMIN_DSN, 'q1-cph', [{'aid': 'a1', 'req': 'q1', 'phase': 'RESERVED', 'nonce': None, 'receipt': False, 'crossed': True}], op=('CROSS', 'a1')),
                          psycopg.errors.CheckViolation))
    _put_a1('q1-rph', 'RESERVED')
    checks.append(refused('setting receipt on a non-consumption phase (RESERVED) is refused',
                          lambda: forge(ADMIN_DSN, 'q1-rph', [{'aid': 'a1', 'req': 'q1', 'phase': 'RESERVED', 'nonce': None, 'receipt': True, 'crossed': False}], op=('RECEIPT', 'a1')),
                          psycopg.errors.CheckViolation))

    checks.append(('replay lockstep on a governed root through the proper credentials', replay_lockstep(admin, 'q1-ok-CONSUMED-EFFECT', 3, 1)[0]))
    return checks


# ============================================================ Q2: control separation
def q2():
    checks = []

    # plea_local cannot apply any control operation through the proper path; the state is unchanged.
    # Each precondition and op is set up so the reference engine would APPLY it (reaching the guarded write).
    def local_refused(name, root, setup, op):
        build(root, 3, 'CONSUMED')                                      # a1 consumed; business OPEN, witness ACTIVE
        for o in setup:
            d, _ = admin.apply(root, o); assert d.kind == 'APPLIED', (root, o, d)   # owner stages the precondition
        pre = admin.observe(root)
        label, ok = refused(f'plea_local cannot apply {name}', lambda: local.apply(root, op), AuthorityError)
        checks.append((label + '; state unchanged', ok and admin.observe(root) == pre))
    local_refused('HOLD', 'q2-loc-HOLD', [], ('HOLD',))
    local_refused('STOP', 'q2-loc-STOP', [], ('STOP',))
    local_refused('TERMINALISE', 'q2-loc-TERM', [('STOP',)], ('TERMINALISE',))
    local_refused('TERMINAL', 'q2-loc-TERMINAL', [('RECONCILE', 'a1', 'EFFECT', 'AUTHORISED'), ('STOP',), ('TERMINALISE',)], ('TERMINAL',))
    local_refused('REREGISTER', 'q2-loc-REREG', [], ('REREGISTER',))
    local_refused('RECOVER', 'q2-loc-RECOVER', [('HOLD',)], ('RECOVER', True, True))

    # plea_local forging a mode change through plea_write is refused, by any mode
    build('q2-forge-w', 3, 'RESERVING'); admin.apply('q2-forge-w', ('HOLD',))
    checks.append(refused('plea_local forging witness HELD->ACTIVE via plea_write is refused',
                          lambda: forge(LOCAL_DSN, 'q2-forge-w', [], {'witness': 'ACTIVE', 'business': 'OPEN', 'reregistered': False}, op=('RECOVER', True, True)),
                          psycopg.errors.InsufficientPrivilege))
    checks.append(('the witness stays HELD after the forged flip', admin.observe('q2-forge-w')['witness'] == 'HELD'))
    build('q2-forge-b', 3, 'RESERVING')
    checks.append(refused('plea_local forging business OPEN->STOPPING via plea_write is refused',
                          lambda: forge(LOCAL_DSN, 'q2-forge-b', [], {'witness': 'ACTIVE', 'business': 'STOPPING', 'reregistered': False}, op=('STOP',)),
                          psycopg.errors.InsufficientPrivilege))
    checks.append(('business stays OPEN after the forged flip', admin.observe('q2-forge-b')['business'] == 'OPEN'))

    # plea_local cannot change a mode by raw DML either
    build('q2-raw', 3, 'RESERVING'); admin.apply('q2-raw', ('HOLD',))
    allowed = raw(LOCAL_DSN, "UPDATE roots SET witness='ACTIVE' WHERE root_id=%s", ('q2-raw',))
    checks.append(('plea_local raw UPDATE of the witness mode is refused; it stays HELD', (not allowed) and admin.observe('q2-raw')['witness'] == 'HELD'))

    # the control credential CAN change modes
    root = 'q2-ctl-ok'; build(root, 3, 'RESERVING')
    d1, _ = control.apply(root, ('HOLD',)); d2, o2 = control.apply(root, ('RECOVER', True, True))
    checks.append(('plea_control applies HOLD then RECOVER: HELD then ACTIVE', d1.kind == 'APPLIED' and d2.kind == 'APPLIED' and o2['witness'] == 'ACTIVE'))
    root = 'q2-ctl-rereg'; build(root, 3, 'CONSUMED')
    d, o = control.apply(root, ('REREGISTER',))
    checks.append(('plea_control applies REREGISTER: business STOPPING, reregistered', d.kind == 'APPLIED' and o['business'] == 'STOPPING' and o['reregistered']))

    # the control credential is NOT the witness: it cannot set an accepted phase, nor write the tables directly
    build('q2-ctl-wit', 3, 'RESERVING')
    checks.append(refused('plea_control cannot forge an accepted phase (RESERVING->RESERVED is the witness\'s)',
                          lambda: forge(CONTROL_DSN, 'q2-ctl-wit', [{'aid': 'a1', 'req': 'q1', 'phase': 'RESERVED', 'nonce': None, 'receipt': False, 'crossed': False}], op=('ACCEPT_RESERVATION', 'a1')),
                          psycopg.errors.InsufficientPrivilege))
    checks.append(('plea_control has no direct DML on the authoritative tables',
                   not raw(CONTROL_DSN, "UPDATE roots SET k=9 WHERE root_id=%s", ('q2-ctl-wit',))))
    checks.append(('plea_control applied op leaves the chain valid', admin.verify_chain('q2-ctl-ok')[0]))
    return checks


def main():
    t0 = time.time()
    out = {'Q1': q1(), 'Q2': q2()}
    out['seconds'] = round(time.time() - t0, 1)
    for k in ('Q1', 'Q2'):
        out[k + '_ok'] = all(ok for _, ok in out[k])
    out['PASS'] = all(out[k + '_ok'] for k in ('Q1', 'Q2'))
    out['Q1_count'] = len(out['Q1']); out['Q2_count'] = len(out['Q2'])
    write_output('q_tests.json', out)
    for k in ('Q1', 'Q2'):
        for label, ok in out[k]:
            print(k, 'ok  ' if ok else 'FAIL', label)
    print(json.dumps({k: v for k, v in out.items() if k not in ('Q1', 'Q2')}, indent=1))
    print('Q RESULT:', 'PASS' if out['PASS'] else 'FAIL'); raise SystemExit(0 if out['PASS'] else 1)


if __name__ == '__main__':
    main()
