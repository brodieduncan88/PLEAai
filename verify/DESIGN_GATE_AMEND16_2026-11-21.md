# Amendment 16: the final design gate before any Step 3 (design, evidence and review only)

21 November 2026. Private working material. Internal work under the owner's direction. It is not an independent
validation, not a declaration and not an acceptance of anything. Nothing is implemented by it, and no code of the
courier, the mailbox, the witness, the gateway or any deployment configuration is changed. It is kept on the branch
`diagnostic-amend16-alarm-2026-11-21` only.

**What it is.** The owner asked for four design decisions to be settled, with evidence, before any coding: verdict
transitions and UNKNOWN; the mailbox's freshness, deadline and behaviour without a courier; the mailbox's 64 KiB limit
against the evidence a notice must carry; and incremental consistency at about 1,000 runs. This note gives each
decision, the tests made for it on the deployment, the design claims with a standing each (PASS, FAIL or UNPROVEN), the
defects found on the way, and what stays open. The independent review asked for is in
`verify/DESIGN_GATE_REVIEW_AMEND16_2026-11-21.md`; its findings and what was done with each are in section 9 here.

**Baselines.** The provisional design baseline is the Step 2 note at
`1fcc2270582f3c8ca179653911b0e73b06405d96` (`verify/STEP2_DESIGN_AMEND16_2026-11-21.md`) with its erratum
(`verify/AMEND16_ERRATUM_FRESHNESS_2026-11-21.md`). The threat-model baseline stays
`verify/AMEND16_THREAT_MODEL_ADDENDUM_2026-11-21.md` at `0da1a85e819daac4839e51917402f3fcd67d5caf` on
`verification-amendment-16`, which is not touched. Where this note corrects the Step 2 note it says so, and the Step 2
note is left as it was written. The bounded model, its nine weakened variants, its three searches stopped at the state
limit and its counterexamples are unchanged in `tests/diag_amend16_model/` and are bounded evidence, by the same author
as the rules: they are not a proof.

**Standing of the code.** `e25a297` stays INCOMPLETE, failed at internal review and undeclared, with its eight
confirmed defects. S-1 to S-4, B-1 to B-3 and every earlier finding stand as recorded.

**Words used.** A gate report claims EFFECT, NO_EFFECT or UNKNOWN. A *verdict report* claims EFFECT or NO_EFFECT; its
*pair* is (claim, result digest). The *verdict scope* is what a gate report signs beside its claim and digest: the
budget, the run and the run's nonce. A report is *authentic* for a scope when it is an effect report signed by a gate
key given, whose signature verifies, naming that budget, run and nonce. The check's own verdict (PASS, FAIL, or
UNKNOWN when the check did not run to a result) is inside the result that an EFFECT report signs; it is not the gate's
claim UNKNOWN, and the two are kept apart throughout.

## 1. The tests made for this gate

All on one machine, against the unchanged code of `e25a297` (the pinned copy used for the earlier diagnostics), each on
a deployment of its own, in fresh databases `plea23` and `plea24`. Scripts and every output, failed runs of the harness
included, are in `tests/diag_amend16_gate/`. The predicates in them are the harness's own and are not proposed code.
Development evidence only.

| Part | Script | What it asks | When (UTC) | Output |
|---|---|---|---|---|
| clocks | (inline, in `README`) | which clocks the host offers | 18:11 | `clocks.txt` |
| A | `gate_token.py` | a 32-byte token through the witness's real checkpoint reading | 18:19:10 to 18:19:15 | `gate_token.json`, run 2 |
| C | `gate_release.py` | reports recorded with a RELEASE decision, early, or of every kind | 18:21:08 to 18:21:18 | `gate_release.json`, run 2 |
| B1 | `gate_unknown.py B1` | an honest gate host's UNKNOWN report after a run is cut off | 18:24:27 to 18:24:33 | `gate_unknown_B1.json`, run 2 |
| B2 | `gate_unknown.py B2` | UNKNOWN and then a verdict from an honest gate: a stalled host, a second host | 18:24:08 to 18:24:12 | `gate_unknown_B2.json` |
| B3 | `gate_unknown.py B3` | every sequence of 1 to 4 reports for one run, through the real witness | 18:24:33 to 18:31:48 | `gate_unknown_B3_len3.json`, `_len4.json` |
| D | `gate_sizes.py` | how large a report can be; the mailbox at its limit | 18:32:21 to 18:33:11 | `gate_sizes.json`, run 2 |
| E | `gate_result_store.py` | whether a stored result can be changed, and whether storing one is in the chain | 18:32:12 | `gate_result_store.json` |

**Failures of the harness, kept.** (1) `gate_token` run 1 stopped at its last step but one: it offered a server's
certificate as a client's, which TLS refuses; run 2 records that as an answer. (2) `gate_release` run 1 took a run's
phase from a field the witness's reading does not carry, so its line for what `e25a297` concludes read "None"; run 2
takes the phase from the chain's own table. (3) `gate_unknown B1` run 1 gave its last step no stored result to judge;
run 2 does. (4) `gate_sizes` run 1 is void: it was started while part B3 was running, and the test deployment's ports
are fixed, so its services could not start and it spoke to the other deployment, which refused its certificates.
Nothing of run 1 is used. Part B3's own run was not disturbed: only refused handshakes reached it.

**Machine.** Linux 6.18.44, Python 3.11.17, PostgreSQL 16. The machine was restarted four times on 21 November (09:41,
12:29, 17:38, 18:00:57 UTC); each restart stops PostgreSQL and resets a kernel setting, and both were put back by hand
before these tests, as approved earlier.

## 2. Decision 1: verdict transitions, and UNKNOWN

### 2.1 What an honest gate does (code, then deployment)

- **An honest gate host signs UNKNOWN in two cases.** When the check's function raises an error other than "no effect"
  (`plea_gateway/gate_host.py` 268-270). And when a host starts, finds a run still marked running by a previous owner
  of its state, marks it interrupted, and is then asked for that run (257-260).
- **By the code's own description, UNKNOWN can be followed by a verdict.** "If the interrupted host completes the tool
  after all (it was stalled, not dead), its EFFECT or NO_EFFECT report replaces the UNKNOWN one, which is kept as
  prior_report" (lines 24-33; `finish()`, 168-178). The governor treats a stored unknown outcome as not final and asks
  the host again (`plea_gateway/governor.py`, `_replay` and `_requery`).
