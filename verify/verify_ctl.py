#!/usr/bin/env python3
"""The responsible engineer's console.  Everything here needs a key or a credential the assistant never holds.

    verify_ctl.py keygen KEYFILE
    verify_ctl.py baseline HOME --from DIR --card DRAFT.json --key KEYFILE [--runs 1000]
    verify_ctl.py revise   HOME --from DIR --card DRAFT.json --key KEYFILE --supersedes HASH --reason "..."
    verify_ctl.py status   HOME HASH
    verify_ctl.py acknowledge HOME HASH AID --disposition "..." --key KEYFILE
    verify_ctl.py record   HOME HASH --key KEYFILE --witness-key HEX --gate-key HEX --out RECORD.json [--journal FILE ...]

baseline takes a draft card the engineer wrote (requirement, limits, load case, design space, the check's file name,
author, reviewer and stated limits, the data files, the control cases) and a directory holding the check and its data.
It fills in the file hashes, runs every control case through the same decision code a governed attempt uses, and
refuses to go on unless each control gives the verdict the engineer expected: a check that cannot be seen to fail is
not baselined.  It then signs the card and the control results with the engineer's key, stores them with the check
and data under HOME/baselines/<hash>/, and provisions the budget REQ/REV/<hash> through the control plane, so the
immutable provisioning record names the baseline.  The number of official runs allowed is a ceiling, not a ration:
the default is 1000, and the replacement allowance is always 0, so no run is ever refunded.

revise is the only way a requirement, a limit, a load case, a design space or a check changes.  It stops the old
baseline's budget (no further runs on it), counts what happened on it from the store, and writes that count and the
engineer's reason into the new card before signing.  The old record stays.  Nothing is edited in place.

acknowledge records the engineer's disposition of a FAIL or UNKNOWN, signed with the engineer's key.
"""
import argparse
import json
import os
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from plea_gateway import RootExists, Store                          # noqa: E402
from baseline import FORMAT, BaselineInvalid, card_hash, evaluate, root_for, sha256_hex, validate_card   # noqa: E402
from verify_record import Key, acknowledgement_message, attempts_of, build, load_envelope, now, sign_envelope   # noqa: E402

CONTROL_DSN = os.environ.get('PLEA_CONTROL_DSN', 'postgresql://plea_control:control@127.0.0.1:5432/plea')
LOCAL_DSN = os.environ.get('PLEA_LOCAL_DSN', 'postgresql://plea_local:local@127.0.0.1:5432/plea')


def load_key(path) -> Key:
    return Key(pathlib.Path(path).read_text().strip())


def keygen(path) -> Key:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    key = Key()
    with os.fdopen(fd, 'w') as f:
        f.write(key.private_hex + '\n')
    return key


def make_baseline(home, source, draft: dict, key: Key, runs: int = 1000, supersedes: dict | None = None, control_dsn: str = CONTROL_DSN, at: str | None = None) -> dict:
    """Fill, test, sign, store and provision a baseline.  Returns the envelope.  Raises BaselineInvalid with the reason."""
    home, source = pathlib.Path(home), pathlib.Path(source)
    card = json.loads(json.dumps(draft))
    card['format'] = FORMAT
    card.setdefault('check', {})
    try:
        card['check']['sha256'] = sha256_hex((source / card['check']['file']).read_bytes())
        card['inputs'] = [{'file': i['file'], 'sha256': sha256_hex((source / i['file']).read_bytes())} for i in card.get('inputs', [])]
    except (OSError, KeyError, TypeError) as exc:
        raise BaselineInvalid(f'the check or a data file could not be read: {exc}')
    card['responsible_engineer'] = {'name': (card.get('responsible_engineer') or {}).get('name', ''), 'key': key.public_hex}
    card['supersedes'] = supersedes
    card['baselined_at'] = at or now()
    validate_card(card)
    controls_run = []
    for c in card['controls']:
        v = evaluate(source, card, c['design'], control=True)
        controls_run.append({'name': c['name'], 'expect': c['expect'], 'verdict': v['verdict'], 'reason_code': v['reason_code'],
                             'criteria': [{'id': k['id'], 'achieved': k['achieved'], 'limit': k['limit'], 'met': k['met']} for k in v['criteria']]})
        if v['verdict'] != c['expect']:
            raise BaselineInvalid(f"control case \"{c['name']}\" was expected to {c['expect']} and gave {v['verdict']} ({v['reason_code']}): not baselined")
    envelope = sign_envelope(card, controls_run, key)
    directory = home / 'baselines' / envelope['baseline_sha256']
    directory.mkdir(parents=True, exist_ok=False)
    for name in [card['check']['file']] + [i['file'] for i in card['inputs']]:
        shutil.copyfile(source / name, directory / name)
    (directory / 'baseline.json').write_text(json.dumps(envelope, indent=1) + '\n')
    try:
        Store(control_dsn).new_root(root_for(card), runs, 0)          # replacement allowance 0: no run is ever refunded
    except RootExists:
        raise BaselineInvalid('this exact baseline is already provisioned')
    return envelope


