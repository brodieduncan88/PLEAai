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
import subprocess
import sys
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
        self.env = self.s.baseline(CASE, card or draft())
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
        rows = lambda: len(Store(deploy.LOCAL_DSN).audit_snapshot(root)[0])
        cur = lambda rec, cp, **kw: check_record.currency(rec, cp, wk, **kw)
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
        def save(name, obj):
            (here / name).write_text(json.dumps(obj)); return here / name
        keys = save('keys.json', s.keys)

        prov = Store(deploy.LOCAL_DSN).provisioning(root)
        cp0 = s.checkpoint(root, 'first-ask_1'); cp0at = s.checkpoint(root, None, 0)
        r.submit(BAD)
        before = rows(); five = [s.checkpoint(root) for _ in range(5)]; after_reads = rows()
        rec1 = r.record(); ok1, checks1, sum1 = check_record.verify(rec1, s.keys)
        bare = s.record(r.h, [r.ws / '.verify' / 'submissions.jsonl'], checkpoint=False); okb, checksb, sumb = check_record.verify(bare, s.keys)
        cp1 = s.checkpoint(root, 'n-1'); f_rec1, f_cp1 = save('rec1.json', rec1), save('cp1.json', cp1)
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
        edited = copy.deepcopy(rec2); edited['checkpoint']['head_at'] = '0' * 64
        earlier = copy.deepcopy(rec2); earlier['checkpoint'] = cp2at                                       # a true checkpoint, of an earlier point in the chain
        foreign = copy.deepcopy(rec2); foreign['checkpoint'] = sign_checkpoint(Signer(), **{k: rec2['checkpoint'][k] for k in ('root', 'seq', 'head', 'business', 'witness', 'time', 'nonce', 'at', 'head_at')})
        plain = copy.deepcopy(rec2); plain['checkpoint'] = s.checkpoint(root)                                 # a true checkpoint that names no earlier head
        inside = {'edited': fails(edited), 'edited, re-signed': fails(resign(edited)), 'earlier point, re-signed': fails(resign(earlier)), 'another key, re-signed': fails(resign(foreign)),
                  'names no head, re-signed': fails(resign(plain)), 'taken out, re-signed': fails(resign({k: v for k, v in rec2.items() if k != 'checkpoint'}))}
        log = here / 'keeper' / 'checkpoints.jsonl'
        kept = [refused(checkpoints.keep, log, c, wk) for c in (cp0, cp1, cp2at)]
        rev = verify_ctl.revise(s.home, CASE, draft(requirement=dict(r.env['card']['requirement'], revision='B')), s.engineer, r.h, 'The bracket was strengthened (CR-31).')
        cp_old = s.checkpoint(root, None, n2); old_state = cur(rec2, cp_old); kept.append(refused(checkpoints.keep, log, cp_old, wk))
        top = cp_old['seq']
        turned = {'rollback': refused(checkpoints.keep, log, cp1, wk), 'fork': refused(checkpoints.keep, log, signed(root=root, seq=top, head='0' * 64, **when), wk),
                  'fork of an earlier head': refused(checkpoints.keep, log, signed(root=root, seq=top + 8, head='1' * 64, at=n1, head_at='0' * 64, **when), wk),
                  'a longer chain that does not follow the last kept': refused(checkpoints.keep, log, signed(root=root, seq=top + 8, head='1' * 64, at=top, head_at='0' * 64, **when), wk),
                  'another key': refused(checkpoints.keep, log, sign_checkpoint(Signer(), root=root, seq=top, head=cp_old['head'], **when), wk),
                  'another budget than asked': refused(checkpoints.keep, log, cp_old, wk, root + 'x'), 'another nonce than asked': refused(checkpoints.keep, log, cp_old, wk, root, 'mine')}
        lines = len(log.read_text().splitlines()); clean = checkpoints.audit(checkpoints.read_log(log)[0], wk)
        evidence = len((here / 'keeper' / 'checkpoints.jsonl.refused.jsonl').read_text().splitlines())
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
        log2 = here / 'keeper2' / 'log.jsonl'
        first = keeper('fetch', '--witness-url', url, *keeper_tls, '--root', root, '--out', here / 'cp_cli.json', '--log', log2, '--witness-key', wk)
        second = keeper('fetch', '--witness-url', url, *keeper_tls, '--root', root, '--log', log2, '--witness-key', wk)
        j1, j2 = (json.loads(x[1]) if x[0] == 0 else {} for x in (first, second))
        with log2.open('a') as f:
            f.write('{"statement": "CHECKP')                                                               # a line cut off by a crash
        torn_audit = keeper('audit', log2, '--witness-key', wk)
        third = keeper('fetch', '--witness-url', url, *keeper_tls, '--root', root, '--log', log2, '--witness-key', wk)
        audited = keeper('audit', log2, '--witness-key', wk)
        rec3 = r.record(); cli_closed = cli(save('rec3.json', rec3), '--keys', keys, '--checkpoint', here / 'cp_cli.json', '--nonce', j1.get('nonce', ''), '--max-age', '600')
        keyfile = here / 'engineer.key'; keyfile.write_text(s.engineer.private_hex + '\n')
        console = subprocess.run([PY, '-B', str(GATEWAY / 'verify' / 'verify_ctl.py'), 'record', str(s.home), r.h, '--key', str(keyfile), '--witness-key', wk, '--gate-key', s.keys['gate'],
                                  '--journal', str(r.ws / '.verify' / 'submissions.jsonl'), '--out', str(here / 'rec_console.json'), '--witness-url', url, '--tls-ca', s.pki['ca'],
                                  '--tls-cert', s.pki['keeper'][0], '--tls-key', s.pki['keeper'][1]], capture_output=True, text=True, timeout=120)
        rec_c = json.loads((here / 'rec_console.json').read_text()) if console.returncode == 0 else {}
        console_ok = bool(rec_c) and check_record.verify(rec_c, s.keys)[0] and (rec_c.get('checkpoint') or {}).get('at') == rec_c['as_of']['seq']
        e.update(cp0={k: cp0.get(k) for k in ('seq', 'business', 'witness', 'nonce', 'at')}, reads=(before, after_reads), checks1=[(n, t, g) for n, t, g, _ in checks1][-1], bare=[(n, t, g) for n, t, g, _ in checksb][-1],
                 summary=sum1.get('checkpoint'), at_the_time={k: v[0] for k, v in at_the_time.items()}, states={k: v[0] for k, v in states.items()}, sentences={k: v[1][:130] for k, v in states.items()},
                 cli=(cli_current[:2], cli_none[:2], cli_old[:2], cli_closed[:2]), cli_misuse=cli_misuse, cli_bad=cli_bad, cli_stale=cli_stale,
                 inside=inside, old_state=old_state, kept=kept, turned=turned, lines=lines, evidence=evidence, clean=clean, dirty=dirty, witness_says=witness_says, no_cert=no_cert, plain_http=plain_http,
                 chain=(chain_before, chain_after), keeper=(first, second, third), torn_audit=torn_audit, audited=audited, console=(console.returncode, console.stderr[:200]))
        st = e['states']
        checks = {'before any run the witness signs a checkpoint of the empty chain: no decisions, its head the provisioning record\'s hash, the budget open, the asker\'s nonce signed back; asked for the head after decision 0 it gives the same hash; both verify under the witness\'s key':
                      cp0['seq'] == 0 and cp0['head'] == prov['hash'] and (cp0['business'], cp0['witness'], cp0['nonce']) == ('OPEN', 'ACTIVE', 'first-ask_1') and check_record.checkpoint_problems(cp0, [wk], root) == []
                      and (cp0at['at'], cp0at['head_at']) == (0, prov['hash']) and check_record.checkpoint_problems(cp0at, wk, root) == [],
                  'asking for a checkpoint adds no decision: five asks leave the chain as long as it was, and each gives its length and head':
                      before == after_reads == n1 and all(c['seq'] == before and c['head'] == h1 for c in five),
                  'a record carries the witness\'s checkpoint, which names the record\'s own last decision and head; the record verifies with a ninth check, the witness checkpoint; a record built without one still verifies, and its ninth check says it has none':
                      ok1 and e['checks1'] == (9, 'witness checkpoint', True) and rec1['checkpoint']['at'] == n1 and rec1['checkpoint']['head_at'] == h1
                      and sum1['checkpoint']['seq'] == n1 and okb and 'checkpoint' not in bare and e['bare'] == (9, 'witness checkpoint (none in this record)', True) and sumb['checkpoint'] is None,
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
                  'a log of checkpoints kept apart from the service takes them in order, and refuses a rollback, a fork of the head, a fork of an earlier head, a longer chain that does not follow the last one kept, a checkpoint not signed by the witness, and one for another budget or nonce than asked; it keeps none of them, and puts the four that contradict it aside as evidence':
                      kept == [None, None, None, None] and turned['rollback'].startswith('not kept: ROLLBACK') and all(turned[k].startswith('not kept: FORK') for k in ('fork', 'fork of an earlier head', 'a longer chain that does not follow the last kept'))
                      and 'not signed by a witness key given' in turned['another key'] and 'another budget' in turned['another budget than asked'] and 'nonce' in turned['another nonce than asked'] and lines == 4 and evidence == 4,
                  'the log\'s audit is clean, and reports a fork written into it behind the keeper\'s back': clean == [] and len(dirty) == 1 and 'FORK' in dirty[0],
                  'the witness answers 404 for a budget it does not hold and 400 for no budget, a nonce with a space or of 65 characters, a decision beyond the chain, a number that is not one and a budget name with a control character; none of it adds a decision':
                      [witness_says[k] for k in ('unknown budget', 'no budget named', 'nonce with a space', 'nonce of 65 characters', 'beyond the chain', 'a number that is not one', 'a budget name with a control character')] == [404, 400, 400, 400, 400, 400, 400]
                      and chain_before == chain_after,
                  'the keeper\'s certificate reads a checkpoint (200) and can do nothing else: the witness refuses its write (403) and its other question (403); a certificate the witness does not know is refused the checkpoint (403); the fetcher gives nothing with no certificate, and will not ask over plain http':
                      (witness_says['keeper reads'], witness_says['keeper writes'], witness_says['keeper asks the key'], witness_says['stranger'], witness_says['governor reads']) == (200, 403, 403, 403, 200)
                      and 'could not be asked' in (no_cert or '') and 'https' in (plain_http or ''),
                  'the keeper\'s command fetches a checkpoint with a nonce of its own making, keeps it and writes it out; its next fetch asks the witness for the head at the last number kept; a line cut off in the log is reported by the audit and does not stop the next fetch; the log then audits clean with three checkpoints':
                      first[0] == 0 and second[0] == 0 and third[0] == 0 and len(j1.get('nonce', '')) >= 16 and j1.get('nonce') != j2.get('nonce') and j1.get('at') is None and j2.get('at') == j1.get('seq')
                      and torn_audit[0] == 1 and 'cut off' in torn_audit[1] and audited[0] == 0 and audited[1].endswith('3 checkpoints; no rollback or fork, every signature verifies'),
                  'the superseded baseline\'s record, built after the revision and checked against the keeper\'s first checkpoint with its nonce, is CURRENT; the command says the budget is no longer open, and exits 0; the engineer\'s console, given the witness\'s address, writes a record that carries a checkpoint and verifies':
                      cli_closed[0] == 0 and cli_closed[1] == ['CURRENCY: CURRENT'] and 'it was superseded or closed' in cli_closed[2] and console.returncode == 0 and console_ok}
    finally:
        r.stop()
    return checks, e


TESTS = {'R1': r1, 'R2': r2, 'R3': r3, 'R4': r4, 'R5': r5, 'R6': r6, 'R7': r7, 'R8': r8, 'R9': r9, 'R10': r10, 'R11': r11, 'R12': r12, 'R13': r13, 'R14': r14, 'R15': r15, 'R16': r16, 'R17': r17, 'R18': r18, 'R19': r19, 'R20': r20, 'R21': r21, 'R22': r22, 'R23': r23, 'R24': r24, 'R25': r25}


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
