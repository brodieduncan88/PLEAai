#!/usr/bin/env python3
"""Declared tests F1-F16 for the front door and the MCP server (verify/DECLARED_FRONT.md states the expected outcomes),
and F17 to F19, added by Amendment 2 (verify/DECLARED_AMEND2.md), which also restates two checks of F15,
and F20, added by Amendment 3 (verify/DECLARED_AMEND3.md), and F21, added by Amendment 4 (verify/DECLARED_AMEND4.md), and F22 to F27, added by Amendment 7 (verify/DECLARED_AMEND7.md), and F28 to F32, added by Amendment 8 (verify/DECLARED_AMEND8.md), which also restates F19, and F33 and F34, added by Amendment 9 (verify/DECLARED_AMEND9.md), which also restates F1, F6, F10, F11, F13, F21, F29 and F32.

    verify_front_tests.py [F1 F6 ...]     all thirty-four by default; writes outputs/verify_front_tests.json; exits 1 if any test fails

F1 and F2 ran the first plug-in as it was released, with no front door, and showed the two defects this work is for; they are
retired by Amendment 17 with the first plug-in, and their properties are carried by R30 and F7.
F3 to F16 make a fresh deployment with a front door (verify/deploy_front.py: new keys; the released witness service
and gate host, unchanged, admitting only the front door's certificate; front_door.py; the gate host loading
verify_tools), baseline the self-test fixture in tests/verify_case/ as the responsible engineer would, enrol a job,
and then act as an assistant's host application through the MCP server, or as a caller holding the job's certificate
and writing its own requests.  The independent measures are the gate tool's ledger and the engineer's inbox, both
outside every PLEA store, and the store's own audit rows.

A test passes only if every named check in it is true.  A harness or service error is a failed test.
"""
import hashlib
import http.client
import json
import pathlib
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

HERE = pathlib.Path(__file__).resolve().parent
GATEWAY = HERE.parent
sys.path.insert(0, str(GATEWAY)); sys.path.insert(0, str(GATEWAY / 'verify'))
import baseline as B                    # noqa: E402
import check_record                     # noqa: E402
import deploy                           # noqa: E402
import deploy_front                     # noqa: E402
import front_ctl                        # noqa: E402
import front_door                       # noqa: E402
import notices as service_notices       # noqa: E402  (Amendment 8: the gate's proof that it can write an inbox)
import verify_ctl                       # noqa: E402
from deploy_front import text_of        # noqa: E402
from front_client import FrontClient    # noqa: E402
from plea_gateway import Store          # noqa: E402
from plea_gateway import tls as TLS     # noqa: E402
from plea_gateway.tls import TLSClient  # noqa: E402
from verify_record import Key, arguments_for, request_key   # noqa: E402

OUT = GATEWAY / 'outputs' / 'verify_front_tests'
CASE = HERE / 'verify_case'
PY = sys.executable
BAD = {'material': 'PA66-GF30', 'wall_mm': 3, 'mode': 'normal'}          # 180 C against 200 C: must fail
GOOD = {'material': 'PPS-GF40', 'wall_mm': 3, 'mode': 'normal'}         # 220 C: meets the check
FAILED = 'FAIL: REQUIREMENT NOT MET'
MET = 'DECLARED CHECK MET'


def draft(**changes) -> dict:
    d = json.loads((CASE / 'card.json').read_text())
    d['job'] = uuid.uuid4().hex                 # every baseline in every run is distinct, so its budget is new
    d.update(changes)
    return d


def relaxed(**changes) -> dict:
    """The same requirement with the limit lowered to 170 C, so the design that fails at 200 C passes."""
    d = draft(**changes)
    d['criteria'] = [dict(d['criteria'][0], limit='170')]
    d['controls'] = [{'name': 'PA66 passes at 170 C', 'design': BAD, 'expect': 'PASS'},
                     {'name': 'PA6 (160 C) must fail at 170 C', 'design': {'material': 'PA6', 'wall_mm': 3, 'mode': 'normal'}, 'expect': 'FAIL'}]
    return d


def case_b(tag: str) -> pathlib.Path:
    """The fixture with one more material in its table, for the relaxed baseline's failing control."""
    src = OUT / tag / 'case_b'; src.mkdir(parents=True, exist_ok=True)
    (src / 'check.py').write_text((CASE / 'check.py').read_text()); (src / 'materials.csv').write_text((CASE / 'materials.csv').read_text() + 'PA6,160\n')
    return src


def head(out: str) -> str:
    return out.strip().splitlines()[0] if out.strip() else ''


def failing(checks: list) -> list:
    return [f'{n} {t}: {d}' for n, t, good, d in checks if not good]


class Run:
    """One deployment with a front door, one baseline, and one job enrolled for it."""

    def __init__(self, tag: str, crash_at: str | None = None, card: dict | None = None):
        self.tag = tag
        self.s = deploy_front.FrontServices(OUT / tag).start(crash_at)
        self.env = self.s.baseline(CASE, card or draft())
        self.h = self.env['baseline_sha256']
        self.root = B.root_for(self.env['card'])
        self.job = self.s.enrol('job-a', self.h)
        self._mcp = None

    def mcp(self) -> deploy_front.Mcp:
        if self._mcp is None:
            self._mcp = self.s.mcp(self.job)
        return self._mcp

    def submit(self, design) -> dict:
        """A tool call, as a host application makes it: the tool result."""
        return self.mcp().call('plea_submit_design', {'design': design})

    def checked(self, h=None, design=None):
        ok, checks, s = check_record.verify(self.s.record(h or self.h), self.s.keys, design)
        return ok, failing(checks), s

    def calls(self) -> int:
        return len(self.s.ledger('called'))

    def notices(self, h=None) -> int:
        return len(self.s.inbox(h or self.h))

    def audit_rows(self, root=None) -> int:
        return len(Store(deploy.LOCAL_DSN).audit_snapshot(root or self.root)[0])

    def stop(self):
        if self._mcp is not None:
            self._mcp.close()
        self.s.stop()


def raw(job_dir, method: str, path: str, body: bytes | None = None, length: int | None = None, headers: dict | None = None):
    """One HTTPS request with a job folder's certificate and the bytes given: (status, the JSON answer), or (None, why)."""
    try:
        c = FrontClient(job_dir, timeout=60)
    except Exception as exc:
        return None, {'unreachable': type(exc).__name__}
    conn = http.client.HTTPSConnection(c.host, c.port, context=c.ctx, timeout=60)
    try:
        conn.putrequest(method, path)
        for k, v in (headers or {}).items():
            conn.putheader(k, v)
        if body is not None or length is not None:
            conn.putheader('Content-Length', str(len(body) if length is None else length))
        conn.endheaders(body)
        r = conn.getresponse()
        return r.status, json.loads(r.read())
    except (OSError, http.client.HTTPException, ValueError) as exc:
        return None, {'unreachable': type(exc).__name__}
    finally:
        conn.close()


def folder(path: pathlib.Path, job: str, url: str, ca_cert: bytes, cert: bytes, key: bytes) -> pathlib.Path:
    """A job folder made by hand, for a certificate the engineer did not enrol."""
    path.mkdir(parents=True, exist_ok=True)
    (path / 'ca.crt').write_bytes(ca_cert); (path / 'job.crt').write_bytes(cert); (path / 'job.key').write_bytes(key)
    (path / 'job.json').write_text(json.dumps({'job': job, 'url': url, 'ca': 'ca.crt', 'cert': 'job.crt', 'key': 'job.key'}))
    return path


def direct(url: str, ca: str, cert: str, key: str, body: dict | None = None):
    """A request straight to the witness service or the gate host with a given certificate: the HTTP status, or why not."""
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(), headers={'Content-Type': 'application/json'}, method='GET' if body is None else 'POST')
    try:
        with urllib.request.urlopen(req, timeout=20, context=TLSClient(ca, cert, key).context()) as r:
            return r.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, OSError) as exc:
        return type(exc).__name__


# ====================================================================== the two defects, on the first plug-in as released
# F1 and F2 are retired by Amendment 17 (22 November 2026, D6).  They ran the first plug-in (verify_client.py), which held the
# gateway's database credential in the assistant's workspace, to show the two defects the front door was built for.  That
# plug-in now refuses to run.  Their text and results are as they were, at 1b132e2 and in every results file before Amendment 17.
#   F1 (a caller holding the workspace's credentials runs a design against another baseline on one baseline's budget and is told
#      PASS): the attack is now refused by the gate host itself, before anything is claimed or signed.  It is carried by R30,
#      made with the service's own database role and the front door's certificate, which is more than the workspace held.
#   F2 (a design the database cannot store leaves the record of its baseline unable to verify): such a design is refused by the
#      front door before anything is run, counted, journaled or recorded.  It is carried by F7, which sends both of F2's designs
#      (a NUL in a value, an infinite number) and twelve more, through the front door, the MCP tool and the command line.


# ====================================================================== the front door and the MCP server
def f3():
    """Through the MCP server, a design that does not meet the requirement gets a signed FAIL with the reason, kept on the record and sent to the engineer."""
    r = Run('F3'); e = {}
    try:
        res = r.submit(BAD); out = text_of(res); sc = res.get('structuredContent') or {}
        ok, why, s = r.checked()
        notice = (r.s.home / 'inbox' / r.h[:16] / r.s.inbox(r.h)[0]).read_text() if r.s.inbox(r.h) else ''
        run = s['runs'][0] if s.get('runs') else {}
        blocks = [c.get('text', '') for c in res.get('content', [])]
        e.update(is_error=res.get('isError'), first_line=head(out), says_values='achieved 180 C' in out and 'at least 200 C' in out, outcome=sc.get('outcome'), met=sc.get('met'),
                 names_baseline=sc.get('baseline_sha256') == r.h and (sc.get('verdict') or {}).get('baseline_sha256') == r.h, text_blocks=len(blocks), record_verifies=ok, why=why, status=s.get('status'),
                 run=dict(outcome=run.get('outcome'), reason=run.get('reason_code'), criteria=run.get('criteria')), notices=r.s.inbox(r.h), notice_head=notice.splitlines()[:4])
        checks = {'the tool result leads with FAIL and the required and achieved values, and is not marked as a tool error': res.get('isError') is False and head(out) == FAILED and e['says_values'],
                  'the same verdict is given as fields: outcome FAIL, not met, for this job\'s baseline': sc.get('outcome') == 'FAIL' and sc.get('met') is False and e['names_baseline']
                      and len(blocks) == 2 and json.loads(blocks[1]) == sc,
                  'the record holds the FAIL with reason LIMIT_NOT_MET, 180 against 200, margin -20': run.get('outcome') == 'FAIL' and run.get('reason_code') == 'LIMIT_NOT_MET'
                      and [(c['achieved'], c['limit'], c['margin'], c['met']) for c in run.get('criteria', [])] == [('180', '200', '-20', False)],
                  'the record verifies offline and its status is NOT VERIFIED': ok and s.get('status') == 'NOT VERIFIED',
                  'one notice is in the engineer\'s inbox, from the service, naming the failure': len(r.s.inbox(r.h)) == 1 and 'From: the verification service (not the assistant)' in notice
                      and FAILED in notice and 'To: D. Marsh' in notice}
    finally:
        r.stop()
    return checks, e


def f4():
    """The same design sent again, by tool call or by command line, returns the same verdict: one run, one notice."""
    r = Run('F4'); e = {}
    try:
        a = r.submit(BAD); b = r.submit(BAD)
        other = r.s.mcp(r.job, era='modern'); c = other.call('plea_submit_design', {'design': BAD}); other.close()      # another server process, the newer protocol
        cli = r.s.cli(r.job, 'submit', BAD)
        ok, why, s = r.checked()
        aids = [(x.get('structuredContent') or {}).get('aid') for x in (a, b, c)]
        e.update(heads=[head(text_of(x)) for x in (a, b, c)], cli=(cli[0], head(cli[1])), aids=aids, tool_calls=r.calls(), notices=r.notices(), official_runs=s.get('official_runs'), record_verifies=ok, why=why)
        checks = {'all four answers are the same FAIL (the command line exits with status 2)': all(h == FAILED for h in e['heads']) and cli[0] == 2 and head(cli[1]) == FAILED,
                  'they name one run': len(set(aids)) == 1 and aids[0] is not None,
                  'the check ran once and one notice was sent': r.calls() == 1 and e['notices'] == 1,
                  'the record shows one official run': ok and s.get('official_runs') == 1}
    finally:
        r.stop()
    return checks, e


def f5():
    """The server offers exactly three tools, and a call that is not exactly a design goes no further."""
    r = Run('F5'); e = {}
    try:
        m = r.mcp(); tools = m.tools(); by = {t['name']: t for t in tools}
        schema = by.get('plea_submit_design', {}).get('inputSchema', {})
        tries = {'an extra argument naming a baseline': ('plea_submit_design', {'design': BAD, 'baseline_sha256': r.h}), 'an extra argument naming a check': ('plea_submit_design', {'design': BAD, 'check': 'mine.py'}),
                 'no design': ('plea_submit_design', {}), 'a design that is a list': ('plea_submit_design', {'design': [1, 2]}), 'a design that is text': ('plea_submit_design', {'design': 'PPS-GF40'}),
                 'an argument to plea_status': ('plea_status', {'baseline_sha256': r.h}), 'an argument to plea_show_requirement': ('plea_show_requirement', {'revision': 'B'})}
        got = {k: m.call(*v) for k, v in tries.items()}
        at_door = {'an extra field naming a baseline': raw(r.job, 'POST', '/submit', json.dumps({'design': BAD, 'baseline_sha256': r.h}).encode()),
                   'a design that is a list': raw(r.job, 'POST', '/submit', b'{"design": [1, 2]}'), 'an empty object': raw(r.job, 'POST', '/submit', b'{}')}
        journal = front_ctl.journal(r.s.home)
        e.update(names=[t['name'] for t in tools], schemas={n: t.get('inputSchema') for n, t in by.items()}, relay={k: (v.get('isError'), text_of(v)[:60]) for k, v in got.items()},
                 door={k: (st, p.get('refused')) for k, (st, p) in at_door.items()}, tool_calls=r.calls(), audit_rows=r.audit_rows(), journal_lines=len(journal.read_text().splitlines()) if journal.exists() else 0, notices=r.notices())
        checks = {'the tools are plea_show_requirement, plea_submit_design and plea_status, and no other': e['names'] == ['plea_show_requirement', 'plea_submit_design', 'plea_status'],
                  'plea_submit_design takes `design` and nothing else; the other two take nothing': schema.get('required') == ['design'] and list(schema.get('properties', {})) == ['design']
                      and all(t.get('inputSchema', {}).get('additionalProperties') is False for t in tools) and all(by[n]['inputSchema'].get('properties') == {} for n in ('plea_show_requirement', 'plea_status')),
                  'the relay refuses each malformed call itself and says nothing was sent': all(v.get('isError') is True and text_of(v).startswith('Nothing was sent.') for v in got.values()),
                  'asked directly, the front door refuses the same shapes (400)': all(st == 400 and p.get('refused') == 'BAD_REQUEST' for st, p in at_door.values()),
                  'nothing was run or recorded: no run of the check, no audit row, no journal line, no notice': r.calls() == 0 and e['audit_rows'] == 0 and e['journal_lines'] == 0 and e['notices'] == 0}
    finally:
        r.stop()
    return checks, e


def f6():
    """Through the front door a caller cannot choose the baseline: the defect of F1 is closed."""
    r = Run('F6'); e = {}
    try:
        b = r.s.baseline(case_b('F6'), relaxed(), alongside_reason='a relaxed copy baselined as new, as the test needs'); hb = b['baseline_sha256']; root_b = B.root_for(b['card'])        # the relaxed copy exists and has a budget
        by_tool = r.mcp().call('plea_submit_design', {'design': BAD, 'baseline_sha256': hb})
        by_body = raw(r.job, 'POST', '/submit', json.dumps({'design': BAD, 'baseline_sha256': hb}).encode())
        by_header = raw(r.job, 'POST', '/submit', json.dumps({'design': BAD}).encode(), headers={'X-Baseline': hb, 'X-Root': root_b})
        by_query = raw(r.job, 'POST', f'/submit?baseline_sha256={hb}', json.dumps({'design': BAD}).encode())
        before = (r.calls(), r.audit_rows(), r.audit_rows(root_b))
        inside = r.submit(dict(BAD, baseline_sha256=hb))                              # the baseline named inside the design itself
        honest = r.submit(BAD)
        show_q = raw(r.job, 'GET', f'/requirement?baseline_sha256={hb}'); base_q = raw(r.job, 'GET', f'/baseline/{hb}')
        ok_a, why_a, s_a = r.checked(); ok_b, why_b, s_b = r.checked(hb)
        verdicts = [by_header[1].get('verdict') or {}, (inside.get('structuredContent') or {}).get('verdict') or {}, (honest.get('structuredContent') or {}).get('verdict') or {}]
        e.update(by_tool=(by_tool.get('isError'), text_of(by_tool)[:40]), by_body=(by_body[0], by_body[1].get('refused')), by_header=(by_header[0], by_header[1].get('outcome')), by_query=by_query[0],
                 before=before, inside=head(text_of(inside)), honest=head(text_of(honest)), verdicts_name_a=[v.get('baseline_sha256') == r.h for v in verdicts], show_q=show_q[0], base_q=base_q[0],
                 record_a=dict(verifies=ok_a, why=why_a, runs=s_a.get('official_runs'), status=s_a.get('status'), reasons=sorted(x['reason_code'] for x in s_a.get('runs', []))),
                 record_b=dict(verifies=ok_b, runs=s_b.get('official_runs')), notices_a=r.notices(), notices_b=r.notices(hb), audit_rows_b=r.audit_rows(root_b))
        checks = {'a baseline named as a tool argument or as a field of the request is refused and nothing is run': by_tool.get('isError') is True and by_body[0] == 400 and by_body[1].get('refused') == 'BAD_REQUEST'
                      and by_query[0] == 404 and show_q[0] == 404 and base_q[0] == 404,
                  'a baseline named in a header changes nothing: the design is decided against the job\'s own baseline and fails': by_header[0] == 200 and by_header[1].get('outcome') == 'FAIL' and before[0] == 1 and before[2] == 0,
                  'a baseline named inside the design is a design outside the baseline: FAIL, on the record': head(text_of(inside)) == 'FAIL: DESIGN OUTSIDE THE BASELINE' and inside.get('isError') is False,
                  'every verdict returned names the job\'s own baseline': e['verdicts_name_a'] == [True, True, True] and head(text_of(honest)) == FAILED,
                  'the relaxed baseline has no run and no audit row; the job\'s record verifies with two failures, NOT VERIFIED': ok_a and ok_b and s_a.get('official_runs') == 2 and s_b.get('official_runs') == 0
                      and e['audit_rows_b'] == 0 and s_a.get('status') == 'NOT VERIFIED' and e['record_a']['reasons'] == ['DESIGN_OUTSIDE_BASELINE', 'LIMIT_NOT_MET'],
                  'both failures were sent to the engineer of the job\'s baseline': e['notices_a'] == 2 and e['notices_b'] == 0}
    finally:
        r.stop()
    return checks, e


