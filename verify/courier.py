#!/usr/bin/env python3
"""The courier: notices to the responsible engineer that the verification service does not write (Amendment 11).

    courier.py keygen KEYFILE                    write a new courier key; print its public half
    courier.py run --config CONFIG [--every S]   one pass over every budget watched (or a pass every S seconds)
    courier.py status --config CONFIG            for each budget configured: coverage, how the last pass ended, the two lines
                                                 and their bound, runs not read or put off, notices not accepted by the mailbox
                                                 (by kind), and accepted
    courier.py resume --config CONFIG --root R   read budget R again from its start, after a refusal has been looked into
                                                 (notices already sent, for a run and an outcome, are not sent again)

CONFIG is a JSON file the engineer writes:

    {"name": "courier-1", "key_file": "...", "state_dir": "...", "stall_after": 900, "page": 200,
     "witness_url": "https://...", "ca": "...", "cert": "...", "key": "...",
     "witness_keys": [HEX], "gate_keys": [HEX],
     "watches": [{"root": R, "mailbox_url": "https://...", "mailbox_keys": [HEX]}]}

Where a notice comes from.  The service writes its own notice of a failing run into an inbox it controls (verify_tools.py),
and whoever can write that inbox can remove or change it; a run the service cannot finish, or cannot write a notice for,
gets none.  The courier does not read the service: not its store, its inbox, its ledger or its files, and it holds no
credential of the service's.  It reads only the witness, as a client the witness admits to its chain readings and nothing
that writes (--tls-allow-chain), and it believes the witness only as far as it can check:

  - it asks for a checkpoint with a nonce of its own, signed by a witness key given, naming the last decision it read
    before and that decision's head (Amendment 10);
  - it reads the decisions since (GET /chain), page by page, and recomputes each hash: they must follow on from what it
    read before and end at the checkpoint's head;
  - for each run, it reads the gate's reports and the stored result (GET /run): a report counts only if a gate key given
    signed it for this budget, run and nonce, and a result only if it hashes to the digest the gate signed.

A run calls for a notice when the chain, the reports and the result say FAIL, UNKNOWN, INTERRUPTED or INDETERMINATE (the
control plane re-registered the budget); INVALID or REFUNDED, which must never happen; UNVERIFIED, a run the gate signed an
effect for with no stored result that hashes to the digest the gate signed; or NO_OUTCOME, a run whose intent was accepted,
or that was admitted and crossed, with no outcome.  The last two are sent only once the courier has seen them so for
`stall_after` seconds (900 unless set) by its own clock, since the witness records an outcome a moment before the result is
stored.  An UNVERIFIED notice vouches for no result.  A run that met the declared check calls for none.  Each notice, for
one run and one outcome, is made once and signed with the courier's key; "once" holds as long as STATE_DIR/state.json does.
It names the decision it was read at and that decision's hash, so a reader can tie it to a record.

Delivery.  Each notice is sent to the watch's mailbox (mailbox_service.py) over HTTPS with the courier's client
certificate.  It is accepted by the mailbox when the mailbox answers with a receipt signed by a mailbox key given, naming the
notice; that is all "delivered" means here: a signed receipt, not a person's acknowledgement.  The notice and its receipt are
then appended to STATE_DIR/deliveries.jsonl, and a record can carry them (verify_ctl.py record --deliveries).  Each request
has 60 seconds, however slowly a party answers, and no answer is read past 32 MiB and a byte; an answer that cannot be
parsed for any reason (not JSON, nested too deeply, too large for memory) is not readable.  A pass exits 0 if nothing is
waiting, refused, unreachable, unread, put off or failed and the courier's coverage statement, once made, has been
accepted; and 1 otherwise.

The outbox (Amendment 16, fifth form).  Every notice made is put in the budget's outbox with a record of its own: when made,
how many times tried, when last tried, and what came of the last try (refused by the mailbox; no valid receipt; could not be
sent).  It is sent as soon as it is made, and what waits is sent before the witness is asked.  Before notices are sent, and
again after one fails as a transport fails, the courier asks the mailbox for its key (GET /pubkey): if it answers with a key
given, the mailbox can be reached and the notice that failed is kept, counted, and the next is tried; if not, nothing more
is sent to that mailbox in the pass.  The one tried longest ago is tried first (never tried first, in the order made), each
at most once in a pass, and none is dropped: the status lists each with its kind, its count and the last reason.  So with
the mailbox not answering, sending costs one request in a pass for each budget, whatever is waiting; with a mailbox that
answers its key and fails deliveries, at most two requests for each notice waiting.  Sending never changes what is asked of
the witness, and a failure to send never ends the reading of a budget.

Runs it cannot read (Amendment 16).  A run the courier cannot read ends nothing: every other run is still read in the same
pass.  If the reading failed as a transport fails (a dropped connection, an answer too long or not readable), the courier
asks the witness for a fresh checkpoint with a nonce of its own: if that verifies, the witness is up and the trouble is the
run's; if it does not answer, the pass ends as "the witness cannot be read" (after `stall_after`, COURIER_BLOCKED, naming the
run after which the witness stopped answering).  Either way the run is marked unread, once, with since when and why; the
mark is removed when the run is read, and once it has been unread for `stall_after` one signed notice of it is sent
(UNREADABLE), which says the courier could not read it and does not know its outcome.  A run that cannot be read is never
marked done.

What a pass asks for (Amendment 16, fifth form, A).  Runs whose outcome needs no request to the witness are settled in every
pass.  Every other run not done is in one of two lines: new (never asked for, or its entry in the chain is not what it was
when last asked for), in the chain's order (by the decision at which the chain came to say what it now says of the run);
old (all the others), the one asked for longest ago first, so a run after which
the witness stopped answering stands last.  A budget's pass has `pass_seconds` (600 unless set) for asking: while both lines
hold runs each has half, and a line that is empty gives its half to the other; whatever the time, at least `floor` runs of
each line not empty are asked for, floor being what half of pass_seconds holds at two deadlines a run (a request and the
checkpoint after a failed one), and never less than 1 (2 with the defaults).  A run of the old line is so asked for at least
once in every ceil(old line / floor) passes; the status gives both lines' lengths, how many of each were asked for and put
off at the last pass, and that bound.  A run not asked for, for want of time, is listed as put off, never as unread; if it
bears the unread mark past `stall_after`, its UNREADABLE notice is made in words true of a run not asked for again.  A pass
that put runs off exits 1 and makes no WATCHING statement.

How a pass ends (Amendment 16, fifth form, C; sixth form).  The chain's entries of runs are made records of a fixed shape as
they are read (six items, a name and a phase that are text), in every decision read; a chain that holds another is what the
witness says that cannot be believed.  A RecursionError or MemoryError while an answer is parsed, verified, hashed or worked
out is an answer the courier could not handle (in words that do not say whether its size or depth or the courier's own
memory brought it about); one anywhere else in the courier's own code is an error it did not expect (seventh form, L4).  Every pass over a
budget ends in one of four ways, written in the state whatever happens and shown in the status: read (whole; or with runs
put off, or with runs that could not be read, each said); the witness could not be reached (blocked; COURIER_BLOCKED after
`stall_after`); what the witness said cannot be believed (stopped; COURIER_STOPPED at once); the courier met an error it did
not expect (recorded by its name; COURIER_FAILED after `stall_after`, in words that say the courier cannot tell from this
alone whether something it was given brought it about).  `stall_after` counts from the first pass not completed, whatever
ended it.  A mark that suppresses later work (a run final, a notice sent, the statement made, the budget stopped, an alarm
sent) is set only after the notice it stands for is in the outbox and the state saved; a fault while an ending's own work is
done (its alarm, its mark, refused.jsonl) makes the pass end as an error not expected, and a budget is never marked stopped
without its alarm.  A budget whose own state in the courier's state file is malformed (damaged on disk) is not read in that
pass (summary: own_state); the state the earlier forms wrote is read as it is, not judged malformed; a time in it later than
the courier's clock is set back to the clock (summary: clock_set_back).  A fault in the sending code is kept in the state and
shown in the status; so is a mailbox that has not answered, since when; a damaged log of deliveries is reported, not raised.

Open.  If the service adds new runs faster than a pass can ask for them, the new line grows without end: that is shown (its
length, runs put off, exit 1, no WATCHING statement), not repaired; the bound of the old line holds for passes that reach it.
Budgets are read one after another, so a slow budget delays the next.  A request's DEADLINE bounds how long the courier
waits; the reading thread ends at the deadline once an answer has begun (it is closed, and it looks at the deadline between
reads), but before the answer's headers the socket's timeout (at most what is left of the deadline) applies to each
receive, not to the whole request, so a peer that sends a byte at a time before its headers can keep that thread alive past
the deadline.  A courier whose own state is malformed, that is not running, or that cannot send, tells the mailbox nothing:
only its exit status and its status say so (a signed heartbeat is Amendment 17).  A fault while an INCONSISTENT notice is
made loses that notice: D49's check may only add a notice, so the PASS it qualifies is marked done as always.  Also open, and
stated (seventh form): a receipt taken but not written to deliveries.jsonl (a fault of the disk) leaves the notice listed as
waiting though the mailbox holds it; a state from an earlier form that was stopped without its alarm stays so; status()
ends with the load error when the whole state file is damaged; a damaged head reads as a FORK; every property of A, B and C
except T4, T6, T7 and the pinning of receipts is tested against the stand-in witness and mailbox only.

The seventh form (L1-L7).  A notice is built, then put in the outbox with its mark in memory, then the state saved once,
and only then sent; a notice put and not saved is never sent.  No UNREADABLE notice is made in a pass after the witness
fell in it: a run after which the witness stopped answering gets its notice, once due, at a later pass after that pass's
checkpoint and chain were read and before any run is asked for.  An error of the courier's own while one run is read, or
while its notice is made, is said as such for that run, which is kept (not done) while the pass goes on; a notice that
cannot be made for the waiting time gets one COURIER_FAILED for that run.  A pass whose state cannot be saved says so
(state_not_saved) and the next budget is read; under --every the courier keeps running.

Coverage (Amendment 16).  After its first whole pass over a budget, with the witness readable, the courier makes one signed
statement that it watches that budget from the decision it read to (WATCHING), and sends it as it sends a notice.  Coverage
is confirmed only once the mailbox has accepted it.  The courier knows only the budgets it is configured for.

The words (Amendment 16).  Notices are of form 2 (check_record.notice_text_2): four lines, the last the courier's; everything
the service chose (a run's name, a reason code, a criterion's id, comparison, numbers and units, a detail) is shown as data,
in quotation marks.  D49: after a run's outcome is worked out, if it is PASS and the result's own numbers miss the result's
own stated limit, one more notice (INCONSISTENT) is made; that check can only add that notice.

What the courier refuses.  A checkpoint that is not the witness's, does not sign back its nonce, or names another decision
than asked; another head for the last decision the courier read (a fork); decisions that are not readable, do not follow
on, or do not hash to the checkpoint's head; a run's entry not of the chain's shape; an answer saying that the courier's
last decision is beyond the chain (a rollback).  It stops for that budget, writes what it was told to STATE_DIR/refused.jsonl, and sends the mailbox a signed
notice that it has stopped (COURIER_STOPPED).  It makes no notice of that budget's runs until `resume`.  If it cannot read the
witness for `stall_after` seconds, it sends one notice that it is blocked (COURIER_BLOCKED): the courier is blocked, it cannot
read the witness; notices follow once it can.  None of these, nor COURIER_FAILED, is a notice of a run, and none goes into a
record; nor do UNREADABLE and INCONSISTENT, which are the courier's own judgement.

What it trusts, and what it cannot do.  It sees what the witness records, so a run that never reached the witness is not
seen, and a witness that tells it one consistent false chain is believed.  The witness reads the same database as the
service: the chain is written only through the witness's role, and a stored result is the service's, believed only when
it hashes to the gate's signed digest.  In the demonstration one certificate authority issues every certificate, and the
witness's allow list is set by whoever runs the witness: they can cut the courier off, which it then reports as blocked if
the mailbox is still reachable.  A receipt says the mailbox holds a notice, not that the engineer, or anyone, read it.  The courier is
as independent of the service as the account and machine it runs on: in the demonstration that is the same machine as
everything else.  It needs the Python standard library and `cryptography` (through check_record.py).
"""
import argparse
import fcntl
import http.client
import json
import math
import os
import pathlib
import secrets
import socket
import ssl
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_record as C                                                  # noqa: E402
from mailbox_service import MailboxKey as CourierKey                     # noqa: E402  (the same kind of Ed25519 key)

