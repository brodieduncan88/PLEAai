# Amendment 16, final specification round: the separate agents' reports, as returned

21 November 2026. Private working material. This file holds, without change, the reports of the separate Opus-tier
agents the owner authorised for the final specification round. By the white paper's rule (revision 16, section 3) they
are **internal review** and **separately authored verification**: checks by other AI sessions instructed by the
author. They are not independent validation. Agreement between a model and the specification is not evidence about any
implementation.

**How to read it.** Each part is one agent's answer, saved exactly as returned (the agents' file tool refuses to write
report files, so each returned its report as text). Their scripts, models and outputs are in
`tests/diag_amend16_spec/`. What was done with each finding is in section 14 of the specification
(`verify/STEP3_SPECIFICATION_AMEND16_2026-11-21.md`) and in the round's summary. Parts are added in the order the
reports came back; none is edited afterwards.

| Part | Agent | On | Returned (UTC) |
|---|---|---|---|
| 1 | the reviewer | specification version 1 (commit `1495320`) | 20:44 |
| 2 | the modeller | specification version 1 | 21:39 |

---

# Part 1. The reviewer, on version 1, as returned

[tier: opus]

# Amendment 16, Step 3 specification v1: internal review (round 2)

21 November 2026. This is an internal review by one Opus-tier session, instructed by the author. It is not independent validation and must not be described as such. I spawned no subagents and did not escalate to any other model. I do not give a GO or NO-GO.

**I did not save `G/review2/report_v1.md`.** My operating rules forbid writing report files, so this text is the report. Scripts and outputs are under `G/review2/`.

**Labels.**
- **RUN**: I ran it on the real, unchanged components and saw the output in the file named.
- **ARGUED**: from reading the code or the text, or from reasoning. Not tested.

**What I ran.**
- Script: `/tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad/amend16/gate/review2/rv2_probe.py`.
- Harness: `…/gate/review2/gate_common.py`, a copy of the pack's harness with one change: `VT.OUT` is redirected to `review2/out/deploy`, so nothing is written under the pinned tree.
- Output: `…/gate/review2/out/rv2_probe_run1.txt` and `…/gate/review2/out/rv2_probe.json`.
- Database `plea27`, one deployment (RV2). It was stopped afterwards, and nothing listens on 8971, 8972 or 8974.

**Powers I used.**
- `plea_local`, the governor certificate (POST /accept and the gate host), and the courier certificate (GET /run and /chain).
- The harness process held the gate's private key (it lives in `deploy.Services`). None of my probes signed anything with it; I checked this by reading my script.
- **CAP-OWNER, labelled:** I used the `plea`/`plea` password once, to list database names. No data was read.

**Integrity checks (RUN).**
- The 11 named source files of the pinned copy are byte-identical before and after (`review2/out/src_before.sha256`, `sha256sum -c` all OK).
- Five of them are identical to `git show e25a297:<file>`.
- `/home/user/PLEAai` is on `verification-amendment-16` at `0da1a85`, with a clean status.

---

## 1. Findings

Numbering is stable for the next round.

