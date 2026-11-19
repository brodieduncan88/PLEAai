#!/usr/bin/env python3
"""The courier: notices to the responsible engineer that the verification service does not write (Amendment 11).

    courier.py keygen KEYFILE                    write a new courier key; print its public half
    courier.py run --config CONFIG [--every S]   one pass over every budget watched (or a pass every S seconds)
    courier.py status --config CONFIG            what has been sent, delivered and is waiting
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
certificate.  It is delivered when the mailbox answers with a receipt signed by a mailbox key given, naming the notice.  The
notice and its receipt are then appended to STATE_DIR/deliveries.jsonl, and a record can carry them (verify_ctl.py record
--deliveries).  A notice not delivered stays waiting and is sent again at the next pass, and what is waiting is sent before
the witness is asked.  A run the witness will not answer for is passed over, keeping its wait, and asked after again at the
next pass; if the witness does not answer at all, the pass asks no more.  Each request has 60 seconds, however slowly a
party answers.  A pass exits 0 if nothing is waiting, refused or unreachable, and 1 otherwise.

What the courier refuses.  A checkpoint that is not the witness's, does not sign back its nonce, or names another decision
than asked; another head for the last decision the courier read (a fork); decisions that are not readable, do not follow
on, or do not hash to the checkpoint's head; an answer saying that the courier's last decision is beyond the chain (a
rollback).  It stops for that budget, writes what it was told to STATE_DIR/refused.jsonl, and sends the engineer's mailbox a
signed notice that it has stopped (COURIER_STOPPED).  It sends nothing more on that budget until `resume`.  If it cannot read
the witness for `stall_after` seconds, it sends one notice that it is blocked (COURIER_BLOCKED).  Neither is a notice of a
run, and neither goes into a record.

What it trusts, and what it cannot do.  It sees what the witness records, so a run that never reached the witness is not
seen, and a witness that tells it one consistent false chain is believed.  The witness reads the same database as the
service: the chain is written only through the witness's role, and a stored result is the service's, believed only when
it hashes to the gate's signed digest.  In the demonstration one certificate authority issues every certificate, and the
witness's allow list is set by whoever runs the witness: they can cut the courier off, which it then reports as blocked if
the mailbox is still reachable.  A receipt says the mailbox holds a notice, not that the engineer read it.  The courier is
as independent of the service as the account and machine it runs on: in the demonstration that is the same machine as
everything else.  It needs the Python standard library and `cryptography` (through check_record.py).
"""
import argparse
import fcntl
import http.client
import json
import os
import pathlib
import secrets
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


def https(method: str, url: str, cfg: dict, body=None, timeout: float = 15.0):
    """(status, answer) from a party, over HTTPS with the courier's client certificate; the answer is a JSON object.  The
    whole request has DEADLINE seconds.  Raises Unreachable."""
    box = {}
    def ask():
        try:
            box['answer'] = _https(method, url, cfg, body, timeout)
        except BaseException as exc:
            box['error'] = exc
    worker = threading.Thread(target=ask, daemon=True); worker.start(); worker.join(DEADLINE)
    if worker.is_alive():
        raise Unreachable(f'{urllib.parse.urlsplit(url).netloc} did not answer within {int(DEADLINE)} seconds')
    if 'error' in box:
        raise box['error']
    return box['answer']


def _https(method: str, url: str, cfg: dict, body=None, timeout: float = 15.0):
    if urllib.parse.urlsplit(url).scheme != 'https':
        raise Unreachable('a party is asked over https only')
    req = urllib.request.Request(url, method=method, data=None if body is None else json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_context(cfg['ca'], cfg['cert'], cfg['key'])) as r:
            raw, status = r.read(MAX_ANSWER + 1), r.status
    except urllib.error.HTTPError as exc:
        try:
            ans = json.loads(exc.read(65536))
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
    aid, req = (attempt[0], attempt[1]) if attempt else ('', None)
    r = result if isinstance(result, dict) else {}
    detail = C.notice_detail(result)
    if attempt:
        text = C.notice_text(outcome, aid, root, result, seq, cfg['name'])
    else:
        text = (f"{C.HEADLINES[outcome]}\nBudget {root}.\n{why_alarm or ''}\n"
                f"This notice was made by the courier {cfg['name']}.  Until this is looked into, no notice of this budget's runs will come from the courier.")
    body = {'statement': 'NOTICE', 'root': root, 'aid': aid, 'request_key': req, 'outcome': outcome, 'reason_code': r.get('reason_code'),
            'detail': detail, 'result_digest': C.sha(C.canonical(result)) if isinstance(result, dict) else None,
            'seq': seq, 'head': head, 'time': now(), 'courier': cfg['name'], 'text': text}
    return dict(body, signer=key.public_hex, signature=key.sign(C.canonical({k: body[k] for k in C.NOTICE_FIELDS}).encode()))


