"""Q4: the runner's planting decision at fb544a0, replayed without running any suite (body as the sixth review's q1).
EXPECTATION (written before running): 47 entries; 34 planted, 13 NOT PLANTED; the 13 are the same 13 as at c5c9832 (the sixth
review's q1_runner_count.out); the four new entries ('a job with no usable entry not revoked by name', 'the temporary file
opened by name', 'the log opened through a link or a pipe', 'a revocation neither recorded nor written not said') are planted;
every planted edit changes the file text."""
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
