# Amendment 1 to the verification record plug-in: 11 November 2026

Private working material. This is a dated amendment made **after** the frozen declaration (`DECLARED_VERIFY.md`), the
official R1 to R13 run and the trial (`REPORT_VERIFY.md`). Those records, and every file they fix, are left exactly as
they were. This note records three defects found afterwards in that plug-in, says what each could and could not do,
and says what was done about them.

## How they were found

By me, the author, on 11 November 2026, while preparing an MCP server for the plug-in. None was found by the tests R1
to R13, by the ten deliberate defects planted in development, by the trial, or by a reviewer. The first came from
asking what stops a caller sending another baseline's hash. The second and third came from trying inputs on the first
plug-in that the new front door would have to refuse.

## Finding 1. The caller chose the baseline

**What.** `verify_client.py`, the assistant's command, holds the gateway's database credential and builds the run's
arguments itself, including `baseline_sha256`. The budget a run is charged to is named for one baseline. The gate's
tool, `verify_tools.verify`, is given the arguments and not the budget's name, so it cannot tell that the two differ.
A caller holding what the assistant's workspace held could reserve a run on baseline A's budget and send arguments
that name baseline B.

**Reproduced by test F1.** A design that fails a 200 C requirement (A) is sent, on A's budget, naming a relaxed copy
at 170 C (B). The gate signs PASS for B. The run is charged to A; B shows no run; no notice is sent, because a pass
sends none.

**What it could do.** Give the caller a signed PASS for a design that does not meet the requirement its job is under.
Make the record of A unverifiable for good, including a record that already held failures.

**What it could not do.** Invent the relaxed baseline: the gate uses only baselines that a pinned engineer signed
(R11), so the choice is among those, such as another job's, an earlier or later revision, or a relaxed copy baselined
as new. Produce a record that verifies: `check_record.py` fails A's record at checks 5 and 6, because one of its runs
is bound to another baseline, and B's record holds no run. The rule "no record, not verified" still held.

**In the trial.** The six trials with the plug-in used the command as given. None did this.

## Finding 2. One malformed design broke a record

**What.** A design holding a character or a number that PostgreSQL's JSON type cannot store (a NUL in a name or a
value, an infinite number) was accepted by the client, run by the gate as a design outside the baseline, and signed.
Storing the result then failed. The client stopped with a traceback, exit status 1. The run stayed in the audit chain
as finished, with a signed verdict and no stored result.

**Reproduced by test F2.** After one such design, a good design still meets the check, but the record of that baseline
fails check 6 ("the gate signed a verdict, but none is given") and its status is NOT VERIFIED.

**What it could do.** Let one request, by slip or on purpose, leave a baseline's record unable to verify, whatever is
verified on it afterwards. The engineer would have to issue a revision to get a clean record.

**What it could not do.** Produce a pass. It fails closed.

A third input, half of a surrogate pair in a text value, gave an interrupted run where a FAIL was due. The record
still verified.

## Finding 3. A stored card that is no longer a card gives no notice

**What.** If `baseline.json` on the service machine is changed into something that is not a valid card,
`validate_card` raises `BaselineInvalid`, which `verify_tools.verify` does not catch (it catches the errors a changed
but valid card raises). The tool stops with an error where it should return a signed UNKNOWN.

**Effect.** The run is counted, is never a pass, and the record verifies. But the caller is told the run was
interrupted, which is not the reason, and no notice goes to the engineer. The white paper of 11 November says the
engineer is still notified when no usable baseline is held. That is true when the stored card is changed and is still
a card (R5), and not in this case.

**Shown by the last-but-one check of test F15,** which states the behaviour as it is.

## What was done

New files only, on the branch `verification-mcp-front-door`. No file fixed by `DECLARED_VERIFY.md` is changed.

- **A front door on the service's side** (`front_door.py`). It runs the governor and holds the gateway's database
  credential. A caller is known by its client certificate, which belongs to a job; the engineer signs a binding of the
  job to one baseline. No request names a baseline. The witness service and the gate host admit only the front door's
  certificate.
- **An MCP server with three tools** (`plea_verify_mcp.py`) and a command (`front_client.py`) for the assistant's
  side, which is given a folder with the job's certificate and nothing else.
- **A console for the engineer** (`front_ctl.py`) to enrol a job, move it to a revision, and revoke it.

**Finding 1 is closed for a caller that comes through the front door** (test F6). **Finding 2 is closed for a caller
that comes through the front door** (test F7): a request that is not a design is refused before anything happens.

**Neither is closed in the first client,** which is unchanged. It must not be what an assistant is given.
`deploy_front.py` starts the witness service and the gate host so that they refuse it. Closing finding 1 for every
caller needs the gate to see the budget a run was admitted under, which is a change to the gateway and is not made.

**Finding 3 is open.** The repair is one line in `verify_tools.py`, a declared file. It needs its own amendment and a
new run of R1 to R13. Through the front door the caller is at least told that the stored baseline could not be read
as the one the engineer signed.

## The tests

F1 to F16 in `tests/verify_front_tests.py`, declared in `DECLARED_FRONT.md` before the official run. The official run at commit `92f2d5d`, started 23:03:09 UTC on 11 November 2026: **16 of 16 passed, 83 of 83 checks.**
The record is `results_front_tests_official.json`; `REPORT_FRONT.md` gives the results.

## What earlier documents said that this corrects

- `README.md` and `REPORT_VERIFY.md` describe the first client as the assistant's route. It should not be.
- The technical white paper of 11 November said, in its section 8, that because the assistant holds no key it "could
  not change the question or the verdict". For the client as tested that was too strong: see finding 1. Revision 2 of
  the paper corrects it.
- The same paper says, in its section 6, that the engineer is still notified whenever no usable baseline is held.
  Finding 3 is an exception. `README.md` says a failure is sent straight to the engineer; that holds for every FAIL,
  and for every UNKNOWN but this one.

## Still open

Finding 3. The first client's two defects, for any caller that is given it. Everything `README_FRONT.md` lists under
"What it does not do". No outside review of any of this.
