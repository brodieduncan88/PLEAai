# Amendment 17: development log (22 November 2026)

Development runs made before the declaration of Amendment 17, and every change made to a test after it was run, under
the owner's rules VP-1 to VP-6 (`plan/GOVERNANCE_NOTE_2026-11-22.md`). Nothing here is an official run.

## Entry 1. R31, run 1, and the restated predicates

- **Run 1** (development; R30 and R31 only). R30 passed. R31 failed two of its checks.
- **What it showed.** Two designs given a 16-bit request key (case b), or a 16-bit attempt identity (case c), were refused
  as predicted: the second design was not run and was not told the first design's pass. The mechanism was not the one
  predicted:
  - The governor refused the second design itself (`RequestKeyReused`). The stored outcome of the shared attempt carries
    the nonce of the first design, and the nonce binds the arguments (`plea_gateway/governor.py`, `_replay`).
  - So the store's `ATTEMPT_BOUND_TO_OTHER_REQUEST` (predicted for case c) and the front door's new check of the design
    (predicted for case b) were never reached.
- **Kept (VP-2, VP-3).** The failing test file and run 1's output are in `tests/amend17_dev_evidence/r31_run1/`, with
  their SHA-256 in `SHA256SUMS` there. Run 1 was not against a declaration; its predictions were the test's own checks.
- **Changed (VP-4).** The diff is `tests/amend17_dev_evidence/r31_run1/CHANGE.diff`.
  - The checks of cases b and c now name the governor's refusal.
  - A case d is added, with the governor's replay guard taken out in the test's own process only, so the front door's
    check is reached and shown to refuse on its own.
  - No check was dropped. The security outcome checked (refused, not run, not told met) is the same.
- **Declared before run 2 (VP-5).** The test file is `tests/verify_tests.py` with SHA-256 `4b888b31b9ffe8e995a98566d99fdbc8781ad4923c50b2cc28854488db955d0b`. Expected:
  - R30 passes, 5 of 5 checks.
  - R31 passes, 6 of 6 checks: cases b and c are refused by the governor with `RequestKeyReused`; case d by the front
    door, "not for this design".
- **What this says about D21.** The white paper's claim that a collision of attempt identities can cause only a
  refusal is borne out at 16 bits, by the governor's nonce. It was not tested before. The consequence of a collision is a
  refusal of the second design for ever, which an assistant able to grind designs could aim at a chosen design. That is
  why the identity and the key are widened.

## Entry 2. The first full development runs of the gate and front suites, with A1

- **Run** (development; the gate suite R1 to R31 and the front suite F1 to F36, the code of A1 and the old client still in
  place). Gate: 29 of 31. Front: F1 failed, and the run went on. The gateway's own chain, run first on a fresh database,
  passed 22 of 22 stages.
- **R26 failed, and the fault was in the new code (`verify/check_record.py`, `identity_form`).** R26 makes, with the service's
  database role, an attempt named `!x`, whose design no record can give. The new rule read that name as of neither form,
  so every record of that budget failed check 5. A run whose design the record does not give cannot have its key or identity
  recomputed, and check 5 already passed it over. Corrected: only runs whose design the record gives decide the form. No
  test was changed for this.
- **R17 failed one check, on a length.** The print of a record whose reason is 440 characters long must stay on one row
  shorter than 450 characters. It was 460, because the attempt identity printed at the head of each row is now 67
  characters, not 18. Kept and restated under VP-2 to VP-5: entry 3.
- **F1 failed, as the change intends.** F1 is the attack D5 names, made through the first plug-in: it is now refused by the
  gate host (`BASELINE_NOT_ADMITTED_BUDGET`). It is retired by A4, with its property carried by R30.

## Entry 3. R17's bound on the length of a row, restated

- **Kept (VP-2, VP-3).** In `tests/amend17_dev_evidence/full_run1/`: the test file as run, the gate suite's output and
  console, and the gateway chain's console, with their SHA-256 in `SHA256SUMS`.
- **Changed (VP-4).** The diff is `CHANGE_R17.diff` there. The bound is raised by the 49 characters the attempt identity
  grew, from `< 450` to `< 450 + 49`. What the check is for is unchanged: a long reason with characters that cannot be
  printed is shown on one row, cut, and printable. The row held 460 characters; it would have held 411 with the earlier
  identity.
