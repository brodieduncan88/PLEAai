# Defect register entries from Amendment 16's diagnostics (for entry in the permanent PLEA defect register)

21 November 2026. Private working material. Internal work under the owner's direction. It is not an independent
validation and not a declaration. Nothing is repaired by it. The frozen gateway is unchanged.

**Where the permanent register is.** It is not a file in this repository. The last issued register that can be found is
the one in the review pack of 15 November 2026, which holds D1 to D33 and was built outside the repository. The property
file of Amendment 16 speaks of D46 to D50 "in the defect register"; no register file holding D34 to D50 was found on any
branch or in the working files. These entries are therefore written here, in register form, so that nothing is lost,
and are to be carried into the permanent register wherever the owner designates it. That needs a separate commit, or a
reissue of the register outside the repository: this file does not make it.

**What does not change.** `e25a297`, the eighth form of the courier, is and stays INCOMPLETE, rejected at internal review
and undeclared. Its findings are not rewritten or erased. `verification-amendment-16` stays at `0da1a85e`, the accepted
threat-model design baseline (`verify/AMEND16_THREAT_MODEL_ADDENDUM_2026-11-21.md`), which is not an implementation or a
security declaration.

Evidence is on the branch `diagnostic-amend16-alarm-2026-11-21`. Every test named ran from a copy of the tree at
`e25a297`, on real deployments started by `verify/deploy.py` over databases made fresh for the purpose, unless said
otherwise. All of it is the work of the code's own side; no planted-defect pass was made on the harnesses.

## Part 1. Substrate, deployment and gateway-adjacent findings (separate from the courier's eight)

### S-1. Silent replacement of a verdict by a second gate-signed digest

- **What happens.** After the gate host has signed FAIL for a run and the witness has recorded that report, the service
  can withhold the result (or store one marked 'unknown'), have a second report recorded for the same run over a PASS
  result, and store the PASS. The witness records the second report as a duplicate decision with its report. The
  courier and the record's checker believe a stored result that matches any recorded digest. No notice is made, and the
  record verifies.
- **Where.** `plea_gateway/witness.py` 79-87 and `plea_gateway/store.py` 400-401, 773-788, 837-838 (frozen gateway);
  `verify/check_record.py` 188-203 (the courier and the checker).
- **Evidence.** `verify/DIAGNOSTIC_AMEND16_POWERS_2026-11-21.md` section 3 (steps 3, 3b, 3c of
  `tests/diag_amend16_powers/commit_check.py`); `verify/DIAGNOSTIC_AMEND16_VISIBILITY_2026-11-21.md` (V1 to V5).
  Commits `1313dc9`, `1fc9046`.
- **Reproduction conditions.** The service holds the gate's key, the client's certificate and the database role
  `plea_local` (all three are in the locked table of powers). The run's result has not yet been stored as a value. With
  the courier's default waiting time, the replacement is made before that time has passed. Reproduce with
  `DIAG_DB=<fresh database> python tests/diag_amend16_powers/commit_check.py SRC OUT`, steps 3 to 3c, and
  `visibility_check.py`, V1 to V3.
- **What limits it.** A FAIL already stored as a value stays (by test). Both reports stay readable through the witness's
  existing reading, so the conflict can be detected without a change to the gateway; nothing detects it at `e25a297`.
  Detection shows that two results were signed, not which is true.
- **Affected trust boundaries.** Service to witness (what the witness records for a run); witness to courier and witness
  to record (what a reader concludes from the reports); gate-key custody.
- **Standing.** Open. An unmet requirement of Amendment 16 (UM6 b). It is the one finding of these diagnostics that
  turns a signed FAIL into silence.
- **Remediation status.** None made. Detection is specified in the Step 2 design note and is not implemented. The
  frozen gateway stays unchanged by the owner's decision, so refusing a second report at the witness is not in hand.

### S-2. Plaintext database role passwords

- **What happens.** The passwords of all four database roles, the owner's included, are literal text in the
  repository. Which role a party holds is a matter of which line of configuration it uses, not of what it can do.
- **Where.** 23 places listed in `tests/diag_amend16_powers/results_2026-11-21/roles.txt` (among them `README.md`,
  `verify/deploy.py`, `verify/verify_ctl.py`, `tests/common.py`).
- **Evidence.** `verify/DIAGNOSTIC_AMEND16_POWERS_2026-11-21.md` section 1; the schema of every diagnostic database was
  installed with the owner's password from the README; with it a recorded gate report was deleted
  (`visibility_check.py`, V7).
