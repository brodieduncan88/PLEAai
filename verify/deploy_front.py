"""One verification service with a front door, on one machine, for the demonstration and the tests.

FrontServices(directory) is deploy.Services with three differences:

  - the witness service and the gate host admit one client name, `frontdoor`, and no other.  The `governor`
    certificate that deploy.py also issues is a real certificate of the same authority; here it is refused, which is
    what a job certificate meets too;
  - a third process, front_door.py, holds the gateway's database credential and the `frontdoor` certificate;
  - the assistant's side is a job folder (enrol) holding the service's address and the job's certificate, used
    through front_client.py or through the MCP server (Mcp).

What one machine does not show is what deploy.py says of itself: every party runs under one operating-system
account, so the separation is by process and credential, not by machine.
"""
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from plea_gateway import tls as TLS                  # noqa: E402
import deploy                                        # noqa: E402
import front_ctl                                     # noqa: E402
from front_client import FrontClient                 # noqa: E402

PY = sys.executable
CLEAN_ENV = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}          # what the assistant's side is started with: no service address, no credential


class FrontServices(deploy.Services):
    def __init__(self, directory, witness_port: int = 8971, host_port: int = 8972, front_port: int = 8973):
        super().__init__(directory, witness_port, host_port)
        self.ports['front'] = front_port
        pki = pathlib.Path(self.pki['ca']).parent
        self.ca_cert, self.ca_key = pathlib.Path(self.pki['ca']).read_bytes(), pathlib.Path(self.pki['ca_key']).read_bytes()
        for name, role, san in (('front', 'server', ('127.0.0.1', 'localhost')), ('frontdoor', 'client', ())):
            key, cert = TLS.issue(self.ca_key, self.ca_cert, name, role, san, 3)
            (pki / f'{name}.key').write_bytes(key); (pki / f'{name}.key').chmod(0o600); (pki / f'{name}.crt').write_bytes(cert)
            self.pki[name] = (str(pki / f'{name}.crt'), str(pki / f'{name}.key'))
        self.url = f'https://127.0.0.1:{front_port}'
        (self.dir / 'state.json').write_text(json.dumps({'ports': self.ports, 'pki': self.pki, 'keys': self.keys}, indent=1) + '\n')

    def _tls(self, name) -> list:
        return ['--tls-cert', self.pki[name][0], '--tls-key', self.pki[name][1], '--tls-ca', self.pki['ca'], '--tls-allow', 'frontdoor']

    def start_front(self, rate: int = 120, sweep_after: float = 3600.0, sweep_every: float = 30.0) -> None:
        """Amendment 9: the front door's look for runs left pending waits an hour here unless a test asks otherwise, so that tests
        that leave a run pending on purpose see it as they left it.  The front door's own default is SWEEP_AFTER."""
        cmd = [PY, '-B', str(HERE / 'front_door.py'), '--home', str(self.home), '--port', str(self.ports['front']), '--local-dsn', deploy.LOCAL_DSN,
               '--witness-url', f'https://127.0.0.1:{self.ports["witness"]}', '--witness-key', self.keys['witness'],
               '--gate-host', f'https://127.0.0.1:{self.ports["host"]}', '--gate-key', self.keys['gate'], '--engineer-key', self.keys['engineer'],
               '--tls-cert', self.pki['front'][0], '--tls-key', self.pki['front'][1], '--tls-ca', self.pki['ca'],
               '--upstream-cert', self.pki['frontdoor'][0], '--upstream-key', self.pki['frontdoor'][1], '--rate', str(rate),
               '--sweep-after', str(sweep_after), '--sweep-every', str(sweep_every)]
        self.procs['front'] = subprocess.Popen(cmd, stdout=open(self.dir / 'front.log', 'a'), stderr=subprocess.STDOUT)
        self._await('front')

    def stop_front(self) -> None:
        p = self.procs.get('front')
        if p is not None and p.poll() is None:
            p.kill(); p.wait(timeout=5)

    def start(self, crash_at: str | None = None, rate: int = 120) -> 'FrontServices':
        super().start(crash_at); self.start_front(rate); return self

    # ------------------------------------------------------------------ the engineer's side
    def enrol(self, job: str, baseline_hash: str, reason: str | None = None) -> pathlib.Path:
        """Enrol a job and return its folder: all the assistant's side is given."""
        out = self.dir / 'jobs' / job
        front_ctl.enrol(self.home, job, baseline_hash, self.engineer, self.ca_cert, self.ca_key, self.url, out, reason, days=3)
        return out

    def rebind(self, job: str, new_hash: str) -> dict:
        return front_ctl.rebind(self.home, job, new_hash, self.engineer)

    def revoke(self, job: str) -> dict:
        return front_ctl.revoke(self.home, job, self.engineer)

    def record(self, baseline_hash: str, journals=(), checkpoint: bool = True) -> dict:
        return front_ctl.record(self.home, baseline_hash, self.engineer, self.keys['witness'], self.keys['gate'], journals,
                                checkpointer=self.checkpointer() if checkpoint else None)

    # ------------------------------------------------------------------ the assistant's side
    def client(self, job_dir) -> FrontClient:
        return FrontClient(job_dir)

    def cli(self, job_dir, action: str, design=None) -> tuple[int, str]:
        """front_client.py as an assistant's shell would run it: (exit status, what it printed)."""
        cmd = [PY, '-B', str(HERE / 'front_client.py'), '--job-dir', str(job_dir), action]
        if design is not None:
            f = pathlib.Path(job_dir).parent / f'{pathlib.Path(job_dir).name}_design.json'; f.write_text(json.dumps(design)); cmd.append(str(f))
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=CLEAN_ENV)
        return out.returncode, out.stdout + out.stderr

    def mcp(self, job_dir, era: str = 'legacy', version: str | None = None) -> 'Mcp':
        return Mcp(job_dir, era, version)


