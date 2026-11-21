"""The seam between the acceptance tests and the system under test (Amendment 16 specification, VERSION 6, SPEC_v6_as_sent_to_review.md, section 12).

The tests never import the implementation.  They call an ADAPTER: an object with the methods below.  The adapter in use
is named by the environment variable ACC_SUT (a module name in this directory, e.g. `sut_e25a297`; the module must define
`ADAPTER`).  With none named, `DefaultAdapter` is used: every method raises SutNotImplemented, and the runner reports
the test as NOT IMPLEMENTED (distinct from PASS, FAIL and ERROR).

An implementer provides a module `sut_<name>.py` with ADAPTER = a subclass of Adapter that overrides what it binds.
Anything not overridden stays NOT IMPLEMENTED, so a partial binding is reported honestly.

----------------------------------------------------------------------------------------------------------- section 3
judge_run(RunInput) -> RunJudgement
    The consistency rule for ONE run at checkpoint N, as the courier applies it (3.1 to 3.4, K-N-1).  Rules: K-CNT-1..5,
    the nine findings of 3.2, K-1 (order of `evidence` is arbitrary), K-2, K-3 (gate_keys: every key given), K-4 (any
    phase), K-5, K-6, K-7, K-BEL-1..4, 3.4, I-K-1 (bound reports), D-2 to D-14.  The reports recorded after N are in
    `evidence` and MUST be left out by the implementation ("Reports recorded after N are left out", section 3).
judge_unborne_names(NamesInput) -> NamesJudgement
    O-R-1 / D-12 / K-PHASE for the budget: names named in (K, N] that no attempt bears, judged together.
record_judge_runs(RecordRunsInput) -> {aid: frozenset(findings)}
    The record's checker applying section 3 to the reports a RECORD carries (K-REC-1, K-REC-3, K-3: the same rule as the
    courier).  An implementation of check_record MUST fail a record for which this returns any finding.
verify_record(record, keys) -> (ok: bool, failed: list[int])
    The whole record checker (`check_record.verify` at e25a297), for K-REC-2 and earlier-form records.
notice_problems(notice, courier_keys) / receipt_problems(receipt, mailbox_keys, notice) -> list[str]
    Earlier forms (section 11): notices and receipts of forms 1 and 2 MUST go on verifying as they do.

------------------------------------------------------------------------------------------------- sections 6 to 8, 11
start_mailbox(MailboxConfig, clock: TestClock, store_dir: str) -> MailboxHandle
    A mailbox with the given configuration (section 11: every limit and quota as a parameter, small values in tests),
    taking ALL its time from `clock` (TR-CLOCK) and keeping ALL its durable state under `store_dir` (TR-STORE).
    MailboxHandle:
      request(method, path_with_query, body: bytes|None, client: str) -> (status: int, body: bytes)
            The HTTP interface of section 11, with the TLS client name given as `client` (TR-CLIENT: the adapter maps it
            to a client certificate, or the mailbox is driven without TLS by the adapter).
      public_key -> hex of the mailbox's signing key (as GET /pubkey).
      restart()          stop the mailbox process and start it again on the same store and the same clock (no reboot);
                         the test calls clock.reboot() first for a reboot (M-T-2, M-T-3, M-K-5).
      stop() / start()   the mailbox down / up again (C-S-2).
      snapshot() -> opaque, restore(opaque)   copy and roll back the mailbox's whole durable state while it is stopped
                         (models L-10 / I-O-4: CAP-OS or an operator's restore).  Optional.
      corrupt_record(root)   make the mailbox's own record of the budget unreadable (C-1.8).  Optional (CAP-OS).
      remove_evidence(root, id)   delete one stored evidence object from the store (CAP-OS/CAP-OWNER), for E-B-3
                         "begins again if the object is ever absent".  Optional.
      run_maintenance()  run one pass of retirement and orphan removal (E-Q-4, E-Q-5) now.  (TR-MAINT: the
                         specification permits both and says nothing of when they run.)
      source_files() -> [paths]   the implementation's source, for the static half of M-T-1.  Optional.
      close()
codec() -> fixtures.form3.Codec
    The field names of bodies, challenges, receipts, statuses and answers that the specification does not fix (TR-CODEC,
    finding T5).  The default is fixtures.form3.Codec; an implementation that names them otherwise overrides it.

------------------------------------------------------------------------------------------------------ sections 4, 5
start_courier(CourierConfig, witness_url, mailbox_url, clock: TestClock, state_dir) -> CourierHandle
    A courier for the budgets of the config, reading the scripted witness at witness_url and delivering to mailbox_url
    (a test-side proxy in front of the mailbox under test, which logs and can perturb every answer).  Both speak plain
    HTTP on loopback (TR-CLIENT); the courier sends the header X-Acc-Client: <config.client> as its client name.
    CourierHandle:
      read(root) -> dict      perform ONE reading of the budget now (4.1), with its deliveries, and return.
      snapshot_state() -> opaque / restore_state(opaque)   copy, and later put back, the courier's whole durable state
                              (I-E-8: a courier restored from an old copy).
      lose_state(root)        remove the courier's state for the budget (I-E-4: absent).
      restart()               stop and start the courier process on the same state (the test reboots the clock first
                              for "its machine restarted", K-N-3).
      outbox(root) -> [items] the items in the courier's durable outbox for the budget (I-O-1).
      close()
"""
import importlib
import os
from dataclasses import dataclass, field


class SutNotImplemented(Exception):
    """The adapter does not bind this part of the system: the test is NOT IMPLEMENTED, not FAIL."""


