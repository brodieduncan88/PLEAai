#!/usr/bin/env python3
"""The courier: notices to the responsible engineer that the verification service does not write (Amendment 11).

    courier.py keygen KEYFILE                    write a new courier key; print its public half
    courier.py run --config CONFIG [--every S]   one pass over every budget watched (or a pass every S seconds)
    courier.py status --config CONFIG            what has been sent, delivered and is waiting

CONFIG is a JSON file the engineer writes:

    {"name": "courier-1", "key_file": "...", "state_dir": "...", "stall_after": 900,
     "witness_url": "https://...", "ca": "...", "cert": "...", "key": "...",
     "witness_keys": [HEX], "gate_keys": [HEX],
     "watches": [{"root": R, "mailbox_url": "https://...", "mailbox_keys": [HEX]}]}

Where a notice comes from.  The service writes its own notice of a failing run into an inbox it controls (verify_tools.py),
and whoever can write that inbox can remove or change it; a run the service cannot finish, or cannot write a notice for,
gets none.  The courier does not read the service: not its store, its inbox, its ledger or its files.  It holds no
credential of the service's.  It reads only the witness, as a client admitted to the witness's readings and nothing else
(--tls-allow-read), and it believes the witness only as far as it can check:

  - it asks for a checkpoint with a nonce of its own, signed by a witness key given, naming the last decision it read
    before and that decision's head (Amendment 10);
  - it reads the decisions since (GET /chain) and recomputes each hash: they must follow on from what it read before and
    end at the checkpoint's head;
  - for each run, it reads the gate's reports and the stored result (GET /run): a report counts only if a gate key given
    signed it for this budget, run and nonce, and a result only if it hashes to the digest the gate signed.

A run calls for a notice when the chain, the reports and the result say FAIL, UNKNOWN or INTERRUPTED; INVALID or
REFUNDED, which must never happen; UNVERIFIED, a run the gate signed an effect for with no stored result that hashes to the
digest the gate signed; or NO_OUTCOME, a run admitted and crossed with no outcome.  The last two are sent only once the
courier has seen them so for `stall_after` seconds (900 unless set) by its own clock, since the witness records an outcome
a moment before the result is stored.  An UNVERIFIED notice vouches for no result.  A run that
met the declared check calls for none.  Each notice, for one run and one outcome, is made once and signed with the
courier's key.  It names the decision it was read at and that decision's hash, so a reader can tie it to a record.

Delivery.  Each notice is sent to the watch's mailbox (mailbox_service.py) over HTTPS with the courier's client certificate.  It is
delivered when the mailbox answers with a receipt signed by a mailbox key given, naming the notice.  The notice and its
receipt are then appended to STATE_DIR/deliveries.jsonl, and a record can carry them (verify_ctl.py record --deliveries).
A notice not delivered stays waiting and is sent again at the next pass.  A pass exits 0 if nothing is waiting and nothing
was refused, and 1 otherwise.

What the courier refuses.  A checkpoint that is not the witness's, does not sign back its nonce, or says another head for
the last decision the courier read (a fork); decisions that do not hash to the checkpoint's head; an answer saying that
the courier's last decision is beyond the chain (a rollback).  It stops for that budget, writes what it was told to
STATE_DIR/refused.jsonl, and sends nothing on it until the engineer has looked.

What it cannot do.  It sees what the witness records, so a run that never reached the witness is not seen.  A witness that
tells it one consistent false chain is believed.  It does not show that the engineer read a notice; a receipt says the
mailbox holds it.  It is as independent of the service as the account and machine it runs on: in the demonstration that is
the same machine as everything else.  It needs the Python standard library and `cryptography` (through check_record.py).
"""
import argparse
import fcntl
import json
import os
import pathlib
import secrets
import ssl
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_record as C                                                  # noqa: E402
from mailbox_service import MailboxKey as CourierKey                     # noqa: E402  (the same kind of Ed25519 key)

