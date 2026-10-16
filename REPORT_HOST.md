# PLEA gateway v0.4: the gate host holds the only gate key

12 October 2026 · follows the v0.3 report · private working material, not for publication

## Summary

**Headline.** The caller's process now holds no key at all. A separate gate host holds the gate's key, runs each attempt's tool exactly once, and signs the fence and effect reports; the governor carries receipts in and reports out. The v0.2 limit, "the governor is the gate", is closed. Key lists are pinned on both sides, so witness and gate keys can be rotated without a gap. Three of the five check groups failed on the declared run because the test fixture pointed the host's ledger at the wrong file; the host itself behaved correctly. After one labelled amendment to the fixture, all 32 checks pass.

| check | declared | result |
| --- | --- | --- |
| H1 the host runs nothing without the witness's word | 5 refusals, ledger unchanged, then the genuine receipt runs | **7/7 ok** on the re-run; declared run 6/7, fixture fault (amendment 1) |
| H2 one-shot at the host | repeat on retry, repeat with other arguments, 1 execution from 8 concurrent requests, repeat after restart | **5/5 ok** on the re-run; declared run 0/5, fixture fault (amendment 1) |
| H3 fence and run exclude each other | fenced cannot run, ran cannot be fenced, a never-started reservation is released, accepted consumption is not | **7/7 ok** (declared run) |
| H4 no gate key in the governor: API and MCP in host mode | 4 roots E3-style, gov.gate is None; MCP retry runs once | **5/5 ok** on the re-run; declared run 3/5, fixture fault (amendment 1) |
| H5 key rotation, witness and gate | old receipts accepted during overlap and refused after; old gate reports NONE after | **8/8 ok** (declared run) |
| re-runs on the new schema: E1–E3, W1–W4, M1–M3, conformance, chaos, G02b, G01 (300) | all pass | **all pass**, declared run; conformance 34/34, chaos 90/90, G02b 200/200, G01 300/300 |

What this does not close: transport security (loopback HTTP without TLS; the signed receipts and reports detect tampering but requests are not authenticated), and the fence report's operational truth (the host says FENCED\_NO\_START because it recorded the fence; making that true of a real sandbox is the fence's job).

## 0. Gate B, by proxy

The plan's Gate B says: an engineer who has never seen PLEA governs a tool call in under 30 minutes, from the quickstart alone. No such person was available, so the proxy was an agent with no prior knowledge of the project, confined to the v0.3 bundle directory, told to work from the README only, timed, and asked for a friction log. The full log is `GATE_B_LOG.md`.

**Result: succeeded in about 4 minutes** (09:31:36 to 09:35:39 UTC), through the README's Python route: schema installed from the one-liner, the witness service started, a governed call made twice with the function executing once, confirmed by its own counter and by a fresh process seeing the stored result. The bundle was left unmodified.

**The friction it found, all in the README and one in the code:**

1. `--key` for the witness service was shown but never defined: no format, no way to make one, no statement that an omitted key is generated per run and changes on restart. Nor what `RemoteWitness(url)` without a public key does (trust on first use).
2. The gate-key lifecycle was presented backwards: the snippet began with `GateSigner()`, a fresh key the service had not pinned. The stranger discovered `GateSigner(private_hex=…)`, `.private_hex` and `.public_hex` by introspection.
3. No expected output for the two-call demonstration, and no statement that `attempt` returns the function's value, that the retry returns the stored value, or that root creation is idempotent. The schema one-liner assumed the working directory, wrote caches into the package, and printed nothing.
4. `plea_ctl audit` printed one row. That was a bug: the `return` sat inside the loop. Fixed in v0.4.
5. The reproduce section's last line pointed outside the bundle. The vectors runner is now in the bundle.

All five are addressed in the v0.4 README, which now gives the three-step order, the key lifecycle with the commands to make keys, the expected output, and a host-mode section.

**What this proxy does and does not show.** An agent of the same family as the author is a stronger reader than a typical engineer and a weaker test of a human's patience. Four minutes is not evidence that a person takes four minutes. The friction list is the useful output, and it is the kind a person would also hit. Gate B with a person remains to be done.

## 1. What was built

**The gate host (`gate_host.py`).** A small service that holds the gate key, pins the witness's public key(s), and loads the tools.

