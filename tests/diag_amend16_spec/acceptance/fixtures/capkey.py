"""CAP-KEY ONLY.  A signer that holds a gate signing key in the test's own process (K-CAP-1: "A test that signs anything
with the gate's key is a CAP-KEY test and MUST be labelled so").

The runner refuses (ERROR) a test labelled anything but CAP-KEY that imports or touches this module:
  - statically, before the test runs (run_acceptance.capability_violation: the test's source and its module's globals);
  - dynamically, here: constructing a CapKeySigner, or signing with one, while the current test is not CAP-KEY raises
    CapabilityViolation, which the runner reports as ERROR.

Tests reach it only through AccTest.capkey_signer(), never by importing this module at module level.
"""
import hashlib
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import acc


def _guard(what: str):
    cap = acc.current_capability()
    if cap != 'CAP-KEY':
        raise acc.CapabilityViolation(f'{what}: the CAP-KEY signer was touched by a test labelled {cap!r} (K-CAP-1)')


class CapKeySigner:
    """Holds a gate key.  `honest_*` sign what an honest host would; `sign` signs anything (a service holding the key)."""

    def __init__(self):
        _guard('CapKeySigner()')
        self._k = Ed25519PrivateKey.generate()
        self.public_key = self._k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()

    def sign(self, kind, root, aid, nonce, claim, result_digest, omit=()) -> dict:
        """A report over exactly these six signed fields.  `omit` deletes signed fields that are null from the report as
        sent (D-2: an absent signed field is read as null, so the signature still verifies)."""
        _guard('CapKeySigner.sign')
        body = {'kind': kind, 'root': root, 'aid': aid, 'nonce': nonce, 'claim': claim, 'result_digest': result_digest}
        sig = self._k.sign(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hex()
        out = dict(body, signer=self.public_key, signature=sig)
        for k in omit:
            out.pop(k, None)
        return out

    def effect(self, root, aid, nonce, claim, result=None) -> dict:
        d = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        return self.sign('EFFECT_REPORT', root, aid, nonce, claim, d)

    def fence(self, root, aid) -> dict:
        return self.sign('FENCE_REPORT', root, aid, None, 'FENCED_NO_START', None)
