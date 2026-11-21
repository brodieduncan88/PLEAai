# Amendment 16: threat-model addendum. A conditional security contract

21 November 2026. Private working material. Internal work under the owner's direction. It is not an independent
validation and it is not a declaration. No code is changed by it or with it. It documents a conditional security
contract: what the notification path may promise, against which powers of the service, and only where stated
preconditions of the deployment hold. The owner approved finalising it on 21 November, subject to the requirements it
records.

It does not change `verify/AMEND16_PROPERTY_2026-11-20.md`. P1 to P7 and T1 to T8 stand as written there. Where this
addendum says a part cannot be met, that part stays a requirement, unmet. It does not change
`verify/AMEND16_ADDENDUM_2026-11-20.md` either.

**The eighth form of the courier, `e25a297`, is INCOMPLETE. It failed its eighth internal review. It is not declared.
Its eight confirmed defects are listed in section 9 and go with any mention of it.** Nothing here is independently
validated. The proposed guarantee of section 7 is not built. Release gates G2, G5 and G6 stay implemented and
internally tested, with open obligations. One machine, one kernel, a database shared by the witness and the service,
and no real separation of the parties remain material.

Citations are to the tree at `e25a297`. "Code reading" means the cited lines were read. "By test" means a diagnostic
of 21 November named in section 12; those ran against real deployments on fresh databases, except the alarm
diagnostic, which ran against a stand-in witness. All of it is the work of the code's own side, with no planted-defect
pass on the harnesses.

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

## 2. The service's powers (locked)

This table is the fixed model of the service for Amendment 16, by the owner's decision of 21 November. It uses the
authority of the role `plea_local` as it was read from the database and tried, and it holds under the preconditions of
section 3. "Still promised" is what notification can say against a power once the defects of section 9 are repaired;
at `e25a297` some of it is not met. A later finding that needs a power not in this table is a request to change the
model.

| Power | Where it comes from | Granted by the property file | Lets it do | Still promised against it |
|---|---|---|---|---|
| Run names and every field of a result | property 21-24 | yes | put text of its choosing in a notice | shown as data only (P5) |
| Result size | property 22-23; the courier reads to 32 MiB (courier.py 178) | yes | make one GET /run slow or unreadable | that run unread and visible (P2); no other run hidden by it |
| Which budgets exist | property 23 | yes | create a budget the courier is not configured for | never reported as covered (P6) |
| The gate's key | property 21 | yes | sign a report whose result says PASS for a run that failed, and send the witness that report alone | nothing about the truth of a verdict (section 5; UM6 a) |
| The database role `plea_local`, and no other | property 21 says "a database role"; this is the role the client is configured with (deploy.py 35, 136). Grants read from the catalogue; changes tried, by test | yes; named here | read every table of every budget; store a result through `plea_put_result`; write its own operations through `plea_write`; hold connections; take advisory locks | it cannot change `results`, `evidence`, `decisions`, `attempts` or `roots` directly (20 changes refused), cannot write a RECONCILE, cannot remove a recorded report, and cannot replace a result stored as a value |
| Replacing a verdict before it is committed (two signed digests) | the gate's key, the client's certificate and `plea_local` together; by test | follows from what is granted; named here | after the gate host signed FAIL and the witness recorded it: withhold the result or store one marked 'unknown', have a second report recorded over a PASS result, store the PASS. No notice at `e25a297` | a FAIL stored as a value stays and its notice is made (by test). Before that: both reports remain in the witness's reading, so the conflict can be told; it is not told at `e25a297` (UM6 b) |
| Failing the witness's readings by taking every free database connection | `plea_local` has no connection limit; by test (97 connections, every reading failed) | no; named here | make every reading fail for as long as it likes | the courier blocked, never a budget read as covered. Residual risk R1 (section 3) |
| Slowing or failing readings through the shared database server | the shared database, property 26; load measured, deliberate interference beyond connections not tested | no; named here | slow readings by load, large results or long work on the same server | the same. Residual risk R2 (section 3) |
| The rate at which runs are added | front door and gate, property 21; rate not stated | no; named here | add runs faster than a pass can ask for them | shown, not repaired (courier.py 103-104) |
| Runs that never finish | follows from holding the gate; not stated | no; named here | leave runs CONSUMED or UNVERIFIED for ever; each costs one GET /run at every pass (courier.py 403, 804) | each listed; NO_OUTCOME or UNVERIFIED notice after the waiting time if read |