# ---------------------------------------------------------------------------------------------------- section 3 types
@dataclass
class RunInput:
    root: str
    aid: str
    n: int                         # the checkpoint's N
    phase: str | None              # the run's phase at N (D-9)
    chain_nonce: str | None        # D-4
    decisions: list                # the per-attempt decisions naming the run, up to N: [{seq, op, kind, code}]
    evidence: list                 # the witness's answer: [{seq, evidence, derived}], in ANY order, may include seq > N
    result: object                 # the stored result (envelope) or None
    gate_keys: list                # the reader's gate keys (P-KEYS)
    intent_seq: int | None = None  # number of the run's ACCEPT_INTENT APPLIED decision, if any (D-14); also derivable from decisions


@dataclass
class RunJudgement:
    findings: frozenset            # of 'K-CONFLICT', 'K-UNKNOWN-VERDICT', 'K-FENCE', 'K-PHASE', 'K-EARLY', 'K-NONCE',
                                   #    'K-DIGEST', 'K-CLAIM', 'K-MISSING'
    outcome: str | None            # 3.4: 'INCONSISTENT', 'PASS', 'FAIL', 'UNKNOWN', 'INVALID', 'UNVERIFIED', 'REFUNDED',
                                   #    'INTERRUPTED', other phases as today; None when only K-MISSING decides
    believed: bool                 # K-BEL-1
    notice: str | None             # the notice called for: 'EQUIVOCATION', an outcome kind of I-ID-1, or None
    notice_after_wait: bool        # True when the notice is called for only after a waiting time (K-N-3)
    bound: tuple = ()              # evidence ids of the bound reports of an EQUIVOCATION notice (I-K-1)
    recorded_pair_id: str | None = None   # O-P-1
    whole: bool = True             # False when K-MISSING holds (3.4 row 2)


@dataclass
class NamesInput:
    root: str
    n: int
    answers: dict                  # name -> the witness's evidence list for that name
    gate_keys: list
    order: list = field(default_factory=list)   # the names in the order the chain first named them


@dataclass
class NamesJudgement:
    findings: frozenset            # {'K-PHASE'} or empty
    notice: str | None             # 'EQUIVOCATION' (one, for the budget, identity with a null name) or None
    bound: tuple = ()              # the evidence id of the earliest such report (O-R-1)


@dataclass
class RecordRunsInput:
    root: str
    audit: list                    # the record's audit rows [{seq, op, kind, code, observation, prev_hash, hash}]
    attempts: list                 # [{aid, phase, nonce, evidence: [{seq, evidence}], result}]
    gate_keys: list


# ---------------------------------------------------------------------------------------------------- configuration
@dataclass
class MailboxConfig:
    writers: list                  # client names that may write (the courier's)
    readers: list                  # client names that may read
    budgets: dict                  # root -> courier public key hex (I-4)
    witness_keys: list
    L: float
    R: float
    TOKENS_MAX: int = 8
    ITEM_MAX: int = 65536
    OBJ_MAX: int = 1 << 20
    EVID_BUDGET_QUOTA: int = 64 << 20
    EVID_GLOBAL_QUOTA: int = 1 << 30
    NOTICE_QUOTA: int = 1 << 24
    OBS_QUOTA: int = 1 << 24
    ALARM_RESERVE: int = 1 << 22
    ALARMS_KEEP: int = 64
    INDEX_QUOTA: int = 1 << 24
    INDEX_RESERVE: int = 1 << 20
    T_ORPHAN: float = 3600.0
    CLOCK_TOLERANCE: float = 5.0


@dataclass
class CourierConfig:
    name: str
    client: str
    courier_key_hex: str           # the courier's private key (the engineer's party)
    budgets: list                  # [{'root', 'provisioning_hash'}]
    witness_keys: list
    gate_keys: list
    mailbox_keys: list
    RUN_ANSWER_MAX: int = 8 << 20
    INLINE_TOTAL_MAX: int = 32 << 10
    NOTICES_PER_RUN_MAX: int = 16
    wait_seconds: float = 900.0    # the waiting time of K-N-3 (UNVERIFIED, NO_OUTCOME)


# ---------------------------------------------------------------------------------------------------- adapters
class Adapter:
    name = 'abstract'

    def _ni(self, what):
        raise SutNotImplemented(f'{self.name}: {what} is not bound')

    # section 3
    def judge_run(self, inp: RunInput) -> RunJudgement:
        self._ni('judge_run')

    def judge_unborne_names(self, inp: NamesInput) -> NamesJudgement:
        self._ni('judge_unborne_names')

    def record_judge_runs(self, inp: RecordRunsInput) -> dict:
        self._ni('record_judge_runs')

    def verify_record(self, record, keys):
        self._ni('verify_record')

    def notice_problems(self, notice, courier_keys):
        self._ni('notice_problems')

    def receipt_problems(self, receipt, mailbox_keys, notice):
        self._ni('receipt_problems')

    # mailbox
    def start_mailbox(self, config: MailboxConfig, clock, store_dir):
        self._ni('start_mailbox')

    def codec(self):
        from fixtures.form3 import Codec
        return Codec()

    # courier
    def start_courier(self, config: CourierConfig, witness_url, mailbox_url, clock, state_dir):
        self._ni('start_courier')


class DefaultAdapter(Adapter):
    name = 'default'


_adapter = None


def get_adapter() -> Adapter:
    global _adapter
    if _adapter is None:
        mod = os.environ.get('ACC_SUT')
        _adapter = importlib.import_module(mod).ADAPTER if mod else DefaultAdapter()
    return _adapter


def set_adapter(a):
    global _adapter
    _adapter = a
