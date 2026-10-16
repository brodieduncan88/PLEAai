# PLEA gateway v1.2.1: the attempt-budget contract over a transactional store, with a witness service, verified evidence, governed tools over MCP, a gate host, mutual TLS, admission enforced at the host, one owner per host state, a gateway credential that can neither rewrite accounting nor author the audit record nor provision a budget, every audit record checked in the database against the contract's own decision, every budget anchored to its provisioning record, and outcomes authenticated on replay

13 October 2026. Private working material for the PLEA campaign. Keep it in the private connected Library; do not share or publish it.

Read the reports in order, or their PDFs: `REPORT_GATEWAY.md` (v0: the store, G01, G02b), `REPORT_WITNESS.md` (v0.1: the authority boundary, receipts, the service), `REPORT_EVIDENCE.md` (v0.2: verified evidence, G03), `REPORT_MCP.md` (v0.3: an agent's tools governed over MCP), `REPORT_HOST.md` (v0.4: the gate host holds the only gate key; the Gate B stranger test), `REPORT_TLS.md` (v0.5: mutual TLS between the governor, the witness service and the gate host), `REPORT_AUTH.md` (v0.6: execution authorisation and recovery, the response to the v0.4 scoped review), `REPORT_ADMISSION.md` (v0.7: admission enforced at the host and state ownership, the response to the v0.6 review), `REPORT_AUTHORITY.md` (v0.8: atomic host-state ownership with fencing, and the gateway credential restricted from rewriting accounting, the response to the v0.7 review), `REPORT_INTEGRITY.md` (v0.9: the legal transition relation enforced in the database and a separate control-plane credential, the response to the v0.8 review), `REPORT_BOUNDARY.md` (v1.0: accepted bindings immutable, outcomes authenticated on replay, the privileged functions hardened, the response to the v0.9 review), `REPORT_PROVENANCE.md` (v1.1: the audit record authored by the database and budgets provisioned only by the control plane, the response to the v1.0 review), `REPORT_BINDING.md` (v1.2: every record the contract's own decision, operands and refusals included, and every budget anchored to an immutable provisioning record, the response to the v1.1 review), `REPORT_RELEASE.md` (v1.2.1: the release check made trustworthy, and wider adversarial testing of the in-database contract engine, the response to the v1.2 review; no product code changed).

## What it is

The verified pure reference of contract v3.1 (`plea_gateway/plea_budget_ref.py`, unchanged, sha256 `a367a4bb…`) is the decision engine. The package adds what the contract leaves to the gateway:

