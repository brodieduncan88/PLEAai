"""Amendment 19 (D20-F).  The decision path, verify_tools._decide, put to a matrix of printed numbers, with the sandbox replaced by
a stand-in that returns the check's printed bytes (nothing else of the path is replaced).  Run with the tree to test as argv[1]
and the label of the expectation set as argv[2] ('before' for the uncorrected tree, 'after' for the corrected one).

Three criteria: GE (service_temperature >= 200, plausible 20 to 1000), LE (the same, <= 200), NEG (>= -5, plausible -100 to 100).

Expectations, written before any run:
  'before' (2c1af26, uncorrected): the D20-F false PASS reproduces: GE '199.99999999999999' and LE '200.00000000000001', printed as
     JSON numbers, are PASS with achieved '200', and check_record.rederive accepts them.  (Only these two are asserted for 'before';
     the rest is recorded as it comes out.)
  'after' (the corrected tree):
     A1  no case is PASS unless its exact printed value meets the criterion (the property the owner asks for);
     A2  every PASS and FAIL is accepted by check_record.rederive;
     A3  the listed cases give the listed (verdict, reason);
     A4  every verdict's text (canonical JSON) is under 64 KiB.
"""
import copy, decimal, json, pathlib, sys, types
REPO = pathlib.Path(sys.argv[1]).resolve(); WHICH = sys.argv[2]
sys.path[:0] = [str(REPO / 'verify'), str(REPO)]
import baseline, verify_tools, check_record
from baseline import sha256_hex, canonical
case = REPO / 'tests' / 'verify_case'
GE = json.loads((case / 'card.json').read_text())
GE['check']['sha256'] = sha256_hex((case / GE['check']['file']).read_bytes())
for i in GE['inputs']:
    i['sha256'] = sha256_hex((case / i['file']).read_bytes())
LE = copy.deepcopy(GE); LE['criteria'][0]['comparison'] = '<='
NEG = copy.deepcopy(GE); NEG['criteria'][0].update(limit='-5', plausible={'min': '-100', 'max': '100'})
cards = {'GE': GE, 'LE': LE, 'NEG': NEG}
design = {'material': 'PPS-GF40', 'wall_mm': 3, 'mode': 'normal'}
P, F, U = 'PASS', 'FAIL', 'UNKNOWN'
cases = [  # (criterion, token as printed, expected (verdict, reason) after the correction)
    ('GE', '200', (P, 'MET')), ('GE', '200.0', (P, 'MET')), ('GE', '2e2', (P, 'MET')), ('GE', '2E+2', (P, 'MET')), ('GE', '0.2e3', (P, 'MET')),
    ('GE', '199.99999999999999', (F, 'LIMIT_NOT_MET')), ('GE', '199.999999999999999', (F, 'LIMIT_NOT_MET')),
    ('GE', '200.00000000000001', (P, 'MET')), ('GE', '1.9999999999999999e2', (F, 'LIMIT_NOT_MET')), ('GE', '2.0000000000000001e2', (P, 'MET')),
    ('GE', '199.9999999999999999999999999', (F, 'LIMIT_NOT_MET')), ('GE', '200.0000000000000000000000001', (P, 'MET')),
    ('GE', '199.99999999999999999999999999999', (U, 'CHECK_OUTPUT_INVALID')), ('GE', '200.00000000000000000000000000001', (U, 'CHECK_OUTPUT_INVALID')),
    ('GE', '199.' + '9' * 1000, (U, 'CHECK_OUTPUT_INVALID')), ('GE', '250.000000000000000000000000000001', (P, 'MET')),
    ('GE', '199', (F, 'LIMIT_NOT_MET')), ('GE', '201', (P, 'MET')), ('GE', '2' + '0' * 30, (U, 'RESULT_IMPLAUSIBLE')),
    ('GE', '1e999999', (U, None)), ('GE', '1e1000000', (U, None)), ('GE', '1e-999999', (U, None)), ('GE', '-1e999999', (U, None)),
    ('GE', 'NaN', (U, 'CHECK_OUTPUT_INVALID')), ('GE', 'Infinity', (U, 'CHECK_OUTPUT_INVALID')), ('GE', '-Infinity', (U, 'CHECK_OUTPUT_INVALID')),
    ('GE', '1e', (U, 'CHECK_OUTPUT_INVALID')), ('GE', '--1', (U, 'CHECK_OUTPUT_INVALID')), ('GE', '01', (U, 'CHECK_OUTPUT_INVALID')),
    ('GE', '"199.99999999999999"', (F, 'LIMIT_NOT_MET')), ('GE', '"200"', (P, 'MET')), ('GE', 'true', (U, 'CHECK_OUTPUT_INVALID')),
    ('LE', '200', (P, 'MET')), ('LE', '200.00000000000001', (F, 'LIMIT_NOT_MET')), ('LE', '199.99999999999999', (P, 'MET')),
    ('LE', '2.0000000000000001e2', (F, 'LIMIT_NOT_MET')),
    ('NEG', '-5', (P, 'MET')), ('NEG', '-5.0', (P, 'MET')), ('NEG', '-5.00000000000000001', (F, 'LIMIT_NOT_MET')),
    ('NEG', '-4.99999999999999999', (P, 'MET')), ('NEG', '-5e0', (P, 'MET')), ('NEG', '-0.5e1', (P, 'MET')),
]
def meets(card, token):
    try:
        v = decimal.Decimal(json.loads(token, parse_float=decimal.Decimal, parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))) if not token.startswith('"') else decimal.Decimal(json.loads(token))
    except Exception:
        return None
    if not v.is_finite():
        return None
    c = card['criteria'][0]; lim = decimal.Decimal(c['limit'])
    return v >= lim if c['comparison'] == '>=' else v <= lim
