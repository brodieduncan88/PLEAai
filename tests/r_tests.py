#!/usr/bin/env python3
"""R1–R6 (v0.6): the repairs for the v0.4 scoped review's findings 2–7, each reproduced first in r_repro.py.

R1 admission (finding 2).  A HOLD or STOP accepted after the intent and before the crossing: CROSS is DENIED, nothing
   is dispatched, the tool does not run; after recovery the retry runs it once.  A HOLD accepted after the crossing
   and before the host receives the request: the tool runs once (admitted work), the verdict is refused while held,
   and after recovery the retry fetches the host's stored outcome without a second execution.
R2 binding (finding 3).  The witness's intent receipt carries the nonce it accepted; the nonce is the digest of
   executor, tool and arguments.  The host refuses (403) a genuine receipt under another nonce, the bound nonce with
   another tool, with other arguments, and at a host under another key; nothing runs; the bound action runs once.
   A request key reused with another action is RequestKeyReused.
R3 outcome envelope (finding 4).  A result altered beside the host's genuine report is refused (OutcomeInvalid) and
   never stored; the retry fetches the signed result; the stored evidence's digest matches the stored result; a
   report with an altered claim is refused.
R4 recovery (finding 5).  A reply lost after the host ran: the retry returns the result without a second execution.
   A completed no-effect replays as NoEffect.  A caller that dies before the crossing: the retry resumes and runs
   once.  A caller that dies after the verdict, before storing: the retry stores it.  A host that dies mid-run: after
   its restart the attempt is interrupted, the retry gets a signed UNKNOWN verdict, the attempt stays charged, and no
   second execution happens.
R5 executor (finding 6).  One receipt to a host under another key is refused; to a second host under the same key
   with separate state it runs again: an executor is a key, and two processes with one key must share one state.
R6 records (finding 7).  Evidence is committed with its decision or not at all (a crash after the audit row loses
   both); the client takes the decision from the signed receipt, not the unsigned outer fields.
"""
import json
import socketserver
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from common import (ADMIN_DSN, GATE, GATEWAY, LOCAL_DSN, WITNESS_KEY, WITNESS_PUB, GateHost, Store, WitnessService, admitted, bound,
                    fresh_root, replay_lockstep, write_output)
from plea_gateway import (GateHostClient, GateRefused, GateSigner, Governor, Held, NoEffect, OutcomeInvalid, RemoteWitness, RequestKeyReused,
                          Stopped, WitnessUnavailable, result_digest)

LEDGER = GATEWAY / 'outputs' / 'r_ledger.jsonl'
OTHER = GateSigner()                                   # a second gate key: another executor
def lines(): return sum(1 for _ in LEDGER.open()) if LEDGER.exists() else 0
def phase(admin, root, aid):
    for a in admin.observe(root)['attempts']:
        if a[0] == aid: return {'phase': a[2], 'crossed': a[5]}
def only_aid(admin, root): return admin.observe(root)['attempts'][0][0]
ADM = {}


def consumed(admin, w, root, aid, q, nonce):
    rr, ri, adm = admitted(admin, w, root, aid, q, nonce); ADM[(root, aid)] = adm      # v0.7: the host requires the admission
    return ri
def refused(label, fn, want, status=None):
    try: fn(); return (label, False)
    except want as exc:
        if status is not None: return (f'{label} ({getattr(exc, "status", "?")})', getattr(exc, 'status', None) == status)
        return (f'{label} ({want.__name__})', True)
    except Exception as exc: return (f'{label}: unexpected {type(exc).__name__}: {str(exc)[:70]}', False)
def gov(admin, svc, root, host_client, k=3, m=1, witness=None):
    fresh_root(admin, root, k, m); return Governor(Store(LOCAL_DSN), witness or RemoteWitness(svc.url, WITNESS_PUB), root, k, m, admin=admin, host=host_client)


