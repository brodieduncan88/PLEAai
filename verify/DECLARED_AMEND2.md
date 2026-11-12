# Amendment 2: declaration before the official test runs

12 November 2026. Private working material.

This file is committed before the official runs of `tests/verify_tests.py` and `tests/verify_front_tests.py` on the branch
`verification-amendment-2`. It fixes the changed code, states what each test is expected to show, and records what was
done in development. Each official run is made once after this commit and its first result is kept, pass or fail. A
later correction would be a separate, dated amendment.

## Why declared files are changed

`AMENDMENT_2026-11-11.md` left its Finding 3 open: a stored baseline changed into something that is no longer a card
gave a run with no verdict and no notice to the engineer. Its repair is in `verify_tools.py`, a file fixed by
`DECLARED_VERIFY.md`. On 12 November the owner asked for it to be repaired. That is done here, under this declaration.

Before anything was changed, the ways a FAIL or an UNKNOWN can fail to reach the engineer, and the ways a record can be
left unable to verify, were looked for again. Three more defects were found. They were not asked for. They are
repaired here too, because each breaks the same two promises as Finding 3 and two of them can be caused by a caller
through the front door. They are numbered on from Amendment 1.

- **Finding 3 (asked for).** A stored baseline that is unusable in any way. Amendment 1 named one kind of error and
  said the repair was one line. That was too narrow: three kinds of error left the tool, and the words of two of them
  quote the changed file.
- **Finding 4 (new).** A notice could be written over another. A notice's file name was the time to the second, the
  verdict and eight digits of the design's hash. Two failures in the same second whose hashes share those digits had
  the same name, and the second replaced the first. A caller through the front door can find such a pair of designs
  inside the design space in under a second of computing.
- **Finding 5 (new).** A number in a design could leave a record unable to verify. The front door accepted any finite
  number. The database holds a number as a decimal: it hands back 1e22 as a whole number and -0.0 as 0.0. The stored
  result then no longer matches what the gate signed, the record of that baseline fails its check 6 from then on, and
  the same design sent again is refused by the service. This is the effect of Finding 2 by a route Finding 2 did not
  list. **The statement in Amendment 1 and in `REPORT_FRONT.md` that Finding 2 is closed for a caller through the front
  door was wrong for these numbers.** The failure itself still reached the engineer.
- **Finding 6 (new).** What a baselined check prints. `baseline.py` says a check that prints anything but one usable
  result is UNKNOWN. For output it could not read at all (nested very deep, or a number written with an exponent of a
  million) it raised an error instead, with the effect of Finding 3. And a check that printed a NUL or half a surrogate
  pair in its basis, or stopped with such bytes in its last message, produced a verdict that could not be stored or
  could not be written in a notice. And a value given to more than 28 significant digits got a verdict that the
  record's checker rejects. Only the engineer's own check can cause these; a caller cannot.

None of the four let a design that does not meet its requirement be shown as met by a record that verifies.

The earlier declarations, reports, results and Amendment 1 are not changed. They say what was known when they were
written.

## What is changed, and what is fixed

Base: `verification-mcp-front-door` at `6e34364`. Four declared files change.

| file | fixed by | sha256 before | sha256 now |
| --- | --- | --- | --- |
| `verify/verify_tools.py` | `DECLARED_VERIFY.md` | `33a6b31c1650eb73…` | `f6fe01e6022192d4e1b2c727f777f2c1a6f96fac32bbe5109c9fe2a3eacdfb5d` |
| `tests/verify_tests.py` | `DECLARED_VERIFY.md` | `6b24ecc12979c882…` | `335f1ce2778f738587a4e29899bf8b3aa8520513487c92afc30dd2ef83426a41` |
| `verify/front_door.py` | `DECLARED_FRONT.md` | `a9db5e29c08d6e76…` | `b8abe3dbc0162e91f7cd9452417f91d8a086d3c0116bb0875695178287ef626f` |
| `tests/verify_front_tests.py` | `DECLARED_FRONT.md` | `ddcd6bd853fcb58f…` | `b5ec3f9db186fc8c3a1e6ea582675dfb72321fa9eb2e834f7c1b37863474171e` |

