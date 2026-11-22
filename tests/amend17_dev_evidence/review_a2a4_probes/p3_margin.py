"""P3 (review A3). Expectation written before the run: a check that prints 29 significant digits, far from the limit, gives
controls that check_record.control_problems accepts (so make_baseline would baseline it), while rederive() -- the rule every
run is put to by verify_tools -- rejects the same verdicts (margin does not recompute), so every run of such a check is UNKNOWN.
PREDICTION: problems == []; rederive(control PA66) != []; rederive(run PPS-GF40) != [].
The sandbox is replaced in this process by a stub that prints the chosen value; evaluate() is otherwise the real code."""
import sys, json, types, hashlib
W = sys.argv[1]; sys.path.insert(0, W); sys.path.insert(0, W + '/verify')
import baseline as B, check_record
VAL = {'PA66-GF30': '123.45678901234567890123456789', 'PPS-GF40': '345.67890123456789012345678901', 'PEEK': '345.67890123456789012345678901'}
def run(files, name, stdin, timeout=None):
    d = json.loads(stdin)
    return types.SimpleNamespace(state='OK', returncode=0, stderr=b'', detail='', stdout=json.dumps({'achieved': {'service_temperature': VAL[d['material']]}, 'basis': 'stub'}).encode())
B.sandbox.run = run
card = json.load(open(W + '/tests/verify_case/card.json'))
card['check']['sha256'] = B.sha256_hex(open(W + '/tests/verify_case/check.py', 'rb').read())
card['inputs'] = [{'file': 'materials.csv', 'sha256': B.sha256_hex(open(W + '/tests/verify_case/materials.csv', 'rb').read())}]
src = W + '/tests/verify_case'
controls_run = []
for c in card['controls']:
    v = B.evaluate(src, card, c['design'], control=True)
    controls_run.append({'name': c['name'], 'expect': c['expect'], 'verdict': v['verdict'], 'reason_code': v['reason_code'],
                         'criteria': [{'id': k['id'], 'achieved': k['achieved'], 'limit': k['limit'], 'met': k['met']} for k in v['criteria']]})
    if c['name'].startswith('PA66'):
        ctl_rederive = check_record.rederive(card, v, c['design'])
problems = check_record.control_problems(card, controls_run)
design = {'material': 'PPS-GF40', 'wall_mm': 3, 'mode': 'normal'}
r = B.evaluate(src, card, design)
print(json.dumps({'controls_run': controls_run, 'control_problems': problems, 'rederive_control_PA66': ctl_rederive,
                  'run_PPS': {'verdict': r['verdict'], 'margin': r['criteria'][0]['margin'], 'achieved': r['criteria'][0]['achieved']},
                  'rederive_run_PPS': check_record.rederive(card, r, design)}, indent=1))