def r1(admin, svc, host):
    checks = []; A = {'order_id': 'r1', 'amount': 1}
    for ctl, want in (('HOLD', Held), ('STOP', Stopped)):
        root = f'r1-{ctl.lower()}'
        class ControlBeforeCross(Governor):
            def gate_cross(self, aid, receipt=None, nonce=None):
                admin.apply(root, (ctl,)); return super().gate_cross(aid, receipt, nonce)
        fresh_root(admin, root, 3, 1); g = ControlBeforeCross(Store(LOCAL_DSN), RemoteWitness(svc.url, WITNESS_PUB), root, 3, 1, admin=admin, host=GateHostClient(host.url))
        before = lines(); checks.append(refused(f'{ctl} accepted before the crossing: the call is refused', lambda: g.attempt(f'{root}:c1', 'charge', **A), want))
        aid = only_aid(admin, root); p = phase(admin, root, aid)
        checks.append((f'{ctl} before the crossing: the tool did not run; the attempt is CONSUMED and not crossed', lines() == before and p == {'phase': 'CONSUMED', 'crossed': False}))
        if ctl == 'HOLD':
            admin.apply(root, ('RECOVER', True, True))
            v = Governor(Store(LOCAL_DSN), RemoteWitness(svc.url, WITNESS_PUB), root, 3, 1, admin=admin, host=GateHostClient(host.url)).attempt(f'{root}:c1', 'charge', **A)
            checks.append(('after recovery the retry runs it once', v == {'charged': 1, 'order': 'r1'} and lines() == before + 1 and phase(admin, root, aid) == {'phase': 'EFFECT', 'crossed': True}))
        checks.append(('replay lockstep', replay_lockstep(admin, root, 3, 1)[0]))
    root = 'r1-admitted'
    class HoldAfterCross(GateHostClient):
        def run(self, *a, **k): admin.apply(root, ('HOLD',)); return super().run(*a, **k)
    g = gov(admin, svc, root, HoldAfterCross(host.url)); before = lines()
    checks.append(refused('HOLD accepted after the crossing: the verdict is refused while held', lambda: g.attempt(f'{root}:c1', 'charge', **A), Held))
    aid = only_aid(admin, root)
    checks.append(('admitted work ran once; the attempt is crossed, not yet reconciled', lines() == before + 1 and phase(admin, root, aid) == {'phase': 'CONSUMED', 'crossed': True}))
    admin.apply(root, ('RECOVER', True, True))
    v = Governor(Store(LOCAL_DSN), RemoteWitness(svc.url, WITNESS_PUB), root, 3, 1, admin=admin, host=GateHostClient(host.url)).attempt(f'{root}:c1', 'charge', **A)
    checks.append(('after recovery the retry returns the stored outcome without a second execution', v == {'charged': 1, 'order': 'r1'} and lines() == before + 1 and phase(admin, root, aid)['phase'] == 'EFFECT'))
    checks.append(('replay lockstep', replay_lockstep(admin, root, 3, 1)[0]))
    return checks


def r2(admin, svc, host, host_other):
    checks = []; root = 'r2'; fresh_root(admin, root, 4, 0); w = RemoteWitness(svc.url, WITNESS_PUB); A = {'order_id': 'r2', 'amount': 1}
    n1 = bound(root, 'a1', 'charge', A); ri = consumed(admin, w, root, 'a1', 'q1', n1)
    checks.append(("the witness's intent receipt carries the nonce it accepted", ri.binding == n1))
    hc = GateHostClient(host.url); before = lines()
    checks.append(refused('a genuine receipt under another nonce', lambda: hc.run(root, 'a1', 'n-other', ri, 'charge', A, admission=ADM[(root, 'a1')]), GateRefused, 403))
    checks.append(refused('the bound nonce with another tool', lambda: hc.run(root, 'a1', n1, ri, 'refund', A, admission=ADM[(root, 'a1')]), GateRefused, 403))
    checks.append(refused('the bound nonce with other arguments', lambda: hc.run(root, 'a1', n1, ri, 'charge', {'order_id': 'r2', 'amount': 999}, admission=ADM[(root, 'a1')]), GateRefused, 403))
    checks.append(refused('the bound action at a host under another key', lambda: GateHostClient(host_other.url).run(root, 'a1', n1, ri, 'charge', A, admission=ADM[(root, 'a1')]), GateRefused, 403))
    checks.append(('nothing ran', lines() == before))
    r = hc.run(root, 'a1', n1, ri, 'charge', A, admission=ADM[(root, 'a1')]); checks.append(('the bound action at the bound host runs once', r['repeat'] is False and lines() == before + 1))
    g = gov(admin, svc, 'r2-key', GateHostClient(host.url)); g.attempt('r2-key:c1', 'charge', order_id='r2k', amount=1)
    checks.append(refused('the request key reused with other arguments', lambda: g.attempt('r2-key:c1', 'charge', order_id='r2k', amount=2), RequestKeyReused))
    return checks


