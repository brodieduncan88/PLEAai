# PLEA gateway v0.7: admission enforced at the host, and one owner per host state

12 October 2026 · follows the v0.6 report · a response to the v0.6 technical review · private working material, not for publication

## Summary

**Headline.** The v0.6 review's central finding was that the gate host trusted a genuine intent receipt as permission to run, while the admission decision, CROSS, lived in the caller's own store: an authorised caller that skipped the governor's check could run a tool after a HOLD or STOP. That is closed. The crossing is now applied by the witness and receipted, the host runs nothing without that receipt, and the local credential cannot set `crossed`. The review's second finding, that a second host on the same state file marked a live host's work interrupted, is closed by a lease: one owner per state file, and a verdict learned late replaces an interim UNKNOWN. The four smaller findings are repaired. Every finding was reproduced on v0.6 before anything was changed. All 43 checks passed on the declared run, and every earlier test passed again, with no amendment.

| finding (review) | reproduced on v0.6 | repair | test | result |
| --- | --- | --- | --- | --- |
| 1 the host runs on a genuine intent receipt without proof of admission | yes: after HOLD and after STOP, CROSS denied, the tool ran | the witness applies CROSS and signs the admission; the host requires it; `crossed` is witness-only in the store | V1 | **21/21 ok** |
| 2 two hosts on one state file: the second marks the first's running work interrupted; the governor caches the UNKNOWN | yes: UNKNOWN cached while the store already said EFFECT | one owner per state file (lease); a late verdict replaces the UNKNOWN; UNKNOWN is re-queried, not final | V2 | **9/9 ok** |
| 3a an UNKNOWN is cached although the witness refused its reconciliation | yes | nothing stored unless the witness recorded NOOP; Held or Stopped raised | V3 | **5/5 ok** |
| 3b an older signed response accepted for a later submission | yes: the client reported the first decision for the second submission | RELEASE and RECONCILE receipts bind the digest of the evidence submitted | V4 | **4/4 ok** |
| 3c a client with TLS settings accepts an http:// URL | yes | both clients refuse the configuration before any request | V5 | **2/2 ok** |
| 3d the chain verifier reads two moments and reports false corruption | yes: 72 false failures in 93 checks under appends | one snapshot | V6 | **2/2 ok** |
| re-runs: R, H, T, M, E, W, conformance, chaos, G02b, G01 (300) | | | | **all pass**: R 43/43, H 33/33, T 35/35, M 28/28, conformance 34/34, chaos 90/90, G02b 200/200, G01 300/300 |

What this does not close: the review's remaining point on the local credential's reach beyond `crossed` (it can still write the other local facts of every root in the store), resolution of an UNKNOWN that the host never learns more about, the design-partner integration, and Gate B with a person. The review's further requests, a clearer index of historical outputs and the TLS quickstart, are addressed in the bundle (`outputs/INDEX.md`; the quickstart was run from a clean extraction as part of the verification).

## 1. The reproduction

`tests/v_repro.py` drove the review's schedules through the unchanged v0.6 code with real services. `outputs/review2_repro_v0_6.json` is its record.

| schedule | what v0.6 did |
| --- | --- |
| 1: HOLD accepted after the intent; CROSS DENIED (NOT_ACTIVE_AND_OPEN); a direct /run at the host with the genuine intent receipt | the host ran: 1 effect |
| 1: STOP accepted after the intent; CROSS DENIED (NOT_ACTIVE_AND_OPEN); a direct /run at the host with the genuine intent receipt | the host ran: 1 effect |
| 2: host A running a slow tool; host B started on the same state file | B answered `RuntimeError: tool outcome unknown at th…`; A completed (`{"charged": 1, "order": "v2"}`), 1 effect; the host's row then read ran with claim EFFECT; the governor's replay still raised `RuntimeError: tool outcome unk…` and its stored outcome was unknown while the store's phase was EFFECT |
| 3a: a failing tool with HOLD accepted after the crossing | the witness DENIED (WITNESS_HELD) the reconciliation, the governor raised RuntimeError and still stored outcome unknown |
| 3b: a proxy replaying the first RECONCILE receipt for the second submission | the client reported DENIED NONE (same receipt) while the store had moved to EFFECT |
| 3c: TLS settings with an http:// URL | both clients constructed and used the plain URL (`http://127.0.0.1:8940`) |
| 3d: verify_chain while another connection appends | 72 false failures in 93 checks (`root head does not match the log`); the quiescent check passed |

