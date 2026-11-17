# Amendment 8: declaration before the official test runs

17 November 2026. Private working material.

This file is committed before the official runs of `tests/verify_tests.py` and `tests/verify_front_tests.py` on the branch
`verification-amendment-8`. It fixes the changed code, states what each test is expected to show, and records what was done
in development. Each official run is made once after this commit and its first result is kept, pass or fail. A later
correction would be a separate, dated amendment. Times are UTC.

## Why declared files are changed

Amendment 7 repaired five defects of the register that share one failure: a failure the engineer cannot see. It left two of
them partly silent, and said so under "What stays open". On 17 November the owner set the order of the remaining work: first
the checks that need no redesign and remove a silent case before any run (D3), then the one defect that can silence every job
at once (D1). The two that need a second channel to the engineer (D2 and D11) are not in this amendment.

- **D3** (delivery), the register's words: "With the console and the gate under two accounts, the inbox the console makes is
  the console's. If the gate cannot write in it, a failing run stops with no verdict and no notice. This is the first step of
  separation, not damage." After Amendment 7 the run no longer stops: the verdict is returned and the notice is kept in the
  service's own store. What stayed silent: nothing checked, when the gate started or when a job was enrolled, that the gate
  could write the inbox, so the fault was found at the first failure and not before; and an error when the gate claimed an
  inbox at start was swallowed.
- **D1** (front door), the register's words: "Every accepted design, repeats included, is appended to a journal with no size
  limit (front_door.py, _submit()). One job certificate, at the pace allowed, can add about 3 to 8 GB a day. A full disk then
  stops notices for every job (D2)." After Amendment 7 the journal has a size limit and the disk keeps room for notices. What
  stayed wrong: the limit was shared, so one job could fill the journal and every job was then refused; and the refusal went
  only to the caller, so the engineer was not told.

## What is changed, and what is fixed

**The gate proves that it can deliver (D3).** The gate's tool shows that it can write a baseline's inbox by doing it: it writes
a file of 4 KiB there, has it put on the disk, and removes it. It records what it found, with the time at which it had tried,
in `delivery/<full hash>.json` in the service's home, readable by any account. It does this when it starts; on every run; and
on a look of its own, every second, for a baseline that has no good proof, and again for each good proof after 30 seconds. It
does it for every baseline whose notices go to an engineer's inbox: each baseline folder it holds, and each baseline whose
folder is gone and whose inbox still holds its hash (Amendment 6). A proof is read as PROVEN; as NOT_WRITABLE; as STALE when it
is more than 120 seconds old or dated further ahead than that; and as UNPROVEN when there is none that can be read for the
exact hash with a time that is a number. The look cannot be switched off, and a good proof is always made again within a third
of the time for which it stays good: while a proof is not good no run is admitted, so only the look can make it good again.

Four things keep the proof honest. When the tool cannot write an inbox, or cannot record a proof, it says so on its error
output, and again when it is put right. A proof that cannot be recorded takes the one before it off the file, so the state
does not stay good by default. A clock put back does not put a proof off. And nothing the proof does can reach a run: an
error in it, or an error output that fails or is closed, is taken where it happens.

**Who makes an inbox.** The console makes it, a moment after the baseline's folder. The tool's look therefore leaves a
baseline which has no inbox yet, and whose folder is dated less than 10 seconds from now, either way, for its next look; after
that it makes the inbox itself, as it does for a baseline made before Amendment 6.

**What a killed process leaves.** As the tool starts, it takes away its own temporary files that a process killed part-way left
more than a minute before: in an inbox, in a folder of notices that are no engineer's, in the store and in the folder of
proofs. It takes only a plain file whose whole name is one the service gives: not a folder or a link, and not a file of
anyone else's whose name begins the same way.

**A job is opened only on a proven inbox (D3).** `front_ctl.py enrol` and `rebind` wait, 15 seconds unless told otherwise,
for the proof of the baseline the job is to be bound to, and refuse if it is not good. Nothing is changed by a refusal: no
certificate is issued, no binding is written, no folder is made, no line is added to the log of enrolments. With the console
and the gate under two accounts, an inbox the gate cannot write is therefore found by the engineer, at enrolment, and not by a
failure.

