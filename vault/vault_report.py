"""The signed attempt report for one submitter's budget on one holdout.

build() reads, with the vault's own database credential, everything a reader needs to check the record without the
vault: the holdout's manifest, the budget's provisioning record, every audit row, the witness's receipts, the gate
host's signed reports and the results they cover, and for each attempt the arguments it was bound to.  It adds the
submitter's certificate fingerprint, an as-of time and sequence number, and one signature over all of it by the
owner's report key.  plea_verify.py checks a report offline, given three public keys (witness, gate, report).

Outcome of an attempt, from its phase and the gate's reports:
  EFFECT      scored; the result is present
  NO_EFFECT   rejected inside the scoring tool; refunded while refunds are within the replacement allowance
  UNKNOWN     admitted, and the gate signed that it does not know the outcome; charged, never run again
  PENDING     reserved or admitted with no outcome yet; counted as charged

A report is a statement as of its sequence number.  A later one may hold more attempts, so a reader should get the
report from the owner, not from the submitter.
"""
import datetime
import hashlib
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

FORMAT = 'plea-vault-report/1'
RECEIPT_OPS = ('ACCEPT_RESERVATION', 'ACCEPT_INTENT', 'CROSS')
PENDING_PHASES = ('RESERVING', 'RESERVED', 'TOKEN', 'INTENT_PENDING')


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


class ReportKey:
    """The owner's report key (Ed25519).  It signs reports and nothing else."""

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


def score_arguments(manifest_sha256: str, submitter: str, submission_sha256: str) -> dict:
    return {'submission_sha256': submission_sha256, 'manifest_sha256': manifest_sha256, 'submitter': submitter}


def request_key(arguments: dict) -> str:
    """The same rule plea_mcp.py uses: the tool name and a hash of its canonical arguments."""
    return 'score:' + hashlib.sha256(canonical(arguments).encode()).hexdigest()[:24]


def outcome_of(phase: str, evidence: list) -> str:
    if phase in ('EFFECT', 'NO_EFFECT'):
        return phase
    if phase in PENDING_PHASES:
        return 'PENDING'
    if phase == 'CONSUMED':
        claims = [e['evidence'].get('claim') for e in evidence if isinstance(e.get('evidence'), dict)]
        return 'UNKNOWN' if 'UNKNOWN' in claims else 'PENDING'
    return phase                                        # INDETERMINATE, DISCARDED: reported as the contract names them


def build(store, holdout, submitter: str, enrolment: dict, submissions: list, keys: dict, signer: ReportKey, now: str | None = None) -> dict:
    """submissions: the hashes this submitter has uploaded.  keys: {'witness': hex, 'gate': hex}."""
    root = holdout.root(submitter)
    audit, observation = store.audit_snapshot(root)                  # the log and the state from one snapshot
    provisioning = store.provisioning(root)
    by_request = {}
    for sha in submissions:
        args = score_arguments(holdout.manifest_sha256, submitter, sha)
        by_request[request_key(args)] = args
    attempts = []
    for aid, req, phase, nonce, _receipt, _crossed in observation['attempts']:
        evidence = [{'seq': e['seq'], 'evidence': e['evidence']} for e in store.evidence_for(root, aid) if e['seq'] <= len(audit)]
        receipts = {}
        for op in RECEIPT_OPS:
            r = store.get_receipt(root, aid, op)
            if r is not None and r.get('seq', 0) <= len(audit):
                receipts[op] = r
        stored = store.get_result(root, aid)
        result = stored.get('value') if isinstance(stored, dict) and stored.get('outcome', 'value') == 'value' and phase == 'EFFECT' else None
        attempts.append({'aid': aid, 'request_key': req, 'arguments': by_request.get(req), 'phase': phase, 'nonce': nonce,
                         'outcome': outcome_of(phase, evidence), 'receipts': receipts, 'evidence': evidence, 'result': result})
    body = {
        'format': FORMAT, 'holdout': holdout.name, 'submitter': submitter, 'root': root,
        'certificate_sha256': enrolment.get('cert_sha256'),
        'enrolment': {k: enrolment.get(k) for k in ('submitter', 'organisation', 'issued', 'expires')},
        'manifest': holdout.manifest, 'manifest_sha256': holdout.manifest_sha256,
        'keys': {'witness': keys['witness'], 'gate': keys['gate'], 'report': signer.public_hex},
        'provisioning': provisioning, 'audit': audit, 'attempts': attempts,
        'as_of': {'time': now or datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'seq': len(audit),
                  'head': audit[-1]['hash'] if audit else (provisioning or {}).get('hash')},
    }
    body = json.loads(json.dumps(body))                                # plain JSON types, exactly what a reader will parse
    return dict(body, signature={'signer': signer.public_hex, 'signature': signer.sign(canonical(body).encode())})
