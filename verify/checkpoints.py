#!/usr/bin/env python3
"""The witness's checkpoints, kept by someone other than the service (Amendment 10).

    checkpoints.py fetch --witness-url URL --ca CA --cert CERT --key KEY --root ROOT [--nonce N] [--at K] [--out FILE] [--log LOG --witness-key HEX ...]
    checkpoints.py audit LOG --witness-key HEX [--witness-key HEX ...]

A checkpoint is the witness's signed statement of one budget's chain as it reads it at that moment: how many decisions
are recorded (seq), the hash of the last (head), the budget's two states, and its clock (witness_service.py, GET
/checkpoint).  A record says only what was so at its own sequence number, so an older record omits later runs and still
verifies.  A checkpoint obtained separately from the record says whether it is the latest: check_record.py --checkpoint.

`fetch` asks the witness over mutual TLS and writes what it signed.  Unless --nonce is given it makes a nonce of its own,
which the witness must sign back, so a checkpoint made earlier cannot be handed over in its place.  The answer must be
for the budget asked.

With --log it also appends the checkpoint to a log.  It asks the witness what the chain's head was at the last sequence
number the log holds for that budget (unless --at is given), so each checkpoint kept is tied to the one before it.  The
checkpoint is kept only if it is the witness's (under one of the keys given: give the old and the new during a key
rotation) and does not contradict what the log holds:

  ROLLBACK   its sequence number is lower than one already kept for the budget;
  FORK       it gives another head for a sequence number the log already knows, as the chain's head or as the head after
             an earlier decision (at, head_at).

A checkpoint that contradicts the log is the evidence that the witness said two things.  It is not appended to the log,
but it is written to LOG.refused.jsonl beside it, and the command exits 1 saying which rule it broke.  A witness that
answers that the log's last sequence number is beyond its chain has rolled the chain back: the command says so.
`audit` re-reads a whole log by the same rules and checks every signature.

What the log can and cannot show.  Kept as above, it shows a change to any decision at or before a sequence number it
holds.  It does not show what the witness told others in between two of its own askings, nor a witness that tells
everyone the same false thing.  The log is one writer's: a second keeper waits for the first (a file lock), and a
checkpoint that arrives after a later one is refused as a rollback, so keep them in the order they were fetched.  A last
line cut off by a crash is passed over and reported by `audit`.  The log is as independent as the machine and account
it is kept on: in the demonstration that is the same machine as everything else.  The time in a checkpoint is the
witness's clock, not a third party's.  This file needs the Python standard library and `cryptography` (through
check_record.py), and nothing from the gateway.
"""
import argparse
import fcntl
import json
import os
import pathlib
import re
import secrets
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from check_record import _keys, checkpoint_problems     # noqa: E402

NONCE = re.compile(r'[A-Za-z0-9_-]{1,64}')
MAX_ANSWER = 65536


class CheckpointRefused(ValueError):
    """The witness did not give a checkpoint, or the checkpoint contradicts what is already held."""


def fetch(witness_url: str, ca: str, cert: str | None, key: str | None, root: str, nonce: str | None = None, at: int | None = None, timeout: float = 15.0) -> dict:
    """Ask the witness for a checkpoint of `root`, over TLS with the authority `ca`.  The answer is returned as given, except
    that it must be a JSON object: verify it before use (checkpoint_problems, or keep)."""
    if nonce is not None and not (isinstance(nonce, str) and NONCE.fullmatch(nonce)):
        raise CheckpointRefused('a nonce is 1 to 64 characters of A-Z a-z 0-9 _ -')
    parts = urllib.parse.urlsplit(witness_url)
    if parts.scheme != 'https' or not ca:
        raise CheckpointRefused('the witness is asked over https, with the authority that issued its certificate (--ca)')
    q = {'root': root}
    if nonce is not None:
        q['nonce'] = nonce
    if at is not None:
        q['at'] = str(int(at))
    url = f'https://{parts.netloc}/checkpoint?' + urllib.parse.urlencode(q)
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT); ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.check_hostname = True; ctx.verify_mode = ssl.CERT_REQUIRED; ctx.load_verify_locations(cafile=ca)
        if cert:
            ctx.load_cert_chain(cert, key)
        with urllib.request.urlopen(url, timeout=timeout, context=ctx) as r:
            raw = r.read(MAX_ANSWER + 1)
        if len(raw) > MAX_ANSWER:
            raise CheckpointRefused('the witness\'s answer is too long to be a checkpoint')
        cp = json.loads(raw)
    except urllib.error.HTTPError as exc:
        try:
            why = json.loads(exc.read(MAX_ANSWER)).get('error')
        except Exception:
            why = None
        raise CheckpointRefused(f'the witness answered {exc.code}' + (f': {why}' if why else ''))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        if isinstance(exc, CheckpointRefused):
            raise
        raise CheckpointRefused(f'the witness could not be asked ({type(exc).__name__})')
    if not isinstance(cp, dict):
        raise CheckpointRefused('the witness\'s answer is not a checkpoint')
    return cp


