#!/usr/bin/env python3
"""Declared tests R1-R13 for the verification-record plug-in (verify/DECLARED_VERIFY.md states the expected outcomes),
and R14 to R16, added by Amendment 2 (verify/DECLARED_AMEND2.md).  R1 to R13 are as they were declared.

    verify_tests.py [R1 R5 ...]       all sixteen by default; writes outputs/verify_tests.json; exits 1 if any test fails

Each test makes a fresh deployment (verify/deploy.py: new keys, the released witness service and gate host under mutual
TLS, the gate host loading verify_tools), baselines the self-test fixture in tests/verify_case/ as the responsible
engineer would, and then acts as the assistant through verify_client.py, exactly as an assistant's shell would.  The
independent measures are the gate tool's ledger and the engineer's inbox, both outside every PLEA store.

A test passes only if every named check in it is true.  A harness or service error is a failed test.
"""
import json
import os
import pathlib
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
        unknown = 'UNKNOWN: THE CHECK OR ITS DATA NO LONGER MATCHES THE BASELINE'
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


TESTS = {'R1': r1, 'R2': r2, 'R3': r3, 'R4': r4, 'R5': r5, 'R6': r6, 'R7': r7, 'R8': r8, 'R9': r9, 'R10': r10, 'R11': r11, 'R12': r12, 'R13': r13, 'R14': r14, 'R15': r15, 'R16': r16}


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
