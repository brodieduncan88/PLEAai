#!/usr/bin/env python3
"""Check a verification record offline.

    check_record.py RECORD.json --witness-key HEX --gate-key HEX --engineer-key HEX   (keys obtained separately from the record)
    check_record.py RECORD.json --keys KEYS.json                                      ({"witness": HEX, "gate": HEX, "engineer": HEX})
    ... --courier-key HEX --mailbox-key HEX   (or "courier" and "mailbox" in KEYS.json): the keys of a record's notices delivered
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
  8  each acknowledgement is signed by the engineer and names a run in this record;
  9  the witness's checkpoint inside the record, if it has one (Amendment 10): signed by a witness key, for this budget,
     and saying that the chain's head after the record's last decision is the record's head;
 10  the notices delivered, if the record carries any (Amendment 11): each notice is signed by the courier's key, names a
     decision of this record's chain with its hash, and says what this record's chain, gate reports and verdict say of
     that run at that decision: its outcome, the digest of its verdict, the reason code and detail it quotes, and its
     words, which are made again here and compared; each receipt is signed by the engineer's mailbox key and names that notice.  With keys given
     separately but none for the courier and the mailbox, the notices are not checked, and the record is judged without them.

It then says which runs that call for a notice to the engineer (FAIL, UNKNOWN, INTERRUPTED; and INVALID or REFUNDED,
which must never happen) have a notice delivered, with the mailbox's signed receipt, and which have none.  A record built
before a notice was delivered has none for it.  --require-delivery makes the exit status 1 unless every such run has one.

With --checkpoint FILE it also says whether the record is current (Amendment 10).  The file is a checkpoint the witness
signed, obtained separately from the record: from the witness, or from someone who keeps the witness's checkpoints.  The
record is CURRENT if the checkpoint's chain is exactly the record's; SUPERSEDED if the chain has gone on since, and the
checkpoint says the record's head is where that chain was; FORKED if the two disagree about the same decision.  --max-age
SECONDS is how old the checkpoint may be by this computer's clock (an hour unless given); one dated in the future is not
used.  --nonce N refuses one that does not sign back N.  CURRENT therefore means: current when the checkpoint was made, at
most that long ago.  An old checkpoint replayed inside that time still reads CURRENT; to rule that out, ask the witness
with a nonce of your own choosing and give it here.  The keys must be given separately.  The exit status is 0 only if the
record verifies and, where a checkpoint was given, it is CURRENT.

It then states the status.  NOT VERIFIED is the default: the status is "declared check met" only if a listed run's
verdict is PASS, and only for that exact design.

What it cannot tell you.  Whether the check is correct, whether the requirement is complete, whether the design sent
is the part that was built, or whether work was done outside the service.  One party holds the witness, gate and
engineer keys in the demonstration, so that party is trusted.  A record is a statement as of its sequence number: an
older record omits later runs and still verifies; only a checkpoint obtained separately says whether it is current, and
that is the witness's word, as old as the checkpoint.  Without keys given separately, the keys are read from the record
itself, which shows only that the record is consistent, not who made it.
"""
import argparse
import calendar
import decimal
import hashlib
import json
import re
import sys
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

FORMAT, CARD_FORMAT, VERDICT_FORMAT = 'verification-record/1', 'verification-baseline/1', 'verification-verdict/1'
PROVISION_FIELDS = ('record', 'seq', 'root', 'k', 'm', 'issuer', 'contract', 'release', 'created_at')
LIVE_R = ('RESERVING', 'RESERVED', 'TOKEN')
LIVE_C = ('INTENT_PENDING', 'CONSUMED', 'NO_EFFECT', 'EFFECT', 'INDETERMINATE')
REASONS = {'MET': 'PASS', 'LIMIT_NOT_MET': 'FAIL', 'DESIGN_OUTSIDE_BASELINE': 'FAIL', 'BASELINE_MISMATCH': 'UNKNOWN', 'CHECK_ERROR': 'UNKNOWN',
           'CHECK_OUTPUT_INVALID': 'UNKNOWN', 'RESULT_IMPLAUSIBLE': 'UNKNOWN'}
CHECKPOINT_FIELDS = ('statement', 'root', 'seq', 'head', 'business', 'witness', 'time', 'nonce', 'at', 'head_at')
NOTICE_FIELDS = ('statement', 'root', 'aid', 'request_key', 'outcome', 'reason_code', 'detail', 'result_digest', 'seq', 'head', 'time', 'courier', 'text')
RECEIPT_FIELDS = ('statement', 'notice', 'root', 'aid', 'outcome', 'mailbox', 'time')
RUN_NOTICES = ('FAIL', 'UNKNOWN', 'INTERRUPTED', 'INDETERMINATE', 'INVALID', 'REFUNDED', 'UNVERIFIED', 'NO_OUTCOME')   # a courier's notices of a run (Amendment 11)
ALARMS = ('COURIER_STOPPED', 'COURIER_BLOCKED')                                         # a courier's notices about itself: of no run, never in a record
NOTICE_OUTCOMES = RUN_NOTICES + ALARMS
DUE = ('FAIL', 'UNKNOWN', 'INTERRUPTED', 'INDETERMINATE', 'INVALID', 'REFUNDED')        # a run's outcome in a record that calls for a notice
HEADLINES = {'FAIL': 'DECLARED CHECK NOT MET (FAIL)', 'UNKNOWN': 'NO VERDICT: THE CHECK DID NOT DECIDE (UNKNOWN)',
             'INTERRUPTED': 'THE RUN WAS INTERRUPTED: ADMITTED AND COUNTED, WITH NO VERDICT',
             'INDETERMINATE': 'THE RUN WAS MADE INDETERMINATE BY THE CONTROL PLANE: FROZEN AND COUNTED, WITH NO VERDICT RECORDED',
             'INVALID': 'THE GATE SIGNED A RESULT THAT HAS NO VERDICT', 'REFUNDED': 'THE RUN WAS REFUNDED, WHICH A VERIFICATION RUN MUST NEVER BE',
             'UNVERIFIED': 'THE STORED RESULT DOES NOT MATCH THE GATE\'S SIGNATURE', 'NO_OUTCOME': 'A RUN WAS ADMITTED AND HAS NO OUTCOME',
             'COURIER_STOPPED': 'THE COURIER HAS STOPPED READING THIS BUDGET: WHAT THE WITNESS SAID CANNOT BE BELIEVED',
             'COURIER_BLOCKED': 'THE COURIER CANNOT READ THIS BUDGET FROM THE WITNESS'}
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


