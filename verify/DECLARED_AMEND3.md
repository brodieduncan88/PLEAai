# Amendment 3: declaration before the official test runs

12 November 2026. Private working material.

This file is committed before the official runs of `tests/verify_tests.py` and `tests/verify_front_tests.py` on the branch
`verification-amendment-3`. It fixes the changed code, states what each test is expected to show, and records what was
done in development. Each official run is made once after this commit and its first result is kept, pass or fail. A
later correction would be a separate, dated amendment.

## Why declared files are changed

`DECLARED_AMEND2.md` lists, first under "What stays open", something a caller through the front door could still do: put
words of its own inside a notice. On 12 November the owner asked for it to be repaired. This is that repair, and nothing
else. It is numbered on from Amendment 2.

**Finding 7. Words of the sender's own, shown as if they were the service's.** A design's names and text values were
written as sent into three places a person reads: the reason for a design outside the design space, which is part of
the signed verdict; the design line of the engineer's notice and of the answer; and the checker's print of a record,
which repeated that reason. A name can be a sentence. Sent as a name, "CORRECTION BY THE VERIFICATION SERVICE: this
notice was sent in error" stood in the notice's reason line with nothing to mark where the service's words ended. And a
name padded with spaces could fall at the start of a row when the reader's window wrapped the line, so that a row
reading "Verdict       DECLARED CHECK MET" appeared in a notice of a FAIL. The first line of the notice still said FAIL,
its closing lines were the service's own, and the verdict, the record and its status were not affected. It was found
on 12 November by an AI agent set to play a caller, and it is as old as the plug-in.

The earlier declarations, reports, results and amendments are not changed.

## What is changed, and what is fixed

Base: `verification-amendment-2` at `285edd0`. Five declared files change.

| file | hash last declared in | sha256 before | sha256 now |
| --- | --- | --- | --- |
| `verify/baseline.py` | `DECLARED_VERIFY.md` | `1e1044a8efa2b6f0…` | `e84a9b19bea6a328a7e2515d0917b3e9d89354bc628fd7b62ff35084fad2d13d` |
| `verify/check_record.py` | `DECLARED_VERIFY.md` | `fb4a44cba9d8463b…` | `ae8a573a64e043afcfe875aec0bfc4df16b60cc0f07b832a06df84058386c795` |
| `verify/verify_tools.py` | `DECLARED_AMEND2.md` | `f6fe01e6022192d4…` | `74d6de2bfb8793a8c765c39ca69a403712ca77e7fdb399199f42dfe72e5c2d67` |
| `tests/verify_tests.py` | `DECLARED_AMEND2.md` | `335f1ce2778f7385…` | `fd8132a2329604f536d99513ea078c2527e157458a348014ee8122ad27484570` |
| `tests/verify_front_tests.py` | `DECLARED_AMEND2.md` | `b5ec3f9db186fc8c…` | `fd3a3c30c95426b1fc867fdfc190d4f643f8645ae4dadadc02e5e53418f538c3` |

One file is new: `verify/dev_amend3_mutants.json` (sha256 `1e06fd8543c1e83e0b226cdc9f1ce97dd380144b6770f842a2e95b8091d9598e`), the three passes of the deliberate defects.

Every other file in the repository at `285edd0`, 166 of them, is unchanged: the gateway, the record builder, both clients, both
consoles, the front door, the MCP server, the fixture, and every earlier document and result.

The script that wrote this file compared every top-level statement of the five changed files (each function, class,
constant and import) with the same statement at `285edd0`, one by one.

- `verify/baseline.py`: 29 statements are unchanged, `evaluate()` and the card's rules among them. Changed: `in_design_space()`
  (the wording of its reason only), `face()` (one line, which now calls `design_lines()`), and one sentence of the opening
  description. Added: `sent()`, `design_lines()`, two small helpers and four constants.
- `verify/check_record.py`: 31 statements are unchanged, every check of a record among them. Changed: `verify()` (one field
  added to the summary it returns) and `render()` (what it prints as the reason of a run). Added: `outside_reason()` and
  `recorded()`.
- `verify/verify_tools.py`: 23 statements are unchanged, `verify()` and its guards among them. Changed: `_notify()` (the design in
  the notice written when no usable baseline is held) and one import.
