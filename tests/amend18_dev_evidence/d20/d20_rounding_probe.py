"""D20 assessment (owner's decision of 22 November 2026, point 3): can the rounding of a value given to more than 28 significant
digits change a security-relevant PASS/FAIL?  In-process probe of the gate's own decision path, verify_tools._decide, with the
sandbox replaced by a stand-in that returns a chosen printed value (nothing else of the path is replaced).  The fixture's
criterion is service_temperature >= 200 C, plausible 20 to 1000.

Expectation, written before the probe is run:
  P1. In no case is the verdict PASS when the printed value is below 200 exactly, nor FAIL (LIMIT_NOT_MET) when it is at or above
      200 exactly.  Every verdict is either the side of the exact printed value or UNKNOWN (CHECK_OUTPUT_INVALID).
  P2. a  '199.99999999999999999999999999999' (32 significant digits, below; rounds to 200): UNKNOWN CHECK_OUTPUT_INVALID.
      b  '200.00000000000000000000000000001' (at or above; rounds to 200, the margin then does not recompute): UNKNOWN.
      c  '250.000000000000000000000000000001' (far above): PASS (MET), written achieved '250' (the D20 residue: written rounded).
      d  '150.000000000000000000000000000001' (far below): FAIL (LIMIT_NOT_MET), written achieved '150'.
      e  '200' exactly: PASS, margin '0'.
      f  '199.9999999999999999999999999' (28 significant digits, below; not rounded): FAIL.
      g  '200.0000000000000000000000001' (28 significant digits, above; not rounded): PASS.
  P3. Every verdict _decide returns is accepted by check_record.rederive (an empty list of problems).
"""
import json, pathlib, sys, types
REPO = pathlib.Path(sys.argv[1]).resolve()
sys.path[:0] = [str(REPO / 'verify'), str(REPO)]
import baseline, verify_tools, check_record
from baseline import sha256_hex
case = REPO / 'tests' / 'verify_case'
card = json.loads((case / 'card.json').read_text())
card['check']['sha256'] = sha256_hex((case / card['check']['file']).read_bytes())
for i in card['inputs']:
    i['sha256'] = sha256_hex((case / i['file']).read_bytes())
design = {'material': 'PPS-GF40', 'wall_mm': 3, 'mode': 'normal'}
printed = {'a': '199.99999999999999999999999999999', 'b': '200.00000000000000000000000000001', 'c': '250.000000000000000000000000000001',
           'd': '150.000000000000000000000000000001', 'e': '200', 'f': '199.9999999999999999999999999', 'g': '200.0000000000000000000000001'}
expect = {'a': ('UNKNOWN', 'CHECK_OUTPUT_INVALID'), 'b': ('UNKNOWN', 'CHECK_OUTPUT_INVALID'), 'c': ('PASS', 'MET'), 'd': ('FAIL', 'LIMIT_NOT_MET'),
          'e': ('PASS', 'MET'), 'f': ('FAIL', 'LIMIT_NOT_MET'), 'g': ('PASS', 'MET')}
out, failed = {}, []
for k, v in printed.items():
    stdout = json.dumps({'achieved': {'service_temperature': v}, 'basis': 'probe'}).replace(json.dumps(v), v)   # a JSON number, as a check prints it
    baseline.sandbox.run = lambda files, script, stdin, timeout=30.0, **kw: types.SimpleNamespace(state='RAN', returncode=0, stdout=stdout.encode(), stderr=b'', detail='')
    r = verify_tools._decide(case, card, design)
    exact = baseline.D(v) >= 200
    crit = (r.get('criteria') or [{}])[0]
    problems = check_record.rederive(card, r, design)
    side_ok = r['verdict'] == 'UNKNOWN' or (r['verdict'] == 'PASS') == exact
    out[k] = {'printed': v, 'exact_at_or_above': exact, 'verdict': r['verdict'], 'reason': r['reason_code'], 'achieved': crit.get('achieved'),
              'margin': crit.get('margin'), 'rederive_problems': problems, 'P1_side_or_unknown': side_ok}
    if not side_ok: failed.append(f'P1 {k}')
    if (r['verdict'], r['reason_code']) != expect[k]: failed.append(f'P2 {k}')
    if problems: failed.append(f'P3 {k}')
if out['c']['achieved'] != '250': failed.append('P2 c achieved')
if out['d']['achieved'] != '150': failed.append('P2 d achieved')
if out['e']['margin'] != '0': failed.append('P2 e margin')
print(json.dumps(out, indent=1))
print('PREDICTIONS FAILED: ' + repr(failed) if failed else 'ALL PREDICTIONS HELD')
