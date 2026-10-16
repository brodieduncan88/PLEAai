#!/usr/bin/env python3
"""H1–H5 (v0.4): the gate host holds the only gate key; the governor holds none.

H1 the host runs nothing without the witness's word.  /run with no receipt, a receipt signed by an unknown key,
   a reservation receipt where an intent receipt is required, and another attempt's genuine receipt are all
   refused, and the ledger stays empty; the genuine receipt then runs, so the refusals consumed nothing.
H2 one-shot at the host.  A genuine /run runs once; the same /run again, and one with a different nonce and
   arguments, are answered from the first result with "repeat" and the ledger does not grow; eight concurrent
   /run requests for one attempt produce exactly one execution; after a host restart the same /run is still a
   repeat (state is persisted).
H3 fence and run exclude each other.  An attempt fenced at the host cannot run there (409); an attempt that ran
   cannot be fenced (409); a fence report for a reservation that never started releases it at the witness
   (APPLIED BOUND_FENCE); a fence report for an attempt whose intent the witness had accepted is DENIED by the
   contract (5.8/4), so the host's fence cannot undo accepted consumption.
H4 the governor holds no gate key.  Four roots through the Python API in host mode (E3's schedule: 4 ran,
   1 NoEffect, 1 denied, credit 1), gov.gate is None, every verdict AUTHORISED, replay lockstep; then the MCP
   server in host mode: a retried charge runs once and a call beyond the budget is refused.
H5 rotation.  Witness: a receipt signed under the old key is accepted by a host pinning [old, new] and by one
   pinning only new is refused; a receipt under the new key is accepted.  Gate: the witness service pinning
   [old, new] accepts reports from either host key; pinning only new, the old host's report derives NONE.  v0.6: a
   host under another gate key refuses an attempt bound to the old one (the executor is bound); an attempt bound
   to the new host runs there.
"""
import dataclasses
import json
import os
import subprocess
import threading
import time

from common import (ADMIN_DSN, GATE, GATEWAY, LOCAL_DSN, PYTHON, WITNESS_KEY, WITNESS_PUB, GateHost, Store, WitnessService, admitted,
                    bound, fresh_root, replay_lockstep, write_output)
from plea_gateway import (BudgetExhausted, GateHostClient, GateRefused, GateSigner, Governor, NoEffect, Receipt, RemoteWitness,
                          Signer)

LEDGER = GATEWAY / 'outputs' / 'host_ledger.jsonl'      # the path GateHost gives the host explicitly (amendment 1)


def ledger_lines():
    return sum(1 for _ in LEDGER.open()) if LEDGER.exists() else 0


ADM = {}                                                 # v0.7: the admission receipt of each (root, aid) the manual lifecycle crossed


def consumed(admin, w, root, aid, q, n):
    """RESERVE, ACCEPT_RESERVATION (receipt kept), TOKEN, START, ACCEPT_INTENT (receipt kept), then (v0.7) RECEIPT and the
    witness's CROSS, whose receipt the host requires.  Returns the reservation and intent receipts; the admission is in ADM."""
    rr, ri, adm = admitted(admin, w, root, aid, q, n); ADM[(root, aid)] = adm
    return rr, ri


def run(hc, root, aid, nonce, receipt, tool, arguments):
    return hc.run(root, aid, nonce, receipt, tool, arguments, admission=ADM.get((root, aid)))


