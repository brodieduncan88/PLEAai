#!/usr/bin/env python3
"""
Separately authored bounded model of "Amendment 16 ... Step 3", VERSION 2
(SPEC_v2_as_sent_to_review.md, SHA-256 4a5ad166...), sections 5 to 8, properties of section 9.

Internal, separately authored verification. NOT independent validation; not a proof for unbounded
parameters; says nothing about any implementation. Round 2 of the model of G/model2 (left unchanged).

Organised by rule id: dl2_.. dl6_ in deliver_raw(), st1..st9 in dl6_statement(), M-K-* in
mk1_issue()/request(), M-T-* in age(), C-1.1..C-1.8 in c1_covered(), I-O-* in courier_answer() and
courier_take_challenge(), O-* in courier_read(). Readings of text that is still not definite are
switches in BASE; mechanisms removed by mutants are names in MUTANTS.

Abstractions (REPORT in the final answer):
  * exact symbolic hashes; unforgeable signatures (every item in the network was made by K0);
  * the witness signs honestly what its chain is, but its chain MAY be truncated (rollback) and then
    grown differently (fork) by the adversary (O-3, O-4, SAF-10);
  * a run's standing: u (outcome notice, unsettled), p (settled, no notice), x (settled, outcome
    notice), f (a finding: EQUIVOCATION, never settled, absorbing: once f, always f);
  * notice identity (I-ID-1): u/x -> (run, standing, last decision naming the run); f -> (run, 'f')
    (the set of findings), binding one report whose evidence id is ('ev', run, first f decision);
  * OBSERVATION_INCOMPLETE identity (I-ID-2): (token); EPOCH_OPEN/COVERAGE: unique (I-ID-3);
  * a reading is one atomic event; OBSERVATION_PART items are not modelled.
"""
import sys, os, json, time, argparse
from collections import deque

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

BASE = dict(
    RUNS=1, NMAX=1, VALUES=('u', 'x'), L3=False, TMAX=1, L=1, R=0, TOKENS_MAX=1, EMAX=1, MAX_READS=2,
    REBOOTS=0, RESTARTS=0, WALL_MOVES=0, SUSPENDS=0, LOSSES=0, SNAPS=0, RESTORES=0, REQ_REPLAYS=0,
    CARRY_BREAKS=0, ORPHAN=False, WIPES=0, EV_FAIL=False, READ_FAIL=False, INCREMENTAL=True,
    WTRUNC=0, ROOMS=None, INDEX_IN_OBS=True, READER=False, QMAX=2, NSTAT_MAX=3,
    COURIER='honest',          # honest | resume | oldcursor | nocheck
    MUTANTS=(), MAX_STATES=6_000_000,
)

(C_REBOOT, C_RESTART, C_WALL, C_SUSP, C_LOSS, C_SNAP, C_RESTORE, C_REQ, C_CARRY, C_WIPE, C_READS,
 C_WTRUNC) = range(12)
NCTR = 12

(MEP, BT, MONO, WOFF, TOKS, CE, HK, HA, COMMIT, ANCHOR, HELD, STORED, DIG, STMTS, GAPS, EVID, NAMED,
 SEEN_CE, ALARM_SEQ, RSTMT_SEQ, ROOM_SEQ, OPEN_SEQ, SEQ, ROOMS, OPEN_REASON, REQS, PENDING, GANCHOR,
 NHELD_EVER, HCLAIM) = range(30)
NMB = 30

T_SER, T_B, T_K, T_MEP, T_GMEP, T_BT, T_WALL, T_MONO, T_RT, T_ST = range(10)
(S_MID, S_REF, S_CE, S_MEP, S_TOK, S_N, S_HEADN, S_RK, S_CARR, S_OLDEST, S_SEQ, S_CALLED, S_EVNEED,
 S_OBS, S_GMEP, S_AT, S_HEADAT) = range(17)
(K_CE, K_CHAIN, K_J, K_LASTREF, K_MEPLAST, K_OBS, K_PHASE, K_CHAL, K_OUT, K_RKMAX, K_SENT, K_PEND,
 K_OK, K_EORCPT, K_MISSING, K_STALE) = range(16)
G_NEXTCE, G_EVER, G_GMEP, G_SERIAL, G_NREQ = range(5)

STATE_PROPS = ['SAF3', 'SAF5', 'SAF7', 'SAF8', 'CENT_N', 'CENT_E', 'R_AT_STATUS', 'C1_VS_82']
TRANS_PROPS = ['SAF1', 'SAF2', 'SAF4', 'SAF6', 'SAF10', 'SAF11', 'SAF3B_ACC', 'PMK1', 'DL2_SAME',
               'REFUSED_NOPOS']
ALL_PROPS = TRANS_PROPS + STATE_PROPS
PROBES = [
    'P_COVERED', 'P_COVERED_INC', 'P_COVERED_AFTER_LOST', 'P_COVERED_AFTER_REBOOT',
    'P_COVERED_AFTER_RESTART', 'P_COVERED_REFRESH_NEWMEP', 'P_LINK', 'P_DL2_FIRST_RECEIPT_STMT',
    'P_DL2_FIRST_REFUSAL', 'P_STMT_BEFORE_ITEMS', 'P_EPOCH_KNOWN', 'P_OPEN_LOST', 'P_OPEN_CLOSES_LIVE',
    'P_COURIER_LOST', 'P_LOST_ST5', 'P_MAILBOX_ROLLBACK', 'P_RESTORE', 'P_STALECOPY_COUNTED',
    'P_FORK_ALARM', 'P_ROLLBACK_ALARM', 'P_ST6_FAIL', 'P_EVICT', 'P_EXPIRED_STMT', 'P_ANOMALY_AGE',
    'P_REQ_REPLAY_REFUSED', 'P_GAP', 'P_GAP_CLOSED', 'P_ORPHAN', 'P_EVMISSING', 'P_NOTHELD_REMADE',
    'P_STMT_ACCEPTED_WITH_GAP', 'P_ROOM_NOTICE', 'P_ROOM_ALARM', 'P_ROOM_OBS',
    'P_ALARM_REFUSED_OBS_ONLY', 'P_ALARM_AFTER_ROOM_REFUSAL', 'P_NOTCOV_BY_ALARM',
    'P_NOTCOV_BY_REFUSED_STMT', 'P_NOTCOV_STALE_CARRY', 'P_L3_READ', 'P_ST7_FAIL', 'P_READER_COVERED',
    'P_STALE_STATUS_REJECTED', 'P_WIPE', 'P_CARRY_BREAK', 'P_PENDING_ORPHAN', 'P_WITNESS_TRUNC',
    'P_ALARM_TAKEN', 'P_ST5_FAIL',
]


