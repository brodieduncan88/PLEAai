"""The witness: in process (v0) or behind an HTTP service (v0.1).  Both sign receipts; both derive labels from
evidence (v0.2, G03).

The contract receives ACCEPT_RESERVATION, ACCEPT_INTENT, RELEASE and RECONCILE only as facts the witness has
accepted.  Each acceptance is its own transaction, separate from the local commit it accepts.  Every acceptance
returns a signed receipt (receipts.py).  A RELEASE or RECONCILE never carries a label from the caller: it carries a
gate-signed report, and the witness derives the label (evidence.py).

Witness        applies acceptances through a store opened with the plea_witness credential, and signs.
RemoteWitness  the client of witness_service.py: POSTs the acceptance, parses the receipt, verifies its signature
               against the pinned public key at once, and raises WitnessUnavailable when the service cannot be
               reached (the caller retries; acceptances are idempotent by contract, 5.2/2 and 5.5/2).
"""
import json
import threading
import time
import urllib.error
import urllib.request

from .evidence import derive_release_label, derive_verdict
from .binding import evidence_digest
from .receipts import ACCEPTANCES, WITNESSED, Receipt, ReceiptInvalid, Signer, verify, verify_signed
from .store import Store, Decision
from .tls import TLSClient, TransportError, is_transport_error

EVIDENCE_OPS = ('RELEASE', 'RECONCILE')


class WitnessUnavailable(Exception):
    pass


def _nonce_of(store: Store, root_id: str, aid: str):
    state, _, _ = store.state(root_id)
    a = state.attempt(aid)
    return None if a is None else a.nonce


def nonce_in(observation: dict, aid: str):
    """The nonce an attempt holds in a committed observation (section 7 tuple: aid, req, phase, nonce, receipt, crossed)."""
    for a in observation.get('attempts', ()):
        if a[0] == aid:
            return a[3]
    return None


def binding_for(op, decision_kind: str, decision_code: str, observation: dict, evidence=None):
    """What a receipt binds.  ACCEPT_INTENT (v0.6) and CROSS (v0.7): the attempt's nonce from the committed state, when
    the intent was accepted or the crossing recorded (CROSS DENIED ALREADY_CROSSED still names a crossing).  RELEASE and
    RECONCILE (v0.7): the digest of the evidence submitted, whatever was decided, so a replayed receipt is refused."""
    if op[0] == 'ACCEPT_INTENT' and decision_kind in ('APPLIED', 'DUPLICATE'):
        return nonce_in(observation, op[1])
    if op[0] == 'CROSS' and (decision_kind == 'APPLIED' or (decision_kind == 'DENIED' and decision_code == 'ALREADY_CROSSED')):
        return nonce_in(observation, op[1])
    if op[0] in EVIDENCE_OPS:
        return evidence_digest(evidence)
    return None


def derive_op(store: Store, pinned_gate_keys, root_id: str, op, evidence) -> tuple:
    """Turn ('RELEASE', a) or ('RECONCILE', a) plus a report into the contract's labelled operation."""
    if len(op) != 2:
        raise ValueError('labels are derived from evidence, not supplied')
    if op[0] == 'RELEASE':
        return ('RELEASE', op[1], derive_release_label(evidence, pinned_gate_keys, root_id, op[1]))
    verdict, label = derive_verdict(evidence, pinned_gate_keys, root_id, op[1], _nonce_of(store, root_id, op[1]))
    return ('RECONCILE', op[1], verdict, label)


