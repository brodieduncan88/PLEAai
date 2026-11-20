#!/usr/bin/env python3
"""The courier: notices to the responsible engineer that the verification service does not write (Amendment 11).

    courier.py keygen KEYFILE                    write a new courier key; print its public half
    courier.py run --config CONFIG [--every S]   one pass over every budget watched (or a pass every S seconds)
    courier.py status --config CONFIG            for each budget configured: coverage, blocked or stopped, runs not read,
                                                 notices made and not yet accepted by the mailbox, and accepted
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
then appended to STATE_DIR/deliveries.jsonl, and a record can carry them (verify_ctl.py record --deliveries).  A notice made
and not yet accepted by the mailbox stays waiting and is sent again at the next pass, and what is waiting is sent before the
witness is asked.  Each request has 60 seconds, however slowly a party answers, and no answer is read past 32 MiB and a byte.
A pass exits 0 if nothing is waiting, refused, unreachable or unread and the courier's coverage statement, once made, has been
accepted; and 1 otherwise.

Runs it cannot read (Amendment 16).  A run the courier cannot read ends nothing: every other run is still read in the same
pass, wherever it sorts.  If the reading failed as a transport fails (a dropped connection, an answer too long or not
readable), the courier asks the witness for a fresh checkpoint with a nonce of its own: if that verifies, the witness is up
and the trouble is the run's; only if it does not answer is the pass ended as "the witness cannot be read" (and then, after
`stall_after`, COURIER_BLOCKED, naming the run after which the witness stopped answering).  That run is then recorded as
one after which the witness stopped answering (status: "runs after which the witness stopped answering"); so a witness
that simply goes down in the middle of a pass marks one run so, once, with no notice of it.  If the witness stops
answering after the same run a second time, the run is also listed as unread and, after `stall_after` from the first
time, gets its UNREADABLE notice.  A pass asks first for every run with no trouble recorded, then for the runs it could not
read, then for those after which the witness stopped answering, each of the last two groups the one asked for longest ago
first.  (Amendment 16, third form, G1: the order is in three tiers: A, runs never asked for, in the chain's order; B, runs
asked for before with no trouble recorded, the one asked longest ago first; C, runs it could not read or after which the
witness stopped answering, one queue, the one asked longest ago first.  A run leaves the second list only after two clean
readings in a row.)  Once `pass_seconds` (600 unless set) have gone in a budget's pass, runs of tiers B and C are not asked
for in that pass, except that at least one of each is; they stay listed, an unread run past `stall_after`, or one after
which the witness stopped answering, still gets its UNREADABLE notice, the pass reports them as put off and exits 1, and
no WATCHING statement is made in such a pass.  A notice is sent as soon as it is made.  A notice the mailbox refuses is
kept, its refusals counted (status: "notices the mailbox refused"), and the next is tried; once the mailbox cannot be
reached, no other notice is tried until the end of the pass, and at the end of the pass delivery stops at the first notice
the mailbox cannot be reached for.  A budget whose own state in the courier's state file is malformed is refused for that
pass, saying so; it is not marked stopped.

Open.  Tier A is not bounded: a first pass over N new runs that do not answer costs N deadlines, and a service that adds
slow new runs at every pass can keep tiers B and C to one run each per pass (that is visible: put off, exit 1, no
WATCHING).  Budgets are read one after another, so a slow budget delays the next.  A request's DEADLINE bounds how long
the courier waits; the reading thread ends at the deadline once an answer has begun (it is closed, and it looks at the
deadline between reads), but before the answer's headers the socket's timeout (at most what is left of the deadline)
applies to each receive, not to the whole request, so a peer that sends a byte at a time before its headers can keep that
thread alive past the deadline.  A run that cannot be read is never marked done; it is in the summary and the status, with
since when and why, and once it has been unreadable for `stall_after` one signed notice of it is sent (UNREADABLE), which says
the courier could not read it and does not know its outcome.  When it reads again it is handled as any other run.

Coverage (Amendment 16).  After its first whole pass over a budget, with the witness readable, the courier makes one signed
statement that it watches that budget from the decision it read to (WATCHING), and sends it as it sends a notice.  Coverage
is confirmed only once the mailbox has accepted it.  The courier knows only the budgets it is configured for.

The words (Amendment 16).  Notices are of form 2 (check_record.notice_text_2): four lines, the last the courier's; everything
the service chose (a run's name, a reason code, a criterion's id, comparison, numbers and units, a detail) is shown as data,
in quotation marks.  D49: after a run's outcome is worked out, if it is PASS and the result's own numbers miss the result's
own stated limit, one more notice (INCONSISTENT) is made; that check can only add that notice.

What the courier refuses.  A checkpoint that is not the witness's, does not sign back its nonce, or names another decision
than asked; another head for the last decision the courier read (a fork); decisions that are not readable, do not follow
on, or do not hash to the checkpoint's head; an answer saying that the courier's last decision is beyond the chain (a
rollback).  It stops for that budget, writes what it was told to STATE_DIR/refused.jsonl, and sends the mailbox a signed
notice that it has stopped (COURIER_STOPPED).  It makes no notice of that budget's runs until `resume`.  If it cannot read the
witness for `stall_after` seconds, it sends one notice that it is blocked (COURIER_BLOCKED): the courier is blocked, it cannot
read the witness; notices follow once it can.  Neither is a notice of a run, and neither goes into a record; nor do UNREADABLE
and INCONSISTENT, which are the courier's own judgement.

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
    if not isinstance(ans, dict):
        raise Unreachable('the answer is not a JSON object')
    return status, ans


def q(**kw) -> str:
    return urllib.parse.urlencode({k: v for k, v in kw.items() if v is not None})


# ---------------------------------------------------------------------------------------------------- reading the witness
def checkpoint(cfg, root, at: int):
    """A checkpoint asked with a nonce of the courier's own, naming decision `at`."""
    nonce = secrets.token_urlsafe(18)
    status, cp = https('GET', f"{cfg['witness_url']}/checkpoint?" + q(root=root, nonce=nonce, at=at), cfg)
    if status == 400 and 'beyond the chain' in str(cp.get('error', '')):
        _, now_cp = https('GET', f"{cfg['witness_url']}/checkpoint?" + q(root=root, nonce=nonce), cfg)
        raise Refused(f'ROLLBACK: the witness says decision {at}, which the courier read before, is beyond its chain', now_cp)
    if status != 200:
        raise Unreachable(f'the witness answered {status} to the checkpoint: {cp.get("error")}')
    bad = C.checkpoint_problems(cp, cfg['witness_keys'], root)
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