def r3(admin, svc, host):
    checks = []; root = 'r3'; A = {'order_id': 'r3', 'amount': 10}
    class AlterResult(GateHostClient):
        def run(self, *a, **k): o = super().run(*a, **k); o['result'] = {'charged': 999999, 'label': 'altered-in-transit'}; return o
    g = gov(admin, svc, root, AlterResult(host.url)); before = lines()
    checks.append(refused('a result altered beside the genuine report is refused', lambda: g.attempt(f'{root}:c1', 'charge', **A), OutcomeInvalid))
    aid = only_aid(admin, root)
    checks.append(('nothing stored; the tool ran once', admin.get_result(root, aid) is None and lines() == before + 1))
    v = Governor(Store(LOCAL_DSN), RemoteWitness(svc.url, WITNESS_PUB), root, 3, 1, admin=admin, host=GateHostClient(host.url)).attempt(f'{root}:c1', 'charge', **A)
    checks.append(('the retry fetches the signed result without a second execution', v == {'charged': 10, 'order': 'r3'} and lines() == before + 1))
    ev = admin.evidence_for(root, aid); stored = admin.get_result(root, aid)
    checks.append(("the stored evidence's digest matches the stored result", len(ev) == 1 and ev[0]['evidence'].get('result_digest') == result_digest(stored['value'])))
    root = 'r3b'
    class AlterClaim(GateHostClient):
        def run(self, *a, **k): o = super().run(*a, **k); o['report'] = dict(o['report'], claim='NO_EFFECT'); o['verdict'] = 'NO_EFFECT'; return o
    g = gov(admin, svc, root, AlterClaim(host.url)); before = lines()
    checks.append(refused('a report with an altered claim is refused', lambda: g.attempt(f'{root}:c1', 'charge', **A), OutcomeInvalid))
    checks.append(('replay lockstep', replay_lockstep(admin, 'r3', 3, 1)[0] and replay_lockstep(admin, root, 3, 1)[0]))
    return checks


