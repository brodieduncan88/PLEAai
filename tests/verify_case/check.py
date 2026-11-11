"""The self-test check: a material's continuous-use temperature from a table.  `mode` makes it misbehave on purpose."""
import csv
import json
import pathlib
import sys
import time

design = json.load(sys.stdin)
rows = {r['material']: r for r in csv.DictReader(open(pathlib.Path(__file__).parent / 'materials.csv'))}
mode = design.get('mode', 'normal')
if mode == 'crash':
    raise SystemExit('deliberate crash')
if mode == 'garbage':
    print('not json'); sys.exit(0)
if mode == 'hang':
    time.sleep(600)
value = float(rows[design['material']]['max_service_c'])
if mode == 'nan':
    print('{"achieved": {"service_temperature": NaN}, "basis": "nan"}'); sys.exit(0)
if mode == 'zero':
    value = 0.0
if mode == 'huge':
    value = 1e9
print(json.dumps({'achieved': {'service_temperature': value}, 'basis': f"limited by the continuous-use rating of {design['material']}: {value:g} C"}))
