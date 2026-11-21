# Diagnostic: Amendment 16, eighth form. Does the courier's alarm hold when the witness stops and resumes?

21 November 2026. Private working material. Internal work by the author of the code, under the owner's direction. It is
not an independent validation, it is not a declaration, and no official run was made. No code of the service, the
gateway, the witness, the mailbox or the courier is changed on this branch: it adds a test harness, its results and
this note to commit `e25a297` (the eighth form of the repair on `verification-amendment-16`, which is not declared and
whose eighth internal review failed it).

## The question

Asked by the owner on 21 November, before any further work on the eighth form:

> Simulate a witness that stops responding and then resumes mid-pass, including an older failed run and newly arriving
> runs. Determine whether the courier emits and durably records a truthful signed alarm within the specified waiting
> deadline, even when the original failure notice is delayed. Also verify that no false coverage, progress or
> provenance statement is signed. Report PASS, FAIL or UNPROVEN with exact evidence and timings.

## What was run

`tests/diag_amend16_alarm/adv.py` drives the real courier (`verify/courier.py`, sha256 `9a9d42c1d413e2dd…`) in process
against the stand-in witness and the real mailbox class of `tests/notify_standin.py`, both as they are at `e25a297`,
from a copy made by `git archive e25a297`. The pass clock is simulated: a pass every 100 s; the waiting time
(`stall_after`) is 900 s, the courier's default. "Stops responding and then resumes" is the stand-in's `knocks`: the
answer for one run is dropped while it is read, the courier's next request (its question whether the witness is up) is
refused, and from the request after that the witness answers again.

`check.py` and `check_t2.py` run in a process of their own. They read what the mailbox holds, the courier's state file
and its log of deliveries from disk, verify every courier signature and every mailbox receipt, and test each sentence of
the alarm against the stand-in's own record of every request it received (written to a file as each request happens).

Run on 21 November 2026 at 08:47 UTC (without T1f, and with a fault in the check of the killed pass Kb, since
corrected: the check compared the alarm with the pass before it, because what the killed process had asked for was not
yet written to a file), and whole at 08:50 and 08:57 UTC. The verdicts were the same each time. The results kept in
`tests/diag_amend16_alarm/results_2026-11-21/` are those of the last, 08:57:12 to 08:57:42 UTC. Across the nine
scenarios: 239 notices held by the mailbox, 0 courier signatures that fail, 0 receipts that fail; 106 sentence and
record checks hold, 4 do not (listed below).

To run it again:

    git archive e25a297 | tar -x -C SRC
    python tests/diag_amend16_alarm/adv.py SRC <scenario> OUT        # T1a T1b T1c T1d T1e T1f Ka Kb T2
    python tests/diag_amend16_alarm/check.py SRC OUT T1a T1b T1c T1d T1e T1f Ka Kb T2
    python tests/diag_amend16_alarm/check_t2.py SRC OUT T2

## Results

In every scenario the budget holds runs in flight, an older failed run whose entry in the chain comes to say FAIL
(`y-old-fail`), an older failed run whose entry does not change (`z-old-fail`), and newly arriving runs. The first pass
that does not complete is at t=100 s unless said otherwise, so the alarm falls due at t=1000 s.

| Scenario | What the witness does | Alarm COURIER_BLOCKED | Failure notices |
|---|---|---|---|
| T1a | stops and resumes in mid-pass at every pass, at a run of the old line; a new failed run arrives at every pass | made in the pass at t=1000 (0 s late), taken by the mailbox in that pass | `z-old-fail`, `y-old-fail`, `n-01-fail` at t=1300: 1200 s after they could first be read, 300 s after the alarm |
| T1b | stops and resumes at a newly arrived failed run at every pass | t=1000 (0 s late), taken in that pass | the older failed run `h-old-fail` not noticed in the passes run (to t=1600) |
| T1c | as T1a, with no pass ever completed before | t=1000 (0 s late); no statement of coverage was ever signed | t=1300 |
| T1d | answers nothing at all for twelve passes, then answers | t=1000 (0 s late) | t=1300, the first pass after it answers again |
| T1e | as T1a; the mailbox does not answer at t=900 to 1200 | made at t=1000 and kept in the outbox on disk; taken by the mailbox at t=1300 | t=1300 |
| T1f | answers nothing from the first pass the courier ever makes (first unfinished pass t=0, due t=900) | t=900 (0 s late) | none could be made |
| Ka | as T1a; the courier process is killed before the state that holds the alarm is saved | made at the next pass, t=1100 (100 s late: one pass); one alarm, not two; its text says 1000 seconds | t=1300 |
| Kb | as T1a; killed after that save, before the alarm is sent | made at t=1000, taken by the mailbox at t=1100; one alarm | t=1300 |
| **T2** | stops and resumes in mid-pass for eight passes, then answers one whole pass slowly; repeated | **none in 46 passes (t=0 to 4500)** | `y-old-fail` t=900; **`n-new-fail` t=2700 (2600 s after it could first be read); `z-old-fail` t=3400 (3300 s)** |

The alarm's words in T1a (T1b, T1c, T1e, Ka, Kb the same but for the run named and the number of seconds):

