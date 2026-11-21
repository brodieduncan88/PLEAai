# Amendment 16: the final design gate before any Step 3 (design, evidence and review only)

21 November 2026. Private working material. Internal work under the owner's direction. It is not an independent
validation, not a declaration and not an acceptance of anything. Nothing is implemented by it, and no code of the
courier, the mailbox, the witness, the gateway or any deployment configuration is changed. It is kept on the branch
`diagnostic-amend16-alarm-2026-11-21` only.

**Recommendation, in one line: NO-GO for Step 3 implementation today** (section 11). The facts the design rests on
are established; the design text is not yet fit to hand to an implementer.

**What it is.** The owner asked for four design decisions to be settled, with evidence, before any coding: verdict
transitions and UNKNOWN; the mailbox's freshness, deadline and behaviour without a courier; the mailbox's 64 KiB limit
against the evidence a notice must carry; and incremental consistency at about 1,000 runs. This note gives each
decision, the tests made for it on the deployment, the design claims with a standing each (PASS, FAIL or UNPROVEN), the
defects found on the way, the independent review and what was done with it, and what stays open.

**This is the second form of this note.** The first form, at commit `6337a54`, is the draft the independent reviewer
judged, written before the author saw any of the review. The reviewer's two reports are, unchanged, in
`verify/DESIGN_GATE_REVIEW_AMEND16_2026-11-21.md`. This form corrects the draft where the review, or the author's own
re-reading, showed it wrong. Every such place is marked **(after review)** and listed in section 9. **None of the
corrected text has been reviewed.**

**Baselines.** The provisional design baseline is the Step 2 note at
`1fcc2270582f3c8ca179653911b0e73b06405d96` (`verify/STEP2_DESIGN_AMEND16_2026-11-21.md`) with its erratum
(`verify/AMEND16_ERRATUM_FRESHNESS_2026-11-21.md`). The threat-model baseline stays
`verify/AMEND16_THREAT_MODEL_ADDENDUM_2026-11-21.md` at `0da1a85e819daac4839e51917402f3fcd67d5caf` on
`verification-amendment-16`, which is not touched. Where this note corrects the Step 2 note it says so, and the Step 2
note is left as it was written. The bounded model, its nine weakened variants, its three searches stopped at the state
limit and its counterexamples are unchanged in `tests/diag_amend16_model/`. They are bounded evidence, by the same
author as the rules. They are not a proof.

**Standing of the code.** `e25a297` stays INCOMPLETE, failed at internal review and undeclared, with its eight
confirmed defects. S-1 to S-4, B-1 to B-3 and every earlier finding stand as recorded.

**Words used.** A gate report claims EFFECT, NO_EFFECT or UNKNOWN. A *verdict report* claims EFFECT or NO_EFFECT; its
*pair* is (claim, result digest). Two reports with one pair are the same result, whatever their bytes or signatures.
The *verdict scope* is the budget, the run and the nonce the chain records for the run. A report is *authentic* for a
scope when it is an effect report signed by any gate key given, whose signature verifies, naming that budget, run and
nonce. **UNKNOWN has three meanings, kept apart throughout (after review):** (a) the gate's claim UNKNOWN in a signed
report; (b) the check's own verdict UNKNOWN, inside the result that an EFFECT report signs, which is final; (c) the
governor's stored marker `'outcome': 'unknown'`, which the service chooses and nobody signs. Only (a) is "an UNKNOWN
report". (c) is never evidence of anything.

## 1. The tests made for this gate

All on one machine, against the unchanged code of `e25a297` (a pinned copy; its six main files are byte-identical to
the commit, checked by the reviewer and by the author). Scripts and every output, failed runs of the harness included,
are in `tests/diag_amend16_gate/`. The predicates in them are the harness's own and are not proposed code.
Development evidence only.

| Part | Script | What it asks | When (UTC) | Output |
|---|---|---|---|---|
| clocks | (inline) | which clocks the host offers | 18:11 | `clocks.txt` |
| A | `gate_token.py` | a 32-byte token through the witness's real checkpoint reading | 18:19:10 to 18:19:15 | `gate_token.json`, run 2 |
| C | `gate_release.py` | reports recorded with a RELEASE decision, early, or of every kind | 18:21:08 to 18:21:18 | `gate_release.json`, run 2 |
| B1 | `gate_unknown.py B1` | an honest gate host's UNKNOWN report after a run is cut off | 18:24:27 to 18:24:33 | `gate_unknown_B1.json`, run 2 |
| B2 | `gate_unknown.py B2` | UNKNOWN and then a verdict from the gate host's own code: a stalled host, a second host | 18:24:08 to 18:24:12 | `gate_unknown_B2.json` |
| B3 | `gate_unknown.py B3` | every sequence of 1 to 4 reports for one run, through the real witness | 18:24:33 to 18:31:48 | `gate_unknown_B3_len3.json`, `_len4.json` |
| D | `gate_sizes.py` | how large a report can be; the mailbox at its limit | 18:32:21 to 18:33:11 | `gate_sizes.json`, run 2 |
| E | `gate_result_store.py` | whether a stored result can be changed, and whether storing one is in the chain | 18:32:12 | `gate_result_store.json` |
| F | `gate_rows_as_service.py` | every report row against the chain, read with the service's own role | 18:49:45 | `gate_rows_as_service.json` |
| R | the reviewer's `review/rv_*.py` | the reviewer's own counterexamples, on a database of its own | 18:43 to 18:54 | `review/out/` |

**Limits of this evidence, stated once (after review).**

- **Databases.** `plea23` and `plea24` were made new for these tests and then shared: A, C and D used `plea23`; B and E
  used `plea24`. Each part made deployments and budgets of its own inside them.
- **A power outside the service's.** Parts C4 and C8 read the store's table of reports with the database owner's
  password. Part F repeats the check with the service's own role, over every budget of both databases.
- **The pinned copy.** The harness writes each test deployment's files under `outputs/verify_tests/` of the pinned
  copy. No source file of it was changed.
- **One signer, synthetic runs.** B3 and parts of C, D and R drive runs with the service's own database role and no
  check, and sign reports with the deployment's gate key, which the property file gives the service.
- **Failures of the harness, kept.** (1) `gate_token` run 1 stopped at its last step but one: it offered a server's
  certificate as a client's. (2) `gate_release` run 1 took a run's phase from a field the reading does not carry, so
  its line for what `e25a297` concludes read "None". (3) `gate_unknown B1` run 1 gave its last step no stored result
  to judge. (4) `gate_sizes` run 1 is void: its services could not start because the test deployment's ports are fixed
  and were in use, and it spoke to another deployment, which refused its certificates. The author's account is that
  part B3 held the ports; run 1's output carries no time, so that cannot be checked from the file. Nothing of run 1 is
  used. (5) The case "a final run with no stored result" was not found by part E and so was not tested there; that a
  result can be stored for such a run is shown by C1b.

**Machine.** Linux 6.18.44, Python 3.11.17, PostgreSQL 16, everything under one account (uid 0). The machine was
restarted four times on 21 November (09:41, 12:29, 17:38, 18:00:57 UTC); each restart stops PostgreSQL and resets a
kernel setting, and both were put back by hand before these tests, as approved earlier.

## 2. Decision 1: verdict transitions, and UNKNOWN

### 2.1 What an honest gate does (code, then deployment)

- **An honest gate host signs UNKNOWN in two cases.** When the check's function raises an error other than "no effect"
  (`plea_gateway/gate_host.py` 268-270). And when a host starts, finds a run still marked running by a previous owner
  of its state, marks it interrupted, and is then asked for that run (257-260).
- **By the code's own description, UNKNOWN can be followed by a verdict.** "If the interrupted host completes the tool
  after all (it was stalled, not dead), its EFFECT or NO_EFFECT report replaces the UNKNOWN one, which is kept as
  prior_report" (lines 24-33; `finish()`, 168-178). By the code, the governor treats a stored unknown outcome as not
  final and asks the host again (`plea_gateway/governor.py`, `_replay` and `_requery`); no test of this gate exercised
  that.