**A new run is admitted only on a proven inbox (D3).** The front door refuses a new run, before it is journaled, run or
counted, with 503 `DELIVERY_UNPROVEN`, while the proof for the job's baseline is not good, and says why in the service's own
words. A design whose run is finished (PASS, FAIL, UNKNOWN or INTERRUPTED) is still answered: asking again runs nothing. A run
that an earlier request began and that has no outcome yet is not let through, because asking again could make it. The refusal
does not deny that run: it says that the run is on the record with no verdict yet and is not taken further, and that this
request ran nothing. If the runs cannot be read, the design is not let through, and the refusal says only that this request ran
nothing.

**The engineer is told of that refusal (D3).** One notice on the day for each reason, named `DELIVERY_UNPROVEN_<date>_<reason>`,
the reason being the state of the proof (UNPROVEN, STALE or NOT_WRITABLE). The front door writes it: to the inbox if the front
door can write it, and otherwise to the service's own store, which the console lists. The caller is told whether the engineer
could be sent it. The engineer's console (`verify_ctl.py status`) shows the state of the proof, with its time, or says that
delivery is not proven and that new runs are refused.

**Each baseline has its own share of the journal (D1).** The front door counts the bytes of the journal that hold each
baseline's designs: from the journal when the process first needs them, in step as it writes, and again whenever the journal
is not the size the process left it, as when an operator has made room in it. A baseline whose designs would pass
`journal_share_bytes` (64 MiB unless set with `--journal-share-bytes`) is refused with 507 `STORAGE_FULL`, saying that the
baseline has used its share. Other baselines are not affected. The journal's whole size limit and the disk's reserve, from
Amendment 7, stand. The journal has a lock of its own, so that counting it does not hold up the admission of other requests. A
line of the journal that is nested too deep to read, which the door never writes, does not stop the count, and is passed over
when the journal is read for an answer, as a line that is not JSON already was.

**The engineer is told of a refusal for want of room (D1).** Any 507 refusal writes a notice to the engineer of the refused
job's baseline, named `STORAGE_FULL_<date>_<reason>`: one for each reason on each day on which it happens, however many designs
are refused. The reasons are the baseline's SHARE, the journal's LIMIT, the DISK's reserve, and the JOURNAL itself, which could
not be read or written. The notice gives the reason in words, says that nothing is run or counted and that no check gave it,
and says what can happen next. It is written outside the front door's locks. The refusal tells the caller whether the engineer
could be sent it.

**Where a notice of a refusal goes.** To the inbox; where the inbox cannot take it, to the service's own store (Amendment 7).
A copy kept in the store does not stop the inbox getting its own copy once it can take one: at most one in each place, for
each reason, on each day.

Nothing in a verdict or a record is changed. The words of every notice that existed before are as they were.

## The changed files

Base: `verification-amendment-7` at `e03a9c6`. Seven files change. The hashes are of the files as they stand at this commit.

