# Amendment 17: third internal review, of f4c1de6 (corrections after the second review)

22 November 2026. Kept as returned by the reviewing agent, unedited, below the line. The reviewer is a separate AI agent
working at the author's instruction, read-only on the worktree, with its own database (plea_rv3). This is an internal
review, not an independent validation. Its probes and their outputs are kept in
`tests/amend17_dev_evidence/review_f4c1de6_probes/`.

---

[tier: opus] REVIEW OF f4c1de6 (corrections after the second review). This is an internal review by an AI agent, done at the author's instruction. It is NOT independent validation.

**Method.** I read the earlier review, `git show f4c1de6` and the code around each change. The worktree was clean and I left it unchanged (git status is empty). I bound no ports and started no deployment. In-process probes ran against my own database, plea_rv3, which I created and then dropped. Probes and outputs are in `/tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad/review3/`. Each probe's expectation is in its docstring or in a change file, written before it ran.

== CRITICAL ==
None found.

== HIGH ==
H1'. The fix for H1 depends on a realm the console is not required to have, that nobody checks, and that is stored nowhere. Under the documented commands, D16's put-back still works. RUN (q2_console.out: S1, S2, S3).
- Where:
  - front_ctl.py:245: `--realm` is optional.
  - front_ctl.py:112: with no realm, `_record` silently records nothing.
  - README_FRONT.md:135 and :150, and front_door.py:4: the documented commands give no `--realm`. Since front_door.py:1034 makes `--realm` required, the documented start command now fails.
- S1. The console is given no realm (the CLI default). The engineer revokes while the front door is stopped, or within its 30 s look interval. The earlier jobs.json is put back before the front door reads it. On restart the front door admits the revoked job (`s1_admitted: true`).
- S2. The console is given a realm that differs from the front door's by one character. The revocation succeeds and is recorded under the wrong name. The job is then admitted (`s2_admitted: true`, rows show the wrong-realm row).
- S3. The revocation is recorded under realm R1 and the file is put back. The front door is restarted with `--realm R2` and admits the job (`s3_admitted: true`). This is H2 moved from the CA file's bytes to a command-line string. The front door neither stores its realm nor refuses a changed one.
- Compared with the earlier H1, the window is narrower: it is now bounded by the front door's uptime plus 30 s, not by "until the job calls". With a stopped front door it is still unbounded.
- Fix: have the front door write its realm once into HOME/front (and refuse to start with a different one), and have front_ctl read it from there. Or make `--realm` mandatory for revoke and rebind, validated against front_state.REALM and against the stored realm. Then document it.

== MEDIUM ==
M-a. A revocation is refused when the console cannot reach the database, so a leaked job stays admitted. RUN (q2_console.out S4).
- Where: front_ctl.py:215-219.
- The console's control DSN is wrong or unreachable while the front door's database is fine. The answer is `Refused(... nothing was written)`, jobs.json is unchanged, and `s4_admitted: true`.
- Before this commit the revocation took effect on the next request.
- For a revocation, the safe order is: try to record, always write the file, then report a recording failure. Refusing is right for rebind, not for revoke.
- Related (ARGUED): nothing checks that PLEA_CONTROL_DSN (the console) and the front door's --local-dsn name the same database. verify_ctl.py:51 defaults to the database `plea`.

M-b. Rebind records before it writes, so a failure or crash between the two makes the job unusable for good. RUN (q2b_rebind_later.out; S5 of q2_console.out was a failed prediction, see Process).
- Where: front_ctl.py:196-202.
- The record takes REBIND seq 2 (CURRENT), then writing jobs.json fails (simulated ENOSPC; a crash or Ctrl-C has the same effect).
  - The binding in force, seq 1, is now STALE: the job is refused.
  - A retry a minute later signs a new `time`, so it gets a new digest, and is refused CONFLICT. So is every later retry.
  - The only way out is to revoke the job and enrol a new job name.
- An immediate retry within the same second succeeds only because now() has one-second resolution.
- This fails closed, but it is a permanent loss of the job from a transient error. The console's message gives no remedy.

M-c. The planted-defect runner cannot run the five new defects, and two older ones no longer apply. RUN (q1_planted_run1.err, q1_planted.out).
- Where: tests/amend17_mutants.py:30-31 and :48.
- 'revocations recorded only when the job calls' has 4 fields, but the loop unpacks 5 (`for name, path, old, new, tests in MUTANTS`). It raises ValueError at entry 15 whatever names are given. OUT is written only at the end, so a full run writes nothing.
- 'no form kept per budget' (governor) and 'a binding for another budget admitted' (front_door) now find their text 0 times: NOT PLANTED. The commit rewrote both lines.
- So D21's per-budget form rule and A2's budget-matches-baseline rule have no planted defect any more.

== LOW ==
L-a. R33 check 3 still passes with the identity fix removed. ARGUED.
- Where: verify_tests.py:3477 and :3496.
- `good_aid` is the first attempt in the record with design GOOD. attempts_of keeps the store's order, so the pending legacy attempt comes first even when a second, new attempt also ran GOOD.
- The pending run never reached the tool, so `sum(GOOD) == 1` holds either way. Check 2 is now discriminating (calls_1 == calls_0).
- Fix: require exactly one attempt with design GOOD, with its phase EFFECT.

L-b. F37 never shows that the console's recording is needed. ARGUED.
- job-c is revoked through the console (verify_front_tests.py:1822), but a restart follows at once and record_revocations records it anyway.
- A defect that removed only front_ctl._record would not be caught. The combined planted defect hides this.
- That defect also leaves the sweep loop's own observe of REVOKE bindings in place (front_door.py:826). It is caught only because nothing looks within 30 s.

