# Amendment 10: declaration before the official test runs

19 November 2026. Private working material.

This file is committed before the official runs of `tests/verify_tests.py` and `tests/verify_front_tests.py` on the branch
`verification-amendment-10`. It fixes the changed code, states what each test is expected to show, and records what was done
in development. Each official run is made once after this commit and its first result is kept, pass or fail. A later
correction would be a separate, dated amendment. Times are UTC.

## Why declared files are changed

A record is a statement as of its own sequence number. An older record leaves out later runs and still verifies, and nothing
outside the record said which record was the latest. The owner's reviewer raised this twice: in point 3 of 17 November, and as
release gate G6, "witness-signed freshness checkpoints", on 19 November. It is D7 in the defect register. Amendment 9 left it
open. On 19 November the owner asked for G6 to be built as this amendment, by the same process as Amendment 9.

## What is changed

**The witness signs a checkpoint.** `GET /checkpoint?root=R` on the witness service returns a statement of one budget's chain
as the witness reads it at that moment, signed with the witness's key. It gives:

- the number of decisions recorded (`seq`);
- the hash of the last (`head`), or of the provisioning record when there are none;
- the budget's two states (`business`, `witness`);
- the witness's clock (`time`).

A `nonce` the asker gives (1 to 64 letters, digits, `-` or `_`) is signed back, so the asker knows the statement was made
after it chose the nonce. `at=K` also asks for `head_at`, the head after decision K, so that an older record can be shown to be
a true beginning of the chain. The witness reads that one hash from the store, not the whole chain.

The reading changes nothing and adds no decision. The witness answers 400 to a request with:

- no budget named, or a name longer than 512 characters or holding a control character;
- a nonce of another shape;
- an `at` that is not a whole number or is beyond the chain.

It answers 404 for a budget it does not hold.

