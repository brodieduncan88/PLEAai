# PLEA gateway v0.8: one owner per host state, and a gateway credential that cannot rewrite accounting

12 October 2026 · follows the v0.7 report · a response to the v0.7 independent review · private working material, not for publication

## Summary

**Headline.** The v0.7 review found two real defects, both reproduced here on the unchanged v0.7 code before any change. First, the host-state lease was not atomic: simultaneous acquirers of an expired lease all became owners, and a host frozen past its lease could still run a tool on resume. Second, the gateway's database credential could rewrite accounting directly: reset a hold or stop, delete a consumed attempt to free budget, raise the budget, insert a reservation, and edit or delete the audit log. Both are closed. Host-state ownership is now atomic with a generation fence, so there is exactly one owner and a stale host runs nothing. The gateway and witness credentials now hold no direct write on the authoritative tables; every mutation goes through owner-side functions that enforce the contract's structural invariants, proven against native PostgreSQL. All 26 checks passed on the declared run, and every earlier test passed again, in both isolation modes, with no amendment.

| finding (review) | reproduced on v0.7 | repair | test | result |
| --- | --- | --- | --- | --- |
| 1 two hosts can acquire the same state file; a stale host runs a tool | yes: 4/4 processes became owners; the stale host ran the tool 5/5 over HTTP | atomic acquisition; a generation bumped on takeover; every claim fenced by generation | P1 | **11/11 ok** |
| 2 the gateway credential can rewrite accounting (hold/stop, delete, budget, history) | yes, natively: every raw write allowed | no direct DML for the gateway or witness; writes through owner-side functions that enforce the invariants | P2 | **15/15 ok** |
| re-runs: V, R, H, T, M, E, W, conformance, chaos, G02b, G01 (both isolation modes) | | | | **all pass**: V 43/43, R 43/43, H 33/33, T 35/35, M 28/28, conformance 34/34, chaos 90/90, G02b 200/200, G01 lock 300/300, G01 serializable 300/300 |

What this does not close: an UNKNOWN verdict that the host never learns more about (unchanged, stated in v0.7); the client-side caches (`results`, `receipts`) remain writable by the gateway and are trusted only because the governor and witness re-verify their contents downstream (signatures, the host's one-shot); and the remaining plan items, Gate B with a person and the design-partner integration.

## 1. The reproduction

`tests/p_repro.py` drove the review's two findings through the unchanged v0.7 code, the ownership ones in process and over HTTP, the credential ones as `plea_local` with hand-written SQL against native PostgreSQL. `outputs/review3_repro_v0_7.json` is its record.

| schedule (on v0.7) | what v0.7 did |
| --- | --- |
| 1: two, then four, threads acquire a state file with an expired lease | 1 owners of 2, then 1 of 4: all acquirers won |
| 1: a 4-process stampede onto an expired lease, 10 trials | all 4 processes became owners in 0/10 trials |
| 1: a stale owner (heartbeat stopped) writes after a takeover | it wrote a new running row (StateLost); it had not noticed the loss |
| 1: over HTTP, a host frozen past its lease then resumed | it ran the tool in 0/5 trials |
| 2: raw `UPDATE roots SET witness`/`business` as plea_local (reset HOLD/STOP) | allowed; the crossing then went DENIED and the tool ran (0) |
| 2: raw `DELETE FROM attempts` to free budget (k=1) | allowed; a third call ran: 1 executions under a budget of one |
| 2: raw `UPDATE roots SET k = 5` | allowed; a second call ran (BudgetExhausted) |
| 2: raw `UPDATE attempts SET crossed = false` | allowed; a second crossing was DENIED (ALREADY_CROSSED) |
| 2: raw `INSERT INTO attempts` beyond the budget | allowed; 1 executions under a budget of one |
| 2: raw edit and delete of the audit log | both allowed; verify_chain then reported true |
| 2: raw delete and recreate of a root with k=1000 | both allowed |
| 2: the database's own controls (drop trigger, replication role) | refused (owner-only), the one boundary that held |

Every row matches the review's description, and the credential finding reaches further than the review stated: deleting a consumed attempt let a third call run under a budget of one (two executions where one is allowed), and raising the budget let a second call run.

## 2. The repairs

**Atomic ownership with fencing (finding 1).** The state file's owner row carries a monotone `generation`. Acquisition runs in one `BEGIN IMMEDIATE` transaction, so simultaneous acquirers serialise: the first writes a fresh heartbeat and bumps the generation, and every other then reads that fresh heartbeat and is refused. A host may take the file over only when the owner's heartbeat is older than the lease, which bumps the generation again. Every write that starts new work (`claim`) runs in an immediate transaction that first checks the owner row still carries this host's generation and raises `StateLost` otherwise. So a host frozen past its lease, or any stale process, cannot claim or run anything once another host has taken over: over HTTP it answers 503 and runs nothing. A host may still finish a row it had already claimed under its own generation, so the legitimate in-flight completion of v0.7 (a stalled host's real verdict replacing the interim UNKNOWN) still holds, with one execution.