def read_log(path) -> tuple[list, bool]:
    """(the checkpoints in a log, whether its last line was cut off).  A line that is not a checkpoint, other than a last
    line with no end, is refused."""
    p = pathlib.Path(path)
    if not p.exists():
        return [], False
    text = p.read_text(encoding='utf-8'); lines = text.split('\n'); torn = False
    if lines and lines[-1] == '':
        lines.pop()
    out = []
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            cp = json.loads(line)
            if not isinstance(cp, dict):
                raise ValueError
            out.append(cp)
        except ValueError:
            if n == len(lines) and not text.endswith('\n'):
                torn = True; continue
            raise CheckpointRefused(f'line {n} of the log is not a checkpoint')
    return out, torn


def _heads(cp: dict) -> list:
    """The (sequence number, head) pairs a checkpoint states."""
    out = [(cp['seq'], cp['head'])]
    if cp.get('at') is not None:
        out.append((cp['at'], cp['head_at']))
    return out


def last_seq(held: list, root: str):
    """The highest sequence number kept for a budget, or None."""
    mine = [h['seq'] for h in held if isinstance(h, dict) and h.get('root') == root and type(h.get('seq')) is int]
    return max(mine) if mine else None


def contradiction(known: dict, top, cp: dict):
    """None, or how `cp` contradicts what is held for its budget: `known` maps a sequence number to its head, `top` is the
    highest sequence number kept."""
    if top is not None and cp['seq'] < top:
        return f"ROLLBACK: sequence number {cp['seq']} after {top} for {cp['root']}"
    for seq, head in _heads(cp):
        if seq in known and known[seq] != head:
            return f'FORK: two heads for sequence number {seq} of {cp["root"]}'
    return None


def audit(checkpoints: list, witness_keys) -> list:
    """Every problem in a log, read in order: a signature that does not verify, a rollback, a fork."""
    out, known, top = [], {}, {}
    for n, cp in enumerate(checkpoints, 1):
        bad = checkpoint_problems(cp, _keys(witness_keys), cp.get('root') if isinstance(cp, dict) else None)
        if bad:
            out.append(f'line {n}: ' + '; '.join(bad)); continue
        root = cp['root']; mine = known.setdefault(root, {})
        why = contradiction(mine, top.get(root), cp)
        if why:
            out.append(f'line {n}: {why}')
        for seq, head in _heads(cp):
            mine.setdefault(seq, head)
        top[root] = max(top.get(root, -1), cp['seq'])
    return out


