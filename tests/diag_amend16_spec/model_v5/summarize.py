#!/usr/bin/env python3
"""Summarises results/<config>.json into results/SUMMARY.md and results/SUMMARY.json."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import configs
from model import ALL_PROPS

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
rows = []
summ = {}
for n in configs.ORDER:
    p = os.path.join(out, n + '.json')
    if not os.path.exists(p):
        rows.append('| %s | (not run) |' % n)
        continue
    r = json.load(open(p))
    viol_decl = sorted(k for k, v in r['properties'].items() if v['declared'] == 'violated')
    viol_obs = sorted(k for k, v in r['properties'].items() if v['observed'] == 'violated')
    depths = ', '.join('%s:%d' % (k, r['properties'][k]['depth']) for k in viol_obs)
    pm = [k for k in r['mismatches'] if k.startswith('P_')]
    prm = [k for k in r['mismatches'] if not k.startswith('P_')]
    rows.append('| %s | %s | %s | %d | %s | %s | %s | %s |' % (
        n, ', '.join(viol_decl) or '-', ', '.join(viol_obs) or '-', r['states'],
        'complete' if r['complete'] else 'INCOMPLETE', depths or '-',
        'yes' if not r['mismatches'] else 'NO: ' + ', '.join(r['mismatches']), '%.0fs' % r['wall_seconds']))
    summ[n] = dict(states=r['states'], complete=r['complete'], declared_violated=viol_decl,
                   observed_violated=viol_obs, mismatches=r['mismatches'], secs=r['wall_seconds'],
                   probes={k: v['observed'] for k, v in r['probes'].items()})
hdr = ('| config | declared violated | observed violated | states | search | shortest trace length | '
       'declared = observed | time |\n|---|---|---|---|---|---|---|---|')
with open(os.path.join(out, 'SUMMARY.md'), 'w') as f:
    f.write(hdr + '\n' + '\n'.join(rows) + '\n')
with open(os.path.join(out, 'SUMMARY.json'), 'w') as f:
    json.dump(summ, f, indent=1)
print(hdr)
print('\n'.join(rows))
