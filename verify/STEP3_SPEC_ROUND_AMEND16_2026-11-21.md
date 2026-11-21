# Amendment 16, final specification round of 21 November 2026: summary and recommendation

21 November 2026. Private working material on `diagnostic-amend16-alarm-2026-11-21`. Written by the specification's
author, as PLEA's internal technical reviewer under the owner's direction. Nothing here is a declaration, an official
run, an acceptance, an implementation or independent validation.

**Recommendation: NO-GO for a Step 3 implementation against version 6 as it stands.** The design's safety did not
fail in this round's last checks. The specification is not yet complete enough to implement and declare against: one
HIGH and eleven MEDIUM findings are open, and correcting them makes text that nobody has reviewed. Section 8 says what
a GO would need.

## 1. What stands unchanged

- `verification-amendment-16` is at `0da1a85e819daac4839e51917402f3fcd67d5caf`. Nothing was committed to it.
- `e25a297` stays INCOMPLETE, failed at internal review and undeclared, with its eight defects.
- No code of the courier, the mailbox, the witness, the gateway or any deployment was changed. No Step 3 code exists.
- S-1 to S-7 and B-1 to B-3 stay recorded and open. G2, G5 and G6 stay "implemented and internally tested, with open
  obligations".
- Everything was run on one machine, one kernel, one account and one database server. DP1 and DP2 do not hold there.
  By ACC-2, no result of this round establishes acceptance of the production contract.

## 2. What was done

**The specification** (`verify/STEP3_SPECIFICATION_AMEND16_2026-11-21.md`) went through six versions. Each was
committed as it was sent to the agents, before their answers.

| Version | Commit | Reviewed by | Modelled |
|---|---|---|---|
| 1 | `1495320` | the reviewer (Part 1) | yes (Part 2) |
| 2 | `2694b52` | the reviewer (Part 3) | yes (Part 6) |
| 3 | `6f1ed23` | the reviewer (Part 4) | no |
| 4 | `d958810` | the reviewer (Part 5) | no |
| 5 | `466dd2f` | the reviewer (Part 7) | yes (Part 8) |
| 6 (final) | `e57ea2a` | the reviewer (Part 9) | yes, the changed area only (Part 11) |

Version 6 is 989 lines, SHA-256 `8eb8fe4b7ecb869670bba85a359093ee2817cf02fc77a8a150a4667c2509f836`. It was not
edited after its review. The findings made against it are recorded as open below and are not written into it.

**Three separate agents**, each one Opus-tier session instructed by the author. By the white paper's rule (revision 16,
section 3) their work is **internal review** and **separately authored verification**. It is not independent
validation. No Fable agent was used.

| Agent | What it did | Where |
|---|---|---|
| The reviewer | read each version against the owner's decisions and the unchanged code; ran its own probes on `e25a297` for version 1 | Parts 1, 3, 4, 5, 7, 9; `tests/diag_amend16_spec/review/` |
| The modeller | wrote its own bounded state-machine model of sections 5 to 8 from the text, four times, with verdicts declared before each run | Parts 2, 6, 8, 11; `model_v1/`, `model_v2/`, `model_v5/`, `model_v6/` |
| The test author | wrote 200 adversarial acceptance tests from version 6 before any implementation | Part 10; `tests/diag_amend16_spec/acceptance/` |

The eleven reports are in `verify/STEP3_SPEC_REVIEW_AMEND16_2026-11-21.md`, each exactly as returned.

**The author's own test** (`tests/diag_amend16_spec/gate_s5_capability.py`): which capability S-5 and S-1 need. As
demonstrated they need the gate's signing key (CAP-KEY). With the database role alone (CAP-DB), no replay of a genuine
PASS report from another attempt or another budget made a failing run read PASS; such runs read UNVERIFIED or
NO_OUTCOME. Not shown: that no CAP-DB path exists.

**Where each of the owner's seven decisions is met** is in section 13 of the specification.

## 3. Findings by severity

F-numbers are the reviewer's, M-numbers the modeller's, T-numbers the test author's. Every finding is in the reports;
what was changed for each is in section 14 of the specification.