def deliver(cfg, watch, notice) -> dict:
    status, receipt = https('POST', f"{watch['mailbox_url']}/deliver", cfg, notice)
    if status != 200:
        raise Unreachable(f'the mailbox answered {status}: {receipt.get("error")}')
    bad = C.receipt_problems(receipt, watch['mailbox_keys'], notice)
    if bad:
        raise Unreachable('the mailbox\'s answer is not a receipt for this notice: ' + '; '.join(bad))
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


def read_witness(cfg, key, watch, st: dict, clock: float, summary: dict, save) -> None:
    root = watch['root']
    cp = checkpoint(cfg, root, st.get('seq', 0))
    if st.get('seq', 0) and cp['head_at'] != st['head']:
        raise Refused(f"FORK: the witness says another head for decision {st['seq']} than the one the courier read", cp)
    last = chain(cfg, root, st.get('seq', 0), cp['head_at'] if not st.get('seq') else st['head'], cp)
    if last is not None:
        st['attempts'] = [list(x[:4]) for x in last['observation'].get('attempts', []) if isinstance(x, list) and len(x) >= 4]
    st['seq'], st['head'] = cp['seq'], cp['head']
    sent, final, before = st.setdefault('sent', []), st.setdefault('final', []), st.get('first_seen', {})
    seen, failed = {}, []                                            # a wait counts only while the run is seen in that state, pass after pass
    for attempt in st.get('attempts', []):
        aid, phase = attempt[0], attempt[2]
        if aid in final or phase not in READ:
            continue
        try:                                                        # one run the witness will not answer for does not hide the others
            outcome, result = run_outcome(cfg, root, attempt, cp['seq'])
        except Unreachable as exc:
            seen.update({k: v for k, v in before.items() if k.startswith(f'{aid}|')})   # its waits go on, though it was not read this time
            failed.append(f'{aid}: {exc}')
            if isinstance(exc, Answered):
                continue
            for later in st.get('attempts', [])[st['attempts'].index(attempt) + 1:]:      # the witness itself is not answering: ask no more, keep every wait
                seen.update({k: v for k, v in before.items() if k.startswith(f'{later[0]}|')})
            break
        done = phase in FINAL and outcome != 'UNVERIFIED'
        if outcome in ('PASS', 'PENDING'):
            if done:
                final.append(aid)
            continue
        waited = None
        if outcome in WAIT:                                          # what may yet change: no outcome yet, or a result not yet stored
            mark = f'{aid}|{outcome}|{phase}'
            seen[mark] = before.get(mark, clock); waited = clock - seen[mark]
            if waited < float(cfg.get('stall_after', 900)):
                continue
            result = None                                          # the courier vouches for no result it could not match
        if f'{aid}|{outcome}' not in sent:
            st.setdefault('pending', []).append(make_notice(cfg, key, root, attempt, outcome, result, cp['seq'], cp['head'], waited))
            sent.append(f'{aid}|{outcome}'); summary['made'].append({'root': root, 'aid': aid, 'outcome': outcome})
        if done:
            final.append(aid)                                      # final only once its notice is made
        save()                                                     # a notice made is kept before anything else
    st['first_seen'] = seen
    if failed:
        raise Unreachable(f'{len(failed)} runs could not be read: ' + '; '.join(failed[:3]))


