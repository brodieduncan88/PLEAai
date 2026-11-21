#!/usr/bin/env python3
"""Declared verdicts for model3 (specification v2), written BEFORE any verdict run."""
import json, os, hashlib, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import configs
from model import ALL_PROPS
H, V, NA, RE, NR = 'holds', 'violated', 'n/a', 'reached', 'not_reached'

def props(viol, reader=False):
    d = {p: (V if p in viol else H) for p in ALL_PROPS}
    d['SAF8'] = (V if 'SAF8' in viol else H) if reader else NA
    return d

P = {
 'CHAIN': dict(P_COVERED=RE, P_COVERED_INC=RE, P_COVERED_AFTER_LOST=RE, P_LINK=RE, P_STMT_BEFORE_ITEMS=RE,
               P_DL2_FIRST_RECEIPT_STMT=RE, P_DL2_FIRST_REFUSAL=RE, P_EPOCH_KNOWN=RE, P_OPEN_LOST=RE,
               P_OPEN_CLOSES_LIVE=RE, P_COURIER_LOST=RE, P_NOTCOV_BY_REFUSED_STMT=RE, P_NOTCOV_STALE_CARRY=RE),
 'RESTORE': dict(P_COVERED=RE, P_RESTORE=RE, P_STALECOPY_COUNTED=RE, P_COURIER_LOST=RE, P_COVERED_AFTER_LOST=RE),
 'EPOCH': dict(P_COVERED=RE, P_COVERED_AFTER_REBOOT=RE, P_COVERED_AFTER_RESTART=RE, P_COVERED_REFRESH_NEWMEP=RE,
               P_EXPIRED_STMT=RE, P_ANOMALY_AGE=RE),
 'SUSP': dict(P_COVERED=RE, P_EXPIRED_STMT=RE, P_ANOMALY_AGE=RE),
 'REQ': dict(P_COVERED=RE, P_REQ_REPLAY_REFUSED=RE),
 'ALARM': dict(P_COVERED=RE, P_COVERED_INC=RE, P_NOTCOV_BY_ALARM=RE, P_ALARM_TAKEN=RE, P_L3_READ=RE),
 'EVID': dict(P_COVERED=RE, P_GAP=RE, P_GAP_CLOSED=RE, P_ORPHAN=RE, P_EVMISSING=RE, P_NOTHELD_REMADE=RE),
 'SKIPEV': dict(P_COVERED=RE, P_LINK=RE, P_ORPHAN=RE, P_GAP=RE),
 'FORK': dict(P_COVERED=RE, P_FORK_ALARM=RE, P_ROLLBACK_ALARM=RE, P_WITNESS_TRUNC=RE, P_ST6_FAIL=NR),
 'QUOTA': dict(P_COVERED=RE, P_ROOM_NOTICE=RE, P_ALARM_AFTER_ROOM_REFUSAL=NR),
 'QUOTA_OBS': dict(P_COVERED=RE, P_ROOM_OBS=RE, P_ALARM_REFUSED_OBS_ONLY=RE),
 'WIPE': dict(P_COVERED=RE, P_WIPE=RE, P_MAILBOX_ROLLBACK=RE, P_COVERED_AFTER_LOST=RE),
 'STATUS': dict(P_COVERED=RE, P_READER_COVERED=RE, P_STALE_STATUS_REJECTED=RE),
}
D = {}
for n in configs.ORDER:
    if n.startswith('FD_'):
        fam = n[3:]
        base = fam[:-2] if fam.endswith('_L') else fam
        base = {'WIPE_FORK': 'WIPE'}.get(base, base)
        viol = {'SAF10'} if fam.startswith('WIPE') else set()
        pr = dict(P[base])
        if fam == 'FORK_L':
            pr['P_COVERED_AFTER_LOST'] = RE
        if fam == 'WIPE_FORK':
            pr['P_FORK_ALARM'] = RE
        D[n] = (props(viol, reader=(fam == 'STATUS')), pr)
