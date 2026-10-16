# PLEA gateway v1.2.1 — a release check that tells the truth, and wider adversarial testing

**The response to the v1.2 independent review (conditional clearance).** Date 2026-10-13. Database PostgreSQL 16.13. No product code changed: every file under `plea_gateway/` and `mcp/` is byte-identical to the shipped v1.2. Every v1.2.1 result below is from the declared run recorded in `DECLARED_RELEASE.txt`, whose hashes were frozen before the run. The exception is the reproduction of the review's findings A and B on the shipped v1.2, run before any change.

---

## 1. The review

The v1.2 review verified the package (560/560 manifest hashes, 51/51 declared source hashes, the standalone report identical to the one in the zip, the archive's integrity), found the counts in the report in agreement with the packaged outputs, and judged the four v1.1 findings addressed within the documented trust boundary, P4 partly. It could reproduce the oracle vectors but had no PostgreSQL, so the database-dependent results are, in its words, "independently inspected evidence, not independently reproduced results". Its verdict is **technically promising, conditional clearance**. It raised three findings:

- **A. The regression runner can conceal failure.** `run_chain_v12.sh` records each stage's exit code but neither stops nor fails, so the script can exit 0 after a failed stage.
- **B. The clean-machine instructions do not match the runner.** The runner looks for `../../venv/bin/python` from `tests/`; the README creates `venv` inside the bundle.
- **C. The contract engine needs continued adversarial testing.** A disagreement is fail-closed when the database refuses a legitimate decision, but an over-permissive engine could accept an invalid direct SQL write. The 768,544 comparisons are bounded evidence, not a proof.

It also set the next steps: fix the runner, have a separate reviewer run the unchanged release on a fresh PostgreSQL, and test real service failures under staging conditions.

---

## 2. A and B, reproduced on the shipped v1.2

On a fresh extraction of the shipped zip with no `venv` above the bundle root, which is the layout the README's own instructions produce, I ran the runner unchanged (`outputs/review8/runner_before_v1_2_all_stages_127.log`):

| | shipped v1.2 |
|---|---|
| stages | all 22 printed `exit=127` (command not found: the runner looks one directory too high) |
| the runner's exit status | **0** |
| `outputs/rerun.done` | **written** |

Both findings are confirmed, and together they are worse than either alone: a reviewer who followed the README would have seen 22 failures scroll past and a success status at the end. The declared v1.2 run was not affected. Its interpreter sat beside the bundle and every stage exited 0, as its outputs record. I found a third inconsistency while fixing the README: its manual G01 commands said 1,000 rounds, where the declared chain runs 300.

---

## 3. The repair (A, B)

`run_chain_v121.sh` replaces the runner, and the v1.2 one stays in the bundle as shipped.

- **It finds its Python the way the README says.** `PLEA_PYTHON` if set, else `./venv/bin/python` in the bundle root, else `python3`.
- **It refuses to start on a broken setup.** Before any stage it checks that the interpreter imports `psycopg` and `cryptography` and that the database accepts the owner role. If not, it prints what to do and exits 2.
- **It cannot report success it did not earn.** Every stage runs, even after a failure, so the evidence is complete. The runner counts the stages and requires 22. It lists the failed ones, writes `rerun.failed` and exits 1. Only 22 stages with exit 0 give `CHAIN PASSED`, `rerun.done` and exit 0.
- **`check_runner.sh` tests the runner in seconds, in a throwaway copy.** No usable Python gives exit 2; every stage failing gives exit 1 with `rerun.failed` and no `rerun.done`. Both pass. (My first draft of this script would have overwritten the bundle's real outputs when run; it now never touches them.)
- **The README** says where the venv goes, gives the one-command run and the runner's exit statuses, and now matches the declared 300 rounds.

---

## 4. C: wider adversarial testing of the engine

Two additions to `x_tests.py`, both seeded and both written to look for the failure the review describes, a database that accepts what the contract would not give:

| check | what it does | result |
|---|---|---|
| **X2.11** a second mutation sweep | another seed and larger budgets (k up to 5, m up to 3); six walks of 120 genuine decisions; each record mutated in operands, operation name, a row added or dropped, and written in a rolled-back transaction | 720 genuine decisions accepted; of 3,141 mutated records, the 1,136 that are the contract's own decision accepted and the 2,005 that are not **all refused**; every chain verifies and replays; 0 mismatches |
| **X4.4** a random differential beyond the exhaustive bound | 3,000 walks of 40 operations on budgets up to k=5 and m=3 with six attempt identities, `plea_step` against the reference engine and the independent oracle at every step | 120,000 steps, 0 mismatches (15,681 applying, 98,440 denied, 2,186 NOOP, 3,693 DUPLICATE) |

With v1.2's sweep (3,246 mutated records, 2,252 not the contract's) the two sweeps put 4,257 records that are not the contract's decision (2,252 + 2,005) to the database's write path, and none was accepted. These widen the bounded evidence; they do not turn it into a proof, and they are only as good as the mutations and walks chosen.

**One mistake of mine, preserved.** My first X4.4 required more than 20,000 applying steps, a guess. Random walks are mostly denied, because most random operations are legitimately refused, and the first run had 15,681. That run showed 0 mismatches and one failure of the threshold. I corrected the threshold to 10,000 and declared the corrected file. The run is kept in `outputs/review8/x_tests_dev_run1_coverage_threshold.txt`.

---

## 5. Full regression

The declared run on a clean `plea121`, through the new runner, which printed `CHAIN PASSED: 22 of 22 stages exit 0` and exited 0:

| suite | result |
|---|---|
| X1–X4 | **15 + 11 + 7 + 4 = 37/37**; 768,544 exhaustive pairs and 120,000 random steps, 0 mismatches |
| U, S, Q, P | 36, 37, 33, 26 |
| V, R, H, T, M | 43, 43, 33, 35, 28 |
| E1, E2, E3 · W1–W4 | 13, 9, PASS · PASS, PASS, PASS, 18/18 |
| conformance · chaos · G02b | **34/34 · 90/90 · 200/200** |
| G01, lock / serializable | **300/300 / 300/300**, 10,650 decisions each, replayed in lockstep |

G01 took 229.5 s and 388.5 s, against 257.9 s and 421.4 s in v1.2's declared run. The code is the same, so this is machine variance, not a speed-up. The review's measured cost of evaluating the contract in the database, about 20% in lock mode and 25% serializable over v1.1, stands.

---

## 6. What this does not do

- **A separate reviewer has not run this release.** I can reproduce my own results from a clean extraction, as I did; I cannot supply the independence the review asks for. The clean-extraction check follows the README exactly, including creating the venv in the bundle root.
- **Real service failures under staging conditions are still untested.** The chaos tests kill processes at named points of a transaction on one machine. They are not failures of a network, a disk, a connection pool or a clock.
- **The engine is still not proved equivalent.** Both new checks are bounded and seeded.
- **P4's limit stands:** the gateway can still record a refusal the contract would give for a request it never received.
- **The operational gates are unchanged:** a human onboarding test, a design-partner staging integration and a throughput benchmark with production pooling.
