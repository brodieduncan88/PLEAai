# Verification record plug-in: declaration before the official test run

11 November 2026. Private working material.

This file is committed before the official run of `tests/verify_tests.py`. It fixes the code, states what each test
is expected to show, and records what was done in development. The official run is made once after this commit and
its first result is kept, pass or fail. A later correction would be a separate, dated amendment.

## What is fixed

Base: `main` at `b4503ba` (PLEA gateway v1.2.1). No v1.2.1 file is changed on this branch.

| file | sha256 |
| --- | --- |
| `verify/baseline.py` | `1e1044a8efa2b6f037960a6cfa7f9889b2565ae48a9fec3981da80ba4ada672f` |
| `verify/verify_tools.py` | `33a6b31c1650eb7367baeefc1a82143cac8f205f8206eeacba0a993a1f2d86aa` |
| `verify/verify_client.py` | `4219b01d8d083b4ec1a230024054f7957814ed15d6e9bdedbd222ea507416e12` |
| `verify/verify_ctl.py` | `5aff8ef0de7097f57b32da6fb445b572ab7cfce6438f20c2edbbc6f7d487075c` |
| `verify/verify_record.py` | `7fc8c168bf57f400434abbdf236eae399901a503db7106e33b6ac633588e38f3` |
| `verify/check_record.py` | `fb4a44cba9d8463b926c34aa0c00b499c06421b0c6e11a93224f11f1d0d9ddde` |
| `verify/deploy.py` | `8836e99f608ee081aefc599c999d0f8a8d1073777266813a9f646fe631158003` |
| `tests/verify_tests.py` | `6b24ecc12979c8829c66d78c3828e5871b4232affe130ce94e738145cea796f1` |
| `tests/verify_case/card.json` | `40fe6b63169639aed9b3312c18ccc5f37e5c9b18b17ce6318fa0c75160f47256` |
| `tests/verify_case/check.py` | `00046e4ecd2534e0c71bcba6143e6e74ffb5578d9fe2b9c1679b9929bf4ee533` |
| `tests/verify_case/materials.csv` | `25d233871cecb9994aa2cea27f69bcd0092f12ba7b2ab85171333eb502746c2d` |

Environment: Python 3.11, cryptography 50.0.2, psycopg 3.3.8, PostgreSQL 16, one machine, all services on 127.0.0.1.

## What each test is expected to show

Each test makes a fresh deployment (new keys; the released witness service and gate host, unchanged, under mutual
TLS, the gate host loading `verify_tools`), baselines the self-test fixture in `tests/verify_case/` as the responsible
engineer, and acts as the assistant through `verify_client.py`. The fixture is a toy (a material's rated temperature
against a 200 C limit); it tests the plug-in, not engineering. A test passes only if every check listed is true.

**R1. A design that does not meet the requirement gets a signed FAIL with the reason, kept on the record and sent to the engineer.**
- the assistant is told FAIL, with the required and achieved values (exit status 2)
- the record holds the FAIL with reason LIMIT_NOT_MET, 180 against 200, margin -20
- the record verifies offline and its status is NOT VERIFIED
- one notice is in the engineer's inbox, from the service, naming the failure

**R2. The same design sent again returns the same verdict: one run, one notice.**
- both answers are the same FAIL
- the check ran once and one notice was sent
- the record shows one official run

**R3. A design outside the baselined design space is a FAIL, and the check is not run on it.**
- each is answered FAIL: DESIGN OUTSIDE THE BASELINE (exit status 2)
- the record holds four FAILs with that reason and no achieved value
- each was sent to the engineer and the status is NOT VERIFIED

**R4. A design that meets the check after two that did not: met for that design only, and the failures stay on the record.**
- the three runs answer FAIL, FAIL, met (exit 2, 2, 0)
- the status is DECLARED CHECK MET with both failures still counted
- it is met for that exact design only
- the two failures were sent to the engineer and are still open

