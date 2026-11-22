"""The SDK surface, v0.6: one governed call runs the whole attempt lifecycle through the store, the witness and,
in host mode, the gate host; a retry resumes it from wherever it stopped and never executes twice.

    gov = Governor(local_store, witness, root='billing-agent', budget=3, replacement=1, host=GateHostClient(url))
    result = gov.attempt('charge:order-42', 'charge', order_id=42, amount=10)     # host mode: a tool name

    gov = Governor(local_store, witness, root=..., gate=GateSigner())              # in-process mode (v0.2)
    result = gov.attempt('charge:order-42', charge, 42, 10)                        # a callable; this process is the gate

Lifecycle of one call (contract v3.1, section 5):
  RESERVE(a, q) -> witness ACCEPT_RESERVATION (receipt stored) -> TOKEN -> START(a, n) -> witness ACCEPT_INTENT
  (receipt stored, binding n) -> RECEIPT, behind the verified receipt -> CROSS, the admission -> the run -> witness
  RECONCILE on the gate's signed report -> the outcome stored.

What v0.6 changed, after the v0.4 review:
  - CROSS is applied before the dispatch, not after.  CROSS is where the contract checks that the run is ACTIVE and
    OPEN (5.7/4), so a HOLD or STOP accepted before the crossing means nothing is dispatched.  An attempt that has
    crossed is admitted work: a HOLD or STOP after that does not retract it, and its outcome is reconciled when the
    run is active again.  The window between the crossing and the host receiving the request is the admitted-work
    window; it is the same window the in-process gate has had since v0.2.
  - v0.7: the crossing is applied by the witness and receipted (the admission), and the gate host runs nothing
    without that receipt.  The local credential cannot set `crossed` (store.py AUTHORITY), so a caller that skips
    this governor and asks the host directly still has to obtain the witness's CROSS, which the contract denies on
    a held or stopped run.  An UNKNOWN outcome is not final: a retry asks the host again, and a verdict the host has
    learned since is reconciled and stored.
  - The nonce is binding.nonce_for(root, a, executor, tool, arguments): the witness's intent receipt carries it, and
    the host runs nothing whose nonce the witness did not accept or whose action and executor do not hash to it.
    The same request key with another action computes another nonce, which START refuses: RequestKeyReused.
  - The host's result is accepted only when the host's signed effect report covers its digest (OutcomeInvalid
    otherwise; nothing is stored, and the retry fetches the host's stored result).
  - Every terminal outcome is stored with the executor's signed effect report and replayed only once that report
    re-verifies against the pinned executor key, this attempt and nonce, with its digest covering the value returned
    (v1.0: the results table is a cache the gateway can be made to write; it is never trusted on its own): a value,
    a no-effect (NoEffect again), an unknown verdict (RuntimeError again).  A retry of an unfinished attempt resumes: every step is idempotent by contract (E8), the
    crossing is one-shot (ALREADY_CROSSED continues), and the host answers an admitted attempt with its stored
    result and report.  InProgress is raised only when the host reports that the attempt is running right now.

The local store holds the plea_local credential, so even this code cannot apply an acceptance itself (W1).
"""
import hashlib
import re

from .binding import nonce_for
from .evidence import GateSigner, OutcomeInvalid, verify_effect_report
from .receipts import Receipt, ReceiptInvalid
from .store import Store, Decision, AuthorityError, RootExists, UnknownRoot


class GovernedError(Exception):
    def __init__(self, decision: Decision, stage: str):
        super().__init__(f'{stage}: {decision.kind} ({decision.code})')
        self.decision, self.stage = decision, stage


class BudgetExhausted(GovernedError):
    pass


class Held(GovernedError):
    pass


class Stopped(GovernedError):
    pass


class InProgress(GovernedError):
    """The attempt under this request key is running at the host right now (a concurrent duplicate)."""


class NoEffect(Exception):
    """Raised by a governed function to declare, with evidence, that it had no effect."""


class GateRefusedRun(Exception):
    """The gate host refused to run the attempt (receipt invalid, not bound, fenced)."""


class RequestKeyReused(Exception):
    """The request key is bound to a different action (tool, arguments or executor) than this call's."""


class VerdictRefused(GovernedError):
    """The run happened, but the witness refused the gate's verdict (for example, the gate's key is not one the witness
    pins).  The attempt stays charged; `result` carries what the gate returned, so nothing is hidden, and nothing is
    stored, so a retry asks again."""
    def __init__(self, decision: Decision, stage: str, result):
        super().__init__(decision, stage); self.result = result