| Not a power of the service under this contract | Why | Where the demonstration stands |
|---|---|---|
| Any other database role, the owner's above all | excluded by precondition DP1 | not excluded: every role's password is in the repository |
| Stopping, delaying, reading or writing the witness's process, keys or files | excluded by precondition DP2 | not excluded: one operating-system account runs everything; a chosen reading was delayed 5.04 s by it |
| Rewriting the chain | out of scope, property 27 | follows from the owner's role, so see DP1 |
| Holding the witness's, the courier's or the mailbox's key | these are trusted, property 18-19 | their keys are made and kept by the one account (deploy.py 13-16) |

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

## 3. Deployment preconditions, and where the demonstration stands

The contract is conditional. Sections 5 to 7 hold only in a deployment where all of the following are so. They are
required by the owner's decision of 21 November. None is described here as satisfied unless the table below says so.

- **DP1. No database-owner credential is accessible to the service.** Nor the witness's role, nor the control plane's.
  The service holds `plea_local` and nothing else.
- **DP2. The service and the witness run under separate operating-system identities.** Neither can signal, stop, read
  or write the other's process, keys or files. By A1 and A2 (section 4) the same is needed of the courier and of the
  mailbox.
- **DP3. The effective database permissions are those of section 2.** They are read from the catalogue of the deployed
  database, not assumed from the code: for `plea_local`, SELECT on the tables, INSERT on `receipts`, EXECUTE on
  `plea_write` and `plea_put_result`, temporary tables, and nothing else that changes an authoritative table.
- **DP4. Connection exhaustion and interference through the shared database are either prevented or carried as
  residual risks.** Prevention would be a connection limit for each role, connections kept for the witness, timeouts,
  or a database of the witness's own. None of these exists, so both are carried as residual risks:

  - **R1, connection exhaustion.** One role can take every free connection. The witness's readings then fail and the
    courier is blocked (by test).
  - **R2, interference through the shared database.** Load, large results or long work on the same server can slow or
    fail the witness's readings. Measured only under honest load (section 8).

R1 and R2 are risks to availability. They can keep a budget from being read, and so NOT COVERED, for as long as the
service likes. They cannot make a budget read as COVERED.

**Where the current demonstration stands, 21 November 2026.**

| Precondition | Standing | Evidence |
|---|---|---|
| DP1 | **Not satisfied.** The passwords of all four database roles, the owner's included, are plaintext in the repository. This is an outstanding security defect (S-2, section 9). It is not an acceptable implementation of credential separation | `roles.txt` (23 places); with the owner's password a recorded gate report was removed (by test) |
| DP2 | **Not satisfied.** One operating-system account runs the witness, the gate host, the mailbox, the courier and the client | deploy.py 11-16; the witness process was stopped and continued by that account, delaying a chosen reading 5.04 s (by test) |
| DP3 | Consistent for the three roles as installed on a fresh database. In effect only where DP1 holds, which it does not | the catalogue; 20 changes refused for `plea_local`; removal and change of a report refused for all three roles (by test) |
| DP4 | No protection exists. R1 and R2 are carried as residual risks | no connection limit on any role, no statement or idle timeout; 97 connections taken by `plea_local`, every reading failed (by test) |

So in the current demonstration the contract's preconditions are not met, and the conditional guarantee of section 7
is not in force there. What the tests show is what the role `plea_local` can do when it is the only credential used.

## 4. The other parties: named assumptions

