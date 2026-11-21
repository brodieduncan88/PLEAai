#!/usr/bin/env python3
"""Writes the declared verdicts (declared/<config>.json) BEFORE any run, and declared/SHA256SUMS.
Version 2 (configs.py version 2). Version 1 is kept in declared_v1/ (one run, FD_STATUS v1,
INCOMPLETE, was made against it; see results/run0_first_attempt/).

Each declaration gives, for every property, 'holds' or 'violated' (or 'n/a'), and for the probes
that are the purpose of the configuration 'reached' or 'not_reached'. Probes not listed are
informational ('any'): reported, not compared.
"""
import json, os, hashlib, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import configs
from model import ALL_PROPS

H, V, NA = 'holds', 'violated', 'n/a'
RE, NR = 'reached', 'not_reached'


def props(viol, reader=False):
    d = {p: (V if p in viol else H) for p in ALL_PROPS}
    d['SAF8'] = (V if 'SAF8' in viol else H) if reader else NA
    return d


F = {'R_AT_STATUS', 'C1_VS_82'}        # finding properties: expected violated where INCREMENTAL can run
REPLAY = {'SAF5'}                      # literal DL-3: a replayed EPOCH_OPEN re-opens the chain epoch
SKIP = {'SAF2', 'CENT_N'}              # literal DL-2: a linked item moves the head over a missing item

P = {}
P['CHAIN_FD'] = dict(P_COVERED=RE, P_COVERED_INC=RE, P_COVERED_AFTER_LOST=RE, P_LINK=RE,
                     P_DL3_STMT_TOKEN_KEPT=RE, P_OPEN_LOST=RE, P_STMT_REDELIVER_409=RE,
                     P_COURIER_LOST_REFUSAL=RE, P_EPOCH_REOPEN=RE, P_LINK_SKIP=RE, P_MS1=RE, P_ST5_FAIL=RE)
P['CHAIN_AR'] = dict(P['CHAIN_FD'], P_EPOCH_REOPEN=NR, P_LINK_SKIP=NR, P_MS1=NR)
del P['CHAIN_AR']['P_ST5_FAIL']
P['RESTORE'] = dict(P_COVERED=RE, P_RESTORE=RE, P_COVERED_AFTER_LOST=RE, P_COURIER_LOST_REFUSAL=RE,
                    P_OPEN_LOST=RE)
P['EPOCH'] = dict(P_COVERED=RE, P_COVERED_AFTER_REBOOT=RE, P_COVERED_AFTER_RESTART=RE,
                  P_COVERED_REFRESH_NEWMEP=RE, P_EXPIRED_STMT=RE, P_ANOMALY_AGE=RE)
P['SUSP'] = dict(P_COVERED=RE, P_EXPIRED_STMT=RE, P_ANOMALY_AGE=RE)
P['XB'] = dict(P_COVERED=RE, P_EVICT=RE, P_XB_REFUSED=RE, P_REPLAY_STMT_422=RE, P_XB_SPENT=NR)
P['ALARM'] = dict(P_COVERED=RE, P_COVERED_INC=RE, P_NOTCOV_BY_ALARM=RE, P_ALARM_LINKED=RE, P_L3_READ=RE)
P['EVID_FD'] = dict(P_COVERED=RE, P_GAP=RE, P_GAP_CLOSED=NR, P_EVMISSING=RE, P_ORPHAN=RE)
P['EVID_AR'] = dict(P['EVID_FD'], P_GAP_CLOSED=RE)
P['SKIPEV_FD'] = dict(P_COVERED=RE, P_ORPHAN=RE, P_LINK_SKIP=RE)
P['SKIPEV_AR'] = dict(P_COVERED=RE, P_ORPHAN=RE, P_LINK_SKIP=NR)

D = {}
D['FD_CHAIN'] = (props(F | REPLAY | SKIP), P['CHAIN_FD'])
D['FD_CHAIN_L'] = (props(F | REPLAY | SKIP), P['CHAIN_FD'])
D['FD_RESTORE'] = (props(F | REPLAY), P['RESTORE'])
D['FD_EPOCH'] = (props(F | REPLAY), P['EPOCH'])
D['FD_EPOCH_L'] = (props(F | REPLAY), P['EPOCH'])
D['FD_SUSP'] = (props(F | REPLAY), P['SUSP'])
D['FD_XB'] = (props(F | REPLAY), P['XB'])
D['FD_XB_SHAREDKEY'] = (props(F | REPLAY), dict(P['XB'], P_XB_SPENT=RE))
D['FD_ALARM'] = (props(F | REPLAY | {'SAF7'}), P['ALARM'])
D['FD_EVID'] = (props({'C1_VS_82'} | REPLAY), P['EVID_FD'])          # no settled value: no INCREMENTAL
D['FD_SKIPEV'] = (props(F | REPLAY | SKIP | {'CENT_E'}), P['SKIPEV_FD'])
D['FD_STATUS'] = (props(F | REPLAY, reader=True), dict(P_COVERED=RE, P_READER_COVERED=RE,
                                                       P_STALE_STATUS_REJECTED=RE))
