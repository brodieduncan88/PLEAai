#!/usr/bin/env python3
"""The verification service's front door: the one address an assistant-side process talks to.

    front_door.py --home HOME --port 8973 --local-dsn DSN --witness-url URL --witness-key HEX --gate-host URL --gate-key HEX
                  --engineer-key HEX --tls-cert CERT --tls-key KEY --tls-ca CA --upstream-cert CERT --upstream-key KEY

Why it exists.  In the first plug-in (verify_client.py) the assistant-side process held the gateway's database
credential and chose the `baseline_sha256` it sent.  The gate's tool cannot see which budget an attempt was admitted
under, so a caller could run a design against one baseline while charging another baseline's budget, and be told
PASS.  The offline check of the record catches that afterwards (checks 5 and 6), but the wrong answer had already
been given and the record could no longer be made to verify.  AMENDMENT_2026-11-11.md records the finding.

What it changes.  The governor moves to the service side, into this process.  A caller is the common name of its
client certificate: a job.  A job is bound, by a statement the responsible engineer signed (front_ctl.py), to exactly
one baseline.  No request names a baseline, a budget, a check or an attempt; the front door fills those in from the
job's binding, so the budget charged and the baseline decided against are always the same one.

  GET  /requirement   the baselined requirement of the caller's job, as text and as fields.  Read-only.
  GET  /baseline      the signed baseline envelope, as stored.  Read-only.
  POST /submit        the body is exactly {"design": {...}}.  One official run: the witness admits it, the gate host
                      runs the declared check once and signs the verdict.  The same design again returns the same
                      verdict with no second run.
                      -> 200 {"outcome": "PASS" | "FAIL" | "UNKNOWN" | "INTERRUPTED", "exit", "text", "verdict", ...}
                         400 the request is not a design (nothing is run and nothing is recorded)
                         403 not enrolled, or no budget      409 stopped, held, exhausted, or already running
                         502 the service refused its own step        503 a part of the service could not be reached, or the
                         service has not shown that it can write a notice to the engineer's inbox: nothing is run, and the
                         engineer is sent a notice where one can be written (Amendment 8)
                         507 the journal is at its size limit, the job's baseline has used its share of it (Amendment 8), or the
                         disk is below the space kept for notices: nothing is run, and the engineer is sent a notice (Amendments 7, 8)
  GET  /status        every official run on the job's baseline, and whether any design has met the check.
  anything else       404.  There is no path here that baselines, revises, acknowledges, builds a record or reads a key.

What this process holds: the gateway's database credential (it cannot provision, stop or rewrite a budget), a client
certificate named `frontdoor` for the witness service and the gate host, and three public keys.  It holds no signing
key.  The witness service and the gate host admit only `frontdoor`, so a job certificate cannot reach them.

What the caller holds: a certificate for its job, and this service's address.  No database credential, no key that
signs anything, no copy of the check.

A request that is not a design is refused before anything else happens.  "Not a design" is decided here from the bytes
alone: over 16 KiB, not strict JSON (a repeated key, NaN, an infinite number), a number the database would hand back
changed (Amendment 2: 1e16 or more in size with a decimal point or an exponent, or negative zero), a name or a text value holding a
character that is not printable (a control character, a line separator, half a surrogate pair), not exactly
{"design": object}, or nested more than four deep.  Such a request could not be stored, or could put a line of its
own into the notice the engineer reads.  Everything else, including a design outside the baselined design space, goes
to the gate and is an official run with a signed verdict, as before.
"""
import argparse
import collections
import hashlib
import json
import os
import pathlib
import re
import shutil
import ssl
import sys
import threading
import time
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from plea_gateway import (BudgetExhausted, GateRefusedRun, GovernedError, Held, InProgress, OutcomeInvalid, ReceiptInvalid,   # noqa: E402
                          RequestKeyReused, Store, Stopped, TransportError, UnknownRoot, WitnessUnavailable)
from plea_gateway.tls import TLSHandlerMixin, add_server_args, server_from_args, wrap_server   # noqa: E402
from baseline import HEADLINE, canonical, design_hash, design_lines, face, root_for   # noqa: E402  (design_hash: Amendment 17)
from plea_gateway.governor import identity_form             # noqa: E402  (Amendment 17)
from service_client import Client, alongside_lines                   # noqa: E402  (Amendment 17: moved from verify_client, which is retired)
from verify_record import PENDING_PHASES, arguments_for, load_envelope, request_key, request_keys, signed_by   # noqa: E402  (request_keys: Amendment 17)
import notices                                                       # noqa: E402  (Amendment 7: a notice the inbox cannot take is kept, not lost)
import front_state                                                   # noqa: E402  (Amendment 17, D16)

JOB_NAME = re.compile(r'^[a-z0-9][a-z0-9-]{1,40}$')
RESERVED = ('frontdoor', 'front', 'witness', 'host', 'governor', 'engineer')
HEX64 = re.compile(r'^[0-9a-f]{64}$')
MAX_BODY = 16384
MAX_DEPTH = 4
EVENTS = ('ENROL', 'REBIND', 'REVOKE')
BINDING_FIELDS = ('event', 'seq', 'job', 'baseline_sha256', 'root', 'cert_sha256', 'previous', 'time', 'note')
JOURNAL_MAX = 1 << 30            # bytes the journal of submissions may reach; at that size the door refuses new runs (Amendment 7, D1)
DISK_RESERVE = 512 << 20         # free bytes the journal's disk keeps for notices; below that the door refuses new runs (Amendment 7, D1)
SWEEP_AFTER = 120.0               # seconds a run is seen pending before the front door asks the gate for it itself (Amendment 9)
SWEEP_EVERY = 30.0                   # seconds between the front door's looks for runs left pending (Amendment 9)
SWEEP_MIN_WAIT = 1.0                 # the shortest wait the look takes, whatever it is given (Amendment 9)
SWEEP_MAX_WAIT = 3600.0              # the longest the look waits before it acts on one run again (Amendment 9)
SWEEP_MAX_ASKS = 12                  # how often the look acts on one run before it leaves it as it is, until the front door restarts (Amendment 9)
JOURNAL_SHARE = 64 << 20         # bytes of the journal one baseline's designs may take; at that size the door refuses new runs for it alone (Amendment 8, D1)
HEX_BYTES = set(b'0123456789abcdef')


# ---------------------------------------------------------------------------------------------------- job bindings
def binding_message(b: dict) -> bytes:
    """What the responsible engineer signs when a job is enrolled, moved to a revision, or revoked."""
    return canonical({k: b.get(k) for k in BINDING_FIELDS}).encode()


def jobs_path(home) -> pathlib.Path:
    return pathlib.Path(home) / 'front' / 'jobs.json'


def read_jobs(home) -> dict:
    """{job: its current signed binding}.  An unreadable file admits nobody."""
    try:
        jobs = json.loads(jobs_path(home).read_text()).get('jobs', {})
        return jobs if isinstance(jobs, dict) else {}
    except (OSError, ValueError, AttributeError):
        return {}


def binding_valid(b, engineer_keys) -> bool:
    """A binding counts only if a pinned engineer key signed exactly these fields."""
    if not isinstance(b, dict) or b.get('event') not in EVENTS or b.get('signer') not in engineer_keys:
        return False
    if not isinstance(b.get('job'), str) or not JOB_NAME.match(b['job']) or b['job'] in RESERVED:
        return False
    if not isinstance(b.get('baseline_sha256'), str) or not HEX64.match(b['baseline_sha256']) or not isinstance(b.get('cert_sha256'), str):
        return False
    if not isinstance(b.get('root'), str) or not isinstance(b.get('seq'), int) or isinstance(b['seq'], bool) or b['seq'] < 1:
        return False
    return signed_by(b['signer'], b.get('signature', ''), binding_message(b))


