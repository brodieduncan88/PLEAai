# PLEA gateway v0.2: evidence the witness verifies (G03)

12 October 2026 · follows the v0.1 report · private working material, not for publication

## Summary

**Headline.** The caller can no longer tell the witness what to believe. A release is accepted only on a fence report, and a verdict only on an effect report, each signed by the gate's key and bound to the attempt, and the witness derives the contract's label itself. The part 1 attack, a forged NO\_EFFECT minting replacement credit, now fails at the signature. E1, E2 and E3 passed exactly as declared: 29 cases, every derivation as expected, and the credit accounting end to end.

| check | declared | result |
| --- | --- | --- |
| E1 release evidence: 7 report cases, a supplied label, a replay, 4 in-process derivations | every case as declared | as declared, 14/14 |
| E2 reconcile evidence: 7 report cases, a supplied label, a genuine UNKNOWN | every case as declared; credit exactly 1 | as declared, 9/9; credit 1 |
| E3 lifecycle over HTTP with the governor as gate, 4 roots; 2 roots with an unpinned gate key | 4 ran / 1 denied / credit 1 per pinned root; 3 ran / 2 denied / credit 0 per unpinned root | as declared, 6/6 roots |
| W1–W4, conformance, chaos, G02b, G01 (300 rounds) re-run | all pass | all pass as declared |

What this closes from the plan: G03, authenticated release reports and verdicts, to the extent a single gate key held by the governor can close it. What it does not close: in a deployment the gate key belongs to the sandbox host, not to the caller's process; here they are the same process. Key rotation, revocation and a second witness are still open.

## 1. What was built

**Evidence (`evidence.py`).** Two report kinds, each an Ed25519 signature by the gate over five fields:

- `FENCE_REPORT` (root, attempt, claim FENCED\_NO\_START): the sandbox was fenced and no START\_INTENT was committed under the token.
- `EFFECT_REPORT` (root, attempt, nonce, claim EFFECT | NO\_EFFECT | UNKNOWN): the gate's verdict for the intent that ran under that nonce.

**Derivation.** The witness derives the contract's label from the report and nothing else:

| report | derived |
| --- | --- |
| absent, malformed, wrong kind, wrong claim, unknown signer, or bad signature | NONE |
| genuine, but for another root or attempt (or, for a verdict, another nonce) | WRONG\_BINDING |
| genuine and bound | BOUND\_FENCE / AUTHORISED |

The verdict is taken from the report when it is genuine, and is UNKNOWN otherwise. The contract then decides: 5.8 rule 6 denies a release unless BOUND\_FENCE; 5.9 rule 4 denies a verdict unless AUTHORISED (D8). The witness never clamps and never guesses.

**The service.** `POST /accept` takes `['RELEASE', a]` or `['RECONCILE', a]` with an `evidence` object. An operation that carries a label is refused with 400. The service pins one or more gate public keys (`--gate-key`), records the report it verified and the label it derived in an `evidence` table beside the audit row, and signs its receipt over the labelled operation it applied, so the receipt attests the derivation.

**The governor as gate.** The governor holds a `GateSigner`. After the governed call it signs an effect report bound to the root, the attempt and the nonce that ran: EFFECT on return, NO\_EFFECT when the call raises `NoEffect`, UNKNOWN on any other exception. `release(aid)` signs a fence report. No label is ever sent.

**The in-process witness** derives labels the same way, with the gate keys given at construction.

## 2. Declaration

`DECLARED_EVIDENCE.txt`, recorded at 08:21:35 UTC, holds the sha256 of every file and the expected result of every test. One development smoke preceded it and is named in it. The v0.1 outputs are kept under `outputs/v0_1/`.

## 3. Results

### 3.1 E1: release evidence

Service, on a root with eight accepted reservations, 1.9 s:

| case | decision | derived label |
| --- | --- | --- |
| a1: genuine report for a1 | APPLIED | BOUND_FENCE |
| a2: no evidence | DENIED | NONE |
| a3: signed by an unpinned key | DENIED | NONE |
| a4: genuine report for another attempt | DENIED | WRONG_BINDING |
| a5: genuine report for another root | DENIED | WRONG_BINDING |
| a6: claim edited on a genuine report | DENIED | NONE |
| a7: genuine report claiming STARTED | DENIED | NONE |
| a8: label supplied by the caller | refused by the service (400), state unchanged: True | — |
| a1: a1's genuine report again after release | DUPLICATE | — |

