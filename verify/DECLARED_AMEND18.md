# Amendment 18: declaration before the official test runs

22 November 2026. Private working material. Branch `hardening/prepentest-2026-11-22`.

This file is committed before the official runs. It fixes the changed code, states what each test is expected to show,
and states how the runs are made. Each official run is made once, after this commit, and its first result is kept, pass
or fail. This is internal work by the author under the owner's decision of 22 November 2026, point 1. It is not an
independent validation, and it claims no production readiness. Amendment 17's declaration, results and amendment are not
changed by it.

## What is changed

A front door pins exactly one responsible engineer's key (D16). `verify/front_door.py`:
- `single_engineer_key` and `EngineerKeys`, used by `Front.__init__` and by the start (`main`), before anything is
  opened, written or bound;
- none, two or more (the same twice included), or a key that is not 64 lower-case hex digits, and the front door is not
  made or not started;
- configuration is the existing repeated `--engineer-key` option;
- bindings and baselines signed by any other key are refused as before.

Also changed:
- `verify/README_FRONT.md`: one key, rotation not supported, and the steps of a new start;
- `tests/verify_front_tests.py`: F39 is added;
- `tests/amend17_mutants.py`: three defects are added (development tooling).

`plea_gateway/`, `mcp/` and every other file are unchanged since `ba82e66`.

## The changed files

Base: `ba82e66` (Amendment 17's results). Hashes are of the files at the commit carrying this declaration.

| file | sha256 at ba82e66 | sha256 declared |
| --- | --- | --- |
| `verify/front_door.py` | `9bd4686f71433310bc52539338a9238ea7b4373fadc30485b6c5cc74d8e14e91` | `8c1336e0de528567436f4616fd99624ab08a065e84bdc5150734756c42ac5494` |
| `verify/README_FRONT.md` | `a3714179bb76072bc3fe6a3eedde2aaed73329aa3f56d417b22286eabf9a4340` | `74867cdd5129936283d8533d025b31f990365652f465586f8546da4464a613ef` |
| `tests/verify_front_tests.py` | `1f2385ab5ea43a1181b3fcfb28a9e2f38613d5e106d2625782ed544f968f48a3` | `0921fd87f2c3c0fac5d50736c541c4ca349be1c5495ed05896649f0b7a1b9dd9` |
| `tests/amend17_mutants.py` | `91d1278d01534fde93c3fa4220451de63bf50f96b91ade1b9a0c8d2c7e62aa16` | `d721199afdc9f80ce4475892483c636e04055529b0c5e3e84520aaf1cfd39e21` |

`tests/verify_tests.py` is unchanged (`c4ab616416c4a85405bb4ebd1a4e079ccbf3f7da9c009979222a1932ba473cb1`).

## What each test is expected to show

**The gate's suite, `tests/verify_tests.py`: 34 tests, 252 checks, each expected true**, with the counts of Amendment 17's
declaration. R1 to R13 run through the front door, which now starts with its one key.

**The front door's suite, `tests/verify_front_tests.py`: 37 tests, 214 checks, each expected true**: F3 to F38 with
Amendment 17's counts, and F39 with 3 checks.
- In process, a front door is made with exactly one key and refused with none, two, the same twice, or one of another
  form.
- As a process, it does not start with none, two, the same twice, or one of another form, and says why. The clause "and
  binds no port" is recorded as unable to fail (the review's L-2).
- A binding signed by another key admits nobody.

**The gateway's chain is not run.** No file it runs has changed since `f4c1de6`, and Amendment 17's official run of it (22
of 22, at `ed2ec76`) stands.

**Planted defects (development, not official):** at `8c4762f`, 3 of 3 caught by F39. The 51 earlier ones were run at
`203bdca` (37 of 37 caught, 14 not planted); their texts plant identically now.

## What stays open

- D16, as register entry G13 gives it.
- The lows of the review (L-2, L-3).
- D20-F (a false PASS through float parsing), new, for the owner's decision.
- D6's front-door equivalents, specified, not built.
- D21's rolling-upgrade limit.
- Separate accounts, cgroup v2 and KVM are not tested here.

## Commands and conditions

As Amendment 17's declaration states them:
- as root;
- PostgreSQL 16 on 127.0.0.1;
- the project's virtual environment;
- `fs.file-max` set for this start of the machine to 33617920;
- `verify/sandbox.py --prerequisites` ending with status 0.

Each suite runs once, in this order:

    cd tests && <venv>/bin/python -B verify_tests.py
    cd tests && <venv>/bin/python -B verify_front_tests.py

Each output file is removed before its command, and copied to `verify/results_verify_tests_amended18_2026-11-22.json` and
`verify/results_front_tests_amended18_2026-11-22.json`.

Expected:
- the gate: 34 of 34 tests and 252 of 252 checks;
- the front door: 37 of 37 tests and 214 of 214 checks.

A test or a check that comes out otherwise is reported as it came out, in the amendment that follows, and is not run again
under this declaration.
