"""Signing keys, the signed baseline envelope, and the verification record.

The envelope (baseline.json) is what the responsible engineer signs: the card, and the control cases as they actually
ran at baselining.  Its signature is by the engineer's own key, which the gate host pins.

    {"card": {...}, "baseline_sha256": "...", "controls_run": [...], "signature": {"signer": KEY, "signature": SIG}}

The record is everything a reader needs to check the work without this system: the envelope, the budget's provisioning
record, every audit row, the witness's receipts, the gate host's signed reports and the verdicts they cover, the
engineer's acknowledgements, an as-of line, and one signature over all of it by the engineer's key.  check_record.py
checks a record offline.

Outcome of an official run, from its phase and the gate's reports:
  PASS / FAIL / UNKNOWN   the verdict the gate signed (a result is present and says why)
  INTERRUPTED             admitted, and the gate signed that it does not know the outcome; no result; never run again
  PENDING                 reserved or admitted with no outcome yet
  REFUNDED                the contract's NO_EFFECT.  It must never appear here: a verification run is never refunded.
"""
import datetime
import hashlib
import json
import pathlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from baseline import canonical, card_hash, validate_card

FORMAT = 'verification-record/1'
RECEIPT_OPS = ('ACCEPT_RESERVATION', 'ACCEPT_INTENT', 'CROSS')
PENDING_PHASES = ('RESERVING', 'RESERVED', 'TOKEN', 'INTENT_PENDING')
TOOL = 'verify'


class Key:
    """An Ed25519 key: the responsible engineer's.  It signs baselines, acknowledgements and records."""

    def __init__(self, private_hex: str | None = None):
        self._key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_hex)) if private_hex else Ed25519PrivateKey.generate()

    @property
    def private_hex(self) -> str:
        return self._key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()).hex()

    @property
    def public_hex(self) -> str:
        return self._key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()

    def sign(self, message: bytes) -> str:
        return self._key.sign(message).hex()


def signed_by(public_hex: str, signature_hex: str, message: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex)).verify(bytes.fromhex(signature_hex), message)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


# ---------------------------------------------------------------------------------------------------- the envelope
def envelope_message(card: dict, controls_run: list) -> bytes:
    return canonical({'card': card, 'controls_run': controls_run}).encode()


def sign_envelope(card: dict, controls_run: list, key: Key) -> dict:
    return {'card': card, 'baseline_sha256': card_hash(card), 'controls_run': controls_run,
            'signature': {'signer': key.public_hex, 'signature': key.sign(envelope_message(card, controls_run))}}


def load_envelope(path, pinned_keys) -> dict:
    """Read a baseline and refuse it unless a pinned engineer key signed exactly this card and these control results."""
    env = json.loads(pathlib.Path(path).read_text())
    card, sig = env['card'], env['signature']
    validate_card(card)
    pinned = (pinned_keys,) if isinstance(pinned_keys, str) else tuple(pinned_keys)
    if sig.get('signer') not in pinned or sig['signer'] != card['responsible_engineer']['key']:
        raise ValueError('the baseline is not signed by a pinned engineer key that the card names')
    if not signed_by(sig['signer'], sig.get('signature', ''), envelope_message(card, env['controls_run'])):
        raise ValueError('the baseline\'s signature does not verify: the card or its control results were changed after signing')
    if env.get('baseline_sha256') != card_hash(card):
        raise ValueError('baseline_sha256 is not the card\'s hash')
    return env


# ---------------------------------------------------------------------------------------------------- attempts
def arguments_for(baseline_sha256: str, design) -> dict:
    return {'baseline_sha256': baseline_sha256, 'design': design}


def request_key(arguments: dict) -> str:
    """The same rule plea_mcp.py uses: the tool name and a hash of its canonical arguments.  Never chosen by the caller."""
    return f'{TOOL}:' + hashlib.sha256(canonical(arguments).encode()).hexdigest()[:24]


