# Amendment 4: declaration before the official test runs

12 November 2026. Private working material.

This file is committed before the official runs of `tests/verify_tests.py` and `tests/verify_front_tests.py` on the branch
`verification-amendment-4`. It fixes the changed code, states what each test is expected to show, and records what was
done in development. Each official run is made once after this commit and its first result is kept, pass or fail. A
later correction would be a separate, dated amendment.

## Why declared files are changed

On 12 November an AI agent reviewing a revision of the white paper found that the engineer's notice can say the check is
unchanged when it was changed. The paper has recorded it since as the record's eighth defect, open. On 12 November the
owner asked for it to be repaired, with two limits of the same kind that the paper and `DECLARED_AMEND3.md` list. This is
that repair. The rule it applies is one: what a notice, an answer or a record's print tells a person must be true of
the run it is about. It is numbered on from Amendment 3.

**Finding 8. A notice that says what is not so of its run.** The notice of every FAIL and UNKNOWN, which is also the
answer to the caller, said "Nothing was changed.  The requirement, the limits, the load case and the check are exactly
as baselined." whatever the reason. For an UNKNOWN given because the check or its data no longer matched the baseline,
that is the opposite of its own reason, two lines above it. Its closing line said what the declared check returned
against the limits when no check had run or none of its numbers had been used; its next step offered a different
design when no design can be verified until the files are restored; and it said only the engineer could "accept a
failure" when the result was not a failure. The review of this repair found the same fault in one more place: when the
gate holds no usable copy of the card, the first client's answer began "UNKNOWN: THE CHECK OR ITS DATA NO LONGER
MATCHES THE BASELINE", called the baseline unchanged, and named the check's files as what was to be restored, when the
card was what could not be used. The verdict, the record and its status were not affected in any of these.

**Two limits repaired with it.**

- *The service's own Verdict row* said who computed the verdict and not what it was. `DECLARED_AMEND3.md` lists it under
  "What stays open" and says the verdict is on the notice's first line "and in its closing lines"; it was not in the
  closing lines. It is now on the Verdict row.
- *A revised baseline's banner,* in the record's print, in the requirement the front door shows and in the first
  client's, gave the runs on the baseline it replaced and how many did not meet the requirement, but not how many were
  unknown, so a reader could take the rest as passes. The counts were always in the signed card.

The earlier declarations, reports, results and amendments are not changed.

## What is changed, and what is fixed

Base: `verification-amendment-3` at `eb1c923`. Six declared files change.

| file | hash last declared in | sha256 before | sha256 now |
| --- | --- | --- | --- |
| `verify/baseline.py` | `DECLARED_AMEND3.md` | `e84a9b19bea6a328…` | `8e9619e5c35d04f6d3fa3a6670afe2c22c1a49d9cc60642027e1c6d4b6d41a2e` |
| `verify/check_record.py` | `DECLARED_AMEND3.md` | `ae8a573a64e043af…` | `1cbf01f0ae0435942a3d849bfacc4a03db4b85e3c93160a167db4e5d03ca468d` |
| `verify/front_door.py` | `DECLARED_AMEND2.md` | `b8abe3dbc0162e91…` | `3b0ed2f68ed8db941ba5634337409e839e86c9dde8fab99ad0a94eb37ecc8836` |
| `verify/verify_client.py` | `DECLARED_VERIFY.md` | `4219b01d8d083b4e…` | `9316be5bc26a98a193435f62118533904423c639590b2badd2fbe1715943f2f5` |
| `tests/verify_tests.py` | `DECLARED_AMEND3.md` | `fd8132a2329604f5…` | `80423d0000b7eefdba99999d393bc1addb782d6109dc06c9f75b39c1f7ac5a67` |
| `tests/verify_front_tests.py` | `DECLARED_AMEND3.md` | `fd3a3c30c95426b1…` | `7e7d764650ec6c8ab131584493fd517f4832faba39e3cf95ba9bfc47834c8785` |

Files new: `verify/dev_amend4_mutants.json` (sha256 `54bf741510a405d92ba44b7404248536979995a211257a5601332439ff831dcf`), the three passes of the deliberate defects;
and, in `verify/sample/amended4/`, the record demonstration run once in the repository after the repair, as a sample of the new wording
(not evidence, and not declared): `demo_transcript.txt` (`772c449e7cd88eef…`); `keys.json` (`f220bac6589b612c…`); `record_revA.json` (`c65a70884f292982…`); `record_revB.json` (`c0e76c911343e47e…`).

