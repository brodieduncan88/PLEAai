# Amendment 6: declaration before the official test runs

15 November 2026. Private working material.

This file is committed before the official runs of `tests/verify_tests.py` and `tests/verify_front_tests.py` on the branch
`verification-amendment-6`. It fixes the changed code, states what each test is expected to show, and records what was
done in development. Each official run is made once after this commit and its first result is kept, pass or fail. A
later correction would be a separate, dated amendment.

## Why declared files are changed

`DECLARED_AMEND2.md` lists, under "What stays open", that through the first client a caller can send "a made-up hash
that shares its first sixteen digits with a real one (the notice lands in the real one's inbox)". The engineer's inbox
is named by the first 64 bits of the baseline hash, and the gate's tool accepts a request naming any hash. For a hash
it holds no baseline for, it answers with a signed UNKNOWN and writes a notice, "A VERIFICATION RUN WAS ASKED FOR AND NO
USABLE BASELINE IS HELD", with the design the caller sent, into the inbox of that name. A caller who copies the first
16 digits of a real baseline's hash can therefore put such notices in that engineer's inbox, as many as it sends, and
the engineer may take them for news about their own baseline. Section 6 of the white paper, revision 12, says this
reading of the code had not been tested. On 15 November the owner approved its repair.

No verdict, record or status is affected: each such run is a signed UNKNOWN on the made-up hash, as before. Only where
its notice is written changes. It is not one of the record's numbered findings: it was listed as open from the start.

The earlier declarations, reports, results and amendments are not changed.

## What is changed, and what is fixed

Base: `verification-amendment-5` at `a5cc3d1`. Three declared files change.

| file | hash last declared in | sha256 before | sha256 now |
| --- | --- | --- | --- |
| `verify/verify_tools.py` | `DECLARED_AMEND3.md` | `74d6de2bfb8793a8…` | `9f977e1db76ab41b9f695ec42ad6086c8a32e3b4bb8e2fa25321555d45d9e351` |
| `verify/verify_ctl.py` | `DECLARED_VERIFY.md` | `5aff8ef0de7097f5…` | `83f8244984dc242534df0d111b0336b589833afe5b59b926f577066369e4433c` |
| `tests/verify_tests.py` | `DECLARED_AMEND5.md` | `b754fe5d860ce71b…` | `3ec14b03472ad85ef9b472ba96c8ef1e7ad006721f1718428627046ea18b34f4` |

One file is new: `verify/dev_amend6_mutants.json` (sha256 `3400c42723014dac3bb75477ab89d20b55c92765e48ef25234e6255b64eeff18`), the pass of the deliberate defects.

Every other file in the repository at `a5cc3d1`, 187 of them, is unchanged: the rules of the baseline, the front door, the
record builder, the first client, the MCP server, the front door's tests, the fixture, and every earlier document and result.

The script that wrote this file compared every top-level statement of the three changed files with the same statement at
`a5cc3d1`, one by one.

- `verify/verify_tools.py`: 22 statements are unchanged, `_decide()` and `_refusal()` among them. Changed:
  `_notify()`, in the line that chooses the inbox, in the address of a notice kept apart and in the last line of the
  engineer's notice when nothing is stored under the hash; `verify()`, which claims the
  inbox on every run on a baseline the service holds and, for a hash with nothing stored under it, gives the reason
  "(none is stored under this hash)"; and the module's opening description, which names the new files. New: `CLAIM`,
  `NONE_STORED`, `_held()`, `_claimed()`, `_inbox()`, `_claim()`, `_claim_all()` and the one line that calls `_claim_all()`
  when the tool starts.
- `verify/verify_ctl.py`: 24 statements are unchanged, `revise()` among them. Changed: `make_baseline()`, which
  now makes the engineer's inbox and writes its claim.
- `tests/verify_tests.py`: 76 statements are unchanged, the functions of R1 to R18 among them. Changed: `TESTS`,
  which names R19, and the opening description, which says so. New: `INSIDE19` and `r19()`.

The repair:

1. **The inbox claims its baseline.** When a baseline is made, the console makes its engineer's inbox,
   `inbox/<first 16 digits>/`, and writes in it a file `baseline_sha256` holding the baseline's full hash: the claim. A
   revision is made in the same way and gets its own. The claim is written whole or not at all: by a hard link, or by a
   rename where the file system makes no hard links, from a temporary file of its own name, which is then removed.
2. **A notice goes to an inbox only for the exact hash.** The gate's tool writes a notice to that inbox only if the
   service holds a baseline folder for the exact hash named, or the inbox's claim names the exact hash; the second keeps
   a baseline whose folder was taken away in touch with its engineer. If the folder cannot be looked at, the claim
   decides. Any other notice goes to `inbox/unclaimed/<the full hash>/`, which is no engineer's inbox, and is addressed
   to no engineer: it says the service found no baseline folder for the hash and read it in no inbox, and that the notice
   is kept and sent to nobody. It is still written, so what was asked, and when, is kept. The signed UNKNOWN for a hash
   with nothing stored under it gives the reason "(none is stored under this hash)" in place of "(the stored file could
   not be opened)", and when such a notice reaches an engineer by the claim, its last line says the baseline should be
   restored, or a revised one issued, in place of "The stored baseline should be inspected."
