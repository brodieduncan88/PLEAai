#!/usr/bin/env python3
"""Reproduction of the v0.6 review's findings against the unchanged v0.6 code, before any repair.  Not a declared test."""
import json
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from common import (ADMIN_DSN, GATE, GATEWAY, LOCAL_DSN, WITNESS_KEY, WITNESS_PUB, GateHost, Store, TLSClient, WitnessService, bound, fresh_root,
                    make_pki, client_tls, write_output)
from plea_gateway import GateHostClient, GateRefused, Governor, Held, RemoteWitness

LEDGER = GATEWAY / 'outputs' / 'v_ledger.jsonl'
def lines(): return sum(1 for _ in LEDGER.open()) if LEDGER.exists() else 0
def phase(admin, root, aid):
    for a in admin.observe(root)['attempts']:
        if a[0] == aid: return {'phase': a[2], 'crossed': a[5]}
def only_aid(admin, root): return admin.observe(root)['attempts'][0][0]
def consumed(admin, w, root, aid, q, nonce):
    admin.apply(root, ('RESERVE', aid, q)); w.accept_reservation(root, aid); admin.apply(root, ('TOKEN', aid)); admin.apply(root, ('START', aid, nonce))
    return w.accept_intent(root, aid)[1]


class Replay(BaseHTTPRequestHandler):
    """Forwards every request, but answers a repeated (root, aid, op) with the first response it saw."""
    upstream = None; cache = {}
    def log_message(self, *a): pass
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', '0'))); req = json.loads(body); key = (req['root'], req['op'][1], req['op'][0])
        with urllib.request.urlopen(urllib.request.Request(self.upstream + self.path, data=body, headers={'Content-Type': 'application/json'}, method='POST'), timeout=10) as r:
            fresh = r.read()
        out = Replay.cache.setdefault(key, fresh)
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(out))); self.end_headers(); self.wfile.write(out)
    def do_GET(self):
        with urllib.request.urlopen(self.upstream + self.path, timeout=10) as r: out = r.read()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(out))); self.end_headers(); self.wfile.write(out)


