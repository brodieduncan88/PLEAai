#!/usr/bin/env python3
"""Check a verification record offline.

    check_record.py RECORD.json --witness-key HEX --gate-key HEX --engineer-key HEX   (keys obtained separately from the record)
    check_record.py RECORD.json --keys KEYS.json                                      ({"witness": HEX, "gate": HEX, "engineer": HEX})
    check_record.py RECORD.json                                                       (keys read from the record: consistency only)
    ... --design RELEASED.json      also say whether this design file is one the record shows as meeting the declared check

This file stands alone: the Python standard library and the `cryptography` package, nothing from the gateway, and no
network or database.  It recomputes every hash, checks every signature and re-does every comparison in the record:

  1  the record's own signature, by the responsible engineer's key; the keys the record names are the keys given;
  2  the baseline: the card hashes to the baseline hash; the engineer signed the card together with its control cases;
     the controls include a design that failed as expected and one that passed as expected; the budget is named for
     this baseline's hash, its provisioning record hashes to itself, and it allows no refunds;
  3  the audit chain recomputes from the provisioning record, row by row, to the record's as-of sequence number;
  4  each witness receipt is signed by the witness, is for this budget and attempt, and carries the chain hash of the
     audit row at its sequence number; the intent and crossing receipts bind the attempt's nonce;
  5  the official runs listed are exactly the attempts in the last chained state, and each is bound to the baseline
     and the design it was sent with: the request key, the attempt id and the nonce recompute from them;
  6  each gate report is signed by the gate host; each verdict hashes to the digest the gate signed, names this
     baseline, this design and the baselined check; and the verdict is re-derived here from the achieved values and
     the baselined limits: design-space membership, every comparison, every margin, the plausible range, the reason
     code.  No run was refunded.  A run without a verdict carries no result;
  7  the counts: every attempt in the chained state is listed and counted;
  8  each acknowledgement is signed by the engineer and names a run in this record.

It then states the status.  NOT VERIFIED is the default: the status is "declared check met" only if a listed run's
verdict is PASS, and only for that exact design.

What it cannot tell you.  Whether the check is correct, whether the requirement is complete, whether the design sent
is the part that was built, or whether work was done outside the service.  One party holds the witness, gate and
engineer keys in the demonstration, so that party is trusted.  A record is a statement as of its sequence number: an
older record omits later runs and still verifies.  Without keys given separately, the keys are read from the record
itself, which shows only that the record is consistent, not who made it.
"""
import argparse
import decimal
import hashlib
import json
import sys

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

FORMAT, CARD_FORMAT, VERDICT_FORMAT = 'verification-record/1', 'verification-baseline/1', 'verification-verdict/1'
PROVISION_FIELDS = ('record', 'seq', 'root', 'k', 'm', 'issuer', 'contract', 'release', 'created_at')
LIVE_R = ('RESERVING', 'RESERVED', 'TOKEN')
LIVE_C = ('INTENT_PENDING', 'CONSUMED', 'NO_EFFECT', 'EFFECT', 'INDETERMINATE')
REASONS = {'MET': 'PASS', 'LIMIT_NOT_MET': 'FAIL', 'DESIGN_OUTSIDE_BASELINE': 'FAIL', 'BASELINE_MISMATCH': 'UNKNOWN', 'CHECK_ERROR': 'UNKNOWN',
           'CHECK_OUTPUT_INVALID': 'UNKNOWN', 'RESULT_IMPLAUSIBLE': 'UNKNOWN'}