def keep(log, cp: dict, witness_keys, root: str | None = None, nonce: str | None = None) -> None:
    """Append a checkpoint to a log, unless it is not the witness's, is not for `root` or does not sign back `nonce` (where
    given), or contradicts what the log holds.  A checkpoint that contradicts the log is written to LOG.refused.jsonl.
    Raises CheckpointRefused."""
    bad = checkpoint_problems(cp, _keys(witness_keys), root if root is not None else (cp.get('root') if isinstance(cp, dict) else None))
    if not bad and nonce is not None and cp.get('nonce') != nonce:
        bad = ['it does not sign back the nonce asked']
    if bad:
        raise CheckpointRefused('not kept: ' + '; '.join(bad))
    p = pathlib.Path(log); p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'a+b') as f:
        fcntl.flock(f, fcntl.LOCK_EX)                                   # one keeper at a time
        held, torn = read_log(p)
        earlier = audit(held, witness_keys)
        if earlier:
            raise CheckpointRefused('not kept: the log itself does not verify (' + earlier[0] + ')')
        known = {}
        for h in held:
            if h['root'] == cp['root']:
                for seq, head in _heads(h):
                    known.setdefault(seq, head)
        why = contradiction(known, last_seq(held, cp['root']), cp)
        if why:
            with open(str(p) + '.refused.jsonl', 'a', encoding='utf-8') as g:      # the evidence that two things were said
                g.write(json.dumps(cp, sort_keys=True) + '\n')
            raise CheckpointRefused(f'not kept: {why}.  The checkpoint is in {p}.refused.jsonl')
        if torn:                                                        # a last line cut off by a crash is taken away: it was never a checkpoint
            f.truncate(p.read_bytes().rfind(b'\n') + 1)
        f.seek(0, os.SEEK_END)
        f.write((json.dumps(cp, sort_keys=True) + '\n').encode()); f.flush(); os.fsync(f.fileno())


def main():
    ap = argparse.ArgumentParser(description='Fetch and keep the witness\'s checkpoints.')
    ap.add_argument('action', choices=['fetch', 'audit']); ap.add_argument('log_file', nargs='?')
    ap.add_argument('--witness-url'); ap.add_argument('--ca'); ap.add_argument('--cert'); ap.add_argument('--key')
    ap.add_argument('--root'); ap.add_argument('--nonce'); ap.add_argument('--at', type=int); ap.add_argument('--out'); ap.add_argument('--log')
    ap.add_argument('--witness-key', action='append', default=[])
    a = ap.parse_args()
    try:
        if a.action == 'fetch':
            if not (a.witness_url and a.root):
                ap.error('fetch needs --witness-url and --root')
            if a.log and not a.witness_key:
                ap.error('--log needs --witness-key, so that only the witness\'s checkpoints are kept')
            nonce = a.nonce if a.nonce is not None else secrets.token_urlsafe(18)
            at = a.at
            if at is None and a.log:
                at = last_seq(read_log(a.log)[0], a.root)                # tie this checkpoint to the last one kept
            try:
                cp = fetch(a.witness_url, a.ca, a.cert, a.key, a.root, nonce, at)
            except CheckpointRefused as exc:
                if a.log and a.at is None and at is not None and 'beyond the chain' in str(exc):
                    raise CheckpointRefused(f'ROLLBACK: the witness says its chain for {a.root} is shorter than sequence number {at}, which the log holds')
                raise
            if cp.get('root') != a.root or cp.get('nonce') != nonce:
                raise CheckpointRefused('the answer is not for the budget asked, or does not sign back the nonce asked')
            if a.witness_key:
                bad = checkpoint_problems(cp, _keys(a.witness_key), a.root)
                if bad:
                    raise CheckpointRefused('; '.join(bad))
            if a.out:
                pathlib.Path(a.out).write_text(json.dumps(cp, indent=1) + '\n')
            if a.log:
                keep(a.log, cp, a.witness_key, a.root, nonce)
            print(json.dumps({'root': cp.get('root'), 'seq': cp.get('seq'), 'time': cp.get('time'), 'nonce': nonce, 'at': cp.get('at'), 'kept': bool(a.log), 'out': a.out}))
        else:
            if not (a.log_file and a.witness_key):
                ap.error('audit needs the log and --witness-key')
            held, torn = read_log(a.log_file); problems = audit(held, a.witness_key)
            if torn:
                problems.append('the last line was cut off and is passed over')
            for line in problems:
                print(line)
            print(f'{len(held)} checkpoints; ' + ('no rollback or fork, every signature verifies' if not problems else f'{len(problems)} problems'))
            sys.exit(1 if problems else 0)
    except CheckpointRefused as exc:
        print(f'refused: {exc}', file=sys.stderr); sys.exit(1)


if __name__ == '__main__':
    main()
