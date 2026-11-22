#!/usr/bin/env python3
"""The responsible engineer's console.  Everything here needs a key or a credential the assistant never holds.

    verify_ctl.py keygen KEYFILE
    verify_ctl.py baseline HOME --from DIR --card DRAFT.json --key KEYFILE [--runs 1000] [--alongside-reason "..."]
    verify_ctl.py revise   HOME --from DIR --card DRAFT.json --key KEYFILE --supersedes HASH --reason "..."
    verify_ctl.py status   HOME HASH
    verify_ctl.py acknowledge HOME HASH AID --disposition "..." --key KEYFILE
    verify_ctl.py record   HOME HASH --key KEYFILE --witness-key HEX --gate-key HEX --out RECORD.json [--journal FILE ...]
                           [--witness-url URL --tls-ca CA --tls-cert CERT --tls-key KEY]   put the witness's checkpoint in the record (Amendment 10)
                           [--deliveries LOG --courier-key HEX --mailbox-key HEX]   put the notices a courier delivered in the record (Amendment 11)

baseline takes a draft card the engineer wrote (requirement, limits, load case, design space, the check's file name,
author, reviewer and stated limits, the data files, the control cases) and a directory holding the check and its data.
It fills in the file hashes, runs every control case through the same decision code a governed attempt uses, and
refuses to go on unless each control gives the verdict the engineer expected: a check that cannot be seen to fail is
not baselined.  It then signs the card and the control results with the engineer's key, stores them with the check
and data under HOME/baselines/<hash>/, and provisions the budget REQ/REV/<hash> through the control plane, so the
immutable provisioning record names the baseline.  The number of official runs allowed is a ceiling, not a ration:
the default is 1000, and the replacement allowance is always 0, so no run is ever refunded.

baseline refuses a draft whose requirement id the service already holds a baseline for (Amendment 9): a change to a
requirement is made with revise, so that it is linked.  A second baseline for the same requirement that is not a change to
the first needs the engineer's reason, --alongside-reason; the reason and the baselines already held for that requirement are
written into the new card, which the engineer signs, so the link is in every record built from it.

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
import time
import unicodedata

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from plea_gateway import RootExists, Store                          # noqa: E402
from baseline import FORMAT, BaselineInvalid, card_hash, evaluate, root_for, sha256_hex, validate_card   # noqa: E402
from verify_record import Key, acknowledgement_message, attempts_of, build, load_envelope, now, sign_envelope   # noqa: E402
from service_client import OUTCOME_WORDS, met_lines                 # noqa: E402  (Amendment 9: a pass is shown as the declared check met; Amendment 17: from service_client)
import notices                                                       # noqa: E402  (Amendment 7: notices the service kept undelivered)
import check_record                                                  # noqa: E402  (Amendment 17, D20: controls put to the record's checker)

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


def requirement_key(requirement_id) -> str:
    """A requirement id as the continuity rule compares it: in Unicode's compatibility form; without the characters that show
    nothing (Unicode's format characters, such as a zero-width space, a soft hyphen or a byte-order mark; the combining marks
    left over once the form is composed, such as a variation selector or the combining grapheme joiner; and the Hangul
    fillers); with every dash and the minus sign as a hyphen; without case; with each run of white space as one space, and
    none at either end.  Ids that differ only in these ways are one requirement.  Letters that only look alike, a Latin E and
    a Cyrillic one, are not made one.  (Amendment 9.)"""
    s = unicodedata.normalize('NFKC', str(requirement_id))
    s = ''.join('-' if unicodedata.category(ch) == 'Pd' or ch == '\u2212' else ch for ch in s
                if unicodedata.category(ch) not in ('Cf', 'Mn', 'Me') and ch not in '\u115f\u1160\u3164\uffa0')
    return ' '.join(s.casefold().split())



def held_for_requirement(home, requirement_id) -> list:
    """The baselines this service holds for a requirement id, as {baseline_sha256, revision}, oldest first by when they were
    baselined.  Ids are compared as requirement_key gives them.  A baseline folder counts when its envelope is whole: its card
    can be read, its hash is its card's, and the key its card names signed it.  Whose key that is, is not asked here: the
    engineers of one service may each hold a baseline for one requirement, and each is counted, whichever engineer runs the
    console; the gate decides which keys it takes baselines from.  A folder that is not whole is passed over.  (Amendment 9.)"""
    found, want = [], requirement_key(requirement_id)
    try:
        folders = sorted((pathlib.Path(home) / 'baselines').iterdir())
    except OSError:
        return found
    for d in folders:
        try:
            env = json.loads((d / 'baseline.json').read_text(encoding='utf-8'))
            env = load_envelope(d / 'baseline.json', env['signature']['signer'])      # whole: its hash is its card's, and the key the card names signed it
            card = env['card']
            if requirement_key(card['requirement']['id']) == want and env['baseline_sha256'] == d.name:
                found.append((str(card.get('baselined_at', '')), {'baseline_sha256': d.name, 'revision': str(card['requirement']['revision'])}))
        except Exception:
            continue
    return [x for _, x in sorted(found, key=lambda t: t[0])]


def make_baseline(home, source, draft: dict, key: Key, runs: int = 1000, supersedes: dict | None = None, control_dsn: str = CONTROL_DSN, at: str | None = None,
                  alongside_reason: str | None = None) -> dict:
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
    card.pop('alongside', None)                    # Amendment 9: a link is made here, from what the service holds, and never taken from the draft
    if supersedes is None:                         # Amendment 9 (continuity): a requirement already held is changed by revise, or linked here
        rid = (card.get('requirement') or {}).get('id')
        others = held_for_requirement(home, rid) if isinstance(rid, str) else []
        if others:
            if not (isinstance(alongside_reason, str) and alongside_reason.strip()):
                raise BaselineInvalid(f"requirement {rid} already has a baseline at this service ({', '.join(o['baseline_sha256'][:16] + '… rev ' + o['revision'] for o in others)}): "
                                      'make this one a revision of it (revise --supersedes), or, if it is a separate baseline for the same requirement and not a change to it, '
                                      'give the reason (--alongside-reason), which is written into the signed card.  Nothing was baselined')
            card['alongside'] = {'reason': alongside_reason.strip(), 'baselines': others}
    card['baselined_at'] = at or now()
    validate_card(card)
    controls_run, rederived = [], []
    for c in card['controls']:
        v = evaluate(source, card, c['design'], control=True)
        rederived += [f'control "{c["name"]}": {p}' for p in check_record.rederive(card, v, c['design'], control=True)]   # Amendment 17 (second review, M4)
        controls_run.append({'name': c['name'], 'expect': c['expect'], 'verdict': v['verdict'], 'reason_code': v['reason_code'],
                             'criteria': [{'id': k['id'], 'achieved': k['achieved'], 'limit': k['limit'], 'met': k['met']} for k in v['criteria']]})
        if v['verdict'] != c['expect']:
            raise BaselineInvalid(f"control case \"{c['name']}\" was expected to {c['expect']} and gave {v['verdict']} ({v['reason_code']}): not baselined")
    problems = check_record.control_problems(card, controls_run) + rederived   # Amendment 17 (D20): the controls as the record's checker reads them, and as it reads every run
    if problems:
        raise BaselineInvalid('the controls as run would not verify in a record of this baseline, by the record\'s checker: '
                              + '; '.join(problems) + '.  A value the check gives to more than 28 significant digits is written rounded, '
                              'and a rounded value can fall on the other side of its limit.  Nothing was baselined')
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
    # Amendment 6 (15 November 2026): the engineer's inbox is made with the baseline and holds its full hash, its claim, so
    # that a notice about this baseline still reaches its engineer if the baseline's folder is later taken away.  A notice
    # about a made-up hash is kept out of the inbox because the service holds no folder for it (verify_tools._inbox).  A
    # claim already there is kept.  The claim is written whole or not at all.  If it cannot be written here, the gate's
    # tool writes it when it starts.
    box = home / 'inbox' / envelope['baseline_sha256'][:16]
    try:
        box.mkdir(parents=True, exist_ok=True)
        part = box / '.baseline_sha256.console'
        try:
            part.write_text(envelope['baseline_sha256'] + '\n', encoding='utf-8')
            try:
                os.link(part, box / 'baseline_sha256')
            except FileExistsError:
                pass
            except OSError:                                # a file system that makes no hard links
                if not (box / 'baseline_sha256').exists():
                    os.replace(part, box / 'baseline_sha256')
        finally:
            part.unlink(missing_ok=True)
    except OSError:
        pass
    return envelope


def revise(home, source, draft: dict, key: Key, old_hash: str, reason: str, runs: int = 1000, control_dsn: str = CONTROL_DSN, local_dsn: str = LOCAL_DSN) -> dict:
    old = load_envelope(pathlib.Path(home) / 'baselines' / old_hash / 'baseline.json', key.public_hex)
    old_root = root_for(old['card'])
    new_id, old_id = (draft.get('requirement') or {}).get('id'), old['card']['requirement']['id']
    if new_id != old_id:
        if isinstance(new_id, str) and requirement_key(new_id) == requirement_key(old_id):     # Amendment 9: say which spelling to keep
            raise BaselineInvalid(f'a revision keeps the requirement id as it is spelled in the baseline it revises: {old_id!r}, not {new_id!r}')
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


def witness_checkpointer(witness_url: str, ca: str, cert: str | None, key_file: str | None):
    """A function for record(): asks the witness for a checkpoint that names the head after the record's last decision.  (Amendment 10.)"""
    import checkpoints
    return lambda root, seq: checkpoints.fetch(witness_url, ca, cert, key_file, root, None, seq)