- **Reproduction conditions.** Read access to the repository and network access to the database server. No other
  condition.
- **Affected trust boundaries.** Service to database owner; service to witness (the witness's role); every boundary
  the database's grants are meant to keep.
- **Standing.** Open. **A deployment-security blocker**, by the owner's decision of 21 November: it must be resolved
  before any claim that a deployment complies. Precondition DP1 of the addendum is not satisfied. It is an outstanding
  security defect, not an acceptable implementation of credential separation.
- **Remediation status.** None made. Tracked outside the Step 2 task. No credential or deployment configuration is
  edited here.

### S-3. Connection exhaustion affecting the witness

- **What happens.** No database role has a connection limit, and the server has no statement or idle timeout. The
  service's role took every free connection (97 of 100), after which every reading of the witness failed and the
  courier was blocked, for as long as the connections were held.
- **Where.** Database server configuration and role settings (`roles.txt`, sections 1 and 3).
- **Evidence.** `verify/DIAGNOSTIC_AMEND16_POWERS_2026-11-21.md` section 4 (step 6a of `commit_check.py`). Commit
  `1313dc9`.
- **Reproduction conditions.** The role `plea_local` and network access to the database server shared with the witness.
- **Affected trust boundaries.** Service to witness, through the shared database server (availability).
- **Standing.** Open, as an operational risk (residual risk R1 of the addendum). It can keep a budget from being read;
  it cannot make an unread budget look read.
- **Remediation status.** None made. Not prevented; carried as a residual risk.

### S-4. Quadratic growth of a chain read from its start

- **What happens.** Every decision the witness gives carries the state of every run of its budget, so a decision grew
  from 3.8 KB to 127 KB over 996 runs, and the whole chain of that budget was 508 MB (126 pages, 37 s). A courier that
  is new, or has lost its state, pays this; the time a pass has for asking does not bound it.
- **Where.** The store's record of a decision (frozen gateway); the witness's GET /chain.
- **Evidence.** `verify/DIAGNOSTIC_AMEND16_POWERS_2026-11-21.md` section 6 (`measure2.py chain`). Commit `1313dc9`.
- **Reproduction conditions.** A budget of about 1000 runs made through the client; read with
  `measure2.py chain SRC OUT ROOT`.
- **Affected trust boundaries.** Witness to courier (the cost of the first reading; recovery after loss of the
  courier's state).
- **Standing.** Open, as an operational risk and a stated limitation of the measured envelope.
- **Remediation status.** None made. A change would touch the frozen gateway.

## Part 2. Deployment-security blockers

By the owner's decision of 21 November these must be resolved before any claim that a deployment complies. They are
tracked here and outside the Step 2 task. Nothing is edited for them now.

| Blocker | What is so today | Evidence |
|---|---|---|
| B-1. Database credentials exposed (S-2) | every role's password is in the repository | `roles.txt`; V7 |
| B-2. No separation of operating-system accounts | one account runs the witness, the gate host, the mailbox, the courier and the client; that account stopped and continued the witness | `verify/deploy.py` 11-16; step 6b of `commit_check.py` |
| B-3. Custody of the gate's key | the property file takes the service to hold the gate's key; with it a report can be forged before the witness sees anything, which nothing in the notification path can detect | property file line 21; V5 |

## Part 3. The eight confirmed defects of the courier at `e25a297` (kept as they are)

`e25a297` is INCOMPLETE, rejected at internal review and undeclared. These eight are recorded in section 9.1 of
`verify/AMEND16_THREAT_MODEL_ADDENDUM_2026-11-21.md` at `0da1a85e` and are not restated differently here.

| Id | In short | Standing |
|---|---|---|
| D-a | the alarm's count is cleared by a pass that put runs off; no alarm in the test of 4500 s | open |
| D-b | false provenance sentence ("from what the witness gave it, read to decision 0"); a current breach of P5 | open |
| D-c | four notices carry a headline with no explanation; the UNVERIFIED headline was signed false of its run; a current breach of P5 | open |
| D-d | the statement of coverage is made with runs asked for and not read, and promises the future | open |
| D-e | one clock value for a whole pass over all budgets | open |
| D-f | "complete" has several meanings | open |
| D-g | an older failed run not noticed while the witness stops at a new run in every pass | open |
| D-h | a run that never reaches a final phase is asked for at every pass for ever (cost) | open |

Reported by the eighth internal review and not re-confirmed: F1, F2, F4, F5. Their disposition against the Step 2 model
is in the Step 2 design note.
