"""Q6. Q1a's substitution and Q2a's re-enrolment, run against the tree of 3473478 (realm design), to see whether Q1a/Q2a are new.

At 3473478 the console names the row by the realm file and the job ARGUMENT, not by the binding it reads.  An honest realm file
throughout (the H1'' forgery is not used here).

Q6a (Q1a): jobs['job-x'] := job-y's ENROL; revoke job-x; put job-x's ENROL back.  EXPECTED: revoke records 'R:job-x' REVOKED (seq 2),
and job-x is REFUSED after the put-back (False).  So Q1a is new at 818bee9.

Q6b (Q2a): job-r enrolled C1, admitted; entry deleted; job-r enrolled again with C2.  EXPECTED: C2 REFUSED at first admission
(CONFLICT on R:job-r seq 1).  revoke job-r; put back C1's ENROL: EXPECTED REFUSED (False).  So Q2a's admission is new at 818bee9
(at 3473478 a re-used name fails closed instead).
"""
import hashlib, json, os, pathlib, shutil, sys, uuid
R = pathlib.Path('/tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad/review5')
TREE = R / 'tree_3473478'; DB = 'plea_rv5'
OWNER = f'postgresql://plea:plea@127.0.0.1:5432/{DB}'; LOCAL = f'postgresql://plea_local:local@127.0.0.1:5432/{DB}'; CONTROL = f'postgresql://plea_control:control@127.0.0.1:5432/{DB}'
os.environ['PLEA_CONTROL_DSN'] = CONTROL; os.environ['PLEA_LOCAL_DSN'] = LOCAL; os.environ['PLEA_ADMIN_DSN'] = OWNER
sys.path[:0] = [str(TREE / 'verify'), str(TREE)]
from plea_gateway import Store
import front_state, front_door, front_ctl
from verify_record import Key, now

key = Key(); out = {}; realm = 'rv5-' + uuid.uuid4().hex[:12]

def home(tag):
    h = R / 'homes' / f'{tag}-{uuid.uuid4().hex[:6]}'; (h / 'front').mkdir(parents=True); return h

def enrol(h, job):
    der = os.urandom(64)
    b = {'event': 'ENROL', 'seq': 1, 'job': job, 'baseline_sha256': 'ab' * 32, 'root': 'budget/' + 'ab' * 16,
         'cert_sha256': hashlib.sha256(der).hexdigest(), 'previous': None, 'time': now(), 'note': None}
    b = dict(b, signer=key.public_hex, signature=key.sign(front_door.binding_message(b))); front_ctl._write(h, b); return der, b

def put(h, job, b):
    p = front_door.jobs_path(h); jobs = json.loads(p.read_text())['jobs']
    if b is None: jobs.pop(job, None)
    else: jobs[job] = b
    p.write_text(json.dumps({'jobs': jobs}))

def adm(fr, job, der):
    try: return fr.admit(job, der) is not None
    except Exception as exc: return f'{type(exc).__name__}({exc})'

def rowq(name):
    with Store(OWNER).connect() as c:
        r = c.execute('SELECT seq, revoked FROM public.verify_front_binding WHERE job = %s', (name,)).fetchone(); return tuple(r) if r else None

front_state.install(Store(OWNER))        # 3473478's function (same SQL as 818bee9's; checked by diff below)
# Q6a
h = home('q6a'); dx, ex = enrol(h, 'job-x'); dy, ey = enrol(h, 'job-y')
fr = front_door.Front(h, Store(LOCAL), {'realm': realm}, [key.public_hex]); out['q6a_first_admit'] = adm(fr, 'job-x', dx)
put(h, 'job-x', ey)
try: front_ctl.revoke(h, 'job-x', key, control_dsn=CONTROL); out['q6a_revoke'] = 'returned normally'
except Exception as exc: out['q6a_revoke'] = f'{type(exc).__name__}: {exc}'
out['q6a_row'] = rowq(f'{realm}:job-x')
put(h, 'job-x', ex); fr2 = front_door.Front(h, Store(LOCAL), {'realm': realm}, [key.public_hex]); fr2.record_revocations()
out['q6a_admitted_after_put_back'] = adm(fr2, 'job-x', dx)
# Q6b
realm2 = 'rv5-' + uuid.uuid4().hex[:12]
h = home('q6b'); d1, e1 = enrol(h, 'job-r'); fr = front_door.Front(h, Store(LOCAL), {'realm': realm2}, [key.public_hex])
out['q6b_first_admit_C1'] = adm(fr, 'job-r', d1)
put(h, 'job-r', None); d2, e2 = enrol(h, 'job-r'); out['q6b_admit_C2'] = adm(fr, 'job-r', d2)
try: front_ctl.revoke(h, 'job-r', key, control_dsn=CONTROL); out['q6b_revoke'] = 'returned normally'
except Exception as exc: out['q6b_revoke'] = f'{type(exc).__name__}: {exc}'
put(h, 'job-r', e1); fr2 = front_door.Front(h, Store(LOCAL), {'realm': realm2}, [key.public_hex]); fr2.record_revocations()
out['q6b_admitted_C1_after_put_back'] = adm(fr2, 'job-r', d1)
print(json.dumps(out, indent=1, default=str))
