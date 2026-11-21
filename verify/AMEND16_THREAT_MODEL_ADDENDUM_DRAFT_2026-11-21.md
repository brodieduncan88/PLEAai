# Amendment 16: threat-model addendum (DRAFT for the owner's review)

21 November 2026. Private working material. Internal work under the owner's direction. It is not an independent
validation. It is a draft and is not approved. It is not a declaration. No code is changed by it. It does not change
`verify/AMEND16_PROPERTY_2026-11-20.md`: P1 to P7 and T1 to T8 stand as written there, and where this addendum says a
part cannot be met, that part stays a requirement, unmet. Release gates G2, G5 and G6 stay implemented and internally
tested, with open obligations. One machine, one kernel, a database shared by the witness and the service, and no real
separation of the parties remain material.

Citations are to the tree at `e25a297` unless another commit or branch is named. "Code reading" means the cited lines were
read for this draft; nothing was run for it except reading files and counting entries in one result file (section 6).

How it was made: a separate drafting session wrote it from a brief of facts the coordinator had checked. The
coordinator then re-read every cited line, corrected the draft where it differed, and wrote the part of section 3 on
when a verdict is committed. It is one internal reading of the code and the documents. Nothing in it was tested for
it.

## 1. Why this addendum

Eight forms of the courier were built on `verification-amendment-16`. Each failed an internal review. The eighth
(`e25a297`) is not declared. The diagnostic of 21 November (`verify/DIAGNOSTIC_AMEND16_ALARM_2026-11-21.md` on branch
`diagnostic-amend16-alarm-2026-11-21`) found the alarm missing in 4500 s when the witness lets one whole pass through
slowly in every nine (T2), and a false provenance sentence (T1f).

The property file says what the service may choose (lines 21-24): run names, every field of a result, a result's size,
and which budgets exist. It gives the service no stated power over time: when the witness answers, how fast runs are
added, whether a run ever finishes. Yet lines 26-27 keep the shared database, one machine and one kernel. Much of what
the reviews found used a power over time that the file had not named; the rest were faults of the courier's own. This
addendum names those powers, says what notification can still
promise against them, and keeps what it cannot promise as named, unmet requirements. A later review finding that
falls outside section 2 is then a request to change the model, not a defect of the code.

## 2. The parties, and the service's powers

"Granted" says whether the property file already gives the power. "Lets it do" is what the power does to notification.
"Still promised" is what notification can say against it, if the defects of section 6 are repaired; at `e25a297` some
of these are not met.

| Power | Where it comes from | Granted | Lets it do | Still promised |
|---|---|---|---|---|
| Run names and every field of a result | property 21-24 | yes | put text of its choosing in a notice | shown as data only (P5) |
| Result size | property 22-23; courier reads to 32 MiB (courier.py 178) | yes | make one GET /run slow or unreadable | that run unread and visible (P2); no other run hidden by it |
| Which budgets exist | property 23 | yes | create a budget the courier is not configured for | never reported as covered (P6) |
| The gate's key | property 21 | yes | sign a report whose result says PASS for a run that failed | nothing about the truth of a verdict (section 3) |
| When each witness answer arrives (per request) | assumed from the shared database, property 26-27 and courier.py 147-148; not demonstrated | no | stall the chosen request up to the 60 s deadline (courier.py 212), or drop it | that a budget not read whole is never said to be read (safety); nothing about when a run's notice arrives |
| The rate at which runs are added | front door and gate, property 21; rate not stated | no | add runs faster than a pass can ask for them | shown, not repaired (courier.py 103-104) |
| Runs that never finish | follows from holding the gate; not stated | no | leave runs CONSUMED or UNVERIFIED for ever; each costs one GET /run at every pass (courier.py 403, 804) | each listed; NO_OUTCOME or UNVERIFIED notice after the waiting time if read |
| Rewriting the chain | property 27 | out of scope | not answered | nothing |
| Holding the witness's, courier's or mailbox's key | property 18-19 (these are trusted) | out of scope | not answered | nothing |