# ---------------------------------------------------------------------------------------------------- the request body
class BadRequest(Exception):
    pass


def _clean(value, depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        raise BadRequest('nested too deeply')
    if isinstance(value, str):
        if not value.replace(' ', '').isprintable():          # control and format characters, line separators, half a surrogate pair, odd spaces
            raise BadRequest('a string holds a character that is not printable')
    elif isinstance(value, dict):
        for k, v in value.items():
            _clean(k, depth + 1); _clean(v, depth + 1)
    elif isinstance(value, list):
        for v in value:
            _clean(v, depth + 1)


def parse_design(raw: bytes):
    """The design from a request body, or BadRequest.  Strict: what is accepted has one canonical form and can be stored."""
    def pairs(items):
        out = {}
        for k, v in items:
            if k in out:
                raise BadRequest('a key is repeated')
            out[k] = v
        return out

    def number(text):
        v = float(text)
        if v != v or v in (float('inf'), float('-inf')):
            raise BadRequest('a number is not finite')
        # Amendment 2.  The database holds a number as a decimal.  A number written with a decimal point or an exponent
        # whose size is 1e16 or more comes back from it as a whole number, and negative zero comes back as zero.  The gate
        # signs the design as it was sent, the stored copy would then differ from what was signed, and the record of
        # the baseline could not verify again.  Such a number is refused here, before anything is run or recorded.
        if abs(v) >= 1e16 or repr(v) == '-0.0':
            raise BadRequest('a number cannot be kept as written: with a decimal point or an exponent its size must be below 1e16, and it must not be negative zero')
        return v

    def constant(name):
        raise BadRequest('NaN and Infinity are not JSON')

    if len(raw) > MAX_BODY:
        raise BadRequest('the request is too large')
    try:
        body = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_float=number, parse_constant=constant)
    except BadRequest:
        raise
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise BadRequest('the request is not JSON')
    if not isinstance(body, dict) or set(body) != {'design'}:
        raise BadRequest('the request must be exactly {"design": {...}}; it cannot name a baseline, a check, a limit or a run')
    design = body['design']
    if not isinstance(design, dict):
        raise BadRequest('the design must be an object of parameters')
    _clean(design)
    return design


# ---------------------------------------------------------------------------------------------------- what is shown
def requirement_text(card: dict, baseline_hash: str, state: str = 'OPEN') -> str:
    """The baselined requirement as an engineer reads it.  The wording of service_client.Client.show (formerly verify_client's), without its command line."""
    req, chk, eng = card['requirement'], card['check'], card['responsible_engineer']
    L = [f"BASELINED REQUIREMENT  {req['id']} rev {req['revision']}: {req['title']}"]
    if state == 'STOPPED':
        L.append(f"  NO FURTHER RUNS ARE ACCEPTED ON THIS BASELINE: {eng['name']} has stopped it (it was superseded or closed).  Ask {eng['name']} which baseline is in force.")
    elif state == 'HELD':
        L.append(f"  RUNS ON THIS BASELINE ARE ON HOLD by {eng['name']}.")
    if card.get('supersedes'):
        s = card['supersedes']
        L.append(f"  THIS BASELINE SUPERSEDES {s['baseline_sha256'][:16]}… ({s.get('official_runs', '?')} official runs, {s.get('not_met', '?')} not met); "
                 f"{s.get('unknown', '?')} unknown, {s.get('met', '?')} met.  Reason given: {s['reason']}")     # Amendment 4: the unknown and met counts too
    L += alongside_lines(card)                                                                      # Amendment 9
    L += [f"  \"{req['statement']}\"", f"  Source: {req['source']}",
          f"  Baselined {card.get('baselined_at', '?')} by {eng['name']}, responsible engineer.  Baseline hash {baseline_hash}", '', 'ACCEPTANCE LIMITS']
    for k in card['criteria']:
        L.append(f"  {k['id']}: {k['quantity']} {'at most' if k['comparison'] == '<=' else 'at least'} {k['limit']} {k['units']}")
    L += ['', 'LOAD CASE', f"  {card['load_case']}", '', 'DESIGN SPACE (what may be varied)']
    for name, rule in card['design_space'].items():
        L.append(f"  {name}: " + ('one of ' + ', '.join(map(str, rule['choice'])) if 'choice' in rule else f"a number from {rule['min']} to {rule['max']}"))
    L += ['', f"DECLARED CHECK  {chk['id']} v{chk['version']}, written by {chk['author']}, reviewed by {chk['reviewed_by']}", '  It does not cover: ' + '; '.join(chk['stated_limits']), '',
          'A design is checked against this baseline only by submitting it to the verification service: an object giving exactly the design-space parameters.',
          'The requirement, the limits, the load case, the design space and the check cannot be changed from here.',
          f"Only {eng['name']} can issue a revised baseline or accept a failure."]
    return '\n'.join(L)


def requirement_fields(card: dict) -> dict:
    chk = card['check']
    return {'requirement': card['requirement'],
            'criteria': [{k: c[k] for k in ('id', 'quantity', 'comparison', 'limit', 'units')} for c in card['criteria']],
            'load_case': card['load_case'], 'design_space': card['design_space'],
            'check': {'id': chk['id'], 'version': chk['version'], 'author': chk['author'], 'reviewed_by': chk['reviewed_by'], 'stated_limits': chk['stated_limits']},
            'responsible_engineer': card['responsible_engineer']['name'], 'baselined_at': card.get('baselined_at'), 'supersedes': card.get('supersedes'),
            'alongside': card.get('alongside')}                       # Amendment 9: the other baselines held for this requirement, and the engineer's reason


def run_fields(attempt: dict) -> dict:
    r = attempt['result'] or {}
    return {'aid': attempt['aid'], 'outcome': attempt['outcome'], 'reason_code': r.get('reason_code'), 'design': r.get('design'), 'design_sha256': r.get('design_sha256'),
            'criteria': [{k: c.get(k) for k in ('id', 'limit', 'units', 'achieved', 'margin', 'met')} for c in r.get('criteria', [])], 'detail': r.get('detail', '')}


def refusal(code: str, text: str) -> dict:
    return {'refused': code, 'exit': 4, 'text': text}


def plain_text(verdict: dict, runs: dict, aid) -> str:
    """A verdict in words when the front door holds no usable card to print it against (the stored baseline was changed)."""
    # Amendment 5 (13 November 2026).  A verdict the gate decided with its card (it read the baseline as signed, though the
    # front door could not) is named by its own reason, and the last line says so; "no usable baseline is held" only when
    # the gate held none either.  The design is set out as sent, as the gate's own notice does when it holds no usable
    # card, but the first line says it is the front door that holds no usable baseline, which is so whether the gate held one
    # or not; it was printed whole, as JSON, with the sender's names and text in it.
    gate_held = verdict.get('verdict') != 'UNKNOWN' or verdict.get('check') is not None
    L = [HEADLINE.get(verdict.get('reason_code'), 'UNKNOWN') if gate_held else 'UNKNOWN: NO USABLE BASELINE IS HELD FOR THIS JOB', '',
         f"Reason        {verdict.get('detail') or verdict.get('reason_code')}"]
    D = design_lines(None, verdict.get('design'))
    if D[0] == 'Design        no usable baseline is held to set it against':
        D[0] = 'Design        the front door holds no usable baseline to set it against'
    L += D
    L += [f"Official runs {runs['total']} through the service on this baseline: {runs['PASS']} met, {runs['FAIL']} not met, {runs['UNKNOWN']} unknown." + (f"  This run: {aid}." if aid else ''), '']
    if verdict.get('verdict') != 'PASS':
        L.append('This is not a pass.  The run is counted and kept, and the responsible engineer has been sent this result directly by the verification service.')
    L.append('This result does not say the check is correct, the requirement is complete, or the design is safe.  '            # Amendment 9: a pass too
             'What the check does not cover cannot be shown here: ask the responsible engineer.')
    L.append('The front door could not read the stored baseline for this job as the one the responsible engineer signed, so the requirement is not printed here.  '
             'The gate read it as signed and decided this result.' if gate_held else
             'The baseline held by the service for this job could not be read as the one the responsible engineer signed, so the requirement is not printed here.')
    return '\n'.join(L)