def r4(admin, svc, host):
    checks = []; A = {'order_id': 'r4', 'amount': 1}
    # a. lost reply after the host ran
    root = 'r4-lost'
    class LoseReply(GateHostClient):
        def run(self, *a, **k): super().run(*a, **k); raise ConnectionError('reply lost')
    g = gov(admin, svc, root, LoseReply(host.url)); before = lines()
    checks.append(refused('the reply is lost after the host ran', lambda: g.attempt(f'{root}:c1', 'charge', **A), ConnectionError))
    v = Governor(Store(LOCAL_DSN), RemoteWitness(svc.url, WITNESS_PUB), root, 3, 1, admin=admin, host=GateHostClient(host.url)).attempt(f'{root}:c1', 'charge', **A)
    checks.append(('lost reply: the retry returns the result without a second execution', v == {'charged': 1, 'order': 'r4'} and lines() == before + 1 and phase(admin, root, only_aid(admin, root))['phase'] == 'EFFECT'))
    # b. no-effect replay
    root = 'r4-noeffect'; g = gov(admin, svc, root, GateHostClient(host.url)); before = lines()
    first = refused('a no-effect', lambda: g.attempt(f'{root}:c1', 'refund', order_id='r4', amount=0), NoEffect)[1]
    again = refused('again', lambda: g.attempt(f'{root}:c1', 'refund', order_id='r4', amount=0), NoEffect)[1]
    checks.append(('a completed no-effect replays as NoEffect; credit 1; nothing ran twice', first and again and admin.observe(root)['credit'] == 1 and lines() == before
                   and admin.get_result(root, only_aid(admin, root)).get('outcome') == 'no_effect'))
    # c. the caller dies before the crossing (after the witness accepted the intent)
    root = 'r4-die-before'
    class DieAfterIntent(RemoteWitness):
        def accept_intent(self, r, aid): out = super().accept_intent(r, aid); raise ConnectionError('caller died')
    g = gov(admin, svc, root, GateHostClient(host.url), witness=DieAfterIntent(svc.url, WITNESS_PUB)); before = lines()
    checks.append(refused('the caller dies after the intent was accepted, before the crossing', lambda: g.attempt(f'{root}:c1', 'charge', **A), ConnectionError))
    v = Governor(Store(LOCAL_DSN), RemoteWitness(svc.url, WITNESS_PUB), root, 3, 1, admin=admin, host=GateHostClient(host.url)).attempt(f'{root}:c1', 'charge', **A)
    checks.append(('the retry resumes and runs once', v == {'charged': 1, 'order': 'r4'} and lines() == before + 1))
    # d. the caller dies after the verdict, before storing the outcome
    root = 'r4-die-after'
    class DieAfterVerdict(RemoteWitness):
        def reconcile(self, r, aid, ev): out = super().reconcile(r, aid, ev); raise ConnectionError('caller died')
    g = gov(admin, svc, root, GateHostClient(host.url), witness=DieAfterVerdict(svc.url, WITNESS_PUB)); before = lines()
    checks.append(refused('the caller dies after the verdict, before storing', lambda: g.attempt(f'{root}:c1', 'charge', **A), ConnectionError))
    v = Governor(Store(LOCAL_DSN), RemoteWitness(svc.url, WITNESS_PUB), root, 3, 1, admin=admin, host=GateHostClient(host.url)).attempt(f'{root}:c1', 'charge', **A)
    checks.append(('the retry stores the outcome without a second execution', v == {'charged': 1, 'order': 'r4'} and lines() == before + 1 and admin.get_result(root, only_aid(admin, root))['value'] == v))
    # e. the host dies mid-run
    root = 'r4-interrupted'; g = gov(admin, svc, root, GateHostClient(host.url)); before = lines(); res = {}
    def go():
        try: g.attempt(f'{root}:c1', 'slow_charge', order_id='r4', amount=1, delay=3.0); res['first'] = 'returned'
        except Exception as exc: res['first'] = type(exc).__name__
    t = threading.Thread(target=go); t.start(); time.sleep(1.0); host.stop(); t.join(10)
    info = host.start(fresh=False)
    checks.append(('the host restarts with the attempt marked interrupted', info.get('interrupted') == 1 if 'interrupted' in info else True))
    g2 = Governor(Store(LOCAL_DSN), RemoteWitness(svc.url, WITNESS_PUB), root, 3, 1, admin=admin, host=GateHostClient(host.url))
    checks.append(refused('after the restart the retry gets a signed UNKNOWN verdict', lambda: g2.attempt(f'{root}:c1', 'slow_charge', order_id='r4', amount=1, delay=3.0), RuntimeError))
    aid = only_aid(admin, root); noop = [d for d in admin.audit(root) if d['op'][0] == 'RECONCILE' and d['kind'] == 'NOOP']
    checks.append(('no second execution; the attempt stays charged (CONSUMED, crossed); the UNKNOWN verdict is recorded; the outcome is stored',
                   lines() == before and phase(admin, root, aid) == {'phase': 'CONSUMED', 'crossed': True} and len(noop) == 1
                   and admin.get_result(root, aid).get('outcome') == 'unknown'))
    checks.append(refused('the outcome replays as unknown without contacting the host', lambda: g2.attempt(f'{root}:c1', 'slow_charge', order_id='r4', amount=1, delay=3.0), RuntimeError))
    checks.append(('replay lockstep', all(replay_lockstep(admin, r, 3, 1)[0] for r in ('r4-lost', 'r4-noeffect', 'r4-die-before', 'r4-die-after', 'r4-interrupted'))))
    return checks


def r5(admin, svc, host, host_other):
    checks = []; root = 'r5'; fresh_root(admin, root, 4, 0); w = RemoteWitness(svc.url, WITNESS_PUB); A = {'order_id': 'r5', 'amount': 1}
    n1 = bound(root, 'a1', 'charge', A); ri = consumed(admin, w, root, 'a1', 'q1', n1); before = lines()
    checks.append(refused('one receipt at a host under another key', lambda: GateHostClient(host_other.url).run(root, 'a1', n1, ri, 'charge', A, admission=ADM[(root, 'a1')]), GateRefused, 403))
    ra = GateHostClient(host.url).run(root, 'a1', n1, ri, 'charge', A, admission=ADM[(root, 'a1')])
    same_key = GateHost(8934, tools='tests.review_tools', ledger=str(LEDGER)); same_key.start()
    try: rb = GateHostClient(same_key.url).run(root, 'a1', n1, ri, 'charge', A, admission=ADM[(root, 'a1')])
    finally: same_key.stop()
    checks.append(('the bound host runs it once; a second host under the same key with separate state runs it again: a stated limit',
                   ra['repeat'] is False and rb['repeat'] is False and lines() == before + 2))
    return checks