def revise(home, source, draft: dict, key: Key, old_hash: str, reason: str, runs: int = 1000, control_dsn: str = CONTROL_DSN, local_dsn: str = LOCAL_DSN) -> dict:
    old = load_envelope(pathlib.Path(home) / 'baselines' / old_hash / 'baseline.json', key.public_hex)
    old_root = root_for(old['card'])
    if (draft.get('requirement') or {}).get('id') != old['card']['requirement']['id']:
        raise BaselineInvalid('a revision keeps the requirement id; a different id is a different requirement')
    if not reason or not reason.strip():
        raise BaselineInvalid('a revision needs a reason')
    d, _ = Store(control_dsn).apply(old_root, ('STOP',))             # no further official runs on the superseded baseline
    attempts, _ = attempts_of(Store(local_dsn), old_root, [])
    counts = {'official_runs': len(attempts), 'met': sum(a['outcome'] == 'PASS' for a in attempts), 'not_met': sum(a['outcome'] == 'FAIL' for a in attempts),
              'unknown': sum(a['outcome'] not in ('PASS', 'FAIL') for a in attempts)}
    return make_baseline(home, source, draft, key, runs, dict(baseline_sha256=old_hash, revision=old['card']['requirement']['revision'], reason=reason.strip(), **counts), control_dsn)


def acknowledgements(home, baseline_hash) -> list:
    p = pathlib.Path(home) / 'baselines' / baseline_hash / 'acknowledgements.jsonl'
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def acknowledge(home, baseline_hash, aid: str, disposition: str, key: Key, local_dsn: str = LOCAL_DSN) -> dict:
    env = load_envelope(pathlib.Path(home) / 'baselines' / baseline_hash / 'baseline.json', key.public_hex)
    root = root_for(env['card'])
    attempts, _ = attempts_of(Store(local_dsn), root, [])
    a = next((x for x in attempts if x['aid'] == aid), None)
    if a is None:
        raise BaselineInvalid(f'{aid} is not an official run on this baseline')
    if a['outcome'] == 'PASS':
        raise BaselineInvalid('a run that met the declared check needs no disposition')
    t = now()
    ack = {'aid': aid, 'outcome': a['outcome'], 'disposition': disposition, 'time': t, 'signer': key.public_hex,
           'signature': key.sign(acknowledgement_message(root, aid, a['outcome'], disposition, t))}
    with (pathlib.Path(home) / 'baselines' / baseline_hash / 'acknowledgements.jsonl').open('a') as f:
        f.write(json.dumps(ack) + '\n')
    return ack