out, failed = [], []
for crit, token, want in cases:
    card = cards[crit]
    stdout = '{"achieved": {"service_temperature": %s}, "basis": "probe"}' % token
    baseline.sandbox.run = lambda files, script, stdin, timeout=30.0, _s=stdout, **kw: types.SimpleNamespace(state='RAN', returncode=0, stdout=_s.encode(), stderr=b'', detail='')
    try:
        r = verify_tools._decide(case, card, design); err = None
    except Exception as exc:
        r, err = None, f'{type(exc).__name__}: {exc}'[:200]
    row = {'criterion': crit, 'token': token if len(token) <= 60 else token[:40] + f'... ({len(token)} chars)', 'exact_meets': meets(card, token), 'expected_after': want, 'raised': err}
    if r is not None:
        size = len(canonical(r).encode())
        row.update(verdict=r['verdict'], reason=r['reason_code'], achieved=(r.get('criteria') or [{}])[0].get('achieved'), detail_len=len(r.get('detail') or ''),
                   verdict_bytes=size, rederive=check_record.rederive(card, r, design))
        if isinstance(row['achieved'], str) and len(row['achieved']) > 60:
            row['achieved'] = row['achieved'][:40] + f'... ({len(row["achieved"])} chars)'
    out.append(row)
    if WHICH == 'after':
        if r is None: failed.append(f'raised {crit} {row["token"]}'); continue
        if r['verdict'] == P and row['exact_meets'] is not True: failed.append(f'A1 {crit} {row["token"]}')
        if r['verdict'] in (P, F) and row['rederive']: failed.append(f'A2 {crit} {row["token"]}')
        if r['verdict'] != want[0] or (want[1] is not None and r['reason_code'] != want[1]): failed.append(f'A3 {crit} {row["token"]} -> {r["verdict"]} {r["reason_code"]}')
        if row['verdict_bytes'] >= 65536: failed.append(f'A4 {crit} {row["token"]} {row["verdict_bytes"]} bytes')
if WHICH == 'before':
    rows = {(x['criterion'], x['token']): x for x in out}
    for k in (('GE', '199.99999999999999'), ('LE', '200.00000000000001')):
        x = rows[k]
        if (x.get('verdict'), x.get('achieved'), x.get('rederive')) != ('PASS', '200', []): failed.append(f'before {k}')
print(json.dumps(out, indent=1, default=str))
print('PREDICTIONS FAILED: ' + repr(failed) if failed else 'ALL PREDICTIONS HELD')
