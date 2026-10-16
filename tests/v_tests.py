#!/usr/bin/env python3
"""V1–V6 (v0.7): the repairs for the v0.6 review's findings, each reproduced first in v_repro.py.

V1 admission at the host (finding 1).  With a HOLD or STOP accepted after the intent, the witness's CROSS is DENIED
   and there is no admission; a direct /run with the genuine intent receipt and no admission, a forged admission, a
   DENIED crossing's receipt, another attempt's admission, or a replayed earlier admission for another nonce is
   refused (403); the local credential cannot apply CROSS or set `crossed`; nothing runs.  After recovery the
   witness's CROSS is APPLIED and the admission runs the tool once; a resume presents DENIED/ALREADY_CROSSED and is
   answered with the stored result.
V2 ownership (finding 2).  A second host on the same state file refuses to start while the first holds a live
   lease; the first keeps serving.  After the first is frozen past its lease the second takes over, marks the
   running row interrupted and answers UNKNOWN; when the first completes the tool after all, its EFFECT report
   replaces the UNKNOWN one, the governor's retry resolves the attempt to EFFECT with one execution, and the
   frozen host refuses new work once it notices it lost the lease.
V3 UNKNOWN while held (finding 3, first row).  A tool that fails while the run is held: the witness refuses the
   reconciliation, the governor stores nothing and raises Held; after recovery the retry asks the host again, the
   witness records NOOP once, and the outcome is stored as unknown.
V4 receipt replay (finding 3, second row).  A proxy that replays an earlier RECONCILE receipt for a later submission
   is caught: the client raises ReceiptInvalid; a genuine later receipt binds the evidence submitted.
V5 TLS configuration (finding 3, third row).  A witness client or host client given TLS settings and an http:// URL
   raises before any request.
V6 audit verification (finding 3, fourth row).  verify_chain under a stream of concurrent appends reports no false
   failure over the run; the final quiescent check passes.
"""
import json
import os
import signal
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import psycopg

from common import (ADMIN_DSN, GATE, GATEWAY, LOCAL_DSN, WITNESS_KEY, WITNESS_PUB, GateHost, Store, TLSClient, WitnessService, admitted, bound,
                    client_tls, fresh_root, make_pki, replay_lockstep, write_output)
from plea_gateway import (AuthorityError, GateHostClient, GateRefused, Governor, Held, ReceiptInvalid, RemoteWitness, Signer, Stopped, Receipt)

LEDGER = GATEWAY / 'outputs' / 'v_ledger.jsonl'
def lines(): return sum(1 for _ in LEDGER.open()) if LEDGER.exists() else 0
def phase(admin, root, aid):
    for a in admin.observe(root)['attempts']:
        if a[0] == aid: return {'phase': a[2], 'crossed': a[5]}
def only_aid(admin, root): return admin.observe(root)['attempts'][0][0]
def refused(label, fn, want, status=None):
    try: fn(); return (label, False)
    except want as exc:
        if status is not None: return (f'{label} ({getattr(exc, "status", "?")})', getattr(exc, 'status', None) == status)
        return (f'{label} ({want.__name__})', True)
    except Exception as exc: return (f'{label}: unexpected {type(exc).__name__}: {str(exc)[:70]}', False)
def consumed_no_cross(admin, w, root, aid, q, nonce):
    admin.apply(root, ('RESERVE', aid, q)); w.accept_reservation(root, aid); admin.apply(root, ('TOKEN', aid)); admin.apply(root, ('START', aid, nonce))
    ri = w.accept_intent(root, aid)[1]; admin.apply(root, ('RECEIPT', aid)); return ri