class Witness:
    def __init__(self, store: Store, signer: Signer | None = None, delay: float = 0.0, gate_keys=()):
        self.store, self.signer, self.delay = store, signer or Signer(), delay
        self.gate_keys = tuple(gate_keys)

    @property
    def public_key(self) -> str:
        return self.signer.public_hex

    def accept(self, root_id: str, op, evidence=None) -> tuple[Decision, Receipt]:
        if not op or op[0] not in WITNESSED:
            raise ValueError(f'not a witnessed operation: {op!r}')
        if op[0] in EVIDENCE_OPS:
            op = derive_op(self.store, self.gate_keys, root_id, tuple(op), evidence)
        if self.delay:
            time.sleep(self.delay)                      # acceptance in flight (G02b)
        decision, obs, seq, digest = self.store.apply_ex(root_id, op, evidence, op[-1] if evidence is not None else None)
        return decision, self.signer.sign(root_id, op[1], seq, op, decision.kind, decision.code, digest, binding_for(op, decision.kind, decision.code, obs, evidence))

    def cross(self, root_id, aid):              return self.accept(root_id, ('CROSS', aid))          # v0.7: the admission, receipted
    def accept_reservation(self, root_id, aid): return self.accept(root_id, ('ACCEPT_RESERVATION', aid))
    def accept_intent(self, root_id, aid):      return self.accept(root_id, ('ACCEPT_INTENT', aid))
    def release(self, root_id, aid, evidence):  return self.accept(root_id, ('RELEASE', aid), evidence)
    def reconcile(self, root_id, aid, evidence): return self.accept(root_id, ('RECONCILE', aid), evidence)

    def verify_receipt(self, receipt: Receipt, root_id: str, aid: str, op_name: str = 'ACCEPT_INTENT') -> None:
        verify(receipt, self.public_key, root_id, aid, op_name)

    def accept_intent_async(self, root_id: str, aid: str) -> threading.Thread:
        t = threading.Thread(target=self.accept_intent, args=(root_id, aid), daemon=True)
        t.start()
        return t


class RemoteWitness:
    def __init__(self, url: str, public_key=None, timeout: float = 10.0, tls: TLSClient | None = None):
        """public_key: one hex key, or a list of keys to accept during a rotation (v0.4); None fetches the current key.
        tls (v0.5): the pinned authority and this client's certificate; the URL is then https."""
        self.url, self.timeout = url.rstrip('/'), timeout
        if tls is not None and not self.url.startswith('https://'):
            raise ValueError(f'TLS is configured but the witness URL is not https: {self.url}')     # v0.7
        self.ctx = tls.context() if tls else None
        self.public_key = public_key or self._fetch_public_key()

    def _fetch_public_key(self) -> str:
        try:
            with urllib.request.urlopen(self.url + '/pubkey', timeout=self.timeout, context=self.ctx) as r:
                return json.load(r)['public_key']
        except (urllib.error.URLError, ConnectionError, OSError) as exc:
            if is_transport_error(exc):
                raise TransportError(f'{self.url}: {exc}')
            raise WitnessUnavailable(str(exc))

    def accept(self, root_id: str, op, evidence=None, crash_at: str | None = None) -> tuple[Decision, Receipt]:
        if not op or op[0] not in WITNESSED:
            raise ValueError(f'not a witnessed operation: {op!r}')
        body = json.dumps({'root': root_id, 'op': list(op), 'evidence': evidence}).encode()
        headers = {'Content-Type': 'application/json'}
        if crash_at:
            headers['X-Plea-Crash-At'] = crash_at                  # test only: the service dies at that point
        req = urllib.request.Request(self.url + '/accept', data=body, headers=headers, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self.ctx) as r:
                payload = json.load(r)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors='replace')[:200]
            if exc.code == 400:
                raise ValueError(f'witness rejected the input: {detail}')
            if exc.code == 403:
                raise PermissionError(detail)
            raise WitnessUnavailable(f'HTTP {exc.code}: {detail}')
        except (urllib.error.URLError, ConnectionError, OSError) as exc:
            if is_transport_error(exc):
                raise TransportError(f'{self.url}: {exc}')     # not retried: the transport refused us
            raise WitnessUnavailable(str(exc))
        receipt = Receipt.from_json(payload['receipt'])
        verify_signed(receipt, self.public_key, root_id, op[1], op[0])   # the signature, before anything else trusts it (amendment 1)
        if op[0] in EVIDENCE_OPS and receipt.binding != evidence_digest(evidence):
            raise ReceiptInvalid('the receipt does not bind the evidence submitted: a replayed receipt')   # v0.7
        return Decision(receipt.kind, receipt.code), receipt              # v0.6: the signed fields, never the unsigned outer ones

    def cross(self, root_id, aid):              return self.accept(root_id, ('CROSS', aid))
    def accept_reservation(self, root_id, aid): return self.accept(root_id, ('ACCEPT_RESERVATION', aid))
    def accept_intent(self, root_id, aid):      return self.accept(root_id, ('ACCEPT_INTENT', aid))
    def release(self, root_id, aid, evidence):  return self.accept(root_id, ('RELEASE', aid), evidence)
    def reconcile(self, root_id, aid, evidence): return self.accept(root_id, ('RECONCILE', aid), evidence)

    def verify_receipt(self, receipt: Receipt, root_id: str, aid: str, op_name: str = 'ACCEPT_INTENT') -> None:
        verify(receipt, self.public_key, root_id, aid, op_name)
