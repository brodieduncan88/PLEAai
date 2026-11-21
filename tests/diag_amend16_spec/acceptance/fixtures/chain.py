"""A scripted budget: the witness's chain, its stored reports and results, as the honest witness would hold them.

This is TEST DATA, written from the formats of e25a297 (`plea_gateway/store.py`: decisions {seq, op, kind, code,
observation, prev_hash, hash}, chain_hash = sha256(prev || canonical({seq, op, kind, code, observation})); attempts
[aid, req, phase, nonce, receipt, crossed]; the witness's GET /run answer {root, aid, evidence: [{seq, evidence,
derived}], result}) and from the specification's D-9 to D-14.  It is not the contract engine: kinds and codes are the
ones the tests need (APPLIED / DENIED / DUPLICATE; VERDICT_RECORDED), and every helper says what it records.

Labels of RELEASE and RECONCILE decisions are derived as the witness derives them (`plea_gateway/evidence.py`,
re-written here, not imported): the test chooses the report, never the label, except through `label=` which models a
witness whose pinned keys differ from the reader's (K-CNT-4, P-KEYS) and is used only in tests that say so.

The witness's signing key is a TestKey in the test process: the witness is a trusted party in every test here, and
ROLLBACK / FORK / CHAIN_BROKEN are modelled by the scripted witness's misbehaviour flags (CAP-OWNER tests).
"""
import copy
import hashlib

from fixtures.crypto import TestKey, canonical, report_message, verify_sig, H, rand_hex

PER_ATTEMPT = ('RESERVE', 'ACCEPT_RESERVATION', 'TOKEN', 'START', 'ACCEPT_INTENT', 'RECEIPT', 'CROSS', 'RELEASE',
               'RECONCILE', 'TIMEOUT', 'MISSING_RECEIPT')                         # D-13
LIVE_R = ('RESERVING', 'RESERVED', 'TOKEN')
LIVE_C = ('INTENT_PENDING', 'CONSUMED', 'NO_EFFECT', 'EFFECT', 'INDETERMINATE')


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def chain_hash(prev, seq, op, kind, code, observation) -> str:
    return _sha(prev + canonical({'seq': seq, 'op': op, 'kind': kind, 'code': code, 'observation': observation}))


def _genuine(report, keys) -> bool:
    return isinstance(report, dict) and report.get('signer') in keys and \
        verify_sig(report.get('signer', ''), report.get('signature', ''), report_message(report))


def derive_release_label(report, keys, root, aid) -> str:
    if not isinstance(report, dict) or report.get('kind') != 'FENCE_REPORT' or report.get('claim') != 'FENCED_NO_START' or not _genuine(report, keys):
        return 'NONE'
    if report.get('root') != root or report.get('aid') != aid:
        return 'WRONG_BINDING'
    return 'BOUND_FENCE'


def derive_verdict(report, keys, root, aid, nonce):
    if not isinstance(report, dict) or report.get('kind') != 'EFFECT_REPORT' or report.get('claim') not in ('EFFECT', 'NO_EFFECT', 'UNKNOWN') or not _genuine(report, keys):
        return 'UNKNOWN', 'NONE'
    if report.get('root') != root or report.get('aid') != aid or nonce is None or report.get('nonce') != nonce:
        return report.get('claim'), 'WRONG_BINDING'
    return report.get('claim'), 'AUTHORISED'


