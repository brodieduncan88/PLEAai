"""Reference implementation of the PLEA attempt-budget contract v3 (11 October 2026).

This module follows sections 2 to 9 of the contract. It decides over trusted
facts only (section 1): it does not authenticate evidence, store anything
transactionally, fence sandboxes, issue receipts or operate gates.

Layout
------
vocabulary    modes, phases, labels and decision kinds (sections 3, 4, 5, 9)
facts         AttemptFacts and RootState: immutable value objects that validate
              themselves on construction, so an invalid state cannot be built
              (sections 2, 4, 8)
views         live_view and accepted_view; each counts exactly one view (section 4)
operations    typed operations and the parser for the tuple alphabet (sections 5, 9)
rules         one function per operation, its rules written in the order the
              contract lists them; the first rule that matches decides (section 5)
world         several roots and delegated callers (sections 2, 5.14)
observation   the dictionary of section 7

State is carried as attempt identities with per-attempt facts; every count is
derived from those facts and no aggregate count is ever stored or accepted from
a caller. Every transition returns a new state and never mutates its input.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

__all__ = [
    "InvalidInput", "ContractViolation",
    "Witness", "Business", "Phase", "ReleaseEvidence", "Verdict", "VerdictEvidence", "Kind",
    "AttemptFacts", "RootState", "World", "Decision",
    "LiveView", "AcceptedView", "live_view", "accepted_view", "no_effect_count", "credit",
    "live_charge",
    "initial", "make_root", "root_from_facts",
    "parse_op", "parse_world_op", "apply", "apply_world", "observe",
]


# ============================================================== errors

class InvalidInput(ValueError):
    """Malformed input: rejected, never clamped (section 5)."""


class ContractViolation(RuntimeError):
    """A rule was about to produce an outcome the contract forbids.

    This signals a defect in this module, never a problem with the input.
    Nothing catches it.
    """


# ============================================================== vocabulary

class Witness(Enum):
    ACTIVE = "ACTIVE"
    HELD = "HELD"


class Business(Enum):
    OPEN = "OPEN"
    STOPPING = "STOPPING"
    TERMINALISING = "TERMINALISING"
    TERMINAL = "TERMINAL"


class Phase(Enum):
    RESERVING = "RESERVING"
    RESERVED = "RESERVED"
    TOKEN = "TOKEN"
    INTENT_PENDING = "INTENT_PENDING"
    CONSUMED = "CONSUMED"
    NO_EFFECT = "NO_EFFECT"
    EFFECT = "EFFECT"
    INDETERMINATE = "INDETERMINATE"
    RELEASED = "RELEASED"
    DISCARDED = "DISCARDED"


class ReleaseEvidence(Enum):
    """The fencing evidence label e of RELEASE (5.8)."""
    BOUND_FENCE = "BOUND_FENCE"
    NONE = "NONE"
    WRONG_BINDING = "WRONG_BINDING"


class Verdict(Enum):
    """The verdict v of RECONCILE (5.9)."""
    NO_EFFECT = "NO_EFFECT"
    EFFECT = "EFFECT"
    UNKNOWN = "UNKNOWN"


class VerdictEvidence(Enum):
    """The evidence label e of RECONCILE (5.9)."""
    AUTHORISED = "AUTHORISED"
    NONE = "NONE"
    WRONG_BINDING = "WRONG_BINDING"


class Kind(Enum):
    """The four decision kinds (section 5)."""
    APPLIED = "APPLIED"
    NOOP = "NOOP"
    DUPLICATE = "DUPLICATE"
    DENIED = "DENIED"


P = Phase

# Section 4, per-attempt facts.
NONCE_REQUIRED = frozenset({P.INTENT_PENDING, P.CONSUMED, P.NO_EFFECT, P.EFFECT})
NONCE_OPTIONAL = frozenset({P.INDETERMINATE})  # "keeps the nonce it had, if any"
RECEIPT_ALLOWED = frozenset({P.CONSUMED, P.NO_EFFECT, P.EFFECT, P.INDETERMINATE})

# Section 4, the views table. One phase set per counter.
LIVE_R_PHASES = frozenset({P.RESERVING, P.RESERVED, P.TOKEN})
LIVE_C_PHASES = frozenset({P.INTENT_PENDING, P.CONSUMED, P.NO_EFFECT, P.EFFECT, P.INDETERMINATE})
ACCEPTED_R_PHASES = frozenset({P.RESERVED, P.TOKEN, P.INTENT_PENDING})
ACCEPTED_C_PHASES = frozenset({P.CONSUMED, P.NO_EFFECT, P.EFFECT, P.INDETERMINATE})
N_PHASES = frozenset({P.NO_EFFECT})  # N, the same in both views

# Phase groups named by the operation rules of section 5.
ACCEPTED_CONSUMPTION = frozenset({P.CONSUMED, P.NO_EFFECT, P.EFFECT})  # 5.5/2, 5.6/1, 5.8/4
RECONCILED = frozenset({P.NO_EFFECT, P.EFFECT})  # 5.9/2
TOKEN_OR_LATER = frozenset({P.TOKEN, P.INTENT_PENDING, P.CONSUMED, P.NO_EFFECT, P.EFFECT})  # 5.3/3
# 5.11 TERMINAL/3 (D5) and 5.13/3 (D6) name the same five phases.
UNRESOLVED = frozenset({P.RESERVING, P.RESERVED, P.TOKEN, P.INTENT_PENDING, P.CONSUMED})

_VERDICT_PHASE = {Verdict.NO_EFFECT: P.NO_EFFECT, Verdict.EFFECT: P.EFFECT}


# ============================================================== validation helpers

def _require_identity(value: object, what: str) -> str:
    """Section 2: identities, request keys and nonces are opaque non-empty strings."""
    if not isinstance(value, str) or value == "":
        raise InvalidInput(f"{what} must be a non-empty string, got {value!r}")
    return value


def _require_flag(value: object, what: str) -> bool:
    if type(value) is not bool:
        raise InvalidInput(f"{what} must be a boolean, got {value!r}")
    return value


def _require_count(value: object, what: str) -> int:
    """Section 2: a non-negative integer; booleans and other types are invalid."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InvalidInput(f"{what} must be a non-negative integer (not a boolean), got {value!r}")
    return value


