# Amendment 14: declaration before the official test runs

20 November 2026. Private working material.

This file is committed before the official runs of `tests/verify_tests.py` and `tests/verify_front_tests.py` on the branch
`verification-amendment-14`. It fixes the changed code, states what each test is expected to show, and records what was done
in development. Each official run is made once after this commit and its first result is kept, pass or fail. A later
correction would be a separate, dated amendment. Times are UTC.

This is internal work by the author of the code, under the owner's direction. It is not an independent validation.

## Why declared files are changed

F17 shows that two failures whose notices would have the same file name both reach the engineer. It made that case by
timing alone: two failing designs sent one after the other, just after a second began, had both to end within that second.
In the official run of Amendment 12 they did not, in any of six tries, and F17 failed two of its three checks without
having tested what it is for. That result stands, in `verify/results_front_tests_amended12_2026-11-19.json` and
`verify/AMENDMENT_12_2026-11-19.md`, and is not changed.

The cause was found on the branch `diagnostic-f17-2026-11-19` (`verify/DIAGNOSTIC_F17_2026-11-19.md` there). F17 had about a
tenth of a second to spare; the sandbox of Amendment 12 takes about 0.07 s more for each run; and each run on a baseline
was slower than the one before, so that after one miss F17 could not recover. Amendment 13 repaired the slowing. F17 then
passed, in that amendment's official run, and it still rested on a few hundredths of a second.

On 20 November the owner asked for F17 to be restated so that its precondition is explicit, and for one sentence of
Amendment 12's amendment to be corrected here and not in place.

## What is changed

**No code of the service is changed.** Two tests are restated, in `tests/verify_front_tests.py` and `tests/verify_tests.py`.

**F17 is restated.** It keeps its purpose and has four checks where it had three:

- **The naming, with no clock.** Two notices are delivered under one name, by the call the gate's tool makes for every
  notice (`notices.deliver`), into a folder of the test's own. Nothing here depends on time.
- **The case, made through the service, and said to be made.** Two jobs are enrolled on the one baseline, and each sends
  one of two failing designs whose hashes begin with the same eight digits, at the same moment, early in a second. (One job
  cannot send both: the front door takes one design at a time for a job, and refuses a second as IN_PROGRESS.) Each takes
  about half a second, so both end well within the second, where before the second of two in a row ended at its very end.
  It tries six pairs. Only when both notices are named for the same second and the same eight digits is the case made, and
  only then is anything judged of it. The test's evidence says which of three things happened: COLLISION_HANDLED,
  COLLISION_MISHANDLED, or PRECONDITION_NOT_MET. The last is a failure to test, and F17 fails on it; it is never a pass.
- **That it was handled**, and **that the inbox holds a notice for every failure**, as before.

**R28 is restated**, after a review of the form Amendment 13 declared found things it could not see. It has six checks
where it had five, and tests the same reading, which is not changed:

- connections are counted where the database driver opens them, not where the store does, and must be exactly two;
- a reading is cut at the very decision of a run's report, and at the one before;
- after the record is checked, the test changes the store by hand, with the owner's role. Under a second budget it puts a
  report, every receipt and a result saying PASS for three of this budget's runs. In this budget it puts a second, earlier
  report for one run; takes every report, receipt and result from another; puts a PASS for the run that was interrupted;
  and makes a third run's result into one that is no value. The reading must give what reading each run by itself gives,
  with nothing of the other budget's anywhere in it;
- a reading that raises is a reading that failed: R28 fails its checks, and does not stop.

Amendment 13's official result for R28, 5 of 5, stands as it was reported: it is a result of the form declared then.

## A correction to the amendment of Amendment 12

`verify/AMENDMENT_12_2026-11-19.md` says, of F17: "When F17 fails, each of its runs takes about a second." That is not so.
It was read from the names of the notices, which show only that the second run ended in the second after the first. No
run took a second: each took about half of one, and the pair ended a few hundredths of a second after the second did.
The same document says "Why is still not known"; it is known now, and is stated above. The declaration of Amendment 12
offers, as all that was known of the cause, that both failing development runs began within minutes of a pass of deliberate
defects; that was a coincidence. Neither document is changed. They are corrected by this paragraph.

## The changed files

Base: `verification-amendment-13` at `f44e629`. Two files change, both of them tests, neither new.
The hashes are of the files as they stand at this commit.

| file | sha256 at f44e629 | sha256 now |
| --- | --- | --- |
| `tests/verify_front_tests.py` | `6fea8dc990448d6f7f9bd6a40bda992de4ec9f184015d2a0ef5ac29a1bfab128` | `f85fd99222ab4fb3a6f2915fe03846b9be726a542d6a8699eef8d26bbf1b3e60` |
| `tests/verify_tests.py` | `f681088556030cdbd4532159a6ef04f05d2069e7b5e060ceeb86c744f9f5da39` | `44ad84d7cc906e9621132dd655d73aa7cc5000023302252889670e8e1fd43f99` |