| file | sha256 at e03a9c6 | sha256 now |
| --- | --- | --- |
| `verify/notices.py` | `67c1c6d1c1ecb05ddcdb4125d7bdaafe34634845ebe2ec941ebb5b1b98f8c4a7` | `385385b06b9d8d116e7cbd98718dba35fea47f1414384f3230e2b31dbe21197c` |
| `verify/verify_tools.py` | `477c243bee40ef4a3dcb4d1866c02523693f118f7d52f00fc897cb42cda33c0b` | `7f05c314cd68cbc2668c141fd07f8fdbf9fdf7daabb9a2f1b3cc3292dae35750` |
| `verify/front_door.py` | `5ab2dacb5c5a1fa23f1f6e998605868b437c2f70a7b81b8aa8734974815d0c3a` | `5e122666a76d2952f70492bf02cf73864fdba5b11632336016f9782f8c1c06a8` |
| `verify/front_ctl.py` | `d0d0ab91c78974cbdff59562f5d27f371a1dd61ac76d50ac3ab19164d397b0c9` | `64330e3a6324096c062c38c3683dde911c04d85f6771000d2fee9b218368ab18` |
| `verify/verify_ctl.py` | `530f2145bad430843b78e17867ad47587119df9e6518e7f8ca86f3bc731a4123` | `65ce6ad011e972a8e48a6f1098c490bede11bf7be3a5242addbc45a77595c005` |
| `tests/verify_tests.py` | `a8008a8c0cf15422abb8ed58579dceb38072e4e49451afa302934d68afa77567` | `c2d6a66eb255613f21d5dfa9ec8c5ba8e75a864375664d64c3ee8770be31553a` |
| `tests/verify_front_tests.py` | `2ddc69bb2ad0401f771f601f7ea03d7d3b5cada01139373d3dbeb290ee994008` | `fe76692c6f701d4e65ea375eb1f53ffbe4d08dbdeb55b330a834d0de16692fa2` |

One file is new as a development record: `verify/dev_amend8_mutants.json`, the pass of deliberate defects on this code.

Every other file in the repository at `e03a9c6` is unchanged: the rules of the baseline, the record builder and its checker,
the witness service, the gate host, the governor, the store, the first client, the MCP server, and the test harness.

## What each test is expected to show

**R1 to R21** are as declared before: the same functions, the same 120 checks, each expected true. The gate's tool now makes a
proof on every run and keeps it outside the inbox, and its probe leaves nothing in the inbox, so the checks of R19 and R20 that
list what an inbox holds read as before.

**R22 is new** (13 checks). The tool is started in a child process with its own service home, with no services running. Put
there beforehand: temporary files as a killed process would leave them, minutes old, in the inbox, in a folder of notices that
are no engineer's and in the folder of proofs; a fresh one in the inbox; and two old files that are not the service's own, one
in the inbox whose name begins as a part-written notice's does, and one in the folder of proofs. Expected, each true:

1. as the tool starts, a proof is on record that names the baseline and the present time; the probe leaves nothing in the
   inbox; the three old temporary files are taken away, and the fresh one and the two files that are not the service's own
   are left;
2. a proof is read rightly in each of eleven states: older than its limit, within it, dated ahead, a time that is not a
   number, a time too large to be one, a time that is a yes, missing, not a proof, naming another baseline, not saying plainly
   that the inbox was written, and put back;
3. with a file in place of the inbox, a run still returns its verdict with its notice in the store, the proof then says the
   inbox cannot be written, and the tool says so;
4. put back, the inbox is proved again by the tool's own look with no run, and the tool says so in that step;
5. a baseline folder that appears later, and has had no inbox for a minute, is given its inbox, hash and proof by that look;
   so is one whose folder is dated an hour ahead;
6. a baseline folder made that moment, with no inbox, is left for the console, and is proved once the console has made it;
7. a run renews the proof;
8. where the proof cannot be recorded, a run still returns its verdict, the state reads as not proven, the tool says so, and
   a new proof is on record once it can be;
9. where the record cannot be written though its folder is there, as on a full disk, the proof from before is not kept as good;
10. with the clock put back, the proof is made again all the same;
11. with the baseline's folder taken away and its inbox still holding its hash, the proof is still made by the tool's look;
    with that proof taken away, a run is answered UNKNOWN with its notice in that inbox, as before this amendment, and the
    run has made the proof again;
12. with the error output closed, a run whose proof and ledger both have something to say still returns its verdict;
13. the console shows proven with its time, and not proven with the proof taken away.

Expected for the gate: 22 of 22 tests, 133 of 133 checks.

**F1 to F18 and F20 to F27** are as declared before: the same functions, each expected true. Every one of them enrols its job
straight after making its baseline; enrolment now waits for the gate's proof, which the gate makes within about a second.