- `tests/verify_tests.py`: 48 statements are unchanged, the functions of R1 to R16 and the deployment they use among
  them. Changed: the opening description and the list of tests. Added: R17, the helpers it uses and two imports.
- `tests/verify_front_tests.py`: 71 statements are unchanged, the functions of F1 to F19 and the deployment they use
  among them. Changed: the opening description and the list of tests. Added: F20, the same helpers and one import.

The repair:

1. **The reason.** For a design outside the design space the reason is now the service's own words throughout. It
   names the baseline's parameters and its approved values, counts the names that are not the baseline's, and repeats
   from the design only a number of at most 24 characters. The decision itself, inside or outside, is the same code
   as before.
2. **The design, in a notice and in an answer.** What is the baseline's own is written plainly on the first line, as
   before: a parameter it names, with a value on its approved list or a number of at most 24 characters. Anything else
   was chosen by the sender. It is set out underneath, each on a line that begins "sent:", under a line that says
   these are from the caller and not the service. On those lines a text is in double quotes and in printable ASCII:
   any other character is written as its escape, and so is a space that follows a space. At most 20 characters of a
   text are shown, with the number left out after it. A number is shown whole or, if it is longer than 24 characters,
   not at all, because part of a number reads as another number. A list or an object is counted and not shown. What
   was sent for the baseline's own parameters is always shown; of the names that are not the baseline's, 12 are
   shown and the rest are counted. No such line is longer than 78 characters, so in a window of 80 columns or more no
   row begins with a sender's words. The notice written when no usable baseline is held sets the design out the same
   way.
3. **The checker's print.** For a design outside the design space the checker prints its own reason, worked out from
   the card and the design in the record, in the same words as item 1. It does not repeat the record's, which in a
   record made before this amendment can hold a sender's words. Other recorded reasons are printed on one line, and
   one longer than 300 characters is cut.
4. **What reads as it did, and what does not.** When every parameter is the baseline's and every value is on its
   approved list or is a number of at most 24 characters, the design's line in a notice and in an answer is what it
   was, character for character. Three things read differently although no text of a sender's is in them. An empty
   design's line now says "no parameters were sent"; it used to be blank. For a number outside its range whose plain
   decimal form is longer than 24 characters, the reason gives the number as it was sent, or not at all; it used to
   give the long form. And a whole number longer than 24 characters is not shown on the design's lines; its length
   is.

Environment: Python 3.11, cryptography 50.0.2, psycopg 3.3.8, PostgreSQL 16, one machine, all services on 127.0.0.1.

## What each test is expected to show

**R1 to R16** are as declared in `DECLARED_VERIFY.md` and `DECLARED_AMEND2.md`: the same functions, the same 74 checks, each
expected true.

**R17. What a design supplies cannot be read as the service's own words: not in the reason that is signed, not in the engineer's notice or the answer, not in the checker's print of the record.**
- each of sixteen designs outside the baseline is answered FAIL: DESIGN OUTSIDE THE BASELINE (exit status 2); one sent while no usable baseline is held is UNKNOWN (exit status 3)
- the reason that is signed repeats no name and no text from a design: none of the senders' words is in any recorded reason
- it names the baseline's parameter, counts the names that are not the baseline's, and repeats a short number
- in the seventeen notices, what a sender supplied is only on lines that begin "sent:", inside double quotes, in printable ASCII, on lines of at most 78 characters; none of the words planted further on in a name or a text is shown, and no letter of full width
- the seventeen answers given to the caller, the one given while no usable baseline is held among them, set it out the same way
- every line that begins "sent:", in the notices and in the answers, has one form: a parameter of the baseline or a name in quotes, then a text in quotes, a number, true, false, null or a count; and the four designs that add names to an approved design keep the approved design on the first line
- a design with forty names of its own, and texts of its own for two of the baseline's parameters, is shown as those two, twelve of the names and a count of the other 28: the sender does not choose what is left out
- a number is shown whole or not at all: one of 23 characters stands on the design's first line as it was sent, one of forty digits is named by its length, and no part of it is shown anywhere
- folded at every width from 80 to 200 columns, the notices and the answers show one row beginning Reason for each, one beginning Verdict for each that has one, and no row beginning with a sender's words or with words of a pass
- the checker's print of the record holds no word a sender wrote, shows one row beginning STATUS and one beginning RECORD VERIFIED at every width, its own, and for each design outside the baseline gives the reason that was signed, in its own words
- a record that holds a sender's words in its signed reasons, as one made before this amendment can, is printed without them: the print is the same, because the checker gives its own reason
- the rule itself, for 4,765 texts, every character below U+0100 among them: what is shown is one quoted run of at most 20 printable ASCII characters with no two spaces together, it reads back as the first characters of the text, and the number after it is how many were left out; a text of 20 characters is shown whole and one of 21 is cut by one
- in process, for 15,792 designs, 15,625 of them made of 25 awkward values for each of the baseline's parameters: the checker decides as the service does and gives the reason the service signs, neither stops with an error, no line of what was sent is longer than 78 characters or holds a character outside ASCII, and no reason and no line of the service's own repeats what was planted in a design
- an ordinary design is set out on one line as it always was, an empty one is said to be empty, and a name of the baseline's own longer than 26 characters is cut on a line of what was sent
- the record verifies: sixteen not met, one unknown, none met

