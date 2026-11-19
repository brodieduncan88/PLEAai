"""The baselined requirement, the design space, and the comparison that decides a verdict.

A baseline is the requirement as a named engineer approved it before any work started.  It fixes, in one card:

  requirement     its id, revision, the sentence as the engineer wrote it, and where it comes from
  criteria        one or more numbers to compare: quantity, comparison (<= or >=), limit, units, and a plausible range
  load_case       the conditions the requirement applies under, as text
  design_space    what the designer may vary: each parameter is a choice from an approved list or a number within bounds
  check           the declared check: a script, its hash, who wrote and reviewed it, and what it does not cover
  inputs          the data files the check reads, each with its hash
  controls        designs with a known answer: at least one that must FAIL and one that must PASS.  They test the
                  check, not the requirement, so a control may lie outside the design space

The card's hash (sha256 of its canonical JSON) names the baseline everywhere: in the budget's name at the control
plane, in every attempt's arguments, and in every signed verdict.  Nothing here edits a card.  A change is a new card
that says which one it supersedes (verify_ctl.py revise).

evaluate() is the decision, and it is the same code for a control case and for a governed attempt.  For a governed
attempt the gate's tool then holds it to its word (verify_tools._decide, Amendment 2): a verdict that cannot be produced,
or that the record's checker would reject, becomes UNKNOWN there, or FAIL / DESIGN_OUTSIDE_BASELINE if the design cannot
be shown to be inside the design space.

  1  the design must be inside the design space, or the verdict is FAIL / DESIGN_OUTSIDE_BASELINE and the check is not run;
  2  the check and every input must hash to the card's values, or the verdict is UNKNOWN / BASELINE_MISMATCH;
  3  the verified bytes are copied to an empty directory and run there in a disposable sandbox of their own (sandbox.py,
     Amendment 12): no network, no other process, none of the machine's files but the Python installation, nobody's identity,
     and limits on time, memory, processes and output; the design on standard input.  A crash, a timeout, too much output
     or a non-zero exit is UNKNOWN / CHECK_ERROR, and so is a sandbox that cannot be made: the check is then not run;
  4  the check must print one JSON object {"achieved": {criterion id: number}, "basis": "one sentence"}; anything else,
     or a value that is not a finite number, is UNKNOWN / CHECK_OUTPUT_INVALID;
  5  a value outside the criterion's plausible range is UNKNOWN / RESULT_IMPLAUSIBLE (zero, a sign error, a unit slip);
  6  this code, not the check and not the caller, compares each value with its limit in exact decimal arithmetic:
     all met is PASS / MET, otherwise FAIL / LIMIT_NOT_MET.

UNKNOWN is never a pass.  A verdict says only that the declared check returned numbers that do or do not meet the
baselined limits.  It does not say the check is right, the requirement is complete, or the part is safe.

Standard library only (and sandbox.py beside it).
"""
import decimal
import hashlib
import json
import os
import pathlib
import sys

import sandbox                                                          # Amendment 12: the check's own disposable sandbox

FORMAT = 'verification-baseline/1'
VERDICT_FORMAT = 'verification-verdict/1'
COMPARISONS = ('<=', '>=')
VERDICTS = ('PASS', 'FAIL', 'UNKNOWN')
REASONS = {'MET': 'PASS', 'LIMIT_NOT_MET': 'FAIL', 'DESIGN_OUTSIDE_BASELINE': 'FAIL', 'BASELINE_MISMATCH': 'UNKNOWN', 'CHECK_ERROR': 'UNKNOWN',
           'CHECK_OUTPUT_INVALID': 'UNKNOWN', 'RESULT_IMPLAUSIBLE': 'UNKNOWN'}
CHECK_TIMEOUT = 30.0
D = decimal.Decimal


class BaselineInvalid(Exception):
    pass


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def card_hash(card: dict) -> str:
    return sha256_hex(canonical(card).encode())


def design_hash(design) -> str:
    return sha256_hex(canonical(design).encode())


def root_for(card: dict) -> str:
    """The budget's name at the control plane.  It carries the card's hash, so the immutable provisioning record anchors it."""
    r = card['requirement']
    return f"{r['id']}/{r['revision']}/{card_hash(card)[:32]}"