**F19 is restated, for the second time.** Amendment 7 restated it to the repaired behaviour. One step and one check change
here, and the reason is this amendment's own rule. F19 replaces the inbox with a file, runs a failing design (which Amendment
7's fallback answers, and which makes the gate record that the inbox cannot be written), puts the inbox back, and at once sends
a new design. Under this amendment that new design is refused until the gate has shown that it can write the inbox again, which
its own look does within about a second. The restated F19 waits for that proof before sending the design, and its sixth check
now reads "with the inbox put back, and once the gate has shown that it can write it again, the next failing design is FAIL,
and its notice goes to the inbox". Its other six checks are as Amendment 7 declared them, among them that the same design sent
again while the inbox is blocked is still answered. Seven checks, each expected true.

**F28 to F32 are new.**

- **F28** (5 checks): with the gate not running, a job is not enrolled on a new baseline, and nothing is changed: no binding,
  no folder, no line in the log of enrolments; with an inbox the gate cannot write, the gate says so as it starts and enrolment
  is refused; once the inbox can be written the gate shows it with no run and the job is enrolled and answered; a job is not
  moved to a revision whose inbox the gate cannot write, and stays where it was; once it can, the job moves.
- **F29** (8 checks): with the proof good a failing design is FAIL; with no proof on record a new design is refused at the
  door with nothing run, counted or journaled and no result sent; the engineer has one notice of the refusal on the day for
  that reason, however many designs are refused, it says what becomes of a run already on the record, and the caller is told
  the engineer has been sent it; a design whose run is finished is still answered and nothing more is run; a proof older than
  its limit, and one that says the inbox could not be written, each refuse a new design in their own words and each write a
  notice of their own, with their own reason; where the runs cannot be read a design is not let through, and the refusal says
  only that this request ran nothing; when the gate shows again that it can write the inbox, the design refused before is run;
  and a run that an earlier request began and that was not yet made is not made while the proof is not good, the refusal says
  that it is on the record with no verdict yet and does not say that nothing was run, and it is made once the proof is good.
- **F30** (9 checks): a design within its baseline's share is run; the next new designs for that baseline are refused with
  nothing run or counted and the journal the same size; a design already journaled is still answered; a job on another baseline
  still runs; the refused baseline's engineer has one notice, with the reason, and the other baseline's inbox has none; the
  caller is told the engineer has been sent it; a front door started afresh counts the share again from the journal; when
  room is made in the journal, the count is taken again and the baseline's next design is run; and a journal line nested too
  deep to read is counted for no baseline and stops no answer.
- **F31** (5 checks): a full journal refuses the design and the engineer has one notice with the reason; the caller is told; a
  second design refused for the same reason writes no second notice, and a refusal for too little disk writes a notice of its
  own, with its own reason; with the inbox unable to take it the notice is kept in the store, the console lists it, and the
  caller is told the engineer could not be sent it; nothing was run or counted.
- **F32** (6 checks): the gate host dies during a run, and the gate, started again with a file in place of the inbox, shows
  that it cannot write it; the design asked for again is refused, and the refusal does not deny the run: it says that an
  earlier request began a run that is on the record with no verdict yet and that this request ran nothing, it does not say
  that nothing was run, and nothing more is run or counted; the notice of that refusal is kept in the store and the caller is
  told the engineer could not be sent it; once the gate has shown that it can write the inbox, the design is answered
  INTERRUPTED with one notice of the run; with the proof then saying again that the inbox could not be written, that design is
  still answered INTERRUPTED and nothing more is run; and a new design is then refused with nothing run, the notice that was
  kept in the store now has its copy in the inbox, and the caller is told the engineer has been sent it.

Expected for the front door: 32 of 32 tests, 168 of 168 checks: the 135 of Amendment 7, F19's seven among them, and the 33 of
F28 to F32 (5 + 8 + 9 + 5 + 6).

## What was done before this declaration

All of this was on 17 November 2026, in the repository on this branch.

