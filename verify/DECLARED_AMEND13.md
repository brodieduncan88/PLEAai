# Amendment 13: declaration before the official test runs

20 November 2026. Private working material.

This file is committed before the official runs of `tests/verify_tests.py` and `tests/verify_front_tests.py` on the branch
`verification-amendment-13`. It fixes the changed code, states what each test is expected to show, and records what was done
in development. Each official run is made once after this commit and its first result is kept, pass or fail. A later
correction would be a separate, dated amendment. Times are UTC.

This is internal work by the author of the code, under the owner's direction. It is not an independent validation.

## Why declared files are changed

In the official run of Amendment 12, F17 failed: its two runs did not end in the same second. Looking for the cause, on the
branch `diagnostic-f17-2026-11-19` (`verify/DIAGNOSTIC_F17_2026-11-19.md` there), showed something F17 had not been written to
find: every answer the front door gives takes longer than the one before. Thirty designs sent one after another on one
baseline took 0.49 s for the first and 1.97 s for the thirtieth, about 0.05 s more for every run already made. At that rate
a baseline with 1,000 runs would take about 50 s for an answer, near the client's limit of 60 s.

The cause is in `verify/verify_record.py`. After every verdict the front door reads the baseline's runs, to count them in
its answer. That reading, `attempts_of`, read each run by itself: its evidence, its three receipts and its result, each
through a method of the store that opens a connection to the database of its own. Five connections for every run already
made, at about 9 ms each. The governed run itself took the same 0.40 s throughout.

On 19 November the owner asked for this to be repaired first, in an amendment of its own, with a declared test that fails
if an answer's time grows with the runs already made, and before F17's own logic is touched.

## What is changed

**A baseline's runs are read in one transaction.** `attempts_of` still takes the log and the state of the budget from
`store.audit_snapshot`, as before. Then, where it read each attempt by itself, it now calls `_stored_for(store, root)`, new,
which opens one connection, begins one transaction that only reads and sees one moment (REPEATABLE READ, READ ONLY), and
reads the budget's evidence, its receipts and its results, one query each. So a reading opens two connections, whatever the
number of runs.

What the reading gives is the same: the same rows, the evidence of each attempt in the order of its decisions, the same
cut at an earlier decision (`upto`), and nothing for an attempt that has no rows. Each table's key allows one result for an
attempt, one receipt for an attempt and an operation, and one row of evidence for a decision, so nothing can be read twice
or lost in the gathering. The three readings are now of one moment, where before they were of as many moments as there
were readings.

Nothing else is changed: not the store or any other file of the gateway, not the front door, the gate's tool, the sandbox,
the record or its checker. Every caller of `attempts_of` (the front door and the first client, for their answers; the
record's builder; the engineer's console) gets the faster reading.

## The changed files

Base: `verification-amendment-12` at `bc33c4b`. Three files change, none of them new.
The hashes are of the files as they stand at this commit.

| file | sha256 at bc33c4b | sha256 now |
| --- | --- | --- |
| `verify/verify_record.py` | `1036f9dce7826ce59df95259192c18e8e19ad828a5e2dde90455945f99773227` | `89ac0bcf81f603835730adc7851a8dda4e554c60df9e0c7ed88476fa9a192888` |
| `tests/verify_tests.py` | `e7354ab3e4e89e04bbe9719bf706dbf37426ffe851a174403e8197c50bfba72d` | `f681088556030cdbd4532159a6ef04f05d2069e7b5e060ceeb86c744f9f5da39` |
| `tests/verify_front_tests.py` | `6a255b101420605cffb5978fbb618ea22ce6b202a154ead982dcfedadf0644f5` | `6fea8dc990448d6f7f9bd6a40bda992de4ec9f184015d2a0ef5ac29a1bfab128` |

One file is new as a development record: `verify/dev_amend13_mutants.json`, the pass of deliberate defects on this code.
Every other file in the repository at `bc33c4b` is unchanged.

## What each test is expected to show

**R1 to R27** are as declared before: the same functions, each expected true.

**R28 is new** (5 checks). On one deployment, its host is stopped during the first run, so that run is interrupted;
it makes 2 more runs and reads the 3; it makes 12 more, one of them outside the design space, and reads the 15. Then, the
record having been checked, it puts into the store, with the owner's role, a second, earlier report for one run, and a
report and a receipt for a run of the same name under a second budget, and reads again. Each reading is made three ways:
as the code now reads; as the code read before, kept in the test (`_attempts_one_by_one`); and cut at the decision halfway
through the log. The store it reads through counts the connections it opens.

1. the runs are there to read: 3, then 15, one of them interrupted, with no result; and the record verifies.
2. the reading gives exactly what reading each run by itself gives, for 3 runs and for 15, each run's reports in the order of
   their decisions.