MAX_ANSWER = 8 * 1024 * 1024
PAGE = 200
FINAL = ('EFFECT', 'NO_EFFECT')                                          # phases a run does not leave
HEADLINES = {'FAIL': 'DECLARED CHECK NOT MET (FAIL)', 'UNKNOWN': 'NO VERDICT: THE CHECK DID NOT DECIDE (UNKNOWN)',
             'INTERRUPTED': 'THE RUN WAS INTERRUPTED: ADMITTED AND COUNTED, WITH NO VERDICT', 'INVALID': 'THE GATE SIGNED A RESULT THAT HAS NO VERDICT',
             'REFUNDED': 'THE RUN WAS REFUNDED, WHICH A VERIFICATION RUN MUST NEVER BE', 'UNVERIFIED': 'THE STORED RESULT DOES NOT MATCH THE GATE\'S SIGNATURE',
             'NO_OUTCOME': 'A RUN WAS ADMITTED AND HAS NO OUTCOME'}


class Refused(Exception):
    """What the witness said cannot be believed, or it contradicts what the courier read before."""


class Unreachable(Exception):
    """A party could not be asked, or did not answer as it must."""


def now() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def _context(ca, cert, key) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT); ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.check_hostname = True; ctx.verify_mode = ssl.CERT_REQUIRED; ctx.load_verify_locations(cafile=ca)
    ctx.load_cert_chain(cert, key)
    return ctx


def https(method: str, url: str, cfg: dict, body=None, timeout: float = 15.0):
    """(status, answer) from a party, over HTTPS with the courier's client certificate.  Raises Unreachable."""
    if urllib.parse.urlsplit(url).scheme != 'https':
        raise Unreachable('a party is asked over https only')
    req = urllib.request.Request(url, method=method, data=None if body is None else json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_context(cfg['ca'], cfg['cert'], cfg['key'])) as r:
            raw, status = r.read(MAX_ANSWER + 1), r.status
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read(65536))
        except Exception:
            return exc.code, {}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise Unreachable(f'{urllib.parse.urlsplit(url).netloc} could not be asked ({type(exc).__name__})')
    if len(raw) > MAX_ANSWER:
        raise Unreachable('the answer is too long')
    try:
        return status, json.loads(raw)
    except ValueError:
        raise Unreachable('the answer is not JSON')


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
        if not isinstance(row, dict) or row.get('seq') != n + 1:
            raise Refused(f'the witness gave decision {row.get("seq") if isinstance(row, dict) else row!r} where {n + 1} was due')
        if row.get('prev_hash') != prev or C.chain_hash(prev, row) != row.get('hash'):
            raise Refused(f'decision {n + 1} does not follow on from the one before it, or does not hash to itself')
        out.append(row); prev, n = row['hash'], n + 1
        if n == upto:
            break
    if n != upto or prev != head:
        raise Refused(f'the decisions read do not end at the checkpoint\'s head after decision {upto}')
    return out


def chain(cfg, root, after: int, prev: str, cp) -> list:
    rows = []
    while after + len(rows) < cp['seq']:
        status, page = https('GET', f"{cfg['witness_url']}/chain?" + q(root=root, after=after + len(rows), limit=PAGE), cfg)
        if status != 200 or not isinstance(page.get('rows'), list) or not page['rows']:
            raise Unreachable(f'the witness answered {status} to the chain, with no decisions')
        rows += [r for r in page['rows'] if isinstance(r, dict) and isinstance(r.get('seq'), int) and r['seq'] <= cp['seq']]
        if page['rows'][-1].get('seq', 0) >= cp['seq']:
            break
    return verify_rows(rows, after, prev, cp['seq'], cp['head'])


def run_outcome(cfg, root, attempt, upto: int) -> tuple[str, dict | None]:
    """(outcome, result) of one run, from the witness's reports and stored result, believed only as far as they check."""
    aid, _req, phase, nonce = attempt[:4]
    status, ans = https('GET', f"{cfg['witness_url']}/run?" + q(root=root, aid=aid), cfg)
    if status != 200:
        raise Unreachable(f'the witness answered {status} for run {aid}')
    evidence = [e for e in ans.get('evidence') or [] if isinstance(e, dict) and isinstance(e.get('seq'), int) and e['seq'] <= upto]
    stored = ans.get('result')
    result = stored.get('value') if phase == 'EFFECT' and isinstance(stored, dict) and stored.get('outcome', 'value') == 'value' else None
    return C.run_outcome(phase, evidence, result, cfg['gate_keys'], root, aid, nonce), result


