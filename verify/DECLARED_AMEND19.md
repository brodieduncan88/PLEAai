# Amendment 19: declaration before the official test runs

23 November 2026. Private working material. Branch `amend19-r15-2026-11-23` (cut from `b97fe6b` at the owner's decision of 23
November 2026).

This file is committed before the official runs. It fixes the changed code, states what each test is expected to show, and
states how the runs are made. Each official run is made once, after this commit, and its first result is kept, pass or fail.
This is internal work by the author under the owner's decisions of 22 and 23 November 2026. It is not an independent
validation, and it claims no production readiness. The declarations, official results and amendments of Amendments 17 and 18,
and the frozen diagnostic commits `0da1a85e` and `d208f6e`, are not changed by it.

## What is changed (D20-F, against `2c1af26`)

A JSON number a check prints is read as the decimal its digits write, and compared exactly (Option A; Option B was not
implemented and is the owner's to approve). `verify/baseline.py`:
- `evaluate` reads the check's output with `parse_float=decimal.Decimal`;
- `dec` accepts a `Decimal`; no decimal is ever made into a float, and no tolerance or epsilon is used;
- a number a reason must show is shown by `_shown`, by the rule for a number a sender supplied;
- (the R15 correction, candidate 2) a number whose exponent is above `decimal.DefaultContext.Emax` is answered CHECK_ERROR, as
  before Amendment 19, from the constant and not from the thread's context.

Also changed (development tooling and tests):
- `tests/verify_tests.py`: R35 (4 checks), with `raw_number_case`, `D20F_CASES` (22) and `D20F_EXPONENT_CASES` (5);
- `tests/amend17_mutants.py`: seven defects added (five for the first candidate, two for the R15 correction).

`plea_gateway/`, `mcp/` and every other file under `verify/` are unchanged since `2c1af26`. Not changed by this amendment, and
for Amendment 20: the card's bounds, the released-design reader, the front door's reading of a number, and the `-0` and
reason-length faults the external review found.

## The changed files

| file | sha256 at 2c1af26 | sha256 declared |
| --- | --- | --- |
| `verify/baseline.py` | `1860168c223ce7db8ae912ff6986b38149a180de17eaaade4944da1bb2a0bdc5` | `02acdb95065887c063edeceaa9376cbd05ccbd3fbaa3f8d78068d9f8a8c1a4b0` |
| `tests/verify_tests.py` | `c4ab616416c4a85405bb4ebd1a4e079ccbf3f7da9c009979222a1932ba473cb1` | `bab468099b194678a638f14b987db3538ef79cc71a9cbec437e5bebd575887fc` |
| `tests/amend17_mutants.py` | `d721199afdc9f80ce4475892483c636e04055529b0c5e3e84520aaf1cfd39e21` | `c2b0135fe7745ac67e797771103e3b006cbfa4d8a34713e1312304c9d6e8b824` |

`tests/verify_front_tests.py` is unchanged (`0921fd87f2c3c0fac5d50736c541c4ca349be1c5495ed05896649f0b7a1b9dd9`).

## What each test is expected to show

**The gate's suite, `tests/verify_tests.py`: 35 tests, 256 checks, each expected true**: R1 to R34 with the counts of
Amendment 18 (252 checks), and R35 with 4 checks:
1. through the front door, 199.99999999999999 printed as a JSON number against at least 200 is a signed FAIL held as printed,
   and the record verifies;
2. 200 and 200.00000000000001 are signed PASS, held as printed;
3. in process, 22 printed numbers on three criteria: none is PASS unless its exact value meets the criterion, each gives the
   verdict expected, every PASS and FAIL is accepted by the record's checker, no verdict is 64 KiB or more;
4. a number whose exponent is at the decimal context's limit (1e999999, either sign) is UNKNOWN: RESULT_IMPLAUSIBLE, and one
   past it (1e1000000, 1e9999999999, either sign) is UNKNOWN: CHECK_ERROR; none is PASS, each verdict is under 64 KiB.

**The front door's suite, `tests/verify_front_tests.py`: 37 tests, 214 checks, each expected true**, as at Amendment 18.

**The gateway's chain is not run.** No file it runs has changed since `f4c1de6`; Amendment 17's official run of it (22 of 22, at
`ed2ec76`) stands.

**Planted defects (development, not official), against the candidate `5569957`, whose code is the code of this commit:** the
whole runner, 61 entries: 47 planted and 47 caught, 14 not planted (the same 14 as at `203bdca`). The first candidate
(`3d6598f`) gave 59 entries, 45 planted and 45 caught, with gate 34 of 35 (R15 failed) and front 37 of 37; all of that run is
kept as it came out. At `5569957`, in development: gate 35 of 35 with 256 checks; front 37 of 37 with 214 checks. These
development results are not the official ones.

## Limitations and what stays open

- The internal review of the first candidate was not completed (the reviewing agent was stopped by a usage limit before it
  reported), and no review of the second candidate was made. The owner directed on 23 November that this be reported as it is.
  No review finding exists for either.
- A very small number inside a plausible range that includes zero (such as 1e-999999 against a range from -100 to 100) is still
  written in plain notation, about a million characters, in the achieved and margin fields. That existed before for decimal
  strings and is now reachable by JSON numbers. It is not decision-relevant, and it is not changed here.
- D20-F is implemented and tested internally. It is NOT closed: closing it is the owner's.
- Option B (exact tokens through the whole record) would change the signed bytes or the numerical contract and is not
  implemented.
- The external review's findings F-1, F-2, F-4 and F-9 are for Amendment 20.
- Separate accounts, cgroup v2 and KVM are not tested here.

## Commands and conditions

As Amendment 17's declaration states them: as root; PostgreSQL 16 on 127.0.0.1; the project's virtual environment;
`fs.file-max` set for this start of the machine to 33617920; `verify/sandbox.py --prerequisites` ending with status 0.

Each suite runs once, in this order:

    cd tests && <venv>/bin/python -B verify_tests.py
    cd tests && <venv>/bin/python -B verify_front_tests.py

Each output file is removed before its command, and copied to `verify/results_verify_tests_amended19_2026-11-23.json` and
`verify/results_front_tests_amended19_2026-11-23.json`.

Expected: the gate 35 of 35 tests and 256 of 256 checks; the front door 37 of 37 tests and 214 of 214 checks.

A test or a check that comes out otherwise is reported as it came out, in the amendment that follows, and is not run again
under this declaration.
