# Amendment 16: specification for a Step 3 (for review; not approved for implementation)

21 November 2026. Private working material. Internal work under the owner's direction. It is a specification only.
Nothing is implemented by it; no code of the courier, the mailbox, the witness, the gateway or any deployment
configuration is changed; it is not a declaration and not an acceptance of anything. It is kept on the branch
`diagnostic-amend16-alarm-2026-11-21` only.

**Version: 1, as sent to review.**

**What it is.** The owner accepted the NO-GO of the design gate (`verify/DESIGN_GATE_AMEND16_2026-11-21.md`, commit
`f1aa677`) and decided seven points on 21 November. This document restates the design as numbered rules that an
implementer and a test author could work from, with those decisions applied. Every rule has an identifier. The words
MUST, MUST NOT and MAY are used strictly. Where a rule rests on evidence, the evidence is named; where it rests on
nothing yet, it says so.

**How it is to be checked.** By separate AI agents instructed by the author: one reviews this text; one writes a
bounded model or exhaustive state-machine test of sections 6 to 8 from this text; one writes adversarial acceptance
tests from this text before any implementation. By the white paper's rule (revision 16, section 3, "Inspection is not
reproduction" and "Implemented, internally tested, independently validated") these are **internal review** and
**separately authored verification**. They are not independent validation, and agreement between a model and this
text is not evidence about any implementation.

**Baselines, unchanged.** The threat model: `verify/AMEND16_THREAT_MODEL_ADDENDUM_2026-11-21.md` at `0da1a85e` on
`verification-amendment-16`. The property file: `verify/AMEND16_PROPERTY_2026-11-20.md`. The Step 2 note at `1fcc227`,
its erratum, and the design gate at `f1aa677` are superseded by this document where they differ and are left as
written. `e25a297` stays INCOMPLETE, failed at internal review and undeclared, with its findings. The earlier model
results and counterexamples are preserved as they are.

## 1. Parties, capabilities and what a test can establish

### 1.1 Parties

| Party | Key | Trusted for |
|---|---|---|
| Gate host | the gate's signing key | signing a report only for a run the witness accepted, once |
| Witness | the witness's key | its chain: one consistent chain per budget; its checkpoint; its answers for a run |
| Courier | the courier's key | reading the witness truthfully and signing only what it read (the engineer's) |
| Mailbox | the mailbox's key | holding what it receipts; its own time (the engineer's) |
| Service | none of the above, by the contract | nothing |

### 1.2 Capabilities of an adversary, kept apart

Every attack, test and finding in this document names the least capability it needs.

| Capability | What it is | Standing in the contract |
|---|---|---|
| **CAP-DB** | the database role `plea_local`, the service's client certificate, the front door, and every report an honest gate host has signed. **It holds no gate signing key.** It may replay any genuine report anywhere | the service's own power; always assumed |
| **CAP-KEY** | CAP-DB and the gate's signing key | the property file takes the service to hold it ("The service is taken to hold the gate's key", `verify/AMEND16_PROPERTY_2026-11-20.md`, line 21). Blocker B-3 |
| **CAP-OS** | CAP-DB and the power to signal, stop, read or write another party's process, keys or files | excluded by precondition DP2; not excluded in the demonstration (B-2) |
| **CAP-OWNER** | CAP-DB and any other database role, the owner's above all | excluded by precondition DP1; not excluded in the demonstration (B-1) |

**K-CAP-1.** A test that signs anything with the gate's key is a CAP-KEY test and MUST be labelled so. A CAP-DB test
MUST NOT have the gate's key within its reach: it uses only reports that an unchanged gate host produced for real
runs.

**What S-1 and S-5 need (by test, 21 November, `tests/diag_amend16_gate/gate_s5_capability.py`).**

| Attempt | Capability | Result at `e25a297` |
|---|---|---|
| A genuine PASS report of another attempt of the same budget, replayed onto a run whose gate host signed FAIL, with RECONCILE or RELEASE, before or after the run's START; the other run's PASS result then stored | CAP-DB | The report is kept and is **not counted** for the run (it names another run and nonce; label WRONG_BINDING or NONE). The run reads UNVERIFIED, never PASS. The courier makes an UNVERIFIED notice |
| The same with a genuine PASS report of another budget | CAP-DB | the same |
| An attempt made in another budget with the run name and nonce of a genuine PASS report, and that report sent to it | CAP-DB | not counted (it names another budget); the run reads NO_OUTCOME |
| The honest gate host asked again for the failing run | CAP-DB | the same report, byte for byte; recorded as a repeat |
| The honest gate host asked to run a passing design under the failing run's name, nonce or receipts | CAP-DB | refused three ways (the nonce does not bind; the witness did not accept that nonce; the receipt is for another attempt) |
| A report signed with the gate's key over a forged PASS result for the failing run itself; the forged result stored | **CAP-KEY** | **believed: the run reads PASS and the courier makes no notice** (S-5; S-1 the same) |

**So S-1 and S-5, as demonstrated, need CAP-KEY.** With CAP-DB alone no replay made a failing run read PASS. What
CAP-DB can do is withhold the result, so that the engineer is told UNVERIFIED and not FAIL. Not shown and not claimed:
that no CAP-DB path exists. One is known that needs more than CAP-DB: an honest gate host that loses its state
(CAP-OS) can run a check twice over inputs that changed and sign two results.

### 1.3 Preconditions and blockers, cited

From the baseline at `0da1a85e`, section 3:

> **DP1. No database-owner credential is accessible to the service.** Nor the witness's role, nor the control plane's.
> The service holds `plea_local` and nothing else.
>
> **DP2. The service and the witness run under separate operating-system identities.** Neither can signal, stop, read
> or write the other's process, keys or files. By A1 and A2 (section 4) the same is needed of the courier and of the
> mailbox.

From `verify/DEFECT_REGISTER.md` (draft), Part C, at `f1aa677`:

> By the owner's decision of 21 November these must be resolved before any claim that a deployment complies.
>
> | B-1. Database credentials exposed (S-2) | every role's password is in the repository | `roles.txt`; V7 |
> | B-2. No separation of operating-system accounts | one account runs the witness, the gate host, the mailbox, the courier and the client; that account stopped and continued the witness | `verify/deploy.py` 11-16; step 6b of `commit_check.py` |

