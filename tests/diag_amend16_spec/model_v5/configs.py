"""Configurations for model4 (specification version 5). One process per configuration."""
from model import BASE

def fam(**kw):
    d = dict(BASE); d.update(kw); return d

F = {}
F['CHAIN'] = fam(RUNS=2, NMAX=2, EMAX=2, LOSSES=1)
F['CHAIN_L'] = fam(RUNS=2, NMAX=2, EMAX=2, LOSSES=1, VALUES=('u', 'x', 'p'), TMAX=2, MAX_READS=3)
F['RESTORE'] = fam(MAX_READS=3, EMAX=2, LOSSES=1, SNAPS=1, RESTORES=1)
F['RESTORE_L'] = fam(MAX_READS=3, EMAX=2, LOSSES=1, SNAPS=1, RESTORES=1, NMAX=2, VALUES=('u', 'x', 'p'))
F['EPOCH'] = fam(TMAX=2, REBOOTS=1, RESTARTS=1, WALL_MOVES=1)
F['EPOCH_L'] = fam(TMAX=3, L=2, R=1, REBOOTS=1, RESTARTS=1, WALL_MOVES=1)
F['SUSP'] = fam(TMAX=3, SUSPENDS=1, WALL_MOVES=1, MAX_READS=3)
F['REQ'] = fam(TMAX=2, REQ_REPLAYS=2)
F['REQ_L'] = fam(TMAX=2, REQ_REPLAYS=3, MAX_READS=3, RESTARTS=1)
F['ALARM'] = fam(L3=True, MAX_READS=3, READ_FAIL=True)
F['ALARM_L'] = fam(L3=True, MAX_READS=4, READ_FAIL=True, TMAX=2)
F['EVID'] = fam(VALUES=('u', 'f'), NMAX=2, MAX_READS=3, EV_FAIL=True, ORPHAN=True)
F['EVID_L'] = fam(RUNS=2, VALUES=('u', 'f'), NMAX=2, MAX_READS=3, EV_FAIL=True, ORPHAN=True)
F['SKIPEV'] = fam(RUNS=2, NMAX=2, VALUES=('x', 'f'), ORPHAN=True, EV_FAIL=True, MAX_READS=3)
F['FORK'] = fam(NMAX=3, WTRUNC=1, MAX_READS=3)
F['FORK_L'] = fam(NMAX=3, WTRUNC=1, MAX_READS=3, EMAX=2, LOSSES=1)
F['QUOTA_NOTICE'] = fam(RUNS=2, NMAX=2, ROOMS=(1, 2, 6, 9, 2), ALARMS_KEEP=2, READ_FAIL=True, MAX_READS=3)
F['QUOTA_NOTICE_L'] = fam(RUNS=2, NMAX=2, ROOMS=(1, 2, 6, 9, 2), ALARMS_KEEP=2, READ_FAIL=True, MAX_READS=4, TMAX=2)
F['QUOTA_INDEX'] = fam(RUNS=1, NMAX=1, ROOMS=(2, 2, 8, 5, 2), ALARMS_KEEP=2, READ_FAIL=True, MAX_READS=3)
F['QUOTA_OBS'] = fam(RUNS=1, NMAX=1, ROOMS=(2, 2, 4, 9, 2), ALARMS_KEEP=2, READ_FAIL=True, MAX_READS=4, RETIRE=True)
F['QUOTA_ALARM'] = fam(RUNS=1, NMAX=1, ROOMS=(2, 1, 8, 9, 2), ALARMS_KEEP=1, READ_FAIL=True, MAX_READS=3)
F['WIPE'] = fam(NMAX=2, EMAX=3, WIPES=1, MAX_READS=3)
F['WIPE_FORK'] = fam(NMAX=2, EMAX=3, WIPES=1, WTRUNC=1, MAX_READS=3)
F['WIPE_FORK_L'] = fam(NMAX=3, EMAX=3, WIPES=1, WTRUNC=1, MAX_READS=3)
F['WIPE_BOTHLOST'] = fam(NMAX=2, EMAX=2, WIPES=1, WTRUNC=1, MAX_READS=2, LOSSES=1)
F['STATUS'] = fam(TMAX=2, READER=True)

CONFIGS = {}
for n, f in F.items():
    CONFIGS['FD_' + n] = f
CONFIGS['AR_WIPE_FORK_DROPANCHOR'] = dict(F['WIPE_FORK'], KEEP_OWN_ANCHOR_ON_LOSS=False)
CONFIGS['CV_RESUME'] = fam(MAX_READS=3, EMAX=1, LOSSES=1, COURIER='resume')
CONFIGS['CV_OLDCURSOR'] = fam(MAX_READS=3, EMAX=2, LOSSES=1, COURIER='oldcursor')
CONFIGS['CV_NOCHECK'] = fam(NMAX=3, WTRUNC=1, MAX_READS=3, COURIER='nocheck')
CONFIGS['OA_CARRYBREAK'] = fam(RUNS=2, NMAX=2, VALUES=('u', 'x', 'p'), CARRY_BREAKS=1, MAX_READS=3)

