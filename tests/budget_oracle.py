"""Independent oracle for the PLEA root-run attempt budget.

Written from attempt-budget contract v2 (5 Oct 2026) and rev 2.3 parts 2, 4, 5, 6, 7 and 12, without seeing any
reference implementation.  The vocabulary is frozen in ALPHABET.md.  Amendment 2 (11 Oct 2026) implements attempt-budget
contract v3, which now holds the normative operation semantics: decision D2 (token release only in ACTIVE and OPEN)
and label validation before the INDETERMINATE rule, as v3 section 5 orders it.  Amendment 3 (11 Oct 2026) implements
contract v3.1: the complete list of malformed input, checked before any rule (E1, E10; `validate`, `validate_world`),
and root_from_facts' keyword check (E4).  It was written after the v3 malformed-input differential and after reading the
independent reference's input parser, which is where these readings were first written down; no accounting rule
changed.  Standard library only; every function is pure
and returns new immutable values.  The oracle decides over trusted facts: it does not authenticate evidence, store
anything transactionally, fence sandboxes, issue receipts or operate gates.
"""
from dataclasses import dataclass, replace
from typing import NamedTuple, Optional

WITNESS = ('ACTIVE', 'HELD')
BUSINESS = ('OPEN', 'STOPPING', 'TERMINALISING', 'TERMINAL')
RESERVATION_PHASES = ('RESERVING', 'RESERVED', 'TOKEN')
CHARGED_PHASES = ('INTENT_PENDING', 'CONSUMED', 'NO_EFFECT', 'EFFECT', 'INDETERMINATE')
ACCEPTED_R = ('RESERVED', 'TOKEN', 'INTENT_PENDING')
ACCEPTED_C = ('CONSUMED', 'NO_EFFECT', 'EFFECT', 'INDETERMINATE')
PHASES = RESERVATION_PHASES + CHARGED_PHASES + ('RELEASED', 'DISCARDED')
NONCE_PHASES = ('INTENT_PENDING', 'CONSUMED', 'NO_EFFECT', 'EFFECT')      # must hold a nonce (INDETERMINATE may)
RECEIPT_PHASES = ('CONSUMED', 'NO_EFFECT', 'EFFECT', 'INDETERMINATE')
RELEASE_EVIDENCE = ('BOUND_FENCE', 'NONE', 'WRONG_BINDING')
RECONCILE_EVIDENCE = ('AUTHORISED', 'NONE', 'WRONG_BINDING')
VERDICTS = ('NO_EFFECT', 'EFFECT', 'UNKNOWN')


class InvalidInput(ValueError):
    """B18: corrupt or impossible inputs are rejected, never clamped."""


class Decision(NamedTuple):
    kind: str          # APPLIED | NOOP | DUPLICATE | DENIED
    code: str


def _nat(x, name):
    if type(x) is not int or x < 0:
        raise InvalidInput(f'{name} must be a non-negative integer, got {x!r}')


@dataclass(frozen=True)
class Attempt:
    aid: str
    req: str
    phase: str
    nonce: Optional[str] = None
    receipt: bool = False
    crossed: bool = False

    def __post_init__(self):
        if not (isinstance(self.aid, str) and self.aid and isinstance(self.req, str) and self.req):
            raise InvalidInput('attempt and request identities must be non-empty strings')
        if self.phase not in PHASES:
            raise InvalidInput(f'unknown phase {self.phase!r}')
        if self.phase in NONCE_PHASES and not (isinstance(self.nonce, str) and self.nonce):
            raise InvalidInput(f'{self.phase} needs a nonce')
        if self.phase not in NONCE_PHASES + ('INDETERMINATE',) and self.nonce is not None:
            raise InvalidInput(f'{self.phase} cannot hold a nonce')
        if self.receipt and self.phase not in RECEIPT_PHASES:
            raise InvalidInput(f'{self.phase} cannot have a covering receipt')
        if type(self.receipt) is not bool or type(self.crossed) is not bool:
            raise InvalidInput('receipt and crossed are booleans')
        if self.crossed and not self.receipt:
            raise InvalidInput('an attempt cannot cross without its covering receipt')


