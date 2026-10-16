# PLEA gateway v0.1: the witness behind a service boundary, with signed receipts

12 October 2026 · week 2 of the commercialisation plan · follows the v0 gateway report · private working material, not for publication

## Summary

**Headline.** The witness now sits behind a boundary that the gateway's own code cannot cross. The database refuses every acceptance, and every accepted phase, to any role but `plea_witness`; the witness service is the only holder of that credential and of the Ed25519 key that signs receipts; the gate applies RECEIPT and CROSS only behind a receipt that verifies against the pinned key, names this attempt, and matches the hash in the local audit chain. All of this was declared before it ran. The boundary and the receipt barrier passed exactly as declared: 32 refusals and 9 rejected forgeries, with nothing blocked that should pass. The declared chain also found two defects, one in the client's verification scope and one in a test harness, and one wrong expectation in a declaration, all caught by declaring first; the fixes are labelled and every re-run is reported beside its original (sections 3.3 and 3.5).

| check | declared | result |
| --- | --- | --- |
| W1 authority: acceptances through the local credential | 4/4 refused by the database, state unchanged; 4/4 APPLIED through the witness credential | 4/4; 4/4 |
| W1 raw SQL as the local role (phase updates, phase inserts, forged log rows) | 14/14 refused | 14/14 |
| W1 local operations through the local credential | 14/14 APPLIED or NOOP | 14/14 |
| W2 receipts: forgeries against the gate | 9/9 rejected, attempt untouched; own receipt then crosses | 9/9; crossed |
| W3 lifecycle over HTTP, 80 governed calls on 8 roots | 24 executed, 24 denied, 32 retries served, 0 re-executed | **client fail** (amendment 1), then **expectation fail** (amendment 2), then 24 executed, 32 denied, 24 served, 0 re-executed |
| W3 G02b through the service, 100 rounds | 100/100 | 100/100 after amendment 1 |
| W4 service killed mid-acceptance, 18 kills | state pre or post; retry APPLIED (15) or DUPLICATE (3); receipts verify | 18/18; 15 APPLIED, 3 DUPLICATE; re-run 18/18 |
| re-runs under the split credentials: conformance, chaos, G02b, G01 both modes | all pass as in v0 | 34/34; 90/90; G02b **harness fail** then 200/200 after amendment 1; G01 1,000/1,000 and 1,000/1,000 |

What this closes from the plan: the witness as a service with signed receipts (next-step 1 of the v0 report), and the receipt barrier half of G02. What it does not close: evidence is still a label (G03); there is no TLS, no key rotation, no witness quorum; the service is a single process.

## 1. What was built

**The authority boundary (`store.py`, AUTHORITY).** Two triggers, installed once by the owner role:

- on the audit log: an insert whose operation is ACCEPT\_RESERVATION, ACCEPT\_INTENT, RELEASE or RECONCILE is refused unless the current role is `plea_witness`;
- on the attempts: a transition into RESERVED, CONSUMED, RELEASED, NO\_EFFECT or EFFECT is refused unless the current role is `plea_witness`.

The two together mean that the local credential cannot produce an accepted fact by any route: not through the gateway's code, and not with raw SQL. The owner role is exempt, so that setup and the conformance adapter can build states; it is an administrative credential never given to a gateway. The store translates the database's refusal into `AuthorityError` after the rollback.

**Receipts (`receipts.py`).** A receipt binds the root, the attempt, the audit sequence number of the acceptance, the operation, the decision kind and code, and the audit hash of that decision, and carries the signer's public key and an Ed25519 signature over the canonical JSON of the seven fields. Verification checks the signer against the pinned key, the fields against what the gate expects, and the signature.

**The witness service (`witness_service.py`).** A small HTTP service, standard library only, holding the `plea_witness` credential and the signing key. `POST /accept` takes one of the four acceptances and returns the decision, the sequence number, the hash and the signed receipt; anything else is refused. `GET /pubkey` publishes the key. In chaos mode only, a request header makes the process die at a named point of the transaction, for W4.

