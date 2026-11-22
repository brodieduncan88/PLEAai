"""P3: the console's `jobs` listing (L-3's signer column) at fb544a0.
EXPECTATION (before running): (a) an entry whose signature is spoiled, but whose signer field is the engineer's key, is listed
with 'signer <engineer key prefix>' exactly like an honest one: the listing does not check binding_valid.  (b) an entry that is
not an object (a string) makes `jobs` end with an AttributeError traceback (exit 1, no 'refused:' line), so no job is listed;
this predates the commit (the line's b.get('event') was there before)."""
import json
from common import *  # noqa
A = Key()
h = home('p3'); der, b = enrol(h, A, 'job-ok'); der2, b2 = enrol(h, A, 'job-sp')
put(h, 'job-sp', dict(b2, note='changed after it was signed'))
import subprocess
r = subprocess.run([sys.executable, '-B', str(TREE / 'verify' / 'front_ctl.py'), 'jobs', str(h)], capture_output=True, text=True, timeout=60)
lines = r.stdout.splitlines(); print('a_listing =', json.dumps(lines))
print('a_valid_sp =', front_door.binding_valid(front_door.read_jobs(h)['job-sp'], (A.public_hex,)))
put(h, 'job-str', 'not an object')
r2 = subprocess.run([sys.executable, '-B', str(TREE / 'verify' / 'front_ctl.py'), 'jobs', str(h)], capture_output=True, text=True, timeout=60)
print('b_listing =', json.dumps((r2.returncode, r2.stdout, r2.stderr.strip()[-120:])))
ok_a = any(l.startswith('job-sp ') and ('signer ' + A.public_hex[:16]) in l for l in lines)
ok_b = r2.returncode == 1 and 'AttributeError' in r2.stderr and 'refused:' not in r2.stderr and r2.stdout == ''
print('ALL PREDICTIONS HELD' if ok_a and ok_b else 'PREDICTIONS FAILED', ok_a, ok_b)