def _label(enum_cls, value: object, what: str):
    """Accept an enum member or its exact name; anything else is an unknown label."""
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str) and value in enum_cls.__members__:
        return enum_cls[value]
    raise InvalidInput(f"unknown {what}: {value!r}")


# ============================================================== facts

@dataclass(frozen=True)
class AttemptFacts:
    """One attempt: its identity, request key, phase and facts (sections 2 and 4).

    Construction validates the per-attempt rules of section 8.
    """

    aid: str
    req: str
    phase: Phase
    nonce: Optional[str] = None
    receipt: bool = False
    crossed: bool = False

    def __post_init__(self) -> None:
        _require_identity(self.aid, "attempt identity")
        _require_identity(self.req, "request key")
        object.__setattr__(self, "phase", _label(Phase, self.phase, "phase"))
        if self.nonce is not None:
            _require_identity(self.nonce, "nonce")
        _require_flag(self.receipt, "receipt")
        _require_flag(self.crossed, "crossed")
        phase = self.phase
        if phase in NONCE_REQUIRED and self.nonce is None:
            raise InvalidInput(f"attempt {self.aid!r}: {phase.value} must hold a nonce")
        if phase not in NONCE_REQUIRED | NONCE_OPTIONAL and self.nonce is not None:
            raise InvalidInput(f"attempt {self.aid!r}: {phase.value} holds no nonce")
        if self.receipt and phase not in RECEIPT_ALLOWED:
            raise InvalidInput(f"attempt {self.aid!r}: no receipt is possible in {phase.value}")
        if self.crossed and not self.receipt:
            raise InvalidInput(f"attempt {self.aid!r}: crossed implies receipt")


def _distinct(values, what: str) -> None:
    seen = set()
    for value in values:
        if value in seen:
            raise InvalidInput(f"{what} {value!r} is bound to two attempts")
        seen.add(value)


@dataclass(frozen=True)
class RootState:
    """The state of one root run (sections 2 to 4).

    The field order matches ``Root(k, m, witness, business, attempts,
    reregistered)`` of section 8. Attempts are kept sorted by identity, so two
    states with the same facts compare equal.
    """

    k: int
    m: int
    witness: Witness = Witness.ACTIVE
    business: Business = Business.OPEN
    attempts: tuple = ()
    reregistered: bool = False

    def __post_init__(self) -> None:
        _require_count(self.k, "budget k")
        _require_count(self.m, "replacement allowance m")
        object.__setattr__(self, "witness", _label(Witness, self.witness, "witness mode"))
        object.__setattr__(self, "business", _label(Business, self.business, "business state"))
        _require_flag(self.reregistered, "reregistered")
        try:
            attempts = tuple(self.attempts)
        except TypeError:
            raise InvalidInput(f"attempts must be an iterable of attempts, got {self.attempts!r}") from None
        for attempt in attempts:
            if not isinstance(attempt, AttemptFacts):
                raise InvalidInput(f"not an attempt: {attempt!r}")
        _distinct((a.aid for a in attempts), "attempt identity")
        _distinct((a.req for a in attempts), "request key")
        _distinct((a.nonce for a in attempts if a.nonce is not None), "nonce")
        if self.reregistered and self.business is Business.OPEN:
            raise InvalidInput("a re-registered run is never OPEN")
        object.__setattr__(self, "attempts", tuple(sorted(attempts, key=lambda a: a.aid)))

    # ---- lookups

    def attempt(self, aid: str) -> Optional[AttemptFacts]:
        for a in self.attempts:
            if a.aid == aid:
                return a
        return None

    def attempt_bound_to_request(self, req: str) -> Optional[AttemptFacts]:
        for a in self.attempts:
            if a.req == req:
                return a
        return None

    def nonce_holder(self, nonce: str) -> Optional[AttemptFacts]:
        for a in self.attempts:
            if a.nonce == nonce:
                return a
        return None

    def any_attempt_in(self, phases: frozenset) -> bool:
        return any(a.phase in phases for a in self.attempts)

    @property
    def active_and_open(self) -> bool:
        return self.witness is Witness.ACTIVE and self.business is Business.OPEN

    # ---- derived states (never mutate self)

    def with_attempt(self, attempt: AttemptFacts) -> "RootState":
        others = tuple(a for a in self.attempts if a.aid != attempt.aid)
        return dataclasses.replace(self, attempts=others + (attempt,))


