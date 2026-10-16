#!/usr/bin/env python3
"""T1–T4 (v0.5): mutual TLS between the governor, the witness service and the gate host.

T1 the services admit nothing without a certificate the authority issued and the allow-list names.  Against a
   witness and a host that require client certificates and admit only 'governor': plain HTTP to the TLS port (the
   connection is closed without a response: WitnessUnavailable / ConnectionError, amendment 1), HTTPS with the
   authority pinned but no client certificate, a client certificate from an impostor authority, a server certificate
   (the host's own) presented as a client certificate (each a TransportError), and a 'stranger' certificate from the
   right authority that the allow-list does not name (refused by the handler), are each refused; the audit log and
   the host's ledger do not change; the governor's certificate is then admitted, and the service names it as its peer.
T2 the client refuses a server that is not the pinned one.  A witness and a host presenting certificates from
   the impostor authority, and a witness presenting a genuine certificate issued for another name, are each
   refused by a client pinning the authority; nothing is applied and nothing runs; the genuine witness is accepted.
T3 the lifecycle over mutual TLS.  Four roots through the API in host mode over TLS (E3's schedule: 4 ran,
   1 NoEffect, 1 denied, credit 1, no gate key in the governor, replay lockstep); the MCP server with --tls-ca,
   --tls-cert and --tls-key in host mode: lists the host's tools, a retried charge runs once, beyond the budget is
   refused; the MCP server without them against the TLS services does not start and applies nothing.
T4 rotation.  A new server certificate from the same authority: the unchanged client keeps working.  A new client
   certificate: the unchanged service admits it.  A new authority: during the overlap the service presents a
   certificate from the new authority and trusts both, a client pinning both with the old certificate works, a
   client pinning only the old authority is refused; after the cut-over (the service trusts only the new) the old
   client certificate is refused and the new one admitted; replay lockstep.
"""
import json
import os
import subprocess
import time

from common import (ADMIN_DSN, GATEWAY, LOCAL_DSN, PKI, PYTHON, WITNESS_KEY, WITNESS_PUB, GateHost, Store, TLS, TLSClient, TLSServer,
                    WitnessService, admitted, bound, client_tls, fresh_root, make_pki, replay_lockstep, server_tls, write_output)
from plea_gateway import BudgetExhausted, GateHostClient, GateRefused, Governor, NoEffect, RemoteWitness, TransportError, WitnessUnavailable

LEDGER = GATEWAY / 'outputs' / 'tls_ledger.jsonl'
IMPOSTOR_LEDGER = GATEWAY / 'outputs' / 'tls_impostor_ledger.jsonl'


def lines(path):
    return sum(1 for _ in path.open()) if path.exists() else 0


ADM = {}


def consumed(admin, w, root, aid, q, n):
    rr, ri, adm = admitted(admin, w, root, aid, q, n); ADM[(root, aid)] = adm      # v0.7: the host requires the admission
    return rr, ri


def attempt_refused(label, fn, want=TransportError, status=None):
    """Run fn; the check passes when it raises `want` (and, for GateRefused/PermissionError, the right status)."""
    try:
        fn(); return (label, False)
    except want as exc:
        if status is not None and isinstance(exc, GateRefused):
            return (f'{label} ({exc.status})', exc.status == status)
        return (f'{label} ({want.__name__})', True)
    except Exception as exc:
        return (f'{label}: unexpected {type(exc).__name__}: {str(exc)[:80]}', False)