# ---------------------------------------------------------------------------------------------------- notices
def make_notice(cfg, key: CourierKey, root, attempt, outcome, result, cp, waited=None) -> dict:
    aid, req = attempt[0], attempt[1]
    r = result if isinstance(result, dict) else {}
    detail = ''.join(ch if ch >= ' ' and ch != '\x7f' else ' ' for ch in str(r.get('detail') or ''))[:400]
    numbers = '; '.join(f"{c.get('id')} achieved {c.get('achieved')}, required {({'<=': 'at most', '>=': 'at least'}).get(c.get('comparison'), c.get('comparison'))} {c.get('limit')} {c.get('units') or ''}".strip()
                        for c in r.get('criteria') or [] if isinstance(c, dict) and c.get('achieved') is not None)
    why = (f"Reason: {r.get('reason_code')}.  " + (f'{numbers}.  ' if numbers else '') + detail if r.get('reason_code') else
           {'INTERRUPTED': 'The gate signed that it does not know the outcome: the run is counted and will not be run again.',
            'NO_OUTCOME': f'It was admitted and crossed, and the courier has seen it with no outcome for {int(waited or 0)} seconds.',
            'UNVERIFIED': f'The gate signed that the check ran, but for {int(waited or 0)} seconds the courier has found no stored result that hashes to the digest the gate signed.',
            'REFUNDED': 'The witness recorded the run as refunded.'}.get(outcome, ''))
    text = (f"{HEADLINES[outcome]}\nRun {aid} on budget {root}.\n{why}\n"
            f"This notice was made by the courier {cfg['name']} from the witness's chain at decision {cp['seq']} and the gate's signed reports.  "
            'The verification service did not write it.  It does not say the check is correct.')
    body = {'statement': 'NOTICE', 'root': root, 'aid': aid, 'request_key': req, 'outcome': outcome, 'reason_code': r.get('reason_code'),
            'detail': detail or None, 'result_digest': C.sha(C.canonical(result)) if isinstance(result, dict) else None,
            'seq': cp['seq'], 'head': cp['head'], 'time': now(), 'courier': cfg['name'], 'text': text}
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
def _write_whole(path: pathlib.Path, data: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.tmp-')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        pathlib.Path(tmp).unlink(missing_ok=True); raise


def _append(path: pathlib.Path, obj) -> None:
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(obj, sort_keys=True) + '\n'); f.flush(); os.fsync(f.fileno())


def delivered_digests(state_dir: pathlib.Path) -> set:
    p, out = state_dir / 'deliveries.jsonl', set()
    if p.exists():
        for line in p.read_text(encoding='utf-8').splitlines():
            try:
                out.add(C.notice_digest(json.loads(line)['notice']))
            except (ValueError, KeyError, TypeError):
                continue
    return out


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


