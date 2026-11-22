"""P3. The console's other files in HOME/front, opened by name (N-L1 corrected only the lock).  Expectations written before running.

P3a: the adversary makes HOME/front/jobs.tmp a symbolic link to a file outside HOME (standing in for a file of the engineer's,
e.g. the key).  The console's next write (here a revoke, the database reachable).  EXPECTED: the outside file is overwritten with
the jobs.json text (Path.write_text follows the link), and os.replace then moves the link itself to jobs.json, so jobs.json is a
link to the outside file; the revocation is recorded and read back from jobs.json (the console says nothing).
P3b: HOME/front/enrolment.jsonl a link to an outside file.  EXPECTED: the binding's JSON line is appended to the outside file.
P3c: jobs.tmp a FIFO with no reader.  EXPECTED: write_text blocks (open O_WRONLY on a FIFO without a reader), with the lock held,
so the console hangs without end and a second console then gives up after LOCK_WAIT.  Run in a thread with a 3 s limit."""
import os, sys, json as _j, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa
K = Key(); out = {}
outside = R / 'outside'; outside.mkdir(exist_ok=True)
# P3a
h = home('p3a'); fr = front(h, K.public_hex); c1, e1 = enrol(h, K, 'job-t')
victim = outside / f'victim-{uuid.uuid4().hex[:6]}.key'; victim.write_text('SECRET KEY MATERIAL\n')
os.symlink(victim, h / 'front' / 'jobs.tmp')
out['p3a_revoke'] = attempt(lambda: front_ctl.revoke(h, 'job-t', K))
out['p3a_victim_now'] = victim.read_text()[:60]; out['p3a_jobs_is_link'] = os.path.islink(h / 'front' / 'jobs.json')
out['p3a_jobs_reads_revoke'] = front_door.read_jobs(h).get('job-t', {}).get('event')
# P3b
h = home('p3b'); log = outside / f'log-{uuid.uuid4().hex[:6]}.txt'; log.write_text('first line\n')
os.symlink(log, h / 'front' / 'enrolment.jsonl'); c2, e2 = enrol(h, K, 'job-u')
out['p3b_outside_lines'] = len(log.read_text().splitlines()); out['p3b_last_has_binding'] = '"job-u"' in log.read_text().splitlines()[-1]
# P3c
h = home('p3c'); c3, e3 = enrol(h, K, 'job-v'); os.mkfifo(h / 'front' / 'jobs.tmp')
res = {}
t = threading.Thread(target=lambda: res.setdefault('r', attempt(lambda: front_ctl.revoke(h, 'job-v', K))), daemon=True); t.start(); t.join(3)
out['p3c_blocked_after_3s'] = t.is_alive()
w0 = front_ctl.LOCK_WAIT; front_ctl.LOCK_WAIT = 1.0
out['p3c_second_console'] = attempt(lambda: front_ctl._write(h, dict(e3, job='job-other'), None)); front_ctl.LOCK_WAIT = w0
out['p3c_row'] = row(e3)
# free the blocked thread: open the FIFO for reading
fd = os.open(h / 'front' / 'jobs.tmp', os.O_RDONLY | os.O_NONBLOCK); time.sleep(0.5); os.close(fd); t.join(3)
out['p3c_first_result'] = res.get('r')
print(_j.dumps(out, indent=1, default=str))
ok = (out['p3a_revoke'] == ('ok', 'REVOKE') and out['p3a_victim_now'].startswith('{') and out['p3a_jobs_is_link'] is True
      and out['p3a_jobs_reads_revoke'] == 'REVOKE' and out['p3b_outside_lines'] == 2 and out['p3b_last_has_binding']
      and out['p3c_blocked_after_3s'] is True and out['p3c_second_console'][0] == 'OSError')
print('PREDICTIONS FAILED:', 'none' if ok else 'see above')