def submissions(home, journals=()) -> list:
    """Candidate submissions for binding attempts to what was sent: the gate's own ledger and any client journals."""
    out = []
    ledger = pathlib.Path(home) / 'ledger.jsonl'
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get('event') == 'called' and isinstance(row.get('baseline_sha256'), str):
                out.append({'baseline_sha256': row['baseline_sha256'], 'design': row.get('design')})
    for j in journals:
        p = pathlib.Path(j)
        if p.exists():
            for line in p.read_text().splitlines():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def record(home, baseline_hash, key: Key, witness_key, gate_key, journals=(), local_dsn: str = LOCAL_DSN) -> dict:
    env = load_envelope(pathlib.Path(home) / 'baselines' / baseline_hash / 'baseline.json', key.public_hex)
    return build(Store(local_dsn), env, root_for(env['card']), {'witness': witness_key, 'gate': gate_key}, key, submissions(home, journals), acknowledgements(home, baseline_hash))


def status(home, baseline_hash, engineer_key: str, local_dsn: str = LOCAL_DSN) -> str:
    env = load_envelope(pathlib.Path(home) / 'baselines' / baseline_hash / 'baseline.json', engineer_key)
    root = root_for(env['card'])
    attempts, _ = attempts_of(Store(local_dsn), root, submissions(home))
    acked = {a['aid'] for a in acknowledgements(home, baseline_hash)}
    box = pathlib.Path(home) / 'inbox' / baseline_hash[:16]
    L = [root, f"{len(attempts)} official runs; {len(list(box.glob('*.txt'))) if box.exists() else 0} notices in the inbox"]
    for a in attempts:
        r = a['result'] or {}
        L.append(f"  {a['aid']}  {a['outcome']:<11} {r.get('reason_code', ''):<24} {'' if a['outcome'] == 'PASS' else ('acknowledged' if a['aid'] in acked else 'OPEN: awaiting disposition')}")
    return '\n'.join(L)


def main():
    ap = argparse.ArgumentParser(description='The responsible engineer\'s console.')
    ap.add_argument('action', choices=['keygen', 'baseline', 'revise', 'status', 'acknowledge', 'record']); ap.add_argument('home'); ap.add_argument('rest', nargs='*')
    ap.add_argument('--from', dest='source'); ap.add_argument('--card'); ap.add_argument('--key'); ap.add_argument('--runs', type=int, default=1000)
    ap.add_argument('--supersedes'); ap.add_argument('--reason'); ap.add_argument('--disposition'); ap.add_argument('--witness-key'); ap.add_argument('--gate-key')
    ap.add_argument('--out'); ap.add_argument('--journal', action='append', default=[])
    a = ap.parse_args()
    try:
        if a.action == 'keygen':
            print(json.dumps({'engineer_key': keygen(a.home).public_hex})); return
        key = load_key(a.key) if a.key else None
        if a.action in ('baseline', 'revise'):
            draft = json.loads(pathlib.Path(a.card).read_text())
            env = make_baseline(a.home, a.source, draft, key, a.runs) if a.action == 'baseline' else revise(a.home, a.source, draft, key, a.supersedes, a.reason, a.runs)
            print(json.dumps({'baseline_sha256': env['baseline_sha256'], 'root': root_for(env['card']), 'controls': [(c['name'], c['verdict']) for c in env['controls_run']]}))
        elif a.action == 'status':
            print(status(a.home, a.rest[0], key.public_hex))
        elif a.action == 'acknowledge':
            print(json.dumps(acknowledge(a.home, a.rest[0], a.rest[1], a.disposition, key)))
        elif a.action == 'record':
            rec = record(a.home, a.rest[0], key, a.witness_key, a.gate_key, a.journal)
            pathlib.Path(a.out).write_text(json.dumps(rec, indent=1) + '\n'); print(json.dumps({'record': a.out, 'attempts': len(rec['attempts']), 'as_of': rec['as_of']}))
    except (BaselineInvalid, ValueError, OSError) as exc:
        print(f'refused: {exc}', file=sys.stderr); sys.exit(1)


if __name__ == '__main__':
    main()