def h1(admin, w, hc):
    root = 'h1'; fresh_root(admin, root, 4, 0); checks = []
    A1 = {'order_id': 'h1', 'amount': 1}; n1 = bound(root, 'a1', 'charge', A1); n2 = bound(root, 'a2', 'charge', A1)   # v0.6: bound nonces
    rr1, ri1 = consumed(admin, w, root, 'a1', 'q1', n1); rr2, ri2 = consumed(admin, w, root, 'a2', 'q2', n2)
    before = ledger_lines()
    def refused(label, **payload):
        try:
            hc._post('/run', payload); checks.append((label, False))
        except GateRefused as exc:
            checks.append((label + f' ({exc.status})', exc.status in (400, 403)))
    base = {'root': root, 'aid': 'a1', 'nonce': n1, 'tool': 'charge', 'arguments': A1, 'admission': ADM[(root, 'a1')].to_json()}
    refused('no receipt', **{k: v for k, v in base.items()}, receipt={})
    refused('receipt signed by an unknown key', **base, receipt=Signer().sign(root, 'a1', ri1.seq, ri1.op, ri1.kind, ri1.code, ri1.hash).to_json())
    refused('reservation receipt where an intent receipt is required', **base, receipt=rr1.to_json())
    refused("another attempt's genuine intent receipt", **base, receipt=ri2.to_json())
    refused('kind edited on a copy of the genuine receipt', **base, receipt=dataclasses.replace(ri1, kind='DENIED').to_json())
    checks.append(('ledger unchanged by the refusals', ledger_lines() == before))
    out = run(hc, root, 'a1', n1, ri1, 'charge', A1)
    checks.append(('the genuine receipt then runs, once', out['repeat'] is False and out['verdict'] == 'EFFECT' and ledger_lines() == before + 1))
    return checks


def h2(admin, w, hc, host):
    root = 'h2'; fresh_root(admin, root, 4, 0); checks = []
    A1, A2 = {'order_id': 'h2-1', 'amount': 1}, {'order_id': 'h2-2', 'amount': 2}; n1 = bound(root, 'a1', 'charge', A1); n2 = bound(root, 'a2', 'charge', A2)
    _, ri1 = consumed(admin, w, root, 'a1', 'q1', n1); _, ri2 = consumed(admin, w, root, 'a2', 'q2', n2)
    before = ledger_lines()
    first = run(hc, root, 'a1', n1, ri1, 'charge', A1)
    checks.append(('first run executes', first['repeat'] is False and ledger_lines() == before + 1))
    again = run(hc, root, 'a1', n1, ri1, 'charge', A1)
    checks.append(('same run again is a repeat with the same report', again['repeat'] is True and again['report'] == first['report'] and ledger_lines() == before + 1))
    try:                                                       # v0.6: other arguments are another action; the host refuses rather than answering from the first
        run(hc, root, 'a1', n1, ri1, 'charge', {'order_id': 'DIFFERENT', 'amount': 999}); checks.append(('a retry with other arguments is refused', False))
    except GateRefused as exc:
        checks.append(('a retry with other arguments is refused (403); the first result stands', exc.status == 403 and ledger_lines() == before + 1))
    results, lock = [], threading.Lock()
    def burst():
        try:
            r = run(hc, root, 'a2', n2, ri2, 'charge', A2); kind = 'repeat' if r['repeat'] else 'ran'
        except GateRefused as exc:
            kind = f'refused {exc.status}'
        with lock: results.append(kind)
    ts = [threading.Thread(target=burst) for _ in range(8)]
    for t in ts: t.start()
    for t in ts: t.join()
    checks.append(('eight concurrent runs: exactly one execution', results.count('ran') == 1 and ledger_lines() == before + 2 and all(k in ('ran', 'repeat', 'refused 409') for k in results)))
    host.stop(); host.start(fresh=False)                      # the one-shot survives a host restart
    hc2 = GateHostClient(host.url)
    after = run(hc2, root, 'a1', n1, ri1, 'charge', A1)
    checks.append(('after a host restart the run is still a repeat', after['repeat'] is True and ledger_lines() == before + 2))
    return checks, {'burst': results}


