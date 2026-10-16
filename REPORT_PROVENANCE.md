# PLEA gateway v1.1 — the audit record authored by the database, and budgets provisioned only by the control plane

**The response to the v1.0 independent security review (NOT CLEARED).** Date 2026-10-13. Database PostgreSQL 16.13. Every result below is from the declared run recorded in `DECLARED_PROVENANCE.txt` (hashes frozen before the run), except the reviewer's own probe, which was run on the shipped v1.0 **before any repair** and again after.

---

## 1. The findings

The v1.0 review accepted the three v0.9 repairs (nonce immutability, authenticated replay, hardened definers), independently exercised the cryptographic replay checks and the 34 oracle vector groups, and raised two authority findings, confirmed from the source but — the reviewer had no PostgreSQL — not executed natively:

- **F1 — the privileged write could record a semantically false decision.** `plea_write` enforced transitions, credentials and chain linkage but stored the caller's `op`, `kind`, `code`, `observation` and `hash` as given. A `["STOP"] / APPLIED` record with a correctly recomputed hash and *no* mode change would pass every check while the business mode stayed OPEN: `verify_chain` would say ok for a hash-consistent log of an event that never happened. (My v1.0 report had stated that decision labels were caller text; the reviewer rightly extended that to the operation, the observation and the claimed post-state.)
- **F2 — run creation was a separate, unguarded trust boundary.** The gateway credential held EXECUTE on `plea_new_root`, which accepted any root identity and any non-negative `k`, `m`. A budget-one root could be exhausted and the same credential could create another root with an arbitrary budget. A policy escape only if an agent is meant to be bound to one allowance — which it is: the contract's World binds a caller to one root.
- **§4 — deployment.** The README still carried a v0.8 title, and its minimal example handed `admin=` (the owner) and `control=` to the same process as the governor.

---

## 2. Reproduction — the reviewer's probe, before and after

The reviewer supplied `native_pg_forged_audit_NOT_RUN.py` (syntax-checked only) and asked that it be run **unchanged** on a disposable database before any repair, its results preserved including harness errors, then re-run after. Done, in `outputs/review6/`:

- **Unchanged, on shipped v1.0:** the script stops in its own harness before any SQL — line 41 hands the reference a raw tuple, `ref.apply(state, ('STOP',))`, where the reference takes a parsed operation, and raises `InvalidInput`. Preserved as `forged_audit_before_v1_0_UNCHANGED.stdout.txt`. It is a harness error, not evidence about F1 or F2.
- **One line fixed** (`ref.parse_op(('STOP',))`; diff shipped), on the same frozen shipped-v1.0 copy, fresh database: **both findings reproduce natively.**
- **After**, on v1.1, with the two *setup* roots owner-provisioned (the gateway can no longer create one; the forged write and the attacking `local.new_root(root2, 1000, 999)` untouched; diff shipped): **both refused.**

