# PLEA gateway v0: the budget contract over a real store, with G01 and G02b run

12 October 2026 · week 1 of the commercialisation plan · private working material, not for publication

## Summary

**Headline.** The attempt-budget contract now runs over PostgreSQL, with the verified pure reference as its decision engine, and the two gateway tests that mattered most are no longer NOT RUN. G01 held in 1,000 of 1,000 raced rounds under the row lock, and G02b in all 200. The declared run also found one defect, in the alternative isolation mode, which the declaration caught, the fix is labelled, and the re-run is reported beside the original (section 3.5). Every result was declared before it ran.

| check | declared | result |
| --- | --- | --- |
| store-backed implementation through the 34 vector groups | 34/34 | 34/34 |
| chaos: kills at 6 points of the transaction, 15 operations | 90/90 land in the pre- or post-state, chain and lockstep intact, no lock left behind | 90/90 |
| G02b: release raced against an in-flight acceptance | 200/200: release DENIED, acceptance APPLIED, no slot freed | 200/200; both orders occurred (121 acceptance-first, 79 release-first) |
| G01, row lock: last-slot race, 16 processes, *k* = 3 | 1,000/1,000 rounds exactly *k* admitted, recovery frees exactly the dead reservations, 0 reader violations | 1,000/1,000; 19,638 reader snapshots, 0 violations; 600 s |
| G01, SERIALIZABLE with retry | the same | **FAIL in round 0** as declared: a liveness defect in the store (section 3.5); re-run after the labelled fix: 1,000/1,000, 0 worker errors, 0 reader violations |

What this closes from the plan: Gate A, in the row-lock mode that the governor uses by default. Admission holds under real concurrency across processes, with crashes between local commit and acceptance, and the store's serialization order replays through the independent oracle without a single disagreement.

What it does not close: G03 (evidence is still a label), G04 (no timed holders), G05 (no epochs), G06 (no witness profiles). The witness is in process. There is no service boundary, no signed receipt, and no SDK beyond a single Python call.

## 1. What was built

The design follows contract v3.1 section 1: the reference computes decisions over trusted facts; the gateway supplies transactional storage, the witness's acceptances, the gate and the audit.

**The store (`store.py`).** One transaction per operation:

1. Validate the operation with the reference's parser before touching the store. Malformed input never reaches the database.
2. Lock the root row with `SELECT … FOR UPDATE`, or run SERIALIZABLE and retry on serialization failure. Both modes are implemented and both were tested.
3. Rebuild the state from the attempt rows. No counter is stored anywhere. The reference's constructor validates the state on the way in.
4. Decide with the reference: `apply(state, op)`.
5. If APPLIED, write the changed attempt rows and the root's modes.
6. Append the decision to the audit log, whatever its kind, with a hash over the previous hash, the sequence number, the operation, the decision and the observation after it.
7. Commit.

**The witness (`witness.py`).** Each acceptance is its own transaction. That makes RESERVING and INTENT\_PENDING real states on disk, which is what G01's crash injection and G02b's in-flight acceptance need.

**The governor (`governor.py`).** One call runs the lifecycle: RESERVE, acceptance, TOKEN, START, acceptance, RECEIPT, CROSS, the call, RECONCILE. The attempt identity is derived from the request key, so a retry is RESERVE with the same identity and key: the contract's DUPLICATE, in any phase and any mode. The governor then returns the stored outcome instead of running the call again. Denials raise `BudgetExhausted`, `Held` or `Stopped`, chosen from the observation rather than from the wording of a code.

**Fault injection (`faults.py`).** Six named points in the transaction at which a process can be made to die without cleanup.

Lines, excluding the vendored reference and oracle: about 440 in the package and 490 in the tests, docstrings included.

## 2. Declaration

`DECLARED_GATEWAY.txt`, recorded at 04:52:52 UTC, holds the sha256 of every file and the expected result of every test. Two development smoke runs preceded it and are named in it: one governor lifecycle, one adapter step. Nothing was changed after the declaration.

## 3. Results

### 3.1 Conformance of the store-backed implementation

The store sits behind contract v3.1's section 8 interface (`tests/conform_store.py`). Every vector step is a round trip: the handle's snapshot is written to its root when the database has moved on, the operation is applied by the store's transaction, and the new state is read back. All 34 groups pass in 30 s. This exercises the persistence of every phase and fact, validation before the store, and the apply path. It does not exercise concurrency; that is G01's job.

### 3.2 Chaos

For each of 15 operations, a root is prepared so that the operation is APPLIED, and a twin root gives the expected post-state. A child process then applies the operation and is killed at one of six points. 90 kills in 59 s:

- every child exited 137;
- for the five in-transaction points the state equalled the pre-state, and after commit it equalled the post-state;
- the invariants held, the hash chain verified, and the audit log replayed through the oracle, after every kill;
- a follow-up operation succeeded on every root: the server released the row lock when the connection dropped.

### 3.3 G02b: release-then-accept

200 rounds. On a root with *k* = 1, a START\_INTENT is committed locally, then three processes race: the witness's acceptance after a random delay, a RELEASE after a random delay, and five RESERVE probes for a freed slot.

- The release was DENIED in all 200 rounds: by rule 3 while the intent was pending, or by rule 4 once it was consumed.
- The acceptance was APPLIED in all 200.
- All 1,000 probes were DENIED. No slot was ever freed.
- Every round ended with the attempt CONSUMED and accepted *C* = 1.
- Both orders occurred: acceptance first in 121 rounds, release first in 79. The scheduler produced both; the gateway was correct under both.

### 3.4 G01: the last-slot race

Declared: 1,000 rounds, 16 worker processes, *k* = 3, in both isolation modes. The declared row-lock run is reported here; the re-runs of both modes under the amended store are in section 3.5. Each round:

1. **Wave 1.** On a fresh root, 16 processes release from a barrier and each RESERVE a distinct attempt. Exactly 3 must be APPLIED and 13 DENIED.
2. **Crash by omission.** *j* of the 3 winners are accepted by the witness, where *j* cycles through 0 to 3. The other 3 − *j* are left RESERVING: the state a caller leaves behind when it dies between its local commit and the witness's acceptance.
3. **Recovery.** HOLD, then RECOVER(true, true). The never-accepted reservations must become DISCARDED and the live view must be (*j*, 0, 0).
4. **Wave 2.** 16 fresh processes RESERVE again. Exactly 3 − *j* must be APPLIED.
5. **Checks.** A reader thread observes the root throughout, from consistent snapshots, and checks I1, I2, I3 and I6 on each. The audit log is replayed through the oracle. The hash chain is verified.

**Row-lock mode, declared run:** PASS.

| measure | result |
| --- | --- |
| rounds with wave 1 exactly 3 APPLIED | 1,000 of 1,000 |
| rounds with wave 2 exactly 3 − *j* APPLIED | 1,000 of 1,000 |
| RESERVE operations under contention | 32,000 |
| recoveries APPLIED, reservations DISCARDED | 1,000; 1,500 |
| reader snapshots, invariant violations | 19,638; 0 |
| rounds with replay lockstep ok, chain ok | 1,000; 1,000 |
| decisions replayed through the oracle | 35,500 |
| wall time | 600 s |

**Serializable mode, declared run:** FAIL in round 0. Section 3.5.

### 3.5 The finding: serializable mode, as declared, could not survive the race

The store offers two ways to serialise operations on a root: lock the root row, or run the transaction SERIALIZABLE and retry on a serialization failure. The governor uses the lock. Both were declared to pass G01.

**What happened.** In serializable mode, round 0: two workers read the root's sequence number (7) in the same instant. The first updated the log and committed. The second then inserted its log row with the same sequence number and hit the log's primary key. PostgreSQL reports that as a unique violation, not as a serialization failure, so the store did not retry; the worker died with the exception, and the harness, waiting for the dead worker's result, hung until its one-hour limit.

**What it was not.** A safety failure. The failed transaction rolled back. The state and the chain were intact; the lock-mode run that had just completed had checked 1,000 rounds of the same operations. The defect is in liveness: one of two racing callers crashed instead of retrying.

**The fix (amendment 1, recorded in `DECLARED_GATEWAY.txt` after the declared runs).**

- In `store.py`, the root row is updated before the log row is inserted. Two transactions that read the same sequence number now collide on the root row. The second fails there with a serialization failure, which the store retries from the start.
- In `g01_race.py`, a worker reports an error instead of dying silently, the parent times out instead of hanging, and any worker error fails the run.

**The re-run.** All five tests were re-run under the amended store, declared before running, with the original outputs kept in `outputs/declared/`.

| test | declared run (04:52 declaration) | re-run under the amended store (05:55 amendment) |
| --- | --- | --- |
| store through the 34 vector groups | 34/34 | 34/34 |
| chaos, 90 kills | 90/90, 59 s | 90/90, 54 s |
| G02b, 200 rounds | 200/200; acceptance first 121, release first 79 | 200/200; acceptance first 123, release first 77 |
| G01, row lock, 1,000 rounds | 1,000/1,000; 19,638 reader snapshots, 0 violations; 600 s | 1,000/1,000 both waves; 20,079 snapshots, 0 violations; 583 s |
| G01, serializable, 1,000 rounds | FAIL, round 0 | 1,000/1,000 both waves; 0 worker errors; 24,888 snapshots, 0 violations; 944 s |

