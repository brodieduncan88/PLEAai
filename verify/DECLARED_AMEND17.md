# Amendment 17: declaration before the official test runs

22 November 2026. Private working material. Branch `hardening/prepentest-2026-11-22`.

This file is committed before the official runs. It fixes the changed code, states what each test is expected to show,
and states how the runs are made. Each official run is made once, after this commit. Its first result is kept, pass or
fail. A later correction would be a separate, dated amendment. Times are UTC.

This is internal work by the author of the code, under the owner's direction (the owner's "Trimmed Pre-Pen-Test
Implementation Directive", Stage A). It is not an independent validation, and no reviewer named here is independent:
each is an AI agent instructed by the author. Nothing here claims production readiness or production-contract
compliance.

## What is changed, and why

The defect identifiers are those of `verify/DEFECT_REGISTER.md`. What was done in development, with every failed run, is
in `verify/AMEND17_DEV_LOG.md`, entries 1 to 18. The eight internal reviews are in `verify/reviews/AMEND17_REVIEW_*`.

- **A1: D5 and D21.** Opens `plea_gateway/` under the directive's dated authorisation.
  - **D5.** The gate host asks the tool's binder (`verify_tools.bound`) before an attempt is claimed. A baseline whose
    hash does not match the budget the attempt was admitted under is refused (403 BASELINE_NOT_ADMITTED_BUDGET), and
    nothing is run or signed.
  - **D21.** Attempt identities become the whole SHA-256 (`a2-` and 64 hex digits). Request keys become `verify:` and
    the whole hash. A budget that already holds attempts of the earlier 64-bit form keeps that form. A budget holding
    both forms makes no further attempt (`IdentityFormsMixed`; the front door answers 409). The record's checker
    reads either form, never both in one record.
- **A2: D16.** The latest binding the front door has seen for each job, and its revocation, are kept in PostgreSQL
  (`verify/front_state.py`). The table is reached only through the SECURITY DEFINER function `verify_front_observe`.
  - A revocation is absorbing.
  - A stale, conflicting or revoked binding admits nobody.
  - A job is named in the record by the engineer's public key and the job's name, both signed, after five rounds of
    review found ways around each earlier naming.
  - The engineer's console records each move and revocation:
    - a revocation is recorded first and written always, unless what stops it is said;
    - a revocation with no usable entry can be made by name (`--by-name`);
    - `jobs.json` is written under a lock, without following links.
  - The front door records every revocation in `jobs.json` at its start and on its look.
- **A3: D20.** When a baseline is made, its controls are put to the record checker's own rules
  (`check_record.control_problems`, and `rederive` with the design-space test set aside). A baseline that would not
  verify in a record is refused.
- **A4: D6 and D35.**
  - The first client's transport (`verify/verify_client.py`) is retired: it prints that it is retired and exits 4.
  - R1 to R13 now run through the real front door. Their shared reading code is in `verify/service_client.py`.
  - Five gate tests (R14, R17, R18, R25 and R26) reach the service through a test-only copy of the first client
    (`tests/service_route.py`), which holds the service's own database role.
  - The readmes' references to the first client are corrected.

`plea_gateway/` and `mcp/` are unchanged since `f4c1de6`.

## The changed files

Base: `2a1804c` (the planning commit of 22 November, on `1b132e2`). The code declared is that of `203bdca`. The commit
carrying this declaration changes no file below. The hashes are of the files at `203bdca`.

