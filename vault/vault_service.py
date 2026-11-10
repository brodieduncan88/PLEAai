#!/usr/bin/env python3
"""The vault's front door: the one service a submitter talks to.

    vault_service.py --holdout DIR --port 8950 --local-dsn DSN --witness-url URL --witness-key HEX --gate-host URL --gate-key HEX
                     --tls-cert CERT --tls-key KEY --tls-ca CA --upstream-cert CERT --upstream-key KEY [--report-key HEX]

It serves HTTPS with mutual TLS.  A submitter is the common name of the client certificate, and a request is served
only if that name is enrolled for this holdout, not revoked, and the certificate presented is the one enrolled (by
SHA-256 fingerprint).  No request names a submitter: each one acts on the caller's own budget, HOLDOUT/SUBMITTER.

  POST /upload   the predictions file as the body.  Checked from public information (holdout.py); an invalid file is
                 refused with its code and nothing else happens: no attempt, no audit row, nothing charged or refunded.
                 -> 200 {"sha256", "stored"}   400 {"rejected": CODE}   409 {"refused": "UPLOAD_CAP"}
  POST /score    {"sha256"}.  Runs one governed attempt: the governor (inside this process, with the vault's database
                 credential) drives the contract, the witness signs the receipts, the gate host scores once.
                 -> 200 {"outcome": "EFFECT", "result"} | {"outcome": "NO_EFFECT"} | {"outcome": "UNKNOWN"}
                    409 {"refused": "BUDGET_EXHAUSTED" | "HELD" | "STOPPED" | "IN_PROGRESS"}   404 unknown hash
                    410 the file is gone and was never scored   503 a vault service could not be reached
                 The same hash again returns the stored result at no charge.
  GET  /status   attempts allowed, used, refunded and remaining, and each upload's outcome.
  GET  /report   the signed attempt report (vault_report.py).  First asks the gate host once about any admitted attempt
                 that has no outcome yet.
  GET  /manifest the holdout's public manifest and its hash.     GET /ids  the public id list.

Limits come from the manifest: file size, unscored uploads held per submitter, requests per minute per certificate.
One scoring runs at a time per submitter; a second request meanwhile gets IN_PROGRESS.

The submitter never holds a database credential, never reaches the witness or the gate host (their allow-lists admit
only this service's own certificate name), and no path here returns the sealed labels.

index.sqlite in the holdout directory is this service's own record: who is enrolled (vault_ctl.py writes it) and what
each submitter has uploaded.  It is not part of the accounting; the contract's store is.
"""
import argparse
import collections
import hashlib
import json
import os
import pathlib
import sqlite3
import ssl
import sys
import threading
import time
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from plea_gateway import (BudgetExhausted, GateHostClient, GateRefusedRun, Governor, GovernedError, Held, InProgress, NoEffect,   # noqa: E402
                          OutcomeInvalid, ReceiptInvalid, RemoteWitness, RequestKeyReused, Store, Stopped, TransportError, UnknownRoot,
                          WitnessUnavailable)
from plea_gateway.tls import TLSClient, TLSHandlerMixin, add_server_args, server_from_args, wrap_server   # noqa: E402
from holdout import HEX64, NAME, RESERVED, Holdout, sha256_hex            # noqa: E402
from vault_report import ReportKey, build, outcome_of, request_key, score_arguments   # noqa: E402


