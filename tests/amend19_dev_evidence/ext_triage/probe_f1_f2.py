"""Triage of the external review's F-1 and F-2 at b97fe6b, in process, no services.
Expectations, written before running:
 F-1a validate_card accepts a card whose plausible min is the JSON float 0.3 and whose design_space min/max are floats 1e23/2e23.
 F-1b with that card, the in-process verdict for achieved 0.29999999999999999 (below 0.3) is MET, and check_record.rederive finds no problem.
 F-1c the integer design 99999999999999995000000 (below 10**23) is inside the design space by both baseline and check_record.
 F-1d the exact design 0.3 is refused against a float max 0.3 (boundary wrongly refused) -- checked with a second card.
 F-2  check_record's CLI path (json.load) hashes {"wall_mm": 1.9999999999999999} equal to {"wall_mm": 2.0}, and keeps the last of duplicate keys.
"""
import copy, decimal, json, sys
sys.path.insert(0, sys.argv[1] + '/verify')
import baseline as B, check_record as C
card = json.loads(open(sys.argv[1] + '/verify/cases/pump-station-submain/card.json').read())
card = json.loads(json.dumps(card).replace('"min": "0.2"', '"min": 0.3'))      # coordination plausible min as a JSON float
card['criteria'] = [card['criteria'][1]]
card['design_space'] = {'x': {'min': 1e23, 'max': 2e23}}
card['check']['sha256'] = '0' * 64
card = json.loads(json.dumps(card))                                              # as a signed card is read back
try: B.validate_card(card); print('F-1a validate_card accepted float bounds:', type(card['criteria'][0]['plausible']['min']).__name__, type(card['design_space']['x']['min']).__name__)
except Exception as e: print('F-1a refused:', e)
design = {'x': 99999999999999995000000}
print('F-1c below 10**23:', design['x'] < 10**23, '| baseline inside:', B.in_design_space(card, design), '| check_record inside:', C.in_design_space(card, design))
value = decimal.Decimal('0.29999999999999999')
c = card['criteria'][0]
print('F-1b value < 0.3:', value < decimal.Decimal('0.3'), '| plausible test passes:', B.D(c['plausible']['min']) <= value <= B.D(c['plausible']['max']))
met, margin = B.compare(c, value)
v = B._verdict(card, design, 'MET' if met else 'LIMIT_NOT_MET', [{'id': c['id'], 'quantity': c['quantity'], 'comparison': c['comparison'], 'limit': c['limit'], 'units': c['units'], 'achieved': B.text(value), 'margin': margin, 'met': met}])
v = json.loads(B.canonical(v)) if hasattr(B, 'canonical') else json.loads(json.dumps(v))
print('F-1b verdict:', v['verdict'], v['reason_code'], '| rederive problems:', C.rederive(card, v, design))
card2 = json.loads(json.dumps(dict(card, design_space={'w': {'min': 0.1, 'max': 0.3}})))
print('F-1d exact 0.3 inside [0.1, 0.3]:', B.in_design_space(card2, {'w': 0.3}), '| exact 0.1:', B.in_design_space(card2, {'w': 0.1}))
a = json.loads('{"wall_mm": 1.9999999999999999}'); b = json.loads('{"wall_mm": 2.0}'); d = json.loads('{"wall_mm": 999, "wall_mm": 2.0}')
print('F-2 hash equal (rounded):', C.sha(C.canonical(a)) == C.sha(C.canonical(b)), '| duplicate keys read as:', d)
