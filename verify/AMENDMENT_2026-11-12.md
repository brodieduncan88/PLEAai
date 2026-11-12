# Amendment 2: the open defect repaired, and three more found and repaired

12 November 2026. Private working material. Internal evidence: written, run and checked by the same party.

This amends `AMENDMENT_2026-11-11.md`, `DECLARED_VERIFY.md`, `DECLARED_FRONT.md` and the two reports. None of them is
changed. `DECLARED_AMEND2.md`, committed before the runs reported here, says what was changed, what each test was
expected to show and what was done in development.

## Summary

1. **Finding 3 of Amendment 1 is repaired.** A stored baseline that is unusable in any way now gives a signed UNKNOWN
   and a notice to the engineer, in fixed words. It was asked for by the owner on 12 November.
2. **Three more defects were found while looking, and are repaired too.** A notice could be written over another. A
   number in a design could leave a record unable to verify, which means the statement of 11 November that Finding 2
   was closed for callers through the front door was wrong for such numbers. And a check that printed something
   that could not be read or kept had the effect of Finding 3. These were not asked for.
3. **The tests, on the one official run of each file:** first plug-in 16 of 16 tests, 74 of 74 checks; front door
   19 of 19 tests, 98 of 98 checks. 30 deliberate defects were planted in a copy of the repaired code:
   30 were caught at the first pass.
4. **None of the four defects let a design that does not meet its requirement be shown as met** by a record that
   verifies.
5. **What this does not show.** Nobody outside has reviewed it; the reviews were made by AI agents working for the
   party that wrote the code. Everything ran on one machine. The list of what stays open is longer than before,
   because more was looked for.

## The findings

### Finding 3. A stored baseline that is unusable

**What was wrong.** As Amendment 1 says: a stored baseline changed into something that is JSON but not a card made the
gate's tool stop with an error. The gate host signed its own "unknown" with no result, the run read as interrupted,
and nobody was told. Amendment 1 named one kind of error and called the repair one line. Looking again found three
kinds (a part missing, a part of the wrong kind, a file nested too deep to read), and found that the words of two of
them quote the changed file. A one-line repair would have put text from that file, a NUL included, into a signed
verdict. The front door's own reading of the stored file also missed the third kind, and stopped such a request
before the gate was asked.

**The repair.** Any error while the stored baseline is read gives the same signed UNKNOWN (BASELINE_MISMATCH) and a
notice, in fixed words. A file that cannot be opened is given fixed words too, because the error's own words held the
path of the service's folder. The front door treats any error in its own reading as "no usable card": nothing is
shown from the file, and a design sent goes to the gate.

**Shown by** R14 (fourteen kinds of unusable file through the first client), the restated check of F15 (two kinds
through the front door) and R16 (an error of another kind, from the inside).

### Finding 4. A notice written over another

**What was wrong.** A notice's file name was the time to the second, the verdict and the first eight digits of the
design's hash. Two results in the same second with the same verdict and the same eight digits had the same name, and
the second replaced the first. A pair of failing designs with the same eight digits, both inside the design space,
is found in under a second of computing. So a caller through the front door could send two failures and leave the
engineer with one notice. Both runs stayed on the record.

**The repair.** A notice is created and never replaced. A name that is taken gets `_2`, `_3` and so on. Notices are
written as UTF-8 whatever the locale.

**Shown by** F17 (two failures of one name through the front door) and R16 (five of one name, and a locale that is
not UTF-8, from the inside).

### Finding 5. A number the database hands back changed

**What was wrong.** The front door accepted any finite number in a design. The gate signs its verdict with the design
in it, as sent. The database holds a number as a decimal: a number written with a decimal point or an exponent that
is 1e16 or more in size comes back as a whole number, and negative zero comes back as zero. The stored verdict then
no longer matches what the gate signed. The first answer is a signed FAIL (such a number is outside any design
space tried) and the engineer is sent it; but the record of that baseline fails its check 6 from then on, and the
same design sent again is refused by the service. One request is enough.

**This corrects Amendment 1,** which said Finding 2 was closed for a caller through the front door. It was closed for
the inputs Finding 2 listed and not for these.

**The repair.** The front door refuses such a number before anything is run or recorded. Whole numbers are kept as
written and are accepted.

**Shown by** F18, whose last check compares the rule with the database itself for 872 numbers.

### Finding 6. What a baselined check prints

**What was wrong.** Three things, all needing the engineer's own check to print something unusual; a caller cannot
cause them. Output the tool could not read at all (nested very deep, or a number written with an exponent of a
million) made it stop with an error, with the effect of Finding 3. A NUL or half a surrogate pair in the check's
basis, or in the last line it wrote before stopping, gave a verdict that could not be stored or could not be written
in a notice; a line break there set a line of the check's own in the notice. And a value given to more than 28
significant digits was compared exactly but written rounded, so the record's checker did not agree with the verdict.

