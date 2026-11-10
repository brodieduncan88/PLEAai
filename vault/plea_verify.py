#!/usr/bin/env python3
"""Check a PLEA Holdout Vault report offline.

    plea_verify.py REPORT.json --witness-key HEX --gate-key HEX --report-key HEX      (keys from the owner, by another channel)
    plea_verify.py REPORT.json --keys KEYS.json                                       ({"witness": HEX, "gate": HEX, "report": HEX})
    plea_verify.py REPORT.json                                                        (keys read from the report: consistency only)

This file stands alone: the Python standard library and the `cryptography` package, nothing from the vault or the
gateway, and no network or database.  It recomputes every hash and checks every signature in the report:

  1  the report's own signature, by the owner's report key, over everything else in it; the keys the report names
     are the keys given;
  2  the manifest hashes to the value the report names; the provisioning record hashes to itself and names this budget;
  3  the audit chain recomputes from that record, row by row, and ends at the report's as-of sequence number;
  4  each witness receipt is signed by the witness, is for this budget and attempt, and carries the chain hash of the
     audit row at its sequence number; the intent and crossing receipts bind the attempt's nonce;
  5  each attempt is bound to the arguments the report gives for it (submission hash, manifest hash, submitter): the
     request key, the attempt id and the nonce all recompute from them and the gate key; and the attempts listed are
     exactly the attempts in the last chained state;
  6  each gate report is signed by the gate host and matches its attempt; an EFFECT's result hashes to the digest the
     gate signed, names this manifest and this submission, and holds a score of the manifest's form and nothing else;
     NO_EFFECT, UNKNOWN and PENDING attempts carry no score;
  7  charged attempts, less refunds, do not exceed the budget.

It prints one line per check and a summary, and exits 0 only if every check passed.

What it cannot tell you.  The owner holds the witness, gate and report keys, so an owner who rewrote the whole record
would produce a report that verifies: the owner is trusted.  And a report is a statement as of its sequence number: an
older report omits later attempts and still verifies.  Get the report from the owner, not from the submitter, and note
the as-of line.  Without keys given on the command line the keys are read from the report itself, which shows only that
the report is consistent, not who made it.
"""
import argparse
import hashlib
import json
import re
import sys

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

FORMAT = 'plea-vault-report/1'
PROVISION_FIELDS = ('record', 'seq', 'root', 'k', 'm', 'issuer', 'contract', 'release', 'created_at')
LIVE_R = ('RESERVING', 'RESERVED', 'TOKEN')
LIVE_C = ('INTENT_PENDING', 'CONSUMED', 'NO_EFFECT', 'EFFECT', 'INDETERMINATE')
RESULT_KEYS = {'score', 'metric', 'decimals', 'rows', 'submission_sha256', 'manifest_sha256'}


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def signed_by(public_hex: str, signature_hex: str, message: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex)).verify(bytes.fromhex(signature_hex), message)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def chain_hash(prev_hash, row) -> str:
    return sha(prev_hash + canonical({k: row[k] for k in ('seq', 'op', 'kind', 'code', 'observation')}))


def provision_hash(record) -> str:
    return sha(record['prev_hash'] + canonical({f: record[f] for f in PROVISION_FIELDS}))


def receipt_message(r) -> bytes:
    return canonical({k: r.get(k) for k in ('root', 'aid', 'seq', 'op', 'kind', 'code', 'hash', 'binding')}).encode()


def evidence_message(e) -> bytes:
    return canonical({k: e.get(k) for k in ('kind', 'root', 'aid', 'nonce', 'claim', 'result_digest')}).encode()


def request_key(arguments) -> str:
    return 'score:' + sha(canonical(arguments))[:24]


def attempt_id(key: str) -> str:
    return 'a-' + sha(key)[:16]


def nonce_for(root, aid, executor, tool, arguments) -> str:
    return 'n-' + sha(canonical({'root': root, 'aid': aid, 'executor': executor, 'tool': tool, 'arguments': arguments}))[:40]


def _keys(pinned) -> tuple:
    return (pinned,) if isinstance(pinned, str) else tuple(pinned or ())


def outcome_of(phase, claims) -> str:
    if phase in ('EFFECT', 'NO_EFFECT'):
        return phase
    if phase in ('RESERVING', 'RESERVED', 'TOKEN', 'INTENT_PENDING'):
        return 'PENDING'
    if phase == 'CONSUMED':
        return 'UNKNOWN' if 'UNKNOWN' in claims else 'PENDING'
    return phase


