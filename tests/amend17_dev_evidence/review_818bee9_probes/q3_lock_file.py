"""Q3. HOME/front/jobs.lock, which the D16 adversary can create, replace or hold.

Q3a (lock held by the adversary: any process that can open the file can flock it).  The engineer revokes job-p, DB reachable.
EXPECTED: the revoke has recorded (row (2, True)) and is still blocked in _write after 3 s (thread alive); the file still holds the
ENROL.  When the adversary lets go, revoke returns and writes REVOKE.

Q3b (same, DB unreachable).  EXPECTED: blocked after 3 s; nothing recorded (row (1, False)); nothing written (ENROL); no message
and no exit status reach the engineer while it waits.

Q3c (jobs.lock a FIFO).  EXPECTED: open(..., 'a') blocks: revoke blocked after 3 s (released here by opening the FIFO to read).

Q3d (jobs.lock a symlink to a path that does not exist, in a directory the console's account can write).  EXPECTED: revoke
succeeds and the target file is created (empty) by the console's open(..., 'a').
"""
import fcntl, json, os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa

key = Key(); out = {}

def revoke_in_thread(h, job, dsn):
    res = {}
    def go():
        try:
            res['ret'] = front_ctl.revoke(h, job, key, control_dsn=dsn)['event']
        except Exception as exc:
            res['ret'] = f'{type(exc).__name__}: {str(exc)[:120]}'
    t = threading.Thread(target=go, daemon=True); t.start(); return t, res

for tag, dsn in (('q3a', CONTROL), ('q3b', BAD)):
    h = home(tag); d, e = enrol(h, key, 'job-p'); fr = front(h, key); admitted(fr, 'job-p', d)
    holder = open(h / 'front' / 'jobs.lock', 'a'); fcntl.flock(holder, fcntl.LOCK_EX)    # the adversary
    t, res = revoke_in_thread(h, 'job-p', dsn); time.sleep(3)
    out[f'{tag}_blocked_after_3s'] = t.is_alive(); out[f'{tag}_row_while_blocked'] = row(e)
    out[f'{tag}_file_while_blocked'] = front_door.read_jobs(h)['job-p']['event']
    fcntl.flock(holder, fcntl.LOCK_UN); holder.close(); t.join(10)
    out[f'{tag}_after_release'] = res.get('ret'); out[f'{tag}_file_after_release'] = front_door.read_jobs(h)['job-p']['event']

h = home('q3c'); d, e = enrol(h, key, 'job-p')
lock = h / 'front' / 'jobs.lock'; lock.unlink(); os.mkfifo(lock)
t, res = revoke_in_thread(h, 'job-p', CONTROL); time.sleep(3)
out['q3c_blocked_after_3s'] = t.is_alive(); out['q3c_row_while_blocked'] = row(e)
fd = os.open(lock, os.O_RDONLY | os.O_NONBLOCK); t.join(10); os.close(fd)
out['q3c_after_release'] = res.get('ret')

h = home('q3d'); d, e = enrol(h, key, 'job-p')
target = R / 'homes' / f'q3d-target-{uuid.uuid4().hex[:6]}'
lock = h / 'front' / 'jobs.lock'; lock.unlink(); lock.symlink_to(target)
out['q3d_target_before'] = target.exists()
t, res = revoke_in_thread(h, 'job-p', CONTROL); t.join(10)
out['q3d_ret'] = res.get('ret'); out['q3d_target_created'] = target.exists(); out['q3d_target_size'] = target.stat().st_size if target.exists() else None

print(json.dumps(out, indent=1, default=str))