def dec(value):
    """A finite decimal from a JSON number or a decimal string, else None.  Booleans are not numbers here."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        d = D(str(value).strip())
    except (decimal.InvalidOperation, ValueError):
        return None
    return d if d.is_finite() else None


def text(d) -> str:
    """A decimal as plain text: no exponent, no trailing zeros."""
    if d == 0:
        return '0'
    s = format(d.normalize(), 'f')
    return s


# ---------------------------------------------------------------------------------------------------- what a sender supplied, shown to a person
SENT_KEEP = 20          # how many characters of a name or a text that a sender supplied are shown to a person
SENT_NUMBER = 24        # a number is shown whole if it is no longer than this (every float is), and is not shown at all if it is longer
SENT_LINES = 12         # how many names that are not the baseline's are shown, each on a line; the rest are counted
SENT_MARK = '          sent: '      # what begins every line that shows something a sender supplied


def sent(value) -> str:
    """Something a design supplied, as it is written wherever a person reads it.  (Amendment 3, 12 November 2026.)

    The sender of a design chooses its names and its text.  Written as sent, a name could be a sentence that reads like
    the service's own, and padded with spaces it could fall at the start of a row on the reader's screen.  So a text is
    written in double quotes and in ASCII: every other character is written as its escape, and so is a space that
    follows a space.  At most SENT_KEEP characters are shown, and "+N" after the quotes says that N more were sent.  A
    number is written whole if it has at most SENT_NUMBER characters, as every float has; a longer one is not shown,
    because part of a number reads as another number.  A list or an object is counted, not shown.  Nothing returned
    here is longer than 30 characters, so no line that design_lines() makes of it is longer than 78.  The whole design
    is in the signed verdict; this is only how it is shown."""
    if value is None or isinstance(value, bool):
        return json.dumps(value)
    if isinstance(value, (int, float)):
        digits = _digits(value)
        if digits is None:
            return 'a number, not shown'
        return digits if len(digits) <= SENT_NUMBER else f'a number of {len(digits)} characters'
    if isinstance(value, str):
        out, used, shown = [], 0, 0
        for i, ch in enumerate(value):
            o = ord(ch)
            if ch in '"\\':
                piece = '\\' + ch
            elif ch == ' ' and i and value[i - 1] == ' ':
                piece = '\\u0020'
            elif 32 <= o < 127:
                piece = ch
            elif o > 0xFFFF:
                piece = f'\\u{0xD800 + ((o - 0x10000) >> 10):04x}\\u{0xDC00 + ((o - 0x10000) & 0x3FF):04x}'
            else:
                piece = f'\\u{o:04x}'
            if used + len(piece) > SENT_KEEP:
                break
            out.append(piece); used += len(piece); shown += 1
        more = len(value) - shown
        return '"' + ''.join(out) + '"' + ('' if not more else f'+{more}' if more < 100000 else '+99999+')
    count = str(len(value)) if isinstance(value, (list, dict)) and len(value) < 100000 else '99999+'
    if isinstance(value, list):
        return f'a list of {count}, not shown'
    if isinstance(value, dict):
        return f'an object of {count}, not shown'
    return 'a value of another kind'


def _digits(v):
    """A finite number as it is written, or None if the value is not one or is too long to be written at all."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v in (float('inf'), float('-inf')):
        return None
    try:
        return json.dumps(v)
    except ValueError:
        return None


def _plain_number(v) -> bool:
    """A number short enough to be written whole in the service's own sentence: digits, a sign, a point and an exponent, and nothing else."""
    digits = _digits(v)
    return digits is not None and len(digits) <= SENT_NUMBER