def verify(report: dict, keys: dict | None = None) -> tuple[bool, list, dict]:
    """(every check passed, [(number, title, ok, detail)], summary).  keys: {'witness', 'gate', 'report'}; None reads the report's."""
    checks, problems = [], {n: [] for n in range(1, 8)}
    def bad(n, msg):
        problems[n].append(msg)
    pinned = keys is not None
    try:
        keys = keys or report['keys']
        wkeys, gkey, rkey = _keys(keys['witness']), keys['gate'], keys['report']
        body = {k: v for k, v in report.items() if k != 'signature'}
        root, manifest, prov, audit, attempts = report['root'], report['manifest'], report['provisioning'], report['audit'], report['attempts']
        as_of, sig = report['as_of'], report['signature']
    except (KeyError, TypeError) as exc:
        return False, [(0, 'the report has the expected shape', False, f'missing {exc}')], {}

    # 1 the report's signature
    if report.get('format') != FORMAT:
        bad(1, f'format is {report.get("format")!r}, not {FORMAT!r}')
    if sig.get('signer') != rkey:
        bad(1, 'signed by a key other than the report key')
    elif not signed_by(rkey, sig.get('signature', ''), canonical(body).encode()):
        bad(1, 'bad signature: the report was changed after it was signed')
    named = report.get('keys') if isinstance(report.get('keys'), dict) else {}
    if not set(_keys(named.get('witness'))) <= set(wkeys) or not _keys(named.get('witness')) or named.get('gate') != gkey or named.get('report') != rkey:
        bad(1, 'the report names keys other than the ones given')

    # 2 manifest and provisioning record
    m_hash = sha(canonical(manifest))
    if m_hash != report.get('manifest_sha256'):
        bad(2, 'the manifest does not hash to manifest_sha256')
    if root != f"{manifest.get('holdout')}/{report.get('submitter')}" or report.get('holdout') != manifest.get('holdout'):
        bad(2, 'the budget is not named HOLDOUT/SUBMITTER for this manifest and submitter')
    if not isinstance(prov, dict) or any(f not in prov for f in PROVISION_FIELDS + ('prev_hash', 'hash')):
        bad(2, 'no provisioning record'); prov = None
    elif provision_hash(prov) != prov['hash']:
        bad(2, 'the provisioning record does not hash to itself')
    elif prov['root'] != root:
        bad(2, 'the provisioning record is for another budget')
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

    # 5 attempts are the chained state's attempts, bound to their arguments
    listed = [[a.get('aid'), a.get('request_key'), a.get('phase'), a.get('nonce')] for a in attempts]
    chained = [[x[0], x[1], x[2], x[3]] for x in final.get('attempts', [])]
    if sorted(listed, key=str) != sorted(chained, key=str):
        bad(5, 'the attempts listed are not the attempts in the last chained state')
    for a in attempts:
        aid, args = a.get('aid'), a.get('arguments')
        if not isinstance(args, dict):
            bad(5, f'{aid}: no arguments given, so the submission it was bound to cannot be checked'); continue
        if set(args) != {'submission_sha256', 'manifest_sha256', 'submitter'}:
            bad(5, f'{aid}: unexpected arguments')
        if request_key(args) != a.get('request_key') or attempt_id(a.get('request_key') or '') != aid:
            bad(5, f'{aid}: the request key or attempt id does not recompute from the arguments')
        if args.get('manifest_sha256') != m_hash or args.get('submitter') != report.get('submitter'):
            bad(5, f'{aid}: bound to another manifest or submitter')
        if a.get('nonce') is not None and nonce_for(root, aid, gkey, 'score', args) != a['nonce']:
            bad(5, f'{aid}: the nonce does not bind these arguments to the gate key')

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
                bad(4, f'{aid}: no {op} receipt for an attempt in phase {a.get("phase")}')

    # 6 gate reports and results
    decimals = manifest.get('decimals')
    score_form = re.compile(r'^(0|1)$' if decimals == 0 else r'^(0\.\d{%d}|1\.0{%d})$' % (decimals, decimals)) if isinstance(decimals, int) and decimals >= 0 else None
    rows_out = []
    for a in attempts:
        aid, args, result, claims = a.get('aid'), a.get('arguments') or {}, a.get('result'), []
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
        want = outcome_of(a.get('phase'), claims)
        if a.get('outcome') != want:
            bad(6, f'{aid}: the report says {a.get("outcome")}, the phase and gate reports say {want}')
        if a.get('phase') in ('EFFECT', 'NO_EFFECT') and a.get('phase') not in claims:
            bad(6, f'{aid}: phase {a.get("phase")} without a gate report claiming it')
        if want == 'EFFECT':
            digests = [i['evidence'].get('result_digest') for i in a.get('evidence') or [] if (i.get('evidence') or {}).get('claim') == 'EFFECT']
            if not isinstance(result, dict):
                bad(6, f'{aid}: scored, but no result is given')
            else:
                if sha(canonical(result)) not in digests:
                    bad(6, f'{aid}: the result does not hash to the digest the gate signed')
                if set(result) != RESULT_KEYS:
                    bad(6, f'{aid}: the result holds fields other than the six the contract allows')
                if result.get('manifest_sha256') != m_hash or result.get('submission_sha256') != args.get('submission_sha256'):
                    bad(6, f'{aid}: the result names another manifest or submission')
                if (result.get('metric'), result.get('decimals'), result.get('rows')) != (manifest.get('metric'), decimals, manifest.get('rows')):
                    bad(6, f'{aid}: the result does not follow the manifest\'s metric, decimals or row count')
                if score_form is None or not isinstance(result.get('score'), str) or not score_form.match(result['score']):
                    bad(6, f'{aid}: the score is not a number between 0 and 1 with {decimals} decimal places')
        elif result is not None:
            bad(6, f'{aid}: outcome {want} must carry no result')
        rows_out.append({'aid': aid, 'submission_sha256': args.get('submission_sha256'), 'outcome': a.get('outcome'),
                         'score': result.get('score') if isinstance(result, dict) and want == 'EFFECT' else None})

    # 7 budget arithmetic, from the phases in the last chained state
    phases = [x[2] for x in final.get('attempts', [])]
    r, c, n = sum(p in LIVE_R for p in phases), sum(p in LIVE_C for p in phases), phases.count('NO_EFFECT')
    if list(final.get('live', [])) != [r, c, n]:
        bad(7, 'the recorded counts do not match the attempts\' phases')
    credit = min(n, m) if isinstance(m, int) else 0
    charged = r + c - credit
    if not isinstance(k, int) or charged > k:
        bad(7, f'charged attempts ({charged}) exceed the budget ({k})')
    if isinstance(k, int) and isinstance(m, int) and c > k + m:
        bad(7, 'more attempts were admitted than the budget and allowance permit')

    titles = {1: 'report signature', 2: 'manifest and provisioning record', 3: 'audit chain', 4: 'witness receipts', 5: 'attempts bound to their submissions',
              6: 'gate reports and results', 7: 'budget arithmetic'}
    for num in range(1, 8):
        checks.append((num, titles[num], not problems[num], '; '.join(problems[num][:3]) + (f' (+{len(problems[num]) - 3} more)' if len(problems[num]) > 3 else '')))
    refused = sum(1 for row in audit if row.get('kind') == 'DENIED' and row.get('op', [None])[0] == 'RESERVE')
    summary = {'holdout': report.get('holdout'), 'submitter': report.get('submitter'), 'allowed': k, 'replacement': m, 'used': charged, 'refunded': credit,
               'remaining': max(0, k - charged) if isinstance(k, int) else None, 'refused_requests': refused, 'audit_rows': len(audit), 'receipts': n_receipts,
               'as_of': as_of, 'attempts': rows_out, 'keys_pinned': pinned, 'certificate_sha256': report.get('certificate_sha256')}
    return all(ok for _, _, ok, _ in checks), checks, summary


