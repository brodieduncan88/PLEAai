"""Shared pieces for the gateway tests: paths, the three credentials, invariant checks, replay lockstep against the
oracle, and the witness service as a subprocess.

Credentials.  ADMIN_DSN is the owner role (setup, conformance put_state, chaos preparation).  LOCAL_DSN is what a
gateway holds: it cannot apply an acceptance.  WITNESS_DSN is what the witness service holds.

Replay lockstep: the store's audit log is the serialization order the database chose.  Replaying its operations
through the independent oracle (budget_oracle, amendment 3) from initial(k, m) and comparing every recorded
decision kind and observation is the runtime form of B17's lockstep.
"""
import json
import os
import pathlib
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
GATEWAY = HERE.parent
sys.path.insert(0, str(GATEWAY)); sys.path.insert(0, str(HERE))

import hashlib                            # noqa: E402

import budget_oracle as O                 # noqa: E402  the independent oracle, vendored (sha256 6b7646b7...)
from plea_gateway import GateSigner, Signer, Store, nonce_for  # noqa: E402
from plea_gateway import tls as TLS       # noqa: E402  v0.5
from plea_gateway.tls import TLSClient, TLSServer   # noqa: E402

PKI = GATEWAY / 'outputs' / 'pki'         # the test deployment's certificates (v0.5), rebuilt by make_pki()

# The gate's key for tests: fixed, so racers in forked processes can sign reports the service has pinned.
GATE = GateSigner(os.environ.get('PLEA_TEST_GATE_KEY') or hashlib.sha256(b'plea-test-gate-v0.2').hexdigest())
# The witness's key for tests (v0.4): fixed, so a gate host can pin it before the service is up.
WITNESS_KEY = os.environ.get('PLEA_TEST_WITNESS_KEY') or hashlib.sha256(b'plea-test-witness-v0.4').hexdigest()
WITNESS_PUB = Signer(WITNESS_KEY).public_hex

ADMIN_DSN = os.environ.get('PLEA_ADMIN_DSN', 'postgresql://plea:plea@127.0.0.1:5432/plea')
LOCAL_DSN = os.environ.get('PLEA_LOCAL_DSN', 'postgresql://plea_local:local@127.0.0.1:5432/plea')
WITNESS_DSN = os.environ.get('PLEA_WITNESS_DSN', 'postgresql://plea_witness:witness@127.0.0.1:5432/plea')
CONTROL_DSN = os.environ.get('PLEA_CONTROL_DSN', 'postgresql://plea_control:control@127.0.0.1:5432/plea')  # v0.9 control plane
DSN = ADMIN_DSN                           # the name the v0 tests used
PYTHON = sys.executable
WITNESS_OPS = ('ACCEPT_RESERVATION', 'ACCEPT_INTENT', 'RELEASE', 'RECONCILE', 'CROSS')     # v0.7: the crossing is witnessed
CONTROL_OPS = ('HOLD', 'STOP', 'TERMINALISE', 'TERMINAL', 'RECOVER', 'REREGISTER')         # v0.9: the control plane changes modes


def store_for(op, mode: str = 'lock') -> Store:
    """The credential a correct deployment would use for this operation: the witness for the acceptances and the
    crossing, the control plane for the mode changes (HOLD/STOP/.../RECOVER/REREGISTER), the gateway for the rest."""
    if op[0] in WITNESS_OPS:
        return Store(WITNESS_DSN, mode=mode)
    if op[0] in CONTROL_OPS:
        return Store(CONTROL_DSN, mode=mode)
    return Store(LOCAL_DSN, mode=mode)


def fresh_root(store: Store, root_id: str, k: int, m: int) -> None:
    with store.connect() as conn:
        conn.execute('DELETE FROM roots WHERE root_id = %s', (root_id,)); conn.commit()
    store.new_root(root_id, k, m)


def bound(root: str, aid: str, tool: str, arguments: dict, executor: str | None = None) -> str:
    """v0.6: the nonce that binds this action to the test gate key (or another executor)."""
    return nonce_for(root, aid, executor or GATE.public_hex, tool, arguments)