Three facts about the code bear on the table:

- The chain binds seq, op, kind, code and observation (`verify/check_record.py` 145-146). The verdict is not in it.
  It comes from the stored result, believed if the result hashes to the `result_digest` of any gate-signed EFFECT
  report for that budget, run and nonce (check_record.py 181-203, the `digests` list). Otherwise the run is UNVERIFIED.
- GET /run is unsigned (`plea_gateway/witness_service.py` 25-28). The witness offers three readings only,
  /checkpoint, /chain with `after=K`, and /run for one run (witness_service.py 14-28, 60). There is no bulk reading of
  runs and no list of budgets. `result_digest` does not occur in `plea_gateway/store.py`.
- The witness reads the same database as the service; the chain is written only through the witness's role; a stored
  result is the service's (courier.py 146-149). Whoever runs the witness can cut the courier off (courier.py 149-151).

Assumptions about the other parties, each named:

- **A1. The courier.** Honest; its key secret; its configuration its own (property 18). It may be killed and restarted.
  While it is not running, or its own state is malformed, or it cannot send, it tells the mailbox nothing
  (courier.py 111-112; budget skipped at 1264-1268).
- **A2. The mailbox.** Honest; its key its own (property 19); it stores what it receipts. Its clock is assumed to be
  its own. Not examined for this draft.
- **A3. The channel.** Courier to mailbox delivers when both are up. On one machine this is assumed, not shown.
- **A4. The clocks.** The courier's clock is its own. It is read once per pass, before the loop over budgets
  (courier.py 1258-1259); budgets are read one after another (courier.py 107). A statement judged at the mailbox
  would be judged by the mailbox's clock (A2).
- **A5. The reader.** The mailbox is passive storage. Someone or something must read it for any notice, or any
  absence of one, to reach a person. Nothing in this path shows that a person read anything (property 34-35).

## 3. What notification covers: committed verdicts only

**The answer to the owner's question is yes: notification covers committed verdicts only.** A service holding the
gate's key can sign an EFFECT report for a result that says PASS for a run that failed. The courier has no card, and
P7 compares only a result's own numbers with its own stated limits (property 80-82). Nothing in the notification path
can detect such a report. So notification can say that a verdict the service committed to reached the mailbox, or did
not. It can say nothing about whether a verdict is true.

A stored result that does not hash to a signed digest gives UNVERIFIED (check_record.py 200-202), which is a notice
after the waiting time if the run is read (courier.py 182, 818-823), not silence.

**When a verdict is committed.** From code reading only. Nothing here was tested.

- The witness records the gate's report with the RECONCILE decision (`plea_gateway/witness.py` 79-87). Its derivation
  of the verdict checks the signer, the budget, the run and the nonce, and does not look at the digest
  (`plea_gateway/evidence.py` 114-120).
- A second RECONCILE with the same verdict, for a run already in a final phase, is recorded as DUPLICATE /
  VERDICT_RETRY (`plea_gateway/plea_budget_ref.py` 725-727; store.py 400-401). Its report is stored with it: the
  evidence row is built whenever evidence is given (store.py 1070) and inserted whatever the decision's kind (store.py
  773-788). `run_outcome` then accepts a result that hashes to either digest (check_record.py 188-203). So a run can
  carry two gate-signed digests, and neither the courier nor the record's checker remarks on it.
- A stored result is written only through `plea_put_result`, which is granted to the service's role alone (store.py
  866). It replaces a stored result only where the stored one is marked 'unknown' (store.py 837-838). A result stored
  as a value is not replaced by it.