- **A1. The courier.** Honest; its key secret; its configuration its own (property 18). It may be killed and restarted.
  While it is not running, or its own state is malformed, or it cannot send, it tells the mailbox nothing
  (courier.py 111-112; budget skipped at 1264-1268).
- **A2. The mailbox.** Honest; its key its own (property 19); it stores what it receipts. Its clock is assumed to be
  its own; the waiting limit of section 7 is set by the mailbox or its operator on that clock. The mailbox's code was
  not examined for this addendum.
- **A3. The channel.** Courier to mailbox delivers when both are up. On one machine this is assumed, not shown.
- **A4. The clocks.** The courier's clock is its own. It is read once per pass, before the loop over budgets
  (courier.py 1258-1259); budgets are read one after another (courier.py 107). The statement of section 7 is judged
  by the mailbox's clock (A2), not the courier's.
- **A5. The reader.** The mailbox is passive storage. Someone or something must read it for any notice, or any
  absence of one, to reach a person. Nothing in this path shows that a person read anything (property 34-35).

## 5. What notification covers: committed verdicts only

**Notification covers committed verdicts only.** A service holding the gate's key can sign an EFFECT report for a
result that says PASS for a run that failed. The courier has no card, and P7 compares only a result's own numbers with
its own stated limits (property 80-82). So notification can say that a verdict the service committed to reached the
mailbox, or did not. It can say nothing about whether a verdict is true.

**When a verdict is committed, by test.** A verdict is committed when a result that hashes to a recorded gate-signed
report has been stored as a value, and not before.

- After that point it stayed. With a FAIL stored as a value, a second report over a PASS result was recorded by the
  witness (DUPLICATE / VERDICT_RETRY, with the report), `plea_put_result` changed nothing, the courier read FAIL and
  the mailbox accepted its notice.
- Before that point it did not. The gate host signed FAIL and the witness recorded it. The service then withheld the
  result, or stored one marked 'unknown'; had a second report recorded over a PASS result; and stored the PASS. The
  courier read PASS and, with the 900 s waiting time, made no notice before or after. Where the forged PASS named the
  same design with numbers that meet the limit, the record verified.
- A stored result that hashes to no recorded digest reads as UNVERIFIED (check_record.py 200-202), a notice after the
  waiting time if the run is read. A client without the gate's key can only withhold, which ends there.

**What the witness's existing reading shows, by test.**

- **Both conflicting reports are exposed.** After a replacement, GET /run with the courier's certificate gives both
  EFFECT reports of the run, with their two digests, each signed by the gate's key for that budget, run and nonce. The
  chain gives two RECONCILE decisions for the run (APPLIED / VERDICT_RECORDED, then DUPLICATE / VERDICT_RETRY), and
  each report sits at one of them. The record carries both reports too.
- **The conflict can be identified by the courier and by the record's checker with no change to the gateway. Neither
  identifies it today.** "Two different digests among the genuine EFFECT reports of one run" is true of the replaced
  run from the courier's reading and from the record. An honest repeat of a report carries the same digest and does
  not look like a conflict. At `e25a297` the courier made no notice and the record verified.
- **Neither report can be concealed or replaced by a role the store grants.** DELETE and UPDATE of a recorded report
  were refused for `plea_local`, `plea_witness` and `plea_control`. And for the courier to read PASS the PASS digest
  must already be recorded, so at that reading both reports are in the answer. A reader that looked for two digests
  could not miss a replacement.
- **With the owner's password a report can be concealed.** The first report was deleted as the owner. The reading then
  gave one report and the conflict could not be told from the reports; the chain still held two RECONCILE decisions
  against one report, and since the chain does not bind a digest, which one was removed cannot be recovered. This is
  the limit DP1 answers.
- **A forgery made before the witness sees anything cannot be identified at all.** If the service sends the witness
  only its own report, there is one report and one decision. No reading and no check in this path sees it.

