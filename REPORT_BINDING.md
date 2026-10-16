# PLEA gateway v1.2 — every record the contract's own decision, and every budget anchored to its provisioning

**The response to the v1.1 independent review (NOT CLEARED for broad provenance claims).** Date 2026-10-13. Database PostgreSQL 16.13. Every v1.2 result below comes from the declared run recorded in `DECLARED_BINDING.txt`, whose hashes were frozen before the run. The exceptions are the reviewer's probe and offline scripts, run unchanged on shipped v1.1 before any repair and on v1.2 after, and the new X suite's run on shipped v1.1 before the repair.

---

## 1. The findings

The v1.1 review judged the v1.1 fixes for false APPLIED records and unauthorised provisioning credible within the evidence, and kept broader provenance sign-off **not cleared**. It ran the release manifest (480/480), the report identity, the Python syntax and the 34 oracle vector groups, then raised four findings from the source. It had no PostgreSQL, so it supplied a native probe and asked for it to be run unchanged.

- **P1 — provisioning is not in the audit history (confirmed).** `plea_new_root` inserted the root at `seq = 0` and appended no decision. A verifier could check every later entry, but nothing attested who authorised the original `k` and `m`.
- **P2 — the genesis is supplied by the caller (confirmed).** `plea_new_root(root, k, m, p_head)` stored `p_head` unchecked. A direct privileged call could start a root's chain anywhere. `verify_chain` would then reject the root, so this was detectable but not prevented.
- **P3 — operation operands are not bound to the changed rows (source-supported, native test open).** v1.1 checked the operation's *name* against each row's transition, not its arguments, and not that a single RESERVE changes a single row. A record could say `RESERVE declared-aid` while inserting `actual-aid`, or one RESERVE could insert two reservations, with a valid hash chain.
- **P4 — refusal authenticity (declared limit).** A DENIED or NOOP record that changes nothing could carry a caller's code and an operation never requested. Replay catches a refusal the contract would not give. It cannot show that a plausible refusal was requested.

It also proposed explicit clearance criteria (§4) and asked for the same discipline as before: run the probe unchanged first, keep the failures, declare the tests and expectations, repair, re-run everything in both isolation modes on a clean database, and verify the exported release.

---

## 2. Reproduction on shipped v1.1, before any repair

All in `outputs/review7/`, run on a fresh extraction of the shipped zip, byte-identical to the reviewer's copy (`3e313964…`), and fresh disposable databases.

- **The reviewer's offline scripts**, unchanged, reproduce their recorded results exactly: `review_checks.py` gives the same JSON, with all 9 results matching, and `model_counterexamples.py` gives the same three model consequences.
- **The native probe** (`native_pg_v11_PROBES_NOT_RUN.py`, sha256 `a47052ef…`) was run unchanged on shipped v1.1. It completed without a harness error, unlike last round's. **All four source findings reproduce natively:**

