#!/usr/bin/env python3
"""The gate host (v0.4, hardened in v0.6 and v0.7): the process that holds the gate's key, runs each attempt's tool
exactly once, and signs the reports.  The governor holds no gate key at all.

    gate_host.py --port 8900 --tools MODULE --witness-key HEX [--witness-key HEX ...] [--key HEX] [--state PATH] [--lease S]

POST /run    {"root", "aid", "nonce", "receipt", "admission", "tool", "arguments"}
             receipt: the witness's signed ACCEPT_INTENT for this attempt, binding this nonce (v0.6).
             admission (v0.7): the witness's signed CROSS for this attempt and nonce, APPLIED or DENIED with
             ALREADY_CROSSED.  CROSS is where the contract checks that the run is ACTIVE and OPEN (5.7/4) and it is
             applied by the witness, so a HOLD or STOP accepted before the crossing leaves no admission to present,
             and the local credential cannot set `crossed` itself (store.py AUTHORITY).  Without a valid admission
             nothing runs, whoever asks.
             The nonce must be binding.nonce_for(root, aid, this host's key, tool, arguments).  The host then runs
             the tool once: a second /run for the same (root, aid), from anywhere, returns the stored result and the
             same signed report with "repeat": true.  A concurrent duplicate is refused while the first is running.
             The verdict is EFFECT on return, NO_EFFECT when the tool raises NoEffect, UNKNOWN on any other exception.
             -> 200 {"result", "verdict", "report", "repeat"}   403 receipt or admission invalid, or not bound
             409 fenced or running   400 malformed   503 this host lost ownership of its state
POST /fence  {"root", "aid", "receipt"}  The receipt is the witness's acceptance of the reservation.  The host
             fences the attempt (it can never run here) and returns a signed FENCE_REPORT.  409 if it already ran.
GET  /tools  the tool list (MCP shape)      GET /pubkey  {"public_key", "tls", "peer", "instance", "lost"}

State and ownership (v0.7).  The SQLite state file records what ran or was fenced, with results and reports, so
one-shot holds across restarts.  It has one owner at a time: a host takes the file over at start only if the
previous owner's heartbeat is older than its lease, and refuses to start otherwise (exit 3).  A host that finds
it has lost the lease stops taking new work (503) but may still record work it was running.  On a takeover, rows
still 'running' are marked 'interrupted': their effect is unknown, and /run answers them with a signed
EFFECT_REPORT claiming UNKNOWN and never runs them again.  If the interrupted host completes the tool after all
(it was stalled, not dead), its EFFECT or NO_EFFECT report replaces the UNKNOWN one, which is kept as
prior_report, so a later /run returns the better-informed verdict and the governor can resolve the attempt.
The accounting of record is still the witness's store; this file is the host's own.  The effect report's signed
fields include a digest of the result returned beside it (evidence.py).
"""
import argparse
import importlib
import json
import os
import pathlib
import sqlite3
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from plea_gateway.binding import nonce_for                               # noqa: E402
from plea_gateway.evidence import Evidence, GateSigner                   # noqa: E402
from plea_gateway.governor import NoEffect                               # noqa: E402
from plea_gateway.receipts import Receipt, ReceiptInvalid, verify, verify_admission   # noqa: E402
from plea_gateway.tls import (TLSClient, TLSHandlerMixin, TransportError, add_server_args, is_transport_error,   # noqa: E402
                              server_from_args, wrap_server)