**Detecting a conflict is not proving a verdict.** Two genuine reports with different digests show that the gate's key
signed two different results for one run. They do not show which result is true, nor that the first recorded is: the
same key signed both, and the first can itself be the forgery. A notice of such a conflict could say only that the run
carries two signed results.

**Limits.** Each case was made once, on one deployment, by the harness's author acting as the service. How long the
service has to replace a verdict was not measured.

## 6. P1 to P7: what is met, what is achievable after repair, and what stays unmet

Each property is given its standing in plain words. **Met by `e25a297` in development runs** means internally tested
and no more: `e25a297` is not declared and nothing is independently validated. **Achievable after repair** means
nothing in section 2 prevents it and `e25a297` breaks it now; that is not the same as satisfied. **Achievable in
part** means a part can be met and the rest is a named, unmet requirement, UM1 to UM6, which stays a requirement. Each
guarantee is also marked **safety** (something false is never said) or **timeliness** (something is said within a
time). (U1 to U9 are already the names of tests in `verify/AMEND16_ADDENDUM_2026-11-20.md`.)

**P1. No run hides another.** Achievable in part. Its safety part is achievable after repair and is broken at `e25a297` (D-d).
- Can be met. Safety: a run the courier cannot read, or did not ask for, never ends the reading of other runs as
  done, and never lets the budget read as covered (not so at `e25a297` for runs asked for and not read: D-d).
  Timeliness, conditional: where every GET /run is answered inside the time a pass has, every run that may call for a
  notice is examined in that pass.
- **UM1, every run examined in every pass the witness answers.** Against the powers of section 2 the service can make
  this false by slowing answers or adding runs (section 8). Needed: a witness whose answer time the service does not
  control (a database of its own, so separation of the parties); a bound on the rate of runs; a reading whose cost does
  not grow with the runs in flight. The last two touch the frozen gateway.

**P2. A run that cannot be read stays unresolved and visible.** Achievable in part. Its safety part is met by `e25a297` in development runs.
- Can be met. Safety: such a run is never marked done (courier.py 804: done only in EFFECT or NO_EFFECT and not
  UNVERIFIED) and is in the status with since when and why. Its UNREADABLE notice says the outcome is not known.
- **UM2, the notice within the waiting time, whatever the witness does.** The courier makes the UNREADABLE notice
  only at a later pass whose checkpoint and chain were read (courier.py 121-123), and the blocked alarm was missing in
  T2 (section 9, D-a). Needed: an alarm derived from the last positive proof of reading, evaluated at a bounded interval
  that does not wait on any witness answer. This holds only while the courier runs (see UM5).

**P3. The witness down told apart from one run unreadable.** Achievable in part: what was answered can be reported, the cause cannot.
- Can be met. Safety: the courier reports which requests were answered and which were not.
- **UM3, the cause.** The service can answer the probe and withhold the run, or the reverse. Needed: a witness whose
  answers the service does not time (as UM1).

**P4. Names refused at the door.** Met by `e25a297` in development runs; no breach found; it does not depend on time.
The rule is witness_service.py 64-69, used at 135 and 164. Internally tested only, not declared.

**P5. The courier's words are the courier's.** Achievable in full after repair; not satisfied now; safety; independent
of time. **At `e25a297` it is breached, by the owner's ruling of 21 November: the courier's signed words must be its
own true sentences.**
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

**P6. Coverage confirmed, not assumed.** Achievable in part; safety. Its letter is met by `e25a297` in development
runs; D-d (section 9) bears on it. As written, "watched" holds from a receipted statement and never lapses.
- **UM4, budgets the courier is not told of.** The courier cannot discover budgets (property 77-78). Needed: a
  reading at the witness that lists them, which touches the gateway.
- **UM5, a courier that is absent is seen.** A courier not running, with malformed own state, or unable to send tells
  the mailbox nothing (A1). Needed: a receiver-side rule that reads the absence of a fresh positive statement as NOT
  COVERED. The proposed guarantee of section 7 does this; it still needs A5.