class OutcomeUnavailable(Exception):
    """The verdict is final but the outcome was never stored and there is no host to ask (in-process mode).  The
    audit log holds the verdict; the function is not run again."""


def _raise_for(decision: Decision, observation: dict, stage: str):
    if observation['witness'] == 'HELD':
        raise Held(decision, stage)
    if observation['business'] != 'OPEN':
        raise Stopped(decision, stage)
    if decision.code == 'BUDGET_EXHAUSTED':
        raise BudgetExhausted(decision, stage)
    raise GovernedError(decision, stage)


LEGACY_AID = re.compile(r'a-[0-9a-f]{16}')
CURRENT_AID = re.compile(r'a2-[0-9a-f]{64}')


class IdentityFormsMixed(Exception):
    """A budget holds attempts of both forms of identity: no further attempt is made on it (Amendment 17, second review M3)."""


def attempt_id(request_key: str, legacy: bool = False) -> str:
    """Amendment 17 (22 November 2026, D21): the whole SHA-256 of the request key, 256 bits, marked 'a2-'.  Before it the
    identity was 'a-' and 64 bits, so two request keys met after about 2^32 hashes and the second was refused for ever
    (the store's ATTEMPT_BOUND_TO_OTHER_REQUEST).  legacy=True gives that earlier form, for a budget that already holds it
    (identity_form): such a budget keeps it, so that a call made before the change, retried after it, is the same attempt."""
    h = hashlib.sha256(request_key.encode()).hexdigest()
    return 'a-' + h[:16] if legacy else 'a2-' + h


def identity_form(store, root: str) -> str:
    """The form of attempt identity, and of request key, a budget uses for every attempt: 'legacy' when it already holds an
    attempt of the 64-bit form made before Amendment 17, else 'current'.  (Amendment 17, after its first review, H1.)

    Without this, a budget with runs from before the change got attempts of the new form for the same request keys: a call
    made before and retried after was run a second time, a design sent again was charged again, a pending run was left for
    ever, and the budget's record mixed two forms and could not verify.  A budget of the earlier form keeps 64-bit identities;
    the engineer moves to the current form by baselining again.

    A budget whose attempts are of both forms makes no further attempt: IdentityFormsMixed is raised, and nothing is run (after
    the second review, M3: the rule was once "any attempt of the earlier form", so a caller holding the service's database role
    could add one to a budget of the current form and turn it to 64 bits, after which a design decided before was run again).
    That role can still make a new budget's first attempt one of the earlier form, and so keep that budget at 64 bits, or add
    one to a budget of the current form and so stop all its runs; it can already refuse runs on a budget in other ways.  Names
    of neither form (made by that role) do not count.  UnknownRoot is raised for a budget that does not exist, as the attempt
    itself would raise it."""
    obs = store.observe(root)
    forms = {'legacy' if LEGACY_AID.fullmatch(str(a[0])) else 'current' if CURRENT_AID.fullmatch(str(a[0])) else None for a in obs.get('attempts', ())} - {None}
    if len(forms) > 1:
        raise IdentityFormsMixed(f'{root}: its attempts are of both forms of identity; no further attempt is made on it')
    return 'legacy' if forms == {'legacy'} else 'current'


def _phase_in(observation: dict, aid: str):
    for a in observation.get('attempts', ()):
        if a[0] == aid:
            return a[2]
    return None