def design_lines(space, design) -> list:
    """The design as a person reads it, in a notice or an answer.  (Amendment 3.)

    What is the baseline's own, a parameter it names with a value on its approved list or a number of at most
    SENT_NUMBER characters, is written plainly on the first line, as before.  Anything else was chosen by the sender.
    It is set out underneath, one parameter to a line, each line beginning SENT_MARK, through sent().  First come the
    baseline's own parameters for which something else was sent: all of them.  Then the names that are not the
    baseline's: at most SENT_LINES of them, and a count of the rest, so that a design of hundreds of names cannot push
    the service's own lines out of sight or choose which lines are shown.  No such line is longer than 78 characters,
    so in a window of 80 columns or more no row begins with a sender's words.  `space` is the card's design space, or
    None when no usable baseline is held: then all of it is the sender's."""
    held, space = isinstance(space, dict), (space if isinstance(space, dict) else {})
    if not isinstance(design, dict):
        return ['Design        not an object; as sent: ' + sent(design)]
    if not design:
        return ['Design        no parameters were sent']
    own, named, other = [], [], []
    for k in sorted(design, key=str):
        v, rule = design[k], (space.get(k) if isinstance(k, str) else None)
        if rule is not None and (_plain_number(v) or ('choice' in rule and not isinstance(v, bool) and isinstance(v, (str, int)) and any(type(v) is type(c) and v == c for c in rule['choice']))):
            own.append(f'{k} = {v}')
        elif rule is not None:
            named.append(SENT_MARK + (k if len(k) <= 26 else k[:23] + '...') + ' = ' + sent(v))
        else:
            other.append(SENT_MARK + sent(k) + ' = ' + sent(v))
    L = ['Design        ' + (', '.join(own) if own else ('nothing in it is in the baseline\'s own words' if held else 'no usable baseline is held to set it against'))]
    if named or other:
        L.append('              From the caller, not the service (quoted; cut at 20, +N more):')
        L += named + other[:SENT_LINES]
        if len(other) > SENT_LINES:
            # Amendment 5: with no baseline to set it against (held False), it is not known whose names these are
            L.append(f'                and {len(other) - SENT_LINES} more names' + (" that are not the baseline's" if held else '') + ', not shown')
    return L


# ---------------------------------------------------------------------------------------------------- the card
def validate_card(card: dict) -> None:
    def need(cond, msg):
        if not cond:
            raise BaselineInvalid(msg)
    need(isinstance(card, dict) and card.get('format') == FORMAT, f'format must be {FORMAT}')
    req = card.get('requirement') or {}
    for k in ('id', 'revision', 'title', 'statement', 'source'):
        need(isinstance(req.get(k), str) and req[k].strip(), f'requirement.{k} is needed')
    need('/' not in req['id'] and '/' not in req['revision'], 'requirement id and revision must not contain "/"')
    crit = card.get('criteria')
    need(isinstance(crit, list) and crit, 'at least one criterion is needed')
    seen = set()
    for c in crit:
        for k in ('id', 'quantity', 'units'):
            need(isinstance(c.get(k), str) and c[k].strip(), f'criterion.{k} is needed')
        need(c['id'] not in seen, f'criterion id {c["id"]} is repeated'); seen.add(c['id'])
        need(c.get('comparison') in COMPARISONS, f'criterion {c["id"]}: comparison must be <= or >=')
        need(dec(c.get('limit')) is not None and isinstance(c['limit'], str), f'criterion {c["id"]}: limit must be a number written as text')
        p = c.get('plausible') or {}
        lo, hi = dec(p.get('min')), dec(p.get('max'))
        need(lo is not None and hi is not None and lo < hi, f'criterion {c["id"]}: a plausible range (min < max) is needed, so that zero or a unit slip is not read as a result')
    need(isinstance(card.get('load_case'), str) and card['load_case'].strip(), 'load_case is needed')
    space = card.get('design_space')
    need(isinstance(space, dict) and space, 'design_space needs at least one parameter')
    for name, rule in space.items():
        if 'choice' in rule:
            need(isinstance(rule['choice'], list) and rule['choice'] and all(isinstance(x, (str, int)) and not isinstance(x, bool) for x in rule['choice']),
                 f'design_space.{name}: choice must be a list of names or whole numbers')
        else:
            lo, hi = dec(rule.get('min')), dec(rule.get('max'))
            need(lo is not None and hi is not None and lo <= hi, f'design_space.{name}: needs "choice" or numeric "min" and "max"')
    chk = card.get('check') or {}
    for k in ('id', 'version', 'file', 'sha256', 'author', 'reviewed_by'):
        need(isinstance(chk.get(k), str) and chk[k].strip(), f'check.{k} is needed')
    # Amendment 7 (D4): each stated limit is text.  A card whose limits are not text was signed and accepted before, and its notice
    # then failed in face(), so no verdict and no notice were given.  load_envelope() calls this too, so every run refuses such a card.
    need(isinstance(chk.get('stated_limits'), list) and chk['stated_limits'] and all(isinstance(s, str) and s.strip() for s in chk['stated_limits']),
         'check.stated_limits is needed: say what the check does not cover')
    need(isinstance(card.get('inputs'), list) and all(isinstance(i.get('file'), str) and isinstance(i.get('sha256'), str) for i in card['inputs']), 'inputs must be a list of {file, sha256}')
    for f in [chk['file']] + [i['file'] for i in card['inputs']]:
        need(f == pathlib.PurePosixPath(f).name and not f.startswith('.'), f'file name {f!r} must be a plain name in the baseline directory')
    controls = card.get('controls')
    need(isinstance(controls, list) and {'PASS', 'FAIL'} <= {c.get('expect') for c in controls},
         'controls need at least one design that must FAIL and one that must PASS: a check nobody has seen fail is not a check')
    eng = card.get('responsible_engineer') or {}
    need(isinstance(eng.get('name'), str) and eng['name'].strip() and isinstance(eng.get('key'), str) and len(eng['key']) == 64, 'responsible_engineer needs a name and a public key')
    sup = card.get('supersedes')
    need(sup is None or (isinstance(sup, dict) and isinstance(sup.get('baseline_sha256'), str) and isinstance(sup.get('reason'), str) and sup['reason'].strip()),
         'supersedes must be null or name the earlier baseline and give a reason')
    # Amendment 9: a baseline made for a requirement id the service already held a baseline for, and not as a revision of it,
    # names those baselines and the engineer's reason, so that the link is in the signed card and in every record built from it.
    side = card.get('alongside')
    need(side is None or (isinstance(side, dict) and isinstance(side.get('reason'), str) and side['reason'].strip()
                          and isinstance(side.get('baselines'), list) and side['baselines']
                          and all(isinstance(x, dict) and isinstance(x.get('baseline_sha256'), str) and len(x['baseline_sha256']) == 64
                                  and set(x['baseline_sha256']) <= set('0123456789abcdef') and isinstance(x.get('revision'), str) for x in side['baselines'])),
         'alongside must be null or name the other baselines held for this requirement and give a reason')