def chain(cfg, root, after: int, prev: str, cp):
    """The last decision up to the checkpoint's, after checking every one since `after`, page by page (None if none is new).
    Only the last is kept: a page is checked and let go before the next is asked."""
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
        got = verify_rows(part, n, prev, upto, end)
        n, prev, last = upto, got[-1]['hash'], got[-1]
    return last


def run_outcome(cfg, root, attempt, upto: int) -> tuple[str, dict | None]:
    """(outcome, result) of one run, from the witness's reports and stored result, believed only as far as they check."""
    aid, _req, phase, nonce = attempt[:4]
    if phase not in ('EFFECT', 'CONSUMED'):                          # the chain alone says what these are
        return C.run_outcome(phase, [], None, cfg['gate_keys'], root, aid, nonce), None
    status, ans = https('GET', f"{cfg['witness_url']}/run?" + q(root=root, aid=aid), cfg)
    if status != 200:
        raise Answered(f'the witness answered {status} for run {aid}')
    if not isinstance(ans.get('evidence', []), list):
        raise Refused(f'the witness\'s reports for run {aid} are not a list')
    evidence = [e for e in ans.get('evidence') or [] if isinstance(e, dict) and type(e.get('seq')) is int and e['seq'] <= upto]
    stored = ans.get('result')
    result = stored.get('value') if phase == 'EFFECT' and isinstance(stored, dict) and stored.get('outcome', 'value') == 'value' else None
    return C.run_outcome(phase, evidence, result, cfg['gate_keys'], root, aid, nonce), result


# ---------------------------------------------------------------------------------------------------- notices
def make_notice(cfg, key: CourierKey, root, attempt, outcome, result, seq, head, waited=None, why_alarm=None) -> dict:
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
        raise Answered('the mailbox\'s answer is not a receipt for this notice: ' + '; '.join(bad))
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
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(obj, sort_keys=True) + '\n'); f.flush(); os.fsync(f.fileno())
    if new:
        _sync_dir(path.parent)


def delivered_digests(state_dir: pathlib.Path) -> set:
    return {C.notice_digest(d['notice']) for d in read_deliveries(state_dir / 'deliveries.jsonl')}