A name given with the new option `--tls-allow-read NAME` may read `/checkpoint` and nothing else: the witness refuses it
`/accept` and `/pubkey`, also when no `--tls-allow` list is given. The demonstration gives the new client certificate,
`keeper`, only that. Names in `--tls-allow` (the governor's) may read checkpoints as well.

What the witness signs as a checkpoint has a `statement` field and no `aid`; a receipt has an `aid` and no `statement`. So
neither can be passed off as the other. This is the first change to the witness service since v1.2.1. Its `/accept` and
`/pubkey` are as they were, for every name they admitted before.

**A record carries a checkpoint.** The record builder asks the witness for a checkpoint that names the head after the record's
last decision (`at` equal to the record's `as_of.seq`). It puts the checkpoint in the record as `checkpoint`, under the
engineer's signature. The two consoles check that answer before they sign: it must be the witness's, for this budget, and name
the record's own last decision and head. Otherwise they refuse to write the record.

The checker has a ninth check. The checkpoint must:

- have exactly the fields the witness signs;
- be signed by a witness key given;
- be for this budget;
- name the record's own last decision and head.

So the record's as-of point is the witness's word as well as the engineer's. A record built without a checkpoint (the console
without `--witness-url`) has no such field, verifies as before, and its ninth check says it has none. Records made before this
amendment verify unchanged.

**The checker says whether a record is current.** `check_record.py --checkpoint FILE` takes a checkpoint obtained separately
from the record and prints one of these:

- CURRENT: the checkpoint's chain ends exactly where the record does, with the same head, and the checkpoint is no older than
  the age allowed (`--max-age`, an hour unless given);
- SUPERSEDED: the chain has gone on, and the checkpoint shows that the record's head is where that chain was (`at`, `head_at`);
- SUPERSEDED_UNPROVEN: the chain has gone on, and the checkpoint does not say what its head was at the record's point;
- FORKED: the checkpoint gives another head for a decision the record holds, as the chain's head or as an earlier one, so the
  record is not of the chain the witness holds;
- OLDER: the checkpoint is from before the record and says nothing of it;
- STALE: it would be current, but the checkpoint is older than the age allowed by this computer's clock;
- INVALID: one of these is true:
  - the checkpoint is not signed by a witness key given;
  - it is for another budget, or is not a checkpoint;
  - it was edited, or carries a field the witness did not sign;
  - its numbers are not whole numbers;
  - it does not sign back the `--nonce` given;
  - it is dated more than five minutes ahead of this computer's clock;
  - the age given is not a number.

The library (`currency`) says CURRENT_AT, not CURRENT, when no age is given: current at the checkpoint's time, and no more.

Where the budget was not open when the checkpoint was made (superseded, closed or held), the sentence says so. CURRENT says no
more than its definition: an old checkpoint handed over again with an old record reads CURRENT while it is within the age
allowed. A reader who wants to know the record is current now fetches the checkpoint themselves, with a nonce of their own.

With no checkpoint given, the checker prints "CURRENCY: NOT CHECKED" and exits as before. With one, the exit status is 0 only
if the record verifies and is CURRENT. The command refuses, with exit status 2:

- `--max-age` or `--nonce` without `--checkpoint`;
- a checkpoint file with no name;
- an age that is not a number;
- a checkpoint checked with the keys read from the record itself rather than given separately.

**A second party can keep the checkpoints.** `verify/checkpoints.py fetch` asks the witness over mutual TLS, with a nonce of
its own making unless one is given. It refuses an address that is not https, a client with no certificate, an answer larger than
64 KiB, and an answer for another budget or nonce than it asked. With `--log` it appends the checkpoint to a log, and asks the
witness for the head at the last sequence number the log holds for the budget. A checkpoint is kept only if it answers that
question: it names that number (`at`) and gives the head the log holds for it. So each checkpoint kept is tied to the one before
it by the witness's own signature.

The keeper refuses, and keeps nothing in the log, when the checkpoint:

- is not the witness's;
- has a sequence number lower than one already held (ROLLBACK);
- gives another head for a sequence number the log already knows, as the chain's head or as an earlier one (FORK);
- does not answer for the last number kept.

A checkpoint that contradicts the log (ROLLBACK or FORK) is written to `LOG.refused.jsonl` beside the log, as the evidence that
the witness said two things. If the witness says that the log's last number is beyond its chain, the keeper asks again for the
chain as it stands, and puts that signed answer aside as the evidence of the rollback.

The log takes one writer at a time (a file lock). A last line cut off by a crash is reported by `audit` and taken away by the
next keeping. A whole last line that lost only its line end is given one. `audit` re-reads a whole log by the same rules. The
file needs only the standard library and `cryptography`.

The engineer's two consoles take `--witness-url` and the TLS files for `record`. The test deployments issue the `keeper`
certificate, start the witness with `--tls-allow-read keeper`, and build every record with a checkpoint unless asked not to.
`verify/README.md` says how to ask whether a record is the latest.

## The changed files

Base: `verification-amendment-9` at `f9ae97f`. Eleven files change, one of them new.
The hashes are of the files as they stand at this commit.

| file | sha256 at f9ae97f | sha256 now |
| --- | --- | --- |
| `plea_gateway/receipts.py` | `be23f1182d2110399e4584c630017f81f59246737294efde519db6e1f6541b6e` | `adf926b34a78197ea0a0934a79a136bb8bbf2e75286bf8a14efc98c429024a45` |
| `plea_gateway/witness_service.py` | `92ea90044d14fe2180fb9fdf15caf11cb2ad49caa21eef9bf3365bcc2e9155b0` | `d5766582555fa7d808d3029e8b74e885c39a76b70006a3e06c92349f69d81bdc` |
| `verify/check_record.py` | `9d556169bdf10318d973744e0c7c5e229465bd5f97f838aef02c0b55113515f3` | `6a972088927a6e242e7bac112e47472f6d1ff85bb16aaf23db228adf74b57b7e` |
| `verify/checkpoints.py` | new | `4c5b92fd95498a46aaf73af01cdce02333c7c19ddbcaa966acce1d36d266223f` |
| `verify/verify_record.py` | `7fc8c168bf57f400434abbdf236eae399901a503db7106e33b6ac633588e38f3` | `160fe58529c755e9c5d13f980ac50eaaa22c57ace320432653d9210946cd3811` |
| `verify/verify_ctl.py` | `1677886e2a1fab1059471167093ca3e21d3404b39dd3797bc848519f20727434` | `357266a97b696b1c3569e91c2577e071d64ab75380cf0879c389443adfe6e3b2` |
| `verify/front_ctl.py` | `1f7ae841eb1994ee820780280cf3562111ef548bb9597858a19c3751a2761349` | `2d59f3f823c9e47ca3fc13cb976ffdc1310ae222a6088252d1870b24b85cea52` |
| `verify/deploy.py` | `89fd4e99df0ab58c969c796751212e3b1cb570581ad0971dd7e9d36acea4e1e6` | `641024ab3de2ac5be3bc8c58bc1481f87053d8104adbe9f811653c3eda3aa010` |
| `verify/deploy_front.py` | `ac038d1f4c43f75fc5fbfe086153c62861c901a0f243e2b22ccf832503565bc1` | `0fca7f2327f5f8ccc63b67cdadcf064849d78845e07ec149f1da47e29b45cc9c` |
| `tests/verify_tests.py` | `996bb52cefa2bde887d79ab8675cfd580018f59afaaf7a8967c854fd338ec7a0` | `e0af8a5fcec252708a323cf32c92b0e7b544bbb49d37291f008bb98a222cb7b0` |
| `verify/README.md` | `55e48299339eba2b75de0fcb36e9b7cb0877ea2818060f5f9a1be58faa254cb7` | `b43c05ed696c77c5abc6efb2929cfbc7fe9a4ab8b5d388630845fb83014f20df` |

`verify/checkpoints.py` is new. One file is new as a development record: `verify/dev_amend10_mutants.json`, the pass of
deliberate defects on this code.

Every other file in the repository at `f9ae97f` is unchanged, among them the gate host, the governor, the store, the gate's
tool, the front door, the MCP server and the first client.

## What each test is expected to show

**R1 to R24** are as declared before: the same functions, each expected true. Every record they build now carries a
checkpoint and has a ninth check, and they passed so in development (below).

**R25 is new** (19 checks). On one service, before a run, after a failing run, after a passing run and after a revision.
A defect that makes a step raise is taken as that step's answer, so that a check fails rather than the test stopping:

1. before any run the witness signs a checkpoint of the empty chain: no decisions, its head the provisioning record's hash,
   the budget open, the asker's nonce signed back; asked for the head after decision 0 it gives the same hash; both verify
   under the witness's key.
2. asking for a checkpoint adds no decision: five asks leave the chain as long as it was, and each gives its length and head.
3. a record carries the witness's checkpoint, which names the record's own last decision and head; the record verifies with a
   ninth check, the witness checkpoint; a record built without one still verifies, and its ninth check says it has none.
4. against a checkpoint obtained separately, whose chain ends where the record does, the record is CURRENT within the age
   allowed, with the nonce asked signed back; with no age allowed it is only CURRENT_AT the checkpoint's time; the checker's
   command, which allows an hour unless told, says CURRENT and exits 0; with no checkpoint given it says the currency was not
   checked, and exits 0 as before.
5. the command refuses to be misused (exit 2): an age or a nonce with no checkpoint, a checkpoint with the keys read from the
   record itself, an age that is not a number, a checkpoint file with no name.
6. after a later run the same record is out of date: SUPERSEDED, a true beginning of the chain, where the checkpoint names the
   record's head; SUPERSEDED_UNPROVEN where it does not; the command exits 1 though the record itself verifies.
7. an old checkpoint handed over again with the old record, after a later run, still reads CURRENT inside the age allowed,
   which is all that CURRENT says; asked with a nonce of the reader's own, it is not used.
8. a checkpoint older than the record says nothing of it (OLDER); one older than the age allowed is STALE and one within it
   CURRENT; one dated more than five minutes ahead of the reader's clock is not used, and one less than that ahead is; the
   command exits 1 for a stale, a forked, an unusable and an older checkpoint.
9. a checkpoint is not used (INVALID) when it signs back another nonce or none, when its number, head, time or state was
   edited or a field added, when its number is text or true, when it gives an earlier head with no number, when it is signed
   by another key, is for another budget, or is a receipt and not a checkpoint; nor is an age that is not a number, or a
   record with no as-of point.
10. a checkpoint the witness's key signed that gives another head for a decision the record holds shows the record is of
    another chain (FORKED): for the record's last decision, as the chain's head or as an earlier one, and for a decision
    inside the record, in a checkpoint older or newer than it.
11. the checkpoint inside a record cannot be changed, exchanged or dropped unseen: edited, checks 1 and 9 fail; edited and
    re-signed with the engineer's key, or exchanged for a true checkpoint of an earlier point, for a true one that names no
    head, or for one signed by another key, check 9 alone fails; taken out and re-signed, the record verifies and says it has
    none.
12. once the baseline is superseded, a checkpoint of its chain says the budget is no longer open, and the checker says so
    beside the record's currency.
13. a log of checkpoints kept apart from the service takes them in order, each answering for the last number kept, and refuses
    a rollback, a fork of the head, a fork of an earlier head, a longer chain that does not follow the last one kept, one that
    does not answer for the last number kept (naming none, or an earlier one), a checkpoint not signed by the witness, and one
    for another budget or nonce than asked; it keeps none of them, and puts the four that contradict it aside as evidence.
14. the log's audit is clean, and reports a fork written into it behind the keeper's back.
15. the witness answers 404 for a budget it does not hold and 400 for no budget, a nonce with a space or of 65 characters, a
    decision beyond the chain, a number that is not one and a budget name with a control character; none of it adds a
    decision.
16. the keeper's certificate reads a checkpoint (200) and can do nothing else: the witness refuses its write (403) and its
    other question (403); a certificate the witness does not know is refused the checkpoint (403); the fetcher gives nothing
    with no certificate, and will not ask over plain http.
17. the keeper's command fetches a checkpoint with a nonce of its own making, keeps it and writes it out; its next fetch asks
    the witness for the head at the last number kept; a line cut off in the log is reported by the audit and does not stop the
    next fetch, nor does a last line that lost its line end; the log then audits clean with four checkpoints.
18. a keeper whose log holds a longer chain than the witness now has is told of a rollback: the command exits 1, and the
    witness's signed checkpoint of the shorter chain is put aside as the evidence.
19. the superseded baseline's record, built after the revision and checked against the keeper's first checkpoint with its
    nonce, is CURRENT; the command says the budget is no longer open, and exits 0; the engineer's console, given the witness's
    address, writes a record that carries a checkpoint and verifies.

Expected for the gate: 25 of 25 tests, 169 of 169 checks: the 150 of Amendment 9 and the 19 of R25.

**F1 to F35** are as declared before, each expected true. The front door's deployment builds its records with a checkpoint,
and they passed so in development (below).

Expected for the front door: 35 of 35 tests, 189 of 189 checks, as for Amendment 9.

## What was done before this declaration

All of this was on the branch, before this declaration, on 19 November.

- **The first form**, the witness's checkpoint, check 9, the checker's currency and the keeper's log (`1f83df5`), with R25 at
  13 checks (`b5135ef`). Its full runs, 00:35:49 to 00:41:46: the gate's suite, 25 of 25 tests and 163 of 163 checks; the front
  door's, 35 of 35 tests and 189 of 189 checks. The witness service's own tests (`tests/w1_authority.py`, `w2_receipts.py`,
  `w3_service_lockstep.py`, `w4_service_crash.py`) each exited 0.
- **An independent review** of `f9ae97f` to `b5135ef`, read only, by a separate agent given the diff and asked to find what is
  wrong. It ran its own snippets against copies of the files. It reported nine findings of medium weight or more, and these were
  done with them:
  1. *The keeper's certificate could write to the witness* (POST `/accept`), because the witness's allow list is for the whole
     service. Fixed: `--tls-allow-read`.
  2. *A replayed checkpoint read CURRENT by default*, with no age or nonce given, and R25 asserted it. Fixed: CURRENT needs an
     age; the library says CURRENT_AT without one; the command allows an hour unless told. A replay within the age allowed
     still reads CURRENT, and is stated below.
  3. *A checkpoint dated in the future never went stale*, and an age that was not a number turned the check off. Fixed: more
     than five minutes ahead is INVALID, and so is an age that is not a number.
  4. *`--max-age` and `--nonce` were ignored without `--checkpoint`*, and so was an empty file name. Fixed: exit status 2.
  5. *With no keys given, currency was judged with the witness key read from the record itself.* Fixed: refused.
  6. *The keeper missed a rewritten chain*: two checkpoints in its log were never tied to each other. Fixed: it asks for the
     head at the last number kept.
  7. *A contradicting checkpoint was thrown away*, with the evidence of what the witness said. Fixed: `LOG.refused.jsonl`.
  8. *A torn last line stopped the keeper for good*, there was no lock, and a key rotation or two keepers could stop it. Fixed:
     the lock, the repair of a torn line, and more than one key given. A checkpoint that arrives out of order is still refused
     as a rollback.
  9. *`at=K` read the whole chain.* Fixed: one hash is read.

  Of its findings of low weight, these were fixed:
  - currency now compares every head a checkpoint states with the record's own chain (FORKED);
  - a record whose as-of point is not a number is INVALID, not an error;
  - a checkpoint must have exactly the witness's fields;
  - the keeper checks the budget and the nonce it asked;
  - the fetcher refuses plain http and caps the answer;
  - the consoles check the witness's answer before signing;
  - the witness refuses a budget name with a control character;
  - the keeper makes its own nonce;
  - the console's usage no longer lists `record` twice.

  It also named checks of R25 that would pass while the behaviour was wrong, and what R25 did not test. R25 was given checks for
  each, and grew to 18.
- **The second form** (`01d5b11`). Its run of the gate's suite, 00:46:32 to 00:49:03: 25 of 25 tests and 168 of 168 checks. The
  front door's suite was stopped after F7, at 00:49:25, when the second review reported, since the code was to change.
- **A second independent review**, of the first review's fixes alone (`b5135ef` to `01d5b11`), by another agent. It reported four
  findings of medium weight or more, all in the keeper and the witness's allow logic, and none in the checker:
  1. *The keeper never checked that the answer carried the `at` it asked for*, so a witness that rewrote its chain could answer
     with no `at`, or with `at` equal to its own head, and be kept (high). Fixed: `keep` requires the checkpoint to name the last
     number kept.
  2. *A log whose last line lost only its line end was run together with the next line*, and the keeper was stuck. Fixed.
  3. *A rollback that the witness admitted, by answering that the log's last number was beyond its chain, kept no evidence.*
     Fixed: the keeper asks again and puts the signed answer aside.
  4. *A name given only to `--tls-allow-read` could POST `/accept` when no `--tls-allow` list was given.* Fixed: such a name is
     admitted to `/checkpoint` alone in every configuration, and the startup line prints the read list.

  It said that R25's count of rows (the "adds no decision" check) reads the local store, not the witness's chain. In this
  demonstration they are one database, read under different roles, and the test now says so. It also said that no check made the
  keeper meet an answer without the `at` asked, or the "beyond the chain" path. R25 was given both, and has 19 checks.
- **The third form** (`d249baf`). Its full runs, 00:51:04 to 00:56:58: the gate's suite, 25 of 25 tests and 169 of 169 checks;
  the front door's, 35 of 35 tests and 189 of 189 checks. The witness service's own four tests each exited 0.
- **Its pass of deliberate defects**, 00:57:54 to 01:02:56: 50 defects and the control, each run against R25. The control passed.
  44 were caught by a check that failed. Six stopped R25 with an error before its checks could be read: C1, C22, C31, C32, C44
  and C48. Their errors were in R25's own steps:
  - for C1, a log folder the keeper never made;
  - for C31, a dropped connection;
  - for C32, the checker raising;
  - for C22, a record with no checkpoint;
  - for C44, a nonce of none;
  - for C48, a refusal that did not happen.

  R25 was changed so that each such step gives an answer and a check fails (`3a7c376`). The six were run again with the control,
  01:04 to 01:10: the control passed and all six were caught.
- **The fourth form** (`3a7c376`, with `verify/README.md` as committed here), which is the code this declaration carries.
  Its full runs, 01:11:09 to 01:16:49: the gate's suite, 25 of 25 tests and 169 of 169 checks; the front door's,
  35 of 35 tests and 189 of 189 checks. The witness service's own four tests each exited 0, by 01:17:45. These are the counts
  expected below.
- **Its pass of deliberate defects**, 01:17:46 to 01:22:46: 50 defects and the control, each run against R25. The control
  passed unchanged. All 50 were caught by a check that failed, and none stopped R25 with an error. They are kept in
  `verify/dev_amend10_mutants.json`, which names, for each, the checks that caught it. The defects cover:
  - the witness's endpoint (C1 to C6, C29 to C31);
  - the checkpoint's form and signature (C7 to C10, C32, C33);
  - currency (C11 to C18, C34 to C41);
  - the checkpoint inside a record (C19 to C23);
  - the keeper (C24 to C28, C42 to C50).
- **The third and fourth forms were not themselves read by a reviewer.** The fixes of the first review were read by the second;
  those of the second were read only by their author.

## What stays open

- **CURRENT is not "current now" unless the reader asked.** A checkpoint is a signed statement of what the witness read at its
  time. Handed over with a record by someone else, an old one reads CURRENT while it is within the age allowed (an hour by
  default), even if the chain has gone on since. Only a checkpoint that the reader fetched with a nonce of their own shows that
  it was made after they asked.
- **The witness is still one party.** A witness that keeps one consistent false chain, and tells everyone the same thing, is not
  caught by the checker or by the keeper. The keeper catches a witness that says two different things to it, at or before a
  number it holds. It does not see what the witness told others between two of its own askings.
- **The keeper is on the same machine.** In the demonstration, the keeper's log, the witness, the store and the engineer's key
  are on one machine under one account. Someone who can write there can rewrite the log, as R25 does on purpose. The log is as
  independent as the machine and account it is kept on.
- **The time in a checkpoint is the witness's clock**, not a third party's. Its age is judged by the reader's clock, with five
  minutes allowed for the difference.
- **A checkpoint that arrives out of order** (a lower number after a higher, from the same chain) is refused by the keeper as a
  rollback. The keeper does not check that the witness's clock goes forward, or that a closed budget does not open again. Its
  audit takes time that grows with the square of the log's length.
- **Every record the test deployments build needs the witness to be up.** A record built with `--witness-url` while the witness
  is down is not written; one built without it carries no checkpoint.
- **The record is still evidence of process, not of correctness**, and **a notice is still a file the service writes about
  itself** (G5, an independent notification path, is not done).

## What is not tested

- A checkpoint handed over by a second party and replayed later. R25 replays one in its own process; it does not stage two
  parties.
- A witness that lies consistently. R25 makes forks and rollbacks with the witness's key in the test's process; the witness
  service itself is never made to lie. The keeper's ROLLBACK path through the command is made by a log that holds a longer chain
  than the witness has, not by a witness that rolls back.
- Two keepers appending to one log at the same moment (the lock), a key rotation, and a checkpoint that arrives out of order.
- The fetcher's refusal of an answer larger than 64 KiB.
- The console `front_ctl.py record --witness-url`. R25 runs `verify_ctl.py record --witness-url`.
- A record built while the witness is down, and a witness that answers slowly.
- A checkpoint dated ahead by between nought and five minutes through the command; R25 tests both sides of the limit in the
  library.
- The cost of `at=K` and of the keeper's audit on a long chain.
- That a reader who sees CURRENT understands what it does and does not say.

## Commands and results

The official runs are these, each once, from the tree at the commit that carries this declaration, with the services on
127.0.0.1 and PostgreSQL 16:

    cd tests && python3 -B verify_tests.py
    cd tests && python3 -B verify_front_tests.py

Each output file is copied to `verify/results_verify_tests_amended10_2026-11-19.json` and
`verify/results_front_tests_amended10_2026-11-19.json`. The outputs folder is not committed.

Expected: for the gate, 25 of 25 tests and 169 of 169 checks; for the front door, 35 of 35 tests and 189 of 189 checks.
A check that comes out other than expected is reported as it came out, in the amendment that follows the runs, and is not run
again under this declaration.