def outcome_of(phase: str, evidence: list, result) -> str:
    if phase == 'NO_EFFECT':
        return 'REFUNDED'
    if phase == 'EFFECT':
        return result.get('verdict') if isinstance(result, dict) and result.get('verdict') in ('PASS', 'FAIL', 'UNKNOWN') else 'INVALID'
    if phase in PENDING_PHASES:
        return 'PENDING'
    if phase == 'CONSUMED':
        claims = [e['evidence'].get('claim') for e in evidence if isinstance(e.get('evidence'), dict)]
        return 'INTERRUPTED' if 'UNKNOWN' in claims else 'PENDING'
    return phase


def acknowledgement_message(root: str, aid: str, outcome: str, disposition: str, time: str) -> bytes:
    return canonical({'root': root, 'aid': aid, 'outcome': outcome, 'disposition': disposition, 'time': time}).encode()


def attempts_of(store, root: str, submissions: list, upto: int | None = None) -> tuple[list, dict]:
    """(attempts, observation) from one snapshot.  submissions: candidate {baseline_sha256, design} objects from any
    source; each is used only if it hashes to an attempt's request key, so the source need not be trusted."""
    audit, observation = store.audit_snapshot(root)
    upto = len(audit) if upto is None else upto
    by_key = {request_key(a): a for a in submissions}
    attempts = []
    for aid, req, phase, nonce, _receipt, _crossed in observation['attempts']:
        evidence = [{'seq': e['seq'], 'evidence': e['evidence']} for e in store.evidence_for(root, aid) if e['seq'] <= upto]
        receipts = {}
        for op in RECEIPT_OPS:
            r = store.get_receipt(root, aid, op)
            if r is not None and r.get('seq', 0) <= upto:
                receipts[op] = r
        stored = store.get_result(root, aid)
        result = stored.get('value') if isinstance(stored, dict) and stored.get('outcome', 'value') == 'value' and phase == 'EFFECT' else None
        arguments = by_key.get(req)
        if arguments is None and isinstance(result, dict) and 'design' in result:
            guess = arguments_for(result.get('baseline_sha256'), result['design'])
            arguments = guess if request_key(guess) == req else None
        attempts.append({'aid': aid, 'request_key': req, 'arguments': arguments, 'phase': phase, 'nonce': nonce,
                         'outcome': outcome_of(phase, evidence, result), 'receipts': receipts, 'evidence': evidence, 'result': result})
    return attempts, {'audit': audit, 'observation': observation}


def build(store, envelope: dict, root: str, keys: dict, signer: Key, submissions=(), acknowledgements=(), at: str | None = None, checkpointer=None) -> dict:
    """keys: {'witness': hex, 'gate': hex}.  The record is signed by the engineer's key.  checkpointer(root, seq), where given,
    asks the witness for a checkpoint that says what the chain's head was after decision `seq`; it goes into the record, under
    the engineer's signature (Amendment 10).  The record's checker requires it to be the witness's and to name this record's head."""
    attempts, snap = attempts_of(store, root, list(submissions))
    audit, provisioning = snap['audit'], store.provisioning(root)
    known = {a['aid'] for a in attempts}
    body = {
        'format': FORMAT, 'root': root, 'baseline': envelope, 'baseline_sha256': envelope['baseline_sha256'],
        'keys': {'witness': keys['witness'], 'gate': keys['gate'], 'engineer': signer.public_hex},
        'provisioning': provisioning, 'audit': audit, 'attempts': attempts,
        'acknowledgements': [a for a in acknowledgements if a.get('aid') in known],
        'as_of': {'time': at or now(), 'seq': len(audit), 'head': audit[-1]['hash'] if audit else (provisioning or {}).get('hash')},
    }
    if checkpointer is not None:
        body['checkpoint'] = checkpointer(root, body['as_of']['seq'])
    body = json.loads(json.dumps(body))                                # plain JSON types, exactly what a reader will parse
    return dict(body, signature={'signer': signer.public_hex, 'signature': signer.sign(canonical(body).encode())})
