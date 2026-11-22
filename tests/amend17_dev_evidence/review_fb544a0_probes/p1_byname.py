"""P1: revocation by name (front_ctl.revoke, the `except Refused as no_entry` branch), at fb544a0.

EXPECTATIONS (written before running):
P1a  The by-name REVOKE statement put into jobs.json by an adversary as the job's entry: binding_valid False; Front.usable False;
     admit returns None (no exception); record_revocations returns 0 without raising; a Front can be constructed; sweep-like
     iteration (usable) skips it.  The honest ENROL put back after the by-name revoke is refused (row revoked).
P1b  Typo: revoke of a never-enrolled name 'job-typo' -> Unwritten (by name), a new row (1, True) for key:job-typo; the CLI form
     exits 4 with 'recorded, not written'.  A later honest enrolment of 'job-typo' (written as enrol's last step does) is not
     admitted (REVOKED): the name is burned.  The intended job (job-real) stays admitted.
P1c  Wrong key: keys A and B both pinned; A enrols job-a; revoke job-a with key B -> Unwritten (exit 4 at the CLI), row B:job-a
     (1, True); row A:job-a stays (1, False); A's job-a is still admitted.  (At c5c9832 this was exit 1, refused.)
P1d  Trailing newline: revoke 'job-n\\n' (job-n enrolled) -> JOB_NAME.match accepts it, so Unwritten by name under the row
     key:'job-n\\n'; job-n's own row stays (1, False) and job-n is still admitted.
P1e  Repeated by-name revoke of a removed entry: each answer Unwritten; jobs.json never gains an entry for it (the README's
     'revoke given again writes it' for status 4 does not hold here).
P1f  After a by-name revoke with the honest entry restored, revoke again takes the normal path: REVOKE seq 2 written and
     recorded, returns the binding; row (2, True).
P1g  The by-name statement is not appended to enrolment.jsonl (log line count unchanged).
P1h  With PLEA_CONTROL_DSN naming another database (plea, not this front door's), a by-name revoke answers Unwritten
     ('the front door refuses'), and the front door, on plea_rv7, still admits the job.  -- not run against `plea`:
     the author's suites use it; replaced by a second database? no: skipped, ARGUED only.
"""
import json
from common import *  # noqa

out = {}
A = Key(); B = Key()

# P1a
h = home('p1a'); der, b = enrol(h, A, 'job-p1a'); fr = front(h, A.public_hex)
out['p1a_admitted_before'] = admitted(fr, 'job-p1a', der)
put(h, 'job-p1a', None)
out['p1a_revoke'] = attempt(lambda: front_ctl.revoke(h, 'job-p1a', A))
# build the by-name statement the same way the console does, and put it in jobs.json
st = {'event': 'REVOKE', 'seq': 1, 'job': 'job-p1a', 'baseline_sha256': None, 'root': None, 'cert_sha256': None, 'previous': None, 'time': now(), 'note': 'x'}
st = dict(st, signer=A.public_hex, signature=A.sign(front_door.binding_message(st)))
put(h, 'job-p1a', st)
out['p1a_binding_valid'] = front_door.binding_valid(st, (A.public_hex,))
fr2 = front(h, A.public_hex)
out['p1a_usable'] = fr2.usable('job-p1a', st)
out['p1a_admit'] = admitted(fr2, 'job-p1a', der)
out['p1a_record_revocations'] = attempt(lambda: fr2.record_revocations())
out['p1a_rebind'] = attempt(lambda: front_ctl.rebind(h, 'job-p1a', 'ab' * 32, A, wait=0))
out['p1a_revoke_again'] = attempt(lambda: front_ctl.revoke(h, 'job-p1a', A))
put(h, 'job-p1a', b)
out['p1a_put_back_admitted'] = admitted(fr2, 'job-p1a', der)
out['p1a_row'] = row(b)

# P1b
h = home('p1b'); der_r, b_r = enrol(h, A, 'job-real'); fr = front(h, A.public_hex)
out['p1b_typo_revoke'] = attempt(lambda: front_ctl.revoke(h, 'job-typo', A))
out['p1b_row_typo'] = row_named(f'{A.public_hex}:job-typo')
kA = keyfile(A, 'A')
out['p1b_cli_typo2'] = cli(h, kA, 'revoke', 'job-typo2')
out['p1b_real_admitted'] = admitted(fr, 'job-real', der_r)
der_t, b_t = enrol(h, A, 'job-typo')
out['p1b_later_enrol_admitted'] = admitted(fr, 'job-typo', der_t)
out['p1b_later_enrol_answer'] = fr.observe('job-typo', b_t)

