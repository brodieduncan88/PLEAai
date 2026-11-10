# Holdout Vault demo: result of the official run

10 November 2026. Private working material. Internal evidence: written, run and checked by the same party.

## Result

**13 of 13 tests passed, 66 of 66 checks, on the first and only official run.**

The run was made at commit `933d40e`, the commit that holds `DECLARED_VAULT.md`, with no file changed after it.
It started at 00:31:30 UTC on 10 November 2026 and took 50.6 seconds. The full record is
`results/vault_tests_official.json` (sha256 `621c6662…03273e`); the console output is `results/official_run.log`.

| test | what it shows | checks | observed |
| --- | --- | --- | --- |
| V1 | A fourth submission is refused | 5 of 5 | Fourth answer 409 `BUDGET_EXHAUSTED`. Tool called 3 times before and after. Used 3, remaining 0. |
| V2 | The same file twice is one attempt | 4 of 4 | Same score both times. Labels opened once. Used 1. |
| V3 | An invalid file past the front door is refunded, within the allowance | 6 of 6 | Rejected in the tool as `BAD_CLASS`, `ROW_COUNT`. Labels not opened. First refunded, second charged. |
| V4 | Scoring killed part-way gives UNKNOWN, never re-run | 6 of 6 | Host exit 137. Called 1, labels opened 1, scored 0. Stays charged. |
| V5 | The report verifies offline; an edited one fails | 5 of 5 | 1,410 values edited one at a time: none verified. Re-signed with the report key: only `as_of.time`, `certificate_sha256`, `enrolment`. |
| V6 | A submitter's certificate reaches the front door only | 9 of 9 | Witness and gate host 403. Twelve other paths 404. Other authority: `UNKNOWN_CA`. Database login refused. |
| V7 | An invalid upload is refused and nothing is counted | 4 of 4 | Seven codes, each returned. Audit rows 0. Nothing stored. |
| V8 | The score is the declared rounding | 4 of 4 | 0.00, 1.00, and the four ties 0.02, 0.08, 0.12, 0.18. |
| V9 | A report with one of each outcome verifies | 5 of 5 | EFFECT, NO_EFFECT, PENDING, UNKNOWN. As-of 32 = 32 audit rows. Used 3, refunded 1. |
| V10 | Stopped, revoked, expired and replaced credentials are refused | 7 of 7 | 409 `STOPPED`, tool not called. Revoked 403 at once. Expired: `CERTIFICATE_EXPIRED`. Old certificate 403 after renewal. |
| V11 | Size and upload limits hold | 4 of 4 | `TOO_LARGE`. Eleventh upload 409 `UPLOAD_CAP`. |
| V12 | The request limit holds, per certificate | 4 of 4 | Requests 21 and 22 answer 429. Other submitter served. |
| V13 | Racing requests cannot exceed the budget | 3 of 3 | Six at once, budget 3: three scored, three refused. Labels opened 3 times. |

Every outcome matches the declaration. There were no failures to explain and no re-runs.

## The demonstration

`sample/demo_transcript.txt` is one run of `demo.py`, made after the official run. A submitter with three attempts
sends four files. Three are scored (0.65, 0.74, 0.80), the fourth is refused, and the scoring tool's own log shows
the labels were opened three times. The signed report verifies offline against three public keys. A copy with one
score raised from 0.80 to 0.90 fails two checks: the report signature, and the result no longer matching what the
gate host signed.

`sample/report.json`, `sample/keys.json` and `sample/report_edited.json` are those files. They hold public keys,
hashes and signatures only. Anyone with Python and the `cryptography` package can repeat the check:

```
python vault/plea_verify.py vault/sample/report.json --keys vault/sample/keys.json
```

## How to read this result

- **It is a first internal result.** The tests were written by the same party as the code, and were run six times
  in development before the declaration. `DECLARED_VAULT.md` lists what changed during that time. The declaration
  shows the official run was not adjusted afterwards; it does not make the tests independent.
- **V13 was decided by the front door, not by the contract.** In the first round one request ran and five were told
  `IN_PROGRESS`, so the front door's own lock put the requests in a line. The database's guard against racing
  admissions was not exercised here; the v1.2.1 release tests cover it (G01).
- **V6's database check is narrow.** It shows PostgreSQL has no login for the submitter. It does not show the
  database is unreachable from a submitter's network.
- **The tests can fail.** Ten deliberate defects were each caught in development. Three verifier defects were caught
  only by V5's re-signing sweep, which makes that sweep the check to keep if the verifier changes.
- **The limits in the README stand.** The owner is trusted, a report is a snapshot, timing was not measured, and
  nobody outside has reviewed or attacked this.

## What is on the branch

New files only. `git diff main --stat` shows additions under `vault/` and `tests/vault_tests.py`; no v1.2.1 file is
touched, so the release archive and its hashes are unaffected.

| | lines |
| --- | --- |
| Six vault modules | 1,150 (estimate was about 950) |
| `demo.py` | 140 |
| `tests/vault_tests.py` | 642 |

## Not done

The MCP client, a signing-request flow for submitter keys, hardening, deployment packaging, and any external test.
