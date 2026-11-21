# Design-only architectural review of Amendment 16's notification path

21 November 2026. Private working material. Internal work under the owner's direction. It is not an independent
validation, not a declaration, and not a specification for another form of the courier. Nothing was run, built or
changed for it: the tree at `e25a297` was only read. No official run was made. Release gates G2, G5 and G6 stay
implemented and internally tested, with open obligations.

## Why it was made

On 21 November the owner set a rule before any further work on the eighth form: one targeted adversarial test; if the
alarm guarantee held, a narrower threat-model addendum and wording repairs only; if the alarm was silently delayed,
missing, untruthful or could not be shown, implementation stops and a design-only architectural review follows, with no
further redesign of the reading loop and no declaration. The test (`verify/DIAGNOSTIC_AMEND16_ALARM_2026-11-21.md`, on
this branch) found the alarm missing where the witness lets one whole pass through slowly in every nine, and a false
provenance sentence. This is that review. It was made by a separate reviewer session given the property file, the
addendum, the code at `e25a297`, the development log and the diagnostic note, and told to write no code.

## The coordinator's notes on it

What was checked against the code at `e25a297` after the review came back, and holds: `end_read` clearing the count for
any pass that ends 'read' (`verify/courier.py` 1023 to 1025); alarms signed with `st.get('seq', 0)` (523); the statement
of coverage made whenever no run was put off, without regard to runs that could not be read (841), and its sentence
about the future (`verify/check_record.py` 364); the clock taken once before the loop over all budgets (1258 to 1259);
a budget whose own state is malformed skipped with no alarm (1265 to 1268); the four lost entries of `WHY_2`
(`check_record.py` 303 to 307, 346); `chain_hash` covering seq, op, kind, code and observation only (145 to 146); no
occurrence of `result_digest` in `plea_gateway/store.py`; GET /chain with `after=K` at the witness; and the property
file's own statement that the service is taken to hold the gate's key (line 21). The rest of the review's citations
were not re-checked.

Corrections and cautions:

1. Section 7 says a defect pass "caught 102 of 103 planted defects". That figure is the development log's summary line
   and is not right as a count of defects caught by a failing check. The result file of that pass (the fourth form)
   shows 98 caught by a check that failed, 4 that did not finish within 600 s (hangs, which are counted apart and not as
   caught), and 1 missed. The review's point stands with the corrected figure.
2. Section 7's "two reports never delivered" was not confirmed; the log records one.
3. The review's step 5 (the courier's accounting, with the alarm taken out of the endings of a pass) may be a redesign
   of the reading loop in the sense of the owner's instruction. The review leaves that to the owner, and so does this
   note. Nothing in the review has been begun.
4. The recommended statement of coverage is only as useful as it is often true. Under the present way of asking, run by
   run, a whole reading may be rare under ordinary heavy load, and the service can make it rare by adding runs. A
   budget that reads NOT COVERED most of the time will be ignored. The review names this as the necessity for a change
   to what the witness offers (its alternative (c), which touches the frozen gateway). It should be weighed before the
   recommended path is taken, not after.
5. The review is one reviewer's reasoning over the code and the documents. It is internal, and none of its conclusions
   has been tested.

## The review, as returned

Internal review under the owner's direction. Nothing was run, changed or committed; the tree at e25a297 was only read. This is not a validation, not a declaration and not a specification for a ninth form. G2, G5 and G6 stay "implemented and internally tested, with open obligations".

## 1. Summary

**The achievable property.** Against a party that controls what the witness answers and when, no courier can promise that a given run is read, or that its notice arrives within any time. What can be met is narrower:

> At every moment, for every configured budget, a reader of the mailbox can derive exactly one of two states from signed statements. COVERED: the courier signed, and the mailbox receipted within the last L seconds by the mailbox's clock, that it read the budget whole to decision N, and the mailbox holds every notice that reading called for. NOT COVERED: anything else, whether the courier said so or said nothing.

This is a safety property with no promise of timeliness. "Not covered" is the default and needs no courier action to become true.

**The recommended path.** Alternative (b), restated: move the guarantee off the reading loop and onto one positive, expiring, signed coverage statement, evaluated on the receiving side. The steps before it are a dated threat model and a small explicit model of the invariant. Alternative (c) follows only if liveness under load is wanted, with its necessity named. Alternative (d) stays a named, unsatisfied requirement.

**The three main reasons.**

