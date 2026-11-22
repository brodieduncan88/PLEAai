[tier: opus] REVIEW OF 9efccf0 (A2), 0128d46 (A3), e1f1082 (A4) and abe044d (A1 corrected). This is an internal review by an AI agent, done at the author's instruction. It is NOT independent validation.

**Scope and method**
- I read every commit with `git show`. Where the worktree has uncommitted author changes (tests/verify_tests.py, the dev log, R34, amend17_mutants.py), I read the committed files instead.
- I bound no ports and started no deployment.
- Probes ran in-process against a database I created, plea_rv2. I dropped it at the end.
- Probes and their outputs are in `/tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad/review_a2a4/`. Each probe's expectation is written in its docstring before it ran.

== CRITICAL ==
None found.

== HIGH ==
H1. A revocation is absorbing only if the front door happens to see it. D16's own scenario still works, restart included. RUN (p1_unobserved_revoke.out, p1_db_rows.out).
- Where: front_door.py:441 (admit) and :805-808 (sweep, `b['event'] == 'REVOKE'` → `continue`). front_ctl.revoke (front_ctl.py:188-196) writes jobs.json only.
- A REVOKE reaches the record only when the revoked job itself connects while the REVOKE is in the file.
- Scenario: a job is enrolled and admitted (seq 1). The engineer revokes it (seq 2) because its key leaked. The holder of the key does not call. The sweep runs, skips REVOKE, and returns `[]`. Then an earlier jobs.json is put back, the front door is restarted, and the job is admitted again.
- Result: `p1_put_back_admitted: true`. The DB row is `job-p1|1|f`, never revoked.
- F37 always calls `sub()` straight after `s.revoke`, so it cannot see this.
- Fix: put every REVOKE the front door reads to the record (sweep, and admit for any job name), and do it at start-up. Better still, have front_ctl.revoke/rebind observe in the database before replacing jobs.json.

H2. The realm key is the hash of the CA file's bytes, so changing that file wipes the record of revocations. RUN for the record (p1b); ARGUED for TLS.
- Where: front_door.py:414-422.
- Entry 4 says "The old jobs' certificates are then not accepted anyway." The repo's own README.md:205 contradicts this. To rotate the authority, it says to "give each party a bundle of the old and new ca.crt during the overlap". The file's bytes change and old job certificates still chain. Re-encoding the file or renewing the CA with the same key has the same effect.
- Result: a revocation already recorded in the old realm, then a put-back, gives `p1b_put_back_after_ca_reencoded_admitted: true`. The rows are `job-p1b|2|t` and `job-p1b|1|f`.
- Fix: key the realm on a stable configured identifier, or on the front door's home, not on the CA bytes. Or carry the rows over when the CA changes.

== MEDIUM ==
M1. A signed REVOKE whose number has already been seen is answered CONFLICT or STALE, and the revocation is not recorded. RUN (p1c: put-back admitted).
- Where: front_state.py:59-66. The seq tests return before p_revoked is considered.
- It arises when two consoles race (rebind and revoke both from seq N), or when a revoke is signed from a jobs.json that was already put back.
- Fix: a signed REVOKE of any number sets revoked=true. plea_local can already do that (stated), so nothing new is exposed.

M2. The sweep path skips A2's check that a binding's baseline matches its budget, so such a binding still sends designs on. ARGUED.
- Where: front_door.py:803-811 and :853. admit (:434) refuses a binding whose root names another baseline's budget. The sweep has no such check. It reads pending runs on that other budget (`obs = self.store.observe(root)`) and calls `self.submit(b, design)`, which journals and sends `arguments_for(A, design)` on budget B.
- D5's binder at the gate host refuses it after the cross. So no false verdict, but a unit on B is spent and a NO_OUTCOME is left.
- This is D16's "still sent on", now on the sweep path only. F37 tests admit only.

