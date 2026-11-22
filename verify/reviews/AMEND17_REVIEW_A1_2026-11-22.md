[tier: opus] REVIEW OF d187172 (A1: D5, D21): an internal review by an AI agent at the author's instruction. It is NOT independent validation.

Note: during the review the worktree's HEAD moved to 9efccf0 (A2). I reviewed d187172 only, using a read-only `git archive d187172` copy in `/tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad/review_a1/tree/`. No deployment was started and no port was bound. Probes and their outputs are in `/tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad/review_a1/` (p1_identity, p2_binder_mcp, p3_straddle; .py and .out). Each probe's expectations were written in its header before it ran, and no predicate was changed afterwards (VP-1 to VP-6: no violation to report).

== HIGH ==
H1. The identity change has no migration path. Anything that spans the deployment loses continuity. RUN (p3) for the mechanism; ARGUED end to end.
- governor.py:105-110 and Governor.attempt (governor.py:278-279) now give one request key a different attempt id ('a2-'+256 bits). front_door._submit (front_door.py:670) now computes the 64-hex key. p3 E1: for the same design and baseline, the run before A1 (verify:8694…/a-bb70…) and the run after (a2-903f…) are different attempts.
- Consequences:
  (a) Records stop verifying. Take any baseline with runs whose design was found before A1 (e.g. one past run of a design the journal holds). One further run after A1 makes its record fail check 5 permanently. attempts_of gives both runs their design (p3 E2), so identity_form returns None (p3 E3; check_record.py:401-419, 620-622). The status becomes NOT VERIFIED, even for a genuine pass. The commit's rule "never mixed within one record" turns this into a permanent failure for every live baseline, and nothing refuses new runs on a legacy baseline or tells the engineer to supersede it.
  (b) A repeat is run and charged again. The module claims "sending the same design again is safe… never runs the check twice". For a design sent before A1 and again after, it is false: _delivery (front_door.py:592) matches only the new key, and the governor RESERVEs a fresh attempt. The replacement allowance is 0 (verify_ctl.py:143), so this costs an official run.
  (c) Pending runs are orphaned. The sweep (front_door.py:836-838) finds the legacy PENDING run's design through request_keys and calls submit(). That makes a new a2- attempt and runs the check. The legacy attempt stays PENDING for ever. If the legacy attempt had reached the gate host (host died, or the reply was lost), the design is executed twice. Before A1 the same aid would have been answered with the host's stored or UNKNOWN report.
  (d) The gateway in general loses exactly-once. mcp/plea_mcp.py:51 and every Governor caller are affected. Take a call whose governor died after the host ran it but before the outcome was stored. Retried after the upgrade, it gets a new aid, and the tool runs a second time. This hits the side-effecting tools the gateway exists to govern (e.g. tests/review_tools.py 'charge').
- Fix direction:
  - In Governor.attempt, look for an existing attempt under the legacy aid ('a-'+sha(key)[:16]), under either key form, and resume it.
  - Or require each root to be of one form: keep the legacy forms on a root that already has legacy attempts.
  - Or refuse runs on such roots and state that baselines must be re-issued. Whichever is chosen, add a test that spans the upgrade.

== MEDIUM ==
M1. R31's "a record whose runs mix the two forms fails at check 5" is vacuous. RUN (p1 E2).
- Why: the test (verify_tests.py:3266) rewrites attempts[0].aid of a record with one run. That record cannot hold two forms. Changing the aid already fails check 5 on "the runs listed are not the attempts in the last chained state" and "does not recompute", as well as checks 1, 4 and 6.
- With identity_form neutralised (forced to 'legacy'), check 5 still fails, so the test would pass if the rule were deleted.
- A real mixed record (legacy and current runs in one chained state) is never built. That is exactly the H1(a) case.

