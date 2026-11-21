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
| 3 | the reviewer | specification version 2 (commit `2694b52`) | 21:48 |
| 4 | the reviewer | specification version 3 | 21:53 |
| 5 | the reviewer | specification version 4 (commit `d958810`) | 21:56 |
| 6 | the modeller | specification version 2 | 22:04 |
| 7 | the reviewer | specification version 5 (commit `466dd2f`) | 22:08 |
| 8 | the modeller | specification version 5 | 22:29 |

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

---

# Part 3. The reviewer, on version 2, as returned

[tier: opus]

# Step 3 specification v2: internal review, round 2

21 November 2026. This is an internal review by the same Opus-tier session, instructed by the author. It is not independent validation. I spawned no subagents and did not escalate. I give no GO or NO-GO. The report is returned as text only; my operating rules forbid writing report files.

**Labels.** RUN means I ran it and saw the output. ARGUED means it comes from reading the code or the text.

**The one new test (RUN, offline: no deployment and no database).**
- Script: `…/gate/review2/rv2_absent_fields.py`. Output: `…/gate/review2/out/rv2_absent_fields_run1.txt`.
- I took a genuine fence report and deleted its two null-valued keys, `nonce` and `result_digest`.
- It still verifies, for the witness (label `BOUND_FENCE`) and for the record checker.
- `H(object)` changes (`2df4…` → `6320…`). `H(projection)` stays the same only if absent keys are read as null.

**Repository.** Untouched, on `verification-amendment-16` at `0da1a85`. No code was changed.

**A correction to my own round-1 evidence.** In my Q3 output, the field `budget_charge_unchanged: true` was a constant written into my script, not a measurement. Version 2's table in 1.2 now cites "the budget is not charged" as shown by that test. It should be labelled ARGUED from `store.py`: a DENIED decision changes no state.

## 1. My findings F1 to F19

| # | Standing | What remains |
|---|---|---|
| F1 | **Partly fixed, and introduces a new defect** | The three rooms, retirement of parts, hashed names, O-P-2, the outbox and N-6 are right. But an item refused for room keeps its chain position and blocks every later item (F21). The proposed NOTICE_QUOTA breaks E-X-4's own sizing rule (F23). Index entries grow without limit (F24). |
| F2 | Fixed | E-Q-6 and SAF-11. A related gap remains (F22). |
| F3 | Fixed | DL-3 now comes before the link at DL-5, and I-3. |
| F4 | Fixed | DL-2, I-O-1 to I-O-3, I-E-7, I-E-3. One small point remains (F29c). |
| F5 | **Fixed, but introduces a new defect** | Gaps are now keyed by evidence id. But an object that closed a gap can then be removed as an orphan (F22), and nothing makes the courier upload it again (F25). |
| F6 | Fixed, with one gap | The signed projection does not say how an absent key is read (F26). |
| F7 | Fixed | The anchor (O-1 to O-4, ST-6, ST-8, SAF-10). The remainder is stated as L-10. |
| F8 | **Fixed, but introduces a new defect** | K-N-3 now starts waiting times only at an accepted statement (F20). |
| F9, F10, F11 | Fixed | — |
| F12 | Fixed, with one gap | The cap of eight bound reports is below what I-K-1 itself selects (F27). |
| F13, F14, F15, F16, F18, F19 | Fixed | For F16, see F29c. |
| F17 | Partly fixed | Two citations in 1.2 over-read my evidence (F29a, F29b). |

## 2. The model's findings M1 to M19

| # | Standing | Note |
|---|---|---|
| M1 | Fixed | DL-3 before the link at DL-5 |
| M2 | Fixed | I-E-3, DL-3 |
| M3 | Fixed | I-ID-2 now carries the token |
| M4 | Fixed, but introduces a new defect | F22, F25 |
| M5 | Fixed | DL-2 |
| M6 | Fixed | I-O-3 |
| M7 | Fixed | C-1.5, C-1.6, 8.2 |
| M8 | Fixed | C-1.7 |
| M9, M10, M11 | Fixed | — |
| M12 | Fixed | See F29c |
| M13 | Fixed, but introduces a new defect | I-O-6's "made again" meets F21 |
| M14 | Partly fixed | Answered NEVER. A lost anchor loses fork detection, which is stated as L-10 |
| M15, M16, M17, M18 | Fixed | — |
| M19 | Fixed | I-O-7 |

## 3. New findings

| # | Sev. | Rules | Defect and counterexample | Correction |
|---|---|---|---|---|
| **F20** | **HIGH** | K-N-3, O-W-1, O-7 | **A waiting time never starts while no statement is accepted, so a failed run can be hidden behind an alarm about another run.** With CAP-DB: (1) the service pads run Y with added fields beyond RUN_ANSWER_MAX (as in Q2), so every reading fails with RUN_OVERSIZE for Y; (2) it withholds the result of run X, whose gate host signed FAIL; (3) no statement is ever accepted, so X's UNVERIFIED (and NO_OUTCOME) notice is never called for. The engineer is told only about Y, for ever. Version 1 delivered X's UNVERIFIED under O-W-1. Decision 3 forbids exactly this. Also, K-N-3 does not say which clock counts the time. | Count a waiting time from the first reading that saw the run in that standing, whole or not, using that reading's token issue time as the challenge signs it. In a reading that is not whole, treat every waiting time as over. |
| **F21** | **HIGH** | I-O-5, I-O-6, I-3, DL-3, E-X-3, E-X-4 | **An item refused for room keeps its signed position and blocks every later item.** (1) A notice for run X gets 507 at k=10 and stays in the outbox with k=10. (2) The alarm E-X-4 requires (k=11) gets 409, head 9. (3) I-O-3 says deliver from 10 in order; k=10 is refused again, so the alarm naming X can never be delivered. Likewise, once OBS_QUOTA is full (reachable honestly, see F24), an observation part refused at k is followed by later FAIL notices that are blocked although NOTICE_QUOTA has room. That breaks E-X-3's "notices of other runs are still taken" and loses a called-for notice. I-O-6's "made again" has the same problem. | An item refused at DL-4 (507 or 409 EVIDENCE_MISSING) takes no position. The courier signs it again at the next free position when it resends it; its identity is unchanged. |
| **F22** | **HIGH** (false COVERED under the narrow reading of "names") | E-2, E-Q-5, E-B-3, C-2 (last bullet) | **"An item names an object" is undefined.** (1) An EQUIVOCATION notice says NOT_HELD for id e, and a gap is recorded. (2) The courier POSTs e and the gap closes. (3) No held item says HELD for e, and I-O-7 stops the notice being resent. (4) Read as "says HELD for", e is an orphan and is removed after T_ORPHAN. (5) The gap stays closed, the budget is COVERED, and the bound evidence is gone. This needs a finding: CAP-KEY, or an honest fault. | Define "names": an item names every evidence id it binds, whatever the holding it states. Reopen a gap if its object is ever absent. |
| F23 | MEDIUM | E-X-4, N-6, §11 values | **The proposed NOTICE_QUOTA (64 MiB) breaks E-X-4's own "MUST size for the runs".** Under CAP-KEY, each of about 1,000 runs can carry about 8 EQUIVOCATION identities (one for each set of findings) of up to 64 KiB each, about 512 MiB in all. The service can then lose a genuine FAIL notice. N-6 discloses this, but the proposed value invites it. | Give the formula: NOTICE_QUOTA ≥ (k+m) × NOTICES_PER_RUN_MAX × ITEM_MAX, and propose a value from it. |
| F24 | MEDIUM | E-Q-2, E-Q-4 | **Index entries and the records of accepted statements are never retired, and they share OBS_QUOTA.** That is about 0.9 KB per reading (ARGUED), so 256 MiB lasts about 300,000 readings: about 200 days at one reading a minute. After that: 507, ITEMS_REFUSED, NOT COVERED for ever with no adversary. With F21 it also blocks notices. | Give indexes and records their own room, sized and stated. Or allow compaction behind a signed checkpoint of the index. |
| F25 | MEDIUM | E-B-3, I-O-6, I-O-7, E-B-6 | **No rule makes the courier upload again the evidence for an open gap.** After a transient NOT_HELD(UNAVAILABLE), the gap stays open for ever: NOT COVERED. | At every reading, the courier POSTs every gap id the status lists that it holds (E-B-6). |
| F26 | MEDIUM | D-2, K-CLAIM, 3.6 | **The signed projection does not say how an absent key is read.** RUN offline: deleting `nonce` and `result_digest` from a genuine fence report leaves it verifying, with label BOUND_FENCE. Read literally ("a null nonce and digest"), this lets CAP-DB produce K-CLAIM at will, against 3.6; and one signature then has two evidence ids. | Say that an absent signed key is read as null, in the projection and in every check. |
| F27 | MEDIUM | I-K-1, E-B-1 | **I-K-1 selects up to 10 distinct reports but caps the total at 8.** For a consumed run: K-CONFLICT 2, K-UNKNOWN-VERDICT 2, K-FENCE 2, K-EARLY, K-NONCE, K-DIGEST and K-CLAIM 1 each. Which to drop is unspecified, so some finding may be left without evidence. | Give an order of priority that keeps at least one report for each finding, or raise the cap to 10 (it fits ITEM_MAX). |
| F28 | MEDIUM | I-O-4, I-E-4 | **The receipt comparison does not say "in the same chain epoch".** After an honest new epoch, the courier's kept receipts of the old epoch lie "beyond" the new head. That reads as MAILBOX_ROLLBACK, which opens another epoch, again and again: a livelock. | Compare positions only within the open chain epoch, and drop old receipts once their epoch is closed. |
| F29 | LOW | various | (a) 1.2 "the budget is not charged, by test": not measured (my error, see above). (b) 1.2 "the reviewer found no CAP-DB path to any finding of 3.2": I never assessed K-EARLY, K-CLAIM or K-PHASE for names no attempt bears; see F26. (c) M-K-1: resending a request after a lost answer gets 409 REPLAY; say the courier uses a fresh request nonce. (d) O-3: the operator's act that clears an anchor is unspecified, so it cannot be tested. (e) CRASH is a budget-level decision and is not in the control-only list (`store.py` 764, ARGUED), so CAP-DB can force a REFRESH of every run at will (O-R-4); add this to O-L-2. (f) K-PHASE's title says "effect report", but its budget clause says "any report". | — |

