# Amendment 5: declaration before the official test runs

13 November 2026. Private working material.

This file is committed before the official runs of `tests/verify_tests.py` and `tests/verify_front_tests.py` on the branch
`verification-amendment-5`. It fixes the changed code, states what each test is expected to show, and records what was
done in development. Each official run is made once after this commit and its first result is kept, pass or fail. A
later correction would be a separate, dated amendment.

## Why declared files are changed

`DECLARED_AMEND4.md` lists, under "What stays open", that the requirement line of every notice still said "Baseline …,
unchanged.". That was so of the signed card, but in the notice of a changed check it stood under the first line
"UNKNOWN: THE CHECK OR ITS DATA NO LONGER MATCHES THE BASELINE", and three rounds of AI reviewers of the white paper
said a reader could take it for the check. On 13 November the owner asked for it to be repaired. This is that repair,
with what its review found of the same kind. It continues Finding 8, the record's eighth defect, which Amendment 4
repaired but for this word. The rule is the one Amendment 4 applied: what a notice, an answer or a record's print
tells a person must be true of the run it is about.

**Finding 8, continued. Lines a reader could take as saying what is not so.**

- The requirement line ended "Baseline …, unchanged." for every notice and answer set out from a usable card.
- The Check line gave "Hash …", the baselined hash, under a reason saying the check no longer matches it.
- When the gate held no usable copy of the card, the answer called the card the copy "this client holds"; when the
  front door prints that text, in a race, the copy is the front door's.
- The front door's own text, used when it holds no usable card, began "NO USABLE BASELINE IS HELD FOR THIS JOB" for
  every UNKNOWN, also when the gate had read the baseline and decided with its check; it ended by saying so again; and
  it printed the sender's design whole, as JSON (the last two found in this repair's review).
- And a pass, after Amendment 4, said nothing of the card at all once "unchanged" was gone (found in this repair's
  review).
- The count of a sender's names not shown called them "not the baseline's" when no baseline was held to tell, in the
  gate's own notice since Amendment 3 and in the front door's own text as first repaired here (found in its review).

The verdict, the record and its status were not affected by any of these.

**A correction to `AMENDMENT_4_2026-11-12.md`.** It says the eighth defect was found by an AI agent reviewing
revision 8 of the white paper. It was found by reviewers of revision 7, in the round whose findings made revision 8;
the review log of that round holds the finding. `AMENDMENT_4_2026-11-12.md` is not changed.

The earlier declarations, reports, results and amendments are not changed.

## What is changed, and what is fixed

Base: `verification-amendment-4` at `99e59c6`. Four declared files change.

| file | hash last declared in | sha256 before | sha256 now |
| --- | --- | --- | --- |
| `verify/baseline.py` | `DECLARED_AMEND4.md` | `8e9619e5c35d04f6…` | `0f01523d7e34bda3b31e4abf131d4286b208b92a4a4f38d6c53d05cb20e94d80` |
| `verify/front_door.py` | `DECLARED_AMEND4.md` | `3b0ed2f68ed8db94…` | `c83f281c11f556106891bbe3c8ef06b6ed0d32599cc6f9eedaf5f6c6585041e4` |
| `tests/verify_tests.py` | `DECLARED_AMEND4.md` | `80423d0000b7eefd…` | `b754fe5d860ce71b86ee9c1d4b9fd97fa5bbe765f0251077a627a43376d9f84a` |
| `tests/verify_front_tests.py` | `DECLARED_AMEND4.md` | `7e7d764650ec6c8a…` | `71376af02bbe4e46c528a8ecf44e5b077dc724715b4da4fce46e99140730a505` |

One file is new: `verify/dev_amend5_mutants.json` (sha256 `e712e6289fb511774c20869b21a98ac517c8ecbeaf1671f304d4fecb1aea89b2`), the five passes of the deliberate defects.

Every other file in the repository at `99e59c6`, 181 of them, is unchanged: the gateway, the record builder, the gate's
tool `verify_tools.py`, the first client, the consoles, the MCP server, the fixture, and every earlier document and result.

The script that wrote this file compared every top-level statement of the four changed files with the same statement at
`99e59c6`, one by one.

- `verify/baseline.py`: 39 statements are unchanged, `evaluate()` and the card's rules among them. Changed: `face()`,
  `_CHECK_FILES` (an entry for MET) and `design_lines()`, in its count line when no baseline is held.
- `verify/front_door.py`: 43 statements are unchanged. Changed: `plain_text()`, in its first line, its
  design line and its last line, and the line that imports from `baseline`, which now imports `design_lines()` too.
- `tests/verify_tests.py`: 68 statements are unchanged, the functions of R1 to R17 among them. Changed:
  `NOTICE_OLD`, `CLAIMS` and `text_claims()`, which R18 uses, and R18 itself: it passes the card and the design sent to
  `text_claims()`, holds the gate's own notice when no usable card is held to its rows, puts five kinds of design through
  `face()` in process for every reason on both cards, and adds words to three checks. New: `HEADLINES` and
  `SENT_LINE_MARK`, written out here rather than taken from the code under test, and `rows_in_order()`, `sent_patterns()`,
  `rows_known()` and `no_card_notice_known()`, which R18 uses.
