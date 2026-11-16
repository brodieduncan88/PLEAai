# Amendment 7: declaration before the official test runs

16 November 2026. Private working material.

This file is committed before the official runs of `tests/verify_tests.py` and `tests/verify_front_tests.py` on the branch
`verification-amendment-7`. It fixes the changed code, states what each test is expected to show, and records what was done
in development. Each official run is made once after this commit and its first result is kept, pass or fail. A later
correction would be a separate, dated amendment. Times are UTC.

## Why declared files are changed

Five defects in the engineer's defect register, which are the pilot blockers in the review pack, section 3, are repaired
here. The register's own words:

- **D1** (front door, `_submit()`): "Every accepted design, repeats included, is appended to a journal with no size limit
  (front_door.py, _submit()). One job certificate, at the pace allowed, can add about 3 to 8 GB a day. A full disk then
  stops notices for every job (D2)."
- **D2** (delivery): "If the inbox or the tool's ledger cannot be written (full disk, changed permission, a file in place of
  the folder), the run is counted, never a pass, with no verdict and no notice. A part-written notice can be left."
- **D3** (delivery): "With the console and the gate under two accounts, the inbox the console makes is the console's. If the
  gate cannot write in it, a failing run stops with no verdict and no notice. This is the first step of separation, not
  damage."
- **D4** (baselining): "The card's rules accept a check's stated limits that are not text (baseline.py, line 240); a notice
  joins them as text (line 436). On such a card, which can be signed today, a failing run gets no verdict and no notice."
- **D11** (delivery): "A run cut off when the gate host dies is counted INTERRUPTED, never run again, and gets no notice."

The other pilot blockers, D5 to D8, are not touched by this amendment (see "What stays open").

## What is changed, and what is fixed

**Notices (D2, D3).** A new module, `verify/notices.py`, says where a notice goes and how it is written. A notice goes to the
engineer's inbox as before (Amendment 6). If the inbox cannot take it, the notice goes to `undelivered/<full hash>/` in the
service's own home, which the console's status lists. If neither can take it, the answer says so. A notice is written whole
or not at all: under a temporary name, then linked to its name, and where the file system makes no hard links, written
under its name in one piece and taken away again if the write stops part-way, by an error or by an interrupt. A notice is
never written twice under one name, in either place. The gate's verdict is returned whatever happens to its notice, and
carries a field `notice` with the state: `INBOX`, `UNCLAIMED`, `UNDELIVERED`, `NOT_WRITTEN`, or `NO_HASH` when the request
names no usable hash. A notice whose text cannot be built from the card is written in fixed words, which repeat no text from
the card or the design. The ledger is kept for the tests and never stops a run, not even when its error output fails too.

**Stated limits (D4).** `validate_card` requires each stated limit to be non-empty text. The console refuses such a card at
baselining. Every run refuses a card already signed that way, because `load_envelope` calls `validate_card`; the run is
answered UNKNOWN as not a baseline card, and its notice goes to the engineer's inbox in fixed words.

**The journal (D1).** The front door refuses a new run before any attempt is made, with 507 `STORAGE_FULL`, if journaling
the design would take the journal past `journal_max_bytes` (default 1 GiB), or if the disk holding the journal would have
less than `disk_reserve_bytes` free (default 512 MiB), the space kept for notices. The reserve applies to every submission,
a re-ask included. A design is journaled once per process, so a repeat adds no line. A journal line that a failed write
left part-written is taken back. Both limits are set on `front_door.py` with `--journal-max-bytes` and
`--disk-reserve-bytes`.