- `POST /run` takes the attempt, its nonce, the witness's intent receipt, the tool and its arguments. It verifies the receipt against the pinned witness keys with the gate's rule (APPLIED or DUPLICATE); then it claims the attempt in its own SQLite state and runs the tool once. A second `/run` for the same attempt, from anywhere, with any arguments, returns the stored result and the same signed report with `repeat: true`. A concurrent duplicate is refused while the first is running. The verdict is EFFECT on return, NO\_EFFECT when the tool raises `NoEffect`, UNKNOWN on any other exception.
- `POST /fence` takes the reservation receipt, fences the attempt (it can never run on this host), and returns a signed fence report. An attempt that ran cannot be fenced; a fenced attempt cannot run.
- The host's state file is its own record of what ran or was fenced. The accounting of record is still the witness's store.

**The governor in host mode (`governor.py`).** `Governor(..., host=GateHostClient(url))` holds no `GateSigner`. `attempt(key, tool_name, **arguments)` runs the contract's lifecycle, stores both receipts (reservation and intent, keyed by operation now), applies RECEIPT behind the verified intent receipt, sends the receipt to the host, applies CROSS when the host reports the crossing, and passes the host's signed report to the witness. `release(aid)` sends the reservation receipt to the host and the host's fence report to the witness. In-process mode (`gate=`) remains for v0.2's tests.

**Pinned key lists (`receipts.py`, `witness.py`).** Every verifier accepts a key or a list of keys, so a rotation is: pin old and new, rotate, drop old. The receipt's `signer` field selects the key.

**The MCP server (`plea_mcp.py --gate-host URL`).** In host mode the tool list comes from the host and every call goes to it through the governor; the server process holds no key either.

## 2. Declaration

`DECLARED_HOST.txt`, recorded at 09:39:38 UTC, holds the sha256 of every file and the expected result of every check. Two development smokes preceded it and are named in it. The v0.3 outputs are kept under `outputs/v0_3/`. Because the receipts table gained an `op` column, the whole chain was run on a fresh database. One amendment followed the declared run and is labelled in the same file; section 3 reports both runs.

## 3. Results

The declared run of `h_tests.py` (14.6 s) failed H1, H2 and H4; H3 and H5 passed; every earlier test passed. The failing checks were every check that counts lines in the host's ledger. The cause was in the test fixture, not the host: the chain exported `PLEA_LEDGER` for the MCP tests, the `GateHost` fixture inherited it, and the host wrote its ledger to `mcp_ledger.jsonl` while the test counted `host_ledger.jsonl`, which never existed. The host's lines are in `mcp_ledger.jsonl`. The H2 burst in the declared output shows the host's own behaviour was already right: one `ran`, seven `repeat` (one request arrived while the first was still running and was refused with 409, as designed). Amendment 1, recorded in `DECLARED_HOST.txt` at 09:48:56 UTC with the expected re-run result, makes the fixture pass an explicit ledger path. The declared output is kept in `outputs/declared_h/`. The re-run (13.9 s) gave 32 of 32. Both are reported here.

### 3.1 H1: the host runs nothing without the witness's word

Five bad credentials at `/run` for one attempt, then the genuine receipt. 7 of 7 on the re-run (declared run: 6 of 7, the last check counting the ledger).

| check | result |
| --- | --- |
| no receipt (400) | ok |
| receipt signed by an unknown key (403) | ok |
| reservation receipt where an intent receipt is required (403) | ok |
| another attempt's genuine intent receipt (403) | ok |
| kind edited on a copy of the genuine receipt (403) | ok |
| ledger unchanged by the refusals | ok |
| the genuine receipt then runs, once | ok |

No receipt was a 400. A receipt signed by a key the host does not pin, a reservation receipt where an intent receipt is required, another attempt's genuine intent receipt, and a copy of the genuine receipt with its kind edited were each a 403 and the ledger did not change. The genuine receipt then ran the tool, once.

### 3.2 H2: one-shot at the host

5 of 5 on the re-run (declared run: 0 of 5, every check counting the ledger).

| check | result |
| --- | --- |
| first run executes | ok |
| same run again is a repeat with the same report | ok |
| a retry with other arguments is still the first result | ok |
| eight concurrent runs: exactly one execution | ok |
| after a host restart the run is still a repeat | ok |

The first run executed and the host signed its effect report. The same request again returned the stored result and the same report with `repeat: true`. A retry carrying other arguments still got the first result. Eight concurrent requests for the same attempt gave exactly one execution: the burst read `ran, repeat, repeat, repeat, repeat, repeat, repeat, repeat`. The host was stopped and restarted on the same state file and the run was still a repeat.

### 3.3 H3: fence and run exclude each other

7 of 7 (declared run).

