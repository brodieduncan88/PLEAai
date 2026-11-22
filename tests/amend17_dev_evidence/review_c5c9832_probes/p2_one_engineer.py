"""P2. One engineer: the N-M1 correction, the M1 re-record path, the Changed and lock paths, and CAP-DB on predictable names.
Expectations written before running.

P2a (N-M1, first enrolment moved to seq 2 before the re-enrolment).  job-r enrolled (R1), admitted, rebound (REBIND seq 2
recorded), admitted.  Entry deleted; job-r enrolled again (R2, ENROL seq 1): EXPECTED R2 refused (STALE).  Revoke job-r (cur = R2's
ENROL, REVOKE seq 2): EXPECTED ok, row (2, True).  R1's REBIND put back: EXPECTED refused.  R1's ENROL put back: refused.

P2b (first enrolment never seen by the record).  job-q enrolled (Q1), never admitted (no row).  Entry deleted; job-q enrolled
again (Q2), admitted (row (1, False)).  Q1's ENROL put back: EXPECTED refused (CONFLICT).  Revoke with Q2's entry: ok.  Q1 put
back: refused (REVOKED).

P2c (the M1 re-record path, an earlier enrolment's REVOKE of the same name).  job-p enrolled (P1) and revoked (REVOKE seq 2).
Entry deleted; job-p enrolled again (P2) (refused at admit: REVOKED).  The adversary puts P1's REVOKE in the entry, and the
engineer runs revoke job-p: EXPECTED returns the REVOKE (re-recorded on the same row), row stays revoked; P2 and P1 refused.

P2d (Changed during revoke, the database reachable).  job-c enrolled, admitted.  _record is wrapped so that, after it returns, the
adversary rewrites job-c's entry (a copy of it with a changed note field is not signable; it writes the same ENROL with an extra
key 'x').  EXPECTED Unwritten (recorded, not written), row (2, True), the ENROL put back refused.

P2e (Changed during revoke, the database unreachable).  As P2d with control_dsn = BAD.  EXPECTED Changed (an OSError) is raised
(main prints 'refused: ...' and exits 1), nothing recorded (no row change), nothing written; the ENROL put back ADMITTED (True).
The message says nothing was written; EXPECTED it does not say that nothing was recorded either (it names only jobs.json).

P2f (lock held by the adversary, the database unreachable).  LOCK_WAIT set to 1 s.  EXPECTED OSError 'held by another process';
nothing recorded or written; put back ADMITTED.  With the database reachable: EXPECTED Unwritten; row revoked.

P2g (CAP-DB on a predictable name).  Before job-n is enrolled, plea_local calls the function for '<engineer key>:job-n', seq 1, a
made-up digest, not revoked.  Then job-n is enrolled and calls: EXPECTED refused (CONFLICT): a denial, not an admission.
"""
import os, sys, json as _j, fcntl
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa

out = {}; K = Key()
# P2a
h = home('p2a'); fr = front(h, K.public_hex)
r1, er1 = enrol(h, K, 'job-r'); out['p2a_R1'] = admitted(fr, 'job-r', r1)
rb = signed(K, event='REBIND', seq=2, job='job-r', cert_sha256=er1['cert_sha256'], previous=er1['baseline_sha256'])
front_ctl._write(h, rb, er1); out['p2a_rebind_recorded'] = front_ctl._record(rb, CONTROL); out['p2a_R1_rebound'] = admitted(fr, 'job-r', r1)
put(h, 'job-r', None); r2, er2 = enrol(h, K, 'job-r'); out['p2a_R2'] = admitted(fr, 'job-r', r2)
out['p2a_revoke'] = attempt(lambda: front_ctl.revoke(h, 'job-r', K)); out['p2a_row'] = row(er2)
put(h, 'job-r', rb); out['p2a_R1_rebind_put_back'] = admitted(fr, 'job-r', r1)
put(h, 'job-r', er1); out['p2a_R1_enrol_put_back'] = admitted(fr, 'job-r', r1)
# P2b
h = home('p2b'); fr = front(h, K.public_hex)
q1, eq1 = enrol(h, K, 'job-q'); put(h, 'job-q', None); q2, eq2 = enrol(h, K, 'job-q'); out['p2b_Q2'] = admitted(fr, 'job-q', q2)
put(h, 'job-q', eq1); out['p2b_Q1_put_back'] = admitted(fr, 'job-q', q1); out['p2b_answer_Q1'] = fr.observe('job-q', eq1)
put(h, 'job-q', eq2); out['p2b_revoke'] = attempt(lambda: front_ctl.revoke(h, 'job-q', K))
put(h, 'job-q', eq1); out['p2b_Q1_after_revoke'] = admitted(fr, 'job-q', q1)
# P2c
h = home('p2c'); fr = front(h, K.public_hex)
p1, ep1 = enrol(h, K, 'job-p'); rv = front_ctl.revoke(h, 'job-p', K)
put(h, 'job-p', None); p2, ep2 = enrol(h, K, 'job-p'); out['p2c_P2'] = admitted(fr, 'job-p', p2)
put(h, 'job-p', rv); out['p2c_revoke_rerecord'] = attempt(lambda: front_ctl.revoke(h, 'job-p', K)); out['p2c_row'] = row(ep2)
put(h, 'job-p', ep2); out['p2c_P2_after'] = admitted(fr, 'job-p', p2)
put(h, 'job-p', ep1); out['p2c_P1_after'] = admitted(fr, 'job-p', p1)
# P2d / P2e
orig_record = front_ctl._record
for tag, dsn in (('p2d', CONTROL), ('p2e', BAD)):
    h = home(tag); fr = front(h, K.public_hex)
    c1, ec = enrol(h, K, 'job-c'); out[f'{tag}_admitted'] = admitted(fr, 'job-c', c1)
    def meddle(binding, control_dsn, h=h, ec=ec):
        try:
            return orig_record(binding, control_dsn)
        finally:
            put(h, 'job-c', dict(ec, x=1))
    front_ctl._record = meddle
    try:
        out[f'{tag}_revoke'] = attempt(lambda: front_ctl.revoke(h, 'job-c', K, control_dsn=dsn))
    finally:
        front_ctl._record = orig_record
    out[f'{tag}_row'] = row(ec); out[f'{tag}_file_event'] = front_door.read_jobs(h)['job-c']['event']
    put(h, 'job-c', ec); out[f'{tag}_put_back'] = admitted(fr, 'job-c', c1)
