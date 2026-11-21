"""Diagnostic, 21 November 2026: what the witness's readings and a courier's pass cost on the deployment under honest load.
Development evidence only; not a declared test.  No code of e25a297 is changed.

    DIAG_DB=<fresh database> python measure.py SRC OUT [RUNS_A RUNS_B RUNS_C WORKERS MINUTES]

SRC is a copy of the tree at e25a297.  One real deployment (deploy.Services: witness service, gate host and mailbox under
mutual TLS, PostgreSQL behind them); three budgets; honest runs made through the assistant's client, each a real check in
its sandbox; the witness read over HTTPS with the courier's certificate; the real courier run as its own process with its
default settings (waiting time 900 s, 600 s for a budget's pass, 60 s for a request).
"""
import json, os, pathlib, random, statistics, subprocess, sys, threading, time, urllib.error, urllib.parse, urllib.request

SRC, OUT = sys.argv[1], pathlib.Path(sys.argv[2]); DB = os.environ['DIAG_DB']
WANT = [int(x) for x in sys.argv[3:6]] or [600, 150, 150]; WORKERS = int(sys.argv[6]) if len(sys.argv) > 6 else 4; MINUTES = float(sys.argv[7]) if len(sys.argv) > 7 else 15
for role, pw, var in (('plea_local', 'local', 'PLEA_LOCAL_DSN'), ('plea_witness', 'witness', 'PLEA_WITNESS_DSN'), ('plea_control', 'control', 'PLEA_CONTROL_DSN')):
    os.environ[var] = f'postgresql://{role}:{pw}@127.0.0.1:5432/{DB}'
sys.path[:0] = [SRC + '/tests', SRC, SRC + '/verify']
import verify_tests as VT                                   # noqa: E402
import deploy                                               # noqa: E402
from plea_gateway import Store, tls as TLS                  # noqa: E402

R = {'when_started': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'database': DB, 'wanted_runs': WANT, 'workers': WORKERS}
PY = sys.executable


def stats(xs):
    xs = sorted(xs)
    if not xs:
        return None
    pick = lambda p: xs[min(len(xs) - 1, int(p * len(xs)))]
    return {'n': len(xs), 'min': round(xs[0], 4), 'median': round(statistics.median(xs), 4), 'p95': round(pick(0.95), 4), 'p99': round(pick(0.99), 4), 'max': round(xs[-1], 4), 'mean': round(sum(xs) / len(xs), 4)}


def say(k, v):
    R[k] = v; print(f'--- {k}: {json.dumps(v, default=str)[:1500]}'); sys.stdout.flush()
    (OUT / 'measure.json').write_text(json.dumps(R, indent=1, default=str))