| check | result |
| --- | --- |
| fence at the host returns a signed fence report | ok |
| fenced attempt cannot run (409) | ok |
| the witness denies releasing an attempt whose intent it accepted (5.8/4) | ok |
| a fence report for a reservation that never started releases it | ok |
| a3 runs | ok |
| an attempt that ran cannot be fenced (409) | ok |
| replay lockstep | ok |

An attempt fenced at the host returned a signed fence report and could not then run (409). The witness denied releasing that attempt, because it had accepted its intent (contract 5.8/4): a fence report never releases accepted consumption. A reservation that never started was released on its fence report (APPLIED, BOUND\_FENCE). An attempt that ran could not be fenced (409). The store's audit log replayed through the oracle.

### 3.4 H4: no gate key in the governor

5 of 5 on the re-run (declared run: 3 of 5, the two MCP checks counting the ledger).

| check | result |
| --- | --- |
| four roots through the API in host mode | ok |
| MCP host mode lists the host's tools | ok |
| MCP host mode: a retried charge runs once | ok |
| MCP host mode: beyond the budget is refused and never runs | ok |
| MCP root replay lockstep | ok |

Four roots ran E3's lifecycle through the API in host mode: each 4 ran, 1 no-effect, 1 denied, credit 1, phases EFFECT, EFFECT, EFFECT, NO\_EFFECT, every reconcile labelled AUTHORISED, and `gov.gate` was `None` in every governor. The accounting is the same as v0.2's. Through MCP with `--gate-host`, the server listed the host's tools, a retried charge ran once, and a charge beyond the budget was refused and never reached the host.

### 3.5 H5: key rotation, witness and gate

8 of 8 (declared run).

| check | result |
| --- | --- |
| client pinning [old, new] accepts receipts under the new key | ok |
| host pinning [old, new] runs on receipts under either witness key | ok |
| witness pinning [old gate, new gate] accepts the old host's report | ok |
| host pinning only the new witness key refuses an old receipt (403) | ok |
| a host with fresh state runs a3 again: one-shot state is per host, a stated limit | ok |
| witness accepts the new host's report | ok |
| witness pinning only the new gate key derives NONE for the old host's report | ok |
| replay lockstep | ok |

Witness rotation: a client pinning the old and new keys accepted receipts under the new key; a host pinning both ran on receipts under either; a host pinning only the new key refused an old receipt (403). Gate rotation: a witness pinning the old and new gate keys accepted the old host's report; a second host with the new gate key and fresh state ran a3 again, which is the stated limit that one-shot state is per host; the witness accepted the new host's report; a witness pinning only the new gate key derived NONE for the old host's report and denied it. The audit log replayed through the oracle.

### 3.6 Re-runs on the new schema

Because the receipts table changed shape, the whole chain was declared and run again on a fresh database, after the H tests. All passed.

| test | result | time |
| --- | --- | --- |
| E1 release evidence | 8/8, lockstep | 2.1 s |
| E2 reconcile evidence | 8/8, lockstep | 2.2 s |
| E3 lifecycle evidence, 6 roots | PASS | 10.0 s |
| W1 authority boundary | PASS | 4.2 s |
| W2 receipts | PASS, lockstep | 0.9 s |
| W3 service lockstep | PASS | 59.2 s |
| W4 service crash, 18 points | 18/18 | 21.1 s |
| M1–M3 MCP | 28/28 | 6.0 s |
| conformance, 34 vector groups | 34/34 | 33.7 s |
| chaos | 90/90 | 67.9 s |
| G02b | 200/200 | 92.7 s |
| G01 lock, 16 workers | 300/300 | 188.8 s |

The v0.3 outputs stay under `outputs/v0_3/` for comparison; these are under `outputs/`.

## 4. What this shows, and what it does not

**Shows.**

- Nothing runs at the host without the witness's signed acceptance of this attempt's intent. Not a missing receipt, not a stranger's signature, not a reservation receipt, not a sibling's receipt.
- The host runs an attempt once. Retries, retries with other arguments, concurrent duplicates and a host restart all get the first result and the first report.
- A fence and a run exclude each other at the host, and the contract still decides what a fence report may release: never accepted consumption.
- The caller's process holds no key, through the API and through MCP, and the accounting is identical to v0.2's.
- Both keys rotate with an overlap window and a clean cut-off.

**Does not show.**