Every other file in the repository at `eb1c923`, 170 of them, is unchanged: the gateway, the record builder, the gate's
tool `verify_tools.py`, the consoles, the MCP server, the fixture, and every earlier document and result.

The script that wrote this file compared every top-level statement of the six changed files (each function, class,
constant and import) with the same statement at `eb1c923`, one by one.

- `verify/baseline.py`: 39 statements are unchanged, `evaluate()`, `design_lines()` and the card's rules among them.
  Changed: `face()`. Added: two constants, what a notice says of the check's files by reason, and the first line used
  when no usable card is held.
- `verify/check_record.py`: 34 statements are unchanged, `verify()` and every check of a record among them. Changed:
  `render()`, in the banner's one line.
- `verify/front_door.py`: 44 statements are unchanged. Changed: `requirement_text()`, in the banner's one line.
- `verify/verify_client.py`: 15 statements are unchanged. Changed: the class `Client`, in one line of its `show()`.
- `tests/verify_tests.py`: 56 statements are unchanged, the functions of R1 to R13 and R15 to R17 and the deployment
  they use among them. Changed: the opening description, the list of tests, and one line of R14 (below). Added: R18
  and the helpers it uses.
- `tests/verify_front_tests.py`: 79 statements are unchanged, the functions of F1 to F20 among them. Changed: the
  opening description and the list of tests. Added: F21 and one helper.

The repair, in `face()` unless said:

1. **The Verdict row states the verdict.** It reads "Verdict       FAIL." (or PASS, or UNKNOWN), then, for a verdict
   reached by comparing the check's numbers with the limits (MET and LIMIT_NOT_MET), "Computed by the verification
   service from the check's output and the baselined limits.", and for any other, "Decided by the verification service,
   not by comparing the check's numbers with the limits.", then "Not stated by the assistant."
2. **What is said to be as baselined.** In place of "Nothing was changed. ...", the notice of a FAIL or an UNKNOWN
   says "The requirement, the limits and the load case are as baselined.": the card was checked, its hash and the
   engineer's signature, before it was used, on every route. On a line of its own it then says what is known of the
   check's files, and only for the reasons that `evaluate()` alone gives after checking them: for LIMIT_NOT_MET and
   RESULT_IMPLAUSIBLE, "The check and its data matched their baselined hashes when it ran."; for BASELINE_MISMATCH,
   "The check or its data is not as baselined (the reason above), so the check was not run." For any other reason it
   says nothing of them.
3. **Who may accept it.** "Only ... can accept this result or issue a revised baseline", where it said "accept a
   failure".
4. **The next step.** For BASELINE_MISMATCH: the engineer restores the check and its data to the files whose hashes
   the baseline holds, or issues a revised baseline with a reason, and until then no design inside the design space
   can be verified against this baseline. No different design is offered. For other reasons it is as before.
5. **The closing line.** "This result says what the declared check returned against the baselined limits." only for
   MET and LIMIT_NOT_MET; for any other, "This result gives no number from the check against the limits." Both go on
   "It does not say the check is correct."
6. **When the gate holds no usable copy of the card.** The gate then returns a signed UNKNOWN, BASELINE_MISMATCH, that
   names no check. The first client sets it out from its own copy of the card; the front door has words of its own
   for it, and uses `face()` only if the stored card changes between its read and the gate's; the engineer's notice
   is the tool's, unchanged. `face()` now sees that no check is named and
   writes the first line "UNKNOWN: THE VERIFICATION SERVICE HOLDS NO USABLE COPY OF THIS BASELINE", "Baseline …, as
   this client holds it." where it said "unchanged", "The verification service could not use its stored copy of this
   baseline (the reason above), so nothing was checked against it.", and the next step "restores the stored baseline,
   or issues a revised baseline with a reason. Until then no design can be verified against this baseline."
7. **The banners.** `check_record.render()` prints "after N official runs on it: K met, M not met, U unknown."
   `front_door.requirement_text()` and the first client's `show()` print "(N official runs, M not met); U unknown, K
   met." Each keeps the engineer's reason after the counts.