def initial(k: int, m: int) -> RootState:
    """A new root: ACTIVE, OPEN, no attempts (section 8)."""
    return RootState(k, m)


def make_root(k, m, witness="ACTIVE", business="OPEN", attempts=(), reregistered=False) -> RootState:
    """Build a root state from facts, validating it (section 8, Root)."""
    return RootState(k, m, witness, business, attempts, reregistered)


_MODE_KEYWORDS = frozenset({"witness", "business", "reregistered"})


def root_from_facts(k, m, attempts=(), claimed_no_effect=None, **modes) -> RootState:
    """As make_root, and also reject a claimed N that the attempts do not justify (section 8)."""
    unknown = set(modes) - _MODE_KEYWORDS
    if unknown:
        raise InvalidInput(f"unknown mode keyword(s): {sorted(unknown)}")
    state = RootState(k, m, attempts=attempts, **modes)
    if claimed_no_effect is not None:
        _require_count(claimed_no_effect, "claimed N")
        actual = no_effect_count(state)
        if claimed_no_effect != actual:
            raise InvalidInput(
                f"claimed N = {claimed_no_effect} differs from the {actual} distinct NO_EFFECT attempt(s)")
    return state


# ============================================================== views (section 4)

@dataclass(frozen=True)
class LiveView:
    """The live local view: pending local work is charged at once."""
    R: int
    C: int
    N: int


@dataclass(frozen=True)
class AcceptedView:
    """The accepted view: what the witness has accepted."""
    R: int
    C: int
    N: int


def _count(state: RootState, phases: frozenset) -> int:
    return sum(1 for a in state.attempts if a.phase in phases)


def no_effect_count(state: RootState) -> int:
    """N: distinct NO_EFFECT attempts. The table gives it the same definition in both views."""
    return _count(state, N_PHASES)


def live_view(state: RootState) -> LiveView:
    return LiveView(R=_count(state, LIVE_R_PHASES), C=_count(state, LIVE_C_PHASES),
                    N=no_effect_count(state))


def accepted_view(state: RootState) -> AcceptedView:
    return AcceptedView(R=_count(state, ACCEPTED_R_PHASES), C=_count(state, ACCEPTED_C_PHASES),
                        N=no_effect_count(state))


def credit(state: RootState) -> int:
    """credit = min(N, m): bounded credit, never a decrement of C."""
    return min(no_effect_count(state), state.m)


def live_charge(state: RootState) -> int:
    """live R + live C - credit, the quantity admission compares with k. Live view only."""
    view = live_view(state)
    return view.R + view.C - min(view.N, state.m)


# ============================================================== decisions

@dataclass(frozen=True)
class Decision:
    kind: Kind
    code: str


def _denied(state, code: str):
    return Decision(Kind.DENIED, code), state


def _duplicate(state, code: str):
    return Decision(Kind.DUPLICATE, code), state


def _noop(state, code: str):
    return Decision(Kind.NOOP, code), state


def _applied(new_state, code: str):
    return Decision(Kind.APPLIED, code), new_state


def _expect_phase(attempt: AttemptFacts, phases: frozenset, rule: str) -> None:
    """Check a claim the contract makes about the phase that reaches an 'Otherwise' rule."""
    if attempt.phase not in phases:
        raise ContractViolation(f"{rule}: reached with {attempt.aid!r} in {attempt.phase.value}")


# ============================================================== operations (sections 5, 9)

