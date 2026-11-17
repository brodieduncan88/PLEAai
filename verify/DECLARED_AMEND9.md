# Amendment 9: declaration before the official test runs

17 November 2026. Private working material.

This file is committed before the official runs of `tests/verify_tests.py` and `tests/verify_front_tests.py` on the branch
`verification-amendment-9`. It fixes the changed code, states what each test is expected to show, and records what was done
in development. Each official run is made once after this commit and its first result is kept, pass or fail. A later
correction would be a separate, dated amendment. Times are UTC.

## Why declared files are changed

On 17 November the owner sent a reviewer's points on the record, and asked for an amendment that takes up three of them.

- **Point 1: evidence of process can be mistaken for evidence of correctness.** The record shows that a declared check ran
  against declared inputs and what it returned. It does not show that the requirement is complete, the check correct, the
  assumptions sound or the design the part built. A signed record of a subtly wrong calculation can carry more authority than a
  chat reply. The reviewer asked that what people read favour "declared check met" over an unqualified "PASS", with the check's
  exclusions always visible. Much of this was so already: a notice and the assistant's answer have opened with DECLARED CHECK
  MET since the first plug-in, have ended with "It does not say the check is correct" and the check's exclusions since
  Amendment 4, and the record's checker prints its status as DECLARED CHECK MET. What was not so: the status's field for a
  design met was called `verified`; the status listings, the engineer's console and the answer's fields showed a pass as PASS
  with nothing beside it; the Verdict row of a pass said PASS; the exclusions were the last line of a long text, which a host
  that shortens a result cuts first; and the front door's own text, used when it cannot read the stored card, said nothing of
  what a pass does not show.