Afterwards a1 was RELEASED and a2 to a8 were still RESERVED: live *R* 7. 7 evidence rows were recorded, one per derivation. The in-process witness derived the same labels on its own root: a1 APPLIED BOUND_FENCE, a2 DENIED NONE, a3 DENIED NONE, a4 DENIED WRONG_BINDING. Replay lockstep and the chain held.

### 3.2 E2: reconcile evidence

Service, on a root with *k* = 8, *m* = 2 and eight consumed attempts under nonces n1 to n8, 2.1 s:

| case | decision | derived (verdict, label) | credit after |
| --- | --- | --- | --- |
| a1: genuine EFFECT bound to n1 | APPLIED | ('EFFECT', 'AUTHORISED') | 0 |
| a2: genuine NO_EFFECT bound to n2 | APPLIED | ('NO_EFFECT', 'AUTHORISED') | 1 |
| a3: no evidence | DENIED | ('UNKNOWN', 'NONE') | 1 |
| a4: forged NO_EFFECT by an unpinned key | DENIED | ('UNKNOWN', 'NONE') | 1 |
| a5: genuine NO_EFFECT, wrong nonce | DENIED | ('NO_EFFECT', 'WRONG_BINDING') | 1 |
| a6: genuine report for a1 used on a6 | DENIED | ('NO_EFFECT', 'WRONG_BINDING') | 1 |
| a7: claim edited on a genuine report | DENIED | ('UNKNOWN', 'NONE') | 1 |
| a8: label supplied by the caller | refused by the service (400), state unchanged: True | — | — |
| a8: genuine UNKNOWN bound to n8 | NOOP | a8 stays CONSUMED | — |

Final phases: a1 EFFECT, a2 NO\_EFFECT, a3 to a8 CONSUMED. Credit 1 and *N* 1: the one genuine NO\_EFFECT, and nothing from the forged one. Replay lockstep and the chain held.

### 3.3 E3: the lifecycle with evidence

Over HTTP, with the governor holding the pinned gate key, 9.5 s.

**Part A, four roots with *k* = 3 and *m* = 1, five distinct calls each, the second raising `NoEffect`.** Every root: 4 calls ran (1 of them NoEffect), 1 denied, 0 other errors; phases EFFECT, EFFECT, EFFECT, NO_EFFECT; credit 1; the four RECONCILE operations in the audit log carry AUTHORISED; 4 evidence rows, all derived AUTHORISED; replay lockstep and chain ok. The fourth call was admitted on the credit the NoEffect earned, and the fifth was denied: live *R* + *C* − credit = 4 − 1 = 3, which is *k*.

**Part B, two roots whose governor holds a gate key the service does not pin.** Every root: 3 calls ran, 2 denied; phases CONSUMED, CONSUMED, CONSUMED; every RECONCILE DENIED with NONE; credit 0. The calls themselves ran, because CROSS depends on the receipt and not on evidence; their verdicts were refused, so the attempts stayed charged and the third NoEffect-free root ran out of budget one call earlier. Pinning is what makes the gate's word count.

### 3.4 Re-runs

Everything earlier was re-run under the v0.2 code, declared with the E tests, and passed as declared:

| test | result |
| --- | --- |
| W1 authority | 4/4 acceptances refused to the local role; 14/14 raw SQL statements refused; 14/14 local operations allowed |
| W2 receipts | 9/9 forgeries rejected |
| W3 lifecycle over HTTP | pass; the release racer now sends a genuine fence report and is still DENIED in all 100 rounds (rule 3 or rule 4); acceptance first 83, release first 17 |
| W4 service killed mid-acceptance | 18/18, with the RECONCILE case carrying a genuine effect report; 15 retries APPLIED, 3 DUPLICATE |
| conformance through the store | 34/34 |
| chaos | 90/90, 61 s |
| G02b | 200/200; 1000/1000 probes DENIED; acceptance first 141, release first 59 |
| G01 row lock, 300 rounds (regression; the apply path did not change) | 300/300 both waves; 6,283 reader snapshots, 0 violations; 10,650 decisions replayed through the oracle; 190 s |

Two of the earlier harnesses changed for the new API, and both changes are in the declaration: W3's release racer signs a fence report instead of naming a label, and W4's RECONCILE case signs an effect report. The store-level tests (chaos, G01, G02b, conformance) still apply labelled operations directly through the witness credential, which is the path the service takes after it has derived the label; only the service holds that credential, so in a deployment every label is a derived one.

## 4. What this shows, and what it does not

**Shows.**

