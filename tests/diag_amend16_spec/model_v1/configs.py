"""Configurations, version 2 (bounds chosen by sizing runs that print no verdicts; see REPORT.md).
Each configuration is run in its own process. Bounds are stated here and in each result file.

Families (each one keeps a few adversary moves, so that every family is searched exhaustively):
  CHAIN    two runs; chain epochs; COURIER_STATE_LOST; linking; order of delivery; replay
  RESTORE  one run; a courier restored from an old copy of its state; loss; three readings
  EPOCH    one run; mailbox reboot and restart (CLOCK_BOOTTIME epochs) and the wall clock set back/forward
  SUSP     one run; suspension (BOOTTIME counts it, MONOTONIC does not) and the wall clock
  XB       one run; another budget's tokens; replayed challenge requests; old challenges handed to the courier
  ALARM    one run; readings that are not whole (OBSERVATION_INCOMPLETE), three readings, L-3 results
  EVID     one run; evidence refused (NOT_HELD, gaps), orphan removal, re-upload, three readings
  SKIPEV   two runs; evidence and orphan removal with linking
  STATUS   one run; the reader's nonce
  QUOTA    one run; item quota and ALARM_RESERVE
  WIPE     one run; loss of the mailbox's durable record of the budget
  CARRY    two runs; A-CARRY broken by CAP-OWNER (outside the text's assumption)
Prefixes:
  FD_  fixed design, literal readings chosen in model.py BASE
  AR_  fixed design under the alternative readings (link only at the head position; gap closed by a
       verified same-identity item; a linked alarm counts as accepted; EPOCH_OPEN only for a new epoch)
  CV_  courier variants that do not follow I-E-3
  OA_  outside an assumption of the text: not claimed by the text
  MU_  mutants: one mechanism removed, on an AR_ base so that the break is attributable
  *_L  a larger bound of the same family
"""

COMMON = dict(VALUES=('u', 'x'), L3=False, TMAX=1, L=1, R=0, TOKENS_MAX=1, EMAX=1, MAX_READS=2,
              LOSSES=0, SNAPS=0, RESTORES=0, REBOOTS=0, RESTARTS=0, WALL_MOVES=0, SUSPENDS=0,
              B1_ISSUES=0, REQ_REPLAYS=0, MAX_ISSUES=0, CHAL_REPLAY=False, CARRY_BREAKS=0,
              ORPHAN=False, WIPES=0, EV_FAIL=False, READ_FAIL=False, INCREMENTAL=True,
              ITEM_QUOTA=None, ALARM_RESERVE=0, READER=False, MAX_STATES=6_000_000)


def fam(**kw):
    d = dict(COMMON)
    d.update(kw)
    return d


CHAIN = fam(RUNS=2, NMAX=2, EMAX=2, LOSSES=1)
CHAIN_L = fam(RUNS=2, NMAX=2, EMAX=2, LOSSES=1, VALUES=('u', 'x', 'p'), TMAX=2)
RESTORE = fam(RUNS=1, NMAX=1, EMAX=2, LOSSES=1, SNAPS=1, RESTORES=1, MAX_READS=3)
EPOCH = fam(RUNS=1, NMAX=1, TMAX=2, REBOOTS=1, RESTARTS=1, WALL_MOVES=1)
EPOCH_L = fam(RUNS=1, NMAX=1, TMAX=3, L=2, R=1, REBOOTS=1, RESTARTS=1, WALL_MOVES=1)
SUSP = fam(RUNS=1, NMAX=1, TMAX=3, SUSPENDS=1, WALL_MOVES=1, MAX_READS=3)
XB = fam(RUNS=1, NMAX=1, TMAX=2, B1_ISSUES=1, REQ_REPLAYS=1, MAX_ISSUES=1, CHAL_REPLAY=True)
ALARM = fam(RUNS=1, NMAX=1, L3=True, MAX_READS=3, READ_FAIL=True)
EVID = fam(RUNS=1, NMAX=2, VALUES=('u', 'f'), MAX_READS=3, EV_FAIL=True, ORPHAN=True)
SKIPEV = fam(RUNS=2, NMAX=2, VALUES=('x', 'f'), ORPHAN=True)
STATUS = fam(RUNS=1, NMAX=1, TMAX=2, READER=True, QMAX=2, NSTAT_MAX=3)
QUOTA = fam(RUNS=1, NMAX=1, ITEM_QUOTA=4, ALARM_RESERVE=1, READ_FAIL=True, MAX_READS=3)
WIPE = fam(RUNS=1, NMAX=2, EMAX=2, WIPES=1, MAX_READS=3)
CARRY = fam(RUNS=2, NMAX=2, VALUES=('u', 'x', 'p'), CARRY_BREAKS=1, MAX_READS=3)

AR = dict(LINK_MODE='checked', GAP_CLOSE='verified', LINK_COUNTS_ALARM=True, OPEN_FRESH=True)