**ACC-1.** B-1 and B-2 are mandatory security-acceptance blockers. Credential custody (DP1), separation of
operating-system accounts (DP2) and the trust boundaries that fail without them MUST be resolved before any claim
that a deployment complies with this specification.

**ACC-2.** No test run on a single host, or on any deployment where DP1 or DP2 does not hold, establishes acceptance
of the production contract. Such a test is diagnostic evidence about the code's behaviour and MUST be reported as
that. This holds for every test named in this document and for the acceptance tests written from it.

**ACC-3.** Diagnostic modelling and testing MAY continue without those changes.

**ACC-4.** B-3 (custody of the gate's key) is not resolved by anything here. While the service holds the gate's key
(CAP-KEY), a forgery made before the witness sees anything is not detected by any rule of this document (N-3).

## 2. Definitions

- **D-1. Canonical form.** `canonical(x)` is `check_record.canonical`. `H(x)` is the SHA-256 of `canonical(x)` in
  lower-case hexadecimal. `Hb(bytes)` is the SHA-256 of the bytes.
- **D-2. Report.** An object the witness returns as evidence for a run. Its **evidence id** is `H(report)`: the same
  report gives the same id wherever it is read.
- **D-3. Gate-signed for a run.** A report is gate-signed for run a of budget B when its kind is `EFFECT_REPORT` or
  `FENCE_REPORT`, its signer is one of the gate keys given, its signature verifies over its signed fields, its `root`
  is B and its `aid` is a. Anything else returned as evidence is a **stray**. A genuine report of another run or
  budget is a stray for this run.
- **D-4. Chain nonce.** The nonce the chain's state at the checkpoint records for the run, or null.
- **D-5. In scope.** A gate-signed effect report is in scope when the chain nonce is not null and the report's nonce
  equals it. A gate-signed effect report for the run that is not in scope is a **foreign-nonce report**.
- **D-6. Claim and pair.** An in-scope report claims EFFECT, NO_EFFECT or UNKNOWN. A **verdict report** claims EFFECT or
  NO_EFFECT. Its **pair** is (claim, result digest), compared as strings. Two reports with one pair are one result,
  whatever their bytes or signatures. The **pair id** is `H([claim, result digest])`.
- **D-7. Well-formed digest.** 64 lower-case hexadecimal characters.
- **D-8. Three meanings of UNKNOWN.** (a) the gate's claim UNKNOWN; (b) the check's own verdict UNKNOWN inside the
  result an EFFECT report signs, which is final; (c) the stored marker `'outcome': 'unknown'`, chosen by the service
  and signed by nobody. "An UNKNOWN report" is (a). (c) is never evidence.
- **D-9. Phases.** *Before consumption*: RESERVING, RESERVED, TOKEN, INTENT_PENDING. *Of consumption*: CONSUMED,
  EFFECT, NO_EFFECT, INDETERMINATE. *Ended without consumption*: RELEASED, DISCARDED.
- **D-10. Recorded verdict.** A decision of the chain for the run with operation `['RECONCILE', a, v, 'AUTHORISED']`,
  kind APPLIED and code VERDICT_RECORDED. The report at its number is the **recorded report**.
- **D-11. Label.** The last operand of a RELEASE or RECONCILE decision: AUTHORISED, WRONG_BINDING, BOUND_FENCE or
  NONE. By test, a decision whose label is not NONE always has a report row; one labelled NONE may have one or none.

## 3. The consistency rule

Applied by the courier to what the witness gives for a run at a checkpoint N, and by the record's checker to what a
record carries. Reports recorded after N are left out.

### 3.1 The count rule

- **K-CNT-1.** Every RELEASE or RECONCILE decision for the run, up to N, whose label is not NONE MUST have a report at
  its number.
- **K-CNT-2.** Every report MUST sit at the number of a RELEASE or RECONCILE decision for the run.
- **K-CNT-3.** The run MUST have at most one recorded verdict; if its phase is EFFECT or NO_EFFECT it MUST have
  exactly one, whose operand v is the phase; and the recorded report MUST be in scope and claim v.
- **K-CNT-4.** If the label of a decision is AUTHORISED, the report at its number MUST be gate-signed for the run
  under the reader's gate keys. If not, the reader's keys are not the witness's.
- **K-CNT-5.** If any of K-CNT-1 to 4 fails, the finding is **K-MISSING**: the answer is not whole against the chain.

### 3.2 The findings

Let V be the set of distinct pairs among the in-scope verdict reports; U true when an in-scope UNKNOWN report exists;
F true when a gate-signed fence report for the run exists; X true when a foreign-nonce report exists. All findings
that hold are reported together.

| Id | Finding | Holds when | Meaning, and no more than this |
|---|---|---|---|
| K-CONFLICT | conflicting verdicts | V has two or more members, at any decisions, of any kind or operation, with or without a recorded verdict | the gate's key signed two different results, or two different verdicts, for one run |
| K-UNKNOWN-VERDICT | a verdict beside UNKNOWN | U, and V is not empty, in any order | the gate's key signed UNKNOWN and a verdict for one run; no rule permits it |
| K-FENCE | an effect report beside a fence | F, and any gate-signed effect report for the run exists (in scope or not, any claim) | the gate's key signed that the run never started and that it had an effect |
| K-PHASE | an effect report for a run that ended without consumption | the phase is RELEASED or DISCARDED, and any gate-signed effect report for the run exists | as K-FENCE |
| K-NONCE | a foreign-nonce report | X | the gate's key signed an effect for this run under a nonce the chain does not record |
| K-DIGEST | a malformed digest | an in-scope verdict report whose digest is not well-formed | the gate's key signed a digest no honest gate host signs |
| K-MISSING | the answer is not whole | K-CNT-5 | the reading, or the record, lacks a report the chain says exists, or holds one the chain does not place |

- **K-1. Set, not sequence.** No finding and no verdict depends on the order of reports. An implementation MUST NOT
  take "the latest report" as anything.
- **K-2. Pair, not bytes.** K-CONFLICT compares pairs. A report signed again with other bytes is not a conflict.
- **K-3. Every key.** A report is gate-signed if it verifies under any gate key given. The courier and the record's
  checker MUST use the same rule. **Precondition P-KEYS:** the reader's gate keys are the witness's pinned set; the
  reader cannot read that set from the witness and the engineer MUST configure it. K-CNT-4 detects a difference for
  authorised decisions only.
- **K-4. Every phase.** The reports of a run MUST be read whatever its phase.
- **K-5. UNKNOWN beside a verdict is forbidden** (the owner's decision). An honest gate signing UNKNOWN does not
  establish that a later verdict is safe to accept, and in the shipped deployment the honest sequence cannot arise.
  UNKNOWN reports alone (no verdict) are permitted and the run is INTERRUPTED as today.
- **K-6. No supersession.** No verdict replaces another by any path.

### 3.3 Belief

- **K-BEL-1.** A stored result is believed if and only if all of these hold: the run's phase is EFFECT; no finding of
  3.2 holds for the run; the recorded report claims EFFECT and its digest is well-formed; and the stored result is a
  value whose `H` equals that digest.
- **K-BEL-2.** A report at any decision other than the recorded verdict is never the basis of belief. It can only add
  a finding.
- **K-BEL-3.** A run with verdict reports and no recorded verdict has no verdict. It is not final.
- **K-BEL-4.** The stored marker of D-8 (c) is never the basis of any outcome that says the gate reported anything.

### 3.4 What each standing calls for

| The run | Outcome | Notice called for |
|---|---|---|
| any finding of 3.2 except K-MISSING | INCONSISTENT | one EQUIVOCATION notice naming every finding that holds (5.3), and no notice that states a verdict |
| K-MISSING | NOT OBSERVED | none for the run; the reading is incomplete (4.6) |
| believed, by K-BEL-1 | the result's own verdict, as today (PASS, FAIL, UNKNOWN in meaning (b), INVALID) | as today |
| phase EFFECT, no finding, not believed | UNVERIFIED | as today, after the waiting time |
| phase NO_EFFECT, no finding | REFUNDED | as today |
| phase CONSUMED, U, V empty | INTERRUPTED | as today |
| other phases, no finding | as today | as today |

- **K-N-1.** What a notice is called for is decided from what the witness gives in this reading, never from what the
  courier remembers having sent.
- **K-N-2.** An EQUIVOCATION notice says only what the "meaning" column says. It MUST NOT say which report is true,
  that the run failed or passed, that a verdict was changed, or who signed.

### 3.5 The record's checker

- **K-REC-1.** A record fails verification if any finding of 3.2 holds for any of its runs, K-MISSING included, by the
  same rules applied to the reports the record carries.
- **K-REC-2.** A record is signed by the engineer's key; a report taken out of it afterwards fails its signature (by
  the reviewer's test P1).
- **K-REC-3.** Limit: a report that sat at a decision labelled NONE can be absent from a record without K-MISSING
  (L-1).

### 3.6 Which capability can produce each finding

| Finding | CAP-DB | CAP-KEY | An honest fault |
|---|---|---|---|
| K-CONFLICT | not produced by any replay tested (1.2) | yes (S-1, S-5) | yes, with a gate host that loses its state |
| K-UNKNOWN-VERDICT | not tested | yes | only in an arrangement with a second gate host; not in the shipped deployment |
| K-FENCE, K-PHASE, K-NONCE, K-DIGEST | not tested; each needs a report the honest gate host does not sign | yes (the reviewer's P2, P5) | none known |
| K-MISSING | no (no granted role can remove a report, by test) | no | CAP-OWNER; or keys that differ |
| a stray | yes, at will | yes | no |

A stray is never a finding and never calls for a notice: otherwise CAP-DB could make notices at will. Strays are
counted in the observation record (4.5).

## 4. The observation: one reading

### 4.1 Order

- **O-1.** The courier takes a challenge from the mailbox for the budget (7.2) before it asks the witness anything.
- **O-2.** It asks the witness for a checkpoint with the token as nonce and its cursor's decision as `at`
  (`GET /checkpoint?root=B&nonce=TOKEN&at=K`). It MUST check the signed fields: the witness's key, `root` = B,
  `nonce` = the token, `at` = K, and `head_at` = the head it holds for K. For K = 0, `head_at` is the budget's
  provisioning hash.
- **O-3.** "at is beyond the chain" is a ROLLBACK. A different `head_at` is a FORK. Either ends the reading with an
  alarm (4.6) and no statement.
- **O-4.** It reads the decisions after K to the checkpoint's N and recomputes each hash from the one before; the last
  MUST equal the checkpoint's head. A decision left out fails here.
- **O-5.** It reads runs (4.2), applies section 3 to each, and makes the items called for (5).
- **O-6.** It makes a statement (5.5) only if the reading is whole (4.6).

### 4.2 Which runs are read

- **O-R-1. Named.** Every run named by any decision in (K, N], of any operation.
- **O-R-2. Unsettled.** Every run that is not settled (4.3).
- **O-R-3. Kinds of reading.** FROM_ZERO: K = 0 and every run of the budget is read. REFRESH: K is the cursor and every
  run of the budget is read. INCREMENTAL: K is the cursor and the runs of O-R-1 and O-R-2 are read; every other run is
  **carried** (4.4).

### 4.3 Settled

| Phase | Settled when |
|---|---|
| EFFECT | believed (K-BEL-1) |
| NO_EFFECT | no finding, and the recorded report claims NO_EFFECT |
| RELEASED, DISCARDED | no finding |
| INDETERMINATE | no finding (it has no verdict; it is frozen by the control plane) |
| any other, or any run with a finding | never |

- **O-S-1.** A run with a finding is never settled: it is read at every reading, and its EQUIVOCATION notice is made
  again only when the set of findings or of evidence ids changes (5.2).

### 4.4 Carried runs: an assumption, stated

- **O-C-1.** A settled run MAY be carried without being read only on **assumption A-CARRY**: that the run's reports
  and stored result are unchanged since it was last read, unless a decision of the chain names it. What supports it:
  a report enters the store only with a decision naming its run (code; 3,456 rows read with the service's own role);
  a stored value cannot be replaced or removed by `plea_local` (by test). What does not: any role but `plea_local`
  (DP1, B-1); the reports' resistance to the witness's and the control plane's roles rests on the author's earlier
  tests only.
- **O-C-2.** A run that was final is **not** taken to be immutable. A late report at any decision, a RELEASE included,
  names the run in the chain and brings it back under O-R-1.
- **O-C-3. Bounded.** A carried observation MUST have been made in a reading of the same chain epoch (5.4) and the same
  mailbox epoch (7.1), under a statement the mailbox accepted, no longer ago than the **refresh bound R** by the
  mailbox's time. The statement names the oldest such statement (5.5); the mailbox enforces the bound (7.4). With
  R = L every reading reads every run.
- **O-C-4.** After a restart of the mailbox, or a new chain epoch, nothing is carried.

### 4.5 The observation record

- **O-P-1.** For each run read in a reading, the courier makes a record: the run; N; its phase; its outcome (3.4); the
  findings; the pair id of its recorded report, or null; the number of reports, of strays, and one digest over the
  evidence ids of all of them in the order of their decisions; whether its stored result was present. Records go in
  OBSERVATION_PART items of bounded size.

### 4.6 A reading that is not whole

A reading is **whole** only if: O-2 to O-4 passed; every run of 4.2 was read; no run has K-MISSING; every answer was
within the courier's limits (4.7); every item called for was accepted by the mailbox; and every piece of evidence a
finding rests on is held by the mailbox (6).

- **O-W-1.** If a reading is not whole the courier MUST NOT make a statement. It MUST make an
  **OBSERVATION_INCOMPLETE** alarm item (5.3) naming the reason and, where there is one, the run. It MUST still
  deliver every notice the reading called for from the runs it did read.
- **O-W-2.** Reasons: ROLLBACK, FORK, CHAIN_BROKEN, WITNESS_UNREACHABLE, DEADLINE (the reading could not end within L),
  RUN_OVERSIZE, RUN_UNREADABLE, K_MISSING, EVIDENCE_NOT_HELD, MAILBOX_REFUSED.

### 4.7 Limits on what the courier reads

- **O-L-1.** The courier reads at most RUN_ANSWER_MAX bytes of one run's answer. An answer that is larger makes that
  run RUN_OVERSIZE: an UNREADABLE notice for the run, and the reading is not whole.
- **O-L-2.** The service chooses the size of a run's answer (S-6: 70,448 and 200,435 bytes for one report; 5,002,287
  bytes for one run, by test). It can therefore make any reading slow or not whole, and keep a budget NOT COVERED.
  This is a loss of liveness. It MUST surface as NOT COVERED with an alarm (8.2), never as a statement that leaves
  the run out.

## 5. Items, identities and chain epochs

### 5.1 The item

- **I-1.** Everything the courier sends for a budget is an **item** of form 3, at most ITEM_MAX bytes: `statement`
  ("ITEM"), `form` (3), `kind`, `root` (the budget), `chain_epoch`, `k`, `prev`, `identity`, `body`, `time` (the
  courier's wall clock, for people only), `courier`, `signer`, `signature`. The courier's signature covers every
  field but `signer` and `signature`.
- **I-2.** Every field is bounded. A value the service can make large (a nonce, a digest that is not well-formed) is
  carried as its SHA-256 and its length, never whole. An item can therefore always be delivered.
- **I-3.** `A(0) = H(["PLEA-A16-CHAIN", root, chain_epoch])`. `A(k) = H(["PLEA-A16-ITEM", A(k−1), identity_k])`.
  An item's `prev` is A(k−1).
- **I-4.** One courier key per budget. The mailbox refuses an item for a budget from a second courier key.

### 5.2 Deterministic identity

- **I-ID-1.** For a notice about a run, `identity = H(["PLEA-A16-ID", root, kind, run, basis])`, where the basis is
  computed from the witness's data only:

| Kind | Basis |
|---|---|
| outcome notice (FAIL, UNKNOWN, INVALID, UNVERIFIED, INTERRUPTED, NO_OUTCOME, REFUNDED, INDETERMINATE, UNREADABLE) | the outcome; the number of the recorded verdict's decision, or null; the pair id of the recorded report, or null |
| EQUIVOCATION | the sorted findings; the sorted evidence ids of every gate-signed report of the run |

- **I-ID-2.** For OBSERVATION_INCOMPLETE: `identity = H(["PLEA-A16-ID", root, kind, reason, run or null])`.
- **I-ID-3.** For every other kind (EPOCH_OPEN, OBSERVATION_PART, COVERAGE): `identity = H(["PLEA-A16-ID", root, kind,
  chain_epoch, body])`. These are never deduplicated.
- **I-ID-4.** An identity never depends on the time, on k, on the chain epoch (for I-ID-1 and I-ID-2), or on anything
  the courier remembers.

### 5.3 Kinds

| Kind | Body (beyond what identity needs) |
|---|---|
| a notice of an outcome | as the form 2 notice today, with the provenance sentence that applies |
| EQUIVOCATION | the run; the nonce's SHA-256 and length; N and head; the findings; for each of at most two reports per finding (the earliest by decision of each differing kind; for K-CONFLICT the recorded report if there is one, and the earliest whose pair differs): its decision, that decision's operation, kind, code and label, its claim, its digest or the digest's SHA-256 and length, its signer, its size, its evidence id, and where it is held (6.4); the count of reports, of pairs, of strays; the digest of O-P-1 |
| OBSERVATION_INCOMPLETE | the reason; the run, if any; N if a checkpoint was had; sizes, if size is the reason |
| OBSERVATION_PART | the token; N; records of O-P-1; part i of n |
| EPOCH_OPEN | 5.4 |
| COVERAGE (the statement) | 5.5 |

### 5.4 Chain epochs, and a courier that has lost its state

A **chain epoch** is one unbroken life of a courier's state for a budget: its cursor, its unsettled set, its record of
carried observations, its position k and A(k), and its continuity secret.

- **I-E-1. Opening.** The first item of a chain epoch (k = 1) is EPOCH_OPEN: a new random `chain_epoch`; `reason`, one
  of FIRST or COURIER_STATE_LOST; and `commit = Hb(s_1)` for a secret s_1 of 32 random bytes that the courier has
  written durably first.
- **I-E-2. The mailbox, on EPOCH_OPEN.** It closes the budget's current chain epoch, if any, recording why; it keeps
  every item, receipt and piece of evidence of every earlier epoch; it starts the new chain at A(0); and the budget is
  NOT COVERED (EPOCH_OPENED) until a FROM_ZERO statement of the new epoch is accepted. Its status shows how many chain
  epochs the budget has had, and the reason each was opened.
- **I-E-3. Fail closed.** A courier that finds its state for a budget absent, unreadable, or not continuing the
  mailbox's head (a refusal by I-E-6 or M-D-3) has lost its state. It MUST NOT take its cursor, its position, its
  settled runs or anything else from the mailbox or from an old copy. It MUST open a new chain epoch with reason
  COURIER_STATE_LOST and read from decision 0.
- **I-E-4. From sequence 0.** The first statement of a chain epoch MUST be FROM_ZERO: its checkpoint's signed `at` is
  0, every run of the budget was read in its reading, none is carried, and every notice that reading called for is an
  item of the new epoch's chain.
- **I-E-5. No duplicate, none missing.** When an item's identity is already held for the budget (from any chain
  epoch), the mailbox does not keep a second copy for the engineer. It records (k, identity, the first item's digest)
  in the new chain's index and answers with **the first receipt**, unchanged, and a signed LINKED acknowledgement.
  A notice the lost courier had made and not delivered is made again by the reading from 0 and is delivered now. A
  notice of an earlier epoch that the new reading does not call for stays held, as history.
- **I-E-6. Continuity is authenticated.** Statement j of a chain epoch carries `reveal = s_j` and
  `commit = Hb(s_{j+1})`, with s_{j+1} written durably before the statement is sent. The mailbox accepts the statement
  only if `Hb(reveal)` equals the commit it holds (from EPOCH_OPEN for j = 1, else from statement j−1). A courier
  without its state, or with an old copy of it, cannot produce `reveal`: it cannot make a statement, and so cannot
  claim COVERED, until it has opened a new epoch and read from 0.
- **I-E-7.** The mailbox cannot check that a reading was from decision 0 beyond the checkpoint's signed `at` and the
  statement's counts. That the courier read every run is the courier's signed word.

### 5.5 The statement of coverage

- **I-S-1.** A statement is an item of kind COVERAGE. It is delivered after every item it commits to: the mailbox
  takes only the next item of a chain (7.3).
- **I-S-2.** Its body: the challenge whole; the checkpoint whole; `reading` (FROM_ZERO, REFRESH or INCREMENTAL);
  `at` and `head_at` as the checkpoint signs them; N and head; `prev_statement` (the digest of the last statement the
  courier had accepted in this chain epoch, or null); `reveal` and `commit` (I-E-6); the counts: runs of the budget,
  read, carried, unsettled; `oldest_carried` (the digest of the accepted statement whose reading made the oldest
  observation still carried, or null); and the limits it was made under (L, R, RUN_ANSWER_MAX).
- **I-S-3.** The statement's own `prev` (A(k−1)) is its commitment to every item before it.

## 6. The mailbox's evidence store

### 6.1 Objects

- **E-1.** A piece of evidence is a sequence of bytes. Its **id** is `Hb(bytes)`. For a report the bytes are
  `canonical(report)` in UTF-8, so its id is the report's evidence id (D-2).
- **E-2. Immutable.** Stored under its id, written whole and synced before any answer, never overwritten, never
  removed while any held item names it. Storing an id already held changes nothing and answers as before.
- **E-3. Hard limit.** One object is at most OBJ_MAX bytes. A larger one is refused (413) and nothing is kept.

### 6.2 Quotas and retention

- **E-Q-1.** Evidence held for one budget is at most EVID_BUDGET_QUOTA bytes; for the mailbox, EVID_GLOBAL_QUOTA.
  An object is charged to each budget that stored it.
- **E-Q-2.** Items are not charged to the evidence quotas. Each budget has ITEM_QUOTA bytes for items, of which
  ALARM_RESERVE bytes are kept for OBSERVATION_INCOMPLETE and EQUIVOCATION items and can be used by nothing else.
- **E-Q-3.** A store that would exceed a quota is refused (507) and nothing is kept.
- **E-Q-4. Retention.** An object named by a held item is kept for as long as the item is. An object named by no held
  item after T_ORPHAN is removed and its bytes returned to the quota. Nothing in the protocol removes a named object.

### 6.3 Reading evidence back

- **E-R-1.** `GET /evidence?root=B&id=…` gives the bytes to an admitted reader. The reader MUST recompute `Hb` and
  compare with the id; for a report it MUST then apply D-3. Bytes that do not match the id are treated as absent.

### 6.4 Binding, and failing closed

- **E-B-1.** An EQUIVOCATION notice binds each report it rests on by its evidence id and size, and says for each where
  it is: `INLINE` (whole, in the notice; only when each such report is at most REPORT_INLINE_MAX), `HELD` (in the
  evidence store), or `NOT_HELD` with a reason (OVERSIZE, QUOTA, UNAVAILABLE).
- **E-B-2.** The mailbox refuses (409) a notice that says HELD for an id it does not hold.
- **E-B-3.** The mailbox takes a notice that says NOT_HELD, and records an **evidence gap** for (budget, identity).
  The gap is closed only by a later item of the same identity that says INLINE or HELD for every report, which the
  mailbox verifies.
- **E-B-4. Fail closed.** While a budget has an evidence gap it is NOT COVERED (EVIDENCE_GAP), whatever statements it
  holds, and its status names the gap. Missing, altered, oversized or unavailable evidence never turns a finding into
  no finding: a reader who cannot obtain a report matching its id treats the finding as standing and its evidence as
  incomplete.
- **E-B-5.** The courier also keeps each report a finding rests on in its own durable state, up to RUN_ANSWER_MAX.

### 6.5 Exhaustion by a dishonest service

- **E-X-1.** A service with CAP-KEY can sign reports of any size and number; a service with CAP-DB can add strays of
  any size to any run. Either can fill EVID_BUDGET_QUOTA, exceed OBJ_MAX or RUN_ANSWER_MAX, or make a reading miss L.
- **E-X-2.** In every such case the outcome MUST be: the notices of other runs are still delivered; the budget is
  NOT COVERED with a reason (EVIDENCE_GAP or OBSERVATION_INCOMPLETE); and an alarm item is held, within
  ALARM_RESERVE, that names the reason. It MUST NOT be a statement that leaves the run out, a notice dropped without
  trace, or a status that says COVERED.
- **E-X-3.** If even ALARM_RESERVE is spent, the mailbox refuses further items (507), the courier can make no
  statement, and the budget becomes NOT COVERED by the clock (EXPIRED). The status MUST say that items were refused
  for want of room (ITEMS_REFUSED).
- **E-X-4.** Strays are not stored as evidence. They are counted and committed to in the observation record only.

## 7. The mailbox: time, tokens and statements

### 7.1 Time and epochs

- **M-T-1.** Elapsed time is `time.clock_gettime_ns(time.CLOCK_BOOTTIME)`. `time.monotonic()` MUST NOT be used: on the
  deployment host it is `CLOCK_MONOTONIC`, which does not count suspension, and under-counting an age is a failure of
  safety.
- **M-T-2. Mailbox epoch.** Made at each start of the mailbox: the machine's boot identifier
  (`/proc/sys/kernel/random/boot_id`) and 16 random bytes, written durably before anything is answered. A tick is
  meaningful only inside the epoch that took it. A tick of another epoch, or of another boot identifier, MUST NOT be
  compared with the present clock.
- **M-T-3.** After a reboot `CLOCK_BOOTTIME` begins again near zero. Because every start makes a new epoch and no tick
  crosses epochs, no age can be computed across a reboot: every token of before is VOID and every budget is
  NOT COVERED (MAILBOX_RESTARTED).
- **M-T-4. The wall clock** is written beside what the mailbox signs, for people. No decision uses it alone.
- **M-T-5. Larger age.** When the mailbox works out an age it also takes the wall clock's movement over the same
  interval. If the wall clock went backwards, or the two differ by more than CLOCK_TOLERANCE, it records a clock
  anomaly durably, shows it in every status until the operator clears it, and uses the larger of the two ages.
- **M-T-6.** The mailbox takes no time from the courier, the witness, an item or a checkpoint.
- **M-T-7. Limit.** A pause of the whole machine from outside it (a hypervisor) may move no clock inside it. Then only
  a corrected wall clock shows the gap (M-T-5); if nothing corrects it, nothing inside the machine can see the pause.

### 7.2 Tokens

- **M-K-1. Issue.** `POST /challenge {root}` from the budget's courier key. The mailbox makes 32 bytes from the
  operating system's source of randomness, written as 43 characters of URL-safe base64 without padding; writes
  durably the token, the mailbox epoch, a serial number, the budget, the courier's key, L, R and the tick; and only
  then returns the challenge, signed.
- **M-K-2. Bounded.** At most TOKENS_MAX tokens are ISSUED for one budget. Issuing another makes the oldest VOID.
- **M-K-3. States.** ISSUED, USED, SPENT, EXPIRED, VOID. Only ISSUED can change, except by M-K-6.
- **M-K-4. Expiry.** A token whose age is more than L is EXPIRED, whatever its state was: coverage that rested on it
  has ended.
- **M-K-5. Restart.** At a start of the mailbox every token of an earlier epoch is VOID.
- **M-K-6.** USED and SPENT are written durably before the mailbox answers the statement.

### 7.3 Taking an item: strict order

For every item delivered, in this order. A failure at one step ends the handling; the later steps are not reached.

| Step | Check | On failure |
|---|---|---|
| DL-1 | It is at most ITEM_MAX bytes, of form 3, of a kind known, signed by the budget's courier key | 400 or 403; nothing kept |
| DL-2 | If its identity is of I-ID-1 or I-ID-2 and is already held for the budget: link it (I-E-5) | — (answered with the first receipt) |
| DL-3 | It is an EPOCH_OPEN (then I-E-2), or its `chain_epoch` is the budget's open epoch, its k is the head's k + 1 and its `prev` is the head's A | 409 CHAIN_POSITION, with the mailbox's signed head; nothing kept; **no token is touched** |
| DL-4 | Every evidence id it says is HELD is held (E-B-2); there is room (E-Q-2, E-Q-3) | 409 EVIDENCE_MISSING or 507; nothing kept; **no token is touched** |
| DL-5 | If it is not a COVERAGE item: write it, the index entry and the new head durably, then answer with a receipt | — |
| DL-6 | If it is a COVERAGE item: the statement checks of 7.4 | as 7.4 |

- **M-D-1.** A statement that arrives before an item it commits to fails at DL-3 and is refused. Its token stays
  ISSUED. The courier delivers the items and sends the statement again. A token is never spent by the order of
  delivery.
- **M-D-2.** Evidence and every item a statement commits to are therefore durably stored and verified before any step
  that can use or spend a token.
- **M-D-3.** A courier refused at DL-3 whose own position is not the head it is shown has lost its state (I-E-3).

### 7.4 Statement checks

Reached only after DL-1 to DL-4. All are evaluated; if all pass the token becomes USED; if any fails the token, if it
was ISSUED and named by a statement signed by its own courier key, becomes SPENT, and the statement is kept as
evidence with the reason (422).

| Id | Check |
|---|---|
| ST-1 | the challenge is this mailbox's own (its signature), of the current mailbox epoch, for this budget and this courier key |
| ST-2 | the token is ISSUED |
| ST-3 | the token's age is at most L (M-T-5) |
| ST-4 | the checkpoint verifies under a witness key the mailbox was given; its `root` is the budget; its `nonce` is the token; its `seq` and `head` are the statement's N and head |
| ST-5 | continuity of the chain epoch: `Hb(reveal)` is the commit held (I-E-6) |
| ST-6 | continuity of the cursor: for the first statement of a chain epoch, `reading` is FROM_ZERO and the checkpoint's `at` is 0; otherwise the checkpoint's `at` and `head_at` are the N and head of the last statement accepted in this chain epoch, and `prev_statement` is its digest |
| ST-7 | kind of reading: for FROM_ZERO and REFRESH, carried is 0. The first statement accepted in a mailbox epoch is FROM_ZERO or REFRESH. For INCREMENTAL, `oldest_carried` names a statement accepted in this chain epoch and this mailbox epoch whose token's age is at most R |
| ST-8 | N is not lower than the last accepted N |
| ST-9 | the limits in the statement are the mailbox's own |

- **M-S-1.** The same statement delivered again (the same digest) is answered with its first receipt and counts
  nothing afresh.
- **M-S-2.** A statement naming a token that is not ISSUED (USED, SPENT, EXPIRED, VOID, or unknown) is kept as
  evidence and counts nothing.
- **M-S-3.** The mailbox does not check that the observation is true. It checks bindings, holdings, order and time.

## 8. COVERED and NOT COVERED

### 8.1 The definition

**C-1.** At the mailbox's time t, budget B is **COVERED to N** if and only if all of these hold:

1. the mailbox holds a statement S for B that passed 7.4, in the current mailbox epoch and the budget's open chain
   epoch, and S is the last such;
2. the token of S is USED and its age at t is at most L;
3. B has no evidence gap (E-B-4);
4. no OBSERVATION_INCOMPLETE item for B has been accepted after S;
5. the mailbox can read its own record of B.

Otherwise B is **NOT COVERED**.

**C-2. What COVERED to N claims, and nothing more.** That the courier holding the budget's courier key signed all of
the following, and the mailbox verified what 7.3 and 7.4 say it verifies:

- in a reading that began after this mailbox issued a token no more than L ago, the witness signed a checkpoint for B
  at decision N bearing that token;
- the decisions to N hash to that checkpoint's head, continuously from the last accepted statement or from 0;
- every run named by a decision since the last statement, and every unsettled run, was read in that reading and
  judged by section 3;
- every other run was last read in a reading of this chain epoch and mailbox epoch no more than R ago, and no
  decision since names it (A-CARRY);
- every item those observations called for is held by this mailbox, and every piece of evidence a finding rests on
  is held or is in the notice.

**C-3. It is an observation at a boundary, bounded in time. It is not a guarantee.** It does not say: that any
verdict is correct; that no conflicting report will appear after N; that a run that was final will stay as it was;
that every report attached at a decision labelled NONE was returned (L-1); that a carried run's stored result or
reports were not changed by a role other than `plea_local` (B-1); or that the budget will be COVERED at any later
time.

**C-4.** NOT COVERED never says that a run failed.

### 8.2 Reasons for NOT COVERED

The status gives every reason that holds: NEVER (no statement accepted in this chain epoch), EXPIRED (C-1.2),
MAILBOX_RESTARTED, EPOCH_OPENED, STATEMENT_SPENT (the last statement on a token of the budget was SPENT),
EVIDENCE_GAP, OBSERVATION_INCOMPLETE (with the alarm's reason), ITEMS_REFUSED, RECORD_UNREADABLE. CLOCK_ANOMALY is
shown beside any state.

### 8.3 The status

- **C-S-1.** `GET /status?root=B&nonce=R` is answered with a status signed by the mailbox that carries R back, the
  mailbox epoch, the state and reasons, and, where they exist: N and head, the statement's digest, the token's age
  and L, the age of the oldest carried observation and R, the chain epoch, the count of chain epochs and why each was
  opened, k and A(k), the evidence gaps, the alarms held, any clock anomaly, and the wall-clock time for people.
- **C-S-2. The reader's rule.** Only a status that verifies under the mailbox's key and carries the reader's own nonce
  is evidence of COVERED. No such status is NOT COVERED: a mailbox that is down, stalled, cut off or restarted is not
  "still covered".
- **C-S-3.** NOT COVERED is seen without any courier: a mailbox that receives nothing moves a budget to EXPIRED by its
  own clock.

## 9. Safety, liveness, and what is not claimed

| Id | Kind | Statement |
|---|---|---|
| SAF-1 | safety | The mailbox never counts a statement whose token is older than L, was used or spent, or is of another budget, courier key or mailbox epoch |
| SAF-2 | safety | No statement is counted unless every item it commits to, and every piece of evidence those items say is held, was durably stored first |
| SAF-3 | safety | A fresh receipt, a restart, a replay or a late delivery never makes an old observation fresh: age is counted from the issue of the token, inside one mailbox epoch |
| SAF-4 | safety | A courier without the continuity secret of the open chain epoch cannot cause a statement to be counted |
| SAF-5 | safety | After EPOCH_OPEN, a budget is not COVERED until a FROM_ZERO statement of the new epoch is accepted |
| SAF-6 | safety | An item is linked, not stored again, when its identity is held; the first receipt is returned unchanged; no item of an earlier epoch is removed |
| SAF-7 | safety | While a budget has an evidence gap, or an OBSERVATION_INCOMPLETE item newer than its last statement, its status is not COVERED |
| SAF-8 | safety | A status carries the asker's nonce; an old status cannot answer a new question |
| SAF-9 | safety | A run with any finding of 3.2 is never given a verdict, and a record carrying such a run fails |
| N-1 | not claimed | **Liveness.** That a courier runs; that a reading ends within L; that a budget ever becomes COVERED. The service can prevent each (S-3, S-6) |
| N-2 | not claimed | **Notification.** That anybody is told anything by any time. The mailbox sends nothing. NOT COVERED is seen only by one who asks while the mailbox answers. No bound on the time to notification is claimed and the mechanism cannot give one. What is bounded: a COVERED status rests on a checkpoint read no more than L before, and on observations no more than R old |
| N-3 | not claimed | **Correctness of a verdict.** One consistent report is not evidence that it is correct. With CAP-KEY, a forgery made before the witness sees anything passes every rule here |
| N-4 | not claimed | **Suspension and pause.** `CLOCK_BOOTTIME` is available and cannot be set; its behaviour across a real suspension is untested, and a pause from outside the machine may be invisible (M-T-7) |
| N-5 | not claimed | **Acceptance.** Nothing here, and no test on a deployment where DP1 or DP2 fails, establishes the production contract (ACC-2) |

## 10. Limits that cannot be removed without changing the witness or the store

- L-1. Whether a decision labelled NONE carried a report. The loss of such a report (possible only with CAP-OWNER) is
  not detectable; a late report sent with a RELEASE is always labelled NONE.
- L-2. Which report was recorded at a decision: the chain's hash does not cover the report or its digest. What the
  courier saw is fixed only by the courier's own signed observation record.
- L-3. A stored result is written without a decision of the chain. Worked round by reading unsettled runs at every
  reading and by the refresh bound R; not removed.
- L-4. The cost of the chain: each decision carries the state of every run of its budget (S-4). About 1.0 MB for one
  new run at 1,000 runs; about 0.5 GB over the life of a 1,000-run budget, read at once or a little at a time;
  508,180,089 bytes measured at 996 runs. A REFRESH reading adds one answer for every run. No linear scaling is
  claimed.
- L-5. The size of a report and of a run's answer has no bound short of the database's own (S-6). The cost of
  reading unsettled runs, and of any REFRESH, is the service's to choose.
- L-6. A forgery made before the witness sees anything; one consistent false chain signed by the witness.
- L-7. The witness's answer for a run is unsigned and takes no nonce: an observation of a run is bound to the token
  only by the courier's signature.
- L-8. No reading lists the budgets.
- L-9. A pause of the machine from outside it.

## 11. Interfaces

**The witness, the gateway and the store: no change.**

**The mailbox.**

| Request | From | Answer |
|---|---|---|
| `POST /challenge {root}` | the budget's courier | 200 a signed CHALLENGE: mailbox, mailbox epoch, serial, root, courier key, token, L, R, wall time |
| `POST /deliver` an item | the budget's courier | 200 a signed receipt (or the first receipt and a LINKED acknowledgement); 400, 403, 409 CHAIN_POSITION, 409 EVIDENCE_MISSING, 413, 422 with the failed checks, 507 |
| `POST /evidence?root=B` bytes | the budget's courier | 200 a signed HELD: id, size, root; 413; 507 |
| `GET /evidence?root=B&id=…` | an admitted reader | 200 the bytes; 404 |
| `GET /items?root=B&chain_epoch=E&after=k` | an admitted reader | 200 the items of that chain epoch in the mailbox's order of acceptance, each with its receipt or its link, and the signed head |
| `GET /status?root=B&nonce=R` | an admitted reader | 200 a signed STATUS (C-S-1) |
| `GET /pubkey` | as today | as today |

**Configuration, set by the operator at start and fixed for the mailbox epoch:** the courier key for each budget; the
witness's public keys; L; R; TOKENS_MAX; ITEM_MAX (65,536); OBJ_MAX; EVID_BUDGET_QUOTA; EVID_GLOBAL_QUOTA; ITEM_QUOTA;
ALARM_RESERVE; T_ORPHAN; CLOCK_TOLERANCE. RUN_ANSWER_MAX and REPORT_INLINE_MAX are the courier's, and are named in
each statement.

**Proposed values, for the operator to set before any acceptance testing:** REPORT_INLINE_MAX 16 KiB; OBJ_MAX 1 MiB;
RUN_ANSWER_MAX 8 MiB; EVID_BUDGET_QUOTA 64 MiB; EVID_GLOBAL_QUOTA 1 GiB; ITEM_QUOTA 256 MiB; ALARM_RESERVE 1 MiB;
TOKENS_MAX 8. L and R have no proposed value: a reading from nothing over 996 runs took 98 s on the demonstration
machine, and L below a reading from nothing means a courier that has lost its state can never bring a budget back.

**Durable storage at the mailbox**, each written whole and synced before any answer that depends on it: the mailbox
epoch; challenges and token states; items and receipts; the index of each chain epoch in order of acceptance, with
links; the open chain epoch, its head and its commit; statements, accepted and spent, with reasons; evidence; evidence
gaps; alarms; clock anomalies.

**Earlier forms.** Notices and receipts of forms 1 and 2 MUST go on verifying as they do.

## 12. What must be shown, and by what

| What | By |
|---|---|
| Sections 6 to 8 as a state machine: tokens, epochs of the mailbox across a reboot, the strict order of 7.3 with a statement before its items, statement checks, chain epochs with COURIER_STATE_LOST, linking, evidence gaps, the status | a separately authored bounded model or exhaustive state-machine test, with its bounds stated, mechanisms removed one at a time, and probes that its paths are reachable |
| Every MUST of sections 3 to 8 against an implementation | adversarial acceptance tests written from this text before the implementation, each naming the rule it tests and the capability it uses (K-CAP-1) |
| That an implementation does what the model does | nothing here. Agreement between this text and a model says nothing about code |
| The clock across a real suspension; a hypervisor's pause | cannot be shown on the demonstration machine (N-4) |
| The production contract | only on a deployment where DP1 and DP2 hold (ACC-2) |

## 13. Trace: the owner's decisions of 21 November

| Decision | Rules |
|---|---|
| 1. UNKNOWN beside a verdict forbidden; the rule extended to every authenticated claim; pair identity; the capability S-5 needs | K-5; 3.2 (K-CONFLICT, K-UNKNOWN-VERDICT, K-FENCE, K-PHASE, K-NONCE, K-DIGEST, K-MISSING), K-CNT-3; K-2, D-6; 1.2, K-CAP-1, 3.6 |
| 2. Lost courier state: fail closed, from sequence 0, an authenticated epoch transition, deduplication by identity | I-E-1 to I-E-7; 5.2; SAF-4 to SAF-6 |
| 3. Evidence store, binding, limits and quotas, strict write order, exhaustion | section 6; 7.3 (DL-3, DL-4, M-D-1, M-D-2); E-X-1 to E-X-4; O-W-1 |
| 4. B-1 and B-2 mandatory; no acceptance on a non-compliant deployment | 1.3 (ACC-1 to ACC-4); N-5 |
| 5. COVERED as a time-bounded observation at a boundary; results without decisions; unbound reports; unsettled runs; cursor gaps; large evidence | C-1 to C-4; O-C-1 to O-C-4; 4.3; ST-6, O-3, O-4; 4.7; section 10 |
| 6. Separate agents: review, model, acceptance tests; no escalation; internal review only | "How it is to be checked"; section 12 |
| 7. Branch, stop conditions | the head of this document |
