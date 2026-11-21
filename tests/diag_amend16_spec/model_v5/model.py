#!/usr/bin/env python3
"""
Separately authored bounded model of "Amendment 16 ... Step 3", VERSION 5 (final text;
SPEC_v5_as_sent_to_review.md, SHA-256 e9f7f4b8...), sections 5 to 8, properties of section 9.

Internal, separately authored verification. NOT independent validation; not a proof for unbounded
parameters; says nothing about any implementation. Round 3 (G/model2 and G/model3 left unchanged).

Changes from model3 (version 2): a refused item takes no position and is signed again at the next one
(I-3, I-O-5, I-O-6); the courier sends one item at a time and a statement only when its items are
acknowledged (I-S-1); four rooms with ALARMS_KEEP and INDEX_RESERVE (E-Q-2, E-Q-3a, E-Q-4); binding and
evidence gaps as a state (E-2, E-Q-5, E-B-3) with the challenge listing gaps and the courier storing them
again (O-1, I-O-7); only notices about runs kept in the outbox (I-O-1, I-O-5); EPOCH_OPEN names the epoch it
closes (I-E-1..I-E-4, DL-3, EPOCH_STALE), reason MAILBOX_STATE_LOST; the courier's own anchor (I-O-4,
SAF-10, L-10).  Section 3 and K-N-3 are not modelled.
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
    WTRUNC=0, ROOMS=None, ALARMS_KEEP=1, RETIRE=False, READER=False, QMAX=2, NSTAT_MAX=3,
    COURIER='honest',            # honest | resume | oldcursor | nocheck
    KEEP_OWN_ANCHOR_ON_LOSS=True,  # reading: a courier told by the head that it lost state keeps its own anchor
    MUTANTS=(), MAX_STATES=6_000_000,
)
# ROOMS = (NOTICE_QUOTA, ALARM_RESERVE, OBS_QUOTA, INDEX_QUOTA, INDEX_RESERVE), in items

(C_REBOOT, C_RESTART, C_WALL, C_SUSP, C_LOSS, C_SNAP, C_RESTORE, C_REQ, C_CARRY, C_WIPE, C_READS,
 C_WTRUNC, C_OPENS) = range(13)
NCTR = 13

(MEP, BT, MONO, WOFF, TOKS, CE, HK, HA, COMMIT, ANCHOR, HELD, STORED, DIG, STMTS, GAPSEV, EVID, NAMED,
 SEEN_CE, ALARM_SEQ, RSTMT_SEQ, ROOM_SEQ, OPEN_SEQ, SEQ, ROOMS, OPEN_REASON, REQS, PENDING, GANCHOR,
 NHELD_EVER, HCLAIM, NAMED_H, RETIRED) = range(32)
NMB = 32

T_SER, T_B, T_K, T_MEP, T_GMEP, T_BT, T_WALL, T_MONO, T_RT, T_ST = range(10)
(S_MID, S_REF, S_CE, S_MEP, S_TOK, S_N, S_HEADN, S_RK, S_CARR, S_OLDEST, S_SEQ, S_CALLED, S_EVNEED,
 S_OBS, S_GMEP, S_AT, S_HEADAT) = range(17)
# courier
(K_CE, K_CHAIN, K_J, K_LASTREF, K_MEPLAST, K_OBS, K_PHASE, K_CHAL, K_QUEUE, K_INFL, K_INFLOG, K_RKMAX,
 K_SENT, K_REFN, K_RD, K_OK, K_STALE, K_OWNA, K_REASON, K_MISS, K_GOWNA) = range(21)
G_NEXTCE, G_EVER, G_GMEP, G_SERIAL, G_NREQ = range(5)
# phases: 0 idle (no token); 1 token held, not read; 2 working the queue

STATE_PROPS = ['SAF3', 'SAF5', 'SAF7', 'SAF8', 'CENT_N', 'CENT_E', 'R_AT_STATUS', 'C1_VS_82']
TRANS_PROPS = ['SAF1', 'SAF2', 'SAF4', 'SAF6', 'SAF10', 'SAF10_L10', 'SAF11', 'SAF3B_ACC', 'PMK1',
               'DL2_SAME', 'REFUSED_NOPOS', 'ALARM_ROOM', 'INDEX_RESERVE']
ALL_PROPS = TRANS_PROPS + STATE_PROPS
PROBES = [
    'P_COVERED', 'P_COVERED_INC', 'P_COVERED_AFTER_LOST', 'P_COVERED_AFTER_MBLOST', 'P_COVERED_AFTER_REBOOT',
    'P_COVERED_AFTER_RESTART', 'P_COVERED_REFRESH_NEWMEP', 'P_LINK', 'P_DL2_FIRST_RECEIPT_STMT',
    'P_DL2_FIRST_REFUSAL', 'P_STMT_BEFORE_ITEMS', 'P_EPOCH_KNOWN', 'P_EPOCH_STALE', 'P_OPEN_LOST',
    'P_OPEN_MBLOST', 'P_OPEN_CLOSES_LIVE', 'P_COURIER_LOST', 'P_LOST_ST5', 'P_MAILBOX_ROLLBACK',
    'P_ROLLBACK_BY_ANCHOR', 'P_ROLLBACK_BY_RECEIPT', 'P_OWN_ANCHOR_FORK', 'P_RESTORE', 'P_STALECOPY_COUNTED',
    'P_FORK_ALARM', 'P_ROLLBACK_ALARM', 'P_ST6_FAIL', 'P_EVICT', 'P_EXPIRED_STMT', 'P_ANOMALY_AGE',
    'P_REQ_REPLAY_REFUSED', 'P_GAP', 'P_GAP_CLOSED', 'P_GAP_REBEGIN', 'P_ORPHAN', 'P_EVMISSING',
    'P_NOTHELD_REMADE', 'P_RESIGNED', 'P_ROOM_NOTICE', 'P_ROOM_ALARM', 'P_ROOM_OBS', 'P_ROOM_INDEX',
    'P_ALARM_AFTER_ROOM_REFUSAL', 'P_INDEX_RESERVE_USED', 'P_ALARM_BODY_DROPPED', 'P_RETIRE',
    'P_NOTCOV_BY_ALARM', 'P_NOTCOV_BY_REFUSED_STMT', 'P_NOTCOV_STALE_CARRY', 'P_L3_READ', 'P_ST7_FAIL',
    'P_READER_COVERED', 'P_STALE_STATUS_REJECTED', 'P_WIPE', 'P_CARRY_BREAK', 'P_PENDING_ORPHAN',
    'P_WITNESS_TRUNC', 'P_ALARM_TAKEN', 'P_ST5_FAIL', 'P_WIPE_THEN_COVERED',
]
ROOMNAMES = ('NOTICE_QUOTA', 'ALARM_RESERVE', 'OBS_QUOTA', 'INDEX_QUOTA')


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
        return (0, tuple(mb), w, self.no_epoch_courier('FIRST', None), None, frozenset(), (0,) * NCTR, rd, gh)

    def wipe_fields(self, mb):
        mb[CE] = None; mb[HK] = 0; mb[HA] = None; mb[COMMIT] = None; mb[ANCHOR] = None
        mb[HELD] = frozenset(); mb[STORED] = frozenset(); mb[DIG] = frozenset(); mb[STMTS] = ()
        mb[GAPSEV] = frozenset(); mb[EVID] = frozenset(); mb[NAMED] = frozenset(); mb[SEEN_CE] = frozenset()
        mb[ALARM_SEQ] = -1; mb[RSTMT_SEQ] = -1; mb[ROOM_SEQ] = -1; mb[OPEN_SEQ] = -1; mb[SEQ] = 0
        mb[ROOMS] = (0, 0, 0, 0, 0); mb[OPEN_REASON] = None; mb[REQS] = frozenset(); mb[PENDING] = None
        mb[HCLAIM] = frozenset(); mb[NAMED_H] = frozenset(); mb[RETIRED] = frozenset()

    def no_epoch_courier(self, reason, owna, gowna=None):
        return (None, None, 0, None, None, (None,) * self.c['RUNS'], 0, None, (), None, None, 0, frozenset(),
                frozenset(), None, True, False, owna, reason, None, gowna)

    # ------------------------------------------------------------------ evidence gaps (E-B-3)
    def gaps(self, mb):
        if 'GAP_NO_REBEGIN' in self.mut:
            return mb[GAPSEV]
        return mb[NAMED] - mb[EVID]          # a state: bound (not INLINE) and not held

    # ------------------------------------------------------------------ witness
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
                    cur = ('f', i, False, cur[3])
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
        return I(('N', r, 'f')) if st[0] == 'f' else I(('N', r, st[0], st[1]))

    @staticmethod
    def evid_of(r, st):
        return I(('ev', r, st[3]))

    # ------------------------------------------------------------------ time
    def age(self, rt, mb, tok):
        mut = self.mut
        if tok[T_MEP] != mb[MEP] and 'TICK_CROSS' not in mut and 'MEPOCH' not in mut:
            return None
        boot = (mb[MONO] - tok[T_MONO]) if 'MT1_mono' in mut else (mb[BT] - tok[T_BT])
        wall = (rt + mb[WOFF]) - tok[T_WALL]
        if 'MT5_wall' in mut:
            return wall
        if wall < 0 or wall != boot:
            return max(boot, wall)
        return boot

    def anomaly(self, rt, mb, tok):
        return tok[T_MEP] == mb[MEP] and ((rt + mb[WOFF]) - tok[T_WALL]) != (mb[BT] - tok[T_BT])

    def eff(self, rt, mb, tok):
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

    def mk1_issue(self, rt, mb, gh, ev):
        serial = gh[G_SERIAL]
        toks = list(mb[TOKS])
        issued = [i for i, t in enumerate(toks) if self.eff(rt, mb, t) == 'I']
        if len(issued) >= self.c['TOKENS_MAX']:
            i = min(issued, key=lambda i: toks[i][T_SER])
            toks[i] = toks[i][:T_ST] + ('V',)
            ev.append('P_EVICT')
        toks.append((serial, 0, 'K0', mb[MEP], gh[G_GMEP], mb[BT], rt + mb[WOFF], mb[MONO], rt, 'I'))
        L = list(mb)
        L[TOKS] = tuple(toks)
        return L, gh[:G_SERIAL] + (serial + 1,) + gh[G_SERIAL + 1:], serial

    # ------------------------------------------------------------------ C-1
    def c1_covered(self, rt, mb):
        mut = self.mut
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
        if self.gaps(mb) and 'C1_gap' not in mut:                    # C-1.3
            return None
        if mb[ALARM_SEQ] > S[S_SEQ] and 'C1_alarm' not in mut:       # C-1.4
            return None
        if mb[RSTMT_SEQ] > S[S_SEQ] and 'C15_off' not in mut:        # C-1.5
            return None
        if mb[ROOM_SEQ] > S[S_SEQ] and 'C16_off' not in mut:         # C-1.6
            return None
        if S[S_CARR] > 0 and 'C17_off' not in mut and not self.oldest_fresh(rt, mb, S, True):   # C-1.7
            return None
        return S

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
            return 'EPOCH_OPEN(ce%s,%s,closes=%s)#%d' % (m[1], m[5], m[7], mid)
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
                'K': lambda: '409 EPOCH_KNOWN', 'S': lambda: '409 EPOCH_STALE', 'M': lambda: '409 EVIDENCE_MISSING',
                'F': lambda: '422 ' + ','.join(ans[1]), 'Q': lambda: '507 ' + ans[1],
                'W': lambda: '(write pending)'}.get(t, lambda: str(ans))()

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
            L[ROOMS] = (0, 0, 0, 0, 0)
        return tuple(L)

    def is_iid1(self, kind):
        return kind == 'N' or (kind == 'O' and 'ALARM_NOTOKEN' in self.mut)

    def held_rcpt(self, mb, ident):
        for e in mb[HELD]:
            if e[0] == ident:
                return e[1]
        return None

    def dig_lookup(self, mb, mid):
        for (d, a) in mb[DIG]:
            if d == mid:
                return a
        return None

    # ------------------------------------------------------------------ rooms (E-Q-2, E-Q-3, E-Q-4)
    def room_check(self, mb, kind, link):
        """Returns (full room name or None, new ROOMS tuple if written, events)."""
        rooms = self.c['ROOMS']
        n, a, o, i, istmt = mb[ROOMS]
        ev = []
        if kind == 'N':
            new = (n + (0 if link else 1), a, o, i + 1, istmt)
        elif kind == 'O':
            keep = self.c['ALARMS_KEEP']
            if 'ALARM_STORE_FIRST' in self.mut:
                a2 = a + 1                               # mutant: store, then drop the oldest
            else:
                a2 = min(a, keep - 1) + 1                # E-Q-4: drop the oldest BEFORE storing
                if a2 <= a:
                    ev.append('P_ALARM_BODY_DROPPED')
            new = (n, a2, o, i + 1, istmt)
        elif kind == 'E':
            new = (n, a, o, i + 1, istmt)
        else:
            new = (n, a, o + 2, i + 1, istmt + 1)        # statement body and record; its index entry
        if rooms is None:
            return None, mb[ROOMS], ev
        NQ, AQ, OQ, IQ, IRES = rooms
        if new[0] > NQ:
            return 'NOTICE_QUOTA', None, ev
        if new[1] > AQ:
            if kind == 'O':
                ev.append('V_ALARM_ROOM')                # E-X-4: an alarm's body always has room
            return 'ALARM_RESERVE', None, ev
        if new[2] > OQ:
            return 'OBS_QUOTA', None, ev
        ilim = IQ if (kind in ('N', 'O', 'E') or 'NO_INDEX_RESERVE' in self.mut) else IQ - IRES
        if new[3] > ilim:
            if kind in ('N', 'O', 'E') and istmt > IQ - IRES:
                ev.append('V_INDEX_RESERVE')             # statements have eaten into the reserve
            return 'INDEX_QUOTA', None, ev
        if kind in ('N', 'O', 'E') and new[3] > IQ - IRES:
            ev.append('P_INDEX_RESERVE_USED')
        if kind == 'O' and 'ALARM_STORE_FIRST' in self.mut:
            new = (new[0], min(new[1], self.c['ALARMS_KEEP']), new[2], new[3], new[4])
        return None, new, ev

    # ------------------------------------------------------------------ the mailbox (7.3)
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
        mut = self.mut
        ev = []
        m = U(mid)
        kind = m[0]
        ce_m, k_m, prev_m, ident = m[1], m[2], m[3], m[4]
        late_dl2 = (kind == 'C' and 'DL2_AFTER_DL3' in mut)
        # DL-2
        if ce_m == mb[CE] and not late_dl2:
            a = self.dig_lookup(mb, mid)
            if a is not None:
                ev.append('DL2HIT')
                if kind == 'C':
                    ev.append('P_DL2_FIRST_RECEIPT_STMT' if a[0] == 'R' else 'P_DL2_FIRST_REFUSAL')
                return mb, a, ev
        L = list(mb)
        # DL-3
        if kind == 'E':
            if ce_m in mb[SEEN_CE] and 'OPEN_KNOWN' not in mut:
                ev.append('P_EPOCH_KNOWN')
                return mb, ('K',), ev
            if m[7] != mb[CE] and 'CLOSES_off' not in mut:
                ev.append('P_EPOCH_STALE')
                return mb, ('S',), ev
            if not (k_m == 1 and prev_m == I(('A0', ce_m))):
                return mb, ('P', mb[CE], mb[HK], mb[HA]), ev
        else:
            pos_ok = (ce_m == mb[CE] and k_m == mb[HK] + 1 and prev_m == mb[HA])
            if not pos_ok and not (kind == 'C' and 'DL3_order' in mut and ce_m == mb[CE]):
                if late_dl2 and self.dig_lookup(mb, mid) is not None:
                    ev.append('V_DL2_SAME')
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
        # DL-4
        if kind == 'N' and m[5] == 'H' and m[6] not in mb[EVID] and 'DL4_held' not in mut:
            ev.append('P_EVMISSING')
            return mb, ('M',), ev
        link = self.is_iid1(kind) and self.held_rcpt(mb, ident) is not None and 'DL2_off' not in mut
        full, newrooms, rev = self.room_check(mb, kind, link)
        ev.extend(rev)
        if full is not None:
            L[SEQ] = mb[SEQ] + 1
            L[ROOM_SEQ] = L[SEQ]
            ev.append({'NOTICE_QUOTA': 'P_ROOM_NOTICE', 'ALARM_RESERVE': 'P_ROOM_ALARM',
                       'OBS_QUOTA': 'P_ROOM_OBS', 'INDEX_QUOTA': 'P_ROOM_INDEX'}[full])
            return tuple(L), ('Q', full), ev
        if kind == 'C':
            return self.dl6_statement(rt, mb, L, gh, mid, m, ev, newrooms)
        if 'EQ6_off' in mut and kind == 'N' and m[5] == 'H':
            L[PENDING] = mid
            return tuple(L), ('W',), ev
        L[ROOMS] = newrooms
        return self.dl5_write(mb, L, mid, m, ev, link)

    def dl5_write(self, mb, L, mid, m, ev, link):
        mut = self.mut
        kind = m[0]
        ce_m, k_m, prev_m, ident = m[1], m[2], m[3], m[4]
        if kind == 'N' and m[5] == 'H' and m[6] not in mb[EVID] and 'DL4_held' not in mut:
            ev.append('V_SAF11')
        if kind == 'N' and m[5] == 'H':
            L[HCLAIM] = mb[HCLAIM] | {m[6]}
        if kind == 'E':
            if mb[CE] is not None and any(x[S_CE] == mb[CE] for x in mb[STMTS]):
                ev.append('P_OPEN_CLOSES_LIVE')
            ev.append({'COURIER_STATE_LOST': 'P_OPEN_LOST', 'MAILBOX_STATE_LOST': 'P_OPEN_MBLOST'}.get(m[5], 'OPEN'))
            L[CE] = ce_m
            L[COMMIT] = m[6]
            L[SEEN_CE] = mb[SEEN_CE] | {ce_m}
            L[OPEN_REASON] = m[5]
            L[DIG] = frozenset()
        rcpt = (ce_m, k_m, ident)
        ans = ('R', rcpt, None)
        if self.is_iid1(kind):
            first = self.held_rcpt(mb, ident)
            if first is not None and link:
                ans_rcpt = (ce_m, k_m, ident) if 'DL2_newreceipt' in mut else first
                if ans_rcpt != first:
                    ev.append('V_SAF6')
                ev.append('P_LINK')
                ans = ('R', ans_rcpt, (ce_m, k_m, ident))
            elif first is not None:
                ev.append('V_SAF6')
            else:
                L[HELD] = mb[HELD] | {(ident, rcpt)}
                L[NHELD_EVER] = mb[NHELD_EVER] | {ident}
        L[SEQ] = mb[SEQ] + 1
        if kind == 'O':
            L[ALARM_SEQ] = L[SEQ]
            ev.append('P_ALARM_TAKEN')
            if mb[ROOM_SEQ] > mb[OPEN_SEQ] and mb[CE] == ce_m:
                ev.append('P_ALARM_AFTER_ROOM_REFUSAL')
        if kind == 'E':
            L[OPEN_SEQ] = L[SEQ]
        if kind == 'N' and m[6] is not None:
            e = m[6]
            L[NAMED] = mb[NAMED] | {e}                   # E-2: a notice binds its ids, whatever it says
            if m[5] == 'H':
                L[NAMED_H] = mb[NAMED_H] | {e}
            if e not in mb[EVID]:
                L[GAPSEV] = mb[GAPSEV] | {e}
                ev.append('P_GAP')
        L[STORED] = mb[STORED] | {ident}
        L[HK] = k_m
        L[HA] = I(('A', prev_m, ident))
        L[DIG] = L[DIG] | {(mid, ans)}
        return tuple(L), ans, ev

    def dl6_statement(self, rt, mb, L, gh, mid, m, ev, newrooms):
        c = self.c
        mut = self.mut
        (_, ce_m, k_m, prev_m, ident, ref, tser, rk, at, head_at, N, headN, prev_ref, reveal, commit,
         carried, oldest_ref, called, evneed, obs_after, ok, stale, owna, gwit) = m
        t = self.tok(mb, tser)
        fails = []
        if t is None or t[T_B] != 0 or t[T_K] != 'K0' or (
                t[T_MEP] != mb[MEP] and 'ST1_epoch' not in mut and 'MEPOCH' not in mut):
            fails.append('ST1')
        effst = self.eff(rt, mb, t) if t is not None else None
        if effst != 'I' and 'ST2' not in mut:
            fails.append('ST2')
        if t is not None:
            a = self.age(rt, mb, t)
            if self.anomaly(rt, mb, t):
                ev.append('P_ANOMALY_AGE')
            if (a is None or a > c['L']) and 'ST3' not in mut:
                fails.append('ST3')
                ev.append('P_EXPIRED_STMT')
        in_ce = [x for x in mb[STMTS] if x[S_CE] == mb[CE]]
        last_ref = in_ce[-1][S_REF] if in_ce else None
        if 'ST5' not in mut and (reveal != mb[COMMIT] or prev_ref != last_ref):
            fails.append('ST5')
            ev.append('P_ST5_FAIL')
        aN, ahead = mb[ANCHOR] if mb[ANCHOR] is not None else (0, None)
        if 'ST6' not in mut and not (at == aN and (aN == 0 or head_at == ahead)):
            fails.append('ST6')
            ev.append('P_ST6_FAIL')
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
        if N < aN and 'ST6' not in mut:
            fails.append('ST8')
        if not fails:
            if t is None or t[T_ST] != 'I' or rt - t[T_RT] > c['L'] or t[T_GMEP] != gh[G_GMEP]:
                ev.append('V_SAF1')
            for idn in self.chain_idents(prev_m):
                if idn not in mb[STORED]:
                    ev.append('V_SAF2')
                    break
            if not mb[HCLAIM] <= mb[EVID]:
                ev.append('V_SAF2')
            if not ok or reveal != mb[COMMIT]:
                ev.append('V_SAF4')
            # SAF-10, as worded in version 5, in three cases
            ga = mb[GANCHOR]
            if mb[ANCHOR] == ga:                                     # (a) the mailbox's record intact
                if ga is not None and not (at == ga[0] and head_at == ga[1]):
                    ev.append('V_SAF10')
                if ga is None and at != 0:
                    ev.append('V_SAF10')
            elif owna == ga:                                         # (b) record lost, own anchor intact
                if not gwit:
                    ev.append('V_SAF10')
            else:                                                    # (c) both lost: L-10, not claimed
                if not gwit:
                    ev.append('V_SAF10_L10')
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
            L[TOKS] = tuple(x if x[T_SER] != tser else x[:T_ST] + ('U',) for x in mb[TOKS])
            L[SEQ] = mb[SEQ] + 1
            L[HK] = k_m
            L[HA] = I(('A', prev_m, ident))
            L[STORED] = mb[STORED] | {ident}
            L[COMMIT] = commit
            L[ANCHOR] = (N, headN)
            L[GANCHOR] = (N, headN)
            L[ROOMS] = newrooms
            rec = (mid, ref, ce_m, mb[MEP], tser, N, headN, rk, carried, oldest_ref, L[SEQ], called,
                   evneed, obs_after, gh[G_GMEP], at, head_at)
            L[STMTS] = mb[STMTS] + (rec,)
            ans = ('R', (ce_m, k_m, ident), None)
            L[DIG] = mb[DIG] | {(mid, ans)}
            ev.append('ACCEPT')
            return tuple(L), ans, ev
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

    # ------------------------------------------------------------------ the courier
    def sign(self, cr, log):
        """I-3: sign a logical item for the position that is next now."""
        ce = cr[K_CE]
        chain = U(cr[K_CHAIN])
        k, A = len(chain), chain[-1]
        kind = log[0]
        if kind == 'E':
            return I(('E', ce, 1, chain[0], log[1], log[2], (ce, 1), log[3]))
        if kind == 'N':
            return I(('N', ce, k, A, log[1], log[2], log[3]))
        if kind == 'O':
            return I(('O', ce, k, A, log[1], log[2]))
        if kind == 'C':
            return I(('C', ce, k, A) + log[1:])
        raise ValueError(log)

    def advance(self, cr, net, ev):
        """Send the next item of the queue when nothing is in flight; resolve END (statement or alarm)."""
        while cr is not None and cr[K_INFL] is None and cr[K_QUEUE]:
            log = cr[K_QUEUE][0]
            rest = cr[K_QUEUE][1:]
            if log[0] == 'END':
                rdi = cr[K_RD]
                (tser, rk, at, head_at, N, headN, obs_after, carried, oldest_ref, called, evneed, reasons,
                 owna, gwit) = rdi
                if reasons:
                    aident = I(('O', tser)) if 'ALARM_NOTOKEN' not in self.mut else I(('O', tuple(sorted(reasons))))
                    if 'ALARM_NOTOKEN' in self.mut and aident in cr[K_SENT]:
                        cr = cr[:K_QUEUE] + (rest,) + cr[K_QUEUE + 1:]
                        continue
                    log = ('O', aident, tuple(sorted(set(reasons))))
                else:
                    ce, j = cr[K_CE], cr[K_J]
                    ref = I(('ref', ce, j, tser))
                    ident = I(('CS', ref))
                    reveal = (ce, j) if cr[K_OK] else ('guess', ce, j)
                    log = ('C', ident, ref, tser, rk, at, head_at, N, headN, cr[K_LASTREF], reveal, (ce, j + 1),
                           carried, oldest_ref, called, evneed, obs_after, cr[K_OK], cr[K_STALE], owna, gwit)
            mid = self.sign(cr, log)
            net = net | {mid}
            cr = cr[:K_QUEUE] + (rest, mid, log) + cr[K_INFLOG + 1:]
        return cr, net

    def own_anchor_now(self, cr):
        """I-O-4: the last own statement accepted, or sent and not refused."""
        lg = cr[K_INFLOG]
        if lg is not None and lg[0] == 'C':
            return (lg[7], lg[8])
        return cr[K_OWNA]

    def lost(self, cr, ev, reason='COURIER_STATE_LOST'):
        ev.append('P_COURIER_LOST' if reason == 'COURIER_STATE_LOST' else 'P_MAILBOX_ROLLBACK')
        keep = (reason == 'MAILBOX_STATE_LOST' or self.c['KEEP_OWN_ANCHOR_ON_LOSS'])
        return self.no_epoch_courier(reason, self.own_anchor_now(cr) if keep else None, self.gown_now(cr))

    def gown_now(self, cr):
        lg = cr[K_INFLOG]
        if lg is not None and lg[0] == 'C':
            return (lg[7], lg[8])
        return cr[K_GOWNA]

    def courier_answer(self, cr, mid, ans, mb, ev):
        mut = self.mut
        log = cr[K_INFLOG]
        if cr[K_INFL] != mid:
            return cr
        typ = ans[0]
        m = U(mid)
        chain = U(cr[K_CHAIN])

        def clear(c2):
            return c2[:K_INFL] + (None, None) + c2[K_INFLOG + 1:]
        if typ == 'W':
            return cr
        if typ == 'R':
            if log[0] == 'C':
                return self.courier_accepted(cr, mb, log)
            A = I(('A', m[3], m[4]))
            if log[0] == 'E':
                cr2 = list(clear(cr))
                cr2[K_CHAIN] = I((chain[0], A))
                cr2[K_RKMAX] = 1
                return tuple(cr2)
            cr2 = list(clear(cr))
            cr2[K_CHAIN] = I(chain + (A,))
            cr2[K_RKMAX] = m[2]
            if log[0] == 'N':
                cr2[K_SENT] = cr[K_SENT] | {log[1]}
                cr2[K_REFN] = cr[K_REFN] - {log}
            if log[0] == 'O' and 'ALARM_NOTOKEN' in mut:
                cr2[K_SENT] = cr[K_SENT] | {log[1]}
            return tuple(cr2)
        if typ in ('K', 'S'):                                 # EPOCH_KNOWN / EPOCH_STALE: make another
            if log[0] == 'E':
                ev.append('P_STALE_OPEN_REDONE')
                return self.no_epoch_courier(cr[K_REASON], cr[K_OWNA], cr[K_GOWNA])
            return cr
        if typ in ('F', 'Q'):
            if typ == 'F' and log[0] == 'C' and 'ST5' in ans[1]:
                ev.append('P_LOST_ST5')
                return self.lost(cr, ev)
            if log[0] == 'E':
                return self.no_epoch_courier(cr[K_REASON], cr[K_OWNA], cr[K_GOWNA])
            c2 = list(clear(cr))
            if typ == 'Q' and 'REFUSED_KEEPS_POS' in mut:     # mutant: a refused item keeps its position
                c2[K_CHAIN] = I(chain + (I(('A', m[3], m[4])),))
            reason = 'MAILBOX_REFUSED'
            if log[0] == 'N':                                 # I-O-5: kept, sent again at every reading
                c2[K_REFN] = cr[K_REFN] | {log}
                reason = 'NOTICE_REFUSED'
            if log[0] == 'C' and 'OUTBOX_KEEPS_STMT' in mut:
                c2[K_REFN] = cr[K_REFN] | {log}               # mutant: a refused statement is kept
            rdi = cr[K_RD]
            if rdi is not None:
                c2[K_RD] = rdi[:11] + (rdi[11] | {reason},) + rdi[12:]
                if log[0] == 'C':
                    c2[K_QUEUE] = cr[K_QUEUE] + (('END',),)   # the reading is not whole: its alarm
            return tuple(c2)
        if typ == 'M':                                        # I-O-6
            c2 = list(cr)
            c2[K_MISS] = log
            return tuple(c2)
        if typ == 'P':                                        # I-O-3 / I-O-4 / I-E-4
            hce, hk, hA = ans[1], ans[2], ans[3]
            if hce == cr[K_CE] and hce is not None:
                if cr[K_RKMAX] > hk:
                    ev.append('P_ROLLBACK_BY_RECEIPT')
                    return self.lost(cr, ev, 'MAILBOX_STATE_LOST')
                if hk < len(chain) and chain[hk] == hA:
                    return cr
            if log[0] == 'E':
                return cr
            return self.lost(cr, ev)
        return cr

    def courier_accepted(self, cr, mb, log):
        m = U(cr[K_INFL])
        chain = U(cr[K_CHAIN]) + (I(('A', m[3], m[4])),)
        rdi = cr[K_RD]
        meplast = cr[K_CHAL][3]
        cr2 = list(cr)
        cr2[K_CHAIN] = I(chain)
        cr2[K_J] = cr[K_J] + 1
        cr2[K_LASTREF] = log[2]
        cr2[K_MEPLAST] = meplast
        cr2[K_OBS] = rdi[6]
        cr2[K_PHASE] = 0
        cr2[K_CHAL] = None
        cr2[K_INFL] = None
        cr2[K_INFLOG] = None
        cr2[K_RKMAX] = len(chain) - 1
        cr2[K_RD] = None
        cr2[K_OWNA] = (log[7], log[8])
        cr2[K_GOWNA] = (log[7], log[8])
        return tuple(cr2)

    def courier_take_challenge(self, s, S, inc):
        """O-1, 5.6, I-O-4, I-E-1."""
        rt, mb, w, cr, bk, net, ctr, rd, gh = s
        mut = self.mut
        ev = []
        rid = gh[G_NREQ]
        gh = gh[:G_NREQ] + (rid + 1,)
        L, gh2, ser = self.mk1_issue(rt, mb, gh, ev)
        L[REQS] = mb[REQS] | {rid}
        mb2 = tuple(L)
        net2 = net | {I(('Q', rid, mb[MEP]))}
        anchor = mb[ANCHOR] if mb[ANCHOR] is not None else (0, None)
        chal = (ser, anchor[0], anchor[1], mb[MEP], self.gaps(mb))
        lab = 'courier_takes_challenge->token%d' % ser
        hce, hk, hA = mb[CE], mb[HK], mb[HA]
        if cr[K_CE] is None:                                  # opening an epoch (I-E-1)
            if gh2[G_NEXTCE] > self.c['EMAX'] or ctr[C_OPENS] >= self.c['EMAX'] + 2:
                return []
            ce = gh2[G_NEXTCE]
            A0 = I(('A0', ce))
            reason = cr[K_REASON]
            owna0 = cr[K_OWNA]
            if (owna0 is not None and anchor[0] < owna0[0] and 'NO_OWN_ANCHOR' not in mut
                    and reason != 'MAILBOX_STATE_LOST'):
                reason = 'MAILBOX_STATE_LOST'                 # I-O-4: the challenge's anchor is behind
                ev.append('P_ROLLBACK_BY_ANCHOR')
                ev.append('P_MAILBOX_ROLLBACK')
            ident = I(('E', ce, reason, (ce, 1), hce))
            log = ('E', ident, reason, hce)
            obs0, mepl0 = (None,) * self.c['RUNS'], None
            if self.c['COURIER'] == 'oldcursor' and mb[STMTS] and reason == 'COURIER_STATE_LOST':
                obs0, mepl0 = mb[STMTS][-1][S_OBS], mb[STMTS][-1][S_MEP]
            cr2 = (ce, I((A0,)), 1, None, mepl0, obs0, 1, chal, (log,), None, None, 0,
                   frozenset(), frozenset(), None, True, False, cr[K_OWNA], reason, None, cr[K_GOWNA])
            gh3 = (ce + 1, True) + gh2[2:]
            cr2, net3 = self.advance(cr2, net2, ev)
            return [(lab + ' -> opens epoch(%s,closes=%s)' % (reason, hce),
                     S(mb_=mb2, gh_=gh3, cr_=cr2, net_=net3, ctr_=inc(C_OPENS)), tuple(ev))]
        chain = U(cr[K_CHAIN])
        owna = self.own_anchor_now(cr)
        behind = (owna is not None and anchor[0] < owna[0] and 'NO_OWN_ANCHOR' not in mut)
        rb_receipt = (hce == cr[K_CE] and cr[K_RKMAX] > hk)
        if behind or rb_receipt:                              # I-O-4
            ev.append('P_ROLLBACK_BY_ANCHOR' if behind else 'P_ROLLBACK_BY_RECEIPT')
            ev.append('P_MAILBOX_ROLLBACK')
            cr2 = self.no_epoch_courier('MAILBOX_STATE_LOST', owna, self.gown_now(cr))
            return [(lab + ' -> mailbox behind the courier: MAILBOX_ROLLBACK', S(mb_=mb2, gh_=gh2, cr_=cr2, net_=net2),
                     tuple(ev))]
        if hce == cr[K_CE] and hk < len(chain) and chain[hk] == hA:
            cr2 = cr[:K_PHASE] + (1, chal) + cr[K_CHAL + 1:]
            return [(lab, S(mb_=mb2, gh_=gh2, cr_=cr2, net_=net2), tuple(ev))]
        cr2 = self.lost(cr, ev)
        return [(lab + ' -> head not of its chain: state lost', S(mb_=mb2, gh_=gh2, cr_=cr2, net_=net2), tuple(ev))]

    def courier_read(self, s, rk, fail, evok):
        rt, mb, w, cr, bk, net, ctr, rd, gh = s
        c = self.c
        dec, l3 = w
        N = len(dec)
        stand = self.stand(w)
        tser, aN, ahead, cmep, cgaps = cr[K_CHAL]
        obs = cr[K_OBS]
        ev = []
        reasons = set()
        L = None
        existing = [r for r in range(c['RUNS']) if stand[r] is not None]
        at, head_at = aN, (self.whead(dec, aN) if aN <= N else None)
        owna = self.own_anchor_now(cr)
        ga = mb[GANCHOR]
        gwit = ga is None or (ga[0] <= N and self.whead(dec, ga[0]) == ga[1])
        if c['COURIER'] != 'nocheck':                        # O-2, O-3, O-4, I-O-4
            if aN > N:
                reasons.add('ROLLBACK')
                ev.append('P_ROLLBACK_ALARM')
            elif aN > 0 and self.whead(dec, aN) != ahead:
                reasons.add('FORK')
                ev.append('P_FORK_ALARM')
            elif rk == FZ and owna is not None and 'NO_OWN_ANCHOR' not in self.mut:
                if owna[0] > N:
                    reasons.add('ROLLBACK')
                    ev.append('P_OWN_ANCHOR_FORK')
                elif self.whead(dec, owna[0]) != owna[1]:
                    reasons.add('FORK')
                    ev.append('P_OWN_ANCHOR_FORK')
        elif aN > N:
            at, head_at = N, self.whead(dec, N)

        def post(e):
            nonlocal L
            if L is None:
                L = list(mb)
            if e not in L[EVID]:
                L[EVID] = L[EVID] | {e}
                if e in self.gaps(tuple(mb)) or e in L[GAPSEV]:
                    ev.append('P_GAP_CLOSED')
                L[GAPSEV] = L[GAPSEV] - {e}
        for e in sorted(cgaps):                              # I-O-7: store again every listed gap
            if c['EV_FAIL'] and not evok.get(('gap', e), True):
                reasons.add('EVIDENCE_NOT_HELD')
            else:
                post(e)
        queue = list(sorted(cr[K_REFN]))                     # I-O-5: refused notices sent again
        sent = set(cr[K_SENT]) | {lg[1] for lg in cr[K_REFN]}
        if cr[K_REFN]:
            reasons.add('NOTICE_REFUSED')
        read = set()
        carried = []
        if not reasons & {'ROLLBACK', 'FORK'}:
            if rk in (FZ, RF):
                read = set(existing)
            else:
                named = {rr for (rr, v) in dec[aN:N]}
                uns = set() if 'OR2' in self.mut else {r for r in existing if obs[r] is None or obs[r][0] in ('u', 'f')}
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
                    held = e in (L[EVID] if L is not None else mb[EVID])
                    if held or evok.get(r, True):
                        claim = 'H'
                        post(e)
                    else:
                        claim = 'X'
                        reasons.add('EVIDENCE_NOT_HELD')
                if ident in sent:                            # I-O-8
                    continue
                queue.append(('N', ident, claim, e))
                sent.add(ident)
        if fail:
            reasons.add('DEADLINE')
        mb2 = tuple(L) if L is not None else mb
        ref_j = cr[K_J]
        ref = I(('ref', cr[K_CE], ref_j, tser))
        obs_after = tuple(((stand[r][0], stand[r][1], ref, ref_j) if r in read else obs[r]) for r in range(c['RUNS']))
        oldest_ref = None
        if carried:
            oldest_ref = obs[min(carried, key=lambda r: obs[r][3])][2]
        called = I(frozenset(self.ident_of(r, stand[r]) for r in existing if stand[r][0] in ('u', 'x', 'f')))
        evneed = I(frozenset(self.evid_of(r, stand[r]) for r in existing if stand[r][0] == 'f'))
        rdi = (tser, rk, at, head_at, N, self.whead(dec, N), obs_after, len(carried), oldest_ref, called, evneed,
               frozenset(reasons), self.gown_now(cr), gwit)
        queue.append(('END',))
        cr2 = cr[:K_PHASE] + (2,) + cr[K_PHASE + 1:K_QUEUE] + (tuple(queue),) + cr[K_QUEUE + 1:K_RD] + (rdi,) + cr[K_RD + 1:]
        cr2, net2 = self.advance(cr2, net, ev)
        return mb2, cr2, net2, ev

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
        if pending is not None:
            m = U(pending)
            L = list(mb)
            L[PENDING] = None
            link = self.held_rcpt(mb, m[4]) is not None and 'DL2_off' not in mut
            full, newrooms, rev = self.room_check(mb, 'N', link)
            L[ROOMS] = newrooms if newrooms is not None else mb[ROOMS]
            mb2, ans, ev = self.dl5_write(mb, L, pending, m, list(rev), link)
            cr2 = self.courier_answer(cr, pending, ans, mb2, ev)
            cr2, net2 = self.advance(cr2, net, ev)
            res.append(('mailbox_completes_write ' + self.desc(pending),
                        S(mb_=self.normalise(mb2), cr_=cr2, net_=net2), tuple(ev)))
        if rt < c['TMAX']:
            res.append(('tick', S(rt_=rt + 1, mb_=setmb(BT=mb[BT] + 1, MONO=mb[MONO] + 1)), ()))
            if ctr[C_SUSP] < c['SUSPENDS']:
                res.append(('suspend(boottime+1,monotonic+0)', S(rt_=rt + 1, mb_=setmb(BT=mb[BT] + 1), ctr_=inc(C_SUSP)), ()))
        if ctr[C_WALL] < c['WALL_MOVES']:
            for d in (-1, 1):
                if -1 <= mb[WOFF] + d <= 1:
                    res.append(('wall_clock_%s' % ('back' if d < 0 else 'forward'),
                                S(mb_=setmb(WOFF=mb[WOFF] + d), ctr_=inc(C_WALL)), ()))
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
        if ctr[C_LOSS] < c['LOSSES']:
            res.append(('courier_loses_state', S(cr_=self.no_epoch_courier('COURIER_STATE_LOST', None, None), ctr_=inc(C_LOSS)), ()))
        if ctr[C_SNAP] < c['SNAPS'] and bk != cr:
            res.append(('courier_state_copied', S(bk_=cr, ctr_=inc(C_SNAP)), ()))
        if bk is not None and ctr[C_RESTORE] < c['RESTORES'] and bk != cr:
            n_acc = sum(1 for x in mb[STMTS] if x[S_CE] == bk[K_CE])
            stale = bk[K_CE] is not None and n_acc > bk[K_J] - 1
            bk2 = bk[:K_STALE] + (stale,) + bk[K_STALE + 1:]
            res.append(('courier_restored_from_old_copy%s' % (' (older than its last accepted statement)' if stale else ''),
                        S(cr_=bk2, ctr_=inc(C_RESTORE)), ('P_RESTORE',)))
        dec, l3 = w
        wit_ok = cr[K_PHASE] == 1
        if wit_ok:
            stand = self.stand(w)
            if len(dec) < c['NMAX']:
                for r in range(c['RUNS']):
                    vals = ('f',) if (stand[r] is not None and stand[r][0] == 'f') else c['VALUES']
                    for v in vals:
                        res.append(('decision%d(run%d->%s)' % (len(dec) + 1, r, v), S(w_=(dec + ((r, v),), l3)), ()))
            for r in range(c['RUNS']):
                x = stand[r]
                if x is None:
                    continue
                if c['L3'] and x[0] == 'u':
                    for v in ('p', 'x'):
                        res.append(('stored_result_without_decision(run%d->%s)' % (r, v), S(w_=(dec, l3 | {(r, x[1], v)})), ()))
                if ctr[C_CARRY] < c['CARRY_BREAKS'] and x[0] in ('p', 'x') and not x[2]:
                    v = 'x' if x[0] == 'p' else 'p'
                    res.append(('CAP_OWNER_changes_settled_run%d->%s' % (r, v),
                                S(w_=(dec, l3 | {(r, x[1], v)}), ctr_=inc(C_CARRY)), ('P_CARRY_BREAK',)))
            if ctr[C_WTRUNC] < c['WTRUNC']:
                for p in range(len(dec)):
                    res.append(('witness_chain_cut_back_to_%d' % p,
                                S(w_=(dec[:p], frozenset(x for x in l3 if x[1] <= p)), ctr_=inc(C_WTRUNC)), ('P_WITNESS_TRUNC',)))
        if c['ORPHAN']:
            binders = mb[NAMED_H] if 'ORPHAN_NOTHELD' in mut else mb[NAMED]
            for e in sorted(mb[EVID] - binders):
                evs = ['P_ORPHAN']
                if pending is not None:
                    evs.append('P_PENDING_ORPHAN')
                if e in mb[NAMED]:
                    evs.append('P_GAP_REBEGIN')
                res.append(('evidence_orphan_removed(%s)' % (U(e),), S(mb_=setmb(EVID=mb[EVID] - {e})), tuple(evs)))
        if c['RETIRE'] and c['ROOMS'] is not None:
            last = mb[STMTS][-1] if mb[STMTS] else None
            keep = {last[S_REF], last[S_OLDEST]} if last else set()
            for x in mb[STMTS]:
                if x[S_REF] not in keep and x[S_REF] not in mb[RETIRED]:
                    rm = mb[ROOMS]
                    res.append(('mailbox_retires_statement_body', S(mb_=setmb(RETIRED=mb[RETIRED] | {x[S_REF]},
                                ROOMS=(rm[0], rm[1], rm[2] - 1, rm[3], rm[4]))), ('P_RETIRE',)))
                    break
        if ctr[C_WIPE] < c['WIPES'] and pending is None:
            L = list(mb)
            self.wipe_fields(L)
            L[TOKS] = ()
            L[NHELD_EVER] = mb[NHELD_EVER]
            res.append(('mailbox_loses_record_of_budget', S(mb_=tuple(L), ctr_=inc(C_WIPE)), ('P_WIPE', 'WIPE')))
        if pending is not None:
            return res + self.reader_moves(s, S)
        for mid in net:
            m = U(mid)
            if m[0] == 'Q':
                if ctr[C_REQ] >= c['REQ_REPLAYS']:
                    continue
                ev = []
                if 'REQ_REPLAY' in mut:
                    L, gh2, ser = self.mk1_issue(rt, mb, gh, ev)
                    ev.append('V_PMK1')
                    res.append(('adversary_replays %s -> token%d issued' % (self.desc(mid), ser),
                                S(mb_=tuple(L), gh_=gh2, ctr_=inc(C_REQ)), tuple(ev)))
                elif m[2] == mb[MEP]:
                    res.append(('adversary_replays %s -> 409 REPLAY' % self.desc(mid), S(ctr_=inc(C_REQ)), ('P_REQ_REPLAY_REFUSED',)))
                continue
            mb2, ans, ev = self.deliver(rt, mb, gh, mid)
            if mid == cr[K_INFL]:
                ev2 = list(ev)
                cr2 = self.courier_answer(cr, mid, ans, mb2, ev2)
                cr2, net2 = self.advance(cr2, net, ev2)
                res.append(('courier_delivers ' + self.desc(mid) + ' -> ' + self.ansdesc(ans), S(mb_=mb2, cr_=cr2, net_=net2), tuple(ev2)))
            if mb2 == mb and not [e for e in ev if e != 'DL2HIT']:
                continue
            res.append(('adversary_delivers ' + self.desc(mid) + ' -> ' + self.ansdesc(ans), S(mb_=mb2), ev))
        # courier moves
        if c['COURIER'] == 'resume' and cr[K_CE] is None and cr[K_REASON] == 'COURIER_STATE_LOST' and mb[CE] is not None:
            last = [x for x in mb[STMTS] if x[S_CE] == mb[CE]]
            if last:
                lx = last[-1]
                lref, mepl, obs, jn = lx[S_REF], lx[S_MEP], lx[S_OBS], U(lx[S_REF])[2] + 1
            else:
                lref = mepl = None
                obs = (None,) * c['RUNS']
                jn = 1
            chain = tuple([None] * mb[HK] + [mb[HA]])
            cr2 = (mb[CE], I(chain), jn, lref, mepl, obs, 0, None, (), None, None, mb[HK], frozenset(), frozenset(),
                   None, False, False, None, 'COURIER_STATE_LOST', None, None)
            res.append(('courier_resumes_from_mailbox_head', S(cr_=cr2), ()))
            return res + self.reader_moves(s, S)
        phase = cr[K_PHASE]
        if phase == 0 and cr[K_INFL] is None and not cr[K_QUEUE] and ctr[C_READS] < c['MAX_READS']:
            res.extend(self.courier_take_challenge(s, S, inc))
        if phase == 1 and cr[K_INFL] is None and not cr[K_QUEUE] and cr[K_MISS] is None and ctr[C_READS] < c['MAX_READS']:
            stand = self.stand(w)
            tser, aN, ahead, cmep, cgaps = cr[K_CHAL]
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
                    uns = set() if 'OR2' in mut else {r for r in existing if cr[K_OBS][r] is None or cr[K_OBS][r][0] in ('u', 'f')}
                    if not [r for r in existing if r not in (named | uns)]:
                        continue
                    readset = (named | uns) & set(existing)
                else:
                    readset = set(existing)
                keys = [r for r in sorted(readset) if stand[r][0] == 'f' and self.evid_of(r, stand[r]) not in mb[EVID]]
                keys += [('gap', e) for e in sorted(cgaps)]
                evchoices = [{}]
                if c['EV_FAIL'] and keys:
                    evchoices = [{kk: not ((b >> i) & 1) for i, kk in enumerate(keys)} for b in range(1 << len(keys))]
                for fail in ((False, True) if c['READ_FAIL'] else (False,)):
                    for evok in evchoices:
                        mb2, cr2, net2, ev = self.courier_read(s, rk, fail, evok)
                        lab = 'courier_reads(%s,N%d%s%s)' % (rk, len(dec), ',DEADLINE' if fail else '',
                              ''.join(',evidence_%s_%s' % (kk, 'stored' if o else 'REFUSED') for kk, o in sorted(evok.items(), key=str)))
                        res.append((lab, S(mb_=mb2, cr_=cr2, net_=net2, ctr_=inc(C_READS)), tuple(ev)))
        if cr[K_MISS] is not None:                            # I-O-6
            log = cr[K_MISS]
            e = log[3]
            L = list(mb)
            L[EVID] = mb[EVID] | {e}
            L[GAPSEV] = mb[GAPSEV] - {e}
            c2 = list(cr)
            c2[K_INFL] = None
            c2[K_INFLOG] = None
            c2[K_MISS] = None
            c2[K_QUEUE] = (log,) + cr[K_QUEUE]
            cr2 = tuple(c2)
            ev = ['P_RESIGNED']
            cr2, net2 = self.advance(cr2, net, ev)
            res.append(('courier_stores_evidence_again_and_resigns', S(mb_=tuple(L), cr_=cr2, net_=net2), tuple(ev)))
            if c['EV_FAIL']:
                log2 = ('N', log[1], 'X', e)
                c3 = list(cr)
                c3[K_INFL] = None
                c3[K_INFLOG] = None
                c3[K_MISS] = None
                c3[K_QUEUE] = (log2,) + cr[K_QUEUE]
                rdi = cr[K_RD]
                if rdi is not None:
                    c3[K_RD] = rdi[:11] + (rdi[11] | {'EVIDENCE_NOT_HELD'},) + rdi[12:]
                cr3 = tuple(c3)
                ev = ['P_NOTHELD_REMADE']
                cr3, net3 = self.advance(cr3, net, ev)
                res.append(('courier_evidence_refused_sends_NOT_HELD', S(cr_=cr3, net_=net3), tuple(ev)))
        if phase == 2 and cr[K_INFL] is None and not cr[K_QUEUE] and cr[K_MISS] is None:
            cr2 = cr[:K_PHASE] + (0, None) + cr[K_CHAL + 1:K_RD] + (None,) + cr[K_RD + 1:]
            res.append(('courier_reading_done', S(cr_=cr2), ()))
        res.extend(self.reader_moves(s, S))
        return res

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
        key = (rt, mb, gh[G_GMEP], ctr[C_REBOOT] >= 1, ctr[C_RESTART] >= 1, ctr[C_WIPE] >= 1, rd)
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
        gaps = mb[NAMED] - mb[EVID]                         # the true state of gaps (E-B-3)
        if S is not None:
            out.append('P_COVERED')
            t = self.tok(mb, S[S_TOK])
            if not (rt - t[T_RT] <= c['L'] and t[T_GMEP] == gh[G_GMEP]):
                out.append('V_SAF3')
            if not (S[S_SEQ] > mb[OPEN_SEQ] and any(
                    x[S_RK] == FZ and mb[OPEN_SEQ] < x[S_SEQ] <= S[S_SEQ] and x[S_CE] == mb[CE] for x in mb[STMTS])):
                out.append('V_SAF5')
            fresh_true = (S[S_CARR] == 0) or self.oldest_fresh(rt, mb, S, mailbox_time=False)
            if (gaps or mb[ALARM_SEQ] > S[S_SEQ] or mb[RSTMT_SEQ] > S[S_SEQ] or mb[ROOM_SEQ] > S[S_SEQ] or not fresh_true):
                out.append('V_SAF7')
            held = {e[0] for e in mb[HELD]}
            if not U(S[S_CALLED]) <= held:
                out.append('V_CENT_N')
            if not U(S[S_EVNEED]) <= mb[EVID]:
                out.append('V_CENT_E')
            if not fresh_true:
                out.append('V_R_AT_STATUS')
            reasons82 = (mb[RSTMT_SEQ] > S[S_SEQ] or mb[ROOM_SEQ] > S[S_SEQ] or gaps or mb[ALARM_SEQ] > S[S_SEQ]
                         or self.eff(rt, mb, t) != 'U' or (S[S_CARR] > 0 and not self.oldest_fresh(rt, mb, S, True))
                         or not any(x[S_RK] == FZ and x[S_CE] == mb[CE] for x in mb[STMTS]) or S[S_MEP] != mb[MEP])
            if reasons82:
                out.append('V_C1_VS_82')
            if S[S_RK] == INC and S[S_CARR] >= 1:
                out.append('P_COVERED_INC')
            if mb[OPEN_REASON] == 'COURIER_STATE_LOST':
                out.append('P_COVERED_AFTER_LOST')
            if mb[OPEN_REASON] == 'MAILBOX_STATE_LOST':
                out.append('P_COVERED_AFTER_MBLOST')
            if ctr[C_REBOOT] >= 1:
                out.append('P_COVERED_AFTER_REBOOT')
            if ctr[C_RESTART] >= 1:
                out.append('P_COVERED_AFTER_RESTART')
            if ctr[C_WIPE] >= 1:
                out.append('P_WIPE_THEN_COVERED')
            if S[S_RK] == RF and mb[MEP] > 0:
                out.append('P_COVERED_REFRESH_NEWMEP')
        elif mb[CE] is not None:
            lst = [x for x in mb[STMTS] if x[S_CE] == mb[CE] and x[S_MEP] == mb[MEP]]
            if lst:
                S2 = lst[-1]
                t = self.tok(mb, S2[S_TOK])
                if t is not None and self.eff(rt, mb, t) == 'U' and not gaps:
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
            print('  %-28s declared=%-12s observed=%-12s %s' % (p, v['declared'], v['observed'], '' if v['agree'] else 'MISMATCH'))
    for p, v in props.items():
        if v.get('observed') == 'violated':
            print('  shortest trace for %s:' % p)
            for i, l in enumerate(v['trace']):
                print('     %2d. %s' % (i + 1, l))
    print('  verdict agrees with declaration: %s' % (not mism))


if __name__ == '__main__':
    main()