One file is new: `verify/dev_amend2_mutants.json` (sha256 `2c3c6c0b26aea7b931bb444053e7c3a975a32bcda3f8b27eb797524879a61783`), the first pass of the deliberate defects.

Every other file listed in `DECLARED_VERIFY.md` and `DECLARED_FRONT.md` has the hash given there, and `git diff 6e34364` is
empty for the gateway, the checker, the record builder, the first client, both consoles, the MCP server, the fixture and
every earlier document and result.

The script that wrote this file compared every top-level statement of the two test files (each function, class, constant
and import) with the same statement at `6e34364`, one by one.

- `tests/verify_tests.py`: 43 statements are unchanged, the functions of R1 to R13 and the deployment they use among them.
  Changed: the opening description and the list of tests. Added: R14, R15, R16 (with the script it runs) and one import.
- `tests/verify_front_tests.py`: 65 statements are unchanged, the functions of F1 to F14 and F16 and the deployment they use among
  them. Changed: the opening description, the list of tests, and F15, which has two steps added and two checks restated
  (below). Added: F17, F18, F19 and two helpers.

The repair, in the order of the code:

1. `verify_tools.py`, reading the stored baseline. The existing clause is left as it is. After it, any other error is
   answered with the same signed UNKNOWN (reason BASELINE_MISMATCH) and the engineer is sent it. The words are fixed,
   one of four short phrases chosen by the kind of error. Nothing from the stored file is repeated. Before the
   existing clause, a file that cannot be opened is given fixed words too: the error's own words held the path of the
   service's folder. For a file that is not JSON, or is a card that fails its signature, the reason is still the
   reader's own message. It can hold a position in the file, the value of one byte or a count, and none of its text.
2. `verify_tools.py`, running the check. Any error while the check is run or its output is read is answered UNKNOWN
   (reason CHECK_ERROR), in fixed words that name only the kind of error. The text in a verdict's basis and reason,
   which a check or a card can supply, is made printable: a space of any kind becomes a plain space, and any other
   character that is not printable (a control or format character, a line break, half a surrogate pair) is written as
   its escape. Then the verdict is put to the record's own checker. One the checker would not accept, such as a
   value given to more than 28 significant digits, becomes UNKNOWN (reason CHECK_OUTPUT_INVALID). If the check cannot
   be run for a design the checker finds outside the design space, the answer is FAIL (DESIGN_OUTSIDE_BASELINE), the
   only one the checker accepts for such a design.
3. `verify_tools.py`, writing a notice. A notice is created and never replaced. If the name is taken the notice gets
   `_2`, `_3` and so on after it. It is written as UTF-8 whatever the locale of the process.
4. `front_door.py`, its own reading of the stored file. Any error is treated as "no usable card": nothing is shown from
   the file, and a design sent still goes to the gate, which decides and notifies. Before, a file nested very deep
   stopped the request at the front door.
5. `front_door.py`, numbers. A number written with a decimal point or an exponent is refused if it is 1e16 or more in
   size, or is negative zero. A whole number of up to 4300 digits is kept as written and is accepted; a longer one was
   and is refused as not being JSON. A number is read as the nearest double, as before, and is decided and shown as that.

Environment: Python 3.11, cryptography 50.0.2, psycopg 3.3.8, PostgreSQL 16, one machine, all services on 127.0.0.1.

## What each test is expected to show

**R1 to R13** are as declared in `DECLARED_VERIFY.md`: the same functions, the same 53 checks, each expected true.

**R14. A stored baseline that is no longer a card at all gives a signed UNKNOWN and a notice, like any other changed baseline: never an interrupted run, never a pass.**
- each of fourteen unusable stored baselines is answered UNKNOWN (exit status 3), not interrupted and not a pass
- the tool returned a verdict every time and the gate host kept running
- the record holds fourteen UNKNOWNs with the reason BASELINE_MISMATCH, and no run without a verdict
- every one of them was sent to the engineer, in a notice that is not empty
- no notice carries a line of its own from the changed file; and no word of the file, and no path of the service's own folder, is in an answer, in the record or in a notice
- with the file restored a failing design fails and a good design meets the check
- the record verifies: fourteen unknown, one not met, one met, and met for that design only

