#!/usr/bin/env python3
"""
Separately authored bounded model of "Amendment 16: specification for a Step 3", version 1
(SPEC_v1_as_sent_to_review.md), sections 5 to 8, with the properties of section 9.

Written from the specification text only. This is internal, separately authored
verification. It is NOT independent validation, it is not a proof for unbounded
parameters, and it says nothing about any implementation.

Organisation: every mailbox step is a function named after its rule id
(dl1_..dl6_, st1_..st9_, mk*_, mt*_, c1_*). Readings of ambiguous text are
switches in the configuration (LINK_MODE, GAP_CLOSE, LINK_COUNTS_ALARM,
OPEN_FRESH); mechanisms removed by mutants are names in MUTANTS.

Abstractions (see REPORT.md for the full list):
  * hashes are exact: A(k) and secrets are interned symbolic values, no collisions;
  * signatures cannot be forged: every item in the network was made by the courier;
  * the witness is trusted and its chain is append-only; a reading is one atomic event;
  * a run's standing is one of u (unsettled, calls for an outcome notice, e.g. UNVERIFIED),
    p (settled, no notice, e.g. PASS), x (settled, outcome notice, e.g. FAIL or REFUNDED),
    f (a finding of 3.2: EQUIVOCATION notice resting on one piece of evidence; never settled);
  * notice identity (I-ID-1) = (run, standing, number of the last decision naming the run).
"""
import sys, os, json, time, argparse
from collections import deque

# ----------------------------------------------------------------------------- interning
_IT = {}
_IL = []


def I(x):
    v = _IT.get(x)
    if v is None:
        v = len(_IL)
        _IT[x] = v
        _IL.append(x)
    return v


def U(i):
    return _IL[i]


FZ, RF, INC = 'FROM_ZERO', 'REFRESH', 'INCREMENTAL'

# ----------------------------------------------------------------------------- configuration
BASE = dict(
    RUNS=2, NMAX=2, VALUES=('u', 'p', 'x', 'f'), TMAX=3, L=2, R=1,
    TOKENS_MAX=1, MAX_ISSUES=3, EMAX=2, MAX_READS=3, ADV_DELIVERIES=None,
    REBOOTS=0, RESTARTS=0, WALL_MOVES=0, SUSPENDS=0,
    LOSSES=0, SNAPS=0, RESTORES=0,
    B1_ISSUES=0, SHARED_KEY=False, REQ_REPLAYS=0, CHAL_REPLAY=True,
    CARRY_BREAKS=0, ORPHAN=False, WIPES=0,
    EV_FAIL=False, READ_FAIL=False, L3=True, INCREMENTAL=True,
    ITEM_QUOTA=None, ALARM_RESERVE=0,
    READER=False, QMAX=2, NSTAT_MAX=3,
    # readings of ambiguous text (defaults = the literal reading chosen, see REPORT.md)
    LINK_MODE='own_k',          # DL-2 before DL-3: link at the item's own k, no position check
    GAP_CLOSE='never',          # E-B-3 vs DL-2: a same-identity item is linked, never taken
    LINK_COUNTS_ALARM=False,    # C-1.4: a linked OBSERVATION_INCOMPLETE is not "accepted"
    OPEN_FRESH=False,           # DL-3: any EPOCH_OPEN passes; nothing requires a new chain_epoch
    COURIER='honest',           # 'honest' | 'resume' (resumes from the mailbox's head) | 'oldcursor'
    MUTANTS=(),
    MAX_STATES=3_000_000,
)

# counters
(C_ISS, C_REBOOT, C_RESTART, C_WALL, C_SUSP, C_LOSS, C_SNAP, C_RESTORE,
 C_B1, C_REQ, C_CARRY, C_WIPE, C_READS, C_ADV) = range(14)
NCTR = 14

# mailbox fields
(MEP, BT, MONO, WOFF, TOKS, CE, HK, HA, COMMIT, HELD, STORED, NSTORED, STMTS, SPENT_LAST,
 GAPS, ALARM_SEQ, ALARM_ANY, OPEN_SEQ, SEQ, EVID, REFUSED, SEEN_CE, UNREAD, OPEN_REASON) = range(24)
NMB = 24

# token fields
T_SER, T_B, T_K, T_MEP, T_GMEP, T_BT, T_WALL, T_MONO, T_RT, T_ST = range(10)
# statement record fields
(S_MID, S_REF, S_CE, S_MEP, S_TOK, S_N, S_RK, S_CARR, S_OLDEST, S_SEQ, S_CALLED, S_EVNEED,
 S_OBS, S_RCPT, S_GMEP) = range(15)
# courier fields
(K_CE, K_K, K_CHAIN, K_J, K_CURSOR, K_LASTREF, K_MEPLAST, K_OBS, K_PHASE, K_TOK, K_OUT,
 K_PEND, K_OK) = range(13)
# ghost fields
G_NEXTCE, G_EVER, G_GMEP, G_SERIAL = range(4)

# state: (rt, mb, w, cr, bk, net, chal, ctr, rd, gh)

STATE_PROPS = ['SAF3', 'SAF5', 'SAF7', 'SAF8', 'CENT_N', 'CENT_E', 'R_AT_STATUS', 'C1_VS_82']
TRANS_PROPS = ['SAF1', 'SAF2', 'SAF4', 'SAF6', 'SAF3B_ACC', 'PMD1']
ALL_PROPS = TRANS_PROPS + STATE_PROPS
PROBES = [
    'P_COVERED', 'P_COVERED_INC', 'P_COVERED_AFTER_LOST', 'P_COVERED_AFTER_REBOOT',
    'P_COVERED_AFTER_RESTART', 'P_COVERED_REFRESH_NEWMEP', 'P_NOTCOV_BY_ALARM',
    'P_LINK', 'P_LINK_SKIP', 'P_DL3_STMT_TOKEN_KEPT', 'P_OPEN_LOST', 'P_EPOCH_REOPEN',
    'P_EVICT', 'P_EXPIRED_STMT', 'P_REPLAY_STMT_422', 'P_GAP', 'P_GAP_CLOSED',
    'P_XB_REFUSED', 'P_XB_SPENT', 'P_ANOMALY_AGE', 'P_RESTORE', 'P_EVMISSING', 'P_ORPHAN',
    'P_MS1', 'P_STMT_REDELIVER_409', 'P_COURIER_LOST_REFUSAL', 'P_ITEMS_REFUSED',
    'P_L3_READ', 'P_ST5_FAIL', 'P_ST6_FAIL', 'P_ST7_FAIL', 'P_READER_COVERED',
    'P_STALE_STATUS_REJECTED', 'P_WIPE', 'P_CARRY_BREAK', 'P_ALARM_LINKED',
]


