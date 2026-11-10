#!/usr/bin/env python3
"""The Holdout Vault in one run: three scored attempts, a fourth refused, a signed report checked offline.

    python vault/demo.py            needs PostgreSQL with the PLEA schema and roles (README.md, "Reproduce")

It builds a fresh deployment under outputs/vault_demo/ (new keys and certificates every run), starts the three
services under mutual TLS -- the v1.2.1 witness service and gate host, unchanged, and the vault's front door -- and
then acts as two people: the owner, who seals a 200-row holdout and enrols one submitter with three attempts, and the
submitter, who holds a client certificate and nothing else.  The report and the three public keys are left in
outputs/vault_demo/ so the last step can be repeated by hand:

    python vault/plea_verify.py outputs/vault_demo/report.json --keys outputs/vault_demo/keys.json
"""
import json
import os
import pathlib
import random
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from plea_gateway import GateSigner, Signer          # noqa: E402
from plea_gateway import tls as TLS                  # noqa: E402
import holdout as H                                  # noqa: E402

OUT = HERE.parent / 'outputs' / 'vault_demo'
PORT = {'vault': 8950, 'witness': 8951, 'host': 8952}
WITNESS_DSN = os.environ.get('PLEA_WITNESS_DSN', 'postgresql://plea_witness:witness@127.0.0.1:5432/plea')
LOCAL_DSN = os.environ.get('PLEA_LOCAL_DSN', 'postgresql://plea_local:local@127.0.0.1:5432/plea')
ROWS, CLASSES, PY = 200, ('bird', 'cat', 'dog'), sys.executable


def say(text=''):
    print(text, flush=True)


def wait_for(proc, port, what):
    for _ in range(300):
        if proc.poll() is not None:
            raise SystemExit(f'{what} exited with {proc.returncode}; see {OUT}/{what.replace(" ", "_")}.log')
        try:
            socket.create_connection(('127.0.0.1', port), timeout=0.5).close(); time.sleep(0.2); return
        except OSError:
            time.sleep(0.05)
    raise SystemExit(f'{what} did not come up')


