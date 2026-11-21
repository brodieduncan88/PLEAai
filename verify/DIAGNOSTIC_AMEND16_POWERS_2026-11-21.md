# Diagnostic: the service's database role, when a verdict is committed, two signed digests, and readings under honest load

21 November 2026. Private working material. Internal work under the owner's direction. It is not an independent
validation, it is not a declaration, and no official run was made. No code of the service, the gateway, the witness, the
mailbox or the courier is changed on this branch: it adds harnesses, their results and this note. The code under test is
`e25a297`, the eighth form of the repair on `verification-amendment-16`, which is INCOMPLETE: it failed its eighth
internal review and is not declared.

## What was asked

On 21 November, before approving the draft threat-model addendum, the owner asked for two things to be checked on the
deployment, with no change to code:

1. The actual database role grants, what the service can and cannot change, and by test: when a verdict is committed,
   and whether a run can carry two gate-signed digests.
2. The measurements the draft named, to settle whether a budget can be read whole under honest load without touching
   the frozen gateway.

## What was run

Everything ran from a copy of the tree made by `git archive e25a297`, against real deployments started by
`verify/deploy.py` (the witness service, the gate host and the mailbox under mutual TLS, PostgreSQL 16.15 behind them),
each on a database created fresh and given its schema by `Store.init_schema()` and `init_authority()`: `plea18` for the
checks of the role and of commitment, `plea20` and `plea21` for the measurements (`plea19` held a small trial). Runs were
made through the assistant's client, each a real check in its sandbox. The courier ran as its own process.

The machine had restarted at 09:41 UTC; PostgreSQL was started again and `fs.file-max` raised again, as on 20 November.

| Harness (in `tests/diag_amend16_powers/`) | What it does | When (UTC) | Results (in `results_2026-11-21/`) |
|---|---|---|---|
| `roles.sql` | reads roles, privileges, functions and settings from the catalogue | 09:50 | `roles.txt` |
| `commit_check.py` | tries each change as the service's role; replaces verdicts; holds connections; stops the witness | 09:53:46 to 09:54:05 | `commit_check.txt`, `.json`, `notice_words.txt` |
| `measure.py` | 1296 honest runs over three budgets; the readings; the courier from nothing | 09:56:16 to 10:25:59 | `measure.txt`, `.json` |
| `measure2.py chain` | the whole chain of the largest budget, page by page | 10:27 | `measure2_chain.txt`, `.json` |
| `measure2.py live` | the courier pass after pass while honest runs are made | 10:28:20 to 10:34:35 | `measure2_live.txt`, `.json` |

`commit_check.py` was run four times. The first stopped on a slip of the harness (an identical design is replayed by the
client, so no new run was made); the second lacked steps 3c and 6; in the third, step 3c used a design outside the
baseline. All three outputs are kept beside the fourth. Steps 0 to 3b gave the same results in every run that reached
them.

## 1. The roles, as the database holds them

From the catalogue of `plea18` (`roles.txt`):

- Four roles besides the superuser: `plea` (owns every table and function), `plea_local`, `plea_witness`,
  `plea_control`. None is a superuser, none is a member of another, none has a connection limit.
- **`plea_local` is the role the assistant's client is configured with** (`verify/deploy.py` 35, 136). It is the role
  that stores results. It has SELECT on all seven tables (`attempts`, `decisions`, `evidence`, `provisions`, `receipts`,
  `results`, `roots`), INSERT on `receipts` only, and may execute `plea_write` and `plea_put_result`. It may make
  temporary tables. It may not create anything in the schema.
- `plea_witness`: SELECT on all tables, INSERT on `receipts`, `plea_write`. `plea_control`: SELECT on all tables,
  `plea_write`, `plea_new_root`.
- `plea_write`, `plea_put_result` and `plea_new_root` are SECURITY DEFINER functions owned by `plea`: they are the only
  way a login role changes an authoritative table.
- The server allows 100 connections, 3 kept for superusers. There is no statement, lock or idle timeout.
- A role proves who it is by a password over the local network (scram-sha-256). **The passwords of all four roles are
  literal text in the repository** (`plea:plea`, `plea_local:local`, `plea_witness:witness`, `plea_control:control`; 23
  places listed in `roles.txt`). In the demonstration, which role a party holds is therefore a matter of which line of
  configuration it uses, not of what it is able to do. The schema of each database here was installed with the owner's
  password taken from the README.

## 2. What `plea_local` could and could not change, by trial

Each statement was tried in a transaction of its own as `plea_local` on a budget holding a real FAIL
(`commit_check.txt`, step 1).

