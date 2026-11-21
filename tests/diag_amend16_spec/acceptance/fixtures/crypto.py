"""Test-side primitives of the specification's definitions (D-1, D-2, D-6, E-1).  Written from the text of
the specification (version 6) and from the formats of `check_record.canonical` / `evidence_message` at e25a297; nothing here imports
the system under test.

    canonical(x)  json.dumps(x, sort_keys=True, separators=(',', ':'))           D-1
    H(x)          sha256(canonical(x)) lower-case hex                            D-1
    Hb(b)         sha256(bytes) lower-case hex                                   D-1
    signed_projection(report)  the eight fields of D-2, absent signed fields read as null
    evidence_id(report)        H(signed projection)                              D-2, E-1
    pair_id(claim, digest)     H([claim, digest])                                D-6

`TestKey` is an Ed25519 key for parties OTHER than the gate (witness, courier, mailbox, engineer).  The gate's key never
lives in a test process except in fixtures/capkey.py (CAP-KEY only, K-CAP-1).
"""
import hashlib
import json
import os

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

SIGNED_SIX = ('kind', 'root', 'aid', 'nonce', 'claim', 'result_digest')
PROJECTION = SIGNED_SIX + ('signer', 'signature')


def canonical(x) -> str:
    return json.dumps(x, sort_keys=True, separators=(',', ':'))


def H(x) -> str:
    return hashlib.sha256(canonical(x).encode()).hexdigest()


def Hb(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def report_message(report: dict) -> bytes:
    """What the gate's signature covers: the six signed fields, absent read as null (D-2)."""
    return canonical({k: report.get(k) for k in SIGNED_SIX}).encode()


def signed_projection(report: dict) -> dict:
    return {k: report.get(k) for k in PROJECTION}


def projection_bytes(report: dict) -> bytes:
    return canonical(signed_projection(report)).encode()


def evidence_id(report: dict) -> str:
    return H(signed_projection(report))


def pair_id(claim, digest) -> str:
    return H([claim, digest])


def well_formed_digest(d) -> bool:
    return isinstance(d, str) and len(d) == 64 and all(c in '0123456789abcdef' for c in d)


def verify_sig(public_hex: str, signature_hex: str, message: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex)).verify(bytes.fromhex(signature_hex), message)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def rand_hex(n: int) -> str:
    return os.urandom(n).hex()


class TestKey:
    """An Ed25519 key of a party that is NOT the gate."""
    __test__ = False

    def __init__(self, private_hex=None):
        self._k = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_hex)) if private_hex else Ed25519PrivateKey.generate()

    @property
    def private_hex(self) -> str:
        return self._k.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()).hex()

    @property
    def public_hex(self) -> str:
        return self._k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()

    def sign(self, message: bytes) -> str:
        return self._k.sign(message).hex()

    def sign_object(self, obj: dict, exclude=('signer', 'signature')) -> dict:
        """The convention the tests assume for every form-3 object (items, challenge requests): the signature covers
        canonical(every field but signer and signature) (I-1).  For mailbox-signed objects the same convention is
        assumed (finding T-series: the specification does not state the mailbox's signed message)."""
        body = {k: v for k, v in obj.items() if k not in exclude}
        return dict(body, signer=self.public_hex, signature=self.sign(canonical(body).encode()))


def verify_object(obj: dict, keys) -> bool:
    if not isinstance(obj, dict):
        return False
    body = {k: v for k, v in obj.items() if k not in ('signer', 'signature')}
    return obj.get('signer') in tuple(keys) and verify_sig(obj.get('signer', ''), obj.get('signature', ''), canonical(body).encode())