- **The witness never moves a run on an UNKNOWN report** (`plea_gateway/store.py` 397-407).

**B1, on the deployment: an honest host signs UNKNOWN.** A run was cut off by the gate host ending while the check ran
(exit status 137). The host was started again and the same design sent again by the ordinary client: the host signed an
UNKNOWN report; the witness recorded it as NOOP, VERDICT_UNKNOWN_STAYS_CHARGED; the run stayed CONSUMED; the client was
told "UNKNOWN: THE RUN WAS INTERRUPTED"; the courier made one INTERRUPTED notice. Sent a third time: the same report
again, a second no-op, no second notice. The record verified at `e25a297` with both reports and the outcome
INTERRUPTED. For comparison, a check that fails by itself while the host stays up does not produce the gate's UNKNOWN:
the gate signed EFFECT over a result whose own verdict is UNKNOWN, and the run became final.

**B2: UNKNOWN, then a verdict, by the gate host's own code.** Staged:

1. A failing design was submitted by the ordinary client. Six milliseconds after the governor called the gate host,
   with the run marked running, the host process was stopped where it stood (SIGSTOP).
2. After the host's one-second lease had run out, a second gate host with the same key and state file was started by
   the harness on another port. It took the state over and marked the run interrupted.
3. The harness asked the second host for the run, with the receipts the governor had used. It answered with a
   gate-signed UNKNOWN report. The harness sent it to the witness: NOOP. The courier made an INTERRUPTED notice.
4. The first host was let go on, 2.2 s after it was stopped. It finished the check, signed EFFECT, and wrote it over
   the interim report, keeping the UNKNOWN as `prior_report`. The waiting client's governor reconciled it: APPLIED,
   VERDICT_RECORDED. The client was told "FAIL: REQUIREMENT NOT MET".
5. The second host, asked again, gave the EFFECT report with the UNKNOWN as its prior report.
6. A late copy of the UNKNOWN report sent to the witness after the verdict: DENIED, VERDICT_IS_FINAL, and kept.
7. The courier then made a FAIL notice. The record verified at `e25a297` with three reports and the outcome FAIL.

**What B2 is, and is not (after review).** Both hosts ran the unchanged gate host code with the gate's key. But the
stall, the second host, its port and the carrying of the UNKNOWN report to the witness were all the harness's. In the
deployment as it is shipped (`verify/deploy.py` 84-100: one address for the gate host, and a stopped host is killed) a
stalled host keeps its port, a second host cannot take it, and a governor that tries again reaches the stalled host,
not a second one. **So B2 shows that the code path exists. It does not show that an honest deployment can produce
UNKNOWN followed by a verdict, and in the shipped arrangement it cannot.** The draft's words "as a governor that tries
again would" were wrong for this deployment.

### 2.2 What the witness records

**B3.** Every sequence of one to four gate-signed reports for one run was sent to the real witness with RECONCILE, each
on a run of its own that had reached the point of awaiting its verdict: 780 sequences over five reports (two UNKNOWN
reports with different results; two EFFECT reports, over a FAIL result and over a PASS result; one NO_EFFECT report);
6,830 decisions.

| The run awaits its verdict, or has one, and has | A report arrives with RECONCILE, claiming | The witness records | Report kept? |
|---|---|---|---|
| no report yet | UNKNOWN | NOOP, VERDICT_UNKNOWN_STAYS_CHARGED | yes |
| UNKNOWN reports only | UNKNOWN (the same or another) | NOOP, VERDICT_UNKNOWN_STAYS_CHARGED | yes |
| no report yet, or UNKNOWN only | a verdict | APPLIED, VERDICT_RECORDED: the run becomes final with that claim | yes |
| a verdict recorded | the same claim, **whatever its digest** | DUPLICATE, VERDICT_RETRY | yes |
| a verdict recorded | the other claim | DENIED, VERDICT_IS_FINAL | yes |
| a verdict recorded | UNKNOWN | DENIED, VERDICT_IS_FINAL | yes |

**What B3 shows, and what it does not (after review).** Within its scope (runs that begin awaiting a verdict;
RECONCILE only; the witness active; one gate key; one signature per report) no other answer was seen, every report was
kept in order and authentic (780 of 780), and the run's phase was the first verdict sent. It is **not** "the witness's
transitions and no others": at other phases, with RELEASE, with a held witness or with other evidence the witness gives
other answers (section 5.1; `store.py` 403; the reviewer's P4). And its counts of conflicts found (480 of 480, none
of 300 falsely) compared what was sent with what was read through the same function: they can fail only if the witness
loses or alters a report. **They are evidence that the witness keeps what it is sent, not evidence for the rule.** The
fourth row is S-1.

**The reviewer's own runs add** (`review/out/rv_conflict.json`, `rv_phase2.json`): the same pair signed a second time
with different signature bytes is accepted by the witness as a repeat (R1), so a rule keyed on a report's bytes would
find conflicts that are not there; a NO_EFFECT report on a run whose verdict is EFFECT is kept, and `e25a297` ignores
it (R1); two different EFFECT reports can be put on record while a run's intent is pending, leaving a run that awaits
its verdict with two pairs and no VERDICT_RECORDED decision (P4); and a run that was only reserved can be given an
EFFECT report with a null nonce and then released with a fence report, both signed by the gate's key (P5).

### 2.3 The decision

**The rule is on the set of gate-signed reports the reading or the record holds for one run, not on their order.**

| Id | The reports hold | Standing | Record verification |
|---|---|---|---|
| T1 | no report | no signed result | as today |
| T2 | UNKNOWN reports only, any number, any results | no verdict; the run is INTERRUPTED as today | as today |
| T3 | exactly one distinct verdict pair, any number of times, any bytes; it is the report at the run's one VERDICT_RECORDED decision | one signed result | as today |
| T4 | UNKNOWN reports and exactly one distinct verdict pair, in any order | **not permitted** (below) | **FAILS**, with its own reason; every report kept |
| T5 | two or more distinct verdict pairs, at any decisions, of any kind and operation, with or without UNKNOWN reports, with or without a VERDICT_RECORDED decision | **a conflict** | **FAILS**; every report kept |
| T6 *(after review)* | a verdict report for a run that is not in a phase of consumption, or whose chain nonce is null, or beside a fence report signed for the same run | **a conflict of kind**: the gate's key signed that the run had an effect and that it never started | **FAILS**; every report kept |

**No verdict replaces another, by any path, under any name.** There is no supersession.

**Conditions on the rule (after review where marked).**

- **C-1. Set, not sequence.** No implementation may take "the latest report" or "the report after the UNKNOWN" as the
  verdict.
- **C-2. Pair, not bytes.** Two reports conflict when their pairs differ, and only then.
- **C-3. Belief.** A stored result is believed only if it hashes to the digest of the report at the run's
  VERDICT_RECORDED decision, the claim there is EFFECT, the digest is 64 lower-case hexadecimal characters, and the run
  falls under T3. A report at any other decision can only add to a conflict. It is never believed.
- **C-4. Every key.** Authenticity is judged against every gate key given, in the courier and in the record's checker
  alike (`check_record.py` 854 compares with one key today). **Precondition:** the reader's set of gate keys is the
  witness's pinned set. The courier cannot read that set (its certificate is refused at the witness's `/pubkey`), so it
  is the engineer's to configure. Where a decision's label is AUTHORISED and the reader cannot verify the report
  there, the reading is not whole: the key sets differ.
- **C-5. Every phase.** The reports of a run are read whatever its phase: NO_EFFECT, INDETERMINATE and RELEASED too.
  The courier of `e25a297` asks only for runs that are EFFECT or CONSUMED (`courier.py` 403).
- **C-6. A digest that is not 64 lower-case hexadecimal characters** is still a pair for T5, is never believed, and is
  reported as itself: an honest gate host signs no such digest.
- **C-7. What is told.** Any run under T4, T5 or T6 calls for a notice, decided from what the witness gives and not
  from what the courier remembers having sent.

**T4, UNKNOWN beside a verdict: the owner's fail-closed default stands.** The default forbids it unless two things are
demonstrated by code inspection and deployment evidence.