class Index:
    """Enrolment and uploads, in SQLite beside the holdout.  One short connection per operation."""

    def __init__(self, path):
        self.path = str(path)
        with self._db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS enrolment (submitter TEXT PRIMARY KEY, organisation TEXT, contact TEXT, cert_sha256 TEXT NOT NULL, '
                       'issued TEXT, expires TEXT, revoked INTEGER NOT NULL DEFAULT 0)')
            db.execute('CREATE TABLE IF NOT EXISTS uploads (submitter TEXT NOT NULL, sha256 TEXT NOT NULL, bytes INTEGER NOT NULL, uploaded_at REAL NOT NULL, '
                       'PRIMARY KEY (submitter, sha256))')

    def _db(self):
        return sqlite3.connect(self.path, timeout=10)

    def enrol(self, submitter, organisation, contact, cert_sha256, issued, expires) -> None:
        with self._db() as db:
            db.execute('INSERT INTO enrolment (submitter, organisation, contact, cert_sha256, issued, expires, revoked) VALUES (?, ?, ?, ?, ?, ?, 0) '
                       'ON CONFLICT (submitter) DO UPDATE SET organisation = excluded.organisation, contact = excluded.contact, '
                       'cert_sha256 = excluded.cert_sha256, issued = excluded.issued, expires = excluded.expires', (submitter, organisation, contact, cert_sha256, issued, expires))

    def revoke(self, submitter) -> None:
        with self._db() as db:
            db.execute('UPDATE enrolment SET revoked = 1 WHERE submitter = ?', (submitter,))

    def enrolled(self, submitter):
        with self._db() as db:
            row = db.execute('SELECT submitter, organisation, contact, cert_sha256, issued, expires, revoked FROM enrolment WHERE submitter = ?', (submitter,)).fetchone()
        return None if row is None else dict(zip(('submitter', 'organisation', 'contact', 'cert_sha256', 'issued', 'expires', 'revoked'), row))

    def submitters(self) -> list:
        with self._db() as db:
            return [r[0] for r in db.execute('SELECT submitter FROM enrolment ORDER BY submitter')]

    def uploads(self, submitter) -> list:
        with self._db() as db:
            return [r[0] for r in db.execute('SELECT sha256 FROM uploads WHERE submitter = ? ORDER BY uploaded_at, sha256', (submitter,))]

    def has_upload(self, submitter, sha256) -> bool:
        with self._db() as db:
            return db.execute('SELECT 1 FROM uploads WHERE submitter = ? AND sha256 = ?', (submitter, sha256)).fetchone() is not None

    def add_upload(self, submitter, sha256, nbytes) -> None:
        with self._db() as db:
            db.execute('INSERT OR IGNORE INTO uploads (submitter, sha256, bytes, uploaded_at) VALUES (?, ?, ?, ?)', (submitter, sha256, nbytes, time.time()))