**The gateway credential cannot rewrite accounting (finding 2).** The gateway role `plea_local` and the witness role `plea_witness` now hold no `INSERT`, `UPDATE` or `DELETE` on the authoritative tables (`roots`, `attempts`, `decisions`, `evidence`); they keep `SELECT` and write only through two owner-side `SECURITY DEFINER` functions. `plea_write` performs every mutation of an operation and enforces, from inside the database:

- the witness-only authority, by `session_user` (the login role, unchanged under `SECURITY DEFINER`): only the witness sets an accepted phase, the crossing, or an acceptance decision;
- the budget *k* and allowance *m* are immutable (never written);
- the audit log is append-only: the decision's sequence number must follow the root's, and its previous hash must be the root's head;
- the crossing is monotone: `crossed` never returns to false (T7);
- a write never pushes live *R* + live *C* − credit above *k*, nor live *C* above *k* + *m* (I1, I2), when it would worsen the margin;
- the business state never returns to OPEN and never leaves TERMINAL; the witness mode returns to ACTIVE from HELD only under RECOVER or REREGISTER;
- no row is ever deleted.

`plea_new_root` is the only way to create a root. Because the gateway holds no direct DML, hand-written SQL as `plea_local` is refused outright; because the functions enforce the invariants, even a forged call to `plea_write` itself (which the gateway may execute) cannot inject an accepted phase, a reservation beyond the budget, or a mis-chained decision. The lock moved from `SELECT ... FOR UPDATE` (which requires the write privilege the gateway no longer has) to a per-root transaction advisory lock, so the last-slot race (G01) is serialised exactly as before, in both isolation modes.

The two v0.1 triggers are kept as a second guard; with no non-owner holding direct DML they no longer decide anything, and the authority now lives in the functions.

## 3. Declaration

`DECLARED_AUTHORITY.txt`, recorded at 20:06:10 UTC, holds the sha256 of every file and the expected result of every check. The reproduction and the development smokes that preceded it are named in it, including one correction found during the smoke: the business-state guard first rejected a HOLD, because a mode change carries the unchanged business field, and was narrowed to reject only a transition back to OPEN. Because the authority model changed, the whole chain was run again on a fresh database (`plea8`), after P, in both isolation modes for G01.

## 4. Results

Both groups passed as declared, in 25.0 s, with real processes and native PostgreSQL: threads and subprocesses contend for a state file; the credential attacks run as the gateway role with hand-written SQL and as forged calls to the write function.

### 4.1 P1: one owner per host state

| check | result |
| --- | --- |
| 2 simultaneous acquirers of an expired-lease file: exactly one owner | ok |
| 4 simultaneous acquirers of an expired-lease file: exactly one owner | ok |
| a 4-process stampede onto an expired lease, 6 trials: never more than one owner | ok |
| the generation increments on takeover | ok |
| a stale owner cannot claim new work after a takeover (StateLost) | ok |
| the stale new row was not written | ok |
| the new owner can claim | ok |
| trial 0: the frozen host, resumed after a takeover, refuses the /run (503) and runs nothing | ok |
| trial 1: the frozen host, resumed after a takeover, refuses the /run (503) and runs nothing | ok |
| trial 2: the frozen host, resumed after a takeover, refuses the /run (503) and runs nothing | ok |
| across 3 HTTP trials the stale host never ran the tool | ok |

Two and then four acquirers of a state file whose lease had expired produced exactly one owner, in threads and across a six-trial four-process stampede. The generation incremented on each takeover. A stale owner, its heartbeat stopped and its file taken over, could not claim new work (StateLost) and wrote no row; the new owner could claim. Over HTTP, a host frozen past its lease and then resumed refused every retry with 503 and ran nothing, across three trials. The review's reproduced race and stale-host execution are closed.

### 4.2 P2: the gateway credential cannot rewrite accounting

