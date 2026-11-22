"""P2h and P2i, moved from p2_mode.py (whose run 1 died on a probe error).  Run under `setpriv --bounding-set -all --inh-caps -all`:
the console is uid 0 without CAP_DAC_OVERRIDE/CAP_DAC_READ_SEARCH/CAP_FOWNER, so file modes bind it like any account; "another
account" is uid 65534, given files by a root parent (prepared by p2b_setup in the same script before exec? no: the planted file
is made by this script with chown impossible without CAP_CHOWN, so the setup is run first, with caps, as `p2b_nocaps.py setup`).

EXPECTATIONS (written before running, the same as in p2_mode.py):
P2h  jobs.json of mode 0o000 owned by the console's account, with one entry: after a write of another job, jobs.json is 0o000 and
     holds only the new job (read_jobs turned EACCES into {}), with no error raised.
P2i  A file planted by another account (65534) at jobs.json, mode 0o044, one entry: the first console write reads it (as 'other'),
     keeps the entry, and leaves a console-owned 0o044 file; the second console write cannot read its own file and keeps only its
     own job, silently.
"""
import os, stat, sys, json, uuid
from common import *  # noqa
A = Key()
def b_for(job): return signed(A, job=job, cert_sha256='00' * 32)
def mode(p): return oct(stat.S_IMODE(os.lstat(p).st_mode))
cfg = R / 'p2b_cfg.json'
if sys.argv[1:] == ['setup']:
    hh, hi = home('p2h'), home('p2i')
    pi = front_door.jobs_path(hi); pi.write_text(json.dumps({'jobs': {'job-old': b_for('job-old')}})); os.chown(pi, 65534, 65534); os.chmod(pi, 0o044)
    cfg.write_text(json.dumps({'hh': str(hh), 'hi': str(hi)})); sys.exit(0)
c = json.loads(cfg.read_text()); hh, hi = pathlib.Path(c['hh']), pathlib.Path(c['hi'])
print('CapEff', open('/proc/self/status').read().split('CapEff:')[1].split()[0])
out = {}
front_ctl._write(hh, b_for('job-1'), None); os.chmod(front_door.jobs_path(hh), 0o000)
try:
    front_ctl._write(hh, b_for('job-2'), None); err = None
except Exception as exc:
    err = f'{type(exc).__name__}: {exc}'
os.chmod(front_door.jobs_path(hh), 0o600); out['p2h'] = (err, sorted(json.loads(front_door.jobs_path(hh).read_text())['jobs']))
pi = front_door.jobs_path(hi)
try:
    front_ctl._write(hi, b_for('job-new1'), None); e1 = None
except Exception as exc:
    e1 = f'{type(exc).__name__}: {exc}'
m1, own1 = mode(pi), os.lstat(pi).st_uid
os.chmod(pi, 0o644); kept1 = sorted(json.loads(pi.read_text())['jobs']); os.chmod(pi, 0o044)
try:
    front_ctl._write(hi, b_for('job-new2'), None); e2 = None
except Exception as exc:
    e2 = f'{type(exc).__name__}: {exc}'
m2 = mode(pi); os.chmod(pi, 0o644); kept2 = sorted(json.loads(pi.read_text())['jobs'])
out['p2i'] = (e1, m1, own1, kept1, e2, m2, kept2)
for k, v in out.items():
    print(k, '=', v)
pred = {'p2h': out['p2h'] == (None, ['job-2']),
        'p2i': out['p2i'] == (None, '0o44', 0, ['job-new1', 'job-old'], None, '0o44', ['job-new2'])}
print('PREDICTIONS', pred); print('PREDICTIONS FAILED:', [k for k, v in pred.items() if not v])