# ---------------------------------------------------------------------------------------------------- the service
NOTICE_WORDS = {
    'UNDELIVERED': ("NOTICE NOT DELIVERED: the verification service could not write this result to the responsible engineer's inbox.  It is kept "
                    "in the service's own store, for the engineer to collect.  The engineer must be told of this result by other means."),
    'NOT_WRITTEN': ("NOTICE NOT WRITTEN: the verification service could not write this result to the responsible engineer's inbox, or to its own "
                    "store.  The engineer must be told of this result by other means."),
}


def notice_line(verdict) -> str:
    """The line an answer gives when the engineer's notice of a verdict could not be put in the inbox (Amendment 7, D2 and D3).
    Nothing is added when the notice was delivered."""
    state = verdict.get('notice') if isinstance(verdict, dict) else None
    return ('\n' + NOTICE_WORDS[state]) if state in NOTICE_WORDS else ''


def interrupted_body(card, baseline_sha256: str, design, runs: dict, aid: str, engineer: bool) -> str:
    """The engineer's notice for a run cut off before its verdict (Amendment 7, D11): the run, the design as the notices of verdicts
    set it out, and the fact that the run is counted and will not be run again.  The words are the service's own."""
    if card is not None:
        to, space = f"To: {card['responsible_engineer']['name']}", card['design_space']
    elif engineer:
        to, space = f"To: the responsible engineer for baseline {baseline_sha256}", None
    else:
        to, space = f"To: no engineer: the verification service found no baseline folder for the hash {baseline_sha256}, and read it in no inbox", None
    return '\n'.join([to, 'From: the verification service (not the assistant)', '',
                      'UNKNOWN: THE RUN WAS INTERRUPTED', '',
                      'Reason        The verification service did not finish this design\'s run: no verdict was recorded.  The run is counted, '
                      'and it will not be run again.  NOT VERIFIED.',
                      f"Official runs {runs['total']} on this baseline: {runs['PASS']} met, {runs['FAIL']} not met, {runs['UNKNOWN']} unknown.  This run: {aid}.",
                      ''] + design_lines(space, design) + ['', 'Nothing was checked to a result.  This is not a pass.'])


def interrupted_fixed(baseline_sha256: str, aid: str, engineer: bool) -> str:
    """The same notice in fixed words, for a card or a design that cannot be shown (Amendment 7, D11)."""
    to = (f"To: the responsible engineer for baseline {baseline_sha256}" if engineer else
          f"To: no engineer: the verification service found no baseline folder for the hash {baseline_sha256}, and read it in no inbox")
    return '\n'.join([to, 'From: the verification service (not the assistant)', '', 'UNKNOWN: THE RUN WAS INTERRUPTED', '',
                      f'Run {aid}.  The verification service did not finish this design\'s run: no verdict was recorded.  The run is counted, '
                      'and it will not be run again.  NOT VERIFIED.  The design is not shown here.  This is not a pass.'])


def _addressed(card, baseline_sha256: str, engineer: bool) -> str:
    """The first line of a notice the front door writes: to the engineer by name where the card can be read, by the baseline's
    hash where it cannot, and to no engineer where the hash is held in no inbox."""
    if card is not None:
        return f"To: {card['responsible_engineer']['name']}"
    if engineer:
        return f"To: the responsible engineer for baseline {baseline_sha256}"
    return f"To: no engineer: the verification service found no baseline folder for the hash {baseline_sha256}, and read it in no inbox"


DELIVERY_NOTICE = {                # Amendment 8 (D3): what a notice of this refusal says of each state of the gate's inbox-writability check
    'UNCHECKED': 'The gate, which writes the notice of each failure, has not shown that it can write to this inbox.',
    'STALE': 'The gate, which writes the notice of each failure, has not shown lately that it can write to this inbox.  It may not be running.',
    'NOT_WRITABLE': 'The gate, which writes the notice of each failure, could not write to this inbox when it last tried.',
}


def delivery_body(card, baseline_sha256: str, state: str, engineer: bool) -> str:
    """The engineer's notice that the front door is refusing new runs because a failure might not reach the engineer (Amendment 8,
    D3).  The front door writes it, where it can: the gate, which could not be shown to write here, does not."""
    return '\n'.join([_addressed(card, baseline_sha256, engineer), 'From: the verification service (not the assistant)', '',
                      'THE VERIFICATION SERVICE IS REFUSING NEW RUNS FOR THIS BASELINE', '',
                      f'Reason        {DELIVERY_NOTICE[state]}',
                      '              A failure might therefore not reach you, so no new run is admitted.',
                      f'Baseline      {baseline_sha256[:16]}…',
                      f"Refused       first today at {time.strftime('%H:%M:%S', time.gmtime())} UTC", '',
                      'A new design sent for this baseline is refused before anything is run, and nothing is counted.  A run that an earlier',
                      'request began, and that has no verdict yet, is not taken further until then; the status of the baseline shows it.',
                      'No verdict is changed, and every run already made is on the record.  This is not the result of any check.',
                      'The front door wrote this notice.',
                      'What can happen next:  the operator of the service starts the gate if it is not running, and makes this inbox',
                      '                       writable by the gate\'s account.  Runs go on once the gate has shown that it can write here.',
                      'This notice is written once on each day on which the service refuses a run for this reason.'])


STORAGE_REASONS = (('this baseline has used its share', 'SHARE'), ('the journal of submissions has reached its size limit', 'LIMIT'),
                   ('the disk that holds the journal has less free space', 'DISK'))


def storage_reason(why: str) -> str:
    """The short name of a reason for refusing a run for want of room, for the name of its notice: the baseline's SHARE, the
    journal's LIMIT, the DISK's reserve, or the JOURNAL itself, which could not be read or written.  (Amendment 8.)"""
    return next((key for words, key in STORAGE_REASONS if why.startswith(words)), 'JOURNAL')


def storage_body(card, baseline_sha256: str, why: str, engineer: bool) -> str:
    """The engineer's notice that the front door is refusing new runs for want of room (Amendment 8, D1).  The words are the
    service's own, and it says that no check gave this."""
    return '\n'.join([_addressed(card, baseline_sha256, engineer), 'From: the verification service (not the assistant)', '',
                      'THE VERIFICATION SERVICE IS REFUSING NEW RUNS FOR THIS BASELINE', '',
                      f'Reason        {why[:1].upper() + why[1:]}.',
                      f'Baseline      {baseline_sha256[:16]}…',
                      f"Refused       first today at {time.strftime('%H:%M:%S', time.gmtime())} UTC", '',
                      'A design sent for this baseline is refused before anything is run, and nothing is counted.  No verdict is changed,',
                      'and every run already made is on the record.  This is not the result of any check.',
                      'What can happen next:  the operator of the service makes room in the journal of submissions or on its disk,',
                      '                       or raises the limit.',
                      'This notice is written once on each day on which the service refuses a run for this reason.'])


