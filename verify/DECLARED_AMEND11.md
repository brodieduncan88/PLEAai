# Amendment 11: declaration before the official test runs

19 November 2026. Private working material.

This file is committed before the official runs of `tests/verify_tests.py` and `tests/verify_front_tests.py` on the branch
`verification-amendment-11`. It fixes the changed code, states what each test is expected to show, and records what was done
in development. Each official run is made once after this commit and its first result is kept, pass or fail. A later
correction would be a separate, dated amendment. Times are UTC.

## Why declared files are changed

A notice to the responsible engineer was a file the service wrote about itself, into an inbox it controls. Whoever can write
that inbox can remove or change a notice, and nothing showed that one had reached the engineer. This is D12 in the defect
register, and release gate G5, "independent notification path with delivery evidence", of 19 November. Amendments 7 to 9
made the service write a notice in more cases, and Amendment 9 renamed what it checks of the inbox, but the notice stayed the
service's own word. On 19 November the owner asked for G5 to be built, by the same process as Amendments 9 and 10.

## What is changed

**A courier, which reads only the witness.** `verify/courier.py` is a separate party, with its own Ed25519 key, its own
client certificate, its own folder, and no credential of the service's. It does not read the service's store, inbox, ledger
or files. It reads the witness, and believes it only as far as it can check:

- it asks for a checkpoint (Amendment 10) with a nonce of its own, naming the last decision it read before;
- it reads the decisions since, page by page, and recomputes each hash: they must follow on from that decision's head and
  end at the checkpoint's head;
- for each run, it reads the gate's reports and the stored result: a report counts only if a gate key given signed it for
  this budget, run and nonce, and a result only if it hashes to the digest the gate signed.

From these it says what each run's outcome is, by the same rule the record's checker uses (`check_record.run_outcome`). A
run calls for a notice when that outcome is:

- FAIL or UNKNOWN;
- INTERRUPTED (the gate signed that it does not know the outcome);
- INDETERMINATE (the control plane re-registered the budget);
- INVALID or REFUNDED, which must never happen;
- UNVERIFIED: the gate signed an effect, and no stored result hashes to its digest;
- NO_OUTCOME: the run's intent was accepted, or it was admitted and crossed, and it has no outcome.

The last two are sent only after the courier has seen them so for `stall_after` seconds (900 unless set), because the
witness records an outcome a moment before the result is stored. A run that met the declared check calls for none. Each
notice, for one run and one outcome, is made once and signed with the courier's key. It names the decision it was read at
and that decision's hash, and gives the reason, the numbers and the detail of a verdict in words a person reads.

**The witness gives the courier its chain.** Two readings are added to the witness service:

- `GET /chain?root=R&after=K` gives the decisions after K, at most 200, and fewer once the answer passes 4 MiB;
- `GET /run?root=R&aid=A` gives one run's gate reports and its stored result.

Neither is signed, neither changes anything, and each is given only to a client certificate admitted to it. The new option
`--tls-allow-chain NAME` admits a name to the checkpoint and the two readings, and to nothing that writes. `--tls-allow-read`
still admits a name to the checkpoint alone, as in Amendment 10. The demonstration gives `courier` the first and `keeper`
the second.