- **Declared before the next run (VP-5).** The test file has SHA-256 `43881a0517760a8e6b513f2d0abe7ba6b14bc0b18ff0a8b14b49ed8d41667b5f`. Expected:
  - every test of the gate suite passes except those A4 retires or migrates (declared in entry 4);
  - R17 and R26 pass with the old client still in place.

## Entry 4. A2 (D16): the record of bindings, and F37

- **The first two attempts did not run F37's checks.** In the first, A2's code was not yet applied, and F37 stopped with an
  error (`deploy_front` had no `OWNER_DSN`). In the second, a patch script stopped part-way: `front_door.py` named
  `front_state` without importing it, so F10 failed as well, with errors, not with its checks. Both outputs were
  overwritten by the next run and are not kept. That is a breach of VP-2/VP-3, recorded here: what was lost is two runs
  that stopped with an exception before any check of F37 was judged.
- **A design fault found before F37 ran.** The record was first keyed by job name alone. Every test deployment enrols a
  job named `job-a` in one shared database, and one database can serve more than one front door. So one front door's
  revocation would have refused another's job. The key is now the front door's certificate authority (the first 32 hex
  digits of the SHA-256 of its certificate) and the job's name. F37's one direct call by job name was changed to that
  name before F37's checks were first judged.
- **Run 3** (F37 and F10): both pass. Kept in `tests/amend17_dev_evidence/f37_f10_run1.json`.
- **What stays open (stated in `verify/front_state.py`).**
  - The service's own role can call the function with a made-up number or revocation and so refuse a job for ever. It
    fails closed: it can deny, never admit.
  - A restore of the database, together with an earlier `jobs.json`, would undo a revocation. That needs the database's
    owner or operator.
  - A change of the front door's certificate authority starts a new record. The old jobs' certificates are then not
    accepted anyway.
  - Pacing counters and the per-job lock stay in memory.

## Entry 5. A3 (D20): reproduced first, then corrected, and R32

- **Reproduced before any change** (`tests/amend17_dev_evidence/d20_repro_before.json`, made by
  `tests/amend17_dev_evidence/repro_d20.py` on the tree at `9efccf0`):
  - A control whose value is 199.99999999999999999999999999999 is baselined. It is written as 200, the limit, with
    "not met". The record of that baseline then fails check 2 for ever.
  - A run of the same value is UNKNOWN (`CHECK_OUTPUT_INVALID`), because the gate's tool already puts every run's verdict
    to the record's checker before it returns it.
  - A value of 33 significant digits that does not cross its limit is written rounded and stays consistent.
- **Corrected.** Check 2's rule for controls is moved, unchanged, into `check_record.control_problems`. Check 2 calls it,
  and `verify_ctl.make_baseline` calls it before anything is signed, stored or provisioned.
- **Declared before R32 is first run (VP-5).** The test file has SHA-256 `b7f41fb3125a0f7bc295b82d34f1b5cf752a28b8fc0584a887e135c6cdc07968`. Expected: R32 passes, 4 of 4.

## Entry 6. R32, run 1: a fault in the test

- **Run 1** (R32, R8, R10): R8 and R10 passed. R32 failed two of its four checks, because its third and fourth baselines
  were refused. They name a requirement already baselined at that service, and a second baseline of one requirement needs
  the engineer's reason (Amendment 9). The test gave none. The refusal's words were not kept by the test.
- **Kept.** `tests/amend17_dev_evidence/r32_run1/`.
- **Changed.** The test gives the reason for every baseline after the first, and now keeps the words of any refusal in
  its evidence. The diff is `CHANGE.diff` there. No check's predicate is changed.
- **Declared before run 2.** The test file has SHA-256 `1a7fb10c021db887ef00164c1673ceaa15940fb2a4b7f26614b57589995cc3b0`. Expected: R32, R8 and R10 pass.

## Entry 7. R32, run 2: the same fault, at enrolment

- **Run 2:** R32 stopped with an error before its checks were judged. Its second job, enrolled for the same requirement,
  needed the engineer's reason too (`front_ctl.enrol`). R8 and R10 passed.
- **Kept, and changed.** Kept in `tests/amend17_dev_evidence/r32_run2/`, with the diff. The two enrolments now give the
  reason. No predicate is changed.