- `tests/verify_front_tests.py`: 81 statements are unchanged, the functions of F1 to F20 among them. Changed:
  `NOTICE_OLD` and F21. New: `FRONT_NO_CARD`, `HEADLINES`, `OWN_TEXT_DESIGNS` and `own_text_lines()`, which F21 uses.

The repair:

1. **The requirement line** ends at the baseline's hash for a usable card: "Baseline 832eaca1ec446a74…". When the gate
   held no usable copy of the card it ends "Baseline …, as read for this answer.", which is so whether the first client
   or the front door sets the text out from its copy.
2. **The Check line** says "Baselined hash …".
3. **A pass** says, after its Verdict row, "The requirement, the limits and the load case are as baselined." and "The
   check and its data matched their baselined hashes when it ran.", as a FAIL on matching files does. A MET is given
   only by `evaluate()`, after the check's files are hashed, so both are so of every pass.
4. **The front door's own text,** used when it holds no usable card, begins with the gate's reason for an UNKNOWN that
   the gate decided with its check, and with "UNKNOWN: NO USABLE BASELINE IS HELD FOR THIS JOB" only when the gate held
   no usable card either. Its last line says which: "The gate read it as signed and decided this result." follows the
   front door's own failure to read the card only when the gate did read it. The design is set out as the gate's notice
   sets it out when no usable card is held, each value in quotes on a line marked as sent, under "the front door holds no
   usable baseline to set it against"; it was printed whole, as JSON, with the sender's names and text in it.
5. **The count line** under the sender's lines of a design with more than twelve names said "and N more names that are
   not the baseline's, not shown" also when no baseline was held to tell which names were whose: in the gate's notice
   when it holds no usable card (since Amendment 3), and so in the front door's own text, which sets the design out the
   same way. Then it now says "and N more names, not shown". With a usable card it is as before.

Nothing a sender supplies is in any changed line. A FAIL and an UNKNOWN read as after Amendment 4 but for the
requirement line, the Check line and, for a pass, the two lines after the Verdict row.

Environment: Python 3.11, cryptography 50.0.2, psycopg 3.3.8, PostgreSQL 16, one machine, all services on 127.0.0.1.

## What each test is expected to show

**R1 to R17** are as declared in `DECLARED_VERIFY.md`, `DECLARED_AMEND2.md`, `DECLARED_AMEND3.md` and `DECLARED_AMEND4.md`: the
same functions, the same 89 checks, each expected true.

**R18** is as declared in `DECLARED_AMEND4.md`, restated where its rules read the wording repaired here. `NOTICE_OLD` holds
"unchanged" too, and the old words are counted in any case. The rule that required "unchanged" in a text from a usable
card is replaced by two that hold the requirement line and the Check line each to one exact form. A new rule,
`rows_known()`, holds every line of a notice or an answer to the rows `face()` writes, in their order and number:

- the rows set out from the card are made from the card's own fields, and the headlines are written out in the test;
- the notice's address must be exactly the engineer's, and a notice has no Official runs row;
- the criteria come one to a criterion and agree with the verdict: each met for a pass, at least one not met for a limit
  not met, none evaluated for any other reason;
- the baseline's hash and the check's are the card's own, and the design's hash is the design's;
- a sender's lines stand only between the Design row and the design hash, and only in the forms `design_lines()` writes;
- a Basis row stands only for a reason for which the check printed one;
- after the Verdict row (or the Official runs row) come, line for line, exactly the sentences for that verdict;
- each criterion row agrees with itself: its margin is its value against its limit, it is met when the margin is not
  below zero, and its percentage is the margin's share of the limit; and the Reason row of a limit not met names
  exactly the rows not met, with their values;
- the Design row gives exactly the parameters of the design sent that are the baseline's own;
- in process, where the verdict is known, the Reason row of any other reason is the verdict's detail and the Basis row
  its basis.

Through the services two rows stay free text: the gate's reason for any reason but MET and LIMIT_NOT_MET, and the
check's own words inside the Basis row's quotes. On the Reason row, and on every other line of the service's own that
is not set out from the card, the design or the check, the rule for lines that say what is so looks for its words in
any case; the old words are counted in every line of the service's own. `no_card_notice_known()` holds the gate's own
notice when it holds no usable card to its rows in the same way. In process, R18 puts every reason on two cards, each
with five kinds of design, and the refusal, through `face()`. A pass is expected to say that the requirement, the limits
and the load case are as baselined and that the check's files matched. Its ten checks keep their words but for two:
the second adds "that anything is unchanged" and a clause on the notice written while no usable card is held, and the
seventh adds the five kinds of design.

