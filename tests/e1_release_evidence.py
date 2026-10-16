#!/usr/bin/env python3
"""E1 (G03): a release is accepted only on a genuine fence report bound to this attempt; labels cannot be supplied.

With the witness service pinning the test gate key, on a root with eight accepted reservations:
  a1  a genuine fence report for a1                     -> APPLIED, the applied op carries BOUND_FENCE
  a2  no evidence                                        -> DENIED, label NONE
  a3  a fence report signed by a key the service does not pin -> DENIED, NONE
  a4  a genuine fence report for a9 (another attempt)    -> DENIED, WRONG_BINDING
  a5  a genuine fence report for a5 on another root      -> DENIED, WRONG_BINDING
  a6  a genuine report with its claim edited             -> DENIED, NONE (the signature no longer verifies)
  a7  a genuine report whose claim is STARTED            -> DENIED, NONE (a start is not release evidence)
  a8  the caller sends ('RELEASE', 'a8', 'BOUND_FENCE')  -> refused by the service (400), nothing applied
  a1  a1's genuine report again, after its release       -> DUPLICATE (5.8/2)
The same derivations are checked through the in-process witness.  Replay lockstep and the chain hold.
"""
import dataclasses
import json
import time

from common import ADMIN_DSN, GATE, LOCAL_DSN, WITNESS_DSN, Store, WitnessService, fresh_root, replay_lockstep, write_output
from plea_gateway import GateSigner, RemoteWitness, Witness


def main():
    admin = Store(ADMIN_DSN); svc = WitnessService(8794); svc.start(); t0 = time.time(); rows = []
    try:
        w = RemoteWitness(svc.url)
        root, other_root = 'e1-root', 'e1-other'
        for r in (root, other_root):
            fresh_root(admin, r, 8, 0)
            for i in range(1, 9):
                for op in (('RESERVE', f'a{i}', f'q{i}'), ('ACCEPT_RESERVATION', f'a{i}')):
                    d, _ = admin.apply(r, op); assert d.kind == 'APPLIED', (r, op, d)
        stranger = GateSigner()
        genuine_a6 = GATE.fence_report(root, 'a6')
        cases = [
            ('a1', 'genuine report for a1', GATE.fence_report(root, 'a1').to_json(), 'APPLIED', 'BOUND_FENCE'),
            ('a2', 'no evidence', None, 'DENIED', 'NONE'),
            ('a3', 'signed by an unpinned key', stranger.fence_report(root, 'a3').to_json(), 'DENIED', 'NONE'),
            ('a4', 'genuine report for another attempt', GATE.fence_report(root, 'a9').to_json(), 'DENIED', 'WRONG_BINDING'),
            ('a5', 'genuine report for another root', GATE.fence_report(other_root, 'a5').to_json(), 'DENIED', 'WRONG_BINDING'),
            ('a6', 'claim edited on a genuine report', dataclasses.replace(genuine_a6, claim='FENCED').to_json(), 'DENIED', 'NONE'),
            ('a7', 'genuine report claiming STARTED', GATE._sign('FENCE_REPORT', root, 'a7', None, 'STARTED').to_json(), 'DENIED', 'NONE'),
        ]
        for aid, name, ev, want_kind, want_label in cases:
            d, receipt = w.release(root, aid, ev)
            applied = receipt.op
            rows.append({'case': name, 'aid': aid, 'kind': d.kind, 'label': applied[2], 'want': (want_kind, want_label),
                         'ok': d.kind == want_kind and applied[2] == want_label and applied[:2] == ['RELEASE', aid]})
        # a supplied label is refused by the service
        pre = admin.observe(root)
        try:
            w.accept(root, ('RELEASE', 'a8', 'BOUND_FENCE')); refused = False
        except ValueError:
            refused = True
        rows.append({'case': 'label supplied by the caller', 'aid': 'a8', 'refused': refused, 'unchanged': admin.observe(root) == pre,
                     'ok': refused and admin.observe(root) == pre})
        d, receipt = w.release(root, 'a1', GATE.fence_report(root, 'a1').to_json())
        rows.append({'case': "a1's genuine report again after release", 'aid': 'a1', 'kind': d.kind, 'ok': d.kind == 'DUPLICATE'})
        # the in-process witness derives the same labels
        wi = Witness(Store(WITNESS_DSN), gate_keys=(GATE.public_hex,))
        root2 = 'e1-inproc'; fresh_root(admin, root2, 4, 0)
        for i in range(1, 5):
            for op in (('RESERVE', f'a{i}', f'q{i}'), ('ACCEPT_RESERVATION', f'a{i}')):
                admin.apply(root2, op)
        inproc = []
        for aid, ev, want in (('a1', GATE.fence_report(root2, 'a1').to_json(), ('APPLIED', 'BOUND_FENCE')),
                              ('a2', None, ('DENIED', 'NONE')),
                              ('a3', stranger.fence_report(root2, 'a3').to_json(), ('DENIED', 'NONE')),
                              ('a4', GATE.fence_report(root2, 'a1').to_json(), ('DENIED', 'WRONG_BINDING'))):
            d, rc = wi.release(root2, aid, ev); inproc.append({'aid': aid, 'kind': d.kind, 'label': rc.op[2], 'ok': (d.kind, rc.op[2]) == want})
        obs = admin.observe(root)
        phases = {a[0]: a[2] for a in obs['attempts']}
        evidence_rows = sum(len(admin.evidence_for(root, f'a{i}')) for i in range(1, 9))
        out = {'seconds': round(time.time() - t0, 1), 'service': rows, 'in_process': inproc,
               'a1_released_only': phases['a1'] == 'RELEASED' and all(phases[f'a{i}'] == 'RESERVED' for i in range(2, 9)),
               'live_R': obs['live'][0], 'evidence_rows_recorded': evidence_rows,
               'lockstep': replay_lockstep(admin, root, 8, 0)[0], 'chain': admin.verify_chain(root)[0]}
        out['PASS'] = all(r['ok'] for r in rows + inproc) and out['a1_released_only'] and out['live_R'] == 7 and out['lockstep'] and out['chain']
    finally:
        svc.stop()
    write_output('e1_release_evidence.json', out)
    print(json.dumps({k: v for k, v in out.items() if k not in ('service', 'in_process')}, indent=1))
    for r in rows + inproc:
        print(('ok   ' if r['ok'] else 'FAIL '), r)
    print('E1 RESULT:', 'PASS' if out['PASS'] else 'FAIL'); raise SystemExit(0 if out['PASS'] else 1)


if __name__ == '__main__':
    main()
