#!/usr/bin/env python3
"""Declared tests F1-F16 for the front door and the MCP server (verify/DECLARED_FRONT.md states the expected outcomes).

    verify_front_tests.py [F1 F6 ...]     all sixteen by default; writes outputs/verify_front_tests.json; exits 1 if any test fails

F1 and F2 run the first plug-in as it was released, with no front door, and show the two defects this work is for.
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
import verify_client                    # noqa: E402
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
def f1():
    """The first plug-in, with no front door: a caller holding the workspace's credentials can run a design against another baseline and be told PASS."""
    s = deploy.Services(OUT / 'F1').start(); e = {}
    try:
        a = s.baseline(CASE, draft()); ha = a['baseline_sha256']
        b = s.baseline(case_b('F1'), relaxed()); hb = b['baseline_sha256']             # a relaxed copy, baselined as new
        cfg = s.client_config(OUT / 'F1' / 'workspace', ha)
        honest = s.submit(cfg, BAD)                                                    # 180 C against A's 200 C
        c = verify_client.Client(cfg)                                                  # what the workspace holds, used directly
        args = arguments_for(hb, BAD)                                                  # the caller names baseline B
        verdict = c.governor().attempt(request_key(args), 'verify', **args)            # on A's budget
        journal = [cfg.parent / 'submissions.jsonl']
        ok_a, checks_a, s_a = check_record.verify(s.record(ha, journal), s.keys)
        ok_b, _, s_b = check_record.verify(s.record(hb), s.keys)
        bad = [n for n, _, good, _ in checks_a if not good]
        e.update(honest=(honest[0], head(honest[1])), told=(verdict.get('verdict'), verdict.get('reason_code')), verdict_names=str(verdict.get('baseline_sha256'))[:16],
                 is_b=verdict.get('baseline_sha256') == hb, runs_on_a=s_a.get('official_runs'), runs_on_b=s_b.get('official_runs'), notices_a=len(s.inbox(ha)), notices_b=len(s.inbox(hb)),
                 record_a_verifies=ok_a, record_a_fails_checks=bad, why=failing(checks_a), record_b_verifies=ok_b)
        checks = {'sent honestly, the design fails against A (exit status 2)': honest[0] == 2 and head(honest[1]) == FAILED,
                  'naming baseline B on A\'s budget, the same design is told PASS': verdict.get('verdict') == 'PASS' and verdict.get('baseline_sha256') == hb,
                  'the run is charged to A, B shows no run, and nobody is sent a notice for it': s_a.get('official_runs') == 2 and s_b.get('official_runs') == 0 and e['notices_a'] == 1 and e['notices_b'] == 0,
                  'the record of A no longer verifies, at checks 5 and 6 only': not ok_a and bad == [5, 6]}
    finally:
        s.stop()
    return checks, e


