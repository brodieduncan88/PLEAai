# Amendment 16: specification for a Step 3 (for review; not approved for implementation)

21 November 2026. Private working material. Internal work under the owner's direction. It is a specification only.
Nothing is implemented by it; no code of the courier, the mailbox, the witness, the gateway or any deployment
configuration is changed; it is not a declaration and not an acceptance of anything. It is kept on the branch
`diagnostic-amend16-alarm-2026-11-21` only.

**Version: 4.** Version 1 (commit `1495320`) was reviewed by a separate agent and modelled by another; version 2
(commit `2694b52`) corrected it and was reviewed again; version 3 corrected what the second review found and was
reviewed a third time; version 4 corrects what the third review found. Every
change is listed in section 14 against the finding that caused it.

**What it is.** The owner accepted the NO-GO of the design gate (`verify/DESIGN_GATE_AMEND16_2026-11-21.md`, commit
`f1aa677`) and decided seven points on 21 November. This document restates the design as numbered rules that an
implementer and a test author could work from, with those decisions applied. The words MUST, MUST NOT and MAY are
used strictly. Where a rule rests on evidence, the evidence is named; where it rests on argument or on nothing yet, it
says so.

**How it is checked.** By separate AI agents instructed by the author: one reviews the text; one writes a bounded
model of sections 5 to 8 from the text; one writes adversarial acceptance tests from the text before any
implementation. By the white paper's rule (revision 16, section 3) these are **internal review** and **separately
authored verification**. They are not independent validation, and agreement between a model and this text is not
evidence about any implementation.

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
| **CAP-DB** | the database role `plea_local`, the service's client certificate, the front door, and every report an honest gate host has signed or can be made to sign. **It holds no gate signing key.** It may replay any genuine report anywhere, with anything added to it | the service's own power; always assumed |
| **CAP-KEY** | CAP-DB and the gate's signing key | the property file takes the service to hold it ("The service is taken to hold the gate's key", `verify/AMEND16_PROPERTY_2026-11-20.md`, line 21). Blocker B-3 |
| **CAP-OS** | CAP-DB and the power to signal, stop, read or write another party's process, keys or files | excluded by precondition DP2; not excluded in the demonstration (B-2) |
| **CAP-OWNER** | CAP-DB and any other database role, the owner's above all | excluded by precondition DP1; not excluded in the demonstration (B-1) |

**K-CAP-1.** A test that signs anything with the gate's key is a CAP-KEY test and MUST be labelled so. In an acceptance
test labelled CAP-DB the gate's key MUST be out of the test's reach: held by a gate host in another process, and used
only by that host. The diagnostic tests cited below do not meet this: their harness held the key in its own process
and, by inspection of the scripts, did not use it in the steps labelled CAP-DB.