| probe (the reviewer's) | shipped v1.1 |
|---|---|
| **A.** provision as `plea_control`, then inspect | root at `seq 0`, **no decision**, `verify_chain` ok; nothing records the provisioning |
| **B.** `plea_new_root` with a caller's 64-character starting hash | **ACCEPTED**; `verify_chain` then fails ("root head does not match the log") |
| **C.** as `plea_local`: `[RESERVE, declared-aid, declared-request]` recorded while inserting `actual-aid` | **ACCEPTED**; `verify_chain` **ok**; the log names an attempt that does not exist |
| **D.** as `plea_local`: one `[RESERVE, a1, q1]` record inserting `a1` **and** `a2` | **ACCEPTED**; `verify_chain` **ok**; two reservations, one logged operation |
| **E.** as `plea_local`: `[STOP]` recorded as DENIED (`SYNTHETIC_REFUSAL`) on an OPEN run | **ACCEPTED**; `verify_chain` **ok**; the contract would have applied STOP |

The reviewer asked that an accepted record also be checked against oracle replay. Replaying each root's log through the independent oracle (`native_pg_v11_before_REPLAY.*`) **detects C, D and E after the fact**: two observations differ, and the oracle gives APPLIED for the STOP. `verify_chain` detects B. So v1.1's history was checkable but not *guarded*. The database accepted all four at write time, and a hash-valid log carried them.

- **The new X suite, run on shipped v1.1 before the repair**, passes **6 of 35** (§5). Its mutation sweep shows the size of the gap. Over 720 genuine decisions, 2,252 mutated records were *not* the contract's own decision. **v1.1 accepted 1,876 of them** and refused 376 under its earlier rules. It refused none of the 994 that were.

---

## 3. The repair

Confined to `plea_gateway/store.py` (the schema, the write function, the provisioning function, two owner-only helpers, two trigger functions behind three triggers, the grants, and the Python side of provisioning and verification) and `mcp/plea_ctl.py` (`provenance`; `provision` prints the anchor). The reference engine, governor, gate host, witness, evidence, receipts and TLS are byte-identical to v1.1.

### 3.1 Every budget has an origin (P1, P2)

- **A provisioning log.** `plea_new_root(root, k, m)` appends one record to `provisions` — the root, `k`, `m`, the issuing credential (`session_user`), the contract (`attempt-budget contract v3.1`), the release (`plea-gateway v1.2`) and the database's clock — hash-linked to the record before it (the first to the genesis), with the same canonical form and hash as the decision chain. Provisionings serialise on a transaction advisory lock, so the log is one contiguous chain.
- **The anchor.** The root's decision chain starts at its record's hash. The database computes it; the argument that took a caller's starting hash is gone, and on an upgraded database the old 4-argument function is dropped, so the reviewer's probe B now finds no such function.
- **Immutable.** No login role holds INSERT, UPDATE, DELETE or TRUNCATE on the log; a trigger refuses UPDATE, DELETE and TRUNCATE to the owner too. A root's identity, `k`, `m` and record are immutable (trigger). `plea_write` refuses to write to a root that carries no record.
- **Verified.** `verify_chain` checks that the root's record hashes to itself and names this root, `k` and `m`, starts the chain at the anchor, and checks every recorded observation against the provisioned `k` and `m`. `verify_provisioning` walks the whole log. `plea_ctl.py ROOT provenance` prints the record and runs both.
- **Kept out of the decision log, deliberately.** The reviewer asked whether a provision register or a world-level `NEW_ROOT` event was intended. A separate log: a root's decision log is replayed through the contract's single-root step, which has no `NEW_ROOT`; putting provisioning in it would change that replay. The anchor ties the two together.

### 3.2 Every record is the contract's own decision (P3)

v1.1 bound the operation's *name* to each row's transition. v1.2 binds the whole operation. `plea_step` is the contract's single-root step in PL/pgSQL — a port of the reference engine (`plea_budget_ref.apply`) with its decision codes: evaluation step 1 (a malformed operation is refused), step 2 (an INDETERMINATE attempt is frozen), step 3 (each operation's rules in the contract's order, the first match deciding). After every earlier rule has passed, `plea_write` evaluates it on the observation taken *before* the write and requires the record to be exactly its result:

- **the kind and the code** the contract gives for the named operation on that state, and
- **the state after the write** — every attempt row and every mode — equal to the state the contract's transition produces.

So the operands are bound (a RESERVE logged for one attempt cannot insert another; a START cannot record another nonce; a RECONCILE another verdict; a RELEASE without its fence label is not applied), a batch is exactly the contract's batch (RECOVER discards every unaccepted reservation and returns every pending intent to TOKEN, or does nothing; REREGISTER freezes every unresolved attempt), one operation changes one attempt where the contract says one, and every mode guard holds (no TOKEN, START, RESERVE or CROSS outside ACTIVE and OPEN, no acceptance while HELD, no TERMINAL with an unresolved attempt). The new check comes **after** every v0.8–v1.1 rule, so each earlier test still meets the rule it was written for, and only what passed all of them reaches the new one.

The engine is a second implementation of the contract in the authority's path, so it is held to the first: on every state of two complete bounded explorations and every operation and label, `plea_step` gives the reference engine's kind, code and observation and the independent oracle's kind and observation (X4); it rejects exactly the malformed operations the reference's parser rejects; and every genuine decision of every suite passes through it.

### 3.3 Refusals are checked too, and the control plane's are its own (P4)

The same evaluation covers a record that changes nothing: a DENIED, NOOP or DUPLICATE must be the contract's own for the operation named, with its code. The reviewer's probe E — STOP recorded as DENIED on an OPEN run — is refused, to every credential; so is an invented code, and a NOOP or DUPLICATE the contract would apply. And a control-plane operation is recorded only by the control plane, applied **or refused**, as the witness's have been since v0.7: the gateway cannot write "HOLD refused" into a run's history.

**The limit, stated.** A refusal the contract *does* give for the current state — a RESERVE on an exhausted budget, DENIED `BUDGET_EXHAUSTED` — can still be recorded by the gateway for a request that never reached it. It changes no state, frees nothing, admits nothing and replays clean. The database can prove that a refusal is the contract's; it cannot prove that the request was made. Under the threat model the reviewer stated, where the agent and the gateway are the same compromised party, a signature on the request would come from that party too; refusal records are operational diagnostics, not evidence that a request was made.

### 3.4 Evidence rows belong to their decision (found while closing P3)

`plea_write` also stores, with a RELEASE or RECONCILE, the report the witness verified and the label it derived. v1.1 took that row's attempt, sequence number and label from the caller, for any operation and any credential. So the gateway could attach a row to its own harmless record under the *next* sequence number — and the witness's genuine RELEASE at that number then failed on the duplicate key — or plant a label no witness derived. v1.2 records an evidence row only for the witness, only with a RELEASE or RECONCILE, and only for this decision's attempt, sequence number and label (X2; on v1.1 the same check shows the witness's RELEASE failing).

