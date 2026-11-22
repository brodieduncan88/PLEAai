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

**R35's first run, on the uncorrected code (as declared).** R35 failed its three checks.
- Through the front door, the check printed 199.99999999999999 against "at least 200", and the gate signed **PASS**
  ("DECLARED CHECK MET") with achieved `200`. `check_record.verify` accepted the record, with no check failing.
- The record, rebuilt from the stopped deployment's stored data, is kept as
  `tests/amend19_dev_evidence/counterexample/record_2905c132c3cb97c9.json`, with the three public keys and the check and
  table that made it.
- `check_record.py` on that file alone ends with status 0: "RECORD VERIFIED … STATUS: DECLARED CHECK MET … 0 not met".
- The in-process matrix gave seven false PASSes.
- Kept in `tests/amend19_dev_evidence/counterexample/`.

## Entry 2. Where precision goes, and the two options

Traced in the code, at `2c1af26`:
1. **Raw output.** The check's standard output: bytes, at most 1 MiB (`sandbox.MAX_OUTPUT`).
2. **JSON parsing.** `baseline.evaluate`: `json.loads(...)` turns a JSON number into a binary float (about 17 significant
   digits), and `dec()` turns the float's shortest text into a decimal. **This is the loss of D20-F.** A JSON string goes
   through `dec()` as written, exactly.
3. **Comparisons.** `compare()` compares decimals, exactly. The margin is a subtraction under the decimal context (28
   significant digits).
4. **The verdict.** `achieved` and `margin` are written as plain decimal **strings** by `text()`, which normalises under
   the context (28 significant digits). No number of the check's is put in the verdict as a JSON number.
5. **`canonical(verdict)`.** `json.dumps(sort_keys=True, separators=(',', ':'))` writes the strings as given.
6. **PostgreSQL.** The result is stored in `results.result jsonb` through `plea_put_result`. Strings are kept exactly.
   The gate's signed report names the result's digest, which the record's checker recomputes.
7. **`check_record.py`.** It reads `achieved` and `margin` as strings and re-derives `met` and the margin
   (`rederive`), with the same 28-digit context.

So the record's form already holds decimals exactly as strings. The only losses are step 2 for JSON numbers, and step 4
for values of more than 28 significant digits. For the second, `rederive` already refuses a verdict whose written
values do not give the same decision or the same margin. The gate then answers UNKNOWN, CHECK_OUTPUT_INVALID: an
existing reason code, accepted by the record's checker as it stands.

**Option A**, the record's contract kept: read JSON numbers as decimals (`parse_float=decimal.Decimal`), compare exactly,
and keep `rederive`'s refusal where the 28-digit form would write a value otherwise than as decided.
- No schema, canonical form, signed field or reason code changes.
- A value of more than 28 significant digits far from its limit is still written rounded. This is the residue the
  register gives for D20, not decision-relevant.

**Option B**, exact tokens through the whole record: writing a value of more than 28 significant digits exactly would
change `text()` in the service and in `check_record`, and with it the signed bytes of such verdicts and the checker's
recomputation of margins. That is a new numerical contract. Under the owner's point 1.4 it is **not implemented**, and
it is put to the owner.

**Implemented: Option A** (`verify/baseline.py`):
- `evaluate` reads with `json.loads(..., parse_float=decimal.Decimal)`;
- `dec()` takes a `decimal.Decimal`;
- no float is made from a decimal anywhere;
- no tolerance is added.

One further change was needed by Option A itself. A JSON number of huge exponent (1e999999), read exactly, would have
been written out as a million digits in the reason of RESULT_IMPLAUSIBLE; before, it was read as infinity. That reason
now shows a number by the existing rule for a number a sender supplied (`SENT_NUMBER`, 24 characters: whole, or else
its length only).

**Declared before the next run (VP-5).** The matrix's 'after' expectations (committed in `9ba0f88`), and R35 as
committed in `f1dc370` (`tests/verify_tests.py` SHA-256 `bbc884b8…`, not changed since), both expected to pass:
- the matrix: A1 to A4, all predictions holding;
- R35: 3 of 3.