def main():
    shutil.rmtree(OUT, ignore_errors=True); OUT.mkdir(parents=True)
    rng = random.Random(7)
    ids = [f'item-{i:04d}' for i in range(ROWS)]
    truth = [rng.choice(CLASSES) for _ in ids]

    say('OWNER  seals the holdout')
    labels = OUT / 'owner_labels.csv'; labels.write_text('id,label\n' + ''.join(f'{i},{l}\n' for i, l in zip(ids, truth)))
    holdout = H.init(OUT / 'holdout', f'demo-{uuid.uuid4().hex[:6]}', labels, decimals=2, classes=list(CLASSES))
    labels.unlink()                                                # the only copy of the labels is now labels.sealed, mode 0600
    say(f'       {holdout.name}: {ROWS} rows, classes {", ".join(CLASSES)}, score = accuracy to 2 decimal places')
    say(f'       manifest sha256 {holdout.manifest_sha256[:16]}…  (public; carried in every signed result)')

    pki = TLS.init_pki(OUT / 'pki', servers=('witness', 'host', 'vault'), clients=('governor',), ca_name='vault-demo-ca', days=2)
    witness, gate = Signer(), GateSigner()
    tls = lambda name: ['--tls-cert', pki[name][0], '--tls-key', pki[name][1], '--tls-ca', pki['ca']]
    env = dict(os.environ, PLEA_VAULT_HOLDOUT=str(holdout.dir)); env.pop('PLEA_CRASH_AT', None)
    procs = []
    def start(what, port, cmd, cwd=None):
        log = open(OUT / f'{what.replace(" ", "_")}.log', 'w')
        procs.append(subprocess.Popen(cmd, stdout=log, stderr=log, env=env, cwd=cwd)); wait_for(procs[-1], port, what)

    try:
        ctl = lambda *a: json.loads(subprocess.run([PY, '-B', str(HERE / 'vault_ctl.py'), str(holdout.dir), *map(str, a)], capture_output=True, text=True, check=True).stdout)
        report_key = ctl('report-key')['report_key']
        start('witness service', PORT['witness'], [PY, '-B', str(HERE.parent / 'plea_gateway' / 'witness_service.py'), '--port', str(PORT['witness']), '--dsn', WITNESS_DSN,
                                                   '--key', witness.private_hex, '--gate-key', gate.public_hex, '--tls-allow', 'governor'] + tls('witness'))
        start('gate host', PORT['host'], [PY, '-B', str(HERE.parent / 'plea_gateway' / 'gate_host.py'), '--port', str(PORT['host']), '--tools', 'vault_tools', '--key', gate.private_hex,
                                          '--state', str(OUT / 'gate_host.sqlite'), '--witness-key', witness.public_hex, '--tls-allow', 'governor'] + tls('host'), cwd=str(HERE))
        start('front door', PORT['vault'], [PY, '-B', str(HERE / 'vault_service.py'), '--holdout', str(holdout.dir), '--port', str(PORT['vault']), '--local-dsn', LOCAL_DSN,
                                            '--witness-url', f'https://127.0.0.1:{PORT["witness"]}', '--witness-key', witness.public_hex, '--gate-host', f'https://127.0.0.1:{PORT["host"]}',
                                            '--gate-key', gate.public_hex, '--upstream-cert', pki['governor'][0], '--upstream-key', pki['governor'][1]] + tls('vault'))
        keys = {'witness': witness.public_hex, 'gate': gate.public_hex, 'report': report_key}
        (OUT / 'keys.json').write_text(json.dumps(keys, indent=1) + '\n')
        say('       three services are up under mutual TLS: witness, gate host (holds the labels), front door')

        enrolled = ctl('enrol', 'lab-a', '--budget', 3, '--pki', OUT / 'pki', '--days', 2, '--organisation', 'Lab A (demo)')
        say(f'OWNER  enrols submitter "lab-a": 3 attempts, certificate {enrolled["cert_sha256"][:16]}…, budget {enrolled["root"]}')

        ctx = TLS.TLSClient(pki['ca'], str(OUT / 'pki' / 'lab-a.crt'), str(OUT / 'pki' / 'lab-a.key')).context()
        def call(method, path, body=None):
            req = urllib.request.Request(f'https://127.0.0.1:{PORT["vault"]}{path}', data=body, method=method)
            try:
                with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
                    return r.status, json.loads(r.read())
            except urllib.error.HTTPError as exc:
                return exc.code, json.loads(exc.read())

        say(); say('SUBMITTER  holds a client certificate only; sends four different prediction files')
        for n, wrong in enumerate((70, 52, 41, 30), start=1):          # four models, each a little better than the last
            flip = set(rng.sample(range(ROWS), wrong))
            rows = [f'{i},{CLASSES[(CLASSES.index(l) + 1) % 3] if k in flip else l}' for k, (i, l) in enumerate(zip(ids, truth))]
            data = ('id,prediction\n' + '\n'.join(rows) + '\n').encode()
            _, up = call('POST', '/upload', data)
            status, body = call('POST', '/score', json.dumps({'sha256': up['sha256']}).encode())
            if status == 200 and body.get('outcome') == 'EFFECT':
                say(f'  file {n}  {up["sha256"][:12]}…  scored   accuracy {body["result"]["score"]}')
            else:
                say(f'  file {n}  {up["sha256"][:12]}…  REFUSED  {body.get("refused") or body}   (HTTP {status}; the scoring tool was not run)')
            if n == 2:
                _, again = call('POST', '/score', json.dumps({'sha256': up['sha256']}).encode())
                say(f'  file {n}  sent again           same answer, no charge: {again["result"]["score"]}')
        _, st = call('GET', '/status')
        say(f'  status: allowed {st["allowed"]}, used {st["used"]}, remaining {st["remaining"]}')
        ledger = [json.loads(l)['event'] for l in (holdout.dir / 'ledger.jsonl').read_text().splitlines()]
        say(f'  the scoring tool\'s own log: labels opened {ledger.count("labels_opened")} times')

        say(); say('ANYONE  checks the signed report offline, with three public keys from the owner')
        _, report = call('GET', '/report')
        (OUT / 'report.json').write_text(json.dumps(report, indent=1) + '\n')
        verify = [PY, '-B', str(HERE / 'plea_verify.py')]
        say(subprocess.run(verify + [str(OUT / 'report.json'), '--keys', str(OUT / 'keys.json')], capture_output=True, text=True).stdout.rstrip())

        say(); say('ANYONE  the same report with one score raised by 0.10')
        forged = json.loads(json.dumps(report)); best = max((a for a in forged['attempts'] if a['result']), key=lambda a: a['result']['score'])
        best['result']['score'] = f'{float(best["result"]["score"]) + 0.10:.2f}'
        (OUT / 'report_edited.json').write_text(json.dumps(forged, indent=1) + '\n')
        say(subprocess.run(verify + [str(OUT / 'report_edited.json'), '--keys', str(OUT / 'keys.json')], capture_output=True, text=True).stdout.rstrip())
        say(); say(f'Left in {OUT.relative_to(HERE.parent)}/: report.json, keys.json, report_edited.json, the service logs.')
    finally:
        for p in procs:
            p.kill()


if __name__ == '__main__':
    main()