- Transport security: no TLS, no request authentication. A tampered response is detected by the signatures; a request is not authenticated.
- The host's state survives its restart, but a lost state file would let an attempt run again at that host; the witness's accounting would still show the attempt as consumed and would refuse a second verdict. State durability is the deployment's concern.
- Real sandboxes. The host runs Python functions; fencing a real sandbox is G04's territory.

## 5. Next

1. **Transport:** TLS, or mutual authentication, between governor, witness service and gate host.
2. **The design-partner framework integration.**
3. **A throughput measurement** with connection pooling.

## 6. Files and hashes

| file | sha256 (first 16 hex digits) | role |
| --- | --- | --- |
| `plea_gateway/__init__.py` | `8694a538e92639ef…` | package |
| `plea_gateway/evidence.py` | `41f6a14b7a5c21b0…` | reports and derivation |
| `plea_gateway/faults.py` | `67c9ac8f872d31b5…` | crash points |
| `plea_gateway/gate_host.py` | `4b35e95aafeec7c1…` | the gate host and its client (v0.4) |
| `plea_gateway/governor.py` | `b04868e5dde64780…` | SDK surface; host mode holds no key |
| `plea_gateway/plea_budget_ref.py` | `a367a4bbc2ca21b4…` | the verified reference, unchanged |
| `plea_gateway/receipts.py` | `b1a58566bbae8cf6…` | receipts; pinned key lists |
| `plea_gateway/store.py` | `f006c7646ba59182…` | the store; receipts keyed by operation |
| `plea_gateway/witness.py` | `fbd39b39938719c4…` | witnesses; client pins a key list |
| `plea_gateway/witness_service.py` | `0ce82b8d848746fc…` | the witness service |
| `mcp/demo_tools.py` | `7f672232e9988fb1…` | demonstration tools |
| `mcp/plea_ctl.py` | `a8974537035ea014…` | operator control (audit fixed) |
| `mcp/plea_mcp.py` | `5e3fcfad6e5f9c68…` | governed MCP server; --gate-host |
| `mcp/vanilla_mcp.py` | `3b574ba659f905a8…` | ungoverned control case |
| `tests/apply_once.py` | `18a47ba1a8fc9379…` | earlier test, unchanged except where the API changed |
| `tests/budget_oracle.py` | `6b7646b7e2f4824f…` | earlier test, unchanged except where the API changed |
| `tests/chaos.py` | `22932e82a196e76d…` | earlier test, unchanged except where the API changed |
| `tests/common.py` | `9112ff697ac8a7bf…` → `cd6b6ce85b5755cc…` (amendment 1) | fixtures: keys, services, replay lockstep |
| `tests/conform_store.py` | `22b3d5a1e0198f0d…` | earlier test, unchanged except where the API changed |
| `tests/e1_release_evidence.py` | `1ecc76ee74aa2804…` | earlier test, unchanged except where the API changed |
| `tests/e2_reconcile_evidence.py` | `afc43394784e4875…` | earlier test, unchanged except where the API changed |
| `tests/e3_lifecycle_evidence.py` | `8e57f66c34758351…` | earlier test, unchanged except where the API changed |
| `tests/g01_race.py` | `34b00e079e0a055a…` | earlier test, unchanged except where the API changed |
| `tests/g02b.py` | `4640e08d322857b3…` | earlier test, unchanged except where the API changed |
| `tests/h_tests.py` | `e57c81e0cabd9709…` → `8ce6557f09837b8c…` (amendment 1) | H1–H5 |
| `tests/mcp_tests.py` | `fede07f8300dfd04…` | earlier test, unchanged except where the API changed |
| `tests/vectors.py` | `ee0147c353c331cf…` | the 34 vector groups, copied unchanged from the v3.1 oracle bundle |
| `tests/w1_authority.py` | `061df2240a9d1e33…` | earlier test, unchanged except where the API changed |
| `tests/w2_receipts.py` | `ae80070baa9eb532…` | earlier test, unchanged except where the API changed |
| `tests/w3_service_lockstep.py` | `d5359d1dbb7ca14d…` | earlier test, unchanged except where the API changed |
| `tests/w4_service_crash.py` | `01914f2ce5338071…` | earlier test, unchanged except where the API changed |
| `../budget_v3_1/contract/CONTRACT_V3_1.md` | `4200c1ce4931c9ed…` | the contract, frozen |

All recorded in `DECLARED_HOST.txt` at 09:39:38 UTC, before any declared test ran. The two amended files carry both hashes: the declared one and the one recorded with amendment 1 at 09:48:56 UTC, before the re-run. `SHA256SUMS` in the bundle lists every file.