- **Point 3: requirement continuity is incomplete.** A relaxed requirement could be baselined as new, not as a revision, and
  nothing in the new record linked it to the old one. The front door narrowed this (a job moves only to a revision, and a
  second job needs a reason, kept in the service's log), but the link was not in the record itself. The other half of point
  3, telling a current record from an old one, needs a statement by the witness, and is not in this amendment.
- **Point 4: notification is not independent delivery.** The reviewer said that the name "proof of delivery" overstates what
  Amendment 8 shows: a recent ability to write a test file, not delivery, reading or acknowledgement; and that a run cut off
  part-way gets no notice unless its design is sent again. The first half of point 4, that a notice is written by the service it
  reports on, needs a second party, and is not in this amendment.

## What is changed, and what is fixed

**A pass is called the declared check met, wherever a person or an assistant reads it (point 1).**

- *The text of a verdict* (`baseline.face`, which is both the engineer's notice and the assistant's answer) has the line "The
  check does not cover: ..." directly under its headline, for every verdict, as well as at its end. The Verdict row of a pass
  reads "DECLARED CHECK MET (signed as PASS)"; a FAIL and an UNKNOWN read as before.
- *The status listings* of the first client and of the front door, and the engineer's console, show a run that met the check
  as MET, not PASS. Where a design has met the check, they add a line that names the design and says: "This says what the
  declared check returned against the baselined limits.  It does not say the check is correct, the requirement is complete, or
  the design is safe.", and then the check's exclusions.
- *The front door's fields.* The status's field for whether a design has met the check is called `declared_check_met`, not
  `verified`. The answer to a run carries `declared_check_met` and `check_does_not_cover` beside `outcome`, which stays PASS,
  FAIL or UNKNOWN for callers that read it.
- *The front door's own text*, used when it cannot read the stored card, says for every verdict that the result does not say
  the check is correct, and that what the check does not cover cannot be shown there.
- *The MCP server's* description of the submit tool and its instructions call a pass the declared check met, signed as PASS,
  and say that it is not a statement that the check is correct. The descriptions of the two command-line clients do the same.
  A tool's result has two parts: the words, then the same fields as JSON for hosts that pass on text only. The words say
  DECLARED CHECK MET; the fields keep `outcome` PASS beside `declared_check_met`.
- *The answer to a run cut off* (INTERRUPTED) carries `declared_check_met` (false) and `check_does_not_cover`, as any other
  answer does.
- *The record's checker* shows a run that met the check as MET in its list of runs, as it already printed its status as
  DECLARED CHECK MET.
- *The two views of the requirement* say that a design is checked against the baseline only by submitting it, where they said
  it was verified only so. A verdict value the text has no words for is printed as it is, as before this amendment, and not
  raised.

**A second baseline for a requirement is linked to the first, in the signed card (point 3).** The engineer's console
(`verify_ctl.py baseline`, and `make_baseline` beneath it) refuses a draft whose requirement id the service already holds a
baseline for, unless it is made as a revision (`revise`), which is linked as before. The refusal names the baselines held and
says to revise one or give a reason, and nothing is stored, signed or provisioned. With the engineer's reason
(`--alongside-reason`), the new card carries a field `alongside`: the reason, and every baseline the service holds for that
requirement id, each with its hash and revision. The engineer signs it with the rest of the card, the card's rules check its
form, and it is in every record built from the card. The record's checker, the first client's view of the requirement and the
front door's (the MCP tool that shows the requirement) print it: "ALSO BASELINED FOR THIS REQUIREMENT, NOT AS A REVISION OF IT:
<hash> (rev <revision>), ...  Reason given by the engineer: ...". The front door's fields of the requirement give it too. A card
with no other baseline held has no such field, so its hash is as before.

Two ids are one requirement when they differ only in case, in white space, in characters that show nothing (Unicode's format
characters, such as a zero-width space or a soft hyphen; combining marks left over, such as a variation selector; the Hangul
fillers), in the kind of dash, or in Unicode's compatibility form: "REQ-1", " req-1", "REQ-1" with a zero-width space in it,
and the same in full-width letters are one. A revision of such an id is told which spelling to keep. A link is made only by the
console, from what the service holds: one written in the draft is dropped before signing. A baseline folder counts as held when
its envelope is whole: its hash is its card's, and the key its card names signed it. Whose key that is, is not asked: the
engineers of one service may each hold a baseline for one requirement, and each is counted, whichever engineer runs the
console.

**The gate's check of an inbox is named for what it shows (point 4).** What Amendment 8 called a proof of delivery is called an
inbox-writability check in everything a person or a caller reads. Its states are WRITABLE, UNCHECKED, STALE and NOT_WRITABLE
(were PROVEN, UNPROVEN, STALE and NOT_WRITABLE). It is kept in `inbox_checks/` in the service's home (was `delivery/`). The
front door's refusal of a new run without a good check is coded `INBOX_UNCHECKED` (was `DELIVERY_UNPROVEN`), and so is the
name of its notice to the engineer. The engineer's console says "inbox writable: the gate wrote a test file in this inbox at
<time>.  This is not delivery: it does not show that a notice was delivered or read.", or, for the other states, "INBOX NOT
CHECKED: ...", "INBOX CHECK OUT OF DATE: ..." or "INBOX NOT WRITABLE: ...". The gate's
tool says "CANNOT RECORD THE INBOX-WRITABILITY CHECK" on its error output. The internal names of functions, and the tool's two
settings `VERIFY_PROOF_SCAN` and `VERIFY_PROOF_REFRESH`, are kept. A check kept in `delivery/` by Amendment 8 is not read: the
gate's tool makes a new one in `inbox_checks/` when it starts.

**A run left pending gets its notice with no one sending its design again (point 4).** The front door looks, every 30 seconds
unless set (`--sweep-every`), at every job whose binding a pinned engineer signed and that is not revoked. For each it reads the
observation of the job's baseline from the store, once, and, for a run the gate began and has no notice of, that run's
evidence. From these it picks the runs left pending, and the runs cut off whose notice is not written. It reads the job's runs
in full only when one of them is due. A run is due once it has been seen in that state for 120 seconds unless set
(`--sweep-after`; at least one second); each time the look acts on it, the wait before it acts again doubles, up to an hour,
so a run that cannot be finished is acted on less and less often. A run seen in a new state is seen afresh, and a look that
cannot read a baseline forgets none of its waits. For a run cut off whose notice is missing, the notice is written, whatever
the state of the budget and of the gate's inbox-writability check (a notice the inbox cannot take is kept in the service's own
store, as before), and in the service's fixed words, which say that the design is not shown, where the journal does not hold
the design. A pending run is asked for again, through the same path as a caller's request, only while that check is good
and the budget is neither held nor stopped, only if the journal holds its design, and only if the job's binding, read again
just before, is unchanged. The design found in the journal is not journaled again. The look acts on one run
at most twelve times; it then leaves it as it is, and says so in its log, until the front door restarts. The gate host never
runs a run twice: a run it began and lost is answered with its signed UNKNOWN,
counted as interrupted, and the engineer is sent its notice, as Amendment 7 has it. A run that was admitted but never reached
the gate host is run now, once, as its caller asked, with its verdict and notice as for any run. What the front door did is
written to its log. The test harness starts the front door with an hour's wait, so that tests that leave a run pending on
purpose find it as they left it; F34 sets a short one, and F35 drives the look in its own process with a clock of its own.

**Two callers and two readmes follow.** The trials' preparation (`verify/experiment/prepare.py`) baselines one requirement once
for each governed trial's job, at one service; it now gives the reason that each is a separate job under the same requirement,
so the second and later cards name the others. The demonstration of the front door (`demo_front.py`) gives one for its relaxed
copy. `verify/README.md` and `verify/README_FRONT.md` say, where they describe a pass and the record's format, what this
amendment changes.

Nothing in a signed verdict, a record or the record's checks is changed. The verdict a pass is signed with is still PASS, and
the record's checker still recomputes it; renaming it would leave every record made so far unable to verify.

