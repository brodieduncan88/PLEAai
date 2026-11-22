"""P1d re-run.  p1_byname.out's P1d failed on p1d_row_n (null, predicted (1, False)): the fault is the probe's order, which
read job-n's row before the front door had ever observed job-n (the simulated enrol does not touch the record; the row is made
at the first admit).  Same predicate, with one admit first.
EXPECTATION (before running): JOB_NAME.match('job-n\\n') is truthy; revoke 'job-n\\n' answers Unwritten (by name); row
key:'job-n\\n' is (1, True); job-n's own row is (1, False); job-n is still admitted.  Also the CLI with the argument
'job-n\\n' exits 4."""
import json
from common import *  # noqa
A = Key()
h = home('p1d2'); der_n, b_n = enrol(h, A, 'job-n'); fr = front(h, A.public_hex)
out = {'first_admit': admitted(fr, 'job-n', der_n)}
out['match'] = bool(front_door.JOB_NAME.match('job-n\n'))
out['revoke_nl'] = attempt(lambda: front_ctl.revoke(h, 'job-n\n', A))[0]
out['row_nl'] = row_named(f'{A.public_hex}:job-n\n'); out['row_n'] = row(b_n)
out['cli_nl'] = cli(h, keyfile(A, 'A'), 'revoke', 'job-n\n')[0]
out['admitted'] = admitted(fr, 'job-n', der_n)
for k, v in out.items(): print(k, '=', json.dumps(v))
ok = out['match'] and out['revoke_nl'] == 'Unwritten' and out['row_nl'] == (1, True) and out['row_n'] == (1, False) and out['admitted'] is True and out['cli_nl'] == 4
print('ALL PREDICTIONS HELD' if ok else 'PREDICTIONS FAILED')