MAX_ANSWER = 32 * 1024 * 1024
PAGE = 200
FINAL = ('EFFECT', 'NO_EFFECT')                                          # phases a run does not leave
READ = ('EFFECT', 'NO_EFFECT', 'CONSUMED', 'INDETERMINATE', 'INTENT_PENDING')   # phases that may call for a notice
WAIT = ('NO_OUTCOME', 'UNVERIFIED')                                      # outcomes that may yet change: sent only after stall_after


class Refused(Exception):
    """What the witness said cannot be believed, or it contradicts what the courier read before."""


class Unreachable(Exception):
    """A party could not be asked, or did not answer as it must."""


class Answered(Unreachable):
    """A party answered, but not with what was asked (a status other than 200).  It is still there: go on with the rest."""


class NoReceipt(Answered):
    """The mailbox answered 200, but with no valid receipt for the notice (Amendment 16, H10)."""


def now() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def _context(ca, cert, key) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT); ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.check_hostname = True; ctx.verify_mode = ssl.CERT_REQUIRED; ctx.load_verify_locations(cafile=ca)
    ctx.load_cert_chain(cert, key)
    return ctx


DEADLINE = 60.0                                                         # seconds for one whole request, however slowly a party answers


CHUNK = 65536                                                           # an answer is read this much at a time, the deadline looked at between


def https(method: str, url: str, cfg: dict, body=None, timeout: float = 15.0):
    """(status, answer) from a party, over HTTPS with the courier's client certificate; the answer is a JSON object.  The
    whole request has DEADLINE seconds.  Raises Unreachable.  When it gives up at the deadline, the connection is closed, so
    the thread that was reading ends too (Amendment 16, F3): the reader also looks at the deadline between reads."""
    box = {'until': time.monotonic() + DEADLINE}
    def ask():
        try:
            box['answer'] = _https(method, url, cfg, body, timeout, box)
        except BaseException as exc:
            box['error'] = exc
    worker = threading.Thread(target=ask, daemon=True); worker.start(); worker.join(DEADLINE)
    if worker.is_alive():
        box['abandoned'] = True
        _close(box.get('response'))
        raise Unreachable(f'{urllib.parse.urlsplit(url).netloc} did not answer within {int(DEADLINE)} seconds')
    if 'error' in box:
        raise box['error']
    return box['answer']


def _socket_of(response):
    """The socket an answer is read from: of an http.client.HTTPResponse, or of the one an HTTPError holds."""
    r = response
    for _ in range(3):
        if isinstance(r, http.client.HTTPResponse):
            return getattr(getattr(r.fp, 'raw', None), '_sock', None) if r.fp is not None else None
        r = getattr(r, 'fp', None)
    return None


def _close(response) -> None:
    """Close an answer being read from another thread: shut its socket down, so a read waiting on it returns, then close it.
    The close is made in a thread of its own: closing a buffered answer waits for a read that holds it, and the caller must
    not wait (Amendment 16, third form: found with an HTTPError whose body drips)."""
    if response is None:
        return
    try:
        sock = _socket_of(response)
        if sock is not None:
            sock.shutdown(socket.SHUT_RDWR)
    except Exception:
        pass
    def close():
        try:
            response.close()
        except Exception:
            pass
    threading.Thread(target=close, daemon=True).start()


def _read_bounded(r, until, box, limit, url) -> bytes:
    """At most limit + 1 bytes of an answer, never past the deadline (looked at between reads)."""
    raw = bytearray()
    while True:
        if time.monotonic() > until or box.get('abandoned'):
            raise Unreachable(f'{urllib.parse.urlsplit(url).netloc} did not answer within {int(DEADLINE)} seconds')
        chunk = getattr(r, 'read1', r.read)(min(CHUNK, limit + 1 - len(raw)))   # read1: what has come, not a wait for the whole chunk
        if not chunk:
            return bytes(raw)
        raw += chunk
        if len(raw) > limit:
            return bytes(raw)


def _https(method: str, url: str, cfg: dict, body=None, timeout: float = 15.0, box=None):
    box = {} if box is None else box
    until = box.get('until', time.monotonic() + DEADLINE)
    if urllib.parse.urlsplit(url).scheme != 'https':
        raise Unreachable('a party is asked over https only')
    req = urllib.request.Request(url, method=method, data=None if body is None else json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=max(0.001, min(timeout, until - time.monotonic())),   # G5: never longer than what is left
                                    context=_context(cfg['ca'], cfg['cert'], cfg['key'])) as r:
            box['response'] = r
            if box.get('abandoned'):
                _close(r)
            status = r.status
            raw = _read_bounded(r, until, box, MAX_ANSWER, url)     # never more than MAX_ANSWER + 1 bytes, never past the deadline
    except urllib.error.HTTPError as exc:                           # G5: an error's body is read as an answer is: bounded, with the deadline
        box['response'] = exc
        if box.get('abandoned'):
            _close(exc)
        try:
            ans = json.loads(_read_bounded(exc, until, box, 65536, url))
        except Unreachable:
            raise
        except Exception:
            ans = {}
        return exc.code, ans if isinstance(ans, dict) else {}
    except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException) as exc:
        raise Unreachable(f'{urllib.parse.urlsplit(url).netloc} could not be asked ({type(exc).__name__})')
    if len(raw) > MAX_ANSWER:
        raise Unreachable('the answer is too long')
    try:
        ans = json.loads(raw)
    except ValueError:
        raise Unreachable('the answer is not JSON')
    except (RecursionError, MemoryError) as exc:                    # Amendment 16, fifth form: an answer that cannot be parsed for any reason
        raise Unreachable(f'the answer is not readable: it cannot be parsed ({type(exc).__name__}: nested too deeply or too large)')
    if not isinstance(ans, dict):
        raise Unreachable('the answer is not a JSON object')
    return status, ans


def q(**kw) -> str:
    return urllib.parse.urlencode({k: v for k, v in kw.items() if v is not None})


# ---------------------------------------------------------------------------------------------------- reading the witness
def handled(f, *a):
    """f(*a), where f parses, verifies or hashes an answer's data.  A RecursionError or MemoryError there is an answer the
    courier could not handle (Amendment 16, seventh form, L4): Unreachable, in words that do not say whose it is.  An error
    of that kind anywhere else is not caught here, and ends the pass as an error the courier did not expect."""
    try:
        return f(*a)
    except (RecursionError, MemoryError) as exc:
        raise Unreachable(f'the courier could not handle the answer ({type(exc).__name__}); it cannot tell from this alone whether the '
                          'answer\'s size or depth, or its own want of memory, brought it about') from None


def checkpoint(cfg, root, at: int):
    """A checkpoint asked with a nonce of the courier's own, naming decision `at`."""
    nonce = secrets.token_urlsafe(18)
    status, cp = https('GET', f"{cfg['witness_url']}/checkpoint?" + q(root=root, nonce=nonce, at=at), cfg)
    if status == 400 and 'beyond the chain' in str(cp.get('error', '')):
        _, now_cp = https('GET', f"{cfg['witness_url']}/checkpoint?" + q(root=root, nonce=nonce), cfg)
        raise Refused(f'ROLLBACK: the witness says decision {at}, which the courier read before, is beyond its chain', now_cp)
    if status != 200:
        raise Unreachable(f'the witness answered {status} to the checkpoint: {cp.get("error")}')
    bad = handled(C.checkpoint_problems, cp, cfg['witness_keys'], root)
    if not bad and cp.get('nonce') != nonce:
        bad = ['it does not sign back the courier\'s nonce']
    if not bad and cp.get('at') != at:
        bad = [f'it does not name decision {at}']
    if bad:
        raise Refused('the checkpoint cannot be used: ' + '; '.join(bad), cp)
    return cp


def verify_rows(rows, after: int, prev: str, upto: int, head: str) -> list:
    """The decisions after `after` up to `upto`, each following on from `prev` and hashing to itself, the last to `head`."""
    out, n = [], after
    for row in rows:
        if not isinstance(row, dict) or type(row.get('seq')) is not int or row['seq'] != n + 1 or not isinstance(row.get('observation'), dict) \
                or not all(k in row for k in ('op', 'kind', 'code', 'prev_hash', 'hash')):
            raise Refused(f'the witness gave {row.get("seq") if isinstance(row, dict) else type(row).__name__!r} where decision {n + 1} was due, or a decision that is not readable')
        if row.get('prev_hash') != prev or C.chain_hash(prev, row) != row.get('hash'):
            raise Refused(f'decision {n + 1} does not follow on from the one before it, or does not hash to itself')
        out.append(row); prev, n = row['hash'], n + 1
        if n == upto:
            break
    if n != upto or prev != head:
        raise Refused(f'the decisions read do not end at the checkpoint\'s head after decision {upto}')
    return out