def mu(base, *names, **kw):
    d = dict(base)
    d['MUTANTS'] = tuple(names)
    d.update(kw)
    return d


CONFIGS = {}
FAMS = dict(CHAIN=CHAIN, CHAIN_L=CHAIN_L, RESTORE=RESTORE, EPOCH=EPOCH, EPOCH_L=EPOCH_L, SUSP=SUSP,
            XB=XB, ALARM=ALARM, EVID=EVID, SKIPEV=SKIPEV, STATUS=STATUS, QUOTA=QUOTA, WIPE=WIPE)
for _n, _f in FAMS.items():
    CONFIGS['FD_' + _n] = dict(_f)
for _n in ('CHAIN', 'CHAIN_L', 'RESTORE', 'EPOCH', 'EPOCH_L', 'SUSP', 'XB', 'ALARM', 'EVID', 'SKIPEV'):
    CONFIGS['AR_' + _n] = dict(FAMS[_n], **AR)
CONFIGS['FD_XB_SHAREDKEY'] = dict(XB, SHARED_KEY=True)
CONFIGS['AR_CHAIN_LINKCHECKED_ONLY'] = dict(CHAIN, LINK_MODE='checked')
CONFIGS['AR_CHAIN_OPENFRESH_ONLY'] = dict(CHAIN, OPEN_FRESH=True)
CONFIGS['AR_ALARM_COUNTS_ONLY'] = dict(ALARM, LINK_COUNTS_ALARM=True)
CONFIGS['CV_RESUME'] = dict(RESTORE, COURIER='resume', SNAPS=0, RESTORES=0, **AR)
CONFIGS['CV_OLDCURSOR'] = dict(RESTORE, COURIER='oldcursor', SNAPS=0, RESTORES=0, **AR)
CONFIGS['OA_CARRYBREAK'] = dict(CARRY, **AR)

MUTANTS = {
    'MU_DL2_off': ('AR_CHAIN', 'DL2_off'),
    'MU_DL2_newreceipt': ('AR_CHAIN', 'DL2_newreceipt'),
    'MU_DL3_order': ('AR_CHAIN', 'DL3_order'),
    'MU_DL3_spend': ('AR_CHAIN', 'DL3_spend'),
    'MU_ST2': ('AR_XB', 'ST2'),
    'MU_ST5': ('AR_RESTORE', 'ST5'),
    'MU_ST6': ('AR_RESTORE', 'ST6'),
    'MU_ST5_RESUME': ('CV_RESUME', 'ST5'),
    'MU_ST6_FZ_OLDCURSOR': ('CV_OLDCURSOR', 'ST6_FZ'),
    'MU_ST1_budget': ('AR_XB', 'ST1_budget'),
    'MU_ST1_epoch': ('AR_EPOCH', 'ST1_epoch'),
    'MU_MK5': ('AR_EPOCH', 'MK5'),
    'MU_ST3': ('AR_EPOCH', 'ST3'),
    'MU_C12_age': ('AR_EPOCH', 'C12_age'),
    'MU_C1_epoch': ('AR_EPOCH', 'C1_epoch'),
    'MU_MT5_wall': ('AR_EPOCH', 'MT5_wall'),
    'MU_MT1_mono': ('AR_SUSP', 'MT1_mono'),
    'MU_MEPOCH': ('AR_EPOCH', 'MEPOCH'),
    'MU_TICK_CROSS': ('AR_EPOCH', 'TICK_CROSS'),
    'MU_DL4_held': ('AR_EVID', 'DL4_held'),
    'MU_C1_gap': ('AR_EVID', 'C1_gap'),
    'MU_C1_alarm': ('AR_ALARM', 'C1_alarm'),
    'MU_ST7_R': ('AR_CHAIN', 'ST7_R'),
    'MU_OR2': ('AR_ALARM', 'OR2'),
    'MU_GAP_unverified': ('AR_EVID', 'GAP_unverified'),
    'MU_CS2_nonce': ('FD_STATUS', 'CS2_nonce'),
}
for _n, (_b, _m) in MUTANTS.items():
    CONFIGS[_n] = mu(CONFIGS[_b], _m)

# version 2b: larger bounds for the alternative readings (declared before their first run)
CONFIGS['AR_CHAIN_XL'] = dict(CHAIN, VALUES=('u', 'x', 'p'), MAX_READS=3, TMAX=2, **AR)
CONFIGS['AR_ALARM_L'] = dict(ALARM, MAX_READS=4, TMAX=2, **AR)
CONFIGS['AR_EVID_L'] = dict(EVID, MAX_READS=4, **AR)
CONFIGS['AR_SKIPEV_L'] = dict(SKIPEV, EV_FAIL=True, MAX_READS=3, **AR)

ORDER = list(CONFIGS)