**P7. A signed verdict looked at.** Achievable in part, in its "may only add a notice" form, which `e25a297` has in
development runs; safety. It is asked only of a run that was read (courier.py 805-817), so its timeliness is P1's.
- **UM6, a verdict stays the verdict.** Not met. It has three limits, kept apart here and in section 5:
  - **(a) Forgery before the witness sees anything.** A service with the gate's key can send the witness only a report
    of its own. The witness then holds one report and one decision, and nothing in this path can tell (by test).
    Needed: a gate whose key the service does not hold. That is outside this amendment.
  - **(b) Replacement after the witness has recorded a report and before a result is stored as a value.** A second
    report is recorded and any recorded digest is believed, so a FAIL became a PASS with no notice (by test, three
    ways). Both reports are then in the witness's reading and in the record, and the conflict can be told from them
    with no change to the gateway. Nothing tells it at `e25a297`. Telling it shows that the gate's key signed two
    results for one run; it does not show which is true.
  - **(c) The store.** A result stored as a value is not replaced by `plea_local` (by test): from that moment the
    verdict stays, where DP1 and DP3 hold. A result marked 'unknown' is replaced, and which value is stored first is
    the client's choice. No role the store grants can remove a recorded report; the owner can (by test), which is why
    DP1 is a precondition.
  Needed for (b), any of: the courier and the record's checker remarking on two digests for one run (which may only
  add a notice, and touches no gateway file); the witness refusing a second EFFECT report for a run in a final phase;
  only the first recorded digest being believed; the verdict bound in the chain at reconcile. The second and fourth
  touch the frozen gateway. None is made or begun here.

**The three states** (property 29-38) stay distinct: the courier blocked or unable to read; the mailbox accepted (a
receipt, and all it means); the engineer acknowledged (nothing in this path shows it). They can be kept apart in words,
safety only. Added here, from the design review: a fourth observation, the courier running and delivering notices but
not reading the budget whole (as in T2), must not read as any of the three.

**T1 to T8.** Can still be shown: T3, T4, T5, T6, T7 (as wording) and T8. T1 can be shown against a witness whose
answers fit in the pass; against the powers of section 2 it presupposes UM1. T2's first half (in the status, never
done) can be shown; its second half (the notice after the waiting time) presupposes UM2 and a running courier (UM5).

## 7. The proposed conditional guarantee: COVERED / NOT COVERED

By the owner's decision of 21 November this is adopted as the **proposed conditional guarantee of Amendment 16**. It
is not built. It is not a validated or production property. `e25a297` does not have it: its statement of coverage is
made once, never lapses, and is made with runs asked for and not read (D-d). It holds only under sections 2 to 4.

**Definition.** For a budget B, a mailbox M and a time t on M's clock, B is **COVERED to decision N** if and only if M
holds a coverage statement signed by the courier's key, which M receipted at a time r with t − r no more than the
waiting limit, and every clause below is true of one reading by the courier that the statement names. Otherwise B is
**NOT COVERED**.

- **O1, the checkpoint.** In that reading the courier received a checkpoint for B, signed by a witness key it was
  given, bearing a nonce the courier made for that reading, at decision N.
- **O2, the chain.** In that reading the courier received every decision after the last it had verified, up to N, and
  verified them to the checkpoint's head.
- **O3, the runs.** For every run the chain at N shows in a phase that may call for a notice, one of two things is so.
  Either, in that reading and after the checkpoint of O1, the courier received the witness's answer for the run,
  verified it, and worked out the run's outcome from that answer. Or the run was final already: in an earlier reading,
  which the statement or the courier's record names, the courier received and verified the witness's answer for it in
  a final phase with a result stored as a value, and worked out its outcome then.
- **O4, the notices.** The statement identifies every notice that the outcomes of O3 call for, and M holds each of
  them.