def record(home, baseline_hash, key: Key, witness_key, gate_key, journals=(), local_dsn: str = LOCAL_DSN, checkpointer=None, deliveries=None) -> dict:
    """The verification record.  checkpointer (witness_checkpointer) puts the witness's checkpoint into it (Amendment 10); without
    one the record has none, as before, and its checker says so.  deliveries ({'log': a courier's deliveries.jsonl, 'courier':
    [hex], 'mailbox': [hex]}) puts the notices delivered to the engineer's mailbox into it, with their receipts (Amendment 11)."""
    env = load_envelope(pathlib.Path(home) / 'baselines' / baseline_hash / 'baseline.json', key.public_hex)
    given = None
    if deliveries is not None:
        import courier
        given = {'items': courier.read_deliveries(deliveries['log'], root_for(env['card'])), 'courier': deliveries['courier'], 'mailbox': deliveries['mailbox']}
    rec = build(Store(local_dsn), env, root_for(env['card']), {'witness': witness_key, 'gate': gate_key}, key, submissions(home, journals), acknowledgements(home, baseline_hash),
                checkpointer=checkpointer, deliveries=given)
    if checkpointer is not None:                   # a record whose checkpoint its own checker would refuse is not handed over
        import check_record
        cp = rec.get('checkpoint')
        bad = check_record.checkpoint_problems(cp, witness_key, rec['root'])
        if not bad and (cp.get('at') != rec['as_of']['seq'] or cp.get('head_at') != rec['as_of']['head']):
            bad = ['it does not name the head after the record\'s last decision']
        if bad:
            raise ValueError('the witness\'s answer cannot go into the record: ' + '; '.join(bad))
    if deliveries is not None:                     # nor a record whose notices delivered its own checker would refuse (Amendment 11)
        import check_record
        _, checks, _ = check_record.verify(rec, dict(rec['keys'], witness=witness_key))
        bad = [d for n, _, good, d in checks if n == 10 and not good]
        if bad:
            raise ValueError('the notices delivered cannot go into the record: ' + bad[0])
    return rec