Serializable mode is correct now, and about 1.6 times slower than the row lock under this contention, because losers retry from the start. The governor keeps the row lock as its default.

**What it says about the method.** The row-lock mode passed first time. The alternative was declared to pass as well, and it did not. Without the declaration there would have been a temptation to drop the failing mode quietly, or to report the lock-mode pass as the result. The declaration made the failure a finding with a fix, which is the point.

### 3.6 Replay lockstep

The store's audit log is the serialization order the database chose. After every G01 round, every G02b round and every chaos kill, that log was replayed through the independent oracle from the initial state, and every recorded decision kind and observation was compared. Across the two G01 runs under the amended store that was 71,000 decisions over 2,000 roots, with no disagreement; the declared row-lock run added another 35,500. This is B17's lockstep at runtime, with the database rather than an enumerator choosing the order.

## 4. What this shows, and what it does not

**Shows.**

- The admission rule holds under contention across processes, in both isolation modes. Exactly *k* callers win the race, every time.
- A caller that dies between its local commit and the witness's acceptance leaves a RESERVING row that verified recovery discards, freeing exactly its slot and nothing more.
- A release cannot free a slot while an intent is pending or after it is consumed, whichever order the race produces.
- A crash at any point of the transaction leaves the store in the state before or after, never between, with the audit chain intact.
- A retry of the same request is answered from the stored outcome. The governed function runs once.

**Does not show.**

- Authenticated evidence (G03). BOUND\_FENCE and AUTHORISED are still labels the caller supplies.
- Timed holders and nonce races (G04), epochs and replacement gates (G05), witness-profile defects (G06).
- A witness behind a service boundary with signed receipts. The in-process witness shares the store.
- Throughput. The tests measure correctness. One transaction per operation with a fresh connection each time is deliberately simple, and it is not a performance design.
- Anything about the hold, lease and epoch slice of PLEA, which has no reference implementation at this standard yet.

## 5. Observations from the build

- **Deriving the attempt identity from the request key is the right SDK design.** It turns the contract's DUPLICATE rule into the idempotency guarantee a caller wants, with no extra lookup table deciding anything.
- **Recomputing the view under the lock is cheap at this scale and removes a whole class of bugs.** A stored counter would have to be kept consistent with the rows; there is none.
- **The audit hash chain doubled as the test oracle's input.** Replaying it is the cheapest strong check available, and it will carry over to a witness service unchanged.
- **Error classification belongs to the observation, not the code string.** The first draft guessed from code wording and was wrong for the held case. The observation carries the witness and business modes, so the governor reads them.

## 6. Next

In the plan's order:

1. **Witness as a service** with signed receipts, behind the same store API. The replay lockstep stays the check.
2. **Evidence (G03).** Replace the labels with verified evidence from the fence or sandbox.
3. **The MCP wrapper**, so an agent's tools are governed without changing the agent.
4. **A throughput measurement**, with connection pooling, before any number is quoted.
5. **Gate B:** a stranger governs a tool call in under 30 minutes from the quickstart alone.

## 7. Files and hashes

| file | sha256 (first 16 hex digits) | role |
| --- | --- | --- |
| `plea_gateway/__init__.py` | `6c2086264aa58666…` | package |
| `plea_gateway/faults.py` | `67c9ac8f872d31b5…` | crash points |
| `plea_gateway/governor.py` | `cdd433bb0c19c252…` | SDK surface |
| `plea_gateway/plea_budget_ref.py` | `a367a4bbc2ca21b4…` | the verified reference, unchanged (decision engine) |
| `plea_gateway/store.py` | `91591264c253fb71…` | the transactional store |
| `plea_gateway/witness.py` | `2f6b82191b77ee4b…` | the in-process witness |
| `tests/apply_once.py` | `b7b54bbcfa5b825f…` | chaos child |
| `tests/budget_oracle.py` | `6b7646b7e2f4824f…` | the oracle, unchanged (replay lockstep) |
| `tests/chaos.py` | `cd37e410cbdda49d…` | chaos runner |
| `tests/common.py` | `21b955e91ecd87ac…` | replay lockstep, invariants |
| `tests/conform_store.py` | `cc3bc13ed368735e…` | section 8 adapter over the store |
| `tests/g01_race.py` | `a4c1ebe3c9c45a06…` | G01 |
| `tests/g02b.py` | `77b27012245fcdb7…` | G02b |
| `../budget_v3_1/contract/CONTRACT_V3_1.md` | `4200c1ce4931c9ed…` | the contract, frozen |

All recorded in `DECLARED_GATEWAY.txt` at 04:52:52 UTC, before any declared test ran.

`SHA256SUMS` in the bundle lists every file.