On this reading a verdict is committed once a gate-signed report is recorded and a result that hashes to it is stored
as a value. From then the service's database role, as the store grants it, cannot put another result in its place, and
a result that no longer hashes to a signed digest reads as UNVERIFIED. Before then the service still chooses: it can
have a second digest recorded, store the result it prefers, or store one marked 'unknown' and replace it later. With
the gate's key that adds nothing to what it could sign in the first place. It does mean that delay before a result is
stored is not only delay, and that a run carrying two signed digests passes without remark.

Two limits of this reading. It rests on the service holding only the role the store grants it; the property file says
"a database role" (line 21) and does not say which. And it has not been tested: no run was made with a second report,
and none with a result marked 'unknown' and then replaced.

## 4. P1 to P7: what can be met, and what stays unmet

Each guarantee below is marked **safety** (something false is never said) or **timeliness** (something is said within a
time). The unmet parts are named UM1 to UM6. (U1 to U9 are already the names of tests in
`verify/AMEND16_ADDENDUM_2026-11-20.md`.)

**P1. No run hides another.**
- Can be met. Safety: a run the courier cannot read, or did not ask for, never ends the reading of other runs as
  done, and never lets the budget read as covered (not so at `e25a297` for runs asked for and not read: D-d).
  Timeliness, conditional: where every GET /run is answered inside the time a pass has, every run that may call for a
  notice is examined in that pass.
- **UM1, every run examined in every pass the witness answers.** Against the powers of section 2 the service can make
  this false by slowing answers or adding runs (section 5). Needed: a witness whose answer time the service does not
  control (a database of its own, so separation of the parties); a bound on the rate of runs; a reading whose cost does
  not grow with the runs in flight. The last two touch the frozen gateway.

**P2. A run that cannot be read stays unresolved and visible.**
- Can be met. Safety: such a run is never marked done (courier.py 804: done only in EFFECT or NO_EFFECT and not
  UNVERIFIED) and is in the status with since when and why. Its UNREADABLE notice says the outcome is not known.
- **UM2, the notice within the waiting time, whatever the witness does.** The courier makes the UNREADABLE notice
  only at a later pass whose checkpoint and chain were read (courier.py 121-123), and the blocked alarm was missing in
  T2 (section 6, D-a). Needed: an alarm derived from the last positive proof of reading, evaluated at a bounded interval
  that does not wait on any witness answer. This holds only while the courier runs (see UM5).

**P3. The witness down told apart from one run unreadable.**
- Can be met. Safety: the courier reports which requests were answered and which were not.
- **UM3, the cause.** The service can answer the probe and withhold the run, or the reverse. Needed: a witness whose
  answers the service does not time (as UM1).

**P4. Names refused at the door.** Can be met in full; it does not depend on time. The rule is
witness_service.py 64-69, used at 135 and 164. Internally tested only.

**P5. The courier's words are the courier's.** Can be met in full; safety; independent of time. As written it concerns
text the service chooses. Not met at `e25a297` if F5 (section 6) is confirmed, since earlier records must still verify.
D-b and D-c are faults in the courier's own sentences: they bear on what may be claimed (section 7) more than on P5's
letter.

**P6. Coverage confirmed, not assumed.** Can be met as written; safety. As written, "watched" holds from a receipted
statement and never lapses.
- **UM4, budgets the courier is not told of.** The courier cannot discover budgets (property 77-78). Needed: a
  reading at the witness that lists them, which touches the gateway.
- **UM5, a courier that is absent is seen.** A courier not running, with malformed own state, or unable to send tells
  the mailbox nothing (A1). Needed: a receiver-side rule that reads the absence of a fresh positive statement as NOT
  COVERED. The candidate form is below; it still needs A5.

**P7. A signed verdict looked at.** Can be met in its "may only add a notice" form; safety. It is asked only of a run
that was read (courier.py 805-817), so its timeliness is P1's.
- **UM6, a committed verdict stays committed, and this is shown.** By the reading of section 3 it holds once a result
  is stored as a value. That has not been tested, and a run that carries two gate-signed digests is accepted without
  remark. Needed: a test of the reading. To make it hold by construction: the courier and the checker remarking on two
  digests for one run (which may only add a notice), or the witness refusing a second report for a run in a final
  phase, or the verdict bound in the chain at reconcile. The last two touch the frozen gateway.