**The repair.** Any error while the check is run or read gives UNKNOWN (CHECK_ERROR) in fixed words. Text in a
verdict's basis and reason is made printable. Every verdict is put to the record's own checker before it is returned,
and one the checker would reject becomes UNKNOWN (CHECK_OUTPUT_INVALID).

**Shown by** R15 (eight kinds of output) and R16.

## The tests

Declared in `DECLARED_AMEND2.md` at commit `8fa5973`. Each file was run once after that commit, on 12 November 2026:

- `tests/verify_tests.py`, started 03:06:43 UTC, 89.5 seconds: **16 of 16 passed, 74 of 74 checks.**
  Record: `results_verify_tests_amended_2026-11-12.json` (sha256 `b08059f6d242669b43decc9bbde2d02f545504b227bfc515801fe58616eb904a`).
- `tests/verify_front_tests.py`, started 03:08:13 UTC, 96.6 seconds: **19 of 19 passed, 98 of 98 checks.**
  Record: `results_front_tests_amended_2026-11-12.json` (sha256 `fa39ada611bca7a0a3798e41ae8758ef30084abb1d286b70174bc9573df49b7c`).

Every outcome matches the declaration. R1 to R13, as declared on 11 November, pass with the repaired tool, and so do
F1 to F14 and F16. F1 and F2 pass because the first client still has the two defects they describe. F19 passes
because the limit it states is present.

The new tests and the one restated:

| test | what it shows | checks |
| --- | --- | --- |
| R14 | A stored baseline that is no longer a card at all gives a signed UNKNOWN and a notice, like any other changed baseline: never an interrupted run, never a pass. | 7 of 7 |
| R15 | Whatever a baselined check prints, the answer is a signed verdict that can be kept and checked again, and a notice: never an interrupted run, never a record left unable to verify. | 8 of 8 |
| R16 | From the inside, the tool called directly with no services: its guards take an error of any kind, a verdict the record's checker would reject is not returned, notices of one name are each kept, and a notice is written under a locale that is not UTF-8. | 6 of 6 |
| F15 | A stored baseline changed after it was signed is not shown, and a design sent against it is decided UNKNOWN by the gate, counted, and sent to the engineer. | 7 of 7 |
| F17 | Two failures whose notices would once have had the same file name both reach the engineer: a notice is never written over another. | 3 of 3 |
| F18 | A number the database would hand back changed is refused before anything happens, so it cannot leave a record unable to verify. | 6 of 6 |
| F19 | Known limit, not closed: when the engineer's inbox cannot be written, a run is counted with no verdict and no notice.  It is never a pass, and the record verifies. | 6 of 6 |

This is the first official run of R1 to R13 since 11 November, and the first with the repaired tool. The results of
11 November stand as the results for the tool as it then was.

## Putting the repair into use

- The gate host loads the tool when it starts. It has to be started again to use the repaired tool, on the same state
  file, so that runs already decided are not decided again.
- Runs that Finding 3 left without a verdict stay on the record as interrupted. The gate decides an attempt once.
- After a notice that no usable baseline is held, the stored file has to be put back from the signed copy before a
  record is built or a run acknowledged.

## What earlier documents said that this corrects

- `AMENDMENT_2026-11-11.md`: "Finding 2 is closed for a caller that comes through the front door". Not for the numbers of
  Finding 5, until this amendment. And: "The repair is one line". It was not.
- `REPORT_FRONT.md` and `README_FRONT.md` repeat the first of these. `README_FRONT.md` now carries a dated note.
- `DECLARED_FRONT.md` lists a check of F15 that states the open defect. That check is restated here.
- `baseline.py`, which is not changed, says in its opening description that `evaluate()` is the whole decision and never
  raises. For a run through the gate the decision is now `evaluate()` and then the tool's guard. Controls at baselining
  still call `evaluate()` alone.
- `README.md` says a failure is sent straight to the engineer. Until this amendment that failed in the cases of
  Findings 3, 4 and 6. It still fails where "What stays open" in `DECLARED_AMEND2.md` says so.
- The technical white paper, revision 2, and the five-page explainer, revision 2, say the first two defects are
  closed through the front door and, in the paper, that the third is open. Revision 3 of each corrects it.

## Still open

Everything under "What stays open" and "What is not tested" in `DECLARED_AMEND2.md`. In short:

- a caller through the front door can still put words of its own inside a notice's reason, and can fill the front
  door's journal, which has no size limit;
- runs already interrupted stay interrupted;
- a machine that cannot write its inbox loses the notice (F19);
- someone who can write the service's files can make the tool wait for ever, make the front door drop connections,
  and add unsigned parts to what the front door hands out;
- the engineer's console stops with a traceback for some unusable files, and a card can be signed that cannot be set
  out in a notice;
- the first client is unchanged and must not be what an assistant is given.

Everything `README_FRONT.md` lists under "What it does not do". No outside review of any of this.