def checkpoint_problems(cp, wkeys, root) -> list:
    """What is wrong with a checkpoint as a statement by a pinned witness about this budget.  (Amendment 10.)"""
    if not isinstance(cp, dict):
        return ['it is not a checkpoint']
    wkeys, out = _keys(wkeys), []
    if cp.get('statement') != 'CHECKPOINT' or set(cp) != set(CHECKPOINT_FIELDS) | {'signer', 'signature'}:
        out.append('it is not a checkpoint, or has fields a checkpoint does not have')
    signer = cp.get('signer')
    if not isinstance(signer, str) or signer not in wkeys or not signed_by(signer, cp.get('signature', ''), canonical({k: cp.get(k) for k in CHECKPOINT_FIELDS}).encode()):
        out.append('it is not signed by a witness key given')
    if cp.get('root') != root:
        out.append('it is for another budget')
    seq, at = cp.get('seq'), cp.get('at')
    if type(seq) is not int or seq < 0 or not isinstance(cp.get('head'), str) or checkpoint_time(cp) is None:
        out.append('its sequence number, head or time is not readable')
    elif (at is None) != (cp.get('head_at') is None) or (at is not None and (type(at) is not int or not 0 <= at <= seq or not isinstance(cp.get('head_at'), str) or (at == seq and cp.get('head_at') != cp.get('head')))):
        out.append('what it says of an earlier decision is not readable, or contradicts its own head')
    return out


def run_outcome(phase, evidence, result, gate_keys, root, aid, nonce) -> str:
    """What a run's chained phase, the gate's reports and the stored result say of it (Amendment 11), as a courier and this
    checker both read them.  evidence: [{'seq', 'evidence'}]; only reports signed by a gate key given, for this budget,
    attempt and nonce, count.  UNVERIFIED: a run the gate signed an effect for, whose result (if any is given) does not hash to
    the digest the gate signed.
    NO_OUTCOME: its intent accepted, or admitted and crossed, with no verdict and no report that the gate does not know.
    INDETERMINATE: the control plane made it so (a re-registration); it is counted and frozen, with no verdict."""
    gkeys, claims, digests = _keys(gate_keys), [], []
    for item in evidence or []:
        e = item.get('evidence') if isinstance(item, dict) else None
        if not isinstance(e, dict) or e.get('kind') != 'EFFECT_REPORT' or e.get('signer') not in gkeys or not signed_by(e['signer'], e.get('signature', ''), evidence_message(e)):
            continue
        if e.get('root') != root or e.get('aid') != aid or e.get('nonce') != nonce:
            continue
        claims.append(e.get('claim'))
        if e.get('claim') == 'EFFECT':
            digests.append(e.get('result_digest'))
    if phase == 'NO_EFFECT':
        return 'REFUNDED'
    if phase == 'EFFECT':
        if not isinstance(result, dict) or sha(canonical(result)) not in digests:
            return 'UNVERIFIED'
        return result.get('verdict') if result.get('verdict') in ('PASS', 'FAIL', 'UNKNOWN') else 'INVALID'
    if phase == 'CONSUMED':
        return 'INTERRUPTED' if 'UNKNOWN' in claims else 'NO_OUTCOME'
    if phase == 'INTENT_PENDING':
        return 'NO_OUTCOME'
    return 'PENDING' if phase in LIVE_R else str(phase)


def notice_detail(result):
    """What a notice quotes of a result's detail: no control characters, at most 400 characters; None if there is none."""
    d = ''.join(ch if ch >= ' ' and ch != '\x7f' else ' ' for ch in str((result or {}).get('detail') or ''))[:400] if isinstance(result, dict) else ''
    return d or None


WHY = {'INTERRUPTED': 'The gate signed that it does not know the outcome: the run is counted and will not be run again.  If the gate learns the verdict later, another notice follows.',
       'INDETERMINATE': 'The control plane re-registered the budget: the run is frozen and counted, and the witness records no verdict for it.',
       'NO_OUTCOME': 'It was started, or admitted and crossed, and the witness holds no outcome for it; the courier has seen it so for longer than it waits.',
       'UNVERIFIED': 'The gate signed that the check ran, but for longer than it waits the courier has found no stored result that hashes to the digest the gate signed.',
       'REFUNDED': 'The witness recorded the run as refunded.'}


