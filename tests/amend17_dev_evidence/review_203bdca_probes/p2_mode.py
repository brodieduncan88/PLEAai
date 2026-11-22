"""P2: _write's mode handling at 203bdca (front_ctl.py:197-215).  No database needed; bindings are made with a fresh key.

EXPECTATIONS (written before running):
P2a  No jobs.json yet: the new file is 0o644 under umask 077 and under umask 000 (fchmod ignores the umask).
P2b  jobs.json 0o640 -> 0o640 after a write.  0o600 (as fb544a0 left it) -> stays 0o600.
P2c  jobs.json 0o666 -> stays 0o666 (world-writable copied).  0o6755 (as root) -> 0o6755 (set-id bits copied; S_IMODE keeps them).
P2d  jobs.json a symlink to an outside file of mode 0o600: the new jobs.json is a plain file of mode 0o644; the outside file's
     content and mode are untouched.
P2e  jobs.json a directory: OSError; no .jobs-*.tmp left behind.
P2f  os.fchmod made to fail (monkeypatched): the OSError propagates; no .jobs-*.tmp left; jobs.json unchanged; one descriptor
     is leaked (the temporary file's, never closed: it is opened by mkstemp and only fdopen would close it).
P2g  os.stat of jobs.json made to fail with PermissionError: the same as P2f (propagates, nothing left, one descriptor leaked).
P2h  As a non-root account (nobody, in a child process): jobs.json of mode 0o000 owned by the console's account, with one entry:
     after a write of another job, jobs.json is 0o000 and holds only the new job (read_jobs turned EACCES into {}), with no
     error raised.  (Pre-existing read_jobs behaviour; the diff makes the mode persist.)
P2i  As nobody: a file planted by another account (root) at jobs.json with mode 0o044 and one entry: the first console write
     reads it (as 'other'), keeps the entry, and leaves a nobody-owned 0o044 file; the second console write cannot read its own
     file and keeps only its own job, silently.
"""
import os, stat, sys, json
from common import *  # noqa

A = Key(); out = {}
def b_for(job): return signed(A, job=job, cert_sha256='00' * 32)
def mode(p): return oct(stat.S_IMODE(os.lstat(p).st_mode))
def tmps(h): return sorted(x.name for x in (h / 'front').iterdir() if x.name.startswith('.jobs-'))
def nfds(): return len(os.listdir('/proc/self/fd'))

# P2a
for um in (0o077, 0o000):
    h = home('p2a'); old = os.umask(um)
    try:
        front_ctl._write(h, b_for('job-a'), None)
    finally:
        os.umask(old)
    out[f'p2a_umask_{oct(um)}'] = mode(front_door.jobs_path(h))
# P2b, P2c
for m in (0o640, 0o600, 0o666, 0o6755):
    h = home('p2b'); front_ctl._write(h, b_for('job-a'), None); os.chmod(front_door.jobs_path(h), m)
    front_ctl._write(h, b_for('job-b'), None); out[f'p2bc_{oct(m)}'] = mode(front_door.jobs_path(h))
# P2d
h = home('p2d'); outside = h / 'outside'; outside.write_text('KEEP\n'); os.chmod(outside, 0o600)
os.symlink(outside, front_door.jobs_path(h)); front_ctl._write(h, b_for('job-a'), None)
p = front_door.jobs_path(h); out['p2d'] = (stat.S_ISREG(os.lstat(p).st_mode), mode(p), outside.read_text(), mode(outside))
# P2e
h = home('p2e'); front_door.jobs_path(h).mkdir()
try:
    front_ctl._write(h, b_for('job-a'), None); out['p2e'] = 'written'
except OSError as exc:
    out['p2e'] = (type(exc).__name__, tmps(h))
# P2f
h = home('p2f'); front_ctl._write(h, b_for('job-a'), None); before = jobs_raw(h); real = os.fchmod; n0 = nfds()
def bad_fchmod(fd, m): raise PermissionError(1, 'fchmod refused (probe)')
os.fchmod = bad_fchmod
try:
    front_ctl._write(h, b_for('job-b'), None); out['p2f'] = 'written'
except OSError as exc:
    out['p2f'] = (type(exc).__name__, tmps(h), jobs_raw(h) == before, nfds() - n0)
finally:
    os.fchmod = real
# P2g
h = home('p2g'); front_ctl._write(h, b_for('job-a'), None); before = jobs_raw(h); real_stat = os.stat; n0 = nfds(); target = str(front_door.jobs_path(h))
def bad_stat(p, *a, **k):
    if str(p) == target and k.get('follow_symlinks') is False:
        raise PermissionError(13, 'stat refused (probe)')
    return real_stat(p, *a, **k)
os.stat = bad_stat
try:
    front_ctl._write(h, b_for('job-b'), None); out['p2g'] = 'written'
except OSError as exc:
    out['p2g'] = (type(exc).__name__, tmps(h), jobs_raw(h) == before, nfds() - n0)
finally:
    os.stat = real_stat

# P2h, P2i: moved to p2b_nocaps.py after run 1 (run 1 died: mkstemp makes the path absolute, and nobody cannot pass the
# scratchpad's 0700 ancestors; probe error, output kept in p2_mode_run1_PROBE_ERROR.out).  Expectations unchanged.

for k, v in out.items():
    print(k, '=', v)
pred = {
 'p2a': out['p2a_umask_0o77'] == '0o644' and out['p2a_umask_0o0'] == '0o644',
 'p2b': out['p2bc_0o640'] == '0o640' and out['p2bc_0o600'] == '0o600',
 'p2c': out['p2bc_0o666'] == '0o666' and out['p2bc_0o6755'] == '0o6755',
 'p2d': out['p2d'] == (True, '0o644', 'KEEP\n', '0o600'),
 'p2e': isinstance(out['p2e'], tuple) and out['p2e'][1] == [],
 'p2f': isinstance(out['p2f'], tuple) and out['p2f'][1:] == ([], True, 1),
 'p2g': isinstance(out['p2g'], tuple) and out['p2g'][1:] == ([], True, 1),
}
print('PREDICTIONS', pred); print('PREDICTIONS FAILED:', [k for k, v in pred.items() if not v])
