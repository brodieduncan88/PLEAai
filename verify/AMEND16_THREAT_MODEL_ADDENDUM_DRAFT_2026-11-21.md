# Amendment 16: threat-model addendum (DRAFT for the owner's review, second revision)

21 November 2026. Private working material. Internal work under the owner's direction. It is not an independent
validation. It is a draft and is not approved. It is not a declaration. No code is changed by it. It does not change
`verify/AMEND16_PROPERTY_2026-11-20.md`: P1 to P7 and T1 to T8 stand as written there, and where this addendum says a
part cannot be met, that part stays a requirement, unmet. Release gates G2, G5 and G6 stay implemented and internally
tested, with open obligations. One machine, one kernel, a database shared by the witness and the service, and no real
separation of the parties remain material.

**The eighth form, `e25a297`, is INCOMPLETE. It failed its eighth internal review. It is not declared. Its eight
confirmed defects are listed in section 6 and go with any mention of it.**

This draft is kept on the branch `diagnostic-amend16-alarm-2026-11-21` only. `verification-amendment-16` stays at
`e25a297`.

Citations are to the tree at `e25a297` unless another commit or branch is named. "Code reading" means the cited lines
were read. "By test" means the checks of 21 November recorded in `verify/DIAGNOSTIC_AMEND16_ALARM_2026-11-21.md` (the
alarm) and `verify/DIAGNOSTIC_AMEND16_POWERS_2026-11-21.md` (the role, commitment, two digests, honest load), both on
this branch.

How it was made. First revision: a separate drafting session wrote it from a brief of facts the coordinator had
checked; the coordinator re-read every cited line and corrected it. Second revision, after the owner's instructions of
21 November: the role's grants, the commitment of a verdict and the two digests were checked on the deployment, the
honest-load measurements were made, and sections 2 to 8 were revised from the results. Section 8 says what the owner
has ruled, what the owner has deferred, and what is still open.

## 1. Why this addendum

Eight forms of the courier were built on `verification-amendment-16`. Each failed an internal review. The diagnostic
of 21 November found the alarm missing in 4500 s when the witness lets one whole pass through slowly in every nine
(T2), and a false provenance sentence (T1f).

The property file says what the service may choose (lines 21-24): run names, every field of a result, a result's size,
and which budgets exist. It gives the service no stated power over time: when the witness answers, how fast runs are
added, whether a run ever finishes. Yet lines 26-27 keep the shared database, one machine and one kernel. Much of what
the reviews found used a power over time that the file had not named; the rest were faults of the courier's own. This
addendum names those powers, says what notification can still promise against them, and keeps what it cannot promise
as named, unmet requirements. A later review finding that falls outside section 2 is then a request to change the
model, not a defect of the code.

## 2. The parties, and the service's powers

"Granted" says whether the property file already gives the power. "Lets it do" is what the power does to notification.
"Still promised" is what notification can say against it, if the defects of section 6 are repaired; at `e25a297` some
of these are not met. **The table is not locked: the owner has deferred that until the checks of 21 November have been
reviewed (section 8).**

| Power | Where it comes from | Granted | Lets it do | Still promised |
|---|---|---|---|---|
| Run names and every field of a result | property 21-24 | yes | put text of its choosing in a notice | shown as data only (P5) |
| Result size | property 22-23; courier reads to 32 MiB (courier.py 178) | yes | make one GET /run slow or unreadable | that run unread and visible (P2); no other run hidden by it |
| Which budgets exist | property 23 | yes | create a budget the courier is not configured for | never reported as covered (P6) |
| The gate's key | property 21 | yes | sign a report whose result says PASS for a run that failed | nothing about the truth of a verdict (section 3) |
| The database role `plea_local` | property 21 says "a database role"; the role is the one the client is configured with (deploy.py 35, 136). Grants read from the catalogue; changes tried, by test | yes, not named | read every table of every budget; store a result through `plea_put_result`; write its own operations through `plea_write`; hold connections (no limit); take advisory locks | it cannot change `results`, `evidence`, `decisions`, `attempts` or `roots` directly (20 changes refused), cannot write a RECONCILE, and cannot replace a result stored as a value |
| Replacing a verdict before it is committed (two signed digests) | the gate's key, the client's certificate and `plea_local` together; by test | follows from what is granted; not named | after the gate host signed FAIL and the witness recorded it: withhold the result (or store one marked 'unknown'), have a second report recorded over a PASS result, store the PASS. No notice; the record's checker silent for a forgery of the same design | a FAIL stored as a value stays, and its notice is made (by test). Before that, nothing. Both reports stay in the witness's answer for anyone who looks |
| When each witness answer arrives | by test, two ways: `plea_local` holding all 97 free connections makes every reading fail; the shared operating-system account stopping the witness delays one chosen reading (5.04 s shown). Not shown: delaying one chosen reading through the role alone | no | fail or stall readings at times of its choosing, up to the 60 s deadline (courier.py 212) | that a budget not read whole is never said to be read (safety); nothing about when a run's notice arrives |
| The rate at which runs are added | front door and gate, property 21; rate not stated | no | add runs faster than a pass can ask for them | shown, not repaired (courier.py 103-104) |
| Runs that never finish | follows from holding the gate; not stated | no | leave runs CONSUMED or UNVERIFIED for ever; each costs one GET /run at every pass (courier.py 403, 804) | each listed; NO_OUTCOME or UNVERIFIED notice after the waiting time if read |
| Any other database role (the demonstration only) | every role's password is literal text in the repository, the owner's included (`roles.txt`, 23 places); by test only so far as the schema was installed with the owner's | no | as the owner of the tables: anything, the chain included | nothing. Whether the model takes the service to hold `plea_local` only is for the owner (section 8) |
| Rewriting the chain | property 27 | out of scope | not answered | nothing |
| Holding the witness's, courier's or mailbox's key | property 18-19 (these are trusted) | out of scope | not answered | nothing |