def notice_numbers(result) -> str:
    """A verdict's achieved and required values, as a notice gives them."""
    out = []
    for c in (result.get('criteria') if isinstance(result, dict) else None) or []:
        if isinstance(c, dict) and c.get('achieved') is not None:
            cmp_ = c.get('comparison'); word = {'<=': 'at most', '>=': 'at least'}.get(cmp_, str(cmp_)) if isinstance(cmp_, str) else str(cmp_)
            out.append(f"{c.get('id')} achieved {c.get('achieved')}, required {word} {c.get('limit')} {c.get('units') or ''}".strip())
    return '; '.join(out)[:2000]


def notice_text(outcome, aid, root, result, seq, courier) -> str:
    """The words of a courier's notice of a run: made from what the notice states and the verdict it names, so a record's
    checker can make them again and compare.  (Amendment 11.)"""
    r = result if isinstance(result, dict) else {}
    if r.get('reason_code'):
        numbers, detail = notice_numbers(r), notice_detail(r)
        why = f"Reason: {r.get('reason_code')}.  " + (f'{numbers}.  ' if numbers else '') + (detail or '')
    else:
        why = WHY.get(outcome, '')
    return (f"{HEADLINES[outcome]}\nRun {aid} on budget {root}.\n{why}\n"
            f"This notice was made by the courier {courier} from the witness's chain at decision {seq} and the gate's signed reports.  "
            'The verification service did not write it.  It does not say the check is correct.')


def delivery_problem(d, root, audit, attempts_by_aid, gate_key, courier_keys, mailbox_keys, chain_ok: bool = True):
    """(None, notice) if a delivery is a true courier notice of a run of this record, with the mailbox's receipt for it, and
    says what this record says of that run at the decision it names; otherwise (what is wrong, notice).  (Amendment 11.)"""
    n, rc = (d.get('notice'), d.get('receipt')) if isinstance(d, dict) else (None, None)
    msgs = notice_problems(n, courier_keys)
    if msgs:
        return f'the notice: {msgs[0]}', n
    msgs = receipt_problems(rc, mailbox_keys, n)
    if msgs:
        return f'the receipt: {msgs[0]}', n
    a, seq = attempts_by_aid.get(n['aid']), n['seq']
    if n['root'] != root or a is None or n['outcome'] in ALARMS:
        return 'the notice is of a run that is not in this record', n
    if not chain_ok or not 1 <= seq <= len(audit) or audit[seq - 1]['hash'] != n['head']:
        return 'the notice names a decision that is not in this record\'s chain', n
    then = next((x for x in audit[seq - 1]['observation'].get('attempts', []) if x[0] == n['aid']), None)
    if then is None:
        return 'the run was not in the chain at the decision the notice names', n
    ev = [e for e in a.get('evidence') or [] if isinstance(e.get('seq'), int) and e['seq'] <= seq]
    res = a.get('result') if then[2] == 'EFFECT' and n['result_digest'] is not None else None   # a notice with no digest vouches for no result: UNVERIFIED
    said = run_outcome(then[2], ev, res, gate_key, root, n['aid'], then[3])
    if n['outcome'] != said or n['request_key'] != a.get('request_key') or n['result_digest'] != (sha(canonical(res)) if isinstance(res, dict) else None):
        return f'the notice says {n["outcome"]} of {n["aid"]}; this record says {said} at decision {seq}', n
    if n['reason_code'] != (res or {}).get('reason_code') or n['detail'] != notice_detail(res) or n['text'] != notice_text(n['outcome'], n['aid'], root, res, seq, n['courier']):
        return f'what the notice gives a person to read is not what this record says of {n["aid"]}', n
    return None, n


def kept_deliveries(body: dict, keys: dict) -> list:
    """The deliveries of a record body that check 10 would take, once each.  For the record's builder."""
    by_aid = {a.get('aid'): a for a in body.get('attempts') or []}
    out, seen = [], set()
    for d in body.get('deliveries') or []:
        why, n = delivery_problem(d, body['root'], body['audit'], by_aid, keys['gate'], keys.get('courier'), keys.get('mailbox'))
        if why is None and notice_digest(n) not in seen:
            seen.add(notice_digest(n)); out.append({'notice': n, 'receipt': d['receipt']})
    return out


def _hex(value, n: int) -> bool:
    return isinstance(value, str) and len(value) == n and all(c in '0123456789abcdef' for c in value)


def notice_digest(n) -> str:
    """The digest a mailbox's receipt names: of the whole signed notice."""
    return sha(canonical(n))


def notice_problems(n, courier_keys) -> list:
    """What is wrong with a notice as one made by a courier key given.  (Amendment 11.)"""
    if not isinstance(n, dict):
        return ['it is not a notice']
    out = []
    if n.get('statement') != 'NOTICE' or set(n) != set(NOTICE_FIELDS) | {'signer', 'signature'}:
        out.append('it is not a notice, or has fields a notice does not have')
    signer = n.get('signer')
    if not _hex(signer, 64) or not _hex(n.get('signature'), 128) or signer not in _keys(courier_keys) \
            or not signed_by(signer, n.get('signature', ''), canonical({k: n.get(k) for k in NOTICE_FIELDS}).encode()):
        out.append('it is not signed by a courier key given')
    if n.get('outcome') not in NOTICE_OUTCOMES or type(n.get('seq')) is not int or n.get('seq') < 0 or not isinstance(n.get('head'), str) \
            or not all(isinstance(n.get(k), str) for k in ('root', 'aid', 'courier', 'text')) or checkpoint_time(n) is None:
        out.append('its outcome, decision, head, names or time are not readable')
    return out