| | CRITICAL | HIGH | MEDIUM | LOW | Total |
|---|---|---|---|---|---|
| Reviewer (F1 to F38) | 2 | 8 | 17 | 11 | 38 |
| Modeller (M1 to M37) | 3 | 7 | 11 | 16 | 37 |
| Test author (T1 to T19) | 0 | 1 | 10 | 8 | 19 |
| **Open at the end of the round** | **0** | **1** | **11** | **12** | **24** |

Several M-findings are the same defect as an F-finding, found a second way (M1 to M7 against F3, F4, F5, F9, F10,
F16).

**Corrected in versions 2 to 6** (70 findings): F1 to F37 and M1 to M32 and M34. "Corrected" means the text was
changed and the reviewer then argued the change sound. For the rules the model covers, the model's fixed design then
held. It does not mean proven.

**Open: HIGH (1)**

- **T1.** The specification fixes no wire names: not for item bodies, the challenge and its request, receipts, the
  signed head, the status, the error codes, or the message the mailbox signs. The interface cannot be implemented or
  tested as written. The test author chose the names itself, in one place (`codec()` in `sut.py`).

**Open: MEDIUM (11)**

- **M37.** SAF-10 is false as worded when the courier is restored from an older copy of its state, the mailbox has
  lost its record of the budget, and the witness is then forked (14 steps, `FD_WIPE_RESTORE_FORK`). "Never lowers it"
  (I-O-4) cannot hold through a restore. L-10 speaks only of state that is "lost". The correction is to L-10 and
  SAF-10: a courier restored from a copy older than its last verified checkpoint is the case nothing detects.
- **T2.** No outcome is stated when K-MISSING is the only finding.
- **T3.** K-N-2 (a notice must not say who signed) against 5.3 (each bound report is carried with its signer).
- **T4.** A checkpoint that fails O-2 has no alarm reason in O-W-2.
- **T5.** "400 or 403" is not assigned to cases; the answer to bad INLINE bytes is not stated.
- **T6.** The clock rule (M-T-1) can be tested only with an injected clock, which the text does not require.
- **T7.** No interface serves refused statements, so "kept without its `reveal`" can be checked only by reading the
  store.
- **T8.** It is not said when retirement and orphan removal run.
- **T9.** The status fields have no names.
- **T10.** The waiting time of K-N-3 is not among the configuration of section 11.
- **T11.** "For as long as it can read it" (I-O-4) does not say what a courier with no state keeps.

**Open: LOW (12)**

- **F38, M36.** After a rollback or fork of the witness below a checkpoint the courier verified, the courier refuses
  every reading without end. This is safe. The operator's act that accepts a restored witness must also reset the
  courier's own anchor, and the text does not say so.
- **T12 to T19.** A test that needs two capabilities; H of a null name; the mailbox epoch named before one is seen; the
  challenge's fields against section 11's list; ties for "earliest by decision"; whether a fence counts by its kind
  alone; whether the mailbox enforces "INLINE all together"; the encoding of the chain epoch and the secrets.
- **M33, M35.** Left unchanged on purpose; the reviewer agrees. EPOCH_KNOWN is redundant beside `closes` at the
  model's bounds and both are kept. The size of each item in each room is the implementer's to measure.

**Failures of proposed repairs in this round** (kept, by standing rule 5):

- Version 2's anchor rule did not hold when the mailbox lost its record (M20, found on version 2's model).
- Version 5's repair of M20, the courier's own anchor, was broken by the model in 16 steps (M30): a refusal lowered
  the anchor. The reviewer had argued that rule fixed. Version 6 rewrites it.
- Version 6's rewritten rule holds in the model, and its wording still claims too much for a restored courier (M37).

## 4. The models, each as it was run

All four are kept whole, with their declarations, results and counterexample traces. The reports give every trace.

