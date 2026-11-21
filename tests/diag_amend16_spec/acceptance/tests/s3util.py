"""Scenario helpers for the section 3 tests.  No signing key lives here: honest reports come from the honest gate host
(another process); CAP-KEY tests pass their own signer object in."""
from fixtures.crypto import rand_hex, evidence_id, pair_id, H

REASON = {'PASS': 'MET', 'FAIL': 'LIMIT_NOT_MET', 'UNKNOWN': 'CHECK_ERROR'}
FINDINGS = ('K-CONFLICT', 'K-UNKNOWN-VERDICT', 'K-FENCE', 'K-PHASE', 'K-EARLY', 'K-NONCE', 'K-DIGEST', 'K-CLAIM', 'K-MISSING')
VERDICT_NOTICES = ('PASS', 'FAIL', 'UNKNOWN', 'INVALID', 'UNVERIFIED', 'REFUNDED', 'INTERRUPTED', 'NO_OUTCOME', 'INDETERMINATE')


def val(verdict='FAIL'):
    """A check's result (the value a gate signs the digest of)."""
    return {'verdict': verdict, 'reason_code': REASON.get(verdict, 'ODD'), 'salt': rand_hex(6)}


def honest_run(tc, b, verdict='FAIL', store=True, claim='EFFECT'):
    """A run the honest gate host ran: CONSUMED, then RECONCILE with its genuine report (VERDICT_RECORDED)."""
    aid, nonce = b.new_run(upto='CONSUMED')
    v = val(verdict)
    rep = tc.gate().run(b.root, aid, nonce, claim, v)
    b.reconcile(aid, rep)
    if store and claim == 'EFFECT':
        b.store_result(aid, v)
    return aid, nonce, rep, v


def key_budget(tc, *signers, extra_keys=()):
    return tc.new_budget(gate_keys=[s.public_key for s in signers] + list(extra_keys), honest=False)


def key_run(b, s, verdict='FAIL', store=True):
    aid, nonce = b.new_run(upto='CONSUMED')
    v = val(verdict)
    rep = s.effect(b.root, aid, nonce, 'EFFECT', v)
    b.reconcile(aid, rep)
    if store:
        b.store_result(aid, v)
    return aid, nonce, rep, v


def eid(r):
    return evidence_id(r)


def pid(r):
    return pair_id(r['claim'], r['result_digest'])