**What S-1 and S-5 need.** By test on the unchanged `e25a297`, one machine (`tests/diag_amend16_spec/`, run 2; the
reviewer's probes Q1 to Q3):

| Attempt | Capability | Result at `e25a297` |
|---|---|---|
| A genuine PASS report of another attempt of the same budget, replayed onto a run whose gate host signed FAIL, with RECONCILE or RELEASE, before or after the run's START; the other run's PASS result then stored | CAP-DB | The report is kept and is **not counted** for the run (it names another run and nonce; label WRONG_BINDING or NONE). The run reads UNVERIFIED, never PASS. A courier whose waiting time for a result has passed makes an UNVERIFIED notice; within the waiting time it makes nothing |
| The same with a genuine PASS report of another budget | CAP-DB | the same |
| An attempt made in another budget with the run name and nonce of a genuine PASS report, and that report sent to it | CAP-DB | not counted (it names another budget); the run reads NO_OUTCOME |
| The honest gate host asked again for the failing run | CAP-DB | the same report, byte for byte; recorded as a repeat |
| The honest gate host asked to run a passing design under the failing run's name, nonce or receipts | CAP-DB | refused three ways |
| A genuine report sent again with fields added that the gate did not sign (100 KB) | CAP-DB | accepted as a repeat (DUPLICATE, AUTHORISED); the witness keeps and serves the added fields; one pair, one signature |
| The honest gate host asked to fence a run the chain holds as consumed and that the host never ran | CAP-DB | it signs FENCED_NO_START; sent with RELEASE: DENIED, label BOUND_FENCE, and kept |
| Decisions naming a run that does not exist (a name of 6,146 bytes) | CAP-DB | recorded as DENIED; no attempt is made. That the budget is not charged is argued from `plea_gateway/store.py` (a DENIED decision changes no state), not measured |
| A report signed with the gate's key over a forged PASS result for the failing run itself; the forged result stored | **CAP-KEY** | **believed: the run reads PASS and the courier makes no notice** (S-5) |

**So S-5, as demonstrated, needs CAP-KEY.** S-1 was likewise demonstrated only with reports signed by the gate's key
(`tests/diag_amend16_powers/commit_check.py`); it was not repeated here. With CAP-DB alone no replay made a failing
run read PASS. The reviewer, reading the gate host's code, found no CAP-DB path to K-CONFLICT, K-UNKNOWN-VERDICT,
K-FENCE, K-NONCE, K-DIGEST or K-PHASE for a run, and argued the same for K-EARLY and for K-PHASE of names that no
attempt bears. K-CLAIM is out of CAP-DB's reach only because an absent signed field is read as null (D-2).
What CAP-DB can do: withhold a result, so that the engineer is told UNVERIFIED and not FAIL; make any answer large;
and add decisions without limit. Not shown and not claimed: that no CAP-DB path exists. One path is argued from the
code and not tested: an honest gate host that loses its state (CAP-OS) can run a check twice over inputs that changed
and sign two results.

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

- **ACC-1.** B-1 and B-2 are mandatory security-acceptance blockers. Credential custody (DP1), separation of
  operating-system accounts (DP2) and the trust boundaries that fail without them MUST be resolved before any claim
  that a deployment complies with this specification.
- **ACC-2.** No test run on a single host, or on any deployment where DP1 or DP2 does not hold, establishes acceptance
  of the production contract. Such a test is diagnostic evidence about the code's behaviour and MUST be reported as
  that. This holds for every test named in this document and for the acceptance tests written from it.
- **ACC-3.** Diagnostic modelling and testing MAY continue without those changes.
- **ACC-4.** B-3 (custody of the gate's key) is not resolved by anything here. While the service holds the gate's key
  (CAP-KEY), a forgery made before the witness sees anything is not detected by any rule of this document (N-3).
- **ACC-5.** A test that judges a whole record or a whole budget MUST use a budget made for that test alone.

## 2. Definitions

- **D-1. Canonical form.** `canonical(x)` is `check_record.canonical`. `H(x)` is the SHA-256 of `canonical(x)` in
  lower-case hexadecimal. `Hb(bytes)` is the SHA-256 of the bytes.
- **D-2. Report, and its signed projection.** A report is an object the witness returns as evidence for a run. Its
  **signed projection** is the object holding exactly its `kind`, `root`, `aid`, `nonce`, `claim`, `result_digest`
  (the six fields the gate's signature covers), `signer` and `signature`. A signed field that is absent is read as null, in the projection and in every
  check (a genuine fence report with its two null fields deleted still verifies, by the reviewer's test). Any other
  field was signed by nobody: it is ignored everywhere and only counted. The report's **evidence id** is `H(signed projection)`, and the bytes kept for
  it anywhere are `canonical(signed projection)`.
- **D-3. Gate-signed for a run.** A report is gate-signed for run a of budget B when its kind is `EFFECT_REPORT` or
  `FENCE_REPORT`, its signer is one of the gate keys given, its signature verifies over its six signed fields, its
  `root` is B and its `aid` is a. Anything else returned as evidence is a **stray**. A genuine report of another run
  or budget is a stray for this run.
- **D-4. Chain nonce.** The nonce the chain's state at the checkpoint records for the run, or null.
- **D-5. In scope.** A gate-signed effect report is in scope when the chain nonce is not null and the report's nonce
  equals it. A gate-signed effect report for the run that is not in scope is a **foreign-nonce report**.
- **D-6. Claim and pair.** An in-scope report whose claim is EFFECT or NO_EFFECT is a **verdict report**; one whose
  claim is UNKNOWN is an **UNKNOWN report**. A verdict report's **pair** is (claim, result digest), compared as
  strings. Two reports with one pair are one result, whatever their bytes or signatures. The **pair id** is
  `H([claim, result digest])`.
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
- **D-12. Run of the budget.** An attempt present in the chain's state at the checkpoint. A name that a decision
  carries and that no attempt bears is not a run.
- **D-13. Per-attempt decision.** A decision whose operation is one of RESERVE, ACCEPT_RESERVATION, TOKEN, START,
  ACCEPT_INTENT, RECEIPT, CROSS, RELEASE, RECONCILE, TIMEOUT, MISSING_RECEIPT (`plea_gateway/store.py` 273). Its
  second operand is the name it **names**. Every other decision is **budget-level** and names no run.
- **D-14. Intent acceptance.** The decision `['ACCEPT_INTENT', a]` of kind APPLIED for the run.

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

Let V be the set of distinct pairs among the verdict reports; U true when an UNKNOWN report exists; F true when a
gate-signed fence report for the run exists; X true when a foreign-nonce report exists. All findings that hold are
reported together.

| Id | Finding | Holds when | Meaning, and no more than this |
|---|---|---|---|
| K-CONFLICT | conflicting verdicts | V has two or more members, at any decisions, of any kind or operation, with or without a recorded verdict | the gate's key signed two different results, or two different verdicts, for one run |
| K-UNKNOWN-VERDICT | a verdict beside UNKNOWN | U, and V is not empty, in any order | the gate's key signed UNKNOWN and a verdict for one run; no rule permits it |
| K-FENCE | an effect report beside a fence | F, and any gate-signed effect report for the run exists (in scope or not, any claim) | the gate's key signed that it would never run this run, and a report of its effect |
| K-PHASE | a report where none can be | any gate-signed effect report for a run whose phase is RELEASED or DISCARDED; or, for the budget, any report gate-signed for a name that no attempt bears (O-R-1) | the gate's key signed an effect for a run that was never consumed, or a report for a run that does not exist |
| K-EARLY | an effect report before the intent was accepted | an in-scope effect report at a decision whose number is lower than the run's intent acceptance (D-14), or the run has none | the gate's key signed an effect before the witness had accepted the run's intent |
| K-NONCE | a foreign-nonce report | X | the gate's key signed an effect for this run under a nonce the chain does not record |
| K-DIGEST | a malformed digest | a verdict report whose digest is not well-formed | the gate's key signed a digest no honest gate host signs |
| K-CLAIM | a malformed claim | a report gate-signed for the run whose kind and claim are not EFFECT_REPORT with EFFECT, NO_EFFECT or UNKNOWN, or FENCE_REPORT with FENCED_NO_START and a null nonce and digest | the gate's key signed a claim no honest gate host signs |
| K-MISSING | the answer is not whole | K-CNT-5 | the reading, or the record, lacks a report the chain says exists, or holds one the chain does not place |

- **K-1. Set, not sequence.** No finding and no verdict depends on the order of reports, except K-EARLY, which
  compares decision numbers. An implementation MUST NOT take "the latest report" as anything.
- **K-2. Pair, not bytes.** K-CONFLICT compares pairs. A report signed again with other bytes, or sent again with
  fields added, is not a conflict.
- **K-3. Every key.** A report is gate-signed if it verifies under any gate key given. The courier and the record's
  checker MUST use the same rule. **Precondition P-KEYS:** the reader's gate keys are the witness's pinned set; the
  reader cannot read that set from the witness and the engineer MUST configure it. K-CNT-4 detects a difference for
  authorised decisions only.
- **K-4. Every phase.** The reports of a run MUST be read whatever its phase.
- **K-5. UNKNOWN beside a verdict is forbidden** (the owner's decision). An honest gate signing UNKNOWN does not
  establish that a later verdict is safe to accept. By reading of `verify/deploy.py` (one address for the gate host; a
  stopped host is killed) the honest sequence cannot arise in the shipped deployment; that is argued, not tested.
  UNKNOWN reports alone (no verdict) are permitted and the run is INTERRUPTED as today.
- **K-6. No supersession.** No verdict replaces another by any path.
- **K-7. A fence report alone is not a finding,** whatever the run's phase. An honest gate host will fence a run that
  the chain holds as consumed and that the host never ran (the reviewer's Q1, CAP-DB). Were it a finding, CAP-DB could
  make notices at will.

### 3.3 Belief

- **K-BEL-1.** A stored result is believed if and only if all of these hold: the run's phase is EFFECT; no finding of
  3.2 holds for the run; the recorded report claims EFFECT and its digest is well-formed; and the stored result is an
  envelope whose `outcome` is exactly `'value'` and whose `value` has `H(value)` equal to that digest.
- **K-BEL-2.** A report at any decision other than the recorded verdict is never the basis of belief. It can only add
  a finding.
- **K-BEL-3.** A run with verdict reports and no recorded verdict has no verdict. It is not final.
- **K-BEL-4.** The stored marker of D-8 (c) is never the basis of any outcome, even when the envelope beside it
  carries a `value`.

### 3.4 What each standing calls for

| The run | Outcome | Notice called for |
|---|---|---|
| any finding of 3.2 other than K-MISSING holds (whether or not K-MISSING also holds) | INCONSISTENT | one EQUIVOCATION notice naming every finding that holds (5.3), and no notice that states a verdict |
| K-MISSING holds | the reading is not whole (4.6), in addition to the row above if it applies | none of its own |
| believed, by K-BEL-1 | the result's own verdict, as today (PASS, FAIL, UNKNOWN in meaning (b), INVALID) | as today |
| phase EFFECT, no finding, not believed | UNVERIFIED | as today, after the waiting time (K-N-3) |
| phase NO_EFFECT, no finding | REFUNDED | as today |
| phase CONSUMED, U, V empty, no finding | INTERRUPTED | as today |
| other phases, no finding | as today | as today |

- **K-N-1.** What notice is called for is decided from what the witness gives in this reading, never from what the
  courier remembers having sent.
- **K-N-2.** An EQUIVOCATION notice says only what the "meaning" column says. It MUST NOT say which report is true,
  that the run failed or passed, that a verdict was changed, or who signed.
- **K-N-3. Waiting times.** Where a notice is called for only after a waiting time, the time is counted by the
  courier's own `CLOCK_BOOTTIME` from the first reading of the open chain epoch, whole or not, that saw the run in
  that standing; the courier writes that moment durably when it first sees it. Every waiting time is taken as over,
  and the notice is called for at once: in any reading that is not whole; in the first reading of a chain epoch opened
  for COURIER_STATE_LOST; and wherever the courier cannot count the time (its machine restarted since). So a run
  whose result is withheld cannot be kept without a notice by making some other run unreadable.

### 3.5 The record's checker

- **K-REC-1.** A record fails verification if any finding of 3.2 holds for any of its runs, K-MISSING included, by the
  same rules applied to the reports the record carries.
- **K-REC-2.** A record is signed by the engineer's key; a report taken out of it afterwards fails its signature (by
  the first reviewer's test P1).
- **K-REC-3.** Limit: a report that sat at a decision labelled NONE can be absent from a record without K-MISSING
  (L-1).
- **K-REC-4.** A record and the courier's notices are two channels. A record need not carry the courier's deliveries,
  and it fails on the reports it carries, not on a notice.

### 3.6 Which capability can produce what

| | CAP-DB | CAP-KEY | An honest fault |
|---|---|---|---|
| K-CONFLICT | no replay tested produced it; none found by reading | yes (S-1, S-5) | argued: a gate host that loses its state |
| K-UNKNOWN-VERDICT | none found | yes | only with a second gate host; argued not reachable as shipped |
| K-FENCE, K-PHASE, K-EARLY, K-NONCE, K-DIGEST, K-CLAIM | none found: each needs a report the honest gate host does not sign | yes | none known |
| K-MISSING | no granted role can remove a report (the author's role tests of 21 November) | no | CAP-OWNER; or keys that differ |
| a fence report beside a consumed run | yes (Q1) | yes | yes |
| a stray; a genuine report sent again with fields added; decisions naming no run | yes, at will (S1 to S4; Q2; Q3) | yes | no |
| any answer made large | yes (added fields, Q2; long names, Q3) | yes, also by long nonces and digests under the signature (S-6) | no |

Neither a stray, nor added fields, nor a fence alone, nor a name that no attempt bears is a finding or calls for a
notice.

## 4. The observation: one reading

### 4.1 Order

- **O-1.** The courier takes a challenge from the mailbox for the budget (7.2) before it asks the witness anything,
  and checks it: the mailbox's signature, the budget, its own courier key, and that it answers the request just made.
  The challenge carries the budget's **anchor**: the N and head of the last statement the mailbox accepted for the
  budget in any chain epoch, or (0, none). It also carries the mailbox's head for the budget's open chain epoch
  (chain epoch, k, A), by which the courier checks its own position before it reads (5.6), and the budget's evidence
  gaps (at most 64 ids and a count of the rest).
- **O-2.** It asks the witness for a checkpoint with the token as nonce and the anchor's N as `at`
  (`GET /checkpoint?root=B&nonce=TOKEN&at=N*`). It MUST check the signed fields: the witness's key, `root` = B,
  `nonce` = the token, `at` = N*, and `head_at` = the anchor's head (for N* = 0, the budget's provisioning hash).
- **O-3.** "at is beyond the chain" is a ROLLBACK. A different `head_at` is a FORK. Either ends the reading with an
  alarm (4.6) and no statement, in whatever chain epoch the courier is. Nothing in the protocol clears an anchor: a
  budget whose witness no longer signs the anchor's head stays NOT COVERED until the operator decides otherwise.
  That act is outside this specification and no test written from it covers it.
- **O-4.** It reads the decisions it needs (from its cursor, which in an unbroken chain epoch is the anchor; from 0 in
  a FROM_ZERO reading) to the checkpoint's N and recomputes each hash from the one before. The last MUST equal the
  checkpoint's head, and in a FROM_ZERO reading the hash it computes at N* MUST equal the anchor's head. A decision
  left out fails here (CHAIN_BROKEN).
- **O-5.** It reads runs (4.2), applies section 3 to each, and makes the items called for (5).
- **O-6.** It delivers in this order: pieces of evidence; notices about runs; then, if the reading is whole, the
  observation parts and the statement; if it is not whole, the alarm.
- **O-7.** The courier's cursor, its unsettled set and its carried observations change only when the mailbox has
  accepted a statement. A reading that is not whole, or whose statement is refused, changes none of them. The moments
  of K-N-3 and the outbox are written at any reading.

### 4.2 Which runs are read

- **O-R-1. Named.** Every name named by a per-attempt decision in (K, N]. If no attempt bears the name, its answer is
  read once in this reading. Such names are judged together: if any of them bears a report gate-signed for it, the
  finding K-PHASE holds **for the budget** and calls for one EQUIVOCATION notice for the budget, whose identity has
  no name and which binds the earliest such report. However many such names there are, that is one notice.
- **O-R-2. Unsettled.** Every run that is not settled (4.3).
- **O-R-3. Kinds of reading.** FROM_ZERO: the chain is read from 0 and every run of the budget is read. REFRESH: the
  chain is read from the cursor and every run of the budget is read. INCREMENTAL: the chain is read from the cursor
  and the runs of O-R-1 and O-R-2 are read; every other run is **carried** (4.4).
- **O-R-4.** If any budget-level decision lies in (K, N], the reading MUST be REFRESH or FROM_ZERO.

### 4.3 Settled

| Phase | Settled when |
|---|---|
| EFFECT | believed (K-BEL-1) |
| NO_EFFECT | no finding, and the recorded report claims NO_EFFECT |
| RELEASED, DISCARDED | no finding |
| INDETERMINATE | no finding (it has no verdict; it is frozen by the control plane) |
| any other, or any run with a finding | never |

- **O-S-1.** A run with a finding is never settled: it is read at every reading.

### 4.4 Carried runs: an assumption, stated

- **O-C-1.** A settled run MAY be carried without being read only on **assumption A-CARRY**: that the run's reports
  and stored result are unchanged since it was last read, unless a decision of the chain names it. What supports it:
  a report enters the store only with a decision naming its run (code; 3,456 rows read with the service's own role);
  a stored result whose outcome is `'value'` could not be replaced or removed by `plea_local` (by test). What does
  not: a stored result whose outcome is `'unknown'` is replaced by `plea_local` with no decision (by the same test),
  which is why K-BEL-1 and 4.3 never settle a run on it; any role but `plea_local` (DP1, B-1); and the reports'
  resistance to the witness's and the control plane's roles rests on the author's earlier tests only.
- **O-C-2.** A run that was final is **not** taken to be immutable. A late report at any decision, a RELEASE included,
  names the run in the chain and brings it back under O-R-1.
- **O-C-3. Bounded.** A carried observation MUST have been made in a reading of the same chain epoch (5.4) and the same
  mailbox epoch (7.1), under a statement the mailbox accepted, whose token is no older than the **refresh bound R** by
  the mailbox's time. The statement names the oldest such statement (5.5); the mailbox enforces the bound (ST-7).
  R = 0 forbids carrying: every reading then reads every run.
- **O-C-4.** After a restart of the mailbox, or a new chain epoch, nothing is carried.

### 4.5 The observation record

- **O-P-1.** For each run read in a reading the courier makes a record: `H(name)` and the name's length; N; its phase;
  its outcome (3.4); the findings; the pair id of its recorded report, or null; the number of gate-signed reports, of
  strays, of reports with fields added; one digest over the evidence ids of the gate-signed reports in the order of
  their decisions; whether its stored result was present. Records go in OBSERVATION_PART items of bounded size.
- **O-P-2.** Names that no attempt bears get no record of their own: one count of them, and one digest over their
  `H(name)` in order, for the reading.

### 4.6 A reading that is not whole

A reading is **whole** only if: O-2 to O-4 passed; every run of 4.2 was read; no run has K-MISSING; every answer was
within the courier's limits (4.7); every item called for was accepted or linked by the mailbox; and every piece of
evidence a finding rests on is INLINE in its notice or HELD by the mailbox (6.4).

- **O-W-1.** If a reading is not whole the courier MUST NOT make a statement. It MUST make one
  **OBSERVATION_INCOMPLETE** alarm item for the reading (5.3) naming every reason and, where there is one, the run.
  It MUST still deliver every notice the reading called for from the runs it did read.
- **O-W-2.** Reasons: ROLLBACK, FORK, CHAIN_BROKEN, WITNESS_UNREACHABLE, DEADLINE (the reading could not end within L),
  RUN_OVERSIZE, RUN_UNREADABLE, K_MISSING, EVIDENCE_NOT_HELD, NOTICE_REFUSED (the mailbox refused a notice for want of
  room; the run is named), RUN_NOTICE_LIMIT, MAILBOX_REFUSED, MAILBOX_ROLLBACK (5.6).

### 4.7 Limits on what the courier reads

- **O-L-1.** The courier reads at most RUN_ANSWER_MAX bytes of one run's answer. An answer that is larger makes that
  run RUN_OVERSIZE: an UNREADABLE notice for the run, and the reading is not whole.
- **O-L-2.** The service chooses the size of every answer. With CAP-DB: by fields added to a genuine report (102,681
  bytes for one run, the reviewer's Q2), by names (6,146 bytes each, Q3), and by any number of decisions and strays.
  With CAP-KEY also: by nonces and digests under the gate's signature (70,448 and 200,435 bytes for one report;
  5,002,287 bytes for one run; S-6). CAP-DB can also force every reading to be a REFRESH, by a budget-level decision
  it is allowed to record (CRASH, by reading of `plea_gateway/store.py`; O-R-4). It can therefore make any reading slow or not whole, and keep a budget
  NOT COVERED. This is a loss of liveness. It MUST surface as NOT COVERED with an alarm (8.2), never as a statement
  that leaves the run out.
- **O-L-3.** At most NOTICES_PER_RUN_MAX notices are made for one run in one chain epoch. A run that would need more
  makes the reading not whole (RUN_NOTICE_LIMIT), and the alarm names it. An honest run needs about four. A service
  with CAP-KEY can change a run's set of findings again and again and so reach the limit: the budget is then
  NOT COVERED for as long as the chain epoch lasts. That is a loss of liveness, beside E-B-5.

## 5. Items, identities and chain epochs

### 5.1 The item

- **I-1.** Everything the courier sends for a budget, except pieces of evidence and the request for a challenge, is an
  **item** of form 3, at most ITEM_MAX bytes: `statement` ("ITEM"), `form` (3), `kind`, `root` (the budget),
  `chain_epoch`, `k`, `prev`, `identity`, `body`, `time` (the courier's wall clock, for people only), `courier`,
  `signer`, `signature`. The courier's signature covers every field but `signer` and `signature`. The item's
  **digest** is `H(item)`.
- **I-2.** Every field is bounded. A value the service can make large (a run's name beyond 200 characters, a nonce, a
  digest that is not well-formed) is carried as its SHA-256 and its length, with at most its first 200 characters
  shown as data. The courier MUST NOT make an item larger than ITEM_MAX (E-B-1 keeps an EQUIVOCATION notice within
  it).
- **I-3.** `A(0) = H(["PLEA-A16-CHAIN", root, chain_epoch])`. `A(k) = H(["PLEA-A16-ITEM", A(k−1), identity_k])`.
  An item's `prev` is A(k−1). Every item accepted or linked takes the next k of its chain epoch and moves the head.
  An item that is refused takes no position: the courier signs an item for the position that is next when it sends
  it, and signs it again, with its identity and body unchanged, if it must send it at another position.
- **I-4.** One courier key per budget, and one courier process per budget. The mailbox refuses an item for a budget
  from a second courier key. Two processes with one key each close the other's chain epoch; the mailbox cannot tell
  them apart; the status shows the count of chain epochs rising.

### 5.2 Deterministic identity

- **I-ID-1.** For a notice about a run, `identity = H(["PLEA-A16-ID", root, kind, H(name), basis])`, where the basis
  is computed from the witness's data only. For the budget's one notice of O-R-1 the name is null.

| Kind | Basis |
|---|---|
| outcome notice (FAIL, UNKNOWN, INVALID, UNVERIFIED, INTERRUPTED, NO_OUTCOME, REFUNDED, INDETERMINATE, UNREADABLE) | the outcome; the number of the recorded verdict's decision, or null; the pair id of the recorded report, or null |
| EQUIVOCATION | the sorted set of findings that hold, K-MISSING left out |

- **I-ID-2.** For OBSERVATION_INCOMPLETE: `identity = H(["PLEA-A16-ID", root, kind, token])`: one alarm for one
  reading. It is never deduplicated against an earlier reading's.
- **I-ID-3.** For EPOCH_OPEN, OBSERVATION_PART and COVERAGE: `identity = H(["PLEA-A16-ID", root, kind, chain_epoch,
  body])`. These are never deduplicated.
- **I-ID-4.** An identity of I-ID-1 never depends on the time, on k, on the chain epoch, on which reports beyond the
  findings exist, or on anything the courier remembers. So more reports added to a run that already has a finding
  make no new notice unless the set of findings changes; they show in the observation record.

### 5.3 Kinds

| Kind | Body (beyond what identity needs) |
|---|---|
| a notice of an outcome | as the form 2 notice today, with the provenance sentence that applies; the run's name by I-2 |
| EQUIVOCATION | the run's name by I-2; the nonce's SHA-256 and length; N and head; the findings; the bound reports (below), each with its decision, that decision's operation, kind, code and label, its claim, its digest or the digest's SHA-256 and length, its signer, its size, its evidence id, and where it is (6.4); the count of gate-signed reports, of pairs, of strays; the digest of O-P-1 |
| OBSERVATION_INCOMPLETE | the token; every reason with its run (`H(name)` and length), at most 64 entries and a count of the rest; N if a checkpoint was had; sizes, if size is a reason |
| OBSERVATION_PART | the token; N; records of O-P-1 and O-P-2; part i of n |
| EPOCH_OPEN | 5.4 |
| COVERAGE (the statement) | 5.5 |

- **I-K-1. The bound reports of an EQUIVOCATION notice.** For K-CONFLICT: the recorded report if there is one,
  otherwise the earliest verdict report by decision; and the earliest verdict report whose pair differs from it. For
  every other finding: the earliest report by decision that makes it hold, and for K-UNKNOWN-VERDICT and K-FENCE the
  earliest of each of the two kinds. At most twelve reports in all, which is every report these rules can select; the same report is bound once.

### 5.4 Chain epochs, and a courier that has lost its state

A **chain epoch** is one unbroken life of a courier's state for a budget: its cursor, its unsettled set, its record of
carried observations, its position k and A(k), its outbox, and its continuity secret.

- **I-E-1. Opening.** The first item of a chain epoch (k = 1) is EPOCH_OPEN: a new random `chain_epoch` of 16 bytes;
  `reason`, one of FIRST or COURIER_STATE_LOST; and `commit = Hb(s_1)` for a secret s_1 of 32 random bytes that the
  courier has written durably first.
- **I-E-2. The mailbox, on an EPOCH_OPEN whose `chain_epoch` it has never seen.** It closes the budget's open chain
  epoch, if any, recording why; it keeps every notice, receipt and piece of evidence of every earlier epoch; it starts
  the new chain at A(0); and the budget is NOT COVERED (EPOCH_OPENED) until a FROM_ZERO statement of the new epoch is
  accepted. The budget's anchor (O-1) is kept across chain epochs. Its status shows how many chain epochs the budget
  has had, and the reason each was opened.
- **I-E-3. A known `chain_epoch`.** An EPOCH_OPEN that is the very item that opened the open epoch (the same digest) is
  answered with its first receipt (DL-2). Any other EPOCH_OPEN naming a `chain_epoch` the mailbox has seen is refused
  (409 EPOCH_KNOWN) and changes nothing: an old EPOCH_OPEN replayed cannot close the open epoch.
- **I-E-4. Fail closed.** A courier has lost its state for a budget when that state is absent or unreadable, when
  the mailbox's signed head for the open epoch is not a position of the courier's own chain (5.6), or when a statement
  of its is refused at ST-5. It MUST NOT take
  its cursor, its position, its settled runs or anything else from the mailbox or from an old copy. It MUST open a
  new chain epoch with reason COURIER_STATE_LOST and read from decision 0.
- **I-E-5. From sequence 0.** The first statement of a chain epoch MUST be FROM_ZERO: every decision from 0 was read
  and hashed, every run of the budget was read in its reading, none is carried, and every notice that reading called
  for is an item of the new epoch's chain.
- **I-E-6. No duplicate, none missing.** When an item of I-ID-1 has an identity already held for the budget (from any
  chain epoch), the mailbox keeps no second copy for the engineer. The item takes the next position of the open chain
  (I-3); the mailbox records (k, identity, this item's digest, the first item's digest) in the chain's index and
  answers with **the first receipt**, unchanged, and a signed LINKED acknowledgement of (chain epoch, k, identity). A notice the lost courier
  had made and not delivered is made again by the reading from 0 and is delivered now. A notice of an earlier epoch
  that the new reading does not call for stays held, as history.
- **I-E-7. Continuity is authenticated.** Statement j of a chain epoch carries `reveal = s_j` and
  `commit = Hb(s_{j+1})`. The mailbox accepts the statement only if `Hb(reveal)` equals the commit it holds (from
  EPOCH_OPEN for j = 1, else from the last accepted statement). The courier writes s_{j+1} durably before it sends
  statement j, and keeps s_j until statement j has been accepted. A statement that is refused uses up nothing: the
  commit the mailbox holds is unchanged and the next statement reveals s_j again.
- **I-E-8. What the secret adds.** The position k and A(k) can be read back from the mailbox; the secret cannot. A
  courier without its state, or restored from a copy older than its last accepted statement, cannot produce `reveal`,
  so no statement of the open epoch can be counted for it, and it cannot claim COVERED, until it has opened a new
  epoch and read from 0.
- **I-E-9.** The mailbox cannot check that a reading was from decision 0. That is the courier's signed word.

### 5.5 The statement of coverage

- **I-S-1.** A statement is an item of kind COVERAGE. It is delivered after every item it commits to: the mailbox
  takes only the next item of a chain (7.3).
- **I-S-2.** Its body: the challenge whole; the checkpoint whole; `reading` (FROM_ZERO, REFRESH or INCREMENTAL); N and
  head; `prev_statement` (the digest of the last statement accepted in this chain epoch, or null); `reveal` and
  `commit` (I-E-7); the counts: runs of the budget, read, carried, unsettled; `oldest_carried` (the digest of the
  accepted statement whose reading made the oldest observation still carried, or null); and the limits it was made
  under (L, R, RUN_ANSWER_MAX).
- **I-S-3.** The statement's own `prev` (A(k−1)) is its commitment to every item before it.

### 5.6 The courier's outbox, and answers it must act on

- **I-O-1.** Every item the courier makes is written durably in its outbox before it is sent. A notice about a run is
  kept there until it has a receipt or a LINKED acknowledgement, or the chain epoch is closed. Every other item
  (an alarm, an observation part, a statement, an EPOCH_OPEN) is kept only until the mailbox has answered it: if it
  is refused, by 422 or for want of room, it is dropped, the reading it belongs to is not whole, and the next reading
  makes its own.
- **I-O-2. No answer.** The courier sends the same item again. The mailbox answers an item it already holds in the
  open chain epoch (the same digest) with its first answer (DL-2).
- **I-O-3. 409 CHAIN_POSITION**, with the mailbox's signed head (chain epoch, k, A). If that head is a position of the
  courier's own chain of this epoch, the courier delivers its items after that position, in order, and goes on. If
  it is not, the courier has lost its state (I-E-4).
- **I-O-4. The mailbox behind its own receipts.** If the courier holds a receipt of this mailbox for a position of the
  open chain epoch beyond the head the mailbox now signs for that epoch, the mailbox has lost state. Receipts of a
  closed chain epoch are not compared. The courier makes the reading not whole
  (MAILBOX_ROLLBACK), opens a new chain epoch and delivers everything again.
- **I-O-5. 507.** The item took no position. A notice about a run stays in the outbox and is sent again at every
  reading, signed for the position then next; any other item is dropped (I-O-1). The courier goes on at once with its
  other items, each signed for the position then next, so that a refused item never holds back a later one. The
  reading is not whole (NOTICE_REFUSED for a notice about a run, MAILBOX_REFUSED otherwise).
- **I-O-6. 409 EVIDENCE_MISSING.** The item took no position. The courier stores the evidence again from its own copy
  (E-B-6) and sends the item again, signed for the position then next. If the mailbox refuses the evidence, the
  notice is sent saying NOT_HELD with the reason; its identity is the same.
- **I-O-7. Gaps.** At every reading the courier stores again, from its own copy (E-B-6), every object for which the
  challenge lists a gap.
- **I-O-8. Once in a chain epoch.** Within one chain epoch the courier sends an item of I-ID-1 once: when a reading
  calls for a notice whose identity already has a receipt or a link in this chain epoch, nothing is sent again. This
  uses the courier's memory only for what the mailbox has already acknowledged in the epoch; what is called for is
  still decided by K-N-1. In a new chain epoch everything called for is sent.

## 6. The mailbox's stores

### 6.1 Evidence objects

- **E-1.** A piece of evidence is a sequence of bytes. Its **id** is `Hb(bytes)`. For a report the bytes are
  `canonical(signed projection)` in UTF-8, so its id is the report's evidence id (D-2).
- **E-2. Immutable.** Stored under its id, written whole and synced before any answer, never overwritten, never
  removed while any notice the mailbox holds **binds** it. A notice binds every evidence id of its bound reports
  (I-K-1), whatever it says of where each is. Storing an id already held changes nothing and answers as before.
- **E-3. Hard limit.** One object is at most OBJ_MAX bytes. A larger one is refused (413) and nothing is kept.
- **E-4.** A report signed by an honest gate host has a signed projection of at most about 13 KB at the witness's
  longest names (calculated). A larger one needs CAP-KEY.

### 6.2 Room, quotas and retention

- **E-Q-1. Evidence.** Evidence held for one budget is at most EVID_BUDGET_QUOTA bytes; for the mailbox,
  EVID_GLOBAL_QUOTA. An object is charged to each budget that stored it. The operator SHOULD set EVID_GLOBAL_QUOTA to
  at least the sum of the budgets' quotas; if it is less, one budget's evidence can use up another's room, and the
  other's status then says so (GLOBAL_QUOTA).
- **E-Q-2. Items, in four rooms for each budget, none of which can use another's.** NOTICE_QUOTA for the bodies of
  notices about runs (I-ID-1). ALARM_RESERVE for the bodies of OBSERVATION_INCOMPLETE items. OBS_QUOTA for the bodies
  of OBSERVATION_PART and COVERAGE items and for the record of each accepted statement. INDEX_QUOTA for the index
  entry of every position of every chain epoch, links included, and for EPOCH_OPEN items. The last INDEX_RESERVE
  bytes of INDEX_QUOTA can be used only by notices about runs, alarms and EPOCH_OPEN items.
- **E-Q-3.** A store that would exceed its room is refused (507, naming the room) and nothing is kept.
- **E-Q-3a. Sizing, stated.** NOTICE_QUOTA MUST be at least (the runs the budget can come to have, those allowed back
  after NO_EFFECT included, and one more for the budget's own notice) × NOTICES_PER_RUN_MAX × ITEM_MAX, which is the
  most the bodies of its notices can come to. ALARM_RESERVE MUST be at least ALARMS_KEEP × ITEM_MAX. Index entries and
  statement records are never dropped, so INDEX_QUOTA and OBS_QUOTA are used up as the mailbox works: about 0.2 KiB
  of INDEX_QUOTA for every position (a reading takes at least one; a new chain epoch takes one for every notice it
  links), and about 1 KiB of OBS_QUOTA for every accepted statement (calculated). **A mailbox therefore has a finite
  life at given quotas.** When OBS_QUOTA is full, statements are refused and notices and alarms are still taken. When
  INDEX_QUOTA is down to its reserve, only notices about runs, alarms and EPOCH_OPEN items are taken. When it is
  full, nothing is taken, a courier that has lost its state cannot open an epoch, and nothing more can be held until
  the operator provides more. In each case the item is refused (507, naming the room), the budget is NOT COVERED at
  once (C-1.6) and the status says which room is full.
- **E-Q-4. Retirement.** The bodies of OBSERVATION_PART and COVERAGE items that support no carried observation (those
  of statements older than the `oldest_carried` of the last accepted statement, and those of closed chain epochs) MAY
  be dropped and their room returned. Their index entries (k, identity, digest) and the record of each accepted
  statement (its digest, N, head, token, tick) are kept. The body of an alarm MUST be dropped, oldest first, when
  keeping it would leave more than ALARMS_KEEP alarm bodies for the budget; its index entry is kept. A notice about a run, its receipt, and evidence a held notice binds are
  never dropped by the protocol.
- **E-Q-5. Orphans.** An evidence object that no held notice binds (E-2) MAY be removed once it has been so for T_ORPHAN,
  counted by M-T-1 inside the current mailbox epoch from the later of its storing and the epoch's start.
- **E-Q-6. One at a time.** The handling of one item (7.3), the storing of one evidence object, a retirement and an
  orphan removal are serialised for the whole mailbox: none begins while another is under way, and each is durable
  before the next begins. So an object found held at DL-4 is still held when DL-5 or DL-6 writes the item that names
  it.

### 6.3 Reading back

- **E-R-1.** `GET /evidence?root=B&id=…` gives the bytes to a reader. The reader MUST recompute `Hb` and compare with
  the id; for a report it MUST then apply D-3. Bytes that do not match the id are treated as absent.
- **E-R-2. A reader verifies a chain epoch** by taking its items in the mailbox's order (`GET /items`), and for each
  position k: checking the courier's signature on the item, or for a link that the identity is that of the first item
  named and that the first item is held; recomputing the identity from the item's own fields (5.2); recomputing A(k);
  and at the end comparing A(k) with the mailbox's signed head and with the `prev` of the last accepted statement.
  A position whose body was retired is verified from its index entry alone and is reported as retired.

### 6.4 Binding, and failing closed

- **E-B-1.** An EQUIVOCATION notice binds each of its bound reports (I-K-1) by its evidence id and size, and says for
  each where it is: `INLINE`, `HELD` or `NOT_HELD` with a reason (OVERSIZE, QUOTA, UNAVAILABLE). Reports are INLINE
  only all together, and only if their sizes sum to at most INLINE_TOTAL_MAX; otherwise none is INLINE.
- **E-B-2.** The mailbox refuses (409 EVIDENCE_MISSING) a notice that says HELD for an id it does not hold for that
  budget, and checks that every INLINE report's bytes give the id the notice states.
- **E-B-3.** The mailbox takes a notice that says NOT_HELD for an id. A budget has an **evidence gap** for an id
  whenever a notice the mailbox holds for the budget binds that id other than INLINE and the mailbox does not hold
  an object with that id for the budget. A gap is a state, not an event: it ends when the object is stored (a
  verified `POST /evidence`) and it begins again if the object is ever absent.
- **E-B-4. Fail closed.** While a budget has an evidence gap it is NOT COVERED (EVIDENCE_GAP), whatever statements it
  holds, and its status names the ids. Missing, altered, oversized or unavailable evidence never turns a finding into
  no finding: a reader who cannot obtain a report matching its id treats the finding as standing and its evidence as
  incomplete.
- **E-B-5.** A gap for an object larger than OBJ_MAX cannot be closed while OBJ_MAX stands. A service with CAP-KEY can
  therefore keep a budget NOT COVERED with one such report. That is a loss of liveness, shown by the status; it is
  the price of failing closed.
- **E-B-6.** The courier also keeps each bound report in its own durable state, up to RUN_ANSWER_MAX.

### 6.5 Exhaustion by a dishonest service

- **E-X-1.** A service with CAP-DB can add decisions, strays, names and added fields without limit, and so make
  answers and observation records large. A service with CAP-KEY can also sign reports of any size and number.
- **E-X-2.** Neither can use a notice's room except through runs: a notice exists only for an attempt of the budget,
  at most NOTICES_PER_RUN_MAX for one run in one chain epoch, and one for the budget (O-R-1); and observation parts,
  alarms and evidence are in rooms of their own (E-Q-2). The number of attempts that can come to call for a notice is
  bounded by the runs the budget was provisioned with: argued from the store's accounting, not tested.
- **E-X-3.** In every case of exhaustion the outcome MUST be all of: the notices of other runs are still taken while
  NOTICE_QUOTA has room; the budget is NOT COVERED with the reason; and an alarm item within ALARM_RESERVE names the
  reason and, for a notice refused, the run. It MUST NOT be a statement that leaves a run out, a notice dropped
  without trace, or a status that says COVERED.
- **E-X-4.** If NOTICE_QUOTA itself is spent, a notice about a run is refused (507 NOTICE_QUOTA). It stays in the
  courier's outbox (I-O-5), the reading is not whole, the alarm names the run, and the status says NOTICES_REFUSED
  with the count of refusals. An alarm's body always has room (E-Q-3a, E-Q-4). If INDEX_QUOTA is spent, the mailbox
  refuses the alarm too, no statement can be made, and the status says ITEMS_REFUSED. In both cases a failed run's notice
  is not held, the budget is NOT COVERED at once (C-1.6), and the status says that notices were refused: the operator MUST size NOTICE_QUOTA and ALARM_RESERVE
  for the budget's number of runs.
- **E-X-5.** Strays, added fields and names that no attempt bears are not stored as evidence. They are counted and
  committed to in the observation record only.

## 7. The mailbox: time, tokens and statements

### 7.1 Time and epochs

- **M-T-1.** Elapsed time is `time.clock_gettime_ns(time.CLOCK_BOOTTIME)`. `time.monotonic()` MUST NOT be used: on the
  deployment host it is `CLOCK_MONOTONIC`, which does not count suspension, and under-counting an age is a failure of
  safety.
- **M-T-2. Mailbox epoch.** Made at each start of the mailbox: the machine's boot identifier
  (`/proc/sys/kernel/random/boot_id`) and 16 random bytes, written durably before anything is answered. A tick is
  meaningful only inside the epoch that took it. A tick of another epoch MUST NOT be compared with the present clock.
- **M-T-3.** After a reboot `CLOCK_BOOTTIME` begins again near zero. Because every start makes a new epoch and no tick
  crosses epochs, no age is computed across a reboot: every token of before is VOID and every budget is NOT COVERED
  (MAILBOX_RESTARTED).
- **M-T-4. The wall clock** is written beside what the mailbox signs, for people. No decision uses it alone.
- **M-T-5. Larger age.** When the mailbox works out an age it also takes the wall clock's movement over the same
  interval. If the wall clock went backwards, or the two differ by more than CLOCK_TOLERANCE, it records a clock
  anomaly durably, shows it in every status until the operator clears it, and uses the larger of the two ages.
- **M-T-6.** The mailbox takes no time from the courier, the witness, an item or a checkpoint.
- **M-T-7. Limit.** A pause of the whole machine from outside it (a hypervisor) may move no clock inside it. Then only
  a corrected wall clock shows the gap (M-T-5); if nothing corrects it, nothing inside the machine can see the pause.

### 7.2 Tokens

- **M-K-1. Issue.** `POST /challenge` with a request signed by the budget's courier key (11), naming the mailbox epoch
  the courier last saw. A request that names another mailbox epoch is refused (409 EPOCH, with the current epoch) and
  the courier asks again; a request whose digest the mailbox has already answered in this mailbox epoch is refused
  (409 REPLAY). So a request replayed cannot issue a token or make one VOID. A courier that had no answer asks again with a new
  request nonce. The mailbox makes 32
  bytes from the operating system's source of randomness, written as 43 characters of URL-safe base64 without
  padding; writes durably the token, the mailbox epoch, a serial number, the budget, the courier's key, L, R, the
  budget's anchor and the tick; and only then returns the challenge, signed.
- **M-K-2. Bounded.** At most TOKENS_MAX tokens are ISSUED for one budget. Issuing another makes the oldest ISSUED
  token of the budget VOID.
- **M-K-3. States.** ISSUED, USED, SPENT, EXPIRED, VOID. ISSUED becomes USED or SPENT by a statement (7.4), VOID by
  M-K-2 or a restart, EXPIRED by age. USED becomes EXPIRED by age. Nothing else changes.
- **M-K-4. Expiry.** A token whose age is more than L is EXPIRED: coverage that rested on it has ended.
- **M-K-5. Restart.** At a start of the mailbox every token of an earlier epoch is VOID.
- **M-K-6.** USED and SPENT are written durably before the mailbox answers the statement.

### 7.3 Taking an item: strict order

For every item delivered, in this order, under E-Q-6. A failure at one step ends the handling; the later steps are not
reached.

| Step | Check | On failure |
|---|---|---|
| DL-1 | It is at most ITEM_MAX bytes, of form 3, of a kind known, signed by the budget's courier key | 400 or 403; nothing kept |
| DL-2 | If an item with the same digest is already held in the budget's open chain epoch, or was refused there as a statement: answer as the first time (the first receipt, the first LINKED acknowledgement, or the first refusal) | — (nothing changes) |
| DL-3 | It is an EPOCH_OPEN with a `chain_epoch` never seen, k = 1 and `prev` = A(0) of that epoch; or its `chain_epoch` is the budget's open epoch, its k is the head's k + 1 and its `prev` is the head's A | 409 EPOCH_KNOWN, or 409 CHAIN_POSITION with the mailbox's signed head; nothing kept; **no token is touched** |
| DL-4 | Every evidence id it says is HELD is held for the budget and every INLINE report gives its id (E-B-2); its room has space (E-Q-2, E-Q-3) | 409 EVIDENCE_MISSING, or 507; nothing kept; **no token is touched** |
| DL-5 | If it is not a COVERAGE item: if its identity is of I-ID-1 and is held for the budget, link it (I-E-6), else store it; for an EPOCH_OPEN, do I-E-2 now and not before; write the index entry and the new head; all durably; then answer | — |
| DL-6 | If it is a COVERAGE item: the statement checks of 7.4 | as 7.4 |

- **M-D-1.** A statement that arrives before an item it commits to fails at DL-3 and is refused with the mailbox's
  head. Its token stays ISSUED. The courier delivers the items after that head and sends the statement again (I-O-3).
  A token is never spent by the order of delivery.
- **M-D-2.** Evidence and every item a statement commits to are therefore durably stored and verified before any step
  that can use or spend a token.

### 7.4 Statement checks

Reached only after DL-1 to DL-4. All are evaluated. If all pass: the statement takes its position, the head moves,
the token becomes USED, the commit and the anchor are replaced, all durably, and the statement is receipted. If any
fails: the statement takes **no** position and the head, the commit and the anchor are unchanged; the token, if it
was ISSUED, is a token of this statement's budget, and the statement is signed by that token's courier key, becomes
SPENT (a statement never spends a token of another budget, even where one courier key serves both); the statement is kept beside the chain
as evidence with the checks that failed; and the answer is 422 naming them.

| Id | Check |
|---|---|
| ST-1 | the challenge is this mailbox's own (its signature), of the current mailbox epoch, for this budget and this courier key |
| ST-2 | the token is ISSUED |
| ST-3 | the token's age is at most L (M-T-5). By M-K-4 such a token is no longer ISSUED, so ST-2 fails with it; ST-3 is kept so that the reason is given |
| ST-4 | the checkpoint verifies under a witness key the mailbox was given; its `root` is the budget; its `nonce` is the token; its `seq` and `head` are the statement's N and head |
| ST-5 | continuity of the chain epoch: `Hb(reveal)` is the commit held (I-E-7), and `prev_statement` is the digest of the last statement accepted in this chain epoch, or null if there is none |
| ST-6 | continuity of the budget: the checkpoint's signed `at` is the anchor's N and, unless that N is 0, its signed `head_at` is the anchor's head. The anchor is the budget's, across chain epochs |
| ST-7 | kind of reading: the first statement of a chain epoch is FROM_ZERO. The first statement accepted for the budget in a mailbox epoch is FROM_ZERO or REFRESH. For FROM_ZERO and REFRESH, carried is 0. For INCREMENTAL, `oldest_carried` names a statement accepted in this chain epoch and this mailbox epoch whose token's age is at most R |
| ST-8 | N is not lower than the anchor's N |
| ST-9 | the limits in the statement are the mailbox's own |

- **M-S-1.** A statement naming a token that is not ISSUED (USED, SPENT, EXPIRED, VOID, or unknown) fails ST-2, is
  kept as evidence and counts nothing.
- **M-S-2.** The mailbox does not check that the observation is true. It checks bindings, holdings, order and time.

## 8. COVERED and NOT COVERED

### 8.1 The definition

**C-1.** At the mailbox's time t, budget B is **COVERED to N** if and only if all of these hold:

1. the mailbox holds a statement S for B that passed 7.4, in the current mailbox epoch and the budget's open chain
   epoch, and S is the last such;
2. the token of S is USED and its age at t is at most L;
3. B has no evidence gap (E-B-4);
4. no OBSERVATION_INCOMPLETE item for B has been taken after S;
5. no statement for B has been refused at 7.4 after S;
6. no item for B has been refused for want of room after S;
7. if S carries any run, the token of the statement S names as `oldest_carried` is at most R old at t;
8. the mailbox can read its own record of B.

Otherwise B is **NOT COVERED**.

**C-2. What COVERED to N claims, and nothing more.** That the courier holding the budget's courier key signed all of
the following, and the mailbox verified what 7.3 and 7.4 say it verifies:

- in a reading that began after this mailbox issued a token no more than L ago, the witness signed a checkpoint for B
  at decision N bearing that token, naming the budget's anchor and signing the anchor's head back;
- the decisions to N hash to that checkpoint's head, continuously from the last accepted statement or from 0;
- every name named by a per-attempt decision since the cursor, and every unsettled run, was read in that reading and
  judged by section 3;
- every other run was last read in a reading of this chain epoch and mailbox epoch whose token is no more than R old
  at the time of the status, and no decision since names it (A-CARRY);
- every item those observations called for is held by this mailbox or linked to one it holds, and every report a
  finding's notice binds is in the notice or in the mailbox's evidence store.

**C-3. It is an observation at a boundary, bounded in time. It is not a guarantee.** It does not say: that any
verdict is correct; that no conflicting report will appear after N; that a run that was final will stay as it was;
that every report attached at a decision labelled NONE was returned (L-1); that a carried run's stored result or
reports were not changed by a role other than `plea_local` (B-1); that the courier read every run (I-E-9); or that
the budget will be COVERED at any later time.

**C-4.** NOT COVERED never says that a run failed.

### 8.2 Reasons for NOT COVERED

The status gives every reason that holds: NEVER (no statement accepted in the open chain epoch), EXPIRED (C-1.2),
MAILBOX_RESTARTED, EPOCH_OPENED, STATEMENT_REFUSED (C-1.5), EVIDENCE_GAP (with the ids, and GLOBAL_QUOTA where that
is why), OBSERVATION_INCOMPLETE (with the alarm's reasons), NOTICES_REFUSED (C-1.6 for a notice about a run, with the
count), ITEMS_REFUSED (C-1.6 for any other item), STALE_CARRY (C-1.7), RECORD_UNREADABLE (C-1.8; a mailbox that
finds no record of a budget answers NEVER). CLOCK_ANOMALY is shown beside any state.

### 8.3 The status

- **C-S-1.** `GET /status?root=B&nonce=Q` is answered with a status signed by the mailbox that carries Q back, the
  mailbox epoch, the state and reasons, and, where they exist: N and head (the anchor), the statement's digest, the
  token's age and L, the age of the token of the oldest carried observation and R, the chain epoch, the count of
  chain epochs and why each was opened, k and A(k), the evidence gaps, the alarms held, the count of notices and
  items refused, any clock anomaly, and the wall-clock time for people.
- **C-S-2. The reader's rule.** Only a status that verifies under the mailbox's key and carries the reader's own nonce
  is evidence of COVERED. No such status is NOT COVERED: a mailbox that is down, stalled, cut off or restarted is not
  "still covered".
- **C-S-3.** NOT COVERED is seen without any courier: a mailbox that receives nothing moves a budget to EXPIRED by its
  own clock.

## 9. Safety, liveness, and what is not claimed

| Id | Kind | Statement |
|---|---|---|
| SAF-1 | safety | The mailbox never counts a statement whose token is older than L, was used or spent, or is of another budget, courier key or mailbox epoch |
| SAF-2 | safety | No statement is counted unless every item it commits to, and every piece of evidence those items say is held, was durably stored first, and no token is used or spent by a statement that fails for the order of delivery |
| SAF-3 | safety | A fresh receipt, a restart, a reboot, a replay or a late delivery never makes an old observation fresh: age is counted from the issue of the token, inside one mailbox epoch |
| SAF-4 | safety | Within the open chain epoch, no statement is counted unless it reveals the secret committed by the epoch's opening or by the last accepted statement |
| SAF-5 | safety | After EPOCH_OPEN, a budget is not COVERED until a FROM_ZERO statement of the new epoch is accepted |
| SAF-6 | safety | An item of I-ID-1 whose identity is held is linked, not stored again; the first receipt is returned unchanged; no notice or receipt of an earlier epoch is removed |
| SAF-7 | safety | While a budget has an evidence gap, or an OBSERVATION_INCOMPLETE item, a refused statement or an item refused for room newer than its last accepted statement, or a carried observation whose token is older than R, its status is not COVERED |
| SAF-8 | safety | A status carries the asker's nonce; an old status cannot answer a new question |
| SAF-9 | safety | A run with any finding of 3.2 is never given a verdict, and a record carrying such a run fails |
| SAF-10 | safety | No statement is counted, in any chain epoch, whose checkpoint does not sign back the head of the last statement accepted for the budget |
| SAF-11 | safety | An evidence object found held when an item naming it is taken is still held when that item is written |
| N-1 | not claimed | **Liveness.** That a courier runs; that a reading ends within L; that a budget ever becomes COVERED. The service can prevent each (S-3, S-6, E-B-5) |
| N-2 | not claimed | **Notification.** That anybody is told anything by any time. The mailbox sends nothing. NOT COVERED is seen only by one who asks while the mailbox answers. No bound on the time to notification is claimed and the mechanism cannot give one. What is bounded, at the time the status is signed: a COVERED status rests on a checkpoint read under a token no more than L old, and on observations made under tokens no more than R old (C-1.2, C-1.7) |
| N-3 | not claimed | **Correctness of a verdict.** One consistent report is not evidence that it is correct. With CAP-KEY, a forgery made before the witness sees anything passes every rule here |
| N-4 | not claimed | **Suspension and pause.** `CLOCK_BOOTTIME` is available and cannot be set; its behaviour across a real suspension is untested, and a pause from outside the machine may be invisible (M-T-7) |
| N-5 | not claimed | **Acceptance.** Nothing here, and no test on a deployment where DP1 or DP2 fails, establishes the production contract (ACC-2) |
| N-6 | not claimed | **That a failed run's notice is always held.** If the room for notices, or for the index, is spent, the notice is refused and the status says so (E-Q-3a, E-X-4). A mailbox has a finite life at given quotas |

## 10. Limits that cannot be removed without changing the witness or the store

- L-1. Whether a decision labelled NONE carried a report. The loss of such a report (possible only with CAP-OWNER) is
  not detectable; a late report sent with a RELEASE is always labelled NONE.
- L-2. Which report was recorded at a decision: the chain's hash does not cover the report or its digest. What the
  courier saw is fixed only by the courier's own signed observation record.
- L-3. A stored result is written without a decision of the chain. Worked round by reading unsettled runs at every
  reading and by the refresh bound R; not removed.
- L-4. The cost of the chain: each decision carries the state of every run of its budget, names included (S-4). With
  the short names of the measurements: about 1.0 MB for one new run at 1,000 runs; about 0.5 GB over the life of a
  1,000-run budget, read at once or a little at a time; 508,180,089 bytes measured at 996 runs. The service chooses
  the names (6,146 bytes each is possible), so the cost can be many times that. A REFRESH reading adds one answer for
  every run. No linear scaling is claimed.
- L-5. The size of a report, of a run's answer and of the chain has no bound short of the database's own (S-6). The
  cost of every reading is the service's to choose.
- L-6. A forgery made before the witness sees anything; one consistent false chain signed by the witness.
- L-7. The witness's answer for a run is unsigned and takes no nonce: an observation of a run is bound to the token
  only by the courier's signature.
- L-8. No reading lists the budgets.
- L-9. A pause of the machine from outside it.
- L-10. A mailbox whose own durable state is rolled back cannot see it. The courier sees it only while it holds a
  later receipt (I-O-4); if both lose their state together, nothing here detects it.
- L-11. The store rewrites some numbers in a stored result (1e300, 1.5e17 and −0.0, by the reviewer's Q4). A result
  holding such a number does not hash to the digest the gate signed and is never believed: the run reads UNVERIFIED.

## 11. Interfaces

**The witness, the gateway and the store: no change.**

**The mailbox.** Every request is over TLS with a client certificate issued by the mailbox's authority. The mailbox is
started with the client names that may write (the courier's) and the client names that may read. A request from any
other name is refused (403).

| Request | From | Answer |
|---|---|---|
| `POST /challenge` a request `{CHALLENGE_REQUEST, root, mailbox epoch, request nonce}` signed by the budget's courier key | a writing name | 200 a signed CHALLENGE: mailbox, mailbox epoch, serial, root, courier key, token, L, R, the anchor, the head of the open chain epoch, wall time; 403; 409 EPOCH; 409 REPLAY |
| `POST /deliver` an item | a writing name | 200 a signed receipt (or the first receipt and a LINKED acknowledgement); 400; 403; 409 EPOCH_KNOWN; 409 CHAIN_POSITION with the signed head; 409 EVIDENCE_MISSING; 422 with the failed checks; 507 naming the room |
| `POST /evidence?root=B` bytes | a writing name | 200 a signed HELD: id, size, root; 413; 507 naming the quota |
| `GET /evidence?root=B&id=…` | a reading name | 200 the bytes; 404 |
| `GET /items?root=B&chain_epoch=E&after=k&limit=n` | a reading name | 200 at most n positions of that chain epoch after k, in the mailbox's order, at most 1 MiB in all: for each, the item or the mark that its body was retired, its receipt or its link, and its index entry; and the signed head |
| `GET /status?root=B&nonce=Q` | a reading name | 200 a signed STATUS (C-S-1) |
| `GET /pubkey` | as today | as today |

**Configuration, set by the operator at start and fixed for the mailbox epoch:** the writing and reading names; the
courier key for each budget; the witness's public keys; L; R; TOKENS_MAX; ITEM_MAX (65,536); OBJ_MAX;
EVID_BUDGET_QUOTA; EVID_GLOBAL_QUOTA; NOTICE_QUOTA; OBS_QUOTA; ALARM_RESERVE; ALARMS_KEEP; INDEX_QUOTA;
INDEX_RESERVE; T_ORPHAN; CLOCK_TOLERANCE. RUN_ANSWER_MAX, INLINE_TOTAL_MAX and NOTICES_PER_RUN_MAX are the courier's; the first is named in
each statement.

**Proposed values, for the operator to set before any acceptance testing:** INLINE_TOTAL_MAX 32 KiB; OBJ_MAX 1 MiB;
RUN_ANSWER_MAX 8 MiB; EVID_BUDGET_QUOTA 64 MiB; EVID_GLOBAL_QUOTA 1 GiB; NOTICES_PER_RUN_MAX 16; NOTICE_QUOTA by E-Q-3a (for a budget that can come to 1,000 runs: 1,001 × 16 × 65,536
bytes, about 1 GiB); ALARMS_KEEP 64; ALARM_RESERVE 4 MiB; OBS_QUOTA 1 GiB (about a million accepted statements);
INDEX_QUOTA 1 GiB (about five million positions); INDEX_RESERVE 16 MiB; TOKENS_MAX 8. L and R have no proposed value. One
measurement bears on L: the courier of `e25a297`, which skips some phases, read a budget of 996 runs from nothing in
98 s on the demonstration machine, and the chain alone of a 996-run budget took 37 s and 508 MB. An L below a reading
from nothing means a courier that has lost its state can never bring a budget back. Acceptance tests MUST take L, R
and every limit as parameters.

**Durable storage at the mailbox**, each written whole and synced before any answer that depends on it: the mailbox
epoch; challenges and token states; items and receipts; the index of each chain epoch in order of acceptance, with
links; the open chain epoch, its head and its commit; the budget's anchor; statements accepted, and statements
refused with their reasons; evidence; evidence gaps; alarms; counts of refusals; clock anomalies.

**Earlier forms.** Notices and receipts of forms 1 and 2 MUST go on verifying as they do.

## 12. What must be shown, and by what

| What | By |
|---|---|
| Sections 5 to 8 as a state machine: tokens, epochs of the mailbox across a reboot, the strict order of 7.3 with a statement before its items, statement checks, chain epochs with COURIER_STATE_LOST, linking, evidence gaps, the status | a separately authored bounded model, with its bounds stated, mechanisms removed one at a time, and probes that its paths are reachable |
| Every MUST of sections 3 to 8 against an implementation | adversarial acceptance tests written from this text before the implementation, each naming the rule it tests and the capability it uses (K-CAP-1), each on a budget of its own (ACC-5) |
| That an implementation does what the model does | nothing here. Agreement between this text and a model says nothing about code |
| The clock across a real suspension; a hypervisor's pause | cannot be shown on the demonstration machine (N-4) |
| The production contract | only on a deployment where DP1 and DP2 hold (ACC-2) |

## 13. Trace: the owner's decisions of 21 November

| Decision | Rules |
|---|---|
| 1. UNKNOWN beside a verdict forbidden; the rule extended to every authenticated claim; pair identity; the capability S-5 needs | K-5; 3.2 (all nine findings), K-CNT-3, K-BEL-3; K-2, D-2, D-6; 1.2, K-CAP-1, 3.6 |
| 2. Lost courier state: fail closed, from sequence 0, an authenticated epoch transition, deduplication by identity | I-E-1 to I-E-9; 5.2; 5.6; ST-5, ST-6; SAF-4 to SAF-6, SAF-10 |
| 3. Evidence store, binding, limits and quotas, strict write order, exhaustion | section 6; 7.3 (DL-3, DL-4, M-D-1, M-D-2); E-X-1 to E-X-5; O-W-1 |
| 4. B-1 and B-2 mandatory; no acceptance on a non-compliant deployment | 1.3 (ACC-1 to ACC-5); N-5 |
| 5. COVERED as a time-bounded observation at a boundary; results without decisions; unbound reports; unsettled runs; cursor gaps; large evidence | C-1 to C-4; O-C-1 to O-C-4; 4.3; ST-6, O-3, O-4; 4.7; section 10 |
| 6. Separate agents: review, model, acceptance tests; no escalation; internal review only | "How it is checked"; section 12 |
| 7. Branch, stop conditions | the head of this document |

## 14. Changes from version 1, against the findings that caused them

F-numbers are the reviewer's; M-numbers are the modeller's. Both reports are, unchanged, in
`verify/STEP3_SPEC_REVIEW_AMEND16_2026-11-21.md`.

| Finding | Severity | What was changed |
|---|---|---|
| F1 | CRITICAL | three rooms for items (E-Q-2); retirement of observation parts (E-Q-4); names with no attempt get no record (D-12, O-P-2, O-R-1); names carried as hashes (I-2, O-P-1); order of delivery (O-6); the courier's outbox and a refused notice named in an alarm and in the status (I-O-5, O-W-2, E-X-4, C-1.6); a limit of notices for a run (O-L-3); N-6 says what is not claimed |
| F2 | CRITICAL | one thing at a time at the mailbox (E-Q-6); orphans counted inside the mailbox epoch (E-Q-5); SAF-11 |
| F3 | HIGH | position is checked before linking; a link takes the next position and moves the head (I-3, I-E-6, DL-3, DL-5) |
| F4 | HIGH | an item sent again is answered as the first time, before the position check (DL-2); what the courier does with each answer (5.6); the secret is kept until the statement is accepted (I-E-7); a known chain epoch is refused (I-E-3) |
| F5 | HIGH | an evidence gap is keyed by the evidence id and closed by holding that object (E-B-3) |
| F6 | HIGH | the evidence id and the stored bytes are of the signed projection only (D-2, E-1); added fields are counted, not findings (3.6, O-P-1); E-X-1 corrected |
| F7 | HIGH | the budget's anchor, kept across chain epochs and checked on every statement (O-1 to O-4, I-E-2, ST-6, ST-8, SAF-10); the mailbox's own rollback (I-O-4, L-10) |
| F8 | MEDIUM | waiting times (K-N-3) |
| F9 | MEDIUM | one alarm for each reading (I-ID-2); C-1.4 |
| F10 | MEDIUM | a refused statement takes no position and uses nothing (7.4, I-E-7); the courier's state moves only on acceptance (O-7); C-1.5 and 8.2 agree |
| F11 | MEDIUM | an EQUIVOCATION notice whenever another finding holds beside K-MISSING (3.4) |
| F12 | MEDIUM | K-CLAIM and K-EARLY (3.2); K-FENCE's meaning, and a fence alone not a finding (K-7); the bound reports (I-K-1) |
| F13 | MEDIUM | belief needs the envelope's outcome to be `'value'` (K-BEL-1, K-BEL-4); A-CARRY's support corrected (O-C-1) |
| F14 | MEDIUM | INLINE only all together within a total (E-B-1, I-2) |
| F15 | MEDIUM | R = 0 forbids carrying (O-C-3) |
| F16 | MEDIUM | client names for each request, a signed request for a challenge (11, M-K-1); a known chain epoch refused (I-E-3); two processes with one key (I-4); GLOBAL_QUOTA (E-Q-1, 8.2) |
| F17 | LOW | the citations of 1.2, K-CAP-1, O-L-2, K-5 and section 11 corrected and labelled |
| F18 | LOW | L-4 and L-11 |
| F19 | LOW | M-K-3; D-13 and O-R-4; the status nonce is Q; sets; D-12; SAF-4 |
| M1, M2, M3, M4, M5, M6, M7 | CRITICAL (M1 to M3), HIGH | the same defects as F3, F4 and F16, F9, F5, F4, F4, F10, found by the model; corrected as above. For M7 also: any item refused for room ends coverage at once (C-1.6, 8.2, E-X-4) |
| M8 | MEDIUM | the refresh bound holds at the time of the status, not only when the statement is taken (C-1.7, STALE_CARRY, C-2, N-2, SAF-7) |
| M9 | MEDIUM | 7.4 says what an accepted and a refused statement do to the chain |
| M10 | MEDIUM | M-K-2 (the oldest ISSUED); M-K-3; ST-3 kept for its reason |
| M11 | MEDIUM | a statement never spends a token of another budget (7.4) |
| M12 | MEDIUM | a request for a challenge names the mailbox epoch and is refused when replayed (M-K-1, 11) |
| M13 | MEDIUM | the courier's action on EVIDENCE_MISSING (I-O-6); orphans (E-Q-5) |
| M14 | MEDIUM | a mailbox with no record of a budget answers NEVER (8.2); L-10 |
| M15 | LOW | an EPOCH_OPEN closes the earlier epoch only when it is written (DL-5) |
| M16 | LOW | ST-8 and ST-6 are over the budget (the anchor); ST-7 is for the budget |
| M17 | LOW | a refusal at ST-5 is a loss of state (I-E-4) |
| M18 | LOW | the courier checks the challenge (O-1) |
| M19 | LOW | the courier sends an identity once in a chain epoch (I-O-8); O-S-1 |

**Not changed, and why.** F1's suggestion to reclaim room is taken for observation parts only; a notice about a run
is never reclaimed. F7's suggestion of a second checkpoint is met by one checkpoint that names the anchor. The
continuity secret is kept although the reviewer judged it redundant: the model's mutant without it lets a courier that
resumes from the mailbox's head be counted (SAF-4 broken in 7 steps), which is what I-E-8 says it is for.

### Changes from version 2 to version 3

F20 to F29 are the reviewer's findings on version 2 (Part 3 of the reports).

| Finding | Severity | What was changed |
|---|---|---|
| F20 | HIGH | waiting times are counted from the first reading that saw the run so, whole or not, and are taken as over in any reading that is not whole (K-N-3, O-7) |
| F21 | HIGH | a refused item takes no position and is signed again for the next one; a refused item never holds back a later one (I-3, I-O-5, I-O-6) |
| F22 | HIGH | "binds" defined; an evidence gap is a state that begins again if the object is absent; an object a held notice binds is never an orphan (E-2, E-Q-5, E-B-3, DL-5) |
| F23 | MEDIUM | the sizing of NOTICE_QUOTA as a formula, and the proposed values from it (E-Q-3a, 11) |
| F24 | MEDIUM | each index entry is charged to its item's own room; the finite life of OBS_QUOTA stated (E-Q-2, E-Q-3a) |
| F25 | MEDIUM | the courier stores again the objects of the gaps the challenge lists (O-1, I-O-7) |
| F26 | MEDIUM | an absent signed field is read as null (D-2) |
| F27 | MEDIUM | twelve bound reports (I-K-1) |
| F28 | MEDIUM | receipts are compared only within the open chain epoch (I-O-4) |
| F29 | LOW | 1.2 corrected in two places; a new request nonce after no answer (M-K-1); clearing an anchor is outside the specification (O-3); CRASH (O-L-2); K-PHASE's title |

### Changes from version 3 to version 4

F30 to F32 are the reviewer's findings on version 3 (Part 4 of the reports).

| Finding | Severity | What was changed |
|---|---|---|
| F30 | MEDIUM | a room of its own for index entries and EPOCH_OPEN items, with a reserve for notices, alarms and EPOCH_OPEN; alarm bodies bounded by ALARMS_KEEP; the finite life of a mailbox at given quotas stated, and what is refused in what order (E-Q-2, E-Q-3a, E-Q-4, E-X-4, N-6, 11) |
| F31 | MEDIUM | only a notice about a run is kept to be sent again; any other item that is refused is dropped (I-O-1, I-O-5) |
| F32 | LOW | the sizing formula counts the runs allowed back and the budget's own notice (E-Q-3a); reaching the limit of notices for a run stated as a loss of liveness (O-L-3); proposed values (11) |
