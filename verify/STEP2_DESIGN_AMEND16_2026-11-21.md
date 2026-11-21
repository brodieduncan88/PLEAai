# Amendment 16, Step 2: a design-and-verification note. The COVERED / NOT COVERED model, and detecting more than one signed digest for a run

21 November 2026. Private working material. Internal work under the owner's direction. It is not an independent
validation, it is not a declaration, and it is not an implementation. Authorised by the owner on 21 November as a design
and verification exercise only. Nothing is implemented here: the check for more than one digest is not written, the
courier, the mailbox and the gateway are not changed, no credential or deployment configuration is edited.

The design baseline is `verify/AMEND16_THREAT_MODEL_ADDENDUM_2026-11-21.md` at `0da1a85e` on `verification-
amendment-16`, accepted by the owner as a threat-model design baseline and not as an implementation or a security
declaration. `e25a297`, the eighth form of the courier, is and stays INCOMPLETE, rejected at internal review and
undeclared. Citations are to the tree at `e25a297`; the mailbox's file is the same at `0da1a85e`.

This note is for review before any coding begins. It returns: the mailbox inspection (section 1), the three guarantees
kept apart (2), the assumptions (3), the model and its results (4), the counterexamples (5), the specification for
detecting more than one signed digest (6), the proposed signed assertions against the evidence that exists (7), the
disposition of the eighth review's four unconfirmed findings (8), the outstanding implementation requirements (9), the
proposed validation tests (10), and what is still unsupported (11).

## 1. The mailbox, its clock, its receipts and the channel to it: a read-only inspection

Read: `verify/mailbox_service.py` (233 lines), and in `verify/courier.py` the transport (212-330), the delivery
(431-440), the outbox (855-935) and the log of deliveries (463-477); in `verify/check_record.py` what a notice and a
receipt must be (88-99, 456-512). Nothing was run for this section.

**What the mailbox is.**

- M1. A passive store with two requests: POST /deliver and GET /pubkey (mailbox_service.py 9-13, 172-192). It has no
  other reading, no statement of its own state, no waiting limit, and no notion of a budget.
- M2. It admits a client by a certificate of the certificate authority it was given, and by name if names were given
  with `--tls-allow`. If no name is given, any client holding a certificate of that authority is admitted (167-170).
  The deployment gives the name `courier`. A notice must also be signed by a courier key the mailbox was started with
  (115-117).
- M3. It takes only a NOTICE of a form and an outcome that `check_record` knows (check_record.py 476-493; the outcomes
  at 97-98). A statement of coverage, or a notice of a conflict, would be refused today as not readable. A notice is
  at most 64 KiB (51, 186).

**Its clock.**

- M4. One clock is used, once: the wall clock of its host, in whole seconds (70-71), written as the `time` of a
  receipt (127) and signed with it (check_record.py 90). Nothing guards against that clock being set back or forward.
  Nothing compares it with a notice's own time, with a checkpoint's, or with anything else. The mailbox offers its
  clock to no one except through a receipt.

**Its receipts and what they keep.**

- M5. A receipt signs: the notice's digest, the budget, the run, the outcome, the mailbox's name and that time
  (126-128). It says that this process, holding this key, had stored this notice at that time by its clock (23-27).
- M6. A notice is kept whole or not at all: its readable copy and then the notice with its receipt are each written to
  a temporary file, flushed, synced, renamed, and the folder synced, before the receipt is sent (74-87, 129-131).
- M7. A notice delivered again is answered with the receipt first given, time included, and is not kept twice
  (120-123). So delivering again does not make a notice look newer. One exception: a kept copy that cannot be read is
  written again with a new receipt and a new time (124-125), so two receipts with two times can exist for one notice.
- M8. Stopped between its two writes, the mailbox holds the readable copy and no receipt; the next delivery writes both
  again with a new time.
- M9. Nothing in the mailbox removes a notice, and nothing in it would show that one had been removed from its folder
  by the account that owns the folder. In the demonstration that account is the service's (15-17).
- M10. A listing of what is held is read from the folder and sorted by the receipts' times as text (133-140, 220-226).
  A listing is not signed.

**The channel from the courier.**

- M11. HTTPS only, with the courier's client certificate and the certificate authority given, one connection for each
  request, 60 s for a whole request, an answer read to 32 MiB at most (courier.py 212-236, 294-300).
- M12. Before it sends, the courier asks the mailbox for its key and goes on only if the key is one it was given
  (881-891). It takes an answer as a receipt only if it is signed by a mailbox key given and names the notice
  (431-440).