**The client (`witness.py`, `RemoteWitness`).** Posts the acceptance, verifies the receipt's signature before anything else trusts it, and raises `WitnessUnavailable` when the service cannot be reached, so the caller retries. Acceptances are idempotent by contract (5.2 rule 2, 5.5 rule 2), which is what makes the retry safe.

**The gate (`governor.py`, `gate_cross`).** RECEIPT and CROSS are applied only after the receipt verifies, and only if the hash it carries is the hash at that sequence number in this store's own audit chain. A receipt for the same attempt name on another root's chain therefore fails even though its signature is genuine.

**The governor** now holds the local credential, so the boundary applies to it too. It creates the root through an owner store once, and never uses that store again.

## 2. Declaration

`DECLARED_WITNESS.txt`, recorded at 07:29:51 UTC, holds the sha256 of every file and the expected result of every test, including the five re-runs. The v0 outputs are kept under `outputs/v0/`, with their declared run and the amended re-run. One development smoke preceded the declaration and is named in it.

## 3. Results

### 3.1 W1: the boundary

For each acceptance, on a state where it would be APPLIED: through the local credential the database raised `insufficient_privilege`, the transaction rolled back, and the observation and the audit log were unchanged; through the witness credential it was APPLIED, and the log replayed through the oracle. Then, bypassing the application, raw SQL as the local role tried to set each of the five accepted phases by update and by insert, and to insert each of the four acceptances into the log: 14 statements, 14 refusals, state unchanged. Finally all 14 local operations were APPLIED or NOOP through the local credential, so the boundary blocks nothing it should allow. 4.5 s.

### 3.2 W2: the receipt barrier

With the service running: a1's intent was accepted over HTTP and its receipt crossed the gate. a2's intent was then accepted, and the gate was tried with nine forgeries: a receipt signed by another key; a1's genuine receipt replayed for a2; the attempt field edited; the sequence number edited; the kind edited to APPLIED on a receipt that attested a DUPLICATE; a receipt for ACCEPT\_RESERVATION used as the intent receipt; the signature truncated; the hash edited; and a genuine receipt for an attempt of the same name on another root's chain. All nine were rejected, a2 had neither receipt nor crossing afterwards, and a2's own receipt then crossed. 1.4 s.

### 3.3 W3: the lifecycle over HTTP

**Declared run: FAIL.** Part B's first round killed the release racer. The service correctly DENIED the RELEASE (rule 3 while the intent was pending) and returned a signed receipt saying so. The client refused that receipt: its verifier applied the gate's rule, that a receipt must attest an acceptance, to every receipt it received. A receipt for a denied operation is a valid signed statement by the witness; only the gate, which is about to open a sandbox, should insist on APPLIED or DUPLICATE. The racer died on the exception and the parent timed out waiting for its result (71 s).

Nothing in the store, the boundary or the contract was wrong. The defect is in the scope of a check: the client's verification was stricter than its job, and that strictness broke a correct denial path. Part A, the 80 governed calls, had already passed inside the same run, as the per-root rows in the declared output show.

**Amendment 1 (recorded in `DECLARED_WITNESS.txt` after the declared chain finished).** `receipts.verify_signed` checks the signer, the fields and the signature, and is what the client uses; `receipts.verify` adds the acceptance requirement, and is what the gate uses. W2's "kind edited" forgery still fails at the gate. The v0 re-runs do not use the client and were not repeated; W2, W3 and W4 were re-run under the amended client.

**Re-run under amendment 1: part B PASS, part A FAIL on the declaration.** Part B, the race through the service, passed 100/100: the release DENIED and the acceptance APPLIED in every round, all 500 probes DENIED, acceptance first in 60 rounds and release first in 40. Part A ran all 80 calls and every root showed 3 executed, 4 denied, 3 retries served and 0 re-executed, with replay lockstep and chain ok. The declaration had said 3 denied and 4 retries served. The schedule's fourth retry is of a key that was DENIED at the budget: no attempt exists for it, so the contract denies the retry again (5.1 rule 6). It is not a DUPLICATE, and the gateway was right not to serve it. The declaration had miscounted.

