#!/usr/bin/env python3
"""Diagnostic for F17 (diagnostic branch only; not a declared test, and it changes nothing the service does).

F17 shows that two failures whose notices would have the same file name both reach the engineer.  It makes that case by
timing: two failing designs, sent one after the other just after a second begins, must both end within that second.  Under
Amendment 12 two runs in a row take about 0.96 to 1.02 s, so the case is often not made, and F17 then fails without having
tested anything.  This file measures that, and makes the case in two ways that do not rest on that margin:

  A  timing     F17's own way, with every submission timed, and the sandbox's own phases if VERIFY_SANDBOX_TRACE is set:
                how long a pair takes, and where the time goes.  It reports; it does not judge.
  B  component  two notices published with one stem, straight through notices.publish: deterministic, no clock.
  C  together   the two designs sent at the same moment by two jobs enrolled on the one baseline (one job may have only one
                design being verified at a time, and a second is refused IN_PROGRESS).  The precondition is checked for
                itself: only when both notices are named for the same second and the same eight digits is the property
                judged.

Each of B and C ends in exactly one of:
  COLLISION_HANDLED       the case was made, and each failure has its own whole notice
  COLLISION_MISHANDLED    the case was made, and a notice was lost, written over or wrong
  PRECONDITION_NOT_MET    the case was not made: nothing is shown either way (never a pass)

    python3 -B diag_f17_collision.py [A] [B] [C]        writes ../outputs/diag_f17_collision.json; exit 0 only if no
                                                        part asked for was MISHANDLED or NOT_MET
"""
import json
import os
import pathlib
import sys
import tempfile
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / 'verify'))
import verify_front_tests as F                                            # the declared suite's own harness, unchanged
import notices

B = F.B
TRACE = os.environ.get('VERIFY_SANDBOX_TRACE')


def stem(name) -> str:
    """A notice's name without its number: time to the second, verdict, first eight digits of the design hash."""
    return '_'.join(str(name)[:-4].split('_')[:3])


def submit(job, design):
    t0 = time.time()
    status, answer = F.raw(job, 'POST', '/submit', json.dumps({'design': design}).encode())
    return {'sent': t0, 'answered': time.time(), 'status': status, 'outcome': (answer or {}).get('outcome')}


def sandbox_runs(since: float) -> list:
    """The sandbox's own account of each run since then, if it was traced: when it began and ended, and its phases."""
    if not TRACE or not os.path.exists(TRACE):
        return []
    open_, done = {}, []
    for line in open(TRACE):
        x = json.loads(line)
        if x['t'] < since:
            continue
        k = (x['pid'], x['thread'])
        if x['event'] == 'run.begin':
            open_[k] = {'begin': x['t']}
        elif k in open_:
            open_[k][x['event']] = x['t']
            if x['event'] == 'run.end':
                c = open_.pop(k)
                done.append({'begin': c['begin'], 'end': x['t'], 'seconds': round(x['t'] - c['begin'], 3),
                             'groups': round(c.get('run.groups', 0) - c.get('run.ids', 0), 3), 'launch': round(c.get('run.go', 0) - c.get('run.groups', 0), 3),
                             'check': round(c.get('supervise.read', 0) - c.get('run.go', 0), 3), 'cleanup': round(x['t'] - c.get('supervise.read', 0), 3)})
    return done


def judge(box: pathlib.Path, names: list, designs: list) -> dict:
    """Given two notices' names: was the case made, and if so, does each failure have its own whole notice?"""
    made = len(names) == 2 and all(names) and stem(names[0]) == stem(names[1])
    out = {'names': names, 'stems': [stem(n) for n in names], 'precondition_met': made}
    if not made:
        return dict(out, result='PRECONDITION_NOT_MET')
    texts = [(box / n).read_text() if (box / n).is_file() else '' for n in names]
    own = [f"wall_mm = {d.get('wall_mm')}" in t for d, t in zip(designs, texts)] if designs else [bool(t) for t in texts]
    good = len(set(names)) == 2 and all(own) and all(len(t) > (200 if designs else 0) for t in texts)
    return dict(out, distinct=len(set(names)) == 2, own_text=own, sizes=[len(t) for t in texts], result='COLLISION_HANDLED' if good else 'COLLISION_MISHANDLED')


def part_a(tries: int = 6) -> dict:
    r = F.Run('F17diagA'); rows = []
    try:
        for a, b in F._clashing_pairs(tries):
            time.sleep(1.03 - time.time() % 1)                            # as F17 does
            began = time.time()
            first = submit(r.job, a); second = submit(r.job, b)
            names = [x.get('notice') for x in r.s.ledger('verdict')][-2:]
            runs = sandbox_runs(began)
            rows.append({'second_began': int(began), 'offset': round(began % 1, 3),
                         'first_seconds': round(first['answered'] - first['sent'], 3), 'second_seconds': round(second['answered'] - second['sent'], 3),
                         'pair_ended_at': round(second['answered'] - int(began), 3), 'names': names, 'same_second': len(names) == 2 and stem(names[0]) == stem(names[1]),
                         'sandbox': [{**s, 'began_at': round(s['begin'] - int(began), 3), 'ended_at': round(s['end'] - int(began), 3)} for s in runs[-2:]]})
    finally:
        r.stop()
    each = [x for row in rows for x in (row['first_seconds'], row['second_seconds'])]
    return {'tries': rows, 'made': sum(row['same_second'] for row in rows), 'of': len(rows), 'submission_seconds': {'least': min(each), 'most': max(each), 'mean': round(sum(each) / len(each), 3)},
            'note': 'both notices are named for the second their run ends in; the pair must end before 1.000'}


