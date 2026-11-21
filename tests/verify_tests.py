#!/usr/bin/env python3
"""Declared tests R1-R13 for the verification-record plug-in (verify/DECLARED_VERIFY.md states the expected outcomes),
and R14 to R16, added by Amendment 2 (verify/DECLARED_AMEND2.md), R17, added by Amendment 3 (verify/DECLARED_AMEND3.md),
R18, added by Amendment 4 (verify/DECLARED_AMEND4.md), and R19, added by Amendment 6 (verify/DECLARED_AMEND6.md), and R20 and R21, added by Amendment 7 (verify/DECLARED_AMEND7.md), and R22, added by Amendment 8 (verify/DECLARED_AMEND8.md), and R23 and R24, added by Amendment 9 (verify/DECLARED_AMEND9.md), which also restates R18's model of a notice and R22.
R1 to R13 are as they were declared.

    verify_tests.py [R1 R5 ...]       all twenty-four by default; writes outputs/verify_tests.json; exits 1 if any test fails

Each test makes a fresh deployment (verify/deploy.py: new keys, the released witness service and gate host under mutual
TLS, the gate host loading verify_tools), baselines the self-test fixture in tests/verify_case/ as the responsible
engineer would, and then acts as the assistant through verify_client.py, exactly as an assistant's shell would.  The
independent measures are the gate tool's ledger and the engineer's inbox, both outside every PLEA store.

A test passes only if every named check in it is true.  A harness or service error is a failed test.
"""
import itertools
import json
import os
import pathlib
import re
import shutil
import copy
import http.client
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

HERE = pathlib.Path(__file__).resolve().parent
GATEWAY = HERE.parent
sys.path.insert(0, str(GATEWAY)); sys.path.insert(0, str(GATEWAY / 'verify'))
import baseline as B                    # noqa: E402
import check_record                     # noqa: E402
import deploy                           # noqa: E402
import verify_ctl                       # noqa: E402
import verify_client                    # noqa: E402  (Amendment 9)
import front_door                       # noqa: E402  (Amendment 9: its view of the requirement, in R23)
import checkpoints                      # noqa: E402  (Amendment 10)
import courier                          # noqa: E402  (Amendment 11)
from plea_gateway import tls as TLS     # noqa: E402  (Amendment 10)
from plea_gateway.receipts import Signer, sign_checkpoint   # noqa: E402  (Amendment 10)
from plea_gateway import AuthorityError, Store      # noqa: E402
from verify_record import Key, canonical, envelope_message, load_envelope, sign_envelope   # noqa: E402

OUT = GATEWAY / 'outputs' / 'verify_tests'
CASE = HERE / 'verify_case'
PY = sys.executable
BAD = {'material': 'PA66-GF30', 'wall_mm': 3, 'mode': 'normal'}          # 180 C against 200 C: must fail
GOOD = {'material': 'PPS-GF40', 'wall_mm': 3, 'mode': 'normal'}         # 220 C: meets the check


def draft(**changes) -> dict:
    d = json.loads((CASE / 'card.json').read_text())
    d['job'] = uuid.uuid4().hex                 # every baseline in every run is distinct, so its budget is new
    d.update(changes)
    return d


class Run:
    """One deployment with one baseline and one assistant workspace."""

    def __init__(self, tag: str, crash_at: str | None = None, card: dict | None = None):
        self.s = deploy.Services(OUT / tag).start(crash_at)
        try:
            self.env = self.s.baseline(CASE, card or draft())
        except BaseException:
            self.s.stop(); raise                                         # a test that cannot baseline leaves no service behind (Amendment 12)
        self.h = self.env['baseline_sha256']
        self.ws = OUT / tag / 'workspace'
        self.cfg = self.s.client_config(self.ws, self.h)

    def submit(self, design):
        return self.s.submit(self.cfg, design)

    def record(self, h=None, ws=None):
        return self.s.record(h or self.h, [(ws or self.ws) / '.verify' / 'submissions.jsonl'])

    def checked(self, design=None, h=None):
        ok, checks, s = check_record.verify(self.record(h), self.s.keys, design)
        return ok, [f'{n} {t}: {d}' for n, t, good, d in checks if not good], s

    def calls(self) -> int:
        return len(self.s.ledger('called'))

    def stop(self):
        self.s.stop()


def head(out: str) -> str:
    return out.strip().splitlines()[0] if out.strip() else ''


# ====================================================================== the tests
def r1():
    """A design that does not meet the requirement gets a signed FAIL with the reason, kept on the record and sent to the engineer."""
    r = Run('R1'); e = {}
    try:
        code, out = r.submit(BAD)
        ok, why, s = r.checked()
        notice = (r.s.home / 'inbox' / r.h[:16] / r.s.inbox(r.h)[0]).read_text() if r.s.inbox(r.h) else ''
        run = s['runs'][0] if s.get('runs') else {}
        e.update(exit=code, first_line=head(out), says_values='achieved 180 C' in out and 'at least 200 C' in out, record_verifies=ok, why=why, status=s.get('status'),
                 run=dict(outcome=run.get('outcome'), reason=run.get('reason_code'), criteria=run.get('criteria')), notices=r.s.inbox(r.h), notice_head=notice.splitlines()[:4])
        checks = {'the assistant is told FAIL, with the required and achieved values (exit status 2)': code == 2 and head(out) == 'FAIL: REQUIREMENT NOT MET' and e['says_values'],
                  'the record holds the FAIL with reason LIMIT_NOT_MET, 180 against 200, margin -20': run.get('outcome') == 'FAIL' and run.get('reason_code') == 'LIMIT_NOT_MET'
                      and [(c['achieved'], c['limit'], c['margin'], c['met']) for c in run.get('criteria', [])] == [('180', '200', '-20', False)],
                  'the record verifies offline and its status is NOT VERIFIED': ok and s.get('status') == 'NOT VERIFIED',
                  'one notice is in the engineer\'s inbox, from the service, naming the failure': len(r.s.inbox(r.h)) == 1 and 'From: the verification service (not the assistant)' in notice
                      and 'FAIL: REQUIREMENT NOT MET' in notice and 'To: D. Marsh' in notice}
    finally:
        r.stop()
    return checks, e


def r2():
    """The same design sent again returns the same verdict: one run, one notice."""
    r = Run('R2'); e = {}
    try:
        a = r.submit(BAD); b = r.submit(BAD)
        ok, why, s = r.checked()
        e.update(first=(a[0], head(a[1])), second=(b[0], head(b[1])), tool_calls=r.calls(), notices=len(r.s.inbox(r.h)), official_runs=s.get('official_runs'), record_verifies=ok, why=why)
        checks = {'both answers are the same FAIL': a[0] == b[0] == 2 and head(a[1]) == head(b[1]) == 'FAIL: REQUIREMENT NOT MET',
                  'the check ran once and one notice was sent': r.calls() == 1 and e['notices'] == 1,
                  'the record shows one official run': ok and s.get('official_runs') == 1}
    finally:
        r.stop()
    return checks, e


def r3():
    """A design outside the baselined design space is a FAIL, and the check is not run on it."""
    r = Run('R3'); e = {}
    try:
        tries = {'material off the approved list': {'material': 'PEEK', 'wall_mm': 3, 'mode': 'normal'}, 'number outside its bounds': {'material': 'PPS-GF40', 'wall_mm': 9, 'mode': 'normal'},
                 'an extra parameter': {'material': 'PPS-GF40', 'wall_mm': 3, 'mode': 'normal', 'coating': 'ceramic'}, 'a parameter left out': {'material': 'PPS-GF40', 'mode': 'normal'}}
        got = {k: r.submit(d) for k, d in tries.items()}
        ok, why, s = r.checked()
        e.update(answers={k: (c, head(o)) for k, (c, o) in got.items()}, reasons=[x['reason_code'] for x in s.get('runs', [])], achieved=[[c['achieved'] for c in x['criteria']] for x in s.get('runs', [])],
                 notices=len(r.s.inbox(r.h)), status=s.get('status'), record_verifies=ok, why=why)
        checks = {'each is answered FAIL: DESIGN OUTSIDE THE BASELINE (exit status 2)': all(c == 2 and head(o) == 'FAIL: DESIGN OUTSIDE THE BASELINE' for c, o in got.values()),
                  'the record holds four FAILs with that reason and no achieved value': e['reasons'] == ['DESIGN_OUTSIDE_BASELINE'] * 4 and all(a == [None] for a in e['achieved']),
                  'each was sent to the engineer and the status is NOT VERIFIED': e['notices'] == 4 and ok and s.get('status') == 'NOT VERIFIED'}
    finally:
        r.stop()
    return checks, e


def r4():
    """A design that meets the check after two that did not: met for that design only, and the failures stay on the record."""
    r = Run('R4'); e = {}
    try:
        codes = [r.submit(d)[0] for d in (BAD, {'material': 'PA66-GF30', 'wall_mm': 4, 'mode': 'normal'}, GOOD)]
        ok, why, s = r.checked(GOOD)
        _, _, other = r.checked({'material': 'PPS-GF40', 'wall_mm': 3.5, 'mode': 'normal'}); _, _, failed = r.checked(BAD)
        text = check_record.render(ok, [], s)
        e.update(exits=codes, status=s.get('status'), counts=(s.get('official_runs'), s.get('met'), s.get('not_met')), open=s.get('open'), released_good=s.get('released'),
                 released_other=other.get('released'), released_failed=failed.get('released'), record_verifies=ok, why=why, notices=len(r.s.inbox(r.h)))
        checks = {'the three runs answer FAIL, FAIL, met (exit 2, 2, 0)': codes == [2, 2, 0],
                  'the status is DECLARED CHECK MET with both failures still counted': ok and s.get('status') == 'DECLARED CHECK MET' and e['counts'] == (3, 1, 2) and 'after 3 official runs (2 not met' in text,
                  'it is met for that exact design only': s['released']['met'] is True and other['released'] == dict(other['released'], met=False, seen=False) and failed['released']['met'] is False and failed['released']['seen'] is True,
                  'the two failures were sent to the engineer and are still open': e['notices'] == 2 and s.get('open') == 2}
    finally:
        r.stop()
    return checks, e


def r5():
    """A check, a data file or a card changed after baselining gives UNKNOWN, never a pass."""
    r = Run('R5'); e = {}
    try:
        d = r.s.home / 'baselines' / r.h
        data = d / 'materials.csv'; original = data.read_text()
        data.write_text(original.replace('PA66-GF30,180', 'PA66-GF30,260'))                       # make the failing material look good
        after_data = r.submit(BAD); data.write_text(original)
        chk = d / 'check.py'; code = chk.read_text(); chk.write_text(code.replace('value = float(', 'value = 999 + 0 * float('))
        after_check = r.submit({'material': 'PA66-GF30', 'wall_mm': 2.5, 'mode': 'normal'}); chk.write_text(code)
        env = json.loads((d / 'baseline.json').read_text()); good = json.dumps(env, indent=1) + '\n'
        env['card']['criteria'][0]['limit'] = '150'; (d / 'baseline.json').write_text(json.dumps(env))   # relax the limit in the stored card
        after_card = r.submit({'material': 'PA66-GF30', 'wall_mm': 2.6, 'mode': 'normal'})
        other = Key(); env2 = json.loads(good); env2['card']['criteria'][0]['limit'] = '150'; env2['card']['responsible_engineer']['key'] = other.public_hex
        env2['baseline_sha256'] = B.card_hash(env2['card']); env2['signature'] = {'signer': other.public_hex, 'signature': other.sign(envelope_message(env2['card'], env2['controls_run']))}
        (d / 'baseline.json').write_text(json.dumps(env2))                                            # a relaxed card properly signed by someone else's key
        after_forged = r.submit({'material': 'PA66-GF30', 'wall_mm': 2.7, 'mode': 'normal'})
        (d / 'baseline.json').write_text(good)
        restored = r.submit({'material': 'PA66-GF30', 'wall_mm': 2.8, 'mode': 'normal'})
        ok, why, s = r.checked()
        e.update(data=(after_data[0], head(after_data[1])), check=(after_check[0], head(after_check[1])), card=(after_card[0], head(after_card[1])), forged=(after_forged[0], head(after_forged[1])),
                 restored=(restored[0], head(restored[1])), outcomes=[(x['outcome'], x['reason_code']) for x in s.get('runs', [])], status=s.get('status'), record_verifies=ok, why=why, notices=len(r.s.inbox(r.h)))
        unknown = 'UNKNOWN: THE CHECK OR ITS DATA NO LONGER MATCHES THE BASELINE'
        checks = {'changed data gives UNKNOWN (exit status 3), not a pass': after_data == (3, after_data[1]) and head(after_data[1]) == unknown,
                  'a changed check gives UNKNOWN': after_check[0] == 3 and head(after_check[1]) == unknown,
                  'a stored card with a relaxed limit is not used': after_card[0] == 3 and after_forged[0] == 3,
                  'with the files restored the same requirement still fails': restored[0] == 2 and head(restored[1]) == 'FAIL: REQUIREMENT NOT MET',
                  'no run met the check, the record verifies and the status is NOT VERIFIED': ok and s.get('met') == 0 and s.get('status') == 'NOT VERIFIED'
                      and sorted(o for o, _ in e['outcomes']) == ['FAIL', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN'],
                  'all five results were sent to the engineer': e['notices'] == 5}
    finally:
        r.stop()
    return checks, e


def r6():
    """A check that crashes, prints rubbish, returns not-a-number, zero or an absurd value, or hangs, gives UNKNOWN with its reason."""
    r = Run('R6'); e = {}
    try:
        want = {'crash': 'CHECK_ERROR', 'garbage': 'CHECK_OUTPUT_INVALID', 'nan': 'CHECK_OUTPUT_INVALID', 'zero': 'RESULT_IMPLAUSIBLE', 'huge': 'RESULT_IMPLAUSIBLE'}
        got = {m: r.submit({'material': 'PPS-GF40', 'wall_mm': 3, 'mode': m}) for m in want}
        ok, why, s = r.checked()
        reasons = {x['design']['mode']: (x['outcome'], x['reason_code']) for x in s.get('runs', [])}
        card = r.env['card']; old = B.CHECK_TIMEOUT; B.CHECK_TIMEOUT = 1.0
        try:
            t0 = time.time(); hang = B.evaluate(r.s.home / 'baselines' / r.h, card, {'material': 'PPS-GF40', 'wall_mm': 3, 'mode': 'hang'}); took = time.time() - t0
        finally:
            B.CHECK_TIMEOUT = old
        e.update(exits={m: c for m, (c, _) in got.items()}, reasons=reasons, hang=(hang['verdict'], hang['reason_code'], round(took, 1)), status=s.get('status'), notices=len(r.s.inbox(r.h)), record_verifies=ok, why=why)
        checks = {'each answers UNKNOWN (exit status 3)': all(c == 3 and head(o).startswith('UNKNOWN') for c, o in got.values()),
                  'the record gives each its reason': reasons == {m: ('UNKNOWN', code) for m, code in want.items()},
                  'a check that hangs is stopped and is UNKNOWN': hang['verdict'] == 'UNKNOWN' and hang['reason_code'] == 'CHECK_ERROR' and took < 10,
                  'a material that would have passed is not a pass when the check misbehaves': s.get('met') == 0 and s.get('status') == 'NOT VERIFIED' and ok,
                  'every UNKNOWN was sent to the engineer': e['notices'] == 5}
    finally:
        r.stop()
    return checks, e


def r7():
    """The service dying part-way through a run leaves it counted, without a verdict, and never run again."""
    r = Run('R7', crash_at='verify_running'); e = {}
    try:
        during = r.submit(GOOD); time.sleep(0.3); exit_code = r.s.procs['host'].poll()
        r.s.stop_host(); r.s.start_host()
        again = r.submit(GOOD); again2 = r.submit(GOOD)
        other = r.submit({'material': 'PPS-GF40', 'wall_mm': 2.5, 'mode': 'normal'})
        ok, why, s = r.checked(GOOD)
        e.update(during=(during[0], head(during[1])), host_exit=exit_code, again=(again[0], head(again[1])), again2=again2[0], tool_calls_for_design=sum(1 for x in r.s.ledger('called') if x.get('design') == GOOD),
                 verdicts_for_design=sum(1 for x in r.s.ledger('verdict') if x.get('design_sha256') == B.design_hash(GOOD)), outcomes=sorted(x['outcome'] for x in s.get('runs', [])),
                 released=s.get('released'), other=other[0], record_verifies=ok, why=why)
        checks = {'the host died during the run (exit 137) and the assistant was not told it passed': exit_code == 137 and during[0] in (3, 4),
                  'asked again, twice, the answer is UNKNOWN: interrupted (exit status 3)': again[0] == again2[0] == 3 and head(again[1]) == head(again2[1]) == 'UNKNOWN: THE RUN WAS INTERRUPTED',
                  'the check was started once for that design and never produced a verdict': e['tool_calls_for_design'] == 1 and e['verdicts_for_design'] == 0,
                  'the record shows it INTERRUPTED and counted, and that design is not verified': ok and e['outcomes'] == ['INTERRUPTED', 'PASS'] and s['released']['met'] is False,
                  'a different design can still be verified': other == (0, other[1])}
    finally:
        r.stop()
    return checks, e


def r8():
    """A baseline is refused unless its check is seen to fail a bad design and pass a good one."""
    s = deploy.Services(OUT / 'R8'); e = {}
    try:
        def attempt(d):
            try:
                s.baseline(CASE, d); return 'baselined'
            except B.BaselineInvalid as exc:
                return str(exc)[:220]
        base = draft()
        no_fail = draft(controls=[c for c in base['controls'] if c['expect'] == 'PASS'])
        no_pass = draft(controls=[c for c in base['controls'] if c['expect'] == 'FAIL'])
        wrong_fail = draft(controls=[dict(base['controls'][0], design=GOOD), base['controls'][1]])       # a "must fail" design that passes
        wrong_pass = draft(controls=[base['controls'][0], dict(base['controls'][1], design=BAD)])        # a "must pass" design that fails
        loose = draft(criteria=[dict(base['criteria'][0], limit='100')])                                 # a limit so loose the must-fail control passes
        no_limits = draft(); no_limits['check'] = dict(base['check'], stated_limits=[])
        no_range = draft(criteria=[{k: v for k, v in base['criteria'][0].items() if k != 'plausible'}])
        got = {'no failing control': attempt(no_fail), 'no passing control': attempt(no_pass), 'must-fail control passes': attempt(wrong_fail), 'must-pass control fails': attempt(wrong_pass),
               'limit so loose nothing fails': attempt(loose), 'no stated limits of the check': attempt(no_limits), 'no plausible range': attempt(no_range), 'the fixture as written': attempt(draft())}
        e.update(got=got, baselines_stored=len(list((s.home / 'baselines').iterdir())))
        checks = {'seven defective baselines are refused, each with its reason': all(v != 'baselined' for k, v in got.items() if k != 'the fixture as written')
                      and 'must FAIL' in got['no failing control'] and 'expected to FAIL and gave PASS' in got['must-fail control passes'] and 'expected to PASS and gave FAIL' in got['must-pass control fails']
                      and 'expected to FAIL and gave PASS' in got['limit so loose nothing fails'],
                  'the sound one is baselined, and only it is stored': got['the fixture as written'] == 'baselined' and e['baselines_stored'] == 1}
    finally:
        s.stop()
    return checks, e


def _leaves(node, path=()):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _leaves(v, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _leaves(v, path + (i,))
    else:
        yield path, node


def _edited(record: dict, path: tuple, value):
    copy = json.loads(json.dumps(record)); node = copy
    for p in path[:-1]:
        node = node[p]
    if isinstance(value, bool):          new = not value
    elif isinstance(value, (int, float)): new = value + 1
    elif isinstance(value, str):         new = (('1' if value[-1] != '1' else '2') if value else 'x').join((value[:-1], ''))
    else:                                new = 'x'                                    # null
    node[path[-1]] = new
    return copy


def r9():
    """The record verifies offline; an edited one does not, even when re-signed with the engineer's key."""
    r = Run('R9'); e = {}
    try:
        for d in (BAD, {'material': 'PEEK', 'wall_mm': 3, 'mode': 'normal'}, {'material': 'PPS-GF40', 'wall_mm': 3, 'mode': 'crash'}, GOOD):
            r.submit(d)
        aid = [a['aid'] for a in r.record()['attempts'] if a['outcome'] == 'FAIL'][0]
        verify_ctl.acknowledge(r.s.home, r.h, aid, 'Redesign in PPS-GF40 and re-verify.', r.s.engineer)
        record = r.record(); ok, checks, s = check_record.verify(record, r.s.keys)
        path = OUT / 'R9' / 'record.json'; path.write_text(json.dumps(record, indent=1))
        k = r.s.keys
        cli = subprocess.run([PY, '-B', str(GATEWAY / 'verify' / 'check_record.py'), str(path), '--witness-key', k['witness'], '--gate-key', k['gate'], '--engineer-key', k['engineer']], capture_output=True, text=True)
        unpinned = subprocess.run([PY, '-B', str(GATEWAY / 'verify' / 'check_record.py'), str(path)], capture_output=True, text=True)
        leaves = list(_leaves(record))
        survived = ['.'.join(map(str, p)) for p, v in leaves if check_record.verify(_edited(record, p, v), r.s.keys)[0]]
        # an insider who holds the engineer's key but not the witness's or the gate's: edit one value, then re-sign the baseline and the record
        signer, resigned = r.s.engineer, []
        for p, v in leaves:
            if p[0] == 'signature' or p[:2] == ('baseline', 'signature'):
                continue
            body = {x: y for x, y in _edited(record, p, v).items() if x != 'signature'}
            env = body['baseline']
            env['signature'] = {'signer': signer.public_hex, 'signature': signer.sign(envelope_message(env['card'], env['controls_run']))}
            forged = dict(body, signature={'signer': signer.public_hex, 'signature': signer.sign(canonical(body).encode())})
            if check_record.verify(forged, r.s.keys)[0]:
                resigned.append('.'.join(str(x) for x in p if not isinstance(x, int)))
        wrong_key = check_record.verify(record, dict(r.s.keys, engineer=Key().public_hex))[0]
        e.update(verifies=ok, cli_exit=cli.returncode, cli_says=[l for l in cli.stdout.splitlines() if l.startswith(('RECORD', 'STATUS'))], unpinned_exit=unpinned.returncode,
                 unpinned_says=[l[:40] for l in unpinned.stdout.splitlines() if l.startswith('RECORD')], values=len(leaves), edits_that_still_verify=survived,
                 resigned_edits_that_verify=sorted(set(resigned)), outcomes=sorted(x['outcome'] for x in s['runs']), open=s['open'])
        checks = {'the record verifies, by library and by command line': ok and cli.returncode == 0 and 'RECORD VERIFIED against the keys given.' in cli.stdout,
                  'without keys given it says consistent, not verified': unpinned.returncode == 0 and 'RECORD CONSISTENT' in unpinned.stdout and 'RECORD VERIFIED' not in unpinned.stdout,
                  'every single-value edit fails': not survived and len(leaves) > 300,
                  'a wrong engineer key fails': not wrong_key,
                  're-signed with the engineer\'s key, edits verify only where the engineer alone is the source': e['resigned_edits_that_verify'] == RESIGNED_EXPECTED}
    finally:
        r.stop()
    return checks, e


RESIGNED_EXPECTED = ['as_of.time', 'baseline.controls_run.criteria.achieved']      # the time of signing, and a control's number where the edit does not change its verdict


def r10():
    """A requirement changes only as a new, signed baseline that says what it replaced and what had failed."""
    r = Run('R10'); e = {}
    try:
        first = r.submit(BAD)
        relaxed = draft(); relaxed['requirement'] = dict(relaxed['requirement'], revision='B', statement='The housing shall withstand continuous operation at 170 C.')
        relaxed['criteria'] = [dict(relaxed['criteria'][0], limit='170')]
        relaxed['controls'] = [{'name': 'PA66 must now pass at 170 C', 'design': BAD, 'expect': 'PASS'},
                               {'name': 'a 160 C material must fail', 'design': {'material': 'PA66-GF30', 'wall_mm': 3, 'mode': 'zero'}, 'expect': 'FAIL'}]
        try:
            verify_ctl.revise(r.s.home, CASE, relaxed, r.s.engineer, r.h, '   '); no_reason = 'accepted'
        except B.BaselineInvalid as exc:
            no_reason = str(exc)
        relaxed['controls'][1] = {'name': 'PEEK-free control: an unlisted material fails the lookup', 'design': {'material': 'PA66-GF30', 'wall_mm': 3, 'mode': 'crash'}, 'expect': 'FAIL'}
        try:
            verify_ctl.revise(r.s.home, CASE, relaxed, r.s.engineer, r.h, 'Customer lowered the operating temperature (CR-17).'); bad_control = 'accepted'
        except B.BaselineInvalid as exc:
            bad_control = str(exc)[:80]
        data = (CASE / 'materials.csv').read_text()
        src = OUT / 'R10' / 'case_b'; src.mkdir()
        (src / 'check.py').write_text((CASE / 'check.py').read_text()); (src / 'materials.csv').write_text(data + 'PA6,160\n')
        relaxed['controls'][1] = {'name': 'PA6 (160 C) must fail at 170 C', 'design': {'material': 'PA6', 'wall_mm': 3, 'mode': 'normal'}, 'expect': 'FAIL'}
        env_b = verify_ctl.revise(r.s.home, src, relaxed, r.s.engineer, r.h, 'Customer lowered the operating temperature (CR-17).')
        on_old = r.submit({'material': 'PA66-GF30', 'wall_mm': 3.5, 'mode': 'normal'})                 # the superseded baseline takes no more runs
        calls_before = r.calls()
        ws_b = OUT / 'R10' / 'workspace_b'; cfg_b = r.s.client_config(ws_b, env_b['baseline_sha256'])
        on_new = r.s.submit(cfg_b, BAD)
        ok_a, why_a, s_a = r.checked()
        ok_b, checks_b, s_b = check_record.verify(r.s.record(env_b['baseline_sha256'], [ws_b / '.verify' / 'submissions.jsonl']), r.s.keys)
        text_b = check_record.render(ok_b, checks_b, s_b)
        e.update(first=first[0], no_reason=no_reason, weak_control=bad_control, on_old=(on_old[0], head(on_old[1])), on_new=(on_new[0], head(on_new[1])), supersedes=env_b['card']['supersedes'],
                 rev_a=dict(verifies=ok_a, status=s_a.get('status'), not_met=s_a.get('not_met')), rev_b=dict(verifies=ok_b, status=s_b.get('status')),
                 headline=[l.strip()[:100] for l in text_b.splitlines() if 'CHANGED AFTER THE EVENT' in l])
        sup = env_b['card']['supersedes'] or {}
        checks = {'a revision with no reason is refused': 'needs a reason' in no_reason,
                  'the old baseline takes no further runs (exit status 4, nothing run)': on_old[0] == 4 and 'REFUSED: this baseline has been stopped' in on_old[1] and r.calls() - calls_before == 1,
                  'the new card says what it replaced and what had failed, counted by the console': (sup.get('baseline_sha256'), sup.get('revision'), sup.get('official_runs'), sup.get('not_met')) == (r.h, 'A', 1, 1)
                      and sup.get('reason') == 'Customer lowered the operating temperature (CR-17).',
                  'the design that failed on A meets the check on B, and B\'s record is headed CHANGED AFTER THE EVENT': on_new[0] == 0 and ok_b and s_b.get('status') == 'DECLARED CHECK MET' and len(e['headline']) == 1,
                  'the old record still verifies and still shows the failure': ok_a and s_a.get('status') == 'NOT VERIFIED' and s_a.get('not_met') == 1}
    finally:
        r.stop()
    return checks, e


def r11():
    """What the assistant's side holds cannot do the engineer's part."""
    r = Run('R11'); e = {}
    try:
        local = Store(deploy.LOCAL_DSN); root = B.root_for(r.env['card'])
        try:
            local.new_root('REQ-X/A/' + uuid.uuid4().hex, 10, 0); provision = 'provisioned'
        except AuthorityError:
            provision = 'refused'
        except Exception as exc:
            provision = f'refused ({type(exc).__name__})'
        try:
            d, _ = local.apply(root, ('STOP',)); stop = f'{d.kind} {d.code}'
        except AuthorityError:
            stop = 'refused'
        except Exception as exc:
            stop = f'refused ({type(exc).__name__})'
        still_runs = r.submit(BAD)
        # a relaxed baseline of the assistant's own making, properly signed with its own key, used as its client's copy
        mine = Key(); env = json.loads((r.ws / '.verify' / 'baseline.json').read_text())
        env['card']['criteria'][0]['limit'] = '150'; env['card']['responsible_engineer']['key'] = mine.public_hex
        env['baseline_sha256'] = B.card_hash(env['card']); env['signature'] = {'signer': mine.public_hex, 'signature': mine.sign(envelope_message(env['card'], env['controls_run']))}
        ws2 = OUT / 'R11' / 'workspace_forged'; cfg2 = r.s.client_config(ws2, r.h)
        (ws2 / '.verify' / 'baseline.json').write_text(json.dumps(env))
        pinned_engineer = r.s.submit(cfg2, BAD)                                                   # the client still pins the real engineer's key
        cfg = json.loads(cfg2.read_text()); cfg['engineer_key'] = mine.public_hex; cfg2.write_text(json.dumps(cfg))
        own_key_pinned = r.s.submit(cfg2, BAD)                                                    # the client now trusts the forger's key: is anything run?
        calls = r.calls(); ok, why, s = r.checked()
        # the control credential in the wrong hands as well: a budget is provisioned for the forger's baseline and its files are put where the gate looks
        d2 = r.s.home / 'baselines' / env['baseline_sha256']; d2.mkdir()
        for name in ('check.py', 'materials.csv'):
            shutil.copyfile(CASE / name, d2 / name)
        (d2 / 'baseline.json').write_text(json.dumps(env))
        Store(verify_ctl.CONTROL_DSN).new_root(B.root_for(env['card']), 10, 0)
        with_control = r.s.submit(cfg2, BAD)                                                     # 180 C against the forger's limit of 150 C would pass
        e.update(forged_baseline_with_a_budget=(with_control[0], head(with_control[1])[:70]))
        e.update(provision_with_gateway_credential=provision, stop_with_gateway_credential=stop, still_runs=still_runs[0], forged_copy=(pinned_engineer[0], head(pinned_engineer[1])[:70]),
                 forged_copy_own_key=(own_key_pinned[0], head(own_key_pinned[1])[:70]), tool_calls=calls, official_runs=s.get('official_runs'), status=s.get('status'), record_verifies=ok, why=why)
        checks = {'the gateway credential cannot provision a budget or stop one': provision.startswith('refused') and stop.startswith('refused') and still_runs[0] == 2,
                  'a relaxed baseline signed by another key is not accepted by the client': pinned_engineer[0] == 4,
                  'even trusting that key, nothing is run: no budget exists for a baseline the engineer did not provision': own_key_pinned[0] == 4 and 'no budget' in own_key_pinned[1] and calls == 1,
                  'the real record is unchanged: one run, NOT VERIFIED': ok and s.get('official_runs') == 1 and s.get('status') == 'NOT VERIFIED',
                  'even with a budget provisioned for it, a baseline the pinned engineer did not sign gets UNKNOWN, not a pass': with_control[0] == 3 and head(with_control[1]).startswith('UNKNOWN')}
    finally:
        r.stop()
    return checks, e


def r12():
    """The engineer's disposition of a failure is signed, shown on the record, and cannot be made by anyone else."""
    r = Run('R12'); e = {}
    try:
        r.submit(BAD); r.submit(GOOD)
        rec = r.record(); fail = next(a['aid'] for a in rec['attempts'] if a['outcome'] == 'FAIL'); met = next(a['aid'] for a in rec['attempts'] if a['outcome'] == 'PASS')
        _, _, before = r.checked()
        ack = verify_ctl.acknowledge(r.s.home, r.h, fail, 'Rejected. Redesign in PPS-GF40.', r.s.engineer)
        try:
            verify_ctl.acknowledge(r.s.home, r.h, met, 'ok', r.s.engineer); on_pass = 'accepted'
        except B.BaselineInvalid as exc:
            on_pass = str(exc)[:60]
        ok, why, after = r.checked()
        other = Key(); t = '2026-01-01T00:00:00Z'
        from verify_record import acknowledgement_message
        forged = {'aid': fail, 'outcome': 'FAIL', 'disposition': 'Accepted as is.', 'time': t, 'signer': other.public_hex,
                  'signature': other.sign(acknowledgement_message(B.root_for(r.env['card']), fail, 'FAIL', 'Accepted as is.', t))}
        with (r.s.home / 'baselines' / r.h / 'acknowledgements.jsonl').open('a') as f:
            f.write(json.dumps(forged) + '\n')
        ok_forged, why_forged, _ = r.checked()
        e.update(open_before=before.get('open'), open_after=after.get('open'), acknowledged=[x['acknowledged'] for x in after['runs'] if x['outcome'] == 'FAIL'], on_pass=on_pass,
                 verifies=ok, why=why, with_forged_acknowledgement=ok_forged, forged_why=why_forged, ack_signer_is_engineer=ack['signer'] == r.s.keys['engineer'])
        checks = {'before the disposition the failure is open; after it, acknowledged': before.get('open') == 1 and after.get('open') == 0 and e['acknowledged'] == [True] and ok,
                  'a run that met the check takes no disposition': 'needs no disposition' in on_pass,
                  'a disposition signed by another key makes the record fail': not ok_forged and any('not signed by the engineer' in w for w in why_forged)}
    finally:
        r.stop()
    return checks, e


def r13():
    """A verdict that does not follow from its own numbers is rejected, even when the gate and the engineer have both signed it."""
    import hashlib
    r = Run('R13'); e = {}
    try:
        r.submit(BAD)
        record = r.record(); honest = check_record.verify(record, r.s.keys)[0]
        forged = json.loads(json.dumps(record)); a = forged['attempts'][0]; res = a['result']
        res['verdict'], res['reason_code'], res['criteria'][0]['met'] = 'PASS', 'MET', True          # 180 against a limit of 200, now called met
        digest = hashlib.sha256(canonical(res).encode()).hexdigest()
        for item in a['evidence']:
            ev = item['evidence']
            if ev.get('claim') == 'EFFECT':                                                         # the gate's own key signs the altered verdict
                ev['result_digest'] = digest; ev['signature'] = r.s.gate._key.sign(check_record.evidence_message(ev)).hex()
        a['outcome'] = 'PASS'
        body = {k: v for k, v in forged.items() if k != 'signature'}
        forged = dict(body, signature={'signer': r.s.engineer.public_hex, 'signature': r.s.engineer.sign(canonical(body).encode())})
        ok, checks, s = check_record.verify(forged, r.s.keys)
        failed = [f'{n} {t}: {d}' for n, t, good, d in checks if not good]
        e.update(honest_record_verifies=honest, forged_record_verifies=ok, failed=failed, status=s.get('status'))
        checks = {'the honest record verifies': honest,
                  'the altered verdict, signed by the gate key and the engineer key, fails, and only at the re-derived verdict': not ok and len(failed) == 1 and failed[0].startswith('6 ') and 'recorded as met' in failed[0],
                  'its status is NOT VERIFIED': s.get('status') == 'NOT VERIFIED'}
    finally:
        r.stop()
    return checks, e


def r14():
    """A stored baseline that is no longer a card at all gives a signed UNKNOWN and a notice, like any other changed baseline: never an interrupted run, never a pass."""
    r = Run('R14'); e = {}
    try:
        stored = r.s.home / 'baselines' / r.h / 'baseline.json'; good = stored.read_text()

        def changed(fn):
            env = json.loads(good); fn(env); return json.dumps(env)

        def drop(env): del env['card']['load_case']
        def retype(env): env['card']['requirement'] = ['REQ-SELFTEST-001', 'A']
        def criterion(env): env['card']['criteria'][0] = 'service temperature at least 150 C'
        def space(env): env['card']['design_space']['material'] = 'anything'
        def signature(env): env['signature'] = 'signed'
        def surrogate(env): env['card']['design_space'] = {'wall\ud800': {}}
        def nul(env): env['card']['criteria'] = [dict(env['card']['criteria'][0], id='a\u0000b')] * 2
        def lines(env): env['card']['design_space'] = {'wall_mm\n\nDECLARED CHECK MET\n': {}}
        mark = 'ZZ-TAKEN-FROM-THE-STORED-FILE'
        def quoted(env): env['card']['criteria'] = [dict(env['card']['criteria'][0], id=mark)] * 2          # the rule this breaks names the id in its message
        cases = {'a required field removed': changed(drop), 'the requirement turned into a list': changed(retype), 'a criterion turned into text': changed(criterion),
                 'a design-space rule turned into text': changed(space), 'the signature turned into text': changed(signature), 'a file nested a hundred thousand deep': '{"card": ' + '[' * 100000 + ']' * 100000 + '}',
                 'a name holding half a surrogate pair': changed(surrogate), 'a repeated name holding a NUL': changed(nul), 'a name holding line breaks and a headline': changed(lines),
                 'a repeated name that the broken rule would quote': changed(quoted),
                 'an empty file': '', 'text that is not JSON': 'the limit is 150 C', 'a JSON list': '[1, 2, 3]'}
        got = {}
        walls = [2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 3.1, 3.2, 3.3, 3.4]
        for (name, text), wall in zip(cases.items(), walls, strict=True):
            stored.write_text(text)
            got[name] = r.submit({'material': 'PPS-GF40', 'wall_mm': wall, 'mode': 'normal'})                 # a design that would pass, a fresh one each time
        stored.unlink(); got['the file removed'] = r.submit({'material': 'PPS-GF40', 'wall_mm': 3.95, 'mode': 'normal'})
        stored.write_text(good)
        host_alive = r.s.procs['host'].poll() is None
        box = r.s.home / 'inbox' / r.h[:16]
        notices = [p.read_text() for p in sorted(box.glob('*.txt'))] if box.exists() else []
        restored = r.submit(BAD); passes = r.submit(GOOD)
        ok, why, s = r.checked(GOOD)
        runs = s.get('runs', [])
        e.update(answers={k: (c, head(o)) for k, (c, o) in got.items()}, host_alive=host_alive, restored=(restored[0], head(restored[1])), passes=(passes[0], head(passes[1])),
                 outcomes=sorted((x['outcome'], str(x['reason_code'])) for x in runs), notices=len(notices), empty_notices=sum(1 for t in notices if not t.strip()),
                 forged_lines=sum(1 for t in notices for l in t.splitlines() if l.strip() == 'DECLARED CHECK MET'), tool_calls=r.calls(), verdict_lines=len(r.s.ledger('verdict')),
                 quoted_from_the_file=sum(mark in t for t in [o for _, o in got.values()] + [str(x.get('detail')) for x in runs] + notices),
                 service_path_shown=sum(str(r.s.home)[:30] in t for t in [o for _, o in got.values()] + [str(x.get('detail')) for x in runs] + notices),
                 reasons_given=sorted({x['detail'].split(': ', 1)[-1] for x in runs if 'is not a baseline card' in x['detail']}), status=s.get('status'), met=s.get('met'), unknown=s.get('unknown'), record_verifies=ok, why=why)
        unknown = 'UNKNOWN: THE VERIFICATION SERVICE HOLDS NO USABLE COPY OF THIS BASELINE'     # Amendment 4: the first client's first line when the gate holds no usable copy of
        # the card.  It was 'UNKNOWN: THE CHECK OR ITS DATA NO LONGER MATCHES THE BASELINE', which is not what had happened.
        checks = {'each of fourteen unusable stored baselines is answered UNKNOWN (exit status 3), not interrupted and not a pass': len(got) == 14 and all(c == 3 and head(o) == unknown for c, o in got.values()),
                  'the tool returned a verdict every time and the gate host kept running': e['verdict_lines'] == e['tool_calls'] == 16 and host_alive,
                  'the record holds fourteen UNKNOWNs with the reason BASELINE_MISMATCH, and no run without a verdict': e['outcomes'].count(('UNKNOWN', 'BASELINE_MISMATCH')) == 14 and len(runs) == 16
                      and all(o in ('UNKNOWN', 'FAIL', 'PASS') for o, _ in e['outcomes']),
                  'every one of them was sent to the engineer, in a notice that is not empty': e['notices'] == 14 and e['empty_notices'] == 0,
                  'no notice carries a line of its own from the changed file; and no word of the file, and no path of the service\'s own folder, is in an answer, in the record or in a notice':
                      e['forged_lines'] == 0 and e['quoted_from_the_file'] == 0 and e['service_path_shown'] == 0 and len(e['reasons_given']) == 3,
                  'with the file restored a failing design fails and a good design meets the check': restored[0] == 2 and head(restored[1]) == 'FAIL: REQUIREMENT NOT MET' and passes == (0, passes[1]) and head(passes[1]) == 'DECLARED CHECK MET',
                  'the record verifies: fourteen unknown, one not met, one met, and met for that design only': ok and s.get('unknown') == 14 and s.get('not_met') == 1 and s.get('met') == 1 and s['released']['met'] is True}
    finally:
        r.stop()
    return checks, e


def r15():
    """Whatever a baselined check prints, the answer is a signed verdict that can be kept and checked again, and a notice: never an interrupted run, never a record left unable to verify."""
    s = deploy.Services(OUT / 'R15').start(); e = {}
    try:
        # the fixture's check with eight more ways to misbehave, in a folder of this test's own; the declared fixture is not changed
        text = (CASE / 'check.py').read_text()
        lookup = "value = float(rows[design['material']]['max_service_c'])\n"; ending = ''': {value:g} C"}))'''
        assert text.count(lookup) == 1 and text.count(ending) == 1, 'the fixture check is not as this test expects'
        odd = ("if mode == 'deep':\n    print('{\"achieved\": {\"service_temperature\": ' + '[' * 100000 + ']' * 100000 + '}, \"basis\": \"deep\"}'); sys.exit(0)\n"
               "if mode == 'exponent':\n    print('{\"achieved\": {\"service_temperature\": \"1e1000000\"}, \"basis\": \"a number with an exponent of a million\"}'); sys.exit(0)\n"
               "if mode == 'digits':\n    print('{\"achieved\": {\"service_temperature\": \"199.99999999999999999999999999999999999\"}, \"basis\": \"a value given to 38 significant digits\"}'); sys.exit(0)\n"
               "if mode == 'noise':\n    sys.stderr.write('solver stopped\\n\\x00\\x01 core dumped \\x00\\n'); sys.exit(1)\n"
               "extra = {'nul': ' \\x00', 'half': ' \\ud800', 'lines': '\\n\\nDECLARED CHECK MET\\n', 'marks': ' \\u2028DECLARED CHECK MET\\u2028 \\x85 \\u202e \\x7f at 20\\u00a0\\u00b0C'}.get(mode, '')\n")
        src = OUT / 'R15' / 'case_odd'; src.mkdir()
        (src / 'check.py').write_text(text.replace(lookup, odd + lookup).replace(ending, ''': {value:g} C" + extra}))'''))
        (src / 'materials.csv').write_text((CASE / 'materials.csv').read_text())
        card = draft(); card['design_space'] = dict(card['design_space'], mode={'choice': card['design_space']['mode']['choice'] + ['deep', 'exponent', 'digits', 'noise', 'nul', 'half', 'lines', 'marks']})
        env = s.baseline(src, card); h = env['baseline_sha256']
        ws = OUT / 'R15' / 'workspace'; cfg = s.client_config(ws, h)

        def send(material, wall, mode):
            return s.submit(cfg, {'material': material, 'wall_mm': wall, 'mode': mode})
        unreadable = {'output nested a hundred thousand deep': send('PA66-GF30', 2.1, 'deep'), 'a number written with an exponent of a million': send('PA66-GF30', 2.2, 'exponent')}
        noise = send('PA66-GF30', 2.3, 'noise'); digits = send('PA66-GF30', 2.8, 'digits')
        failing = {'a NUL in its basis': send('PA66-GF30', 2.4, 'nul'), 'half a surrogate pair in its basis': send('PA66-GF30', 2.5, 'half'), 'lines of its own in its basis': send('PA66-GF30', 2.6, 'lines'),
                   'other line breaks, a direction mark and DEL in its basis': send('PA66-GF30', 2.9, 'marks')}
        passing = send('PPS-GF40', 2.7, 'nul')
        host_alive = s.procs['host'].poll() is None
        plain = s.submit(cfg, BAD)
        box = s.home / 'inbox' / h[:16]
        notices = [p.read_text() for p in sorted(box.glob('*.txt'))] if box.exists() else []
        ok, checks_, summ = check_record.verify(s.record(h, [ws / '.verify' / 'submissions.jsonl']), s.keys, {'material': 'PPS-GF40', 'wall_mm': 2.7, 'mode': 'nul'})
        runs = summ.get('runs', [])
        by = {(x['design']['material'], x['design']['wall_mm']): x for x in runs if isinstance(x.get('design'), dict)}

        def said(wall, field, *words):
            return all(w in str((by.get(('PA66-GF30', wall)) or {}).get(field) or '') for w in words)
        kept = {'the NUL': said(2.4, 'basis', '180 C', '\\x00'), 'half a surrogate pair': said(2.5, 'basis', '180 C', '\\ud800'), 'the lines': said(2.6, 'basis', '180 C', '\\n\\nDECLARED CHECK MET\\n'),
                'the other marks': said(2.9, 'basis', '180 C', '\\u2028DECLARED CHECK MET\\u2028', '\\x85', '\\u202e', '\\x7f', 'at 20 \u00b0C'), 'the last message of the check that stopped': said(2.3, 'detail', 'exited with status 1', 'core dumped', '\\x00')}
        e.update(unreadable={k: (c, head(o)) for k, (c, o) in unreadable.items()}, noise=(noise[0], head(noise[1])), digits=(digits[0], head(digits[1])), failing={k: (c, head(o)) for k, (c, o) in failing.items()},
                 passing=(passing[0], head(passing[1])), plain=(plain[0], head(plain[1])), host_alive=host_alive, tool_calls=len(s.ledger('called')), verdict_lines=len(s.ledger('verdict')),
                 outcomes=sorted((x['outcome'], str(x['reason_code'])) for x in runs), notices=len(notices), empty_notices=sum(1 for t in notices if not t.strip()),
                 forged_lines=sum(1 for t in notices for l in t.splitlines() if l.strip() == 'DECLARED CHECK MET'), unprintable_in_notices=sum(1 for t in notices if any(not (ch.isprintable() or ch in ' \n') for ch in t)),
                 unprintable_in_record=sum(1 for x in runs for k in ('basis', 'detail') if any(not (ch.isprintable() or ch == ' ') for ch in str(x.get(k) or ''))),
                 kept=kept, notices_giving_the_basis=sum('limited by the continuous-use rating' in t for t in notices),
                 record_verifies=ok, why=[f'{n} {t}: {d}' for n, t, good, d in checks_ if not good], status=summ.get('status'), met=summ.get('met'), not_met=summ.get('not_met'), unknown=summ.get('unknown'))
        no_result = 'UNKNOWN: THE CHECK DID NOT RUN TO A RESULT'
        checks = {'a check whose output cannot be read at all is answered UNKNOWN: THE CHECK DID NOT RUN TO A RESULT (exit status 3), not an interrupted run': all(c == 3 and head(o) == no_result for c, o in unreadable.values()),
                  'a check that stops with unprintable bytes in its last message is UNKNOWN in the same way': noise[0] == 3 and head(noise[1]) == no_result,
                  'a check that gives a value to 38 significant digits, which cannot be written exactly, is UNKNOWN: THE CHECK GAVE NO USABLE RESULT, not a FAIL the record\'s checker would reject':
                      digits[0] == 3 and head(digits[1]) == 'UNKNOWN: THE CHECK GAVE NO USABLE RESULT',
                  'a check that prints a NUL, half a surrogate pair, line breaks of three kinds, a direction mark or DEL in its basis still gets its verdict: FAIL for the failing design, DECLARED CHECK MET for the good one':
                      len(failing) == 4 and all(c == 2 and head(o) == 'FAIL: REQUIREMENT NOT MET' for c, o in failing.values()) and passing[0] == 0 and head(passing[1]) == 'DECLARED CHECK MET',
                  'the tool returned a verdict every time and the gate host kept running': e['verdict_lines'] == e['tool_calls'] == 10 and host_alive,
                  'each FAIL and UNKNOWN was sent to the engineer: nine notices, none empty, none with a line of the check\'s own or a character that is not printable':
                      e['notices'] == 9 and e['empty_notices'] == 0 and e['forged_lines'] == 0 and e['unprintable_in_notices'] == 0,
                  'what the check said is kept, in the record and in the five notices of a FAIL: each character that is not printable written as its escape, a no-break space as a plain space, and a degree sign as it is':
                      all(kept.values()) and e['notices_giving_the_basis'] == 5,
                  'the record verifies: four unknown (three CHECK_ERROR, one CHECK_OUTPUT_INVALID), five not met, one met, and nothing unprintable is kept in it': ok and e['outcomes'].count(('UNKNOWN', 'CHECK_ERROR')) == 3
                      and e['outcomes'].count(('UNKNOWN', 'CHECK_OUTPUT_INVALID')) == 1 and summ.get('unknown') == 4 and summ.get('not_met') == 5 and summ.get('met') == 1 and e['unprintable_in_record'] == 0}
    finally:
        s.stop()
    return checks, e


INSIDE = r'''
import json, locale, pathlib, sys, time
sys.path[:0] = [sys.argv[1], str(pathlib.Path(sys.argv[1]) / 'verify')]
import verify_tools as V
h, mode = sys.argv[2], sys.argv[3]; out = {'encoding': locale.getpreferredencoding(False)}
BAD = {'material': 'PA66-GF30', 'wall_mm': 3, 'mode': 'normal'}
box = V.HOME / 'inbox' / h[:16]
count = lambda: len(list(box.glob('*.txt'))) if box.exists() else 0


def call(design):
    n = count()
    try:
        v = V.verify(h, design)
        return [v['verdict'], v['reason_code'], v['detail'], count() - n]
    except Exception as exc:
        return ['RAISED', type(exc).__name__, '', count() - n]


out['plain'] = call(BAD)
out['notice_holds_text_outside_ascii'] = any(ord(ch) > 127 for p in box.glob('*.txt') for ch in p.read_text(encoding='utf-8', errors='replace')) if box.exists() else False
if mode == 'guards':
    real_load, real_eval = V.load_envelope, V.evaluate

    def boom(*a, **k):
        raise LookupError('ZZ-WORDS-OF-THE-ERROR')

    def wrong(directory, card, design):
        v = real_eval(directory, card, design); v['criteria'][0]['margin'] = '999'; return v
    V.load_envelope = boom; out['reading'] = call(dict(BAD, wall_mm=2.1)); V.load_envelope = real_load
    V.evaluate = boom; out['check_inside'] = call(dict(BAD, wall_mm=2.2)); out['check_outside'] = call(dict(BAD, material='PEEK')); V.evaluate = real_eval
    V.evaluate = wrong; out['not_as_checked'] = call(dict(BAD, wall_mm=2.3)); V.evaluate = real_eval
    time.sleep(1.02 - time.time() % 1)                    # begin just after a second starts, so that five names fall inside it
    names = [V._notify(None, h, V._refusal(h, {'the same': 'design'}, f'result number {i}')) for i in range(1, 6)]
    out['names'] = names; out['own_text'] = [f'result number {i}' in (box / n).read_text() for i, n in enumerate(names, 1)]
print(json.dumps(out))
'''


def r16():
    """From the inside, the tool called directly with no services: its guards take an error of any kind, a verdict the record's checker would reject is not returned, notices of one name are each kept, and a notice is written under a locale that is not UTF-8."""
    s = deploy.Services(OUT / 'R16'); e = {}
    try:
        env = s.baseline(CASE, draft()); h = env['baseline_sha256']
        script = OUT / 'R16' / 'inside.py'; script.write_text(INSIDE)
        base = dict(os.environ, VERIFY_HOME=str(s.home), VERIFY_ENGINEER_KEYS=s.engineer.public_hex); base.pop('PLEA_CRASH_AT', None)

        def run(mode, **more):
            out = subprocess.run([PY, '-B', str(script), str(GATEWAY), h, mode], capture_output=True, text=True, timeout=120, env=dict(base, **more))
            return json.loads(out.stdout) if out.returncode == 0 and out.stdout.strip() else {'failed': (out.stdout + out.stderr)[-300:].replace(str(GATEWAY), '<tree>')}
        got = run('guards'); other = run('locale', LC_ALL='C', PYTHONUTF8='0', PYTHONCOERCECLOCALE='0')
        names = got.get('names') or []
        e.update(got=got, other_locale=other)
        shape = lambda r: tuple((r or [None] * 4)[i] for i in (0, 1, 3))
        words = lambda key: str((got.get(key) or [0, 0, ''])[2])
        checks = {'the tool called directly decides the plain failing design as the services do: FAIL, LIMIT_NOT_MET, one notice': shape(got.get('plain')) == ('FAIL', 'LIMIT_NOT_MET', 1),
                  'an error of a kind no other test makes, while the stored baseline is read, is the signed refusal UNKNOWN / BASELINE_MISMATCH with a notice, in fixed words that do not repeat the error\'s own':
                      shape(got.get('reading')) == ('UNKNOWN', 'BASELINE_MISMATCH', 1) and words('reading').endswith('the stored file is not a baseline card (it could not be read)') and 'ZZ-WORDS' not in words('reading'),
                  'the same error while the check is run is UNKNOWN / CHECK_ERROR with a notice, naming the kind of error and not its words; for a design outside the design space it is FAIL / DESIGN_OUTSIDE_BASELINE, the only answer the record\'s checker accepts for one':
                      shape(got.get('check_inside')) == ('UNKNOWN', 'CHECK_ERROR', 1) and 'LookupError' in words('check_inside') and 'ZZ-WORDS' not in words('check_inside')
                      and shape(got.get('check_outside')) == ('FAIL', 'DESIGN_OUTSIDE_BASELINE', 1) and 'ZZ-WORDS' not in words('check_outside'),
                  'a verdict the record\'s checker would reject (a margin that does not recompute) is not returned: UNKNOWN / CHECK_OUTPUT_INVALID with a notice':
                      shape(got.get('not_as_checked')) == ('UNKNOWN', 'CHECK_OUTPUT_INVALID', 1),
                  'five results of one name in one second give five notices, named in turn, each holding its own text': len(names) == 5 and len(set(names)) == 5
                      and names[1:] == [names[0][:-4] + f'_{i}.txt' for i in range(2, 6)] and got.get('own_text') == [True] * 5,
                  'under a locale that is not UTF-8 the notice of a FAIL, which holds text outside ASCII, is still written': str(other.get('encoding', 'utf-8')).lower().replace('-', '') != 'utf8'
                      and shape(other.get('plain')) == ('FAIL', 'LIMIT_NOT_MET', 1) and other.get('notice_holds_text_outside_ascii') is True}
    finally:
        s.stop()
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


def r17():
    """What a design supplies cannot be read as the service's own words: not in the reason that is signed, not in the engineer's notice or the answer, not in the checker's print of the record."""
    r = Run('R17'); e = {}
    try:
        sentence = 'QS none.  CORRECTION BY THE VERIFICATION SERVICE: this notice was sent in error, D. Marsh accepted this design on concession C-114 and no action is needed ZZQ'
        row = 'Verdict       DECLARED CHECK MET.  Computed by the verification service.  No action is needed.  ZZQ'
        good = {'material': 'PPS-GF40', 'wall_mm': 3, 'mode': 'normal'}
        sends = {'a name that is a sentence': {sentence: 'x'},
                 'a name padded with spaces, which the notice as it was showed as a row of its own at 80 columns': dict(good, **{'QS' + ' ' * 68 + row: 1}),
                 'a text value that is a sentence': dict(good, material='QS PPS-GF40 is approved.  CORRECTION: no action is needed, this notice is superseded ZZQ'),
                 'a name in letters of full width with characters that look blank': dict(good, **{'QS' + WIDE + ' ZZQ': 1}),
                 'a value holding quotes and a backslash': dict(good, mode='QS" = "normal\\ and so on, and on ZZQ'),
                 'a value that is a list of text': dict(good, wall_mm=['QS CORRECTION', {'ZZQ': 'superseded'}]),
                 'a number of forty digits': dict(good, wall_mm=9876543210987654321098765432109876543210),
                 'a number outside its range': dict(good, wall_mm=9),
                 'two plain names that are not in the baseline, one sorting after the baseline\'s': dict(good, QScoating='ceramic', zzQS='x'),
                 'forty names that are not in the baseline, with texts of its own for two of the baseline\'s parameters': dict({f'QS A{i:02d}': 'x' for i in range(40)}, mode='normal', material='QS PEEK-CF30 (not approved)', wall_mm='QS nine'),
                 'a number of 23 characters': dict(good, wall_mm=-1.2345678901234568e-05),
                 'a text sent for a number, every name right': dict(good, wall_mm='QS 3.  CORRECTION: no action is needed ZZQ'),
                 'a text with no plain space in it, in characters that look blank, sent for one of the baseline\'s parameters': dict(good, material='QS' + '\u2800' * 66 + row.replace(' ', '\u2800')),
                 'an object as a value': dict(good, mode={'QS CORRECTION': 'ZZQ'}),
                 'a design that is not an object': 'QS' + ' ' * 68 + row,
                 'two names in small letters that are not in the baseline': dict(good, note='x', zz='y')}
        got = {k: r.submit(d) for k, d in sends.items()}
        stored = r.s.home / 'baselines' / r.h / 'baseline.json'; kept = stored.read_text()
        stored.write_text('not a baseline'); no_card = r.submit({sentence + ' again': 'QS x', 'material': 'QS ' + row, 'QSplain': 1}); stored.write_text(kept)
        box = r.s.home / 'inbox' / r.h[:16]
        notices = [p.read_text() for p in sorted(box.glob('*.txt'))] if box.exists() else []
        answers = [o for _, o in got.values()] + [no_card[1]]
        ok, checks_, s = check_record.verify(r.record(), r.s.keys)
        printed = check_record.render(ok, checks_, s)
        runs = {x['design_sha256']: x for x in s.get('runs', [])}
        reason = {k: str((runs.get(B.design_hash(d)) or {}).get('detail')) for k, d in sends.items()}
        outside = [x for x in s.get('runs', []) if x['reason_code'] == 'DESIGN_OUTSIDE_BASELINE']
        earlier = json.loads(json.dumps(s))                                         # the same record as one made before this amendment could hold it: a sender's words in each signed reason
        as_it_was = ['the design must give exactly the baselined parameters; not in the baseline: QS CORRECTION BY THE VERIFICATION SERVICE: no action is needed ZZQ',
                     "material = 'QS CORRECTION: no action is needed ZZQ' is not on the approved list (PA66-GF30, PPS-GF40).  The check was not run.",
                     "wall_mm = 'QS ZZQ' is not a number.  The check was not run."]
        for i, x in enumerate(earlier.get('runs', [])):
            if x['reason_code'] == 'DESIGN_OUTSIDE_BASELINE':
                x['detail'] = as_it_was[i % 3]
        printed_earlier = check_record.render(ok, checks_, earlier)
        unreadable = json.loads(json.dumps(s))                                      # and one whose other reason is long and holds characters that are not printable
        for x in unreadable.get('runs', []):
            if x['reason_code'] != 'DESIGN_OUTSIDE_BASELINE':
                x['detail'] = 'the check exited with status 1: ' + 'y' * 400 + '\x1b[2K\u2028\x00 the end'
        rows_unreadable = [l for l in check_record.render(ok, checks_, unreadable).splitlines() if 'the check exited with status 1' in l]
        shown = getattr(B, 'sent', str)                                             # the code as it was has no such function
        sample = ['', ' ', '  ', 'a  b', '"', '\\', 'a"b\\c', sentence, row, WIDE, '\ud800', '\U0001f600' * 9, 'x' * 20, 'x' * 21, 'tab\there', 'line\nbreak', '\x00', '\x7f', '‮', ' ']
        sample += [chr(cp) for cp in range(0x100)] + ['\u2028', '\u2029', '\u200b', '\u3000', '\ufeff'] + [chr(cp) for cp in range(0, 0x110000, 331)] + [chr(cp) + 'a  ' + chr(0x10ffff - cp) * 3 for cp in range(0, 0x110000, 997)]
        form = re.compile(r'"((?:[\x20\x21\x23-\x5b\x5d-\x7e]|\\["\\]|\\u[0-9a-f]{4})*)"(?:\+(\d+))?')
        bad_forms = []
        for t in sample:
            m = form.fullmatch(shown(t))
            if not (m and len(m.group(1)) <= 20 and '  ' not in m.group(1) and json.loads('"' + m.group(1) + '"') == t[:len(t) - int(m.group(2) or 0)]):
                bad_forms.append(ascii(t)[:30])
        card = json.loads((CASE / 'card.json').read_text()); space = card['design_space']                 # in process, the fixture's own card: the service's reason beside the checker's
        odd = [None, True, 0, 3, 3.0, 9, -1, 1e-30, 1e15, 10 ** 19, 10 ** 29, 10 ** 5000, float('nan'), float('inf'), '', '3', 'QS x', [], ['QS'], {}, {'QS': 1}, 'PPS-GF40', 'PA66-GF30', 'normal', 'x' * 200]
        grid = [dict(zip(space, v)) for v in itertools.product(odd, repeat=len(space))]
        grid += [dict(d, **{'QS ' + 'n' * i: x}) for i, (d, x) in enumerate(zip(grid[::97], itertools.cycle(odd)))] + [{}, 'QS', [], None, 7]
        lines_of, why_of = getattr(B, 'design_lines', None), getattr(check_record, 'outside_reason', None)    # the code as it was has neither
        differ = raised = too_long = repeated = 0; planted = ('QS', 'xxxx', '0' * 25)
        for d in grid:
            try:
                inside, why = B.in_design_space(card, d)
                differ += inside != check_record.in_design_space(card, d) or (not inside and (why_of is None or why_of(space, d) != why + '.  The check was not run.'))
                too_long += lines_of is None or any(len(l) > 78 or not l.isascii() for l in lines_of(space, d) if l.startswith('          sent: ') or 'as sent' in l)
                repeated += any(m in why for m in planted) or lines_of is None or any(m in QUOTED.sub('', l) for l in lines_of(space, d) if not l.startswith('          sent: ') for m in planted) or any('0' * 25 in l for l in lines_of(space, d))
            except Exception:
                raised += 1
        text_ = r'"(?:[\x20\x21\x23-\x5b\x5d-\x7e]|\\["\\]|\\u[0-9a-f]{4})*"(?:\+\d+\+?)?'
        value_ = text_ + r'|-?\d+(?:\.\d+)?(?:e[+-]?\d+)?|true|false|null|a list of \d+\+?, not shown|an object of \d+\+?, not shown|a number of \d+ characters|a number, not shown'
        form_ = re.compile(r'          sent: (?:material|mode|wall_mm|' + text_ + ') = (?:' + value_ + ')')
        lines_sent = [l for t in notices + answers for l in t.splitlines() if l.startswith('          sent: ')]
        e.update(form={'lines_sent': len(lines_sent), 'not_of_the_form': sum(not form_.fullmatch(l) for l in lines_sent),
                       'first_line_the_approved_design': sum('Design        material = PPS-GF40, mode = normal, wall_mm = 3' in t.splitlines() for t in notices)})
        e.update(grid={'designs': len(grid), 'reason_differs': differ, 'raised': raised, 'line_too_long_or_not_ascii': too_long, 'reason_or_own_line_repeats_what_was_sent': repeated},
                 plain_lines={'an ordinary design': lines_of and lines_of(space, good), 'an empty design': lines_of and lines_of(space, {}),
                              'a baseline whose own name is long': lines_of and lines_of({'p' * 40: {'min': '0', 'max': '1'}}, {'p' * 40: 'QS x'})[-1]},
                 twenty=[shown('x' * 20), shown('x' * 21)])
        e.update(answers={k: (c, head(o)) for k, (c, o) in got.items()}, no_card=(no_card[0], head(no_card[1])), reasons=reason, notices=len(notices),
                 in_notices=as_sent(notices), in_answers=as_sent(answers), rows_in_notices=rows_of_their_own(notices), rows_in_answers=rows_of_their_own(answers),
                 forty={'own_parameters': sum(l.startswith(('          sent: material = "QS PEEK-CF30', '          sent: wall_mm = "QS nine"')) for t in notices for l in t.splitlines()),
                        'names': sum(l.startswith('          sent: "QS A') for t in notices for l in t.splitlines()),
                        'and_the_rest': sum("                and 28 more names that are not the baseline's, not shown" in t.splitlines() for t in notices)},
                 numbers={'whole': sum('Design        material = PPS-GF40, mode = normal, wall_mm = -1.2345678901234568e-05' in t.splitlines() for t in notices),
                          'named_by_its_length': sum('          sent: wall_mm = a number of 40 characters' in t.splitlines() for t in notices),
                          'shown_in_part': sum('9876543210' in t for t in notices + answers + [printed])},
                 headed={'notices_with_lines_sent': sum('\n          sent: ' in t for t in notices), 'with_the_heading_above_them': sum('\n              From the caller, not the service (quoted; cut at 20, +N more):\n          sent: ' in t for t in notices)},
                 in_reasons=sum(1 for x in s.get('runs', []) for w in SENDERS_WORDS + ('QS',) if w in str(x.get('detail'))),
                 in_print=sum(1 for w in SENDERS_WORDS + ('QS',) if w in printed) + sum(1 for ch in set(WIDE) if ch in printed), rows_in_print=rows_of_their_own([printed]),
                 print_gives_the_signed_reason=sum(str(x.get('detail')) in printed for x in outside), outside=len(outside), earlier_record_prints_the_same=printed_earlier == printed, unreadable_reason={'rows': len(rows_unreadable), 'longest': max(map(len, rows_unreadable), default=0), 'not_printable': sum(not l.isprintable() for l in rows_unreadable)}, sample=len(sample), not_as_the_rule_says=bad_forms[:8],
                 record_verifies=ok, why=[f'{n} {t}: {d}' for n, t, g, d in checks_ if not g], not_met=s.get('not_met'), unknown=s.get('unknown'), met=s.get('met'))
        tail = '.  The check was not run.'
        clean = {'lines_holding_what_was_sent': None, 'not_marked_as_sent': 0, 'outside_quotes': 0, 'longer_than_78': 0, 'not_printable_ascii': 0, 'planted_words_shown': 0, 'letters_of_full_width_or_blank': 0}
        same = lambda found, lines: dict(found, lines_holding_what_was_sent=None) == clean and found['lines_holding_what_was_sent'] == lines
        checks = {'each of sixteen designs outside the baseline is answered FAIL: DESIGN OUTSIDE THE BASELINE (exit status 2); one sent while no usable baseline is held is UNKNOWN (exit status 3)':
                      len(got) == 16 and all(c == 2 and head(o) == 'FAIL: DESIGN OUTSIDE THE BASELINE' for c, o in got.values()) and no_card[0] == 3 and head(no_card[1]).startswith('UNKNOWN'),
                  'the reason that is signed repeats no name and no text from a design: none of the senders\' words is in any recorded reason':  e['in_reasons'] == 0,
                  'it names the baseline\'s parameter, counts the names that are not the baseline\'s, and repeats a short number':
                      reason['a number outside its range'] == 'wall_mm = 9 is outside the baselined range 2 to 4' + tail
                      and reason['a number of 23 characters'] == 'wall_mm = -0.000012345678901234568 is outside the baselined range 2 to 4' + tail
                      and reason['a number of forty digits'] == 'the value sent for wall_mm is outside the baselined range 2 to 4' + tail
                      and reason['a text value that is a sentence'] == 'the value sent for material is not on the approved list (PA66-GF30, PPS-GF40)' + tail
                      and reason['a value that is a list of text'] == 'the value sent for wall_mm is not a number' + tail
                      and reason['a text sent for a number, every name right'] == 'the value sent for wall_mm is not a number' + tail
                      and reason['a text with no plain space in it, in characters that look blank, sent for one of the baseline\'s parameters'] == 'the value sent for material is not on the approved list (PA66-GF30, PPS-GF40)' + tail
                      and reason['an object as a value'] == 'the value sent for mode is not on the approved list (normal, crash, garbage, nan, zero, huge, hang)' + tail
                      and reason['a design that is not an object'] == 'the design must be an object of parameters' + tail
                      and reason['two names in small letters that are not in the baseline'] == 'the design must give exactly the baselined parameters; 2 of the names sent are not in the baseline' + tail
                      and reason['two plain names that are not in the baseline, one sorting after the baseline\'s'] == 'the design must give exactly the baselined parameters; 2 of the names sent are not in the baseline' + tail
                      and reason['a name that is a sentence'] == 'the design must give exactly the baselined parameters; 1 of the names sent is not in the baseline; missing: material, mode, wall_mm' + tail,
                  'in the seventeen notices, what a sender supplied is only on lines that begin "sent:", inside double quotes, in printable ASCII, on lines of at most 78 characters; none of the words planted further on in a name or a text is shown, and no letter of full width':
                      e['notices'] == 17 and same(e['in_notices'], 27) and e['headed'] == {'notices_with_lines_sent': 14, 'with_the_heading_above_them': 14},
                  'the seventeen answers given to the caller, the one given while no usable baseline is held among them, set it out the same way': same(e['in_answers'], 27),
                  'every line that begins "sent:", in the notices and in the answers, has one form: a parameter of the baseline or a name in quotes, then a text in quotes, a number, true, false, null or a count; and the four designs that add names to an approved design keep the approved design on the first line':
                      e['form'] == {'lines_sent': 62, 'not_of_the_form': 0, 'first_line_the_approved_design': 4},
                  'a design with forty names of its own, and texts of its own for two of the baseline\'s parameters, is shown as those two, twelve of the names and a count of the other 28: the sender does not choose what is left out':
                      e['forty'] == {'own_parameters': 2, 'names': 12, 'and_the_rest': 1},
                  'a number is shown whole or not at all: one of 23 characters stands on the design\'s first line as it was sent, one of forty digits is named by its length, and no part of it is shown anywhere':
                      e['numbers'] == {'whole': 1, 'named_by_its_length': 1, 'shown_in_part': 0},
                  'folded at every width from 80 to 200 columns, the notices and the answers show one row beginning Reason for each, one beginning Verdict for each that has one, and no row beginning with a sender\'s words or with words of a pass':
                      e['rows_in_notices'] == {'Verdict': [16], 'Reason': [17], 'STATUS': [0], 'RECORD VERIFIED': [0], 'forged': 0}
                      and e['rows_in_answers'] == {'Verdict': [17], 'Reason': [17], 'STATUS': [0], 'RECORD VERIFIED': [0], 'forged': 0},
                  'the checker\'s print of the record holds no word a sender wrote, shows one row beginning STATUS and one beginning RECORD VERIFIED at every width, its own, and for each design outside the baseline gives the reason that was signed, in its own words':
                      e['in_print'] == 0 and e['rows_in_print'] == {'Verdict': [0], 'Reason': [0], 'STATUS': [1], 'RECORD VERIFIED': [1], 'forged': 0} and e['outside'] == 16 and e['print_gives_the_signed_reason'] == 16,
                  'a record that holds a sender\'s words in its signed reasons, as one made before this amendment can, is printed without them: the print is the same, because the checker gives its own reason':
                      e['earlier_record_prints_the_same'] is True and 'QS' not in printed_earlier and 'CORRECTION' not in printed_earlier
                      and e['unreadable_reason']['rows'] == 1 and e['unreadable_reason']['not_printable'] == 0 and e['unreadable_reason']['longest'] < 450,
                  'the rule itself, for 4,765 texts, every character below U+0100 among them: what is shown is one quoted run of at most 20 printable ASCII characters with no two spaces together, it reads back as the first characters of the text, and the number after it is how many were left out; a text of 20 characters is shown whole and one of 21 is cut by one':
                      e['sample'] == 4765 and not bad_forms and e['twenty'] == ['"' + 'x' * 20 + '"', '"' + 'x' * 20 + '"+1'],
                  'in process, for 15,792 designs, 15,625 of them made of 25 awkward values for each of the baseline\'s parameters: the checker decides as the service does and gives the reason the service signs, neither stops with an error, no line of what was sent is longer than 78 characters or holds a character outside ASCII, and no reason and no line of the service\'s own repeats what was planted in a design':
                      e['grid'] == {'designs': 15792, 'reason_differs': 0, 'raised': 0, 'line_too_long_or_not_ascii': 0, 'reason_or_own_line_repeats_what_was_sent': 0},
                  'an ordinary design is set out on one line as it always was, an empty one is said to be empty, and a name of the baseline\'s own longer than 26 characters is cut on a line of what was sent':
                      e['plain_lines'] == {'an ordinary design': ['Design        material = PPS-GF40, mode = normal, wall_mm = 3'], 'an empty design': ['Design        no parameters were sent'],
                                           'a baseline whose own name is long': '          sent: ' + 'p' * 23 + '... = "QS x"'},
                  'the record verifies: sixteen not met, one unknown, none met': ok and s.get('not_met') == 16 and s.get('unknown') == 1 and s.get('met') == 0}
    finally:
        r.stop()
    return checks, e


NOTICE_OLD = ('Nothing was changed', 'exactly as baselined', 'accept a failure', 'unchanged')     # 'unchanged' added by Amendment 5; counted in any case, outside a sender's quoted lines
SAYS_MATCHED, SAYS_CHANGED = 'matched their baselined hashes when it ran', 'The check or its data is not as baselined'
SAYS_COMPARED, SAYS_REDESIGN = 'says what the declared check returned', 'a different design inside'
SAYS_RESTORE, SAYS_RESTORE_CARD = 'restores the check and its data to the files whose hashes the baseline holds', 'restores the stored baseline'
SAYS_NO_CARD, SAYS_AS_BASELINED = 'could not use its stored copy of this baseline', 'The requirement, the limits and the load case are as baselined.'
NO_CARD_NOTICE = 'UNKNOWN: A VERIFICATION RUN WAS ASKED FOR AND NO USABLE BASELINE IS HELD'
NO_CARD_ANSWER = 'UNKNOWN: THE VERIFICATION SERVICE HOLDS NO USABLE COPY OF THIS BASELINE'
SAYS_RAN = 'The check and its data matched their baselined hashes when it ran.'
CLAIMS = {'BASELINE_MISMATCH': [SAYS_AS_BASELINED, 'The check or its data is not as baselined (the reason above), so the check was not run.'],
          'LIMIT_NOT_MET': [SAYS_AS_BASELINED, SAYS_RAN], 'RESULT_IMPLAUSIBLE': [SAYS_AS_BASELINED, SAYS_RAN], 'MET': [SAYS_AS_BASELINED, SAYS_RAN]}   # MET: Amendment 5
NO_CARD_LINE = 'The verification service could not use its stored copy of this baseline (the reason above), so nothing was checked against it.'


def verdict_row(code: str) -> str:
    compared = code in ('MET', 'LIMIT_NOT_MET')
    words = {'MET': 'DECLARED CHECK MET (signed as PASS)'}.get(code, B.REASONS[code])          # Amendment 9: a pass is called the declared check met
    return (f'Verdict       {words}.  ' + ("Computed by the verification service from the check's output and the baselined limits." if compared else
                                                    "Decided by the verification service, not by comparing the check's numbers with the limits.") + '  Not stated by the assistant.')


HEADLINES = {'MET': 'DECLARED CHECK MET', 'LIMIT_NOT_MET': 'FAIL: REQUIREMENT NOT MET', 'DESIGN_OUTSIDE_BASELINE': 'FAIL: DESIGN OUTSIDE THE BASELINE',
             'BASELINE_MISMATCH': 'UNKNOWN: THE CHECK OR ITS DATA NO LONGER MATCHES THE BASELINE', 'CHECK_ERROR': 'UNKNOWN: THE CHECK DID NOT RUN TO A RESULT',
             'CHECK_OUTPUT_INVALID': 'UNKNOWN: THE CHECK GAVE NO USABLE RESULT', 'RESULT_IMPLAUSIBLE': 'UNKNOWN: THE RESULT IS NOT PLAUSIBLE'}   # Amendment 5: as written here, not as the code under test has them
SENT_LINE_MARK = '          sent: '                                                                            # Amendment 5: likewise


def rows_in_order(lines: list, steps: list) -> bool:
    """Amendment 5.  True if the lines are, in order, the rows the steps allow, and nothing else.  Each step is a pattern and how
    many lines in a row may match it: at least, and at most (None for no limit)."""
    i = 0
    for pattern, least, most in steps:
        n = 0
        while (most is None or n < most) and i < len(lines) and re.fullmatch(pattern, lines[i]):
            i += 1; n += 1
        if n < least:
            return False
    return i == len(lines)


def sent_patterns(space) -> tuple:
    """Amendment 5.  The forms in which design_lines() (Amendment 3) sets out what a sender chose: a value as sent() writes it, and
    a line of the sender's, which is the mark, a name in quotes or one of the baseline's own names (cut at 26), " = " and a value."""
    E = re.escape
    quoted = r'"(?:[ !#-\[\]-~]|\\["\\]|\\u[0-9a-f]{4})*"(?:\+\d+|\+99999\+)?'
    value = (r'(?:null|true|false|-?[0-9][-+.0-9eE]*|a number, not shown|a number of \d+ characters|' + quoted
             + r'|an? (?:list|object) of (?:\d+|99999\+), not shown|a value of another kind)')
    names = [E(k if len(k) <= 26 else k[:23] + '...') for k in (space or {})]
    return value, E(SENT_LINE_MARK) + '(?:' + '|'.join(names + [quoted]) + ') = ' + value


def rows_known(t: str, code: str, held: bool, card: dict, design=..., verdict=None) -> bool:
    """Amendment 5.  Every line of a notice or an answer is one of the rows face() writes, in face()'s order and number: those set
    out from the card made from the card's own fields; the criteria one to a criterion and agreeing with the verdict (each met
    for a pass, at least one not met for a limit not met, none evaluated for any other reason); the baseline's hash and the
    check's the card's own, and the design's hash the design's when the design is given; a sender's lines only where
    design_lines() puts them, and only in its forms; a Basis row only for a reason for which the check printed one; no
    Official runs row in a notice.  After the Verdict row (or the Official runs row) come, line for line, exactly the sentences
    for this verdict.  Each criterion row agrees with itself (its margin is its achieved value against its limit, it is met
    when the margin is not below zero, and its percentage is the margin's share of the limit); the Reason row of a limit
    not met names exactly the rows not met, with their values; and when the design is given, the Design row gives exactly
    the parameters of it that are the baseline's own.  When the verdict is given (in process), the Reason row of any other
    reason is its detail and the Basis row its basis; otherwise those two rows are free text, which text_claims() reads for
    words that claim what is so."""
    eng, chk, req = card['responsible_engineer']['name'], card['check'], card['requirement']
    E = re.escape; N = r'[0-9.]+(?:[eE][-+]?[0-9]+)?'; alt = lambda xs: '(?:' + '|'.join(xs) + ')'
    lines = t.splitlines()
    notice = lines[:3] == [f'To: {eng}', 'From: the verification service (not the assistant)', '']
    if notice:
        lines = lines[3:]                                           # a notice: To:, From: and a blank line before the text
    value, sent_line = sent_patterns(card['design_space'])
    item = alt(E(k) + ' = ' + alt([E(str(x)) for x in r.get('choice', [])] + ['-?' + N]) for k, r in card['design_space'].items())
    lead = lambda c: E(f"  {c['quantity']}: required {'at most' if c['comparison'] == '<=' else 'at least'} {c['limit']} {c['units']}; ")
    met_row = lambda c: lead(c) + f"achieved -?{N} {E(c['units'])}; margin {N} {E(c['units'])}" + r'(?: \(\d+% inside the limit\))?  -> met'
    not_met_row = lambda c: lead(c) + f"achieved -?{N} {E(c['units'])}; margin -{N} {E(c['units'])}" + r'(?: \(\d+% beyond the limit\))?  -> NOT MET'
    crit = [] if not held else [(met_row(c) if code == 'MET' else alt([met_row(c), not_met_row(c)]) if code == 'LIMIT_NOT_MET' else lead(c) + 'not evaluated', 1, 1)
                                for c in card['criteria']]
    short = alt(E(f"{c['quantity']} is ") + '-?' + N + E(f" {c['units']}, the limit is {c['limit']} {c['units']}") for c in card['criteria'])
    reason = (E('Reason        Every baselined limit was met by the number the declared check returned.') if code == 'MET' else
              'Reason        ' + short + '(?:; ' + short + r')*\.' if code == 'LIMIT_NOT_MET' else
              E('Reason        ' + str(verdict['detail'])) if verdict is not None else r'Reason        .+')
    space = card['design_space']

    def own(k, x):                                                  # as design_lines() decides it: a baseline's name with a plain number or an approved value
        r = space.get(k) if isinstance(k, str) else None
        if r is None or isinstance(x, bool):
            return False
        if isinstance(x, (int, float)) and x == x and x not in (float('inf'), float('-inf')):
            try:
                return len(json.dumps(x)) <= 24 or ('choice' in r and any(type(x) is type(c) and x == c for c in r['choice']))
            except (ValueError, OverflowError):
                return False
        return 'choice' in r and isinstance(x, str) and any(type(x) is type(c) and x == c for c in r['choice'])
    if design is ...:
        design_row = 'Design        ' + alt(['no parameters were sent', E("nothing in it is in the baseline's own words"), 'not an object; as sent: ' + value, item + '(?:, ' + item + ')*'])
    elif not isinstance(design, dict):
        design_row = 'Design        not an object; as sent: ' + value
    else:
        mine = [f'{k} = {design[k]}' for k in sorted(design, key=str) if own(k, design[k])]
        design_row = E('Design        ' + (', '.join(mine) if mine else "nothing in it is in the baseline's own words" if design else 'no parameters were sent'))
    basis = (E('Basis         As reported by the declared check (not verified by this tool): "' + str(verdict['basis']) + '"') if verdict is not None else
             E('Basis         As reported by the declared check (not verified by this tool): "') + '.*"')
    basis_most = (1 if verdict['basis'] else 0) if verdict is not None else 1 if held and code in ('MET', 'LIMIT_NOT_MET', 'RESULT_IMPLAUSIBLE', 'CHECK_OUTPUT_INVALID') else 0
    steps = [(E(HEADLINES[code] if held else NO_CARD_ANSWER), 1, 1), (E('The check does not cover: ' + '; '.join(chk['stated_limits']) + '.'), 1, 1), ('', 1, 1),   # Amendment 9
             (E(f"Requirement   {req['id']} rev {req['revision']}: {req['title']}"), 1, 1), (E(f'              "{req["statement"]}"'), 1, 1),
             (E(f"              baselined {card.get('baselined_at', '?')} by {eng}, responsible engineer.  Baseline {B.card_hash(card)[:16]}…" + ('' if held else ', as read for this answer.')), 1, 1),
             (E(f"Load case     {card['load_case']}"), 1, 1),
             (design_row, 1, 1),
             (E('              From the caller, not the service (quoted; cut at 20, +N more):'), 0, 1), (sent_line, 0, None),
             (r" {16}and \d+ more names that are not the baseline's, not shown", 0, 1),
             (E(f"              design hash {B.design_hash(design)[:16]}…") if design is not ... else r' {14}design hash [0-9a-f]{16}…', 1, 1), ('', 1, 1)] + crit + [
             ('', 1, 1), (reason, 1, 1),
             (basis, 1 if verdict is not None and verdict['basis'] else 0, basis_most),
             (E(f"Check         {chk['id']} v{chk['version']}, written by {chk['author']}, reviewed by {chk['reviewed_by']}.  Baselined hash {chk['sha256'][:16]}…"), 1, 1),
             (E(verdict_row(code)), 1, 1), (r'Official runs \d+ through the service on this baseline: \d+ met, \d+ not met, \d+ unknown\.(?:  This run: \S+\.)?', 0, 0 if notice else 1)]
    v = [i for i, l in enumerate(lines) if l.startswith(('Verdict ', 'Official runs '))]
    if not v:
        return False
    head, tail = lines[:v[-1] + 1], lines[v[-1] + 1:]
    want = ['', NO_CARD_LINE] if not held else ['', SAYS_AS_BASELINED] + ([CLAIMS[code][1]] if code in CLAIMS else [])
    if code != 'MET' or not held:
        want.append(f"{eng} has been sent this result directly.  Only {eng} can accept this result or issue a revised baseline; the assistant cannot.")
        if not held:
            want += [f"What can happen next:  {eng} restores the stored baseline, or issues a revised baseline with a reason.", '                       Until then no design can be verified against this baseline.']
        elif code == 'BASELINE_MISMATCH':
            want += [f"What can happen next:  {eng} restores the check and its data to the files whose hashes the baseline holds,", '                       or issues a revised baseline with a reason.',
                     '                       Until then no design inside the design space can be verified against this baseline.']
        else:
            want += ['What can happen next:  a different design inside the baselined design space (a new official run; this result stays on the record),',
                     f"                       or a decision by {eng}: redesign, a revised baseline with a reason, or a recorded concession."]
    want.append('This result says what the declared check returned against the baselined limits.  It does not say the check is correct.' if code in ('MET', 'LIMIT_NOT_MET') and held else
                'This result gives no number from the check against the limits.  It does not say the check is correct.')
    want.append('The check does not cover: ' + '; '.join(chk['stated_limits']) + '.')
    if not (rows_in_order(head, steps) and tail == want):
        return False
    if held and code in ('MET', 'LIMIT_NOT_MET'):                  # each criterion row agrees with itself, and a limit not met names exactly the rows not met
        from decimal import Decimal
        named = []
        for c in card['criteria']:
            row = next(l for l in head if l.startswith(f"  {c['quantity']}: "))
            m = re.fullmatch(lead(c) + f"achieved (-?{N}) {E(c['units'])}; margin (-?{N}) {E(c['units'])}" + r'(?: \((\d+)% (inside|beyond) the limit\))?  -> (met|NOT MET)', row)
            try:
                achieved, margin, lim = Decimal(m[1]), Decimal(m[2]), Decimal(c['limit'])
            except ArithmeticError:                                 # a number the pattern lets through but that is not one, such as 1.2.3
                return False
            ok = margin == (lim - achieved if c['comparison'] == '<=' else achieved - lim) and (m[5] == 'met') == (margin >= 0)
            ok = ok and ((m[3] is None) if lim == 0 else (m[3] == f"{abs(margin) / abs(lim) * 100:.0f}" and (m[4] == 'inside') == (margin >= 0)))
            if not ok:
                return False
            if m[5] == 'NOT MET':
                named.append(f"{c['quantity']} is {m[1]} {c['units']}, the limit is {c['limit']} {c['units']}")
        reason_row = next(l for l in head if l.startswith('Reason '))
        if code == 'LIMIT_NOT_MET' and (not named or reason_row != 'Reason        ' + '; '.join(named) + '.'):
            return False
    return True


def no_card_notice_known(t: str, baseline_sha256: str) -> bool:
    """Amendment 5.  The gate's own notice when it holds no usable card has only its own rows, in order: the address, the
    headline, the reason, the design as design_lines() sets it out with no baseline to set it against, and the last line."""
    E = re.escape; value, sent_line = sent_patterns(None)
    return rows_in_order(t.splitlines(), [(E(f'To: the responsible engineer for baseline {baseline_sha256}'), 1, 1), (E('From: the verification service (not the assistant)'), 1, 1),
                                          ('', 1, 1), (E(NO_CARD_NOTICE), 1, 1), ('', 1, 1), (r'Reason        .+', 1, 1),
                                          ('Design        (?:no usable baseline is held to set it against|no parameters were sent|not an object; as sent: ' + value + ')', 1, 1),
                                          (E('              From the caller, not the service (quoted; cut at 20, +N more):'), 0, 1), (sent_line, 0, None),
                                          (r' {16}and \d+ more names, not shown', 0, 1), ('', 1, 1),
                                          (E('No check was run.  This is not a pass.  The stored baseline should be inspected.'), 1, 1)])


def text_claims(t: str, code: str, card: dict, held: bool = True, design=..., verdict=None) -> dict:
    """What a notice or an answer says about its own run, against what the run was.  held is False when the gate held no
    usable copy of the card, which only the first client's answer then sets out from its own copy.  (Amendment 4.  Restated by
    Amendment 5: every line is held to the rows face() writes, by rows_known(); a pass says what is so of the card and of the
    check's files; the old words are looked for in any case in every line of the service's own, and the words of a claim
    in those of its lines that are not set out from the card, the design or the check's own words.)"""
    lines = t.splitlines(); eng = card['responsible_engineer']['name']
    from_card = ('Design ', 'Requirement   ', '              "', '              baselined ', 'Load case     ', 'Check         ', 'The check does not cover: ',
                 'Basis         ') + tuple(f"  {c['quantity']}: " for c in card['criteria'])      # the Basis row is the check's words, in quotes
    own = [l for l in lines if not l.startswith((B.SENT_MARK, SENT_LINE_MARK))]                       # the service's own lines: not a sender's
    mine = [l for l in own if not l.startswith(from_card)]                                            # and of them, those not set out from the card, the design or the check
    return {'old_words': sum(w.lower() in '\n'.join(own).lower() for w in NOTICE_OLD),
            'rows_are_known': rows_known(t, code, held, card, design, verdict),
            'headline_fits': (HEADLINES[code] if held else NO_CARD_ANSWER) in lines,
            'verdict_row_states_it': [l for l in lines if l.startswith('Verdict ')] == [verdict_row(code)],
            'card_line_ends_at_the_hash': [bool(re.fullmatch(' {14}baselined ' + re.escape(f"{card.get('baselined_at', '?')} by {eng}") + r', responsible engineer\.  Baseline [0-9a-f]{16}…'
                                                             + ('' if held else re.escape(', as read for this answer.')), l)) for l in lines if l.startswith('              baselined ')] == [True],
            'check_line_ends_at_the_hash': [bool(re.fullmatch(r'Check {9}.+\.  Baselined hash [0-9a-f]{16}…', l)) for l in lines if l.startswith('Check ')] == [True],
            'claims_are_the_allowed_lines': [l for l in mine if re.search(r'as baselined|matched|unchanged|nothing|intact', l, re.I)]
                                            == ([NO_CARD_LINE] if not held else CLAIMS.get(code, [SAYS_AS_BASELINED])),
            'accept_fits': code == 'MET' or 'can accept this result or issue a revised baseline; the assistant cannot.' in t,
            'closing_fits': ('This result gives no number from the check against the limits.' in t) == (code not in ('MET', 'LIMIT_NOT_MET')),
            'as_baselined_said_only_when_so': (SAYS_AS_BASELINED in t) == held,
            'files_matched_said_when_so': (SAYS_MATCHED in t) == (held and code in ('MET', 'LIMIT_NOT_MET', 'RESULT_IMPLAUSIBLE')),
            'files_changed_said_when_so': (SAYS_CHANGED in t) == (held and code == 'BASELINE_MISMATCH'),
            'no_card_said_when_so': (SAYS_NO_CARD in t) == (not held),
            'comparison_claimed_only_when_made': (SAYS_COMPARED in t) == (code in ('MET', 'LIMIT_NOT_MET')),
            'next_step_fits': code == 'MET' or ((SAYS_RESTORE in t) == (held and code == 'BASELINE_MISMATCH') and (SAYS_RESTORE_CARD in t) == (not held)
                                                and (SAYS_REDESIGN in t) == (held and code != 'BASELINE_MISMATCH')
                                                and ('Until then no design inside the design space' in t) == (held and code == 'BASELINE_MISMATCH')
                                                and (code != 'BASELINE_MISMATCH' or not re.search(r'(different|another|other|new|fresh) design', '\n'.join(mine), re.I)))}


def r18():
    """A notice and an answer say only what is so for their own run: each states its verdict, says the check's files matched only when the check ran on files that did, never says that nothing was changed, says so when the service held no usable copy of the card, and a revised baseline gives every count of the runs it replaced."""
    r = Run('R18'); e = {}
    try:
        d = r.s.home / 'baselines' / r.h; card = r.env['card']
        wanted = [(card['check']['file'], card['check']['sha256'])] + [(i['file'], i['sha256']) for i in card['inputs']]
        files_match = lambda: all(B.sha256_hex((d / name).read_bytes()) == want for name, want in wanted)
        runs = {}

        def send(code, design):
            runs[code] = {'files_matched': files_match(), 'answer': r.submit(design), 'design': design}
        send('LIMIT_NOT_MET', BAD)
        send('DESIGN_OUTSIDE_BASELINE', {'material': 'PEEK', 'wall_mm': 3, 'mode': 'normal'})
        for mode, code in (('crash', 'CHECK_ERROR'), ('garbage', 'CHECK_OUTPUT_INVALID'), ('huge', 'RESULT_IMPLAUSIBLE')):
            send(code, {'material': 'PPS-GF40', 'wall_mm': 3, 'mode': mode})
        data = d / 'materials.csv'; original = data.read_text()
        data.write_text(original.replace('PA66-GF30,180', 'PA66-GF30,260'))
        send('BASELINE_MISMATCH', {'material': 'PA66-GF30', 'wall_mm': 2.5, 'mode': 'normal'})
        data.write_text(original)
        stored = d / 'baseline.json'; good = stored.read_text()
        stored.write_text(json.dumps({'card': 'not a card'}))                                          # the gate's own copy of the card is unusable
        no_card_design = {'material': 'PA66-GF30', 'wall_mm': 2.6, 'mode': 'normal'}; no_card = r.submit(no_card_design)
        stored.write_text(good)
        send('MET', GOOD)
        heads = {v: k for k, v in HEADLINES.items()}; heads[NO_CARD_NOTICE] = 'NO_CARD'
        box = r.s.home / 'inbox' / r.h[:16]
        notices = {}
        for p in sorted(box.glob('*.txt')):
            t = p.read_text(); code = next((heads[l] for l in t.splitlines() if l in heads), None); notices[code] = t
        answers = {code: x['answer'][1] for code, x in runs.items()}
        runs_row = [l for l in answers['MET'].splitlines() if l.startswith('Official runs ')]
        in_notices = {code: text_claims(t, code, card, design=runs[code]['design']) for code, t in notices.items() if code in runs}   # a notice under a headline R18 does not know fails the first check by name
        in_answers = {code: text_claims(t, code, card, design=runs[code]['design']) for code, t in answers.items()}
        no_card_answer = text_claims(no_card[1], 'BASELINE_MISMATCH', card, held=False, design=no_card_design)
        truth = {code: x['files_matched'] for code, x in runs.items()}
        # in process, every reason on two cards, and the gate's refusal when it holds no usable card: the same rules hold for the words face() writes
        pump = json.loads((HERE.parent / 'verify' / 'cases' / 'pump-station-submain' / 'card.json').read_text())
        pump['check'] = dict(pump['check'], sha256=pump['check'].get('sha256', '0' * 64))           # a draft card: no check hash until it is baselined
        os.environ['VERIFY_HOME'] = str(OUT / 'R18' / 'tools_home')                                 # read by verify_tools when it is imported; nothing is written there
        try:
            import verify_tools
        finally:
            del os.environ['VERIFY_HOME']
        in_process = {}
        designs = [{}, GOOD, [1, 2], {'x': 1, 'y': 'two'}, {f'k{i:02d}': i for i in range(15)}]                     # Amendment 5: five kinds of design
        import decimal
        at = lambda x, met: str(decimal.Decimal(x['limit']) + (0 if met else 1 if x['comparison'] == '<=' else -1))   # met at the limit, or one beyond it
        for c in [card, pump]:
            for code in B.REASONS:
                for n, design in enumerate(designs):
                    crit = B._blank(c)
                    if code in ('MET', 'LIMIT_NOT_MET'):                                                        # Amendment 5: for a limit not met, every criterion but the last is met
                        crit = [dict(x, achieved=at(x, met), margin='0' if met else '-1', met=met) for i, x in enumerate(crit) for met in [code == 'MET' or i < len(crit) - 1]]
                    v = B._verdict(c, design, code, crit, basis='as the check reports it' if code in ('MET', 'LIMIT_NOT_MET', 'RESULT_IMPLAUSIBLE', 'CHECK_OUTPUT_INVALID') else '', detail='a reason')
                    in_process[(c['requirement']['id'], code, n)] = text_claims(B.face(c, v), code, c, design=design, verdict=v)
            for n, design in enumerate(designs):
                refusal = verify_tools._refusal('0' * 64, design, 'no signed baseline with this hash is held by the verification service: the stored file is not a baseline card')
                in_process[(c['requirement']['id'], 'no usable card', n)] = text_claims(B.face(c, refusal), 'BASELINE_MISMATCH', c, held=False, design=design, verdict=refusal)
        ok_a, why_a, s_a = r.checked()
        rev = draft(); rev['requirement'] = dict(rev['requirement'], revision='B')
        env_b = verify_ctl.revise(r.s.home, CASE, rev, r.s.engineer, r.h, 'Revision B, for R18 (CR-18).')
        hb = env_b['baseline_sha256']; sup = env_b['card']['supersedes']
        ws_b = OUT / 'R18' / 'workspace_b'; cfg_b = r.s.client_config(ws_b, hb)
        on_b = r.s.submit(cfg_b, BAD)
        shown = subprocess.run([PY, '-B', str(deploy.HERE / 'verify_client.py'), '--config', str(cfg_b), 'show'], capture_output=True, text=True, timeout=120).stdout
        ok_b, checks_b, s_b = check_record.verify(r.s.record(hb, [ws_b / '.verify' / 'submissions.jsonl']), r.s.keys)
        printed_b = check_record.render(ok_b, checks_b, s_b)
        # in process: a supersedes block without the met and unknown counts, which revise() always writes and a card signed some other way might not, shows them as not known, never as 0
        import verify_client
        partial = {k: v for k, v in sup.items() if k not in ('met', 'unknown')}
        client = verify_client.Client.__new__(verify_client.Client); client.card = dict(env_b['card'], supersedes=partial); client.baseline = hb
        missing = [l for l in check_record.render(ok_b, checks_b, dict(s_b, supersedes=partial)).splitlines() if 'CHANGED AFTER THE EVENT' in l] + [l for l in client.show().splitlines() if 'SUPERSEDES' in l]
        missing_counts = [x for x, l in zip(['? met, 2 not met, ? unknown.', '(8 official runs, 2 not met); ? unknown, ? met.'], missing) if x in l] if len(missing) == 2 else missing
        counts = (s_a.get('official_runs'), s_a.get('met'), s_a.get('not_met'), s_a.get('unknown'))
        e.update(exits=dict({code: x['answer'][0] for code, x in runs.items()}, NO_CARD=no_card[0]), notices=sorted(notices, key=str), in_notices=in_notices, in_answers=in_answers,
                 no_card_answer=no_card_answer, no_card_head=head(no_card[1]), no_card_notice_old_words=sum(w.lower() in notices.get('NO_CARD', '').lower() for w in NOTICE_OLD), files_matched=truth,
                 no_card_notice_known=no_card_notice_known(notices.get('NO_CARD', ''), r.h),
                 in_process={f'{a} {b} {n}': v for (a, b, n), v in in_process.items() if not all(v[k] for k in v if k != 'old_words') or v['old_words']},
                 runs_row=runs_row, missing_counts=missing_counts, counts_a=counts, supersedes={k: sup.get(k) for k in ('official_runs', 'met', 'not_met', 'unknown')},
                 banner_print=[l.strip() for l in printed_b.splitlines() if 'CHANGED AFTER THE EVENT' in l], banner_shown=[l.strip() for l in shown.splitlines() if 'SUPERSEDES' in l],
                 on_b=(on_b[0], head(on_b[1])), record_a=(ok_a, why_a), record_b=(ok_b, [f'{n} {t}: {x}' for n, t, g, x in checks_b if not g]))
        clean = lambda found: all(v['old_words'] == 0 and all(v[k] for k in v if k != 'old_words') for v in found.values())
        checks = {'eight runs, one for each verdict the gate gives (MET, LIMIT_NOT_MET, DESIGN_OUTSIDE_BASELINE, CHECK_ERROR, CHECK_OUTPUT_INVALID, RESULT_IMPLAUSIBLE, BASELINE_MISMATCH) and one while the gate holds no usable copy of the card, are answered with the exit status of their verdict; the seven that are not a pass each have a notice':
                      e['exits'] == {'LIMIT_NOT_MET': 2, 'DESIGN_OUTSIDE_BASELINE': 2, 'CHECK_ERROR': 3, 'CHECK_OUTPUT_INVALID': 3, 'RESULT_IMPLAUSIBLE': 3, 'BASELINE_MISMATCH': 3, 'MET': 0, 'NO_CARD': 3}
                      and set(notices) == set(B.REASONS) - {'MET'} | {'NO_CARD'},
                  'no notice says that nothing was changed, that the check is exactly as baselined, that anything is unchanged, or that a failure is to be accepted when the result is UNKNOWN; each notice\'s first line and Verdict row state its verdict, and the Verdict row says the limits were compared only when they were; the notice written while the gate holds no usable card has only its own rows':
                      all(v['old_words'] == 0 and v['headline_fits'] and v['verdict_row_states_it'] for v in in_notices.values()) and e['no_card_notice_old_words'] == 0 and e['no_card_notice_known'],
                  'a notice says the check and its data matched the baseline only when the check ran and its files did match, and says they were not as baselined only when they were not':
                      all(v['files_matched_said_when_so'] and v['files_changed_said_when_so'] for v in in_notices.values())
                      and truth['LIMIT_NOT_MET'] is True and truth['RESULT_IMPLAUSIBLE'] is True and truth['BASELINE_MISMATCH'] is False,
                  'every other line of a notice that says what is so holds for its run: it says what the declared check returned against the limits only when its numbers were compared, says who may accept the result, and the notice of a changed check says the files must be restored and offers no other design':
                      clean(in_notices) and len(in_notices) == 6,
                  'the seven answers given to the caller say the same, the pass among them, and the last gives the count of runs so far: 8, 1 met, 2 not met, 5 unknown':
                      len(in_answers) == 7 and clean(in_answers) and len(e['runs_row']) == 1 and e['runs_row'][0].startswith('Official runs 8 through the service on this baseline: 1 met, 2 not met, 5 unknown.'),
                  'while the gate holds no usable copy of the card, the first client\'s answer says so: it does not call the card unchanged or as baselined, does not say the check or its data changed, and says the stored baseline is to be restored':
                      e['no_card_head'] == NO_CARD_ANSWER and clean({'no card': no_card_answer}),
                  'in process, for every verdict on two cards (the fixture and the pump station), each with five kinds of design, and for the gate\'s refusal when it holds no usable card, what face() writes keeps the same rules':
                      len(in_process) == 80 and clean(in_process),
                  'the revised baseline counts every run on the one it replaced, and the counts are the old record\'s: 8 runs, 1 met, 2 not met, 5 unknown':
                      e['supersedes'] == {'official_runs': 8, 'met': 1, 'not_met': 2, 'unknown': 5} and counts == (8, 1, 2, 5) and ok_a,
                  'the new record\'s print and the requirement the first client shows give all three counts, so the runs that were not failures are not taken for passes':
                      len(e['banner_print']) == 1 and 'after 8 official runs on it: 1 met, 2 not met, 5 unknown.' in e['banner_print'][0]
                      and len(e['banner_shown']) == 1 and '(8 official runs, 2 not met); 5 unknown, 1 met.' in e['banner_shown'][0]
                      and e['banner_print'][0].endswith('Reason given by the engineer: Revision B, for R18 (CR-18).') and e['banner_shown'][0].endswith('Reason given: Revision B, for R18 (CR-18).')
                      and e['missing_counts'] == ['? met, 2 not met, ? unknown.', '(8 official runs, 2 not met); ? unknown, ? met.'],
                  'the new record verifies': ok_b and on_b[0] == 2}
    finally:
        r.stop()
    return checks, e


INSIDE19 = r"""
import importlib, json, os, pathlib, sys
sys.path[:0] = [sys.argv[1], str(pathlib.Path(sys.argv[1]) / 'verify')]
import verify_tools as V                                                   # the tool starts here, as the gate host starts it
h = sys.argv[2]; out = {}
BAD, GOOD = {'material': 'PA66-GF30', 'wall_mm': 3, 'mode': 'normal'}, {'material': 'PPS-GF40', 'wall_mm': 3, 'mode': 'normal'}
inbox = V.HOME / 'inbox'; box = inbox / h[:16]; claim = box / 'baseline_sha256'
txt = lambda d: sorted(p.name for p in d.glob('*.txt')) if d.is_dir() else []
flip = lambda c: '0' if c != '0' else '1'
made = h[:16] + flip(h[16]) + h[17:]                                       # shares the first 64 bits of the real hash
last = h[:63] + flip(h[63])                                                 # differs from it only in its last digit
other = ''.join('0123456789abcdef'[(int(c, 16) + 8) % 16] for c in h)       # shares nothing with it
held = lambda: claim.read_bytes().decode('utf-8', 'replace').strip() if claim.exists() else None


def call(hh, design):
    places = {'real': box, 'unclaimed': inbox / 'unclaimed' / hh, 'own': inbox / hh[:16]}
    if hh[:16] == h[:16]:
        places.pop('own')                                                   # the same folder as the real engineer's inbox
    before = {k: set(txt(d)) for k, d in places.items()}
    try:
        v = V.verify(hh, design)
    except Exception as exc:
        return {'raised': type(exc).__name__}
    after = {k: set(txt(d)) for k, d in places.items()}
    added = {k: len(after[k] - before[k]) for k in after}                    # by name: notices of one second sort by verdict, not by time
    new = [(places[k] / n).read_text(encoding='utf-8') for k in places for n in sorted(after[k] - before[k])]
    return {'verdict': [v['verdict'], v['reason_code'], v['detail']], 'added': added, 'own_inbox_made': (inbox / hh[:16]).exists() if hh[:16] != h[:16] else None,
            'notices': [[t.splitlines()[0], t.splitlines()[-1]] for t in new]}


out['claim_after_start'] = held()
for k, hh in (('made', made), ('last', last), ('other', other)):
    out[k] = call(hh, BAD)
out['real'] = call(h, dict(BAD, wall_mm=3.2))
claim.unlink(missing_ok=True); importlib.reload(V); out['claim_after_restart'] = held()   # started again, with an inbox that holds notices and no hash
claim.unlink(missing_ok=True); out['made_with_no_claim'] = call(made, dict(BAD, wall_mm=3.25)); out['claim_after_made'] = held()
out['pass_with_no_claim'] = call(h, GOOD); out['claim_after_pass'] = held()
d = V.HOME / 'baselines' / h; aside = d.with_name(d.name + '.aside'); d.rename(aside)
out['folder_gone'] = call(h, dict(BAD, wall_mm=3.3)); aside.rename(d)
claim.write_text(made + '\n'); out['foreign_claim'] = call(h, dict(BAD, wall_mm=3.35)); out['claim_after_foreign'] = held()
claim.unlink(missing_ok=True); card = d / 'baseline.json'; card_aside = d / 'baseline.json.aside'; card.rename(card_aside)
out['card_gone_no_claim'] = call(h, dict(BAD, wall_mm=3.4)); card_aside.rename(card); out['claim_after_card_gone'] = held()
real_is_dir, real_read_text = pathlib.Path.is_dir, pathlib.Path.read_text
under = lambda p: p.parent == V.HOME / 'baselines'                        # as when the folder of baselines cannot be searched


def refusing(self):
    if under(self):
        raise PermissionError('the folder of baselines cannot be searched')
    return real_is_dir(self)


def unreadable(self, *a, **k):
    if under(self.parent):
        raise PermissionError('the folder of baselines cannot be searched')
    return real_read_text(self, *a, **k)
pathlib.Path.is_dir, pathlib.Path.read_text = refusing, unreadable
out['baselines_unsearchable'] = call(h, dict(BAD, wall_mm=3.45)); out['made_unsearchable'] = call(made, dict(BAD, wall_mm=3.47))
pathlib.Path.is_dir, pathlib.Path.read_text = real_is_dir, real_read_text
claim.write_text(''); out['empty_claim'] = call(h, dict(BAD, wall_mm=3.5)); out['claim_after_empty'] = held()
claim.write_bytes(b'\xff\xfe\n'); out['bad_claim'] = call(h, dict(BAD, wall_mm=3.55)); out['claim_after_bad'] = held()
claim.write_text('not a hash\n'); out['garbage_claim'] = call(h, dict(BAD, wall_mm=3.6)); out['claim_after_garbage'] = held()
claim.unlink(missing_ok=True); claim.mkdir(); out['claim_folder'] = call(h, dict(BAD, wall_mm=3.62))       # a folder where the hash file should be
out['left_with_claim_folder'] = sorted(p.name for p in box.iterdir() if not p.name.endswith('.txt')); claim.rmdir()
real_link = os.link


def no_links(*a, **k):
    raise PermissionError('this file system makes no hard links')
claim.unlink(missing_ok=True); os.link = no_links; out['no_links'] = call(h, dict(BAD, wall_mm=3.65)); os.link = real_link
out['claim_after_no_links'] = held(); out['left_in_inbox'] = sorted(p.name for p in box.iterdir() if not p.name.endswith('.txt'))
out['h'], out['made_h'], out['last_h'], out['other_h'] = h, made, last, other
print(json.dumps(out))
"""


def r19():
    """A notice reaches an engineer's inbox only for that engineer's own baseline: a request naming a hash the service holds no baseline for, even one that shares all but one digit of a real baseline's, is answered UNKNOWN and its notice is kept apart, addressed to no engineer; and a notice about a real baseline still reaches its engineer while the service can find its folder or read its full hash in its inbox.  (Amendment 6.)"""
    s = deploy.Services(OUT / 'R19'); e = {}
    try:
        env = s.baseline(CASE, draft()); h = env['baseline_sha256']
        box = s.home / 'inbox' / h[:16]; claim = box / 'baseline_sha256'
        e['inbox_at_baselining'] = sorted(p.name for p in box.iterdir()) if box.is_dir() else None
        e['claim_at_baselining'] = claim.read_text().strip() if claim.exists() else None
        if claim.exists():
            claim.unlink()                                                  # as for a baseline made before Amendment 6: the tool, starting, must claim it
        if box.is_dir() and not any(box.iterdir()):
            box.rmdir()                                                     # and with no inbox at all, as before its first notice
        script = OUT / 'R19' / 'inside.py'; script.write_text(INSIDE19)
        base = dict(os.environ, VERIFY_HOME=str(s.home), VERIFY_ENGINEER_KEYS=s.engineer.public_hex); base.pop('PLEA_CRASH_AT', None)
        out = subprocess.run([PY, '-B', str(script), str(GATEWAY), h], capture_output=True, text=True, timeout=120, env=base)
        got = json.loads(out.stdout) if out.returncode == 0 and out.stdout.strip() else {'failed': (out.stdout + out.stderr)[-300:].replace(str(GATEWAY), '<tree>')}
        e['got'] = got
        g = lambda k: got.get(k) or {}
        none_stored = 'no signed baseline with this hash is held by the verification service (none is stored under this hash)'
        not_opened = 'no signed baseline with this hash is held by the verification service (the stored file could not be opened)'
        nobody = lambda hh: [f'To: no engineer: the verification service found no baseline folder for the hash {hh}, and read it in no inbox',
                             'No check was run.  This is not a pass.  This notice is kept by the service and sent to nobody.']
        kept = lambda r, hh: r.get('verdict') == ['UNKNOWN', 'BASELINE_MISMATCH', none_stored] and r.get('notices') == [nobody(hh)]
        to_engineer = lambda r, verdict: r.get('verdict', [None, None])[:2] == verdict and r.get('added', {}).get('real') == 1 and r.get('added', {}).get('unclaimed') == 0
        checks = {'when a baseline is made, its engineer\'s inbox is made with it, holds no notice, and holds the baseline\'s full hash; when the gate\'s tool starts, a baseline with no inbox, or with one that holds notices and no hash, as for a baseline made before this amendment, is given an inbox that holds it':
                      e['inbox_at_baselining'] == ['baseline_sha256'] and e['claim_at_baselining'] == h and got.get('claim_after_start') == h and got.get('claim_after_restart') == h,
                  'requests naming hashes the service holds no baseline for (one sharing the real hash\'s first 64 bits, one differing from it only in its last digit, one sharing nothing) are answered UNKNOWN, saying none is stored, or, while the service cannot look in its folder of baselines, that the stored file could not be opened; each notice is kept apart under its own hash, addressed to no engineer, and nothing is added to the real engineer\'s inbox, even while the service cannot look in its folder of baselines':
                      kept(g('made'), got.get('made_h')) and g('made').get('added') == {'real': 0, 'unclaimed': 1}
                      and g('made_unsearchable').get('verdict') == ['UNKNOWN', 'BASELINE_MISMATCH', not_opened] and g('made_unsearchable').get('added') == {'real': 0, 'unclaimed': 1}
                      and g('made_unsearchable').get('notices') == [nobody(got.get('made_h'))]
                      and kept(g('last'), got.get('last_h')) and g('last').get('added') == {'real': 0, 'unclaimed': 1}
                      and kept(g('other'), got.get('other_h')) and g('other').get('added') == {'real': 0, 'unclaimed': 1, 'own': 0} and g('other').get('own_inbox_made') is False,
                  'a failure on the real baseline goes to its engineer\'s inbox': to_engineer(g('real'), ['FAIL', 'LIMIT_NOT_MET']),
                  'while the real engineer\'s inbox holds no hash, a made-up hash that shares its name still does not reach it; and any run on the real baseline, a pass included, writes the hash again, also where the file system makes no hard links, and leaves nothing else in the inbox':
                      kept(g('made_with_no_claim'), got.get('made_h')) and g('made_with_no_claim').get('added') == {'real': 0, 'unclaimed': 1} and got.get('claim_after_made') is None
                      and g('pass_with_no_claim').get('verdict', [None])[0] == 'PASS' and got.get('claim_after_pass') == h
                      and to_engineer(g('no_links'), ['FAIL', 'LIMIT_NOT_MET']) and got.get('claim_after_no_links') == h and got.get('left_in_inbox') == ['baseline_sha256'],
                  'with the baseline\'s folder taken away, a run on its hash is answered UNKNOWN, saying none is stored, and its notice still goes to its engineer, by the hash its inbox holds, saying the baseline should be restored':
                      to_engineer(g('folder_gone'), ['UNKNOWN', 'BASELINE_MISMATCH']) and g('folder_gone').get('verdict', [None] * 3)[2] == none_stored
                      and g('folder_gone').get('notices') == [[f'To: the responsible engineer for baseline {h}', 'No check was run.  This is not a pass.  Nothing is stored under this hash; the baseline should be restored, or a revised one issued.']],
                  'an inbox that holds another baseline\'s hash, as two baselines sharing their first 64 bits would share one, still takes the notices of a baseline whose folder the gate holds, and its hash is not replaced':
                      to_engineer(g('foreign_claim'), ['FAIL', 'LIMIT_NOT_MET']) and got.get('claim_after_foreign') == got.get('made_h'),
                  'with the stored card taken away and the inbox holding no hash, the reason saying the stored file could not be opened; with the service unable to look in its folder of baselines, the reason saying so too and the notice that the stored baseline should be inspected; with a hash file that is empty, as a crash could leave, not text, or not a hash; or with a folder in its place: each notice still reaches the engineer, the hash is written again where it can be, and no temporary file is left':
                      to_engineer(g('card_gone_no_claim'), ['UNKNOWN', 'BASELINE_MISMATCH']) and g('card_gone_no_claim').get('verdict', [None] * 3)[2] == not_opened and got.get('claim_after_card_gone') == h
                      and to_engineer(g('baselines_unsearchable'), ['UNKNOWN', 'BASELINE_MISMATCH']) and g('baselines_unsearchable').get('verdict', [None] * 3)[2] == not_opened
                      and g('baselines_unsearchable').get('notices') == [[f'To: the responsible engineer for baseline {h}', 'No check was run.  This is not a pass.  The stored baseline should be inspected.']]
                      and to_engineer(g('claim_folder'), ['FAIL', 'LIMIT_NOT_MET']) and got.get('left_with_claim_folder') == ['baseline_sha256']
                      and all(to_engineer(g(k), ['FAIL', 'LIMIT_NOT_MET']) and got.get(c) == h for k, c in (('empty_claim', 'claim_after_empty'), ('bad_claim', 'claim_after_bad'), ('garbage_claim', 'claim_after_garbage')))}
    finally:
        s.stop()
    return checks, e


INSIDE20 = r"""
import errno, json, os, pathlib, sys
sys.path[:0] = [sys.argv[1], str(pathlib.Path(sys.argv[1]) / 'verify')]
import verify_tools as V                                                   # the tool starts here, as the gate host starts it
h = sys.argv[2]; out = {}
BAD = {'material': 'PA66-GF30', 'wall_mm': 3, 'mode': 'normal'}
box = V.HOME / 'inbox' / h[:16]; und = V.HOME / 'undelivered' / h
real_link, real_open, real_write = os.link, pathlib.Path.open, pathlib.Path.write_text


def inside(p, *folders):
    return any(str(p) == str(f) or str(p).startswith(str(f) + os.sep) for f in folders)


def texts(d):
    return {p.name: p.read_text(encoding='utf-8') for p in d.glob('*.txt')} if d.is_dir() else {}


def dots(*folders):
    return sorted(n for d in folders if d.is_dir() for n in os.listdir(d) if n.startswith('.'))


def run(wall):
    before_box, before_und = set(texts(box)), set(texts(und))
    try:
        v = V.verify(h, dict(BAD, wall_mm=wall))
    except Exception as exc:
        return {'raised': type(exc).__name__}
    new_box = {k: t for k, t in texts(box).items() if k not in before_box}
    new_und = {k: t for k, t in texts(und).items() if k not in before_und}
    return {'verdict': [v['verdict'], v['reason_code']], 'notice': v.get('notice'), 'in_inbox': sorted(new_box), 'in_undelivered': sorted(new_und),
            'texts': list(new_box.values()) + list(new_und.values()), 'dots': dots(box, und)}


# 1. the inbox is a file in place of its folder
aside = box.with_name(box.name + '.aside'); box.rename(aside); box.write_text('a file in place of the folder\n')
out['inbox_is_a_file'] = run(3.2)
box.unlink(); aside.rename(box)


# 2. the inbox refuses writes, as one made by another account would
def refused_link(src, dst, *a, **k):
    if inside(dst, box):
        raise PermissionError(errno.EACCES, 'the inbox is made by another account')
    return real_link(src, dst, *a, **k)


def refused_open(self, *a, **k):
    mode = a[0] if a else k.get('mode', 'r')
    if inside(self, box) and any(c in mode for c in 'wxa+'):
        raise PermissionError(errno.EACCES, 'the inbox is made by another account')
    return real_open(self, *a, **k)


def refused_write(self, *a, **k):
    if inside(self, box):
        raise PermissionError(errno.EACCES, 'the inbox is made by another account')
    return real_write(self, *a, **k)


os.link, pathlib.Path.open, pathlib.Path.write_text = refused_link, refused_open, refused_write
out['inbox_refuses'] = run(3.25)
os.link, pathlib.Path.open, pathlib.Path.write_text = real_link, real_open, real_write


# 3. the disk fills part-way through the copy in the inbox: nothing partial may be left behind
def full_disk(self, data, *a, **k):
    if inside(self, box) and self.name.startswith('.notice'):
        real_write(self, data[: len(data) // 2], *a, **k)
        raise OSError(errno.ENOSPC, 'No space left on device')
    return real_write(self, data, *a, **k)


pathlib.Path.write_text = full_disk
out['disk_fills'] = run(3.3)
pathlib.Path.write_text = real_write


# 4. nothing at all can be written, the inbox or the service's own store
def refused_link_all(src, dst, *a, **k):
    if inside(dst, box, und):
        raise PermissionError(errno.EACCES, 'no place takes the notice')
    return real_link(src, dst, *a, **k)


def refused_open_all(self, *a, **k):
    mode = a[0] if a else k.get('mode', 'r')
    if inside(self, box, und) and any(c in mode for c in 'wxa+'):
        raise PermissionError(errno.EACCES, 'no place takes the notice')
    return real_open(self, *a, **k)


def refused_write_all(self, *a, **k):
    if inside(self, box, und):
        raise PermissionError(errno.EACCES, 'no place takes the notice')
    return real_write(self, *a, **k)


os.link, pathlib.Path.open, pathlib.Path.write_text = refused_link_all, refused_open_all, refused_write_all
out['nothing_writes'] = run(3.35)
os.link, pathlib.Path.open, pathlib.Path.write_text = real_link, real_open, real_write

# 5. the ledger cannot be written
real_ledger = V.LEDGER
V.LEDGER = V.HOME / 'ledger-kept-as-a-folder'; V.LEDGER.mkdir(exist_ok=True)
out['ledger_refuses'] = run(3.4)
V.LEDGER = real_ledger

# 6. a card the notice text cannot be built from
real_face = V.face


def broken_face(*a, **k):
    raise RuntimeError('the card cannot be shown')


V.face = broken_face
out['face_breaks'] = run(3.45)
V.face = real_face

# 8. the ledger and the error output both fail: the verdict is still returned
class BrokenStream:
    def write(self, *a, **k):
        raise OSError(errno.ENOSPC, 'No space left on device')

    def flush(self):
        raise OSError(errno.ENOSPC, 'No space left on device')


real_stderr, real_ledger = sys.stderr, V.LEDGER
V.LEDGER = V.HOME / 'ledger-kept-as-a-folder'; V.LEDGER.mkdir(exist_ok=True)
sys.stderr = BrokenStream()
out['ledger_and_stderr'] = run(3.55)
sys.stderr = real_stderr; V.LEDGER = real_ledger


# 9. one notice held under one name is one copy across the inbox and the service's own store
aside = box.with_name(box.name + '.aside'); box.rename(aside); box.write_text('a file in place of the folder\n')
first = list(V.notices.deliver(V.HOME, h, 'INTERRUPTED_one', lambda engineer: 'one copy\n', numbered=False))
box.unlink(); aside.rename(box)
second = list(V.notices.deliver(V.HOME, h, 'INTERRUPTED_one', lambda engineer: 'one copy\n', numbered=False))
out['one_copy'] = {'first': first, 'second': second,
                   'in_inbox': sorted(n for n in os.listdir(box) if n.startswith('INTERRUPTED_one')) if box.is_dir() else [],
                   'in_store': sorted(n for n in os.listdir(und) if n.startswith('INTERRUPTED_one')) if und.is_dir() else []}


# 10. a write stopped part-way, with no hard links: no notice is left under its name
real_link = os.link


def no_links(*a, **k):
    raise PermissionError(errno.EPERM, 'this file system makes no hard links')


class Stopped:
    def __init__(self, f):
        self.f = f

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.f.close()
        return False

    def write(self, data):
        self.f.write(data[: len(data) // 2]); self.f.flush()
        raise KeyboardInterrupt()


def open_stopped(self, *a, **k):
    if inside(self, box) and a and 'x' in a[0]:
        return Stopped(real_open(self, *a, **k))
    return real_open(self, *a, **k)


before = set(texts(box))
os.link, pathlib.Path.open = no_links, open_stopped
try:
    V.verify(h, dict(BAD, wall_mm=3.65)); raised = 'none'
except BaseException as exc:
    raised = type(exc).__name__
os.link, pathlib.Path.open = real_link, real_open
out['stopped'] = {'raised': raised, 'new': sorted(set(texts(box)) - before), 'dots': dots(box, und)}


# 7. the normal run, as a control
out['normal'] = run(3.5)
print(json.dumps(out))
"""


def r20():
    """A notice that cannot be written does not stop a run or lose its verdict: it goes to the service's own store, whole, and the verdict says where it went; where nothing can be written, the verdict says so; a ledger that cannot be written does not stop a run; a card whose notice text cannot be built still gets its notice, in fixed words.  (Amendment 7, D2 and D3.)"""
    s = deploy.Services(OUT / 'R20'); e = {}
    try:
        env = s.baseline(CASE, draft()); h = env['baseline_sha256']
        script = OUT / 'R20' / 'inside20.py'; script.write_text(INSIDE20)
        base = dict(os.environ, VERIFY_HOME=str(s.home), VERIFY_ENGINEER_KEYS=s.engineer.public_hex); base.pop('PLEA_CRASH_AT', None)
        out = subprocess.run([PY, '-B', str(script), str(GATEWAY), h], capture_output=True, text=True, timeout=120, env=base)
        got = json.loads(out.stdout) if out.returncode == 0 and out.stdout.strip() else {'failed': (out.stdout + out.stderr)[-300:].replace(str(GATEWAY), '<tree>')}
        e['got'] = got
        g = lambda k: got.get(k) or {}
        fail = ['FAIL', 'LIMIT_NOT_MET']
        words = 'FAIL: REQUIREMENT NOT MET'
        whole = lambda r: len(r.get('in_undelivered', [])) == 1 and bool(r.get('texts')) and r['texts'][0].endswith('\n') and words in r['texts'][0]
        keys = ('inbox_is_a_file', 'inbox_refuses', 'disk_fills', 'nothing_writes', 'ledger_refuses', 'face_breaks', 'normal', 'ledger_and_stderr')
        checks = {'the inbox is a file in place of its folder: the verdict is returned, the notice is kept in the service\'s own store, whole, and the verdict says where it went':
                      g('inbox_is_a_file').get('verdict') == fail and g('inbox_is_a_file').get('notice') == 'UNDELIVERED' and not g('inbox_is_a_file').get('in_inbox')
                      and whole(g('inbox_is_a_file')),
                  'the inbox refuses writes, as one made by another account would: the same, with the notice whole in the service\'s own store':
                      g('inbox_refuses').get('verdict') == fail and g('inbox_refuses').get('notice') == 'UNDELIVERED' and not g('inbox_refuses').get('in_inbox')
                      and whole(g('inbox_refuses')),
                  'the disk fills part-way through the inbox\'s copy: the notice kept is whole, and no partial notice is left in either place':
                      g('disk_fills').get('verdict') == fail and g('disk_fills').get('notice') == 'UNDELIVERED' and not g('disk_fills').get('in_inbox')
                      and whole(g('disk_fills')),
                  'where nothing can be written, the verdict is still returned and says so, and nothing is raised':
                      g('nothing_writes').get('verdict') == fail and g('nothing_writes').get('notice') == 'NOT_WRITTEN' and 'raised' not in g('nothing_writes'),
                  'a ledger that cannot be written does not stop a run: the verdict is returned and its notice is in the inbox':
                      g('ledger_refuses').get('verdict') == fail and g('ledger_refuses').get('notice') == 'INBOX'
                      and len(g('ledger_refuses').get('in_inbox', [])) == 1 and 'raised' not in g('ledger_refuses'),
                  'a card whose notice text cannot be built gets its notice in fixed words, in the inbox, and the words repeat none of the card\'s text':
                      g('face_breaks').get('notice') == 'INBOX' and any('NOTICE COULD NOT BE SHOWN IN FULL' in t for t in g('face_breaks').get('texts', []))
                      and 'raised' not in g('face_breaks') and 'Requirement   ' not in ''.join(g('face_breaks').get('texts', [])),
                  'a normal failing run is unchanged: its notice is in the inbox, whole, with the card\'s own text':
                      g('normal').get('notice') == 'INBOX' and len(g('normal').get('in_inbox', [])) == 1 and words in (g('normal').get('texts') or [''])[0],
                  'the error output may fail too: the verdict is still returned, and its notice is in the inbox':
                      g('ledger_and_stderr').get('verdict') == fail and g('ledger_and_stderr').get('notice') == 'INBOX' and 'raised' not in g('ledger_and_stderr'),
                  'a notice held under one name is one copy: a repeat is reported where that copy is, and no second copy is made':
                      g('one_copy').get('first') == ['UNDELIVERED', 'INTERRUPTED_one.txt'] and g('one_copy').get('second') == ['UNDELIVERED', 'INTERRUPTED_one.txt']
                      and g('one_copy').get('in_inbox') == [] and g('one_copy').get('in_store') == ['INTERRUPTED_one.txt'],
                  'a write stopped part-way, with no hard links, leaves no notice under its name and no temporary file': g('stopped').get('raised') == 'KeyboardInterrupt'
                      and g('stopped').get('new') == [] and not g('stopped').get('dots'),
                  'every run returned a verdict, and no temporary file was left in any place': 'failed' not in got
                      and all('raised' not in g(k) and not g(k).get('dots') for k in keys)}
    finally:
        s.stop()
    return checks, e


INSIDE21 = r"""
import json, pathlib, sys
sys.path[:0] = [sys.argv[1], str(pathlib.Path(sys.argv[1]) / 'verify')]
import verify_tools as V
h = sys.argv[2]
v = V.verify(h, {'material': 'PA66-GF30', 'wall_mm': 3, 'mode': 'normal'})
box = V.HOME / 'inbox' / h[:16]
print(json.dumps({'verdict': [v['verdict'], v['reason_code'], v['detail']], 'notice': v.get('notice'),
                  'texts': [p.read_text(encoding='utf-8') for p in sorted(box.glob('*.txt'))]}))
"""


def r21():
    """A check whose stated limits are not text cannot be baselined, and a card signed that way is refused at every run, as not a baseline card, with its notice in the engineer's inbox and no error raised.  (Amendment 7, D4.)"""
    s = deploy.Services(OUT / 'R21'); e = {}
    try:
        bad = draft(); bad['check'] = dict(bad['check'], stated_limits=[42])
        try:
            verify_ctl.make_baseline(s.home, CASE, bad, s.engineer)
            refused = None
        except B.BaselineInvalid as exc:
            refused = str(exc)
        env = s.baseline(CASE, draft()); h = env['baseline_sha256']
        card = json.loads(json.dumps(env['card'])); card['check']['stated_limits'] = [42]
        signed = sign_envelope(card, env['controls_run'], s.engineer)
        h2 = signed['baseline_sha256']
        (s.home / 'baselines' / h2).mkdir(parents=True, exist_ok=True)
        (s.home / 'baselines' / h2 / 'baseline.json').write_text(json.dumps(signed, indent=1) + '\n')
        script = OUT / 'R21' / 'inside21.py'; script.write_text(INSIDE21)
        base = dict(os.environ, VERIFY_HOME=str(s.home), VERIFY_ENGINEER_KEYS=s.engineer.public_hex); base.pop('PLEA_CRASH_AT', None)
        out = subprocess.run([PY, '-B', str(script), str(GATEWAY), h2], capture_output=True, text=True, timeout=120, env=base)
        got = json.loads(out.stdout) if out.returncode == 0 and out.stdout.strip() else {'failed': (out.stdout + out.stderr)[-300:].replace(str(GATEWAY), '<tree>')}
        e.update(refused=refused, got=got)
        verdict = got.get('verdict') or [None, None, '']
        checks = {'the console will not baseline a check whose stated limits are not text, and says why': refused is not None and 'stated_limits' in refused,
                  'a card signed that way anyway is refused at the run as not a baseline card: UNKNOWN, no check run, and its notice is in the engineer\'s inbox':
                      verdict[:2] == ['UNKNOWN', 'BASELINE_MISMATCH'] and 'not a baseline card' in verdict[2] and got.get('notice') == 'INBOX' and len(got.get('texts', [])) == 1,
                  'the run raises no error, and the notice is the no-usable-baseline notice': 'failed' not in got and any('NO USABLE BASELINE IS HELD' in t for t in got.get('texts', []))}
    finally:
        s.stop()
    return checks, e


INSIDE22 = r"""
import errno, json, os, pathlib, shutil, sys, time
sys.path[:0] = [sys.argv[1], str(pathlib.Path(sys.argv[1]) / 'verify')]
import verify_tools as V                                                   # the tool starts here, as the gate host starts it
import notices as N
h = sys.argv[2]; out = {}
BAD = {'material': 'PA66-GF30', 'wall_mm': 3, 'mode': 'normal'}
box = V.HOME / 'inbox' / h[:16]; proof = V.HOME / 'inbox_checks' / (h + '.json')
read = lambda: json.loads(proof.read_text()) if proof.is_file() else {}
state = lambda **k: N.delivery_state(V.HOME, h, **k)[0]
rest = lambda d: sorted(n for n in os.listdir(d) if not n.endswith('.txt')) if d.is_dir() else None


def reading():
    try:
        return state()
    except Exception as exc:                                                   # a proof that stops the reader is a reading too
        return 'RAISED ' + type(exc).__name__


class Tee:                                                                     # what the tool says on its error output, kept in order as it is said
    def __init__(self, real):
        self.real, self.lines = real, []

    def write(self, text):
        self.lines.append(text); return self.real.write(text)

    def flush(self):
        self.real.flush()


tee = Tee(sys.stderr); sys.stderr = tee


def until(want, seconds=8.0):
    t0 = time.time()
    while time.time() - t0 < seconds and state() != want:
        time.sleep(0.05)
    return round(time.time() - t0, 2)


# 1. as the tool starts
p = read()
out['at_start'] = {'inbox': p.get('inbox'), 'store': p.get('store'), 'names_this_baseline': p.get('baseline_sha256') == h,
                   'time_is_now': abs(time.time() - p.get('checked_at', 0)) < 30, 'state': state(), 'inbox_holds': rest(box),
                   'no_engineers_folder_holds': rest(V.HOME / 'inbox' / 'unclaimed' / ('0' * 64)),
                   'proofs_folder_holds': sorted(n for n in os.listdir(V.HOME / 'inbox_checks') if n.startswith('.'))}
for name in ('.probe.1.0123456789ab', '.notice.draft'):                        # the fresh temporary file and the engineer's own file the test put there
    (box / name).unlink(missing_ok=True)

# 2. how a proof is read
keep = proof.read_bytes(); at = json.loads(keep)['checked_at']                  # times are taken from the proof itself, not from the clock now
out['read'] = {'older_than_limit': N.delivery_state(V.HOME, h, max_age=300, now=at + 301)[0], 'within_limit': N.delivery_state(V.HOME, h, max_age=300, now=at + 299)[0],
               'dated_ahead': N.delivery_state(V.HOME, h, max_age=300, now=at - 301)[0]}
proof.write_text(json.dumps(dict(json.loads(keep), checked_at=float('nan')))); out['read']['time_not_a_number'] = reading()
proof.write_text('{"baseline_sha256": "%s", "checked_at": 1%s, "inbox": true}' % (h, '0' * 400)); out['read']['time_too_large'] = reading()
proof.write_text(json.dumps(dict(json.loads(keep), checked_at=True))); out['read']['time_a_yes'] = reading()
proof.unlink(); out['read']['missing'] = reading()
proof.write_text('not a proof'); out['read']['not_a_proof'] = reading()
proof.write_text(json.dumps(dict(json.loads(keep), baseline_sha256='0' * 64))); out['read']['another_baseline'] = reading()
proof.write_text(json.dumps(dict(json.loads(keep), inbox='yes'))); out['read']['inbox_not_true'] = reading()
proof.write_bytes(keep); out['read']['put_back'] = reading()

# 3. a file in place of the inbox: a run still gives its verdict, and the proof then says the inbox cannot be written
aside = box.with_name(box.name + '.aside'); box.rename(aside); box.write_text('a file in place of the folder\n')
try:
    v = V.verify(h, dict(BAD, wall_mm=3.2)); p = read()
    out['blocked'] = {'verdict': [v['verdict'], v['reason_code']], 'notice': v.get('notice'), 'inbox': p.get('inbox'), 'store': p.get('store'), 'state': state()}
except Exception as exc:
    out['blocked'] = {'raised': type(exc).__name__}

# 4. put back: the tool's own look proves it again, with no run, and the tool says so in this step
said_before = len(tee.lines)
box.unlink(); aside.rename(box)
out['restored'] = {'seconds': until('WRITABLE'), 'state': state(), 'inbox_holds': rest(box)}
t0 = time.time()
while time.time() - t0 < 3 and not any('can be written again' in l and h[:16] in l for l in tee.lines[said_before:]):
    time.sleep(0.05)
out['restored']['the_tool_says_so'] = any('can be written again' in l and h[:16] in l for l in tee.lines[said_before:])

# 5. a baseline folder that appears after the tool started
h2 = ''.join('0123456789abcdef'[(int(c, 16) + 5) % 16] for c in h)
shutil.copytree(V.HOME / 'baselines' / h, V.HOME / 'baselines' / h2)
os.utime(V.HOME / 'baselines' / h2, (time.time() - 60, time.time() - 60))        # as one that has had no inbox for a minute
t0 = time.time()
while time.time() - t0 < 8 and N.delivery_state(V.HOME, h2)[0] != 'WRITABLE':
    time.sleep(0.05)
claim2 = V.HOME / 'inbox' / h2[:16] / 'baseline_sha256'
out['later'] = {'seconds': round(time.time() - t0, 2), 'state': N.delivery_state(V.HOME, h2)[0], 'inbox_claims_it': claim2.is_file() and claim2.read_text().strip() == h2}
h4 = ''.join('0123456789abcdef'[(int(c, 16) + 3) % 16] for c in h)             # the same, with a folder dated an hour ahead, as by a clock since put back
shutil.copytree(V.HOME / 'baselines' / h, V.HOME / 'baselines' / h4)
os.utime(V.HOME / 'baselines' / h4, (time.time() + 3600, time.time() + 3600))
t0 = time.time()
while time.time() - t0 < 8 and N.delivery_state(V.HOME, h4)[0] != 'WRITABLE':
    time.sleep(0.05)
claim4 = V.HOME / 'inbox' / h4[:16] / 'baseline_sha256'
out['later_dated_ahead'] = {'state': N.delivery_state(V.HOME, h4)[0], 'inbox_claims_it': claim4.is_file() and claim4.read_text().strip() == h4}

# 5b. a baseline folder made this moment, with no inbox yet: its inbox is left for the console to make
h3 = ''.join('0123456789abcdef'[(int(c, 16) + 9) % 16] for c in h)
shutil.copytree(V.HOME / 'baselines' / h, V.HOME / 'baselines' / h3); os.utime(V.HOME / 'baselines' / h3)
time.sleep(2.5)                                                                 # two of the tool's own looks
box3 = V.HOME / 'inbox' / h3[:16]
out['young'] = {'inbox_made_by_the_tool': box3.exists(), 'state': N.delivery_state(V.HOME, h3)[0]}
box3.mkdir(); (box3 / 'baseline_sha256').write_text(h3 + '\n')                  # the console makes it
t0 = time.time()
while time.time() - t0 < 8 and N.delivery_state(V.HOME, h3)[0] != 'WRITABLE':
    time.sleep(0.05)
out['young_after_console'] = {'seconds': round(time.time() - t0, 2), 'state': N.delivery_state(V.HOME, h3)[0]}

# 6. a run renews the proof
before = read().get('checked_at', 0); time.sleep(0.05)
V.verify(h, dict(BAD, wall_mm=3.3)); out['renewed'] = read().get('checked_at', 0) > before

# 7. the proof cannot be recorded: a run still gives its verdict, and the state reads as not proven
left = read().get('checked_at')                                                 # the proof on file before its folder is taken away
ddir = V.HOME / 'inbox_checks'; daside = ddir.with_name('inbox_checks.aside'); ddir.rename(daside); ddir.write_text('a file in place of the folder\n')
try:
    v = V.verify(h, dict(BAD, wall_mm=3.4))
    out['unrecorded'] = {'verdict': [v['verdict'], v['reason_code']], 'notice': v.get('notice'), 'state': state()}
except Exception as exc:
    out['unrecorded'] = {'raised': type(exc).__name__}
ddir.unlink(); daside.rename(ddir)
t0 = time.time()
while time.time() - t0 < 8 and read().get('checked_at') == left:                # a proof other than the one left in the folder
    time.sleep(0.05)
out['recorded_again'] = {'seconds': round(time.time() - t0, 2), 'state': state(), 'a_new_proof_is_on_record': read().get('checked_at') != left}

# 8. the record cannot be written though its folder is there, as on a full disk: the proof left from before is not kept as good
real_replace = os.replace


def no_room(src, dst, *a, **k):
    if str(dst).startswith(str(V.HOME / 'inbox_checks')):
        raise OSError(errno.ENOSPC, 'No space left on device')
    return real_replace(src, dst, *a, **k)


os.replace = no_room
try:
    v = V.verify(h, dict(BAD, wall_mm=3.45))
    out['no_room'] = {'verdict': [v['verdict'], v['reason_code']], 'state': state(), 'left': sorted(n for n in os.listdir(V.HOME / 'inbox_checks') if n.startswith('.') and n != '.keep')}
except Exception as exc:
    out['no_room'] = {'raised': type(exc).__name__}
finally:
    os.replace = real_replace
out['room_again'] = {'seconds': until('WRITABLE'), 'state': state()}

# 9. the clock put back: this process's memory of its proof is dated an hour ahead, and the proof is made again all the same
before = read().get('checked_at', 0); V._PROVED[h] = (time.time() + 3600, True)
t0 = time.time()
while time.time() - t0 < 8 and not read().get('checked_at', 0) > before:
    time.sleep(0.05)
out['clock_put_back'] = {'seconds': round(time.time() - t0, 2), 'made_again': read().get('checked_at', 0) > before}

# 10. the baseline's folder is taken away, and its inbox still holds its hash: its notices still go there, so its proof is still made
d = V.HOME / 'baselines' / h; gone = d.with_name(d.name + '.aside'); d.rename(gone)
proof.unlink(missing_ok=True); V._PROVED.pop(h, None)
out['folder_gone'] = {'seconds': until('WRITABLE'), 'state': state()}
proof.unlink(missing_ok=True)                                                  # the proof is taken away; the tool's look is not due for 30 seconds, so only the run can make it again
try:
    v = V.verify(h, dict(BAD, wall_mm=3.5)); out['folder_gone']['run'] = [v['verdict'], v['reason_code'], v.get('notice')]
except Exception as exc:
    out['folder_gone']['run'] = ['RAISED', type(exc).__name__, None]
out['folder_gone']['after_the_run'] = state()
gone.rename(d)

# 11. the error output is closed: a run whose proof and whose ledger both have something to say still returns its verdict
class Closed:
    def write(self, *a, **k):
        raise ValueError('I/O operation on closed file')

    def flush(self):
        raise ValueError('I/O operation on closed file')


real_err, real_ledger = sys.stderr, V.LEDGER
V.LEDGER = V.HOME / 'ledger-kept-as-a-folder'; V.LEDGER.mkdir(exist_ok=True)
aside = box.with_name(box.name + '.aside'); box.rename(aside); box.write_text('a file in place of the folder\n')
sys.stderr = Closed()
try:
    v = V.verify(h, dict(BAD, wall_mm=3.6)); out['closed_output'] = {'verdict': [v['verdict'], v['reason_code']], 'notice': v.get('notice')}
except Exception as exc:
    out['closed_output'] = {'raised': type(exc).__name__}
finally:
    sys.stderr = real_err; V.LEDGER = real_ledger; box.unlink(); aside.rename(box)
until('WRITABLE')
out['h2'] = h2
print(json.dumps(out))
"""


def r22():
    """The gate's tool shows that it can write each baseline's inbox, and keeps a dated proof of it: when it starts, on every run, and by its own look for a baseline made later or an inbox it could not write; a proof that is missing, old, or says the inbox could not be written reads as not good; and the engineer's console shows which.  (Amendment 8, D3.)"""
    s = deploy.Services(OUT / 'R22'); e = {}
    try:
        env = s.baseline(CASE, draft()); h = env['baseline_sha256']
        script = OUT / 'R22' / 'inside22.py'; script.write_text(INSIDE22)
        box = s.home / 'inbox' / h[:16]; old = (time.time() - 300, time.time() - 300)
        nobody, proofs = s.home / 'inbox' / 'unclaimed' / ('0' * 64), s.home / 'inbox_checks'
        for folder in (nobody, proofs):
            folder.mkdir(parents=True, exist_ok=True)
        for left in (box / '.notice.1.0123456789ab.part', nobody / '.notice.1.0123456789ab.part', proofs / f'.{h}.json.1.0123456789ab',     # as a process killed part-way leaves them
                     box / '.notice.draft', proofs / '.keep'):                                                                           # old files that are not the service's own
            left.write_text('left minutes ago\n'); os.utime(left, old)
        (box / '.probe.1.0123456789ab').write_text('fresh\n')                    # a temporary file of the service's own, made this moment
        base = dict(os.environ, VERIFY_HOME=str(s.home), VERIFY_ENGINEER_KEYS=s.engineer.public_hex); base.pop('PLEA_CRASH_AT', None)
        for k in ('VERIFY_PROOF_SCAN', 'VERIFY_PROOF_REFRESH'):
            base.pop(k, None)                                                   # the tool's own settings
        out = subprocess.run([PY, '-B', str(script), str(GATEWAY), h], capture_output=True, text=True, timeout=180, env=base)
        got = json.loads(out.stdout) if out.returncode == 0 and out.stdout.strip() else {'failed': (out.stdout + out.stderr)[-300:].replace(str(GATEWAY), '<tree>')}
        said = [l for l in out.stderr.splitlines() if l.startswith('verify tool: ')]
        shown = verify_ctl.status(s.home, h, s.engineer.public_hex, deploy.LOCAL_DSN).splitlines()
        (s.home / 'inbox_checks' / (h + '.json')).unlink(missing_ok=True)
        shown_without = verify_ctl.status(s.home, h, s.engineer.public_hex, deploy.LOCAL_DSN).splitlines()
        e.update(got=got, said=[l[:90] for l in said], shown=[l[:110] for l in shown[1:4]], shown_without=[l[:110] for l in shown_without[1:4]])
        g = lambda k: got.get(k) or {}
        fail = ['FAIL', 'LIMIT_NOT_MET']
        checks = {'when the tool starts, a baseline it holds has an inbox-writability check on record: its inbox and the service\'s store could be written, the proof names this baseline and the present time, and the probe leaves nothing in the inbox; a temporary file that a killed process left minutes ago is taken away, from the inbox, from a folder of notices that are no engineer\'s and from the folder of proofs; a fresh one is left alone, and so is an old file that is not the service\'s own, though its name begins the same way':
                      g('at_start') == {'inbox': True, 'store': True, 'names_this_baseline': True, 'time_is_now': True, 'state': 'WRITABLE',
                                        'inbox_holds': ['.notice.draft', '.probe.1.0123456789ab', 'baseline_sha256'], 'no_engineers_folder_holds': [], 'proofs_folder_holds': ['.keep']},
                  'a proof is read as not proven when it is missing, is not a proof, names another baseline, or gives a time that is not a number that can be used; as not writable unless it says plainly that the inbox was written; and as stale when it is older than its limit or dated further ahead than that':
                      g('read') == {'older_than_limit': 'STALE', 'within_limit': 'WRITABLE', 'dated_ahead': 'STALE', 'time_not_a_number': 'UNCHECKED', 'time_too_large': 'UNCHECKED',
                                    'time_a_yes': 'UNCHECKED', 'missing': 'UNCHECKED', 'not_a_proof': 'UNCHECKED', 'another_baseline': 'UNCHECKED', 'inbox_not_true': 'NOT_WRITABLE',
                                    'put_back': 'WRITABLE'},
                  'with a file in place of the inbox, a run still returns its verdict, with its notice kept in the service\'s own store, and the proof then says the inbox cannot be written; the tool says so on its error output':
                      g('blocked') == {'verdict': fail, 'notice': 'UNDELIVERED', 'inbox': False, 'store': True, 'state': 'NOT_WRITABLE'}
                      and any('CANNOT WRITE THE INBOX' in l and h[:16] in l for l in said),
                  'put back, the inbox is proved again by the tool\'s own look, with no run, the tool says so, and nothing is left in the inbox but its hash':
                      g('restored').get('state') == 'WRITABLE' and g('restored').get('inbox_holds') == ['baseline_sha256'] and g('restored').get('the_tool_says_so') is True,
                  'a baseline folder that appears after the tool started, and has had no inbox for a minute, is given its inbox, its hash and its proof by the tool\'s own look; so is one whose folder is dated an hour ahead':
                      g('later').get('state') == 'WRITABLE' and g('later').get('inbox_claims_it') is True and g('later_dated_ahead') == {'state': 'WRITABLE', 'inbox_claims_it': True},
                  'a baseline folder made this moment, with no inbox yet, is left for the console: the tool\'s look makes no inbox for it, and it is not proven; once the console has made the inbox, the look proves it':
                      g('young') == {'inbox_made_by_the_tool': False, 'state': 'UNCHECKED'} and g('young_after_console').get('state') == 'WRITABLE',
                  'a run on a baseline renews its proof': got.get('renewed') is True,
                  'where the proof cannot be recorded, a run still returns its verdict and its notice, the state reads as not proven, and the tool says so; once it can be recorded, it is':
                      g('unrecorded') == {'verdict': fail, 'notice': 'INBOX', 'state': 'UNCHECKED'} and any('CANNOT RECORD THE INBOX-WRITABILITY CHECK' in l for l in said)
                      and g('recorded_again').get('state') == 'WRITABLE' and g('recorded_again').get('a_new_proof_is_on_record') is True,
                  'where the record cannot be written though its folder is there, as on a full disk, the proof left from before is not kept as good: the state reads as not proven at once, nothing is left beside it, and it is proved again once it can be':
                      g('no_room') == {'verdict': fail, 'state': 'UNCHECKED', 'left': []} and g('room_again').get('state') == 'WRITABLE',
                  'with the clock put back, so that the tool\'s memory of its proof is dated an hour ahead, the proof is made again all the same':
                      g('clock_put_back').get('made_again') is True,
                  'with the baseline\'s folder taken away and its inbox still holding its hash, its proof is still made by the tool\'s own look, and a run on it is answered UNKNOWN with its notice in that inbox, as before this amendment':
                      g('folder_gone').get('state') == 'WRITABLE' and g('folder_gone').get('run') == ['UNKNOWN', 'BASELINE_MISMATCH', 'INBOX'] and g('folder_gone').get('after_the_run') == 'WRITABLE',
                  'with the error output closed, a run whose proof and whose ledger both have something to say still returns its verdict and keeps its notice':
                      g('closed_output') == {'verdict': fail, 'notice': 'UNDELIVERED'},
                  'the engineer\'s console shows the state: proven, with its time; and, with the proof taken away, not proven, saying that new runs are refused':
                      any(l.startswith('inbox writable: the gate wrote a test file in this inbox at 20') and 'This is not delivery' in l for l in shown) and not any('INBOX NOT CHECKED' in l for l in shown)
                      and any(l.startswith('INBOX NOT CHECKED: the verification service has not shown') and 'new runs through the front door are refused' in l for l in shown_without)}
    finally:
        s.stop()
    return checks, e


def r23():
    """A requirement the service already holds a baseline for is changed by a revision, which is linked as before, or baselined again only with the engineer's reason; the reason, and the baselines already held, go into the signed card, and the record's checker and the first client's view of the requirement print them.  (Amendment 9.)"""
    s = deploy.Services(OUT / 'R23').start(); e = {}
    try:
        first = s.baseline(CASE, draft()); h1 = first['baseline_sha256']; req = first['card']['requirement']; rid = req['id']
        relaxed = lambda limit: draft(criteria=[dict(draft()['criteria'][0], limit=limit)])           # the same requirement, a lower limit; the controls still fail and pass
        folders = lambda: sorted(p.name for p in (s.home / 'baselines').iterdir())
        boxes = lambda: sorted(p.name for p in (s.home / 'inbox').iterdir()) if (s.home / 'inbox').exists() else []
        before, boxes_before = folders(), boxes()

        def attempt(d, reason=None):                                                 # any error is an answer here, so that a defect fails a check
            try:
                return s.baseline(CASE, d, alongside_reason=reason)
            except Exception as exc:
                return str(exc) if isinstance(exc, B.BaselineInvalid) else f'{type(exc).__name__}: {exc}'

        def revised(d, old, why_):
            try:
                return verify_ctl.revise(s.home, CASE, d, s.engineer, old, why_)
            except Exception as exc:
                return f'{type(exc).__name__}: {exc}'
        card_of = lambda x: x['card'] if isinstance(x, dict) else {}
        refused, blank = attempt(relaxed('190')), attempt(relaxed('190'), '   ')
        after, boxes_after = folders(), boxes()
        why = 'A second bracket of the same part, rated for a lower temperature (CR-23).'
        second = attempt(relaxed('190'), why); h2 = second['baseline_sha256'] if isinstance(second, dict) else None
        side = second['card'].get('alongside') if isinstance(second, dict) else None
        signed = load_envelope(s.home / 'baselines' / h2 / 'baseline.json', s.keys['engineer'])['card'].get('alongside') if h2 else None
        rev = revised(draft(requirement=dict(req, revision='B')), h1, 'The bracket was strengthened (CR-24).'); h3 = rev['baseline_sha256'] if isinstance(rev, dict) else None
        third = attempt(relaxed('195'), 'Another variant of the part (CR-25).')
        other = attempt(draft(requirement=dict(req, id='REQ-SELFTEST-023')))
        keyfile = OUT / 'R23' / 'engineer.key'; keyfile.write_text(s.engineer.private_hex + '\n')
        cardfile = OUT / 'R23' / 'draft.json'; cardfile.write_text(json.dumps(relaxed('185')))
        count_before_cli = len(folders())
        cli = subprocess.run([PY, '-B', str(GATEWAY / 'verify' / 'verify_ctl.py'), 'baseline', str(s.home), '--from', str(CASE), '--card', str(cardfile), '--key', str(keyfile)],
                             capture_output=True, text=True, timeout=120)
        count_after_cli = len(folders())
        alike = [attempt(draft(requirement=dict(req, id=v))) for v in (' req-selftest-001', 'ＲＥＱ-SELFTEST-001', 'REQ-SELFTEST-001\t', 'REQ\u200b-SELFTEST-001', 'REQ\u2011SELFTEST\u2212001', 'REQ-SELFTEST-001\ufe0f')]
        # case and space; full-width letters; a tab; a zero-width space; a non-breaking hyphen and a minus sign; a variation selector
        fake = {'reason': 'Written in the draft, not by the service.', 'baselines': [{'baseline_sha256': 'ab' * 32, 'revision': 'Z'}]}
        from_draft = attempt(dict(draft(requirement=dict(req, id='REQ-SELFTEST-024')), alongside=fake))
        rev_draft = revised(dict(draft(requirement=dict(req, revision='C')), alongside=fake), h3, 'Strengthened again (CR-26).') if h3 else 'no revision B'
        forged_id = 'REQ-SELFTEST-025'; forged = s.home / 'baselines' / ('cd' * 32)
        forged.mkdir(); forged.joinpath('baseline.json').write_text(json.dumps({'baseline_sha256': 'cd' * 32, 'card': dict(first['card'], requirement=dict(req, id=forged_id)),
                                                                                'controls_run': [], 'signature': {'signer': s.keys['engineer'], 'signature': '00' * 64}}))   # a signature that does not verify
        after_forged = attempt(draft(requirement=dict(req, id=forged_id)))
        colleague = Key(); other_id = 'REQ-SELFTEST-026'                                    # another engineer of the service, with a key of their own
        fenv = sign_envelope(dict(first['card'], requirement=dict(req, id=other_id), responsible_engineer={'name': 'A Colleague', 'key': colleague.public_hex}), [], colleague)
        (s.home / 'baselines' / fenv['baseline_sha256']).mkdir(); (s.home / 'baselines' / fenv['baseline_sha256'] / 'baseline.json').write_text(json.dumps(fenv))
        after_colleague = attempt(draft(requirement=dict(req, id=other_id)))
        rec = s.record(h2); ok, checks_2, summary = check_record.verify(rec, s.keys)
        printed = check_record.render(ok, checks_2, summary)
        shown = verify_client.Client(s.client_config(OUT / 'R23' / 'workspace', h2)).show()
        door_text = front_door.requirement_text(card_of(second), h2) if isinstance(second, dict) else ''
        door_fields = front_door.requirement_fields(card_of(second)).get('alongside') if isinstance(second, dict) else None
        link = f'  ALSO BASELINED FOR THIS REQUIREMENT, NOT AS A REVISION OF IT: {h1[:16]}… (rev A).  Reason given by the engineer: {why}'

        def rejects(card):
            try:
                B.validate_card(card); return False
            except B.BaselineInvalid:
                return True
        c2 = card_of(second)
        malformed = [dict(c2, alongside=dict(side or {}, reason='  ')), dict(c2, alongside=dict(side or {}, baselines=[])),
                     dict(c2, alongside=dict(side or {}, baselines=[{'baseline_sha256': 'x' * 64, 'revision': 'A'}])), dict(c2, alongside='yes')]
        e.update(refused=refused[:260] if isinstance(refused, str) else 'baselined', blank=blank[:120] if isinstance(blank, str) else 'baselined', side=side,
                 third=sorted(str(b.get('baseline_sha256'))[:16] for b in ((card_of(third).get('alongside') or {}).get('baselines') or [])),
                 alike=[x[:90] if isinstance(x, str) else 'baselined' for x in alike], from_draft=card_of(from_draft).get('alongside', 'none'), rev_draft=card_of(rev_draft).get('alongside', 'none') if isinstance(rev_draft, dict) else rev_draft[:120],
                 after_forged=list(card_of(after_forged)) if isinstance(after_forged, dict) else after_forged[:160], after_colleague=after_colleague[:200] if isinstance(after_colleague, str) else 'baselined', door=[l for l in door_text.splitlines() if 'ALSO BASELINED' in l], door_fields=door_fields,
                 other=list(other['card']) if isinstance(other, dict) else other, cli=(cli.returncode, cli.stderr[-260:]), record_ok=ok,
                 printed=[l for l in printed.splitlines() if 'ALSO BASELINED' in l], shown=[l for l in shown.splitlines() if 'ALSO BASELINED' in l])
        checks = {'a second baseline for a requirement the service holds, not made as a revision, is refused without a reason, or with a blank one; the refusal names the baseline held and says to revise it or give a reason; nothing is stored and no inbox is made':
                      isinstance(refused, str) and rid in refused and h1[:16] in refused and 'revise' in refused and '--alongside-reason' in refused
                      and isinstance(blank, str) and 'already has a baseline' in blank and after == before and boxes_after == boxes_before,
                  'with the engineer\'s reason it is baselined, and its signed card names the baseline held, with its revision, and the reason':
                      side == {'reason': why, 'baselines': [{'baseline_sha256': h1, 'revision': 'A'}]} and signed == side,
                  'a revision needs no reason and is linked as before, and its card has no such field': isinstance(rev, dict) and 'alongside' not in rev['card'] and rev['card']['supersedes']['baseline_sha256'] == h1,
                  'a later baseline made as new names every baseline the service holds for the requirement': e['third'] == sorted(str(x)[:16] for x in (h1, h2, h3)),
                  'a baseline for another requirement needs no reason, and its card has no such field, as a first baseline\'s has none': isinstance(other, dict) and 'alongside' not in other['card'] and 'alongside' not in first['card'],
                  'the record\'s checker, on a record that verifies, the first client\'s view of the requirement and the front door\'s, in its text and its fields, each give the link and the reason':
                      ok and e['printed'] == [link] and e['shown'] == [link] and e['door'] == [link] and door_fields == side and side is not None,
                  'the console\'s command line refuses such a draft without a reason, with exit status 1, and stores nothing': cli.returncode == 1 and 'already has a baseline' in cli.stderr and count_after_cli == count_before_cli,
                  'a card whose link has a blank reason, no baselines, a hash that is not one, or is not a link at all, is refused by the card\'s rules': all(rejects(c) for c in malformed),
                  'an id that differs from one held only in case, in white space or in its Unicode form is the same requirement: each such draft is refused without a reason':
                      all(isinstance(x, str) and 'already has a baseline' in x for x in alike),
                  'a link written in the draft is never signed: a first baseline for another requirement and a revision, each made from a draft that carries one, have none':
                      e['from_draft'] == 'none' and e['rev_draft'] == 'none',
                  'a baseline folder whose signature does not verify is not counted as held, and a first baseline for its requirement needs no reason; one that is whole, signed by another engineer\'s key, is counted, and a baseline for its requirement is refused without a reason':
                      isinstance(after_forged, dict) and 'alongside' not in after_forged['card'] and isinstance(after_colleague, str)
                      and 'already has a baseline' in after_colleague and fenv['baseline_sha256'][:16] in after_colleague}
    finally:
        s.stop()
    return checks, e


def r24():
    """What a person or an assistant reads of a pass calls it the declared check met, never a bare PASS, and shows what the check does not cover: the answer, the first client's status and the engineer's console.  A notice shows what the check does not cover under its headline.  The signed verdict and the record keep the word PASS.  (Amendment 9.)"""
    r = Run('R24'); e = {}
    try:
        excl = 'The check does not cover: ' + '; '.join(r.env['card']['check']['stated_limits']) + '.'
        bare = lambda t: [l for l in t.splitlines() if re.search(r'\bPASS\b', l.replace('(signed as PASS)', ''))]
        code_f, out_f = r.submit(BAD)
        mid = verify_client.Client(r.cfg).status()
        code, out = r.submit(GOOD)
        after = verify_client.Client(r.cfg).status()
        console = verify_ctl.status(r.s.home, r.h, r.s.keys['engineer'], deploy.LOCAL_DSN)
        notice = (r.s.home / 'inbox' / r.h[:16] / r.s.inbox(r.h)[0]).read_text() if r.s.inbox(r.h) else ''
        ok, checks_r, s = check_record.verify(r.record(), r.s.keys)
        printed = check_record.render(ok, checks_r, s)
        lines, nl = out.strip().splitlines(), notice.strip().splitlines()
        met_line = (f"DECLARED CHECK MET, for design {B.design_hash(GOOD)[:16]}… only.  This says what the declared check returned against the baselined limits.  "
                    'It does not say the check is correct, the requirement is complete, or the design is safe.')
        rows = lambda t: sorted(l.split()[1] for l in t.splitlines() if re.match(r'  a-[0-9a-f]+ ', l))       # runs are listed by their identity, not in the order sent
        e.update(code=code, first_lines=lines[:2], last=lines[-1:], verdict_rows=[l for l in lines if l.startswith('Verdict ')], bare=(bare(out), bare(after), bare(console), bare(out_f)),
                 rows_after=rows(after), rows_console=rows(console), mid_tail=mid.splitlines()[-1:], after_tail=after.splitlines()[-2:], console_tail=console.splitlines()[-2:],
                 inbox_line=[l[:60] for l in console.splitlines() if l.startswith(('inbox writable', 'INBOX NOT CHECKED'))], notice_lines=nl[3:5] + nl[-1:],
                 outcomes=sorted(x['outcome'] for x in s.get('runs', [])), status=s.get('status'))
        checks = {'the answer to a pass begins DECLARED CHECK MET, with what the check does not cover on the next line and again at its end, and its Verdict row calls it the declared check met, signed as PASS (exit status 0)':
                      code == 0 and lines[:2] == ['DECLARED CHECK MET', excl] and lines[-1] == excl
                      and e['verdict_rows'] == ["Verdict       DECLARED CHECK MET (signed as PASS).  Computed by the verification service from the check's output and the baselined limits.  Not stated by the assistant."],
                  'no line of the answers, the first client\'s status or the engineer\'s console shows the bare word PASS': e['bare'] == ([], [], [], []),
                  'with no design met, the status says NOT VERIFIED and nothing more; with one met, the first client\'s status shows the run as MET and says for which design the declared check was met, that this does not say the check is correct, and what the check does not cover':
                      e['mid_tail'] == ['NOT VERIFIED: no design has met the declared check on this baseline.'] and 'DECLARED CHECK MET' not in mid
                      and e['rows_after'] == ['FAIL', 'MET'] and e['after_tail'] == [met_line, excl],
                  'the engineer\'s console shows the run as MET with the same lines, and calls the gate\'s check what it is, an inbox-writability check, not delivery':
                      e['rows_console'] == ['FAIL', 'MET'] and e['console_tail'] == [met_line, excl]
                      and any(l.startswith('inbox writable: the gate wrote a test file in this inbox at ') and l.endswith('This is not delivery: it does not show that a notice was delivered or read.') for l in console.splitlines()),
                  'the notice of the failure has what the check does not cover under its headline and at its end': e['notice_lines'] == ['FAIL: REQUIREMENT NOT MET', excl, excl],
                  'the signed verdicts and the record keep the word PASS, the record verifies, and its checker prints DECLARED CHECK MET and shows the run that met it as MET':
                      ok and e['outcomes'] == ['FAIL', 'PASS'] and s.get('status') == 'DECLARED CHECK MET' and 'STATUS: DECLARED CHECK MET, for design' in printed
                      and sorted(l.split()[3] for l in printed.splitlines() if l.startswith('    ') and '  design ' in l) == ['FAIL', 'MET']}
    finally:
        r.stop()
    return checks, e


def r25():
    """The witness signs a checkpoint of a baseline's chain: how many decisions it holds, the hash of the last, and its clock.  A record carries one, and its checker requires it to be the witness's and to name the record's own head.  Against a checkpoint obtained separately, the checker says whether a record is current, out of date or of another chain; and a log of checkpoints kept apart from the service refuses a rollback or a fork, and keeps the evidence.  (Amendment 10.)"""
    r = Run('R25'); e = {}
    try:
        s = r.s; root = B.root_for(r.env['card']); wk = s.keys['witness']; here = OUT / 'R25'
        url = f"https://127.0.0.1:{s.ports['witness']}"; keeper_tls = ['--ca', s.pki['ca'], '--cert', s.pki['keeper'][0], '--key', s.pki['keeper'][1]]
        rows = lambda: len(Store(deploy.LOCAL_DSN).audit_snapshot(root)[0])                   # the one chain: the witness and this reader use one database, under different roles
        def cur(rec, cp, **kw):                                                               # a defect that makes the checker raise reads as no state, not as an error of the test
            try:
                return check_record.currency(rec, cp, wk, **kw)
            except Exception as exc:
                return ('RAISED', f'{type(exc).__name__}: {exc}')
        signed = lambda **f: sign_checkpoint(s.witness, **f)                                  # what only the witness's key can sign
        fails = lambda rec: [n for n, _, good, _ in check_record.verify(rec, s.keys)[1] if not good]
        T = check_record.checkpoint_time
        def resign(rec):
            body = {k: v for k, v in rec.items() if k != 'signature'}
            return dict(body, signature={'signer': s.engineer.public_hex, 'signature': s.engineer.sign(canonical(body).encode())})
        def refused(f, *a, **kw):
            try:
                f(*a, **kw); return None
            except checkpoints.CheckpointRefused as exc:
                return str(exc)
        def cli(*args):
            p = subprocess.run([PY, '-B', str(GATEWAY / 'verify' / 'check_record.py'), *map(str, args)], capture_output=True, text=True, timeout=120)
            return p.returncode, [l.split('.')[0] for l in p.stdout.splitlines() if l.startswith('CURRENCY')], p.stdout
        def keeper(*args):
            p = subprocess.run([PY, '-B', str(GATEWAY / 'verify' / 'checkpoints.py'), *map(str, args)], capture_output=True, text=True, timeout=120)
            return p.returncode, p.stdout.strip(), p.stderr.strip()
        def raw(path, cert, method='GET', body=None):                                        # straight to the witness, as a client with this certificate
            ctx = TLS.TLSClient(s.pki['ca'], *cert).context()
            req = urllib.request.Request(url + path, data=None if body is None else json.dumps(body).encode(), method=method, headers={'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                    return resp.status
            except urllib.error.HTTPError as exc:
                return exc.code
            except (OSError, http.client.HTTPException) as exc:                                    # the witness dropped the connection: no answer
                return f'no answer: {type(exc).__name__}'
        def save(name, obj):
            (here / name).write_text(json.dumps(obj)); return here / name
        keys = save('keys.json', s.keys)

        prov = Store(deploy.LOCAL_DSN).provisioning(root)
        cp0 = s.checkpoint(root, 'first-ask_1'); cp0at = s.checkpoint(root, None, 0)
        r.submit(BAD)
        before = rows(); five = [s.checkpoint(root) for _ in range(5)]; after_reads = rows()
        rec1 = r.record(); ok1, checks1, sum1 = check_record.verify(rec1, s.keys)
        bare = s.record(r.h, [r.ws / '.verify' / 'submissions.jsonl'], checkpoint=False); okb, checksb, sumb = check_record.verify(bare, s.keys)
        cp1 = s.checkpoint(root, 'n-1'); f_rec1, f_cp1 = save('rec1.json', rec1), save('cp1.json', cp1); k1 = s.checkpoint(root, None, 0)      # k1 answers for decision 0, which the keeper will hold
        n1, h1 = rec1['as_of']['seq'], rec1['as_of']['head']
        when = dict(business='OPEN', witness='ACTIVE', time=cp1['time'])
        at_the_time = {'in the age allowed, nonce signed back': cur(rec1, cp1, nonce='n-1', max_age=600), 'no age allowed': cur(rec1, cp1)}
        cli_current = cli(f_rec1, '--keys', keys, '--checkpoint', f_cp1, '--nonce', 'n-1')
        cli_none = cli(f_rec1, '--keys', keys)
        cli_misuse = [cli(f_rec1, '--keys', keys, '--max-age', '60')[0], cli(f_rec1, '--keys', keys, '--nonce', 'n-1')[0], cli(f_rec1, '--checkpoint', f_cp1)[0],
                      cli(f_rec1, '--keys', keys, '--checkpoint', f_cp1, '--max-age', 'nan')[0], cli(f_rec1, '--keys', keys, '--checkpoint', '')[0]]
        r.submit(GOOD)
        cp2 = s.checkpoint(root); cp2at = s.checkpoint(root, None, n1)
        cli_old = cli(f_rec1, '--keys', keys, '--checkpoint', save('cp2at.json', cp2at))
        rec2 = r.record(); n2 = rec2['as_of']['seq']
        fork_same = signed(root=root, seq=n1, head='0' * 64, **when); fork_earlier = signed(root=root, seq=n1 + 8, head='1' * 64, at=n1, head_at='0' * 64, **when)
        states = {'replayed after a later run, in the age allowed': cur(rec1, cp1, max_age=600), 'replayed, a new nonce asked': cur(rec1, cp1, max_age=600, nonce='n-9'),
                  'later, no word on this record': cur(rec1, cp2), 'later, names this record': cur(rec1, cp2at), 'older': cur(rec2, cp1),
                  'stale': cur(rec1, cp1, max_age=60, now=T(cp1) + 61), 'fresh enough': cur(rec1, cp1, max_age=60, now=T(cp1) + 59),
                  'dated ahead': cur(rec1, cp1, max_age=60, now=T(cp1) - 301), 'clock a little behind': cur(rec1, cp1, max_age=60, now=T(cp1) - 299),
                  'age not a number': cur(rec1, cp1, max_age=float('nan')), 'other nonce': cur(rec1, cp1, nonce='n-2'), 'no nonce signed': cur(rec1, cp2, nonce='n-1'),
                  'edited number': cur(rec1, dict(cp1, seq=cp1['seq'] + 8)), 'edited head': cur(rec1, dict(cp1, head='0' * 64)), 'edited time': cur(rec1, dict(cp1, time='2030-01-01T00:00:00Z')),
                  'edited state': cur(rec1, dict(cp1, business='OPEN', witness='HELD')), 'a field added': cur(rec1, dict(cp1, note='current')),
                  'number as text': cur(rec1, signed(root=root, seq=str(n1), head=h1, **when)), 'number as true': cur(rec1, signed(root=root, seq=True, head=h1, **when)),
                  'earlier head with no number': cur(rec1, signed(root=root, seq=n1, head=h1, head_at=h1, **when)),
                  'another key': cur(rec1, sign_checkpoint(Signer(), root=root, seq=n1, head=h1, **when)),
                  'another budget': cur(rec1, signed(root=root + 'x', seq=n1, head=h1, **when)), 'not a checkpoint': cur(rec1, rec1['attempts'][0]['receipts']['CROSS']),
                  'record with no as-of': cur({'root': root, 'as_of': {'seq': None, 'head': None}}, cp1),
                  'fork, same number': cur(rec1, fork_same), 'fork, earlier head': cur(rec1, fork_earlier),
                  'fork, older than the record': cur(rec2, fork_same), 'fork, an earlier head inside the record': cur(rec2, signed(root=root, seq=n2 + 8, head='1' * 64, at=n1, head_at='0' * 64, **when))}
        cli_bad = {k: cli(f_rec1, '--keys', keys, '--checkpoint', save(f'x_{i}.json', c))[:2] for i, (k, c) in enumerate(
            (('forked', fork_same), ('invalid', dict(cp1, head='0' * 64)), ('older', cp0)))}
        cli_stale = cli(f_rec1, '--keys', keys, '--checkpoint', save('old.json', signed(root=root, seq=n1, head=h1, business='OPEN', witness='ACTIVE', time='2026-01-01T00:00:00Z')))[:2]
        ck2 = rec2.get('checkpoint') or {}
        edited = copy.deepcopy(rec2); edited['checkpoint'] = dict(ck2, head_at='0' * 64)
        earlier = copy.deepcopy(rec2); earlier['checkpoint'] = cp2at                                       # a true checkpoint, of an earlier point in the chain
        foreign = copy.deepcopy(rec2); foreign['checkpoint'] = sign_checkpoint(Signer(), **{k: ck2.get(k) for k in ('root', 'seq', 'head', 'business', 'witness', 'time', 'nonce', 'at', 'head_at')})
        plain = copy.deepcopy(rec2); plain['checkpoint'] = s.checkpoint(root)                                 # a true checkpoint that names no earlier head
        inside = {'edited': fails(edited), 'edited, re-signed': fails(resign(edited)), 'earlier point, re-signed': fails(resign(earlier)), 'another key, re-signed': fails(resign(foreign)),
                  'names no head, re-signed': fails(resign(plain)), 'taken out, re-signed': fails(resign({k: v for k, v in rec2.items() if k != 'checkpoint'}))}
        log = here / 'keeper' / 'checkpoints.jsonl'
        kept = [refused(checkpoints.keep, log, c, wk) for c in (cp0, k1, cp2at)]
        rev = verify_ctl.revise(s.home, CASE, draft(requirement=dict(r.env['card']['requirement'], revision='B')), s.engineer, r.h, 'The bracket was strengthened (CR-31).')
        cp_old = s.checkpoint(root, None, n2); old_state = cur(rec2, cp_old); kept.append(refused(checkpoints.keep, log, cp_old, wk))
        top = cp_old['seq']
        turned = {'rollback': refused(checkpoints.keep, log, cp1, wk), 'fork': refused(checkpoints.keep, log, signed(root=root, seq=top, head='0' * 64, **when), wk),
                  'fork of an earlier head': refused(checkpoints.keep, log, signed(root=root, seq=top + 8, head='1' * 64, at=n1, head_at='0' * 64, **when), wk),
                  'a longer chain that does not follow the last kept': refused(checkpoints.keep, log, signed(root=root, seq=top + 8, head='1' * 64, at=top, head_at='0' * 64, **when), wk),
                  'not tied to the last kept': refused(checkpoints.keep, log, signed(root=root, seq=top + 8, head='1' * 64, **when), wk),
                  'tied to an earlier one, truly': refused(checkpoints.keep, log, signed(root=root, seq=top + 8, head='1' * 64, at=n1, head_at=h1, **when), wk),
                  'another key': refused(checkpoints.keep, log, sign_checkpoint(Signer(), root=root, seq=top, head=cp_old['head'], **when), wk),
                  'another budget than asked': refused(checkpoints.keep, log, cp_old, wk, root + 'x'), 'another nonce than asked': refused(checkpoints.keep, log, cp_old, wk, root, 'mine')}
        lines = len(log.read_text().splitlines()) if log.exists() else 0; clean = checkpoints.audit(checkpoints.read_log(log)[0], wk)
        aside = here / 'keeper' / 'checkpoints.jsonl.refused.jsonl'; evidence = len(aside.read_text().splitlines()) if aside.exists() else 0
        with log.open('a') as f:
            f.write(json.dumps(signed(root=root, seq=top, head='0' * 64, **when)) + '\n')                  # put in behind the keeper's back
        dirty = checkpoints.audit(checkpoints.read_log(log)[0], wk)
        stranger = TLS.issue(pathlib.Path(s.pki['ca_key']).read_bytes(), pathlib.Path(s.pki['ca']).read_bytes(), 'stranger', 'client', (), 3)
        (here / 'stranger.key').write_bytes(stranger[0]); (here / 'stranger.crt').write_bytes(stranger[1])
        q = urllib.parse.quote(root, safe='')
        accept = {'root': root, 'op': ['ACCEPT_RESERVATION', 'a-0000000000000000'], 'evidence': None}
        chain_before = rows()
        witness_says = {'unknown budget': raw(f'/checkpoint?root={q}x', s.pki['keeper']), 'no budget named': raw('/checkpoint', s.pki['keeper']), 'nonce with a space': raw(f'/checkpoint?root={q}&nonce=a%20b', s.pki['keeper']),
                        'nonce of 65 characters': raw(f'/checkpoint?root={q}&nonce=' + 'a' * 65, s.pki['keeper']), 'beyond the chain': raw(f'/checkpoint?root={q}&at=1000000', s.pki['keeper']),
                        'a number that is not one': raw(f'/checkpoint?root={q}&at=-1', s.pki['keeper']), 'a budget name with a control character': raw(f'/checkpoint?root={q}%00', s.pki['keeper']),
                        'stranger': raw(f'/checkpoint?root={q}', (str(here / 'stranger.crt'), str(here / 'stranger.key'))), 'keeper reads': raw(f'/checkpoint?root={q}', s.pki['keeper']),
                        'keeper writes': raw('/accept', s.pki['keeper'], 'POST', accept), 'keeper asks the key': raw('/pubkey', s.pki['keeper']), 'governor reads': raw(f'/checkpoint?root={q}', s.pki['governor'])}
        no_cert = refused(checkpoints.fetch, url, s.pki['ca'], None, None, root); plain_http = refused(checkpoints.fetch, url.replace('https', 'http'), s.pki['ca'], *s.pki['keeper'], root)
        chain_after = rows()
        log2 = here / 'keeper2' / 'log.jsonl'; log2.parent.mkdir()
        first = keeper('fetch', '--witness-url', url, *keeper_tls, '--root', root, '--out', here / 'cp_cli.json', '--log', log2, '--witness-key', wk)
        second = keeper('fetch', '--witness-url', url, *keeper_tls, '--root', root, '--log', log2, '--witness-key', wk)
        j1, j2 = (json.loads(x[1]) if x[0] == 0 else {} for x in (first, second))
        with log2.open('a') as f:
            f.write('{"statement": "CHECKP')                                                               # a line cut off by a crash
        torn_audit = keeper('audit', log2, '--witness-key', wk)
        third = keeper('fetch', '--witness-url', url, *keeper_tls, '--root', root, '--log', log2, '--witness-key', wk)
        log2.write_bytes(log2.read_bytes().rstrip(b'\n'))                                                  # the last line whole, its line end lost
        fourth = keeper('fetch', '--witness-url', url, *keeper_tls, '--root', root, '--log', log2, '--witness-key', wk)
        audited = keeper('audit', log2, '--witness-key', wk)
        log3 = here / 'keeper3' / 'log.jsonl'; log3.parent.mkdir()
        log3.write_text(json.dumps(signed(root=root, seq=top + 8, head='1' * 64, **when)) + '\n')           # a keeper that was once told of a longer chain
        shorter = keeper('fetch', '--witness-url', url, *keeper_tls, '--root', root, '--log', log3, '--witness-key', wk)
        aside3 = [json.loads(l) for l in (here / 'keeper3' / 'log.jsonl.refused.jsonl').read_text().splitlines()] if (here / 'keeper3' / 'log.jsonl.refused.jsonl').exists() else []
        rec3 = r.record(); cli_closed = cli(save('rec3.json', rec3), '--keys', keys, '--checkpoint', here / 'cp_cli.json', '--nonce', j1.get('nonce') or '', '--max-age', '600')
        keyfile = here / 'engineer.key'; keyfile.write_text(s.engineer.private_hex + '\n')
        console = subprocess.run([PY, '-B', str(GATEWAY / 'verify' / 'verify_ctl.py'), 'record', str(s.home), r.h, '--key', str(keyfile), '--witness-key', wk, '--gate-key', s.keys['gate'],
                                  '--journal', str(r.ws / '.verify' / 'submissions.jsonl'), '--out', str(here / 'rec_console.json'), '--witness-url', url, '--tls-ca', s.pki['ca'],
                                  '--tls-cert', s.pki['keeper'][0], '--tls-key', s.pki['keeper'][1]], capture_output=True, text=True, timeout=120)
        rec_c = json.loads((here / 'rec_console.json').read_text()) if console.returncode == 0 else {}
        console_ok = bool(rec_c) and check_record.verify(rec_c, s.keys)[0] and (rec_c.get('checkpoint') or {}).get('at') == rec_c['as_of']['seq']
        e.update(cp0={k: cp0.get(k) for k in ('seq', 'business', 'witness', 'nonce', 'at')}, reads=(before, after_reads), checks1=next(((n, t, g) for n, t, g, _ in checks1 if n == 9), None), bare=next(((n, t, g) for n, t, g, _ in checksb if n == 9), None),
                 summary=sum1.get('checkpoint'), at_the_time={k: v[0] for k, v in at_the_time.items()}, states={k: v[0] for k, v in states.items()}, sentences={k: v[1][:130] for k, v in states.items()},
                 cli=(cli_current[:2], cli_none[:2], cli_old[:2], cli_closed[:2]), cli_misuse=cli_misuse, cli_bad=cli_bad, cli_stale=cli_stale,
                 inside=inside, old_state=old_state, kept=kept, turned=turned, lines=lines, evidence=evidence, clean=clean, dirty=dirty, witness_says=witness_says, no_cert=no_cert, plain_http=plain_http,
                 chain=(chain_before, chain_after), keeper=(first, second, third, fourth), torn_audit=torn_audit, audited=audited, shorter=shorter, aside3=[(c.get('seq'), c.get('at')) for c in aside3], console=(console.returncode, console.stderr[:200]))
        st = e['states']
        checks = {'before any run the witness signs a checkpoint of the empty chain: no decisions, its head the provisioning record\'s hash, the budget open, the asker\'s nonce signed back; asked for the head after decision 0 it gives the same hash; both verify under the witness\'s key':
                      cp0['seq'] == 0 and cp0['head'] == prov['hash'] and (cp0['business'], cp0['witness'], cp0['nonce']) == ('OPEN', 'ACTIVE', 'first-ask_1') and check_record.checkpoint_problems(cp0, [wk], root) == []
                      and (cp0at['at'], cp0at['head_at']) == (0, prov['hash']) and check_record.checkpoint_problems(cp0at, wk, root) == [],
                  'asking for a checkpoint adds no decision: five asks leave the chain as long as it was, and each gives its length and head':
                      before == after_reads == n1 and all(c['seq'] == before and c['head'] == h1 for c in five),
                  'a record carries the witness\'s checkpoint, which names the record\'s own last decision and head; the record verifies with a ninth check, the witness checkpoint; a record built without one still verifies, and its ninth check says it has none':
                      ok1 and e['checks1'] == (9, 'witness checkpoint', True) and (rec1.get('checkpoint') or {}).get('at') == n1 and (rec1.get('checkpoint') or {}).get('head_at') == h1
                      and (sum1.get('checkpoint') or {}).get('seq') == n1 and okb and 'checkpoint' not in bare and e['bare'] == (9, 'witness checkpoint (none in this record)', True) and sumb['checkpoint'] is None,
                  'against a checkpoint obtained separately, whose chain ends where the record does, the record is CURRENT within the age allowed, with the nonce asked signed back; with no age allowed it is only CURRENT_AT the checkpoint\'s time; the checker\'s command, which allows an hour unless told, says CURRENT and exits 0; with no checkpoint given it says the currency was not checked, and exits 0 as before':
                      e['at_the_time'] == {'in the age allowed, nonce signed back': 'CURRENT', 'no age allowed': 'CURRENT_AT'} and cli_current[:2] == (0, ['CURRENCY: CURRENT'])
                      and cli_none[:2] == (0, ['CURRENCY: NOT CHECKED']),
                  'the command refuses to be misused (exit 2): an age or a nonce with no checkpoint, a checkpoint with the keys read from the record itself, an age that is not a number, a checkpoint file with no name':
                      cli_misuse == [2, 2, 2, 2, 2],
                  'after a later run the same record is out of date: SUPERSEDED, a true beginning of the chain, where the checkpoint names the record\'s head; SUPERSEDED_UNPROVEN where it does not; the command exits 1 though the record itself verifies':
                      st['later, names this record'] == 'SUPERSEDED' and 'The record is a true beginning of that chain' in states['later, names this record'][1] and '8 later decisions' in states['later, names this record'][1]
                      and st['later, no word on this record'] == 'SUPERSEDED_UNPROVEN' and cli_old[:2] == (1, ['CURRENCY: SUPERSEDED']),
                  'an old checkpoint handed over again with the old record, after a later run, still reads CURRENT inside the age allowed, which is all that CURRENT says; asked with a nonce of the reader\'s own, it is not used':
                      (st['replayed after a later run, in the age allowed'], st['replayed, a new nonce asked']) == ('CURRENT', 'INVALID'),
                  'a checkpoint older than the record says nothing of it (OLDER); one older than the age allowed is STALE and one within it CURRENT; one dated more than five minutes ahead of the reader\'s clock is not used, and one less than that ahead is; the command exits 1 for a stale, a forked, an unusable and an older checkpoint':
                      (st['older'], st['stale'], st['fresh enough'], st['dated ahead'], st['clock a little behind']) == ('OLDER', 'STALE', 'CURRENT', 'INVALID', 'CURRENT')
                      and cli_stale == (1, ['CURRENCY: STALE']) and cli_bad == {'forked': (1, ['CURRENCY: FORKED']), 'invalid': (1, ['CURRENCY: INVALID']), 'older': (1, ['CURRENCY: OLDER'])},
                  'a checkpoint is not used (INVALID) when it signs back another nonce or none, when its number, head, time or state was edited or a field added, when its number is text or true, when it gives an earlier head with no number, when it is signed by another key, is for another budget, or is a receipt and not a checkpoint; nor is an age that is not a number, or a record with no as-of point':
                      all(st[k] == 'INVALID' for k in ('other nonce', 'no nonce signed', 'edited number', 'edited head', 'edited time', 'edited state', 'a field added', 'number as text', 'number as true',
                                                       'earlier head with no number', 'another key', 'another budget', 'not a checkpoint', 'age not a number', 'record with no as-of')),
                  'a checkpoint the witness\'s key signed that gives another head for a decision the record holds shows the record is of another chain (FORKED): for the record\'s last decision, as the chain\'s head or as an earlier one, and for a decision inside the record, in a checkpoint older or newer than it':
                      all(st[k] == 'FORKED' for k in ('fork, same number', 'fork, earlier head', 'fork, older than the record', 'fork, an earlier head inside the record')),
                  'the checkpoint inside a record cannot be changed, exchanged or dropped unseen: edited, checks 1 and 9 fail; edited and re-signed with the engineer\'s key, or exchanged for a true checkpoint of an earlier point, for a true one that names no head, or for one signed by another key, check 9 alone fails; taken out and re-signed, the record verifies and says it has none':
                      inside == {'edited': [1, 9], 'edited, re-signed': [9], 'earlier point, re-signed': [9], 'another key, re-signed': [9], 'names no head, re-signed': [9], 'taken out, re-signed': []},
                  'once the baseline is superseded, a checkpoint of its chain says the budget is no longer open, and the checker says so beside the record\'s currency':
                      cp_old['business'] != 'OPEN' and old_state[0] == 'SUPERSEDED' and 'it was superseded or closed' in old_state[1],
                  'a log of checkpoints kept apart from the service takes them in order, each answering for the last number kept, and refuses a rollback, a fork of the head, a fork of an earlier head, a longer chain that does not follow the last one kept, one that does not answer for the last number kept (naming none, or an earlier one), a checkpoint not signed by the witness, and one for another budget or nonce than asked; it keeps none of them, and puts the four that contradict it aside as evidence':
                      kept == [None, None, None, None] and (turned['rollback'] or '').startswith('not kept: ROLLBACK') and all((turned[k] or '').startswith('not kept: FORK') for k in ('fork', 'fork of an earlier head', 'a longer chain that does not follow the last kept'))
                      and all('does not say what the chain\'s head was at sequence number' in (turned[k] or '') for k in ('not tied to the last kept', 'tied to an earlier one, truly'))
                      and 'not signed by a witness key given' in (turned['another key'] or '') and 'another budget' in (turned['another budget than asked'] or '') and 'nonce' in (turned['another nonce than asked'] or '') and lines == 4 and evidence == 4,
                  'the log\'s audit is clean, and reports a fork written into it behind the keeper\'s back': clean == [] and len(dirty) == 1 and 'FORK' in dirty[0],
                  'the witness answers 404 for a budget it does not hold and 400 for no budget, a nonce with a space or of 65 characters, a decision beyond the chain, a number that is not one and a budget name with a control character; none of it adds a decision':
                      [witness_says[k] for k in ('unknown budget', 'no budget named', 'nonce with a space', 'nonce of 65 characters', 'beyond the chain', 'a number that is not one', 'a budget name with a control character')] == [404, 400, 400, 400, 400, 400, 400]
                      and chain_before == chain_after,
                  'the keeper\'s certificate reads a checkpoint (200) and can do nothing else: the witness refuses its write (403) and its other question (403); a certificate the witness does not know is refused the checkpoint (403); the fetcher gives nothing with no certificate, and will not ask over plain http':
                      (witness_says['keeper reads'], witness_says['keeper writes'], witness_says['keeper asks the key'], witness_says['stranger'], witness_says['governor reads']) == (200, 403, 403, 403, 200)
                      and 'could not be asked' in (no_cert or '') and 'https' in (plain_http or ''),
                  'the keeper\'s command fetches a checkpoint with a nonce of its own making, keeps it and writes it out; its next fetch asks the witness for the head at the last number kept; a line cut off in the log is reported by the audit and does not stop the next fetch, nor does a last line that lost its line end; the log then audits clean with four checkpoints':
                      first[0] == 0 and second[0] == 0 and third[0] == 0 and len(j1.get('nonce') or '') >= 16 and j1.get('nonce') != j2.get('nonce') and j1.get('at') is None and j2.get('at') == j1.get('seq')
                      and torn_audit[0] == 1 and 'cut off' in torn_audit[1] and fourth[0] == 0 and audited[0] == 0 and audited[1].endswith('4 checkpoints; no rollback or fork, every signature verifies'),
                  'a keeper whose log holds a longer chain than the witness now has is told of a rollback: the command exits 1, and the witness\'s signed checkpoint of the shorter chain is put aside as the evidence':
                      shorter[0] == 1 and 'ROLLBACK' in shorter[2] and len(aside3) == 1 and aside3[0].get('seq') == top and check_record.checkpoint_problems(aside3[0], wk, root) == [],
                  'the superseded baseline\'s record, built after the revision and checked against the keeper\'s first checkpoint with its nonce, is CURRENT; the command says the budget is no longer open, and exits 0; the engineer\'s console, given the witness\'s address, writes a record that carries a checkpoint and verifies':
                      cli_closed[0] == 0 and cli_closed[1] == ['CURRENCY: CURRENT'] and 'it was superseded or closed' in cli_closed[2] and console.returncode == 0 and console_ok}
    finally:
        r.stop()
    return checks, e


def r26():
    """A courier that reads only the witness sends the engineer a notice of each run that calls for one, signed with its own key,
    to the engineer's mailbox, which signs a receipt for it.  It does not read the service, so a notice the service did not
    write, or that was removed from its inbox, is still sent.  A record can carry the notices and receipts, and its checker
    says which runs have a notice delivered and which have none.  (Amendment 11.)"""
    r = Run('R26', crash_at='verify_running'); e = {}
    try:
        s = r.s; root = B.root_for(r.env['card']); here = OUT / 'R26'; C = check_record
        url, mb_url = f"https://127.0.0.1:{s.ports['witness']}", f"https://127.0.0.1:{s.ports['mailbox']}"
        rows = lambda: len(Store(deploy.LOCAL_DSN).audit_snapshot(root)[0])
        fails = lambda rec: [n for n, _, good, _ in C.verify(rec, s.keys)[1] if not good]
        def step(f, *a, **kw):                                                                     # a defect that makes a step raise gives an answer, not an error of the test
            try:
                return f(*a, **kw)
            except Exception as exc:
                return ('RAISED', f'{type(exc).__name__}: {exc}')
        def call(base, path, cert, method='GET', body=None, raw_body=None):                        # straight to a party, as a client with this certificate: (status, answer)
            ctx = TLS.TLSClient(s.pki['ca'], *cert).context()
            data = raw_body if raw_body is not None else (None if body is None else json.dumps(body).encode())
            req = urllib.request.Request(base + path, data=data, method=method, headers={'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                    return resp.status, json.loads(resp.read() or b'null')
            except urllib.error.HTTPError as exc:
                return exc.code, None
            except (OSError, http.client.HTTPException, ValueError) as exc:
                return f'no answer: {type(exc).__name__}', None
        def resign(rec):
            body = {k: v for k, v in rec.items() if k != 'signature'}
            return dict(body, signature={'signer': s.engineer.public_hex, 'signature': s.engineer.sign(canonical(body).encode())})
        def signed(key, fields, body):
            return dict(body, signer=key.public_hex, signature=key.sign(C.canonical({k: body.get(k) for k in fields}).encode()))
        def cli(*args):
            p = subprocess.run([PY, '-B', str(GATEWAY / 'verify' / 'check_record.py'), *map(str, args)], capture_output=True, text=True, timeout=120)
            return p.returncode, [l for l in p.stdout.splitlines() if l.startswith('NOTICES')]
        def save(name, obj):
            (here / name).write_text(json.dumps(obj)); return here / name
        def run_courier(stall, name='courier'):
            return step(s.courier, [root], stall, name)
        def made(c):
            return sorted(x.get('outcome') for x in (c[1].get('made') or [])) if isinstance(c, tuple) and isinstance(c[1], dict) else c
        def delivered(c):
            return sorted(x.get('outcome') for x in (c[1].get('delivered') or [])) if isinstance(c, tuple) and isinstance(c[1], dict) else c
        courier_cert, keeper_cert = s.pki['courier'], s.pki['keeper']
        keys = save('keys.json', s.keys)

        # a run cut off, then answered as interrupted
        cut = r.submit(GOOD); time.sleep(0.3); host_exit = s.procs['host'].poll()
        c_wait = run_courier(900); c_cut = run_courier(0)
        s.stop_host(); s.start_host()
        again = r.submit(GOOD)
        c_int = run_courier(0)
        # a failing run whose own notice is taken out of the service's inbox, and a passing run
        bad = r.submit(BAD)
        box = s.home / 'inbox' / r.h[:16]; own = sorted(p.name for p in box.glob('*FAIL*')) if box.exists() else []
        for p in box.glob('*FAIL*'):
            p.unlink()                                                                              # whoever can write the inbox can remove a notice (D12)
        good = r.submit({'material': 'PPS-GF40', 'wall_mm': 2.5, 'mode': 'normal'})
        c_fail = run_courier(0); c_again = run_courier(0)
        held = [json.loads(p.read_text()) for p in sorted((s.dir / 'mailbox' / 'notices').glob('*.json'))]
        texts = [p.read_text() for p in sorted((s.dir / 'mailbox' / 'notices').glob('*.txt'))]
        log = courier.read_deliveries(s.dir / 'courier' / 'deliveries.jsonl', root)
        cfg_text = (s.dir / 'courier.json').read_text()
        # the mailbox down, then up
        s.stop_mailbox(); bad2 = r.submit({'material': 'PA66-GF30', 'wall_mm': 2, 'mode': 'normal'})
        c_down = run_courier(0); s.start_mailbox(); c_up = run_courier(0)

        # the witness's readings
        before = rows(); q = urllib.parse.quote(root, safe='')
        cp = step(checkpoints.fetch, url, s.pki['ca'], *courier_cert, root, 'r26-reader', 0)
        ch = call(url, f'/chain?root={q}&after=0&limit=200', courier_cert)
        chained = step(courier.verify_rows, (ch[1] or {}).get('rows', []), 0, cp.get('head_at') if isinstance(cp, dict) else None, len((ch[1] or {}).get('rows', [])),
                       ((ch[1] or {}).get('rows') or [{}])[-1].get('hash')) if isinstance(cp, dict) else cp
        live = step(checkpoints.fetch, url, s.pki['ca'], *courier_cert, root, 'r26-reader-2')
        fail_aid = next((x['notice'].get('aid') for x in log if x['notice'].get('outcome') == 'FAIL'), None)
        run_ans = call(url, f'/run?root={q}&aid={fail_aid}', courier_cert)
        after = rows()
        stranger = TLS.issue(pathlib.Path(s.pki['ca_key']).read_bytes(), pathlib.Path(s.pki['ca']).read_bytes(), 'stranger', 'client', (), 3)
        (here / 'stranger.key').write_bytes(stranger[0]); (here / 'stranger.crt').write_bytes(stranger[1]); stranger_cert = (str(here / 'stranger.crt'), str(here / 'stranger.key'))
        witness_says = {'chain, unknown budget': call(url, f'/chain?root={q}x', courier_cert)[0], 'chain, no budget': call(url, '/chain', courier_cert)[0],
                        'chain, after not a number': call(url, f'/chain?root={q}&after=-1', courier_cert)[0], 'chain, limit 0': call(url, f'/chain?root={q}&limit=0', courier_cert)[0],
                        'chain, limit 201': call(url, f'/chain?root={q}&limit=201', courier_cert)[0], 'chain, control character': call(url, f'/chain?root={q}%01', courier_cert)[0],
                        'run, unknown budget': call(url, f'/run?root={q}x&aid=a-1', courier_cert)[0], 'run, no attempt': call(url, f'/run?root={q}', courier_cert)[0],
                        'run, attempt with a control character': call(url, f'/run?root={q}&aid=a%011', courier_cert)[0],
                        'courier writes': call(url, '/accept', courier_cert, 'POST', {'root': root, 'op': ['ACCEPT_RESERVATION', 'a-0000000000000000'], 'evidence': None})[0],
                        'courier asks the key': call(url, '/pubkey', courier_cert)[0], 'stranger reads the chain': call(url, f'/chain?root={q}', stranger_cert)[0],
                        'keeper reads the chain': call(url, f'/chain?root={q}&limit=1', keeper_cert)[0]}
        # the mailbox's refusals
        one = next((h['notice'] for h in held if h['notice'].get('outcome') != 'WATCHING'), {})   # Amendment 16: a notice of a run, not the courier's statement that it watches
        import mailbox_service
        stranger_courier = mailbox_service.MailboxKey()
        forged = signed(stranger_courier, C.NOTICE_FIELDS, {k: one.get(k) for k in C.NOTICE_FIELDS})
        n_files = len(list((s.dir / 'mailbox' / 'notices').glob('*.json')))
        mailbox_says = {'another key': call(mb_url, '/deliver', courier_cert, 'POST', forged)[0], 'not a notice': call(mb_url, '/deliver', courier_cert, 'POST', {'statement': 'NOTICE'})[0],
                        'not JSON': call(mb_url, '/deliver', courier_cert, 'POST', raw_body=b'{"no')[0], 'keeper delivers': call(mb_url, '/deliver', keeper_cert, 'POST', one)[0]}
        again_ans = call(mb_url, '/deliver', courier_cert, 'POST', one)
        same_receipt = again_ans[0] == 200 and again_ans[1] == next((h['receipt'] for h in held if h['notice'] == one), None) if held else False
        n_files_after = len(list((s.dir / 'mailbox' / 'notices').glob('*.json')))
        # a mailbox whose key is not the one given
        cfg3 = json.loads(s.courier_config([root], 0, 'courier3').read_text()); cfg3['watches'][0]['mailbox_keys'] = [mailbox_service.MailboxKey().public_hex]
        (s.dir / 'courier3.json').write_text(json.dumps(cfg3))
        p3 = subprocess.run([PY, '-B', str(GATEWAY / 'verify' / 'courier.py'), 'run', '--config', str(s.dir / 'courier3.json')], capture_output=True, text=True, timeout=120)
        c_wrongbox = (p3.returncode, step(json.loads, (p3.stdout.strip().splitlines() or ['{}'])[-1]))
        # sixth form: the real mailbox, asked for its key, gives the key the courier was given; its receipts are signed with its own
        # (the courier's answer to /pubkey is replaced in process: mailbox_service.py is not changed)
        stranger_box = mailbox_service.MailboxKey()
        cfg3b = json.loads(s.courier_config([root], 0, 'courier3b').read_text()); cfg3b['watches'][0]['mailbox_keys'] = [stranger_box.public_hex]
        def pinned_lie():
            orig = courier.https
            def fake(method, u, cfg, body=None, timeout=15.0):
                if u.endswith('/pubkey') and u.startswith(cfg3b['watches'][0]['mailbox_url']):
                    return 200, {'public_key': stranger_box.public_hex, 'name': 'not the mailbox'}
                return orig(method, u, cfg, body, timeout)
            courier.https = fake
            try:
                return courier.one_pass(cfg3b)
            except BaseException as exc:
                return {'error': f'{type(exc).__name__}: {exc}'}
            finally:
                courier.https = orig
        s3b = pinned_lie()
        c_pinned = (s3b.get('delivered'), sorted({x.get('kind') for x in s3b.get('undelivered', [])}), len(s3b.get('waiting', [])), courier.failed(s3b) if 'error' not in s3b else s3b)
        # decisions that do not hash, follow on or end at the head
        good_rows = (ch[1] or {}).get('rows', [])[:3]
        start = good_rows[0]['prev_hash'] if good_rows else ''
        bent = copy.deepcopy(good_rows); bent and bent[1]['observation'].update(note='changed')
        rows_refused = [step(courier.verify_rows, x, 0, start, 3, good_rows[-1]['hash'] if good_rows else '') for x in (bent, good_rows[:1] + good_rows[2:], good_rows)]
        rows_refused = [isinstance(x, tuple) and x[0] == 'RAISED' and 'Refused' in x[1] for x in rows_refused[:2]] + [isinstance(rows_refused[2], list) and len(rows_refused[2]) == 3]
        wrong_head = step(courier.verify_rows, good_rows, 0, start, 3, '0' * 64)
        # a fork and a rollback against what a courier read before
        st_path = s.dir / 'courier' / 'state.json'; st = json.loads(st_path.read_text()); st['roots'][root]['head'] = '0' * 64; st_path.write_text(json.dumps(st))
        c_fork = run_courier(0); c_fork2 = run_courier(0)
        forks = [json.loads(l) for l in (s.dir / 'courier' / 'refused.jsonl').read_text().splitlines()] if (s.dir / 'courier' / 'refused.jsonl').exists() else []
        c_r2 = run_courier(0, 'courier2')
        st2_path = s.dir / 'courier2' / 'state.json'; st2 = json.loads(st2_path.read_text()); st2['roots'][root]['seq'] += 50; st2_path.write_text(json.dumps(st2))
        c_roll = run_courier(0, 'courier2')
        rolls = [json.loads(l) for l in (s.dir / 'courier2' / 'refused.jsonl').read_text().splitlines()] if (s.dir / 'courier2' / 'refused.jsonl').exists() else []

        # the record
        rec = step(s.record, r.h, [r.ws / '.verify' / 'submissions.jsonl'], deliveries=True)
        rec = rec if isinstance(rec, dict) else {}
        ok, checks, summ = C.verify(rec, s.keys) if rec else (False, [], {})
        ten = next(((n, t, g) for n, t, g, _ in checks if n == 10), None)
        dv = summ.get('delivery') or {}
        f_rec = save('rec.json', rec)
        cli_full = cli(f_rec, '--keys', keys, '--require-delivery')
        dropped = copy.deepcopy(rec); fail_aids = [d['aid'] for d in dv.get('due', []) if d['outcome'] == 'FAIL']
        dropped['deliveries'] = [d for d in rec.get('deliveries', []) if not (d['notice'].get('aid') == (fail_aids[:1] or [None])[0] and d['notice'].get('outcome') == 'FAIL')]
        dropped = resign(dropped); okd, _, sd = C.verify(dropped, s.keys)
        no_int = copy.deepcopy(rec); no_int['deliveries'] = [d for d in rec.get('deliveries', []) if d['notice'].get('outcome') != 'INTERRUPTED']
        no_int = resign(no_int); oki, _, si = C.verify(no_int, s.keys)
        cli_dropped = cli(save('dropped.json', dropped), '--keys', keys, '--require-delivery')
        d0 = (rec.get('deliveries') or [{}])[0]; n0 = d0.get('notice') or {}
        def with_delivery(d):
            x = copy.deepcopy(rec); x['deliveries'] = [d] + (rec.get('deliveries') or [])[1:]; return resign(x)
        def receipt_for(n, key=None):
            body = {'statement': 'DELIVERED', 'notice': C.notice_digest(n), 'root': n.get('root'), 'aid': n.get('aid'), 'outcome': n.get('outcome'), 'mailbox': 'engineer-mailbox', 'time': n.get('time')}
            return signed(key or s.mailbox_key, C.RECEIPT_FIELDS, body)
        moved = signed(s.courier_key, C.NOTICE_FIELDS, dict({k: n0.get(k) for k in C.NOTICE_FIELDS}, head='1' * 64))
        fail_n = next((d['notice'] for d in rec.get('deliveries', []) if d['notice'].get('outcome') == 'FAIL'), {})
        misstated = signed(s.courier_key, C.NOTICE_FIELDS, dict({k: fail_n.get(k) for k in C.NOTICE_FIELDS}, outcome='UNKNOWN'))
        fail_rec_a = next((a for a in rec.get('attempts', []) if a.get('aid') == fail_n.get('aid')), {})
        misstated = signed(s.courier_key, C.NOTICE_FIELDS, dict(misstated, text=C.notice_text('UNKNOWN', fail_n.get('aid'), root, fail_rec_a.get('result'), fail_n.get('seq'), fail_n.get('courier'))))   # words that agree with the false outcome
        tampered = {'notice edited': fails(with_delivery(dict(d0, notice=dict(n0, outcome='FAIL' if n0.get('outcome') != 'FAIL' else 'UNKNOWN')))),
                    'notice of another courier key': fails(with_delivery({'notice': signed(stranger_courier, C.NOTICE_FIELDS, {k: n0.get(k) for k in C.NOTICE_FIELDS}), 'receipt': d0.get('receipt')})),
                    'receipt of another key': fails(with_delivery(dict(d0, receipt=receipt_for(n0, stranger_courier)))),
                    'decision not in the chain': fails(with_delivery({'notice': moved, 'receipt': receipt_for(moved)})),
                    'outcome the record does not give': fails(with_delivery({'notice': misstated, 'receipt': receipt_for(misstated)})),
                    'a field added to the notice': fails(with_delivery({'notice': dict(n0, note='read this'), 'receipt': receipt_for(dict(n0, note='read this'))})),
                    'a receipt for another notice': fails(with_delivery(dict(d0, receipt=((rec.get('deliveries') or [{}, {}])[1:2] or [{}])[0].get('receipt')))),
                    'a notice for another budget': fails(with_delivery({'notice': signed(s.courier_key, C.NOTICE_FIELDS, dict({k: n0.get(k) for k in C.NOTICE_FIELDS}, root=root + 'x')),
                                                                       'receipt': receipt_for(signed(s.courier_key, C.NOTICE_FIELDS, dict({k: n0.get(k) for k in C.NOTICE_FIELDS}, root=root + 'x')))})),
                    'words changed': fails(with_delivery({'notice': signed(s.courier_key, C.notice_fields(fail_n), dict({k: fail_n.get(k) for k in C.notice_fields(fail_n)}, text=str(fail_n.get('text')).replace('achieved "180"', 'achieved "210"'))),
                                                          'receipt': receipt_for(signed(s.courier_key, C.notice_fields(fail_n), dict({k: fail_n.get(k) for k in C.notice_fields(fail_n)}, text=str(fail_n.get('text')).replace('achieved "180"', 'achieved "210"'))))}))}
        words_differ = 'achieved "180"' in str(fail_n.get('text'))
        three = C.verify(rec, {k: s.keys[k] for k in ('witness', 'gate', 'engineer')})
        three_keys = (three[0], next(((n, tt, g) for n, tt, g, _ in three[1] if n == 10), None), (three[2].get('delivery') or {}).get('unchecked'))
        cli_three = cli(f_rec, '--witness-key', s.keys['witness'], '--gate-key', s.keys['gate'], '--engineer-key', s.keys['engineer'], '--require-delivery')
        cli_five = cli(f_rec, '--witness-key', s.keys['witness'], '--gate-key', s.keys['gate'], '--engineer-key', s.keys['engineer'],
                       '--courier-key', s.keys['courier'][0], '--mailbox-key', s.keys['mailbox'][0], '--require-delivery')
        # a notice that vouches for no result, made at the decision the gate signed an effect
        fail_a = next((a for a in rec.get('attempts', []) if a.get('aid') == fail_n.get('aid')), {})
        eff_seq = max((i['seq'] for i in fail_a.get('evidence') or [] if (i.get('evidence') or {}).get('claim') == 'EFFECT'), default=None)
        early = signed(s.courier_key, C.NOTICE_FIELDS, dict({k: fail_n.get(k) for k in C.NOTICE_FIELDS}, outcome='UNVERIFIED', result_digest=None, reason_code=None, detail=None,
                                                             text=C.notice_text('UNVERIFIED', fail_n.get('aid'), root, None, eff_seq, fail_n.get('courier')),
                                                             seq=eff_seq, head=rec['audit'][eff_seq - 1]['hash'] if eff_seq else None))
        x = copy.deepcopy(rec); x['deliveries'] = (rec.get('deliveries') or []) + [{'notice': early, 'receipt': receipt_for(early)}]; early_rec = resign(x)
        okx, _, sx = C.verify(early_rec, s.keys)
        unverified = {'no result': C.run_outcome('EFFECT', fail_a.get('evidence'), None, s.keys['gate'], root, fail_a.get('aid'), fail_a.get('nonce')),
                      'a result changed': C.run_outcome('EFFECT', fail_a.get('evidence'), dict(fail_a.get('result') or {}, verdict='PASS'), s.keys['gate'], root, fail_a.get('aid'), fail_a.get('nonce')),
                      'the result': C.run_outcome('EFFECT', fail_a.get('evidence'), fail_a.get('result'), s.keys['gate'], root, fail_a.get('aid'), fail_a.get('nonce'))}
        ev0 = [i for i in fail_a.get('evidence') or [] if (i.get('evidence') or {}).get('claim') == 'EFFECT'][:1]
        gate2 = mailbox_service.MailboxKey()
        def regate(item, **change):
            e2 = dict(item['evidence'], **change); e2['signer'] = gate2.public_hex if 'signer' not in change else e2['signer']
            e2['signature'] = gate2.sign(C.evidence_message(e2)) if 'signer' not in change else e2['signature']
            return dict(item, evidence=e2)
        unverified.update({'a report not the gate\'s': C.run_outcome('EFFECT', [regate(i) for i in ev0], fail_a.get('result'), s.keys['gate'], root, fail_a.get('aid'), fail_a.get('nonce')),
                           'a report for another nonce': C.run_outcome('EFFECT', ev0, fail_a.get('result'), s.keys['gate'], root, fail_a.get('aid'), 'n-another')})
        # the courier's own refusal of checkpoints, with the witness's answers replaced in process
        ccfg = json.loads((s.dir / 'courier.json').read_text())
        def answered(make):
            orig = courier.https
            def fake(method, u, cfg, body=None, timeout=15.0):
                qs = urllib.parse.parse_qs(urllib.parse.urlsplit(u).query)
                return 200, make(qs.get('nonce', [None])[0], int(qs.get('at', ['0'])[0]))
            courier.https = fake
            try:
                return courier.checkpoint(ccfg, root, live['seq'])
            except courier.Refused as exc:
                return 'refused: ' + str(exc.args[0])
            except Exception as exc:
                return f'RAISED {type(exc).__name__}: {exc}'
            finally:
                courier.https = orig
        lv = live if isinstance(live, dict) else {}
        mk = lambda key, nonce, at: sign_checkpoint(key, root, lv.get('seq'), lv.get('head'), lv.get('business'), lv.get('witness'), lv.get('time'), nonce, at, lv.get('head') if at == lv.get('seq') else '0' * 64)
        courier_takes = {'its own nonce, the decision asked': answered(lambda n, at: mk(s.witness, n, at)), 'an old checkpoint handed back': answered(lambda n, at: mk(s.witness, 'an-earlier-nonce', at)),
                         'another decision named': answered(lambda n, at: mk(s.witness, n, at - 1)), 'signed by another key': answered(lambda n, at: mk(Signer(), n, at))}
        # the courier reading the chain a few decisions at a time, from the start
        c_paged = step(s.courier, [root], 0, 'courier4', 5)
        # what the witness says cannot be read: the courier refuses it, stops, and tells the mailbox
        cfg5 = json.loads(s.courier_config([root], 0, 'courier5').read_text())
        def malformed(answer, path='/chain?'):
            orig = courier.https
            def fake(method, u, cfg, body=None, timeout=15.0):
                return (200, answer) if path in u else orig(method, u, cfg, body, timeout)
            courier.https = fake
            try:
                state = s.dir / 'courier5' / 'state.json'
                state.unlink(missing_ok=True)
                return courier.one_pass(cfg5)
            except BaseException as exc:
                return f'RAISED {type(exc).__name__}: {exc}'
            finally:
                courier.https = orig
        bad_answers = {k: malformed(v) for k, v in (('a decision with no number', {'rows': [{}]}), ('a number that is text', {'rows': [{'seq': '1'}]}), ('no decisions', {'rows': []}),
                                                    ('a decision with no operation', {'rows': [{'seq': 1, 'observation': {}, 'kind': 'APPLIED', 'code': 'X', 'prev_hash': '', 'hash': ''}]}))}
        bad_answers['reports that are not a list'] = malformed({'evidence': 5, 'result': None}, '/run?')
        stopped_alarms = [d['notice'].get('outcome') for d in courier.read_deliveries(s.dir / 'courier5' / 'deliveries.jsonl', root)]
        # a witness the courier cannot reach
        cfg6 = json.loads(s.courier_config([root], 3600, 'courier6').read_text()); cfg6['witness_url'] = 'https://127.0.0.1:8979'
        (s.dir / 'courier6.json').write_text(json.dumps(cfg6))
        p6w = subprocess.run([PY, '-B', str(GATEWAY / 'verify' / 'courier.py'), 'run', '--config', str(s.dir / 'courier6.json')], capture_output=True, text=True, timeout=120)
        early_alarms = len(courier.read_deliveries(s.dir / 'courier6' / 'deliveries.jsonl', root))
        cfg6['stall_after'] = 0; (s.dir / 'courier6.json').write_text(json.dumps(cfg6))
        p6 = subprocess.run([PY, '-B', str(GATEWAY / 'verify' / 'courier.py'), 'run', '--config', str(s.dir / 'courier6.json')], capture_output=True, text=True, timeout=120)
        p6b = subprocess.run([PY, '-B', str(GATEWAY / 'verify' / 'courier.py'), 'run', '--config', str(s.dir / 'courier6.json')], capture_output=True, text=True, timeout=120)
        made_b = step(lambda: [m.get('outcome') for m in json.loads(p6b.stdout.strip().splitlines()[-1]).get('made', [])])
        blocked = (p6w.returncode, early_alarms, p6.returncode, p6b.returncode, [d['notice'].get('outcome') for d in courier.read_deliveries(s.dir / 'courier6' / 'deliveries.jsonl', root)], made_b)
        # the mailbox under a client that sends nothing, a body too long, and a notice spelt another way
        import socket as _socket
        idle = _socket.create_connection(('127.0.0.1', s.ports['mailbox']), timeout=5)
        try:
            t0 = time.time(); while_idle = call(mb_url, '/pubkey', courier_cert)[0]; idle_seconds = time.time() - t0
        finally:
            idle.close()
        too_long = call(mb_url, '/deliver', courier_cert, 'POST', raw_body=b'{"x": "' + b'a' * 70000 + b'"}')[0]
        upper = dict(one, signature=str(one.get('signature', '')).upper())
        before_upper = len(list((s.dir / 'mailbox' / 'notices').glob('*.json')))
        upper_ans = call(mb_url, '/deliver', courier_cert, 'POST', upper)[0]
        after_upper = len(list((s.dir / 'mailbox' / 'notices').glob('*.json')))
        # an attempt the gateway names oddly, started and never admitted: its notice comes, and it hides no other run
        local = Store(deploy.LOCAL_DSN); gov = s.pki['governor']; odd = '!x'
        def odd_step(op):
            d, _ = local.apply(root, op); return d.kind
        def odd_accept(op):
            st_, ans = call(url, '/accept', gov, 'POST', {'root': root, 'op': [op, odd], 'evidence': None})
            if st_ == 200 and ans.get('kind') in ('APPLIED', 'DUPLICATE'):
                local.put_receipt(root, odd, ans['seq'], ans['receipt'], op)
            return st_ if ans is None else (st_, ans.get('kind'))
        odd_steps = [step(odd_step, ('RESERVE', odd, 'verify:odd')), step(odd_accept, 'ACCEPT_RESERVATION'), step(odd_step, ('TOKEN', odd)), step(odd_step, ('START', odd, 'n-odd'))]
        odd_phase = next((x[2] for x in Store(deploy.LOCAL_DSN).audit_snapshot(root)[1]['attempts'] if x[0] == odd), None)
        c_odd = step(s.courier, [root], 0, 'courier7')
        odd_steps += [step(odd_accept, 'ACCEPT_INTENT'), step(odd_step, ('RECEIPT', odd)), step(odd_accept, 'CROSS')]
        odd_after = next((x[2] for x in Store(deploy.LOCAL_DSN).audit_snapshot(root)[1]['attempts'] if x[0] == odd), None)
        c_odd2 = step(s.courier, [root], 0, 'courier7')                                            # now admitted and crossed, it is asked after by name
        # the witness refusing to answer for one run: the others are still read, and that one is read when it answers
        cfg8 = json.loads(s.courier_config([root], 0, 'courier8').read_text())
        fail_aids_all = sorted(x['notice'].get('aid') for x in courier.read_deliveries(s.dir / 'courier' / 'deliveries.jsonl', root) if x['notice'].get('outcome') == 'FAIL')
        refused_aid = fail_aids_all[0] if fail_aids_all else None
        def one_refused():
            orig = courier.https
            def fake(method, u, cfg, body=None, timeout=15.0):
                if '/run?' in u and urllib.parse.parse_qs(urllib.parse.urlsplit(u).query).get('aid', [None])[0] == refused_aid:
                    return 503, {'error': 'not now'}
                return orig(method, u, cfg, body, timeout)
            courier.https = fake
            try:
                return courier.one_pass(cfg8)
            except BaseException as exc:
                return {'error': f'{type(exc).__name__}: {exc}'}
            finally:
                courier.https = orig
        s8a = one_refused(); s8b = step(courier.one_pass, cfg8)
        isolated = ([(m.get('aid') == refused_aid, m.get('outcome')) for m in sorted(s8a.get('made', []), key=lambda m: (m.get('aid') == refused_aid, m.get('outcome')))] if isinstance(s8a, dict) else s8a,
                    len(s8a.get('unreachable', [])) if isinstance(s8a, dict) else None,
                    [(m.get('aid') == refused_aid, m.get('outcome')) for m in s8b.get('made', [])] if isinstance(s8b, dict) else s8b)
        odd_made = sorted((x.get('aid') == odd, x.get('outcome')) for x in (c_odd[1].get('made') or [])) if isinstance(c_odd, tuple) and isinstance(c_odd[1], dict) else c_odd
        # a record without notices, and the console
        plain = step(s.record, r.h, [r.ws / '.verify' / 'submissions.jsonl'])
        okp, checksp, sp = C.verify(plain, s.keys) if isinstance(plain, dict) else (False, [], {})
        cli_plain = cli(save('plain.json', plain if isinstance(plain, dict) else {}), '--keys', keys, '--require-delivery')
        keyfile = here / 'engineer.key'; keyfile.write_text(s.engineer.private_hex + '\n')
        base = [PY, '-B', str(GATEWAY / 'verify' / 'verify_ctl.py'), 'record', str(s.home), r.h, '--key', str(keyfile), '--witness-key', s.keys['witness'], '--gate-key', s.keys['gate'],
                '--journal', str(r.ws / '.verify' / 'submissions.jsonl'), '--deliveries', str(s.dir / 'courier' / 'deliveries.jsonl')]
        console = subprocess.run(base + ['--out', str(here / 'rec_console.json'), '--courier-key', s.keys['courier'][0], '--mailbox-key', s.keys['mailbox'][0]], capture_output=True, text=True, timeout=120)
        rec_c = json.loads((here / 'rec_console.json').read_text()) if console.returncode == 0 else {}
        console_ok = bool(rec_c) and C.verify(rec_c, s.keys)[0] and len(rec_c.get('deliveries') or []) == len(rec.get('deliveries') or [])
        console_nokeys = subprocess.run(base + ['--out', str(here / 'rec_console2.json')], capture_output=True, text=True, timeout=120)
        # a run cut off again, then the budget re-registered by the control plane: the run is INDETERMINATE
        s.stop_host(); s.start_host('verify_running')
        cut2 = r.submit({'material': 'PPS-GF40', 'wall_mm': 4, 'mode': 'normal'}); time.sleep(0.3); host_exit2 = s.procs['host'].poll()
        rereg = step(Store(verify_ctl.CONTROL_DSN).apply, root, ('REREGISTER',))
        resumed = subprocess.run([PY, '-B', str(GATEWAY / 'verify' / 'courier.py'), 'resume', '--config', str(s.dir / 'courier.json'), '--root', root], capture_output=True, text=True, timeout=60).returncode
        c_indet = run_courier(0)
        rec3 = step(s.record, r.h, [r.ws / '.verify' / 'submissions.jsonl'], deliveries=True)
        ok3, _, s3 = C.verify(rec3, s.keys) if isinstance(rec3, dict) else (False, [], {})
        indet = (host_exit2, resumed, rereg[0].code if isinstance(rereg, tuple) and hasattr(rereg[0], 'code') else str(rereg)[:80], made(c_indet), ok3,
                 sorted((d['outcome'], d['delivered']) for d in (s3.get('delivery') or {}).get('due', [])))

        e.update(host_exit=host_exit, cut=cut[0], again=again[0], bad=bad[0], good=good[0], bad2=bad2[0], own=own,
                 couriers={k: (v[0], made(v), delivered(v)) if isinstance(v, tuple) and len(v) == 2 and isinstance(v[1], dict) else v
                           for k, v in dict(wait=c_wait, cut=c_cut, interrupted=c_int, fail=c_fail, again=c_again, down=c_down, up=c_up, fork=c_fork, fork2=c_fork2, roll=c_roll).items()},
                 waiting=(c_down[1].get('waiting') if isinstance(c_down, tuple) and isinstance(c_down[1], dict) else c_down), held=len(held), log=len(log),
                 headlines=sorted(t.splitlines()[0] for t in texts), reads=(before, after), chain=(ch[0], len((ch[1] or {}).get('rows', [])), isinstance(chained, list), isinstance(live, dict) and live.get('seq')),
                 run=(run_ans[0], len((run_ans[1] or {}).get('evidence', [])), isinstance((run_ans[1] or {}).get('result'), dict)), witness_says=witness_says, mailbox_says=mailbox_says,
                 same_receipt=same_receipt, files=(n_files, n_files_after), pinned=c_pinned, wrongbox=(c_wrongbox[0], c_wrongbox[1].get('waiting', [{}])[0].get('why', '')[:300] if isinstance(c_wrongbox[1], dict) and c_wrongbox[1].get('waiting') else c_wrongbox[1]),
                 rows_refused=rows_refused, wrong_head=str(wrong_head)[:120], forks=[(f.get('why', '')[:60], (f.get('evidence') or {}).get('statement')) for f in forks],
                 rolls=[(f.get('why', '')[:60], (f.get('evidence') or {}).get('statement'), (f.get('evidence') or {}).get('seq')) for f in rolls],
                 record=(ok, ten, dv), cli_full=cli_full, dropped=(okd, (sd.get('delivery') or {}).get('due')), cli_dropped=cli_dropped, tampered=tampered,
                 unverified=unverified, courier_takes={k: v if isinstance(v, str) else 'TAKEN' for k, v in courier_takes.items()}, no_int=(oki, (si.get('delivery') or {}).get('due')), early=(okx, ((sx.get('delivery') or {}).get('due'))), plain=(okp, next(((n, t, g) for n, t, g, _ in checksp if n == 10), None), sp.get('delivery')), cli_plain=cli_plain,
                 console=(console.returncode, console.stderr[:200]), console_nokeys=(console_nokeys.returncode, console_nokeys.stderr[:160]),
                 three_keys=three_keys, cli_three=cli_three, cli_five=cli_five[0], paged=(c_paged[0], made(c_paged)) if isinstance(c_paged, tuple) else c_paged,
                 bad_answers={k: (v.get('refused'), [m.get('outcome') for m in v.get('made', [])]) if isinstance(v, dict) else v for k, v in bad_answers.items()},
                 stopped_alarms=stopped_alarms, blocked=blocked, odd=(odd_steps, odd_phase, odd_after, c_odd[0] if isinstance(c_odd, tuple) else c_odd, odd_made), words_differ=words_differ,
                 odd2=(c_odd2[0], made(c_odd2)) if isinstance(c_odd2, tuple) else c_odd2, isolated=isolated, idle=(while_idle, round(idle_seconds, 1)), too_long=too_long, upper=(upper_ans, before_upper, after_upper), indet=indet)
        cs = e['couriers']; cut_aid = next((x['notice']['aid'] for x in log if x['notice'].get('outcome') == 'INTERRUPTED'), None)
        checks = {'the witness gives the courier\'s certificate its decisions, which follow on from the head a checkpoint names for decision 0 and hash one to the next, and a run\'s signed gate reports and stored result; reading adds no decision':
                      ch[0] == 200 and e['chain'][1] == before and isinstance(chained, list) and isinstance(live, dict) and live.get('seq') == before
                      and e['run'] == (200, 1, True) and before == after,
                  'the witness answers 404 for a budget it does not hold and 400 for no budget, a number that is not one, a page of 0 or 201 decisions, a budget name with a control character, no run named and a run named with a control character':
                      [witness_says[k] for k in ('chain, unknown budget', 'chain, no budget', 'chain, after not a number', 'chain, limit 0', 'chain, limit 201', 'chain, control character',
                                                 'run, unknown budget', 'run, no attempt', 'run, attempt with a control character')] == [404, 400, 400, 400, 400, 400, 404, 400, 400],
                  'the courier\'s certificate reads and can do nothing else: the witness refuses its write (403) and its other question (403); a certificate the witness does not know is refused the chain (403), and so is the keeper, which reads checkpoints only':
                      (witness_says['courier writes'], witness_says['courier asks the key'], witness_says['stranger reads the chain'], witness_says['keeper reads the chain']) == (403, 403, 403, 403),
                  'a run cut off when the gate host dies gets no notice before the courier has seen it with no outcome for the time allowed, then a notice that it has none; once the gate signs that it does not know the outcome, a notice that it was interrupted; each is delivered':
                      host_exit == 137 and cs.get('wait', (None,))[:3] == (0, [], []) and cs.get('cut', (None,))[:3] == (0, ['NO_OUTCOME'], ['NO_OUTCOME'])
                      and again[0] == 3 and cs.get('interrupted', (None,))[:3] == (0, ['INTERRUPTED'], ['INTERRUPTED']),
                  'a failing run whose own notice was taken out of the service\'s inbox still gets the courier\'s notice of the failure, delivered; a passing run gets none; a second pass sends nothing more':
                      bad[0] == 2 and len(own) == 1 and good[0] == 0 and cs.get('fail', (None,))[:3] == (0, ['FAIL'], ['FAIL']) and cs.get('again', (None,))[:3] == (0, [], []),
                  'the mailbox holds each notice, and the courier\'s statement that it watches the budget (Amendment 16), with its receipt, which verifies under the mailbox\'s key and names that notice, and a readable copy that opens with what happened; the failure\'s copy gives the numbers, shown as data (Amendment 16); the courier\'s log holds the same notices':
                      len(held) == 4 and all(C.notice_problems(h['notice'], s.keys['courier']) == [] and C.receipt_problems(h['receipt'], s.keys['mailbox'], h['notice']) == [] for h in held)
                      and e['headlines'] == sorted(['A RUN WAS ADMITTED AND HAS NO OUTCOME', 'DECLARED CHECK NOT MET (FAIL)', 'THE RUN WAS INTERRUPTED: ADMITTED AND COUNTED, WITH NO VERDICT', 'THE COURIER HAS BEGUN TO WATCH THIS BUDGET'])
                      and any('achieved "180", comparison ">=", limit "200"' in t for t in texts) and len(log) == 4 and sorted(C.notice_digest(x['notice']) for x in log) == sorted(C.notice_digest(h['notice']) for h in held),
                  'the courier\'s configuration names neither the service\'s home nor its database; it holds the courier\'s certificate and the witness\'s address':
                      str(s.home) not in cfg_text and 'postgresql' not in cfg_text and s.pki['courier'][0] in cfg_text and url in cfg_text,
                  'with the mailbox down, the notice of a failure is made and waits, and the pass exits 1; with the mailbox back, the next pass delivers it, makes no other, and exits 0':
                      bad2[0] == 2 and cs.get('down', (None,))[:3] == (1, ['FAIL'], []) and isinstance(e['waiting'], list) and len(e['waiting']) == 1 and cs.get('up', (None,))[:3] == (0, [], ['FAIL']),
                  'the mailbox refuses a notice signed by another key (403), one that is not a notice (400), a body that is not JSON (400) and a client that is not the courier (403); a notice delivered again gets the receipt first given and is kept once':
                      mailbox_says == {'another key': 403, 'not a notice': 400, 'not JSON': 400, 'keeper delivers': 403} and same_receipt and n_files == n_files_after,
                  'a courier given another key for the mailbox takes no answer of the mailbox as a receipt: nothing is delivered, the notices wait, and the pass exits 1':
                      c_wrongbox[0] == 1 and 'not one given to the courier, so no answer of it can be taken as a receipt' in str(e['wrongbox'][1]),   # fifth form: the courier asks the mailbox's key first
                  'a courier whose mailbox gives the key the courier was given when asked for it, but signs its receipts with its own (the real mailbox), takes none of its answers as a receipt: nothing is delivered, each is listed as no valid receipt, the notices wait, and the pass exits 1':
                      c_pinned[0] == [] and c_pinned[1] == ['the mailbox gave no valid receipt'] and c_pinned[2] >= 1 and c_pinned[3] is True,
                  'the courier refuses decisions that were changed, skip one, or do not end at the head the checkpoint names, and takes them when they are whole':
                      rows_refused == [True, True, True] and 'RAISED' in e['wrong_head'] and 'Refused' in e['wrong_head'],
                  'a courier whose last head the witness contradicts refuses the budget (a fork), keeps the witness\'s signed checkpoint as the evidence, exits 1, and stays stopped at the next pass':
                      cs.get('fork', (None,))[0] == 1 and cs.get('fork2', (None,))[0] == 1 and len(forks) == 1 and forks[0].get('why', '').startswith('FORK') and (forks[0].get('evidence') or {}).get('statement') == 'CHECKPOINT',
                  'a courier told that the last decision it read is beyond the chain refuses the budget (a rollback), and keeps the witness\'s signed checkpoint of the shorter chain as the evidence':
                      isinstance(c_r2, tuple) and c_r2[0] == 0 and cs.get('roll', (None,))[0] == 1 and len(rolls) == 1 and rolls[0].get('why', '').startswith('ROLLBACK')
                      and (rolls[0].get('evidence') or {}).get('statement') == 'CHECKPOINT' and (rolls[0].get('evidence') or {}).get('seq') == after,
                  'a record built with the courier\'s log verifies with a tenth check, the notices delivered; each run that calls for a notice (two failures and the interruption) has one delivered, and the run once without an outcome is named; the checker\'s command says so and exits 0 when delivery is required':
                      ok and ten == (10, 'notices delivered', True) and sorted(d['outcome'] for d in dv.get('due', [])) == ['FAIL', 'FAIL', 'INTERRUPTED'] and all(d['delivered'] for d in dv.get('due', []))
                      and dv.get('no_outcome') == [cut_aid] and dv.get('notices') == 4 and cli_full[0] == 0 and len(cli_full[1]) == 1 and cli_full[1][0].startswith('NOTICES: 3 of 3 runs'),
                  'a record that lacks the notice of one failure verifies, and says that run has no delivery evidence; the command exits 1 when delivery is required; a record that lacks the notice of the interruption says so, though it holds the earlier notice that the run had no outcome':
                      okd and sorted((d['outcome'], d['delivered']) for d in e['dropped'][1] or []) == [('FAIL', False), ('FAIL', True), ('INTERRUPTED', True)]
                      and cli_dropped[0] == 1 and 'NO DELIVERY EVIDENCE' in (cli_dropped[1] or [''])[0]
                      and oki and [d['delivered'] for d in e['no_int'][1] or [] if d['outcome'] == 'INTERRUPTED'] == [False],
                  'the notices in a record cannot be changed or made up unseen: a notice edited, one signed by another courier key, one with a field added, one for another budget, a receipt signed by another key or for another notice, a notice naming a decision not in the record\'s chain, and one that says what the record does not (in its outcome or in its words), each fail check 10 alone':
                      all(v == [10] for v in tampered.values()) and words_differ,
                  'a run the gate signed an effect for is UNVERIFIED with no result, or with a result that does not hash to the digest the gate signed, and has its verdict with the true one; a notice that vouches for no result, made at that decision, is taken':
                      unverified == {'no result': 'UNVERIFIED', 'a result changed': 'UNVERIFIED', 'the result': 'FAIL', 'a report not the gate\'s': 'UNVERIFIED', 'a report for another nonce': 'UNVERIFIED'}
                      and okx and e['early'][1] == dv.get('due'),
                  'the courier takes a checkpoint signed by the witness that signs back its own nonce and names the decision it asked about, and refuses an old one handed back, one naming another decision, and one signed by another key':
                      e['courier_takes']['its own nonce, the decision asked'] == 'TAKEN' and all(str(e['courier_takes'][k]).startswith('refused') for k in ('an old checkpoint handed back', 'another decision named', 'signed by another key')),
                  'a record carrying notices, checked with the three keys alone, verifies and says its notices were not checked; the command exits 1 when delivery is required, and 0 with the courier\'s and the mailbox\'s keys given':
                      three_keys[0] and three_keys[1] == (10, 'notices delivered (not checked: no courier and mailbox keys were given with the others)', True) and bool(three_keys[2])
                      and cli_three[0] == 1 and (cli_three[1] or [''])[0].startswith('NOTICES: NOT CHECKED.  The record carries') and cli_five[0] == 0,
                  'a courier reading the chain five decisions at a time, from the start, makes the notices of the interruption and the two failures, and delivers them':
                      isinstance(c_paged, tuple) and c_paged[0] == 0 and made(c_paged) == ['FAIL', 'FAIL', 'INTERRUPTED'],
                  'a courier given decisions it cannot read (one with no number, one numbered in text, one with no operation), none where the checkpoint says there are some, or a run\'s reports that are not a list, refuses the budget, does not stop with an error, and delivers to the mailbox a signed notice that it has stopped':
                      all(isinstance(v, dict) and len(v.get('refused') or []) == 1 and [m.get('outcome') for m in v.get('made', [])] == ['COURIER_STOPPED'] for v in bad_answers.values())
                      and stopped_alarms == ['COURIER_STOPPED'] * 5,
                  'a courier that cannot reach the witness exits 1; it sends nothing until it has been blocked for the time allowed, then one signed notice that it is blocked, not one at each pass':
                      blocked == (1, 0, 1, 1, ['COURIER_BLOCKED'], []),
                  'a client that connects to the mailbox and sends nothing does not hold up another; a body over 64 KiB is refused (400); a notice whose signature is spelt in capitals is refused (403) and not kept':
                      e['idle'][0] == 200 and e['idle'][1] < 5 and too_long == 400 and upper_ans == 403 and before_upper == after_upper,
                  'when the control plane re-registers the budget, the run cut off before, the oddly named run and a run cut off now are made INDETERMINATE; a courier resumed after its refusal reads the budget again and sends a notice of each, and a record built after shows all three delivered':
                      indet[0] == 137 and indet[1] == 0 and indet[2] == 'REREGISTERED_REDUCED' and indet[3] == ['INDETERMINATE'] * 3 and indet[4]
                      and [x for x in indet[5] if x[0] == 'INDETERMINATE'] == [('INDETERMINATE', True)] * 3 and all(d for _, d in indet[5]),
                  'an attempt the gateway names oddly ("!x"), started and never admitted, gets a notice that it has no outcome, beside the notices of the other runs; once admitted and crossed, the witness answers for it by that name, and the courier sends nothing more of it':
                      odd_steps == ['APPLIED', (200, 'APPLIED'), 'APPLIED', 'APPLIED', (200, 'APPLIED'), 'APPLIED', (200, 'APPLIED')] and odd_phase == 'INTENT_PENDING' and odd_after == 'CONSUMED'
                      and isinstance(c_odd, tuple) and c_odd[0] == 0
                      and odd_made == [(False, 'FAIL'), (False, 'FAIL'), (False, 'INTERRUPTED'), (True, 'NO_OUTCOME')] and e['odd2'] == (0, []),
                  'when the witness will not answer for one run, the courier still reads the others and sends their notices, says it could not read that one (with no time allowed, a notice that it cannot read that run, and no budget reported unreachable: Amendment 16), and sends its notice at the next pass, when the witness answers':
                      isolated[0] == [(False, 'FAIL'), (False, 'INTERRUPTED'), (False, 'NO_OUTCOME'), (True, 'UNREADABLE')] and isolated[1] == 0 and isolated[2] == [(True, 'FAIL')]
                      and isinstance(s8a, dict) and [u.get('aid') for u in s8a.get('unread', [])] == [refused_aid],
                  'a record without notices verifies and says it has none; the command says notices were not checked and exits 1 when delivery is required; the engineer\'s console, given the courier\'s log and the two keys, writes a record that carries the notices and verifies, and refuses without the keys':
                      okp and e['plain'][1] == (10, 'notices delivered (none in this record)', True) and sp.get('delivery') is None and cli_plain[0] == 1 and (cli_plain[1] or [''])[0].startswith('NOTICES: NOT CHECKED')
                      and console.returncode == 0 and console_ok and console_nokeys.returncode == 1}
    finally:
        r.stop()
    return checks, e


def r27():
    """Each run of a check is made a disposable sandbox of its own: no network, no other process, none of the service's files,
    nobody's identity, limits on time, memory, processes and output, and nothing kept after it.  A check that tries to read
    the service's keys, reach its database or the witness, write outside its /work and /tmp, or outlive its run cannot; and
    if the sandbox cannot be made, the check is not run.  (Amendment 12.)"""
    s = deploy.Services(OUT / 'R27').start(); e = {}
    try:
        import sandbox
        here = OUT / 'R27'
        def step(f, *a, **kw):
            try:
                return f(*a, **kw)
            except Exception as exc:
                return ('RAISED', f'{type(exc).__name__}: {exc}')
        env = step(s.baseline, CASE, draft())                                                   # baselining runs the controls in the sandbox: a broken sandbox fails the checks below
        h = env.get('baseline_sha256') if isinstance(env, dict) else None
        req = (env.get('card') or {}).get('requirement') if isinstance(env, dict) else json.loads((CASE / 'card.json').read_text())['requirement']
        cfg = s.client_config(OUT / 'R27' / 'workspace', h) if h else None
        submit = lambda design: s.submit(cfg, design) if cfg else (None, 'no baseline')
        def checked():
            rec = step(s.record, h, [OUT / 'R27' / 'workspace' / '.verify' / 'submissions.jsonl']) if h else None
            if not isinstance(rec, dict):
                return False, [str(rec)], {}
            ok, checks, summ = check_record.verify(rec, s.keys)
            return ok, [f'{n} {t}: {d}' for n, t, good, d in checks if not good], summ
        def boxed(src, stdin=b'{}', **kw):                                                     # one run of a script in the sandbox: (state, exit status, what it printed)
            o = step(sandbox.run, {'c.py': src.encode(), 'data.csv': b'a,b\n1,2\n'}, 'c.py', stdin, **kw)
            return (o.state, o.returncode, o.stdout.decode(errors='replace')[:2000], o.stderr.decode(errors='replace')[-300:], o.detail) if not isinstance(o, tuple) else o
        said = lambda out: head(out) if isinstance(out, str) else str(out)[:300]                 # what a step said, if it said something other than text
        def printed(o):
            try:
                return json.loads(o[2])
            except Exception:
                return o
        secrets = [str(s.dir / 'engineer.key'), str(s.dir / 'courier.key'), str(s.pki['witness'][1]), str(s.home / 'ledger.jsonl'), str(s.home / 'baselines'),
                   '/etc/passwd', '/proc/self/environ', '/root', str(GATEWAY / 'verify' / 'deploy.py')]
        probe = ("import json, os, socket\n"
                 "def read(p):\n"
                 "    try:\n"
                 "        return 'listed' if os.path.isdir(p) and os.listdir(p) is not None else ('read' if open(p, 'rb').read(1) is not None else 'read')\n"
                 "    except Exception as e:\n"
                 "        return type(e).__name__\n"
                 "def reach(h, p):\n"
                 "    try:\n"
                 "        s = socket.socket(); s.settimeout(2); s.connect((h, p)); return 'connected'\n"
                 "    except Exception as e:\n"
                 "        return type(e).__name__\n"
                 "def write(p):\n"
                 "    try:\n"
                 "        open(p, 'w').write('x'); return 'written'\n"
                 "    except Exception as e:\n"
                 "        return type(e).__name__\n"
                 f"SECRETS = {secrets!r}\n"
                 f"PORTS = [('127.0.0.1', {s.ports['witness']}), ('127.0.0.1', {s.ports['host']}), ('127.0.0.1', 5432), ('8.8.8.8', 53)]\n"
                 "found = {'uid': os.getuid(), 'gid': os.getgid(), 'groups': os.getgroups(), 'cwd': os.getcwd(), 'root': sorted(os.listdir('/')),\n"
                 "         'here': sorted(os.listdir('.')), 'read': {p: read(p) for p in SECRETS}, 'reach': [reach(h, p) for h, p in PORTS],\n"
                 "         'kept': os.path.exists('/work/kept-from-before'), 'write': {p: write(p) for p in ('/x', '/usr/x', '/dev/x', '/work/kept-from-before', '/tmp/x')}}\n")
        # what a check sees and can do, run straight in the sandbox
        first = printed(boxed(probe + "print(json.dumps(found))"))
        second = printed(boxed(probe + "print(json.dumps(found))"))
        mark = f'r27-{uuid.uuid4().hex[:8]}'
        t0 = time.monotonic(); piped = boxed("import sys, time\nsys.stdin.buffer.read(8192)\ntime.sleep(20)", stdin=b'x' * 500000, timeout=3); e['piped_seconds'] = round(time.monotonic() - t0, 2)   # it reads a little, so the pipe has room again, then stops
        grouped = subprocess.run([PY, '-B', '-c', "import sys; sys.path.insert(0, sys.argv[1]); import sandbox; o = sandbox.run({'c.py': b'import os; print(os.getgroups())'}, 'c.py', b''); print(o.state, o.stdout.decode().strip())",
                                  str(GATEWAY / 'verify')], capture_output=True, text=True, timeout=60, extra_groups=[4242])   # a service that holds a group of its own: the check holds none
        e['grouped'] = grouped.stdout.strip()
        t0 = time.monotonic(); escape = boxed(f"import os, sys, time\nos.setsid()\nfor i in range(3):\n    if os.fork() == 0:\n        os.execv(sys.executable, [sys.executable, '-c', 'import time; time.sleep(120)', '{mark}-e'])\nos.execv(sys.executable, [sys.executable, '-c', 'import time; time.sleep(120)', '{mark}-e'])", timeout=2); e['escape_seconds'] = round(time.monotonic() - t0, 2)   # it leaves its process group: the run still ends at its time, not at the launcher's
        limits = {'fork bomb': boxed("import os\nn = 0\ntry:\n    while n < 300:\n        if os.fork() == 0:\n            import time; time.sleep(30); os._exit(0)\n        n += 1\n    print(n, 'no limit')\nexcept Exception as e:\n    print(n, type(e).__name__)"),
                  'escape': escape,
                  'memory, many processes': boxed("import os, sys, time\nfor i in range(6):\n    if os.fork() == 0:\n        x = bytearray(900 * 1024 ** 2); time.sleep(3); print('alive', flush=True); os._exit(0)\n"
                                                  "x = bytearray(900 * 1024 ** 2)\ntime.sleep(3)\nprint('alive', flush=True)\ntime.sleep(1)", timeout=10),
                  'disk, many files': boxed("n = 0\ntry:\n    while n < 40:\n        open(f'/work/f{n}', 'wb').write(b'x' * (10 << 20)); n += 1\n    print(n, 'no limit')\nexcept Exception as e:\n    print(n, type(e).__name__)"),
                  'a design larger than the pipe': piped,
                  'keyring, first run': boxed("import ctypes\nlibc = ctypes.CDLL(None, use_errno=True)\nlibc.syscall.restype = ctypes.c_long\n"
                                              "r = libc.syscall(248, b'user', b'r27-kept', b'secret', 6, ctypes.c_int(-4))\nprint('added' if r > 0 else 'refused %d' % ctypes.get_errno())"),
                  'keyring, next run': boxed("import ctypes\nlibc = ctypes.CDLL(None, use_errno=True)\nlibc.syscall.restype = ctypes.c_long\n"
                                             "r = libc.syscall(249, b'user', b'r27-kept', None, ctypes.c_int(0))\nprint('found' if r > 0 else 'not found')"),
                  'host': boxed("import os, socket, sys\ntry:\n    import cryptography; site = 'imported'\nexcept ImportError:\n    site = 'ImportError'\nprint(socket.gethostname(), sorted(os.listdir('/usr/local')), site, sys.flags.no_site, sys.flags.isolated)"),
                  'calls': boxed("import json, os, socket, sys\nr = {}\nfor name, fam in (('vsock', 40), ('packet', 17), ('netlink', 16), ('unix', 1), ('inet', 2)):\n    try:\n        socket.socket(fam, socket.SOCK_RAW if fam in (16, 17) else socket.SOCK_STREAM).close(); r[name] = 'made'\n"
                                 "    except OSError as e:\n        r[name] = e.errno\ntry:\n    socket.socketpair(); r['pair'] = 'made'\nexcept OSError as e:\n    r['pair'] = e.errno\nst = os.statvfs('/work'); r['work_bytes'] = st.f_frsize * st.f_blocks\n"
                                 "sys.path.append('/usr/lib/python3/dist-packages')\ntry:\n    import yaml; r['dist'] = 'imported'\nexcept ImportError:\n    r['dist'] = 'ImportError'\n"
                                 "import ctypes, resource\nlibc = ctypes.CDLL(None, use_errno=True); libc.syscall.restype = ctypes.c_long; ctx = ctypes.c_ulong(0)\n"
                                 "r['aio'] = [libc.syscall(206, 1, ctypes.byref(ctx)), ctypes.get_errno()]\n"
                                 "r['bounding'] = [c for c in range(64) if libc.prctl(23, c, 0, 0, 0) == 1]\n"
                                 "r['rlimits'] = [resource.getrlimit(resource.RLIMIT_SIGPENDING)[0], resource.getrlimit(resource.RLIMIT_MSGQUEUE)[0]]\nprint(json.dumps(r))"),
                  'memory': boxed("x = bytearray(2 * 1024 ** 3)\nprint('got it')"),
                  'output': boxed("import sys\nwhile True:\n    sys.stdout.write('x' * 65536)"),
                  'spin': boxed("while True:\n    pass", timeout=3),
                  'disk': boxed("f = open('/work/big', 'wb')\ntry:\n    f.write(b'x' * (100 << 20)); print('wrote')\nexcept Exception as e:\n    print(type(e).__name__)"),
                  'left behind': boxed(f"import os, sys, time\nif os.fork() == 0:\n    os.setsid(); sys.argv[0] = '{mark}'\n    os.execv(sys.executable, [sys.executable, '-c', 'import time; time.sleep(120)', '{mark}'])\nprint('parent done')"),
                  'others': boxed("import os\nr = []\nfor pid in (1, 50, 300, 4000):\n    try:\n        os.kill(pid, 0); r.append('seen')\n    except Exception as e:\n        r.append(type(e).__name__)\nprint(r)")}
        time.sleep(0.5)
        survivors = subprocess.run(['pgrep', '-f', mark], capture_output=True, text=True).stdout.split()
        for _ in range(30):                                                                     # no live process of any run's own identities is left (a zombie waits only to be reaped)
            rows = [l.split() for l in subprocess.run(['ps', '-eo', 'uid=,stat='], capture_output=True, text=True).stdout.splitlines()]
            run_left = [u for u, *st in rows if u.isdigit() and int(u) >= sandbox.UID_BASE and not (st and st[0].startswith('Z'))]
            if not run_left:
                break
            time.sleep(0.1)
        # two runs, watched from outside: their host ids differ
        def ids_during(sleep_s):
            seen, box = set(), {}
            th = threading.Thread(target=lambda: box.update(o=boxed(f"import time\ntime.sleep({sleep_s})")))
            th.start()
            while th.is_alive():
                for l in subprocess.run(['ps', '-eo', 'uid='], capture_output=True, text=True).stdout.split():
                    if l.isdigit() and int(l) >= sandbox.UID_BASE:
                        seen.add(int(l))
                time.sleep(0.1)
            th.join(); return sorted(seen)
        e['host_ids'] = [ids_during(1.5), ids_during(1.5)]
        # the service killed in the middle of a run: the run ends with it
        def run_procs():
            rows = [l.split() for l in subprocess.run(['ps', '-eo', 'uid=,stat='], capture_output=True, text=True).stdout.splitlines()]
            return [u for u, *st in rows if u.isdigit() and int(u) >= sandbox.UID_BASE and not (st and st[0].startswith('Z'))]
        def cmdline(p):
            try:
                return pathlib.Path(f'/proc/{p}/cmdline').read_bytes()
            except OSError:
                return b''
        def run_pids():
            rows = [l.split() for l in subprocess.run(['ps', '-eo', 'pid=,uid=,stat='], capture_output=True, text=True).stdout.splitlines()]
            out = []
            for p, u, *st in rows:
                if u.isdigit() and int(u) >= sandbox.UID_BASE and int(u) % 2 == 1 and not (st and st[0].startswith('Z')) and os.path.exists(f'/proc/{p}/cmdline'):
                    out.append(p)
            return out
        DYING = ("import ctypes, os, sys, threading, time\nif sys.argv[1:] != ['again']:\n    ctypes.CDLL(None).prctl(1, 0, 0, 0, 0)\n"   # it clears its death signal, then runs itself again from a second thread, which starts without one
                 "    threading.Thread(target=os.execv, args=(sys.executable, [sys.executable, '-I', '-S', '/work/c.py', 'again'])).start(); time.sleep(5)\nelse:\n    time.sleep(60)")
        dying = subprocess.Popen([PY, '-B', '-c', "import sys; sys.path.insert(0, sys.argv[1]); import sandbox; sandbox.run({'c.py': sys.argv[2].encode()}, 'c.py', b'', timeout=30)", str(GATEWAY / 'verify'), DYING])
        for _ in range(100):                                            # until the check has done both: its process now runs the script again, as 'again'
            if any(b'again' in cmdline(p) for p in run_pids()):
                break
            time.sleep(0.05)
        e['tried_before_kill'] = any(b'again' in cmdline(p) for p in run_pids())
        e['running_before_kill'] = bool(run_procs())
        dying.kill(); dying.wait()
        for _ in range(20):                                             # two seconds: long before the launcher's own clock (30 + 5 s) would end the run
            e['orphans'] = run_procs()
            if not e['orphans']:
                break
            time.sleep(0.1)
        # what the kernel counts per user: a check takes all the inotify instances it may, and root, outside, can still make one
        held = {}
        th = threading.Thread(target=lambda: held.update(o=boxed("import ctypes, os, time\npids = []\nfor i in range(3):\n    pid = os.fork()\n    if pid == 0:\n"
                                                                  "        libc = ctypes.CDLL(None, use_errno=True); n = 0\n        while libc.inotify_init1(0) >= 0:\n            n += 1\n"
                                                                  "        print(n, ctypes.get_errno(), flush=True); time.sleep(4); os._exit(0)\n    pids.append(pid)\nfor p in pids:\n    os.waitpid(p, 0)", timeout=8)))
        th.start(); time.sleep(2.5)
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True); fd = libc.inotify_init1(0); e['root_inotify'] = [fd >= 0, ctypes.get_errno()]
        if fd >= 0:
            os.close(fd)
        th.join(); e['inotify'] = held.get('o')
        taken = [int(l.split()[0]) for l in (e['inotify'][2] if isinstance(e['inotify'], tuple) and len(e['inotify']) > 2 else '').splitlines() if l.split() and l.split()[0].isdigit()]
        e['inotify_taken'] = sum(taken)
        # a launcher that makes no namespaces: it refuses, and the check is not run; nor is it where the control groups cannot be made
        ran_marker = pathlib.Path(tempfile.gettempdir()) / f'{mark}-ran'
        o = step(sandbox.run, {'c.py': f"open({str(ran_marker)!r}, 'w').write('ran')".encode()}, 'c.py', b'{}', _no_unshare=True)
        no_groups = subprocess.run([PY, '-B', '-c', "import sys, json; sys.path.insert(0, sys.argv[1]); import sandbox; o = sandbox.run({'c.py': sys.argv[2].encode()}, 'c.py', b'{}'); "
                                    "print(json.dumps([o.state, o.detail]))", str(GATEWAY / 'verify'), f"open({str(ran_marker)!r}, 'w').write('ran')"],
                                   capture_output=True, text=True, timeout=60, env=dict(os.environ, VERIFY_SANDBOX_CGROUP_ROOT=str(here / 'no-cgroups')))
        small = here / 'file-max'; small.write_text('1644500\n'); was = sandbox.FILE_MAX_PATH; sandbox.FILE_MAX_PATH = str(small)
        try:                                                            # a machine whose file table one run could fill
            o3 = step(sandbox.run, {'c.py': f"open({str(ran_marker)!r}, 'w').write('ran')".encode()}, 'c.py', b'{}')
        finally:
            sandbox.FILE_MAX_PATH = was
        fail_closed = ([o.state, o.detail] if not isinstance(o, tuple) else o, ran_marker.exists(), step(json.loads, (no_groups.stdout.strip().splitlines() or ['null'])[-1]),
                       [o3.state, o3.detail] if not isinstance(o3, tuple) else o3)
        # a hostile check, baselined and run through the gate: it does its work, and what it found goes into the signed verdict
        hdir = here / 'hostile_case'; shutil.copytree(CASE, hdir)
        honest = (CASE / 'check.py').read_text()
        (hdir / 'check.py').write_text(probe.replace("import json, os, socket\n", "import json, os, socket, csv, pathlib, sys\n") +
                                       "design = json.load(sys.stdin)\n"
                                       "rows = {r['material']: r for r in csv.DictReader(open(pathlib.Path(__file__).parent / 'materials.csv'))}\n"
                                       "value = float(rows[design['material']]['max_service_c'])\n"
                                       "seen = [k for k, v in found['read'].items() if v in ('read', 'listed')] + [str(i) for i, v in enumerate(found['reach']) if v == 'connected']\n"
                                       "print(json.dumps({'achieved': {'service_temperature': value}, 'basis': f\"uid {found['uid']}; reached {seen or 'nothing'} of the service\"}))\n")
        env2 = step(s.baseline, hdir, draft(requirement=dict(req, id='REQ-SANDBOX-027')))
        h2 = env2.get('baseline_sha256') if isinstance(env2, dict) else None
        cfg2 = s.client_config(here / 'ws2', h2) if h2 else None
        bad2 = s.submit(cfg2, BAD) if cfg2 else ('no baseline', env2)
        rec2 = step(s.record, h2, [here / 'ws2' / '.verify' / 'submissions.jsonl']) if h2 else {}
        ok2, _, s2 = check_record.verify(rec2, s.keys) if isinstance(rec2, dict) and rec2 else (False, [], {})
        run2 = (s2.get('runs') or [{}])[0]
        controls2 = [(c.get('name'), c.get('verdict')) for c in (env2.get('controls_run') if isinstance(env2, dict) else []) or []]
        # the gate host started where the control groups cannot be made: the run is UNKNOWN, the check is not run, and the engineer is told
        s.stop_host(); s.start_host(extra_env={'VERIFY_SANDBOX_CGROUP_ROOT': str(here / 'no-cgroups')})
        notices_before = len(s.inbox(h)) if h else 0
        refused = submit({'material': 'PPS-GF40', 'wall_mm': 3.5, 'mode': 'normal'})
        notices_after = len(s.inbox(h)) if h else 0
        s.stop_host(); s.start_host()
        again = submit({'material': 'PPS-GF40', 'wall_mm': 2.5, 'mode': 'normal'})
        ok, why, summ = checked()
        runs = {(x['design'] or {}).get('wall_mm'): (x['outcome'], x['reason_code'], x['detail'][:160]) for x in summ.get('runs', [])}
        good = submit(GOOD); bad = submit(BAD)
        e.update(first=first, second=second, limits={k: v[:4] if isinstance(v, tuple) else v for k, v in limits.items()}, survivors=survivors, run_left=run_left, fail_closed=fail_closed,
                 controls2=controls2, bad2=(bad2[0], said(bad2[1])), run2=(run2.get('outcome'), run2.get('reason_code'), run2.get('basis')), ok2=ok2,
                 refused=(refused[0], said(refused[1])), notices=(notices_before, notices_after), runs=runs, again=(again[0], said(again[1])), good=good[0], bad=bad[0], ok=ok, why=why)
        f1, f2 = (first if isinstance(first, dict) else {}), (second if isinstance(second, dict) else {})
        checks = {'a check runs as nobody (user and group 65534, no other group, even where the service holds one), in /work, which holds only its own files, under a root that holds only /usr (and links into it), /work, /tmp and /dev':
                      (f1.get('uid'), f1.get('gid'), f1.get('groups'), f1.get('cwd'), f1.get('here')) == (65534, 65534, [], '/work', ['c.py', 'data.csv']) and e['grouped'] == 'RAN []'
                      and f1.get('root') == ['bin', 'dev', 'lib', 'lib64', 'sbin', 'tmp', 'usr', 'work'],
                  'none of the service\'s files is there to read: not the engineer\'s or the courier\'s key, the witness\'s TLS key, the ledger, the baselines, /etc/passwd, /proc or the code':
                      bool(f1.get('read')) and all(v == 'FileNotFoundError' for v in f1['read'].values()),
                  'it has no network: the witness, the gate host, the database and an address outside cannot be reached':
                      f1.get('reach') is not None and len(f1['reach']) == 4 and all(v != 'connected' for v in f1['reach']),
                  'it can write only in /work and /tmp, not in the root, /usr or /dev; and the next run starts in an empty /work, with nothing kept from the one before':
                      f1.get('write') == {'/x': 'OSError', '/usr/x': 'OSError', '/dev/x': 'OSError', '/work/kept-from-before': 'written', '/tmp/x': 'written'}
                      and f1.get('kept') is False and f2.get('kept') is False,
                  'a fork bomb stops at the process limit; asking for 2 GiB of memory fails; more than 1 MiB of output ends the run; a loop is stopped at the time allowed; a file of 100 MiB cannot be written':
                      limits['fork bomb'][0] == 'RAN' and limits['fork bomb'][2].split()[-1:] == ['BlockingIOError'] and int((limits['fork bomb'][2].split() or ['999'])[0]) < 64
                      and limits['memory'][:2] == ('RAN', 1) and 'MemoryError' in limits['memory'][3] and limits['output'][0] == 'OUTPUT_TOO_LONG' and limits['spin'][0] == 'TIMEOUT'
                      and limits['disk'][0] in ('RAN',) and 'wrote' not in limits['disk'][2],
                  'a process the check leaves behind ends with the run, and so does a check that leaves its process group and outlives the time allowed, with its children, at its time, not later at the launcher\'s; no process of any run\'s identities is left; the check sees no process of the machine, and cannot signal the namespace\'s first process, which is the sandbox\'s own':
                      limits['left behind'][:2] == ('RAN', 0) and limits['escape'][0] == 'TIMEOUT' and e['escape_seconds'] < 4 and survivors == [] and run_left == []
                      and limits['others'][2].strip() == "['PermissionError', 'ProcessLookupError', 'ProcessLookupError', 'ProcessLookupError']",
                  'what a run uses is limited for the run as a whole: of seven processes that each take 900 MiB, at most one lives, ten-MiB files stop before 7 of them, and a design larger than a pipe holds, of which the check reads a little and then no more, does not stop the clock: that run ends at its own time, not later at the launcher\'s':
                      limits['memory, many processes'][0] == 'RAN' and limits['memory, many processes'][2].split().count('alive') <= 1
                      and limits['disk, many files'][0] == 'RAN' and int((limits['disk, many files'][2].split() or ['99'])[0]) < 7 and limits['disk, many files'][2].split()[-1:] == ['OSError']
                      and limits['a design larger than the pipe'][0] == 'TIMEOUT' and e['piped_seconds'] < 5,
                  'runs keep nothing for one another: the kernel\'s keyrings cannot be used (refused, ENOSYS), so nothing is kept in them from one run to the next; the host name is the sandbox\'s; /usr/local is hidden; and the check has no site packages, not even by adding their folder, and is run without them (python -I -S)':
                      limits['keyring, first run'][2].strip() == 'refused 38' and limits['keyring, next run'][2].strip() == 'not found'
                      and limits['host'][2].strip() == 'sandbox [] ImportError 1 1' and (printed(limits['calls']) or {}).get('dist') == 'ImportError',
                  'the check can make no socket of any family: vsock (which no network namespace closes), packet, netlink, internet and Unix sockets, and socket pairs, are refused; nor can it set up native asynchronous I/O (ENOSYS); its capability bounding set is empty; it may queue 64 signals and no message-queue bytes; /work is in memory, at most 64 MiB':
                      isinstance(printed(limits['calls']), dict) and {k: printed(limits['calls']).get(k) for k in ('vsock', 'packet', 'netlink', 'unix', 'inet', 'pair')} == dict.fromkeys(('vsock', 'packet', 'netlink', 'unix', 'inet', 'pair'), 97)
                      and 0 < printed(limits['calls'])['work_bytes'] <= (64 << 20)
                      and printed(limits['calls']).get('aio') == [-1, 38]
                      and printed(limits['calls']).get('bounding') == [] and printed(limits['calls']).get('rlimits') == [64, 0],
                  'what the kernel counts for each user is counted against a user of the run\'s own, not root: a check takes inotify instances until refused, and gets exactly 128, the limit for one user, while root, outside, can still make one':
                      isinstance(e['inotify'], tuple) and e['inotify'][0] == 'RAN' and e['inotify_taken'] == 128 and e['root_inotify'][0] is True,
                  'two runs have different host identities, and a run whose service is killed ends with it, within two seconds, with every process it started, though the check had tried to clear its death signal, and had run itself again from a second thread, which starts without one':
                      len(e['host_ids']) == 2 and e['host_ids'][0] and e['host_ids'][1] and not set(e['host_ids'][0]) & set(e['host_ids'][1]) and e['running_before_kill'] and e['tried_before_kill'] and e['orphans'] == [],
                  'where the sandbox cannot be made, the check is not run and the outcome says why: a launcher outside new namespaces refuses, and so does a service that cannot make the run\'s control groups, or whose machine has a file table one run could fill':
                      isinstance(fail_closed[0], list) and fail_closed[0][0] == 'SANDBOX_UNAVAILABLE' and 'not the first process of a new process namespace' in fail_closed[0][1] and fail_closed[1] is False
                      and isinstance(fail_closed[2], list) and fail_closed[2][0] == 'SANDBOX_UNAVAILABLE' and 'control groups' in fail_closed[2][1]
                      and isinstance(fail_closed[3], list) and fail_closed[3][0] == 'SANDBOX_UNAVAILABLE' and 'file table' in fail_closed[3][1],
                  'a hostile check that probes the service while it works is baselined with its controls as declared, gives a failing design its FAIL, and its own words in the signed verdict say it reached nothing; the record verifies':
                      controls2 and all(v in ('PASS', 'FAIL') for _, v in controls2) and bad2[0] == 2 and run2.get('outcome') == 'FAIL'
                      and run2.get('basis') == "uid 65534; reached nothing of the service" and ok2,
                  'a gate host whose sandbox cannot be made answers UNKNOWN, says the check was not run, and sends the engineer the notice; started again as it should be, it runs checks again':
                      refused[0] == 3 and runs.get(3.5, ('',))[:2] == ('UNKNOWN', 'CHECK_ERROR') and 'the check was not run' in runs.get(3.5, ('', '', ''))[2]
                      and notices_after == notices_before + 1 and again[0] == 0 and runs.get(2.5, ('',))[0] == 'PASS',
                  'a check that keeps to the standard library and its own files runs as before: a design that meets the declared check passes and one that does not fails, and the record verifies':
                      good[0] == 0 and bad[0] == 2 and ok}
    finally:
        s.stop()
    return {k: bool(v) for k, v in checks.items()}, e


# ====================================================================== Amendment 13: an answer does not slow with the runs already made
def _attempts_one_by_one(store, root: str, submissions: list, upto: int | None = None) -> list:
    """The attempts as verify_record.attempts_of read them before Amendment 13: each attempt by itself, through the store's own
    evidence_for, get_receipt and get_result.  Kept here as what the new reading must equal."""
    import verify_record as VR
    audit, observation = store.audit_snapshot(root)
    upto = len(audit) if upto is None else upto
    by_key = {VR.request_key(a): a for a in submissions}
    attempts = []
    for aid, req, phase, nonce, _receipt, _crossed in observation['attempts']:
        evidence = [{'seq': x['seq'], 'evidence': x['evidence']} for x in store.evidence_for(root, aid) if x['seq'] <= upto]
        receipts = {}
        for op in VR.RECEIPT_OPS:
            got = store.get_receipt(root, aid, op)
            if got is not None and got.get('seq', 0) <= upto:
                receipts[op] = got
        stored = store.get_result(root, aid)
        result = stored.get('value') if isinstance(stored, dict) and stored.get('outcome', 'value') == 'value' and phase == 'EFFECT' else None
        arguments = by_key.get(req)
        if arguments is None and isinstance(result, dict) and 'design' in result:
            guess = VR.arguments_for(result.get('baseline_sha256'), result['design'])
            arguments = guess if VR.request_key(guess) == req else None
        attempts.append({'aid': aid, 'request_key': req, 'arguments': arguments, 'phase': phase, 'nonce': nonce,
                         'outcome': VR.outcome_of(phase, evidence, result), 'receipts': receipts, 'evidence': evidence, 'result': result})
    return attempts


def r28():
    """The reading of a baseline's runs, which every answer makes, opens two connections to the database whatever the number of
    runs already made, and gives exactly what reading each run by itself gives.  Restated by Amendment 14, after a review of its
    first declared form: connections are counted where the database driver opens them; a reading is cut at the very decision of a
    report and at the one before; and the store is then changed by hand, to show what the reading must not do: take another
    budget's reports, receipts or results for a run of the same name, take a result for a run that had no effect or a result
    that is no value, or fail on a run that has no report, no receipt and no result.  (Amendments 13 and 14.)"""
    r = Run('R28', crash_at='verify_running'); e = {}
    try:
        import psycopg
        import verify_record as VR
        store = Store(deploy.LOCAL_DSN)
        journal = lambda: [json.loads(l) for l in (r.ws / '.verify' / 'submissions.jsonl').read_text().splitlines()]
        root = B.root_for(r.env['card'])

        def counted(f, *a, **kw):
            """f's answer, and the connections to the database opened in this process while it ran, wherever they were opened."""
            n = [0]; real_method, real_function = psycopg.Connection.__dict__['connect'], psycopg.connect

            def connect(cls, *ca, **ck):
                n[0] += 1
                return real_method.__func__(cls, *ca, **ck)
            psycopg.Connection.connect = classmethod(connect); psycopg.connect = psycopg.Connection.connect
            try:
                return f(*a, **kw), n[0]
            finally:
                psycopg.Connection.connect = real_method; psycopg.connect = real_function

        def measure():
            (new, snap), opened = counted(VR.attempts_of, store, root, journal())
            old, opened_old = counted(_attempts_one_by_one, store, root, journal())
            half = len(snap['audit']) // 2
            new_half, _ = VR.attempts_of(store, root, journal(), upto=half)
            old_half = _attempts_one_by_one(store, root, journal(), upto=half)
            rows = [[x['seq'] for x in a['evidence']] for a in new]
            return {'runs': len(new), 'opened': opened, 'opened_one_by_one': opened_old, 'same': canonical(new) == canonical(old),
                    'same_cut': canonical(new_half) == canonical(old_half), 'cut_at': half, 'cut_differs': canonical(new_half) != canonical(new),
                    'outcomes': sorted(a['outcome'] for a in new), 'most_reports': max(map(len, rows), default=0), 'in_order': all(x == sorted(x) for x in rows),
                    'without_result': sum(a['result'] is None for a in new), 'with_receipts': sum(len(a['receipts']) for a in new), 'attempts': new}

        def at(upto, aid):
            """What each reading shows of one run's reports, cut at a decision: (the new reading's, the old one's)."""
            pick = lambda attempts: [x['seq'] for a in attempts if a['aid'] == aid for x in a['evidence']]
            try:
                return pick(VR.attempts_of(store, root, journal(), upto=upto)[0]), pick(_attempts_one_by_one(store, root, journal(), upto=upto))
            except Exception as exc:
                return (f'{type(exc).__name__}: {exc}'[:120], None)

        unread = lambda exc: {'runs': 0, 'opened': None, 'opened_one_by_one': 0, 'same': False, 'same_cut': False, 'cut_at': 0, 'cut_differs': False, 'outcomes': [], 'most_reports': 0,
                              'in_order': False, 'without_result': 0, 'with_receipts': 0, 'attempts': [], 'raised': f'{type(exc).__name__}: {exc}'[:160]}

        def measured():                                                  # a reading that raises is a reading that failed: the checks say so, and the test goes on
            try:
                return measure()
            except Exception as exc:
                return unread(exc)

        during = r.submit(GOOD); time.sleep(0.3); r.s.stop_host(); r.s.start_host()     # the host dies during the first run; asked again, it is interrupted
        again = r.submit(GOOD)
        first = [r.submit(d)[0] for d in (BAD, {'material': 'PPS-GF40', 'wall_mm': 2.5, 'mode': 'normal'})]
        few = measured()
        more = [r.submit({'material': 'PA66-GF30', 'wall_mm': round(3.1 + i / 10, 1), 'mode': 'normal'})[0] for i in range(11)]
        outside = r.submit({'material': 'PA66-GF30', 'wall_mm': 99, 'mode': 'normal'})[0]          # outside the design space: a FAIL with no check run
        many = measured()
        failed = [a for a in many['attempts'] if a['outcome'] == 'FAIL' and a['evidence'] and len(a['receipts']) == 3]
        none = {'aid': 'none', 'evidence': [{'seq': 2, 'evidence': {}}], 'receipts': {}, 'result': None}           # if no run reads as a FAIL, the checks say so
        victim, emptied, tampered = (failed + [none, none, none])[:3]
        halted = next((a for a in many['attempts'] if a['outcome'] == 'INTERRUPTED'), none)
        own = victim['evidence'][0]['seq']
        edge = {'at_its_decision': at(own, victim['aid']), 'at_the_one_before': at(own - 1, victim['aid'])}
        ok, why, s = r.checked({'material': 'PPS-GF40', 'wall_mm': 2.5, 'mode': 'normal'})          # the record, before anything is put into the store by hand
        # another budget in the same store, and changes made by hand with the owner's role (no service's role may make them)
        card2 = draft(requirement=dict(r.env['card']['requirement'], id='REQ-OTHER-028'))
        env2 = r.s.baseline(CASE, card2); root2 = B.root_for(env2['card'])
        other = {'planted': 'another budget'}
        try:
            w = Store(os.environ.get('PLEA_ADMIN_DSN', 'postgresql://plea:plea@127.0.0.1:5432/plea'))
            with w.connect() as conn:
                put = lambda sql, *args: conn.execute(sql, args)
                taken = {row[0] for row in conn.execute('SELECT seq FROM evidence WHERE root_id = %s', (root,)).fetchall()}
                free = max((q for q in range(1, own) if q not in taken), default=0)
                # the other budget holds, for runs of this budget's names: a report each (at decisions inside this budget's log), every receipt, and a result that says PASS
                for n, aid in enumerate((victim['aid'], emptied['aid'], halted['aid']), 1):
                    put('INSERT INTO evidence (root_id, aid, seq, evidence, derived) VALUES (%s, %s, %s, %s, %s)', root2, aid, n, json.dumps(dict(other, claim='PLANTED')), 'PLANTED')
                    for op in VR.RECEIPT_OPS:
                        put('INSERT INTO receipts (root_id, aid, op, seq, receipt) VALUES (%s, %s, %s, %s, %s)', root2, aid, op, 1, json.dumps(dict(other, seq=1)))
                    put('INSERT INTO results (root_id, aid, result) VALUES (%s, %s, %s)', root2, aid, json.dumps({'outcome': 'value', 'value': dict(other, verdict='PASS')}))
                # in this budget: a second, earlier report for one run; one run left with no report, no receipt and no result;
                put('INSERT INTO evidence (root_id, aid, seq, evidence, derived) VALUES (%s, %s, %s, %s, %s)', root, victim['aid'], free, json.dumps({'claim': 'EARLIER', 'of': 'this budget'}), 'PLANTED')
                put('DELETE FROM evidence WHERE root_id = %s AND aid = %s', root, emptied['aid'])
                put('DELETE FROM receipts WHERE root_id = %s AND aid = %s', root, emptied['aid'])
                put('DELETE FROM results WHERE root_id = %s AND aid = %s', root, emptied['aid'])          # so that another budget's result for its name would show, whichever row is read last
                # a result that says PASS for the run that had no effect (it was interrupted); and one run's result made into one that is no value
                put('INSERT INTO results (root_id, aid, result) VALUES (%s, %s, %s) ON CONFLICT (root_id, aid) DO UPDATE SET result = EXCLUDED.result', root, halted['aid'],
                    json.dumps({'outcome': 'value', 'value': {'verdict': 'PASS', 'put': 'by hand'}}))
                put('UPDATE results SET result = %s WHERE root_id = %s AND aid = %s', json.dumps({'outcome': 'unknown', 'value': tampered['result']}), root, tampered['aid'])
                conn.commit()
            planted = ['done', [free, own]]
        except Exception as exc:
            planted = [f'{type(exc).__name__}: {exc}'[:200]]
        beside = measured()
        find = lambda aid: next((a for a in beside['attempts'] if a['aid'] == aid), {'evidence': None, 'receipts': None, 'result': 'missing', 'outcome': 'missing'})
        mine, bare, halted2, tampered2 = find(victim['aid']), find(emptied['aid']), find(halted['aid']), find(tampered['aid'])
        leaked = 'another budget' in canonical(beside['attempts'])
        for m in (few, many, beside):
            m.pop('attempts')
        e.update(during=during[0], again=(again[0], head(again[1])), first=first, more=more, outside=outside, few=few, many=many, beside=beside, planted=planted, other_root=root2 != root,
                 edge=edge, own=own, leaked=leaked, mine_reports=[(x['seq'], x['evidence'].get('claim')) for x in (mine['evidence'] or [])], mine_outcome=mine['outcome'],
                 mine_receipts_same=canonical(mine['receipts']) == canonical(victim['receipts']), bare=(bare['evidence'], bare['receipts'], bare['result'], bare['outcome']),
                 halted=(halted2['outcome'], halted2['result']), tampered=(tampered2['outcome'], tampered2['result']), three_runs=len({victim['aid'], emptied['aid'], tampered['aid'], halted['aid']}),
                 record_verifies=ok, why=why, counts=(s.get('official_runs'), s.get('met'), s.get('not_met')))
        checks = {'the runs are there to read: 3, then 15, one of them interrupted, with no result; and the record verifies':
                      again[0] == 3 and head(again[1]) == 'UNKNOWN: THE RUN WAS INTERRUPTED' and first == [2, 0] and more == [2] * 11 and outside == 2 and few['runs'] == 3
                      and many['runs'] == 15 and 'INTERRUPTED' in many['outcomes'] and many['without_result'] >= 1 and ok and e['counts'] == (15, 1, 13),
                  'the reading gives exactly what reading each run by itself gives, for 3 runs and for 15':
                      few['same'] and many['same'],
                  'and so does a reading cut at an earlier decision, which is not the whole reading; cut at the very decision of a run\'s report it shows the report, and cut at the decision before it does not':
                      few['same_cut'] and many['same_cut'] and many['cut_differs'] and 0 < many['cut_at']
                      and edge['at_its_decision'] == ([own], [own]) and edge['at_the_one_before'] == ([], []),
                  'it opens two connections to the database for 15 runs as for 3, counted where the driver opens them, where reading each run by itself opens more for every run':
                      few['opened'] == many['opened'] == beside['opened'] == 2 and many['opened_one_by_one'] > few['opened_one_by_one'] > 2,
                  'with a second, earlier report put into the store for one run, and a report, every receipt and a PASS put under another budget for runs of the same names: the run shows its own two reports, the earlier first, its own receipts and its own FAIL, and nothing of the other budget\'s is anywhere in the reading, as reading each run by itself gives':
                      planted[0] == 'done' and e['other_root'] and e['three_runs'] == 4 and beside['same'] and beside['same_cut'] and beside['runs'] == 15 and not leaked
                      and beside['most_reports'] == 2 and beside['in_order'] and [c for _, c in e['mine_reports']] == ['EARLIER', victim['evidence'][0]['evidence'].get('claim')]
                      and e['mine_reports'][0][0] < e['mine_reports'][1][0] and e['mine_receipts_same'] and e['mine_outcome'] == 'FAIL',
                  'a run left with no report, no receipt and no result is read as having none, and is no longer a FAIL or a PASS; a PASS put by hand for the run that had no effect is not taken, and it stays interrupted; and a result made into one that is no value is not taken':
                      planted[0] == 'done' and beside['same'] and e['bare'] == ([], {}, None, 'INVALID') and e['halted'] == ('INTERRUPTED', None) and e['tampered'][1] is None and e['tampered'][0] != 'FAIL'}
    finally:
        r.stop()
    return {k: bool(v) for k, v in checks.items()}, e

# ====================================================================== Amendment 15: what the machine must give, said before a check is run
def r29():
    """What the sandbox needs of the machine is looked at before every run, and said: root, x86-64, cgroup v1 control groups, user
    namespaces, and a file table at least twice what one service's runs can keep open, worked out from the machine's own limits.
    Where one is not met the check is not run, and the words say which and why; an operator can ask for the same answer.  The
    floor rests on a measurement, made here again: one run keeping open every file it can.  (Amendment 15.)"""
    r = Run('R29'); e = {}
    try:
        import sandbox
        here = OUT / 'R29'
        maps = int(open('/proc/sys/vm/max_map_count').read()); table = int(open('/proc/sys/fs/file-max').read())
        L = sandbox.LIMITS; page = os.sysconf('SC_PAGE_SIZE')

        def one_run(processes=L['processes'], mappings=maps):
            # worked out here by itself.  For each process: its descriptors, its mappings (the machine's limit and one, or a page each
            # of the memory it may address, whichever is fewer) and its program; for the run, 4096 shared-memory segments
            return processes * (min(mappings + 1, L['memory_bytes'] // page) + L['open_files'] + 1) + 4096
        per_run = one_run(); floor = 2 * 4 * per_run                      # twice what four runs can keep open
        script = {'c.py': b"print('the check ran')"}                     # what it prints is the sign that it ran: it can write nothing outside its sandbox

        def with_paths(limits=None, **paths):
            """One run with the sandbox reading the machine from other files, and what it says of the machine then."""
            was = {k: getattr(sandbox, k) for k in paths}
            for k, v in paths.items():
                setattr(sandbox, k, str(v))
            try:
                o = sandbox.run(script, 'c.py', b'', limits=limits)
                return [o.state, o.detail, o.stdout.decode(errors='replace').strip()], {n: (m, w) for n, m, w in sandbox.prerequisites(limits)}
            except Exception as exc:
                return [f'RAISED {type(exc).__name__}: {exc}'[:160], '', ''], {}
            finally:
                for k, v in was.items():
                    setattr(sandbox, k, v)

        def file(name, text):
            (here / name).write_text(text); return here / name

        as_is = sandbox.prerequisites()
        cli = subprocess.run([PY, '-B', str(GATEWAY / 'verify' / 'sandbox.py'), '--prerequisites'], capture_output=True, text=True, timeout=60)
        below, below_said = with_paths(FILE_MAX_PATH=file('below', f'{floor - 1}\n'))
        at, at_said = with_paths(FILE_MAX_PATH=file('at', f'{floor}\n'))
        half, half_said = with_paths(MAP_COUNT_PATH=file('half-maps', f'{maps // 2}\n'), FILE_MAX_PATH=file('half-floor', f'{2 * 4 * one_run(mappings=maps // 2)}\n'))
        many_floor = 2 * 4 * one_run(mappings=1048576)                    # as Ubuntu 24.04 sets the limit: more mappings than a process has pages for
        many, many_said = with_paths(MAP_COUNT_PATH=file('many-maps', '1048576\n'))
        none_maps, none_maps_said = with_paths(MAP_COUNT_PATH=file('no-maps', '-100\n'))
        raised, raised_said = with_paths(REAL_FILE_MAX=file('real-below', f'{floor - 1}\n'), FILE_MAX_PATH=file('named-above', f'{10 * floor}\n'))
        unread, unread_said = with_paths(MAP_COUNT_PATH=here / 'not-there')
        no_table, no_table_said = with_paths(FILE_MAX_PATH=here / 'not-there')
        words_table, words_table_said = with_paths(FILE_MAX_PATH=file('words', 'unlimited\n'))
        twice = {'processes': 2 * sandbox.LIMITS['processes']}             # a run allowed twice the processes can keep twice the files open
        more, more_said = with_paths(limits=twice, FILE_MAX_PATH=file('at-again', f'{floor}\n'))
        fewer = {'processes': L['processes'] // 2}; fewer_floor = 2 * 4 * one_run(processes=fewer['processes'])
        less_below, less_below_said = with_paths(limits=fewer, FILE_MAX_PATH=file('fewer-below', f'{fewer_floor - 1}\n'))
        less_at, less_at_said = with_paths(limits=fewer, FILE_MAX_PATH=file('fewer-at', f'{fewer_floor}\n'))
        v2, v2_said = with_paths(SELF_CGROUP=file('cgroup-v2', '0::/user.slice/user-0.slice/session-1.scope\n'))
        no_freezer, no_freezer_said = with_paths(SELF_CGROUP=file('cgroup-no-freezer', ''.join(l + '\n' for l in open('/proc/self/cgroup').read().splitlines() if 'freezer' not in l)))
        no_spaces, no_spaces_said = with_paths(USERNS_PATH=file('no-userns', '0\n'))
        elsewhere, elsewhere_said = with_paths(SELF_CGROUP=file('cgroup-elsewhere', ''.join((l if ':freezer:' not in l else l.split(':', 2)[0] + ':freezer:/not-there-r29') + '\n' for l in open('/proc/self/cgroup').read().splitlines())))
        unread_spaces, unread_spaces_said = with_paths(USERNS_PATH=here / 'not-there')
        (here / 'cgroup-rubbish').write_bytes(b'12:freezer:/\xff\xfe\n'); rubbish, rubbish_said = with_paths(SELF_CGROUP=here / 'cgroup-rubbish')
        nothing_ran = all(x[2] == '' for x in (below, unread, no_table, words_table, more, less_below, many, none_maps, raised, v2, no_freezer, no_spaces, elsewhere, unread_spaces, rubbish))
        # the bound counts one IPC namespace for a run: a check must not be able to make namespaces of its own
        o = sandbox.run({'c.py': b"import ctypes\nlibc = ctypes.CDLL(None, use_errno=True)\nprint([(libc.unshare(f), ctypes.get_errno()) for f in (0x10000000, 0x08000000, 0x18000000)])"}, 'c.py', b'')
        own_spaces = [o.state, o.stdout.decode(errors='replace').strip()]
        # the floor counts four runs at once on the machine: two made by this process and two by another, and a fifth is not made
        slow = {'c.py': b"import time\ntime.sleep(5)\nprint('the check ran')"}; four = [None] * 2
        places_were = sandbox.SLOTS_DIR; sandbox.SLOTS_DIR = str(here / 'places')   # places of the test's own, so that nothing else on the machine takes or waits for them

        def one(i):
            try:
                o = sandbox.run(slow, 'c.py', b'', timeout=20); four[i] = [o.state, o.stdout.decode(errors='replace').strip()]
            except Exception as exc:
                four[i] = [f'RAISED {type(exc).__name__}: {exc}'[:160], '']
        other = ("import sys, json, threading\nsys.path.insert(0, sys.argv[1])\nimport sandbox\nsandbox.SLOTS_DIR = sys.argv[2]\nout = [None, None]\n"
                 "def one(i):\n    o = sandbox.run({'c.py': b\"import time\\ntime.sleep(5)\\nprint('the check ran')\"}, 'c.py', b'', timeout=20); out[i] = [o.state, o.stdout.decode().strip()]\n"
                 "ths = [threading.Thread(target=one, args=(i,)) for i in range(2)]\n[t.start() for t in ths]; [t.join() for t in ths]\nprint(json.dumps(out))")
        t0 = time.time(); ths = [threading.Thread(target=one, args=(i,)) for i in range(2)]
        elsewhere_proc = subprocess.Popen([PY, '-B', '-c', other, str(GATEWAY / 'verify'), sandbox.SLOTS_DIR], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for th in ths:
            th.start()
        time.sleep(2.0)
        try:
            o = sandbox.run(script, 'c.py', b'', timeout=1); fifth = [o.state, o.detail, o.stdout.decode(errors='replace').strip()]
        except Exception as exc:
            fifth = [f'RAISED {type(exc).__name__}: {exc}'[:160], '', '']
        for th in ths:
            th.join()
        try:
            four = four + json.loads((elsewhere_proc.communicate(timeout=60)[0].strip().splitlines() or ['[null, null]'])[-1])
        except Exception as exc:
            four = four + [f'RAISED {type(exc).__name__}: {exc}'[:160]]
        finally:
            if elsewhere_proc.poll() is None:
                elsewhere_proc.kill()
        four_took = round(time.time() - t0, 2)
        o = sandbox.run(script, 'c.py', b'', timeout=20); after_four = [o.state, o.detail, o.stdout.decode(errors='replace').strip()]
        sandbox.SLOTS_DIR = places_were
        (here / 'open-places').mkdir(); os.chmod(here / 'open-places', 0o777)   # places anyone could take are no count
        open_places, open_places_said = with_paths(SLOTS_DIR=here / 'open-places')
        (here / 'a-file').write_text(''); no_places, no_places_said = with_paths(SLOTS_DIR=here / 'a-file' / 'places')
        small = file('small', '1644500\n')                                # the table this machine starts with
        cli_small = subprocess.run([PY, '-B', str(GATEWAY / 'verify' / 'sandbox.py'), '--prerequisites'], capture_output=True, text=True, timeout=60, env=dict(os.environ, VERIFY_SANDBOX_FILE_MAX=str(small)))
        # a service on such a machine: the run is UNKNOWN, the check is not run, and the engineer is told
        r.s.stop_host(); r.s.start_host(extra_env={'VERIFY_SANDBOX_FILE_MAX': str(small)})
        before = len(r.s.inbox(r.h)); refused = r.submit(BAD); after = len(r.s.inbox(r.h))
        r.s.stop_host(); r.s.start_host()
        again = r.submit({'material': 'PA66-GF30', 'wall_mm': 4, 'mode': 'normal'})               # another design: the first is on the record as UNKNOWN, and is not run again
        ok, why, s = r.checked()
        runs = [(x['outcome'], x['reason_code'], x['detail'][:200]) for x in s.get('runs', [])]
        # the measurement the floor rests on: one run keeping open every file it can, watched from outside
        attack = (b"import ctypes, os, sys, time\nlibc = ctypes.CDLL(None, use_errno=True)\nlibc.mmap.restype = ctypes.c_void_p\n"
                  b"libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_long]\nkids = []\n"
                  b"for i in range(62):\n    try:\n        pid = os.fork()\n    except OSError:\n        break\n    if pid == 0:\n        n = 0\n        try:\n            while True:\n"
                  b"                fd = os.open(os.__file__, os.O_RDONLY); p = libc.mmap(None, 4096, 1, 2, fd, 0); os.close(fd)\n"
                  b"                if p in (None, ctypes.c_void_p(-1).value):\n                    break\n                n += 1\n        except BaseException:\n            pass\n"
                  b"        sys.stdout.write(str(n) + chr(10)); sys.stdout.flush(); time.sleep(8); os._exit(0)\n    kids.append(pid)\n"
                  b"for k in kids:\n    try:\n        os.waitpid(k, 0)\n    except OSError:\n        pass\n")
        open_now = lambda: int(open('/proc/sys/fs/file-nr').read().split()[0])
        base, peak, stop = open_now(), [0], [False]

        def watch():
            while not stop[0]:
                peak[0] = max(peak[0], open_now()); time.sleep(0.05)
        th = threading.Thread(target=watch); th.start()
        try:
            o = sandbox.run({'c.py': attack}, 'c.py', b'', timeout=25)
            held_run = [o.state, o.returncode, o.detail[:120]]
        except Exception as exc:
            held_run = [f'RAISED {type(exc).__name__}: {exc}'[:160], None, '']
        stop[0] = True; th.join(); time.sleep(1.0); left = open_now()
        e.update(maps=maps, table=table, per_run=per_run, floor=floor, floor_said=sandbox.file_table_floor(), as_is=[(n, m) for n, m, _ in as_is], cli=(cli.returncode, cli.stdout.strip().splitlines()[-1:]),
                 below=below, at=at, half=half, more=more, less_below=less_below, less_at=less_at, many=many, many_floor=many_floor, open_places=open_places, no_places=no_places, none_maps=none_maps, raised=raised, unread_spaces=unread_spaces, rubbish=rubbish, own_spaces=own_spaces, unread=unread, no_table=no_table, words_table=words_table, elsewhere=elsewhere, four=four, fifth=fifth, four_took=four_took, after_four=after_four, runs_at_once=sandbox.RUNS_AT_ONCE, v2=v2, no_freezer=no_freezer, no_spaces=no_spaces, nothing_ran=nothing_ran,
                 cli_small=(cli_small.returncode, [l for l in cli_small.stdout.splitlines() if l.startswith('NOT MET')]), refused=(refused[0], head(refused[1])), notices=(before, after),
                 again=again[0], runs=runs, record_verifies=ok, why=why, held_run=held_run, files_before=base, files_peak=peak[0], held=peak[0] - base, files_after=left)
        unmet = lambda said: sorted(n for n, (m, _) in said.items() if not m)
        checks = {'as this machine is set up for the runs, every one of the six is met, and the command an operator gives says so, says that it made no run, and ends with status 0':
                      [n for n, _ in e['as_is']] == ['root', 'x86-64', 'control groups', 'user namespaces', 'places for runs', 'file table'] and all(m for _, m in e['as_is'])
                      and cli.returncode == 0 and 'Each of these is met' in cli.stdout and 'No run was made' in cli.stdout and cli.stdout.count('met    ') == 6 and 'NOT MET' not in cli.stdout,
                  'the file table must hold twice what four runs can keep open, worked out from the machine\'s own limit on mappings: one below that the check is not run, and the words give both numbers; at it, the check is run; with half the mappings a smaller table is enough; a run allowed twice the processes is not made on this table, and one allowed half is held to its own, smaller floor':
                      e['floor_said'] == floor and below[0] == 'SANDBOX_UNAVAILABLE' and str(floor - 1) in below[1] and str(floor) in below[1] and 'file table' in below[1] and below[2] == ''
                      and unmet(below_said) == ['file table'] and at == ['RAN', '', 'the check ran'] and unmet(at_said) == [] and half == ['RAN', '', 'the check ran'] and unmet(half_said) == []
                      and more[0] == 'SANDBOX_UNAVAILABLE' and 'file table' in more[1] and unmet(more_said) == ['file table']
                      and less_below[0] == 'SANDBOX_UNAVAILABLE' and str(fewer_floor) in less_below[1] and less_at == ['RAN', '', 'the check ran'] and unmet(less_at_said) == [],
                  'where a process may have more mappings than it has pages of memory to put them in (1,048,576, as Ubuntu 24.04 sets it), the floor counts the pages, and says the number; a file named in place of the kernel\'s can make the table smaller and cannot make it larger':
                      many[0] == 'SANDBOX_UNAVAILABLE' and str(many_floor) in many[1] and many_floor == 2 * 4 * (L['processes'] * (L['memory_bytes'] // page + L['open_files'] + 1) + 4096) and unmet(many_said) == ['file table']
                      and raised[0] == 'SANDBOX_UNAVAILABLE' and str(floor - 1) in raised[1] and str(10 * floor) not in raised[1].replace(str(here), '') and unmet(raised_said) == ['file table'],
                  'where the machine\'s limit on mappings, or its file table, cannot be read as a number above nothing, it cannot be shown that the table is large enough, and the check is not run':
                      all(x[0] == 'SANDBOX_UNAVAILABLE' and 'cannot be read' in x[1] and unmet(said) == ['file table'] for x, said in ((unread, unread_said), (no_table, no_table_said), (words_table, words_table_said), (none_maps, none_maps_said))),
                  'a machine that gives cgroup v2 only is refused in those words; one without a freezer control group is told which is missing, as is one whose freezer group is not where the sandbox makes its own; one that allows no user namespaces is told so, and so is one where that cannot be read; one whose control groups cannot be read at all is refused and nothing raises; and on none of them is the check run':
                      v2[0] == 'SANDBOX_UNAVAILABLE' and 'cgroup v2 only' in v2[1] and unmet(v2_said) == ['control groups']
                      and no_freezer[0] == 'SANDBOX_UNAVAILABLE' and 'freezer' in no_freezer[1] and 'cgroup v2 only' not in no_freezer[1] and unmet(no_freezer_said) == ['control groups']
                      and elsewhere[0] == 'SANDBOX_UNAVAILABLE' and 'freezer' in elsewhere[1] and 'is not under' in elsewhere[1] and unmet(elsewhere_said) == ['control groups']
                      and no_spaces[0] == 'SANDBOX_UNAVAILABLE' and 'user namespaces' in no_spaces[1] and unmet(no_spaces_said) == ['user namespaces']
                      and unread_spaces[0] == 'SANDBOX_UNAVAILABLE' and 'cannot be read' in unread_spaces[1] and unmet(unread_spaces_said) == ['user namespaces']
                      and rubbish[0] == 'SANDBOX_UNAVAILABLE' and len(unmet(rubbish_said)) == 1 and nothing_ran,
                  'with the file table this machine starts with (1,644,500), the operator\'s command says the file table is NOT MET and ends with status 1; a service there answers UNKNOWN, says the check was not run and why, and sends the engineer the notice; started again on the machine as set up, it runs checks':
                      cli_small.returncode == 1 and len(e['cli_small'][1]) == 1 and 'file table' in e['cli_small'][1][0] and '1644500' in e['cli_small'][1][0] and 'cannot run checks' in cli_small.stdout
                      and refused[0] == 3 and head(refused[1]).startswith('UNKNOWN') and any(x[0] == 'UNKNOWN' and 'the check was not run' in x[2] and 'file table' in x[2] for x in runs)
                      and after == before + 1 and again[0] == 2 and ok,
                  'the floor counts four runs at once on the machine, and no more are made, whichever process asks: two runs of five seconds by this process and two by another are made together, a fifth asked for meanwhile is not made and says why, and one asked for after them is made; where the places are a folder others can write to, or cannot be made, no run is made':
                      e['runs_at_once'] == 4 and len(four) == 4 and all(x == ['RAN', 'the check ran'] for x in four) and four_took < 15 and fifth == ['SANDBOX_UNAVAILABLE', 'too many checks are running at once on this machine', '']
                      and after_four == ['RAN', '', 'the check ran']
                      and all(x[0] == 'SANDBOX_UNAVAILABLE' and 'cannot be counted' in x[1] and x[2] == '' and unmet(said) == ['places for runs'] for x, said in ((open_places, open_places_said), (no_places, no_places_said))),
                  'a check that asks, by unshare, for a user namespace of its own, an IPC namespace, or both, is refused each (EPERM): the count of what one run can keep open has one IPC namespace in it':
                      own_spaces == ['RAN', '[(-1, 1), (-1, 1), (-1, 1)]'],
                  'a measurement, not a proof of the floor: one run that keeps open every file it can keeps more than a million, which is more than half the table this machine starts with, and fewer than the count worked out for one run; and after it has ended the machine has within 2,000 of the files open that it had before':
                      1_000_000 < e['held'] < per_run and e['held'] > 1644500 // 2 and held_run[0] in ('RAN', 'TIMEOUT') and e['files_after'] < base + 2000}
    finally:
        r.stop()
    return {k: bool(v) for k, v in checks.items()}, e


def r30():
    """The courier reads every run whatever happens when another is read; a run it cannot read stays unresolved, visible and
    noticed as unreadable, and the witness down is told apart from one run unreadable.  The witness refuses at its door a
    run's name its reading refuses.  In the words of a notice, everything the service chose is shown as data, and the
    checker makes the words again.  Coverage of a budget is confirmed only by the mailbox's receipt for the courier's
    statement that it watches it.  A blocked courier, a notice made and a notice accepted are told apart, and no word says a
    person read anything.  A signed PASS whose own numbers miss its own limit gets a notice, and that check can only add one.
    (Amendment 16.)"""
    import hashlib
    import notify_standin as S
    C = check_record; e = {}; t0 = 1_000_000.0
    def step(f, *a, **kw):                                                                     # a defect that makes a step raise gives an answer, not an error of the test
        try:
            return f(*a, **kw)
        except Exception as exc:
            return ('RAISED', f'{type(exc).__name__}: {exc}'[:300])
    def holds(f):                                                                              # a check whose expression raises is false
        try:
            return bool(f())
        except Exception:
            return False
    def in_thread(f, *a, seconds=20.0):                                                        # a direct call that might hang: in a thread of its own, joined; "still alive" fails
        box_ = {}
        th = threading.Thread(target=lambda: box_.update(got=step(f, *a)), daemon=True); th.start(); th.join(seconds)
        return box_.get('got') if not th.is_alive() else ('RAISED', 'still alive')
    short = lambda x: (x[:60] + f'...({len(x)})') if isinstance(x, str) and len(x) > 60 else x
    def last_line(name, seq):                                                                  # the courier's fixed last line, written out here
        return (f"This notice was made by the courier {name} from what the witness gave it, read to decision {seq}.  "
                "Words in quotation marks are shown as data: they are the service's, or what the courier was told, and not the courier's own words.  "
                "The verification service did not write this notice.  It does not say the check is correct.  "
                "A receipt for it says that the mailbox holds it, not that anyone has read it.")
    def as_data(value, limit):                                                                 # the rule of shown(), written out again here, independently
        if not isinstance(value, str):
            value = json.dumps(value, sort_keys=True, separators=(',', ':'))
        esc = ''.join('\\"' if ch == '"' else '\\\\' if ch == '\\' else ch if 32 <= ord(ch) <= 126 else (f'\\u{ord(ch):04x}' if ord(ch) < 0x10000 else f'\\U{ord(ch):08x}') for ch in value[:limit])
        return f'"{esc}"' + (f' (cut: {len(value)} characters in all, SHA-256 {hashlib.sha256(value.encode("utf-8", "surrogatepass")).hexdigest()})' if len(value) > limit else '')
    QUOTED = re.compile(r'"(?:[^"\\]|\\.)*"(?: \(cut: [0-9]+ characters in all, SHA-256 [0-9a-f]{64}\))?')
    def four_lines(text):
        return isinstance(text, str) and text.count('\n') == 3 and len(text.split('\n')) == 4 and all(32 <= ord(ch) <= 126 for ch in text.replace('\n', '')) and len(text.splitlines()) == 4
    made = lambda s: sorted((m.get('aid'), m.get('outcome')) for m in s.get('made', [])) if isinstance(s, dict) else s
    unread = lambda s: sorted(u.get('aid') for u in s.get('unread', [])) if isinstance(s, dict) else s

    # ---------------------------------------------------------------- T1: no run hides another (stand-in witness, real courier and mailbox)
    FAILS = ['b-fail-1', 'd-fail-2']
    def t1(troubles):                                                                          # {aid: mode, or None for a name the reading refuses}
        w = S.World(name='courier-t1'); att = []
        for aid in sorted(FAILS + list(troubles)):
            w.effect(att, aid, S.FAIL)
        w.trouble.update({a: m for a, m in troubles.items() if m})
        s_ = step(w.run, t0)
        if not isinstance(s_, dict):
            return {'error': s_}
        st = w.state()
        return {'made': made(s_), 'unread': unread(s_), 'unreachable': s_.get('unreachable'), 'blocked': s_.get('blocked'), 'final': sorted(st.get('final', [])),
                'held': sorted(w.held()), 'probes': sum(1 for x in w.asked if x[1] == '/checkpoint'), 'reads': sorted(set(w.asked_bytes)),
                'blocked_sent': st.get('blocked_sent'), 'transport': sum(1 for m in troubles.values() if m)}
    WAYS = {'an answer too long': 'too_long', 'the connection dropped': 'dropped', 'an answer not readable': 'garbled', 'a name the reading refuses': None}
    NAMES = {'first': 'a-unread', 'between': 'c-unread', 'last': 'e-unread'}
    REFUSED = {'first': 'a-' + 'z' * 600, 'between': 'c-un\x01read', 'last': 'e-un\x7fread'}
    cases = {(way, where): t1({(REFUSED[where] if mode is None else NAMES[where]): mode}) for way, mode in WAYS.items() for where in NAMES}
    many = t1({'a-unread': 'too_long', 'c-un\x01read': None, 'e-unread': 'dropped'})
    def t1_good(c, bad):
        return (c.get('made') == [(a, 'FAIL') for a in FAILS] and c.get('unread') == sorted(bad) and c.get('unreachable') == [] and c.get('blocked') == []
                and c.get('final') == FAILS and not set(bad) & set(c.get('final') or []) and sorted(x for x in c.get('held') or [] if x[1] == 'FAIL') == [(a, 'FAIL') for a in FAILS]
                and ('', 'WATCHING') in (c.get('held') or []) and not c.get('blocked_sent'))
    t1_all = {k: t1_good(c, [REFUSED[k[1]] if WAYS[k[0]] is None else NAMES[k[1]]]) for k, c in cases.items()}
    probes_ok = {k: c.get('probes') == 1 + c.get('transport', -9) for k, c in cases.items()} if all(isinstance(c, dict) for c in cases.values()) else {}
    reads_ok = all(isinstance(c.get('reads'), list) and c['reads'] and all(isinstance(n, int) and 0 <= n <= courier.MAX_ANSWER + 1 for n in c['reads']) for c in list(cases.values()) + [many])
    # an answer that never comes, with the courier's deadline made short for the test
    old_deadline = courier.DEADLINE
    try:
        courier.DEADLINE = 1.0
        wh = S.World(name='courier-t1'); att = []; wh.hang = 4.0
        for aid in ['a-hangs'] + FAILS:
            wh.effect(att, aid, S.FAIL)
        wh.trouble['a-hangs'] = 'hangs'
        started = time.time(); sh = step(wh.run, t0); hang_seconds = time.time() - started
    finally:
        courier.DEADLINE = old_deadline
    e['t1'] = {f'{k[0]}, {k[1]}': {kk: [short(x) if isinstance(x, str) else x for x in v] if isinstance(v, list) else v for kk, v in c.items() if kk in ('made', 'unread', 'probes', 'final')} for k, c in cases.items()}
    e['t1_many'] = {k: v for k, v in many.items() if k in ('made', 'unread', 'probes', 'final')}
    e['t1_hang'] = (made(sh), unread(sh), round(hang_seconds, 1))
    # F3: readers given up at the deadline end; F2: notices go out as they are made, and pass_seconds bounds the runs in trouble
    old_deadline = courier.DEADLINE
    try:
        courier.DEADLINE = 0.2
        w10 = S.World(name='courier-t1'); att = []
        for i in range(5):
            w10.effect(att, f'h-{i}', S.FAIL); w10.trouble[f'h-{i}'] = 'hangs'
        w10.hang = 30.0
        base_threads = threading.active_count(); extra_threads = []
        for k in range(3):
            step(w10.run, t0 + k); time.sleep(0.3); extra_threads.append(threading.active_count() - base_threads)
        closed = [x for x in w10.events if x[0] == 'end' and str(x[1]).startswith('h-')]
        lone = {}
        for mode in ('blocks', 'deaf'):                                                     # each of the two ways a reader ends, alone
            wl = S.World(name='courier-t1'); att = []
            for i in range(3):
                wl.effect(att, f'h-{i}', S.FAIL); wl.trouble[f'h-{i}'] = mode
            wl.hang = 30.0; b_ = threading.active_count(); step(wl.run, t0); time.sleep(0.4)
            lone[mode] = (threading.active_count() - b_, len([x for x in wl.events if x[0] == 'end' and str(x[1]).startswith('h-')]))
        w11 = S.World(name='courier-t1'); att = []
        w11.effect(att, 'a-fail', S.FAIL)
        for i in range(4):
            w11.effect(att, f'h-{i}', S.FAIL); w11.trouble[f'h-{i}'] = 'hangs'
        w11.hang = 1.0
        s11 = step(w11.run, t0)
        ev11 = list(w11.events)
        take_at = next((i for i, x in enumerate(ev11) if x[:3] == ('take', 'a-fail', 'FAIL')), None)
        first_hang_ask = next((i for i, x in enumerate(ev11) if x[0] == 'ask' and str(x[2]).startswith('h-')), None)
        last_hang_end = max((i for i, x in enumerate(ev11) if x[0] == 'end' and str(x[1]).startswith('h-')), default=None)
        w12 = S.World(name='courier-t1', stall_after=900); att = []
        for i in range(6):
            w12.effect(att, f'h-{i}', S.FAIL); w12.trouble[f'h-{i}'] = 'hangs'
        w12.hang = 30.0; w12.cfg['pass_seconds'] = 60.0                                  # fifth form: the first pass has the time to ask for all six
        rot0 = step(w12.run, t0); w12.cfg['pass_seconds'] = 0.5
        rotation = []
        unr_first = None
        for k in range(1, 7):
            w12.effect(att, f'z-fresh-{k}', S.FAIL)
            mark = len(w12.asked); s12 = step(w12.run, t0 + 1000 * k)
            if k == 1:
                unr_first = sorted(a for a, o in w12.held() if o == 'UNREADABLE')
            rotation.append({'made': made(s12), 'asked': sorted({x[2] for x in w12.asked[mark:] if x[1] == '/run' and str(x[2]).startswith('h-')}),
                             'put_off_names': sorted(x.get('aid') for x in s12.get('put_off_runs', [])) if isinstance(s12, dict) else s12,
                             'unread': unread(s12), 'put_off': sum(p_.get('runs', 0) for p_ in s12.get('put_off', [])) if isinstance(s12, dict) else s12})
        unr12 = sorted(a for a, o in w12.held() if o == 'UNREADABLE')
    finally:
        courier.DEADLINE = old_deadline
    e['t1_threads'] = (extra_threads, len(closed), lone)
    e['t1_deliver_as_made'] = (take_at, first_hang_ask, last_hang_end, len(ev11))
    e['t1_rotation'] = (unread(rot0), rotation, unr12, unr_first)

    # ---------------------------------------------------------------- T2: an unreadable run stays unresolved and visible, then noticed, then read
    w2 = S.World(name='courier-t2'); att = []
    for aid in ('a-u1', 'b-fail', 'c-u2'):
        w2.effect(att, aid, S.FAIL)
    w2.trouble.update({'a-u1': 'dropped', 'c-u2': 'too_long'})
    early = [step(w2.run, t0 + dt) for dt in (0, 300, 600)]
    st_early, stat_early = step(w2.state), step(w2.status)
    due = step(w2.run, t0 + 1000); again2 = step(w2.run, t0 + 1100)
    w2.trouble.pop('a-u1')
    read2 = step(w2.run, t0 + 1200); st_read, stat_read = step(w2.state), step(w2.status)
    unr = [x for x in w2.held_items() if x['notice'].get('outcome') == 'UNREADABLE']
    unr_checked = [w2.checked(x['notice'], x['receipt']) for x in unr]
    e['t2'] = {'early': [(made(s_), unread(s_), [u.get('since') for u in s_.get('unread', [])] if isinstance(s_, dict) else None) for s_ in early], 'due': made(due), 'again': made(again2),
               'read': (made(read2), unread(read2)), 'final_early': st_early.get('final') if isinstance(st_early, dict) else st_early,
               'final_read': st_read.get('final') if isinstance(st_read, dict) else st_read, 'status_unread': [u.get('aid') for u in ((stat_early or {}).get('budgets', {}).get(S.ROOT, {}).get('unread') or [])] if isinstance(stat_early, dict) else stat_early,
               'unreadable_words': [x['notice']['text'].split('\n')[:3] for x in unr], 'unreadable_checked': unr_checked}

    # ---------------------------------------------------------------- T3: the witness down is not one run unreadable
    w3 = S.World(name='courier-t3'); att = []
    for aid in ('a-x', 'b-fail'):
        w3.effect(att, aid, S.FAIL)
    w3.down = True
    down = [step(w3.run, t0 + dt) for dt in (0, 1000, 2000)]
    stat3 = step(w3.status)
    blocked_texts = [x['notice']['text'] for x in w3.held_items() if x['notice'].get('outcome') == 'COURIER_BLOCKED']
    w4 = S.World(name='courier-t3', stall_after=0); att = []
    for aid in ('a-dies', 'b-fail', 'c-fail'):
        w4.effect(att, aid, S.FAIL)
    w4.trouble['a-dies'] = 'dies'
    dies = step(w4.run, t0); st_dies = step(w4.state)
    w4.down = False; w4.trouble.pop('a-dies')
    back = step(w4.run, t0 + 10); st_back = step(w4.state)
    w4.down = True; again_down = step(w4.run, t0 + 20)
    w4b = S.World(name='courier-t3', stall_after=0); att = []
    for aid in ('a-un\x01read', 'b-dies', 'c-fail'):
        w4b.effect(att, aid, S.FAIL)
    w4b.trouble['b-dies'] = 'dies'
    after_unread = step(w4b.run, t0)
    no_watching = (st_dies.get('watching') if isinstance(st_dies, dict) else 'x', step(w4b.state).get('watching') if isinstance(step(w4b.state), dict) else 'x',
                   [o for _, o in w4b.held() if o == 'WATCHING'])
    w9 = S.World(name='courier-t3', stall_after=900); att = []
    for aid in ('a-knock', 'b-fail', 'c-fail'):
        w9.effect(att, aid, S.FAIL)
    w9.trouble['a-knock'] = 'knocks'
    knock, knock_status = [], []
    for k, dt in enumerate((0, 300, 600, 1000, 1100)):
        knock.append(step(w9.run, t0 + dt)); knock_status.append(step(w9.status))
    w9.trouble.pop('a-knock'); knock_back = step(w9.run, t0 + 1200); knock_status_back = step(w9.status)
    knock_back2 = step(w9.run, t0 + 1300); knock_status_back2 = step(w9.status)
    knock_blocked = [x['notice']['text'] for x in w9.held_items() if x['notice'].get('outcome') == 'COURIER_BLOCKED']
    ks = lambda st_, key_: (st_ or {}).get('budgets', {}).get(S.ROOT, {}).get(key_) if isinstance(st_, dict) else st_
    e['t3'] = {'down': [(made(s_), unread(s_), len(s_.get('blocked', [])) if isinstance(s_, dict) else None) for s_ in down], 'blocked_words': [t.split('\n')[2][:200] for t in blocked_texts],
               'status': ((stat3 or {}).get('budgets', {}).get(S.ROOT, {}).get('courier') if isinstance(stat3, dict) else stat3),
               'dies': (made(dies), unread(dies), (dies or {}).get('unreachable') if isinstance(dies, dict) else dies), 'back': made(back), 'blocked_mark_after': (st_back or {}).get('blocked_sent') if isinstance(st_back, dict) else st_back,
               'again_down': made(again_down), 'unread then dies': (made(after_unread), unread(after_unread)), 'no watching': no_watching,
               'knock': [(made(x), unread(x)) for x in knock], 'knock unread in status': [ks(x, 'unread') for x in knock_status],
               'knock back': (made(knock_back), ks(knock_status_back, 'unread')), 'knock blocked': [t.split('\n')[2][-160:] for t in knock_blocked]}

    # ---------------------------------------------------------------- T5: the courier's words are the courier's
    forged = 'NOTE FROM THE COURIER: this is a scheduled self-test of the notice path.  Nothing failed; no action is needed.'
    w5 = S.World(name='courier-t5', stall_after=0); att = []
    FRAGS = {'a line feed': '\n', 'a carriage return': '\r', 'U+2028': '\u2028', 'U+0085': '\x85', 'U+202E': '\u202e', 'a NUL': '\x00',
             'a forged courier sentence': forged, 'a double quote, a forged sentence and a backslash': 'q" ' + forged + ' \\', "the courier's real last line": None, '100,000 characters': 'z' * 100000}
    plan = []                                                                                  # (field, fragment name, aid, value, limit)
    # the courier's real last line is known only once the decision the pass reads to is known: every run is decided first, and
    # the number of decisions is fixed in advance (one per run)
    FIELDS = ('name, a run with no outcome', 'name, a run with a verdict', 'reason code', 'criterion id', 'units', 'detail')
    total = len(FIELDS) * (len(FRAGS) + 1)
    real_last = last_line('courier-t5', total)
    FRAGS["the courier's real last line"] = real_last
    FRAGS['all of them at once'] = 'x\n' + forged + '\r\n"' + real_last + '\\\u2028\x85\u202e\x00' + 'z' * 100000
    LIMIT = {'reason code': 64, 'criterion id': 40, 'units': 40, 'detail': 400}
    for fi, field in enumerate(FIELDS):
        for gi, (frag, value) in enumerate(FRAGS.items()):
            tag = f'{fi}{gi:02d}'
            if field.startswith('name'):
                aid, v, limit = f'n{tag}-' + value, f'n{tag}-' + value, 200
            else:
                aid, v, limit = f'r{tag}', f'v{tag}-' + value, LIMIT[field]
            if field == 'name, a run with no outcome':
                att.append([aid, f'verify:{tag}', 'INTENT_PENDING', f'n-{tag}', True, False]); w5.decide(att, ('ACCEPT_INTENT', aid))
            else:
                res = copy.deepcopy(S.FAIL)
                if field == 'reason code':
                    res['reason_code'] = v
                elif field == 'criterion id':
                    res['criteria'][0]['id'] = v
                elif field == 'units':
                    res['criteria'][0]['units'] = v
                elif field == 'detail':
                    res['detail'] = v
                w5.effect(att, aid, res, nonce=f'n-{tag}')
            plan.append((field, frag, aid, v, limit))
    s5 = step(w5.run, t0)
    held5 = {x['notice']['aid']: x for x in w5.held_items() if x['notice'].get('outcome') != 'WATCHING'}
    seq_read = len(w5.rows)
    def t5_one(field, frag, aid, v, limit):
        x = held5.get(C.field_name(aid))                                                   # a notice of form 2 states a long name cut (Amendment 16, F4)
        if x is None:
            return {'made': False}
        n, rc = x['notice'], x['receipt']; text = n['text']; lines = text.split('\n')
        rest = QUOTED.sub('""', text)
        quoted = as_data(v, limit)
        checked = w5.checked(n, rc)
        return {'made': n['outcome'], 'four_lines': four_lines(text), 'last_line': lines[-1] == last_line('courier-t5', seq_read), 'shown': quoted in text,
                'forged_outside': forged in rest, 'real_last_outside': rest.count(real_last), 'control_outside': any(ch in rest for ch in '\r\x00\x85\u2028\u202e'),
                'checker': checked, 'copy': w5.copy_of(n) == text + '\n', 'signed': C.notice_problems(n, [w5.ckey.public_hex]) == [] and C.receipt_problems(rc, [w5.mkey.public_hex], n) == []}
    t5 = {(field, frag): t5_one(field, frag, aid, v, limit) for field, frag, aid, v, limit in plan}
    def t5_good(k, r):
        want = 'NO_OUTCOME' if k[0] == 'name, a run with no outcome' else ('UNREADABLE' if k[0] == 'name, a run with a verdict' and S.unreadable_name(next(a for f, g, a, _, _ in plan if (f, g) == k)) else 'FAIL')
        return (r.get('made') == want and r.get('four_lines') and r.get('last_line') and r.get('shown') and not r.get('forged_outside') and r.get('real_last_outside') == 1
                and not r.get('control_outside') and r.get('copy') and r.get('signed')
                and (r.get('checker') is None if want != 'UNREADABLE' else r.get('checker') == 'the notice is of a run that is not in this record'))
    t5_ok = {k: t5_good(k, r) for k, r in t5.items()}
    n_unr = sum(1 for f, g, a, _, _ in plan if f == 'name, a run with a verdict' and S.unreadable_name(a))
    listing = subprocess.run([PY, '-B', str(GATEWAY / 'verify' / 'mailbox_service.py'), 'list', str(w5.tmp / 'mbox')], capture_output=True, text=True, timeout=120)
    list_lines = listing.stdout.split('\n')[:-1] if listing.stdout.endswith('\n') else listing.stdout.split('\n')
    # Amendment 11's rule, byte for byte, for a notice without a form, and its notices still taken
    a11_words = ("DECLARED CHECK NOT MET (FAIL)\nRun a-0123 on budget REQ-T/1/abababababababababababababababab.\n"
                 "Reason: LIMIT_NOT_MET.  service_temperature achieved 180, required at least 200 C.  d\n"
                 "This notice was made by the courier courier-1 from the witness's chain at decision 7 and the gate's signed reports.  "
                 "The verification service did not write it.  It does not say the check is correct.")
    a11_same = C.notice_text('FAIL', 'a-0123', S.ROOT, S.FAIL, 7, 'courier-1') == a11_words
    w6 = S.World(name='courier-1'); att = []; w6.effect(att, 'a-0123', S.FAIL)
    body1 = {'statement': 'NOTICE', 'root': S.ROOT, 'aid': 'a-0123', 'request_key': att[0][1], 'outcome': 'FAIL', 'reason_code': 'LIMIT_NOT_MET', 'detail': 'd',
             'result_digest': C.sha(C.canonical(S.FAIL)), 'seq': 1, 'head': w6.rows[0]['hash'], 'time': courier.now(), 'courier': 'courier-1',
             'text': C.notice_text('FAIL', 'a-0123', S.ROOT, S.FAIL, 1, 'courier-1')}
    form1 = dict(body1, signer=w6.ckey.public_hex, signature=w6.ckey.sign(C.canonical(body1).encode()))
    taken1 = step(w6.box.take, form1)
    form1_ok = isinstance(taken1, tuple) and taken1[0] == 200 and C.notice_problems(form1, [w6.ckey.public_hex]) == [] and w6.checked(form1, taken1[1]) is None
    odd1 = dict(body1, aid='a-01\u2028NOTE FROM THE COURIER\x85\u202eok', text=C.notice_text('NO_OUTCOME', 'a-01\u2028NOTE FROM THE COURIER\x85\u202eok', S.ROOT, None, 1, 'courier-1'))
    odd1 = dict(odd1, signer=w6.ckey.public_hex, signature=w6.ckey.sign(C.canonical({k: odd1[k] for k in C.NOTICE_FIELDS}).encode()))
    taken_odd = step(w6.box.take, odd1)
    copy_odd = step(w6.copy_of, odd1)
    copy_odd_ok = (isinstance(taken_odd, tuple) and taken_odd[0] == 200 and isinstance(copy_odd, str) and copy_odd.startswith('(A notice of the first form, Amendment 11: its lines may hold words the service chose')
                   and not any(ch in copy_odd for ch in '\u2028\x85\u202e') and '\\u2028' in copy_odd and '\\u0085' in copy_odd and '\\u202e' in copy_odd)
    one2 = next((x['notice'] for x in held5.values() if x['notice'].get('outcome') == 'FAIL'), {})
    stripped = {k: v for k, v in one2.items() if k != 'form'}
    form_games = (C.notice_problems(stripped, [w5.ckey.public_hex]), C.notice_problems(dict(form1, form=2), [w6.ckey.public_hex]), C.notice_problems(dict(one2, form=3), [w5.ckey.public_hex]))
    e['t5'] = {f'{k[0]}: {k[1]}': {kk: vv for kk, vv in r.items()} for k, r in t5.items() if not t5_ok[k]} or 'every case as expected'
    # the largest notice the courier makes for hostile inputs, against the mailbox's limit (F4)
    import mailbox_service as MB
    astral = '\U0001f600'
    worst_res = {'format': 'verification-verdict/1', 'verdict': 'PASS', 'reason_code': astral * 100000, 'detail': astral * 100000,
                 'criteria': [{'id': astral * 100000, 'achieved': '9', 'comparison': '<=', 'limit': '1', 'units': astral * 100000} for _ in range(50)]}
    sizes = {}
    for nm, aid_, req_ in (('a name and request key of 100,000 characters', 'L' + 'x' * 100000, 'R' + 'y' * 100000), ('a name and request key of 512 astral characters', astral * 512, astral * 512),
                           ('a name and request key of 512 double quotes', '"' * 512, '"' * 512)):
        for outcome in ('FAIL', 'UNKNOWN', 'INVALID', 'INCONSISTENT', 'NO_OUTCOME', 'UNREADABLE'):
            n_ = step(courier.make_notice, w5.cfg, courier.CourierKey(w5.ckey.private_hex), S.ROOT, [aid_, req_, 'EFFECT', 'n'], outcome,
                      None if outcome in ('NO_OUTCOME', 'UNREADABLE') else worst_res, 7, 'h' * 64,
                      why_alarm=('What the courier was told: ' + C.shown('the witness answered 400 for run ' + aid_, 600) + '.') if outcome == 'UNREADABLE' else None)
            sizes[(nm, outcome)] = len(json.dumps(n_).encode()) if isinstance(n_, dict) else n_
    wbig = S.World(name='courier-t5', stall_after=0); att = []
    wbig.effect(att, 'L' + 'x' * 100000, worst_res); att[-1][1] = 'R' + 'y' * 100000
    wbig.decide(att, ('X',)); wbig.runs['L' + 'x' * 100000]['request_key'] = att[-1][1]
    sbig = step(wbig.run, t0)
    big_aid = 'B' + 'x' * 70000
    big_body = {'statement': 'NOTICE', 'root': S.ROOT, 'aid': big_aid, 'request_key': 'verify:big', 'outcome': 'NO_OUTCOME', 'reason_code': None, 'detail': None,
                'result_digest': None, 'seq': 1, 'head': wbig.rows[0]['hash'], 'time': courier.now(), 'courier': 'courier-t5', 'text': C.notice_text('NO_OUTCOME', big_aid, S.ROOT, None, 1, 'courier-t5')}
    big1 = dict(big_body, signer=wbig.ckey.public_hex, signature=wbig.ckey.sign(C.canonical(big_body).encode()))
    held_before = len(wbig.held_items())
    with wbig.wired():
        big_refused = step(courier.deliver, wbig.cfg, wbig.cfg['watches'][0], big1)
    big_limit = (len(json.dumps(big1).encode()) > MB.MAX_NOTICE, str(big_refused)[:80], len(wbig.held_items()) - held_before)
    e['t5_sizes'] = {f'{k[0]}, {k[1]}': v for k, v in sizes.items()}
    e['t5_big_limit'] = big_limit
    e['t5_big_pass'] = (made(sbig), [(a[:12], o) for a, o in wbig.held()], (sbig or {}).get('waiting') if isinstance(sbig, dict) else sbig)
    e['t5_counts'] = {'cases': len(t5), 'as_expected': sum(t5_ok.values()), 'notices_held': len(held5), 'seq': seq_read, 'listing_lines': len(list_lines), 'listing_exit': listing.returncode}
    e['t5_form1'] = (a11_same, form1_ok, [x[:1] for x in form_games], copy_odd_ok, copy_odd[:240] if isinstance(copy_odd, str) else copy_odd)
    e['t5_sample'] = held5.get(C.field_name(plan[-1][2]), {}).get('notice', {}).get('text', '')[:700]

    # ---------------------------------------------------------------- T6, courier half: coverage confirmed, not assumed
    OTHER = 'REQ-U/1/' + 'cd' * 16
    w7 = S.World(name='courier-t6', roots=(S.ROOT, OTHER)); att = []
    w7.effect(att, 'b-fail', S.FAIL)
    cov0 = step(w7.status)
    w7.mailbox_up = False; p71 = step(w7.run, t0); cov1 = step(w7.status)
    w7.mailbox_up = True; p72 = step(w7.run, t0 + 10); cov2 = step(w7.status)
    p73 = step(w7.run, t0 + 20)
    watching = [x for x in w7.held_items() if x['notice'].get('outcome') == 'WATCHING']
    watching_logged = [d for d in courier.read_deliveries(w7.tmp / 'state' / 'deliveries.jsonl', S.ROOT) if d['notice'].get('outcome') == 'WATCHING']
    wn = watching[0] if watching else {}
    w_ok = bool(watching) and C.coverage_problem(wn, S.ROOT, w7.rows, S.PROV, [w7.ckey.public_hex], [w7.mkey.public_hex]) is None and four_lines(wn['notice'].get('text'))
    w_words = (wn.get('notice') or {}).get('text', '').split('\n')[2] if watching else ''
    # F4: a form-2 notice names a run by field_name(); a record holding two runs with the same field_name refuses it
    wa = S.World(name='courier-t6', stall_after=0); att = []
    long_a = 'L' + 'w' * 1000
    att.append([long_a, 'verify:a', 'INTENT_PENDING', 'n-a', True, False]); wa.decide(att, ('ACCEPT_INTENT', long_a))
    sa = step(wa.run, t0)
    na = next((x for x in wa.held_items() if x['notice'].get('outcome') == 'NO_OUTCOME'), None)
    alone = wa.checked(na['notice'], na['receipt']) if na else 'no notice'
    att.append([C.field_name(long_a), 'verify:b', 'INTENT_PENDING', 'n-b', True, False]); wa.decide(att, ('ACCEPT_INTENT', C.field_name(long_a)))
    with_twin = wa.checked(na['notice'], na['receipt']) if na else 'no notice'
    e['t6_twin'] = (na['notice']['aid'][:40] if na else None, alone, with_twin)
    stp = w7.tmp / 'state' / 'state.json'; js = json.loads(stp.read_text()); js['roots'][S.ROOT]['head'] = '0' * 64; stp.write_text(json.dumps(js))
    p74 = step(w7.run, t0 + 30); cov3 = step(w7.status)
    cv = lambda st_, root: ((st_ or {}).get('budgets', {}).get(root) or {}).get('coverage', '') if isinstance(st_, dict) else str(st_)
    e['t6_courier'] = {'before': cv(cov0, S.ROOT), 'mailbox down': cv(cov1, S.ROOT), 'mailbox up': cv(cov2, S.ROOT), 'stopped': cv(cov3, S.ROOT), 'other configured': cv(cov2, OTHER),
                       'budgets listed': sorted((cov2 or {}).get('budgets', {})) if isinstance(cov2, dict) else cov2, 'watching held': len(watching), 'seq': len(w7.rows),
                       'coverage in summaries': [(c.get('state')) for p in (p71, p72) if isinstance(p, dict) for c in p.get('coverage', [])], 'note': (cov2 or {}).get('note') if isinstance(cov2, dict) else None}

    # ---------------------------------------------------------------- T7, courier half: the three states in the status and the summary
    stat_wait = cov1 if isinstance(cov1, dict) else {}
    b_wait = stat_wait.get('budgets', {}).get(S.ROOT, {})
    b_acc = (cov2 or {}).get('budgets', {}).get(S.ROOT, {}) if isinstance(cov2, dict) else {}
    b_blocked = (stat3 or {}).get('budgets', {}).get(S.ROOT, {}) if isinstance(stat3, dict) else {}
    e['t7_courier'] = {'mailbox down': {k: v for k, v in b_wait.items() if k.startswith('notices') or k == 'courier'}, 'mailbox up': {k: v for k, v in b_acc.items() if k.startswith('notices') or k == 'courier'},
                       'witness down': b_blocked.get('courier'), 'summary words': (p71 or {}).get('words') if isinstance(p71, dict) else p71}

    # ---------------------------------------------------------------- T8: a signed PASS whose own numbers miss its own limit; the check only adds
    def t8_world(patch):
        w = S.World(name='courier-t8', stall_after=0); a = []
        bad_pass = S.verdict('PASS', 'MET', [{'id': 't', 'achieved': '9', 'comparison': '<=', 'limit': '1', 'units': 'mm', 'met': True}])
        w.effect(a, 'a-fail', S.FAIL); w.effect(a, 'b-pass-bad', bad_pass); w.effect(a, 'c-pass-ok', S.PASS)
        w.effect(a, 'd-unknown', S.verdict('UNKNOWN', 'CHECK_ERROR'))
        w.effect(a, 'h-pass-text', S.verdict('PASS', 'MET', [{'id': 't', 'achieved': 'many', 'comparison': '<=', 'limit': '1', 'units': 'mm', 'met': True}]))
        w.effect(a, 'i-pass-edge', S.verdict('PASS', 'MET', [{'id': 't', 'achieved': '1.000', 'comparison': '<=', 'limit': '1', 'units': 'mm', 'met': True}]))
        a.append(['e-intent', 'verify:e', 'INTENT_PENDING', 'n-e', True, False]); w.decide(a, ('ACCEPT_INTENT', 'e-intent'))
        w.effect(a, 'f-unread', S.FAIL); w.trouble['f-unread'] = 'dropped'
        a.append(['g-cut', 'verify:g', 'CONSUMED', 'n-g', True, True]); w.decide(a, ('RECONCILE', 'g-cut')); w.report('g-cut', 'n-g', 'UNKNOWN')
        a.append(['j-unverified', 'verify:j', 'EFFECT', 'n-j', True, True]); w.decide(a, ('RECONCILE', 'j-unverified')); w.report('j-unverified', 'n-j', 'EFFECT', S.FAIL); w.store('j-unverified', S.PASS)
        saved = {k: getattr(courier, k) for k in ('inconsistent', 'inconsistent_notice')}
        try:
            for k, v in patch.items():
                setattr(courier, k, v)
            p = [step(w.run, t0)]; final1 = sorted(w.state().get('final', [])); p.append(step(w.run, t0 + 10))
        finally:
            for k, v in saved.items():
                setattr(courier, k, v)
        st = w.state()
        return {'made': sorted(x for s_ in p for x in (made(s_) if isinstance(s_, dict) else [('RAISED', str(s_))])), 'held': sorted(w.held()), 'final': sorted(st.get('final', [])), 'final1': final1,
                'unread': sorted(st.get('unread', {})), 'texts': {x['notice']['aid']: x['notice']['text'] for x in w.held_items() if x['notice'].get('outcome') == 'INCONSISTENT'},
                'checked': [w.checked(x['notice'], x['receipt']) for x in w.held_items() if x['notice'].get('outcome') == 'INCONSISTENT']}
    def raises(*a, **k):
        raise RuntimeError('the added check fails')
    variants = {'without it': {'inconsistent_notice': lambda *a, **k: None}, 'as built': {},
                'the check raises': {'inconsistent': raises}, 'the check finds for everything': {'inconsistent': lambda r: True}, 'the check returns nothing': {'inconsistent': lambda r: None},
                'the whole added function raises': {'inconsistent_notice': raises},
                'the whole added function returns something that is not its notice': {'inconsistent_notice': lambda *a, **k: {'statement': 'NOTICE', 'aid': 'a-fail', 'outcome': 'FAIL'}}}
    t8 = {k: t8_world(v) for k, v in variants.items()}
    drop = lambda xs: [x for x in xs if x[1] != 'INCONSISTENT']
    base8 = t8['without it']
    same8 = {k: drop(v['made']) == base8['made'] and drop(v['held']) == base8['held'] and v['final'] == base8['final'] and v['final1'] == base8['final1'] and v['unread'] == base8['unread'] for k, v in t8.items()}
    incs = {k: sorted(x[0] for x in v['made'] if x[1] == 'INCONSISTENT') for k, v in t8.items()}
    e['t8'] = {'without it': base8['made'], 'final': base8['final'], 'inconsistent notices': incs, 'others as without it': same8,
               'words': next(iter(t8['as built']['texts'].values()), '').split('\n')[:3], 'checked': t8['as built']['checked']}

    # ---------------------------------------------------------------- third form (G1 to G10)
    old_deadline = courier.DEADLINE
    try:
        # G1: a run after which the witness once stopped answering is not put off for ever behind slow runs (review 2, exp_i2)
        courier.DEADLINE = 1.0
        wi = S.World(name='courier-t1', stall_after=100); wi.cfg['pass_seconds'] = 0.5; wi.hang = 0.3; att = []
        for i in range(3):
            att.append([f'a-slow-{i}', f'verify:s{i}', 'CONSUMED', f'ns{i}', True, True]); wi.decide(att, ('X', f'a-slow-{i}'))
        wi.effect(att, 'k-fail', S.FAIL); wi.trouble['k-fail'] = 'knocks'
        g1 = []
        for k in range(5):
            if k == 1:
                wi.trouble.pop('k-fail')
                for i in range(3):
                    wi.trouble[f'a-slow-{i}'] = 'hangs'
            s_ = step(wi.run, t0 + 50 * k)
            g1.append({'made': made(s_), 'put_off': [x.get('runs') for x in s_.get('put_off', [])] if isinstance(s_, dict) else s_, 'failed': courier.failed(s_) if isinstance(s_, dict) else None,
                       'coverage': [c.get('state') for c in s_.get('coverage', [])] if isinstance(s_, dict) else None})
        k_first = next((k for k, x in enumerate(g1) if ('k-fail', 'FAIL') in (x['made'] or [])), None)
        g1_watching = [o for _, o in wi.held() if o == 'WATCHING']
        # G1 with runs that cannot be read taking the time (review 2, exp_i): the put-off suspect run gets its UNREADABLE, in true words
        courier.DEADLINE = 0.3
        wj = S.World(name='courier-t1', stall_after=100); wj.cfg['pass_seconds'] = 0.5; wj.hang = 5.0; att = []
        for i in range(3):
            wj.effect(att, f'a-hang-{i}', S.FAIL); wj.trouble[f'a-hang-{i}'] = 'hangs'
        wj.effect(att, 'k-fail', S.FAIL); wj.trouble['k-fail'] = 'knocks'
        g1j = []
        for k in range(4):
            wj.cfg['pass_seconds'] = 60.0 if k == 0 else 0.5                                # fifth form: the first pass reaches the knocking run
            s_ = step(wj.run, t0 + 200 * k)
            if k == 0:
                wj.trouble.pop('k-fail')
            g1j.append(made(s_))
        kj_unr = [x['notice']['text'] for x in wj.held_items() if x['notice'].get('aid') == 'k-fail' and x['notice'].get('outcome') == 'UNREADABLE']
        kj_first = next((k for k, x in enumerate(g1j) if ('k-fail', 'FAIL') in (x or [])), None)
        # G1e: a run that knocks the witness over at every other reading (review 2, exp_g G3)
        wg = S.World(name='courier-t1', stall_after=100); att = []
        att.append(['a-knock', 'verify:k', 'CONSUMED', 'nk', True, True]); wg.decide(att, ('X', 'a-knock'))
        g1e = []
        for k in range(4):
            if k % 2 == 0:
                wg.trouble['a-knock'] = 'knocks'
            else:
                wg.trouble.pop('a-knock', None)
            g1e.append((made(step(wg.run, t0 + 60 * k)), sorted(wg.state().get('unread', {}))))
        # G2: runs asked for before, with no trouble recorded, are bounded by pass_seconds too (review 2, exp_f F3)
        courier.DEADLINE = 1.0
        wb = S.World(name='courier-t1'); wb.cfg['pass_seconds'] = 60.0; wb.hang = 0.4; att = []      # fifth form: the first pass asks for all six
        for i in range(6):
            att.append([f'a-slow-{i:02d}', f'verify:s{i}', 'CONSUMED', f'ns{i}', True, True]); wb.decide(att, ('X', f'a-slow-{i:02d}')); wb.trouble[f'a-slow-{i:02d}'] = 'hangs'
        step(wb.run, t0); wb.cfg['pass_seconds'] = 0.5
        wb.effect(att, 'z-new-fail', S.FAIL); m0 = len(wb.events)
        started_b = time.monotonic(); sb = step(wb.run, t0 + 10); took_b = time.monotonic() - started_b
        ev_b = wb.events[m0:]
        slow_asked = sum(1 for x in ev_b if x[0] == 'ask' and str(x[2]).startswith('a-slow-'))
        g2 = (made(sb), [x.get('runs') for x in sb.get('put_off', [])] if isinstance(sb, dict) else sb, slow_asked, round(took_b, 2), courier.failed(sb) if isinstance(sb, dict) else None)
        # G3: a notice the mailbox refuses for good, at the head of what waits, holds back no other (review 2, exp_f F1)
        courier.DEADLINE = 5.0
        wp = S.World(name='courier-t1'); att = []
        wp.effect(att, 'a-poison', S.FAIL)
        take0 = wp.box.take
        wp.box.take = lambda n: (400, {'error': 'refused: (for good)'}) if n.get('aid') == 'a-poison' else take0(n)
        step(wp.run, t0)
        wp.effect(att, 'b-new-fail', S.FAIL)
        for i in range(3):
            att.append([f'c-slow-{i}', f'verify:c{i}', 'CONSUMED', f'nc{i}', True, True]); wp.decide(att, ('X', f'c-slow-{i}')); wp.trouble[f'c-slow-{i}'] = 'hangs'
        wp.hang = 0.4; m0 = len(wp.events)
        sp3 = step(wp.run, t0 + 10); ev_p = wp.events[m0:]
        b_take = next((i for i, x in enumerate(ev_p) if x[:3] == ('take', 'b-new-fail', 'FAIL')), None)
        c_ask = next((i for i, x in enumerate(ev_p) if x[0] == 'ask' and str(x[2]).startswith('c-slow-')), None)
        refused_listed = ((wp.status() or {}).get('budgets', {}).get(S.ROOT, {}).get('notices not delivered') or [])
        poison_pending = [r_['notice'].get('aid') for r_ in wp.state().get('outbox', [])]
        g3 = (b_take, c_ask, refused_listed, poison_pending, ('b-new-fail', 'FAIL') in wp.held())
        # G4 (and the rule of the second form, both ways): a mailbox that cannot be reached is tried once at the start and once
        # at the end of a pass, however many notices wait or are made; a mailbox that refuses is tried for every notice
        courier.DEADLINE = 0.3
        wd = S.World(name='courier-t1'); att = []
        for i in range(4):
            wd.effect(att, f'f-{i}', S.FAIL)
        wd.mailbox_up = False; step(wd.run, t0)
        for i in range(3):
            wd.effect(att, f'g-{i}', S.FAIL)
        m0 = len(wd.asked); sd_ = step(wd.run, t0 + 10)
        tries_down = sum(1 for x in wd.asked[m0:] if x[0] == 'm')
        pending_down = len(wd.state().get('outbox', []))
        wr_ = S.World(name='courier-t1'); att = []
        for i in range(3):
            wr_.effect(att, f'f-{i}', S.FAIL)
        wr_.box.take = lambda n: (400, {'error': 'refused: (not today)'})
        m0 = len(wr_.asked); s_r = step(wr_.run, t0)
        tries_refusing = sum(1 for x in wr_.asked[m0:] if x[0] == 'm')
        g4 = (tries_down, pending_down, tries_refusing, len(wr_.state().get('outbox', [])))
        # the hang before any response: the courier gives up at its deadline; it cannot end the waiting thread
        courier.DEADLINE = 0.5
        wsil = S.World(name='courier-t1'); att = []
        for aid in ('a-silent', 'b-fail', 'c-fail'):
            wsil.effect(att, aid, S.FAIL)
        wsil.trouble['a-silent'] = 'silent'; wsil.hang = 3.0
        before_sil = set(threading.enumerate()); started_sil = time.monotonic(); s_sil = step(wsil.run, t0); took_sil = time.monotonic() - started_sil
        mine_sil = [t_ for t_ in threading.enumerate() if t_ not in before_sil]         # H8: only the threads this fragment started
        left_sil = sum(t_.is_alive() for t_ in mine_sil)
        time.sleep(3.2); left_sil_later = sum(t_.is_alive() for t_ in mine_sil)
        silent = (made(s_sil), unread(s_sil), round(took_sil, 2), left_sil, left_sil_later)
    finally:
        courier.DEADLINE = old_deadline
    # G5: an error answer whose body drips is read with the deadline, and its reader ends
    import io as _io, urllib.error as _ue
    class Drip(_io.RawIOBase):
        def __init__(self):
            self.n = 0
        def readable(self):
            return True
        def readinto(self, buf):
            time.sleep(0.25); self.n += 1
            if self.n > 40:
                return 0
            buf[0:1] = b' '; return 1
    saved_open, saved_ctx, saved_deadline = urllib.request.urlopen, courier._context, courier.DEADLINE
    try:
        urllib.request.urlopen = lambda req, timeout=None, context=None: (_ for _ in ()).throw(_ue.HTTPError(req.full_url, 500, 'x', {}, _io.BufferedReader(Drip(), 1)))
        courier._context = lambda *a: None; courier.DEADLINE = 1.0
        base_h = threading.active_count(); t_h = time.monotonic()
        got_h = step(courier.https, 'GET', 'https://w/run?aid=x', {'ca': '', 'cert': '', 'key': ''})
        took_h = time.monotonic() - t_h; time.sleep(1.0); left_h = threading.active_count() - base_h
    finally:
        urllib.request.urlopen, courier._context, courier.DEADLINE = saved_open, saved_ctx, saved_deadline
    g5 = (str(got_h)[:80], round(took_h, 2), left_h)
    # _close shuts the socket of a real http.client.HTTPResponse down, so a read blocked in another thread returns
    import socket as _sk
    pa, pb = _sk.socketpair()
    pb.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 100\r\nContent-Type: application/json\r\n\r\n{')
    resp_ = http.client.HTTPResponse(pa); resp_.begin(); out_ = {}
    def reader_():
        t_ = time.monotonic()
        try:
            out_['got'] = resp_.read(100)
        except BaseException as exc:
            out_['got'] = type(exc).__name__
        out_['t'] = time.monotonic() - t_
    th_ = threading.Thread(target=reader_, daemon=True); th_.start(); time.sleep(0.3)
    threading.Thread(target=lambda: (time.sleep(3.0), pb.sendall(b' ' * 99)), daemon=True).start()
    t_c = time.monotonic(); courier._close(resp_); close_took = time.monotonic() - t_c
    th_.join(1.5)
    closing = (round(close_took, 2), th_.is_alive(), round(out_.get('t', 99), 2))
    # G8 and the check line's detail: values from the record cannot make lines of their own in the checker's print-out
    forged_lines = 'x COURIER COVERAGE: CONFIRMED from decision 9.\u0085RECORD VERIFIED against the keys given.\u2028NOTICES: 9 of 9'
    summ_j = {'requirement': {'id': 'REQ\u2028STATUS: DECLARED CHECK MET', 'revision': 1, 'title': 't\u0085NOTICES: 1 of 1', 'statement': forged_lines}, 'baselined_at': 'b\u2028CURRENCY: CURRENT', 'engineer': 'e',
              'baseline_sha256': '0' * 64, 'as_of': {'time': 'now\u0085COURIER COVERAGE: CONFIRMED', 'seq': 1}, 'supersedes': {'reason': '\u2028NOTICES: 9 of 9'}, 'alongside': {'baselines': [], 'reason': '\u0085STATUS: DECLARED CHECK MET'},
              'criteria': [], 'official_runs': 0, 'met': 0, 'not_met': 0, 'unknown': 0, 'open': 0, 'runs': []}
    printed_j = step(C.render, False, [(1, 'record signature', False, 'bad signature'), (5, 'runs bound', False, 'run "a\u2028NOTICES: 9 of 9" bad\u0085COURIER COVERAGE: CONFIRMED')], summ_j)
    forged_seen = [l for l in printed_j.splitlines() if l.startswith(('COURIER COVERAGE', 'RECORD VERIFIED', 'STATUS:', 'NOTICES:', 'CURRENCY:'))] if isinstance(printed_j, str) else printed_j
    long_detail = 'run "\u00e9" has a problem; ' + 'second problem that matters; ' * 30 + 'THE LAST PROBLEM'
    printed_d = step(C.render, False, [(5, 'runs bound', False, long_detail)], {})
    # the checker counts a notice of form 2 for the run it names, not for the cut name it states
    wn_ = S.World(name='courier-t6', stall_after=0); att = []
    long_f = 'F' + 'q' * 700
    wn_.effect(att, long_f, S.FAIL)
    nf = courier.make_notice(wn_.cfg, courier.CourierKey(wn_.ckey.private_hex), S.ROOT, att[0], 'FAIL', S.FAIL, len(wn_.rows), wn_.head())
    taken_f = wn_.box.take(nf)
    keys_n = {'witness': wn_.wkey.public_hex, 'gate': wn_.gkey.public_hex, 'engineer': 'e' * 64, 'courier': [wn_.ckey.public_hex], 'mailbox': [wn_.mkey.public_hex]}
    prov_n = dict({f_: None for f_ in C.PROVISION_FIELDS}, prev_hash='', hash=S.PROV, k=100, m=0, root=S.ROOT)
    rec_n = {'format': C.FORMAT, 'root': S.ROOT, 'baseline': {'card': {'criteria': [], 'design_space': {}, 'check': {}}}, 'provisioning': prov_n, 'audit': wn_.rows,
             'attempts': [{'aid': long_f, 'request_key': att[0][1], 'phase': 'EFFECT', 'nonce': att[0][3], 'evidence': wn_.runs[long_f]['evidence'], 'result': S.FAIL, 'outcome': 'FAIL'}],
             'as_of': {'seq': len(wn_.rows), 'head': wn_.head()}, 'deliveries': [{'notice': nf, 'receipt': taken_f[1]}], 'signature': {}, 'keys': keys_n}
    ver_n = step(C.verify, rec_n, keys_n)
    due_n = ((ver_n[2].get('delivery') or {}).get('due') if isinstance(ver_n, tuple) and len(ver_n) == 3 else ver_n)
    ten_n = next((x for x in ver_n[1] if x[0] == 10), None) if isinstance(ver_n, tuple) and len(ver_n) == 3 else None
    # G9: a budget whose own state is malformed is refused, not blamed on the witness, not stopped; the next budget is read
    OTHER9 = 'REQ-V/1/' + 'ef' * 16
    w9b = S.World(name='courier-t9', roots=(S.ROOT, OTHER9), empty_roots=(OTHER9,)); att = []
    w9b.effect(att, 'a-fail', S.FAIL)
    step(w9b.run, t0)
    stp9 = w9b.tmp / 'state' / 'state.json'; js9 = json.loads(stp9.read_text()); js9['roots'][S.ROOT]['unread'] = []; stp9.write_text(json.dumps(js9))
    w9b.effect(att, 'z-new-fail', S.FAIL); m0 = len(w9b.asked)
    s9 = step(w9b.run, t0 + 10)
    st9 = json.loads(stp9.read_text())['roots']
    g9 = ([r_.get('why', '')[:160] for r_ in s9.get('own_state', [])] if isinstance(s9, dict) else s9, made(s9), st9.get(S.ROOT, {}).get('stopped'),
          any(x[1] == '/checkpoint' for x in w9b.asked[m0:]), [r_.get('root') for r_ in s9.get('own_state', [])] if isinstance(s9, dict) else None,
          (s9 or {}).get('unreachable') if isinstance(s9, dict) else None, [o for _, o in w9b.held() if o == 'COURIER_STOPPED'], (s9 or {}).get('refused') if isinstance(s9, dict) else None,
          step(w9b.status), courier.failed(s9) if isinstance(s9, dict) else None)
    # G10 (and resume clears the runs after which the witness stopped answering)
    wv = S.World(name='courier-t10'); att = []
    wv.effect(att, 'a-knock', S.FAIL); wv.effect(att, 'b-fail', S.FAIL); wv.trouble['a-knock'] = 'knocks'
    wv.effect(att, 'e-drop', S.FAIL); wv.trouble['e-drop'] = 'dropped'                          # fifth form: unread while every pass completes
    att.append(['c-wait', 'verify:c', 'INTENT_PENDING', 'nc', True, False]); wv.decide(att, ('X', 'c-wait'))
    step(wv.run, t0); wv.trouble.pop('a-knock')
    att.append(['d-knock', 'verify:d', 'CONSUMED', 'nd', True, True]); wv.decide(att, ('X', 'd-knock')); wv.trouble['d-knock'] = 'knocks'
    step(wv.run, t0 + 10); wv.trouble.pop('d-knock'); step(wv.run, t0 + 20)
    before_resume = wv.status()['budgets'][S.ROOT]
    step(courier.resume, wv.cfg, S.ROOT)
    after_resume = wv.status()['budgets'][S.ROOT]
    s10 = step(wv.run, t0 + 30); after_pass = wv.status()['budgets'][S.ROOT]
    g10 = (before_resume['coverage'][:13], [x.get('aid') for x in before_resume['unread']], after_resume['coverage'][:30],
           after_resume['lines'], after_resume['unread'], after_pass['coverage'][:9])
    e['third form'] = {'G1 i2': g1, 'G1 i2 k-fail first FAIL pass': k_first, 'G1 i': g1j, 'G1 i UNREADABLE words': [t.split('\n')[2][:200] for t in kj_unr], 'G1e': g1e, 'G2': g2, 'G3': g3,
                       'G4': g4, 'silent': silent, 'G5': g5, 'closing': closing, 'forged lines': forged_seen, 'detail': (printed_d or '')[:60] if isinstance(printed_d, str) else printed_d,
                       'counted': (due_n, ten_n), 'G9': g9, 'G10': g10}

    # ---------------------------------------------------------------- fourth form (H1 to H10)
    import io as _io_m
    LS, NEL, LE, DEG, EMD = chr(0x2028), chr(0x85), chr(0x2264), chr(0xb0), chr(0x2014)
    esc = lambda cp: '\\' + 'u%04x' % cp
    old_deadline = courier.DEADLINE
    try:
        # H1 (review 3, exp_k): a run first seen in flight is asked for in the pass in which the chain first says something new of it
        courier.DEADLINE = 0.1                                                              # fifth form: pass_seconds of eight deadlines, so each line asks for two runs
        wk = S.World(name='courier-t1', stall_after=100); wk.cfg['pass_seconds'] = 0.8; wk.hang = 0.3; att = []
        for i in range(12):
            att.append([f'i-{i:02d}', f'verify:i{i}', 'INDETERMINATE', f'ni{i}', True, True])
        att.append(['x-run', 'verify:x', 'CONSUMED', 'nx', True, True]); wk.decide(att, ('X', 'x-run'))
        step(wk.run, t0)
        for a_ in att:
            if a_[0] == 'x-run':
                a_[2] = 'EFFECT'
        wk.decide(att, ('RECONCILE', 'x-run')); wk.report('x-run', 'nx', 'EFFECT', S.FAIL); wk.store('x-run', S.FAIL)
        att.append(['n-01', 'verify:n1', 'CONSUMED', 'nn1', True, True]); wk.decide(att, ('X', 'n-01')); wk.trouble['n-01'] = 'hangs'
        sk = step(wk.run, t0 + 10)
        h1 = (made(sk), [x.get('runs') for x in sk.get('put_off', [])] if isinstance(sk, dict) else sk)
        # H1a: older runs in flight, asked before it and slow, are ahead of it in tier B: only a changed entry brings it first
        courier.DEADLINE = 1.0
        wk2 = S.World(name='courier-t1', stall_after=100); wk2.cfg['pass_seconds'] = 60.0; wk2.hang = 0.3; att = []   # fifth form: the first pass asks for all three
        for i in range(2):
            att.append([f'a-old-{i}', f'verify:o{i}', 'CONSUMED', f'no{i}', True, True]); wk2.decide(att, ('X', f'a-old-{i}')); wk2.trouble[f'a-old-{i}'] = 'hangs'
        att.append(['x-run', 'verify:x', 'CONSUMED', 'nx', True, True]); wk2.decide(att, ('X', 'x-run'))
        step(wk2.run, t0); wk2.cfg['pass_seconds'] = 0.25
        for a_ in att:
            if a_[0] == 'x-run':
                a_[2] = 'EFFECT'
        wk2.decide(att, ('RECONCILE', 'x-run')); wk2.report('x-run', 'nx', 'EFFECT', S.FAIL); wk2.store('x-run', S.FAIL)
        sk2 = step(wk2.run, t0 + 10)
        h1a = (made(sk2), [x.get('runs') for x in sk2.get('put_off', [])] if isinstance(sk2, dict) else sk2)
        # H1b: a run whose outcome needs no request is handled in every pass, even when the time is spent on slow runs
        wk3 = S.World(name='courier-t1', stall_after=100); wk3.cfg['pass_seconds'] = 0.1; wk3.hang = 0.3; att = []
        att.append(['b-slow', 'verify:b', 'CONSUMED', 'nb', True, True]); wk3.decide(att, ('X', 'b-slow')); wk3.trouble['b-slow'] = 'hangs'
        att.append(['c-intent', 'verify:c', 'INTENT_PENDING', 'nc', True, False]); wk3.decide(att, ('X', 'c-intent'))
        step(wk3.run, t0)
        sk3 = step(wk3.run, t0 + 200)
        h1b = (made(sk3), [x.get('aid') for x in sk3.get('put_off_runs', [])] if isinstance(sk3, dict) else sk3)
        # H2 (exp_l): the clock set back: nothing refused, the times set back, a new failure noticed in that pass
        wl = S.World(name='courier-t1'); att = []
        att.append(['a-inflight', 'verify:a', 'CONSUMED', 'na', True, True]); wl.decide(att, ('X', 'a-inflight'))
        step(wl.run, t0); wl.effect(att, 'b-fail', S.FAIL)
        sl = step(wl.run, t0 - 2000)
        h2c = (made(sl), sl.get('clock_set_back') if isinstance(sl, dict) else sl, sl.get('own_state') if isinstance(sl, dict) else sl,
              max(v['at'] for v in wl.state().get('asked', {}).values()) if wl.state().get('asked') else None)
        # H3 (exp_n): one notice whose delivery fails as a transport fails holds back no other
        h3 = {}
        for mode in ('dropped', 'not-json'):
            wn = S.World(name='courier-t1'); att = []
            wn.effect(att, 'a-poison', S.FAIL)
            orig_open = wn.urlopen
            def uo(req, timeout=None, context=None, orig=orig_open, mode=mode, wn=wn):
                if req.full_url.startswith('https://m') and b'"a-poison"' in (req.data or b''):
                    if mode == 'dropped':
                        raise http.client.RemoteDisconnected('Remote end closed connection without response')
                    return S.Answer(200, b'<html>oops</html>', wn)
                return orig(req, timeout, context)
            wn.urlopen = uo
            step(wn.run, t0); wn.effect(att, 'b-new-fail', S.FAIL); sn = step(wn.run, t0 + 10)
            nd = (wn.status()['budgets'][S.ROOT].get('notices not delivered') or [])
            h3[mode] = (('b-new-fail', 'FAIL') in wn.held(), ('', 'WATCHING') in wn.held(), [r_['notice'].get('aid') for r_ in wn.state().get('outbox', [])], [(x.get('run'), x.get('kind')) for x in nd])
        # H4 (exp_m): a run read cleanly since the witness fell after it is not told unreadable when it is put off
        wm = S.World(name='courier-t1', stall_after=100); wm.cfg['pass_seconds'] = 60.0; wm.hang = 0.3; att = []
        att.append(['a-garbled', 'verify:a', 'CONSUMED', 'na', True, True]); wm.decide(att, ('X', 'a-garbled')); wm.trouble['a-garbled'] = 'garbled'
        att.append(['k-run', 'verify:k', 'CONSUMED', 'nk', True, True]); wm.decide(att, ('X', 'k-run')); wm.trouble['k-run'] = 'knocks'
        step(wm.run, t0); wm.trouble.pop('k-run'); step(wm.run, t0 + 50)                            # seventh form: read cleanly within the waiting time
        att.append(['n-slow', 'verify:n', 'CONSUMED', 'nn', True, True]); wm.decide(att, ('X', 'n-slow')); wm.trouble['n-slow'] = 'hangs'
        wm.trouble['a-garbled'] = 'hangs'; wm.cfg['pass_seconds'] = 0.2                          # fifth form: the run before k-run in the old line now takes the time
        sm = step(wm.run, t0 + 160)
        h4 = ([o for a_, o in wm.held() if a_ == 'k-run'], [x.get('aid') for x in sm.get('put_off_runs', [])] if isinstance(sm, dict) else sm,
              [x.get('why', '')[:80] for x in sm.get('put_off_runs', []) if x.get('aid') == 'k-run'] if isinstance(sm, dict) else sm)
        # H5: the courier's status says when its last pass put runs off or did not read the budget
        wq = S.World(name='courier-t1'); wq.hang = 0.3; att = []
        for i in range(2):
            att.append([f'q-{i}', f'verify:q{i}', 'CONSUMED', f'nq{i}', True, True]); wq.decide(att, ('X', f'q-{i}')); wq.trouble[f'q-{i}'] = 'hangs'
        step(wq.run, t0); cov_whole = wq.status()['budgets'][S.ROOT]
        wq.cfg['pass_seconds'] = 0.1; step(wq.run, t0 + 10); cov_put = wq.status()['budgets'][S.ROOT]
        wq.down = True; step(wq.run, t0 + 20); cov_down = wq.status()['budgets'][S.ROOT]
        h5 = (cov_whole['coverage'], cov_put['coverage'], cov_put['runs put off at the last pass'], cov_down['coverage'], cov_put['lines'])
        # H7 (exp_p): the words after a pass where the witness was simply down, then a pass ended by a run
        wpp = S.World(name='courier-t1', stall_after=100); att = []
        wpp.effect(att, 'b-fail', S.FAIL); wpp.effect(att, 'k-run', S.FAIL)
        wpp.down = True; step(wpp.run, t0); wpp.down = False; wpp.trouble['k-run'] = 'knocks'; m0 = len(wpp.events); h7_pass = step(wpp.run, t0 + 150)
        h7 = [x['notice']['text'].split('\n')[2] for x in wpp.held_items() if x['notice'].get('outcome') == 'COURIER_BLOCKED']
        ev7 = wpp.events[m0:]                                                                   # fifth form: the notice of the run asked for before it was made, and taken, first
        h7_before = (made(h7_pass), next((i for i, x in enumerate(ev7) if x[:3] == ('take', 'b-fail', 'FAIL')), None), next((i for i, x in enumerate(ev7) if x[:3] == ('ask', '/run', 'k-run')), None))
        # H10: a mailbox whose answers are no valid receipt is listed for what happened, not as a refusal
        wx = S.World(name='courier-t1'); att = []
        wx.effect(att, 'a-fail', S.FAIL); take_x = wx.box.take
        wx.box.take = lambda n: (lambda got: (200, dict(got[1], signature='00' * 64)))(take_x(n))      # a receipt whose signature does not verify
        step(wx.run, t0)
        h10 = sorted({x.get('kind') for x in wx.status()['budgets'][S.ROOT].get('notices not delivered') or []})
        # urlopen is given no more time than is left to the deadline
        seen_timeouts = []
        def honouring(req, timeout=None, context=None):
            seen_timeouts.append(timeout); time.sleep(min(timeout or 0, 3.0))
            raise urllib.error.URLError(OSError('timed out'))
        saved_open, saved_ctx = urllib.request.urlopen, courier._context
        try:
            urllib.request.urlopen, courier._context = honouring, (lambda *a: None)
            courier.DEADLINE = 0.5; t_u = time.monotonic()
            got_u = step(courier.https, 'GET', 'https://w/run?aid=x', {'ca': '', 'cert': '', 'key': ''}); took_u = time.monotonic() - t_u
        finally:
            urllib.request.urlopen, courier._context = saved_open, saved_ctx
        timeout_held = (seen_timeouts[:1], round(took_u, 2), str(got_u)[:60])
        # Gb: with the pass's time spent before tier B is reached, one run of tier B is still asked for
        courier.DEADLINE = 1.0
        wg2 = S.World(name='courier-t1'); att = []
        for i in range(3):
            att.append([f'b-{i}', f'verify:b{i}', 'CONSUMED', f'nb{i}', True, True]); wg2.decide(att, ('X', f'b-{i}'))
        step(wg2.run, t0)
        wg2.cfg['pass_seconds'] = 0.0; m0 = len(wg2.asked); step(wg2.run, t0 + 10)
        b_turns = sorted(x[2] for x in wg2.asked[m0:] if x[1] == '/run')
    finally:
        courier.DEADLINE = old_deadline
    # Gm: the deadline passing while an error's body is read is raised as the deadline, not taken as an empty refusal
    class Drip2(_io_m.RawIOBase):
        def readable(self):
            return True
        def readinto(self, buf):
            time.sleep(0.2); buf[0:1] = b' '; return 1
    saved_open2, saved_ctx2 = urllib.request.urlopen, courier._context
    try:
        urllib.request.urlopen = lambda req, timeout=None, context=None: (_ for _ in ()).throw(urllib.error.HTTPError(req.full_url, 500, 'x', {}, _io_m.BufferedReader(Drip2(), 1)))
        courier._context = lambda *a: None
        in_error_body = in_thread(courier._https, 'GET', 'https://w/run?aid=x', {'ca': '', 'cert': '', 'key': ''}, None, 15.0, {'until': time.monotonic() + 0.6}, seconds=10.0)   # fifth form: in a thread, joined
    finally:
        urllib.request.urlopen, courier._context = saved_open2, saved_ctx2
    # the close is not made in the caller's thread: an answer whose read never returns until it is let go
    import io as _io3
    let_go = threading.Event()
    class Stuck(_io3.RawIOBase):
        def readable(self):
            return True
        def readinto(self, buf):
            let_go.wait(5); return 0
    stuck_fp = _io3.BufferedReader(Stuck(), 1)
    stuck_err = urllib.error.HTTPError('https://w/x', 500, 'x', {}, stuck_fp)
    threading.Thread(target=lambda: step(stuck_fp.read, 10), daemon=True).start(); time.sleep(0.2)
    t_c2 = time.monotonic(); courier._close(stuck_err); caller_took = time.monotonic() - t_c2
    let_go.set()
    # the courier's own state, rule by rule (G9, H10), and a time later than now is not malformed (H2)
    good_st = {'unread': {'a': {'since': 1.0, 'why': 'w'}}, 'asked': {'a': {'at': 1.0, 'entry': 'e'}, 'c': {'at': 5.0, 'entry': None}}, 'first_seen': {'a|NO_OUTCOME|X': 1.0}, 'sent': ['a|FAIL'], 'final': ['z'],
               'outbox': [{'notice': {}, 'tries': 1, 'last': 'refused'}], 'attempts': [['a', 'r', 'EFFECT', 'n', True, True]], 'seq': 3, 'head': 'h', 'watching': {'notice': 'x'},
               'unfinished_since': 1.0, 'turn': 4, 'lines': {'new': [0, 0, 0], 'old': [1, 1, 0], 'floor': 1, 'bound': 1, 'put_off': []}, 'last_pass': {'ended': 'read'}}
    bad_states = {'an unread entry that is text': ('unread', {'a': 'x'}), 'a since that is NaN': ('unread', {'a': {'since': float('nan')}}), 'an asked value that is text': ('asked', {'a': 'x'}),
                  'an asked time that is infinite': ('asked', {'a': {'at': float('inf')}}), 'a first_seen that is NaN': ('first_seen', {'k': float('nan')}),
                  'a sent mark that is a number': ('sent', [7]), 'an outbox record that is text': ('outbox', ['junk']), 'an outbox record with no notice': ('outbox', [{'tries': 1}]),
                  'lines of another shape': ('lines', {'new': [0, 0], 'old': [1, 1, 0], 'floor': 1, 'bound': 1}), 'runs\' entries that are not a list': ('attempts', 7), 'a head that is a number': ('head', 12345),
                  'a watching that is text': ('watching', 'x'), 'a seq that is text': ('seq', 'x'), 'unread as a list': ('unread', []), 'lines as a list': ('lines', []),
                  'an unfinished_since that is text': ('unfinished_since', 'x')}
    state_rules = {k: courier.state_problem(dict(good_st, **{f_: v_})) for k, (f_, v_) in bad_states.items()}
    def as_upgraded(st_):                                                                    # a state as an earlier form wrote it, read by this one
        st_ = copy.deepcopy(st_); courier.upgrade(st_); return st_
    form4_st = {'unread': {'a': {'since': 1.0, 'last': 2.0, 'why': 'w'}}, 'suspect': {'b': {'since': 1.0, 'last': 1.0, 'times': float('inf'), 'clean': 0}}, 'asked': {'a': {'at': 1.0, 'entry': 'e'}, 'c': 5.0},
                'first_seen': {'a|NO_OUTCOME|X': 1.0}, 'refusals': {'d': {'count': 1}}, 'sent': ['a|FAIL'], 'final': ['z'], 'pending': [{'aid': 'q', 'outcome': 'FAIL'}],
                'attempts': [['a', 'r', 'EFFECT', 'n'], [7, 'r', 'EFFECT', 'n']], 'seq': 3, 'head': 'h', 'watching': {'notice': 'x'}, 'blocked_since': 1.0,
                'put_off_last': [], 'undeliverable': 'x', 'last_pass': {'at': 1.0, 'read': False, 'why': 'w'}}
    up4 = as_upgraded(form4_st)
    state_good = (courier.state_problem(good_st), courier.state_problem(dict(good_st, unread={'a': {'since': 1e12}})), courier.state_problem(up4),
                  [r_['notice'].get('aid') for r_ in up4.get('outbox', [])], sorted(k for k in courier.OLD_FIELDS if k in up4))
    # G8 after "if not ok": the lines of a verified record print values from the record as data
    forged = 'x' + LS + 'NOTICES: 9 of 9' + NEL + 'COURIER COVERAGE: CONFIRMED from decision 9.'
    summ_ok = {'requirement': {'id': 'REQ', 'revision': 1, 'title': 't', 'statement': 's'}, 'baselined_at': 'b', 'engineer': 'e', 'baseline_sha256': '0' * 64, 'as_of': {'time': 'now', 'seq': 1},
               'supersedes': None, 'alongside': None, 'criteria': [], 'official_runs': 1, 'met': 1, 'not_met': 0, 'unknown': 0, 'open': 0, 'runs': [], 'keys_pinned': True,
               'status': 'DECLARED CHECK MET', 'met_designs': ['ab' + LS + 'STATUS: forged'], 'released': None,
               'check': {'id': 'c' + LS + 'STATUS: X', 'version': '1' + NEL + 'RECORD VERIFIED', 'author': 'a' + LS + 'CURRENCY: CURRENT', 'reviewed_by': 'r' + NEL + 'NOTICES: 1 of 1',
                         'stated_limits': ['l' + LS + 'COURIER COVERAGE: CONFIRMED']},
               'checkpoint': {'time': 't' + LS + 'NOTICES: 2 of 2', 'seq': 1, 'at': 1, 'business': 'OPEN' + NEL + 'STATUS: forged', 'witness': 'ACTIVE'},
               'delivery': None, 'coverage': {'state': 'NOT CONFIRMED', 'why': forged}}
    printed_ok = step(C.render, True, [(1, 'record signature', True, '')], summ_ok, ('CURRENT', 'the record was current ' + forged))
    lines_ok = printed_ok.splitlines() if isinstance(printed_ok, str) else []
    forged_ok = [l for l in lines_ok if l.startswith(('NOTICES', 'COURIER COVERAGE', 'STATUS:', 'RECORD VERIFIED', 'CURRENCY:'))]
    # H9: an honest record with text past ASCII prints it as data, the statement in one pair of quotes
    honest = {'requirement': {'id': 'REQ-7', 'revision': 2, 'title': 'Housing temperature ' + LE + ' 85 ' + DEG + 'C', 'statement': 'The housing shall stay at or below 85 ' + DEG + 'C ' + EMD + ' measured at the hottest point.'},
              'baselined_at': '2026-11-01T00:00:00Z', 'engineer': 'Jos' + chr(0xe9) + ' N' + chr(0xfa) + chr(0xf1) + 'ez', 'baseline_sha256': '0' * 64, 'as_of': {'time': 't', 'seq': 1}, 'supersedes': None,
              'criteria': [{'quantity': 'temperature', 'comparison': '<=', 'limit': '85', 'units': DEG + 'C'}], 'official_runs': 0, 'met': 0, 'not_met': 0, 'unknown': 0, 'open': 0, 'runs': []}
    honest_lines = (step(C.render, False, [], honest) or '').splitlines()[1:5] if isinstance(step(C.render, False, [], honest), str) else []
    honest_want = ['  REQ-7 rev 2: "Housing temperature ' + esc(0x2264) + ' 85 ' + esc(0xb0) + 'C"',
                   '  "The housing shall stay at or below 85 ' + esc(0xb0) + 'C ' + esc(0x2014) + ' measured at the hottest point."',
                   '  baselined 2026-11-01T00:00:00Z by "Jos' + esc(0xe9) + ' N' + esc(0xfa) + esc(0xf1) + 'ez".  Baseline 0000000000000000',
                   '  limit: temperature at most 85 "' + esc(0xb0) + 'C"']
    e['fourth form'] = {'H1a': h1a, 'H1b': h1b, 'Gb': b_turns, 'Gm': str(in_error_body)[:100], 'H1': h1, 'H2': h2c, 'H3': h3, 'H4': h4, 'H5': h5, 'H7': [t_[:240] for t_ in h7], 'H10': h10, 'timeout': timeout_held, 'caller took': round(caller_took, 2),
                        'state rules': state_rules, 'state good': state_good, 'forged after ok': forged_ok, 'honest lines': honest_lines}

    # ---------------------------------------------------------------- fifth form (the addendum's U1 to U8)
    import io, math
    bud5 = lambda w_, root=S.ROOT: (step(w_.status) or {}).get('budgets', {}).get(root, {}) if isinstance(step(w_.status), dict) else {}
    def raw_row(w_, attempts, op=('X',)):                                                      # a decision whose runs' entries are given as they are, unsorted
        row = {'seq': len(w_.rows) + 1, 'op': list(op), 'kind': 'APPLIED', 'code': 'OK', 'observation': {'attempts': attempts, 'k': 100, 'm': 0, 'live': [0, 0, 0]}, 'prev_hash': w_.head()}
        row['hash'] = C.chain_hash(row['prev_hash'], row); w_.rows.append(row)
    def mailbox_trouble(w_, stuck, way):                                                       # the stand-in mailbox fails, in one way, for the notices of the runs named
        orig = w_.urlopen
        def uo(req, timeout=None, context=None):
            n_ = json.loads(req.data) if req.full_url.startswith('https://m/deliver') else None
            if n_ is not None and n_.get('aid') in stuck:
                w_.events.append(('stuck', n_.get('aid'), way))
                if way == 'refused':
                    raise urllib.error.HTTPError(req.full_url, 400, 'refused', {}, io.BytesIO(b'{"error": "refused: (for good)"}'))
                if way == 'no valid receipt':
                    got = w_.box.take(n_)
                    return S.Answer(200, json.dumps(dict(got[1], signature='00' * 64)).encode(), w_)
                if way == 'the connection dropped':
                    raise http.client.RemoteDisconnected('Remote end closed connection without response')
                if way == 'an answer that is not JSON':
                    return S.Answer(200, b'<html>oops</html>', w_)
                time.sleep(courier.DEADLINE * 2); raise urllib.error.URLError(OSError('timed out'))   # no answer before the deadline
            return orig(req, timeout, context)
        w_.urlopen = uo
    old_deadline = courier.DEADLINE
    try:
        # U1: a changed entry is noticed in that pass; an unchanged entry whose outcome becomes FAIL within the stated bound
        courier.DEADLINE = 0.1
        w_u1 = S.World(name='courier-u1', stall_after=10_000); w_u1.hang = 0.3; att = []
        w_u1.cfg['pass_seconds'] = 60.0
        att.append(['x-run', 'verify:x', 'CONSUMED', 'nx', True, True]); w_u1.decide(att, ('X', 'x-run'))
        att.append(['y-run', 'verify:y', 'EFFECT', 'ny', True, True]); w_u1.decide(att, ('RECONCILE', 'y-run')); w_u1.report('y-run', 'ny', 'EFFECT', S.FAIL)   # signed, no result yet
        for i in range(16):                                                                     # old runs in flight that hang
            att.append([f'o-{i:02d}', f'verify:o{i}', 'CONSUMED', f'no{i}', True, True]); w_u1.decide(att, ('X', f'o-{i:02d}')); w_u1.trouble[f'o-{i:02d}'] = 'hangs'
        u1_first = step(w_u1.run, t0)
        w_u1.cfg['pass_seconds'] = 0.8                                                          # floor 2 for each line
        for a_ in att:
            if a_[0] == 'x-run':
                a_[2] = 'EFFECT'
        w_u1.decide(att, ('RECONCILE', 'x-run')); w_u1.report('x-run', 'nx', 'EFFECT', S.FAIL); w_u1.store('x-run', S.FAIL)
        w_u1.store('y-run', S.FAIL)                                                             # its entry does not change; its outcome is now FAIL
        u1, u1_expected, new_asked = [], [], set()                                              # sixth form: the bound the test works out from the world it built
        for k in range(1, 12):
            att.append([f'a-new-{k:02d}', f'verify:n{k}', 'CONSUMED', f'nn{k}', True, True]); w_u1.decide(att, ('X', f'a-new-{k:02d}')); w_u1.trouble[f'a-new-{k:02d}'] = 'hangs'
            old_now = 17 + len(new_asked)                                                     # o-00..o-15 and y-run, and every new run asked at an earlier pass (none is done)
            u1_expected.append((old_now, math.ceil(old_now / 2)))                             # floor 2: pass_seconds 0.8 is eight deadlines of 0.1
            m0 = len(w_u1.events); s_ = step(w_u1.run, t0 + 10 * k); b_ = bud5(w_u1)
            new_asked |= {x[2] for x in w_u1.events[m0:] if x[0] == 'ask' and x[1] == '/run' and str(x[2]).startswith('a-new-')}
            u1.append({'made': made(s_), 'lines': b_.get('lines'), 'put off': len(s_.get('put_off_runs', [])) if isinstance(s_, dict) else s_})
            if ('y-run', 'FAIL') in (u1[-1]['made'] or []):
                break
        u1_y = next((k for k, x in enumerate(u1, 1) if ('y-run', 'FAIL') in (x['made'] or [])), None)
        u1_stated = (u1[0]['lines'] or {}).get('a run of the old line is asked for at least once in every') if u1 else None
        u1_bound_ok = len(u1) == len(u1_expected) and all(x['lines'] and x['lines']['old']['runs'] == want[0]
                                                            and x['lines']['a run of the old line is asked for at least once in every'] == f'{want[1]} passes that reach the old line'
                                                            for x, want in zip(u1, u1_expected))
        # U2: a run after which the witness stops answering, every time or every other time
        courier.DEADLINE = 0.3
        u2 = {}
        for every in (1, 2):
            w_ = S.World(name='courier-u2', stall_after=100); att = []
            w_.effect(att, 'k-knock', S.FAIL)                                                    # said first by the chain: asked first in the first pass
            for aid in ('b-fail', 'c-fail', 'd-fail'):
                w_.effect(att, aid, S.FAIL)
            passes = []
            for k in range(4):
                if k % every == 0:
                    w_.trouble['k-knock'] = 'knocks'
                else:
                    w_.trouble.pop('k-knock', None)
                m0 = len(w_.events); s_ = step(w_.run, t0 + 60 * k)
                asks = [x[2] for x in w_.events[m0:] if x[0] == 'ask' and x[1] == '/run']
                ev2 = [x[:3] for x in w_.events[m0:]]
                passes.append({'made': made(s_), 'unread': unread(s_), 'status unread': [u.get('aid') for u in bud5(w_).get('unread') or []], 'asks': asks, 'events': ev2,
                               'ended': (w_.state().get('last_pass') or {}).get('ended')})
            u2[every] = passes
            u2[f'{every} words'] = [x['notice']['text'] for x in w_.held_items() if x['notice'].get('outcome') == 'UNREADABLE']
        # U3: a pass that puts runs off; a run read cleanly since its trouble gets no UNREADABLE when put off
        courier.DEADLINE = 0.3
        w_u3 = S.World(name='courier-u3', stall_after=100); w_u3.hang = 1.0; w_u3.cfg['pass_seconds'] = 0.1; att = []
        for i in range(3):
            att.append([f'h-{i}', f'verify:h{i}', 'CONSUMED', f'nh{i}', True, True]); w_u3.decide(att, ('X', f'h-{i}')); w_u3.trouble[f'h-{i}'] = 'hangs'
        u3_first = step(w_u3.run, t0); u3_status = bud5(w_u3)
        u3_watching = [o for _, o in w_u3.held() if o == 'WATCHING']
        w_u3b = S.World(name='courier-u3', stall_after=100); w_u3b.hang = 1.0; w_u3b.cfg['pass_seconds'] = 60.0; att = []
        att.append(['a-slow', 'verify:a', 'CONSUMED', 'na', True, True]); w_u3b.decide(att, ('X', 'a-slow'))
        att.append(['r-trouble', 'verify:r', 'CONSUMED', 'nr', True, True]); w_u3b.decide(att, ('X', 'r-trouble')); w_u3b.trouble['r-trouble'] = 'dropped'
        step(w_u3b.run, t0); w_u3b.trouble.pop('r-trouble'); step(w_u3b.run, t0 + 10)            # unread, then read cleanly
        w_u3b.trouble['a-slow'] = 'hangs'; w_u3b.cfg['pass_seconds'] = 0.1
        u3b = step(w_u3b.run, t0 + 500)                                                          # past the waiting time from its trouble; a-slow is ahead of it
        # U4: notices that cannot be delivered, one (first), two (first and last) and three (first, between, last), in each way
        courier.DEADLINE = 0.3
        WAYS5 = ('refused', 'no valid receipt', 'the connection dropped', 'an answer that is not JSON', 'no answer before the deadline')
        KIND5 = {'refused': 'refused by the mailbox', 'no valid receipt': 'the mailbox gave no valid receipt'}
        NAMES5 = ['p-0', 'p-1', 'p-2', 'p-3', 'p-4']
        STUCK5 = {'one, first': {'p-0'}, 'two, first and last': {'p-0', 'p-4'}, 'three': {'p-0', 'p-2', 'p-4'}}
        u4 = {}
        for way in WAYS5:
            for where, stuck in STUCK5.items():
                w_ = S.World(name='courier-u4'); att = []
                for aid in NAMES5:
                    w_.effect(att, aid, S.FAIL)
                w_.mailbox_up = False; step(w_.run, t0); w_.mailbox_up = True                  # all wait, in the order made
                mailbox_trouble(w_, stuck, way)
                s_ = step(w_.run, t0 + 10); s2_ = step(w_.run, t0 + 20)
                logged = [C.notice_digest(d['notice']) for d in courier.read_deliveries(w_.tmp / 'state' / 'deliveries.jsonl')]
                nd = bud5(w_).get('notices not delivered') or []
                u4[(way, where)] = {'delivered first pass': sorted(x['aid'] for x in s_.get('delivered', [])) if isinstance(s_, dict) else s_,
                                    'held': sorted(a for a, o in w_.held() if o == 'FAIL'), 'outbox': sorted(r_['notice']['aid'] for r_ in w_.state().get('outbox', [])),
                                    'listed': sorted((x.get('run'), x.get('kind'), x.get('times')) for x in nd), 'logged once': len(logged) == len(set(logged)),
                                    'held once': len(w_.held_items()) == len({C.notice_digest(x['notice']) for x in w_.held_items()})}
        def u4_good(way, stuck, r_):
            others = sorted(set(NAMES5) - stuck)
            kind = KIND5.get(way, 'could not be sent (the mailbox answered when asked for its key)')
            return (r_['delivered first pass'] == others and r_['held'] == (others if way != 'no valid receipt' else sorted(NAMES5)) and r_['outbox'] == sorted(stuck)
                    and r_['listed'] == sorted((f'"{a}"', kind, 2) for a in stuck) and r_['logged once'] and r_['held once'])
        u4_ok = {k: u4_good(k[0], STUCK5[k[1]], v) for k, v in u4.items()}
        # U5: the mailbox not answering at all: one request in a pass, whatever is waiting, then all delivered
        courier.DEADLINE = 0.3
        u5 = {}
        for n_wait in (1, 10):
            w_ = S.World(name='courier-u5'); att = []
            for i in range(n_wait):
                w_.effect(att, f'f-{i:02d}', S.FAIL)
            orig = w_.urlopen
            def silent_box(req, timeout=None, context=None, orig=orig, w_=w_):
                if req.full_url.startswith('https://m') and w_.cfg.get('box_silent'):
                    w_.events.append(('box asked', req.full_url[9:16])); time.sleep(courier.DEADLINE * 2); raise urllib.error.URLError(OSError('timed out'))
                return orig(req, timeout, context)
            w_.urlopen = silent_box; w_.cfg['box_silent'] = True
            step(w_.run, t0)
            w_.effect(att, 'g-new', S.FAIL)
            m0 = len(w_.events); t_5 = time.monotonic(); s_ = step(w_.run, t0 + 10); took5 = time.monotonic() - t_5
            asked5 = sum(1 for x in w_.events[m0:] if x[0] == 'box asked')
            w_.cfg['box_silent'] = False; s2_ = step(w_.run, t0 + 20)
            u5[n_wait] = {'asked': asked5, 'took': round(took5, 2), 'waiting': len(s_.get('waiting', [])) if isinstance(s_, dict) else s_, 'mailbox listed': len(s_.get('mailbox', [])) if isinstance(s_, dict) else s_,
                          'then delivered': sorted(x['aid'] for x in s2_.get('delivered', [])) if isinstance(s2_, dict) else s2_, 'then waiting': len(w_.state().get('outbox', []))}
        # U6: an entry of the wrong shape in the chain, in the last decision or an earlier one
        OTHER6 = 'REQ-V/1/' + 'ef' * 16
        u6 = {}
        for name6, entry6 in (('a name that is not text', [7, 'verify:7', 'INDETERMINATE', 'n7', True, True]), ('too short', ['z-short', 'verify:z', 'EFFECT', 'nz']),
                              ('not a list', 'z-text'), ('a phase that is not text', ['z-phase', 'verify:z', 5, 'nz', True, True])):
            for where6 in ('in the last decision', 'in an earlier decision'):
                w_ = S.World(name='courier-u6', roots=(S.ROOT, OTHER6), empty_roots=(OTHER6,)); att = []
                w_.effect(att, 'a-fail', S.FAIL); step(w_.run, t0)
                raw_row(w_, [list(a) for a in att] + [entry6])
                if where6 == 'in an earlier decision':
                    w_.effect(att, 'b-later-fail', S.FAIL)
                s_ = step(w_.run, t0 + 10); s2_ = step(w_.run, t0 + 20)
                u6[(name6, where6)] = {'own state': s_.get('own_state') if isinstance(s_, dict) else s_, 'malformed': courier.state_problem(w_.state()),
                                       'stopped': bool(w_.state().get('stopped')), 'alarm': [o for a, o in w_.held() if o == 'COURIER_STOPPED'], 'refused': [x.get('root') for x in s_.get('refused', [])] if isinstance(s_, dict) else s_,
                                       'kept': [a[0] for a in w_.state().get('attempts', [])], 'other read': (bud5(w_, OTHER6).get('coverage') or '')[:9],
                                       'second pass own state': s2_.get('own_state') if isinstance(s2_, dict) else s2_, 'no later notice': ('b-later-fail', 'FAIL') not in w_.held()}
        # U6, at the witness: POST /accept with a run's name that is not text (the real handler; a Store with no database, so that
        # reaching the database is seen, and refused)
        from http.server import ThreadingHTTPServer as _THS
        from plea_gateway import witness_service as _WS, store as _ST, plea_budget_ref as _ref
        from plea_gateway.receipts import Signer as _Signer
        class _NoDB(_ST.Store):
            def __init__(self):
                self.mode = 'read committed'; self.reached = []
            def connect(self):
                self.reached.append('connect'); raise RuntimeError('no database here')
            def state(self, root_):
                self.reached.append('state'); return _ref.RootState(100, 0), 0, 'h'
        nodb = _NoDB(); H6 = _WS.make_handler(nodb, _Signer(), (), False); H6.peer_allowed = lambda self: True; H6.peer_name = None
        srv6 = _THS(('127.0.0.1', 0), H6); threading.Thread(target=srv6.serve_forever, daemon=True).start()
        accept6 = {}
        try:
            for op6 in ('ACCEPT_RESERVATION', 'ACCEPT_INTENT', 'CROSS', 'RELEASE', 'RECONCILE'):
                for k6, v6 in (('a number', 7), ('null', None), ('true', True), ('a list', ['a']), ('an object', {'a': 1})):
                    nodb.reached.clear()
                    req6 = urllib.request.Request(f'http://127.0.0.1:{srv6.server_address[1]}/accept', data=json.dumps({'root': S.ROOT, 'op': [op6, v6], 'evidence': None}).encode(), method='POST')
                    try:
                        with urllib.request.urlopen(req6, timeout=10) as r6:
                            got6 = r6.status
                    except urllib.error.HTTPError as exc6:
                        got6 = exc6.code
                    except Exception as exc6:
                        got6 = type(exc6).__name__
                    accept6[(op6, k6)] = (got6, 'connect' in nodb.reached)
        finally:
            srv6.shutdown(); srv6.server_close()
        # U7: an answer nested too deeply, at the checkpoint, the chain and a run; a fault planted in the courier itself
        courier.DEADLINE = 1.0
        DEEP = b'[' * 200000 + b']' * 200000
        u7 = {}
        for at7 in ('/checkpoint', '/chain', '/run'):
            w_ = S.World(name='courier-u7', stall_after=100); att = []
            w_.effect(att, 'a-fail', S.FAIL); step(w_.run, t0)
            w_.effect(att, 'b-deep', S.FAIL); w_.effect(att, 'c-fail', S.FAIL)
            orig = w_.urlopen
            def deep(req, timeout=None, context=None, orig=orig, at7=at7, w_=w_):
                u_ = urllib.parse.urlsplit(req.full_url)
                if u_.netloc == 'w' and u_.path == at7 and (at7 != '/run' or 'aid=b-deep' in u_.query):
                    return S.Answer(200, DEEP, w_)
                return orig(req, timeout, context)
            w_.urlopen = deep
            p1 = step(w_.run, t0 + 10); st1 = bud5(w_); p2 = step(w_.run, t0 + 200); st2 = bud5(w_)
            u7[at7] = {'made': (made(p1), made(p2)), 'unread': (unread(p1), unread(p2)), 'blocked': [len(x.get('blocked', [])) if isinstance(x, dict) else x for x in (p1, p2)],
                       'ended': ((st1.get('last pass') or {}).get('ended'), (st2.get('last pass') or {}).get('ended')), 'coverage': st2.get('coverage', ''),
                       'why': [x.get('why', '')[:80] for x in (p1.get('unreachable', []) if isinstance(p1, dict) else [])] + [x.get('why', '')[:80] for x in (p1.get('unread', []) if isinstance(p1, dict) else [])]}
        OTHER7 = 'REQ-W/1/' + '12' * 16
        w_u7f = S.World(name='courier-u7', stall_after=100, roots=(S.ROOT, OTHER7), empty_roots=(OTHER7,)); att = []
        w_u7f.effect(att, 'a-fail', S.FAIL); step(w_u7f.run, t0); w_u7f.effect(att, 'b-fail', S.FAIL)
        saved_lines = courier.lines
        def planted(todo, *a, **k):
            if todo:
                raise RuntimeError('a fault planted in the courier')
            return saved_lines(todo, *a, **k)
        try:
            courier.lines = planted
            f1 = step(w_u7f.run, t0 + 10); fs1 = bud5(w_u7f); f2 = step(w_u7f.run, t0 + 200); fs2 = bud5(w_u7f); fo = bud5(w_u7f, OTHER7)
        finally:
            courier.lines = saved_lines
        f3 = step(w_u7f.run, t0 + 300); fs3 = bud5(w_u7f)
        alarms7 = [x['notice'] for x in w_u7f.held_items() if x['notice'].get('outcome') == 'COURIER_FAILED']
        u7f = {'made': (made(f1), made(f2), made(f3)), 'failed': [len(x.get('courier_failed', [])) if isinstance(x, dict) else x for x in (f1, f2, f3)],
               'unreachable': [x.get('unreachable') if isinstance(x, dict) else x for x in (f1, f2)], 'refused': [x.get('refused') if isinstance(x, dict) else x for x in (f1, f2)],
               'ended': [(x.get('last pass') or {}).get('ended') for x in (fs1, fs2, fs3)], 'courier': fs2.get('courier', ''), 'coverage': (fs2.get('coverage', ''), fs3.get('coverage', '')),
               'other': (fo.get('last pass') or {}).get('ended'), 'exit': [courier.failed(x) if isinstance(x, dict) else x for x in (f1, f2, f3)],
               'words': [n_['text'].split('\n')[:3] for n_ in alarms7], 'checked': [C.notice_problems(n_, [w_u7f.ckey.public_hex]) for n_ in alarms7]}
        # U8: after each way a pass can end, the status says that way and no other
        courier.DEADLINE = 0.3
        u8 = {}
        for end8 in ('read whole', 'read, runs put off', 'the witness could not be reached', 'what the witness said cannot be believed', 'the courier itself failed'):
            w_ = S.World(name='courier-u8', stall_after=100); w_.hang = 1.0; att = []
            w_.effect(att, 'a-fail', S.FAIL)
            for i in range(2):
                att.append([f'h-{i}', f'verify:h{i}', 'CONSUMED', f'nh{i}', True, True]); w_.decide(att, ('X', f'h-{i}'))
            step(w_.run, t0)                                                                       # a whole pass: CONFIRMED
            if end8 == 'read, runs put off':
                w_.trouble.update({'h-0': 'hangs', 'h-1': 'hangs'}); w_.cfg['pass_seconds'] = 0.1
            elif end8 == 'the witness could not be reached':
                w_.down = True
            elif end8 == 'what the witness said cannot be believed':
                raw_row(w_, [list(a) for a in att] + [[7, 'verify:7', 'INDETERMINATE', 'n7', True, True]])
            saved_floor = courier.floor_of
            try:
                if end8 == 'the courier itself failed':
                    courier.floor_of = lambda *a: (_ for _ in ()).throw(KeyError('planted'))
                s_ = step(w_.run, t0 + 10)
            finally:
                courier.floor_of = saved_floor
            b_ = bud5(w_)
            u8[end8] = {'ended': (b_.get('last pass') or {}).get('ended'), 'how': (b_.get('last pass') or {}).get('how', ''), 'coverage': b_.get('coverage', ''), 'courier': b_.get('courier', ''),
                        'exit': courier.failed(s_) if isinstance(s_, dict) else s_}
        # A: the shares (the new line has half while the old holds runs), and runs that need no request never take a line's floor
        courier.DEADLINE = 0.1
        w_sh = S.World(name='courier-u1', stall_after=10_000); w_sh.hang = 0.3; w_sh.cfg['pass_seconds'] = 60.0; att = []
        for i in range(2):
            att.append([f'a-old-{i}', f'verify:a{i}', 'CONSUMED', f'na{i}', True, True]); w_sh.decide(att, ('X', f'a-old-{i}'))
        step(w_sh.run, t0); w_sh.cfg['pass_seconds'] = 0.8
        for i in range(10):
            att.append([f'n-{i:02d}', f'verify:n{i}', 'CONSUMED', f'nn{i}', True, True]); w_sh.decide(att, ('X', f'n-{i:02d}')); w_sh.trouble[f'n-{i:02d}'] = 'hangs'
        step(w_sh.run, t0 + 10); shares = bud5(w_sh).get('lines')
        w_nr = S.World(name='courier-u1', stall_after=0); att = []
        att.append(['a-intent', 'verify:a', 'INTENT_PENDING', 'na', True, False]); w_nr.decide(att, ('X', 'a-intent'))
        att.append(['b-run', 'verify:b', 'CONSUMED', 'nb', True, True]); w_nr.decide(att, ('X', 'b-run'))
        w_nr.cfg['pass_seconds'] = 0.0; s_nr = step(w_nr.run, t0)
        no_request = (made(s_nr), [x.get('aid') for x in s_nr.get('put_off_runs', [])] if isinstance(s_nr, dict) else s_nr, bud5(w_nr).get('lines'))
        # B: a mailbox that answers with a key not given; the one tried longest ago first, when the mailbox drops out after one notice
        courier.DEADLINE = 0.3
        w_k = S.World(name='courier-u4'); att = []
        w_k.effect(att, 'a-fail', S.FAIL); w_k.cfg['watches'][0]['mailbox_keys'] = [S.M.MailboxKey().public_hex]
        s_k = step(w_k.run, t0)
        wrong_key = ([x.get('why', '')[:120] for x in s_k.get('mailbox', [])] if isinstance(s_k, dict) else s_k, s_k.get('undelivered') if isinstance(s_k, dict) else s_k,
                     len(w_k.held_items()), sorted(r_['notice'].get('outcome') for r_ in w_k.state().get('outbox', [])))
        w_o = S.World(name='courier-u4'); att = []
        for aid in ('p-0', 'p-1', 'p-2'):
            w_o.effect(att, aid, S.FAIL)
        w_o.mailbox_up = False; step(w_o.run, t0); w_o.mailbox_up = True
        orig_o = w_o.urlopen; flap = {'down': False}
        def flapping(req, timeout=None, context=None):
            if req.full_url.startswith('https://m/pubkey') and flap['down']:
                flap['down'] = False; raise urllib.error.URLError(ConnectionRefusedError(111, 'refused'))
            if req.full_url.startswith('https://m/deliver') and b'"p-0"' in (req.data or b''):
                flap['down'] = True; raise http.client.RemoteDisconnected('closed')       # after p-0, the mailbox is gone for one request
            return orig_o(req, timeout, context)
        w_o.urlopen = flapping
        oldest = [sorted(x['aid'] for x in (step(w_o.run, t0 + 10 * k) or {}).get('delivered', [])) for k in (1, 2, 3)]
        # sixth form (K1 to K7): faults planted where something is at stake
        courier.DEADLINE = 0.3
        saved_make, saved_append, saved_dd = courier.make_notice, courier._append, courier.delivered_digests
        def plant_make(when):                                                                  # make_notice raises once, for the notice `when` picks
            armed = {'n': 1}
            def planted(cfg, key, root, attempt, outcome, *a, **k):
                if armed['n'] and when(attempt, outcome):
                    armed['n'] -= 1; raise KeyError('planted in make_notice')
                return saved_make(cfg, key, root, attempt, outcome, *a, **k)
            courier.make_notice = planted
        k1 = {}
        try:
            # K1: a run's FAIL
            w_ = S.World(name='courier-k1'); att = []
            w_.effect(att, 'run-a', S.FAIL); w_.effect(att, 'run-b', S.FAIL)
            plant_make(lambda a, o: a and a[0] == 'run-a' and o == 'FAIL')
            p1 = step(w_.run, t0); st1 = w_.state(); p2 = step(w_.run, t0 + 10); st2 = w_.state()
            k1['FAIL'] = (courier.failed(p1) if isinstance(p1, dict) else p1, 'run-a' in st1.get('final', []), 'run-a|FAIL' in st1.get('sent', []), made(p2), 'run-a' in st2.get('final', []))
            k1['FAIL p1'] = made(p1)
            # K1: WATCHING
            w_ = S.World(name='courier-k1'); att = []; w_.effect(att, 'run-a', S.FAIL)
            plant_make(lambda a, o: o == C.WATCHING)
            p1 = step(w_.run, t0); st1 = w_.state(); p2 = step(w_.run, t0 + 10)
            k1['WATCHING'] = (st1.get('watching'), st1['last_pass']['ended'], [o for _, o in w_.held() if o == 'WATCHING'])
            # K1: UNREADABLE
            w_ = S.World(name='courier-k1', stall_after=0); att = []; w_.effect(att, 'run-u', S.FAIL); w_.trouble['run-u'] = 'dropped'
            plant_make(lambda a, o: o == 'UNREADABLE')
            p1 = step(w_.run, t0); st1 = w_.state(); p2 = step(w_.run, t0 + 10)
            k1['UNREADABLE'] = ('run-u|UNREADABLE' in st1.get('sent', []), made(p2))
            # K1, K2: each alarm; the budget is never left marked with no alarm
            w_ = S.World(name='courier-k1'); att = []; w_.effect(att, 'run-a', S.PASS); step(w_.run, t0)
            w_.rows.pop()                                                                        # a rollback: Refused
            plant_make(lambda a, o: o == 'COURIER_STOPPED')
            p1 = step(w_.run, t0 + 10); st1 = w_.state(); p2 = step(w_.run, t0 + 20); st2 = w_.state()
            k1['COURIER_STOPPED'] = (st1.get('stopped'), st1['last_pass']['ended'], made(p2), bool(st2.get('stopped')))
            w_ = S.World(name='courier-k1', stall_after=0); att = []; w_.effect(att, 'run-a', S.PASS); step(w_.run, t0); w_.down = True
            plant_make(lambda a, o: o == 'COURIER_BLOCKED')
            p1 = step(w_.run, t0 + 10); st1 = w_.state(); p2 = step(w_.run, t0 + 20); st2 = w_.state()
            k1['COURIER_BLOCKED'] = (st1.get('blocked_sent'), st1['last_pass']['ended'], made(p2), st2.get('blocked_sent'))
            w_ = S.World(name='courier-k1', stall_after=0); att = []; w_.effect(att, 'run-a', S.PASS); step(w_.run, t0); w_.effect(att, 'run-b', S.FAIL)
            saved_lines = courier.lines
            courier.lines = lambda todo, *a, **k: (_ for _ in ()).throw(RuntimeError('a fault planted in the courier')) if todo else saved_lines(todo, *a, **k)
            try:
                plant_make(lambda a, o: o == 'COURIER_FAILED')
                p1 = step(w_.run, t0 + 10); st1 = w_.state(); p2 = step(w_.run, t0 + 20); st2 = w_.state()
            finally:
                courier.lines = saved_lines
            k1['COURIER_FAILED'] = (st1.get('failed_sent'), st1['last_pass']['ended'], 'its alarm could not be made either' in st1['last_pass']['why'], made(p2), st2.get('failed_sent'))
        finally:
            courier.make_notice = saved_make
        # K2: a fault while refused.jsonl is written
        w_ = S.World(name='courier-k2'); att = []; w_.effect(att, 'run-a', S.PASS); step(w_.run, t0); w_.rows.pop()
        armed2 = {'n': 1}
        def append_once(path, obj):
            if pathlib.Path(path).name == 'refused.jsonl' and armed2['n']:
                armed2['n'] -= 1; raise OSError(28, 'No space left on device')
            return saved_append(path, obj)
        try:
            courier._append = append_once
            p1 = step(w_.run, t0 + 10); st1 = w_.state(); p2 = step(w_.run, t0 + 20); st2 = w_.state()
        finally:
            courier._append = saved_append
        ref_lines = (w_.tmp / 'state' / 'refused.jsonl').read_text().splitlines() if (w_.tmp / 'state' / 'refused.jsonl').exists() else []
        k2 = (made(p1), bool(st1.get('stopped')), st1['last_pass']['ended'], isinstance(st1.get('refusal_unwritten'), dict), len(ref_lines), 'refusal_unwritten' in st2,
              st1['last_pass']['why'], st1.get('unfinished_since'), [x.get('why', '') for x in p1.get('courier_failed', [])] if isinstance(p1, dict) else p1)
        # K3: a fault in the sending code, and a log of deliveries that is not UTF-8
        w_ = S.World(name='courier-k3'); att = []; w_.effect(att, 'run-a', S.PASS); step(w_.run, t0); w_.effect(att, 'run-b', S.FAIL)
        try:
            courier.delivered_digests = lambda *a, **k: (_ for _ in ()).throw(UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'planted'))
            for k_ in range(3):
                step(w_.run, t0 + 10 + k_)
            st3, b3 = w_.state(), bud5(w_)
        finally:
            courier.delivered_digests = saved_dd
        step(w_.run, t0 + 20); st3b, b3b = w_.state(), bud5(w_)
        w_ = S.World(name='courier-k3'); att = []; w_.effect(att, 'run-a', S.PASS); step(w_.run, t0)
        with open(w_.tmp / 'state' / 'deliveries.jsonl', 'ab') as f_:
            f_.write(b'\xff\xfe not utf-8\n')
        w_.effect(att, 'run-b', S.FAIL); p3 = step(w_.run, t0 + 10); st3c = step(w_.status)
        k3 = {'send fault': ((st3.get('send_fault') or {}).get('passes'), b3.get('coverage', ''), b3.get('courier', ''), [x.get('kind') for x in b3.get('notices not delivered') or []]),
              'cleared': ('send_fault' in st3b, b3b.get('coverage', ''), [x['notice'].get('aid') for x in (lambda r_: r_ if isinstance(r_, list) else [])(step(courier.read_deliveries, w_.tmp / 'state' / 'deliveries.jsonl'))]),
              'log not UTF-8': ([x.get('why', '')[:60] for x in p3.get('courier_failed', [])] if isinstance(p3, dict) else p3, made(p3),
                                ((st3c or {}).get('budgets', {}).get(S.ROOT, {}) if isinstance(st3c, dict) else {'raised': st3c}).get('log of deliveries'))}
        # K4: the mailbox down over several passes
        w_ = S.World(name='courier-k4'); att = []; w_.effect(att, 'run-a', S.PASS); step(w_.run, t0); w_.effect(att, 'run-b', S.FAIL); w_.mailbox_up = False
        for c_ in (t0 + 1000, t0 + 90000, t0 + 400000):
            step(w_.run, c_)
        b4 = bud5(w_)
        k4 = (b4.get('coverage', ''), b4.get('notices not delivered'), b4.get('mailbox'))
        # K5, L4: a RecursionError or MemoryError while an answer's data is verified or worked out is an answer the courier could not
        # handle; one elsewhere in the courier's own code is an error it did not expect (seventh form: faults planted, not depths)
        saved_cpp, saved_ro = C.checkpoint_problems, C.run_outcome
        w_ = S.World(name='courier-k5', stall_after=0); att = []; w_.effect(att, 'a', S.PASS); step(w_.run, t0)
        try:
            C.checkpoint_problems = lambda *a, **k: (_ for _ in ()).throw(RecursionError('planted while the checkpoint is verified'))
            p5 = step(w_.run, t0 + 10); st5 = w_.state()
        finally:
            C.checkpoint_problems = saved_cpp
        w_ = S.World(name='courier-k5', stall_after=0); att = []
        w_.effect(att, 'run-deep', S.FAIL); w_.effect(att, 'run-b', S.FAIL)
        try:
            C.run_outcome = lambda phase, ev, res, gk, root_, aid_, nonce_: (_ for _ in ()).throw(MemoryError()) if aid_ == 'run-deep' else saved_ro(phase, ev, res, gk, root_, aid_, nonce_)
            p5b = step(w_.run, t0)
        finally:
            C.run_outcome = saved_ro
        unr5 = [x['notice']['text'].split('\n')[2] for x in w_.held_items() if x['notice'].get('outcome') == 'UNREADABLE']
        w_ = S.World(name='courier-k5', stall_after=0); att = []                                   # a run whose outcome the chain alone says (no request)
        att.append(['n-intent', 'verify:n', 'INTENT_PENDING', 'nn', True, False]); w_.decide(att, ('X', 'n-intent')); w_.effect(att, 'run-b', S.FAIL)
        try:
            C.run_outcome = lambda phase, ev, res, gk, root_, aid_, nonce_: (_ for _ in ()).throw(MemoryError()) if aid_ == 'n-intent' else saved_ro(phase, ev, res, gk, root_, aid_, nonce_)
            p5d = step(w_.run, t0)
        finally:
            C.run_outcome = saved_ro
        no_req5 = ([x.get('why', '') for x in p5d.get('unread', [])] if isinstance(p5d, dict) else p5d, made(p5d))
        w_ = S.World(name='courier-k5', stall_after=0); att = []; w_.effect(att, 'a', S.PASS); step(w_.run, t0); w_.effect(att, 'b', S.FAIL)
        saved_lines = courier.lines
        try:
            courier.lines = lambda *a, **k: (_ for _ in ()).throw(RecursionError('planted in the courier\'s own code'))
            p5c = step(w_.run, t0 + 10); st5c = w_.state()
        finally:
            courier.lines = saved_lines
        k5 = (st5['last_pass']['ended'], st5['last_pass']['why'], made(p5), unread(p5b), made(p5b), p5b.get('courier_failed') if isinstance(p5b, dict) else p5b,
              [x.get('why', '') for x in p5.get('unreachable', [])] if isinstance(p5, dict) else p5, [x.get('why', '') for x in p5b.get('unread', [])] if isinstance(p5b, dict) else p5b,
              st5c['last_pass']['ended'], unr5, no_req5)
        # K6: a pass in which a run could not be read
        w_ = S.World(name='courier-k6'); att = []; w_.effect(att, 'a', S.PASS); step(w_.run, t0)
        w_.effect(att, 'b-unreadable', S.FAIL); w_.trouble['b-unreadable'] = 'dropped'; step(w_.run, t0 + 10); b6 = bud5(w_)
        k6 = ((b6.get('last pass') or {}).get('how'), b6.get('coverage', ''))
        # K7: a pass that ends before the old line; one time since no pass was completed, whatever ended them
        w_ = S.World(name='courier-k7', stall_after=100); att = []
        att.append(['a-old', 'verify:a', 'CONSUMED', 'na', True, True]); w_.decide(att, ('X', 'a-old')); step(w_.run, t0)
        w_.effect(att, 'k-new', S.FAIL); w_.trouble['k-new'] = 'knocks'
        step(w_.run, t0 + 10); b7 = bud5(w_)
        w_.trouble.pop('k-new'); w_.down = True; step(w_.run, t0 + 20)                           # blocked, then an error the courier did not expect
        saved_lines = courier.lines
        try:
            w_.down = False
            courier.lines = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('planted'))
            p7 = step(w_.run, t0 + 150)
        finally:
            courier.lines = saved_lines
        alarms7b = [x['notice']['text'].split('\n')[2] for x in w_.held_items() if x['notice'].get('outcome') in ('COURIER_FAILED', 'COURIER_BLOCKED')]
        saved_rd = courier.read_deliveries
        try:
            courier.read_deliveries = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('planted in read_deliveries'))
            st7 = step(courier.status, w_.cfg)
        finally:
            courier.read_deliveries = saved_rd
        k7 = ((b7.get('lines') or {}).get('the last pass'), (b7.get('lines') or {}).get('the new line', ''), (b7.get('lines') or {}).get('a run of the old line is asked for at least once in every'),
              alarms7b, made(p7), st7 if not isinstance(st7, dict) else st7.get('budgets', {}).get(S.ROOT, {}).get('state', ''))
        # the pinning of receipts: a mailbox that gives the key it was given at /pubkey and signs its receipts with another key
        w_ = S.World(name='courier-pin'); att = []; w_.effect(att, 'run-a', S.FAIL)
        other_key = S.M.MailboxKey(); take_p = w_.box.take
        def take_other(n_):
            status_, rc_ = take_p(n_)
            body_ = {k: rc_.get(k) for k in C.RECEIPT_FIELDS}
            return status_, dict(body_, signer=other_key.public_hex, signature=other_key.sign(C.canonical(body_).encode()))
        w_.box.take = take_other; s_pin = step(w_.run, t0)
        pin = (s_pin.get('delivered') if isinstance(s_pin, dict) else s_pin, sorted({x.get('kind') for x in s_pin.get('undelivered', [])}) if isinstance(s_pin, dict) else s_pin,
               s_pin.get('mailbox') if isinstance(s_pin, dict) else s_pin, len(w_.state().get('outbox', [])))
        e['sixth form'] = {'K1': k1, 'K2': k2, 'K3': k3, 'K4': k4, 'K5': k5, 'K6': k6, 'K7': k7, 'receipts pinned': pin}
        # seventh form (L1 to L7)
        # L2: the state's write failing once at each call of a pass in turn, and from each call to the end of the pass
        saved_ww = courier._write_whole
        l2 = {}
        for mode_ in ('once', 'rest'):
            for k_ in range(1, 40):
                w_ = S.World(name='courier-l2'); att = []
                w_.effect(att, 'run-a', S.FAIL); w_.effect(att, 'run-b', S.FAIL); w_.effect(att, 'run-c', S.PASS)
                calls_ = {'n': 0, 'armed': True}
                def planted_ww(path, data, calls_=calls_, k_=k_, mode_=mode_):
                    if path.name == 'state.json' and calls_['armed']:
                        calls_['n'] += 1
                        if (mode_ == 'once' and calls_['n'] == k_) or (mode_ == 'rest' and calls_['n'] >= k_):
                            raise OSError(28, 'No space left on device (planted)')
                    return saved_ww(path, data)
                try:
                    courier._write_whole = planted_ww
                    p1_ = step(w_.run, t0); calls_['armed'] = False
                finally:
                    courier._write_whole = saved_ww
                if k_ > calls_['n']:                                                     # past the last write of the pass: no fault was planted
                    break
                p2_ = step(w_.run, t0 + 10); p3_ = step(w_.run, t0 + 20)
                held_ = [(x['notice']['aid'], x['notice']['outcome']) for x in w_.held_items()]
                l2[(mode_, k_)] = {'raised': not isinstance(p1_, dict), 'saved_not': len(p1_.get('state_not_saved', [])) if isinstance(p1_, dict) else None,
                                   'failed': courier.failed(p1_) if isinstance(p1_, dict) else None,
                                   'held': sorted(held_), 'twice': sorted({h for h in held_ if held_.count(h) > 1})}
        want_l2 = [('', 'WATCHING'), ('run-a', 'FAIL'), ('run-b', 'FAIL')]
        # L3: an error of the courier's own while one run is read
        w_ = S.World(name='courier-l3', stall_after=0); att = []; w_.effect(att, 'run-a', S.FAIL); w_.effect(att, 'run-b', S.FAIL)
        try:
            C.run_outcome = lambda phase, ev, res, gk, root_, aid_, nonce_: (_ for _ in ()).throw(TypeError("unhashable type: 'list'")) if aid_ == 'run-a' else saved_ro(phase, ev, res, gk, root_, aid_, nonce_)
            p3l = step(w_.run, t0)
        finally:
            C.run_outcome = saved_ro
        l3 = (made(p3l), [x.get('why', '') for x in p3l.get('unread', [])] if isinstance(p3l, dict) else p3l, [(x.get('aid'), x.get('why', '')[:80]) for x in p3l.get('courier_failed', [])] if isinstance(p3l, dict) else p3l,
              [x['notice']['text'].split('\n')[2] for x in w_.held_items() if x['notice'].get('outcome') == 'UNREADABLE'])
        # L5: a fault, every time, while one run's notice is made
        w_ = S.World(name='courier-l5', stall_after=100); att = []
        for aid in ('run-a', 'run-b', 'run-c'):
            w_.effect(att, aid, S.FAIL)
        def planted_l5(cfg_, key_, root_, attempt, outcome, *a, **k):
            if attempt and attempt[0] == 'run-a' and outcome == 'FAIL':
                raise TypeError("planted in making run-a's notice")
            return saved_make(cfg_, key_, root_, attempt, outcome, *a, **k)
        l5p = []
        try:
            courier.make_notice = planted_l5
            for c_ in (t0, t0 + 50, t0 + 150, t0 + 160):
                s_ = step(w_.run, c_); st_ = w_.state()
                l5p.append({'made': made(s_), 'exit': courier.failed(s_) if isinstance(s_, dict) else s_, 'how': st_['last_pass']['why'], 'final': sorted(st_.get('final', [])),
                            'named': [x.get('aid') for x in s_.get('courier_failed', [])] if isinstance(s_, dict) else s_})
            b5 = bud5(w_)
        finally:
            courier.make_notice = saved_make
        l5_words = [x['notice']['text'].split('\n')[2] for x in w_.held_items() if x['notice'].get('outcome') == 'COURIER_FAILED']
        l5 = (l5p, b5.get('notices the courier could not make'), b5.get('coverage', ''), l5_words)
        # L6: the state cannot be saved, from some call to the end of the pass, with a second budget
        OTHER_L6 = 'REQ-V/1/' + 'ef' * 16
        w_ = S.World(name='courier-l6', roots=(S.ROOT, OTHER_L6), empty_roots=(OTHER_L6,)); att = []; w_.effect(att, 'run-a', S.FAIL)
        try:
            courier._write_whole = lambda path, data: (_ for _ in ()).throw(OSError(28, 'planted')) if path.name == 'state.json' else saved_ww(path, data)
            p6l = step(w_.run, t0)
        finally:
            courier._write_whole = saved_ww
        p6l2 = step(w_.run, t0 + 10)
        l6 = (not isinstance(p6l, dict), sorted(x.get('root') for x in p6l.get('state_not_saved', [])) if isinstance(p6l, dict) else p6l, courier.failed(p6l) if isinstance(p6l, dict) else None,
              len(w_.held_items()), sorted((a, o) for a, o in w_.held()))
        # L7: small things
        w_ = S.World(name='courier-l7'); att = []; w_.effect(att, 'run-a', S.FAIL)
        mailbox_before = bud5(w_).get('mailbox')
        step(w_.run, t0); mailbox_after = bud5(w_).get('mailbox')
        with open(w_.tmp / 'state' / 'deliveries.jsonl', 'ab') as f_:
            f_.write(b'{"torn": ')                                                                # a line left unfinished
        w_.effect(att, 'run-b', S.FAIL); step(w_.run, t0 + 10)
        log_lines = (w_.tmp / 'state' / 'deliveries.jsonl').read_bytes().split(b'\n')
        probs7 = []; logged7 = [d['notice'].get('aid') for d in courier.read_deliveries(w_.tmp / 'state' / 'deliveries.jsonl', problems=probs7)]
        w_ = S.World(name='courier-l7'); att = []; w_.effect(att, 'run-a', S.PASS); step(w_.run, t0); w_.rows.pop()
        try:
            courier._append = append_once; armed2['n'] = 1
            step(w_.run, t0 + 10)
        finally:
            courier._append = saved_append
        unwritten7 = isinstance(w_.state().get('refusal_unwritten'), dict)
        step(courier.resume, w_.cfg, S.ROOT)
        ref7 = (w_.tmp / 'state' / 'refused.jsonl').read_text().splitlines() if (w_.tmp / 'state' / 'refused.jsonl').exists() else []
        l7 = (mailbox_before, mailbox_after, sum(1 for l_ in log_lines if l_.startswith(b'{"torn": {')), logged7, probs7, unwritten7, len(ref7), 'refusal_unwritten' in w_.state())
        e['seventh form'] = {'L2': {f'{k[0]} {k[1]}': v for k, v in l2.items()}, 'L3': l3, 'L5': l5, 'L6': l6, 'L7': l7}
    finally:
        courier.DEADLINE = old_deadline
    # the state the fourth form (769f6e4) wrote, read by this one (tests/r30_states_769f6e4.json, made by that courier)
    olds = json.loads((GATEWAY / 'tests' / 'r30_states_769f6e4.json').read_text())
    old5 = {}
    for name_o, fx in olds.items():
        w_ = S.World(name=fx['name'], stall_after=fx['stall_after'], keys=fx['keys'])
        w_.rows, w_.runs = fx['rows'], fx['runs']
        (w_.tmp / 'state').mkdir(parents=True, exist_ok=True)
        (w_.tmp / 'state' / 'state.json').write_text(json.dumps(fx['state'])); (w_.tmp / 'state' / 'deliveries.jsonl').write_text(fx['deliveries'])
        before_o = step(w_.status)
        s_ = step(w_.run, t0 + 100); s2_ = step(w_.run, t0 + 200)
        b_o = (before_o or {}).get('budgets', {}).get(S.ROOT, {}) if isinstance(before_o, dict) else {'state': before_o}
        old5[name_o] = {'status before': (b_o.get('state'), b_o.get('coverage', '')[:40]),
                        'own state': [x.get('own_state') for x in (s_, s2_) if isinstance(x, dict)], 'upgraded': s_.get('state_upgraded') if isinstance(s_, dict) else s_,
                        'made': (made(s_), made(s2_)), 'delivered': sorted(x['aid'] for x in s_.get('delivered', [])) if isinstance(s_, dict) else s_,
                        'malformed': courier.state_problem(w_.state()), 'old fields': sorted(k for k in courier.OLD_FIELDS + ('pending',) if k in w_.state()),
                        'stopped': bool(w_.state().get('stopped')), 'refused': [x.get('why', '')[:100] for x in s_.get('refused', [])] if isinstance(s_, dict) else s_,
                        'coverage': bud5(w_).get('coverage', '')}
    e['fifth form'] = {'U1': (made(u1_first), u1, u1_y, u1_stated), 'U2': u2, 'U3': (made(u3_first), courier.failed(u3_first) if isinstance(u3_first, dict) else u3_first, u3_status.get('lines'), u3_watching,
                       made(u3b), [x.get('aid') for x in u3b.get('put_off_runs', [])] if isinstance(u3b, dict) else u3b),
                       'U4': {f'{k[0]}, {k[1]}': v for k, v in u4.items() if not u4_ok[k]} or 'every case as expected', 'U5': u5,
                       'U6': {f'{k[0]}, {k[1]}': v for k, v in u6.items()}, 'U6 accept': {f'{k[0]} {k[1]}': v for k, v in accept6.items()}, 'U7': u7, 'U7 fault': u7f, 'U8': u8, 'state of 769f6e4': old5}

    # ---------------------------------------------------------------- T4, T6 and T7 with the real deployment
    r = Run('R30'); here = OUT / 'R30'
    try:
        s = r.s; root = B.root_for(r.env['card']); url = f"https://127.0.0.1:{s.ports['witness']}"
        rows = lambda: len(Store(deploy.LOCAL_DSN).audit_snapshot(root)[0])
        def call(path, cert, method='GET', body=None):                                         # (status, answer), the answer read on an error too
            ctx = TLS.TLSClient(s.pki['ca'], *cert).context()
            req = urllib.request.Request(url + path, data=None if body is None else json.dumps(body).encode(), method=method, headers={'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                    return resp.status, json.loads(resp.read() or b'null')
            except urllib.error.HTTPError as exc:
                try:
                    return exc.code, json.loads(exc.read() or b'null')
                except ValueError:
                    return exc.code, None
            except (OSError, http.client.HTTPException, ValueError) as exc:
                return f'no answer: {type(exc).__name__}', None
        def resign(rec):
            body = {k: v for k, v in rec.items() if k != 'signature'}
            return dict(body, signature={'signer': s.engineer.public_hex, 'signature': s.engineer.sign(canonical(body).encode())})
        def signed(key, fields, body):
            return dict(body, signer=key.public_hex, signature=key.sign(C.canonical({k: body.get(k) for k in fields}).encode()))
        def save(name, obj):
            (here / name).write_text(json.dumps(obj)); return here / name
        keys = save('keys.json', s.keys)
        def cli(rec, *extra):
            p = subprocess.run([PY, '-B', str(GATEWAY / 'verify' / 'check_record.py'), str(save('rec.json', rec)), '--keys', str(keys), '--require-delivery', *extra], capture_output=True, text=True, timeout=120)
            return p.returncode, [l for l in p.stdout.splitlines() if l.startswith(('NOTICES', 'COURIER COVERAGE'))]
        def status_cli(name='courier'):
            p = subprocess.run([PY, '-B', str(GATEWAY / 'verify' / 'courier.py'), 'status', '--config', str(s.dir / f'{name}.json')], capture_output=True, text=True, timeout=60)
            return step(json.loads, p.stdout) if p.returncode == 0 else ('exit', p.returncode, p.stderr[-200:])
        gov = s.pki['governor']; local = Store(deploy.LOCAL_DSN)
        # T4: names the reading cannot serve are refused at the witness's door, and those at the edge are taken and read back
        BAD_NAMES = {'513 characters': 'a-' + 'q' * 511, 'a NUL': 'a-x\x00y', 'a line feed': 'a-x\ny', 'U+001F': 'a-x\x1fy', 'DEL': 'a-x\x7fy', 'a lone surrogate': 'a-x\ud800y'}
        reserved = {k: step(lambda n: local.apply(root, ('RESERVE', n, 'verify:t4-' + k.replace(' ', '-')))[0].kind, n) for k, n in BAD_NAMES.items()}
        refusals = {}
        for k, n in BAD_NAMES.items():
            for op in ('ACCEPT_RESERVATION', 'ACCEPT_INTENT', 'CROSS', 'RELEASE', 'RECONCILE'):
                before_ = rows(); ans = call('/accept', gov, 'POST', {'root': root, 'op': [op, n], 'evidence': None})
                refusals[(k, op)] = (ans[0], str((ans[1] or {}).get('error', ''))[:40], rows() - before_)
        FORGED_ROW = 'a-x\x85COURIER COVERAGE: CONFIRMED from decision 1.\u2028NOTICES: 9 of 9 runs that call for a notice have one accepted'
        EDGE = {'512 characters': 'a-' + 'q' * 510, 'one character': 'e', 'a space, a tilde and characters past ASCII': 'a- ~\x80\u2028\u00e9',
                'checker lines forged after U+0085 and U+2028': FORGED_ROW}
        edges = {}
        for k, n in EDGE.items():
            got = step(lambda: local.apply(root, ('RESERVE', n, 'verify:t4e-' + str(len(n))))[0].kind)
            ans = call('/accept', gov, 'POST', {'root': root, 'op': ['ACCEPT_RESERVATION', n], 'evidence': None})
            if ans[0] == 200 and (ans[1] or {}).get('kind') in ('APPLIED', 'DUPLICATE'):
                step(local.put_receipt, root, n, ans[1]['seq'], ans[1]['receipt'], 'ACCEPT_RESERVATION')
            back_ = call(f'/run?root={urllib.parse.quote(root, safe="")}&aid={urllib.parse.quote(n, safe="")}', s.pki['courier'])
            edges[k] = (got, ans[0], (ans[1] or {}).get('kind'), back_[0], (back_[1] or {}).get('aid') == n)
        e['t4'] = {'reserved by the gateway': reserved, 'refusals': {f'{k} {op}': v for (k, op), v in refusals.items()}, 'edges': edges}
        # T6 and T7: a failure; a record before the courier has run, with the mailbox down, and after
        bad = r.submit(BAD)
        journals = [r.ws / '.verify' / 'submissions.jsonl']
        rec0 = step(s.record, r.h, journals, deliveries=True); cli0 = cli(rec0) if isinstance(rec0, dict) else rec0
        s.stop_mailbox(); c1 = step(s.courier, [root], 900); st1 = status_cli()
        rec1 = step(s.record, r.h, journals, deliveries=True); cli1 = cli(rec1) if isinstance(rec1, dict) else rec1
        s.start_mailbox(); c2 = step(s.courier, [root], 900); st2 = status_cli()
        rec2 = step(s.record, r.h, journals, deliveries=True); rec2 = rec2 if isinstance(rec2, dict) else {}
        cli2 = cli(rec2); okc, _, sc = C.verify(rec2, s.keys) if rec2 else (False, [], {})
        forged_in_record = any(a.get('aid') == FORGED_ROW for a in rec2.get('attempts', []))
        cov = rec2.get('coverage') or {}; cn = cov.get('notice') or {}
        log_w = [d for d in courier.read_deliveries(s.dir / 'courier' / 'deliveries.jsonl', root) if d['notice'].get('outcome') == 'WATCHING']
        def receipt_for(n, key=None):
            body = {'statement': 'DELIVERED', 'notice': C.notice_digest(n), 'root': n.get('root'), 'aid': n.get('aid'), 'outcome': n.get('outcome'), 'mailbox': 'engineer-mailbox', 'time': n.get('time')}
            return signed(key or s.mailbox_key, C.RECEIPT_FIELDS, body)
        def watching_for(key=None, **change):
            body = dict({k: cn.get(k) for k in C.NOTICE_FIELDS_2}, **change)
            body['text'] = C.watching_text(body['root'], body['seq'], body['head'], body['courier'])
            return signed(key or s.courier_key, C.NOTICE_FIELDS_2, body)
        def with_coverage(c):
            x = copy.deepcopy(rec2)
            if c is None:
                x.pop('coverage', None)
            else:
                x['coverage'] = c
            return resign(x)
        import mailbox_service
        stranger = mailbox_service.MailboxKey()
        other_budget = watching_for(root=root + 'x'); not_in_chain = watching_for(head='1' * 64); strangers = watching_for(stranger)
        other_field = dict({k: cn.get(k) for k in C.NOTICE_FIELDS_2}, root=root + 'x'); other_field = signed(s.courier_key, C.NOTICE_FIELDS_2, other_field)   # words of this budget, field of another
        no_form = signed(s.courier_key, C.NOTICE_FIELDS, {k: cn.get(k) for k in C.NOTICE_FIELDS})
        variants6 = {'no statement': with_coverage(None), 'a statement for another budget': with_coverage({'notice': other_budget, 'receipt': receipt_for(other_budget)}),
                     'a statement whose budget field names another budget, its words this one': with_coverage({'notice': other_field, 'receipt': receipt_for(other_field)}),
                     'a statement without a receipt': with_coverage({'notice': cn, 'receipt': None}), 'a receipt signed by another key': with_coverage({'notice': cn, 'receipt': receipt_for(cn, stranger)}),
                     'a statement naming a decision not in the chain': with_coverage({'notice': not_in_chain, 'receipt': receipt_for(not_in_chain)}),
                     'a statement signed by another courier key': with_coverage({'notice': strangers, 'receipt': receipt_for(strangers)}),
                     'a statement of Amendment 11\'s form': with_coverage({'notice': no_form, 'receipt': receipt_for(no_form)})}
        judged6 = {k: ((C.verify(v, s.keys)[2].get('coverage') or {}).get('state'), cli(v)[0]) for k, v in variants6.items()}
        # a budget not in the courier's configuration: a second baseline of the requirement, alongside
        env2 = step(s.baseline, CASE, draft(), alongside_reason='R30: a budget the courier is not configured for')
        h2 = env2.get('baseline_sha256') if isinstance(env2, dict) else None
        root2 = B.root_for(env2['card']) if isinstance(env2, dict) else None
        rec_other = step(s.record, h2, (), deliveries=True) if h2 else env2
        cli_other = cli(rec_other) if isinstance(rec_other, dict) else rec_other
        # the courier blocked: its configuration given a witness that does not answer
        cfgb = json.loads(s.courier_config([root], 0, 'courierb').read_text()); cfgb['witness_url'] = 'https://127.0.0.1:8979'
        (s.dir / 'courierb.json').write_text(json.dumps(cfgb))
        pb = subprocess.run([PY, '-B', str(GATEWAY / 'verify' / 'courier.py'), 'run', '--config', str(s.dir / 'courierb.json')], capture_output=True, text=True, timeout=120)
        sum_b = step(json.loads, (pb.stdout.strip().splitlines() or ['{}'])[-1]); st_b = status_cli('courierb')
        helps = {name: subprocess.run([PY, '-B', str(GATEWAY / 'verify' / name), '--help'], capture_output=True, text=True, timeout=60).stdout
                 for name in ('courier.py', 'check_record.py', 'mailbox_service.py')}
        mailbox_words = [p.read_text() for p in sorted((s.dir / 'mailbox' / 'notices').glob('*.txt'))]
        b_of = lambda st_, rt: (st_ or {}).get('budgets', {}).get(rt, {}) if isinstance(st_, dict) else {}
        e['t6'] = {'record before the courier': cli0, 'record with the mailbox down': cli1, 'record after': cli2, 'statement seq': cn.get('seq'), 'logged statement seq': [d['notice'].get('seq') for d in log_w],
                   'status mailbox down': b_of(st1, root).get('coverage'), 'status after': b_of(st2, root).get('coverage'), 'variants': judged6,
                   'other budget': (root2 in (st2 or {}).get('budgets', {}) if isinstance(st2, dict) else st2, cli_other), 'courier runs': (c1[0] if isinstance(c1, tuple) else c1, c2[0] if isinstance(c2, tuple) else c2)}
        e['t7'] = {'status mailbox down': {k: v for k, v in b_of(st1, root).items() if k.startswith('notices')}, 'status after': {k: v for k, v in b_of(st2, root).items() if k.startswith('notices')},
                   'status blocked': b_of(st_b, root).get('courier'), 'summary blocked': (sum_b or {}).get('blocked') if isinstance(sum_b, dict) else sum_b,
                   'summary mailbox down': {k: (c1[1] or {}).get(k) for k in ('made', 'waiting', 'delivered', 'coverage')} if isinstance(c1, tuple) and isinstance(c1[1], dict) else c1}
        ALLOWED = ("not a person's acknowledgement", 'it does not say that anyone has read it', 'not that anyone has read it', 'nothing here shows that anyone read a notice')
        FORBIDDEN = re.compile(r"acknowledg|delivered to the engineer|read by|seen by|\b(engineer|person|someone|anyone|they|he|she)( has| have| had)? (read|seen)\b|has been read|was read|been seen", re.I)
        def says_no_person(text):
            text = re.sub(r'\s+', ' ', text.replace('\\n', ' '))                              # help is wrapped, and JSON writes line ends as \n
            for a in ALLOWED:
                text = text.replace(a, '')
            return FORBIDDEN.search(text) is None
        spoken = {'status': json.dumps([st1, st2, st_b]), 'summaries': json.dumps([c1[1] if isinstance(c1, tuple) else c1, c2[1] if isinstance(c2, tuple) else c2, sum_b]),
                  "checker's notices and coverage lines": json.dumps([cli0, cli1, cli2]), 'help': json.dumps(helps), 'notices': json.dumps(mailbox_words),
                  'stand-in status and summaries': json.dumps([cov1, cov2, stat3, p71, p72], default=str)}
        e['t7_words'] = {k: says_no_person(v) for k, v in spoken.items()}
    finally:
        r.stop()

    N = lambda c: (c or ['', ''])
    checks = {
        # T1
        'with one run made unreadable by an answer too long, a dropped connection, an answer that is not JSON, or a name the witness\'s reading refuses, and that run sorted first, between or last of two failed runs, the courier makes both FAIL notices in the same pass and the in-process mailbox accepts them; the unreadable run is listed as unread and not marked done, the failed runs are marked done, and no budget is reported unreachable or blocked':
            holds(lambda: len(t1_all) == 12 and all(t1_all.values())),
        'with three runs unreadable at once (an answer too long first, a refused name between, a dropped connection last), both failed runs still get their FAIL notices in that pass and all three are listed as unread':
            holds(lambda: t1_good(many, ['a-unread', 'c-un\x01read', 'e-unread'])),
        'when a run\'s reading fails as a transport fails, the courier asks the witness for one more checkpoint, and it asks none when the witness answered with a refusal; no answer is read past MAX_ANSWER + 1 bytes':
            holds(lambda: len(probes_ok) == 12 and all(probes_ok.values()) and many.get('probes') == 3 and reads_ok),
        'an answer that comes a byte at a time and would take 4 seconds is given up at the courier\'s deadline (made 1 second here), the run is listed as unread, and the other runs\' FAIL notices are made in the same pass':
            holds(lambda: made(sh) == [(a, 'FAIL') for a in FAILS] and unread(sh) == ['a-hangs'] and hang_seconds < 4.0),
        'a reader given up at the courier\'s deadline ends: over three passes of five answers that come a byte at a time for 30 seconds, no thread is left over after each pass, and every slow answer is closed':
            holds(lambda: extra_threads == [0, 0, 0] and len(closed) == 15),
        'a reader blocked inside one read ends when the courier closes the answer at its deadline, and a reader whose answer ignores being closed ends at its own deadline: no thread is left over either way':
            holds(lambda: lone == {'blocks': (0, 3), 'deaf': (0, 3)}),
        'a notice is sent as soon as it is made: the FAIL notice of a run read before four slow ones is in the stand-in mailbox before the first slow run is asked for, and so before the last slow answer ends':
            holds(lambda: take_at is not None and first_hang_ask is not None and last_hang_end is not None and take_at < first_hang_ask < last_hang_end),
        'with six unreadable runs and a pass allowed half a second for runs already in trouble, each of six later passes reads its new run and makes its FAIL notice, the six stay listed, as unread when asked for and as put off (and not as unread) when not, some are put off and said so, every one is asked for again within the six passes, and each gets its UNREADABLE notice in the first pass after the waiting time, whether or not it was asked for in that pass':
            holds(lambda: unread(rot0) == [f'h-{i}' for i in range(6)] and all((f'z-fresh-{k}', 'FAIL') in r_['made'] for k, r_ in enumerate(rotation, 1))
                  and all(sorted(r_['unread'] + r_['put_off_names']) == [f'h-{i}' for i in range(6)] for r_ in rotation) and any(r_['put_off'] > 0 for r_ in rotation)
                  and all(not set(r_['unread']) & set(r_['put_off_names']) and len(r_['put_off_names']) == r_['put_off'] for r_ in rotation)
                  and sorted(set().union(*[r_['asked'] for r_ in rotation])) == [f'h-{i}' for i in range(6)] and unr12 == [f'h-{i}' for i in range(6)]
                  and rotation[0]['put_off'] > 0 and unr_first == [f'h-{i}' for i in range(6)]),
        # T2
        'two runs that cannot be read are listed as unread, with the time since and why, in the summary of each of three passes inside the waiting time and in the courier\'s status; neither is marked done, no notice of them is made, and the blocked mark is not set':
            holds(lambda: all(unread(x) == ['a-u1', 'c-u2'] and all(u.get('since') == t0 and u.get('why') for u in x['unread']) for x in early)
                  and made(early[0]) == [('b-fail', 'FAIL')] and made(early[1]) == [] and made(early[2]) == [] and st_early.get('final') == ['b-fail'] and not st_early.get('blocked_sent')
                  and e['t2']['status_unread'] == ['"a-u1"', '"c-u2"']),
        'once they have been unreadable for the waiting time, each gets one UNREADABLE notice of its own, which the mailbox accepts with a receipt that verifies; its four lines say the courier could not read the run and does not know its outcome; it is not made again at the next pass, and the record\'s checker does not take it as a notice of the run\'s outcome':
            holds(lambda: made(due) == [('a-u1', 'UNREADABLE'), ('c-u2', 'UNREADABLE')] and made(again2) == [] and len(unr) == 2
                  and all(C.notice_problems(x['notice'], [w2.ckey.public_hex]) == [] and C.receipt_problems(x['receipt'], [w2.mkey.public_hex], x['notice']) == [] for x in unr)
                  and all(four_lines(x['notice']['text']) and x['notice']['text'].split('\n')[0] == 'THE COURIER CANNOT READ ONE RUN FROM THE WITNESS: ITS OUTCOME IS NOT KNOWN'
                          and 'does not know its outcome' in x['notice']['text'] for x in unr)
                  and unr_checked == ['the notice is of a run that is not in this record'] * 2),
        'when one of them becomes readable, its FAIL notice is made at the next pass, it leaves the unread list and is marked done, and the other stays unread':
            holds(lambda: made(read2) == [('a-u1', 'FAIL')] and unread(read2) == ['c-u2'] and 'a-u1' in st_read.get('final', []) and 'c-u2' not in st_read.get('final', [])
                  and [u.get('aid') for u in stat_read['budgets'][S.ROOT]['unread']] == ['"c-u2"']),
        # T3
        'with the witness not answering at all, no run is listed as unread and no notice of a run is made; each pass\'s summary says the courier is blocked; one COURIER_BLOCKED notice is made once the waiting time has passed, not before and not again; its words say the courier has not been able to read the witness and do not say that no notice of the budget\'s runs will come; the status says the courier is blocked':
            holds(lambda: [made(x) for x in down] == [[], [('', 'COURIER_BLOCKED')], []] and all(unread(x) == [] and len(x.get('blocked', [])) == 1 for x in down)
                  and len(blocked_texts) == 1 and 'has not been able to read the witness' in blocked_texts[0] and 'no notice of this budget\'s runs will come' not in blocked_texts[0]
                  and four_lines(blocked_texts[0]) and stat3['budgets'][S.ROOT]['courier'].startswith('the courier is blocked: it cannot read the witness')),
        'when the witness stops answering while one run is read, that run is listed as unread (once, with since when and why), no notice of that run is made in that pass, and the pass ends as the witness not readable (with no waiting time, one COURIER_BLOCKED); once the witness answers, the next pass makes that run\'s UNREADABLE (due, with no waiting time) before it asks for it, then the FAIL notices of all three runs, and clears the blocked mark, and a later outage is told again':
            holds(lambda: made(dies) == [('', 'COURIER_BLOCKED')] and unread(dies) == ['a-dies'] and len(dies.get('unreachable', [])) == 1 and 'the witness cannot be read' in dies['unreachable'][0]['why']
                  and st_dies.get('final', []) == [] and made(back) == [('a-dies', 'FAIL'), ('a-dies', 'UNREADABLE'), ('b-fail', 'FAIL'), ('c-fail', 'FAIL')] and not st_back.get('blocked_sent') and made(again_down) == [('', 'COURIER_BLOCKED')]),
        'a run that could not be read earlier in a pass does not silence the notice that the courier is blocked when the witness then stops answering in that pass (no waiting time): the one COURIER_BLOCKED is made, and the UNREADABLE notice of the run before it (none of the run after which the witness stopped answering, in that pass)':
            holds(lambda: made(after_unread) == [('', 'COURIER_BLOCKED'), ('a-un\x01read', 'UNREADABLE')]),
        'a pass that ends because the witness stopped answering part-way makes no WATCHING statement':
            holds(lambda: no_watching == (None, None, [])),
        'a run whose reading knocks the witness over, which then comes back: the runs after it get their FAIL notices at the second pass (it is asked for last); the run is listed as unread in the summary and the status from the first pass, with the time since, and gets one UNREADABLE notice after the waiting time; the COURIER_BLOCKED notice names it; once it reads, its FAIL notice follows and it leaves the unread list at once':
            holds(lambda: made(knock[0]) == [] and made(knock[1]) == [('b-fail', 'FAIL'), ('c-fail', 'FAIL')] and all(unread(x) == ['a-knock'] for x in knock)
                  and all([(u.get('aid'), u.get('since')) for u in ks(st_, 'unread')] == [('"a-knock"', t0)] for st_ in knock_status)
                  and sum(1 for x in knock for m in x.get('made', []) if m.get('outcome') == 'UNREADABLE') == 1 and ('a-knock', 'UNREADABLE') in w9.held()
                  and len(knock_blocked) == 1 and 'after the courier asked it for run "a-knock"' in knock_blocked[0]
                  and made(knock_back) == [('a-knock', 'FAIL')] and ks(knock_status_back, 'unread') == [] and ks(knock_status_back2, 'unread') == []),
        'when the pass ends because the witness stopped answering after one run, the COURIER_BLOCKED words say that no pass has been completed for that long, name the run, say that in the last pass the runs asked for before it were asked for as usual and those after it not asked for, and do not say that no notice of the budget\'s runs can be made, or that this was so in each pass':
            holds(lambda: len(knock_blocked) == 1 and 'No pass over this budget has been completed for' in knock_blocked[0] and 'In the last pass, the witness stopped answering after the courier asked it for run "a-knock"' in knock_blocked[0]
                  and 'the runs asked for before it in that pass were asked for as usual' in knock_blocked[0] and 'in each' not in knock_blocked[0]
                  and 'the runs after it were not asked for in that pass' in knock_blocked[0] and 'can make no notice' not in knock_blocked[0]),
        # T4
        'the witness refuses (400, with the error of its rule on names) each of ACCEPT_RESERVATION, ACCEPT_INTENT, CROSS, RELEASE and RECONCILE for a run named with 513 characters, a NUL, a line feed, U+001F, DEL or a lone surrogate, and adds no decision; the gateway\'s own store had admitted the 513-character name':
            holds(lambda: len(refusals) == 30 and all(v[0] == 400 and v[1].startswith('malformed request: an attempt is named') and v[2] == 0 for v in refusals.values())
                  and reserved['513 characters'] == 'APPLIED'),
        'names at the edge (512 characters, one character, a space, a tilde and characters past ASCII, U+0085 and U+2028 among them) are accepted by the witness and read back under the same name':
            holds(lambda: all(v[1] == 200 and v[2] == 'APPLIED' and v[3] == 200 and v[4] for v in edges.values()) and len(edges) == 4),
        # T5
        'for a run\'s name (on a run with no outcome, and on a run with a verdict), a reason code, a criterion\'s id, its units and a detail, each holding a line feed, a carriage return, U+2028, U+0085, U+202E, a NUL, a forged courier sentence, a double quote and a backslash around a forged sentence, the courier\'s real last line, 100,000 characters, or all of these: the notice has exactly four lines of printable ASCII, its last line is exactly the courier\'s, the value appears in it in quotation marks escaped by the rule written out in this test (cut, with its length and SHA-256, where longer than its place), and outside quotation marks there is no forged sentence, no control or format character, and the real last line once':
            holds(lambda: len(t5) == 66 and all(t5_ok.values())),
        'each of those notices is signed by the courier, accepted by the stand-in mailbox (Mailbox.take behind the same 64 KiB limit on the notice\'s JSON as the real handler) with a receipt that verifies, its readable copy is its words exactly, and the record\'s checker rule takes it and makes the same words (a notice of the run\'s outcome), or refuses it as not a run\'s outcome (UNREADABLE, for a name the reading refuses)':
            holds(lambda: all(r_.get('signed') and r_.get('copy') for r_ in t5.values()) and n_unr > 0 and sum(r_.get('made') == 'UNREADABLE' for r_ in t5.values()) == n_unr
                  and sum(r_.get('checker') is None for r_ in t5.values()) == len(t5) - n_unr),
        'the mailbox\'s readable copy of a notice of Amendment 11\'s form whose run name holds U+2028, U+0085 and U+202E writes each of them as an escape, and opens with a line saying its lines may hold words the service chose':
            holds(lambda: copy_odd_ok),
        'the notices the courier makes for a name and a request key of 100,000 characters, of 512 astral characters or of 512 double quotes, with a result whose reason code, detail, criteria ids and units are 100,000 astral characters each (50 criteria), of each outcome, are all under the mailbox\'s 64 KiB; and a run so named in the stand-in\'s chain has its notice accepted by the stand-in mailbox at the first pass, which refuses (400) and does not keep a notice of Amendment 11\'s form over 64 KiB':
            holds(lambda: len(sizes) == 18 and all(isinstance(v, int) and v < MB.MAX_NOTICE for v in sizes.values())
                  and sorted(o for a, o in wbig.held() if a.startswith('cut name: ')) == ['UNREADABLE'] and not sbig.get('waiting')
                  and big_limit[0] and 'the mailbox answered 400' in big_limit[1] and big_limit[2] == 0),
        'the mailbox\'s listing gives one line for each notice it holds, whatever the names':
            holds(lambda: listing.returncode == 0 and len(list_lines) == len(w5.held_items()) and all(all(32 <= ord(ch) <= 126 for ch in l) for l in list_lines)),
        'Amendment 11\'s words, for a notice without a form, are byte for byte as written out here; a notice of that form is still accepted by the mailbox and taken by the checker; taking the form away from a notice of form 2, or adding form 2 to one of Amendment 11, breaks its signature, and form 3 is refused':
            holds(lambda: a11_same and form1_ok and form_games[0] == ['it is not signed by a courier key given'] and form_games[1] == ['it is not signed by a courier key given']
                  and form_games[2] == ['it is of a form of notice this checker does not know']),
        # T6
        'in the courier\'s status, a configured budget is NOT CONFIRMED (not yet read) before any pass, NOT CONFIRMED (statement made, not yet accepted) with the mailbox down, and CONFIRMED from the decision the pass read to once the mailbox accepts the statement; NOT CONFIRMED (stopped) after the courier refuses the budget; a configured budget whose chain it cannot read is not yet read; only configured budgets are listed, and the status says the courier knows only those':
            holds(lambda: e['t6_courier']['before'].startswith('NOT CONFIRMED (not yet read') and e['t6_courier']['mailbox down'].startswith('NOT CONFIRMED (statement made, not yet accepted by the mailbox')
                  and e['t6_courier']['mailbox up'].startswith('CONFIRMED') and e['t6_courier']['mailbox up'].endswith(f'from decision {len(w7.rows)})')
                  and e['t6_courier']['stopped'].startswith('NOT CONFIRMED (stopped') and e['t6_courier']['other configured'].startswith('NOT CONFIRMED (not yet read')
                  and e['t6_courier']['budgets listed'] == sorted([S.ROOT, OTHER]) and 'knows only the budgets it is configured for' in e['t6_courier']['note']),
        'the WATCHING statement says the courier has asked the witness for every run in the chain that may call for a notice and that a run it cannot read is reported in a notice of its own, and does not say it has looked at every run':
            holds(lambda: 'has asked the witness for every run in it that may call for a notice; a run it cannot read is reported in a notice of its own (UNREADABLE)' in w_words
                  and 'looked at every run' not in w_words),
        'a notice of form 2 for a run whose name is longer than 512 characters states the name cut, and the checker\'s rule takes it for that run; once the chain also holds a run named with exactly that cut text, the same notice is refused as naming more than one run':
            holds(lambda: na is not None and na['notice']['aid'] == C.field_name(long_a) and na['notice']['aid'].startswith('cut name: "') and alone is None
                  and with_twin == 'the notice names more than one run of this record'),
        'the courier makes one WATCHING statement for a budget, after its first whole pass, and not again; it is of form 2 with four lines, and the checker\'s rule takes it for the stand-in\'s chain':
            holds(lambda: len(watching) == 1 and len(watching_logged) == 1 and w_ok and [c.get('state') for c in p73.get('coverage', [])] == []),
        'with the real deployment: a record built before the courier has run, and one built while the mailbox is down, fail --require-delivery saying COURIER COVERAGE: NOT CONFIRMED; once the mailbox accepts the statement, the record carries it and passes, saying COURIER COVERAGE: CONFIRMED from the decision the statement names':
            holds(lambda: cli0[0] == 1 and N(cli0[1])[-1].startswith('COURIER COVERAGE: NOT CONFIRMED') and cli1[0] == 1 and N(cli1[1])[-1].startswith('COURIER COVERAGE: NOT CONFIRMED')
                  and cli2[0] == 0 and okc and N(cli2[1])[-1].startswith(f"COURIER COVERAGE: CONFIRMED from decision {cn.get('seq')}") and [d['notice'].get('seq') for d in log_w] == [cn.get('seq')]
                  and (sc.get('coverage') or {}).get('state') == 'CONFIRMED' and isinstance(cn.get('seq'), int)),
        'the checker\'s CONFIRMED line says that it shows the courier began to watch at that decision, not that it still does':
            holds(lambda: 'This shows that the courier began to watch at that decision; it does not show that it still does' in N(cli2[1])[-1]),
        'with the real deployment, the courier\'s status says NOT CONFIRMED (statement made, not yet accepted by the mailbox) while the mailbox is down and CONFIRMED from that decision after; a budget it is not configured for is not in its status, and a record of that budget fails --require-delivery saying COURIER COVERAGE: NOT CONFIRMED':
            holds(lambda: b_of(st1, root).get('coverage', '').startswith('NOT CONFIRMED (statement made, not yet accepted by the mailbox') and b_of(st2, root).get('coverage', '').startswith('CONFIRMED')
                  and b_of(st2, root)['coverage'].endswith(f"from decision {cn.get('seq')})") and root2 is not None and root2 not in st2['budgets'] and cli_other[0] == 1
                  and N(cli_other[1])[-1].startswith('COURIER COVERAGE: NOT CONFIRMED')),
        'a record whose coverage statement is missing, for another budget (in its words and field, or in its field alone), without a receipt, with a receipt signed by another key, naming a decision not in its chain, signed by another courier key, or of Amendment 11\'s form, is NOT CONFIRMED and fails --require-delivery':
            holds(lambda: len(judged6) == 8 and all(v == ('NOT CONFIRMED', 1) for v in judged6.values())),
        # T7
        'the courier\'s status tells a notice made and not yet accepted by the mailbox from one accepted (a signed receipt; not a person\'s acknowledgement), and the courier blocked (it cannot read the witness), in those words, with the stand-in and with the real deployment; the summary of a pass lists the blocked budget, and the notices waiting apart from those accepted':
            holds(lambda: b_wait.get('notices made, not yet accepted by the mailbox') == 1 and b_wait.get("notices accepted by the mailbox (a signed receipt; not a person's acknowledgement)") == 0
                  and b_acc.get('notices made, not yet accepted by the mailbox') == 0 and b_acc.get("notices accepted by the mailbox (a signed receipt; not a person's acknowledgement)") == 1
                  and b_of(st1, root).get('notices made, not yet accepted by the mailbox') == 1 and b_of(st2, root).get("notices accepted by the mailbox (a signed receipt; not a person's acknowledgement)") == 1
                  and b_of(st_b, root).get('courier', '').startswith('the courier is blocked: it cannot read the witness') and len(sum_b.get('blocked', [])) == 1
                  and sum_b['blocked'][0]['state'] == 'the courier is blocked: it cannot read the witness'
                  and [x.get('outcome') for x in c1[1]['waiting']] == ['FAIL'] and c1[1]['delivered'] == [] and [x.get('outcome') for x in c2[1]['delivered']] == ['FAIL']),
        'with a run in the record named with U+0085 and U+2028 before words that copy the checker\'s lines, the checker\'s print-out read with str.splitlines() has exactly one line beginning "COURIER COVERAGE:" and one beginning "NOTICES:"':
            holds(lambda: forged_in_record and len([l for l in cli2[1] if l.startswith('COURIER COVERAGE:')]) == 1 and len([l for l in cli2[1] if l.startswith('NOTICES:')]) == 1),
        'the checker\'s NOTICES line says a notice is accepted by the mailbox (a signed receipt; not a person\'s acknowledgement); in the courier\'s status, the summaries of passes, the checker\'s notices and coverage lines, the three commands\' help and the notices\' words, none of the phrases this test lists for a person having read, seen or acknowledged something appears, except in saying that a receipt is not that':
            holds(lambda: "have one accepted by the mailbox (a signed receipt; not a person's acknowledgement)" in N(cli2[1])[0] and all(e['t7_words'].values()) and len(e['t7_words']) == 6),
        # T8
        'a signed PASS whose own numbers miss its own stated limit gets one INCONSISTENT notice, once over two passes, accepted by the mailbox and not taken by the checker as the run\'s outcome; the run is marked done in the same pass, as a PASS always is; a PASS that meets its limit, one at the limit and one whose number is not a number get none':
            holds(lambda: incs['as built'] == ['b-pass-bad'] and 'b-pass-bad' in t8['as built']['final1'] and t8['as built']['final1'] == base8['final1'] and ('b-pass-bad', 'INCONSISTENT') in t8['as built']['held']
                  and t8['as built']['checked'] == ['the notice is of a run that is not in this record'] and e['t8']['words'][0] == 'THE GATE SIGNED PASS, BUT THE NUMBERS IN THE SAME SIGNED RESULT DO NOT MEET ITS STATED LIMIT'),
        'with the added check made to raise, to find for everything, or to return nothing, and with the whole added function made to raise or to return something that is not its notice, every notice made and accepted without it is still made and accepted, the same runs are marked done (after each of two passes) and unread, and no INCONSISTENT notice is made except, when it finds for everything, one for each PASS':
            holds(lambda: all(same8.values()) and len(same8) == 7 and incs['without it'] == [] and incs['the check raises'] == [] and incs['the check returns nothing'] == []
                  and incs['the check finds for everything'] == ['b-pass-bad', 'c-pass-ok', 'h-pass-text', 'i-pass-edge'] and incs['the whole added function raises'] == []
                  and incs['the whole added function returns something that is not its notice'] == []
                  and sorted(base8['made']) == sorted([('a-fail', 'FAIL'), ('d-unknown', 'UNKNOWN'), ('e-intent', 'NO_OUTCOME'), ('f-unread', 'UNREADABLE'), ('g-cut', 'INTERRUPTED'), ('j-unverified', 'UNVERIFIED')])),
        # third form
        'a run after which the witness once stopped answering is not put off for ever behind runs that answer slowly: its FAIL notice is made within the first two passes after it reads; while runs are put off, every pass exits 1 and no WATCHING statement is made':
            holds(lambda: k_first is not None and k_first <= 2 and all(x['failed'] for x in g1 if x['put_off']) and any(x['put_off'] for x in g1) and g1_watching == []
                  and all('made, not yet accepted by the mailbox' not in (x['coverage'] or []) for x in g1 if x['put_off'])),
        'a run after which the witness once stopped answering, behind runs that cannot be read, gets its UNREADABLE notice after the waiting time, at the next pass whose checkpoint is answered, in words that say the witness stopped answering when it was last asked for and has answered the checkpoint since, and its FAIL notice follows within three passes':
            holds(lambda: len(kj_unr) == 1 and 'the witness stopped answering' in kj_unr[0] and "the witness has answered the courier's checkpoint since" in kj_unr[0]
                  and kj_first is not None and kj_first <= 3),
        'a run that knocks the witness over at every other reading is listed as unread after each pass in which it knocks and not after those in which it is read; the wait for its outcome goes on across the passes in which it knocks, and its NO_OUTCOME notice is made once the waiting time has passed':
            holds(lambda: [u_ for _, u_ in g1e] == [['a-knock'], [], ['a-knock'], []] and [m_ for m_, _ in g1e] == [[], [], [], [('a-knock', 'NO_OUTCOME')]]),
        'runs asked for before, with no trouble recorded, are bounded by pass_seconds: with six slow runs a new failing run is read and noticed, most slow runs are put off and said to be, the pass exits 1, and it takes less than the slow runs would':
            holds(lambda: ('z-new-fail', 'FAIL') in g2[0] and g2[1] and g2[1][0] >= 3 and g2[2] <= 3 and g2[3] < 6 * 0.4 and g2[4] is True),
        'a notice the mailbox refuses for good, first in the waiting list, holds back no other: a notice made later in the pass is in the mailbox before the slow runs are asked for; the refused one stays waiting and the status lists it among the notices not delivered, as refused by the mailbox, with its run, the count and the reason':
            holds(lambda: g3[0] is not None and g3[1] is not None and g3[0] < g3[1] and g3[4] and g3[3] == ['a-poison'] and len(g3[2]) == 1
                  and g3[2][0]['run'] == '"a-poison"' and g3[2][0]['times'] >= 1 and 'refused' in g3[2][0]['last reason'] and g3[2][0]['kind'] == 'refused by the mailbox'),
        'a mailbox that cannot be reached is asked one thing in a pass (its key, at the start), however many notices wait and are made in it, and none is lost; a mailbox that answers with refusals is asked for its key and sent each notice once, for each notice made':
            holds(lambda: g4 == (1, 8, 8, 4)),
        'a request whose peer sends nothing before its headers is given up at the courier\'s deadline and the other runs are noticed in that pass; the thread that waits for that peer is not ended by the courier, and lives until the peer\'s silence ends':
            holds(lambda: silent[0] == [('b-fail', 'FAIL'), ('c-fail', 'FAIL')] and silent[1] == ['a-silent'] and silent[2] < 3.0 and silent[3] >= 1 and silent[4] == 0),
        'an error answer whose body comes a byte at a time is given up at the courier\'s deadline, and its reader does not outlive it':
            holds(lambda: 'did not answer within' in g5[0] and g5[1] < 2.0 and g5[2] == 0),
        'closing an answer shuts its socket down: a read of a real http.client.HTTPResponse over a socket pair, blocked in another thread, returns at once, and the close does not wait for it':
            holds(lambda: closing[0] < 0.5 and closing[1] is False and closing[2] < 1.2),
        'values from the record in the checker\'s print-out (requirement, dates, names, reasons, a check line\'s detail) holding U+2028 or U+0085 make no line of their own under str.splitlines(); a check line\'s detail is shown whole to 2,000 characters':
            holds(lambda: forged_seen == [] and isinstance(printed_d, str) and 'THE LAST PROBLEM' in printed_d.splitlines()[0]),
        'the checker counts a notice of form 2, which states a long name cut, as delivered for the run it names':
            holds(lambda: ten_n is not None and ten_n[2] and due_n == [{'aid': long_f, 'outcome': 'FAIL', 'delivered': True}]),
        'a budget whose own state in the courier\'s state file is malformed is refused for that pass, under a summary key of its own, in words that say so and name the field; it is not marked stopped, nothing is put under the witness\'s refusals, no notice blames the witness, the next budget is read as usual, the status says the state is malformed, and the pass exits 1':
            holds(lambda: len(g9[0]) == 1 and "the courier's own state for this budget" in g9[0][0] and 'its field unread' in g9[0][0] and g9[4] == [S.ROOT] and g9[2] is None
                  and g9[3] and g9[5] == [] and g9[6] == [] and ('z-new-fail', 'FAIL') not in g9[1] and g9[7] == []
                  and g9[8]['budgets'][S.ROOT]['state'].startswith('malformed: its field unread') and g9[8]['budgets'][S.ROOT]['coverage'].startswith('NOT CONFIRMED') and g9[9] is True),
        'resume clears the courier\'s coverage, its unread runs and its lines: the status says NOT CONFIRMED and lists none until a whole pass has been made again, and then CONFIRMED':
            holds(lambda: g10[0] == 'CONFIRMED (th' and g10[1] == ['"e-drop"'] and g10[2].startswith('NOT CONFIRMED (not yet read') and g10[3] is None and g10[4] == [] and g10[5] == 'CONFIRMED'),
        # fourth form
        'with the pass\'s time spent before any run asked for before is reached, one of them is still asked for in the pass, and only one':
            holds(lambda: len(b_turns) == 1),
        'the deadline passing while the body of an error answer is being read is raised as the deadline, not taken as an answer with nothing in it':
            holds(lambda: isinstance(in_error_body, tuple) and in_error_body[0] == 'RAISED' and 'did not answer within' in in_error_body[1]),
        'a run first seen in flight, among a dozen runs that are never done and a new slow run, gets its FAIL notice in the pass in which the chain first says it':
            holds(lambda: ('x-run', 'FAIL') in h1[0]),
        'a run in flight whose entry in the chain changes (it now has a FAIL) is asked for in that pass before older runs in flight that answer slowly, and its FAIL notice is made, though the time runs out on them':
            holds(lambda: ('x-run', 'FAIL') in h1a[0] and h1a[1] and h1a[1][0] >= 1),
        'a run whose outcome needs no request to the witness gets its notice in the pass in which its waiting time ends, though the pass\'s time is spent on a slow run':
            holds(lambda: ('c-intent', 'NO_OUTCOME') in h1b[0] and 'c-intent' not in h1b[1]),
        'when the clock is set back two thousand seconds, nothing of the courier\'s own state is refused, the times in it later than now are set back and the summary says how many, and a new failure is noticed in that pass':
            holds(lambda: h2c[0] == [('b-fail', 'FAIL')] and h2c[1] and h2c[1][0].get('times', 0) >= 1 and h2c[2] == [] and h2c[3] <= t0 - 2000),
        'a notice whose delivery drops the connection, or gets an answer that is not JSON, while the mailbox answers for other notices, holds back no other: a failure made later is delivered in that pass, the first stays waiting, and the status lists it as could not be sent while the mailbox answered when asked for its key':
            holds(lambda: all(v[0] and v[1] and v[2] == ['a-poison'] and v[3] == [('"a-poison"', 'could not be sent (the mailbox answered when asked for its key)')] for v in h3.values()) and len(h3) == 2),
        'a run read cleanly since the witness stopped answering after it, when it is put off, gets no UNREADABLE notice and is listed as put off for want of time only':
            holds(lambda: h4[0] == [] and 'k-run' in h4[1] and h4[2] == ['not asked for in this pass, for want of time']),
        'the courier\'s status says CONFIRMED after a whole pass, "CONFIRMED, but the last pass did not complete: 1 run put off" and lists it, with its line, after a pass that put a run off, and "CONFIRMED, but the last pass did not read this budget" after one that could not read the witness':
            holds(lambda: h5[0].startswith('CONFIRMED') and 'but the last pass' not in h5[0] and h5[1].endswith(', but the last pass did not complete: 1 run put off')
                  and [(x.get('aid'), x.get('line')) for x in h5[2]] == [('"q-1"', 'old')] and h5[4]['old']['put off'] == 1 and h5[4]['new']['put off'] == 0
                  and ', but the last pass did not read this budget: the courier is blocked: it cannot read the witness' in h5[3]),
        'after a pass in which the witness did not answer at all, then one ended by a run after which it stopped answering, the COURIER_BLOCKED words speak of the last pass only and say the runs before it were asked for, not read; and in that pass the notice of the run asked for before it was made and taken by the mailbox before it was asked for':
            holds(lambda: len(h7) == 1 and 'In the last pass, the witness stopped answering after the courier asked it for run "k-run"' in h7[0] and 'in each' not in h7[0] and 'were read' not in h7[0]
                  and h7_before[0] == [('', 'COURIER_BLOCKED'), ('b-fail', 'FAIL')] and h7_before[1] is not None and h7_before[2] is not None and h7_before[1] < h7_before[2]),
        'notices the mailbox answers with no valid receipt for are listed as such in the courier\'s status, not as refused':
            holds(lambda: h10 == ['the mailbox gave no valid receipt']),
        'the time a request is given at the transport is no more than what is left of the deadline, and the courier gives up at the deadline':
            holds(lambda: timeout_held[0] and timeout_held[0][0] <= 0.5 and timeout_held[1] < 1.0),
        'closing an answer whose read never returns does not keep the caller waiting: the close is made apart from it':
            holds(lambda: caller_took < 0.5),
        'the courier\'s own state is malformed for each of sixteen wrong shapes (unread entries, times, asked times, marks, outbox records, the lines\' shape, runs\' entries, the head, the statement, seq, the time since no pass was completed), and not for a good state, one whose times are later than now, or one as the fourth form wrote it (its tiers\' marks, refusals, notices waiting, put-off runs and runs\' entries of the wrong shape among them), whose notices waiting become records of the outbox and whose marks of no use now are let go':
            holds(lambda: len(state_rules) == 16 and all(isinstance(v, str) and v for v in state_rules.values()) and state_good == (None, None, None, ['q'], [])),
        'in the print-out of a verified record, the met designs, the check\'s id, version, author, reviewer and stated limits, the checkpoint\'s time and state, the coverage reason and the currency sentence make no line of their own under str.splitlines()':
            holds(lambda: bool(lines_ok) and forged_ok == [l for l in lines_ok if l.startswith(('NOTICES', 'COURIER COVERAGE', 'STATUS:', 'RECORD VERIFIED', 'CURRENCY:'))]
                  and [l[:16] for l in forged_ok] == ['RECORD VERIFIED ', 'STATUS: DECLARED', 'NOTICES: NOT CHE', 'COURIER COVERAGE', 'CURRENCY: CURREN']),
        'an honest record with a title, a statement, an engineer\'s name and units holding characters past ASCII (\u2264, \u00b0, \u2014, accents) prints each of those values as data, escaped, and the statement in one pair of quotation marks':
            holds(lambda: len(honest_lines) == 4 and honest_lines[0] == honest_want[0] and honest_lines[1] == honest_want[1] and honest_lines[2].startswith(honest_want[2]) and honest_lines[3] == honest_want[3]),
        # fifth form (the addendum's U1 to U8)
        'U1: with sixteen old runs in flight that hang and a new slow run added at every pass (floor 2), a run whose entry in the chain comes to say FAIL is noticed in that pass, and a run whose entry does not change but whose outcome becomes FAIL, last of the old line, is noticed within the number of passes the status states; that number, and the old line\'s length, are at every pass those the test works out from the world it built (17 old runs, then one more for each new run asked, floor 2)':
            holds(lambda: ('x-run', 'FAIL') in u1[0]['made'] and u1[0]['put off'] > 0 and u1_y is not None and u1_y <= u1_expected[0][1] and u1_bound_ok
                  and u1_expected[0] == (17, 9) and u1[0]['lines']['asked in every pass, at least, of each line not empty'] == 2),
        'U2, L1: a run after which the witness stops answering every time: every other run that failed is noticed at the next pass, the run is asked for last, it is listed as unread in the summary and the status at every pass, and its one UNREADABLE notice is made at the first pass after the waiting time, after its checkpoint was answered and before the run was asked for (never after the witness fell), in words that say the witness stopped answering when the run was last asked for and has answered the checkpoint since':
            holds(lambda: u2[1][0]['made'] == [] and u2[1][1]['made'] == [('b-fail', 'FAIL'), ('c-fail', 'FAIL'), ('d-fail', 'FAIL')] and u2[1][1]['asks'][-1] == 'k-knock'
                  and all(x['unread'] == ['k-knock'] and x['status unread'] == ['"k-knock"'] for x in u2[1]) and [x['made'] for x in u2[1][2:]] == [[('', 'COURIER_BLOCKED'), ('k-knock', 'UNREADABLE')], []]
                  and sum(1 for x in u2[1] for m_ in x['made'] if m_[1] == 'UNREADABLE') == 1 and len(u2['1 words']) == 1
                  and 'the witness stopped answering' in u2['1 words'][0] and "the witness has answered the courier's checkpoint since" in u2['1 words'][0]
                  and (lambda ev: ev.index(('ask', '/checkpoint', None)) < ev.index(('take', 'k-knock', 'UNREADABLE')) < ev.index(('ask', '/run', 'k-knock')))(u2[1][2]['events'])),
        'L1: no UNREADABLE notice is made after the witness has stopped answering in a pass: in every pass that ended so, each UNREADABLE notice was taken before the run after which it fell was asked for, after the pass\'s checkpoint was answered':
            holds(lambda: all(all(x['events'].index(t_) < max(i for i, e_ in enumerate(x['events']) if e_[0] == 'ask' and e_[1] == '/run') and x['events'].index(t_) > x['events'].index(('ask', '/checkpoint', None))
                                  for t_ in x['events'] if t_[0] == 'take' and t_[2] == 'UNREADABLE') for x in u2[1] + u2[2] if x['ended'] == 'blocked')
                  and any(x['ended'] == 'blocked' for x in u2[1])),
        'U2: a run after which the witness stops answering every other time: every other run that failed is noticed at the next pass, in which the run is asked for last, read, and its FAIL notice made; it is listed as unread only after the pass in which it knocked, and gets no UNREADABLE notice':
            holds(lambda: u2[2][0]['made'] == [] and u2[2][1]['made'] == [('b-fail', 'FAIL'), ('c-fail', 'FAIL'), ('d-fail', 'FAIL'), ('k-knock', 'FAIL')] and u2[2][1]['asks'][-1] == 'k-knock'
                  and u2[2][0]['unread'] == ['k-knock'] and u2[2][1]['unread'] == [] and u2[2][1]['status unread'] == [] and not any(m_[1] == 'UNREADABLE' for x in u2[2] for m_ in x['made'])),
        'U3: a first pass that put runs off makes no WATCHING statement and exits 1, and the status says how many runs of each line were put off; a run read cleanly since its trouble, put off later past the waiting time, gets no UNREADABLE notice and is listed as put off':
            holds(lambda: made(u3_first) == [] and courier.failed(u3_first) is True and u3_watching == [] and u3_status['lines']['new']['put off'] == 2 and u3_status['lines']['old']['put off'] == 0
                  and u3_status['lines']['new']['asked at the last pass'] == 1 and ('r-trouble', 'UNREADABLE') not in made(u3b) and 'r-trouble' in [x.get('aid') for x in u3b.get('put_off_runs', [])]),
        'U4: with one (first), two (first and last) or three (first, between, last) notices that cannot be delivered, in each way (refused; no valid receipt; the connection dropped; an answer that is not JSON; no answer before the deadline), every other notice is accepted in the same pass; each stuck notice stays in the outbox, listed in the status with its kind and count; none is lost, and none is logged or held twice':
            holds(lambda: len(u4_ok) == 15 and all(u4_ok.values())),
        'U5: with the mailbox not answering at all, a pass sends it one request (asking its key), so costs it one deadline at most, whether one notice waits or ten, and says the mailbox could not be reached; when it answers again, all are delivered at the next pass and none waits':
            holds(lambda: all(v['asked'] == 1 and v['mailbox listed'] == 1 and v['waiting'] == n + 1 and len(v['then delivered']) == n + 1 and v['then waiting'] == 0 for n, v in u5.items()) and len(u5) == 2),
        'U6: an entry of the chain whose name is not text, that is too short, that is not a list, or whose phase is not text, in the last decision or an earlier one: the courier\'s own state is not made malformed (not at that pass, not at the next), the entry is not kept, the budget is stopped with its COURIER_STOPPED alarm accepted by the mailbox, no later notice of the budget is made, and the next budget is read':
            holds(lambda: len(u6) == 8 and all(v['own state'] == [] and v['malformed'] is None and v['stopped'] and v['alarm'] == ['COURIER_STOPPED'] and v['refused'] == [S.ROOT]
                                                and v['kept'] == ['a-fail'] and v['other read'] == 'CONFIRMED' and v['second pass own state'] == [] and v['no later notice'] for v in u6.values())),
        'U6: the witness\'s POST /accept (its real handler) refuses each of ACCEPT_RESERVATION, ACCEPT_INTENT, CROSS, RELEASE and RECONCILE for a run named by a number, null, true, a list or an object (400), before its store reaches the database: it adds no decision':
            holds(lambda: len(accept6) == 25 and all(v == (400, False) for v in accept6.values())),
        'U7: an answer nested too deeply at the checkpoint or at the chain ends the pass as "the witness could not be reached", the answer not readable, with COURIER_BLOCKED after the waiting time; at a run, that run is unread and the others are read, and it gets its UNREADABLE notice after the waiting time':
            holds(lambda: all(u7[k]['made'] == ([], [('', 'COURIER_BLOCKED')]) and u7[k]['unread'] == ([], []) and u7[k]['blocked'] == [1, 1] and u7[k]['ended'] == ('the witness could not be reached',) * 2
                              and 'did not read this budget' in u7[k]['coverage'] and 'not readable' in u7[k]['why'][0] for k in ('/checkpoint', '/chain'))
                  and u7['/run']['made'] == ([('c-fail', 'FAIL')], [('b-deep', 'UNREADABLE')]) and u7['/run']['unread'] == (['b-deep'], ['b-deep']) and u7['/run']['ended'] == ('read', 'read')
                  and 'not readable' in u7['/run']['why'][0]),
        'U7: a fault planted in the courier\'s own handling of a pass is recorded as an error the courier did not expect (not refused, not unreachable), shown in the status with the time since no pass was completed, the pass exits 1, the next budget is read, and after the waiting time one COURIER_FAILED alarm, in words that say the courier cannot tell from this alone whose fault it is and that attribute it to no one, is accepted; once the fault is gone the pass reads the budget again':
            holds(lambda: u7f['made'][:2] == ([], [('', 'COURIER_FAILED')]) and u7f['failed'][:2] == [1, 1] and u7f['unreachable'] == [[], []] and u7f['refused'] == [[], []]
                  and u7f['ended'] == ['the courier met an error it did not expect'] * 2 + ['read'] and 'the courier met an error it did not expect' in u7f['courier']
                  and 'it cannot tell from this alone whether something it was given brought it about' in u7f['courier'] and 'no pass completed since' in u7f['courier']
                  and 'but the last pass did not read this budget: the courier met an error it did not expect' in u7f['coverage'][0] and u7f['coverage'][1].startswith('CONFIRMED') and 'but' not in u7f['coverage'][1]
                  and u7f['other'] == 'read' and u7f['exit'][:2] == [True, True] and u7f['made'][2] == [('b-fail', 'FAIL')]
                  and len(u7f['words']) == 1 and u7f['words'][0][0] == 'THE COURIER HAS MET AN ERROR IT DID NOT EXPECT, AND HAS NOT COMPLETED A PASS OVER THIS BUDGET'
                  and 'It cannot tell from this alone whether something it was given' in u7f['words'][0][2] and 'fault is the courier' not in u7f['words'][0][2] and u7f['checked'] == [[]]),
        'U8: after each way a pass can end (read whole; read with runs put off; the witness could not be reached; what the witness said cannot be believed; the courier met an error it did not expect), the status says that way and no other, and coverage reads plainly CONFIRMED only after the pass that read the budget whole; every other pass exits 1':
            holds(lambda: [v['ended'] for v in u8.values()] == ['read', 'read', 'the witness could not be reached', 'what the witness said cannot be believed', 'the courier met an error it did not expect']
                  and u8['read whole']['coverage'].startswith('CONFIRMED') and 'but' not in u8['read whole']['coverage'] and u8['read whole']['how'] == 'read whole' and u8['read whole']['exit'] is False
                  and u8['read, runs put off']['coverage'].endswith('but the last pass did not complete: 1 run put off, but in the last pass 1 run could not be read')
                  and u8['read, runs put off']['how'] == 'read; 1 run put off for want of time; 1 run could not be read'
                  and 'but the last pass did not read this budget: the courier is blocked' in u8['the witness could not be reached']['coverage']
                  and u8['what the witness said cannot be believed']['coverage'].startswith('NOT CONFIRMED (stopped')
                  and 'but the last pass did not read this budget: the courier met an error it did not expect' in u8['the courier itself failed']['coverage']
                  and all(v['exit'] is True for k, v in u8.items() if k != 'read whole')),
        'while both lines hold runs, the new line has half of pass_seconds: with ten new runs that hang and two old ones, a pass of eight deadlines asks for at least two and at most six new runs, and both old ones':
            holds(lambda: 2 <= shares['new']['asked at the last pass'] <= 6 and shares['old']['asked at the last pass'] == 2 and shares['old']['put off'] == 0),
        'a run that needs no request is settled in every pass and takes no line\'s floor: with pass_seconds 0, its notice is made and the one run that needs a request is still asked for':
            holds(lambda: no_request[0] == [('a-intent', 'NO_OUTCOME'), ('b-run', 'NO_OUTCOME')] and no_request[1] == [] and no_request[2]['new']['asked at the last pass'] == 1),
        'a mailbox that answers with a key not given to the courier is not reached: nothing is sent to it, the pass says so, and the notices wait':
            holds(lambda: len(wrong_key[0]) == 1 and 'not one given to the courier' in wrong_key[0][0] and wrong_key[1] == [] and wrong_key[2] == 0 and wrong_key[3] == ['FAIL', 'WATCHING']),
        'the notice tried longest ago is tried first: when the mailbox drops out after one notice at each pass, the others are delivered at the next pass, not held behind it':
            holds(lambda: oldest[0] == [] and oldest[1] == ['p-1', 'p-2']),
        # sixth form (K1 to K7)
        'K1, L5: a fault while a run\'s FAIL notice is made leaves the run not final and not marked sent, the pass goes on to the run after it (whose notice is made) and exits 1, and the notice is made at the next pass, the run then final':
            holds(lambda: k1['FAIL'] == (True, False, False, [('run-a', 'FAIL')], True) and k1['FAIL p1'] == [('run-b', 'FAIL')]),
        'K1: a fault while the WATCHING statement is made leaves no statement marked made (the pass ends as an error the courier did not expect), and the statement is made at the next pass':
            holds(lambda: k1['WATCHING'] == (None, 'failed', ['WATCHING'])),
        'K1: a fault while an UNREADABLE notice is made leaves it not marked sent, and it is made at the next pass':
            holds(lambda: k1['UNREADABLE'] == (False, [('run-u', 'UNREADABLE')])),
        'K1, K2: a fault while COURIER_STOPPED, COURIER_BLOCKED or COURIER_FAILED is made leaves the budget not marked stopped, or the alarm not marked sent; the pass ends as an error the courier did not expect (saying the alarm could not be made); the alarm is made at the next pass, and only then the mark set':
            holds(lambda: k1['COURIER_STOPPED'] == (None, 'failed', [('', 'COURIER_STOPPED')], True) and k1['COURIER_BLOCKED'] == (None, 'failed', [('', 'COURIER_BLOCKED')], True)
                  and k1['COURIER_FAILED'] == (None, 'failed', True, [('', 'COURIER_FAILED')], True)),
        'K2: a fault while refused.jsonl is written does not keep COURIER_STOPPED from being made in that pass; the budget is stopped, the pass ends as an error the courier did not expect, in words that name the ending whose work failed, with the time since no pass was completed; the refusal is kept in the state and written at the next pass':
            holds(lambda: k2[:6] == ([('', 'COURIER_STOPPED')], True, 'failed', True, 1, False)
                  and 'No space left on device (while the courier was ending a pass that came to: what the witness said cannot be believed)' in k2[6]
                  and k2[7] == t0 + 10 and len(k2[8]) == 1 and k2[8][0].startswith('OSError')),
        'K3: a lasting fault in the sending code is kept in the state with the number of passes, shown in the status\'s coverage and courier lines, and each waiting notice says it was not tried for it; once the fault is gone it is cleared and the notice delivered':
            holds(lambda: k3['send fault'][0] == 3 and ', but the courier cannot send: ' in k3['send fault'][1] and 'the courier cannot send notices' in k3['send fault'][2]
                  and k3['send fault'][3] == ['not tried: the courier met an error while sending'] and k3['cleared'][0] is False and 'cannot send' not in k3['cleared'][1] and 'run-b' in k3['cleared'][2]),
        'K3: a log of deliveries with a line that is not UTF-8 is reported in the pass and in the status, never raised; the pass still makes and delivers its notice':
            holds(lambda: any(x.startswith('the log of deliveries is damaged: line') for x in k3['log not UTF-8'][0]) and k3['log not UTF-8'][1] == [('run-b', 'FAIL')]
                  and str(k3['log not UTF-8'][2]).startswith('damaged: line') and 'is not UTF-8' in str(k3['log not UTF-8'][2])),
        'K4: with the mailbox down over three passes, the waiting notice says it was not tried because the mailbox could not be reached, with the time; the status says since when the mailbox has not answered, and coverage says one notice is not accepted':
            holds(lambda: ', but 1 notice is not accepted; the mailbox has not answered since ' + courier._when(t0 + 1000) + ' by its clock' in k4[0]
                  and [(x['kind'], x['times'], x.get('not tried at')) for x in k4[1]] == [('not tried: the mailbox could not be reached', 0, courier._when(t0 + 400000))]
                  and all('null' not in json.dumps(x) for x in k4[1]) and k4[2]['not answered since'] == courier._when(t0 + 1000)),
        'K5, L4: a RecursionError while the checkpoint is verified ends the pass as the witness not readable, with COURIER_BLOCKED; a MemoryError while a run\'s answer is worked out (one asked for, or one the chain alone settles) leaves that run unread and the others read; both in words that the courier could not handle the answer and cannot tell whether its size or depth or its own memory brought it about, and the run\'s UNREADABLE notice does not say it was told so; a RecursionError in the courier\'s own code elsewhere is an error it did not expect':
            holds(lambda: k5[0] == 'blocked' and k5[2] == [('', 'COURIER_BLOCKED')] and k5[3] == ['run-deep'] and ('run-b', 'FAIL') in k5[4] and k5[5] == []
                  and all('the courier could not handle the answer (' in w5 and 'cannot tell from this alone whether the answer\'s size or depth, or its own want of memory' in w5 for w5 in k5[6] + k5[7])
                  and len(k5[6]) == 1 and len(k5[7]) == 1 and k5[8] == 'failed' and len(k5[9]) == 1 and 'could not handle the answer' in k5[9][0]
                  and len(k5[10][0]) == 1 and k5[10][0][0].startswith('the courier could not handle the answer (MemoryError)') and ('run-b', 'FAIL') in k5[10][1]),
        'K6: a pass in which a run could not be read is not "read whole": its ending says "read; 1 run could not be read", and coverage says so':
            holds(lambda: k6[0] == 'read; 1 run could not be read' and k6[1].startswith('CONFIRMED') and k6[1].endswith(', but in the last pass 1 run could not be read')),
        'K7: after a pass that ended before the old line the status says so, that the bound is for passes that reach the old line and that the new line has none; after a blocked pass then one with an error not expected, the COURIER_FAILED alarm counts from the first pass not completed; status() reports a budget it cannot build, and does not raise':
            holds(lambda: k7[0] == 'ended before it reached the old line' and k7[1].startswith('has no bound') and str(k7[2]).endswith('that reach the old line')
                  and len(k7[3]) == 1 and 'No pass over this budget has been completed for 140 seconds by its clock' in k7[3][0] and k7[4] == [('', 'COURIER_FAILED'), ('k-new', 'UNREADABLE')]
                  and str(k7[5]).startswith('malformed: its status could not be built (RuntimeError')),
        'a mailbox that gives the key the courier was given at /pubkey but signs its receipts with another key has no notice taken as delivered: each is listed as no valid receipt, and waits':
            holds(lambda: pin == ([], ['the mailbox gave no valid receipt'], [], 2)),
        # seventh form (L1 to L7)
        'L2: with the state\'s write failing once at each call of a pass in turn, or from each call to the end of the pass, the pass does not raise, and after two passes with no fault the mailbox holds each notice once (both FAILs and the statement): none lost, none twice':
            holds(lambda: len(l2) >= 10 and all(not v['raised'] and v['held'] == want_l2 and v['twice'] == [] for v in l2.values())
                  and all(v['failed'] for v in l2.values()) and any(v['saved_not'] for k, v in l2.items() if k[0] == 'rest')),
        'L3: an error of the courier\'s own while one run is read is recorded as an error it did not expect while reading that run (not as what it was told), names the run in the summary, and the pass goes on to the other runs; the run\'s UNREADABLE notice says so':
            holds(lambda: ('run-b', 'FAIL') in l3[0] and ('run-a', 'UNREADABLE') in l3[0] and len(l3[1]) == 1 and l3[1][0].startswith('the courier met an error it did not expect while reading this run (TypeError')
                  and [a_ for a_, _ in l3[2]] == ['run-a'] and len(l3[3]) == 1 and 'The courier met an error it did not expect while reading this run' in l3[3][0] and 'What the courier was told' not in l3[3][0]),
        'L5: a fault, every time, while one run\'s notice is made keeps that run (not done, no notice), names it in the summary and in the status, lets the pass go on to the other runs, ends "read; 1 notice could not be made" with exit 1 and coverage saying so, and after the waiting time makes one COURIER_FAILED for that run, in words that say the courier read it and has not been able to make its notice':
            holds(lambda: l5[0][0]['made'] == [('run-b', 'FAIL'), ('run-c', 'FAIL')] and all(x['how'] == 'read; 1 notice could not be made' and x['exit'] is True and 'run-a' not in x['final'] and 'run-a' in x['named'] for x in l5[0])
                  and [x['made'] for x in l5[0][1:]] == [[], [('', 'COURIER_FAILED')], []] and [x.get('run') for x in l5[1]] == ['"run-a"'] and ', but in the last pass 1 notice could not be made' in l5[2]
                  and len(l5[3]) == 1 and 'The courier has read run "run-a" of this budget and has not been able to make its notice since' in l5[3][0]),
        'L6: when the state cannot be saved at all, one_pass does not raise: the pass says so for each budget under a key of its own and exits 1, the next budget is still read, and at the next pass, the state saved, the notices are delivered once':
            holds(lambda: l6[0] is False and l6[1] == sorted([S.ROOT, OTHER_L6]) and l6[2] is True and l6[4] == [('', 'WATCHING'), ('', 'WATCHING'), ('run-a', 'FAIL')]),
        'L7: the status says "not asked yet" of a mailbox never asked and when it last answered after; an append to the log of deliveries after a line left unfinished begins on a line of its own; resume writes a refusal that could not be written before it lets it go; the words of COURIER_BLOCKED after a run say only that the courier tries again at each pass':
            holds(lambda: l7[0] == 'not asked yet' and str(l7[1]).startswith('answered when last asked, at') and l7[2] == 0 and 'run-b' in l7[3] and any('is not JSON' in p_ for p_ in l7[4])
                  and l7[5] is True and l7[6] == 1 and l7[7] is False and len(knock_blocked) == 1 and knock_blocked[0].split('\n')[2].endswith('The courier tries again at each pass.') and 'asks for that run last' not in knock_blocked[0]),
        'the state the fourth form (769f6e4) wrote, with its tiers\' marks, refusals, a notice waiting and runs put off, is read by this form: not judged malformed in the status before or at any pass, brought to this form\'s shape (no field of the earlier forms left), its waiting notice delivered, its runs in trouble read and noticed, and the budget then CONFIRMED':
            holds(lambda: (lambda v: v['status before'][0] is None and v['own state'] == [[], []] and v['upgraded'] and v['malformed'] is None and v['old fields'] == [] and 'b-poison' in v['delivered']
                           and ('k-knock', 'FAIL') in v['made'][0] + v['made'][1] and ('d-drop', 'FAIL') in v['made'][0] + v['made'][1] and not v['stopped'] and v['coverage'].startswith('CONFIRMED'))(old5['fourth form, tiers, refusals and waiting notices'])),
        'the state the fourth form (769f6e4) wrote with a run named by a number in its entries (review 4, exp_b) is not judged malformed: the budget is stopped with its COURIER_STOPPED alarm, in words that say an earlier form kept the entry from what the witness said or the file was damaged':
            holds(lambda: (lambda v: v['status before'][0] is None and v['own state'] == [[], []] and v['malformed'] is None and v['stopped'] and v['made'][0] == [('', 'COURIER_STOPPED')]
                           and v['refused'][0].startswith('an entry of a run that the courier kept from the chain at an earlier pass') and v['coverage'].startswith('NOT CONFIRMED (stopped'))(old5['fourth form, a run named by a number'])),
    }
    return checks, e


TESTS = {'R1': r1, 'R2': r2, 'R3': r3, 'R4': r4, 'R5': r5, 'R6': r6, 'R7': r7, 'R8': r8, 'R9': r9, 'R10': r10, 'R11': r11, 'R12': r12, 'R13': r13, 'R14': r14, 'R15': r15, 'R16': r16, 'R17': r17, 'R18': r18, 'R19': r19, 'R20': r20, 'R21': r21, 'R22': r22, 'R23': r23, 'R24': r24, 'R25': r25, 'R26': r26, 'R27': r27, 'R28': r28, 'R29': r29, 'R30': r30}


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
    (GATEWAY / 'outputs' / 'verify_tests.json').write_text(json.dumps(out, indent=1, default=str))
    print(f"VERIFY RESULT: {'PASS' if out['PASS'] else 'FAIL'} ({passed} of {len(results)})")
    sys.exit(0 if out['PASS'] else 1)


if __name__ == '__main__':
    main()
