"""The one tool the gate host runs for verification:  gate_host.py --tools verify_tools   (with VERIFY_HOME set).

verify(baseline_sha256, design) decides one design against one baselined requirement and returns the verdict object
the gate host signs (baseline.py: PASS, FAIL or UNKNOWN, with a reason code, each limit, each achieved value and the
margin).  The gate host runs it at most once per attempt, behind the witness's receipts.

A failure is a result here, never an error and never NoEffect.  In the attempt-budget contract NO_EFFECT refunds the
attempt and carries no result, which would hand a failed verification a free retry and drop its reason; so every
handled outcome, including "the check could not be run", is returned as a signed result.  The contract's own UNKNOWN
is left for the one case this code cannot report: the host dying part-way.

VERIFY_HOME holds, on the engineer's side of the line:
  baselines/<baseline_sha256>/   baseline.json (the signed envelope), the check script, its input files
  inbox/<first 16 of the hash>/  one notice per FAIL or UNKNOWN, written here by this process for the responsible
                                 engineer.  The assistant does not write it and is not asked to pass it on.  The file
                                 baseline_sha256 in it holds the full hash of the baseline it belongs to (Amendment 6).
  inbox/unclaimed/<full hash>/   a notice about a hash for which the service finds no baseline folder and whose full
                                 hash it reads in no inbox: kept, addressed to no engineer, read by none (Amendment 6)
  ledger.jsonl                   one line per call and per verdict, outside every PLEA store, for tests

VERIFY_ENGINEER_KEYS is the comma-separated list of engineer public keys this gate accepts baselines from.  A baseline
is read and its signature checked on every call, so a card changed after signing is refused, not used.
"""
import json
import os
import pathlib
import sys
import time
import unicodedata

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from plea_gateway.faults import crash_point            # noqa: E402
from baseline import REASONS, VERDICT_FORMAT, _blank, _verdict, design_hash, design_lines, evaluate, face   # noqa: E402
from check_record import in_design_space as inside_as_checked, rederive   # noqa: E402  (Amendment 2: the record's checker is asked before a verdict is returned)
from verify_record import load_envelope                # noqa: E402

HOME = pathlib.Path(os.environ['VERIFY_HOME'])
ENGINEER_KEYS = tuple(k for k in os.environ.get('VERIFY_ENGINEER_KEYS', '').split(',') if k)
LEDGER = HOME / 'ledger.jsonl'
HEX = set('0123456789abcdef')
NOT_A_CARD = {'BaselineInvalid': 'a part of it is missing or is not as a card needs it', 'AttributeError': 'a part of it is the wrong kind of value',
              'RecursionError': 'it is nested too deeply to read'}


def _ledger(event: str, **fields) -> None:
    with LEDGER.open('a') as f:
        f.write(json.dumps({'event': event, 'pid': os.getpid(), 't': time.time(), **fields}) + '\n')


def _printable(text: str) -> str:
    """Text on one line that can be signed, stored and printed.  A space of any kind is written as a plain space; any other
    character that is not printable (a control or format character, a line break, half a surrogate pair) as its escape."""
    return ''.join(ch if ch.isprintable() else ' ' if unicodedata.category(ch) == 'Zs' else ch.encode('unicode_escape').decode('ascii') for ch in text)


def _decide(directory, card: dict, design) -> dict:
    """evaluate(), held to what it promises: a verdict whatever the check does.  (Amendment 2, 12 November 2026.)

    Three things went wrong here before.  For output it could not read at all (nested very deep, a number written with an
    exponent of a million) evaluate() raised instead of returning, and the run read as interrupted with nobody told.  A
    NUL or half a surrogate pair in the text a check supplies (its basis, the last line it wrote before stopping) could
    not be stored or written in a notice, and a line break there set a line of the check's own in the notice.  And a
    value the check gave to more than 28 significant digits was compared exactly but written rounded, so the record's
    checker, working from what was written, did not agree with the verdict.

    So: the text a check supplies is made printable; the verdict is put to the record's own checker (rederive) before
    it is returned; and a verdict that cannot be produced, or that the checker would not accept, becomes UNKNOWN in
    fixed words.  Nothing the check printed is repeated in those words."""
    try:
        result = evaluate(directory, card, design)
        for field in ('basis', 'detail'):
            result[field] = _printable(result[field])
        if not rederive(card, result, design):
            return result
        reason, words = 'CHECK_OUTPUT_INVALID', ('the numbers the check printed could not be written in a form that can be checked again '
                                                 '(for example a value given to more than 28 significant digits)')
    except Exception as exc:
        reason, words = 'CHECK_ERROR', ('the check could not be run to a result: the verification service met an error it did not expect '
                                        f'while running the check or reading what it printed (an error of the kind {type(exc).__name__})')
    try:
        inside = inside_as_checked(card, design)
    except Exception:
        inside = False
    if not inside:                                        # the checker accepts only this answer for a design it finds outside the design space
        return _verdict(card, design, 'DESIGN_OUTSIDE_BASELINE', _blank(card), detail='the design could not be shown to be inside the baselined design space, so no result of the check is given for it')
    return _verdict(card, design, reason, _blank(card), detail=words)