**Interrupted runs (D11).** When the service answers a run as INTERRUPTED (the gate's signed UNKNOWN), the engineer is sent one
notice of it, named `INTERRUPTED_<attempt id>`, however often the answer is asked for again. The notice gives the run and the
design, says that the service did not finish the run and no verdict was recorded, that the run is counted and will not be run
again, and that it is not a pass. A failed ask, or a status call, that finds an interrupted run without its notice writes it
too. The answer to the ask says so when the notice could not be put in the inbox.

Nothing else is changed. A notice for a verdict that is not a pass says what Amendment 6 had it say, and a PASS verdict
carries no notice and no `notice` field. The wording of the interrupted notice is new.

## The changed files

Base: `verification-amendment-6` at `118e2a3`. Six files change, and one is new. The hashes are of the files as they stand
at this commit, with the base at `118e2a3`.

| file | sha256 at 118e2a3 | sha256 now |
| --- | --- | --- |
| `verify/notices.py` (new) | - | `67c1c6d1c1ecb05ddcdb4125d7bdaafe34634845ebe2ec941ebb5b1b98f8c4a7` |
| `verify/verify_tools.py` | `9f977e1db76ab41b9f695ec42ad6086c8a32e3b4bb8e2fa25321555d45d9e351` | `477c243bee40ef4a3dcb4d1866c02523693f118f7d52f00fc897cb42cda33c0b` |
| `verify/baseline.py` | `0f01523d7e34bda3b31e4abf131d4286b208b92a4a4f38d6c53d05cb20e94d80` | `8aa9348cbed25387e64aa0bb42357933c9f60dd1bdf655ee9dc0823422226ffc` |
| `verify/front_door.py` | `c83f281c11f556106891bbe3c8ef06b6ed0d32599cc6f9eedaf5f6c6585041e4` | `5ab2dacb5c5a1fa23f1f6e998605868b437c2f70a7b81b8aa8734974815d0c3a` |
| `verify/verify_ctl.py` | `83f8244984dc242534df0d111b0336b589833afe5b59b926f577066369e4433c` | `530f2145bad430843b78e17867ad47587119df9e6518e7f8ca86f3bc731a4123` |
| `tests/verify_tests.py` | `3ec14b03472ad85ef9b472ba96c8ef1e7ad006721f1718428627046ea18b34f4` | `a8008a8c0cf15422abb8ed58579dceb38072e4e49451afa302934d68afa77567` |
| `tests/verify_front_tests.py` | `71376af02bbe4e46c528a8ecf44e5b077dc724715b4da4fce46e99140730a505` | `2ddc69bb2ad0401f771f601f7ea03d7d3b5cada01139373d3dbeb290ee994008` |

One file is new as a development record: `verify/dev_amend7_mutants.json`, the pass of deliberate defects on this code,
whose result is given below.

Every other file in the repository at `118e2a3` is unchanged. The verification record's own rules, the witness service, the
gate host, the governor, the store and the first client are not in the change.

## What each test is expected to show

**R1 to R19** are as declared in the earlier declarations: the same functions, each expected true. Together they are 19 tests
and 106 checks, as at Amendment 6. R16 calls the tool's `_notify` by name to check how notice names are given; `_notify` is kept
as a wrapper over the new delivery, so R16 tests the same thing.

**R20 is new** (11 checks). The tool is called in a child process with its own service home, and each failure of a notice is
made in turn, by replacing the inbox with a file, by refusing writes as another account would, by filling the disk part-way
through a copy, by refusing every place, by refusing the ledger and its error output, by making the notice text fail, by
asking for one copy of a name in two places, and by stopping a write part-way with no hard links. Expected: each verdict is
returned, each notice is in the place its state names and is whole, no temporary file is left, no error escapes, and a
normal failing run is unchanged. Expected: all 11 true.

**R21 is new** (3 checks). A check whose stated limits are not text is refused at baselining, and a card signed that way is
refused at every run as not a baseline card, with its notice in the engineer's inbox and no error raised. Expected: all 3
true.

**R1 to R19 and R20 and R21, together**: 21 of 21 tests pass, with 120 of 120 checks, expected.

**F1 to F18 and F20 and F21** are as declared before: the same functions, each expected true. F17 is as declared: two failures
whose notices would once have had the same name each reach the engineer. F17 reads a notice's file name from the ledger; the
ledger's verdict line still carries it.

**F19 is restated.** It was the Amendment 2 test of the known limit, which asserted the defect: with the inbox replaced by a
file, a failing design was answered as an interrupted run, with no verdict and no notice. That is D2, which this amendment
repairs. The restated F19 expects the repaired behaviour, with seven checks in place of six: the design is still FAIL and
counted with its verdict; the answer says the notice was not delivered and that one copy is kept in the service's own
store; the same design asked for again is answered the same, without a second run; every run has its verdict on the
record, all three FAIL; the next failing design, with the inbox put back, is FAIL and its notice goes to the inbox; and the
record verifies, with status NOT VERIFIED and no run meeting the check. The Amendment 6 results file keeps the old
expectations as they were run. Expected: 7 of 7 true.

**F22 to F27 are new**, and the checks are:

- **F22** (3 checks): a full journal stops new runs at the door: the next design is refused with 507 and nothing run or counted,
  and the journal keeps its size.
- **F23** (4 checks): with less free space on the journal's disk than the notices keep, a new design is refused; before that, a
  repeat of a journaled design, with room to spare, is answered and adds no line and no run; and at the reserve a repeat is
  refused too.
- **F24** (6 checks): a run cut off when the gate host dies is counted INTERRUPTED, the engineer has one notice of it and no
  other, the notice says the run was interrupted, is not a pass, will not be run again, shows the design, and says no verdict was
  recorded, and the answer does not say the notice was lost.
- **F25** (4 checks): a verdict the service cannot put in the engineer's inbox is still returned at the door, the answer says the
  notice was not delivered, the notice is kept once in the service's own store, and the console lists it as kept undelivered.
- **F26** (3 checks): a journal write that fails part-way is taken back: the line is not left torn, the design is refused at the
  door with 507 with nothing run, and the next design is journaled whole.
- **F27** (4 checks): a run the gate has not yet signed as interrupted is not noticed by a look at the job's runs; it is PENDING.
  The next ask, which the gate answers as interrupted, writes one notice; later looks and asks write no second one.

Expected for the front door: 27 of 27 tests pass, with 135 of 135 checks, expected. The count is the 110 checks of Amendment 6
with F19's six replaced by its seven, plus the 24 of F22 to F27 (3 + 4 + 6 + 4 + 3 + 4).

## What was done before this declaration

All of this was on 16 November 2026, in the repository on this branch.

- **The first form** passed the gate tests but R16, which calls `_notify` by name: the name had been removed in the rewrite of
  the notice path. `_notify` was kept as a wrapper, so R16 tests the same thing.
- **The first full run of the front suite** found two things. F17 read the file names of notices from the ledger, and the
  ledger had been given the notice's state instead of its name; the ledger keeps the name now, and the state in a second field.
  F19, the known-limit test, asserted the defect and is restated as above.
- **Two new checks found faults in the tests themselves.** F26 counted the calls after the second design had also run, not
  after the refusal; corrected. F27 assumed the gate reports a cut-off run as interrupted before the next ask, which it does not:
  the gate signs its UNKNOWN when the design is asked for again, and until then the run is PENDING. F27 is restated to that.
  Its first version is not kept as evidence.
- **One review of the change, before the declaration.** A separate AI agent, read-only and not given the author's conclusions,
  was given the register's text for the five defects and the intended repair, and asked whether a verdict can be lost, a notice
  lost, partly written or written twice, a refused run journaled or counted, an interrupted notice written wrongly or not at all,
  or a non-text limit reach the notice. It reported seven findings and found no defect in the stated-limit check, in the
  race between journal check and write, or in the unchanged verdict fields. Dispositions:
  - *High, a verdict lost when the ledger's error output also fails* (`_ledger` raised out of the tool): **fixed**. The ledger
    never raises (R20, the "error output may fail too" check; planted defect M17).
  - *Medium, a re-ask during a disk shortage was not held to the reserve* (a design already journaled skipped the check): **fixed**.
    The reserve applies to every submission (F23, the repeat at the reserve; planted defect M12).
  - *Medium, an interrupted notice written only at the ask that finds the interrupted answer, not on a failed ask or a look*:
    **partly fixed**. A failed ask and a status call write the notice when the store already shows the run interrupted (planted
    defects M21, not caught, see below). The gate signs the UNKNOWN only at the next ask for the design, so a run nobody asks
    about again stays PENDING and is not noticed. That is the gate's protocol, not changed here (see "What stays open").
  - *Medium-low, a stop part-way through a write with no hard links left the notice under its name*: **fixed** for any stop the
    process can see, an error or an interrupt (R20, the "stopped" check; M19). A kill that the process cannot see is open.
  - *Low, one copy of a notice name across the inbox and the store*: **fixed** (R20, the "one copy" check; M18).
  - *Low, a journal line part-written by a full disk, the next line appended to it*: **fixed**. The line is taken back (F26; M20).
  - *Low, the interrupted notice said the service "stopped" when a tool raised*: **fixed**. The wording now says the service did not
    finish the run and no verdict was recorded (F24; M22).
  - Also raised, and not a change of this amendment: a notice is written inside the tool before the gate host records the result,
    so a host that dies between the two leaves a notice of a verdict the record does not hold (the order is as before, see "What
    stays open"), and a failed read of the store in building an answer gives a 500 with no notice in that answer (before this
    amendment; open).
- **Planted defects**, deliberate faults in a scratch copy, one at a time, each run against the checks that cover its repair. The
  first pass, on the code before the review's fixes, caught 16 of 16. The final pass, on this code, is recorded in
  `verify/dev_amend7_mutants.json`: the control M0 passes unchanged, and 21 of 22 defects are caught, M1 to M20 and M22. M21 is
  not caught: a look at the job's runs writes no notice for an interrupted run. That path is a backup for the ask; it is not
  separately tested, and the declaration says so.
- **Full development runs on this code** before this declaration, in this order: the gate suite 21 of 21 with 120 checks, and the
  front suite 27 of 27 with 135 checks, both on the code as it stands at this commit.

## What stays open

- **D5 to D8 are not repaired.** D5: the gate does not bind the baseline to the budget admitted. D6: the first client's defects
  1, 2 and 5. D7: no way to tell a current record from an old one. D8: separation by process and credential only.
- **The gap-table rows on the keep list** (G4, G7, G8, G10, G11) are not in this amendment.
- **An interrupted run is noticed when the gate signs it.** The gate answers a run as interrupted, and signs its UNKNOWN, at the
  next ask for the same design. A run nobody asks about again stays PENDING, and it is neither counted INTERRUPTED nor noticed.
  F27 shows this. A guarantee that every cut-off run is noticed would need the gate to finalise its interrupted rows without an
  ask. That is a change to the gate's protocol, and it is not made here.
- **A notice is written before the verdict is recorded.** The tool writes the notice inside `verify()`; the gate host then records
  the result. A host that dies between the two leaves a notice of a verdict the record counts as interrupted. The order is as it
  was; it is not changed.
- **A stalled host that finishes later** records its verdict on the record; the interrupted notice is not withdrawn, and the
  verdict is sent as its own notice.
- **Undelivered notices reach the engineer only through the console's status, or from the store.** Who can read the store depends on
  the deployment's permissions. This was not tested across accounts.
- **The journal's limits are defaults**: 1 GiB for the journal, 512 MiB of disk kept for notices. The operator sets them. At the
  limit the front door refuses new runs, which is an availability cost. No archive or rotation procedure exists; an operator must
  make room. A run refused for storage is not run and not counted, and the engineer is not sent a notice of the refusal; the
  refusal's text goes to the caller.
- **The journal's memory of designs is per process.** After a restart, a design journaled before is journaled once more.
- **The verdict now carries the field `notice`**, from this amendment on. The record checker does not read the field. Records made
  before this amendment verify as before; the record tests are unchanged and pass.
- **A kill that the process cannot see** (a power cut, or a kill signal) between writing a temporary name and linking it leaves that
  temporary name in the folder. No notice of that name exists, and the console counts only `.txt` files. Where the file system
  makes no hard links, a kill during the write under the final name can leave a part-written notice under that name. The usual
  hard-link path is whole or nothing.
- **The look paths** (a failed ask, and a status call) that write an interrupted notice are backups. Their own effect is not
  separately tested (planted defect M21).
- **The fixed-words notice** for a card whose text cannot be built is reached only if a part of the notice fails. Nothing in the
  present cards reaches it: `validate_card` now rules out a non-text limit, and the other fields it shows are checked already.

## What is not tested

- Real permissions across two accounts. The two-account failure is simulated by making the gate's writes fail, in the test
  process and in the tool's child process.
- A real full disk. Each write that fills a disk is simulated by a write that stops part-way. The container has 28 GB free.
- A real kill during a write. It is simulated by an interrupt raised inside the write.
- A power cut, and a kill between the link and the removal of a temporary name.
- An engineer reading undelivered notices through the console on another account.
- An assistant's reaction to the 507 refusal, beyond its text.
- Behaviour near the 1 GiB journal limit: the checks use small limits.
- File systems without hard links, other than by simulation.

## Commands and results

The official runs are these, each once, from the tree at the commit that carries this declaration, with the services on
127.0.0.1 and PostgreSQL 16:

    cd tests && python3 -B verify_tests.py
    cd tests && python3 -B verify_front_tests.py

Each output file is copied to `verify/results_verify_tests_amended7_2026-11-16.json` and
`verify/results_front_tests_amended7_2026-11-16.json`. The outputs folder is not committed.

The expected results are: gate 21 of 21 tests and 120 of 120 checks; front door 27 of 27 tests and 135 of 135 checks. Every
outcome must match this declaration. An outcome that does not match is recorded as it is, and the amendment says so.

## Packaging

`verify/notices.py` is a new file. A commit that omits it breaks the imports of `verify_tools.py` and `front_door.py`. It is
added with the declaration commit.