**Amendment 2** corrects the harness's expectation to the contract's numbers, with the amendment-1 output kept in `outputs/amend1_w3/`.

**Re-run under amendment 2: PASS.** 24 executed, 32 denied, 24 retries served from the stored result, 0 re-executed, 0 other errors, across 80 governed calls on 8 roots, every one over HTTP with the governor on the local credential and every CROSS behind a verified receipt. Part B 100/100 again. 55 s.

### 3.4 W4: the service dies mid-acceptance

**Declared run: PASS**, 18/18 kills in 19 s. For each of three acceptances (ACCEPT\_RESERVATION, ACCEPT\_INTENT, RECONCILE) and each of the six crash points: the service, started in chaos mode with a fixed key, died at that point while applying the acceptance (exit 137), and the client saw `WitnessUnavailable`. The state equalled the pre-state for the five in-transaction points and the post-state after commit, in all 18 cases. The service was restarted with the same key and the same acceptance was retried: APPLIED in the 15 cases where the crash had been before commit, DUPLICATE in the 3 cases after commit. Every retry's receipt verified; for the three intent cases the gate then applied RECEIPT and CROSS behind it. Replay lockstep and the hash chain held after every kill.

This is the service-side half of G02's crash barrier: an acceptance is all or nothing, and a retry after the witness dies is safe because the contract makes identical acceptances DUPLICATE.

**Re-run under amendment 1:** PASS, 18/18, 15 retries APPLIED and 3 DUPLICATE, every crash point 3/3, 19 s.

### 3.5 The v0 tests under the split credentials

The v0 tests were re-run with callers on the local credential and acceptances on the witness credential, which is how a deployment would run. Conformance 34/34; chaos 90/90; G01 row lock 1,000/1,000 both waves with 20,638 reader snapshots and 0 violations (620 s); G01 serializable 1,000/1,000 with 0 worker errors, 25,402 snapshots and 0 violations (964 s). Across the two G01 runs, 71,000 decisions replayed through the oracle with no disagreement.

**G02b, declared run: FAIL, in the harness.** In every one of the 200 rounds the store behaved correctly: the final state was CONSUMED with accepted *C* = 1, the invariants held, the hash chain verified, the audit log replayed through the oracle, and the log showed both the acceptance and the release recorded (acceptance first in 128 rounds, release first in 72). But the harness reported no decisions at all, because when the racer was repointed at the split credentials the line that records each decision was left after a trailing comment on the same line, and so was commented out. The checks that read the audit log passed; the checks that read the racers' reports failed on empty lists.

**Amendment 1** restores that line. The declared output is kept; G02b was re-run: 200/200, the release DENIED and the acceptance APPLIED in every round, all 1,000 probes DENIED, acceptance first in 139 rounds and release first in 61, replay lockstep and chain ok throughout, 87 s.

Two findings in one declared chain, both in harness or client code and neither in the store, the boundary or the contract. The declaration is what made them findings rather than quiet edits.

## 4. What this shows, and what it does not

**Shows.**

- Acceptance is a capability of the witness credential, enforced by the database. A gateway cannot forge an accepted fact, whatever its code does.
- A receipt cannot be forged, replayed for another attempt, moved to another chain, or altered, and the gate will not open without one.
- An acceptance interrupted by the service's death is either fully recorded or not at all, and the retry after restart is safe: APPLIED if it had not landed, DUPLICATE if it had, with a valid receipt either way.
- Everything the v0 gateway showed still holds with callers on the local credential and acceptances on the witness credential.

**Does not show.**

