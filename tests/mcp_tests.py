#!/usr/bin/env python3
"""M1–M3: an agent's tools governed over MCP, without the agent changing.

M1 protocol and governance.  A governed server (budget 2, replacement 1) over stdio with the demo tools: initialize,
   tools/list; charge 1 runs; charge 1 again is served from the stored result and the ledger does not grow; refund
   of a zero amount is a NoEffect and earns a replacement; charge 2 runs on it; charge 3 is refused (budget) and
   does not run; the operator holds the run and charge 4 is refused (held); after recovery charge 4 is refused
   again (budget); plea_status reports live (0, 3, 1) and credit 1.  Replay lockstep and the chain hold.
M2 the double charge.  The same retry against the ungoverned server charges twice; against the governed server it
   charges once.  A second charge under a distinct request key runs, so the governor keys retries, it does not
   blanket-deduplicate.
M3 the upstream proxy.  The governed server spawns the ungoverned server and proxies its tools.  The agent sees
   the same tool list; the same guarantees hold; the ledger shows the upstream ran each admitted call once.
"""
import json
import os
import subprocess
import time

from common import ADMIN_DSN, CONTROL_DSN, GATE, GATEWAY, LOCAL_DSN, PYTHON, Store, WitnessService, replay_lockstep, write_output

MCP = GATEWAY / 'mcp'


