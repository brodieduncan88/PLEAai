"""P1b re-run (setup fault in p1_realm_forgery.py: job-x reused across P1a and P1b under one realm, so P1b's first admit met
CONFLICT).  Same expectations as P1b, with a unique realm and job: EXPECTED first admit True; after the console's revocation,
refused (False); realm file forged, earlier jobs.json put back, front door started without --realm: it takes the forged realm and
ADMITS (True); started with --realm R: RealmMismatch."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa
key = Key(); sfx = os.urandom(3).hex(); R_, R3 = f'realm-real-{sfx}', f'realm-forged3-{sfx}'; job = 'job-b' + sfx
h = home('p1b2'); der, _ = enrol(h, key, job); fr = front(h, key, R_); out = {'first_admit': admitted(fr, job, der)}
before = front_door.jobs_path(h).read_text()
front_ctl.revoke(h, job, key, control_dsn=CONTROL); out['after_revoke'] = admitted(fr, job, der); out['rows_after_revoke'] = rows(job)
front_state.realm_path(h).write_text(R3 + '\n'); front_door.jobs_path(h).write_text(before)
fr3 = front(h, key, None); fr3.record_revocations(); out['realm_without_flag'] = fr3.cfg['realm']; out['admitted_without_flag'] = admitted(fr3, job, der)
try:
    front(h, key, R_); out['with_flag'] = 'started'
except front_state.RealmMismatch:
    out['with_flag'] = 'RealmMismatch'
out['rows_end'] = rows(job)
for k, v in out.items(): print(f'{k}: {v}')
print('PREDICTION:', out['first_admit'] is True and out['after_revoke'] is False and out['admitted_without_flag'] is True and out['with_flag'] == 'RealmMismatch')