1. **The failures are structural in one specific way.** All eight forms carry the guarantee in the asking order and in the classification of how a pass ended. The adversary sees the order and chooses which request stalls, so a defeating schedule always exists. The reviews will keep finding one as long as the property promises per-run timeliness.
2. **The alarm is built on recognised failure kinds.** A timer starts on some endings and is cleared by others, so any ending classed wrongly is silent. That is the T2 mechanism. An alarm derived from the last positive proof ("last whole reading at W") has one variable and one writer, and cannot be reset by a partial success.
3. **A courier cannot announce its own absence.** A dead or damaged courier, or one that is alive but starved (T2), is only visible to a party that expects a statement and sees none. A plain heartbeat is not enough: the T2 courier is alive and sends true notices throughout.

## 2. What I verified by reading, and what I did not

Verified in the code at e25a297:

- **T2 mechanism.** `end_read` clears `unfinished_since`, `blocked_sent` and `failed_sent` for every pass that ends "read", including one with runs put off or unread (`verify/courier.py` 1023-1025). `unfinished_since` is only ever set in `end_blocked` (1057) and `end_failed` (1079-1082). A "read" pass with 71 runs put off starts no timer and stops the running one.
- **Four meanings of "complete".** The file uses at least four: ending "read" (1023), `whole` (750, 820), "no run put off" for WATCHING (841), and exit status (`failed()`, 1283). They disagree, as the diagnostic saw.
- **WATCHING with unread runs.** WATCHING is made when nothing was put off, even if runs were asked for and could not be read (841). Its words say "asked", so they are true, but they also make a promise about the future: "From that decision on, it makes a notice of each run that calls for one" (`verify/check_record.py` 364). No signed promise can be true by construction.
- **Provenance line.** It is one fixed sentence for every form-2 notice (`check_record.py` 353). Alarms pass `st.get('seq', 0)` (`courier.py` 523), which gives "read to decision 0" when nothing was ever read.
- **F3.** A trailing comment on the INTERRUPTED entry of `WHY_2` swallowed the entries for INDETERMINATE, NO_OUTCOME, UNVERIFIED and REFUNDED (`check_record.py` 303-307). With `outcome in WHY_2` false (346), the third line is empty for those four outcomes.
- **One clock value per pass.** `one_pass` takes the time once, before the loop over all budgets (`courier.py` 1259). Every "by its clock" age for a late budget is counted from the start of the pass. Budgets are read in sequence, so a slow budget delays the alarm evaluation of the next. The diagnostic's simulated clock does not show this.
- **Malformed own state.** A budget whose own state is malformed is skipped with no timer and no alarm (1265-1268). The docstring states this as open.
- **Where the verdict lives.** PASS or FAIL is not in the chain. `chain_hash` covers seq, op, kind, code and observation (`check_record.py` 145-146). The verdict is read from the stored result, believed if it hashes to the digest in a gate-signed report (`check_record.py` 157-158, 200-203). `plea_gateway/store.py` has no occurrence of `result_digest`. Results are written by the service's role alone (`store.py` 866). GET /run is unsigned (`plea_gateway/witness_service.py` docstring).
- **Witness interface.** The witness already offers an append-only reading since a decision number (GET /chain?after=K). It has no reading that lists budgets.
- **Floor.** `floor_of` gives 2 with the defaults (`courier.py` 622-625).

Not verified: F1, F2 and F5 of the eighth review (taken from the brief), anything about the real deployment, and whether the service's database role can in practice stall a chosen witness request. I assume it can, since the documents concede shared database, one machine and one kernel.

One consequence to state plainly. The property file gives the service the gate's key. Such a service can sign a PASS result outright and needs no timing attack. The notification path can therefore guarantee nothing about a verdict the service chose to falsify. It concerns only verdicts the service has already committed to through a signed digest.

## 3. Question 1: the achievable property and P1 to P7

**Assumptions, all named.**

- **A1.** The courier is honest and its key is secret. It may be killed and restarted; its state file survives or is lost whole.
- **A2.** The mailbox is honest, has a clock of its own and stores durably.
- **A3.** The service does not hold the witness's key and does not rewrite the chain (documented as out of scope).
- **A4.** The service chooses names, every field and size of a result, which budgets exist, when runs are added (at any rate), and whether and when each witness answer arrives, per request.
- **A5.** The courier-to-mailbox channel delivers when both are up. On one machine this is an assumption, not a fact.
- **A6.** Someone or something reads the mailbox's state at the time in question. The mailbox is passive storage.
- **A7.** The courier's clock is its own. Only the mailbox's receipt times are used to judge freshness.

**Invariant N1 (receiver side, holds against A4 in full).** At mailbox time τ, budget B is COVERED to N if and only if the mailbox holds a courier-signed coverage statement "whole to N", receipted at ρ with τ − ρ ≤ L, and holds every notice that statement names. Otherwise B is NOT COVERED. No other state exists, and none is inferred from the absence of an alarm.

