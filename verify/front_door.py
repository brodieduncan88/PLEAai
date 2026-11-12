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
                         502 the service refused its own step        503 a part of the service could not be reached
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
from baseline import HEADLINE, canonical, face, root_for   # noqa: E402
from verify_client import Client                                     # noqa: E402
from verify_record import arguments_for, load_envelope, request_key, signed_by   # noqa: E402

JOB_NAME = re.compile(r'^[a-z0-9][a-z0-9-]{1,40}$')
RESERVED = ('frontdoor', 'front', 'witness', 'host', 'governor', 'engineer')
HEX64 = re.compile(r'^[0-9a-f]{64}$')
MAX_BODY = 16384
MAX_DEPTH = 4
EVENTS = ('ENROL', 'REBIND', 'REVOKE')
BINDING_FIELDS = ('event', 'seq', 'job', 'baseline_sha256', 'root', 'cert_sha256', 'previous', 'time', 'note')


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
    """The baselined requirement as an engineer reads it.  The wording of verify_client.Client.show, without its command line."""
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
    L += [f"  \"{req['statement']}\"", f"  Source: {req['source']}",
          f"  Baselined {card.get('baselined_at', '?')} by {eng['name']}, responsible engineer.  Baseline hash {baseline_hash}", '', 'ACCEPTANCE LIMITS']
    for k in card['criteria']:
        L.append(f"  {k['id']}: {k['quantity']} {'at most' if k['comparison'] == '<=' else 'at least'} {k['limit']} {k['units']}")
    L += ['', 'LOAD CASE', f"  {card['load_case']}", '', 'DESIGN SPACE (what may be varied)']
    for name, rule in card['design_space'].items():
        L.append(f"  {name}: " + ('one of ' + ', '.join(map(str, rule['choice'])) if 'choice' in rule else f"a number from {rule['min']} to {rule['max']}"))
    L += ['', f"DECLARED CHECK  {chk['id']} v{chk['version']}, written by {chk['author']}, reviewed by {chk['reviewed_by']}", '  It does not cover: ' + '; '.join(chk['stated_limits']), '',
          'A design is verified only by submitting it to the verification service: an object giving exactly the design-space parameters.',
          'The requirement, the limits, the load case, the design space and the check cannot be changed from here.',
          f"Only {eng['name']} can issue a revised baseline or accept a failure."]
    return '\n'.join(L)


def requirement_fields(card: dict) -> dict:
    chk = card['check']
    return {'requirement': card['requirement'],
            'criteria': [{k: c[k] for k in ('id', 'quantity', 'comparison', 'limit', 'units')} for c in card['criteria']],
            'load_case': card['load_case'], 'design_space': card['design_space'],
            'check': {'id': chk['id'], 'version': chk['version'], 'author': chk['author'], 'reviewed_by': chk['reviewed_by'], 'stated_limits': chk['stated_limits']},
            'responsible_engineer': card['responsible_engineer']['name'], 'baselined_at': card.get('baselined_at'), 'supersedes': card.get('supersedes')}


def run_fields(attempt: dict) -> dict:
    r = attempt['result'] or {}
    return {'aid': attempt['aid'], 'outcome': attempt['outcome'], 'reason_code': r.get('reason_code'), 'design': r.get('design'), 'design_sha256': r.get('design_sha256'),
            'criteria': [{k: c.get(k) for k in ('id', 'limit', 'units', 'achieved', 'margin', 'met')} for c in r.get('criteria', [])], 'detail': r.get('detail', '')}


def refusal(code: str, text: str) -> dict:
    return {'refused': code, 'exit': 4, 'text': text}


def plain_text(verdict: dict, runs: dict, aid) -> str:
    """A verdict in words when the front door holds no usable card to print it against (the stored baseline was changed)."""
    L = [HEADLINE.get(verdict.get('reason_code'), 'UNKNOWN') if verdict.get('verdict') != 'UNKNOWN' else 'UNKNOWN: NO USABLE BASELINE IS HELD FOR THIS JOB', '',
         f"Reason        {verdict.get('detail') or verdict.get('reason_code')}",
         'Design        ' + json.dumps(verdict.get('design'), sort_keys=True),
         f"Official runs {runs['total']} through the service on this baseline: {runs['PASS']} met, {runs['FAIL']} not met, {runs['UNKNOWN']} unknown." + (f"  This run: {aid}." if aid else ''), '']
    if verdict.get('verdict') != 'PASS':
        L.append('This is not a pass.  The run is counted and kept, and the responsible engineer has been sent this result directly by the verification service.')
    L.append('The baseline held by the service for this job could not be read as the one the responsible engineer signed, so the requirement is not printed here.')
    return '\n'.join(L)