def status(home, baseline_hash, engineer_key: str, local_dsn: str = LOCAL_DSN) -> str:
    env = load_envelope(pathlib.Path(home) / 'baselines' / baseline_hash / 'baseline.json', engineer_key)
    root = root_for(env['card'])
    attempts, _ = attempts_of(Store(local_dsn), root, submissions(home))
    acked = {a['aid'] for a in acknowledgements(home, baseline_hash)}
    box = pathlib.Path(home) / 'inbox' / baseline_hash[:16]
    L = [root, f"{len(attempts)} official runs; {len(list(box.glob('*.txt'))) if box.exists() else 0} notices in the inbox"]
    checked, at = notices.delivery_state(home, baseline_hash)     # Amendment 8 (D3): whether the gate has shown it can write this inbox
    if checked == 'WRITABLE':                                       # Amendment 9: named for what it shows, which is not delivery
        L.append(f"inbox writable: the gate wrote a test file in this inbox at {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(at))}.  "
                 'This is not delivery: it does not show that a notice was delivered or read.')
    else:
        heading = {'UNCHECKED': 'INBOX NOT CHECKED', 'STALE': 'INBOX CHECK OUT OF DATE', 'NOT_WRITABLE': 'INBOX NOT WRITABLE'}.get(checked, 'INBOX NOT CHECKED')
        L.append(f"{heading}: {notices.DELIVERY_WORDS[checked]}.  A failure might not reach this inbox, and new runs through the "
                 f"front door are refused until the gate has written a test file there.")
    kept = notices.undelivered(home, baseline_hash)
    if kept:                                       # Amendment 7 (D2, D3): notices the inbox could not take, kept in the service's own store
        L.append(f"{len(kept)} notices kept undelivered, in {pathlib.Path(home) / 'undelivered' / baseline_hash}: {', '.join(kept)}")
    for a in attempts:
        r = a['result'] or {}
        L.append(f"  {a['aid']}  {OUTCOME_WORDS.get(a['outcome'], a['outcome']):<11} {r.get('reason_code', ''):<24} {'' if a['outcome'] == 'PASS' else ('acknowledged' if a['aid'] in acked else 'OPEN: awaiting disposition')}")
    L += met_lines(env['card'], attempts)
    return '\n'.join(L)