def h3(admin, w, hc):
    root = 'h3'; fresh_root(admin, root, 4, 0); checks = []
    A1, A3 = {'order_id': 'h3-1', 'amount': 1}, {'order_id': 'h3-3', 'amount': 3}; n1 = bound(root, 'a1', 'charge', A1); n3 = bound(root, 'a3', 'charge', A3)
    rr1, ri1 = consumed(admin, w, root, 'a1', 'q1', n1)             # intent accepted: the witness will not release it
    admin.apply(root, ('RESERVE', 'a2', 'q2')); d, rr2 = w.accept_reservation(root, 'a2')   # reserved only
    rr3, ri3 = consumed(admin, w, root, 'a3', 'q3', n3)
    before = ledger_lines()
    f1 = hc.fence(root, 'a1', rr1); checks.append(('fence at the host returns a signed fence report', f1['report']['kind'] == 'FENCE_REPORT' and f1['report']['signer'] == GATE.public_hex))
    try:
        run(hc, root, 'a1', n1, ri1, 'charge', A1); checks.append(('fenced attempt cannot run', False))
    except GateRefused as exc:
        checks.append(('fenced attempt cannot run (409)', exc.status == 409 and ledger_lines() == before))
    d, _ = w.release(root, 'a1', f1['report']); checks.append(("the witness denies releasing an attempt whose intent it accepted (5.8/4)", d.kind == 'DENIED'))
    f2 = hc.fence(root, 'a2', rr2); d, rc = w.release(root, 'a2', f2['report'])
    checks.append(('a fence report for a reservation that never started releases it', d.kind == 'APPLIED' and rc.op[2] == 'BOUND_FENCE'))
    out = run(hc, root, 'a3', n3, ri3, 'charge', A3); checks.append(('a3 runs', out['repeat'] is False))
    try:
        hc.fence(root, 'a3', rr3); checks.append(('an attempt that ran cannot be fenced', False))
    except GateRefused as exc:
        checks.append(('an attempt that ran cannot be fenced (409)', exc.status == 409))
    checks.append(('replay lockstep', replay_lockstep(admin, root, 4, 0)[0]))
    return checks


