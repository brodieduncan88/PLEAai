"""Configurations for model5 (specification version 6). One process per configuration."""
from model import BASE

def fam(**kw):
    d = dict(BASE); d.update(kw); return d

F = {}
F['WIPE'] = fam(NMAX=2, EMAX=3, WIPES=1, MAX_READS=3)
F['WIPE_L'] = fam(NMAX=2, EMAX=3, WIPES=1, MAX_READS=4, VALUES=('u', 'x', 'p'))
F['WIPE_FORK'] = fam(NMAX=2, EMAX=3, WIPES=1, WTRUNC=1, MAX_READS=3)
F['WIPE_FORK_L'] = fam(NMAX=3, EMAX=3, WIPES=1, WTRUNC=1, MAX_READS=3)
F['WIPE_FORK_INC'] = fam(NMAX=3, EMAX=3, WIPES=1, WTRUNC=1, MAX_READS=3, VALUES=('x', 'p'))
F['WIPE_BOTHLOST'] = fam(NMAX=2, EMAX=2, WIPES=1, WTRUNC=1, MAX_READS=2, LOSSES=1)
F['FORK'] = fam(NMAX=3, WTRUNC=1, MAX_READS=3)
F['FORK_L'] = fam(NMAX=3, WTRUNC=1, MAX_READS=3, EMAX=2, LOSSES=1)
F['RESTORE'] = fam(MAX_READS=3, EMAX=2, LOSSES=1, SNAPS=1, RESTORES=1)
F['RESTORE_L'] = fam(MAX_READS=3, EMAX=2, LOSSES=1, SNAPS=1, RESTORES=1, NMAX=2, VALUES=('u', 'x', 'p'))
F['RESTORE_FORK'] = fam(MAX_READS=3, EMAX=2, SNAPS=1, RESTORES=1, NMAX=2, WTRUNC=1)
F['WIPE_RESTORE_FORK'] = fam(MAX_READS=2, EMAX=2, SNAPS=1, RESTORES=1, NMAX=2, WTRUNC=1, WIPES=1)
F['CHAIN'] = fam(RUNS=2, NMAX=2, EMAX=2, LOSSES=1)
F['EPOCH'] = fam(TMAX=2, REBOOTS=1, RESTARTS=1, WALL_MOVES=1)
F['QUOTA_NOTICE'] = fam(RUNS=2, NMAX=2, ROOMS=(1, 2, 6, 9, 2), ALARMS_KEEP=2, READ_FAIL=True, MAX_READS=3)

CONFIGS = {'FD_' + n: f for n, f in F.items()}
MUTANTS = {
    'MU_OA_LOWER_ON_REFUSAL': ('FD_WIPE_FORK', ('OA_LOWER_ON_REFUSAL',)),
    'MU_OA_NOT_INC': ('FD_WIPE_FORK_INC', ('OA_NOT_INC',)),
    'MU_OA_DROP_IE4': ('FD_WIPE_FORK', ('OA_DROP_IE4',)),
    'MU_IOA_UNANSWERED': ('FD_WIPE', ('IOA_UNANSWERED',)),
    'MU_NO_OWN_ANCHOR': ('FD_WIPE_FORK', ('NO_OWN_ANCHOR',)),
}
for n, (b, m) in MUTANTS.items():
    d = dict(CONFIGS[b]); d['MUTANTS'] = m; CONFIGS[n] = d
ORDER = list(CONFIGS)
