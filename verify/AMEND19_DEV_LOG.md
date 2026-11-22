# Amendment 19: development log

22 November 2026. Private working material. Branch `hardening/prepentest-2026-11-22`, from `2c1af26`. Times are UTC.

Internal work by the author, under the owner's decision "Amendment 19 and Stage B Security Review" of 22 November 2026,
point 1. It is not an independent validation. VP-1 to VP-6 apply. Amendments 17 and 18, their declarations, official
results and hashes, and the frozen commits `0da1a85e` and `d208f6e`, are not changed. D20-F is treated as provisionally
high in severity.

## Entry 1. The counterexample, before any correction

**The matrix probe.** `tests/amend19_dev_evidence/matrix/d20f_matrix.py` (SHA-256 `5d5480438bee…`) was committed
(`9ba0f88`) before it was run.
- **On the uncorrected tree (`2c1af26`)** its 'before' predictions held (`before_2c1af26.out`). On the gate's own decision
  path, every JSON number on the wrong side of the limit, nearer to it than a binary float resolves, is signed PASS with
  achieved `200`, and the record's checker accepts it:
  - against "at least 200": 199.99999999999999, 199.999999999999999, 1.9999999999999999e2, a 28-digit 199.99…9, a
    32-digit 199.99…9, and a 1,000-digit 199.99…9;
  - against "at most 200": 200.00000000000001 and 2.0000000000000001e2;
  - against "at least -5": -5.00000000000000001.
- The same values given as JSON strings are decided exactly. Tokens beyond a float's range (1e999999, NaN, Infinity) are
  UNKNOWN, and a token below it (1e-999999) became 0.0.

**R35, the end-to-end counterexample.** R35 is new in `tests/verify_tests.py`.
- A deployment with the front door baselines a check that prints its table's text as a JSON number. A job sends three
  designs: one whose value is 199.99999999999999, one at exactly 200, and one at 200.00000000000001. The record is built
  and verified offline with `check_record.verify`.
- It also puts 22 printed numbers on three criteria to the gate's decision path in process.

**Declared before R35 is first run (VP-5).** `tests/verify_tests.py` has SHA-256 ``bbc884b8ce4d44ffaef3e4a8ff68d16c62574b1ade1a5e1ec6cedafe4121d778``. Expected on the
uncorrected code: R35 fails all three checks.
- Check 1: the 199.99999999999999 design is signed PASS with achieved `200`, and the record verifies offline. This is the
  signed false PASS the owner asks to keep.
- Check 2: the value above the limit is held as `200`, not as printed.
- Check 3: the in-process matrix gives false PASSes.

That run is kept as the original failing evidence.