Every row matches the review's description.

## 2. The repairs

**Admission at the host (finding 1).** In v0.6 the governor applied CROSS in its own store before dispatch, which closed the ordinary path but not the direct one: the host could not tell whether the crossing had happened, because nothing attested it. Now CROSS is one of the witnessed operations. The governor applies RECEIPT locally, asks the witness service to apply CROSS, and receives a signed receipt whose binding is the attempt's nonce when the crossing was recorded (APPLIED, or DENIED with ALREADY\_CROSSED on a resume) and nothing otherwise. The host verifies that receipt, the admission, against its pinned witness keys, for this attempt and nonce, before its one-shot claim; a missing, forged, denied, foreign or replayed admission is 403 and nothing runs. The store's authority triggers reserve CROSS and the `crossed` column to the witness role, so the local credential can neither apply the crossing nor write the fact. The contract's check that the run is ACTIVE and OPEN (5.7/4) therefore happens under the witness's credential, and a HOLD or STOP accepted before the crossing leaves no admission to present, whoever asks.

**One owner per host state (finding 2).** The state file records its owner and a heartbeat. A host takes the file over at start only if the owner's heartbeat is older than the lease (`--lease`, default 10 s) and exits with code 3 otherwise. The owner heartbeats every quarter lease; a host that finds its heartbeat no longer accepted has lost the lease, refuses new work (503), and may still record work it was running. On a takeover the rows still running are marked interrupted and answered with a signed UNKNOWN, as in v0.6, but if the stalled host completes the tool after all its EFFECT or NO\_EFFECT report replaces the UNKNOWN one, which is kept as `prior_report`. On the governor's side an UNKNOWN outcome is no longer final: a retry asks the host again, and a verdict the host has learned since is reconciled (the contract moves CONSUMED to EFFECT or NO\_EFFECT, 5.9/7) and stored over the unknown.

**UNKNOWN while held (finding 3a).** The governor stores an unknown outcome only when the witness recorded NOOP for it. A DENIED reconciliation on a held or stopped run raises `Held` or `Stopped` with nothing stored, and the retry after recovery asks the host again.

**Receipt replay (finding 3b).** A RELEASE or RECONCILE receipt now binds the digest of the evidence submitted, whatever the witness decided, and the client refuses a receipt whose binding is not the digest of what it sent. A replayed receipt for an earlier submission is therefore `ReceiptInvalid`.

**TLS configuration (finding 3c).** `RemoteWitness` and `GateHostClient` refuse an http:// URL when TLS settings are supplied.

**Audit verification (finding 3d).** `verify_chain` reads the root's head and the log in one REPEATABLE READ snapshot.

## 3. Declaration

`DECLARED_ADMISSION.txt`, recorded at 13:23:00 UTC, holds the sha256 of every file and the expected result of every check. The reproduction and the development smokes that preceded it are named in it. Because the crossing moved to the witness, every test that drove a lifecycle by hand was updated to obtain the admission (H, T, R) and W1 moved CROSS from the local operations to the witnessed ones; those updates are listed in the declaration. The whole chain was run again on the same database after V.

## 4. Results

All six groups passed as declared, in 16.4 s, with real services: a witness service and a gate host under the test gate key; for V2 two hosts on one state file; for V4 a replaying proxy; for V6 a concurrent appender.

### 4.1 V1: admission at the host