def read_deliveries(path, root=None) -> list:
    """The notices delivered and their receipts, from a courier's log, for one budget or all."""
    out, p = [], pathlib.Path(path)
    if p.exists():
        for line in p.read_text(encoding='utf-8').splitlines():
            try:
                d = json.loads(line)
            except ValueError:
                continue
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
def alarm(cfg, key, watch, st, outcome, why, summary) -> None:
    """A notice about the courier itself, once for each time it is stopped or blocked."""
    st.setdefault('pending', []).append(make_notice(cfg, key, watch['root'], None, outcome, None, st.get('seq', 0), st.get('head') or '', why_alarm=why))
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
    """The one notice D49 may add for a run whose outcome is PASS, or None.  It never raises: any exception, or any answer of
    inconsistent() other than True, is no finding.  It changes nothing; its caller only appends what it returns.  It decides
    nothing about any other notice, and the PASS is marked final by its caller exactly as before."""
    try:
        if f'{attempt[0]}|INCONSISTENT' in sent or inconsistent(result) is not True:
            return None
        return make_notice(cfg, key, root, attempt, 'INCONSISTENT', result, cp['seq'], cp['head'])
    except Exception:
        return None


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


def reading_order(todo, unread: dict, suspect: dict, asked: dict) -> list:
    """The order in which a pass asks for runs (Amendment 16, G1): tier A, runs never asked for, in the chain's order; tier B,
    runs asked for before with no trouble recorded, the one asked longest ago first; tier C, runs the courier could not read
    or after which the witness stopped answering, one queue, the one asked longest ago first.  [(attempt, tier)]"""
    when = lambda aid: _number(asked.get(aid), 0)
    trouble = lambda aid: aid in unread or aid in suspect
    tier_a = [a for a in todo if a[0] not in asked and not trouble(a[0])]
    tier_b = sorted([a for a in todo if a[0] in asked and not trouble(a[0])], key=lambda a: when(a[0]))
    tier_c = sorted([a for a in todo if trouble(a[0])], key=lambda a: when(a[0]))
    return [(a, 'A') for a in tier_a] + [(a, 'B') for a in tier_b] + [(a, 'C') for a in tier_c]