---

## 4. Against the reviewer's clearance criteria

The review proposed explicit criteria for a compromised agent or gateway holding only `plea_local`, with the witness, the control plane, the owner, the gate's signing key and the state-store host trusted. Each, with where it is shown:

| criterion | v1.2 | shown in |
|---|---|---|
| no unauthorised budget creation | the gateway cannot provision (v1.1); every budget now has a record naming its issuer | U2, X1 |
| no modification of accepted facts | transition relation (v0.9), immutable bindings (v1.0), and now every row must be the contract's transition | Q1, S1, X2 |
| no execution without a witnessed CROSS | the host runs nothing without the witness's admission receipt (v0.7); CROSS is the witness's to record and, now, only when the contract allows it | V1–V6, R, H, X2 |
| every authoritative APPLIED record names its changed state and its target accurately | the observation, kind, operation name and hash are the database's (v1.1); now the operands, the batch, the guards and the code are the contract's own | U1, X2, X4 |
| a verifiable creation anchor | the provisioning log; the chain starts at the record's hash; verify_chain checks it | X1 |
| the crash, admission, recovery and one-shot behaviours preserved | the full regression, both isolation modes | §6 |

**What remains outside these criteria**, stated so the boundary is not overstated:

- **Refusal provenance** (§3.3). A refusal the contract gives can be recorded for a request never made. It changes nothing.
- **A second implementation of the contract now sits in the authority's path.** The evidence that it is faithful is differential, over complete bounded explorations and every suite's traffic, not a proof. A divergence would fail closed: a genuine write the database's engine disagreed with would be refused, not misrecorded.
- **The trusted components stay trusted.** The owner can still disable a trigger or drop a table; `verify_chain` and `verify_provisioning` detect a changed budget, a moved anchor or an altered record, but a database administrator is outside this boundary by the review's own statement. The control plane can provision any budget; the log records that it did, and which credential did it. A per-operator identity in that record needs a login per operator, which v1.2 does not add.

---

## 5. X1–X4: the new tests, before and after

Written before the repair and run first against the shipped v1.1, failures kept (`outputs/review7/x_tests_before_v1_1.*`); then in the declared v1.2 run. The forgeries hold every v1.1 rule — the right operation name, the database's observation, a correct hash — and are written by the credential that genuinely performs the operation, so the only thing that can refuse them is the new binding. The forgeries of X2.3, X2.5, X2.6, part of X2.8 and the sweep run in a transaction that is rolled back. The reviewer's probes, the malformed records and the X3 records are committed, to show that a refusal leaves no trace.