| check | result |
| --- | --- |
| HOLD: the witness's CROSS is DENIED and its receipt binds nothing | ok |
| HOLD: /run with the genuine intent receipt and no admission (403) | ok |
| HOLD: the DENIED crossing as admission (403) | ok |
| HOLD: a forged admission (unknown key) (403) | ok |
| HOLD: another attempt's admission (403) | ok |
| HOLD: the local credential cannot apply CROSS (AuthorityError) | ok |
| HOLD: the local credential cannot set crossed by SQL | ok |
| HOLD: nothing ran; a1 is CONSUMED and not crossed | ok |
| after recovery the witness records the crossing and the admission runs the tool once | ok |
| a resume presents DENIED/ALREADY_CROSSED and is answered with the stored result | ok |
| the earlier admission replayed for another nonce (403) | ok |
| replay lockstep | ok |
| STOP: the witness's CROSS is DENIED and its receipt binds nothing | ok |
| STOP: /run with the genuine intent receipt and no admission (403) | ok |
| STOP: the DENIED crossing as admission (403) | ok |
| STOP: a forged admission (unknown key) (403) | ok |
| STOP: another attempt's admission (403) | ok |
| STOP: the local credential cannot apply CROSS (AuthorityError) | ok |
| STOP: the local credential cannot set crossed by SQL | ok |
| STOP: nothing ran; a1 is CONSUMED and not crossed | ok |
| replay lockstep | ok |

With a HOLD or a STOP accepted after the witness's acceptance of the intent, the witness's CROSS was DENIED (not active and open) and its receipt bound nothing. A direct request to the host with the genuine intent receipt and no admission, with that denied crossing as the admission, with a forged admission, and with another attempt's admission were each refused with 403; the local credential could neither apply CROSS nor set `crossed` by SQL; nothing ran. After recovery from the HOLD the witness recorded the crossing and its receipt ran the tool once; a resume presented DENIED with ALREADY\_CROSSED, still bound to the nonce, and was answered with the stored result; that admission replayed for another nonce was refused. The review's schedule (section 1 of the review) now ends with no effect, whoever asks.

### 4.2 V2: one owner per host state

| check | result |
| --- | --- |
| a second host on the same state file refuses to start while the first holds a live lease | ok |
| the first host keeps serving | ok |
| after the first host's lease expires the second takes over and marks the running row interrupted | ok |
| the retry at the second host gets a signed UNKNOWN verdict (RuntimeError) | ok |
| the frozen host completes the tool after all and records EFFECT over the UNKNOWN | ok |
| the governor's retry resolves the attempt to EFFECT with one execution | ok |
| the host that lost its lease refuses new work (Exception) | ok |
| and reports it | ok |
| replay lockstep | ok |

A second host started on the first host's state file exited with code 3 while the first held a live lease, and the first kept serving. The first host was then frozen (SIGSTOP) past its lease: the second took the file over, marked the running row interrupted, and answered the retry with a signed UNKNOWN. When the first host was resumed it completed the tool, one effect in all, and its EFFECT report replaced the UNKNOWN one; the governor's next retry re-queried the host, reconciled EFFECT and stored the value. The first host, having lost its lease, refused new work and reported it. The review's schedule (section 2) now ends with one execution and a resolved verdict.

### 4.3 V3: UNKNOWN while held

| check | result |
| --- | --- |
| a tool that fails while the run is held: the governor raises Held (Held) | ok |
| nothing is stored; the witness refused the reconciliation | ok |
| after recovery the retry asks the host again and gets the UNKNOWN verdict (RuntimeError) | ok |
| the witness records NOOP once; the outcome is stored as unknown | ok |
| replay lockstep | ok |

### 4.4 V4: receipt replay

| check | result |
| --- | --- |
| a receipt binds the evidence submitted (none here) | ok |
| the earlier receipt replayed for a later submission is refused by the client (ReceiptInvalid) | ok |
| the genuine later receipt binds the evidence | ok |
| replay lockstep | ok |

### 4.5 V5: TLS configuration