class Governor:
    def __init__(self, store: Store, witness, root: str, budget: int, replacement: int = 0, admin: Store | None = None,
                 gate: GateSigner | None = None, host=None, control: Store | None = None):
        """store: the local credential, all a production agent process holds.  The root must already be provisioned
        (v1.1: a budget is provisioned by the control plane -- plea_ctl.py ROOT provision -- and the gateway credential
        cannot create one); with neither control= nor admin= this constructor refuses an unprovisioned root.
        control: the control-plane credential (plea_control), for an operator process: it provisions the root if it
        does not exist and drives the operator mode changes (hold/stop/terminalise/terminal/recover/reregister);
        without it those methods raise (no fallback to admin).  admin: the owner, a provisioning convenience for tests
        only; never in an agent process.  gate: this process is the gate and
        signs reports (v0.2 mode).  host: a GateHostClient; this process holds no gate key (v0.4 mode).  Exactly one
        of gate and host; with neither, an in-process gate key is generated."""
        if gate is not None and host is not None:
            raise ValueError('a governor is either the gate (gate=) or a client of a gate host (host=), not both')
        self.store, self.witness, self.root, self.host = store, witness, root, host
        self.control = control                          # v1.0: the mode-changing credential; never the gateway store, never the owner by default
        self.gate = None if host is not None else (gate or GateSigner())
        provisioner = control or admin                  # v1.1: never the gateway store
        if provisioner is not None:
            try:
                provisioner.new_root(root, budget, replacement)
            except RootExists:
                pass                                    # the root already carries its immutable budget
        else:
            try:
                store.observe(root)
            except UnknownRoot:
                raise UnknownRoot(f'{root}: not provisioned; the control plane provisions a budget first '
                                  f'(plea_ctl.py {root} provision --budget {budget} --replacement {replacement})') from None

    @property
    def executor(self) -> str:
        """The gate key every action is bound to: the host's pinned key, or this process's own."""
        return self.host.public_key if self.host is not None else self.gate.public_hex

    def _must(self, op, stage: str, allow_duplicate: bool = False) -> Decision:
        d, obs = self.store.apply(self.root, op)
        if d.kind == 'APPLIED' or (allow_duplicate and d.kind == 'DUPLICATE'):
            return d
        _raise_for(d, obs, stage)

    def _accepted(self, decision: Decision, stage: str) -> None:
        if decision.kind not in ('APPLIED', 'DUPLICATE'):
            _raise_for(decision, self.store.observe(self.root), stage)

    def _verdict_accepted(self, decision: Decision, result) -> None:
        """After RECONCILE: Held or Stopped when the run's state refused it (recoverable); VerdictRefused otherwise."""
        if decision.kind in ('APPLIED', 'DUPLICATE'):
            return
        obs = self.store.observe(self.root)
        if obs['witness'] == 'HELD' or obs['business'] != 'OPEN':
            _raise_for(decision, obs, 'RECONCILE')
        raise VerdictRefused(decision, 'RECONCILE', result)

    # ------------------------------------------------------------------ the receipt barrier
    def _verified_intent_receipt(self, aid: str, receipt: Receipt | None, nonce: str | None = None) -> Receipt:
        if receipt is None:
            stored = self.store.get_receipt(self.root, aid, 'ACCEPT_INTENT')
            if stored is None:
                raise ReceiptInvalid('no receipt for this attempt')
            receipt = Receipt.from_json(stored)
        self.witness.verify_receipt(receipt, self.root, aid, 'ACCEPT_INTENT')           # key, fields, signature
        if self.store.decision_hash(self.root, receipt.seq) != receipt.hash:              # this store's own chain
            raise ReceiptInvalid('receipt does not match the audit chain')
        if nonce is not None and receipt.binding != nonce:                                # v0.6: the witness accepted this action
            raise ReceiptInvalid('the witness accepted a different nonce for this attempt')
        return receipt

    def _stored_admission(self, aid: str) -> Receipt | None:
        stored = self.store.get_receipt(self.root, aid, 'CROSS')
        return None if stored is None else Receipt.from_json(stored)

    def gate_cross(self, aid: str, receipt: Receipt | None = None, nonce: str | None = None) -> tuple[Decision, Receipt | None]:
        """Apply RECEIPT, then ask the witness to apply CROSS (v0.7) behind a verified receipt for this attempt's accepted
        intent.  CROSS is the admission: DENIED unless the run is ACTIVE and OPEN; ALREADY_CROSSED means this attempt
        was admitted earlier (a resume).  Returns the decision and the admission receipt the host will require."""
        self._verified_intent_receipt(aid, receipt, nonce)
        self._must(('RECEIPT', aid), 'RECEIPT', allow_duplicate=True)
        d, admission = self.witness.cross(self.root, aid)
        if d.kind == 'APPLIED' or (d.kind == 'DENIED' and d.code == 'ALREADY_CROSSED'):
            self.store.put_receipt(self.root, aid, admission.seq, admission.to_json(), 'CROSS')
            return d, admission
        obs = self.store.observe(self.root)
        if d.kind == 'DENIED' and d.code == 'NOT_CONSUMED' and _phase_in(obs, aid) in ('EFFECT', 'NO_EFFECT'):
            return d, self._stored_admission(aid)      # the verdict is already final (a resume after the verdict, before the outcome was stored)
        _raise_for(d, obs, 'CROSS')

    # ------------------------------------------------------------------ one governed call
    def _action(self, fn_or_tool, args, kwargs) -> tuple[str, dict]:
        if self.host is not None:
            if args:
                raise TypeError('host mode takes keyword arguments only: the tool name, then its arguments')
            return str(fn_or_tool), dict(kwargs)
        return f'{fn_or_tool.__module__}.{fn_or_tool.__qualname__}', {'args': list(args), 'kwargs': dict(kwargs)}

    def _replay(self, outcome: dict, nonce: str, aid: str | None = None, tool: str | None = None, arguments=None):
        if outcome.get('nonce') != nonce:                    # v1.0: a stored outcome must carry this action's nonce; a missing one is refused too
            raise RequestKeyReused('this request key is bound to a different action')
        kind = outcome.get('outcome', 'value')
        if kind in ('value', 'no_effect'):
            # v1.0: the results table is a cache; a stored outcome is never trusted on its own.  It is replayed only
            # once the executor's signed effect report stored with it re-verifies against the pinned executor key for
            # this root, attempt and nonce, with the report's digest covering exactly what is returned (the v0.9
            # review returned a fabricated cache row as a successful payment, before any admission).
            if aid is None:
                raise OutcomeInvalid('a stored outcome can only be replayed for a named attempt')
            report = outcome.get('report')
            if not isinstance(report, dict):
                raise OutcomeInvalid('the stored outcome carries no signed effect report')
            result = outcome['value'] if kind == 'value' else outcome.get('result')
            claim = verify_effect_report(report, self.executor, self.root, aid, nonce, result)
            if claim != ('EFFECT' if kind == 'value' else 'NO_EFFECT'):
                raise OutcomeInvalid(f'the stored outcome ({kind}) does not match its signed report ({claim})')
            if kind == 'value':
                return outcome['value']
            raise NoEffect()
        if self.host is not None and aid is not None:
            return self._requery(aid, nonce, tool, arguments, outcome)   # v0.7: unknown is not final; the host may know more now
        raise RuntimeError(outcome.get('detail', 'the verdict for this attempt is UNKNOWN'))

    def _store_outcome(self, aid: str, nonce: str, outcome: dict, report: dict):
        """Store a terminal outcome together with the executor's signed effect report, then return it through the
        same verification every later replay uses (v1.0): what is returned now is exactly what is returned later."""
        stored = dict(outcome, nonce=nonce, report=report)
        self.store.put_result(self.root, aid, stored)
        return self._replay(stored, nonce, aid)

    def _call_host(self, aid, nonce, receipt, admission, tool, arguments) -> dict:
        try:
            return self.host.run(self.root, aid, nonce, receipt, tool, arguments, admission=admission)   # the host verifies both receipts and runs once
        except Exception as exc:
            status, detail = getattr(exc, 'status', None), getattr(exc, 'detail', '')
            if status is None:
                raise                                   # not a refusal: the transport or the connection; the caller retries, and the retry resumes
            if status == 409 and 'running' in detail:
                raise InProgress(Decision('DENIED', 'RUNNING_AT_HOST'), 'RUN') from None
            raise GateRefusedRun(str(exc)) from None

    def _settle(self, aid, nonce, out) -> object:
        """Verify the host's outcome envelope, reconcile with the witness, store the terminal outcome and replay it."""
        claim = verify_effect_report(out.get('report'), self.host.public_key, self.root, aid, nonce, out.get('result'))   # the outcome envelope (v0.6)
        d, _ = self.witness.reconcile(self.root, aid, out['report'])                 # the host's signed verdict
        if claim == 'UNKNOWN':
            if d.kind != 'NOOP':
                self._verdict_accepted(d, out.get('result'))                        # v0.7: held or stopped: nothing is stored
            detail = f"tool outcome unknown at the gate host: {out.get('result')}"[:300]
            self.store.put_result(self.root, aid, {'outcome': 'unknown', 'detail': detail, 'nonce': nonce})
            raise RuntimeError(detail)
        self._verdict_accepted(d, out.get('result'))
        if claim == 'NO_EFFECT':
            return self._store_outcome(aid, nonce, {'outcome': 'no_effect', 'result': out.get('result')}, out['report'])
        return self._store_outcome(aid, nonce, {'outcome': 'value', 'value': out['result']}, out['report'])

    def _requery(self, aid, nonce, tool, arguments, stored: dict):
        receipt = self._verified_intent_receipt(aid, None, nonce)
        out = self._call_host(aid, nonce, receipt, self._stored_admission(aid), tool, arguments)
        return self._settle(aid, nonce, out)

    def attempt(self, request_key: str, fn_or_tool, *args, **kwargs):
        aid = attempt_id(request_key, identity_form(self.store, self.root) == 'legacy')     # Amendment 17: the budget's own form
        tool, arguments = self._action(fn_or_tool, args, kwargs)
        nonce = nonce_for(self.root, aid, self.executor, tool, arguments)
        stored = self.store.get_result(self.root, aid)
        if stored is not None:
            return self._replay(stored, nonce, aid, tool, arguments)   # the earlier outcome, not a second execution
        d, obs = self.store.apply(self.root, ('RESERVE', aid, request_key))
        if d.kind not in ('APPLIED', 'DUPLICATE'):     # DUPLICATE: an unfinished attempt under this key; resume it
            _raise_for(d, obs, 'RESERVE')
        d, r_res = self.witness.accept_reservation(self.root, aid)
        self._accepted(d, 'ACCEPT_RESERVATION')
        self.store.put_receipt(self.root, aid, r_res.seq, r_res.to_json(), 'ACCEPT_RESERVATION')
        self._must(('TOKEN', aid), 'TOKEN', allow_duplicate=True)
        d, obs = self.store.apply(self.root, ('START', aid, nonce))
        if d.kind == 'DENIED' and d.code == 'ATTEMPT_HOLDS_OTHER_NONCE':
            raise RequestKeyReused('this request key is bound to a different action')
        if d.kind not in ('APPLIED', 'DUPLICATE'):
            _raise_for(d, obs, 'START')
        d, receipt = self.witness.accept_intent(self.root, aid)
        self._accepted(d, 'ACCEPT_INTENT')
        self.store.put_receipt(self.root, aid, receipt.seq, receipt.to_json(), 'ACCEPT_INTENT')
        if self.host is not None:
            return self._run_at_host(aid, nonce, receipt, tool, arguments)
        return self._run_here(aid, nonce, receipt, fn_or_tool, args, kwargs)

    def _run_here(self, aid, nonce, receipt, fn, args, kwargs):
        d, _ = self.gate_cross(aid, receipt, nonce)     # the admission, behind the verified receipt
        if d.kind == 'DENIED':                          # already admitted or already final: never run the function twice in this mode
            raise OutcomeUnavailable(f'attempt {aid} was admitted earlier ({d.code}); its outcome was not stored, and an in-process gate cannot be asked again')
        try:
            value = fn(*args, **kwargs)
        except NoEffect:
            report = self.gate.effect_report(self.root, aid, nonce, 'NO_EFFECT').to_json()
            d, _ = self.witness.reconcile(self.root, aid, report)
            self._verdict_accepted(d, None)
            return self._store_outcome(aid, nonce, {'outcome': 'no_effect', 'result': None}, report)
        except Exception as exc:
            self.witness.reconcile(self.root, aid, self.gate.effect_report(self.root, aid, nonce, 'UNKNOWN', {'error': repr(exc)[:200]}).to_json())
            self.store.put_result(self.root, aid, {'outcome': 'unknown', 'detail': f'the function raised: {exc!r}'[:300], 'nonce': nonce})
            raise
        report = self.gate.effect_report(self.root, aid, nonce, 'EFFECT', value).to_json()
        d, _ = self.witness.reconcile(self.root, aid, report)
        self._verdict_accepted(d, value)
        return self._store_outcome(aid, nonce, {'outcome': 'value', 'value': value}, report)

    def _run_at_host(self, aid, nonce, receipt, tool, arguments):
        _, admission = self.gate_cross(aid, receipt, nonce)   # the admission: ACTIVE and OPEN are checked by the witness's CROSS, before anything is dispatched
        out = self._call_host(aid, nonce, receipt, admission, tool, arguments)
        return self._settle(aid, nonce, out)

    def release(self, aid: str) -> Decision:
        """Release an accepted reservation whose sandbox the gate has fenced with no start."""
        if self.host is not None:
            stored = self.store.get_receipt(self.root, aid, 'ACCEPT_RESERVATION')
            if stored is None:
                raise ReceiptInvalid('no reservation receipt for this attempt')
            out = self.host.fence(self.root, aid, Receipt.from_json(stored))
            return self.witness.release(self.root, aid, out['report'])[0]
        return self.witness.release(self.root, aid, self.gate.fence_report(self.root, aid).to_json())[0]

    # control plane (v0.9: through the control credential, never the gateway store)
    def _ctl(self, op):
        if self.control is None:
            raise AuthorityError('this governor holds no control-plane credential; a mode change needs an explicit control= (plea_control)')
        return self.control.apply(self.root, op)[0]
    def hold(self):        return self._ctl(('HOLD',))
    def stop(self):        return self._ctl(('STOP',))
    def terminalise(self): return self._ctl(('TERMINALISE',))
    def terminal(self):    return self._ctl(('TERMINAL',))
    def recover(self, approved: bool = True, complete: bool = True):
        return self._ctl(('RECOVER', approved, complete))
    def reregister(self):  return self._ctl(('REREGISTER',))
    def status(self):      return self.store.observe(self.root)