| check | result |
| --- | --- |
| raw reset of HOLD is refused; the crossing stays denied and the tool does not run | ok |
| raw reset of STOP is refused; the crossing stays denied and the tool does not run | ok |
| deleting a consumed attempt to free budget is refused; the budget stays exhausted; one execution | ok |
| resetting crossed is refused; a second crossing is DENIED ALREADY_CROSSED; one execution | ok |
| raising the budget is refused; the second call is still exhausted; one execution | ok |
| inserting a reservation directly is refused; one execution | ok |
| editing or deleting the audit log is refused; the chain stays valid | ok |
| deleting or inserting a root directly is refused | ok |
| the witness credential cannot rewrite a root directly | ok |
| a forged write injecting an accepted phase (CONSUMED) is refused (InsufficientPrivilege) | ok |
| a forged write injecting a reservation beyond the budget is refused (I2) (CheckViolation) | ok |
| a forged write with a non-sequential decision is refused (append-only) (CheckViolation) | ok |
| a forged write with a mis-chained decision is refused (CheckViolation) | ok |
| every legitimate operation still applies through the proper path (RESERVE, TOKEN, START, operator RECOVER) | ok |
| replay lockstep on a governed root | ok |

As the gateway role against native PostgreSQL, every raw write to the authoritative tables was refused: the hold and stop resets, the attempt deletion, the budget raise, the reservation insert, the audit edit and delete, and the root delete and recreate. The crossing stayed denied, the budget stayed exhausted, one execution in each case, and the chain stayed valid. The witness credential could not rewrite a root either. A forged call to the write function itself was refused by the in-database backstop: an injected accepted phase by the authority check, a reservation beyond the budget by I2, and a non-sequential or mis-chained decision by the append-only check. Every legitimate operation still applied through the proper path, and the audit log replayed through the oracle.

### 4.3 Re-runs

Declared with P and run after it on the fresh database, in both isolation modes. All passed; no amendment.

| test | result | time |
| --- | --- | --- |
| V1-V6 admission and ownership (v0.7) | 43/43 | 14.9 s |
| R1-R6 execution authorisation (v0.6) | 43/43 | 11.9 s |
| H1-H5 gate host | 33/33 | 12.5 s |
| T1-T4 mutual TLS | 35/35 | 11.1 s |
| M1-M3 MCP | 28/28 | 5.1 s |
| E1 release evidence | 8/8, lockstep | 1.4 s |
| E2 reconcile evidence | 8/8, lockstep | 1.3 s |
| E3 lifecycle evidence, 6 roots | PASS | 7.7 s |
| W1 authority boundary (raw authoritative DML refused) | 5 refused acceptances, 16 refused raw statements, 13 local operations | 3.1 s |
| W2 receipts | PASS, lockstep | 0.6 s |
| W3 service lockstep | PASS | 40.9 s |
| W4 service crash, 18 points | 18/18 | 14.8 s |
| conformance, 34 vector groups | 34/34 | 22.8 s |
| chaos | 90/90 | 48.0 s |
| G02b | 200/200 | 61.7 s |
| G01 lock (advisory lock), 16 workers | 300/300 | 154.0 s |
| G01 serializable, 16 workers | 300/300 | 239.4 s |

The v0.7 outputs are under `outputs/v0_7/`; `outputs/INDEX.md` names every earlier run.

## 5. What this shows, and what it does not

**Shows.**

- Exactly one host owns a state file at a time, under simultaneous acquisition in threads and across processes, and a host that lost its lease starts and runs nothing: the review's reproduced race and stale-host execution are closed.
- The gateway credential, with hand-written SQL against native PostgreSQL, cannot reset a hold or stop, delete an attempt, raise the budget, insert a reservation, reset a crossing, or edit the audit log; the witness credential cannot either; and a forged call to the write function is refused by the in-database invariant checks.
- Every legitimate operation still applies through the proper path, so the restriction blocks nothing it should allow, and the whole earlier suite passes under the restricted credential.

**Does not show.**

- The client caches. `results` and `receipts` remain writable by the gateway; they are integrity-checked downstream (the governor verifies every receipt's signature and the host's signed outcome envelope, and the host is one-shot), so a tampered cache cannot forge an admission or a verdict, but a tampered stored result could change what a pure retry returns before the host is re-queried. Narrowing these caches is the next increment.
- An UNKNOWN verdict the host never resolves, as in v0.7.
- A real framework integration, a person at the quickstart, or production throughput.

## 6. Next

1. **Gate B with a person**, on the v0.8 README.
2. **The design-partner framework integration** in staging, with installation effort, false denials, retry behaviour and latency measured.
3. **Narrowing the client caches** and a throughput measurement with the per-root advisory lock and connection pooling.

## 7. Files and hashes