s = deploy.Services(VT.OUT / 'MEASURE').start()
try:
    local = Store(os.environ['PLEA_LOCAL_DSN']); url = f"https://127.0.0.1:{s.ports['witness']}"; cour = s.pki['courier']
    ctx = TLS.TLSClient(s.pki['ca'], *cour).context()

    def get(path):                                             # one request on a connection of its own, as the courier makes them: (status, seconds, bytes)
        t = time.monotonic()
        try:
            with urllib.request.urlopen(urllib.request.Request(url + path), timeout=70, context=ctx) as resp:
                body = resp.read(); return resp.status, time.monotonic() - t, len(body), body
        except urllib.error.HTTPError as exc:
            return exc.code, time.monotonic() - t, 0, b''
        except Exception as exc:
            return type(exc).__name__, time.monotonic() - t, 0, b''

    budgets = []
    for i, want in enumerate(WANT):
        env = s.baseline(VT.CASE, VT.draft(), runs=1000, alongside_reason=None if i == 0 else 'measurement: a further budget for the same self-test requirement')
        h = env['baseline_sha256']; root = VT.B.root_for(env['card'])
        cfgs = [s.client_config(VT.OUT / 'MEASURE' / f'ws-{i}-{w}', h) for w in range(WORKERS)]
        budgets.append({'root': root, 'h': h, 'cfgs': cfgs, 'want': want, 'q': urllib.parse.quote(root, safe='')})
    say('budgets', [{'root': b['root'], 'runs_wanted': b['want']} for b in budgets])

    def aids(b):
        with local.connect() as conn:
            return [a for (a,) in conn.execute('SELECT aid FROM attempts WHERE root_id = %s', (b['root'],)).fetchall()]

    # ------------------------------------------------------------------ the load: honest runs through the client
    submits, lock, stop_at = [], threading.Lock(), time.time() + MINUTES * 60
    jobs = [(bi, n) for bi, b in enumerate(budgets) for n in range(b['want'])]
    random.Random(16).shuffle(jobs); it = iter(jobs)

    def worker(w):
        while time.time() < stop_at:
            with lock:
                job = next(it, None)
            if job is None:
                return
            bi, n = job
            design = {'material': 'PA66-GF30' if n % 4 == 0 else 'PPS-GF40', 'wall_mm': round(2 + (n + 1) / 1000, 3), 'mode': 'normal'}     # one in four fails; each design distinct
            t = time.monotonic(); code, out = s.submit(budgets[bi]['cfgs'][w], design); dt = time.monotonic() - t
            with lock:
                submits.append({'budget': bi, 'exit': code, 'seconds': dt, 'first_line': VT.head(out)[:60], 'at': time.time()})

    samples, sampling = [], threading.Event()

    def sampler():                                             # GET /run of a run already made, while the load runs
        rnd = random.Random(5)
        while not sampling.is_set():
            known = aids(budgets[0])
            if known:
                a = rnd.choice(known); st, dt, n, _ = get(f"/run?root={budgets[0]['q']}&aid={urllib.parse.quote(a, safe='')}")
                samples.append({'status': st, 'seconds': dt, 'bytes': n, 'runs_in_budget': len(known), 'at': time.time()})
            time.sleep(0.25)

    t0 = time.time(); th = [threading.Thread(target=worker, args=(w,)) for w in range(WORKERS)]; sm = threading.Thread(target=sampler)
    [t.start() for t in th]; sm.start(); [t.join() for t in th]; sampling.set(); sm.join(); load_seconds = time.time() - t0
    codes = {}
    for x in submits:
        codes[f"exit {x['exit']}: {x['first_line']}"] = codes.get(f"exit {x['exit']}: {x['first_line']}", 0) + 1
    say('load', {'seconds': round(load_seconds, 1), 'submissions': len(submits), 'per_minute': round(60 * len(submits) / load_seconds, 1), 'workers': WORKERS, 'by_outcome': codes,
                 'seconds_per_submission': stats([x['seconds'] for x in submits]), 'runs_made_per_budget': [len(aids(b)) for b in budgets]})
    ok = [x for x in samples if x['status'] == 200]
    third = max(1, len(ok) // 3)
    say('GET /run while the load runs', {'requests': len(samples), 'not 200': len(samples) - len(ok), 'seconds': stats([x['seconds'] for x in ok]), 'bytes': stats([x['bytes'] for x in ok]),
                                         'first third of the load (few runs)': {'runs_in_budget': [ok[0]['runs_in_budget'], ok[third - 1]['runs_in_budget']] if ok else None, 'seconds': stats([x['seconds'] for x in ok[:third]])},
                                         'last third of the load (most runs)': {'runs_in_budget': [ok[-third]['runs_in_budget'], ok[-1]['runs_in_budget']] if ok else None, 'seconds': stats([x['seconds'] for x in ok[-third:]])}})

    # ------------------------------------------------------------------ the witness's readings, nothing else running
    for bi, b in enumerate(budgets):
        runs = [get(f"/run?root={b['q']}&aid={urllib.parse.quote(a, safe='')}") for a in aids(b)]
        cps = [get(f"/checkpoint?root={b['q']}&nonce=m{i}") for i in range(20)]
        pages, after = [], 0
        while True:
            st, dt, n, body = get(f"/chain?root={b['q']}&after={after}&limit=200")
            rows = json.loads(body).get('rows', []) if st == 200 else []
            pages.append((dt, n, len(rows)))
            if len(rows) < 200:
                break
            after = rows[-1]['seq']
        say(f'readings, idle, budget {bi}', {'runs': len(runs), 'GET /run not 200': sum(1 for x in runs if x[0] != 200), 'GET /run seconds': stats([x[1] for x in runs]), 'GET /run bytes': stats([x[2] for x in runs]),
                                             'GET /checkpoint seconds': stats([x[1] for x in cps]), 'GET /chain pages': len(pages), 'decisions': sum(p[2] for p in pages),
                                             'GET /chain seconds per page': stats([p[0] for p in pages]), 'GET /chain bytes per page': stats([p[1] for p in pages])})

    # ------------------------------------------------------------------ the courier, as its own process, default settings
    def courier(roots, name):
        cfg = s.courier_config(roots, 900, name); t = time.monotonic()
        p = subprocess.run([PY, '-B', str(pathlib.Path(SRC) / 'verify' / 'courier.py'), 'run', '--config', str(cfg)], capture_output=True, text=True, timeout=3000)
        dt = time.monotonic() - t
        try:
            sm_ = json.loads(p.stdout.strip().splitlines()[-1])
        except Exception:
            sm_ = {'error': (p.stdout + p.stderr)[-400:]}
        st_ = json.loads((s.dir / name / 'state.json').read_text())['roots'] if (s.dir / name / 'state.json').exists() else {}
        per_root = {}
        for root_, x in st_.items():
            ln, lp = x.get('lines') or {}, x.get('last_pass') or {}
            per_root[root_[-12:]] = {'ended': lp.get('ended'), 'why': lp.get('why'), 'new line [length, asked, put off]': ln.get('new'), 'old line [length, asked, put off]': ln.get('old'), 'runs done (final)': len(x.get('final') or []),
                                     'watching': bool(x.get('watching')), 'outbox': len(x.get('outbox') or [])}
        kinds = {}
        for m in sm_.get('made', []) if isinstance(sm_, dict) else []:
            kinds[m.get('outcome')] = kinds.get(m.get('outcome'), 0) + 1
        return {'seconds': round(dt, 2), 'exit': p.returncode, 'notices_made_by_kind': kinds, 'delivered': len(sm_.get('delivered', [])) if isinstance(sm_, dict) else None,
                'put_off': sm_.get('put_off') if isinstance(sm_, dict) else None, 'error': sm_.get('error') if isinstance(sm_, dict) else None, 'budgets': per_root}

    a_root = budgets[0]['root']
    say('courier, budget 0 alone, first pass (nothing read before)', courier([a_root], 'm-one'))
    say('courier, budget 0 alone, second pass', courier([a_root], 'm-one'))
    say('courier, budget 0 alone, third pass', courier([a_root], 'm-one'))
    all_roots = [b['root'] for b in budgets]
    say('courier, three budgets in one cycle, first (nothing read before)', courier(all_roots, 'm-all'))
    say('courier, three budgets in one cycle, second', courier(all_roots, 'm-all'))
    say('courier, three budgets in one cycle, third', courier(all_roots, 'm-all'))

    # ------------------------------------------------------------------ what is left not final, and how large results are
    with local.connect() as conn:
        phases = conn.execute('SELECT phase, count(*) FROM attempts WHERE root_id = ANY(%s) GROUP BY 1 ORDER BY 1', (all_roots,)).fetchall()
        sizes = [n for (n,) in conn.execute('SELECT octet_length(result::text) FROM results WHERE root_id = ANY(%s)', (all_roots,)).fetchall()]
        rows = {t: conn.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in ('attempts', 'decisions', 'evidence', 'results')}
    say('after the load', {'attempts by phase': phases, 'stored result bytes': stats(sizes), 'rows in the database': rows})
finally:
    s.stop()
    R['when_ended'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    (OUT / 'measure.json').write_text(json.dumps(R, indent=1, default=str))