> THE COURIER HAS NOT COMPLETED A PASS OVER THIS BUDGET: THE WITNESS DID NOT GIVE IT WHAT IT ASKED FOR
> No pass over this budget has been completed for 900 seconds by its clock.  In the last pass, the witness stopped
> answering after the courier asked it for run "a-09"; the runs asked for before it in that pass were asked for as
> usual, and the runs after it were not asked for in that pass.  The courier tries again at each pass. […]
> This notice was made by the courier courier-t from what the witness gave it, read to decision 12. […]

Each of these was tested against the stand-in's record of the pass that made the alarm, and holds in T1a, T1b, T1c, T1e,
Ka and Kb: the number of seconds is the time since the first unfinished pass and no more than the time since the last
completed one; the run named is the last the courier asked for in that pass and its answer was dropped; the request
after it was not answered; the runs asked for before it were answered; no run was asked for after it; the decision named
is the one the courier had read.

## Verdicts

**1. A witness that stops and resumes in the middle of every pass (T1a, T1b, T1c): PASS, against the stand-in.** One
alarm, signed by the courier's key, made in the first pass at or after the waiting time (0 s late), held by the mailbox
with a valid receipt, in the courier's log of deliveries, with every sentence true of the pass, and made before the
delayed failure notices (which came 300 s later, or not at all in the passes run).

**2. The alarm is durably recorded (T1e, Ka, Kb): PASS, against the stand-in.** With the mailbox down it stays in the
outbox on disk and is delivered when the mailbox answers. Killed before the save, the courier makes it at the next pass
(100 s late, with a number of seconds true of that pass) and makes one, not two. Killed after the save, the alarm is on
disk and is delivered at the next pass.

**3. Coverage statements: PASS, against the stand-in.** In no scenario was a statement of coverage (WATCHING) signed in
or after a pass that did not read every run not done; the only one is from the complete pass at t=0 (and none at all in
T1c and T1f).

**4. Provenance statement: FAIL.** Every form-2 notice ends with one fixed line (`verify/check_record.py` line 353):
"This notice was made by the courier … from what the witness gave it, read to decision N." In T1f the witness has never
given the courier anything, and the signed alarm says "from what the witness gave it, read to decision 0". That is not
true: the notice was made from the absence of any answer. In T1d the same line is signed in a pass in which the witness
gave nothing; "read to decision 1" is true of an earlier pass, and the body of the notice says correctly that the
witness cannot be read, so there the line is inexact, not false. The decision number in that line agrees with the number recorded in the
notice in the eight alarms and in all 80 notices of T2; it was not tested against the stand-in's own count.

**5. A witness that stops and resumes in most passes and lets one whole pass through slowly (T2): FAIL.** No alarm was
made in 4500 s. The failure notice of the newly arrived failed run was made 2600 s after it could first be read and that
of the older failed run 3300 s after, against a waiting time of 900 s. In that time the mailbox received 43 NO_OUTCOME,
21 UNREADABLE and 2 FAIL notices about other runs, each true of its own run (all 31 UNREADABLE notices were tested
against the stand-in's record: 31 of 31), and nothing that speaks of the budget as a whole: no signed statement says
that passes are being cut short or that other runs are not being asked for. A reader of the mailbox cannot tell this
budget from one that is merely busy.

The cause is in the code, not in the stand-in. `end_read` (`verify/courier.py` lines 1023 to 1025) clears
`unfinished_since`, `blocked_sent` and `failed_sent` for any pass that ends 'read', and a pass that put runs off for
want of time ends 'read'. `end_blocked` (lines 1056 to 1066) counts the waiting time from `unfinished_since`. So one
slow pass in every nine starts the count again: the longest streak of unfinished passes in T2 is 700 s. The courier's
own status disagrees with its count: after the pass at t=900 it says "the last pass did not complete: 71 runs put off"
(exit status 1, no WATCHING statement), and that same pass cleared the count. The status's stated bound for a run of
the old line (36 passes at t=100) held: `z-old-fail` was asked for again at the 34th pass. But the bound is local, it
is counted in passes and not in time, and nothing of it is signed.

**6. The same against the deployment: UNPROVEN.** None of this was run against the witness service, the mailbox service
or the courier as deployed, over HTTPS, with the real clock and the real deadline of 60 s. The pass clock is simulated,
and in T2 the time a slow pass itself takes is not counted in that clock (in real time the delays would be longer, not
shorter). T2 depends on real timing, with the deadline of a request and the time of a pass scaled down (0.5 s and 4 s
for 60 s and 600 s, the same floor of 2); it gave the same result in each of three runs. No planted-defect pass was made
on this harness: that its checks can fail is shown only by the four that did.

## What this does and does not establish

- The alarm is not "silently delayed" by a witness that fails in the same way at every pass, or that answers nothing.
  It is missing when the witness lets a pass through, slowly, more often than once in the waiting time. That is within
  what the documented shared-database assumption gives the service: the service decides when the witness answers.
- The eighth form therefore does not meet "a delayed failure is announced within the waiting time" even in the narrower
  sense of an alarm in place of the notice. The original property (P1 to P7 of
  `verify/AMEND16_PROPERTY_2026-11-20.md`) stands as written and is not met.
- This note proposes no repair. By the owner's instruction of 21 November, implementation stops here, no further form
  of the reading loop is begun, and no declaration is issued; the next step is a design-only architectural review.
- Findings of the eighth internal review (the lost WHY_2 entries of four outcomes, among others) are not re-tested here
  and remain open.
- G2, G5 and G6 remain implemented and internally tested, with open obligations. One machine, one kernel, a database
  shared by the witness and the service, and no real separation of the parties are unchanged.