Expected: 17 of 17 pass (89 checks).

**F1 to F19** are as declared in `DECLARED_FRONT.md` and `DECLARED_AMEND2.md`: the same functions, the same 98 checks, each
expected true. F1 and F2 still pass because the first client still has the two defects they describe, and F19 because
the limit it states is still present.

**F20. Through the front door, what a design supplies cannot be read as the service's own words: not in the engineer's notice, not in the text of the answer, not in the checker's print of the record.**
- each of six such designs sent by address, and one sent by tool, is decided FAIL / DESIGN_OUTSIDE_BASELINE and is not marked as a tool error; one sent while no usable baseline is held is UNKNOWN
- the reason that is signed, in each answer and in the record, repeats no name and no text from a design
- in the eight notices, what a sender supplied is only on lines that begin "sent:", inside double quotes, in printable ASCII, on lines of at most 78 characters; none of the words planted further on in a name or a text is shown, and no letter of full width
- the text of each of the seven answers given for a design decided against the job's baseline sets it out the same way
- folded at every width from 80 to 200 columns, the notices and the answers show one row beginning Reason for each, one beginning Verdict for each that has one, and no row beginning with a sender's words or with words of a pass
- the checker's print of the record holds no word a sender wrote and prints, for each design outside the baseline, a reason equal to the one signed; the record verifies: seven not met, one unknown

Expected: 20 of 20 pass (104 checks).

In R17 and F20 nearly every text a sender supplies begins with the letters QS, and the long ones hold other words
further on. The tests look for those letters and words in what a person would read. "Folded" means each line cut at
a given width and carried on to the next row, as a terminal does.

## What was done before this declaration

All of this was on 12 November 2026, times in UTC. The repair and the tests were worked out in scratch copies outside
the repository. The repository's files were changed once, by a script of exact replacements, just before this file was
written.

- **Looking before changing.** I read every place where a design's own words reach a person. There are four: the
  reason for a design outside the design space, the design line of a notice and of an answer, the notice written when
  no usable baseline is held, and the checker's print of a record. The engineer's console prints no reason and no
  design.
- **The tests fail on the code as it was.** R17 and F20, as declared here, were run against a copy with the new tests
  and the unrepaired code. R17 failed 13 of its 15 checks and F20 failed 5 of its 6. The checks that passed there say
  that a design is refused and that the record verifies, which was always so.
- **Mistakes of mine, found by running.**
  - The first run of R17 on the repaired copy failed three checks, and all three were mistakes in the test. A word I
    had planted as a sender's is also in the service's own closing lines. The checker's own last rows begin STATUS
    and RECORD VERIFIED, which the test had counted as forged. Two expected counts of lines were wrong. The test was
    corrected; the repair was not changed for it.
  - A marker I used to look for part of a long number was also the start of another number's decimal form. The number
    and the marker were changed.
  - A deliberate defect was missed at the first pass (B15, below).
