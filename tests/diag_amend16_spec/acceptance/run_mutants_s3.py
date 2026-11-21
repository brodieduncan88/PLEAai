#!/usr/bin/env python3
"""Planted defects in the section 3 TEST ORACLE, one at a time: each must make at least one section 3 test FAIL.
Writes results/mutants_s3.json.  ACC-2 applies: this is evidence about the tests, not about any implementation."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import acc  # noqa: E402
import oracle_s3  # noqa: E402

out, survivors = {}, []
print(acc.ACC2)
for m, what in oracle_s3.MUTANTS.items():
    name = f'mutant-{m}'
    env = dict(os.environ, ORACLE_MUTANT=m)
    subprocess.run([sys.executable, os.path.join(HERE, 'run_acceptance.py'), '--adapter', 'sut_oracle_s3', '--filter', 'S3-',
                    '--name', 'mutants/' + name], env=env, capture_output=True, text=True)
    files = sorted((f for f in os.listdir(os.path.join(HERE, 'results', 'mutants')) if f.startswith(name) and f.endswith('.json')),
                   key=lambda f: os.path.getmtime(os.path.join(HERE, 'results', 'mutants', f)))
    res = json.load(open(os.path.join(HERE, 'results', 'mutants', files[-1])))['results']
    killed = [r['id'] for r in res if r['outcome'] == 'FAIL']
    errors = [r['id'] for r in res if r['outcome'] == 'ERROR']
    out[m] = {'defect': what, 'caught_by': killed, 'errors': errors}
    print(f"{'CAUGHT ' if killed else 'SURVIVES'} {m:<28} by {len(killed)}: {', '.join(killed[:6])}{' ...' if len(killed) > 6 else ''}{'  ERRORS ' + str(errors) if errors else ''}")
    if not killed:
        survivors.append(m)
json.dump({'acc2': acc.ACC2, 'mutants': out, 'survivors': survivors}, open(os.path.join(HERE, 'results', 'mutants', 'mutants_s3.json'), 'w'), indent=1)
print('survivors:', survivors or 'none')
print(acc.ACC2)