- **The first run of the nearest Amendment 7 tests on the new code** found F19 failing, as expected: it sends a new design at
  once after putting the inbox back, and this amendment refuses that design until the gate has proved the inbox again. F19 is
  restated as above. The first version of R22's check that a proof is recorded again was true whatever the code did, because the
  proof from before was still on file; it now needs a proof other than the one left.
- **The first form**, both suites in full, 10:12:23 to 10:16:57: the gate suite 22 of 22 with 128 checks, and the front suite 31
  of 31 with 157 checks. In the first form a proof stayed good for 300 seconds, the front door had a setting for that limit, a
  design with any attempt on record was let through, and only held baseline folders were proved.
- **Planted defects, first pass**, on the first form: 29 of 29 caught, with the control passing.
- **The author's own read**, while the review was out, found two faults. With the machine's clock put back, the tool's memory of
  a proof was dated ahead, and the proof was not made again until the clock caught up. And a proof that could not be recorded,
  as on a full disk, left the proof from before on file as good. Both were fixed, with a check and a planted defect each (R22,
  checks 9 and 10; N9, N10). Both suites in full again, 10:26:02 to 10:30:36: 22 of 22 with 130 checks, and 31 of 31 with 157.
- **One review of the change, before the declaration.** A separate AI agent, read-only and not given the author's conclusions,
  was given the register's text for D3 and D1 and the intended repair, and asked whether the proof can read as good when the
  gate cannot write the inbox, or stay bad when it can; whether a refused enrolment or run changes, journals or counts anything;
  whether a baseline can be refused for another's share; whether a notice of a refusal can be lost, written twice or reach the
  wrong engineer; and whether anything changed that should not have. It read the first form, and ran neither suite. It
  reported nine findings, and found no defect in the order of enrolment (the proof is asked for before the certificate is issued
  and before any write), in what a refusal journals and counts (nothing), in the count within one process, in where a notice of
  a refusal goes, or in the verdict, the existing notices and the Amendment 7 fallback. Dispositions:
  - *Medium, a design with an unfinished attempt was let through* (a run admitted on a good proof and not made, then asked for
    again when the proof was bad, was made): **fixed**. Only a design whose run is finished is let through, and a failed read of
    the runs refuses (F29, its last check and the "cannot be read" check; planted defects D13, D16).
  - *Medium, a baseline whose folder is gone was no longer proved*, so its designs were refused where before they were answered
    UNKNOWN with a notice, and the engineer was told nothing: **fixed**. Every inbox that holds a baseline's hash is proved (R22,
    check 11; N13), and a refusal for an unproven inbox writes a notice to the engineer (F29; D14).
  - *Medium, a clock set back put the proof off* for as long as the step: **fixed** (R22, check 10; N9). The author's read had
    found it too.
  - *Low to medium, the look could be switched off by a setting, the refresh could be set longer than the limit, and the front
    door's limit was not the consoles'*: **fixed**. The look's interval is held between 0.1 and 10 seconds, the refresh to a third
    of the limit at most, and there is one limit, 120 seconds, with no setting. Not tested beyond the defaults.
  - *Low to medium, the shares were counted once*: room made in the journal did not count until the door restarted; a second
    door on the same journal counted only its own lines; a line nested too deep to read raised an error on every submission; and
    the first count held the lock that admits every request. **Fixed**: the count is taken again whenever the journal is not the
    size the door left it (F30, its last check; D15), a line that cannot be read is counted for no baseline, and the journal has
    a lock of its own. The last two, and a second door, are not tested.
  - *Low, the state can read as proven while the gate cannot write*: for up to 30 seconds after an inbox goes bad (**open**, see
    "What stays open"); for the whole limit when the bad result cannot be recorded (**fixed**: the proof from before is taken
    away; R22, check 9; N10); for the whole limit after the gate has died (**partly**: the limit is cut from 300 to 120 seconds,
    and the rest is open); and for ever on a proof whose time is not a number, with an error on one too large to be a number
    (**fixed**; R22, check 2; N11, N12).
  - *Low, who makes the inbox had become a race* between the console and the tool's look, and a restrictive gate account could
    leave the folder of proofs unreadable to the console: **partly fixed**. The look leaves a baseline whose folder is under 10
    seconds old for the console (R22, check 6; N14), and the tool sets the permissions of the proofs itself. The race as the tool
    starts is open, and permissions were not tried on two accounts.
  - *Low, a killed process could leave a probe file in an inbox, and the tool's report of a bad inbox could raise into a run*
    when the error output is closed: **fixed**. The tool takes away its old temporary files as it starts (R22, check 1; V7), and
    nothing the proof does can raise into a run (R22, check 12; V6).
  - *Low, the tests*: one R22 wait could fail falsely about once in a thousand runs, one R22 check and F29 depended on timing,
    F28 did not look at the log of enrolments, and four cases were untested (an unfinished attempt, a failed read of the runs,
    the share after room is made, a clock change). **Fixed**: the waits look for a proof other than the one left, the times in
    the tests are taken from the proof on record, F28 reads the log, and the four cases have checks.
  - Also raised: each run now does two more writes that are put on the disk, about a millisecond on this machine. Not changed
    (see "What stays open").
