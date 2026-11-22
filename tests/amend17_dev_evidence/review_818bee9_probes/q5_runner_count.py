"""Q5. The planted-defect runner's 34 entries against the tree of 818bee9, with the runner's own rule (each edit's text found
exactly once; a 'git:' entry counts as planted).  Nothing is run through the suites.

EXPECTED (entry 15): 34 entries; 26 planted, 8 not planted.  The 8 I expect not planted: 'no form kept per budget', 'a binding for
another budget admitted', 'revocations recorded only when the job calls', 'realm from the authority's file', 'a binding for another
budget admitted (restated)', 'the console does not read the front door's realm', 'the front door started under another realm',
'a revocation not written when it cannot be recorded'.
"""
import ast, json, pathlib
TREE = pathlib.Path('/tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad/review5/tree')
src = (TREE / 'tests' / 'amend17_mutants.py').read_text()
mod = ast.parse(src)
node = next(n for n in mod.body if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'MUTANTS')
MUTANTS = ast.literal_eval(node.value)
res = {}
for entry in MUTANTS:
    name, path = entry[0], entry[1]
    edits = path if isinstance(path, list) else [(path, entry[2], entry[3])]
    planted, counts = True, []
    for pth, o, n in edits:
        if n is not None and n.startswith('git:'):
            counts.append('git'); continue
        c = (TREE / pth).read_text().count(o); counts.append(c); planted = planted and c == 1
    res[name] = {'planted': planted, 'counts': counts, 'tests': entry[-1]}
print(json.dumps({'of': len(res), 'planted': sum(r['planted'] for r in res.values()),
                  'not_planted': [n for n, r in res.items() if not r['planted']], 'entries': res}, indent=1))