**The observation boundary.** Every clause is something the courier actually received from the witness and verified,
at a named decision. Nothing is covered by having been asked for. A run asked for and not answered, a run answered
with something that cannot be read or verified, a run not asked for, and a run that is not final and whose outcome is
carried over from an earlier reading, each make the reading not whole, and no coverage statement may be made for it.
The statement speaks of the past, to decision N. It says nothing of decisions after N. The second half of O3 rests on
a stored value staying stored (UM6 c), so on DP1 and DP3.

**The waiting limit.** The mailbox or its operator sets it, on the mailbox's clock, before acceptance testing. The
measurements of section 8 inform that choice and do not make it.

**What the two words mean, and do not.**

- COVERED means: the failures the service had committed to, as the courier observed them up to decision N, have their
  notices in the mailbox, and that observation is no older than the waiting limit. It does not mean that every verdict
  is PASS, that any verdict is true (section 5), that nothing has happened since N, or that anyone has read the
  mailbox.
- **NOT COVERED means only that the mailbox holds no fresh proof that the budget was read whole.** It never means that
  a run failed, that any underlying verdict is FAIL, or that the service misbehaved. Its causes include a courier that
  is not running, a mailbox that could not be reached, a witness that was slow or failed, and load. It is the default,
  and needs nothing to be sent in order to be true.
- It is a safety statement. It promises no time by which a budget becomes COVERED, and none by which a run's notice
  arrives.

**What it would and would not answer.** It would answer UM5 at the receiver (a courier that is absent is seen, by
whoever reads the mailbox: A5) and the safety parts of P1, P2 and P6. It answers none of UM1 to UM4 and none of UM6.

## 8. The measured operational envelope

Measured on 21 November, with no change to code: real runs through the client and the gate host, the witness read over
HTTPS with the courier's certificate, the courier as its own process with its default settings. "Read whole" below is
the eighth form's own ending of a pass with nothing put off and nothing unread. That is narrower evidence than the
definition of section 7 asks for, and it comes from a form that is INCOMPLETE.

| Measured | Result |
|---|---|
| Whole-budget passes while honest runs were made by four clients at once (531 runs in 6 minutes) | 31 of 31 read whole |
| Time of each of those passes | 0.3 to 3.2 s |
| Cold start: the courier from nothing over a budget of 996 runs | 98 s, read whole (120 s over three budgets, 1296 runs) |
| Stored result | about 1.4 KB (1369 to 1404 bytes); the self-test fixture |
| Runs left unfinished | none: all 1827 runs of the two measurements reached a final phase; at most 4 in flight at any second |
| The chain of the 996-run budget, read from its start | 508 MB in 126 pages, 37 s |
| One reading of a run (GET /run) under that load | median 0.060 s, longest 0.163 s, about 2 KB |

**A limitation the measurement identified: quadratic growth.** Every decision of a chain carries the state of every
run of its budget, so a decision grew from 3.8 KB to 127 KB over 996 runs, and the cost of reading a chain from its
start grows with the square of the budget's runs. It is paid by a courier that is new or has lost its state, and the
time a pass has for asking does not bound it.

**No extrapolation.** These figures are an envelope, not a capacity. They were taken on one machine, over the loopback
interface, in half an hour, with no fault during the load, with the self-test fixture as the check, on budgets of at
most 1000 runs. They do not show what happens with a real engineering check, a large result, a long run, separate
machines, days of operation, a larger budget, or runs that never finish, whose rate in real operation is not known.
They support no claim of unlimited capacity and no general promise that a budget will become COVERED.

## 9. Defect register

### 9.1 The eight confirmed defects of the courier at `e25a297` (INCOMPLETE, failed internal review, not declared)

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

### 9.2 Substrate, deployment and gateway-adjacent findings (outside the courier; not among the eight)

