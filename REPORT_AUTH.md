# PLEA gateway v0.6: execution authorisation and recovery

12 October 2026 · follows the v0.5 report · a response to the v0.4 scoped technical review · private working material, not for publication

## Summary

**Headline.** The v0.4 scoped review found that the gate host ran tools the contract had not admitted, ran them under any nonce, tool or arguments the caller supplied, returned results its signature did not cover, and left admitted work unrecoverable after a lost reply, a no-effect or a host crash. Every finding was reproduced here on v0.5 before anything was changed, then repaired, and each repair is a declared test. All 43 checks passed on the declared run, and every earlier test passed again on the new receipt and report formats, with no amendment.

| finding (review section) | reproduced on v0.5 | repair | test | result |
| --- | --- | --- | --- | --- |
| 2 HOLD or STOP accepted before dispatch, yet the tool runs | yes: APPLIED, one effect, CROSS denied | CROSS is the admission, applied before dispatch; crossed work is admitted work | R1 | **11/11 ok** |
| 3 the host does not bind the nonce to the accepted intent | yes: a genuine receipt ran under another nonce; WRONG\_BINDING only afterwards | the receipt carries the accepted nonce; the nonce is a digest of executor, tool and arguments | R2 | **8/8 ok** |
| 4 signed reports do not authenticate the result | yes: an altered result was returned and stored | the effect report's signed fields include the result's digest; the governor verifies it | R3 | **6/6 ok** |
| 5 recovery: lost reply, no-effect, host crash | yes: InProgress forever; no final outcome | outcomes stored and replayed; unfinished attempts resumed; interrupted host rows resolved as UNKNOWN | R4 | **12/12 ok** |
| 6 one-shot is per host state | yes: two hosts, two effects | the executor key is bound; same key means one state (stated) | R5 | **2/2 ok** |
| 7 evidence and decision committed separately; unsigned outer fields; two-snapshot replay | by inspection | evidence in the decision's transaction; the client reads the signed receipt; one-snapshot replay | R6 | **4/4 ok** |
| 8 the README's host command fails from the bundle root | yes: ModuleNotFoundError | module path, absolute state, clean-machine prerequisites | README | fixed |
| re-runs: H, T, M, E, W, conformance, chaos, G02b, G01 (300) on the new formats | | | | **all pass**: H 33/33, T 35/35, M 28/28, conformance 34/34, chaos 90/90, G02b 200/200, G01 300/300 |

What this does not close: the review's finding on broad local write authority (the gateway's credential can write any root in the store; narrowing it is a schema change, not a gateway change), revocation (a compromised certificate is handled by rotating the authority), resolving an UNKNOWN verdict with evidence from the integration (the host says it does not know; only the integration can), and a Gate B trial with a person.

## 1. The reproduction

`tests/r_repro.py` drove the review's schedules through the unchanged v0.5 code with real services and a tools module that appends to a file. `outputs/review_repro_v0_5.json` is its record.

| schedule | what v0.5 did |
| --- | --- |
| 2: HOLD accepted after the intent, before dispatch | HOLD APPLIED; the tool ran (1 effect); then `GovernedError: CROSS: DENIED (NOT_ACTIVE_AND_OPEN)`; the attempt CONSUMED, crossed False; the retry raised InProgress |
| 2: STOP, same schedule | STOP APPLIED; the tool ran (1 effect); `GovernedError: CROSS: DENIED (NOT_ACTIVE_AND_OPEN)`; the retry raised InProgress |
| 3: a genuine intent receipt submitted under another nonce, another tool and other arguments | the host ran it (1 effect) and signed EFFECT for nonce `different-nonce`; the witness then DENIED (WRONG_BINDING) |
| 4: the result altered beside the genuine report | the governor returned `{"charged": 999999, "label": "altered-in-transit"}` and stored it; the witness reconciled EFFECT AUTHORISED; phase EFFECT |
| 5: the reply lost after the host ran | 1 effect; `GateRefusedRun`; the retry with a healthy host raised InProgress; the attempt CONSUMED, crossed False |
| 5: a completed no-effect, retried | first NoEffect, credit 1; the retry raised InProgress |
| 5: the host killed mid-run, restarted on the same state | first GateRefusedRun; 0 effects; the retry raised InProgress: no final outcome |
| 6: one receipt to two hosts with separate state | both ran it (repeat False, False): 2 effects |