def admitted(admin: Store, w, root: str, aid: str, q: str, nonce: str):
    """v0.7: the manual lifecycle up to the admission: RESERVE, ACCEPT_RESERVATION, TOKEN, START, ACCEPT_INTENT, RECEIPT,
    then CROSS through the witness.  Returns (reservation receipt, intent receipt, admission receipt)."""
    admin.apply(root, ('RESERVE', aid, q)); d, rr = w.accept_reservation(root, aid); assert d.kind == 'APPLIED', d
    admin.apply(root, ('TOKEN', aid)); admin.apply(root, ('START', aid, nonce)); d, ri = w.accept_intent(root, aid); assert d.kind == 'APPLIED', d
    admin.apply(root, ('RECEIPT', aid)); d, adm = w.cross(root, aid); assert d.kind == 'APPLIED', d
    return rr, ri, adm


def invariants_ok(obs: dict) -> tuple[bool, str]:
    """I1 and I2 on an observation, plus I3 and I6 (what a reader can check without the attempt facts)."""
    r, c, n = obs['live']; ra, ca, _ = obs['accepted']; k, m = obs['k'], obs['m']
    if c > k + m: return False, f'I1 live C {c} > k+m {k + m}'
    if r + c - min(n, m) > k: return False, f'I2 R+C-credit {r + c - min(n, m)} > k {k}'
    if ca > c or ra + ca > r + c: return False, 'I3 accepted view exceeds live view'
    if obs['reregistered'] and obs['business'] == 'OPEN': return False, 'I6 re-registered OPEN'
    return True, 'ok'


def _tuple_op(op):
    return tuple(_tuple_op(x) if isinstance(x, list) else x for x in op)


def _norm(obs):
    return json.loads(json.dumps(obs))


def replay_lockstep(store: Store, root_id: str, k: int, m: int) -> tuple[bool, str, int]:
    """Replay the audit log through the oracle.  Returns (ok, detail, decisions replayed)."""
    state = O.initial(k, m)
    log, final = store.audit_snapshot(root_id)      # v0.6: the log and the current observation from one snapshot
    for d in log:
        op = _tuple_op(d['op'])
        decision, state = O.step(state, op)
        if decision.kind != d['kind']:
            return False, f"seq {d['seq']} {op}: store {d['kind']} oracle {decision.kind}", len(log)
        if _norm(O.observe(state)) != d['observation']:
            return False, f"seq {d['seq']} {op}: observation differs", len(log)
    if log and final != log[-1]['observation']:
        return False, 'the current state differs from the last recorded observation', len(log)
    if not log and final != _norm(O.observe(state)):
        return False, 'the initial state differs from the oracle', len(log)
    return True, 'ok', len(log)


def write_output(name: str, payload: dict) -> None:
    out = GATEWAY / 'outputs' / name
    out.write_text(json.dumps(payload, indent=1))


def make_pki(fresh: bool = True) -> dict:
    """The test PKI (v0.5).  Authority A ('plea-test-ca'): server certificates for witness and host (SAN 127.0.0.1,
    localhost), client certificates for governor and stranger, and a server certificate for another name
    ('elsewhere', SAN elsewhere.example).  An impostor authority B ('impostor-ca') with its own witness, host and
    governor.  Returns the paths; paths['impostor'] holds B's."""
    import shutil
    if fresh and PKI.exists():
        shutil.rmtree(PKI)
    paths = TLS.init_pki(PKI, servers=('witness', 'host'), clients=('governor', 'stranger'), ca_name='plea-test-ca')
    ca_key, ca_cert = (PKI / 'ca.key').read_bytes(), (PKI / 'ca.crt').read_bytes()
    k, c = TLS.issue(ca_key, ca_cert, 'elsewhere', 'server', ('elsewhere.example',))
    (PKI / 'elsewhere.key').write_bytes(k); (PKI / 'elsewhere.crt').write_bytes(c)
    paths['elsewhere'] = (str(PKI / 'elsewhere.crt'), str(PKI / 'elsewhere.key'))
    paths['impostor'] = TLS.init_pki(PKI / 'impostor', servers=('witness', 'host'), clients=('governor',), ca_name='impostor-ca')
    return paths


def client_tls(paths: dict, name: str = 'governor', ca: str | None = None) -> TLSClient:
    return TLSClient(ca or paths['ca'], *paths[name])


def server_tls(paths: dict, name: str, allow=('governor',), ca: str | None = None) -> TLSServer:
    return TLSServer(*paths[name], ca or paths['ca'], tuple(allow))


def _tls_args(tls: TLSServer | None) -> list:
    if tls is None:
        return []
    args = ['--tls-cert', tls.cert, '--tls-key', tls.key, '--tls-ca', tls.ca]
    for n in tls.allow:
        args += ['--tls-allow', n]
    return args