- **The witness never moves a run on an UNKNOWN report.** A reconcile that carries one is recorded as a no-op while the
  run has no verdict, and as denied once it has one (`plea_gateway/store.py` 397-407).

**B1, on the deployment: an honest host signs UNKNOWN.** A run was cut off by the gate host ending while the check ran
(exit status 137). The client was told the service could not be reached. The host was started again and the same
design sent again: the host signed an UNKNOWN report; the witness recorded it as NOOP, VERDICT_UNKNOWN_STAYS_CHARGED;
the run stayed CONSUMED; the client was told "UNKNOWN: THE RUN WAS INTERRUPTED"; the courier made one INTERRUPTED
notice. Sent a third time: the same report again, a second no-op, no second notice. The record verified at `e25a297`
with both reports and the outcome INTERRUPTED. The host's own row stayed interrupted, with no earlier report. For
comparison, a check that fails by itself while the host stays up (the fixture's `crash` mode) does not produce the
gate's UNKNOWN: the gate signed EFFECT over a result whose own verdict is UNKNOWN, and the run became final.

**B2, on the deployment: UNKNOWN, then a verdict, from an honest gate.** Staged with real components and one staged
fault:

1. A failing design was submitted by the ordinary client. Six milliseconds after the governor called the gate host,
   with the run marked running, the host process was stopped where it stood (SIGSTOP). Nothing was recorded for the run
   yet.
2. After the host's one-second lease had run out, a second gate host with the same key and the same state file was
   started. It took the state over (generation 2) and marked the run interrupted.
3. The second host was asked for the run, with the receipts the governor had used. It answered with a gate-signed
   UNKNOWN report. Sent to the witness: NOOP, VERDICT_UNKNOWN_STAYS_CHARGED. The courier made an INTERRUPTED notice.
4. The first host was let go on, 2.2 s after it was stopped. It finished the check, signed EFFECT, and wrote it over
   the interim report, keeping the UNKNOWN as `prior_report`. The waiting client's governor reconciled it: APPLIED,
   VERDICT_RECORDED. The client was told "FAIL: REQUIREMENT NOT MET" and the result was stored.
5. The second host, asked again, now gave the EFFECT report with the UNKNOWN as its prior report.
6. A late copy of the UNKNOWN report sent to the witness after the verdict: DENIED, VERDICT_IS_FINAL, and kept.
7. The courier then made a FAIL notice. The record verified at `e25a297` with three reports (UNKNOWN, EFFECT,
   UNKNOWN) and the outcome FAIL.

**What B2 is, and is not.** Both hosts were unchanged gate hosts holding the gate's key; neither signed anything an
honest host would not. The stall was made by the harness. The second host was started by the harness on another port,
because the stalled process still held the first port, and the harness carried its UNKNOWN report to the witness as a
governor that tries again would. So this is the path the code describes, shown to happen with the real parts. It was
not seen in ordinary operation, and a takeover at the same address needs a machine arrangement this one-machine
demonstration does not have.

### 2.2 What the witness records: the transitions, enumerated

**B3.** Every sequence of one to four gate-signed reports for one run was sent to the real witness, each sequence on a
run of its own taken to the point of awaiting its verdict: 780 sequences over five reports (two UNKNOWN reports with
different results, Ua and Ub; two EFFECT reports, E1 over a FAIL result and E2 over a PASS result; one NO_EFFECT
report, N); 6,830 decisions in the chain. (The runs were made with the service's own database role and no check was
run; the reports were signed with the deployment's gate key, which the property file gives the service.)

| The run has | A report arrives claiming | The witness records | Report kept? |
|---|---|---|---|
| no report yet | UNKNOWN | NOOP, VERDICT_UNKNOWN_STAYS_CHARGED | yes |
| UNKNOWN reports only | UNKNOWN (the same or another) | NOOP, VERDICT_UNKNOWN_STAYS_CHARGED | yes |
| no report yet, or UNKNOWN only | a verdict (EFFECT or NO_EFFECT) | APPLIED, VERDICT_RECORDED: the run becomes final with that claim | yes |
| a verdict recorded | the same claim, **whatever its digest** | DUPLICATE, VERDICT_RETRY | yes |
| a verdict recorded | the other claim | DENIED, VERDICT_IS_FINAL | yes |
| a verdict recorded | UNKNOWN | DENIED, VERDICT_IS_FINAL | yes |

No other answer was seen for any of the 780. In every sequence every report was kept, in order, and was authentic
(780 of 780), and the run's final phase was the first verdict sent, wherever the UNKNOWN reports stood. The fourth row
is S-1: the witness's name for a second EFFECT report with another digest is the name it gives an honest repeat.

### 2.3 The decision

**The rule is a rule on the set of authentic reports of one verdict scope, not on their order.**

| The authentic reports of the scope hold | Standing | Record verification |
|---|---|---|
| T1. no report | no signed result | as today |
| T2. UNKNOWN reports only, any number, any results | no verdict; the run is INTERRUPTED as today | as today |
| T3. exactly one distinct verdict pair, any number of times | one signed result; a repeat is not a conflict | as today |
| T4. UNKNOWN reports and exactly one distinct verdict pair, in any order | one signed result; the UNKNOWN reports are kept and shown | **passes**, on the conditions below |
| T5. two or more distinct verdict pairs, with or without UNKNOWN reports | **a conflict** | **FAILS**; every report is kept as evidence |

No transition from one verdict to another is permitted, by any path, under any name: there is no supersession of a
verdict. T4 is not a supersession of a verdict. It is "no verdict yet, then the one verdict".

**Why T4 is permitted, against the fail-closed default.** The owner's default forbids it unless two things are shown.

1. *An honest gate actually emits a gate-signed UNKNOWN report.* Shown by code and on the deployment (B1), and an
   honest gate was shown to follow it with a verdict for the same run (B2, staged as described).
2. *Permitting it cannot conceal, replace or legitimise a conflicting verdict.*
   - **Conceal.** The conflict rule looks at verdict pairs only. An UNKNOWN report adds no pair and removes none. In
     B3, of the 780 sequences, 480 sent more than one distinct verdict pair and the rule found a conflict in all 480,
     372 of them with UNKNOWN reports among the verdicts; 300 sent at most one pair and the rule found a conflict in
     none, 258 of them with UNKNOWN beside the one pair.
   - **Replace.** The witness records the first verdict and never moves a run on UNKNOWN. An UNKNOWN before the
     verdict changes nothing; one after it is denied and kept (the table above; B2 step 6).
   - **Legitimise.** A stored result is to be believed only if it hashes to the digest of the run's one verdict pair
     and the scope holds no conflict. An UNKNOWN report's digest is never a digest a result is compared with.
   - **What it cannot do, and neither can forbidding it.** Whoever holds the gate's key can sign UNKNOWN and then a
     false verdict for a run whose true verdict the witness was never shown. That is the forgery made before the
     witness sees anything (UM6 a). It needs no UNKNOWN report: the false verdict alone does the same. Forbidding T4
     would not stop it, since the forger simply leaves the UNKNOWN out; it would only fail the records of honest
     interrupted runs.

**Conditions on T4.**

- **C-1. Set, not sequence.** No implementation may take "the latest report" or "the report after the UNKNOWN" as the
  verdict. The verdict is the one distinct pair; with two there is none.
- **C-2. The reports are kept and shown.** A record and a notice of the run's outcome name every UNKNOWN report of
  the scope beside the verdict.
- **C-3. The change is told.** When a run for which an INTERRUPTED notice was made later has a verdict, the courier
  makes a notice of that, whatever the verdict, PASS included. Today nothing is said when the verdict is PASS, so the
  mailbox would go on holding "no verdict exists" for a run that has one. This is a new requirement of this gate.
- **C-4. A verdict then UNKNOWN is not a fault.** A late copy of an UNKNOWN report can reach the witness after the
  verdict by honest reordering (B2 step 6). It is kept, it is denied, and it changes nothing.

**What a failed record says.** That the gate's key signed two different results, or two different verdicts, for one
run. It does not say which is right, that the run failed, that a verdict was changed, or who signed. An honest fault
can produce it too: a gate host that loses its state and runs a check twice over inputs that changed signs two
results. That record fails as well, and should: the record is not consistent. Evidence of equivocation is not evidence
about the verdict's correctness, in either direction; and one consistent report is not evidence that it is correct.

**What `e25a297` does today.** In 95 of the 780 sequences the witness recorded the FAIL result first and
`check_record.run_outcome` reads PASS when the PASS result is the one stored. The conflict rule is not built.

## 3. Decision 2: the mailbox's freshness, deadline, and the courier's absence

The corrected definition of the erratum stands: F1 to F6, T1 to T6, restart failing closed. This section adds what the
gate was asked to settle and what the tests changed.

### 3.1 The token through the real witness (part A)

A token of 32 bytes from the operating system's source of randomness was sent as the nonce of `GET /checkpoint`, with
the courier's certificate, to the unchanged witness.

| Question | Answer, by test |
|---|---|
| Does a 32-byte token fit? | Yes. Written as 43 characters of URL-safe base64 without padding: status 200, and the nonce is signed back exactly as sent. Written as 64 hexadecimal characters: the same. |
| The limit | 1 to 64 characters: lengths 1, 43, 63 and 64 give 200; 65 and 128 give 400. An empty nonce gives 400. No nonce gives a checkpoint whose nonce is null. |
| The encoding | Letters, digits, `_` and `-` only, case kept. Base64 with its padding (`=`), or with `+` or `/`, gives 400. A space, a dot, a tilde, a NUL, a non-ASCII letter and a newline each give 400. |
| What the signature covers | statement, root (the budget), seq, head, business, witness, time, nonce, at, head_at. A change to the nonce, the budget, the number or the time makes the signature fail. |
| Is the nonce bound to the budget? | **In one signed statement, yes.** The witness signs the budget and the nonce together; a checkpoint for one budget checked for another is refused ("it is for another budget"), and one relabelled as another budget's fails its signature. |
| Does the witness refuse a token used for another budget? | **No.** One token asked for two budgets at one witness gave two valid checkpoints, each naming its own budget. |
| Does the witness enforce single use? | **No.** The same token asked twice gave two valid checkpoints, a second apart. The witness keeps no memory of a nonce. |
| A request that gives the nonce twice | The last one is signed. A reader must compare the signed field, never the request. |
| A checkpoint that names a decision | `at` and that decision's head are signed too; a decision beyond the chain gives 400. |
| Who is given a checkpoint | The courier's, the keeper's and the governor's certificates: 200. So the service, which holds the governor's certificate, can also ask for a checkpoint with any nonce it knows. |
| Sizes | 557 bytes with this token; 1,109 bytes at the largest names. |

**So.** The witness gives the binding of the token to a budget and to a point of the chain, and gives nothing else.
Binding to the *correct* budget, single use, and refusal of replay are the mailbox's to enforce, by comparing the
signed fields of the checkpoint with its own record of the challenge. PO-6 of the Step 2 note ("read, not tested") is
now tested for the witness's side.

### 3.2 The clock (the host, as it is)

| Clock | On this host |
|---|---|
| `CLOCK_BOOTTIME` | offered (id 7), resolution 1 ns; cannot be set (the kernel refuses, as root). By its definition it goes on counting while the machine is suspended. |
| `CLOCK_MONOTONIC` | offered, 1 ns, cannot be set. By its definition it does **not** count suspension. **Python's `time.monotonic()` is this clock here**, so it must not be the mailbox's measure of age. |
| `CLOCK_REALTIME` | the wall clock; root can set it (not tried). For people only (T3). |

- **The primitive for T2 is `time.clock_gettime_ns(time.CLOCK_BOOTTIME)`.** Availability, resolution and that it cannot
  be set are verified.
- **Not verified: suspension itself.** This machine cannot be suspended from inside; the two clocks differed by 0.000 s
  at the reading. And where a hypervisor freezes a guest whole, no clock inside the guest need move: then only the
  wall clock, corrected afterwards, shows the gap, which is why T5 compares the two and takes the larger age. If
  nothing corrects the wall clock either, nothing inside the machine can see the pause. That is a limit of any design
  that keeps time on the machine it runs on, and it is recorded here, not solved.
- **A restart of the machine is a restart of the mailbox:** a new epoch, and everything NOT COVERED (four such
  restarts happened on this machine today).

### 3.3 How the mailbox issues, tracks and enforces

**The life of a token, at the mailbox.** For independent modelling or testing; it is specified and checked nowhere.

| From | Event | To | What the mailbox does |
|---|---|---|---|
| none | an admitted courier asks for a challenge for budget B | ISSUED | makes the token; records epoch, serial, B, the courier's key, L, and the moment by T2; writes it durably; returns the challenge signed. At most a set number are ISSUED for one budget and key: the oldest is made VOID |
| ISSUED | a statement on this token, signed by the token's courier key, passes every check | USED | keeps the statement; the budget is COVERED to the statement's N from now until the token's age passes L |
| ISSUED | a statement on this token, signed by the token's courier key, fails any check | SPENT | keeps the statement as evidence, with the reason; nothing is covered by it |
| ISSUED or USED | the token's age passes L | EXPIRED | nothing; coverage that rested on it has ended |
| USED, SPENT, EXPIRED or VOID | any statement on this token | unchanged | keeps it as evidence; counts nothing. The same statement delivered again is answered with its first receipt |
| any | the mailbox starts | VOID | a new epoch; every earlier token counts for nothing |
| any | a statement naming this token, not signed by the token's courier key | unchanged | refused |

**The checks on a statement** (all must pass): it is signed by a courier key given; the challenge in it is this
mailbox's own, of the current epoch, ISSUED, for this budget and this key (F1, F4); the checkpoint in it verifies
under a witness key the mailbox was given, names this budget, and its signed nonce is the token (F2); the courier's
signature covers the challenge, the checkpoint and the commitments (F3); the token's age is within L, by T2 and the
larger-age rule T5 (F5); the mailbox holds every item the statement commits to (F6); and the statement continues the
last one it accepted for this budget (the same chain of items, a decision number not lower, the earlier statement's
digest named).

**What the mailbox does not check.** That the observation is true. It checks bindings and holdings. The truth of what
was observed is the courier's signed word (the baseline's O1 to O4), and rests on the courier and its key being the
engineer's.

**Binding, three ways, and where each is enforced.**

| Bound to | By | Checked by |
|---|---|---|
| the budget | the challenge names B (mailbox's signature); the checkpoint names B (witness's signature); the statement names B (courier's signature); all three must agree | the mailbox, at the statement |
| the checkpoint | the witness signs the token as the checkpoint's nonce | the mailbox, with the witness's public key (which it does not hold today) |
| the observation | the courier signs the challenge, the checkpoint, the budget, N, the head and the commitments together | the mailbox (signature and holdings); a reader (recomputing the commitments) |

**Each case the owner named.**

| Case | What happens | Kind of guarantee |
|---|---|---|
| Replay of a statement | the first receipt again; nothing counted afresh | safety |
| A second statement on a used token | kept, not counted | safety |
| A token of another budget or key | refused | safety |
| A token from before a restart | counts for nothing | safety |
| An old checkpoint with a new token | cannot exist: the witness's signature covers the nonce | safety, resting on the witness's key |
| Mailbox restart | new epoch; every budget NOT COVERED until a statement on a new token | safety; coverage is lost until the courier reads again (liveness lost) |
| Courier absent | when the last used token's age passes L the budget is NOT COVERED, by the mailbox's own time, with nothing received | safety |
| Wall clock set back | no effect on age (T2); an anomaly is recorded and shown (T5) | safety |
| Wall clock set forward | the larger age is used; statements may be refused that were in time | safety; liveness lost |
| Machine suspended | `CLOCK_BOOTTIME` counts it; ages grow; tokens expire | safety, **unverified on this host** (3.2) |
| Mailbox process stopped and continued | as suspension: the clock went on | safety |
| Statement delayed in delivery | if it arrives after L it is kept and never counted; the courier must take a new token and read again | safety; liveness lost |
| Token asked early, used late | its age counts from its issue | safety |

### 3.4 When NOT COVERED can be seen from outside, with no courier

NOT COVERED is the default. It needs no statement and no alarm to be true. Precisely, at the mailbox's time t a budget
is NOT COVERED when any of these holds, and each is decided by the mailbox alone:

1. no statement has been accepted for it in the current epoch (never, or not since a restart);
2. the token of the last accepted statement is older than L;
3. the mailbox cannot read its own record of the budget;
4. the last statement on a token of the budget was SPENT for a broken continuation (a chain cut back or forked, as
   the courier reported it, or a statement that does not continue the last).

**How it is seen.** By asking the mailbox for a signed status (Step 2, MB-10). This gate adds one requirement: **the
status must sign back a nonce chosen by whoever asks.** Without it, a status saying COVERED that was signed yesterday
can be shown today, and only the mailbox's unguarded wall clock, written in it, tells them apart. And a rule for the
reader: **no fresh signed status saying COVERED is NOT COVERED.** A mailbox that is down, stalled or cut off gives no
status, and the reader must read that as NOT COVERED, never as "still covered".

**Safety and liveness, kept apart.**

| | Guaranteed by the design, if built as specified and its conditions hold | Not guaranteed |
|---|---|---|
| Safety | The mailbox never counts a statement whose token is older than L, used before, of another budget, key or epoch. A fresh receipt never makes an old observation fresh. A status says COVERED to N only while such a statement stands. | — |
| Liveness | — | That the courier runs. That a reading ends within L: the service can make the witness slow or unreachable (a 5 s stall of the witness made one reading take 5.04 s; 97 held connections made every reading fail; S-3). That a budget ever becomes COVERED. |
| Notification | — | **That anybody is told.** The mailbox sends nothing to anyone. NOT COVERED is seen only by one who asks, and only while the mailbox answers. **No bounded time to notification is claimed, and the mechanism cannot give one.** What is bounded is how stale a COVERED answer can be: the reading it rests on began no more than L before the status was signed. |

## 4. Decision 3: the 64 KiB limit and the evidence of a conflict

### 4.1 What was measured (part D)

| Thing | Size | By |
|---|---|---|
| a real gate report of this deployment | 499 bytes | test |
| two real reports, whole | 1,002 bytes | test |
| a report for a run named with 512 non-ASCII letters (the witness's longest name) | 3,522 bytes; two: 7,044 | test: made, recorded as the run's verdict, read back authentic |
| a report for a run whose nonce is 70,000 characters | **70,448 bytes; two: 140,896** | test: the store took the nonce, the witness accepted the intent and recorded the verdict, and the reading gave the report back authentic |
| a nonce of 1,000,000 characters | refused by the database at START (an index row limit) | test |
| a real FAIL notice; its receipt | 1,440 bytes; 501 bytes | test |
| the mailbox's limit | a notice of exactly 65,536 bytes is taken; 65,537 is refused | test |

**So two whole reports do not always fit.** An honest gate host's nonce is 42 characters. Two reports at the witness's longest
run name were 7,044 bytes; a budget name of the longest kind would add about as much again (calculated, not made), so
two honest reports stay under 16 KB. But the nonce is the service's to choose, the store sets no limit
on it short of the database's own, and a single authentic report larger than the mailbox's whole limit was put on
record. No size between 70,000 and 1,000,000 characters was tried, and no bound is claimed between them. This is a new
finding (S-6, section 8). The Step 2 note's "both reports whole (983 bytes for two, calculated)" holds for honest
reports only.

**What the mailbox as it stands takes.** A notice whose outcome it does not know (CONFLICT) is refused. A notice with
one more field is refused. A notice of an outcome it knows, with any words at all up to the limit, is taken: the
mailbox does not check a notice's words. The last is not proposed as a route: a notice of a conflict must be a kind
the mailbox and every reader know.

### 4.2 The decision: a notice of a conflict

**It always carries, under the courier's signature:** the scope (budget, run, and the nonce's SHA-256 and length); the
checkpoint it was read at (N and head); for each of the two reports it rests on, the decision it sits at, that
decision's operation, kind and code, the report's claim and result digest, its size, and **the SHA-256 of the whole
report as the witness gave it**; the number of reports the reading gave for the run, the number of distinct verdict
pairs, and one digest over all of them in the order of their decisions (the commitment to the whole answer).
The two reports are the one at the run's VERDICT_RECORDED decision and the earliest that differs from it.

**The reports themselves, by size.**

| Case | Where the two reports are kept | In the notice |
|---|---|---|
| each report is at most 16 KiB (every report an honest gate host can sign within the witness's limits on names) | **in the notice, whole** | the notice is at most about 40 KiB |
| a report is larger, up to the mailbox's limit for one piece of evidence (proposed: 1 MiB) | **at the mailbox, as a piece of evidence of its own**, sent before the notice and stored under its SHA-256 | its digest and size; the mailbox refuses the notice until it holds every piece the notice names |
| a report is larger than that | **not held by the mailbox.** It stays in the witness's store, which no granted role can alter (by test, V6) | its digest and size, and the words that the mailbox does not hold it |

**Durable retrieval.** A piece of evidence is written whole and synced before the mailbox answers, as notices are, and
is given back by its digest. **Complete binding.** The courier's signature covers each report's digest; nothing can
be put in a report's place without the digest failing. **Omission is detected.** A reader recomputes each digest from
the report it is given; a missing or different report fails. **Fail closed.** A notice of a conflict fails the record
whether or not its evidence can be produced; evidence that is missing or does not match never turns a conflict into no
conflict. It is reported as a conflict whose evidence is incomplete.

**The limit of the third row.** Evidence the mailbox does not hold is only as durable as the witness's store, which
the engineer does not control and the owner of the database can rewrite. For such a report the notice proves that the
courier saw a report with that digest, and no more. A bound on the size of a nonce at the witness or the store would
remove this case; that is a change to the frozen gateway and is not proposed.

### 4.3 The cumulative set for about 1,000 runs

The Step 2 note's chain of items stands (section 15): every item the courier sends for a budget carries the chain's
identifier, its number k and A(k) = H(A(k−1), digest of item k); a statement carries k and A(k), 64 characters whatever
the budget's size.

- **At 1,000 runs.** If every run calls for a notice: 1,000 items of about 1.4 KB, 1.4 MB held at the mailbox; the
  statement stays about 3 KB. Observation records (135 bytes a run) go in parts of at most 478 records: three parts
  for a reading from nothing, one small part in steady state.
- **Verified independently.** A reader who is given the mailbox's items recomputes A(1) to A(k) in order, checks each
  item's signature and its own chain fields, and compares A(k) with the statement and with the mailbox's status: 1,000
  hashes and 1,000 signature checks. A missing, altered or reordered item breaks the chain at its number.
- **What the mailbox must add for it.** On each delivery, that k is the next number and A(k−1) is its own head, or it
  refuses and says where its head is; and an index of items by chain, so that the order can be given to a reader.
- **Not established.** The chain of items is specified and has been checked nowhere: not in the model, which names
  notices as a set, and not in any code. In particular a new chain after a courier loses its state must not be a way
  to drop an item unseen. It stays an UNMODELLED proof obligation (PO-10).

## 5. Decision 4: incremental consistency, and scale

### 5.1 The release-decision path, tested (part C)

**The store keeps whatever is sent as evidence with a RELEASE or a RECONCILE, whatever the decision.** A gate-signed
EFFECT report for a forged PASS result was sent with a RELEASE, and with a RECONCILE, at every phase:

| Sent with | When | The witness's answer | Report kept and given back by the reading? | Authentic for the run's scope? |
|---|---|---|---|---|
| RELEASE | the run is final (the gate host signed FAIL) | DENIED, CONSUMPTION_IS_FINAL (label NONE) | yes | yes |
| RELEASE | before the run's START | DENIED, NO_BOUND_FENCING_EVIDENCE (NONE) | yes | yes |
| RELEASE | before the attempt exists | DENIED, UNKNOWN_OR_DISCARDED_ATTEMPT (NONE) | yes | yes, once the attempt is made with that nonce |
| RECONCILE | before the attempt exists | DENIED, UNKNOWN_ATTEMPT (WRONG_BINDING) | yes | yes, once the attempt is made with that nonce |
| RELEASE | reserving, reserved, token, intent pending, consumed | DENIED, each time (NONE) | yes | yes |
| RECONCILE | reserving, reserved, token | DENIED, NOT_CONSUMED (WRONG_BINDING) | yes | yes |
| RECONCILE | intent pending | DENIED, NOT_CONSUMED (AUTHORISED) | yes | yes |
| RECONCILE | consumed | APPLIED, VERDICT_RECORDED | yes | yes |

- **`e25a297` believes such a report.** With the forged PASS result then stored for the run, `check_record.run_outcome`
  reads PASS, and **the courier made no notice** for a run whose gate host signed FAIL (two real runs, X and Y). For
  the two reports recorded before their attempt existed, `run_outcome` reads PASS in the same way; those attempts
  were made without a check and no courier was run on them. The courier does not look at which decision a report sits at. The record's checker does,
  for a report at a RELEASE: such a record fails its sixth check ("not recorded with a reconcile decision"), while
  giving the run the outcome PASS. This is S-1 by a second route, and a new finding (S-5, section 8).
- **Under the rule of section 2.3, every one of these is a conflict** once a second verdict pair is in the scope: the
  rule takes every authentic verdict report the reading gives, wherever it sits.
- **They are visible to a reader that follows a cursor.** In every case the report came with a decision of the chain,
  after the cursor, naming the run. Over both budgets of this test, every report row in the store (41) sat at a
  RELEASE or RECONCILE decision naming its run, at that decision's number. With the earlier tests (no granted role can
  insert, change or remove a report), PO-7's first half is now tested.

**Every kind of evidence (PO-8).** Twelve kinds were sent with each operation to one run. A report row was kept for
every one that carried anything at all: text that is not a report, an empty object, a report signed by another key, a
report with its digest altered, reports for another nonce and another run, a fence report, UNKNOWN, NO_EFFECT, EFFECT.
**Only a decision sent with no evidence has no row** (two of the 24). So:

- **Correction to the Step 2 note's count rule (section 6, step 2).** It required every report to sit at an AUTHORISED
  reconcile, and so called a run with a stray report "not observed". The rule is restated: (a) the *verdict* of a run
  is the report at its one APPLIED, VERDICT_RECORDED decision; (b) the *conflict rule* takes every authentic verdict
  report of the scope, at any decision; (c) the *count rule* requires a report at every RELEASE or RECONCILE decision
  for the run whose label is not NONE (AUTHORISED, WRONG_BINDING, BOUND_FENCE: each means evidence was sent), and
  every report must sit at a RELEASE or RECONCILE decision for the run. A conflict is reported as a conflict, not as a
  run that could not be observed.
- **A limit that cannot be removed without changing the store.** A decision labelled NONE may have a report or none,
  and the chain does not say which. A verdict report sent with a RELEASE is always labelled NONE. So if that report
  were later missing from the witness's answer, nothing in the chain would show it. It can go missing only by the
  database owner's hand (no granted role can remove it), which is outside the service's stated powers (DP1); and such
  a report can never be the one a result is believed on. But the *evidence of that conflict* would be gone unseen.
- **A second limit of the same kind.** The chain's hash covers a decision's operation, kind, code and the budget's
  state, not the report. The chain says that a report claiming EFFECT was authorised at decision k; it does not say
  which digest. The reports of a run are authenticated one by one by the gate's signature; as a set they are
  authenticated by nothing but the reading itself. What the courier saw is fixed afterwards by the courier's own
  signed commitments, not by the witness.

### 5.2 A stored result leaves no decision (part E), and what follows

- **Storing a result adds no decision to the chain.** By test: the chain's length was the same before and after.
- **A value once stored cannot be changed or removed by the service's role.** By test: a second and a third value were
  "accepted" and silently not stored; DELETE and UPDATE were refused. An outcome stored as "unknown" can be replaced,
  once, by a value. (An observation, not a defect of this amendment: the store answers a refused replacement as
  success.)
- **So "final" is not the mark of a run that need not be read again.** A run can be final in the chain with its result
  not yet stored, and the result can be stored later with no trace in the chain. A courier that re-reads only runs
  with a new decision would then never see the stored FAIL: it would hold an UNVERIFIED notice for a run whose
  verdict was committed after its reading. **Correction to the Step 2 note, section 14, step 4:** the runs asked for
  again at every reading are those named by a new decision **and every run that is not settled**. A run is *settled*
  when its verdict is recorded, its scope holds no conflict, and its stored result is a value that hashes to the
  verdict's digest. A settled run cannot change without a new decision that names it: its reports cannot be altered
  by any granted role, a new report needs a decision, and its stored value cannot be replaced.
- **Cost of the unsettled set.** In honest operation it is the runs in flight. A service that withholds results can
  keep it as large as the budget: one reading of a run each (0.04 to 0.06 s, about 2 KB, measured) at every pass, up to
  about a minute a pass at 1,000 runs. Each such run already carries a notice. This is D-h's cost, kept and bounded by
  the budget, not removed.

### 5.3 The mechanism, link by link

| Asked | Answer | Standing |
|---|---|---|
| Are the decisions read incrementally authenticated? | Each is under the chain's hash to the head the witness signs in a checkpoint that bears the mailbox's token. Its operation, the run it names, the verdict claimed and the label are under the hash. The report is not (5.1). | by code and test A3, A7 |
| Is the cursor continuous? | The courier's checkpoint names the cursor's decision and the witness signs that decision's head back; the mailbox holds the last statement's N and digest and refuses a statement that does not continue it. A courier that has lost its cursor reads from the start. | the witness's side by test A7; the courier's and mailbox's side specified, not built |
| Forks, missing decisions, rollbacks | A decision left out breaks the hash to the signed head. A chain cut back gives "beyond the chain" (test A7, status 400). A different head for the cursor's decision is a fork. | `e25a297` has these checks (code reading; its tests R25, R26, R30 in development runs). **Not exercised in this gate.** A fork cannot be made without the database owner's power. |
| A conflicting report added after a run was final | Recorded as a decision naming the run (DUPLICATE, DENIED), seen after the cursor, the run read again, the conflict found | by test: C1 here; V2 and commit_check earlier |
| Complete coverage evidence | The chain of items and the statement's commitments (4.3); each run's observation record is in the part of the reading that last read it | specified; UNMODELLED |

### 5.4 Transfer at about 1,000 runs

From the measurements of 21 November (996 runs, one machine): a decision as the witness gives it grows from 3.8 KB to
127 KB, because each carries the state of every run of its budget, and its hash is over that state.

| Reading | Transfer | Note |
|---|---|---|
| from nothing, at 996 runs | 508,180,089 bytes in 126 pages, 37 s for the chain; 98 s for a whole reading by the courier | measured; grows with the square of the runs |
| one new run at about 1,000 runs, following the cursor | about 1.0 MB: its eight decisions at about 127 KB each; plus about 2 KB for the run, 0.6 KB for the checkpoint, at most 1.6 KB for a notice and about 3 KB for the statement | calculated from the measured sizes |
| the whole life of a 1,000-run budget, read a little at a time | about 0.5 GB in all: the same total as one reading from nothing | calculated; the square law is not removed by reading incrementally, only spread |
| each run that is not settled, at each pass | about 2 KB and 0.04 to 0.06 s | measured |
| a courier that loses its cursor | the whole reading from nothing again | — |

**No linear scaling is claimed.** Following a cursor removes the re-reading of old *runs*. It does not remove the
witness's transfer of the budget's whole state with every decision. S-4 stays open. Removing it needs a change to the
witness and the store, which is not proposed.

### 5.5 What cannot be had without changing the witness or the store

- L-1. Whether a decision labelled NONE carried a report (5.1). The loss of such a report is not detectable.
- L-2. Which report was recorded at a decision: the chain does not hold its digest (5.1).
- L-3. A trace in the chain of a result being stored (5.2). Worked around by reading unsettled runs again, at a cost.
- L-4. The square law of the chain's transfer (5.4; S-4).
- L-5. A bound on the size of a report (4.1; S-6).
- L-6. A forgery made before the witness sees anything, and one consistent false chain signed by the witness: the
  baseline's stated limits, unchanged.

## 6. The design claims, each with its standing

**PASS** means the claim is supported by evidence that can be run again, within the bounds stated beside it. **FAIL**
means the evidence contradicts the claim. **UNPROVEN** means it is specified, argued or read, and not established.
Nothing here is built, so a PASS on a design claim is a PASS on the facts the design rests on, never on an
implementation. The reviewer's standing for each claim is in section 9.

| Id | Claim | Author's standing | Evidence |
|---|---|---|---|
| **Decision 1** | | | |
| G1.1 | An honest gate host signs a gate-signed UNKNOWN report, and the witness records it without moving the run | PASS | code; B1, B2 step 3 |
| G1.2 | An honest gate can sign UNKNOWN and later a verdict for one run | PASS as staged; not seen in ordinary operation | code; B2 |
| G1.3 | The witness's transitions are the six rows of 2.2 and no others | PASS for sequences of up to four reports of five kinds | B3 (780) |
| G1.4 | Under the set rule an UNKNOWN report neither hides nor makes a conflict among the reports the witness holds | PASS within B3's bound; argued beyond it | B3: 480 of 480 found, 0 of 300 false |
| G1.5 | Permitting T4 gives the baseline's adversary nothing it lacks without it | UNPROVEN | argued (2.3); the model has no UNKNOWN |
| G1.6 | Two distinct verdict pairs in one scope fail record verification | the rule: PASS on the data it needs. **As built at `e25a297`: FAIL** (a record with a second report at a reconcile verifies) | B3, C; V3 earlier |
| G1.7 | Identical repeated digests make no conflict | PASS on the data | B3; V4 earlier |
| G1.8 | Every report is preserved in the witness's store against every granted role | PASS | B3 (780 of 780 kept); V6 earlier |
| G1.9 | A failed record is worded as equivocation only, never as a verdict's falsity | UNPROVEN | wording specified; no notice or checker text exists |
| G1.10 | A verdict after an INTERRUPTED notice is itself noticed (C-3) | UNPROVEN | new requirement; nothing built |
| **Decision 2** | | | |
| G2.1 | A 32-byte token passes the real checkpoint reading and is signed back exactly | PASS | A1 |
| G2.2 | The limit is 1 to 64 characters of letters, digits, `_`, `-`; padding is refused | PASS | A1, A2 |
| G2.3 | The checkpoint's signature binds the nonce and the budget in one statement | PASS | A3, A4 |
| G2.4 | The witness itself refuses a token for the wrong budget, or a second use | **FAIL** | A4, A5, A6. It must be the mailbox's check |
| G2.5 | The mailbox's token rules (3.3) enforce single use and refuse every replay named | UNPROVEN | specified; UNMODELLED; nothing built |
| G2.6 | A suspend-counting clock that cannot be set is available on the host | PASS for availability, resolution and that it cannot be set. **UNPROVEN across a real suspension or a hypervisor's pause** | `clocks.txt` |
| G2.7 | A late statement never makes a budget COVERED; a fresh receipt never makes an old observation fresh | PASS in the bounded model only (4,137,699 states; the baseline's wording fails there). UNPROVEN as a mechanism | `tests/diag_amend16_model/` |
| G2.8 | NOT COVERED can be seen without a courier | UNPROVEN | specified (3.4); needs the status with the reader's nonce |
| G2.9 | A bounded time to notification | **Not claimed. The mechanism cannot give it** | 3.4 |
| **Decision 3** | | | |
| G3.1 | Two honest reports fit whole in a notice | PASS | D: 1,002 bytes; 7,044 at the longest run name |
| G3.2 | Two authentic reports always fit whole | **FAIL** | D: one authentic report of 70,448 bytes on record |
| G3.3 | The mailbox as it stands can take a notice of a conflict | **FAIL** for a new outcome or field | D |
| G3.4 | The reference mechanism of 4.2 binds, detects omission and fails closed | UNPROVEN | specified |
| G3.5 | The chain of items represents and verifies the set for 1,000 runs | UNPROVEN | specified; UNMODELLED (PO-10) |
| **Decision 4** | | | |
| G4.1 | A report enters the store only with a RELEASE or RECONCILE decision naming its run | PASS | code; C (41 of 41 rows); role tests earlier |
| G4.2 | A report sent by the release path, early, or at a denied decision is visible to a reader following a cursor | PASS | C1, C2, C5, C6 |
| G4.3 | Such a report cannot evade the conflict rule of 2.3 | PASS on the data. **As built at `e25a297`: FAIL** (the courier is silent; S-5) | C1b, C2b, C6 |
| G4.4 | The Step 2 count rule as written | **FAIL**; restated in 5.1 | C7 |
| G4.5 | The loss of a report at a decision labelled NONE is detectable | **FAIL**; cannot be had without a change to the store (L-1) | C7, C8 |
| G4.6 | A settled run cannot change without a new decision naming it | PASS for the service's role | E; role tests earlier |
| G4.7 | Reading unsettled runs again closes the gap left by a result stored after a reading | UNPROVEN | specified (5.2); not modelled |
| G4.8 | Forks, rollbacks and missing decisions are detected | UNPROVEN in this gate | code reading; A7 for the witness's answers only |
| G4.9 | The costs at 1,000 runs are as in 5.4, and are not linear | PASS | measurements of 21 November; arithmetic |

## 7. Remaining counterexamples and proof obligations

**Counterexamples that stand** (none is repaired; each is a property of `e25a297` or of the parts as they are):

1. A second EFFECT report with another digest, recorded as VERDICT_RETRY; the stored PASS is believed (S-1; 95 of 780
   sequences here).
2. A verdict report recorded with a RELEASE, before or after the run's verdict, or before the attempt exists; the
   courier believes it and is silent (S-5).
3. A report larger than the mailbox's limit, authentic and on record (S-6).
4. The baseline's receipt-counted freshness: the model's `receipt_time` trace (erratum).
5. The nine weakened variants of the model, each breaking an invariant; three searches stopped at 14,000,001 states.
6. The forgery made before the witness sees anything (UM6 a), with or without an UNKNOWN before it.
7. The service slowing or stopping the witness, so that no reading ends in time: NOT COVERED for as long as it likes.

**UNMODELLED, by the owner's instruction, until independently tested or modelled:**

- PO-A. **The mailbox's token state machine** (3.3): single use, epochs, bounded tokens, the SPENT state, the checks
  on a statement, the continuation of statements.
- PO-B. **The per-budget chain of items** (4.3): that every omission, alteration and reordering is detected, and that
  a new chain cannot drop an item unseen.

**Other obligations open after this gate** (the Step 2 note's PO-1 to PO-19 stand except as stated):

- PO-6 (the token through the witness): tested for the witness's side (part A). The mailbox's side is PO-A.
- PO-7 (reports only with decisions; the release path): tested (part C).
- PO-8 (the count rule against every kind): tested, and the rule corrected (5.1).
- PO-9 (UNKNOWN): examined by code, on the deployment and by enumeration (section 2); G1.5 stays UNPROVEN.
- PO-C. The model has no UNKNOWN report, no release-path report, no result stored after a reading, no epochs and no
  replay. Each rule of this gate that touches those is outside the model.
- PO-D. Suspension, and a pause by a hypervisor, against the mailbox's clock (3.2).
- PO-E. Forks and rollbacks against the cursor and the mailbox's continuation rule (5.3).
- PO-F. The status with a reader's nonce, and the reader's rule that no fresh status is NOT COVERED (3.4).
- PO-G. The wording of a conflict: that no notice, record or checker text says more than equivocation (G1.9).
- PO-H. A gate-signed verdict report that names the run under another nonce is not authentic for the scope and is
  ignored by the rule. Whether it should fail the record is not decided.
- The deployment-security blockers B-1 to B-3 are untouched: no compliance claim can be made whatever is built.

## 8. Findings of this gate for the defect register

Entered in `verify/DEFECT_REGISTER.md` as a new dated part, beside S-1 to S-4; nothing earlier is changed.

- **S-5. A gate-signed verdict report recorded with a RELEASE decision, or before its attempt exists, is believed.**
  The witness keeps whatever evidence is sent with a RELEASE or RECONCILE, whatever it decides; the reading gives it
  back; `check_record.run_outcome` counts any authentic EFFECT report of the scope, wherever it sits. On two real runs
  whose gate host signed FAIL, with a forged PASS result stored, the courier of `e25a297` made no notice. The record's
  checker fails such a record at its sixth check when the report sits at a RELEASE. A report sent with a RECONCILE
  before its attempt exists sits at a reconcile decision; a record of that case was not made. Open. A second route to
  S-1.
- **S-6. The size of a gate report is not bounded short of the database's own limits.** A nonce of 70,000 characters
  was accepted by the store and the witness, and the run's authentic report (70,448 bytes) is larger than the
  mailbox's whole limit. A notice cannot always carry two reports whole, and every reader of a run's answer must be
  ready for one of this size. Open. An operational risk and a constraint on the design.
- **Observations, not entered as defects.** The store answers a refused replacement of a stored result as success
  (5.2). The witness gives a checkpoint, with any nonce, to the governor's certificate (3.1). The mailbox does not
  check a notice's words (4.1).

## 9. The independent review

(Filled from `verify/DESIGN_GATE_REVIEW_AMEND16_2026-11-21.md` once the review is returned.)

## 10. The minimum changes for a Step 3 (none is made)

**The witness, the gateway, the store: none.** The three readings as they are.

**The mailbox** (Step 2's MB-1 to MB-10 stand; what this gate adds or makes exact is marked *gate*):

| Interface | Change |
|---|---|
| `POST /challenge` (new) | MB-1: a token for a budget and a courier key, signed, with epoch, serial, L and the moment of issue |
| `POST /deliver` (changed) | MB-2: takes the new item form with its chain fields, the notice of a conflict, observation parts, and the statement of coverage; *gate*: refuses an item that is not the next of its chain, saying where its head is; *gate*: refuses a notice that names evidence it does not hold |
| `POST /evidence` (new, *gate*) | a piece of evidence up to a set size, stored under its SHA-256 and returned with a signed holding; needed only for a report over 16 KiB (S-6) |
| `GET /status?root=B&nonce=R` (new) | MB-10, and *gate*: signs back the asker's nonce |
| `GET /pubkey` | as today |

| Configuration and storage | Change |
|---|---|
| the witness's public keys | MB-3: to check a checkpoint; the mailbox holds none today |
| L, the bound on tokens, the size limits | MB-9: set by the operator at start |
| the clock | MB-4, and *gate*: `CLOCK_BOOTTIME` by name; never `time.monotonic()` |
| challenges, statements (accepted, spent, late), items indexed by chain, evidence, anomalies | MB-5 to MB-7: each written whole and synced before any answer |
| the epoch | MB-4, MB-6: made at each start; nothing of an earlier epoch counts |

**The courier and the record's checker** (not the mailbox, listed so that the whole is seen): the conflict rule of 2.3
on every authentic verdict report wherever it sits; the verdict taken from the VERDICT_RECORDED decision; the count
rule as restated; the unsettled set; the notice of a verdict after an INTERRUPTED notice; the new item form. In
`check_record`, which the mailbox imports: a change there is a change to the mailbox.

## 11. Recommendation

(Given after the review, in section 9's light.)
