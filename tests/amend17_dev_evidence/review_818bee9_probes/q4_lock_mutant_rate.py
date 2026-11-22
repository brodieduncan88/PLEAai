"""Q4. How often F38 check 8 (forty threads calling front_ctl._write at once into one folder) catches the planted defect 'jobs.json
written without a lock' (fcntl.flock replaced by pass; done here by making flock a no-op in process, the same effect).

EXPECTED: with the lock, 30 of 30 trials pass check 8 (no errors, 40 kept, 40 logged).  Without it, most trials fail check 8
(lost entries, or FileNotFoundError from two threads' os.replace of the one jobs.tmp); I predict at least 25 of 30 fail, and
cannot predict that all do.  No database is used.
"""
import fcntl, json, os, shutil, sys, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa

key = Key()
_, base = enrol(None, key, 'job-base', write=False)
names = [f'job-c{n:02d}' for n in range(40)]

def trial(tag):
    scratch = R / 'homes' / f'q4-{tag}'; shutil.rmtree(scratch, ignore_errors=True); (scratch / 'front').mkdir(parents=True)
    errors = []
    def put_(n):
        try:
            front_ctl._write(scratch, dict(base, job=n))
        except Exception as exc:
            errors.append(type(exc).__name__)
    ts = [threading.Thread(target=put_, args=(n,)) for n in names]
    [t.start() for t in ts]; [t.join() for t in ts]
    kept = sorted(front_door.read_jobs(scratch)); logged = len((scratch / 'front' / 'enrolment.jsonl').read_text().splitlines())
    shutil.rmtree(scratch, ignore_errors=True)
    return (not errors and kept == names and logged == 40), len(kept), sorted(set(errors))

out = {}
res = [trial(f'locked-{i}') for i in range(30)]
out['locked_pass'] = sum(r[0] for r in res)
real = fcntl.flock; fcntl.flock = lambda *a, **k: None
try:
    res = [trial(f'unlocked-{i}') for i in range(30)]
finally:
    fcntl.flock = real
out['unlocked_pass'] = sum(r[0] for r in res); out['unlocked_fail'] = 30 - out['unlocked_pass']
out['unlocked_kept'] = [r[1] for r in res]; out['unlocked_errors'] = sorted({e for r in res for e in r[2]})
print(json.dumps(out, indent=1))