3. and so does a reading cut at an earlier decision, which is not the whole reading.
4. it opens the same number of connections to the store for 15 runs as for 3, where reading each run by itself opens more for
   every run.
5. with a second, earlier report put into the store for one run, and a report and a receipt for a run of the same name put
   under another budget: the run shows its own two reports, the earlier first, and nothing of the other budget's, as reading
   each run by itself gives.

Expected for the gate: 28 of 28 tests, 216 of 216 checks: the 211 of Amendment 12 and the 5 of R28.

**F1 to F35** are as declared before, each expected true, **with F17 as it is**: it is not changed here. F17 still needs two
runs in a row to end within one second. With this change an answer takes about 0.44 s where it took 0.49 s, and no longer
slows from one try to the next, so F17 should make its case more often than under Amendment 12; it can still miss. It is
expected true. If it fails as it did before, that is reported as it comes out, and it is restated in the amendment after
this one.

**F36 is new** (3 checks). It sends 25 failing designs, one after another, through the front door, and times each
answer:

1. 25 designs sent one after another each get their FAIL, and each answer counts the runs so far, 1 to 25.
2. the last five are answered about as fast as the first five: their middle time is less than a quarter of a second more (it
   was a second more before).
3. every failure has its notice, and the record verifies with all 25.

Expected for the front door: 36 of 36 tests, 192 of 192 checks: the 189 of Amendment 12 and the 3 of F36.

## What was done before this declaration

All of this was on the branch, before this declaration, on 19 and 20 November.

- **Finding the cause**, on the branch `diagnostic-f17-2026-11-19`, by measuring from outside: the time of an answer rose by
  0.051 s for every run already made, and the sandbox's time did not. Then, on this branch, the front door's own steps were
  timed while it ran, by timers put in from outside the code: over 30 submissions the governed run took 0.53 s, then 0.40 s
  throughout; the reading of the runs after it, `attempts_of`, took 0.070 s for the first and 1.387 s for the thirtieth.
- **The first form** (`3ec6132`): the reading in one transaction, with R28 at 4 checks and F36 at 3. Thirty submissions
  then took 0.445 s for the first and 0.465 s for the thirtieth, and the reading 0.021 to 0.033 s. Both tests were run
  against the code as it was before, `verify_record.py` of `bc33c4b`: R28 failed its check of the connections (11 for 2
  runs, 71 for 14), and F36 its check of the time (0.858 s more), and each passed its other checks. Its full runs, 23:58:53
  to 00:06:21: the gate's suite, 28 of 28 tests and 215 of 215 checks; the front door's, 36 of 36 tests and 192 of 192
  checks, F17 making its case at its first try; the four whole-gate tests each exited 0.
- **An independent review** of `bc33c4b` to `3ec6132`, by a separate agent, which read the code and the store's tables and
  made one reading of the database, and ran no test. It reported nothing of medium weight in the change: the reading is the
  same for every caller, each table's key allows no row to be read twice or lost, every role holds the grant it needs, and
  the readings are of one moment where they were of many. It reported three things of lower weight:
  1. *R28's docstring said the reading costs the same whatever the number of runs*, where only its connections do. Corrected.
  2. *R28 read no run without a result and none that was interrupted.* Corrected: it now makes one (below).
  3. *F36, a test of time, can be wrong both ways*, and other work of an answer still grows with the runs made. Both are
     stated under "What stays open".