def main():
    admin = Store(ADMIN_DSN); LEDGER.unlink(missing_ok=True); out = {}
    svc = WitnessService(8940, key=WITNESS_KEY); svc.start(); w = RemoteWitness(svc.url, WITNESS_PUB)
    host = GateHost(8941, tools='tests.review_tools', ledger=str(LEDGER)); host.start(); hc = GateHostClient(host.url)
    try:
        # 1. the host runs on a genuine intent receipt although CROSS was denied
        for ctl in ('HOLD', 'STOP'):
            root = f'v1-{ctl.lower()}'; fresh_root(admin, root, 3, 0); A = {'order_id': root, 'amount': 1}; n = bound(root, 'a1', 'charge', A)
            ri = consumed(admin, w, root, 'a1', 'q1', n); admin.apply(root, ('RECEIPT', 'a1'))
            d_ctl, _ = admin.apply(root, (ctl,)); d_cross, _ = admin.apply(root, ('CROSS', 'a1')); before = lines()
            try: r = hc.run(root, 'a1', n, ri, 'charge', A); host_said = 'ran' if not r['repeat'] else 'repeat'
            except GateRefused as exc: host_said = f'refused {exc.status}'
            out[f'F1_{ctl}'] = {'control': d_ctl.kind, 'cross': [d_cross.kind, d_cross.code], 'direct_run_at_host': host_said, 'tool_ran': lines() - before}
        # 3a. an UNKNOWN verdict is cached although the witness refused its reconciliation (held)
        root = 'v3a'; fresh_root(admin, root, 3, 0)
        class HoldAfterCross(GateHostClient):
            def run(self, *a, **k): admin.apply(root, ('HOLD',)); return super().run(*a, **k)
        g = Governor(Store(LOCAL_DSN), w, root, 3, 0, admin=admin, host=HoldAfterCross(host.url))
        try: g.attempt(f'{root}:c1', 'fail', order_id=root, amount=1); err = None
        except Exception as exc: err = type(exc).__name__
        aid = only_aid(admin, root); rec = [[d['kind'], d['code']] for d in admin.audit(root) if d['op'][0] == 'RECONCILE']
        out['F3a_unknown_cached_while_held'] = {'error': err, 'stored_outcome': admin.get_result(root, aid), 'reconcile_decisions': rec, 'witness': admin.observe(root)['witness']}
        # 3b. a replayed older receipt is accepted for a later submission
        root = 'v3b'; fresh_root(admin, root, 3, 0); A = {'order_id': root, 'amount': 1}; n = bound(root, 'a1', 'charge', A); ri = consumed(admin, w, root, 'a1', 'q1', n)
        Replay.upstream = svc.url; Replay.cache = {}; proxy = ThreadingHTTPServer(('127.0.0.1', 8942), Replay); threading.Thread(target=proxy.serve_forever, daemon=True).start()
        try:
            wp = RemoteWitness('http://127.0.0.1:8942', WITNESS_PUB)
            d1, r1 = wp.reconcile(root, 'a1', None)                                      # no evidence: DENIED NONE, now cached by the proxy
            genuine = GATE.effect_report(root, 'a1', n, 'EFFECT', {'ok': 1}).to_json()
            d2, r2 = wp.reconcile(root, 'a1', genuine)                                   # the witness applies EFFECT; the proxy replays the first receipt
        finally:
            proxy.shutdown()
        out['F3b_replayed_receipt'] = {'first': [d1.kind, r1.op[3]], 'second_client_saw': [d2.kind, r2.op[3], 'same receipt' if r2 == r1 else 'different'],
                                       'store_phase': phase(admin, root, 'a1')['phase']}
        # 3c. a client with TLS settings accepts an http:// URL
        pki = make_pki(); tls = client_tls(pki)
        try: RemoteWitness(svc.url, WITNESS_PUB, tls=tls).accept_reservation('v3b', 'a2') if False else None; wt = RemoteWitness(svc.url, WITNESS_PUB, tls=tls); out['F3c_http_with_tls'] = {'constructed': True, 'url': wt.url, 'error': None}
        except Exception as exc: out['F3c_http_with_tls'] = {'constructed': False, 'error': f'{type(exc).__name__}: {exc}'}
        try: GateHostClient(host.url, tls=tls); out['F3c_http_with_tls']['host_client_constructed'] = True
        except Exception as exc: out['F3c_http_with_tls']['host_client_constructed'] = f'{type(exc).__name__}'
        # 3d. verify_chain under a concurrent append
        root = 'v3d'; fresh_root(admin, root, 10_000, 0); stop = threading.Event(); false_failures = []; checks = [0]
        def appender():
            i = 0
            while not stop.is_set():
                i += 1; admin.apply(root, ('RESERVE', f'a{i}', f'q{i}'))
        def verifier():
            local = Store(LOCAL_DSN)
            while not stop.is_set():
                ok, detail = local.verify_chain(root); checks[0] += 1
                if not ok: false_failures.append(detail)
        ta, tv = threading.Thread(target=appender), threading.Thread(target=verifier); ta.start(); tv.start(); time.sleep(6); stop.set(); ta.join(); tv.join()
        final_ok, _ = admin.verify_chain(root)
        out['F3d_verify_chain_race'] = {'verifications': checks[0], 'false_failures': len(false_failures), 'examples': sorted(set(false_failures))[:3], 'final_quiescent_check': final_ok}
    finally:
        host.stop(); svc.stop()
    # 2. two hosts, one key, one state file: the second start marks the first's running action interrupted
    svc = WitnessService(8940, key=WITNESS_KEY); svc.start(); w = RemoteWitness(svc.url, WITNESS_PUB)
    state = str(GATEWAY / 'outputs' / 'v2_shared_state.sqlite')
    ha = GateHost(8943, tools='tests.review_tools', ledger=str(LEDGER), state=state); ha.start()
    root = 'v2'; fresh_root(admin, root, 3, 0); g = Governor(Store(LOCAL_DSN), w, root, 3, 0, admin=admin, host=GateHostClient(ha.url)); res = {}
    before = lines()
    def go():
        try: res['A_governor'] = g.attempt(f'{root}:c1', 'slow_charge', order_id=root, amount=1, delay=4.0)
        except Exception as exc: res['A_governor'] = f'{type(exc).__name__}: {str(exc)[:80]}'
    t = threading.Thread(target=go); t.start(); time.sleep(1.0)
    hb = GateHost(8944, tools='tests.review_tools', ledger=str(LEDGER), state=state); info = hb.start(fresh=False)
    gb = Governor(Store(LOCAL_DSN), w, root, 3, 0, admin=admin, host=GateHostClient(hb.url))
    try: res['B_governor'] = gb.attempt(f'{root}:c1', 'slow_charge', order_id=root, amount=1, delay=4.0)
    except Exception as exc: res['B_governor'] = f'{type(exc).__name__}: {str(exc)[:80]}'
    t.join(15); aid = only_aid(admin, root)
    try: res['replay_after_A_finished'] = gb.attempt(f'{root}:c1', 'slow_charge', order_id=root, amount=1, delay=4.0)
    except Exception as exc: res['replay_after_A_finished'] = f'{type(exc).__name__}: {str(exc)[:80]}'
    import sqlite3; row = sqlite3.connect(state).execute('SELECT status, report FROM crossings WHERE root = ?', (root,)).fetchone()
    out['F2_two_hosts_one_state'] = {'B_start_marked_interrupted': info.get('interrupted'), **res, 'tool_ran': lines() - before,
                                      'host_row_status_after': row[0], 'host_report_claim_after': json.loads(row[1])['claim'] if row[1] else None,
                                      'stored_outcome': admin.get_result(root, aid), 'phase': phase(admin, root, aid)}
    ha.stop(); hb.stop(); svc.stop()
    write_output('review2_repro_v0_6.json', out); print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