M3. The service's role can switch an existing current-form budget to the 64-bit form, which breaks exactly-once and the record. RUN (p4_flip.out).
- Where: governor.py identity_form (`any(LEGACY_AID...)`).
- plea_local alone (`apply(root, ('RESERVE', 'a-'+16 hex, ...))`) moves a budget holding an `a2-` attempt from `current` to `legacy`. Every later request then gets the 64-bit key and identity. A design decided before is run and charged again, a pending current-form run is orphaned, and the next run with a design mixes forms, so check 5 fails for ever (the H1 effects of the first review).
- The docstring admits only "make a new budget's first attempt" legacy.
- Fix: decide the form by the budget's earliest attempt, and refuse (fail closed) when its attempts are of mixed form. Then state the limit as it really is.

M4. A3 puts controls to check 2's rule but not to `rederive`, the rule every run is put to. D20's first half still holds. RUN (p3_margin.out).
- Setup: a check printing 29 significant digits, far from the limit.
- `control_problems == []`, so make_baseline would baseline it.
- `rederive(control PA66)` gives "the margin does not recompute", so a run of that design is UNKNOWN (verify_tools.py:135).
- My prediction that the PPS run would also fail was wrong: `rederive_run_PPS == []`. I kept the predicate and the output as they are.
- Fix: also require `rederive(card, v, design) == []` for each control in make_baseline (verify_ctl.py:137).

M5. The kept evidence does not show the committed trees passing.
- a4_run1, where R1–R13 and F3–F37 pass, ran before e1f1082's change to front_door.state_name (the F12 fix, which every front-door request goes through).
- Run 2 covered only R14, R17, R18, R25, R26 and F12.
- abe044d changes Governor.attempt for every test (identity_form), and only R30, R31 and R33 were run after it.
- Even so, the commit message and register G5 say "R1 to R13 pass there". ARGUED from the evidence files; I ran no suite.

M6. Parts of R14, R17 and R18 now test test-only code.
- R18's failing check is literally "the first client's answer says so". R14's and R17's "answered … (exit status N)" and "the answers given to the caller" are produced by tests/service_route.py, which is retired code run as a harness.
- The gate-side checks in those tests (outcomes, notices, record) still test the product.
- In the front-door deployment, the only one now supported, R25's keeper and R26's courier/record properties are not shown. Under the front door in a4_run1, R26's `s.record(..., deliveries=True)` did not even return a record.
- Keeping the five is acceptable as gate tests, but these checks should be relabelled or ported. ARGUED.

M7. Retiring F2 drops the only demonstration that a holder of the service's role can still break a record with one design.
- F7 covers the front door only. Nothing in the gateway validates NUL or non-finite values (grep).
- Finding 2 is "closed only at the front door". Its residue for the service's role should stay stated in the register rather than being "carried by F7".
- F1's property is carried by R30 at the gate. ARGUED.

== LOW ==
L1. The gateway MCP server now crashes on a database error instead of answering. RUN (p5_mcp_dberror.out).
- mcp/plea_mcp.py:116 calls identity_form outside call_tool's try, and serve() does not catch it. A DB error or UnknownRoot now ends the process.
- At 1b132e2 the same failure was answered `tool error`.

L2. R33's checks 2 and 3 do not test what their names claim. ARGUED.
- "Not run or charged again" and "finished as the same attempt" check only the exit code and the headline (BAD fails again either way). Check 3 also counts tool calls, but the earlier pending run never called the tool, so that holds either way.
- With the fix removed, only check 4 (3 aids, all legacy) fails.
- The mutants that would show this (amend17_mutants.py) are uncommitted and have not been run.

L3. Stale or wrong text.
- verify/README.md:41 says "every test acts as the assistant through the front door" (false for 5 tests) and "R1 to R32" (R33 exists).
- The docstring of verify_record.request_key says no new run is made under legacy, but now one is.
- Entry 9 gives service_route.py as "exactly as at 1b132e2 (SHA-256 1cbfc5c0…)". That hash is of the edited copy; the original is 5a272be4….

