#!/usr/bin/env python3
"""Declared tests R1-R13 for the verification-record plug-in (verify/DECLARED_VERIFY.md states the expected outcomes),
and R14 to R16, added by Amendment 2 (verify/DECLARED_AMEND2.md), R17, added by Amendment 3 (verify/DECLARED_AMEND3.md),
and R18, added by Amendment 4 (verify/DECLARED_AMEND4.md).
R1 to R13 are as they were declared.

    verify_tests.py [R1 R5 ...]       all eighteen by default; writes outputs/verify_tests.json; exits 1 if any test fails

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
import subprocess
import sys
import time
import uuid

HERE = pathlib.Path(__file__).resolve().parent
GATEWAY = HERE.parent
sys.path.insert(0, str(GATEWAY)); sys.path.insert(0, str(GATEWAY / 'verify'))
import baseline as B                    # noqa: E402
import check_record                     # noqa: E402
import deploy                           # noqa: E402
import verify_ctl                       # noqa: E402
from plea_gateway import AuthorityError, Store      # noqa: E402
from verify_record import Key, canonical, envelope_message   # noqa: E402

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


NOTICE_OLD = ('Nothing was changed', 'exactly as baselined', 'accept a failure')
SAYS_MATCHED, SAYS_CHANGED = 'matched their baselined hashes when it ran', 'The check or its data is not as baselined'
SAYS_COMPARED, SAYS_REDESIGN = 'says what the declared check returned', 'a different design inside'
SAYS_RESTORE, SAYS_RESTORE_CARD = 'restores the check and its data to the files whose hashes the baseline holds', 'restores the stored baseline'
SAYS_NO_CARD, SAYS_AS_BASELINED = 'could not use its stored copy of this baseline', 'The requirement, the limits and the load case are as baselined.'
NO_CARD_NOTICE = 'UNKNOWN: A VERIFICATION RUN WAS ASKED FOR AND NO USABLE BASELINE IS HELD'
NO_CARD_ANSWER = 'UNKNOWN: THE VERIFICATION SERVICE HOLDS NO USABLE COPY OF THIS BASELINE'
SAYS_RAN = 'The check and its data matched their baselined hashes when it ran.'
CLAIMS = {'BASELINE_MISMATCH': [SAYS_AS_BASELINED, 'The check or its data is not as baselined (the reason above), so the check was not run.'],
          'LIMIT_NOT_MET': [SAYS_AS_BASELINED, SAYS_RAN], 'RESULT_IMPLAUSIBLE': [SAYS_AS_BASELINED, SAYS_RAN]}
NO_CARD_LINE = 'The verification service could not use its stored copy of this baseline (the reason above), so nothing was checked against it.'


def verdict_row(code: str) -> str:
    compared = code in ('MET', 'LIMIT_NOT_MET')
    return (f'Verdict       {B.REASONS[code]}.  ' + ("Computed by the verification service from the check's output and the baselined limits." if compared else
                                                    "Decided by the verification service, not by comparing the check's numbers with the limits.") + '  Not stated by the assistant.')


def text_claims(t: str, code: str, held: bool = True) -> dict:
    """What a notice or an answer says about its own run, against what the run was.  held is False when the gate held no
    usable copy of the card, which only the first client's answer then sets out from its own copy.  (Amendment 4.)"""
    lines = t.splitlines()
    return {'old_words': sum(w in t for w in NOTICE_OLD),
            'headline_fits': (B.HEADLINE[code] if held else NO_CARD_ANSWER) in lines,
            'verdict_row_states_it': [l for l in lines if l.startswith('Verdict ')] == [verdict_row(code)],
            'card_said_unchanged_only_when_held': ('unchanged' in t) == held,
            'claims_are_the_allowed_lines': [l for l in lines if re.search(r'as baselined|matched|unchanged|[Nn]othing|intact', l) and not l.startswith(('              baselined ', B.SENT_MARK))]
                                            == ([] if code == 'MET' else [NO_CARD_LINE] if not held else CLAIMS.get(code, [SAYS_AS_BASELINED])),
            'accept_fits': code == 'MET' or 'can accept this result or issue a revised baseline; the assistant cannot.' in t,
            'closing_fits': ('This result gives no number from the check against the limits.' in t) == (code not in ('MET', 'LIMIT_NOT_MET')),
            'as_baselined_said_only_when_so': (SAYS_AS_BASELINED in t) == (held and code != 'MET'),
            'files_matched_said_when_so': (SAYS_MATCHED in t) == (held and code in ('LIMIT_NOT_MET', 'RESULT_IMPLAUSIBLE')),
            'files_changed_said_when_so': (SAYS_CHANGED in t) == (held and code == 'BASELINE_MISMATCH'),
            'no_card_said_when_so': (SAYS_NO_CARD in t) == (not held),
            'comparison_claimed_only_when_made': (SAYS_COMPARED in t) == (code in ('MET', 'LIMIT_NOT_MET')),
            'next_step_fits': code == 'MET' or ((SAYS_RESTORE in t) == (held and code == 'BASELINE_MISMATCH') and (SAYS_RESTORE_CARD in t) == (not held)
                                                and (SAYS_REDESIGN in t) == (held and code != 'BASELINE_MISMATCH')
                                                and ('Until then no design inside the design space' in t) == (held and code == 'BASELINE_MISMATCH')
                                                and (code != 'BASELINE_MISMATCH' or not re.search(r'(different|another|other|new) design', t)))}