class Mcp:
    """An MCP host's end of the stdio connection to plea_verify_mcp.py, for tests and the demonstration.

    era='legacy' opens with the `initialize` handshake; era='modern' sends the protocol version with every request;
    era='raw' sends nothing first.  The server is started with an empty environment: it is given the job folder only."""

    def __init__(self, job_dir, era: str = 'legacy', version: str | None = None):
        self.proc = subprocess.Popen([PY, '-B', str(HERE / 'plea_verify_mcp.py'), '--job-dir', str(job_dir)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, bufsize=1, env=CLEAN_ENV)
        self.era, self._id = era, 0
        self.version = version or ('2026-07-28' if era == 'modern' else '2025-11-25')
        self.opened = None
        if era == 'legacy':
            self.opened = self.rpc('initialize', {'protocolVersion': self.version, 'capabilities': {}, 'clientInfo': {'name': 'test-host', 'version': '0'}})
            self.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})

    def send(self, msg) -> None:
        self.proc.stdin.write((msg if isinstance(msg, str) else json.dumps(msg)) + '\n'); self.proc.stdin.flush()

    def read(self) -> dict:
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError('the MCP server closed its output: ' + self.proc.stderr.read()[-300:])
        return json.loads(line)

    def rpc(self, method: str, params: dict | None = None) -> dict:
        """The whole reply message (so a test can look at `error` as well as `result`)."""
        self._id += 1
        params = dict(params or {})
        if self.era == 'modern':
            params['_meta'] = {'io.modelcontextprotocol/protocolVersion': self.version, 'io.modelcontextprotocol/clientCapabilities': {},
                               'io.modelcontextprotocol/clientInfo': {'name': 'test-host', 'version': '0'}}
        self.send({'jsonrpc': '2.0', 'id': self._id, 'method': method, 'params': params})
        reply = self.read()
        if reply.get('id') != self._id:
            raise RuntimeError(f'reply to another request: {reply}')
        return reply

    def tools(self) -> list:
        return self.rpc('tools/list')['result']['tools']

    def call(self, name: str, arguments=None) -> dict:
        """The tool result: {content, isError, structuredContent}.  A protocol error is returned as {'error': ...}."""
        reply = self.rpc('tools/call', {'name': name, 'arguments': {} if arguments is None else arguments})
        return reply['result'] if 'result' in reply else {'error': reply['error']}

    def close(self) -> int:
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            return self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill(); return self.proc.wait(timeout=5)


def text_of(result: dict) -> str:
    """The first text block of a tool result: what a host shows."""
    return next((c.get('text', '') for c in result.get('content', []) if c.get('type') == 'text'), '')
