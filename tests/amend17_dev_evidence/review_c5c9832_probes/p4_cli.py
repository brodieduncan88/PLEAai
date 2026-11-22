"""P4. The previous review's Q1b through the command line, and P1d (i) and P2e-like refusals, as the engineer sees them.
EXPECTED: (a) jobs['job-w'] = job-z's REVOKE (same engineer), `front_ctl.py revoke HOME job-w`: exit 1, stderr starts
'refused: the stored binding of job-w is one signed for another job (job-z)'; job-w's row unchanged (1, False); the file unchanged.
(b) job-w's entry deleted: exit 1, stderr 'refused: job-w is not enrolled'.  (c) honest file, PLEA_CONTROL_DSN unreachable: exit 3,
'written, not recorded'; then revoke again with the database reachable: exit 0; row (2, True)."""
import os, sys, json as _j, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa
K = Key(); out = {}
h = home('p4'); kf = h.parent / f'{h.name}.key'; kf.write_text(K.private_hex + '\n'); fr = front(h, K.public_hex)
w, ew = enrol(h, K, 'job-w'); z, ez = enrol(h, K, 'job-z'); admitted(fr, 'job-w', w)
rz = front_ctl.revoke(h, 'job-z', K)
def cli(dsn=CONTROL):
    p = subprocess.run([sys.executable, '-B', str(TREE / 'verify' / 'front_ctl.py'), 'revoke', str(h), 'job-w', '--key', str(kf)],
                       capture_output=True, text=True, timeout=120, env=dict(os.environ, PLEA_CONTROL_DSN=dsn))
    return p.returncode, p.stderr.strip()[:200]
put(h, 'job-w', rz); before = front_door.jobs_path(h).read_text(); out['a'] = cli(); out['a_row'] = row(ew); out['a_file_same'] = front_door.jobs_path(h).read_text() == before
put(h, 'job-w', None); out['b'] = cli()
put(h, 'job-w', ew); out['c1'] = cli(BAD); out['c2'] = cli(); out['c_row'] = row(ew)
print(_j.dumps(out, indent=1, default=str))
ok = (out['a'][0] == 1 and out['a'][1].startswith('refused: the stored binding of job-w is one signed for another job (job-z)') and out['a_row'] == (1, False)
      and out['a_file_same'] and out['b'] == (1, 'refused: job-w is not enrolled') and out['c1'][0] == 3 and 'written, not recorded' in out['c1'][1]
      and out['c2'][0] == 0 and out['c_row'] == (2, True))
print('PREDICTIONS FAILED:', 'none' if ok else 'see above')