@dataclass(frozen=True)
class _NamesAttempt:
    """Base of every operation that names an attempt (used by evaluation step 2)."""
    aid: str

    def __post_init__(self) -> None:
        _require_identity(self.aid, "attempt identity")


@dataclass(frozen=True)
class Reserve(_NamesAttempt):
    req: str

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_identity(self.req, "request key")


@dataclass(frozen=True)
class AcceptReservation(_NamesAttempt):
    pass


@dataclass(frozen=True)
class Token(_NamesAttempt):
    pass


@dataclass(frozen=True)
class Start(_NamesAttempt):
    nonce: str

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_identity(self.nonce, "nonce")


@dataclass(frozen=True)
class AcceptIntent(_NamesAttempt):
    pass


@dataclass(frozen=True)
class Receipt(_NamesAttempt):
    pass


@dataclass(frozen=True)
class Cross(_NamesAttempt):
    pass


@dataclass(frozen=True)
class Release(_NamesAttempt):
    evidence: ReleaseEvidence

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "evidence",
                           _label(ReleaseEvidence, self.evidence, "RELEASE evidence label"))


@dataclass(frozen=True)
class Reconcile(_NamesAttempt):
    verdict: Verdict
    evidence: VerdictEvidence

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "verdict", _label(Verdict, self.verdict, "verdict label"))
        object.__setattr__(self, "evidence",
                           _label(VerdictEvidence, self.evidence, "RECONCILE evidence label"))


@dataclass(frozen=True)
class Timeout(_NamesAttempt):
    pass


@dataclass(frozen=True)
class MissingReceipt(_NamesAttempt):
    pass


@dataclass(frozen=True)
class Crash:
    pass


@dataclass(frozen=True)
class Hold:
    pass


@dataclass(frozen=True)
class Stop:
    pass


@dataclass(frozen=True)
class Terminalise:
    pass


@dataclass(frozen=True)
class Terminal:
    pass


@dataclass(frozen=True)
class Recover:
    approved: bool
    complete: bool

    def __post_init__(self) -> None:
        _require_flag(self.approved, "RECOVER approved")
        _require_flag(self.complete, "RECOVER complete")


@dataclass(frozen=True)
class Reregister:
    pass


SINGLE_ROOT_ALPHABET = {
    "RESERVE": Reserve,
    "ACCEPT_RESERVATION": AcceptReservation,
    "TOKEN": Token,
    "START": Start,
    "ACCEPT_INTENT": AcceptIntent,
    "RECEIPT": Receipt,
    "CROSS": Cross,
    "RELEASE": Release,
    "RECONCILE": Reconcile,
    "TIMEOUT": Timeout,
    "MISSING_RECEIPT": MissingReceipt,
    "CRASH": Crash,
    "HOLD": Hold,
    "STOP": Stop,
    "TERMINALISE": Terminalise,
    "TERMINAL": Terminal,
    "RECOVER": Recover,
    "REREGISTER": Reregister,
}
_SINGLE_ROOT_TYPES = tuple(SINGLE_ROOT_ALPHABET.values())


@dataclass(frozen=True)
class NewRoot:
    root: str
    k: object  # validated by NEW_ROOT rule 2, after the existence check of rule 1
    m: object
    caller: str

    def __post_init__(self) -> None:
        _require_identity(self.root, "root identity")
        _require_identity(self.caller, "caller identity")


@dataclass(frozen=True)
class Delegate:
    parent: str
    caller: str

    def __post_init__(self) -> None:
        _require_identity(self.parent, "caller identity")
        _require_identity(self.caller, "caller identity")


@dataclass(frozen=True)
class Call:
    caller: str
    op: object  # a single-root operation; a tuple is parsed (and so validated) here

    def __post_init__(self) -> None:
        _require_identity(self.caller, "caller identity")
        if not isinstance(self.op, _SINGLE_ROOT_TYPES):
            object.__setattr__(self, "op", parse_op(self.op))


WORLD_ALPHABET = {"NEW_ROOT": NewRoot, "DELEGATE": Delegate, "CALL": Call}


def _parse(alphabet: dict, raw: object, what: str):
    if not isinstance(raw, tuple) or not raw or not isinstance(raw[0], str):
        raise InvalidInput(f"{what} must be a tuple that starts with an operation name, got {raw!r}")
    name, args = raw[0], raw[1:]
    cls = alphabet.get(name)
    if cls is None:
        raise InvalidInput(f"unknown {what}: {name!r}")
    arity = len(dataclasses.fields(cls))
    if len(args) != arity:
        raise InvalidInput(f"{name} takes {arity} argument(s), got {len(args)}")
    return cls(*args)


def parse_op(raw: object):
    """Evaluation step 1 for a single-root operation tuple of section 9."""
    return _parse(SINGLE_ROOT_ALPHABET, raw, "single-root operation")