class ServiceClient(Client):
    """service_client.Client (the first client's reading of runs, moved there by Amendment 17), unchanged in what it does, built from what the service holds and not from a workspace file.
    One is made per request, for the baseline the caller's job is bound to.  The baseline's hash and the budget's name
    come from the binding the engineer signed.  The card comes from the stored baseline, and is None if that file is
    no longer the one the engineer signed: nothing is shown from it, and a design sent is still decided by the gate."""

    def __init__(self, front: 'Front', binding: dict, envelope: dict | None):
        self.cfg, self.path, self.store = front.cfg, str, front.store
        self.envelope, self.card = envelope, (envelope['card'] if envelope is not None else None)
        self.baseline, self.root = binding['baseline_sha256'], binding['root']
        self._snapshot = None

    def runs(self):
        if self._snapshot is None:
            self._snapshot = super().runs()                  # one reading of the store per answer, so its text and its fields agree
        return self._snapshot

    def fresh(self) -> 'ServiceClient':
        self._snapshot = None
        return self

    def journal(self) -> list:
        """The journal's lines, as the first client reads them, except that a line nested too deep to read is passed over as a
        line that is not JSON is, and not raised.  The front door writes no such line.  (Amendment 8.)"""
        p = pathlib.Path(self.path(self.cfg.get('journal', 'submissions.jsonl')))
        if not p.exists():
            return []
        out = []
        for line in p.read_text().splitlines():
            try:
                out.append(json.loads(line))
            except (ValueError, RecursionError):
                pass
        return out


