# Amendment 16, Step 2: a design-and-verification note. The COVERED / NOT COVERED model, and detecting more than one signed digest for a run

21 November 2026. Private working material. Internal work under the owner's direction. It is not an independent
validation, it is not a declaration, and it is not an implementation. Authorised by the owner on 21 November as a design
and verification exercise only. Nothing is implemented here: the check for more than one digest is not written, the
courier, the mailbox and the gateway are not changed, no credential or deployment configuration is edited.

The design baseline is `verify/AMEND16_THREAT_MODEL_ADDENDUM_2026-11-21.md` at `0da1a85e` on `verification-
amendment-16`, accepted by the owner as a threat-model design baseline and not as an implementation or a security
declaration. `e25a297`, the eighth form of the courier, is and stays INCOMPLETE, rejected at internal review and
undeclared. Citations are to the tree at `e25a297`; the mailbox's file is the same at `0da1a85e`.

**Second revision, 21 November 2026**, after the owner's review of the first (commit `2938fca`, which keeps the first
as it was). Still documentation and verification design only; no Step 3 is begun. What changed: the freshness of
COVERED is corrected by a dated erratum (section 12); two distinct signed verdict digests for one run are now a hard
failure of record verification (sections 6 and 13); the two scaling questions are answered (sections 14 and 15); the
exact minimum mailbox changes and the proposed Step 3 interfaces are set out (sections 16 and 17); the model's limits
and the unresolved assumptions and proof obligations are stated (sections 18 and 19). Sections 1 to 4 and 8 are as
they were. The model was not changed or run again.

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

**A counterexample against the baseline's own wording.** The addendum's section 7 defines COVERED by a statement
"which M receipted at a time r with t − r no more than the waiting limit". The variant `receipt_time` is that wording,
and it breaks NOTICED: a statement made from a reading at t=0 can wait in the outbox and be receipted at t=2; the
budget then reads COVERED at t=2 on an observation two ticks old, and a FAIL committed after that reading and long
before t − L has no notice. The receipt shows when the statement arrived, not when the budget was observed (M14).
**The correction, adopted by the owner on 21 November:** COVERED is judged by the age of a challenge token the mailbox
issued before the reading began and the witness signed back in the checkpoint, never by the receipt's time. It is set
out in the dated erratum `verify/AMEND16_ERRATUM_FRESHNESS_2026-11-21.md` and in section 12. It needs something from
the mailbox that it does not give today (MA5) and no change to the gateway. The baseline at `0da1a85e` is not edited.

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

**Step 3, the digests.** The *verdict scope* of a report is the budget, the run and the nonce it signs. Within one
scope, let D be the set of distinct pairs (verdict claimed, result digest) among the authentic reports that claim a
verdict, EFFECT or NO_EFFECT. A report that claims UNKNOWN is left out: an unknown outcome followed by a
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
(check_record.py 858-859). The same steps 1 to 3 apply to a record. By the owner's decision of 21 November a record
that holds a conflict **fails** verification, with both reports kept in it as evidence (section 13); at `e25a297` such
a record verifies.

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
| VT-23 | sections 6, 13 | a record of a budget with a run in conflict | the record's verification fails, naming the run, both decisions and both digests; both reports are in the record |
| VT-24 | the measured envelope | the honest load of 21 November, with the new rules | whole readings and their times as measured, within a stated margin |
| VT-25 | DP1, DP2 | a deployment with separate accounts and no owner credential with the service | all of the above again. **Blocked** until B-1 and B-2 are resolved |

Each trace in the model's results is a ready set-up for one of VT-1, VT-3, VT-7 to VT-13.

## 11. What is unsupported or open (the first revision's list; section 19 is the fuller one)

- The proposed guarantee is a proposal. It is not built, and nothing in this note is evidence about code.
- The token, the mailbox's working out of COVERED, its signed status, its acceptance of the new notice kinds, and a
  guard on its clock do not exist (section 1). Every assertion that needs them is marked "no" in section 7.
- The correction to the baseline's definition (freshness from a token, not from the receipt) is adopted by a dated
  erratum and is not made in the baseline. It is not built and not proved (section 19).