def receipt_problems(r, mailbox_keys, n) -> list:
    """What is wrong with a receipt as a mailbox's signed word that it holds notice n.  (Amendment 11.)"""
    if not isinstance(r, dict):
        return ['it is not a receipt']
    out = []
    if r.get('statement') != 'DELIVERED' or set(r) != set(RECEIPT_FIELDS) | {'signer', 'signature'}:
        out.append('it is not a receipt, or has fields a receipt does not have')
    signer = r.get('signer')
    if not _hex(signer, 64) or not _hex(r.get('signature'), 128) or signer not in _keys(mailbox_keys) \
            or not signed_by(signer, r.get('signature', ''), canonical({k: r.get(k) for k in RECEIPT_FIELDS}).encode()):
        out.append('it is not signed by a mailbox key given')
    if not isinstance(n, dict) or r.get('notice') != notice_digest(n) or any(r.get(k) != n.get(k) for k in ('root', 'aid', 'outcome')):
        out.append('it does not name this notice')
    if not isinstance(r.get('mailbox'), str) or checkpoint_time(r) is None:
        out.append('its mailbox or time is not readable')
    return out


def checkpoint_time(cp):
    """The checkpoint's time as seconds since 1970, or None."""
    try:
        return calendar.timegm(time.strptime(cp.get('time'), '%Y-%m-%dT%H:%M:%SZ'))
    except (TypeError, ValueError, AttributeError):
        return None


def record_head_at(record: dict, n: int):
    """The head of the record's own chain after decision n, or None if the record does not hold it."""
    try:
        if n == 0:
            return record['provisioning']['hash']
        row = record['audit'][n - 1]
        return row['hash'] if row['seq'] == n else None
    except (KeyError, IndexError, TypeError):
        return None


CLOCK_SKEW = 300.0        # seconds a checkpoint's time may be ahead of this computer's clock


def currency(record: dict, cp, witness_keys, now=None, max_age=None, nonce=None) -> tuple[str, str]:
    """(state, sentence): whether a record is current, by a checkpoint obtained separately from it.  (Amendment 10.)

    CURRENT              the checkpoint's chain ends where the record does, and the checkpoint is no older than max_age;
    CURRENT_AT           the same, but no max_age was given: the record was current when the checkpoint was made, and how
                         long ago that was is not judged.  An old checkpoint replayed with an old record reads like this;
    SUPERSEDED           the chain has gone on, and the checkpoint says the record's head is where the chain was;
    SUPERSEDED_UNPROVEN  the chain has gone on, and the checkpoint does not say what its head was at the record's point;
    FORKED               the checkpoint and the record give different heads for the same decision;
    OLDER                the checkpoint is from before the record and agrees with it as far as it goes: it says nothing more;
    STALE                it would be current, but the checkpoint is older than max_age;
    INVALID              the checkpoint cannot be used.

    Only CURRENT says the record is the latest, and only as of the checkpoint's time by the witness's clock.  The record is
    taken as given: verify it first."""
    try:
        root, seq, head = record['root'], record['as_of']['seq'], record['as_of']['head']
    except (KeyError, TypeError):
        return 'INVALID', 'the record has no as-of sequence number and head to compare'
    if type(seq) is not int or seq < 0 or not isinstance(head, str):
        return 'INVALID', 'the record has no as-of sequence number and head to compare'
    bad = checkpoint_problems(cp, witness_keys, root)
    if bad:
        return 'INVALID', 'the checkpoint cannot be used: ' + '; '.join(bad)
    if nonce is not None and cp.get('nonce') != nonce:
        return 'INVALID', 'the checkpoint does not sign back the nonce given, so it may have been made before it was asked for'
    if max_age is not None and not (isinstance(max_age, (int, float)) and 0 <= max_age < float('inf')):
        return 'INVALID', 'the age allowed is not a number of seconds'
    now = time.time() if now is None else now
    if not (isinstance(now, (int, float)) and now == now):
        return 'INVALID', 'the time now is not a number'
    age = now - checkpoint_time(cp)
    if age < -CLOCK_SKEW:
        return 'INVALID', f"the checkpoint is dated {cp['time']}, which is in the future by this computer's clock: one of the two clocks is wrong, and its age cannot be judged"
    when = f"at {cp['time']} by the witness's clock"
    closed = '' if cp.get('business') == 'OPEN' and cp.get('witness') == 'ACTIVE' else \
        f"  The budget was then {cp.get('business')}" + (' and on hold' if cp.get('witness') != 'ACTIVE' else '') + ': it was superseded or closed, or is held, and takes no new runs as it stands.'
    forked = lambda n: ('FORKED', f"the witness's chain and the record's disagree at sequence number {n}: this record is not of the chain the witness holds")
    for n, h in ((cp['seq'], cp['head']), (cp.get('at'), cp.get('head_at'))):          # every head the checkpoint states, against the record's own chain
        if n is not None and n <= seq:
            mine = head if n == seq else record_head_at(record, n)
            if mine is not None and mine != h:
                return forked(n)
    if cp['seq'] < seq:
        return 'OLDER', f"the checkpoint is older than the record (sequence number {cp['seq']}, the record's is {seq}): it says nothing of whether the record is current"
    if cp['seq'] == seq:
        if max_age is None:
            return 'CURRENT_AT', f"the record was current {when}.  How long ago that was is not judged here: give the age allowed (--max-age) to have it judged." + closed
        if age > max_age:
            return 'STALE', f"the record was current {when}, which is more than {int(max_age)} seconds ago: get a newer checkpoint" + closed
        return 'CURRENT', f"the record was current {when}, {max(0, int(age))} seconds ago by this computer's clock: the witness's chain ended at this record's sequence number {seq}, with its head." + closed
    later = cp['seq'] - seq
    out_of_date = f"the record is out of date: {when} the witness's chain had {later} later decision{'s' if later != 1 else ''} (sequence number {cp['seq']}).  "
    if cp.get('at') == seq:
        return 'SUPERSEDED', out_of_date + 'The record is a true beginning of that chain.  Ask for the current record.' + closed
    return 'SUPERSEDED_UNPROVEN', out_of_date + 'This checkpoint does not say whether the record is a beginning of that chain.  Ask for the current record.' + closed


