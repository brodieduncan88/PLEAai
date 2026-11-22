"""Q1. Expectation (written before running): replaying the runner's planting test (text.count(old) == 1 for every edit, files
read from the archived 203bdca tree, 'git:' replacements counted as planted) gives 51 entries, 37 planted, 14 NOT PLANTED;
the 14 are the 13 NOT PLANTED at fb544a0 plus 'a job with no usable entry not revoked by name' (the sixth review's entry);
the four entries added after the seventh review are each planted (count exactly 1)."""
import ast, pathlib, sys, subprocess
tree = pathlib.Path(sys.argv[1]); src = (tree / 'tests' / 'amend17_mutants.py').read_text()
mod = ast.parse(src)
MUTANTS = next(ast.literal_eval(n.value) for n in mod.body if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'MUTANTS')
notp = []
for e in MUTANTS:
    name, path = e[0], e[1]
    edits = path if isinstance(path, list) else [(path, e[2], e[3])]
    planted = True; counts = []
    for pth, o, n in edits:
        if n is not None and n.startswith('git:'):
            counts.append('git'); continue
        c = (tree / pth).read_text().count(o); counts.append(c); planted = planted and c == 1
    if not planted: notp.append(name)
    print(('PLANTED    ' if planted else 'NOT PLANTED'), counts, name)
print('total', len(MUTANTS), 'planted', len(MUTANTS) - len(notp), 'not planted', len(notp))