**Invariant N2 (courier side, holds only while the courier runs).** Let W be the courier-clock time of the last whole reading of B, or "never". At every evaluation, either now − W < L, or a signed "not whole since W" statement for that W is in the durable outbox. Evaluation happens at a bounded interval that does not depend on any witness answer.

**"Whole reading to N" must mean exactly this:** a fresh signed checkpoint at N was verified; the chain was verified to N; every run in that chain that may call for a notice and is not final has an outcome computed from an answer received after that checkpoint; and every resulting notice is saved in the outbox. A run asked for and not answered makes the reading not whole. So does a run not asked for.

| Property | Status under A1-A7 | Note |
|---|---|---|
| P1 (no run hides another; notice within the pass) | **Exceeds** as written | The timing clause is a liveness claim. It fails against A4 by withholding alone, and against unbounded run arrival even with answers inside the deadline. Weaker form met: an unread or unasked run can never make the budget read as covered. Keep the original as an unsatisfied requirement; it needs (d), (c) and a bound on arrival rate. |
| P2 (unreadable run stays visible, UNREADABLE notice) | **Weaker form** | "Never marked done, shown in status" is met. "The mailbox is sent a notice after the waiting time" holds only while the courier runs, evaluates and can send. A FAIL may stand signed as UNREADABLE indefinitely (F1). That is truthful only because UNREADABLE says the outcome is unknown. |
| P3 (witness down told apart from one run unreadable) | **Exceeds** as a claim of cause | The service can answer the probe and withhold the run, or the reverse. The courier can only report which requests were answered. Weaker form met: observations without attribution. |
| P4 (names refused at the door) | **Meets** | Independent of timing. Read in `witness_service.py`. Internally tested only. |
| P5 (the courier's words are the courier's) | **Achievable in full** | Independent of timing. Not met today because of F3 and F5. |
| P6 (coverage confirmed, not assumed) | **Meets, and N1 is stronger** | As written, P6 confirms only that watching began, and "CONFIRMED" never lapses. N1 adds the lapse. Budget discovery stays unmet and stated. |
| P7 (signed PASS looked at) | **Meets in the "may only add" form** | Independent of timing, but it inherits P1's weakness: the check runs only on a run that was read. Not re-evaluated here. |
| The three states | **Achievable** | Needs a fourth observation kept apart: "the courier is running and delivering, and is not covering the budget". |

## 4. Question 2: is run-by-run polling under a time budget the right mechanism?

**The case that it is only details.** T2 is one wrong clearing rule. F3 is a misplaced comment. The provenance line is one sentence. Each could be repaired in a few lines.

**The case that it is structural.** I find three arguments, and they hold.

1. **No order gives liveness.** For any deterministic order, the adversary stalls the request for the chosen run, or the request just before it so that the pass ends there. The "fellers" group exists for this reason, and F1 shows it starves in turn. Even an adversary that answers every request inside the deadline wins by adding runs: at up to two deadlines a run, a 600-second share reads five runs, and arrivals are unbounded.
2. **The pass is the wrong unit of truth.** Sentences such as "no pass completed" and "in the last pass" need every ending classed correctly. The endings multiply: four kinds, times put off, unread, unmade and fell. The addendum removed ten marks, and the eighth form has about as many again.
3. **The cost of a whole reading is set by the adversary.** Under run-by-run asking, a whole reading may be unreachable under honest heavy load too. That weakens any positive coverage statement.

**Conclusion.** Polling is acceptable as a way to fetch data. It is structurally unable to carry the guarantee. The repair is to make the order irrelevant to truth, so that a bad order costs coverage visibly and never silently.

**The coordinator's working view.** "No asking order guarantees that a chosen run is read" is right. "What can be guaranteed is only that delay is never silent" needs three corrections:

- **Silent to whom.** A courier-side clock can make it true only towards a mailbox, and only while the courier runs. A dead courier is silent. Nothing in this path reaches a person.
- **Not per run.** The courier knows only runs in a chain it has verified. The claim has to be about the budget ("not read whole since W"), with per-run notices as detail.
- **The diagnostic's finding is not a limit of courier clocks.** It comes from a timer that failure kinds start and partial success clears. N2 holds by construction if W has a single writer (a whole reading) and the evaluation is not queued behind witness requests. The single clock value per pass (1259) and the sequential budgets break the second condition today.

**Can it be true by construction rather than by marks?** Yes. The marks then only describe the reason in the statement. If a mark is wrong, the reason is wrong, but the alarm still fires. If whole readings are too rare under load, a finer form of the same idea is available: the age of the oldest unresolved run, taken as a maximum over runs. It is also monotone and also reset only by a successful read. I stop at that invariant.