def request_key(arguments, legacy: bool = False) -> str:
    """Amendment 17 (D21): the whole hash.  legacy=True gives the form made before it, 96 bits, for records made then."""
    return 'verify:' + (sha(canonical(arguments))[:24] if legacy else sha(canonical(arguments)))


def attempt_id(key: str, legacy: bool = False) -> str:
    """Amendment 17 (D21): 'a2-' and the whole hash of the request key.  legacy=True gives the earlier 'a-' and 64 bits."""
    return 'a-' + sha(key)[:16] if legacy else 'a2-' + sha(key)


def identity_form(attempts) -> str | None:
    """Which form of request key and attempt identity a record's runs carry: 'current' (Amendment 17), 'legacy' (before it),
    or None when they are mixed, or are of neither form.  Only runs whose design the record gives are counted, since only their
    keys and identities can be recomputed; a run with no design (one made under another name by whoever holds the service's
    database role, or whose design the journal does not show) is listed and checked as before, and does not decide the form.
    A record with no such runs is 'current'.  One record is never read as both: a run of the earlier form beside one of the
    current form fails check 5."""
    attempts = [a for a in attempts if isinstance(a.get('arguments'), dict)]
    def form(a):
        aid, key = a.get('aid'), a.get('request_key')
        if not (isinstance(aid, str) and isinstance(key, str)):
            return None
        if re.fullmatch(r'a2-[0-9a-f]{64}', aid) and re.fullmatch(r'verify:[0-9a-f]{64}', key):
            return 'current'
        if re.fullmatch(r'a-[0-9a-f]{16}', aid) and re.fullmatch(r'verify:[0-9a-f]{24}', key):
            return 'legacy'
        return None
    forms = {form(a) for a in attempts}
    return 'current' if not forms else forms.pop() if len(forms) == 1 else None


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


def outside_reason(space, design) -> str:
    """Why a design is outside the baselined design space, in the checker's own words, worked out from the card and the
    design in the record.  (Amendment 3, 12 November 2026.)  The print of a record used to repeat the record's own
    reason, which before that date could hold a name or a text chosen by whoever sent the design.  The wording is the
    one baseline.py now signs: it names the baseline's parameters, counts the names that are not the baseline's, and
    repeats from the design only a number of at most 24 characters."""
    tail = '.  The check was not run.'
    if not isinstance(space, dict):
        return 'the design is outside the baselined design space' + tail
    if not isinstance(design, dict):
        return 'the design must be an object of parameters' + tail
    if set(design) != set(space):
        extra, missing = set(design) - set(space), sorted(set(space) - set(design))
        return ('the design must give exactly the baselined parameters' + (f'; {len(extra)} of the names sent {"is" if len(extra) == 1 else "are"} not in the baseline' if extra else '')
                + (f'; missing: {", ".join(missing)}' if missing else '') + tail)
    for name, rule in space.items():
        v = design[name]
        try:
            written = json.dumps(v) if not isinstance(v, bool) and isinstance(v, (int, float)) and v == v and v not in (float('inf'), float('-inf')) else None
        except ValueError:                                   # a whole number too long to be written at all
            written = None
        short = written is not None and len(written) <= 24
        if 'choice' in rule:
            if isinstance(v, bool) or not isinstance(v, (str, int)) or not any(type(v) is type(c) and v == c for c in rule['choice']):
                return (f'{name} = {v!r}' if short else f'the value sent for {name}') + f' is not on the approved list ({", ".join(map(str, rule["choice"]))})' + tail
        else:
            d = dec(v)
            if d is None or isinstance(v, str):
                return f'the value sent for {name} is not a number' + tail
            if not D(rule['min']) <= d <= D(rule['max']):
                shown = text(d) if len(text(d)) <= 24 else (written if short else None)
                return (f'{name} = {shown}' if shown is not None else f'the value sent for {name}') + f' is outside the baselined range {rule["min"]} to {rule["max"]}' + tail
    return 'the record says the design is outside the baselined design space' + tail