- **Its pass of deliberate defects**, 00:07:14 to 00:12:56: nine defects and a control, each run against R28 and F36. Seven
  were caught, and the control passed. Two were missed:
  - T3, an attempt's reports read in the wrong order: every run R28 read had one report;
  - T8, the reports of every budget read, not this one's: no other budget held a run of the same name.

  The store, which holds the budgets of every test made on this machine, showed both to be real: 712 attempts there have
  more than one report, and about a hundred names of runs are held by more than one budget (all of other tests; in this
  product a run's name is made from its baseline).
- **The second form** (`d1cfb34`): R28 changed, and nothing else. Its host is stopped during its first run, so that one run
  is interrupted and has no result. After the record is checked, the test puts into the store, with the owner's role, a
  second, earlier report for one run, and a report and a receipt for a run of the same name under a second budget, and
  reads again. R28 has 5 checks. A first try at this used the roles of the services, which may not write a report, and was
  refused; and it took a function from the wrong module. Both were corrected before any run was recorded. Its full runs,
  00:16:12 to 00:23:12: the gate's suite, 28 of 28 tests and 216 of 216 checks; the front door's, 36 of 36 tests and 192 of
  192 checks, F17 making its case at its first try; the four whole-gate tests each exited 0.
- **Its pass of deliberate defects**, 00:24:05 to 00:30:46, caught 8 of 9, with the control passing. T3 was now caught. T8
  was still missed: the other budget's report had been put at a decision numbered far beyond this budget's log, and a
  reading leaves out what lies beyond its log, so the report could not have shown. And with T5, no result read, R28 stopped
  with an error where it should have failed a check: it looked for a run that had failed, and found none.
- **The third form** (`ab7df76`): R28 changed again, and nothing else. The other budget's report is put at its decision 1,
  and where no run reads as failed R28 goes on and its checks fail. T5, T8 and the control were run again at once: both
  caught, and the control passed. This is the code this declaration carries. Its full runs, 00:33:59 to 00:41:05: the gate's
  suite, 28 of 28 tests and 216 of 216 checks; the front door's, 36 of 36 tests and 192 of 192 checks, F17 making its case
  at its first try; the four whole-gate tests each exited 0.
- **Its pass of deliberate defects**, 00:41:55 to 00:48:19, caught 9 of 9, with the control passing.
- The defects are kept in `verify/dev_amend13_mutants.json`, which names, for each, the checks that caught it.
- **What no reviewer has read.** The second and third forms' changes to R28 were read only by their author.

## What stays open

- **An answer still does work that grows with the runs already made; it is the connections that no longer grow.** Each
  reading still moves every row of the budget's log, attempts, evidence, receipts and results, and reads and hashes every
  line of the journal. The governor reads the budget's state several times for each run, and the witness once for each
  decision. Over 30 runs none of this showed in the time of an answer (0.445 s for the first, 0.465 s for the thirtieth).
  What it comes to at thousands of runs was not measured.
- **F36 measures time, and a test of time can be wrong both ways.** It can fail where nothing grows, if the machine's load
  changes between its first and its last answers. It passes a growth of less than about 0.0125 s for each run. R28, which
  counts connections, depends on no clock, and it is R28 that shows the repair; F36 shows its effect.
- **F17 is as it was.** It still makes its case by two runs ending within one second. This amendment makes that likelier
  and does not make it sure.
- **The amendment of Amendment 12 says something untrue**, that when F17 fails each of its runs takes about a second. No run
  did. It is corrected in the amendment after this one, with F17, not in place.
- **The two transactions of a reading are not one.** The log and state are read in one, the stored rows in a second, a
  moment later, as before this change (when the rows were read in many). Rows of decisions made between the two are cut off
  by the log's length, as before.
- **The store still opens a connection for every call.** That is the gateway's, and is not changed here. Other code that
  calls the store once for each of many things would slow in the same way; one such place is known, the front door's look
  for interrupted runs, which reads the evidence of each run left without a verdict, and only of those.

## What is not tested

- A baseline with hundreds or thousands of runs. R28 reads 15 and F36 makes 25.
- An attempt with no rows at all, or still pending, read both ways. R28 reads an interrupted run, which has no result, and
  a run with two reports; none without any report or receipt.
- A run with two reports made by the service itself. R28's second report is put into the store by the test, with the
  owner's role, as are the other budget's rows: in this product a run's name is made from its baseline, so two budgets do
  not share one, though the store has budgets of other tests that do.
- A reading made while a run is being decided, between its two transactions.
- A role other than the local one reading the three tables. Every caller uses the local role; the others hold the same
  grant, which no check uses.
- The record's builder and the engineer's console, timed. They call the same reading; only the front door's answers are
  timed, by F36.
- What the witness, the governor and the journal cost at many runs.

## Commands and results

The official runs are these, each once, from the tree at the commit that carries this declaration, as root, with the services
on 127.0.0.1 and PostgreSQL 16, with the interpreter of the project's virtual environment, which holds the cryptography
library (the machine's own `python3` does not, and Amendment 12's declaration did not say which was meant), on a machine
whose file table has been raised for this start of the machine as the sandbox requires
(`sysctl -w fs.file-max=9223372036854775807`), and with no run of the sandbox's left on it:

    cd tests && <venv>/bin/python -B verify_tests.py
    cd tests && <venv>/bin/python -B verify_front_tests.py

Before each command the output file it will write is removed, so that a command that fails to start leaves nothing to be
taken for a result. Each output file is copied to `verify/results_verify_tests_amended13_2026-11-20.json` and
`verify/results_front_tests_amended13_2026-11-20.json`. The outputs folder is not committed.

Expected: for the gate, 28 of 28 tests and 216 of 216 checks; for the front door, 36 of 36 tests and 192 of
192 checks. A check that comes out other than expected is reported as it came out, in the amendment that follows the
runs, and is not run again under this declaration.