**R18. A notice and an answer say only what is so for their own run: each states its verdict, says the check's files matched only when the check ran on files that did, never says that nothing was changed, says so when the service held no usable copy of the card, and a revised baseline gives every count of the runs it replaced.**
- eight runs, one for each verdict the gate gives (MET, LIMIT_NOT_MET, DESIGN_OUTSIDE_BASELINE, CHECK_ERROR, CHECK_OUTPUT_INVALID, RESULT_IMPLAUSIBLE, BASELINE_MISMATCH) and one while the gate holds no usable copy of the card, are answered with the exit status of their verdict; the seven that are not a pass each have a notice
- no notice says that nothing was changed, that the check is exactly as baselined, that anything is unchanged, or that a failure is to be accepted when the result is UNKNOWN; each notice's first line and Verdict row state its verdict, and the Verdict row says the limits were compared only when they were; the notice written while the gate holds no usable card has only its own rows
- a notice says the check and its data matched the baseline only when the check ran and its files did match, and says they were not as baselined only when they were not
- every other line of a notice that says what is so holds for its run: it says what the declared check returned against the limits only when its numbers were compared, says who may accept the result, and the notice of a changed check says the files must be restored and offers no other design
- the seven answers given to the caller say the same, the pass among them, and the last gives the count of runs so far: 8, 1 met, 2 not met, 5 unknown
- while the gate holds no usable copy of the card, the first client's answer says so: it does not call the card unchanged or as baselined, does not say the check or its data changed, and says the stored baseline is to be restored
- in process, for every verdict on two cards (the fixture and the pump station), each with five kinds of design, and for the gate's refusal when it holds no usable card, what face() writes keeps the same rules
- the revised baseline counts every run on the one it replaced, and the counts are the old record's: 8 runs, 1 met, 2 not met, 5 unknown
- the new record's print and the requirement the first client shows give all three counts, so the runs that were not failures are not taken for passes
- the new record verifies

Expected: 18 of 18 pass (99 checks).

**F1 to F20** are as declared before: the same functions, the same 104 checks, each expected true. F1 and F2 still pass
because the first client still has the two defects they describe, and F19 because the limit it states is still present.

**F21** is as declared in `DECLARED_AMEND4.md`, restated: `NOTICE_OLD` holds "unchanged" too, the old words are counted
in any case and in the pass's answer as well, and a sixth check is added, in process, for the front door's own text:
for every reason the gate gives with its card, then a missing data file, a design of many names and an empty design,
and for the gate's refusal, the text must be, line for line, what `own_text_lines()` says it should be, with the
design's rows written out in the test.

**F21. Through the front door, a notice and the tool's answer say only what is so for their run: a changed data file is said to be changed and nothing is said to be unchanged, the Verdict row states the verdict, and the requirement shown after a revision gives every count of the runs it replaced.**
- a design that fails, one that passes, and two sent while a data file of the baseline is changed (by tool and by address) are answered FAIL, met, UNKNOWN and UNKNOWN; three notices are written
- for the changed data file, the two notices and the two answers say the check or its data is not as baselined and must be restored, offer no different design, never say that nothing was changed, and state UNKNOWN on the Verdict row
- for the failure, the notice and the answer say the check's files matched when it ran and what the check returned, and state FAIL on the Verdict row; no notice or answer, the pass's among them, has the old words, in any case
- after the engineer revises and moves the job, the requirement shown gives every count of the runs on the baseline it replaced (4 runs, 1 not met, 2 unknown, 1 met) and the engineer's reason, also while the baseline is on hold; in process, other counts, none equal, are each put in their place
- the new record's print gives the same counts and the engineer's reason, and both records verify
- in process, the front door's own text for when it holds no usable card is, line for line, what is so: for every reason the gate gives with its card, a missing data file, a design of many names and an empty design among them, it begins with the gate's reason, and it says no usable baseline is held only for the gate's refusal; it sets the design out as sent and has no old words

Expected: 21 of 21 pass (110 checks).

R18 and F21 hold the wording of the repaired lines exactly. A true sentence in other words would fail them: the wording
declared here is part of what is declared.

## What was done before this declaration

All of this was on 13 November 2026, times in UTC. The repair and the tests were worked out in scratch copies outside
the repository. The repository's files were changed only by a script of exact replacements: at about 03:15, to the fifth
form as first written, and at about 04:33, after two lines of R18 were changed, set back to the base and changed again.
After each, the four changed files were compared with the scratch copy and found identical.

- **Looking before changing.** The word "unchanged" is printed in one place, the requirement line of `face()`. Nothing
  else in the repository reads that line: the record builder and the record's checker never call `face()`, the MCP
  server and the front door's client pass the text through, the demonstrations print only first lines, and no declared
  test before R18 reads the requirement line.
- **A first form of the repair,** which only dropped the word and restated three rules of R18 and F21, passed both test
  files in full on a scratch copy (01:16 to 01:20), and a first pass of planted defects, a control and eight defects
  against that form, caught all eight (01:20 to 01:28). On the unrepaired code R18 failed 4 of its 10 checks and F21 1 of
  its 5.
- **A mistake of mine, found by running.** The first attempt to run the tests failed at every check: PostgreSQL had
  stopped while the machine was idle, and the services that first attempt had started were left holding the test ports.
  They were mine; they were stopped, the database was started again, and the tests were run again. Nothing in the code or
  the tests was changed for it.