- The model is small: two runs, three decisions, three ticks. It does not cover a courier or a mailbox that loses its
  state, or time within a reading. Its clean result for the proposed rules is exhaustive only at those bounds.
- The model's author also wrote the rules it checks. The variants show that its invariants can fail; they do not make
  it independent.
- F1, F2, F4 and F5 are placed against the model and are still not re-confirmed by test.
- The pair EFFECT with NO_EFFECT has no wording and no end-to-end test.
- A record in conflict is to fail the record's check (section 13). Nothing does that today.
- B-1 to B-3 are unresolved, so no test here can run on a deployment that meets the contract.
- Verdict correctness is outside everything here.

## 12. Second revision: the freshness of COVERED

The dated erratum `verify/AMEND16_ERRATUM_FRESHNESS_2026-11-21.md` corrects section 7 of the baseline without editing
it. In short: the mailbox issues an unpredictable challenge before the reading; the witness signs its token back in
the checkpoint; the courier signs the challenge, the checkpoint and its commitments together; the token is used once;
its age is counted from its issue by the mailbox's trusted time, against a deadline the operator sets; a restart makes
every budget NOT COVERED; a statement that arrives late is kept and never counts. A fresh receipt cannot make an old
observation look fresh, because nothing is counted from a receipt.

In the model the token is the mailbox's clock at the start of a reading and the rule is `t − token ≤ L` (variant
`spec`). The model has no epochs, no restart, no replay, no second mailbox and no clock anomaly. Those parts of the
erratum are specified and are checked nowhere.

## 13. Second revision: two distinct signed verdict digests are a hard failure of record verification

- **The rule.** Within one verdict scope (budget, run, nonce: the things a gate report signs beside its claim and
  digest, check_record.py 157-158), if the authentic reports that claim a verdict name more than one distinct
  (verdict, digest), the record's verification **fails**. It is not a warning and not a mark.
- **Both reports are kept as evidence.** In the record, which already carries every report of a run with its decision
  number. In the witness's reading, where both stay (no granted role can remove one, by test). And in the courier's
  notice of the conflict, which carries both reports whole (983 bytes for two, calculated).