def recorded(words, limit: int = 300) -> str:
    """A reason as the record gives it, made fit to print on one line: the service's or the check's wording, cut."""
    words = '' if words is None else str(words)
    return ''.join(ch if ch.isprintable() else ' ' for ch in words[:limit]) + (f' (+{len(words) - limit} more characters)' if len(words) > limit else '')


def control_problems(card: dict, runs) -> list:
    """Amendment 17 (D20): what is wrong with a baseline's controls as run, by the rules of check 2.  Empty when the controls
    run are the controls declared, each gave its expected verdict, a failure and a pass are among them, and each one's
    recorded numbers give its recorded verdict against the card's limits.  The code is check 2's, moved here unchanged.
    verify_ctl.make_baseline asks it before anything is signed, stored or provisioned, so that no baseline is made whose own
    controls its record could not verify (a control whose value, written rounded, falls on the other side of its limit)."""
    out = []
    runs = runs or []
    declared = [(c.get('name'), c.get('expect')) for c in card.get('controls') or []]
    if [(c.get('name'), c.get('expect')) for c in runs] != declared or any(c.get('verdict') != c.get('expect') for c in runs):
        out.append('a control case did not give its expected verdict at baselining, or the controls run are not the controls declared')
    if not {'PASS', 'FAIL'} <= {c.get('verdict') for c in runs}:
        out.append('the controls do not include both a design that failed and one that passed')
    for c in runs:                                           # a control's recorded numbers must give its recorded verdict against the card's limits
        got = c.get('criteria') or []
        if [x.get('id') for x in got] != [x['id'] for x in card['criteria']] or any(x.get('limit') != b['limit'] for x, b in zip(got, card['criteria'])):
            out.append(f'control "{c.get("name")}": its criteria are not the card\'s'); continue
        values = [dec(x.get('achieved')) for x in got]
        if any(v is None for v in values):
            if REASONS.get(c.get('reason_code')) != 'UNKNOWN' or c.get('verdict') != 'UNKNOWN' or any(x.get('met') is not None for x in got):
                out.append(f'control "{c.get("name")}": no achieved value, but it is not recorded as UNKNOWN')
            continue
        mets = [(v <= D(b['limit'])) if b['comparison'] == '<=' else (v >= D(b['limit'])) for v, b in zip(values, card['criteria'])]
        if [x.get('met') for x in got] != mets or c.get('verdict') != ('PASS' if all(mets) else 'FAIL') or c.get('reason_code') != ('MET' if all(mets) else 'LIMIT_NOT_MET'):
            out.append(f'control "{c.get("name")}": its recorded verdict does not follow from its recorded numbers')
    return out


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
    problems = {n: [] for n in range(1, 11)}
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
    for problem in control_problems(card, env.get('controls_run')):      # Amendment 17 (D20): the rule baselining asks too
        bad(2, problem)
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
    ident = identity_form(attempts)                   # Amendment 17 (D21): one form of identity for the whole record
    if ident is None:
        bad(5, 'the runs\' request keys and attempt identities are not all of one form (the whole hash, or the 64-bit form made before 22 November 2026)')
    legacy = ident == 'legacy'
    for a in attempts:
        aid, args = a.get('aid'), a.get('arguments')
        if not isinstance(args, dict):
            if a.get('phase') == 'EFFECT':
                bad(5, f'{aid}: a run with a verdict gives no design, so it cannot be checked')
            continue
        if set(args) != {'baseline_sha256', 'design'}:
            bad(5, f'{aid}: unexpected arguments')
        if request_key(args, legacy) != a.get('request_key') or attempt_id(a.get('request_key') or '', legacy) != aid:
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

    # 9 the witness's checkpoint inside the record, if any (Amendment 10)
    cp = record.get('checkpoint')
    if cp is not None:
        for msg in checkpoint_problems(cp, wkeys, root):
            bad(9, msg)
        if not problems[9] and (type(cp.get('at')) is not int or cp.get('at') != as_of.get('seq') or cp.get('head_at') != as_of.get('head')):
            bad(9, 'it does not say that the chain\'s head after this record\'s last decision is this record\'s head')

    # 10 the notices delivered, if any (Amendment 11)
    deliveries, delivered, unchecked = record.get('deliveries'), {}, None
    ckeys, mkeys = _keys(keys.get('courier')), _keys(keys.get('mailbox'))
    if deliveries is not None and pinned and (not ckeys or not mkeys):
        unchecked = 'no courier and mailbox keys were given with the others'      # optional evidence, not checked: the rest of the record stands
    elif deliveries is not None:
        if pinned and (not set(_keys(named.get('courier'))) <= set(ckeys) or not set(_keys(named.get('mailbox'))) <= set(mkeys)):
            bad(10, 'the record names courier or mailbox keys other than the ones given')
        if not ckeys or not mkeys:
            bad(10, 'the record names no courier or mailbox key')
        elif not isinstance(deliveries, list):
            bad(10, 'the deliveries are not a list')
        else:
            for i, d in enumerate(deliveries, start=1):
                why, n = delivery_problem(d, root, audit, by_aid, gkey, ckeys, mkeys, chain_ok)
                if why is not None:
                    bad(10, f'delivery {i}: {why}'); continue
                delivered.setdefault(n['aid'], set()).add(n['outcome'])

    titles = {1: 'record signature', 2: 'baseline, controls and anchor', 3: 'audit chain', 4: 'witness receipts', 5: 'runs bound to baseline and design',
              6: 'gate reports and re-derived verdicts', 7: 'counts', 8: 'acknowledgements',
              9: 'witness checkpoint' if cp is not None else 'witness checkpoint (none in this record)',
              10: 'notices delivered (none in this record)' if deliveries is None else (f'notices delivered (not checked: {unchecked})' if unchecked else 'notices delivered')}
    checks = [(n, titles[n], not problems[n], '; '.join(problems[n][:3]) + (f' (+{len(problems[n]) - 3} more)' if len(problems[n]) > 3 else '')) for n in range(1, 11)]
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
               'criteria': card['criteria'], 'load_case': card.get('load_case'), 'check': card['check'], 'supersedes': card.get('supersedes'), 'alongside': card.get('alongside'), 'design_space': card.get('design_space'),
               'runs': rows_out, 'official_runs': len(rows_out), 'met': len(met), 'not_met': sum(r['outcome'] == 'FAIL' for r in rows_out),
               'unknown': sum(r['outcome'] not in ('PASS', 'FAIL') for r in rows_out), 'open': sum(1 for r in rows_out if r['outcome'] != 'PASS' and not r['acknowledged']),
               'status': 'DECLARED CHECK MET' if ok and met else 'NOT VERIFIED', 'met_designs': [r['design_sha256'] for r in met], 'released': released,
               'as_of': as_of, 'keys_pinned': pinned, 'receipts': n_receipts, 'audit_rows': len(audit),
               'identities': ident,          # Amendment 17 (D21): 'current', 'legacy' (64-bit, before 22 November 2026) or None (mixed)
               'checkpoint': ({k: cp.get(k) for k in ('seq', 'time', 'business', 'witness', 'at')} if isinstance(cp, dict) and not problems[9] else None),
               'delivery': None if deliveries is None or problems[10] else {'unchecked': unchecked, 'notices': len(deliveries) if isinstance(deliveries, list) else 0} if unchecked else {
                   'due': [{'aid': r['aid'], 'outcome': r['outcome'], 'delivered': r['outcome'] in delivered.get(r['aid'], ())} for r in rows_out if r['outcome'] in DUE],
                   'no_outcome': sorted(aid for aid, outs in delivered.items() if 'NO_OUTCOME' in outs), 'notices': len({notice_digest(d.get('notice')) for d in deliveries})}}
    return ok, checks, summary