def read_witness(cfg, key, watch, st: dict, clock: float, summary: dict, save, deliver_now=lambda: None, started=None) -> None:
    root = watch['root']
    started = time.monotonic() if started is None else started
    cp = checkpoint(cfg, root, st.get('seq', 0))
    if st.get('seq', 0) and cp['head_at'] != st['head']:
        raise Refused(f"FORK: the witness says another head for decision {st['seq']} than the one the courier read", cp)
    last = chain(cfg, root, st.get('seq', 0), cp['head_at'] if not st.get('seq') else st['head'], cp)
    if last is not None:
        st['attempts'] = [list(x[:4]) for x in last['observation'].get('attempts', []) if isinstance(x, list) and len(x) >= 4]
    st['seq'], st['head'] = cp['seq'], cp['head']
    sent, final, before = st.setdefault('sent', []), st.setdefault('final', []), st.get('first_seen', {})
    unread = st.setdefault('unread', {})                             # Amendment 16 (P2): runs the courier could not read, by name: {since, why, last}
    suspect = st.setdefault('suspect', {})                           # Amendment 16 (F1, G1e): runs after which the witness stopped answering: {since, last, times, clean}
    asked = st.setdefault('asked', {})                               # Amendment 16 (G1): when each run not yet done was last asked for
    stall = float(cfg.get('stall_after', 900))
    budget = float(cfg.get('pass_seconds', 600))                     # Amendment 16 (F2, G1, G2): time for one budget's pass, for runs asked for before
    seen, put_off, asked_in = {}, 0, {'B': 0, 'C': 0}                # a wait counts only while the run is seen in that state, pass after pass

    def unreadable_notice(attempt, since, why, words=None):
        aid = attempt[0]
        if clock - since >= stall and f'{aid}|UNREADABLE' not in sent:     # once per run, its own mark (P2)
            st.setdefault('pending', []).append(make_notice(cfg, key, root, attempt, 'UNREADABLE', None, cp['seq'], cp['head'], why_alarm=words or (
                f'What the courier was told: {C.shown(why, 600)}.  It has not been able to read this run for {int(clock - since)} seconds.')))
            sent.append(f'{aid}|UNREADABLE'); summary['made'].append({'root': root, 'aid': aid, 'outcome': 'UNREADABLE'})
            save(); deliver_now()

    todo = [a for a in st.get('attempts', []) if a[0] not in final and a[2] in READ]
    for attempt in st.get('attempts', []):
        if attempt[0] in final or attempt[2] not in READ:
            unread.pop(attempt[0], None); suspect.pop(attempt[0], None); asked.pop(attempt[0], None)
    for attempt, tier in reading_order(todo, unread, suspect, asked):
        aid, phase = attempt[0], attempt[2]
        if tier != 'A' and asked_in[tier] >= 1 and time.monotonic() - started >= budget:
            put_off += 1                                            # out of time (G1): it waits for its turn at a later pass, still listed
            seen.update({k: v for k, v in before.items() if k.startswith(f'{aid}|')})
            u, f = unread.get(aid), suspect.get(aid)
            if isinstance(u, dict):
                since = _number(u.get('since'), clock)
                summary['unread'].append({'root': root, 'aid': aid, 'since': since, 'why': u.get('why'), 'put_off': True})
                unreadable_notice(attempt, since, str(u.get('why')))
            elif isinstance(f, dict):                               # G1b: the witness stopped answering once when it was asked for this run
                since = _number(f.get('since'), clock)
                why = 'the witness stopped answering when the courier asked for this run, and it has not been asked for since, for want of time'
                summary['unread'].append({'root': root, 'aid': aid, 'since': since, 'why': why, 'put_off': True})
                unreadable_notice(attempt, since, why, words=(
                    f"The courier has not been able to read this run since {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(since))} by its clock: "
                    'the witness stopped answering when the courier asked for it, and the courier has not asked again since, for want of time in its passes.'))
            continue
        if tier != 'A':
            asked_in[tier] += 1
        asked[aid] = clock                                          # G1: when it was asked for, whatever comes of it
        try:                                                        # Amendment 16 (P1): no run the courier cannot read ends this loop
            outcome, result = run_outcome(cfg, root, attempt, cp['seq'])
        except Refused:
            raise
        except Exception as exc:
            if not isinstance(exc, Answered):                       # it failed as a transport fails: is the witness itself up? (P3)
                try:
                    witness_up(cfg, root, cp)
                except Unreachable as down:                         # the witness stopped answering after this run was asked for (F1)
                    was = suspect.get(aid) if isinstance(suspect.get(aid), dict) else {}
                    since, times = _number(was.get('since'), clock), int(_number(was.get('times'), 0)) + 1
                    suspect[aid] = {'since': since, 'last': clock, 'times': times, 'clean': 0}   # G1e: a fall sets the clean reads back to none
                    if times >= 2:                                  # twice: it is this run's trouble too, and visible as such
                        why = f'the witness stopped answering after this run was asked for, {times} times'
                        u = unread.get(aid) if isinstance(unread.get(aid), dict) else {}
                        unread[aid] = {'since': _number(u.get('since'), since), 'why': why, 'last': clock}
                        summary['unread'].append({'root': root, 'aid': aid, 'since': unread[aid]['since'], 'why': why})
                        unreadable_notice(attempt, unread[aid]['since'], why)
                    st['first_seen'] = dict(before, **seen)          # every wait is kept
                    save()
                    raise WitnessFell(f'the witness cannot be read: it stopped answering after the courier asked for run {C.shown(aid, 200)} ({down})', aid)
                except BaseException:
                    st['first_seen'] = dict(before, **seen)
                    raise
            seen.update({k: v for k, v in before.items() if k.startswith(f'{aid}|')})   # its waits go on, though it was not read this time
            why = str(exc) if isinstance(exc, Unreachable) else f'{type(exc).__name__}: {exc}'
            was = unread.get(aid) if isinstance(unread.get(aid), dict) else {}
            since = _number(was.get('since'), clock)
            unread[aid] = {'since': since, 'why': why, 'last': clock}
            if aid in suspect:
                suspect[aid]['last'] = clock
            summary['unread'].append({'root': root, 'aid': aid, 'since': since, 'why': why})
            save()
            unreadable_notice(attempt, since, why)
            continue
        unread.pop(aid, None)                                       # read: it is handled as any other run, so its true notice follows
        if isinstance(suspect.get(aid), dict):                      # G1e: it leaves the suspect list only after two clean readings in a row
            suspect[aid]['clean'] = int(_number(suspect[aid].get('clean'), 0)) + 1; suspect[aid]['last'] = clock
            if suspect[aid]['clean'] >= 2:
                suspect.pop(aid, None)
        done = phase in FINAL and outcome != 'UNVERIFIED'
        if outcome in ('PASS', 'PENDING'):
            try:                                                    # D49: it may only add a notice, and only one of its own kind
                extra = inconsistent_notice(cfg, key, root, attempt, result, cp, sent) if outcome == 'PASS' else None
                take = isinstance(extra, dict) and extra.get('outcome') == 'INCONSISTENT' and extra.get('aid') == C.field_name(aid) and not C.notice_problems(extra, [key.public_hex])
            except Exception:
                take = False
            if take:
                st.setdefault('pending', []).append(extra); sent.append(f'{aid}|INCONSISTENT')
                summary['made'].append({'root': root, 'aid': aid, 'outcome': 'INCONSISTENT'}); save(); deliver_now()
            if done:
                final.append(aid)
            continue
        waited = None
        if outcome in WAIT:                                          # what may yet change: no outcome yet, or a result not yet stored
            mark = f'{aid}|{outcome}|{phase}'
            seen[mark] = before.get(mark, clock); waited = clock - seen[mark]
            if waited < stall:
                continue
            result = None                                          # the courier vouches for no result it could not match
        made_one = False
        if f'{aid}|{outcome}' not in sent:
            st.setdefault('pending', []).append(make_notice(cfg, key, root, attempt, outcome, result, cp['seq'], cp['head'], waited))
            sent.append(f'{aid}|{outcome}'); summary['made'].append({'root': root, 'aid': aid, 'outcome': outcome}); made_one = True
        if done:
            final.append(aid)                                      # final only once its notice is made
        save()                                                     # a notice made is kept before anything else
        if made_one:
            deliver_now()                                          # and sent at once (F2)
    st['first_seen'] = seen
    if put_off:
        summary['put_off'].append({'root': root, 'runs': put_off, 'why': f'the pass had used its {budget:g} seconds; they are asked for in their turn at a later pass'})
    if not st.get('watching') and not put_off:                      # Amendment 16 (P6, G1c): the first whole pass over this budget, every run asked for
        n = make_notice(cfg, key, root, None, C.WATCHING, None, cp['seq'], cp['head'])
        st.setdefault('pending', []).append(n)
        st['watching'] = {'seq': cp['seq'], 'head': cp['head'], 'notice': C.notice_digest(n), 'made': now(), 'accepted': None}
        summary['coverage'].append({'root': root, 'seq': cp['seq'], 'state': MADE})
        save()


