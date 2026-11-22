"""Q4: the runner's planting decision, replayed without running any suite.
EXPECTATION (written before running): 43 entries; 30 planted, 13 NOT PLANTED; the 13 are the 8 declared NOT PLANTED at 818bee9
plus 'the record keyed by the job name alone', 'jobs.json written without a lock',
'a revocation not written when it cannot be recorded (restated)', 'the front door records no revocation at its start',
'a move not written when it cannot be recorded'.  Every planted edit actually changes the file text."""
import ast, pathlib, sys
T = pathlib.Path(sys.argv[1])
src = (T / 'tests' / 'amend17_mutants.py').read_text()
mod = ast.parse(src)
MUT = None
for node in mod.body:
    if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', None) == 'MUTANTS':
        MUT = ast.literal_eval(node.value)
planted, notp = [], []
for entry in MUT:
    name = entry[0]; path = entry[1]
    edits = path if isinstance(path, list) else [(path, entry[2], entry[3])]
    ok = True; changed = True
    for pth, o, n in edits:
        if n is not None and n.startswith('git:'):
            continue
        text = (T / pth).read_text(); c = text.count(o)
        ok = ok and c == 1
        if c == 1 and text.replace(o, n) == text: changed = False
    (planted if ok else notp).append((name, changed))
print('entries', len(MUT), 'planted', len(planted), 'not planted', len(notp))
print('NOT PLANTED:'); [print('  ', n) for n, _ in notp]
print('planted with no change:', [n for n, c in planted if not c])
print('planted:'); [print('  ', n) for n, _ in planted]
