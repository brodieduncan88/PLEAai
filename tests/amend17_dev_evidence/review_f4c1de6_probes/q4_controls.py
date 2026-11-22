"""Q4 (review 3).  Expectation written before the run.  The control loop of verify_ctl.make_baseline at f4c1de6 (evaluate with
control=True, rederive(control=True), control_problems), with the sandbox replaced by a stub printing the PA66 and PEEK values:
  across  PA66 = 199.99999999999999999999999999999            -> refused, includes 'does not follow from its recorded numbers'
  many    PA66 = 180.000000000000000000000000000001           -> []   (R32 check 2 needs it baselined)
  run     PA66 = 180                                          -> []
  far     PA66 = 123.45678901234567890123456789               -> includes 'margin does not recompute'
  plain   PA66 = 180, PEEK = 250                              -> []
  edge28  PA66 = 20.00000000000000000000000001 (28 digits, margin needs 29) -> []
  peek29  PEEK = 345.67890123456789012345678901 (29 digits, the PASS control)  -> includes 'margin does not recompute'"""
import sys, json, types
W = sys.argv[1]; sys.path.insert(0, W); sys.path.insert(0, W + '/verify')
import baseline as B, check_record
CASES = {'across': {'PA66-GF30': '199.99999999999999999999999999999'}, 'many': {'PA66-GF30': '180.000000000000000000000000000001'},
         'run': {'PA66-GF30': '180'}, 'far': {'PA66-GF30': '123.45678901234567890123456789'}, 'plain': {},
         'edge28': {'PA66-GF30': '20.00000000000000000000000001'}, 'peek29': {'PEEK': '345.67890123456789012345678901'}}
card = json.load(open(W + '/tests/verify_case/card.json'))
card['check']['sha256'] = B.sha256_hex(open(W + '/tests/verify_case/check.py', 'rb').read())
card['inputs'] = [{'file': 'materials.csv', 'sha256': B.sha256_hex(open(W + '/tests/verify_case/materials.csv', 'rb').read())}]
out = {}
for tag, vals in CASES.items():
    VAL = dict({'PA66-GF30': '180', 'PPS-GF40': '220', 'PEEK': '250'}, **vals)
    B.sandbox.run = lambda files, name, stdin, timeout=None: types.SimpleNamespace(state='OK', returncode=0, stderr=b'', detail='',
        stdout=json.dumps({'achieved': {'service_temperature': VAL[json.loads(stdin)['material']]}, 'basis': 'stub'}).encode())
    controls_run, rederived = [], []
    for c in card['controls']:
        v = B.evaluate(W + '/tests/verify_case', card, c['design'], control=True)
        rederived += [f'control "{c["name"]}": {p}' for p in check_record.rederive(card, v, c['design'], control=True)]
        controls_run.append({'name': c['name'], 'expect': c['expect'], 'verdict': v['verdict'], 'reason_code': v['reason_code'],
                             'criteria': [{'id': k['id'], 'achieved': k['achieved'], 'limit': k['limit'], 'met': k['met']} for k in v['criteria']]})
    out[tag] = {'verdicts': [c['verdict'] for c in controls_run], 'problems': check_record.control_problems(card, controls_run) + rederived}
print(json.dumps(out, indent=1))
