#!/usr/bin/env python3
"""Run the v0.8 review's two counterexamples against native PostgreSQL, as plea_local, through plea_write.

Usage: repro_counterexamples.py <code_dir> <db> <label>

Each counterexample is driven exactly as the reviewer described: a hand-written call to the owner-side write
function plea_write, issued over a real connection authenticated as the gateway credential plea_local.  The only
thing that differs between the two runs is which version's plea_write is installed in the database (v0.8 or v0.9);
the attack SQL is identical.  Emits one JSON object on stdout.

Scenario A -- "Budget of one already consumed; changing CONSUMED to DISCARDED makes another reservation possible."
Scenario B -- "Run is held, recovery is not approved; an operation named RECOVER satisfies the mode check."
"""
import json
import sys

sys.path.insert(0, sys.argv[1])
CODE, DB, LABEL = sys.argv[1], sys.argv[2], sys.argv[3]

import psycopg                                      # noqa: E402
from plea_gateway import Store                      # noqa: E402

A = f'postgresql://plea:plea@127.0.0.1:5432/{DB}'
L = f'postgresql://plea_local:local@127.0.0.1:5432/{DB}'
W = f'postgresql://plea_witness:witness@127.0.0.1:5432/{DB}'
adm, loc, wit = Store(A), Store(L), Store(W)


def reset():
    adm.init_schema(drop=True)
    adm.init_authority()


def fresh(root, k, m=0):
    with adm.connect() as c:
        c.execute('DELETE FROM roots WHERE root_id=%s', (root,)); c.commit()
    adm.new_root(root, k, m)


def head(root):
    with adm.connect() as c:
        return c.execute('SELECT seq, head_hash FROM roots WHERE root_id=%s', (root,)).fetchone()


def forge(root, attempts, modes, op):
    """A hand-written plea_write over a plea_local connection.  Returns (accepted, detail)."""
    seq, h = head(root)
    try:
        with psycopg.connect(L) as c:
            c.execute('SELECT plea_write(%s, %s::jsonb, %s::jsonb, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s::jsonb)',
                      (root, json.dumps(attempts), json.dumps(modes) if modes is not None else None,
                       seq + 1, 'forged-head-' + str(seq + 1), json.dumps(list(op)), 'APPLIED', 'FORGED',
                       json.dumps({}), h, None))
            c.commit()
        return True, 'committed'
    except psycopg.Error as exc:
        return False, f'{type(exc).__name__}: {str(exc).splitlines()[0]}'


def witness_mode(root):
    with adm.connect() as c:
        return c.execute('SELECT witness FROM roots WHERE root_id=%s', (root,)).fetchone()[0]


# ---- Scenario A: CONSUMED -> DISCARDED frees a k=1 budget --------------------------------------------------
def scenario_a():
    root = 'cexA'; fresh(root, 1, 0)
    for st, op in [(loc, ('RESERVE', 'a1', 'q1')), (wit, ('ACCEPT_RESERVATION', 'a1')), (loc, ('TOKEN', 'a1')),
                   (loc, ('START', 'a1', 'n1')), (wit, ('ACCEPT_INTENT', 'a1'))]:
        st.apply(root, op)
    before = adm.observe(root)['live']                             # [R, C, N]; expect [0,1,0], budget exhausted
    # baseline: a second reservation is correctly denied before the attack
    d0, _ = loc.apply(root, ('RESERVE', 'a2', 'q2'))
    accepted, detail = forge(root, [{'aid': 'a1', 'req': 'q1', 'phase': 'DISCARDED',
                                     'nonce': None, 'receipt': False, 'crossed': False}], None, ('FORGE_DISCARD', 'a1'))
    after = adm.observe(root)['live']
    # after the attack, try the extra reservation again
    d1, o1 = loc.apply(root, ('RESERVE', 'a3', 'q3'))
    return {
        'name': 'A: CONSUMED->DISCARDED frees a consumed budget of one',
        'k': 1, 'live_before_attack': before,
        'baseline_second_reserve': [d0.kind, d0.code],
        'forged_write_accepted': accepted, 'forged_write_detail': detail,
        'live_after_attack': after,
        'extra_reservation_after_attack': [d1.kind, d1.code],
        'budget_breached': (d1.kind == 'APPLIED'),
    }


# ---- Scenario B: forged RECOVER flips witness HELD -> ACTIVE without approval ------------------------------
def scenario_b():
    root = 'cexB'; fresh(root, 3, 0)
    loc.apply(root, ('RESERVE', 'a1', 'q1'))
    adm.apply(root, ('HOLD',))                                     # precondition via the owner (works in both versions)
    before = witness_mode(root)                                    # HELD
    accepted, detail = forge(root, [], {'witness': 'ACTIVE', 'business': 'OPEN', 'reregistered': False},
                             ('RECOVER', True, True))
    after = witness_mode(root)
    return {
        'name': 'B: a forged RECOVER flips witness HELD->ACTIVE without approval',
        'witness_before_attack': before,
        'forged_write_accepted': accepted, 'forged_write_detail': detail,
        'witness_after_attack': after,
        'mode_breached': (before == 'HELD' and after == 'ACTIVE'),
    }


def main():
    reset()
    out = {'label': LABEL, 'code_dir': CODE, 'db': DB,
           'scenario_A': scenario_a(), 'scenario_B': scenario_b()}
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