- **A review by three AI agents.** Each was set on a copy of the repair under one lens, and none was allowed to change
  anything: a caller who holds one job's certificate, the correctness of the code, and whether the tests can fail.
  All three reported. They worked in process, with no services. The first two found faults in the repair; the third
  found that the tests would have passed many wrong repairs.
- **What the first two found in the repair, and what was done.**
  - *The sender chose what was left out.* I had added a limit of 12 lines of what was sent, so that a design of
    hundreds of names could not push the service's own lines far down a notice. Both agents showed that the limit
    then let a sender fill the 12 lines with names of its choosing and hide what it had sent for the baseline's own
    parameters. What was sent for the baseline's own parameters is now always shown; the limit applies only to names
    that are not the baseline's, in a fixed order.
  - *A number cut short read as another number.* A number longer than 20 characters was cut like a text, so
    -1.2345678901234568e-05 was shown as "-1.2345678901234568e+3". This also touched designs inside the design
    space. A number is now shown whole, up to 24 characters, which every number written with a point or an exponent
    fits; a longer whole number is not shown at all, and the line says how long it is.
  - *The lines had no mark of their own.* Twelve lines such as `"Verdict" = "DECLARED CHECK MET"` could read as a table
    of results. Every such line now begins "sent:", and the line above them says they are from the caller and not
    the service.
  - *The limit of 78 characters did not hold for every input,* only for a design that came through the front door. The
    fixed words used for a number, a list or an object were shortened so that it holds for any design.
  - *The claim that an ordinary design reads as before was not exact.* An empty design, and a number whose plain
    decimal form is long, read differently. The claim is restated above, the empty design is now said to be empty,
    and such a number is written as it was sent.
  - *The checker stopped with an error* for a whole number too long to be written, where the service answers. Only a
    direct call can make such a number; it is guarded now.
  - Smaller points: a heading line of 83 characters was shortened to 76; a sentence in `baseline.py` that said UNKNOWN
    where the tool can also give FAIL was corrected. Three things they noted are not changed and are listed under
    "What stays open": files that hold a design whole, the order of the card's parameters, and a long reason from a
    check.
- **What the third found in the tests, and what was done.** It wrote 43 wrong versions of the repair of its own and
  put the text of R17 and F20, as they then stood, against each, using a stand-in for the services. **Twenty-two of
  the 43 passed both tests.** Two of the worst: a repair that still writes a sender's whole sentence into the signed
  reason when it is sent as the value of a numeric parameter, in the service and the checker alike; and one that
  still writes a value with no plain space in it, made of characters that look blank, on the service's own design
  line, where it again makes a row reading "Verdict DECLARED CHECK MET". The repair itself did neither. The cause was
  in my tests: every text they sent for one of the baseline's parameters held a plain space and went to a parameter
  with an approved list, or travelled with forty other names; and the check of 15,792 designs in process only
  compared the service with the checker, so the same mistake in both passed. What was changed:
  - R17 sends five more designs and F20 two more: a sentence sent for a number, a text with no plain space made of
    characters that look blank, an object as a value, a design that is not an object, and two names in small letters.
  - The check of 15,792 designs also looks for what it planted, in each reason and on each line of the service's own.
  - Every line that begins "sent:" is held to one exact form.
  - The check of the print uses three shapes of earlier reason, and a long reason that holds unprintable characters.
  - The check of the rule itself has every character below U+0100, and pins the cut at exactly 20.
  - The answer given while no usable baseline is held is read too.
  - F20's title said "the tool's answer". The answer also carries the verdict as data, with the design in it as sent.
    The title now says "the text of the answer", and the data is listed under "What stays open".
  - Three sentences in the tests said more than their expressions measured, and were reworded.
  - My script for planted defects counted a test that stopped with an error as a catch, and had no unchanged control.
    No earlier result was affected: every catch in the first two passes was a named check. The script now counts
    only a named check and runs a control with no change.
  R17 went from 9 checks at the first full run to 15, and F20 stayed at 6 with more designs.
- **A probe in development,** in process and not a declared test, compared the code as it was with the repaired code
  over 8,008 generated designs on two baselines (the fixture and the pump station). The decision was the same for
  every design. The reason the service gives was the one the checker gives. An ordinary design's line was the same as
  before for every design but the empty one. No reason held a marker planted in a name or a text.
