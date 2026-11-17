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
  undelivered/<full hash>/       a notice the inbox could not take (a full disk, a permission, a file in its place, or an
                                 inbox made by another account): kept here, and listed by the engineer's console (Amendment 7)
  inbox_checks/<full hash>.json  this tool's inbox-writability check for that baseline: whether it could write a test file in
                                 the inbox, with the time; made when the tool starts, on every run, and on a look of its own
                                 for a baseline that has none (Amendment 8; named so by Amendment 9: it does not show delivery)
  ledger.jsonl                   one line per call, per verdict and per notice, outside every PLEA store, for tests

The verdict says where its notice went, in its field notice: INBOX, UNCLAIMED, UNDELIVERED or NOT_WRITTEN, or NO_HASH when
the request names no usable hash (Amendment 7).  A verdict is returned whatever happens to its notice.

VERIFY_ENGINEER_KEYS is the comma-separated list of engineer public keys this gate accepts baselines from.  A baseline
is read and its signature checked on every call, so a card changed after signing is refused, not used.
"""
import json
import os
import pathlib
import sys
import threading
import time
import unicodedata

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from plea_gateway.faults import crash_point            # noqa: E402
from baseline import REASONS, VERDICT_FORMAT, _blank, _verdict, design_hash, design_lines, evaluate, face   # noqa: E402
from check_record import in_design_space as inside_as_checked, rederive   # noqa: E402  (Amendment 2: the record's checker is asked before a verdict is returned)
from verify_record import load_envelope                # noqa: E402
import notices                                         # noqa: E402  (Amendment 7: where a notice goes, and how it is kept)

HOME = pathlib.Path(os.environ['VERIFY_HOME'])
ENGINEER_KEYS = tuple(k for k in os.environ.get('VERIFY_ENGINEER_KEYS', '').split(',') if k)
LEDGER = HOME / 'ledger.jsonl'
HEX = set('0123456789abcdef')
NOT_A_CARD = {'BaselineInvalid': 'a part of it is missing or is not as a card needs it', 'AttributeError': 'a part of it is the wrong kind of value',
              'RecursionError': 'it is nested too deeply to read'}


def _seconds(name: str, default: float) -> float:
    try:
        return max(0.0, float(os.environ.get(name, default)))
    except ValueError:
        return default


# Amendment 8 (16-17 November 2026).  The tool shows that it can write each baseline's inbox, and records it (notices.prove).
# The look is never off, and a good proof is made again well inside the time for which it stays good: while a proof is not good
# no run is admitted, so only the look can make it good again.
PROOF_SCAN = min(10.0, max(0.1, _seconds('VERIFY_PROOF_SCAN', 1.0)))                         # seconds between this tool's own looks
PROOF_REFRESH = min(notices.DELIVERY_MAX_AGE / 3, _seconds('VERIFY_PROOF_REFRESH', 30.0))    # seconds after which a good proof is made again
PROOF_GRACE = 10.0                                       # seconds for which a new baseline's inbox is left for the console to make
_PROVED = {}                                             # this process's memory of its own proofs: hash -> (time, good)
_SAID = {}                                               # what was last said on the error output about each baseline's proof


def _report(found: dict) -> None:
    """Remember a proof this process made, and say so on the error output when a baseline's inbox stops being writable, when its
    proof cannot be recorded, and when either is put right.  Nothing is raised.  (Amendment 8.)"""
    try:
        h = found['baseline_sha256']
        state = 'inbox' if not found['inbox'] else ('record' if not found['recorded'] else 'good')
        _PROVED[h] = (found['checked_at'], state == 'good')
        was = _SAID.get(h); _SAID[h] = state
        if state == was or (state == 'good' and was is None):
            return
        words = {'inbox': f'CANNOT WRITE THE INBOX of baseline {h[:16]}…: its notices go to the service\'s own store, and new runs for it are refused at the front door',
                 'record': f'CANNOT RECORD THE INBOX-WRITABILITY CHECK for baseline {h[:16]}…: enrolment and new runs for it are refused until it can',   # Amendment 9: the name
                 'good': f'the inbox of baseline {h[:16]}… can be written again, and the inbox-writability check is recorded'}[state]
        print(f'verify tool: {words}', file=sys.stderr, flush=True)
    except Exception:                                    # an error output that fails, or is closed, does not reach a run
        pass


def _prove(baseline_sha256: str, make: bool = True) -> None:
    """Prove delivery for one baseline now, and remember it.  Nothing here can reach a run.  (Amendment 8.)"""
    try:
        _report(notices.prove(HOME, baseline_sha256, make))
    except Exception:
        pass


def _ledger(event: str, **fields) -> None:
    """One line of the ledger, which is kept for the tests.  A ledger that cannot be written is said so on the error output and
    does not stop a run: the verdict is the decision, and the ledger only records it.  (Amendment 7.)"""
    try:
        with LEDGER.open('a') as f:
            f.write(json.dumps({'event': event, 'pid': os.getpid(), 't': time.time(), **fields}) + '\n')
    except OSError as exc:
        try:
            print(f'verify tool: the ledger could not be written ({type(exc).__name__})', file=sys.stderr, flush=True)
        except Exception:                  # the error output may fail too, or be closed; the run goes on (Amendments 7 and 8)
            pass


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


NONE_STORED = '(none is stored under this hash)'    # Amendment 6: how the reason ends when nothing at all is stored under the hash


def _body(card, baseline_sha256: str, verdict: dict, engineer: bool) -> str:
    """The text of the notice for a verdict that is not a pass, in the words the service has written since Amendments 3 and 6."""
    if card is not None:
        return f"To: {card['responsible_engineer']['name']}\nFrom: the verification service (not the assistant)\n\n" + face(card, verdict)
    if not engineer:                                     # Amendment 6: no engineer holds this hash, and the notice does not say one does
        return (f"To: no engineer: the verification service found no baseline folder for the hash {baseline_sha256}, and read it in no inbox\n"
                f"From: the verification service (not the assistant)\n\n"
                f"UNKNOWN: A VERIFICATION RUN WAS ASKED FOR AND NO USABLE BASELINE IS HELD\n\nReason        {verdict['detail']}\n"
                + '\n'.join(design_lines(None, verdict['design']))
                + "\n\nNo check was run.  This is not a pass.  This notice is kept by the service and sent to nobody.")
    return (f"To: the responsible engineer for baseline {baseline_sha256}\nFrom: the verification service (not the assistant)\n\n"
            f"UNKNOWN: A VERIFICATION RUN WAS ASKED FOR AND NO USABLE BASELINE IS HELD\n\nReason        {verdict['detail']}\n"
            + '\n'.join(design_lines(None, verdict['design']))          # Amendment 3: marked as sent, in quotes and cut; no baseline is held to set it against
            + ("\n\nNo check was run.  This is not a pass.  Nothing is stored under this hash; the baseline should be restored, or a revised one issued."
               if verdict['detail'].endswith(NONE_STORED) else      # Amendment 6: the folder was taken away, and the inbox's claim brought the notice here
               "\n\nNo check was run.  This is not a pass.  The stored baseline should be inspected."))


def _fixed_body(baseline_sha256: str, verdict: dict, engineer: bool) -> str:
    """A notice in fixed words, for a verdict whose notice cannot be built from the card.  It names the verdict and its reason
    code, and repeats no text from the card or from the design.  (Amendment 7.)"""
    to = (f"To: the responsible engineer for baseline {baseline_sha256}" if engineer else
          f"To: no engineer: the verification service found no baseline folder for the hash {baseline_sha256}, and read it in no inbox")
    return (f"{to}\nFrom: the verification service (not the assistant)\n\n"
            f"{verdict['verdict']}: A VERIFICATION RUN GAVE THIS RESULT, AND ITS NOTICE COULD NOT BE SHOWN IN FULL\n\n"
            f"Reason code  {verdict['reason_code']}\n\n"
            "The notice could not be built from the baseline, so the text of the baseline and of the design is left out.  "
            "The reason code above is the verification service's own.  This is not a pass.")


def _write(card, baseline_sha256: str, verdict: dict):
    """Write the notice for a verdict that is not a pass, where it can be written.  Returns (where it went, its file name or None).  (Amendment 7.)"""
    stem = f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}_{verdict['verdict']}_{verdict['design_sha256'][:8]}"

    def text(engineer: bool) -> str:
        try:
            return _body(card, baseline_sha256, verdict, engineer)
        except Exception:                                # a card the text cannot be built from does not lose the notice
            return _fixed_body(baseline_sha256, verdict, engineer)
    state, name = notices.deliver(HOME, baseline_sha256, stem, text)
    _ledger('notice', baseline_sha256=baseline_sha256, state=state, name=name)
    return state, name


def _notify(card, baseline_sha256: str, verdict: dict) -> str:
    """The file name of the notice for a verdict, kept for the tests of how names are given: a notice is never replaced, and five of one
    name in one second get five names.  Raises OSError if no place takes it.  (Amendment 2, kept by Amendment 7.)"""
    state, name = _write(card, baseline_sha256, verdict)
    if name is None:
        raise OSError('no place takes the notice')
    return name


def verify(baseline_sha256: str, design) -> dict:
    _ledger('called', baseline_sha256=baseline_sha256 if isinstance(baseline_sha256, str) else None, design=design)
    if not isinstance(baseline_sha256, str) or len(baseline_sha256) != 64 or not set(baseline_sha256) <= HEX:
        result, card = _refusal(baseline_sha256, design, 'the request does not name a baseline'), None
    else:
        directory = HOME / 'baselines' / baseline_sha256
        if notices.held(HOME, baseline_sha256):
            notices.claim(HOME, baseline_sha256)           # Amendment 6: any run on a baseline the service holds, a pass too, claims its inbox
            _prove(baseline_sha256)                        # Amendment 8: and shows again whether its inbox can be written
        elif notices.inbox_for(HOME, baseline_sha256)[1]:
            _prove(baseline_sha256, make=False)            # Amendment 8: its folder is gone, and its inbox still holds its hash and takes its notice
        try:
            envelope = load_envelope(directory / 'baseline.json', ENGINEER_KEYS)
            if envelope['baseline_sha256'] != baseline_sha256:
                raise ValueError('the directory holds another baseline')
            card = envelope['card']
        except OSError as exc:
            # Amendment 2.  Fixed words: the error's own text holds the path of the service's folder, which went into the
            # signed verdict, the answer and the notice.  Amendment 6: when nothing at all is stored under the hash, the
            # words say that, and not that a stored file could not be opened.
            stored = not (isinstance(exc, FileNotFoundError) and not notices.held(HOME, baseline_sha256))
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
    notice_name = None
    if result['verdict'] != 'PASS':                       # Amendment 7: the verdict says where its notice went; a notice that cannot be written does not undo it
        h = result['baseline_sha256']
        if isinstance(h, str) and len(h) == 64 and set(h) <= HEX:
            result['notice'], notice_name = _write(card, h, result)
        else:
            result['notice'] = 'NO_HASH'
    _ledger('verdict', baseline_sha256=result['baseline_sha256'], design_sha256=result['design_sha256'], verdict=result['verdict'], reason_code=result['reason_code'], notice=notice_name, notice_state=result.get('notice'))
    return result


notices.claim_all(HOME)                                   # Amendment 6, as the tool starts (the work is in notices.py, Amendment 7)
try:                                                      # Amendment 8, as the tool starts; nothing here can stop it starting
    notices.sweep_all(HOME)                               # temporary files a killed process left in an inbox, the store or the proofs
    for _found in notices.prove_due(HOME, _PROVED, 0.0):  # every baseline whose notices go to an inbox gets its inbox-writability check
        _report(_found)
except Exception:
    pass


def _watch() -> None:
    """This tool's own look, every PROOF_SCAN seconds: a baseline made since the tool started, one whose inbox could not be written,
    and one whose proof is older than PROOF_REFRESH seconds are each proved again.  Nothing here can stop a run.  (Amendment 8.)"""
    while True:
        time.sleep(PROOF_SCAN)
        try:
            for found in notices.prove_due(HOME, _PROVED, PROOF_REFRESH, PROOF_GRACE):
                _report(found)
        except Exception:
            pass


if not any(t.name == 'verify-delivery-proof' for t in threading.enumerate()):      # one look per process, however often the tool is loaded
    threading.Thread(target=_watch, name='verify-delivery-proof', daemon=True).start()


TOOLS = {
    'verify': ('Decide one design against one baselined requirement and return a signed PASS, FAIL or UNKNOWN with the reason.',
               {'type': 'object', 'properties': {'baseline_sha256': {'type': 'string'}, 'design': {'type': 'object'}}, 'required': ['baseline_sha256', 'design']},
               verify),
}