## The changed files

Base: `verification-amendment-8` at `d39f7a8`. Eighteen files change. The hashes are of the files as they stand at this commit.

| file | sha256 at d39f7a8 | sha256 now |
| --- | --- | --- |
| `verify/baseline.py` | `8aa9348cbed25387e64aa0bb42357933c9f60dd1bdf655ee9dc0823422226ffc` | `075df944071a38e0672136cd26e49eac74a47c6b627f13a5b19c06ff6ea2c737` |
| `verify/verify_ctl.py` | `65ce6ad011e972a8e48a6f1098c490bede11bf7be3a5242addbc45a77595c005` | `1677886e2a1fab1059471167093ca3e21d3404b39dd3797bc848519f20727434` |
| `verify/verify_client.py` | `9316be5bc26a98a193435f62118533904423c639590b2badd2fbe1715943f2f5` | `5a272be40fc6c3927a5dd6c2ec8b6c3513bb6357a485e1f7a926fb82a2f9dbd3` |
| `verify/check_record.py` | `1cbf01f0ae0435942a3d849bfacc4a03db4b85e3c93160a167db4e5d03ca468d` | `9d556169bdf10318d973744e0c7c5e229465bd5f97f838aef02c0b55113515f3` |
| `verify/front_door.py` | `5e122666a76d2952f70492bf02cf73864fdba5b11632336016f9782f8c1c06a8` | `407e7516c8719d1d0c92794a81fcebc5989abc1fd4469e9955a4156fd54ec460` |
| `verify/notices.py` | `385385b06b9d8d116e7cbd98718dba35fea47f1414384f3230e2b31dbe21197c` | `baa1d371f67bcbcbdf828cd53038feff63606da067f6971f56f6748d866980b8` |
| `verify/verify_tools.py` | `7f05c314cd68cbc2668c141fd07f8fdbf9fdf7daabb9a2f1b3cc3292dae35750` | `6110f2daa48df1b3f51a22b42e4936a546ea65896aff9261167a4c9b465ab942` |
| `verify/front_ctl.py` | `64330e3a6324096c062c38c3683dde911c04d85f6771000d2fee9b218368ab18` | `1f7ae841eb1994ee820780280cf3562111ef548bb9597858a19c3751a2761349` |
| `verify/plea_verify_mcp.py` | `43d1b37cd079291bb1ba31b76bc4687eed32341cd01771b394a3d3de2ba3941a` | `2d75999417259fe3b3c40fa209d4b93ff26d2fa307fc292d8543c77bbb7b335c` |
| `verify/front_client.py` | `06fc9e7ac701e09d0fe7d132cc633f402999dda6ce39002c2a1bbd6a228b2c78` | `f8644be409eb678659c3cbe0bfcdde04ba526d3a45d030c7062c26770fc0db8f` |
| `verify/deploy.py` | `8836e99f608ee081aefc599c999d0f8a8d1073777266813a9f646fe631158003` | `89fd4e99df0ab58c969c796751212e3b1cb570581ad0971dd7e9d36acea4e1e6` |
| `verify/deploy_front.py` | `7df5a15149240275a513e9ed9b6e73e4b4717f75a3820827dc6b09afaa2a35a7` | `ac038d1f4c43f75fc5fbfe086153c62861c901a0f243e2b22ccf832503565bc1` |
| `verify/demo_front.py` | `bf2ab2810b666a55addd5bc6209485ece796ec59f6e8ae270c3dff74d10b7bbd` | `e2fb29d4fa2bfcfdd67f36c7598ec81d0f48127faaaef22e1dd7d7427bd873b7` |
| `verify/experiment/prepare.py` | `a8cc50d602a3bb64e1fe88f97f6e5b9dffbe326d9b9e363645837ab985c99755` | `d09b40cbaca826f892975a8b39fe15c226d75b14efc9386be68d8c47f9b25981` |
| `tests/verify_tests.py` | `c2d6a66eb255613f21d5dfa9ec8c5ba8e75a864375664d64c3ee8770be31553a` | `996bb52cefa2bde887d79ab8675cfd580018f59afaaf7a8967c854fd338ec7a0` |
| `tests/verify_front_tests.py` | `fe76692c6f701d4e65ea375eb1f53ffbe4d08dbdeb55b330a834d0de16692fa2` | `6a255b101420605cffb5978fbb618ea22ce6b202a154ead982dcfedadf0644f5` |
| `verify/README.md` | `0b8915a6b1d4feb0f5c221fb7f504098ecda798231320149385f5e6722c00616` | `55e48299339eba2b75de0fcb36e9b7cb0877ea2818060f5f9a1be58faa254cb7` |
| `verify/README_FRONT.md` | `8654b09543f1ee6f4d00b234d47062724a8e5c155e97be3e9db6058d1823c98c` | `c00c0d7a6e9ba01308d3f6d2a3b37a559af2430bab6419bbaab66552923c5450` |