Every row matches the review's description. Finding 7 was confirmed by reading the code: `put_evidence` committed after `apply_ex`, `RemoteWitness.accept` returned the outer `kind` and `code`, and `replay_lockstep` read the log and the observation in two transactions.

## 2. The repairs

**Admission (finding 2).** In v0.4 the governor applied RECEIPT, asked the host to run, then applied CROSS. CROSS is where the contract checks that the run is ACTIVE and OPEN (5.7/4), so a HOLD or STOP accepted between the intent and the dispatch was found only after the effect. Now CROSS is applied before the dispatch. If it is DENIED for the run's state, nothing is sent and the caller gets `Held` or `Stopped`. If it is APPLIED, the attempt is admitted work: a HOLD or STOP after that does not retract it, the verdict is refused while the run is held (5.9/5), and after recovery a retry fetches the host's stored outcome. The window between the crossing and the host receiving the request is the admitted-work window; it is the window the in-process gate has had since v0.2, and it is now stated.

**Binding (finding 3).** The nonce is `nonce_for(root, attempt, executor, tool, arguments)`: a digest of the gate key that will run the action, the tool, and the canonical JSON of its arguments. The witness's ACCEPT\_INTENT receipt now carries the nonce it accepted, read from the committed state and signed. The host verifies the receipt's binding against the submitted nonce and recomputes the digest from its own key, the tool and the arguments; anything else is 403 before the one-shot claim. A request key reused with another action computes another nonce, which START refuses (5.4/2), and the governor raises `RequestKeyReused`. The witness still derives every label from the report alone.

**The outcome envelope (finding 4).** The effect report's signed fields now include `result_digest`, the digest of the result returned beside it. The governor pins the host's key, verifies the report (genuine, this root, attempt and nonce) and checks the result against the digest before storing or returning anything. A substituted result is `OutcomeInvalid`; the witness still reconciles on the genuine report, and the retry fetches the host's stored result. The stored evidence carries the digest, so an auditor can check a stored result against the witness's record.

**Recovery (finding 5).** Every terminal outcome is stored with the nonce it belongs to and replayed on a retry: a value, a no-effect (`NoEffect` again), an unknown verdict (`RuntimeError` again), without touching the host. A retry of an unfinished attempt resumes it: each step is idempotent by contract (E8), the crossing's ALREADY\_CROSSED continues, a final verdict without a stored outcome asks the host for its stored result, and the host answers an admitted attempt with the result and report it kept. A host that stops while a tool is running marks that row interrupted at its next start and answers the retry with a signed EFFECT\_REPORT claiming UNKNOWN: the witness records NOOP, the attempt stays charged, the outcome is stored, and the tool is never run again. `InProgress` is now raised only when the host reports the attempt running at that moment.

**Executor (finding 6).** The nonce binds the gate key, so a receipt cannot run at a host under another key. Two hosts under one key are one executor and must share one state file; the host's state durability is still the deployment's.

**Records (finding 7).** The witness's evidence row is inserted in the same transaction as the decision it belongs to; a crash after the audit row loses both. The witness client takes the decision kind and code from the verified receipt, never from the unsigned outer fields of the response. The replay check reads the audit log and the current observation from one REPEATABLE READ snapshot.

**The quickstart (finding 8).** The host command in the README now names the tools module by its import path from the bundle root, gives the state file an absolute path, and the README opens with the packages, roles and database a clean machine needs.

## 3. Declaration

`DECLARED_AUTH.txt`, recorded at 11:41:48 UTC, holds the sha256 of every file and the expected result of every check. The reproduction and the development smokes that preceded it are named in it. Because the receipt and report formats changed and the governor's lifecycle changed, the whole chain was declared and run again, after R, on a fresh database (`plea6`), created with the README's commands. The v0.5 outputs are under `outputs/v0_5/`.