def parse_world_op(raw: object):
    """Evaluation step 1 for a world operation tuple of section 9."""
    return _parse(WORLD_ALPHABET, raw, "world operation")


# ============================================================== rules (section 5)
# Each function lists its operation's rules in the contract's order. The first
# rule that matches returns. Codes are explanatory only.

def _reserve(s: RootState, op: Reserve):  # 5.1
    a = s.attempt(op.aid)
    if a is not None and a.phase is P.DISCARDED:
        return _denied(s, "RESERVE_DISCARDED_ATTEMPT")                 # 1 (D7)
    if a is not None and a.req == op.req:
        return _duplicate(s, "RESERVE_RETRY")                          # 2
    if a is not None:
        return _denied(s, "ATTEMPT_BOUND_TO_OTHER_REQUEST")            # 3
    if s.attempt_bound_to_request(op.req) is not None:
        return _denied(s, "REQUEST_BOUND_TO_OTHER_ATTEMPT")            # 4 (also D7)
    if not s.active_and_open:
        return _denied(s, "NOT_ACTIVE_AND_OPEN")                       # 5
    if live_charge(s) >= s.k:
        return _denied(s, "BUDGET_EXHAUSTED")                          # 6
    return _applied(s.with_attempt(AttemptFacts(op.aid, op.req, P.RESERVING)),
                    "RESERVATION_COMMITTED")                           # 7


def _accept_reservation(s: RootState, op: AcceptReservation):  # 5.2
    a = s.attempt(op.aid)
    if a is None or a.phase is P.DISCARDED:
        return _denied(s, "UNKNOWN_OR_DISCARDED_ATTEMPT")              # 1
    if a.phase is not P.RESERVING:
        return _duplicate(s, "RESERVATION_ALREADY_ACCEPTED")           # 2
    if s.witness is Witness.HELD:
        return _denied(s, "WITNESS_HELD")                              # 3
    return _applied(s.with_attempt(dataclasses.replace(a, phase=P.RESERVED)),
                    "RESERVATION_ACCEPTED")                            # 4


def _token(s: RootState, op: Token):  # 5.3
    a = s.attempt(op.aid)
    if a is None or a.phase in (P.RELEASED, P.DISCARDED):
        return _denied(s, "UNKNOWN_RELEASED_OR_DISCARDED_ATTEMPT")     # 1
    if a.phase is P.RESERVING:
        return _denied(s, "RESERVATION_NOT_ACCEPTED")                  # 2
    if a.phase in TOKEN_OR_LATER:
        return _duplicate(s, "TOKEN_ALREADY_RELEASED")                 # 3
    if not s.active_and_open:
        return _denied(s, "NOT_ACTIVE_AND_OPEN")                       # 4 (D2)
    _expect_phase(a, frozenset({P.RESERVED}), "5.3/5")
    return _applied(s.with_attempt(dataclasses.replace(a, phase=P.TOKEN)),
                    "TOKEN_RELEASED")                                  # 5


def _start(s: RootState, op: Start):  # 5.4
    a = s.attempt(op.aid)
    if a is None:
        return _denied(s, "UNKNOWN_ATTEMPT")                           # 1
    if a.nonce is not None:                                            # 2
        if a.nonce == op.nonce:
            return _duplicate(s, "START_RETRY")
        return _denied(s, "ATTEMPT_HOLDS_OTHER_NONCE")
    if s.nonce_holder(op.nonce) is not None:
        return _denied(s, "NONCE_HELD_BY_OTHER_ATTEMPT")               # 3
    if not s.active_and_open:
        return _denied(s, "NOT_ACTIVE_AND_OPEN")                       # 4
    if a.phase is not P.TOKEN:
        return _denied(s, "TOKEN_NOT_RELEASED")                        # 5
    return _applied(s.with_attempt(dataclasses.replace(a, phase=P.INTENT_PENDING, nonce=op.nonce)),
                    "INTENT_COMMITTED_LOCALLY")                        # 6


def _accept_intent(s: RootState, op: AcceptIntent):  # 5.5
    a = s.attempt(op.aid)
    if a is None:
        return _denied(s, "UNKNOWN_ATTEMPT")                           # 1
    if a.phase in ACCEPTED_CONSUMPTION:
        return _duplicate(s, "INTENT_ALREADY_ACCEPTED")                # 2
    if a.phase is not P.INTENT_PENDING:
        return _denied(s, "NO_PENDING_INTENT")                         # 3
    if s.witness is Witness.HELD:
        return _denied(s, "WITNESS_HELD")                              # 4
    return _applied(s.with_attempt(dataclasses.replace(a, phase=P.CONSUMED)),
                    "INTENT_ACCEPTED")                                 # 5


