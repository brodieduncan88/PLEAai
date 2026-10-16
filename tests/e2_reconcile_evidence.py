#!/usr/bin/env python3
"""E2 (G03, D8): a verdict is accepted only on a genuine effect report bound to this attempt and its nonce.

On a root with k = 8, m = 2 and eight consumed attempts a1..a8 under nonces n1..n8:
  a1  genuine EFFECT report bound to n1                  -> APPLIED EFFECT, label AUTHORISED
  a2  genuine NO_EFFECT report bound to n2               -> APPLIED NO_EFFECT, AUTHORISED; credit becomes 1
  a3  no evidence                                        -> DENIED, (UNKNOWN, NONE)
  a4  NO_EFFECT report signed by an unpinned key         -> DENIED, NONE: the forged NO_EFFECT_PROVED attack of part 1;
                                                            credit stays 1
  a5  genuine NO_EFFECT report bound to the wrong nonce  -> DENIED, WRONG_BINDING
  a6  genuine report for a1 used on a6                   -> DENIED, WRONG_BINDING
  a7  genuine EFFECT report with the claim edited to NO_EFFECT -> DENIED, NONE (the signature no longer verifies)
  a8  the caller sends ('RECONCILE', 'a8', 'NO_EFFECT', 'AUTHORISED') -> refused by the service (400), nothing applied
  a8  genuine UNKNOWN report bound to n8                 -> NOOP (5.9/6), a8 stays CONSUMED and charged
Then with m = 2 the only credit is the one genuine NO_EFFECT.  Replay lockstep and the chain hold.
"""
import dataclasses
import json
import time

from common import ADMIN_DSN, GATE, Store, WitnessService, fresh_root, replay_lockstep, write_output
from plea_gateway import GateSigner, RemoteWitness


def main():
    admin = Store(ADMIN_DSN); svc = WitnessService(8795); svc.start(); t0 = time.time(); rows = []
    try:
        w = RemoteWitness(svc.url)
        root = 'e2-root'; fresh_root(admin, root, 8, 2)
        for i in range(1, 9):
            for op in (('RESERVE', f'a{i}', f'q{i}'), ('ACCEPT_RESERVATION', f'a{i}'), ('TOKEN', f'a{i}'), ('START', f'a{i}', f'n{i}'), ('ACCEPT_INTENT', f'a{i}')):
                d, _ = admin.apply(root, op); assert d.kind == 'APPLIED', (op, d)
        stranger = GateSigner()
        genuine_a7 = GATE.effect_report(root, 'a7', 'n7', 'EFFECT')
        cases = [
            ('a1', 'genuine EFFECT bound to n1', GATE.effect_report(root, 'a1', 'n1', 'EFFECT').to_json(), 'APPLIED', ('EFFECT', 'AUTHORISED')),
            ('a2', 'genuine NO_EFFECT bound to n2', GATE.effect_report(root, 'a2', 'n2', 'NO_EFFECT').to_json(), 'APPLIED', ('NO_EFFECT', 'AUTHORISED')),
            ('a3', 'no evidence', None, 'DENIED', ('UNKNOWN', 'NONE')),
            ('a4', 'forged NO_EFFECT by an unpinned key', stranger.effect_report(root, 'a4', 'n4', 'NO_EFFECT').to_json(), 'DENIED', ('UNKNOWN', 'NONE')),
            ('a5', 'genuine NO_EFFECT, wrong nonce', GATE.effect_report(root, 'a5', 'n9', 'NO_EFFECT').to_json(), 'DENIED', ('NO_EFFECT', 'WRONG_BINDING')),
            ('a6', "genuine report for a1 used on a6", GATE.effect_report(root, 'a1', 'n1', 'NO_EFFECT').to_json(), 'DENIED', ('NO_EFFECT', 'WRONG_BINDING')),
            ('a7', 'claim edited on a genuine report', dataclasses.replace(genuine_a7, claim='NO_EFFECT').to_json(), 'DENIED', ('UNKNOWN', 'NONE')),
        ]
        credit_after = {}
        for aid, name, ev, want_kind, want in cases:
            d, receipt = w.reconcile(root, aid, ev)
            applied = receipt.op; credit_after[aid] = admin.observe(root)['credit']
            rows.append({'case': name, 'aid': aid, 'kind': d.kind, 'verdict_label': applied[2:], 'credit_after': credit_after[aid],
                         'ok': d.kind == want_kind and tuple(applied[2:]) == want and applied[:2] == ['RECONCILE', aid]})
        pre = admin.observe(root)
        try:
            w.accept(root, ('RECONCILE', 'a8', 'NO_EFFECT', 'AUTHORISED')); refused = False
        except ValueError:
            refused = True
        rows.append({'case': 'label supplied by the caller', 'aid': 'a8', 'refused': refused, 'unchanged': admin.observe(root) == pre,
                     'ok': refused and admin.observe(root) == pre})
        d, receipt = w.reconcile(root, 'a8', GATE.effect_report(root, 'a8', 'n8', 'UNKNOWN').to_json())
        a8 = [a for a in admin.observe(root)['attempts'] if a[0] == 'a8'][0]
        rows.append({'case': 'genuine UNKNOWN bound to n8', 'aid': 'a8', 'kind': d.kind, 'phase': a8[2],
                     'ok': d.kind == 'NOOP' and tuple(receipt.op[2:]) == ('UNKNOWN', 'AUTHORISED') and a8[2] == 'CONSUMED'})
        obs = admin.observe(root); phases = {a[0]: a[2] for a in obs['attempts']}
        out = {'seconds': round(time.time() - t0, 1), 'cases': rows, 'phases': phases, 'credit': obs['credit'], 'N': obs['live'][2],
               'credit_after_forgery_a4': credit_after['a4'],
               'lockstep': replay_lockstep(admin, root, 8, 2)[0], 'chain': admin.verify_chain(root)[0]}
        out['PASS'] = (all(r['ok'] for r in rows) and phases['a1'] == 'EFFECT' and phases['a2'] == 'NO_EFFECT'
                       and all(phases[f'a{i}'] == 'CONSUMED' for i in range(3, 9)) and obs['credit'] == 1 and obs['live'][2] == 1
                       and credit_after['a4'] == 1 and out['lockstep'] and out['chain'])
    finally:
        svc.stop()
    write_output('e2_reconcile_evidence.json', out)
    print(json.dumps({k: v for k, v in out.items() if k != 'cases'}, indent=1))
    for r in rows:
        print(('ok   ' if r['ok'] else 'FAIL '), r)
    print('E2 RESULT:', 'PASS' if out['PASS'] else 'FAIL'); raise SystemExit(0 if out['PASS'] else 1)


if __name__ == '__main__':
    main()