| | check | shipped v1.1 | v1.2 |
|---|---|---|---|
| X1.1 | a provisioning appends a record: root, k, m, issuer, contract, release, database time | **FAIL** | pass |
| X1.2 | the chain starts at the record's hash, which recomputes outside the database | **FAIL** | pass |
| X1.3 | the first decision links to the anchor; a full lifecycle verifies and replays | **FAIL** | pass |
| X1.4 | the reviewer's probe B: a caller's starting hash refused (control plane and owner) | **FAIL** | pass |
| X1.5 | the gateway and the witness cannot provision | pass | pass |
| X1.6 | no login role can write the provisioning log | **FAIL** | pass |
| X1.7 | the owner cannot rewrite, remove or truncate a record | **FAIL** | pass |
| X1.8 | the owner cannot change a root's k or m | **FAIL** | pass |
| X1.9 | verify_chain detects a budget that differs from its record | **FAIL** | pass |
| X1.10 | verify_chain detects a moved anchor | pass | pass |
| X1.11 | a root without a record is not written to; verify_chain refuses it | **FAIL** | pass |
| X1.12 | a re-provisioned identity gets a new record; the log verifies | **FAIL** | pass |
| X1.13 | 16 concurrent provisionings leave a contiguous linked log | **FAIL** | pass |
| X1.14 | the 4-argument function is gone; grants owner and control plane only | **FAIL** | pass |
| X1.15 | plea_ctl provision prints the anchor; provenance verifies | **FAIL** | pass |
| X2.1 | the reviewer's probe C (one attempt logged, another inserted) refused, no trace | **FAIL** | pass |
| X2.2 | the reviewer's probe D (two reservations, one RESERVE) refused, no trace | **FAIL** | pass |
| X2.3 | 14 forgeries: the right operation over the wrong operands, refused | **FAIL** | pass |
| X2.4 | the 9 genuine records they imitate apply | pass | pass |
| X2.5 | batch forgeries (partial RECOVER, incomplete RECOVER reactivating, partial REREGISTER, double accept) refused | **FAIL** | pass |
| X2.6 | 6 guard forgeries (TOKEN/RESERVE/ACCEPT_INTENT/CROSS while HELD, START while STOPPING, TERMINAL unresolved) refused | **FAIL** | pass |
| X2.7 | 7 malformed-operation records refused | **FAIL** | pass |
| X2.8 | evidence rows: the gateway's refused, the witness's bound to its decision | **FAIL** | pass |
| X2.9 | mutation sweep: a record is accepted exactly when it is the contract's decision | **FAIL** | pass |
| X2.10 | every genuine decision of the walks accepted; chains verify and replay | pass | pass |
| X3.1 | the reviewer's probe E (STOP recorded DENIED on an OPEN run) refused, as plea_local | **FAIL** | pass |
| X3.2 | the same refused to the control plane | **FAIL** | pass |
| X3.3 | an invented code refused; the contract's refusal recorded | **FAIL** | pass |
| X3.4 | a contract refusal of STOP, RECOVER, HOLD or TERMINAL written by the gateway refused | **FAIL** | pass |
| X3.5 | a witness-operation refusal written by the gateway refused (v0.7) | pass | pass |
| X3.6 | a NOOP or DUPLICATE the contract would apply refused | **FAIL** | pass |
| X3.7 | the declared limit: a contract refusal for a request never made is recorded, changes nothing | pass | pass |
| X4.1 | plea_step = the reference engine and the oracle on 768,544 pairs | **FAIL** | pass |
| X4.2 | plea_step rejects exactly the malformed operations the reference rejects (45/10) | **FAIL** | pass |
| X4.3 | the engine is the owner's: no login role can call it | **FAIL** | pass |
| | **total** | **6/35** | **35/35** |

The six that pass on v1.1 are the properties v1.1 already had, or the declared limit, which is meant to hold: the gateway and witness cannot provision (X1.5), a moved chain head is detected (X1.10), genuine records apply (X2.4, X2.10), the v0.7 witness rule (X3.5), and the limit (X3.7).

**The mutation sweep (X2.9)** is the broadest single check. Six random walks of 120 genuine decisions each run through the real write path with the right credentials, on budgets from 1 to 4. Before each genuine write, up to five operand mutations of its record are tried: another attempt, request, nonce, verdict or evidence label, another operation name, flipped RECOVER flags. Up to two payload mutations are tried as well: one row dropped from a batch, one row too many. Each is tried in a rolled-back transaction, and the database must accept a mutated record **exactly when** the reference engine says it is the contract's own decision on that state.

| | records | v1.1 | v1.2 |
|---|---|---|---|
| genuine decisions | 720 | all accepted | all accepted |
| mutated, *the contract's own decision* (e.g. RECOVER on an ACTIVE run, refused NOT_HELD whatever its flags) | 994 | all accepted | all accepted |
| mutated, *not* the contract's decision | 2,252 | **1,876 accepted**, 376 refused | **all refused** |
| refused by a v1.2 rule | | — | 1,876: kind or code 1,835; rows 41 |
| refused by an earlier rule | | 376 | 376: witness authority 249, operation-to-mode 86, operation-to-transition 38, invariants 3 |

