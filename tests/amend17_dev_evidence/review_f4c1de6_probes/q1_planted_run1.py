"""Q1. Expectation written before the run: at commit f4c1de6, the mutants 'no form kept per budget' and
'a binding for another budget admitted' are NOT PLANTED (their old text was moved or rewritten by the commit); every
other text-mutant's old text occurs exactly once.  PREDICTION: exactly those two report count 0."""
import subprocess, sys, runpy, types
REPO = sys.argv[1]
src = subprocess.run(['git', '-C', REPO, 'show', 'f4c1de6:tests/amend17_mutants.py'], capture_output=True, text=True, check=True).stdout
start = src.index('MUTANTS = ['); end = src.index('\n]\n', start) + 3
ns = {}; exec(src[start:end], ns)
for name, path, old, new, tests in ns['MUTANTS']:
    edits = path if isinstance(path, list) else [(path, old, new)]
    for p, o, n in edits:
        if n is not None and n.startswith('git:'):
            print(f'{name!r}: {p}: git replacement'); continue
        text = subprocess.run(['git', '-C', REPO, 'show', f'f4c1de6:{p}'], capture_output=True, text=True, check=True).stdout
        print(f'{name!r}: {p}: count={text.count(o)}')