One file is new as a development record: `verify/dev_amend14_mutants.json`, the pass of deliberate defects.
Every other file in the repository at `f44e629` is unchanged.

## What each test is expected to show

**R1 to R27** are as declared before: the same functions, each expected true.

**R28 is restated** (6 checks):

1. the runs are there to read: 3, then 15, one of them interrupted, with no result; and the record verifies.
2. the reading gives exactly what reading each run by itself gives, for 3 runs and for 15.
3. and so does a reading cut at an earlier decision, which is not the whole reading; cut at the very decision of a run's
   report it shows the report, and cut at the decision before it does not.
4. it opens two connections to the database for 15 runs as for 3, counted where the driver opens them, where reading each run
   by itself opens more for every run.
5. with a second, earlier report put into the store for one run, and a report, every receipt and a PASS put under another
   budget for runs of the same names: the run shows its own two reports, the earlier first, its own receipts and its own FAIL,
   and nothing of the other budget's is anywhere in the reading, as reading each run by itself gives.
6. a run left with no report, no receipt and no result is read as having none, and is no longer a FAIL or a PASS; a PASS put
   by hand for the run that had no effect is not taken, and it stays interrupted; and a result made into one that is no value
   is not taken.

Expected for the gate: 28 of 28 tests, 217 of 217 checks: the 216 of Amendment 13, less R28's 5, and its 6.

**F1 to F16 and F18 to F36** are as declared before, each expected true.

**F17 is restated** (4 checks):

1. with no clock: two notices delivered under one name are two files, the second numbered, each with its own text, and nothing
   else is left.
2. through the service the case was made: two designs whose hashes begin with the same eight digits, sent at the same moment
   by two jobs on the one baseline, both failed, with their notices named for the same second (a case not made is
   PRECONDITION_NOT_MET: a failure to test, never a pass).
3. and it was handled: each failure has its own notice, two files with different names, neither empty, each naming its own
   design.
4. the inbox holds one notice for every failure, and the record verifies with all of them.

Expected for the front door: 36 of 36 tests, 193 of 193 checks: the 192 of Amendment 13, less F17's 3, and its 4.

## What was done before this declaration

All of this was on the branch, before this declaration, on 20 November.

- **A diagnostic first**, on the branch `diagnostic-f17-2026-11-19`: `tests/diag_f17_collision.py`, not a declared test, which
  made the case in the three ways F17 now uses or measures. Its part that sent both designs from one job never made the
  case, one of each pair being refused IN_PROGRESS, and said so; with two jobs it made it at the first try in six runs of
  six, the pair ending between 0.59 and 0.94 s into the second.
- **The first form** (`ad1d865`): F17 restated, with four checks. Run by itself it passed, the case made at its first try.
  Five things were then planted, one at a time, in a copy, with a control:
  - a notice written over the one that has its name;
  - a notice whose name is taken not written, and the first reported in its place;
  - no second name tried, so that the notice goes to the service's own store;
  - the second notice given its number and no text;
  - and, not a defect of the service, the two jobs made to send a second apart.

  With each of the first four F17 said the case was made and failed its check that it was handled, and the check with no
  clock failed too. With the fifth it said PRECONDITION_NOT_MET after six tries, failed its two checks of the service, and
  passed the other two. The control passed.
- **An independent review of R28**, the test Amendment 13 declared, as it stood at `f44e629`, by a separate agent that read
  the code and the store and ran no test. R28's earlier forms had missed defects, and its last two forms had been read only
  by their author. The review found five more things R28 could not see, all of medium weight:
  1. *Another budget's results.* R28 put a report and one receipt under a second budget, and no result: a reading that took
     every budget's results would have passed.
  2. *The two conditions on a result.* A result counts only for a run that had its effect, and only if it is a value. With
     R28's data, taking away either changed nothing.
  3. *A run with no rows.* Every run R28 read had its report and its three receipts, so a reading that failed on a run
     without them would have passed.
  4. *Connections opened another way.* R28 counted connections opened through the store's own method; one opened straight
     through the driver was not counted.
  5. *A name that claimed more than its check.* Check 2 said each run's reports were in order, where every run it read had
     one report; order was tested only by check 5.

  And of lower weight: no reading was cut exactly at a report's decision; the other budget's receipt showed only by the
  order of rows on the disk; and the check of connections allowed three where two are opened.