**R15. Whatever a baselined check prints, the answer is a signed verdict that can be kept and checked again, and a notice: never an interrupted run, never a record left unable to verify.**
- a check whose output cannot be read at all is answered UNKNOWN: THE CHECK DID NOT RUN TO A RESULT (exit status 3), not an interrupted run
- a check that stops with unprintable bytes in its last message is UNKNOWN in the same way
- a check that gives a value to 38 significant digits, which cannot be written exactly, is UNKNOWN: THE CHECK GAVE NO USABLE RESULT, not a FAIL the record's checker would reject
- a check that prints a NUL, half a surrogate pair, line breaks of three kinds, a direction mark or DEL in its basis still gets its verdict: FAIL for the failing design, DECLARED CHECK MET for the good one
- the tool returned a verdict every time and the gate host kept running
- each FAIL and UNKNOWN was sent to the engineer: nine notices, none empty, none with a line of the check's own or a character that is not printable
- what the check said is kept, in the record and in the five notices of a FAIL: each character that is not printable written as its escape, a no-break space as a plain space, and a degree sign as it is
- the record verifies: four unknown (three CHECK_ERROR, one CHECK_OUTPUT_INVALID), five not met, one met, and nothing unprintable is kept in it

**R16. From the inside, the tool called directly with no services: its guards take an error of any kind, a verdict the record's checker would reject is not returned, notices of one name are each kept, and a notice is written under a locale that is not UTF-8.**
- the tool called directly decides the plain failing design as the services do: FAIL, LIMIT_NOT_MET, one notice
- an error of a kind no other test makes, while the stored baseline is read, is the signed refusal UNKNOWN / BASELINE_MISMATCH with a notice, in fixed words that do not repeat the error's own
- the same error while the check is run is UNKNOWN / CHECK_ERROR with a notice, naming the kind of error and not its words; for a design outside the design space it is FAIL / DESIGN_OUTSIDE_BASELINE, the only answer the record's checker accepts for one
- a verdict the record's checker would reject (a margin that does not recompute) is not returned: UNKNOWN / CHECK_OUTPUT_INVALID with a notice
- five results of one name in one second give five notices, named in turn, each holding its own text
- under a locale that is not UTF-8 the notice of a FAIL, which holds text outside ASCII, is still written

R15 uses a copy of the fixture's check with eight more ways to misbehave, written by the test into a folder of its own.
The declared fixture files are not changed. R16 starts no service: it calls the tool in a process of its own, with a
stand-in that raises where the stored baseline is read or the check is run. It is a test from the inside.

Expected: 16 of 16 pass (74 checks).

**F1 to F14 and F16** are as declared in `DECLARED_FRONT.md`: the same functions and checks, each expected true. F1 and F2
still pass because the first client still has the two defects they describe.

**F15. A stored baseline changed after it was signed is not shown, and a design sent against it is decided UNKNOWN by the gate, counted, and sent to the engineer.**
- the changed baseline is not shown, by address or by tool
- a design that the relaxed card would pass is decided UNKNOWN by the gate, not a pass
- so is one sent against a relaxed card properly signed by another key, and the runs are counted
- with the file restored the requirement is shown again and still fails
- all three results were sent to the engineer
- a stored file that is no longer a card at all, or is nested too deep to read, is not shown, and a design sent is decided UNKNOWN by the gate in the same way and sent to the engineer (Amendment 2)  *(restated)*
- no run met the check, the record verifies and the status is NOT VERIFIED

F15 as declared on 11 November had a check that stated the defect:

> known gap, not closed here: a stored card that is no longer a card gives a counted run with no verdict, not a pass, and no notice

