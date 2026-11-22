"""P3d.  As P3c (HOME/front/jobs.tmp a FIFO with no reader), with the database unreachable (N-L1's Q3b case, through jobs.tmp
instead of jobs.lock).  EXPECTED: revoke still blocked after 5 s, with no exception and no message; row unchanged (1, False); jobs.json
still holds the ENROL; the ENROL in place admits the job (True)."""
import os, sys, json as _j, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa
K = Key(); out = {}
h = home('p3d'); fr = front(h, K.public_hex); c, e = enrol(h, K, 'job-f'); admitted(fr, 'job-f', c); os.mkfifo(h / 'front' / 'jobs.tmp')
res = {}
t = threading.Thread(target=lambda: res.setdefault('r', attempt(lambda: front_ctl.revoke(h, 'job-f', K, control_dsn=BAD))), daemon=True); t.start(); t.join(5)
out['blocked_after_5s'] = t.is_alive(); out['result_so_far'] = res.get('r'); out['row'] = row(e)
out['file_event'] = front_door.read_jobs(h)['job-f']['event']; out['admitted_meanwhile'] = admitted(fr, 'job-f', c)
print(_j.dumps(out, indent=1, default=str))
ok = out['blocked_after_5s'] and out['result_so_far'] is None and out['row'] == (1, False) and out['file_event'] == 'ENROL' and out['admitted_meanwhile'] is True
print('PREDICTIONS FAILED:', 'none' if ok else 'see above')
os._exit(0)
