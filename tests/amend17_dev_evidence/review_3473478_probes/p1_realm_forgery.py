"""P1. The realm file lives in HOME/front, which the D16 adversary (one who can put a binding back into HOME/front/jobs.json,
but cannot start the front door) can also write.

Setting: the front door is started with realm R (it writes HOME/front/realm = R) and admits job-x (record: R:job-x seq 1).

P1a (console given no realm, as README_FRONT documents).  The adversary rewrites HOME/front/realm to R2 (a valid realm).  The
engineer revokes job-x while the front door is stopped.  EXPECTED: revoke returns normally (no Unrecorded, so the CLI would exit 0);
the REVOKE row is under R2:job-x, not R:job-x.  The adversary restores the realm file to R and puts back the earlier jobs.json.  The
front door is started again with --realm R (cfg realm R).  EXPECTED: job-x is ADMITTED (True).

P1b (revocation properly recorded under R).  The adversary rewrites the realm file to R3 and puts back the earlier jobs.json.  The
front door is started as README_FRONT says a later start may be: without --realm (cfg realm None).  EXPECTED: it starts under R3,
and job-x is ADMITTED (True).  Started with --realm R instead: EXPECTED RealmMismatch (fails closed).

P1c (console given realm R, as deploy_front does).  Realm file forged to R4; revoke(realm=R).  EXPECTED: Unrecorded raised whose
message says it 'was recorded under the front door's own realm'; the row is under R4 only; R:job-x is still seq 1 not revoked; after
restoring the file and putting back jobs.json, a front door with realm R ADMITS job-x (True).

P1d (CLI, P1a's case).  EXPECTED: front_ctl.py revoke exits 0 with the forged realm file in place.
"""
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa

key = Key(); out = {}
suffix = os.urandom(3).hex()
R_, R2, R3, R4 = f'realm-real-{suffix}', f'realm-forged2-{suffix}', f'realm-forged3-{suffix}', f'realm-forged4-{suffix}'

# P1a
h = home('p1a'); der, _ = enrol(h, key, 'job-x')
fr = front(h, key, R_); out['p1a_first_admit'] = admitted(fr, 'job-x', der)
before = front_door.jobs_path(h).read_text()
front_state.realm_path(h).write_text(R2 + '\n')                       # the adversary
try:
    front_ctl.revoke(h, 'job-x', key, control_dsn=CONTROL); out['p1a_revoke'] = 'returned normally (exit 0)'
except front_ctl.Unrecorded as exc:
    out['p1a_revoke'] = f'Unrecorded: {exc}'
out['p1a_rows'] = rows('job-x')
front_state.realm_path(h).write_text(R_ + '\n'); front_door.jobs_path(h).write_text(before)   # the adversary restores and puts back
fr2 = front(h, key, R_); fr2.record_revocations()
out['p1a_admitted_after_put_back'] = admitted(fr2, 'job-x', der)

# P1b
h = home('p1b'); der, _ = enrol(h, key, 'job-x')
fr = front(h, key, R_); out['p1b_first_admit'] = admitted(fr, 'job-x', der)
before = front_door.jobs_path(h).read_text()
front_ctl.revoke(h, 'job-x', key, control_dsn=CONTROL); out['p1b_refused_after_revoke'] = admitted(fr, 'job-x', der)
front_state.realm_path(h).write_text(R3 + '\n'); front_door.jobs_path(h).write_text(before)
fr3 = front(h, key, None); fr3.record_revocations()
out['p1b_realm_started_without_flag'] = fr3.cfg['realm']
out['p1b_admitted_started_without_flag'] = admitted(fr3, 'job-x', der)
try:
    front(h, key, R_); out['p1b_started_with_flag'] = 'started'
except front_state.RealmMismatch as exc:
    out['p1b_started_with_flag'] = 'RealmMismatch'

# P1c
h = home('p1c'); der, _ = enrol(h, key, 'job-y')
fr = front(h, key, R_); out['p1c_first_admit'] = admitted(fr, 'job-y', der)
before = front_door.jobs_path(h).read_text()
front_state.realm_path(h).write_text(R4 + '\n')
try:
    front_ctl.revoke(h, 'job-y', key, realm=R_, control_dsn=CONTROL); out['p1c_revoke'] = 'returned normally'
except front_ctl.Unrecorded as exc:
    out['p1c_revoke'] = f'Unrecorded: {exc}'
out['p1c_rows'] = rows('job-y')
front_state.realm_path(h).write_text(R_ + '\n'); front_door.jobs_path(h).write_text(before)
fr4 = front(h, key, R_); fr4.record_revocations()
out['p1c_admitted_after_put_back'] = admitted(fr4, 'job-y', der)

# P1d
h = home('p1d'); der, _ = enrol(h, key, 'job-z')
fr = front(h, key, R_); admitted(fr, 'job-z', der)
front_state.realm_path(h).write_text(R2 + '\n')
kf = h / 'engineer.key'; kf.write_text(key.private_hex)
cli = subprocess.run([sys.executable, '-I', '-B', str(TREE / 'verify' / 'front_ctl.py'), 'revoke', str(h), 'job-z', '--key', str(kf)],
                     capture_output=True, text=True, env=dict(os.environ, PLEA_CONTROL_DSN=CONTROL))
out['p1d_cli'] = (cli.returncode, cli.stdout.strip()[-200:], cli.stderr.strip()[-300:])
out['p1d_rows'] = rows('job-z')

for k, v in out.items():
    print(f'{k}: {v}')
pred = {'p1a': out['p1a_revoke'].startswith('returned') and out['p1a_admitted_after_put_back'] is True,
        'p1b': out['p1b_admitted_started_without_flag'] is True and out['p1b_started_with_flag'] == 'RealmMismatch',
        'p1c': "recorded under the front door's own realm" in out['p1c_revoke'] and out['p1c_admitted_after_put_back'] is True,
        'p1d': out['p1d_cli'][0] == 0}
print('PREDICTIONS:', pred)
