# Amendment 17: development log (22 November 2026)

Development runs made before the declaration of Amendment 17, and every change made to a test after it was run, under
the owner's rules VP-1 to VP-6 (`plan/GOVERNANCE_NOTE_2026-11-22.md`). Nothing here is an official run.

## Entry 1. R31, run 1, and the restated predicates

- **Run 1** (development; R30 and R31 only). R30 passed. R31 failed two of its checks.
- **What it showed.** Two designs given a 16-bit request key (case b), or a 16-bit attempt identity (case c), were refused
  as predicted: the second design was not run and was not told the first design's pass. The mechanism was not the one
  predicted:
  - The governor refused the second design itself (`RequestKeyReused`). The stored outcome of the shared attempt carries
    the nonce of the first design, and the nonce binds the arguments (`plea_gateway/governor.py`, `_replay`).
  - So the store's `ATTEMPT_BOUND_TO_OTHER_REQUEST` (predicted for case c) and the front door's new check of the design
    (predicted for case b) were never reached.
- **Kept (VP-2, VP-3).** The failing test file and run 1's output are in `tests/amend17_dev_evidence/r31_run1/`, with
  their SHA-256 in `SHA256SUMS` there. Run 1 was not against a declaration; its predictions were the test's own checks.
- **Changed (VP-4).** The diff is `tests/amend17_dev_evidence/r31_run1/CHANGE.diff`.
  - The checks of cases b and c now name the governor's refusal.
  - A case d is added, with the governor's replay guard taken out in the test's own process only, so the front door's
    check is reached and shown to refuse on its own.
  - No check was dropped. The security outcome checked (refused, not run, not told met) is the same.
- **Declared before run 2 (VP-5).** The test file is `tests/verify_tests.py` with SHA-256 `4b888b31b9ffe8e995a98566d99fdbc8781ad4923c50b2cc28854488db955d0b`. Expected:
  - R30 passes, 5 of 5 checks.
  - R31 passes, 6 of 6 checks: cases b and c are refused by the governor with `RequestKeyReused`; case d by the front
    door, "not for this design".
- **What this says about D21.** The white paper's claim that a collision of attempt identities can cause only a
  refusal is borne out at 16 bits, by the governor's nonce. It was not tested before. The consequence of a collision is a
  refusal of the second design for ever, which an assistant able to grind designs could aim at a chosen design. That is
  why the identity and the key are widened.

## Entry 2. The first full development runs of the gate and front suites, with A1

- **Run** (development; the gate suite R1 to R31 and the front suite F1 to F36, the code of A1 and the old client still in
  place). Gate: 29 of 31. Front: F1 failed, and the run went on. The gateway's own chain, run first on a fresh database,
  passed 22 of 22 stages.
- **R26 failed, and the fault was in the new code (`verify/check_record.py`, `identity_form`).** R26 makes, with the service's
  database role, an attempt named `!x`, whose design no record can give. The new rule read that name as of neither form,
  so every record of that budget failed check 5. A run whose design the record does not give cannot have its key or identity
  recomputed, and check 5 already passed it over. Corrected: only runs whose design the record gives decide the form. No
  test was changed for this.
- **R17 failed one check, on a length.** The print of a record whose reason is 440 characters long must stay on one row
  shorter than 450 characters. It was 460, because the attempt identity printed at the head of each row is now 67
  characters, not 18. Kept and restated under VP-2 to VP-5: entry 3.
- **F1 failed, as the change intends.** F1 is the attack D5 names, made through the first plug-in: it is now refused by the
  gate host (`BASELINE_NOT_ADMITTED_BUDGET`). It is retired by A4, with its property carried by R30.

## Entry 3. R17's bound on the length of a row, restated

- **Kept (VP-2, VP-3).** In `tests/amend17_dev_evidence/full_run1/`: the test file as run, the gate suite's output and
  console, and the gateway chain's console, with their SHA-256 in `SHA256SUMS`.
- **Changed (VP-4).** The diff is `CHANGE_R17.diff` there. The bound is raised by the 49 characters the attempt identity
  grew, from `< 450` to `< 450 + 49`. What the check is for is unchanged: a long reason with characters that cannot be
  printed is shown on one row, cut, and printable. The row held 460 characters; it would have held 411 with the earlier
  identity.
- **Declared before the next run (VP-5).** The test file has SHA-256 `43881a0517760a8e6b513f2d0abe7ba6b14bc0b18ff0a8b14b49ed8d41667b5f`. Expected:
  - every test of the gate suite passes except those A4 retires or migrates (declared in entry 4);
  - R17 and R26 pass with the old client still in place.