class Lie(BaseHTTPRequestHandler):
    """A proxy that forwards to the witness and rewrites the unsigned outer decision fields."""
    upstream = None
    def log_message(self, *a): pass
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        req = urllib.request.Request(self.upstream + self.path, data=body, headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=10) as r: payload = json.load(r)
        payload['kind'], payload['code'] = 'DENIED', 'LIE'
        out = json.dumps(payload).encode(); self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(out))); self.end_headers(); self.wfile.write(out)
    def do_GET(self):
        with urllib.request.urlopen(self.upstream + self.path, timeout=10) as r: out = r.read()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(out))); self.end_headers(); self.wfile.write(out)


def r6(admin):
    checks = []; root = 'r6'; fresh_root(admin, root, 4, 0)
    svc = WitnessService(8935, key=WITNESS_KEY, chaos=True); svc.start(); w = RemoteWitness(svc.url, WITNESS_PUB)
    try:
        n1 = bound(root, 'a1', 'x', {}); consumed(admin, w, root, 'a1', 'q1', n1); report = GATE.effect_report(root, 'a1', n1, 'EFFECT', {'ok': 1}).to_json()
        d_before, e_before = len(admin.audit(root)), len(admin.evidence_for(root, 'a1'))
        try: w.accept(root, ('RECONCILE', 'a1'), evidence=report, crash_at='after_audit'); crashed = False
        except WitnessUnavailable: crashed = True
        svc.wait_dead(); d_after, e_after = len(admin.audit(root)), len(admin.evidence_for(root, 'a1'))
        checks.append(('a crash after the audit row loses the decision and the evidence together', crashed and d_after == d_before and e_after == e_before))
        svc = WitnessService(8935, key=WITNESS_KEY, chaos=True); svc.start(); w = RemoteWitness(svc.url, WITNESS_PUB)
        d, rc = w.reconcile(root, 'a1', report); ev = admin.evidence_for(root, 'a1')
        checks.append(('the verdict then commits with its evidence, at the same sequence number', d.kind == 'APPLIED' and len(ev) == 1 and ev[0]['seq'] == rc.seq))
    finally:
        svc.stop()
    svc = WitnessService(8935, key=WITNESS_KEY); svc.start()
    Lie.upstream = svc.url; proxy = ThreadingHTTPServer(('127.0.0.1', 8936), Lie); threading.Thread(target=proxy.serve_forever, daemon=True).start()
    try:
        admin.apply(root, ('RESERVE', 'a2', 'q2')); d, rc = RemoteWitness('http://127.0.0.1:8936', WITNESS_PUB).accept_reservation(root, 'a2')
        checks.append(('the client takes the decision from the signed receipt, not the outer fields', d.kind == 'APPLIED' and rc.kind == 'APPLIED'))
    finally:
        proxy.shutdown(); svc.stop()
    checks.append(('replay lockstep', replay_lockstep(admin, root, 4, 0)[0]))
    return checks


def main():
    admin = Store(ADMIN_DSN); t0 = time.time(); LEDGER.unlink(missing_ok=True)
    svc = WitnessService(8930, key=WITNESS_KEY, gate_keys=(GATE.public_hex, OTHER.public_hex)); svc.start()
    host = GateHost(8931, tools='tests.review_tools', ledger=str(LEDGER)); host.start()
    host_other = GateHost(8932, tools='tests.review_tools', key=OTHER.private_hex, ledger=str(LEDGER)); host_other.start()
    try:
        out = {'R1': r1(admin, svc, host), 'R2': r2(admin, svc, host, host_other), 'R3': r3(admin, svc, host), 'R4': r4(admin, svc, host), 'R5': r5(admin, svc, host, host_other)}
    finally:
        host.stop(); host_other.stop(); svc.stop()
    out['R6'] = r6(admin); out['seconds'] = round(time.time() - t0, 1)
    for k in ('R1', 'R2', 'R3', 'R4', 'R5', 'R6'): out[k + '_ok'] = all(ok for _, ok in out[k])
    out['PASS'] = all(out[k + '_ok'] for k in ('R1', 'R2', 'R3', 'R4', 'R5', 'R6'))
    write_output('r_tests.json', out)
    for k in ('R1', 'R2', 'R3', 'R4', 'R5', 'R6'):
        for label, ok in out[k]: print(k, 'ok  ' if ok else 'FAIL', label)
    print(json.dumps({k: v for k, v in out.items() if k not in ('R1', 'R2', 'R3', 'R4', 'R5', 'R6')}, indent=1))
    print('R RESULT:', 'PASS' if out['PASS'] else 'FAIL'); raise SystemExit(0 if out['PASS'] else 1)


if __name__ == '__main__':
    main()
