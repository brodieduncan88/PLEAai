"""The vault's one tool, run by the gate host:  gate_host.py --tools vault_tools   (with PLEA_VAULT_HOLDOUT=DIR set).

score(submission_sha256, manifest_sha256, submitter) returns the result object the gate host signs:

    {"score": "0.87", "metric": "accuracy", "decimals": 2, "rows": N, "submission_sha256": ..., "manifest_sha256": ...}

The gate host runs it at most once per attempt, behind the witness's receipts, like any other tool.  Before the sealed
labels are opened the tool repeats the front door's checks, from public information only: the manifest hash is this
holdout's, the stored file hashes to the name it was stored under, and the file is a valid submission.  Any failure
raises NoEffect, which the gate host reports as NO_EFFECT and the contract refunds up to the replacement allowance.  In
normal use that never happens, because the front door has already refused the upload; it covers a bypassed front door
and a file damaged on disk.  A sealed labels file that no longer matches the manifest is also NO_EFFECT: no score leaves.

Ledger.  Every call appends lines to PLEA_VAULT_LEDGER (default DIR/ledger.jsonl): "called", then "rejected" with a
reason, or "labels_opened" and "scored".  It is outside every PLEA store, so a test can count how often the labels were
really opened without trusting the accounting it is checking.

PLEA_CRASH_AT=vault_scoring makes the process die after the labels are opened and before a score exists (faults.py),
which is how the declared test kills a scoring run part-way.
"""
import json
import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from plea_gateway import NoEffect                      # noqa: E402
from plea_gateway.faults import crash_point            # noqa: E402
from holdout import HEX64, NAME, Holdout, LabelsDamaged, sha256_hex   # noqa: E402

HOLDOUT = Holdout(os.environ['PLEA_VAULT_HOLDOUT'])
LEDGER = pathlib.Path(os.environ.get('PLEA_VAULT_LEDGER', str(HOLDOUT.dir / 'ledger.jsonl')))


def _ledger(event: str, **fields) -> None:
    with LEDGER.open('a') as f:
        f.write(json.dumps({'event': event, 'pid': os.getpid(), 't': time.time(), **fields}) + '\n')


def _reject(reason: str, sha: str):
    _ledger('rejected', reason=reason, submission_sha256=sha)
    raise NoEffect()


def score(submission_sha256: str, manifest_sha256: str, submitter: str) -> dict:
    sha = submission_sha256 if isinstance(submission_sha256, str) else repr(submission_sha256)[:80]
    _ledger('called', submission_sha256=sha, submitter=submitter if isinstance(submitter, str) else None)
    if manifest_sha256 != HOLDOUT.manifest_sha256:
        _reject('MANIFEST', sha)
    if not (isinstance(submitter, str) and NAME.match(submitter) and isinstance(submission_sha256, str) and HEX64.match(submission_sha256)):
        _reject('ARGUMENTS', sha)
    try:
        data = HOLDOUT.upload_path(submitter, submission_sha256).read_bytes()
    except OSError:
        _reject('MISSING', sha)
    if sha256_hex(data) != submission_sha256:
        _reject('DAMAGED', sha)
    code, predictions = HOLDOUT.validate(data)
    if code is not None:
        _reject(code, sha)
    _ledger('labels_opened', submission_sha256=sha)       # from here on the labels are in this process
    try:
        labels = HOLDOUT.labels()
    except LabelsDamaged:
        _reject('LABELS_DAMAGED', sha)
    crash_point('vault_scoring')
    result = HOLDOUT.result(HOLDOUT.correct(predictions, labels), submission_sha256)
    _ledger('scored', submission_sha256=sha)               # the score itself is not written here
    return result


TOOLS = {
    'score': ('Score one uploaded predictions file against the sealed labels.',
              {'type': 'object', 'properties': {'submission_sha256': {'type': 'string'}, 'manifest_sha256': {'type': 'string'}, 'submitter': {'type': 'string'}},
               'required': ['submission_sha256', 'manifest_sha256', 'submitter']},
              score),
}