| check | result |
| --- | --- |
| a witness client with TLS settings and an http:// URL (ValueError) | ok |
| a host client with TLS settings and an http:// URL (ValueError) | ok |

### 4.6 V6: audit verification under concurrent appends

| check | result |
| --- | --- |
| verify_chain under concurrent appends: 154 verifications, 0 false failures | ok |
| the final quiescent check passes | ok |

154 verifications ran while another connection appended continuously, with 0 false failures; on v0.6 the same schedule gave 72 false failures in 93.

### 4.7 Re-runs

Declared with V and run after it on the same database. All passed; no amendment.

| test | result | time |
| --- | --- | --- |
| R1–R6 execution authorisation and recovery (admissions added) | 43/43 | 14.8 s |
| H1–H5 gate host (admissions added) | 33/33 | 15.8 s |
| T1–T4 mutual TLS (admissions added) | 35/35 | 15.1 s |
| M1–M3 MCP | 28/28 | 7.1 s |
| E1 release evidence | 8/8, lockstep | 2.0 s |
| E2 reconcile evidence | 8/8, lockstep | 2.0 s |
| E3 lifecycle evidence, 6 roots | PASS | 11.2 s |
| W1 authority boundary (CROSS witnessed; raw `crossed` refused) | 5 refused acceptances, 16 refused raw statements, 13 local operations | 4.6 s |
| W2 receipts | PASS, lockstep | 0.9 s |
| W3 service lockstep | PASS | 55.9 s |
| W4 service crash, 18 points | 18/18 | 22.4 s |
| conformance, 34 vector groups | 34/34 | 32.6 s |
| chaos | 90/90 | 63.9 s |
| G02b | 200/200 | 82.6 s |
| G01 lock, 16 workers | 300/300 | 168.0 s |

The v0.6 outputs are under `outputs/v0_6/`; `outputs/INDEX.md` names every earlier run.

## 5. What this shows, and what it does not

**Shows.**

- Nothing runs at the host without the witness's signed record of the crossing for exactly this attempt and nonce: not for the governor, not for a caller that skips it, not for the holder of the local database credential. After a HOLD or STOP the witness denies the crossing, so there is nothing to present.
- A second host cannot disturb a live host's work: it does not start. When a host has genuinely stalled, the takeover is recorded, the interim verdict is honest, and the better verdict replaces it when the stalled host finishes.
- An UNKNOWN is never cached against the witness's refusal, a replayed receipt is caught at the client, a TLS client cannot be pointed at a plain port, and the chain verifier no longer reports false corruption under load.

**Does not show.**

- The local credential's reach beyond the crossing. The gateway's role can still write every root's reservations, tokens, starts and control state. The accounting of record is the witness's, and what the host will run is now the witness's word; narrowing the rest is a schema change.
- An UNKNOWN that stays unknown. If the host never learns more, the attempt stays charged and the integration's own evidence is the only way to resolve it.
- A real framework integration, a person at the quickstart, or production throughput.

## 6. Next

1. **Gate B with a person**, on the v0.7 README.
2. **The design-partner framework integration** in staging, measuring installation effort, false denials, retry behaviour and latency.
3. **Narrowing the local credential** per root, and a throughput measurement with connection pooling.

## 7. Files and hashes