**The three states** (property 29-38) stay distinct: the courier blocked or unable to read; the mailbox accepted (a
receipt, and all it means); the engineer acknowledged (nothing in this path shows it). They can be kept apart in words,
safety only. Added here, from the design review: a fourth observation, the courier running and delivering notices but
not reading the budget whole (as in T2), must not read as any of the three.

**The candidate form of the achievable guarantee.** For the owner to accept or not; not adopted, not built:
COVERED to decision N when the mailbox holds a courier-signed statement, receipted within the last L seconds by the
mailbox's clock, that the courier read the budget whole to N, and holds every notice that reading called for;
otherwise NOT COVERED. It is a safety statement with no promise of timeliness. It would meet UM5 at the receiver and
the safety parts above. It meets none of UM1 to UM4 or UM6. "Whole" would have to be defined once (section 6, D-f).

**T1 to T8.** Can still be shown: T3, T4, T5, T6, T7 (as wording) and T8. T1 can be shown against a witness whose
answers fit in the pass; against the powers of section 2 it presupposes UM1. T2's first half (in the status, never
done) can be shown; its second half (the notice after the waiting time) presupposes UM2 and a running courier (UM5).

## 5. Is COVERED operationally achievable under ordinary load without modifying the frozen gateway?

**Verdict: UNPROVEN under honest ordinary load (conditionally reachable; nothing measured). FAIL against a service
using the powers of section 2: it can keep a budget NOT COVERED at will, which is safe and operationally weak.**

How a pass spends time, from the code:

- Only runs in EFFECT or CONSUMED that are not done need a request, one GET /run each (courier.py 403-405). The
  checkpoint and the chain pages (200 decisions a page, courier.py 179) are read first (641-650).
- A budget's pass has `pass_seconds`, 600 unless set, for asking (658). Time is measured by a monotonic clock around each
  request (772-775) and checked before the next (759). So the last request may run past the share by up to one deadline,
  or two where a failed reading is followed by a checkpoint. While both lines hold runs each has half; at least `floor`
  runs of each line are asked for whatever the time, 2 with the defaults (622-625).
- A run that never reaches a final phase is asked for at every pass for ever (804); nothing retires it. In T2, runs
  given their NO_OUTCOME notice at t=900 (a-09 to a-13) were asked for again at t=4500 (`passes_T2.json` on that branch).
- Budgets are read one after another with one clock value per pass (1258-1259; docstring 107).

A small example with the defaults. If each GET /run takes t seconds, one budget's pass asks for about 600 / t runs:

| t per GET /run | Runs asked in 600 s | Comment |
|---|---|---|
| 0.05 s | about 12,000 | not measured on the deployment |
| 0.5 s | about 1,200 | not measured |
| 5 s | about 120 | not measured |
| 59 s (answered just inside the deadline) | about 10 | the service's choice |
| 60 s, then a 60 s checkpoint | about 5 | the service's choice |

So a service using these powers needs about a dozen runs left CONSUMED for ever, each answered in 59 s, to keep one
budget from ever being read whole: eleven are asked for before the 600 s are spent, and the twelfth is put off. It
needs no overload, and from outside it looks like a slow database. Each of those runs would get its NO_OUTCOME notice,
so they are visible one by one; what is not said is that the budget is never read whole.

Illustration only (the numbers are invented): if honest operation leaves 10 runs a day that never finish, then at
0.5 s a request the 1,200 of a pass are used up in about 120 days, after which no pass is whole, for ever.

Several budgets: if each of B budgets uses its whole share, one budget is evaluated again no sooner than about
B x 600 s later, plus the chain, sending and the interval of `--every`. With two such budgets that is already past the
900 s waiting time; a lease L would have to be longer than one whole cycle over all budgets.

