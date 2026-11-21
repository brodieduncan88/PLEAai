#!/usr/bin/env python3
"""Declared verdicts for model5 (specification v6), written BEFORE any verdict run."""
import json, os, hashlib, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import configs
from model import ALL_PROPS
H, V, NA, RE, NR = 'holds', 'violated', 'n/a', 'reached', 'not_reached'
def props(viol):
    d = {p: (V if p in viol else H) for p in ALL_PROPS}; d['SAF8'] = NA; return d
W = dict(P_COVERED=RE, P_WIPE=RE, P_MAILBOX_ROLLBACK=RE, P_COVERED_AFTER_MBLOST=RE)
WF = dict(W, P_OWN_ANCHOR_FORK=RE)
D = {
 'FD_WIPE': (props(set()), W), 'FD_WIPE_L': (props(set()), W), 'FD_WIPE_FORK': (props(set()), WF),
 'FD_WIPE_FORK_L': (props(set()), WF), 'FD_WIPE_FORK_INC': (props(set()), dict(WF, P_COVERED_INC=RE)),
 'FD_WIPE_BOTHLOST': (props({'SAF10_L10'}), dict(P_COVERED=RE, P_WIPE=RE, P_WIPE_THEN_COVERED=RE)),
 'FD_FORK': (props(set()), dict(P_COVERED=RE, P_FORK_ALARM=RE, P_ROLLBACK_ALARM=RE, P_ST6_FAIL=NR)),
 'FD_FORK_L': (props(set()), dict(P_COVERED=RE, P_FORK_ALARM=RE, P_ROLLBACK_ALARM=RE, P_COVERED_AFTER_LOST=RE)),
 'FD_RESTORE': (props(set()), dict(P_COVERED=RE, P_RESTORE=RE, P_COVERED_AFTER_LOST=RE)),
 'FD_RESTORE_L': (props(set()), dict(P_COVERED=RE, P_RESTORE=RE, P_COVERED_AFTER_LOST=RE)),
 'FD_RESTORE_FORK': (props(set()), dict(P_COVERED=RE, P_RESTORE=RE, P_FORK_ALARM=RE)),
 'FD_WIPE_RESTORE_FORK': (props({'SAF10_L10'}), dict(P_COVERED=RE, P_RESTORE=RE, P_WIPE=RE)),
 'FD_CHAIN': (props(set()), dict(P_COVERED=RE, P_EPOCH_STALE=RE, P_LINK=RE)),
 'FD_EPOCH': (props(set()), dict(P_COVERED=RE, P_COVERED_AFTER_REBOOT=RE, P_COVERED_AFTER_RESTART=RE)),
 'FD_QUOTA_NOTICE': (props(set()), dict(P_COVERED=RE, P_ROOM_NOTICE=RE, P_ALARM_AFTER_ROOM_REFUSAL=RE)),
}
MUT = {'MU_OA_LOWER_ON_REFUSAL': {'SAF10'}, 'MU_OA_NOT_INC': set(), 'MU_OA_DROP_IE4': {'SAF10'},
       'MU_IOA_UNANSWERED': set(), 'MU_NO_OWN_ANCHOR': {'SAF10'}}
for n, extra in MUT.items():
    bp, _ = D[configs.MUTANTS[n][0]]
    p2 = dict(bp)
    for e in extra: p2[e] = V
    D[n] = (p2, {})
assert set(D) == set(configs.CONFIGS)
dd = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'declared'); os.makedirs(dd, exist_ok=True)
lines = []
for n in configs.ORDER:
    p, pr = D[n]
    b = json.dumps(dict(config=n, properties=p, probes=pr, model='model5', spec='v6'), indent=1, sort_keys=True).encode()
    path = os.path.join(dd, n + '.json')
    if os.path.exists(path) and open(path, 'rb').read() != b: sys.exit('exists and differs ' + n)
    open(path, 'wb').write(b); lines.append('%s  %s.json' % (hashlib.sha256(b).hexdigest(), n))
open(os.path.join(dd, 'SHA256SUMS'), 'w').write('\n'.join(lines) + '\n'); print('declared', len(lines))