- `store.py`: one transaction per operation over PostgreSQL, serialised per root; validation before the store is touched; the state rebuilt from the rows; the reference decides; an audit log with a hash chain. Since v0.8 no login role holds a direct write on the authoritative tables: every mutation goes through one owner-side `SECURITY DEFINER` function (`plea_write`). Since v0.9 that function enforces the *complete* contract-authorised change, not just the new phase: each per-attempt phase transition must be one a contract operation produces (the legal transition relation) and is reserved to the credential class of that operation — gateway (`plea_local`), witness (`plea_witness`) or control plane (`plea_control`); every mode change is reserved to `plea_control`; a new attempt is a bare reservation; crossing and receipt are monotone and only on a consumption phase; the budget is immutable, the audit append-only, and I1/I2 hold. So hand-written SQL as the gateway can neither rewrite accepted facts, free a consumed budget (e.g. `CONSUMED→DISCARDED`), nor change a mode (e.g. flip the witness with a forged `RECOVER`). Since v1.0 the bindings an attempt carries are immutable in place (the request binding never changes; the nonce is set only by START and cleared only by RECOVER), the results cache is written only through `plea_put_result` (an admitted, consumed attempt; a known outcome never rewritten) and the governor re-verifies the executor's signed effect report on every replay before returning a cached value. All three functions are `SECURITY DEFINER` with every table reference schema-qualified, `search_path = pg_catalog, pg_temp` (temporary tables last, so none can shadow a name), and PUBLIC's default EXECUTE revoked; no login role may create objects in `public`. Since v1.1 the database authors the audit record: the observation it stores is derived from the rows just written (the caller's must equal it), the decision kind is APPLIED exactly when the state changed, the operation named is the one that produces the transition performed, and the chain hash is recomputed in-database with a canonical form identical to the client's — so a hash-consistent but false record cannot exist and `verify_chain` attests to real history; and a root (a budget) is provisioned only by the control plane. Since v1.2 every record is the contract's own decision: `plea_write` evaluates the contract's single-root step in the database (`plea_step`, a PL/pgSQL port of the reference engine, differential-tested against it and the independent oracle) on the state before the write, and refuses a record unless its kind, its code and every row and mode it changed are exactly what the operation it names produces there — so the operation's operands (attempt, request, nonce, verdict, evidence label), the extent of a batch (RECOVER, REREGISTER) and every mode guard are bound, a refusal is checked as strictly as a change, and a control-plane operation is recorded, applied or refused, only by the control plane. And every budget has an origin: `plea_new_root` appends an immutable record (root, k, m, issuing credential, contract, release, database time) to a hash-linked provisioning log, the root's chain starts at that record's hash, and `verify_chain` checks the anchor and the budget against it. What the database cannot check is whether a request it refused was ever made: a refusal the contract gives for the current state may be recorded for a request that never reached the gateway (it changes nothing; `REPORT_BINDING.md` section 4).
- `receipts.py`: Ed25519-signed receipts binding root, attempt, sequence number, operation, decision and audit hash.
- `evidence.py`: gate-signed fence reports and effect reports, and the derivation of the contract's RELEASE and RECONCILE labels from them (G03). The caller never supplies a label.
- `witness_service.py`: the only holder of the witness credential and the signing key; pins the gate's public key(s) and derives labels from evidence. `POST /accept`, `GET /pubkey`. Since v0.7 it also applies CROSS, the admission, and receipts it: the contract's check that the run is ACTIVE and OPEN happens under the witness's credential, and the receipt is what the gate host requires.
- `witness.py`: the in-process witness (v0) and the HTTP client (`RemoteWitness`), which verifies every receipt it receives.
- `governor.py`: the SDK surface over the local credential. CROSS is the admission point, applied before anything is dispatched, so a HOLD or STOP accepted first means nothing runs; a retry replays the stored outcome (a value, a no-effect, an unknown verdict) or resumes an unfinished attempt without a second execution (v0.6). The gate crosses only behind a verified receipt that matches the local audit chain and binds this action.
- `gate_host.py` (v0.4): the process that holds the gate's key, runs each attempt's tool exactly once, and signs the reports. With it, the caller's process holds no key. Since v0.7 it runs nothing without the witness's admission receipt, whoever asks. Since v0.8 its state file has exactly one owner at a time: acquisition is atomic (serialised), a takeover bumps a generation, and every write that starts new work is fenced by that generation, so a host frozen past its lease cannot start or run anything after another has taken over.
- `binding.py` (v0.6): the nonce as a digest of executor, tool and arguments; the witness's intent receipt carries it; the host runs only what the witness accepted at exactly this executor; the effect report covers a digest of the result.
- `tls.py` (v0.5): a private certificate authority, server and client certificates, and the TLS contexts: the services require a client certificate the authority issued and admit only the names on their allow-list; the clients pin the authority and check the server's name. The receipts and reports stay the end-to-end proof; TLS protects the hop.
- `faults.py`: crash injection for the chaos runs.

No accounting logic lives in this package.

`mcp/` is the agent-facing layer: `plea_mcp.py` exposes tools over MCP's stdio transport and runs every call through the governor (from a Python registry, or by proxying an upstream MCP server); `plea_ctl.py` is the operator's control, outside the agent's reach; `demo_tools.py` and `vanilla_mcp.py` are the demonstration's tools and their ungoverned control case.

## Contents

| path | what it is |
| --- | --- |
| `REPORT_BINDING.md`, `.pdf` | v1.2: every record the contract's own decision, the provisioning log and the anchor, X1–X4, the v1.1 review's findings reproduced and repaired |
| `REPORT_PROVENANCE.md`, `.pdf` | v1.1: the audit record authored by the database, provisioning by the control plane, U1–U2, the v1.0 review's findings reproduced and repaired |
| `REPORT_AUTHORITY.md`, `.pdf` | v0.8: atomic ownership with fencing, the gateway credential restricted, P1–P2, the v0.7 review's findings reproduced and repaired |
| `REPORT_ADMISSION.md`, `.pdf` | v0.7: admission at the host, state ownership, V1–V6, the v0.6 review's findings reproduced and repaired |
| `REPORT_AUTH.md`, `.pdf` | v0.6: execution authorisation and recovery, R1–R6, the review's findings reproduced and repaired |
| `REPORT_TLS.md`, `.pdf` | v0.5: mutual TLS, T1–T4, certificate and authority rotation |
| `REPORT_HOST.md`, `.pdf` | v0.4: the gate host, H1–H5, key rotation, the Gate B stranger test |
| `REPORT_MCP.md`, `.pdf` | v0.3: governed tools over MCP, M1–M3, the double-charge demonstration |
| `REPORT_EVIDENCE.md`, `.pdf` | v0.2: evidence, derivation, E1–E3, the re-runs |
| `REPORT_WITNESS.md`, `.pdf` | v0.1: the boundary, receipts, the service, W1–W4, the re-runs |
| `REPORT_GATEWAY.md`, `.pdf` | v0: the store, G01, G02b, chaos, the serializable finding |
| `DECLARED_AUTHORITY.txt`, `DECLARED_ADMISSION.txt`, `DECLARED_AUTH.txt`, `DECLARED_TLS.txt`, `DECLARED_HOST.txt`, `DECLARED_MCP.txt`, `DECLARED_EVIDENCE.txt`, `DECLARED_WITNESS.txt`, `DECLARED_GATEWAY.txt` | hashes and expected results, recorded before the tests ran; amendments labelled |
| `plea_gateway/` | the package |
| `mcp/` | the governed MCP server, the operator CLI, the demonstration tools |
| `tests/mcp_tests.py` | M1–M3 |
| `tests/x_tests.py` | X1–X4: the provisioning anchor, every operand bound, refusal records, the database's contract engine (v1.2); v1.2.1 adds a second mutation sweep and a seeded random differential beyond the exhaustive bound |
| `tests/u_tests.py` | U1–U2: audit integrity, provisioning authority (v1.1) |
| `tests/s_tests.py` | S1–S3: binding immutability, authenticated replay, SECURITY DEFINER hardening (v1.0) |
| `tests/q_tests.py` | Q1–Q2: transition integrity and control separation (v0.9) |
| `tests/p_tests.py`, `tests/p_repro.py` | P1–P2 and the reproduction of the v0.7 review's findings on v0.7 |
| `tests/v_tests.py`, `tests/v_repro.py` | V1–V6 and the reproduction of the v0.6 review's findings on v0.6 |
| `tests/r_tests.py`, `tests/r_repro.py`, `tests/review_tools.py` | R1–R6, the reproduction of the v0.4 review's findings on v0.5, and their tools |
| `tests/t_tests.py` | T1–T4 |
| `tests/h_tests.py` | H1–H5 |
| `tests/vectors.py` | the contract's 34 vector groups, copied unchanged from the v3.1 oracle bundle |
| `tests/e1_release_evidence.py` … `e3_lifecycle_evidence.py` | the v0.2 tests |
| `tests/w1_authority.py` … `w4_service_crash.py` | the v0.1 tests, now sending evidence where the API needs it |
| `tests/g01_race.py`, `g02b.py`, `chaos.py`, `conform_store.py` | the v0 tests, now using the credential a deployment would |
| `tests/common.py` | credentials, replay lockstep, invariants, the service as a subprocess |
| `tests/budget_oracle.py` | the oracle, vendored unchanged (sha256 `6b7646b7…`) |
| `outputs/` | the v0.7 runs; `outputs/INDEX.md` names every earlier run kept under `outputs/v0_6/` … `outputs/v0/`, with their declared, failed and amended results, and the two review reproductions |
| `GATE_B_LOG.md` | the stranger's timed log of governing a call from the v0.3 README alone |
| `contract/` | contract v3.1, frozen, with its freeze record |
| `run_chain_v121.sh`, `check_runner.sh` | the declared chain with a truthful exit status, and its self-test (v1.2.1); `run_chain_v12.sh` and earlier are kept as shipped |
| `DECLARED_RELEASE.txt`, `REPORT_RELEASE.md`, `.pdf` | v1.2.1: hashes and expected results declared before the run, and the report |
| `SHA256SUMS` | hashes of every file in this bundle |

## Reproduce

**On a clean machine.** Debian or Ubuntu with PostgreSQL 16 and Python 3.11 or later:

```
sudo apt-get install -y postgresql-16 python3-venv
python3 -m venv venv && . venv/bin/activate && pip install 'psycopg[binary]' cryptography
sudo -u postgres psql -c "CREATE ROLE plea LOGIN PASSWORD 'plea';" -c "CREATE ROLE plea_local LOGIN PASSWORD 'local';" \
    -c "CREATE ROLE plea_witness LOGIN PASSWORD 'witness';" -c "CREATE ROLE plea_control LOGIN PASSWORD 'control';" \
    -c "CREATE DATABASE plea OWNER plea;"
```

Four login roles: `plea` is the owner (setup only, never handed out); `plea_local` is the gateway credential, all an agent-facing process holds — it can neither change a mode nor create a root; `plea_witness` is the witness service's; `plea_control` is the control plane's, the only non-owner role that provisions a root (`plea_ctl.py ROOT provision --budget K`) and changes a mode (hold/stop/recover/reregister). Since v1.2 a control-plane operation is recorded only by `plea_control`, even when the contract refuses it, and each provisioning names its issuing role in the provisioning log.

**Production shape (v1.2), stated plainly.** The agent-facing process (the governor, or `plea_mcp.py`) holds `plea_local` only. The budget is provisioned before it starts, by an operator with `plea_control`; the same operator holds, stops and recovers the run with `plea_ctl.py`. The owner credential `plea` installs the schema and is used by the test suite to stage states; it has no place in any running service. No credential in the agent's process can mint a budget, change a mode, rewrite accounting, author an audit record or record anything but the contract's own decision. Every budget's origin is in the provisioning log (`plea_ctl.py ROOT provenance` prints the record and verifies the chain from it). A database initialised by v1.1 is upgraded by re-running `init_authority()`; roots provisioned before v1.2 carry no provisioning record and are refused by `plea_write` and `verify_chain` until re-provisioned. The tests and the examples below read `PLEA_ADMIN_DSN`, `PLEA_LOCAL_DSN`, `PLEA_WITNESS_DSN` and `PLEA_CONTROL_DSN`; the defaults are `postgresql://plea:plea@127.0.0.1:5432/plea`, `postgresql://plea_local:local@127.0.0.1:5432/plea`, `postgresql://plea_witness:witness@127.0.0.1:5432/plea` and `postgresql://plea_control:control@127.0.0.1:5432/plea`.

**The whole declared chain, in one command.** From the bundle root, with the database `plea` created as above (set `PLEA_DB` for another name):

```
PLEA_DB=plea bash run_chain_v121.sh      # about 30 minutes; exit status 0 only if all 22 stages exit 0
bash check_runner.sh                      # seconds: the runner's own exit statuses, in a throwaway copy
```

The runner uses `PLEA_PYTHON` if set, else `./venv/bin/python` in the bundle root (the venv created above), else `python3`. It checks that Python can import `psycopg` and `cryptography` and that the database is reachable, and exits 2 if not. It runs every stage even after a failure, so the evidence is complete, lists the failed stages, and exits 1. A passing run writes `outputs/rerun.done`; a failing one writes `outputs/rerun.failed`. (v1.2's `run_chain_v12.sh` exited 0 whatever its stages did, and looked for its interpreter one directory above the bundle.) The individual commands follow.

```
# from this directory (the bundle root); prints nothing on success; safe to run again
python3 -B -c "import sys; sys.path.insert(0,'.'); from plea_gateway import Store
s = Store('postgresql://plea:plea@127.0.0.1:5432/plea'); s.init_schema(); s.init_authority()"

cd tests
python3 -B x_tests.py                                         # provisioning anchor, operands bound, refusals, the engine: X1–X4 (v1.2)
python3 -B u_tests.py                                         # audit integrity, provisioning authority: U1–U2 (v1.1)
python3 -B s_tests.py                                         # binding immutability, authenticated replay, definer hardening: S1–S3 (v1.0)
python3 -B q_tests.py                                         # transition integrity and control separation: Q1–Q2 (v0.9)
python3 -B p_tests.py                                         # ownership fencing and the gateway credential: P1–P2 (v0.8)
python3 -B v_tests.py                                         # admission at the host, state ownership: V1–V6 (v0.7)
python3 -B r_tests.py                                         # execution authorisation and recovery: R1–R6 (v0.6)
python3 -B t_tests.py                                         # mutual TLS: T1–T4, certificate and authority rotation
python3 -B h_tests.py                                         # the gate host: H1–H5, key rotation
python3 -B mcp_tests.py                                       # governed tools over MCP, the double-charge demonstration
python3 -B e1_release_evidence.py; python3 -B e2_reconcile_evidence.py; python3 -B e3_lifecycle_evidence.py
python3 -B w1_authority.py                                    # the boundary, 5 s
python3 -B w2_receipts.py                                     # forged receipts, 2 s
python3 -B w3_service_lockstep.py                             # lifecycle over HTTP, G02b through the service
python3 -B w4_service_crash.py                                # the service killed mid-acceptance
python3 -B chaos.py; python3 -B g02b.py --rounds 200
python3 -B g01_race.py --rounds 300 --workers 16 --k 3 --mode lock          # the declared chain runs 300 rounds in each mode
python3 -B g01_race.py --rounds 300 --workers 16 --k 3 --mode serializable
PYTHONPATH=. python3 -B vectors.py conform_store              # the contract's 34 vector groups through the store
```

Every test creates the roots it uses, so the suite can be run again on the same database.

Optional extra hardening for a deployment: `REVOKE TEMPORARY ON DATABASE plea FROM PUBLIC;` (as the owner) stops the login roles creating temporary tables at all. It is not needed for correctness — the functions qualify every table and search `pg_temp` last — and is left off here so the v0.9 review's native probe, which creates a temporary table, runs unchanged.

## Minimal use

Three steps, in this order: install the schema (above), start the witness service, then run the snippet.

**Keys.** There are two Ed25519 keys, both 32 bytes written as 64 hex characters.

- The **witness key** signs receipts. Give it to the service with `--key <hex>`; `python3 -c "from plea_gateway import Signer; print(Signer().private_hex)"` makes one. If `--key` is omitted the service generates a key for that run only, and every restart changes it.
- The **gate key** signs effect and fence reports. Make it once, keep its private half, and give the service its public half with `--gate-key`. The service refuses reports signed by any other key.

```
# once: make the gate key and keep it
python3 -c "from plea_gateway import GateSigner; g = GateSigner(); print(g.private_hex); print(g.public_hex)" > gate_keys.txt

# every time: the service, with its own key and the gate's public key
python3 plea_gateway/witness_service.py --port 8787 --key <witness private hex> \
    --dsn postgresql://plea_witness:witness@127.0.0.1:5432/plea --gate-key <gate public hex>
```

```python
from plea_gateway import Store, RemoteWitness, Governor, GateSigner, BudgetExhausted, Held, NoEffect

gate = GateSigner(private_hex=GATE_PRIVATE_HEX)                             # the same key in every process
local = Store('postgresql://plea_local:local@127.0.0.1:5432/plea')          # cannot apply an acceptance, nor change a mode
witness = RemoteWitness('http://127.0.0.1:8787', public_key=WITNESS_PUBLIC_HEX)   # pinned; omit public_key for trust-on-first-use
# first, once, as the operator (plea_control):  python3 mcp/plea_ctl.py billing-agent provision --budget 3 --replacement 1
gov = Governor(local, witness, root='billing-agent', budget=3, replacement=1, gate=gate)   # this process holds plea_local only; it refuses an unprovisioned root

def charge(order_id, amount): print('charge ran'); return {'charged': amount}

print(gov.attempt('charge:order-42', charge, order_id=42, amount=10))   # prints "charge ran", then {'charged': 10}
print(gov.attempt('charge:order-42', charge, order_id=42, amount=10))   # prints only {'charged': 10}: the stored value, charge did not run
```

`attempt` returns the function's return value. A retry under the same request key returns the stored value (JSON round-tripped) without calling the function, in any state of the run. A fourth distinct call on this root raises `BudgetExhausted`; after `gov.hold()` any new call raises `Held`; `gov.recover()` discards never-accepted work and returns the run to ACTIVE. A governed function that raises `NoEffect` earns a replacement (the gate signs NO\_EFFECT); any other exception leaves the attempt charged (UNKNOWN).

## Host mode: no key in the caller's process (v0.4)

Run the tools on a gate host, which holds the gate key and pins the witness's public key; the governor then needs no key. From the bundle root (the tools module is named by its import path from here; the review found the earlier `--tools demo_tools` failed from this directory):

```
PLEA_LEDGER=$PWD/ledger.jsonl python3 plea_gateway/gate_host.py --port 8900 --tools mcp.demo_tools \
    --key <gate private hex> --witness-key <witness public hex> --state $PWD/gate_host.sqlite
```

`--state` is the host's own record of what ran or was fenced; give it an absolute path and keep the file. `PLEA_LEDGER` is where the demonstration tools write; it is not part of the product.

```python
from plea_gateway import Store, RemoteWitness, Governor, GateHostClient
host = GateHostClient('http://127.0.0.1:8900', public_key=GATE_PUBLIC_HEX)   # pinned; omit public_key for trust on first use
gov = Governor(local, witness, root='billing-agent', budget=3, replacement=1, host=host)   # the root provisioned beforehand by the control plane
gov.attempt('charge:order-42', 'charge', order_id='42', amount=10)        # a tool name, run once at the host
gov.attempt('charge:order-42', 'charge', order_id='42', amount=10)        # the stored value; the host would refuse a second run anyway
```

The host runs each attempt once: a retry, from any process, gets the first result and the same signed report. `gov.release(aid)` fences a reservation at the host and releases it at the witness.

**What the host requires (v0.7).** The witness applies the crossing (CROSS) on the governor's request and signs a receipt for it, the admission. The host runs nothing without a valid admission for exactly this attempt and nonce, whoever asks: a caller that skips the governor and presents a genuine intent receipt is refused, because after a HOLD or STOP the witness's CROSS is denied and there is no admission to present, and the local credential cannot set `crossed` itself. The host's state file has one owner at a time: `--lease SECONDS` (default 10) is how stale the owner's heartbeat must be before another host may take the file over; a second host started earlier exits with code 3. A host that loses its lease refuses new work and may still record what it was running; if it completes a tool another host had marked interrupted, its verdict replaces the UNKNOWN one and a retry resolves the attempt.

**What a call is bound to (v0.6).** The witness accepts an intent for exactly one action at exactly one executor: the nonce is a digest of the host's key, the tool and its arguments, and the host refuses anything else (403). A request key reused with other arguments raises `RequestKeyReused`. The governor returns a result only when the host's signed report covers its digest; otherwise `OutcomeInvalid`, and the retry fetches the signed one. A HOLD or STOP accepted before the crossing means the tool does not run (`Held`, `Stopped`); a retry of an unfinished call resumes it and never executes twice; a call that completed as a no-effect raises `NoEffect` again; a call whose host died mid-run gets an UNKNOWN verdict after the host restarts (`RuntimeError`), stays charged, and is never run again. Two hosts under one key must share one state file: the one-shot is per key, not per process.

## Transport security: mutual TLS (v0.5)

Without the TLS options the services speak plain HTTP on loopback, as above. With them, each service presents a certificate from the deployment's own authority and admits only clients that present one too; each client pins the authority, checks the server's name and presents its own certificate.

```
# once: the authority and the certificates (keep the .key files private; distribute ca.crt)
python3 plea_gateway/tls.py init pki          # pki/ca.crt ca.key witness.crt .key host.crt .key governor.crt .key

# the services: HTTPS, a client certificate required, only the name "governor" admitted
python3 plea_gateway/witness_service.py --port 8787 --key <witness private hex> --dsn ... --gate-key <gate public hex> \
    --tls-cert pki/witness.crt --tls-key pki/witness.key --tls-ca pki/ca.crt --tls-allow governor
python3 plea_gateway/gate_host.py --port 8900 --tools demo_tools --key <gate private hex> --witness-key <witness public hex> \
    --tls-cert pki/host.crt --tls-key pki/host.key --tls-ca pki/ca.crt --tls-allow governor
```

```python
from plea_gateway import TLSClient
tls = TLSClient('pki/ca.crt', 'pki/governor.crt', 'pki/governor.key')
witness = RemoteWitness('https://127.0.0.1:8787', public_key=WITNESS_PUBLIC_HEX, tls=tls)
host = GateHostClient('https://127.0.0.1:8900', tls=tls)
```

`plea_mcp.py` takes the same three as `--tls-ca`, `--tls-cert`, `--tls-key`. A request without a certificate the authority issued never reaches a handler; a server that is not the pinned one never receives the request; both raise `TransportError`, which is not retried. To rotate a certificate, issue a new one from the same authority and restart that party. To rotate the authority, give each party a bundle of the old and new `ca.crt` during the overlap, move the certificates, then drop the old authority. The certificates are issued for `127.0.0.1` and `localhost` by default; `--san` names other hosts.

Not covered: the connection from each process to PostgreSQL, which is the DSN's business (`sslmode=verify-full` and the server's certificate), and anything behind the gate host.

## Governing an agent's tools

```
python3 mcp/plea_mcp.py --root billing-agent --budget 3 --replacement 1 \
    --witness-url http://127.0.0.1:8787 --gate-key <gate private hex> --admin-dsn postgresql://plea:plea@127.0.0.1:5432/plea \
    --tools demo_tools                       # or:  --upstream "python3 path/to/your_mcp_server.py"
                                             # or:  --gate-host http://127.0.0.1:8900   (v0.4: no key in this process)
                                             # add: --tls-ca pki/ca.crt --tls-cert pki/governor.crt --tls-key pki/governor.key   (v0.5)
```

Point the agent's MCP client at that command. It sees the same tools as before, plus `plea_status`. An identical call is answered from the stored result without running the tool; a call beyond the budget, or on a held or stopped run, is an MCP tool error that says why. The operator controls the run from outside the agent:

```
python3 mcp/plea_ctl.py billing-agent provision --budget 3 --replacement 1      # once, before the agent starts
python3 mcp/plea_ctl.py billing-agent status | hold | stop | recover | audit | provenance
```

`status` prints the budget view; `audit` prints every decision recorded for the root (sequence number, kind, code, operation), in order; `provenance` (v1.2) prints the root's provisioning record and verifies its chain from that anchor and the whole provisioning log.