A PASS reads as before but for the Verdict row. Nothing a sender supplies is in any new line, so the rules of
Amendment 3 for a sender's words are untouched. The longest new line is the Verdict row of an UNKNOWN, 144
characters; the line that names the engineer twice grows with the name, as it did before.

Environment: Python 3.11, cryptography 50.0.2, psycopg 3.3.8, PostgreSQL 16, one machine, all services on 127.0.0.1.

## What each test is expected to show

**R1 to R13 and R15 to R17** are as declared in `DECLARED_VERIFY.md`, `DECLARED_AMEND2.md` and `DECLARED_AMEND3.md`: the
same functions, each check expected true.

**R14** is as declared in `DECLARED_AMEND2.md`, with one line restated. Its first check expects each of fourteen
unusable stored baselines to be answered UNKNOWN with exit status 3, and held the first line of the first client's
answer to "UNKNOWN: THE CHECK OR ITS DATA NO LONGER MATCHES THE BASELINE", which is the defect repaired here: in all
fourteen the card, not the check or its data, is what could not be used. It now expects "UNKNOWN: THE VERIFICATION
SERVICE HOLDS NO USABLE COPY OF THIS BASELINE". Its seven checks and their words are as declared, each expected true.
R1 to R17 together hold the same 89 checks.

**R18. A notice and an answer say only what is so for their own run: each states its verdict, says the check's files matched only when the check ran on files that did, never says that nothing was changed, says so when the service held no usable copy of the card, and a revised baseline gives every count of the runs it replaced.**
- eight runs, one for each verdict the gate gives (MET, LIMIT_NOT_MET, DESIGN_OUTSIDE_BASELINE, CHECK_ERROR, CHECK_OUTPUT_INVALID, RESULT_IMPLAUSIBLE, BASELINE_MISMATCH) and one while the gate holds no usable copy of the card, are answered with the exit status of their verdict; the seven that are not a pass each have a notice
- no notice says that nothing was changed, that the check is exactly as baselined, or that a failure is to be accepted when the result is UNKNOWN; each notice's first line and Verdict row state its verdict, and the Verdict row says the limits were compared only when they were
- a notice says the check and its data matched the baseline only when the check ran and its files did match, and says they were not as baselined only when they were not
- every other line of a notice that says what is so holds for its run: it says what the declared check returned against the limits only when its numbers were compared, says who may accept the result, and the notice of a changed check says the files must be restored and offers no other design
- the seven answers given to the caller say the same, the pass among them, and the last gives the count of runs so far: 8, 1 met, 2 not met, 5 unknown
- while the gate holds no usable copy of the card, the first client's answer says so: it does not call the card unchanged or as baselined, does not say the check or its data changed, and says the stored baseline is to be restored
- in process, for every verdict on two cards (the fixture and the pump station), and for the gate's refusal when it holds no usable card, what face() writes keeps the same rules
- the revised baseline counts every run on the one it replaced, and the counts are the old record's: 8 runs, 1 met, 2 not met, 5 unknown
- the new record's print and the requirement the first client shows give all three counts, so the runs that were not failures are not taken for passes
- the new record verifies

Expected: 18 of 18 pass (99 checks).

**F1 to F20** are as declared in `DECLARED_FRONT.md`, `DECLARED_AMEND2.md` and `DECLARED_AMEND3.md`: the same functions, the
same 104 checks, each expected true. F1 and F2 still pass because the first client still has the two defects they
describe, and F19 because the limit it states is still present. F11 looks for "(1 official runs, 1 not met)" in the
line the front door shows; the new line keeps those words.

**F21. Through the front door, a notice and the tool's answer say only what is so for their run: a changed data file is said to be changed and nothing is said to be unchanged, the Verdict row states the verdict, and the requirement shown after a revision gives every count of the runs it replaced.**
- a design that fails, one that passes, and two sent while a data file of the baseline is changed (by tool and by address) are answered FAIL, met, UNKNOWN and UNKNOWN; three notices are written
- for the changed data file, the two notices and the two answers say the check or its data is not as baselined and must be restored, offer no different design, never say that nothing was changed, and state UNKNOWN on the Verdict row
- for the failure, the notice and the answer say the check's files matched when it ran and what the check returned, and state FAIL on the Verdict row; no notice or answer has the old words
- after the engineer revises and moves the job, the requirement shown gives every count of the runs on the baseline it replaced (4 runs, 1 not met, 2 unknown, 1 met) and the engineer's reason, also while the baseline is on hold; in process, other counts, none equal, are each put in their place
- the new record's print gives the same counts and the engineer's reason, and both records verify