def _receipt(s: RootState, op: Receipt):  # 5.6
    a = s.attempt(op.aid)
    if a is None or a.phase not in ACCEPTED_CONSUMPTION:
        return _denied(s, "NO_ACCEPTED_INTENT")                        # 1
    if a.receipt:
        return _duplicate(s, "RECEIPT_ALREADY_DELIVERED")              # 2
    return _applied(s.with_attempt(dataclasses.replace(a, receipt=True)),
                    "RECEIPT_RECORDED")                                # 3 (any mode)


def _cross(s: RootState, op: Cross):  # 5.7
    a = s.attempt(op.aid)
    if a is None or a.phase is not P.CONSUMED:
        return _denied(s, "NOT_CONSUMED")                              # 1
    if a.crossed:
        return _denied(s, "ALREADY_CROSSED")                           # 2 (one-shot)
    if not a.receipt:
        return _denied(s, "RECEIPT_NOT_DELIVERED")                     # 3
    if not s.active_and_open:
        return _denied(s, "NOT_ACTIVE_AND_OPEN")                       # 4
    return _applied(s.with_attempt(dataclasses.replace(a, crossed=True)),
                    "CROSSED")                                         # 5


def _release(s: RootState, op: Release):  # 5.8
    a = s.attempt(op.aid)
    if a is None or a.phase is P.DISCARDED:
        return _denied(s, "UNKNOWN_OR_DISCARDED_ATTEMPT")              # 1
    if a.phase is P.RELEASED:
        return _duplicate(s, "ALREADY_RELEASED")                       # 2 (whatever e is)
    if a.phase is P.INTENT_PENDING:
        return _denied(s, "PENDING_INTENT_NEEDS_RECOVERY")             # 3 (AC2)
    if a.phase in ACCEPTED_CONSUMPTION:
        return _denied(s, "CONSUMPTION_IS_FINAL")                      # 4
    if a.phase is P.RESERVING:
        return _denied(s, "RESERVATION_NOT_ACCEPTED")                  # 5 (D3)
    if op.evidence is not ReleaseEvidence.BOUND_FENCE:
        return _denied(s, "NO_BOUND_FENCING_EVIDENCE")                 # 6
    if s.witness is Witness.HELD:
        return _denied(s, "WITNESS_HELD")                              # 7 (D4)
    _expect_phase(a, frozenset({P.RESERVED, P.TOKEN}), "5.8/8")
    return _applied(s.with_attempt(dataclasses.replace(a, phase=P.RELEASED)),
                    "RESERVATION_RELEASED")                            # 8 (any business state)


def _reconcile(s: RootState, op: Reconcile):  # 5.9
    a = s.attempt(op.aid)
    if a is None:
        return _denied(s, "UNKNOWN_ATTEMPT")                           # 1
    if a.phase in RECONCILED:                                          # 2 (verdicts are final)
        if _VERDICT_PHASE.get(op.verdict) is a.phase and op.evidence is VerdictEvidence.AUTHORISED:
            return _duplicate(s, "VERDICT_RETRY")
        return _denied(s, "VERDICT_IS_FINAL")
    if a.phase is not P.CONSUMED:
        return _denied(s, "NOT_CONSUMED")                              # 3
    if op.evidence is not VerdictEvidence.AUTHORISED:
        return _denied(s, "VERDICT_NOT_AUTHORISED")                    # 4 (D8)
    if s.witness is Witness.HELD:
        return _denied(s, "WITNESS_HELD")                              # 5 (D4)
    if op.verdict is Verdict.UNKNOWN:
        return _noop(s, "VERDICT_UNKNOWN_STAYS_CHARGED")               # 6
    return _applied(s.with_attempt(dataclasses.replace(a, phase=_VERDICT_PHASE[op.verdict])),
                    "VERDICT_RECORDED")                                # 7 (receipt, crossed kept)


def _no_refund_fact(s: RootState, op):  # 5.10, TIMEOUT and MISSING_RECEIPT
    if s.attempt(op.aid) is None:
        return _denied(s, "UNKNOWN_ATTEMPT")                           # 1
    return _noop(s, "NEVER_REFUNDS")                                   # 2


def _crash(s: RootState, op: Crash):  # 5.10/3
    return _noop(s, "CRASH_NEVER_REFUNDS")


def _hold(s: RootState, op: Hold):  # 5.11 HOLD
    if s.witness is Witness.HELD:
        return _denied(s, "ALREADY_HELD")                              # 1
    return _applied(dataclasses.replace(s, witness=Witness.HELD), "HELD")  # 2


def _stop(s: RootState, op: Stop):  # 5.11 STOP (BREAK_GLASS)
    if s.business is not Business.OPEN:
        return _denied(s, "NOT_OPEN")                                  # 1
    return _applied(dataclasses.replace(s, business=Business.STOPPING),
                    "STOPPING")                                        # 2 (witness unchanged, AC4)