- Evidence (G03): BOUND\_FENCE and AUTHORISED are still labels the caller supplies to RECONCILE and RELEASE. The boundary ensures only the witness can apply them; it does not verify them.
- Transport security: the service listens on loopback without TLS. The receipts are signed, so a tampered response is detected, but the request is not authenticated.
- Key management: one key, generated at start or supplied; no rotation, no revocation, no second witness.
- The hold, lease and epoch slice of PLEA.

## 5. Observations from the build

- **Putting the boundary in the database was the right call.** The W1 raw-SQL cases are the proof that it does not depend on the gateway's code at all. A boundary in application code would have needed a code audit to claim the same.
- **Binding the receipt to the audit hash made the cross-root replay fail for free.** The same attempt name on another root has a genuine signature and the wrong hash.
- **The contract's idempotent acceptances are what make W4 simple.** No request identifiers, no deduplication table: the retry is just the same acceptance again.
- **The owner exemption is a wart.** The conformance adapter needs to construct states directly, which the triggers would refuse. A cleaner design gives the adapter its own role with a narrower exemption. It is noted, not fixed.

## 6. Next

1. **Evidence (G03).** Replace the labels with evidence the witness verifies: a fence token bound to the attempt for RELEASE, and a signed effect or no-effect attestation for RECONCILE.
2. **The MCP wrapper**, so an agent's tools are governed without changing the agent.
3. **Transport and keys:** TLS or a mutual-auth channel to the service, and key rotation with a key identifier in the receipt.
4. **A throughput measurement** with connection pooling.

## 7. Files and hashes

| file | sha256 (first 16 hex digits) | role |
| --- | --- | --- |
| `plea_gateway/__init__.py` | `4180970ecf183449…` | package |
| `plea_gateway/faults.py` | `67c9ac8f872d31b5…` | crash points |
| `plea_gateway/governor.py` | `2630347b92365f09…` | SDK surface and the gate |
| `plea_gateway/plea_budget_ref.py` | `a367a4bbc2ca21b4…` | the verified reference, unchanged (decision engine) |
| `plea_gateway/receipts.py` | `0b6de9b374e2cbdc…` declared; `7a72297f57850803…` after amendment 1 | Ed25519 receipts |
| `plea_gateway/store.py` | `7ec6a48ed255b2b3…` | the transactional store and the AUTHORITY triggers |
| `plea_gateway/witness.py` | `3275ee5b1ae7f34c…` declared; `8386997a0a0c4268…` after amendment 1 | in-process witness and the HTTP client |
| `plea_gateway/witness_service.py` | `e38e89fcdf084bbe…` | the witness service |
| `tests/apply_once.py` | `18a47ba1a8fc9379…` | chaos child |
| `tests/budget_oracle.py` | `6b7646b7e2f4824f…` | the oracle, unchanged (replay lockstep) |
| `tests/chaos.py` | `22932e82a196e76d…` | chaos runner |
| `tests/common.py` | `62e148586449b1ab…` | credentials, replay lockstep, the service as a subprocess |
| `tests/conform_store.py` | `22b3d5a1e0198f0d…` | section 8 adapter over the store |
| `tests/g01_race.py` | `34b00e079e0a055a…` | G01 |
| `tests/g02b.py` | `aa910a9ab41eef6b…` declared; `4640e08d322857b3…` after amendment 1 | G02b |
| `tests/w1_authority.py` | `061df2240a9d1e33…` | W1 |
| `tests/w2_receipts.py` | `ae80070baa9eb532…` | W2 |
| `tests/w3_service_lockstep.py` | `ee4cd7c5ebe76e13…` declared; `692004dced8fe45a…` after amendment 2 | W3 |
| `tests/w4_service_crash.py` | `13188e9cbf0f4031…` | W4 |
| `../budget_v3_1/contract/CONTRACT_V3_1.md` | `4200c1ce4931c9ed…` | the contract, frozen |

The declared hashes were recorded in `DECLARED_WITNESS.txt` at 07:29:51 UTC, before any declared test ran; the amended hashes are recorded there under amendments 1 and 2, each after the run that found the defect. `SHA256SUMS` in the bundle lists every file as shipped.