def render(ok: bool, checks: list, s: dict, current=None) -> str:
    L = [f"  {'ok  ' if good else 'FAIL'} {n}  {title}" + (f': {detail}' if detail else '') for n, title, good, detail in checks]
    if not s:
        return '\n'.join(L + ['', 'FAILED: do not rely on this record.'])
    req = s['requirement']
    L += ['', f"  {req.get('id')} rev {req.get('revision')}: {req.get('title')}", f"  \"{req.get('statement')}\"",
          f"  baselined {s['baselined_at']} by {s['engineer']}.  Baseline {s['baseline_sha256'][:16]}…   Record as of {s['as_of'].get('time')}, sequence number {s['as_of'].get('seq')}."]
    if s.get('identities') == 'legacy':           # Amendment 17 (D21)
        L.append('  Its runs carry 64-bit attempt identities and 96-bit request keys, the form made before 22 November 2026.')
    if s['supersedes']:
        sp = s['supersedes']
        L.append(f"  CHANGED AFTER THE EVENT: this baseline replaced {sp.get('baseline_sha256', '')[:16]}… (rev {sp.get('revision', '?')}) after {sp.get('official_runs', '?')} official runs "
                 f"on it: {sp.get('met', '?')} met, {sp.get('not_met', '?')} not met, {sp.get('unknown', '?')} unknown.  Reason given by the engineer: {sp.get('reason')}")   # Amendment 4: all three counts
    if s.get('alongside'):                         # Amendment 9: a baseline made for a requirement already held, not as a revision of it, names the others
        al = s['alongside']
        L.append('  ALSO BASELINED FOR THIS REQUIREMENT, NOT AS A REVISION OF IT: ' + ', '.join(f"{str(b.get('baseline_sha256', ''))[:16]}… (rev {b.get('revision', '?')})" for b in al.get('baselines') or [])
                 + f".  Reason given by the engineer: {al.get('reason')}")
    for c in s['criteria']:
        L.append(f"  limit: {c['quantity']} {'at most' if c['comparison'] == '<=' else 'at least'} {c['limit']} {c['units']}")
    L += ['', f"  Official runs through the service: {s['official_runs']}.  Met {s['met']}, not met {s['not_met']}, unknown {s['unknown']}.  Awaiting the engineer's disposition: {s['open']}."]
    for r in s['runs']:
        what = ('; '.join(f"{c['id']} {c['achieved']} vs limit {c['limit']} {c['units']}" for c in r['criteria'] if c.get('achieved') is not None)
                or (outside_reason(s.get('design_space'), r.get('design')) if r['reason_code'] == 'DESIGN_OUTSIDE_BASELINE' else recorded(r['detail'])))
        tail = '' if r['outcome'] == 'PASS' else ('   acknowledged' if r['acknowledged'] else '   OPEN')
        L.append(f"    {r['aid']}  design {str(r['design_sha256'])[:10]}…  {'MET' if r['outcome'] == 'PASS' else r['outcome']:<11} {r['reason_code'] or '':<24} {what}{tail}")   # Amendment 9: MET, not PASS
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
    cp = s.get('checkpoint')
    if cp:                                         # Amendment 10: the witness's own word on the chain when the record was made
        later = cp['seq'] - cp['at']
        L.append(f"The witness's checkpoint in this record, made at {cp['time']} by its clock: the chain then had {cp['seq']} decisions"
                 + (', and ended with this record\'s last.' if later == 0 else f", {later} of them after this record's last: it was out of date when it was made.")
                 + ('' if cp.get('business') == 'OPEN' and cp.get('witness') == 'ACTIVE' else f"  The budget was then {cp.get('business')}" + (' and on hold' if cp.get('witness') != 'ACTIVE' else '') + ', and took no new runs.'))
    dv = s.get('delivery')                         # Amendment 11: notices delivered by a courier to the engineer's mailbox
    if dv is None:
        L.append('NOTICES: NOT CHECKED.  This record carries no notices delivered by a courier.')
    elif dv.get('unchecked'):
        L.append(f"NOTICES: NOT CHECKED.  The record carries {dv['notices']} notices delivered by a courier, but {dv['unchecked']} (--courier-key, --mailbox-key).")
    else:
        missing = [d for d in dv['due'] if not d['delivered']]
        L.append(f"NOTICES: {len(dv['due']) - len(missing)} of {len(dv['due'])} runs that call for a notice have one delivered to the engineer's mailbox, with its signed receipt."
                 + (('  NO DELIVERY EVIDENCE: ' + ', '.join(f"{d['aid']} ({d['outcome']})" for d in missing) + '.') if missing else '')
                 + ('  A receipt says the mailbox holds the notice; it does not say the engineer read it.'))
    if current is not None:
        L.append(f'CURRENCY: {current[0]}.  ' + current[1][:1].upper() + current[1][1:])
    else:
        L.append('CURRENCY: NOT CHECKED.  Give a checkpoint obtained separately from this record (--checkpoint) to see whether it is current.')
    return '\n'.join(L)


