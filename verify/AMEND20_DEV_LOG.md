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