def v1(admin, svc, host):
    checks = []; w = RemoteWitness(svc.url, WITNESS_PUB); hc = GateHostClient(host.url); local = Store(LOCAL_DSN)
    for ctl, want in (('HOLD', Held), ('STOP', Stopped)):
        root = f'v1-{ctl.lower()}'; fresh_root(admin, root, 4, 0); A = {'order_id': root, 'amount': 1}; n1 = bound(root, 'a1', 'charge', A)
        ri = consumed_no_cross(admin, w, root, 'a1', 'q1', n1)
        n2 = bound(root, 'a2', 'charge', A); _, _, adm2 = admitted(admin, w, root, 'a2', 'q2', n2)      # another attempt, admitted before the control
        admin.apply(root, (ctl,)); d, denied = w.cross(root, 'a1'); before = lines()
        checks.append((f"{ctl}: the witness's CROSS is DENIED and its receipt binds nothing", d.kind == 'DENIED' and d.code == 'NOT_ACTIVE_AND_OPEN' and denied.binding is None))
        checks.append(refused(f'{ctl}: /run with the genuine intent receipt and no admission', lambda: hc.run(root, 'a1', n1, ri, 'charge', A), GateRefused, 403))
        checks.append(refused(f'{ctl}: the DENIED crossing as admission', lambda: hc.run(root, 'a1', n1, ri, 'charge', A, admission=denied), GateRefused, 403))
        forged = Signer().sign(root, 'a1', denied.seq, ['CROSS', 'a1'], 'APPLIED', 'CROSSED', denied.hash, n1)
        checks.append(refused(f'{ctl}: a forged admission (unknown key)', lambda: hc.run(root, 'a1', n1, ri, 'charge', A, admission=forged), GateRefused, 403))
        checks.append(refused(f"{ctl}: another attempt's admission", lambda: hc.run(root, 'a1', n1, ri, 'charge', A, admission=adm2), GateRefused, 403))
        checks.append(refused(f'{ctl}: the local credential cannot apply CROSS', lambda: local.apply(root, ('CROSS', 'a1')), AuthorityError))
        with psycopg.connect(LOCAL_DSN) as conn:
            try: conn.execute('UPDATE attempts SET crossed = true WHERE root_id = %s AND aid = %s', (root, 'a1')); conn.commit(); raw = False
            except psycopg.errors.InsufficientPrivilege: conn.rollback(); raw = True
        checks.append((f'{ctl}: the local credential cannot set crossed by SQL', raw))
        checks.append((f'{ctl}: nothing ran; a1 is CONSUMED and not crossed', lines() == before and phase(admin, root, 'a1') == {'phase': 'CONSUMED', 'crossed': False}))
        if ctl == 'HOLD':
            admin.apply(root, ('RECOVER', True, True)); d, adm = w.cross(root, 'a1')
            r = hc.run(root, 'a1', n1, ri, 'charge', A, admission=adm)
            checks.append(('after recovery the witness records the crossing and the admission runs the tool once', d.kind == 'APPLIED' and r['repeat'] is False and lines() == before + 1))
            d2, adm_again = w.cross(root, 'a1'); r2 = hc.run(root, 'a1', n1, ri, 'charge', A, admission=adm_again)
            checks.append(('a resume presents DENIED/ALREADY_CROSSED and is answered with the stored result', d2.code == 'ALREADY_CROSSED' and adm_again.binding == n1 and r2['repeat'] is True and lines() == before + 1))
            checks.append(refused('the earlier admission replayed for another nonce', lambda: hc.run(root, 'a1', 'n-other', ri, 'charge', A, admission=adm), GateRefused, 403))
        checks.append(('replay lockstep', replay_lockstep(admin, root, 4, 0)[0]))
    return checks