Four facts about the code bear on the table:

- The chain binds seq, op, kind, code and observation (`verify/check_record.py` 145-146). The verdict is not in it. It
  comes from the stored result, believed if the result hashes to the `result_digest` of any gate-signed EFFECT report
  recorded for that budget, run and nonce (check_record.py 181-203, the `digests` list). Otherwise the run is
  UNVERIFIED.
- The stored result is written by the client, with `plea_local` (`plea_gateway/governor.py` 236-241), after the
  witness has recorded the gate's report (governor.py 257). `plea_put_result` keeps the first result stored, except
  one marked 'unknown' (`plea_gateway/store.py` 837-838).
- GET /run is unsigned (`plea_gateway/witness_service.py` 25-28). The witness offers three readings only, /checkpoint,
  /chain with `after=K`, and /run for one run (witness_service.py 14-28, 60). There is no bulk reading of runs and no
  list of budgets.
- The witness reads the same database as the service; the chain is written only through the witness's role (courier.py
  146-149; by test, a RECONCILE written as `plea_local` is refused). Whoever runs the witness can cut the courier off
  (courier.py 149-151).

Assumptions about the other parties, each named:

- **A1. The courier.** Honest; its key secret; its configuration its own (property 18). It may be killed and restarted.
  While it is not running, or its own state is malformed, or it cannot send, it tells the mailbox nothing
  (courier.py 111-112; budget skipped at 1264-1268).
- **A2. The mailbox.** Honest; its key its own (property 19); it stores what it receipts. Its clock is assumed to be
  its own; if a statement of coverage with a time limit is adopted later, the mailbox or its operator sets that limit,
  on the mailbox's clock (the owner's ruling of 21 November). The mailbox's code was not examined for this draft.
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

**When a verdict is committed, by test.** A verdict is committed when a result that hashes to a recorded gate-signed
report has been stored as a value, and not before.

- After that point it stayed. With a FAIL stored as a value, a second report over a PASS result was recorded by the
  witness (DUPLICATE / VERDICT_RETRY, with the report), `plea_put_result` changed nothing, the courier read FAIL and
  the mailbox accepted its notice. Every direct change to the stored result as `plea_local` was refused.
- Before that point it did not. The gate host signed FAIL and the witness recorded it. The service then withheld the
  result, or stored one marked 'unknown'; had a second report recorded over a PASS result; and stored the PASS. The
  courier read PASS. With the 900 s waiting time it made no notice before or after, and the mailbox held nothing for
  the run. Where the forged PASS named the same design with numbers that meet the limit, the record's checker raised
  nothing against the run.
- The witness then holds two EFFECT reports for one run with two digests, and gives both to whoever asks. Neither the
  courier nor the record's checker remarks on it. In honest operation a repeated report carries the same digest, so
  two different digests for one run have no honest cause known to this draft.
- A stored result that hashes to no recorded digest reads as UNVERIFIED (check_record.py 200-202), a notice after the
  waiting time if the run is read (courier.py 182, 818-823). A courier with no waiting time, reading between the first
  report and the replacement, said UNVERIFIED. A client without the gate's key can only withhold, which ends there.

