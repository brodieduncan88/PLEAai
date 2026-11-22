"""Q2 (review 3, of f4c1de6).  Expectations written before the run.
S1 console given no realm (the CLI default), front door not running from the revocation to the put-back: a front door
   started after the put-back admits the revoked job.                         PREDICTION s1_admitted = True
S2 console given a realm that is not the front door's (a typo): revoke succeeds silently and records under the wrong name;
   with the front door not running until after the put-back, it admits.        PREDICTION s2_revoke_ok = True, s2_admitted = True
S3 revocation recorded under realm R1; earlier file put back; the front door restarted with another realm (R2): admits.
                                                                               PREDICTION s3_recorded = 'REVOKED', s3_admitted = True
S4 console's control DSN fails (wrong password) while the front door's database is fine: revoke is refused, jobs.json is
   unchanged, and the job (whose key leaked) is still admitted.                PREDICTION s4_refused = True, s4_file_unchanged = True, s4_admitted = True
S5 rebind: the record is written (seq 2, CURRENT), then writing jobs.json fails once.  The job's binding in force (seq 1)
   is then STALE (refused), and a retried rebind is refused CONFLICT, so the job can never be moved again.
                                                                               PREDICTION s5_after_fail_admitted = False, s5_retry = Refused containing 'CONFLICT', s5_retry2 same
S6 the console's realm is not checked against front_state.REALM: realm '' is accepted.  PREDICTION s6_ok = True
"""
import sys, json, hashlib, pathlib, tempfile, shutil
W = sys.argv[1]; sys.path.insert(0, W); sys.path.insert(0, W + '/verify')
from plea_gateway import Store
import front_door, front_state, front_ctl
from verify_record import Key
LOCAL = 'postgresql://plea_local:local@127.0.0.1:5432/plea_rv3'
CTL = 'postgresql://plea_control:control@127.0.0.1:5432/plea_rv3'
BADCTL = 'postgresql://plea_control:wrong@127.0.0.1:5432/plea_rv3'
eng = Key(); der = b'job-cert-der'; h = hashlib.sha256(b'baseline').hexdigest()
base = pathlib.Path(sys.argv[2])
def newhome():
    home = pathlib.Path(tempfile.mkdtemp(dir=base)); (home / 'front').mkdir(); return home
def enrol(home, job):
    b = {'event': 'ENROL', 'seq': 1, 'job': job, 'baseline_sha256': h, 'root': f'REQ-1/A/{h[:32]}', 'cert_sha256': hashlib.sha256(der).hexdigest(),
         'previous': None, 'time': '2026-11-22T00:00:00Z', 'note': None}
    b = dict(b, signer=eng.public_hex, signature=eng.sign(front_door.binding_message(b))); front_ctl._write(home, b); return b
def front(home, realm):
    f = front_door.Front(home, Store(LOCAL), {'tls': {}, 'journal': str(home / 'j.jsonl'), 'realm': realm}, (eng.public_hex,))
    try: f.record_revocations()          # as main() does at start
    except front_state.StateUnavailable as exc: print('start:', exc)
    return f
out = {}
R1, R2 = 'realm-one-1', 'realm-two-2'
# S1
home = newhome(); enrol(home, 'job-s1'); out['s1_first'] = front(home, R1).admit('job-s1', der) is not None
before = front_door.jobs_path(home).read_text()
front_ctl.revoke(home, 'job-s1', eng)                                   # no realm
front_door.jobs_path(home).write_text(before)                           # put back before any front door reads it
out['s1_admitted'] = front(home, R1).admit('job-s1', der) is not None
# S2
home = newhome(); enrol(home, 'job-s2'); out['s2_first'] = front(home, R1).admit('job-s2', der) is not None
before = front_door.jobs_path(home).read_text()
try: front_ctl.revoke(home, 'job-s2', eng, realm='realm-onе-1', control_dsn=CTL); out['s2_revoke_ok'] = True   # a typo (Cyrillic e)
except Exception as exc: out['s2_revoke_ok'] = repr(exc)
front_door.jobs_path(home).write_text(before)
out['s2_admitted'] = front(home, R1).admit('job-s2', der) is not None
# S3
home = newhome(); enrol(home, 'job-s3'); out['s3_first'] = front(home, R1).admit('job-s3', der) is not None
before = front_door.jobs_path(home).read_text()
front_ctl.revoke(home, 'job-s3', eng, realm=R1, control_dsn=CTL)
out['s3_recorded'] = front(home, R1).admit('job-s3', der) is None and 'REVOKED'
front_door.jobs_path(home).write_text(before)
out['s3_same_realm_admitted'] = front(home, R1).admit('job-s3', der) is not None
out['s3_admitted'] = front(home, R2).admit('job-s3', der) is not None
# S4
home = newhome(); enrol(home, 'job-s4'); out['s4_first'] = front(home, R1).admit('job-s4', der) is not None
before = front_door.jobs_path(home).read_text()
try: front_ctl.revoke(home, 'job-s4', eng, realm=R1, control_dsn=BADCTL); out['s4_refused'] = False
except front_ctl.Refused as exc: out['s4_refused'] = True; out['s4_message'] = str(exc)
out['s4_file_unchanged'] = front_door.jobs_path(home).read_text() == before
out['s4_admitted'] = front(home, R1).admit('job-s4', der) is not None
# S5
home = newhome(); enrol(home, 'job-s5'); f5 = front(home, R1); out['s5_first'] = f5.admit('job-s5', der) is not None
h2 = hashlib.sha256(b'baseline-rev').hexdigest()
front_ctl._envelope = lambda home, nh, key: {'baseline_sha256': nh, 'card': {'supersedes': {'baseline_sha256': h}}}
front_ctl._deliverable = lambda home, nh, wait: None
front_ctl.root_for = lambda card: f'REQ-1/B/{h2[:32]}'
real_write = front_ctl._write
def failing(home, b): raise OSError(28, 'No space left on device')
front_ctl._write = failing
try: front_ctl.rebind(home, 'job-s5', h2, eng, realm=R1, control_dsn=CTL); out['s5_first_rebind'] = 'ok'
except Exception as exc: out['s5_first_rebind'] = repr(exc)
front_ctl._write = real_write
out['s5_after_fail_admitted'] = f5.admit('job-s5', der) is not None
for k in ('s5_retry', 's5_retry2'):
    try: front_ctl.rebind(home, 'job-s5', h2, eng, realm=R1, control_dsn=CTL); out[k] = 'ok'
    except Exception as exc: out[k] = repr(exc)
out['s5_jobs_seq'] = front_door.read_jobs(home)['job-s5']['seq']
# S6
home = newhome(); enrol(home, 'job-s6')
try: front_ctl.revoke(home, 'job-s6', eng, realm='', control_dsn=CTL); out['s6_ok'] = True
except Exception as exc: out['s6_ok'] = repr(exc)
with Store('postgresql://plea:plea@127.0.0.1:5432/plea_rv3').connect() as c:
    out['rows'] = [list(r) for r in c.execute('SELECT job, seq, revoked FROM public.verify_front_binding ORDER BY job').fetchall()]
print(json.dumps(out, indent=1, ensure_ascii=True))