Expected: 21 of 21 pass (109 checks).

R18 and F21 hold the wording of the repaired lines exactly. A true sentence in other words would fail them: the wording
declared here is part of what is declared.

## What was done before this declaration

All of this was on 12 November 2026, times in UTC. The repair and the tests were worked out in scratch copies outside
the repository. The repository's files were changed once, by a script of exact replacements, just before this file was
written.

- **Looking before changing.** I read every sentence of `face()`, the text that is both the engineer's notice and the
  answer to the caller, and every place it is printed: the gate's notice, the first client's answer and the front
  door's. For each sentence I asked, for each reason the gate can give, whether it is true of that run. Four were not
  always true: "Nothing was changed.  The requirement, the limits, the load case and the check are exactly as
  baselined."; the closing line, which said what the check returned when no check had run or none of its numbers had
  been used; the next step, which offered a different design when no design can be verified until the files are
  restored; and "can accept a failure", for a result that was not a failure. The Verdict row named who decided and not what was decided. I also read the three places that print a
  revised baseline's banner.
- **The tests fail on the code as it was.** R18 and F21, as declared here, were run against a copy with the new tests
  and the unrepaired code. R18 failed 7 of its 10 checks and F21 failed 4 of its 5; R14, with its one line restated,
  failed that one of its 7 checks. The checks that passed there say that each run is answered with the exit status of its
  verdict, that the revised baseline counts the runs it replaced, that the records verify, and that the four runs
  through the front door are answered as they should be, which was always so.
- **Mistakes of mine, found by running.**
  - The first run of F21 compared a slice of 24 characters of the Verdict row with an expected string of 26, so it
    could not pass. The slices are now 30 characters. The repair was not changed for it.
  - R18 read the pump station's card, which is a draft with no check hash until it is baselined, and stopped with an
    error. It now gives that card a placeholder hash for the check in process; nothing is run on it.
- **A review by three AI agents.** Each was set on a copy of the repair under one lens, and none was allowed to change
  anything: whether every sentence of the notice, the answer and the banner is true for every verdict; the correctness
  and side effects of the change; and whether the tests can fail. They worked in process, with no services, no tests
  and no demonstrations.
- **What the first two found in the repair, and what was done.** Both found the same fault, separately.
  - *When the gate holds no usable copy of the card,* it returns a signed UNKNOWN with the reason BASELINE_MISMATCH and
    no check. The first client set that out from its own copy of the card, with the first line of a changed check: the
    answer said the check or its data no longer matched, that the requirement, the limits and the load case were as
    baselined, that the baseline was unchanged, and that the check's files should be restored. The card was what could
    not be used. The engineer's notice for the same run was right, so the caller and the engineer were told different
    causes. The old wording was false there too. R14 sends fourteen such runs, and R5 and R17 more; none of them looked
    at what the lines below the first said of the cause, and R14 held the first line to the wrong words. Now `face()` sees that no check is held and says that the service
    could not use its stored copy of this baseline, that nothing was checked against it, and that the stored baseline is
    to be restored, under a first line of its own: "UNKNOWN: THE VERIFICATION SERVICE HOLDS NO USABLE COPY OF THIS
    BASELINE". R14's check of that first line is restated (below). The front door already set such a run out in plain
    words of its own, and still does.
  - *The Verdict row of an UNKNOWN said that no number from the check was compared with the limits.* For some runs one
    was: a result whose second number is implausible after its first was compared, and R15's value of 38 significant
    digits, compared and then set aside because it cannot be written exactly. The row now says the verdict was
    decided by the verification service, not by comparing the check's numbers with the limits.
  - *"Restores the check and its data from the signed copy"* named something that does not exist: the baseline signs the
    hashes of the check and its data, not the files. It now says to restore them to the files whose hashes the baseline
    holds.
  - Smaller points: the line that joined "as baselined" and what is known of the files was 152 characters, and is now
    two lines. The rest of what they noted is listed under "What stays open".