**What this adds to the custody of the gate's key.** In one sense nothing: a service that can sign a second report
could have signed PASS in the first place. In another it is a separate power, and section 2 lists it so: the first
report here was the gate host's own, made by running the check. Whoever holds the key later, and the client's place,
can undo a FAIL that an honest gate host signed and the witness recorded, for as long as its result has not been
stored as a value; and it is the client, the party with most reason to, that stores it. Delay before that point is
therefore not only delay.

**Limits.** The role is confined as tested only if the service holds `plea_local` and no other role; in the
demonstration every role's password is in the repository. How long the service has was not measured: the replacements
were made within seconds. No planted-defect pass was made on the harness.

## 4. P1 to P7: what can be met, and what stays unmet

Each property is given one of three standings. **Achievable in full after repair**: nothing in section 2 prevents it;
where `e25a297` breaks it, that is said as a current breach. **Achievable in part**: a part can be met and the rest is
a named, unmet requirement. **Not a breach** is said only where the property was looked at and nothing was found
against it. Each guarantee is also marked **safety** (something false is never said) or **timeliness** (something is
said within a time). The unmet parts are named UM1 to UM6. (U1 to U9 are already the names of tests in
`verify/AMEND16_ADDENDUM_2026-11-20.md`.)

**P1. No run hides another.** Achievable in part.
- Can be met. Safety: a run the courier cannot read, or did not ask for, never ends the reading of other runs as
  done, and never lets the budget read as covered (not so at `e25a297` for runs asked for and not read: D-d).
  Timeliness, conditional: where every GET /run is answered inside the time a pass has, every run that may call for a
  notice is examined in that pass.
- **UM1, every run examined in every pass the witness answers.** Against the powers of section 2 the service can make
  this false by slowing answers or adding runs (section 5). Needed: a witness whose answer time the service does not
  control (a database of its own, so separation of the parties); a bound on the rate of runs; a reading whose cost does
  not grow with the runs in flight. The last two touch the frozen gateway.

**P2. A run that cannot be read stays unresolved and visible.** Achievable in part.
- Can be met. Safety: such a run is never marked done (courier.py 804: done only in EFFECT or NO_EFFECT and not
  UNVERIFIED) and is in the status with since when and why. Its UNREADABLE notice says the outcome is not known.
- **UM2, the notice within the waiting time, whatever the witness does.** The courier makes the UNREADABLE notice
  only at a later pass whose checkpoint and chain were read (courier.py 121-123), and the blocked alarm was missing in
  T2 (section 6, D-a). Needed: an alarm derived from the last positive proof of reading, evaluated at a bounded interval
  that does not wait on any witness answer. This holds only while the courier runs (see UM5).

**P3. The witness down told apart from one run unreadable.** Achievable in part.
- Can be met. Safety: the courier reports which requests were answered and which were not.
- **UM3, the cause.** The service can answer the probe and withhold the run, or the reverse. Needed: a witness whose
  answers the service does not time (as UM1).

**P4. Names refused at the door.** Achievable in full; not a breach so far as tested; it does not depend on time. The rule is
witness_service.py 64-69, used at 135 and 164. Internally tested only.

**P5. The courier's words are the courier's.** Achievable in full after repair; safety; independent of time. **At
`e25a297` it is breached, by the owner's ruling of 21 November: the courier's signed words must be its own true
sentences.**
- **Breach, false provenance (D-b).** Every form-2 notice ends "made by the courier … from what the witness gave it,
  read to decision N". It is signed with "read to decision 0" where the witness has never given the courier anything
  (by test, T1f), and in a pass where the witness gave nothing (T1d).
- **Breach, headlines standing alone, one of them false (D-c).** The explanation line of the notices of INDETERMINATE,
  NO_OUTCOME, UNVERIFIED and REFUNDED is empty. The UNVERIFIED headline, "THE STORED RESULT DOES NOT MATCH THE GATE'S
  SIGNATURE", was signed and receipted for a run that had no stored result at all (by test). The NO_OUTCOME headline
  says a run "was admitted" and is also used for a run whose intent was only accepted (code reading, check_record.py
  204-207; not tested).
- **Not yet confirmed (F5).** The eighth review reported that form-2 notices of earlier forms fail the new checker. If
  so, that breaks "records made before this amendment still verify".
- **Not a breach, so far as tested:** text the service chooses (a run's name, a reason code, a criterion's name and
  units, a detail) was shown as data in every notice looked at; R25, R26 and R30 pass at `e25a297` in development
  runs.