def chain(cfg, root, after: int, prev: str, cp, each=lambda row: None):
    """The last decision up to the checkpoint's, after checking every one since `after`, page by page (None if none is new).
    Only the last is kept: a page is checked, given row by row to `each`, and let go before the next is asked."""
    n, last = after, None
    while n < cp['seq']:
        status, page = https('GET', f"{cfg['witness_url']}/chain?" + q(root=root, after=n, limit=max(1, min(PAGE, int(cfg.get('page', PAGE))))), cfg)
        if status != 200:
            raise Unreachable(f'the witness answered {status} to the chain')
        rows = page.get('rows')
        if not isinstance(rows, list) or not rows:
            raise Refused(f'the witness gave no decisions after {n}, though its checkpoint says it holds {cp["seq"]}')
        upto = min(cp['seq'], n + len(rows))
        part = rows[:upto - n]
        end = cp['head'] if upto == cp['seq'] else (part[-1].get('hash') if isinstance(part[-1], dict) else None)   # each row's own hash is recomputed; the last page must end at the checkpoint
        got = handled(verify_rows, part, n, prev, upto, end)
        for row in got:
            handled(each, row)
        n, prev, last = upto, got[-1]['hash'], got[-1]
    return last


def run_outcome(cfg, root, attempt, upto: int) -> tuple[str, dict | None]:
    """(outcome, result) of one run, from the witness's reports and stored result, believed only as far as they check."""
    aid, _req, phase, nonce = attempt[:4]
    if phase not in ('EFFECT', 'CONSUMED'):                          # the chain alone says what these are
        return handled(C.run_outcome, phase, [], None, cfg['gate_keys'], root, aid, nonce), None
    status, ans = https('GET', f"{cfg['witness_url']}/run?" + q(root=root, aid=aid), cfg)
    if status != 200:
        raise Answered(f'the witness answered {status} for run {aid}')
    if not isinstance(ans.get('evidence', []), list):
        raise Refused(f'the witness\'s reports for run {aid} are not a list')
    evidence = [e for e in ans.get('evidence') or [] if isinstance(e, dict) and type(e.get('seq')) is int and e['seq'] <= upto]
    stored = ans.get('result')
    result = stored.get('value') if phase == 'EFFECT' and isinstance(stored, dict) and stored.get('outcome', 'value') == 'value' else None
    return handled(C.run_outcome, phase, evidence, result, cfg['gate_keys'], root, aid, nonce), result


# ---------------------------------------------------------------------------------------------------- notices
def make_notice(cfg, key: CourierKey, root, attempt, outcome, result, seq, head, why_alarm=None) -> dict:
    """A notice of form 2 (Amendment 16), the only form the courier makes: its words are check_record.notice_text_2's, in which
    everything the service chose is shown as data.  why_alarm is the courier's own sentence, for an alarm or an unreadable run."""
    aid, req = (attempt[0], attempt[1]) if attempt else ('', None)
    if outcome == C.WATCHING:
        text = C.watching_text(root, seq, head, cfg['name'])
    else:
        text = C.notice_text_2(outcome, aid, root, result, seq, cfg['name'], why_alarm)
    body = {'statement': 'NOTICE', 'root': root, 'aid': C.field_name(aid), 'request_key': C.field_name(req), 'outcome': outcome, 'reason_code': C.notice_reason(result, 2),   # F4: bounded names
            'detail': C.notice_detail(result), 'result_digest': C.sha(C.canonical(result)) if isinstance(result, dict) else None,
            'seq': seq, 'head': head, 'time': now(), 'courier': cfg['name'], 'text': text, 'form': 2}
    return dict(body, signer=key.public_hex, signature=key.sign(C.canonical({k: body[k] for k in C.NOTICE_FIELDS_2}).encode()))


def deliver(cfg, watch, notice) -> dict:
    """The mailbox's receipt for a notice.  Raises Answered if the mailbox answered, but not with a receipt for it (a refusal
    of this notice), Unreachable if it could not be reached."""
    status, receipt = https('POST', f"{watch['mailbox_url']}/deliver", cfg, notice)
    if status != 200:
        raise Answered(f'the mailbox answered {status}: {receipt.get("error")}')
    bad = C.receipt_problems(receipt, watch['mailbox_keys'], notice)
    if bad:
        raise NoReceipt('the mailbox\'s answer is not a receipt for this notice: ' + '; '.join(bad))
    return receipt


