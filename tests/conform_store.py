"""The store-backed implementation behind contract v3.1's section 8 conformance interface.

Every step is a round trip through the database: the handle's snapshot is written to its root (only when the
database has moved on, which happens when a vector branches from one state), the operation is applied by the
store's transaction, and the new state is read back.  The vectors therefore test the persistence of every phase
and fact, the validation at step 1 before the store is touched, and the store's apply path.  Concurrency is
G01's job, not this module's.  No accounting logic lives here.

Run from budget_v3_1/oracle:  PYTHONPATH=../../gateway/tests python3 -B vectors.py conform_store
"""
import os
import pathlib
import sys
import uuid
from dataclasses import dataclass

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from plea_gateway import Store, Decision                      # noqa: E402
from plea_gateway import plea_budget_ref as ref                # noqa: E402

DSN = os.environ.get('PLEA_ADMIN_DSN', 'postgresql://plea:plea@127.0.0.1:5432/plea')   # put_state needs the owner
STORE = Store(DSN, mode=os.environ.get('PLEA_MODE', 'lock'))
InvalidInput = ref.InvalidInput
_PREFIX = 'conf-' + uuid.uuid4().hex[:8] + '-'


@dataclass(frozen=True)
class Handle:
    root_id: str
    state: object        # the pure RootState this handle stands for


def _persist(state) -> Handle:
    root_id = _PREFIX + uuid.uuid4().hex[:10]
    STORE.put_state(root_id, state)
    return Handle(root_id, state)


def _sync(h: Handle) -> None:
    current, _, _ = STORE.state(h.root_id)
    if current != h.state:                                     # a vector branched: restore this handle's snapshot
        STORE.put_state(h.root_id, h.state)


def initial(k, m):
    return _persist(ref.initial(k, m))


def step(h, op):
    if not isinstance(h, Handle):
        raise InvalidInput('not a store handle')
    ref.parse_op(op)                                           # step 1, before any store access
    _sync(h)
    decision, _ = STORE.apply(h.root_id, op)
    new_state, _, _ = STORE.state(h.root_id)
    return decision, Handle(h.root_id, new_state)


def observe(h):
    if not isinstance(h, Handle):
        raise InvalidInput('not a store handle')
    _sync(h)
    return STORE.observe(h.root_id)


def Root(k, m, witness='ACTIVE', business='OPEN', attempts=(), reregistered=False):
    return _persist(ref.make_root(k, m, witness=witness, business=business, attempts=attempts, reregistered=reregistered))


def Attempt(aid, req, phase, nonce=None, receipt=False, crossed=False):
    return ref.AttemptFacts(aid, req, phase, nonce, receipt, crossed)


def root_from_facts(k, m, attempts=(), claimed_no_effect=None, **modes):
    return _persist(ref.root_from_facts(k, m, attempts, claimed_no_effect, **modes))


@dataclass(frozen=True)
class World:
    roots: tuple = ()        # ((rid, Handle), ...)
    callers: tuple = ()      # ((cid, rid), ...)


def world_step(w, op):
    parsed = ref.parse_world_op(op)                            # step 1, nested operation included
    roots, callers = dict(w.roots), dict(w.callers)
    name = op[0]
    if name == 'NEW_ROOT':
        rid, k, m, cid = op[1:]
        if rid in roots or cid in callers:
            return Decision('DENIED', 'ROOT_OR_CALLER_EXISTS'), w             # 5.14 rule 1, before the budget
        roots[rid] = initial(k, m); callers[cid] = rid                        # rule 2: initial validates k and m
        return Decision('APPLIED', 'NEW_ROOT'), World(tuple(sorted(roots.items())), tuple(sorted(callers.items())))
    if name == 'DELEGATE':
        parent, child = op[1:]
        if parent not in callers or child in callers:
            return Decision('DENIED', 'UNKNOWN_PARENT_OR_BOUND_CHILD'), w
        callers[child] = callers[parent]
        return Decision('APPLIED', 'DELEGATE'), World(tuple(sorted(roots.items())), tuple(sorted(callers.items())))
    cid, inner = op[1:]
    if cid not in callers:
        return Decision('DENIED', 'UNKNOWN_CALLER'), w
    rid = callers[cid]
    decision, h = step(roots[rid], inner)
    roots[rid] = h
    return decision, World(tuple(sorted(roots.items())), tuple(sorted(callers.items())))