def watch_pass(cfg, key, watch, st: dict, clock: float, summary: dict, save) -> None:
    root = watch['root']
    started = time.monotonic()
    held_back = {'failed': False}                                    # once a delivery fails in this pass, none is tried again before its end (F2)
    def deliver_now():
        if not held_back['failed'] and st.get('pending'):
            held_back['failed'] = _deliver_pending(cfg, watch, st, summary, save, quiet=True, stop_at_first=True)
    if st.get('pending'):
        held_back['failed'] = _deliver_pending(cfg, watch, st, summary, save, quiet=True, stop_at_first=True)   # what is waiting goes out before the witness is asked
    if st.get('stopped'):
        summary['refused'].append({'root': root, 'why': 'stopped since ' + st['stopped'] + ': see refused.jsonl, then courier.py resume'})
    else:
        try:
            read_witness(cfg, key, watch, st, clock, summary, save, deliver_now, started)
            st.pop('blocked_since', None); st.pop('blocked_sent', None)    # a pass that read the witness clears the mark; one run's trouble never sets it
        except Refused as exc:
            st['stopped'] = now()
            _append(pathlib.Path(cfg['state_dir']) / 'refused.jsonl', {'time': now(), 'root': root, 'why': str(exc.args[0]), 'evidence': exc.args[1] if len(exc.args) > 1 else None})
            summary['refused'].append({'root': root, 'why': str(exc.args[0])})
            alarm(cfg, key, watch, st, 'COURIER_STOPPED', STOPPED_WORDS.format(C.shown(str(exc.args[0]), 600)), summary)
        except (Unreachable, KeyError, TypeError, AttributeError, IndexError) as exc:
            if not isinstance(exc, Unreachable):                    # an answer the courier could not even read is not believed
                st['stopped'] = now()
                why = f'an answer of the witness could not be read ({type(exc).__name__}: {exc})'
                _append(pathlib.Path(cfg['state_dir']) / 'refused.jsonl', {'time': now(), 'root': root, 'why': why, 'evidence': None})
                summary['refused'].append({'root': root, 'why': why})
                alarm(cfg, key, watch, st, 'COURIER_STOPPED', STOPPED_WORDS.format(C.shown(why, 600)), summary)
                save(); return _deliver_pending(cfg, watch, st, summary, save)
            since = st.setdefault('blocked_since', clock)            # only the checkpoint, the chain, or a run's failure with the witness then not answering
            summary['unreachable'].append({'root': root, 'why': str(exc)})
            summary['blocked'].append({'root': root, 'since': since, 'state': BLOCKED})
            if clock - since >= float(cfg.get('stall_after', 900)) and not st.get('blocked_sent'):
                st['blocked_sent'] = True
                if isinstance(exc, WitnessFell):                    # G7: what is true when it is one run that stops the witness
                    words = FELL_WORDS.format(int(clock - since), C.shown(exc.aid, 200))
                else:
                    words = BLOCKED_WORDS.format(int(clock - since), C.shown(str(exc), 600))
                alarm(cfg, key, watch, st, 'COURIER_BLOCKED', words, summary)
        save()
    _deliver_pending(cfg, watch, st, summary, save)