class Model:
    def __init__(self, cfg):
        self.c = dict(BASE)
        self.c.update(cfg)
        self.mut = set(self.c['MUTANTS'])
        self._dcache = {}
        self._scache = {}
        self._stcache = {}

    # ------------------------------------------------------------------ init
    def init(self):
        mb = [None] * NMB
        mb[MEP] = 0; mb[BT] = 0; mb[MONO] = 0; mb[WOFF] = 0; mb[TOKS] = ()
        self.wipe_fields(mb)
        mb[GANCHOR] = None
        mb[NHELD_EVER] = frozenset()
        w = ((), frozenset())
        rd = (0, 0, frozenset(), 0, None) if self.c['READER'] else None
        gh = (1, False, 0, 0, 0)
        return (0, tuple(mb), w, None, None, frozenset(), (0,) * NCTR, rd, gh)

    def wipe_fields(self, mb):
        mb[CE] = None; mb[HK] = 0; mb[HA] = None; mb[COMMIT] = None; mb[ANCHOR] = None
        mb[HELD] = frozenset(); mb[STORED] = frozenset(); mb[DIG] = frozenset(); mb[STMTS] = ()
        mb[GAPS] = frozenset(); mb[EVID] = frozenset(); mb[NAMED] = frozenset(); mb[SEEN_CE] = frozenset()
        mb[ALARM_SEQ] = -1; mb[RSTMT_SEQ] = -1; mb[ROOM_SEQ] = -1; mb[OPEN_SEQ] = -1; mb[SEQ] = 0
        mb[ROOMS] = (0, 0, 0); mb[OPEN_REASON] = None; mb[REQS] = frozenset(); mb[PENDING] = None
        mb[HCLAIM] = frozenset()

    # ------------------------------------------------------------------ the witness
    def stand(self, w):
        r_ = self._stcache.get(w)
        if r_ is not None:
            return r_
        dec, l3 = w
        out = []
        for r in range(self.c['RUNS']):
            cur = None
            for i, (rr, v) in enumerate(dec, 1):
                if rr != r:
                    continue
                if cur is not None and cur[0] == 'f':
                    cur = ('f', i, False, cur[3])          # f is absorbing; findings unchanged
                else:
                    cur = (v, i, False, i if v == 'f' else None)
            if cur is not None and cur[0] in ('u', 'p', 'x'):
                for (rr, n, wv) in l3:
                    if rr == r and n == cur[1]:
                        cur = (wv, n, True, None)
            out.append(cur)
        r_ = tuple(out)
        self._stcache[w] = r_
        return r_

    @staticmethod
    def whead(dec, n):
        return I(('W',) + tuple(dec[:n]))

    @staticmethod
    def ident_of(r, st):
        v = st[0]
        if v == 'f':
            return I(('N', r, 'f'))
        return I(('N', r, v, st[1]))

    @staticmethod
    def evid_of(r, st):
        return I(('ev', r, st[3]))

    # ------------------------------------------------------------------ time M-T-*
    def age(self, rt, mb, tok):
        mut = self.mut
        if tok[T_MEP] != mb[MEP] and 'TICK_CROSS' not in mut and 'MEPOCH' not in mut:
            return None                                       # M-T-2
        boot = (mb[MONO] - tok[T_MONO]) if 'MT1_mono' in mut else (mb[BT] - tok[T_BT])   # M-T-1
        wall = (rt + mb[WOFF]) - tok[T_WALL]
        if 'MT5_wall' in mut:
            return wall
        if wall < 0 or wall != boot:                          # M-T-5, CLOCK_TOLERANCE = 0
            return max(boot, wall)
        return boot

    def anomaly(self, rt, mb, tok):
        if tok[T_MEP] != mb[MEP]:
            return False
        return ((rt + mb[WOFF]) - tok[T_WALL]) != (mb[BT] - tok[T_BT])

    def eff(self, rt, mb, tok):
        """M-K-3/M-K-4: EXPIRED by age (from ISSUED or USED)."""
        st = tok[T_ST]
        if st in ('V', 'S'):
            return st
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

    # ------------------------------------------------------------------ M-K-1 / M-K-2
    def mk1_issue(self, rt, mb, gh, ev):
        serial = gh[G_SERIAL]
        toks = list(mb[TOKS])
        issued = [i for i, t in enumerate(toks) if t[T_B] == 0 and self.eff(rt, mb, t) == 'I']
        if len(issued) >= self.c['TOKENS_MAX']:                    # M-K-2: the oldest ISSUED -> VOID
            i = min(issued, key=lambda i: toks[i][T_SER])
            toks[i] = toks[i][:T_ST] + ('V',)
            ev.append('P_EVICT')
        toks.append((serial, 0, 'K0', mb[MEP], gh[G_GMEP], mb[BT], rt + mb[WOFF], mb[MONO], rt, 'I'))
        L = list(mb)
        L[TOKS] = tuple(toks)
        gh = gh[:G_SERIAL] + (serial + 1,) + gh[G_SERIAL + 1:]
        return L, gh, serial

    # ------------------------------------------------------------------ C-1
    def c1_covered(self, rt, mb):
        mut = self.mut
        ce = mb[CE]
        if ce is None:                                               # NEVER
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
        if mb[RSTMT_SEQ] > S[S_SEQ] and 'C15_off' not in mut:        # C-1.5
            return None
        if mb[ROOM_SEQ] > S[S_SEQ] and 'C16_off' not in mut:         # C-1.6
            return None
        if S[S_CARR] > 0 and 'C17_off' not in mut:                   # C-1.7
            if not self.oldest_fresh(rt, mb, S, mailbox_time=True):
                return None
        return S                                                     # C-1.8: record readable (always)

    def oldest_fresh(self, rt, mb, S, mailbox_time):
        for x in mb[STMTS]:
            if x[S_REF] == S[S_OLDEST]:
                tx = self.tok(mb, x[S_TOK])
                if tx is None:
                    return False
                if mailbox_time:
                    a = self.age(rt, mb, tx)
                    return a is not None and a <= self.c['R']
                return rt - tx[T_RT] <= self.c['R']
        return False

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
            return 'EPOCH_OPEN(ce%s,%s)#%d' % (m[1], m[5], mid)
        if k == 'N':
            idn = U(m[4])
            cl = '' if m[5] is None else ',' + {'H': 'HELD', 'X': 'NOT_HELD'}[m[5]]
            return 'NOTICE(ce%s,k%d,run%d=%s%s)#%d' % (m[1], m[2], idn[1], '/'.join(map(str, idn[2:])), cl, mid)
        if k == 'O':
            return 'OBS_INCOMPLETE(ce%s,k%d,%s)#%d' % (m[1], m[2], ','.join(m[5]), mid)
        if k == 'C':
            return 'STATEMENT(ce%s,k%d,j%d,tok%d,%s,at%d,N%d,carried%d)#%d' % (
                m[1], m[2], U(m[5])[2], m[6], m[7], m[8], m[10], m[15], mid)
        if k == 'Q':
            return 'CHALLENGE_REQUEST(#%d,epoch%d)' % (m[1], m[2])
        return str(m)

    @staticmethod
    def ansdesc(ans):
        t = ans[0]
        return {'R': lambda: 'receipt' + (' + LINKED' if ans[2] else ''),
                'P': lambda: '409 CHAIN_POSITION(head ce%s k%d)' % (ans[1], ans[2]),
                'K': lambda: '409 EPOCH_KNOWN', 'M': lambda: '409 EVIDENCE_MISSING',
                'F': lambda: '422 ' + ','.join(ans[1]), 'Q': lambda: '507 ' + ans[1],
                'RP': lambda: '409 REPLAY', 'EP': lambda: '409 EPOCH', 'W': lambda: '(write pending)',
                'T': lambda: 'challenge token%d' % ans[1]}.get(t, lambda: str(ans))()

    def normalise(self, mb):
        vals = {mb[ALARM_SEQ], mb[RSTMT_SEQ], mb[ROOM_SEQ], mb[OPEN_SEQ]} | {x[S_SEQ] for x in mb[STMTS]}
        vals.discard(-1)
        rank = {v: i for i, v in enumerate(sorted(vals))}
        rank[-1] = -1
        L = list(mb)
        for f in (ALARM_SEQ, RSTMT_SEQ, ROOM_SEQ, OPEN_SEQ):
            L[f] = rank[mb[f]]
        L[STMTS] = tuple(x[:S_SEQ] + (rank[x[S_SEQ]],) + x[S_SEQ + 1:] for x in mb[STMTS])
        L[SEQ] = len(vals)
        if self.c['ROOMS'] is None:
            L[ROOMS] = (0, 0, 0)
        return tuple(L)

    def is_iid1(self, kind):
        return kind == 'N' or (kind == 'O' and 'ALARM_NOTOKEN' in self.mut)

    def held_rcpt(self, mb, ident):
        for e in mb[HELD]:
            if e[0] == ident:
                return e[1]
        return None

    # ------------------------------------------------------------------ the mailbox: 7.3
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

    def dig_lookup(self, mb, mid):
        for (d, a) in mb[DIG]:
            if d == mid:
                return a
        return None

    def deliver_raw(self, rt, mb, gh, mid):
        c = self.c
        mut = self.mut
        ev = []
        m = U(mid)
        kind = m[0]
        ce_m, k_m, prev_m, ident = m[1], m[2], m[3], m[4]
        # DL-1: always passes (genuine items of K0)
        # DL-2: same digest held in the open chain epoch, or refused there as a statement (at 7.4)
        late_dl2 = (kind == 'C' and 'DL2_AFTER_DL3' in mut)
        if ce_m == mb[CE] and not late_dl2:
            a = self.dig_lookup(mb, mid)
            if a is not None:
                ev.append('DL2HIT')
                if kind == 'C':
                    ev.append('P_DL2_FIRST_RECEIPT_STMT' if a[0] == 'R' else 'P_DL2_FIRST_REFUSAL')
                return mb, a, ev
        # DL-3
        L = list(mb)
        if kind == 'E':
            ok = ((ce_m not in mb[SEEN_CE] or 'OPEN_KNOWN' in mut) and k_m == 1
                  and prev_m == I(('A0', ce_m)))
            if not ok:
                if ce_m in mb[SEEN_CE]:
                    ev.append('P_EPOCH_KNOWN')
                    return mb, ('K',), ev
                return mb, ('P', mb[CE], mb[HK], mb[HA]), ev
        else:
            pos_ok = (ce_m == mb[CE] and k_m == mb[HK] + 1 and prev_m == mb[HA])
            if not pos_ok and not (kind == 'C' and 'DL3_order' in mut and ce_m == mb[CE]):
                if late_dl2 and self.dig_lookup(mb, mid) is not None:
                    ev.append('V_DL2_SAME')      # a re-sent statement not answered as the first time
                if kind == 'C':
                    t = self.tok(mb, m[6])
                    if t is not None and self.eff(rt, mb, t) == 'I':
                        if 'DL3_spend' in mut:
                            L[TOKS] = tuple(x if x[T_SER] != t[T_SER] else x[:T_ST] + ('S',) for x in mb[TOKS])
                            ev.append('V_SAF2')
                            return tuple(L), ('P', mb[CE], mb[HK], mb[HA]), ev
                        if ce_m == mb[CE] and k_m > mb[HK] + 1:
                            ev.append('P_STMT_BEFORE_ITEMS')
                return mb, ('P', mb[CE], mb[HK], mb[HA]), ev
        if late_dl2:
            a = self.dig_lookup(mb, mid)
            if a is not None:
                return mb, a, ev
        # DL-4: evidence said HELD is held (E-B-2); room (E-Q-2, E-Q-3)
        if kind == 'N' and m[5] == 'H' and m[6] not in mb[EVID] and 'DL4_held' not in mut:
            ev.append('P_EVMISSING')
            return mb, ('M',), ev
        link = self.is_iid1(kind) and self.held_rcpt(mb, ident) is not None and 'DL2_off' not in mut
        rooms = c['ROOMS']
        need = self.room_need(kind, link)
        if rooms is not None:
            have = mb[ROOMS]
            full = [nm for i, nm in enumerate(('NOTICE_QUOTA', 'ALARM_RESERVE', 'OBS_QUOTA'))
                    if need[i] and have[i] + need[i] > rooms[i]]
            if full:
                L[SEQ] = mb[SEQ] + 1
                L[ROOM_SEQ] = L[SEQ]
                ev.append({'NOTICE_QUOTA': 'P_ROOM_NOTICE', 'ALARM_RESERVE': 'P_ROOM_ALARM',
                           'OBS_QUOTA': 'P_ROOM_OBS'}[full[0]])
                if kind == 'O' and full == ['OBS_QUOTA']:
                    ev.append('P_ALARM_REFUSED_OBS_ONLY')
                return tuple(L), ('Q', full[0]), ev
        if kind == 'C':
            return self.dl6_statement(rt, mb, L, gh, mid, m, ev)
        if 'EQ6_off' in mut and kind == 'N' and m[5] == 'H':
            L[PENDING] = mid                     # mutant: the write is a separate step (E-Q-6 removed)
            return tuple(L), ('W',), ev
        return self.dl5_write(mb, L, mid, m, ev, link)

    def room_need(self, kind, link):
        ix = 1 if self.c['INDEX_IN_OBS'] else 0
        if kind == 'N':
            return (0, 0, ix) if link else (1, 0, ix)
        if kind in ('O', 'E'):
            return (0, 1, ix)
        return (0, 0, 1 + ix)                    # COVERAGE: its body and its index entry

    def dl5_write(self, mb, L, mid, m, ev, link):
        """DL-5: link or store; I-E-2 for EPOCH_OPEN; evidence gap; index entry and new head."""
        mut = self.mut
        kind = m[0]
        ce_m, k_m, prev_m, ident = m[1], m[2], m[3], m[4]
        if kind == 'N' and m[5] == 'H' and m[6] not in mb[EVID] and 'DL4_held' not in mut:
            ev.append('V_SAF11')                 # SAF-11: object found held at DL-4 not held at write
        if kind == 'N' and m[5] == 'H':
            L[HCLAIM] = mb[HCLAIM] | {m[6]}
        if kind == 'E':
            if mb[CE] is not None and any(x[S_CE] == mb[CE] for x in mb[STMTS]):
                ev.append('P_OPEN_CLOSES_LIVE')
            if m[5] == 'LOST':
                ev.append('P_OPEN_LOST')
            L[CE] = ce_m
            L[COMMIT] = m[6]
            L[SEEN_CE] = mb[SEEN_CE] | {ce_m}
            L[OPEN_REASON] = m[5]
            L[DIG] = frozenset()
        rcpt = (ce_m, k_m, ident)
        linked = False
        if self.is_iid1(kind):
            first = self.held_rcpt(mb, ident)
            if first is not None and link:
                linked = True
                ans_rcpt = first
                if 'DL2_newreceipt' in mut:
                    ans_rcpt = rcpt
                if ans_rcpt != first:
                    ev.append('V_SAF6')
                ev.append('P_LINK')
                ans = ('R', ans_rcpt, (ce_m, k_m, ident))
            else:
                if first is not None:
                    ev.append('V_SAF6')          # a second copy kept (DL2_off)
                else:
                    L[HELD] = mb[HELD] | {(ident, rcpt)}
                    L[NHELD_EVER] = mb[NHELD_EVER] | {ident}
                ans = ('R', rcpt, None)
        else:
            ans = ('R', rcpt, None)
        L[SEQ] = mb[SEQ] + 1
        if kind == 'O':
            L[ALARM_SEQ] = L[SEQ]
            ev.append('P_ALARM_TAKEN')
            if mb[ROOM_SEQ] >= 0 and mb[CE] == ce_m and mb[ROOM_SEQ] > mb[OPEN_SEQ]:
                ev.append('P_ALARM_AFTER_ROOM_REFUSAL')
        if kind == 'E':
            L[OPEN_SEQ] = L[SEQ]
        if kind == 'N':
            e = m[6]
            if e is not None:
                L[NAMED] = mb[NAMED] | {e}
                if m[5] == 'X' and e not in mb[EVID]:
                    L[GAPS] = mb[GAPS] | {e}                                 # E-B-3
                    ev.append('P_GAP')
                if 'GAP_BY_NOTICE' in mut and m[5] == 'H' and e in mb[GAPS]:
                    L[GAPS] = L[GAPS] - {e}
                    ev.append('P_GAP_CLOSED')
        L[STORED] = mb[STORED] | {ident}
        L[HK] = k_m
        L[HA] = I(('A', prev_m, ident))
        if self.c['ROOMS'] is not None:
            need = self.room_need(kind, linked)
            L[ROOMS] = tuple(a + b for a, b in zip(mb[ROOMS], need))
        L[DIG] = L[DIG] | {(mid, ans)}
        return tuple(L), ans, ev

    # ------------------------------------------------------------------ 7.4
    def dl6_statement(self, rt, mb, L, gh, mid, m, ev):
        c = self.c
        mut = self.mut
        (_, ce_m, k_m, prev_m, ident, ref, tser, rk, at, head_at, N, headN, prev_ref, reveal, commit,
         carried, oldest_ref, called, evneed, obs_after, ok, stale) = m
        t = self.tok(mb, tser)
        fails = []
        # ST-1
        if t is None or t[T_B] != 0 or t[T_K] != 'K0' or (
                t[T_MEP] != mb[MEP] and 'ST1_epoch' not in mut and 'MEPOCH' not in mut):
            fails.append('ST1')
        effst = self.eff(rt, mb, t) if t is not None else None
        # ST-2
        if effst != 'I' and 'ST2' not in mut:
            fails.append('ST2')
        # ST-3
        if t is not None:
            a = self.age(rt, mb, t)
            if self.anomaly(rt, mb, t):
                ev.append('P_ANOMALY_AGE')
            if (a is None or a > c['L']) and 'ST3' not in mut:
                fails.append('ST3')
                ev.append('P_EXPIRED_STMT')
        # ST-4: genuine checkpoint bearing the token: always true here (not exercised)
        # ST-5: continuity of the chain epoch
        in_ce = [x for x in mb[STMTS] if x[S_CE] == mb[CE]]
        last_ref = in_ce[-1][S_REF] if in_ce else None
        if 'ST5' not in mut and (reveal != mb[COMMIT] or prev_ref != last_ref):
            fails.append('ST5')
            ev.append('P_ST5_FAIL')
        # ST-6: continuity of the budget: the anchor
        aN, ahead = mb[ANCHOR] if mb[ANCHOR] is not None else (0, None)
        if 'ST6' not in mut and not (at == aN and (aN == 0 or head_at == ahead)):
            fails.append('ST6')
            ev.append('P_ST6_FAIL')
        # ST-7
        st7 = True
        if not in_ce and rk != FZ and 'ST7_FZ' not in mut:
            st7 = False
        if not any(x[S_MEP] == mb[MEP] for x in mb[STMTS]) and rk not in (FZ, RF):
            st7 = False
        if rk in (FZ, RF) and carried != 0:
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
        if N < aN and 'ST6' not in mut:
            fails.append('ST8')
        # ST-9: the mailbox's own limits: always true
        if not fails:
            if (t is None or t[T_ST] != 'I' or rt - t[T_RT] > c['L'] or t[T_GMEP] != gh[G_GMEP]):
                ev.append('V_SAF1')
            for idn in self.chain_idents(prev_m):
                if idn not in mb[STORED]:
                    ev.append('V_SAF2')
                    break
            if not mb[HCLAIM] <= mb[EVID]:
                ev.append('V_SAF2')              # evidence a taken item says is HELD is not held
            if not ok or reveal != mb[COMMIT]:
                ev.append('V_SAF4')
            ga = mb[GANCHOR]
            if ga is None:
                if at != 0:
                    ev.append('V_SAF10')
            elif not (at == ga[0] and head_at == ga[1]):
                ev.append('V_SAF10')
            if rk == INC:
                okr = False
                for x in mb[STMTS]:
                    if x[S_REF] == oldest_ref:
                        tx = self.tok(mb, x[S_TOK])
                        if tx is not None and tx[T_GMEP] == gh[G_GMEP] and rt - tx[T_RT] <= c['R']:
                            okr = True
                if not okr:
                    ev.append('V_SAF3B_ACC')
            if stale:
                ev.append('P_STALECOPY_COUNTED')
            if mb[GAPS]:
                ev.append('P_STMT_ACCEPTED_WITH_GAP')
            L[TOKS] = tuple(x if x[T_SER] != tser else x[:T_ST] + ('U',) for x in mb[TOKS])
            L[SEQ] = mb[SEQ] + 1
            L[HK] = k_m
            L[HA] = I(('A', prev_m, ident))
            L[STORED] = mb[STORED] | {ident}
            L[COMMIT] = commit
            L[ANCHOR] = (N, headN)
            L[GANCHOR] = (N, headN)
            if c['ROOMS'] is not None:
                L[ROOMS] = tuple(a + b for a, b in zip(mb[ROOMS], self.room_need('C', False)))
            rec = (mid, ref, ce_m, mb[MEP], tser, N, headN, rk, carried, oldest_ref, L[SEQ], called,
                   evneed, obs_after, gh[G_GMEP], at, head_at)
            L[STMTS] = mb[STMTS] + (rec,)
            ans = ('R', (ce_m, k_m, ident), None)
            L[DIG] = mb[DIG] | {(mid, ans)}
            ev.append('ACCEPT')
            return tuple(L), ans, ev
        # refused: no position; token of this budget, ISSUED, own key -> SPENT; kept as evidence
        if t is not None and effst == 'I' and t[T_B] == 0 and t[T_K] == 'K0':
            L[TOKS] = tuple(x if x[T_SER] != tser else x[:T_ST] + ('S',) for x in mb[TOKS])
        L[SEQ] = mb[SEQ] + 1
        L[RSTMT_SEQ] = L[SEQ]
        ans = ('F', tuple(fails))
        L[DIG] = mb[DIG] | {(mid, ans)}
        if 'REFUSED_POS' in mut:
            L[HK] = k_m
            L[HA] = I(('A', prev_m, ident))
            ev.append('V_REFUSED_NOPOS')
        return tuple(L), ans, ev

    # ------------------------------------------------------------------ M-K-1: requests
    def request(self, rt, mb, gh, ev):
        """The courier's fresh, signed request naming the current mailbox epoch."""
        rid = gh[G_NREQ]
        gh = gh[:G_NREQ] + (rid + 1,)
        L, gh, ser = self.mk1_issue(rt, mb, gh, ev)
        L[REQS] = mb[REQS] | {rid}
        return tuple(L), gh, ser, I(('Q', rid, mb[MEP]))

    # ------------------------------------------------------------------ the courier
    def new_epoch_courier(self, gh, reason, keep=None):
        ce = gh[G_NEXTCE]
        A0 = I(('A0', ce))
        ident = I(('E', ce, reason, (ce, 1)))
        mid = I(('E', ce, 1, A0, ident, reason, (ce, 1)))
        A1 = I(('A', A0, ident))
        obs = (None,) * self.c['RUNS']
        lastref = meplast = None
        if keep is not None:
            meplast, obs = keep
        cr = (ce, I((A0, A1)), 1, lastref, meplast, obs, 0, None, (mid,), 0, frozenset(), None, True,
              False, frozenset(), False)
        gh = (ce + 1, True) + gh[2:]
        return cr, gh, mid

    def lost(self, ev):
        ev.append('P_COURIER_LOST')
        return None

    def courier_answer(self, cr, mid, ans, mb, ev):
        if cr is None:
            return cr
        out, pend, chain = cr[K_OUT], cr[K_PEND], U(cr[K_CHAIN])
        m = U(mid)
        typ = ans[0]
        if typ == 'R':
            if pend is not None and mid == pend[0]:
                return self.courier_accepted(cr, mb)
            k = m[2]
            out2 = tuple(x for x in out if x != mid)
            cr2 = list(cr)
            cr2[K_OUT] = out2
            cr2[K_RKMAX] = max(cr[K_RKMAX], k)
            if m[0] == 'E':
                cr2[K_EORCPT] = True
            cr2[K_MISSING] = cr[K_MISSING] - {mid}
            return tuple(cr2)
        if typ == 'F':
            if pend is not None and mid == pend[0]:
                if 'ST5' in ans[1]:
                    ev.append('P_LOST_ST5')
                    return self.lost(ev)                     # I-E-4
                out2 = tuple(x for x in out if x != mid)
                return cr[:K_PHASE] + (0, None, out2) + cr[K_OUT + 1:K_PEND] + (None,) + cr[K_PEND + 1:]
            return cr
        if typ == 'P':                                       # I-O-3 / I-O-4 / I-E-4
            hce, hk, hA = ans[1], ans[2], ans[3]
            if hce == cr[K_CE]:
                if cr[K_RKMAX] > hk:
                    ev.append('P_MAILBOX_ROLLBACK')
                    return self.lost(ev)
                if hk < len(chain) and chain[hk] == hA and hA is not None:
                    return cr
                if pend is not None and hk == len(chain) and hA == pend[4]:
                    return cr
                return self.lost(ev)
            if not cr[K_EORCPT]:
                return cr                                    # its own EPOCH_OPEN is not yet taken
            if hce is None and cr[K_RKMAX] >= 1:
                ev.append('P_MAILBOX_ROLLBACK')
            return self.lost(ev)
        if typ == 'M':
            cr2 = list(cr)
            cr2[K_MISSING] = cr[K_MISSING] | {mid}
            return tuple(cr2)
        if typ == 'Q':                                       # I-O-5
            if pend is not None and mid != pend[0]:
                smid = pend[0]
                sm = U(smid)
                ch = U(cr[K_CHAL][0]) if False else None
                tser = sm[6]
                reasons = ('NOTICE_REFUSED',) if m[0] == 'N' else ('MAILBOX_REFUSED',)
                aident = I(('O', tser)) if 'ALARM_NOTOKEN' not in self.mut else I(('O', reasons))
                amid = I(('O', sm[1], sm[2], sm[3], aident, reasons))
                out2 = tuple(x for x in out if x != smid) + (amid,)
                cr2 = list(cr)
                cr2[K_OUT] = out2
                cr2[K_PEND] = None
                cr2[K_PHASE] = 0
                cr2[K_CHAL] = None
                cr2[K_CHAIN] = I(chain + (I(('A', sm[3], aident)),))
                return tuple(cr2), amid
            return cr
        return cr

    def courier_accepted(self, cr, mb):
        mid, ref, N, headN, obs_after, A_after = cr[K_PEND][:6]
        chain = U(cr[K_CHAIN]) + (A_after,)
        meplast = cr[K_CHAL][3]
        k = len(chain) - 1
        return (cr[K_CE], I(chain), cr[K_J] + 1, ref, meplast, obs_after, 0, None, (), k, cr[K_SENT],
                None, cr[K_OK], cr[K_EORCPT], frozenset(), cr[K_STALE])

    def courier_read(self, s, rk, fail, evok):
        rt, mb, w, cr, bk, net, ctr, rd, gh = s
        c = self.c
        dec, l3 = w
        N = len(dec)
        stand = self.stand(w)
        tser, aN, ahead, cmep = cr[K_CHAL]
        ce, j = cr[K_CE], cr[K_J]
        chain = list(U(cr[K_CHAIN]))
        A = chain[-1]
        items = []
        ev = []
        reasons = []
        L = None
        sent = set(cr[K_SENT])
        obs = cr[K_OBS]
        existing = [r for r in range(c['RUNS']) if stand[r] is not None]
        at, head_at = aN, (self.whead(dec, aN) if aN <= N else None)
        if c['COURIER'] != 'nocheck':                     # O-2, O-3
            if aN > N:
                reasons.append('ROLLBACK')
                ev.append('P_ROLLBACK_ALARM')
            elif aN > 0 and self.whead(dec, aN) != ahead:
                reasons.append('FORK')
                ev.append('P_FORK_ALARM')
        else:
            if aN > N:
                at, head_at = N, self.whead(dec, N)
        carried = []
        read = set()
        if not reasons:
            if rk in (FZ, RF):
                read = set(existing)
            else:
                named = {rr for (rr, v) in dec[aN:N]}                 # O-R-1: since the anchor
                uns = set() if 'OR2' in self.mut else {r for r in existing if obs[r] is None
                                                       or obs[r][0] in ('u', 'f')}
                read = (named | uns) & set(existing)
            carried = [r for r in existing if r not in read]
            for r in sorted(read):
                st = stand[r]
                if st[2] and st[0] == 'x':
                    ev.append('P_L3_READ')
                if st[0] not in ('u', 'x', 'f'):
                    continue
                ident = self.ident_of(r, st)
                claim = e = None
                if st[0] == 'f':
                    e = self.evid_of(r, st)
                    if e in (L[EVID] if L else mb[EVID]):
                        claim = 'H'
                    elif evok.get(r, True):
                        claim = 'H'
                        if L is None:
                            L = list(mb)
                        L[EVID] = L[EVID] | {e}                       # POST /evidence (O-6 first)
                        if e in L[GAPS] and 'GAP_BY_NOTICE' not in self.mut:
                            L[GAPS] = L[GAPS] - {e}                   # E-B-3: closed by holding
                            ev.append('P_GAP_CLOSED')
                    else:
                        claim = 'X'
                        reasons.append('EVIDENCE_NOT_HELD')
                if ident in sent:                                     # I-O-7: once in a chain epoch
                    continue
                k = len(chain)
                mid = I(('N', ce, k, A, ident, claim, e))
                A = I(('A', A, ident))
                chain.append(A)
                items.append(mid)
                sent.add(ident)
        if fail:
            reasons.append('DEADLINE')
        mb2 = tuple(L) if L is not None else mb
        if reasons:                                                   # O-W-1: one alarm per reading
            rs = tuple(sorted(set(reasons)))
            aident = I(('O', tser)) if 'ALARM_NOTOKEN' not in self.mut else I(('O', rs))
            if not ('ALARM_NOTOKEN' in self.mut and aident in sent):   # mutant: once per epoch
                k = len(chain)
                mid = I(('O', ce, k, A, aident, rs))
                A = I(('A', A, aident))
                chain.append(A)
                items.append(mid)
                if 'ALARM_NOTOKEN' in self.mut:
                    sent.add(aident)
            cr2 = (ce, I(tuple(chain)), j, cr[K_LASTREF], cr[K_MEPLAST], obs, 0, None,
                   cr[K_OUT] + tuple(items), cr[K_RKMAX], frozenset(sent), None, cr[K_OK], cr[K_EORCPT],
                   cr[K_MISSING], cr[K_STALE])
            return mb2, cr2, net | set(items), ev
        ref = I(('ref', ce, j, tser))
        obs_after = tuple(((stand[r][0], stand[r][1], ref, j) if r in read else obs[r])
                          for r in range(c['RUNS']))
        oldest_ref = None
        if carried:
            oldest = min(carried, key=lambda r: obs[r][3])
            oldest_ref = obs[oldest][2]
        called = I(frozenset(self.ident_of(r, stand[r]) for r in existing if stand[r][0] in ('u', 'x', 'f')))
        evneed = I(frozenset(self.evid_of(r, stand[r]) for r in existing if stand[r][0] == 'f'))
        ident = I(('CS', ref))
        reveal = (ce, j) if cr[K_OK] else ('guess', ce, j)
        k = len(chain)
        headN = self.whead(dec, N)
        mid = I(('C', ce, k, A, ident, ref, tser, rk, at, head_at, N, headN, cr[K_LASTREF], reveal,
                 (ce, j + 1), len(carried), oldest_ref, called, evneed, obs_after, cr[K_OK], cr[K_STALE]))
        A_after = I(('A', A, ident))
        items.append(mid)
        pend = (mid, ref, N, headN, obs_after, A_after)
        cr2 = (ce, I(tuple(chain)), j, cr[K_LASTREF], cr[K_MEPLAST], obs, 2, cr[K_CHAL],
               cr[K_OUT] + tuple(items), cr[K_RKMAX], frozenset(sent), pend, cr[K_OK], cr[K_EORCPT],
               cr[K_MISSING], cr[K_STALE])
        return mb2, cr2, net | set(items), ev

    # ------------------------------------------------------------------ successors
    def succ(self, s):
        c = self.c
        mut = self.mut
        rt, mb, w, cr, bk, net, ctr, rd, gh = s
        res = []

        def S(rt_=rt, mb_=mb, w_=w, cr_=cr, bk_=bk, net_=net, ctr_=ctr, rd_=rd, gh_=gh):
            return (rt_, mb_, w_, cr_, bk_, net_, ctr_, rd_, gh_)

        def inc(i, ct=None):
            ct = ctr if ct is None else ct
            return ct[:i] + (ct[i] + 1,) + ct[i + 1:]

        def setmb(**kw):
            L = list(mb)
            for k_, v_ in kw.items():
                L[globals()[k_]] = v_
            return tuple(L)

        pending = mb[PENDING]
        # --- mutant EQ6_off: the pending write completes (other moves may come between)
        if pending is not None:
            m = U(pending)
            L = list(mb)
            L[PENDING] = None
            link = self.held_rcpt(mb, m[4]) is not None and 'DL2_off' not in mut
            mb2, ans, ev = self.dl5_write(mb, L, pending, m, [], link)
            res.append(('mailbox_completes_write ' + self.desc(pending), S(mb_=self.normalise(mb2)), tuple(ev)))
        # --- time
        if rt < c['TMAX']:
            res.append(('tick', S(rt_=rt + 1, mb_=setmb(BT=mb[BT] + 1, MONO=mb[MONO] + 1)), ()))
            if ctr[C_SUSP] < c['SUSPENDS']:
                res.append(('suspend(boottime+1,monotonic+0)', S(rt_=rt + 1, mb_=setmb(BT=mb[BT] + 1),
                                                                ctr_=inc(C_SUSP)), ()))
        if ctr[C_WALL] < c['WALL_MOVES']:
            for d in (-1, 1):
                if -1 <= mb[WOFF] + d <= 1:
                    res.append(('wall_clock_%s' % ('back' if d < 0 else 'forward'),
                                S(mb_=setmb(WOFF=mb[WOFF] + d), ctr_=inc(C_WALL)), ()))
        # --- restart / reboot
        if pending is None:
            for kind, ci, lim in (('reboot', C_REBOOT, c['REBOOTS']), ('restart', C_RESTART, c['RESTARTS'])):
                if ctr[ci] < lim:
                    L = list(mb)
                    if 'MEPOCH' not in mut:
                        L[MEP] = mb[MEP] + 1
                        L[REQS] = frozenset()
                    if kind == 'reboot':
                        L[BT] = 0
                        L[MONO] = 0
                    if 'MEPOCH' not in mut and 'MK5' not in mut:
                        L[TOKS] = tuple(t if t[T_ST] == 'V' else t[:T_ST] + ('V',) for t in mb[TOKS])
                    gh2 = gh[:G_GMEP] + (gh[G_GMEP] + 1,) + gh[G_GMEP + 1:]
                    res.append(('mailbox_' + kind, S(mb_=tuple(L), ctr_=inc(ci), gh_=gh2), ()))
        # --- courier loss / copy / restore
        if cr is not None and ctr[C_LOSS] < c['LOSSES']:
            res.append(('courier_loses_state', S(cr_=None, ctr_=inc(C_LOSS)), ()))
        if cr is not None and ctr[C_SNAP] < c['SNAPS'] and bk != cr:
            res.append(('courier_state_copied', S(bk_=cr, ctr_=inc(C_SNAP)), ()))
        if bk is not None and ctr[C_RESTORE] < c['RESTORES'] and bk != cr:
            n_acc = sum(1 for x in mb[STMTS] if x[S_CE] == bk[K_CE])
            stale = n_acc > bk[K_J] - 1
            bk2 = bk[:K_STALE] + (stale,)
            res.append(('courier_restored_from_old_copy%s' % (' (older than its last accepted statement)' if stale else ''),
                        S(cr_=bk2, ctr_=inc(C_RESTORE)), ('P_RESTORE',)))
        # --- witness (offered only while the courier holds a token it has not read with)
        dec, l3 = w
        wit_ok = cr is not None and cr[K_PHASE] == 1
        if wit_ok:
            stand = self.stand(w)
            if len(dec) < c['NMAX']:
                for r in range(c['RUNS']):
                    vals = ('f',) if (stand[r] is not None and stand[r][0] == 'f') else c['VALUES']
                    for v in vals:
                        res.append(('decision%d(run%d->%s)' % (len(dec) + 1, r, v),
                                    S(w_=(dec + ((r, v),), l3)), ()))
            for r in range(c['RUNS']):
                x = stand[r]
                if x is None:
                    continue
                if c['L3'] and x[0] == 'u':
                    for v in ('p', 'x'):
                        res.append(('stored_result_without_decision(run%d->%s)' % (r, v),
                                    S(w_=(dec, l3 | {(r, x[1], v)})), ()))
                if ctr[C_CARRY] < c['CARRY_BREAKS'] and x[0] in ('p', 'x') and not x[2]:
                    v = 'x' if x[0] == 'p' else 'p'
                    res.append(('CAP_OWNER_changes_settled_run%d->%s' % (r, v),
                                S(w_=(dec, l3 | {(r, x[1], v)}), ctr_=inc(C_CARRY)), ('P_CARRY_BREAK',)))
            if ctr[C_WTRUNC] < c['WTRUNC']:
                for p in range(len(dec)):
                    res.append(('witness_chain_cut_back_to_%d' % p,
                                S(w_=(dec[:p], frozenset(x for x in l3 if x[1] <= p)), ctr_=inc(C_WTRUNC)),
                                ('P_WITNESS_TRUNC',)))
        # --- evidence orphan removal (E-Q-5; serialised by E-Q-6, so not during a write, except mutant)
        if c['ORPHAN']:
            for e in sorted(mb[EVID] - mb[NAMED]):
                evs = ('P_ORPHAN', 'P_PENDING_ORPHAN') if pending is not None else ('P_ORPHAN',)
                res.append(('evidence_orphan_removed(%s)' % (U(e),), S(mb_=setmb(EVID=mb[EVID] - {e})), evs))
        # --- loss of the mailbox's record of the budget
        if ctr[C_WIPE] < c['WIPES'] and pending is None:
            L = list(mb)
            self.wipe_fields(L)
            L[TOKS] = ()
            L[NHELD_EVER] = mb[NHELD_EVER]
            res.append(('mailbox_loses_record_of_budget', S(mb_=tuple(L), ctr_=inc(C_WIPE)), ('P_WIPE', 'WIPE')))
        if pending is not None:
            return res + self.reader_moves(s, S)   # E-Q-6 removed: only the above may interleave
        # --- adversary delivers any message ever sent; replays requests (bounded)
        for mid in net:
            m = U(mid)
            if m[0] == 'Q':                                   # M-K-1: a replayed request
                if ctr[C_REQ] >= c['REQ_REPLAYS']:
                    continue
                ev = []
                if 'REQ_REPLAY' in mut:
                    L, gh2, ser = self.mk1_issue(rt, mb, gh, ev)
                    ev.append('V_PMK1')
                    res.append(('adversary_replays %s -> token%d issued' % (self.desc(mid), ser),
                                S(mb_=tuple(L), gh_=gh2, ctr_=inc(C_REQ)), tuple(ev)))
                elif m[2] != mb[MEP]:
                    res.append(('adversary_replays %s -> 409 EPOCH' % self.desc(mid), S(ctr_=inc(C_REQ)), ()))
                else:
                    res.append(('adversary_replays %s -> 409 REPLAY' % self.desc(mid), S(ctr_=inc(C_REQ)),
                                ('P_REQ_REPLAY_REFUSED',)))
                continue
            mb2, ans, ev = self.deliver(rt, mb, gh, mid)
            if mb2 == mb and not [e for e in ev if e != 'DL2HIT']:
                continue
            res.append(('adversary_delivers ' + self.desc(mid) + ' -> ' + self.ansdesc(ans), S(mb_=mb2), ev))
        # --- courier
        if cr is None:
            if gh[G_NEXTCE] <= c['EMAX'] or (c['COURIER'] == 'resume' and gh[G_EVER]):
                reason = 'LOST' if gh[G_EVER] else 'FIRST'
                if c['COURIER'] == 'resume' and gh[G_EVER] and mb[CE] is not None:
                    last = [x for x in mb[STMTS] if x[S_CE] == mb[CE]]
                    chain = tuple([None] * mb[HK] + [mb[HA]])
                    if last:
                        lx = last[-1]
                        lref, mepl, obs, jn = lx[S_REF], lx[S_MEP], lx[S_OBS], U(lx[S_REF])[2] + 1
                    else:
                        lref = mepl = None
                        obs = (None,) * c['RUNS']
                        jn = 1
                    cr2 = (mb[CE], I(chain), jn, lref, mepl, obs, 0, None, (), mb[HK], frozenset(), None,
                           False, True, frozenset(), False)
                    res.append(('courier_resumes_from_mailbox_head', S(cr_=cr2), ()))
                elif gh[G_NEXTCE] <= c['EMAX']:
                    keep = None
                    if c['COURIER'] == 'oldcursor' and gh[G_EVER] and mb[STMTS]:
                        lx = mb[STMTS][-1]
                        keep = (lx[S_MEP], lx[S_OBS])
                    cr2, gh2, mid = self.new_epoch_courier(gh, reason, keep)
                    res.append(('courier_opens_epoch(%s) ' % reason + self.desc(mid),
                                S(cr_=cr2, gh_=gh2, net_=net | {mid}), ()))
        else:
            phase = cr[K_PHASE]
            if (phase == 0 and cr[K_PEND] is None and cr[K_EORCPT] and ctr[C_READS] < c['MAX_READS']):
                res.extend(self.courier_take_challenge(s, S, inc))
            if phase == 1 and ctr[C_READS] < c['MAX_READS']:
                stand = self.stand(w)
                tser, aN, ahead, cmep = cr[K_CHAL]
                oldc = (c['COURIER'] == 'oldcursor' and any(o is not None for o in cr[K_OBS]))
                if cr[K_LASTREF] is None and not oldc:
                    kinds = [FZ]
                elif cmep != cr[K_MEPLAST]:
                    kinds = [RF]
                else:
                    kinds = [RF] + ([INC] if c['INCREMENTAL'] else [])
                existing = [r for r in range(c['RUNS']) if stand[r] is not None]
                for rk in kinds:
                    if rk == INC:
                        named = {rr for (rr, v) in dec[aN:len(dec)]}
                        uns = set() if 'OR2' in mut else {r for r in existing if cr[K_OBS][r] is None
                                                         or cr[K_OBS][r][0] in ('u', 'f')}
                        if not [r for r in existing if r not in (named | uns)]:
                            continue
                        readset = (named | uns) & set(existing)
                    else:
                        readset = set(existing)
                    fr = [r for r in sorted(readset) if stand[r][0] == 'f'
                          and self.evid_of(r, stand[r]) not in mb[EVID]]
                    evchoices = [{}]
                    if c['EV_FAIL'] and fr:
                        evchoices = [{r: not ((b >> i) & 1) for i, r in enumerate(fr)} for b in range(1 << len(fr))]
                    for fail in ((False, True) if c['READ_FAIL'] else (False,)):
                        for evok in evchoices:
                            mb2, cr2, net2, ev = self.courier_read(s, rk, fail, evok)
                            lab = 'courier_reads(%s,N%d%s%s)' % (rk, len(dec), ',DEADLINE' if fail else '',
                                  ''.join(',evidence_run%d_%s' % (r, 'stored' if o else 'REFUSED')
                                          for r, o in sorted(evok.items())))
                            res.append((lab, S(mb_=mb2, cr_=cr2, net_=net2, ctr_=inc(C_READS)), tuple(ev)))
            for mid in cr[K_OUT]:
                mb2, ans, ev0 = self.deliver(rt, mb, gh, mid)
                ev = list(ev0)
                r = self.courier_answer(cr, mid, ans, mb2, ev)
                net2 = net
                if isinstance(r, tuple) and len(r) == 2 and isinstance(r[1], int):
                    cr2, amid = r
                    net2 = net | {amid}
                else:
                    cr2 = r
                res.append(('courier_delivers ' + self.desc(mid) + ' -> ' + self.ansdesc(ans),
                            S(mb_=mb2, cr_=cr2, net_=net2), tuple(ev)))
            # I-O-6: 409 EVIDENCE_MISSING: store again from its own copy, or make the notice NOT_HELD
            for mid in sorted(cr[K_MISSING]):
                m = U(mid)
                e = m[6]
                L = list(mb)
                L[EVID] = mb[EVID] | {e}
                evs = ()
                if e in mb[GAPS] and 'GAP_BY_NOTICE' not in mut:
                    L[GAPS] = mb[GAPS] - {e}
                    evs = ('P_GAP_CLOSED',)
                cr2 = list(cr)
                cr2[K_MISSING] = cr[K_MISSING] - {mid}
                res.append(('courier_stores_evidence_again(%s)' % (U(e),), S(mb_=tuple(L), cr_=tuple(cr2)), evs))
                if c['EV_FAIL']:
                    nmid = I(('N', m[1], m[2], m[3], m[4], 'X', e))
                    cr3 = list(cr)
                    cr3[K_MISSING] = cr[K_MISSING] - {mid}
                    cr3[K_OUT] = tuple(nmid if x == mid else x for x in cr[K_OUT])
                    res.append(('courier_evidence_refused_remakes_notice_NOT_HELD', S(cr_=tuple(cr3), net_=net | {nmid}),
                                ('P_NOTHELD_REMADE',)))
        res.extend(self.reader_moves(s, S))
        return res

    def courier_take_challenge(self, s, S, inc):
        """O-1 and 5.6: a fresh signed request; the courier checks the challenge and its position."""
        rt, mb, w, cr, bk, net, ctr, rd, gh = s
        ev = []
        mb2, gh2, ser, qmid = self.request(rt, mb, gh, ev)
        anchor = mb[ANCHOR] if mb[ANCHOR] is not None else (0, None)
        chal = (ser, anchor[0], anchor[1], mb[MEP])
        chain = U(cr[K_CHAIN])
        hce, hk, hA = mb[CE], mb[HK], mb[HA]
        lab = 'courier_takes_challenge->token%d' % ser
        net2 = net | {qmid}
        if hce == cr[K_CE]:
            if cr[K_RKMAX] > hk:
                return [self.rollback_path(s, S, inc, mb2, gh2, ser, net2, lab, ev)]
            if hk < len(chain) and chain[hk] == hA:
                cr2 = cr[:K_PHASE] + (1, chal) + cr[K_CHAL + 1:]
                return [(lab, S(mb_=mb2, gh_=gh2, cr_=cr2, net_=net2), tuple(ev))]
            return [(lab + ' -> head not of its chain: state lost', S(mb_=mb2, gh_=gh2, cr_=None, net_=net2),
                     tuple(ev) + ('P_COURIER_LOST',))]
        if hce is None and cr[K_RKMAX] >= 1:
            return [self.rollback_path(s, S, inc, mb2, gh2, ser, net2, lab, ev)]
        return [(lab + ' -> head of another epoch: state lost', S(mb_=mb2, gh_=gh2, cr_=None, net_=net2),
                 tuple(ev) + ('P_COURIER_LOST',))]

    def rollback_path(self, s, S, inc, mb2, gh2, ser, net2, lab, ev):
        """I-O-4: reading not whole (MAILBOX_ROLLBACK); a new chain epoch; everything again."""
        rt, mb, w, cr, bk, net, ctr, rd, gh = s
        if gh2[G_NEXTCE] > self.c['EMAX']:
            return (lab + ' -> mailbox behind its receipts (no epoch left)', S(mb_=mb2, gh_=gh2, cr_=None, net_=net2),
                    tuple(ev) + ('P_MAILBOX_ROLLBACK',))
        cr2, gh3, emid = self.new_epoch_courier(gh2, 'LOST')
        chain = list(U(cr2[K_CHAIN]))
        aident = I(('O', ser)) if 'ALARM_NOTOKEN' not in self.mut else I(('O', ('MAILBOX_ROLLBACK',)))
        amid = I(('O', cr2[K_CE], 2, chain[-1], aident, ('MAILBOX_ROLLBACK',)))
        chain.append(I(('A', chain[-1], aident)))
        cr2 = cr2[:K_CHAIN] + (I(tuple(chain)),) + cr2[K_CHAIN + 1:K_OUT] + ((emid, amid),) + cr2[K_OUT + 1:]
        return (lab + ' -> mailbox behind its receipts: new epoch', S(mb_=mb2, gh_=gh3, cr_=cr2, net_=net2 | {emid, amid},
                ctr_=inc(C_READS)), tuple(ev) + ('P_MAILBOX_ROLLBACK',))

    def reader_moves(self, s, S):
        rt, mb, w, cr, bk, net, ctr, rd, gh = s
        res = []
        if rd is None:
            return res
        c = self.c
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
            if x[0] == q or 'CS2_nonce' in self.mut:
                res.append(('reader_takes_status(nonce%d,%s,#%d)' % (x[0], 'COVERED' if x[1] else 'NOT', x[2]),
                            S(rd_=(q, asked_at, sts, nstat, x)), ()))
            else:
                res.append(('reader_rejects_status(nonce%d)#%d' % (x[0], x[2]), s, ('P_STALE_STATUS_REJECTED',)))
        return res

    # ------------------------------------------------------------------ state properties
    def state_checks(self, s):
        rt, mb, w, cr, bk, net, ctr, rd, gh = s
        key = (rt, mb, gh[G_GMEP], ctr[C_REBOOT] >= 1, ctr[C_RESTART] >= 1, rd)
        r = self._scache.get(key)
        if r is None:
            r = self.state_checks_raw(s)
            if len(self._scache) > 1500000:
                self._scache.clear()
            self._scache[key] = r
        return r

    def state_checks_raw(self, s):
        c = self.c
        rt, mb, w, cr, bk, net, ctr, rd, gh = s
        out = []
        S = self.c1_covered(rt, mb)
        if S is not None:
            out.append('P_COVERED')
            t = self.tok(mb, S[S_TOK])
            if not (rt - t[T_RT] <= c['L'] and t[T_GMEP] == gh[G_GMEP]):
                out.append('V_SAF3')
            if not (S[S_SEQ] > mb[OPEN_SEQ] and any(
                    x[S_RK] == FZ and mb[OPEN_SEQ] < x[S_SEQ] <= S[S_SEQ] and x[S_CE] == mb[CE] for x in mb[STMTS])):
                out.append('V_SAF5')
            fresh_true = (S[S_CARR] == 0) or self.oldest_fresh(rt, mb, S, mailbox_time=False)
            if (mb[GAPS] or mb[ALARM_SEQ] > S[S_SEQ] or mb[RSTMT_SEQ] > S[S_SEQ] or mb[ROOM_SEQ] > S[S_SEQ]
                    or not fresh_true):
                out.append('V_SAF7')
            held = {e[0] for e in mb[HELD]}
            if not U(S[S_CALLED]) <= held:
                out.append('V_CENT_N')
            if not U(S[S_EVNEED]) <= mb[EVID]:
                out.append('V_CENT_E')
            if not fresh_true:
                out.append('V_R_AT_STATUS')
            # 8.2 reasons, computed on their own: STATEMENT_REFUSED, NOTICES/ITEMS_REFUSED, STALE_CARRY,
            # EVIDENCE_GAP, OBSERVATION_INCOMPLETE, EXPIRED, EPOCH_OPENED, MAILBOX_RESTARTED
            reasons82 = (mb[RSTMT_SEQ] > S[S_SEQ] or mb[ROOM_SEQ] > S[S_SEQ] or mb[GAPS]
                         or mb[ALARM_SEQ] > S[S_SEQ] or self.eff(rt, mb, t) != 'U'
                         or (S[S_CARR] > 0 and not self.oldest_fresh(rt, mb, S, True))
                         or not any(x[S_RK] == FZ and x[S_CE] == mb[CE] for x in mb[STMTS])
                         or S[S_MEP] != mb[MEP])
            if reasons82:
                out.append('V_C1_VS_82')
            if S[S_RK] == INC and S[S_CARR] >= 1:
                out.append('P_COVERED_INC')
            if mb[OPEN_REASON] == 'LOST':
                out.append('P_COVERED_AFTER_LOST')
            if ctr[C_REBOOT] >= 1:
                out.append('P_COVERED_AFTER_REBOOT')
            if ctr[C_RESTART] >= 1:
                out.append('P_COVERED_AFTER_RESTART')
            if S[S_RK] == RF and mb[MEP] > 0:
                out.append('P_COVERED_REFRESH_NEWMEP')
        else:
            if mb[CE] is not None:
                lst = [x for x in mb[STMTS] if x[S_CE] == mb[CE] and x[S_MEP] == mb[MEP]]
                if lst:
                    S2 = lst[-1]
                    t = self.tok(mb, S2[S_TOK])
                    if t is not None and self.eff(rt, mb, t) == 'U' and not mb[GAPS]:
                        if mb[ALARM_SEQ] > S2[S_SEQ]:
                            out.append('P_NOTCOV_BY_ALARM')
                        if mb[RSTMT_SEQ] > S2[S_SEQ]:
                            out.append('P_NOTCOV_BY_REFUSED_STMT')
                        if S2[S_CARR] > 0 and not self.oldest_fresh(rt, mb, S2, True):
                            out.append('P_NOTCOV_STALE_CARRY')
        if rd is not None:
            q, asked_at, sts, nstat, belief = rd
            if belief is not None:
                if belief[2] < asked_at or belief[0] != q:
                    out.append('V_SAF8')
                if belief[1]:
                    out.append('P_READER_COVERED')
        return out