**P6. Coverage confirmed, not assumed.** Achievable in part; safety. No breach of its letter was found; D-d (section 6) bears on it. As written, "watched" holds from a receipted
statement and never lapses.
- **UM4, budgets the courier is not told of.** The courier cannot discover budgets (property 77-78). Needed: a
  reading at the witness that lists them, which touches the gateway.
- **UM5, a courier that is absent is seen.** A courier not running, with malformed own state, or unable to send tells
  the mailbox nothing (A1). Needed: a receiver-side rule that reads the absence of a fresh positive statement as NOT
  COVERED. The candidate form is below; it still needs A5.

**P7. A signed verdict looked at.** Achievable in part, in its "may only add a notice" form; safety. It is asked only of a run
that was read (courier.py 805-817), so its timeliness is P1's.
- **UM6, a verdict the gate signed and the witness recorded stays the verdict.** Not met, by test. This requirement
  now takes in the replacement of section 3: a FAIL that the gate host signed and the witness recorded was replaced by
  a PASS with no notice, in three ways, because any recorded digest is accepted and the result is stored afterwards by
  the client. It holds only from the moment a result is stored as a value. Needed, any of: the courier and the checker
  remarking on two digests for one run (which may only add a notice, and touches no gateway file); the witness
  refusing a second EFFECT report for a run in a final phase; the first recorded digest being the only one believed;
  the verdict bound in the chain at reconcile. The second and fourth touch the frozen gateway. None is proposed here.

**The three states** (property 29-38) stay distinct: the courier blocked or unable to read; the mailbox accepted (a
receipt, and all it means); the engineer acknowledged (nothing in this path shows it). They can be kept apart in words,
safety only. Added here, from the design review: a fourth observation, the courier running and delivering notices but
not reading the budget whole (as in T2), must not read as any of the three.

**The candidate form of the achievable guarantee.** Not adopted, not built, and by the owner's instruction of 21
November not to be settled until the checks have been reviewed: COVERED to decision N when the mailbox holds a
courier-signed statement, receipted within a time limit by the mailbox's clock, that the courier read the budget whole
to N, and holds every notice that reading called for; otherwise NOT COVERED. If it is adopted later, the mailbox or
its operator sets the time limit, on the mailbox's clock. It is a safety statement with no promise of timeliness. It
would meet UM5 at the receiver and the safety parts above. It meets none of UM1 to UM4 or UM6. "Whole" would have to
be defined once (section 6, D-f).

**T1 to T8.** Can still be shown: T3, T4, T5, T6, T7 (as wording) and T8. T1 can be shown against a witness whose
answers fit in the pass; against the powers of section 2 it presupposes UM1. T2's first half (in the status, never
done) can be shown; its second half (the notice after the waiting time) presupposes UM2 and a running courier (UM5).

## 5. Is COVERED operationally achievable under ordinary load without modifying the frozen gateway?

**Verdict, by test: under honest load, yes on this deployment, with a wide margin (PASS for what was measured;
UNPROVEN beyond it). Against a service using the powers of section 2, no: it can keep a budget from being read whole
at will, by two routes now shown, which is safe and operationally weak.**

What was measured, with no change to code (`verify/DIAGNOSTIC_AMEND16_POWERS_2026-11-21.md`, section 6): real runs
through the client and the gate host, the witness read over HTTPS with the courier's certificate, the courier as its
own process with its default settings. "Read whole" below is the eighth form's own ending of a pass with nothing put
off and nothing unread.

| Measured | Result |
|---|---|
| Honest load | 1296 runs over three budgets (996, 150, 150) by four clients in 1509 s; 973 PASS, 323 FAIL; every run reached a final phase |
| GET /run while the load ran | 4543 requests, all answered: median 0.060 s, 99th centile 0.101 s, longest 0.163 s; about 2 KB each |
| GET /run with nothing else running | median 0.038 s, longest 0.101 s; no slowing with the size of the budget |
| Stored result | 1369 to 1404 bytes (the self-test fixture) |
| The courier from nothing, 996-run budget | 98 s, read whole, 996 runs asked for, none put off, 247 FAIL notices accepted; later passes 0.16 s |
| The courier from nothing, three budgets | 120 s for the whole cycle; later cycles 0.24 to 0.31 s |
| The courier while runs were made (531 runs in 6 minutes) | 31 passes, all read whole, exit status 0, 0.3 to 3.2 s each; at most 41 runs asked for in a pass |
| Runs not yet final at any moment under that load | median 2, never more than 4 |
| The whole chain of the 996-run budget | 508 MB in 126 pages, 37 s; one decision grows from 3.8 KB to 127 KB |