- **The second form** carried those fixes. Both suites in full, 10:40:06 to 10:44:59: 22 of 22 with 133 checks, and 31 of 31
  with 161 checks. Planted defects on it, 10:44:59 to 10:54:11: the control passed, and 38 of 41 were caught by a failing check.
  The other three (a time too large to be a number; the door not asking for the proof; a design let through when the runs
  cannot be read) stopped a test with an error where a check should have failed. None went unnoticed. The two tests were
  changed so that each of the three fails a check.
- **A second review, of the second form.** Another separate AI agent, read-only, was given the first review's nine findings and
  the fix intended for each, not the author's view of whether the fixes worked, and asked whether each fix closes its finding
  and whether it brings a new fault. It ran neither suite. It reported eight findings. It found no defect in a claim put in an
  inbox by someone else, in where a notice of a refusal goes or how many are written in one place, in what a refusal journals
  or counts, or in the count, its lock and their order. Dispositions:
  - *Medium, the refusal of a design whose run an earlier request had begun said that nothing was run and nothing was counted*,
    which is untrue of that run; and before the second form such a design, if its run had been cut off, was answered
    INTERRUPTED. **Fixed in the words, open in the timing.** The refusal now says that the run is on the record with no verdict
    yet (F29, last check; F32; planted defect D17), and the engineer's notice says what becomes of such a run (F29; D23). The
    run is still not reported as interrupted until the proof is good (see "What stays open").
  - *Medium to low, a notice of a refusal first kept in the store stopped the inbox getting a copy that day*, even after the
    inbox was put right; and a notice of the morning for one reason silenced the afternoon's for another, while the caller was
    told that the engineer had been sent it. **Fixed**: the inbox gets its copy once it can take one (F32, last check; D19), and
    there is one notice for each reason (F29, F31; D20, D24, D25). A second episode on the same day for the same reason is open.
  - *Low, the 10 seconds left to the console were counted one way only*, so a baseline folder dated ahead got no inbox and no
    proof: **fixed** (R22, check 5; N15).
  - *Low, the proof from before is taken away only where it can be*: with a folder of proofs the gate cannot change, it reads
    as good for up to 120 seconds. **Open**, stated.
  - *Low, a journal line nested too deep to read*, counted since the second form, then stopped every answer, after the run was
    made: **fixed**. Such a line is passed over when the journal is read for an answer (F30, last check; D21, D22).
  - *Low, the sweep went by the start of a name and followed a linked inbox*, so it could take a file of the engineer's own; it
    took any old file in the folder of proofs whose name began with a dot; and it did not reach the folders of notices that are
    no engineer's. **Fixed**: only a plain file with one of the service's exact temporary names is taken, and those folders are
    swept (R22, check 1; N16 to N19). A linked inbox is still followed (stated).
  - *Low, the fix for who makes an inbox was partial*: the start still makes inboxes at once, the permissions are set only when
    the tool makes the folder of proofs, an inbox the gate makes has the gate account's permissions, and a refusal's notice can
    make a missing inbox under the front door's account. **Open**, stated.
  - *Low, the tests*: no check for the limits on the two settings, for the permissions, for a second door, for the run's own
    proof on a baseline whose folder is gone, for an interrupted design let through, or for the words of two of the three
    notices; one part of an R22 check is true by its own set-up; one R22 check could be met by a later step; F29's timing; and
    the one-notice checks at midnight. **Fixed in part**: the run's own proof (R22, check 11; V8), an interrupted design (F32;
    D18), the notices' words (F29; D24) and the R22 step (check 4) now have checks. The rest is under "What is not tested". The
    part that is true by its set-up stays: where the folder of proofs is a file the state reads as not proven whatever the
    code does, and the check's other parts are what test the code.