def h4(admin, svc, host):
    checks, rows = [], []
    for i in range(4):
        root = f'h4-{i}'; fresh_root(admin, root, 3, 1)
        gov = Governor(Store(LOCAL_DSN), RemoteWitness(svc.url, WITNESS_PUB), root, 3, 1, admin=admin, host=GateHostClient(host.url))
        outcome = {'ran': 0, 'no_effect': 0, 'denied': 0, 'other': 0}
        for j in range(1, 6):
            try:
                if j == 2: gov.attempt(f'{root}:c{j}', 'refund', order_id=f'{root}', amount=0)
                else: gov.attempt(f'{root}:c{j}', 'charge', order_id=f'{root}-{j}', amount=j)
                outcome['ran'] += 1
            except NoEffect: outcome['ran'] += 1; outcome['no_effect'] += 1
            except BudgetExhausted: outcome['denied'] += 1
            except Exception as exc: outcome['other'] += 1; outcome.setdefault('errors', []).append(repr(exc)[:120])
        obs = admin.observe(root); labels = [d['op'][3] for d in admin.audit(root) if d['op'][0] == 'RECONCILE']
        row = {'root': root, **outcome, 'gate_key_in_governor': gov.gate is not None, 'credit': obs['credit'], 'labels': labels,
               'phases': sorted(a[2] for a in obs['attempts']), 'lockstep': replay_lockstep(admin, root, 3, 1)[0]}
        row['ok'] = (outcome['ran'] == 4 and outcome['no_effect'] == 1 and outcome['denied'] == 1 and outcome['other'] == 0 and not row['gate_key_in_governor']
                     and row['credit'] == 1 and labels == ['AUTHORISED'] * 4 and row['phases'] == ['EFFECT', 'EFFECT', 'EFFECT', 'NO_EFFECT'] and row['lockstep'])
        rows.append(row)
    checks.append(('four roots through the API in host mode', all(r['ok'] for r in rows)))
    # MCP in host mode
    root = 'h4-mcp'; fresh_root(admin, root, 2, 0); before = ledger_lines()
    env = dict(os.environ, PLEA_ADMIN_DSN=ADMIN_DSN, PLEA_LOCAL_DSN=LOCAL_DSN)
    p = subprocess.Popen([PYTHON, '-B', 'plea_mcp.py', '--root', root, '--budget', '2', '--witness-url', svc.url, '--admin-dsn', ADMIN_DSN,
                          '--gate-host', host.url], cwd=str(GATEWAY / 'mcp'), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
    rid = [0]
    def rpc(method, params=None):
        rid[0] += 1; p.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': rid[0], 'method': method, 'params': params or {}}) + '\n'); p.stdin.flush()
        line = p.stdout.readline()
        if not line: raise RuntimeError('mcp server closed: ' + p.stderr.read()[-300:])
        return json.loads(line)
    try:
        rpc('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {}, 'clientInfo': {'name': 't', 'version': '0'}})
        names = {t['name'] for t in rpc('tools/list')['result']['tools']}
        checks.append(("MCP host mode lists the host's tools", names == {'charge', 'refund', 'plea_status'}))
        def call(name, args): r = rpc('tools/call', {'name': name, 'arguments': args})['result']; return r['isError'], r['content'][0]['text']
        e1, t1 = call('charge', {'order_id': 'mcp-1', 'amount': 5}); e2, t2 = call('charge', {'order_id': 'mcp-1', 'amount': 5})
        checks.append(('MCP host mode: a retried charge runs once', not e1 and not e2 and t1 == t2 and ledger_lines() == before + 1))
        call('charge', {'order_id': 'mcp-2', 'amount': 5}); e3, t3 = call('charge', {'order_id': 'mcp-3', 'amount': 5})
        checks.append(('MCP host mode: beyond the budget is refused and never runs', e3 and 'budget exhausted' in t3 and ledger_lines() == before + 2))
    finally:
        p.stdin.close(); p.wait(timeout=10)
    checks.append(('MCP root replay lockstep', replay_lockstep(admin, root, 2, 0)[0]))
    return checks, rows


def h5(admin):
    checks = []
    old_w, new_w = WITNESS_KEY, Signer().private_hex; old_wp, new_wp = Signer(old_w).public_hex, Signer(new_w).public_hex
    old_g, new_g = GATE.private_hex, GateSigner().private_hex; old_gp, new_gp = GATE.public_hex, GateSigner(new_g).public_hex
    # witness rotation: a receipt under the old witness key, then the service restarted under the new key
    root = 'h5'; fresh_root(admin, root, 6, 0); A = lambda i: {'order_id': f'h5-{i}', 'amount': i}
    svc = WitnessService(8906, key=old_w, gate_keys=(old_gp, new_gp)); svc.start()
    w_old = RemoteWitness(svc.url, old_wp)
    n1, n2 = bound(root, 'a1', 'charge', A(1), old_gp), bound(root, 'a2', 'charge', A(2), old_gp)      # v0.6: bound to the old gate key
    _, ri_old = consumed(admin, w_old, root, 'a1', 'q1', n1); _, ri_old2 = consumed(admin, w_old, root, 'a2', 'q2', n2)
    svc.stop(); svc = WitnessService(8906, key=new_w, gate_keys=(old_gp, new_gp)); svc.start()
    w_both = RemoteWitness(svc.url, [old_wp, new_wp]); n3 = bound(root, 'a3', 'charge', A(3), old_gp); _, ri_new = consumed(admin, w_both, root, 'a3', 'q3', n3)
    checks.append(('client pinning [old, new] accepts receipts under the new key', ri_new.signer == new_wp))
    host_both = GateHost(8907, key=old_g, witness_keys=(old_wp, new_wp)); host_both.start(); hb = GateHostClient(host_both.url)
    r1 = run(hb, root, 'a1', n1, ri_old, 'charge', A(1)); r3 = run(hb, root, 'a3', n3, ri_new, 'charge', A(3))
    checks.append(('host pinning [old, new] runs on receipts under either witness key', r1['repeat'] is False and r3['repeat'] is False))
    d_old, _ = w_both.reconcile(root, 'a1', r1['report']); checks.append(("witness pinning [old gate, new gate] accepts the old host's report", d_old.kind == 'APPLIED'))
    host_both.stop()
    host_new_only = GateHost(8907, key=new_g, witness_keys=(new_wp,)); host_new_only.start(); hn = GateHostClient(host_new_only.url)
    try:
        run(hn, root, 'a2', n2, ri_old2, 'charge', A(2)); checks.append(('host pinning only the new witness key refuses an old receipt', False))
    except GateRefused as exc:
        checks.append(('host pinning only the new witness key refuses an old receipt (403)', exc.status == 403))
    try:                                                       # v0.6: the executor is bound; in v0.4 this host ran a3 again
        run(hn, root, 'a3', n3, ri_new, 'charge', A(3)); checks.append(('a host under another gate key refuses an attempt bound to the old one', False))
    except GateRefused as exc:
        checks.append(('a host under another gate key refuses an attempt bound to the old one (403): the executor is bound', exc.status == 403))
    n4 = bound(root, 'a4', 'charge', A(4), new_gp); _, ri4 = consumed(admin, w_both, root, 'a4', 'q4', n4)
    r4 = run(hn, root, 'a4', n4, ri4, 'charge', A(4)); checks.append(('an attempt bound to the new host runs there', r4['repeat'] is False))
    d_new, _ = w_both.reconcile(root, 'a4', r4['report']); checks.append(("witness accepts the new host's report", d_new.kind == 'APPLIED'))
    host_new_only.stop(); svc.stop()
    svc = WitnessService(8906, key=new_w, gate_keys=(new_gp,)); svc.start(); w_new = RemoteWitness(svc.url, new_wp)
    n5 = bound(root, 'a5', 'charge', A(5), old_gp); _, ri5 = consumed(admin, w_new, root, 'a5', 'q5', n5)
    host_old = GateHost(8907, key=old_g, witness_keys=(new_wp,)); host_old.start(); ho = GateHostClient(host_old.url)
    r5 = run(ho, root, 'a5', n5, ri5, 'charge', A(5))
    d5, rc5 = w_new.reconcile(root, 'a5', r5['report'])
    checks.append(("witness pinning only the new gate key derives NONE for the old host's report", d5.kind == 'DENIED' and rc5.op[3] == 'NONE'))
    host_old.stop(); svc.stop()
    checks.append(('replay lockstep', replay_lockstep(admin, root, 6, 0)[0]))
    return checks


def main():
    admin = Store(ADMIN_DSN); t0 = time.time()
    LEDGER.unlink(missing_ok=True)
    host = GateHost(8904); host.start(); svc = WitnessService(8905, key=WITNESS_KEY); svc.start()
    try:
        w = RemoteWitness(svc.url, WITNESS_PUB); hc = GateHostClient(host.url)
        r1 = h1(admin, w, hc); r2, burst = h2(admin, w, hc, host); hc = GateHostClient(host.url); r3 = h3(admin, w, hc); r4, rows = h4(admin, svc, host)
    finally:
        host.stop(); svc.stop()
    r5 = h5(admin)
    out = {'seconds': round(time.time() - t0, 1), 'H1': r1, 'H2': r2, 'H3': r3, 'H4': r4, 'H5': r5, 'h2_burst': burst, 'h4_rows': rows}
    for k in ('H1', 'H2', 'H3', 'H4', 'H5'): out[k + '_ok'] = all(ok for _, ok in out[k])
    out['PASS'] = all(out[k + '_ok'] for k in ('H1', 'H2', 'H3', 'H4', 'H5'))
    write_output('h_tests.json', out)
    for k in ('H1', 'H2', 'H3', 'H4', 'H5'):
        for label, ok in out[k]: print(k, 'ok  ' if ok else 'FAIL', label)
    print(json.dumps({k: v for k, v in out.items() if k not in ('H1', 'H2', 'H3', 'H4', 'H5', 'h4_rows')}, indent=1))
    print('H RESULT:', 'PASS' if out['PASS'] else 'FAIL'); raise SystemExit(0 if out['PASS'] else 1)


if __name__ == '__main__':
    main()