MUTANTS = {
    'MU_DL2_off': ('FD_CHAIN', ('DL2_off',)), 'MU_DL2_newreceipt': ('FD_CHAIN', ('DL2_newreceipt',)),
    'MU_DL3_order': ('FD_CHAIN', ('DL3_order',)), 'MU_DL3_spend': ('FD_CHAIN', ('DL3_spend',)),
    'MU_DL2_AFTER_DL3': ('FD_CHAIN', ('DL2_AFTER_DL3',)), 'MU_REFUSED_POS': ('FD_CHAIN', ('REFUSED_POS',)),
    'MU_OPEN_KNOWN': ('FD_CHAIN', ('OPEN_KNOWN',)), 'MU_CLOSES_off': ('FD_CHAIN', ('CLOSES_off',)),
    'MU_ST7_R': ('FD_CHAIN', ('ST7_R',)), 'MU_C15_off': ('FD_CHAIN', ('C15_off',)),
    'MU_C17_off': ('FD_CHAIN', ('C17_off',)),
    'MU_ST2': ('FD_RESTORE', ('ST2',)), 'MU_ST5': ('FD_RESTORE', ('ST5',)),
    'MU_ST5_RESUME': ('CV_RESUME', ('ST5',)), 'MU_ST7_FZ_OLDCURSOR': ('CV_OLDCURSOR', ('ST7_FZ',)),
    'MU_ANCHOR_off': ('FD_FORK_L', ('ST6',)), 'MU_ANCHOR_off_NOCHECK': ('CV_NOCHECK', ('ST6',)),
    'MU_NO_OWN_ANCHOR': ('FD_WIPE_FORK', ('NO_OWN_ANCHOR',)),
    'MU_ST1_epoch': ('FD_EPOCH', ('ST1_epoch',)), 'MU_MK5': ('FD_EPOCH', ('MK5',)), 'MU_ST3': ('FD_EPOCH', ('ST3',)),
    'MU_C12_age': ('FD_EPOCH', ('C12_age',)), 'MU_C1_epoch': ('FD_EPOCH', ('C1_epoch',)),
    'MU_MT5_wall': ('FD_EPOCH', ('MT5_wall',)), 'MU_MEPOCH': ('FD_EPOCH', ('MEPOCH',)),
    'MU_TICK_CROSS': ('FD_EPOCH', ('TICK_CROSS',)), 'MU_MT1_mono': ('FD_SUSP', ('MT1_mono',)),
    'MU_REQ_REPLAY': ('FD_REQ', ('REQ_REPLAY',)),
    'MU_C1_alarm': ('FD_ALARM', ('C1_alarm',)), 'MU_OR2': ('FD_ALARM', ('OR2',)),
    'MU_ALARM_NOTOKEN': ('FD_ALARM', ('ALARM_NOTOKEN',)),
    'MU_DL4_held': ('FD_EVID', ('DL4_held',)), 'MU_C1_gap': ('FD_EVID', ('C1_gap',)),
    'MU_EQ6_off': ('FD_EVID', ('EQ6_off',)), 'MU_ORPHAN_NOTHELD': ('FD_EVID', ('ORPHAN_NOTHELD',)),
    'MU_GAP_NO_REBEGIN': ('FD_EVID', ('GAP_NO_REBEGIN',)),
    'MU2_ORPHAN_NOTHELD+GAP_NO_REBEGIN': ('FD_EVID', ('ORPHAN_NOTHELD', 'GAP_NO_REBEGIN')),
    'MU_C16_off': ('FD_QUOTA_NOTICE', ('C16_off',)), 'MU_REFUSED_KEEPS_POS': ('FD_QUOTA_NOTICE', ('REFUSED_KEEPS_POS',)),
    'MU_NO_INDEX_RESERVE': ('FD_QUOTA_INDEX', ('NO_INDEX_RESERVE',)),
    'MU_ALARM_STORE_FIRST': ('FD_QUOTA_ALARM', ('ALARM_STORE_FIRST',)),
    'MU_OUTBOX_KEEPS_STMT': ('FD_QUOTA_OBS', ('OUTBOX_KEEPS_STMT',)),
    'MU_CS2_nonce': ('FD_STATUS', ('CS2_nonce',)),
}
for n, (b, m) in MUTANTS.items():
    d = dict(CONFIGS[b]); d['MUTANTS'] = m; CONFIGS[n] = d
ORDER = list(CONFIGS)