def t1(admin, pki, svc, host):
    checks = []; root = 't1'; fresh_root(admin, root, 4, 0)
    gov_tls = client_tls(pki)
    w = RemoteWitness(svc.url, WITNESS_PUB, tls=gov_tls)
    A1 = {'order_id': 't1-1', 'amount': 1}; n1 = bound(root, 'a1', 'charge', A1)   # v0.6: the nonce binds the action to the host's key
    _, ri1 = consumed(admin, w, root, 'a1', 'q1', n1)                         # the genuine client, to get a receipt for the host checks
    admin.apply(root, ('RESERVE', 'a2', 'q2'))                                 # a2 reserved locally; its acceptance is what the bad clients try
    transports = [       # (label, url pattern, client TLS, what the witness client raises, what the host client raises)
        ('plain HTTP to the TLS port: the connection is closed without a response', 'http://127.0.0.1:%d', None, WitnessUnavailable, ConnectionError),
        ('HTTPS with the authority pinned but no client certificate', 'https://127.0.0.1:%d', TLSClient(pki['ca']), TransportError, TransportError),
        ('a client certificate from the impostor authority', 'https://127.0.0.1:%d', TLSClient(pki['ca'], *pki['impostor']['governor']), TransportError, TransportError),
        ("a server certificate (the host's own) as a client certificate", 'https://127.0.0.1:%d', TLSClient(pki['ca'], *pki['host']), TransportError, TransportError),
    ]
    before = len(admin.audit(root))
    for label, url, tls, want_w, _ in transports:
        checks.append(attempt_refused('witness: ' + label, lambda: RemoteWitness(url % svc.port, WITNESS_PUB, tls=tls).accept_reservation(root, 'a2'), want_w))
    checks.append(attempt_refused("witness: a 'stranger' certificate the allow-list does not name",
                                  lambda: RemoteWitness(svc.url, WITNESS_PUB, tls=client_tls(pki, 'stranger')).accept_reservation(root, 'a2'), PermissionError))
    checks.append(('witness: the audit log is unchanged by the refusals', len(admin.audit(root)) == before))
    d, _ = w.accept_reservation(root, 'a2'); checks.append(("witness: the governor's certificate is admitted", d.kind == 'APPLIED'))
    import urllib.request
    with urllib.request.urlopen(svc.url + '/pubkey', context=gov_tls.context()) as r:
        info = json.load(r)
    checks.append(("witness: names the peer 'governor' over TLS", info.get('tls') is True and info.get('peer') == 'governor'))
    # the host
    before = lines(LEDGER); run = dict(root=root, aid='a1', nonce=n1, receipt=ri1, tool='charge', arguments=A1, admission=ADM[(root, 'a1')])
    for label, url, tls, _, want_h in transports:
        checks.append(attempt_refused('host: ' + label, lambda: GateHostClient(url % host.port, tls=tls).run(**run), want_h))
    checks.append(attempt_refused("host: a 'stranger' certificate the allow-list does not name",
                                  lambda: GateHostClient(host.url, tls=client_tls(pki, 'stranger')).run(**run), GateRefused, 403))
    checks.append(('host: the ledger is unchanged by the refusals', lines(LEDGER) == before))
    r = GateHostClient(host.url, tls=gov_tls).run(**run)
    checks.append(("host: the governor's certificate is admitted and the tool runs once", r['repeat'] is False and lines(LEDGER) == before + 1))
    return checks


def t2(admin, pki):
    checks = []; root = 't2'; fresh_root(admin, root, 4, 0); gov_tls = client_tls(pki)
    imp = pki['impostor']; imp_client = TLSClient(imp['ca'], *imp['governor'])
    admin.apply(root, ('RESERVE', 'a1', 'q1')); before = len(admin.audit(root))
    svc = WitnessService(8912, key=WITNESS_KEY, tls=server_tls(imp, 'witness', ca=imp['ca']), client=imp_client); svc.start()
    try:
        checks.append(attempt_refused('an impostor witness (certificate from another authority)',
                                      lambda: RemoteWitness(svc.url, WITNESS_PUB, tls=gov_tls).accept_reservation(root, 'a1')))
    finally:
        svc.stop()
    checks.append(('the impostor witness applied nothing', len(admin.audit(root)) == before))
    host = GateHost(8913, tls=server_tls(imp, 'host', ca=imp['ca']), client=imp_client, ledger=str(IMPOSTOR_LEDGER)); host.start()
    try:
        checks.append(attempt_refused('an impostor host', lambda: GateHostClient(host.url, tls=gov_tls).tools()))
    finally:
        host.stop()
    checks.append(('the impostor host ran nothing', lines(IMPOSTOR_LEDGER) == 0))
    svc = WitnessService(8914, key=WITNESS_KEY, tls=TLSServer(*pki['elsewhere'], pki['ca'], ('governor',))); svc.start()
    try:
        checks.append(attempt_refused('a genuine certificate issued for another name',
                                      lambda: RemoteWitness(svc.url, WITNESS_PUB, tls=gov_tls).accept_reservation(root, 'a1')))
    finally:
        svc.stop()
    checks.append(('the wrongly named witness applied nothing', len(admin.audit(root)) == before))
    svc = WitnessService(8912, key=WITNESS_KEY, tls=server_tls(pki, 'witness'), client=gov_tls); svc.start()
    try:
        d, _ = RemoteWitness(svc.url, WITNESS_PUB, tls=gov_tls).accept_reservation(root, 'a1')
        checks.append(('the genuine witness is accepted', d.kind == 'APPLIED'))
    finally:
        svc.stop()
    return checks


