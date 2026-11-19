"""Signed receipts: what the witness returns for an acceptance, and what the gate verifies before it crosses.

A receipt binds eight fields: the root, the attempt, the audit sequence number of the acceptance, the operation,
the decision kind and code, the audit hash of that decision, and (v0.6) the binding: for an accepted START_INTENT,
the nonce the witness accepted, read from the committed state; None for every other acceptance.  The witness
signs the canonical JSON of those fields with Ed25519.  Verification checks the signer against the pinned public
key, the fields against what the gate expects, the signature, and (in the governor) the hash against the local
audit chain.  A receipt therefore cannot be forged without the witness's key, moved to another attempt, moved to
another root's chain, altered, or (v0.6) used to run under a nonce the witness did not accept.
"""
import json
from dataclasses import dataclass, asdict

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

ACCEPTANCES = ('ACCEPT_RESERVATION', 'ACCEPT_INTENT', 'RELEASE', 'RECONCILE')
WITNESSED = ACCEPTANCES + ('CROSS',)        # v0.7: the crossing is applied by the witness and receipted; the host requires it


class ReceiptInvalid(Exception):
    pass


@dataclass(frozen=True)
class Receipt:
    root: str
    aid: str
    seq: int
    op: list
    kind: str
    code: str
    hash: str
    signer: str      # public key, hex
    signature: str   # hex
    binding: str | None = None   # v0.6: the nonce an accepted START_INTENT bound; None otherwise

    def message(self) -> bytes:
        body = {k: getattr(self, k) for k in ('root', 'aid', 'seq', 'op', 'kind', 'code', 'hash', 'binding')}
        return json.dumps(body, sort_keys=True, separators=(',', ':')).encode()

    def to_json(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_json(d: dict) -> 'Receipt':
        try:
            binding = d.get('binding')
            if binding is not None and not isinstance(binding, str):
                raise TypeError('binding')
            return Receipt(d['root'], d['aid'], int(d['seq']), list(d['op']), d['kind'], d['code'], d['hash'], d['signer'], d['signature'], binding)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ReceiptInvalid(f'malformed receipt: {exc}')


class Signer:
    def __init__(self, private_hex: str | None = None):
        self._key = (Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_hex)) if private_hex
                     else Ed25519PrivateKey.generate())

    @property
    def private_hex(self) -> str:
        return self._key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                       serialization.NoEncryption()).hex()

    @property
    def public_hex(self) -> str:
        return self._key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()

    def sign(self, root: str, aid: str, seq: int, op, kind: str, code: str, digest: str, binding: str | None = None) -> Receipt:
        unsigned = Receipt(root, aid, seq, list(op), kind, code, digest, self.public_hex, '', binding)
        return Receipt(root, aid, seq, list(op), kind, code, digest, self.public_hex, self._key.sign(unsigned.message()).hex(), binding)


CHECKPOINT_FIELDS = ('statement', 'root', 'seq', 'head', 'business', 'witness', 'time', 'nonce', 'at', 'head_at')


def checkpoint_message(c: dict) -> bytes:
    """What the witness signs in a checkpoint (Amendment 10): the canonical JSON of its ten fields.  A receipt's message
    always has an "aid" and no "statement", so neither can be passed off as the other."""
    return json.dumps({k: c.get(k) for k in CHECKPOINT_FIELDS}, sort_keys=True, separators=(',', ':')).encode()


def sign_checkpoint(signer: 'Signer', root: str, seq: int, head: str, business: str, witness: str, time: str,
                    nonce: str | None = None, at: int | None = None, head_at: str | None = None) -> dict:
    """A witness-signed statement of a budget's chain as the witness reads it now (Amendment 10): the number of decisions
    recorded (seq), the hash of the last (head), the budget's two states, and the witness's clock.  nonce is the asker's,
    signed back, so the asker knows the statement was made after it chose the nonce.  at and head_at say what the chain's
    head was after decision number `at`, so that an older record can be shown to be a beginning of this chain."""
    c = {'statement': 'CHECKPOINT', 'root': root, 'seq': seq, 'head': head, 'business': business, 'witness': witness, 'time': time,
         'nonce': nonce, 'at': at, 'head_at': head_at}
    return dict(c, signer=signer.public_hex, signature=signer._key.sign(checkpoint_message(c)).hex())


def _pinned(keys) -> tuple:
    return (keys,) if isinstance(keys, str) else tuple(keys)


def verify_signed(receipt: Receipt, pinned_public_hex, root: str, aid: str, op_name: str) -> None:
    """Raise ReceiptInvalid unless the receipt is the pinned witness's, for this root, attempt and operation.

    This is the client's check: the witness's signed statement about this operation, whatever it decided.  A
    receipt for a DENIED release is a valid statement (amendment 1: the first version applied the gate's rule here
    and refused it, which the declared W3 run found)."""
    if receipt.signer not in _pinned(pinned_public_hex):          # one key, or a list during rotation (v0.4)
        raise ReceiptInvalid('receipt signed by an unknown key')
    if receipt.root != root or receipt.aid != aid:
        raise ReceiptInvalid('receipt is for another root or attempt')
    if not receipt.op or receipt.op[0] != op_name or (len(receipt.op) > 1 and receipt.op[1] != aid):
        raise ReceiptInvalid('receipt is for another operation')
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(receipt.signer)).verify(bytes.fromhex(receipt.signature), receipt.message())
    except (InvalidSignature, ValueError):
        raise ReceiptInvalid('bad signature')


def verify_admission(receipt: Receipt, pinned_public_hex, root: str, aid: str, nonce: str) -> None:
    """The host's admission check (v0.7): the witness's signed CROSS for this attempt and nonce, APPLIED (the crossing)
    or DENIED with ALREADY_CROSSED (a resume of an earlier crossing).  Anything else, and nothing runs."""
    verify_signed(receipt, pinned_public_hex, root, aid, 'CROSS')
    if not (receipt.kind == 'APPLIED' or (receipt.kind == 'DENIED' and receipt.code == 'ALREADY_CROSSED')):
        raise ReceiptInvalid('the witness did not record a crossing for this attempt')
    if receipt.binding != nonce:
        raise ReceiptInvalid('the crossing is not for this nonce')


def verify(receipt: Receipt, pinned_public_hex, root: str, aid: str, op_name: str, binding: str | None = None) -> None:
    """The gate's check: verify_signed, the receipt must attest an acceptance (APPLIED or DUPLICATE), and (v0.6) when
    a binding is expected the receipt must carry exactly that nonce: the witness accepted this action."""
    verify_signed(receipt, pinned_public_hex, root, aid, op_name)
    if receipt.kind not in ('APPLIED', 'DUPLICATE'):
        raise ReceiptInvalid('receipt does not attest an acceptance')
    if binding is not None and receipt.binding != binding:
        raise ReceiptInvalid('the witness did not accept this nonce for this attempt')