STOPPED_WORDS = ('The courier refused what the witness said: {}.  It makes no notice of this budget\'s runs until this has been looked into '
                 'and the courier is resumed (courier.py resume); notices already made are still sent.')
BLOCKED_WORDS = ('For {} seconds the courier has not been able to read the witness: {}.  While it cannot, it can make no notice of this budget\'s runs.  '
                 'It tries again at each pass; once it reads the witness again, the notices of the runs it then reads follow, and no other notice that it is blocked '
                 'is made until it has read the witness and then been blocked again.')
FELL_WORDS = ('No pass over this budget has been completed for {} seconds: in each, the witness stopped answering after the courier asked it for run {}.  '
              'In each such pass the runs asked for before it were read and their notices made; the runs after it were not asked for in that pass.  '
              'The courier tries again at each pass, and asks for that run after the others.')
MADE = 'made, not yet accepted by the mailbox'
ACCEPTED = 'accepted by the mailbox (a signed receipt; not a person\'s acknowledgement)'
BLOCKED = 'the courier is blocked: it cannot read the witness'
SUMMARY_WORDS = {'made': 'notices made in this pass; each is ' + MADE + ' until it is listed under delivered',
                 'delivered': 'notices ' + ACCEPTED, 'waiting': 'notices ' + MADE + ': sent again at the next pass',
                 'refused': 'budgets the courier has stopped reading: what the witness said cannot be believed',
                 'unreachable': 'budgets whose witness, or whose pass, could not be read in this pass', 'blocked': 'budgets for which ' + BLOCKED,
                 'unread': 'runs the courier could not read from the witness, which answers; their outcome is not known, and they are not marked done',
                 'coverage': 'the courier\'s statement that it watches a budget: ' + MADE + ', or ' + ACCEPTED,
                 'put_off': 'runs already in trouble that were not asked for in this pass, for want of time (pass_seconds); still listed, and asked for first in their turn'}


def _deliver_pending(cfg, watch, st, summary, save, quiet: bool = False, stop_at_first: bool = True) -> bool:
    """Send what is waiting, in order; True if the mailbox could not be reached.  A notice the mailbox refuses (it answers,
    but not with a receipt) is kept waiting, its refusals counted in the state, and the next is tried (G3).  Once the mailbox
    cannot be reached, no other notice is tried in this call: they wait for the next (G4: one deadline, not one for each
    notice).  stop_at_first is kept for its callers and is always so."""
    root = watch['root']
    done = delivered_digests(pathlib.Path(cfg['state_dir']))
    refusals = st.setdefault('refusals', {})
    waiting, unreachable = [], None
    for notice in st.get('pending', []):
        coverage = isinstance(notice, dict) and notice.get('outcome') == C.WATCHING
        entry = {'root': root, 'aid': notice.get('aid') if isinstance(notice, dict) else None, 'outcome': notice.get('outcome') if isinstance(notice, dict) else None}
        if unreachable is not None:
            waiting.append(notice)
            if not quiet:
                e = dict(entry, why=f'not tried in this pass: the mailbox could not be reached ({unreachable})')
                (summary['coverage'] if coverage else summary['waiting']).append(dict(e, state=MADE) if coverage else e)
            continue
        try:
            receipt = deliver(cfg, watch, notice)
        except Answered as exc:                                     # refused: this notice waits, the next is tried
            waiting.append(notice)
            r = refusals.setdefault(C.notice_digest(notice), {'count': 0})
            r.update(count=int(_number(r.get('count'), 0)) + 1, why=str(exc), outcome=entry['outcome'], aid=entry['aid'], last=now())
            if not quiet:
                e = dict(entry, why=str(exc), refused=True)
                (summary['coverage'] if coverage else summary['waiting']).append(dict(e, state=MADE) if coverage else e)
            continue
        except Exception as exc:                                    # the mailbox could not be reached
            unreachable = str(exc) if isinstance(exc, Unreachable) else f'{type(exc).__name__}: {exc}'
            waiting.append(notice)
            if not quiet:
                e = dict(entry, why=unreachable)
                (summary['coverage'] if coverage else summary['waiting']).append(dict(e, state=MADE) if coverage else e)
            continue
        refusals.pop(C.notice_digest(notice), None)
        if C.notice_digest(notice) not in done:
            _append(pathlib.Path(cfg['state_dir']) / 'deliveries.jsonl', {'notice': notice, 'receipt': receipt}); done.add(C.notice_digest(notice))
        if coverage:
            if isinstance(st.get('watching'), dict) and st['watching'].get('notice') == C.notice_digest(notice):
                st['watching']['accepted'] = receipt.get('time')
            summary['coverage'].append({'root': root, 'seq': notice.get('seq'), 'state': ACCEPTED})
        else:
            summary['delivered'].append({'root': root, 'aid': notice['aid'], 'outcome': notice['outcome']})
    st['pending'] = waiting
    held = {C.notice_digest(n) for n in waiting}
    for d in [d for d in refusals if d not in held]:
        refusals.pop(d, None)
    save()
    return unreachable is not None