1. *An honest gate actually emits a gate-signed UNKNOWN report.* **Demonstrated** (code; B1, end to end with the real
   governor; the reviewer agrees).
2. *Permitting it cannot conceal, replace or legitimise a conflicting verdict.* **Not demonstrated.**
   - It is **argued**, by the author and independently by the reviewer: under a rule that counts every verdict report
     at every decision and believes only the report at VERDICT_RECORDED, an UNKNOWN report adds no pair and removes
     none; the witness never moves a run on UNKNOWN; and any history "UNKNOWN, then a verdict" that an adversary can
     make, it can make as the verdict alone, which is the forgery made before the witness sees anything (UM6 a). So
     permitting T4 would add no power and forbidding it removes none.
   - It is **not modelled**: the Step 2 model has no UNKNOWN report. And the rule it depends on is not built, and its
     draft wording had gaps the reviewer found by test (the null nonce, the phases not read, a conflict with no
     recorded verdict).
   - **And nothing is lost by forbidding it today.** An honest UNKNOWN followed by a verdict cannot arise in the
     shipped deployment (2.1). The cost of the default is false failures in a failover arrangement that does not
     exist.

**So T4 is not permitted.** A run whose reports hold an UNKNOWN report and a verdict report fails record verification
with the reason "a verdict beside UNKNOWN: no rule permits it", distinct from a conflict, and calls for a notice; the
verdict is not believed. **What would lift it:** an independent model or test that establishes point 2 for the rule as
finally worded, and a deployment arrangement in which an honest gate can in fact produce the sequence. Until both, the
default holds. The owner may of course decide otherwise; the argument above is what there is.

**What a failed record says.** That the gate's key signed two different results, or two different verdicts, or a
verdict beside UNKNOWN or beside a fence, for one run. It does not say which is right, that the run failed, that a
verdict was changed, or who signed. An honest fault can produce a conflict too: a gate host that loses its state and
runs a check twice over inputs that changed signs two results. Evidence of equivocation is not evidence about the
verdict's correctness, in either direction; and one consistent report is not evidence that it is correct.

**What `e25a297` does today.** In 95 of B3's 780 sequences the witness recorded the FAIL result first and
`check_record.run_outcome` reads PASS when the PASS result is the one stored. With four distinct verdict pairs on
record for one run, a further pass of the courier made nothing and the record's sixth check raised nothing for the
second EFFECT pair or the NO_EFFECT pair (the reviewer's R1). None of this rule is built.

## 3. Decision 2: the mailbox's freshness, deadline, and the courier's absence

The corrected definition of the erratum stands: F1 to F6, T1 to T6, restart failing closed.

**The baseline's own wording is now broken on the real mailbox, not only in the model (the reviewer's R5).** A
statement of coverage signed three hours earlier was accepted and receipted with the current time; after a restart
the same receipt came back; after the mailbox lost its folder a new receipt with a new time was given. Counting from a
receipt makes an old observation fresh. The reviewer, without having seen the erratum, required the same repair:
count from the mailbox's own issue of a token.

### 3.1 The token through the real witness (part A; the reviewer's R4 agrees where it repeats it)

| Question | Answer, by test |
|---|---|
| Does a 32-byte token fit? | Yes. As 43 characters of URL-safe base64 without padding: status 200, and the nonce is signed back exactly as sent. As 64 hexadecimal characters: the same. |
| The limit | 1 to 64 characters: lengths 1, 43, 63 and 64 give 200; 65 and 128 give 400. An empty nonce gives 400. No nonce gives a checkpoint whose nonce is null. |
| The encoding | Letters, digits, `_` and `-` only, case kept. Base64 with its padding, or with `+` or `/`, gives 400. A space, a dot, a tilde, a NUL, a non-ASCII letter and a newline each give 400. |
| What the signature covers | statement, root (the budget), seq, head, business, witness, time, nonce, at, head_at. A change to the nonce, the budget, the number or the time makes the signature fail. |
| Is the nonce bound to the budget? | **In one signed statement, yes.** A checkpoint for one budget checked for another is refused, and one relabelled as another budget's fails its signature. |
| Does the witness refuse a token used for another budget? | **No.** One token asked for two budgets gave two valid checkpoints, each naming its own budget. |
| Does the witness enforce single use? | **No.** The same token asked twice gave two valid checkpoints. The witness keeps no memory of a nonce. |
| A request that gives the nonce twice | The last one is signed. A reader must compare the signed field, never the request. |
| A checkpoint that names a decision | `at` and that decision's head are signed too; a decision beyond the chain gives 400. |
| Who is given a checkpoint | The courier's, the keeper's and the governor's certificates. So the service can also ask for a checkpoint with any nonce it knows. |
| Sizes | 557 bytes with this token; 1,109 bytes at the largest names. |

**So.** The witness binds the token to a budget and to a point of the chain, and to nothing else. It does **not** bind
it to any reading of a run: the witness's answer for a run is unsigned and takes no nonce. That binding is the
courier's signature alone. Binding to the *correct* budget, single use and refusal of replay are the mailbox's to
enforce. The token used in the tests was the harness's; no mailbox issues one today.

### 3.2 The clock (the host, as it is)

| Clock | On this host |
|---|---|
| `CLOCK_BOOTTIME` | offered (id 7), resolution 1 ns; cannot be set (the kernel refuses, as root). By its definition it goes on counting while the machine is suspended. |
| `CLOCK_MONOTONIC` | offered, 1 ns, cannot be set. By its definition it does **not** count suspension. **Python's `time.monotonic()` is this clock here.** Using it would under-count age, which is a failure of safety. |
| `CLOCK_REALTIME` | the wall clock; root can set it (not tried). For people only (T3). |

- **The primitive for T2 is `time.clock_gettime_ns(time.CLOCK_BOOTTIME)`.** Availability, resolution and that it cannot
  be set are verified, by the author and by the reviewer.
- **Not verified: suspension itself.** This machine cannot be suspended from inside; the two clocks differed by 0.000 s.
  The kernel's name suggests a guest of a hypervisor. Where a hypervisor freezes a guest whole, no clock inside it
  need move; then only the wall clock, corrected afterwards, shows the gap (T5), and if nothing corrects it, nothing
  inside the machine can see the pause. That is recorded, not solved.
- **An epoch (after review)** is the machine's boot identifier together with a random value made at each start of the
  mailbox, stored with every token. A tick of an earlier epoch is never compared with the present clock.

### 3.3 How the mailbox issues, tracks and enforces

**The life of a token.** For independent modelling or testing. It is specified and checked nowhere, and after review
its text has changed, so what the reviewer said of the draft is not a judgement of this.

| From | Event | To | What the mailbox does |
|---|---|---|---|
| none | an admitted courier asks for a challenge for budget B | ISSUED | makes the token; writes epoch, serial, B, the courier's key, L and the moment by T2 durably; only then returns the challenge signed. A bounded number are ISSUED for one budget and key: the oldest is made VOID |
| ISSUED | a statement on this token, signed by the token's courier key and next in its chain of items, passes every check | USED | writes the mark durably before answering; the budget is COVERED to the statement's N until the token's age passes L |
| ISSUED | such a statement fails a check | SPENT | keeps the statement as evidence, with the reason; nothing is covered by it |
| ISSUED | a statement that is not the next item of its chain | unchanged | refuses it and says where its head is; the token is not touched |
| ISSUED or USED | the token's age passes L | EXPIRED | coverage that rested on it has ended |
| USED, SPENT, EXPIRED or VOID | any statement on this token | unchanged | keeps it as evidence; counts nothing. The same statement again is answered with its first receipt |
| any | the mailbox starts | VOID | a new epoch |
| any | a statement naming this token, not signed by its courier key | unchanged | refused |

**A statement of coverage is itself an item of the budget's chain (after review).** It is delivered after every item
it commits to, because the mailbox takes only the next item of a chain. So "the mailbox holds every item the statement
commits to" (F6) cannot fail merely because the statement arrived first, and a token is not spent by the order of
delivery. The draft's table would have spent it; and the model's trace in which a statement arrives before a notice
and counts later is a rule the draft did not have. **The model therefore does not model this table**, and its clean
search is not evidence for it.

