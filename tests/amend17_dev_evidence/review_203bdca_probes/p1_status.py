"""P1: revoke's paths and the command's exit statuses at 203bdca.

EXPECTATIONS (written before running):
P1a  Plain revoke of a name never enrolled ('job-typo'): Refused naming --by-name and the key prefix; no row for key:job-typo.
     CLI: exit 1, stderr starts 'refused:' and contains '--by-name'; still no row.
P1b  Entry removed, CLI revoke --by-name: exit 5; stderr 'revoked by name, nothing written'; stdout JSON event REVOKE seq 1 with
     signer; row (1, True); jobs.json byte-identical; the honest entry put back is not admitted.
P1c  --by-name given with a usable entry: the ordinary path; exit 0; jobs.json entry REVOKE seq 2; row (2, True).
P1d  --by-name, entry removed, PLEA_CONTROL_DSN unreachable: exit 1, 'is NOT revoked'; no row change.
P1e  --by-name with names that are not job names: 'job-n\\n', 'JOB-A', 'a', 'job-x\\x00', 'ｊob' (fullwidth), a RESERVED name,
     43 characters: each Refused 'not a job name', no row.  'job-n\\n' passes JOB_NAME.match and fails fullmatch.
P1f  Status 4 only on the ordinary path: entry usable, log made a directory: exit 4 'recorded, not written'; row (2, True).
P1g  Status 3: entry usable, DSN unreachable: exit 3 'written, not recorded'.
P1h  Keys A and B pinned; A enrolled job-ab.  Plain revoke with B: exit 1, mentions 'not signed by this engineer' and '--by-name'.
     --by-name with B: exit 5, message names B's prefix and 'signed by another key is not covered'; row B:job-ab (1, True),
     row A:job-ab (1, False); A's job-ab still admitted (documented as not covered).
P1i  In process: RevokedByName is a subclass of Unwritten (so 'except Unwritten' catches it), and main() catches it first.
P1j  --by-name given to rebind/enrol is accepted by argparse and ignored (no error).  (Expected: ignored, exit as without it.)
Run 2 note (added after run 1, expectations unchanged): rowk skips the database for a name with NUL, which psycopg cannot send.
"""
import json, os, re
from common import *  # noqa

out = {}
A = Key(); B = Key(); KA = keyfile(A, 'A'); KB = keyfile(B, 'B')

def rowk(key, job): return None if '\x00' in job else row_named(   # run 2: run 1 died here, psycopg refuses NUL in text (probe error, output kept)
        front_state.state_name({'signer': key.public_hex, 'job': job}))

# P1a
h = home('p1a'); der, b = enrol(h, A, 'job-real')
try:
    front_ctl.revoke(h, 'job-typo', A); out['p1a_inproc'] = 'no refusal'
except front_ctl.Refused as exc:
    out['p1a_inproc'] = ('Refused', '--by-name' in str(exc), A.public_hex[:16] in str(exc))
out['p1a_cli'] = cli(h, KA, 'revoke', 'job-typo')
out['p1a_row'] = rowk(A, 'job-typo')

# P1b
h = home('p1b'); der, b = enrol(h, A, 'job-b'); fr = front(h, A.public_hex); out['p1b_admit_before'] = admitted(fr, 'job-b', der)
put(h, 'job-b', None); before = jobs_raw(h)
rc = cli(h, KA, 'revoke', 'job-b', '--by-name'); out['p1b_cli'] = rc
out['p1b_unchanged'] = jobs_raw(h) == before; out['p1b_row'] = row(b)
put(h, 'job-b', b); out['p1b_put_back_admitted'] = admitted(front(h, A.public_hex), 'job-b', der)

# P1c
h = home('p1c'); der, b = enrol(h, A, 'job-c'); admitted(front(h, A.public_hex), 'job-c', der)
out['p1c_cli'] = cli(h, KA, 'revoke', 'job-c', '--by-name')
out['p1c_entry'] = (lambda e: (e['event'], e['seq']))(front_door.read_jobs(h)['job-c']); out['p1c_row'] = row(b)

# P1d
h = home('p1d'); der, b = enrol(h, A, 'job-d'); admitted(front(h, A.public_hex), 'job-d', der); put(h, 'job-d', None)
out['p1d_cli'] = cli(h, KA, 'revoke', 'job-d', '--by-name', env={'PLEA_CONTROL_DSN': BAD}); out['p1d_row'] = row(b)