class Model:
    def __init__(self, cfg):
        self.c = dict(BASE)
        self.c.update(cfg)
        c = self.c
        self.mut = set(c['MUTANTS'])
        self.K0 = 'K0'
        self.K1 = 'K0' if c['SHARED_KEY'] else 'K1'
        self._dcache = {}
        self._scache = {}

    # ------------------------------------------------------------------ init
    def init(self):
        mb = [None] * NMB
        mb[MEP] = 0; mb[BT] = 0; mb[MONO] = 0; mb[WOFF] = 0; mb[TOKS] = ()
        mb[CE] = None; mb[HK] = 0; mb[HA] = None; mb[COMMIT] = None
        mb[HELD] = frozenset(); mb[STORED] = frozenset(); mb[NSTORED] = 0; mb[STMTS] = ()
        mb[SPENT_LAST] = False; mb[GAPS] = frozenset(); mb[ALARM_SEQ] = -1; mb[ALARM_ANY] = -1
        mb[OPEN_SEQ] = -1; mb[SEQ] = 0; mb[EVID] = frozenset(); mb[REFUSED] = False
        mb[SEEN_CE] = frozenset(); mb[UNREAD] = False; mb[OPEN_REASON] = None
        w = (0, (), (None,) * self.c['RUNS'])
        rd = (0, 0, frozenset(), 0, None) if self.c['READER'] else None
        gh = (1, False, 0, 0)
        return (0, tuple(mb), w, None, None, frozenset(), frozenset(), (0,) * NCTR, rd, gh)

    # ------------------------------------------------------------------ time (M-T-*)
    def age(self, rt, mb, tok):
        """M-T-1, M-T-2, M-T-5. None = no age can be computed (another mailbox epoch)."""
        mut = self.mut
        if tok[T_MEP] != mb[MEP] and 'TICK_CROSS' not in mut and 'MEPOCH' not in mut:
            return None  # M-T-2: a tick of another epoch is never compared
        if 'MT1_mono' in mut:
            boot = mb[MONO] - tok[T_MONO]   # mutant: CLOCK_MONOTONIC (does not count suspension)
        else:
            boot = mb[BT] - tok[T_BT]       # M-T-1: CLOCK_BOOTTIME
        wall = (rt + mb[WOFF]) - tok[T_WALL]
        if 'MT5_wall' in mut:
            return wall                     # mutant: the wall clock alone (M-T-4 removed)
        if wall < 0 or wall != boot:        # M-T-5 with CLOCK_TOLERANCE = 0
            return max(boot, wall)
        return boot

    def anomaly(self, rt, mb, tok):
        if tok[T_MEP] != mb[MEP]:
            return False
        boot = mb[BT] - tok[T_BT]
        wall = (rt + mb[WOFF]) - tok[T_WALL]
        return wall < 0 or wall != boot

    def eff(self, rt, mb, tok):
        """M-K-3/M-K-4: effective state; EXPIRED is computed lazily from the age."""
        st = tok[T_ST]
        if st == 'V':
            return 'V'
        a = self.age(rt, mb, tok)
        if a is None or a > self.c['L']:
            return 'E'
        return st

    @staticmethod
    def tok(mb, serial):
        for t in mb[TOKS]:
            if t[T_SER] == serial:
                return t
        return None

    # ------------------------------------------------------------------ M-K-1, M-K-2 issue
    def mk1_issue(self, rt, mb, gh, budget, key, ev):
        serial = gh[G_SERIAL]
        toks = list(mb[TOKS])
        issued = [i for i, t in enumerate(toks) if t[T_B] == budget and self.eff(rt, mb, t) == 'I']
        if len(issued) >= self.c['TOKENS_MAX']:                    # M-K-2
            i = min(issued, key=lambda i: toks[i][T_SER])
            toks[i] = toks[i][:T_ST] + ('V',)
            ev.append('P_EVICT')
        toks.append((serial, budget, key, mb[MEP], gh[G_GMEP], mb[BT], rt + mb[WOFF], mb[MONO], rt, 'I'))
        mb = list(mb); mb[TOKS] = tuple(toks)
        gh = gh[:G_SERIAL] + (serial + 1,)
        return tuple(mb), gh, serial

    # ------------------------------------------------------------------ status C-1
    def c1_covered(self, rt, mb):
        mut = self.mut
        if mb[UNREAD]:                                               # C-1.5
            return None
        ce = mb[CE]
        if ce is None:
            return None
        S = None
        for x in reversed(mb[STMTS]):                                # C-1.1
            if x[S_CE] == ce and (x[S_MEP] == mb[MEP] or 'C1_epoch' in mut):
                S = x
                break
        if S is None:
            return None
        t = self.tok(mb, S[S_TOK])
        if t is None:
            return None
        if 'C12_age' in mut:
            if t[T_ST] != 'U':
                return None
        elif self.eff(rt, mb, t) != 'U':                             # C-1.2
            return None
        if mb[GAPS] and 'C1_gap' not in mut:                         # C-1.3
            return None
        if mb[ALARM_SEQ] > S[S_SEQ] and 'C1_alarm' not in mut:       # C-1.4
            return None
        return S

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def chain_idents(A):
        out = []
        while A is not None:
            x = U(A)
            if x[0] == 'A0':
                break
            out.append(x[2])
            A = x[1]
        return out

    def desc(self, mid):
        m = U(mid)
        k = m[0]
        if k == 'E':
            return 'EPOCH_OPEN(ce%s,k%d,%s)#%d' % (m[1], m[2], m[5], mid)
        if k == 'N':
            idn = U(m[4])
            cl = '' if m[5] is None else ',' + {'H': 'HELD', 'X': 'NOT_HELD'}[m[5]]
            return 'NOTICE(ce%s,k%d,run%d=%s@d%d%s)#%d' % (m[1], m[2], idn[1], idn[2], idn[3], cl, mid)
        if k == 'O':
            idn = U(m[4])
            return 'OBS_INCOMPLETE(ce%s,k%d,%s,run=%s)#%d' % (m[1], m[2], idn[1], idn[2], mid)
        if k == 'C':
            return 'STATEMENT(ce%s,k%d,j%d,tok%d,%s,at%d,N%d,carried%d)#%d' % (
                m[1], m[2], U(m[5])[2], m[6], m[7], m[8], m[9], m[13], mid)
        return str(m)

    # ------------------------------------------------------------------ abstraction of counters
    def normalise(self, mb):
        """Acceptance order is kept only as an order: the sequence numbers present in the
        state are replaced by their ranks (finite state; comparisons unchanged). The count of
        stored items is kept only when an item quota is modelled, and capped at it."""
        vals = {mb[ALARM_SEQ], mb[ALARM_ANY], mb[OPEN_SEQ]} | {x[S_SEQ] for x in mb[STMTS]}
        vals.discard(-1)
        rank = {v: i for i, v in enumerate(sorted(vals))}
        rank[-1] = -1
        L = list(mb)
        L[ALARM_SEQ] = rank[mb[ALARM_SEQ]]
        L[ALARM_ANY] = rank[mb[ALARM_ANY]]
        L[OPEN_SEQ] = rank[mb[OPEN_SEQ]]
        L[STMTS] = tuple(x[:S_SEQ] + (rank[x[S_SEQ]],) + x[S_SEQ + 1:] for x in mb[STMTS])
        L[SEQ] = len(vals)
        q = self.c['ITEM_QUOTA']
        L[NSTORED] = 0 if q is None else min(mb[NSTORED], q)
        return tuple(L)

    # ------------------------------------------------------------------ the mailbox: 7.3 / 7.4
    def deliver(self, rt, mb, gh, mid):
        key = (rt, mb, gh[G_GMEP], mid)
        r = self._dcache.get(key)
        if r is not None:
            return r
        mb2, ans, ev = self.deliver_raw(rt, mb, gh, mid)
        if mb2 is not mb:
            mb2 = self.normalise(mb2)
        r = (mb2, ans, tuple(ev))
        if len(self._dcache) > 1500000:
            self._dcache.clear()
        self._dcache[key] = r
        return r

    def deliver_raw(self, rt, mb, gh, mid):
        """Returns (mb', answer, events). Strict order DL-1 .. DL-6."""
        c = self.c
        mut = self.mut
        ev = []
        m = U(mid)
        kind = m[0]
        ce_m, k_m, prev_m, ident = m[1], m[2], m[3], m[4]
        if mb[UNREAD]:
            return mb, ('X',), ev
        # DL-1: size, form, kind, signature: always pass (the adversary cannot forge; every
        # item in the network was made by the budget's courier key K0).
        L = list(mb)
        # DL-2: link an identity of I-ID-1 / I-ID-2 already held for the budget (I-E-5)
        if kind in ('N', 'O') and 'DL2_off' not in mut:
            h = None
            for e in mb[HELD]:
                if e[0] == ident:
                    h = e
                    break
            if h is not None:
                pos_ok = (ce_m == mb[CE] and k_m == mb[HK] + 1 and prev_m == mb[HA])
                if c['LINK_MODE'] == 'checked' and not pos_ok:
                    pass  # alternative reading: position checked first; falls to DL-3 (refused)
                else:
                    newA = I(('A', prev_m, ident))
                    if not pos_ok:
                        ev.append('P_LINK_SKIP')
                    L[HK] = k_m
                    L[HA] = newA
                    L[SEQ] = mb[SEQ] + 1
                    if kind == 'O':
                        L[ALARM_ANY] = L[SEQ]
                        ev.append('P_ALARM_LINKED')
                        if c['LINK_COUNTS_ALARM']:
                            L[ALARM_SEQ] = L[SEQ]
                    if kind == 'N' and ident in mb[GAPS]:
                        if c['GAP_CLOSE'] == 'verified' and m[5] == 'H' and m[6] in mb[EVID]:
                            L[GAPS] = mb[GAPS] - {ident}
                            ev.append('P_GAP_CLOSED')
                        elif c['GAP_CLOSE'] == 'unverified' or 'GAP_unverified' in mut:
                            if m[5] == 'H':
                                L[GAPS] = mb[GAPS] - {ident}
                                ev.append('P_GAP_CLOSED')
                    rcpt = h[1]
                    if 'DL2_newreceipt' in mut:
                        rcpt = (ce_m, k_m, ident)
                    if rcpt != h[1]:
                        ev.append('V_SAF6')
                    ev.append('P_LINK')
                    return tuple(L), ('R', rcpt, True), ev
        # DL-3: chain position
        if kind == 'E':
            if c['OPEN_FRESH'] and ce_m in mb[SEEN_CE]:
                return mb, ('P', mb[CE], mb[HK], mb[HA]), ev + ['P_DL3_REFUSE']
        else:
            pos_ok = (ce_m == mb[CE] and k_m == mb[HK] + 1 and prev_m == mb[HA])
            if not pos_ok and not (kind == 'C' and 'DL3_order' in mut):
                if kind == 'C':
                    t = self.tok(mb, m[6])
                    if any(x[S_MID] == mid for x in mb[STMTS]):
                        ev.append('P_STMT_REDELIVER_409')
                    if t is not None and self.eff(rt, mb, t) == 'I':
                        if 'DL3_spend' in mut and t[T_K] == self.K0:
                            toks = [x if x[T_SER] != t[T_SER] else x[:T_ST] + ('S',) for x in mb[TOKS]]
                            L[TOKS] = tuple(toks)
                            L[SPENT_LAST] = True
                            ev.append('V_PMD1')
                            return tuple(L), ('P', mb[CE], mb[HK], mb[HA]), ev
                        ev.append('P_DL3_STMT_TOKEN_KEPT')
                return mb, ('P', mb[CE], mb[HK], mb[HA]), ev
        # DL-4: evidence said HELD is held (E-B-2); room (E-Q-2, E-Q-3)
        if kind == 'N' and m[5] == 'H' and m[6] not in mb[EVID] and 'DL4_held' not in mut:
            ev.append('P_EVMISSING')
            return mb, ('M',), ev
        q = c['ITEM_QUOTA']
        if q is not None:
            is_alarm = (kind == 'O') or (kind == 'N' and U(ident)[2] == 'f')
            limit = q if is_alarm else q - c['ALARM_RESERVE']
            if mb[NSTORED] >= limit:
                L[REFUSED] = True
                ev.append('P_ITEMS_REFUSED')
                return tuple(L), ('Q',), ev
        newA = I(('A', prev_m, ident))
        # DL-5: not a statement: write, index, head
        if kind != 'C':
            L[NSTORED] = mb[NSTORED] + 1
            L[SEQ] = mb[SEQ] + 1
            L[HK] = k_m
            L[HA] = newA
            L[STORED] = mb[STORED] | {ident}
            rcpt = (ce_m, k_m, ident)
            if kind == 'E':
                # I-E-2: close the current chain epoch, keep everything, start the new chain
                if ce_m in mb[SEEN_CE]:
                    ev.append('P_EPOCH_REOPEN')
                if m[5] == 'LOST':
                    ev.append('P_OPEN_LOST')
                L[CE] = ce_m
                L[COMMIT] = m[6]
                L[OPEN_SEQ] = L[SEQ]
                L[SEEN_CE] = mb[SEEN_CE] | {ce_m}
                L[OPEN_REASON] = m[5]
            else:
                if any(e[0] == ident for e in mb[HELD]):
                    ev.append('V_SAF6')   # a second copy kept (only reachable with DL2_off)
                else:
                    L[HELD] = mb[HELD] | {(ident, rcpt, m[5] if kind == 'N' else None,
                                          m[6] if kind == 'N' else None)}
                if kind == 'N' and m[5] == 'X':
                    L[GAPS] = mb[GAPS] | {ident}                     # E-B-3
                    ev.append('P_GAP')
                if kind == 'O':
                    L[ALARM_SEQ] = L[SEQ]
                    L[ALARM_ANY] = L[SEQ]
            return tuple(L), ('R', rcpt, False), ev
        # DL-6: statement checks of 7.4
        return self.dl6_statement(rt, mb, L, gh, mid, m, newA, ev)

    def dl6_statement(self, rt, mb, L, gh, mid, m, newA, ev):
        c = self.c
        mut = self.mut
        # M-S-1: the same statement again: its first receipt, counts nothing
        for x in mb[STMTS]:
            if x[S_MID] == mid:
                ev.append('P_MS1')
                return mb, ('R', x[S_RCPT], False), ev
        (_, ce_m, k_m, prev_m, ident, ref, tser, rk, at, N, prev_ref, reveal, commit, carried,
         oldest_ref, called, evneed, obs_after, ok) = m
        t = self.tok(mb, tser)
        fails = []
        # ST-1
        if t is None:
            fails.append('ST1')
        else:
            ok1 = True
            if 'ST1_epoch' not in mut and 'MEPOCH' not in mut and t[T_MEP] != mb[MEP]:
                ok1 = False
            if 'ST1_budget' not in mut and (t[T_B] != 0 or t[T_K] != self.K0):
                ok1 = False
                ev.append('P_XB_REFUSED')
            if not ok1:
                fails.append('ST1')
        effst = self.eff(rt, mb, t) if t is not None else None
        # ST-2
        if 'ST2' not in mut and effst != 'I':
            fails.append('ST2')
        # ST-3
        if t is not None:
            a = self.age(rt, mb, t)
            if self.anomaly(rt, mb, t):
                ev.append('P_ANOMALY_AGE')
            if 'ST3' not in mut and (a is None or a > c['L']):
                fails.append('ST3')
                ev.append('P_EXPIRED_STMT')
        # ST-4: the checkpoint is genuine and bears the token: always true for the honest
        # courier with a trusted witness (not exercised by this model).
        # ST-5
        if 'ST5' not in mut and reveal != mb[COMMIT]:
            fails.append('ST5')
            ev.append('P_ST5_FAIL')
        # ST-6
        prev_in_ce = [x for x in mb[STMTS] if x[S_CE] == mb[CE]]
        if not prev_in_ce:
            if 'ST6_FZ' not in mut and not (rk == FZ and at == 0):
                fails.append('ST6')
        else:
            last = prev_in_ce[-1]
            if 'ST6' not in mut and not (at == last[S_N] and prev_ref == last[S_REF]):
                fails.append('ST6')
        if 'ST6' in fails:
            ev.append('P_ST6_FAIL')
        # ST-7
        st7 = True
        if rk in (FZ, RF) and carried != 0:
            st7 = False
        if not any(x[S_MEP] == mb[MEP] for x in mb[STMTS]) and rk not in (FZ, RF):
            st7 = False
        if rk == INC:
            okc = False
            for x in mb[STMTS]:
                if x[S_REF] == oldest_ref and x[S_CE] == mb[CE] and x[S_MEP] == mb[MEP]:
                    tx = self.tok(mb, x[S_TOK])
                    ax = self.age(rt, mb, tx) if tx is not None else None
                    if 'ST7_R' in mut or (ax is not None and ax <= c['R']):
                        okc = True
            if not okc:
                st7 = False
        if not st7:
            fails.append('ST7')
            ev.append('P_ST7_FAIL')
        # ST-8
        if mb[STMTS] and N < max(x[S_N] for x in mb[STMTS]):
            fails.append('ST8')
        # ST-9: limits are the mailbox's own: always true (fixed configuration).
        if not fails:
            # ------------- accepted: transition properties
            # SAF-1 (true time, true epoch, true state before)
            if (t is None or t[T_ST] != 'I' or rt - t[T_RT] > c['L'] or t[T_B] != 0
                    or t[T_K] != 'K0' or t[T_GMEP] != gh[G_GMEP]):
                ev.append('V_SAF1')
            # SAF-2: every item it commits to stored first; evidence said HELD is held
            for idn in self.chain_idents(prev_m):
                if idn not in mb[STORED]:
                    ev.append('V_SAF2')
                    break
            for e in mb[HELD]:
                if e[2] == 'H' and e[3] not in mb[EVID]:
                    ev.append('V_SAF2')
                    break
            # SAF-4: the statement's maker had the continuity secret of the open chain epoch
            if not ok or reveal != mb[COMMIT]:
                ev.append('V_SAF4')
            # SAF-3b at acceptance: carried observations no older than R (real time)
            if rk == INC:
                okr = False
                for x in mb[STMTS]:
                    if x[S_REF] == oldest_ref:
                        tx = self.tok(mb, x[S_TOK])
                        if tx is not None and tx[T_GMEP] == gh[G_GMEP] and rt - tx[T_RT] <= c['R']:
                            okr = True
                if not okr:
                    ev.append('V_SAF3B_ACC')
            toks = [x if x[T_SER] != tser else x[:T_ST] + ('U',) for x in mb[TOKS]]
            L[TOKS] = tuple(toks)
            L[NSTORED] = mb[NSTORED] + 1
            L[SEQ] = mb[SEQ] + 1
            L[HK] = k_m
            L[HA] = newA
            L[STORED] = mb[STORED] | {ident}
            L[COMMIT] = commit
            L[SPENT_LAST] = False
            rcpt = (ce_m, k_m, ident)
            rec = (mid, ref, ce_m, mb[MEP], tser, N, rk, carried, oldest_ref, L[SEQ], called,
                   evneed, obs_after, rcpt, gh[G_GMEP])
            L[STMTS] = mb[STMTS] + (rec,)
            ev.append('ACCEPT')
            return tuple(L), ('R', rcpt, False), ev
        # failed: the token, if ISSUED and named by a statement of its own courier key, SPENT
        if t is not None and t[T_ST] == 'U':
            ev.append('P_REPLAY_STMT_422')
        if t is not None and effst == 'I' and t[T_K] == self.K0:
            toks = [x if x[T_SER] != tser else x[:T_ST] + ('S',) for x in mb[TOKS]]
            L[TOKS] = tuple(toks)
            if t[T_B] == 0:
                L[SPENT_LAST] = True
            else:
                ev.append('P_XB_SPENT')
        return tuple(L), ('F', tuple(fails)), ev

    # ------------------------------------------------------------------ the courier
    def new_epoch_courier(self, mb, gh, reason, keep=None):
        """I-E-1: EPOCH_OPEN with a new chain_epoch and commit = Hb(s_1)."""
        ce = gh[G_NEXTCE]
        A0 = I(('A0', ce))
        ident = I(('E', ce, reason, (ce, 1)))
        mid = I(('E', ce, 1, A0, ident, reason, (ce, 1)))
        A1 = I(('A', A0, ident))
        obs = (None,) * self.c['RUNS']
        cursor = lastref = meplast = None
        if keep is not None:
            cursor, lastref, meplast, obs = keep
        cr = (ce, 1, I((A0, A1)), 1, cursor, lastref, meplast, obs, 0, None, (mid,), None, True)
        gh = (ce + 1, True) + gh[2:]
        return cr, gh, mid

    def courier_answer(self, s_cr, mid, ans, mb, ev):
        """Courier's handling of an answer to its own delivery."""
        cr = s_cr
        if cr is None:
            return cr
        out = cr[K_OUT]
        pend = cr[K_PEND]
        typ = ans[0]
        if typ == 'R':
            if pend is not None and mid == pend[0]:
                return self.courier_accepted(cr, mb)
            return cr[:K_OUT] + (tuple(x for x in out if x != mid),) + cr[K_OUT + 1:]
        if typ == 'F':
            if pend is not None and mid == pend[0]:
                if 'ST5' in ans[1]:
                    ev.append('P_COURIER_LOST_REFUSAL')
                    return None          # I-E-3: a refusal by I-E-6 means lost state
                out2 = tuple(x for x in out if x != mid)
                return cr[:K_PHASE] + (0, None, out2, None) + cr[K_PEND + 1:]
            return cr
        if typ == 'P':
            hce, hk, hA = ans[1], ans[2], ans[3]
            chain = U(cr[K_CHAIN])
            if hce == cr[K_CE] and hk < len(chain) and chain[hk] == hA and hA is not None:
                out2 = tuple(x for x in out if U(x)[2] > hk)
                return cr[:K_OUT] + (out2,) + cr[K_OUT + 1:]
            if pend is not None and hce == cr[K_CE] and hk == cr[K_K] + 1 and hA == pend[4]:
                return self.courier_accepted(cr, mb)
            if any(U(x)[0] == 'E' for x in out):
                return cr                # its own EPOCH_OPEN is not yet taken: deliver it first
            ev.append('P_COURIER_LOST_REFUSAL')
            return None                  # I-E-3 / M-D-3: not continuing the mailbox's head
        return cr                        # 'M' (re-upload is a separate move), 'Q', 'X'

    def courier_accepted(self, cr, mb):
        mid, ref, N, obs_after, A_after = cr[K_PEND]
        chain = U(cr[K_CHAIN]) + (A_after,)
        t = self.tok(mb, cr[K_TOK])
        meplast = t[T_MEP] if t is not None else None
        return (cr[K_CE], cr[K_K] + 1, I(chain), cr[K_J] + 1, N, ref, meplast, obs_after, 0, None,
                (), None, cr[K_OK])

    def courier_read(self, s, rk, fail, evok):
        """O-1..O-6 as one atomic reading. evok: dict run -> True (stored) / False (NOT_HELD)."""
        rt, mb, w, cr, bk, net, chal, ctr, rd, gh = s
        N, dec, stand = w
        ce, k, chainA, j = cr[K_CE], cr[K_K], cr[K_CHAIN], cr[K_J]
        cursor, obs = cr[K_CURSOR], cr[K_OBS]
        existing = [r for r in range(self.c['RUNS']) if stand[r] is not None]
        if rk in (FZ, RF):
            read = set(existing)
        else:
            named = set(dec[cursor:N])                                  # O-R-1
            if 'OR2' in self.mut:
                unsettled = set()                                       # mutant: O-R-2 removed
            else:
                unsettled = {r for r in existing if obs[r] is None or obs[r][0] in ('u', 'f')}
            read = (named | unsettled) & set(existing)
        carried = [r for r in existing if r not in read]
        at = 0 if rk == FZ else cursor
        chain = list(U(chainA))
        A = chain[-1]
        items = []
        mbL = None
        ev = []
        reasons = []
        for r in sorted(read):
            v, n, l3 = stand[r]
            if l3 and v == 'x':
                ev.append('P_L3_READ')
            if v in ('u', 'x', 'f'):
                ident = I(('N', r, v, n))
                claim = evid = None
                if v == 'f':
                    evid = I(('ev', r, n))
                    if evok.get(r, True):
                        claim = 'H'
                        if evid not in mb[EVID]:
                            if mbL is None:
                                mbL = list(mb)
                            mbL[EVID] = mbL[EVID] | {evid}
                    else:
                        claim = 'X'
                        reasons.append(('EVIDENCE_NOT_HELD', r))
                k += 1
                mid = I(('N', ce, k, A, ident, claim, evid))
                A = I(('A', A, ident))
                chain.append(A)
                items.append(mid)
        if fail:
            reasons.append(('DEADLINE', None))
        if mbL is not None:
            mb = tuple(mbL)
        tser = cr[K_TOK]
        if reasons:                                                     # O-W-1
            for (reason, run) in reasons:
                ident = I(('O', reason, run))
                k += 1
                mid = I(('O', ce, k, A, ident))
                A = I(('A', A, ident))
                chain.append(A)
                items.append(mid)
            cr2 = (ce, k, I(tuple(chain)), j, cursor, cr[K_LASTREF], cr[K_MEPLAST], obs, 0, None,
                   cr[K_OUT] + tuple(items), None, cr[K_OK])
            return mb, cr2, net | set(items), ev
        # statement (I-S-1, I-S-2)
        ref = I(('ref', ce, j, tser))
        obs_after = tuple(((stand[r][0], stand[r][1], ref, j) if r in read else obs[r])
                          for r in range(self.c['RUNS']))
        oldest_ref = None
        if carried:
            oldest = min(carried, key=lambda r: obs[r][3])
            oldest_ref = obs[oldest][2]
        called = I(frozenset(I(('N', r, stand[r][0], stand[r][1])) for r in existing
                             if stand[r][0] in ('u', 'x', 'f')))
        evneed = I(frozenset(I(('ev', r, stand[r][1])) for r in existing if stand[r][0] == 'f'))
        ident = I(('CS', ref))
        reveal = (ce, j) if cr[K_OK] else ('guess', ce, j)
        mid = I(('C', ce, k + 1, A, ident, ref, tser, rk, at, N, cr[K_LASTREF], reveal, (ce, j + 1),
                 len(carried), oldest_ref, called, evneed, obs_after,
                 cr[K_OK]))
        A_after = I(('A', A, ident))
        items.append(mid)
        pend = (mid, ref, N, obs_after, A_after)
        cr2 = (ce, k, I(tuple(chain)), j, cursor, cr[K_LASTREF], cr[K_MEPLAST], obs, 2, tser,
               cr[K_OUT] + tuple(items), pend, cr[K_OK])
        return mb, cr2, net | set(items), ev

    # ------------------------------------------------------------------ successors
    def succ(self, s):
        c = self.c
        mut = self.mut
        rt, mb, w, cr, bk, net, chal, ctr, rd, gh = s
        res = []

        def S(rt_=rt, mb_=mb, w_=w, cr_=cr, bk_=bk, net_=net, chal_=chal, ctr_=ctr, rd_=rd, gh_=gh):
            return (rt_, mb_, w_, cr_, bk_, net_, chal_, ctr_, rd_, gh_)

        def inc(i):
            return ctr[:i] + (ctr[i] + 1,) + ctr[i + 1:]

        def setmb(**kw):
            L = list(mb)
            for k_, v_ in kw.items():
                L[globals()[k_]] = v_
            return tuple(L)

        # --- time
        if rt < c['TMAX']:
            res.append(('tick', S(rt_=rt + 1, mb_=setmb(BT=mb[BT] + 1, MONO=mb[MONO] + 1)), ()))
            if ctr[C_SUSP] < c['SUSPENDS']:
                res.append(('suspend(boottime+1,monotonic+0)',
                            S(rt_=rt + 1, mb_=setmb(BT=mb[BT] + 1), ctr_=inc(C_SUSP)), ()))
        if ctr[C_WALL] < c['WALL_MOVES']:
            for d in (-1, 1):
                if -1 <= mb[WOFF] + d <= 1:
                    res.append(('wall_clock_%s' % ('back' if d < 0 else 'forward'),
                                S(mb_=setmb(WOFF=mb[WOFF] + d), ctr_=inc(C_WALL)), ()))
        # --- mailbox restart / reboot (M-T-2, M-T-3, M-K-5)
        for kind, ci, lim in (('reboot', C_REBOOT, c['REBOOTS']), ('restart', C_RESTART, c['RESTARTS'])):
            if ctr[ci] < lim:
                L = list(mb)
                if 'MEPOCH' not in mut:
                    L[MEP] = mb[MEP] + 1
                if kind == 'reboot':
                    L[BT] = 0
                    L[MONO] = 0
                if 'MEPOCH' not in mut and 'MK5' not in mut:
                    L[TOKS] = tuple(t if t[T_ST] == 'V' else t[:T_ST] + ('V',) for t in mb[TOKS])
                gh2 = gh[:G_GMEP] + (gh[G_GMEP] + 1,) + gh[G_GMEP + 1:]
                res.append(('mailbox_' + kind, S(mb_=tuple(L), ctr_=inc(ci), gh_=gh2), ()))
        # --- courier state loss, snapshot, restore
        if cr is not None and ctr[C_LOSS] < c['LOSSES']:
            res.append(('courier_loses_state', S(cr_=None, ctr_=inc(C_LOSS)), ()))
        # a copy of the courier's state is taken only between readings (phase 0, nothing
        # outstanding): a stated restriction of where an "old copy" can come from
        if (cr is not None and ctr[C_SNAP] < c['SNAPS'] and bk != cr and cr[K_PHASE] == 0
                and not cr[K_OUT]):
            res.append(('courier_state_copied', S(bk_=cr, ctr_=inc(C_SNAP)), ()))
        if bk is not None and ctr[C_RESTORE] < c['RESTORES'] and bk != cr:
            res.append(('courier_restored_from_old_copy', S(cr_=bk, ctr_=inc(C_RESTORE)), ('P_RESTORE',)))
        # --- witness. Reduction (sound for this model): the witness's state is read only by a
        # courier's reading and by no property, and no other move reads or writes it, so every
        # witness move commutes with every other move. Witness moves are therefore offered only
        # while the courier holds a token and has not yet read (phase 1): any interleaving is
        # equivalent to one in which the witness moves come just before the next reading.
        N, dec, stand = w
        wit_ok = cr is not None and cr[K_PHASE] == 1
        if N < c['NMAX'] and wit_ok:
            for r in range(c['RUNS']):
                for v in c['VALUES']:
                    st2 = stand[:r] + ((v, N + 1, False),) + stand[r + 1:]
                    res.append(('decision%d(run%d->%s)' % (N + 1, r, v), S(w_=(N + 1, dec + (r,), st2)), ()))
        for r in range(c['RUNS'] if wit_ok else 0):
            x = stand[r]
            if x is None:
                continue
            if c['L3'] and x[0] == 'u':
                for v in ('p', 'x'):
                    st2 = stand[:r] + ((v, x[1], True),) + stand[r + 1:]
                    res.append(('stored_result_without_decision(run%d->%s)' % (r, v), S(w_=(N, dec, st2)), ()))
            if ctr[C_CARRY] < c['CARRY_BREAKS'] and x[0] in ('p', 'x'):
                v = 'x' if x[0] == 'p' else 'p'
                st2 = stand[:r] + ((v, x[1], True),) + stand[r + 1:]
                res.append(('CAP_OWNER_changes_settled_run%d->%s' % (r, v),
                            S(w_=(N, dec, st2), ctr_=inc(C_CARRY)), ('P_CARRY_BREAK',)))
        # --- other budget's tokens, replayed challenge requests
        if ctr[C_B1] < c['B1_ISSUES']:
            ev = []
            mb2, gh2, ser = self.mk1_issue(rt, mb, gh, 1, self.K1, ev)
            res.append(('budget1_courier_takes_token%d' % ser, S(mb_=mb2, gh_=gh2, chal_=chal | {ser},
                                                                ctr_=inc(C_B1)), tuple(ev)))
        if ctr[C_REQ] < c['REQ_REPLAYS']:
            ev = []
            mb2, gh2, ser = self.mk1_issue(rt, mb, gh, 0, self.K0, ev)
            res.append(('adversary_replays_challenge_request->token%d' % ser,
                        S(mb_=mb2, gh_=gh2, chal_=chal | {ser}, ctr_=inc(C_REQ)), tuple(ev)))
        # --- evidence orphan removal (E-Q-4, T_ORPHAN abstracted to "any time")
        if c['ORPHAN']:
            named = {e[3] for e in mb[HELD] if e[3] is not None}
            for evid in sorted(mb[EVID] - named):
                res.append(('evidence_orphan_removed(%s)' % (U(evid),), S(mb_=setmb(EVID=mb[EVID] - {evid})),
                            ('P_ORPHAN',)))
        # --- loss of the mailbox's durable record of the budget
        if ctr[C_WIPE] < c['WIPES']:
            L = list(self.init()[1])
            L[MEP] = mb[MEP]; L[BT] = mb[BT]; L[MONO] = mb[MONO]; L[WOFF] = mb[WOFF]
            L[TOKS] = tuple(t for t in mb[TOKS] if t[T_B] != 0)
            res.append(('mailbox_loses_budget_record', S(mb_=tuple(L), ctr_=inc(C_WIPE)), ('P_WIPE', 'WIPE')))
        # --- adversary delivers any message ever sent (delay, reorder, replay); answer lost
        # (bounded: at most ADV_DELIVERIES such deliveries in a run; the courier's own deliveries,
        # in any order of its outstanding messages, are not bounded)
        adv = c['ADV_DELIVERIES']
        if adv is None or ctr[C_ADV] < adv:
            ctr_adv = ctr if adv is None else inc(C_ADV)
            for mid in net:
                mb2, ans, ev = self.deliver(rt, mb, gh, mid)
                if mb2 == mb and not ev:
                    continue                    # no effect at all: the same state
                res.append(('adversary_delivers ' + self.desc(mid) + ' -> ' + self.ansdesc(ans),
                            S(mb_=mb2, ctr_=ctr_adv), tuple(ev)))
        # --- courier moves
        if cr is None:
            if gh[G_NEXTCE] <= c['EMAX']:
                reason = 'LOST' if gh[G_EVER] else 'FIRST'
                if c['COURIER'] == 'resume' and gh[G_EVER] and mb[CE] is not None:
                    last = [x for x in mb[STMTS] if x[S_CE] == mb[CE]]
                    chain = tuple([None] * mb[HK] + [mb[HA]])
                    if last:
                        lx = last[-1]
                        cur, lref, mepl, obs = lx[S_N], lx[S_REF], lx[S_MEP], lx[S_OBS]
                        jn = U(lx[S_REF])[2] + 1
                    else:
                        cur = lref = mepl = None
                        obs = (None,) * c['RUNS']
                        jn = 1
                    cr2 = (mb[CE], mb[HK], I(chain), jn, cur, lref, mepl, obs, 0, None, (), None, False)
                    res.append(('courier_resumes_from_mailbox_head', S(cr_=cr2), ()))
                else:
                    keep = None
                    if c['COURIER'] == 'oldcursor' and gh[G_EVER] and mb[STMTS]:
                        lx = mb[STMTS][-1]
                        keep = (lx[S_N], lx[S_REF], lx[S_MEP], lx[S_OBS])
                    cr2, gh2, mid = self.new_epoch_courier(mb, gh, reason, keep)
                    res.append(('courier_opens_epoch(%s) ' % reason + self.desc(mid),
                                S(cr_=cr2, gh_=gh2, net_=net | {mid}), ()))
        else:
            phase = cr[K_PHASE]
            if phase == 0 and cr[K_PEND] is None:
                # O-1 / M-K-1: take a challenge (fresh), or be handed any genuine earlier one
                if ctr[C_READS] < c['MAX_READS']:
                    ev = []
                    mb2, gh2, ser = self.mk1_issue(rt, mb, gh, 0, self.K0, ev)
                    cr2 = cr[:K_PHASE] + (1, ser) + cr[K_TOK + 1:]
                    res.append(('courier_takes_challenge->token%d' % ser,
                                S(mb_=mb2, gh_=gh2, cr_=cr2, chal_=chal | {ser}), tuple(ev)))
                if c['CHAL_REPLAY'] and ctr[C_READS] < c['MAX_READS']:
                    for ser in sorted(chal):
                        cr2 = cr[:K_PHASE] + (1, ser) + cr[K_TOK + 1:]
                        res.append(('courier_handed_old_challenge(token%d)' % ser, S(cr_=cr2), ()))
            if phase == 1 and ctr[C_READS] < c['MAX_READS']:
                t = self.tok(mb, cr[K_TOK])
                tmep = t[T_MEP] if t is not None else None
                if cr[K_CURSOR] is None:
                    kinds = [FZ]
                elif tmep != cr[K_MEPLAST]:
                    kinds = [RF]                                   # O-C-4, ST-7
                else:
                    kinds = [RF]
                    if c['INCREMENTAL']:
                        kinds.append(INC)
                existing = [r for r in range(c['RUNS']) if stand[r] is not None]
                for rk in kinds:
                    if rk == INC:
                        named = set(dec[cr[K_CURSOR]:N])
                        uns = set() if 'OR2' in mut else {r for r in existing if cr[K_OBS][r] is None
                                                         or cr[K_OBS][r][0] in ('u', 'f')}
                        if not [r for r in existing if r not in (named | uns)]:
                            continue                            # nothing would be carried
                        readset = (named | uns) & set(existing)
                    else:
                        readset = set(existing)
                    fruns = [r for r in sorted(readset) if stand[r][0] == 'f'
                             and I(('ev', r, stand[r][1])) not in mb[EVID]]
                    evchoices = [{}]
                    if c['EV_FAIL']:
                        evchoices = []
                        for bits in range(1 << len(fruns)):
                            evchoices.append({r: not ((bits >> i) & 1) for i, r in enumerate(fruns)})
                    for fail in ((False, True) if c['READ_FAIL'] else (False,)):
                        for evok in evchoices:
                            mb2, cr2, net2, ev = self.courier_read(s, rk, fail, evok)
                            lab = 'courier_reads(%s,N%d%s%s)' % (
                                rk, N, ',DEADLINE' if fail else '',
                                ''.join(',evidence_run%d_%s' % (r, 'stored' if ok_ else 'REFUSED')
                                        for r, ok_ in sorted(evok.items())))
                            res.append((lab, S(mb_=mb2, cr_=cr2, net_=net2, ctr_=inc(C_READS)), tuple(ev)))
            # deliver one of its own outstanding messages (in any order) and read the answer
            for mid in cr[K_OUT]:
                mb2, ans, ev0 = self.deliver(rt, mb, gh, mid)
                ev = list(ev0)
                cr2 = self.courier_answer(cr, mid, ans, mb2, ev)
                res.append(('courier_delivers ' + self.desc(mid) + ' -> ' + self.ansdesc(ans),
                            S(mb_=mb2, cr_=cr2), tuple(ev)))
            # E-B-5: re-upload evidence it keeps, for an outstanding notice that says HELD
            ups = set()
            for mid in cr[K_OUT]:
                m = U(mid)
                if m[0] == 'N' and m[5] == 'H' and m[6] not in mb[EVID]:
                    ups.add(m[6])
            for evid in sorted(ups):
                res.append(('courier_reuploads_evidence(%s)' % (U(evid),),
                            S(mb_=setmb(EVID=mb[EVID] | {evid})), ()))
        # --- reader and status (C-S-1, C-S-2)
        if rd is not None:
            q, asked_at, sts, nstat, belief = rd
            if q < c['QMAX']:
                res.append(('reader_asks(nonce%d)' % (q + 1), S(rd_=(q + 1, nstat, sts, nstat, None)), ()))
            if q > 0 and nstat < c['NSTAT_MAX']:
                cov = self.c1_covered(rt, mb) is not None
                res.append(('mailbox_answers_status(nonce%d,%s)' % (q, 'COVERED' if cov else 'NOT_COVERED'),
                            S(rd_=(q, asked_at, sts | {(q, cov, nstat)}, nstat + 1, belief)), ()))
            for x in sorted(sts):
                if belief == x:
                    continue
                if x[0] == q or 'CS2_nonce' in mut:
                    res.append(('reader_takes_status(nonce%d,%s,#%d)' % (x[0], 'COVERED' if x[1] else 'NOT', x[2]),
                                S(rd_=(q, asked_at, sts, nstat, x)), ()))
                else:
                    res.append(('reader_rejects_status(nonce%d)#%d' % (x[0], x[2]), s, ('P_STALE_STATUS_REJECTED',)))
        return res

    @staticmethod
    def ansdesc(ans):
        t = ans[0]
        if t == 'R':
            return 'receipt%s' % (' (first receipt, LINKED)' if ans[2] else '')
        if t == 'P':
            return '409 CHAIN_POSITION(head ce%s k%d)' % (ans[1], ans[2])
        if t == 'M':
            return '409 EVIDENCE_MISSING'
        if t == 'F':
            return '422 %s' % (','.join(ans[1]),)
        if t == 'Q':
            return '507'
        return 'error'

    # ------------------------------------------------------------------ state properties
    def state_checks(self, s):
        rt, mb, w, cr, bk, net, chal, ctr, rd, gh = s
        key = (rt, mb, gh[G_GMEP], ctr[C_REBOOT] >= 1, ctr[C_RESTART] >= 1, rd)
        r = self._scache.get(key)
        if r is None:
            r = self.state_checks_raw(s)
            if len(self._scache) > 1500000:
                self._scache.clear()
            self._scache[key] = r
        return r

    def state_checks_raw(self, s):
        """Returns list of violated state properties and reached state probes."""
        c = self.c
        rt, mb, w, cr, bk, net, chal, ctr, rd, gh = s
        out = []
        S = self.c1_covered(rt, mb)
        if S is not None:
            out.append('P_COVERED')
            t = self.tok(mb, S[S_TOK])
            # SAF-3 / central (ii): token issued no more than L ago (true time), same epoch
            if not (rt - t[T_RT] <= c['L'] and t[T_GMEP] == gh[G_GMEP]):
                out.append('V_SAF3')
            # SAF-5 / central (iii): a FROM_ZERO statement accepted after the last EPOCH_OPEN
            if not (S[S_SEQ] > mb[OPEN_SEQ] and any(
                    x[S_RK] == FZ and mb[OPEN_SEQ] < x[S_SEQ] <= S[S_SEQ] and x[S_CE] == mb[CE]
                    for x in mb[STMTS])):
                out.append('V_SAF5')
            # SAF-7: no gap, no OBSERVATION_INCOMPLETE taken (stored or linked) after S
            if mb[GAPS] or mb[ALARM_ANY] > S[S_SEQ]:
                out.append('V_SAF7')
            # central (i): every notice identity the covering reading called for is held
            held = {e[0] for e in mb[HELD]}
            if not U(S[S_CALLED]) <= held:
                out.append('V_CENT_N')
            # C-2 last bullet: evidence a finding rests on is held
            if not U(S[S_EVNEED]) <= mb[EVID]:
                out.append('V_CENT_E')
            # N-2 wording: "observations no more than R old" at the time of the status
            if S[S_RK] == INC:
                okr = False
                for x in mb[STMTS]:
                    if x[S_REF] == S[S_OLDEST]:
                        tx = self.tok(mb, x[S_TOK])
                        if tx is not None and rt - tx[T_RT] <= c['R']:
                            okr = True
                if not okr:
                    out.append('V_R_AT_STATUS')
                if S[S_CARR] >= 1:
                    out.append('P_COVERED_INC')
            # C-1 against 8.2: a reason of 8.2 holds while C-1 says COVERED
            if mb[SPENT_LAST] or mb[REFUSED]:
                out.append('V_C1_VS_82')
            if mb[OPEN_REASON] == 'LOST':
                out.append('P_COVERED_AFTER_LOST')
            if ctr[C_REBOOT] >= 1:
                out.append('P_COVERED_AFTER_REBOOT')
            if ctr[C_RESTART] >= 1:
                out.append('P_COVERED_AFTER_RESTART')
            if S[S_RK] == RF and mb[MEP] > 0:
                out.append('P_COVERED_REFRESH_NEWMEP')
        else:
            # would be covered but for C-1.4
            if mb[ALARM_SEQ] >= 0 and mb[CE] is not None:
                lst = [x for x in mb[STMTS] if x[S_CE] == mb[CE] and x[S_MEP] == mb[MEP]]
                if lst and mb[ALARM_SEQ] > lst[-1][S_SEQ] and not mb[GAPS]:
                    t = self.tok(mb, lst[-1][S_TOK])
                    if t is not None and self.eff(rt, mb, t) == 'U':
                        out.append('P_NOTCOV_BY_ALARM')
        if rd is not None:
            q, asked_at, sts, nstat, belief = rd
            if belief is not None:
                # SAF-8: a status the reader accepts carries its own nonce: produced after the question
                if belief[2] < asked_at or belief[0] != q:
                    out.append('V_SAF8')
                if belief[1]:
                    out.append('P_READER_COVERED')
        return out