def in_design_space(card: dict, design) -> tuple[bool, str]:
    """Whether a design is inside the baselined design space and, if it is not, why.  The reason goes into the signed
    verdict and is read by people.  Since Amendment 3 it is the service's own words throughout: it names the baseline's
    parameters, counts the names that are not the baseline's, and repeats from the design only a number of at most
    SENT_NUMBER characters.  A name or a text from the design is never repeated here; face() shows it, marked as sent."""
    space = card['design_space']
    if not isinstance(design, dict):
        return False, 'the design must be an object of parameters'
    if set(design) != set(space):
        extra, missing = set(design) - set(space), sorted(set(space) - set(design))
        return False, ('the design must give exactly the baselined parameters' + (f'; {len(extra)} of the names sent {"is" if len(extra) == 1 else "are"} not in the baseline' if extra else '')
                       + (f'; missing: {", ".join(missing)}' if missing else ''))
    for name, rule in space.items():
        v = design[name]
        if 'choice' in rule:
            if isinstance(v, bool) or not isinstance(v, (str, int)) or not any(type(v) is type(c) and v == c for c in rule['choice']):
                return False, (f'{name} = {v!r}' if _plain_number(v) else f'the value sent for {name}') + f' is not on the approved list ({", ".join(map(str, rule["choice"]))})'
        else:
            d = dec(v)
            if d is None or isinstance(v, str):
                return False, f'the value sent for {name} is not a number'
            if not D(rule['min']) <= d <= D(rule['max']):
                shown = text(d) if len(text(d)) <= SENT_NUMBER else (_digits(v) if _plain_number(v) else None)     # as before when that is short; else as it was written; else not at all
                return False, (f'{name} = {shown}' if shown is not None else f'the value sent for {name}') + f' is outside the baselined range {rule["min"]} to {rule["max"]}'
    return True, ''


# ---------------------------------------------------------------------------------------------------- the decision
def _verdict(card, design, reason, criteria, basis='', detail='') -> dict:
    return {'format': VERDICT_FORMAT, 'verdict': REASONS[reason], 'reason_code': reason, 'requirement_id': card['requirement']['id'],
            'revision': card['requirement']['revision'], 'baseline_sha256': card_hash(card), 'design': design, 'design_sha256': design_hash(design),
            'criteria': criteria, 'basis': basis, 'detail': detail,
            'check': {'id': card['check']['id'], 'version': card['check']['version'], 'sha256': card['check']['sha256']}}