def r18():
    """A notice and an answer say only what is so for their own run: each states its verdict, says the check's files matched only when the check ran on files that did, never says that nothing was changed, says so when the service held no usable copy of the card, and a revised baseline gives every count of the runs it replaced."""
    r = Run('R18'); e = {}
    try:
        d = r.s.home / 'baselines' / r.h; card = r.env['card']
        wanted = [(card['check']['file'], card['check']['sha256'])] + [(i['file'], i['sha256']) for i in card['inputs']]
        files_match = lambda: all(B.sha256_hex((d / name).read_bytes()) == want for name, want in wanted)
        runs = {}

        def send(code, design):
            runs[code] = {'files_matched': files_match(), 'answer': r.submit(design)}
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
        no_card = r.submit({'material': 'PA66-GF30', 'wall_mm': 2.6, 'mode': 'normal'})
        stored.write_text(good)
        send('MET', GOOD)
        heads = {v: k for k, v in B.HEADLINE.items()}; heads[NO_CARD_NOTICE] = 'NO_CARD'
        box = r.s.home / 'inbox' / r.h[:16]
        notices = {}
        for p in sorted(box.glob('*.txt')):
            t = p.read_text(); code = next((heads[l] for l in t.splitlines() if l in heads), None); notices[code] = t
        answers = {code: x['answer'][1] for code, x in runs.items()}
        runs_row = [l for l in answers['MET'].splitlines() if l.startswith('Official runs ')]
        in_notices = {code: text_claims(t, code) for code, t in notices.items() if code != 'NO_CARD'}
        in_answers = {code: text_claims(t, code) for code, t in answers.items()}
        no_card_answer = text_claims(no_card[1], 'BASELINE_MISMATCH', held=False)
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
        for c in [card, pump]:
            for code in B.REASONS:
                crit = B._blank(c)
                if code in ('MET', 'LIMIT_NOT_MET'):
                    crit = [dict(x, achieved='1', margin='0' if code == 'MET' else '-1', met=code == 'MET') for x in crit]
                v = B._verdict(c, {}, code, crit, detail='a reason')
                in_process[(c['requirement']['id'], code)] = text_claims(B.face(c, v), code)
            refusal = verify_tools._refusal('0' * 64, {}, 'no signed baseline with this hash is held by the verification service: the stored file is not a baseline card')
            in_process[(c['requirement']['id'], 'no usable card')] = text_claims(B.face(c, refusal), 'BASELINE_MISMATCH', held=False)
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
                 no_card_answer=no_card_answer, no_card_head=head(no_card[1]), no_card_notice_old_words=sum(w in notices.get('NO_CARD', '') for w in NOTICE_OLD), files_matched=truth,
                 in_process={f'{a} {b}': v for (a, b), v in in_process.items() if not all(v[k] for k in v if k != 'old_words') or v['old_words']},
                 runs_row=runs_row, missing_counts=missing_counts, counts_a=counts, supersedes={k: sup.get(k) for k in ('official_runs', 'met', 'not_met', 'unknown')},
                 banner_print=[l.strip() for l in printed_b.splitlines() if 'CHANGED AFTER THE EVENT' in l], banner_shown=[l.strip() for l in shown.splitlines() if 'SUPERSEDES' in l],
                 on_b=(on_b[0], head(on_b[1])), record_a=(ok_a, why_a), record_b=(ok_b, [f'{n} {t}: {x}' for n, t, g, x in checks_b if not g]))
        clean = lambda found: all(v['old_words'] == 0 and all(v[k] for k in v if k != 'old_words') for v in found.values())
        checks = {'eight runs, one for each verdict the gate gives (MET, LIMIT_NOT_MET, DESIGN_OUTSIDE_BASELINE, CHECK_ERROR, CHECK_OUTPUT_INVALID, RESULT_IMPLAUSIBLE, BASELINE_MISMATCH) and one while the gate holds no usable copy of the card, are answered with the exit status of their verdict; the seven that are not a pass each have a notice':
                      e['exits'] == {'LIMIT_NOT_MET': 2, 'DESIGN_OUTSIDE_BASELINE': 2, 'CHECK_ERROR': 3, 'CHECK_OUTPUT_INVALID': 3, 'RESULT_IMPLAUSIBLE': 3, 'BASELINE_MISMATCH': 3, 'MET': 0, 'NO_CARD': 3}
                      and set(notices) == set(B.REASONS) - {'MET'} | {'NO_CARD'},
                  'no notice says that nothing was changed, that the check is exactly as baselined, or that a failure is to be accepted when the result is UNKNOWN; each notice\'s first line and Verdict row state its verdict, and the Verdict row says the limits were compared only when they were':
                      all(v['old_words'] == 0 and v['headline_fits'] and v['verdict_row_states_it'] for v in in_notices.values()) and e['no_card_notice_old_words'] == 0,
                  'a notice says the check and its data matched the baseline only when the check ran and its files did match, and says they were not as baselined only when they were not':
                      all(v['files_matched_said_when_so'] and v['files_changed_said_when_so'] for v in in_notices.values())
                      and truth['LIMIT_NOT_MET'] is True and truth['RESULT_IMPLAUSIBLE'] is True and truth['BASELINE_MISMATCH'] is False,
                  'every other line of a notice that says what is so holds for its run: it says what the declared check returned against the limits only when its numbers were compared, says who may accept the result, and the notice of a changed check says the files must be restored and offers no other design':
                      clean(in_notices) and len(in_notices) == 6,
                  'the seven answers given to the caller say the same, the pass among them, and the last gives the count of runs so far: 8, 1 met, 2 not met, 5 unknown':
                      len(in_answers) == 7 and clean(in_answers) and len(e['runs_row']) == 1 and e['runs_row'][0].startswith('Official runs 8 through the service on this baseline: 1 met, 2 not met, 5 unknown.'),
                  'while the gate holds no usable copy of the card, the first client\'s answer says so: it does not call the card unchanged or as baselined, does not say the check or its data changed, and says the stored baseline is to be restored':
                      e['no_card_head'] == NO_CARD_ANSWER and clean({'no card': no_card_answer}),
                  'in process, for every verdict on two cards (the fixture and the pump station), and for the gate\'s refusal when it holds no usable card, what face() writes keeps the same rules':
                      len(in_process) == 16 and clean(in_process),
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


TESTS = {'R1': r1, 'R2': r2, 'R3': r3, 'R4': r4, 'R5': r5, 'R6': r6, 'R7': r7, 'R8': r8, 'R9': r9, 'R10': r10, 'R11': r11, 'R12': r12, 'R13': r13, 'R14': r14, 'R15': r15, 'R16': r16, 'R17': r17, 'R18': r18}


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
