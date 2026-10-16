#!/usr/bin/env python3
"""W2: the gate crosses only behind a receipt the witness signed, for this attempt, on this chain.

With the witness service running: a1 is taken to an accepted intent through the service, which returns a signed
receipt; gate_cross with that receipt applies RECEIPT and CROSS.  Then a2 is taken to an accepted intent, and
gate_cross is tried with each forgery below.  Every forgery must raise ReceiptInvalid, and a2 must still have
neither receipt nor crossing afterwards.  Finally a2's own receipt crosses.

Forgeries: signed by another key; a1's valid receipt replayed for a2; the attempt field edited; the seq edited;
the kind edited from DENIED to APPLIED on a receipt for a denied acceptance; a receipt for ACCEPT_RESERVATION used
as the intent receipt; the signature truncated; the hash edited; a receipt for the same attempt name on another
root's chain.
"""
import dataclasses
import json
import time

from common import ADMIN_DSN, LOCAL_DSN, Store, WitnessService, fresh_root, replay_lockstep, write_output
from plea_gateway import Governor, Receipt, ReceiptInvalid, RemoteWitness, Signer


def to_pending(admin, root, aid, q, n):
    for op in ((('RESERVE', aid, q)), ('ACCEPT_RESERVATION', aid), ('TOKEN', aid), ('START', aid, n)):
        d, _ = admin.apply(root, op); assert d.kind == 'APPLIED', (op, d)


def main():
    admin, local = Store(ADMIN_DSN), Store(LOCAL_DSN)
    svc = WitnessService(8791); info = svc.start(); t0 = time.time()
    try:
        w = RemoteWitness(svc.url)
        assert w.public_key == info['public_key']
        root = 'w2-root'; fresh_root(admin, root, 3, 0)
        gov = Governor(local, w, root, 3, 0, admin=admin)
        # a1: the honest path
        to_pending(admin, root, 'a1', 'q1', 'n1')
        d1, r1 = w.accept_intent(root, 'a1'); assert d1.kind == 'APPLIED'
        honest = gov.gate_cross('a1', r1)[0].kind              # v0.7: gate_cross returns (decision, admission receipt)
        # a2: accepted intent, then forgeries against the gate
        to_pending(admin, root, 'a2', 'q2', 'n2')
        d2, r2 = w.accept_intent(root, 'a2'); assert d2.kind == 'APPLIED'
        # a receipt for a denied acceptance (a2's intent accepted again is DUPLICATE; ACCEPT_RESERVATION on a3 unknown is DENIED)
        d_den, r_den = w.accept_reservation(root, 'a2')          # a2 is INTENT_PENDING -> CONSUMED now: DUPLICATE by 5.2/2
        other = Signer()
        other_root = 'w2-other'; fresh_root(admin, other_root, 3, 0); to_pending(admin, other_root, 'a2', 'q2', 'n2')
        _, r_other = w.accept_intent(other_root, 'a2')
        rep = dataclasses.replace
        forgeries = {
            'signed by another key': other.sign(root, 'a2', r2.seq, r2.op, r2.kind, r2.code, r2.hash),
            "a1's receipt replayed for a2": r1,
            'attempt field edited': rep(r2, aid='a9'),
            'seq edited': rep(r2, seq=r2.seq + 1),
            'kind edited on a non-APPLIED receipt': rep(r_den, kind='APPLIED', op=['ACCEPT_INTENT', 'a2']),
            'ACCEPT_RESERVATION receipt used as intent receipt': r_den,
            'signature truncated': rep(r2, signature=r2.signature[:-8]),
            'hash edited': rep(r2, hash='0' * 64),
            "another root's receipt, same attempt name": r_other,
        }
        results = []
        for name, forged in forgeries.items():
            try:
                gov.gate_cross('a2', forged); results.append({'forgery': name, 'rejected': False})
            except ReceiptInvalid as exc:
                results.append({'forgery': name, 'rejected': True, 'reason': str(exc)})
        a2 = [a for a in admin.observe(root)['attempts'] if a[0] == 'a2'][0]
        a2_untouched = a2[2] == 'CONSUMED' and a2[4] is False and a2[5] is False
        crossed = gov.gate_cross('a2', r2)[0].kind
        a2_after = [a for a in admin.observe(root)['attempts'] if a[0] == 'a2'][0]
        lock = replay_lockstep(admin, root, 3, 0)[0]
        out = {'seconds': round(time.time() - t0, 1), 'honest_cross': honest, 'forgeries': results,
               'forgeries_rejected': sum(r['rejected'] for r in results), 'forgeries_total': len(results),
               'a2_untouched_by_forgeries': a2_untouched, 'a2_cross_with_own_receipt': crossed,
               'a2_final': a2_after, 'lockstep': lock, 'chain': admin.verify_chain(root)[0],
               'PASS': honest == 'APPLIED' and all(r['rejected'] for r in results) and a2_untouched and crossed == 'APPLIED'
                       and a2_after[4] is True and a2_after[5] is True and lock}
    finally:
        svc.stop()
    write_output('w2_receipts.json', out)
    print(json.dumps(out, indent=1))
    print('W2 RESULT:', 'PASS' if out['PASS'] else 'FAIL'); raise SystemExit(0 if out['PASS'] else 1)


if __name__ == '__main__':
    main()