# ============================================================================== search
def bfs(model, max_states):
    init = model.init()
    seen = {hash(init): (None, None)}
    first = {}
    frontier = deque([(init, 0)])
    for p in model.state_checks(init):
        first.setdefault(p, (hash(init), None, 0))
    transitions = 0
    complete = True
    maxdepth = 0
    while frontier:
        s, d = frontier.popleft()
        hs = hash(s)
        maxdepth = max(maxdepth, d)
        for label, t, evs in model.succ(s):
            transitions += 1
            if 'WIPE' not in evs and not (s[1][NHELD_EVER] <= t[1][NHELD_EVER]
                                          and {e[0] for e in s[1][HELD]} <= {e[0] for e in t[1][HELD]}):
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
    return dict(seen=seen, first=first, states=len(seen), transitions=transitions, complete=complete,
                maxdepth=maxdepth, init=init)


def trace_to(model, r, key):
    seen = r['seen']
    hs, label, depth = r['first'][key]
    labels = [label] if label is not None else []
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
    import configs, hashlib
    cfg = configs.CONFIGS[args.config]
    decl_bytes = open(args.declared, 'rb').read()
    decl = json.loads(decl_bytes)
    model = Model(cfg)
    t0 = time.time()
    r = bfs(model, model.c['MAX_STATES'])
    wall = time.time() - t0
    props = {}
    for p in ALL_PROPS:
        if p == 'SAF8' and not model.c['READER']:
            props[p] = dict(observed='n/a')
            continue
        k = 'V_' + p
        if k in r['first']:
            tr = trace_to(model, r, k)
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
        v['declared'] = decl['properties'].get(p, 'undeclared')
        v['agree'] = v['declared'] == v['observed']
        if not v['agree']:
            mism.append(p)
    for p, v in probes.items():
        v['declared'] = decl['probes'].get(p, 'any')
        v['agree'] = v['declared'] in ('any', v['observed'])
        if not v['agree']:
            mism.append(p)
    pc = {k: (list(v) if isinstance(v, tuple) else v) for k, v in model.c.items()}
    res = dict(config=args.config, bounds=pc, declared_file=args.declared,
               declared_sha256=hashlib.sha256(decl_bytes).hexdigest(), states=r['states'],
               transitions=r['transitions'], max_depth=r['maxdepth'], complete=r['complete'],
               result='COMPLETE' if r['complete'] else 'INCOMPLETE (state cap hit)', wall_seconds=round(wall, 1),
               key='64-bit Python hash of the state tuple', properties=props, probes=probes, mismatches=mism,
               verdict_agrees_with_declaration=not mism)
    json.dump(res, open(args.out, 'w'), indent=1)
    print('config %s: states=%d transitions=%d depth=%d complete=%s secs=%.1f' % (
        args.config, r['states'], r['transitions'], r['maxdepth'], r['complete'], wall))
    for p, v in props.items():
        print('  %-14s declared=%-10s observed=%-10s %s%s' % (p, v['declared'], v['observed'],
              '' if v['agree'] else 'MISMATCH ', ('depth %d' % v['depth']) if 'depth' in v else ''))
    for p, v in probes.items():
        if v['declared'] != 'any' or v['observed'] == 'reached':
            print('  %-28s declared=%-12s observed=%-12s %s' % (p, v['declared'], v['observed'],
                  '' if v['agree'] else 'MISMATCH'))
    for p, v in props.items():
        if v.get('observed') == 'violated':
            print('  shortest trace for %s:' % p)
            for i, l in enumerate(v['trace']):
                print('     %2d. %s' % (i + 1, l))
    print('  verdict agrees with declaration: %s' % (not mism))


if __name__ == '__main__':
    main()