## 5. Question 3: the alternatives

**(a) Narrower threat model plus smallest repairs to the eighth form.**
- Repairs: restore the four `WHY_2` entries; make the provenance line depend on what the notice was made from; stop `end_read` clearing the timer unless the pass was whole; reword "completed"; settle F5.
- The third repair is not small. A "read" pass with runs put off would then need its own timer and its own alarm text, because the BLOCKED words would be false for it. That is a new statement kind.
- Honestly claimable afterwards: against a witness that fails the same way at every pass or answers nothing, one alarm is made at the first pass after 900 seconds, shown against a stand-in only.
- Cost: low. Touches the courier and `check_record.py`.
- Open: F1, F2, the dead courier, and a contradiction. The documented shared database gives the service exactly the power this model would exclude. By the owner's own rule this path was ruled out by T2. It is usable only as the honest label for the branch as it stands.

**(b) Receiver-side coverage lease.**
- Guarantees N1. It covers a dead courier, damaged state, a courier that cannot send, and any failure kind nobody has thought of.
- Assumes A2, A5 and A6.
- Cost: a new statement kind; an evaluation rule in the mailbox or the checker; a decision on L.
- Touches `verify/courier.py`, `verify/check_record.py` and `verify/mailbox_service.py`. It does not touch the gateway or the witness.
- Open: the adversary can keep a budget NOT COVERED for ever, visibly. Nobody is alerted unless something reads the mailbox. The mailbox is on the same machine in the demonstration.
- The lease must carry coverage, not just liveness.

**(c) A different witness reading.**
- Guarantees nothing more against a withholding adversary. It does remove the dependence of a pass's cost on the number of runs in flight, so no order exists to starve and whole readings become normal under honest load.
- Two shapes. One is a bulk reading of reports and results for decisions after K, unsigned and checked as today. The other is a witness-signed digest per checkpoint of each run's outcome, which would be the first witness-signed statement about outcomes.
- Touches the frozen witness. The necessity to name: without it, a lease would read "not whole" under ordinary load, and the service can cause that cheaply by adding runs.
- Open: the service chooses result sizes, up to the courier's 32 MiB limit, so a bulk answer can still be made slow. A size bound belongs in the store, which is also frozen.
- The clean end state is the verdict bound into the chain at reconcile time. That changes the gate's report and the store. I do not recommend it now.

**(d) Separating the witness's database.**
- This is the real trust boundary. It removes the service's power over when the witness answers, as far as the database goes.
- By itself it does not fix: one machine and one kernel (CPU and loopback contention remain); unbounded run arrival; the dead courier; the T2 accounting; any wording.
- It would require results to be submitted to the witness, not written beside it. That is a deep change to the frozen gateway.
- It is the precondition for ever meeting P1 as written. Keep it as a named, unsatisfied requirement.

**(e) What I see as better.** Use (b), with N2 on the courier side derived from the same W that the lease reports. One fact then drives the courier's alarm and the receiver's absence detection.

**Recommendation and order of steps.**

1. A dated threat-model addendum that fixes the adversary's powers as a table (A1-A7), splits each property into a safety part and a liveness part, and lists the unmet requirements by name.
2. A small explicit model of N1 and N2, explored before any code, with tests written by someone other than the implementer.
3. The statement set and its truth conditions (section 6), including the wording repairs.
4. The receiver-side rule in the mailbox and the checker.
5. The courier's accounting for W and the lease. This needs no new asking order. It does need the alarm taken out of the pass endings. Whether that counts as a loop redesign is the owner's call.
6. Only then, evaluate (c) with its necessity named.

**Out of scope, explicitly:** (d); any timeliness promise for a run's notice; engineer acknowledgement; budget discovery; a service that falsifies a verdict with the gate's key or rewrites the chain; closing any release gate.

## 6. Question 4: signed statements

| Statement | Signer | True exactly when |
|---|---|---|
| NOTICE (run, outcome) | Courier | The outcome was computed from an answer for that run received after the checkpoint at decision N, checked against the gate keys given. |
| UNREADABLE (run) | Courier | The run is in the verified chain at N; the courier asked for it at least once; no outcome has been computed since "since"; and now − since ≥ the waiting time. It states the count of tries and the last try, and no cause. |
| COVERAGE whole (N, W, list or digest of notices made since the last one, number k, digest of statement k−1) | Courier | A whole reading to N, as defined in section 3, finished at W. It speaks only of the past. |
| COVERAGE not whole (last W or "never", reason) | Courier | now − W ≥ L at an evaluation. The reason is data: no checkpoint answer; chain not finished; n runs asked and not answered; m runs not asked; the courier's own error. A wrong reason does not make the statement false in its main clause. |
| COURIER_STOPPED | Courier | The witness gave something verifiably inconsistent (fork, rollback, bad chain). The evidence is kept. Unchanged. |
| RECEIPT | Mailbox | The mailbox stored exactly this notice at the stated time by its clock. Unchanged. |
| Engineer's disposition | Engineer | Exists already, outside this path. Nothing above may use a word for reading. |