| file | sha256 at 2a1804c | sha256 declared |
| --- | --- | --- |
| `mcp/plea_mcp.py` | `dcb60eb17678092420f795ac9b3344e43ddf6730328e19c04825dfd5bf18f5df` | `2b978b3c2fa1447d1736714f24682e89eec9b551ec9677d0989cc6de88f56031` |
| `mcp/vanilla_mcp.py` | `3b574ba659f905a84475b94f8310a58e047b4fbbf57786c9223d8bb1b44c8b1c` | `5260d8ca872428cf76a4bb96b1f619eac5bf2d94fc6ce1d8ecd5d1c4fe19dca0` |
| `plea_gateway/gate_host.py` | `44f2a180a456467a8fc694e384f90f200bdc279c3fcd66a93e70e631f9b01bc9` | `f414c3a1807a3c038d1a1190051966f0b564c437bed28491dbfe1495563576a6` |
| `plea_gateway/governor.py` | `3dac342419c705dd6cdec11058902364de8634d65f40dd45240ad8fb598967f0` | `29f01ea3f9fb05be95fe299727c91f7d90a250f7a043ad88d745a6aba36f8cc4` |
| `tests/amend17_mutants.py` | `(new)` | `91d1278d01534fde93c3fa4220451de63bf50f96b91ade1b9a0c8d2c7e62aa16` |
| `tests/e3_lifecycle_evidence.py` | `5c9cfba268546e0248d3b1f62209040093d6e1830c47794576b78ea050936b48` | `54965c3e7a88102bd1200d1f9d3a081c7d52a9d4ab07c03417769811f27624aa` |
| `tests/service_route.py` | `(new)` | `1cbfc5c09fa53fc46159abb75a2dd241782bece71aa05fb8414770199de23949` |
| `tests/verify_front_tests.py` | `f85fd99222ab4fb3a6f2915fe03846b9be726a542d6a8699eef8d26bbf1b3e60` | `1f2385ab5ea43a1181b3fcfb28a9e2f38613d5e106d2625782ed544f968f48a3` |
| `tests/verify_tests.py` | `5cdb61f8bf9b58ce00fbd9c7305bfd1c5c2c652e42997eeae8750d7ef46bfd1f` | `c4ab616416c4a85405bb4ebd1a4e079ccbf3f7da9c009979222a1932ba473cb1` |
| `verify/README.md` | `0b057a14b1cad1e6aac573df355f9c0e5072ad267780dab00e289923b828f32d` | `4f064d2b10ca2d3dc9ef8e7a7b45217c63bf289a3b9c2ac4d7a37d6cc4163282` |
| `verify/README_FRONT.md` | `9f9d86ebfbfd478e8cd0b866597167abdc91445b49d66a970661bd8bf70e3ea8` | `a3714179bb76072bc3fe6a3eedde2aaed73329aa3f56d417b22286eabf9a4340` |
| `verify/check_record.py` | `5e7eb84a451f6b17a1f1ed463ff051d9e529f0da67401f9eab2f706b6bb9b1b7` | `474fe7f055c4d3688992ae49bbb3df25be4a8dbf65486fab57b97f196999e432` |
| `verify/deploy.py` | `c3653a493f4bd39e0394587d7dcce651a1dea386aa186b5e0c252f550e16f21b` | `2445bc83407e8ad8f817b52432b5f66bad6031a08f08c83457351a40ded5ce1b` |
| `verify/deploy_front.py` | `0fca7f2327f5f8ccc63b67cdadcf064849d78845e07ec149f1da47e29b45cc9c` | `44ce16afc525dcae52bb7819bab81594d5dce54076e37a4cbd092643ebbbd781` |
| `verify/front_client.py` | `f8644be409eb678659c3cbe0bfcdde04ba526d3a45d030c7062c26770fc0db8f` | `2c12449319d662e5e0fe1467e12abc7e76ee219df62622696e5c50a53b9a35c6` |
| `verify/front_ctl.py` | `2d59f3f823c9e47ca3fc13cb976ffdc1310ae222a6088252d1870b24b85cea52` | `8065c075e7e99c8ccc793f4e8d7142cb3df0aa11297ad345fa2419d12c2ce7ec` |
| `verify/front_door.py` | `407e7516c8719d1d0c92794a81fcebc5989abc1fd4469e9955a4156fd54ec460` | `9bd4686f71433310bc52539338a9238ea7b4373fadc30485b6c5cc74d8e14e91` |
| `verify/front_state.py` | `(new)` | `e1d9f819c7694afdb976369749775c720d218ddb944271a208fe3ff03e55eed2` |
| `verify/service_client.py` | `(new)` | `d78cc6eff387bcb12c2e256eb381a527f66a678e1e3e57a6e281706d38439053` |
| `verify/verify_client.py` | `5a272be40fc6c3927a5dd6c2ec8b6c3513bb6357a485e1f7a926fb82a2f9dbd3` | `4b7ffa8673b0ebe94c65eb23a6275787c47e245ea806de7e207e3459c8d8c154` |
| `verify/verify_ctl.py` | `8ec49b53ef51b0218afca12848331938ace74e677848a6be2360434403ad06c5` | `782fa3e2a5e880fd9e3118135bd65272fb400d54c02918743bdc2f437ab4a9e0` |
| `verify/verify_record.py` | `89ac0bcf81f603835730adc7851a8dda4e554c60df9e0c7ed88476fa9a192888` | `07eee35ca5d91acb90e591068ef8ec61c689d14149452c0ce93f93e89e949189` |
| `verify/verify_tools.py` | `6110f2daa48df1b3f51a22b42e4936a546ea65896aff9261167a4c9b465ab942` | `10c92d66eef30c90e9bfd8c78a2eda8923bd666f73f078d01f5d52e44e97c3a3` |

