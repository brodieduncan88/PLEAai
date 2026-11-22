"""Q2. Re-enrolment of a job name, the admit order, non-canonical certificate hashes, CAP-DB, and two front doors on one database.

Q2a (re-enrolment after the entry is deleted).  job-r enrolled with C1 and admitted (row C1:job-r seq 1).  The adversary deletes
job-r's entry from jobs.json.  The console's enrol refuses a used name only by reading jobs.json (front_ctl.py:178), so the
engineer can enrol job-r again: here the ENROL with C2 is written as enrol's last step writes it.  The engineer then revokes job-r
(honest file, DB reachable): it is recorded under C2:job-r only.  The adversary puts C1's ENROL back.  EXPECTED: the holder of C1
is ADMITTED (True); rows: C1:job-r (1, False), C2:job-r (2, True).

Q2b (admit order).  job-a (Ca) and job-b (Cb).  The front door calls admit('job-a', Cb's DER) (a name the TLS layer would not give
for Cb, since the name is the certificate's CN; this is the in-process worst case).  With jobs['job-a'] = a REBIND seq 2 written
and not yet recorded: EXPECTED admit returns None, and the row Ca:job-a moves to (2, False) (the record advances to the file's
signed binding; nothing else).  With jobs['job-a'] then put back to the ENROL seq 1: EXPECTED None, and the row stays (2, False).

Q2c (non-canonical certificate hash).  Engineer-signed bindings of job-u with cert_sha256 upper-case, and with a trailing '\n'
after 64 lower-case hex digits.  EXPECTED: upper-case: usable False, admit None, no row.  Trailing newline: usable True (front_door's
HEX64 is '^...$' with .match, and '$' matches before a final newline), then front_state.state_name raises ValueError, so admit raises
ValueError (not StateUnavailable) and record_revocations raises ValueError for such a REVOKE.

Q2d (CAP-DB: plea_local calling the function directly).  On a revoked row: p_revoked false with a higher seq: EXPECTED 'REVOKED',
row unchanged revoked.  On a live row Cl:job-l at seq 1: p_seq 2**62, made-up digest, revoked false: EXPECTED 'CURRENT'; then the
job's own ENROL: EXPECTED STALE (refused: a denial, not an admission).  Direct SELECT on the table: EXPECTED permission denied.

Q2e (two front doors, one database, one engineer key).  HOME1 and HOME2 each enrol job-s (certs S1, S2).  HOME1 revokes job-s.
EXPECTED: HOME2's job-s still admitted (rows are separate).  HOME1's revoked ENROL (S1) put into HOME2's jobs.json: EXPECTED refused
(REVOKED).  An unrevoked HOME2 binding of another job, job-t (T2), put into HOME1's file: EXPECTED admitted at HOME1 for T2's
holder (in process; over TLS only if the two deployments share an authority).
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa

key = Key(); out = {}

# Q2a
h = home('q2a'); d1, e1 = enrol(h, key, 'job-r')
fr = front(h, key); out['q2a_first_admit_C1'] = admitted(fr, 'job-r', d1)
put(h, 'job-r', None)                                                 # the adversary deletes the entry
out['q2a_name_in_file'] = 'job-r' in front_door.read_jobs(h)
d2, e2 = enrol(h, key, 'job-r')                                       # the engineer enrols the name again
out['q2a_admit_C2'] = admitted(fr, 'job-r', d2)
try:
    front_ctl.revoke(h, 'job-r', key, control_dsn=CONTROL); out['q2a_revoke'] = 'returned normally'
except Exception as exc:
    out['q2a_revoke'] = f'{type(exc).__name__}: {exc}'
put(h, 'job-r', e1)                                                   # the adversary puts C1's ENROL back
fr2 = front(h, key); fr2.record_revocations()
out['q2a_admitted_C1_after_put_back'] = admitted(fr2, 'job-r', d1)
out['q2a_rows'] = {'C1': row(e1), 'C2': row(e2)}

# Q2b
h = home('q2b'); da, ea = enrol(h, key, 'job-a'); db_, eb = enrol(h, key, 'job-b')
fr = front(h, key); out['q2b_first_admit_a'] = admitted(fr, 'job-a', da)
mv = signed(key, event='REBIND', seq=2, job='job-a', baseline_sha256='cd' * 32, root='budget/' + 'cd' * 16, cert_sha256=ea['cert_sha256'], previous='ab' * 32)
put(h, 'job-a', mv)
out['q2b_admit_with_Cb_on_move'] = admitted(fr, 'job-a', db_); out['q2b_row_after_move'] = row(ea)
put(h, 'job-a', ea)
out['q2b_admit_with_Cb_on_put_back'] = admitted(fr, 'job-a', db_); out['q2b_row_after_put_back'] = row(ea)
out['q2b_admit_with_Ca_on_put_back'] = admitted(fr, 'job-a', da)

# Q2c
h = home('q2c'); du = os.urandom(64); hu = hashlib.sha256(du).hexdigest()
up = signed(key, job='job-u', cert_sha256=hu.upper()); put(h, 'job-u', up); fr = front(h, key)
out['q2c_upper_usable'] = fr.usable('job-u', up); out['q2c_upper_admit'] = admitted(fr, 'job-u', du)
with Store(OWNER).connect() as c:
    out['q2c_upper_rows'] = c.execute("SELECT count(*) FROM public.verify_front_binding WHERE job ILIKE %s", (hu + ':job-u',)).fetchone()[0]
nl = signed(key, job='job-u', cert_sha256=hu + '\n'); put(h, 'job-u', nl)
out['q2c_newline_usable'] = fr.usable('job-u', nl); out['q2c_newline_admit'] = admitted(fr, 'job-u', du)
nlr = signed(key, event='REVOKE', seq=2, job='job-u', cert_sha256=hu + '\n'); put(h, 'job-u', nlr)
try:
    out['q2c_newline_record_revocations'] = fr.record_revocations()
except Exception as exc:
    out['q2c_newline_record_revocations'] = f'{type(exc).__name__}: {exc}'

# Q2d
local = Store(LOCAL)
def call(name, seq, sha, rev):
    with local.connect() as c:
        return c.execute('SELECT public.verify_front_observe(%s, %s, %s, %s)', (name, seq, sha, rev)).fetchone()[0]
h = home('q2d'); dk, ek = enrol(h, key, 'job-k'); dl, el = enrol(h, key, 'job-l')
fr = front(h, key); front_ctl.revoke(h, 'job-k', key, control_dsn=CONTROL)
out['q2d_unrevoke_attempt'] = call(front_state.state_name(ek), 99, 'ee' * 32, False); out['q2d_row_k'] = row(ek)
out['q2d_first_admit_l'] = admitted(fr, 'job-l', dl)
out['q2d_bump'] = call(front_state.state_name(el), 2 ** 62, 'ee' * 32, False)
out['q2d_admit_l_after_bump'] = admitted(fr, 'job-l', dl)
try:
    with local.connect() as c:
        c.execute('SELECT * FROM public.verify_front_binding').fetchall(); out['q2d_select'] = 'allowed'
except Exception as exc:
    out['q2d_select'] = type(exc).__name__

# Q2e
h1, h2 = home('q2e1'), home('q2e2')
s1d, s1 = enrol(h1, key, 'job-s'); s2d, s2 = enrol(h2, key, 'job-s'); t2d, t2 = enrol(h2, key, 'job-t')
f1, f2 = front(h1, key), front(h2, key)
out['q2e_admit_1'] = admitted(f1, 'job-s', s1d); out['q2e_admit_2'] = admitted(f2, 'job-s', s2d)
front_ctl.revoke(h1, 'job-s', key, control_dsn=CONTROL)
out['q2e_admit_2_after_revoke_1'] = admitted(f2, 'job-s', s2d)
put(h2, 'job-s', s1); out['q2e_home1_revoked_binding_in_home2'] = admitted(f2, 'job-s', s1d)
put(h1, 'job-t', t2); out['q2e_home2_binding_in_home1'] = admitted(f1, 'job-t', t2d)

print(json.dumps(out, indent=1, default=str))