| Model of | Configurations | States | Searches complete | Not as declared | Result for the fixed design |
|---|---|---|---|---|---|
| Version 1 | 60 | 19.9 million | all | 9 | broken: M1 to M3 CRITICAL, M4 to M7 HIGH |
| Version 2 | 60 | 10.1 million | all | 5 | held all but SAF-10 when the mailbox loses its record (M20) |
| Version 5 | 74 | 12.1 million | all | 8 | held all but SAF-10 in the case version 5 said it handled (M30) |
| Version 6, run 1 | 20 | 12.1 million | all | 2 | see below |
| Version 6, run 2 | 20 | 12.1 million | all | 3 | all 15 fixed-design configurations as declared |

**Version 6, plainly.** The declarations were written and hashed before run 1. In run 1 the fixed design showed SAF-10
violated in two configurations declared to hold (`FD_WIPE_BOTHLOST`, 15 steps; `FD_WIPE_RESTORE_FORK`, 16 steps). The
modeller then changed how its model judges SAF-10 and ran again. In run 2 those two agree, and three mutants show one
violation more than declared. So neither run matches its declarations in full, and the judgement of one property was
changed after results were seen. That weakens this run as evidence, and it is recorded as that.

What the author checked for itself:

- Both run-1 traces contain a loss of the courier's state (`courier_loses_state`, or
  `courier_restored_from_old_copy`) and a loss of the mailbox's record before the forked statement is counted. Both are
  the case SAF-10 says nothing stands in for (L-10), with the wording gap of M37 for the restored courier.
- All 20 searches have the same number of states, transitions and depth in both runs. Only the two SAF-10 properties
  differ between the runs.
- The declaration files match their recorded hashes.
- Not checkable: the model's code as it was in run 1 was not kept, only its hash. The change between the runs cannot be
  read as a diff.

The mutants of the version 6 model show the rule is needed: with no own anchor, with the version 5 rule, or with the
anchor dropped on I-E-4, SAF-10 breaks in 13 steps. Two mutants survive (the check in INCREMENTAL readings; counting an
unanswered statement): at these bounds those two rules are not shown to be needed.

**Agreement between the model, the review and the tests is not proof of any implementation.** All three agents are
sessions of one kind, instructed by one author, reading one text.

## 5. The acceptance tests

200 tests, written from version 6: 54 for section 3, 41 for the courier's side of sections 4 and 5, 66 for the mailbox
(sections 5 to 7), 22 for sections 8 and 9, and the rest for waiting times, exhaustion, earlier forms and self-tests.
Each test names its rules, the owner's decisions it serves, and exactly one capability. A test not labelled CAP-KEY
that reaches the gate's key is refused by the runner; the honest gate host holds its key in another process.

| Run | Result |
|---|---|
| No implementation bound | 193 NOT IMPLEMENTED, 7 PASS (the self-tests) |
| The unchanged `e25a297` | 124 FAIL, 52 NOT IMPLEMENTED, 24 PASS |
| The test author's own oracle for section 3 | all 54 section 3 tests PASS; 42 of 43 planted defects caught |

The author made the three runs and the planted-defect check again in a copy of the suite and got the same outcome on
every test (`acceptance/author_check/`). The pinned copy of `e25a297` was unchanged after the runs.

What the tests do not show:

- **146 mailbox and courier tests have never run past their first call.** No implementation and no stand-in exists.
  Whether they can all pass together is not known.
- The wire names and several behaviours in them are the test author's choices (T1 to T19), not approved text.
- The one planted defect that survives (`believe_any_report`) is judged equivalent by the test author. Not checked by
  anyone else.
- The section 3 oracle was written by the agent that wrote the tests it passes.
- Not tested: durability across a crash, a real suspension, a pause from outside the machine, TLS client names, and
  anything that holds only where DP1 and DP2 hold.

## 6. Defects of this round's own conduct

- The author told the agents twice that the text would not be edited again and then revised it. The last time was
  version 5, revised to version 6 after the model broke it (M30). Both times were disclosed to them. Version 6 was
  held.
- The reviewer's field `budget_charge_unchanged: true` was a constant, not a measurement. The specification now says
  "argued, not measured".
- Two tests were mislabelled CAP-OS while using the gate's key. The runner's own check caught it; the run is kept.
- The modeller changed a property's judgement after a run (section 4), and did not keep the earlier code.
- The agents cannot write report files. Each report was saved by the author from the session's transcript.