class Budget:
    """One budget (ACC-5: made for one test alone).  `gate` is the honest gate client (or None); `witness_gate_keys` the
    keys the WITNESS pins (the reader's keys are given separately to every reader, P-KEYS)."""

    def __init__(self, root, witness_key: TestKey, witness_gate_keys, gate=None):
        self.root, self.wkey, self.wgk, self.gate = root, witness_key, tuple(witness_gate_keys), gate
        self.prov_hash = _sha('provisioning:' + root + rand_hex(8))     # stands for the provisioning record's hash
        self.decisions = []                                             # rows as the witness stores them
        self.attempts = {}                                              # aid -> [aid, req, phase, nonce, receipt, crossed]
        self.evidence = {}                                              # name -> [{seq, evidence, derived}]
        self.results = {}                                               # aid -> stored result (envelope) or absent
        self.business, self.witness_state = 'OPEN', 'ACTIVE'

    # ---------------------------------------------------------------- state
    def observation(self):
        atts = sorted(copy.deepcopy(list(self.attempts.values())), key=lambda a: a[0])
        ph = [a[2] for a in atts]
        n = ph.count('NO_EFFECT')
        return {'k': 1000, 'm': 0, 'witness': self.witness_state, 'business': self.business, 'reregistered': False,
                'live': [sum(p in LIVE_R for p in ph), sum(p in LIVE_C for p in ph), n],
                'accepted': [sum(p in ('RESERVED', 'TOKEN', 'INTENT_PENDING') for p in ph),
                             sum(p in ('CONSUMED', 'NO_EFFECT', 'EFFECT', 'INDETERMINATE') for p in ph), n],
                'credit': 0, 'attempts': atts}

    @property
    def n(self) -> int:
        return len(self.decisions)

    def head_at(self, n: int) -> str:
        return self.prov_hash if n == 0 else self.decisions[n - 1]['hash']

    @property
    def head(self) -> str:
        return self.head_at(self.n)

    def phase(self, aid):
        a = self.attempts.get(aid)
        return a[2] if a else None

    def nonce(self, aid):
        a = self.attempts.get(aid)
        return a[3] if a else None

    def phase_at(self, aid, n):
        """(phase, chain nonce) of the run in the chain's state after decision n (D-4, D-12)."""
        if n == 0:
            return None, None
        for a in self.decisions[n - 1]['observation']['attempts']:
            if a[0] == aid:
                return a[2], a[3]
        return None, None

    # ---------------------------------------------------------------- decisions
    def decide(self, op, kind='APPLIED', code='APPLIED', report=None, derived=None, evidence_name=None):
        seq = self.n + 1
        obs = self.observation()
        prev = self.head
        row = {'seq': seq, 'op': list(op), 'kind': kind, 'code': code, 'observation': obs, 'prev_hash': prev,
               'hash': chain_hash(prev, seq, list(op), kind, code, obs)}
        self.decisions.append(row)
        if report is not None:
            name = evidence_name if evidence_name is not None else op[1]
            self.evidence.setdefault(name, []).append({'seq': seq, 'evidence': report, 'derived': derived})
        return seq

    def _set(self, aid, phase=None, nonce=None):
        a = self.attempts[aid]
        if phase is not None:
            a[2] = phase
        if nonce is not None:
            a[3] = nonce

    def new_run(self, aid=None, upto='CONSUMED', nonce=None):
        """RESERVE .. up to the phase asked: RESERVED, TOKEN, INTENT_PENDING (START), ACCEPTED (ACCEPT_INTENT applied,
        phase still INTENT_PENDING), CONSUMED (CROSS).  The honest gate host is told of the intent acceptance."""
        aid = aid or ('a-' + rand_hex(8))
        nonce = nonce or ('n-' + rand_hex(20))
        self.attempts[aid] = [aid, 'verify:' + rand_hex(12), 'RESERVING', None, None, False]
        self.decide(['RESERVE', aid, self.attempts[aid][1]], code='RESERVED')
        steps = ['RESERVED', 'TOKEN', 'INTENT_PENDING', 'ACCEPTED', 'CONSUMED']
        stop = steps.index(upto)
        self._set(aid, 'RESERVED'); self.decide(['ACCEPT_RESERVATION', aid], code='RESERVATION_ACCEPTED')
        if stop >= 1:
            self._set(aid, 'TOKEN'); self.decide(['TOKEN', aid], code='TOKEN_ISSUED')
        if stop >= 2:
            self._set(aid, 'INTENT_PENDING', nonce); self.decide(['START', aid, nonce], code='INTENT_PENDING')
        if stop >= 3:
            self.decide(['ACCEPT_INTENT', aid], code='INTENT_ACCEPTED')
            if self.gate is not None:
                self.gate.intent_accepted(self.root, aid, nonce)
        if stop >= 4:
            self._set(aid, 'CONSUMED'); self.attempts[aid][5] = True; self.decide(['CROSS', aid], code='CROSSED')
        return aid, nonce

    def reconcile(self, aid, report, kind=None, code=None, label=None, store_report=True):
        """RECONCILE with this report; the label is the witness's (derived), unless `label` overrides it (a witness that
        pins other keys).  APPLIED VERDICT_RECORDED moves a CONSUMED run to EFFECT or NO_EFFECT (UNKNOWN: APPLIED,
        UNKNOWN_RECORDED, phase unchanged)."""
        v, lab = derive_verdict(report, self.wgk, self.root, aid, self.nonce(aid))
        lab = label or lab
        ph = self.phase(aid)
        if kind is None:
            if lab == 'AUTHORISED' and ph == 'CONSUMED' and v in ('EFFECT', 'NO_EFFECT'):
                kind, code = 'APPLIED', 'VERDICT_RECORDED'
            elif lab == 'AUTHORISED' and ph == 'CONSUMED' and v == 'UNKNOWN':
                kind, code = 'APPLIED', 'UNKNOWN_RECORDED'
            elif lab == 'AUTHORISED' and ph in ('EFFECT', 'NO_EFFECT') and ph == v:
                kind, code = 'DUPLICATE', 'VERDICT_ALREADY_RECORDED'
            else:
                kind, code = 'DENIED', 'NOT_AUTHORISED' if lab != 'AUTHORISED' else 'NOT_CONSUMED'
        if (kind, code) == ('APPLIED', 'VERDICT_RECORDED') and aid in self.attempts:
            self._set(aid, v)
        return self.decide(['RECONCILE', aid, v, lab], kind, code, report if store_report else None, lab)

    def release(self, aid, report, kind=None, code=None, label=None, store_report=True):
        lab = label or derive_release_label(report, self.wgk, self.root, aid)
        ph = self.phase(aid)
        if kind is None:
            if lab == 'BOUND_FENCE' and ph in ('RESERVING', 'RESERVED', 'TOKEN', 'INTENT_PENDING'):
                kind, code = 'APPLIED', 'RELEASED'
            else:
                kind, code = 'DENIED', 'RELEASE_DENIED'
        if (kind, code) == ('APPLIED', 'RELEASED'):
            self._set(aid, 'RELEASED')
        return self.decide(['RELEASE', aid, lab], kind, code, report if store_report else None, lab)

    def discard(self, aid):
        self._set(aid, 'DISCARDED'); return self.decide(['TIMEOUT', aid], code='DISCARDED')

    def indeterminate(self, aid):
        self._set(aid, 'INDETERMINATE'); return self.decide(['REREGISTER'], code='REREGISTERED')

    def budget_level(self, op=('CRASH',)):
        return self.decide(list(op), code='CRASH_RECORDED')

    def unborne(self, name, report=None, op='RECONCILE'):
        """A decision naming a name no attempt bears (D-12): DENIED, with the report kept if one is given."""
        if op == 'RECONCILE':
            v, lab = derive_verdict(report, self.wgk, self.root, name, None)
            return self.decide(['RECONCILE', name, v, lab], 'DENIED', 'UNKNOWN_ATTEMPT', report, lab)
        if op == 'RELEASE':
            lab = derive_release_label(report, self.wgk, self.root, name)
            return self.decide(['RELEASE', name, lab], 'DENIED', 'UNKNOWN_ATTEMPT', report, lab)
        return self.decide([op, name], 'DENIED', 'UNKNOWN_ATTEMPT', report, None)

    def store_result(self, aid, value=None, outcome='value', envelope=None):
        self.results[aid] = envelope if envelope is not None else ({'outcome': outcome, 'value': value} if outcome == 'value' else {'outcome': outcome, 'detail': 'x', 'value': value})

    # ---------------------------------------------------------------- what the witness answers
    def run_answer(self, name):
        return {'root': self.root, 'aid': name, 'evidence': copy.deepcopy(self.evidence.get(name, [])),
                'result': copy.deepcopy(self.results.get(name))}

    def checkpoint(self, nonce=None, at=None, seq=None, head=None, head_at=None, key=None, time_='2026-11-21T12:00:00Z'):
        seq = self.n if seq is None else seq
        head = self.head_at(seq) if head is None else head
        if at is not None and head_at is None:
            head_at = self.head_at(at)
        c = {'statement': 'CHECKPOINT', 'root': self.root, 'seq': seq, 'head': head, 'business': self.business,
             'witness': self.witness_state, 'time': time_, 'nonce': nonce, 'at': at, 'head_at': head_at}
        k = key or self.wkey
        return dict(c, signer=k.public_hex, signature=k.sign(canonical(c).encode()))

    def names_in(self, lo, hi):
        """Names named by per-attempt decisions in (lo, hi] (O-R-1)."""
        out = []
        for d in self.decisions[lo:hi]:
            if d['op'][0] in PER_ATTEMPT and d['op'][1] not in out:
                out.append(d['op'][1])
        return out

    def decisions_naming(self, name, upto=None):
        upto = self.n if upto is None else upto
        return [{k: d[k] for k in ('seq', 'op', 'kind', 'code')} for d in self.decisions[:upto]
                if d['op'][0] in PER_ATTEMPT and d['op'][1] == name]

    def rewrite_below(self, seq):
        """The witness's chain forked at decision seq: that decision recorded differently and every hash from it
        recomputed (a fork of the witness below an anchor: CAP-OWNER or the witness's key)."""
        d = self.decisions[seq - 1]
        d['code'] = d['code'] + '_FORKED'
        prev = self.head_at(seq - 1)
        for row in self.decisions[seq - 1:]:
            row['prev_hash'] = prev
            row['hash'] = chain_hash(prev, row['seq'], row['op'], row['kind'], row['code'], row['observation'])
            prev = row['hash']

    def result_digest_of(self, value):
        return H(value)
