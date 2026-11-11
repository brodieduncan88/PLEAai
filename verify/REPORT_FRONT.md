# Front door and MCP server: results

11 November 2026. Private working material. Internal evidence: written, run and checked by the same party.

## Summary

1. **Three defects were found in the first plug-in after its results were reported.** A caller could choose which signed
   baseline a design was decided against; one malformed design could leave a record unable to verify; and one kind of
   damage to a stored baseline gives no notice to the engineer. `AMENDMENT_2026-11-11.md` records them. None let a
   design that does not meet its requirement be shown as met by a record that verifies.
2. **A front door and an MCP server with three tools were built** beside the first plug-in, changing none of its files.
   The assistant's side now holds a certificate for its job and nothing else, and no request can name a baseline. The
   first two defects are closed for callers that come through the front door. The third is open.
3. **Its tests: 16 of 16, 83 of 83 checks, on the one official run.** 24 deliberate defects were planted one at a time in a copy: 23 were caught at first, and a check was added for the 24th before the declaration.
4. **What this does not show.** No assistant product and no assistant has used the tools: a test harness played the
   host application. Everything ran on one machine under one account. Nobody outside has reviewed it.

## 1. The official run

Official run at commit `92f2d5d`, the commit holding `DECLARED_FRONT.md`, started 23:03:09 UTC on 11 November 2026,
79.9 seconds. Record: `results_front_tests_official.json` (sha256 `6dc19fd3…8fad0a`).

| test | what it shows | checks |
| --- | --- | --- |
| F1 | The first client, no front door: a caller can run a design against another signed baseline and be told PASS; the record then fails checks 5 and 6 | 4 of 4 |
| F2 | The first client: one design the database cannot store leaves the record of its baseline unable to verify | 4 of 4 |
| F3 | Through the MCP server a failing design gets a signed FAIL with the reason, kept, sent to the engineer, and not marked as a tool error | 5 of 5 |
| F4 | The same design again, by tool or by command: one run, one notice | 4 of 4 |
| F5 | Exactly three tools; a call that is not exactly a design goes no further | 5 of 5 |
| F6 | A caller cannot choose the baseline: not as an argument, a field, a header, an address, or inside the design | 6 of 6 |
| F7 | Fourteen malformed requests are refused with no run, no audit row and no notice; a good design then verifies | 4 of 4 |
| F8 | The assistant's side holds no database credential and no signing key; its certificate is refused by the witness service and the gate host | 5 of 5 |
| F9 | Nothing the engineer does is offered to the assistant's side, by tool or by address | 4 of 4 |
| F10 | Only the enrolled certificate of an unrevoked job under a binding the engineer signed is answered; an earlier binding put back does not undo a revocation | 6 of 6 |
| F11 | A job moves only to a signed revision of its own baseline, which says what it replaced and what had failed | 6 of 6 |
| F12 | The service dying part-way leaves the run counted, without a verdict, never run again | 6 of 6 |
| F13 | Two jobs each see and charge only their own baseline; a second job for the same requirement needs a reason; pacing is per job | 5 of 5 |
| F14 | Both forms of the protocol; nothing but protocol on the output; one call is one request, with no retry | 7 of 7 |
| F15 | A stored baseline changed after signing is not shown; a design sent is decided UNKNOWN by the gate and sent to the engineer; the open defect behaves as described | 7 of 7 |
| F16 | One run at a time for a job; a check that does not finish is stopped and is UNKNOWN | 5 of 5 |

Every outcome matches the declaration. F1 and F2 pass because the defects they describe are present in the first
plug-in, which this branch does not change. One check of F15 states the open defect as it behaves.

After the official run the first plug-in's tests, R1 to R13, were run once on this branch as a check that nothing was disturbed: 13 of 13. That is not an official run of them; theirs is the one in `REPORT_VERIFY.md`.

Development history, including the mistakes in the tests and the weaknesses found in the new code before the
declaration, is in `DECLARED_FRONT.md`.

## 2. Planted defects

24 deliberate defects were applied one at a time to a scratch copy of the code. 23 were caught at first. M22 was missed, because no test reached the guard it removes; the last check of F12 was added for it before the declaration and catches it. The table is the first pass (`dev_front_mutants.json`).

| | defect | caught by, at first |
| --- | --- | --- |
| M1 | the front door honours a baseline named in the request | F5, F6 |
| M2 | the front door admits any certificate with the job's name (fingerprint not checked) | F10 |
| M3 | the front door does not check the engineer's signature on a binding | F10 |
| M4 | the front door ignores a revocation | F10 |
| M5 | the front door accepts an earlier binding put back | F10 |
| M6 | a job can be moved to any baseline (no revision needed) | F11 |
| M7 | a second job for the same requirement needs no reason | F10, F11, F13 |
| M8 | the front door does not check the characters of a design | F7 |
| M9 | the front door accepts a repeated name | F7 |
| M10 | the front door accepts a number that is not finite | F7 |
| M11 | the witness service and the gate host admit every certificate of the authority | F8 |
| M12 | the MCP relay tries a second time when the service cannot be reached | F14 |
| M13 | the MCP server offers a fourth tool | F5, F9, F14 |
| M14 | the MCP relay lets extra arguments through | F5, F6 |
| M15 | the MCP relay does not mark a refusal as an error | F7, F10, F11, F15, F16 |
| M16 | the front door lets a job run two designs at once | F16 |
| M17 | the MCP server sends structured content to a revision that has none | F14 |
| M18 | the front door does not pace a job | F13 |
| M19 | the front door runs a design sent to any address | F6, F9 |
| M20 | enrolment leaves the engineer's key in the job folder | F8 |
| M21 | the front door refuses before the gate is asked when the stored baseline was changed | F15 |
| M22 | the front door reports any error from the governor as an interrupted run | **not caught**; after the added check, F12 |
| M23 | a revoked job is ignored when a second baseline is opened for its requirement | F10 |
| M24 | the requirement shown does not say its baseline was stopped | F11 |

They were chosen by the party that wrote the code. They show the tests can fail; they do not show the tests are enough.

## 3. The demonstration

`demo_front.py`, transcript in `sample/front_demo_transcript.txt`. A script plays a host application on the pump-station
job. The best allowed design fails at 5.74 % against 5 %, and is the same run when sent again. Then, from the
assistant's side: a size outside the list is a FAIL on the record; a limit or a relaxed baseline passed as an argument
is refused by the relay, and by the front door when the request is written by hand; the job's certificate is refused
by the witness service and the gate host; a design the database could not store is refused with nothing recorded.
Then the legitimate way: the engineer revises, the old baseline takes no further runs, moving the job to a relaxed
copy that is not a revision is refused, the job is moved to the revision, and 120 mm2 meets the check under a record
headed "CHANGED AFTER THE EVENT".

## 4. Limits

- **MCP delivers a result; it does not account for it.** A host application may shorten or drop a tool's result and an
  assistant may misreport it. The record and the engineer's notice do not depend on either.
- **No host product and no assistant was run.** The trial in `REPORT_VERIFY.md` used the first client.
- **The first client still has the first two defects.** It must not be what an assistant is given.
- **The record's format is unchanged.** A second job for the same requirement needs the engineer's reason, which is in
  the service's signed log and not in the record. The log is signed line by line and is not chained.
- **The front door keeps the latest binding it has seen, its pacing counters and its locks in memory.** A restart
  forgets them.
- **A job's certificate is a bearer credential.** Renewing one is not built.
- **One machine does not show separation.** Here every party shares one account.
- Everything `REPORT_VERIFY.md` lists under its limits still holds.
