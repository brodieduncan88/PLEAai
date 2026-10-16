# Stranger test: PLEA gateway v0.3 README

Goal: following only README.md, make the same governed tool call twice so the tool executes exactly once, with evidence.

## Timeline

- START: `date -u` -> Mon Oct 12 09:31:36 UTC 2026

## Commands, in order

### 1. Read README.md and list bundle (09:31)
`cat bundle/README.md; ls -la bundle/`
Result: README read. Bundle has plea_gateway/, mcp/, tests/, contract/, outputs/, reports.

### 2. Schema init (README "Reproduce" first block) -- 09:32:20 -> 09:32:22
Ran the README's one-liner, but from work/ with `sys.path.insert(0,'<abs bundle path>')` and `PYTHONDONTWRITEBYTECODE=1 python -B` (the README's own command would write `__pycache__` into the bundle; I was told not to modify bundle/):
`python -B -c "import sys; sys.path.insert(0,'$B'); from plea_gateway import Store; s = Store('postgresql://plea:plea@127.0.0.1:5432/plea'); s.init_schema(); s.init_authority()"`
Result: exit 0, no output. (Silent success; I added my own print to confirm.)
- MILESTONE schema installed: Mon Oct 12 09:32:22 UTC 2026

### 3. Discover service flags and constructor signatures (09:32:3x)
`python -B bundle/plea_gateway/witness_service.py --help`
`python -B -c "import inspect, plea_gateway as pg; print(inspect.signature(pg.GateSigner.__init__)) ..."` for GateSigner, Governor, RemoteWitness, Store.
Found: `--key KEY` is optional with no help text; `--gate-key` repeatable. `GateSigner(private_hex=None)` exposes `.private_hex`/`.public_hex`. `Governor(store, witness, root, budget, replacement=0, admin=None, gate=None)`. `RemoteWitness(url, public_key=None, timeout=10)`.

### 4. Generate gate key, start service on 9787 (09:32:56 -> 09:32:58)
`python -B -c "from plea_gateway import GateSigner; g=GateSigner(); write g.private_hex, g.public_hex to gate_private.hex / gate_public.hex"`
`nohup python -B bundle/plea_gateway/witness_service.py --port 9787 --dsn postgresql://plea_witness:witness@127.0.0.1:5432/plea --gate-key $(cat gate_public.hex) > service.log &`  (pid 541; `--key` omitted on purpose to see what happens)
`curl http://127.0.0.1:9787/pubkey`
Result: service logged `{"listening": 9787, "public_key": "17d5c8f6...", "gate_keys": ["54469c19..."]}`; /pubkey returns the same. Service generated its own key when `--key` was omitted.
- MILESTONE service started: Mon Oct 12 09:32:58 UTC 2026

### 5. First governed call + retry, via the README "Minimal use" Python API (09:33:30 -> 09:33:31)
Wrote `work/minimal_use.py`: the README snippet verbatim except (a) `GateSigner(open('gate_private.hex').read())` instead of `GateSigner()` so the gate key matches what the service pins, (b) port 9787, (c) a `charge()` that increments a global EXECUTIONS counter and prints when it runs.
`python -B minimal_use.py`
Result (exit 0):
```
first governed call at Mon Oct 12 09:33:30 UTC 2026
   [charge EXECUTED] #1: order_id=42 amount=10
   returned: {'charged': True, 'order_id': 42, 'amount': 10, 'execution_no': 1}
retry (identical call) at Mon Oct 12 09:33:31 UTC 2026
   returned: {'amount': 10, 'charged': True, 'order_id': 42, 'execution_no': 1}
EXECUTIONS = 1
r1 == r2 -> True
status: {'k': 3, 'm': 1, 'witness': 'ACTIVE', 'business': 'OPEN', ..., 'live': [0, 1, 0], 'accepted': [0, 1, 0], 'attempts': [['a-85822d900f8d0e8c', 'charge:order-42', 'EFFECT', 'n-7869f41956c2', True, True]]}
```
- MILESTONE first governed call: Mon Oct 12 09:33:30 UTC 2026
- MILESTONE retry returned stored result, tool executed exactly once (EXECUTIONS = 1): Mon Oct 12 09:33:31 UTC 2026

### 6. Same script again in a fresh process (09:33:55)
`python -B minimal_use.py`
Result: both calls returned the stored result; `EXECUTIONS = 0` in the new process (the tool never ran); `Governor(..., admin=...)` did not complain that root `billing-agent` already existed. Store still shows exactly one attempt.