Both runs replay the same seeded walk. v1.2's new rules refuse 1,876 records, the number v1.1 accepted. The earlier rules' tallies are identical in both runs: 249, 86, 38 and 3. The counts were compared, not each record.

---

## 6. Full regression, both isolation modes

The declared run on a clean `plea12`, every suite against the v1.2 write function (`outputs/chain_v12_official.log`):

| suite | result |
|---|---|
| **X1–X4** (v1.2) | **15 + 10 + 7 + 3 = 35/35**; 768,544 differential pairs, 0 mismatches; sweep 0 mismatches |
| U1–U2 (v1.1) | 21 + 15 = **36/36** |
| S1–S3 (v1.0) · Q1–Q2 (v0.9) · P1–P2 (v0.8) | **37/37 · 33/33 · 26/26** |
| V1–V6 / R1–R6 / H1–H5 / T1–T4 / M1–M3 | **43 / 43 / 33 / 35 / 28** |
| E1 / E2 / E3 · W1–W4 | 13 / 9 / PASS · PASS, PASS, PASS, 18/18 |
| conform_store · chaos · G02b | **34/34 · 90/90 · 200/200** |
| G01 last-slot race — **lock / serializable** | **300/300 / 300/300** (10,650 decisions each, replayed in lockstep) |

Every genuine decision of every suite passed through the database's evaluation of the contract and was found to be the contract's own. The earlier reviews' counterexamples stay refused: the v0.8 pair (`review4_repro_v1_2.json`) and the v1.0 probe (`review6/forged_audit_after_v1_2_ADAPTED.*`), each by the same rule as in v1.1.

---

## 7. The reviewer's scripts against v1.2

Run unchanged against the v1.2 bundle. The scripts look for the bundle under its v1.1 directory name. A link of that name points at the v1.2 extraction, and nothing in the scripts is altered.

| the native probe | shipped v1.1 | v1.2 |
|---|---|---|
| **A** provision, then inspect the decision log | `seq 0`, no decision, chain ok | **the same view of the decision log, by design.** The record is in the provisioning log, which the probe does not read; X1.1–X1.3 show it |
| **B** a caller's starting hash | **ACCEPTED**; verify_chain fails | **REFUSED 42883**: no 4-argument `plea_new_root` exists |
| **C** RESERVE logged for one attempt, another inserted | **ACCEPTED**; chain ok | **REFUSED 23514**: `operation ["RESERVE", "declared-aid", "declared-request"] does not produce the rows written` |
| **D** two reservations under one RESERVE | **ACCEPTED**; chain ok | **REFUSED 23514**: `operation ["RESERVE", "a1", "q1"] does not produce the rows written` |
| **E** STOP recorded DENIED on an OPEN run | **ACCEPTED**; chain ok | **REFUSED 23514**: `the contract decides ["STOP"] here as APPLIED (STOPPING), not DENIED (SYNTHETIC_REFUSAL)` |

The probe's own roots each received a record in the provisioning log, issued by `plea_control`, and the log verifies (`native_pg_v11_after_v1_2_PROVISIONS.txt`). The refused probe B left none.

`review_checks.py`, the offline script, against v1.2: every manifest entry matches, the report identity holds (the v1.1 report it compares is carried unchanged), 45 Python files compile, and 34/34 vector groups pass. Its status labels are fixed strings in the script, so they read the same whatever the source; what it measured is in the details:

- `genesis_parameter_from_caller` is **False**; it was True on v1.1.
- `provisioning_emits_decision` is False by design. The record goes to the provisioning log, not the decision log (§3.1).
- `default_initial_audit_seq` reads False only because the schema's column alignment changed. It matches a literal string with fixed spacing, and a root's sequence still starts at 0.
- `op_argument_binding_source` looks for `p_op->>1`, `p_op->>2` and `jsonb_array_length(p_attempts)` inside `plea_write`'s own text. The binding lives in `plea_step`, which `plea_write` calls, so this grep cannot see it. `attempt_id_bound_to_op_arg` reads True only through an incidental match in the evidence-row check. The evidence is the native refusals of C and D and X2.
- `refusal_source`: `accepts_denied_if_no_change` is still True, because v1.1's kind-binding line is still there. Refusals are now checked by `plea_step` (X3).
- `control_root_authority`: `removes_gateway_grant` reads False. It searches for v1.1's 4-argument GRANT text, which no longer exists. The 3-argument function is granted to the control plane only (X1.14).