One file is new as a development record: `verify/dev_amend9_mutants.json`, the pass of deliberate defects on this code.

Every other file in the repository at `d39f7a8` is unchanged, among them the record builder (`verify_record.py`), the witness
service, the gate host, the governor and the store.

## What each test is expected to show

**R1 to R17 and R19 to R21** are as declared before: the same functions, each expected true. The first lines of an answer and of
a notice are as they were; the line under the headline is new, and no check among them reads it.

**R18 is restated in its model of a notice, by two lines.** `rows_known`, which holds every line of a notice and an answer to
the rows `face` writes in their order, now expects the line "The check does not cover: ..." under the headline, and the Verdict
row of a pass as "DECLARED CHECK MET (signed as PASS)". Its checks, their number and their names are as before.

**R22 is restated for the rename only.** Its states are WRITABLE and UNCHECKED where they were PROVEN and UNPROVEN, its folder
is `inbox_checks/`, the tool's line is "CANNOT RECORD THE INBOX-WRITABILITY CHECK", and the console's lines are "inbox writable:
the gate wrote a test file in this inbox at ..." with "This is not delivery", and "INBOX NOT CHECKED: ...". Its thirteen checks
are otherwise as declared by Amendment 8.

**R23 is new** (11 checks). In a service home of its own; an error raised by any step is taken as that step's answer, so that
a defect fails a check rather than stopping the test:

1. a second baseline for a requirement the service holds, not made as a revision, is refused without a reason, and with a
   blank one; the refusal names the requirement and the baseline held and says to revise it or give a reason; nothing is
   stored and no inbox is made;
2. with the engineer's reason it is baselined, and its signed card names the baseline held, with its revision, and the reason;
3. a revision needs no reason and is linked as before, and its card has no such field;
4. a later baseline made as new names every baseline the service holds for the requirement;
5. a baseline for another requirement needs no reason, and its card has no such field, as a first baseline's has none;
6. the record's checker, on a record that verifies, the first client's view of the requirement and the front door's, in its
   text and its fields, each give the link and the reason;
7. the console's command line refuses such a draft without a reason, with exit status 1, and stores nothing;
8. a card whose link has a blank reason, no baselines, a hash that is not one, or is not a link at all, is refused by the
   card's rules;
9. an id that differs from one held only in case, in white space, in characters that show nothing, in the kind of dash or
   in its Unicode form (" req-selftest-001"; the same in full-width letters; one with a tab after it; one with a zero-width
   space in it; one with a non-breaking hyphen and a minus sign for its hyphens; one with a variation selector after it) is the
   same requirement: each such draft is refused without a reason;
10. a link written in the draft is never signed: a first baseline for another requirement, and a revision, each made from a
    draft that carries one, have none;
11. a baseline folder whose signature does not verify is not counted as held, and a first baseline for its requirement needs
    no reason; one that is whole, signed by another engineer's key, is counted, and a baseline for its requirement is refused
    without a reason, naming it.

**R24 is new** (6 checks). Through the first client, a failing design and then a passing one:

1. the answer to the pass begins DECLARED CHECK MET, with what the check does not cover on the next line and again at its end,
   and its Verdict row calls it the declared check met, signed as PASS; its exit status is 0;
2. no line of the two answers, the first client's status or the engineer's console shows the bare word PASS;
3. with no design met, the status says NOT VERIFIED and nothing more; with one met, the first client's status shows the run as
   MET and says for which design the declared check was met, that this does not say the check is correct, and what the check
   does not cover;
4. the engineer's console shows the run as MET with the same lines, and says "inbox writable: ... This is not delivery";
5. the notice of the failure has what the check does not cover under its headline and at its end;
6. the signed verdicts and the record keep the word PASS, the record verifies, and its checker prints DECLARED CHECK MET and
   lists the run that met it as MET.

Expected for the gate: 24 of 24 tests, 150 of 150 checks: the 133 of Amendment 8 and the 17 of R23 and R24 (11 + 6).

**F3 to F5, F7 to F9, F12, F14 to F18, F20, F22 to F28, F30 and F31** are as declared before, each expected true.

**F1, F2, F6, F10, F11 and F13 are restated, each in one line of its set-up.** F1, F6, F10, F11 and F13 each make, on
purpose, a relaxed copy of the requirement as a new baseline, to show what a caller could or could not do with it. F2 makes a
second baseline of the same requirement at the same service, one for each of its two cases. Under this amendment the console
asks the engineer's reason for that, so each now gives one. Their checks are as declared before.

**F21 is restated in its model of the front door's own text, by one line**: the sentence that a result does not say the check is
correct, and that what the check does not cover cannot be shown there, which this amendment adds for every verdict.

