# Holdout Vault demo: declaration before the official run

10 November 2026. Private working material.

This file is committed before the official run of `tests/vault_tests.py`. It fixes the code, states what each test
is expected to show, and records what was done during development. The official run is made once, after this commit.
Its first result is kept and reported, pass or fail. Nothing here is changed afterwards; a later correction would be
a separate, dated amendment.

## What is fixed

Base: `main` at `b4503ba` (PLEA gateway v1.2.1). No file under `plea_gateway/`, `mcp/` or `contract/`, and no
existing test file, is changed on this branch. These eight files are new:

| file | sha256 |
| --- | --- |
| `vault/holdout.py` | `db641d6a0b03dbdb72da7c88fb3ff94a9fc284adc4c229a40df89c99d03f9967` |
| `vault/vault_tools.py` | `6c4b22d080c4f00546a5b054392a6fbbb9ee39b9bf28d8c8c348d0237c8a393d` |
| `vault/vault_service.py` | `da5b7a2fb0c074cc7d6fc8a577b39ae486489b4ce29aca8c860f8424416e6019` |
| `vault/vault_ctl.py` | `56b37f459d3706d135554de2d8e04ed9bc74eebdf10215a0c5bea60e0d68678c` |
| `vault/vault_report.py` | `7ae2e6b17e5dfd1872db3402b1062178a962fc8e5165526cee788caef3c79c3d` |
| `vault/plea_verify.py` | `ec4121ac4c55b4bc19ae5ebc273ad5dd750a36d802d4366c713a8ab0346ed9c7` |
| `vault/demo.py` | `dc9c6a748e29520139e860b50abd6f86279d88dc622c51eec07cf38a0a227a86` |
| `tests/vault_tests.py` | `81681c04ed1557596b0be0b4a02b6d28a7d406f38d735c426059791d98f8875d` |

Environment: Python 3.11.17, cryptography 50.0.2, psycopg 3.3.8, PostgreSQL 16.15, OpenSSL 3.0.13, Linux, one
machine, all services on 127.0.0.1.

## What each test is expected to show

Each test builds its own 40-row holdout (classes a, b, c; two decimal places), starts the released witness service
and gate host and the vault's front door under mutual TLS, enrols submitters with `vault_ctl.py`, and acts through
the front door with the submitter's certificate. The independent measure is the scoring tool's own log
(`ledger.jsonl`), which is outside every PLEA store. A test passes only if every check listed for it is true.
A harness or service error counts as a failure.

**V1. A fourth submission is refused.** Budget 3, four different valid files.
The first three answer 200 with outcome EFFECT. The fourth answers 409 `BUDGET_EXHAUSTED`. The tool's log shows 3
calls before and after the fourth request and no line for the fourth file. Status: allowed 3, used 3, refunded 0,
remaining 0. The last audit row is `RESERVE DENIED BUDGET_EXHAUSTED`.

**V2. The same file twice is one attempt.** Both requests answer 200 with the same body, score "0.90" (36 of 40).
Used 1, remaining 2. Labels opened once. Uploading the same file again answers 200 with `stored: false`.

**V3. An invalid file that got past the front door is refunded, within the allowance.** Budget 3, replacement 1.
Two invalid files are placed directly in the upload store. Both answer 200 `NO_EFFECT`. The tool's log gives the
reasons `BAD_CLASS` and `ROW_COUNT`, and the labels are not opened for either. After the first: used 0, refunded 1,
remaining 3. After the second: used 1, refunded 1, remaining 2. A valid file then scores.

**V4. Scoring killed part-way gives UNKNOWN and is never run again.** The gate host is set to die after it opens the
labels. It exits with 137 and the request answers 503. The host is restarted on the same state. The same hash,
asked twice, answers 200 `UNKNOWN`, "no score; attempt used". For that file the tool's log shows called 1, labels
opened 1, scored 0. Used 1. The audit log holds `RECONCILE NOOP VERDICT_UNKNOWN_STAYS_CHARGED`. Another file then
scores, and the report verifies.

**V5. The report verifies offline, and an edited one does not.** A report holding scored, rejected and refused
requests verifies through the library and through the command line (exit 0, "VERIFIED"). Without keys the command
exits 0 and says "CONSISTENT", not "VERIFIED". Every single-value edit of the report fails (more than 200 values).
A wrong report key fails. When each edit is re-signed with the true report key, as an insider holding only that key
could, it verifies only for `as_of.time`, `certificate_sha256` and the `enrolment` fields.

