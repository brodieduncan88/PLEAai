"""P2. States of HOME/front/realm, in process.

P2a  realm is a dangling symlink, front door's first start with --realm R.  EXPECTED: fix_realm recurses without end (read_realm
     sees FileNotFoundError, O_EXCL sees EEXIST); Front() raises RecursionError, which main() does not catch (it catches
     RealmMismatch): the front door fails to start with a traceback.  Fails closed.
P2b  realm is a symlink to a file elsewhere holding a valid realm R2, the front door started without --realm.  EXPECTED: adopted
     (cfg realm == R2), as with P1's rewrite.
P2c  realm is empty (a crash between O_EXCL create and the write).  EXPECTED: Front() with --realm R raises RealmMismatch; without,
     cfg realm None and admit raises StateUnavailable.  The console's revoke: written, Unrecorded.  Fails closed.
P2d  no realm file and no realm given to an in-process Front.  EXPECTED: admit raises StateUnavailable.  Front() also replaces the
     caller's cfg['realm'] (it mutates the dict it is given): EXPECTED cfg is the same object and gains 'realm': None.
P2e  console given a realm that is not one ('bad realm!').  EXPECTED: revoke raises Refused and jobs.json is unchanged (the
     revocation is NOT written, contrary to 'a revocation is always written').
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa
key = Key(); sfx = os.urandom(3).hex(); out = {}
R_, R2 = f'realm-p2-{sfx}', f'realm-p2-other-{sfx}'

# P2a
h = home('p2a'); os.symlink(str(h / 'nowhere'), front_state.realm_path(h))
try:
    front(h, key, R_); out['p2a'] = 'started'
except RecursionError:
    out['p2a'] = 'RecursionError'
except front_state.RealmMismatch as exc:
    out['p2a'] = f'RealmMismatch: {exc}'

# P2b
h = home('p2b'); elsewhere = h / 'elsewhere.txt'; elsewhere.write_text(R2 + '\n'); os.symlink(str(elsewhere), front_state.realm_path(h))
out['p2b'] = front(h, key, None).cfg['realm']

# P2c
h = home('p2c'); der, _ = enrol(h, key, 'job-c' + sfx); front_state.realm_path(h).write_text('')
try:
    front(h, key, R_); out['p2c_with'] = 'started'
except front_state.RealmMismatch:
    out['p2c_with'] = 'RealmMismatch'
fr = front(h, key, None); out['p2c_without'] = (fr.cfg['realm'], admitted(fr, 'job-c' + sfx, der))
try:
    front_ctl.revoke(h, 'job-c' + sfx, key, control_dsn=CONTROL); out['p2c_revoke'] = 'returned'
except front_ctl.Unrecorded as exc:
    out['p2c_revoke'] = ('Unrecorded', str(exc)[:120], front_ctl.read_jobs(h)['job-c' + sfx]['event'])

# P2d
h = home('p2d'); der, _ = enrol(h, key, 'job-d' + sfx); cfg = {'journal': 'x'}
fr = front_door.Front(h, Store(LOCAL), cfg, [key.public_hex])
out['p2d'] = (admitted(fr, 'job-d' + sfx, der), fr.cfg is cfg, cfg.get('realm', 'absent'))

# P2e
h = home('p2e'); der, _ = enrol(h, key, 'job-e' + sfx); front(h, key, R_); before = front_door.jobs_path(h).read_text()
try:
    front_ctl.revoke(h, 'job-e' + sfx, key, realm='bad realm!', control_dsn=CONTROL); out['p2e'] = 'returned'
except front_ctl.Refused as exc:
    out['p2e'] = ('Refused', str(exc), 'jobs.json unchanged' if front_door.jobs_path(h).read_text() == before else 'written')

for k, v in out.items(): print(f'{k}: {v}')
print('PREDICTIONS:', {'p2a': out['p2a'] == 'RecursionError', 'p2b': out['p2b'] == R2, 'p2c': out['p2c_with'] == 'RealmMismatch' and out['p2c_without'][0] is None
       and str(out['p2c_without'][1]).startswith('StateUnavailable') and out['p2c_revoke'][0] == 'Unrecorded' and out['p2c_revoke'][2] == 'REVOKE',
       'p2d': str(out['p2d'][0]).startswith('StateUnavailable') and out['p2d'][1] is True and out['p2d'][2] is None,
       'p2e': out['p2e'][0] == 'Refused' and out['p2e'][2] == 'jobs.json unchanged'})