# ============================================================================== search
def bfs(model, max_states, progress=None):
    init = model.init()
    seen = {hash(init): (None, None)}
    first = {}        # name -> (state_hash, label or None, depth)
    frontier = deque([(init, 0)])
    for p in model.state_checks(init):
        first.setdefault(p, (hash(init), None, 0))
    transitions = 0
    complete = True
    maxdepth = 0
    t0 = time.time()
    while frontier:
        s, d = frontier.popleft()
        hs = hash(s)
        maxdepth = max(maxdepth, d)
        for label, t, evs in model.succ(s):
            transitions += 1
            if 'WIPE' not in evs and not (s[1][STORED] <= t[1][STORED]):
                evs = tuple(evs) + ('V_SAF6',)
            for e in evs:
                if e not in first:
                    first[e] = (hs, label, d + 1)
            ht = hash(t)
            if ht in seen:
                continue
            seen[ht] = (hs, label)
            for p in model.state_checks(t):
                if p not in first:
                    first[p] = (ht, None, d + 1)
            if len(seen) >= max_states:
                complete = False
                frontier.clear()
                break
            frontier.append((t, d + 1))
        if progress and len(seen) % 200000 < 50:
            pass
    return dict(seen=seen, first=first, states=len(seen), transitions=transitions,
                complete=complete, maxdepth=maxdepth, secs=time.time() - t0, init=init)