**R5. A check, a data file or a card changed after baselining gives UNKNOWN, never a pass.**
- changed data gives UNKNOWN (exit status 3), not a pass
- a changed check gives UNKNOWN
- a stored card with a relaxed limit is not used
- with the files restored the same requirement still fails
- no run met the check, the record verifies and the status is NOT VERIFIED
- all five results were sent to the engineer

**R6. A check that crashes, prints rubbish, returns not-a-number, zero or an absurd value, or hangs, gives UNKNOWN with its reason.**
- each answers UNKNOWN (exit status 3)
- the record gives each its reason
- a check that hangs is stopped and is UNKNOWN
- a material that would have passed is not a pass when the check misbehaves
- every UNKNOWN was sent to the engineer

**R7. The service dying part-way through a run leaves it counted, without a verdict, and never run again.**
- the host died during the run (exit 137) and the assistant was not told it passed
- asked again, twice, the answer is UNKNOWN: interrupted (exit status 3)
- the check was started once for that design and never produced a verdict
- the record shows it INTERRUPTED and counted, and that design is not verified
- a different design can still be verified

**R8. A baseline is refused unless its check is seen to fail a bad design and pass a good one.**
- seven defective baselines are refused, each with its reason
- the sound one is baselined, and only it is stored

**R9. The record verifies offline; an edited one does not, even when re-signed with the engineer's key.**
- the record verifies, by library and by command line
- without keys given it says consistent, not verified
- every single-value edit fails
- a wrong engineer key fails
- re-signed with the engineer's key, edits verify only where the engineer alone is the source

**R10. A requirement changes only as a new, signed baseline that says what it replaced and what had failed.**
- a revision with no reason is refused
- the old baseline takes no further runs (exit status 4, nothing run)
- the new card says what it replaced and what had failed, counted by the console
- the design that failed on A meets the check on B, and B's record is headed CHANGED AFTER THE EVENT
- the old record still verifies and still shows the failure

**R11. What the assistant's side holds cannot do the engineer's part.**
- the gateway credential cannot provision a budget or stop one
- a relaxed baseline signed by another key is not accepted by the client
- even trusting that key, nothing is run: no budget exists for a baseline the engineer did not provision
- the real record is unchanged: one run, NOT VERIFIED
- even with a budget provisioned for it, a baseline the pinned engineer did not sign gets UNKNOWN, not a pass

**R12. The engineer's disposition of a failure is signed, shown on the record, and cannot be made by anyone else.**
- before the disposition the failure is open; after it, acknowledged
- a run that met the check takes no disposition
- a disposition signed by another key makes the record fail

**R13. A verdict that does not follow from its own numbers is rejected, even when the gate and the engineer have both signed it.**
- the honest record verifies
- the altered verdict, signed by the gate key and the engineer key, fails, and only at the re-derived verdict
- its status is NOT VERIFIED

Expected overall: 13 of 13 pass.

## What was done before this declaration

- The test file was run in full twice and in part twice during development. The first full run passed 8 of 12.
- Two failures were real and the code was changed: the offline checker rejected an honest record that held a refusal
  for want of a usable baseline, and no notice was sent to the engineer in that case. The checker now also re-derives
  each control case's verdict from its recorded numbers.
- Two failures were mistakes in the tests (a comparison of a number with a pair; a message cut short).
- Added after the first runs: R13 (a signed verdict that contradicts its own numbers) and the last check in R11.
- To check the tests can fail, ten deliberate defects were applied one at a time to a scratch copy. Nine were caught
  at first. The tenth (the gate accepting a baseline signed by any key) was missed, because no test reached that
  code with a budget in place; the last check of R11 was added for it and now catches it. `experiment/dev_mutants.json`
  holds the first pass.

## What is not tested

- The engineering. The checks used are a toy and one worked case; the plug-in cannot tell a right check from a wrong one.
- Separation by machine. Here every party runs under one operating-system account. An assistant with a shell on this
  machine could read the keys. The tests show separation by process and credential only.
- Work that never goes through the service. Nothing here can see it.
- Whether the design sent is the part that is built.
- The owner. One party holds the witness, gate and engineer keys; a party who rewrote everything is outside these tests.
- Any independent review.