D = decimal.Decimal


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def signed_by(public_hex, signature_hex, message: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex)).verify(bytes.fromhex(signature_hex), message)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def dec(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        d = D(str(value).strip())
    except (decimal.InvalidOperation, ValueError):
        return None
    return d if d.is_finite() else None


def text(d) -> str:
    return '0' if d == 0 else format(d.normalize(), 'f')


def chain_hash(prev_hash, row) -> str:
    return sha(prev_hash + canonical({k: row[k] for k in ('seq', 'op', 'kind', 'code', 'observation')}))


def provision_hash(record) -> str:
    return sha(record['prev_hash'] + canonical({f: record[f] for f in PROVISION_FIELDS}))


def receipt_message(r) -> bytes:
    return canonical({k: r.get(k) for k in ('root', 'aid', 'seq', 'op', 'kind', 'code', 'hash', 'binding')}).encode()


def evidence_message(e) -> bytes:
    return canonical({k: e.get(k) for k in ('kind', 'root', 'aid', 'nonce', 'claim', 'result_digest')}).encode()


def request_key(arguments) -> str:
    return 'verify:' + sha(canonical(arguments))[:24]


def attempt_id(key: str) -> str:
    return 'a-' + sha(key)[:16]


def nonce_for(root, aid, executor, tool, arguments) -> str:
    return 'n-' + sha(canonical({'root': root, 'aid': aid, 'executor': executor, 'tool': tool, 'arguments': arguments}))[:40]


def _keys(pinned) -> tuple:
    return (pinned,) if isinstance(pinned, str) else tuple(pinned or ())


def in_design_space(card, design) -> bool:
    space = card.get('design_space') or {}
    if not isinstance(design, dict) or set(design) != set(space):
        return False
    for name, rule in space.items():
        v = design[name]
        if 'choice' in rule:
            if isinstance(v, bool) or not isinstance(v, (str, int)) or not any(type(v) is type(c) and v == c for c in rule['choice']):
                return False
        else:
            d = dec(v)
            if d is None or isinstance(v, str) or not D(rule['min']) <= d <= D(rule['max']):
                return False
    return True


def rederive(card, result, design) -> list:
    """Problems with a signed verdict, re-deriving it from the card.  Empty when the verdict is exactly what the card implies."""
    out = []
    reason, verdict, crit = result.get('reason_code'), result.get('verdict'), result.get('criteria')
    if reason not in REASONS or REASONS[reason] != verdict:
        return [f'verdict {verdict} does not go with reason {reason}']
    if not isinstance(crit, list) or [c.get('id') for c in crit] != [c['id'] for c in card['criteria']]:
        return ['the criteria are not the baselined criteria']
    for c, base in zip(crit, card['criteria']):
        if any(c.get(k) != base[k] for k in ('quantity', 'comparison', 'limit', 'units')):
            out.append(f'{base["id"]}: the limit, comparison, quantity or units differ from the baseline')
    inside = in_design_space(card, design)
    if reason == 'DESIGN_OUTSIDE_BASELINE':
        if inside:
            out.append('says the design is outside the baseline, but it is inside')
        if any(c.get('achieved') is not None or c.get('met') is not None for c in crit):
            out.append('carries achieved values for a design that was not checked')
        return out
    if not inside:
        return out + ['the design is outside the baselined design space, so it cannot have this verdict']
    if verdict == 'UNKNOWN':
        if any(c.get('achieved') is not None or c.get('met') is not None for c in crit):
            out.append('an UNKNOWN verdict carries achieved values')
        return out
    all_met = True
    for c, base in zip(crit, card['criteria']):
        value, limit = dec(c.get('achieved')), D(base['limit'])
        if value is None or not isinstance(c.get('achieved'), str):
            out.append(f'{base["id"]}: no achieved value'); all_met = False; continue
        if not D(base['plausible']['min']) <= value <= D(base['plausible']['max']):
            out.append(f'{base["id"]}: achieved {c["achieved"]} is outside the plausible range and should have been UNKNOWN')
        met = value <= limit if base['comparison'] == '<=' else value >= limit
        margin = text(limit - value) if base['comparison'] == '<=' else text(value - limit)
        if c.get('met') is not met:
            out.append(f'{base["id"]}: recorded as {"met" if c.get("met") else "not met"}, but {c["achieved"]} {base["comparison"]} {base["limit"]} is {met}')
        if c.get('margin') != margin:
            out.append(f'{base["id"]}: the margin does not recompute')
        all_met = all_met and met
    if (reason == 'MET') != all_met:
        out.append(f'reason {reason} does not follow from the comparisons')
    return out


def verify(record: dict, keys: dict | None = None, design=None) -> tuple[bool, list, dict]:
    """(every check passed, [(number, title, ok, detail)], summary).  keys: {'witness', 'gate', 'engineer'}; None reads the record's."""
    problems = {n: [] for n in range(1, 9)}
    def bad(n, msg):
        problems[n].append(msg)
    pinned = keys is not None
    try:
        keys = keys or record['keys']
        wkeys, gkey, ekey = _keys(keys['witness']), keys['gate'], keys['engineer']
        body = {k: v for k, v in record.items() if k != 'signature'}
        root, env, prov, audit, attempts, as_of, sig = record['root'], record['baseline'], record['provisioning'], record['audit'], record['attempts'], record['as_of'], record['signature']
        card, acks = env['card'], record.get('acknowledgements') or []
        if not isinstance(card.get('criteria'), list) or not isinstance(card.get('design_space'), dict) or not isinstance(card.get('check'), dict):
            raise KeyError('card')
    except (KeyError, TypeError, AttributeError) as exc:
        return False, [(0, 'the record has the expected shape', False, f'missing {exc}')], {}

    # 1 the record's signature
    if record.get('format') != FORMAT:
        bad(1, f'format is {record.get("format")!r}, not {FORMAT!r}')
    if sig.get('signer') != ekey:
        bad(1, 'signed by a key other than the engineer\'s')
    elif not signed_by(ekey, sig.get('signature', ''), canonical(body).encode()):
        bad(1, 'bad signature: the record was changed after it was signed')
    named = record.get('keys') if isinstance(record.get('keys'), dict) else {}
    if not _keys(named.get('witness')) or not set(_keys(named.get('witness'))) <= set(wkeys) or named.get('gate') != gkey or named.get('engineer') != ekey:
        bad(1, 'the record names keys other than the ones given')

    # 2 the baseline and its anchor
    b_hash = sha(canonical(card))
    if card.get('format') != CARD_FORMAT or b_hash != record.get('baseline_sha256') or b_hash != env.get('baseline_sha256'):
        bad(2, 'the card does not hash to the baseline hash')
    esig = env.get('signature') or {}
    if esig.get('signer') != ekey or (card.get('responsible_engineer') or {}).get('key') != ekey:
        bad(2, 'the baseline is not signed by the engineer\'s key, or the card names another key')
    elif not signed_by(ekey, esig.get('signature', ''), canonical({'card': card, 'controls_run': env.get('controls_run')}).encode()):
        bad(2, 'the engineer\'s signature on the baseline does not verify')
    runs = env.get('controls_run') or []
    declared = [(c.get('name'), c.get('expect')) for c in card.get('controls') or []]
    if [(c.get('name'), c.get('expect')) for c in runs] != declared or any(c.get('verdict') != c.get('expect') for c in runs):
        bad(2, 'a control case did not give its expected verdict at baselining, or the controls run are not the controls declared')
    if not {'PASS', 'FAIL'} <= {c.get('verdict') for c in runs}:
        bad(2, 'the controls do not include both a design that failed and one that passed')
    for c in runs:                                           # a control's recorded numbers must give its recorded verdict against the card's limits
        got = c.get('criteria') or []
        if [x.get('id') for x in got] != [x['id'] for x in card['criteria']] or any(x.get('limit') != b['limit'] for x, b in zip(got, card['criteria'])):
            bad(2, f'control "{c.get("name")}": its criteria are not the card\'s'); continue
        values = [dec(x.get('achieved')) for x in got]
        if any(v is None for v in values):
            if REASONS.get(c.get('reason_code')) != 'UNKNOWN' or c.get('verdict') != 'UNKNOWN' or any(x.get('met') is not None for x in got):
                bad(2, f'control "{c.get("name")}": no achieved value, but it is not recorded as UNKNOWN')
            continue
        mets = [(v <= D(b['limit'])) if b['comparison'] == '<=' else (v >= D(b['limit'])) for v, b in zip(values, card['criteria'])]
        if [x.get('met') for x in got] != mets or c.get('verdict') != ('PASS' if all(mets) else 'FAIL') or c.get('reason_code') != ('MET' if all(mets) else 'LIMIT_NOT_MET'):
            bad(2, f'control "{c.get("name")}": its recorded verdict does not follow from its recorded numbers')
    req = card.get('requirement') or {}
    if root != f"{req.get('id')}/{req.get('revision')}/{b_hash[:32]}":
        bad(2, 'the budget is not named for this requirement, revision and baseline hash')
    if not isinstance(prov, dict) or any(f not in prov for f in PROVISION_FIELDS + ('prev_hash', 'hash')):
        bad(2, 'no provisioning record'); prov = None
    elif provision_hash(prov) != prov['hash']:
        bad(2, 'the provisioning record does not hash to itself')
    elif prov['root'] != root:
        bad(2, 'the provisioning record is for another budget')
    elif prov['m'] != 0:
        bad(2, 'the budget allows refunds; a verification run must never be refunded')
    k, m = (prov['k'], prov['m']) if prov else (None, None)

    # 3 the audit chain
    prev = prov['hash'] if prov else ''
    for i, row in enumerate(audit, start=1):
        if row.get('seq') != i:
            bad(3, f'row {i}: sequence number is {row.get("seq")}'); break
        if row.get('prev_hash') != prev:
            bad(3, f'seq {i}: does not follow the row before it'); break
        if chain_hash(prev, row) != row.get('hash'):
            bad(3, f'seq {i}: the row does not hash to its recorded hash'); break
        if (row['observation'].get('k'), row['observation'].get('m')) != (k, m):
            bad(3, f'seq {i}: records a budget other than the one provisioned'); break
        prev = row['hash']
    if as_of.get('seq') != len(audit) or as_of.get('head') != prev:
        bad(3, 'the as-of sequence number or head does not match the audit rows')
    chain_ok = not problems[3]
    final = audit[-1]['observation'] if audit else {'attempts': [], 'live': [0, 0, 0], 'k': k, 'm': m}

    # 5 the runs listed are the chained state's attempts, bound to what was sent
    listed = [[a.get('aid'), a.get('request_key'), a.get('phase'), a.get('nonce')] for a in attempts]
    chained = [[x[0], x[1], x[2], x[3]] for x in final.get('attempts', [])]
    if sorted(listed, key=str) != sorted(chained, key=str):
        bad(5, 'the runs listed are not the attempts in the last chained state')
    for a in attempts:
        aid, args = a.get('aid'), a.get('arguments')
        if not isinstance(args, dict):
            if a.get('phase') == 'EFFECT':
                bad(5, f'{aid}: a run with a verdict gives no design, so it cannot be checked')
            continue
        if set(args) != {'baseline_sha256', 'design'}:
            bad(5, f'{aid}: unexpected arguments')
        if request_key(args) != a.get('request_key') or attempt_id(a.get('request_key') or '') != aid:
            bad(5, f'{aid}: the request key or attempt id does not recompute from the baseline and design')
        if args.get('baseline_sha256') != b_hash:
            bad(5, f'{aid}: sent against another baseline')
        if a.get('nonce') is not None and nonce_for(root, aid, gkey, 'verify', args) != a['nonce']:
            bad(5, f'{aid}: the nonce does not bind this design to the gate key')

    # 4 witness receipts
    n_receipts = 0
    for a in attempts:
        aid = a.get('aid')
        for op, r in (a.get('receipts') or {}).items():
            n_receipts += 1
            where = f'{aid} {op}'
            if r.get('signer') not in wkeys:
                bad(4, f'{where}: not signed by the witness key'); continue
            if not signed_by(r['signer'], r.get('signature', ''), receipt_message(r)):
                bad(4, f'{where}: bad signature'); continue
            if r.get('root') != root or r.get('aid') != aid or not r.get('op') or r['op'][0] != op:
                bad(4, f'{where}: for another budget, attempt or operation'); continue
            seq = r.get('seq')
            if not isinstance(seq, int) or not 1 <= seq <= len(audit):
                bad(4, f'{where}: sequence number {seq} is outside the audit rows'); continue
            row = audit[seq - 1]
            if chain_ok and (row['hash'] != r.get('hash') or row['op'] != r['op'] or row['kind'] != r.get('kind') or row['code'] != r.get('code')):
                bad(4, f'{where}: does not match the audit row at sequence number {seq}')
            if op in ('ACCEPT_INTENT', 'CROSS') and r.get('binding') != a.get('nonce'):
                bad(4, f'{where}: binds another nonce')
            if op == 'CROSS' and not (r.get('kind') == 'APPLIED' or (r.get('kind'), r.get('code')) == ('DENIED', 'ALREADY_CROSSED')):
                bad(4, f'{where}: the witness did not record a crossing')
            if op != 'CROSS' and r.get('kind') not in ('APPLIED', 'DUPLICATE'):
                bad(4, f'{where}: not an acceptance')
        need = {'RESERVING': (), 'RESERVED': ('ACCEPT_RESERVATION',), 'TOKEN': ('ACCEPT_RESERVATION',), 'INTENT_PENDING': ('ACCEPT_RESERVATION', 'ACCEPT_INTENT')}
        for op in need.get(a.get('phase'), ('ACCEPT_RESERVATION', 'ACCEPT_INTENT', 'CROSS')):
            if op not in (a.get('receipts') or {}):
                bad(4, f'{aid}: no {op} receipt for a run in phase {a.get("phase")}')

    # 6 gate reports and verdicts, re-derived
    rows_out = []
    for a in attempts:
        aid, args, result, claims, phase = a.get('aid'), a.get('arguments') or {}, a.get('result'), [], a.get('phase')
        for item in a.get('evidence') or []:
            e, seq = item.get('evidence') or {}, item.get('seq')
            where = f'{aid} gate report at {seq}'
            if e.get('kind') != 'EFFECT_REPORT':
                bad(6, f'{where}: not an effect report'); continue
            if e.get('signer') != gkey or not signed_by(gkey, e.get('signature', ''), evidence_message(e)):
                bad(6, f'{where}: not signed by the gate key'); continue
            if e.get('root') != root or e.get('aid') != aid or e.get('nonce') != a.get('nonce'):
                bad(6, f'{where}: for another budget, attempt or nonce'); continue
            if not isinstance(seq, int) or not 1 <= seq <= len(audit) or audit[seq - 1]['op'][:2] != ['RECONCILE', aid]:
                bad(6, f'{where}: not recorded with a reconcile decision for this attempt'); continue
            claims.append(e.get('claim'))
        if phase == 'NO_EFFECT':
            bad(6, f'{aid}: this run was refunded (NO_EFFECT); a verification run must never be refunded'); want = 'REFUNDED'
        elif phase == 'EFFECT':
            if 'EFFECT' not in claims:
                bad(6, f'{aid}: phase EFFECT without a gate report claiming it')
            digests = [i['evidence'].get('result_digest') for i in a.get('evidence') or [] if (i.get('evidence') or {}).get('claim') == 'EFFECT']
            want = 'INVALID'
            if not isinstance(result, dict):
                bad(6, f'{aid}: the gate signed a verdict, but none is given')
            else:
                if sha(canonical(result)) not in digests:
                    bad(6, f'{aid}: the verdict does not hash to the digest the gate signed')
                if result.get('format') != VERDICT_FORMAT or result.get('baseline_sha256') != b_hash:
                    bad(6, f'{aid}: the verdict is for another baseline')
                if result.get('design') != args.get('design') or result.get('design_sha256') != sha(canonical(result.get('design'))):
                    bad(6, f'{aid}: the verdict is for another design than the one sent')
                if result.get('reason_code') == 'BASELINE_MISMATCH' and result.get('check') is None:
                    # the service held no usable baseline for this request (the stored card was changed, or signed by someone else): no card was used
                    if result.get('verdict') != 'UNKNOWN' or result.get('criteria') != [] or result.get('requirement_id') is not None or result.get('revision') is not None:
                        bad(6, f'{aid}: a refusal for want of a usable baseline must be UNKNOWN and carry no criteria')
                else:
                    if (result.get('requirement_id'), result.get('revision')) != (req.get('id'), req.get('revision')):
                        bad(6, f'{aid}: the verdict names another requirement or revision')
                    if (result.get('check') or {}).get('sha256') != card['check'].get('sha256'):
                        bad(6, f'{aid}: the verdict was produced by a check other than the baselined one')
                    for p in rederive(card, result, result.get('design')):
                        bad(6, f'{aid}: {p}')
                want = result.get('verdict') if result.get('verdict') in ('PASS', 'FAIL', 'UNKNOWN') else 'INVALID'
        else:
            want = 'PENDING' if phase in LIVE_R + ('INTENT_PENDING',) else ('INTERRUPTED' if phase == 'CONSUMED' and 'UNKNOWN' in claims else ('PENDING' if phase == 'CONSUMED' else phase))
            if result is not None:
                bad(6, f'{aid}: a run without a signed verdict must carry no result')
        if a.get('outcome') != want:
            bad(6, f'{aid}: the record says {a.get("outcome")}, the phase and gate reports say {want}')
        r = result if isinstance(result, dict) else {}
        rows_out.append({'aid': aid, 'outcome': a.get('outcome'), 'reason_code': r.get('reason_code'), 'design': (a.get('arguments') or {}).get('design'),
                         'design_sha256': r.get('design_sha256') or (sha(canonical(args['design'])) if 'design' in args else None), 'criteria': r.get('criteria') or [],
                         'detail': r.get('detail', ''), 'basis': r.get('basis', '')})

    # 7 the counts
    phases = [x[2] for x in final.get('attempts', [])]
    r_, c_, n_ = sum(p in LIVE_R for p in phases), sum(p in LIVE_C for p in phases), phases.count('NO_EFFECT')
    if list(final.get('live', [])) != [r_, c_, n_]:
        bad(7, 'the recorded counts do not match the attempts\' phases')
    if isinstance(k, int) and r_ + c_ > k:
        bad(7, f'more runs ({r_ + c_}) than the ceiling ({k})')

    # 8 acknowledgements
    by_aid = {a.get('aid'): a for a in attempts}
    for ack in acks:
        a = by_aid.get(ack.get('aid'))
        msg = canonical({'root': root, 'aid': ack.get('aid'), 'outcome': ack.get('outcome'), 'disposition': ack.get('disposition'), 'time': ack.get('time')}).encode()
        if a is None or ack.get('outcome') != a.get('outcome'):
            bad(8, f'{ack.get("aid")}: acknowledges a run that is not in this record, or with another outcome')
        elif ack.get('signer') != ekey or not signed_by(ekey, ack.get('signature', ''), msg):
            bad(8, f'{ack.get("aid")}: not signed by the engineer\'s key')

    titles = {1: 'record signature', 2: 'baseline, controls and anchor', 3: 'audit chain', 4: 'witness receipts', 5: 'runs bound to baseline and design',
              6: 'gate reports and re-derived verdicts', 7: 'counts', 8: 'acknowledgements'}
    checks = [(n, titles[n], not problems[n], '; '.join(problems[n][:3]) + (f' (+{len(problems[n]) - 3} more)' if len(problems[n]) > 3 else '')) for n in range(1, 9)]
    ok = all(c[2] for c in checks)
    acked = {a.get('aid') for a in acks}
    met = [r for r in rows_out if r['outcome'] == 'PASS']
    for r in rows_out:
        r['acknowledged'] = r['aid'] in acked
    released = None
    if design is not None:
        h = sha(canonical(design))
        released = {'design_sha256': h, 'met': any(r['design_sha256'] == h for r in met), 'seen': any(r['design_sha256'] == h for r in rows_out)}
    summary = {'requirement': req, 'engineer': (card.get('responsible_engineer') or {}).get('name'), 'baseline_sha256': b_hash, 'baselined_at': card.get('baselined_at'),
               'criteria': card['criteria'], 'load_case': card.get('load_case'), 'check': card['check'], 'supersedes': card.get('supersedes'),
               'runs': rows_out, 'official_runs': len(rows_out), 'met': len(met), 'not_met': sum(r['outcome'] == 'FAIL' for r in rows_out),
               'unknown': sum(r['outcome'] not in ('PASS', 'FAIL') for r in rows_out), 'open': sum(1 for r in rows_out if r['outcome'] != 'PASS' and not r['acknowledged']),
               'status': 'DECLARED CHECK MET' if ok and met else 'NOT VERIFIED', 'met_designs': [r['design_sha256'] for r in met], 'released': released,
               'as_of': as_of, 'keys_pinned': pinned, 'receipts': n_receipts, 'audit_rows': len(audit)}
    return ok, checks, summary


def render(ok: bool, checks: list, s: dict) -> str:
    L = [f"  {'ok  ' if good else 'FAIL'} {n}  {title}" + (f': {detail}' if detail else '') for n, title, good, detail in checks]
    if not s:
        return '\n'.join(L + ['', 'FAILED: do not rely on this record.'])
    req = s['requirement']
    L += ['', f"  {req.get('id')} rev {req.get('revision')}: {req.get('title')}", f"  \"{req.get('statement')}\"",
          f"  baselined {s['baselined_at']} by {s['engineer']}.  Baseline {s['baseline_sha256'][:16]}…   Record as of {s['as_of'].get('time')}, sequence number {s['as_of'].get('seq')}."]
    if s['supersedes']:
        sp = s['supersedes']
        L.append(f"  CHANGED AFTER THE EVENT: this baseline replaced {sp.get('baseline_sha256', '')[:16]}… (rev {sp.get('revision', '?')}) after {sp.get('official_runs', '?')} official runs "
                 f"on it, of which {sp.get('not_met', '?')} did not meet the requirement.  Reason given by the engineer: {sp.get('reason')}")
    for c in s['criteria']:
        L.append(f"  limit: {c['quantity']} {'at most' if c['comparison'] == '<=' else 'at least'} {c['limit']} {c['units']}")
    L += ['', f"  Official runs through the service: {s['official_runs']}.  Met {s['met']}, not met {s['not_met']}, unknown {s['unknown']}.  Awaiting the engineer's disposition: {s['open']}."]
    for r in s['runs']:
        what = '; '.join(f"{c['id']} {c['achieved']} vs limit {c['limit']} {c['units']}" for c in r['criteria'] if c.get('achieved') is not None) or r['detail']
        tail = '' if r['outcome'] == 'PASS' else ('   acknowledged' if r['acknowledged'] else '   OPEN')
        L.append(f"    {r['aid']}  design {str(r['design_sha256'])[:10]}…  {r['outcome']:<11} {r['reason_code'] or '':<24} {what}{tail}")
    L.append('')
    if not ok:
        L.append('FAILED: do not rely on this record.')
        return '\n'.join(L)
    L.append('RECORD VERIFIED against the keys given.' if s['keys_pinned'] else 'RECORD CONSISTENT, but the keys were read from the record itself, so this does not show who made it.  Give the keys to verify.')
    if s['status'] == 'DECLARED CHECK MET':
        L.append(f"STATUS: DECLARED CHECK MET, for design {', '.join(h[:16] + '…' for h in s['met_designs'])} only, after {s['official_runs']} official runs ({s['not_met']} not met, {s['unknown']} unknown).")
    else:
        L.append('STATUS: NOT VERIFIED.  No design has met the declared check against this baseline.')
    if s['released'] is not None:
        rel = s['released']
        L.append(f"Released design {rel['design_sha256'][:16]}…: " + ('this is a design the record shows as meeting the declared check.' if rel['met'] else
                 ('NOT VERIFIED.  The record shows this design was run and did not meet the check.' if rel['seen'] else 'NOT VERIFIED.  This design does not appear in the record.')))
    L += ['', f"This says what the declared check ({s['check'].get('id')} v{s['check'].get('version')}, written by {s['check'].get('author')}, reviewed by {s['check'].get('reviewed_by')}) returned against the baselined limits.",
          'It does not say the check is correct, the requirement is complete, or the design is safe.',
          'The check does not cover: ' + '; '.join(s['check'].get('stated_limits') or []) + '.',
          'A record is a statement as of its sequence number.  Ask the responsible engineer for the current one.']
    return '\n'.join(L)


def main():
    ap = argparse.ArgumentParser(description='Check a verification record offline.')
    ap.add_argument('record'); ap.add_argument('--keys', help='a JSON file: {"witness": HEX, "gate": HEX, "engineer": HEX}')
    ap.add_argument('--witness-key', action='append'); ap.add_argument('--gate-key'); ap.add_argument('--engineer-key')
    ap.add_argument('--design', help='a released design file to compare with the record'); ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    with open(a.record) as f:
        record = json.load(f)
    keys = None
    if a.keys:
        with open(a.keys) as f:
            keys = json.load(f)
    elif a.witness_key or a.gate_key or a.engineer_key:
        if not (a.witness_key and a.gate_key and a.engineer_key):
            ap.error('give all three of --witness-key, --gate-key and --engineer-key, or none')
        keys = {'witness': a.witness_key, 'gate': a.gate_key, 'engineer': a.engineer_key}
    design = None
    if a.design:
        with open(a.design) as f:
            design = json.load(f)
    ok, checks, s = verify(record, keys, design)
    if a.json:
        print(json.dumps({'verified': ok, 'checks': [{'check': n, 'title': t, 'ok': o, 'detail': d} for n, t, o, d in checks], 'summary': s}, indent=1))
    else:
        print(render(ok, checks, s))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