class Front:
    def __init__(self, home, store: Store, cfg: dict, engineer_keys, rate: int = 120):
        self.home, self.store, self.cfg, self.engineer_keys, self.rate = pathlib.Path(home), store, cfg, tuple(engineer_keys), rate
        self._guard = threading.Lock()
        self._locks, self._hits = {}, collections.defaultdict(collections.deque)     # Amendment 17 (D16): no binding sequence is kept here any more
        self._journaled = set()                  # the request keys this process has journaled: a design journaled once adds no line again (Amendment 7, D1)
        self._shares, self._counted = None, None   # bytes of the journal taken by each baseline's designs, and the size of the journal they were counted from (Amendment 8, D1)
        self._pending = {}                       # the look's runs to act on: (baseline, attempt, PENDING or INTERRUPTED) -> {'next', 'wait'} (Amendment 9)
        self._journal_lock = threading.Lock()    # the journal has a lock of its own, so that counting it does not hold up every other request (Amendment 8)
        (self.home / 'front').mkdir(parents=True, exist_ok=True)
        # Amendment 17 (D16): the names this front door's jobs have in the database's record of bindings.  Job names are unique
        # within one front door, whose jobs' certificates one authority issues; the record is keyed by that authority's
        # certificate as well, so two front doors on one database never share a job's record.
        self._realm = None

    # ------------------------------------------------------------------ who is asking
    def state_name(self, job: str) -> str:
        """The job's name in the database's record of bindings (Amendment 17, D16).  Without the authority's certificate in the
        configuration no job can be named in the record, and nobody is admitted (StateUnavailable)."""
        if self._realm is None:
            try:
                self._realm = hashlib.sha256(pathlib.Path(self.cfg['tls']['ca']).read_bytes()).hexdigest()[:32]
            except (KeyError, TypeError, OSError) as exc:
                raise front_state.StateUnavailable(f'no certificate authority to key the record by ({type(exc).__name__})') from None
        return f'{self._realm}:{job}'

    def admit(self, name, der) -> dict | None:
        """The job's binding, if this certificate is the one enrolled for this name, the job is not revoked, and a
        pinned engineer key signed the binding.  The file is read on every request, so a revocation or a move to a
        revision takes effect on the next one."""
        if not name or not JOB_NAME.match(name) or name in RESERVED or not der:
            return None
        b = read_jobs(self.home).get(name)
        if not binding_valid(b, self.engineer_keys) or b['job'] != name:
            return None
        if b['root'].rsplit('/', 1)[-1] != b['baseline_sha256'][:32] or '/' not in b['root']:
            # Amendment 17 (D16): a binding naming one baseline and another baseline's budget admits nobody.  Before, it was
            # noticed (the stored card was not shown) and its designs were still sent on.
            return None
        # Amendment 17 (D16): the latest binding seen for each job is kept in the database, not in this process's memory, so a
        # restart forgets nothing.  An earlier signed binding put back (STALE), a second binding with the same number
        # (CONFLICT) and any binding of a revoked job (REVOKED: absorbing) admit nobody.  If the record cannot be read, this
        # raises StateUnavailable, and the caller is answered 503: nobody is admitted.
        answer = front_state.observe(self.store, self.state_name(name), b['seq'], hashlib.sha256(canonical(b).encode()).hexdigest(), b['event'] == 'REVOKE')
        if answer != 'CURRENT' or b['cert_sha256'] != hashlib.sha256(der).hexdigest():
            return None
        return b

    def within_rate(self, name) -> bool:
        now = time.time()
        with self._guard:
            hits = self._hits[name]
            while hits and now - hits[0] >= 60.0:
                hits.popleft()
            if len(hits) >= self.rate:
                return False
            hits.append(now); return True

    def _lock(self, job) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(job, threading.Lock())

    def client(self, binding) -> ServiceClient:
        """The stored baseline is read on every request and used only if it is still what a pinned engineer signed and
        what the binding names."""
        h = binding['baseline_sha256']
        try:
            envelope = load_envelope(self.home / 'baselines' / h / 'baseline.json', self.engineer_keys)
            if envelope['baseline_sha256'] != h or root_for(envelope['card']) != binding['root']:
                envelope = None
        except Exception as exc:                             # Amendment 2: any way of being unusable, a file nested too deep to read included;
            envelope = None                                  # nothing is shown from it, and a design sent still goes to the gate, which decides
            try:
                print(f'front door: the stored baseline of job {binding["job"]} could not be read ({type(exc).__name__})', file=sys.stderr, flush=True)
            except OSError:                                  # a log that cannot be written must not stop the design reaching the gate
                pass
        return ServiceClient(self, binding, envelope)

    NO_BASELINE = (500, refusal('BASELINE_UNAVAILABLE', 'The baseline held by the verification service for this job is not the one the responsible engineer signed.  '
                                                        'It is not shown.  NOT VERIFIED.'))

    def _head(self, binding, c: ServiceClient) -> dict:
        return {'job': binding['job'], 'baseline_sha256': c.baseline, 'root': c.root}

    # ------------------------------------------------------------------ read-only
    def requirement(self, binding):
        c = self.client(binding)
        if c.card is None:
            return self.NO_BASELINE
        try:
            obs = self.store.observe(c.root)
            state = 'HELD' if obs['witness'] == 'HELD' else ('OPEN' if obs['business'] == 'OPEN' else 'STOPPED')
        except UnknownRoot:
            return 403, refusal('NO_BUDGET', 'REFUSED: this baseline has no budget at the control plane.  It was not provisioned by the responsible engineer.')
        return 200, dict(self._head(binding, c), **requirement_fields(c.card), accepting_runs=state == 'OPEN', text=requirement_text(c.card, c.baseline, state))

    def baseline(self, binding):
        c = self.client(binding)
        return self.NO_BASELINE if c.card is None else (200, c.envelope)

    def status(self, binding):
        c = self.client(binding)
        try:
            runs, attempts = c.runs()
            text = c.status()
        except UnknownRoot:
            return 403, refusal('NO_BUDGET', 'REFUSED: this baseline has no budget at the control plane.  It was not provisioned by the responsible engineer.')
        self._notify_interrupted(c, attempts, runs)       # Amendment 7 (D11): a run the store shows as interrupted, and not yet noticed, is noticed on this look
        return 200, dict(self._head(binding, c), runs=runs, declared_check_met=runs['PASS'] > 0, attempts=[run_fields(a) for a in attempts], text=text)   # Amendment 9: not "verified"

    # ------------------------------------------------------------------ one official run
    def submit(self, binding, design):
        lock = self._lock(binding['job'])
        if not lock.acquire(blocking=False):
            return 409, refusal('IN_PROGRESS', 'REFUSED: a design is already being verified for this job.  Ask again for its result.')
        try:
            return self._submit(binding, design)
        finally:
            lock.release()

    def _journal_size(self):
        """The size of the journal now, or None if it cannot be read.  (Amendment 7, D1.)"""
        try:
            p = pathlib.Path(self.cfg['journal'])
            return p.stat().st_size if p.exists() else 0
        except OSError:
            return None

    def _take_back(self, size) -> None:
        """Take a journal back to the size it had before a write that failed part-way.  (Amendment 7, D1.)"""
        if size is None:
            return
        try:
            os.truncate(self.cfg['journal'], size)
        except OSError:
            pass

    def _design_for(self, key):
        """The design a journaled request carries, found by its request key, or None if the journal does not show it.  (Amendment 7, D11.)"""
        try:
            with open(self.cfg['journal']) as f:
                for line in f:
                    try:
                        args = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(args, dict) and key in request_keys(args):     # Amendment 17: a run of either form
                        return args.get('design')
        except OSError:
            return None
        return None

    def _notify_interrupted(self, c: ServiceClient, attempts, runs: dict) -> None:
        """Amendment 7 (D11).  Each run on the job's baseline that the store shows as interrupted, and that has no notice yet, is given
        its engineer's notice, whichever answer first shows it: an ask, a second ask, or a look at the job's runs.  Nothing here is
        raised, and nothing changes the answer it is part of."""
        for a in attempts or []:
            try:
                if a.get('outcome') != 'INTERRUPTED' or 'aid' not in a:
                    continue
                name = 'INTERRUPTED_' + re.sub(r'[^A-Za-z0-9_-]', '_', str(a['aid']))
                if notices.written(self.home, c.baseline, name):
                    continue
                design = self._design_for(a.get('request_key'))
                if design is not None:
                    self._interrupted_notice(c, design, runs, a['aid'])
            except Exception:
                continue

    def _look_for_interrupted(self, c: ServiceClient) -> None:
        """Amendment 7 (D11).  A failed ask does not say whether its run was interrupted; the store may already say so, and if it does,
        the notice is written now.  The answer itself is not changed."""
        try:
            runs, attempts = c.fresh().runs()
        except Exception:
            return
        self._notify_interrupted(c, attempts, runs)

    def _used(self, baseline: str, size: int):
        """The bytes of the journal that hold this baseline's designs, or None if the journal cannot be read.  They are counted from
        the journal when this process first needs them, kept in step as it writes, and counted again whenever the journal is not
        the size this process left it: an operator has made room in it, or another process has written to it.  (Amendment 8, D1.)"""
        if self._shares is None or size != self._counted:
            shares = collections.Counter()
            path = pathlib.Path(self.cfg['journal'])
            try:
                if path.exists():
                    with path.open('rb') as f:
                        for line in f:
                            h = line[21:85] if line.startswith(b'{"baseline_sha256": "') else b''
                            if len(h) != 64 or not set(h) <= HEX_BYTES:        # a line this door did not write in its usual form
                                try:
                                    h = str(json.loads(line).get('baseline_sha256')).encode('ascii', 'replace')
                                except Exception:                              # not JSON, not an object, or nested too deep to read
                                    h = b'?'
                            shares[h.decode('ascii', 'replace')] += len(line)
            except OSError:
                return None
            self._shares, self._counted = shares, sum(shares.values())
        return self._shares[baseline]

    FINISHED = ('PASS', 'FAIL', 'UNKNOWN', 'INTERRUPTED')     # the outcomes after which asking again runs nothing

    def _delivery(self, c: ServiceClient, key):
        """Amendment 8 (D3).  None if the gate's tool has shown, not too long ago, that it can write a notice to the inbox of the job's
        baseline, or if this design's run is finished, so that asking again runs nothing.  Otherwise (the state of the gate's check,
        waiting).  A run that an earlier request began and that has no outcome yet is not let through: asking again could make
        it.  waiting is True for such a run, False where no run of this design is on the record, and None where that cannot be
        said: the runs could not be read, or the run on record is neither finished nor pending."""
        state, _ = notices.delivery_state(self.home, c.baseline)
        if state == 'WRITABLE':
            return None
        waiting = None
        try:
            _, attempts = c.fresh().runs()
            mine = [a.get('outcome') for a in attempts if a.get('request_key') == key]
            if any(o in self.FINISHED for o in mine):
                return None
            waiting = True if 'PENDING' in mine else False if not mine else None
        except Exception:                                # the runs cannot be read: the design is not let through
            pass
        return state, waiting

    def _tell(self, c: ServiceClient, kind: str, reason: str, make) -> str:
        """Amendment 8.  A refusal that the caller alone would otherwise hear of is told to the engineer of the refused job's baseline:
        one notice for each reason on each day on which it happens, however many designs are refused.  A notice kept in the
        service's own store while the inbox could not take it does not stop the inbox getting its copy once it can.
        make(card, engineer) gives the text.  Returns the sentence the refusal gives the caller.  Nothing is raised."""
        name = f"{kind}_{time.strftime('%Y%m%d', time.gmtime())}_{reason}"

        def text(engineer: bool) -> str:
            try:
                return make(c.card, engineer)
            except Exception:                            # where the card cannot be shown, the notice is addressed by the hash
                return make(None, engineer)
        try:
            state, _ = notices.deliver(self.home, c.baseline, name, text, numbered=False, inbox_again=True)
        except Exception:
            state = 'NOT_WRITTEN'
        return ('  The responsible engineer has been sent a notice of this.' if state == 'INBOX' else
                '  The responsible engineer could not be sent a notice of this.  Tell the responsible engineer.')

    def _storage_notice(self, c: ServiceClient, why: str) -> str:
        """Amendment 8 (D1).  The engineer's notice of a refusal for want of room."""
        return self._tell(c, 'STORAGE_FULL', storage_reason(why), lambda card, engineer: storage_body(card, c.baseline, why, engineer))

    def _delivery_notice(self, c: ServiceClient, state: str) -> str:
        """Amendment 8 (D3).  The engineer's notice of a refusal because the gate has not shown that it can write the inbox.  The front
        door writes it: to the inbox if the front door can, and otherwise to the service's own store, which the console lists."""
        return self._tell(c, 'INBOX_UNCHECKED', state, lambda card, engineer: delivery_body(card, c.baseline, state, engineer))     # Amendment 9: the name

    def _journal_room(self, nbytes: int, baseline: str):
        """None if the journal can take nbytes more for this baseline and its disk keeps the space the service keeps for notices;
        otherwise why not, in fixed words.  (Amendment 7, D1; the baseline's own share, Amendment 8.)"""
        path = pathlib.Path(self.cfg['journal'])
        try:
            size = path.stat().st_size if path.exists() else 0
            free = shutil.disk_usage(path.parent).free
        except OSError as exc:
            return f'the journal or its disk cannot be read ({type(exc).__name__})'
        used = self._used(baseline, size)
        if used is None:
            return 'the journal of submissions cannot be read'
        if nbytes and used + nbytes > self.cfg.get('journal_share_bytes', JOURNAL_SHARE):
            return 'this baseline has used its share of the journal of submissions'
        if nbytes and size + nbytes > self.cfg.get('journal_max_bytes', JOURNAL_MAX):
            return 'the journal of submissions has reached its size limit'
        if free - nbytes < self.cfg.get('disk_reserve_bytes', DISK_RESERVE):
            return 'the disk that holds the journal has less free space than the service keeps for notices'
        return None

    def _interrupted_notice(self, c: ServiceClient, design, runs: dict, aid: str) -> str:
        """The engineer's notice of a run cut off when the gate host died (Amendment 7, D11).  The service writes it once for each run,
        however often the answer is asked for again, to the baseline the job is bound to.  Returns the line the answer gives if the
        notice could not be put in the inbox."""
        name = 'INTERRUPTED_' + re.sub(r'[^A-Za-z0-9_-]', '_', str(aid))

        def text(engineer: bool) -> str:
            if design is None:                           # Amendment 9: the look writes it for a run whose design the journal does not hold
                return interrupted_fixed(c.baseline, aid, engineer)
            try:
                return interrupted_body(c.card, c.baseline, design, runs, aid, engineer)
            except Exception:                            # where the card or the design cannot be shown, the words are fixed
                return interrupted_fixed(c.baseline, aid, engineer)
        try:
            state, _ = notices.deliver(self.home, c.baseline, name, text, numbered=False)
        except Exception:                                # a notice that cannot be written is said so in the answer, not raised
            state = 'NOT_WRITTEN'
        return notice_line({'notice': state})

    def _submit(self, binding, design):
        c = self.client(binding)
        args = arguments_for(c.baseline, design)             # the baseline is the job's, never the caller's
        try:                                                 # Amendment 17: the request key in the form the budget already uses
            legacy = identity_form(self.store, c.root) == 'legacy'
        except UnknownRoot:
            return 403, dict(self._head(binding, c), **refusal('NO_BUDGET', 'REFUSED: this baseline has no budget at the control plane.  It was not provisioned by the responsible engineer.'))
        key = request_key(args, legacy=legacy)
        head = self._head(binding, c)
        unproven = self._delivery(c, key)                  # Amendment 8 (D3): no new run while a failure might not reach the engineer
        if unproven is not None:
            state, waiting = unproven
            told = self._delivery_notice(c, state)         # the engineer is told of the refusal too, where a notice can be written
            ran = ('  Nothing was run and nothing was counted.' if waiting is False else
                   '  An earlier request began a run of this design: it is on the record with no verdict yet, and it is not taken further until the '
                   'service has shown that it can write the inbox.  This request ran nothing and counted nothing.' if waiting else
                   '  This request ran nothing and counted nothing.')     # what is on the record for this design could not be said
            return 503, dict(head, **refusal('INBOX_UNCHECKED', f'REFUSED: {notices.DELIVERY_WORDS[state]}, so a failure might not reach the responsible '
                                                                  'engineer.' + ran + told))
        with self._journal_lock:
            fresh = key not in self._journaled             # Amendment 7 (D1): a design journaled once adds no line again
            line = json.dumps(args) + '\n'                 # so an interrupted run can still be tied to what was sent
            nbytes = len(line.encode('utf-8'))
            why = self._journal_room(nbytes if fresh else 0, c.baseline)   # every submission keeps the disk's reserve for notices
            if why is None and fresh:
                size = self._journal_size()
                try:
                    with open(self.cfg['journal'], 'a') as f:
                        f.write(line)
                    self._journaled.add(key)
                    self._shares[c.baseline] += nbytes; self._counted += nbytes     # Amendment 8 (D1): counted against this baseline's own share
                except OSError as exc:
                    self._take_back(size)                  # a line part-written by a full disk is taken back, so the next line starts clean
                    why = f'the journal cannot be written ({type(exc).__name__})'
        if why is not None:                                # refused before anything is run or counted; the engineer is told, outside the lock
            told = self._storage_notice(c, why)            # Amendment 8 (D1)
            return 507, dict(head, **refusal('STORAGE_FULL', f'REFUSED: the verification service has stopped accepting runs: {why}.  '
                                                            'Nothing was run and nothing was counted.' + told))
        try:
            verdict = c.governor().attempt(key, 'verify', **args)
        except UnknownRoot:
            return 403, dict(head, **refusal('NO_BUDGET', 'REFUSED: this baseline has no budget at the control plane.  It was not provisioned by the responsible engineer.'))
        except BudgetExhausted:
            return 409, dict(head, **refusal('BUDGET_EXHAUSTED', 'REFUSED: the number of official runs allowed on this baseline is used up.  Nothing was run.'))
        except Stopped:
            return 409, dict(head, **refusal('STOPPED', 'REFUSED: this baseline has been stopped (it was superseded or closed by the responsible engineer).  Nothing was run.'))
        except Held:
            return 409, dict(head, **refusal('HELD', 'REFUSED: this baseline is on hold by the responsible engineer.  Nothing was run.'))
        except InProgress:
            return 409, dict(head, **refusal('IN_PROGRESS', 'REFUSED: this design is already being verified.  Ask again for its result.'))
        except GovernedError as exc:
            return 409, dict(head, **refusal(str(exc.decision.code), f'REFUSED: {exc.decision.code}.  Nothing was run.'))
        except (GateRefusedRun, OutcomeInvalid, RequestKeyReused, ReceiptInvalid, PermissionError) as exc:
            return 502, dict(head, **refusal('SERVICE_REFUSED', f'REFUSED by the verification service ({type(exc).__name__}).  NOT VERIFIED.'))
        except (WitnessUnavailable, TransportError, urllib.error.URLError, ConnectionError, TimeoutError, OSError) as exc:
            self._look_for_interrupted(c)                  # Amendment 7 (D11): a run the store already shows as interrupted is noticed now
            return 503, dict(head, **refusal('UNAVAILABLE', f'The verification service could not be reached ({type(exc).__name__}).  NOT VERIFIED.  The run may be pending; ask again.'))
        except RuntimeError:
            runs, attempts = c.fresh().runs()
            mine = next((a for a in attempts if a['request_key'] == key), None)
            if mine is None or mine['outcome'] != 'INTERRUPTED':       # only the gate's own signed "I do not know" is reported as interrupted
                return 503, dict(head, **refusal('UNAVAILABLE', 'The verification service did not give a verdict.  NOT VERIFIED.  The run may be pending; ask again.'))
            text = ('UNKNOWN: THE RUN WAS INTERRUPTED\n\nThe verification service stopped while this design was being checked.  No verdict exists, the run is '
                    f'counted, and it will not be run again.  NOT VERIFIED.\nOfficial runs {runs["total"]} on this baseline: {runs["PASS"]} met, {runs["FAIL"]} not met, {runs["UNKNOWN"]} unknown.')
            if c.card is None:
                text += '\nThe baseline held by the service for this job could not be read as the one the responsible engineer signed.  Tell the responsible engineer.'
            text += self._interrupted_notice(c, design, runs, mine['aid'])     # Amendment 7 (D11): the engineer is sent a notice of this run too
            return 200, dict(head, outcome='INTERRUPTED', met=False, declared_check_met=False,                                  # Amendment 9: as for any answer
                             check_does_not_cover=list(c.card['check']['stated_limits']) if c.card is not None else None, exit=3, aid=mine['aid'], runs=runs, verdict=None, text=text)
        runs, attempts = c.fresh().runs()
        aid = next((a['aid'] for a in attempts if a['request_key'] == key), None)
        outcome = verdict.get('verdict') if isinstance(verdict, dict) else None
        if outcome not in ('PASS', 'FAIL', 'UNKNOWN') or verdict.get('baseline_sha256') != c.baseline:
            return 502, dict(head, **refusal('SERVICE_REFUSED', 'REFUSED by the verification service: the verdict returned is not for this job\'s baseline.  NOT VERIFIED.'))
        if verdict.get('design_sha256') != design_hash(design):          # Amendment 17 (D21): never another design's verdict, whatever the keys
            return 502, dict(head, **refusal('SERVICE_REFUSED', 'REFUSED by the verification service: the verdict returned is not for this design.  NOT VERIFIED.'))
        return 200, dict(head, outcome=outcome, met=outcome == 'PASS', declared_check_met=outcome == 'PASS',             # Amendment 9: the words for a pass,
                         check_does_not_cover=list(c.card['check']['stated_limits']) if c.card is not None else None,     # and what the check does not cover
                         exit={'PASS': 0, 'FAIL': 2}.get(outcome, 3), aid=aid, runs=runs, verdict=verdict,
                         text=(face(c.card, verdict, runs, aid) if c.card is not None else plain_text(verdict, runs, aid)) + notice_line(verdict))


    # ------------------------------------------------------------------ runs left pending (Amendment 9)
    def sweep(self, after: float = SWEEP_AFTER, now: float | None = None) -> list:
        """Finish the runs that are left pending, with no caller asking.  A run is pending when it was admitted and the gate has
        signed no outcome for it: the gate host died during it, or the request that began it was cut off.  Before this amendment
        such a run got its notice only if its design was sent again.

        For each job whose binding a pinned engineer signed and that is not revoked, the look reads the observation of the job's
        baseline from the store, and, for a run the gate began and has no notice of, the evidence of that run.  From these it
        picks the runs left pending, and the runs cut off whose notice is not written.  A run is due once it has been seen in
        that state for `after` seconds (at least SWEEP_MIN_WAIT); each time the look acts on it, the wait before it acts again
        doubles, up to SWEEP_MAX_WAIT, so a run that cannot be finished is acted on less and less often.  A run seen in a new
        state is seen afresh.  The job's runs are read in full only when one is due.  An error in reading a job's baseline
        leaves its waits as they were.

        A run cut off whose notice is missing is given it, as an answer would give it, whatever the state of the budget and of
        the gate's inbox-writability check (a notice the inbox cannot take is kept in the service's own store), and in the
        service's fixed words where this door's journal does not hold the run's design.  A pending run
        is asked for again, through the same path as a caller's request, only while that check is good and the budget is
        neither held nor stopped (the governor would refuse it), only if this door's journal holds its design, and only if the
        job's binding, read again just before, is unchanged, so that a revocation made during a look counts.  The gate host
        never runs a run twice: a run it began is answered with its signed UNKNOWN, counted as interrupted, and its engineer is
        sent the notice; a run that never reached the gate host is run now, once, as its caller asked.  The design found in the
        journal is not journaled again.  Runs are a baseline's, not a job's: a run on a baseline is asked for through any live
        job bound to it.  The look acts on one run at most SWEEP_MAX_ASKS times, and then leaves it as it is, pending or without
        its notice, until the front door restarts; the console shows the run as it stands.  Returns what was done.  Nothing is
        raised."""
        done, seen, looked = [], set(), set()
        now = time.time() if now is None else now
        after = max(float(after), SWEEP_MIN_WAIT)
        try:
            jobs = read_jobs(self.home)
        except Exception:
            return done
        for name, b in sorted(jobs.items()):
            try:
                if not binding_valid(b, self.engineer_keys) or b['job'] != name or b['event'] == 'REVOKE':
                    continue
                if front_state.observe(self.store, self.state_name(name), b['seq'], hashlib.sha256(canonical(b).encode()).hexdigest(), False) != 'CURRENT':
                    continue                                   # Amendment 17 (D16): as admit() refuses it; unreadable state raises, and the job is passed over
                h, root = b['baseline_sha256'], b['root']
                obs = self.store.observe(root)                   # one reading of the store; the journal is not read here
                found = []
                for aid, _req, phase, *_ in obs['attempts']:
                    aid = str(aid)
                    if phase in PENDING_PHASES:
                        found.append((aid, 'PENDING'))
                    elif phase == 'CONSUMED' and not notices.written(self.home, h, 'INTERRUPTED_' + re.sub(r'[^A-Za-z0-9_-]', '_', aid)):
                        claims = [e['evidence'].get('claim') for e in self.store.evidence_for(root, aid) if isinstance(e.get('evidence'), dict)]
                        found.append((aid, 'INTERRUPTED' if 'UNKNOWN' in claims else 'PENDING'))
                may_ask = obs.get('witness') == 'ACTIVE' and obs.get('business') == 'OPEN'
            except Exception:
                continue                                       # this job's waits are kept as they were
            looked.add(h)
            due = []
            with self._guard:
                for aid, kind in found:
                    k = (h, aid, kind); seen.add(k)
                    w = self._pending.setdefault(k, {'next': now + after, 'wait': after, 'acts': 0})
                    if now >= w['next'] and w['acts'] < SWEEP_MAX_ASKS:
                        due.append((aid, kind, k))
            if any(kind == 'PENDING' for _, kind, _ in due):
                try:
                    may_ask = may_ask and notices.delivery_state(self.home, h)[0] == 'WRITABLE'
                except Exception:
                    may_ask = False
                if not may_ask:                                # not asked, and not counted as asked: due again at the next look
                    due = [d for d in due if d[1] != 'PENDING']
            if not due:
                continue
            try:
                c = self.client(b)
                runs, attempts = c.fresh().runs()
            except Exception:
                continue
            by_aid = {str(a.get('aid')): a for a in attempts}
            for aid, kind, k in due:
                a = by_aid.get(aid)
                try:
                    if a is None:
                        continue
                    if a.get('outcome') == 'INTERRUPTED':          # cut off, its notice missing: it is written now, once, in fixed words if need be
                        self._interrupted_notice(c, self._design_for(a.get('request_key')), runs, aid)
                        wrote = notices.written(self.home, h, 'INTERRUPTED_' + re.sub(r'[^A-Za-z0-9_-]', '_', aid))
                        done.append({'job': name, 'aid': aid, 'status': None, 'outcome': 'INTERRUPTED_NOTICE_WRITTEN' if wrote else 'INTERRUPTED_NOTICE_NOT_WRITTEN'})
                    elif a.get('outcome') == 'PENDING' and kind == 'PENDING':
                        design = self._design_for(a.get('request_key'))
                        if design is None:
                            continue
                        if read_jobs(self.home).get(name) != b:    # read again: a revocation or a move made during this look counts
                            continue
                        with self._journal_lock:                   # it is in the journal already: asking for it adds no line there
                            self._journaled.add(a.get('request_key'))
                        status, payload = self.submit(b, design)
                        done.append({'job': name, 'aid': aid, 'status': status, 'outcome': payload.get('outcome') or payload.get('refused')})
                except Exception as exc:                       # one run that cannot be acted on does not stop the others
                    done.append({'job': name, 'aid': aid, 'status': None, 'outcome': type(exc).__name__})
                finally:                                       # every run looked at when due waits twice as long before the next time
                    with self._guard:
                        w = self._pending.get(k)
                        if w is not None:
                            w['wait'] = min(w['wait'] * 2, SWEEP_MAX_WAIT); w['next'] = now + w['wait']; w['acts'] += 1
                            if w['acts'] == SWEEP_MAX_ASKS:
                                done.append({'job': name, 'aid': aid, 'status': None, 'outcome': 'LEFT_AS_IT_IS'})
        with self._guard:                                      # forget only what a baseline read without error no longer shows
            self._pending = {k: w for k, w in self._pending.items() if k in seen or k[0] not in looked}
        return done