**The checks on a statement** (all must pass): it is signed by a courier key given; the challenge in it is this
mailbox's own, of the current epoch, ISSUED, for this budget and this key (F1, F4); the checkpoint in it verifies
under a witness key the mailbox was given, names this budget, and its signed nonce is the token (F2); the courier's
signature covers the challenge, the checkpoint and the commitments (F3); the token's age is within L, by T2 and the
larger-age rule T5 (F5); the statement's commitment equals the mailbox's own head for the chain (F6); and it continues
the last statement accepted for this budget, or begins a new chain as below.

**A courier that has lost its state: one rule (after review).** The draft required every statement to continue the
last, and the Step 2 note let a courier begin a new chain; together those left no way back, or a way round. The rule
proposed: a new chain is accepted only with a statement that says, under the courier's signature, that its reading was
from nothing: every run of the budget read in this reading, none carried over, and every notice called for sent again
as an item of the new chain. The mailbox closes the earlier chain, keeps its items, and shows in every status how many
chains the budget has had. The mailbox cannot check that the reading was from nothing; it is the courier's signed
word, and a courier's key in the wrong hands defeats it, as it defeats everything else. Whether this lets an item be
dropped unseen is PO-B, unmodelled.

**What the mailbox does not check.** That the observation is true. It checks bindings and holdings.

**Each case the owner named.**

| Case | What happens | Kind |
|---|---|---|
| Replay of a statement | the first receipt again; nothing counted afresh | safety |
| A second statement on a used token | kept, not counted | safety |
| A token of another budget or key | refused | safety |
| A token from before a restart | counts for nothing | safety |
| An old checkpoint with a new token | cannot exist: the witness's signature covers the nonce | safety, resting on the witness's key |
| Mailbox restart | new epoch; every budget NOT COVERED until a statement on a new token | safety; liveness lost |
| Courier absent | when the last used token's age passes L the budget is NOT COVERED, by the mailbox's own time | safety |
| Wall clock set back | no effect on age; an anomaly is recorded and shown | safety |
| Wall clock set forward | the larger age is used; statements in time may be refused | safety; liveness lost |
| Machine suspended | `CLOCK_BOOTTIME` counts it | safety, **not tested** |
| Mailbox process stopped and continued | as suspension: the clock went on | safety, **not tested** |
| Statement delayed in delivery | after L it is kept and never counted; the courier takes a new token and reads again | safety; liveness lost |
| Token asked early, used late | its age counts from its issue | safety |
| The used mark lost while the epoch survives (a damaged folder, a live process) | a second statement on the token could be counted; it can be no fresher than the first | freshness holds; F4's letter does not. Hence the durable write before any answer |

The reviewer looked for a replay that the rules let through (same budget, another budget, another key, another epoch,
another mailbox, a replayed status, a delayed delivery) and found none, by argument from the text, not by test or
model.

### 3.4 When NOT COVERED can be seen from outside, with no courier

NOT COVERED is the default. At the mailbox's time t a budget is NOT COVERED when any of these holds, each decided by
the mailbox alone: (1) no statement has been accepted for it in the current epoch; (2) the token of the last accepted
statement is older than L; (3) the mailbox cannot read its own record of the budget; (4) the last statement on a token
of the budget was SPENT.

**How it is seen.** By asking the mailbox for a signed status. This gate adds: **the status signs back a nonce chosen
by whoever asks**, or a status saying COVERED that was signed yesterday can be shown today. And a rule for the reader:
**no fresh signed status saying COVERED is NOT COVERED.** A mailbox that is down, stalled or cut off gives no status,
and that must be read as NOT COVERED. No such reading exists today: only files, under the same account.

**What a status saying "COVERED to N" bounds (after review; the draft said more).** The checkpoint, the chain to N and
every run read in that reading were read no more than L before the status was signed. A run that was settled earlier
(section 5.2) is not read again: its observation is as old as the reading that settled it, and rests on the tested
fact that a settled run cannot change without a decision naming it.

**Safety and liveness.**

| | Guaranteed by the design, if built as specified and its conditions hold | Not guaranteed |
|---|---|---|
| Safety | The mailbox never counts a statement whose token is older than L, used before, or of another budget, key or epoch. A fresh receipt never makes an old observation fresh. A status says COVERED to N only while such a statement stands. | — |
| Liveness | — | That the courier runs. That a reading ends within L: the service can make the witness slow or unreachable (S-3), and can make one run's answer megabytes (5.2). That a budget ever becomes COVERED. |
| Notification | — | **That anybody is told.** The mailbox sends nothing to anyone. NOT COVERED is seen only by one who asks, and only while the mailbox answers. **No bounded time to notification is claimed, and the mechanism cannot give one.** |

## 4. Decision 3: the 64 KiB limit and the evidence of a conflict

### 4.1 What was measured (part D; the reviewer's P2)

| Thing | Size | By |
|---|---|---|
| a real gate report of this deployment | 499 bytes; two: 1,002 | test |
| a report for a run named with 512 non-ASCII letters | 3,522 bytes; two: 7,044 | test |
| a report for a run whose nonce is 70,000 characters | **70,448 bytes** | test: recorded as the run's verdict, read back authentic |
| a report whose signed result digest is 200,000 characters | **200,435 bytes**; the run's answer 202,558 | the reviewer's test: recorded (DUPLICATE, VERDICT_RETRY), read back authentic |
| a nonce of 1,000,000 characters | refused by the database at START | test |
| five UNKNOWN reports with digests of 1,000,000 characters on one run | the run's answer is 5,002,287 bytes | the reviewer's test |
| a real FAIL notice; its receipt | 1,440 bytes; 501 bytes | test |
| the mailbox's limit | exactly 65,536 bytes is taken; 65,537 is refused | test |

**Two whole reports do not always fit, and neither does one.** An honest gate host signs a nonce of 42 characters and
a digest of 64. But the nonce and the result are the service's to choose, and neither the store nor the witness bounds
a report short of the database's own limits (S-6). **What the mailbox as it stands takes:** a notice whose outcome it
does not know is refused; a notice with one more field is refused; a notice of an outcome it knows, with any words up
to the limit, is taken, since the mailbox does not check a notice's words. The last is not proposed as a route.

### 4.2 The decision: a notice of a conflict (corrected after review)

**Every field is bounded.** A value the service can make large (the nonce, a result digest that is not 64 hexadecimal
characters) is carried as its SHA-256 and its length, never whole. So a notice of a conflict is always under the
mailbox's limit and can always be delivered: the service cannot block a budget's chain of items with one report.

**It always carries, under the courier's signature:** the budget and the run; the nonce's SHA-256 and length; the
checkpoint it was read at (N and head); which of T4, T5 or T6 holds; for each of the two reports it rests on, the
decision it sits at, that decision's operation, kind, code and label, the report's claim, its digest (or the digest's
SHA-256 and length), its signer, its size, and **the SHA-256 of the report in the project's canonical form**
(`check_record.canonical`), so that the same report gives the same digest wherever it is read; the number of reports
the reading gave for the run; the number of distinct pairs; and one digest over all the reports' digests in the order
of their decisions.

**Which two reports.** For T5: the two earliest, by decision, whose pairs differ. If the run has a VERDICT_RECORDED
decision, one of the two is the report there. With three or more pairs the choice is the earliest two and the
commitment covers the rest. For T4 and T6: the earliest of each kind.

**The reports themselves, by size.**