def main():
    ap = argparse.ArgumentParser(description='The responsible engineer\'s console.')
    ap.add_argument('action', choices=['keygen', 'baseline', 'revise', 'status', 'acknowledge', 'record']); ap.add_argument('home'); ap.add_argument('rest', nargs='*')
    ap.add_argument('--from', dest='source'); ap.add_argument('--card'); ap.add_argument('--key'); ap.add_argument('--runs', type=int, default=1000)
    ap.add_argument('--supersedes'); ap.add_argument('--reason'); ap.add_argument('--disposition'); ap.add_argument('--witness-key'); ap.add_argument('--gate-key')
    ap.add_argument('--alongside-reason', help='why a second baseline for a requirement already held is not a revision of it (Amendment 9)')
    ap.add_argument('--out'); ap.add_argument('--journal', action='append', default=[])
    ap.add_argument('--witness-url', help='record: ask the witness for a checkpoint and put it in the record (Amendment 10)')
    ap.add_argument('--tls-ca'); ap.add_argument('--tls-cert'); ap.add_argument('--tls-key')
    ap.add_argument('--deliveries', help='record: a courier\'s deliveries.jsonl; its notices delivered for this budget go into the record (Amendment 11)')
    ap.add_argument('--courier-key', action='append', default=[]); ap.add_argument('--mailbox-key', action='append', default=[])
    a = ap.parse_args()
    try:
        if a.action == 'keygen':
            print(json.dumps({'engineer_key': keygen(a.home).public_hex})); return
        key = load_key(a.key) if a.key else None
        if a.action in ('baseline', 'revise'):
            draft = json.loads(pathlib.Path(a.card).read_text())
            env = make_baseline(a.home, a.source, draft, key, a.runs, alongside_reason=a.alongside_reason) if a.action == 'baseline' else revise(a.home, a.source, draft, key, a.supersedes, a.reason, a.runs)
            print(json.dumps({'baseline_sha256': env['baseline_sha256'], 'root': root_for(env['card']), 'controls': [(c['name'], c['verdict']) for c in env['controls_run']]}))
        elif a.action == 'status':
            print(status(a.home, a.rest[0], key.public_hex))
        elif a.action == 'acknowledge':
            print(json.dumps(acknowledge(a.home, a.rest[0], a.rest[1], a.disposition, key)))
        elif a.action == 'record':
            if a.deliveries and not (a.courier_key and a.mailbox_key):
                raise ValueError('--deliveries needs the courier\'s key and the mailbox\'s key (--courier-key, --mailbox-key)')
            rec = record(a.home, a.rest[0], key, a.witness_key, a.gate_key, a.journal,
                         checkpointer=witness_checkpointer(a.witness_url, a.tls_ca, a.tls_cert, a.tls_key) if a.witness_url else None,
                         deliveries={'log': a.deliveries, 'courier': a.courier_key, 'mailbox': a.mailbox_key} if a.deliveries else None)
            pathlib.Path(a.out).write_text(json.dumps(rec, indent=1) + '\n'); print(json.dumps({'record': a.out, 'attempts': len(rec['attempts']), 'as_of': rec['as_of']}))
    except (BaselineInvalid, ValueError, OSError) as exc:
        print(f'refused: {exc}', file=sys.stderr); sys.exit(1)


if __name__ == '__main__':
    main()