- **A repeat is not a conflict.** The same (verdict, digest) recorded any number of times is one signed result (by
  test: the gate host's own report sent twice).
- **Two verdicts are a conflict.** An EFFECT report and a NO_EFFECT report in one scope fail the record, whatever
  their digests.
- **A report that claims UNKNOWN is not a verdict.** "Unknown now, a verdict later" is an existing course of an
  interrupted run and is not a conflict. It is the one existing path in which a later report changes what is known of
  a run, so its exclusion is stated here for the owner to confirm.
- **A verdict report anywhere but at a reconcile decision.** By reading, the store keeps a report with a RELEASE
  decision as well as with a RECONCILE (`plea_gateway/store.py` 771-779), and the courier's reading of a run does not
  look at which decision a report sits at; the record's checker does (check_record.py 858-859). Under the count rule a
  verdict report at any decision that is not a RECONCILE for that run makes the run not observed. Not tested.
- **What the courier does.** The run's outcome as today, and one notice of the conflict. The conflict is an
  observation: a reading can still be whole, and its statement of coverage commits to the notice. COVERED then means
  the conflict is in the mailbox, not that the record is sound.
- **Detecting equivocation is not proving correctness.** A failed record says that the gate's key signed two results
  for one run. It does not say which is right, that the run failed, or who signed. A forgery made before the witness
  sees anything still passes (UM6 a): one report, nothing to compare.
- **No supersession.** No protocol exists by which one verdict lawfully replaces another, and none is assumed. If one
  is ever wanted it needs its own property, its own validation and its own declaration. Until then every such pair
  fails. The witness's name for the second report, VERDICT_RETRY, describes the honest case, an identical repeat, and
  nothing more.

## 14. Second revision, scaling question one: a conflict that arises after a run is final

**The question.** A run is read and taken as final; later a second report with another digest is recorded for it. How
is that seen without reading every old run again at every reading, and without reading the chain again from its start?

**The mechanism: follow the chain from a cursor, and read only the runs it names.**

1. The courier keeps a cursor: the last decision it verified and that decision's head. This is what `e25a297` keeps
   already.
2. At each reading it takes a checkpoint that names the cursor's decision and signs that decision's head back, and
   reads the decisions after the cursor, page by page, recomputing each hash from the one before to the checkpoint's
   head (courier.py, `checkpoint()` and `chain()` 379-397).
3. From those decisions alone it takes the set of runs for which a RECONCILE or RELEASE decision appears. Every
   decision carries its operation and the run it names, and the operation is under the hash (check_record.py 145-146).
4. It asks for exactly those runs, and for the runs that are not final. A final run with no new decision is not asked
   for.
5. For each run asked for, the count rule and the digest rule of section 6.

**Why it cannot silently miss a conflict.** Each link, with what it rests on:

| Link | Rests on | How known |
|---|---|---|
| A report enters the witness's store only with a decision of the chain, a RELEASE or a RECONCILE, for the run it names, at that decision's number | `plea_gateway/store.py` 771-788: the store's function inserts a report only so, and only for the witness's role | code reading; and by test, every direct insert, change and removal of a report was refused for all three granted roles |
| A second report for a final run is recorded as a decision (DUPLICATE or DENIED), not dropped | the witness's acceptance writes the decision whatever its kind | by test: recorded as DUPLICATE and as DENIED, each with its report (`commit_check.py` steps 2 and 2b), and read back through GET /chain (`visibility_check.py` V2) |
| The courier sees every decision after its cursor, once | each decision's hash covers the one before; the checkpoint's head is signed by the witness; the cursor's own head is signed back | code reading of `e25a297`; exercised by the existing tests R25, R26, R30 in development runs |
| A chain that was cut back or forked is refused, not followed | `checkpoint()` refuses a cursor beyond the chain (ROLLBACK); a different head for the cursor's decision is a FORK (courier.py 641-643) | code reading; existing tests in development runs |
| A report present in the chain and absent from the answer is noticed | the count rule (section 6, step 2) | specified, not built; the absence was shown by test with the owner's password |
| Two different digests in one answer are noticed | the digest rule (section 6, step 3) | specified, not built; the data shown by test |

So a conflict can be missed only if the witness signs a chain that leaves a decision out (the baseline's stated limit:
one consistent false chain is not caught), or the owner of the database rewrites the chain (out of scope; precondition
DP1), or the courier's cursor is itself lost or wrong. A courier that loses its cursor starts from the beginning and
reads everything once.

**Does it work strictly over the existing, frozen read interface?** For finding every conflict, and for not reading
old runs again: **yes**. It uses GET /checkpoint, GET /chain with `after`, and GET /run, as they are. For the size of
the chain: **no, and it cannot**. Every decision the witness gives carries the state of every run of its budget, and
the decision's hash is over that state, so a decision cannot be verified without it. Following the chain therefore
costs, for each new decision, a transfer that grows with the budget (127 KB a decision at 996 runs, measured), and
over a budget's life the total grows with the square of its runs whether it is read at once or a little at a time (508
MB at 996 runs, measured). **Avoiding that needs a change to the witness and the store**: a reading in which a
decision carries a digest of the state in place of the state, with the hash defined over that digest. That touches the
frozen gateway. It is not proposed here and is not assumed. S-4 stays open.

**Cost with the interface as it is.** Nothing beyond what a reading already does, plus one GET /run (0.04 to 0.06 s,
measured) for each run that has a new RECONCILE or RELEASE decision. In honest operation those are the runs that have
just finished.

**In the model** this is the re-read rule. Without it the variant `no_reread` breaks the consistency invariant in 14
steps.

## 15. Second revision, scaling question two: does the evidence for 1,000 runs fit in 64 KiB?

**No.** Calculated from the shapes the notices have today (a digest is 64 characters; sizes are of compact JSON):

| What a statement of coverage would have to carry | Size | Fits in 65,536 bytes? |
|---|---|---|
| the digests of 1,000 notices, as a plain list | 67,001 bytes (67 each) | no, not even alone; at most about 930 beside the rest of the statement |
| one observation record for each of 1,000 runs (run, decision observed at, outcome, digest) | 135,001 bytes (135 each) | no |
| the challenge and the checkpoint, carried whole | 568 and 601 bytes | yes |
| a statement with the challenge, the checkpoint, two commitments and 1,200 characters of words | 3,156 bytes | yes |