**F29 and F32 are restated for the rename only**: the refusal's code and the name of its notice are INBOX_UNCHECKED, the
folder is `inbox_checks/`, the states are WRITABLE and UNCHECKED, and F29 counts the notices of a refusal by their new name.

**F19 and F28** use the state WRITABLE where they used PROVEN; nothing else in them changes.

**F33 is new** (7 checks). Through the MCP tools, the command line and the front door's address:

1. the answer to a pass begins DECLARED CHECK MET, with what the check does not cover on the next line; its fields say the
   declared check was met and list what the check does not cover; the signed verdict in it still says PASS;
2. the status's fields say whether a design has met the declared check under that name, before a run and after it, and no
   field is called verified, in the tool's result or in the front door's answer;
3. the status's text, through the tool and through the command line, shows for which design the declared check was met, that
   this does not say the check is correct, and what the check does not cover;
4. the command line's answer to a pass begins DECLARED CHECK MET, with what the check does not cover, and exits 0;
5. no line of the words of the answers and the status, nor of the tools' descriptions or the server's instructions, shows
   the bare word PASS (a result's second part gives its fields as JSON, in which `outcome` is still PASS, and is not read here);
6. the tools' descriptions and the server's instructions call a pass the declared check met, and say it is not a statement
   that the check is correct;
7. in process, the front door's own text for a pass says that the result does not say the check is correct, and that what the
   check does not cover cannot be shown there.

**F34 is new** (5 checks). The gate host dies during a run, and is started again:

1. the host died (exit 137); started again, the gate shows that it can write the inbox; with a file in place of the inbox and
   the check taken away, the check is not good;
2. while the check is not good, the front door, started again to look for runs left pending every 0.3 seconds and to ask after
   one second, does not ask: the run is still pending, no notice of any kind is written, and nothing more was run;
3. once the gate has shown again that it can write the inbox, the front door asks for the run itself, with no design sent by
   anyone: the run is INTERRUPTED, one notice of it is in the inbox, the check was not run again, and the front door's log
   says it asked;
4. the design sent again afterwards is answered INTERRUPTED, with no second notice and nothing run; its fields say that the
   declared check was not met, and what the check does not cover;
5. with no check on record, a new design is refused as INBOX_UNCHECKED, and the engineer's notice of it is named
   INBOX_UNCHECKED, for its reason; nothing is named as before.

**F35 is new** (9 checks). The gate host dies during a run, and is started again. A second front door is made in the test's own
process, on the same service, and its look is driven with a clock the test sets, with a wait of 10 seconds. At first each ask
is answered by a stand-in that leaves the run pending:

1. the host died (exit 137) and, started again, shows that it can write the inbox; the run is pending;
2. the run is asked for once it has been pending for 10 seconds, then 20 seconds after that, then 40 seconds after that, and
   not between;
3. the wait stops growing at an hour, and after twelve asks the look leaves the run as it is; a look that cannot read the
   store forgets no wait; a wait of nought, given to another such front door, is taken as one second; nothing was run and no
   notice was written meanwhile;
4. with the journal set aside, so that it does not hold the run's design, a third such front door looks for the design at
   10 seconds, then 20 seconds after that, and not between;
5. with the baseline's budget held (HOLD, by the control plane), a fresh such front door does not ask for the run, though it
   is due, and the run is still pending;
6. with the budget open again (RECOVER) and the real path in place of the stand-in, its next look asks at once and makes the
   run INTERRUPTED, with one notice and nothing run again;
7. a look after that has nothing to do; with the notice taken away, the next look sees the run and the one after the wait writes
   the notice again, once; nothing is run;
8. with the budget held again and the notice taken away again, the notice is still written once it is due; nothing is run;
9. with the notice taken away again and the journal set aside, the notice is still written, in the service's fixed words, which
   say that the design is not shown; nothing is run.

Expected for the front door: 35 of 35 tests, 189 of 189 checks: the 168 of Amendment 8 and the 21 of F33, F34 and F35 (7 + 5 +
9).

## What was done before this declaration

All of this was on the branch, before this declaration, on 17 November.

- **The nearest tests, on the new code as each part was made.** R5, R14, R17 to R20 and R22, then F1, F6, F10, F11, F13, F19,
  F28 and F32, each passed. Of these, F1, F6, F10, F11 and F13 had first failed as expected: each made a relaxed copy of the
  requirement as a new baseline, which the console now refuses without a reason. Each now gives one (see above).
- **One defect in the new code was found by the tests.** In `face`, a comment put inside the expression that writes the
  Verdict row made the row of every verdict read "Decided by" where a computed one reads "Computed by". R18, which holds every
  line of a notice to its model, and F21, which does the same for the front door's answer, both failed on it. The comment was
  moved to a line of its own, and both passed.
- **Four of the new tests were wrong at first, and were corrected before this declaration.**
  - F29 counted the front door's notices of a refusal by their old name (`DELIVERY_`), so it counted the new INBOX_UNCHECKED
    notices as results. It now counts them by their new name.
  - R24 took the runs of the status listing to be in the order they were sent; they are listed by their number. It now
    compares them sorted.
  - F33 read the server's instructions from the wrong level of its reply to the handshake.
  - F34 first made the inbox-writability check not good by putting a file in place of the inbox. The gate's tool keeps a good
    check for up to 30 seconds, so the check was still good when the front door looked. F34 now also takes the check away, and
    restarts the gate host once the inbox is put back, so that its tool makes a new one. F34 was also made to require that no
    notice of any kind is written while the check is not good, so that a sweep that wrote one there is caught (defect S2 below).
- **The full runs of both suites on the work in progress**, from commit `0b38858`. The gate's suite, 21:05:18 to 21:07:42: 24
  of 24 tests, 147 of 147 checks. The front door's, 21:07:42 to 21:10:50: 33 of 34. F2 stopped in its set-up, before any check,
  because it baselines the same requirement twice at one service and gave no reason; it was given one (above), and passed alone
  with its 4 checks. The other 33 passed their 176 checks. The same rule would have stopped the trials' preparation
  (`verify/experiment/prepare.py`), which baselines one requirement for each trial's job at one service; it now gives a reason.
- **The first pass of deliberate defects**, on that code (`3d533d2`), 21:12 to 21:17: 28 defects and the control. The control
  passed. 25 were caught. Three stopped R23 with an error before any of its checks could fail: a defect that took away the
  refusal (K1), one that left the link out of the card (K2), and one that asked a reason of a revision (K5). R23 was changed so
  that an error in any of its steps is taken as that step's answer, and a check fails.
- **An independent review** of the change at `0b38858`, read only, by a separate agent given the diff and asked to find what
  is wrong. It reported nine things. What was done with each:
  1. *Continuity could be dodged by an id that prints alike* (a space at the end). Fixed: ids are compared in Unicode's
     compatibility form, without case, with white space folded. Ids whose letters only look alike stay open.
  2. *A link written in the draft was signed*, so a first baseline or a revision could name baselines that never existed; and
     a forged or damaged folder was counted. Fixed: the draft's link is dropped, and a folder counts only if its envelope
     verifies. A folder signed by someone else's own key stays open.
  3. *The look asked forever for a run it could not finish*, each time adding decisions to the audit log, also on a held or
     stopped baseline. Fixed: the wait doubles at each ask, up to a limit (six hours at first; an hour after the second
     review), and nothing is asked while the budget is held or stopped.
  4. *The look read every job's runs, and the whole journal, every 30 seconds*, with nothing pending. Fixed: it reads one
     observation of the store for each job, and more only when a run is due.
  5. *A revocation made during a look did not stop it*, and a revoked job's run is asked for through another job on its
     baseline. The first is fixed: the binding is read again just before an ask (not tested). The second is stated as it is, in
     the code and below.
  6. *The look never wrote a missing notice of a run cut off.* Fixed: it does, once the run is due.
  7. *A bare PASS could still be read*: in a tool result's second part (its fields as JSON), in the record checker's list of
     runs, and, as "verified", in the views of the requirement; the INTERRUPTED answer lacked the new fields, and the front
     door's fields of the requirement lacked the link. The checker now lists MET, the views say "checked", and the answer and
     the fields carry what they lacked. The JSON part keeps `outcome` PASS, and F33's check says so.
  8. *Wording*: the console said "INBOX NOT CHECKED" for a check that had been made and failed or gone stale (fixed: each state
     has its own heading); the front door's readme still documents `DELIVERY_UNPROVEN` in its note of 17 November, which is kept
     as the record of Amendment 8, with this amendment's note after it; and `face` raised an error on a verdict value it had no
     words for (fixed: printed as it is).
  9. *Tests*: F2 and the trials' preparation (fixed before the review reported, above); what is not exercised is listed under
     "What is not tested". F35 was written for findings 3, 4 and 6, and R23 was given three checks for findings 1 and 2.
- **The second form** (`b1e2b98`), which carries those fixes, F35 and the changed R23. Its full runs: the gate's suite,
  21:26:33 to 21:28:57, 24 of 24 tests and 150 of 150 checks; the front door's, 21:28:57 to 21:32:16, 35 of 35 tests and 186 of
  186 checks (F35 then had 6). Its pass of deliberate defects, 21:32 to 21:39: 39 defects and the control; the control passed,
  38 were caught, and one (K5) still stopped R23 with an error, in a check that compared a revision's hash it did not have. That
  check now compares the hashes as text.
- **A second independent review**, of the fixes alone (`3d533d2` to `b1e2b98`), by another agent. It reported fourteen
  things, five of them of medium weight, all in the look and the continuity rule:
  1. *a run passed over because the journal does not hold its design* skipped the doubling of its wait, so it was looked at in
     full on every look: fixed, every run looked at when due waits twice as long next time (F35, check 4);
  2. *a wait of nought* (`--sweep-after 0`) stayed nought: fixed, a wait is at least one second (check 3);
  3. *one error reading a job's baseline* made the look forget that job's waits: fixed, a look forgets only what a baseline
     read without error no longer shows (check 3);
  4. *a wait carried across a run's states*, so a run cut off whose notice was missing could wait six hours before its first
     look: fixed, a run is kept by its state, and seen afresh in a new one; and the limit is an hour, not six;
  5. *a missing notice was not written while the budget was held or the inbox check not good*, which only an ask needs: fixed
     (check 8);
  6. *the key a folder was checked under was its own*, so a folder whole and signed by any key was counted: fixed, only the
     engineer's key or one the service accepts (R23, check 11, now with such a folder);
  7. *ids still dodged the rule with invisible characters or another dash*: fixed (R23, check 9); letters that only look alike
     stay open;
  8. *revise* refused an id spelled otherwise than its baseline's with words that contradicted the console's: it now names the
     spelling to keep (not tested);
  9. *face* can still raise on a reason code it has no headline for; that is as before this amendment, and is not changed;
  10. three comments, and the log line for a notice written by the look: fixed;
  11. to 14. what the tests do not exercise: added to "What is not tested", or tested as above.
- **The third form** (`0b305f6`), which carries those fixes. Its full runs: the gate's suite, 21:42:21 to 21:44:49, 24 of 24
  tests and 150 of 150 checks; the front door's, 21:44:49 to 21:48:03, 35 of 35 tests and 188 of 188 checks (F35 then had 8).
  Its pass of deliberate defects was begun and stopped after twelve, when the third review reported, since the code was to
  change.
- **A third independent review**, of the second review's fixes alone (`b1e2b98` to `0b305f6`), by another agent asked for
  findings of medium weight or more. It reported five, and nothing of high weight:
  1. *a run cut off whose design the journal does not hold never got its notice*, and the log said it had: fixed, the notice is
     written in the service's fixed words, and the log says whether it was written (F35, check 9);
  2. *counting only the engineer's own key and the gate's, read from the console's environment, was a regression*: an engineer
     whose colleague held a baseline for the requirement was let make one as new. The key a folder is counted under is again the
     one its card names, so any whole folder counts, and a folder put in by someone who can write the service's home is counted;
     this is stated below (R23, check 11, now with a colleague's baseline);
  3. *other characters that show nothing* (variation selectors, the combining grapheme joiner, the Hangul fillers) still made
     an id another requirement: fixed (R23, check 9);
  4. *a run whose ask always fails was asked for once an hour for ever*, each ask adding decisions to the audit log: fixed, the
     look acts on one run at most twelve times, then leaves it until the front door restarts (F35, check 3);
  5. *after the front door restarts, the look's ask journaled a design again*, counting it against the baseline's share of the
     journal: fixed, a design found in the journal is marked as journaled before it is asked for (not tested).
  It also said F35 and R23 tested some of their claims only in part; the checks named above were added for that.
- **The fourth form** (`12da2dc`), which is the code this declaration carries. Its full runs: the gate's suite, 21:54:32 to
  21:56:51, 24 of 24 tests and 150 of 150 checks; the front door's, 21:56:51 to 22:00:07, 35 of 35 tests and 189 of 189 checks.
  These are the counts expected below.
- **Its pass of deliberate defects**, 22:00 to 22:08: 48 defects and the control, kept in `verify/dev_amend9_mutants.json`. The
  control passed unchanged. All 48 were caught by a check that failed, and none stopped a test with an error. They are W1 to W15
  (what a person reads of a pass), K1 to K15 (the continuity rule), N1 to N4 (the name of the inbox-writability check) and S1 to
  S14 (the look for runs left pending). Each names the tests it was run against and the checks that caught it.
- **The fourth form, which this declaration carries, was not itself read by a reviewer.** The fixes of each review were read
  by the next; those of the third were read only by their author.

## What stays open

- **The record is still evidence of process, not of correctness.** This amendment changes what people read, so that a pass is
  not read as more than it is. It cannot make a wrong check right, and a reader can still take a record for more than it says.
- **The signed verdict is still PASS.** Every signed verdict and record keeps that word, and a caller that reads the `outcome`
  field, the second part of a tool's result (its fields as JSON), the counts by outcome (`runs`), or the verdict inside the
  answer, still sees it. The new fields stand beside it.
- **A record still does not show that it is current**, and nothing signs the latest sequence number. That needs a statement by
  the witness, held by a second party (the reviewer's point 3, first half).
- **Continuity is linked only within one service.** An engineer who holds the key can still give a relaxed requirement a new
  requirement id, which this rule does not see, or baseline it at another service. Ids that print alike only because their
  letters look alike (a Latin letter and a Cyrillic one) are different to the rule; case, white space, characters that show
  nothing, the kind of dash and Unicode's compatibility forms are not. Closing this needs a register of requirement ids held by
  someone other than the engineer. A revision is linked only to the baseline it supersedes: a revision made while other
  baselines are held for the requirement does not name them. A baseline folder whose envelope is not whole is not counted as
  held, so a damaged one lets the next baseline for its requirement be made as a first. A folder put in by someone who can write
  the service's home, whole and signed by a key of their own, is counted, and named in the link of the next baseline made for
  its requirement. The rule is in the console: a card made and signed by other means is not refused by the gate.
- **A notice is still a file the service writes about itself**, and the inbox-writability check is too (the reviewer's point 4,
  first half). Independence needs a second party: a statement by the witness of the runs admitted, the verdicts recorded and the
  notices written.
- **The front door's look for runs left pending** runs only while the front door runs, and starts its waits afresh when the
  front door restarts. It asks for a run only if the journal holds its design: a run whose journal line was removed by an
  operator stays pending. A run on a baseline whose budget is held or stopped is not asked for, and a run on a superseded
  baseline, which is stopped, stays pending. Runs are a baseline's, not a job's: a run that a revoked job began is asked for
  through another live job bound to the same baseline, if there is one. A run that was admitted and never reached the gate host
  is run by the look, with no caller waiting for its answer; its verdict is on the record and its notice, if it is not a pass,
  goes to the engineer. A run that cannot be finished is asked for at most twelve times, the last of them about eight hours
  after the first, and each ask may add some decisions to the audit log; it is then left as it is, shown as pending in the
  console, until the front door restarts, when it is asked for again as if new. No notice says that the look has left it. A run
  asked for while the witness or the store was down waits as long as any other, up to an hour after they are back. A run left
  pending on a baseline the engineer holds is not asked for until the budget is open again; its notice, if it was cut off, is
  written meanwhile. Through the first client, which has no front door, a run cut off still gets no notice. Each look reads the
  store once for every job, and once more for each run the gate began that has no notice, every 30 seconds.
- **The first client** (D6 in the register) is unchanged but for its status listing, its view of the requirement and its help;
  its answer to a made-up hash still says the engineer has been sent the result.
- **The amendment's own files** before this one, the declarations and results of Amendments 7 and 8 among them, keep the words
  they were run with: "proof of delivery", `delivery/`, `DELIVERY_UNPROVEN` and "verified".

## What is not tested

- A host product reading the new fields, or an assistant reporting a pass in the new words.
- The front door's look at its own defaults (120 and 30 seconds, an hour), and on more than one job or baseline at once. F34
  uses a wait of one second and a look every 0.3 seconds, on one job; F35 drives the look with a clock of its own, on one job.
- That the look reads a job's binding again before it asks, so that a revocation made during a look takes effect: the race is
  not made to happen in a test. The look passing over a job revoked before it starts is not tested either.
- A stopped baseline (F35 holds the budget; it does not stop it), and the look's single reading of the store for a job with many
  runs.
- A run that was admitted and never reached the gate host, which the look would run for the first time. It is not made to happen
  in a test.
- The look passing over a revoked job, a job whose binding was not signed by a pinned engineer, or a run whose design the
  journal does not hold.
- A requirement given a new id to avoid the rule, ids whose letters only look alike, a folder signed by a key of someone else's,
  and baselines signed by two engineers' keys for one requirement. R23 tests a folder whose signature does not verify.
- That a reader of the new wording is in fact not misled.
- F34's steps on a check that is not good must end within 30 seconds of the gate's last good check, before its look makes a new
  one; here they take about ten. The checks that count one notice on the day (F29 to F32) would fail across midnight UTC.
- The console's headings for a check that went stale or could not write (INBOX CHECK OUT OF DATE, INBOX NOT WRITABLE); R22 and
  R24 read only the headings for a good check and for none. What `revise` says of an id spelled otherwise than its baseline's. A
  baseline counted under a key from `VERIFY_ENGINEER_KEYS`.
- That a design the look finds in the journal is not journaled again, and the look's line in its log when it leaves a run.

## Commands and results

The official runs are these, each once, from the tree at the commit that carries this declaration, with the services on
127.0.0.1 and PostgreSQL 16:

    cd tests && python3 -B verify_tests.py
    cd tests && python3 -B verify_front_tests.py

Each output file is copied to `verify/results_verify_tests_amended9_2026-11-17.json` and
`verify/results_front_tests_amended9_2026-11-17.json`. The outputs folder is not committed.

Expected: for the gate, 24 of 24 tests and 150 of 150 checks; for the front door, 35 of 35 tests and 189 of 189 checks. A check
that comes out other than expected is reported as it came out, in the amendment that follows the runs, and is not run again
under this declaration.
