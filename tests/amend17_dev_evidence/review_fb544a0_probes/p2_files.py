"""P2: the console's files at fb544a0 (mkstemp, _plain), and jobs.json itself read by name.

EXPECTATIONS (written before running):
P2a  Mode of jobs.json after the console's _write: 0o600 at fb544a0 (mkstemp), 0o644 at c5c9832 (write_text under umask 022).
     Run in a child process per tree (tree/ and tree_c5/), no database needed (enrolment write, start None).
P2b  A process of another account (nobody), given the front directory by descriptor (so that the ancestors' modes do not
     matter), cannot open jobs.json written at fb544a0 (PermissionError), and can open the one written at c5c9832.
     read_jobs maps PermissionError to {} (code: front_door.py:104-110), so such a front door would admit nobody.
P2c  A FIFO put at jobs.json: the CLI revoke of an enrolled job does not finish within 10 s (TIMEOUT); its row stays (1, False):
     nothing recorded.  (No by-name fallback: _current blocks in read_jobs.)
P2d  A symlink at jobs.json to an outside file holding a valid jobs.json text: revoke (normal path) succeeds, the outside file
     is unchanged, and jobs.json is afterwards a plain file (rename replaced the link).
P2e  A symlink at jobs.json to /dev/zero, CLI revoke under RLIMIT_AS = 768 MB: it ends with MemoryError in a traceback (not a
     'refused:' line), nothing recorded (row (1, False)).
P2f  os.replace made to fail inside _write: OSError raised; no '.jobs-*.tmp' left in HOME/front; jobs.json unchanged; the log
     not appended.
P2g  enrolment.jsonl a hard link to an outside file (same account here): _write succeeds and appends the binding to the outside
     file (S_ISREG holds for a hard link).  With fs.protected_hardlinks = 1 another account could make such a link only to a
     file it owns or can read and write.
"""
import json, os, resource, subprocess, threading, time
from common import *  # noqa

out = {}
PY = sys.executable

# P2a / P2b: child per tree
child = r'''
import sys, os, json, pathlib
tree, h = sys.argv[1], pathlib.Path(sys.argv[2])
sys.path[:0] = [tree + '/verify', tree]
import front_ctl
from verify_record import Key, now
import front_door
k = Key()
b = {'event': 'ENROL', 'seq': 1, 'job': 'job-m', 'baseline_sha256': 'ab' * 32, 'root': 'budget/' + 'ab' * 16, 'cert_sha256': 'cd' * 32, 'previous': None, 'time': now(), 'note': None}
b = dict(b, signer=k.public_hex, signature=k.sign(front_door.binding_message(b)))
(h / 'front').mkdir(parents=True, exist_ok=True)
try:
    front_ctl._write(h, b, None)
except TypeError:
    front_ctl._write(h, b)
print(oct(os.stat(h / 'front' / 'jobs.json').st_mode & 0o777))
'''
modes = {}
for tag, tree in (('fb544a0', TREE), ('c5c9832', R / 'tree_c5')):
    h = home(f'p2a-{tag}')
    r = subprocess.run([PY, '-B', '-c', child, str(tree), str(h)], capture_output=True, text=True, timeout=60)
    modes[tag] = (r.stdout.strip(), r.stderr.strip()[-200:])
    # P2b: open as nobody through a directory descriptor
    dfd = os.open(h / 'front', os.O_RDONLY | os.O_DIRECTORY)
    pid = os.fork()
    if pid == 0:
        try:
            os.setgroups([]); os.setgid(65534); os.setuid(65534)
            try:
                fd = os.open('jobs.json', os.O_RDONLY, dir_fd=dfd); os.close(fd); os._exit(0)
            except PermissionError:
                os._exit(13)
        except BaseException:
            os._exit(99)
    _, st = os.waitpid(pid, 0); os.close(dfd)
    modes[tag + '_nobody_open'] = {0: 'opened', 13: 'PermissionError'}.get(os.waitstatus_to_exitcode(st), os.waitstatus_to_exitcode(st))
out['p2ab'] = modes

A = Key(); kA = keyfile(A, 'A')

# P2c FIFO at jobs.json
h = home('p2c'); der, b = enrol(h, A, 'job-c'); fr = front(h, A.public_hex); out['p2c_first'] = admitted(fr, 'job-c', der)
held = front_door.jobs_path(h).read_text(); front_door.jobs_path(h).unlink(); os.mkfifo(front_door.jobs_path(h))
out['p2c_cli'] = cli(h, kA, 'revoke', 'job-c', timeout=10)
out['p2c_row'] = row(b)
# the front door's admit, in a thread, on the same FIFO
res = {}
t = threading.Thread(target=lambda: res.setdefault('admit', admitted(fr, 'job-c', der)), daemon=True); t.start(); t.join(3)
out['p2c_admit_blocked'] = t.is_alive()
# release blocked readers: open for writing and write the honest text
if t.is_alive():
    wfd = os.open(front_door.jobs_path(h), os.O_WRONLY); os.write(wfd, held.encode()); os.close(wfd); t.join(5)
