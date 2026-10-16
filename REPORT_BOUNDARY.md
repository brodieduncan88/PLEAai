# PLEA gateway v1.0 — accepted bindings, authenticated replay, hardened privileged SQL

**The response to the v0.9 independent security review (NOT CLEARED).** Date 2026-10-13. Database PostgreSQL 16.13. Every result below is from the declared run recorded in `DECLARED_BOUNDARY.txt` (hashes frozen before the run), except the reviewer's own probe, which was run **unchanged on the shipped v0.9 before any repair** and again after.

---

## 1. The findings

The v0.9 review accepted the two v0.8 repairs and the independently exercised execution controls (admission, retry, argument binding, host ownership, 34/34 oracle vectors), and raised three trust-boundary findings, each confirmed from the source but — the reviewer had no PostgreSQL — not executed natively:

1. **An accepted nonce can be rewritten.** `plea_write` guarded phase *transitions* but read neither the old nonce nor the old request binding, and the transition rules only ran when the phase changed; a same-phase upsert then wrote `nonce = EXCLUDED.nonce`. The downstream consequence was shown with injected state: two execution hosts each ran an action under genuine witness signatures while the root still showed one consumed attempt.
2. **A cached success is unauthenticated.** The gateway credential held `INSERT, UPDATE` on `results`, and the governor replayed a stored `value` *before* reserving, with no signed outcome envelope and tolerating a missing nonce. A fabricated row was returned as a successful payment of 999999 with zero attempts, zero witness decisions and zero executions.
3. **Privileged SQL configuration.** Both `SECURITY DEFINER` functions used unqualified table names with `search_path = pg_catalog, public` — `pg_temp` is searched first unless listed — and never revoked PostgreSQL's default `PUBLIC` EXECUTE.

Plus an operational concern: `control = control or admin` could leave the owner credential in the agent process.

---

## 2. Reproduction — the reviewer's own probe, run unchanged, before and after

The reviewer supplied `native_pg_probes_NOT_RUN.py` (syntax-checked only) and asked for it to be run unchanged against a disposable database before any repair, the failures preserved, then re-run after. That is what was done, with their script byte-for-byte (sha256 `3fa3e0e3…`; `outputs/review5/`). **Every suspected path reproduced natively on v0.9.**