def sweeper(front: Front, after: float, every: float) -> None:
    """The front door's own look for runs left pending, every `every` seconds.  (Amendment 9.)"""
    while True:
        time.sleep(every)
        try:
            for d in front.sweep(after):
                what = {'INTERRUPTED_NOTICE_WRITTEN': 'the notice of a run cut off was written', 'INTERRUPTED_NOTICE_NOT_WRITTEN': 'the notice of a run cut off could not be written',
                        'LEFT_AS_IT_IS': f'the look has acted on a run {SWEEP_MAX_ASKS} times and leaves it as it is until the front door restarts'}.get(d.get('outcome'), 'a run left pending was asked for again')
                print(f"front door: {what}: {json.dumps(d)}", file=sys.stderr, flush=True)
        except Exception as exc:
            try:
                print(f'front door: the look for runs left pending failed: {type(exc).__name__}', file=sys.stderr, flush=True)
            except Exception:
                pass


# ---------------------------------------------------------------------------------------------------- HTTPS
def make_handler(front: Front):
    class Handler(TLSHandlerMixin, BaseHTTPRequestHandler):
        tls_allow = ()                                       # every certificate of the authority reaches admit(), which decides
        server_version, sys_version = 'verification-front-door', ''
        timeout = 30                                         # seconds a caller may take to send or to read; not the time a run may take

        def log_message(self, *args): pass

        def _send(self, status, payload):
            body = json.dumps(payload).encode()
            self.send_response(status); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

        def _who(self):
            """The caller's binding, or None after answering 403 or 429."""
            der = self.connection.getpeercert(binary_form=True) if isinstance(self.connection, ssl.SSLSocket) else None
            try:
                b = front.admit(self.peer_name, der)
            except front_state.StateUnavailable as exc:      # Amendment 17 (D16): the record of bindings cannot be read: nobody is admitted
                print(f'front door: the record of job bindings could not be read ({exc})', file=sys.stderr, flush=True)
                self._send(503, refusal('UNAVAILABLE', 'The verification service cannot read its record of job bindings, so it admits nobody.  Nothing was run.  NOT VERIFIED.')); return None
            if b is None:
                self._send(403, refusal('NOT_ENROLLED', 'REFUSED: this certificate is not enrolled for a job, or the job was revoked.')); return None
            if not front.within_rate(b['job']):
                self._send(429, refusal('RATE_LIMIT', 'REFUSED: too many requests in the last minute.  Nothing was run.')); return None
            return b

        def _answer(self, fn, *args):
            try:
                status, payload = fn(*args)
            except Exception as exc:                         # never a traceback to the caller, and never a dropped connection read as "try again"
                print(f'front door: {type(exc).__name__}: {exc}', file=sys.stderr, flush=True)
                status, payload = 500, refusal('SERVICE_ERROR', 'The verification service failed to answer.  NOT VERIFIED.  Ask for the status before sending anything again.')
            self._send(status, payload)

        def do_GET(self):
            b = self._who()
            if b is None:
                return
            if self.path == '/requirement':
                return self._answer(front.requirement, b)
            if self.path == '/baseline':
                return self._answer(front.baseline, b)
            if self.path == '/status':
                return self._answer(front.status, b)
            self._send(404, refusal('NOT_FOUND', 'There is no such path.'))

        def _body(self):
            """The request body, read within the cap: (bytes, None), or (None, the refusal to send).  It is read before
            the caller is looked up, so that a refusal can be read by the caller and is not lost with an unread body."""
            try:
                length = int(self.headers.get('Content-Length', ''))
            except ValueError:
                self.close_connection = True
                return None, (411, refusal('LENGTH_REQUIRED', 'REFUSED: the request gave no length.  Nothing was run and nothing was recorded.'))
            if length < 0 or length > MAX_BODY:
                self.close_connection = True                 # a negative length would make read() run to end of file, past every cap
                remaining = min(max(length, 0), MAX_BODY + 65536)
                try:
                    while remaining > 0:                     # take a bounded amount off the wire so the answer can be read, then close
                        chunk = self.rfile.read(min(8192, remaining))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                except OSError:
                    pass
                return None, (400, refusal('BAD_REQUEST', 'REFUSED: the request is too large or its length is not valid.  Nothing was run and nothing was recorded.'))
            try:
                raw = self.rfile.read(length)
            except OSError:                                  # the caller stopped sending
                raw = b''
            if len(raw) != length:
                self.close_connection = True
                return None, (400, refusal('BAD_REQUEST', 'REFUSED: the request ended before its stated length.  Nothing was run and nothing was recorded.'))
            return raw, None

        def do_POST(self):
            raw, refused = self._body()
            b = self._who()
            if b is None:
                return
            if self.path != '/submit':
                return self._send(404, refusal('NOT_FOUND', 'There is no such path.'))
            if refused is not None:
                return self._send(*refused)
            try:
                design = parse_design(raw)
            except BadRequest as exc:
                return self._send(400, refusal('BAD_REQUEST', f'REFUSED: {exc}.  Nothing was run and nothing was recorded.'))
            self._answer(front.submit, b, design)

        def do_PUT(self): self._other()
        def do_DELETE(self): self._other()
        def do_PATCH(self): self._other()

        def _other(self):
            if self.headers.get('Content-Length') is not None:
                self._body()
            self.close_connection = True
            if self._who() is not None:
                self._send(404, refusal('NOT_FOUND', 'There is no such path.'))
    return Handler