class Client:
    def __init__(self, cmd, env, cwd=MCP):
        self.p = subprocess.Popen(cmd, cwd=str(cwd), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
        self.rid = 0
        self.rpc('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {}, 'clientInfo': {'name': 'test', 'version': '0'}})
        self.p.stdin.write(json.dumps({'jsonrpc': '2.0', 'method': 'notifications/initialized', 'params': {}}) + '\n'); self.p.stdin.flush()

    def rpc(self, method, params=None):
        self.rid += 1
        self.p.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': self.rid, 'method': method, 'params': params or {}}) + '\n'); self.p.stdin.flush()
        line = self.p.stdout.readline()
        if not line:
            raise RuntimeError('server closed: ' + self.p.stderr.read()[-300:])
        return json.loads(line)

    def tools(self):
        return [t['name'] for t in self.rpc('tools/list')['result']['tools']]

    def call(self, name, args):
        r = self.rpc('tools/call', {'name': name, 'arguments': args})['result']
        return r['isError'], ' '.join(c.get('text', '') for c in r['content'])

    def close(self):
        self.p.stdin.close(); self.p.wait(timeout=10)


def ledger_counts(path):
    counts = {}
    if path.exists():
        for line in path.open():
            d = json.loads(line); counts[(d['kind'], d['order_id'])] = counts.get((d['kind'], d['order_id']), 0) + 1
    return counts


def governed(root, budget, replacement, svc, env, extra):
    return Client([PYTHON, '-B', 'plea_mcp.py', '--root', root, '--budget', str(budget), '--replacement', str(replacement),
                   '--witness-url', svc.url, '--admin-dsn', ADMIN_DSN, '--gate-key', GATE.private_hex] + extra, env)


def ctl(root, action, env):
    return subprocess.run([PYTHON, '-B', 'plea_ctl.py', root, action], cwd=str(MCP), capture_output=True, text=True, env=env).stdout.strip()


def m1(admin, svc, env, ledger):
    root = 'm1'; checks = []
    c = governed(root, 2, 1, svc, env, ['--tools', 'demo_tools'])
    try:
        checks.append(('tools listed', set(c.tools()) == {'charge', 'refund', 'plea_status'}))
        e, t = c.call('charge', {'order_id': '1', 'amount': 10}); checks.append(('charge 1 runs', not e and 'charged 10' in t))
        e, t2 = c.call('charge', {'order_id': '1', 'amount': 10}); checks.append(('charge 1 retry served, same text', not e and t2 == t))
        checks.append(('ledger has one charge for order 1', ledger_counts(ledger).get(('charge', '1')) == 1))
        e, t = c.call('refund', {'order_id': '1', 'amount': 0}); checks.append(('zero refund is a no-effect', not e and 'no effect' in t))
        e, t = c.call('charge', {'order_id': '2', 'amount': 20}); checks.append(('charge 2 runs on the replacement', not e and 'charged 20' in t))
        e, t = c.call('charge', {'order_id': '3', 'amount': 30}); checks.append(('charge 3 refused: budget', e and 'budget exhausted' in t))
        checks.append(('ledger: order 3 never charged', ('charge', '3') not in ledger_counts(ledger)))
        checks.append(('operator hold', ctl(root, 'hold', env).startswith('APPLIED')))
        e, t = c.call('charge', {'order_id': '4', 'amount': 40}); checks.append(('charge 4 refused: held', e and 'held' in t))
        checks.append(('operator recover', ctl(root, 'recover', env).startswith('APPLIED')))
        e, t = c.call('charge', {'order_id': '4', 'amount': 40}); checks.append(('charge 4 refused after recovery: budget', e and 'budget exhausted' in t))
        e, t = c.call('plea_status', {}); st = json.loads(t)
        checks.append(('status live (0,3,1) credit 1', st['live'] == [0, 3, 1] and st['credit'] == 1))
        e, t = c.call('nonexistent', {}); checks.append(('unknown tool is an error', e))
    finally:
        c.close()
    checks.append(('replay lockstep', replay_lockstep(admin, root, 2, 1)[0])); checks.append(('chain', admin.verify_chain(root)[0]))
    return checks


def m2(admin, svc, env, ledger):
    checks = []
    v = Client([PYTHON, '-B', 'vanilla_mcp.py'], env)
    try:
        v.call('charge', {'order_id': '7', 'amount': 50}); v.call('charge', {'order_id': '7', 'amount': 50})   # the retry
    finally:
        v.close()
    vanilla = ledger_counts(ledger).get(('charge', '7'), 0)
    checks.append(('ungoverned: the retry charges twice', vanilla == 2))
    c = governed('m2', 3, 0, svc, env, ['--tools', 'demo_tools'])
    try:
        c.call('charge', {'order_id': '8', 'amount': 50}); c.call('charge', {'order_id': '8', 'amount': 50})
        governed_count = ledger_counts(ledger).get(('charge', '8'), 0)
        checks.append(('governed: the retry charges once', governed_count == 1))
        e, t = c.call('charge', {'order_id': '8', 'amount': 50, '_plea_request_key': 'second-charge-for-8'})
        checks.append(('a distinct request key is a new call', not e and ledger_counts(ledger).get(('charge', '8')) == 2))
    finally:
        c.close()
    checks.append(('replay lockstep', replay_lockstep(admin, 'm2', 3, 0)[0]))
    return checks, {'ungoverned_charges_for_7': vanilla, 'governed_charges_for_8_after_retry': governed_count}


def m3(admin, svc, env, ledger):
    root = 'm3'; checks = []
    c = governed(root, 2, 0, svc, env, ['--upstream', f'{PYTHON} -B vanilla_mcp.py'])
    try:
        checks.append(('upstream tools listed through the proxy', set(c.tools()) == {'charge', 'refund', 'plea_status'}))
        e, t = c.call('charge', {'order_id': '9', 'amount': 5}); checks.append(('proxied charge 9 runs', not e and 'charged 5' in t))
        e, t2 = c.call('charge', {'order_id': '9', 'amount': 5}); checks.append(('proxied retry served', not e and t2 == t))
        checks.append(('upstream ran order 9 once', ledger_counts(ledger).get(('charge', '9')) == 1))
        e, t = c.call('charge', {'order_id': '10', 'amount': 5}); checks.append(('proxied charge 10 runs', not e))
        e, t = c.call('charge', {'order_id': '11', 'amount': 5}); checks.append(('proxied charge 11 refused: budget', e and 'budget exhausted' in t))
        checks.append(('upstream never saw order 11', ('charge', '11') not in ledger_counts(ledger)))
    finally:
        c.close()
    checks.append(('replay lockstep', replay_lockstep(admin, root, 2, 0)[0]))
    return checks


def main():
    admin = Store(ADMIN_DSN); t0 = time.time()
    ledger = GATEWAY / 'outputs' / 'mcp_ledger.jsonl'; ledger.unlink(missing_ok=True)
    with admin.connect() as conn:
        conn.execute("DELETE FROM roots WHERE root_id IN ('m1', 'm2', 'm3')"); conn.commit()
    env = dict(os.environ, PLEA_LEDGER=str(ledger), PLEA_ADMIN_DSN=ADMIN_DSN, PLEA_LOCAL_DSN=LOCAL_DSN, PLEA_CONTROL_DSN=CONTROL_DSN)
    svc = WitnessService(8799); svc.start()
    try:
        r1 = m1(admin, svc, env, ledger); r2, demo = m2(admin, svc, env, ledger); r3 = m3(admin, svc, env, ledger)
    finally:
        svc.stop()
    out = {'seconds': round(time.time() - t0, 1), 'M1': r1, 'M2': r2, 'M3': r3, 'demo': demo,
           'M1_ok': all(ok for _, ok in r1), 'M2_ok': all(ok for _, ok in r2), 'M3_ok': all(ok for _, ok in r3)}
    out['PASS'] = out['M1_ok'] and out['M2_ok'] and out['M3_ok']
    write_output('mcp_tests.json', out)
    for name, rows in (('M1', r1), ('M2', r2), ('M3', r3)):
        for label, ok in rows:
            print(name, 'ok  ' if ok else 'FAIL', label)
    print(json.dumps({k: v for k, v in out.items() if k not in ('M1', 'M2', 'M3')}, indent=1))
    print('MCP RESULT:', 'PASS' if out['PASS'] else 'FAIL'); raise SystemExit(0 if out['PASS'] else 1)


if __name__ == '__main__':
    main()