# ---------------------------------------------------------------------------------------------------- the service
class ServiceClient(Client):
    """verify_client.Client, unchanged in what it does, built from what the service holds and not from a workspace file.
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


class Front:
    def __init__(self, home, store: Store, cfg: dict, engineer_keys, rate: int = 120):
        self.home, self.store, self.cfg, self.engineer_keys, self.rate = pathlib.Path(home), store, cfg, tuple(engineer_keys), rate
        self._guard = threading.Lock()
        self._locks, self._hits, self._seen = {}, collections.defaultdict(collections.deque), {}
        (self.home / 'front').mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ who is asking
    def admit(self, name, der) -> dict | None:
        """The job's binding, if this certificate is the one enrolled for this name, the job is not revoked, and a
        pinned engineer key signed the binding.  The file is read on every request, so a revocation or a move to a
        revision takes effect on the next one."""
        if not name or not JOB_NAME.match(name) or name in RESERVED or not der:
            return None
        b = read_jobs(self.home).get(name)
        if not binding_valid(b, self.engineer_keys) or b['job'] != name:
            return None
        with self._guard:
            if b['seq'] < self._seen.get(name, 0):           # an earlier signed binding put back in the file: a revocation or a move undone
                return None
            self._seen[name] = b['seq']
        if b['event'] == 'REVOKE' or b['cert_sha256'] != hashlib.sha256(der).hexdigest():
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
        return 200, dict(self._head(binding, c), runs=runs, verified=runs['PASS'] > 0, attempts=[run_fields(a) for a in attempts], text=text)

    # ------------------------------------------------------------------ one official run
    def submit(self, binding, design):
        lock = self._lock(binding['job'])
        if not lock.acquire(blocking=False):
            return 409, refusal('IN_PROGRESS', 'REFUSED: a design is already being verified for this job.  Ask again for its result.')
        try:
            return self._submit(binding, design)
        finally:
            lock.release()

    def _submit(self, binding, design):
        c = self.client(binding)
        args = arguments_for(c.baseline, design)             # the baseline is the job's, never the caller's
        key = request_key(args)
        with self._guard:
            with open(self.cfg['journal'], 'a') as f:
                f.write(json.dumps(args) + '\n')             # so an interrupted run can still be tied to what was sent
        head = self._head(binding, c)
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
            return 200, dict(head, outcome='INTERRUPTED', met=False, exit=3, aid=mine['aid'], runs=runs, verdict=None, text=text)
        runs, attempts = c.fresh().runs()
        aid = next((a['aid'] for a in attempts if a['request_key'] == key), None)
        outcome = verdict.get('verdict') if isinstance(verdict, dict) else None
        if outcome not in ('PASS', 'FAIL', 'UNKNOWN') or verdict.get('baseline_sha256') != c.baseline:
            return 502, dict(head, **refusal('SERVICE_REFUSED', 'REFUSED by the verification service: the verdict returned is not for this job\'s baseline.  NOT VERIFIED.'))
        return 200, dict(head, outcome=outcome, met=outcome == 'PASS', exit={'PASS': 0, 'FAIL': 2}.get(outcome, 3), aid=aid, runs=runs, verdict=verdict,
                         text=face(c.card, verdict, runs, aid) if c.card is not None else plain_text(verdict, runs, aid))


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
            b = front.admit(self.peer_name, der)
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
    add_server_args(ap)
    a = ap.parse_args()
    tls = server_from_args(a)
    if tls is None:
        raise SystemExit('the front door serves mutual TLS only: give --tls-cert, --tls-key and --tls-ca')
    home = pathlib.Path(a.home)
    cfg = {'witness_url': a.witness_url, 'witness_keys': a.witness_key, 'gate_url': a.gate_host, 'gate_key': a.gate_key,
           'tls': {'ca': a.tls_ca, 'cert': a.upstream_cert, 'key': a.upstream_key}, 'journal': str(home / 'front' / 'submissions.jsonl')}
    front = Front(home, Store(a.local_dsn), cfg, a.engineer_key, a.rate)
    server = wrap_server(ThreadingHTTPServer((a.bind, a.port), make_handler(front)), tls)
    print(json.dumps({'listening': a.port, 'home': str(home), 'witness_keys': a.witness_key, 'gate_key': a.gate_key, 'engineer_keys': a.engineer_key, 'tls': True}), flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