def f2():
    """The first plug-in, with no front door: one design the database cannot store leaves the record of its baseline unable to verify."""
    s = deploy.Services(OUT / 'F2').start(); e = {}
    try:
        got = {}
        for name, design in (('a NUL character in a value', dict(GOOD, material='PPS-GF40\u0000')), ('an infinite number', dict(GOOD, wall_mm=float('inf')))):
            env = s.baseline(CASE, draft()); h = env['baseline_sha256']
            cfg = s.client_config(OUT / 'F2' / f'workspace_{len(got)}', h)
            first = s.submit(cfg, design); again = s.submit(cfg, design); good = s.submit(cfg, GOOD)
            ok, checks, summ = check_record.verify(s.record(h, [cfg.parent / 'submissions.jsonl']), s.keys, GOOD)
            got[name] = dict(first=first[0], traceback='Traceback' in first[1], again=again[0], good=(good[0], head(good[1])), record_verifies=ok, fails=[n for n, _, g, _ in checks if not g],
                             why=failing(checks), outcomes=sorted(r['outcome'] for r in summ.get('runs', [])), status=summ.get('status'))
        e.update(got)
        checks = {'the client stops with a traceback (exit status 1), both times': all(g['first'] == 1 and g['again'] == 1 and g['traceback'] for g in got.values()),
                  'a run is left with a signed verdict and no stored result': all('INVALID' in g['outcomes'] for g in got.values()),
                  'a good design sent afterwards meets the check (exit status 0)': all(g['good'] == (0, MET) for g in got.values()),
                  'but the record of that baseline no longer verifies, at check 6 only, and its status is NOT VERIFIED': all(not g['record_verifies'] and g['fails'] == [6] and g['status'] == 'NOT VERIFIED' for g in got.values())}
    finally:
        s.stop()
    return checks, e


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
        b = r.s.baseline(case_b('F6'), relaxed()); hb = b['baseline_sha256']; root_b = B.root_for(b['card'])        # the relaxed copy exists and has a budget
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
        other = s.baseline(case_b('F10'), relaxed()); path = front_door.jobs_path(s.home); honest = path.read_text()
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
        unrelated = s.baseline(src, relaxed())                                          # a relaxed copy baselined as new: not a revision
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
        same = s.baseline(case_b('F13'), relaxed())                                     # the first requirement again, relaxed, baselined as new
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
        not_a_card = r.submit(design(2.9)); stored.write_text(good)
        ok, why, s = r.checked()
        sc = lambda x: x.get('structuredContent') or {}
        e.update(shown=(shown[0], shown[1].get('refused')), given=(given[0], given[1].get('refused')), by_tool=(by_tool.get('isError'), text_of(by_tool)[:60]),
                 relaxed_card=(relaxed_card.get('isError'), head(text_of(relaxed_card)), sc(relaxed_card).get('outcome'), (sc(relaxed_card).get('verdict') or {}).get('reason_code')),
                 forged=(head(text_of(forged)), sc(forged).get('outcome')), status_meanwhile=(status_meanwhile[0], (status_meanwhile[1].get('runs') or {}).get('total')), restored=head(text_of(restored)), shown_again=shown_again[0],
                 not_a_card=(not_a_card.get('isError'), head(text_of(not_a_card)), sc(not_a_card).get('outcome'), sc(not_a_card).get('met'), 'could not be read as the one the responsible engineer signed' in text_of(not_a_card)),
                 notices_before=notices_before, notices=r.notices(), outcomes=sorted(x['outcome'] for x in s.get('runs', [])), status=s.get('status'), met=s.get('met'), record_verifies=ok, why=why)
        no_baseline = 'UNKNOWN: NO USABLE BASELINE IS HELD FOR THIS JOB'
        checks = {'the changed baseline is not shown, by address or by tool': e['shown'] == (500, 'BASELINE_UNAVAILABLE') and e['given'] == (500, 'BASELINE_UNAVAILABLE') and by_tool.get('isError') is True,
                  'a design that the relaxed card would pass is decided UNKNOWN by the gate, not a pass': e['relaxed_card'] == (False, no_baseline, 'UNKNOWN', 'BASELINE_MISMATCH'),
                  'so is one sent against a relaxed card properly signed by another key, and the runs are counted': e['forged'] == (no_baseline, 'UNKNOWN') and e['status_meanwhile'] == (200, 2),
                  'with the file restored the requirement is shown again and still fails': shown_again[0] == 200 and e['restored'] == FAILED,
                  'all three results were sent to the engineer': notices_before == 3,
                  'known gap, not closed here: a stored card that is no longer a card gives a counted run with no verdict, not a pass, and no notice': e['not_a_card'] == (False, 'UNKNOWN: THE RUN WAS INTERRUPTED', 'INTERRUPTED', False, True)
                      and e['notices'] == 3,
                  'no run met the check, the record verifies and the status is NOT VERIFIED': ok and s.get('met') == 0 and s.get('status') == 'NOT VERIFIED' and e['outcomes'] == ['FAIL', 'INTERRUPTED', 'UNKNOWN', 'UNKNOWN']}
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


TESTS = {'F1': f1, 'F2': f2, 'F3': f3, 'F4': f4, 'F5': f5, 'F6': f6, 'F7': f7, 'F8': f8, 'F9': f9, 'F10': f10, 'F11': f11, 'F12': f12, 'F13': f13, 'F14': f14, 'F15': f15, 'F16': f16}


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
