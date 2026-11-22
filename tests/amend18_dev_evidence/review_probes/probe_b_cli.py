"""Probe B: front_door.py started as a process (8c4762f) with various --engineer-key arguments.  --port 0 always (never 8970-8979);
the DSN points at a closed port; TLS paths do not exist.

EXPECTATION (written before running):
- no --engineer-key: exit 2, argparse 'required' message, nothing created in HOME.
- twice the same, two different, one upper-case, one with a leading space, empty string (--engineer-key=), one with a comma
  joining two keys, an abbreviated second option (--engineer k2, argparse allow_abbrev): exit 1, stderr
  'front door: not started: ...', no Traceback, HOME/front not created, and the process exits in well under a second or two.
- exactly one valid key: gets past the key check (HOME/front created), then fails later on the DSN or the missing TLS files,
  with some other message or a traceback; this shows the check is the first thing after argument parsing.
"""
import pathlib, subprocess, sys, tempfile, shutil, time
HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / 'src'
sys.path[:0] = [str(SRC / 'verify'), str(SRC)]
from verify_record import Key
k = Key().public_hex; other = Key().public_hex
base_args = ['--port', '0', '--local-dsn', 'postgresql://x:y@127.0.0.1:1/none', '--witness-url', 'https://127.0.0.1:1', '--witness-key', other,
             '--gate-host', 'https://127.0.0.1:1', '--gate-key', other, '--tls-cert', '/nonexistent/c', '--tls-key', '/nonexistent/k',
             '--tls-ca', '/nonexistent/ca', '--upstream-cert', '/nonexistent/uc', '--upstream-key', '/nonexistent/uk']
cases = {'none': [], 'same twice': ['--engineer-key', k, '--engineer-key', k], 'two': ['--engineer-key', k, '--engineer-key', other],
         'upper': ['--engineer-key', k.upper()], 'leading space': ['--engineer-key', ' ' + k], 'empty': ['--engineer-key='],
         'comma-joined': ['--engineer-key', k + ',' + other], 'abbreviated second': ['--engineer-key', k, '--engineer', other],
         'one valid': ['--engineer-key', k]}
for label, extra in cases.items():
    home = pathlib.Path(tempfile.mkdtemp(prefix='pb_', dir=HERE))
    t0 = time.time()
    try:
        run = subprocess.run([sys.executable, '-B', str(SRC / 'verify' / 'front_door.py'), '--home', str(home)] + base_args + extra,
                             capture_output=True, text=True, timeout=20)
        code, err = run.returncode, run.stderr.strip().splitlines()
    except subprocess.TimeoutExpired:
        code, err = 'TIMEOUT', []
    dt = time.time() - t0
    tb = any('Traceback' in l for l in err)
    print(f'{label:20s} exit={code!s:7s} {dt:4.1f}s front_dir={(home / "front").exists()!s:5s} traceback={tb!s:5s} last={err[-1][:150] if err else ""}')
    shutil.rmtree(home)