## 4. Results

All six groups passed as declared, in 13.8 s, with real services: a witness service, a gate host under the test gate key, a second host under another key, and a tools module that appends to a file so executions are counted across processes.

### 4.1 R1: admission

| check | result |
| --- | --- |
| HOLD accepted before the crossing: the call is refused (Held) | ok |
| HOLD before the crossing: the tool did not run; the attempt is CONSUMED and not crossed | ok |
| after recovery the retry runs it once | ok |
| replay lockstep | ok |
| STOP accepted before the crossing: the call is refused (Stopped) | ok |
| STOP before the crossing: the tool did not run; the attempt is CONSUMED and not crossed | ok |
| replay lockstep | ok |
| HOLD accepted after the crossing: the verdict is refused while held (Held) | ok |
| admitted work ran once; the attempt is crossed, not yet reconciled | ok |
| after recovery the retry returns the stored outcome without a second execution | ok |
| replay lockstep | ok |

With a HOLD or a STOP accepted after the witness's acceptance of the intent and before the crossing, CROSS was DENIED, nothing was sent to the host, the tool did not run, and the attempt stayed CONSUMED and not crossed; after RECOVER the retry ran it once. With a HOLD accepted after the crossing and before the host received the request, the tool ran once as admitted work, the witness refused the verdict while held, and after RECOVER the retry returned the host's stored outcome with no second execution. The review's schedule (section 2 of the review) now ends with no effect.

### 4.2 R2: binding

| check | result |
| --- | --- |
| the witness's intent receipt carries the nonce it accepted | ok |
| a genuine receipt under another nonce (403) | ok |
| the bound nonce with another tool (403) | ok |
| the bound nonce with other arguments (403) | ok |
| the bound action at a host under another key (403) | ok |
| nothing ran | ok |
| the bound action at the bound host runs once | ok |
| the request key reused with other arguments (RequestKeyReused) | ok |

The witness's intent receipt carried the nonce it accepted. The host refused a genuine receipt under another nonce, the bound nonce with another tool, the bound nonce with other arguments, and the bound action at a host under another key, each with 403 and no execution; the bound action at the bound host ran once. A request key reused with other arguments raised `RequestKeyReused`. The review's schedule (section 3) now ends with a refusal before any tool is invoked.

### 4.3 R3: the outcome envelope

| check | result |
| --- | --- |
| a result altered beside the genuine report is refused (OutcomeInvalid) | ok |
| nothing stored; the tool ran once | ok |
| the retry fetches the signed result without a second execution | ok |
| the stored evidence's digest matches the stored result | ok |
| a report with an altered claim is refused (OutcomeInvalid) | ok |
| replay lockstep | ok |

A result altered beside the host's genuine report was refused and nothing was stored; the tool had run once, the witness reconciled on the genuine report, and the retry fetched the signed result without a second execution. The stored evidence's `result_digest` equalled the digest of the stored value. A report with an altered claim was refused. The review's schedule (section 4) now ends with `OutcomeInvalid` and the genuine result on retry.

### 4.4 R4: recovery

| check | result |
| --- | --- |
| the reply is lost after the host ran (ConnectionError) | ok |
| lost reply: the retry returns the result without a second execution | ok |
| a completed no-effect replays as NoEffect; credit 1; nothing ran twice | ok |
| the caller dies after the intent was accepted, before the crossing (ConnectionError) | ok |
| the retry resumes and runs once | ok |
| the caller dies after the verdict, before storing (ConnectionError) | ok |
| the retry stores the outcome without a second execution | ok |
| the host restarts with the attempt marked interrupted | ok |
| after the restart the retry gets a signed UNKNOWN verdict (RuntimeError) | ok |
| no second execution; the attempt stays charged (CONSUMED, crossed); the UNKNOWN verdict is recorded; the outcome is stored | ok |
| the outcome replays as unknown without contacting the host (RuntimeError) | ok |
| replay lockstep | ok |