@dataclass(frozen=True)
class Root:
    k: int
    m: int
    witness: str = 'ACTIVE'
    business: str = 'OPEN'
    attempts: tuple = ()
    reregistered: bool = False

    def __post_init__(self):
        _nat(self.k, 'budget k'); _nat(self.m, 'replacement allowance m')
        if self.witness not in WITNESS or self.business not in BUSINESS:
            raise InvalidInput('unknown witness or business mode')
        if type(self.reregistered) is not bool or (self.reregistered and self.business == 'OPEN'):
            raise InvalidInput('a re-registered run cannot be OPEN')
        if not all(isinstance(a, Attempt) for a in self.attempts):
            raise InvalidInput('attempts must be Attempt records')
        for field in ('aid', 'req'):
            values = [getattr(a, field) for a in self.attempts]
            if len(values) != len(set(values)):
                raise InvalidInput(f'duplicate {field} identities with conflicting records')
        nonces = [a.nonce for a in self.attempts if a.nonce is not None]
        if len(nonces) != len(set(nonces)):
            raise InvalidInput('one nonce bound to two attempts')


def root_from_facts(k, m, attempts=(), claimed_no_effect=None, **modes):
    """Constructor for callers that also supply an aggregate N: it must equal the distinct eligible attempts."""
    unknown = set(modes) - {'witness', 'business', 'reregistered'}
    if unknown:
        raise InvalidInput(f'unknown mode keyword(s) {sorted(unknown)}')                  # v3.1 E4
    root = Root(k, m, attempts=tuple(attempts), **modes)
    if claimed_no_effect is not None:
        _nat(claimed_no_effect, 'claimed N')
        if claimed_no_effect != counts(root)[2]:
            raise InvalidInput('N is not justified by distinct eligible NO_EFFECT attempts')
    return root


def counts(root, view='live'):
    """(R, C, N) in the live local view or the accepted view.  N counts distinct NO_EFFECT attempts."""
    if view == 'live':
        r = sum(a.phase in RESERVATION_PHASES for a in root.attempts)
        c = sum(a.phase in CHARGED_PHASES for a in root.attempts)
    elif view == 'accepted':
        r = sum(a.phase in ACCEPTED_R for a in root.attempts)
        c = sum(a.phase in ACCEPTED_C for a in root.attempts)
    else:
        raise InvalidInput(f'unknown view {view!r}')
    n = sum(a.phase == 'NO_EFFECT' for a in root.attempts)
    return r, c, n


def credit(root):
    return min(counts(root)[2], root.m)


def admits(root):
    """The admission rule: witness ACTIVE, business OPEN and R + C - min(N, m) < k in the live view."""
    r, c, _ = counts(root)
    return root.witness == 'ACTIVE' and root.business == 'OPEN' and r + c - credit(root) < root.k


def observe(root):
    """Implementation-neutral observation used to compare another implementation with this oracle."""
    return {'k': root.k, 'm': root.m, 'witness': root.witness, 'business': root.business,
            'reregistered': root.reregistered, 'live': counts(root, 'live'), 'accepted': counts(root, 'accepted'),
            'credit': credit(root),
            'attempts': sorted((a.aid, a.req, a.phase, a.nonce, a.receipt, a.crossed) for a in root.attempts)}


def canonical(root):
    """State up to renaming of attempt, request and nonce identities (they are only compared for equality)."""
    shapes = sorted((a.phase, a.nonce is not None, a.receipt, a.crossed) for a in root.attempts)
    return (root.k, root.m, root.witness, root.business, root.reregistered, tuple(shapes))


# ---------------------------------------------------------------------------------------------------------------
def _find(root, aid):
    return next((a for a in root.attempts if a.aid == aid), None)


