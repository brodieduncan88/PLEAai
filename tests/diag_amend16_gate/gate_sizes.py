"""Design gate, part D (21 November 2026): how large a gate report can be, what the mailbox's 64 KiB limit does at its
edge, and what the mailbox as it stands accepts and refuses.  No code is changed.
DIAG_DB=<database> python gate_sizes.py SRC OUT"""
from gate_common import *                                      # noqa: F401,F403
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

b = Bench('GZ')
try:
    s, root = b.s, b.root; mb = f"https://127.0.0.1:{s.ports['mailbox']}"
    # ---- D1: how large can one gate-signed report be?
    sizes = {}
    honest_before = b.attempts(); b.r.submit({'material': 'PA66-GF30', 'wall_mm': 2.5, 'mode': 'normal'}); x = b.newest(honest_before)
    st, ans, reports = b.reports_of(x); real = ans['evidence'][0]['evidence']
    sizes['a real report of this deployment'] = {'bytes as JSON': len(json.dumps(real)), 'nonce characters': len(real['nonce']), 'run name characters': len(real['aid']), 'budget name characters': len(real['root'])}
    for label, aid, nonce in (('a run name of 512 non-ASCII letters', 'é' * 512, 'n-long-name'), ('a nonce of 70,000 characters', 'big-nonce', 'N' * 70000), ('a nonce of 1,000,000 characters', 'huge-nonce', 'N' * 1000000)):
        row = {}
        try:
            d, _ = b.local.apply(root, ('RESERVE', aid, 'key-' + aid[:20])); row['RESERVE'] = [d.kind, d.code]
            a1 = b.accept(('ACCEPT_RESERVATION', aid)); row['ACCEPT_RESERVATION'] = [a1['status'], a1['kind'], a1['code']]
            d, _ = b.local.apply(root, ('TOKEN', aid)); row['TOKEN'] = [d.kind, d.code]
            d, _ = b.local.apply(root, ('START', aid, nonce)); row['START'] = [d.kind, d.code]
            a2 = b.accept(('ACCEPT_INTENT', aid)); row['ACCEPT_INTENT'] = [a2['status'], a2['kind'], a2['code']]
            rep = b.report(aid, nonce, 'EFFECT', {'verdict': 'FAIL'}); row['bytes of the gate-signed report as JSON'] = len(json.dumps(rep))
            a3 = b.accept(('RECONCILE', aid), rep); row['RECONCILE'] = [a3['status'], a3['kind'], a3['code']]
            st, ans, reps = b.reports_of({'aid': aid, 'nonce': nonce}); row['GET /run'] = st; row['reports given, authentic'] = [r_['authentic'] for r_ in reps]
            row['bytes of the witness\'s answer for the run'] = len(json.dumps(ans)); row['two such reports whole'] = 2 * row['bytes of the gate-signed report as JSON']
        except Exception as exc:
            row['stopped at'] = f'{type(exc).__name__}: {str(exc).splitlines()[0][:200]}'
        sizes[label] = row
    note('D1. how large one gate-signed report can be made by whoever holds the service\'s database role and the gate\'s key', sizes=sizes, mailbox_limit=65536)

    # ---- D2: the mailbox as it stands
    key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex((s.dir / 'courier.key').read_text().strip()))
    def notice(outcome, text, form=2, extra=None, aid=None):
        body = {'statement': 'NOTICE', 'root': root, 'aid': x['aid'] if aid is None else aid, 'request_key': None, 'outcome': outcome, 'reason_code': None, 'detail': None, 'result_digest': None,
                'seq': 9, 'head': 'a' * 64, 'time': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'courier': 'courier', 'text': text}
        if form == 2:
            body['form'] = 2
        fields = C.notice_fields(body)
        n = dict(body, signer=s.keys['courier'][0], signature=key.sign(C.canonical({k: body.get(k) for k in fields}).encode()).hex())
        if extra:
            n.update(extra)
        return n
    def deliver(n=None, raw=None):
        import urllib.request, urllib.error
        ctx = TLS.TLSClient(s.pki['ca'], *b.cour).context(); data = raw if raw is not None else json.dumps(n).encode()
        req = urllib.request.Request(mb + '/deliver', data=data, method='POST', headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                return [resp.status, len(data), 'receipt' if json.loads(resp.read()).get('statement') == 'DELIVERED' else 'other']
        except urllib.error.HTTPError as exc:
            return [exc.code, len(data), (json.loads(exc.read() or b'{}') or {}).get('error', '')[:160]]
    two = json.dumps([real, dict(real, result_digest='b' * 64)])
    def padded(target):
        n = notice('INCONSISTENT', ''); base = len(json.dumps(n)); return notice('INCONSISTENT', 'x' * (target - base))
    exact, over = padded(65536), padded(65537)
    out = {'an existing outcome of the courier\'s own (INCONSISTENT) whose words carry two whole reports': deliver(notice('INCONSISTENT', two)),
           'an outcome the mailbox does not know (CONFLICT)': deliver(notice('CONFLICT', two)),
           'a statement of coverage as an outcome (WATCHING)': deliver(notice('WATCHING', 'x', aid='')),
           'a known outcome with one more field (evidence)': deliver(notice('INCONSISTENT', 'y', extra={'evidence': [real]})),
           'a notice of exactly 65,536 bytes': deliver(exact)[:3], 'a notice of 65,537 bytes': deliver(over)[:3],
           'bytes that are not a notice, 100 of them': deliver(raw=b'{"statement": "CHALLENGE"}' + b' ' * 74)}
    held = sorted((s.dir / 'mailbox' / 'notices').glob('*.json'))
    note('D2. what the mailbox as it stands takes and refuses', deliveries={k: v for k, v in out.items()}, notices_now_held=len(held),
         the_mailbox_checks_a_notice_s_words=False, paths_the_mailbox_serves=['POST /deliver', 'GET /pubkey'])
    code, summary = s.courier([root], 900, 'd3'); held = sorted((s.dir / 'mailbox' / 'notices').glob('*.json'))
    real_notices = [json.loads(p.read_text()) for p in held]
    real_run = [h for h in real_notices if h['notice'].get('outcome') == 'FAIL']
    note('D3. a real notice and receipt of this deployment', courier_exit=code, a_FAIL_notice_bytes=[len(json.dumps(h['notice'])) for h in real_run], its_receipt_bytes=[len(json.dumps(h['receipt'])) for h in real_run],
         two_real_reports_whole_bytes=len(two), receipt_fields=list(C.RECEIPT_FIELDS), receipt_time_resolution='one second, the mailbox\'s wall clock (time.gmtime)')
finally:
    save('gate_sizes.json'); b.stop()