def main():
    ap = argparse.ArgumentParser(description='Check a PLEA Holdout Vault report offline.')
    ap.add_argument('report'); ap.add_argument('--keys', help='a JSON file: {"witness": HEX, "gate": HEX, "report": HEX}')
    ap.add_argument('--witness-key', action='append'); ap.add_argument('--gate-key'); ap.add_argument('--report-key')
    ap.add_argument('--json', action='store_true', help='print the result as JSON')
    a = ap.parse_args()
    with open(a.report) as f:
        report = json.load(f)
    keys = None
    if a.keys:
        with open(a.keys) as f:
            keys = json.load(f)
    elif a.witness_key or a.gate_key or a.report_key:
        if not (a.witness_key and a.gate_key and a.report_key):
            ap.error('give all three of --witness-key, --gate-key and --report-key, or none')
        keys = {'witness': a.witness_key, 'gate': a.gate_key, 'report': a.report_key}
    ok, checks, s = verify(report, keys)
    if a.json:
        print(json.dumps({'verified': ok, 'checks': [{'check': n, 'title': t, 'ok': o, 'detail': d} for n, t, o, d in checks], 'summary': s}, indent=1))
        sys.exit(0 if ok else 1)
    for n, title, good, detail in checks:
        print(f"  {'ok  ' if good else 'FAIL'} {n}  {title}" + (f': {detail}' if detail else ''))
    if s:
        print(f"\n  {s['holdout']} / {s['submitter']}   as of {s['as_of'].get('time')}, sequence number {s['as_of'].get('seq')}")
        print(f"  attempts allowed {s['allowed']}, used {s['used']}, refunded {s['refunded']}, remaining {s['remaining']};  requests refused: {s['refused_requests']}")
        for row in s['attempts']:
            print(f"    {str(row['submission_sha256'])[:16]}…  {row['outcome']:<9} {row['score'] or ''}")
    if not ok:
        print('\nFAILED: do not rely on this report.')
    elif s.get('keys_pinned'):
        print('\nVERIFIED against the keys given.  This is the record as of the sequence number above; ask the owner for the current one.')
    else:
        print('\nCONSISTENT, but the keys were read from the report itself, so this does not show who made it.  Give the owner\'s keys to verify.')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