- **The third form** is the code at this commit. It was not read by a reviewer.
  Both suites in full on it, 11:17:17 to 11:22:30: the gate suite 22 of 22 with 133 checks, and the front suite 32 of 32 with
  168 checks. The planted defects on it (below) then showed one more test that stopped with an error where a check should have
  failed: F29, when the name of a notice carries no reason. One line of F29 was changed for that. The front suite was then run
  in full again, on the file as it stands at this commit, 11:35:55 to 11:38:50: 32 of 32 with 168 checks. No file of the gate
  suite was changed after its run.
- **Planted defects**, deliberate faults in a scratch copy, one at a time, each run against the checks that cover its repair. The
  first pass, on the first form, caught 29 of 29. The second, on the second form, is described above. The final pass, on the
  third form, 11:22:31 to 11:35:24, is recorded in `verify/dev_amend8_mutants.json`: the control M0 passes unchanged, on R19,
  R20, R22, F19, F25 and F28 to F32, and 56 of 56 defects are caught by a failing check. One of them, D20, also stopped F29 with
  an error; after the one-line change to F29 it was run again, and is caught by F29 and F31 with no error. The other 55 were
  not run again after that change.

## What stays open

- **The engineer is still told by notice or by asking, not by a channel the service cannot silence.** A notice of a refusal is
  written by the same service that refuses. A statement signed by the witness, of the runs admitted, the verdicts recorded and
  the notices delivered for each baseline, is the repair for D2 and D11 and for telling a current record from an old one (D7).
  It is not in this amendment.
- **Between an inbox going bad and the gate's next proof there is a window**, of 30 seconds at most while the gate is running.
  A new run admitted in it is answered by Amendment 7's fallback: the verdict is returned, the notice is kept in the store, and
  the caller is told. That run also makes the gate record that the inbox cannot be written, so the next new run is refused.
- **A run cut off while the proof is not good is not reported as interrupted until the proof is good** and its design is asked
  for again. The door cannot tell a run that was cut off from one that was admitted and never made: only the gate knows, and
  asking the gate could make the run. Until then the refusal says that a run of the design is on the record with no verdict
  yet, the engineer's notice of the refusal says what becomes of such a run, and the console's status shows it as PENDING.
- **Where the gate cannot change the folder of proofs at all**, as with a folder it has no permission to write, it cannot take
  the last good proof away, and that proof reads as good until it is 120 seconds old. The tool says so on its error output. A
  full disk is not this case: there the proof from before is taken away.
- **A proof stays good for up to 120 seconds after the gate stops.** In that time a job can still be enrolled, and a new run
  is still admitted at the door and then fails because the gate cannot be reached.
- **The proof says what it says and no more**: that this gate process could write a 4 KiB file in that folder at that time. It
  does not say that the engineer reads the inbox, or that the next write will succeed. It is an unsigned file, like a notice
  (D12): it shows that the service is set up and working, and is no defence against someone who can write the service's home.
