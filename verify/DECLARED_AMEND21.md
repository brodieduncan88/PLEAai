# Amendment 21: declaration before the official test runs

23 November 2026. Private working material. Branch `amend21-t1-clean-2026-11-23`, on `59de0dc`.

This file is committed before the official runs. It fixes the changed files, states what each test is expected to show, and states how
the runs are made. Each official run is made once, after this commit, and its first result is kept, pass or fail. Internal work by the
author under the owner's decision of 23 November 2026 ("repair T-1"). Not an independent validation; no production readiness is
claimed. Nothing is closed by it beyond T-1's own repair, which is internally tested only.

## What is changed

T-1, a fault in a test (R25 handed a random nonce to `check_record.py` as `--nonce VALUE`; about one in 64 begins with a dash and is
read as an option, a false failure). `verify/AMEND21_DEV_LOG.md` entry 1.
- `tests/verify_tests.py`, R25: the nonce is handed as `--nonce=VALUE`; R25 gains one check, a **deterministic** leading-dash case (a
  fixed nonce `-FixedLeadingDash0123456`: status 1 and one CURRENCY line, never status 2).
- `tests/amend17_mutants.py`: one planted defect (the two-argument form again; expected caught by R25).
- `verify/README.md`: the example is `--nonce=NONCE`, with the reason.
- Documents: `verify/AMEND21_DEV_LOG.md`, `verify/DEFECT_REGISTER.md` (G19, G20), `verify/reviews/EXTERNAL_REVIEW_B97FE6B_SUMMARY_2026-11-23.md`,
  `verify/reviews/D20F_CLOSURE_CONFIRMATION_2026-11-23.md`.

No code other than the readme is changed.

## The changed files

| file | sha256 at 59de0dc | sha256 declared |
| --- | --- | --- |
| `tests/verify_tests.py` | `c0b637bf2d38059ef67aa209d55f5e72da6ed391b964a9b825cae2f5413a3ce2` | `a1b932c68852620a3b28df3cfe39129c24a2cb511e7c1ae1c03a21683d0822a8` |
| `tests/amend17_mutants.py` | `8abb589a8a0570859569f25bddd5998c7df514d9c187331ffe4dd575a48dbb8b` | `78517aa2ad8a4efad4f3e56b9975db6daf82e561fc9fc3d1783572efcdbd19bb` |
| `verify/README.md` | `4f064d2b10ca2d3dc9ef8e7a7b45217c63bf289a3b9c2ac4d7a37d6cc4163282` | `a9ea2534169672e1d45851a88d6568f680be14aafbadc8ac77216355b3096174` |

## What each test is expected to show

- **The gate's suite: 36 tests, 263 checks, each expected true** (Amendment 20's 262, plus R25's new check).
- **The front door's suite: 38 tests, 219 checks, each expected true** (unchanged).
- **The planted-defect runner**, against the declaration commit: 77 entries, 63 planted and 63 caught, 14 not planted.
- The gateway's chain is not run (no file it runs has changed since `f4c1de6`).

## Limits

- T-1 is repaired for the one place the test handed the nonce over; none other is known.
- No agent review (a test-only repair), and none is claimed.
- Everything else open stays as the register says.

## Commands and conditions

As Amendment 17's declaration states them: as root; PostgreSQL 16 on 127.0.0.1; `fs.file-max` 33617920; the sandbox prerequisites check ending with status 0. **The working tree, the interpreter and the working directories are under `/tmp/plea-verify/`**,
so that no personal or tool path enters the recorded outputs. Each suite runs once, in this order:

    cd tests && <interpreter> -B verify_tests.py
    cd tests && <interpreter> -B verify_front_tests.py
    <interpreter> -B amend17_mutants.py <declaration commit> <work directory> <interpreter> <output.json>

Each output file is removed before its command, and copied to `verify/results_verify_tests_amended21_2026-11-23.json`,
`verify/results_front_tests_amended21_2026-11-23.json` and `verify/results_mutants_amended21_2026-11-23.json`. Expected: gate 36 of 36 and
263 of 263; front door 38 of 38 and 219 of 219; runner 63 of 63 planted caught. A result that comes out otherwise is reported as it came
out and is not run again under this declaration.
