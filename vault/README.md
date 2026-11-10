# PLEA Holdout Vault: demo

10 November 2026. Private working material. Branch `holdout-vault-demo`; not merged, not released.

A benchmark owner seals a holdout's labels in the vault. A model builder sends predictions and gets back one number,
the accuracy, and may do that a fixed number of times. Every attempt is counted by the PLEA gateway (v1.2.1, used
here unchanged), and the owner can hand anyone a signed report of exactly how many attempts were used and what each
scored, which that person can check offline.

This is a demonstration built to show the idea working end to end. It is internal evidence: nobody outside has
reviewed or attacked it.

## Try it

**Check a real report, no setup.** Needs Python 3.11 and `pip install cryptography`.

```
python vault/plea_verify.py vault/sample/report.json --keys vault/sample/keys.json          # VERIFIED
python vault/plea_verify.py vault/sample/report_edited.json --keys vault/sample/keys.json   # FAILED (one score was raised)
```

`vault/sample/demo_transcript.txt` is the run that produced them.

**Run the whole thing.** Needs PostgreSQL 16 with the PLEA schema and roles (top-level `README.md`, "Reproduce").

```
python vault/demo.py                  # three scored, a fourth refused, the report verified, an edited copy rejected
cd tests && python vault_tests.py     # the thirteen declared tests, about a minute
```

## The pieces

| file | what it does | lines |
| --- | --- | --- |
| `holdout.py` | The holdout: public manifest, public id list, sealed labels. The submission rules and the rounding rule. | 187 |
| `vault_tools.py` | The one tool the gate host runs: `score`. Re-checks the file from public information, then opens the labels. | 79 |
| `vault_service.py` | The front door, the only service a submitter reaches. Upload, score, status, report. Mutual TLS. | 349 |
| `vault_ctl.py` | The owner's console: enrol, renew, revoke, close. | 116 |
| `vault_report.py` | Builds and signs the attempt report. | 104 |
| `plea_verify.py` | Checks a report offline. Stands alone: standard library and `cryptography` only. | 315 |
| `demo.py` | The demonstration above. | 140 |
| `../tests/vault_tests.py` | Tests V1 to V13. | 642 |

No file of the v1.2.1 gateway is changed. The witness service and the gate host run exactly as released; the
governor runs inside the front door with the gateway's ordinary database credential.

## How an attempt works

1. The submitter uploads a predictions file. The front door checks it against public information only (size, UTF-8,
   header, row count, every id once, known classes). An invalid file is refused with a code. Nothing is counted.
2. The submitter asks for a score by the file's hash. The front door runs one governed attempt on that submitter's
   own budget, `HOLDOUT/SUBMITTER`: the witness admits it or refuses it, and only then does the gate host run `score`.
3. The gate host signs the result: six fields, of which only the score depends on the labels. With two decimal
   places a score is one of 101 values, so one attempt can reveal at most 6.7 bits about the labels.
4. Asking again for the same hash returns the stored result and is not counted again.
5. When the budget is used, the witness refuses the next attempt and the scoring tool is not run.

## What it does not do

- **The owner is trusted.** In this demo one operator holds the witness, gate and report keys. An owner who rewrote
  the whole record could produce a report that verifies. The report protects a reader against the submitter, and
  against a single edited field, not against the owner.
- **A report is a snapshot.** It is true as of its sequence number. An older report omits later attempts and still
  verifies. Get the report from the owner and read the as-of line.
- **It counts what goes through it.** Labels that exist anywhere else are outside it.
- **One certificate is one budget.** Tying a certificate to a real organisation is the owner's job. Someone given two
  names has two budgets.
- **The owner creates the submitter's key** and hands it over. A production version would take a signing request so
  the owner never sees it.
- **Not hardened.** The rate limit and the one-scoring-at-a-time lock live in the front door's memory; restarting it
  resets the rate window. Timing was not measured. Closing a holdout deletes uploads in the ordinary way.
- **Not built yet:** a client for MCP, and any deployment packaging.

`DECLARED_VAULT.md` states what each test was expected to show, written before the official run.
`REPORT_VAULT.md` gives the result.
