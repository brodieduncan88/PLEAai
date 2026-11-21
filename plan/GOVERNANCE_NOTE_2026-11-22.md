# Governance note: verification-process control, 22 November 2026

Branch `plan/plea-prepentest-hardening-2026-11-22`, made from `verification-amendment-15` at `1b132e2`. Planning
documents only. Written by PLEA's internal technical reviewer under the owner's direction. Not independent validation.

## 1. Fixed state at the start of this branch

| Branch | Commit | Standing |
|---|---|---|
| `verification-amendment-15` | `1b132e2` | the last officially declared baseline with passing official runs (29 of 29, 36 of 36); the base of this branch |
| `verification-amendment-16` | `0da1a85e819daac4839e51917402f3fcd67d5caf` | unchanged; the Amendment 16 threat-model design baseline, not an implementation or a declaration |
| `diagnostic-amend16-alarm-2026-11-21` | `d208f6e175376debbd1219a83b8b422b5aafc50a` | unchanged; Amendment 16 is parked. No version 7, no stand-in courier or mailbox, no Step 3 |

Nothing from `0da1a85e` or `d208f6e` is merged into this branch. Two files there are cited, read only, by commit and
path, because the plan needs their definitions:

- `verify/AMEND16_THREAT_MODEL_ADDENDUM_2026-11-21.md` at `0da1a85e`: preconditions DP1 and DP2.
- `verify/DEFECT_REGISTER.md` at `d208f6e`: D1 to D50 (Part A), the owner's release gates G1 to G6, S-1 to S-7, and
  blockers B-1 to B-3. It is still a draft and lives only on the diagnostic branch.

## 2. The rule (the owner's decision of 22 November 2026)

These apply to every agent and to the author, on every branch, for models, tests, acceptance suites, checkers and
verdict code.

- **VP-1.** No one changes model semantics, a verdict predicate, an acceptance criterion or verification code after
  seeing a failed result, unless VP-2 to VP-5 are done first.
- **VP-2.** The exact failing source and configuration are kept: committed, or archived with their SHA-256 recorded in
  a committed file, before any edit.
- **VP-3.** The failing traces and the hashes of the declarations they were judged against are recorded.
- **VP-4.** A readable change record is committed: a diff, or the before and after source together, and why the
  change was made.
- **VP-5.** A new declaration is written and hashed before the check is run again. A result obtained after a change
  never replaces the earlier result; both are reported.
- **VP-6.** An agent's report that does not show VP-2 to VP-5 was done is recorded as a process violation, whatever
  its result.

A delegated agent's brief must quote VP-1 to VP-6.

## 3. Process violation recorded: the version 6 model's SAF-10 change

**What happened.** On 21 November the separate modelling agent ran its bounded model of the Amendment 16
specification, version 6. Its declarations were written and hashed at 22:38:08 UTC. In run 1, SAF-10 came back
violated in two fixed-design configurations declared to hold: `FD_WIPE_BOTHLOST` (15 steps) and
`FD_WIPE_RESTORE_FORK` (16 steps). The agent then changed the predicate by which its model judges SAF-10 (case (b)
of its check) and made run 2, in which those two configurations agree with their declarations.

**What was not kept.**

- The run-1 source of `model.py` is lost. Its hash is recorded in `declared/CODE_AT_DECLARATION.sha256`:
  `03187f4113395a2317322f947d5815ee88507e12d63546446cf696ab678d9466`.
- The run-2 source, hash `b724cb157696b27a178994bcd6f9a6544567d754f1cf0566123c005a6dfb568a`, is the one committed in
  `d208f6e:tests/diag_amend16_spec/model_v6/`.
- No source file with the run-1 hash exists in the working files. Only a compiled cache of the later source remains.
- So the change cannot be read as a diff.
- No new declaration was made before run 2.

**What was kept.**

- Run 1's results and counterexample traces (`results/run1/`).
- The hashed declarations.
- Run 2's results.
- The agent's own description of the change (Part 11 of `verify/STEP3_SPEC_REVIEW_AMEND16_2026-11-21.md`).
- The author's comparison: all 20 searches have the same size in both runs, and only the two SAF-10 properties
  differ.

**Breach.** VP-2 (source not kept), VP-4 (no readable change record) and VP-5 (no new declaration before run 2).

**Consequence.** Run 2 of the version 6 model is not evidence that the fixed design holds SAF-10 in those two
configurations. It shows only that the changed predicate, whose text is the run-2 source, holds there. Run 1's two
violations stand as recorded. The round summary at `d208f6e` already says this. It is not edited; this note adds the
classification.

**Fault.** The author's brief did not forbid changing a predicate after a result. That omission is the author's.

## 4. Other defects found while writing this plan (recorded, not corrected)

- **G-1 (low).** Row D35 of the draft register says "Checked again on `1b132e2`: still so (… `tests/vault_tests.py`
  line 2)". No file `tests/vault_tests.py` exists at `1b132e2`. It is on branch `holdout-vault-demo`. The rest of the
  row was checked again here and holds: `verify/README.md` lines 29 and 40, and `verify/README_FRONT.md` line 116. The
  row is not edited.
- **G-2 (low).** D27 says the gateway release rehearsal "failed at two install steps" but does not name them.
  `GATE_B_LOG.md` at `1b132e2` records a rehearsal whose goal succeeded, with eight frictions. Its own top two
  concern keys: the service's `--key` is undefined, and the gate key's set-up is given out of order, with
  `GateSigner(private_hex)` not documented. The plan (Stage D) takes these two as "the two known installation
  corrections". That is an inference, to be confirmed by the owner.