| # | Sev. | Rule(s) | Defect | Counterexample | Suggested correction |
|---|---|---|---|---|---|
| **F1** | **CRITICAL** | E-Q-2, E-X-2, E-X-3, I-ID-3, O-P-1, O-R-1 | Item room is never given back, and only alarms have a reserve. OBSERVATION_PART and COVERAGE items are never deduplicated or retired. Every run named by any decision gets an observation record, even a name with no attempt. Once ITEM_QUOTA minus ALARM_RESERVE is used up, a **FAIL notice** (an outcome notice, not an alarm) is refused with 507. No rule ever delivers it later. E-X-2's "the notices of other runs are still delivered" is then false. | 1) With CAP-DB, the service POSTs ACCEPT_RESERVATION or RECONCILE for names that do not exist, each 512 astral characters long. **RUN Q3:** each is DENIED and recorded; GET /run answers 200; the name's canonical size is 6,146 bytes; no attempt is created. 2) Each name is read under O-R-1 and recorded under O-P-1. About 44,000 such names, or about 900,000 if names are hashed, fill 256 MiB (ARGUED). 3) An honest run then FAILs. Its FAIL notice gets 507 at DL-4, and the budget is NOT COVERED with MAILBOX_REFUSED. The FAIL is never held. Honest operation also gets there over the life of a budget: a REFRESH of 1,000 runs every R adds about 0.3 MB (ARGUED). | Reserve room for outcome notices, bounded per run. Deliver notices before observation parts. Supersede or reclaim the observation parts of statements that are no longer current, keeping a digest of them in the chain. Carry run names as hash and length. Keep a refused notice in the courier's durable outbox, and name it in the status (NOTICE_REFUSED, with the run). |
| **F2** | **CRITICAL** (needs a timing window; no adversary needed) | E-Q-4, E-2, DL-4/DL-5, C-1.3, C-2 (5th bullet) | Nothing makes the orphan sweep atomic with DL-4 and DL-5. An object can be removed after DL-4 has found it held and before DL-5 writes the item that names it. | 1) The courier POSTs evidence O and gets HELD. 2) Delivery of the EQUIVOCATION notice is delayed beyond T_ORPHAN (mailbox down, or a chain-position retry; see F4). 3) DL-4 finds O held. 4) The sweep finds O named by no held item and removes it. 5) DL-5 writes the notice saying HELD. No gap is recorded, the next statement gives COVERED, and C-2's "every piece of evidence a finding rests on is held" is false. | Serialise the sweep with DL-4 and DL-5 for each budget, and re-check holdings under that lock. Never sweep an object younger than T_ORPHAN within the current mailbox epoch. |
| **F3** | **HIGH** | DL-2 before DL-3, I-E-5, I-3, SAF-6 | A linked item never reaches the chain-position check, and the rules do not say whether linking moves the head. It is reached on every reading from 0 of a new epoch (I-E-5), and on every reading if K-N-1 is read as "send again what is called for". | 1) In epoch E1, FAIL notice X is held at k=5. 2) The courier loses its state and opens E2. 3) The reading from 0 sends X at k=2. DL-2 links it, and I-E-5 records (k=2, identity). 4) If the head does not move, the next item (k=3, prev=A(2)) fails DL-3; by M-D-3 the courier "has lost its state" and opens E3, and the same happens again for ever. 5) If the head does move, a resend of X (lost response) is linked again, with no check of its k or prev, and the index diverges. | Put DL-3 before DL-2. A link takes the next position: check k and prev, advance the head with A(k) = H(A(k−1), identity), and answer with the first receipt. |
| **F4** | **HIGH** | M-S-1, DL-3, M-D-1, M-D-3, I-E-3, I-E-6 | Sending again after a lost response cannot work for items that are never deduplicated (COVERAGE, OBSERVATION_PART, EPOCH_OPEN). M-S-1 sits in 7.4, after DL-3. M-D-1 ("deliver the items, send again") also contradicts M-D-3, because in M-D-1 the courier's position is ahead of the mailbox's head. Nothing says the courier must keep s_j until it knows how statement j went. | 1) Statement S at k is accepted; the response is lost. 2) The courier sends S again. DL-3 sees k equal to the head, not head+1, and answers 409 CHAIN_POSITION. 3) By M-D-3 the courier has "lost its state" and opens a new epoch, with a reading from 0 (98 s or more; 508 MB of chain at 996 runs). A courier that overwrote s_j with s_{j+1} before learning the outcome also cannot reveal again, and must open a new epoch. A resent EPOCH_OPEN re-opens an epoch with the same id. | Before DL-3, for every item: if its digest is already held in this epoch, return the first receipt. Define a DL-3 refusal: if the mailbox's head is a prefix of the courier's chain, deliver what is missing; otherwise state is lost. Keep s_j until statement j is receipted or refused. Refuse an EPOCH_OPEN whose chain_epoch was seen before (answer with its first receipt). |
| **F5** | **HIGH** | E-B-3, E-B-4, DL-2, I-ID-1 | An evidence gap can never be closed. The item that should close it has the same identity, because holding status is not in the basis, so DL-2 links it and it is never verified. And if evidence ids change, the identity changes, and the gap's own identity is never sent again. | 1) An EQUIVOCATION notice is sent with NOT_HELD(QUOTA), and a gap is recorded. 2) The operator raises the quota. The courier uploads the evidence and sends the same notice with HELD. 3) DL-2 links it. 4) The gap stays, and the budget is NOT COVERED (EVIDENCE_GAP) for ever. | Key gaps by (budget, evidence id). Close a gap by a verified POST /evidence of that id, or by any later item that holds it. Handle gap-closing before DL-2. |
| **F6** | **HIGH** | D-2, E-1, I-ID-1, E-X-1, E-X-4, 5.3 | The evidence id is taken over the whole report object, including fields the gate never signed, and the witness stores and serves those fields. **RUN Q2 (CAP-DB):** a genuine FAIL report sent again with an unsigned 100 KB field was answered `DUPLICATE VERDICT_RETRY AUTHORISED`. GET /run served both: one pair, the same signature, two evidence ids, 484 and 100,538 bytes. | (a) Once any finding exists, CAP-DB can change the EQUIVOCATION identity at will, giving new notices without end and using up ALARM_RESERVE. That defeats decision 2's "prevent duplicate notices". (b) The service is the governor, so it can pad the **recorded** report itself when it first sends it (ARGUED from `derive_verdict`, which ignores extra fields). Any later finding then needs that report bound, and it is larger than OBJ_MAX, so the gap is permanent. (c) E-X-1 says CAP-DB adds only strays. CAP-DB in fact makes gate-signed, in-scope, AUTHORISED reports of any size. | Define a report's identity, and the bytes stored for it, as the canonical form of the signed projection only: {kind, root, aid, nonce, claim, result_digest, signer, signature}. Ignore unsigned fields everywhere, and count extra fields as an anomaly, not a finding. |
| **F7** | **HIGH** | ST-6, ST-8, I-E-3, I-E-4, O-3 | Opening a new chain epoch throws away the detection of fork and rollback. ST-6 requires `at = 0`, and ST-8 does not say whether "the last accepted N" spans epochs. A mailbox restored from backup looks to the courier like its own state loss, gets the label COURIER_STATE_LOST, and no alarm is raised. | 1) The witness database is restored from an older backup (an operational fault), or rewritten (CAP-OWNER). 2) On a single-host deployment the courier loses its state in the same event. 3) In the new epoch, the reading from 0 reads the shorter or forked chain, a statement is accepted, and the budget is COVERED. The mailbox had already accepted (N1, head1), which this chain contradicts. FAIL decisions after the backup are gone. | The first statement of epoch e > 1 must also carry a checkpoint with `at` = the previous epoch's last accepted N, and `head_at` equal to its head; the mailbox checks it. Make ST-8 apply to the budget across epochs. Add a MAILBOX_ROLLBACK alarm, raised by the courier when its receipted head is ahead of the mailbox's. |
| **F8** | MEDIUM | 3.4 (UNVERIFIED "after the waiting time"), K-N-1, I-E-4 | The waiting time starts from the courier's memory, which K-N-1 forbids and a loss of state resets. | CAP-DB withholds the result of an honest FAIL. The courier restarts its epoch more often than the waiting time W (likely under F4). UNVERIFIED is never sent, while COVERED statements from readings from 0 are accepted. | In a new epoch, treat the waiting time as already over (send UNVERIFIED at once), or record its start at the mailbox. |
| **F9** | MEDIUM | I-ID-2, C-1.4, SAF-7, O-S-1 | The identity of OBSERVATION_INCOMPLETE leaves out N and the token. A second occurrence after recovery is linked, and the rules do not say whether a link is "accepted after S". | WITNESS_UNREACHABLE gives alarm A, then S is accepted (COVERED), then the witness is unreachable again. The new alarm is linked to A, and the budget stays COVERED until S's token is older than L. The status shows a stale alarm. | Count any alarm delivered or linked after S. Put the token in the alarm's identity, bounded by one alarm per reading. |
| **F10** | MEDIUM | 7.4, I-E-6, ST-6, C-1, 8.2 | It is undefined whether a SPENT (422) statement takes a chain position or uses up its reveal. It is undefined whether the cursor moves after a reading that was not whole. C-1 can hold while 8.2 gives STATEMENT_SPENT. | A statement fails ST-3 and is SPENT. The courier counts k as used and the mailbox does not, so the next item gets DL-3 and a new epoch follows (F4). Or the cursor moved to N2 after a reading that was not whole, and the next statement fails ST-6 every time. | Say: a refused statement takes no position and uses no secret; the cursor, the unsettled set and the carried observations move only when a statement is accepted. Add "no later SPENT statement" to C-1, or drop STATEMENT_SPENT from 8.2. |
| **F11** | MEDIUM | 3.4 rows 1–2, O-W-1 | When K-MISSING and another finding both hold, the precedence is undefined. If NOT OBSERVED wins, a visible conflict gets no EQUIVOCATION notice. | During a key rotation the reader lacks key G2 (P-KEYS), so an AUTHORISED report under G2 gives K-MISSING. A CAP-KEY conflict under G1 on the same run then gets no notice. | Make an EQUIVOCATION notice whenever any finding other than K-MISSING holds. K-MISSING only adds "not whole". |
| **F12** | MEDIUM | 3.2, D-6, K-FENCE, 3.6, 5.3 | Section 3 does not cover every gate-signed claim. (a) An EFFECT_REPORT whose claim is not EFFECT, NO_EFFECT or UNKNOWN, or a FENCE_REPORT with another claim, a nonce or a digest, is no finding. (b) An in-scope verdict report at a decision made before the run was consumed (a RECONCILE with label AUTHORISED and code NOT_CONSUMED, which the chain itself proves) is no finding, though the honest gate never signs before ACCEPT_INTENT. (c) **RUN Q1 (CAP-DB):** the honest gate host signed `FENCED_NO_START` for a run the chain holds CONSUMED, given only a DUPLICATE ACCEPT_RESERVATION receipt. RELEASE with it gave `DENIED CONSUMPTION_IS_FINAL BOUND_FENCE`. The run was not crossed; CROSS was DENIED RECEIPT_NOT_DELIVERED. So K-FENCE's "meaning" ("signed that the run never started") overstates what a fence report says, and a rule treating "fence beside a consumption phase" as a finding would give CAP-DB notices at will. (d) 5.3's "the earliest whose pair differs" has no reference point when there is no recorded verdict. | For (b): CAP-KEY plants a forged PASS at INTENT_PENDING, then RECONCILEs it after ACCEPT_INTENT without calling the gate. It is believed, although the chain shows the early signature. | Add K-CLAIM (malformed claim or kind) and K-EARLY (an in-scope report at a decision whose phase was before consumption). State that a fence report beside a consumption phase is not a finding, and why (Q1). In 5.3, without a recorded verdict, bind the two smallest pair ids. |
| **F13** | MEDIUM | O-C-1, K-BEL-1, 4.3 | The support for A-CARRY over-reads its test. `store.py` line 838 replaces any stored row whose `outcome` is 'unknown', and `gate_result_store_run1.txt` (second case) shows plea_local replacing one with a PASS value, with no decision added. K-BEL-1's "the stored result is a value" does not say whether this means the envelope or its `value` field. | CAP-DB stores `{'outcome':'unknown','value': v}` with H(v) equal to the digest. A courier that unwraps `value` believes it and carries the run. CAP-DB then replaces it with no decision, which breaks A-CARRY. | Belief requires the envelope's `outcome == 'value'` and H(envelope.value) equal to the digest. Correct the "(by test)" sentence. |
| **F14** | MEDIUM | E-B-1, 5.3, I-2, ITEM_MAX | INLINE is limited for each report (16 KiB), not for the notice. A notice may name up to about 12 reports. | Two findings with four reports of 16 KiB each already exceed 65,536 bytes. Such an EQUIVOCATION is refused at DL-1, so I-2's "can always be delivered" is false. | Allow INLINE only while the whole notice stays within ITEM_MAX less overhead; otherwise use HELD. |
| **F15** | MEDIUM | O-C-3, ST-7 | "With R = L every reading reads every run" is false. ST-7 lets a run be carried whenever the oldest carried statement's token is at most R old, which an earlier token can be when the current reading is quick. | Token T1 at t0, statement at t0+10 s; token T2 at t0+20 s, INCREMENTAL. T1's age is 30 s, which is at most L, so runs are carried. | Say R = 0 forces whole readings, or state the exact condition. |
| **F16** | MEDIUM | M-K-1, §11, I-E-2, DL-3, I-4, E-Q-1 | Who may call each request, and how it is authenticated, is not stated. `/challenge {root}` carries no signature. "Admitted reader" is undefined. An EPOCH_OPEN is accepted unconditionally at DL-3, so a replayed old one closes the open epoch. Two processes holding one courier key livelock: each EPOCH_OPEN closes the other's epoch. The global evidence quota lets one budget make every other budget NOT COVERED, and the status gives no reason. | Anyone who can reach `/challenge` issues TOKENS_MAX challenges and voids the courier's token. The deployed mailbox admits only the TLS name `courier` (`deploy.py` 110, ARGUED), which is a boundary the spec does not carry. | Specify the TLS client names for each request and a signed challenge request. Refuse a known chain_epoch. Name the cross-budget reason (GLOBAL_QUOTA). |
| **F17** | LOW | 1.2, K-CAP-1, O-L-2, §11 | Over-reading of evidence. Details in section 4. The test cited for K-CAP-1 had the gate key in reach, and its deployment GC was written under the pinned tree. | — | Correct the citations and labels as listed in section 4. |
| **F18** | LOW | L-4, K-BEL-1 | L-4 assumes short names. Every decision's observation carries every attempt's aid (6,146 bytes possible, **RUN Q3**), so a 1,000-run budget's chain can be about 50 times "0.5 GB" (ARGUED). **RUN Q4:** jsonb rewrites 1e300, 1.5e17 and -0.0, so an honest result holding such a number is never believed (UNVERIFIED for ever). | — | State that the chain cost scales with the name lengths the service chooses. State the canonical-form limit in K-BEL-1. |
| **F19** | LOW | various | Wording. (1) M-K-3 ("only ISSUED can change") contradicts M-K-4 (USED becomes EXPIRED). (2) "Named by a decision" is undefined for RECOVER (whose op[1] is a boolean), REREGISTER and HOLD. (3) The status nonce is called `R`, the same letter as the refresh bound. (4) I-ID-1 should say *set* of evidence ids. (5) "Runs of the budget" is undefined for names with no attempt (Q3). (6) SAF-4 should say "within the open chain epoch": a courier with no state may open an epoch, and its later statements count. | — | — |