D['CV_RESUME'] = (props(set()), dict(P_COVERED=RE, P_ST5_FAIL=RE))
D['CV_OLDCURSOR'] = (props(set()), dict(P_COVERED=RE, P_ST7_FAIL=RE))
D['CV_NOCHECK'] = (props(set()), dict(P_COVERED=RE, P_ST6_FAIL=RE))
D['OA_CARRYBREAK'] = (props({'CENT_N'}), dict(P_COVERED=RE, P_CARRY_BREAK=RE, P_COVERED_INC=RE))
MUT = {
 'MU_DL2_off': ({'SAF6'}, dict(P_LINK=NR)), 'MU_DL2_newreceipt': ({'SAF6'}, {}),
 'MU_DL3_order': ({'SAF2', 'CENT_N'}, {}), 'MU_DL3_spend': ({'SAF2'}, dict(P_STMT_BEFORE_ITEMS=NR)),
 'MU_DL2_AFTER_DL3': ({'DL2_SAME'}, {}), 'MU_REFUSED_POS': ({'REFUSED_NOPOS'}, {}),
 'MU_OPEN_KNOWN': ({'SAF5'}, dict(P_EPOCH_KNOWN=NR)), 'MU_ST7_R': ({'SAF3B_ACC'}, {}),
 'MU_C15_off': ({'SAF7', 'C1_VS_82'}, {}), 'MU_C17_off': ({'SAF7', 'R_AT_STATUS', 'C1_VS_82'}, {}),
 'MU_ST2': (set(), {}), 'MU_ST5': (set(), {}), 'MU_ST5_RESUME': ({'SAF4'}, dict(P_ST5_FAIL=NR)),
 'MU_ST7_FZ_OLDCURSOR': ({'SAF5'}, {}), 'MU_ANCHOR_off': (set(), {}), 'MU_ANCHOR_off_NOCHECK': ({'SAF10'}, dict(P_ST6_FAIL=NR)),
 'MU_ST1_epoch': (set(), {}), 'MU_MK5': (set(), {}), 'MU_ST3': (set(), dict(P_EXPIRED_STMT=NR)),
 'MU_C12_age': ({'SAF3', 'C1_VS_82'}, {}), 'MU_C1_epoch': (set(), {}),
 'MU_MT5_wall': ({'SAF1', 'SAF3', 'SAF3B_ACC', 'SAF7', 'R_AT_STATUS'}, {}),
 'MU_MEPOCH': ({'SAF1', 'SAF3', 'SAF3B_ACC', 'SAF7', 'R_AT_STATUS'}, {}),
 'MU_TICK_CROSS': (set(), {}), 'MU_MT1_mono': ({'SAF1', 'SAF3', 'SAF3B_ACC', 'SAF7', 'R_AT_STATUS'}, {}),
 'MU_REQ_REPLAY': ({'PMK1'}, dict(P_REQ_REPLAY_REFUSED=NR)),
 'MU_C1_alarm': ({'SAF7', 'C1_VS_82'}, {}), 'MU_OR2': ({'CENT_N'}, {}), 'MU_ALARM_NOTOKEN': ({'SAF7'}, {}),
 'MU_DL4_held': ({'SAF2', 'CENT_E'}, {}), 'MU_C1_gap': ({'SAF7', 'CENT_E', 'C1_VS_82'}, {}),
 'MU_EQ6_off': ({'SAF11', 'SAF2', 'CENT_E'}, dict(P_PENDING_ORPHAN=RE)), 'MU_GAP_BY_NOTICE': (set(), {}),
 'MU_C16_off': ({'SAF7', 'C1_VS_82'}, {}), 'MU_CS2_nonce': ({'SAF8'}, {}),
}
for n, (extra, pr) in MUT.items():
    bp, _ = D[configs.MUTANTS[n][0]]
    p2 = dict(bp)
    for e in extra:
        p2[e] = V
    D[n] = (p2, pr)
assert set(D) == set(configs.CONFIGS), set(D) ^ set(configs.CONFIGS)
dd = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'declared')
os.makedirs(dd, exist_ok=True)
lines = []
for n in configs.ORDER:
    p, pr = D[n]
    b = json.dumps(dict(config=n, properties=p, probes=pr, model='model3', spec='v2'), indent=1, sort_keys=True).encode()
    path = os.path.join(dd, n + '.json')
    if os.path.exists(path) and open(path, 'rb').read() != b:
        sys.exit('declaration %s exists and differs' % n)
    open(path, 'wb').write(b)
    lines.append('%s  %s.json' % (hashlib.sha256(b).hexdigest(), n))
open(os.path.join(dd, 'SHA256SUMS'), 'w').write('\n'.join(lines) + '\n')
print('declared', len(lines))