def _put(root, new):
    return replace(root, attempts=tuple(new if a.aid == new.aid else a for a in root.attempts))


def _result(root, new, code):
    return (Decision('NOOP', code), root) if new == root else (Decision('APPLIED', code), new)


DENY = lambda root, code: (Decision('DENIED', code), root)
DUP = lambda root, code: (Decision('DUPLICATE', code), root)


def reserve(root, aid, req):
    a = _find(root, aid)
    if a is not None:
        if a.phase == 'DISCARDED':
            return DENY(root, 'DISCARDED_NEVER_ACCEPTED')                         # A7
        return DUP(root, 'IDENTICAL_RESERVE') if a.req == req else DENY(root, 'ATTEMPT_ID_CONFLICT')
    if any(x.req == req for x in root.attempts):
        return DENY(root, 'REQUEST_KEY_CONFLICT')
    if root.witness != 'ACTIVE':
        return DENY(root, 'WITNESS_HELD')
    if root.business != 'OPEN':
        return DENY(root, 'BUSINESS_REDUCED')
    if not admits(root):
        return DENY(root, 'BUDGET')
    return _result(root, replace(root, attempts=root.attempts + (Attempt(aid, req, 'RESERVING'),)), 'RESERVED_LOCAL')


def accept_reservation(root, aid):
    a = _find(root, aid)
    if a is None or a.phase == 'DISCARDED':
        return DENY(root, 'UNKNOWN_OR_DISCARDED')
    if a.phase != 'RESERVING':
        return DUP(root, 'ALREADY_ACCEPTED')
    if root.witness != 'ACTIVE':
        return DENY(root, 'WITNESS_HELD')
    return _result(root, _put(root, replace(a, phase='RESERVED')), 'RESERVATION_ACCEPTED')


def token(root, aid):
    a = _find(root, aid)
    if a is None or a.phase in ('RELEASED', 'DISCARDED'):
        return DENY(root, 'UNKNOWN_RELEASED_OR_DISCARDED')
    if a.phase == 'RESERVING':
        return DENY(root, 'RESERVATION_NOT_ACCEPTED')
    if a.phase != 'RESERVED':
        return DUP(root, 'TOKEN_ALREADY_RELEASED')
    if root.witness != 'ACTIVE':
        return DENY(root, 'WITNESS_HELD')                                         # v3 D2
    if root.business != 'OPEN':
        return DENY(root, 'BUSINESS_REDUCED')                                     # v3 D2
    return _result(root, _put(root, replace(a, phase='TOKEN')), 'TOKEN_RELEASED')


def start(root, aid, nonce):
    a = _find(root, aid)
    if a is None:
        return DENY(root, 'UNKNOWN_ATTEMPT')
    if a.nonce is not None:
        return DUP(root, 'IDENTICAL_START') if a.nonce == nonce else DENY(root, 'ATTEMPT_ALREADY_HAS_NONCE')
    if any(x.nonce == nonce for x in root.attempts):
        return DENY(root, 'NONCE_REUSE')
    if root.witness != 'ACTIVE':
        return DENY(root, 'WITNESS_HELD')
    if root.business != 'OPEN':
        return DENY(root, 'BUSINESS_REDUCED')
    if a.phase != 'TOKEN':
        return DENY(root, 'NO_ACCEPTED_RESERVATION_WITH_RELEASED_TOKEN')
    return _result(root, _put(root, replace(a, phase='INTENT_PENDING', nonce=nonce)), 'INTENT_COMMITTED_LOCAL')


def accept_intent(root, aid):
    a = _find(root, aid)
    if a is None:
        return DENY(root, 'UNKNOWN_ATTEMPT')
    if a.phase in ('CONSUMED', 'NO_EFFECT', 'EFFECT'):
        return DUP(root, 'ALREADY_ACCEPTED')
    if a.phase != 'INTENT_PENDING':
        return DENY(root, 'NO_PENDING_INTENT')
    if root.witness != 'ACTIVE':
        return DENY(root, 'WITNESS_HELD')
    return _result(root, _put(root, replace(a, phase='CONSUMED')), 'CONSUMPTION_FINAL')


