#!/usr/bin/env python3
"""The assistant's side of the front door: three questions over HTTPS, and nothing else.

    front_client.py --job-dir DIR show                 the baselined requirement, as the engineer approved it
    front_client.py --job-dir DIR submit DESIGN.json   one official run: declared check met, FAIL or UNKNOWN, with the reason
    front_client.py --job-dir DIR status               every official run so far on this job's baseline

DIR is the folder front_ctl.py enrol wrote: job.json (the service's address), the authority's certificate, and this
job's certificate and key.  That is everything this side holds.  There is no database credential and no signing key
here, and no request names a baseline: the service knows the job from the certificate and the baseline from the job.

Each call is one HTTPS request.  Nothing here retries.  If the service cannot be reached, that is what is reported;
asking again for the same design is safe, because the service returns the verdict it already has and never runs the
check a second time.

Exit status, as the first client (verify_client.py, retired by Amendment 17) gave it: 0 the declared check was met; 2 FAIL; 3 UNKNOWN or interrupted; 4 refused or the
service could not be reached.  Nothing this command prints is the record.

Standard library only, so this file and plea_verify_mcp.py can be copied to the assistant's machine on their own.
"""
import argparse
import http.client
import json
import pathlib
import ssl
import sys
import urllib.parse

TIMEOUT = 120.0
MAX_ANSWER = 8 * 1024 * 1024


class Unreachable(Exception):
    """No answer from the verification service.  The run, if one was asked for, may be pending."""


class FrontClient:
    def __init__(self, job_dir, timeout: float = TIMEOUT):
        d = pathlib.Path(job_dir)
        cfg = json.loads((d / 'job.json').read_text())
        self.job, self.url, self.timeout = cfg['job'], cfg['url'], timeout
        u = urllib.parse.urlsplit(self.url)
        if u.scheme != 'https' or not u.hostname:
            raise ValueError('the service address must be https://HOST:PORT')
        self.host, self.port = u.hostname, u.port or 443
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)               # pins the deployment's own authority and checks the server's name
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_verify_locations(cafile=str(d / cfg['ca']))
        ctx.load_cert_chain(str(d / cfg['cert']), str(d / cfg['key']))
        self.ctx = ctx

    def request(self, method: str, path: str, body=None, raw_body=None) -> tuple[int, dict]:
        """(HTTP status, the service's JSON answer).  One request; no retry."""
        conn = http.client.HTTPSConnection(self.host, self.port, context=self.ctx, timeout=self.timeout)
        try:
            data = raw_body if raw_body is not None else (None if body is None else json.dumps(body).encode())
            conn.request(method, path, body=data, headers={'Content-Type': 'application/json'} if data is not None else {})
            r = conn.getresponse()
            raw = r.read(MAX_ANSWER + 1)
        except (OSError, http.client.HTTPException) as exc:
            raise Unreachable(f'{type(exc).__name__}: {exc}'[:200]) from None
        finally:
            conn.close()
        if len(raw) > MAX_ANSWER:
            raise Unreachable(f'the service answered {r.status} with more than this client will read')
        try:
            payload = json.loads(raw)
        except ValueError:
            raise Unreachable(f'the service answered {r.status} with something that is not JSON') from None
        if not isinstance(payload, dict):
            raise Unreachable(f'the service answered {r.status} with something that is not an object')
        return r.status, payload

    def requirement(self):
        return self.request('GET', '/requirement')

    def baseline(self):
        return self.request('GET', '/baseline')

    def status(self):
        return self.request('GET', '/status')

    def submit(self, design):
        return self.request('POST', '/submit', {'design': design})

    def submit_raw(self, design_bytes: bytes):
        """Amendment 20 (F-2).  The design as its file wrote it, not read and written again: reading a file as JSON would round a number
        that a binary float cannot hold (1.9999999999999999 is 2.0) and keep the last of a repeated key, before the front door saw it."""
        return self.request('POST', '/submit', raw_body=b'{"design":' + design_bytes + b'}')


def unreachable_text(exc) -> str:
    return f'The verification service could not be reached ({exc}).  NOT VERIFIED.  If a design was sent, its run may be pending; ask for the status, or send the same design again.'


def main():
    ap = argparse.ArgumentParser(description='Verify a design against the baselined requirement, through the front door.')
    ap.add_argument('--job-dir', required=True); ap.add_argument('action', choices=['show', 'submit', 'status']); ap.add_argument('design', nargs='?')
    a = ap.parse_args()
    try:
        client = FrontClient(a.job_dir)
    except (OSError, ValueError, KeyError, ssl.SSLError) as exc:
        print(f'The verification client is not configured correctly: {exc}'); sys.exit(4)
    try:
        if a.action == 'show':
            status, out = client.requirement()
        elif a.action == 'status':
            status, out = client.status()
        else:
            if not a.design:
                ap.error('submit needs a design file')
            try:
                raw = pathlib.Path(a.design).read_bytes()
                json.loads(raw.decode('utf-8'))                 # that it is JSON; what it says is the front door's to read
            except (OSError, ValueError, RecursionError) as exc:
                print(f'{a.design} could not be read as JSON: {exc}.  Nothing was submitted.'); sys.exit(4)
            status, out = client.submit_raw(raw.strip())
    except Unreachable as exc:
        print(unreachable_text(exc)); sys.exit(4)
    print(out.get('text') or json.dumps(out))
    if status != 200:
        sys.exit(4)
    sys.exit(out.get('exit', 0) if a.action == 'submit' else 0)


if __name__ == '__main__':
    main()