A budget with a quarter of its runs failing fitted a plain list on 21 November (247 notices). A budget where every run
fails, or where runs also carry notices of conflict or of not being read, does not.

**The bounded commitment proposed.** One chain of items for each budget and each life of a courier's state:

- **Items.** Everything the courier sends for a budget is an item: a notice of a run, a notice of a conflict, and the
  observation records of a reading, sent as one or more parts of at most 64 KiB (478 records fit in a part; a reading
  from nothing over 1,000 runs is 3 parts; a reading in steady state is one small part).
- **The chain.** Item k carries its number k, the chain's identifier, and A(k) = H(A(k−1), digest of item k), where
  A(0) is fixed by the budget, the courier's key and the chain's identifier. The courier signs these with the item.
- **The statement.** It carries the chain's identifier, the number k of the last item before it, and A(k): 64
  characters, whatever the budget's size. It also carries the count of runs, how many were observed in this reading
  and how many were final already.
- **Omissions are detected.** The mailbox holds what the statement commits to if and only if it holds items 1 to k of
  that chain and recomputes A(k). A missing, altered or reordered item breaks the chain at its number. Then the budget
  is NOT COVERED (erratum, F6).
- **Anyone can reconstruct it.** A reader who has the items recomputes A(k) and checks each item's signature, with no
  help from the courier or the mailbox. The observation record of a run that was final already is in the part of the
  earlier reading that observed it, which is in the same chain.
- **A courier that has lost its state** cannot continue a chain it does not remember. It begins a new chain with a new
  identifier and sends everything again from a reading from nothing. A statement counts only for its own chain.

This needs a new form of notice that carries the three chain fields, which `check_record` and the mailbox do not know
today (M3). Notices of the earlier forms must keep verifying (F5). The hash chain is specified here and has been
checked nowhere: not in the model, which names notices as a set, and not in any code.

## 16. Second revision: the exact minimum changes to the mailbox for a Step 3 (none is made)

Each is set against what the mailbox does today (section 1). The list is the least that the corrected definition
needs; nothing in it is a convenience.

| Id | Change | Why it is needed | Today |
|---|---|---|---|
| MB-1 | Issue a challenge: for a budget and a courier key, a 32-byte random token, with the epoch, a serial number, the waiting limit and the moment of issue, recorded durably and then returned signed | erratum F1, F5; without it freshness can only be counted from a receipt | no such request (M1) |
| MB-2 | Take the new kinds: the item form with chain fields, a notice of a conflict, observation parts, a statement of coverage; refuse what it does not know | sections 13, 15; erratum F3 | refused as unreadable (M3) |
| MB-3 | Check a statement when it arrives: the challenge is its own, of the current epoch, for this budget and key, unused; the checkpoint is signed by a witness key given, for this budget, and signs the token back; the courier's signature covers both | erratum F1 to F4. This needs the witness's public keys at the mailbox, which it does not hold today | checks a courier's signature only (M2) |
| MB-4 | Trusted time: an epoch made at each start; elapsed time by a clock that cannot be set and counts suspension; the wall clock compared with it; a recorded anomaly when they disagree or the wall clock goes back; the larger age used | erratum T1 to T6 | the wall clock, once, unguarded (M4) |
| MB-5 | Replay protection: a token counts once; a later statement on it is kept and not counted; tokens of earlier epochs, other budgets and other keys do not count | erratum F4 and the replay table | nothing to replay against; a notice delivered again returns its first receipt (M7) |
| MB-6 | Fail closed: after a restart, or when its own record cannot be read, every budget it cannot answer for is NOT COVERED | erratum, restart | no state to lose, and no state to answer from (M1) |
| MB-7 | Durable evidence: challenges, statements, items and late or refused statements written whole and synced before any answer, as notices are today; held items indexed by chain so that A(k) can be recomputed | erratum F6; section 15 | notices only, one file each (M6); a damaged copy is rewritten with a new time (M7) |
| MB-8 | Payload limits: 64 KiB for each item stays; a statement is about 3 KB; observation records go in parts | section 15 | 64 KiB (M3) |
| MB-9 | The deadline: set by the operator at start, carried in each challenge, changed only with a new epoch | erratum, the deadline | none (M1) |
| MB-10 | A signed status: for a budget, COVERED to N or NOT COVERED, with the epoch and any clock anomaly | only the mailbox knows its trusted time; without this a reader uses their own clock | none; a listing is unsigned (M10) |