Result size: a 32 MiB result must arrive within 60 s, about 0.53 MiB a second at least. Over HTTPS and the database on the
deployment this has not been measured. The diagnostic read 72 runs in 0.21 s in process against a stand-in, which says
nothing about it.

COVERED is therefore reachable under honest load only if: (i) the not-done runs in EFFECT or CONSUMED times the time
of one GET /run fits in 600 s; (ii) runs that never reach a final phase do not pile up; (iii) with budgets read in
sequence, the time between two evaluations of one budget stays inside L; (iv) results are of ordinary size.

What would settle it, with no change to code: a measurement on the deployment of GET /run latency and result size at a
stated load, a count over time of runs that never reach a final phase, and the time of one whole cycle over all
configured budgets. What would change it: a bulk or feed reading at the witness, a bound on stored result size, a way
to retire abandoned runs. Each touches the frozen gateway, and each would need its necessity named. Reading budgets in
parallel, or evaluating the lease apart from the reading, would touch only the courier, but is a change to its loop and
is not proposed here.

A budget that mostly reads NOT COVERED will be ignored. The reader cannot tell a hostile service from an overloaded one.

## 6. Ledger

### Confirmed defects of `e25a297`

| Id | Defect | Where | How confirmed |
|---|---|---|---|
| D-a | `end_read` clears `unfinished_since`, `blocked_sent`, `failed_sent` for any pass ending 'read', including one that put runs off; `end_blocked` counts from `unfinished_since`. No alarm in T2 (4500 s) | courier.py 1023-1025, 1056-1066 | test and code |
| D-b | The fixed last line of every form-2 notice says "from what the witness gave it, read to decision N"; alarms pass `st.get('seq', 0)`. False where nothing was read (T1f); inexact where the witness gave nothing in that pass (T1d) | check_record.py 353; courier.py 523 | test and code |
| D-c | A trailing comment on INTERRUPTED in `WHY_2` swallowed the entries for INDETERMINATE, NO_OUTCOME, UNVERIFIED, REFUNDED; with `outcome in WHY_2` false their form-2 notices have an empty third line. R25, R26, R30 pass with it | check_record.py 303-307, 346 | code reading |
| D-d | WATCHING is made whenever no run was put off, without regard to runs asked for and not read; its words promise the future ("From that decision on, it makes a notice of each run that calls for one") | courier.py 841; check_record.py 364 | code reading; no test |
| D-e | One clock value for a whole pass over all budgets; a slow budget delays the alarm of the next | courier.py 1258-1259; docstring 107 | code reading |
| D-f | "Complete" has several meanings: ending 'read' (1023), `whole` (750, 831), no run put off for WATCHING (841), the exit status (docstring 46-48). In T2 the status said "the last pass did not complete: 71 runs put off" for the pass that cleared the alarm's count | courier.py as cited; `passes_T2.json` pass 9 | test and code |
| D-g | With the witness stopping at a newly arrived run in every pass (T1b), an older failed run was not noticed in the passes run (to t=1600); the alarm was on time | diagnostic note, T1b | test |
| D-h | Cost, not a wrong statement: a run that never reaches a final phase is asked for at every pass for ever | courier.py 804; T2 | code and test |

The R25, R26 and R30 counts with D-c in place (19 of 19, 28 of 28, 111 of 111) are from three development runs by the
coordinator on `e25a297` on 21 November, 08:15 to 08:20 UTC. Their output is in the session's working files, not in
the repository. They are not official runs.

### Reported by the eighth internal review, not re-confirmed

- F1: the fifth group is never reached while new such runs keep arriving, so a FAIL stands signed as UNREADABLE.
- F2: falls inside the floor delay everything; the stated bound is false.
- F4: the wording of a clock step.
- F5: form-2 notices of earlier forms fail the new checker.

