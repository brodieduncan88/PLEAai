# PLEA gateway v0.3: an agent's tools governed over MCP

12 October 2026 · follows the v0.2 report · private working material, not for publication

## Summary

**Headline.** An agent's tools now pass through the governor without the agent changing. A small MCP server exposes the tools the agent already uses, from a Python registry or by proxying an upstream MCP server, and runs every call through the governed lifecycle. The plan's demonstration is now a test: the same retry charges a customer twice through the plain server and once through the governed one. All 28 declared checks passed.

| check | declared | result |
| --- | --- | --- |
| M1 protocol and governance over stdio | 16 checks | 16/16 |
| M2 the double charge, ungoverned against governed | ungoverned 2, governed 1; a distinct key is a new call | 2 and 1; 4/4 |
| M3 the upstream proxy | 8 checks | 8/8 |

What this closes from the plan: the MCP wrapper (next-step 1 of the v0.2 report) and the demonstration from Phase 2. Gate B, a stranger governing a tool call in under 30 minutes, is not claimed here: that needs a stranger.

## 1. What was built

**`mcp/plea_mcp.py`, the governed server.** MCP's stdio transport, newline-delimited JSON-RPC 2.0: `initialize`, `ping`, `tools/list`, `tools/call`. Tools come from a Python module exposing `TOOLS` (name to description, input schema and function), or from an upstream MCP server the governed server spawns and proxies. Each `tools/call`:

- derives a request key from the tool name and the canonical JSON of its arguments, unless the caller passes `_plea_request_key`. An identical call is therefore the contract's DUPLICATE and is answered from the stored result without running the tool;
- runs through `Governor.attempt`: RESERVE, acceptance, TOKEN, START, acceptance with a signed receipt, the gate behind that receipt, the tool, and a gate-signed effect report;
- maps refusals to MCP tool errors (`isError`) that name the reason: budget exhausted, held, stopped, in progress. The tool does not run;
- maps a tool that raises `NoEffect` to a normal result that says so, which earns a replacement.

The agent cannot hold, stop or recover the run. One read-only tool, `plea_status`, reports the budget view.

**`mcp/plea_ctl.py`, the operator.** Status, hold, stop, recover, terminalise, terminal, re-register, audit: the contract's local operations, applied through the local credential from outside the agent's reach.

**`mcp/demo_tools.py` and `mcp/vanilla_mcp.py`.** Two tools with a real side effect, an append to a ledger file visible across processes, and the same tools behind a plain MCP server with no governor: the control case, and the upstream for the proxy test.

**On the default request key.** Keying on name plus arguments is what makes a retry a DUPLICATE. It also means two deliberately identical calls would be treated as one, unless the second carries its own `_plea_request_key`. That is the right default for a governor whose job is to stop double execution; an agent framework that wants two identical actions says so explicitly.

## 2. Declaration

`DECLARED_MCP.txt`, recorded at 08:27:26 UTC, holds the sha256 of the MCP files and the test, and the expected result of every check. One development smoke preceded it and is named in it. The engine underneath is `plea_gateway` exactly as declared for v0.2.

## 3. Results

All three parts passed as declared in 7.6 s, through a witness service over HTTP, with the governed server as a subprocess speaking MCP over stdio.

### 3.1 M1: protocol and governance

A governed server with budget 2 and replacement 1 over the demo tools. 16 of 16 checks:

| check | result |
| --- | --- |
| tools listed | ok |
| charge 1 runs | ok |
| charge 1 retry served, same text | ok |
| ledger has one charge for order 1 | ok |
| zero refund is a no-effect | ok |
| charge 2 runs on the replacement | ok |
| charge 3 refused: budget | ok |
| ledger: order 3 never charged | ok |
| operator hold | ok |
| charge 4 refused: held | ok |
| operator recover | ok |
| charge 4 refused after recovery: budget | ok |
| status live (0,3,1) credit 1 | ok |
| unknown tool is an error | ok |
| replay lockstep | ok |
| chain | ok |

The sequence the agent saw: charge 1 ran; the same call again was answered with the same text and the ledger still held one charge; a zero refund was reported as a no-effect; charge 2 ran on the replacement that earned; charge 3 was refused with "budget exhausted" and never reached the tool; the operator held the run from outside and charge 4 was refused with "held"; after recovery charge 4 was refused again, at the budget; `plea_status` showed live (0, 3, 1) with credit 1. The audit log replayed through the oracle.

### 3.2 M2: the double charge

| check | result |
| --- | --- |
| ungoverned: the retry charges twice | ok |
| governed: the retry charges once | ok |
| a distinct request key is a new call | ok |
| replay lockstep | ok |

The plain server charged order 7 2 times on a retry. The governed server charged order 8 1 time on the same retry. A second charge for order 8 under its own request key ran, so the governor keys retries; it does not deduplicate everything that looks alike.

### 3.3 M3: the upstream proxy

The governed server spawned the plain server and proxied it. 8 of 8 checks:

| check | result |
| --- | --- |
| upstream tools listed through the proxy | ok |
| proxied charge 9 runs | ok |
| proxied retry served | ok |
| upstream ran order 9 once | ok |
| proxied charge 10 runs | ok |
| proxied charge 11 refused: budget | ok |
| upstream never saw order 11 | ok |
| replay lockstep | ok |

The agent saw the upstream's tools and `plea_status`; charge 9 ran upstream once and its retry was served; charge 11 was refused at the budget and the upstream never saw it.

## 4. What this shows, and what it does not

**Shows.**

- A tool call the agent makes twice runs once. The second answer is the first answer.
- A call beyond the budget, or on a held or stopped run, never reaches the tool, and the agent is told why.
- A zero-effect call earns a replacement that the next call uses.
- The guarantees survive a proxy: an upstream MCP server the governed server did not write behaves the same way behind it.
- The operator's controls are outside the agent's tool list.

**Does not show.**

- Real agent frameworks. The client here is a test harness speaking MCP; a framework's retry policy, parallel tool calls and streaming are not exercised.
- Streaming or long-running tools, cancellation, progress notifications, resources and prompts: the server implements the tools subset of MCP only.
- Transport beyond stdio.
- Gate B. The quickstart has not been tried on a stranger.

## 5. Next

1. **Gate B:** hand the README to someone who has never seen PLEA and time them.
2. **A framework integration**, chosen by the first design partner.
3. **Gate key separation and transport security**, from the v0.2 report.
4. **A throughput measurement** with connection pooling.

## 6. Files and hashes

| file | sha256 (first 16 hex digits) | role |
| --- | --- | --- |
| `mcp/demo_tools.py` | `7f672232e9988fb1…` | two tools with a real side effect |
| `mcp/plea_ctl.py` | `cd8f09abb7d6e197…` | operator control |
| `mcp/plea_mcp.py` | `3d20a58fa9a72c60…` | the governed MCP server (registry or upstream proxy) |
| `mcp/vanilla_mcp.py` | `3b574ba659f905a8…` | the same tools, ungoverned |
| `tests/mcp_tests.py` | `fede07f8300dfd04…` | M1–M3 |
| `tests/common.py` | `ccda19a927a4bc54…` | credentials, the test gate key, the service as a subprocess |

All recorded in `DECLARED_MCP.txt` at 08:27:26 UTC, before the declared test ran. The engine is `plea_gateway` as hashed in `DECLARED_EVIDENCE.txt`. `SHA256SUMS` in the bundle lists every file.