**Checked and found sound (ARGUED):**
- K-EARLY against RECOVER, REREGISTER and WITNESS_HELD: there is only ever one APPLIED ACCEPT_INTENT.
- K-PHASE for names no attempt bears: CAP-DB cannot produce it, because a fence needs an APPLIED or DUPLICATE ACCEPT_RESERVATION receipt.
- The anchor across chain epochs and mailbox epochs.
- DL-2 placed before DL-3.
- 7.4's rule that a refused statement takes no position and uses nothing.
- C-1's eight conditions against 8.2.
- The M-K-1 epoch and replay checks.
- E-X-2's bound of k+m runs under CAP-DB: HOLD and RECOVER are control-only, and RELEASED and DISCARDED runs call for no notice.

## 4. The owner's decisions

1. **Implemented.** K-5; the nine findings of 3.2; K-2, D-2, D-6; 1.2, K-CAP-1, 3.6. Missing: F26, and F29b (3.6's CAP-DB claim not yet reviewed for the new findings).
2. **Implemented.** I-E-1 to I-E-9; 5.6; linking at DL-5; ST-5, ST-6; the anchor. Missing: F21, F28. L-10 stands as a stated limit.
3. **Implemented in structure.** Section 6, E-Q-6, DL-4, E-X-1 to E-X-5. Not yet met: F20 (a failed run suppressed behind an alarm about another run), F21 (the alarm naming the run cannot be delivered), F22, F23, F24, F25.
4. **Implemented.** ACC-1 to ACC-5 and N-5. The quotations were verified in round 1.
5. **Implemented.** C-1 to C-4, C-1.7, O-C-1 to O-C-4, 4.3, L-1 to L-11. Not yet met: C-2's last bullet, under F22.

## 5. Open findings

- **CRITICAL:** none.
- **HIGH: three remain open: F20, F21, F22.**
- **MEDIUM remaining:** F23, F24, F25, F26, F27, F28. All are new; none of F1 to F19 or M1 to M19 remains open at MEDIUM.
- **LOW:** F29, and F17 partly.

Each HIGH has a short correction in the table above. On the owner's rule that the final text carry no unreviewed edits, the text is not ready to hand to the acceptance-test author until F20 to F22 are corrected and those edits are reviewed.

---

# Part 4. The reviewer, on version 3, as returned

[tier: opus]

# Step 3 specification v3: internal review, round 3

21 November 2026. This is an internal review by the same Opus-tier session. It is not independent validation. I spawned no subagents and do not give a GO or NO-GO.

**The diff is the whole difference (RUN).** The v3 file's SHA-256 begins `21fd2dd899b3a3cf`. My own `diff` of v2 against v3 (saved as `…/gate/review2/out/v2v3_mine.diff`) has the same changed lines as `v2_to_v3.diff`: 163 lines each. Nothing else was run this round; everything below is ARGUED from the text and the code read in earlier rounds.

**No CRITICAL or HIGH finding remains open in version 3. Two MEDIUM findings remain (F30, F31).** Both are about the rooms and the outbox, so 6.2, I-O-1 and I-O-5 are not yet fit to hand to the acceptance-test author. Everything else is.

## 1. F20 to F29

| # | Standing | Note |
|---|---|---|
| F20 | **Fixed** | K-N-3 now counts on the courier's own BOOTTIME from the first reading, whole or not, that saw the standing. Every waiting time is over in any reading that is not whole, after a loss of state, or after a restart. O-7 now allows those moments to be written at any reading. A side effect is accepted: in a reading that is not whole, honest runs in flight get an early NO_OUTCOME or UNVERIFIED notice. That stays within NOTICES_PER_RUN_MAX, since an honest run needs at most about four. |
| F21 | **Fixed** | I-3, I-O-5 and I-O-6: a refused item takes no position and is signed again for the next one. This agrees with DL-2 (an item refused for room is not held, so DL-2 does not apply), with DL-3, with I-O-3, and with the statement's `prev` (no statement is made in a reading that is not whole). The outbox has one new problem: F31. |
| F22 | **Fixed** | "Binds" is defined (E-2). The gap is now a state (E-B-3), and E-Q-5 and DL-5 agree with it. Linked notices raise no conflict: the gap depends on whether the object is present, and the held first notice binds the same deterministic ids. C-1.3 is consistent. |
| F23 | **Partly fixed** | The formula is given, but leaves out the m runs allowed back after NO_EFFECT, the budget's one notice, and the index entries of links (F30, F32). |
| F24 | **Fixed, but introduces a new defect** | OBS_QUOTA's finite life is now stated. But index entries charged to "the item's own room" give ALARM_RESERVE and NOTICE_QUOTA a finite life that is not stated (F30). |
| F25 | **Fixed** | O-1 and I-O-7. |
| F26 | **Fixed** | D-2: an absent signed field is read as null. This matches the witness's `.get` reading. |
| F27 | **Fixed** | Twelve bound reports, against at most 11 the rules can select. Twelve entries plus 32 KiB inline fit within ITEM_MAX (ARGUED). |
| F28 | **Fixed** | I-O-4 now compares receipts only within the open chain epoch. |
| F29 a to f | **All fixed** | (a) and (b): 1.2 corrected. (c): M-K-1, a new request nonce after no answer. (d): O-3, clearing an anchor stated as outside the specification. (e): O-L-2, CRASH. (f): K-PHASE's title. |

## 2. New findings

| # | Sev. | Rules | Defect and counterexample | Correction |
|---|---|---|---|---|
| **F30** | MEDIUM | E-Q-2, E-Q-3a, E-Q-4, E-X-3, E-X-4, I-E-1 | **Index entries charged to "the item's own room" are never dropped, so ALARM_RESERVE and NOTICE_QUOTA also run out, and nothing says so.**<br>1. With CAP-DB, the service pads run Y beyond RUN_ANSWER_MAX by adding fields (Q2). Every reading is then not whole, and each makes one alarm (I-ID-2).<br>2. Alarm bodies are dropped after 64. Their index entries, about 200 bytes each (ARGUED), stay in ALARM_RESERVE.<br>3. 4 MiB fills after about 20,000 readings, about 14 days at one reading a minute.<br>4. From then on, alarms are refused (ITEMS_REFUSED). So is any EPOCH_OPEN, which uses the same room. A courier that loses its state can never open an epoch, and the budget is NOT COVERED for ever. E-Q-3a's "Notices and alarms are still taken then" becomes false.<br>Likewise, every new chain epoch adds a link entry to NOTICE_QUOTA for each notice. The E-Q-3a formula does not count these, so repeated epochs (two processes on one key under I-4, or MAILBOX_ROLLBACK) can use the room up and get a FAIL notice refused. | Give index entries a room of their own, sized and stated, or let index entries of alarms and links go past the room's limit. Set aside room for EPOCH_OPEN. Add link entries per epoch to the formula, or state the limit. |
| **F31** | MEDIUM | I-O-1, I-O-5, 7.4, C-1.5, DL-2 | **The outbox keeps and resends items that can never be taken.** I-O-1 keeps an item until it has a receipt or a link, and I-O-5 resends an item refused for room at every reading. Applied to a statement, this gives refusals that recur for ever.<br>1. OBS_QUOTA is full, so statement S1 gets 507.<br>2. The operator adds room.<br>3. At the next reading S1 is sent again, signed for a new position, so it has a new digest and DL-2 does not catch it. Its token has expired, so it gets 422, and C-1.5 (STATEMENT_REFUSED) holds.<br>4. S1 has no receipt, so it is resent at every later reading. Each refusal that comes after that reading's accepted statement makes the budget NOT COVERED, and the order is not specified.<br>Stale observation parts of old readings are resent in the same way and use OBS_QUOTA for nothing. | Any 422 removes the statement from the outbox. A COVERAGE item or an OBSERVATION_PART refused for room is dropped: that reading is simply not whole. Only notices and alarms are kept to be sent again. |
| F32 | LOW | E-Q-3a, O-L-3 | (a) "Provisioned runs" should be k + m (runs allowed back after NO_EFFECT), plus one for the budget's own notice. (b) NOTICES_PER_RUN_MAX = 8 is below what CAP-KEY can make for one run: up to 8 sets of findings, one after another, plus earlier outcome notices. CAP-KEY can therefore reach RUN_NOTICE_LIMIT and keep the epoch not whole. The alarm names the run, so this fails closed, but it should be stated as a loss of liveness beside E-B-5. | — |

**Checked and found consistent (ARGUED):**
- K-N-3 against O-7, I-O-8 and NOTICES_PER_RUN_MAX.
- I-3's re-signing against DL-2, I-O-3, I-O-8 and the statement's commitment `prev`.
- E-2, E-Q-5 and E-B-3 against linking, DL-4 and C-1.3.
- I-O-4 against I-O-8.
- D-2 against K-CLAIM and the witness.
- The cross-references: I-O-7 is now gaps and I-O-8 is now once per epoch, and they are cited correctly.

## 3. What remains open

- **CRITICAL:** none.
- **HIGH:** none.
- **MEDIUM:** F30 and F31.
- **LOW:** F32.

**Still unfit to hand to the acceptance-test author:**
- 6.2: E-Q-2 and E-Q-3a, for the rooms of ALARM_RESERVE, of NOTICE_QUOTA and of EPOCH_OPEN.
- 5.6: I-O-1 and I-O-5, for the retention of refused statements and observation parts.

Every other rule I reviewed I consider fit to hand over.

---

# Part 5. The reviewer, on version 4, as returned

[tier: opus]

# Step 3 specification v4: internal review, round 4

21 November 2026. This is an internal review by the same Opus-tier session. It is not independent validation. I spawned no subagents and do not give a GO or NO-GO.

**No CRITICAL, HIGH or MEDIUM finding remains open in version 4, and I consider no rule unfit to hand to the author of acceptance tests.** Two LOW findings remain: F33 (an unchanged rule) and F34 (a new rule).

**The diff is the whole difference (RUN).** The v4 file's SHA-256 begins `f6d13812e03000f7`. My own `diff` of v3 against v4 (saved as `…/gate/review2/out/v3v4_mine.diff`) has the same changed lines as `v3_to_v4.diff`. Everything else below is ARGUED from the text.

## 1. F30 to F32

| # | Standing | Note |
|---|---|---|
| F30 | **Fixed** | Index entries and EPOCH_OPEN items now have a room of their own, INDEX_QUOTA. Its last INDEX_RESERVE bytes are kept for notices, alarms and EPOCH_OPEN items. Alarm bodies are capped at ALARMS_KEEP, and ALARM_RESERVE must be at least ALARMS_KEEP × ITEM_MAX (4 MiB proposed, exactly 64 × 64 KiB). Links no longer use NOTICE_QUOTA. The order in which things are refused, and the mailbox's finite life, are stated (E-Q-3a, N-6). Every case ends in 507 naming the room, then NOT COVERED by C-1.6, which is fail-closed and consistent. |
| F31 | **Fixed** | Only a notice about a run is kept to be sent again. Any other item that is refused is dropped. This agrees with the other rules: <br>• **I-E-7:** a dropped statement used nothing, and the next one reveals s_j again. <br>• **I-O-2:** with no answer, the identical item is sent again and DL-2 answers as the first time; dropping happens only on an answer. <br>• **A dropped EPOCH_OPEN:** at the next reading the challenge shows the old epoch's head, so I-E-4 opens a new epoch with a fresh id (I-E-1). <br>• **I-O-3:** unaffected. |
| F32 (a) | **Fixed** | E-Q-3a now counts k + m runs plus one for the budget's own notice. The arithmetic in section 11 checks: 1,001 × 16 × 65,536 bytes is about 1 GiB. |
| F32 (b) | **Fixed** | O-L-3 now states this as a loss of liveness. One wording point: with NOTICES_PER_RUN_MAX raised to 16, CAP-KEY probably cannot reach the limit at all. The sets of findings only grow, giving at most 8 EQUIVOCATIONs plus about 4 outcome notices, which is fewer than 16. "Again and again" overstates this, but it is harmless. |

## 2. New findings

| # | Sev. | Rules | Defect | Correction |
|---|---|---|---|---|
| F33 | LOW | 7.4, I-E-7, I-E-8 (not changed in v4) | A statement refused at 7.4 is "kept beside the chain as evidence", and it carries `reveal = s_j`. That s_j stays the valid next reveal, because a refused statement uses nothing. If readers are served refused statements, a courier restored from backup could read s_j back. That contradicts I-E-8's "the secret cannot be read back". An honest courier is already forbidden to take anything from the mailbox (I-E-4), so safety does not change. | Keep refused statements without `reveal`, or never serve it to readers. |
| F34 | LOW | E-Q-4, E-X-4 | "An alarm's body always has room" holds only if the oldest body is dropped *before* the new one is stored. ALARM_RESERVE is exactly ALARMS_KEEP × ITEM_MAX, so storing first and dropping second overflows by one body. | Say that the drop comes first, within the same handling under E-Q-6. |

**Checked and found consistent:**
- E-Q-4's MUST drop against C-1.4: "taken after S" is still decidable from the kept index entries.
- E-Q-4 against 8.3's "the alarms held" (the last 64) and E-X-3.
- When INDEX_QUOTA reaches its reserve, each later reading adds one alarm entry, so the reserve runs down to full. That is within the finite life stated.
- I-O-5 and the proposed values in section 11.

---

# Part 6. The modeller, on version 2, as returned

[tier: opus]

# Round 2: bounded model of Amendment 16, specification version 2

This is internal, separately authored verification, not independent validation. The results are bounded and are not a proof for unbounded parameters. Agreement between this model and the text says nothing about any implementation. No subagents were used and nothing was escalated. Nothing under `G/model2/` was changed; all new work is under `G/model3/`.

**Most important result:** at every bound I searched, the fixed design of version 2 holds every safety property except one. **SAF-10 is violated when the mailbox loses its record of the budget** (M20, HIGH; trace below). Every other configuration of the fixed design shows no violation.

Run 1 numbers: 60 configurations, every search complete (no state cap hit), 10.1 million states, about 7 minutes of compute. 55 of the 60 agree with their declarations. The 5 mismatches are all prediction errors of mine and are kept as they are (section 3). `model.py` and `configs.py` are byte-identical to the hashes recorded at declaration, so no model code changed after declaring.

## 1. What changed in the model

The model is a fresh `G/model3/model.py`, organised by rule id. Declarations are in `G/model3/declared/` (with `SHA256SUMS`, `DECLARED_AT` and `CODE_AT_DECLARATION.sha256`). Results are in `G/model3/results/run1/` (one `.json` and one `.console.txt` per configuration, plus `SUMMARY.md`), the harness is `G/model3/run_all.sh`, and the state-count logs are in `G/model3/results/sizing_logs/` (they print counts, never verdicts).

Every reading R1–R13 I needed for version 1 is now settled by the text, and I modelled the text with no alternative. The rules now in the model:

**Strict order of taking an item (7.3)**
- **DL-2:** an item whose digest is already held in the open epoch, or a statement already refused there at 7.4, is answered as the first time, before the position check.
- **DL-3:**
  - an EPOCH_OPEN is taken only for a chain epoch never seen, with k = 1 and prev = A(0);
  - any other item must be at the head's k + 1 with prev equal to the head's A.
- **DL-4:** evidence an item says is HELD must be held, and the item's room must have space.
- **DL-5:** an item whose identity is already held is linked at the next position and moves the head; otherwise it is stored. I-E-2 (closing the earlier epoch) happens only here, when the item is written. Gaps and the index entry are recorded here.

**Statements (7.4)**
- A refused statement takes no position and leaves the head, the commit and the anchor unchanged. It spends only a token of its own budget.
- The secret is kept until acceptance (I-E-7).
- The budget's anchor is kept across chain epochs, and ST-6 and ST-8 check it on every statement.
- ST-5 also checks `prev_statement`.

**The witness.** It can now be cut back (rollback) and then grown differently (fork), as an adversary move. The courier applies O-2 and O-3 and raises ROLLBACK or FORK alarms. I checked a rollback below the anchor and a fork at the anchor.

**Alarms.** OBSERVATION_INCOMPLETE has one identity per token (I-ID-2). C-1.4 counts any alarm taken.

**Evidence**
- Gaps are keyed by (budget, evidence id) and close only when the object comes to be held.
- Orphan removal is serialised (E-Q-6).
- E-Q-5 is abstracted as "at any time".

**Rooms.** The three rooms of E-Q-2 are counted in items. Each item's index entry is charged to OBS_QUOTA (finding M23). C-1.5 to C-1.7 are applied at the time of the status.

**Challenges (M-K-1).** A request is signed and names the mailbox epoch. A replayed request is refused (409 REPLAY), as is a request naming another epoch (409 EPOCH). The courier checks the challenge and its own position (O-1, section 5.6). Old challenges are therefore never used, and other-budget tokens never reach a statement.

**The courier's outbox (I-O-1 to I-O-7)**
- Resend on no answer (I-O-2).
- 409 CHAIN_POSITION with a head that is a position of its own chain: deliver the rest (I-O-3).
- A receipt beyond the mailbox's head: open a new epoch with a MAILBOX_ROLLBACK alarm (I-O-4).
- 507: the item stays and is resent, and a pending statement is replaced by an alarm (I-O-5).
- 409 EVIDENCE_MISSING: store the evidence again, or remake the notice as NOT_HELD (I-O-6).
- An identity is sent once per epoch (I-O-7).
- A head not of its own chain, or a refusal at ST-5, means lost state (I-E-4).

**Other adversary moves.** Loss of the mailbox's record of the budget (WIPE). Mailbox reboot and restart, the wall clock moved, suspension. Courier state lost, copied at any time, and restored. Delay, reorder and replay of anything sent.

**Abstractions kept from version 1**
- Exact symbolic hashes; signatures cannot be forged.
- Standings: `u` (unsettled, outcome notice), `p` (settled, no notice), `x` (settled, outcome notice), `f` (a finding; never settled).
- `f` is now absorbing, and its identity is the run's set of findings, binding the earliest report.
- Witness moves are offered only before a reading. This is a sound reduction, because only a reading reads the witness.
- Acceptance order is kept as ranks.
- States are keyed by a 64-bit hash, so a collision would prune a state without warning.

## 2. Bounds

Defaults: 1 run, 1 decision, standings u/x, TMAX 1, L 1, R 0, TOKENS_MAX 1, 1 chain epoch, 2 readings.

| Family | Bounds beyond the defaults |
|---|---|
| CHAIN | 2 runs, 2 decisions, 2 epochs, 1 loss |
| CHAIN_L | as CHAIN, plus standing p, TMAX 2, 3 readings |
| RESTORE | 3 readings, 2 epochs, 1 loss, 1 copy, 1 restore |
| RESTORE_L | as RESTORE, plus 2 decisions and standing p |
| EPOCH | TMAX 2, 1 reboot, 1 restart, 1 wall-clock move |
| EPOCH_L | as EPOCH with TMAX 3, L 2, R 1 |
| SUSP | TMAX 3, 1 suspension, 1 wall-clock move, 3 readings |
| REQ | 2 replayed requests |
| REQ_L | 3 replayed requests, 3 readings, 1 restart |
| ALARM | L-3 stored results, 3 readings, readings may fail |
| ALARM_L | as ALARM with 4 readings, TMAX 2 |
| EVID | standings u/f, 2 decisions, 3 readings, evidence refusals, orphan removal |
| EVID_L | as EVID with 2 runs |
| SKIPEV | 2 runs, standings x/f, refusals, orphan removal, 3 readings |
| FORK | 3 decisions, 1 witness cut-back, 3 readings |
| FORK_L | as FORK, plus 2 epochs and 1 loss |
| QUOTA | 2 runs, rooms (1 notice, 3 alarm, 8 obs), readings may fail |
| QUOTA_OBS | rooms (2, 3, 3) |
| WIPE | 2 decisions, 2 epochs, 1 wipe, 3 readings |
| WIPE_FORK | as WIPE, plus 3 decisions and 1 cut-back |
| STATUS | TMAX 2, reader on |

Not combined in one configuration: a reboot with a restore, a fork with evidence refusals, and two runs with mailbox restarts.

## 3. Every configuration (run 1)

Each property violated is followed by its shortest trace length; full traces are in the result files. All 60 searches are complete.

| Config | Observed violated (trace length) | States | Agrees with declaration |
|---|---|---|---|
| FD_CHAIN | none | 27733 | yes |
| FD_CHAIN_L | none | 745709 | yes |
| FD_RESTORE | none | 315953 | yes |
| FD_RESTORE_L | none | 2810211 | yes |
| FD_EPOCH | none | 95087 | yes |
| FD_EPOCH_L | none | 204096 | yes |
| FD_SUSP | none | 78473 | yes |
| FD_REQ | none | 1398 | yes |
| FD_REQ_L | none | 32636 | yes |
| FD_ALARM | none | 12472 | yes |
| FD_ALARM_L | none | 226691 | yes |
| FD_EVID | none | 5567 | yes |
| FD_EVID_L | none | 104424 | yes |
| FD_SKIPEV | none | 108470 | NO: probe P_LINK not reached (see below) |
| FD_FORK | none | 45662 | yes |
| FD_FORK_L | none | 680477 | yes |
| FD_QUOTA | none | 62205 | yes |
| FD_QUOTA_OBS | none | 2097 | yes |
| FD_WIPE | **SAF10 (14)**, as declared | 45710 | yes |
| FD_WIPE_FORK | **SAF10 (14)**, as declared | 1301374 | yes |
| FD_STATUS | none | 45715 | yes |
| CV_RESUME | none | 6807 | yes |
| CV_OLDCURSOR | none | 6712 | yes |
| CV_NOCHECK | none | 94526 | yes |
| OA_CARRYBREAK | CENT_N (10); outside the A-CARRY assumption, as declared | 60726 | yes |
| MU_DL2_off | SAF6 (12) | 27733 | yes |
| MU_DL2_newreceipt | SAF6 (12) | 27733 | yes |
| MU_DL3_order | CENT_N (6), SAF2 (6) | 61481 | yes |
| MU_DL3_spend | SAF2 (6) | 82314 | yes |
| MU_DL2_AFTER_DL3 | DL2_SAME (6) | 34959 | yes |
| MU_REFUSED_POS | REFUSED_NOPOS (11) | 27733 | yes |
| MU_OPEN_KNOWN | SAF5 (9) | 234047 | yes |
| MU_ST7_R | SAF3B_ACC (11) | 27433 | yes |
| MU_C15_off | C1_VS_82 (11), SAF7 (11) | 27733 | yes |
| MU_C17_off | C1_VS_82 (11), R_AT_STATUS (11), SAF7 (11) | 27733 | yes |
| MU_ST2 | SAF1 (8) | 300985 | NO: I declared that it survives |
| MU_ST5 | none | 315953 | yes |
| MU_ST5_RESUME | SAF4 (7) | 5825 | yes |
| MU_ST7_FZ_OLDCURSOR | C1_VS_82 (14), SAF5 (14) | 6474 | NO: C1_VS_82 not declared |
| MU_ANCHOR_off | none | 680477 | yes |
| MU_ANCHOR_off_NOCHECK | CENT_N (12), SAF10 (11) | 72341 | NO: CENT_N not declared |
| MU_ST1_epoch | none | 90301 | yes |
| MU_MK5 | none | 95087 | yes |
| MU_ST3 | none | 95087 | yes |
| MU_C12_age | C1_VS_82 (7), SAF3 (7) | 95087 | yes |
| MU_C1_epoch | none | 95087 | yes |
| MU_MT5_wall | R_AT_STATUS (12), SAF1 (8), SAF3 (8), SAF3B_ACC (12), SAF7 (12) | 95105 | yes |
| MU_MEPOCH | R_AT_STATUS (13), SAF1 (6), SAF3 (6), SAF3B_ACC (11), SAF7 (13) | 99588 | yes |
| MU_TICK_CROSS | none | 101939 | yes |
| MU_MT1_mono | R_AT_STATUS (12), SAF1 (8), SAF3 (8), SAF3B_ACC (12), SAF7 (12) | 78633 | yes |
| MU_REQ_REPLAY | PMK1 (4) | 7791 | yes |
| MU_C1_alarm | C1_VS_82 (8), SAF7 (8) | 12472 | yes |
| MU_OR2 | CENT_N (11) | 13437 | yes |
| MU_ALARM_NOTOKEN | none | 7042 | NO: I declared SAF7 violated |
| MU_DL4_held | CENT_E (8), SAF2 (8) | 5244 | yes |
| MU_C1_gap | C1_VS_82 (9), CENT_E (10), SAF7 (9) | 5567 | yes |
| MU_EQ6_off | CENT_E (9), SAF11 (8), SAF2 (9) | 6401 | yes |
| MU_GAP_BY_NOTICE | none | 6344 | yes |
| MU_C16_off | C1_VS_82 (11), SAF7 (11) | 62205 | yes |
| MU_CS2_nonce | SAF8 (4) | 62574 | yes |

**The five mismatches**

1. **FD_SKIPEV (probe P_LINK not reached).** This family has one epoch, and I-O-7 forbids sending an identity twice in an epoch, so a link cannot happen there. Links are reached in the CHAIN and RESTORE families.
2. **MU_ST2 (SAF1 violated; I declared it survives).** It does break. A restored copy takes a new token, which voids token0 by M-K-2. The old token0 statement is then delivered and, with ST-2 removed, counted. So ST-2 is necessary at this bound.
3. **MU_ST7_FZ_OLDCURSOR (C1_VS_82 also violated).** My own section 8.2 computation counts EPOCH_OPENED (no FROM_ZERO statement in the open epoch). That condition is exactly what the mutant removes, so this is correct and undeclared.
4. **MU_ANCHOR_off_NOCHECK (CENT_N also violated).** With the witness cut back to below the anchor, the INCREMENTAL statement of a courier that does not check is counted while a notice it called for is not held. The anchor check therefore also protects central (i).
5. **MU_ALARM_NOTOKEN (SAF7 holds; I declared it violated).** In the mutant the second alarm is never sent: the courier sends an identity once per epoch. SAF-7 talks only about items taken, so a failed reading that sends no item never touches it. This is a gap in how SAF-7 is phrased (M28).

## 4. Mutants and probes

**Mutants.** "Survives" means redundant at these bounds only, not dispensable.

| Mutant | Result |
|---|---|
| Linking off; first receipt not kept | SAF-6 breaks |
| Statement accepted before its items | SAF-2 and central (i) break |
| Token spent at DL-3 | SAF-2's token clause breaks |
| DL-2 placed after DL-3 for a re-sent statement | only DL-2's own rule breaks (an accepted statement resent gets a 409); no other safety property |
| A refused statement takes a position | only REFUSED_NOPOS breaks; the courier detects the misplaced head and loses state (liveness) |
| EPOCH_OPEN of a known epoch accepted | SAF-5 breaks |
| C-1.5, C-1.6 or C-1.7 removed | SAF-7 breaks (with C1_VS_82, and R_AT_STATUS for C-1.7) |
| ST-7's R check removed | SAF3B_ACC breaks |
| Request replay accepted | PMK1 breaks (a replayed request issues a token) |
| Gap closed by a later notice instead of by holding | survives (liveness only) |
| EQ6_off: orphan removal allowed between DL-4 and the write | SAF-11 breaks (8 steps: the HELD notice is pending, its object is orphan-removed, the write completes), and SAF-2 and CENT_E break too |
| DL4_held; C1_gap | break as in round 1 |
| C1_alarm; OR2 | break as in round 1 |
| Clocks: MT5_wall, MT1_mono, MEPOCH | break SAF-1, SAF-3, SAF3B and now also SAF-7, through C-1.7 |
| C12_age | breaks SAF-3 |
| Clocks: TICK_CROSS, ST1_epoch, MK5, C1_epoch, ST3 | survive (the epoch mechanisms are layered; ST-3 is subsumed by ST-2, as the text now says) |
| Continuity check, honest courier with a restore | survives: stale copies are caught by the position check first |
| Continuity check, with a courier that resumes from the mailbox's head | SAF-4 breaks (7 steps); this is the role I-E-8 claims |
| Anchor check (ST-6/ST-8), honest courier | survives: the courier's own O-3 check catches the fork first |
| Anchor check, courier that does not check | SAF-10 breaks (11 steps) and CENT_N breaks |
| FROM_ZERO requirement, courier that keeps its old cursor | SAF-5 breaks |
| Nonce check (reader) | SAF-8 breaks |

**Probes.** Every declared probe agreed except FD_SKIPEV's P_LINK.
- Reached:
  - a statement refused before its items, with its token kept;
  - DL-2's first receipt for a re-sent statement, and its first refusal;
  - EPOCH_KNOWN; EPOCH_OPEN(LOST); COVERED after a loss, a reboot and a restart, and by a REFRESH in a new mailbox epoch;
  - FORK and ROLLBACK alarms; a gap closed by holding the object; orphan removal; EVIDENCE_MISSING; a notice remade NOT_HELD;
  - each room refused; a replayed request refused;
  - NOT COVERED caused by an alarm, by a refused statement, and by a stale carried observation;
  - MAILBOX_ROLLBACK detected; L-3 results read; a reader taking COVERED, and a stale status rejected.
- Not reached, as declared:
  - an honest courier's statement refused at ST-6 in FORK;
  - **an alarm taken after a refusal for room** (FD_QUOTA, complete search): this is finding M22.

## 5. My round-1 findings against version 2

| Finding | Status in the model |
|---|---|
| M1 link-skip | **CLOSED IN THE MODEL.** SAF-2 and CENT_N hold in all FD configurations, including two runs with evidence (SKIPEV, EVID_L) and with loss (CHAIN_L, RESTORE_L) |
| M2 replayed EPOCH_OPEN | **CLOSED for replays of a seen epoch** (P_EPOCH_KNOWN reached, SAF-5 holds). A residue remains: a delayed EPOCH_OPEN that was never taken still closes the live epoch (M21) |
| M3 alarm linked | **CLOSED** (SAF-7 holds in ALARM and ALARM_L) |
| M4 gap never closes | **CLOSED** (P_GAP_CLOSED reached) |
| M5 M-S-1 unreachable | **CLOSED** (DL-2 first receipt reached) |
| M6 M-D-1 against M-D-3 | **CLOSED** by I-O-3; only liveness remains, which is not checked |
| M7 C-1 against 8.2 | **CLOSED** (C1_VS_82 holds in every FD configuration) |
| M8 R at the status | **CLOSED** (R_AT_STATUS holds; C-1.7) |
| M9, M10, M15, M16, M17, M18, M19 | **CLOSED IN THE MODEL**, as written |
| M11 cross-budget spend | **NOT MODELLED** (vacuous): the courier now refuses other budgets' challenges (O-1), so no such statement exists |
| M12 request replay | **CLOSED** (the mutant shows the mechanism is necessary) |
| M13 EVIDENCE_MISSING | **CLOSED** |
| M14 mailbox record loss | **STILL REACHABLE in a new form:** M20 |

## 6. New findings

**M20, HIGH: SAF-10 fails when the mailbox loses its record of the budget** (SAF-10, 8.2, I-O-4, L-10, I-E-3). Trace (FD_WIPE, 14 steps):
1. FROM_ZERO statement at N1 accepted; the courier's answers were lost.
2. The mailbox loses its record of the budget, including SEEN_CE.
3. The replayed EPOCH_OPEN(E1) is taken as an epoch never seen.
4. The replayed notice is stored.
5. The courier's resent statement is refused (ST1, ST2).
6. The courier holds no receipt beyond the head, so I-O-4 does not fire.
7. Its new FROM_ZERO reading has at = 0 and is counted, so the head of the last statement accepted for the budget is never signed back.

The same trace appears with a witness that can fork (FD_WIPE_FORK). L-10 admits the limit, but SAF-10 states no precondition. Either condition SAF-10 on the mailbox's durable state, or let the courier keep the anchor it last had accepted.

**M21, MEDIUM: an abandoned EPOCH_OPEN closes the live epoch** (I-E-3, DL-3). Trace (FD_CHAIN, 8 steps): E1's EPOCH_OPEN is never delivered; the courier opens E2 and has a statement accepted; the adversary then delivers E1's EPOCH_OPEN. That epoch has never been seen, so it closes E2. I-E-3's "cannot close the open epoch" holds only for epochs already seen. This is liveness, fail-safe, and needs only CAP-DB delay.

**M22, HIGH (cannot be done as written): no alarm can follow a notice refused for room** (E-X-3, E-X-4, I-O-5, DL-3). A notice refused for room keeps its chain position in the outbox, so DL-3 refuses every later item, the alarm "naming the run" included. P_ALARM_AFTER_ROOM_REFUSAL is unreachable at the FD_QUOTA bounds, by complete search. The design is safe (C-1.6 ends coverage), but the required alarm cannot exist.

**M23, MEDIUM: alarms depend on OBS room** (E-Q-2, E-Q-4). The index entries are charged to OBS_QUOTA and never retired, so an alarm can be refused for OBS room while ALARM_RESERVE has room (FD_QUOTA_OBS, 8 steps). E-X-3's "alarm within ALARM_RESERVE" therefore depends on OBS room.

**M24, LOW: I-E-8 overstates.** A copy taken after statement j was sent but before it was accepted holds s_{j+1}. After DL-2 returns j's first receipt, its statement j+1 is counted (FD_RESTORE, 11 steps; P_STALECOPY_COUNTED). SAF-4 holds; only the wording is wrong.

**M25 to M29, LOW: readings and wording I had to resolve**
- **M25:** DL-2's "refused there as a statement" is read as refused at 7.4 only. If refusals at DL-3 counted, a statement resent under M-D-1 would get its first 409 for ever.
- **M26:** under I-E-4, a courier whose own EPOCH_OPEN has not yet been taken would see the old epoch's head and declare its state lost again. Modelled: the courier takes no challenge until its EPOCH_OPEN has a receipt.
- **M27:** I-O-4 needs an epoch reason, but I-E-1 allows only FIRST or COURIER_STATE_LOST. It also does not say in which epoch the MAILBOX_ROLLBACK alarm goes. Modelled: LOST, with the alarm as the item after the EPOCH_OPEN.
- **M28:** SAF-7 is phrased about items, so a failed reading that sends nothing is invisible to it (see the MU_ALARM_NOTOKEN mismatch).
- **M29:** 4.6 requires every item to be accepted before a statement is made, yet M-D-1 and I-O-3 expect statements sent before their items. Modelled: pipelining allowed.

## 7. What the model does not cover

- **Search limits:** bounded results only, at small bounds (L ≤ 2, R ≤ 1, at most 4 readings, at most 2 runs, at most 3 decisions, at most 3 chain epochs).
- **Combinations not explored together:** see the end of section 2.
- **Not modelled:**
  - section 3 and SAF-9;
  - observation parts and their retirement (E-Q-4); INLINE evidence; byte sizes; the global quota; ALARMS_KEEP;
  - waiting times (K-N-3); budget-level decisions (O-R-4); names that no attempt bears;
  - a rollback of the mailbox to an older snapshot (only a loss of the whole record);
  - two courier processes with one key (I-4); a hypervisor pause; a crash in the middle of a write;
  - liveness.
- **Not exercised:**
  - ST-4 and ST-9 are always true for an honest courier with a witness that signs what it holds;
  - ST-1's budget and key branches never trigger, because the courier refuses foreign challenges (O-1).
- **Restricted:** a fork above the anchor is not claimed by the text and is not checked.
- **Search key:** states are keyed by a 64-bit hash, so a collision would prune a state without warning.
- **Nothing here is evidence about any implementation.**

---

# Part 7. The reviewer, on version 5, as returned

[tier: opus]

# Step 3 specification v5: internal review, round 5

21 November 2026. This is an internal review by the same Opus-tier session. It is not independent validation. I spawned no subagents and do not give a GO or NO-GO.

**No CRITICAL, HIGH or MEDIUM finding remains open in version 5, and I consider no rule unfit to hand to the author of acceptance tests.** Three LOW findings (F35 to F37) and M27's one unplaced alarm are recorded as open against version 5.

**The diff is the whole difference (RUN).** The v5 file's SHA-256 begins `e9f7f4b87af52e0a`. My own `diff` of v4 against v5 (saved as `…/gate/review2/out/v4v5_mine.diff`) has the same changed lines as `v4_to_v5.diff`. Everything else below is ARGUED from the text.

## 1. Standings

| # | Standing | Note |
|---|---|---|
| M20 | **Fixed**, within L-10 | The courier now keeps its own anchor (I-O-4). If the mailbox has lost its record, the challenge's anchor is (0, none), lower than the courier's own, so the courier declares MAILBOX_STATE_LOST and opens a new epoch. In its reading from 0 it checks the chain at its own anchor. ST-6 stays at the mailbox's anchor of 0, which is consistent. SAF-10 now says what it rests on. The model's 14-step trace no longer reaches COVERED: at its step 7 the reading from 0 is checked at the courier's own anchor. |
| M21 | **Fixed** | `closes`, I-E-2 and DL-3 (409 EPOCH_STALE). <br>• An undelivered E1 that arrives after E2 was opened is refused as stale. <br>• With two EPOCH_OPENs in flight, the first wins and the second is stale; the courier then makes a new one from a fresh challenge. <br>• A FIRST epoch has `closes` none against none. <br>• A mailbox that has lost its record also has none. |
| M24 | **Fixed** | I-E-8's wording. |
| M25 | **Fixed** | DL-2 now says "at 7.4". |
| M26 | **Fixed** | I-E-4: an unanswered EPOCH_OPEN is sent again first. |
| M27 | **Partly fixed** | The reason MAILBOX_STATE_LOST now exists. Still unstated: which chain epoch the MAILBOX_ROLLBACK alarm goes in, and at what position. The mailbox's head is not a position of the courier's own chain. LOW. |
| M29 | **Fixed** | I-S-1: a statement is sent only once its items are acknowledged. This agrees with M-D-1 (now only a defence) and with I-O-3. It costs a round trip for each reading. |
| F33 | **Fixed** | A refused statement is kept without `reveal`, but with its digest. DL-2's "first 422" can still match on the digest. |
| F34 | **Fixed** | E-Q-4: bodies are dropped before the new one is stored. A side point is F37. |
| M22 | **Agree it was met** | By F21 (I-3, I-O-5): an item refused for room takes no position. |
| M23 | **Agree it was met** | By INDEX_QUOTA and its reserve (v4). |
| M28 | **Agree it was met** | By I-ID-2 and O-W-1. A reading that gets no token sends nothing and needs nothing, because coverage then ends at L. |

## 2. New findings (all LOW)

| # | Sev. | Rules | Defect and counterexample | Correction |
|---|---|---|---|---|
| F35 | LOW | I-O-4, I-O-2, I-O-1 | **The courier can blame the mailbox wrongly.** <br>1. Statement S2, at N2, is sent and its answer is lost. It was in fact refused with 422. <br>2. The courier's own anchor counts S2, since it has "had no refusal of" it. <br>3. If the courier takes its next challenge before sending S2 again, that challenge's anchor (N1) is lower than its own anchor (N2). <br>4. The courier declares MAILBOX_STATE_LOST, opens an epoch and reads from 0. <br>Safety holds: S2's head is a genuine witness head, so the fork check passes. But the status records a false reason, and the courier pays for a needless reading from 0. | Before comparing anchors, send again any statement that has no answer (DL-2 returns its first answer). Count a statement in the own anchor only once it is receipted, or keep the previous anchor until the answer is known. |
| F36 | LOW | I-O-4, O-3 | **I-O-4 has no case for a witness chain shorter than the courier's own anchor.** It names only FORK, but the hash at the courier's own anchor cannot then be computed at all. | Say it is a ROLLBACK, as O-3 does for the challenge's anchor. |
| F37 | LOW | E-Q-4, E-Q-6 | **Old alarm bodies can be lost for nothing.** Old bodies are dropped before the new alarm is stored. If that store is then refused because INDEX_QUOTA is full, the dropped bodies are gone and nothing replaced them. Index entries survive, so C-1.4 is unaffected. | Check the room first, and drop only when the store will succeed. |

**Checked and found consistent:**
- I-E-2, I-E-3 and DL-3 against a FIRST epoch, an EPOCH_OPEN with no answer, two EPOCH_OPENs in flight, and a mailbox that has lost its record.
- SAF-10 and L-10 as reworded.
- DL-2 against a refused statement kept without `reveal`.
- I-S-1 against M-D-1 and I-O-3.

---

# Part 8. The modeller, on version 5, as returned

[tier: opus]

# Round 3: bounded model of Amendment 16, specification version 5

This is internal, separately authored verification, not independent validation. The results are bounded and are not a proof for unbounded parameters. Agreement between this model and the text says nothing about any implementation. No subagents were used and nothing was escalated. Nothing under `G/model2/` or `G/model3/` was changed; all new work is under `G/model4/`.

**Most important result: the fixed design of version 5 violates SAF-10 in the case the text now claims to handle.** The mailbox loses its record of the budget, the courier's own state is intact, and the witness is rolled back below the lost anchor. A statement is then counted without signing back the head of the last accepted statement (finding M30, 16 steps). Every other safety property of the fixed design held at every bound searched.

Run 1 numbers: 74 configurations, every search complete (no state cap hit), 12.1 million states, about 8.7 minutes of compute. 66 of the 74 agree with their declarations; the 8 mismatches are kept and explained in section 3. `model.py` and `configs.py` are byte-identical to the hashes recorded at declaration.

## 1. What changed in the model

**Files** (all under `G/model4/`):
- `model.py`: the model, organised by rule id.
- `configs.py`: configurations and bounds.
- `declare.py` and `declared/`: the declarations, with `SHA256SUMS`, `DECLARED_AT` and `CODE_AT_DECLARATION.sha256`, all written before the run.
- `results/run1/`: one `.json` and one `.console.txt` per configuration, plus `SUMMARY.md`.
- `results/sizing_logs/`: state counts only, no verdicts.

**New in version 5, now in the model**

| Rule | What the model does |
|---|---|
| I-3, I-O-5, I-O-6 | A refused item takes no position. The courier keeps the item in logical form and signs it for the position that is next when it sends it. If the item is refused (507, or 409 EVIDENCE_MISSING) it is signed again at the next free position, so it never holds back later items. |
| I-S-1 | The courier sends one item at a time, and sends a statement only when every item it commits to has a receipt or a link (finding M32). |
| E-Q-2, E-Q-3a, E-Q-4 | Four rooms, counted in items: notice bodies; alarm bodies (bounded by ALARMS_KEEP, the oldest dropped before a new one is stored); statement bodies plus statement records (2 per accepted statement); and an index room for every position and every EPOCH_OPEN, whose last INDEX_RESERVE only notices, alarms and EPOCH_OPEN may use. Retirement of statement bodies is a move in QUOTA_OBS. C-1.6 ends coverage on any refusal for room. |
| E-2, E-Q-5, E-B-3 | A notice binds every evidence id it names, whatever it says about where the object is. The evidence gaps are computed as a state (ids bound by held notices minus objects held), so a gap ends when the object is stored and begins again if it goes absent. Orphan removal applies only to objects nothing binds. |
| O-1, I-O-7 | The challenge lists the budget's gaps, and the courier stores those objects again at every reading. |
| I-O-1 | Only a notice about a run is kept in the outbox to be sent again. A refused alarm, statement or EPOCH_OPEN is dropped. A refused statement leaves the reading not whole, so its alarm follows. |
| I-E-1 to I-E-4, DL-3 | EPOCH_OPEN carries `closes`: the open epoch shown in the courier's last challenge. The mailbox refuses it with 409 EPOCH_STALE if that is not the budget's open epoch. Reasons are FIRST, COURIER_STATE_LOST and MAILBOX_STATE_LOST. A refused or stale EPOCH_OPEN is made again from a new challenge. |
| I-O-4 | The courier keeps its own anchor: its last statement that was accepted, or that it sent and has had no refusal of. A challenge whose anchor is lower than the own anchor, or a receipt beyond the head in the open epoch, means MAILBOX_ROLLBACK and a new epoch with reason MAILBOX_STATE_LOST. In every reading from 0, the witness's head at the own anchor's N must equal the own anchor's head, otherwise the reading is a FORK. |
| DL-2 | Answers again only items held in the open epoch and statements refused at 7.4. |

**Kept from round 2:** tokens and the M-K rules, mailbox epochs and the clocks, ST-1 to ST-9, the anchor in ST-6 and ST-8, a witness that can be rolled back or forked, the alarm identity per token, E-Q-6 (one write at a time), C-1.1 to C-1.8, replay of challenge requests, and the reader.

**Not modelled:** section 3, waiting times (K-N-3), observation parts, INLINE evidence and byte sizes.

## 2. How the properties are rendered

**SAF-10 has three cases.** Each case is judged when a statement is counted, using a ghost record of the last statement truly accepted for the budget (GANCHOR), whatever the mailbox has lost:

| Case | Condition | Requirement |
|---|---|---|
| (a) The mailbox's record is intact | the mailbox's anchor equals GANCHOR | the checkpoint's `at` and `head_at` sign back GANCHOR (property **SAF10**) |
| (b) The record is lost; the courier's own anchor is intact | the mailbox's anchor differs from GANCHOR, and the courier's ghost own anchor equals GANCHOR | at the reading, the witness's head at GANCHOR's N equals GANCHOR's head (property **SAF10**) |
| (c) Both lost | the courier's ghost own anchor differs from GANCHOR | this is L-10 and is **not claimed**. It is checked separately as **SAF10_L10**, declared violated only in FD_WIPE_BOTHLOST, where the courier loses its state, as an expected demonstration |

In case (b) and case (c), "the courier's ghost own anchor" follows the protocol's own definition: the courier's last own statement that was accepted, or that it sent and has had no refusal of. It is lost only by a real loss of the courier's state, or by the protocol itself, which is exactly what happens in M30.

The other properties are as in round 2: SAF-1 to SAF-8, SAF-11, CENT_N, CENT_E, C1_VS_82, R_AT_STATUS. New transition properties:
- **ALARM_ROOM:** an alarm is never refused for ALARM_RESERVE (E-X-4).
- **INDEX_RESERVE:** no notice, alarm or EPOCH_OPEN is refused for index room after statements have used the reserve.

## 3. Bounds and every configuration (run 1)

**Bounds.** Defaults: 1 run, 1 decision, standings u/x, TMAX 1, L 1, R 0, TOKENS_MAX 1, 1 chain epoch, 2 readings.

| Family | Bounds beyond the defaults |
|---|---|
| CHAIN | 2 runs, 2 decisions, 2 epochs, 1 loss |
| CHAIN_L | as CHAIN, plus standing p, TMAX 2, 3 readings |
| RESTORE | 3 readings, 2 epochs, 1 loss, 1 copy, 1 restore |
| RESTORE_L | as RESTORE, plus 2 decisions and standing p |
| EPOCH | TMAX 2, 1 reboot, 1 restart, 1 wall-clock move |
| EPOCH_L | as EPOCH with TMAX 3, L 2, R 1 |
| SUSP | TMAX 3, 1 suspension, 1 wall-clock move |
| REQ | 2 replayed requests |
| REQ_L | 3 replayed requests, 1 restart |
| ALARM | 3 readings, readings may fail, L-3 results |
| ALARM_L | as ALARM with 4 readings |
| EVID | standings u/f, 2 decisions, 3 readings, evidence refusals, orphan removal |
| EVID_L | as EVID with 2 runs |
| SKIPEV | 2 runs, standings x/f |
| FORK | 3 decisions, 1 witness cut-back |
| FORK_L | as FORK, plus 2 epochs and 1 loss |
| QUOTA_NOTICE | rooms (1, 2, 6, 9, reserve 2), ALARMS_KEEP 2 |
| QUOTA_NOTICE_L | as QUOTA_NOTICE with 4 readings, TMAX 2 |
| QUOTA_INDEX | index room 5 |
| QUOTA_OBS | obs room 4, retirement, 4 readings |
| QUOTA_ALARM | alarm room 1, ALARMS_KEEP 1 |
| WIPE | 2 decisions, 3 epochs, 1 wipe |
| WIPE_FORK | as WIPE, plus 1 cut-back |
| WIPE_FORK_L | as WIPE_FORK with 3 decisions |
| WIPE_BOTHLOST | 2 epochs, 1 wipe, 1 cut-back, 1 courier loss, 2 readings |
| STATUS | reader on |

**What was cut to fit.** WIPE_FORK_L at 4 readings, and WIPE_BOTHLOST at 3 readings, both hit a 3-million-state cap in sizing. They were reduced as shown above before declaring, so every search in run 1 is complete.

**Results.** Each property violated is followed by its shortest trace length.

| Config | Declared violated | Observed violated (trace length) | States | Agrees |
|---|---|---|---|---|
| FD_CHAIN | none | none | 23006 | NO: probes (a) |
| FD_CHAIN_L | none | none | 727990 | NO: probes (a) |
| FD_RESTORE | none | none | 289794 | yes |
| FD_RESTORE_L | none | none | 2666917 | yes |
| FD_EPOCH | none | none | 103338 | yes |
| FD_EPOCH_L | none | none | 218533 | yes |
| FD_SUSP | none | none | 90262 | yes |
| FD_REQ | none | none | 1497 | yes |
| FD_REQ_L | none | none | 36306 | yes |
| FD_ALARM | none | none | 5271 | yes |
| FD_ALARM_L | none | none | 85994 | yes |
| FD_EVID | none | none | 3088 | yes |
| FD_EVID_L | none | none | 25232 | yes |
| FD_SKIPEV | none | none | 29016 | yes |
| FD_FORK | none | none | 48222 | yes |
| FD_FORK_L | none | none | 716183 | yes |
| FD_QUOTA_NOTICE | none | none | 37162 | yes |
| FD_QUOTA_NOTICE_L | none | none | 608304 | yes |
| FD_QUOTA_INDEX | none | none | 2522 | yes |
| FD_QUOTA_OBS | none | none | 13022 | yes |
| FD_QUOTA_ALARM | none | none | 2103 | yes |
| FD_WIPE | none | none | 58438 | yes |
| **FD_WIPE_FORK** | none | **SAF10_L10 (16)** | 349026 | **NO: M30** |
| **FD_WIPE_FORK_L** | none | **SAF10_L10 (16)** | 1883512 | **NO: M30** |
| FD_WIPE_BOTHLOST | SAF10_L10 | SAF10_L10 (13), the L-10 case, as declared | 246966 | yes |
| FD_STATUS | none | none | 47808 | yes |
| AR_WIPE_FORK_DROPANCHOR (reading: a courier found to have lost its state drops its own anchor) | SAF10 | SAF10 (13), plus SAF10_L10 | 413840 | NO: SAF10_L10 (the M30 path) |
| CV_RESUME | none | none | 6137 | yes |
| CV_OLDCURSOR | none | none | 6434 | yes |
| CV_NOCHECK | none | none | 108011 | yes |
| OA_CARRYBREAK | CENT_N | CENT_N, outside A-CARRY | 62812 | yes |
| MU_DL2_off | SAF6 | SAF6 | 23006 | yes |
| MU_DL2_newreceipt | SAF6 | SAF6 | 23006 | yes |
| MU_DL3_order | none | none | 23006 | yes |
| MU_DL3_spend | none | none | 23006 | yes |
| MU_DL2_AFTER_DL3 | DL2_SAME | DL2_SAME | 31863 | yes |
| MU_REFUSED_POS | REFUSED_NOPOS | REFUSED_NOPOS | 22718 | yes |
| MU_OPEN_KNOWN | none | none | 23006 | yes |
| MU_CLOSES_off | none | none (the stale EPOCH_OPEN is taken) | 30017 | yes |
| MU_ST7_R | SAF3B_ACC | SAF3B_ACC | 22414 | yes |
| MU_C15_off | SAF7, C1_VS_82 | SAF7, C1_VS_82 | 23006 | yes |
| MU_C17_off | SAF7, R_AT_STATUS, C1_VS_82 | SAF7, R_AT_STATUS, C1_VS_82 | 23006 | yes |
| MU_ST2 | SAF1 | SAF1 | 275195 | yes |
| MU_ST5 | none | none | 289794 | yes |
| MU_ST5_RESUME | SAF4 | SAF4 | 5649 | yes |
| MU_ST7_FZ_OLDCURSOR | SAF5, C1_VS_82 | SAF5, C1_VS_82 | 6066 | yes |
| MU_ANCHOR_off | none | none | 716183 | yes |
| MU_ANCHOR_off_NOCHECK | SAF10, CENT_N | SAF10, CENT_N | 70685 | yes |
| MU_NO_OWN_ANCHOR | SAF10 | SAF10 (13), plus SAF10_L10 | 466582 | NO: SAF10_L10 (the M30 path) |
| MU_ST1_epoch | none | none | 97659 | yes |
| MU_MK5 | none | none | 103338 | yes |
| MU_ST3 | none | none | 103338 | yes |
| MU_C12_age | SAF3, C1_VS_82 | SAF3, C1_VS_82 | 103338 | yes |
| MU_C1_epoch | none | none | 103338 | yes |
| MU_MT5_wall | SAF1, SAF3, SAF3B, SAF7, R_AT_STATUS | same five | 103185 | yes |
| MU_MEPOCH | SAF1, SAF3, SAF3B, SAF7, R_AT_STATUS | same five | 101819 | yes |
| MU_TICK_CROSS | none | none | 111380 | yes |
| MU_MT1_mono | SAF1, SAF3, SAF3B, SAF7, R_AT_STATUS | same five | 90272 | yes |
| MU_REQ_REPLAY | PMK1 | PMK1 | 8737 | yes |
| MU_C1_alarm | SAF7, C1_VS_82 | SAF7, C1_VS_82 | 5271 | yes |
| MU_OR2 | CENT_N | CENT_N | 6566 | yes |
| MU_ALARM_NOTOKEN | none | none | 4469 | yes |
| MU_DL4_held | SAF2 | SAF2 | 3000 | yes |
| MU_C1_gap | SAF7, CENT_E, C1_VS_82 | SAF7, C1_VS_82 | 3088 | NO: CENT_E holds |
| MU_EQ6_off | SAF11, SAF2 | SAF11 (7), SAF2 | 4039 | yes |
| MU_ORPHAN_NOTHELD | none | none | 4756 | yes |
| MU_GAP_NO_REBEGIN | none | none | 3088 | yes |
| MU2_ORPHAN_NOTHELD+GAP_NO_REBEGIN (two mechanisms, labelled) | CENT_E, SAF7, C1_VS_82 | CENT_E, SAF7, C1_VS_82 | 4246 | yes |
| MU_C16_off | SAF7, C1_VS_82 | SAF7, C1_VS_82 | 37162 | yes |
| MU_REFUSED_KEEPS_POS | none | none | 20666 | yes |
| MU_NO_INDEX_RESERVE | INDEX_RESERVE | none | 2103 | NO: not shown at this bound |
| MU_ALARM_STORE_FIRST | ALARM_ROOM | ALARM_ROOM (8) | 2068 | yes |
| MU_OUTBOX_KEEPS_STMT | none | none | 14240 | yes |
| MU_CS2_nonce | SAF8 | SAF8 | 65455 | yes |

**The 8 mismatches**
- **(a) FD_CHAIN and FD_CHAIN_L, two probe mismatches:**
  - My probe P_OPEN_CLOSES_LIVE fires on any EPOCH_OPEN that closes an epoch with an accepted statement, including a legitimate opening after a real loss. That probe was too broad. The shape of M21 is tested instead by P_EPOCH_STALE, which was reached.
  - P_COURIER_LOST was not reached in CHAIN, because a lost courier there recovers through EPOCH_STALE and a new opening, never through I-E-4.
- **FD_WIPE_FORK and FD_WIPE_FORK_L:** finding M30.
- **AR_WIPE_FORK_DROPANCHOR and MU_NO_OWN_ANCHOR:** both also show the M30 path, in addition to the violation that was declared.
- **MU_C1_gap:** CENT_E holds, because the gap belongs to a later reading than the covering statement.
- **MU_NO_INDEX_RESERVE:** not demonstrated at this bound.

## 4. Mutants and probes

**Mutants that break a property**

| Mutant | Breaks |
|---|---|
| No own anchor (`NO_OWN_ANCHOR`) | SAF-10 (13 steps) |
| Anchor check removed, with a courier that does not check | SAF-10 and CENT_N |
| Alarm body stored before the oldest is dropped (`ALARM_STORE_FIRST`) | ALARM_ROOM (8 steps) |
| Orphan removal allowed between DL-4 and the write (`EQ6_off`) | SAF-11 (7 steps) and SAF-2 |
| NOT_HELD-only binding treated as an orphan **and** gaps not beginning again, together (two mechanisms, labelled) | CENT_E and SAF-7 |
| Linking off; first receipt not kept | SAF-6 |
| ST-2 removed | SAF-1 |
| ST-5 removed, with a courier that resumes from the mailbox's head | SAF-4 |
| FROM_ZERO requirement removed, with a courier that keeps its old cursor | SAF-5 |
| C-1.5, C-1.6 or C-1.7 removed; C-1.3 (gap) or C-1.4 (alarm) ignored | SAF-7 |
| Clock mutants | as in rounds 1 and 2 |
| Reader's nonce check removed | SAF-8 |
| Request replay accepted | PMK1 |
| Reading of unsettled runs removed | CENT_N |
| R check removed | SAF3B_ACC |
| DL-2 placed after DL-3 for a re-sent statement | only DL-2's own rule |
| A refused statement takes a position | only REFUSED_NOPOS |

**Mutants that survive** (redundant at these bounds, not dispensable)
- **Statement accepted before its items (`DL3_order`) and token spent at DL-3 (`DL3_spend`):** vacuous now. An honest courier sends a statement only after its items are acknowledged, so P_STMT_BEFORE_ITEMS is not reached.
- **EPOCH_OPEN of a known epoch accepted:** the `closes` check stops the same replays.
- **`closes` check removed:** no safety property breaks; the stale EPOCH_OPEN is taken, which is a liveness loss.
- **A refused item keeps its position:** no safety property breaks, but the alarm after a refused notice becomes unreachable again.
- **Outbox keeps a refused statement; NOT_HELD-only binding treated as an orphan; gaps that do not begin again:** each survives alone, because gaps are computed as a state.
- **Alarm identity without the token:** survives, because SAF-7 is worded about items.
- **ST-5 on an honest courier; anchor check on an honest courier; the clock mechanisms that are layered:** survive, as in round 2.

**Probes**
- Reached:
  - the alarm after a notice refused for room (M22 closed; trace: notice refused 507 at k3, then the alarm taken at k3);
  - EPOCH_STALE (5 steps: E1's delayed EPOCH_OPEN is taken, and E2's is then refused as stale);
  - MAILBOX_ROLLBACK, detected both by the own anchor and by a receipt;
  - the FORK raised by the own anchor (11 steps); COVERED after MAILBOX_STATE_LOST;
  - the index reserve used; an alarm body dropped; a retirement;
  - a gap closed, an item signed again at another position, a notice remade as NOT_HELD;
  - a copy taken mid-statement going on;
  - plus the round-2 probes.
- Not reached, as declared:
  - a gap beginning again in the fixed design;
  - an honest courier's statement refused at ST-6 in FORK;
  - a statement before its items.

## 5. Findings M20 to M29 against version 5

| Finding | Status in the model |
|---|---|
| M20 | The 14-step trace of round 2 is **CLOSED**: the own anchor catches it. **STILL REACHABLE in a new form**: M30 |
| M21 | **CLOSED IN THE MODEL** (P_EPOCH_STALE reached; with the `closes` check removed the stale EPOCH_OPEN is taken again) |
| M22 | **CLOSED** (the alarm after a room refusal is taken) |
| M23 | **CLOSED** (the reserve is used by alarms). The reserve's necessity was not demonstrated at this bound |
| M24 | **CLOSED** (the wording now matches what the model does) |
| M25 | **CLOSED IN THE MODEL** |
| M26 | **CLOSED IN THE MODEL** |
| M27 | **CLOSED IN THE MODEL** |
| M28 | The design is **CLOSED**, but SAF-7 is still worded about items, so a reading that sends nothing is invisible to it |
| M29 | **CLOSED IN THE MODEL** |

## 6. New findings

**M30, HIGH: SAF-10 case (b) fails.** Rules involved: I-O-4 (the own anchor is "sent and has had no refusal of"), I-E-2 and I-E-3 (after the record is lost, no epoch is "seen"), DL-3, 7.4 and L-10.

Trace (FD_WIPE_FORK, 16 steps):

| Step | What happens |
|---|---|
| 1–5 | The courier opens epoch 1, reads FROM_ZERO at N1, and its notice gets a receipt. |
| 6 | The adversary delivers statement S1, which is accepted. The answer is lost. |
| 7 | The mailbox loses its record of the budget, its set of seen epochs included. |
| 8 | The adversary replays the old EPOCH_OPEN(ce1, closes = none). It is taken as an epoch never seen. |
| 9 | The adversary replays the notice; it is stored. |
| 10 | The courier sends S1 again (I-O-2). The token is unknown, so S1 gets 422 (ST1, ST2). This refusal wipes the courier's own anchor, although S1 was in fact accepted before the loss. |
| 11–13 | The courier's alarm is received; it takes a new challenge. The challenge's anchor is 0, it has no own anchor, and its receipts are not beyond the head, so it detects nothing. |
| 14 | The witness is cut back to 0, below the lost anchor N1. |
| 15–16 | A FROM_ZERO reading at N0; the statement is counted with at = 0. |

The courier's state was never lost, yet the head of the last accepted statement is never signed back. The text claims this case. Possible corrections:
- the own anchor never moves back on a refusal of a statement that was sent again after a lost answer (keep the highest anchor sent); or
- keep the set of seen chain epochs, or the anchor, outside the budget record that can be lost.

**M31, MEDIUM (a reading I had to choose).** I-E-4 does not say whether a courier told by the head that it has lost its state keeps its own anchor. I modelled that it keeps it. If it drops it, SAF-10 case (b) fails (AR_WIPE_FORK_DROPANCHOR, 13 steps): a wipe, the courier's resent S1 gets 409 with no head, the courier declares its state lost, and a rollback then passes.

**M32, LOW (reading).** "The position then next" (I-O-5) is defined only if items go one at a time; "goes on at once with its other items" is unclear when several are in flight. I modelled one item at a time. As a consequence, M-D-1 is never exercised by an honest courier.

**M33, LOW.** EPOCH_KNOWN is subsumed by the `closes` check at these bounds.

**M34, LOW (reading).** E-Q-4's retirement rule ("older than the `oldest_carried` of the last accepted statement") is undefined when that statement carries nothing. Modelled: every statement body except the last's may be retired.

**M35, LOW (reading).** The size of each item in each room is unstated. Modelled: one unit per item, two of OBS room per statement.

## 7. What the model does not cover

- **Search limits:** bounded results only (at most 2 runs, 3 decisions, 4 readings, 3 epochs, L ≤ 2, R ≤ 1); see section 3 for what was cut.
- **Combinations not explored together:** a wipe with a restored copy, and a fork with evidence refusals.
- **Not modelled:**
  - section 3, SAF-9 and K-N-3;
  - observation parts, INLINE evidence, byte sizes, the global quota;
  - the courier sending more than one item at a time; two courier processes;
  - a mailbox rolled back to an older snapshot (only the total loss of the budget's record is modelled);
  - a hypervisor pause; liveness.
- **Not exercised:** ST-4 and ST-9 are always true here; ST-1's budget and key branches never trigger.
- **Search key:** states are keyed by a 64-bit hash, so a collision would prune a state without warning.
- **Nothing here is evidence about any implementation.**