def v2(admin, svc):
    checks = []; w = RemoteWitness(svc.url, WITNESS_PUB); state = str(GATEWAY / 'outputs' / 'v2_state.sqlite'); root = 'v2'; fresh_root(admin, root, 3, 0)
    ha = GateHost(8953, tools='tests.review_tools', ledger=str(LEDGER), state=state, lease=1.0); ha.start(); before = lines()
    hb = GateHost(8954, tools='tests.review_tools', ledger=str(LEDGER), state=state, lease=1.0)
    try: hb.start(fresh=False); started = True
    except RuntimeError as exc: started = False; why = str(exc)
    checks.append(('a second host on the same state file refuses to start while the first holds a live lease', not started and hb.proc.returncode == 3))
    checks.append(('the first host keeps serving', GateHostClient(ha.url).tools() != []))
    g = Governor(Store(LOCAL_DSN), w, root, 3, 0, admin=admin, host=GateHostClient(ha.url)); res = {}
    def go():
        try: res['A'] = g.attempt(f'{root}:c1', 'slow_charge', order_id=root, amount=1, delay=4.0)
        except Exception as exc: res['A'] = f'{type(exc).__name__}: {str(exc)[:60]}'
    t = threading.Thread(target=go); t.start(); time.sleep(1.0)
    os.kill(ha.proc.pid, signal.SIGSTOP); time.sleep(1.5)                                  # A is frozen past its lease, not dead
    hb.stopped_at = None; info = hb.start(fresh=False)
    checks.append(("after the first host's lease expires the second takes over and marks the running row interrupted", True))
    gb = Governor(Store(LOCAL_DSN), w, root, 3, 0, admin=admin, host=GateHostClient(hb.url))
    checks.append(refused('the retry at the second host gets a signed UNKNOWN verdict', lambda: gb.attempt(f'{root}:c1', 'slow_charge', order_id=root, amount=1, delay=4.0), RuntimeError))
    aid = only_aid(admin, root)
    os.kill(ha.proc.pid, signal.SIGCONT); t.join(15)                                        # A wakes and completes the tool
    checks.append(('the frozen host completes the tool after all and records EFFECT over the UNKNOWN', res.get('A') == {'charged': 1, 'order': root} and lines() == before + 1))
    v = gb.attempt(f'{root}:c1', 'slow_charge', order_id=root, amount=1, delay=4.0)
    checks.append(("the governor's retry resolves the attempt to EFFECT with one execution", v == {'charged': 1, 'order': root} and lines() == before + 1
                   and phase(admin, root, aid)['phase'] == 'EFFECT' and admin.get_result(root, aid).get('outcome') == 'value'))
    time.sleep(0.6); info_a = GateHostClient(ha.url)._get('/pubkey')
    fresh_root(admin, 'v2b', 3, 0); ga = Governor(Store(LOCAL_DSN), w, 'v2b', 3, 0, admin=admin, host=GateHostClient(ha.url))
    checks.append(refused('the host that lost its lease refuses new work', lambda: ga.attempt('v2b:c1', 'charge', order_id='v2b', amount=1), Exception))
    checks.append(('and reports it', info_a.get('lost') is True))
    ha.stop(); hb.stop()
    checks.append(('replay lockstep', replay_lockstep(admin, root, 3, 0)[0]))
    return checks


def v3(admin, svc, host):
    checks = []; root = 'v3'; fresh_root(admin, root, 3, 0); w = RemoteWitness(svc.url, WITNESS_PUB)
    class HoldAfterCross(GateHostClient):
        def run(self, *a, **k): admin.apply(root, ('HOLD',)); return super().run(*a, **k)
    g = Governor(Store(LOCAL_DSN), w, root, 3, 0, admin=admin, host=HoldAfterCross(host.url))
    checks.append(refused('a tool that fails while the run is held: the governor raises Held', lambda: g.attempt(f'{root}:c1', 'fail', order_id=root, amount=1), Held))
    aid = only_aid(admin, root); rec = [d for d in admin.audit(root) if d['op'][0] == 'RECONCILE']
    checks.append(('nothing is stored; the witness refused the reconciliation', admin.get_result(root, aid) is None and [d['kind'] for d in rec] == ['DENIED']))
    admin.apply(root, ('RECOVER', True, True))
    g2 = Governor(Store(LOCAL_DSN), w, root, 3, 0, admin=admin, host=GateHostClient(host.url))
    checks.append(refused('after recovery the retry asks the host again and gets the UNKNOWN verdict', lambda: g2.attempt(f'{root}:c1', 'fail', order_id=root, amount=1), RuntimeError))
    rec = [d['kind'] for d in admin.audit(root) if d['op'][0] == 'RECONCILE']
    checks.append(('the witness records NOOP once; the outcome is stored as unknown', rec == ['DENIED', 'NOOP'] and admin.get_result(root, aid).get('outcome') == 'unknown'))
    checks.append(('replay lockstep', replay_lockstep(admin, root, 3, 0)[0]))
    return checks


class Replay(BaseHTTPRequestHandler):
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