- **What the third found in the tests, and what was done.** It wrote 32 wrong versions of the repair of its own and put
  the text of R18 and F21, as they then stood, against each, using a stand-in for the services that it first checked
  against my planted defects. **Nineteen of the 32 passed both tests.** Among them: a notice that says "The check and its
  data are as baselined." for a design outside the design space, where nothing was checked; the notice of a changed check
  that keeps the old claim in other words, "Nothing else has been changed."; a next step that offers "another design"
  instead of "a different design"; a front door that swaps the met and not-met counts, which F21 could not see because
  its counts made them both 1; and banners that drop the engineer's reason. The cause was in my tests: they looked for
  the exact sentences I had removed and the exact ones I had put in, so a false claim in other words passed. What was
  changed:
  - Every line of a notice or an answer that holds the words "as baselined", "matched", "unchanged", "nothing" or
    "intact", other than the requirement's line and the lines of what was sent, must be exactly one of the lines
    allowed for its reason; any other such line fails. A claim in words outside that list is not caught by this.
  - The closing line, the words on who may accept the result, and the next step are each held to the line allowed for
    the reason, and the notice of a changed check may not offer any other design in any words.
  - F21 also puts other counts, none of them equal, through the front door's line in process, and reads that line while
    the new baseline is on hold.
  - R18 and F21 check that the engineer's reason is kept in each banner; R18 that a count missing from the card is shown
    as "?" and not as 0; and R18 that the answer's own count of runs so far is right.
  - R18 holds every notice to every rule, where it had named some of them one by one.
  It also noted that the tests now hold the wording itself, so that a true sentence in other words fails them (its W29);
  that is said under "What each test is expected to show". R18 went from 9 checks at its first full run to 10, and F21
  stayed at 5 with more in each.
- **Full runs in development.** Both test files were run in full three times on scratch copies before this declaration,
  and passed each time: on the repair before any review, when R18 had 9 checks (19:51 to 19:56); after the first two
  reviews, with 10 (20:10 to 20:15); and after the review of the tests, with the 10 declared here (20:27 to 20:32). Then
  once in the repository after the script was applied to it (21:24 to 21:29). Both demonstrations were then run once in the
  repository as a check and ended normally. They are not evidence here; the transcript of the first is kept as a sample
  of the new wording (below).

To check that the tests can fail, deliberate defects were applied one at a time to a scratch copy of the repaired code and
the tests were run against each, with the services running. A defect counts as caught only when a named check failed;
each pass began with a control with no change, which must pass. There were three passes. `dev_amend4_mutants.json` holds
all three.

**The first pass,** on the repair as it stood before any review, with R10, R17, R18, F11, F20 and F21: the control and 16
defects. The control passed and all 16 were caught.

**The second pass,** on the code after the first two reviews, was stopped after the control and 7 defects, all caught, when the
review of the tests came in, because the tests were to change.

**The third pass,** on the code and the tests declared here, with R10, R14, R17, R18, F11, F20 and F21: the control, which
passed; my 24 defects; and the 19 wrong versions of the agent's that had passed R18 and F21 as they then stood. All 43 were caught.
The agent's other 13 wrong versions, which the tests already caught in its stand-in, were not run against the services.
One of them, W29, rewords a true sentence truly; that the tests fail it is said above.

The defects were chosen by the party that wrote the code, or by an agent working for it. They show the tests can
fail; they do not show the tests are enough.