M2. R31 cases b and c do not test the fix. ARGUED.
- They patch the width to 4 hex digits whatever width ships. They would pass unchanged with the widening reverted to 24 and 16.
- What they show is the pre-existing property: the governor's nonce turns a collision into RequestKeyReused.
- The parts of R31 that do depend on the fix: case (a) (the regex on aid and key) and case (d) (the front door's design check, which is exercised once _replay is patched out).
- Their checks are labelled "the second design is refused…". They should not be counted as evidence for D21's widening.

M3. A D5 refusal burns a budget unit silently and leaves the attempt unfinishable. ARGUED.
- The refusal comes after the witness's CROSS (gate_host.py:249-261; the governor has already crossed in _run_at_host). The attempt stays CONSUMED with no evidence. outcome_of reads it as PENDING for ever (verify_record.py:117-119), and with allowance 0 the unit is never refunded.
- Nothing about the refusal is signed or noticed. The sweep sees PENDING, finds no design in the journal and skips it, counting acts up to SWEEP_MAX_ASKS after each restart. The engineer sees an unexplained pending run.
- Not a false verdict: a holder of plea_local could already burn budget. But a signed FAIL run notifies the engineer, and this path does not.
- Suggestion: have the host sign a refusal or NO_EFFECT-style report, or record a notice.

== LOW ==
L1. RUN (p2 E2). `GovernedServer(…, verify_tools.TOOLS).list_tools()` raises "ValueError: too many values to unpack (expected 3)" (mcp/plea_mcp.py:100; vanilla_mcp.py:21 has the same unpack). tools/list on plea_mcp started with `--tools verify_tools` in in-process mode would crash the serve loop. In-process mode also never calls the binder (Governor._run_here). That mode needs the gate key, so it is outside D5's threat model, but it should be stated.
L2. ARGUED. verify_client.Client.submit (verify_client.py:97-125), the direct client used by demo.py, has no design_sha256 check like the one at front_door.py:737. Only the front door has the new defence in depth.
L3. RUN (p3 E4). identity_form returns 'current' for a record whose runs are all of the legacy form but have no recoverable design (journal lost, or pending without a result). The summary's 'identities' and render() then mislabel the record. This affects the label only; no check changes.
L4. ARGUED. The sweep adds the legacy request key to _journaled (front_door.py:837). _submit then tests the new key (front_door.py:670-685), so the design is journaled a second time. That breaks "the design found in the journal is not journaled again" and takes a second share of the journal.
L5. ARGUED. R24's row regex now accepts both forms (`a2?-`), so R24 alone would not catch a revert; R31(a) does. The run listings in verify_ctl.py:287 and verify_client.py:152 grow by 49 characters, and the aid an engineer types for `acknowledge` is now 67 characters. This is cosmetic.

== Checked and found sound ==
- D5 binder logic. RUN (p2 E1, 14 cases):
  - True only for root '…/<h[:32]>' with h 64 lowercase hex.
  - '/' in the requirement id works, because rsplit takes the last segment.
  - False for: upper-case h or root, a 32-hex h, missing or non-string h, full-width digits, no '/', a trailing '/', a root carrying the full hash, root None, arguments as a list, and another baseline on the same root.
- D5 ordering. ARGUED.
  - The binder runs after the receipt, admission and nonce checks, so its root and arguments are the ones the witness's ACCEPT_INTENT and CROSS bound. The root is therefore the budget charged.
  - It runs before claim, so a refused attempt has no host row, is not run and is not signed.
  - It is deterministic, so a retry, the interrupted-row path and the repeat path all refuse in the same way.
  - Exceptions refuse.
  - Effect on rows from before A1: only rows made by the D5 attack itself now get 403 on a repeat; honest rows always bind.
- D5 premises. ARGUED.
  - Only the control plane can create roots (store.py:792-801, grants at 862). The single provisioning path uses root_for(card) (verify_ctl.py:143). root_for has been unchanged since it was first written (git log -S).
  - card_hash is the baseline_sha256 (baseline.py:297).
  - A 128-bit suffix needs a second preimage, or two cards signed by the engineer.
  - Without a signing key, I found no way for plea_local plus the front-door certificate to have a design decided against baseline B on A's budget through the gate host. Other tools: the gate host serves only TOOLS['verify'], and an unknown tool gets 400.
- No new denial of service from a legacy-shaped key. ARGUED. A holder of plea_local who runs with key 'verify:<24 hex>' gets its design accepted by the builder, and check 5 then fails. Before A1 the same holder could already fail check 5 with any non-canonical key ("a run with a verdict gives no design", check_record.py:626-628).
- D21 completeness (grep). Nothing outside the legacy branches still computes a 16- or 24-hex attempt identity or request key. The `[:16]` that remain are baseline-hash inbox directories and display prefixes, not attempt identities. Courier, notices, front_ctl and verify_ctl pass the aid through. The INTERRUPTED_<aid> file names stay well under 255 bytes.
- Builder and front door lookups. by_key and _design_for match keys exactly by length, so neither form can be confused with the other.
- The legacy sample record verifies as 'legacy'. RUN (p1 E1).
- Upper-case or hybrid identities read as neither form. RUN (p1 E4).
- The front door's design check. ARGUED: it should not misfire on legitimate repeats. It compares the tool's own design_sha256 string, which survives the jsonb replay, with design_hash of the strictly parsed request. Canonical JSON survives the governor-to-host transport unchanged, and the interrupted path returns before the check.
- R30 depends on the fix (without the binder, B's relaxed limit gives PASS). Its predicates match its claims.
- R31's monkeypatches are restored in finally. Front() starts no thread. The gate host is a separate process and is unaffected. Collision search: meeting() returns None only if no collision is found, and that would fail the checks rather than pass them.

== Could not check ==
- Any end-to-end behaviour: deployments were forbidden. That covers H1(a)-(d), M3, and the R30 and R31 runs themselves.
- The witness's handling of /fence and release for a crossed attempt the binder refused: the host would now fence it, since it has no row.
- Database constraints on aid length: grep found none.
- Interaction with A2 (9efccf0).
- The register's paper claim about a false pass, beyond the code paths above.
