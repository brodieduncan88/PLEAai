#!/usr/bin/env python3
"""The witness's checkpoints, kept by someone other than the service (Amendment 10).

    checkpoints.py fetch --witness-url URL --ca CA --cert CERT --key KEY --root ROOT [--nonce N] [--at K] [--out FILE] [--log LOG --witness-key HEX]
    checkpoints.py audit LOG --witness-key HEX [--witness-key HEX ...]

A checkpoint is the witness's signed statement of one budget's chain as it reads it at that moment: how many decisions
are recorded (seq), the hash of the last (head), the budget's two states, and its clock (witness_service.py, GET
/checkpoint).  A record says only what was so at its own sequence number, so an older record omits later runs and still
verifies.  A checkpoint obtained separately from the record says whether it is the latest: check_record.py --checkpoint.

`fetch` asks the witness and writes what it signed.  With --log it also appends it to a log, after checking it against
what the log already holds.  A party that keeps such a log, on a machine of its own, can tell later if the witness ever
said two different things about the same chain:

  ROLLBACK   a later checkpoint has a lower sequence number than an earlier one for the same budget;
  FORK       two checkpoints give different heads for the same sequence number of the same budget, whether as the chain's
             head or as the head after an earlier decision (at, head_at).

A checkpoint that fails either rule is not appended, and the command exits 1 saying which.  `audit` re-reads a whole log
by the same rules, and checks every signature.

What this is not.  The log is as independent as the machine and account it is kept on: in the demonstration it is on the
same machine as everything else.  A witness that always lies consistently, to everyone, is not caught by it.  The time in
a checkpoint is the witness's clock, not a time stamp from a third party.  This file needs the Python standard library and
`cryptography` (through check_record.py), and nothing from the gateway.
"""
import argparse
import json
import pathlib
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from check_record import _keys, checkpoint_problems     # noqa: E402

NONCE = re.compile(r'[A-Za-z0-9_-]{1,64}')


class CheckpointRefused(Exception):
    """The witness did not give a checkpoint, or the checkpoint contradicts what is already held."""


def fetch(witness_url: str, ca: str, cert: str | None, key: str | None, root: str, nonce: str | None = None, at: int | None = None, timeout: float = 15.0) -> dict:
    """Ask the witness for a checkpoint of `root`.  Nothing is checked here but that an answer came: verify it before use."""
    if nonce is not None and not NONCE.fullmatch(nonce):
        raise CheckpointRefused('a nonce is 1 to 64 characters of A-Z a-z 0-9 _ -')
    q = {'root': root}
    if nonce is not None:
        q['nonce'] = nonce
    if at is not None:
        q['at'] = str(int(at))
    url = witness_url.rstrip('/') + '/checkpoint?' + urllib.parse.urlencode(q)
    ctx = None
    if url.startswith('https:'):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT); ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.check_hostname = True; ctx.verify_mode = ssl.CERT_REQUIRED; ctx.load_verify_locations(cafile=ca)
        if cert:
            ctx.load_cert_chain(cert, key)
    try:
        with urllib.request.urlopen(url, timeout=timeout, context=ctx) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as exc:
        try:
            why = json.loads(exc.read()).get('error')
        except Exception:
            why = None
        raise CheckpointRefused(f'the witness answered {exc.code}' + (f': {why}' if why else ''))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise CheckpointRefused(f'the witness could not be asked ({type(exc).__name__})')


def read_log(path) -> list:
    p = pathlib.Path(path)
    if not p.exists():
        return []
    out = []
    for n, line in enumerate(p.read_text(encoding='utf-8').splitlines(), 1):
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                raise CheckpointRefused(f'line {n} of the log is not a checkpoint')
    return out


def _heads(cp: dict) -> list:
    """The (sequence number, head) pairs a checkpoint states."""
    out = [(cp['seq'], cp['head'])]
    if cp.get('at') is not None:
        out.append((cp['at'], cp['head_at']))
    return out


def contradiction(held: list, cp: dict):
    """None, or how `cp` contradicts the checkpoints already held for its budget, in the order they were kept."""
    mine = [h for h in held if h.get('root') == cp.get('root')]
    if mine and cp['seq'] < max(h['seq'] for h in mine):
        return f"ROLLBACK: sequence number {cp['seq']} after {max(h['seq'] for h in mine)} for {cp['root']}"
    known = {}
    for h in mine:
        for seq, head in _heads(h):
            known.setdefault(seq, head)
    for seq, head in _heads(cp):
        if seq in known and known[seq] != head:
            return f'FORK: two heads for sequence number {seq} of {cp["root"]}'
    return None


def audit(checkpoints: list, witness_keys) -> list:
    """Every problem in a log, read in order: a signature that does not verify, a rollback, a fork."""
    out, held = [], []
    for n, cp in enumerate(checkpoints, 1):
        bad = checkpoint_problems(cp, _keys(witness_keys), cp.get('root') if isinstance(cp, dict) else None)
        if bad:
            out.append(f'line {n}: ' + '; '.join(bad)); continue
        why = contradiction(held, cp)
        if why:
            out.append(f'line {n}: {why}')
        held.append(cp)
    return out


def keep(log, cp: dict, witness_keys) -> None:
    """Append a checkpoint to a log, unless it is not the witness's or contradicts what the log holds.  Raises CheckpointRefused."""
    bad = checkpoint_problems(cp, _keys(witness_keys), cp.get('root') if isinstance(cp, dict) else None)
    if bad:
        raise CheckpointRefused('not kept: ' + '; '.join(bad))
    held = read_log(log)
    earlier = audit(held, witness_keys)
    if earlier:
        raise CheckpointRefused('not kept: the log itself does not verify (' + earlier[0] + ')')
    why = contradiction(held, cp)
    if why:
        raise CheckpointRefused('not kept: ' + why)
    p = pathlib.Path(log); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('a', encoding='utf-8') as f:
        f.write(json.dumps(cp, sort_keys=True) + '\n')


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
            cp = fetch(a.witness_url, a.ca, a.cert, a.key, a.root, a.nonce, a.at)
            if a.log:
                keep(a.log, cp, a.witness_key)
            if a.out:
                pathlib.Path(a.out).write_text(json.dumps(cp, indent=1) + '\n')
            print(json.dumps({'root': cp.get('root'), 'seq': cp.get('seq'), 'time': cp.get('time'), 'kept': bool(a.log), 'out': a.out}))
        else:
            if not (a.log_file and a.witness_key):
                ap.error('audit needs the log and --witness-key')
            held = read_log(a.log_file); problems = audit(held, a.witness_key)
            for line in problems:
                print(line)
            print(f'{len(held)} checkpoints; ' + ('no rollback or fork, every signature verifies' if not problems else f'{len(problems)} problems'))
            sys.exit(1 if problems else 0)
    except CheckpointRefused as exc:
        print(f'refused: {exc}', file=sys.stderr); sys.exit(1)


if __name__ == '__main__':
    main()