It is replaced by the check marked above, which states the repaired behaviour, for the same stored file and for one more,
nested too deep to read. The last check of F15 keeps its words; the list of outcomes it expects changes from one FAIL,
one interrupted run and two UNKNOWN to one FAIL and four UNKNOWN. The other five checks of F15 are unchanged.

That check was the only one that showed a tool stopping with an error inside a running gate host. F19 now shows it, for
a limit that is left: an inbox that cannot be written. F19 passes when that limit is present, which is what is expected.

**F17. Two failures whose notices would once have had the same file name both reach the engineer: a notice is never written over another.**
- two designs inside the design space whose hashes begin with the same eight digits both fail in the same second
- each has its own notice: two files with different names, neither empty, each naming its own design
- the inbox holds one notice for every failure, and the record verifies with all of them

**F18. A number the database would hand back changed is refused before anything happens, so it cannot leave a record unable to verify.**
- each of nine numbers the database would hand back changed is refused (400), and so are three nested inside the design, a negative zero among them
- through the tool and the command line such a number in a design not sent before is refused, and each answer says nothing was recorded
- nothing happened: no run of the check, no audit row, no notice
- seven numbers beside them are decided: each a signed FAIL for a design outside the baseline, sent to the engineer, and the same answer when sent again
- a good design then meets the check, and the record verifies: eight runs, DECLARED CHECK MET
- the rule matches the database: of 872 numbers, the front door accepts a number exactly when the database hands it back as written, and some of each kind are in the sample

**F19. Known limit, not closed: when the engineer's inbox cannot be written, a run is counted with no verdict and no notice.  It is never a pass, and the record verifies.**
- with the inbox in place a failing design is FAIL
- with a file where the inbox folder should be, the next failing design is answered UNKNOWN: THE RUN WAS INTERRUPTED: counted, not met, and not marked as a tool error
- the same design sent again is the same interrupted run, and the check is not run a second time
- no verdict was returned for that run and no notice was written for it: this is the limit
- with the inbox put back the next failing design is FAIL and is sent to the engineer
- no run met the check, the record verifies with the interrupted run in it, and the status is NOT VERIFIED

Expected: 19 of 19 pass (98 checks).

F17 needs two runs to fall in the same second. It tries up to six pairs of designs, starting each pair just after a
second begins. A run takes about 0.37 s here, so the second notice is written about 0.7 s into the second. On a slower
or busier machine no pair may fit, and the test then fails; it does not pass by default.

## What was done before this declaration

All of this was on 12 November 2026, times in UTC. The repair and the tests were worked out in scratch copies outside
the repository. The repository's files were changed once, by a script of exact replacements, just before this file was
written.

- **Looking before changing.** A direct call of the tool confirmed two kinds of error leaving it for a stored file that
  is no longer a card. Seven AI agents were then set to map, without changing anything, every way a FAIL or an UNKNOWN
  can fail to reach the engineer. Five reported; two did not run, because of a usage limit. What they found:
  - three kinds of error leave the tool for an unusable stored file, not one, and the front door's own reading of the
    file missed one of them;
  - the words of those errors quote the changed file;
  - a notice can be written over another (Finding 4). I had met the same thing a few minutes earlier, when a probe
    that sent one design twice in a second showed one notice;
  - numbers the database hands back changed (Finding 5). I confirmed it against the running services, one new baseline
    for each of fourteen numbers: five left their record unable to verify, nine did not;
  - the same failure from the check's own output (Finding 6).
- **Mistakes of mine, found by those agents or by running.**
  - My first repair passed the error's own words into the verdict. Those words can quote the changed file, a NUL
    included, which would have put the file's text into a signed verdict and re-made the defect. Fixed words replaced it.
  - A deliberate defect I planted to test the tests was not the defect it described, so its result meant nothing. It was
    re-made.
  - My first R14 would not have noticed a repair that quotes the changed file once the text is printable and on one
    line. A fourteenth kind of file and a check were added.
  - A check I added for the service's path passed on the unrepaired code, because the old words are cut short and the
    path was long. It now looks for the start of the path.