- **A review by two AI agents,** working in process with no services, each under one lens: whether every line is true
  for every reason and route, and whether the tests can fail. Neither found a false line in the repair. Together they
  found:
  - *A pass had lost its only line about the card.* After Amendment 4, the requirement line's "unchanged" was the one
    thing a pass said of the baseline; the first form dropped it and put nothing in its place. A pass now says what a
    failure says: that the requirement, the limits and the load case are as baselined, and that the check and its data
    matched their hashes when it ran. Both are so of every pass, which only `evaluate()` gives, after the files are
    checked.
  - *The Check line gave "Hash …"* under a reason saying the check no longer matches its hash; it is the baselined hash,
    and now says so.
  - *The tests guarded words, not the line.* Of the second agent's 28 wrong versions of the repair, 20 passed both tests,
    among them ", not changed." on the requirement line of exactly the notice being repaired. R18 now holds the
    requirement line and the Check line each to one exact form, and the claims-word rule to every line of the service's
    own, in any case. F21 counted the old words case by case and never read the pass's answer; it now does both. A
    sender's quoted lines are left out of the count, so that a design's own words cannot fail a correct notice.
  - *"As this client holds it"* is not so when the front door sets out the gate's refusal from its own copy, which it
    does if the stored card changes between its read and the gate's. The line now says the card is the copy "read for
    this answer", which is so on both routes.
  - *The front door's own text,* used when it holds no usable card, began "NO USABLE BASELINE IS HELD FOR THIS JOB" for
    every UNKNOWN, also when the gate had read the baseline and decided with its check. It now gives the gate's reason
    then. F21 has a new check, in process, for this.
- **A second form of the repair,** with those changes, passed both test files in full on a scratch copy (01:33 to 01:37).
  A second pass of planted defects began on it (01:37 to 01:49): the control passed and my twelve defects were all
  caught. It was stopped there, before the reviewing agent's wrong versions were run, because of what follows.
- **A re-check by a third AI agent,** in process, of the second form's tests against wrong versions of its own. Of its 14
  wrong versions of `face()`, 12 passed both restated tests. Each put a claim on a line the tests did not hold to one
  form, in words they did not look for: a second line under the requirement line, the load case line, the Check line
  before its hash, a line made to begin with the sender's mark, a pass that no longer said the check may be wrong, the
  notice of a changed check offering "a fresh design", the answer when no usable card is held calling its copy
  "verified". It proposed holding every line to the rows `face()` writes. R18 now does that, with a new rule,
  `rows_known()`; the claims-word rule stays, for the two rows that remain free text. It also found:
  - *Two correct notices the second form's tests would fail.* A design of names that are not the baseline's has the
    Design row "nothing in it is in the baseline's own words", which the claims-word rule read as a claim; and on the
    notice of a changed check, a design with a name such as "new design" was read as offering another design. The
    claims-word rule now leaves the Design row to `rows_known()`, and the next-step rule reads only the service's own
    lines.
  - *The front door's own text* still printed the sender's design whole, as JSON, unmarked, and, for a verdict the gate
    had decided with its card, still ended by saying the service's baseline could not be read as the one the engineer
    signed. F21's new check read only its first line. The front door now sets the design out as the gate's notice does
    when it holds no usable card, and ends by saying the gate read the card as signed when it did; F21 checks the whole
    text, line for line, for three verdicts the gate decided with its card and for the gate's refusal.
- **A line of the same kind, found by me** in making that repair: set out as the gate's notice does, the front door's
  design line would have begun "no usable baseline is held to set it against", also when the gate held one. It now says
  the front door holds none, which is so on both of its routes. E16 plants it back.
- **The third form.** In process, every notice and answer the gate, the first client and the front door write for every
  reason, and every reason on two cards, passed its rules, and all 14 of the re-checking agent's wrong versions failed
  them. It passed both test files in full (01:59 to 02:03), and a third pass of planted defects, the control and 57
  defects, caught all 57 (02:04 to 02:56).
- **A re-check by a fourth AI agent,** in process, while that pass ran. Of its 18 wrong versions, every one passed the
  third form's rules: a claim on a line made to begin with the sender's mark, among the sender's lines; a second Reason
  row; a claim after the closing quote of the Basis row; a criterion not met shown "-> met"; criteria not evaluated
  shown met; an answer headed "To:" and "From:" with a claim in its From: line; a notice giving zero official runs; the
  baseline's hash as the design's; a claim on the Design row of a design that is not an object; a headline changed in
  the code under test, from which the tests took the expected headline; and, in the front door's own text, lines for the
  reasons F21 did not put to it. It also found one untrue line in the repair itself: set out as the gate's notice does,
  the front door's count of a sender's names not shown called them "not the baseline's", also of the baseline's own
  names, when it could not read the card to tell. The same line, from Amendment 3, is in the gate's own notice when it
  holds no usable card. And it found correct texts the rules would fail, for cards whose own fields hold the words the
  rules look for, or an engineer's name with a comma in it.
- **The fourth form,** which answered those. `design_lines()` no longer calls the names it does not show "not the
  baseline's" when no baseline is held. `rows_known()` holds the rows in their order and number; the criteria to agree
  with the verdict; the hashes to the card and the design; the sender's lines to the forms `design_lines()` writes; and
  allows no Official runs row in a notice and a notice's address only as written. The headlines are written out in the
  tests. `no_card_notice_known()` holds the gate's own notice when no usable card is held. In process, R18 puts five kinds
  of design through `face()` for every reason, and F21 checks the front door's own text for every reason. The claims-word
  rule leaves out the rows set out from the card. All 32 wrong versions so far failed its rules, and it passed both test
  files in full (02:56 to 03:00).