def _blank(card) -> list:
    return [{'id': c['id'], 'quantity': c['quantity'], 'comparison': c['comparison'], 'limit': c['limit'], 'units': c['units'], 'achieved': None, 'margin': None, 'met': None}
            for c in card['criteria']]


def compare(criterion: dict, achieved) -> tuple[bool, str]:
    """(met, margin as text).  The margin is positive when there is room to spare."""
    limit = D(criterion['limit'])
    if criterion['comparison'] == '<=':
        return achieved <= limit, text(limit - achieved)
    return achieved >= limit, text(achieved - limit)


def evaluate(directory, card: dict, design, control: bool = False) -> dict:
    """Decide one design against one baseline.  Always returns a verdict object; never raises for a bad design or a bad check.
    control=True is for a control case at baselining: it exercises the check, so the design-space test is skipped (a
    requirement that no allowed design can meet still needs a design the check is known to pass)."""
    directory = pathlib.Path(directory)
    ok, why = (True, '') if control else in_design_space(card, design)
    if not ok:
        return _verdict(card, design, 'DESIGN_OUTSIDE_BASELINE', _blank(card), detail=why + '.  The check was not run.')
    files = {}
    for name, want in [(card['check']['file'], card['check']['sha256'])] + [(i['file'], i['sha256']) for i in card['inputs']]:
        try:
            data = (directory / name).read_bytes()
        except OSError:
            return _verdict(card, design, 'BASELINE_MISMATCH', _blank(card), detail=f'{name} is missing from the baseline directory')
        if sha256_hex(data) != want:
            return _verdict(card, design, 'BASELINE_MISMATCH', _blank(card), detail=f'{name} no longer matches the baseline (it was changed after baselining)')
        files[name] = data
    run = sandbox.run(files, card['check']['file'], json.dumps(design).encode(), timeout=CHECK_TIMEOUT)   # the bytes run are the bytes hashed (Amendment 12: in a sandbox of its own)
    if run.state == 'SANDBOX_UNAVAILABLE':
        return _verdict(card, design, 'CHECK_ERROR', _blank(card), detail=f'the check was not run: {run.detail}'[:300])
    if run.state == 'TIMEOUT':
        return _verdict(card, design, 'CHECK_ERROR', _blank(card), detail=f'the check did not finish within {CHECK_TIMEOUT:.0f} s')
    if run.state == 'OUTPUT_TOO_LONG':
        return _verdict(card, design, 'CHECK_ERROR', _blank(card), detail=f'the check printed more than {sandbox.MAX_OUTPUT} bytes')
    if run.returncode != 0:
        tail = run.stderr.decode(errors='replace').strip().splitlines()[-1:] or ['no message']
        return _verdict(card, design, 'CHECK_ERROR', _blank(card), detail=f'the check exited with status {run.returncode}: {tail[0]}'[:300])
    try:
        out = json.loads(run.stdout.decode('utf-8'))
        achieved, basis = out['achieved'], out.get('basis', '')
        if not isinstance(achieved, dict) or not isinstance(basis, str):
            raise ValueError
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        return _verdict(card, design, 'CHECK_OUTPUT_INVALID', _blank(card), detail='the check did not print one JSON object {"achieved": {...}, "basis": "..."}')
    criteria, all_met = [], True
    for c in card['criteria']:
        value = dec(achieved.get(c['id']))
        if value is None:
            return _verdict(card, design, 'CHECK_OUTPUT_INVALID', _blank(card), basis[:400], f'the check gave no finite number for {c["id"]} (got {achieved.get(c["id"])!r})')
        if not D(c['plausible']['min']) <= value <= D(c['plausible']['max']):
            return _verdict(card, design, 'RESULT_IMPLAUSIBLE', _blank(card), basis[:400],
                            f'{c["id"]} = {text(value)} {c["units"]} is outside the plausible range {c["plausible"]["min"]} to {c["plausible"]["max"]} declared at baseline')
        met, margin = compare(c, value)
        all_met = all_met and met
        criteria.append({'id': c['id'], 'quantity': c['quantity'], 'comparison': c['comparison'], 'limit': c['limit'], 'units': c['units'],
                         'achieved': text(value), 'margin': margin, 'met': met})
    return _verdict(card, design, 'MET' if all_met else 'LIMIT_NOT_MET', criteria, basis[:400])


