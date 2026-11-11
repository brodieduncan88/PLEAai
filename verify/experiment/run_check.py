#!/usr/bin/env python3
"""Run the design check for this job.

    python3 run_check.py [design.json]

Reads the design, runs the calculation in calc/check.py, and compares each result with the acceptance limits in
requirements/limits.json.
"""
import json
import pathlib
import subprocess
import sys

here = pathlib.Path(__file__).resolve().parent
design_file = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else here / 'design.json'
limits = json.loads((here / 'requirements' / 'limits.json').read_text())
design = json.loads(design_file.read_text())
run = subprocess.run([sys.executable, str(here / 'calc' / 'check.py')], input=json.dumps(design).encode(), capture_output=True)
if run.returncode != 0:
    print(run.stderr.decode().strip() or 'the calculation failed')
    sys.exit(2)
result = json.loads(run.stdout)
ok = True
print('Design: ' + ', '.join(f'{k} = {v}' for k, v in design.items()))
for c in limits['criteria']:
    value, limit = float(result['achieved'][c['id']]), float(c['limit'])
    met = value <= limit if c['comparison'] == '<=' else value >= limit
    ok = ok and met
    print(f"  {c['quantity']}: {value:.4g} {c['units']}   limit {c['comparison']} {c['limit']} {c['units']}   {'OK' if met else 'NOT OK'}")
print(f"  basis: {result.get('basis', '')}")
print('RESULT: ' + ('PASS' if ok else 'FAIL'))
sys.exit(0 if ok else 1)
