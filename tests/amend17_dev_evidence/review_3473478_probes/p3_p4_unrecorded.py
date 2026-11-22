"""P3 and P4: what is left when the console cannot record, and the order write-then-record for a move.

P3   The console's database cannot be reached (bad DSN) while the front door is stopped: revoke writes REVOKE, raises Unrecorded.
     The engineer, told so, fixes the DSN and runs revoke again.  EXPECTED: Refused('... already revoked'): the console has no way
     to record a revocation already in the file.  The record still shows the job seq 1, not revoked.  The adversary puts back the
     earlier jobs.json before the front door starts.  EXPECTED: ADMITTED (True).

P4a  rebind (front door stopped) with the console's database unreachable: written (REBIND seq 2), Unrecorded.  The adversary puts back
     the ENROL (seq 1) before the front door starts.  EXPECTED: the superseded binding is ADMITTED (True), and stays admissible
     until the file shows seq 2 again.  (At f4c1de6 the same failure wrote nothing: the job also stayed on seq 1.)

P4b  rebind with a reachable database; the put-back happens between the write and the record (simulated by a hook in _record), and
     a running front door is asked in that window.  EXPECTED: admitted in the window (True); after the console's record (CURRENT,
     seq 2) the same put-back binding is STALE: refused (False).  The window is the time of one database call.

_envelope, _deliverable and root_for are replaced in process (no baselines are built); the order of write and record is the code's.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa
key = Key(); sfx = os.urandom(3).hex(); R_ = f'realm-p34-{sfx}'; out = {}
OLD, NEW = 'ab' * 32, 'cd' * 32
front_ctl._envelope = lambda home, h, k: {'baseline_sha256': h, 'card': {'supersedes': {'baseline_sha256': OLD}}}
front_ctl._deliverable = lambda home, h, w: None
front_ctl.root_for = lambda card: 'budget/' + NEW[:32]

# P3
job = 'job-p3' + sfx; h = home('p3'); der, _ = enrol(h, key, job, OLD); fr = front(h, key, R_); out['p3_first'] = admitted(fr, job, der); del fr
before = front_door.jobs_path(h).read_text()
try:
    front_ctl.revoke(h, job, key, control_dsn=BAD); out['p3_revoke'] = 'returned'
except front_ctl.Unrecorded as exc:
    out['p3_revoke'] = 'Unrecorded'
try:
    front_ctl.revoke(h, job, key, control_dsn=CONTROL); out['p3_retry'] = 'returned'
except front_ctl.Refused as exc:
    out['p3_retry'] = f'Refused: {exc}'
out['p3_rows'] = rows(job)
front_door.jobs_path(h).write_text(before)
fr = front(h, key, R_); fr.record_revocations(); out['p3_admitted_after_put_back'] = admitted(fr, job, der)

# P4a
job = 'job-p4a' + sfx; h = home('p4a'); der, _ = enrol(h, key, job, OLD); fr = front(h, key, R_); out['p4a_first'] = admitted(fr, job, der); del fr
before = front_door.jobs_path(h).read_text()
try:
    front_ctl.rebind(h, job, NEW, key, control_dsn=BAD); out['p4a_rebind'] = 'returned'
except front_ctl.Unrecorded as exc:
    out['p4a_rebind'] = f'Unrecorded: {exc}'
out['p4a_written'] = (front_ctl.read_jobs(h)[job]['event'], front_ctl.read_jobs(h)[job]['seq'])
front_door.jobs_path(h).write_text(before)
fr = front(h, key, R_); fr.record_revocations(); b = fr.admit(job, der); out['p4a_admitted_after_put_back'] = (b is not None, b and b['baseline_sha256'] == OLD)
out['p4a_rows'] = rows(job)

# P4b
job = 'job-p4b' + sfx; h = home('p4b'); der, _ = enrol(h, key, job, OLD); fr = front(h, key, R_); out['p4b_first'] = admitted(fr, job, der)
before = front_door.jobs_path(h).read_text(); real_record = front_ctl._record; seen = {}
def hooked(binding, realm, dsn):
    after = front_door.jobs_path(h).read_text(); front_door.jobs_path(h).write_text(before)
    seen['in_window'] = admitted(fr, job, der)
    ans = real_record(binding, realm, dsn); seen['answer'] = ans
    return ans
front_ctl._record = hooked
front_ctl.rebind(h, job, NEW, key, control_dsn=CONTROL)
front_ctl._record = real_record
out['p4b_in_window'] = seen['in_window']; out['p4b_console_answer'] = seen['answer']
out['p4b_put_back_after_record'] = admitted(fr, job, der)
out['p4b_rows'] = rows(job)

for k, v in out.items(): print(f'{k}: {v}')
print('PREDICTIONS:', {'p3': out['p3_retry'].startswith('Refused') and 'already revoked' in out['p3_retry'] and out['p3_admitted_after_put_back'] is True,
       'p4a': out['p4a_written'] == ('REBIND', 2) and out['p4a_admitted_after_put_back'] == (True, True),
       'p4b': out['p4b_in_window'] is True and out['p4b_console_answer'] == 'CURRENT' and out['p4b_put_back_after_record'] is False})
