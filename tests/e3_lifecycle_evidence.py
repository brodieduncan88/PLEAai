#!/usr/bin/env python3
"""E3 (G03): the governed lifecycle with evidence, over HTTP, with the governor as the gate.

Part A.  Four roots with k = 3, m = 1.  Five distinct calls each; the second raises NoEffect.  Expected per root:
c1 EFFECT, c2 NO_EFFECT (credit 1), c3 EFFECT, c4 admitted on the credit and EFFECT, c5 DENIED.  So 4 calls run,
1 is denied, the credit is 1, every RECONCILE in the audit log carries AUTHORISED, four evidence rows are
recorded with derived AUTHORISED, and replay lockstep and the chain hold.

Part B.  Two roots with k = 3, m = 1 whose governor holds a gate key the service does not pin.  Every call runs
(the gate's CROSS does not depend on evidence) but every RECONCILE is DENIED with NONE: the attempts stay CONSUMED,
no credit appears, and the fourth call is DENIED at the budget.  3 run, 2 denied.  v0.6: the governor no longer
returns a value the witness refused the verdict for; each of the 3 raises VerdictRefused carrying the result.
"""
import json
import time

from common import ADMIN_DSN, GATE, LOCAL_DSN, Store, WitnessService, fresh_root, replay_lockstep, write_output
from plea_gateway import BudgetExhausted, GateSigner, Governor, NoEffect, RemoteWitness, VerdictRefused
from plea_gateway.governor import attempt_id   # Amendment 17 (D21)


def run_root(admin, local, w, root, gate, raise_on_second: bool):
    fresh_root(admin, root, 3, 1)
    gov = Governor(local, w, root, 3, 1, admin=admin, gate=gate)
    ran, outcome = [], {'ran': 0, 'no_effect': 0, 'denied': 0, 'verdict_refused': 0, 'other': 0}
    def work(i):
        ran.append(i)
        if raise_on_second and i == 2:
            raise NoEffect()
        return f'done {i}'
    for i in range(1, 6):
        try:
            gov.attempt(f'{root}:c{i}', work, i); outcome['ran'] += 1
        except NoEffect:
            outcome['ran'] += 1; outcome['no_effect'] += 1
        except BudgetExhausted:
            outcome['denied'] += 1
        except VerdictRefused as exc:                                  # v0.6: the run happened, the witness refused the verdict; the result rides the error
            outcome['verdict_refused'] += 1; outcome.setdefault('withheld', []).append(exc.result)
        except Exception as exc:
            outcome['other'] += 1; outcome.setdefault('errors', []).append(repr(exc)[:120])
    obs = admin.observe(root)
    log = admin.audit(root)
    labels = [d['op'][3] for d in log if d['op'][0] == 'RECONCILE']
    evidence = [e for i in range(1, 6) for e in admin.evidence_for(root, attempt_id(f'{root}:c{i}'))]     # Amendment 17: the identity as the governor makes it
    return {'root': root, **outcome, 'executions': len(ran), 'phases': sorted(a[2] for a in obs['attempts']), 'credit': obs['credit'],
            'reconcile_labels': labels, 'evidence_rows': len(evidence), 'evidence_derived': sorted(set(e['derived'] for e in evidence)),
            'lockstep': replay_lockstep(admin, root, 3, 1)[0], 'chain': admin.verify_chain(root)[0]}


def main():
    admin, local = Store(ADMIN_DSN), Store(LOCAL_DSN); svc = WitnessService(8796); svc.start(); t0 = time.time()
    try:
        w = RemoteWitness(svc.url)
        a_rows = [run_root(admin, local, w, f'e3a-{i}', GATE, True) for i in range(4)]
        stranger = GateSigner()
        b_rows = [run_root(admin, local, w, f'e3b-{i}', stranger, False) for i in range(2)]
    finally:
        svc.stop()
    a_ok = all(r['ran'] == 4 and r['no_effect'] == 1 and r['denied'] == 1 and r['other'] == 0 and r['credit'] == 1
               and r['phases'] == ['EFFECT', 'EFFECT', 'EFFECT', 'NO_EFFECT'] and r['reconcile_labels'] == ['AUTHORISED'] * 4
               and r['evidence_rows'] == 4 and r['evidence_derived'] == ['AUTHORISED'] and r['lockstep'] and r['chain'] for r in a_rows)
    b_ok = all(r['ran'] == 0 and r['verdict_refused'] == 3 and r['executions'] == 3 and r['withheld'] == ['done 1', 'done 2', 'done 3']   # v0.6
               and r['denied'] == 2 and r['other'] == 0 and r['credit'] == 0 and r['phases'] == ['CONSUMED'] * 3
               and r['reconcile_labels'] == ['NONE'] * 3 and r['evidence_derived'] == ['NONE'] and r['lockstep'] and r['chain'] for r in b_rows)
    out = {'seconds': round(time.time() - t0, 1), 'part_a': a_rows, 'part_b': b_rows, 'part_a_ok': a_ok, 'part_b_ok': b_ok, 'PASS': a_ok and b_ok}
    write_output('e3_lifecycle_evidence.json', out)
    print(json.dumps({k: v for k, v in out.items() if k not in ('part_a', 'part_b')}, indent=1))
    for r in a_rows + b_rows:
        print(r)
    print('E3 RESULT:', 'PASS' if out['PASS'] else 'FAIL'); raise SystemExit(0 if out['PASS'] else 1)


if __name__ == '__main__':
    main()
