"""Q1. The console names the row by the binding it reads from jobs.json, which the D16 adversary writes.  _current() checks only
that the entry is signed by the engineer, not that its `job` is the job asked for, nor that it is that job's current enrolment.

Setting: job-x (cert Cx) and job-y (cert Cy), both enrolled in one HOME by one engineer key; the front door has admitted job-x
(record: Cx:job-x seq 1).  The database is reachable throughout.

Q1a (fresh revoke, another job's binding put in place).  The adversary sets jobs['job-x'] := job-y's ENROL.  The engineer runs
revoke job-x.  EXPECTED: revoke returns normally (no Unrecorded, no Refused: CLI exit 0); the REVOKE it signs has job 'job-x' and
cert_sha256 = Cy, so it is recorded under 'Cy:job-x'; the row Cx:job-x stays (1, False).  The adversary puts job-x's ENROL back.
EXPECTED: a front door (record_revocations first, as at start) ADMITS job-x with its certificate Cx: True.

Q1b (re-record branch, another job's REVOKE put in place).  job-z is enrolled and properly revoked first (any earlier
revocation by this engineer serves).  job-w (cert Cw) is enrolled and admitted.  The adversary sets jobs['job-w'] := job-z's
REVOKE.  The engineer runs the CLI `front_ctl.py revoke HOME job-w`.  EXPECTED: exit status 0; stdout JSON shows event REVOKE with
job 'job-z'; nothing is written for job-w; Cw:job-w stays (1, False).  The adversary puts job-w's ENROL back.  EXPECTED: job-w
ADMITTED: True.

Q1c (control: honest file).  job-v enrolled, admitted, revoked with an honest file; ENROL put back.  EXPECTED: refused (False).
"""
import contextlib, io, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa

key = Key(); out = {}
keyfile = R / 'homes' / f'engineer-{uuid.uuid4().hex[:6]}.key'; keyfile.parent.mkdir(parents=True, exist_ok=True); keyfile.write_text(key.private_hex + '\n')

# Q1a
h = home('q1a'); dx, ex = enrol(h, key, 'job-x'); dy, ey = enrol(h, key, 'job-y')
fr = front(h, key); out['q1a_first_admit_x'] = admitted(fr, 'job-x', dx)
put(h, 'job-x', ey)                                                     # the adversary
try:
    rb = front_ctl.revoke(h, 'job-x', key, control_dsn=CONTROL); out['q1a_revoke'] = 'returned normally (exit 0)'
    out['q1a_revoke_binding'] = {k: rb[k] for k in ('event', 'seq', 'job')} | {'cert_is_Cy': rb['cert_sha256'] == ey['cert_sha256']}
except Exception as exc:
    out['q1a_revoke'] = f'{type(exc).__name__}: {exc}'
out['q1a_rows_job_x'] = [(j[:8] + '…' + j[64:], s, r) for j, s, r in rows_for('job-x')]
out['q1a_row_Cx_job_x'] = row(ex)
put(h, 'job-x', ex)                                                     # the adversary puts job-x's ENROL back
fr2 = front(h, key); fr2.record_revocations()
out['q1a_admitted_after_put_back'] = admitted(fr2, 'job-x', dx)

# Q1b
h = home('q1b'); dz, ez = enrol(h, key, 'job-z'); dw, ew = enrol(h, key, 'job-w')
rz = front_ctl.revoke(h, 'job-z', key, control_dsn=CONTROL)            # an honest earlier revocation
fr = front(h, key); out['q1b_first_admit_w'] = admitted(fr, 'job-w', dw)
put(h, 'job-w', rz)                                                     # the adversary
argv, sys.argv = sys.argv, ['front_ctl.py', 'revoke', str(h), 'job-w', '--key', str(keyfile)]
so, se = io.StringIO(), io.StringIO(); code = 0
with contextlib.redirect_stdout(so), contextlib.redirect_stderr(se):
    try:
        front_ctl.main()
    except SystemExit as exc:
        code = exc.code
sys.argv = argv
out['q1b_cli'] = {'exit': code, 'stdout': so.getvalue().strip(), 'stderr': se.getvalue().strip()}
out['q1b_file_entry_w'] = {k: json.loads(front_door.jobs_path(h).read_text())['jobs']['job-w'][k] for k in ('event', 'job')}
out['q1b_row_Cw_job_w'] = row(ew)
put(h, 'job-w', ew)                                                     # the adversary puts job-w's ENROL back
fr2 = front(h, key); fr2.record_revocations()
out['q1b_admitted_after_put_back'] = admitted(fr2, 'job-w', dw)

# Q1c
h = home('q1c'); dv, ev = enrol(h, key, 'job-v')
fr = front(h, key); out['q1c_first_admit'] = admitted(fr, 'job-v', dv)
front_ctl.revoke(h, 'job-v', key, control_dsn=CONTROL)
put(h, 'job-v', ev); fr2 = front(h, key); fr2.record_revocations()
out['q1c_admitted_after_put_back'] = admitted(fr2, 'job-v', dv)

print(json.dumps(out, indent=1))