D['FD_QUOTA'] = (props({'C1_VS_82'} | REPLAY), dict(P_COVERED=RE, P_ITEMS_REFUSED=RE, P_EPOCH_REOPEN=RE))
D['FD_WIPE'] = (props(F | REPLAY), dict(P_COVERED=RE, P_WIPE=RE, P_COVERED_AFTER_LOST=RE))
D['AR_CHAIN'] = (props(F), P['CHAIN_AR'])
D['AR_CHAIN_L'] = (props(F), P['CHAIN_AR'])
D['AR_RESTORE'] = (props(F), P['RESTORE'])
D['AR_EPOCH'] = (props(F), P['EPOCH'])
D['AR_EPOCH_L'] = (props(F), P['EPOCH'])
D['AR_SUSP'] = (props(F), P['SUSP'])
D['AR_XB'] = (props(F), P['XB'])
D['AR_ALARM'] = (props(F), P['ALARM'])
D['AR_EVID'] = (props(set()), P['EVID_AR'])
D['AR_SKIPEV'] = (props(F), P['SKIPEV_AR'])
D['AR_CHAIN_LINKCHECKED_ONLY'] = (props(F | REPLAY), dict(P_COVERED=RE, P_LINK=RE, P_LINK_SKIP=NR,
                                                          P_EPOCH_REOPEN=RE))
D['AR_CHAIN_OPENFRESH_ONLY'] = (props(F | SKIP), dict(P_COVERED=RE, P_LINK_SKIP=RE, P_EPOCH_REOPEN=NR))
D['AR_ALARM_COUNTS_ONLY'] = (props(F | REPLAY), dict(P_COVERED=RE, P_ALARM_LINKED=RE, P_NOTCOV_BY_ALARM=RE))
D['CV_RESUME'] = (props(F), dict(P_COVERED=RE, P_ST5_FAIL=RE, P_COVERED_AFTER_LOST=NR))
D['CV_OLDCURSOR'] = (props(F), dict(P_COVERED=RE, P_ST6_FAIL=RE, P_COVERED_AFTER_LOST=NR, P_OPEN_LOST=RE))
D['OA_CARRYBREAK'] = (props(F | {'CENT_N'}), dict(P_COVERED=RE, P_CARRY_BREAK=RE, P_COVERED_INC=RE))

MUT = {
    'MU_DL2_off': ({'SAF6'}, dict(P_LINK=NR)),
    'MU_DL2_newreceipt': ({'SAF6'}, dict(P_LINK=RE)),
    'MU_DL3_order': ({'SAF2', 'CENT_N'}, dict(P_DL3_STMT_TOKEN_KEPT=NR)),
    'MU_DL3_spend': ({'PMD1'}, dict(P_DL3_STMT_TOKEN_KEPT=NR)),
    'MU_ST2': ({'SAF1'}, {}),
    'MU_ST5': (set(), {}),
    'MU_ST6': (set(), {}),
    'MU_ST5_RESUME': ({'SAF4'}, dict(P_ST5_FAIL=NR)),
    'MU_ST6_FZ_OLDCURSOR': ({'SAF5'}, dict(P_COVERED_AFTER_LOST=RE)),
    'MU_ST1_budget': ({'SAF1'}, {}),
    'MU_ST1_epoch': (set(), {}),
    'MU_MK5': (set(), {}),
    'MU_ST3': (set(), dict(P_EXPIRED_STMT=NR)),
    'MU_C12_age': ({'SAF3'}, {}),
    'MU_C1_epoch': (set(), {}),
    'MU_MT5_wall': ({'SAF1', 'SAF3', 'SAF3B_ACC'}, {}),
    'MU_MT1_mono': ({'SAF1', 'SAF3', 'SAF3B_ACC'}, {}),
    'MU_MEPOCH': ({'SAF1', 'SAF3', 'SAF3B_ACC'}, {}),
    'MU_TICK_CROSS': (set(), {}),
    'MU_DL4_held': ({'SAF2', 'CENT_E'}, {}),
    'MU_C1_gap': ({'SAF7'}, {}),
    'MU_C1_alarm': ({'SAF7'}, {}),
    'MU_ST7_R': ({'SAF3B_ACC'}, {}),
    'MU_OR2': ({'CENT_N'}, {}),
    'MU_GAP_unverified': (set(), {}),
    'MU_CS2_nonce': ({'SAF8'}, {}),
}
for n, (extra, pr) in MUT.items():
    base = configs.MUTANTS[n][0]
    bp, bpr = D[base]
    p2 = dict(bp)
    for e in extra:
        p2[e] = V
    D[n] = (p2, dict(pr))     # mutants: only the probes the removed mechanism changes are declared

# version 2b (added after run 1, before their own first run)
D['AR_CHAIN_XL'] = (props(F), P['CHAIN_AR'])
D['AR_ALARM_L'] = (props(F), P['ALARM'])
D['AR_EVID_L'] = (props(set()), P['EVID_AR'])
D['AR_SKIPEV_L'] = (props(F), dict(P['SKIPEV_AR'], P_GAP=RE))

assert set(D) == set(configs.CONFIGS), set(configs.CONFIGS) ^ set(D)

here = os.path.dirname(os.path.abspath(__file__))
dd = os.path.join(here, 'declared')
os.makedirs(dd, exist_ok=True)
lines = []
for n in configs.ORDER:
    p, pr = D[n]
    obj = dict(config=n, properties=p, probes=pr, declaration_version=2,
               note='written before the run; probes not listed are informational')
    b = json.dumps(obj, indent=1, sort_keys=True).encode()
    path = os.path.join(dd, n + '.json')
    if os.path.exists(path):
        with open(path, 'rb') as f:
            if f.read() != b:
                sys.exit('declaration %s exists and differs: declarations are never rewritten' % n)
    else:
        with open(path, 'wb') as f:
            f.write(b)
    lines.append('%s  %s.json' % (hashlib.sha256(b).hexdigest(), n))
with open(os.path.join(dd, 'SHA256SUMS'), 'w') as f:
    f.write('\n'.join(lines) + '\n')
print('declared %d configurations' % len(lines))