Each of the review's recovery cases (section 5) ended in at most one execution and a stored, replayable outcome: the lost reply, the completed no-effect, the caller dying before the crossing and after the verdict, and the host dying mid-run. For the last, the host restarted with the row marked interrupted, the retry received a signed UNKNOWN verdict, the witness recorded NOOP, the attempt stayed charged and crossed, and a further retry replayed the stored outcome without contacting the host.

### 4.5 R5: the executor

| check | result |
| --- | --- |
| one receipt at a host under another key (403) | ok |
| the bound host runs it once; a second host under the same key with separate state runs it again: a stated limit | ok |

One receipt at a host under another key was refused. A second host under the same key with its own state ran the attempt again: an executor is a key, and the host's state is per process unless the deployment shares it. The review's section 6 is closed for distinct keys and stated for a shared one.

### 4.6 R6: records

| check | result |
| --- | --- |
| a crash after the audit row loses the decision and the evidence together | ok |
| the verdict then commits with its evidence, at the same sequence number | ok |
| the client takes the decision from the signed receipt, not the outer fields | ok |
| replay lockstep | ok |

A crash point after the audit row, in a witness started with chaos injection, lost the decision and the evidence together; the verdict then committed with its evidence at the same sequence number. A proxy that rewrote the response's outer decision to DENIED did not change what the client reported, because the client reads the signed receipt.

### 4.7 Re-runs

Declared with R and run after it on the fresh database. All passed; no amendment.

| test | result | time |
| --- | --- | --- |
| H1–H5 gate host (H2 and H5 updated for the binding) | 33/33 | 15.9 s |
| T1–T4 mutual TLS | 35/35 | 15.7 s |
| M1–M3 MCP | 28/28 | 7.0 s |
| E1 release evidence | 8/8, lockstep | 1.9 s |
| E2 reconcile evidence | 8/8, lockstep | 2.2 s |
| E3 lifecycle evidence, 6 roots (part B expects VerdictRefused) | PASS | 11.1 s |
| W1 authority boundary | PASS | 4.2 s |
| W2 receipts | PASS, lockstep | 0.9 s |
| W3 service lockstep | PASS | 58.7 s |
| W4 service crash, 18 points | 18/18 | 20.5 s |
| conformance, 34 vector groups | 34/34 | 34.0 s |
| chaos | 90/90 | 71.4 s |
| G02b | 200/200 | 92.4 s |
| G01 lock, 16 workers | 300/300 | 185.4 s |

The v0.5 outputs are under `outputs/v0_5/`.

## 5. What this shows, and what it does not

**Shows.**

- A HOLD or STOP accepted before the crossing stops the tool from running; one accepted after it is admitted work, recovered without a second execution.
- Nothing runs at a host under a nonce the witness did not accept, with another tool or other arguments, or at another executor.
- A result the host's signature does not cover is refused and never stored; the stored evidence names the digest of the stored result.
- A lost reply, a caller that dies before or after the verdict, a completed no-effect, and a host that dies mid-run each end in one execution at most and a stored, replayable outcome.
- The witness's evidence cannot exist without its decision, and the client cannot be told a decision the witness did not sign.

**Does not show.**

- The local credential's reach: the gateway's role can still write every root in the store. The review's "broad local write authority" stands.
- What an UNKNOWN verdict was. The host that was interrupted does not know whether the tool's effect happened; the gateway records that honestly and leaves resolution to the integration's own evidence.
- A real agent framework, a person at the quickstart, or production throughput: the next three items.

## 6. Next

1. **The design-partner framework integration**, now that the execution boundary is specified.
2. **Gate B with a person**, on the v0.6 README.
3. **A throughput measurement** with connection pooling.

## 7. Files and hashes