def _finite(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def state_problem(st, clock=None) -> str | None:
    """What is wrong with the shape of one budget's own state in the courier's state file, or None (Amendment 16, G9).  A
    time in it later than the courier's clock now (with 300 seconds allowed) is wrong too: it would put off a notice for ever."""
    late = lambda v: clock is not None and v > clock + 300
    if not isinstance(st, dict):
        return 'the budget\'s entry is not an object'
    shapes = {'unread': dict, 'suspect': dict, 'asked': dict, 'first_seen': dict, 'refusals': dict, 'sent': list, 'final': list, 'pending': list, 'attempts': list}
    for field, kind in shapes.items():
        if field in st and not isinstance(st[field], kind):
            return f'its field {field} is not a{"n object" if kind is dict else " list"}'
    for aid, u in (st.get('unread') or {}).items():
        if not isinstance(u, dict) or not _finite(u.get('since')) or ('last' in u and not _finite(u['last'])) or late(u['since']):
            return f'its field unread holds an entry for run {C.shown(aid, 80)} whose since or last is not a finite number, or is later than now'
    for aid, u in (st.get('suspect') or {}).items():
        if not isinstance(u, dict) or not all(_finite(u.get(k)) for k in ('since', 'last', 'times')) or ('clean' in u and not _finite(u['clean'])) or late(u['since']):
            return f'its field suspect holds an entry for run {C.shown(aid, 80)} whose since, last, times or clean is not a finite number, or whose since is later than now'
    for field in ('asked', 'first_seen'):
        for k, v in (st.get(field) or {}).items():
            if not _finite(v) or late(v):
                return f'its field {field} holds a value for {C.shown(k, 80)} that is not a finite number, or is later than now'
    if any(not isinstance(x, str) for x in st.get('sent') or []) or any(not isinstance(x, str) for x in st.get('final') or []):
        return 'its field sent or final holds something that is not text'
    if any(not isinstance(n, dict) for n in st.get('pending') or []):
        return 'its field pending holds something that is not a notice'
    if 'watching' in st and st['watching'] is not None and not (isinstance(st['watching'], dict) and isinstance(st['watching'].get('notice'), str)):
        return 'its field watching is not a statement the courier made'
    for field in ('seq', 'blocked_since'):
        if field in st and not _finite(st[field]):
            return f'its field {field} is not a finite number'
    return None


def one_pass(cfg, clock: float | None = None) -> dict:
    sd = pathlib.Path(cfg['state_dir']); sd.mkdir(parents=True, exist_ok=True)
    key = CourierKey(pathlib.Path(cfg['key_file']).read_text().strip())
    summary = {'made': [], 'delivered': [], 'waiting': [], 'refused': [], 'unreachable': [], 'unread': [], 'coverage': [], 'blocked': [], 'put_off': [], 'words': SUMMARY_WORDS}
    with open(sd / 'lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)                            # one pass at a time
        state = load_state(sd)
        save = lambda: _write_whole(sd / 'state.json', json.dumps(state, indent=1, sort_keys=True) + '\n')
        clock = time.time() if clock is None else clock
        for watch in cfg['watches']:
            st = state['roots'].setdefault(watch['root'], {})
            bad = state_problem(st, clock)
            if bad is not None:                                      # G9: the courier's own state, not the witness's word; not stopped
                summary['refused'].append({'root': watch['root'], 'why': f"the courier's own state for this budget (in {sd / 'state.json'}) is malformed: {bad}.  "
                                           'It is not read in this pass; restore the state, or move it aside to start again.'})
                continue
            try:
                watch_pass(cfg, key, watch, st, clock, summary, save)
            except Exception as exc:                                # one budget's trouble does not stop the others
                summary['unreachable'].append({'root': watch['root'], 'why': f'{type(exc).__name__}: {exc}'})
                save()
    return summary


def failed(summary) -> bool:
    """Whether a pass leaves anything to look at: a notice waiting, a budget refused or not read, a run not read, or the
    courier's statement that it watches a budget not accepted by the mailbox."""
    accepted = {c.get('root') for c in summary.get('coverage', []) if c.get('state') == ACCEPTED}
    return bool(summary['waiting'] or summary['refused'] or summary['unreachable'] or summary.get('unread') or summary.get('put_off')
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
        for k in ('stopped', 'seq', 'head', 'attempts', 'blocked_since', 'blocked_sent', 'final', 'first_seen', 'unread', 'suspect', 'asked', 'watching'):
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


def status(cfg) -> dict:
    """For each budget in the configuration (and only those): whether the courier's coverage of it is confirmed, whether the
    courier is blocked or stopped, the runs it cannot read, and its notices made and not yet accepted, and accepted."""
    sd = pathlib.Path(cfg['state_dir'])
    state = load_state(sd)
    out = {}
    for w in cfg['watches']:
        st = state['roots'].get(w['root'], {})
        log = read_deliveries(sd / 'deliveries.jsonl', w['root'])
        accepted = {C.notice_digest(d['notice']) for d in log}
        watching = st.get('watching') if isinstance(st.get('watching'), dict) else None
        if st.get('stopped'):
            coverage = f"NOT CONFIRMED (stopped since {st['stopped']}: the courier makes no notice of this budget's runs until it is resumed)"
        elif watching is None:
            coverage = 'NOT CONFIRMED (not yet read: the courier has not yet completed a pass that read this budget\'s chain to a checkpoint and asked the witness for its runs)'
        elif watching.get('notice') not in accepted:
            coverage = f"NOT CONFIRMED (statement made, not yet accepted by the mailbox: the courier's statement that it watches this budget from decision {watching.get('seq')})"
        else:
            coverage = f"CONFIRMED (the mailbox accepted the courier's statement that it watches this budget, a signed receipt; from decision {watching.get('seq')})"
        blocked = st.get('blocked_since')
        courier_is = (f"stopped since {st['stopped']}" if st.get('stopped') else
                      f"{BLOCKED} (since {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(blocked)) if isinstance(blocked, (int, float)) else blocked})" if blocked is not None else 'reading the witness')
        pending = [n for n in st.get('pending', []) if isinstance(n, dict)]
        out[w['root']] = {'coverage': coverage, 'courier': courier_is, 'read_to': st.get('seq', 0),
                          'unread': [{'aid': C.shown(aid, 200), 'since': u.get('since'), 'why': C.shown(u.get('why'), 300)} for aid, u in sorted((st.get('unread') or {}).items()) if isinstance(u, dict)],
                          'notices the mailbox refused': [{'outcome': C.shown(r.get('outcome'), 40), 'run': C.shown(r.get('aid'), 200), 'refusals': r.get('count'), 'last reason': C.shown(r.get('why'), 300)}
                                                          for d, r in sorted((st.get('refusals') or {}).items()) if isinstance(r, dict) and d in {C.notice_digest(n) for n in pending}],
                          'runs after which the witness stopped answering': [{'aid': C.shown(aid, 200), 'since': u.get('since'), 'times': u.get('times')}
                                                                            for aid, u in sorted((st.get('suspect') or {}).items()) if isinstance(u, dict)],
                          'notices ' + MADE: sum(n.get('outcome') != C.WATCHING for n in pending),
                          'notices ' + ACCEPTED: sum(d['notice'].get('outcome') != C.WATCHING for d in log),
                          'sent': len(st.get('sent', [])), 'waiting': len(pending), 'delivered': len(log), 'stopped': st.get('stopped')}
    return {'budgets': out, 'note': STATUS_NOTE}


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
        s = one_pass(cfg)
        print(json.dumps(s), flush=True)
        if a.every is None:
            sys.exit(1 if failed(s) else 0)
        time.sleep(max(1.0, a.every))


if __name__ == '__main__':
    main()