What follows for honest load. A pass has 600 s for asking. At the longest GET /run seen under load (0.163 s) that is
about 3,700 runs not yet done; at the median, about 10,000. Honest load here left at most 4. The four conditions of
the first revision can now be answered:

- (i) Runs not yet done, times the time of one GET /run, fits in 600 s: yes, by three orders of magnitude here.
- (ii) Runs that never reach a final phase do not pile up: none arose in 1827 honest runs. How often real operation
  leaves one cannot be measured in a demonstration. Each would cost about 0.04 to 0.06 s at every pass, for ever
  (courier.py 804), so thousands would be needed before a pass stopped being whole.
- (iii) With budgets read in sequence, the time between two looks at one budget stays inside any time limit: a cycle
  over three budgets took 0.3 s once read, and 120 s from nothing.
- (iv) Results of ordinary size: 1.4 KB here. A real engineering check was not measured.

Two costs that honest load does show. Reading a chain from its start grows with the square of a budget's runs, because
every decision carries the state of every run: 508 MB for 996 runs. It is paid once, by a courier that has lost its
state or is new; the time a pass has for asking does not bound it. And a submission slows as a budget fills (1.0 s on
an empty budget, 12 s at the 95th centile near 1000 runs); that is the service's cost, not the courier's.

Against the service. The earlier reasoning stands and is now partly shown. About a dozen runs left CONSUMED for ever,
each answered just inside the 60 s deadline, keep a budget from ever being read whole: eleven are asked for before the
600 s are spent and the twelfth is put off (code reading; the 59 s answer was not staged, a 5 s delay of a chosen
reading was). Holding every free database connection makes every reading fail for as long as the service likes (by
test). Each such run, and the blocked courier, is visible one by one; what is not said at `e25a297` is that the budget
is not being read whole (D-a).

Limits of the measurement. One machine, the loopback interface, half an hour, no fault during the load, the self-test
fixture as the check. A check with a large result or a long run, separate machines, and days of operation are
UNPROVEN. A budget that mostly reads NOT COVERED would be ignored; under honest load here it would not have read so
once.

What would still change the picture: a bound on stored result size, a way to retire abandoned runs, a reading whose
cost does not grow with the budget. Each touches the frozen gateway and would need its necessity named. On this
evidence none is needed for honest load at the sizes measured.

## 6. Ledger

### Confirmed defects of `e25a297` (eight; INCOMPLETE, failed internal review, not declared)

| Id | Defect | Where | How confirmed |
|---|---|---|---|
| D-a | `end_read` clears `unfinished_since`, `blocked_sent`, `failed_sent` for any pass ending 'read', including one that put runs off; `end_blocked` counts from `unfinished_since`. No alarm in T2 (4500 s) | courier.py 1023-1025, 1056-1066 | test and code |
| D-b | The fixed last line of every form-2 notice says "from what the witness gave it, read to decision N"; alarms pass `st.get('seq', 0)`. False where nothing was read (T1f); inexact where the witness gave nothing in that pass (T1d) | check_record.py 353; courier.py 523 | test and code |
| D-c | A trailing comment on INTERRUPTED in `WHY_2` swallowed the entries for INDETERMINATE, NO_OUTCOME, UNVERIFIED, REFUNDED; with `outcome in WHY_2` false their form-2 notices have an empty third line, so the headline stands alone; the UNVERIFIED headline was signed for a run with no stored result. R25, R26, R30 pass with it | check_record.py 303-307, 346 | code reading, and test (the UNVERIFIED notice) |
| D-d | WATCHING is made whenever no run was put off, without regard to runs asked for and not read; its words promise the future ("From that decision on, it makes a notice of each run that calls for one") | courier.py 841; check_record.py 364 | code reading; no test |
| D-e | One clock value for a whole pass over all budgets; a slow budget delays the alarm of the next | courier.py 1258-1259; docstring 107 | code reading |
| D-f | "Complete" has several meanings: ending 'read' (1023), `whole` (750, 831), no run put off for WATCHING (841), the exit status (docstring 46-48). In T2 the status said "the last pass did not complete: 71 runs put off" for the pass that cleared the alarm's count | courier.py as cited; `passes_T2.json` pass 9 | test and code |
| D-g | With the witness stopping at a newly arrived run in every pass (T1b), an older failed run was not noticed in the passes run (to t=1600); the alarm was on time | diagnostic note, T1b | test |
| D-h | Cost, not a wrong statement: a run that never reaches a final phase is asked for at every pass for ever | courier.py 804; T2 | code and test |