- **A last check by a fifth AI agent,** in process, of the fourth form, asked for untrue lines and for slips a developer
  could make by mistake. It found no untrue line on the normal routes. Of 53 slips it tried, these passed the fourth
  form's rules and every other test as far as it could tell:
  - a refusal's Reason row reading "Every baselined limit was met", from a condition on the criteria in place of the
    reason;
  - the Reason row of a design outside the baseline left empty;
  - a failure's Reason row naming a criterion that was met, or giving the margin for the value;
  - a percentage off by a factor of 100, or taken of the wrong number;
  - in the front door, an empty design no longer said to be empty.
  It also found, by design, the Design row of a failure showing another approved material. Of the other slips, most
  failed the rules in process; 13 passed them but are caught by other declared tests (R1, R15, R16, R17, and R18's own
  checks of the notices and of the counts of runs), by its run or its reading of them; two were harmless. It found
  correct texts the fourth form would fail: a basis with a double quote in it, and ordinary words in the check's own
  basis or the criteria's names.
- **The fifth form** answered those. Each criterion row must agree with itself: its margin is its value
  against its limit, it is met when the margin is not below zero, and its percentage is the margin's share of the limit.
  The Reason row of a limit not met must name exactly the rows not met, with their values. The Design row must give
  exactly the parameters of the design sent that are the baseline's own. In process, where the verdict is known, the
  Reason row of any other reason must be its detail and the Basis row its basis; elsewhere the Basis row may hold any
  text in its quotes. F21 adds an empty design. The claims-word rule leaves out the check's basis and the criteria rows,
  but the old words are still counted in every line of the service's own. Doing so is a choice: when the count also left
  out the rows set out from the card, the old code no longer failed R18's second check. In process, every notice and
  answer for every reason passes the fifth form's rules, and every one of the 32 earlier wrong versions and the ten slips
  above fails them. On the unrepaired code the restated R18 fails 5 of its 10 checks (the second and the fourth to the
  seventh) and F21 2 of its 6 (the third and the sixth). The checks that pass there say that each run is answered with
  the exit status of its verdict, that the files are said to match only when they did, that a revised baseline counts the
  runs it replaced and the records verify, and that the four runs through the front door are answered as they should be,
  which was always so.
- **A fourth pass of planted defects,** on the fifth form (03:13 to 04:31), caught all 86, but one of them stopped R18
  with an error instead of failing it by name (below, under the passes). Two lines of R18 were changed for it: a notice
  under a headline R18 does not know is left out of the rules for notices, so that the check that counts the notices
  fails; and a number on a criterion row that the pattern lets through but that is not a number makes the row fail. With
  that defect alone, R18 then failed four of its checks by name. In process, every result above held on the code so
  changed, which is the code declared here.