# P1c
h = home('p1c'); der_a, b_a = enrol(h, A, 'job-a'); fr = front(h, A.public_hex, B.public_hex)
out['p1c_before'] = admitted(fr, 'job-a', der_a)
kB = keyfile(B, 'B')
out['p1c_cli_wrong_key'] = cli(h, kB, 'revoke', 'job-a')
out['p1c_row_B'] = row_named(f'{B.public_hex}:job-a')
out['p1c_row_A'] = row(b_a)
out['p1c_after'] = admitted(fr, 'job-a', der_a)

# P1d
h = home('p1d'); der_n, b_n = enrol(h, A, 'job-n'); fr = front(h, A.public_hex)
out['p1d_jobname_match'] = bool(front_door.JOB_NAME.match('job-n\n'))
out['p1d_revoke_nl'] = attempt(lambda: front_ctl.revoke(h, 'job-n\n', A))
out['p1d_row_nl'] = row_named(f'{A.public_hex}:job-n\n')
out['p1d_row_n'] = row(b_n)
out['p1d_admitted'] = admitted(fr, 'job-n', der_n)

# P1e, P1f, P1g
h = home('p1e'); der_e, b_e = enrol(h, A, 'job-e'); fr = front(h, A.public_hex)
log_before = len((h / 'front' / 'enrolment.jsonl').read_text().splitlines())
put(h, 'job-e', None)
out['p1e_first'] = attempt(lambda: front_ctl.revoke(h, 'job-e', A))[0]
out['p1e_second'] = attempt(lambda: front_ctl.revoke(h, 'job-e', A))[0]
out['p1e_entry_in_jobs'] = 'job-e' in front_door.read_jobs(h)
out['p1g_log_lines_same'] = len((h / 'front' / 'enrolment.jsonl').read_text().splitlines()) == log_before
put(h, 'job-e', b_e)
out['p1f_normal'] = attempt(lambda: front_ctl.revoke(h, 'job-e', A))
out['p1f_row'] = row(b_e)
out['p1f_entry'] = front_door.read_jobs(h)['job-e']['event']

for k, v in out.items():
    print(k, '=', json.dumps(v, default=str))

pred = {
    'p1a_binding_valid': out['p1a_binding_valid'] is False, 'p1a_usable': out['p1a_usable'] is False, 'p1a_admit': out['p1a_admit'] is False,
    'p1a_rr': out['p1a_record_revocations'] == ('ok', 0), 'p1a_put_back': out['p1a_put_back_admitted'] is False,
    'p1b_typo': out['p1b_typo_revoke'][0] == 'Unwritten' and out['p1b_row_typo'] == (1, True), 'p1b_cli': out['p1b_cli_typo2'][0] == 4,
    'p1b_real': out['p1b_real_admitted'] is True, 'p1b_burned': out['p1b_later_enrol_admitted'] is False and out['p1b_later_enrol_answer'] == 'REVOKED',
    'p1c_cli': out['p1c_cli_wrong_key'][0] == 4, 'p1c_rows': out['p1c_row_B'] == (1, True) and out['p1c_row_A'] == (1, False), 'p1c_after': out['p1c_after'] is True,
    'p1d': out['p1d_jobname_match'] and out['p1d_revoke_nl'][0] == 'Unwritten' and out['p1d_row_nl'] == (1, True) and out['p1d_row_n'] == (1, False) and out['p1d_admitted'] is True,
    'p1e': out['p1e_first'] == 'Unwritten' and out['p1e_second'] == 'Unwritten' and out['p1e_entry_in_jobs'] is False,
    'p1f': out['p1f_normal'] == ('ok', 'REVOKE') and out['p1f_row'] == (2, True) and out['p1f_entry'] == 'REVOKE',
    'p1g': out['p1g_log_lines_same'] is True,
}
failed = [k for k, v in pred.items() if not v]
print('PREDICTIONS FAILED:' if failed else 'ALL PREDICTIONS HELD', failed)
