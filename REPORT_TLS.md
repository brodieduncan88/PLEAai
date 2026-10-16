# PLEA gateway v0.5: mutual TLS between the governor, the witness service and the gate host

12 October 2026 · follows the v0.4 report · private working material, not for publication

## Summary

**Headline.** The v0.4 report's first open item is closed: the services no longer accept requests from anyone who can reach the port. Each service presents a certificate from the deployment's own certificate authority and requires one from every client; each client pins that authority, checks the server's name and presents its own certificate; an allow-list on each service names the client roles it admits. A request without a certificate the authority issued never reaches a handler, and a server that is not the pinned one never receives the request. All 35 checks passed on the declared run and again after one labelled amendment, which corrected a misclassification the re-run of W4 exposed: a service that dies mid-request must still be reported as unavailable, not as a transport refusal.

| check | declared | result |
| --- | --- | --- |
| T1 nothing without a certificate the authority issued and the allow-list names | 5 refusals at each service, audit log and ledger unchanged, then the governor admitted and named | **15/15 ok**, declared run and re-run (two labels changed by amendment 1) |
| T2 the client refuses a server that is not the pinned one | impostor witness, impostor host, a genuine certificate for another name; nothing applied, nothing run | **7/7 ok** |
| T3 the lifecycle over mutual TLS: API and MCP in host mode | 4 roots E3-style; MCP retry runs once; MCP without TLS does not start | **6/6 ok** |
| T4 rotation of certificates and of the authority | new server and client certificates accepted; overlap and cut-over of a new authority | **7/7 ok** |
| re-runs: H1–H5, M1–M3, E1–E3, W1–W4, conformance, chaos, G02b, G01 (300) | all pass | **all pass**; W4 failed on the declared run (the misclassification), 18/18 after amendment 1; conformance 34/34, chaos 90/90, G02b 200/200, G01 300/300 |

What this does not close: the connection from each process to PostgreSQL (that is the DSN's `sslmode` and the server's certificate, outside this package), the sandbox behind the gate host (G04), and the durability of the host's one-shot state (unchanged from v0.4).

## 1. What was built

**`tls.py`.** A private certificate authority (P-256, SHA-256), server certificates with subject alternative names, client certificates, and the two contexts.

- `TLSServer(cert, key, ca, allow)`: TLS 1.2 or later, the service's certificate, and `CERT_REQUIRED` against `ca`: a client that presents no certificate, or one the authority did not issue, fails at the transport. `allow` is a tuple of client common names; the handler answers 403 to any other certificate the authority issued. Empty admits every certificate the authority issued.
- `TLSClient(ca, cert, key)`: the authority pinned, `check_hostname` on, the client's certificate presented. The certificate's name is checked against the URL's host, so a genuine certificate issued for another host is refused.
- `TLSHandlerMixin`: the TLS handshake runs in the handler's thread, never in the accept loop, so a slow or hostile client cannot stall the service; the peer's common name is read from its certificate and checked against the allow-list before any route.
- `tls.py init DIR` writes a deployment's authority and certificates; `bundle()` concatenates authorities for the overlap window of a rotation.
- `TransportError`: raised by both clients when the transport refuses (a TLS failure at the handshake or, under TLS 1.3, on the first read; or HTTP spoken to a TLS port). It is not `WitnessUnavailable`: retrying will not help.

**The services.** `witness_service.py` and `gate_host.py` take `--tls-cert`, `--tls-key`, `--tls-ca` and `--tls-allow NAME` (repeatable). Without them they speak plain HTTP on loopback, as before, and every earlier test still runs that way. `GET /pubkey` now reports `tls` and `peer`, the name on the client's certificate.

**The clients.** `RemoteWitness(url, public_key, tls=TLSClient(...))`, `GateHostClient(url, tls=...)`, and `plea_mcp.py --tls-ca --tls-cert --tls-key`. The governor is unchanged: it holds the clients and still holds no key.

**What TLS adds and what it does not.** The receipts and reports were already the end-to-end proof: a tampered response is detected by its signature, and the witness derives every label itself. TLS adds authentication of the hop, in both directions, so that only the deployment's own processes can ask the witness to accept or the host to run. It does not replace the signatures, and the report keeps them as the evidence of record.