- **Declared before run 3.** The test file has SHA-256 `0fa75b1a49ba9bc6b099c9dfaa7851c8839eb0ef444186ef75ca797d31fdfc9b`. Expected: R32, R8 and R10 pass.

## Entry 8. A4 (D6, D35): the first client retired, and the gate suite moved to the front door

- **Code.**
  - `verify/verify_client.py` refuses to run (exit 4) and names the route.
  - Its shared part, used by the front door and the console, is `verify/service_client.py`, unchanged in what it does,
    without the assistant's transport (`submit`) and without a configuration file of its own.
  - `deploy.Services.client_config` and `submit`, which put the gateway's database credential in an assistant's
    workspace, raise.
  - The readmes' legacy lines are corrected (D35).
  - `verify/experiment/` used the first client; its results are kept, and the readme says it cannot be run again as it
    stands.
- **Tests.** Every gate test reached the service through the first client, not only R1 to R13, because they share one
  helper (`Run`). So all of them move to the front door: `Run` makes a front-door deployment, enrols a job, and submits by
  `front_client.py`. Besides `Run`:
  - R10, R15, R18 and R27 enrol a job where they made a workspace.
  - R18 and R24 read the front door's view and status.
  - R18 and R23 read the first client's words from `service_client`.
  - Journals are the front door's.
  - R11 is rewritten, with its five assertions kept (two reworded to name the front door). What the workspace's credential
    could do is now tested with the service's own role and the front door's certificate.
  - R24's title names the front door's status in place of the first client's.
  - F1 and F2 are retired; their properties are carried by R30 and F7 (comment in the front suite).
- **Declared before the first run of the migrated suites (VP-5).**
  - `tests/verify_tests.py` has SHA-256 `3b9ad3985aac286e2a49c4d310bdb84c27dbf59cb285710c4bbd3bec14db01fa`; `tests/verify_front_tests.py` has `5e158ba226f6813f7faa70a238dfb65cef30329ceaf8c0ec2bba9279966699bb`.
  - Expected: the gate suite 32 of 32; the front suite 35 of 35 (F3 to F37).
  - A test that does not pass is kept as it ran, and reported here before anything in it is changed.

## Entry 9. The first run of the migrated suites, and what was changed after it

- **Run 1, as declared in entry 8.**
  - Gate suite 27 of 32: R1 to R13 passed through the front door, and R14, R17, R18, R25 and R26 failed.
  - Front suite 34 of 35: F12 failed.
  - Kept in `tests/amend17_dev_evidence/a4_run1/`, with both test files as run and `SHA256SUMS`.
- **Why the five gate tests failed.** In each, what the gate signed and recorded was as before; the difference was the way in.
  - R14: the front door words a missing card in its own terms ("NO USABLE BASELINE IS HELD FOR THIS JOB").
  - R17: one of its designs is not an object, and the front door refuses it before the gate sees it, so its counts were
    one short.
  - R18: one check is about the first client's own answer.
  - R25 and R26: they speak to the witness with certificates that the plain deployment admits and a front-door
    deployment does not.
- **Changed (VP-4; `CHANGE_verify_tests.diff` there).**
  - These five keep the plain deployment and reach it as the service's own caller: `tests/service_route.py`, the first
    client's code exactly as at `1b132e2` (SHA-256 `1cbfc5c09fa53fc46159abb75a2dd241782bece71aa05fb8414770199de23949`), run as a separate process with a configuration the test
    writes.
  - It stands for the service's own role (CAP-DB). It is never deployed or given to an assistant.
  - No check of the five is changed.
  - R1 to R13, R15, R23, R24 and R27 stay on the front door, where they passed.
  - The assistant's route for the inputs of the five is tested by the front suite (F7: a design that is not an object;
    F21: the words when no usable card is held).
  - Open for the owner: whether these five should be rewritten for the front door as well.
- **F12 failed for a fault in A2's code**, not the test. `Front()` read the certificate authority from its configuration
  when made, and F12 makes one in its own process with a configuration that holds only the journal. The authority is now
  read when a binding is first put to the record. Without it, nobody is admitted (StateUnavailable, then 503).