def _refusal(baseline_sha256, design, detail: str) -> dict:
    """A signed UNKNOWN for a request that names no usable baseline.  There is no card, so there are no criteria."""
    return {'format': VERDICT_FORMAT, 'verdict': REASONS['BASELINE_MISMATCH'], 'reason_code': 'BASELINE_MISMATCH', 'requirement_id': None, 'revision': None,
            'baseline_sha256': baseline_sha256 if isinstance(baseline_sha256, str) else None, 'design': design, 'design_sha256': design_hash(design),
            'criteria': [], 'basis': '', 'detail': detail, 'check': None}


CLAIM = 'baseline_sha256'          # Amendment 6: in an engineer's inbox, the full hash of the baseline the inbox belongs to
NONE_STORED = '(none is stored under this hash)'    # Amendment 6: how the reason ends when nothing at all is stored under the hash


def _held(baseline_sha256: str) -> bool:
    """Whether the service holds a baseline folder for this exact hash.  (Amendment 6.)  An error in looking, such as a
    folder that cannot be searched, counts as not held, so that the inbox's claim decides and the notice is not lost."""
    try:
        return (HOME / 'baselines' / baseline_sha256).is_dir()
    except OSError:
        return False


def _claimed(box: pathlib.Path):
    """The full hash an inbox holds, or None if it holds none that can be read: no file, an empty one, or one that is not
    a hash.  (Amendment 6.)"""
    try:
        text = (box / CLAIM).read_text(encoding='utf-8').strip()
    except (OSError, UnicodeError):
        return None
    return text if len(text) == 64 and set(text) <= HEX else None


def _inbox(baseline_sha256: str):
    """Where a notice about this hash goes, and whether that is an engineer's inbox.  (Amendment 6, 15 November 2026.)

    An inbox is named by the first 64 bits of the hash, and a request may name any hash, so a notice for a made-up hash
    that shared them went to a real engineer's inbox.  A notice now goes to that inbox only when the service holds a
    baseline folder for this exact hash, or the inbox holds this exact full hash, so that a baseline whose folder was
    taken away still reaches its engineer.  Any other notice is kept in inbox/unclaimed/<the full hash>/, which is no
    engineer's inbox."""
    box = HOME / 'inbox' / baseline_sha256[:16]
    if _held(baseline_sha256) or _claimed(box) == baseline_sha256:
        return box, True
    return HOME / 'inbox' / 'unclaimed' / baseline_sha256, False


def _claim(baseline_sha256: str) -> None:
    """For a baseline folder the service holds: make its engineer's inbox, and write the inbox's claim if it holds none
    that can be read.  (Amendment 6.)  A claim naming another full hash is left as it is: two baselines whose hashes share
    their first 64 bits share an inbox, and the first keeps the claim.  The claim is written whole or not at all, by a
    link or, where the file system makes none, a rename, and an empty or broken one, as a crash part-way could leave, is
    written again.  Nothing here stops a run: an error is met again, and handled as before, when a notice is written."""
    box = HOME / 'inbox' / baseline_sha256[:16]
    try:
        box.mkdir(parents=True, exist_ok=True)
        if _claimed(box) is not None:
            return
        part = box / f'.{CLAIM}.{os.getpid()}.{os.urandom(6).hex()}'          # its own name in every thread and process
        try:
            part.write_text(baseline_sha256 + '\n', encoding='utf-8')
            try:
                os.link(part, box / CLAIM)
            except OSError:                                    # one is there already, or the file system makes no hard links
                if _claimed(box) is None:
                    os.replace(part, box / CLAIM)
        finally:
            part.unlink(missing_ok=True)
    except OSError:
        pass


def _claim_all() -> None:
    """When the tool starts: every baseline folder the service holds gets its inbox's claim, as baselines made before
    Amendment 6 have none."""
    try:
        names = [p.name for p in (HOME / 'baselines').iterdir()]
    except OSError:
        return
    for name in names:
        if len(name) == 64 and set(name) <= HEX and _held(name):
            _claim(name)