The four points the brief asked for:

- **Provenance line.** Replace the fixed sentence by one chosen from what the notice was actually made from. Four cases: the chain to N and the witness's answer for this run; the chain alone to N; no answer in this attempt, with the last decision verified and when; nothing ever read from the witness for this budget. The constant parts stay: who signed, that the service did not write it, and what a receipt means.
- **"No pass completed for N seconds."** Drop "pass" and "completed". Say "the courier last read this budget whole at W by its clock" or "has never read it whole". N is then defined, and T2 cannot reset it.
- **WATCHING.** It becomes the first COVERAGE whole statement. The forward promise goes. "Confirmed" becomes "covered to N as of ρ", and it lapses.
- **The three states.** Courier not covering is the courier's COVERAGE not whole, or the absence of a fresh lease. Mailbox accepted is a receipt and nothing more. Engineer acknowledged is only the engineer's own signed disposition. The fourth observation, "delivering but not covering", is shown by COVERAGE not whole arriving alongside ordinary notices. Absence of an alarm never reads as covered, because covered needs a positive, unexpired statement.

## 7. Question 5: why the method failed eight times

Read from the DEVLOG, the property file and the addendum:

- **The adversary was never fixed.** The property file lists data powers (names, fields, sizes, budgets) and no timing or rate powers. Each review added one: hanging runs, alternate failures, a clock step, positions in the outbox, the courier's own faults, a failure at a chosen place in the order, one slow whole pass.
- **P1 mixes safety and liveness.** The liveness part cannot be met, so every form approximated it and every review broke the approximation.
- **Tests measured the code against itself.** A defect pass caught 102 of 103 planted defects on a form that then failed review. That measures tests against code, not code against the property. F3 passed every suite.
- **One author, one stand-in.** The implementer wrote the tests and the stand-in. The threat runs through the database, and no test stalls the real database.
- **Speed.** Eight forms in about 28 hours by the log's timestamps, with two reports never delivered.

What should change before any implementation:

1. The threat-model table comes first and is agreed by the owner. A review finding outside it is a change request to the model, not a defect.
2. Each property is stated as an invariant over a small state machine: per-run state, W, the clock, the outbox, and the adversary's moves (add a run, answer, withhold, stall, kill, mailbox down, clock step). Explore it exhaustively at small bounds. Then drive the real courier with random schedules on a simulated clock, as the diagnostic harness already does for fixed ones. T2 is a nine-step schedule.
3. The author of the tests and the model is not the author of the code and does not read it first.
4. Every signed sentence has a recorded predicate, checked mechanically at signing time, plus a completeness check that every outcome has every line of text.
5. At least one scenario stalls the real witness through the database.

## 8. Question 6: what must not be claimed on the present evidence

- That a failed run is notified within any time, or within the pass.
- That COURIER_BLOCKED is always made within 900 seconds. T2 shows it is not.
- That the absence of an alarm means a budget is being read, or that CONFIRMED means it is watched now.
- That "no pass completed for N seconds" is a defined quantity.
- That every notice was made "from what the witness gave it".
- That form-2 notices of INDETERMINATE, NO_OUTCOME, UNVERIFIED and REFUNDED carry their explanation.
- That the courier can tell "the witness is down" from "one run is unreadable" as a matter of cause.
- That the diagnostic's PASS verdicts hold beyond the stand-in. No planted-defect pass was made on that harness, and nothing was run on the deployment.
- That P1 to P7 are met, that Amendment 16 is declared, or that any form is accepted.
- That any of this is validated, independently reviewed or production-ready, or that G2, G5 or G6 is closed.
- That a receipt shows a person read anything, or that the mailbox is independent of the service in the demonstration.

### Files the review names as the ones any later work would touch

- /home/user/PLEAai/verify/courier.py
- /home/user/PLEAai/verify/check_record.py
- /home/user/PLEAai/verify/mailbox_service.py
- /home/user/PLEAai/verify/AMEND16_PROPERTY_2026-11-20.md
- /home/user/PLEAai/plea_gateway/witness_service.py (only if alternative (c) is later taken, with its necessity named)