- **Declared before run 2 (VP-5).** `tests/verify_tests.py` has SHA-256 `b028a3631da5074f5253235fc982da7226fb975568776668e8e5afea3baedbeb`. Expected: R14, R17, R18, R25, R26 and F12
  pass.

## Entry 10. The first review of A1, and what it changed

- **The review.** A separate agent, instructed by the author, reviewed `d187172` read-only and started no deployment. That
  is internal review, not independent validation. Its report is kept as returned in
  `verify/reviews/AMEND17_REVIEW_A1_2026-11-22.md`, and its probes and their outputs in
  `tests/amend17_dev_evidence/review_a1_probes/`.
- **H1 (HIGH), accepted.** The change of identity had no path for a budget with runs from before it. A design sent before
  and again after was run and charged again, a pending run was left for ever, a call in flight across the change was run
  twice, and such a budget's record mixed two forms and could not verify. Corrected:
  - `governor.identity_form(store, root)`: a budget that already holds an attempt of the 64-bit form keeps that form,
    for its identities (governor) and its request keys (front door, the gateway's MCP server). A new budget takes the
    current form.
  - What stays (stated in the code): such a budget keeps 64-bit identities until the engineer baselines again; and a
    holder of the service's role can make a new budget's first attempt one of the earlier form.
- **M1 (MEDIUM), accepted.** R31's check of a mixed record was vacuous: the record it edited failed check 5 for other
  reasons. Now R31 makes a real record with one run of each form, each with its design (the governor's rule taken out in
  the test's process), and requires check 5 alone to fail, for that reason.
- **M2 (MEDIUM), accepted.** R31's cases b and c show the governor's nonce, a property from before this amendment; they do
  not test the widening. Their checks now say so. The widening is shown by case a, and the front door's own check by
  case d.
- **M3 (MEDIUM), answered in part.** A D5 refusal is made after the attempt has crossed. The unit is spent, and nothing is
  signed. The review said it is not noticed. The courier does notice it ("admitted and has no outcome", Amendment 11).
  R30 now checks that. That the unit is not refunded stays, as a limitation: only a holder of the service's role can make
  such an attempt, and it can spend units in other ways too.
- **L1, accepted.** The gateway's MCP servers' list of tools failed on a tool entry with a binder (four fields). Corrected
  in `mcp/plea_mcp.py` and `mcp/vanilla_mcp.py`. In-process mode never asks the binder; that mode holds the gate's key,
  so it is outside D5.
- **L2:** moot; the first client is retired (A4).
- **L3, accepted.** The record's label of its form now comes from the identities alone when no run gives its design. It
  decides no check.
- **L4:** met by H1's correction: within one budget the keys are of one form.
- **L5:** cosmetic; noted.
- **R33 (new):** the change itself. Runs are made by the earlier code, emulated in the test's process by its two rules,
  then the same budget is served by the code as it is now.
- **Declared before the run (VP-5).** `tests/verify_tests.py` has SHA-256 `477b4478c30f55e69d4130843da5a47dce49aa9bae64dfd417294079872f16f2`. Expected:
  - R30: 6 of 6;
  - R31: 7 of 7;
  - R33: 5 of 5;
  - the gateway's chain: 22 of 22;
  - and, when the full suites are next run, every test passes.

## Entry 11. R31 stopped with an error; R30 and R33 passed

- **Run** (R30, R31, R33, as declared in entry 10): R30 and R33 passed. R31 stopped with an error before its checks were
  judged. In case c it puts a 16-bit stand-in for `attempt_id` into the governor, and the stand-in took one argument,
  where the governor now passes two (the form of the budget).
- **Kept, and changed.** Kept in `tests/amend17_dev_evidence/a1b_run1/`. The stand-in now takes the second argument and
  ignores it, as the earlier stand-in of case b does. No check is changed.
- **Declared before the next run.** The test file has SHA-256 `36dd6c5382f967bb2a3acd0923aa5a376def7f5353b0b93715a1564ec4f51cc3`. Expected: R31, 7 of 7.
- **Run 2 of R31:** passed. Entry 10 declared "R31: 7 of 7". R31 has six checks, so that count was wrong: an error in the
  declaration, recorded here, not a seventh check that went missing. All six passed. Kept in
  `tests/amend17_dev_evidence/a1b_run2_r31.json`.