# P1e
h = home('p1e'); enrol(h, A, 'job-n')
names = ['job-n\n', 'JOB-A', 'a', 'job-x\x00', 'ｊob', sorted(front_door.RESERVED)[0], 'j' * 43, 'job-n ', '-job']
out['p1e'] = {}
for n in names:
    try:
        front_ctl.revoke(h, n, A, by_name=True); r = 'no refusal'
    except front_ctl.Unwritten as exc:
        r = 'REVOKED ' + str(exc)[:80]
    except front_ctl.Refused as exc:
        r = 'not a job name' in str(exc)
    out['p1e'][repr(n)] = (r, rowk(A, n), bool(front_door.JOB_NAME.match(n)), bool(front_door.JOB_NAME.fullmatch(n)))

# P1f
h = home('p1f'); der, b = enrol(h, A, 'job-f'); admitted(front(h, A.public_hex), 'job-f', der)
lg = front_door.jobs_path(h).parent / 'enrolment.jsonl'; os.replace(lg, str(lg) + '.aside'); lg.mkdir()
out['p1f_cli'] = cli(h, KA, 'revoke', 'job-f'); out['p1f_row'] = row(b)
lg.rmdir(); os.replace(str(lg) + '.aside', lg)

# P1g
h = home('p1g'); der, b = enrol(h, A, 'job-g'); admitted(front(h, A.public_hex), 'job-g', der)
out['p1g_cli'] = cli(h, KA, 'revoke', 'job-g', env={'PLEA_CONTROL_DSN': BAD})

# P1h
h = home('p1h'); der, b = enrol(h, A, 'job-ab'); fr = front(h, A.public_hex, B.public_hex); out['p1h_admit_before'] = admitted(fr, 'job-ab', der)
rc = cli(h, KB, 'revoke', 'job-ab'); out['p1h_plain'] = (rc[0], 'not signed by this engineer' in rc[2], '--by-name' in rc[2])
rc = cli(h, KB, 'revoke', 'job-ab', '--by-name'); out['p1h_byname'] = (rc[0], B.public_hex[:16] in rc[2], 'signed by another key is not covered' in rc[2])
out['p1h_rows'] = (rowk(B, 'job-ab'), rowk(A, 'job-ab'))
out['p1h_admit_after'] = admitted(front(h, A.public_hex, B.public_hex), 'job-ab', der)

# P1i
out['p1i'] = issubclass(front_ctl.RevokedByName, front_ctl.Unwritten)
src = (TREE / 'verify' / 'front_ctl.py').read_text(); out['p1i_order'] = src.index('except RevokedByName') < src.index('except Unwritten as exc:')

# P1j
h = home('p1j'); der, b = enrol(h, A, 'job-j')
out['p1j_rebind'] = cli(h, KA, 'rebind', 'job-j', 'cd' * 32, '--by-name')[0:3:2]

for k, v in out.items():
    print(k, '=', v)
pred = {
 'p1a': out['p1a_inproc'] == ('Refused', True, True) and out['p1a_cli'][0] == 1 and '--by-name' in out['p1a_cli'][2] and out['p1a_row'] is None,
 'p1b': out['p1b_admit_before'] is True and out['p1b_cli'][0] == 5 and 'revoked by name, nothing written' in out['p1b_cli'][2] and json.loads(out['p1b_cli'][1]).get('signer') == A.public_hex
        and out['p1b_unchanged'] and out['p1b_row'] == (1, True) and out['p1b_put_back_admitted'] is False,
 'p1c': out['p1c_cli'][0] == 0 and out['p1c_entry'] == ('REVOKE', 2) and out['p1c_row'] == (2, True),
 'p1d': out['p1d_cli'][0] == 1 and 'is NOT revoked' in out['p1d_cli'][2] and out['p1d_row'] == (1, False),
 'p1e': all(v[0] is True and v[1] is None for v in out['p1e'].values()) and out['p1e'][repr('job-n\n')][2:] == (True, False),
 'p1f': out['p1f_cli'][0] == 4 and 'recorded, not written' in out['p1f_cli'][2] and out['p1f_row'] == (2, True),
 'p1g': out['p1g_cli'][0] == 3 and 'written, not recorded' in out['p1g_cli'][2],
 'p1h': out['p1h_admit_before'] is True and out['p1h_plain'] == (1, True, True) and out['p1h_byname'] == (5, True, True) and out['p1h_rows'] == ((1, True), (1, False)) and out['p1h_admit_after'] is True,
 'p1i': out['p1i'] and out['p1i_order'],
 'p1j': out['p1j_rebind'][0] == 1,
}
print('PREDICTIONS', pred); print('PREDICTIONS FAILED:', [k for k, v in pred.items() if not v])