### 7. Operator CLI from the README (09:34:10)
`python -B bundle/mcp/plea_ctl.py billing-agent status` -> same JSON as gov.status(): one attempt, EFFECT, accepted [0,1,0].
`python -B bundle/mcp/plea_ctl.py billing-agent audit` -> one line: `1 APPLIED RESERVATION_COMMITTED ["RESERVE", "a-85822d900f8d0e8c", "charge:order-42"]`
Both worked with no flags (defaults from the README's env-var sentence).

### 8. Teardown
`kill <service pid>` -> Mon Oct 12 09:35:39 UTC 2026. Port 9787 confirmed closed.

## Friction points (what I expected / what I found / cost)

1. **Service `--key <hex>`: no definition, no way to make one.** README: `--key <hex>`, as if required. Expected: a sentence saying what it is (the service's Ed25519 signing key?), its format (32 bytes / 64 hex chars?), how to generate it. Found: `--help` has no description for it and marks it optional. I omitted it; the service started and printed a self-generated `public_key`. The README never says omitting it is allowed, nor that the key is then ephemeral (changes on restart), nor what `RemoteWitness(url)` with no `public_key` does about "pinning" (it evidently fetched the key from /pubkey, i.e. trust on first use). Cost: ~1 min of poking; would have been longer had I not tried omitting it.

2. **The gate key cannot be wired up in the order the README presents it.** "Minimal use" starts with `gate = GateSigner()` (a fresh random key), and only *afterwards* shows the service command needing `--gate-key <gate public hex>`. Expected: a stated order (make gate key -> start service pinning its public half -> build Governor with the *same* key) and the API to do it. Found: nothing in the README says `GateSigner` accepts a `private_hex`, or that `.private_hex`/`.public_hex` exist. I had to run `inspect.signature(GateSigner.__init__)` and `dir()` to discover it. Cost: ~1.5 min. A reader who literally runs the snippet as printed will get a receipt/evidence failure or a mismatched gate key.

3. **Schema one-liner assumptions.** `sys.path.insert(0,'.')` silently assumes cwd is the bundle root; no `-B`, so it writes `__pycache__/` into `plea_gateway/` (I was told not to modify the bundle, so I used an absolute path and `PYTHONDONTWRITEBYTECODE=1`); prints nothing on success; doesn't say it is idempotent / safe to re-run. Cost: ~0.5 min.

4. **What does `attempt()` return, and what should I see?** Expected: one line of expected output for the two calls. Found: nothing. I had to infer that it returns the governed function's return value, and that on DUPLICATE it is the *stored* (JSON round-tripped) value: the dict's key order changed on the retry, which is the only visible sign it came from the store. Cost: ~0.5 min (I built my own counter to be sure).

5. **Root creation idempotence not stated.** Expected: a note on whether `Governor(..., admin=Store(...))` fails if the root already exists. Found: it is idempotent, but only by trying (step 6). Cost: ~0.5 min.

6. **`audit` shows one row while `status` shows an accepted EFFECT.** Not investigated (not needed for the goal), but the README doesn't say what the audit view contains or which credential it reads with, so I can't tell whether one row is right. Cost: 0 (noted only).

7. **Reproduce section's last line points outside the bundle:** `cd ../../budget_v3_1/oracle && PYTHONPATH=../../gateway/tests ...`. There is no `budget_v3_1/` in the bundle (only `contract/`). Not needed for the goal; would block anyone trying to run the full Reproduce list. Cost: 0.

8. **Ports/DSNs:** all good. The defaults in the README matched the environment; `plea_ctl.py` worked with no flags. I swapped 8787 -> 9787 in two places without trouble.

I did not open any source file. Everything I needed beyond the README came from `--help` and `inspect.signature`/`dir()` on the public API.

## Verdict

**Goal succeeded: YES.** Same governed call made twice (`gov.attempt('charge:order-42', charge, order_id=42, amount=10)`); the tool ran exactly once (EXECUTIONS = 1 in-process; 0 in a second process), both calls returned the same result, store shows one attempt (`EFFECT`, accepted [0,1,0]).

**Elapsed:** first `date -u` 09:31:36 UTC -> last `date -u` (below) ~4 minutes. Of that, roughly 2.5 minutes went to the README's gaps around keys.

**Three biggest friction points:**
1. `--key <hex>` for the service is undefined and ungeneratable from the README (friction 1).
2. The gate key lifecycle is backwards in the README and the API to persist/reload a gate key (`GateSigner(private_hex)`, `.private_hex`, `.public_hex`) is undocumented (friction 2).
3. No expected output / return-value description for the two-call demonstration, and the schema one-liner's cwd + `__pycache__` assumptions (frictions 3 and 4).

**Exact README changes I would make:**
- In "Minimal use", replace the first two lines with a key lifecycle, in order:
  ```python
  gate = GateSigner()                         # once; keep gate.private_hex somewhere safe
  # start the service pinning gate.public_hex (see below), then in every process:
  gate = GateSigner(private_hex=SAVED_HEX)    # the same key the service pins
  ```
  and add the sentence: "`GateSigner` exposes `.private_hex` and `.public_hex`; the service must be started with `--gate-key <gate.public_hex>` *before* the Governor runs."
- For the service command, define `--key`: "`--key` is the service's Ed25519 private key as 64 hex characters (`python3 -c 'import secrets; print(secrets.token_hex(32))'`, or whatever the real format is). If omitted the service generates one and prints its public key; it changes on every restart, so `RemoteWitness` clients pin a stale key." Also say what `RemoteWitness(url)` does without `public_key` (fetches /pubkey on first use) and show `RemoteWitness(url, public_key=...)` for real pinning.
- Add a one-line order of operations above the code: "1. schema one-liner (owner DSN) 2. start the service 3. run the snippet."
- Schema one-liner: say "run from the bundle root", add `-B`, and add "prints nothing on success; safe to re-run."
- After the two `gov.attempt` lines, add the expected output, e.g. "`attempt` returns the function's return value; the second call returns the stored value from the first (JSON round-tripped) and does not call `charge`. `gov.status()['attempts']` shows one attempt with phase `EFFECT`." Also: "Constructing `Governor` with `admin=` on an existing root is a no-op."
- Say what `plea_ctl.py <root> audit` lists (and with which credential), so one row vs. one accepted attempt is not a surprise.
- Fix or drop the `cd ../../budget_v3_1/oracle` line, which refers to a path outside this bundle.

- FINISH: `date -u` -> Mon Oct 12 09:35:39 UTC 2026

### Teardown check (Mon Oct 12 09:36:06 UTC 2026)
Service pid 541 confirmed gone (`ps -p` / `pgrep -af witness_service`). `find bundle -name __pycache__` -> 0 dirs; bundle left unmodified.