## 2. Declaration

`DECLARED_TLS.txt`, recorded at 10:36:04 UTC, holds the sha256 of every file and the expected result of every check; one amendment, after the chain, is labelled in the same file and reported in 3.5. The development smokes that preceded it are named in it: three runs of `t_tests.py`, two of which failed on the test code itself (a shadowed import in the readiness probe; argument slicing in one check) before the third passed. Because the clients, the services and the MCP server changed, the whole chain was declared and run again, after T, on the same database. The v0.4 outputs were moved to `outputs/v0_4/` first.

## 3. Results

The declared run of `t_tests.py` passed every check (14.3 s). The re-run after amendment 1 passed every check again (12.9 s); the only difference is the two labels in T1 that name what the plain-HTTP client now sees. The tables are from the re-run; the declared output is kept in `outputs/declared_t/`.

### 3.1 T1: nothing without a certificate the authority issued and the allow-list names

The witness and the host were started with `--tls-allow governor`. Five bad clients against each, then the governor.

| check | result |
| --- | --- |
| witness: plain HTTP to the TLS port: the connection is closed without a response (WitnessUnavailable) | ok |
| witness: HTTPS with the authority pinned but no client certificate (TransportError) | ok |
| witness: a client certificate from the impostor authority (TransportError) | ok |
| witness: a server certificate (the host's own) as a client certificate (TransportError) | ok |
| witness: a 'stranger' certificate the allow-list does not name (PermissionError) | ok |
| witness: the audit log is unchanged by the refusals | ok |
| witness: the governor's certificate is admitted | ok |
| witness: names the peer 'governor' over TLS | ok |
| host: plain HTTP to the TLS port: the connection is closed without a response (ConnectionError) | ok |
| host: HTTPS with the authority pinned but no client certificate (TransportError) | ok |
| host: a client certificate from the impostor authority (TransportError) | ok |
| host: a server certificate (the host's own) as a client certificate (TransportError) | ok |
| host: a 'stranger' certificate the allow-list does not name (403) | ok |
| host: the ledger is unchanged by the refusals | ok |
| host: the governor's certificate is admitted and the tool runs once | ok |

The four transport cases never reached a handler: three failed inside TLS (no client certificate, a certificate from the impostor authority, a server certificate presented as a client's) and raised `TransportError`; plain HTTP spoken to the TLS port had its connection closed without a response, which the clients report as they always have (`WitnessUnavailable`; a `ConnectionError` at the host client), because a client cannot tell that case from a service that died. The fifth, a certificate the authority did issue for a name the allow-list does not admit, reached the handler and was answered 403. The audit log and the host's ledger did not change across the ten refusals. The governor's certificate was admitted by both, the tool ran once, and the witness reported its peer as `governor` over TLS.

### 3.2 T2: the client refuses a server that is not the pinned one

| check | result |
| --- | --- |
| an impostor witness (certificate from another authority) (TransportError) | ok |
| the impostor witness applied nothing | ok |
| an impostor host (TransportError) | ok |
| the impostor host ran nothing | ok |
| a genuine certificate issued for another name (TransportError) | ok |
| the wrongly named witness applied nothing | ok |
| the genuine witness is accepted | ok |

A witness and a host presenting certificates from another authority, and a witness presenting a genuine certificate issued for `elsewhere.example`, were each refused by a client pinning the deployment's authority, inside TLS, before any request was sent: the impostor witness, which held the real witness credential, applied nothing, the impostor host's ledger stayed empty, and the wrongly named witness applied nothing. The genuine witness was accepted.

### 3.3 T3: the lifecycle over mutual TLS

| check | result |
| --- | --- |
| four roots through the API in host mode over mutual TLS | ok |
| MCP over TLS lists the host's tools | ok |
| MCP over TLS: a retried charge runs once | ok |
| MCP over TLS: beyond the budget is refused and never runs | ok |
| MCP root replay lockstep | ok |
| MCP without TLS against the TLS services does not start and applies nothing | ok |

Four roots ran E3's schedule through the API in host mode over TLS, each 4 ran, 1 no-effect, 1 denied, credit 1, every reconcile AUTHORISED, no gate key in the governor, and each audit log replayed through the oracle. The MCP server, started with `--tls-ca`, `--tls-cert` and `--tls-key` in host mode, listed the host's tools, ran a retried charge once and refused a charge beyond the budget without it reaching the host. The same server started without the TLS options against the TLS services exited with `TransportError` and applied nothing.

### 3.4 T4: rotation

| check | result |
| --- | --- |
| a new server certificate from the same authority: the unchanged client keeps working | ok |
| a new client certificate from the same authority: the unchanged service admits it | ok |
| overlap: a client pinning both authorities with the old certificate works | ok |
| overlap: a client pinning only the old authority is refused (the server is under the new) (TransportError) | ok |
| cut-over: the old client certificate is refused (TransportError) | ok |
| cut-over: the new client certificate is admitted | ok |
| replay lockstep | ok |

A new server certificate from the same authority was accepted by the unchanged client; a new client certificate from the same authority was admitted by the unchanged service. For a new authority: during the overlap the witness presented a certificate from the new authority and trusted a bundle of both, a client pinning the bundle with its old certificate worked, and a client still pinning only the old authority was refused; after the cut-over, with the witness trusting only the new authority, the old client certificate was refused and the new one admitted. The audit log replayed through the oracle.

### 3.5 Re-runs

Declared with T and run after it on the same database. One failure, then one amendment, then the re-run.

| test | result | time |
| --- | --- | --- |
| H1–H5 gate host | 32/32 | 13.1 s |
| M1–M3 MCP | 28/28 | 6.4 s |
| E1 release evidence | 8/8, lockstep | 1.9 s |
| E2 reconcile evidence | 8/8, lockstep | 1.9 s |
| E3 lifecycle evidence, 6 roots | PASS | 10.3 s |
| W1 authority boundary | PASS | 4.2 s |
| W2 receipts | PASS, lockstep | 0.8 s |
| W3 service lockstep | PASS | 56.8 s |
| W4 service crash, 18 points | **FAIL on the declared run**; 18/18 after amendment 1 | 20.9 s |
| conformance, 34 vector groups | 34/34 | 31.1 s |
| chaos | 90/90 | 65.7 s |
| G02b | 200/200 | 89.6 s |
| G01 lock, 16 workers | 300/300 | 184.5 s |

**The W4 failure and amendment 1.** W4 kills the witness service at each of 18 points inside an acceptance and expects the client to see either a response or `WitnessUnavailable`, which it retries. On the declared run the client raised `TransportError` at the first point: the new classification in `tls.py` counted a connection closed without a response as a transport refusal, "retrying will not help". That was wrong. A client cannot distinguish a service that died mid-request from plain HTTP spoken to a TLS port, and the first must be retried (contract 5.2/2 and 5.5/2). Amendment 1, recorded in `DECLARED_TLS.txt` at 10:44:22 UTC with the new hashes and the expected re-run, makes only a TLS failure a `TransportError`; a closed connection is `WitnessUnavailable` at the witness client and the `ConnectionError` it always was at the host client. T1's two plain-HTTP checks now expect those. The declared W4 output is in `outputs/declared_w4/`; the re-run gave 18/18 and T 35/35. The v0.4 outputs are under `outputs/v0_4/`.

## 4. What this shows, and what it does not

**Shows.**

- With TLS on, nothing reaches a handler without a certificate the deployment's authority issued: not plain HTTP, not an anonymous TLS client, not a certificate from another authority, not a server certificate used as a client's. A certificate the authority issued for a role the service does not admit is refused by the handler, and the store and the ledger show no trace of any of it.
- A client pinning the authority refuses an impostor witness, an impostor host, and a genuine certificate for another host, before sending anything.
- The whole lifecycle, through the API and through MCP in host mode, runs over mutual TLS with the same accounting as v0.2 and v0.4.
- Certificates and the authority itself rotate, with an overlap window and a clean cut-off, like the keys in v0.4.

**Does not show.**

- The PostgreSQL connections. Each process still opens its own, and whether that hop is encrypted and authenticated is set in the DSN.
- Revocation. A compromised certificate is handled by rotating the authority (T4), not by a revocation list; none is checked.
- Anything behind the host, and the host's state durability, as in v0.4.

## 5. Next

1. **The design-partner framework integration.**
2. **A throughput measurement** with connection pooling.
3. **Gate B with a person.**

## 6. Files and hashes

| file | sha256 (first 16 hex digits) | role |
| --- | --- | --- |
| `plea_gateway/__init__.py` | `d04abe271653aafd…` | package |
| `plea_gateway/evidence.py` | `41f6a14b7a5c21b0…` | reports and derivation |
| `plea_gateway/faults.py` | `67c9ac8f872d31b5…` | crash points |
| `plea_gateway/gate_host.py` | `b0d030911b996893…` | the gate host and its client; TLS options |
| `plea_gateway/governor.py` | `b04868e5dde64780…` | SDK surface, unchanged |
| `plea_gateway/plea_budget_ref.py` | `a367a4bbc2ca21b4…` | the verified reference, unchanged |
| `plea_gateway/receipts.py` | `b1a58566bbae8cf6…` | receipts; pinned key lists |
| `plea_gateway/store.py` | `f006c7646ba59182…` | the store, unchanged |
| `plea_gateway/tls.py` | amended: `9b7510bdbc26c18e…` | authority, certificates, contexts, allow-list (v0.5) |
| `plea_gateway/witness.py` | `dd87f36d712c7070…` | witnesses; the client takes a TLSClient |
| `plea_gateway/witness_service.py` | `a1fb02f605eec6f9…` | the witness service; TLS options |
| `mcp/demo_tools.py` | `7f672232e9988fb1…` | demonstration tools |
| `mcp/plea_ctl.py` | `a8974537035ea014…` | operator control |
| `mcp/plea_mcp.py` | `baddf62e40c79290…` | governed MCP server; --tls-* |
| `mcp/vanilla_mcp.py` | `3b574ba659f905a8…` | ungoverned control case |
| `tests/apply_once.py` | `18a47ba1a8fc9379…` | earlier test, unchanged |
| `tests/budget_oracle.py` | `6b7646b7e2f4824f…` | earlier test, unchanged |
| `tests/chaos.py` | `22932e82a196e76d…` | earlier test, unchanged |
| `tests/common.py` | `916d40e28084378b…` | fixtures: keys, services, the test PKI, replay lockstep |
| `tests/conform_store.py` | `22b3d5a1e0198f0d…` | earlier test, unchanged |
| `tests/e1_release_evidence.py` | `1ecc76ee74aa2804…` | earlier test, unchanged |
| `tests/e2_reconcile_evidence.py` | `afc43394784e4875…` | earlier test, unchanged |
| `tests/e3_lifecycle_evidence.py` | `8e57f66c34758351…` | earlier test, unchanged |
| `tests/g01_race.py` | `34b00e079e0a055a…` | earlier test, unchanged |
| `tests/g02b.py` | `4640e08d322857b3…` | earlier test, unchanged |
| `tests/h_tests.py` | `8ce6557f09837b8c…` | H1–H5 |
| `tests/mcp_tests.py` | `fede07f8300dfd04…` | earlier test, unchanged |
| `tests/t_tests.py` | amended: `0767cd4dec6b2814…` | T1–T4 |
| `tests/vectors.py` | `ee0147c353c331cf…` | the 34 vector groups, copied unchanged from the v3.1 oracle bundle |
| `tests/w1_authority.py` | `061df2240a9d1e33…` | earlier test, unchanged |
| `tests/w2_receipts.py` | `ae80070baa9eb532…` | earlier test, unchanged |
| `tests/w3_service_lockstep.py` | `d5359d1dbb7ca14d…` | earlier test, unchanged |
| `tests/w4_service_crash.py` | `01914f2ce5338071…` | earlier test, unchanged |
| `../budget_v3_1/contract/CONTRACT_V3_1.md` | `4200c1ce4931c9ed…` | the contract, frozen |

All recorded in `DECLARED_TLS.txt` at 10:36:04 UTC, before any declared test ran. The two amended files carry the declared hash here; the amended hashes are recorded with amendment 1 at 10:44:22 UTC, before the re-run: `tls.py` e08e322d53539bd9…, `t_tests.py` b1effcbe6a4bcb05…. `SHA256SUMS` in the bundle lists every file.