- **A second set of AI agents reviewed the repaired copy,** each under one lens: the tool, the front door, whether the
  tests can fail, whether anything already declared is disturbed, and an attacker who holds one job's certificate.
  Four looked at an earlier copy of the repair; the attacker's lens also ran everything on the repair as it then stood. For
  two of the lenses a second agent tried to refute each serious finding; for the other three that step did not run,
  because of the usage limit. None found a way, through the front door, to lose a notice, spoil
  a record, get a failing design answered as met, or make the tool stop. Two more agents then reviewed only what had
  changed since. One reported: over about 14,000 cases in process it found none where the tool changes a verdict the
  record's checker accepts. The other did not run (the usage limit), so the last changes to the tests were checked by
  me alone, by running them against the unrepaired code and by the deliberate defects below.
  What was changed for them:
  - the guard round the check answered UNKNOWN for a design outside the design space, which the record's checker
    rejects. It could be reached only by a design nested about a thousand deep, which the front door refuses. The
    guard now asks the checker's own design-space test;
  - a check that gives a value to more than 28 significant digits got a verdict the checker rejects. That is old
    behaviour of `baseline.py`. The tool now puts every verdict to the checker before returning it;
  - the existing clause's words carried the path of the service's folder when the stored file could not be opened;
  - the text helper wrote a no-break space as an escape; it now writes any space as a plain space;
  - nine wrong versions of the repair would have passed the tests as they stood. R15, F15 and F18 were tightened and
    R16 was added;
  - with F15 restated, nothing showed a tool stopping with an error inside a running gate host. F19 was added.

  What they found that is left open is under "What stays open".
- **Full runs in development.** Both test files were run in full seven times. Six were on scratch copies as the repair
  grew: 14 and 16 tests, 14 and 17, 14 and 18, 15 and 18 twice, 16 and 19. The seventh was in the repository after the
  script was applied, from 02:55 to 02:59: 16 of 16 tests and 74 of 74 checks, 19 of 19 tests and 98 of 98 checks. Each of
  the seven passed in full. Parts of the files were run many more times, and some of those runs failed while a test
  or the repair was being written. Each new or restated test was also run against the unrepaired tool and front door:
  R14, R15, R16, F15, F17 and F18 fail there. F19 passes there too, because it states a limit both have.
- **Deliberate defects.** Three passes were made. Eight defects against the first draft: all caught, but one was the
  mis-made one above. Eighteen against a later copy: all caught. The pass reported below is the third, of thirty. It
  stopped at the sixth defect, because that defect's edit no longer matched a line that had gained a log message; the
  edit was corrected, every edit was checked to match the code, and the pass went on from the sixth. After the pass,
  two lines were added to the front door so that a log line that cannot be written does not stop a request. The six
  defects planted in the front door were then run again, on the code declared here, and were caught again. The other
  twenty-four were run against the tool and the tests exactly as declared.

To check that the tests can fail, 30 deliberate defects were applied one at a time to a scratch copy of the repaired code, and
R5, R14, R15, R16, F7, F15, F17 and F18 were run against each. All 30 were caught at the first pass.
`dev_amend2_mutants.json` holds that pass. The defects were chosen by the party that wrote the code. They show the tests
can fail; they do not show the tests are enough.