class Vault:
    def __init__(self, holdout: Holdout, store: Store, witness, host, report_key: ReportKey):
        self.holdout, self.store, self.witness, self.host, self.report_key = holdout, store, witness, host, report_key
        self.index = Index(holdout.dir / 'index.sqlite')
        self.keys = {'witness': witness.public_key, 'gate': host.public_key}
        self._guard = threading.Lock()                       # index writes and the tables below
        self._scoring, self._governors, self._hits = {}, {}, collections.defaultdict(collections.deque)

    # ------------------------------------------------------------------ who is asking
    def admit(self, name, der) -> dict | None:
        """The enrolment record, if this certificate is the one enrolled for this name and it is not revoked."""
        if not name or not NAME.match(name) or name in RESERVED or not der:
            return None
        rec = self.index.enrolled(name)
        if rec is None or rec['revoked'] or rec['cert_sha256'] != sha256_hex(der):
            return None
        return rec

    def within_rate(self, name) -> bool:
        limit, now = self.holdout.limits['max_requests_per_minute'], time.time()
        with self._guard:
            hits = self._hits[name]
            while hits and now - hits[0] >= 60.0:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now); return True

    def _lock(self, submitter) -> threading.Lock:
        with self._guard:
            return self._scoring.setdefault(submitter, threading.Lock())

    def _governor(self, submitter) -> Governor:
        with self._guard:
            gov = self._governors.get(submitter)
        if gov is None:
            root = self.holdout.root(submitter)
            obs = self.store.observe(root)                   # UnknownRoot: the owner has not provisioned a budget
            gov = Governor(self.store, self.witness, root, obs['k'], obs['m'], host=self.host)
            with self._guard:
                self._governors[submitter] = gov
        return gov

    def _attempt_for(self, submitter, sha):
        args = score_arguments(self.holdout.manifest_sha256, submitter, sha)
        return args, request_key(args), self.store.attempt_for_request(self.holdout.root(submitter), request_key(args))

    # ------------------------------------------------------------------ upload: public checks only, never an attempt
    def upload(self, submitter, data: bytes):
        code, _ = self.holdout.validate(data)
        if code is not None:
            return 400, {'rejected': code}
        sha = sha256_hex(data)
        with self._guard:
            if self.index.has_upload(submitter, sha):
                return 200, {'sha256': sha, 'stored': False}
            unscored = sum(1 for s in self.index.uploads(submitter) if self._attempt_for(submitter, s)[2] is None)
            if unscored >= self.holdout.limits['max_unscored']:
                return 409, {'refused': 'UPLOAD_CAP', 'detail': f'{unscored} unscored uploads are held; score or wait before uploading more'}
            path = self.holdout.upload_path(submitter, sha); path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix('.tmp'); tmp.write_bytes(data); os.replace(tmp, path)
            self.index.add_upload(submitter, sha, len(data))
        return 200, {'sha256': sha, 'stored': True}

    # ------------------------------------------------------------------ score: one governed attempt
    def score(self, submitter, sha):
        if not isinstance(sha, str) or not HEX64.match(sha):
            return 400, {'refused': 'BAD_REQUEST'}
        if not self.index.has_upload(submitter, sha):
            return 404, {'refused': 'UNKNOWN_SUBMISSION'}
        lock = self._lock(submitter)
        if not lock.acquire(blocking=False):
            return 409, {'refused': 'IN_PROGRESS'}
        try:
            return self._score(submitter, sha)
        finally:
            lock.release()

    def _score(self, submitter, sha):
        try:
            args, key, existing = self._attempt_for(submitter, sha)
            if existing is None and not self.holdout.upload_path(submitter, sha).exists():
                return 410, {'refused': 'FILE_GONE'}        # deleted and never scored: nothing to score
            value = self._governor(submitter).attempt(key, 'score', **args)
            return 200, {'outcome': 'EFFECT', 'result': value}
        except NoEffect:
            return 200, {'outcome': 'NO_EFFECT', 'detail': 'the file was rejected inside the scoring tool'}
        except BudgetExhausted:
            return 409, {'refused': 'BUDGET_EXHAUSTED'}
        except Held:
            return 409, {'refused': 'HELD'}
        except Stopped:
            return 409, {'refused': 'STOPPED'}
        except InProgress:
            return 409, {'refused': 'IN_PROGRESS'}
        except UnknownRoot:
            return 403, {'refused': 'NO_BUDGET'}
        except GovernedError as exc:
            return 409, {'refused': exc.decision.code}
        except (GateRefusedRun, OutcomeInvalid, RequestKeyReused, ReceiptInvalid, PermissionError) as exc:
            return 502, {'refused': 'VAULT_ERROR', 'detail': type(exc).__name__}
        except (WitnessUnavailable, TransportError, urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            return 503, {'refused': 'UNAVAILABLE', 'detail': 'a vault service could not be reached; the attempt may be pending'}
        except RuntimeError:
            return 200, {'outcome': 'UNKNOWN', 'detail': 'no score; attempt used'}     # the gate signed that it does not know the outcome

    # ------------------------------------------------------------------ status and report
    def status(self, submitter):
        root = self.holdout.root(submitter)
        try:
            obs = self.store.observe(root)
        except UnknownRoot:
            return 403, {'refused': 'NO_BUDGET'}
        r, c, n = obs['live']; credit = min(n, obs['m']); charged = r + c - credit
        phases = {a[1]: (a[0], a[2]) for a in obs['attempts']}
        uploads = []
        for sha in self.index.uploads(submitter):
            _, key, _ = self._attempt_for(submitter, sha)
            if key in phases:
                aid, phase = phases[key]
                uploads.append({'sha256': sha, 'outcome': outcome_of(phase, self.store.evidence_for(root, aid))})
            else:
                uploads.append({'sha256': sha, 'outcome': None})
        return 200, {'holdout': self.holdout.name, 'submitter': submitter, 'allowed': obs['k'], 'replacement': obs['m'], 'used': charged, 'refunded': credit,
                     'remaining': max(0, obs['k'] - charged), 'witness': obs['witness'], 'business': obs['business'], 'uploads': uploads}

    def report(self, submitter, enrolment):
        lock = self._lock(submitter)
        if not lock.acquire(blocking=False):
            return 409, {'refused': 'IN_PROGRESS'}
        try:
            root = self.holdout.root(submitter)
            try:
                obs = self.store.observe(root)
            except UnknownRoot:
                return 403, {'refused': 'NO_BUDGET'}
            phases = {a[1]: (a[0], a[2]) for a in obs['attempts']}
            uploads = self.index.uploads(submitter)
            for sha in uploads:                              # ask the host once about an admitted attempt with no outcome
                args, key, _ = self._attempt_for(submitter, sha)
                if key in phases and phases[key][1] == 'CONSUMED' and outcome_of('CONSUMED', self.store.evidence_for(root, phases[key][0])) == 'PENDING':
                    try:
                        self._governor(submitter).attempt(key, 'score', **args)
                    except Exception:
                        pass                                 # still pending, or now UNKNOWN: the report says which
            return 200, build(self.store, self.holdout, submitter, enrolment, uploads, self.keys, self.report_key)
        finally:
            lock.release()


def make_handler(vault: Vault):
    class Handler(TLSHandlerMixin, BaseHTTPRequestHandler):
        tls_allow = ()                                       # every certificate of the authority reaches admit(), which decides

        def log_message(self, *args): pass

        def _send(self, status, payload, raw: bytes | None = None):
            body = raw if raw is not None else json.dumps(payload).encode()
            self.send_response(status); self.send_header('Content-Type', 'text/plain; charset=utf-8' if raw is not None else 'application/json')
            self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

        def _who(self):
            """(name, enrolment record) or None after answering 403 or 429."""
            der = self.connection.getpeercert(binary_form=True) if isinstance(self.connection, ssl.SSLSocket) else None
            rec = vault.admit(self.peer_name, der)
            if rec is None:
                self._send(403, {'refused': 'NOT_ENROLLED'}); return None
            if not vault.within_rate(rec['submitter']):
                self._send(429, {'refused': 'RATE_LIMIT'}); return None
            return rec

        def do_GET(self):
            rec = self._who()
            if rec is None:
                return
            name = rec['submitter']
            if self.path == '/manifest':
                return self._send(200, {'manifest': vault.holdout.manifest, 'manifest_sha256': vault.holdout.manifest_sha256})
            if self.path == '/ids':
                return self._send(200, None, raw=(vault.holdout.dir / 'ids.txt').read_bytes())
            if self.path == '/status':
                return self._send(*vault.status(name))
            if self.path == '/report':
                return self._send(*vault.report(name, rec))
            self._send(404, {'refused': 'NOT_FOUND'})

        def do_POST(self):
            rec = self._who()
            if rec is None:
                return
            name = rec['submitter']
            try:
                length = int(self.headers.get('Content-Length', ''))
            except ValueError:
                return self._send(411, {'refused': 'LENGTH_REQUIRED'})
            if length < 0:
                self.close_connection = True                       # a negative length would make rfile.read(length) read to EOF, past every cap
                return self._send(400, {'refused': 'BAD_REQUEST'})
            limit = vault.holdout.limits['max_bytes']
            if self.path == '/upload':
                if length > limit:
                    remaining = min(length, limit + 1024 * 1024)       # drain a bounded amount so the answer can be read, then close
                    while remaining > 0:
                        chunk = self.rfile.read(min(65536, remaining))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                    self.close_connection = True
                    return self._send(400, {'rejected': 'TOO_LARGE'})
                return self._send(*vault.upload(name, self.rfile.read(length)))
            if self.path == '/score':
                if length > 4096:
                    return self._send(400, {'refused': 'BAD_REQUEST'})
                try:
                    sha = json.loads(self.rfile.read(length)).get('sha256')
                except Exception:
                    return self._send(400, {'refused': 'BAD_REQUEST'})
                return self._send(*vault.score(name, sha))
            self._send(404, {'refused': 'NOT_FOUND'})
    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--holdout', required=True); ap.add_argument('--port', type=int, default=8950); ap.add_argument('--bind', default='127.0.0.1')
    ap.add_argument('--local-dsn', default=os.environ.get('PLEA_LOCAL_DSN', 'postgresql://plea_local:local@127.0.0.1:5432/plea'))
    ap.add_argument('--witness-url', required=True); ap.add_argument('--witness-key', action='append', required=True, help='a witness public key to pin (hex); repeatable')
    ap.add_argument('--gate-host', required=True); ap.add_argument('--gate-key', required=True, help='the gate host\'s public key to pin (hex)')
    ap.add_argument('--report-key', default=os.environ.get('PLEA_VAULT_REPORT_KEY'), help='the owner\'s report key (hex); default: DIR/report.key')
    ap.add_argument('--upstream-cert', required=True, help='this service\'s client certificate for the witness and the gate host'); ap.add_argument('--upstream-key', required=True)
    add_server_args(ap)
    a = ap.parse_args()
    tls = server_from_args(a)
    if tls is None:
        raise SystemExit('the front door serves mutual TLS only: give --tls-cert, --tls-key and --tls-ca')
    holdout = Holdout(a.holdout)
    key_hex = a.report_key or (holdout.dir / 'report.key').read_text().strip()
    client = TLSClient(a.tls_ca, a.upstream_cert, a.upstream_key)
    witness = RemoteWitness(a.witness_url, a.witness_key if len(a.witness_key) > 1 else a.witness_key[0], tls=client)
    host = GateHostClient(a.gate_host, tls=client, public_key=a.gate_key)
    vault = Vault(holdout, Store(a.local_dsn), witness, host, ReportKey(key_hex))
    server = wrap_server(ThreadingHTTPServer((a.bind, a.port), make_handler(vault)), tls)
    print(json.dumps({'listening': a.port, 'holdout': holdout.name, 'manifest_sha256': holdout.manifest_sha256, 'report_key': vault.report_key.public_hex,
                      'witness_keys': a.witness_key, 'gate_key': a.gate_key, 'tls': True}), flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