| | deliberate defect | first pass | second pass (stopped) | third pass, as declared |
| --- | --- | --- | --- | --- |
| C0 | no change at all: the control, which must not be caught | passes, as it must | passes, as it must | passes, as it must |
| C1 | the notice says "Nothing was changed ... exactly as baselined" for every reason, as before | F21, R18 | F21, R18 | F21, R18 |
| C2 | the notice says the check's files matched for every reason | R18 | R18 | R18 |
| C3 | the notice of a changed check says its files matched | F21, R18 | F21, R18 | F21, R18 |
| C4 | the Verdict row does not state the verdict, as before | F21, R18 | F21, R18 | F21, R18 |
| C5 | the Verdict row states FAIL whatever the verdict | F21, R18 | F21, R18 | F21, R18 |
| C6 | an UNKNOWN notice still says only the engineer can "accept a failure" | F21, R18 | F21, R18 | F21, R18 |
| C7 | the notice of a changed check offers a different design, as before, and says nothing of restoring the files | F21, R18 | F21, R18 | F21, R18 |
| C8 | every notice says it gives what the declared check returned against the limits | R18 | not reached | R18 |
| C9 | an implausible result is not said to have run on matching files | R18 | not reached | R18 |
| C10 | a check that stopped with an error is said to have run on matching files, which the verdict does not show | R18 | not reached | R18 |
| C11 | the record's banner gives only how many did not meet the requirement, as before | F21, R18 | not reached | F21, R18 |
| C12 | the record's banner swaps the met and unknown counts | F21, R18 | not reached | F21, R18 |
| C13 | the requirement the front door shows gives only the failures, as before | F21 | not reached | F21 |
| C14 | the requirement the first client shows gives only the failures, as before | R18 | not reached | R18 |
| C15 | the front door reads the unknown count from the wrong field | F21 | not reached | F21 |
| C16 | an implausible result is said to be compared with the limits | R18 | not reached | R18 |
| C17 | when the gate holds no usable card, the first client's answer begins as if the check or its data had changed, as before | not planted | not planted | R14, R18 |
| C18 | when the gate holds no usable card, the answer says the requirement is as baselined and the check or its data changed | not planted | not planted | R18 |
| C19 | the requirement line calls the baseline unchanged even when the gate holds no usable copy of it | not planted | not planted | R18 |
| C20 | when the gate holds no usable card, the next step is to restore the check's files and a different design is offered | not planted | not planted | R18 |
| C21 | the Verdict row of an UNKNOWN says no number from the check was compared with the limits, which is false when a result was compared and then set aside | not planted | not planted | R18 |
| C22 | the notice of a changed check says to restore the files from a signed copy, which does not exist | not planted | not planted | F21, R18 |
| C23 | the no-card headline is the one for a changed check | not planted | not planted | R14, R18 |
| C24 | held is read from the wrong field, so no answer is ever treated as a refusal | not planted | not planted | R14, R18 |
| W02 | every reason with no entry of its own says the check and its data are as baselined (a design outside the space, a crash, garbage output) | not planted | not planted | R18 |
| W03 | a design outside the design space is said to have run on unchanged files, in other words than the matched sentence | not planted | not planted | R18 |
| W04 | the standing line keeps the old claim in other words ("Nothing else has been changed"), also in the notice of a changed check | not planted | not planted | R18 |
| W05 | an UNKNOWN notice says only the engineer can accept "the failure" (the old claim in other words: not "accept a failure") | not planted | not planted | R18 |
| W06 | "Until then no design inside the design space can be verified" is printed for every held non-pass, not only for a changed check | not planted | not planted | R18 |
| W07 | a verdict with no comparison closes by saying what the check returned against the limits, in other words than the old line | not planted | not planted | R18 |
| W08 | the notice of a changed check offers another design, in other words than "a different design inside" | not planted | not planted | R18 |
| W09 | the front door swaps the met and not-met counts | not planted | not planted | F11, F21 |
| W10 | the front door reads the met count from the not-met field | not planted | not planted | F21 |
| W11 | the front door reads the not-met count from the met field | not planted | not planted | F11, F21 |
| W13 | the record's print drops the engineer's reason from the banner | not planted | not planted | F21, R18 |
| W14 | the first client's requirement drops the engineer's reason from the banner | not planted | not planted | R18 |
| W15 | the front door's requirement drops the engineer's reason from the banner | not planted | not planted | F11, F21 |
| W16 | the record's banner prints 0 for a count the superseded baseline does not give | not planted | not planted | R18 |
| W17 | the first client's banner prints 0 for the met and unknown counts when they are not given | not planted | not planted | R18 |
| W25 | when the gate holds no usable card, the answer offers another design, in other words than "a different design inside" | not planted | not planted | R18 |
| W27 | the answer's Official runs row swaps the not-met and unknown counts (a count from the wrong field, outside the four banners) | not planted | not planted | R18 |
| W28 | the no-card answer says its card is "unchanged as this client holds it" (the word, without the full stop the test looks for) | not planted | not planted | R18 |
| W45 | the front door shows the banner only while the new baseline is open (not when it is held) | not planted | not planted | F21 |