- **Full runs in development.** Both test files were run in full four times before this declaration, and passed each
  time: on the repair before any review, when R17 had 9 checks (03:29 to 03:33); after the first two reviews, with 14
  (04:04 to 04:08); after the review of the tests, with the 15 declared here (04:29 to 04:33); and once in the
  repository after the script was applied to it (04:57 to 05:01). Both demonstrations were then run once in the
  repository as a check and ended normally. They are not evidence here.

To check that the tests can fail, deliberate defects were applied one at a time to a scratch copy of the repaired code and
the tests were run against each, with the services running. There were three passes. `dev_amend3_mutants.json` holds all
three.

**The first pass,** on the copy as it stood before any review: 20 defects, 19 caught. **B15 was not caught**: a checker that
prints the record's own reason, as before. For a verdict signed by the repaired tool the record's reason and the
checker's own are the same words, so nothing in the tests told them apart. A check was added to R17: the same record
with a sender's words put into each signed reason, as a record made before this amendment can hold, must print exactly
the same.

**The second pass,** after the first two reviews: 27 defects, the 20 and 7 more for what those reviews changed. All 27 were
caught. In these two passes R1, R3, R5, F3 and F7 were run beside R17 and F20; they caught nothing that R17 and F20
did not.

**The review of the tests** then showed that 22 of the reviewing agent's 43 wrong versions passed R17 and F20 as they
stood (above). The second pass had shown less than it seemed to.

**The third pass,** on the code and the tests declared here, with R17 and F20: a control with no change, which passed;
the 27 defects again; and the 22 wrong versions of the agent's that had passed. All 49 were caught.
A defect counts as caught only when a named check failed. The agent's other 21 wrong versions, which the earlier
tests already caught in its stand-in, were not run against the services.

The defects were chosen by the party that wrote the code, or by an agent working for it. They show the tests can
fail; they do not show the tests are enough.