def t3(admin, pki, svc, host):
    checks, rows = [], []; gov_tls = client_tls(pki)
    for i in range(4):
        root = f't3-{i}'; fresh_root(admin, root, 3, 1)
        gov = Governor(Store(LOCAL_DSN), RemoteWitness(svc.url, WITNESS_PUB, tls=gov_tls), root, 3, 1, admin=admin, host=GateHostClient(host.url, tls=gov_tls))
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
    checks.append(('four roots through the API in host mode over mutual TLS', all(r['ok'] for r in rows)))
    root = 't3-mcp'; fresh_root(admin, root, 2, 0); before = lines(LEDGER)
    env = dict(os.environ, PLEA_ADMIN_DSN=ADMIN_DSN, PLEA_LOCAL_DSN=LOCAL_DSN)
    base = [PYTHON, '-B', 'plea_mcp.py', '--root', root, '--budget', '2', '--witness-url', svc.url, '--witness-key', WITNESS_PUB, '--admin-dsn', ADMIN_DSN, '--gate-host', host.url]
    tls_args = ['--tls-ca', gov_tls.ca, '--tls-cert', gov_tls.cert, '--tls-key', gov_tls.key]
    p = subprocess.Popen(base + tls_args, cwd=str(GATEWAY / 'mcp'), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
    rid = [0]
    def rpc(method, params=None):
        rid[0] += 1; p.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': rid[0], 'method': method, 'params': params or {}}) + '\n'); p.stdin.flush()
        line = p.stdout.readline()
        if not line: raise RuntimeError('mcp server closed: ' + p.stderr.read()[-300:])
        return json.loads(line)
    try:
        rpc('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {}, 'clientInfo': {'name': 't', 'version': '0'}})
        names = {t['name'] for t in rpc('tools/list')['result']['tools']}
        checks.append(("MCP over TLS lists the host's tools", names == {'charge', 'refund', 'plea_status'}))
        def call(name, args): r = rpc('tools/call', {'name': name, 'arguments': args})['result']; return r['isError'], r['content'][0]['text']
        e1, t1_ = call('charge', {'order_id': 'tmcp-1', 'amount': 5}); e2, t2_ = call('charge', {'order_id': 'tmcp-1', 'amount': 5})
        checks.append(('MCP over TLS: a retried charge runs once', not e1 and not e2 and t1_ == t2_ and lines(LEDGER) == before + 1))
        call('charge', {'order_id': 'tmcp-2', 'amount': 5}); e3, t3_ = call('charge', {'order_id': 'tmcp-3', 'amount': 5})
        checks.append(('MCP over TLS: beyond the budget is refused and never runs', e3 and 'budget exhausted' in t3_ and lines(LEDGER) == before + 2))
    finally:
        p.stdin.close(); p.wait(timeout=10)
    checks.append(('MCP root replay lockstep', replay_lockstep(admin, root, 2, 0)[0]))
    root2 = 't3-mcp-notls'; fresh_root(admin, root2, 2, 0); n_before = len(admin.audit(root2)); l_before = lines(LEDGER)
    q = subprocess.run([*base[:3], '--root', root2, *base[5:]], cwd=str(GATEWAY / 'mcp'), input='', capture_output=True, text=True, timeout=30, env=env)
    checks.append(('MCP without TLS against the TLS services does not start and applies nothing',
                   q.returncode != 0 and 'TransportError' in q.stderr and len(admin.audit(root2)) == n_before and lines(LEDGER) == l_before))
    return checks, rows


def t4(admin, pki):
    checks = []; root = 't4'; fresh_root(admin, root, 6, 0); port = 8915
    ca_key, ca_cert = (PKI / 'ca.key').read_bytes(), (PKI / 'ca.crt').read_bytes()
    def write(name, key, cert):
        (PKI / f'{name}.key').write_bytes(key); (PKI / f'{name}.crt').write_bytes(cert); return str(PKI / f'{name}.crt'), str(PKI / f'{name}.key')
    gov_old = client_tls(pki)
    # (a) a new server certificate from the same authority
    w2 = write('witness2', *TLS.issue(ca_key, ca_cert, 'witness', 'server', ('127.0.0.1', 'localhost')))
    svc = WitnessService(port, key=WITNESS_KEY, tls=TLSServer(*w2, pki['ca'], ('governor',)), client=gov_old); svc.start()
    try:
        _, r1 = consumed(admin, RemoteWitness(svc.url, WITNESS_PUB, tls=gov_old), root, 'a1', 'q1', 'n1')
        checks.append(('a new server certificate from the same authority: the unchanged client keeps working', r1.kind == 'APPLIED'))
        # (b) a new client certificate from the same authority
        g2 = write('governor2', *TLS.issue(ca_key, ca_cert, 'governor', 'client'))
        _, r2 = consumed(admin, RemoteWitness(svc.url, WITNESS_PUB, tls=TLSClient(pki['ca'], *g2)), root, 'a2', 'q2', 'n2')
        checks.append(('a new client certificate from the same authority: the unchanged service admits it', r2.kind == 'APPLIED'))
    finally:
        svc.stop()
    # (c) a new authority: overlap, then cut-over
    new_ca_key, new_ca_cert = TLS.make_ca('plea-test-ca-2'); (PKI / 'ca2.key').write_bytes(new_ca_key); (PKI / 'ca2.crt').write_bytes(new_ca_cert)
    both = TLS.bundle(str(PKI / 'ca_both.crt'), pki['ca'], str(PKI / 'ca2.crt'))
    w3 = write('witness3', *TLS.issue(new_ca_key, new_ca_cert, 'witness', 'server', ('127.0.0.1', 'localhost')))
    g3 = write('governor3', *TLS.issue(new_ca_key, new_ca_cert, 'governor', 'client'))
    gov_both_old_cert = TLSClient(both, *pki['governor']); gov_new = TLSClient(str(PKI / 'ca2.crt'), *g3)
    svc = WitnessService(port, key=WITNESS_KEY, tls=TLSServer(*w3, both, ('governor',)), client=gov_both_old_cert); svc.start()
    try:
        _, r3 = consumed(admin, RemoteWitness(svc.url, WITNESS_PUB, tls=gov_both_old_cert), root, 'a3', 'q3', 'n3')
        checks.append(('overlap: a client pinning both authorities with the old certificate works', r3.kind == 'APPLIED'))
        checks.append(attempt_refused('overlap: a client pinning only the old authority is refused (the server is under the new)',
                                      lambda: RemoteWitness(svc.url, WITNESS_PUB, tls=gov_old).accept_reservation(root, 'a3')))
    finally:
        svc.stop()
    svc = WitnessService(port, key=WITNESS_KEY, tls=TLSServer(*w3, str(PKI / 'ca2.crt'), ('governor',)), client=gov_new); svc.start()
    try:
        checks.append(attempt_refused('cut-over: the old client certificate is refused',
                                      lambda: RemoteWitness(svc.url, WITNESS_PUB, tls=TLSClient(both, *pki['governor'])).accept_reservation(root, 'a3')))
        _, r4 = consumed(admin, RemoteWitness(svc.url, WITNESS_PUB, tls=gov_new), root, 'a4', 'q4', 'n4')
        checks.append(('cut-over: the new client certificate is admitted', r4.kind == 'APPLIED'))
    finally:
        svc.stop()
    checks.append(('replay lockstep', replay_lockstep(admin, root, 6, 0)[0]))
    return checks


def main():
    admin = Store(ADMIN_DSN); t0 = time.time()
    LEDGER.unlink(missing_ok=True); IMPOSTOR_LEDGER.unlink(missing_ok=True)
    pki = make_pki(); gov_tls = client_tls(pki)
    svc = WitnessService(8910, key=WITNESS_KEY, tls=server_tls(pki, 'witness'), client=gov_tls); svc.start()
    host = GateHost(8911, tls=server_tls(pki, 'host'), client=gov_tls, ledger=str(LEDGER)); host.start()
    try:
        r1 = t1(admin, pki, svc, host); r2 = t2(admin, pki); r3, rows = t3(admin, pki, svc, host)
    finally:
        host.stop(); svc.stop()
    r4 = t4(admin, pki)
    out = {'seconds': round(time.time() - t0, 1), 'T1': r1, 'T2': r2, 'T3': r3, 'T4': r4, 't3_rows': rows}
    for k in ('T1', 'T2', 'T3', 'T4'): out[k + '_ok'] = all(ok for _, ok in out[k])
    out['PASS'] = all(out[k + '_ok'] for k in ('T1', 'T2', 'T3', 'T4'))
    write_output('t_tests.json', out)
    for k in ('T1', 'T2', 'T3', 'T4'):
        for label, ok in out[k]: print(k, 'ok  ' if ok else 'FAIL', label)
    print(json.dumps({k: v for k, v in out.items() if k not in ('T1', 'T2', 'T3', 'T4', 't3_rows')}, indent=1))
    print('T RESULT:', 'PASS' if out['PASS'] else 'FAIL'); raise SystemExit(0 if out['PASS'] else 1)


if __name__ == '__main__':
    main()