- **Refused** (permission denied): UPDATE, DELETE, INSERT and TRUNCATE on `results`; UPDATE, DELETE and INSERT on
  `evidence`; UPDATE and DELETE on `decisions`; UPDATE and DELETE on `attempts`; SELECT … FOR UPDATE on `results`;
  LOCK TABLE in ACCESS EXCLUSIVE and in SHARE mode; ALTER TABLE; CREATE TABLE in the schema; SET ROLE to the witness's
  role or the owner's; setting `session_replication_role`; calling `plea_new_root`.
- **Refused by the store's function**: a RECONCILE written through `plea_write` as `plea_local`, with or without a
  report ("operation RECONCILE is reserved to the witness").
- **Allowed**: LOCK TABLE in ACCESS SHARE mode (which blocks no reader); temporary tables; advisory locks; reading
  `pg_stat_activity`.
- Rows before and after: unchanged (16 decisions, 2 reports, 2 results), and the courier's reading of the FAIL
  unchanged.

Two lines of that step say nothing and are not relied on: the UPDATE on `roots` named a column that does not exist, and
the attempt to end the witness's sessions found none open at that moment. The catalogue gives `plea_local` SELECT only
on `roots`.

## 3. When a verdict is committed, by test

**A FAIL stored as a value stays (step 2): the reading holds.** With the FAIL result stored, the service had a second
EFFECT report recorded for the same run, signed with the gate's key over a PASS result, and then stored that PASS
result. The witness answered 200 and recorded the decision as DUPLICATE / VERDICT_RETRY, with the report: decisions 16
to 17, reports 2 to 3. `plea_put_result` raised no error and changed nothing: the stored result was the same before and
after. The courier read FAIL and its notice was accepted by the mailbox. A report with another verdict (NO_EFFECT) was
recorded as DENIED / VERDICT_IS_FINAL, also with its report, and changed nothing (step 2b).

**A FAIL not yet stored can be replaced, and nothing is said (steps 3, 3b, 3c): the two-digest observation holds, and
it is more than an observation.** The gate host itself ran the check and signed FAIL; the witness recorded the report;
the client was told "FAIL: REQUIREMENT NOT MET". The only thing changed was the client's own storing of the result,
which is the client's to do.

| Step | What the service did | What the courier and the mailbox then showed |
|---|---|---|
| 3 | stored nothing; had a second report recorded over a PASS result (DUPLICATE / VERDICT_RETRY, with the report); stored the PASS | `run_outcome` PASS. The courier with the 900 s waiting time made no notice before or after. A courier started afterwards made none. The mailbox holds nothing for the run from either |
| 3b | stored a result marked 'unknown'; second report; stored the PASS, which replaced the 'unknown' | the same: PASS, no notice, the mailbox holds nothing for the run |
| 3c | as 3, with the PASS forged for the same design, its numbers changed to meet the limit (achieved 180 signed by the gate host, 220 in the forgery) | the same: PASS, no notice, nothing in the mailbox |

In each case the witness holds, and gives to anyone who asks, two EFFECT reports for the one run with two different
digests (step 5). Nothing remarks on that.

**What the record's checker said (step 4).** The record of the budget did not verify, for one reason: in steps 3 and 3b
the PASS result put in was another design's, and the sixth check says "the verdict is for another design than the one
sent". For step 3c, where the forgery names the right design and numbers that pass, the checker raised nothing against
that run. So the checker does not remark on two digests either, and a forgery made with a little care passes it.

**A control.** A courier with no waiting time, run between the first report and the replacement, did make a notice of
the run: UNVERIFIED. With the default waiting time of 900 s that notice is not made if the replacement comes sooner.

**What this needs.** The gate's key (to sign the second report), the client's certificate (to send it to the witness),
and the client's role (to store the result). The property file gives the service all three. A client without the gate's
key can only withhold the result, which gives UNVERIFIED after the waiting time.

## 4. Can the role, or the account, decide when the witness answers?

- **The database role can make every reading fail at a time of its choosing (step 6a).** `plea_local` opened
  connections until the server refused: 97. While they were held, GET /run and GET /checkpoint were answered by a closed
  connection in under 0.02 s, three of three, and a courier's pass ended blocked (with no waiting time it made its
  COURIER_BLOCKED notice). When the connections were closed, readings took 0.04 s again.
- **The operating-system account can delay one chosen reading by a chosen time (step 6b).** The witness process was
  stopped and continued 5 s later: the GET /run in flight was answered 200 after 5.04 s. In the demonstration every
  party runs under one account (`verify/deploy.py` 11-12).
- **Not shown:** slowing one chosen reading through the database role alone. With SELECT only, no lock it may take
  blocks a reader.

## 5. A false headline standing alone