| probe (reviewer's, as `plea_local`) | shipped v0.9, before | v1.0, probe unchanged | v1.0, probe adapted¹ |
|---|---|---|---|
| raw `UPDATE attempts SET nonce` | REJECTED 42501 | REJECTED 42501 | REJECTED 42501 |
| **same-phase accepted-nonce rewrite via `plea_write`** | **ACCEPTED [FAIL]** | **REJECTED 23514** | REJECTED 23514 |
| accepted nonce afterwards | **`n-new`** | **`n-old`** | `n-old` |
| direct `INSERT INTO results` (the cache injection) | allowed | **halts: permission denied** | REJECTED 42501 |
| **fabricated success returned, zero attempts** | **returned `{paid, 999999}`** | — (halted above) | **REJECTED** (`RequestKeyReused`) |
| `PUBLIC` EXECUTE on `plea_write` / `plea_new_root` | **True / True** | — | **False / False** |
| temp `roots` shadows `plea_new_root` | **SUCCESS: temp 1, public 0** | — | SUCCESS: **temp 0, public 1** |
| control role calls `plea_new_root` | **ACCEPTED** | — | **REJECTED 42501** |
| `plea_local` TEMPORARY privilege | True | — | True (left on, §8) |

¹ The unchanged probe asserts the flaws (its cache injection has no `try`), so once the direct INSERT is refused it stops there — that stop *is* the after-evidence and is preserved. The adapted copy changes only the two cache-injection sites to log a refusal instead of aborting, and additionally plants the same fake row **as the owner** (past the grant) so the governor's check is exercised on its own; the diff is shipped beside it. Every other probe line is identical.

The v0.8 counterexamples A/B were also re-run against v1.0 with the unchanged attack SQL (`review4_repro_v1_0.json`): both still rejected (A now trips the binding rule first, the transition rule behind it).

---

## 3. The repair

Confined to `plea_gateway/store.py` (the write function, a new outcome function, the grants) and `plea_gateway/governor.py` (replay verification, the control credential). The reference engine, gate host, witness, evidence, receipts and TLS are byte-identical to v0.9.

### 3.1 The accepted bindings are immutable in place (finding 1)

`plea_write` now reads the existing `req` and `nonce` for every attempt it updates and enforces, independent of the phase rules and independent of the caller's credential:

- `req` never changes.
- `nonce` changes **only** where the contract changes it: set by START (`TOKEN→INTENT_PENDING`: old must be null, new must not), cleared by RECOVER (`INTENT_PENDING→TOKEN`: new must be null). On **every other update — a same-phase rewrite included — it must be carried unchanged.** This is exactly the reference engine's nonce behaviour (`_start` sets; `_recovery_view` clears; every other rule `dataclasses.replace`s with the nonce kept).

The reviewer's exact probe — operation `RECEIPT`, phase `CONSUMED` unchanged, flags unchanged, nonce `n-old → n-new` — is refused with `check_violation` and nothing changes; the witness's next receipt still binds `n-old`.

### 3.2 A stored outcome is authenticated on every replay (finding 2)

Two layers, both required:

- **In the database.** No login role holds `INSERT/UPDATE/DELETE` on `results`. Outcomes are written only through `plea_put_result`, which requires an attempt that **exists, is consumed and was admitted (`crossed`)**; the first stored outcome stands, except that an `unknown` is replaced once by a known one. A row for an attempt that was never admitted cannot exist.
- **In the governor.** Every terminal outcome is stored **with the executor's signed effect report**. On replay — including the first return after a run, which goes through the same path — the stored nonce must equal this action's nonce (a missing one is refused), the report must verify against the **pinned executor key** for this root, attempt and nonce, its digest must cover the value being returned, and its claim must match the stored kind. Only then is the value returned. The gateway holds no executor key in host mode, so it cannot mint a report; a row planted past the grant is refused.

### 3.3 `SECURITY DEFINER` hardening (finding 3)

All three functions (`plea_write`, `plea_new_root`, `plea_put_result`): every table reference and the row type schema-qualified (`public.…`); `SET search_path = pg_catalog, pg_temp` — the temporary schema **explicitly last**, so a temporary relation can never shadow a name; `REVOKE EXECUTE … FROM PUBLIC` before the named grants (`plea_write`: gateway, witness, control; `plea_new_root`: gateway, witness; `plea_put_result`: gateway only). `REVOKE CREATE ON SCHEMA public` from every login role stays.

### 3.4 The owner credential stays out of the agent process

`Governor.control` no longer falls back to `admin`: the operator methods require an explicit `control=` and raise otherwise. `admin=` remains a provisioning convenience for tests and development; a production gateway creates its own root through `plea_new_root` and holds no owner credential (README).

---

## 4. Why this holds

`plea_write` and `plea_put_result` are the **only** write paths to the authoritative tables and the outcome cache. A legitimate apply presents exactly the attempt facts the verified reference engine produced, so every binding it carries satisfies 3.1; a hand-written call is held to the same rules under the same `session_user`. The nonce is the executor/action binding the witness's receipts and the host's admission check are keyed on, so with it immutable in place, a second executor cannot be furnished with a receipt for a different action on the same consumed attempt. A client-visible success can be returned only from a row the database let a consumed, admitted attempt have, carrying a report that only the pinned executor could have signed over exactly that value. Completeness is demonstrated, not asserted: every legitimate nonce path (S1), genuine replay without a second execution (S2) and the whole earlier regression pass unchanged (§6).

---

## 5. Declared tests S1–S3

Declared before the run in `DECLARED_BOUNDARY.txt`; record in `outputs/s_tests.json`.

**S1 — binding immutability (15/15).** The reviewer's probe refused as `plea_local`, attempt and audit log unchanged, nonce still `n-old`, the witness's receipt still binding it; the same rewrite refused as the owner (a rule, not an authority check); a `req` rewrite refused; a nonce change smuggled onto a legal phase change (`CONSUMED→EFFECT`, `INTENT_PENDING→CONSUMED`, `CONSUMED→INDETERMINATE` dropping it) refused; START with a nonce already bound, START without one, and RECOVER keeping one, each refused; set by START, carried through ACCEPT_INTENT/RECEIPT/CROSS/RECONCILE, cleared by RECOVER, carried by REREGISTER, all through the proper credentials; replay lockstep.

**S2 — authenticated replay (13/13).** A genuine outcome runs once and replays the same value from the stored, signed outcome; the stored row carries the nonce and the gate's report; `plea_local` raw INSERT refused; storing an outcome for a reserved-never-admitted or a non-existent attempt refused; a known outcome is never replaced, an unknown one is replaced once; then five fabricated rows planted **as the owner** — the reviewer's (no attempt, no nonce), right nonce but no report, an impostor's signature, a genuine-key report whose digest covers a different value, a genuine report whose claim (`NO_EFFECT`) contradicts the stored kind — **each refused, nothing ran, no attempt exists**; replay lockstep.

**S3 — hardening (9/9).** `pg_proc` shows all three functions `SECURITY DEFINER` with `search_path=pg_catalog, pg_temp`; `PUBLIC` holds no EXECUTE on any; the reviewer's shadowing probe (temp `roots`) writes `public.roots` and the temp table stays empty; the same for temp `attempts`/`results` against `plea_put_result`; the control credential can neither create a root nor store an outcome, the witness cannot store one; no login role can create objects in `public` nor hold direct DML on `results`.

---

## 6. Full regression, both isolation modes

Re-run on a clean `plea10` after the v1.0 change.

| Suite | Result |
|---|---|
| **S1–S3** (v1.0) | **15 + 13 + 9 = 37/37** |
| Q1–Q2 (v0.9) | 17 + 16 = **33/33** |
| P1–P2 (v0.8) | 11 + 15 = **26/26** |
| V1–V6 / R1–R6 / H1–H5 / T1–T4 / M1–M3 | **43 / 43 / 33 / 35 / 28** |
| E1 / E2 / E3 · W1–W4 | 13 / 9 / PASS · PASS, PASS, PASS, 18/18 |
| conform_store · chaos · G02b | **34/34 · 90/90 · 200/200** |
| G01 last-slot race — **lock** / **serializable** | **300/300 / 300/300** |

No earlier test changed for v1.0; the suite ran unmodified against the new write function and the authenticated replay (the host and MCP suites exercise replay through real hosts; W3 through the in-process gate).

---

## 7. The reviewer's no-PostgreSQL script, against v1.0

`independent_scoped.py` (unchanged) was run against the v1.0 code: its first eleven observations match as before. It then **stops at its cache test**, because the governor now refuses the injected row (`RequestKeyReused`: no nonce) instead of returning it — the script asserted the flaw and so cannot continue past its absence; the stop is preserved. Its nonce test injects directly into a memory adapter, bypassing the database by construction, and therefore still "matches": that path never touched `plea_write`. The database path it stands for is closed natively by the probe (§2) and S1.

---

## 8. Decisions stated plainly

- **`TEMPORARY` privilege is left on.** The shadowing attack is defeated by qualification and `pg_temp` last (§2, S3), not by forbidding temporary tables; and revoking it would make the reviewer's probe abort before its shadowing step. `REVOKE TEMPORARY ON DATABASE … FROM PUBLIC` is documented as optional extra hardening.
- **Decision labels are the caller's text.** `plea_write` guards the *state* (phases, bindings, modes, counters, chain); the `kind`/`code`/`observation` it appends are supplied by the applying process. A mislabelled decision is detected by replay lockstep (the log replayed through the independent oracle), which every suite runs — not by the database. This is unchanged and stated so the boundary is not overstated.
- **Not in this bundle:** the reviewer's items 6 (a human Gate B quickstart and a design-partner staging integration) are operational steps, not code, and are not claimed here.
- Outcomes stored by versions before v1.0 carry no report and will no longer replay; there is no deployment with such rows.

---

## 9. Scope and what is unchanged

The contract, the verified reference engine, the gate host, the witness service, evidence and receipt handling and TLS are byte-identical to v0.9. v1.0 makes the database enforce the bindings an attempt carries in addition to its transitions, makes a cached result worthless without the executor's signature over it, and configures the privileged functions as the PostgreSQL manual prescribes. File hashes in `DECLARED_BOUNDARY.txt`.
