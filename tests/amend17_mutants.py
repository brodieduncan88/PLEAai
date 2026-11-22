#!/usr/bin/env python3
"""Planted defects for Amendment 17 (22 November 2026), development only.  Each removes or weakens one rule of the amendment, in
a copy of the tree made from a commit, and runs the tests that should catch it.  A defect is caught when one of those tests
fails.  Nothing in the branch is changed.

    amend17_mutants.py COMMIT WORKDIR PYTHON OUT.json [NAME ...]
"""
import json, pathlib, shutil, subprocess, sys, time

COMMIT, WORK, PY, OUT = sys.argv[1], pathlib.Path(sys.argv[2]), sys.argv[3], pathlib.Path(sys.argv[4])
ONLY = set(sys.argv[5:])
REPO = pathlib.Path(__file__).resolve().parent.parent

MUTANTS = [
    ('binder removed', 'verify/verify_tools.py', "               verify, bound),", "               verify),", ['R30']),
    ('binder always binds', 'verify/verify_tools.py', "    return root.rsplit('/', 1)[1] == h[:32]", "    return True", ['R30']),
    ('identity back to 64 bits', 'plea_gateway/governor.py', "return 'a-' + h[:16] if legacy else 'a2-' + h\n", "return 'a-' + h[:16] if legacy else 'a2-' + h[:16]\n", ['R31']),
    ('request key back to 96 bits', 'verify/verify_record.py', "return f'{TOOL}:' + (h[:24] if legacy else h)", "return f'{TOOL}:' + (h[:24] if legacy else h[:24])", ['R31']),
    ('front door does not check the design of a verdict', 'verify/front_door.py', "        if verdict.get('design_sha256') != design_hash(design):", "        if False:", ['R31']),
    ('checker allows mixed forms', 'verify/check_record.py', "    if ident is None:\n        bad(5,", "    if False:\n        bad(5,", ['R31']),
    ('no form kept per budget', 'plea_gateway/governor.py', "    return 'legacy' if any(LEGACY_AID.fullmatch(str(a[0])) for a in obs.get('attempts', ())) else 'current'", "    return 'current'", ['R33']),
    ('front door ignores the budget\'s form', 'verify/front_door.py', "        key = request_key(args, legacy=legacy)", "        key = request_key(args)", ['R33']),
    ('record of bindings not consulted', 'verify/front_door.py', "        if answer != 'CURRENT' or b['cert_sha256']", "        if b['cert_sha256']", ['F37']),
    ('revocation not absorbing', 'verify/front_state.py', "    IF r.revoked THEN\n        RETURN 'REVOKED';", "    IF false THEN\n        RETURN 'REVOKED';", ['F37']),
    ('a stale binding accepted', 'verify/front_state.py', "    IF p_seq < r.seq THEN\n        RETURN 'STALE';", "    IF false THEN\n        RETURN 'STALE';", ['F37']),
    ('a binding for another budget admitted', 'verify/front_door.py', "        if b['root'].rsplit('/', 1)[-1] != b['baseline_sha256'][:32] or '/' not in b['root']:", "        if False:", ['F37']),
    ('controls not put to the checker', 'verify/verify_ctl.py', "    problems = check_record.control_problems(card, controls_run)", "    problems = []", ['R32']),
    ('the first client not retired', 'verify/verify_client.py', None, 'git:1b132e2:verify/verify_client.py', ['R34']),
]


def tree(dest):
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    arc = subprocess.run(['git', '-C', str(REPO), 'archive', COMMIT], capture_output=True, check=True).stdout
    subprocess.run(['tar', 'xf', '-', '-C', str(dest)], input=arc, check=True)


results = {}
for name, path, old, new, tests in MUTANTS:
    if ONLY and name not in ONLY:
        continue
    dest = WORK / 'tree'; tree(dest); f = dest / path
    if new.startswith('git:'):
        _, rev, src = new.split(':', 2)
        f.write_bytes(subprocess.run(['git', '-C', str(REPO), 'show', f'{rev}:{src}'], capture_output=True, check=True).stdout); planted = True
    else:
        text = f.read_text(); planted = text.count(old) == 1
        f.write_text(text.replace(old, new))
    if not planted:
        results[name] = {'planted': False, 'caught': None}; print(f'{name}: NOT PLANTED (the text was not found once)', flush=True); continue
    got = {}
    for t in tests:
        suite = 'verify_front_tests.py' if t.startswith('F') else 'verify_tests.py'
        t0 = time.time()
        run = subprocess.run([PY, '-B', suite, t], cwd=dest / 'tests', capture_output=True, text=True, timeout=1800)
        out = json.loads((dest / 'outputs' / ('verify_front_tests.json' if t.startswith('F') else 'verify_tests.json')).read_text()) if run.returncode in (0, 1) else {}
        res = (out.get('tests') or {}).get(t, {})
        got[t] = {'ok': res.get('ok'), 'failed_checks': [k for k, v in (res.get('checks') or {}).items() if not v], 'error': res.get('error'), 'seconds': round(time.time() - t0, 1)}
    caught = any(v['ok'] is False for v in got.values())
    results[name] = {'planted': True, 'file': path, 'tests': got, 'caught': caught}
    print(f"{name}: {'CAUGHT' if caught else 'NOT CAUGHT'} by {tests}", flush=True)
OUT.write_text(json.dumps({'commit': COMMIT, 'results': results, 'caught': sum(1 for r in results.values() if r.get('caught')), 'of': len(results)}, indent=1) + '\n')
print(f"caught {sum(1 for r in results.values() if r.get('caught'))} of {len(results)}")