| | deliberate defect | caught by, at first |
| --- | --- | --- |
| A1 | the repair is taken out: the tool again names only four kinds of error | F15, R14, R16 |
| A2 | the repair names only a card that fails its own rules (BaselineInvalid), not a part of the wrong kind or a file nested too deep | F15, R14, R16 |
| A3 | the repair puts the exception's own words, which can quote the changed file, into the verdict and the notice | R14, R16 |
| A4 | a notice is written over an earlier one of the same name, as before | F17, R16 |
| A5 | when two notices would share a name the second is not written | F17, R16 |
| A6 | the front door's own reading of the stored file names six kinds of error, as before | F15 |
| A7 | no notice is sent when no usable baseline is held | F15, R5, R14, R16 |
| A8 | an unusable stored file is answered as a design outside the baseline (FAIL), not as UNKNOWN | F15, R14, R16 |
| A9 | the front door accepts any finite number, as before | F18 |
| A10 | the front door refuses a large number but lets negative zero through | F18 |
| A11 | the front door's limit for a number is ten times too high (1e17) | F18 |
| A12 | the front door refuses every number written with an exponent, though most of them can be kept as written | F18 |
| A13 | the guard round the check is taken out: a check whose output cannot be read leaves the tool by an exception | R15, R16 |
| A14 | text the check supplies is kept as it came, unprintable characters and line breaks included | R15 |
| A15 | text the check supplies keeps its line breaks; only other unprintable characters are written as escapes | R15 |
| A16 | the repair names a broken rule and a wrong kind of value, not a file nested too deep | F15, R14, R16 |
| A17 | the repair quotes the changed file after all, made printable and kept on one line | R14, R16 |
| A18 | the new refusal does not name the baseline it was asked for | F15, R14, R16 |
| A19 | the tool does not put its verdict to the record's checker before it answers | R15, R16 |
| A20 | a stored file that cannot be opened is answered in the error's own words, the path of the service's folder among them | R14 |
| A21 | a space that is not the plain one is written as an escape, and so is every character outside ASCII | R15 |
| A22 | only characters below a space and half surrogate pairs are written as escapes: other line breaks, direction marks and DEL are let through | R15 |
| A23 | the text a check supplies is thrown away, not made printable | R15 |
| A24 | the front door looks for negative zero only among the design's own values, not inside them | F18 |
| A25 | a third notice of the same name is written over the second | R16 |
| A26 | the repair names exactly the three kinds of error the stored-file tests make, not any error | R16 |
| A27 | the guard round the check names exactly the two kinds of error the check tests make, not any error | R16 |
| A28 | the guard round the check repeats the error's own words | R16 |
| A29 | a notice is written in the encoding of the locale, as before | R16 |
| A30 | when the check cannot be run for a design outside the design space the answer is CHECK_ERROR, which the record's checker rejects | R16 |

- No load or stress test was made.

## What stays open

Found in this work and not repaired. Grouped by who can cause it.

- **A caller through the front door.** No request was found that loses a notice, leaves a record unable to verify, gets
  a failing design answered as met, or makes the tool stop with an error. These were found and are left:
  - *Words of the sender's own inside a notice.* A design's names and text values are written as sent into the reason
    and the design line of a notice, and into the checker's print of a record. They cannot hold a line break. But a name
    can be a sentence that reads like the service's, and padded with plain spaces it can fall at the start of a row in a
    window of a chosen width. The first line of the notice, its verdict line and its closing lines are the service's
    and still say FAIL. The repair is to quote and cut what a design supplies, in `baseline.py` and `check_record.py`,
    which are not changed here.
  - *A journal with no size limit.* The front door writes every design it accepts to a journal in the service's home,
    also when the same design is sent again. At the rate the front door allows, one certificate can add about 3 to 8 GB
    a day. A full disk is the limit described two items below, for every job on that machine.
  - *Two spellings of one number* (3 and 3.0) are two designs, each an official run with its own notice.
  - *The record builder prefers the journal's copy of a design* to the one in the signed verdict, under a key of 96
    bits. Two designs with the same key, which would take about 2 to the power 48 hashes to find, would leave a record
    unable to verify until it is built again without the second journal line. Not tried.
- **Runs already interrupted by Finding 3 stay interrupted.** The gate decides an attempt once. A run that was left
  without a verdict before this repair stays on the record as interrupted, and nobody is sent a notice for it now. The
  repaired tool is used for new attempts only, and only once the gate host has been started again, on the same state
  file.
- **A machine that cannot write.** If the inbox or the tool's ledger cannot be written (a full disk, a changed
  permission, a file where the folder should be) the tool stops with an error: the run is counted with no verdict and
  no notice is written. F19 shows it. A notice is a file in a folder; this repair does not add a second way to reach
  the engineer. If writing stops part-way, an empty or part-written notice file is left.