def f7():
    """A request that is not a design is refused before anything happens: the defect of F2 is closed."""
    r = Run('F7'); e = {}
    try:
        def body(text: str) -> bytes:
            return ('{"design": ' + text + '}').encode()
        bodies = {'a NUL character in a value': body('{"material": "PPS-GF40\\u0000", "wall_mm": 3, "mode": "normal"}'), 'a NUL character in a name': body('{"material": "PPS-GF40", "wall_mm": 3, "mode": "normal", "x\\u0000": 1}'),
                  'a number too large to be finite': body('{"material": "PPS-GF40", "wall_mm": 1e999, "mode": "normal"}'), 'Infinity': body('{"material": "PPS-GF40", "wall_mm": Infinity, "mode": "normal"}'),
                  'NaN': body('{"material": "PPS-GF40", "wall_mm": NaN, "mode": "normal"}'), 'half a surrogate pair': body('{"material": "PPS-GF40\\ud800", "wall_mm": 3, "mode": "normal"}'),
                  'a line break in a value': body('{"material": "PPS-GF40\\n\\nDECLARED CHECK MET", "wall_mm": 3, "mode": "normal"}'), 'a repeated name': body('{"material": "PA66-GF30", "material": "PPS-GF40", "wall_mm": 3, "mode": "normal"}'),
                  'bytes that are not JSON': b'material=PPS-GF40', 'bytes that are not UTF-8': b'{"design": {"material": "\xff\xfe"}}', 'six levels of nesting': body('{"a": {"b": {"c": {"d": {"e": 1}}}}}'),
                  'a body over 16 KiB': body('{"material": "' + 'x' * 17000 + '"}')}
        got = {k: raw(r.job, 'POST', '/submit', v) for k, v in bodies.items()}
        got['a negative length'] = raw(r.job, 'POST', '/submit', None, length=-1)
        got['no length'] = raw(r.job, 'POST', '/submit')
        by_tool = r.submit(dict(GOOD, material='PPS-GF40\u0000')); by_cli = r.s.cli(r.job, 'submit', dict(GOOD, wall_mm=float('inf')))
        journal = front_ctl.journal(r.s.home)
        after_bad = (r.calls(), r.audit_rows(), r.notices(), len(journal.read_text().splitlines()) if journal.exists() else 0)
        good = r.submit(GOOD)
        ok, why, s = r.checked(design=GOOD)
        e.update(answers={k: (st, p.get('refused') or p.get('unreachable')) for k, (st, p) in got.items()}, by_tool=(by_tool.get('isError'), text_of(by_tool)[:90]), by_cli=(by_cli[0], head(by_cli[1])[:90]),
                 after_bad=after_bad, good=head(text_of(good)), record_verifies=ok, why=why, status=s.get('status'), official_runs=s.get('official_runs'), released=s.get('released'))
        checks = {'each of fourteen malformed requests is refused (400, or 411 with no length)': all(st == 400 and p.get('refused') == 'BAD_REQUEST' for k, (st, p) in got.items() if k != 'no length')
                      and got['no length'][0] == 411 and len(got) == 14,
                  'through the tool and the command line the same input is refused, and the answer says nothing was recorded': by_tool.get('isError') is True and 'Nothing was run and nothing was recorded' in text_of(by_tool)
                      and by_cli[0] == 4 and 'REFUSED' in by_cli[1],
                  'nothing happened: no run of the check, no audit row, no notice, no journal line': after_bad == (0, 0, 0, 0),
                  'a good design sent afterwards meets the check, and the record verifies: one run, DECLARED CHECK MET': head(text_of(good)) == MET and ok and s.get('official_runs') == 1
                      and s.get('status') == MET and (s.get('released') or {}).get('met') is True}
    finally:
        r.stop()
    return checks, e


