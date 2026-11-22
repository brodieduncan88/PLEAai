"""P2e re-run.  In p2_one_engineer.py, P2d and P2e used one engineer key and the same job name ('job-c') in two homes, so both fell
on one row (key:job-c), which P2d had revoked: P2e's job was refused from the start.  That is the probe's fault (and shows the
documented sharing of rows by one engineer key across front doors).  Same case, same predicate, with a key of its own.
EXPECTED: admitted first (True); revoke raises Changed (an OSError: main prints 'refused: ...', exit 1); row (1, False); file
ENROL; the ENROL put back ADMITTED (True); the message does not mention the record."""
import os, sys, json as _j
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa
K = Key(); out = {}
h = home('p2e2'); fr = front(h, K.public_hex)
c1, ec = enrol(h, K, 'job-c'); out['admitted'] = admitted(fr, 'job-c', c1)
orig = front_ctl._record
def meddle(binding, control_dsn):
    try:
        return orig(binding, control_dsn)
    finally:
        put(h, 'job-c', dict(ec, x=1))
front_ctl._record = meddle
try:
    out['revoke'] = attempt(lambda: front_ctl.revoke(h, 'job-c', K, control_dsn=BAD))
finally:
    front_ctl._record = orig
out['row'] = row(ec); out['file_event'] = front_door.read_jobs(h)['job-c']['event']
put(h, 'job-c', ec); out['put_back'] = admitted(fr, 'job-c', c1)
print(_j.dumps(out, indent=1))
ok = (out['admitted'] is True and out['revoke'][0] == 'Changed' and out['row'] == (1, False) and out['file_event'] == 'ENROL'
      and out['put_back'] is True and 'record' not in out['revoke'][1])
print('PREDICTIONS FAILED:', 'none' if ok else 'see above')