def _terminalise(s: RootState, op: Terminalise):  # 5.11 TERMINALISE
    if s.business is not Business.STOPPING:
        return _denied(s, "NOT_STOPPING")                              # 1
    if s.witness is Witness.HELD:
        return _denied(s, "WITNESS_HELD")                              # 2
    return _applied(dataclasses.replace(s, business=Business.TERMINALISING), "TERMINALISING")  # 3


def _terminal(s: RootState, op: Terminal):  # 5.11 TERMINAL
    if s.business is not Business.TERMINALISING:
        return _denied(s, "NOT_TERMINALISING")                         # 1
    if s.witness is Witness.HELD:
        return _denied(s, "WITNESS_HELD")                              # 2
    if s.any_attempt_in(UNRESOLVED):
        return _denied(s, "UNRESOLVED_ATTEMPTS")                       # 3 (D5)
    return _applied(dataclasses.replace(s, business=Business.TERMINAL), "TERMINAL")  # 4


def _recovery_view(a: AttemptFacts) -> AttemptFacts:
    """5.12/3: the verified reconstruction of one attempt from the accepted chain."""
    if a.phase is P.RESERVING:   # proven never accepted
        return dataclasses.replace(a, phase=P.DISCARDED)
    if a.phase is P.INTENT_PENDING:  # the chain holds its reservation and token, not its intent
        return dataclasses.replace(a, phase=P.TOKEN, nonce=None)
    return a


def _recover(s: RootState, op: Recover):  # 5.12
    if s.witness is not Witness.HELD:
        return _denied(s, "NOT_HELD")                                  # 1
    if not op.approved:
        return _denied(s, "NOT_APPROVED")                              # 2
    recovered = dataclasses.replace(                                   # 3
        s,
        attempts=tuple(_recovery_view(a) for a in s.attempts),
        witness=Witness.ACTIVE if op.complete else Witness.HELD,
    )
    if recovered == s:
        return _noop(s, "NOTHING_TO_RECOVER")                          # 4
    return _applied(recovered, "RECOVERED" if op.complete else "RECOVERED_STILL_HELD")


def _reregister(s: RootState, op: Reregister):  # 5.13
    if s.business is Business.TERMINAL:
        return _denied(s, "TERMINAL")                                  # 1
    if s.reregistered:
        return _denied(s, "ALREADY_REREGISTERED")                      # 2
    attempts = tuple(                                                  # 3 (D6)
        dataclasses.replace(a, phase=P.INDETERMINATE) if a.phase in UNRESOLVED else a
        for a in s.attempts
    )
    return _applied(dataclasses.replace(s, attempts=attempts, witness=Witness.ACTIVE,
                                        business=Business.STOPPING, reregistered=True),
                    "REREGISTERED_REDUCED")


_RULES: dict[type, Callable] = {
    Reserve: _reserve,
    AcceptReservation: _accept_reservation,
    Token: _token,
    Start: _start,
    AcceptIntent: _accept_intent,
    Receipt: _receipt,
    Cross: _cross,
    Release: _release,
    Reconcile: _reconcile,
    Timeout: _no_refund_fact,
    MissingReceipt: _no_refund_fact,
    Crash: _crash,
    Hold: _hold,
    Stop: _stop,
    Terminalise: _terminalise,
    Terminal: _terminal,
    Recover: _recover,
    Reregister: _reregister,
}


def apply(state: RootState, op) -> tuple[Decision, RootState]:
    """Decide one single-root operation (section 5). Returns (decision, new state).

    ``op`` is an operation object; use ``parse_op`` for the tuples of section 9.
    The input state is never modified.
    """
    # Step 1: validation. Operation objects validate their labels when built.
    if not isinstance(state, RootState):
        raise InvalidInput(f"not a root state: {state!r}")
    if not isinstance(op, _SINGLE_ROOT_TYPES):
        raise InvalidInput(f"not a single-root operation: {op!r}")

    # Step 2 (D9): an INDETERMINATE attempt is frozen.
    if isinstance(op, _NamesAttempt):
        named = state.attempt(op.aid)
        if named is not None and named.phase is P.INDETERMINATE:
            if isinstance(op, (Timeout, MissingReceipt)):
                return _noop(state, "INDETERMINATE_NEVER_REFUNDS")
            return _denied(state, "INDETERMINATE_IS_FROZEN")

    # Step 3: the operation's own rules.
    decision, new_state = _RULES[type(op)](state, op)

    # T8 guard: only APPLIED changes the state, and APPLIED always does.
    if decision.kind is Kind.APPLIED:
        if new_state == state:
            raise ContractViolation(f"{op!r} was APPLIED without changing the state")
    elif new_state is not state:
        raise ContractViolation(f"{op!r} was {decision.kind.value} but changed the state")
    return decision, new_state