out['p2c_admit_after_release'] = res.get('admit')
os.unlink(front_door.jobs_path(h))

# P2d symlink at jobs.json to an outside file
h = home('p2d'); der, b = enrol(h, A, 'job-d'); fr = front(h, A.public_hex); admitted(fr, 'job-d', der)
outside = R / 'outside' / f'p2d-{uuid.uuid4().hex[:6]}.json'; outside.parent.mkdir(exist_ok=True)
outside.write_text(front_door.jobs_path(h).read_text()); before = outside.read_text()
front_door.jobs_path(h).unlink(); os.symlink(outside, front_door.jobs_path(h))
out['p2d_revoke'] = attempt(lambda: front_ctl.revoke(h, 'job-d', A))
out['p2d_outside_unchanged'] = outside.read_text() == before
out['p2d_jobs_is_link'] = front_door.jobs_path(h).is_symlink()
out['p2d_row'] = row(b)

# P2e symlink to /dev/zero, CLI under a memory limit
h = home('p2e'); der, b = enrol(h, A, 'job-e'); fr = front(h, A.public_hex); admitted(fr, 'job-e', der)
front_door.jobs_path(h).unlink(); os.symlink('/dev/zero', front_door.jobs_path(h))
def lim():
    resource.setrlimit(resource.RLIMIT_AS, (768 << 20, 768 << 20))
t0 = time.monotonic()
r = subprocess.run([PY, '-B', str(TREE / 'verify' / 'front_ctl.py'), 'revoke', str(h), 'job-e', '--key', str(kA)], capture_output=True, text=True, timeout=120, preexec_fn=lim)
out['p2e_cli'] = (r.returncode, round(time.monotonic() - t0, 1), r.stderr.strip()[-160:])
out['p2e_row'] = row(b)
os.unlink(front_door.jobs_path(h))

# P2f os.replace fails inside _write
h = home('p2f'); der, b = enrol(h, A, 'job-f'); start = front_door.read_jobs(h)['job-f']
before_jobs = front_door.jobs_path(h).read_text(); log = h / 'front' / 'enrolment.jsonl'; log_before = log.read_text()
real = os.replace
def boom(*a, **k):
    raise OSError('replace refused (probe)')
os.replace = boom
try:
    out['p2f_write'] = attempt(lambda: front_ctl._write(h, dict(b, seq=2), start))
finally:
    os.replace = real
out['p2f_leftover'] = sorted(p.name for p in (h / 'front').iterdir() if p.name.startswith('.jobs-'))
out['p2f_jobs_unchanged'] = front_door.jobs_path(h).read_text() == before_jobs
out['p2f_log_unchanged'] = log.read_text() == log_before

# P2g hard link at the log
h = home('p2g'); der, b = enrol(h, A, 'job-g'); start = front_door.read_jobs(h)['job-g']
hl_target = R / 'outside' / f'p2g-{uuid.uuid4().hex[:6]}.txt'; hl_target.write_text('KEEP\n')
log = h / 'front' / 'enrolment.jsonl'; log.unlink(); os.link(hl_target, log)
out['p2g_write'] = attempt(lambda: front_ctl._write(h, dict(b, seq=2), start))
out['p2g_outside_lines'] = len(hl_target.read_text().splitlines())
out['protected_hardlinks'] = open('/proc/sys/fs/protected_hardlinks').read().strip()

for k, v in out.items():
    print(k, '=', json.dumps(v, default=str))
pred = {
    'p2a': out['p2ab']['fb544a0'][0] == '0o600' and out['p2ab']['c5c9832'][0] == '0o644',
    'p2b': out['p2ab']['fb544a0_nobody_open'] == 'PermissionError' and out['p2ab']['c5c9832_nobody_open'] == 'opened',
    'p2c': out['p2c_cli'][0] == 'TIMEOUT' and out['p2c_row'] == (1, False),
    'p2d': out['p2d_revoke'] == ('ok', 'REVOKE') and out['p2d_outside_unchanged'] and out['p2d_jobs_is_link'] is False,
    'p2e': out['p2e_cli'][0] != 0 and 'MemoryError' in out['p2e_cli'][2] and 'refused:' not in out['p2e_cli'][2] and out['p2e_row'] == (1, False),
    'p2f': out['p2f_write'][0] == 'OSError' and out['p2f_leftover'] == [] and out['p2f_jobs_unchanged'] and out['p2f_log_unchanged'],
    'p2g': out['p2g_write'][0] == 'ok' and out['p2g_outside_lines'] == 2,
}
failed = [k for k, v in pred.items() if not v]
print('PREDICTIONS FAILED:' if failed else 'ALL PREDICTIONS HELD', failed)