# ---------------------------------------------------------------------------------------------------- state
def _sync_dir(d: pathlib.Path) -> None:
    fd = os.open(d, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_whole(path: pathlib.Path, data: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.tmp-')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        pathlib.Path(tmp).unlink(missing_ok=True); raise
    _sync_dir(path.parent)


def _append(path: pathlib.Path, obj) -> None:
    new = not path.exists()
    torn = False
    if not new and path.stat().st_size:
        with open(path, 'rb') as f:
            f.seek(-1, os.SEEK_END); torn = f.read(1) != b'\n'           # a line left unfinished (a crash): the new one begins on a line of its own
    with open(path, 'a', encoding='utf-8') as f:
        f.write(('\n' if torn else '') + json.dumps(obj, sort_keys=True) + '\n'); f.flush(); os.fsync(f.fileno())
    if new:
        _sync_dir(path.parent)


def delivered_digests(state_dir: pathlib.Path, problems=None) -> set:
    return {C.notice_digest(d['notice']) for d in read_deliveries(state_dir / 'deliveries.jsonl', problems=problems)}


def read_deliveries(path, root=None, problems=None) -> list:
    """The notices delivered and their receipts, from a courier's log, for one budget or all.  A log that cannot be read, or
    a line of it that is not UTF-8 or not JSON, is reported in `problems` (a list, when given) and skipped, never raised
    (Amendment 16, sixth form, K3)."""
    out, p = [], pathlib.Path(path)
    problems = [] if problems is None else problems
    try:
        raw = p.read_bytes() if p.exists() else b''
    except OSError as exc:
        problems.append(f'{p.name} cannot be read ({type(exc).__name__}: {exc})'); return out
    for i, line in enumerate(raw.splitlines(), 1):
        try:
            d = json.loads(line.decode('utf-8'))
        except UnicodeDecodeError:
            problems.append(f'line {i} of {p.name} is not UTF-8'); continue
        except (ValueError, RecursionError):
            problems.append(f'line {i} of {p.name} is not JSON'); continue
        if isinstance(d, dict) and isinstance(d.get('notice'), dict) and (root is None or d['notice'].get('root') == root):
            out.append(d)
    return out


def load_state(sd: pathlib.Path) -> dict:
    sp = sd / 'state.json'
    if not sp.exists():
        return {'roots': {}}
    try:
        state = json.loads(sp.read_text())
        if not isinstance(state, dict) or not isinstance(state.get('roots'), dict):
            raise ValueError('no roots')
        return state
    except (OSError, ValueError) as exc:
        raise SystemExit(f'refused: the courier\'s state ({sp}) cannot be read ({exc}); restore it, or move it aside to start again (notices already sent would be sent again)')


# ---------------------------------------------------------------------------------------------------- one pass
def alarm(cfg, key, watch, st, outcome, why, summary, post) -> None:
    """A notice about the courier itself, put in the outbox and saved; raises if it cannot be made.  Its caller sets the mark
    that stands for it (stopped, blocked_sent, failed_sent) only after this has returned."""
    post.put(make_notice(cfg, key, watch['root'], None, outcome, None, st.get('seq', 0), st.get('head') or '', why_alarm=why))
    summary['made'].append({'root': watch['root'], 'aid': '', 'outcome': outcome})


def inconsistent(result) -> bool:
    """D49 (Amendment 16, P7): True if a result's own criteria say a limit was not met: some criterion with a numeric achieved
    value, a comparison '<=' or '>=' and a numeric limit, compared in decimal arithmetic (check_record.dec), does not meet it.
    Anything it does not understand counts for nothing.  It is asked only of a run whose outcome is already PASS."""
    crit = result.get('criteria') if isinstance(result, dict) else None
    if not isinstance(crit, list):
        return False
    for c in crit:
        if not isinstance(c, dict) or c.get('comparison') not in ('<=', '>='):
            continue
        achieved, limit = C.dec(c.get('achieved')), C.dec(c.get('limit'))
        if achieved is None or limit is None:
            continue
        if not (achieved <= limit if c['comparison'] == '<=' else achieved >= limit):
            return True
    return False


def inconsistent_notice(cfg, key, root, attempt, result, cp, sent):
    """The one notice D49 may add for a run whose outcome is PASS, or None.  Its caller takes any exception, or anything it
    returns that is not that notice, as no finding; any answer of inconsistent() other than True is no finding.  It changes nothing; its caller only appends what it returns.  It decides
    nothing about any other notice, and the PASS is marked final by its caller exactly as before."""
    if f'{attempt[0]}|INCONSISTENT' in sent or inconsistent(result) is not True:
        return None
    return make_notice(cfg, key, root, attempt, 'INCONSISTENT', result, cp['seq'], cp['head'])


def witness_up(cfg, root, cp) -> None:
    """Whether the witness itself answers (Amendment 16, P3), asked when one run's reading failed as a transport would fail (a
    dropped connection, an answer too long or not readable): a fresh checkpoint, with a nonce of the courier's own, that
    verifies and agrees with this pass's.  Raises Unreachable if it does not answer (the witness cannot be read), Refused if
    what it answers cannot be believed; returns if the witness is up, so the trouble is that run's."""
    try:
        again = checkpoint(cfg, root, cp['seq'])
    except Refused:
        raise
    except Unreachable as exc:
        raise Unreachable(f'the witness cannot be read: a run could not be read, and the witness then did not answer a checkpoint ({exc})')
    if again['head_at'] != cp['head']:
        raise Refused(f"FORK: the witness says another head for decision {cp['seq']} than the one it gave earlier in this pass", again)


class WitnessFell(Unreachable):
    """The witness stopped answering after the courier asked it for one run (Amendment 16, F1).  .aid names the run."""

    def __init__(self, message, aid):
        super().__init__(message); self.aid = aid


def _number(v, default):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else default


def _finite(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


ASKS = ('EFFECT', 'CONSUMED')                                             # phases whose outcome needs a request to the witness (GET /run)
ENTRY = 6                                                                 # a run's entry in the chain: name, request key, phase, nonce, receipt, crossed


def entries(attempts) -> list:
    """The runs' entries of a decision of the chain, made records of a fixed shape where they come in (Amendment 16, fifth
    form, C): a list of the chain's length, whose name and phase are text.  Raises Refused for anything else, so that what
    the witness says never makes the courier's own state malformed."""
    if not isinstance(attempts, list):
        raise Refused('the witness gave a decision whose runs are not a list')
    for i, x in enumerate(attempts):
        if not (isinstance(x, list) and len(x) == ENTRY and isinstance(x[0], str) and isinstance(x[2], str)):
            raise Refused(f'the witness gave a decision whose entry {i + 1} of a run is not of the chain\'s shape (a list of {ENTRY} items, '
                          'the run\'s name and its phase text)')
    return [list(x) for x in attempts]


def entry_digest(attempt) -> str:
    """The digest of a run's entry in the chain, as the courier last read it (Amendment 16, H1)."""
    return C.sha(C.canonical(list(attempt)))


def asked_at(asked: dict, aid):
    """(when the run was last asked for, the digest of its entry then) from st['asked']."""
    v = asked.get(aid) or {}
    return _number(v.get('at'), 0), v.get('entry')


def lines(todo, asked, said) -> tuple:
    """The two lines of a pass (Amendment 16, fifth form, A): new, the runs never asked for or whose entry in the chain is not
    what it was when last asked for, in the chain's order: by the decision at which the chain came to say what it now says of
    the run (said), so that no run, however named, waits behind runs the chain spoke of after it; old, all the others, the
    one asked for longest ago first."""
    new = sorted([a for a in todo if asked_at(asked, a[0])[1] != entry_digest(a)], key=lambda a: _number(said.get(a[0]), 0))
    old = sorted([a for a in todo if asked_at(asked, a[0])[1] == entry_digest(a)], key=lambda a: asked_at(asked, a[0])[0])
    return new, old


def floor_of(pass_seconds: float) -> int:
    """How many runs of each line that is not empty are asked for in every pass, whatever the time: what half of pass_seconds
    holds when each request, and the checkpoint that follows a failed one, takes the whole deadline; never less than 1."""
    return max(1, int((pass_seconds / 2) // (2 * DEADLINE)))


def read_witness(cfg, key, watch, st: dict, clock: float, summary: dict, save, post) -> dict:
    """One budget's reading: the checkpoint, the chain, then every run not yet done.  Returns how many runs were put off and
    how many could not be read, and how many notices could not be made.  The rule of the whole file (Amendment 16, sixth
    form, K1; seventh form, L2): a notice is built first; then it is put in the outbox and the mark that suppresses later
    work (final, sent, watching; stopped, blocked_sent, failed_sent in watch_pass) is set, in memory; then the state is
    saved once; only then is anything sent.  So a fault while a notice is built leaves the work to be done again, and a
    fault while the state is saved never leaves a notice on disk without its mark, or sent unsaved."""
    root = watch['root']
    try:
        entries(st.get('attempts', []))                              # what an earlier form kept is checked as what comes in now is
    except Refused:
        raise Refused('an entry of a run that the courier kept from the chain at an earlier pass is not of the chain\'s shape: an earlier form of the '
                      'courier kept it from what the witness said, or the state file was damaged; after courier.py resume the budget is read again from its start')
    cp = checkpoint(cfg, root, st.get('seq', 0))
    if st.get('seq', 0) and cp['head_at'] != st['head']:
        raise Refused(f"FORK: the witness says another head for decision {st['seq']} than the one the courier read", cp)
    said = st.setdefault('said', {})                                 # each run: the decision at which the chain came to say what it now says of it
    known = {a[0]: a for a in st.get('attempts', [])}
    def each(row):                                                   # every decision's entries are checked, not only the last one's
        for a in entries(row['observation'].get('attempts', [])):
            if known.get(a[0]) != a:
                known[a[0]] = a; said[a[0]] = row['seq']
    last = chain(cfg, root, st.get('seq', 0), cp['head_at'] if not st.get('seq') else st['head'], cp, each)
    if last is not None:
        st['attempts'] = entries(last['observation'].get('attempts', []))
    st['seq'], st['head'] = cp['seq'], cp['head']
    sent, final, before = st.setdefault('sent', []), st.setdefault('final', []), st.get('first_seen', {})
    unread = st.setdefault('unread', {})                             # the one mark for trouble: {aid: {since, why}}
    asked = st.setdefault('asked', {})                               # each run not yet done: {at, entry} when last asked for
    stall = float(cfg.get('stall_after', 900))
    share = float(cfg.get('pass_seconds', 600))
    floor = floor_of(share)
    seen = {}                                                        # a wait counts only while the run is seen in that state, pass after pass

    unmade = st.setdefault('unmade', {})                             # runs read whose notice the courier could not make: {aid: {since, why, outcome}}
    unmade_now = []

    def make(attempt, outcome, result=None, why=None, notice=None, done=False):
        """Build the notice (the one step that can fail on data); then put it in the outbox and set its marks, in memory;
        then save once; only then send (Amendment 16, seventh form, L2).  The unread mark goes with the notice (L7)."""
        aid = attempt[0]
        n = notice or make_notice(cfg, key, root, attempt, outcome, result, cp['seq'], cp['head'], why_alarm=why)
        post.put(n); sent.append(f'{aid}|{outcome}')
        if done:
            final.append(aid)
        if outcome != 'UNREADABLE':
            unread.pop(aid, None)
        unmade.pop(aid, None)
        summary['made'].append({'root': root, 'aid': aid, 'outcome': outcome})
        save(); post.send()

    def guarded(attempt, outcome, *a, **k) -> bool:
        """make(), for one run's notice: a fault while it is built keeps the run (not done, not marked sent), names it in the
        summary and the state, and the pass goes on (L5).  After the waiting time, one COURIER_FAILED alarm for the run."""
        aid = attempt[0]
        try:
            make(attempt, outcome, *a, **k); return True
        except Exception as exc:
            why = f'{type(exc).__name__}: {exc}'
            u = unmade.get(aid) if isinstance(unmade.get(aid), dict) else {}
            unmade[aid] = dict(u, since=_number(u.get('since'), clock), why=why, outcome=outcome)
            unmade_now.append(aid)
            summary['courier_failed'].append({'root': root, 'aid': aid, 'why': f'the courier read this run and could not make its {outcome} notice: {why}'})
            if clock - unmade[aid]['since'] >= stall and not unmade[aid].get('alarm_sent'):
                try:
                    name = C.shown(aid, 200)
                except Exception:
                    name = 'a run of this budget'
                try:
                    post.put(make_notice(cfg, key, root, None, 'COURIER_FAILED', None, cp['seq'], cp['head'], why_alarm=UNMADE_WORDS.format(name, _when(unmade[aid]['since']), C.shown(why, 300))))
                    unmade[aid]['alarm_sent'] = True                # the mark with the alarm, one save
                    summary['made'].append({'root': root, 'aid': '', 'outcome': 'COURIER_FAILED'})
                except Exception:
                    pass                                            # no alarm, no mark: tried again at the next pass
            save()
            return False

    def unreadable(attempt, words):
        u = unread.get(attempt[0])
        if isinstance(u, dict) and clock - _number(u.get('since'), clock) >= stall and f'{attempt[0]}|UNREADABLE' not in sent:
            guarded(attempt, 'UNREADABLE', why=words)

    def keep_waits(aid):
        seen.update({k: v for k, v in before.items() if k.startswith(f'{aid}|')})

    todo = [a for a in st.get('attempts', []) if a[0] not in final and a[2] in READ]
    for attempt in st.get('attempts', []):
        if attempt[0] in final or attempt[2] not in READ:
            unread.pop(attempt[0], None); asked.pop(attempt[0], None); said.pop(attempt[0], None); unmade.pop(attempt[0], None)
    for attempt in todo:                                            # L1: the notice of a run after which the witness fell, due now that it answers
        u = unread.get(attempt[0])
        if isinstance(u, dict) and u.get('fell_at') is not None:
            unreadable(attempt, f"When the courier last asked for this run, at {_when(u['fell_at'])} by its clock, the witness stopped answering; "
                                f"the witness has answered the courier's checkpoint since.  The courier has not been able to read this run since {_when(u.get('since'))} by its clock.")
    new, old = lines([a for a in todo if a[2] in ASKS], asked, said)
    count = {'new': [len(new), 0, 0], 'old': [len(old), 0, 0]}       # length, asked, put off
    spent = {'new': 0.0, 'old': 0.0}
    put_off, unread_now = [], 0
    order = [(a, None) for a in todo if a[2] not in ASKS] + [(a, 'new') for a in new] + [(a, 'old') for a in old]
    whole, reached_old = False, not old
    try:
        for attempt, line in order:
            aid, phase = attempt[0], attempt[2]
            reached_old = reached_old or line == 'old'
            if line is not None:
                mine = share if not (new and old) else share / 2 if line == 'new' else share - min(spent['new'], share / 2)
                if count[line][1] >= floor and spent[line] >= mine:   # out of time: it waits for its turn at a later pass
                    count[line][2] += 1; keep_waits(aid)
                    u = unread.get(aid) if isinstance(unread.get(aid), dict) else None
                    put_off.append({'root': root, 'aid': aid, 'line': line, 'why': 'not asked for in this pass, for want of time' + (
                        '; when it was last asked for, the courier could not read it' if u else '')})
                    if u and u.get('fell_at') is None:
                        unreadable(attempt, f"The courier has not been able to read this run since {_when(_number(u.get('since'), clock))} "
                                            f"by its clock; when it last asked for it: {C.shown(u.get('why'), 600)}.  It has not asked for it again since, for want of time in its passes.")
                    continue
                count[line][1] += 1
                asked[aid] = {'at': clock, 'entry': entry_digest(attempt)}   # asked for now: it goes to the end of the old line
            began = time.monotonic()
            def charge():                                           # the time of asking (a request, and the checkpoint after a failed one), not of sending
                if line is not None:
                    spent[line] += time.monotonic() - began
            try:                                                    # Amendment 16 (P1): no run the courier cannot read ends this loop
                outcome, result = run_outcome(cfg, root, attempt, cp['seq'])
            except Refused:
                raise
            except Exception as exc:
                fell, own = None, not isinstance(exc, Unreachable)
                if own:                                             # L3: an error of the courier's own while it read this run
                    why = f'the courier met an error it did not expect while reading this run ({type(exc).__name__}: {exc})'
                    summary['courier_failed'].append({'root': root, 'aid': aid, 'why': why})
                else:
                    why = str(exc)
                    if not isinstance(exc, Answered):               # it failed as a transport fails: is the witness itself up? (P3)
                        try:
                            witness_up(cfg, root, cp)
                        except Unreachable as down:
                            fell = down
                            why = 'the witness stopped answering after the courier asked for this run'
                charge()
                u = unread.get(aid) if isinstance(unread.get(aid), dict) else {}
                unread[aid] = {'since': _number(u.get('since'), clock), 'why': why, 'fell_at': clock if fell is not None else None}
                summary['unread'].append({'root': root, 'aid': aid, 'since': unread[aid]['since'], 'why': why}); unread_now += 1
                keep_waits(aid); save()
                if fell is not None:                                # L1: no UNREADABLE in the pass in which the witness fell after this run
                    raise WitnessFell(f'the witness cannot be read: it stopped answering after the courier asked for run {C.shown(aid, 200)} ({fell})', aid)
                unreadable(attempt, (f'The courier met an error it did not expect while reading this run: {C.shown(f"{type(exc).__name__}: {exc}", 600)}.' if own else
                                     f'What the courier was told: {C.shown(why, 600)}.') + f'  It has not been able to read this run for {int(clock - unread[aid]["since"])} seconds by its clock.')
                continue
            charge()
            done = phase in FINAL and outcome != 'UNVERIFIED'
            if outcome in ('PASS', 'PENDING'):
                try:                                                # D49: it may only add a notice, and only one of its own kind
                    extra = inconsistent_notice(cfg, key, root, attempt, result, cp, sent) if outcome == 'PASS' else None
                    take = isinstance(extra, dict) and extra.get('outcome') == 'INCONSISTENT' and extra.get('aid') == C.field_name(aid) and not C.notice_problems(extra, [key.public_hex])
                except Exception:
                    take = False
                if take:
                    make(attempt, 'INCONSISTENT', notice=extra, done=done)
                else:
                    if done:
                        final.append(aid)
                    unread.pop(aid, None); save()
                continue
            if outcome in WAIT:                                      # what may yet change: no outcome yet, or a result not yet stored
                mark = f'{aid}|{outcome}|{phase}'
                seen[mark] = before.get(mark, clock); waited = clock - seen[mark]
                if waited < stall:
                    unread.pop(aid, None); save()
                    continue
                result = None                                      # the courier vouches for no result it could not match
            if f'{aid}|{outcome}' not in sent:
                guarded(attempt, outcome, result, done=done)       # the run final, its mark and its notice saved together (L2), or kept (L5)
            else:
                if done:
                    final.append(aid)
                unread.pop(aid, None); save()
        whole = True
    finally:
        st['first_seen'] = seen if whole else dict(before, **seen)  # a wait is lost only by a run seen in another state
        bound = math.ceil(count['old'][0] / floor) if count['old'][0] else 0
        st['lines'] = {'at': clock, 'new': count['new'], 'old': count['old'], 'floor': floor, 'bound': bound, 'put_off': put_off, 'reached_old': reached_old}
    summary['put_off_runs'].extend(put_off)
    if put_off:
        summary['put_off'].append({'root': root, 'runs': len(put_off), 'new': count['new'][2], 'old': count['old'][2],
                                   'why': f'the pass had used its {share:g} seconds; they are asked for in their turn at a later pass'})
    if not st.get('watching') and not put_off:                      # Amendment 16 (P6): the first whole pass over this budget, every run asked for
        n = make_notice(cfg, key, root, None, C.WATCHING, None, cp['seq'], cp['head'])
        post.put(n)                                                 # in the outbox and the mark, in memory; one save (L2)
        st['watching'] = {'seq': cp['seq'], 'head': cp['head'], 'notice': C.notice_digest(n), 'made': now()}
        summary['coverage'].append({'root': root, 'seq': cp['seq'], 'state': MADE})
        save()
    return {'put_off': len(put_off), 'unread': unread_now, 'unmade': len(set(unmade_now))}


# ---------------------------------------------------------------------------------------------------- sending
LAST = {'refused': 'refused by the mailbox', 'no receipt': 'the mailbox gave no valid receipt',
        'not sent': 'could not be sent (the mailbox answered when asked for its key)', 'unreached': 'not tried: the mailbox could not be reached',
        'unsent': 'not tried: the courier met an error while sending',
        None: 'not yet tried'}


class Outbox:
    """A budget's notices made and not yet accepted by the mailbox (Amendment 16, fifth form, B), each with a record of its
    own: when made, how many times tried, when last tried, and what came of the last try.  Before notices are sent, and again
    after one fails as a transport fails, the mailbox is asked for its key (GET /pubkey): if it answers with a key given, it
    can be reached and the notice that failed is the one in trouble; if not, nothing more is sent in this pass, and each
    notice not tried is recorded so, with the time.  The one tried longest ago is tried first (never tried first, in the
    order made), and each at most once in a pass; none is dropped.  What the courier knows of the mailbox (since when it
    has not answered) and of its own sending (a fault in it, since when, how many passes) is kept in the state (sixth form,
    K3, K4)."""

    def __init__(self, cfg, watch, st, summary, save, clock):
        self.cfg, self.watch, self.st, self.summary, self.clock = cfg, watch, st, summary, clock
        self.root, self.held, self.tried, self.fault, self.unsaved = watch['root'], None, set(), None, set()
        self.box = st.setdefault('outbox', [])
        def saved():                                                # every save of this budget's pass goes through here
            save(); self.unsaved.clear()
        self.save = saved

    def put(self, notice) -> None:
        """A notice into the outbox, in memory: its caller sets the notice's mark and then saves once (L2).  A notice put and
        not yet saved is never sent."""
        self.box.append({'notice': notice, 'made': now(), 'tries': 0, 'last_try': None, 'turn': None, 'last': None, 'why': None})
        self.unsaved.add(C.notice_digest(notice))

    def reachable(self):
        """None if the mailbox answers with a key given; otherwise why not."""
        try:
            status, ans = https('GET', f"{self.watch['mailbox_url']}/pubkey", self.cfg)
        except Exception as exc:
            return str(exc) if isinstance(exc, Unreachable) else f'{type(exc).__name__}: {exc}'
        if status != 200:
            return f'the mailbox answered {status} when asked for its key'
        if ans.get('public_key') not in self.watch['mailbox_keys']:
            return 'the mailbox answered with a key that is not one given to the courier, so no answer of it can be taken as a receipt'
        return None

    def send(self) -> None:
        """Send what waits, as far as the mailbox can be reached.  Sending never ends the reading of a budget: a fault of the
        courier's own here is kept in the state (send_fault) and the pass goes on."""
        try:
            self._send()
        except Exception as exc:
            self.fault = f'{type(exc).__name__}: {exc}'
            self.summary['courier_failed'].append({'root': self.root, 'why': f'while sending notices: {self.fault}'})
            for r in self.box:                                      # what was not tried says why (K4)
                if C.notice_digest(r['notice']) not in self.tried:
                    r.update(last='unsent', why=f'the courier met an error while sending ({self.fault})', unreached_at=self.clock)

    def _send(self) -> None:
        todo = [r for r in self.box if C.notice_digest(r['notice']) not in self.tried and C.notice_digest(r['notice']) not in self.unsaved]
        if self.held is not None or not todo:
            return
        why = self.reachable()
        if why is not None:
            return self.hold(why)
        self.answered()
        todo.sort(key=lambda r: (r.get('turn') is not None, _number(r.get('turn'), 0)))
        problems = []
        done = delivered_digests(pathlib.Path(self.cfg['state_dir']), problems)
        if problems:
            self.summary['courier_failed'].append({'root': self.root, 'why': 'the log of deliveries is damaged: ' + '; '.join(problems[:5])})
            self.st['deliveries_log'] = {'at': self.clock, 'problems': problems[:5]}
        else:
            self.st.pop('deliveries_log', None)
        for r in todo:
            n = r['notice']; d = C.notice_digest(n)
            self.tried.add(d)
            self.st['turn'] = int(_number(self.st.get('turn'), 0)) + 1
            r.update(tries=int(_number(r.get('tries'), 0)) + 1, last_try=now(), turn=self.st['turn'])
            try:
                receipt = deliver(self.cfg, self.watch, n)
            except NoReceipt as exc:
                r.update(last='no receipt', why=str(exc))
            except Answered as exc:
                r.update(last='refused', why=str(exc))
            except Exception as exc:
                r.update(last='not sent', why=str(exc) if isinstance(exc, Unreachable) else f'{type(exc).__name__}: {exc}')
            else:
                if d not in done:
                    _append(pathlib.Path(self.cfg['state_dir']) / 'deliveries.jsonl', {'notice': n, 'receipt': receipt}); done.add(d)
                self.box.remove(r)
                if n.get('outcome') == C.WATCHING:
                    self.summary['coverage'].append({'root': self.root, 'seq': n.get('seq'), 'state': ACCEPTED})
                else:
                    self.summary['delivered'].append({'root': self.root, 'aid': n.get('aid'), 'outcome': n.get('outcome')})
                continue
            self.summary['undelivered'].append({'root': self.root, 'aid': n.get('aid'), 'outcome': n.get('outcome'), 'kind': LAST[r['last']], 'why': r['why']})
            if r['last'] == 'not sent':
                why = self.reachable()
                if why is not None:
                    self.hold(why); break
        self.save()

    def hold(self, why) -> None:
        """The mailbox could not be reached: nothing more is sent to it in this pass; it is kept in the state since when, and
        each notice not tried in this pass is recorded so."""
        self.held = why
        down = self.st.get('mailbox_down') if isinstance(self.st.get('mailbox_down'), dict) else {}
        self.st['mailbox_down'] = {'since': _number(down.get('since'), self.clock), 'at': self.clock, 'why': why}
        for r in self.box:
            if C.notice_digest(r['notice']) not in self.tried:
                r.update(last='unreached', why=f'the mailbox could not be reached ({why})', unreached_at=self.clock)
        self.save()

    def answered(self) -> None:
        self.st.pop('mailbox_down', None); self.st['mailbox_answered'] = self.clock

    def finish(self) -> None:
        """At the end of the pass: what a fault in sending did is kept in the state (or cleared by a pass with none), and the
        summary lists what waits."""
        f = self.st.get('send_fault') if isinstance(self.st.get('send_fault'), dict) else None
        if self.fault is not None:
            self.st['send_fault'] = {'since': _number((f or {}).get('since'), self.clock), 'at': self.clock, 'why': self.fault, 'passes': int(_number((f or {}).get('passes'), 0)) + 1}
        else:
            self.st.pop('send_fault', None)
        for r in self.box:
            n = r['notice']
            why = f"{LAST.get(r.get('last'), r.get('last'))}: {r.get('why')}"
            if n.get('outcome') == C.WATCHING:
                self.summary['coverage'].append({'root': self.root, 'seq': n.get('seq'), 'state': MADE, 'why': why})
            else:
                self.summary['waiting'].append({'root': self.root, 'aid': n.get('aid'), 'outcome': n.get('outcome'), 'kind': LAST.get(r.get('last'), r.get('last')), 'why': why})
        if self.held is not None:
            self.summary['mailbox'].append({'root': self.root, 'why': self.held, 'since': self.st['mailbox_down']['since']})
        self.save()


# ---------------------------------------------------------------------------------------------------- how a pass ends
ENDINGS = {'read': 'read', 'blocked': 'the witness could not be reached', 'stopped': 'what the witness said cannot be believed',
           'failed': 'the courier met an error it did not expect'}


def watch_pass(cfg, key, watch, st: dict, clock: float, summary: dict, save) -> None:
    """One budget's pass, in three steps that can be seen here (Amendment 16, sixth form, K2): (1) the reading is tried and
    what came of it is put in exactly one of four kinds: read, blocked (the witness could not be reached), stopped (what it
    said cannot be believed), failed (an error the courier did not expect); (2) that ending's own work is done inside a
    guard, its alarm first and its mark after (K1): any fault in that work makes the ending 'failed', whose own work is
    guarded in turn, and a budget is never marked stopped, or its alarm marked sent, without the alarm in the outbox;
    (3) what the pass came to is written in the state whatever happened."""
    post = Outbox(cfg, watch, st, summary, save, clock)
    save = post.save                                                # a save clears what the outbox may now send (L2)
    post.send()                                                     # what is waiting goes out before the witness is asked
    ending = {'at': clock, 'ended': 'failed', 'why': 'the pass was interrupted'}
    try:
        kind, got = 'stopped', None                                 # (1) the reading, classified
        if not st.get('stopped'):
            try:
                kind, got = 'read', read_witness(cfg, key, watch, st, clock, summary, save, post)
            except Refused as exc:
                kind, got = 'stopped', exc
            except Unreachable as exc:
                kind, got = 'blocked', exc
            except Exception as exc:
                kind, got = 'failed', exc
        try:                                                        # (2) the ending's own work, guarded
            ending = END[kind](cfg, key, watch, st, clock, summary, save, post, got)
        except Exception as exc:
            ending = end_failed(cfg, key, watch, st, clock, summary, save, post, exc, also=ENDINGS[kind] if kind != 'failed' else None)
    finally:
        st['last_pass'] = ending                                    # (3) written whatever happened
        save()
        post.send(); post.finish()


def end_read(cfg, key, watch, st, clock, summary, save, post, got) -> dict:
    for k in ('unfinished_since', 'blocked_sent', 'failed_sent'):
        st.pop(k, None)                                             # a pass that read the witness clears the marks
    how = [f'{plural(got["put_off"], "run")} put off for want of time'] if got['put_off'] else []
    how += [f'{plural(got["unread"], "run")} could not be read'] if got['unread'] else []
    how += [f'{plural(got["unmade"], "notice")} could not be made'] if got.get('unmade') else []
    return {'at': clock, 'ended': 'read', 'why': ('read; ' + '; '.join(how)) if how else 'read whole', 'put_off': got['put_off'], 'unread': got['unread'], 'unmade': got.get('unmade', 0)}


def end_stopped(cfg, key, watch, st, clock, summary, save, post, got) -> dict:
    root = watch['root']
    if got is None:                                                 # stopped at an earlier pass
        write_refusal(cfg, st, save)                                # a record that could not be written then is written now
        summary['refused'].append({'root': root, 'why': 'stopped since ' + st['stopped'] + ': see refused.jsonl, then courier.py resume'})
        return {'at': clock, 'ended': 'stopped', 'why': f"not read: the courier stopped reading this budget at {st['stopped']}; see refused.jsonl, then courier.py resume"}
    why = str(got.args[0])
    alarm(cfg, key, watch, st, 'COURIER_STOPPED', STOPPED_WORDS.format(C.shown(why, 600)), summary, post)   # the alarm first,
    st['stopped'] = now()                                                                                    # then the mark,
    st['refusal_unwritten'] = {'time': now(), 'root': root, 'why': why, 'evidence': got.args[1] if len(got.args) > 1 else None}; save()
    summary['refused'].append({'root': root, 'why': why})
    write_refusal(cfg, st, save)                                                                             # then the record
    return {'at': clock, 'ended': 'stopped', 'why': 'what the witness said cannot be believed: ' + C.shown(why, 600)}


def write_refusal(cfg, st, save) -> None:
    """refused.jsonl gets what the witness said; kept in the state until it has been written (a fault here is the pass's
    'failed' ending, and the write is tried again at the next pass)."""
    rec = st.get('refusal_unwritten')
    if isinstance(rec, dict):
        _append(pathlib.Path(cfg['state_dir']) / 'refused.jsonl', rec)
        st.pop('refusal_unwritten', None); save()


def end_blocked(cfg, key, watch, st, clock, summary, save, post, got) -> dict:
    root, stall = watch['root'], float(cfg.get('stall_after', 900))
    since = st.setdefault('unfinished_since', clock); save()
    fell = isinstance(got, WitnessFell)
    state = FELL.format(C.shown(got.aid, 200)) if fell else BLOCKED
    summary['unreachable'].append({'root': root, 'why': str(got)})
    summary['blocked'].append({'root': root, 'since': since, 'state': state})
    if clock - since >= stall and not st.get('blocked_sent'):
        alarm(cfg, key, watch, st, 'COURIER_BLOCKED', (FELL_WORDS.format(int(clock - since), C.shown(got.aid, 200)) if fell else
                                                        BLOCKED_WORDS.format(int(clock - since), C.shown(str(got), 600))), summary, post)
        st['blocked_sent'] = True; save()                           # the mark after the alarm
    return {'at': clock, 'ended': 'blocked', 'why': state, 'run': got.aid if fell else None}


def end_failed(cfg, key, watch, st, clock, summary, save, post, got, also=None) -> dict:
    """The 'failed' ending: never raises.  If its alarm cannot be made, that is said in the ending, failed_sent is not set,
    and it is tried again at the next pass."""
    root, stall = watch['root'], float(cfg.get('stall_after', 900))
    why = f'{type(got).__name__}: {got}'
    if also is not None:
        why = f'{why} (while the courier was ending a pass that came to: {also})'
    since = _number(st.get('unfinished_since'), clock)
    ending = {'at': clock, 'ended': 'failed', 'why': f'{ENDINGS["failed"]} ({C.shown(why, 300)}); it cannot tell from this alone whether something it was given brought it about'}
    summary['courier_failed'].append({'root': root, 'since': since, 'why': why})
    try:
        st['unfinished_since'] = since; save()
        if clock - since >= stall and not st.get('failed_sent'):
            alarm(cfg, key, watch, st, 'COURIER_FAILED', FAILED_WORDS.format(int(clock - since), C.shown(why, 600), _when(since)), summary, post)
            st['failed_sent'] = True; save()                        # the mark after the alarm
    except Exception as exc:
        ending['why'] += f'; its alarm could not be made either ({type(exc).__name__}: {exc}), and is tried again at the next pass'
    return ending


END = {'read': end_read, 'stopped': end_stopped, 'blocked': end_blocked, 'failed': end_failed}


def plural(n, word) -> str:
    return f'{n} {word}' + ('' if n == 1 else 's')


STOPPED_WORDS = ('The courier refused what the witness said: {}.  It makes no notice of this budget\'s runs until this has been looked into '
                 'and the courier is resumed (courier.py resume); notices already made are still sent.')
BLOCKED_WORDS = ('No pass over this budget has been completed for {} seconds by its clock; in the last, the courier has not been able to read the witness: {}.  '
                 'While it cannot, it can make no notice of this budget\'s runs.  '
                 'It tries again at each pass; once it reads the witness again, the notices of the runs it then reads follow, and no other notice that it is blocked '
                 'is made until it has read the witness and then been blocked again.')
FELL_WORDS = ('No pass over this budget has been completed for {} seconds by its clock.  In the last pass, the witness stopped answering after the courier asked it for run {}; '
              'the runs asked for before it in that pass were asked for as usual, and the runs after it were not asked for in that pass.  '
              'The courier tries again at each pass.')
FAILED_WORDS = ('No pass over this budget has been completed for {} seconds by its clock.  In the last, the courier met an error it did not expect: {}.  '
                'It cannot tell from this alone whether something it was given (an answer of the witness or of the mailbox, its own state or configuration) brought it about.  '
                'No pass over this budget has been completed since {} by its clock, and runs of this budget may not have been read or their notices made since then.  '
                'The courier tries again at each pass, and makes no other notice of this kind until it has completed a pass and met such an error again.')
UNMADE_WORDS = ('The courier has read run {} of this budget and has not been able to make its notice since {} by its clock, because of an error it did not expect: {}.  '
                'It cannot tell from this alone whether something it was given brought it about.  It tries again at each pass, and makes no other notice of this kind for that run.')
MADE = 'made, not yet accepted by the mailbox'
ACCEPTED = 'accepted by the mailbox (a signed receipt; not a person\'s acknowledgement)'
BLOCKED = 'the courier is blocked: it cannot read the witness'
FELL = 'the witness stopped answering after the courier asked it for run {}; the runs asked for before it in that pass were asked for as usual'
SUMMARY_WORDS = {'made': 'notices made in this pass; each is ' + MADE + ' until it is listed under delivered',
                 'delivered': 'notices ' + ACCEPTED, 'waiting': 'notices ' + MADE + ', with what came of the last try: tried again at the next pass',
                 'refused': 'budgets the courier has stopped reading: what the witness said cannot be believed',
                 'unreachable': 'budgets whose witness could not be read in this pass', 'blocked': 'budgets whose witness could not be read in this pass, and how',
                 'unread': 'runs the courier could not read from the witness in this pass; their outcome is not known, and they are not marked done',
                 'coverage': 'the courier\'s statement that it watches a budget: ' + MADE + ', or ' + ACCEPTED,
                 'put_off': 'runs not asked for in this pass, for want of time (pass_seconds), by line: they are asked for in their turn at a later pass',
                 'put_off_runs': 'the runs not asked for in this pass, for want of time, each with its line and what is known of it',
                 'own_state': 'budgets not read in this pass because the courier\'s own state for them is malformed: it is the courier\'s own fault, not the witness\'s',
                 'clock_set_back': 'times in the courier\'s own state later than its clock now, set back to now (the clock was set back)',
                 'undelivered': 'tries in this pass that the mailbox did not take, by kind: refused by the mailbox; the mailbox gave no valid receipt; could not be sent',
                 'mailbox': 'budgets whose mailbox could not be reached in this pass (asked for its key): nothing more was sent to it in this pass',
                 'courier_failed': 'budgets whose pass ended, or whose sending stopped, or runs whose reading or notice failed, because the courier met an error it did not expect (it cannot tell from this alone whose fault it is)',
                 'state_not_saved': 'budgets whose state the courier could not save in this pass: nothing it made and did not save was sent; it tries again at the next pass'}


# ---------------------------------------------------------------------------------------------------- the courier's own state
OLD_FIELDS = ('suspect', 'refusals', 'undeliverable', 'put_off_last')     # kept by the four earlier forms; not used by this one


def upgrade(st) -> int:
    """A budget's state as the four earlier forms of Amendment 16 wrote it, brought to this form's shape (never judged
    malformed for that): notices waiting become records of the outbox, with what the earlier form knew of their tries; the
    marks this form does not keep are let go.  How many things were changed."""
    if not isinstance(st, dict):
        return 0
    n = 0
    if 'pending' in st and isinstance(st.get('outbox', []), list):
        refusals = st.get('refusals') if isinstance(st.get('refusals'), dict) else {}
        box = st.setdefault('outbox', [])
        have = {C.notice_digest(r['notice']) for r in box if isinstance(r, dict) and isinstance(r.get('notice'), dict)}
        pending = st.pop('pending'); n += 1
        for notice in pending if isinstance(pending, list) else []:
            if not isinstance(notice, dict) or C.notice_digest(notice) in have:
                continue
            r = refusals.get(C.notice_digest(notice)) if isinstance(refusals.get(C.notice_digest(notice)), dict) else {}
            kind = {UNDELIVERED_4[k]: k for k in UNDELIVERED_4}.get(r.get('kind'), 'refused' if r else None)
            box.append({'notice': notice, 'made': None, 'tries': int(_number(r.get('count'), 0)), 'last_try': r.get('last'), 'turn': None,
                        'last': {'transport': 'not sent'}.get(kind, kind), 'why': r.get('why')})
            have.add(C.notice_digest(notice)); n += 1
    for field in OLD_FIELDS:
        if field in st:
            st.pop(field); n += 1
    for k, v in list((st.get('asked') or {}).items() if isinstance(st.get('asked'), dict) else []):
        if _finite(v):                                              # the third form's plain time, whose entry is not known
            st['asked'][k] = {'at': v, 'entry': None}; n += 1
    since = [st.pop(k) for k in ('blocked_since', 'failed_since') if k in st]   # the fifth form's two times: one now (sixth form, K7)
    if since:
        n += 1
        if all(_finite(x) for x in since):
            st['unfinished_since'] = min(since + ([st['unfinished_since']] if _finite(st.get('unfinished_since')) else []))
        else:
            st['unfinished_since'] = next(x for x in since if not _finite(x))        # left for state_problem to see
    return n


UNDELIVERED_4 = {'refused': 'refused by the mailbox', 'no receipt': 'the mailbox gave no valid receipt',
                 'transport': 'could not be delivered: the mailbox answers for other notices'}     # the fourth form's words, read back


def state_problem(st) -> str | None:
    """What is wrong with the shape of one budget's own state in the courier's state file, or None: what is left after
    upgrade(), a state damaged on disk.  What the witness said never reaches the state unchecked (entries())."""
    if not isinstance(st, dict):
        return 'the budget\'s entry is not an object'
    shapes = {'unread': dict, 'asked': dict, 'said': dict, 'first_seen': dict, 'sent': list, 'final': list, 'outbox': list, 'attempts': list, 'lines': dict, 'last_pass': dict, 'unmade': dict}
    for field, kind in shapes.items():
        if field in st and not isinstance(st[field], kind):
            return f'its field {field} is not a{"n object" if kind is dict else " list"}'
    for aid, u in (st.get('unread') or {}).items():
        if not isinstance(u, dict) or not _finite(u.get('since')):
            return f'its field unread holds an entry for run {C.shown(aid, 80)} whose since is not a finite number'
    for k, v in (st.get('asked') or {}).items():
        if not (isinstance(v, dict) and _finite(v.get('at'))):
            return f'its field asked holds a value for {C.shown(k, 80)} that is not a time'
    for field in ('first_seen', 'said'):
        for k, v in (st.get(field) or {}).items():
            if not _finite(v):
                return f'its field {field} holds a value for {C.shown(k, 80)} that is not a finite number'
    if any(not isinstance(x, str) for x in st.get('sent') or []) or any(not isinstance(x, str) for x in st.get('final') or []):
        return 'its field sent or final holds something that is not text'
    if any(not (isinstance(r, dict) and isinstance(r.get('notice'), dict)) for r in st.get('outbox') or []):
        return 'its field outbox holds something that is not a notice\'s record'
    if 'watching' in st and st['watching'] is not None and not (isinstance(st['watching'], dict) and isinstance(st['watching'].get('notice'), str)):
        return 'its field watching is not a statement the courier made'
    for field in ('seq', 'unfinished_since', 'turn'):
        if field in st and not _finite(st[field]):
            return f'its field {field} is not a finite number'
    if 'head' in st and not isinstance(st['head'], str):
        return 'its field head is not text'
    ln = st.get('lines')
    if ln is not None and not (all(isinstance(ln.get(k), list) and len(ln[k]) == 3 and all(type(x) is int for x in ln[k]) for k in ('new', 'old'))
                               and type(ln.get('floor')) is int and type(ln.get('bound')) is int and isinstance(ln.get('put_off', []), list)
                               and all(isinstance(x, dict) for x in ln.get('put_off', []))):
        return 'its field lines is not of the shape the courier writes'
    for aid, u in (st.get('unmade') or {}).items():
        if not isinstance(u, dict) or not _finite(u.get('since')):
            return f'its field unmade holds an entry for run {C.shown(aid, 80)} whose since is not a finite number'
    for field in ('mailbox_down', 'send_fault', 'deliveries_log', 'refusal_unwritten'):
        if field in st and not isinstance(st[field], dict):
            return f'its field {field} is not an object'
    return None


def set_back(st, clock) -> int:
    """Set every time in a budget's state that is later than the pass's clock to that clock (Amendment 16, H2: the clock was
    set back; nothing is refused for it, and nothing is put off for ever).  How many were set back."""
    n = 0
    def fix(d, k):
        nonlocal n
        if _finite(d.get(k)) and d[k] > clock:
            d[k] = clock; n += 1
    for u in (st.get('unread') or {}).values():
        fix(u, 'since')
    for v in (st.get('asked') or {}).values():
        fix(v, 'at')
    for k in list((st.get('first_seen') or {})):
        fix(st['first_seen'], k)
    fix(st, 'unfinished_since')
    for field in ('mailbox_down', 'send_fault'):
        if isinstance(st.get(field), dict):
            fix(st[field], 'since')
    for u in (st.get('unmade') or {}).values():
        fix(u, 'since')
    return n


def one_pass(cfg, clock: float | None = None) -> dict:
    sd = pathlib.Path(cfg['state_dir']); sd.mkdir(parents=True, exist_ok=True)
    key = CourierKey(pathlib.Path(cfg['key_file']).read_text().strip())
    summary = {'made': [], 'delivered': [], 'waiting': [], 'refused': [], 'unreachable': [], 'unread': [], 'coverage': [], 'blocked': [], 'put_off': [], 'put_off_runs': [],
               'own_state': [], 'clock_set_back': [], 'undelivered': [], 'mailbox': [], 'courier_failed': [], 'state_upgraded': [], 'state_not_saved': [], 'words': SUMMARY_WORDS}
    with open(sd / 'lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)                            # one pass at a time
        state = load_state(sd)
        save = lambda: _write_whole(sd / 'state.json', json.dumps(state, indent=1, sort_keys=True) + '\n')
        clock = time.time() if clock is None else clock
        for watch in cfg['watches']:
            st = state['roots'].setdefault(watch['root'], {})
            changed = upgrade(st)
            if changed:
                summary['state_upgraded'].append({'root': watch['root'], 'changes': changed})
            bad = state_problem(st)
            if bad is not None:                                      # G9, H6: the courier's own state, not the witness's word; not stopped
                summary['own_state'].append({'root': watch['root'], 'why': f"the courier's own state for this budget (in {sd / 'state.json'}) is malformed: {bad}.  "
                                             'It is not read in this pass; restore the state, or move it aside to start again.'})
                continue
            moved = set_back(st, clock)                               # H2
            if moved:
                summary['clock_set_back'].append({'root': watch['root'], 'times': moved})
            try:
                watch_pass(cfg, key, watch, st, clock, summary, save)
            except Exception as exc:                                # one budget's trouble does not stop the others
                summary['courier_failed'].append({'root': watch['root'], 'why': f'{type(exc).__name__}: {exc}'})
                try:
                    save()
                except Exception as exc2:                           # L6: the state cannot be saved: said, and the next budget is read
                    summary['state_not_saved'].append({'root': watch['root'], 'why': f'{type(exc2).__name__}: {exc2}'})
    return summary


def failed(summary) -> bool:
    """Whether a pass leaves anything to look at: a notice waiting, a budget refused or not read, a run not read or put off,
    the courier's own fault, or the courier's statement that it watches a budget not accepted by the mailbox."""
    accepted = {c.get('root') for c in summary.get('coverage', []) if c.get('state') == ACCEPTED}
    return bool(summary['waiting'] or summary['refused'] or summary['unreachable'] or summary.get('unread') or summary.get('put_off') or summary.get('put_off_runs')
                or summary.get('own_state') or summary.get('undelivered') or summary.get('courier_failed') or summary.get('mailbox') or summary.get('state_not_saved')
                or any(c.get('state') != ACCEPTED and c.get('root') not in accepted for c in summary.get('coverage', [])))


def resume(cfg, root) -> dict:
    """After the engineer has looked into a refusal: read the budget again from its first decision.  Notices already sent are
    not sent again.  The courier's statement that it watches the budget is made again after the next whole pass (G10), so
    coverage reads NOT CONFIRMED until the mailbox has accepted that one."""
    sd = pathlib.Path(cfg['state_dir'])
    with open(sd / 'lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = load_state(sd); st = state['roots'].get(root)
        if st is None:
            raise ValueError(f'the courier holds nothing for {root}')
        upgrade(st)
        if isinstance(st.get('refusal_unwritten'), dict):           # L7: what the witness said is written before the budget is read again
            _append(sd / 'refused.jsonl', st['refusal_unwritten']); st.pop('refusal_unwritten')
        for k in ('stopped', 'seq', 'head', 'attempts', 'unfinished_since', 'blocked_sent', 'failed_sent', 'final', 'first_seen', 'unread', 'asked', 'said', 'unmade', 'watching',
                  'lines', 'last_pass'):
            st.pop(k, None)
        _write_whole(sd / 'state.json', json.dumps(state, indent=1, sort_keys=True) + '\n')
    return {'resumed': root}


def load_config(path) -> dict:
    cfg = json.loads(pathlib.Path(path).read_text())
    for k in ('name', 'key_file', 'state_dir', 'witness_url', 'ca', 'cert', 'key', 'witness_keys', 'gate_keys', 'watches'):
        if k not in cfg:
            raise ValueError(f'the configuration has no {k}')
    for w in cfg['watches']:
        if not all(k in w for k in ('root', 'mailbox_url', 'mailbox_keys')):
            raise ValueError('each watch needs root, mailbox_url and mailbox_keys')
    return cfg


STATUS_NOTE = ('The courier knows only the budgets it is configured for: it cannot find a budget by itself, and a budget not listed here '
               'has no courier notices from this courier.  "Accepted by the mailbox" means the mailbox signed a receipt: it is not a person\'s acknowledgement, '
               'and nothing here shows that anyone read a notice.')


def _when(t) -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t)) if _finite(t) else str(t)


def status(cfg) -> dict:
    """For each budget in the configuration (and only those): whether the courier's coverage of it is confirmed, and how its
    last pass ended; whether the courier is blocked, stopped, met an error it did not expect, or cannot send; the two lines,
    what was asked for and put off at the last pass, and the bound; the runs it cannot read; the notices not accepted by the
    mailbox, by kind, and those accepted.  It never raises for one budget: a budget whose own state is malformed, or whose
    status cannot be built, is said to be so (Amendment 16, sixth form, K7)."""
    sd = pathlib.Path(cfg['state_dir'])
    state = load_state(sd)
    out = {}
    for w in cfg['watches']:
        try:
            out[w['root']] = budget_status(sd, w, state['roots'].get(w['root'], {}))
        except Exception as exc:
            out[w['root']] = malformed_status(f'its status could not be built ({type(exc).__name__}: {exc})')
    return {'budgets': out, 'note': STATUS_NOTE}


def malformed_status(bad) -> dict:
    return {'coverage': "NOT CONFIRMED (the courier's own state for this budget is malformed)", 'state': 'malformed: ' + bad,
            'courier': "not reading this budget: the courier's own state for it is malformed; restore it, or move it aside to start again"}


def budget_status(sd, w, st) -> dict:
    st = json.loads(json.dumps(st))                                 # read only: nothing is written back here
    upgrade(st)
    bad = state_problem(st)
    if bad is not None:
        return malformed_status(bad)
    problems = []
    log = read_deliveries(sd / 'deliveries.jsonl', w['root'], problems)
    accepted = {C.notice_digest(d['notice']) for d in log}
    watching = st.get('watching') if isinstance(st.get('watching'), dict) else None
    last = st.get('last_pass') if isinstance(st.get('last_pass'), dict) else {}
    ln = st.get('lines')
    put = (ln or {}).get('put_off') or []
    box = st.get('outbox', [])
    down, fault = st.get('mailbox_down'), st.get('send_fault')
    since = f"no pass completed since {_when(st.get('unfinished_since'))} by its clock"
    if st.get('stopped'):
        coverage = f"NOT CONFIRMED (stopped since {st['stopped']}: the courier makes no notice of this budget's runs until it is resumed)"
    elif watching is None:
        coverage = 'NOT CONFIRMED (not yet read: the courier has not yet completed a pass that read this budget\'s chain to a checkpoint and asked the witness for its runs)'
    elif watching.get('notice') not in accepted:
        coverage = f"NOT CONFIRMED (statement made, not yet accepted by the mailbox: the courier's statement that it watches this budget from decision {watching.get('seq')})"
    else:
        coverage = f"CONFIRMED (the mailbox accepted the courier's statement that it watches this budget, a signed receipt; from decision {watching.get('seq')})"
        if last.get('ended') not in (None, 'read'):
            coverage += f", but the last pass did not read this budget: {last.get('why')}"
        else:
            if put:
                coverage += f", but the last pass did not complete: {plural(len(put), 'run')} put off"
            if last.get('unread'):
                coverage += f", but in the last pass {plural(last['unread'], 'run')} could not be read"
            if last.get('unmade'):
                coverage += f", but in the last pass {plural(last['unmade'], 'notice')} could not be made"
    if fault:
        coverage += f", but the courier cannot send: {C.shown(fault.get('why'), 300)} (since {_when(fault.get('since'))} by its clock, in {plural(fault.get('passes'), 'pass')})".replace('passs', 'passes')
    if down and box:
        coverage += f", but {plural(len(box), 'notice')} {'is' if len(box) == 1 else 'are'} not accepted; the mailbox has not answered since {_when(down.get('since'))} by its clock"
    ended = last.get('ended')
    courier_is = (f"stopped since {st['stopped']}" if st.get('stopped') else
                  f"{last.get('why')} ({since})" if ended == 'blocked' and last.get('run') is not None else
                  f"{BLOCKED} ({since})" if ended == 'blocked' else
                  f"{last.get('why')} ({since})" if ended == 'failed' else 'reading the witness')
    if fault:
        courier_is += f"; and the courier cannot send notices: {C.shown(fault.get('why'), 300)} (since {_when(fault.get('since'))} by its clock)"
    lines_of = None
    if ln:
        b_ = ln['bound']
        lines_of = {'new': {'runs': ln['new'][0], 'asked at the last pass': ln['new'][1], 'put off': ln['new'][2]},
                    'old': {'runs': ln['old'][0], 'asked at the last pass': ln['old'][1], 'put off': ln['old'][2]},
                    'asked in every pass, at least, of each line not empty': ln['floor'],
                    'a run of the old line is asked for at least once in every': f"{b_} pass{'' if b_ == 1 else 'es'} that reach the old line",
                    'the last pass': 'reached the old line' if ln.get('reached_old', True) else 'ended before it reached the old line',
                    'the new line': 'has no bound: its length is shown, and a service that adds new runs faster than a pass can ask for them makes it grow'}
    return {'coverage': coverage, 'courier': courier_is, 'read_to': st.get('seq', 0),
            'last pass': ({'at': last.get('at'), 'ended': ENDINGS.get(ended, ended), 'how': last.get('why')} if last else None),
            'lines': lines_of,
            'runs put off at the last pass': [{'aid': C.shown(p.get('aid'), 200), 'line': p.get('line'), 'why': p.get('why')} for p in put],
            'unread': [{'aid': C.shown(aid, 200), 'since': u.get('since'), 'why': C.shown(u.get('why'), 300)} for aid, u in sorted((st.get('unread') or {}).items())],
            'notices the courier could not make': [{'run': C.shown(aid, 200), 'outcome': u.get('outcome'), 'since': _when(u.get('since')), 'error': C.shown(u.get('why'), 300)}
                                                    for aid, u in sorted((st.get('unmade') or {}).items())],
            'notices not delivered': [dict({'kind': LAST.get(r.get('last'), r.get('last')), 'outcome': C.shown(r['notice'].get('outcome'), 40), 'run': C.shown(r['notice'].get('aid'), 200),
                                            'times': r.get('tries'), 'last tried': r.get('last_try') or 'never', 'last reason': C.shown(r['why'], 300) if r.get('why') is not None else 'none yet'},
                                           **({'not tried at': _when(r.get('unreached_at'))} if r.get('last') in ('unreached', 'unsent') else {})) for r in box],
            'mailbox': ({'not answered since': _when(down.get('since')), 'last asked': _when(down.get('at')), 'why': C.shown(down.get('why'), 300)} if down else
                        f"answered when last asked, at {_when(st['mailbox_answered'])} by its clock" if _finite(st.get('mailbox_answered')) else 'not asked yet'),
            'log of deliveries': ('damaged: ' + '; '.join(problems[:5])) if problems else 'read',
            'notices ' + MADE: sum(r['notice'].get('outcome') != C.WATCHING for r in box),
            'notices ' + ACCEPTED: sum(d['notice'].get('outcome') != C.WATCHING for d in log),
            'sent': len(st.get('sent', [])), 'waiting': len(box), 'delivered': len(log), 'stopped': st.get('stopped')}


def main():
    ap = argparse.ArgumentParser(description='The courier: notices the verification service does not write (Amendment 11).')
    ap.add_argument('action', choices=['keygen', 'run', 'status', 'resume']); ap.add_argument('path', nargs='?')
    ap.add_argument('--config'); ap.add_argument('--every', type=float); ap.add_argument('--root')
    a = ap.parse_args()
    if a.action == 'keygen':
        if not a.path:
            ap.error('keygen KEYFILE')
        k = CourierKey(); p = pathlib.Path(a.path)
        p.write_text(k.private_hex + '\n'); p.chmod(0o600)
        print(json.dumps({'courier_key': k.public_hex})); return
    if not a.config:
        ap.error('--config is needed')
    try:
        cfg = load_config(a.config)
    except (OSError, ValueError) as exc:
        print(f'refused: {exc}', file=sys.stderr); sys.exit(2)
    if a.action == 'status':
        print(json.dumps(status(cfg), indent=1)); return
    if a.action == 'resume':
        if not a.root:
            ap.error('resume needs --root')
        print(json.dumps(resume(cfg, a.root))); return
    while True:
        try:
            s = one_pass(cfg)
        except Exception as exc:                                    # L6: a pass that could not be made at all is said; under --every the courier keeps running
            s = {'courier_failed': [{'root': None, 'why': f'the pass could not be made: {type(exc).__name__}: {exc}'}], 'waiting': [], 'refused': [], 'unreachable': []}
        print(json.dumps(s), flush=True)
        if a.every is None:
            sys.exit(1 if failed(s) else 0)
        time.sleep(max(1.0, a.every))


if __name__ == '__main__':
    main()