The R25, R26 and R30 counts with D-c in place (19 of 19, 28 of 28, 111 of 111) are from three development runs by the
coordinator on `e25a297` on 21 November, 08:15 to 08:20 UTC. Their output is in the session's working files, not in
the repository. They are not official runs.

### Found by the checks of 21 November, outside the courier (not among the eight)

- G-a: a run can carry two gate-signed EFFECT reports with different digests; the witness records the second, and the
  courier and the record's checker believe a result that matches either. With it a FAIL was replaced by a PASS with no
  notice (section 3). In the witness and the store (frozen gateway) and in `verify/check_record.py`. By test.
- G-b: every database role's password is literal text in the repository, the owner's included. The demonstration only.
  Catalogue and repository.
- G-c: no role has a connection limit, and the server has no statement or idle timeout; one role can take every free
  connection, after which the witness's readings fail. By test.
- G-d: every decision of the chain carries the state of every run of its budget, so a chain read from its start grows
  with the square of the runs (508 MB for 996). Measured.

Whether these go into the defect register, and under what numbers, is for the owner. None is repaired or proposed for
repair here.

### Reported by the eighth internal review, not re-confirmed

- F1: the fifth group is never reached while new such runs keep arriving, so a FAIL stands signed as UNREADABLE.
- F2: falls inside the floor delay everything; the stated bound is false.
- F4: the wording of a clock step.
- F5: form-2 notices of earlier forms fail the new checker.

Stated as open in the courier's own docstring, unchanged: a courier whose own state is malformed, that is not running,
or that cannot send tells the mailbox nothing (courier.py 111-112; 1264-1268).

### The alarm diagnostic of 21 November, against the stand-in only

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
- That notification says anything about the truth of a verdict; or that a verdict the gate signed and the witness
  recorded cannot be replaced. It can, until its result is stored as a value (by test).
- That the courier can tell the witness down from one run unreadable as a matter of cause.
- That COVERED is built or adopted: it is a proposal. That a budget can be read whole under honest load may be said
  only with its limits: this deployment, the self-test fixture, half an hour, one machine.
- That the alarm diagnostic's PASS verdicts hold beyond the stand-in. That the service can delay one chosen reading
  through its database role alone: only failing every reading, and a delay by the shared account, were shown.
- That P1 to P7 are met, that Amendment 16 is declared, or that any form is accepted. `e25a297` is INCOMPLETE, failed
  its internal review, and is not declared.
- That the service is confined to the role `plea_local` in the demonstration.
- That anything here is independently validated, or that G2, G5 or G6 is closed.
- That a receipt shows a person read anything, or that the mailbox is independent of the service in the demonstration.

## 8. Rulings, deferrals, and what is open

**Ruled by the owner on 21 November.**

- This draft is held on `diagnostic-amend16-alarm-2026-11-21`. It is not put on `verification-amendment-16`, which
  stays at `e25a297`. No code change, no redesign of the reading loop, no model of an invariant, no declaration.
- The false provenance sentence and the headlines standing alone are current breaches of P5 (section 4).
- `e25a297` is described only as INCOMPLETE, failed internal review, not declared, with its eight confirmed defects
  attached.
- If COVERED / NOT COVERED is adopted later, the mailbox or its operator sets the time limit, on the mailbox's clock.

**Deferred by the owner until the checks of 21 November have been reviewed.**

- Locking the table of section 2 as the fixed model.
- Whether COVERED / NOT COVERED is accepted as the form of the achievable guarantee.
- How the eighth form is to be dealt with beyond the description above, and whether and when this draft goes beside
  the property file.

**Open, and made sharper by the checks.**

1. Whether the model takes the service to hold `plea_local` and no other role. The tests confine that role; the
   demonstration does not confine the service to it.
2. Whether the replacement of a verdict before its result is stored (UM6, G-a) is accepted as a named, unmet
   requirement of this amendment, or is to be taken up first. It is the one finding here that turns a signed FAIL into
   silence.
3. Whether the split of section 4 is accepted with UM1 to UM6, P5 standing as breached.
4. Whether G-a to G-d go into the defect register.
5. Whether a measurement with a real engineering check, on separate machines or over a longer time, is wanted before
   anything is said about honest load beyond this deployment.

Nothing in this draft proposes that implementation begin.
