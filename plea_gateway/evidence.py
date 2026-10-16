"""Evidence (G03): what the witness verifies before it will apply a RELEASE or a RECONCILE, and (v0.6) what the
governor verifies before it accepts a result.

Contract v3.1 takes RELEASE(a, e) and RECONCILE(a, v, e) with labels e in {BOUND_FENCE, NONE, WRONG_BINDING} and
{AUTHORISED, NONE, WRONG_BINDING}.  Section 13 says those labels stand for checks the gateway must make.  Here the
caller never supplies a label.  It supplies a report signed by the gate's key, and the witness derives the label:

  FENCE_REPORT   the sandbox was fenced and no START_INTENT was committed under the token (claim FENCED_NO_START)
                 -> BOUND_FENCE if genuine and bound to this root and attempt; WRONG_BINDING if genuine but for
                 another root or attempt; NONE if absent, malformed, unsigned by a pinned gate key, or not that claim
  EFFECT_REPORT  the gate's verdict EFFECT, NO_EFFECT or UNKNOWN, bound to the root, the attempt and the nonce of
                 the intent that ran, and (v0.6) carrying a digest of the result the gate returned -> (verdict,
                 AUTHORISED) if genuine and bound; (verdict, WRONG_BINDING) if genuine but for another root, attempt
                 or nonce; (UNKNOWN, NONE) otherwise

The contract's rules then do the rest: 5.8/6 denies a release unless BOUND_FENCE, and 5.9/4 denies a verdict
unless AUTHORISED (D8).  A forged NO_EFFECT, the part 1 attack, cannot mint replacement credit because it cannot
carry a signature the witness pins.

The outcome envelope (v0.6).  The v0.4 review substituted the unsigned result beside a genuine report and the
governor returned it.  Now the report's signed fields include result_digest, and verify_effect_report checks a
returned result against it: a result the gate's signature does not cover is refused (OutcomeInvalid) and never
stored.  The witness still derives the label from the report alone; the digest is for whoever holds the result.
"""
import json
from dataclasses import dataclass, asdict

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .binding import result_digest
from .receipts import Signer

FENCE_REPORT, EFFECT_REPORT = 'FENCE_REPORT', 'EFFECT_REPORT'
FENCED_NO_START = 'FENCED_NO_START'
VERDICTS = ('EFFECT', 'NO_EFFECT', 'UNKNOWN')


class OutcomeInvalid(Exception):
    """The returned result is not the one the gate's signed report covers, or the report is not the gate's."""


@dataclass(frozen=True)
class Evidence:
    kind: str          # FENCE_REPORT or EFFECT_REPORT
    root: str
    aid: str
    nonce: str | None  # EFFECT_REPORT: the intent's nonce; FENCE_REPORT: None
    claim: str         # FENCED_NO_START, or a verdict
    signer: str        # the gate's public key, hex
    signature: str     # hex
    result_digest: str | None = None   # v0.6, EFFECT_REPORT: sha256 of the canonical result the gate returned

    def message(self) -> bytes:
        body = {k: getattr(self, k) for k in ('kind', 'root', 'aid', 'nonce', 'claim', 'result_digest')}
        return json.dumps(body, sort_keys=True, separators=(',', ':')).encode()

    def to_json(self) -> dict:
        return asdict(self)


class GateSigner(Signer):
    """The gate's key.  Signs fence reports and effect reports."""

    def _sign(self, kind, root, aid, nonce, claim, rdigest=None) -> Evidence:
        unsigned = Evidence(kind, root, aid, nonce, claim, self.public_hex, '', rdigest)
        return Evidence(kind, root, aid, nonce, claim, self.public_hex, self._key.sign(unsigned.message()).hex(), rdigest)

    def fence_report(self, root: str, aid: str) -> Evidence:
        return self._sign(FENCE_REPORT, root, aid, None, FENCED_NO_START)

    def effect_report(self, root: str, aid: str, nonce: str, verdict: str, result=None) -> Evidence:
        """result: what the gate returns beside the report; its digest is signed (v0.6).  None digests to the digest of null."""
        if verdict not in VERDICTS:
            raise ValueError(verdict)
        return self._sign(EFFECT_REPORT, root, aid, nonce, verdict, result_digest(result))


def _parse(raw) -> Evidence | None:
    if not isinstance(raw, dict):
        return None
    try:
        e = Evidence(raw['kind'], raw['root'], raw['aid'], raw.get('nonce'), raw['claim'], raw['signer'], raw['signature'], raw.get('result_digest'))
    except (KeyError, TypeError):
        return None
    if not all(isinstance(x, str) for x in (e.kind, e.root, e.aid, e.claim, e.signer, e.signature)):
        return None
    if e.nonce is not None and not isinstance(e.nonce, str):
        return None
    if e.result_digest is not None and not isinstance(e.result_digest, str):
        return None
    return e


def _genuine(e: Evidence, pinned_gate_keys) -> bool:
    if e.signer not in pinned_gate_keys:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(e.signer)).verify(bytes.fromhex(e.signature), e.message())
        return True
    except (InvalidSignature, ValueError):
        return False


def derive_release_label(raw, pinned_gate_keys, root: str, aid: str) -> str:
    e = _parse(raw)
    if e is None or e.kind != FENCE_REPORT or e.claim != FENCED_NO_START or not _genuine(e, pinned_gate_keys):
        return 'NONE'
    if e.root != root or e.aid != aid:
        return 'WRONG_BINDING'
    return 'BOUND_FENCE'


def derive_verdict(raw, pinned_gate_keys, root: str, aid: str, nonce: str | None) -> tuple[str, str]:
    e = _parse(raw)
    if e is None or e.kind != EFFECT_REPORT or e.claim not in VERDICTS or not _genuine(e, pinned_gate_keys):
        return 'UNKNOWN', 'NONE'
    if e.root != root or e.aid != aid or nonce is None or e.nonce != nonce:
        return e.claim, 'WRONG_BINDING'
    return e.claim, 'AUTHORISED'


def verify_effect_report(raw, pinned_gate_keys, root: str, aid: str, nonce: str, result) -> str:
    """The governor's check on what a gate host returned (v0.6).  Returns the claim; raises OutcomeInvalid unless the
    report is a pinned gate's genuine EFFECT_REPORT for this root, attempt and nonce, and its digest covers `result`."""
    pinned = (pinned_gate_keys,) if isinstance(pinned_gate_keys, str) else tuple(pinned_gate_keys)
    claim, label = derive_verdict(raw, pinned, root, aid, nonce)
    if label != 'AUTHORISED':
        raise OutcomeInvalid(f'report not authorised: {label}')
    if _parse(raw).result_digest != result_digest(result):
        raise OutcomeInvalid('the result is not the one the gate signed for')
    return claim