C1 to C24 are mine; C1 to C16 were planted in the first pass, against the first form of the repair, and are the same
defects restated for the code declared here. W02 to W45 were written by the reviewing agent, in its words, and are
numbered as in its list.

- No load or stress test was made.

## What stays open

For these findings:

- **The two banners give the counts in different orders.** The record's print says "after N official runs on it: K
  met, M not met, U unknown". The requirement shown by the front door and by the first client says "(N official runs,
  M not met); U unknown, K met", because F11, as declared, looks for "(1 official runs, 1 not met)" in that line and
  the line was kept so that F11 reads it as before. Both give the same three counts.
- **A card whose supersedes block lacks the counts.** Every revised card is made by the console's `revise`, which has
  written all four counts since the first commit. The card's rules do not require them, though, and a card signed some
  other way without them prints "?" for each count.
- **The counts are taken when the revision is made.** The console stops the old baseline and then counts its runs. A
  run already admitted and still being checked at that moment is counted as unknown in the signed counts, though the
  old record will later show its verdict.
- **What a notice says of the check's files, by reason.** It says the check and its data matched their hashes only for
  LIMIT_NOT_MET and RESULT_IMPLAUSIBLE, and that they did not only for BASELINE_MISMATCH, because only those reasons are
  given by `evaluate()` alone, after the files have been checked. A CHECK_ERROR or CHECK_OUTPUT_INVALID can also be given
  by the tool's own guards, sometimes before the files are checked, so its notice says nothing of the files. That is
  never false, but an engineer cannot tell from such a notice that the files were intact.
- **"Baseline …, unchanged."** In a notice set out from a card that was checked, the requirement line still says the
  baseline is unchanged, for every verdict. That is so of the signed card, the only thing it names; in the notice of a
  FAIL or an UNKNOWN, the lines after the Verdict row say what is known of the check's files. When the gate held no
  usable copy of the card, the first client's answer now says "as this client holds it" in its place.
- **The notice to the engineer when no usable baseline is held** is the tool's own text, as before: it says no check
  was run, that this is not a pass, and that the stored baseline should be inspected. It is not changed here.
- **Earlier samples and results.** The transcripts in `verify/sample/`, the results of earlier official runs and the
  notices quoted in earlier documents show the wording as it was. They are records of what was printed then and are not
  changed.

Everything listed as open in `DECLARED_AMEND3.md` is still open, except "The service's own Verdict row", which this
amendment repairs. In short: a sender's text is still shown, up to 20 characters, in quotes, on lines marked as sent;
the front door's journal has no size limit; runs interrupted before Amendment 2 stay interrupted; a machine that cannot
write its inbox loses the notice (F19); someone who can write the service's files can make the tool wait for ever, make
the front door drop connections, and add unsigned parts to what the front door hands out; the engineer's console stops
with a traceback for some unusable files, and a card can be signed that cannot be set out in a notice; the first client
still has the first two defects and the fifth, and must not be what an assistant is given.

## What is not tested

- **Every verdict through every route.** R18 sends one design for each reason the gate gives, and one while the gate
  holds no usable copy of the card, through the first client; F21 sends four designs through the front door, two of
  them while a data file is changed. Every reason is put through `face()` in process on two cards, the fixture and the
  pump station. The front door's own text when no usable baseline is held is not changed and is not looked at by F21.
- **The front door when its read of the card and the gate's differ.** If the stored card changes between the two
  reads, the front door sets out the gate's refusal from its own copy, with the words R18 checks in process. That race
  is not made to happen in a test.
- **A reader.** Whether an engineer reading a notice is in fact not misled is not tested. The tests check what each
  sentence says against what the run was, not what a reader makes of it.
- **The demonstrations and the trial of 30 assistant runs** are not made again as evidence.
- **An assistant, or a host product; separation by machine; any independent review.** As before. The reviews named in
  this file were made by AI agents working for the party that wrote the code.