def watch_pass(cfg, key, watch, st: dict, clock: float, summary: dict, save) -> None:
    root = watch['root']
    if st.get('pending'):
        _deliver_pending(cfg, watch, st, summary, save, quiet=True)   # what is waiting goes out before the witness is asked, however long that takes
    if st.get('stopped'):
        summary['refused'].append({'root': root, 'why': 'stopped since ' + st['stopped'] + ': see refused.jsonl, then courier.py resume'})
    else:
        try:
            read_witness(cfg, key, watch, st, clock, summary, save)
            st.pop('blocked_since', None); st.pop('blocked_sent', None)
        except Refused as exc:
            st['stopped'] = now()
            _append(pathlib.Path(cfg['state_dir']) / 'refused.jsonl', {'time': now(), 'root': root, 'why': str(exc.args[0]), 'evidence': exc.args[1] if len(exc.args) > 1 else None})
            summary['refused'].append({'root': root, 'why': str(exc.args[0])})
            alarm(cfg, key, watch, st, 'COURIER_STOPPED', f'The courier refused what the witness said: {exc.args[0]}', summary)
        except (Unreachable, KeyError, TypeError, AttributeError, IndexError) as exc:
            if not isinstance(exc, Unreachable):                    # an answer the courier could not even read is not believed
                st['stopped'] = now()
                why = f'an answer of the witness could not be read ({type(exc).__name__}: {exc})'
                _append(pathlib.Path(cfg['state_dir']) / 'refused.jsonl', {'time': now(), 'root': root, 'why': why, 'evidence': None})
                summary['refused'].append({'root': root, 'why': why})
                alarm(cfg, key, watch, st, 'COURIER_STOPPED', f'The courier refused what the witness said: {why}', summary)
                save(); return _deliver_pending(cfg, watch, st, summary, save)
            since = st.setdefault('blocked_since', clock)
            summary['unreachable'].append({'root': root, 'why': str(exc)})
            if clock - since >= float(cfg.get('stall_after', 900)) and not st.get('blocked_sent'):
                st['blocked_sent'] = True
                alarm(cfg, key, watch, st, 'COURIER_BLOCKED', f'For {int(clock - since)} seconds the courier has not been able to read the witness: {exc}', summary)
        save()
    _deliver_pending(cfg, watch, st, summary, save)


def _deliver_pending(cfg, watch, st, summary, save, quiet: bool = False) -> None:
    root = watch['root']
    done = delivered_digests(pathlib.Path(cfg['state_dir']))
    waiting = []
    for notice in st.get('pending', []):
        try:
            receipt = deliver(cfg, watch, notice)
        except Unreachable as exc:
            waiting.append(notice)
            if not quiet:
                summary['waiting'].append({'root': root, 'aid': notice['aid'], 'outcome': notice['outcome'], 'why': str(exc)})
            continue
        if C.notice_digest(notice) not in done:
            _append(pathlib.Path(cfg['state_dir']) / 'deliveries.jsonl', {'notice': notice, 'receipt': receipt}); done.add(C.notice_digest(notice))
        summary['delivered'].append({'root': root, 'aid': notice['aid'], 'outcome': notice['outcome']})
    st['pending'] = waiting
    save()


def one_pass(cfg, clock: float | None = None) -> dict:
    sd = pathlib.Path(cfg['state_dir']); sd.mkdir(parents=True, exist_ok=True)
    key = CourierKey(pathlib.Path(cfg['key_file']).read_text().strip())
    summary = {'made': [], 'delivered': [], 'waiting': [], 'refused': [], 'unreachable': []}
    with open(sd / 'lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)                            # one pass at a time
        state = load_state(sd)
        save = lambda: _write_whole(sd / 'state.json', json.dumps(state, indent=1, sort_keys=True) + '\n')
        clock = time.time() if clock is None else clock
        for watch in cfg['watches']:
            st = state['roots'].setdefault(watch['root'], {})
            try:
                watch_pass(cfg, key, watch, st, clock, summary, save)
            except Exception as exc:                                # one budget's trouble does not stop the others
                summary['unreachable'].append({'root': watch['root'], 'why': f'{type(exc).__name__}: {exc}'})
                save()
    return summary


def resume(cfg, root) -> dict:
    """After the engineer has looked into a refusal: read the budget again from its first decision.  Notices already sent are
    not sent again."""
    sd = pathlib.Path(cfg['state_dir'])
    with open(sd / 'lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = load_state(sd); st = state['roots'].get(root)
        if st is None:
            raise ValueError(f'the courier holds nothing for {root}')
        for k in ('stopped', 'seq', 'head', 'attempts', 'blocked_since', 'blocked_sent', 'final', 'first_seen'):
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


def status(cfg) -> dict:
    sd = pathlib.Path(cfg['state_dir'])
    state = load_state(sd)
    out = {}
    for w in cfg['watches']:
        st = state['roots'].get(w['root'], {})
        out[w['root']] = {'read_to': st.get('seq', 0), 'sent': len(st.get('sent', [])), 'waiting': len(st.get('pending', [])),
                          'delivered': len(read_deliveries(sd / 'deliveries.jsonl', w['root'])), 'stopped': st.get('stopped')}
    return out


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
            sys.exit(0 if not (s['waiting'] or s['refused'] or s['unreachable']) else 1)
        time.sleep(max(1.0, a.every))


if __name__ == '__main__':
    main()
