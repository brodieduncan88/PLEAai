"""Probe C: the three Amendment 18 entries of tests/amend17_mutants.py, planted as the runner plants them (text.count(o) == 1,
then text.replace(o, n)) in copies of the 8c4762f tree, and F39's first two checks recomputed against each (the in-process
check exactly as F39 computes it; the process check with F39's predicate but --port 0, a closed-port DSN and missing TLS files,
so the 'binds no port' part is not exercised here).  Also the unmutated tree as a control.

EXPECTATION (written before running):
- each of the three search texts occurs exactly once in verify/front_door.py at 8c4762f -> planted; each mutated file compiles.
- control: check 1 True, check 2 True.
- 'more than one engineer key accepted': check 1 False (two / same twice are made, engineer_keys != (k,)); check 2 False
  (two keys get past the check; with these fake paths it fails later with a traceback rather than 'not started').
- 'an engineer key of another form accepted': check 1 False (upper case and short are made); check 2 False for 'upper case'.
- "the front door's start does not check its keys": check 1 True (Front.__init__ still refuses); check 2 False only because
  Front.__init__'s EngineerKeys escapes main() as a Traceback (exit 1, 'not started' in stderr, but 'Traceback' too).
  So F39 catches this third defect only through its "'Traceback' not in err" clause.
- In all three, HOME/front is not created by the refused in-process cases.
"""
import ast, pathlib, shutil, subprocess, sys, tempfile, importlib, json
HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / 'src'
ns = {}
runner = (SRC / 'tests' / 'amend17_mutants.py').read_text()
mut_src = runner[runner.index('MUTANTS = ['):runner.index(']\n\n\ndef tree')] + ']'
exec(mut_src, ns)
entries = [m for m in ns['MUTANTS'] if m[-1] == ['F39']]
assert len(entries) == 3, entries
print('order check: last four entries:', [m[0] for m in ns['MUTANTS'][-4:]])

CHILD = r'''
import pathlib, sys, json, subprocess, tempfile, shutil
root = pathlib.Path(sys.argv[1]); sys.path[:0] = [str(root / 'verify'), str(root)]
import front_door
from plea_gateway import Store
from verify_record import Key
k = Key().public_hex; other = Key()
cases = {'one': (k,), 'none': (), 'two': (k, other.public_hex), 'the same twice': (k, k), 'upper case': (k.upper(),), 'short': (k[:63],), 'not text': (None,)}
made = {}; dirs = {}
for label, keys in cases.items():
    home = pathlib.Path(tempfile.mkdtemp(dir=sys.argv[2]))
    try:
        door = front_door.Front(home, Store('postgresql://x:y@127.0.0.1:1/none'), {'journal': str(home / 'j')}, keys); made[label] = ('made', door.engineer_keys == (k,))
    except front_door.EngineerKeys as exc:
        made[label] = ('refused', 'not started' in str(exc))
    dirs[label] = (home / 'front').exists(); shutil.rmtree(home)
check1 = made.get('one') == ('made', True) and len(made) == 7 and all(v == ('refused', True) for kk, v in made.items() if kk != 'one')
base = ['--port', '0', '--local-dsn', 'postgresql://x:y@127.0.0.1:1/none', '--witness-url', 'https://127.0.0.1:1', '--witness-key', other.public_hex,
        '--gate-host', 'https://127.0.0.1:1', '--gate-key', other.public_hex, '--tls-cert', '/nonexistent/c', '--tls-key', '/nonexistent/k',
        '--tls-ca', '/nonexistent/ca', '--upstream-cert', '/nonexistent/uc', '--upstream-key', '/nonexistent/uk']
started = {}
for label, keys in (('none', ()), ('two', (k, other.public_hex)), ('the same twice', (k, k)), ('upper case', (k.upper(),))):
    home = pathlib.Path(tempfile.mkdtemp(dir=sys.argv[2]))
    args = [a for key in keys for a in ('--engineer-key', key)]
    try:
        run = subprocess.run([sys.executable, '-B', str(root / 'verify' / 'front_door.py'), '--home', str(home)] + base + args, capture_output=True, text=True, timeout=20)
        code, err = run.returncode, run.stderr
    except subprocess.TimeoutExpired:
        code, err = 'still running', ''
    started[label] = (code, ('required' in err) if label == 'none' else ('not started' in err and 'Traceback' not in err), 'Traceback' in err, 'not started' in err)
    shutil.rmtree(home)
check2 = len(started) == 4 and started['none'][0] == 2 and started['none'][1] and all(v[0] == 1 and v[1] for kk, v in started.items() if kk != 'none')
print(json.dumps({'made': made, 'front_dir_created': dirs, 'started': started, 'check1': check1, 'check2_without_port': check2}))
'''
work = pathlib.Path(tempfile.mkdtemp(prefix='pc_', dir=HERE))
(work / 'child.py').write_text(CHILD)
for name, o, n in [('CONTROL (unmutated)', None, None)] + [(m[0], m[2], m[3]) for m in entries]:
    dest = work / 'tree'
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(SRC, dest)
    f = dest / 'verify' / 'front_door.py'
    if o is not None:
        text = f.read_text(); count = text.count(o)
        f.write_text(text.replace(o, n))
        try:
            ast.parse(f.read_text()); compiles = True
        except SyntaxError as exc:
            compiles = f'SyntaxError {exc}'
        print(f'\n== {name}: count={count} planted={count == 1} compiles={compiles}')
        if count != 1:
            continue
    else:
        print(f'\n== {name}')
    tmp = work / 'homes'; tmp.mkdir(exist_ok=True)
    r = subprocess.run([sys.executable, '-B', str(work / 'child.py'), str(dest), str(tmp)], capture_output=True, text=True, timeout=300)
    print(r.stdout.strip() or r.stderr[-2000:])
shutil.rmtree(work)