def main():
    ap = argparse.ArgumentParser(description='Check a verification record offline.')
    ap.add_argument('record'); ap.add_argument('--keys', help='a JSON file: {"witness": HEX, "gate": HEX, "engineer": HEX}')
    ap.add_argument('--witness-key', action='append'); ap.add_argument('--gate-key'); ap.add_argument('--engineer-key')
    ap.add_argument('--courier-key', action='append', help='a courier\'s key, for the notices delivered in the record (Amendment 11)')
    ap.add_argument('--mailbox-key', action='append', help='the engineer\'s mailbox key, for the receipts of the notices delivered (Amendment 11)')
    ap.add_argument('--design', help='a released design file to compare with the record'); ap.add_argument('--json', action='store_true')
    ap.add_argument('--checkpoint', help='a checkpoint signed by the witness, obtained separately from the record (Amendment 10)')
    ap.add_argument('--max-age', type=float, default=None, help='with --checkpoint: the checkpoint may be this many seconds old at most (default 3600)')
    ap.add_argument('--nonce', help='with --checkpoint: the nonce the checkpoint must sign back')
    ap.add_argument('--require-delivery', action='store_true', help='exit 1 unless every run that calls for a notice has one delivered (Amendment 11)')
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
    if keys is not None and (a.courier_key or a.mailbox_key):
        keys = dict(keys, **({'courier': a.courier_key} if a.courier_key else {}), **({'mailbox': a.mailbox_key} if a.mailbox_key else {}))
    elif a.courier_key or a.mailbox_key:
        ap.error('--courier-key and --mailbox-key go with the other keys given separately (--keys, or the three --*-key)')
    design = None
    if a.design:
        with open(a.design) as f:
            design = json.load(f)
    ok, checks, s = verify(record, keys, design)
    current = None
    if a.checkpoint is None and (a.max_age is not None or a.nonce is not None):
        ap.error('--max-age and --nonce are about a checkpoint: give --checkpoint')
    if a.checkpoint is not None:
        if keys is None:
            ap.error('--checkpoint needs the keys given separately from the record (--keys, or the three --*-key): a record cannot vouch for its own witness')
        if a.max_age is not None and not 0 <= a.max_age < float('inf'):
            ap.error('--max-age is a number of seconds, nought or more')
        try:
            with open(a.checkpoint) as f:
                cp = json.load(f)
        except (OSError, ValueError) as exc:
            ap.error(f'the checkpoint file cannot be read ({type(exc).__name__})')
        if ok:
            current = currency(record, cp, keys['witness'], None, 3600.0 if a.max_age is None else a.max_age, a.nonce)
    if a.json:
        print(json.dumps({'verified': ok, 'checks': [{'check': n, 'title': t, 'ok': o, 'detail': d} for n, t, o, d in checks], 'summary': s,
                          'currency': None if current is None else {'state': current[0], 'detail': current[1]}}, indent=1))
    else:
        print(render(ok, checks, s, current))
    delivered_all = bool((s or {}).get('delivery')) and not s['delivery'].get('unchecked') and all(d['delivered'] for d in s['delivery']['due'])
    sys.exit(0 if ok and (a.checkpoint is None or (current is not None and current[0] == 'CURRENT')) and (not a.require_delivery or delivered_all) else 1)


if __name__ == '__main__':
    main()