def trace_to(model, r, key):
    seen = r['seen']
    hs, label, depth = r['first'][key]
    labels = []
    if label is not None:
        labels.append(label)
    h = hs
    while True:
        ph, lab = seen[h]
        if ph is None:
            break
        labels.append(lab)
        h = ph
    labels.reverse()
    return labels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--declared', required=True)
    args = ap.parse_args()
    import configs
    import hashlib
    cfg = configs.CONFIGS[args.config]
    with open(args.declared, 'rb') as f:
        decl_bytes = f.read()
    decl = json.loads(decl_bytes)
    decl_sha = hashlib.sha256(decl_bytes).hexdigest()
    model = Model(cfg)
    t0 = time.time()
    r = bfs(model, model.c['MAX_STATES'])
    wall = time.time() - t0
    props = {}
    for p in ALL_PROPS:
        key = 'V_' + p
        applicable = not (p == 'SAF8' and not model.c['READER'])
        if not applicable:
            props[p] = dict(observed='n/a')
            continue
        if key in r['first']:
            tr = trace_to(model, r, key)
            props[p] = dict(observed='violated', depth=len(tr), trace=tr)
        else:
            props[p] = dict(observed='holds' if r['complete'] else 'no violation found (INCOMPLETE)')
    probes = {}
    for p in PROBES:
        if p in r['first']:
            tr = trace_to(model, r, p)
            probes[p] = dict(observed='reached', depth=len(tr), trace=tr)
        else:
            probes[p] = dict(observed='not_reached' if r['complete'] else 'not reached (INCOMPLETE)')
    mism = []
    for p, v in props.items():
        dv = decl['properties'].get(p, 'undeclared')
        v['declared'] = dv
        v['agree'] = (dv == v['observed'])
        if not v['agree']:
            mism.append(p)
    for p, v in probes.items():
        dv = decl['probes'].get(p, 'any')
        v['declared'] = dv
        v['agree'] = (dv == 'any' or dv == v['observed'])
        if not v['agree']:
            mism.append(p)
    printable_cfg = {k: (list(v) if isinstance(v, tuple) else v) for k, v in model.c.items()}
    result = dict(config=args.config, bounds=printable_cfg, declared_file=args.declared,
                  declared_sha256=decl_sha, states=r['states'], transitions=r['transitions'],
                  max_depth=r['maxdepth'], complete=r['complete'],
                  result='COMPLETE' if r['complete'] else 'INCOMPLETE (state cap hit)',
                  wall_seconds=round(wall, 1), interned_values=len(_IL),
                  key='64-bit Python hash of the state tuple (collision would prune a state)',
                  properties=props, probes=probes, mismatches=mism,
                  verdict_agrees_with_declaration=(not mism))
    with open(args.out, 'w') as f:
        json.dump(result, f, indent=1)
    print('config %s: states=%d transitions=%d depth=%d complete=%s secs=%.1f' % (
        args.config, r['states'], r['transitions'], r['maxdepth'], r['complete'], wall))
    for p, v in props.items():
        print('  %-12s declared=%-10s observed=%-10s %s%s' % (
            p, v['declared'], v['observed'], '' if v['agree'] else 'MISMATCH ',
            ('depth %d' % v['depth']) if 'depth' in v else ''))
    for p, v in probes.items():
        if v['declared'] != 'any' or v['observed'] == 'reached':
            print('  %-26s declared=%-12s observed=%-12s %s' % (
                p, v['declared'], v['observed'], '' if v['agree'] else 'MISMATCH'))
    for p, v in list(props.items()):
        if v.get('observed') == 'violated':
            print('  shortest trace for %s:' % p)
            for i, l in enumerate(v['trace']):
                print('     %2d. %s' % (i + 1, l))
    print('  verdict agrees with declaration: %s' % (not mism))


if __name__ == '__main__':
    main()
