# Amendment 1 — 10 November 2026

Private working material. This is a dated amendment made **after** the frozen declaration (`DECLARED_VAULT.md`) and
the official V1–V13 run (`REPORT_VAULT.md`, `results/vault_tests_official.json`). Those two records are left exactly
as they were. This note adds one fix and one test on top of them, and says plainly what changed and why.

## Why

An independent static review of the demo was run by another party (code and sample artifacts only; no live services).
It found no critical or high issue and confirmed the disclosed residual risks. While checking its "no unbounded body"
observation, I found a robustness bug the static pass had not reached, because triggering it needs a malformed header
rather than an honest oversize body.

## The finding

**Front door: a negative `Content-Length` bypassed the size caps (low/medium robustness, denial-of-service only).**

In `vault_service.py` the body length was parsed and then compared against the limit:

```
length = int(self.headers.get('Content-Length', ''))   # a negative number parses fine
...
if length > limit:           # -1 > 20 MB is False, so the cap is skipped
    ... drain and refuse ...
return self._send(*vault.upload(name, self.rfile.read(length)))   # read(-1) reads to EOF
```

A caller sending `Content-Length: -1` and then a long stream reached `self.rfile.read(-1)`, which reads until the
connection closes — past the `TOO_LARGE` cap on `/upload` and past the 4 KB cap on `/score`. It could not exceed a
budget, obtain labels, or forge a report; the cost is memory and a held connection. It never created an attempt or
called the scoring tool, because the fault is in the HTTP handler, before the governor.

## The fix

One guard, right after the length is parsed, for both endpoints:

```
if length < 0:
    self.close_connection = True
    return self._send(400, {'refused': 'BAD_REQUEST'})
```

## The test

**V14** (new): one request with `Content-Length: -1` to `/upload` and to `/score`, each with a small body, plus one
with a non-numeric length. Expected: 400, 400 and 411; no audit row and no scoring-tool call from any of them; a
well-formed request still scores. Confirmed to fail without the guard (the two negative requests hang to the client
timeout) and pass with it.

## Result

The full suite, V1 to V14, was run once after the fix at 2026-11-10T10:57:45Z:
**14 of 14 passed.** The record is `results/vault_tests_amended_2026-11-10.json`.

## Changed files, after this amendment

| file | sha256 |
| --- | --- |
| `vault/vault_service.py` | `7a65596bac43014d056f6231bac465bdaf1d9294be0e0ad043b75607358c20e4` |
| `tests/vault_tests.py` | `effec39161639cfa62ec74a141d2c513f0728fb970ad4813d4e8f2ad980c3e74` |

No other file changed. The v1.2.1 gateway, the declaration and the official V1–V13 result file are untouched.

## Still open (unchanged by this amendment)

The review's own recommendations stand and are not done here: move the rate-limit and scoring-lock state out of
process memory (or rely only on the contract), add a signing-request flow so the owner never sees a submitter's
private key, and obtain an external review of the verifier and the contract integration. The trusted-owner and
snapshot-report limits are by design.