| Id | Finding | Where | How confirmed |
|---|---|---|---|
| S-1 | Silent replacement of a verdict by a second signed digest. The witness records a second EFFECT report for a run; the courier and the record's checker believe a result that matches any recorded digest; a FAIL was replaced by a PASS with no notice and the record verified | witness and store (frozen gateway); `verify/check_record.py` 188-203 | by test, three ways; both reports remain readable |
| S-2 | Plaintext database role passwords. The passwords of all four roles, the owner's included, are literal text in the repository. An outstanding security defect; DP1 is not satisfied | 23 places listed in `roles.txt` | catalogue and repository; the owner's password used to remove a recorded report |
| S-3 | Connection exhaustion affecting the witness. No role has a connection limit and the server has no statement or idle timeout; one role took every free connection and the witness's readings failed | database configuration and role settings | by test (97 connections) |
| S-4 | Quadratic cold-start growth of the chain. Every decision carries the state of every run of its budget: 508 MB for 996 runs | the store's record of a decision (frozen gateway) | measured |

None of these is repaired, and no repair is made or begun here. S-1 and S-4 lie in or beside the frozen gateway; a
change there would need its necessity named in a later amendment.

### 9.3 Current breaches of P5

The false provenance sentence (D-b) and the headlines standing alone, one of them shown false of its run (D-c), are
current breaches of P5, by the owner's ruling. P5 is achievable in full after repair. It is not satisfied at
`e25a297`. Section 6 gives each breach.

### 9.4 Reported by the eighth internal review, not re-confirmed

- F1: the fifth group is never reached while new such runs keep arriving, so a FAIL stands signed as UNREADABLE.
- F2: falls inside the floor delay everything; the stated bound is false.
- F4: the wording of a clock step.
- F5: form-2 notices of earlier forms fail the new checker.

Stated as open in the courier's own docstring, unchanged: a courier whose own state is malformed, that is not running,
or that cannot send tells the mailbox nothing (courier.py 111-112; 1264-1268).

### 9.5 The alarm diagnostic, against the stand-in only

Witness stopping and resuming in mid-pass at every pass, or answering nothing: one signed COURIER_BLOCKED at the first
pass at or after 900 s (0 s late; 100 s late when killed before the save), durable through a mailbox outage and a kill:
PASS against the stand-in. T2: no alarm in 4500 s; failure notices made 2600 s and 3300 s after the runs could first
be read: FAIL. T1f, provenance: FAIL. Against the deployment: UNPROVEN.

### 9.6 The corrected planted-defect pass figures

The final planted-defect pass of the fourth form, on `769f6e4`. Result file `mutants5_result.json` in the session's
working files, not in the repository, sha256 beginning `f16bd4e255ec5e4a`; 104 entries. The control passed (R26 27
checks, R30 67 checks, none false). Of 103 planted defects: **98** caught by a check that failed; **4** made both tests
fail to finish within 600 s with no check failing ("the read is not bounded"; "F3: the reader neither closed nor
timed"; "F3: the reader does not look at the deadline"; "G5: the error body read whole, with no deadline"), counted
apart and not as caught by the amendment's own rule; **1** missed ("G1d: a pass that put runs off exits 0", judged
equivalent by the implementer). These counts were made again from the file for this addendum and agree.

It was earlier reported as "102 of 103 caught": to the owner (corrected in the audit of 20 November), in the
development log, and in the design review's section 7. 98 / 4 / 1 is the count. Other passes were not recounted.

A clean planted-defect pass measures the tests against the code, not the code against the property. That form then
failed review.

## 10. What may not be claimed

- That a failed run is notified within any time, or within the pass.
- That COURIER_BLOCKED is always made within the waiting time. The alarm diagnostic's T2 shows it is not.
- That the absence of an alarm means a budget is being read, or that CONFIRMED means it is watched now.
- That every notice was made "from what the witness gave it", or that the notices of INDETERMINATE, NO_OUTCOME,
  UNVERIFIED and REFUNDED carry their explanation.
- That notification says anything about the truth of a verdict; or that a verdict the gate signed and the witness
  recorded cannot be replaced. It can, until its result is stored as a value.