| file | sha256 (first 16 hex digits) | role |
| --- | --- | --- |
| `plea_gateway/__init__.py` | `1313ade4d3834b0f…` | package |
| `plea_gateway/binding.py` | `6c118725a2157388…` | the nonce as a digest of executor, tool and arguments; result digests (v0.6) |
| `plea_gateway/evidence.py` | `7defee95701e7c6e…` | reports; result_digest in the signed fields; the outcome envelope check (v0.6) |
| `plea_gateway/faults.py` | `67c9ac8f872d31b5…` | crash points |
| `plea_gateway/gate_host.py` | `edb84fc16a1d87e8…` | the gate host: binding checks, interrupted rows, signed result digest (v0.6) |
| `plea_gateway/governor.py` | `c04debeb8d3d6765…` | CROSS before dispatch, resumable lifecycle, stored outcomes, verdict handling (v0.6) |
| `plea_gateway/plea_budget_ref.py` | `a367a4bbc2ca21b4…` | the verified reference, unchanged |
| `plea_gateway/receipts.py` | `2c464e0a9f5d97a5…` | receipts; the binding field (v0.6) |
| `plea_gateway/store.py` | `9bd820c0b6610045…` | evidence in the decision's transaction; one-snapshot audit (v0.6) |
| `plea_gateway/tls.py` | `e08e322d53539bd9…` | mutual TLS (v0.5) |
| `plea_gateway/witness.py` | `748966e889e87d9c…` | witnesses: binding in receipts; the client reads signed fields only (v0.6) |
| `plea_gateway/witness_service.py` | `7a73e388a5c19035…` | the witness service: binding, evidence with the decision (v0.6) |
| `mcp/demo_tools.py` | `7f672232e9988fb1…` | demonstration tools |
| `mcp/plea_ctl.py` | `a8974537035ea014…` | operator control |
| `mcp/plea_mcp.py` | `d8c45904f9e7fd4a…` | governed MCP server; the new refusals named |
| `mcp/vanilla_mcp.py` | `3b574ba659f905a8…` | ungoverned control case |
| `tests/apply_once.py` | `18a47ba1a8fc9379…` | earlier test, unchanged |
| `tests/budget_oracle.py` | `6b7646b7e2f4824f…` | earlier test, unchanged |
| `tests/chaos.py` | `22932e82a196e76d…` | earlier test, unchanged |
| `tests/common.py` | `5578fe1ca78332ce…` | fixtures; bound nonces; one-snapshot replay |
| `tests/conform_store.py` | `22b3d5a1e0198f0d…` | earlier test, unchanged |
| `tests/e1_release_evidence.py` | `1ecc76ee74aa2804…` | earlier test, unchanged |
| `tests/e2_reconcile_evidence.py` | `afc43394784e4875…` | earlier test, unchanged |
| `tests/e3_lifecycle_evidence.py` | `5c9cfba268546e02…` | E3, part B expects VerdictRefused |
| `tests/g01_race.py` | `34b00e079e0a055a…` | earlier test, unchanged |
| `tests/g02b.py` | `4640e08d322857b3…` | earlier test, unchanged |
| `tests/h_tests.py` | `2b6ea3092c983e27…` | H1–H5, updated for the binding |
| `tests/mcp_tests.py` | `fede07f8300dfd04…` | earlier test, unchanged |
| `tests/r_repro.py` | `bffd16d842cbc51c…` | the review's findings reproduced on v0.5 |
| `tests/r_tests.py` | `084c29ae0f331f02…` | R1–R6 |
| `tests/review_tools.py` | `c4d6e915250275a9…` | tools for R and the reproduction |
| `tests/t_tests.py` | `93fc024b40cdbea3…` | T1–T4, updated for the binding |
| `tests/vectors.py` | `ee0147c353c331cf…` | the 34 vector groups, copied unchanged from the v3.1 oracle bundle |
| `tests/w1_authority.py` | `061df2240a9d1e33…` | earlier test, unchanged |
| `tests/w2_receipts.py` | `ae80070baa9eb532…` | earlier test, unchanged |
| `tests/w3_service_lockstep.py` | `d5359d1dbb7ca14d…` | earlier test, unchanged |
| `tests/w4_service_crash.py` | `01914f2ce5338071…` | earlier test, unchanged |
| `../budget_v3_1/contract/CONTRACT_V3_1.md` | `4200c1ce4931c9ed…` | the contract, frozen |

All recorded in `DECLARED_AUTH.txt` at 11:41:48 UTC, before any declared test ran. `SHA256SUMS` in the bundle lists every file.
