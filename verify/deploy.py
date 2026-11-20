"""One verification service on one machine, for the demonstration, the tests and the trials.

Services(directory) makes a fresh deployment under `directory`: a certificate authority, new witness and gate keys,
the responsible engineer's key, and VERIFY_HOME.  start() runs the witness service (v1.2.1 with the readings of
verification Amendments 10 and 11), the v1.2.1 gate host, unchanged, and a mailbox standing in for the engineer's
(Amendment 11), under mutual TLS, with the gate host loading verify_tools.  courier() runs one pass of the courier (Amendment 11), which reads
only the witness and delivers to the mailbox.  client_config() writes what an assistant's workspace
needs to call verify_client.py: the gateway database credential, the client certificate, the public keys and a copy
of the signed baseline.

What one machine does not show.  Here the gate, the witness, the database, the engineer's key and the assistant all
run under one operating-system account, so the separation between them is by process and credential, not by machine.
An assistant with a shell on this machine could read the keys.  A real deployment puts everything in `home`, the
keys and the control credential on a machine the assistant cannot reach.  The same is so of the courier and the mailbox:
here this code makes their keys, writes them to files in the deployment's folder, and starts them under the same account,
so the mailbox is the engineer's in name only.  Its receipts show what the mailbox process stored, not that anyone read it.
"""
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from plea_gateway import GateSigner, Signer          # noqa: E402
from plea_gateway import tls as TLS                  # noqa: E402
import verify_ctl                                    # noqa: E402

PY = sys.executable
WITNESS_DSN = os.environ.get('PLEA_WITNESS_DSN', 'postgresql://plea_witness:witness@127.0.0.1:5432/plea')
LOCAL_DSN = os.environ.get('PLEA_LOCAL_DSN', 'postgresql://plea_local:local@127.0.0.1:5432/plea')