- That a conflict between two signed reports is detected. It can be told from what the witness gives; nothing tells
  it. And telling it would not show which verdict is true.
- That COVERED / NOT COVERED is built, validated or in force. It is a proposed conditional guarantee, and its
  preconditions are not met by the demonstration.
- That NOT COVERED means a verdict is FAIL, or that COVERED means a verdict is PASS or true.
- That the deployment preconditions DP1 and DP2 are satisfied, or that the service is confined to the role
  `plea_local` in the demonstration.
- That a budget can be read whole under load beyond the envelope of section 8, or that the envelope is a capacity.
- That the service can delay one chosen reading through its database role alone: failing every reading, and a delay by
  the shared account, are what was shown.
- That the alarm diagnostic's PASS verdicts hold beyond the stand-in.
- That P1 to P7 are met, that Amendment 16 is declared, or that any form is accepted. `e25a297` is INCOMPLETE, failed
  its internal review, and is not declared.
- That anything here is independently validated, or that G2, G5 or G6 is closed.
- That a receipt shows a person read anything, or that the mailbox is independent of the service in the demonstration.

## 11. Unresolved claims, and what is not decided here

Each of these is open. None is settled by this addendum.

1. DP1 and DP2 are not satisfied by the demonstration, so nothing in sections 5 to 7 has been shown in a deployment
    that meets the contract. S-2 is outstanding.
2. The proposed guarantee is not built. "Read whole" in the measurements is the eighth form's own ending, not the
    definition of section 7.
3. The eighth review's F1, F2, F4 and F5 are not re-confirmed.
4. How long the service has to replace a verdict before a courier's waiting time was not measured. The replacement was
    made within seconds.
5. Delaying one chosen reading through the database role alone was not shown; nor was an answer held to just inside
    the 60 s deadline. R2 was not tested beyond honest load and R1.
6. The envelope of section 8 is one machine, half an hour, the self-test fixture. A real check, separate machines, a
    longer time, and the rate of runs that never finish are not measured.
7. The mailbox's code and clock (A2) and the channel to it (A3) were not examined.
8. The NO_OUTCOME headline's inexactness is from code reading only.
9. No planted-defect pass was made on any diagnostic harness, and the harnesses' author acted as the service. Planted-
    defect passes other than the one recounted in section 9.6 were not recounted.
10. Whether S-1 to S-4 are entered in the project's defect register outside this repository, and under what numbers,
    is the owner's.
11. What is done about `e25a297`, and whether any implementation follows, is not decided here. Nothing here proposes
    that implementation begin.

## 12. Source evidence

All on the branch `diagnostic-amend16-alarm-2026-11-21` of the same repository, head `1fc9046`. Harnesses and their
kept results are under `tests/diag_amend16_alarm/` and `tests/diag_amend16_powers/` there. They are not on this
branch.

| What | File on that branch | Commit |
|---|---|---|
| The alarm when the witness stops and resumes (stand-in witness) | `verify/DIAGNOSTIC_AMEND16_ALARM_2026-11-21.md` | `9d30f79` |
| The design-only architectural review, with the coordinator's notes | `verify/DESIGN_REVIEW_AMEND16_2026-11-21.md` | `d10c94c`, `7e31b43` |
| The role's grants, commitment of a verdict, two digests, timing, honest load | `verify/DIAGNOSTIC_AMEND16_POWERS_2026-11-21.md` | `1313dc9` |
| What the witness's reading shows of a replaced verdict | `verify/DIAGNOSTIC_AMEND16_VISIBILITY_2026-11-21.md` | `1fc9046` |
| The drafts of this addendum (first and second revision) | `verify/AMEND16_THREAT_MODEL_ADDENDUM_DRAFT_2026-11-21.md` | `4f91f11`, `1313dc9` |

The databases used were made fresh for each check and are not kept as evidence; the results are the files named above.
The development log of the eight forms, and the result file recounted in section 9.6, are in the session's working
files and not in the repository.
