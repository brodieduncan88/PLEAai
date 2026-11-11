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

evaluate() is the whole decision, and it is the same code for a control case and for a governed attempt:

  1  the design must be inside the design space, or the verdict is FAIL / DESIGN_OUTSIDE_BASELINE and the check is not run;
  2  the check and every input must hash to the card's values, or the verdict is UNKNOWN / BASELINE_MISMATCH;
  3  the verified bytes are copied to an empty directory and run there as a separate process with no credentials, the
     design on standard input; a crash, a timeout or a non-zero exit is UNKNOWN / CHECK_ERROR;
  4  the check must print one JSON object {"achieved": {criterion id: number}, "basis": "one sentence"}; anything else,
     or a value that is not a finite number, is UNKNOWN / CHECK_OUTPUT_INVALID;
  5  a value outside the criterion's plausible range is UNKNOWN / RESULT_IMPLAUSIBLE (zero, a sign error, a unit slip);
  6  this code, not the check and not the caller, compares each value with its limit in exact decimal arithmetic:
     all met is PASS / MET, otherwise FAIL / LIMIT_NOT_MET.

UNKNOWN is never a pass.  A verdict says only that the declared check returned numbers that do or do not meet the
baselined limits.  It does not say the check is right, the requirement is complete, or the part is safe.

Standard library only.
"""
import decimal
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile

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
    need(isinstance(chk.get('stated_limits'), list) and chk['stated_limits'], 'check.stated_limits is needed: say what the check does not cover')
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


def in_design_space(card: dict, design) -> tuple[bool, str]:
    space = card['design_space']
    if not isinstance(design, dict):
        return False, 'the design must be an object of parameters'
    if set(design) != set(space):
        extra, missing = sorted(set(design) - set(space)), sorted(set(space) - set(design))
        return False, 'the design must give exactly the baselined parameters' + (f'; not in the baseline: {", ".join(extra)}' if extra else '') + (f'; missing: {", ".join(missing)}' if missing else '')
    for name, rule in space.items():
        v = design[name]
        if 'choice' in rule:
            if isinstance(v, bool) or not isinstance(v, (str, int)) or not any(type(v) is type(c) and v == c for c in rule['choice']):
                return False, f'{name} = {v!r} is not on the approved list ({", ".join(map(str, rule["choice"]))})'
        else:
            d = dec(v)
            if d is None or isinstance(v, str):
                return False, f'{name} = {v!r} is not a number'
            if not D(rule['min']) <= d <= D(rule['max']):
                return False, f'{name} = {text(d)} is outside the baselined range {rule["min"]} to {rule["max"]}'
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
    with tempfile.TemporaryDirectory(prefix='verify-run-') as tmp:
        for name, data in files.items():
            (pathlib.Path(tmp) / name).write_bytes(data)                 # the bytes run are the bytes hashed
        try:
            run = subprocess.run([sys.executable, '-I', card['check']['file']], input=json.dumps(design).encode(), capture_output=True, cwd=tmp,
                                 timeout=CHECK_TIMEOUT, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        except subprocess.TimeoutExpired:
            return _verdict(card, design, 'CHECK_ERROR', _blank(card), detail=f'the check did not finish within {CHECK_TIMEOUT:.0f} s')
        except OSError as exc:
            return _verdict(card, design, 'CHECK_ERROR', _blank(card), detail=f'the check could not be started: {exc}'[:200])
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


def face(card: dict, verdict: dict, runs: dict | None = None, aid: str | None = None) -> str:
    """The verdict as an engineer reads it.  The same text goes to the assistant and to the engineer's inbox."""
    req, eng, chk = card['requirement'], card['responsible_engineer'], card['check']
    L = [HEADLINE[verdict['reason_code']], '']
    L.append(f"Requirement   {req['id']} rev {req['revision']}: {req['title']}")
    L.append(f"              \"{req['statement']}\"")
    L.append(f"              baselined {card.get('baselined_at', '?')} by {eng['name']}, responsible engineer.  Baseline {card_hash(card)[:16]}…, unchanged.")
    L.append(f"Load case     {card['load_case']}")
    L.append('Design        ' + ', '.join(f'{k} = {v}' for k, v in sorted(verdict['design'].items())) if isinstance(verdict['design'], dict) else f"Design        {verdict['design']!r}")
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
    L.append(f"Check         {chk['id']} v{chk['version']}, written by {chk['author']}, reviewed by {chk['reviewed_by']}.  Hash {chk['sha256'][:16]}…")
    L.append('Verdict       Computed by the verification service from the check\'s output and the baselined limits.  Not stated by the assistant.')
    if runs:
        L.append(f"Official runs {runs['total']} through the service on this baseline: {runs['PASS']} met, {runs['FAIL']} not met, {runs['UNKNOWN']} unknown." + (f"  This run: {aid}." if aid else ''))
    L.append('')
    if verdict['verdict'] != 'PASS':
        L.append('Nothing was changed.  The requirement, the limits, the load case and the check are exactly as baselined.')
        L.append(f"{eng['name']} has been sent this result directly.  Only {eng['name']} can accept a failure or issue a revised baseline; the assistant cannot.")
        L.append('What can happen next:  a different design inside the baselined design space (a new official run; this result stays on the record),')
        L.append(f"                       or a decision by {eng['name']}: redesign, a revised baseline with a reason, or a recorded concession.")
    L.append('This result says what the declared check returned against the baselined limits.  It does not say the check is correct.')
    L.append('The check does not cover: ' + '; '.join(chk['stated_limits']) + '.')
    return '\n'.join(L)