L-c. Mutant 'a revocation at a number already seen not kept' changes the SQL function. ARGUED.
- start_front runs front_state.install, so the mutated function is installed with CREATE OR REPLACE into whichever database the runner uses.
- It stays there until the next install, so any suite running on that database at the same time sees it.

L-d. Identity-form rule details. RUN for the rule (q3_forms.out); the upgrade case is ARGUED.
- A process still running pre-Amendment-17 code, during a rolling upgrade, writes 'a-' ids. On a budget where new code wrote 'a2-', it now stops every run. Before, it switched the budget's form.
- That fails closed, but the docstring does not say it, and the only way out is to baseline again.

L-e. Smaller points.
- The console's realm is not validated: realm '' is accepted and recorded as ':job-s6' (RUN, q2 S6).
- CREATE TABLE IF NOT EXISTS does not add the new length CHECK to an existing table. The function's INVALID test covers it.
- A holder of plea_local can hold the row lock in an open transaction and so stall the console's revoke indefinitely. The job's admits stall too, so nothing is admitted meanwhile (ARGUED).

== THE QUESTIONS ASKED ==
- **Revoked job admitted again:** yes, by S1, S2 and S3 above, and by a database restore (stated in the code). I found no route when the realm matches, is unchanged, and the console records the revocation before the put-back.
- **plea_local and plea_control:**
  - Neither gains a way to admit. The revocation branch only sets revoked=true, using GREATEST, and the non-revoke UPDATE runs under FOR UPDATE, so it cannot clear the flag. ARGUED from front_state.py:51-80.
  - They can deny a job, as before. New: plea_local can block the console's rebind by planting CONFLICT, and stall its revoke (L-e). Both fail closed.
- **Realm:**
  - No realm: 503 for everyone (fail closed).
  - A wrong realm format: the front door starts and admits nobody.
  - A different realm: everything recorded is lost (S3).
  - Two front doors on one realm and one database: they share rows, which fails closed. On one home with two realms, the console records under only one.
- **Console order:** it fails closed for admission, but not safely for revocation (M-a), and permanently for rebind (M-b).
- **Mixed forms:**
  - Governor.attempt raises for every caller (RUN q3a). plea_mcp answers it as a tool error (RUN q3c). The front door answers 409, or 500 if the form changes between its two reads (ARGUED).
  - Names of neither form are ignored (RUN q3b).
  - Re-registration and crashes keep the form (ARGUED). An honest trigger exists only during a rolling upgrade (L-d).
- **rederive(control=True):**
  - It refuses only controls whose values exceed 28 significant digits, so that the written value does not recompute. A run of that design would be UNKNOWN by the same function (verify_tools.py:135).
  - R32's 'many' and 'run' cases, the plain fixture, and a 28-digit value whose margin needs 29 digits all pass (RUN q4).
  - Setting aside only the design-space test is right: evaluate(control=True) skips exactly that test, and nothing else in rederive depends on the design. ARGUED.
- **Tests:**
  - F37's new checks would fail with H1's front-door part, H2 or M1 removed (ARGUED, the timing reading above).
  - R32's new check would fail without the rederive change (q4 'far').
  - R33's check 6 would fail without the mixed-forms refusal (q3a shows the refusal); check 3 would not fail with the identity fix removed (L-a).
  - The old 'controls not put to the checker' defect is still caught, by R32 check 1's wording (q4 'across').

== EARLIER FINDINGS ==
- H1: partly corrected (H1' and M-a).
- H2: corrected for the CA file. The same reset now follows a change of realm (S3).
- M1: corrected (ARGUED from SQL; the author's F37 run shows 403).
- M2: corrected: `usable` is shared by admit and the look (ARGUED).
- M3: corrected (RUN q3).
- M4: corrected (RUN q4).
- M5: not corrected by this commit. No full-suite run; it is stated as pending before declaration.
- M6, M7: recorded, not changed. The register now states M7.
- L1: corrected (RUN q3c).
- L2: partly corrected: check 2 yes, check 3 no (L-a).
- L3: corrected, but README_FRONT.md now lacks `--realm` (H1').
- L4: unchanged.
- L5: partly corrected: p_job's length is bounded; the number of rows is not; a rolling upgrade now stops runs (L-d).

== PROCESS (my own probes) ==
- Q1 run 1 stopped with ValueError, which is itself M-c. I kept it, wrote q1_CHANGE.txt and a new expectation, and re-ran with the predicate unchanged.
- Q2 S5 predicted that an immediate retry would be refused CONFLICT; it succeeded. I kept the predicate and the output, wrote q2_CHANGE.txt and a new expectation, and ran a separate probe, Q2b (delayed retry), which matched.
- Q4 'peek29' predicted a margin failure; there was none. The predicate was not changed; it is reported here.
- Author's declared hashes: 86bf43… (verify_tests.py), 18018d… (verify_front_tests.py) and 749a71… (before_review2) match the committed files.

== COULD NOT CHECK ==
- Anything end to end: F37, R32 and R33 against this commit (I relied on the author's review2_run1 files), real TLS with a changed CA, and the sweeper's timing.
- Rebind through the real _envelope and _deliverable. Q2 and Q2b replace them, and root_for, in-process.
- Which database the suites' PLEA_CONTROL_DSN names during F37.
- Behaviour of a real pre-Amendment-17 process during a rolling upgrade.
