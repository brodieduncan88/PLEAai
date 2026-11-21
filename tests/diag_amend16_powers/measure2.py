"""Diagnostic, 21 November 2026, second part of the measurement.  Development evidence only; no code of e25a297 is changed.

    DIAG_DB=<database of measure.py> python measure2.py chain SRC OUT ROOT      the whole chain of one budget, read page by page as the courier follows it
    DIAG_DB=<fresh database>         python measure2.py live  SRC OUT MINUTES   the courier making pass after pass while honest runs are made
"""
import json, os, pathlib, statistics, subprocess, sys, threading, time, urllib.parse, urllib.request

MODE, SRC, OUT = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3]); DB = os.environ['DIAG_DB']
for role, pw, var in (('plea_local', 'local', 'PLEA_LOCAL_DSN'), ('plea_witness', 'witness', 'PLEA_WITNESS_DSN'), ('plea_control', 'control', 'PLEA_CONTROL_DSN')):
    os.environ[var] = f'postgresql://{role}:{pw}@127.0.0.1:5432/{DB}'
sys.path[:0] = [SRC + '/tests', SRC, SRC + '/verify']
import verify_tests as VT                                   # noqa: E402
import deploy                                               # noqa: E402
from plea_gateway import Store, tls as TLS                  # noqa: E402
PY = sys.executable; R = {'mode': MODE, 'database': DB, 'when_started': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}


def stats(xs):
    xs = sorted(xs)
    return None if not xs else {'n': len(xs), 'min': round(xs[0], 4), 'median': round(statistics.median(xs), 4), 'p95': round(xs[min(len(xs) - 1, int(0.95 * len(xs)))], 4), 'max': round(xs[-1], 4), 'sum': round(sum(xs), 2)}


def say(k, v):
    R[k] = v; print(f'--- {k}: {json.dumps(v, default=str)[:1800]}'); sys.stdout.flush(); (OUT / f'measure2_{MODE}.json').write_text(json.dumps(R, indent=1, default=str))


if MODE == 'chain':
    root = sys.argv[4]; s = deploy.Services(VT.OUT / 'CHAIN'); s.start_witness()          # the witness service alone, over the database the load was made in
    try:
        ctx = TLS.TLSClient(s.pki['ca'], *s.pki['courier']).context(); url = f"https://127.0.0.1:{s.ports['witness']}"; qr = urllib.parse.quote(root, safe='')
        with Store(os.environ['PLEA_LOCAL_DSN']).connect() as conn:
            total = conn.execute('SELECT count(*) FROM decisions WHERE root_id = %s', (root,)).fetchone()[0]
            runs = conn.execute('SELECT count(*) FROM attempts WHERE root_id = %s', (root,)).fetchone()[0]
        pages, after, t0 = [], 0, time.monotonic()
        while after < total:
            t = time.monotonic()
            with urllib.request.urlopen(urllib.request.Request(f'{url}/chain?root={qr}&after={after}&limit=200'), timeout=70, context=ctx) as resp:
                body = resp.read()
            rows = json.loads(body)['rows']; dt = time.monotonic() - t
            pages.append({'after': after, 'rows': len(rows), 'bytes': len(body), 'seconds': dt, 'last_row_bytes': len(json.dumps(rows[-1]))})
            after = rows[-1]['seq']
        say('the whole chain of one budget, read page by page (limit 200, as the courier asks)', {
            'runs in the budget': runs, 'decisions': total, 'pages': len(pages), 'seconds in all': round(time.monotonic() - t0, 2), 'bytes in all': sum(p['bytes'] for p in pages),
            'rows per page': stats([p['rows'] for p in pages]), 'bytes per page': stats([p['bytes'] for p in pages]), 'seconds per page': stats([p['seconds'] for p in pages]),
            'bytes of one decision, first page': pages[0]['last_row_bytes'], 'bytes of one decision, last page': pages[-1]['last_row_bytes'],
            'pages cut short by the witness\'s limit on a page\'s bytes': sum(1 for p in pages[:-1] if p['rows'] < 200)})
    finally:
        s.stop()