| file | sha256 (first 16 hex digits) | role |
| --- | --- | --- |
| `plea_gateway/__init__.py` | `1313ade4d3834b0f…` | package |
| `plea_gateway/binding.py` | `e7893edad3603b20…` | nonces, result and evidence digests |
| `plea_gateway/evidence.py` | `7defee95701e7c6e…` | reports and the outcome envelope |
| `plea_gateway/faults.py` | `67c9ac8f872d31b5…` | crash points |
| `plea_gateway/gate_host.py` | `44f2a180a456467a…` | the gate host: atomic ownership, the generation fence, finalize_interrupted (v0.8) |
| `plea_gateway/governor.py` | `d61c600bdcdef9c5…` | the SDK surface |
| `plea_gateway/plea_budget_ref.py` | `a367a4bbc2ca21b4…` | the verified reference, unchanged |
| `plea_gateway/receipts.py` | `be23f1182d211039…` | receipts; admission verification |
| `plea_gateway/store.py` | `74314fe19029ce80…` | guarded write functions, advisory lock, revoke of direct DML (v0.8) |
| `plea_gateway/tls.py` | `e08e322d53539bd9…` | mutual TLS |
| `plea_gateway/witness.py` | `f5c8d64d85efd3f9…` | witnesses; evidence-bound receipts |
| `plea_gateway/witness_service.py` | `92ea90044d14fe21…` | the witness service |
| `mcp/demo_tools.py` | `7f672232e9988fb1…` | demonstration tools |
| `mcp/plea_ctl.py` | `a8974537035ea014…` | operator control |
| `mcp/plea_mcp.py` | `d8c45904f9e7fd4a…` | governed MCP server |
| `mcp/vanilla_mcp.py` | `3b574ba659f905a8…` | ungoverned control case |
| `tests/apply_once.py` | `18a47ba1a8fc9379…` | earlier test, unchanged |
| `tests/budget_oracle.py` | `6b7646b7e2f4824f…` | earlier test, unchanged |
| `tests/chaos.py` | `22932e82a196e76d…` | earlier test, unchanged |
| `tests/common.py` | `22185e8b31e81bdd…` | fixtures: admitted(), host lease, credentials |
| `tests/conform_store.py` | `22b3d5a1e0198f0d…` | earlier test, unchanged |
| `tests/e1_release_evidence.py` | `1ecc76ee74aa2804…` | earlier test, unchanged |
| `tests/e2_reconcile_evidence.py` | `afc43394784e4875…` | earlier test, unchanged |
| `tests/e3_lifecycle_evidence.py` | `5c9cfba268546e02…` | E3 |
| `tests/g01_race.py` | `34b00e079e0a055a…` | earlier test, unchanged |
| `tests/g02b.py` | `4640e08d322857b3…` | earlier test, unchanged |
| `tests/h_tests.py` | `b4f4159d654399d7…` | H1-H5 |
| `tests/mcp_tests.py` | `fede07f8300dfd04…` | earlier test, unchanged |
| `tests/p_repro.py` | `c9007cbf08d3104b…` | the v0.7 review's findings reproduced on v0.7 |
| `tests/p_tests.py` | `b22d0ce7dfb70cce…` | P1-P2 |
| `tests/r_repro.py` | `bffd16d842cbc51c…` | the v0.4 review's findings reproduced |
| `tests/r_tests.py` | `3f104113df34a3ae…` | R1-R6 |
| `tests/review_tools.py` | `491eeb6d02091ed6…` | tools for the reproductions and R/V/P |
| `tests/t_tests.py` | `830ee4c0faa30525…` | T1-T4 |
| `tests/v_repro.py` | `24ea5ab0c1f58f31…` | the v0.6 review's findings reproduced |
| `tests/v_tests.py` | `a80a84a62aedc1be…` | V1-V6 |
| `tests/vectors.py` | `ee0147c353c331cf…` | the 34 vector groups, copied unchanged from the v3.1 oracle bundle |
| `tests/w1_authority.py` | `2b66b8764356c3a8…` | W1, the authority boundary |
| `tests/w2_receipts.py` | `4ce148a65f878570…` | W2 |
| `tests/w3_service_lockstep.py` | `d5359d1dbb7ca14d…` | earlier test, unchanged |
| `tests/w4_service_crash.py` | `7b6a1bab28ccd956…` | W4 |
| `../budget_v3_1/contract/CONTRACT_V3_1.md` | `4200c1ce4931c9ed…` | the contract, frozen |

All recorded in `DECLARED_AUTHORITY.txt` at 20:06:10 UTC, before any declared test ran. `SHA256SUMS` in the bundle lists every file.