**The engineer's mailbox signs a receipt.** `verify/mailbox_service.py` is the engineer's: its own key, its own folder, and
only HTTPS from a client certificate it admits (the courier's). For each notice signed by a courier key it was given, it
writes the notice whole and synced, with a readable copy, and answers with a receipt signed by its own key that names the
notice by its digest. A notice delivered again gets the receipt first given. The courier counts a notice as delivered only
when the receipt is signed by a mailbox key it was given and names that notice. It keeps each notice and receipt in its log,
and keeps a notice it could not deliver until the next pass. A receipt says the mailbox holds the notice, not that the
engineer read it; the engineer's signed acknowledgement of a run does that, as before.

**The courier says when it has stopped.** It refuses a budget, and stops reading it until `courier.py resume`, when:

- a checkpoint is not the witness's, does not sign back its nonce, or names another decision than asked;
- the witness gives another head for the last decision the courier read (a fork);
- the witness says that decision is beyond its chain (a rollback);
- decisions are not readable, do not follow on, or do not end at the checkpoint's head.

It writes what it was told to `refused.jsonl` and sends the mailbox a signed notice that it has stopped (COURIER_STOPPED).
If it cannot read the witness for `stall_after` seconds, it sends one notice that it is blocked (COURIER_BLOCKED). Neither is
a notice of a run, and neither goes into a record.

**A record can carry the notices, and the checker reads them.** The engineer's console (`verify_ctl.py record --deliveries
LOG --courier-key HEX --mailbox-key HEX`) puts into the record the notices of runs of this budget, with their receipts, that
are signed as they must be and name a decision of the record's chain, once each, with the two keys. The checker has a tenth
check. Each notice must be signed by the courier's key, name a decision of this record's chain with its hash, and say what
this record's chain, gate reports and verdict say of that run at that decision: its outcome, the digest of its verdict, the
reason code and detail it quotes, and the first line of its words. Each receipt must be signed by the mailbox's key and name
that notice.

The checker then prints which runs that call for a notice have one delivered, and which have none ("NO DELIVERY EVIDENCE").
`--require-delivery` makes its exit status 1 unless every such run has one. Checked with the witness, gate and engineer keys
given and no courier or mailbox key, a record's notices are not checked: the record is judged without them, and the checker
says so. A record without notices verifies as before, and its tenth check says it has none. Records made before this
amendment verify unchanged.

The service's own notices, in its inbox, are unchanged. The courier is a second path beside them, not a replacement.

## The changed files

Base: `verification-amendment-10` at `7026ded`. Ten files change, two of them new.
The hashes are of the files as they stand at this commit.

| file | sha256 at 7026ded | sha256 now |
| --- | --- | --- |
| `plea_gateway/witness_service.py` | `d5766582555fa7d808d3029e8b74e885c39a76b70006a3e06c92349f69d81bdc` | `62959c633526401d494644934d85197af785cb2e8c9a4132e552c446b67f2582` |
| `plea_gateway/store.py` | `8a5f7c36bf5cb0315d9134f230c818ecd9c3ac6b51143c1dec279898cce1a152` | `db8795d966030790c9e2d44018b8c39e0ee9d5fc9507c672de5081bd9e60ff09` |
| `verify/courier.py` | new | `7285c14ccec6f9265d9df50eb270fa44f4b2ae4b28f2c9e609fa8293f7a0507a` |
| `verify/mailbox_service.py` | new | `7cdfe159f88741ba7fa8c53882e72bc7d131f23830e8cdf4fac6d48df06f6318` |
| `verify/check_record.py` | `6a972088927a6e242e7bac112e47472f6d1ff85bb16aaf23db228adf74b57b7e` | `5e7eb84a451f6b17a1f1ed463ff051d9e529f0da67401f9eab2f706b6bb9b1b7` |
| `verify/verify_record.py` | `160fe58529c755e9c5d13f980ac50eaaa22c57ace320432653d9210946cd3811` | `1036f9dce7826ce59df95259192c18e8e19ad828a5e2dde90455945f99773227` |
| `verify/verify_ctl.py` | `357266a97b696b1c3569e91c2577e071d64ab75380cf0879c389443adfe6e3b2` | `8ec49b53ef51b0218afca12848331938ace74e677848a6be2360434403ad06c5` |
| `verify/deploy.py` | `641024ab3de2ac5be3bc8c58bc1481f87053d8104adbe9f811653c3eda3aa010` | `1f2de10c92bac233c58789b664ba8081c9bb68b4d0ef9b4f8b0f2b0edb619f23` |
| `tests/verify_tests.py` | `e0af8a5fcec252708a323cf32c92b0e7b544bbb49d37291f008bb98a222cb7b0` | `829334f4c056f6893edd2254cefa6bb2f00a2db110a36d708f1c574bda515334` |
| `verify/README.md` | `b43c05ed696c77c5abc6efb2929cfbc7fe9a4ab8b5d388630845fb83014f20df` | `b3b434e8dddc541fa2010be9ac1e322980b04ad1a7886b9cce28b154183af0fb` |

`verify/courier.py` and `verify/mailbox_service.py` are new. One file is new as a development record:
`verify/dev_amend11_mutants.json`, the pass of deliberate defects on this code.

Every other file in the repository at `7026ded` is unchanged, among them the gate host, the governor, the gate's tool, the
front door, the MCP server and the first client.

## What each test is expected to show

**R1 to R24** are as declared before: the same functions, each expected true. Every record they build has a tenth check,
which says it carries no notices.

**R25 is restated in one line.** It read the record's ninth check as the last of the record's checks; it now reads the check
numbered 9. Its 19 checks are otherwise as declared by Amendment 10.

**R26 is new** (27 checks). On one service, with a run cut off, a failing run, a passing run and a failing run while
the mailbox is down; then the record, and a re-registration. A step that raises is taken as that step's answer, so that a
check fails rather than the test stopping:

1. the witness gives the courier's certificate its decisions, which follow on from the head a checkpoint names for decision 0
   and hash one to the next, and a run's signed gate reports and stored result; reading adds no decision.
2. the witness answers 404 for a budget it does not hold and 400 for no budget, a number that is not one, a page of 0 or 201
   decisions, a budget name with a control character, no run named and a run named with a control character.
3. the courier's certificate reads and can do nothing else: the witness refuses its write (403) and its other question (403);
   a certificate the witness does not know is refused the chain (403), and so is the keeper, which reads checkpoints only.
4. a run cut off when the gate host dies gets no notice before the courier has seen it with no outcome for the time allowed,
   then a notice that it has none; once the gate signs that it does not know the outcome, a notice that it was interrupted;
   each is delivered.
5. a failing run whose own notice was taken out of the service's inbox still gets the courier's notice of the failure,
   delivered; a passing run gets none; a second pass sends nothing more.
6. the mailbox holds each notice with its receipt, which verifies under the mailbox's key and names that notice, and a
   readable copy that opens with what happened; the failure's copy gives the numbers; the courier's log holds the same
   notices.
7. the courier's configuration names neither the service's home nor its database; it holds the courier's certificate and the
   witness's address.
8. with the mailbox down, the notice of a failure is made and waits, and the pass exits 1; with the mailbox back, the next
   pass delivers it, makes no other, and exits 0.
9. the mailbox refuses a notice signed by another key (403), one that is not a notice (400), a body that is not JSON (400) and
   a client that is not the courier (403); a notice delivered again gets the receipt first given and is kept once.
10. a courier given another key for the mailbox takes no answer of the mailbox as a receipt: nothing is delivered, the notices
    wait, and the pass exits 1.
11. the courier refuses decisions that were changed, skip one, or do not end at the head the checkpoint names, and takes them
    when they are whole.
12. a courier whose last head the witness contradicts refuses the budget (a fork), keeps the witness's signed checkpoint as
    the evidence, exits 1, and stays stopped at the next pass.
13. a courier told that the last decision it read is beyond the chain refuses the budget (a rollback), and keeps the witness's
    signed checkpoint of the shorter chain as the evidence.
14. a record built with the courier's log verifies with a tenth check, the notices delivered; each run that calls for a notice
    (two failures and the interruption) has one delivered, and the run once without an outcome is named; the checker's command
    says so and exits 0 when delivery is required.
15. a record that lacks the notice of one failure verifies, and says that run has no delivery evidence; the command exits 1
    when delivery is required; a record that lacks the notice of the interruption says so, though it holds the earlier notice
    that the run had no outcome.
16. the notices in a record cannot be changed or made up unseen: a notice edited, one signed by another courier key, one with
    a field added, one for another budget, a receipt signed by another key or for another notice, a notice naming a decision
    not in the record's chain, and one that says what the record does not (in its outcome or in its words), each fail check 10
    alone.
17. a run the gate signed an effect for is UNVERIFIED with no result, or with a result that does not hash to the digest the
    gate signed, and has its verdict with the true one; a notice that vouches for no result, made at that decision, is taken.
18. the courier takes a checkpoint signed by the witness that signs back its own nonce and names the decision it asked about,
    and refuses an old one handed back, one naming another decision, and one signed by another key.
19. a record carrying notices, checked with the three keys alone, verifies and says its notices were not checked; the command
    exits 1 when delivery is required, and 0 with the courier's and the mailbox's keys given.
20. a courier reading the chain five decisions at a time, from the start, makes the notices of the interruption and the two
    failures, and delivers them.
21. a courier given decisions it cannot read (one with no number, one numbered in text, one with no operation), none where the
    checkpoint says there are some, or a run's reports that are not a list, refuses the budget, does not stop with an error,
    and delivers to the mailbox a signed notice that it has stopped.
22. a courier that cannot reach the witness exits 1; it sends nothing until it has been blocked for the time allowed, then one
    signed notice that it is blocked, not one at each pass.
23. a client that connects to the mailbox and sends nothing does not hold up another; a body over 64 KiB is refused (400); a
    notice whose signature is spelt in capitals is refused (403) and not kept.
24. when the control plane re-registers the budget, the run cut off before, the oddly named run and a run cut off now are made
    INDETERMINATE; a courier resumed after its refusal reads the budget again and sends a notice of each, and a record built
    after shows all three delivered.
25. an attempt the gateway names oddly ("!x"), started and never admitted, gets a notice that it has no outcome, beside the
    notices of the other runs; once admitted and crossed, the witness answers for it by that name, and the courier sends
    nothing more of it.
26. when the witness will not answer for one run, the courier still reads the others and sends their notices, says it could
    not read that one (with no time allowed, a notice that it is blocked), and sends its notice at the next pass, when the
    witness answers.
27. a record without notices verifies and says it has none; the command says notices were not checked and exits 1 when
    delivery is required; the engineer's console, given the courier's log and the two keys, writes a record that carries the
    notices and verifies, and refuses without the keys.

Expected for the gate: 26 of 26 tests, 196 of 196 checks: the 169 of Amendment 10 and the 27 of R26.

**F1 to F35** are as declared before, each expected true. The front door's deployment also starts the engineer's mailbox; no
check reads it.

Expected for the front door: 35 of 35 tests, 189 of 189 checks, as for Amendment 10.

## What was done before this declaration

All of this was on the branch, before this declaration, on 19 November.

- **A first trial**, by hand, of the whole path: a run cut off, then interrupted; a failing run; a passing run; the courier's
  passes; the mailbox's notices; a record with the notices; the mailbox down and back. It showed that the governor records
  an outcome with the witness a moment before it stores the result (`plea_gateway/governor.py`, `_settle`). So a courier that
  read in that moment would have called a sound run UNVERIFIED. The courier now waits before it says so, as it does before
  NO_OUTCOME, and an UNVERIFIED notice vouches for no result.
- **The first form** (`9901002`), with R26 at 18 checks. Its full runs, 02:20:55 to 02:27:28: the gate's suite, 26 of 26
  tests and 187 of 187 checks; the front door's, 35 of 35 tests and 189 of 189 checks. The witness service's own four tests
  each exited 0. While R26 was written, some of its own steps were wrong at first and were corrected, among them a run's id
  read from the wrong level of a delivery, and a wrong mailbox key put at the wrong level of the courier's configuration.
- **An independent review** of `7026ded` to `9901002`, read only, by a separate agent that ran its own snippets against
  copies. It reported two findings of high weight and five of medium weight. What was done with each:
  1. *A run that the control plane made INDETERMINATE (a re-registration) never got a notice*, and a record did not count it
     as calling for one. Fixed: INDETERMINATE is noticed and is due; a run left INTENT_PENDING gets NO_OUTCOME.
  2. *The courier stopped for good once a budget held about 330 runs*: a page of 200 decisions, each carrying the whole
     state, passed its 8 MiB limit, and it held the whole chain in memory. Fixed: the witness cuts a page at 4 MiB, the
     courier checks page by page and keeps only the last decision, and its limit is 32 MiB.
  3. *One idle connection held up the mailbox*: its handshake ran in the accept loop. Fixed: in each connection's thread,
     with 15 seconds' patience.
  4. *Answers the courier could not read crashed or hung it.* Fixed: they are refused (and see the third review).
  5. *A courier that stopped told no one, and the docstring overstated its independence.* Fixed: COURIER_STOPPED and
     COURIER_BLOCKED notices to the mailbox, and the docstring says what the courier still trusts: the witness, its shared
     database, one certificate authority, and whoever sets the witness's allow list.
  6. *A name allowed to read checkpoints could now read every decision and result.* Fixed: `--tls-allow-chain` is a separate
     list; `--tls-allow-read` gives the checkpoint alone, as in Amendment 10.
  7. *A record with notices, checked with the three usual keys, became NOT VERIFIED.* Fixed: its notices are not checked, and
     the record is judged without them.

  Of its findings of low weight, these were fixed: a signature in capitals let one notice be kept twice (now lower case only);
  check 10 did not read a notice's words (it now compares the reason code, the detail and, after the second review, the whole
  text); the courier's state was not synced and could not be resumed (`resume` added); the builder refused a whole record for
  one bad notice, kept duplicates and split a key given as text; `/run` and `/chain` judged an unknown budget differently.
  It also named what R26 did not test, and checks were added for most of it (below). R26 grew to 25 checks.
- **The second form** (`cb24593`). Its full runs, 02:36:37 to 02:42:57: the gate's suite, 26 of 26 tests and 194 of 194
  checks; the front door's, 35 of 35 tests and 189 of 189 checks; the witness's four tests each exited 0. Its pass of
  deliberate defects was begun and stopped after 16 defects, all caught, with the control passing, when the second review
  reported, since the code was to change.
- **A second independent review**, of the first review's fixes alone (`9901002` to `cb24593`). It reported one finding of
  high weight and four of medium weight:
  1. *One run the witness would not answer for hid every run listed after it*: `/run` refused a run named outside a narrow
     pattern, which the contract allows, and the courier stopped at the first run it could not read. Fixed: `/run` takes any
     name the chain can hold; the courier asks it only for runs whose reports matter, and a run it cannot read no longer
     stops the others.
  2. *Other unreadable answers still escaped the courier's handling.* Fixed: a decision must have every field, a run's
     reports must be a list, and an answer that cannot be read is refused, with its alarm; waiting notices are still sent.
  3. *A run could be marked final before its notice was made.* Fixed.
  4. *`resume` kept what it should have forgotten.* Fixed.
  5. *A slow witness or mailbox could hang a pass.* Fixed: each request has 60 seconds in all.

  Of its findings of low weight, these were fixed: check 10 took a notice of decision 0; a notice's words were checked only
  in their first line (now made again by the checker and compared whole); the words for INDETERMINATE and NO_OUTCOME were
  not right in every case; a wait could be carried over from an earlier spell; the builder now keeps only the notices its
  checker would take. R26 grew to 26 checks.
- **The third form** (`2bcffde`). Its gate's suite, 02:50:58 to 02:53:44: 26 of 26 tests and 195 of 195 checks. The front
  door's suite was stopped when the third review reported.
- **A third independent review**, of the second review's fixes alone (`cb24593` to `2bcffde`), asked for findings of medium
  weight or more. It reported four, and nothing of high weight:
  1. *A run whose reading failed every other pass lost its wait each time, so its notice never came.* Fixed: a run not read
     keeps its wait.
  2. *A transport fault (a cut answer, a bad status line) was taken as the witness lying, and stopped the courier for good.*
     Fixed: it is unreachable, and retried; only answers that cannot be read are refused.
  3. *With the witness hung, a pass asked after every run in turn.* Fixed: the pass asks no more once the witness stops
     answering, and what is waiting is sent before the witness is asked.
  4. *R26 never made the witness answer for the oddly named run, and nothing showed one refused run hiding no other.* Fixed:
     two checks (R26 has 27).
- **The fourth form** (`b2cc3fb`), which is the code this declaration carries. Its full runs, 02:58:58 to 03:05:18: the gate's
  suite, 26 of 26 tests and 196 of 196 checks; the front door's, 35 of 35 tests and 189 of 189 checks. The witness service's
  own four tests each exited 0, by 03:06:13.
- **Its pass of deliberate defects**, 03:06:13 to 03:24:02: 55 defects and the control, each run against R26. The control
  passed unchanged. 51 were caught by a check that failed, and none stopped R26 with an error. Four were not caught. Three
  showed checks that passed because another rule caught the same case first: G17 (a notice need not say the record's outcome,
  caught by the words instead), G23 (the courier does not compare its nonce, caught by the decision named instead) and G47 (a
  blocked courier sends its notice at every pass, where the second notice was the same as the first and kept once). The
  fourth, G51 (the builder keeps the courier's notices about itself), cannot be seen: the check the builder calls leaves those
  notices out too. G51 was taken off the list.
- **R26 was then changed twice, and nothing else.** A check's name still said that a record checked without the courier's and
  the mailbox's keys fails check 10, which stopped being so after the first review; it was corrected (`6202403`). Three checks
  were made to test one thing each, so that the three defects they had missed would fail them (`e82f704`). Its gate's suite,
  03:25:26 to 03:28:17: 26 of 26 tests and 196 of 196 checks. The control and G17, G23 and G47 were run again on it, 03:28 to
  03:29: the control passed, and each of the three was caught. So, of the 54 defects kept, all are caught by a check that
  fails.
- The defects are kept in `verify/dev_amend11_mutants.json`, which names, for each, the checks that caught it. They cover:
  - the witness's readings (G1 to G7, G2b);
  - what a run's outcome is (G8 to G11);
  - notices and receipts (G12 to G15, G49);
  - check 10 and what the checker says (G16 to G22, G45, G50);
  - the courier (G23 to G36, G44, G46, G47, G52 to G54);
  - the mailbox (G37 to G41, G48);
  - the record (G42, G43).
- **The fourth form was not itself read by a reviewer.** The fixes of each review were read by the next; those of the third
  were read only by their author.

## What stays open

- **A receipt is not reading.** It says the engineer's mailbox holds the notice. It does not say the engineer read it; the
  engineer's signed acknowledgement of a run does, as before. Nothing makes the engineer read the mailbox.
- **The courier believes the witness.** It sees what the witness records. A run that never reached the witness is not seen,
  and a witness that tells it one consistent false chain is believed. It catches a witness that contradicts what it read
  before (a fork or a rollback), and says so to the mailbox.
- **The courier's independence has limits, which the demonstration does not separate.**
  - The witness reads the same database as the service. The chain is written only through the witness's role, but a
    stored result is the service's, believed only when it hashes to the digest the gate signed.
  - One certificate authority issues every certificate, and whoever runs the witness sets its allow list. They can cut the
    courier off; it then sends one notice that it is blocked, if the mailbox is reachable.
  - The courier, the mailbox, the witness and the service run under one account on one machine. Whoever can write there can
    change the courier's state or the mailbox's folder.
- **A courier that is not running tells no one.** Nothing notices its silence: there is no heartbeat.
- **"Once" holds as long as the courier's state does.** If its state file is lost, a notice already sent for a run and an
  outcome is made again, with a new time, and delivered as a second notice.
- **A record does not call for a notice of a run that has no outcome yet.** A run left INTENT_PENDING or CONSUMED gets a
  NO_OUTCOME notice from the courier after 15 minutes, but the record's checker counts only runs with a final outcome (FAIL,
  UNKNOWN, INTERRUPTED, INDETERMINATE, INVALID, REFUNDED) as calling for one, so `--require-delivery` passes without it.
- **What a notice of INTERRUPTED says may later change.** The gate may still learn the verdict; the courier then sends a
  second notice, and the first stays as it was.
- **The courier's notices about itself are not in a record.** A record does not show that its courier stopped or was
  blocked.
- **Check 10 trusts the courier's key for what the record cannot show.** An UNVERIFIED notice says no matching result was
  found for a while; a record cannot show that absence. A NO_OUTCOME notice says the courier waited; a record cannot show how
  long.
- **The service's own notices are unchanged**, with every limit stated for them before (D12 remains for that path).

## What is not tested

- A witness that itself forks or rolls back. R26 makes the courier meet a fork and a rollback by changing what the courier
  read before, in its own state; the witness service is never made to lie.
- A real UNVERIFIED notice made in the moment between the witness recording an outcome and the result being stored. R26
  tests the rule and a notice made by hand; every courier pass in R26 waits nought seconds.
- The witness's 4 MiB cut of a page of decisions. R26 reads five decisions at a time, but its chain is short.
- A courier crash between a notice reaching the mailbox and the courier's log, or between making a notice and saving its
  state.
- A party that answers slowly, against the courier's 60-second deadline for a whole request.
- `resume` after a chain that really changed; R26 resumes after a refusal made by changing the courier's own state.
- The record's builder leaving out a delivery its checker would refuse, a duplicate, or a key given as one string.
- Two couriers delivering to one mailbox, and two passes of one courier at once (its lock).
- A key rotation of the courier or the mailbox.
- The courier run continuously (`--every`), and its configuration's defaults (15 minutes, 200 decisions a page).
- That a person who reads a notice, or a record's NOTICES line, understands what it does and does not say.

## Commands and results

The official runs are these, each once, from the tree at the commit that carries this declaration, with the services on
127.0.0.1 and PostgreSQL 16:

    cd tests && python3 -B verify_tests.py
    cd tests && python3 -B verify_front_tests.py

Each output file is copied to `verify/results_verify_tests_amended11_2026-11-19.json` and
`verify/results_front_tests_amended11_2026-11-19.json`. The outputs folder is not committed.

Expected: for the gate, 26 of 26 tests and 196 of 196 checks; for the front door, 35 of 35 tests and 189 of 189 checks.
A check that comes out other than expected is reported as it came out, in the amendment that follows the runs, and is not run
again under this declaration.