else:
    minutes = float(sys.argv[4]); WORKERS = 4
    s = deploy.Services(VT.OUT / 'LIVE').start()
    try:
        env = s.baseline(VT.CASE, VT.draft(), runs=1000); h = env['baseline_sha256']; root = VT.B.root_for(env['card'])
        cfgs = [s.client_config(VT.OUT / 'LIVE' / f'ws-{w}', h) for w in range(WORKERS)]; local = Store(os.environ['PLEA_LOCAL_DSN'])
        stop_at, lock, n_next, submits, flying = time.time() + minutes * 60, threading.Lock(), [0], [], []

        def worker(w):
            while time.time() < stop_at:
                with lock:
                    n = n_next[0]; n_next[0] += 1
                design = {'material': 'PA66-GF30' if n % 4 == 0 else 'PPS-GF40', 'wall_mm': round(2 + (n + 1) / 1000, 3), 'mode': 'normal'}
                t = time.monotonic(); code, out = s.submit(cfgs[w], design)
                with lock:
                    submits.append({'exit': code, 'seconds': time.monotonic() - t})

        done = threading.Event()

        def watch():                                           # how many runs are not in a final phase, sampled each second
            while not done.is_set():
                with local.connect() as conn:
                    flying.append(conn.execute("SELECT count(*) FROM attempts WHERE root_id = %s AND phase NOT IN ('EFFECT', 'NO_EFFECT')", (root,)).fetchone()[0])
                time.sleep(1)

        def one_pass(tag):
            cfg = s.courier_config([root], 900, 'live'); t = time.monotonic()
            p = subprocess.run([PY, '-B', str(pathlib.Path(SRC) / 'verify' / 'courier.py'), 'run', '--config', str(cfg)], capture_output=True, text=True, timeout=1500); dt = time.monotonic() - t
            try:
                sm = json.loads(p.stdout.strip().splitlines()[-1])
            except Exception:
                sm = {'error': (p.stdout + p.stderr)[-300:]}
            x = json.loads((s.dir / 'live' / 'state.json').read_text())['roots'][root]; ln, lp = x.get('lines') or {}, x.get('last_pass') or {}
            return {'when': tag, 'seconds': round(dt, 2), 'exit': p.returncode, 'ended': lp.get('ended'), 'why': lp.get('why'), 'new [length, asked, put off]': ln.get('new'), 'old [length, asked, put off]': ln.get('old'),
                    'read to decision': x.get('seq'), 'runs done': len(x.get('final') or []), 'notices made': len(sm.get('made', [])) if isinstance(sm, dict) else None,
                    'waiting': len(sm.get('waiting', [])) if isinstance(sm, dict) else None, 'unread': len(sm.get('unread', [])) if isinstance(sm, dict) else None, 'watching': bool(x.get('watching')), 'error': sm.get('error') if isinstance(sm, dict) else None}

        th = [threading.Thread(target=worker, args=(w,)) for w in range(WORKERS)]; wt = threading.Thread(target=watch); t0 = time.time()
        [t.start() for t in th]; wt.start(); passes = []
        while time.time() < stop_at:
            passes.append(one_pass(f'load running, t={time.time() - t0:.0f} s')); time.sleep(10)
        [t.join() for t in th]; done.set(); wt.join()
        for i in range(3):
            passes.append(one_pass(f'load ended, pass {i + 1}')); time.sleep(1)
        with local.connect() as conn:
            phases = conn.execute('SELECT phase, count(*) FROM attempts WHERE root_id = %s GROUP BY 1', (root,)).fetchall()
        say('load', {'minutes': minutes, 'workers': WORKERS, 'submissions': len(submits), 'per_minute': round(len(submits) / minutes, 1), 'exits': {str(c): sum(1 for x in submits if x['exit'] == c) for c in {x['exit'] for x in submits}},
                     'runs not in a final phase, sampled each second': stats(flying), 'attempts by phase at the end': phases})
        say('passes', passes)
        live = [p for p in passes if p['when'].startswith('load running')]
        say('summary', {'passes while the load ran': len(live), 'of them ended read whole with nothing put off and nothing unread': sum(1 for p in live if p['why'] == 'read whole' and p['exit'] == 0),
                        'exit statuses': sorted({p['exit'] for p in passes}), 'seconds of a pass while the load ran': stats([p['seconds'] for p in live]),
                        'runs asked for in a pass while the load ran (new + old)': stats([(p['new [length, asked, put off]'] or [0, 0, 0])[1] + (p['old [length, asked, put off]'] or [0, 0, 0])[1] for p in live]),
                        'runs put off in any pass': sum((p['new [length, asked, put off]'] or [0, 0, 0])[2] + (p['old [length, asked, put off]'] or [0, 0, 0])[2] for p in passes)})
    finally:
        s.stop()
R['when_ended'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()); (OUT / f'measure2_{MODE}.json').write_text(json.dumps(R, indent=1, default=str))