def receipt(root, aid):
    a = _find(root, aid)
    if a is None or a.phase not in ('CONSUMED', 'NO_EFFECT', 'EFFECT'):
        return DENY(root, 'NO_ACCEPTED_INTENT')
    if a.receipt:
        return DUP(root, 'RECEIPT_ALREADY_DELIVERED')
    return _result(root, _put(root, replace(a, receipt=True)), 'RECEIPT_DELIVERED')


def cross(root, aid):
    a = _find(root, aid)
    if a is None or a.phase != 'CONSUMED':
        return DENY(root, 'NOT_EXECUTABLE')
    if a.crossed:
        return DENY(root, 'ALREADY_CROSSED')
    if not a.receipt:
        return DENY(root, 'NO_COVERING_RECEIPT')
    if root.witness != 'ACTIVE' or root.business != 'OPEN':
        return DENY(root, 'MODE_FORBIDS_CROSSING')
    return _result(root, _put(root, replace(a, crossed=True)), 'CROSSED')


def release(root, aid, evidence):
    a = _find(root, aid)
    if a is None or a.phase == 'DISCARDED':
        return DENY(root, 'UNKNOWN_OR_DISCARDED')
    if a.phase == 'RELEASED':
        return DUP(root, 'ALREADY_RELEASED')
    if a.phase == 'INTENT_PENDING':
        return DENY(root, 'PENDING_INTENT_NEEDS_VERIFIED_RECOVERY')
    if a.phase in ACCEPTED_C:
        return DENY(root, 'RELEASE_AFTER_ACCEPTED_INTENT')
    if a.phase == 'RESERVING':
        return DENY(root, 'RESERVATION_NOT_ACCEPTED')
    if evidence != 'BOUND_FENCE':
        return DENY(root, 'NO_BOUND_FENCING_EVIDENCE')
    if root.witness != 'ACTIVE':
        return DENY(root, 'WITNESS_HELD')
    return _result(root, _put(root, replace(a, phase='RELEASED')), 'RESERVATION_RELEASED')


def reconcile(root, aid, verdict, evidence):
    if verdict not in VERDICTS or evidence not in RECONCILE_EVIDENCE:
        raise InvalidInput('unknown verdict or evidence label')
    a = _find(root, aid)
    if a is None:
        return DENY(root, 'UNKNOWN_ATTEMPT')
    if a.phase in ('NO_EFFECT', 'EFFECT'):
        if a.phase == verdict and evidence == 'AUTHORISED':
            return DUP(root, 'ALREADY_RECONCILED')
        return DENY(root, 'RECONCILED_DIFFERENTLY_OR_UNAUTHORISED')
    if a.phase != 'CONSUMED':
        return DENY(root, 'NOT_AN_ELIGIBLE_CONSUMED_ATTEMPT')
    if evidence != 'AUTHORISED':
        return DENY(root, 'NO_AUTHORISED_BOUND_EVIDENCE')
    if root.witness != 'ACTIVE':
        return DENY(root, 'WITNESS_HELD')
    if verdict == 'UNKNOWN':
        return Decision('NOOP', 'STAYS_CHARGED'), root
    return _result(root, _put(root, replace(a, phase=verdict)), 'RECONCILED')


def fact(root, aid=None):
    if aid is not None and _find(root, aid) is None:
        return DENY(root, 'UNKNOWN_ATTEMPT')
    return Decision('NOOP', 'NO_ACCOUNTING_EFFECT'), root


def hold(root):
    if root.witness == 'HELD':
        return DENY(root, 'ALREADY_HELD')
    return _result(root, replace(root, witness='HELD'), 'HELD')


def stop(root):
    if root.business != 'OPEN':
        return DENY(root, 'BREAK_GLASS_ONLY_FROM_OPEN')
    return _result(root, replace(root, business='STOPPING'), 'STOPPING')


