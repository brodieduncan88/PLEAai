#!/usr/bin/env python3
"""Reproduction of the v0.4 scoped review's findings 2-6 against the current code, before any repair.  Not a declared
test: a record of what the reviewer's schedules do here, kept beside the repair's tests."""
import json
import threading
import time

from common import ADMIN_DSN, GATEWAY, LOCAL_DSN, WITNESS_KEY, WITNESS_PUB, GateHost, Store, WitnessService, fresh_root, write_output
from plea_gateway import GateHostClient, GateRefused, GateRefusedRun, Governor, GovernedError, InProgress, NoEffect, RemoteWitness

LEDGER = GATEWAY / 'outputs' / 'review_ledger.jsonl'
def lines(): return sum(1 for _ in LEDGER.open()) if LEDGER.exists() else 0
def consumed(admin, w, root, aid, q, n):
    admin.apply(root, ('RESERVE', aid, q)); w.accept_reservation(root, aid); admin.apply(root, ('TOKEN', aid)); admin.apply(root, ('START', aid, n))
    return w.accept_intent(root, aid)[1]
def attempt_of(admin, root, aid):
    for a in admin.observe(root)['attempts']:
        if a[0] == aid: return {'phase': a[2], 'nonce': a[3], 'receipt': a[4], 'crossed': a[5]}

def gov_for(admin, svc, root, hc, k=3, m=1):
    fresh_root(admin, root, k, m); return Governor(Store(LOCAL_DSN), RemoteWitness(svc.url, WITNESS_PUB), root, k, m, admin=admin, host=hc)