def _poll(url: str, tls: TLSServer | None, client: TLSClient | None):
    """One readiness probe.  With a client, GET /pubkey through it; under TLS without one, a TCP connect only."""
    if tls is not None and client is None:
        u = urllib.parse.urlparse(url); socket.create_connection((u.hostname, u.port), timeout=1).close(); return {}
    with urllib.request.urlopen(url + '/pubkey', timeout=1, context=client.context() if client else None) as r:
        return json.load(r)


class WitnessService:
    """The witness service as a subprocess, for tests.  Same key across restarts when `key` is given."""

    def __init__(self, port: int, key: str | None = None, chaos: bool = False, gate_keys=(GATE.public_hex,),
                 tls: TLSServer | None = None, client: TLSClient | None = None):
        """tls (v0.5): serve HTTPS with these; client: the certificate the readiness probe presents."""
        self.port, self.key, self.chaos, self.proc = port, key, chaos, None
        self.gate_keys = tuple(gate_keys); self.tls, self.client = tls, client

    @property
    def url(self) -> str:
        return f'{"https" if self.tls else "http"}://127.0.0.1:{self.port}'

    def start(self, wait: float = 10.0) -> dict:
        cmd = [PYTHON, '-B', str(GATEWAY / 'plea_gateway' / 'witness_service.py'), '--port', str(self.port), '--dsn', WITNESS_DSN]
        if self.key: cmd += ['--key', self.key]
        if self.chaos: cmd.append('--chaos')
        for g in self.gate_keys: cmd += ['--gate-key', g]
        cmd += _tls_args(self.tls)
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        deadline = time.time() + wait
        while time.time() < deadline:
            try:
                return _poll(self.url, self.tls, self.client)
            except Exception:
                if self.proc.poll() is not None:
                    raise RuntimeError(f'witness service exited with {self.proc.returncode}')
                time.sleep(0.05)
        raise RuntimeError('witness service did not come up')

    def wait_dead(self, timeout: float = 10.0) -> int:
        return self.proc.wait(timeout=timeout)

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.kill(); self.proc.wait(timeout=5)


class GateHost:
    """The gate host as a subprocess, for tests.  Pins the test witness key; holds the test gate key unless told otherwise."""

    def __init__(self, port: int, tools: str = 'demo_tools', key: str | None = None, witness_keys=(WITNESS_PUB,), state: str | None = None,
                 ledger: str | None = None, tls: TLSServer | None = None, client: TLSClient | None = None, lease: float = 1.0):
        self.port, self.tools, self.key, self.witness_keys, self.proc = port, tools, key or GATE.private_hex, tuple(witness_keys), None
        self.state = state or str(GATEWAY / 'outputs' / f'gate_host_{port}.sqlite')
        self.ledger = ledger or str(GATEWAY / 'outputs' / 'host_ledger.jsonl')     # explicit: never inherited from the environment (amendment 1)
        self.tls, self.client, self.lease, self.stopped_at = tls, client, lease, None   # v0.7: a short lease, so a restart after a kill can take the state over

    @property
    def url(self) -> str:
        return f'{"https" if self.tls else "http"}://127.0.0.1:{self.port}'

    def start(self, wait: float = 10.0, fresh: bool = True) -> dict:
        if fresh:
            pathlib.Path(self.state).unlink(missing_ok=True)
        elif self.stopped_at is not None:                                       # let the previous owner's lease expire
            time.sleep(max(0.0, self.lease + 0.3 - (time.time() - self.stopped_at)))
        cmd = [PYTHON, '-B', str(GATEWAY / 'plea_gateway' / 'gate_host.py'), '--port', str(self.port), '--tools', self.tools,
               '--key', self.key, '--state', self.state, '--lease', str(self.lease)]
        for w in self.witness_keys: cmd += ['--witness-key', w]
        cmd += _tls_args(self.tls)
        self.proc = subprocess.Popen(cmd, cwd=str(GATEWAY / 'mcp'), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                     env=dict(os.environ, PLEA_LEDGER=self.ledger))
        deadline = time.time() + wait
        while time.time() < deadline:
            try:
                return _poll(self.url, self.tls, self.client)
            except Exception:
                if self.proc.poll() is not None:
                    raise RuntimeError(f'gate host exited with {self.proc.returncode}')
                time.sleep(0.05)
        raise RuntimeError('gate host did not come up')

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.kill(); self.proc.wait(timeout=5)
        self.stopped_at = time.time()