| file | sha256 (first 16 hex digits) | role |
| --- | --- | --- |
| `plea_gateway/__init__.py` | `1313ade4d3834b0f…` | package |
| `plea_gateway/binding.py` | `e7893edad3603b20…` | nonces, result and evidence digests |
| `plea_gateway/evidence.py` | `7defee95701e7c6e…` | reports and the outcome envelope |
| `plea_gateway/faults.py` | `67c9ac8f872d31b5…` | crash points |
| `plea_gateway/gate_host.py` | `3c55b1e7e8a5209d…` | the gate host: admission required; state ownership (v0.7) |
| `plea_gateway/governor.py` | `d61c600bdcdef9c5…` | the crossing through the witness; UNKNOWN re-queried (v0.7) |
| `plea_gateway/plea_budget_ref.py` | `a367a4bbc2ca21b4…` | the verified reference, unchanged |
| `plea_gateway/receipts.py` | `be23f1182d211039…` | receipts; verify_admission (v0.7) |
| `plea_gateway/store.py` | `932dbba5ebec2b07…` | CROSS and crossed reserved to the witness; one-snapshot verify_chain (v0.7) |
| `plea_gateway/tls.py` | `e08e322d53539bd9…` | mutual TLS |
| `plea_gateway/witness.py` | `f5c8d64d85efd3f9…` | witnesses: cross(); evidence-bound receipts; TLS URL check (v0.7) |
| `plea_gateway/witness_service.py` | `92ea90044d14fe21…` | the witness service: CROSS witnessed (v0.7) |
| `mcp/demo_tools.py` | `7f672232e9988fb1…` | demonstration tools |
| `mcp/plea_ctl.py` | `a8974537035ea014…` | operator control |
| `mcp/plea_mcp.py` | `d8c45904f9e7fd4a…` | governed MCP server |
| `mcp/vanilla_mcp.py` | `3b574ba659f905a8…` | ungoverned control case |
| `tests/apply_once.py` | `18a47ba1a8fc9379…` | earlier test, unchanged |
| `tests/budget_oracle.py` | `6b7646b7e2f4824f…` | earlier test, unchanged |
| `tests/chaos.py` | `22932e82a196e76d…` | earlier test, unchanged |
| `tests/common.py` | `22185e8b31e81bdd…` | fixtures: admitted(), host lease, CROSS routed to the witness |
| `tests/conform_store.py` | `22b3d5a1e0198f0d…` | earlier test, unchanged |
| `tests/e1_release_evidence.py` | `1ecc76ee74aa2804…` | earlier test, unchanged |
| `tests/e2_reconcile_evidence.py` | `afc43394784e4875…` | earlier test, unchanged |
| `tests/e3_lifecycle_evidence.py` | `5c9cfba268546e02…` | E3 |
| `tests/g01_race.py` | `34b00e079e0a055a…` | earlier test, unchanged |
| `tests/g02b.py` | `4640e08d322857b3…` | earlier test, unchanged |
| `tests/h_tests.py` | `b4f4159d654399d7…` | H1–H5, admissions added |
| `tests/mcp_tests.py` | `fede07f8300dfd04…` | earlier test, unchanged |
| `tests/r_repro.py` | `bffd16d842cbc51c…` | the v0.4 review's findings reproduced on v0.5 |
| `tests/r_tests.py` | `3f104113df34a3ae…` | R1–R6, admissions added |
| `tests/review_tools.py` | `491eeb6d02091ed6…` | tools for R, V and the reproductions |
| `tests/t_tests.py` | `830ee4c0faa30525…` | T1–T4, admissions added |
| `tests/v_repro.py` | `24ea5ab0c1f58f31…` | the v0.6 review's findings reproduced on v0.6 |
| `tests/v_tests.py` | `a80a84a62aedc1be…` | V1–V6 |
| `tests/vectors.py` | `ee0147c353c331cf…` | the 34 vector groups, copied unchanged from the v3.1 oracle bundle |
| `tests/w1_authority.py` | `2b66b8764356c3a8…` | W1, CROSS witnessed |
| `tests/w2_receipts.py` | `4ce148a65f878570…` | W2, reads the decision from the pair |
| `tests/w3_service_lockstep.py` | `d5359d1dbb7ca14d…` | earlier test, unchanged |
| `tests/w4_service_crash.py` | `7b6a1bab28ccd956…` | W4, reads the decision from the pair |
| `../budget_v3_1/contract/CONTRACT_V3_1.md` | `4200c1ce4931c9ed…` | the contract, frozen |

All recorded in `DECLARED_ADMISSION.txt` at 13:23:00 UTC, before any declared test ran. `SHA256SUMS` in the bundle lists every file.