- **Full runs in development.** Both test files passed in full on a scratch copy of each form, 18 of 18 and 21 of 21 each
  time: the first form (01:16 to 01:20), the second (01:33 to 01:37), the third (01:59 to 02:03), the fourth (02:56 to
  03:00), the fifth (03:10 to 03:13, and 03:04 to 03:07 before the count of the old words was made to read every line of
  the service's own again), and the code declared here (04:32 to 04:36). The fifth pass of planted defects then ran on it,
  from 04:36. The machine was restarted at about 05:05, after 34 versions; PostgreSQL was started again and the pass was
  resumed at 05:07 with the remaining 53, and the control was run once more at the end. Both test files then passed in
  full in the repository itself, 18 of 18 and 21 of 21 (06:01 to 06:05), just before this file was written.

To check that the tests can fail, deliberate defects were applied one at a time to a scratch copy of the repaired code and
the tests were run against each (R14, R17, R18, F20 and F21), with the services running. A defect counts as caught only
when a named check failed; each pass began with a control with no change, which must pass. `dev_amend5_mutants.json`
holds all five passes.

**The first pass,** on the first form of the repair: the control, which passed, and 8 defects, all caught.

**A second pass,** on the second form: the control, which passed, and 12 of my defects, all caught. It was stopped
there, before the reviewing agent's wrong versions were run, when a further review found that the second form's
tests still let wrong versions through. Its results are kept.

**A third pass,** on the third form: the control, which passed, and 57 defects; all 57 were caught.
It ran while a further agent re-checked the third form's tests, and its results are kept.

The fourth form had no pass of its own: the last review found its gaps before one was run.

**A fourth pass,** on the fifth form as first written: the control, which passed, and 86 defects, all caught. But one of
them, Y14, which changes a headline in the code under test, stopped R18 with an error (`KeyError: None`): R18 filed the
notice under its headline and found no headline it knew. It was caught by F21 by name. Two lines of R18 were then changed
so that it fails by name instead: a notice under a headline it does not know is left out of the rules for notices, so
that the first check, which counts the notices, fails; and a number on a criterion row that the pattern lets through but
that is not a number makes the row fail, where it would have stopped the test. With Y14 alone, R18 then failed four of
its checks by name. Its results are kept.

**The fifth pass,** on the code and the tests declared here: the control, which passed; my 17 defects;
the 27 wrong versions of the agent's that reviewed the tests (W), the 14 of the agent's that re-checked the
second form (X), the 18 of the agent's that re-checked the third (Y), and the 10 slips of the agent's that checked
the fourth (Z), restated for this code. All 86 were caught.
The first agent's 28th, W26, is left out: the hash it shows is the one asked for, which in every real run is the card's own.
This pass was cut off after 34 versions, at W21, when the machine it ran on was restarted; the database was started
again and the pass was resumed with the other 53, on the same copy of the code, and the control was run once more
at the end. Each version is run on its own fresh copy, so none depends on another.

The defects were chosen by the party that wrote the code, or by agents working for it. They show the tests can
fail; they do not show the tests are enough.

| | deliberate defect | first | second | third | fourth | fifth pass, as declared |
| --- | --- | --- | --- | --- | --- | --- |
| E0 | no change at all: the control, which must not be caught | passes, as it must | passes, as it must | passes, as it must | passes, as it must | passes, as it must |
| E1 | the requirement line ends "unchanged." for a usable card, as before | F21, R18 | F21, R18 | F21, R18 | F21, R18 | F21, R18 |
| E2 | the requirement line says "unchanged" only in the notice of a changed check | F21, R18 | F21, R18 | F21, R18 | F21, R18 | F21, R18 |
| E3 | the requirement line says "unchanged" for every reason but a changed check | F21, R18 | F21, R18 | F21, R18 | F21, R18 | F21, R18 |
| E4 | the answer when no usable card is held no longer says whose copy the card is | R18 | R18 | R18 | R18 | R18 |
| E5 | every notice says the card is the copy read for the answer, a usable one too | R18 | R18 | R18 | R18 | R18 |
| E6 | the requirement line says "Unchanged." with a capital | R18 | F21, R18 | F21, R18 | F21, R18 | F21, R18 |
| E7 | the requirement line says the baseline is intact | R18 | R18 | R18 | R18 | R18 |
| E8 | the no-card answer calls its copy unchanged | R18 | R18 | R18 | R18 | R18 |
| E9 | a pass says nothing of the card or the check's files, as after Amendment 4 | not planted | R18 | R18 | R18 | R18 |
| E10 | the Check line gives "Hash", as before | not planted | R18 | R18 | R18 | R18 |
| E11 | the front door's own text says no usable baseline is held for every UNKNOWN, as before | not planted | F21 | F21 | F21 | F21 |
| E12 | a pass does not say the check's files matched | not planted | R18 | R18 | R18 | R18 |
| E13 | the front door's own text ends with the old line for every verdict, also one the gate decided with its card | not planted | not planted | F21 | F21 | F21 |
| E14 | the front door's own text prints the design whole, as JSON, as before | not planted | not planted | F21 | F21 | F21 |
| E15 | the front door takes every BASELINE_MISMATCH for the gate's refusal | not planted | not planted | F21 | F21 | F21 |
| E16 | the front door's design line says no usable baseline is held, also when the gate held one | not planted | not planted | F21 | F21 | F21 |
| E17 | the count of names not shown says they are not the baseline's, also when no baseline is held | not planted | not planted | not planted | F21 | F21 |
| W1 | ", not changed." for a usable card | not planted | not planted | R18 | R18 | R18 |
| W2 | ", not changed." only in the notice of a changed check | not planted | not planted | R18 | R18 | R18 |
| W3 | ", unmodified." | not planted | not planted | R18 | R18 | R18 |
| W4 | ", unaltered." | not planted | not planted | R18 | R18 | R18 |
| W5 | ", untouched." | not planted | not planted | R18 | R18 | R18 |
| W6 | ", as signed." | not planted | not planted | R18 | R18 | R18 |
| W7 | ", verified." | not planted | not planted | R18 | R18 | R18 |
| W8 | ", current and in force." | not planted | not planted | R18 | R18 | R18 |
| W9 | ", matches the signed card." | not planted | not planted | R18 | R18 | R18 |
| W10 | ", the same as when signed." | not planted | not planted | R18 | R18 | R18 |
| W11 | ", no change since signing." only for a changed check | not planted | not planted | R18 | R18 | R18 |
| W12 | ", valid." only for a changed check | not planted | not planted | R18 | R18 | R18 |
| W13 | "UNCHANGED" in capitals | not planted | not planted | F21, R18 | F21, R18 | F21, R18 |
| W14 | "unchanged" only in the pass | not planted | not planted | F21, R18 | F21, R18 | F21, R18 |
| W15 | "Unchanged" only for a changed check (capital) | not planted | not planted | F21, R18 | F21, R18 | F21, R18 |
| W16 | before the hash: "responsible engineer; card not altered." | not planted | not planted | R18 | R18 | R18 |
| W17 | before the hash: "responsible engineer, unchanged." | not planted | not planted | F21, R18 | F21, R18 | F21, R18 |
| W18 | no-card marker reworded: ", as held by this client." | not planted | not planted | R18 | R18 | R18 |
| W19 | no-card marker moved off the requirement line to the load case line | not planted | not planted | R18 | R18 | R18 |
| W20 | no-card line adds "signed and verified" | not planted | not planted | R18 | R18 | R18 |
| W21 | no-card line adds "not modified" | not planted | not planted | R18 | R18 | R18 |
| W22 | marker inverted (said for a usable card, not for the refusal) | not planted | not planted | R18 | R18 | R18 |
| W23 | marker also on the notice of a changed check | not planted | not planted | R18 | R18 | R18 |
| W24 | the baseline hash dropped from the line | not planted | not planted | R18 | R18 | R18 |
| W25 | the whole requirement line dropped for a usable card | not planted | not planted | R18 | R18 | R18 |
| W27 | "Unchanged" on the Check line | not planted | not planted | F21, R18 | F21, R18 | F21, R18 |
| W28 | "not changed" on the Check line of a changed check | not planted | not planted | R18 | R18 | R18 |
| X1 | not-changed line | not planted | not planted | R18 | R18 | R18 |
| X2 | as-approved check | not planted | not planted | R18 | R18 | R18 |
| X3 | unaltered (other word) | not planted | not planted | R18 | R18 | R18 |
| X4 | verified files for every reason | not planted | not planted | R18 | R18 | R18 |
| X5 | second card line | not planted | not planted | R18 | R18 | R18 |
| X6 | load case line | not planted | not planted | R18 | R18 | R18 |
| X7 | check line as signed | not planted | not planted | R18 | R18 | R18 |
| X8 | check line file hash claim | not planted | not planted | R18 | R18 | R18 |
| X9 | pass says check correct | not planted | not planted | R18 | R18 | R18 |
| X10 | mismatch: try again | not planted | not planted | R18 | R18 | R18 |
| X11 | claim behind SENT_MARK | not planted | not planted | R17, R18 | R17, R18 | R17, R18 |
| X12 | check-error: ran on baselined files | not planted | not planted | R18 | R18 | R18 |
| X13 | check line unmodified | not planted | not planted | R18 | R18 | R18 |
| X14 | no-card: card verified | not planted | not planted | R18 | R18 | R18 |
| Y1 | a claim on a line that begins with the sender's mark, among the sender's lines | not planted | not planted | not planted | R17, R18 | R17, R18 |
| Y2 | the same, only where R17 does not look | not planted | not planted | not planted | R18 | R18 |
| Y3 | a second Reason row offering a fresh design for a changed check | not planted | not planted | not planted | R18 | R18 |
| Y4 | a second Reason row saying the check ran on its baselined files, for CHECK_ERROR | not planted | not planted | not planted | R18 | R18 |
| Y5 | a second Reason row calling the no-card copy verified | not planted | not planted | not planted | R17, R18 | R17, R18 |
| Y6 | the same claim on a Basis row | not planted | not planted | not planted | R18 | R18 |
| Y7 | a criterion not met reads "-> met" | not planted | not planted | not planted | R18 | R18 |
| Y8 | an answer headed To:/From: with a claim in its From: line | not planted | not planted | not planted | F20, F21, R14, R17, R18 | F20, F21, R14, R17, R18 |
| Y9 | a pass's Basis row runs on with the service's own claim | not planted | not planted | not planted | R18 | R18 |
| Y10 | a notice gives zero official runs | not planted | not planted | not planted | R18 | R18 |
| Y11 | the design hash row gives the baseline's hash | not planted | not planted | not planted | R18 | R18 |
| Y12 | criteria not evaluated are shown met | not planted | not planted | not planted | R18 | R18 |
| Y13 | a claim on the Design row of a design that is not an object | not planted | not planted | not planted | R17, R18 | R17, R18 |
| Y14 | the headline of RESULT_IMPLAUSIBLE says the limit was met | not planted | not planted | not planted | F21 (R18 stopped with an error) | F21, R18 |
| Y15 | a claim among the design lines when no baseline is held | not planted | not planted | not planted | F21, R18 | F21, R18 |
| Y16 | the front door's own text says every FAIL ran on matching files | not planted | not planted | not planted | F21 | F21 |
| Y17 | the front door's own text calls the check unchanged for four reasons | not planted | not planted | not planted | F21 | F21 |
| Y18 | the front door's own text offers another design for a missing data file | not planted | not planted | not planted | F21 | F21 |
| Z1 | MET reason when every criterion is met (all() of the criteria) | not planted | not planted | not planted | R18 | R18 |
| Z2 | LIMIT_NOT_MET branch chosen by verdict FAIL | not planted | not planted | not planted | R18 | R18 |
| Z3 | LIMIT_NOT_MET branch chosen by "there are criteria" | not planted | not planted | not planted | R18 | R18 |
| Z4 | LIMIT_NOT_MET reason lists every criterion (filter dropped) | not planted | not planted | not planted | R18 | R18 |
| Z5 | LIMIT_NOT_MET reason lists every evaluated criterion (is not None) | not planted | not planted | not planted | R18 | R18 |
| Z6 | LIMIT_NOT_MET reason gives the margin as the value | not planted | not planted | not planted | R18 | R18 |
| Z7 | percent without *100 | not planted | not planted | not planted | R18 | R18 |
| Z8 | percent of the achieved value, not the limit | not planted | not planted | not planted | R18 | R18 |
| Z9 | first design line replaced whatever it is | not planted | not planted | not planted | F21 | F21 |
| Z10 | DELIBERATE: a failing design shown with the other approved material | not planted | not planted | not planted | R18 | R18 |

E1 to E17 are mine. E1 to E8 were planted in the first pass, against the first form of the repair, E1 to E12 in the
second and E1 to E16 in the third; they are the same defects restated for the code declared here. E13 to E16 are in the
front door's own text, which the third form changes, and E17 is in the count line, which the fourth form repairs. W1 to
W28 were written by the agent that reviewed the tests, X1 to X14 by the agent that re-checked the second form, and Y1 to
Y18 by the agent that re-checked the third, each in its own words. W and X are numbered as in their agents' lists; Y1 to
Y15 are the third agent's m1 to m13, with its m1b and m4b after m1 and m4, and Y16 to Y18 its p1 to p3. Z1 to Z10 are
the slips of the agent that checked the fourth form which passed it, Z10 the one it made by design.

- No load or stress test was made.

## What stays open

For this finding:

- **Two rows are free text through the services.** R18 holds every other line of a notice or an answer to the rows
  `face()` writes, in their order and number. The Reason row of an UNKNOWN or a design outside the baseline gives the
  gate's own words for the reason, and the Basis row gives the check's. In process they are held to the verdict's detail
  and basis; through the services, where the test does not hold the verdict, a claim on the Reason row in words other
  than "as baselined", "matched", "unchanged", "nothing" and "intact" would not be caught, nor one inside the Basis row's
  quotes. The Reason row of a pass and of a limit not met is held exactly.
- **The criteria's values are held to agree with each other, not with the check.** Each criterion row must agree with
  itself (margin, met, percentage) and the Reason row of a limit not met with the rows; the value achieved is checked
  where earlier tests check it (R1, for a failure). The counts on the Official runs row are held to their form, and R18
  checks them after its eight runs.
- **A line in the exact form of a sender's line** (the mark, a name in quotes, " = " and a value) would pass where the
  sender's lines stand. It would read as the sender's, in quotes.
- **The tests hold the wording.** A true sentence in other words would fail R18 and F21, as would a new row. Changing
  what a notice says means changing these tests, under an amendment.
- **Correct texts the rules would fail.** A card whose own fields hold "unchanged" or another of the old words fails R18's
  count of them, which reads every line of the service's own. A gate's reason holding one of the words of a claim, such
  as a check's error text "nothing to read", fails the claims-word rule. A requirement statement with a line break in it
  is printed with its second line at the start of a row; the rule fails it, and the print is a fault of its own, not
  repaired here. None of the shipped cards or checks does any of these.
- **The front door's own text for a pass** gives "Reason        MET", the reason's code and not a sentence. It is so, and
  is as before; it is not repaired here.
- **The no-card notice's source.** The gate's own notice when it holds no usable card begins "To: the responsible
  engineer for baseline …" and does not say which copy could not be used. It is as before.
- **Notices written before this amendment** keep "Baseline …, unchanged." A notice is a file and is not rewritten.
- **The race at the front door is not made to happen.** The front door's own text for when it holds no usable card is
  checked in process, by F21, line for line, for every reason the gate gives with its card and for the gate's refusal;
  the race in which the stored card changes between the front door's read and the gate's is not made to happen
  in a test, as before.

Found in this amendment's last review, in code it does not change, and not repaired:

- **A data file that is present but cannot be read** (for example, the gate running as another user than the file's
  owner) is reported as missing: the notice says the check or its data no longer matches the baseline and is to be
  restored. `evaluate()` takes every error in reading a file for its absence.
- **When the gate and the front door are set up with different lists of engineers' keys,** the gate can refuse a
  baseline the front door reads as signed. The answer then says the service holds no usable copy, under the requirement
  the front door read from that copy, and asks the engineer to restore a baseline that is intact. This was found by
  reading the code, and not shown.

Everything listed as open in `DECLARED_AMEND4.md` is still open, except "Baseline …, unchanged.", which this amendment
repairs. In short: the two banners of a revised baseline give the counts in different orders; a card signed without the
counts prints "?" for them; the counts are taken when the revision is made; a CHECK_ERROR or CHECK_OUTPUT_INVALID notice
says nothing of the check's files; a sender's text is shown, up to 20 characters, in quotes, on lines marked as sent; the
front door's journal has no size limit; the first client still has the first two defects and the fifth.

## What is not tested

- **Every verdict through every route.** As in `DECLARED_AMEND4.md`: R18 sends one design for each reason the gate gives,
  and one while it holds no usable card, through the first client, and puts every reason through `face()` in process on
  two cards, each with five kinds of design; F21 sends four designs through the front door, and checks the front door's
  own text in process for every reason the gate gives with its card, a missing data file, a design of many names, an
  empty design and the gate's refusal.
- **A reader.** Whether an engineer reading a notice is in fact not misled is not tested.
- **The demonstrations and the trial of 30 assistant runs** are not made again as evidence.
- **An assistant, or a host product; separation by machine; any independent review.** As before. The reviews named in
  this file were made by AI agents working for the party that wrote the code.
