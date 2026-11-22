"""Probe D: what a front door started with a different engineer key does with the earlier key's entries (README_FRONT.md's
statement on rotation).  In process, no database: the Store's DSN is a closed port.

EXPECTATION (written before running):
- jobs.json holds job-a (ENROL, signed by A) and job-r (REVOKE, signed by A).
- A front door pinned to B: usable() is False for both; admit('job-a', any der) is None without touching the database;
  record_revocations() returns 0 without touching the database, i.e. A's revocation of job-r is never put to the record by a
  front door pinned to B, at its start or on its look.
- A front door pinned to A: usable() True for both; record_revocations() tries the database (raises, since the DSN is closed).
- So the README's "its jobs are refused" is right, and an A-revocation that the console could not record stays unrecorded for
  as long as B is pinned (it matters only if A is pinned again).
"""
import json, pathlib, sys, tempfile, shutil, hashlib
SRC = pathlib.Path(__file__).resolve().parent / 'src'
sys.path[:0] = [str(SRC / 'verify'), str(SRC)]
import front_door
from plea_gateway import Store
from verify_record import Key

A, B = Key(), Key()
def signed(event, job, seq):
    h = hashlib.sha256(job.encode()).hexdigest()
    b = {'event': event, 'seq': seq, 'job': job, 'baseline_sha256': h, 'root': f'r/{h[:32]}', 'cert_sha256': hashlib.sha256(b'c').hexdigest(),
         'previous': None, 'time': '2026-11-22T00:00:00Z', 'note': None}
    return dict(b, signer=A.public_hex, signature=A.sign(front_door.binding_message(b)))
home = pathlib.Path(tempfile.mkdtemp(prefix='pd_', dir=pathlib.Path(__file__).parent))
(home / 'front').mkdir()
jobs = {'job-a': signed('ENROL', 'job-a', 1), 'job-r': signed('REVOKE', 'job-r', 2)}
front_door.jobs_path(home).write_text(json.dumps({'jobs': jobs}))
store = Store('postgresql://x:y@127.0.0.1:1/none')
for who, key in (('pinned B', B), ('pinned A', A)):
    door = front_door.Front(home, store, {'journal': str(home / 'j')}, (key.public_hex,))
    u = {n: door.usable(n, b) for n, b in jobs.items()}
    try:
        adm = door.admit('job-a', b'c')
    except Exception as exc:
        adm = f'raised {type(exc).__name__}'
    try:
        rr = door.record_revocations()
    except Exception as exc:
        rr = f'raised {type(exc).__name__}'
    print(f'{who}: usable={u} admit(job-a)={adm!r:.40} record_revocations={rr}')
shutil.rmtree(home)