## 7. Unresolved proof obligations

Nothing below was shown in this round.

1. **The interface.** No wire format is fixed (T1), and ten behaviours are left to the reader (T2 to T11).
2. **That the acceptance tests can be met.** No implementation or stand-in has run the 146 mailbox and courier tests.
3. **SAF-10's true extent** (M37), and the operator's reset (F38, M36).
4. **Section 3 is in no model.** The consistency rule, belief, the waiting times (K-N-3) and the record checker rest on
   the reviewer's reading and on the test author's oracle.
5. **Not in any model:** observation parts and A-CARRY, INLINE evidence, sizes in bytes, the global quota, two courier
   processes with one key, a mailbox rolled back to an older copy (only a total loss of a budget's record was
   modelled), a partial loss of the courier's state, a crash between two durable writes.
6. **Only the changed area was modelled on version 6.** The other families were last run on version 5.
7. **Bounds.** One run, two or three decisions, one token, L = 1, R = 0. States are keyed by a 64-bit hash. A bounded
   search is not a proof.
8. **Time.** CLOCK_BOOTTIME across a real suspension and a real reboot was never run on a machine. A pause from
   outside the machine cannot be seen by the mailbox (L-9); that is a stated limit, not an obligation that can be met.
9. **Liveness.** None is checked and none is claimed. Known ways a budget stays NOT COVERED without end: F38 and M36;
   the limit of notices for a run (O-L-3); a mailbox whose rooms are full (N-6).
10. **Observation completeness.** The frozen witness and store cannot establish it: a result can be stored with no
    chain decision; the chain's hash does not cover which report was attached; re-reading costs cannot be bounded
    (L-1 to L-8, L-11). COVERED is a claim about one checkpoint at one time (C-2, C-3).
11. **CAP-DB.** That no path exists from the database role alone to a believed false verdict. One path is argued from
    code and untested: an honest gate host that loses its state signs twice.
12. **CAP-KEY (B-3).** While the service can hold the gate's key, a forgery made before the witness sees anything is
    detected by no rule here (N-3, ACC-4).
13. **B-1 and B-2.** Mandatory blockers, unresolved. Every role's password is in the repository; one account runs
    every party. No deployment can be said to comply until both are resolved (ACC-1).
14. **Values.** L and R are unset. The quotas and limits of section 11 are proposals.
15. **Independence.** Every check here was made by AI sessions working for the author.

## 8. Recommendation

**NO-GO for a Step 3 implementation against version 6 as it stands.**

Reasons:

1. **A HIGH finding is open (T1).** An implementation written now would take its wire format from the test author's
   choices or from its own. Either way the declared contract would not be the approved text.
2. **Eleven MEDIUM findings are open.** Ten are places where the text does not decide the behaviour. One (M37) is a
   safety property that is false as worded.
3. **Correcting them makes unreviewed text.** The owner's decision 6 asks for a full review with no unreviewed edits
   after it. Version 6 meets that only because the corrections are not in it.
4. **The acceptance tests are not shown to be satisfiable.**

What is not a reason: the design's safety. After six versions no counterexample is open against a property version 6
claims, at the bounds searched and inside its stated limits. The findings that remain are about completeness and
wording, not a broken mechanism. That is a statement about a model and a text, not about any code.

**What a GO would need, for the owner to decide:**

1. One closing version, limited to the open list: resolve T1 to T19 (by adopting the test author's choices or changing
   them), correct M37, and state the operator's reset (F38, M36). No new mechanism.
2. A review of that diff and nothing else by the reviewer, and the test suite moved from its own names to the
   specification's.
3. A stand-in mailbox and courier, kept apart from any production code, to show the 146 tests can pass together. Or
   the owner's acceptance that this is first shown by the implementation.
4. The owner's values for L and R, and a decision on custody of the gate's key (B-3).
5. A plan and a date for B-1 and B-2. Diagnostic work can go on without them (ACC-3); no claim of compliance can.

Step 3 itself would then be a new dated amendment with its own declaration made before its official runs.

The author stops here for the owner's approval.