def _notify(card, baseline_sha256: str, verdict: dict) -> str:
    """One notice per FAIL or UNKNOWN, in the inbox of the baseline the request named, when the service finds that baseline's
    folder or reads its full hash in the inbox; otherwise kept in inbox/unclaimed/, addressed to no engineer (Amendment 6).  With no
    usable card (it was changed, or signed by someone else) the notice says so in plain words; it never quotes the
    unusable card."""
    box, engineer = _inbox(baseline_sha256); box.mkdir(parents=True, exist_ok=True)
    stem = f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}_{verdict['verdict']}_{verdict['design_sha256'][:8]}"
    if card is not None:
        body = f"To: {card['responsible_engineer']['name']}\nFrom: the verification service (not the assistant)\n\n" + face(card, verdict)
    elif not engineer:                                   # Amendment 6: no engineer holds this hash, and the notice does not say one does
        body = (f"To: no engineer: the verification service found no baseline folder for the hash {baseline_sha256}, and read it in no inbox\n"
                f"From: the verification service (not the assistant)\n\n"
                f"UNKNOWN: A VERIFICATION RUN WAS ASKED FOR AND NO USABLE BASELINE IS HELD\n\nReason        {verdict['detail']}\n"
                + '\n'.join(design_lines(None, verdict['design']))
                + "\n\nNo check was run.  This is not a pass.  This notice is kept by the service and sent to nobody.")
    else:
        body = (f"To: the responsible engineer for baseline {baseline_sha256}\nFrom: the verification service (not the assistant)\n\n"
                f"UNKNOWN: A VERIFICATION RUN WAS ASKED FOR AND NO USABLE BASELINE IS HELD\n\nReason        {verdict['detail']}\n"
                + '\n'.join(design_lines(None, verdict['design']))          # Amendment 3: marked as sent, in quotes and cut; no baseline is held to set it against
                + ("\n\nNo check was run.  This is not a pass.  Nothing is stored under this hash; the baseline should be restored, or a revised one issued."
                   if verdict['detail'].endswith(NONE_STORED) else      # Amendment 6: the folder was taken away, and the inbox's claim brought the notice here
                   "\n\nNo check was run.  This is not a pass.  The stored baseline should be inspected."))
    # Amendment 2.  The name is the time to the second, the verdict and eight digits of the design's hash, so two results
    # could share it, and the second was written over the first.  A notice is now created, never replaced: a second
    # result with the same name gets a number after it.  It is written as UTF-8 whatever the process's locale.
    for n in range(1, 100000):
        name = f'{stem}.txt' if n == 1 else f'{stem}_{n}.txt'
        try:
            with open(box / name, 'x', encoding='utf-8') as f:
                f.write(body + '\n')
            return name
        except FileExistsError:
            continue
    raise OSError(f'no free name for a notice beginning {stem}')


def verify(baseline_sha256: str, design) -> dict:
    _ledger('called', baseline_sha256=baseline_sha256 if isinstance(baseline_sha256, str) else None, design=design)
    if not isinstance(baseline_sha256, str) or len(baseline_sha256) != 64 or not set(baseline_sha256) <= HEX:
        result, card = _refusal(baseline_sha256, design, 'the request does not name a baseline'), None
    else:
        directory = HOME / 'baselines' / baseline_sha256
        if _held(baseline_sha256):
            _claim(baseline_sha256)                       # Amendment 6: any run on a baseline the service holds, a pass too, claims its inbox
        try:
            envelope = load_envelope(directory / 'baseline.json', ENGINEER_KEYS)
            if envelope['baseline_sha256'] != baseline_sha256:
                raise ValueError('the directory holds another baseline')
            card = envelope['card']
        except OSError as exc:
            # Amendment 2.  Fixed words: the error's own text holds the path of the service's folder, which went into the
            # signed verdict, the answer and the notice.  Amendment 6: when nothing at all is stored under the hash, the
            # words say that, and not that a stored file could not be opened.
            stored = not (isinstance(exc, FileNotFoundError) and not _held(baseline_sha256))
            result, card = _refusal(baseline_sha256, design, 'no signed baseline with this hash is held by the verification service '
                                    + ('(the stored file could not be opened)' if stored else NONE_STORED)), None
        except (OSError, ValueError, KeyError, TypeError) as exc:
            result, card = _refusal(baseline_sha256, design, f'no signed baseline with this hash is held by the verification service ({str(exc)[:120]})'), None
        except Exception as exc:
            # Amendment 2 (12 November 2026).  A stored file that is JSON but not a card left this function by an exception
            # the clause above does not name: BaselineInvalid for a part that is missing, AttributeError for a part of the
            # wrong kind, RecursionError for a file nested too deep.  The gate host then signed "unknown" with no result,
            # the run read as interrupted, and nobody was told.  Whatever makes the stored baseline unusable, the answer
            # is the same signed UNKNOWN and the engineer is sent it.  The words are fixed: the exception's own text can
            # quote the changed file, and nothing from that file goes into a verdict or a notice.
            result, card = _refusal(baseline_sha256, design, 'no signed baseline with this hash is held by the verification service: the stored file is not '
                                    f'a baseline card ({NOT_A_CARD.get(type(exc).__name__, "it could not be read")})'), None
        else:
            crash_point('verify_running')                 # tests: the host dies after admission and before a verdict exists
            result = _decide(directory, card, design)
    notice = _notify(card, baseline_sha256, result) if result['verdict'] != 'PASS' and isinstance(result['baseline_sha256'], str) and len(result['baseline_sha256']) == 64 and set(result['baseline_sha256']) <= HEX else None
    _ledger('verdict', baseline_sha256=result['baseline_sha256'], design_sha256=result['design_sha256'], verdict=result['verdict'], reason_code=result['reason_code'], notice=notice)
    return result


_claim_all()                                              # Amendment 6


TOOLS = {
    'verify': ('Decide one design against one baselined requirement and return a signed PASS, FAIL or UNKNOWN with the reason.',
               {'type': 'object', 'properties': {'baseline_sha256': {'type': 'string'}, 'design': {'type': 'object'}}, 'required': ['baseline_sha256', 'design']},
               verify),
}