# P2f
for tag, dsn in (('p2f_bad', BAD), ('p2f_good', CONTROL)):
    h = home(tag); fr = front(h, K.public_hex); c1, ec = enrol(h, K, 'job-l'); admitted(fr, 'job-l', c1)
    fd = os.open(h / 'front' / 'jobs.lock', os.O_RDWR | os.O_CREAT, 0o600); fcntl.flock(fd, fcntl.LOCK_EX)
    w0 = front_ctl.LOCK_WAIT; front_ctl.LOCK_WAIT = 1.0
    try:
        out[f'{tag}_revoke'] = attempt(lambda: front_ctl.revoke(h, 'job-l', K, control_dsn=dsn))
    finally:
        front_ctl.LOCK_WAIT = w0; os.close(fd)
    out[f'{tag}_row'] = row(ec); put(h, 'job-l', ec); out[f'{tag}_put_back'] = admitted(fr, 'job-l', c1)
# P2g
h = home('p2g'); fr = front(h, K.public_hex)
out['p2g_capdb'] = front_state.observe(Store(LOCAL), f'{K.public_hex}:job-n', 1, '7' * 64, False)
n1, en = enrol(h, K, 'job-n'); out['p2g_job_n'] = admitted(fr, 'job-n', n1); out['p2g_answer'] = fr.observe('job-n', en)

print(_j.dumps(out, indent=1, default=str))
pred = {'p2a_R1': True, 'p2a_rebind_recorded': 'CURRENT', 'p2a_R1_rebound': True, 'p2a_R2': False, 'p2a_row': (2, True),
        'p2a_R1_rebind_put_back': False, 'p2a_R1_enrol_put_back': False,
        'p2b_Q2': True, 'p2b_Q1_put_back': False, 'p2b_answer_Q1': 'CONFLICT', 'p2b_Q1_after_revoke': False,
        'p2c_P2': False, 'p2c_row': (2, True), 'p2c_P2_after': False, 'p2c_P1_after': False,
        'p2d_admitted': True, 'p2d_row': (2, True), 'p2d_put_back': False,
        'p2e_admitted': True, 'p2e_row': (1, False), 'p2e_file_event': 'ENROL', 'p2e_put_back': True,
        'p2f_bad_row': (1, False), 'p2f_bad_put_back': True, 'p2f_good_row': (2, True), 'p2f_good_put_back': False,
        'p2g_capdb': 'CURRENT', 'p2g_job_n': False, 'p2g_answer': 'CONFLICT'}
pre = {'p2a_revoke': ('ok', 'REVOKE'), 'p2b_revoke': ('ok', 'REVOKE'), 'p2c_revoke_rerecord': ('ok', 'REVOKE'),
       'p2d_revoke': ('Unwritten', 'the revocation is recorded'), 'p2e_revoke': ('Changed', 'the entry of job-c in jobs.json changed'),
       'p2f_bad_revoke': ('OSError', ''), 'p2f_good_revoke': ('Unwritten', 'the revocation is recorded')}
fails = [k for k, v in pred.items() if (tuple(out[k]) if isinstance(out[k], list) else out[k]) != v]
fails += [k for k, (t, p) in pre.items() if not (out[k][0] == t and str(out[k][1]).startswith(p))]
if 'held by another process' not in out['p2f_bad_revoke'][1]: fails.append('p2f_bad_revoke message')
if 'record' in out['p2e_revoke'][1]: fails.append('p2e message mentions the record')
print('PREDICTIONS FAILED:', fails or 'none')
