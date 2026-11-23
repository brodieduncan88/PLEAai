# Amendment 20: declaration before the official test runs

23 November 2026. Private working material. Branch `amend20-2026-11-23`, on `555f2c6` (Amendment 19's results).

This file is committed before the official runs. It fixes the changed code, states what each test is expected to show, and
states how the runs are made. Each official run is made once, after this commit, and its first result is kept, pass or fail.
This is internal work by the author under the owner's decisions of 23 November 2026. It is not an independent validation, and
it claims no production readiness. No defect is closed by it. The declarations, results and amendments of Amendments 17, 18
and 19 are not changed by it.

## Origin

An external AI review of `b97fe6b` (a different system's, read-only; its report is kept separately) found, among eleven
findings, four that this amendment takes: F-1, F-2, F-4 and F-9. The author reproduced F-1 and F-2 in process
(`tests/amend19_dev_evidence/ext_triage/`), and R36 and F40 reproduce them on the earlier code
(`tests/amend20_dev_evidence/before_bc6d865/`). F-3, F-5 to F-8, F-10 and F-11 are NOT in this amendment.

## What is changed (`verify/` only)

- **F-1.** `baseline.py` and `check_record.py` read every card bound with `dec()`, as a decimal, and fail closed if a bound is not a
  number. `validate_card` requires the plausible range and each numeric design-space range to be written as text (the card
  rule), as a criterion's limit already must be.
- **F-2.** `check_record.py --design` reads a released design file with `load_design`: no repeated key, no NaN or Infinity, no
  negative zero, no number a binary float holds as another. `front_door.parse_design` refuses the same numbers (400).
  `front_client.py submit` sends the file's own bytes (`submit_raw`). No new import.
- **F-4, the part that is not a policy.** `text()` never writes `-0` (both modules); the reason for a non-number is quoted by
  `sent()`, bounded. **`MAX_PLAIN` is not added.**
- **F-9.** Check 6 compares `canonical()` of the design in the verdict and in the arguments.
- Also: `tests/verify_tests.py` (R36, 6 checks), `tests/verify_front_tests.py` (F40, 5 checks), `tests/amend17_mutants.py`
  (fifteen defects).

`plea_gateway/`, `mcp/`, `spike/` and every other file are unchanged since `555f2c6`.

## The changed files

| file | sha256 at 555f2c6 | sha256 declared |
| --- | --- | --- |
| `verify/baseline.py` | `02acdb95065887c063edeceaa9376cbd05ccbd3fbaa3f8d78068d9f8a8c1a4b0` | `ff00456645699c13d140abd6a584645933244591bb0915a66df65ee8ba1ff2b8` |
| `verify/check_record.py` | `474fe7f055c4d3688992ae49bbb3df25be4a8dbf65486fab57b97f196999e432` | `64fa18071dc53aea53a5922bcbb99def76ca2ccb53d5f82f0df8520d0225ffad` |
| `verify/front_door.py` | `8c1336e0de528567436f4616fd99624ab08a065e84bdc5150734756c42ac5494` | `320e92458f8b55ef2ae43618411c6e22fa26813a0069b2caef30a5ee702571c3` |
| `verify/front_client.py` | `2c12449319d662e5e0fe1467e12abc7e76ee219df62622696e5c50a53b9a35c6` | `3eb8252aebc047e47df079d753e5b2fd4f9bf308a49fdf564ef4e4d66349fa81` |
| `tests/verify_tests.py` | `bab468099b194678a638f14b987db3538ef79cc71a9cbec437e5bebd575887fc` | `c0b637bf2d38059ef67aa209d55f5e72da6ed391b964a9b825cae2f5413a3ce2` |
| `tests/verify_front_tests.py` | `0921fd87f2c3c0fac5d50736c541c4ca349be1c5495ed05896649f0b7a1b9dd9` | `57b29e1f7737a700cba5a3c79c6e4bdc2de3eeabe41c2b0dba47d447c8b1f079` |
| `tests/amend17_mutants.py` | `c2b0135fe7745ac67e797771103e3b006cbfa4d8a34713e1312304c9d6e8b824` | `8abb589a8a0570859569f25bddd5998c7df514d9c187331ffe4dd575a48dbb8b` |

## What each test is expected to show

**The gate's suite: 36 tests, 262 checks, each expected true**: R1 to R35 with Amendment 19's counts (256 checks), and R36 with 6:
1. a card bound written as a number is read as the decimal it says (0.29999999999999999 against a plausible minimum of 0.3 is
   UNKNOWN: RESULT_IMPLAUSIBLE; the record's checker rejects a PASS that holds it);
2. 99999999999999995000000 is outside a design space from 1e23 to 2e23, and the edges 1e23, 2e23, 0.1 and 0.3 are inside, by the
   service and the checker;
3. a card whose plausible or design-space range is written as numbers is refused by the card's rule; a whole baselined card, in
   text, is accepted;
4. a value that underflows on writing is `0`, never `-0`; a 500000-character answer where a number was due is UNKNOWN:
   CHECK_OUTPUT_INVALID with a reason under 200 characters, under 64 KiB;
5. `check_record.py --design`: the design as it was run is shown as meeting the check (exit 0); a number a binary float rounds, a
   repeated key, 1e-400, -0.0, NaN and Infinity are each refused (exit 2);
6. a verdict signed for 3.0 where 3 was sent fails at Check 6 only, with its design_sha256 written either way.

**The front door's suite: 38 tests, 219 checks, each expected true**: F3 to F39 with Amendment 19's counts (214), and F40 with 5.

**The gateway's chain is not run.** No file it runs has changed since `f4c1de6`.

**Planted defects (development, not official), against the candidate `8f3bfb3`, whose code is the code of this commit:** 76 entries,
62 planted and 62 caught, 14 not planted. At the first candidate (`be89595`): 61 of 62 (one test gap, restated in
`verify/AMEND20_DEV_LOG.md` entry 4). At `8f3bfb3`, in development: front 38 of 38 with 219 checks; gate 35 of 36 in the full run
(R25, see below) and 36 of 36 with 262 checks in the run of the gate alone that followed. All of it is kept.

## Limitations and what stays open

- **T-1 (a fault in a test, low).** R25's last check fails about once in 64 runs, when the witness's random nonce begins with `-`
  and `argparse` takes it for an option. It is not repaired here (`verify/AMEND20_DEV_LOG.md` entry 5). **It applies to the
  official gate run declared below: if it falls to it, the run is reported as it comes out and is not repeated under this
  declaration.**
- No agent review of this candidate was made (the owner's decision of 23 November), and none is claimed. Amendment 19's was
  incomplete too.
- Not changed, and recorded: a very small number inside a plausible range that includes zero is still written in full (about a
  million characters); `plea_verify_mcp.py` reads a tool call's arguments as plain JSON; a design file over the front door's 16 KiB
  limit is refused by the front door (the client no longer compacts it).
- The external review's F-3, F-5, F-6, F-7, F-8, F-10, F-11 are not verified and not changed; the Stage B harness's open findings
  (H1, M1 to M3, L1 to L14) and Amendment 18's L-2 and L-3 stay open.
- D20-F stays open (Amendment 19); closing it is the owner's.

## Commands and conditions

As Amendment 17's declaration states them: as root; PostgreSQL 16 on 127.0.0.1; the project's virtual environment; `fs.file-max`
33617920; `verify/sandbox.py --prerequisites` ending with status 0. Each suite runs once, in this order:

    cd tests && <venv>/bin/python -B verify_tests.py
    cd tests && <venv>/bin/python -B verify_front_tests.py

Each output file is removed before its command, and copied to `verify/results_verify_tests_amended20_2026-11-23.json` and
`verify/results_front_tests_amended20_2026-11-23.json`.

Expected: the gate 36 of 36 tests and 262 of 262 checks; the front door 38 of 38 tests and 219 of 219 checks.

A test or a check that comes out otherwise is reported as it came out, in the amendment that follows, and is not run again under
this declaration.
