"""Probe E: do the 51 earlier entries' search texts plant the same way at 8c4762f as at ba82e66 / 203bdca?

EXPECTATION (written before running): for every earlier entry, in every file it edits, text.count(o) is the same at 203bdca,
ba82e66 and 8c4762f (the diff touches front_door.py only around Front.__init__'s first line, the --engineer-key option and
main()'s parse_args, which no earlier search text names).  Entries using 'git:' replacements are skipped.
"""
import subprocess, sys
WT = sys.argv[1]
def show(rev, path):
    r = subprocess.run(['git', '-C', WT, 'show', f'{rev}:{path}'], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None
src = show('8c4762f', 'tests/amend17_mutants.py'); ns = {}
exec(src[src.index('MUTANTS = ['):src.index(']\n\n\ndef tree')] + ']', ns)
diff = 0
for m in ns['MUTANTS'][:-4] + ns['MUTANTS'][-1:]:
    edits = m[1] if isinstance(m[1], list) else [(m[1], m[2], m[3])]
    for p, o, n in edits:
        if n is not None and n.startswith('git:'):
            continue
        c = [ (show(rev, p) or '').count(o) for rev in ('203bdca', 'ba82e66', '8c4762f')]
        if len(set(c)) != 1:
            diff += 1; print('DIFFERS', m[0], p, c)
print('entries', len(ns['MUTANTS']), 'checked (excluding the three new ones)', len(ns['MUTANTS']) - 3, 'differing edits', diff)
