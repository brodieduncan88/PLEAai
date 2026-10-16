#!/usr/bin/env python3
"""W4: the witness service dies mid-acceptance; the acceptance is retried after restart; nothing is lost or doubled.

For each of three acceptances (ACCEPT_RESERVATION, ACCEPT_INTENT, RECONCILE) and each of the six crash points: a
root is prepared so the acceptance would be APPLIED; the service is started in chaos mode with a fixed key; the
acceptance is sent with the crash header; the service dies (exit 137) and the client sees WitnessUnavailable.
Then: the state equals the pre-state for the five in-transaction points and the post-state after commit; the
service is restarted with the same key; the same acceptance is retried and is APPLIED (if the crash was before
commit) or DUPLICATE (if after); the receipt from the retry verifies; for the intent case gate_cross then applies
RECEIPT and CROSS behind it; replay lockstep and the chain hold.
"""
import json
import time

from common import ADMIN_DSN, GATE, LOCAL_DSN, Store, WitnessService, fresh_root, replay_lockstep, write_output
from plea_gateway import Governor, RemoteWitness, Signer, WitnessUnavailable
from plea_gateway.faults import CRASH_POINTS

tokened = [('RESERVE', 'a1', 'q1'), ('ACCEPT_RESERVATION', 'a1'), ('TOKEN', 'a1')]
pending = tokened + [('START', 'a1', 'n1')]
consumed = pending + [('ACCEPT_INTENT', 'a1')]
# (name, setup, the labelled op for the twin's expected post-state, the op sent to the service, evidence for it)
CASES = [('ACCEPT_RESERVATION', [('RESERVE', 'a1', 'q1')], ('ACCEPT_RESERVATION', 'a1'), ('ACCEPT_RESERVATION', 'a1'), None),
         ('ACCEPT_INTENT', pending, ('ACCEPT_INTENT', 'a1'), ('ACCEPT_INTENT', 'a1'), None),
         ('RECONCILE', consumed, ('RECONCILE', 'a1', 'NO_EFFECT', 'AUTHORISED'), ('RECONCILE', 'a1'), 'effect')]


def prepare(admin, root, setup):
    fresh_root(admin, root, 2, 1)
    for op in setup:
        d, _ = admin.apply(root, op); assert d.kind == 'APPLIED', (root, op, d)


def main():
    admin, local = Store(ADMIN_DSN), Store(LOCAL_DSN)
    key = Signer().private_hex; rows, failures, t0 = [], [], time.time()
    for name, setup, labelled, op, ev_kind in CASES:
        twin = f'w4-twin-{name}'; prepare(admin, twin, setup); d, post = admin.apply(twin, labelled); assert d.kind == 'APPLIED'
        for point in CRASH_POINTS:
            root = f'w4-{name}-{point}'; prepare(admin, root, setup); pre = admin.observe(root)
            svc = WitnessService(8793, key=key, chaos=True); info = svc.start(); pub = info['public_key']
            w = RemoteWitness(svc.url, pub)
            row = {'op': name, 'point': point}
            ev = GATE.effect_report(root, 'a1', 'n1', 'NO_EFFECT').to_json() if ev_kind == 'effect' else None
            try:
                w.accept(root, op, evidence=ev, crash_at=point); row['client_saw'] = 'response'
            except WitnessUnavailable as exc:
                row['client_saw'] = 'unavailable'
            row['service_exit'] = svc.wait_dead(10)
            obs = admin.observe(root)
            row['state_as_expected'] = obs == (post if point == 'after_commit' else pre)
            svc2 = WitnessService(8793, key=key, chaos=False); svc2.start()
            try:
                w2 = RemoteWitness(svc2.url, pub)
                d2, receipt = w2.accept(root, op, evidence=ev)
                row['retry_kind'] = d2.kind
                row['retry_as_expected'] = d2.kind == ('DUPLICATE' if point == 'after_commit' else 'APPLIED')
                row['receipt_ok'] = True
                if name == 'ACCEPT_INTENT':
                    gov = Governor(local, w2, root, 2, 1, admin=admin, gate=GATE)
                    gov.store.put_receipt(root, 'a1', receipt.seq, receipt.to_json())
                    row['gate_cross'] = gov.gate_cross('a1', receipt)[0].kind
                row['state_after_retry'] = admin.observe(root) == post or name == 'ACCEPT_INTENT'
            except Exception as exc:
                row['retry_error'] = repr(exc)[:160]; row['retry_as_expected'] = False; row['receipt_ok'] = False
            finally:
                svc2.stop()
            row['lockstep'] = replay_lockstep(admin, root, 2, 1)[0]; row['chain'] = admin.verify_chain(root)[0]
            row['ok'] = (row['client_saw'] == 'unavailable' and row['service_exit'] == 137 and row['state_as_expected']
                         and row.get('retry_as_expected') and row.get('receipt_ok') and row['lockstep'] and row['chain']
                         and (name != 'ACCEPT_INTENT' or row.get('gate_cross') == 'APPLIED'))
            rows.append(row); failures += [] if row['ok'] else [row]
    out = {'seconds': round(time.time() - t0, 1), 'kills': len(rows), 'ok': sum(r['ok'] for r in rows),
           'by_point': {p: sum(r['ok'] for r in rows if r['point'] == p) for p in CRASH_POINTS},
           'retries_applied': sum(r.get('retry_kind') == 'APPLIED' for r in rows), 'retries_duplicate': sum(r.get('retry_kind') == 'DUPLICATE' for r in rows),
           'rows': rows, 'failures': failures, 'PASS': not failures}
    write_output('w4_service_crash.json', out)
    print(json.dumps({k: v for k, v in out.items() if k not in ('rows', 'failures')}, indent=1))
    for f in failures[:5]: print('FAIL', f)
    print('W4 RESULT:', 'PASS' if out['PASS'] else 'FAIL'); raise SystemExit(0 if out['PASS'] else 1)


if __name__ == '__main__':
    main()