| probe (the reviewer's, as `plea_local`) | shipped v1.0, before | v1.1, after |
|---|---|---|
| **A.** `["STOP"]/APPLIED`, correct hash, no mode change — `plea_write` | **ACCEPTED** | **REJECTED 23514** `decision kind APPLIED does not describe this write (state changed: f)` |
| recorded operation / kind | `["STOP"]` / `APPLIED` | — (no record) |
| `verify_chain` afterwards | **ok** (a false history, hash-consistent) | ok (no record was appended) |
| business after / next RESERVE | OPEN / APPLIED | OPEN / APPLIED |
| **B.** after exhausting a `k=1` root, `plea_local` creates `k=1000, m=999` | **CREATED**; RESERVE on it **APPLIED** | **REJECTED** `permission denied for function plea_new_root` |

The reviewer's no-PostgreSQL script reproduces its 16/16 on shipped v1.0 here (`scoped_before_v1_0.json`); against v1.1 see §7 — one of its two source-inspection checks flips, the other is a textual heuristic that does not see the repair. The v0.8 counterexamples A/B were re-run against v1.1 with the unchanged attack SQL (`review4_repro_v1_1.json`): both still rejected.

---

## 3. The repair

Confined to `plea_gateway/store.py` (the write function, four owner-only helpers, the grants), `plea_gateway/governor.py` (provisioning), `mcp/plea_ctl.py` (`provision`) and `mcp/plea_mcp.py` (`--control-dsn`). The reference engine, gate host, witness, evidence, receipts and TLS are byte-identical to v1.0; no earlier test changed except one S3 check that encoded the old provisioning policy (§8).

### 3.1 The database authors the audit record (F1)

`plea_write` no longer trusts the record it is handed. For every decision it appends, in one transaction with the state change:

- **The observation is the database's.** `plea_observe` derives the section-7 observation (modes, live and accepted views, credit, the attempts) from the rows just written. The caller's observation must equal it; the stored one is the database's.
- **The kind is bound to the change.** The observation is taken before and after the write; the kind must be `APPLIED` exactly when they differ. The reviewer's record — `APPLIED` with nothing changed — is refused; so is a real change labelled `DENIED`, and an `APPLIED` whose payload re-states an attempt unchanged.
- **The operation is bound to the transition.** Each attempt change implies the operation that produces it (an insert is a RESERVE, `RESERVING→RESERVED` an ACCEPT_RESERVATION, a receipt flag a RECEIPT, …), each mode change likewise (a witness hold is a HOLD; reactivation a RECOVER or REREGISTER; `OPEN→STOPPING` a STOP or REREGISTER; …), and only the contract's mode pairs exist. The operation named must be the implied one.
- **The hash is the database's.** `plea_decision_hash` recomputes `sha256(prev ‖ canonical({seq, op, kind, code, observation}))` over exactly what is stored, with `plea_canonical` — a PL/pgSQL canonical form identical to the client's `json.dumps(sort_keys=True, separators=(',',':'))`: keys in code-point order, no whitespace, integers only (a non-integer is refused, so there is nothing to diverge on), strings escaped exactly as Python's `ensure_ascii` does. The caller's hash must equal it. The identity is demonstrated, not assumed: 300 random values with quotes, backslashes, control characters, non-ASCII and non-BMP text, and 100 random decision bodies, agree character for character (U1).

So a record that does not describe the transition it accompanies cannot exist, and `verify_chain` — ordinary hash verification — again attests to real history. The shape is also closed: an unknown operation name, an unknown kind, or a missing code, observation or hash is refused before any write.

### 3.2 A budget is provisioned only by the control plane (F2)

`plea_new_root` is reserved to `plea_control` (and the owner): EXECUTE is revoked from PUBLIC, from the gateway and from the witness — the revoke is explicit so that re-running `init_authority()` on a v1.0 database removes the grants it had — and the function checks `session_user` itself, so a mis-grant could not reopen it. The gateway credential cannot create a root, and therefore cannot mint itself an allowance: the reviewer's probe is refused and the exhausted gateway stays exhausted on the one root it has.

### 3.3 The production shape, made unambiguous (§4)

- `Governor` holding only the gateway credential **refuses an unprovisioned root**, naming the provisioning step; given `control=` it provisions; `admin=` remains a test convenience. It never creates a root through the gateway store.
- `plea_ctl.py ROOT provision --budget K [--replacement M]` provisions through `plea_control` and reports an existing root's immutable budget.
- `plea_mcp.py` holds `plea_local` only, refuses to start against an unprovisioned root and runs against a provisioned one (both checked directly, U2); `--control-dsn` / `--admin-dsn` provision on start for an operator launch or a test, and neither belongs in an agent-facing deployment.
- The README carries the v1.1 title, a **"Production shape, stated plainly"** paragraph, and examples in which the agent's process holds the gateway credential and nothing else.

---

## 4. Why this holds, and what remains the caller's text

`plea_write` is the only path that appends a decision. Every record it appends is now bound to the write it accompanies on all four axes — the state recorded, whether it changed, which operation changed it, and the hash over all of that — under rules that do not depend on the caller's credential (the owner is refused the same records). What the database still cannot attest is the `code` label, and, on a record of a *refusal* (nothing changed), which operation was refused: a gateway could log that a RESERVE was denied when none was requested. Such a record moves no state, frees no budget, admits nothing and claims no event; replay lockstep (the log replayed through the independent oracle, run by every suite) still detects a refusal the contract would have applied. This is stated so the boundary is not overstated.

---

## 5. Declared tests U1–U2

Declared before the run in `DECLARED_PROVENANCE.txt`; record in `outputs/u_tests.json`.

**U1 — audit integrity (21/21).** The reviewer's probe refused as `plea_local`, atomically (no entry, no head advance, run still OPEN and still admitting); refused as the owner too; a real change recorded as DENIED, an observation that misdescribes the post-state, a correct record hashed over a different observation, an insert recorded under another operation, an unknown kind, an unknown operation — each refused, none leaving a trace; an APPLIED whose payload changes nothing refused; a witness hold recorded as a STOP refused as the control plane; the chain still verifying; the canonical form identical on 300 random values and the hash on 100 random bodies; a non-integer refused; a full lifecycle with a duplicate, a no-op, a release, hold/recover and stop/terminalise/terminal applying through their credentials, every stored observation the database's own and APPLIED exactly the records that change it; `verify_chain` and replay lockstep holding; REREGISTER applying.

**U2 — provisioning authority (15/15).** The gateway and the witness cannot create a root; the control credential provisions one with the budget given; the reviewer's probe (exhaust a `k=1` root, then create `k=1000`) refused and the gateway still exhausted with no other root; a gateway-only governor refuses an unprovisioned root naming the provisioning step; given the control credential it provisions, a second does not change the immutable budget, and a gateway-only governor then runs against it; `plea_ctl provision` creates and reports an existing root; PUBLIC holds no EXECUTE on `plea_new_root` nor on the four helpers, `plea_new_root` is granted to the owner and the control plane only, and no login role can call the helpers; `plea_mcp.py` with only the gateway credential refuses an unprovisioned root and starts against a provisioned one.

---

## 6. Full regression, both isolation modes

Re-run on a clean `plea11` after the v1.1 change.

| Suite | Result |
|---|---|
| **U1–U2** (v1.1) | **21 + 15 = 36/36** |
| S1–S3 (v1.0) | 15 + 13 + 9 = **37/37** |
| Q1–Q2 (v0.9) · P1–P2 (v0.8) | **33/33 · 26/26** |
| V1–V6 / R1–R6 / H1–H5 / T1–T4 / M1–M3 | **43 / 43 / 33 / 35 / 28** |
| E1 / E2 / E3 · W1–W4 | 13 / 9 / PASS · PASS, PASS, PASS, 18/18 |
| conform_store · chaos · G02b | **34/34 · 90/90 · 200/200** |
| G01 last-slot race — **lock** / **serializable** | **300/300 / 300/300** |

Every earlier suite ran unmodified against the new write function (the one S3 change is §8): every legitimate decision of every suite was re-derived, re-bound and re-hashed by the database and matched the client's.

---

## 7. The reviewer's no-PostgreSQL script, against v1.1

`run_scoped_checks.py` (unchanged) against the assembled v1.1 bundle (`scoped_after_v1_1.json`): **14/16**. The 11 executable cryptographic and replay checks, the 34 oracle vector groups and the PDF identity pass. The manifest check reports **no mismatch** (every listed file hashes as declared) and still **fails**, because it also asserts the v1.0 bundle's file count, 413; v1.1 had 478 files when the script ran, and the shipped manifest lists two more, the script's own output and its console log. The check `forged STOP decision can carry a cryptographically internally consistent chain hash` still passes: it is computed in Python only (the script marks it "database call not run"); anyone can compute a self-consistent hash over a false observation, and what v1.1 changes is that the database no longer accepts it (§2 probe A, U1). Of its two **source-inspection** checks, which assert that the flaws are *present*:

- `plea_new_root accepts caller-selected positive k,m and grants role plea_local` now **fails** — the grant is gone — as it should.
- `plea_write SQL accepts caller-supplied p_kind, p_code and p_head` still **passes**, i.e. still claims the flaw. It is a textual heuristic: it looks for the strings `IF p_head <>` and `chain_hash(` in the installer and finds neither. The recomputation is there, written `IF p_head IS DISTINCT FROM h` (NULL-safe) and `plea_decision_hash(...)`. I have not reworded the code to satisfy a grep; the executable proof is U1 (the reviewer's own record refused, and the database's hash shown identical to the client's on 100 random bodies), and the probe table in §2. Stated here so the reviewer is not surprised by their own script's output.

---

## 8. Decisions stated plainly

- **One S3 check changed.** v1.0's S3 asserted that the control credential *cannot* create a root — least privilege under the old policy. The policy is now explicit (a budget is provisioned by the control plane), so that check became "neither the gateway nor the witness can create a root", and S3's shadowing probe runs as the provisioning credential. S3 stays 9 checks; the change and its reason are in the declaration.
- **A new rule was at first too strict, and the conformance vectors caught it.** My business-pair rule admitted `OPEN→STOPPING`, `STOPPING→TERMINALISING` and `TERMINALISING→TERMINAL` and nothing else; the contract's erratum E6 has REREGISTER restart a `TERMINALISING` run in `STOPPING`, and vector group B25 refused to apply under v1.1 in the development run (33/34). The pair `TERMINALISING→STOPPING` is now admitted, bound to REREGISTER. A rule that is sound but incomplete fails loudly here — every suite is replayed through the same write function — which is the reason an added check is run against the whole contract before it is declared.
- **The forges in Q and S now name a real operation.** Those suites' hand-written `plea_write` calls carried a placeholder operation name. v1.1 refuses an unknown name before any other rule, so in the development run one Q2 authority check failed outright (it expected the witness-authority refusal and got "unknown operation"), and the other forges would have been refused for the wrong reason — the evidence hollow while the checks still passed. Each forge now names the operation that produces its transition (an `ACCEPT_RESERVATION` for `RESERVING→RESERVED`, a `RECEIPT` for a same-phase rewrite, …), and the refusal each receives was re-read to be the rule under test. Counts unchanged; recorded in the declaration.
- **The cost, measured.** Deriving, canonicalising and hashing every record inside the database is not free: in the declared run, G01 (10,650 decisions a mode, 16 racing workers) took **214.4 s in lock mode and 338.2 s serializable, against 150.2 s and 240.4 s for v1.0** — about +6 ms per decision (+9 ms serializable, retries included), uncontended. The hashing itself is cheap; the character-by-character PL/pgSQL string escaping is most of it, and is where an optimisation would go if a deployment needs one. It is spent on every write, by design: the alternative is a record the database cannot vouch for.
- **Upgrade.** A database initialised by v1.0 keeps function ACLs across `CREATE OR REPLACE`; v1.1's `init_authority()` revokes the stale grants explicitly (checked on such a database before the declared run). Pre-v1.1 audit rows were client-authored and are not retro-verified; there is no deployment with such rows.
- **The A/B rerun's detail.** The v0.8 counterexample script labels its forged write `FORGE_DISCARD`; v1.1 now refuses that at the operation-name check before the transition rule it was written to hit. Q1 and S1 drive the same forgeries under legal names and are refused by the transition and binding rules.
- **The probe's harness error is preserved** and the one-line fix is shipped as a diff; the after-run's second adaptation (owner-provisioned setup roots) is likewise a diff.
- **Not claimed here:** a human Gate B quickstart, a design-partner staging integration, verified delivery and production throughput — operational gates the reviewer lists as outside this source review.

---

## 9. Scope and what is unchanged

The contract, the verified reference engine, the gate host, the witness service, evidence and receipt handling and TLS are byte-identical to v1.0. v1.1 makes the database the author of its own audit record and the control plane the only provisioner of a budget. File hashes in `DECLARED_PROVENANCE.txt`.