- **Who makes an inbox is still a race as the tool starts.** At start the tool gives every baseline it holds an inbox at once,
  as Amendment 6 has it, so a baseline being made at that moment can get an inbox made by the gate's account, with the gate's
  permissions. Its own look, afterwards, leaves a new baseline's inbox to the console for 10 seconds. A notice of a refusal,
  like a notice of an interrupted run since Amendment 7, can make a missing inbox under the front door's account.
- **Permissions.** The tool sets the permissions of the folder of proofs when it makes that folder, and of each proof. A folder
  of proofs made beforehand with tighter permissions is left as it is, and the consoles then read no proof.
- **The sweep follows an inbox that is a link to another folder**, and takes from it only plain files with the service's exact
  temporary names, more than a minute old.
- **The first client has no enrolment and no front door** (D6). On that route the proof is shown by the console's status only.
- **Real accounts were not used.** The two-account case is made by putting a file in place of the inbox, which the gate cannot
  write for another reason. The proof is made by writing, so it does not depend on why the write fails, but permissions on a
  real second account, and the reading of the proofs by another account, were not tried.
- **The cost of proving grows with the number of baselines**: each proof is two 4 KiB writes put on the disk, and each good
  proof is made again every 30 seconds. A run does the same once.
- **The share is a default**, 64 MiB of a journal whose whole limit is 1 GiB, so sixteen baselines can each fill a share before
  the whole limit is reached, and more baselines than that can still fill the journal between them. One job can no longer do it
  alone. No archive or rotation exists: the record ties each run to its design through the journal, so room made in the journal
  by hand takes that tie away for the lines removed.
- **The shares are counted by reading the whole journal**: when a front door first needs them, and again whenever the journal is
  not the size that door left it. Two front doors writing one journal would each count it again on every request. A journal
  emptied and filled again to exactly the size the door left is not counted again.
- **The front door reads the whole journal for each answer**, as it did before this amendment. A large journal is slow.
- **A notice of a refusal is one a day for each reason**, named by the date in UTC. A refusal that goes on is told again the
  next day. A second episode on the same day for the same reason writes no new notice: the day's notice for that reason is
  already there, and the refusal tells the caller that the engineer has been sent it.
- **D2, D5 to D8, D11 to D13 and the gap-table rows on the keep list** (G4, G7, G8, G10, G11) are not in this amendment.

## What is not tested

- Permissions on two real accounts, and a real full disk. Each is simulated.
- A real change of the machine's clock. The tool's memory of its proof is dated ahead instead.
- Many baselines, more than one gate process, and more than one front door on one journal.
- The limits on the tool's two settings (`VERIFY_PROOF_SCAN`, `VERIFY_PROOF_REFRESH`), and the front door's
  `--journal-share-bytes`, beyond their defaults. The tests take both settings out of the tool's environment.
- A journal line that is not JSON, and one that is JSON and not a design. A line nested too deep to read is tested (F30).
- A design whose run on record is neither finished nor pending (refunded, or not a verdict). It is refused while the proof is
  not good, and the refusal says only that this request ran nothing.
- The permissions the tool sets on the proofs.
- The tests' own timing: F29's steps on a proof that is not good must end within 30 seconds of its first run, before the gate
  makes its proof again (here they take about two); and the checks that count one notice on the day would fail across midnight
  UTC.
- That counting the journal does not hold up other requests.
- An assistant's reaction to the two refusals, beyond their text.
- The proof's part for the service's own store. It is recorded, and nothing is decided by it.

## Commands and results

The official runs are these, each once, from the tree at the commit that carries this declaration, with the services on
127.0.0.1 and PostgreSQL 16:

    cd tests && python3 -B verify_tests.py
    cd tests && python3 -B verify_front_tests.py

Each output file is copied to `verify/results_verify_tests_amended8_2026-11-17.json` and
`verify/results_front_tests_amended8_2026-11-17.json`. The outputs folder is not committed.

The expected results are: gate 22 of 22 tests and 133 of 133 checks; front door 32 of 32 tests and 168 of 168 checks. Every
outcome must match this declaration. An outcome that does not match is recorded as it is, and the amendment says so.