def _imports(path: pathlib.Path) -> set:
    import ast
    names = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names |= {a.name.split('.')[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add((node.module or '').split('.')[0])
    return names


def f8():
    """What the assistant's side holds cannot reach the store, the witness or the gate, and cannot sign anything."""
    r = Run('F8'); e = {}
    try:
        files = sorted(p.name for p in r.job.iterdir())
        held = b''.join(p.read_bytes() for p in r.job.iterdir())
        secrets = {'the gateway\'s database address': b'postgresql://', 'the witness key': r.s.witness.private_hex.encode(), 'the gate key': r.s.gate.private_hex.encode(),
                   'the engineer\'s key': r.s.engineer.private_hex.encode(), 'the authority\'s key': r.s.ca_key.strip().splitlines()[1]}
        found = [k for k, v in secrets.items() if v in held]
        ca, pki = r.s.pki['ca'], r.s.pki
        w, g = f'https://127.0.0.1:{r.s.ports["witness"]}', f'https://127.0.0.1:{r.s.ports["host"]}'
        job_cert = (str(r.job / 'job.crt'), str(r.job / 'job.key'))
        reach = {'job certificate, witness': direct(w + '/pubkey', ca, *job_cert), 'job certificate, witness accept': direct(w + '/accept', ca, *job_cert, body={'root': r.root, 'aid': 'a-0', 'op': 'ACCEPT_RESERVATION'}),
                 'job certificate, gate host': direct(g + '/pubkey', ca, *job_cert), 'job certificate, gate host run': direct(g + '/run', ca, *job_cert, body={'root': r.root, 'aid': 'a-0', 'tool': 'verify', 'arguments': arguments_for(r.h, GOOD)}),
                 'another certificate of the same authority, witness': direct(w + '/pubkey', ca, *pki['governor']), 'another certificate of the same authority, gate host': direct(g + '/pubkey', ca, *pki['governor']),
                 'the front door\'s own certificate, witness': direct(w + '/pubkey', ca, *pki['frontdoor']), 'the front door\'s own certificate, gate host': direct(g + '/pubkey', ca, *pki['frontdoor'])}
        allowed = {'json', 'argparse', 'http', 'os', 'pathlib', 'ssl', 'sys', 'urllib', 'front_client'}
        imports = {f: sorted(_imports(GATEWAY / 'verify' / f)) for f in ('plea_verify_mcp.py', 'front_client.py')}
        res = r.submit(GOOD)                                                           # the server was started with an empty environment and the job folder only
        e.update(files=files, secrets_found=found, reach=reach, imports=imports, env=deploy_front.CLEAN_ENV, with_empty_environment=head(text_of(res)), tool_calls=r.calls())
        checks = {'the job folder holds the service address, the authority\'s certificate and the job\'s certificate and key, and nothing else': files == ['ca.crt', 'job.crt', 'job.json', 'job.key'] and not found,
                  'the job\'s certificate is refused by the witness service and by the gate host (403)': all(v == 403 for k, v in reach.items() if k.startswith('job certificate')),
                  'so is any other certificate of the authority that is not the front door\'s': reach['another certificate of the same authority, witness'] == 403 and reach['another certificate of the same authority, gate host'] == 403
                      and reach['the front door\'s own certificate, witness'] == 200 and reach['the front door\'s own certificate, gate host'] == 200,
                  'the MCP server and its client import the standard library only': all(set(v) <= allowed for v in imports.values()),
                  'started with an empty environment and that folder alone, the server still gets a design verified': head(text_of(res)) == MET and r.calls() == 1}
    finally:
        r.stop()
    return checks, e


def f9():
    """Nothing the engineer does is offered to the assistant's side, by tool or by address."""
    r = Run('F9'); e = {}
    try:
        m = r.mcp()
        def state():
            return (hashlib.sha256(front_door.jobs_path(r.s.home).read_bytes()).hexdigest(), sorted(p.name for p in (r.s.home / 'baselines').iterdir()),
                    sorted(p.name for p in (r.s.home / 'baselines' / r.h).iterdir()), r.audit_rows(), r.calls(), r.notices(), Store(deploy.LOCAL_DSN).observe(r.root)['business'])
        before = state()
        names = ['verify', 'plea_baseline', 'plea_revise', 'plea_acknowledge', 'plea_record', 'plea_enrol', 'plea_rebind', 'plea_keygen', 'plea_stop', 'baseline', 'revise', 'acknowledge', 'record']
        tools = {n: m.call(n, {'design': GOOD, 'baseline_sha256': r.h, 'reason': 'x'}) for n in names}
        methods = {n: m.rpc(n, {}).get('error', {}).get('code') for n in ('prompts/list', 'sampling/createMessage', 'logging/setLevel', 'completion/complete', 'tools/register', 'resources/subscribe')}
        write = m.rpc('resources/read', {'uri': 'plea://keys'}).get('error', {}).get('code')
        paths = {}
        for p in ('/baseline', '/revise', '/acknowledge', '/record', '/enrol', '/rebind', '/revoke', '/jobs', '/keys', '/stop', '/requirement', '/status', '/'):
            paths['POST ' + p] = raw(r.job, 'POST', p, json.dumps({'design': GOOD, 'baseline_sha256': r.h, 'reason': 'x'}).encode())[0]
        for p in ('/record', '/jobs', '/keys', '/ledger', '/inbox', '/acknowledgements', '/front/jobs.json', '/../engineer.key', '/submit', '/'):
            paths['GET ' + p] = raw(r.job, 'GET', p)[0]
        for meth in ('PUT', 'DELETE', 'PATCH'):
            paths[meth + ' /requirement'] = raw(r.job, meth, '/requirement', b'{}')[0]
        after = state()
        e.update(tools={n: v.get('error', {}).get('code') for n, v in tools.items()}, methods=methods, other_resource=write, paths=paths, unchanged=before == after, business=after[6])
        checks = {'a call to any other tool name is an unknown tool (-32602)': all(v.get('error', {}).get('code') == -32602 for v in tools.values()),
                  'the server answers no other kind of request, and serves no resource but the signed baseline': all(c == -32601 for c in methods.values()) and write == -32002,
                  'the front door answers 404 to every other address and method': all(st == 404 for st in paths.values()) and len(paths) == 26,
                  'nothing changed: the bindings, the baselines, the budget, the audit rows, the ledger, the inbox': before == after and after[3] == 0 and after[4] == 0 and after[6] == 'OPEN'}
    finally:
        r.stop()
    return checks, e


def f10():
    """Only the certificate the engineer enrolled, for a job the engineer has not revoked, under a binding the engineer signed, is answered."""
    r = Run('F10'); e = {}
    try:
        s, d = r.s, OUT / 'F10' / 'others'
        foreign_key, foreign_ca = TLS.make_ca('another-authority')
        k1, c1 = TLS.issue(foreign_key, foreign_ca, 'job-a', 'client'); k2, c2 = TLS.issue(s.ca_key, s.ca_cert, 'job-x', 'client'); k3, c3 = TLS.issue(s.ca_key, s.ca_cert, 'job-a', 'client')
        k4, c4 = TLS.issue(s.ca_key, s.ca_cert, 'frontdoor', 'client')
        tries = {'the right name from another authority': folder(d / 'foreign', 'job-a', s.url, s.ca_cert, c1, k1), 'this authority, a name never enrolled': folder(d / 'unknown', 'job-x', s.url, s.ca_cert, c2, k2),
                 'this authority, the enrolled name, another certificate': folder(d / 'twin', 'job-a', s.url, s.ca_cert, c3, k3), 'this authority, the front door\'s own name': folder(d / 'frontdoor', 'frontdoor', s.url, s.ca_cert, c4, k4)}
        got = {k: raw(v, 'POST', '/submit', json.dumps({'design': GOOD}).encode()) for k, v in tries.items()}
        got_read = {k: raw(v, 'GET', '/requirement') for k, v in tries.items()}
        enrolled = raw(r.job, 'GET', '/requirement')
        # the stored binding changed by someone who is not the engineer: pointed at another baseline, then re-signed with another key
        other = s.baseline(case_b('F10'), relaxed(), alongside_reason='a relaxed copy baselined as new, as the test needs'); path = front_door.jobs_path(s.home); honest = path.read_text()
        jobs = json.loads(honest); jobs['jobs']['job-a']['baseline_sha256'] = other['baseline_sha256']; path.write_text(json.dumps(jobs))
        edited = raw(r.job, 'POST', '/submit', json.dumps({'design': BAD}).encode())
        mine = Key(); b = dict(jobs['jobs']['job-a'], signer=mine.public_hex); b['signature'] = mine.sign(front_door.binding_message(b)); jobs['jobs']['job-a'] = b; path.write_text(json.dumps(jobs))
        resigned = raw(r.job, 'POST', '/submit', json.dumps({'design': BAD}).encode())
        path.write_text('not json'); broken = raw(r.job, 'GET', '/requirement')
        path.write_text(honest); restored = raw(r.job, 'GET', '/requirement')
        before_revoke = r.calls()
        s.revoke('job-a')
        revoked = raw(r.job, 'POST', '/submit', json.dumps({'design': GOOD}).encode()); by_tool = r.submit(GOOD); by_cli = s.cli(r.job, 'status')
        after_revoke = path.read_text(); path.write_text(honest)                        # the earlier signed binding put back in the file
        put_back = raw(r.job, 'POST', '/submit', json.dumps({'design': GOOD}).encode()); path.write_text(after_revoke)
        try:
            front_ctl.enrol(s.home, 'job-a', r.h, s.engineer, s.ca_cert, s.ca_key, s.url, d / 'again'); again = 'enrolled'
        except front_ctl.Refused as exc:
            again = str(exc)
        try:
            front_ctl.enrol(s.home, 'job-next', other['baseline_sha256'], s.engineer, s.ca_cert, s.ca_key, s.url, d / 'next'); next_job = 'enrolled'
        except front_ctl.Refused as exc:
            next_job = str(exc)
        e.update(submit={k: (st, p.get('refused') or p.get('unreachable')) for k, (st, p) in got.items()}, read={k: (st, p.get('refused') or p.get('unreachable')) for k, (st, p) in got_read.items()}, enrolled=enrolled[0],
                 edited=(edited[0], edited[1].get('refused')), resigned=(resigned[0], resigned[1].get('refused')), broken=(broken[0], broken[1].get('refused')), restored=restored[0],
                 revoked=(revoked[0], revoked[1].get('refused')), put_back=(put_back[0], put_back[1].get('refused')), by_tool=(by_tool.get('isError'), text_of(by_tool)[:70]), by_cli=by_cli[0], enrol_again=again[:60], relaxed_copy_after_revoking=next_job[:70], tool_calls=r.calls(), audit_rows=r.audit_rows(),
                 audit_rows_other=r.audit_rows(B.root_for(other['card'])))
        refused = lambda x: x[0] == 403 and x[1].get('refused') == 'NOT_ENROLLED'
        checks = {'a certificate from another authority gets no answer at all': got['the right name from another authority'][0] is None and got_read['the right name from another authority'][0] is None,
                  'a certificate of this authority that was not enrolled is refused (403), whatever its name': all(refused(got[k]) and refused(got_read[k]) for k in list(tries)[1:]) and enrolled[0] == 200,
                  'a binding pointed at another baseline, or re-signed by another key, or unreadable, admits nobody': refused(edited) and refused(resigned) and refused(broken) and restored[0] == 200,
                  'after the engineer revokes the job its own certificate is refused, and the tool says so as an error': refused(revoked) and by_tool.get('isError') is True and 'REFUSED' in text_of(by_tool) and by_cli[0] == 4
                      and 'used once' in again and 'already under baseline' in next_job,
                  'putting the earlier signed binding back in the file does not undo the revocation': refused(put_back),
                  'nothing was run in any of this': r.calls() == 0 and before_revoke == 0 and e['audit_rows'] == 0 and e['audit_rows_other'] == 0}
    finally:
        r.stop()
    return checks, e


def f11():
    """A job moves to another baseline only when that baseline is a signed revision of its own, which says what it replaced and what had failed."""
    r = Run('F11'); e = {}
    try:
        s = r.s
        first = r.submit(BAD)
        src = case_b('F11')
        unrelated = s.baseline(src, relaxed(), alongside_reason='a relaxed copy baselined as new, as the test needs')                                          # a relaxed copy baselined as new: not a revision
        try:
            s.rebind('job-a', unrelated['baseline_sha256']); moved = 'moved'
        except front_ctl.Refused as exc:
            moved = str(exc)
        try:
            s.enrol('job-quiet', unrelated['baseline_sha256']); second = 'enrolled'
        except front_ctl.Refused as exc:
            second = str(exc)
        still_a = r.submit(BAD)
        req = dict(json.loads((CASE / 'card.json').read_text())['requirement'], revision='B', statement='The housing shall withstand continuous operation at 170 C.')
        env_b = verify_ctl.revise(s.home, src, relaxed(requirement=req), s.engineer, r.h, 'Customer lowered the operating temperature (CR-17).')
        hb = env_b['baseline_sha256']
        calls_before = r.calls()
        on_old = r.submit({'material': 'PA66-GF30', 'wall_mm': 3.5, 'mode': 'normal'})    # the superseded baseline takes no more runs
        calls_after_old = r.calls()
        shown_old = r.mcp().call('plea_show_requirement')
        binding = s.rebind('job-a', hb)
        shown = r.mcp().call('plea_show_requirement'); on_new = r.submit(BAD)
        ok_a, why_a, s_a = r.checked(); ok_b, checks_b, s_b = check_record.verify(s.record(hb), s.keys, BAD); text_b = check_record.render(ok_b, checks_b, s_b)
        log = front_ctl.log(s.home)
        e.update(first=head(text_of(first)), rebind_to_unrelated=moved[:90], second_job=second[:90], still_a=((still_a.get('structuredContent') or {}).get('baseline_sha256') == r.h, head(text_of(still_a))),
                 on_old=(on_old.get('isError'), (on_old.get('structuredContent') or {}).get('refused'), text_of(on_old)[:60]), ran_on_old=calls_after_old - calls_before,
                 shown_old=((shown_old.get('structuredContent') or {}).get('accepting_runs'), [l.strip()[:60] for l in text_of(shown_old).splitlines() if 'NO FURTHER RUNS' in l]),
                 shown=[l.strip() for l in text_of(shown).splitlines() if 'SUPERSEDES' in l], on_new=(head(text_of(on_new)), (on_new.get('structuredContent') or {}).get('baseline_sha256') == hb),
                 rev_a=dict(verifies=ok_a, why=why_a, status=s_a.get('status'), not_met=s_a.get('not_met')), rev_b=dict(verifies=ok_b, status=s_b.get('status'), released=s_b.get('released')),
                 headline=[l.strip()[:100] for l in text_b.splitlines() if 'CHANGED AFTER THE EVENT' in l], log=[(b['event'], b['job'], b['baseline_sha256'][:8], (b.get('previous') or '')[:8]) for b in log],
                 log_signed=[front_door.binding_valid(b, (s.keys['engineer'],)) for b in log])
        checks = {'moving the job to a baseline that is merely different is refused, and so is a second job for the same requirement with no reason': 'does not supersede' in moved and 'already under baseline' in second
                      and e['still_a'] == (True, FAILED),
                  'once the engineer revises, the old baseline takes no further runs: the tool reports the refusal as an error, nothing is run, and the requirement shown says so': on_old.get('isError') is True and e['on_old'][1] == 'STOPPED' and e['ran_on_old'] == 0
                      and e['shown_old'][0] is False and len(e['shown_old'][1]) == 1,
                  'after the move the requirement shown says what it replaced, what had failed and why': len(e['shown']) == 1 and '(1 official runs, 1 not met)' in e['shown'][0] and 'CR-17' in e['shown'][0],
                  'the design that failed on A meets the check on B, and B\'s record is headed CHANGED AFTER THE EVENT': e['on_new'] == (MET, True) and ok_b and s_b.get('status') == MET and len(e['headline']) == 1,
                  'the old record still verifies and still shows the failure': ok_a and s_a.get('status') == 'NOT VERIFIED' and s_a.get('not_met') == 1,
                  'the service\'s log holds the enrolment and the move, each signed by the engineer, the move naming what it replaced': e['log'] == [('ENROL', 'job-a', r.h[:8], ''), ('REBIND', 'job-a', hb[:8], r.h[:8])]
                      and e['log_signed'] == [True, True] and binding['previous'] == r.h}
    finally:
        r.stop()
    return checks, e


def f12():
    """The service dying part-way through a run leaves it counted, without a verdict, and never run again."""
    r = Run('F12', crash_at='verify_running'); e = {}
    try:
        during = r.submit(GOOD); time.sleep(0.3); exit_code = r.s.procs['host'].poll()
        r.s.stop_host(); r.s.start_host()
        again = r.submit(GOOD); again2 = r.submit(GOOD)
        other = r.submit({'material': 'PPS-GF40', 'wall_mm': 2.5, 'mode': 'normal'})
        status = r.mcp().call('plea_status')
        # from inside: an error from the governor that is not the gate's signed "I do not know" must not be reported as an interrupted run
        front = front_door.Front(r.s.home, Store(deploy.LOCAL_DSN), {'journal': str(front_ctl.journal(r.s.home))}, (r.s.keys['engineer'],))

        class Broken(front_door.ServiceClient):
            def governor(self):
                raise RuntimeError('not the gate')
        front.client = lambda b: Broken(front, b, None)
        calls_before = r.calls()
        stray = front.submit(front_door.read_jobs(r.s.home)['job-a'], {'material': 'PPS-GF40', 'wall_mm': 3.3, 'mode': 'normal'})
        stray_ran = r.calls() - calls_before
        ok, why, s = r.checked(design=GOOD)
        sc = again.get('structuredContent') or {}
        e.update(during=(during.get('isError'), text_of(during)[:80]), host_exit=exit_code, again=(again.get('isError'), head(text_of(again)), sc.get('outcome'), sc.get('met')), again2=head(text_of(again2)),
                 tool_calls_for_design=sum(1 for x in r.s.ledger('called') if x.get('design') == GOOD), verdicts_for_design=sum(1 for x in r.s.ledger('verdict') if x.get('design_sha256') == B.design_hash(GOOD)),
                 outcomes=sorted(x['outcome'] for x in s.get('runs', [])), released=s.get('released'), other=head(text_of(other)), stray=(stray[0], stray[1].get('refused'), stray[1].get('outcome'), stray_ran), status_says=[l.strip()[:60] for l in text_of(status).splitlines()[1:2]], record_verifies=ok, why=why)
        checks = {'the host died during the run (exit 137) and the tool did not say it passed': exit_code == 137 and MET not in text_of(during) and 'NOT VERIFIED' in text_of(during),
                  'asked again, twice, the answer is UNKNOWN: interrupted, not met': head(text_of(again)) == head(text_of(again2)) == 'UNKNOWN: THE RUN WAS INTERRUPTED' and sc.get('outcome') == 'INTERRUPTED' and sc.get('met') is False,
                  'the check was started once for that design and never produced a verdict': e['tool_calls_for_design'] == 1 and e['verdicts_for_design'] == 0,
                  'the record shows it INTERRUPTED and counted, and that design is not verified': ok and e['outcomes'] == ['INTERRUPTED', 'PASS'] and s['released']['met'] is False,
                  'a different design can still be verified': head(text_of(other)) == MET,
                  'an error that is not the gate\'s signed "unknown" is reported as no verdict, not as an interrupted run (the front door\'s own code, called directly)': e['stray'] == (503, 'UNAVAILABLE', None, 0)}
    finally:
        r.stop()
    return checks, e


def f13():
    """Two jobs on one service each see and charge only their own baseline."""
    r = Run('F13'); e = {}
    try:
        s = r.s
        req2 = dict(json.loads((CASE / 'card.json').read_text())['requirement'], id='REQ-SELFTEST-002', title='Bracket service temperature', statement='The bracket shall withstand continuous operation at 170 C.')
        env2 = s.baseline(case_b('F13'), relaxed(requirement=req2)); h2 = env2['baseline_sha256']
        job_b = s.enrol('job-b', h2)                                                    # another requirement: no reason needed
        same = s.baseline(case_b('F13'), relaxed(), alongside_reason='a relaxed copy baselined as new, as the test needs')                                     # the first requirement again, relaxed, baselined as new
        try:
            s.enrol('job-c', same['baseline_sha256']); quiet = 'enrolled'
        except front_ctl.Refused as exc:
            quiet = str(exc)
        s.enrol('job-c', same['baseline_sha256'], reason='Separate prototype build, agreed with the client (CR-21).')
        mb = s.mcp(job_b)
        a = r.submit(BAD); b = mb.call('plea_submit_design', {'design': BAD})
        sa = r.mcp().call('plea_status'); sb = mb.call('plea_status'); show_b = mb.call('plea_show_requirement'); mb.close()
        ok_a, why_a, s_a = r.checked(); ok_b, why_b, s_b = r.checked(h2)
        log = front_ctl.log(s.home)
        s.stop_front(); s.start_front(rate=3)                                           # the same service, allowing a job three requests a minute
        paced = [raw(r.job, 'GET', '/status')[0] for _ in range(4)] + [raw(job_b, 'GET', '/status')[0]]
        e.update(paced=paced, a=head(text_of(a)), b=head(text_of(b)), a_names=(a.get('structuredContent') or {}).get('baseline_sha256') == r.h, b_names=(b.get('structuredContent') or {}).get('baseline_sha256') == h2,
                 status_a=(sa.get('structuredContent') or {}).get('runs'), status_b=(sb.get('structuredContent') or {}).get('runs'), b_sees=(show_b.get('structuredContent') or {}).get('requirement', {}).get('id'),
                 record_a=dict(verifies=ok_a, runs=s_a.get('official_runs'), status=s_a.get('status')), record_b=dict(verifies=ok_b, runs=s_b.get('official_runs'), status=s_b.get('status')),
                 notices_a=r.notices(), notices_b=r.notices(h2), quiet=quiet[:80], notes=[(x['job'], x.get('note')) for x in log])
        checks = {'the same design fails for one job and meets the check for the other, each against its own baseline': e['a'] == FAILED and e['b'] == MET and e['a_names'] and e['b_names'],
                  'each job\'s status shows its own run only': e['status_a'] == {'total': 1, 'PASS': 0, 'FAIL': 1, 'UNKNOWN': 0} and e['status_b'] == {'total': 1, 'PASS': 1, 'FAIL': 0, 'UNKNOWN': 0} and e['b_sees'] == 'REQ-SELFTEST-002',
                  'each record verifies with one run, and only the failing job\'s engineer notice was sent': ok_a and ok_b and s_a.get('official_runs') == 1 and s_b.get('official_runs') == 1 and e['notices_a'] == 1 and e['notices_b'] == 0,
                  'a second job for a requirement already under another baseline needs the engineer\'s reason, which is kept in the signed log': 'already under baseline' in quiet
                      and e['notes'] == [('job-a', None), ('job-b', None), ('job-c', 'Separate prototype build, agreed with the client (CR-21).')],
                  'a job that asks too often is refused (429) without slowing the other': paced == [200, 200, 200, 429, 200]}
    finally:
        r.stop()
    return checks, e


class Counter:
    """Something listening where the front door was: it counts the connections made to it and closes each at once."""

    def __init__(self, port: int):
        self.count, self._stop = 0, False
        self.sock = socket.socket(); self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('127.0.0.1', port)); self.sock.listen(8); self.sock.settimeout(0.1)
        self.thread = threading.Thread(target=self._run, daemon=True); self.thread.start()

    def _run(self):
        while not self._stop:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                continue
            self.count += 1; conn.close()

    def stop(self) -> int:
        self._stop = True; self.thread.join(timeout=2); self.sock.close()
        return self.count


def f14():
    """The MCP server speaks both forms of the protocol, says nothing but protocol on its output, and makes one request per call."""
    r = Run('F14'); e = {}
    try:
        s = r.s
        opened = {}
        for v in ('2025-11-25', '2025-06-18', '2025-03-26', '2024-11-05', '2099-01-01'):
            m = s.mcp(r.job, version=v); opened[v] = m.opened['result']['protocolVersion']
            if v == '2024-11-05':
                old_tools = m.tools(); old_call = m.call('plea_status')
            if v == '2025-06-18':
                mid_call = m.call('plea_status')
            m.close()
        mod = s.mcp(r.job, era='modern')
        listed = mod.rpc('tools/list')['result']; discover = mod.rpc('server/discover')['result']; mod_call = mod.call('plea_status')
        mod.version = '2031-01-01'; wrong = mod.rpc('tools/list').get('error', {})
        mod.send({'jsonrpc': '2.0', 'id': 900, 'method': 'tools/list', 'params': {'_meta': {'io.modelcontextprotocol/protocolVersion': '2026-07-28'}}}); no_caps = mod.read().get('error', {})
        mod.close()
        rw = s.mcp(r.job, era='raw')
        early = rw.rpc('tools/call', {'name': 'plea_submit_design', 'arguments': {'design': GOOD}}).get('error', {}); ping = rw.rpc('ping')
        rw.send('this is not json'); parse = rw.read()
        rw.send('[{"jsonrpc": "2.0", "id": 1, "method": "ping"}]'); batch = rw.read()
        rw.send({'jsonrpc': '2.0', 'method': 'notifications/cancelled', 'params': {'requestId': 1}}); after_note = rw.rpc('ping')      # the notification gets no reply: the next line answers the ping
        code = rw.close(); stderr = rw.proc.stderr.read()
        calls_before = r.calls()
        s.stop_front(); time.sleep(0.2); counter = Counter(s.ports['front'])
        m = r.mcp(); down = m.call('plea_submit_design', {'design': GOOD}); time.sleep(0.3); connections = counter.stop(); ran_while_down = r.calls() - calls_before
        s.start_front(); back = m.call('plea_submit_design', {'design': GOOD})
        e.update(opened=opened, old_tool_fields=sorted(old_tools[0]), old_has_structured='structuredContent' in old_call, mid_has_structured='structuredContent' in mid_call,
                 modern=dict(result_type=listed.get('resultType'), server=(listed.get('_meta') or {}).get('io.modelcontextprotocol/serverInfo', {}).get('name'), tools=[t['name'] for t in listed.get('tools', [])],
                             versions=discover.get('supportedVersions'), call_type=mod_call.get('resultType'), has_structured='structuredContent' in mod_call),
                 wrong=(wrong.get('code'), (wrong.get('data') or {}).get('requested'), '2026-07-28' in ((wrong.get('data') or {}).get('supported') or [])), no_caps=no_caps.get('code'), early=early.get('code'), ping=ping.get('result'),
                 parse=(parse.get('error') or {}).get('code'), batch=(batch.get('error') or {}).get('code'), after_note=(after_note.get('id'), after_note.get('result')), exit=code, stderr=stderr[:80],
                 down=(down.get('isError'), text_of(down)[:60]), connections=connections, ran_while_down=ran_while_down, back=head(text_of(back)), tool_calls=r.calls())
        checks = {'opened with the handshake, each earlier revision is agreed as asked, and an unknown one is answered with the latest of them': opened == {'2025-11-25': '2025-11-25', '2025-06-18': '2025-06-18', '2025-03-26': '2025-03-26',
                      '2024-11-05': '2024-11-05', '2099-01-01': '2025-11-25'},
                  'a revision without those fields is not sent them: no annotations or structured content in 2024-11-05, structured content from 2025-06-18': e['old_tool_fields'] == ['description', 'inputSchema', 'name']
                      and not e['old_has_structured'] and e['mid_has_structured'],
                  'with the version on each request (2026-07-28) the same three tools are served, complete, and server/discover lists the versions': e['modern']['result_type'] == 'complete' and e['modern']['call_type'] == 'complete'
                      and e['modern']['tools'] == ['plea_show_requirement', 'plea_submit_design', 'plea_status'] and e['modern']['server'] == 'plea-verification' and e['modern']['versions'][0] == '2026-07-28' and e['modern']['has_structured'],
                  'an unsupported version, a request with no capabilities, and a tool call before any opening are refused with their codes and nothing is run': e['wrong'] == (-32022, '2031-01-01', True) and no_caps.get('code') == -32602
                      and early.get('code') == -32600 and calls_before == 0,
                  'a line that is not JSON and a batch each get an error reply, a notification gets none, and closing the input ends the server (exit 0)': e['parse'] == -32700 and e['batch'] == -32600 and after_note.get('result') == {}
                      and ping.get('result') == {} and code == 0 and stderr == '',
                  'with the service unreachable a call reports that as an error after one connection, not more, and runs nothing': down.get('isError') is True and 'could not be reached' in text_of(down) and 'NOT VERIFIED' in text_of(down)
                      and connections == 1 and e['ran_while_down'] == 0,
                  'when the service is back the same call gets its verdict, from one run': head(text_of(back)) == MET and r.calls() == 1}
    finally:
        r.stop()
    return checks, e


def f15():
    """A stored baseline changed after it was signed is not shown, and a design sent against it is decided UNKNOWN by the gate, counted, and sent to the engineer."""
    r = Run('F15'); e = {}
    try:
        stored = r.s.home / 'baselines' / r.h / 'baseline.json'; good = stored.read_text()
        def design(wall): return {'material': 'PA66-GF30', 'wall_mm': wall, 'mode': 'normal'}
        env = json.loads(good); env['card']['criteria'][0]['limit'] = '150'; stored.write_text(json.dumps(env))            # the limit relaxed in the stored card
        shown = raw(r.job, 'GET', '/requirement'); given = raw(r.job, 'GET', '/baseline'); by_tool = r.mcp().call('plea_show_requirement')
        relaxed_card = r.submit(design(2.5))
        other = Key(); env['card']['responsible_engineer']['key'] = other.public_hex; env['baseline_sha256'] = B.card_hash(env['card'])
        from verify_record import envelope_message
        env['signature'] = {'signer': other.public_hex, 'signature': other.sign(envelope_message(env['card'], env['controls_run']))}; stored.write_text(json.dumps(env))   # properly signed, by someone else
        forged = r.submit(design(2.6))
        status_meanwhile = raw(r.job, 'GET', '/status')
        stored.write_text(good)
        restored = r.submit(design(2.8)); shown_again = raw(r.job, 'GET', '/requirement')
        notices_before = r.notices()
        env = json.loads(good); del env['card']['load_case']; stored.write_text(json.dumps(env))                              # no longer a card at all
        shown_not_a_card = raw(r.job, 'GET', '/requirement'); not_a_card = r.submit(design(2.9))
        stored.write_text('{"card": ' + '[' * 100000 + ']' * 100000 + '}')                                                   # nested too deep to be read at all
        shown_deep = raw(r.job, 'GET', '/requirement'); too_deep = r.submit(design(3.1)); stored.write_text(good)
        ok, why, s = r.checked()
        sc = lambda x: x.get('structuredContent') or {}
        e.update(shown=(shown[0], shown[1].get('refused')), given=(given[0], given[1].get('refused')), by_tool=(by_tool.get('isError'), text_of(by_tool)[:60]),
                 relaxed_card=(relaxed_card.get('isError'), head(text_of(relaxed_card)), sc(relaxed_card).get('outcome'), (sc(relaxed_card).get('verdict') or {}).get('reason_code')),
                 forged=(head(text_of(forged)), sc(forged).get('outcome')), status_meanwhile=(status_meanwhile[0], (status_meanwhile[1].get('runs') or {}).get('total')), restored=head(text_of(restored)), shown_again=shown_again[0],
                 not_a_card=(not_a_card.get('isError'), head(text_of(not_a_card)), sc(not_a_card).get('outcome'), sc(not_a_card).get('met'), (sc(not_a_card).get('verdict') or {}).get('reason_code')),
                 too_deep=(too_deep.get('isError'), head(text_of(too_deep)), sc(too_deep).get('outcome'), sc(too_deep).get('met'), (sc(too_deep).get('verdict') or {}).get('reason_code')),
                 shown_not_a_card=(shown_not_a_card[0], shown_not_a_card[1].get('refused')), shown_deep=(shown_deep[0], shown_deep[1].get('refused')),
                 notices_before=notices_before, notices=r.notices(), outcomes=sorted(x['outcome'] for x in s.get('runs', [])), status=s.get('status'), met=s.get('met'), record_verifies=ok, why=why)
        no_baseline = 'UNKNOWN: NO USABLE BASELINE IS HELD FOR THIS JOB'
        checks = {'the changed baseline is not shown, by address or by tool': e['shown'] == (500, 'BASELINE_UNAVAILABLE') and e['given'] == (500, 'BASELINE_UNAVAILABLE') and by_tool.get('isError') is True,
                  'a design that the relaxed card would pass is decided UNKNOWN by the gate, not a pass': e['relaxed_card'] == (False, no_baseline, 'UNKNOWN', 'BASELINE_MISMATCH'),
                  'so is one sent against a relaxed card properly signed by another key, and the runs are counted': e['forged'] == (no_baseline, 'UNKNOWN') and e['status_meanwhile'] == (200, 2),
                  'with the file restored the requirement is shown again and still fails': shown_again[0] == 200 and e['restored'] == FAILED,
                  'all three results were sent to the engineer': notices_before == 3,
                  'a stored file that is no longer a card at all, or is nested too deep to read, is not shown, and a design sent is decided UNKNOWN by the gate in the same way and sent to the engineer (Amendment 2)':
                      e['not_a_card'] == (False, no_baseline, 'UNKNOWN', False, 'BASELINE_MISMATCH') and e['too_deep'] == (False, no_baseline, 'UNKNOWN', False, 'BASELINE_MISMATCH')
                      and e['shown_not_a_card'] == (500, 'BASELINE_UNAVAILABLE') and e['shown_deep'] == (500, 'BASELINE_UNAVAILABLE') and e['notices'] == 5,
                  'no run met the check, the record verifies and the status is NOT VERIFIED': ok and s.get('met') == 0 and s.get('status') == 'NOT VERIFIED' and e['outcomes'] == ['FAIL', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN']}
    finally:
        r.stop()
    return checks, e


def f16():
    """One run at a time for a job: a second design sent while the first is being checked is refused and not run."""
    r = Run('F16'); e = {}
    try:
        slow = {'material': 'PPS-GF40', 'wall_mm': 3, 'mode': 'hang'}                    # the check does not finish; the gate stops it after 30 s
        first = {}
        t = threading.Thread(target=lambda: first.update(answer=raw(r.job, 'POST', '/submit', json.dumps({'design': slow}).encode())), daemon=True)
        t0 = time.time(); t.start(); time.sleep(2.0)
        second = raw(r.job, 'POST', '/submit', json.dumps({'design': GOOD}).encode()); by_tool = r.submit(GOOD); status = raw(r.job, 'GET', '/status')
        calls_meanwhile = [x.get('design') for x in r.s.ledger('called')]
        t.join(timeout=70); took = time.time() - t0; time.sleep(1.5)
        after = raw(r.job, 'POST', '/submit', json.dumps({'design': slow}).encode()); good = r.submit(GOOD)
        ok, why, s = r.checked(design=GOOD)
        answer = first.get('answer') or (None, {})
        e.update(second=(second[0], second[1].get('refused')), by_tool=(by_tool.get('isError'), text_of(by_tool)[:70]), status=status[0], calls_meanwhile=calls_meanwhile, took=round(took, 1),
                 first=(answer[0], answer[1].get('outcome') or answer[1].get('refused')), after=(after[0], after[1].get('outcome'), (after[1].get('verdict') or {}).get('reason_code')), good=head(text_of(good)),
                 calls=[x.get('design', {}).get('mode') for x in r.s.ledger('called')], outcomes=sorted(x['outcome'] for x in s.get('runs', [])), record_verifies=ok, why=why, status_of_record=s.get('status'))
        checks = {'while the first design is being checked, a second is refused (409), by address and by tool, and is not run': e['second'] == (409, 'IN_PROGRESS') and by_tool.get('isError') is True
                      and 'already being verified' in text_of(by_tool) and calls_meanwhile == [slow],
                  'the status can still be read meanwhile': status[0] == 200,
                  'the check that did not finish is stopped and is UNKNOWN, never a pass': e['after'] == (200, 'UNKNOWN', 'CHECK_ERROR') and e['first'] in ((200, 'UNKNOWN'), (503, 'UNAVAILABLE')) and 25 < took < 60,
                  'afterwards the second design is verified, and each design was run once': e['good'] == MET and e['calls'] == ['hang', 'normal'],
                  'the record verifies: one unknown, one met': ok and e['outcomes'] == ['PASS', 'UNKNOWN'] and s.get('status') == MET}
    finally:
        r.stop()
    return checks, e


def _clashing_pairs(n: int) -> list:
    """Pairs of designs inside the fixture's design space, both failing at 200 C, whose design hashes share their first eight hex digits."""
    seen, pairs, i = {}, [], 0
    while len(pairs) < n and i < 1900000:
        d = {'material': 'PA66-GF30', 'wall_mm': round(2 + i / 1000000, 6), 'mode': 'normal'}; i += 1
        k = B.design_hash(d)[:8]
        if k in seen:
            pairs.append((seen[k], d))
        else:
            seen[k] = d
    return pairs


def f17():
    """Two failures whose notices would have the same file name both reach the engineer: a notice is never written over another.
    Restated by Amendment 14.  Before, the case was made by timing alone, two runs in a row ending within one second, and when
    it was not made the test failed without having tested anything.  Now the naming is shown with no clock at all; and the
    case is made through the service by two jobs sending at the same moment, and the test says for itself whether it was
    made: COLLISION_HANDLED, COLLISION_MISHANDLED, or PRECONDITION_NOT_MET, which is a failure to test and never a pass."""
    r = Run('F17'); e = {}
    try:
        stem_of = lambda n: '_'.join(str(n)[:-4].split('_')[:3])                              # time to the second, verdict, first eight digits of the design hash
        # with no clock: two notices delivered under one name, by the call the gate's tool makes for every notice
        scratch = OUT / 'F17' / 'no-clock'; held = '0' * 64; one = '20261120T000000Z_FAIL_ff539c34'
        __import__('shutil').rmtree(scratch, ignore_errors=True)                               # nothing of an earlier run is there
        wrote = [service_notices.deliver(scratch, held, one, lambda engineer, i=i: f'the notice of design {i}\n' + 'x' * 300) for i in (1, 2)]
        there = sorted(str(q.relative_to(scratch)) for q in scratch.rglob('*') if q.is_file())
        folder = next((q.parent for q in scratch.rglob(one + '.txt')), scratch)
        own = [(folder / n).read_text().startswith(f'the notice of design {i}\n') if n and (folder / n).is_file() else False for i, (_, n) in zip((1, 2), wrote)]
        # through the service: two jobs on the one baseline, each sending one of two designs whose hashes begin alike, at the same moment
        box = r.s.home / 'inbox' / r.h[:16]
        jobs = {'a': r.job, 'b': r.s.enrol('job-b', r.h)}                                     # one job has one design verified at a time; a second is refused IN_PROGRESS
        tried, result, made = [], 'PRECONDITION_NOT_MET', None
        for a, b in _clashing_pairs(6):
            time.sleep(1.03 - time.time() % 1)                                               # both begin early in a second; each takes about half of one
            before = len(r.s.ledger('verdict')); got = {}
            threads = [threading.Thread(target=lambda k=k, d=d: got.update({k: raw(jobs[k], 'POST', '/submit', json.dumps({'design': d}).encode())})) for k, d in (('a', a), ('b', b))]
            for th in threads:
                th.start()
            for th in threads:
                th.join()
            entries = r.s.ledger('verdict')[before:]
            names = [x.get('notice') for x in entries]
            designs = [next((d for d in (a, b) if B.design_hash(d) == x.get('design_sha256')), None) for x in entries]
            outcomes = [(got.get(k) or (None, {}))[1].get('outcome') if isinstance((got.get(k) or (None, {}))[1], dict) else None for k in ('a', 'b')]
            met = len(names) == 2 and all(names) and stem_of(names[0]) == stem_of(names[1])
            tried.append({'outcomes': outcomes, 'names': names, 'precondition_met': met})
            if met:                                                                           # the case is made: now, and only now, the property is judged
                texts = [(box / n).read_text() if (box / n).is_file() else '' for n in names]
                made = {'pair': (a, b), 'names': names, 'distinct': len(set(names)) == 2, 'two_designs': None not in designs and designs[0] != designs[1],
                        'own_text': [d is not None and f"wall_mm = {d.get('wall_mm')}" in x for d, x in zip(designs, texts)], 'sizes': [len(x) for x in texts],
                        'same_hash_start': B.design_hash(a)[:8] == B.design_hash(b)[:8], 'both_failed': outcomes == ['FAIL', 'FAIL']}
                good = made['distinct'] and made['two_designs'] and made['own_text'] == [True, True] and all(n > 200 for n in made['sizes'])
                result = 'COLLISION_HANDLED' if good else 'COLLISION_MISHANDLED'
                break
        files = sorted(q.name for q in box.glob('*.txt')) if box.exists() else []
        failures = sum(1 for row in tried for o in row['outcomes'] if o == 'FAIL')
        ok, why, s = r.checked()
        e.update(no_clock=dict(wrote=wrote, files=there, own_text=own), result=result, tried=tried, made=made, files=len(files), failures=failures, record_verifies=ok, why=why,
                 not_met=s.get('not_met'), status=s.get('status'))
        checks = {'with no clock: two notices delivered under one name are two files, the second numbered, each with its own text, and nothing else is left':
                      [n for _, n in wrote] == [one + '.txt', one + '_2.txt'] and wrote[0][0] == wrote[1][0] and own == [True, True] and len(there) == 2,
                  'through the service the case was made: two designs whose hashes begin with the same eight digits, sent at the same moment by two jobs on the one baseline, both failed, with their notices named for the same second (a case not made is PRECONDITION_NOT_MET: a failure to test, never a pass)':
                      result != 'PRECONDITION_NOT_MET' and made is not None and made['same_hash_start'] and made['both_failed'],
                  'and it was handled: each failure has its own notice, two files with different names, neither empty, each naming its own design':
                      result == 'COLLISION_HANDLED',
                  'the inbox holds one notice for every failure, and the record verifies with all of them':
                      e['files'] == failures and failures >= 2 and ok and s.get('not_met') == failures and s.get('status') == 'NOT VERIFIED'}
    finally:
        r.stop()
    return checks, e


def _number_sample() -> list:
    """Numbers of many sizes and both signs, as a design might hold them: 864 with a decimal point or an exponent, and 8 whole numbers."""
    out = [sign * m * 10.0 ** x for m in (1.0, 1.5, 2.25, 9.999999999999998, 3.141592653589793, 1.0000000000000002, 7.0) for x in range(-30, 31) for sign in (1, -1)]
    out += [0.0, -0.0, 1e16, -1e16, 9999999999999998.0, -9999999999999998.0, 1e308, 5e-324, 2.5, 3.0]
    out += [0, -1, 3, 10 ** 16, -10 ** 16, 10 ** 22, 12345678901234567890, 10 ** 300]
    return out


def f18():
    """A number the database would hand back changed is refused before anything happens, so it cannot leave a record unable to verify."""
    r = Run('F18'); e = {}
    try:
        def body(text: str) -> bytes:
            return ('{"design": {"material": "PPS-GF40", "wall_mm": ' + text + ', "mode": "normal"}}').encode()
        changed = ['1e22', '-0.0', '1e16', '1.5e16', '1e308', '-1e16', '-0e0', '-1e-400', '10000000000000000.0']
        refused = {t: raw(r.job, 'POST', '/submit', body(t)) for t in changed}
        nested = {t: raw(r.job, 'POST', '/submit', ('{"design": {"material": "PPS-GF40", "wall_mm": 3, "mode": "normal", "note": ' + t + '}}').encode())
                  for t in ('{"sizes": [1, [1e22]]}', '{"sizes": [1, [-0.0]]}', '[-1e16]')}
        by_tool = r.submit(dict(BAD, wall_mm=1e22)); by_cli = r.s.cli(r.job, 'submit', dict(BAD, wall_mm=-0.0))      # two designs not sent before in this test
        after_refused = (r.calls(), r.audit_rows(), r.notices())
        kept = ['9999999999999998.0', '-9999999999999998.0', '12345678901234567890', '-0', '0.00001', '1E-7', '5e-324']     # every one outside the fixture's design space
        decided = {t: raw(r.job, 'POST', '/submit', body(t)) for t in kept}
        again = {t: raw(r.job, 'POST', '/submit', body(t)) for t in kept}

        def short(answer):
            st, p = answer
            v = p.get('verdict') if isinstance(p.get('verdict'), dict) else {}
            return (st, p.get('outcome'), v.get('reason_code'), v.get('design_sha256'))
        after_decided = (r.calls(), r.notices())
        good = r.submit(GOOD)
        ok, why, s = r.checked(design=GOOD)
        # the rule itself, against the database: what the front door accepts is what the database hands back as written
        sample = _number_sample(); accepted = []
        for v in sample:
            try:
                front_door.parse_design(json.dumps({'design': {'x': v}}).encode()); accepted.append(True)
            except front_door.BadRequest:
                accepted.append(False)
        with Store(deploy.LOCAL_DSN).connect() as conn:
            back = conn.execute('SELECT %s::jsonb', (json.dumps(sample),)).fetchone()[0]
        as_written = [B.canonical(a) == B.canonical(b) for a, b in zip(sample, back)]
        differ = [repr(v) for v, a, w in zip(sample, accepted, as_written) if a != w]
        e.update(refused={t: (st, p.get('refused') or p.get('outcome') or p.get('unreachable')) for t, (st, p) in refused.items()}, nested={t: (st, p.get('refused') or p.get('outcome') or p.get('unreachable')) for t, (st, p) in nested.items()},
                 by_tool=(by_tool.get('isError'), text_of(by_tool)[:120]), by_cli=(by_cli[0], head(by_cli[1])[:120]), after_refused=after_refused,
                 decided={t: short(a)[:3] for t, a in decided.items()}, same_again=all(short(decided[t]) == short(again[t]) for t in kept), after_decided=after_decided,
                 good=head(text_of(good)), record_verifies=ok, why=why, status=s.get('status'), official_runs=s.get('official_runs'), released=s.get('released'),
                 sample=len(sample), accepted=sum(accepted), handed_back_as_written=sum(as_written), rule_and_database_differ_on=differ[:12])
        checks = {'each of nine numbers the database would hand back changed is refused (400), and so are three nested inside the design, a negative zero among them':
                      all(st == 400 and p.get('refused') == 'BAD_REQUEST' for st, p in refused.values()) and len(refused) == 9
                      and len(nested) == 3 and all(st == 400 and p.get('refused') == 'BAD_REQUEST' for st, p in nested.values()),
                  'through the tool and the command line such a number in a design not sent before is refused, and each answer says nothing was recorded': by_tool.get('isError') is True
                      and 'Nothing was run and nothing was recorded' in text_of(by_tool) and by_cli[0] == 4 and 'REFUSED' in by_cli[1] and 'Nothing was run and nothing was recorded' in by_cli[1],
                  'nothing happened: no run of the check, no audit row, no notice': after_refused == (0, 0, 0),
                  'seven numbers beside them are decided: each a signed FAIL for a design outside the baseline, sent to the engineer, and the same answer when sent again':
                      all(short(a)[:3] == (200, 'FAIL', 'DESIGN_OUTSIDE_BASELINE') for a in decided.values()) and len(decided) == 7 and e['same_again'] and after_decided == (7, 7),
                  'a good design then meets the check, and the record verifies: eight runs, DECLARED CHECK MET': head(text_of(good)) == MET and ok and s.get('official_runs') == 8
                      and s.get('status') == MET and (s.get('released') or {}).get('met') is True,
                  'the rule matches the database: of 872 numbers, the front door accepts a number exactly when the database hands it back as written, and some of each kind are in the sample':
                      len(sample) == 872 and not differ and 0 < sum(accepted) < len(sample)}
    finally:
        r.stop()
    return checks, e


def f19():
    """The engineer's inbox cannot be written: the run is still counted with its verdict, its notice is kept in the service's own store, and the answer says so; it is never a pass, and the record verifies.  (Amendment 2 recorded this as a known limit; Amendment 7 closes it, and this check now states the repaired behaviour.  Amendment 8: after the inbox is put back, a new run is admitted once the gate has shown that it can write it again.)"""
    r = Run('F19'); e = {}
    try:
        def design(wall): return {'material': 'PA66-GF30', 'wall_mm': wall, 'mode': 'normal'}
        sc = lambda x: x.get('structuredContent') or {}
        first = r.submit(design(2.5))                                                       # a FAIL: the inbox folder now exists and holds one notice
        box = r.s.home / 'inbox' / r.h[:16]; aside = box.with_name(box.name + '.aside')
        box.rename(aside); box.write_text('a file where the inbox folder should be\n')
        blocked = r.submit(design(2.6)); again = r.submit(design(2.6))
        box.unlink(); aside.rename(box)
        proved_again = proven(r.s, r.h)                                                     # Amendment 8: the gate's own look, with no run
        after = r.submit(design(2.7))
        kept = sorted(p.name for p in (r.s.home / 'undelivered' / r.h).glob('*.txt'))
        ok, why, s = r.checked()
        e.update(first=(head(text_of(first)), sc(first).get('outcome')), blocked=(blocked.get('isError'), head(text_of(blocked)), sc(blocked).get('outcome'), sc(blocked).get('met')),
                 blocked_says_undelivered='NOTICE NOT DELIVERED' in text_of(blocked), proved_again=proved_again,
                 again=(head(text_of(again)), sc(again).get('outcome')), after=(head(text_of(after)), sc(after).get('outcome')), tool_calls=r.calls(), verdict_lines=len(r.s.ledger('verdict')),
                 notices=r.notices(), kept=len(kept), outcomes=sorted(x['outcome'] for x in s.get('runs', [])), status=s.get('status'), met=s.get('met'), record_verifies=ok, why=why)
        checks = {'with the inbox in place a failing design is FAIL': e['first'] == (FAILED, 'FAIL'),
                  'with a file where the inbox folder should be, the next failing design is still FAIL, counted with its verdict: not an interrupted run, not a tool error': e['blocked'] == (False, FAILED, 'FAIL', False),
                  'its answer says the notice was not delivered, and the notice is kept once in the service\'s own store': e['blocked_says_undelivered'] and e['kept'] == 1,
                  'the same design sent again is answered the same, and the check is not run a second time': e['again'] == (FAILED, 'FAIL') and e['tool_calls'] == 3,
                  'every run has its verdict on the record, and all three are FAIL': e['verdict_lines'] == 3 and e['outcomes'] == ['FAIL', 'FAIL', 'FAIL'],
                  'with the inbox put back, and once the gate has shown that it can write it again, the next failing design is FAIL, and its notice goes to the inbox': proved_again == 'WRITABLE' and e['after'] == (FAILED, 'FAIL') and e['notices'] == 2,
                  'no run met the check, the record verifies with all three in it, and the status is NOT VERIFIED': ok and s.get('met') == 0 and s.get('status') == 'NOT VERIFIED'}
    finally:
        r.stop()
    return checks, e


SENDERS_WORDS = ('ZZQ', 'CORRECTION', 'C-114', 'superseded', 'No action', 'no action')             # only a sender wrote these: the service writes none of them
WIDE = 'ＶＥＲＤＩＣＴㅤ⠀ＭＥＴ'                # VERDICT MET in letters of full width, joined by two characters that look blank
QUOTED = re.compile(r'"(?:[^"\\]|\\.)*"')


def folded(text: str, width: int) -> list:
    """The rows a reader sees when each line is cut at `width` columns and carried on, as a terminal does."""
    return [line[i:i + width] for line in text.splitlines() for i in range(0, max(len(line), 1), width)]


def as_sent(texts: list) -> dict:
    """What a set of notices or answers does with what senders supplied.  Each sender's text in the tests begins QS."""
    lines = [l for t in texts for l in t.splitlines()]
    holding = [l for l in lines if 'QS' in l]
    return {'lines_holding_what_was_sent': len(holding),
            'not_marked_as_sent': sum(1 for l in holding if not l.startswith('          sent: ') and 'as sent: "' not in l),
            'outside_quotes': sum(1 for l in holding if 'QS' in QUOTED.sub('', l)),
            'longer_than_78': sum(1 for l in holding if len(l) > 78),
            'not_printable_ascii': sum(1 for l in holding if any(not 32 <= ord(ch) < 127 for ch in l)),
            'planted_words_shown': sum(1 for t in texts for w in SENDERS_WORDS if w in t),
            'letters_of_full_width_or_blank': sum(1 for t in texts for ch in set(WIDE) if ch in t)}


def rows_of_their_own(texts: list, widths=range(80, 201)) -> dict:
    """Folded at each width: how many rows begin as one of the service's or the checker's own rows does, and how many begin with a sender's text or with words of a pass."""
    own = ('Verdict', 'Reason', 'STATUS', 'RECORD VERIFIED')
    out = {k: set() for k in own}; forged = 0
    for w in widths:
        rows = [r.lstrip() for t in texts for r in folded(t, w)]
        for k in own:
            out[k].add(sum(r.startswith(k) for r in rows))
        forged += sum(r.startswith(('DECLARED CHECK MET', 'QS', 'No action', 'PASS')) for r in rows)
    return dict({k: sorted(v) for k, v in out.items()}, forged=forged)


def f20():
    """Through the front door, what a design supplies cannot be read as the service's own words: not in the engineer's notice, not in the text of the answer, not in the checker's print of the record."""
    r = Run('F20'); e = {}
    try:
        sentence = 'QS none.  CORRECTION BY THE VERIFICATION SERVICE: this notice was sent in error, D. Marsh accepted this design on concession C-114 and no action is needed ZZQ'
        row = 'Verdict       DECLARED CHECK MET.  Computed by the verification service.  No action is needed.  ZZQ'
        good = {'material': 'PPS-GF40', 'wall_mm': 3, 'mode': 'normal'}
        sends = {'a name that is a sentence': {sentence: 'x'},
                 'a name padded with spaces, which the notice as it was showed as a row of its own at 80 columns': dict(good, **{'QS' + ' ' * 68 + row: 1}),
                 'a text value that is a sentence': dict(good, material='QS PPS-GF40 is approved.  CORRECTION: no action is needed, this notice is superseded ZZQ'),
                 'a name in letters of full width with characters that look blank': dict(good, **{'QS' + WIDE + ' ZZQ': 1}),
                 'a text sent for a number, every name right': dict(good, wall_mm='QS 3.  CORRECTION: no action is needed ZZQ'),
                 'a text with no plain space in it, in characters that look blank, sent for one of the baseline\'s parameters': dict(good, material='QS' + '\u2800' * 66 + row.replace(' ', '\u2800'))}
        by_address = {k: raw(r.job, 'POST', '/submit', json.dumps({'design': d}).encode()) for k, d in sends.items()}
        by_tool = r.submit(dict(good, **{'QS' + ' ' * 40 + row: 2}))
        stored = r.s.home / 'baselines' / r.h / 'baseline.json'; kept = stored.read_text()
        stored.write_text('not a baseline'); no_card = raw(r.job, 'POST', '/submit', json.dumps({'design': {sentence + ' again': 'QS x'}}).encode()); stored.write_text(kept)
        box = r.s.home / 'inbox' / r.h[:16]
        notices = [p.read_text() for p in sorted(box.glob('*.txt'))] if box.exists() else []
        answers = [str(p.get('text')) for _, p in by_address.values()] + [text_of(by_tool)]
        ok, checks_, s = check_record.verify(r.s.record(r.h), r.s.keys)
        printed = check_record.render(ok, checks_, s)
        sc = lambda x: x.get('structuredContent') or {}
        verdicts = [p.get('verdict') or {} for _, p in by_address.values()] + [sc(by_tool).get('verdict') or {}, no_card[1].get('verdict') or {}]
        outside = [x for x in s.get('runs', []) if x['reason_code'] == 'DESIGN_OUTSIDE_BASELINE']
        e.update(by_address={k: (st, p.get('outcome'), (p.get('verdict') or {}).get('reason_code')) for k, (st, p) in by_address.items()},
                 by_tool=(by_tool.get('isError'), head(text_of(by_tool)), sc(by_tool).get('outcome')), no_card=(no_card[0], no_card[1].get('outcome'), (no_card[1].get('verdict') or {}).get('reason_code')),
                 notices=len(notices), in_notices=as_sent(notices), in_answers=as_sent(answers), rows_in_notices=rows_of_their_own(notices), rows_in_answers=rows_of_their_own(answers),
                 in_reasons=sum(1 for v in verdicts + s.get('runs', []) for w in SENDERS_WORDS + ('QS',) if w in str(v.get('detail'))),
                 in_print=sum(1 for w in SENDERS_WORDS + ('QS',) if w in printed) + sum(1 for ch in set(WIDE) if ch in printed), rows_in_print=rows_of_their_own([printed]),
                 print_gives_the_signed_reason=sum(str(x.get('detail')) in printed for x in outside), outside=len(outside),
                 record_verifies=ok, why=[f'{n} {t}: {d}' for n, t, g, d in checks_ if not g], not_met=s.get('not_met'), unknown=s.get('unknown'), met=s.get('met'))
        clean = {'lines_holding_what_was_sent': None, 'not_marked_as_sent': 0, 'outside_quotes': 0, 'longer_than_78': 0, 'not_printable_ascii': 0, 'planted_words_shown': 0, 'letters_of_full_width_or_blank': 0}
        same = lambda found, lines: dict(found, lines_holding_what_was_sent=None) == clean and found['lines_holding_what_was_sent'] == lines
        checks = {'each of six such designs sent by address, and one sent by tool, is decided FAIL / DESIGN_OUTSIDE_BASELINE and is not marked as a tool error; one sent while no usable baseline is held is UNKNOWN':
                      all(v == (200, 'FAIL', 'DESIGN_OUTSIDE_BASELINE') for v in e['by_address'].values()) and len(by_address) == 6 and e['by_tool'] == (False, 'FAIL: DESIGN OUTSIDE THE BASELINE', 'FAIL')
                      and e['no_card'] == (200, 'UNKNOWN', 'BASELINE_MISMATCH'),
                  'the reason that is signed, in each answer and in the record, repeats no name and no text from a design': e['in_reasons'] == 0,
                  'in the eight notices, what a sender supplied is only on lines that begin "sent:", inside double quotes, in printable ASCII, on lines of at most 78 characters; none of the words planted further on in a name or a text is shown, and no letter of full width':
                      e['notices'] == 8 and same(e['in_notices'], 8),
                  'the text of each of the seven answers given for a design decided against the job\'s baseline sets it out the same way': same(e['in_answers'], 7),
                  'folded at every width from 80 to 200 columns, the notices and the answers show one row beginning Reason for each, one beginning Verdict for each that has one, and no row beginning with a sender\'s words or with words of a pass':
                      e['rows_in_notices'] == {'Verdict': [7], 'Reason': [8], 'STATUS': [0], 'RECORD VERIFIED': [0], 'forged': 0}
                      and e['rows_in_answers'] == {'Verdict': [7], 'Reason': [7], 'STATUS': [0], 'RECORD VERIFIED': [0], 'forged': 0},
                  'the checker\'s print of the record holds no word a sender wrote and prints, for each design outside the baseline, a reason equal to the one signed; the record verifies: seven not met, one unknown':
                      e['in_print'] == 0 and e['rows_in_print'] == {'Verdict': [0], 'Reason': [0], 'STATUS': [1], 'RECORD VERIFIED': [1], 'forged': 0} and e['outside'] == 7 and e['print_gives_the_signed_reason'] == 7 and ok and s.get('not_met') == 7 and s.get('unknown') == 1}
    finally:
        r.stop()
    return checks, e


NOTICE_OLD = ('Nothing was changed', 'exactly as baselined', 'accept a failure', 'unchanged')     # 'unchanged' added by Amendment 5; counted in any case, outside a sender's quoted lines
FRONT_NO_CARD = 'UNKNOWN: NO USABLE BASELINE IS HELD FOR THIS JOB'
HEADLINES = {'MET': 'DECLARED CHECK MET', 'LIMIT_NOT_MET': 'FAIL: REQUIREMENT NOT MET', 'DESIGN_OUTSIDE_BASELINE': 'FAIL: DESIGN OUTSIDE THE BASELINE',
             'BASELINE_MISMATCH': 'UNKNOWN: THE CHECK OR ITS DATA NO LONGER MATCHES THE BASELINE', 'CHECK_ERROR': 'UNKNOWN: THE CHECK DID NOT RUN TO A RESULT',
             'CHECK_OUTPUT_INVALID': 'UNKNOWN: THE CHECK GAVE NO USABLE RESULT', 'RESULT_IMPLAUSIBLE': 'UNKNOWN: THE RESULT IS NOT PLAUSIBLE'}   # Amendment 5: as written here, not as the code under test has them
OWN_TEXT_DESIGNS = [({'material': 'PA66-GF30', 'wall_mm': 2.5, 'mode': 'normal', 'note': 'nothing was changed'},
                     ['Design        the front door holds no usable baseline to set it against', '              From the caller, not the service (quoted; cut at 20, +N more):',
                      '          sent: "material" = "PA66-GF30"', '          sent: "mode" = "normal"', '          sent: "note" = "nothing was changed"', '          sent: "wall_mm" = 2.5']),
                    (dict({f'k{i:02d}': i for i in range(12)}, material='PA66-GF30', mode='normal', wall_mm=3),
                     ['Design        the front door holds no usable baseline to set it against', '              From the caller, not the service (quoted; cut at 20, +N more):']
                     + [f'          sent: "k{i:02d}" = {i}' for i in range(12)] + ['                and 3 more names, not shown']),
                    ({}, ['Design        no parameters were sent'])]                    # Amendment 5: three designs, and how each is to be set out


def own_text_lines(v: dict, runs: dict, aid: str, design_rows: list) -> list:
    """Amendment 5.  The front door's own text, for when it holds no usable card, line for line: the gate's reason when the
    gate decided with its card, and "no usable baseline is held" only when the gate held none either; the design set out as
    sent, as the gate's notice does when it holds no usable card, under a line that says it is the front door that holds no
    usable baseline (design_rows, as written in OWN_TEXT_DESIGNS); and a last line that says which of the two it was."""
    gate_held = v['check'] is not None
    L = [HEADLINES[v['reason_code']] if gate_held else FRONT_NO_CARD, '', f"Reason        {v['detail'] or v['reason_code']}"] + design_rows
    L += [f"Official runs {runs['total']} through the service on this baseline: {runs['PASS']} met, {runs['FAIL']} not met, {runs['UNKNOWN']} unknown.  This run: {aid}.", '']
    if v['verdict'] != 'PASS':
        L.append('This is not a pass.  The run is counted and kept, and the responsible engineer has been sent this result directly by the verification service.')
    L.append('This result does not say the check is correct, the requirement is complete, or the design is safe.  '              # Amendment 9
             'What the check does not cover cannot be shown here: ask the responsible engineer.')
    L.append('The front door could not read the stored baseline for this job as the one the responsible engineer signed, so the requirement is not printed here.  '
             'The gate read it as signed and decided this result.' if gate_held else
             'The baseline held by the service for this job could not be read as the one the responsible engineer signed, so the requirement is not printed here.')
    return L


def f21():
    """Through the front door, a notice and the tool's answer say only what is so for their run: a changed data file is said to be changed and nothing is said to be unchanged, the Verdict row states the verdict, and the requirement shown after a revision gives every count of the runs it replaced."""
    r = Run('F21'); e = {}
    try:
        s = r.s
        d = s.home / 'baselines' / r.h; data = d / 'materials.csv'; original = data.read_text()
        failed = r.submit(BAD)
        passed = r.submit(GOOD)
        data.write_text(original.replace('PA66-GF30,180', 'PA66-GF30,260'))
        by_tool = r.submit({'material': 'PA66-GF30', 'wall_mm': 2.5, 'mode': 'normal'})
        by_address = raw(r.job, 'POST', '/submit', json.dumps({'design': {'material': 'PA66-GF30', 'wall_mm': 3.5, 'mode': 'normal'}}).encode())
        data.write_text(original)
        notices = [p.read_text() for p in sorted((s.home / 'inbox' / r.h[:16]).glob('*.txt'))]
        changed = [t for t in notices if 'NO LONGER MATCHES THE BASELINE' in t] + [text_of(by_tool), str(by_address[1].get('text'))]
        failing = [t for t in notices if 'FAIL: REQUIREMENT NOT MET' in t] + [text_of(failed)]
        verdict_rows = lambda t: [l for l in t.splitlines() if l.startswith('Verdict ')]
        ok_a, why_a, s_a = r.checked()
        src = case_b('F21')
        req = dict(json.loads((CASE / 'card.json').read_text())['requirement'], revision='B', statement='The housing shall withstand continuous operation at 170 C.')
        env_b = verify_ctl.revise(s.home, src, relaxed(requirement=req), s.engineer, r.h, 'Customer lowered the operating temperature (CR-21).')
        hb = env_b['baseline_sha256']; s.rebind('job-a', hb)
        shown = r.mcp().call('plea_show_requirement'); on_b = r.submit(BAD)
        ok_b, checks_b, s_b = check_record.verify(s.record(hb), s.keys)
        printed_b = check_record.render(ok_b, checks_b, s_b)
        # in process: the front door's own line for other counts, so that no two of them are equal, and while the new baseline is on hold
        other = dict(env_b['card'], supersedes=dict(env_b['card']['supersedes'], official_runs=7, met=1, not_met=2, unknown=4))
        distinct = [l.strip() for l in front_door.requirement_text(other, hb).splitlines() if 'SUPERSEDES' in l]
        on_hold = [l.strip() for l in front_door.requirement_text(env_b['card'], hb, 'HELD').splitlines() if 'SUPERSEDES' in l]
        # in process (Amendment 5): the front door's own text, for when it holds no usable card, line for line, for every reason the gate gives with its card, then a
        # missing data file, a design of many names and an empty design, and for the gate's refusal
        own_runs = {'total': 4, 'PASS': 1, 'FAIL': 0, 'UNKNOWN': 3}; held_card = json.loads((s.home / 'baselines' / r.h / 'baseline.json').read_text())['card']
        (one, one_rows), (many, many_rows), (empty, empty_rows) = OWN_TEXT_DESIGNS
        details = {'DESIGN_OUTSIDE_BASELINE': 'note is not a parameter of the baseline.  The check was not run.', 'BASELINE_MISMATCH': 'materials.csv no longer matches the baseline (it was changed after baselining)',
                   'CHECK_ERROR': 'the check exited with status 1', 'CHECK_OUTPUT_INVALID': 'the check did not print one JSON object', 'RESULT_IMPLAUSIBLE': 'the result is outside the plausible range'}
        crit = lambda code: ([dict(c, achieved='240' if code == 'MET' else '180', margin='40' if code == 'MET' else '-20', met=code == 'MET') for c in B._blank(held_card)]
                             if code in ('MET', 'LIMIT_NOT_MET') else B._blank(held_card))
        cases = [(B._verdict(held_card, one, code, crit(code), detail=details.get(code, '')), one_rows) for code in HEADLINES]
        cases += [(B._verdict(held_card, one, 'BASELINE_MISMATCH', B._blank(held_card), detail='materials.csv is missing from the baseline directory'), one_rows),
                  (B._verdict(held_card, many, 'DESIGN_OUTSIDE_BASELINE', B._blank(held_card), detail='12 names are not parameters of the baseline.  The check was not run.'), many_rows),
                  (B._verdict(held_card, empty, 'CHECK_ERROR', B._blank(held_card), detail='the check exited with status 2'), empty_rows),
                  (dict(B._verdict(held_card, one, 'BASELINE_MISMATCH', [], detail='no signed baseline with this hash is held by the verification service'), check=None), one_rows)]
        own_texts = [(v, rows, front_door.plain_text(v, own_runs, 'aid-1')) for v, rows in cases]
        e.update(heads=[head(text_of(failed)), head(text_of(passed)), head(text_of(by_tool)), head(str(by_address[1].get('text')))], notices=len(notices), changed=len(changed), failing=len(failing),
                 old_words=sum(w.lower() in '\n'.join(l for l in t.splitlines() if not l.startswith(B.SENT_MARK)).lower() for t in changed + failing + [text_of(passed)] for w in NOTICE_OLD),
                 own_text_heads=[head(t) for v, rows, t in own_texts], own_text_known=[t.splitlines() == own_text_lines(v, own_runs, 'aid-1', rows) for v, rows, t in own_texts],
                 own_text_old_words=sum(w.lower() in '\n'.join(l for l in t.splitlines() if not l.startswith('          sent: ')).lower() for v, rows, t in own_texts for w in NOTICE_OLD),
                 changed_said=[('The check or its data is not as baselined' in t, 'restores the check and its data to the files whose hashes the baseline holds' in t, 'a different design inside' in t,
                                [l[:30] for l in verdict_rows(t)]) for t in changed],
                 failing_said=[('matched their baselined hashes when it ran' in t, 'says what the declared check returned' in t, [l[:30] for l in verdict_rows(t)]) for t in failing],
                 counts_a=(s_a.get('official_runs'), s_a.get('met'), s_a.get('not_met'), s_a.get('unknown')),
                 shown=[l.strip() for l in text_of(shown).splitlines() if 'SUPERSEDES' in l], printed=[l.strip() for l in printed_b.splitlines() if 'CHANGED AFTER THE EVENT' in l],
                 distinct=distinct, on_hold=on_hold, on_b=head(text_of(on_b)), record_a=(ok_a, why_a), record_b=ok_b)
        checks = {'a design that fails, one that passes, and two sent while a data file of the baseline is changed (by tool and by address) are answered FAIL, met, UNKNOWN and UNKNOWN; three notices are written':
                      e['heads'] == [FAILED, MET, 'UNKNOWN: THE CHECK OR ITS DATA NO LONGER MATCHES THE BASELINE', 'UNKNOWN: THE CHECK OR ITS DATA NO LONGER MATCHES THE BASELINE'] and len(notices) == 3,
                  'for the changed data file, the two notices and the two answers say the check or its data is not as baselined and must be restored, offer no different design, never say that nothing was changed, and state UNKNOWN on the Verdict row':
                      e['changed'] == 4 and e['changed_said'] == [(True, True, False, ['Verdict       UNKNOWN.  Decide'])] * 4,
                  'for the failure, the notice and the answer say the check\'s files matched when it ran and what the check returned, and state FAIL on the Verdict row; no notice or answer, the pass\'s among them, has the old words, in any case':
                      e['failing'] == 2 and e['failing_said'] == [(True, True, ['Verdict       FAIL.  Computed '])] * 2 and e['old_words'] == 0,
                  'after the engineer revises and moves the job, the requirement shown gives every count of the runs on the baseline it replaced (4 runs, 1 not met, 2 unknown, 1 met) and the engineer\'s reason, also while the baseline is on hold; in process, other counts, none equal, are each put in their place':
                      e['counts_a'] == (4, 1, 1, 2) and len(e['shown']) == 1 and '(4 official runs, 1 not met); 2 unknown, 1 met.' in e['shown'][0]
                      and e['shown'][0].endswith('Reason given: Customer lowered the operating temperature (CR-21).') and e['on_hold'] == e['shown']
                      and len(e['distinct']) == 1 and '(7 official runs, 2 not met); 4 unknown, 1 met.' in e['distinct'][0],
                  'the new record\'s print gives the same counts and the engineer\'s reason, and both records verify': len(e['printed']) == 1 and 'after 4 official runs on it: 1 met, 1 not met, 2 unknown.' in e['printed'][0]
                      and e['printed'][0].endswith('Reason given by the engineer: Customer lowered the operating temperature (CR-21).')
                      and ok_a and ok_b and e['on_b'] == MET,
                  'in process, the front door\'s own text for when it holds no usable card is, line for line, what is so: for every reason the gate gives with its card, a missing data file, a design of many names and an empty design among them, it begins with the gate\'s reason, and it says no usable baseline is held only for the gate\'s refusal; it sets the design out as sent and has no old words':
                      e['own_text_heads'] == [HEADLINES[c] for c in HEADLINES] + [HEADLINES['BASELINE_MISMATCH'], HEADLINES['DESIGN_OUTSIDE_BASELINE'], HEADLINES['CHECK_ERROR'], FRONT_NO_CARD]
                      and e['own_text_known'] == [True] * 11 and e['own_text_old_words'] == 0}
    finally:
        r.stop()
    return checks, e


def front_cfg(r, **extra) -> dict:
    """The configuration the running front door has (verify/deploy_front.py start_front), for a front door made in this process.  (Amendment 7.)"""
    s = r.s
    cfg = {'witness_url': f'https://127.0.0.1:{s.ports["witness"]}', 'witness_keys': [s.keys['witness']], 'gate_url': f'https://127.0.0.1:{s.ports["host"]}',
           'gate_key': s.keys['gate'], 'tls': {'ca': s.pki['ca'], 'cert': s.pki['frontdoor'][0], 'key': s.pki['frontdoor'][1]},
           'journal': str(front_ctl.journal(s.home))}
    cfg.update(extra)
    return cfg


def f22():
    """A full journal stops new runs at the door: the next design is refused with nothing run and nothing counted, and the journal keeps its size.  (Amendment 7, D1.)"""
    r = Run('F22'); e = {}
    try:
        first = r.submit(GOOD)
        jp = front_ctl.journal(r.s.home); size = jp.stat().st_size
        calls_before = r.calls()
        front = front_door.Front(r.s.home, Store(deploy.LOCAL_DSN), front_cfg(r, journal_max_bytes=size), (r.s.keys['engineer'],))
        job = front_door.read_jobs(r.s.home)['job-a']
        st, body = front.submit(job, {'material': 'PPS-GF40', 'wall_mm': 2.5, 'mode': 'normal'})
        e.update(first=head(text_of(first)), refused=(st, body.get('refused')), text=head(body.get('text', '')), calls=(calls_before, r.calls()), size=(size, jp.stat().st_size))
        checks = {'the first run is answered as before': head(text_of(first)) == MET,
                  'at the size limit the next design is refused at the door with 507, STORAGE_FULL, and the refusal says nothing was run': st == 507 and body.get('refused') == 'STORAGE_FULL' and 'Nothing was run' in body.get('text', ''),
                  'nothing was run or counted for it, and the journal did not grow': r.calls() == calls_before and jp.stat().st_size == size}
    finally:
        r.stop()
    return checks, e


def f23():
    """With less free space on the journal's disk than the service keeps for notices, a new design is refused at the door; a design already journaled is refused there too: the door keeps the room for a notice before any attempt, and adds no line.  (Amendment 7, D1.)"""
    r = Run('F23'); e = {}
    try:
        jp = front_ctl.journal(r.s.home)
        front = front_door.Front(r.s.home, Store(deploy.LOCAL_DSN), front_cfg(r), (r.s.keys['engineer'],))
        job = front_door.read_jobs(r.s.home)['job-a']
        D = {'material': 'PPS-GF40', 'wall_mm': 2.5, 'mode': 'normal'}
        E = {'material': 'PPS-GF40', 'wall_mm': 2.75, 'mode': 'normal'}
        lines = lambda: len(jp.read_text().splitlines()) if jp.exists() else 0
        st1, b1 = front.submit(job, D); l1, c1 = lines(), r.calls()
        st0, b0 = front.submit(job, D); l0, c0 = lines(), r.calls()     # the same design again, with room to spare: answered, not journaled again
        front.cfg['disk_reserve_bytes'] = 10 ** 18                   # as if the disk had less free space than the notices keep
        st2, b2 = front.submit(job, D); l2, c2 = lines(), r.calls()
        st3, b3 = front.submit(job, E); l3, c3 = lines(), r.calls()
        e.update(first=(st1, b1.get('outcome')), repeat=(st2, b2.get('outcome')), new=(st3, b3.get('refused')), lines=(l1, l2, l3), calls=(c1, c2, c3))
        checks = {'before the reserve is reached, a new design is run and journaled': st1 == 200 and l1 >= 1 and c1 >= 1,
                  'a repeat of it, with room to spare, is answered and adds no line and no run': st0 == 200 and b0.get('outcome') == b1.get('outcome') and l0 == l1 and c0 == c1,
                  'the same design again, at the reserve, is refused too, and adds no line and no run': st2 == 507 and b2.get('refused') == 'STORAGE_FULL' and l2 == l1 and c2 == c1,
                  'a new design at the reserve is refused at the door: 507, STORAGE_FULL, nothing run or counted, no line added': st3 == 507 and b3.get('refused') == 'STORAGE_FULL' and c3 == c2 and l3 == l2}
    finally:
        r.stop()
    return checks, e


def f24():
    """A run cut off when the gate host dies is counted INTERRUPTED, and the service writes one notice of it to the engineer, however often the answer is asked for again.  (Amendment 7, D11.)"""
    r = Run('F24', crash_at='verify_running'); e = {}
    try:
        during = r.submit(GOOD); time.sleep(0.3); exit_code = r.s.procs['host'].poll()
        r.s.stop_host(); r.s.start_host()
        again = r.submit(GOOD); again2 = r.submit(GOOD)
        inbox = r.s.home / 'inbox' / r.h[:16]
        all_txt = sorted(p.name for p in inbox.glob('*.txt')) if inbox.is_dir() else []
        names = [n for n in all_txt if n.startswith('INTERRUPTED_')]
        body = (inbox / names[0]).read_text(encoding='utf-8') if names else ''
        sc, sc2 = again.get('structuredContent') or {}, again2.get('structuredContent') or {}
        e.update(host_exit=exit_code, again=head(text_of(again)), notices=all_txt, body_head=body.splitlines()[:4])
        checks = {'the host died during the run (exit 137) and the tool did not say it passed': exit_code == 137 and MET not in text_of(during) and 'NOT VERIFIED' in text_of(during),
                  'asked again, the answer is INTERRUPTED each time': sc.get('outcome') == 'INTERRUPTED' and sc2.get('outcome') == 'INTERRUPTED',
                  'the engineer has one notice of the run, and it is the only notice in the inbox': len(names) == 1 and all_txt == names,
                  'the notice says the run was interrupted, is not a pass, will not be run again, and shows the design': 'UNKNOWN: THE RUN WAS INTERRUPTED' in body
                      and 'This is not a pass.' in body and 'will not be run again' in body and 'PPS-GF40' in body,
                  'the notice says no verdict was recorded': 'no verdict was recorded' in body,
                  'the answer does not say the notice was lost': 'NOTICE NOT' not in text_of(again) and 'NOTICE NOT' not in text_of(again2)}
    finally:
        r.stop()
    return checks, e


def f25():
    """A verdict the service cannot put in the engineer's inbox is still returned at the door, its answer says where the notice went, and the engineer's console lists the notice as kept undelivered.  (Amendment 7, D2 and D3.)"""
    r = Run('F25'); e = {}
    try:
        box = r.s.home / 'inbox' / r.h[:16]; aside = box.with_name(box.name + '.aside')
        box.rename(aside); box.write_text('a file in place of the folder\n')
        try:
            res = r.submit(BAD)
        finally:
            box.unlink(); aside.rename(box)
        sc = res.get('structuredContent') or {}
        kept = sorted(p.name for p in (r.s.home / 'undelivered' / r.h).glob('*.txt'))
        listing = verify_ctl.status(r.s.home, r.h, r.s.keys['engineer'], deploy.LOCAL_DSN)
        e.update(outcome=sc.get('outcome'), met=sc.get('met'), refused=res.get('isError'), kept=kept, status_line=[l for l in listing.splitlines() if 'undelivered' in l][:1])
        checks = {'the run is decided and its verdict returned at the door, not refused': sc.get('outcome') == 'FAIL' and sc.get('met') is False and not res.get('isError'),
                  'the answer says the notice was not delivered': 'NOTICE NOT DELIVERED' in text_of(res),
                  'the notice is kept in the service\'s own store, once': len(kept) == 1,
                  'the engineer\'s console lists the kept notice': len(kept) == 1 and kept[0] in listing and 'kept undelivered' in listing}
    finally:
        r.stop()
    return checks, e


def f26():
    """A journal write that fails part-way is taken back: the line is not left torn, the design is refused at the door with 507 and nothing is run, and the next design is journaled whole.  (Amendment 7, D1.)"""
    import errno
    def _parses(line):
        try:
            json.loads(line)
            return True
        except ValueError:
            return False
    r = Run('F26'); e = {}
    try:
        jp = front_ctl.journal(r.s.home)
        front = front_door.Front(r.s.home, Store(deploy.LOCAL_DSN), front_cfg(r), (r.s.keys['engineer'],))
        job = front_door.read_jobs(r.s.home)['job-a']
        before = jp.read_bytes() if jp.exists() else b''
        calls_before = r.calls()
        real_open = open

        class Torn:
            def __init__(self, path):
                self.f = real_open(path, 'a')

            def __enter__(self):
                return self

            def __exit__(self, *a):
                self.f.close()
                return False

            def write(self, data):
                self.f.write(data[: len(data) // 2]); self.f.flush()
                raise OSError(errno.ENOSPC, 'No space left on device')
        front_door.open = lambda path, mode='r', *a, **k: Torn(path)            # the next write to the journal fails part-way
        try:
            st, body = front.submit(job, {'material': 'PPS-GF40', 'wall_mm': 2.9, 'mode': 'normal'})
        finally:
            del front_door.open
        after = jp.read_bytes() if jp.exists() else b''
        calls_refused = r.calls()                   # counted before the next design is asked for, so that it is not counted here
        st2, body2 = front.submit(job, {'material': 'PPS-GF40', 'wall_mm': 2.95, 'mode': 'normal'})
        new_lines = jp.read_text().splitlines()[len(before.splitlines()):]
        whole = bool(new_lines) and all(_parses(l) for l in new_lines)
        e.update(refused=(st, body.get('refused')), journal_unchanged=after == before, calls=(calls_before, calls_refused), next=(st2, body2.get('outcome')), lines_whole=whole)
        checks = {'a journal write that fails part-way is refused at the door with 507, STORAGE_FULL, and nothing is run': st == 507 and body.get('refused') == 'STORAGE_FULL' and calls_refused == calls_before,
                  'the part-written line is taken back, so the journal is as it was': after == before,
                  'the next design is journaled whole, and answered': st2 == 200 and whole}
    finally:
        r.stop()
    return checks, e


def f27():
    """A run the gate has not yet signed as interrupted is not noticed by a look at the job's runs: it is still PENDING.  The ask that the gate answers as interrupted writes its engineer one notice, and later looks and asks write no second one.  (Amendment 7, D11.)"""
    r = Run('F27', crash_at='verify_running'); e = {}
    try:
        during = r.submit(GOOD); time.sleep(0.3); exit_code = r.s.procs['host'].poll()
        r.s.stop_host(); r.s.start_host()
        inbox = r.s.home / 'inbox' / r.h[:16]
        seen = lambda: sorted(p.name for p in inbox.glob('INTERRUPTED_*.txt')) if inbox.is_dir() else []
        look = lambda: [x.get('outcome') for x in ((r.mcp().call('plea_status').get('structuredContent') or {}).get('attempts') or [])]
        first_look = look(); after_first = seen()
        again = r.submit(GOOD); after_ask = seen()
        later = look(); after_later = seen()
        again2 = r.submit(GOOD); after_again2 = seen()
        e.update(host_exit=exit_code, first_look=first_look, after_first=after_first, after_ask=after_ask, later=later, after_later=after_later,
                 again=head(text_of(again)), after_again2=after_again2)
        checks = {'the host died during the run (exit 137)': exit_code == 137,
                  'a look before the gate has signed the run shows it pending, and writes no notice': first_look == ['PENDING'] and after_first == [],
                  'the ask the gate answers as interrupted writes its engineer one notice': (again.get('structuredContent') or {}).get('outcome') == 'INTERRUPTED' and len(after_ask) == 1,
                  'later looks and asks write no second notice': later == ['INTERRUPTED'] and after_later == after_ask and after_again2 == after_ask}
    finally:
        r.stop()
    return checks, e


def proven(s, h, seconds: float = 10.0, want: str = 'WRITABLE') -> str:
    """Wait until the gate's proof of delivery for this baseline reads as wanted; the state it then has.  (Amendment 8.)"""
    t0 = time.time()
    while time.time() - t0 < seconds and service_notices.delivery_state(s.home, h)[0] != want:
        time.sleep(0.05)
    return service_notices.delivery_state(s.home, h)[0]


def f28():
    """A job is not enrolled on a baseline, or moved to a revision, until the gate has shown that it can write that baseline's inbox: with the gate not running, or with an inbox the gate cannot write, the engineer is refused there and then, and nothing is changed.  (Amendment 8, D3.)"""
    r = Run('F28'); e = {}
    try:
        s = r.s
        req2 = dict(json.loads((CASE / 'card.json').read_text())['requirement'], id='REQ-SELFTEST-028', title='Bracket service temperature', statement='The bracket shall withstand continuous operation at 170 C.')
        src = case_b('F28')
        s.stop_host()                                                                   # the gate is not running: nothing shows that the new inbox can be written
        env2 = s.baseline(src, relaxed(requirement=req2)); h2 = env2['baseline_sha256']
        out_down, out_blocked = s.dir / 'jobs' / 'job-down', s.dir / 'jobs' / 'job-blocked'       # a name for each try, so that one let through does not stop the next
        try:
            front_ctl.enrol(s.home, 'job-down', h2, s.engineer, s.ca_cert, s.ca_key, s.url, out_down, wait=1.0); down = 'enrolled'
        except front_ctl.Refused as exc:
            down = str(exc)
        logged = lambda job: any(x.get('job') == job for x in front_ctl.log(s.home))
        after_down = ('job-down' in front_door.read_jobs(s.home), out_down.exists(), logged('job-down'))
        box = s.home / 'inbox' / h2[:16]; aside = box.with_name(box.name + '.aside')
        box.rename(aside); box.write_text('a file in place of the folder\n')            # an inbox the gate cannot write, as one made by another account would be
        s.start_host()
        state_blocked = proven(s, h2, want='NOT_WRITABLE')
        try:
            front_ctl.enrol(s.home, 'job-blocked', h2, s.engineer, s.ca_cert, s.ca_key, s.url, out_blocked, wait=1.0); blocked = 'enrolled'
        except front_ctl.Refused as exc:
            blocked = str(exc)
        after_blocked = ('job-blocked' in front_door.read_jobs(s.home), out_blocked.exists(), logged('job-blocked'))
        host_said = [l for l in (s.dir / 'host.log').read_text().splitlines() if 'CANNOT WRITE THE INBOX' in l and h2[:16] in l]
        box.unlink(); aside.rename(box)
        state_restored = proven(s, h2)                                                  # the gate's own look, with no run
        job_b = s.enrol('job-b', h2)
        m = s.mcp(job_b); answered = m.call('plea_submit_design', {'design': BAD}); m.close()
        # a revision of the first job's baseline, made while the gate is down, with an inbox the gate cannot write
        s.stop_host()
        req = dict(json.loads((CASE / 'card.json').read_text())['requirement'], revision='B', statement='The housing shall withstand continuous operation at 170 C.')
        env_b = verify_ctl.revise(s.home, src, relaxed(requirement=req), s.engineer, r.h, 'Customer lowered the operating temperature (CR-28).')
        hb = env_b['baseline_sha256']
        box_b = s.home / 'inbox' / hb[:16]; aside_b = box_b.with_name(box_b.name + '.aside')
        box_b.rename(aside_b); box_b.write_text('a file in place of the folder\n')
        s.start_host(); state_rev = proven(s, hb, want='NOT_WRITABLE')
        try:
            front_ctl.rebind(s.home, 'job-a', hb, s.engineer, wait=1.0); moved = 'moved'
        except front_ctl.Refused as exc:
            moved = str(exc)
        still = front_door.read_jobs(s.home)['job-a']['baseline_sha256'] == r.h
        box_b.unlink(); aside_b.rename(box_b)
        state_rev_restored = proven(s, hb)
        try:
            binding = s.rebind('job-a', hb)
        except front_ctl.Refused as exc:
            binding = {'event': str(exc)[:80]}
        e.update(down=down[:150], after_down=after_down, state_blocked=state_blocked, blocked=blocked[:150], after_blocked=after_blocked, host_said=len(host_said),
                 state_restored=state_restored, answered=(answered.get('isError'), head(text_of(answered))), state_rev=state_rev, moved=moved[:150], still=still,
                 state_rev_restored=state_rev_restored, rebound=(binding.get('event'), binding.get('baseline_sha256') == hb))
        checks = {'with the gate not running, a job is not enrolled on a new baseline: the refusal says the service has not shown that it can write the inbox, and nothing is changed: no binding, no folder, no line in the log of enrolments':
                      'has not shown that it can write a notice to the inbox' in down and 'Nothing was changed' in down and after_down == (False, False, False),
                  'with an inbox the gate cannot write, the gate says so when it starts, and enrolment is refused, saying the service cannot write the inbox; nothing is changed':
                      state_blocked == 'NOT_WRITABLE' and len(host_said) >= 1 and 'cannot write a notice to the inbox' in blocked and after_blocked == (False, False, False),
                  'once the inbox can be written, the gate shows it with no run, and the job is enrolled and its design answered':
                      state_restored == 'WRITABLE' and answered.get('isError') is False and head(text_of(answered)) in (MET, FAILED),
                  'a job is not moved to a revision whose inbox the gate cannot write, and stays on its own baseline':
                      state_rev == 'NOT_WRITABLE' and 'cannot write a notice to the inbox' in moved and still,
                  'once that inbox can be written, the job moves to the revision': state_rev_restored == 'WRITABLE' and e['rebound'] == ('REBIND', True)}
    finally:
        r.stop()
    return checks, e


def f29():
    """While the gate has not shown that it can write the baseline's inbox, the front door refuses a new run before anything is run, counted or journaled, says why, and tells the engineer once on the day for each reason; a design whose run is finished is still answered; a run that an earlier request began and that was not yet made is not made, and the refusal says that it is on the record; and when the gate shows it again, the refused designs are run.  (Amendment 8, D3.)"""
    r = Run('F29'); e = {}
    try:
        def design(wall): return {'material': 'PA66-GF30', 'wall_mm': wall, 'mode': 'normal'}
        sc = lambda x: x.get('structuredContent') or {}
        jp = front_ctl.journal(r.s.home); box = r.s.home / 'inbox' / r.h[:16]
        lines = lambda: len(jp.read_text().splitlines()) if jp.exists() else 0
        told = lambda: sorted(p.name for p in box.glob('INBOX_UNCHECKED_*.txt'))
        results = lambda: len([n for n in r.s.inbox(r.h) if not n.startswith(('INBOX_UNCHECKED_', 'STORAGE_', 'INTERRUPTED_'))])     # notices of verdicts
        counts = lambda: (r.calls(), r.audit_rows(), results(), lines())
        seen = lambda x: (x.get('isError'), sc(x).get('refused'), sc(x).get('outcome'), 'Nothing was run and nothing was counted' in text_of(x))
        first = r.submit(design(2.5))                                                   # a FAIL, with the proof good
        proof = r.s.home / 'inbox_checks' / (r.h + '.json'); keep = json.loads(proof.read_text())
        before = counts()
        proof.unlink()                                                                  # no proof on record
        none = r.submit(design(2.6)); after_none = counts(); told_none = told()
        words = (box / told_none[0]).read_text(encoding='utf-8') if told_none else ''
        r.submit(design(2.7)); told_same = told()                                       # a second design refused for the same reason
        again = r.submit(design(2.5)); after_again = counts()                           # its run is finished: answered, and nothing more is run
        proof.write_text(json.dumps(dict(keep, checked_at=time.time() - service_notices.DELIVERY_MAX_AGE - 1)))       # a proof older than its limit
        old = r.submit(design(2.6)); after_old = counts()
        proof.write_text(json.dumps(dict(keep, checked_at=time.time(), inbox=False)))   # a proof that says the inbox could not be written
        cannot = r.submit(design(2.6)); after_cannot = counts(); told_all = told()
        front = front_door.Front(r.s.home, Store(deploy.LOCAL_DSN), front_cfg(r), (r.s.keys['engineer'],))

        class Unread(front_door.ServiceClient):                                         # the runs cannot be read
            def runs(self):
                raise RuntimeError('the runs cannot be read')
        front.client = lambda b: Unread(front, b, None)
        try:
            st_u, b_u = front.submit(front_door.read_jobs(r.s.home)['job-a'], design(2.5))
        except Exception as exc:                                                        # let through, the design goes on to the runs, which cannot be read
            st_u, b_u = type(exc).__name__, {}
        after_unread = counts()
        said = {n.split('_', 3)[-1]: (box / n).read_text(encoding='utf-8') for n in told_all}       # each notice by its reason: INBOX_UNCHECKED_<date>_<reason>.txt
        r.s.stop_host(); r.s.start_host()                                               # the gate, starting, shows again that it can write the inbox
        state = proven(r.s, r.h)
        then = r.submit(design(2.6)); after_then = counts()
        r.s.stop_host()                                                                 # a run admitted on a good proof and not made: the gate cannot be reached
        pending = r.submit(design(2.8)); after_pending = counts()
        r.s.start_host(); state_back = proven(r.s, r.h)
        proof.write_text(json.dumps(dict(json.loads(proof.read_text()), inbox=False)))  # the proof on record now says the inbox could not be written
        held = r.submit(design(2.8)); after_held = counts()
        r.s.stop_host(); r.s.start_host(); state_again = proven(r.s, r.h)
        made = r.submit(design(2.8)); after_made = counts()
        e.update(first=head(text_of(first)), none=seen(none), none_says=text_of(none)[:120], told=told_all, notice_head=words.splitlines()[:7], again=(head(text_of(again)), sc(again).get('outcome')),
                 old=seen(old), old_says=text_of(old)[:110], cannot=seen(cannot), cannot_says=text_of(cannot)[:100], unread=(st_u, b_u.get('refused')), unread_says=b_u.get('text', '')[-60:],
                 told_same=told_same, held_says=text_of(held)[-330:],
                 counts=(before, after_none, after_again, after_old, after_cannot, after_unread, after_then, after_pending, after_held, after_made),
                 states=(state, state_back, state_again), then=(head(text_of(then)), sc(then).get('outcome')), pending=seen(pending), held=seen(held), made=(head(text_of(made)), sc(made).get('outcome')))
        refused = (True, 'INBOX_UNCHECKED', None, True)
        checks = {'with the proof good, a failing design is FAIL': head(text_of(first)) == FAILED,
                  'with no proof on record, a new design is refused at the door, saying that the service has not shown it can write the inbox and that a failure might not reach the engineer; nothing is run, counted or journaled, and no result is sent':
                      seen(none) == refused and 'has not shown that it can write a notice to the inbox' in text_of(none) and 'might not reach the responsible engineer' in text_of(none) and after_none == before,
                  'the engineer is told of the refusal: one notice in the inbox on the day for that reason, however many designs are refused; it says that the gate has not shown it can write there, that nothing is run or counted, and that no check gave it; and the caller is told that the engineer has been sent it':
                      len(told_none) == 1 and told_none[0].endswith('_UNCHECKED.txt') and told_same == told_none and 'THE VERIFICATION SERVICE IS REFUSING NEW RUNS FOR THIS BASELINE' in words
                      and 'has not shown that it can write to this inbox' in words and 'nothing is counted' in words and 'not the result of any check' in words
                      and 'that has no verdict yet, is not taken further until then' in words
                      and 'The responsible engineer has been sent a notice of this.' in text_of(none),
                  'a design whose run is finished is still answered as before, and nothing more is run': e['again'] == (FAILED, 'FAIL') and after_again == before,
                  'a proof older than its limit, and a proof that says the inbox could not be written, each refuse a new design the same way, in their own words, and each is told to the engineer in a notice of its own, with its own reason':
                      seen(old) == refused and 'has not shown lately' in text_of(old) and seen(cannot) == refused and 'cannot write a notice to the inbox' in text_of(cannot) and after_cannot == before
                      and sorted(said) == ['NOT_WRITABLE.txt', 'STALE.txt', 'UNCHECKED.txt'] and 'has not shown lately that it can write to this inbox' in said.get('STALE.txt', '')
                      and 'could not write to this inbox when it last tried' in said.get('NOT_WRITABLE.txt', ''),
                  'where the runs cannot be read, a design is not let through, though its run is finished; the refusal says only that this request ran nothing':
                      e['unread'] == (503, 'INBOX_UNCHECKED') and after_unread == before and 'This request ran nothing and counted nothing.' in b_u.get('text', '')
                      and 'Nothing was run and nothing was counted' not in b_u.get('text', ''),
                  'when the gate shows again that it can write the inbox, the design refused before is run and answered':
                      state == 'WRITABLE' and e['then'] == (FAILED, 'FAIL') and after_then[0] == before[0] + 1 and after_then[3] == before[3] + 1,
                  'a run that an earlier request began and that was not yet made is not made while the proof is not good: the refusal says that it is on the record with no verdict yet, and does not say that nothing was run; it is made once the proof is good':
                      sc(pending).get('refused') == 'UNAVAILABLE' and after_pending[0] == after_then[0] and seen(held) == (True, 'INBOX_UNCHECKED', None, False) and after_held == after_pending
                      and 'An earlier request began a run of this design: it is on the record with no verdict yet' in text_of(held) and 'This request ran nothing and counted nothing.' in text_of(held)
                      and state_again == 'WRITABLE' and e['made'] == (FAILED, 'FAIL') and after_made[0] == after_then[0] + 1}
    finally:
        r.stop()
    return checks, e


def f30():
    """Each baseline has its own share of the journal: a job that has used its baseline's share is refused, with nothing run or counted, while a job on another baseline still runs; the engineer of the refused baseline is sent one notice of it; a front door started afresh counts the share again from the journal; when room is made in the journal, the count is taken again; and a journal line that cannot be read stops no answer.  (Amendment 8, D1.)"""
    r = Run('F30'); e = {}
    try:
        s = r.s
        req2 = dict(json.loads((CASE / 'card.json').read_text())['requirement'], id='REQ-SELFTEST-030', title='Bracket service temperature', statement='The bracket shall withstand continuous operation at 170 C.')
        env2 = s.baseline(case_b('F30'), relaxed(requirement=req2)); h2 = env2['baseline_sha256']
        s.enrol('job-b', h2)
        jobs = front_door.read_jobs(s.home); a, b = jobs['job-a'], jobs['job-b']
        def design(wall): return {'material': 'PA66-GF30', 'wall_mm': wall, 'mode': 'normal'}
        one = len((json.dumps(arguments_for(r.h, design(2.5))) + '\n').encode())        # the journal line of one such design
        cfg = front_cfg(r, journal_share_bytes=one + 10)                                # a share that holds one design of this size, and not two
        front = front_door.Front(s.home, Store(deploy.LOCAL_DSN), cfg, (s.keys['engineer'],))
        jp = front_ctl.journal(s.home)
        size = lambda: jp.stat().st_size if jp.exists() else 0
        box_a, box_b = s.home / 'inbox' / r.h[:16], s.home / 'inbox' / h2[:16]
        told = lambda box: sorted(p.name for p in box.glob('STORAGE_FULL_*.txt')) if box.is_dir() else []
        st1, b1 = front.submit(a, design(2.5)); c1, z1 = r.calls(), size()
        st2, b2 = front.submit(a, design(2.6)); st3, b3 = front.submit(a, design(2.7)); c3, z3 = r.calls(), size()
        st4, b4 = front.submit(a, design(2.5)); c4 = r.calls()
        st5, b5 = front.submit(b, design(2.5)); c5 = r.calls()
        told_a, told_b = told(box_a), told(box_b)
        words = (box_a / told_a[0]).read_text(encoding='utf-8') if told_a else ''
        afresh = front_door.Front(s.home, Store(deploy.LOCAL_DSN), cfg, (s.keys['engineer'],))
        st6, b6 = afresh.submit(a, design(2.8)); c6 = r.calls()
        jp.write_text('')                                                               # the operator makes room in the journal
        st7, b7 = afresh.submit(a, design(2.8)); c7 = r.calls()
        with jp.open('a') as f:
            f.write('[' * 5000 + ']' * 5000 + '\n')                                    # a line nested too deep to read, which the door never writes
        try:
            st8, b8 = afresh.submit(a, design(2.8))                                    # a design already run: the count is taken again, and it is answered
        except Exception as exc:
            st8, b8 = type(exc).__name__, {}
        c8 = r.calls()
        e.update(one=one, first=(st1, b1.get('outcome')), refused=[(st2, b2.get('refused')), (st3, b3.get('refused'))], says=b2.get('text', '')[:230], calls=(c1, c3, c4, c5, c6), sizes=(z1, z3),
                 repeat=(st4, b4.get('outcome')), other=(st5, b5.get('outcome')), told_a=told_a, told_b=told_b, notice_head=words.splitlines()[:6], afresh=(st6, b6.get('refused')), room_made=(st7, b7.get('outcome'), c7 - c6), deep_line=(st8, b8.get('outcome'), c8 - c7))
        checks = {'a design within its baseline\'s share is run': st1 == 200 and b1.get('outcome') == 'FAIL',
                  'the next new designs for that baseline are refused at the door: 507, STORAGE_FULL, saying the baseline has used its share; nothing is run or counted, and the journal does not grow':
                      e['refused'] == [(507, 'STORAGE_FULL'), (507, 'STORAGE_FULL')] and 'this baseline has used its share of the journal' in b2.get('text', '')
                      and 'Nothing was run and nothing was counted' in b2.get('text', '') and c3 == c1 and z3 == z1,
                  'a design already journaled for that baseline is still answered, with no new run': e['repeat'] == (200, 'FAIL') and c4 == c3,
                  'a job on another baseline still runs': st5 == 200 and b5.get('outcome') in ('PASS', 'FAIL') and c5 == c4 + 1,
                  'the engineer of the refused baseline has one notice of it in the inbox, however many designs were refused; it gives the reason and says that nothing is run or counted and that no check gave it; the other baseline\'s inbox has none':
                      len(told_a) == 1 and 'THE VERIFICATION SERVICE IS REFUSING NEW RUNS FOR THIS BASELINE' in words and 'This baseline has used its share of the journal' in words
                      and 'nothing is counted' in words and 'not the result of any check' in words and told_b == [],
                  'the refusal tells the caller that the engineer has been sent a notice': 'The responsible engineer has been sent a notice of this.' in b2.get('text', ''),
                  'a front door started afresh counts the share again from the journal, and refuses that baseline at once': e['afresh'] == (507, 'STORAGE_FULL') and 'share' in b6.get('text', '') and c6 == c5,
                  'when room is made in the journal, the count is taken again, and the baseline\'s next design is run': e['room_made'] == (200, 'FAIL', 1),
                  'a journal line nested too deep to read, which the door never writes, is counted for no baseline and does not stop an answer': e['deep_line'] == (200, 'FAIL', 0)}
    finally:
        r.stop()
    return checks, e


def f31():
    """A refusal for a full journal or a full disk reaches the engineer too: one notice on the day for each reason, in the inbox of the refused job's baseline; and where the inbox cannot take it, the notice is kept in the service's own store, the console lists it, and the caller is told that the engineer could not be sent it.  (Amendment 8, D1.)"""
    r = Run('F31'); e = {}
    try:
        s = r.s
        job = front_door.read_jobs(s.home)['job-a']
        def design(wall): return {'material': 'PA66-GF30', 'wall_mm': wall, 'mode': 'normal'}
        box = s.home / 'inbox' / r.h[:16]
        told = lambda: sorted(p.name for p in box.glob('STORAGE_FULL_*.txt')) if box.is_dir() else []
        full = front_door.Front(s.home, Store(deploy.LOCAL_DSN), front_cfg(r, journal_max_bytes=0), (s.keys['engineer'],))                 # a journal with no room at all
        st1, b1 = full.submit(job, design(2.5)); told1 = told()
        words = (box / told1[0]).read_text(encoding='utf-8') if told1 else ''
        full.submit(job, design(2.55)); told_same = told()                              # a second design refused for the same reason
        low = front_door.Front(s.home, Store(deploy.LOCAL_DSN), front_cfg(r, disk_reserve_bytes=10 ** 18), (s.keys['engineer'],))          # as with too little free space on the disk
        st2, b2 = low.submit(job, design(2.6)); told2 = told()
        words_low = ''.join((box / n).read_text(encoding='utf-8') for n in told2 if n not in told1)
        aside = box.with_name(box.name + '.aside'); box.rename(aside); box.write_text('a file in place of the folder\n')
        try:
            st3, b3 = full.submit(job, design(2.7))
        finally:
            box.unlink(); aside.rename(box)
        kept = service_notices.undelivered(s.home, r.h)
        listing = verify_ctl.status(s.home, r.h, s.keys['engineer'], deploy.LOCAL_DSN)
        e.update(full=(st1, b1.get('refused')), says=b1.get('text', '')[:220], told1=told1, notice_head=words.splitlines()[:6], low=(st2, b2.get('refused')), told2=told2,
                 told_same=told_same, blocked=(st3, b3.get('refused')), blocked_says=b3.get('text', '')[-110:], kept=kept, calls=r.calls(), audit_rows=r.audit_rows())
        checks = {'a full journal refuses the design, and the engineer has one notice of it in the inbox: it gives the reason and says that nothing is run or counted':
                      e['full'] == (507, 'STORAGE_FULL') and len(told1) == 1 and 'The journal of submissions has reached its size limit' in words and 'nothing is counted' in words,
                  'the caller is told that the engineer has been sent a notice': 'The responsible engineer has been sent a notice of this.' in b1.get('text', ''),
                  'a second design refused for the same reason on the same day writes no second notice; a refusal for too little disk is refused in its own words and writes a notice of its own, with its own reason':
                      told_same == told1 and e['low'] == (507, 'STORAGE_FULL') and 'less free space than the service keeps for notices' in b2.get('text', '')
                      and len(told2) == 2 and set(told1) < set(told2) and 'The disk that holds the journal has less free space than the service keeps for notices' in words_low,
                  'with the inbox unable to take it, the notice is kept in the service\'s own store, the engineer\'s console lists it, and the caller is told that the engineer could not be sent it':
                      e['blocked'] == (507, 'STORAGE_FULL') and len(kept) == 1 and kept[0].startswith('STORAGE_FULL_') and kept[0] in listing
                      and 'The responsible engineer could not be sent a notice of this.' in b3.get('text', ''),
                  'nothing was run or counted in any of these': r.calls() == 0 and r.audit_rows() == 0}
    finally:
        r.stop()
    return checks, e


def f32():
    """A refusal does not deny a run that an earlier request began: while the gate has not shown that it can write the inbox, the door says that the run is on the record with no verdict yet, and takes it no further; a run the gate has signed as interrupted is finished, and its design is answered whatever the proof says; and a notice of a refusal that had to be kept in the service's own store has its copy in the inbox once the inbox can take it.  (Amendment 8, D3.)"""
    r = Run('F32', crash_at='verify_running'); e = {}
    try:
        sc = lambda x: x.get('structuredContent') or {}
        box = r.s.home / 'inbox' / r.h[:16]; proof = r.s.home / 'inbox_checks' / (r.h + '.json')
        told = lambda d: sorted(p.name for p in d.glob('INBOX_UNCHECKED_*.txt')) if d.is_dir() else []
        cut = lambda: sorted(p.name for p in box.glob('INTERRUPTED_*.txt')) if box.is_dir() else []
        r.submit(GOOD); time.sleep(0.3); exit_code = r.s.procs['host'].poll()             # the host dies during the run
        r.s.stop_host()
        aside = box.with_name(box.name + '.aside'); box.rename(aside); box.write_text('a file in place of the folder\n')
        try:
            r.s.start_host(); state_blocked = proven(r.s, r.h, want='NOT_WRITABLE')       # the gate, starting, finds that it cannot write the inbox
            before = (r.calls(), r.audit_rows())
            held = r.submit(GOOD); after_held = (r.calls(), r.audit_rows())
            kept = [n for n in service_notices.undelivered(r.s.home, r.h) if n.startswith('INBOX_UNCHECKED_')]
        finally:
            box.unlink(); aside.rename(box)
        state_back = proven(r.s, r.h)                                                     # put back, the gate's own look proves the inbox again
        again = r.submit(GOOD); cut_after = cut()                                         # the gate signs the run as interrupted
        proof.write_text(json.dumps(dict(json.loads(proof.read_text()), checked_at=time.time(), inbox=False)))    # the proof on record now says the inbox could not be written
        calls = r.calls()
        finished = r.submit(GOOD); after_finished = r.calls(); cut_then = cut()
        new = r.submit({'material': 'PA66-GF30', 'wall_mm': 2.5, 'mode': 'normal'}); in_inbox = told(box); after_new = r.calls()
        e.update(host_exit=exit_code, states=(state_blocked, state_back), held=(sc(held).get('refused'), text_of(held)[-420:]), counts=(before, after_held), kept=kept,
                 again=sc(again).get('outcome'), finished=sc(finished).get('outcome'), interrupted_notices=(cut_after, cut_then), new=(sc(new).get('refused'), text_of(new)[-150:]), in_inbox=in_inbox)
        checks = {'the host died during the run (exit 137), and the gate, started again with a file in place of the inbox, shows that it cannot write it': exit_code == 137 and state_blocked == 'NOT_WRITABLE',
                  'asked again while the proof is not good, the design is refused, and the refusal does not deny the run: it says that an earlier request began a run that is on the record with no verdict yet, and that this request ran nothing; it does not say that nothing was run; nothing more is run or counted':
                      sc(held).get('refused') == 'INBOX_UNCHECKED' and 'An earlier request began a run of this design: it is on the record with no verdict yet' in text_of(held)
                      and 'This request ran nothing and counted nothing.' in text_of(held) and 'Nothing was run and nothing was counted' not in text_of(held) and after_held == before,
                  'the notice of that refusal is kept in the service\'s own store, as the inbox cannot take it, and the caller is told that the engineer could not be sent it':
                      len(kept) == 1 and kept[0].endswith('_NOT_WRITABLE.txt') and 'The responsible engineer could not be sent a notice of this.' in text_of(held),
                  'once the gate has shown that it can write the inbox, the design is answered INTERRUPTED, with one notice of the run in the inbox': state_back == 'WRITABLE' and sc(again).get('outcome') == 'INTERRUPTED' and len(cut_after) == 1,
                  'a run signed as interrupted is finished: with the proof saying again that the inbox could not be written, its design is still answered INTERRUPTED, nothing more is run, and no second notice of the run is written':
                      sc(finished).get('outcome') == 'INTERRUPTED' and after_finished == calls and cut_then == cut_after,
                  'a new design is then refused with nothing run, and the notice that was kept in the store has its copy in the inbox now that the inbox can take it; the caller is told that the engineer has been sent it':
                      sc(new).get('refused') == 'INBOX_UNCHECKED' and 'Nothing was run and nothing was counted.' in text_of(new) and after_new == calls and in_inbox == kept
                      and 'The responsible engineer has been sent a notice of this.' in text_of(new)}
    finally:
        r.stop()
    return checks, e


def f33():
    """Through the front door, what an assistant or a person reads of a pass calls it the declared check met and shows what the check does not cover: the answer's text and its fields, the status's text and its fields, the command line's answers, and the MCP server's descriptions and instructions.  The front door's own text, for when it cannot read the stored card, says that a result does not say the check is correct.  (Amendment 9.)"""
    r = Run('F33'); e = {}
    try:
        lims = r.env['card']['check']['stated_limits']; excl = 'The check does not cover: ' + '; '.join(lims) + '.'
        bare = lambda t: [l for l in str(t).splitlines() if re.search(r'\bPASS\b', l.replace('(signed as PASS)', ''))]
        sc = lambda x: x.get('structuredContent') or {}
        st0 = r.mcp().call('plea_status')
        passed = r.submit(GOOD)
        st = r.mcp().call('plea_status')
        tools = r.mcp().tools(); opened = (r.mcp().opened or {}).get('result') or {}
        cli_code, cli_status = r.s.cli(r.job, 'status')
        cli_s_code, cli_submit = r.s.cli(r.job, 'submit', GOOD)
        st_raw, body = raw(r.job, 'GET', '/status')
        held_card = r.env['card']
        v = B._verdict(held_card, GOOD, 'MET', [dict(c, achieved='240', margin='40', met=True) for c in B._blank(held_card)])
        own = front_door.plain_text(v, {'total': 1, 'PASS': 1, 'FAIL': 0, 'UNKNOWN': 0}, 'aid-1')
        met_line = (f"DECLARED CHECK MET, for design {B.design_hash(GOOD)[:16]}… only.  This says what the declared check returned against the baselined limits.  "
                    'It does not say the check is correct, the requirement is complete, or the design is safe.')
        said = json.dumps([t.get('description') for t in tools]) + str(opened.get('instructions'))
        lines = text_of(passed).splitlines()
        e.update(first=lines[:2], fields={k: sc(passed).get(k) for k in ('outcome', 'met', 'declared_check_met', 'check_does_not_cover')}, signed=(sc(passed).get('verdict') or {}).get('verdict'),
                 status_fields=(sc(st0).get('declared_check_met'), sc(st).get('declared_check_met'), 'verified' in sc(st), 'verified' in (body or {})),
                 status_tail=text_of(st).splitlines()[-2:], cli=(cli_code, cli_status.strip().splitlines()[-2:], cli_s_code, cli_submit.strip().splitlines()[:2]),
                 bare=[bare(t) for t in (text_of(passed), text_of(st), cli_status, cli_submit, said)], said=said[:300], own=own.splitlines()[-2:])
        checks = {'the answer to a pass begins DECLARED CHECK MET, with what the check does not cover on the next line; its fields say the declared check was met and list what the check does not cover; the signed verdict in it still says PASS':
                      e['first'] == [MET, excl] and e['fields'] == {'outcome': 'PASS', 'met': True, 'declared_check_met': True, 'check_does_not_cover': lims} and e['signed'] == 'PASS',
                  'the status\'s fields say whether a design has met the declared check under that name, before a run and after it, and no field is called verified, in the tool\'s result or in the front door\'s answer':
                      e['status_fields'] == (False, True, False, False),
                  'the status\'s text, through the tool and through the command line, shows for which design the declared check was met, that this does not say the check is correct, and what the check does not cover':
                      e['status_tail'] == [met_line, excl] and cli_code == 0 and e['cli'][1] == [met_line, excl],
                  'the command line\'s answer to a pass begins DECLARED CHECK MET, with what the check does not cover, and exits 0': cli_s_code == 0 and e['cli'][3] == [MET, excl],
                  'no line of the words of the answers and the status (their first part; the second gives the fields, in which outcome is still PASS), nor of the tools\' descriptions or the server\'s instructions, shows the bare word PASS': e['bare'] == [[], [], [], [], []],
                  'the tools\' descriptions and the server\'s instructions call a pass the declared check met, and say it is not a statement that the check is correct':
                      'declared check met' in said and 'not as a statement that the check is correct' in said and 'not that the check is correct' in said,
                  'in process, the front door\'s own text for a pass, for when it cannot read the stored card, says that the result does not say the check is correct, and that what the check does not cover cannot be shown there':
                      e['own'][0] == 'This result does not say the check is correct, the requirement is complete, or the design is safe.  What the check does not cover cannot be shown here: ask the responsible engineer.'}
    finally:
        r.stop()
    return checks, e


def f34():
    """The gate's check is called what it is: a new run refused without it is refused as INBOX_UNCHECKED, and its notice is named so.  And a run left pending when the gate host died gets its notice with no one sending its design again: the front door asks for it itself once it has seen it pending for a while, and only while the gate's check of the inbox is good; asking for it runs nothing again.  (Amendment 9.)"""
    r = Run('F34', crash_at='verify_running'); e = {}
    try:
        box = r.s.home / 'inbox' / r.h[:16]; check = r.s.home / 'inbox_checks' / (r.h + '.json')
        cut = lambda: sorted(p.name for p in box.glob('INTERRUPTED_*.txt')) if box.is_dir() else []
        sc = lambda x: x.get('structuredContent') or {}
        outcomes = lambda: [a.get('outcome') for a in (raw(r.job, 'GET', '/status')[1] or {}).get('attempts', [])]
        r.submit(GOOD); time.sleep(0.3); exit_code = r.s.procs['host'].poll()           # the gate host dies during the run
        r.s.stop_host(); r.s.start_host(); first_state = proven(r.s, r.h)
        calls = r.calls()
        aside = box.with_name(box.name + '.aside'); box.rename(aside); box.write_text('a file in place of the folder\n')
        try:
            check.unlink()                                                              # no check on record; the gate's look is not due again for 30 seconds
            blocked = service_notices.delivery_state(r.s.home, r.h)[0]
            r.s.stop_front(); r.s.start_front(sweep_after=1.0, sweep_every=0.3)         # the front door looks for runs left pending every 0.3 s, and asks after one second
            time.sleep(3.0)
            while_blocked = (outcomes(), cut(), service_notices.undelivered(r.s.home, r.h), r.calls())
        finally:
            box.unlink(); aside.rename(box)
        r.s.stop_host(); r.s.start_host(); back = proven(r.s, r.h)                     # the gate, starting, checks the inbox again
        t0 = time.time()
        while time.time() - t0 < 20 and not cut():
            time.sleep(0.2)
        after = (outcomes(), cut(), r.calls(), round(time.time() - t0, 1))
        logged = 'a run left pending was asked for again' in (r.s.dir / 'front.log').read_text(errors='replace')
        again = r.submit(GOOD); after_again = (cut(), r.calls())
        check.unlink()                                                                  # no check on record: the gate's look is not due for 30 seconds
        refused = r.submit({'material': 'PA66-GF30', 'wall_mm': 2.5, 'mode': 'normal'})
        named = sorted(p.name for p in box.iterdir() if p.name.startswith(('INBOX_UNCHECKED_', 'DELIVERY_')))
        e.update(host_exit=exit_code, states=(first_state, blocked, back), while_blocked=while_blocked, after=after, logged=logged, again=(sc(again).get('outcome'), after_again), again_fields=(sc(again).get('declared_check_met'), sc(again).get('check_does_not_cover') == r.env['card']['check']['stated_limits']),
                 refused=(sc(refused).get('refused'), text_of(refused)[:90]), named=named)
        checks = {'the host died during the run (exit 137); started again, the gate shows that it can write the inbox; with a file in place of the inbox and the check taken away, the check is not good':
                      exit_code == 137 and e['states'][:2] == ('WRITABLE', 'UNCHECKED'),
                  'while the gate\'s check of the inbox is not good, the front door, which looks for runs left pending every 0.3 seconds and asks after one, does not ask: the run is still pending, no notice of any kind is written, and nothing more was run':
                      while_blocked[0] == ['PENDING'] and while_blocked[1] == [] and while_blocked[2] == [] and while_blocked[3] == calls,
                  'once the gate has shown again that it can write the inbox, the front door asks for the run itself, with no design sent by anyone: the run is INTERRUPTED, one notice of it is in the inbox, the check was not run again, and the front door\'s log says it asked':
                      e['states'][2] == 'WRITABLE' and after[0] == ['INTERRUPTED'] and len(after[1]) == 1 and after[2] == calls and logged,
                  'the design sent again afterwards is answered INTERRUPTED, with no second notice and nothing run; its fields say the declared check was not met, and what it does not cover':
                      e['again'] == ('INTERRUPTED', (after[1], calls)) and e['again_fields'] == (False, True),
                  'with no check on record, a new design is refused as INBOX_UNCHECKED, and the engineer\'s notice of it is named INBOX_UNCHECKED, for its reason; nothing is named as before':
                      e['refused'][0] == 'INBOX_UNCHECKED' and len(named) == 1 and named[0].startswith('INBOX_UNCHECKED_') and named[0].endswith('_UNCHECKED.txt')}
    finally:
        r.stop()
    return checks, e


def f35():
    """The front door's look for runs left pending acts on one run less and less often while it cannot be finished, also when the journal does not hold its design, and leaves it after twelve times; it does not ask while its baseline's budget is held; and it writes the notice of a run cut off whose notice is missing, held or not, and in fixed words where the journal does not hold the design; none of it runs anything again.  (Amendment 9.)"""
    r = Run('F35', crash_at='verify_running'); e = {}
    try:
        box = r.s.home / 'inbox' / r.h[:16]
        cut = lambda: sorted(p.name for p in box.glob('INTERRUPTED_*.txt')) if box.is_dir() else []
        lose = lambda: [p.unlink() for p in box.glob('INTERRUPTED_*.txt')]
        outcomes = lambda: [a.get('outcome') for a in (raw(r.job, 'GET', '/status')[1] or {}).get('attempts', [])]
        r.submit(GOOD); time.sleep(0.3); exit_code = r.s.procs['host'].poll()           # the gate host dies during the run
        r.s.stop_host(); r.s.start_host(); state = proven(r.s, r.h); calls = r.calls()
        cfg = {'witness_url': f"https://127.0.0.1:{r.s.ports['witness']}", 'witness_keys': [r.s.keys['witness']], 'gate_url': f"https://127.0.0.1:{r.s.ports['host']}",
               'gate_key': r.s.keys['gate'], 'tls': {'ca': r.s.pki['ca'], 'cert': r.s.pki['frontdoor'][0], 'key': r.s.pki['frontdoor'][1]},
               'journal': str(r.s.home / 'front' / 'submissions.jsonl')}
        door = lambda: front_door.Front(r.s.home, Store(deploy.LOCAL_DSN), cfg, [r.s.keys['engineer']])   # another front door, in this process, on the same service
        journal = pathlib.Path(cfg['journal']); aside = journal.with_name(journal.name + '.aside')

        def stand_in(front):                                                             # an ask that does not finish the run: it stays pending
            got = []
            front.submit = lambda b, d: (got.append(1), (503, {'refused': 'UNAVAILABLE'}))[1]
            return got
        front = door(); asked = stand_in(front)
        t0 = time.time(); counts = []
        for dt in (0, 9, 10, 11, 29, 30, 69, 70):
            front.sweep(after=10, now=t0 + dt); counts.append(len(asked))
        for i in range(16):
            front.sweep(after=10, now=t0 + 1e6 * (i + 1))
        capped, waits = len(asked), sorted(w['wait'] for w in front._pending.values())
        reader = front.store.observe
        front.store.observe = lambda root: (_ for _ in ()).throw(OSError('the store cannot be read'))
        try:
            front.sweep(after=10, now=t0 + 2e7)                                              # a look that cannot read the store
        finally:
            front.store.observe = reader
        kept = sorted(w['wait'] for w in front._pending.values())
        brisk = door(); brisk_asked = stand_in(brisk)
        for i in range(5):
            brisk.sweep(after=0, now=t0 + 0.1 * i)                                          # a wait of nought is taken as the least, one second
        mid = (outcomes(), r.calls(), cut())
        journal.rename(aside)                                                                # the journal does not hold the design
        try:
            blind = door(); lookups, find = [], blind._design_for
            blind._design_for = lambda key: (lookups.append(1), find(key))[1]
            blind_counts = []
            for dt in (0, 10, 11, 29, 30, 31):
                blind.sweep(after=10, now=t0 + 5e8 + dt); blind_counts.append(len(lookups))
        finally:
            aside.rename(journal)
        control = Store(verify_ctl.CONTROL_DSN)
        T = t0 + 1e8; holder = door(); held_asked = stand_in(holder)
        control.apply(r.root, ('HOLD',))
        for dt in (0, 10, 20):
            holder.sweep(after=10, now=T + dt)
        held = (len(held_asked), outcomes())
        control.apply(r.root, ('RECOVER', True, True))
        holder.submit = front_door.Front.submit.__get__(holder)                             # the real path, as a caller's request takes it
        asked_real = holder.sweep(after=10, now=T + 21)
        after = (outcomes(), cut(), r.calls())
        between = holder.sweep(after=10, now=T + 22)                                         # finished and noticed: nothing to do, and forgotten
        lose()                                                                               # the notice is lost
        looks = (holder.sweep(after=10, now=T + 1e6), holder.sweep(after=10, now=T + 1e6 + 10), holder.sweep(after=10, now=T + 2e6))
        restored = (cut(), r.calls())
        control.apply(r.root, ('HOLD',)); lose()                                             # lost again, with the budget held
        held_looks = (holder.sweep(after=10, now=T + 3e6), holder.sweep(after=10, now=T + 3e6 + 10)); held_restored = (cut(), r.calls())
        held_between = holder.sweep(after=10, now=T + 3e6 + 11)                              # noticed again: nothing to do, and forgotten
        lose(); journal.rename(aside)                                                        # lost again, and the journal does not hold the design
        try:
            blind_looks = (holder.sweep(after=10, now=T + 4e6), holder.sweep(after=10, now=T + 4e6 + 10))
        finally:
            aside.rename(journal)
        fixed = [p.read_text() for p in box.glob('INTERRUPTED_*.txt')]
        e.update(host_exit=exit_code, state=state, counts=counts, capped=capped, waits=waits, kept=kept, brisk=len(brisk_asked), mid=mid, blind_counts=blind_counts,
                 held=held, asked_real=asked_real, after=after, between=between, looks=looks, restored=restored, held_looks=held_looks, held_restored=held_restored,
                 blind_looks=blind_looks, fixed=[t[-200:] for t in fixed], calls_at_end=r.calls())
        checks = {'the host died during the run (exit 137) and, started again, shows that it can write the inbox; the run is pending': exit_code == 137 and state == 'WRITABLE' and mid[0] == ['PENDING'],
                  'while an ask does not finish the run, it is asked for once it has been pending for the wait (10 s here), and again after 20 s and then 40 s more: twice the wait before each time':
                      counts == [0, 0, 1, 1, 1, 2, 2, 3],
                  'the wait stops growing at an hour, and after twelve asks the look leaves the run as it is; a look that cannot read the store forgets no wait; a wait of nought is taken as one second; nothing was run and no notice was written meanwhile':
                      waits == [front_door.SWEEP_MAX_WAIT] == [3600.0] and capped == front_door.SWEEP_MAX_ASKS == 12 and kept == waits and e['brisk'] == 0 and mid[1] == calls and mid[2] == [],
                  'a run whose design the journal does not hold is looked for no more often: at 10 s, then 20 s after that, and not between':
                      blind_counts == [0, 1, 1, 1, 2, 2],
                  'while the baseline\'s budget is held, the run is not asked for, though it is due, and is still pending': held == (0, ['PENDING']),
                  'with the budget open again, the real ask, at once, makes the run INTERRUPTED, with one notice and nothing run again':
                      [d.get('outcome') for d in asked_real] == ['INTERRUPTED'] and after[0] == ['INTERRUPTED'] and len(after[1]) == 1 and after[2] == calls,
                  'a run cut off whose notice is missing is given it by the look, once it is due, and only once; nothing is run':
                      between == [] and looks[0] == [] and [d.get('outcome') for d in looks[1]] == ['INTERRUPTED_NOTICE_WRITTEN'] and looks[2] == [] and restored == (after[1], calls),
                  'with the budget held, a missing notice of a run cut off is still written, once it is due; nothing is run':
                      held_looks[0] == [] and [d.get('outcome') for d in held_looks[1]] == ['INTERRUPTED_NOTICE_WRITTEN'] and held_restored == (after[1], calls),
                  'where the journal does not hold the design, the notice is still written, in the service\'s fixed words, which say the design is not shown; nothing is run':
                      held_between == [] and blind_looks[0] == [] and [d.get('outcome') for d in blind_looks[1]] == ['INTERRUPTED_NOTICE_WRITTEN'] and len(fixed) == 1
                      and 'The design is not shown here.' in fixed[0] and e['calls_at_end'] == calls}
    finally:
        r.stop()
    return checks, e


def f36():
    """An answer does not take longer with every run already made on the baseline: of 25 designs sent one after another through
    the front door, the last five are answered about as fast as the first five, and each answer counts the runs so far.
    (Amendment 13.)"""
    r = Run('F36'); e = {}
    try:
        seconds, totals, outcomes = [], [], []
        for i in range(25):
            d = {'material': 'PA66-GF30', 'wall_mm': round(3 + i / 1000, 3), 'mode': 'normal'}
            t0 = time.monotonic(); status, answer = raw(r.job, 'POST', '/submit', json.dumps({'design': d}).encode()); seconds.append(round(time.monotonic() - t0, 3))
            totals.append((answer.get('runs') or {}).get('total') if isinstance(answer, dict) else None); outcomes.append(answer.get('outcome') if isinstance(answer, dict) else None)
        middle = lambda xs: sorted(xs)[len(xs) // 2]
        ok, why, s = r.checked()
        e.update(seconds=seconds, first_five=middle(seconds[:5]), last_five=middle(seconds[-5:]), grew_by=round(middle(seconds[-5:]) - middle(seconds[:5]), 3), totals=totals,
                 outcomes=sorted(set(map(str, outcomes))), record_verifies=ok, why=why, not_met=s.get('not_met'), notices=r.notices())
        checks = {'25 designs sent one after another each get their FAIL, and each answer counts the runs so far, 1 to 25':
                      outcomes == ['FAIL'] * 25 and totals == list(range(1, 26)),
                  'the last five are answered about as fast as the first five: their middle time is less than a quarter of a second more (it was a second more before)':
                      e['grew_by'] < 0.25,
                  'every failure has its notice, and the record verifies with all 25':
                      e['notices'] == 25 and ok and s.get('not_met') == 25}
    finally:
        r.stop()
    return checks, e


# ====================================================================== Amendment 17 (22 November 2026): D16
def f37():
    """Amendment 17 (D16).  The latest binding seen for each job, and its revocation, are kept in the database: a restart forgets nothing, a revocation is never undone, and a stale, conflicting or mismatched binding admits nobody."""
    import random
    import front_state
    import psycopg
    r = Run('F37'); e = {}
    try:
        s = r.s; path = front_door.jobs_path(s.home); local = Store(deploy.LOCAL_DSN); owner = Store(deploy_front.OWNER_DSN)
        sub = lambda d=GOOD: raw(r.job, 'POST', '/submit', json.dumps({'design': d}).encode())
        refused = lambda x: x[0] == 403 and x[1].get('refused') == 'NOT_ENROLLED'
        first = sub(BAD)
        enrolled = path.read_text()                                                     # the ENROL binding, seq 1
        s.stop_front(); s.start_front(); after_restart = sub(GOOD)                      # no attack: still admitted after a restart
        calls_admitted = r.calls()
        s.revoke('job-a'); revoked = sub()
        after_revoke = path.read_text()
        s.stop_front(); s.start_front()
        path.write_text(enrolled); put_back_after_restart = sub()                       # the earlier signed binding put back, after a restart
        path.write_text(after_revoke)
        # a later binding signed by the engineer for the revoked job: revocation is absorbing
        jobs = json.loads(after_revoke); rv = jobs['jobs']['job-a']
        later = {k: rv[k] for k in front_door.BINDING_FIELDS}; later.update(event='REBIND', seq=rv['seq'] + 1, previous=rv['baseline_sha256'], note=None)
        later = dict(later, signer=s.engineer.public_hex, signature=s.engineer.sign(front_door.binding_message(later)))
        jobs['jobs']['job-a'] = later; path.write_text(json.dumps(jobs)); unrevoked = sub(); path.write_text(after_revoke)
        calls_after_revoke = r.calls()
        # a second job: a conflicting binding (another one, signed by the engineer, with the same number)
        job_b = s.enrol('job-b', r.h); ok_b = raw(job_b, 'POST', '/submit', json.dumps({'design': BAD}).encode())
        jobs = json.loads(path.read_text()); kb = jobs['jobs']['job-b']; held_b = path.read_text()
        twin = {k: kb[k] for k in front_door.BINDING_FIELDS}; twin.update(note='another binding with the same number')
        twin = dict(twin, signer=s.engineer.public_hex, signature=s.engineer.sign(front_door.binding_message(twin)))
        jobs['jobs']['job-b'] = twin; path.write_text(json.dumps(jobs)); conflict = raw(job_b, 'GET', '/requirement')
        path.write_text(held_b); same_again = [raw(job_b, 'GET', '/requirement')[0] for _ in range(3)]  # retries of the binding seen first
        # a binding signed by the engineer that names this baseline and another baseline's budget
        other = s.baseline(case_b('F37'), relaxed(), alongside_reason='a relaxed copy baselined as new, as the test needs')
        jobs = json.loads(held_b); mm = {k: jobs['jobs']['job-b'][k] for k in front_door.BINDING_FIELDS}; mm.update(event='REBIND', seq=mm['seq'] + 1, root=B.root_for(other['card']))
        mm = dict(mm, signer=s.engineer.public_hex, signature=s.engineer.sign(front_door.binding_message(mm)))
        jobs['jobs']['job-b'] = mm; path.write_text(json.dumps(jobs)); calls0 = r.calls(); mismatch = raw(job_b, 'POST', '/submit', json.dumps({'design': GOOD}).encode())
        calls_mismatch = r.calls() - calls0; path.write_text(held_b)
        # the record cannot be read: nobody is admitted, and it comes back when it can
        with owner.connect() as c:
            c.execute('REVOKE EXECUTE ON FUNCTION public.verify_front_observe(text, bigint, text, boolean) FROM plea_local')
        calls1 = r.calls(); unreadable = raw(job_b, 'POST', '/submit', json.dumps({'design': GOOD}).encode()); calls_unreadable = r.calls() - calls1
        with owner.connect() as c:
            c.execute('GRANT EXECUTE ON FUNCTION public.verify_front_observe(text, bigint, text, boolean) TO plea_local')
        readable_again = raw(job_b, 'GET', '/requirement')
        # what the service's own role can do to the record: only move it forward; it cannot write the table
        direct = {}
        for what, sql in (('update', "UPDATE public.verify_front_binding SET revoked = false WHERE job = 'job-a'"), ('delete', "DELETE FROM public.verify_front_binding WHERE job = 'job-a'"),
                          ('insert', "INSERT INTO public.verify_front_binding VALUES ('job-z', 1, repeat('0', 64), false, now())")):
            try:
                with local.connect() as c:
                    c.execute(sql)
                direct[what] = 'done'
            except psycopg.Error as exc:
                direct[what] = type(exc).__name__
        rolled = 'job-t-' + uuid.uuid4().hex[:8]
        with local.connect() as c:                                                      # a transaction that fails leaves nothing behind
            c.execute('SELECT public.verify_front_observe(%s, 99, %s, true)', (rolled, '1' * 64)); c.rollback()
        after_rollback = front_state.observe(local, rolled, 2, '2' * 64, False)
        # concurrent observers: the highest number wins, and nothing lower is current after it
        racer = 'job-r-' + uuid.uuid4().hex[:8]; seqs = list(range(1, 41)); random.shuffle(seqs); answers = {}
        def go(n):
            answers[n] = front_state.observe(Store(deploy.LOCAL_DSN), racer, n, format(n, '064x'), False)
        threads = [threading.Thread(target=go, args=(n,)) for n in seqs]
        [t.start() for t in threads]; [t.join() for t in threads]
        with owner.connect() as c:
            final = c.execute('SELECT seq, revoked FROM public.verify_front_binding WHERE job = %s', (racer,)).fetchone()
        late = [front_state.observe(local, racer, n, format(n, '064x'), False) for n in (1, 39)]
        # the service's own role can deny a job, never admit one: a made-up revocation, then a made-up lower number
        realm = hashlib.sha256(pathlib.Path(s.pki['ca']).read_bytes()).hexdigest()[:32]
        denied_by_role = front_state.observe(local, f'{realm}:job-b', 10 ** 6, '3' * 64, True); job_b_after = raw(job_b, 'GET', '/requirement')
        e.update(first=first[0], after_restart=after_restart[0], revoked=(revoked[0], revoked[1].get('refused')), put_back_after_restart=(put_back_after_restart[0], put_back_after_restart[1].get('refused')),
                 unrevoked=(unrevoked[0], unrevoked[1].get('refused')), conflict=(conflict[0], conflict[1].get('refused')), same_again=same_again, ok_b=ok_b[0],
                 mismatch=(mismatch[0], mismatch[1].get('refused')), calls_mismatch=calls_mismatch, unreadable=(unreadable[0], unreadable[1].get('refused')), calls_unreadable=calls_unreadable,
                 readable_again=readable_again[0], direct=direct, after_rollback=after_rollback, race=dict(final=final, current=sum(a == 'CURRENT' for a in answers.values()), late=late),
                 denied_by_role=denied_by_role, job_b_after=(job_b_after[0], job_b_after[1].get('refused')), calls=(calls_admitted, calls_after_revoke, r.calls()))
        checks = {'an enrolled job is admitted, and still admitted after the front door restarts': first[0] == 200 and after_restart[0] == 200,
                  'a revoked job is refused, and the earlier signed binding put back after a restart does not undo it': refused(revoked) and refused(put_back_after_restart),
                  'revocation is absorbing: a later binding signed by the engineer does not admit the revoked job': refused(unrevoked) and calls_after_revoke == calls_admitted,
                  'a second binding with the same number is refused; the one seen first, asked again, is answered': refused(conflict) and same_again == [200, 200, 200],
                  'a binding naming this baseline and another\'s budget admits nobody, and nothing reaches the gate': refused(mismatch) and calls_mismatch == 0,
                  'when the record cannot be read, the front door answers 503 and runs nothing; then it answers again': unreadable[0] == 503 and unreadable[1].get('refused') == 'UNAVAILABLE' and calls_unreadable == 0 and readable_again[0] == 200,
                  'the service\'s role cannot write the table, and a rolled-back call leaves nothing': all(v == 'InsufficientPrivilege' for v in direct.values()) and after_rollback == 'CURRENT',
                  'concurrent observers end at the highest number, and a lower one is then stale': final == (40, False) and late == ['STALE', 'STALE'],
                  'the service\'s role can deny a job with a made-up revocation, and cannot admit one (it fails closed)': denied_by_role == 'REVOKED' and job_b_after[0] == 403}
    finally:
        r.stop()
    return checks, e


TESTS = {'F3': f3, 'F4': f4, 'F5': f5, 'F6': f6, 'F7': f7, 'F8': f8, 'F9': f9, 'F10': f10, 'F11': f11, 'F12': f12, 'F13': f13, 'F14': f14, 'F15': f15, 'F16': f16, 'F17': f17, 'F18': f18, 'F19': f19, 'F20': f20, 'F21': f21, 'F22': f22, 'F23': f23, 'F24': f24, 'F25': f25, 'F26': f26, 'F27': f27, 'F28': f28, 'F29': f29, 'F30': f30, 'F31': f31, 'F32': f32, 'F33': f33, 'F34': f34, 'F35': f35, 'F36': f36, 'F37': f37}


def main():
    wanted = [a for a in sys.argv[1:] if a in TESTS] or list(TESTS)
    OUT.mkdir(parents=True, exist_ok=True)
    results, t0 = {}, time.time()
    for name in wanted:
        started = time.time()
        try:
            checks, evidence = TESTS[name]()
            ok = bool(checks) and all(checks.values())
            results[name] = {'title': TESTS[name].__doc__, 'ok': ok, 'checks': checks, 'evidence': evidence, 'seconds': round(time.time() - started, 1)}
        except Exception as exc:                                                     # a harness or service error is a failed test, never a pass
            results[name] = {'title': TESTS[name].__doc__, 'ok': False, 'checks': {}, 'error': f'{type(exc).__name__}: {exc}'[:400], 'seconds': round(time.time() - started, 1)}
        res = results[name]
        print(f"{name:<4} {'PASS' if res['ok'] else 'FAIL'}  {res['title']}" + ('' if res['ok'] else '   <- ' + (res.get('error') or ', '.join(k for k, v in res['checks'].items() if not v))), flush=True)
    passed = sum(x['ok'] for x in results.values())
    out = {'tests': results, 'passed': passed, 'of': len(results), 'seconds': round(time.time() - t0, 1), 'PASS': passed == len(results) == len(wanted)}
    (GATEWAY / 'outputs' / 'verify_front_tests.json').write_text(json.dumps(out, indent=1, default=str))
    print(f"FRONT RESULT: {'PASS' if out['PASS'] else 'FAIL'} ({passed} of {len(results)})")
    sys.exit(0 if out['PASS'] else 1)


if __name__ == '__main__':
    main()
