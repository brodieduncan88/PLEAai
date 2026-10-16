"""Binding (v0.6): what an accepted intent authorises, and what a signed outcome covers.

The v0.4 review showed three gaps: the witness's intent receipt named the attempt but not the nonce, so a host ran
a genuine receipt under any nonce the caller supplied; the nonce bound nothing, so any tool with any arguments ran
behind it, at any host holding a pinned key; and the host's result travelled unsigned beside its signed report.

Now the nonce is a digest of the action and its executor: nonce = H(root, attempt, executor key, tool, canonical
arguments).  The witness's ACCEPT_INTENT receipt carries the nonce it accepted (receipts.py: `binding`), so the
receipt binds the action and the executor, and the host refuses a run whose nonce the witness did not accept or
whose action and executor do not hash to it.  A retry of a request key with a different action computes a
different nonce, which START refuses (contract 5.4/2), so a request key is bound to one action.  The effect report
carries a digest of the result (evidence.py: `result_digest`), so the governor accepts a result only when the host's
signed report covers it.
"""
import hashlib
import json


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), default=repr)


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def nonce_for(root: str, aid: str, executor: str, tool: str, arguments) -> str:
    """The nonce that binds this attempt's action to this executor.  executor: the gate's public key (hex)."""
    return 'n-' + digest({'root': root, 'aid': aid, 'executor': executor, 'tool': tool, 'arguments': arguments})[:40]


def result_digest(result) -> str:
    return digest(result)


def evidence_digest(evidence) -> str | None:
    """v0.7: what a RELEASE or RECONCILE receipt binds, so a replayed receipt for an earlier submission is refused."""
    return None if evidence is None else digest(evidence)