def part_b() -> dict:
    with tempfile.TemporaryDirectory(prefix='diag-f17-') as tmp:
        box = pathlib.Path(tmp) / 'inbox'
        s = '20261119T000000Z_FAIL_ff539c34'
        names = [notices.publish(box, s, f'the notice of design {i}\n' + 'x' * 300, numbered=True) for i in (1, 2)]
        files = sorted(p.name for p in box.glob('*.txt'))
        texts = [(box / n).read_text() for n in names]
        out = judge(box, names, [])
        good = out['result'] == 'COLLISION_HANDLED' and files == sorted(names) and [f'design {i}' in t for i, t in zip((1, 2), texts)] == [True, True] \
            and not list(box.glob('.notice.*.part'))
        return dict(out, files=files, each_its_own=[f'design {i}' in t for i, t in zip((1, 2), texts)], result='COLLISION_HANDLED' if good else out['result'] if out['result'] != 'COLLISION_HANDLED' else 'COLLISION_MISHANDLED')


def part_c(tries: int = 6) -> dict:
    r = F.Run('F17diagC'); rows, verdict = [], None
    try:
        box = r.s.home / 'inbox' / r.h[:16]
        jobs = {'a': r.job, 'b': r.s.enrol('job-b', r.h)}                 # two jobs, one baseline, one inbox
        for a, b in F._clashing_pairs(tries):
            time.sleep(1.03 - time.time() % 1)                            # both begin together, early in a second; each takes about half a second
            before = len(r.s.ledger('verdict')); got = {}
            threads = [threading.Thread(target=lambda k=k, d=d: got.update({k: submit(jobs[k], d)})) for k, d in (('a', a), ('b', b))]
            began = time.time()
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            entries = r.s.ledger('verdict')[before:]
            by_hash = {B.design_hash(d)[:16]: d for d in (a, b)}
            designs = [next((d for h, d in by_hash.items() if str(x.get('design_sha256', '')).startswith(h)), None) for x in entries]
            names = [x.get('notice') for x in entries]
            if None in designs:                                           # the ledger does not say which design: read each notice for its own
                designs = [next((d for d in (a, b) if n and (box / n).is_file() and f"wall_mm = {d.get('wall_mm')}" in (box / n).read_text()), {}) for n in names]
            row = dict(judge(box, names, designs), outcomes=[got.get('a', {}).get('outcome'), got.get('b', {}).get('outcome')], pair_ended_at=round(max(v['answered'] for v in got.values()) - int(began), 3),
                       same_hash_start=B.design_hash(a)[:8] == B.design_hash(b)[:8], different_designs=len({json.dumps(d, sort_keys=True) for d in designs}) == 2)
            rows.append(row)
            if row['precondition_met']:
                verdict = row['result'] if row['outcomes'] == ['FAIL', 'FAIL'] and row['same_hash_start'] and row['different_designs'] else 'COLLISION_MISHANDLED'
                break
        files = sorted(p.name for p in box.glob('*.txt')) if box.exists() else []
        ok, why, summ = r.checked()
        whole = len(files) == 2 * len(rows) and ok and summ.get('not_met') == 2 * len(rows)
    finally:
        r.stop()
    result = 'PRECONDITION_NOT_MET' if verdict is None else verdict if whole else 'COLLISION_MISHANDLED'
    return {'result': result, 'tries': rows, 'notices_in_inbox': len(files), 'failures': 2 * len(rows), 'record_verifies': ok, 'why': why}


def main() -> int:
    wanted = [a for a in sys.argv[1:] if a in 'ABC'] or ['A', 'B', 'C']
    out = {'made': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'traced': bool(TRACE)}
    if 'A' in wanted:
        out['A'] = part_a(); print(f"A  timing     the case was made in {out['A']['made']} of {out['A']['of']} tries, F17's way; a submission takes {out['A']['submission_seconds']}")
    for k, f in (('B', part_b), ('C', part_c)):
        if k in wanted:
            out[k] = f(); print(f"{k}  {'component ' if k == 'B' else 'together  '} {out[k]['result']}")
    path = HERE.parent / 'outputs' / 'diag_f17_collision.json'; path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, indent=1, default=str))
    return 0 if all(out[k]['result'] == 'COLLISION_HANDLED' for k in ('B', 'C') if k in out) else 1


if __name__ == '__main__':
    sys.exit(main())