- **Someone who can write the service's files.**
  - A named pipe, or a file without end, put in place of the stored baseline, the check or its data makes the tool
    wait for ever. Nothing read there has a size limit, and the gate host has no time limit of its own; only the
    check's own run has one.
  - The front door's own list of jobs, nested very deep, makes the front door drop the connection with no answer.
    Nobody is admitted and nothing is run. Its journal of submissions, damaged in the same way, makes the status and
    the answer to a submission fail after the run has been made and its notice written.
  - Parts added to a stored baseline outside what the engineer signed (another top-level name) are handed out by the
    front door with the signed envelope, and are copied into a record built from it. The requirement, the status and
    every verdict are not affected.
  - A binding signed with the engineer's key that names one baseline and another baseline's budget is noticed by the
    front door, and the design is still sent on. The engineer's console never writes such a binding.
- **The engineer's own tools and cards.**
  - For some unusable stored files the engineer's console (`verify_ctl.py`, `front_ctl.py`) and the first client stop
    with a Python traceback where a plain refusal was meant. Nothing is built or signed. After a notice that no usable
    baseline is held, the stored file has to be restored from the signed copy before a record can be built or a run
    acknowledged.
  - While another job's stored baseline is unusable, `front_ctl.py enrol` leaves that job out of its rule that a
    second job for the same requirement needs a reason, and enrols the second job without one.
  - A card can be signed whose stated limits are not text. A design that meets its check is answered; one that fails
    cannot be set out in a notice, and the run is counted with no verdict and no notice. Such a card should be refused
    when it is baselined; `baseline.py` is not changed here.
  - A check that gives a value to more than 28 significant digits is still accepted when it is baselined, because
    baselining runs `baseline.py` directly. Every later run on it is then UNKNOWN, and a control whose value rounds
    across its limit would be recorded in a way the record's check 2 rejects.
  - A check that prints a number with an exponent just under a million gets a reason about a million characters long.
    Whether every part keeps a verdict of that size is not tested.
  - If the check cannot be started at all, the reason given is the error's own words, which can hold a path on the
    service's machine (`baseline.py`, unchanged).
- **The service's own log.** An error that the tool answers in fixed words leaves only its kind in the verdict. Its
  message is not written anywhere on the service's machine, so whoever looks into it has the kind of error and the
  notice to go on.
- **The first client.** It still has the two defects of Amendment 1 and must not be what an assistant is given. Through
  it, and not through the front door, a caller can also send a design holding half a surrogate pair (the notice cannot
  be written), a design nested very deep, arguments of the wrong shape, a baseline hash that is not 64 hex digits (an
  UNKNOWN with no notice, as written), or a made-up hash that shares its first sixteen digits with a real one (the
  notice lands in the real one's inbox). Finding 5 is repaired at the front door only: the first client still accepts
  such numbers.

## What is not tested

- **Two gate hosts writing to one inbox at the same moment.** That a notice is never replaced rests on the operating
  system creating a file only if it does not exist. F17 and R16 show notices of one name written in turn, not at once.
- **Every number.** The last check of F18 compares the front door's rule with the database for 872 numbers. It does not
  prove the rule for all of them.
- **Every unusable file, and every odd output.** R14 tries fourteen kinds of stored file and R15 eight kinds of
  output. R16 makes an error of another kind, from the inside, with a stand-in. The repair takes any error; the tests
  show the kinds listed.
- **A design nested about a thousand deep,** which only the first client can send. One probe, in process, found the
  tool either answering FAIL for a design outside the design space or stopping at its first ledger line, as before.
- **R16 is from the inside.** It calls the tool directly, with no gate host, no witness and no database of runs.
- **The demonstrations and the trial of 30 assistant runs** were made with the tool as it was and are not made again
  as evidence. Both demonstrations were run once on the repaired code as a check: they end as before, and their
  transcripts differ from the committed ones only in hashes, times and the order of two rows sorted by a hash.
- **An assistant, or a host product; separation by machine; any independent review.** As in `DECLARED_FRONT.md`. The
  reviews named in this file were made by AI agents working for the party that wrote the code.