class Services:
    def __init__(self, directory, witness_port: int = 8971, host_port: int = 8972, attach: bool = False, mailbox_port: int = 8974):
        """attach=True: use a deployment another process is running in `directory` (its engineer's key, its public keys,
        its home), to baseline, write client configurations, build records and read the inbox.  It starts nothing."""
        self.dir = pathlib.Path(directory)
        self.home = self.dir / 'home'
        self.procs = {}
        self.host_stopped_at = None
        if attach:
            state = json.loads((self.dir / 'state.json').read_text())
            self.ports, self.pki, self.keys = state['ports'], state['pki'], state['keys']
            self.engineer = verify_ctl.load_key(self.dir / 'engineer.key')
            return
        shutil.rmtree(self.dir, ignore_errors=True); self.dir.mkdir(parents=True)
        (self.home / 'baselines').mkdir(parents=True); (self.home / 'inbox').mkdir()
        self.ports = {'witness': witness_port, 'host': host_port, 'mailbox': mailbox_port}
        self.pki = TLS.init_pki(self.dir / 'pki', servers=('witness', 'host', 'mailbox'), clients=('governor', 'keeper', 'courier'), ca_name='verification-demo-ca', days=3)   # keeper: reads checkpoints (Amendment 10); courier and mailbox (Amendment 11)
        self.witness, self.gate = Signer(), GateSigner()
        self.engineer = verify_ctl.keygen(self.dir / 'engineer.key')
        import mailbox_service
        self.courier_key, self.mailbox_key = mailbox_service.MailboxKey(), mailbox_service.MailboxKey()      # the courier's and the mailbox's (Amendment 11), made here by the deployment
        (self.dir / 'courier.key').write_text(self.courier_key.private_hex + '\n'); (self.dir / 'mailbox.key').write_text(self.mailbox_key.private_hex + '\n')
        self.keys = {'witness': self.witness.public_hex, 'gate': self.gate.public_hex, 'engineer': self.engineer.public_hex,
                     'courier': [self.courier_key.public_hex], 'mailbox': [self.mailbox_key.public_hex]}
        (self.dir / 'state.json').write_text(json.dumps({'ports': self.ports, 'pki': self.pki, 'keys': self.keys}, indent=1) + '\n')   # public keys and paths only

    def _tls(self, name) -> list:
        return ['--tls-cert', self.pki[name][0], '--tls-key', self.pki[name][1], '--tls-ca', self.pki['ca'], '--tls-allow', 'governor']

    def _await(self, name) -> None:
        proc, port = self.procs[name], self.ports[name]
        for _ in range(400):
            if proc.poll() is not None:
                raise RuntimeError(f'{name} exited with {proc.returncode}; see {self.dir / (name + ".log")}')
            try:
                socket.create_connection(('127.0.0.1', port), timeout=0.5).close(); time.sleep(0.2); return
            except OSError:
                time.sleep(0.05)
        raise RuntimeError(f'{name} did not come up')

    def start_witness(self) -> None:
        cmd = [PY, '-B', str(HERE.parent / 'plea_gateway' / 'witness_service.py'), '--port', str(self.ports['witness']), '--dsn', WITNESS_DSN,
               '--key', self.witness.private_hex, '--gate-key', self.gate.public_hex] + self._tls('witness') + ['--tls-allow-read', 'keeper', '--tls-allow-chain', 'courier']   # they read (the keeper checkpoints, the courier the chain); they cannot write
        self.procs['witness'] = subprocess.Popen(cmd, stdout=open(self.dir / 'witness.log', 'a'), stderr=subprocess.STDOUT)
        self._await('witness')

    def start_host(self, crash_at: str | None = None, extra_env: dict | None = None) -> None:
        if self.host_stopped_at is not None:
            time.sleep(max(0.0, 1.5 - (time.time() - self.host_stopped_at)))       # let a dead owner's lease (1 s) expire
        env = dict(os.environ, VERIFY_HOME=str(self.home), VERIFY_ENGINEER_KEYS=self.engineer.public_hex); env.pop('PLEA_CRASH_AT', None)
        if crash_at:
            env['PLEA_CRASH_AT'] = crash_at
        env.update(extra_env or {})                                     # Amendment 12: a test may point the sandbox at control groups that do not exist, to show a check is then not run
        cmd = [PY, '-B', str(HERE.parent / 'plea_gateway' / 'gate_host.py'), '--port', str(self.ports['host']), '--tools', 'verify_tools', '--key', self.gate.private_hex,
               '--state', str(self.dir / 'gate_host.sqlite'), '--lease', '1.0', '--witness-key', self.witness.public_hex] + self._tls('host')
        self.procs['host'] = subprocess.Popen(cmd, cwd=str(HERE), stdout=open(self.dir / 'host.log', 'a'), stderr=subprocess.STDOUT, env=env)
        self._await('host')

    def stop_host(self):
        p = self.procs.get('host'); code = None
        if p is not None:
            if p.poll() is None:
                p.kill()
            code = p.wait(timeout=5)
        self.host_stopped_at = time.time()
        return code

    def start_mailbox(self) -> None:
        """The mailbox (Amendment 11): a key and folder of its own, outside the service's home; it admits the courier only.  In
        the demonstration its key is made by this deployment and it runs under the service's account (see the module's note)."""
        cmd = [PY, '-B', str(HERE / 'mailbox_service.py'), 'serve', '--port', str(self.ports['mailbox']), '--dir', str(self.dir / 'mailbox'),
               '--key-file', str(self.dir / 'mailbox.key'), '--name', 'engineer-mailbox', '--courier-key', self.keys['courier'][0],
               '--tls-cert', self.pki['mailbox'][0], '--tls-key', self.pki['mailbox'][1], '--tls-ca', self.pki['ca'], '--tls-allow', 'courier']
        self.procs['mailbox'] = subprocess.Popen(cmd, stdout=open(self.dir / 'mailbox.log', 'a'), stderr=subprocess.STDOUT)
        self._await('mailbox')

    def stop_mailbox(self) -> None:
        p = self.procs.get('mailbox')
        if p is not None and p.poll() is None:
            p.kill(); p.wait(timeout=5)

    def start(self, crash_at: str | None = None) -> 'Services':
        self.start_witness(); self.start_host(crash_at); self.start_mailbox(); return self

    def stop(self) -> None:
        for p in self.procs.values():
            if p.poll() is None:
                p.kill(); p.wait(timeout=5)
        time.sleep(0.2)

    # ------------------------------------------------------------------ the engineer's and the assistant's sides
    def baseline(self, source, draft: dict, runs: int = 1000, alongside_reason: str | None = None) -> dict:
        return verify_ctl.make_baseline(self.home, source, draft, self.engineer, runs, alongside_reason=alongside_reason)    # Amendment 9: a second one needs a reason

    def client_config(self, workspace, baseline_hash: str) -> pathlib.Path:
        """Write WORKSPACE/.verify/ (config, baseline copy, journal) and return the config path."""
        d = pathlib.Path(workspace) / '.verify'; d.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.home / 'baselines' / baseline_hash / 'baseline.json', d / 'baseline.json')
        cfg = {'local_dsn': LOCAL_DSN, 'witness_url': f'https://127.0.0.1:{self.ports["witness"]}', 'witness_keys': [self.keys['witness']],
               'gate_url': f'https://127.0.0.1:{self.ports["host"]}', 'gate_key': self.keys['gate'], 'engineer_key': self.keys['engineer'],
               'tls': {'ca': self.pki['ca'], 'cert': self.pki['governor'][0], 'key': self.pki['governor'][1]}, 'baseline': 'baseline.json', 'journal': 'submissions.jsonl'}
        (d / 'config.json').write_text(json.dumps(cfg, indent=1) + '\n')
        return d / 'config.json'

    def submit(self, config, design) -> tuple[int, str]:
        """Run the assistant's command as the assistant would: (exit status, what it printed)."""
        f = pathlib.Path(config).parent / 'design_submitted.json'; f.write_text(json.dumps(design))
        out = subprocess.run([PY, '-B', str(HERE / 'verify_client.py'), '--config', str(config), 'submit', str(f)], capture_output=True, text=True, timeout=120)
        return out.returncode, out.stdout + out.stderr

    def checkpointer(self):
        """Asks the witness, with the keeper's certificate, for the checkpoint a record carries.  (Amendment 10.)"""
        return verify_ctl.witness_checkpointer(f'https://127.0.0.1:{self.ports["witness"]}', self.pki['ca'], *self.pki['keeper'])

    def checkpoint(self, root: str, nonce: str | None = None, at: int | None = None) -> dict:
        """A checkpoint of one budget, as someone outside the service would fetch it.  (Amendment 10.)"""
        import checkpoints
        return checkpoints.fetch(f'https://127.0.0.1:{self.ports["witness"]}', self.pki['ca'], *self.pki['keeper'], root, nonce, at)

    def courier_config(self, roots, stall_after: float = 900, name: str = 'courier', page: int = 200) -> pathlib.Path:
        """The courier's configuration (Amendment 11): the witness's readings with the courier's certificate, the keys it believes,
        and one watch for each budget, delivering to the mailbox.  Nothing in it names the service's home or database."""
        cfg = {'name': name, 'key_file': str(self.dir / 'courier.key'), 'state_dir': str(self.dir / name), 'stall_after': stall_after, 'page': page,
               'witness_url': f'https://127.0.0.1:{self.ports["witness"]}', 'ca': self.pki['ca'], 'cert': self.pki['courier'][0], 'key': self.pki['courier'][1],
               'witness_keys': [self.keys['witness']], 'gate_keys': [self.keys['gate']],
               'watches': [{'root': r, 'mailbox_url': f'https://127.0.0.1:{self.ports["mailbox"]}', 'mailbox_keys': self.keys['mailbox']} for r in roots]}
        p = self.dir / f'{name}.json'; p.write_text(json.dumps(cfg, indent=1) + '\n')
        return p

    def courier(self, roots, stall_after: float = 900, name: str = 'courier', page: int = 200) -> tuple[int, dict]:
        """One pass of the courier, in its own process, as the engineer would run it: (exit status, its summary)."""
        out = subprocess.run([PY, '-B', str(HERE / 'courier.py'), 'run', '--config', str(self.courier_config(roots, stall_after, name, page))], capture_output=True, text=True, timeout=120)
        try:
            return out.returncode, json.loads(out.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return out.returncode, {'error': (out.stdout + out.stderr)[-500:]}

    def deliveries(self, name: str = 'courier') -> dict:
        return {'log': self.dir / name / 'deliveries.jsonl', 'courier': self.keys['courier'], 'mailbox': self.keys['mailbox']}

    def record(self, baseline_hash: str, journals=(), checkpoint: bool = True, deliveries: bool = False) -> dict:
        return verify_ctl.record(self.home, baseline_hash, self.engineer, self.keys['witness'], self.keys['gate'], journals,
                                 checkpointer=self.checkpointer() if checkpoint else None, deliveries=self.deliveries() if deliveries else None)

    def inbox(self, baseline_hash: str) -> list:
        box = self.home / 'inbox' / baseline_hash[:16]
        return sorted(p.name for p in box.glob('*.txt')) if box.exists() else []

    def ledger(self, event: str | None = None) -> list:
        p = self.home / 'ledger.jsonl'
        rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
        return [r for r in rows if event is None or r['event'] == event]