L4. The new R11 check 2 checks file names for "dsn", not file contents. Its check 3 is met by `service_governor` raising UnknownRoot during setup, not by an attempt. The outcome is equivalent.

L5. Housekeeping and smaller exposures.
- verify/demo.py (client_config/submit) and verify/experiment/prepare.py now raise. The README mentions this for experiment only.
- plea_mcp.py with `--tools verify_tools` (made listable by the L1 fix) would still be a route where the assistant holds plea_local. It should refuse or be documented as not a verify route.
- The record table has no bound on p_job, so plea_local can fill it with rows.
- Two front doors that share a CA and one database share job records. That fails closed.
- In a rolling upgrade, any old-code process still running flips budgets (as in M3).

== PROCESS (VP-1 to VP-6) ==
- **F37.** It was changed after two errored runs (the job-name call was rekeyed, entry 4). Neither the earlier test text nor the outputs were kept, and no expectation or file hash was declared before run 3. The author states the lost outputs as a breach. The unkept test edit and the missing VP-5 declaration are not stated.
- **Entry 10.** It declared "R31: 7 of 7" without reading the test, which has 6 checks. This was disclosed in entry 11.
- **Kept and recorded, with SHA256SUMS that verify:** R17's bound (450 → 499), the move of the five tests to service_route, R31's stand-in, and the R32 harness changes.
- **Hashes.** Every declared hash matches the file as run or as committed: 43881a, b7f41f, 1a7fb1, 0fa75b, 3b9ad3, 5e158b, b028a3, 477b44, 36dd6c.
- **r31_run1.** Its SHA256SUMS cites scratchpad paths, not paths in the repo.
- **My own probes.** P3's prediction failed in part (reported in M4; predicate not changed). P6's run 1 output was cut off by the probe's own print. I kept the original, wrote p6_CHANGE.txt and a new expectation, then re-ran; the predicate was unchanged.

== CHECKED AND FOUND SOUND ==
- **SQL hardening.** RUN, by catalog query: SECURITY DEFINER, owner `plea` (not a superuser), `search_path=pg_catalog, pg_temp`, every name schema-qualified, EXECUTE only for plea_local, which has no privilege on the table, no CREATE on public and no role memberships.
- **Concurrency.** RUN (p2_race.out): 30 rounds, each of 20 seq-1 observers racing one seq-2 REVOKE, all ended REVOKED with no errors. The INSERT ON CONFLICT / re-SELECT logic is correct under READ COMMITTED; under REPEATABLE READ it raises rather than mis-answering (ARGUED).
- **Fail-closed paths.** A signature is checked before any write. An unreadable record gives 503. A CONFLICT or STALE binding is never admitted.
- **A3 move.** RUN (p6): check 2's words and verdicts are identical between 1b132e2 and abe044d on the sample record and 8 edits of its controls. make_baseline calls control_problems before signing, storing or provisioning, and both the baseline and the record use this same rule.
- **R1–R9, R12, R13.** Their predicates are textually unchanged. In R10, only the job and record helpers changed.
- **R11.** Checks 1 and 4 are unchanged, and check 5 is equivalent (the same gate path). Check 2's new form (no baseline held; a request carrying one gets 400) is a fair replacement for the client's key pinning.
- **R14's failure through the front door was wording only.** All 14 answers were exit 3, UNKNOWN.
- **identity_form keeps exactly-once** for a budget with pre-change runs, including the pending case. Re-registration keeps the attempt list. Callers outside the service's role cannot choose the form.
- **R31's mixed record** is now real and requires check 5 alone to fail.

== COULD NOT CHECK ==
- Anything end to end (no deployment): M2's spend on the other budget, R33 with the fix removed, the cause of R26's front-door record failure, and full-suite behaviour at e1f1082 and abe044d.
- The uncommitted R34 and mutant runs.
- Any TLS handshake with a CA bundle (H2's TLS half is argued from the README and tls.py).