- **The second form** (`cfb0a88`): R28 restated, with six checks, to see each of these. Connections are counted where the
  driver opens them. A reading is cut at a report's own decision and at the one before. After the record is checked, the
  test puts under a second budget a report, every receipt and a result saying PASS, for three of this budget's runs; takes
  every report and receipt from one run; puts a PASS by hand for the interrupted run; and makes one run's result into one
  that is no value. Its full runs, 01:16:01 to 01:23:27: the gate's suite, 28 of 28 tests and 217 of 217 checks; the front
  door's, 36 of 36 tests and 193 of 193 checks, F17 saying COLLISION_HANDLED at its first try; the four whole-gate tests each
  exited 0.
- **Its pass of deliberate defects**, 01:24:23 to 01:35:46: 22 defects and a control. It caught 19, and the control
  passed. The other three were R28's again:
  - U5 and U8, a reading that fails on a run with no report, or with no receipt: R28 stopped with an error, where it should
    have failed a check, because the reading raised while R28 was measuring it;
  - U1, the results of every budget read: where two budgets hold a result for a run of one name, the row read last is the
    one kept, and in the defect as it was planted this budget's own was last, so nothing showed.
- **The third form** (`9aaac04`): R28 changed, and nothing else. A reading that raises is taken as a reading that failed,
  and the test goes on. The run left with no report and no receipt is left with no result too, so that another budget's
  result for its name would show whichever row is read last. U1, U5, U8 and the control were run again at once: all three
  caught, and the control passed. This is the code this declaration carries. Its full runs, 01:38:35 to 01:45:53: the gate's
  suite, 28 of 28 tests and 217 of 217 checks; the front door's, 36 of 36 tests and 193 of 193 checks, F17 saying
  COLLISION_HANDLED at its first try; the four whole-gate tests each exited 0.
- **Its pass of deliberate defects**, 01:46:49 to 01:58:16, caught 22 of 22, with the control passing.
- The defects are kept in `verify/dev_amend14_mutants.json`, which names, for each, the checks that caught it: N1 to N5 for
  F17; T1 to T9, those of Amendment 13, and U1 to U8, for what the review said R28 could not see.
- **What no reviewer has read.** The restated F17 and the restated R28 were read only by their author. Two reviews and
  three passes of deliberate defects have each found something R28 could not see; that it now sees everything is not claimed.

## What stays open

- **F17's case through the service is still made by timing, with more to spare.** Two jobs sending at once end between
  about 0.6 and 0.95 s into the second, where two runs in a row ended at 1.0. On a slower machine the case could still not
  be made in six tries; F17 would then fail, and say PRECONDITION_NOT_MET. Only its check with no clock never depends on
  time, and that check tests the naming alone, not the service.
- **A case made with certainty through the service** needs the service to be told the time, or two runs to be held and let
  go together. Either is a change to declared code, and neither is made.
- **R28 changes the store by hand.** What it puts there, under the owner's role, the service itself would not write: a
  second budget holding a run of the first's name, a result for a run that had no effect. It shows what the reading does
  with such rows, not that they can arise.
- **R28's reference is the old reading, kept in the test.** A fault in what both readings share (the list of receipts'
  kinds, the rule for an outcome, the snapshot of the log) would be the same on both sides; only the record's own checks
  would show it.
- **What Amendment 13 left open is still open**: an answer still does work that grows with the runs made; F36 is a test of
  time; the store opens a connection for every call.

## What is not tested

- A machine slow enough that two runs sent together do not end within one second.
- More than two failures in one second, or two baselines' failures in one second.
- A notice's name already taken in the service's own store (`undelivered/`), as distinct from the inbox.
- A reading cut exactly at the decision of a receipt. R28 cuts at a report's.
- A reading in which rows change between its two transactions.
- The removal of the transaction's isolation: nothing writes while R28 reads, so reading at several moments would look the
  same.
- Many queries over the one connection, one for each run: the count of connections would not show them, and F36's time
  might not.

## Commands and results

The official runs are these, each once, from the tree at the commit that carries this declaration, as root, with the services
on 127.0.0.1 and PostgreSQL 16, with the interpreter of the project's virtual environment, on a machine whose file table has
been raised for this start of the machine as the sandbox requires (`sysctl -w fs.file-max=9223372036854775807`), and with no
run of the sandbox's left on it:

    cd tests && <venv>/bin/python -B verify_tests.py
    cd tests && <venv>/bin/python -B verify_front_tests.py

Before each command the output file it will write is removed. Each output file is copied to
`verify/results_verify_tests_amended14_2026-11-20.json` and `verify/results_front_tests_amended14_2026-11-20.json`. The outputs
folder is not committed.

Expected: for the gate, 28 of 28 tests and 217 of 217 checks; for the front door, 36 of 36 tests and 193 of
193 checks. A check that comes out other than expected is reported as it came out, in the amendment that follows the
runs, and is not run again under this declaration.
