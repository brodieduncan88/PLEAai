# PLEA gateway v0.9 — transition integrity and control separation

**The response to the v0.8 independent security review's CRITICAL finding.**
Date 2026-10-12. Database PostgreSQL 16. Every result below is from the declared run recorded in `DECLARED_INTEGRITY.txt` (hashes frozen before the run).

---

## 1. The finding

The v0.8 review returned **Conditional FAIL** on one critical point and two evidence-reporting errors.

**Critical — `plea_write` did not verify the complete contract-authorised transition.** The v0.8 write function checked only three things about a caller-supplied post-state: the *new* phase's authority (an accepted phase must come from the witness), the aggregate counters I1/I2 as a *worsening-only* backstop, and the mode guard keyed on the caller-supplied operation *name*. It never checked that each attempt's *(old phase → new phase)* was a transition the contract actually produces. The reviewer supplied two counterexamples, run as the gateway credential `plea_local` against native PostgreSQL:

- **Scenario A — a consumed budget is freed.** With a budget of one (`k = 1`) already consumed, the live charge is `1 = k`, so a second reservation is correctly denied. A hand-written `plea_write` that rewrites the one `CONSUMED` attempt to `DISCARDED` reduces the live charge to zero. The worsening-only I2 backstop does not fire on a *reduction*, and `DISCARDED` is not an accepted phase, so the authority check does not fire either. The write commits, and a second reservation is then admitted — **more than `k` admitted on a budget of `k`.**
- **Scenario B — a held run is resumed without approval.** With the witness `HELD`, a hand-written `plea_write` carrying a mode payload `witness → ACTIVE` and an operation field reading `RECOVER` satisfied the v0.8 guard `op0 NOT IN ('RECOVER','REREGISTER')` (false, so it did not fire). The database cannot verify a recovery approval, and the operation name is caller-supplied, so **the witness is flipped back to `ACTIVE` with no valid recovery.**

**Evidence errors.** (i) The bundled `review3_repro_v0_7.json` recorded one owner per contest — post-fix numbers, not the v0.7 failure it was labelled as. (ii) The repair tests were reported as "28/28"; `p_tests` is 26. Both are corrected in §7.

---

## 2. Reproduction — before and after

One script, `plan/repro_counterexamples.py`, runs **both** counterexamples as `plea_local` through a hand-written `plea_write`, against **both** the unchanged v0.8 code (from the v0.8 bundle) and the v0.9 code. The attack SQL is identical in both runs; only the installed `plea_write` differs. Full record: `outputs/review4_repro_v0_8.json`.

| Counterexample | v0.8 | v0.9 |
|---|---|---|
| **A** `CONSUMED→DISCARDED` forged as `plea_local` | **ACCEPTED** — committed; live `[0,1,0] → [0,0,0]`; the second `RESERVE` is **APPLIED** (budget breached) | **REJECTED** — `check_violation: illegal attempt transition CONSUMED->DISCARDED`; the second `RESERVE` stays **`DENIED BUDGET_EXHAUSTED`** |
| **B** forged `RECOVER` flips `witness HELD→ACTIVE` | **ACCEPTED** — committed; witness `HELD → ACTIVE` without approval | **REJECTED** — `insufficient_privilege: a mode change is reserved to the control plane`; witness stays **`HELD`** |

Both holes are real on v0.8; both are closed on v0.9.

---

## 3. The repair

The entire product change is in `plea_gateway/store.py` (the write function) and `plea_gateway/governor.py` (a control credential for the operator methods). The reference engine, gate host, witness, evidence, binding, receipts and TLS are **byte-identical to v0.8** (see the hashes in `DECLARED_INTEGRITY.txt`).

### 3.1 The legal per-attempt transition relation (closes Scenario A)

`plea_write` now rejects any attempt whose `(old phase → new phase)` is not a transition some contract operation produces. The relation is the per-attempt closure of the contract's section 5 rules:

| from | to | operation | credential class |
|---|---|---|---|
| *(insert)* | `RESERVING` | RESERVE | gateway |
| `RESERVED` | `TOKEN` | TOKEN | gateway |
| `TOKEN` | `INTENT_PENDING` | START | gateway |
| `RESERVING` | `RESERVED` | ACCEPT_RESERVATION | witness |
| `INTENT_PENDING` | `CONSUMED` | ACCEPT_INTENT | witness |
| `RESERVED`, `TOKEN` | `RELEASED` | RELEASE | witness |
| `CONSUMED` | `NO_EFFECT`, `EFFECT` | RECONCILE | witness |
| `RESERVING` | `DISCARDED` | RECOVER | control |
| `INTENT_PENDING` | `TOKEN` | RECOVER | control |
| `RESERVING`,`RESERVED`,`TOKEN`,`INTENT_PENDING`,`CONSUMED` | `INDETERMINATE` | REREGISTER | control |

plus the in-place flag changes — `receipt` false→true on a consumption phase (RECEIPT, gateway), `crossed` false→true on `CONSUMED` (CROSS, witness). **Any other pair is rejected** (`check_violation`). `CONSUMED→DISCARDED` is in no row, so Scenario A is rejected outright; so is every other budget-reducing rewrite (`CONSUMED→RELEASED`, `NO_EFFECT→CONSUMED`, a straight insert at an accepted phase, …). The fact-shape rules are enforced in the same pass: a new attempt must be a bare reservation; `crossed` and `receipt` are monotone (never reset or cleared) and appear only on a consumption phase.

Each transition is **reserved to the credential class of its operation**, checked against `session_user` (the login role, unchanged under `SECURITY DEFINER`). This subsumes the old new-phase authority check and extends it: a gateway cannot drive a witness transition *or* a control transition, even to a phase that is not itself "accepted" (e.g. `RESERVING→DISCARDED`, a budget-freeing move the v0.8 code would have allowed `plea_local` because `DISCARDED` is not an accepted phase).

### 3.2 The control-plane credential (closes Scenario B)

A fourth login role, **`plea_control`**, is the only non-owner role that may change a mode. `plea_write` now reserves **every** mode change to `session_user IN ('plea_control','plea')`, **independent of the caller-supplied operation name**. The gateway credential cannot change a mode by any path — the proper apply, a forged `plea_write`, or raw DML — so Scenario B is rejected regardless of what the `op` field says. The control operations (HOLD, STOP, TERMINALISE, TERMINAL, RECOVER, REREGISTER) are the only operations that change a mode; they run as `plea_control`. The operator CLI (`mcp/plea_ctl.py`) and the governor's operator methods use this credential; the gateway's per-request flow and the witness's acceptances are unaffected.

### 3.3 `SECURITY DEFINER` hardening

Both owner-side functions pin `SET search_path = pg_catalog, public`, and no login role may create objects in `public` (`REVOKE CREATE ON SCHEMA public`), so nothing can be planted there to shadow the functions' unqualified references.

---

## 4. Why this is sound and complete

- **Sound (no illegal change slips through).** `plea_write` is the *only* write path to the authoritative tables (direct DML is revoked from every login role). A legitimate apply writes only the attempts the verified reference engine changed, so every pair it presents is in the relation and within its credential's class. An attacker's hand-written call is held to the same relation and the same `session_user` check. A budget can be freed only by moving a live attempt to a non-live phase; the only such legal moves are `{RESERVED,TOKEN}→RELEASED` (witness) and `RESERVING→DISCARDED` (control) — both reserved away from the gateway. Modes can be changed only by `plea_control`. The I1/I2 aggregate checks remain as a backstop behind the relation.
- **Complete (no legitimate apply is rejected).** The relation is exactly the per-attempt closure of the engine's rules, so every transition the engine produces is accepted. This is demonstrated, not asserted: all 12 legal transition pairs apply through their proper credential in Q1, and the whole earlier regression — including the full lifecycle, recovery, reregistration and the 34 conformance vector groups — passes unchanged (§6).

---

## 5. Declared tests Q1–Q2

Declared before the run in `DECLARED_INTEGRITY.txt`; full record in `outputs/q_tests.json`.