Not code, and not in the table:
- `verify/AMEND17_DEV_LOG.md`;
- `verify/DEFECT_REGISTER.md` (Part G);
- `verify/reviews/`;
- `tests/amend17_dev_evidence/`;
- `plan/`;
- `spike/firecracker_2026-11-22/` (Stage B: preparation only).

`tests/amend17_mutants.py` is development tooling. Its runs are not official.

## What each test is expected to show

**The gate's suite, `tests/verify_tests.py`: 34 tests, 252 checks, every one expected true.** Checks per test:

R1 4, R2 3, R3 3, R4 4, R5 6, R6 5, R7 5, R8 2, R9 5, R10 5, R11 5, R12 3, R13 3, R14 7, R15 8, R16 6, R17 15, R18 10,
R19 7, R20 11, R21 3, R22 13, R23 11, R24 6, R25 19, R26 27, R27 15, R28 6, R29 9, R30 6, R31 6, R32 5, R33 6, R34 3.

- **R1 to R13 are the permanent core regression requirements.** They run through the front door:
  - a test deployment with the witness, the gate host and the front door;
  - the job enrolled by the engineer's console;
  - each design sent by `front_client.py` from a clean environment.
  
  Each keeps every assertion and every count of checks it had at Amendment 15's official run
  (`verify/results_verify_tests_amended15_2026-11-20.json`).
  
  One check is reworded. R11's second, "a relaxed baseline signed by another key is not accepted by the client",
  now names the front door: "… is not accepted by the front door: the assistant's side holds no baseline, and a
  request carrying one is refused". It is the same property, held where it is now enforced (entry 9).
- **R14, R17, R18, R25 and R26** run on the test-only service route. Their gate-side checks test the product. Some
  checks of R14, R17 and R18 test answers made by that route (the second review, M6).
- **R17**'s bound on what a design may make the service print is raised by 49 characters, for the longer identity
  (entry 6).
- **R24**'s pattern takes either form of identity.
- **R29**, the sandbox's own test, is not retired and not changed.
- **New tests:**
  - **R30** (D5): the binder, with the courier noticing NO_OUTCOME;
  - **R31** (D21): identities and request keys of the whole hash, a real record of mixed forms refused, the
    governor's nonce, and the front door's check of a verdict's design;
  - **R32** (D20): controls at baselining, including a control of 29 significant digits;
  - **R33**: across the change of form; a budget of the earlier form keeps it, and one of both forms is refused;
  - **R34**: the first client refuses, and no credential reaches the job's folder.

**The front door's suite, `tests/verify_front_tests.py`: 36 tests, 211 checks, every one expected true.** Checks per
test:

F3 5, F4 4, F5 5, F6 6, F7 4, F8 5, F9 4, F10 6, F11 6, F12 6, F13 5, F14 7, F15 7, F16 5, F17 4, F18 6, F19 7, F20 6,
F21 6, F22 3, F23 4, F24 6, F25 4, F26 3, F27 4, F28 5, F29 8, F30 9, F31 5, F32 6, F33 7, F34 5, F35 9, F36 3, F37 11,
F38 15.