At `e25a297` the explanation line of four form-2 notices is empty (the lost entries of `WHY_2`), so their headline
stands alone. `notice_words.txt` prints each from the wording code. For UNVERIFIED the headline is "THE STORED RESULT
DOES NOT MATCH THE GATE'S SIGNATURE". In step 3 the courier signed exactly that, and the mailbox receipted it, for a run
that had no stored result at all. The sentence the earlier form carried ("the courier has found no stored result that
hashes to the digest the gate signed") would have been true. For NO_OUTCOME the headline says a run "was admitted",
which by reading (`verify/check_record.py` 204-207) is also said of a run whose intent was only accepted; that one was
not tested.

## 6. Readings and the courier under honest load

One budget was filled to 996 of its 1000 runs and two more to 150 each, by four clients at once: 1296 runs in 1509 s
(52 a minute), 973 PASS and 323 FAIL. A submission took 1.0 s on an empty budget and slowed as the budget filled
(median 3.2 s, 95th centile 12.1 s, longest 13.4 s).

| Reading, with the courier's certificate | While the load ran | Nothing else running |
|---|---|---|
| GET /run, seconds | 4543 requests, all 200: median 0.060, 95th centile 0.087, 99th 0.101, longest 0.163 | 996 runs: median 0.038, 99th 0.049, longest 0.101 |
| GET /run, bytes | about 2040 (largest 2075) | the same |
| GET /checkpoint, seconds | not sampled | median 0.020 |

GET /run did not slow with the size of the budget beyond the load itself: median 0.052 s with 1 to 571 runs in the
budget, 0.064 s with 825 to 996. A stored result was 1369 to 1404 bytes.

**The chain.** Each decision the witness gives carries the state of every run of the budget, so a decision was 3.8 KB
near the start and 127 KB at the end, and the whole chain of the 996-run budget was 508 MB in 126 pages (119 of them cut
short by the witness's limit on a page's bytes), read in 37 s. The cost of reading a chain from its start grows with the
square of the budget's runs. A courier that has read it before reads only what is new.

**The courier, from nothing.** Its first pass over the 996-run budget took 98 s: read whole, 996 runs asked for, none
put off, 247 FAIL notices made and accepted, its statement of coverage made, exit status 0. Each later pass took
0.16 s. Over all three budgets (1296 runs) from nothing: 120 s; then 0.31 s and 0.24 s.

**The courier while runs are made.** On a fresh database, four clients made 531 runs in 6 minutes (89 a minute). The
runs not yet in a final phase, sampled each second, were 2 at the median and never more than 4. The courier made 31
passes in that time, one about every 12 s. All 31 ended read whole, with nothing put off and nothing unread, exit
status 0, in 0.3 to 3.2 s (median 2.0 s); the most runs asked for in one pass was 41.

**Runs that never reach a final phase.** None arose: all 1827 runs of the two measurements ended in EFFECT. How often
honest operation leaves one cannot be measured here, because there is no operation, only tests.
`phases_all_databases.txt` gives the counts in every database on the machine; those of the development database come
from test suites that cut runs off on purpose and say nothing about a rate.

## Verdicts

| Question | Verdict | On what |
|---|---|---|
| Is the service's role confined as the store's grants say? | PASS, for `plea_local` | the catalogue, and 20 refused changes |
| Is the service confined to `plea_local` in the demonstration? | FAIL | every role's password is in the repository |
| Does a FAIL stored as a value stay? | PASS | step 2 |
| Is a verdict the gate host signed and the witness recorded committed? | FAIL | steps 3, 3b, 3c: replaced by PASS with no notice |
| Does anything remark on two signed digests for one run? | FAIL | the courier, and the record's checker for step 3c |
| Can the service decide when the witness answers? | Shown two ways | step 6a (the role), step 6b (the account) |
| Can a budget be read whole under honest load, with no change to the gateway? | PASS, for what was measured | 31 of 31 passes whole under load; 98 s from nothing for 996 runs, against 600 s |
| The same for a real engineering check, on separate machines, over days | UNPROVEN | not measured: see the limits |

## Limits

- One machine, the loopback interface, one database server, half an hour of load. No other work on the machine.
- The check is the self-test fixture: its result is 1.4 KB and a run takes 1 to 13 s. A real check with a large result,
  or one that runs for minutes, was not measured. Nothing failed during the load: no crash, no restart, no cut-off run.
- "Read whole" is the eighth form's own ending of a pass (nothing put off, nothing unread). The eighth form is
  INCOMPLETE and has eight confirmed defects; the measurement does not depend on the alarm that is missing, and it does
  rest on the courier's own account of what it asked for.
- The checks of sections 3 and 4 were made by the author of the harness acting as the service. No planted-defect pass
  was made on these harnesses.
- The replacement of a verdict was made within seconds. How long the service has was not measured. What step 3 shows:
  if it replaces before a courier's waiting time has passed, nothing is sent; and the replacement still succeeded after
  a courier with no waiting time had already sent UNVERIFIED, so a later replacement leaves the mailbox with one
  UNVERIFIED notice and no FAIL.
- Nothing here proposes a repair.