**V6. A submitter's certificate reaches the front door only.** The witness and the gate host answer 403 to it.
Twelve paths outside the six endpoints answer 404. No response holds the labels' salt, a label row, another
submitter's file hash or name. The sealed labels and the report key are mode 0600. An unenrolled certificate from
the same authority gets 403 on five endpoints. A certificate from another authority cannot connect (`UNKNOWN_CA`).
Scoring another submitter's hash answers 404. The report covers the caller's budget only. PostgreSQL refuses a login
under the submitter's name.

**V7. An invalid upload is refused with its code and nothing is counted.** One file per code: `TOO_LARGE`,
`NOT_UTF8`, `BAD_HEADER`, `ROW_COUNT`, `UNKNOWN_ID`, `DUPLICATE_ID`, `BAD_CLASS`. Each answers 400 with that code.
Audit rows 0. Used 0, refunded 0, remaining 3. No file stored, the tool never called. Asking to score a rejected
file's hash answers 404.

**V8. The score is the declared rounding.** Files with 40, 0, 39, 37, 35 and 33 wrong rows score "0.00", "1.00",
"0.02", "0.08", "0.12" and "0.18" (the last four are exact ties, rounded to even). The result holds exactly six
fields; the other five do not depend on the labels. The rounding function agrees with a table of eleven cases.

**V9. A report with one of each outcome verifies.** One attempt killed (UNKNOWN), one scored (EFFECT), one rejected
(NO_EFFECT), one started with the witness down (answers 503; PENDING). The report holds one of each and verifies.
Its as-of sequence number equals its number of audit rows. Allowed 4, used 3, refunded 1, remaining 1.

**V10. Stopped, revoked, expired and replaced credentials are refused.** After the v1.2.1 control plane stops a
budget, a new file answers 409 `STOPPED`, the tool is not called, and the audit log ends `RESERVE DENIED` after a
`STOP APPLIED` row; a hash already scored still returns its stored answer. A revoked submitter gets 403 on the next
request with no restart. A certificate past its expiry, enrolled with its true fingerprint, cannot connect
(`EXPIRED`); the same set-up with a valid certificate is served. After renewal the old certificate gets 403 and the
new one is served.

**V11. Size and upload limits hold.** A file over the size limit answers 400 `TOO_LARGE`. Ten unscored uploads are
held; the eleventh answers 409 `UPLOAD_CAP`. After one is scored, another upload is accepted.

**V12. The request limit holds, per certificate.** With a limit of 20 a minute, 20 requests are served and the next
answer 429 `RATE_LIMIT`. Another submitter is not affected. No audit row is created.

**V13. Racing requests cannot exceed the budget.** Budget 3, six different files requested at once, repeating any
answered `IN_PROGRESS`. Three end EFFECT and three `BUDGET_EXHAUSTED`. The tool's log shows called 3, labels opened
3, scored 3. Used 3, remaining 0. The report verifies.

Expected overall: 13 of 13 pass.

## What was done before this declaration

Stated so the official result can be read for what it is.

- The test file was run six times during development. On first run V1 to V9, V11 and V12 passed. V10 failed once:
  the test counted another submitter's scoring as a call made for the stopped submitter. The test was corrected;
  the vault code was not changed for it.
- One change was made to the vault code because of a development result. The first V5 sweep showed that a report
  re-signed after its `keys` field was edited still verified. `plea_verify.py` now fails a report that names keys
  other than the ones given.
- Added after the first runs: the database login probe in V6, the renewed-certificate check in V10, the reasons
  `UNKNOWN_CA` and `EXPIRED` in V6 and V10, and V13.
- To check the tests can fail, ten deliberate defects were applied one at a time to a scratch copy and the matching
  test run. All ten were caught. Three verifier defects (witness signature skipped, gate signature skipped, result
  not tied to the gate's digest) were caught only by the re-signing sweep in V5. One (scoring without a governed
  attempt) was caught by a harness error in V1, not by a named check.

## What is not tested

- The owner. One operator holds the witness, gate and report keys here; an owner who rewrote the whole record is
  outside these tests.
- An older report presented as current. It verifies, by design; the as-of line is the reader's guard.
- Timing. No measurement was made of whether response time depends on the labels.
- The database as a network target. V6 shows the submitter has no login; whether the port is reachable is a
  deployment matter.
- Restart of the front door. The rate window and the scoring lock are in memory.
- More than one front door for the same holdout.
- Any independent review. Everything here was written and run by the same party.

## Differences from the one-page spec and addendum 1 (revision 2)

- The MCP client is not built.
- The front door checks enrolment and the certificate fingerprint on every request, so revocation and renewal take
  effect at once, with no restart.
- The owner generates the submitter's key and certificate; there is no signing-request flow.
- V12 (rate limit) and V13 (race) are added to the eleven tests the spec named.
- Size: the six vault modules are 1,150 lines against an estimate of about 950. The offline verifier is 315 lines
  against 150.