def terminalise(root):
    if root.business != 'STOPPING':
        return DENY(root, 'NOT_STOPPING')
    if root.witness != 'ACTIVE':
        return DENY(root, 'WITNESS_HELD')
    return _result(root, replace(root, business='TERMINALISING'), 'TERMINALISING')


def terminal(root):
    if root.business != 'TERMINALISING':
        return DENY(root, 'NOT_TERMINALISING')
    if root.witness != 'ACTIVE':
        return DENY(root, 'WITNESS_HELD')
    if any(a.phase in RESERVATION_PHASES + ('INTENT_PENDING', 'CONSUMED') for a in root.attempts):
        return DENY(root, 'OUTSTANDING_OR_UNRECONCILED_ATTEMPTS')
    return _result(root, replace(root, business='TERMINAL'), 'TERMINAL')


def recover(root, approved, complete):
    if root.witness != 'HELD':
        return DENY(root, 'NOT_HELD')
    if approved is not True:
        return DENY(root, 'RECOVERY_NOT_APPROVED')
    restored = []
    for a in root.attempts:
        if a.phase == 'RESERVING':
            a = replace(a, phase='DISCARDED')                       # proven never accepted
        elif a.phase == 'INTENT_PENDING':
            a = replace(a, phase='TOKEN', nonce=None)               # accepted-chain attempt, nonce and budget
        restored.append(a)
    new = replace(root, attempts=tuple(restored), witness='ACTIVE' if complete else 'HELD')
    return _result(root, new, 'RECOVERED' if complete else 'RECOVERY_BATCH_STILL_HELD')


def reregister(root):
    if root.business == 'TERMINAL':
        return DENY(root, 'TERMINAL')
    if root.reregistered:
        return DENY(root, 'ALREADY_REREGISTERED')
    unresolved = RESERVATION_PHASES + ('INTENT_PENDING', 'CONSUMED')
    attempts = tuple(replace(a, phase='INDETERMINATE') if a.phase in unresolved else a for a in root.attempts)
    return _result(root, replace(root, attempts=attempts, witness='ACTIVE', business='STOPPING', reregistered=True),
                   'REREGISTERED_REDUCED')


# ------------------------------------------- v3.1 E1: the complete list of malformed input -------------------------------
ARITY = {'RESERVE': 2, 'ACCEPT_RESERVATION': 1, 'TOKEN': 1, 'START': 2, 'ACCEPT_INTENT': 1, 'RECEIPT': 1, 'CROSS': 1,
         'RELEASE': 2, 'RECONCILE': 3, 'TIMEOUT': 1, 'MISSING_RECEIPT': 1, 'CRASH': 0, 'HOLD': 0, 'STOP': 0,
         'TERMINALISE': 0, 'TERMINAL': 0, 'RECOVER': 2, 'REREGISTER': 0}
WORLD_ARITY = {'NEW_ROOT': 4, 'DELEGATE': 2, 'CALL': 2}


def _ident(x, what):
    if not (isinstance(x, str) and x):
        raise InvalidInput(f'{what} must be a non-empty string, got {x!r}')


def _shape(event, arity, what):
    if not (isinstance(event, tuple) and event and isinstance(event[0], str)):
        raise InvalidInput(f'{what} must be a tuple starting with an operation name, got {event!r}')
    if event[0] not in arity:
        raise InvalidInput(f'unknown {what} {event[0]!r}')
    if len(event) - 1 != arity[event[0]]:
        raise InvalidInput(f'{event[0]} takes {arity[event[0]]} argument(s), got {len(event) - 1}')
    return event[0], event[1:]


