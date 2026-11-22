"""P1. Several pinned engineer keys, key rotation, and the form of the signer field.  Expectations written before running.

P1a (two pinned engineers A and B, one job name).  A enrols job-x (C1); the front door, pinning [A, B], admits C1.  The adversary
deletes job-x's entry.  B enrols job-x (C2): B's console sees no job-x in jobs.json, so enrol goes ahead.  C2 is admitted (row
B:job-x is new).  B revokes job-x with an honest file and the database reachable.  The adversary puts A's ENROL (C1) back.
EXPECTED: C1 ADMITTED (True): the rows are A:job-x (1, False) and B:job-x (2, True).  A's console asked to revoke job-x while
B's entry is in the file: EXPECTED Refused ('not signed by this engineer').

P1b (rotation K1 -> K2, both pinned in the transition).  K1 enrols job-y (C1), admitted.  The engineer, now holding K2, revokes
job-y: EXPECTED Refused ('not signed by this engineer'), nothing recorded (row K1:job-y stays (1, False)).  The engineer removes
the entry by hand and enrols job-y again under K2 (C2), then revokes it under K2.  The adversary puts K1's ENROL back:
EXPECTED C1 ADMITTED (True).

P1c (form of the signer).  A's ENROL of job-z (D1), admitted, then revoked by A's console (row A:job-z revoked).  Copies of that
ENROL with signer upper-cased, and with signer upper-cased in its first character only.  The signer is not in the signed message
(BINDING_FIELDS), and bytes.fromhex accepts upper case, so the signature still verifies under the changed field.
  - pins [a] (lower case, as the console prints it): EXPECTED both refused (signer not pinned).
  - pins [a, A] (the operator pinned both forms): EXPECTED both refused (front_state.nameable needs lower case), no row named by
    the upper form is made.
  - pins [A] only: EXPECTED every binding refused, A's honest lower-case ENROL of a fresh job included (fails closed).

P1d (a revocation the folder writer prevents).  job-w enrolled (W1), admitted.  (i) The adversary deletes job-w's entry; the
engineer runs revoke job-w: EXPECTED Refused 'not enrolled', nothing recorded; the adversary puts the entry back: EXPECTED W1
ADMITTED (True).  (ii) The adversary puts job-v's ENROL in job-w's place: EXPECTED Refused 'for another job'; put back: W1
ADMITTED.  (iii) The adversary writes a spoiled copy (signature changed): EXPECTED Refused 'not signed'; put back: ADMITTED.
Since c5c9832 names the row by key and job, the console could record a revocation of key:job-w without any entry; it does not.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *  # noqa

out = {}
A, B = Key(), Key()
# P1a
h = home('p1a'); fr = front(h, A.public_hex, B.public_hex)
c1, e1 = enrol(h, A, 'job-x'); out['p1a_C1_admitted'] = admitted(fr, 'job-x', c1)
put(h, 'job-x', None)
c2, e2 = enrol(h, B, 'job-x'); out['p1a_C2_admitted'] = admitted(fr, 'job-x', c2)
out['p1a_A_revokes_with_B_entry'] = attempt(lambda: front_ctl.revoke(h, 'job-x', A))
out['p1a_B_revokes'] = attempt(lambda: front_ctl.revoke(h, 'job-x', B))
out['p1a_C2_after_revoke'] = admitted(fr, 'job-x', c2)
put(h, 'job-x', e1); out['p1a_C1_after_put_back'] = admitted(fr, 'job-x', c1)
out['p1a_rows'] = {'A': row(e1), 'B': row(e2)}

# P1b
K1, K2 = Key(), Key()
h = home('p1b'); fr = front(h, K1.public_hex, K2.public_hex)
d1, f1 = enrol(h, K1, 'job-y'); out['p1b_C1_admitted'] = admitted(fr, 'job-y', d1)
out['p1b_K2_revokes_K1_job'] = attempt(lambda: front_ctl.revoke(h, 'job-y', K2)); out['p1b_row_K1_after'] = row(f1)
put(h, 'job-y', None); d2, f2 = enrol(h, K2, 'job-y'); out['p1b_C2_admitted'] = admitted(fr, 'job-y', d2)
out['p1b_K2_revokes'] = attempt(lambda: front_ctl.revoke(h, 'job-y', K2))
put(h, 'job-y', f1); out['p1b_C1_after_put_back'] = admitted(fr, 'job-y', d1)
out['p1b_rows'] = {'K1': row(f1), 'K2': row(f2)}

# P1c
h = home('p1c'); a, Au = A.public_hex, A.public_hex.upper()
fr = front(h, a); z1, g1 = enrol(h, A, 'job-z'); out['p1c_admitted'] = admitted(fr, 'job-z', z1)
out['p1c_revoke'] = attempt(lambda: front_ctl.revoke(h, 'job-z', A))
upper = dict(g1, signer=Au); first = dict(g1, signer=a[0].upper() + a[1:]) if a[0].isalpha() else dict(g1, signer=a[:1] + a[1:].upper())
out['p1c_signature_still_verifies'] = (front_door.signed_by(Au, g1['signature'], front_door.binding_message(upper)))
for pins, tag in (([a], 'pins_lower'), ([a, Au], 'pins_both')):
    fr = front(h, *pins); res = {}
    for label, b in (('upper', upper), ('first_char', first)):
        put(h, 'job-z', b); res[label] = (fr.usable('job-z', b), admitted(fr, 'job-z', z1))
    out[f'p1c_{tag}'] = res
out['p1c_upper_row'] = row_named(f'{Au}:job-z')
fr = front(h, Au); y1, gy = enrol(h, A, 'job-zz'); out['p1c_pins_upper_only_fresh_job'] = admitted(fr, 'job-zz', y1)

# P1d
h = home('p1d'); fr = front(h, A.public_hex)
w1, ew = enrol(h, A, 'job-w'); v1, ev = enrol(h, A, 'job-v'); out['p1d_W1_admitted'] = admitted(fr, 'job-w', w1)
put(h, 'job-w', None); out['p1d_i_revoke'] = attempt(lambda: front_ctl.revoke(h, 'job-w', A)); out['p1d_i_row'] = row(ew)
put(h, 'job-w', ew); out['p1d_i_after_put_back'] = admitted(fr, 'job-w', w1)
put(h, 'job-w', ev); out['p1d_ii_revoke'] = attempt(lambda: front_ctl.revoke(h, 'job-w', A))
put(h, 'job-w', ew); out['p1d_ii_after_put_back'] = admitted(fr, 'job-w', w1)
put(h, 'job-w', dict(ew, signature='00' * 64)); out['p1d_iii_revoke'] = attempt(lambda: front_ctl.revoke(h, 'job-w', A))
put(h, 'job-w', ew); out['p1d_iii_after_put_back'] = admitted(fr, 'job-w', w1); out['p1d_row_end'] = row(ew)

import json as _j
print(_j.dumps(out, indent=1, default=str))
pred = {'p1a_C1_admitted': True, 'p1a_C2_admitted': True, 'p1a_C2_after_revoke': False, 'p1a_C1_after_put_back': True,
        'p1b_C1_admitted': True, 'p1b_C2_admitted': True, 'p1b_C1_after_put_back': True,
        'p1c_admitted': True, 'p1c_signature_still_verifies': True,
        'p1c_pins_lower': {'upper': (False, False), 'first_char': (False, False)}, 'p1c_pins_both': {'upper': (False, False), 'first_char': (False, False)},
        'p1c_upper_row': None, 'p1c_pins_upper_only_fresh_job': False,
        'p1d_W1_admitted': True, 'p1d_i_after_put_back': True, 'p1d_ii_after_put_back': True, 'p1d_iii_after_put_back': True}
pred_prefix = {'p1a_A_revokes_with_B_entry': ('Refused', 'the stored binding of job-x is not signed by this engineer'), 'p1a_B_revokes': ('ok', 'REVOKE'),
               'p1b_K2_revokes_K1_job': ('Refused', 'the stored binding of job-y is not signed by this engineer'), 'p1b_K2_revokes': ('ok', 'REVOKE'),
               'p1c_revoke': ('ok', 'REVOKE'), 'p1d_i_revoke': ('Refused', 'job-w is not enrolled'),
               'p1d_ii_revoke': ('Refused', 'the stored binding of job-w is one signed for another job'), 'p1d_iii_revoke': ('Refused', 'the stored binding of job-w is not signed')}
fails = [k for k, v in pred.items() if (tuple(out[k]) if isinstance(v, tuple) else out[k]) != v and not (isinstance(v, dict) and {kk: tuple(vv) for kk, vv in out[k].items()} == v)]
fails += [k for k, (t, p) in pred_prefix.items() if not (out[k][0] == t and str(out[k][1]).startswith(p))]
for k, v in (('p1a_rows', {'A': (1, False), 'B': (2, True)}), ('p1b_rows', {'K1': (1, False), 'K2': (2, True)})):
    if {kk: vv for kk, vv in out[k].items()} != v: fails.append(k)
for k in ('p1b_row_K1_after', 'p1d_i_row'):
    if out[k] != (1, False): fails.append(k)
print('PREDICTIONS FAILED:', fails or 'none')
