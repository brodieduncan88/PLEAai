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
                                 engineer.  The assistant does not write it and is not asked to pass it on.
  ledger.jsonl                   one line per call and per verdict, outside every PLEA store, for tests

VERIFY_ENGINEER_KEYS is the comma-separated list of engineer public keys this gate accepts baselines from.  A baseline
is read and its signature checked on every call, so a card changed after signing is refused, not used.
"""
import json
import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from plea_gateway.faults import crash_point            # noqa: E402
from baseline import REASONS, VERDICT_FORMAT, design_hash, evaluate, face   # noqa: E402
from verify_record import load_envelope                # noqa: E402

HOME = pathlib.Path(os.environ['VERIFY_HOME'])
ENGINEER_KEYS = tuple(k for k in os.environ.get('VERIFY_ENGINEER_KEYS', '').split(',') if k)
LEDGER = HOME / 'ledger.jsonl'
HEX = set('0123456789abcdef')


def _ledger(event: str, **fields) -> None:
    with LEDGER.open('a') as f:
        f.write(json.dumps({'event': event, 'pid': os.getpid(), 't': time.time(), **fields}) + '\n')


def _refusal(baseline_sha256, design, detail: str) -> dict:
    """A signed UNKNOWN for a request that names no usable baseline.  There is no card, so there are no criteria."""
    return {'format': VERDICT_FORMAT, 'verdict': REASONS['BASELINE_MISMATCH'], 'reason_code': 'BASELINE_MISMATCH', 'requirement_id': None, 'revision': None,
            'baseline_sha256': baseline_sha256 if isinstance(baseline_sha256, str) else None, 'design': design, 'design_sha256': design_hash(design),
            'criteria': [], 'basis': '', 'detail': detail, 'check': None}


def _notify(card, baseline_sha256: str, verdict: dict) -> str:
    """One notice per FAIL or UNKNOWN, in the inbox of the baseline the request named.  With no usable card (it was
    changed, or signed by someone else) the notice says so in plain words; it never quotes the unusable card."""
    box = HOME / 'inbox' / baseline_sha256[:16]; box.mkdir(parents=True, exist_ok=True)
    name = f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}_{verdict['verdict']}_{verdict['design_sha256'][:8]}.txt"
    if card is not None:
        body = f"To: {card['responsible_engineer']['name']}\nFrom: the verification service (not the assistant)\n\n" + face(card, verdict)
    else:
        body = (f"To: the responsible engineer for baseline {baseline_sha256}\nFrom: the verification service (not the assistant)\n\n"
                f"UNKNOWN: A VERIFICATION RUN WAS ASKED FOR AND NO USABLE BASELINE IS HELD\n\nReason        {verdict['detail']}\n"
                f"Design        {json.dumps(verdict['design'], sort_keys=True)}\n\nNo check was run.  This is not a pass.  The stored baseline should be inspected.")
    (box / name).write_text(body + '\n')
    return name


def verify(baseline_sha256: str, design) -> dict:
    _ledger('called', baseline_sha256=baseline_sha256 if isinstance(baseline_sha256, str) else None, design=design)
    if not isinstance(baseline_sha256, str) or len(baseline_sha256) != 64 or not set(baseline_sha256) <= HEX:
        result, card = _refusal(baseline_sha256, design, 'the request does not name a baseline'), None
    else:
        directory = HOME / 'baselines' / baseline_sha256
        try:
            envelope = load_envelope(directory / 'baseline.json', ENGINEER_KEYS)
            if envelope['baseline_sha256'] != baseline_sha256:
                raise ValueError('the directory holds another baseline')
            card = envelope['card']
        except (OSError, ValueError, KeyError, TypeError) as exc:
            result, card = _refusal(baseline_sha256, design, f'no signed baseline with this hash is held by the verification service ({str(exc)[:120]})'), None
        else:
            crash_point('verify_running')                 # tests: the host dies after admission and before a verdict exists
            result = evaluate(directory, card, design)
    notice = _notify(card, baseline_sha256, result) if result['verdict'] != 'PASS' and isinstance(result['baseline_sha256'], str) and len(result['baseline_sha256']) == 64 and set(result['baseline_sha256']) <= HEX else None
    _ledger('verdict', baseline_sha256=result['baseline_sha256'], design_sha256=result['design_sha256'], verdict=result['verdict'], reason_code=result['reason_code'], notice=notice)
    return result


TOOLS = {
    'verify': ('Decide one design against one baselined requirement and return a signed PASS, FAIL or UNKNOWN with the reason.',
               {'type': 'object', 'properties': {'baseline_sha256': {'type': 'string'}, 'design': {'type': 'object'}}, 'required': ['baseline_sha256', 'design']},
               verify),
}