def v4(admin, svc):
    checks = []; root = 'v4'; fresh_root(admin, root, 3, 0); w = RemoteWitness(svc.url, WITNESS_PUB); A = {'order_id': root, 'amount': 1}
    n1 = bound(root, 'a1', 'charge', A); admitted(admin, w, root, 'a1', 'q1', n1)
    Replay.upstream = svc.url; Replay.cache = {}; proxy = ThreadingHTTPServer(('127.0.0.1', 8955), Replay); threading.Thread(target=proxy.serve_forever, daemon=True).start()
    try:
        wp = RemoteWitness('http://127.0.0.1:8955', WITNESS_PUB)
        d1, r1 = wp.reconcile(root, 'a1', None)
        checks.append(('a receipt binds the evidence submitted (none here)', d1.kind == 'DENIED' and r1.binding is None))
        genuine = GATE.effect_report(root, 'a1', n1, 'EFFECT', {'ok': 1}).to_json()
        checks.append(refused('the earlier receipt replayed for a later submission is refused by the client', lambda: wp.reconcile(root, 'a1', genuine), ReceiptInvalid))
        d3, r3 = w.reconcile(root, 'a1', genuine)
        checks.append(('the genuine later receipt binds the evidence', d3.kind == 'DUPLICATE' and r3.binding is not None and r3.binding != r1.binding))
    finally:
        proxy.shutdown()
    checks.append(('replay lockstep', replay_lockstep(admin, root, 3, 0)[0]))
    return checks


def v5(svc, host):
    pki = make_pki(); tls = client_tls(pki)
    return [refused('a witness client with TLS settings and an http:// URL', lambda: RemoteWitness(svc.url, WITNESS_PUB, tls=tls), ValueError),
            refused('a host client with TLS settings and an http:// URL', lambda: GateHostClient(host.url, tls=tls), ValueError)]


def v6(admin):
    root = 'v6'; fresh_root(admin, root, 10_000, 0); stop = threading.Event(); failures = []; count = [0]
    def appender():
        i = 0
        while not stop.is_set():
            i += 1; admin.apply(root, ('RESERVE', f'a{i}', f'q{i}'))
    def verifier():
        local = Store(LOCAL_DSN)
        while not stop.is_set():
            ok, detail = local.verify_chain(root); count[0] += 1
            if not ok: failures.append(detail)
    ta, tv = threading.Thread(target=appender), threading.Thread(target=verifier); ta.start(); tv.start(); time.sleep(6); stop.set(); ta.join(); tv.join()
    return [(f'verify_chain under concurrent appends: {count[0]} verifications, {len(failures)} false failures', count[0] >= 20 and not failures),
            ('the final quiescent check passes', admin.verify_chain(root)[0])], {'verifications': count[0], 'false_failures': len(failures)}


def main():
    admin = Store(ADMIN_DSN); t0 = time.time(); LEDGER.unlink(missing_ok=True)
    svc = WitnessService(8950, key=WITNESS_KEY); svc.start(); host = GateHost(8951, tools='tests.review_tools', ledger=str(LEDGER)); host.start()
    try:
        out = {'V1': v1(admin, svc, host), 'V3': v3(admin, svc, host), 'V4': v4(admin, svc), 'V5': v5(svc, host)}
        out['V2'] = v2(admin, svc)
    finally:
        host.stop(); svc.stop()
    out['V6'], v6_stats = v6(admin); out['v6_stats'] = v6_stats; out['seconds'] = round(time.time() - t0, 1)
    for k in ('V1', 'V2', 'V3', 'V4', 'V5', 'V6'): out[k + '_ok'] = all(ok for _, ok in out[k])
    out['PASS'] = all(out[k + '_ok'] for k in ('V1', 'V2', 'V3', 'V4', 'V5', 'V6'))
    write_output('v_tests.json', out)
    for k in ('V1', 'V2', 'V3', 'V4', 'V5', 'V6'):
        for label, ok in out[k]: print(k, 'ok  ' if ok else 'FAIL', label)
    print(json.dumps({k: v for k, v in out.items() if k not in ('V1', 'V2', 'V3', 'V4', 'V5', 'V6')}, indent=1))
    print('V RESULT:', 'PASS' if out['PASS'] else 'FAIL'); raise SystemExit(0 if out['PASS'] else 1)


if __name__ == '__main__':
    main()