- Without the gate's key, nothing can release a reservation or change a verdict. A forged NO\_EFFECT earns no credit.
- With the gate's key, a report still has to name this root, this attempt and, for a verdict, the nonce that ran. A genuine report for a sibling attempt is WRONG\_BINDING and denied.
- A caller cannot bypass derivation by naming a label: the service refuses the request before the store is touched.
- The audit log carries the derived label, the evidence table carries the report, and the receipt signs the labelled operation, so a third party can check the derivation after the fact.
- The lifecycle behaves as the contract says end to end: a NoEffect call earns exactly one replacement, used by exactly one more admission.

**Does not show.**

- Separation of the gate key from the caller's process. In v0.2 the governor is the gate. In a deployment the sandbox host signs, and the caller's process never sees the key. The derivation code does not change; the key's location does.
- What a fence report means operationally. The report says FENCED\_NO\_START; producing it truthfully is the fence's job (G04 territory), not this layer's.
- Key rotation or revocation; one gate key and one witness key.

## 5. Observations

- **Deriving labels inside the witness is what D8 was asking for.** With labels supplied by callers the contract's rule 4 was a formality. Now it is a check.
- **Binding verdicts to the nonce closes a gap that attempt identity alone leaves open.** A report for the same attempt under an earlier, recovered intent would otherwise reconcile the wrong run.
- **The in-process and remote witnesses share one derivation function**, so the two paths cannot drift.

## 6. Next

1. **The MCP wrapper**, so an agent's tools are governed without changing the agent.
2. **Gate key separation:** a sandbox-host signer, with the governor holding no gate key at all.
3. **Transport and keys:** TLS or a mutual-auth channel, key identifiers in receipts and reports, rotation.
4. **A throughput measurement** with connection pooling.

## 7. Files and hashes

| file | sha256 (first 16 hex digits) | role |
| --- | --- | --- |
| `plea_gateway/__init__.py` | `a8beefecadcdc070…` | package |
| `plea_gateway/evidence.py` | `41f6a14b7a5c21b0…` | reports and derivation (G03) |
| `plea_gateway/faults.py` | `67c9ac8f872d31b5…` | crash points |
| `plea_gateway/governor.py` | `adac1be13e0b4f79…` | SDK surface, the gate (signs reports) |
| `plea_gateway/plea_budget_ref.py` | `a367a4bbc2ca21b4…` | the verified reference, unchanged |
| `plea_gateway/receipts.py` | `7a72297f57850803…` | Ed25519 receipts |
| `plea_gateway/store.py` | `7c131f70b29f7b0a…` | the transactional store, AUTHORITY, evidence table |
| `plea_gateway/witness.py` | `8bd6300174fb7c35…` | witnesses: derive labels, sign receipts |
| `plea_gateway/witness_service.py` | `0ce82b8d848746fc…` | the witness service, pins gate keys |
| `tests/apply_once.py` | `18a47ba1a8fc9379…` | chaos child |
| `tests/budget_oracle.py` | `6b7646b7e2f4824f…` | the oracle, unchanged |
| `tests/chaos.py` | `22932e82a196e76d…` | chaos |
| `tests/common.py` | `ccda19a927a4bc54…` | credentials, the test gate key, replay lockstep, the service as a subprocess |
| `tests/conform_store.py` | `22b3d5a1e0198f0d…` | section 8 adapter |
| `tests/e1_release_evidence.py` | `1ecc76ee74aa2804…` | E1 |
| `tests/e2_reconcile_evidence.py` | `afc43394784e4875…` | E2 |
| `tests/e3_lifecycle_evidence.py` | `8e57f66c34758351…` | E3 |
| `tests/g01_race.py` | `34b00e079e0a055a…` | G01 |
| `tests/g02b.py` | `4640e08d322857b3…` | G02b |
| `tests/w1_authority.py` | `061df2240a9d1e33…` | W1 |
| `tests/w2_receipts.py` | `ae80070baa9eb532…` | W2 |
| `tests/w3_service_lockstep.py` | `d5359d1dbb7ca14d…` | W3 (release racer sends a fence report) |
| `tests/w4_service_crash.py` | `01914f2ce5338071…` | W4 (RECONCILE case sends an effect report) |
| `../budget_v3_1/contract/CONTRACT_V3_1.md` | `4200c1ce4931c9ed…` | the contract, frozen |

All recorded in `DECLARED_EVIDENCE.txt` at 08:21:35 UTC, before any declared test ran. `SHA256SUMS` in the bundle lists every file.