3. **Baselines made before this amendment** have an inbox with no claim. The gate's tool writes the claim of every
   baseline it holds when it starts, and on every run on a baseline it holds, a pass included.
4. **A claim already there is kept.** If two baselines share their first 64 bits, the one claimed first keeps the inbox,
   and a notice for the other still reaches it while the service holds its folder. A claim that is empty, cannot be
   read, or is not a hash is written again.

Nothing else a notice says is changed, and nothing in a verdict or a record. The front door was never open to this: it
refuses a hash its job is not bound to.

Environment: Python 3.11, cryptography 50.0.2, psycopg 3.3.8, PostgreSQL 16, one machine, all services on 127.0.0.1.

## What each test is expected to show

**R1 to R18** are as declared in `DECLARED_VERIFY.md` and `DECLARED_AMEND2.md` to `DECLARED_AMEND5.md`: the same functions, the
same 99 checks, each expected true. Making the inbox when the baseline is made changes nothing they read: they count
notices as the files ending `.txt`.

**R19** is new. It makes a baseline with no services running and calls the gate's tool directly, as R16 does, with the
service's own folder.

**R19. A notice reaches an engineer's inbox only for that engineer's own baseline: a request naming a hash the service holds no baseline for, even one that shares all but one digit of a real baseline's, is answered UNKNOWN and its notice is kept apart, addressed to no engineer; and a notice about a real baseline still reaches its engineer while the service can find its folder or read its full hash in its inbox.  (Amendment 6.)**
- when a baseline is made, its engineer's inbox is made with it, holds no notice, and holds the baseline's full hash; when the gate's tool starts, a baseline with no inbox, or with one that holds notices and no hash, as for a baseline made before this amendment, is given an inbox that holds it
- requests naming hashes the service holds no baseline for (one sharing the real hash's first 64 bits, one differing from it only in its last digit, one sharing nothing) are answered UNKNOWN, saying none is stored, or, while the service cannot look in its folder of baselines, that the stored file could not be opened; each notice is kept apart under its own hash, addressed to no engineer, and nothing is added to the real engineer's inbox, even while the service cannot look in its folder of baselines
- a failure on the real baseline goes to its engineer's inbox
- while the real engineer's inbox holds no hash, a made-up hash that shares its name still does not reach it; and any run on the real baseline, a pass included, writes the hash again, also where the file system makes no hard links, and leaves nothing else in the inbox
- with the baseline's folder taken away, a run on its hash is answered UNKNOWN, saying none is stored, and its notice still goes to its engineer, by the hash its inbox holds, saying the baseline should be restored
- an inbox that holds another baseline's hash, as two baselines sharing their first 64 bits would share one, still takes the notices of a baseline whose folder the gate holds, and its hash is not replaced
- with the stored card taken away and the inbox holding no hash, the reason saying the stored file could not be opened; with the service unable to look in its folder of baselines, the reason saying so too and the notice that the stored baseline should be inspected; with a hash file that is empty, as a crash could leave, not text, or not a hash; or with a folder in its place: each notice still reaches the engineer, the hash is written again where it can be, and no temporary file is left

Expected: 19 of 19 pass (106 checks).

**F1 to F21** are as declared before: the same functions, the same 110 checks, each expected true. F1 and F2 still pass
because the first client still has the two defects they describe, and F19 because the limit it states is still present.
F19 replaces the engineer's inbox with a file; the repair keeps what happens then as it was.

Expected: 21 of 21 pass (110 checks).

## What was done before this declaration

All of this was on 15 November 2026, times in UTC. The repair and the test were worked out in a scratch copy outside the
repository. The repository's files were changed only by three scripts of exact replacements, the second form's, the
third's and the fourth's, and the three changed files were then compared with the scratch copy and found identical.

- **Looking before changing.** The inbox is written in one place, `_notify()` in the gate's tool. It is read by the
  console's status, which counts the notices in `inbox/<first 16 digits>/`, by the test harness, which counts the files
  ending `.txt` there, and by the trial's measures, which use the harness. The front door does not write notices. Naming
  every inbox by the full hash would also have closed the hole, but it would have moved every notice and changed every
  declared test that reads an inbox. The claim keeps the inbox's name and its contents, and changes only where a notice
  for an unknown hash goes.
- **A first form of the repair** wrote the claim only when the console made a baseline and when a notice was written for
  a baseline the gate held. A full development run of both test files on it, 10:17 to 10:22, gave 19 of 19 and 21 of 21,
  and a pass of 11 planted defects, 10:23 to 10:32, caught all 11. Neither is the evidence for the code declared here.
- **An internal review of the first form,** by an AI agent working in process for the party that wrote the code, found no
  way for a made-up hash to reach a real inbox, and found these, each shown by a case:
  - an error in looking for the baseline folder, such as a folder that cannot be searched, stopped the run with no verdict
    and no notice, where before it gave a signed UNKNOWN and a notice to the engineer;
  - a real baseline's notice went to `inbox/unclaimed/` when its folder was gone and its inbox held no readable claim
    naming it: a baseline made before the amendment that had had no notice since, a claim that could not be read, and an
    empty claim, which was never written again;
  - the notice kept apart was addressed "To: the responsible engineer" and gave the reason "the stored file could not be
    opened", neither of which is so for a made-up hash, and the first test fixed that first line, so a true one would fail;
  - the console made the inbox before the budget was provisioned, so an inbox that could not be made left a baseline
    folder with no budget;
  - six wrong versions passed the first form of R19, among them a comparison of the first 17 digits, an inbox with no
    claim taking any hash of its name, and a claim that overrode the folder.
- **A second form** answered each: an error in looking counts as not held, so the claim decides; the
  gate's tool writes the claim of every baseline it holds when it starts, and on every run on one, a pass included; an
  empty or unreadable claim is written again, and a claim naming another hash is kept; the notice kept apart says it is
  addressed to no engineer and is sent to nobody, and the signed reason for a hash with nothing stored says so; the
  console writes the claim only after the baseline is made, and an error there does not stop it. R19 gained the cases the
  review suggested: a made-up hash that differs from the real one only in its last digit, one sent while the claim is
  missing, a foreign claim, a missing card, a folder that cannot be looked at, and an empty claim.
- **A false failure in the test itself** was found and fixed before this declaration: R19 picked the newest notices by
  their order in a sorted list, which goes wrong when two are written in the same second, because names sort by verdict.
  It now takes the names that were not there before.
- **On the second form,** a full run in development of both test files, 10:47 to 10:52, gave 19 of 19 tests and 106 of 106
  checks, and 21 of 21 tests and 110 of 110 checks. A pass of planted defects on it was begun at 10:52 and stopped at
  11:05, after the control and 18 defects, all caught, when the second review came back.
- **A second internal review,** of the second form, by another AI agent working in process for the same party, found no
  way for a made-up hash to reach a real inbox, and found the same verdicts, signed reasons and ledger lines as before the
  amendment over 17 steps, the one intended reason apart. It found these, each shown by a case:
  - where the file system makes no hard links, no claim was ever written and temporary files were left in the inbox;
  - threads of one gate host shared one temporary name, so a claim could be read empty while another thread wrote it;
  - the notice kept apart said the service "holds no baseline" with the hash, which is not so when it could not look in
    its folder of baselines;
  - the engineer's notice for a baseline whose folder was taken away gave the reason "(none is stored under this hash)"
    and still ended "The stored baseline should be inspected.";
  - the console's comment said the claim keeps a made-up hash out of the inbox, which the folder test does, not the claim;
  - seven wrong versions passed R19, among them one that counts an error in looking for the folder as holding it, which
    lets a made-up hash in while the folder of baselines cannot be searched, and one that takes any text in the claim
    as a hash;
  - and three more cases where a real baseline's notice is now kept apart, or its run stopped, where before it reached
    the engineer; they are listed under "What stays open".
- **A third form** answered the first five: the claim is put in place by a rename where no hard link can
  be made, and the temporary file, of its own name in every thread and process, is always removed; the notice kept apart
  says the service found no baseline folder for the hash; the engineer's notice for a hash with nothing stored says the
  baseline should be restored, or a revised one issued; the comment says what the claim is for. R19 gained cases that
  catch six of the seven wrong versions: a made-up hash, and a real run, while the folder of baselines cannot be looked
  in, simulated by making the look and the reading of the card raise a permission error; the reason given when the card
  alone is missing; a claim that is not text, and one that is not a hash; a baseline with no inbox at all when the tool
  starts; and a run where hard links cannot be made, after which only the claim and the notices are in the inbox.
  On the second form the strengthened R19 failed checks 2, 4 and 5, the three the third form changed.
- **On the third form,** a full run in development of both test files, 11:10 to 11:14, gave 19 of 19 tests and 106 of 106
  checks, and 21 of 21 tests and 110 of 110 checks. A pass of planted defects on it was begun at 11:14 and stopped at
  11:21, when the third review came back: the control passed, 8 defects were caught, and 2 stopped the tests with an
  error. Those two were faults in the defects themselves, whose replacement lines were indented for the second form,
  and they were corrected; every planted version is now checked to parse before a pass.
- **A third internal review,** of the third form, by a third AI agent working in process for the same party, found no new
  way for a made-up hash to reach a real inbox and no new regression, and confirmed that each change of the third form
  does what it was meant to, among them the rename where no hard link can be made, the removal of the temporary file, and
  a claim read whole while another thread writes it. It found:
  - the notice kept apart said "no inbox holds the hash", which is not so when the inbox's claim names it but cannot be
    read; so did the description of `inbox/unclaimed/`;
  - R19's own words said more than it tested: that a baseline whose inbox holds no hash is given one when the tool starts,
    where the test had taken the inbox away entirely; and that requests for made-up hashes are answered "saying none is
    stored", where one of them, while the folder of baselines cannot be looked in, is rightly answered that the stored
    file could not be opened;
  - five wrong versions passed R19, among them one where the tool, starting, skips an inbox that is already there, one
    where the temporary file is left when writing the claim fails, and one where the engineer's last line follows the
    folder rather than the reason.
- **The fourth form,** declared here, answers each: the notice kept apart says the service found no baseline folder for
  the hash and read it in no inbox; R19's words say what it tests; and R19 gained three cases that catch three of the five
  wrong versions: the tool started again while the inbox holds notices and no hash, a folder where the claim should be,
  after which no temporary file is left, and the last line of the engineer's notice while the folder of baselines cannot
  be looked in. The other two, the console's rename and a temporary name per process, are listed under "What is not
  tested".
- **R19 on the unrepaired code** fails checks 1, 2, 4, 5 and 7, and passes 3 and 6: the unrepaired code also sent a real
  failure to its engineer, and put a held baseline's notices in its engineer's inbox whatever that inbox held. **On the
  third form** it fails checks 2 and 4, both for the words of the notice kept apart.
- **A full run in development** of both test files on the scratch copy of the fourth form, 11:23 to 11:28: 19 of 19 tests
  and 106 of 106 checks, and 21 of 21 tests and 110 of 110 checks.
- **The pass of planted defects** on the fourth form, 11:28 to 11:51: the control passed,
  and all 34 defects were caught. Both test files then passed in full in the repository itself, 19 of 19
  and 21 of 21 (11:51 to 11:56), just before this file was written.

To check that the tests can fail, deliberate defects were applied one at a time to a scratch copy of the repaired code and
the tests were run against each (R1, R14, R16, R18, R19, F19), with PostgreSQL running and the services started where a
test starts them. A defect counts as caught only when a named check failed. The pass began with a control with no change,
which must pass. `dev_amend6_mutants.json` holds the pass.

**The pass,** on the code and the tests declared here: the control, which passed, and 34 defects. All 34 were caught.

The defects were chosen by the party that wrote the code. E1 to E20 were written with the repair. W1 to W5 restate, for
the code declared here, wrong versions that an AI agent wrote while reviewing the first form of the repair; its sixth
is E11. M1 to M4, M6 and M7 restate wrong versions that a second AI agent wrote while reviewing the second form; its
M5, which writes the console's claim before the budget is provisioned and lets an error there stop the console, is
left out, because no test reaches it. N1, N2 and N5 restate wrong versions that a third AI agent wrote while reviewing
the third form; its N3, the console with no rename, and N7, one temporary name for every thread of a process, are left
out for the same reason (see "What is not tested"). They show the tests can fail; they do not show the tests are
enough.

| | deliberate defect | caught by |
| --- | --- | --- |
| E0 | no change at all: the control, which must not be caught | passes, as it must |
| E1 | every notice goes to the inbox named by the first 64 bits, as before | R19 |
| E2 | the hash an inbox holds is compared by its first 64 bits only | R19 |
| E3 | the console makes the inbox but writes no hash in it | R19 |
| E4 | the gate's tool, starting, gives no hash to an inbox that holds none | R19 |
| E5 | notices for a made-up hash are kept under its first 64 bits | R19 |
| E6 | a baseline folder is looked for by the first 64 bits of the hash | R19 |
| E7 | the console writes the hash under another name | R19 |
| E8 | all made-up hashes share one folder | R19 |
| E9 | no notice at all is written for a made-up hash | R19 |
| E10 | the console writes only the first 64 bits of the hash | R19 |
| E11 | a hash an inbox holds is replaced by that of any baseline run later | R19 |
| E12 | an error in looking for the baseline folder is not caught | R19 |
| E13 | an empty hash file is not written again | R19 |
| E14 | a run on a baseline the service holds does not write a missing hash | R19 |
| E15 | a kept notice is addressed to the responsible engineer, as before | R19 |
| E16 | the reason given for a hash with nothing stored is the old one | R19 |
| E17 | where the file system makes no hard links, no hash is written | R19 |
| E18 | the temporary file the hash is written to is left in the inbox | R19 |
| E19 | a kept notice says the service holds no baseline with that hash, as the second form did | R19 |
| E20 | the engineer's notice for a hash with nothing stored says the stored baseline should be inspected | R19 |
| M1 | an error in looking for the baseline folder counts as holding it | R19 |
| M2 | any error but a missing file in opening the card is said to mean nothing is stored | R19 |
| M3 | a hash file that is not text stops the tool | R19 |
| M4 | any text in the hash file is taken as a hash | R19 |
| M6 | the gate's tool writes a hash only in an inbox that is already there | R19 |
| M7 | whether anything is stored is judged by the folder alone | R19 |
| N1 | the gate's tool, starting, gives no hash to an inbox that is already there | R19 |
| N2 | the temporary file is removed only when nothing fails | R19 |
| N5 | the engineer's notice says nothing is stored whenever the folder is not found, whatever the reason says | R19 |
| W1 | the hash an inbox holds is compared by its first 17 digits | R19 |
| W2 | a baseline folder is looked for by the first 17 digits of the hash | R19 |
| W3 | an inbox that holds no hash takes any hash that shares its name | R19 |
| W4 | the hash an inbox holds decides before the baseline folder does | R19 |
| W5 | a baseline is taken as held only if its stored card is there | R19 |

- No load or stress test was made.

## What stays open

For this repair:

- **Nobody reads `inbox/unclaimed/`.** Its notices are kept, so that what was asked and when is not lost, but they tell
  no engineer. The console's status counts only the engineer's inbox. It grows by one folder per made-up hash, as the
  inboxes did before.
- **Through the first client, the answer to a made-up hash says the engineer has been sent the result.** The first client
  prints its answer from its own copy of the card, and that sentence is so only when a notice reached an inbox. Before
  this amendment it was not so either, for any made-up hash that did not share an inbox's name. Through the front door a
  made-up hash is refused before any run.
- **Three cases where a real baseline's notice no longer reaches its engineer,** found by the second review, each where
  the service is already damaged or set up otherwise than in the demonstration:
  - a baseline made before this amendment whose folder was taken away before the repaired tool first started: its inbox
    never received a claim, so its notices are kept apart;
  - a baseline made before this amendment, when the folder of baselines could not be searched from before the repaired
    tool started: the same, and its runs are UNKNOWN as before;
  - the console and the gate under two accounts: the inbox the console now makes is the console's, and if the gate cannot
    write in it a failing run stops with no verdict, as F19 states for an inbox that cannot be written. The demonstration
    runs every party under one account.
- **A real baseline whose folder was taken away and whose claim was taken away too, or cannot be read,** has its notices
  kept apart. So does one whose inbox was replaced by a file once its folder is gone: the run now gets a verdict and a
  notice kept apart, where before it stopped with neither. F19's case, where the folder is still held, is as it was.
- **Two real baselines whose hashes share their first 64 bits** share an inbox, as before; the claim names the first.
  While the service holds the second's folder its notices reach that inbox; once the folder is taken away they are kept
  apart. Finding such a pair means making about four billion baselines, each signed by an engineer.
- **Starting the gate's tool now writes in `VERIFY_HOME`:** the claims of the baselines it holds. A comment in R18 says
  nothing is written in the folder it gives the tool; that is still so, because that folder holds no baseline.
- **The ledger's `notice` field gives the notice's file name only,** not its folder, so the ledger does not say whether a
  notice went to an engineer or was kept apart.
- **`inbox/unclaimed/` sits beside the engineers' inboxes.** Code that took every folder in `inbox/` for an engineer's
  inbox would be wrong.
- **The claim's file name is written in two files,** the console and the gate's tool.
- **F19's own words are now stale in one place.** Its comment on the first failure says the inbox folder "now exists";
  it now exists from baselining. The front door's tests are not changed by this amendment, so the comment stays.

Everything listed as open in `DECLARED_AMEND5.md` is still open. The first client still has the first two defects and
the fifth, and its other ways of sending what the front door refuses (`DECLARED_AMEND2.md`); the front door's journal
has no size limit; and the two lines that are not so, found in Amendment 5's last review, are not repaired.

## What is not tested

- **The console's part:** that it writes the claim only after the budget is provisioned, that an error there does not
  stop it, and its rename where no hard link can be made. R19 reads the claim the console wrote; it does not make the
  console fail.
- **Threads.** That two threads of one gate host writing a claim at once cannot leave it empty is shown by reading the
  code, not by a test.
- **A restart.** R19 starts the tool again by reloading it in its own process, not by starting the gate host again.
- **A folder that really cannot be searched.** R19 simulates it, in the tool's own process, by making the look for the
  folder and the reading of the card raise a permission error; every test runs as one account.
- **The test calls the gate's tool directly,** with the service's folder, as R16 does; it does not send the made-up hash
  through the first client and the gate host, which pass the hash on unchanged.
- **A reader.** Whether an engineer reading an inbox is in fact not misled is not tested.
- **An assistant, or a host product; separation by machine; any independent review.** As before. The reviews named in
  this file were made by AI agents working for the party that wrote the code.
