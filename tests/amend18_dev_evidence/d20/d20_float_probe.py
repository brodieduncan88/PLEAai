"""D20 assessment, second probe, written after the first (d20_rounding_probe.py) failed its predictions and before this one is
run.  The first showed that a JSON number printed by the check is read by json.loads as a binary float, so a value closer to the
limit than a float can tell apart becomes the limit before it is compared.  This probe maps that, on the same path
(verify_tools._decide with the sandbox replaced by a stand-in that returns the printed bytes).  Criterion: >= 200 C.

Expectation, written before the probe is run:
  Q1. JSON numbers just below 200, by 1e-13 ('199.9999999999999') and 1e-12: FAIL (a float holds them apart from 200).
  Q2. JSON numbers just below 200 by 1e-14 and 1e-15 ('199.99999999999999', '199.999999999999999'): PASS with achieved '200'
      (the float rounds them to 200.0): a false PASS, accepted by check_record.rederive.
  Q3. The same values as JSON strings (the check prints "199.99999999999999"): FAIL, decided on the exact decimal, for every
      value below 200 with at most 28 significant digits; a string below 200 with more than 28 significant digits is
      UNKNOWN (CHECK_OUTPUT_INVALID), never PASS.
  Q4. For a <= criterion the same happens mirrored: a JSON number just above the limit by 1e-14 is PASS (checked on a copy of
      the card with comparison '<=' and limit '200').
  Q5. check_record.rederive accepts every verdict the path returns (so a false PASS of Q2 or Q4 leaves a record that verifies).
"""
import copy, json, pathlib, sys, types
REPO = pathlib.Path(sys.argv[1]).resolve()
sys.path[:0] = [str(REPO / 'verify'), str(REPO)]
import baseline, verify_tools, check_record
from baseline import sha256_hex
case = REPO / 'tests' / 'verify_case'
card = json.loads((case / 'card.json').read_text())
card['check']['sha256'] = sha256_hex((case / card['check']['file']).read_bytes())
for i in card['inputs']:
    i['sha256'] = sha256_hex((case / i['file']).read_bytes())
le = copy.deepcopy(card); le['criteria'][0]['comparison'] = '<='
design = {'material': 'PPS-GF40', 'wall_mm': 3, 'mode': 'normal'}
def decide(c, raw):
    stdout = '{"achieved": {"service_temperature": %s}, "basis": "probe"}' % raw
    baseline.sandbox.run = lambda files, script, stdin, timeout=30.0, **kw: types.SimpleNamespace(state='RAN', returncode=0, stdout=stdout.encode(), stderr=b'', detail='')
    r = verify_tools._decide(case, c, design)
    return {'printed': raw, 'verdict': r['verdict'], 'reason': r['reason_code'], 'achieved': (r.get('criteria') or [{}])[0].get('achieved'),
            'rederive_problems': check_record.rederive(c, r, design)}
below = ['199.999999999999', '199.9999999999999', '199.99999999999999', '199.999999999999999', '199.9999999999999999999999999',
         '199.99999999999999999999999999999']
out = {'number': [decide(card, v) for v in below], 'string': [decide(card, json.dumps(v)) for v in below],
       'le_number_above': [decide(le, v) for v in ('200.0000000000001', '200.00000000000001', '200.000000000000001')]}
failed = []
n = {x['printed']: x for x in out['number']}
for v in ('199.999999999999', '199.9999999999999'):
    if n[v]['verdict'] != 'FAIL': failed.append(f'Q1 {v}')
for v in ('199.99999999999999', '199.999999999999999'):
    if (n[v]['verdict'], n[v]['achieved']) != ('PASS', '200'): failed.append(f'Q2 {v}')
for x in out['string']:
    digits = len(x['printed'].strip('"').replace('.', '').lstrip('0'))
    want = 'FAIL' if digits <= 28 else 'UNKNOWN'
    if x['verdict'] != want: failed.append(f"Q3 {x['printed']} -> {x['verdict']}")
le_ = {x['printed']: x for x in out['le_number_above']}
if le_['200.00000000000001']['verdict'] != 'PASS': failed.append('Q4')
for group in out.values():
    for x in group:
        if x['rederive_problems']: failed.append(f"Q5 {x['printed']}")
print(json.dumps(out, indent=1))
print('PREDICTIONS FAILED: ' + repr(failed) if failed else 'ALL PREDICTIONS HELD')