# ---------------------------------------------------------------------------------------------------- one pass
def watch_pass(cfg, key, watch, st: dict, clock: float, summary: dict, save) -> None:
    root = watch['root']
    if st.get('stopped'):
        summary['refused'].append({'root': root, 'why': 'stopped since ' + st['stopped']}); return
    try:
        cp = checkpoint(cfg, root, st.get('seq', 0))
        if st.get('seq', 0) and cp['head_at'] != st['head']:
            raise Refused(f"FORK: the witness says another head for decision {st['seq']} than the one the courier read", cp)
        rows = chain(cfg, root, st.get('seq', 0), cp['head_at'] if not st.get('seq') else st['head'], cp)
    except Refused as exc:
        st['stopped'] = now()
        _append(pathlib.Path(cfg['state_dir']) / 'refused.jsonl', {'time': now(), 'root': root, 'why': str(exc.args[0]), 'evidence': exc.args[1] if len(exc.args) > 1 else None})
        summary['refused'].append({'root': root, 'why': str(exc.args[0])}); save(); return
    if rows:
        st['attempts'] = [x[:4] for x in rows[-1]['observation'].get('attempts', [])]
    st['seq'], st['head'] = cp['seq'], cp['head']
    sent, final, seen = st.setdefault('sent', []), st.setdefault('final', []), st.setdefault('first_seen', {})
    for attempt in st.get('attempts', []):
        aid, phase = attempt[0], attempt[2]
        if aid in final or phase not in ('EFFECT', 'NO_EFFECT', 'CONSUMED'):
            continue
        outcome, result = run_outcome(cfg, root, attempt, cp['seq'])
        if phase in FINAL and outcome != 'UNVERIFIED' and aid not in final:
            final.append(aid)
        if outcome == 'PASS':
            continue
        waited = None
        if outcome in ('NO_OUTCOME', 'UNVERIFIED'):              # what may yet change: no outcome yet, or a result not yet stored
            waited = clock - seen.setdefault(f'{aid}|{outcome}', clock)
            if waited < float(cfg.get('stall_after', 900)):
                continue
            result = None                                          # the courier vouches for no result it could not match
        if f'{aid}|{outcome}' in sent:
            continue
        st.setdefault('pending', []).append(make_notice(cfg, key, root, attempt, outcome, result, cp, waited))
        sent.append(f'{aid}|{outcome}'); summary['made'].append({'root': root, 'aid': aid, 'outcome': outcome})
    save()                                                         # a notice made is kept before it is sent
    done = delivered_digests(pathlib.Path(cfg['state_dir']))
    waiting = []
    for notice in st.get('pending', []):
        try:
            receipt = deliver(cfg, watch, notice)
        except Unreachable as exc:
            waiting.append(notice); summary['waiting'].append({'root': root, 'aid': notice['aid'], 'outcome': notice['outcome'], 'why': str(exc)}); continue
        if C.notice_digest(notice) not in done:
            _append(pathlib.Path(cfg['state_dir']) / 'deliveries.jsonl', {'notice': notice, 'receipt': receipt})
        summary['delivered'].append({'root': root, 'aid': notice['aid'], 'outcome': notice['outcome']})
    st['pending'] = waiting
    save()


def one_pass(cfg) -> dict:
    sd = pathlib.Path(cfg['state_dir']); sd.mkdir(parents=True, exist_ok=True)
    key = CourierKey(pathlib.Path(cfg['key_file']).read_text().strip())
    summary = {'made': [], 'delivered': [], 'waiting': [], 'refused': [], 'unreachable': []}
    with open(sd / 'lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)                            # one pass at a time
        sp = sd / 'state.json'
        state = json.loads(sp.read_text()) if sp.exists() else {'roots': {}}
        save = lambda: _write_whole(sp, json.dumps(state, indent=1, sort_keys=True) + '\n')
        clock = time.time()
        for watch in cfg['watches']:
            st = state['roots'].setdefault(watch['root'], {})
            try:
                watch_pass(cfg, key, watch, st, clock, summary, save)
            except Unreachable as exc:
                summary['unreachable'].append({'root': watch['root'], 'why': str(exc)})
                save()
    return summary


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
    state = json.loads((sd / 'state.json').read_text()) if (sd / 'state.json').exists() else {'roots': {}}
    out = {}
    for w in cfg['watches']:
        st = state['roots'].get(w['root'], {})
        out[w['root']] = {'read_to': st.get('seq', 0), 'sent': len(st.get('sent', [])), 'waiting': len(st.get('pending', [])),
                          'delivered': len(read_deliveries(sd / 'deliveries.jsonl', w['root'])), 'stopped': st.get('stopped')}
    return out


def main():
    ap = argparse.ArgumentParser(description='The courier: notices the verification service does not write (Amendment 11).')
    ap.add_argument('action', choices=['keygen', 'run', 'status']); ap.add_argument('path', nargs='?')
    ap.add_argument('--config'); ap.add_argument('--every', type=float)
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
    while True:
        s = one_pass(cfg)
        print(json.dumps(s), flush=True)
        if a.every is None:
            sys.exit(0 if not (s['waiting'] or s['refused'] or s['unreachable']) else 1)
        time.sleep(max(1.0, a.every))


if __name__ == '__main__':
    main()