# ---------------------------------------------------------------------------------------------------- the face of a verdict
HEADLINE = {'MET': 'DECLARED CHECK MET', 'LIMIT_NOT_MET': 'FAIL: REQUIREMENT NOT MET', 'DESIGN_OUTSIDE_BASELINE': 'FAIL: DESIGN OUTSIDE THE BASELINE',
            'BASELINE_MISMATCH': 'UNKNOWN: THE CHECK OR ITS DATA NO LONGER MATCHES THE BASELINE', 'CHECK_ERROR': 'UNKNOWN: THE CHECK DID NOT RUN TO A RESULT',
            'CHECK_OUTPUT_INVALID': 'UNKNOWN: THE CHECK GAVE NO USABLE RESULT', 'RESULT_IMPLAUSIBLE': 'UNKNOWN: THE RESULT IS NOT PLAUSIBLE'}


# Amendment 4: what a notice says of the check's files, by reason.  Only these reasons come only from evaluate(), so only for
# them is it known whether the files were checked.  Any other reason says nothing of them.
_CHECK_FILES = {'BASELINE_MISMATCH': 'The check or its data is not as baselined (the reason above), so the check was not run.',
                'MET': 'The check and its data matched their baselined hashes when it ran.',              # Amendment 5: a pass says it too
                'LIMIT_NOT_MET': 'The check and its data matched their baselined hashes when it ran.',
                'RESULT_IMPLAUSIBLE': 'The check and its data matched their baselined hashes when it ran.'}
NO_CARD_HEADLINE = 'UNKNOWN: THE VERIFICATION SERVICE HOLDS NO USABLE COPY OF THIS BASELINE'
# Amendment 9: what the Verdict row calls each signed verdict.  A pass is signed PASS, and the record and its checker keep that
# word; what a person or an assistant reads calls it what it is, the declared check met.
VERDICT_WORDS = {'PASS': 'DECLARED CHECK MET (signed as PASS)', 'FAIL': 'FAIL', 'UNKNOWN': 'UNKNOWN'}


def does_not_cover(card: dict) -> str:
    """The line that says what the check does not cover, from the card.  (Amendment 9: it stands under the headline of every
    verdict, so that a host that shortens a result does not cut it, and again at the end.)"""
    return 'The check does not cover: ' + '; '.join(card['check']['stated_limits']) + '.'