def main():
    admin = Store(ADMIN_DSN); LEDGER.unlink(missing_ok=True); out = {}
    svc = WitnessService(8920, key=WITNESS_KEY); svc.start(); host = GateHost(8921, tools='tests.review_tools', ledger=str(LEDGER)); host.start()
    w = RemoteWitness(svc.url, WITNESS_PUB)
    try:
        # finding 2: HOLD / STOP accepted after the intent, before dispatch
        for ctl in ('HOLD', 'STOP'):
            root = f'r2-{ctl.lower()}'
            class ControlThenRun(GateHostClient):
                def run(self, *a, **k):
                    d, _ = admin.apply(root, (ctl,)); self.control = d.kind; return super().run(*a, **k)
            hc = ControlThenRun(host.url); gov = gov_for(admin, svc, root, hc); before = lines(); err = None
            try: gov.attempt(f'{root}:c1', 'charge', order_id=root, amount=1)
            except Exception as exc: err = f'{type(exc).__name__}: {exc}'
            aid = [a[0] for a in admin.observe(root)['attempts']][0]
            try: gov.attempt(f'{root}:c1', 'charge', order_id=root, amount=1); retry = 'returned'
            except Exception as exc: retry = type(exc).__name__
            out[f'F2_{ctl}'] = {'control': hc.control, 'tool_ran': lines() - before, 'error': err, 'attempt': attempt_of(admin, root, aid), 'retry': retry}
        # finding 3: the receipt does not bind the nonce, the tool or the arguments
        root = 'r3'; fresh_root(admin, root, 3, 0); ri = consumed(admin, w, root, 'a1', 'q1', 'accepted-nonce'); hc = GateHostClient(host.url); before = lines()
        r = hc.run(root, 'a1', 'different-nonce', ri, 'refund', {'order_id': 'r3-not-the-intended-action', 'amount': 5})
        d, rc = w.reconcile(root, 'a1', r['report'])
        out['F3'] = {'tool_ran': lines() - before, 'report_nonce': r['report']['nonce'], 'verdict_signed': r['verdict'], 'witness': [d.kind, d.code, rc.op[3]]}
        # finding 4: the result is not authenticated
        root = 'r4'
        class AlterResult(GateHostClient):
            def run(self, *a, **k): o = super().run(*a, **k); o['result'] = {'charged': 999999, 'label': 'altered-in-transit'}; return o
        gov = gov_for(admin, svc, root, AlterResult(host.url)); v = gov.attempt(f'{root}:c1', 'charge', order_id=root, amount=10)
        aid = [a[0] for a in admin.observe(root)['attempts']][0]
        out['F4'] = {'governor_returned': v, 'stored': admin.get_result(root, aid), 'reconcile': [d['op'][2:] for d in admin.audit(root) if d['op'][0] == 'RECONCILE'],
                     'phase': attempt_of(admin, root, aid)['phase']}
        # finding 5a: the reply is lost after the host completed; the retry does not ask the host
        root = 'r5a'
        class LoseReply(GateHostClient):
            def run(self, *a, **k): super().run(*a, **k); raise ConnectionError('reply lost')
        gov = gov_for(admin, svc, root, LoseReply(host.url)); before = lines(); err = None
        try: gov.attempt(f'{root}:c1', 'charge', order_id=root, amount=1)
        except Exception as exc: err = type(exc).__name__
        aid = [a[0] for a in admin.observe(root)['attempts']][0]
        gov2 = Governor(Store(LOCAL_DSN), w, root, 3, 1, admin=admin, host=GateHostClient(host.url))
        try: gov2.attempt(f'{root}:c1', 'charge', order_id=root, amount=1); retry = 'returned'
        except Exception as exc: retry = type(exc).__name__
        out['F5a_lost_reply'] = {'tool_ran': lines() - before, 'error': err, 'retry_with_healthy_host': retry, 'attempt': attempt_of(admin, root, aid)}
        # finding 5b: a completed no-effect; the identical retry
        root = 'r5b'; gov = gov_for(admin, svc, root, GateHostClient(host.url)); first = None
        try: gov.attempt(f'{root}:c1', 'refund', order_id=root, amount=0)
        except Exception as exc: first = type(exc).__name__
        try: gov.attempt(f'{root}:c1', 'refund', order_id=root, amount=0); retry = 'returned'
        except Exception as exc: retry = type(exc).__name__
        out['F5b_no_effect_retry'] = {'first': first, 'retry': retry, 'credit': admin.observe(root)['credit']}
        # finding 5c: the host dies mid-run; after a restart the attempt is 'running' forever
        root = 'r5c'; gov = gov_for(admin, svc, root, GateHostClient(host.url)); before = lines(); res = {}
        def go():
            try: gov.attempt(f'{root}:c1', 'slow_charge', order_id=root, amount=1, delay=3.0); res['first'] = 'returned'
            except Exception as exc: res['first'] = type(exc).__name__
        t = threading.Thread(target=go); t.start(); time.sleep(1.0); host.stop(); t.join(10)
        host.start(fresh=False)                                                     # same key, same state
        try: gov.attempt(f'{root}:c1', 'slow_charge', order_id=root, amount=1, delay=0.1); retry = 'returned'
        except GateRefusedRun as exc: retry = f'GateRefusedRun: {str(exc)[:60]}'
        except Exception as exc: retry = type(exc).__name__
        out['F5c_host_crash'] = {'first': res.get('first'), 'tool_ran': lines() - before, 'retry_after_restart': retry}
        # finding 6: one receipt, two hosts with separate state
        host2 = GateHost(8922, tools='tests.review_tools', ledger=str(LEDGER)); host2.start()
        try:
            root = 'r6'; fresh_root(admin, root, 3, 0); ri = consumed(admin, w, root, 'a1', 'q1', 'n1'); before = lines()
            ra = GateHostClient(host.url).run(root, 'a1', 'n1', ri, 'charge', {'order_id': 'r6', 'amount': 1}); rb = GateHostClient(host2.url).run(root, 'a1', 'n1', ri, 'charge', {'order_id': 'r6', 'amount': 1})
            out['F6_two_hosts'] = {'host_a_repeat': ra['repeat'], 'host_b_repeat': rb['repeat'], 'tool_ran': lines() - before}
        finally:
            host2.stop()
    finally:
        host.stop(); svc.stop()
    write_output('review_repro_v0_5.json', out); print(json.dumps(out, indent=1))

if __name__ == '__main__':
    main()