# ============================================================== world (sections 2, 5.14)

@dataclass(frozen=True)
class World:
    """Roots and the callers bound to them. Immutable; ``World()`` is the empty world."""

    roots: tuple = ()    # ((root identity, RootState), ...), sorted by root identity
    callers: tuple = ()  # ((caller identity, root identity), ...), sorted by caller identity

    def __post_init__(self) -> None:
        roots, callers = tuple(self.roots), tuple(self.callers)
        for rid, state in roots:
            _require_identity(rid, "root identity")
            if not isinstance(state, RootState):
                raise InvalidInput(f"root {rid!r} has no root state")
        root_ids = [rid for rid, _ in roots]
        _distinct_world(root_ids, "root")
        for cid, rid in callers:
            _require_identity(cid, "caller identity")
            if rid not in root_ids:
                raise InvalidInput(f"caller {cid!r} is bound to unknown root {rid!r}")
        _distinct_world([cid for cid, _ in callers], "caller")
        object.__setattr__(self, "roots", tuple(sorted(roots, key=lambda entry: entry[0])))
        object.__setattr__(self, "callers", tuple(sorted(callers, key=lambda entry: entry[0])))

    def root(self, rid: str) -> Optional[RootState]:
        for r, state in self.roots:
            if r == rid:
                return state
        return None

    def root_of(self, caller: str) -> Optional[str]:
        for c, rid in self.callers:
            if c == caller:
                return rid
        return None

    def with_root(self, rid: str, state: RootState) -> "World":
        others = tuple(entry for entry in self.roots if entry[0] != rid)
        return dataclasses.replace(self, roots=others + ((rid, state),))

    def with_caller(self, caller: str, rid: str) -> "World":
        return dataclasses.replace(self, callers=self.callers + ((caller, rid),))


def _distinct_world(ids, what: str) -> None:
    if len(set(ids)) != len(ids):
        raise InvalidInput(f"duplicate {what} identity")


def _new_root(w: World, op: NewRoot):  # 5.14 NEW_ROOT
    if w.root(op.root) is not None or w.root_of(op.caller) is not None:
        return _denied(w, "ROOT_OR_CALLER_EXISTS")                     # 1
    state = RootState(op.k, op.m)                                      # 2: InvalidInput on bad k, m
    return _applied(w.with_root(op.root, state).with_caller(op.caller, op.root),
                    "ROOT_CREATED")                                    # 3


def _delegate(w: World, op: Delegate):  # 5.14 DELEGATE
    rid = w.root_of(op.parent)
    if rid is None:
        return _denied(w, "UNKNOWN_PARENT_CALLER")                     # 1
    if w.root_of(op.caller) is not None:
        return _denied(w, "CALLER_ALREADY_BOUND")                      # 1
    return _applied(w.with_caller(op.caller, rid), "CALLER_DELEGATED")  # 2: no capacity created


def _call(w: World, op: Call):  # 5.14 CALL
    rid = w.root_of(op.caller)
    if rid is None:
        return _denied(w, "UNKNOWN_CALLER")                            # 1
    decision, new_state = apply(w.root(rid), op.op)                    # 2
    if decision.kind is Kind.APPLIED:
        return decision, w.with_root(rid, new_state)
    return decision, w


_WORLD_RULES: dict[type, Callable] = {NewRoot: _new_root, Delegate: _delegate, Call: _call}


def apply_world(world: World, op) -> tuple[Decision, World]:
    """Decide one world operation (5.14). Returns (decision, new world); the input is unchanged."""
    if not isinstance(world, World):
        raise InvalidInput(f"not a world: {world!r}")
    rule = _WORLD_RULES.get(type(op))
    if rule is None:
        raise InvalidInput(f"not a world operation: {op!r}")
    return rule(world, op)


# ============================================================== observation (section 7)

def observe(state: RootState) -> dict:
    """The observation dictionary of section 7, with plain strings for modes and phases."""
    if not isinstance(state, RootState):
        raise InvalidInput(f"not a root state: {state!r}")
    live = live_view(state)
    accepted = accepted_view(state)
    return {
        "k": state.k,
        "m": state.m,
        "witness": state.witness.value,
        "business": state.business.value,
        "reregistered": state.reregistered,
        "live": (live.R, live.C, live.N),
        "accepted": (accepted.R, accepted.C, accepted.N),
        "credit": credit(state),
        "attempts": sorted(
            (a.aid, a.req, a.phase.value, a.nonce, a.receipt, a.crossed) for a in state.attempts
        ),
    }