- M13. A notice is saved in the courier's state before it is sent, stays in its outbox until a valid receipt comes, is
  tried oldest first, and is never dropped (855-935). A receipt is appended to the courier's log of deliveries and
  synced (463-477).
- M14. Nothing bounds how long a notice waits in the outbox. The only signs of the wait are the notice's own time (the
  courier's clock) and the receipt's (the mailbox's).

**What the evidence that exists supports, and what it does not.**

| Claim a signed assertion might make | Evidence today | Supported? |
|---|---|---|
| the mailbox stored this notice | the receipt, signed; the file, synced | yes, at the time of the receipt |
| at what time, by the mailbox's clock | the receipt's `time` | yes, to the second, for a clock nothing checks (M4) |
| the mailbox still holds it | the folder | only by assumption (M9) |
| the observation behind a statement is no older than the waiting limit | none: the receipt says when a statement arrived, not when its reading began (M14) | **no** |
| at this moment, by the mailbox's clock, the budget is COVERED | none: nothing at the mailbox works it out or signs it (M1, M10) | **no** |
| the mailbox's clock does not go backwards | none (M4) | **no** |
| the mailbox accepted a statement of coverage or a notice of a conflict | none: both would be refused (M3) | **no** |
| a statement names every notice of a large budget | a notice holds 64 KiB (M3); a digest is 64 characters | only up to about 900 notices, unless the list is given as a digest |

## 2. Three guarantees, kept apart

No sentence, status or model variable below derives one of these from another.

| Guarantee | What it is | What shows it | What it never shows |
|---|---|---|---|
| **Record consistency** | a run does not carry more than one distinct signed result | the reports the witness gives for the run, compared with one another and with the chain | which result is true; who signed |
| **Verdict authenticity** | a report was signed by a gate key the reader was given, for this budget, run and nonce | the signature | that the holder of the key ran the check, or that the result is what the check gives |
| **Verdict correctness** | the result agrees with what an authorised run of the check would give | nothing in the notification path. It needs a gate whose key the service does not hold (blocker B-3) | — |

Five situations a reader must be able to tell apart, and what each allows to be said:

| Situation | What is observed through the existing readings | Consistency | Authenticity | Correctness | What may be signed |
|---|---|---|---|---|---|
| A conflicting digest is observed | two or more authentic EFFECT reports for one run, with different digests | broken, and said | each report authentic | not known for either | a notice of the conflict; the run's outcome as today |
| An identical digest is repeated | two or more authentic reports, one digest | holds | authentic | not known | nothing new: a repeat is not a conflict |
| The witness is unavailable | no checkpoint, or no answer for a run | nothing observed | nothing observed | nothing observed | no statement of coverage; nothing about any run |
| Coverage is incomplete | a run not asked for, asked for and not answered, or an answer that lacks a report the chain says was recorded | not known for that run | not known | not known | no statement of coverage; the budget reads NOT COVERED, which says nothing of any verdict |
| A report is authenticated but may be forged | one authentic report (however often repeated) and a stored result that matches it | holds | authentic | **not established**: the first report can itself be the forgery | the run's outcome "as the gate's key signed it", never "as the check found" |

## 3. Assumptions

These are the model's and the proposed assertions' assumptions. Each is named, and each that the code does not support
is marked.

- **The baseline's.** The locked table of the service's powers; the deployment preconditions DP1 to DP4 with residual
  risks R1 and R2; the parties' assumptions A1 to A5 (addendum, sections 2 to 4). DP1 and DP2 are not met by the
  demonstration.
- **MA1, the mailbox's clock.** It does not go backwards, and it moves forward at a rate near real time while a
  statement is fresh. **Not supported by the code** (M4). It is the mailbox's operator's to ensure.
- **MA2, the waiting limit.** It is set by the mailbox or its operator, on the mailbox's clock, before acceptance
  testing, and is held where COVERED is worked out. **Nothing holds it today** (M1).
- **MA3, delivery.** No time is assumed. A statement or a notice may wait any time in the courier's outbox. So the age
  of an observation must be measured from before the reading began, not from when its statement arrived (section 5,
  counterexample `receipt_time`).
- **MA4, what the mailbox holds.** What it has receipted it still holds. Supported for a stop of the process (M6); **not
  supported against the account that owns its folder** (M9), which the baseline's A2 and DP2 must exclude.
- **MA5, the token.** The mailbox can give the courier a token that did not exist before it was given, with the
  mailbox's time, and the witness will sign it back in a checkpoint. The second half is supported: a checkpoint signs
  back a nonce of up to 64 characters of letters, digits, `_` and `-` (`plea_gateway/witness_service.py` 96-99, 115-116;
  check_record.py 88), with no change to the gateway. **The first half is not: the mailbox gives no token** (M1).
- **MA6, a stored value stays.** Shown by test for the role `plea_local`; it holds only where DP1 and DP3 do.
- **MA7, reports are not removed.** Shown by test for the three roles the store grants; the owner can remove one (DP1).
  The count rule of section 6 is what turns a removal into "not whole" and not into silence.
- **What the model does not cover:** a courier that loses its own state; a mailbox that loses what it holds; more than
  two runs, three decisions and three ticks of the clock; any clock but the mailbox's; time within a reading.

## 4. The model

`tests/diag_amend16_model/model.py`: a state machine of 299 lines, explored breadth-first, so that a counterexample
found is a shortest one, and, where the search reached its end, every reachable state at the stated bounds was
checked. To run it again: `tests/diag_amend16_model/run_all.sh PYTHON` (about half an hour; one variant needs several
gigabytes of memory). Results: `tests/diag_amend16_model/results_2026-11-21/`. A model is a statement of rules and a
search of their consequences. It is not the courier, and a clean result here is not evidence about any code.

**The world at its bounds.** Two runs, both truly FAIL, which is the worst case for notification. The honest result has
digest `f`; a forged PASS has digest `p`. Run 0 may carry two reports of either digest; run 1 one honest report. Three
decisions. The mailbox's clock runs 0, 1, 2. The waiting limit L is one tick.

**The service's moves** (the locked table): have a report recorded for a run with either digest, the first as the
reconcile and a later one as a duplicate kept with its report; store a value, the first of which stays; leave any
reading of a run unanswered, as often as it likes. A forged first report is the forgery before the witness sees
anything. **The environment's:** the mailbox's clock ticks; a notice or a statement waits in the outbox for any time.
**Outside the contract**, only in the variants that say so: the owner deletes a recorded report or replaces a stored
value.

**The proposed rules** (the variant `spec`).

1. *Begin.* The courier takes a token from the mailbox, which is the mailbox's clock at that moment, and a checkpoint
   at decision N that signs the token back.
2. *Ask.* It asks for every run that is not final, and for every final run for which the chain to N holds more
   reconcile decisions than it had seen when it took the run as final (the re-read rule). An answer is used only if it
   carries one report for each reconcile decision of the chain to N (the count rule). Reports after N are left out.
3. *Observe.* For one run: D is the set of digests among its reports to N. A conflict is observed if and only if D
   holds more than one. The outcome is final if and only if a value is stored whose digest is in D.
4. *End.* A FAIL notice for a final FAIL. A CONFLICT notice for a conflict. The reading is whole if and only if every
   run was observed in this reading, or was final already with nothing new for it in the chain. A run asked for and
   not answered, and an answer that fails the count rule, make it not whole. If it is whole, a statement of coverage is
   made, naming the token, N, and every notice made so far.
5. *COVERED.* At mailbox time t the budget is COVERED if and only if the mailbox holds a statement of coverage whose
   token is no older than L, and holds every notice that statement names. Anything else is NOT COVERED.

**The invariants**, checked in every reachable state. The first three use facts no party can see (when a FAIL became
committed, when a conflict came to exist); they are the model's, not anyone's evidence.

- **NOTICED.** If the budget is COVERED at t, every FAIL committed before t − L has its notice in the mailbox. A FAIL is
  committed when its report is recorded and its value is stored.
- **CONSISTENT.** If the budget is COVERED at t, every run that has carried two different signed digests since before
  t − L has a notice of the conflict in the mailbox.
- **OBSERVED.** No statement of coverage is ever made without the observations the definition requires.
- **TRUE.** Every notice ever signed is true of its run: a FAIL notice only for a FAIL that was committed, a CONFLICT
  notice only for a run that carries two different digests.

Nothing in the model, and no invariant, says or uses that a verdict is correct.

**Result for the proposed rules.** 4,137,699 states, explored to the end: yes. Invariants broken: none. Bounds: 2
runs, 3 decisions, the mailbox's clock 0 to 2, waiting limit 1 tick.

**What the model shows to be reachable with every invariant holding** (these are limits of the guarantee, shown as
traces in the results, not failures of it):

- COVERED while a truly failed run stands as PASS on one authentic report (the forgery before the witness):
  correctness is not guaranteed. (7 steps.)
- NOT COVERED with no run failed: a statement has lapsed, and nothing says or implies a FAIL. (7 steps.)
- COVERED with a CONFLICT notice held for a run with two different digests: the conflict is said, which result is true
  is not. (8 steps.)
- COVERED with a run that carries the same digest twice and no CONFLICT notice: a repeat is not a conflict. (8 steps.)

**Liveness is not promised, and the model shows why.** If the service lets no reading of a run be answered, the budget
is never COVERED: of the 20,330 states reachable under that restriction, none is COVERED. That is safe, and it is the
whole of F1 and F2 (section 8): the service can keep a budget NOT COVERED for as long as it likes, and cannot make it
read COVERED. No rule here promises a time by which a budget is COVERED or a run's notice arrives.

## 5. Counterexamples

Each variant removes or weakens one rule. Each trace is a shortest one and is given in full in the results file.

| Variant | The rule removed or weakened | States | Explored to the end | Invariants broken | Shortest trace |
|---|---|---|---|---|---|
| `no_detection` | the eighth form's reading of reports: any recorded digest is believed and two digests are not remarked on (S-1) | 2,722,925 | yes | CONSISTENT | CONSISTENT: 9 steps |
| `no_reread` | conflicts looked for only when a run is read for its outcome: a final run is never asked for again | 3,892,397 | yes | CONSISTENT | CONSISTENT: 14 steps |
| `asked_is_enough` | a reading counts as whole when every run was asked for, answered or not (the eighth form, D-d) | 5,684,884 | yes | CONSISTENT, NOTICED, OBSERVED | CONSISTENT: 9 steps; NOTICED: 9 steps; OBSERVED: 4 steps |
| `no_lapse` | a coverage statement never lapses (the eighth form's WATCHING) | 4,137,699 | yes | CONSISTENT, NOTICED | CONSISTENT: 9 steps; NOTICED: 9 steps |
| `receipt_time` | freshness counted from the mailbox's receipt of the statement, as the addendum's section 7 words it, not from a token taken before the reading | 7,478,677 | yes | CONSISTENT, NOTICED | CONSISTENT: 9 steps; NOTICED: 9 steps |
| `carry_over` | the outcome of a run that is not final is carried over from an earlier reading instead of being observed again | 14,000,001 | no | CONSISTENT, NOTICED, OBSERVED | CONSISTENT: 13 steps; NOTICED: 13 steps; OBSERVED: 8 steps |
| `names_new_only` | a coverage statement names only the notices of its own reading, not every notice made so far | 6,073,407 | yes | CONSISTENT, NOTICED | CONSISTENT: 13 steps; NOTICED: 13 steps |
| `no_count_rule` | the proposed rules without the count rule, with the owner's powers (a precondition broken) | 14,000,001 | no | CONSISTENT, NOTICED | CONSISTENT: 10 steps; NOTICED: 10 steps |
| `owner` | the proposed rules, with the owner's powers (precondition DP1 broken) | 14,000,001 | no | NOTICED | NOTICED: 10 steps |

**`no_detection`, in full.** CONSISTENT: COVERED at t=2, yet run 0 has carried two different signed digests since t=0
and the mailbox holds no notice of it.

1. service: report for run 0 with digest 'f' recorded at decision 1
2. service: report for run 0 with digest 'p' recorded at decision 2 (a duplicate, kept with its report)
3. the mailbox's clock: 1
4. the mailbox's clock: 2
5. courier: begins a reading; token t=2 from the mailbox; checkpoint at decision 2
6. courier: asks for run 0; observes outcome N and two different signed digests
7. courier: asks for run 1; observes outcome N
8. courier: ends the reading; WHOLE: coverage statement to decision 2 with token t=2, naming []
9. courier: delivers ('COV', 2, 2, frozenset()); the mailbox receipts it at t=2

**`no_reread`, in full.** CONSISTENT: COVERED at t=2, yet run 0 has carried two different signed digests since t=0 and
the mailbox holds no notice of it.

1. service: report for run 0 with digest 'p' recorded at decision 1
2. service: stores the value 'p' for run 0
3. courier: begins a reading; token t=0 from the mailbox; checkpoint at decision 1
4. service: report for run 0 with digest 'f' recorded at decision 2 (a duplicate, kept with its report)
5. the mailbox's clock: 1
6. the mailbox's clock: 2
7. courier: asks for run 0; observes outcome P
8. courier: asks for run 1; NO ANSWER
9. courier: ends the reading; not whole, no coverage statement
10. courier: begins a reading; token t=2 from the mailbox; checkpoint at decision 2
11. courier: run 0 is final already and the chain holds nothing new for it; not asked
12. courier: asks for run 1; observes outcome N
13. courier: ends the reading; WHOLE: coverage statement to decision 2 with token t=2, naming []
14. courier: delivers ('COV', 2, 2, frozenset()); the mailbox receipts it at t=2

**`receipt_time`, in full.** CONSISTENT: COVERED at t=2, yet run 0 has carried two different signed digests since t=0
and the mailbox holds no notice of it.

1. service: report for run 0 with digest 'f' recorded at decision 1
2. courier: begins a reading; token t=0 from the mailbox; checkpoint at decision 1
3. service: report for run 0 with digest 'p' recorded at decision 2 (a duplicate, kept with its report)
4. the mailbox's clock: 1
5. the mailbox's clock: 2
6. courier: asks for run 0; observes outcome N
7. courier: asks for run 1; observes outcome N
8. courier: ends the reading; WHOLE: coverage statement to decision 1 with token t=0, naming []
9. courier: delivers ('COV', 0, 1, frozenset()); the mailbox receipts it at t=2

Where "explored to the end" says no, the search was stopped at 14,000,001 states. The counterexamples found there are
real and shortest among the states searched; nothing is claimed about an invariant that was not seen to break. A first
run of all variants in one process was killed for want of memory after six of them; its output is kept beside the
results, and the six agree with the run reported here.

**A counterexample against the baseline's own wording.** The addendum's section 7 defines COVERED by a statement "which
M receipted at a time r with t − r no more than the waiting limit". The variant `receipt_time` is that wording, and it
breaks NOTICED: a statement made from a reading at t=0 can wait in the outbox and be receipted at t=2; the budget then
reads COVERED at t=2 on an observation two ticks old, and a FAIL committed after that reading and long before t − L has
no notice. The receipt shows when the statement arrived, not when the budget was observed (M14). **Proposed correction,
for the owner's decision:** COVERED is judged by the age of a token the mailbox gave before the reading began and the
witness signed back in the checkpoint, not by the receipt's time. This needs something from the mailbox that it does not
give today (MA5) and no change to the gateway. The baseline at `0da1a85e` is not edited for this; the correction is put
to the owner here.

**What a broken precondition does.** These two variants were stopped at 14,000,001 states and are not exhaustive, so
they show what breaks and prove nothing about what holds. With the owner's powers and the proposed rules (`owner`),
NOTICED breaks: the owner replaces a stored FAIL value before the courier has read the run, the run then reads as not
final, and a whole reading follows with no notice of a FAIL that had been committed. No breach of CONSISTENT was found
in the states explored: a deleted report fails the count rule and the reading is not whole. Without the count rule
(`no_count_rule`) the deletion of one of two conflicting reports breaks CONSISTENT silently. So the count rule answers
the removal of a report, and nothing in these rules answers the replacement of a stored value: that is what
precondition DP1 is for. A FAIL notice already in the mailbox stays there whatever the owner does to the database.

## 6. Specification: detecting more than one distinct gate-signed digest for a run, with the witness's existing readings

This is a specification for review. It is not implemented, and it uses nothing the witness does not already give.

**Inputs, for one run at one checkpoint.** From GET /chain, verified to the checkpoint's head as today: the decisions
for the run whose operation is RECONCILE, each with its number, kind, code and operands. From GET /run: the reports
(`evidence`, each with the number of the decision it was recorded with) and the stored result. The checkpoint's decision
N.

**Step 1, authenticity.** A report is *authentic* if and only if it is an effect report, its signer is a gate key the
reader was given, its signature verifies over the report's signed fields, and it names this budget, this run and this
run's nonce. This is `check_record.run_outcome`'s own test (check_record.py 189-194). It establishes verdict
authenticity and nothing else.

**Step 2, the count rule.** Leave out reports recorded after N. Then every RECONCILE decision for the run, up to N,
whose derived label is AUTHORISED must have exactly one authentic report at its number, with the verdict the
decision's operands name; and every report must sit at such a decision. If not, the run is **not observed**: the
witness's answer lacks, or adds, a report against the chain it signed. The reading is then not whole. (Shown by test:
with the owner's password a report was deleted, and the chain still held its decision.)

**Step 3, the digests.** Let D be the set of distinct pairs (verdict claimed, result digest) among the authentic
reports that claim EFFECT or NO_EFFECT. A report that claims UNKNOWN is left out: an unknown outcome followed by a
verdict is the honest course of an interrupted run.

- D empty: no signed result yet.
- D of one member, however many reports carry it: **one signed result**. A repeat is not a conflict. (Shown by test: the
  gate host's own report sent twice is recorded twice with one digest.)
- D of more than one member: **a conflict**. The record is not consistent for this run.

**Step 4, the outcome, unchanged.** The run's outcome is worked out as today from the stored result and the digests. The
conflict is an additional finding. It may only add a notice: it never removes or replaces the notice the outcome calls
for, so a fault in the detection cannot hide anything that is noticed today (the rule the property file sets for P7).

**Step 5, the re-read rule.** A run already taken as final is asked for again in any reading whose new decisions include
a RECONCILE for it. Without this, a conflict that arises after a run was read stays unseen (section 5, `no_reread`). The
chain alone tells which runs these are; no reading of a run is needed to know.

**Step 6, what is said.** One notice for a run in conflict, made once for each new set D, in words of record consistency
only (section 7). It does not say which result is true, that a verdict was changed, or that any report was forged.

**For the record's checker.** The record already carries every report of a run with its decision number
(`verify/verify_record.py` 146-159), and the sixth check already ties each report to a RECONCILE decision of the chain
(check_record.py 858-859). The same steps 1 to 3 apply to a record. Whether a record in conflict fails the check or is
marked is a decision for the owner; at `e25a297` it verifies.

**What the detection cannot do.** It cannot see a forgery made before the witness sees anything: one report, one
decision, nothing to compare. It cannot say which of two results is true. It rests on reports not being removed (MA7);
the count rule is its only guard there, and that guard rests on the chain, which the owner of the database could also
rewrite (out of scope, and precondition DP1).

**Only partly exercised.** The conflict of two EFFECT reports was made and read on the deployment. A NO_EFFECT report
beside an EFFECT report was recorded and read on the deployment (it was refused as a verdict, and kept with its
report), but no notice wording or test of that pair exists.

## 7. Proposed signed assertions, each against the evidence that exists

Proposed wording is for review and is not adopted. For each assertion: who signs, the condition under which it is true,
the evidence the signer holds for it, and what it must not say.

| Assertion | Signed by | True exactly when | Evidence held | Supported today? |
|---|---|---|---|---|
| A run's outcome (as today) | courier | the outcome was worked out from the witness's answer for this run, received after the checkpoint at decision N, with an authentic report and a stored result that matches it | the answer; the checkpoint | yes, once the provenance sentence says which of four cases applies (below) |
| A run carries more than one signed result (new) | courier | at decision N the witness's answer, received in this reading and passing the count rule, held authentic reports with more than one distinct (verdict, digest) | the answer; the chain's decisions | the data, yes; the notice kind, no (M3) |
| A run could not be observed (as UNREADABLE today, widened) | courier | the run was asked for and no usable answer came, or the answer failed the count rule | the courier's own record of the request | yes |
| The budget was read whole to decision N (new; replaces WATCHING) | courier | clauses O1 to O4 of the baseline's section 7, with O1's nonce being the mailbox's token | the checkpoint bearing the token; each run's answer or its earlier final observation; the list of notices | **no**: there is no token (MA5), no such notice kind (M3), and the list may not fit (M3) |
| The token was given at this time (new) | mailbox | the mailbox made this token at this time by its clock, and had not given it before | the mailbox's own clock and record | **no**: nothing gives a token (M1) |
| A notice is held (the receipt, as today) | mailbox | the mailbox stored this notice at this time by its clock | its folder and clock | yes (M5, M6) |
| The budget is COVERED to N, or NOT COVERED, at this time (new) | mailbox, or a reader with the mailbox's clock | a statement of coverage is held whose token is no older than the limit, with every notice it names | the held files, the token's time, the clock | **no**: nothing works it out or signs it (M1) |

**The provenance sentence**, which today is one fixed sentence and a current breach of P5 (D-b). Proposed: one of four,
chosen by what the notice was in fact made from. (1) From the witness's answer for this run, received after its
checkpoint at decision N. (2) From the witness's chain alone, to decision N. (3) From no answer: the witness last
answered the courier at decision N, and has not answered in this reading. (4) From nothing: the witness has never
answered the courier for this budget.

**Words kept apart, by the three guarantees.**

- Of authenticity, a notice may say "signed by a gate key the courier was given". It may not say verified, confirmed,
  genuine, or correct.
- Of consistency, a notice of a conflict may say: "The witness holds K reports for this run, signed by a gate key the
  courier was given, at decisions a and b. They name M different results. The courier does not know which result is the
  true one, or whether either is." It may not say that a verdict was changed, replaced or forged, or that the first is
  the true one.
- Of correctness, no notice says anything. A run's notice gives the outcome "as the report signed by the gate's key
  gives it".
- Of coverage, a statement says what was observed, to decision N. It says nothing of decisions after N, of the truth of
  any verdict, or of anyone having read the mailbox. NOT COVERED is never worded as, or beside, a statement about a
  verdict: "the mailbox holds no fresh proof that this budget was read whole" and no more.
- No signed sentence gives a time by the courier's clock as a fact about anything but the courier (section 8, F4), and
  none promises the future (D-d).

## 8. The eighth review's four unconfirmed findings, against the model

They remain reported and not re-confirmed by test. Each is placed, so that none is left out.

| Finding | What it says | In the model | Disposition |
|---|---|---|---|
| F1 (high) | a run after which the witness once stopped is never asked for again while new such runs keep arriving; its FAIL stands as UNREADABLE | the move "a reading of a run goes unanswered", made at every reading. The run is never observed, so no reading is whole, so the budget reads NOT COVERED for as long as it lasts | **Safety: answered by the proposed rule.** The FAIL is not noticed, and the mailbox does not read COVERED. **Timeliness: not answered**; it is UM1 and UM2, which stay unmet. Two sentences of the eighth form's text ("one of them in every pass") are false by this finding; they are wording to remove (requirement IR-8) |
| F2 (high) | runs that read once and then stop the witness delay every other run by a number of passes the service chooses, while the status states a bound that is false | the same move. The model has no bound in passes and no order of asking: what is asked first cannot matter to any invariant | **Safety: answered**, as F1. **Timeliness: not answered** (UM1). No bound in passes may be stated or signed unless it holds against the locked powers; none does (IR-8) |
| F4 (low) | after the courier's clock is set back, a notice gives a wrong time for when a run was last asked for, and contradicts itself | not in the model, by design: no invariant and no proposed assertion uses the courier's clock. Freshness is the mailbox's token | **Outside the coverage model. A wording fault of the kind P5 forbids.** The proposed rule of section 7 removes its class: no courier-clock time as a fact. To be confirmed by a test of a clock set back and forward (VT-19) |
| F5 (low) | form-2 notices made by earlier forms fail the eighth form's checker | not in the model: it is about formats over time | **A compatibility requirement** (IR-3): any new notice kind or wording keeps every earlier notice verifying, or the declaration says which do not. To be confirmed against a kept set of earlier notices (VT-20) |

## 9. Outstanding implementation requirements

None is begun. Each would need its own decision, and where it touches the gateway, its necessity named. They are listed
so that the review can see the whole of what the proposed guarantee would take.

- **IR-1, the courier's reading of a run.** Steps 1 to 5 of section 6: the count rule, the set D, the conflict as an
  added notice, the re-read rule. The outcome function is otherwise as it is.
- **IR-2, the record's checker.** The same steps on a record; the owner decides whether a record in conflict fails.
- **IR-3, notice kinds.** A notice of a conflict and a statement of coverage in `check_record`, each with its condition
  written down and checked when it is signed, and every outcome carrying every line of its text. Earlier notices keep
  verifying (F5).
- **IR-4, the mailbox.** A token with its time, signed; acceptance of the new kinds; the waiting limit, set by its
  operator; working out COVERED / NOT COVERED on its own clock and signing it; a guard on its clock going backwards.
  None of this exists (section 1).
- **IR-5, the size of a statement.** A statement of coverage must name every notice made so far within 64 KiB: a digest
  over the list, or the list in parts.
- **IR-6, one meaning of "whole".** The courier's account of a reading follows the definition and nothing else: a
  statement only from observations; no statement that promises the future (D-d); the alarm no longer started and
  cleared by kinds of ending (D-a, D-f).
- **IR-7, provenance and explanations.** The four provenance sentences; the lost explanations restored (D-b, D-c).
- **IR-8, wording.** No time by the courier's clock as a fact; no bound in passes; nothing that says or implies a
  verdict where the budget is NOT COVERED.
- **IR-9, preconditions.** B-1 to B-3 resolved before any claim that a deployment complies. Tracked outside this task.
- **IR-10, the method.** The tests of section 10 written by someone other than the implementer, from this note and the
  baseline, before the code; a planted-defect pass whose list the implementer does not write; a defect that makes a
  test hang counted apart from one caught.

## 10. Proposed validation tests, to be authored independently of the implementer

**Who writes them.** Someone who has this note, the baseline and the model, and does not have, and does not read first,
the implementation. They write the tests before the code exists, against the readings and files a deployment already
has. The stand-in for the witness, if one is used, is theirs and not the implementer's. Each test names the invariant or
the sentence it protects and is shown able to fail.

**Where they run.** Each against a real deployment on a fresh database, with the roles' grants read from the catalogue
first. Tests that need the preconditions (VT-25) are blocked until B-1 and B-2 are resolved, and are listed so that the
gap is visible.

| Id | From | Set-up, in short | Must hold |
|---|---|---|---|
| VT-1 | S-1; model `no_detection` | gate host signs FAIL, result withheld, second report over a PASS, PASS stored | a notice of the conflict in the mailbox; any statement of coverage names it; the run's own notice as today |
| VT-2 | S-1 | as VT-1, a result marked 'unknown' stored first | the same |
| VT-3 | model `no_reread` | a run read as final; then a second report with another digest | the run is asked for again; the conflict noticed |
| VT-4 | visibility V4 | the gate host's own report sent twice | no notice of a conflict |
| VT-5 | visibility V5; UM6 a | only a forged report reaches the witness | no notice of a conflict; and no sentence anywhere that says the result is correct, verified or true |
| VT-6 | section 6 | an EFFECT report and a NO_EFFECT report for one run | a conflict is observed; wording as section 7 |
| VT-7 | model `asked_is_enough`; D-d | one run asked for and not answered | no statement of coverage; the budget reads NOT COVERED |
| VT-8 | model `no_count_rule`; visibility V7 | a recorded report removed with the owner's password | the reading is not whole; the run is reported as not observed; no statement of coverage |
| VT-9 | model `receipt_time` | a whole reading; its statement held back past the limit; a FAIL committed meanwhile; then delivered | NOT COVERED on delivery |
| VT-10 | model `no_lapse` | a statement delivered; no reading after it | NOT COVERED once the limit has passed on the mailbox's clock; also with that clock set back and forward |
| VT-11 | clause O4 | a statement delivered, one notice it names not delivered | NOT COVERED until the notice is held |
| VT-12 | model `names_new_only` | an earlier FAIL notice missing from the mailbox; a later whole reading | NOT COVERED |
| VT-13 | model `carry_over` | a run not final, answered in one reading and not in the next | no statement from the second reading |
| VT-14 | section 6, step 2 | a report recorded after the checkpoint; a value stored after it | the report left out; the run not final in that reading |
| VT-15 | R1; step 6a, 6b | the service's role takes every connection; the witness stopped by its account | NOT COVERED; no notice of any run that says or implies FAIL |
| VT-16 | decision of 21 November | every status line and notice made while NOT COVERED | none says or implies that a verdict is FAIL |
| VT-17 | F1 | the eighth review's `y7_buried` set-up | the budget never reads COVERED while the run is unread |
| VT-18 | F2 | the eighth review's `y3_m_poisoned` set-up | the same; no bound in passes shown or signed |
| VT-19 | F4 | the courier's clock set back, and forward | no signed sentence gives a wrong time; freshness unaffected |
| VT-20 | F5 | a kept set of notices made by each earlier form | each verifies, or is listed as not verifying |
| VT-21 | P5 | every kind of signed sentence | its written condition holds against a recorder that is not the courier |
| VT-22 | D-c | every outcome, every form | every line of its text is present and non-empty |
| VT-23 | section 6 | a record of a budget with a run in conflict | the checker's answer is the one the owner decides (fails, or marked) |
| VT-24 | the measured envelope | the honest load of 21 November, with the new rules | whole readings and their times as measured, within a stated margin |
| VT-25 | DP1, DP2 | a deployment with separate accounts and no owner credential with the service | all of the above again. **Blocked** until B-1 and B-2 are resolved |

Each trace in the model's results is a ready set-up for one of VT-1, VT-3, VT-7 to VT-13.

## 11. What is unsupported or open

- The proposed guarantee is a proposal. It is not built, and nothing in this note is evidence about code.
- The token, the mailbox's working out of COVERED, its signed status, its acceptance of the new notice kinds, and a
  guard on its clock do not exist (section 1). Every assertion that needs them is marked "no" in section 7.
- The correction to the baseline's definition (freshness from a token, not from the receipt) is put to the owner and is
  not made in the baseline.
- The model is small: two runs, three decisions, three ticks. It does not cover a courier or a mailbox that loses its
  state, or time within a reading. Its clean result for the proposed rules is exhaustive only at those bounds.
- The model's author also wrote the rules it checks. The variants show that its invariants can fail; they do not make
  it independent.
- F1, F2, F4 and F5 are placed against the model and are still not re-confirmed by test.
- The pair EFFECT with NO_EFFECT has no wording and no end-to-end test.
- Whether a record in conflict fails the record's check is not decided.
- B-1 to B-3 are unresolved, so no test here can run on a deployment that meets the contract.
- Verdict correctness is outside everything here.