- **F1 and F2 are retired** with the first client. Their properties are carried:
  - by R30 (a design sent against another baseline's budget is refused before anything is run);
  - by F7 (one design that leaves a record unable to verify is refused at the front door).
  
  Their results before Amendment 17 stand as they were.
- **F37** (D16): restarts, a put-back after a restart, absorbing revocation, conflict, a mismatched budget, the
  record unreadable (503), the roles' privileges, a rolled-back call, forty concurrent observers, a role-made
  revocation, and revocations never seen by their job. Its check that a change to the authority's file changes nothing
  can no longer fail (the second review's H2 is gone with the realm); it is kept.
- **F38** (D16, after the third to seventh reviews): fifteen checks, given in its text.

**The gateway's chain, `run_chain_v121.sh`: 22 stages, each expected to exit 0**, on a database made new for the run.
Three development runs of it passed 22 of 22: after A1 (database plea29), after the A1 correction (plea30), and at
`f4c1de6` (plea31). Its files, `plea_gateway/`, `mcp/` and the chain's tests, have not changed since `f4c1de6`.

## What was done in development

All in `verify/AMEND17_DEV_LOG.md`, with the evidence in `tests/amend17_dev_evidence/`.
- **Full development runs before this declaration**, each at a commit of the review rounds: `f4c1de6`, `3473478`,
  `818bee9`, `c5c9832`, `fb544a0` and `203bdca`. The gate passed 34 of 34 at each, and the front 35 of 35 or 36 of 36.
- **The planted-defect runner:**
  - at each but `f4c1de6`, where it stopped on a fault of its own, it caught every defect it planted;
  - at `203bdca` its result is recorded in the log after this declaration, and is not a condition of it.
- **Failed runs kept:** R31's first run, R32's first two, A4's first run, the runner's first run, and F38's two runs
  at `7b2066a`. Each is in the log, with what was changed after it.
- **Process breaches recorded** (VP-2 to VP-5):
  - test counts declared wrongly, twice;
  - a register row edited after commit, then reverted;
  - outputs lost when a patch stopped part-way;
  - a check's predicate restated after a failed run (F38's check 9, entry 17), with the failing run and file kept.

## What stays open

Each is in the register, Part G (G7 to G10, and this declaration's entry).

- **D16:**
  - a revocation that neither the console nor the front door has yet recorded (the database unreachable from both)
    is undone by a put-back made before either records it;
  - a restore of the database, together with `jobs.json`, undoes later bindings;
  - the service's own role (CAP-DB) can deny a job, never admit one;
  - a move is written before it is recorded, so a put-back in between admits the superseded binding, whose old
    budget `revise` has stopped;
  - with more than one engineer key pinned, or during a change of key, a name revoked under one key does not cover
    another key's enrolment of it;
  - nothing checks that the console's database is the front door's;
  - `jobs.json` is read by name, so a pipe there stops the console and the front door, and a link to `/dev/zero`
    exhausts memory;
  - a mode planted on `jobs.json` is kept;
  - names are checked with `fullmatch` only on `--by-name`;
  - the lows of the seventh and eighth reviews, listed in the log, entries 18 and after.
- **D21.** A process of the earlier code during a rolling upgrade stops a budget's runs (fails closed). Records made
  before keep 64-bit identities.
- **D5.** The binder compares the 128-bit prefix of the hash that the budget's name carries.
- **D6.** Five gate tests use a test-only copy of the first client. `verify/experiment/` and `demo.py` cannot run as
  they stand.
- **Finding 2 of D6.** A holder of the service's role can still send a design that leaves a record unable to verify.
  Nothing in the gateway refuses a NUL, or a number that is not finite.
- **D20.** A value given to more than 28 significant digits that does not cross its limit is written rounded in the
  record.

## What is not tested

- A deployment with the parties under separate accounts: every test runs under one account, as root.
- A machine with cgroup v2 only, a KVM host (Stage B), or any kernel but this one.
- A real rolling upgrade.
- The MCP clients of Stage D.

## Commands and conditions

The official runs are these, each once, from the tree at the commit that carries this declaration, in this order, with
nothing else running on the machine's ports 8971 to 8974 or on the databases named.

Conditions:
- as root;
- PostgreSQL 16 on 127.0.0.1 with the four roles of the README;
- the interpreter of the project's virtual environment (Python 3.11);
- `fs.file-max` set for this start of the machine to 33617920 (`sysctl -w fs.file-max=33617920`);
- `python verify/sandbox.py --prerequisites` ending with status 0.

    cd tests && <venv>/bin/python -B verify_tests.py
    cd tests && <venv>/bin/python -B verify_front_tests.py
    PLEA_DB=plea32 PLEA_PYTHON=<venv>/bin/python bash run_chain_v121.sh

The two suites use the database `plea`. `plea32` is made new for the chain, as the owner `plea`, with the gateway's
schema and authority installed as the README shows.

Before each suite the output file it will write is removed, and so is `outputs/rerun.*` before the chain. The outputs
are copied to:
- `verify/results_verify_tests_amended17_2026-11-22.json`;
- `verify/results_front_tests_amended17_2026-11-22.json`;
- `verify/results_chain_amended17_2026-11-22.txt`, with each stage's own output in `verify/results_chain_amended17_2026-11-22/`.

Expected:
- the gate: 34 of 34 tests and 252 of 252 checks;
- the front door: 36 of 36 tests and 211 of 211 checks;
- the chain: 22 of 22 stages exit 0.

A test or a check that comes out otherwise is reported as it came out, in the amendment that follows the runs, and is
not run again under this declaration.