I did not reword any code to satisfy a grep.

`model_counterexamples.py` gives the same output as before. It is a pure-oracle demonstration of what the forged records *would mean*, and the oracle is unchanged. What v1.2 changes is that the database no longer accepts those records.

---

## 8. Decisions stated plainly

- **A separate provisioning log, not a `NEW_ROOT` decision.** As in §3.1: the root's decision log stays exactly the contract's single-root history, so the independent oracle replays it unchanged; the anchor links the two.
- **What the record says, and what it cannot.** Everything in it is the database's own: the root, `k`, `m`, the issuing role, the contract and release strings, the database clock. I read the review's "policy/version" as the contract and release under which the budget was issued. I did not add a caller-supplied policy or ticket field, because it would be the control plane's free text inside the anchor; a deployment that wants one can add it as an operator field. The issuer is a role. Per-person attribution needs one login per operator, inheriting `plea_control`, and v1.2 does not add that.
- **The old signature is gone, not reinterpreted.** `plea_new_root(text, int, int, text)` is dropped. Keeping a 4-argument form under a new meaning, for example a policy text, would have let the reviewer's probe B *succeed* with the would-be genesis taken as a label. Dropping it makes probe B fail with "no such function" (42883), which is the truthful outcome.
- **The new checks come last.** Every v0.8–v1.1 rule in `plea_write` runs first, unchanged. Every earlier forgery test therefore still meets the rule it was written for. The new evaluation sees only what passed all of them. The Q, S and U counts are unchanged.
- **Control-plane refusals are the control plane's.** Since v0.7 a witness operation is recorded only by the witness, refused or applied. v1.2 extends that to the control plane's operations. The governor already sends every control operation through the control credential, so no legitimate path changed.
- **Two harness defects in my own new suite, found by its first run against v1.1, are preserved.** In that run the suite read the store's decision kind as the reference's enum, so every genuine apply looked like a failure. Its malformed-operation list was also mis-tested, because Python treats `True == 1`. Both were fixed, one check that passed vacuously on v1.1 because the provisioning table did not exist was tightened, and the v1.1 run repeated. All three runs are kept in `outputs/review7/`. Only the third used the declared file. The second run predates the evidence-row check of §3.4 and the refusal classification, which is reporting only.
- **A development bug, caught at once.** My first install of the engine failed on `e->>0 COLLATE "C"`: COLLATE binds tighter than `->>`. Parenthesised. Nothing ran on the faulty text.
- **Two existing tests changed, for the signature only.** S3's least-privilege and shadowing probes, and U2's ACL check, named the 4-argument signature. They now name the 3-argument one. The S3 shadowing probe also plants a temporary `provisions` table, because provisioning now writes two tables. Check counts are unchanged and the reasons are in the declaration.
- **Upgrade.** Re-running `init_authority()` on a v1.1 database adds the log, the triggers and the new function, and drops the old one. Roots provisioned before v1.2 carry no record. `plea_write` and `verify_chain` refuse them until the control plane re-provisions them. No deployment has such roots.
- **The cost, measured.** Evaluating the contract in the database is not free. In the declared run, G01 took **257.9 s in lock mode and 421.4 s serializable**, over 10,650 decisions a mode with 16 racing workers. v1.1 took 214.4 s and 338.2 s, and v1.0 took 150.2 s and 240.4 s. So v1.2 adds about 4 ms per decision over v1.1, about 8 ms serializable with retries included. That is about 10 ms per decision over v1.0 in lock mode. The PL/pgSQL engine reads the attempts as JSON several times per evaluation. A compiled extension, or an evaluation narrowed to the named operation, is where a deployment that needs throughput would look. I did not optimise it: a throughput benchmark with production pooling is still an open operational gate (§9).

---

## 9. Scope and what is unchanged

The contract, the reference engine, the independent oracle, the governor, the gate host, the witness service, evidence derivation, receipts and TLS are byte-identical to v1.1. v1.2 is a database-side change, the store's Python side of provisioning and verification, and one operator command. File hashes are in `DECLARED_BINDING.txt`.

Not claimed here: a human Gate B quickstart under 30 minutes, a design-partner staging integration, real failure injection outside this harness, and a throughput benchmark with production connection pooling. The review keeps these as a separate commercial and operational gate, and none of them can be inferred from this suite.