class GateRefused(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(f'{status}: {detail}'); self.status, self.detail = status, detail


class StateOwned(Exception):
    """Another host holds a live lease on this state file."""


class StateLost(Exception):
    """This host no longer owns the state file: another host took the lease over.  Raised at the write boundary so a
    stale or resumed host cannot start new work (v0.8 fencing)."""


class HostState:
    """The host's own record of what ran or was fenced, in a SQLite file with exactly one live owner.

    Ownership (v0.8).  Acquisition runs in one BEGIN IMMEDIATE transaction, so simultaneous acquirers serialise: the
    first writes a fresh heartbeat and bumps a monotone `generation`; every other then reads that fresh heartbeat and
    is refused (StateOwned).  A host may take the file over only when the current owner's heartbeat is older than the
    lease, and doing so bumps the generation again.  Every write that starts new work (`claim`) is fenced: it runs in
    an immediate transaction that first checks the owner row still carries this host's generation, and raises
    StateLost otherwise.  So a host that was frozen past its lease, or a stale process, cannot claim or run anything
    after another host has taken over.  A host may still `finish` a row it had already claimed under its own
    generation (the in-flight tool completes once and its verdict replaces the interim UNKNOWN), because that records
    an execution that already happened; it never starts a new one.
    """

    def __init__(self, path: str, lease: float = 10.0):
        self.path, self.lease, self.instance, self.lock, self.lost = path, float(lease), uuid.uuid4().hex[:12], threading.Lock(), False
        self.generation = 0
        db = self._db()
        try:
            db.execute('CREATE TABLE IF NOT EXISTS crossings (root TEXT, aid TEXT, status TEXT, nonce TEXT, result TEXT, report TEXT, '
                       'owner TEXT, prior_report TEXT, PRIMARY KEY (root, aid))')
            for col in ('owner TEXT', 'prior_report TEXT'):                          # files from v0.4-v0.6
                try:
                    db.execute(f'ALTER TABLE crossings ADD COLUMN {col}')
                except sqlite3.OperationalError:
                    pass
            db.execute('CREATE TABLE IF NOT EXISTS owner (one INTEGER PRIMARY KEY CHECK (one = 1), instance TEXT, heartbeat REAL, lease REAL, generation INTEGER NOT NULL DEFAULT 0)')
            try:
                db.execute('ALTER TABLE owner ADD COLUMN generation INTEGER NOT NULL DEFAULT 0')   # files from v0.7
            except sqlite3.OperationalError:
                pass
            db.execute('BEGIN IMMEDIATE')                                            # serialise acquisitions: the loser sees the winner's fresh heartbeat
            row = db.execute('SELECT instance, heartbeat, lease, generation FROM owner WHERE one = 1').fetchone()
            now = time.time()
            if row is not None and now - row[1] < row[2]:
                db.execute('ROLLBACK')
                raise StateOwned(f'{path} is owned by host {row[0]} (heartbeat {now - row[1]:.1f} s ago, lease {row[2]} s)')
            self.generation = (row[3] if row else 0) + 1
            self.previous_owner = row[0] if row else None
            db.execute('INSERT INTO owner (one, instance, heartbeat, lease, generation) VALUES (1, ?, ?, ?, ?) '
                       'ON CONFLICT (one) DO UPDATE SET instance = excluded.instance, heartbeat = excluded.heartbeat, '
                       'lease = excluded.lease, generation = excluded.generation',
                       (self.instance, now, self.lease, self.generation))
            self.interrupted = db.execute("UPDATE crossings SET status = 'interrupted' WHERE status = 'running'").rowcount
            db.execute('COMMIT')
        finally:
            db.close()
        threading.Thread(target=self._heartbeat, daemon=True).start()

    def _db(self):
        return sqlite3.connect(self.path, isolation_level=None, timeout=5.0)

    def _check_generation(self, db) -> None:
        row = db.execute('SELECT generation FROM owner WHERE one = 1').fetchone()
        if row is None or row[0] != self.generation:
            self.lost = True
            raise StateLost(f'host {self.instance} lost the lease on {self.path} (generation moved past {self.generation})')

    def _heartbeat(self):
        while not self.lost:
            time.sleep(max(self.lease / 4.0, 0.05))
            try:
                with self._db() as db:
                    n = db.execute('UPDATE owner SET heartbeat = ? WHERE one = 1 AND instance = ? AND generation = ?',
                                   (time.time(), self.instance, self.generation)).rowcount
            except sqlite3.OperationalError:
                continue
            if n == 0:
                self.lost = True                                    # another host took the file over

    def get(self, root, aid):
        with self._db() as db:
            row = db.execute('SELECT status, nonce, result, report, prior_report FROM crossings WHERE root = ? AND aid = ?', (root, aid)).fetchone()
        return None if row is None else {'status': row[0], 'nonce': row[1], 'result': json.loads(row[2]) if row[2] else None,
                                         'report': json.loads(row[3]) if row[3] else None, 'prior_report': json.loads(row[4]) if row[4] else None}

    def claim(self, root, aid, status, nonce=None) -> bool:
        """Start new work: insert the (root, aid) row with this status.  False if a row exists (the one-shot check).
        Fenced (v0.8): raises StateLost if this host no longer owns the current generation, so a stale or resumed host
        cannot begin anything after another host took the file over."""
        with self.lock:
            db = self._db()
            try:
                db.execute('BEGIN IMMEDIATE')
                self._check_generation(db)
                try:
                    db.execute('INSERT INTO crossings (root, aid, status, nonce, owner) VALUES (?, ?, ?, ?, ?)', (root, aid, status, nonce, self.instance))
                    db.execute('COMMIT'); return True
                except sqlite3.IntegrityError:
                    db.execute('ROLLBACK'); return False
            except StateLost:
                db.execute('ROLLBACK'); raise
            finally:
                db.close()

    def finish(self, root, aid, status, result, report):
        """Record the outcome of a row this host claimed under its own generation.  A tool that completes after its row
        was marked interrupted (this host was stalled, another took over) replaces the interim UNKNOWN report, which is
        kept as prior_report (v0.7).  Scoped to this host's own rows (owner = self.instance), so one host never
        overwrites another's record; not generation-fenced, so an in-flight tool may finish the single execution it
        already began even after the lease moved."""
        with self._db() as db:
            prior = db.execute('SELECT status, report FROM crossings WHERE root = ? AND aid = ? AND owner = ?', (root, aid, self.instance)).fetchone()
            keep = prior[1] if (prior and prior[0] == 'interrupted' and status == 'ran' and prior[1]) else None
            db.execute('UPDATE crossings SET status = ?, result = ?, report = ?, prior_report = COALESCE(?, prior_report) WHERE root = ? AND aid = ? AND owner = ?',
                       (status, json.dumps(result), json.dumps(report), keep, root, aid, self.instance))

    def set_report(self, root, aid, report):
        with self._db() as db:
            db.execute('UPDATE crossings SET report = ? WHERE root = ? AND aid = ? AND owner = ?', (json.dumps(report), root, aid, self.instance))

    def finalize_interrupted(self, root, aid, report, result):
        """Stamp the interim UNKNOWN verdict on a row this host found already 'interrupted' at takeover (its previous
        owner was stalled or lost).  Not owner-scoped (the finalizing host is not the one that claimed the row) and
        conditioned on the row still being interrupted with no report, so a later genuine completion by the original
        owner (finish, owner-scoped) overwrites it and keeps it as prior_report."""
        with self._db() as db:
            db.execute('UPDATE crossings SET report = ?, result = ? WHERE root = ? AND aid = ? AND status = ? AND report IS NULL',
                       (json.dumps(report), json.dumps(result), root, aid, 'interrupted'))


def make_handler(signer: GateSigner, witness_keys: tuple, tools: dict, state: HostState, allow=()):
    class Handler(TLSHandlerMixin, BaseHTTPRequestHandler):
        tls_allow = tuple(allow)                                      # v0.5: client names admitted over TLS

        def log_message(self, *args): pass

        def _send(self, status, payload):
            body = json.dumps(payload).encode()
            self.send_response(status); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            if not self.peer_allowed():
                return self._send(403, {'error': f'client {self.peer_name!r} is not allowed'})
            if self.path == '/pubkey':
                return self._send(200, {'public_key': signer.public_hex, 'tls': isinstance(self.connection, ssl.SSLSocket), 'peer': self.peer_name,
                                        'instance': state.instance, 'lost': state.lost, 'generation': state.generation})
            if self.path == '/tools':
                return self._send(200, {'tools': [{'name': n, 'description': d, 'inputSchema': s} for n, (d, s, _) in tools.items()]})
            self._send(404, {'error': 'not found'})

        def do_POST(self):
            if not self.peer_allowed():
                return self._send(403, {'error': f'client {self.peer_name!r} is not allowed'})
            try:
                body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
                root, aid = body['root'], body['aid']
                receipt = Receipt.from_json(body['receipt'])
            except Exception as exc:
                return self._send(400, {'error': f'malformed request: {exc}'})
            if self.path == '/run':
                return self._run(root, aid, body, receipt)
            if self.path == '/fence':
                return self._fence(root, aid, receipt)
            self._send(404, {'error': 'not found'})

        def _run(self, root, aid, body, receipt):
            nonce, tool, arguments = body.get('nonce'), body.get('tool'), body.get('arguments') or {}
            if not isinstance(nonce, str) or not nonce or tool not in tools or not isinstance(arguments, dict):
                return self._send(400, {'error': 'nonce, tool or arguments invalid'})
            if state.lost:
                return self._send(503, {'error': 'this host lost ownership of its state; another host owns it'})
            try:
                verify(receipt, witness_keys, root, aid, 'ACCEPT_INTENT', binding=nonce)   # the witness's word for this nonce, or nothing runs
            except ReceiptInvalid as exc:
                return self._send(403, {'error': f'receipt invalid: {exc}'})
            try:
                admission = Receipt.from_json(body.get('admission') or {})
                verify_admission(admission, witness_keys, root, aid, nonce)                # v0.7: the witness recorded the crossing, or nothing runs
            except ReceiptInvalid as exc:
                return self._send(403, {'error': f'admission invalid: {exc}'})
            if nonce != nonce_for(root, aid, signer.public_hex, tool, arguments):          # v0.6: the nonce binds executor, tool and arguments
                return self._send(403, {'error': 'the nonce does not bind this executor, tool and arguments'})
            try:
                claimed = state.claim(root, aid, 'running', nonce)
            except StateLost as exc:
                return self._send(503, {'error': f'host lost ownership mid-request: {exc}'})
            if not claimed:
                prior = state.get(root, aid)
                if prior['status'] == 'fenced':
                    return self._send(409, {'error': 'attempt was fenced; it cannot run'})
                if prior['status'] == 'running':
                    return self._send(409, {'error': 'attempt is running; a concurrent duplicate is refused'})
                if prior['status'] == 'interrupted' and prior['report'] is None:            # v0.6: a final, signed, UNKNOWN outcome
                    result = {'error': 'interrupted: the host stopped while this attempt was running; its effect is unknown'}
                    report = signer.effect_report(root, aid, nonce, 'UNKNOWN', result).to_json()
                    state.finalize_interrupted(root, aid, report, result); prior = state.get(root, aid)   # v0.8: a takeover/restart host may finalize another owner's interrupted row
                return self._send(200, {'result': prior['result'], 'verdict': prior['report']['claim'], 'report': prior['report'], 'repeat': True,
                                        'prior_report': prior['prior_report']})
            fn = tools[tool][2]
            try:
                result, verdict = fn(**arguments), 'EFFECT'
            except NoEffect:
                result, verdict = None, 'NO_EFFECT'
            except Exception as exc:
                result, verdict = {'error': repr(exc)[:200]}, 'UNKNOWN'
            report = signer.effect_report(root, aid, nonce, verdict, result).to_json()      # the digest of the result is signed (v0.6)
            state.finish(root, aid, 'ran', result, report)
            self._send(200, {'result': result, 'verdict': verdict, 'report': report, 'repeat': False})

        def _fence(self, root, aid, receipt):
            try:
                verify(receipt, witness_keys, root, aid, 'ACCEPT_RESERVATION')
            except ReceiptInvalid as exc:
                return self._send(403, {'error': f'receipt invalid: {exc}'})
            if state.lost:
                return self._send(503, {'error': 'this host lost ownership of its state; another host owns it'})
            try:
                fenced = state.claim(root, aid, 'fenced')
            except StateLost as exc:
                return self._send(503, {'error': f'host lost ownership mid-request: {exc}'})
            if not fenced:
                prior = state.get(root, aid)
                if prior['status'] != 'fenced':
                    return self._send(409, {'error': 'attempt already crossed; it cannot be fenced'})
                return self._send(200, {'report': prior['report'], 'repeat': True})
            report = signer.fence_report(root, aid).to_json()
            state.set_report(root, aid, report)
            self._send(200, {'report': report, 'repeat': False})
    return Handler


class GateHostClient:
    """What the governor talks to.  It holds no key: it carries receipts in and reports out."""

    def __init__(self, url: str, timeout: float = 30.0, tls: TLSClient | None = None, public_key: str | None = None):
        """public_key (v0.6): the host's gate key to pin; the governor binds every action to it and verifies every
        outcome against it.  None fetches the key the host announces (trust on first use)."""
        self.url, self.timeout = url.rstrip('/'), timeout
        if tls is not None and not self.url.startswith('https://'):
            raise ValueError(f'TLS is configured but the gate host URL is not https: {self.url}')   # v0.7
        self.ctx = tls.context() if tls else None           # v0.5: pins the authority, checks the host's name, presents our certificate
        self.public_key = public_key or self._get('/pubkey')['public_key']

    def _open(self, req):
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self.ctx) as r:
                return json.load(r)
        except urllib.error.HTTPError as exc:
            raise GateRefused(exc.code, exc.read().decode(errors='replace')[:200])
        except (urllib.error.URLError, OSError) as exc:
            if is_transport_error(exc):
                raise TransportError(f'{self.url}: {exc}')
            raise

    def _get(self, path):
        return self._open(self.url + path)

    def _post(self, path, payload):
        return self._open(urllib.request.Request(self.url + path, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}, method='POST'))

    def tools(self):
        return self._get('/tools')['tools']

    def run(self, root, aid, nonce, receipt: Receipt, tool, arguments, admission: Receipt | None = None):
        return self._post('/run', {'root': root, 'aid': aid, 'nonce': nonce, 'receipt': receipt.to_json(), 'tool': tool, 'arguments': arguments,
                                   'admission': admission.to_json() if admission is not None else None})

    def fence(self, root, aid, receipt: Receipt):
        return self._post('/fence', {'root': root, 'aid': aid, 'receipt': receipt.to_json()})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8900); ap.add_argument('--tools', required=True)
    ap.add_argument('--witness-key', action='append', required=True, help='a witness public key to pin (hex); repeatable')
    ap.add_argument('--key', default=os.environ.get('PLEA_GATE_KEY')); ap.add_argument('--state', default=None)
    ap.add_argument('--lease', type=float, default=10.0, help='seconds: how stale the state owner\'s heartbeat must be before another host may take over')
    ap.add_argument('--bind', default='127.0.0.1'); add_server_args(ap)
    a = ap.parse_args()
    sys.path.insert(0, os.getcwd())
    tools = importlib.import_module(a.tools).TOOLS
    signer = GateSigner(a.key); tls = server_from_args(a)
    try:
        state = HostState(a.state or f'gate_host_{a.port}.sqlite', a.lease)
    except StateOwned as exc:
        print(json.dumps({'refused_to_start': str(exc)}), flush=True); sys.exit(3)
    server = wrap_server(ThreadingHTTPServer((a.bind, a.port), make_handler(signer, tuple(a.witness_key), tools, state, tuple(a.tls_allow))), tls)
    print(json.dumps({'listening': a.port, 'public_key': signer.public_hex, 'tools': list(tools), 'witness_keys': a.witness_key,
                      'tls': tls is not None, 'tls_allow': a.tls_allow, 'instance': state.instance, 'previous_owner': state.previous_owner,
                      'interrupted': state.interrupted, 'lease': state.lease, 'generation': state.generation}), flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
