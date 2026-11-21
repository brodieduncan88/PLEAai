#!/usr/bin/env python3
"""UNDECLARED diagnostic (not part of the declared suite): for the tick/epoch mutants, is there a
reachable state where a statement is counted, or a status is COVERED, on a token whose TRUE age
is more than L (an under-counted age, as opposed to SAF-1's "of another mailbox epoch")?
Usage: diag_age.py CONFIG [CONFIG ...]; writes results/diag_age.json."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import configs, model
from model import *


class DiagModel(model.Model):
    def dl6_statement(self, rt, mb, L, gh, mid, m, newA, ev):
        r = super().dl6_statement(rt, mb, L, gh, mid, m, newA, ev)
        if 'ACCEPT' in r[2]:
            t = self.tok(mb, m[6])
            if rt - t[T_RT] > self.c['L']:
                r[2].append('D_ACCEPT_TRUE_AGE_GT_L')
        return r

    def state_checks_raw(self, s):
        out = super().state_checks_raw(s)
        S = self.c1_covered(s[0], s[1])
        if S is not None:
            t = self.tok(s[1], S[S_TOK])
            if s[0] - t[T_RT] > self.c['L']:
                out.append('D_COVERED_TRUE_AGE_GT_L')
        return out


res = {}
for name in sys.argv[1:]:
    m = DiagModel(configs.CONFIGS[name])
    r = model.bfs(m, m.c['MAX_STATES'])
    res[name] = dict(states=r['states'], complete=r['complete'])
    for k in ('D_ACCEPT_TRUE_AGE_GT_L', 'D_COVERED_TRUE_AGE_GT_L'):
        if k in r['first']:
            res[name][k] = model.trace_to(m, r, k)
        else:
            res[name][k] = 'not reached' if r['complete'] else 'not reached (INCOMPLETE)'
    print(name, json.dumps(res[name], indent=1))
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results', 'diag_age.json')
json.dump(res, open(out, 'w'), indent=1)