def main():
    ap = argparse.ArgumentParser(description='The verification service\'s front door.')
    ap.add_argument('--home', required=True, help='VERIFY_HOME: the baselines the gate host reads, and front/jobs.json')
    ap.add_argument('--port', type=int, default=8973); ap.add_argument('--bind', default='127.0.0.1')
    ap.add_argument('--local-dsn', default=os.environ.get('PLEA_LOCAL_DSN', 'postgresql://plea_local:local@127.0.0.1:5432/plea'))
    ap.add_argument('--witness-url', required=True); ap.add_argument('--witness-key', action='append', required=True, help='a witness public key to pin (hex); repeatable')
    ap.add_argument('--gate-host', required=True); ap.add_argument('--gate-key', required=True, help='the gate host\'s public key to pin (hex)')
    ap.add_argument('--engineer-key', action='append', required=True, help='a responsible engineer\'s public key to pin (hex); repeatable')
    ap.add_argument('--upstream-cert', required=True, help='this service\'s client certificate for the witness and the gate host'); ap.add_argument('--upstream-key', required=True)
    ap.add_argument('--rate', type=int, default=120, help='requests a job may make in a minute')
    ap.add_argument('--journal-max-bytes', type=int, default=JOURNAL_MAX, help='size the journal of submissions may reach before new runs are refused (Amendment 7)')
    ap.add_argument('--disk-reserve-bytes', type=int, default=DISK_RESERVE, help='free bytes the journal\'s disk keeps for notices (Amendment 7)')
    ap.add_argument('--journal-share-bytes', type=int, default=JOURNAL_SHARE, help='bytes of the journal one baseline\'s designs may take before new runs for it are refused (Amendment 8)')
    ap.add_argument('--sweep-after', type=float, default=SWEEP_AFTER, help='seconds a run is seen pending before the front door asks the gate for it itself (Amendment 9)')
    ap.add_argument('--sweep-every', type=float, default=SWEEP_EVERY, help='seconds between the front door\'s looks for runs left pending (Amendment 9)')
    add_server_args(ap)
    a = ap.parse_args()
    tls = server_from_args(a)
    if tls is None:
        raise SystemExit('the front door serves mutual TLS only: give --tls-cert, --tls-key and --tls-ca')
    home = pathlib.Path(a.home)
    cfg = {'witness_url': a.witness_url, 'witness_keys': a.witness_key, 'gate_url': a.gate_host, 'gate_key': a.gate_key,
           'tls': {'ca': a.tls_ca, 'cert': a.upstream_cert, 'key': a.upstream_key}, 'journal': str(home / 'front' / 'submissions.jsonl'),
           'journal_max_bytes': a.journal_max_bytes, 'disk_reserve_bytes': a.disk_reserve_bytes,
           'journal_share_bytes': a.journal_share_bytes}
    front = Front(home, Store(a.local_dsn), cfg, a.engineer_key, a.rate)
    server = wrap_server(ThreadingHTTPServer((a.bind, a.port), make_handler(front)), tls)
    threading.Thread(target=sweeper, args=(front, max(SWEEP_MIN_WAIT, a.sweep_after), min(600.0, max(0.1, a.sweep_every))), name='front-door-sweep', daemon=True).start()
    print(json.dumps({'listening': a.port, 'home': str(home), 'witness_keys': a.witness_key, 'gate_key': a.gate_key, 'engineer_keys': a.engineer_key, 'tls': True}), flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