def validate(event):
    """Evaluation step 1 for a single-root operation (contract v3.1 section 5)."""
    name, args = _shape(event, ARITY, 'single-root operation')
    if name not in ('CRASH', 'HOLD', 'STOP', 'TERMINALISE', 'TERMINAL', 'RECOVER', 'REREGISTER'):
        _ident(args[0], 'attempt identity')
    if name == 'RESERVE':
        _ident(args[1], 'request key')
    if name == 'START':
        _ident(args[1], 'nonce')
    if name == 'RELEASE' and args[1] not in RELEASE_EVIDENCE:
        raise InvalidInput(f'unknown release evidence label {args[1]!r}')
    if name == 'RECONCILE' and (args[1] not in VERDICTS or args[2] not in RECONCILE_EVIDENCE):
        raise InvalidInput(f'unknown verdict or evidence label {args[1:]!r}')
    if name == 'RECOVER' and not (type(args[0]) is bool and type(args[1]) is bool):
        raise InvalidInput(f'RECOVER takes two booleans, got {args!r}')


def validate_world(event):
    """Evaluation step 1 for a world operation, nested operation included (v3.1 E1, E10)."""
    name, args = _shape(event, WORLD_ARITY, 'world operation')
    if name == 'NEW_ROOT':
        _ident(args[0], 'root identity'); _ident(args[3], 'caller identity')   # k and m: NEW_ROOT rule 2
    elif name == 'DELEGATE':
        _ident(args[0], 'caller identity'); _ident(args[1], 'caller identity')
    else:
        _ident(args[0], 'caller identity'); validate(args[1])


def step(root, event):
    """Apply one event tuple, e.g. ('RESERVE', 'a1', 'q1').  Returns (Decision, Root)."""
    validate(event)                                                               # v3.1 E1: step 1, before any rule
    name, *args = event
    table = {'RESERVE': reserve, 'ACCEPT_RESERVATION': accept_reservation, 'TOKEN': token, 'START': start,
             'ACCEPT_INTENT': accept_intent, 'RECEIPT': receipt, 'CROSS': cross, 'RELEASE': release,
             'RECONCILE': reconcile, 'TIMEOUT': fact, 'MISSING_RECEIPT': fact, 'CRASH': fact, 'HOLD': hold,
             'STOP': stop, 'TERMINALISE': terminalise, 'TERMINAL': terminal, 'RECOVER': recover,
             'REREGISTER': reregister}
    if name not in ('TIMEOUT', 'MISSING_RECEIPT', 'CRASH') and args and isinstance(args[0], str):
        a = _find(root, args[0])
        if a is not None and a.phase == 'INDETERMINATE':
            return DENY(root, 'INDETERMINATE')                                    # A9
    return table[name](root, *args)


def initial(k, m):
    return Root(k, m)


# ------------------------------------- several roots and delegated callers -------------------------------------
@dataclass(frozen=True)
class World:
    roots: tuple = ()      # ((root_id, Root), ...)
    callers: tuple = ()    # ((caller_id, root_id), ...)


def world_step(world, event):
    validate_world(event)                                                         # v3.1 E1, E10
    name, *args = event
    roots, callers = dict(world.roots), dict(world.callers)
    if name == 'NEW_ROOT':
        rid, k, m, caller = args
        if rid in roots or caller in callers:
            return Decision('DENIED', 'ROOT_OR_CALLER_EXISTS'), world
        roots[rid] = Root(k, m); callers[caller] = rid
    elif name == 'DELEGATE':
        parent, child = args
        if parent not in callers or child in callers:
            return Decision('DENIED', 'UNKNOWN_PARENT_OR_BOUND_CHILD'), world
        callers[child] = callers[parent]                            # same root: no new capacity
    elif name == 'CALL':
        caller, inner = args
        if caller not in callers:
            return Decision('DENIED', 'UNKNOWN_CALLER'), world
        rid = callers[caller]
        decision, new_root = step(roots[rid], inner)
        roots[rid] = new_root
        return decision, World(tuple(sorted(roots.items())), tuple(sorted(callers.items())))
    else:
        raise InvalidInput(f'unknown world event {name!r}')
    return Decision('APPLIED', name), World(tuple(sorted(roots.items())), tuple(sorted(callers.items())))
