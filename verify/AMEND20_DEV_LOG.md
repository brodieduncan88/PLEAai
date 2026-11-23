# Amendment 20: development log (23 November 2026)

Private working material. Internal work by the author under the owner's decisions of 23 November 2026. Not an independent
validation. Branch `amend20-2026-11-23`, on `555f2c6` (Amendment 19's results). Every entry is kept as it was written.

## Entry 1. The tests and the planted defects, with what they are expected to show on the uncorrected code (declared before they are run)

**Origin.** An external AI review of `b97fe6b` (a different system's, read-only; kept separately) found, among others, F-1, F-2, F-4
and F-9. The author reproduced F-1 and F-2 in process (`tests/amend19_dev_evidence/ext_triage/`). The owner decided on 23
November: these four go to this amendment; F-1 includes the card rule (bounds written as text); F-2 covers the offline checker,
the front door and the command line; F-4 takes only the `-0` and the bounded reason (no `MAX_PLAIN`); F-3 and F-5 to F-8, F-10
and F-11 are not in this amendment.

**Tests written first (this commit has no change to any code under `verify/`).**
- `tests/verify_tests.py`: R36, six checks: (1) a card's bounds written as numbers are read as the decimals they say; (2) the
  design space the same, in the service and the checker; (3) the card's rule: bounds as text; (4) `-0` and a bounded reason; (5)
  `check_record.py --design` reads a released file strictly; (6) a verdict for 3.0 where 3 was sent is rejected.
- `tests/verify_front_tests.py`: F40, five checks: the front door and the command line refuse a number a binary float holds as
  another, and a repeated key; they decide a number a float holds as written; a multi-line file is sent as it is.
- `tests/amend17_mutants.py`: fifteen defects, each planted in the corrected code and expected to be caught by R36 or F40.

**Expected on the code of `555f2c6` (Amendment 19's), before any correction. Run once, kept as it comes out, whatever it shows:**
- R36: all six checks false (the faults are all present). Two caveats stated before the run: check 4's first half may be true
  or false (whether `normalize` of the tiny negative value gives a negative zero is the review's claim, not yet seen here); and
  check 6 is false only if no other check of the record already rejects the forged verdict.
- F40: checks 1, 2 and 5 false; checks 3 and 4 true.

If a prediction does not hold it is recorded here as it came out, and the test or the expectation is changed only in a new,
dated entry.

## Entry 2. What the run on the uncorrected code showed; one fault in R36's own set-up, restated before the correction (23 November 2026)

**The run** (once, on `bc6d865`, whose code under `verify/` is Amendment 19's; kept as it came out in
`tests/amend20_dev_evidence/before_bc6d865/`):
- R36: all six checks false, as predicted. Seen: a value of 0.29999999999999999 against a plausible minimum of 0.3 is PASS; a
  design 99999999999999995000000 is inside a space from 1e23 to 2e23, and the exact edges 0.1 and 0.3 are outside theirs, in the
  service and in the checker; the underflowing value is written '-0' by both (the review's claim holds); a 500000-character
  answer where a number was due gives a reason of 500064 characters; `check_record.py --design` exits 0 on 2.5000000000000001
  and on a repeated key; a verdict signed for 3.0 where 3 was sent verifies, with no check failed (so the review's F-9 holds).
- F40: checks 1, 2 and 5 false, 3 and 4 true, as predicted. Seen: five numbers a binary float holds as another were each run;
  the command line ran both a rounded number and a repeated key; eight official runs, not five.

**A fault in R36's own set-up, found in that run.** Check 3 drew its card from `draft()`, which is the fixture's case card, not
a whole baselined card: `validate_card` refused it first for its format, whatever it was asked about. Check 3 was false for
that reason as well as for the right one, and on corrected code it would have been false for that reason alone. The set-up
now takes the card as it was baselined (the stored envelope's card). Nothing else in the test is changed, and no predicate is
loosened: the same four numeric refusals are asked for, and the baselined card, in text, is still asked to be accepted.
R36 is run again on the uncorrected code with this change (expected: all six false, check 3 now for the right reason), and
that run is kept beside the first.