def face(card: dict, verdict: dict, runs: dict | None = None, aid: str | None = None) -> str:
    """The verdict as an engineer reads it.  The same text goes to the assistant and to the engineer's inbox."""
    req, eng, chk = card['requirement'], card['responsible_engineer'], card['check']
    held = verdict.get('check') is not None             # Amendment 4: False only for the gate's refusal when it holds no usable copy of the card
    L = [HEADLINE[verdict['reason_code']] if held else NO_CARD_HEADLINE, does_not_cover(card), '']      # Amendment 9: the exclusions first
    L.append(f"Requirement   {req['id']} rev {req['revision']}: {req['title']}")
    L.append(f"              \"{req['statement']}\"")
    # Amendment 5 (13 November 2026): this line ended "unchanged." for a usable card, which is so of the signed card but sat
    # under the first line of a changed check, where it could be read as saying the check was unchanged; and "as this
    # client holds it." when no usable card was held, which is not so when the front door prints it.  It now ends at the
    # hash, or says the card is the copy read for this answer; the lines after the Verdict row say what is so of the card
    # and of the check's files.
    L.append(f"              baselined {card.get('baselined_at', '?')} by {eng['name']}, responsible engineer.  Baseline {card_hash(card)[:16]}…"
             + ('' if held else ', as read for this answer.'))
    L.append(f"Load case     {card['load_case']}")
    L += design_lines(card['design_space'], verdict['design'])
    L.append(f"              design hash {verdict['design_sha256'][:16]}…")
    L.append('')
    for c in verdict['criteria']:
        word = {'<=': 'at most', '>=': 'at least'}[c['comparison']]
        if c['achieved'] is None:
            L.append(f"  {c['quantity']}: required {word} {c['limit']} {c['units']}; not evaluated")
        else:
            limit = D(c['limit']); pct = '' if limit == 0 else f" ({abs(D(c['margin'])) / abs(limit) * 100:.0f}% {'inside' if c['met'] else 'beyond'} the limit)"
            L.append(f"  {c['quantity']}: required {word} {c['limit']} {c['units']}; achieved {c['achieved']} {c['units']}; margin {c['margin']} {c['units']}{pct}  -> {'met' if c['met'] else 'NOT MET'}")
    L.append('')
    if verdict['reason_code'] == 'MET':
        L.append('Reason        Every baselined limit was met by the number the declared check returned.')
    elif verdict['reason_code'] == 'LIMIT_NOT_MET':
        L.append('Reason        ' + '; '.join(f"{c['quantity']} is {c['achieved']} {c['units']}, the limit is {c['limit']} {c['units']}" for c in verdict['criteria'] if c['met'] is False) + '.')
    else:
        L.append(f"Reason        {verdict['detail']}")
    if verdict['basis']:
        L.append(f"Basis         As reported by the declared check (not verified by this tool): \"{verdict['basis']}\"")
    L.append(f"Check         {chk['id']} v{chk['version']}, written by {chk['author']}, reviewed by {chk['reviewed_by']}.  Baselined hash {chk['sha256'][:16]}…")     # Amendment 5: "Baselined", not the file's hash now
    compared = verdict['reason_code'] in ('MET', 'LIMIT_NOT_MET')          # Amendment 4: only then were the check's numbers compared with the limits
    # Amendment 9: a pass is called the declared check met, signed as PASS
    L.append(f"Verdict       {VERDICT_WORDS.get(verdict['verdict'], verdict['verdict'])}.  " + ("Computed by the verification service from the check's output and the baselined limits." if compared else
                                                         'Decided by the verification service, not by comparing the check\'s numbers with the limits.') + '  Not stated by the assistant.')
    if runs:
        L.append(f"Official runs {runs['total']} through the service on this baseline: {runs['PASS']} met, {runs['FAIL']} not met, {runs['UNKNOWN']} unknown." + (f"  This run: {aid}." if aid else ''))
    L.append('')
    # Amendment 4 (12 November 2026).  This used to say "Nothing was changed.  The requirement, the limits, the load case and
    # the check are exactly as baselined." for every FAIL and UNKNOWN, so the notice of an UNKNOWN given because the check or
    # its data was changed said the opposite of its own reason.  It says only what is so for this verdict: the card was
    # checked (its hash and the engineer's signature) before it was used; the check's files were checked only when the check
    # ran, and were found changed for BASELINE_MISMATCH.  When the gate held no usable copy of the card, it says that and
    # nothing else.  Amendment 5: a pass says it too, where it used to say only "unchanged" on the requirement line.
    if not held:
        L.append('The verification service could not use its stored copy of this baseline (the reason above), so nothing was checked against it.')
    else:
        L.append('The requirement, the limits and the load case are as baselined.')
        if verdict['reason_code'] in _CHECK_FILES:
            L.append(_CHECK_FILES[verdict['reason_code']])
    if verdict['verdict'] != 'PASS':
        L.append(f"{eng['name']} has been sent this result directly.  Only {eng['name']} can accept this result or issue a revised baseline; the assistant cannot.")
        if not held:
            L.append(f"What can happen next:  {eng['name']} restores the stored baseline, or issues a revised baseline with a reason.")
            L.append('                       Until then no design can be verified against this baseline.')
        elif verdict['reason_code'] == 'BASELINE_MISMATCH':
            L.append(f"What can happen next:  {eng['name']} restores the check and its data to the files whose hashes the baseline holds,")
            L.append('                       or issues a revised baseline with a reason.')
            L.append('                       Until then no design inside the design space can be verified against this baseline.')
        else:
            L.append('What can happen next:  a different design inside the baselined design space (a new official run; this result stays on the record),')
            L.append(f"                       or a decision by {eng['name']}: redesign, a revised baseline with a reason, or a recorded concession.")
    L.append('This result says what the declared check returned against the baselined limits.  It does not say the check is correct.' if compared else
             'This result gives no number from the check against the limits.  It does not say the check is correct.')
    L.append(does_not_cover(card))
    return '\n'.join(L)