| | deliberate defect | first pass | second pass | third pass, as declared |
| --- | --- | --- | --- | --- |
| B1 | the reason lists the names that are not in the baseline, as sent, as before | F20, R17 | F20, R17 | F20, R17 |
| B2 | the reason repeats a text value that is not on the approved list, as before | F20, R17 | F20, R17 | F20, R17 |
| B3 | the reason repeats a number of any length | R17 | R17 | R17 |
| B4 | the notice and the answer write the design on one line as sent, as before | F20, R17 | F20, R17 | F20, R17 |
| B5 | what was sent is shown in quotes but is not cut | F20, R17 | F20, R17 | F20, R17 |
| B6 | what was sent is cut at 60 characters, so a line of it can be longer than 78 | F20, R17 | F20, R17 | F20, R17 |
| B7 | a space that follows a space is written as a space | F20, R17 | F20, R17 | F20, R17 |
| B8 | a character outside ASCII is written as it is | F20, R17 | F20, R17 | F20, R17 |
| B9 | a double quote inside what was sent is not escaped | R17 | R17 | R17 |
| B10 | what was sent is written without quotes | F20, R17 | F20, R17 | F20, R17 |
| B11 | a text value for a parameter of the baseline is written plainly even when it is not on the approved list | F20, R17 | F20, R17 | F20, R17 |
| B12 | a name that is not in the baseline is written plainly when it has no space in it | R17 | R17 | R17 |
| B13 | the lines of what was sent carry no mark of their own: sixteen spaces, like some of the service's own | F20, R17 | F20, R17 | F20, R17 |
| B14 | when no usable baseline is held the notice writes the design on one line as sent, as before | F20, R17 | F20, R17 | F20, R17 |
| B15 | the checker prints the record's own reason for a design outside the baseline, as before | **not caught** | R17 | R17 |
| B16 | the checker's own reason lists the names that are not in the baseline | F20, R17 | F20, R17 | F20, R17 |
| B17 | the checker's own reason repeats a text value | F20, R17 | F20, R17 | F20, R17 |
| B18 | the checker's own reason is worded differently from the one the service signs | R17 | R17 | F20, R17 |
| B19 | a list or an object in a design is shown as sent | R17 | R17 | R17 |
| B20 | the count of what was left out is wrong by one | R17 | R17 | R17 |
| B21 | every line of what was sent is shown, however many there are | not planted | R17 | R17 |
| B22 | a number longer than 24 characters is shown in part, so that it reads as another number | not planted | R17 | R17 |
| B23 | what was sent for the baseline's own parameters is left out with the rest when a design has more than twelve names of its own | not planted | R17 | R17 |
| B25 | the checker stops with an error on a whole number too long to be written, where the service answers | not planted | R17 | R17 |
| B26 | a long number is described in more words, so a line of what was sent can be longer than 78 characters | not planted | R17 | R17 |
| B27 | an empty design is set out as it was before: a design line with nothing on it | not planted | R17 | R17 |
| B24 | a number of up to 24 characters is not written whole on the first line: the limit for a number is 20 | not planted | R17 | R17 |
| W1b | W1 in the service AND in the checker's own reason | not planted | not planted | F20, R17 |
| W2c | reason, service AND checker: a text with no plain space in it sent for a parameter with an approved list is repeated, whatever its length or letters | not planted | not planted | F20, R17 |
| W3b | reason, service AND checker: a number of any length sent for a parameter with an approved list is repeated | not planted | not planted | R17 |
| W4c | reason, service AND checker: a number outside its range is repeated when it has up to 39 characters, not 24 | not planted | not planted | R17 |
| W5 | sent(): carriage return, escape and backspace are written as they are | not planted | not planted | R17 |
| W5b | sent(): every ASCII control character but NUL, tab and line feed is written as it is | not planted | not planted | R17 |
| W6 | sent(): characters U+0080 to U+009F (the C1 controls) and U+00A1 to U+00FF are written as they are | not planted | not planted | R17 |
| W7 | sent(): an object is shown as sent | not planted | not planted | R17 |
| W8 | sent(): a number of 25 to 39 characters is shown whole | not planted | not planted | R17 |
| W9 | sent(): a text is cut at 19, not 20 | not planted | not planted | R17 |
| W10 | design_lines: a text with no plain space in it, sent for one of the baseline's parameters, is written plainly on the first line (any length, any letters) | not planted | not planted | F20, R17 |
| W12 | design_lines: the heading "From the caller, not the service ..." is left out | not planted | not planted | R17 |
| W13 | design_lines: a design that is not an object is written as sent | not planted | not planted | R17 |
| W14 | design_lines: a name that is not the baseline's is written plainly when it is all lower-case letters | not planted | not planted | R17 |
| W15 | design_lines: a name that is not the baseline's but sorts after all of the baseline's is put on the first line | not planted | not planted | R17 |
| W16 | design_lines: when no usable baseline is held, only names that hold a space are quoted | not planted | not planted | R17 |
| W19 | render: other recorded reasons are printed as the record gives them: not cut, not made printable | not planted | not planted | R17 |
| W20 | render: the checker gives its own reason only when the recorded one begins "the design must give exactly"; otherwise it prints the record's | not planted | not planted | R17 |
| W21 | render: the checker gives its own reason only when the recorded one is longer than 100 characters; a shorter one is printed as recorded | not planted | not planted | R17 |
| W27 | face(): for a verdict that is not DESIGN_OUTSIDE_BASELINE the design is written on one line as sent, as before (the first client's answer when the service holds no usable baseline) | not planted | not planted | R17 |
| W28 | reason, service AND checker: the names that are not the baseline's are listed, each cut at 12 characters, when there are at most 3 of them and none begins with a capital | not planted | not planted | R17 |
| W35 | a name of the baseline's own longer than 26 characters is not cut (control: the fixture has none) | not planted | not planted | R17 |

B1 to B27 are mine. W1b to W35 were written by the reviewing agent, in its words, and are numbered as in its list. Its W1
is a reason that repeats in full a text sent for a numeric parameter; W1b is that in the service and the checker alike.

- No load or stress test was made.

## What stays open

For this finding:

- **Twenty characters, in quotes.** A sender's name or text is still shown, up to 20 characters of it, on a line marked
  as sent. A short phrase can stand there. It is inside double quotes, on a line that begins "sent:", under a line
  that says these are from the caller and not the service.
- **A window narrower than 80 columns.** The lines that show what was sent are at most 78 characters long. In a narrower
  window they wrap, and a row can then begin inside one of them.
- **A number is repeated.** A number of at most 24 characters from a design is still written in the reason and on the
  design's first line. It can hold digits, a sign, a point and an exponent.
- **Files that hold a design whole.** The gate's ledger, the database, the front door's journal, a record file and
  the checker's `--json` output hold each design in full, as JSON, with the sender's names and text. They are data
  and are not set out for a person, but a person who opens one reads the sender's words there.
- **What the caller is shown about its own design.** An answer carries, beside its text, the verdict as data: the
  second block of a tool's result and the `verdict` field of the front door's answer hold the design as it was sent.
  The front door's own text for a caller when no usable baseline is held, and the status listings of the front door
  and of the first client, still repeat a reason and a design as they are held. The reader in each case is the
  caller who sent them. `front_door.py`, `plea_verify_mcp.py` and `verify_client.py` are not changed.
- **Verdicts already signed.** A verdict signed before this amendment keeps the reason it was signed with, in the
  database and in any record. The checker no longer prints it. Its `--json` output still carries it, as data.
- **The service's own Verdict row.** In a notice, the row that begins "Verdict" says who computed the verdict. The
  verdict itself is on the notice's first line and in its closing lines. A reader who looks only for a row named
  Verdict does not find the word FAIL on it. This is not changed here; whether it should be is the owner's decision.
- **The order of the card's parameters.** For a design with more than one fault, the reason names the first in the
  order the card lists its parameters. The checker works its reason out from the card in the record. A card's hash
  does not depend on that order, so a record whose card lists them in another order prints another reason, equally
  true, than the one that was signed.
- **A long reason from a check.** In the print, a recorded reason other than this one is cut at 300 characters, with
  a count of the rest. The service's own reasons are shorter, except where they quote what the engineer's check
  printed.
- **What a check says.** A check's basis can repeat a value of the design it was run on. A check is run only on a
  design inside the design space, where a text is one of the baseline's approved values and the rest are numbers.
- **The baseline's own words.** A parameter's name, an approved value, the requirement and the engineer's name are
  printed as the engineer wrote them. A baseline with many parameters, or long names, gives a long first line of the
  design; what wraps there is the baseline's names and numbers. On a line of what was sent, a parameter name of the
  baseline longer than 26 characters is cut.

Everything listed as open in `DECLARED_AMEND2.md` is still open, except its first item, which this amendment repairs.
In short: the front door's journal has no size limit; runs interrupted before Amendment 2 stay interrupted; a machine
that cannot write its inbox loses the notice (F19); someone who can write the service's files can make the tool wait
for ever, make the front door drop connections, and add unsigned parts to what the front door hands out; the
engineer's console stops with a traceback for some unusable files, and a card can be signed that cannot be set out in a
notice; the first client is unchanged and must not be what an assistant is given.

## What is not tested

- **Every text.** One check of R17 puts 4,765 texts through the rule, every character below U+0100 and one or a few
  characters of every kind above it among them. It does not prove the rule for every text.
- **Every design.** Through the services, R17 sends sixteen designs and one more while no usable baseline is held;
  F20 sends seven and one more. In process, R17 looks at 15,792 designs on the fixture's card only. The probe of
  8,008 designs on two baselines is not a declared test.
- **Another baseline.** Every design in R17 and F20 is sent against the fixture's card, which has three parameters
  with short names. A baseline with a long name is checked in process only, for one line.
- **An empty design through the services.** How it is set out is checked in process only.
- **Widths other than 80 to 200 columns.**
- **The data beside the text of an answer** is not examined by F20, as said above.
- **A reader.** Whether a person reading a notice is in fact not misled is not tested. The tests check where a sender's
  words can stand, not what a reader makes of them.
- **The demonstrations and the trial of 30 assistant runs** are not made again as evidence.
- **An assistant, or a host product; separation by machine; any independent review.** As before. The reviews named in
  this file were made by AI agents working for the party that wrote the code. One of them found that the tests as I
  first wrote them passed 22 of its 43 wrong repairs; that is a measure of those tests, and the tests declared here
  were written by the same party with that agent's help.