**Q1 — transition integrity (17/17).** The two counterexamples refused as `plea_local` (A `check_violation`, budget stays exhausted; B `insufficient_privilege`, witness stays HELD); a battery of **12 illegal pairs**, each forged *as the owner* so only legality (not authority) is under test, all refused as `check_violation` with nothing changed; a straight insert at `CONSUMED`/`RESERVED`/`TOKEN`/`DISCARDED` refused; **all 12 legal pairs apply** through their proper credential and reach the new phase; a new attempt carrying `crossed` or `receipt` refused; `receipt` cannot be cleared and `crossed` cannot be reset; `crossed` and `receipt` only on a consumption phase; replay lockstep.

**Q2 — control separation (16/16).** `plea_local` cannot apply HOLD, STOP, TERMINALISE, TERMINAL, REREGISTER or RECOVER (AuthorityError, state unchanged); `plea_local` forging a witness or a business mode change via `plea_write` is refused and the mode is unchanged; `plea_local` raw UPDATE of a mode is refused; `plea_control` applies HOLD/RECOVER and REREGISTER; `plea_control` **cannot** forge an accepted phase (still the witness's) nor write the authoritative tables directly; the chain stays valid.

---

## 6. Full regression, both isolation modes

The whole suite, re-run on a clean `plea9` after the v0.9 change, in both isolation modes for G01.

| Suite | Result |
|---|---|
| **Q1–Q2** (v0.9, transition integrity, control separation) | **17 + 16 = 33/33** |
| P1–P2 (v0.8, ownership, gateway credential) | 11 + 15 = **26/26** |
| V1–V6 (v0.7, admission at the host) | **43/43** |
| R1–R6 (v0.6, authorisation and recovery) | **43/43** |
| H1–H5 (gate host) | **33/33** |
| T1–T4 (mutual TLS) | **35/35** |
| M1–M3 (governed MCP) | **28/28** |
| E1 / E2 / E3 (evidence) | 13 / 9 / PASS |
| W1 (authority boundary, updated for v0.9) / W2 / W3 / W4 | PASS / PASS / PASS / 18/18 |
| conform_store (contract vector groups) | **34/34** |
| chaos | **90/90** |
| G02b | **200/200** |
| G01 last-slot race — **lock** | **300/300** |
| G01 last-slot race — **serializable** | **300/300** |

W1 was updated to the new boundary: the six control operations move from "applied through `plea_local`" to refused-to-`plea_local` and applied through `plea_control`; the seven genuine gateway operations stay with `plea_local`. No test was weakened.

---

## 7. Corrections to the v0.8 evidence (stated plainly)

- **The repair-test count.** The v0.8 delivery message reported "28/28". `p_tests` is **26** checks (P1 11 + P2 15); the 28 is `mcp_tests` (M1 16 + M2 4 + M3 8). The v0.8 `DECLARED_AUTHORITY.txt` likewise over-stated P2 as 17 (28 total); the executed P2 was 15. The code was correct and unchanged; only the written number was wrong. This report and `DECLARED_INTEGRITY.txt` use the executed counts.
- **The v0.7 reproduction file.** The v0.8 bundle shipped `review3_repro_v0_7.json` with the *post-fix* numbers (one owner per contest), not the v0.7 failure it was labelled as. It has been regenerated by running `p_repro.py` **against the frozen v0.7 source**, so it again records the original failure: a 4-process stampede yields more than one owner in **10 of 10** trials, a stale owner writes after a takeover, and every `plea_local` raw escalation is allowed. To prevent a recurrence, `p_repro.py` no longer writes that filename by default — it writes `PLEA_REPRO_OUT` (default `review3_repro_against_current.json`) — so running it against the current code can never again overwrite the v0.7 evidence.

---

## 8. Scope and what is unchanged

The fix is confined to the write function and one new credential. The contract (`CONTRACT_V3_1.md`), the verified reference engine (`plea_budget_ref.py`), the gate host, the witness service, the evidence and receipt handling, and the TLS layer are byte-identical to v0.8. The attempt-budget semantics are unchanged; v0.9 only makes the database enforce the *complete* set of transitions the contract already defined, and separates the credential that may change a run's mode.

File hashes for every source file are in `DECLARED_INTEGRITY.txt`.