---

## 2. Rule by rule

**(a) Section 3: the consistency rule.**
- The count rule (K-CNT-1 to 3) matches the code. An evidence row is written in the same transaction as its decision, and a JSON `null` is refused.
- Pair identity is right, and I found no honest history in the shipped topology that is wrongly failed. The one honest-looking case is an UNKNOWN followed by a verdict, which needs a second gate host or a stalled lease (K-5, by the owner's decision).
- The key-set precondition (P-KEYS) is stated. The phase rules leave gaps: before-consumption reports and malformed claims (F12).
- Belief is right, except for the envelope question (F13) and the canonical-form limit (F18).
- A dishonest history that passes: only N-3 (a forgery before the witness sees anything), plus the F12(b) variant, which could be detected.

**(b) Separating CAP-DB from CAP-KEY (1.2, 3.6).**
- I found **no CAP-DB path** to K-CONFLICT, K-NONCE, K-FENCE, K-PHASE, K-DIGEST or K-UNKNOWN-VERDICT, and none to a believed false PASS.
  - ARGUED from the code: the gate host's one-shot claim per (root, aid); the nonce binding executor, tool and arguments; the ACCEPT_INTENT receipt binding the nonce and requiring APPLIED or DUPLICATE.
  - RUN: Q1 and Q2, plus the pack's S1 to S4 as read.
- What CAP-DB *can* make:
  - a genuine fence report for a consumed run (Q1);
  - gate-signed in-scope reports of any size and with many ids (Q2, giving F6);
  - unboundedly many named runs that do not exist (Q3, giving F1).
- The S-5 demonstration needed the gate key, and the forgery was made *after* the FAIL was recorded. Under these rules that case is K-CONFLICT, so it is detected; only the N-3 shape is not.

**(c) Section 4: the observation.**
- Results stored without a decision: handled, because a run that is not believed is never settled.
- NONE-labelled and late RELEASE reports: re-read by the courier (O-R-1, O-C-2). The record side is a stated limit (L-1).
- Remaining gaps: A-CARRY's support (F13), the refresh-bound claim (F15), cursor movement (F10), and forks across epochs (F7).

**(d) Section 5: identities, epochs and continuity.**
- Identities: F3, F4, F5, F6, F9, F16.
- The continuity secret adds nothing that A(k) and ST-6 do not already give (ARGUED). A copy taken after s_{j+1} was written *can* reveal it, and it is DL-3 that stops it. Its crash window is F4.
- Two couriers: livelock (F16).

**(e) Section 6: the evidence store.**
- Missing evidence can still give COVERED: F2.
- A failed run's notice can be lost: F1.
- Gaps that can never close: F5.
- Oversize caused by CAP-DB: F6.
- The INLINE limit: F14.

**(f) Section 7: time, tokens, order.**
- I found no replay, cross-budget use, cross-epoch use or stale-token path that passes ST-1 to ST-9 (ARGUED).
- Ages count from issue, on BOOTTIME, within one mailbox epoch, and a reboot or restart voids every token.
- A statement sent before its items burns no token, but it sets off the confusion of M-D-3 (F4).
- A rollback of the mailbox is not detected (F7).

**(g) Section 8: what COVERED claims.**
- C-2's fifth bullet can be false (F2).
- C-1 and 8.2 disagree (F10).
- E-X-2 promises delivery that F1 defeats.
- Liveness, notification and permanence are correctly *not* claimed (N-1, N-2, C-3).

**(h) Sections 9 to 11: interfaces and testability.**
- Missing:
  - authentication for each request (F16);
  - item retention and reclamation (F1);
  - paging and size limits on GET /items;
  - the courier's durable outbox;
  - a stated procedure for a reader to verify the item chain and its links;
  - T_ORPHAN across mailbox epochs.
- L and R have no values, so acceptance tests cannot fix their bounds.
- K-CAP-1 ("a CAP-DB test must not have the gate key within its reach") needs a harness in which the gate key sits in another process.

---

## 3. Findings of the previous review

**Phase 1.**

| Finding | Standing |
|---|---|
| V1 | ADDRESSED (K-CONFLICT) |
| V2 | Superseded by the owner's decision (K-5). A late UNKNOWN after a verdict is now a finding |
| V3 | ADDRESSED (K-CNT-3, K-PHASE) |
| V4 | ADDRESSED (K-BEL-1, K-BEL-2) |
| V5 | ADDRESSED (K-CNT-1, K-REC-1) |
| V6 | ADDRESSED (K-N-2) |
| M1–M4 | ADDRESSED (M-K, ST-1 to ST-4, M-T-2/3, SAF-3) |
| GET /coverage | ADDRESSED (C-S-1) |
| E1–E3 | ADDRESSED (5.3, E-B, K-DIGEST, K-NONCE). E1's hash: PARTLY, see F6 |
| Durability caveat | ADDRESSED (E-B-5) |
| Accumulator | ADDRESSED (I-3) |
| I1 | ADDRESSED (O-R-1, O-C-2) |
| I2 | ADDRESSED (O-R-1, "of any operation") |
| I3 | PARTLY (F7) |
| Evidence-pack issue 1 (contaminated whole-budget records) | NOT ADDRESSED in section 12's guidance |
| Pack issue 3 | ADDRESSED (3.6) |
| Pack issue 5 (gate_result_store over-read) | NOT ADDRESSED (F13) |
| Pack issue 6 (harness writes under the pinned tree) | NOT ADDRESSED: GC is under `src/outputs/verify_tests` |
| Pack issue 7 (owner-password reads) | ADDRESSED (part F) |
| Pack issue 9 | ADDRESSED (N-4) |
| Unprovables (a)–(h) | ADDRESSED (section 10, N-1 to N-5) |

**Phase 2.**

| Finding | Standing |
|---|---|
| B1.1 | ADDRESSED (D-5, K-NONCE, K-FENCE, K-PHASE) |
| B1.2 | ADDRESSED (K-4, 4.3) |
| B1.3 | ADDRESSED (K-3, P-KEYS, K-CNT-4) |
| B1.4 | ADDRESSED (K-2) |
| B1.5 | ADDRESSED (K-DIGEST, I-2) |
| B1.6 | PARTLY (F12d) |
| B1.7 | ADDRESSED (K-N-1). Waiting-time residue: F8 |
| B2.1 | ADDRESSED (DL-3, DL-4, M-D-1) |
| B2.2 | ADDRESSED (I-E-*), with the new defects F3, F4, F7 |
| B2.3 | ADDRESSED (C-2, bullet 4) |
| B2.4 | ADDRESSED (M-K-6) |
| B2.5 | stands |
| B3.1 | ADDRESSED |
| B3.2 | PARTLY (F12d) |
| B3.3 | ADDRESSED in form; malleable in substance (F6) |
| B3.4 | ADDRESSED (§11); "admitted reader" undefined (F16) |
| B3.5 | PARTLY (F3, F4, F14) |
| B3.6 (records need not carry deliveries) | NOT ADDRESSED |
| B4.1–B4.5 | ADDRESSED |
| B4.6 | ADDRESSED (not repeated) |
| C.1–C.14 | Not repeated in the spec, except C.8, which is ADDRESSED |
| D.1–D.6 | ADDRESSED |
| D.7 | NOT ADDRESSED |
| D.8 | ADDRESSED |
| E.1–E.5 | ADDRESSED |
| E.6 (model and tests) | Pending (section 12) |
| E.7 | ADDRESSED (K-5) |
| E.8 | ADDRESSED as blockers (ACC-1 to ACC-4) |
| F.1 | ADDRESSED |

---

## 4. Factual check

**Supported.**
- 1.2, table rows 2 to 6, by `gate_s5_capability_run2.txt` S1 to S5.
- D-11 and "3,456 rows": `gate_rows_as_service_run1.txt` gives 87 + 3,369, and the only RELEASE or RECONCILE decisions without a row are labelled NONE.
- K-REC-2 (P1).
- The figures 70,448, 200,435 and 5,002,287.
- L-4: 508,180,089 bytes, 7,968 decisions, 126,949 bytes in the last decision.
- M-T-1 and N-4 (`clocks.txt`).
- The DP1, DP2 and B-1 to B-3 quotations, and "property file line 21".

**Not supported, or over-read.**
1. Row 1 of 1.2, "the courier makes an UNVERIFIED notice": in S1 the courier made nothing. Only S6, with waiting time 0, made UNVERIFIED.
2. "S-1 the same" is not tested by `gate_s5_capability`.
3. Two things are code arguments presented as fact: the CAP-OS "double run", and K-5's "cannot arise in the shipped deployment".
4. O-C-1's "a stored value cannot be replaced (by test)" is contradicted by case 2 of the same test (F13).
5. O-L-2 attributes the S-6 figures to the service in a CAP-DB section. All three were made by signing with the gate key (CAP-KEY), and they carry no capability label. CAP-DB can do the same (my Q2 and Q3).
6. §11's "98 s, 996 runs" is from `measure.txt`: a budget of 1,398 decisions, read by the e25a297 courier, which skips some phases. It is not the 7,968-decision shape, whose chain alone took 37 s and 508 MB.
7. K-CAP-1 is not met by the test it cites: the gate key was in the harness's process.
8. 3.6's K-MISSING "by test" rests on the threat model's DP3 row. I did not see the raw output.
9. I-2's "can always be delivered" is false (F14).
10. Not checked: the branch named in the spec's header.

---

## 5. What cannot be proven without changing the witness or the store

- Which report sat at a decision, and whether a decision labelled NONE carried one (L-1, L-2).
- Whether GET /run is complete. It is unsigned and takes no nonce (L-7).
- That a stored result was not changed by a role other than `plea_local` (L-3).
- Any bound on the cost of reading the chain: it grows with the square of the runs and with the name lengths the service chooses.
- A forgery made before the witness sees anything (N-3, B-3).
- A list of the budgets (L-8).
- A pause of the machine from outside it (L-9).
- That the courier read every run (I-E-7).
- That the mailbox's own state was not rolled back. The mailbox cannot see this itself; only receipts held elsewhere can.

**What only a deployment where DP1 and DP2 hold can establish.**
- That `plea_local` is the service's only power, which is what A-CARRY rests on.
- That the courier's state, the continuity secret, the mailbox's clock and its durable store are beyond the service's reach.
- That the separation of TLS names is a real boundary.
- Acceptance of the production contract (ACC-2).

---

## 6. What the evidence supports

The evidence supports the following, and no more.
- The separation of capabilities in 1.2 and 3.6 holds as far as I tested:
  - in my probes and in the pack's S1 to S4, no replay by CAP-DB made a failing run read PASS or produced a finding;
  - CAP-DB can obtain fence reports for consumed runs (Q1), gate-signed reports of any size with many evidence ids (Q2), and unboundedly many decisions naming runs that do not exist (Q3).
- Section 3's rule is sound on the code for the shipped topology, apart from the completeness gaps in F12.
- Sections 5 to 8 are not yet consistent enough to model or implement:
  - the order of linking and position checks (F3, F4) and the closing of evidence gaps (F5) contradict each other;
  - two rules as written permit a lost FAIL notice (F1) or a COVERED with evidence missing (F2);
  - continuity across epochs drops fork and rollback detection (F7).

All of this is internal review on one development machine where DP1 and DP2 do not hold. It establishes nothing about the production contract.

Files:
- `/tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad/amend16/gate/review2/rv2_probe.py`
- `/tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad/amend16/gate/review2/gate_common.py`
- `/tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad/amend16/gate/review2/out/rv2_probe_run1.txt`
- `/tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad/amend16/gate/review2/out/rv2_probe.json`
- `/tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad/amend16/gate/review2/out/src_before.sha256`

---

# Part 2. The modeller, on version 1, as returned

[tier: opus]

# Bounded model of Amendment 16 v1, sections 5 to 8: report

This is internal, separately authored verification. It is not independent validation. A "pass" here means no violation was found in a finite state space at the stated bounds. It is not a proof for unbounded parameters, and it says nothing about any implementation. The model was written only from `G/spec/SPEC_v1_as_sent_to_review.md` (SHA-256 69e83c7f…aade68). I read no earlier model, review or repository document.

**The file tool refused to write `REPORT.md`, so this answer is the report.** Everything else is under `G = /tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad/amend16/gate`:
- `G/model2/model.py`: the model, organised by rule id (DL-1 … DL-6, ST-1 … ST-9, M-K-*, M-T-*, C-1.*).
- `G/model2/configs.py`: configurations and bounds.
- `G/model2/declare.py` and `G/model2/declared/`: the declarations, with `SHA256SUMS`, `DECLARED_AT` and `CODE_AT_DECLARATION.sha256`.
- `G/model2/run_all.sh` and `G/model2/summarize.py`.
- `G/model2/results/run1/<config>.json` and `<config>.console.txt`, one pair per configuration (60), plus `SUMMARY.md`.
- `G/model2/diag_age.py` and `G/model2/results/diag_age.json`: one undeclared diagnostic, labelled as such.
- `G/model2/results/run0_first_attempt/`: a first run, INCOMPLETE, kept.
- `G/model2/sizing.py` and `G/model2/results/sizing_logs/`: state counts only, no verdicts.

**Process disclosures:**
- I first left sizing logs and scripts in the scratchpad root. I moved the logs into `G/model2/results/sizing_logs/` and deleted the scripts.
- `model.py` is unchanged since the declarations were written (SHA-256 c0be4e37…). `configs.py` only gained four larger-bound configurations at 21:32Z, declared before their own first run.

## 1. What I modelled

**Parties**
- One budget B with courier key K0. In the XB family there are also tokens of a second budget with key K1, or with K0 when one key serves both.
- One mailbox, and a witness that is trusted and append-only.
- One honest courier. The CV_ configurations use couriers that do not follow I-E-3.
- One reader (STATUS family only).
- An adversary that controls the network and the environment and cannot forge any signature.

**State**
- Real time, as a ghost.
- Mailbox clocks: mailbox epoch, CLOCK_BOOTTIME tick, CLOCK_MONOTONIC tick, wall-clock offset.
- Tokens: serial, budget, key, mailbox epoch, tick, wall time, monotonic tick, a ghost real issue time, and ISSUED/USED/SPENT/VOID. EXPIRED is computed from the age.
- Chain: the open chain epoch, the head (k, A(k)), the commit held.
- Holdings: held identities with first receipt and evidence claim, and stored identities.
- Accepted statements, each with ghosts: the notice identities its reading called for, the evidence its findings rest on, and the observation record.
- Flags and order: the STATEMENT_SPENT and ITEMS_REFUSED flags, evidence gaps, held evidence, epochs seen, and the order of the last accepted alarm, the last alarm taken (stored or linked) and the last EPOCH_OPEN.
- The witness: its decisions and each run's standing.
- The courier's durable state: epoch, k, its own A-chain, secret index j, cursor, last statement, the mailbox epoch of that statement, the per-run observation record, phase, token, outstanding items, pending statement.
- One backup copy of the courier's state, every message ever sent, every challenge issued, and bounded counters.

**Abstractions**
- Hashes and secrets are exact symbolic values.
- A run's standing is one of:
  - `u`: unsettled; calls for an outcome notice.
  - `p`: settled; calls for no notice.
  - `x`: settled; calls for an outcome notice.
  - `f`: a finding; calls for an EQUIVOCATION notice resting on one piece of evidence; never settled.
- Identities:
  - a notice (I-ID-1): (run, standing, number of the last decision naming the run);
  - an alarm (I-ID-2): (reason, run or null);
  - EPOCH_OPEN and COVERAGE (I-ID-3): unique per item.
- A reading is one atomic event. A reading that is not whole has one reason: DEADLINE or EVIDENCE_NOT_HELD(run).
- Not modelled: OBSERVATION_PART items, byte sizes, OBJ_MAX and RUN_ANSWER_MAX.
- ITEM_QUOTA and ALARM_RESERVE are counted in items. CLOCK_TOLERANCE is 0. T_ORPHAN means "at any time".
- Acceptance order is kept as ranks.
- The search key is the 64-bit Python hash of the state; a collision would silently prune a state.

**Moves**
- Courier:
  - opens an epoch;
  - takes a fresh challenge, or is handed any earlier genuine one;
  - reads: FROM_ZERO when the epoch has no statement, REFRESH, INCREMENTAL when something would be carried, and REFRESH after a change of mailbox epoch;
  - delivers any outstanding item, in any order, and acts on the answer;
  - re-uploads evidence it keeps.
- Adversary:
  - delivers any message ever sent, at any time, any number of times, with the answer lost;
  - time passes; sets the wall clock back or forward; suspends the machine;
  - restarts or reboots the mailbox;
  - makes the courier lose its state, takes a copy of it (between readings) and restores it later;
  - replays a challenge request; another budget's courier takes a token;
  - removes orphaned evidence;
  - erases the mailbox's record of the budget (WIPE);
  - CAP-OWNER changes a settled run (OA_ configuration only);
  - replays an old status to the reader.
- Witness: a decision sets a run's standing; a stored result moves `u` to `p` or `x` without a decision (L-3).

**Reduction.** Witness moves are offered only while the courier holds a token it has not yet read with. This is sound here because no other move and no property reads the witness.

**Readings I chose where the text is not definite.** Each one is also a finding in section 5.

| Id | Text | Literal reading (FD_) | Alternative reading (AR_) |
|---|---|---|---|
| R1 | DL-2 comes before DL-3; I-E-5 "records (k, identity, …) in the new chain's index" | the link is made at the item's own k and prev with no position check, and the head moves there | link only at k = head.k+1 with prev = head A |
| R2 | E-B-3 against DL-2 | a later item of the same identity is linked and never reaches DL-4 or DL-5, so the gap never closes | a linked item that says HELD closes the gap when the evidence is held |
| R3 | C-1.4 "accepted after S" | a linked alarm is not "accepted" | a linked alarm counts as accepted |
| R4 | DL-3 "It is an EPOCH_OPEN (then I-E-2)" | any EPOCH_OPEN passes, any number of times; C-1.1 identifies the open epoch by its id | an EPOCH_OPEN of an epoch already seen is refused |
| R5 | whether a COVERAGE item takes a chain position | accepted: stored, head advances; refused (422): kept as evidence, head unchanged | same |
| R6 | M-D-1 against M-D-3 ("own position") | the courier continues if the head is a prefix of its own chain, or its own EPOCH_OPEN is not yet taken; otherwise its state is lost | same |
| R7 / R8 | M-K-3 against M-K-4; M-K-2 "the oldest" | EXPIRED is computed for any state except VOID; "oldest" means the oldest ISSUED | same |
| R9 | I-E-2 "at DL-3", before DL-4's room check | I-E-2 is applied when the item is written | same |
| R10 | ST-8 "the last accepted N" | over the whole budget | same |
| R11 | the courier's action on 409 EVIDENCE_MISSING | re-upload the evidence and redeliver the same item | same |
| R12 | the courier's checks of a challenge (O-1, O-2) | none; it uses any genuine challenge | same |
| R13 | "a refusal by I-E-6" (I-E-3) | a 422 that includes ST-5 means the courier's state is lost | same |

**Bounds** (`configs.py`)
- Defaults: TOKENS_MAX 1, L 1, R 0, TMAX 1, 2 readings, 1 chain epoch.

| Family | Bounds beyond the defaults |
|---|---|
| CHAIN | 2 runs, 2 decisions, standings u/x, 2 epochs, 1 loss |
| CHAIN_L | as CHAIN, plus standing p, TMAX 2 |
| AR_CHAIN_XL | as CHAIN_L, plus 3 readings |
| RESTORE | 3 readings, 2 epochs, 1 loss, 1 copy, 1 restore |
| EPOCH | TMAX 2, 1 reboot, 1 restart, 1 wall-clock move |
| EPOCH_L | as EPOCH with TMAX 3, L 2, R 1 |
| SUSP | TMAX 3, 1 suspension, 1 wall-clock move, 3 readings |
| XB | TMAX 2, 1 token of the other budget, 1 replayed request, old challenges handed to the courier |
| ALARM | 3 readings, L-3, readings may fail |
| AR_ALARM_L | as ALARM with 4 readings, TMAX 2 |
| EVID | standings u/f, 2 decisions, 3 readings, evidence refusals, orphan removal |
| AR_EVID_L | as EVID with 4 readings |
| SKIPEV | 2 runs, standings x/f, orphan removal |
| AR_SKIPEV_L | as SKIPEV, plus refusals and 3 readings |
| STATUS | 2 questions, 3 statuses |
| QUOTA | 4 items, reserve 1, 3 readings |
| WIPE | 2 decisions, 3 readings |
| CARRY | 2 runs, standings u/x/p, 3 readings |

**Totals.** All 60 searches completed: 19.9 million states, about 12 minutes of compute.

## 2. Properties, in terms of the model's state

Checks are made at ACCEPT (when the mailbox counts a statement), at every item taken, or at every state where C-1 says COVERED by statement S. "True" means ghost real time and the ghost mailbox epoch, which changes on every restart even in mutants.

| Id | Statement |
|---|---|
| SAF1 | At ACCEPT: the token's stored state was ISSUED, its true age ≤ L, it is of budget B and key K0, and of the true current mailbox epoch. |
| SAF2 | At ACCEPT: every identity in the A(k−1) the statement commits to was already stored, and every held notice that says HELD has its evidence held. |
| SAF3 = central (ii) | COVERED by S implies S's token has true age ≤ L and was issued in the true current epoch. |
| SAF3B_ACC | At ACCEPT of an INCREMENTAL statement: the statement it names as oldest_carried has a token of true age ≤ R. |
| SAF4 | At ACCEPT: the maker held the secret it reveals, and that secret is the preimage of the commit held. |
| SAF5 = central (iii) | COVERED by S implies S was accepted after the last EPOCH_OPEN taken, and a FROM_ZERO statement of the open epoch was accepted after that EPOCH_OPEN and not after S. |
| SAF6 | An item whose identity is held is never stored twice; a link answers with the first receipt unchanged; stored identities never shrink (except by the WIPE move itself). |
| SAF7 | COVERED by S implies no evidence gap, and no OBSERVATION_INCOMPLETE item taken (stored or linked) after S. |
| SAF8 | A status the reader accepts carries its current nonce and was signed after the question. |
| CENT_N = central (i) | COVERED by S implies every notice identity called for by the true state of every run at S's reading, read or carried, is held. |
| CENT_E | COVERED by S implies all evidence the findings at S's reading rest on is held. |
| PMD1 | No token is SPENT by a refusal at DL-3 or DL-4 (M-D-1). |
| R_AT_STATUS (finding probe) | COVERED by an INCREMENTAL S implies the oldest carried observation's token has true age ≤ R now. |
| C1_VS_82 (finding probe) | C-1 says COVERED while an 8.2 reason (STATEMENT_SPENT or ITEMS_REFUSED) holds. |

SAF-9 (section 3 and the record's checker) is not modelled.

## 3. Every configuration (run 1)

All 60 runs are complete. **51 agree with their declaration; 9 do not.** Each mismatch is listed after the table and kept as it was. No model code was changed after declaring, and no mismatch was "fixed".

Declared verdicts were written before the runs: version 2 at 21:25:21Z, and the four AR_*_L/XL additions at 21:32:12Z. Version 1 is kept in `G/model2/declared_v1/`. Its only run, FD_STATUS, hit the state cap and is kept INCOMPLETE. The bounds were then chosen with sizing runs that print no verdicts.

Columns:
- **Declared:** "same" when the declaration equals the observation; otherwise the declared set of violated properties.
- **Observed violated:** each property followed by its shortest trace length. Full traces are in the result files.
- **C1/82** is C1_VS_82 and **R@ST** is R_AT_STATUS.

| Config | Declared | Observed violated (trace length) | States | Agrees |
|---|---|---|---|---|
| FD_CHAIN | same | C1/82(11) CENT_N(12) R@ST(11) SAF2(12) SAF5(6) | 340278 | yes |
| FD_CHAIN_L | same | C1/82(10) CENT_N(12) R@ST(10) SAF2(12) SAF5(6) | 1334112 | yes |
| FD_RESTORE | same | C1/82(11) R@ST(11) SAF5(6) | 1145669 | yes |
| FD_EPOCH | same | C1/82(11) R@ST(11) SAF5(6) | 496012 | yes |
| FD_EPOCH_L | same | C1/82(12) R@ST(12) SAF5(6) | 1102558 | yes |
| FD_SUSP | same | C1/82(11) R@ST(11) SAF5(6) | 547113 | yes |
| FD_XB | same | C1/82(11) R@ST(11) SAF5(6) | 213750 | yes |
| FD_XB_SHAREDKEY | same | C1/82(11) R@ST(11) SAF5(6) | 226638 | yes |
| FD_ALARM | C1/82 R@ST SAF5 SAF7 | C1/82(11) R@ST(11) **SAF2(10)** SAF5(6) SAF7(9) | 780027 | NO: SAF2 |
| FD_EVID | C1/82 SAF5 | C1/82(12) **SAF2(10)** SAF5(6) | 661476 | NO: SAF2 |
| FD_SKIPEV | same | C1/82(11) CENT_E(13) CENT_N(12) R@ST(11) SAF2(12) SAF5(6) | 19906 | yes |
| FD_STATUS | same | C1/82(11) R@ST(11) SAF5(6) | 243372 | yes |
| FD_QUOTA | C1/82 SAF5 | C1/82(7) **SAF2(10)** SAF5(6) **SAF7(9)** | 276182 | NO: SAF2, SAF7 |
| FD_WIPE | same | C1/82(11) R@ST(11) SAF5(6) | 208846 | yes |
| AR_CHAIN | same | C1/82(11) R@ST(11) | 62607 | yes |
| AR_CHAIN_L | same | C1/82(10) R@ST(10) | 285144 | yes |
| AR_CHAIN_XL | same | C1/82(10) R@ST(10) | 1362568 | yes |
| AR_RESTORE | same | C1/82(11) R@ST(11) | 160833 | yes |
| AR_EPOCH | same | C1/82(11) R@ST(11) | 142363 | yes |
| AR_EPOCH_L | same | C1/82(12) R@ST(12) | 312041 | yes |
| AR_SUSP | same | C1/82(11) R@ST(11) | 107129 | yes |
| AR_XB | same | C1/82(11) R@ST(11) | 68108 | yes |
| AR_ALARM | same | C1/82(11) R@ST(11) | 35048 | yes |
| AR_ALARM_L | same | C1/82(11) R@ST(11) | 887596 | yes |
| AR_EVID | same | none | 22948 | yes |
| AR_EVID_L | same | none | 142162 | yes |
| AR_SKIPEV | same | C1/82(11) R@ST(11) | 3613 | yes |
| AR_SKIPEV_L | same | C1/82(11) R@ST(11) | 4846227 | yes |
| AR_CHAIN_LINKCHECKED_ONLY | same | C1/82(11) R@ST(11) SAF5(6) | 165802 | yes |
| AR_CHAIN_OPENFRESH_ONLY | same | C1/82(11) CENT_N(12) R@ST(11) SAF2(12) | 160295 | yes |
| AR_ALARM_COUNTS_ONLY | C1/82 R@ST SAF5 | C1/82(11) R@ST(11) **SAF2(10)** SAF5(6) | 419449 | NO: SAF2 |
| CV_RESUME | same | C1/82(10) R@ST(11) | 13678 | NO: probe P_COVERED_AFTER_LOST |
| CV_OLDCURSOR | same | C1/82(11) R@ST(11) | 15727 | NO: probe P_COVERED_AFTER_LOST |
| OA_CARRYBREAK | same | C1/82(10) CENT_N(10) R@ST(10) | 71367 | yes |
| MU_DL2_off | same | C1/82 R@ST SAF6(10) | 62607 | yes |
| MU_DL2_newreceipt | same | C1/82 R@ST SAF6(10) | 62607 | yes |
| MU_DL3_order | same | C1/82 CENT_N(6) R@ST SAF2(6) | 388317 | yes |
| MU_DL3_spend | same | C1/82 PMD1(4) R@ST | 266013 | yes |
| MU_ST2 | same | C1/82 R@ST SAF1(6) | 53203 | yes |
| MU_ST5 | same | C1/82 R@ST | 160833 | yes |
| MU_ST6 | same | C1/82 R@ST | 160833 | yes |
| MU_ST5_RESUME | same | C1/82 R@ST SAF4(7) | 13416 | yes |
| MU_ST6_FZ_OLDCURSOR | same | C1/82 R@ST SAF5(11) | 13682 | yes |
| MU_ST1_budget | same | C1/82 R@ST SAF1(6) | 65677 | yes |
| MU_ST1_epoch | same | C1/82 R@ST | 142363 | yes |
| MU_MK5 | same | C1/82 R@ST | 142363 | yes |
| MU_ST3 | same | C1/82 R@ST | 142363 | yes |
| MU_C12_age | same | C1/82 R@ST SAF3(7) | 142363 | yes |
| MU_C1_epoch | same | C1/82 R@ST | 142363 | yes |
| MU_MT5_wall | same | C1/82 R@ST SAF1(8) SAF3(8) SAF3B(12) | 143739 | yes |
| MU_MT1_mono | same | C1/82 R@ST SAF1(8) SAF3(8) SAF3B(12) | 108103 | yes |
| MU_MEPOCH | same | C1/82 R@ST SAF1(6) SAF3(6) SAF3B(11) | 136452 | yes |
| MU_TICK_CROSS | same | C1/82 R@ST | 142363 | yes |
| MU_DL4_held | same | CENT_E(8) SAF2(8) | 26476 | yes |
| MU_C1_gap | SAF7 | **CENT_E(12)** SAF7(9) | 22948 | NO: CENT_E |
| MU_C1_alarm | same | C1/82 R@ST SAF7(8) | 35048 | yes |
| MU_ST7_R | C1/82 R@ST SAF3B | R@ST(11) SAF3B(11) | 62159 | NO: C1/82 not violated |
| MU_OR2 | same | C1/82 CENT_N(11) R@ST | 36927 | yes |
| MU_GAP_unverified | none | **CENT_E(12)** | 21441 | NO: CENT_E |
| MU_CS2_nonce | same | C1/82 R@ST SAF5(6) SAF8(4) | 333192 | yes |

**The nine mismatches.** I traced each one, and each is a prediction error of mine, not a model fault.
- **FD_ALARM, FD_EVID, FD_QUOTA, AR_ALARM_COUNTS_ONLY (SAF2).** I expected the link-skip of M1 to need two runs. It also works with one run: a linked notice jumps the head over an undelivered alarm of an earlier failed reading, and the statement then commits to an alarm the mailbox never held.
- **FD_QUOTA (SAF7).** This family also has failing readings, so M3 applies; I did not declare it.
- **CV_RESUME and CV_OLDCURSOR (probe).** The courier can lose its state before its first EPOCH_OPEN is taken. It then opens an honest LOST epoch, so P_COVERED_AFTER_LOST is reached.
- **MU_C1_gap (CENT_E).** With the gap ignored, COVERED is shown while the evidence is absent.
- **MU_ST7_R (C1_VS_82 not violated).** At this bound, ST-7 is the only source of a spent statement.
- **MU_GAP_unverified (CENT_E).** See M4.

## 4. Mutants and vacuity probes

**Mutants.** Each one removes one mechanism from an AR_ base, so that every break can be blamed on that mechanism. "Survives" means redundant at this bound only, not dispensable.

| Mutant | Mechanism removed | Result |
|---|---|---|
| DL2_off | linking | SAF6 breaks |
| DL2_newreceipt | first receipt kept | SAF6 breaks |
| DL3_order | statement accepted before its items | SAF2 and central CENT_N break (6 steps: the statement is counted with notice k2 never delivered) |
| DL3_spend | token not touched at DL-3 | only PMD1 breaks; no safety property. It is a liveness rule |
| ST2 | single use | SAF1 breaks (a token voided by a replayed request is counted) |
| ST1_budget | budget/key check | SAF1 breaks (budget 1's token is counted for B) |
| C12_age | age check in C-1.2 | SAF3 breaks |
| MT5_wall | age from the wall clock alone | SAF1, SAF3, SAF3B break (wall set back) |
| MT1_mono | CLOCK_MONOTONIC instead of BOOTTIME | SAF1, SAF3, SAF3B break (suspension, then wall set back) |
| MEPOCH | no mailbox epoch at all (ticks compared across a reboot, no VOID, no epoch checks) | SAF1, SAF3, SAF3B break. The undeclared diagnostic `diag_age` shows a true under-count: token at t0, two ticks, wall back, reboot (tick back to 0); counted at true age 2 > L = 1 |
| TICK_CROSS | only the ban on comparing ticks across epochs | survives; no true-age > L state is reachable (`diag_age`). M-K-5 VOID, ST-1 epoch and C-1.1 cover it |
| ST1_epoch, MK5, C1_epoch | one epoch check each | survive, for the same layering |
| ST3 | the age check | survives: ST-2 with M-K-4 already treats an aged token as not ISSUED |
| ST5_RESUME | continuity check, with a courier that resumes from the mailbox's head | SAF4 breaks (7 steps) |
| ST5, ST6 (honest courier with restore) | continuity check; cursor check | survive. Not informative: in AR_RESTORE, P_ST5_FAIL and P_ST6_FAIL are not reached, because every stale copy is refused at DL-3 before 7.4 |
| ST6_FZ_OLDCURSOR | FROM_ZERO requirement, with a courier that keeps its old cursor | SAF5 breaks (11 steps); CENT_N still holds, because a REFRESH over a trusted witness reads every run |
| DL4_held | HELD check | SAF2 and CENT_E break (evidence orphan-removed before its notice arrives) |
| C1_gap | gap condition in C-1.3 | SAF7 and CENT_E break |
| C1_alarm | alarm condition in C-1.4 | SAF7 breaks |
| ST7_R | R check | SAF3B breaks |
| OR2 | reading unsettled runs | central CENT_N breaks (an L-3 FAIL on a carried run) |
| GAP_unverified | verification when a gap is closed | CENT_E breaks |
| CS2_nonce | nonce check | SAF8 breaks (an old status is accepted) |
| OA_CARRYBREAK | A-CARRY, outside the text's assumption | CENT_N breaks (10 steps). Expected; the text does not claim it |

**Vacuity probes.**
- Every probe a declaration lists was reached, or not, exactly as declared, except the two CV probes above.
- Reached where declared:
  - COVERED; COVERED by an INCREMENTAL statement with a carried run;
  - COVERED after COURIER_STATE_LOST, after a reboot, after a restart, and by a REFRESH in a new mailbox epoch;
  - a statement refused at DL-3 with its token still ISSUED (M-D-1 holds);
  - a link; EPOCH_OPEN(LOST); the courier detecting a lost state by refusal; a restore;
  - token eviction (M-K-2); a statement refused as expired; a replayed USED token answered with 422;
  - a cross-budget token refused at ST-1; a clock anomaly;
  - a gap, an orphan removal, 409 EVIDENCE_MISSING, a linked alarm, an alarm turning COVERED into NOT COVERED;
  - an L-3 result read; a stale status rejected; ITEMS_REFUSED; WIPE; a CAP-OWNER change.
- Not reached, as declared:
  - a gap closed under the literal reading (FD_EVID, complete);
  - link-skip, EPOCH_OPEN reopen and M-S-1 under the alternative readings;
  - another budget's token spent when the courier keys are distinct.
- PMD1 holds in every configuration without the DL3_spend mutant.

## 5. Findings against the specification text

Severities: **CRITICAL** = a rule as written permits a false COVERED or the loss of a called-for notice. **HIGH** = a rule is contradictory or cannot be implemented as written. **MEDIUM** = an ambiguity I had to resolve. **LOW** = wording.

### M1, CRITICAL: a linked item moves the head past a missing item (DL-2, DL-3, I-E-5, I-S-1, M-D-2; reading R1)
**Rule.** DL-2 links a held identity before DL-3 checks the position. I-E-5 records the item's own k. The head then jumps over an item the mailbox never received, and the next statement passes DL-3.

**Trace (FD_CHAIN, 12 steps):**
1. decision 1: run1 → u; FROM_ZERO reading; the notice for run1 and the statement are delivered.
2. decision 2: run0 → u; REFRESH reading.
3. The adversary delivers k5 (run1's notice, already held), which is LINKED.
4. The adversary delivers the statement at k6, which is counted.

**Consequence.** Run0's notice (k4) was never delivered and is not held, while the budget is COVERED. Both SAF-2 and central (i) are violated.

**Other forms.**
- One run, with an alarm skipped (FD_ALARM, 10 steps).
- An EQUIVOCATION notice whose evidence was orphan-removed (FD_SKIPEV, 13 steps), which also breaks CENT_E.

**Isolation.** The violation remains with only OPEN_FRESH and disappears with only the position-checked link (AR_CHAIN_*_ONLY).

**Fix.** Link only when the item is at head.k+1 with prev equal to the head's A, that is, check DL-3's position before DL-2.

### M2, CRITICAL: a replayed EPOCH_OPEN re-opens an epoch (DL-3, I-E-2, I-ID-3, C-1.1, SAF-5; reading R4)
**Rule.** Any EPOCH_OPEN passes DL-3: nothing requires a new chain_epoch, k = 1 or prev = A(0). It is never deduplicated. C-1.1 identifies the open epoch by its id.

**Capability.** CAP-DB replay alone.

**Trace (6 steps).** Open, statement counted (COVERED), replay of the same EPOCH_OPEN. The status is still COVERED after an EPOCH_OPEN with no new FROM_ZERO statement.

**Further effects.**
- The commit is reset to Hb(s_1), so the honest courier's next statement fails ST-5 and is SPENT. By R13 the courier must then declare its state lost (P_ST5_FAIL reached).
- After a genuine loss (epoch E2), replaying E1's EPOCH_OPEN re-opens E1: the E2 courier is refused (8 steps), and E1's old statement counts again.
- The status's count of epochs and their reasons are falsified.
- Each replay is stored again, so CAP-DB fills ITEM_QUOTA: 507 after three replays (FD_QUOTA, 5 steps).
- Rolling the head back also makes M-S-1 reachable (P_MS1, 7 steps).

**Note.** The covering statement's own claims remain true of its reading; the COVERED is false against SAF-5.

**Fix.** Refuse an EPOCH_OPEN for an epoch already seen. Under that alternative, SAF5 holds in every AR configuration. Also define C-1.1 by "accepted after the latest opening" rather than by the epoch id.

### M3, CRITICAL under reading R3: a repeated alarm leaves the status COVERED (I-ID-2, DL-2, C-1.4 against SAF-7, E-X-2)
**Rule.** An OBSERVATION_INCOMPLETE identity is only (reason, run). A second alarm with the same reason after a statement is linked, so it is not "accepted", and C-1.4 does not fire.

**Trace (FD_ALARM, 9 steps).**
1. A reading fails and its DEADLINE alarm is stored.
2. A FROM_ZERO statement is counted.
3. A later reading fails, and its DEADLINE alarm is LINKED.

The status stays COVERED, against SAF-7. It is bounded by L.

**Related.** E-X-2's "an alarm item is held that names the reason" is satisfied by a stale alarm.

**Fix.** Add the token or N, and the chain epoch, to I-ID-2, or say in C-1.4 that a link counts. With the link counting, SAF7 holds.

### M4, HIGH: an evidence gap can never be closed (E-B-3 against DL-2; reading R2)
**Rule.** The only way to close a gap is a later item of the same identity, and such an item is linked at DL-2. It never reaches DL-4 or DL-5.

**Evidence.** In FD_EVID, a closed gap is not reachable (complete search). A transient QUOTA refusal therefore leaves the budget NOT COVERED for ever, across all epochs, because identities ignore the epoch.

**If an implementation closes the gap at the link, it must verify the claim.** MU_GAP_unverified (12 steps):
1. The evidence is stored.
2. It is orphan-removed before any held item names it (E-Q-4).
3. The NOT_HELD notice arrives, and the gap is recorded.
4. A HELD notice of the same identity is linked, and the gap is closed without the evidence.
5. The status is COVERED with the evidence missing.

**Related.** The upload-to-notice window of E-Q-4 also makes 409 EVIDENCE_MISSING reachable.

### M5, HIGH: M-S-1 is unreachable as intended (M-S-1 against DL-3)
A counted statement takes its chain position, so delivering it again gives 409 CHAIN_POSITION, never its first receipt (P_STMT_REDELIVER_409 reached everywhere). M-S-1 is reachable only after M1 or M2 has moved the head back.

### M6, HIGH: M-D-1 and M-D-3 contradict each other
When a statement arrives before its items, the courier's position is not the head it is shown. M-D-3 then says its state is lost; M-D-1 says deliver the items and resend. A lost answer causes the same conflict. I resolved it with R6, which has no basis in the text.

### M7, HIGH: C-1 against 8.2
C-1 is an "if and only if" over five conditions, but 8.2 also gives STATEMENT_SPENT and ITEMS_REFUSED as reasons for NOT COVERED.
- C1_VS_82 is reached wherever INCREMENTAL can run: an INCREMENTAL is refused at ST-7 and SPENT while the earlier statement is still COVERED (11 steps).
- It is also reached in FD_QUOTA through ITEMS_REFUSED (7 steps).
- E-X-3 ("NOT COVERED by the clock") agrees with C-1, not with 8.2.

### M8, MEDIUM: R is checked only at acceptance (N-2, C-2, O-C-3)
ST-7 checks R only when the statement is counted. A COVERED status can rest on carried observations up to about R + L old. R_AT_STATUS is violated under both readings (11 steps). N-2's "observations no more than R old" is therefore false at the time of a status, and C-2's "no more than R ago" names no reference time.

### M9 to M19
- **M9 MEDIUM (R5).** Whether an accepted or a spent COVERAGE item takes a chain position is not stated.
- **M10 MEDIUM (R7, R8).** M-K-3 ("only ISSUED can change") contradicts M-K-4 ("EXPIRED whatever its state"). M-K-2's "oldest" is unspecified. As a consequence, ST-3 is subsumed by ST-2 (MU_ST3 survives).
- **M11 MEDIUM (I-4, 7.4).** "One courier key per budget" does not say whether one key may serve two budgets. If it may, a statement of B naming budget 1's token SPENDS that token (FD_XB_SHAREDKEY, 6 steps), and 8.2's STATEMENT_SPENT then has no clear budget.
- **M12 MEDIUM (M-K-1, M-K-2).** Nothing protects a challenge request against replay. A replayed request issues a token and voids the courier's (seen in the MU_ST2 trace). This is a CAP-DB liveness lever.
- **M13 MEDIUM (R11, E-Q-4, E-B-5).** No courier action is defined for 409 EVIDENCE_MISSING. T_ORPHAN must exceed any delivery delay, or the courier must re-upload.
- **M14 MEDIUM.** Loss of the mailbox's durable record of a budget is not covered; only "can read" (C-1.5) is. At the bound there is no false COVERED: the courier is refused, opens a LOST epoch and recovers. The history is gone, which breaks SAF-6 by the event itself.
- **M15 LOW (R9).** I-E-2 "at DL-3" comes before DL-4's room check, so it is unclear whether a 507 leaves the epoch closed.
- **M16 LOW (R10).** ST-8's scope is unstated; so is whether ST-7's "first statement in a mailbox epoch" is per budget.
- **M17 LOW (R13).** I-E-3's "a refusal by I-E-6" turns the M2 replay into a forced COURIER_STATE_LOST.
- **M18 LOW (R12).** O-1 and O-2 do not require the courier to check the challenge's budget, key or epoch; ST-1 catches the mismatch later.
- **M19 LOW.** K-N-1 ("never from what the courier remembers") conflicts with O-S-1 ("made again only when the findings change"). Not modelled.

## 6. What the model does NOT cover

- **Not a proof.** These are bounded results only: small bounds (L = 1, R = 0, at most 4 readings, at most 2 runs and 2 decisions, at most 3 chain epochs). Families are split, so some combinations are never explored together; for example, there is no reboot together with a courier restore, and no two runs together with evidence refusals beyond AR_SKIPEV_L.
- **Not modelled at all:**
  - section 3's findings logic, SAF-9 and the record's checker;
  - forks and rollbacks of the witness (O-3, O-4): the witness is trusted, so FROM_ZERO's role against a fork is invisible here;
  - OBSERVATION_PART items, byte sizes, OBJ_MAX, RUN_ANSWER_MAX, INLINE evidence, the global quota;
  - a pause from outside the machine (M-T-7); a crash of the mailbox in the middle of a write;
  - more than one mailbox; a forged signature (CAP-KEY);
  - liveness: N-1 and N-2 are not checked.
- **Not exercised:** ST-4 and ST-9 are always true for an honest courier with a trusted witness.
- **Restricted, not general:** an old copy of the courier's state is taken only between readings. Adversary deliveries are unbounded, but the readings are bounded.
- **Search limits:** the state key is a 64-bit hash, so a collision would prune a state and would not be detected.
- **Nothing here is evidence about any implementation.**