Not in the minimum, and named so that their absence is a choice: protection of the mailbox's folder against its own
account (M9; the baseline's A2 and DP2 must give it), a bound on connections, and any reading of the witness by the
mailbox other than checking a checkpoint's signature.

## 17. Second revision: proposed Step 3 interfaces (for approval; nothing is built)

**The witness: no change.** The three readings as they are. The courier's checkpoint request carries the mailbox's
token as its nonce and its cursor as `at`: `GET /checkpoint?root=B&nonce=TOKEN&at=K`, then `GET
/chain?root=B&after=K&limit=200`, then `GET /run?root=B&aid=A` for the runs of section 14. No request is added, and
the gateway is not touched.

**The mailbox.**

| Request | Gives | Signed by |
|---|---|---|
| `POST /challenge` {budget}, from an admitted courier | {CHALLENGE, mailbox, epoch, serial, budget, courier key, token, limit, issued} | the mailbox |
| `POST /deliver` an item (as today, with the new kinds) | a receipt, meaning stored and no more | the mailbox |
| `GET /status?root=B` | {STATUS, mailbox, epoch, budget, COVERED to N or NOT COVERED, chain, clock anomaly, wall-clock time} | the mailbox |
| `GET /pubkey` | as today | — |

**What the courier signs.**

| Item | Fields beyond today's notice | True exactly when |
|---|---|---|
| every item (a new form) | chain identifier; number k; A(k) | A(k) = H(A(k−1), digest of this item) for this chain |
| notice of a run's outcome | the decision at which the run's answer was received; which of the four provenance sentences applies | as section 7 |
| notice of a conflict | the scope; both reports whole; the decisions they sit at | section 13's rule holds of the answer received |
| observation part | for each run observed in this reading: run, decision observed at, outcome, digests; part i of n | each record is what the courier received and verified in this reading |
| statement of coverage | the challenge and the checkpoint whole; chain identifier, k, A(k); runs, observed now, final already | erratum F1 to F6 and the baseline's O1 to O4 |

**What the courier keeps.** The cursor (decision and head); for each final run, the decisions of its reports that it
has seen; the chain's identifier, k and A(k); the challenge in hand.

**The record's checker.** One added failing condition in its sixth check: more than one distinct (verdict, digest)
among the authentic verdict reports of one scope. Nothing else in a record changes: it already carries the reports.

## 18. Second revision: what the model is, and what it is not

- **What was searched.** The proposed rules, variant `spec`: 4,137,699 states, searched to the end, no invariant
  broken. Bounds: two runs (one may carry two reports of either digest, the other one honest report), three decisions,
  the mailbox's clock at 0, 1 and 2, a waiting limit of one tick.
- **Nine weakened variants.** Each removes or weakens one rule, and each breaks at least one invariant:
  `no_detection`, `no_reread`, `asked_is_enough`, `no_lapse`, `receipt_time`, `carry_over`, `names_new_only`,
  `no_count_rule`, `owner`. Their shortest traces are in the results.
- **Searches that were cut off.** Three variants were stopped at 14,000,001 states: `carry_over`, `no_count_rule` and
  `owner`. What they broke is real. Nothing may be said of what they did not break; in particular, that `owner` showed
  no breach of the consistency invariant is not a finding.
- **A first run that was killed.** A run of all variants in one process was killed for want of memory after six; its
  output is kept. The six agree with the later run.
- **Bounded evidence is not proof.** "No invariant broken" is true of every state of two runs, three decisions and
  three ticks under these rules. It says nothing of three runs, of longer histories, or of anything the model leaves
  out. A fault that needs more than the bounds would not be found.
- **What it leaves out.** A courier that loses its state; a mailbox that restarts or loses what it holds; epochs,
  replay, a clock anomaly, a second mailbox; the hash chain of items; time within a reading; more than one budget;
  honest PASS runs; the order of asking. Every one of these is in the design and none is in the model.
- **One author.** The rules, the invariants, the variants and the model were written by the same author. That the
  invariants can fail is shown by the variants. That they are the right invariants, and that the model says what the
  rules say, is not shown by anything independent. **This is not independent validation.**
- **It is not the code.** A clean model says nothing about a courier or a mailbox that does not exist, and nothing in
  this note claims that the mailbox as it is satisfies any invariant here. It does not: it has no challenge, no
  deadline, no trusted time and no status.
- **The 25 validation tests** of section 10 stand as they were, for an author who has not seen an implementation. Six
  more follow from this revision, for the same author: VT-26, a token used twice, of an earlier epoch, of another
  budget, and a statement offered to another mailbox; VT-27, the mailbox restarted, and its record made unreadable;
  VT-28, the mailbox's wall clock set back and forward, and the machine suspended; VT-29, an item left out, changed or
  reordered in the chain of section 15, and a budget of 1,000 failing runs; VT-30, a verdict report recorded with a
  RELEASE decision, and an UNKNOWN followed by a verdict; VT-31, the courier's cursor against a chain cut back and a
  chain forked, with a conflict recorded for a final run meanwhile.

## 19. Second revision: unresolved assumptions and proof obligations

Nothing below is settled. Each is something a Step 3 would have to show, or something the owner would have to accept
as a limit.

**Safety.**

- PO-1. The token rule beyond the model's bounds, and every part of the erratum the model does not hold: single use,
  epochs, restart, replay, the larger-age rule. Specified; checked nowhere.
- PO-2. That a result stored as a value stays, and that a recorded report is not removed, in a deployment that meets
  DP1 and DP3. Shown for the granted roles on the demonstration; the demonstration does not meet DP1.
- PO-3. The second half of O3: a final run's earlier observation still stands. It rests on PO-2 and on the re-read
  rule.
- PO-4. The mailbox's own folder: that what it holds is not removed or changed by its account (M9). Nothing guards it.
- PO-5. The mailbox's trusted time: that a clock exists on the mailbox's host that cannot be set and counts
  suspension, and that the operator's tolerance is sound. Not examined on any host.
- PO-6. That the witness's checkpoint binds the token as assumed, with a token from a mailbox. Read, not tested.

**Consistency.**

- PO-7. That no path records a verdict report except a RECONCILE decision, and that a report at a RELEASE decision is
  caught by the count rule. From reading; not tested.
- PO-8. The count rule against every kind of decision the witness records (applied, duplicate, denied, no-op) and
  against a report whose derived label is not AUTHORISED. Specified for the cases seen; the others are not enumerated
  by test.
- PO-9. The exclusion of UNKNOWN from the conflict rule: that "unknown now, a verdict later" cannot be used to replace
  a verdict. Not examined.
- PO-10. The hash chain of items: that it detects every omission and that a new chain after a loss of state cannot be
  used to drop an item unseen. Specified; not modelled.
- PO-11. A forgery before the witness sees anything is not detected by anything here (UM6 a). This is a limit, not an
  obligation that can be met in this path.

**Liveness.**

- PO-12. None is promised. The service can keep a budget NOT COVERED for as long as it likes (R1, R2; F1, F2).
- PO-13. That a deadline exists which honest operation meets: the reading and its delivery inside L, including a
  reading from nothing after a loss of state, whose chain transfer grows with the square of the budget (S-4). Measured
  only at up to 996 runs on one machine.
- PO-14. A mailbox restart makes every budget NOT COVERED until each courier reads again. How long that lasts in
  operation is not measured.
- PO-15. Runs that never reach a final phase are asked for at every reading for ever (D-h). Their rate in operation is
  not known.

**Deployment.**

- PO-16. B-1 (database credentials in the repository), B-2 (one operating-system account), B-3 (custody of the gate's
  key) are unresolved. No test can run on a deployment that meets the contract until B-1 and B-2 are.
- PO-17. The mailbox must hold the witness's public keys (MB-3) and be run by someone other than the service (A2).
  Neither is so in the demonstration.
- PO-18. S-3 (connection exhaustion) and S-4 (quadratic growth) are open operational risks, carried and not prevented.
- PO-19. F1, F2, F4 and F5 of the eighth review are placed against the model and are still not re-confirmed by test.