Stated as open in the courier's own docstring, unchanged: a courier whose own state is malformed, that is not running,
or that cannot send tells the mailbox nothing (courier.py 111-112; 1264-1268).

### The diagnostic of 21 November, against the stand-in only

Witness stopping and resuming in mid-pass at every pass, or answering nothing: one signed COURIER_BLOCKED at the first
pass at or after 900 s (0 s late; 100 s late when killed before the save), durable through a mailbox outage and a kill:
PASS against the stand-in. T2: no alarm in 4500 s; failure notices made 2600 s and 3300 s after the runs could first
be read: FAIL. T1f, provenance: FAIL. Against the deployment: UNPROVEN.

### The corrected planted-defect pass figures

The final planted-defect pass of the fourth form, on `769f6e4`. Result file `mutants5_result.json` in the session's
working files, not in the repository, sha256 beginning `f16bd4e255ec5e4a`; 104 entries. The control passed (R26 27
checks, R30 67 checks, none false). Of 103 planted defects: **98** caught by a check that failed; **4** made both tests
fail to finish within 600 s with no check failing ("the read is not bounded"; "F3: the reader neither closed nor
timed"; "F3: the reader does not look at the deadline"; "G5: the error body read whole, with no deadline"), counted
apart and not as caught by the amendment's own rule; **1** missed ("G1d: a pass that put runs off exits 0", judged
equivalent by the implementer). These counts were made again from the file for this draft and agree.

It was earlier reported as "102 of 103 caught": to the owner (corrected in the audit of 20 November), in the
development log, and in the design review's section 7. 98 / 4 / 1 is the count. Other passes were not recounted.

A clean planted-defect pass measures the tests against the code, not the code against the property. That form then
failed review.

## 7. What may not be claimed

- That a failed run is notified within any time, or within the pass.
- That COURIER_BLOCKED is always made within the waiting time. T2 shows it is not.
- That the absence of an alarm means a budget is being read, or that CONFIRMED means it is watched now.
- That every notice was made "from what the witness gave it", or that the notices of INDETERMINATE, NO_OUTCOME,
  UNVERIFIED and REFUNDED carry their explanation.
- That notification says anything about the truth of a verdict, or, until it is tested, that a committed verdict
  cannot be replaced.
- That the courier can tell the witness down from one run unreadable as a matter of cause.
- That COVERED is reachable on the deployment, or that it is built. It is a proposal.
- That the diagnostic's PASS verdicts hold beyond the stand-in, or that any test stalled the real database.
- That P1 to P7 are met, that Amendment 16 is declared, or that any form is accepted.
- That anything here is independently validated, or that G2, G5 or G6 is closed.
- That a receipt shows a person read anything, or that the mailbox is independent of the service in the demonstration.

## 8. What the owner is asked to decide

1. Whether the table of section 2 is accepted as the fixed model, including the three powers it adds (when each
   witness answer arrives; the rate of runs; runs that never finish), or how it is to be changed.
2. Whether the split of section 4 is accepted, with UM1 to UM6 kept as named, unmet requirements.
3. Whether COVERED / NOT COVERED is accepted as the candidate form of the achievable guarantee; if so, who sets L, and
   on what evidence.
4. Whether the reading of section 3 (when a verdict is committed; two signed digests accepted for one run) is to be
   tested first, before anything else is decided, and whether "a database role" in the property file means only the
   role the store grants the service.
5. Whether the measurement of section 5 is to be made on the deployment before any change to the frozen gateway is
   weighed.
6. How the eighth form is to be described meanwhile (built, not declared, failed its eighth internal review).
7. Whether this draft, once approved or amended, goes on `verification-amendment-16` beside the property file, which
   it does not change. Until then it is kept on `diagnostic-amend16-alarm-2026-11-21` only, and `verification-
   amendment-16` stays at `e25a297`.

Nothing in this draft proposes that implementation begin.