| Case | Where the two reports are kept | In the notice |
|---|---|---|
| each is at most 16 KiB (every report an honest gate host can sign within the witness's limits on names) | **in the notice, whole** | the notice is at most about 40 KiB |
| a report is larger, up to the mailbox's limit for one piece of evidence (proposed: 1 MiB) | **at the mailbox, as a piece of evidence**, sent first and stored under its canonical SHA-256; and in the courier's own durable state | its digest and size; the mailbox refuses the notice until it holds every piece named |
| a report is larger than that | **not held by the mailbox.** In the courier's own durable state, up to the 32 MiB the courier will read; and in the witness's store | its digest and size, and the words that the mailbox does not hold it |

- **Durable retrieval.** A piece of evidence is written whole and synced before the mailbox answers, and **the mailbox
  gives it back by its digest to a reader** (a reading the draft's list of changes left out).
- **Complete binding.** The courier's signature covers each report's canonical digest.
- **Omission is detected.** A reader recomputes each digest from the report it is given; a missing or different report
  fails.
- **Fail closed.** Evidence that is missing or does not match never turns a conflict into no conflict. It is a
  conflict whose evidence is incomplete.
- **The limit of the third row.** Such evidence is as durable as the courier's own files and the witness's store. The
  notice then proves that the courier saw a report with that digest, and no more.

**The notice and the record are two channels (after review).** A record fails by T4 to T6 when it carries the reports;
it is signed by the engineer's key, so reports cannot be taken out of it afterwards without its signature failing (the
reviewer's P1; the reviewer withdrew its phase 1 finding to the contrary). A record is not required to carry the
courier's deliveries (`verify_ctl.record` leaves them out by default), so the draft's sentence that a notice of a
conflict "fails the record" was wrong: the notice tells the engineer; the record fails on the reports it carries.

### 4.3 The cumulative set for about 1,000 runs

The Step 2 note's chain of items stands (section 15): every item carries the chain's identifier, its number k and
A(k) = H(A(k−1), digest of item k); a statement carries k and A(k), 64 characters whatever the budget's size.

- **At 1,000 runs.** If every run calls for a notice: 1,000 items of about 1.4 KB, 1.4 MB at the mailbox; the
  statement stays about 3 KB. A plain list of 1,000 notice digests is 67,001 bytes and does not fit (calculated by the
  author and by the reviewer). Observation records go in parts of at most 478: three for a reading from nothing.
- **Verified independently.** A reader who is given the items in the mailbox's own order recomputes A(1) to A(k),
  checks each item's signature and chain fields, and compares A(k) with the statement and with the mailbox's signed
  status: 1,000 hashes and 1,000 signature checks.
- **What the mailbox must add for it.** On each delivery, that k is the next number and A(k−1) is its own head, or it
  refuses and says where its head is; an index of items by chain in its own order of acceptance (its listing today
  sorts by a wall-clock time in whole seconds); **and a reading that gives a reader the items of a chain** (left out
  of the draft: without it a reader must read the mailbox's folder under its own account).
- **Not established.** The chain of items has been checked nowhere by the author. The reviewer's small enumerator
  (one budget, two runs, three readings, one loss of state; 598 and 1,443 states) covers one question only, below. It
  stays an UNMODELLED proof obligation (PO-B).

## 5. Decision 4: incremental consistency, and scale

### 5.1 The release-decision path, tested (part C; part F; the reviewer's R1, R3, P1 to P5)

**The store keeps whatever is sent as evidence with a RELEASE or a RECONCILE, whatever the decision.** A gate-signed
EFFECT report for a forged PASS result was sent with a RELEASE, and with a RECONCILE, at every phase:

| Sent with | When | The witness's answer | Kept and given back? | Authentic for the run's scope? |
|---|---|---|---|---|
| RELEASE | the run is final (the gate host signed FAIL) | DENIED, CONSUMPTION_IS_FINAL (label NONE) | yes | yes |
| RELEASE | before the run's START | DENIED, NO_BOUND_FENCING_EVIDENCE (NONE) | yes | yes |
| RELEASE | before the attempt exists | DENIED, UNKNOWN_OR_DISCARDED_ATTEMPT (NONE) | yes | yes, once the attempt is made with that nonce |
| RECONCILE | before the attempt exists | DENIED, UNKNOWN_ATTEMPT (WRONG_BINDING) | yes | yes, once the attempt is made with that nonce |
| RELEASE | reserving, reserved, token, intent pending, consumed | DENIED, each time (NONE) | yes | yes |
| RECONCILE | reserving, reserved, token | DENIED, NOT_CONSUMED (WRONG_BINDING) | yes | yes |
| RECONCILE | intent pending | DENIED, NOT_CONSUMED (AUTHORISED) | yes | yes |
| RECONCILE | consumed | APPLIED, VERDICT_RECORDED | yes | yes |

- **`e25a297` believes such a report.** With the forged PASS result then stored, `check_record.run_outcome` reads PASS,
  and **the courier made no notice** for a run whose gate host signed FAIL (two real runs, X and Y; the reviewer's R3
  for a report planted with RECONCILE before START). The courier does not look at which decision a report sits at. The
  record's checker does, for a report at a RELEASE: such a record fails its sixth check, while giving the run the
  outcome PASS. This is S-5.
- **The decision that brings such a report is visible after a cursor.** In every case it is a decision of the chain,
  after the cursor, naming the run. **That a reader then reads the run again and finds the conflict is the rule, not a
  test: nothing built does it.** In the tests the finding was the harness's own predicate, and the courier of
  `e25a297` was silent (C1b; the reviewer's R1, second pass). The draft's "by test" for the finding was an over-reading.
- **Every report row sits at a RELEASE or RECONCILE decision naming its run, with the row's label.** Read with the
  service's own role over all 15 budgets of both test databases: 3,456 report rows, none otherwise (part F). The only
  RELEASE or RECONCILE decisions with no report row are labelled NONE (4).

**Every kind of evidence (PO-8).** Twelve kinds were sent with each operation to one run. A report row was kept for
every one that carried anything at all. **Only a decision sent with no evidence has no row.**

- **Correction to the Step 2 note's count rule (section 6, step 2).** Restated: (a) the *verdict* of a run is the
  report at its one APPLIED, VERDICT_RECORDED decision (C-3); (b) the *rule of 2.3* takes every gate-signed report of
  the run, at any decision; (c) the *count rule* requires a report at every RELEASE or RECONCILE decision for the run
  whose label is not NONE (AUTHORISED, WRONG_BINDING and BOUND_FENCE each mean evidence was sent), and every report
  must sit at such a decision for the run. The same count rule applies to a record. The reviewer finds (c) sound on
  the code, and has shown no attack within the service's powers that needs it.
- **A limit that cannot be removed without changing the store (L-1).** A decision labelled NONE may have a report or
  none, and the chain does not say which. A verdict report sent with a RELEASE is always labelled NONE. If it were
  later missing from the witness's answer, nothing would show it. Only the database's owner can remove it (outside the
  service's powers, DP1), and such a report can never be believed (C-3). But the evidence of that conflict would be
  gone unseen.
- **A second limit of the same kind (L-2).** The chain's hash covers a decision's operation, kind, code and the
  budget's state, not the report. The chain says that a report claiming EFFECT was authorised at decision k; it does
  not say which digest. What the courier saw is fixed afterwards only by the courier's own signed commitment, which is
  why that digest must be canonical (4.2).

### 5.2 A stored result leaves no decision (part E), and what follows

- **Storing a result adds no decision to the chain.** By test.
- **A value once stored cannot be changed or removed by the service's role.** By test: a second and a third value were
  answered as success and were not stored; DELETE and UPDATE were refused. An outcome stored as "unknown" (meaning c)
  can be replaced, once, by a value.
- **So "final" is not the mark of a run that need not be read again.** A run can be final in the chain with its result
  not yet stored, and the result can be stored later with no trace in the chain. **Correction to the Step 2 note,
  section 14, step 4:** the runs read again at every reading are those named by a new decision **and every run that is
  not settled**.

**Settled, phase by phase (after review; the draft defined it for one phase only).**

| The run's phase | Settled when | Read |
|---|---|---|
| EFFECT | it falls under T3 and its stored result is a value that hashes to the digest at VERDICT_RECORDED | until settled; then only when a new decision names it |
| NO_EFFECT | it falls under T3 with the claim NO_EFFECT at VERDICT_RECORDED; no stored result is needed | at the reading that sees the verdict; then only when a new decision names it |
| RELEASED, DISCARDED | it has no verdict report (else T6) | at the reading that sees it so; then only when a new decision names it |
| INDETERMINATE | never by a verdict; it is frozen by the control plane | when a decision names it |
| any other | not settled | at every reading |

A settled run cannot change without a new decision that names it: its reports cannot be altered by any granted role,
a new report needs a decision, and its stored value cannot be replaced (for the service's role, by test; the
resistance of reports to the granted roles rests on the earlier role tests, which the reviewer did not repeat).

**Cost of the unsettled set (corrected after review).** In honest operation it is the runs in flight; one reading of
a run took 0.030 to 0.101 s and about 2 KB in the measurements, with a median of 0.060 s and a longest of 0.163 s under
load. The *number* of unsettled runs is bounded by the budget. **Their bytes are not: they are the service's to
choose.** One run kept awaiting its verdict with five large UNKNOWN reports answers with 5,002,287 bytes at every pass
(the reviewer's P3), up to the 32 MiB at which the courier gives a run up as unreadable. A service can therefore make
every reading as slow as it likes and keep a budget NOT COVERED. That is a loss of liveness, not of safety, and the
draft's "about a minute a pass" was for honest reports only.

### 5.3 The mechanism, link by link

| Asked | Answer | Standing |
|---|---|---|
| Are the decisions read incrementally authenticated? | Each is under the chain's hash to the head the witness signs in a checkpoint that bears the reader's nonce. Its operation, the run it names, the verdict claimed and the label are under the hash. The report is not (L-2). | by code and tests A3, A7, with the harness's token |
| Is the cursor continuous? | The courier's checkpoint names the cursor's decision and the witness signs that decision's head back; the mailbox holds the last statement's N and digest. A courier that has lost its cursor reads from the start and begins a new chain (3.3). | the witness's side by test A7; the rest specified, not built |
| Forks, missing decisions, rollbacks | A decision left out breaks the hash to the signed head. A chain cut back gives "beyond the chain" (test A7). A different head for the cursor's decision is a fork. | `e25a297` has these checks (code reading). **Not exercised in this gate.** UNPROVEN |
| A conflicting report added after a run was final | It is recorded as a decision naming the run and is visible after the cursor (by test). Reading the run again and finding the conflict is specified and not built | visibility: by test. Detection: UNPROVEN |
| Complete coverage evidence | The chain of items and the statement's commitments (4.3) | specified; UNMODELLED |

### 5.4 Transfer at about 1,000 runs

From the measurements of 21 November (996 runs, one machine): a decision as the witness gives it grows from 3.8 KB to
127 KB, because each carries the state of every run of its budget, and its hash is over that state. The reviewer's own
model of the same figures gives about 520 MB against the 508 MB measured.

| Reading | Transfer | Note |
|---|---|---|
| from nothing, at 996 runs | 508,180,089 bytes in 126 pages, 37 s for the chain; 98 s for a whole reading by the courier | measured; grows with the square of the runs |
| one new run at about 1,000 runs, following the cursor | about 1.0 MB: its eight decisions at about 127 KB each; plus about 2 KB for the run, 0.6 KB for the checkpoint, at most 1.6 KB for a notice and about 3 KB for the statement | calculated from the measured sizes, honest reports |
| the whole life of a 1,000-run budget, read a little at a time | about 0.5 GB in all: the same total as one reading from nothing | calculated; the square law is spread, not removed |
| each run that is not settled, at each pass | honest: about 2 KB. Adversarial: megabytes, chosen by the service, to 32 MiB a run | measured (5.2) |
| a courier that loses its cursor | the whole reading from nothing again | — |

**No linear scaling is claimed.** S-4 stays open. Removing the square law needs a change to the witness and the store,
which is not proposed.

### 5.5 What cannot be had without changing the witness or the store

- L-1. Whether a decision labelled NONE carried a report. The loss of such a report is not detectable.
- L-2. Which report was recorded at a decision: the chain does not hold its digest.
- L-3. A trace in the chain of a result being stored. Worked round by reading unsettled runs again, at a cost.
- L-4. The square law of the chain's transfer (S-4).
- L-5. A bound on the size of a report: its nonce, its result digest, and the number of reports for one run (S-6).
- L-6. A forgery made before the witness sees anything, and one consistent false chain signed by the witness.
- L-7. The witness's answer for a run is unsigned and takes no nonce: the observation of a run is bound to the
  mailbox's token by the courier's signature alone.
- L-8. No reading lists the budgets (the baseline's UM4).
- L-9. A pause of the whole machine from outside it (3.2).

## 6. The design claims, each with its standing

**PASS** means the claim is supported by evidence that can be run again, within the bounds stated. **FAIL** means the
evidence contradicts the claim. **UNPROVEN** means it is specified, argued or read, and not established. Nothing here
is built, so a PASS is a PASS on facts, never on an implementation. The last column is the standing this note takes:
wherever the author and the reviewer differed, the stricter.

| Id | Claim (as the draft put it) | Author, before review | Reviewer | Standing taken |
|---|---|---|---|---|
| **Decision 1** | | | | |
| G1.1 | An honest gate host signs an UNKNOWN report, and the witness records it without moving the run | PASS | PASS | **PASS** (B1) |
| G1.2 | An honest gate can sign UNKNOWN and later a verdict for one run | PASS as staged | code path PASS; honest deployment UNPROVEN | **Code path PASS. In an honest deployment: UNPROVEN, and not reachable as shipped** |
| G1.3 | The witness's transitions are the six rows of 2.2 and no others | PASS within B3 | PASS only within B3's scope; "no others" unsupported | **FAIL as worded.** PASS for the six rows within B3's scope |
| G1.4 | Under the set rule an UNKNOWN report neither hides nor makes a conflict | PASS within B3 | PASS by construction; B3's counts are not evidence for it | **PASS by construction of the rule only.** B3's counts withdrawn as evidence |
| G1.5 | Permitting T4 gives the baseline's adversary nothing it lacks | UNPROVEN | UNPROVEN | **UNPROVEN.** Hence T4 is not permitted (2.3) |
| G1.6 | Two distinct verdict pairs in one scope fail record verification | rule PASS on data; `e25a297` FAIL | `e25a297` FAIL; rule UNPROVEN | **`e25a297`: FAIL. The rule: UNPROVEN** (not built; gaps found and corrected in text, unreviewed) |
| G1.7 | Identical repeated digests make no conflict | PASS on the data | PASS, on the reviewer's evidence, not B3's | **PASS** (the reviewer's R1: one pair, different bytes, recorded as a repeat) |
| G1.8 | Every report is preserved in the witness's store against every granted role | PASS | PASS for retention; role resistance not reproduced | **PASS for retention** (B3, R1, P1 to P5). Against the granted roles: the earlier role tests, the author's only |
| G1.9 | A failed record is worded as equivocation only | UNPROVEN | UNPROVEN | **UNPROVEN** |
| G1.10 | A verdict after an INTERRUPTED notice is itself noticed | UNPROVEN | FAIL as worded | **FAIL as worded** (keyed on the courier's memory; the reviewer's trace). Restated as C-7; **UNPROVEN** |
| **Decision 2** | | | | |
| G2.1 | A 32-byte token passes the real checkpoint reading and is signed back exactly | PASS | PASS | **PASS** |
| G2.2 | The limit is 1 to 64 characters of letters, digits, `_`, `-`; padding is refused | PASS | PASS | **PASS** |
| G2.3 | The checkpoint's signature binds the nonce and the budget in one statement | PASS | PASS | **PASS** |
| G2.4 | The witness itself refuses a token for the wrong budget, or a second use | FAIL | FAIL | **FAIL.** It must be the mailbox's check |
| G2.5 | The mailbox's token rules enforce single use and refuse every replay named | UNPROVEN | UNPROVEN, with defects in the rules | **UNPROVEN.** UNMODELLED. Two defects of the draft corrected in text, unreviewed |
| G2.6 | A suspend-counting clock that cannot be set is available on the host | PASS for availability | the same | **PASS for availability, resolution, cannot be set. UNPROVEN across suspension or a hypervisor's pause** |
| G2.7 | A late statement never makes a budget COVERED; a fresh receipt never makes an old observation fresh | PASS in the model only | baseline wording fails on the real mailbox; corrected rule UNPROVEN; the model does not model 3.3 | **The baseline's wording: shown to fail on the real mailbox and in the model. The corrected rule: UNPROVEN** |
| G2.8 | NOT COVERED can be seen without a courier | UNPROVEN | UNPROVEN | **UNPROVEN** |
| G2.9 | A bounded time to notification | not claimed | agrees | **Not claimed. The mechanism cannot give it** |
| **Decision 3** | | | | |
| G3.1 | Two honest reports fit whole in a notice | PASS | PASS | **PASS** |
| G3.2 | Two authentic reports always fit whole | FAIL | FAIL, wider | **FAIL**: by the nonce (70,448 bytes) and by the result digest (200,435 bytes) |
| G3.3 | The mailbox as it stands can take a notice of a conflict | FAIL | FAIL | **FAIL** |
| G3.4 | The reference mechanism binds, detects omission and fails closed | UNPROVEN | FAIL as specified | **The draft's: FAIL** (four defects). As corrected in 4.2: **UNPROVEN**, unreviewed |
| G3.5 | The chain of items represents and verifies the set for 1,000 runs | UNPROVEN | UNPROVEN, two defects | **UNPROVEN.** UNMODELLED. The defects corrected in text, unreviewed |
| **Decision 4** | | | | |
| G4.1 | A report enters the store only with a RELEASE or RECONCILE decision naming its run | PASS | PASS | **PASS** (code; part F with the service's own role) |
| G4.2 | A report sent by the release path, early, or at a denied decision is visible after a cursor | PASS | PASS | **PASS** |
| G4.3 | Such a report cannot evade the conflict rule | PASS on data; `e25a297` FAIL | `e25a297` FAIL; design UNPROVEN | **`e25a297`: FAIL. The design: UNPROVEN** |
| G4.4 | The Step 2 count rule as written | FAIL | FAIL | **FAIL**; restated in 5.1 |
| G4.5 | The loss of a report at a decision labelled NONE is detectable | FAIL | FAIL | **FAIL**; not without a change to the store |
| G4.6 | A settled run cannot change without a new decision naming it | PASS for the service's role | PASS for EFFECT with a stored value; "settled" undefined elsewhere | **PASS for an EFFECT run with its value stored.** Other phases defined in 5.2 after review: **UNPROVEN** |
| G4.7 | Reading unsettled runs again closes the gap left by a result stored after a reading | UNPROVEN | UNPROVEN | **UNPROVEN** |
| G4.8 | Forks, rollbacks and missing decisions are detected | UNPROVEN | UNPROVEN | **UNPROVEN** |
| G4.9 | The costs at 1,000 runs, and that they are not linear | PASS | PASS for the chain; FAIL for the unsettled runs' cost | **PASS for the chain's figures. The draft's cost of unsettled runs: FAIL**; corrected in 5.2 |

**Count.** Of 33 claims: 8 stand as PASS on reproducible facts (G1.1, G1.7, G2.1, G2.2, G2.3, G3.1, G4.1, G4.2); 7 are
PASS only in a narrowed sense stated beside them (G1.2, G1.3, G1.4, G1.8, G2.6, G4.6, G4.9); 5 are FAIL as negative
findings the design is built round (G2.4, G3.2, G3.3, G4.4, G4.5); 12 are UNPROVEN (G1.5, G1.6, G1.9, G1.10, G2.5,
G2.7, G2.8, G3.4, G3.5, G4.3, G4.7, G4.8); one is not claimed (G2.9). Four of the draft's own statements failed at
review (G1.3, G1.10, G3.4 and part of G4.9). Every claim about how the new mechanisms would behave is UNPROVEN.

## 7. Remaining counterexamples and proof obligations

**Counterexamples that stand** (none is repaired):

1. A second EFFECT report with another digest, recorded as VERDICT_RETRY; the stored PASS is believed (S-1).
2. A verdict report recorded with a RELEASE, or before START, or before the attempt exists; the courier believes it and
   is silent (S-5).
3. A report larger than the mailbox's limit, authentic and on record, by its nonce or by its digest (S-6).
4. A run in a phase the courier does not ask about, carrying reports nobody reads (S-7).
5. A run that was reserved and released, with a gate-signed EFFECT report beside its fence report (the reviewer's P5).
6. A run awaiting its verdict with two verdict pairs and no recorded verdict (the reviewer's P4).
7. The baseline's receipt-counted freshness: in the model, and now on the real mailbox (the reviewer's R5).
8. The draft's rule for a verdict after an INTERRUPTED notice, under a courier that loses its state: the budget reads
   COVERED while the mailbox holds "no verdict" for a run that has one (the reviewer's enumerator, 598 states).
9. The nine weakened variants of the model, each breaking an invariant; three searches stopped at 14,000,001 states.
10. The forgery made before the witness sees anything (UM6 a), with or without an UNKNOWN before it.
11. The service slowing the witness, or swelling one run's answer, so that no reading ends in time.

**UNMODELLED, by the owner's instruction, until independently tested or modelled:**

- PO-A. **The mailbox's token state machine** (3.3). The reviewer did not model it; its findings on it are argued from
  the text.
- PO-B. **The per-budget chain of items** (4.3), with the rule for a new chain. The reviewer's enumerator covers one
  question at very small bounds and is not a model of the chain.

**Other obligations open after this gate** (the Step 2 note's PO-1 to PO-19 stand except as stated):

- PO-6 (the token through the witness): tested for the witness's side. The mailbox's side is PO-A.
- PO-7 (reports only with decisions; the release path): tested.
- PO-8 (the count rule against every kind): tested, and the rule corrected.
- PO-9 (UNKNOWN): examined; G1.5 UNPROVEN; T4 not permitted.
- PO-C. The model has no UNKNOWN report, no release-path report, no result stored after a reading, no epochs, no
  replay, and an acceptance rule that is not 3.3's. Each rule of this gate that touches those is outside the model.
- PO-D. Suspension, and a pause by a hypervisor, against the mailbox's clock.
- PO-E. Forks and rollbacks against the cursor and the mailbox's continuation rule.
- PO-F. The status with a reader's nonce, and the reader's rule that no fresh status is NOT COVERED.
- PO-G. The wording of every failing finding: that none says more than equivocation.
- PO-H. T6, C-4 and C-5: the rule over fence reports, key sets and every phase. Written after review; unreviewed.
- PO-I. Every correction marked "after review" in this note. None has been reviewed.
- The deployment-security blockers B-1 to B-3 are untouched: no compliance claim can be made whatever is built, and
  with one account running everything no test can show the contract's conditions.

## 8. Findings of this gate for the defect register

Entered in `verify/DEFECT_REGISTER.md` as a new dated Part E, beside S-1 to S-4; nothing earlier is changed.

- **S-5.** A gate-signed verdict report recorded with a RELEASE decision, or with a RECONCILE before its run's START or
  before its attempt exists, is believed by the courier of `e25a297`, which made no notice. A second route to S-1.
- **S-6.** The size of a gate report is not bounded short of the database's own limits: by its nonce (70,448 bytes
  recorded), by its result digest (200,435 bytes recorded), and by the number of reports for one run (a 5 MB answer).
- **S-7.** The courier of `e25a297` does not ask for the reports of a run that is NO_EFFECT, INDETERMINATE or
  RELEASED, and `run_outcome` ignores a NO_EFFECT report on an EFFECT run. Found by the reviewer.
- **Observations, not entered as defects.** The store answers a refused replacement of a stored result as success.
  The witness gives a checkpoint, with any nonce, to the governor's certificate. The mailbox does not check a notice's
  words. The record's sixth check compares reports with one gate key. The record's checker appears to fail any record
  that carries a fence report (the reviewer's side observation; not investigated).

## 9. The independent review, and what was done with it

One Opus-tier reviewer, a model separate from the author's, as the owner authorised; no other escalation. It worked in
two phases: first its own view from the code, the baseline and the raw outputs, with experiments of its own on the
real components; then, only afterwards, the draft's claims. Its reports are in
`verify/DESIGN_GATE_REVIEW_AMEND16_2026-11-21.md`, unchanged. It is an internal review, not an independent validation.

**Its independence, and its limits.** It did not open the design documents in phase 1. It says itself that the test
scripts it was allowed to read show the shape of the author's rule, and that this may have influenced it. It did not
repeat most of the author's tests; it checked them against their raw fields and ran its own. It did not model the
token state machine. It withdrew one of its own phase 1 findings in phase 2 (that the service could leave a report out
of a record: the record is signed by the engineer).

| The reviewer's finding | Where | What was done |
|---|---|---|
| UNKNOWN has three meanings | phase 1, Q1 | adopted: "Words used" |
| Report identity is the pair, not the bytes (shown by re-signing) | R1; B1.4 | adopted: C-2; 4.2's choice of reports |
| Belief only from the report at the authorised, recorded decision | V4; R3 | adopted: C-3 |
| The honest UNKNOWN-then-verdict cannot arise in the shipped deployment; B2 is harness glue | G1.2 | accepted: 2.1 rewritten; G1.2 downgraded |
| B3 compares a predicate with itself | G1.3, G1.4 | accepted: 2.2 rewritten; the counts withdrawn as evidence for the rule |
| The owner's two conditions for T4 are met only in part | Q1 | accepted: **T4 is not permitted** (2.3). The draft permitted it |
| The null-nonce scope and a released run with an EFFECT report | P5; B1.1 | adopted: T6 |
| The courier never reads NO_EFFECT, INDETERMINATE or RELEASED runs | B1.2 | adopted: C-5; settled defined for every phase; S-7 |
| Gate-key sets may differ; check 6 uses one key | B1.3 | adopted: C-4, as a precondition and a check |
| Oversized or malformed digests | P2; B1.5 | adopted: C-6; S-6 widened; 4.2's bounded fields |
| A conflict with no VERDICT_RECORDED | P4; B1.6 | adopted: T5's wording; 4.2's choice of reports |
| C-3 of the draft (a verdict after INTERRUPTED) fails under loss of the courier's state | F.1 | adopted: C-7, decided from the witness's data |
| A statement that arrives before its items spends its token; the model's rule differs | B2.1 | adopted: the statement is an item of the chain; the model said not to model 3.3 |
| Continuation against a new chain | B2.2 | one rule proposed (3.3); PO-B stays open |
| The freshness bound of the status says too much | B2.3 | accepted: 3.4 restated |
| A used mark lost while the epoch survives | B2.4 | recorded in 3.3; durable write before any answer |
| The notice cannot always carry the digest | B3.1 | adopted: every field bounded |
| The report's digest must be canonical | B3.3 | adopted |
| Nothing lets a reader retrieve items or evidence | B3.4 | accepted: two readings added to the minimum (section 10) |
| Head-of-line blocking | B3.5 | answered by bounded fields: every item can be delivered |
| A notice of a conflict does not by itself fail a record | B3.6 | accepted: 4.2 restated |
| "Settled" undefined outside one phase; the unsettled set's bytes are the adversary's | B4.2, B4.3; P3 | accepted: 5.2 rewritten |
| "By test: C1" over-read | B4.6 | accepted: 5.1 and 5.3 restated |
| Fourteen sentences the outputs do not support | C.1 to C.14 | each corrected or labelled in sections 1 to 5 and 8 |
| Reads made with the owner's password, unlabelled | C.8 | labelled; repeated with the service's own role (part F) |
| The harness writes into the pinned copy | C.3 | recorded in section 1 |
| DP1 and DP2 unmet: no test can show the contract | E.8 | stands: B-1, B-2 |

**Not adopted, or left open.** None of the reviewer's findings was rejected. Its suggestion that either choice on T4 is
safe is not taken as permission: the owner's default decides. Its item E.6 (an independent model or test of the token
machine and the item chain) is not met.

## 10. The minimum changes for a Step 3 (none is made)

**The witness, the gateway, the store: none.** The three readings as they are.

**The mailbox** (Step 2's MB-1 to MB-10 stand; *gate* marks what this gate adds or makes exact; *review* marks what
the review showed was missing):

| Interface | Change |
|---|---|
| `POST /challenge` (new) | MB-1: a token for a budget and a courier key, written durably and then returned signed, with epoch, serial, L and the moment of issue |
| `POST /deliver` (changed) | MB-2: takes the new item form with its chain fields, the notices of T4, T5 and T6, observation parts and the statement of coverage as an item; *gate*: refuses an item that is not the next of its chain and says where its head is; refuses a notice that names evidence it does not hold; *review*: accepts a new chain only with a statement of a reading from nothing |
| `POST /evidence` (new, *gate*) | a piece of evidence up to a set size, stored under its canonical SHA-256, answered with a signed holding |
| `GET /evidence` (new, *review*) | a piece of evidence, by its digest |
| `GET /items` (new, *review*) | the items of a chain, in the mailbox's order of acceptance, with their receipts |
| `GET /status?root=B&nonce=R` (new) | MB-10; *gate*: signs back the asker's nonce; *review*: says how many chains the budget has had |
| `GET /pubkey` | as today |

| Configuration and storage | Change |
|---|---|
| the witness's public keys | MB-3: to check a checkpoint; the mailbox holds none today |
| L, the bound on tokens, the size limits | MB-9: set by the operator at start |
| the clock | MB-4; *gate*: `CLOCK_BOOTTIME` by name, never `time.monotonic()`; *review*: the epoch includes the boot identifier |
| challenges, statements (accepted, spent, late), items indexed by chain in order of acceptance, evidence, anomalies | MB-5 to MB-7: each written whole and synced before any answer |

**The courier and the record's checker** (not the mailbox; listed so that the whole is seen): the rule of 2.3 with its
conditions C-1 to C-7; the count rule as restated; reading every phase; the unsettled set; its own durable copy of
large evidence; the new item form. Much of this is in `check_record`, which the mailbox imports: a change there is a
change to the mailbox.

**This list is larger than the draft's, and it is still a list for a design that has not passed its gate.**

## 11. Recommendation: NO-GO for Step 3 implementation

**NO-GO today.** Not because the approach has failed: the reviewer's own view is that the outline of the consistency
rule and of incremental reading is sound, and every fact the design leans on about the frozen parts is established.
The reasons are these.

1. **The design text failed its review in each of the four decisions.** Four of the draft's own statements were shown
   wrong, two by counterexamples run on the real components. The corrections are in this note and **nobody has
   reviewed them**.
2. **The two mechanisms the mailbox would be built on are unmodelled**, as the owner required them not to be: the
   token state machine and the chain of items. The author's model does not model the token rules as written.
3. **Every claim about the behaviour of what would be built is UNPROVEN.** That is expected of a design, but with
   (1) and (2) it means an implementer would be building from text that was shown wrong on the day it was written.
4. **The owner has decisions to make that change what is built**: T4 (this note keeps it forbidden, by the owner's
   default); the rule for a courier that has lost its state; whether the mailbox is to hold large evidence and serve
   readers; and whether B-1 and B-2 are to be resolved first, since without them no test of a Step 3 could show the
   contract's conditions.

**What would turn it into GO**, in the order it could be done, none of it code of the courier, mailbox, witness or
gateway:

- (a) the owner's decisions under (4);
- (b) one more review, of this note's corrected text only, by a reviewer who has not written it;
- (c) an independently authored model or exhaustive test of the token state machine and of the chain of items with
  its new-chain rule, with its bounds stated, including the reviewer's state-loss trace;
- (d) the validation tests for a Step 3 written from this note by someone other than the implementer, before the
  implementation.

**What must wait for an implementation in any case:** that a mailbox enforces 3.3; the clock across a real suspension;
the wording of failing findings; coverage under adversarial cost; forks and rollbacks under the cursor; and that
records and notices of the earlier forms still verify.

**Nothing further is done without the owner's explicit approval. No coding has begun.**
