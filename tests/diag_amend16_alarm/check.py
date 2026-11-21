"""Checks the adversarial test's results in a process of its own: reads what the courier and the mailbox left on disk,
verifies the signatures, and tests each sentence of the alarm against what the stand-in witness recorded.

    python check.py SRC OUTDIR SCENARIO [...]
"""
import json, pathlib, re, sys, calendar, time

SRC, OUT = sys.argv[1], pathlib.Path(sys.argv[2])
sys.path[:0] = [SRC, SRC + '/verify']
import check_record as C                                    # noqa: E402

STALL, EVERY = 900.0, 100.0


def secs(t):
    return calendar.timegm(time.strptime(t, '%Y-%m-%dT%H:%M:%SZ'))


def from_disk(d):
    """What the mailbox holds and what the courier's state and log of deliveries hold, read from the files."""
    box = []
    for p in sorted(pathlib.Path(d['dirs']['mailbox']).glob('*.json')):
        x = json.loads(p.read_text())
        box.append({'notice': x['notice'], 'receipt': x['receipt'],
                    'notice_problems': C.notice_problems(x['notice'], [d['keys']['courier']]),
                    'receipt_problems': C.receipt_problems(x['receipt'], [d['keys']['mailbox']], x['notice']),
                    'readable_copy': (p.with_suffix('.txt')).exists()})
    sd = pathlib.Path(d['dirs']['state'])
    state = json.loads((sd / 'state.json').read_text())['roots']
    log = [json.loads(l) for l in (sd / 'deliveries.jsonl').read_text().splitlines() if l.strip()] if (sd / 'deliveries.jsonl').exists() else []
    return box, next(iter(state.values())), log


def check(scen):
    d = json.loads((OUT / f'{scen}.json').read_text()); P = d['passes']
    box, state, log = from_disk(d)
    res, say = {}, []
    alarms = [x for x in box if x['notice']['outcome'].startswith('COURIER_')]
    watching = [x for x in box if x['notice']['outcome'] == 'WATCHING']
    trouble = [r for r in P if r['ended'] in ('blocked', 'killed', 'failed', 'stopped')]
    first_bad = trouble[0]['clock'] if trouble else None
    say.append(f"scenario {scen}: {len(P)} passes, clocks {int(P[0]['clock'])}..{int(P[-1]['clock'])}; first pass that did not complete: t={first_bad}")
    say.append(f"  signatures from disk: {len(box)} notices held by the mailbox; notices whose courier signature fails: {sum(bool(x['notice_problems']) for x in box)}; "
               f"receipts that fail: {sum(bool(x['receipt_problems']) for x in box)}; readable copies present: {sum(x['readable_copy'] for x in box)}; lines in the courier's log of deliveries: {len(log)}")
    say.append(f"  alarms held by the mailbox: {[(x['notice']['outcome'], secs(x['notice']['time'])) for x in alarms]}")
    res['one alarm'] = len(alarms) == 1
    if alarms:
        a = alarms[0]; n = a['notice']; made = secs(n['time'])                # the pass whose clock the notice's time bears
        made_pass = [r for r in P if r['clock'] <= made][-1]
        made_clock = made_pass['clock']
        # the deadline: the waiting time after the first pass of the streak of unfinished passes the alarm belongs to
        streak_start = made_clock
        for r in reversed([r for r in P if r['clock'] <= made_clock]):
            if r['ended'] in ('blocked', 'killed', 'failed'):
                streak_start = r['clock']
            else:
                break
        deadline = streak_start + STALL
        delivered_pass = next((r for r in P if ['', n['outcome']] in r['delivered']), None)
        text = n['text']; lines = text.split('\n')
        say.append(f"  ALARM {n['outcome']}: streak of unfinished passes began t={streak_start}; deadline t={deadline}; made at pass clock t={made_clock} (notice time {n['time']} = {made}); "
                   f"late by {made_clock - deadline:+.0f} s; taken by the mailbox in the pass at t={delivered_pass['clock'] if delivered_pass else None}")
        res['alarm made at the first pass at or after the deadline'] = deadline <= made_clock < deadline + EVERY or (scen == 'Ka' and made_clock == deadline + EVERY)
        res['alarm signed by the courier key (from disk)'] = not a['notice_problems']
        res['alarm held by the mailbox with a valid receipt (from disk)'] = not a['receipt_problems']
        res['alarm in the courier log of deliveries (from disk)'] = any(C.notice_digest(x['notice']) == C.notice_digest(n) for x in log)
        res['state on disk marks the alarm as sent'] = bool(state.get('blocked_sent')) or state.get('unfinished_since') is None
        say.append('  alarm text:'); say += ['    | ' + l for l in lines]
        # ---- each sentence against what the stand-in recorded
        m = re.search(r'has been completed for (\d+) seconds by its clock', text)
        N = int(m.group(1)) if m else None
        done_before = [r['clock'] for r in P if r['ended'] == 'read' and r['clock'] < made_clock]
        last_done = max(done_before) if done_before else None
        gap = (made_clock - last_done) if last_done is not None else None
        res['"no pass completed for N seconds": N is no more than the time since the last completed pass'] = N is not None and (gap is None or N <= gap) and N == made_clock - streak_start
        say.append(f"    N in the text {N}; last completed pass t={last_done}; time since it {gap}; made - streak start {made_clock - streak_start:.0f}")
        the_pass = made_pass                                          # a killed pass too: what its child asked was written to a file
        if 'the witness stopped answering after the courier asked it for run' in text:
            named = re.search(r'asked it for run "([^"]*)"', text).group(1)
            src_pass = the_pass
            asked = src_pass['asked']
            res['the run named is the last the courier asked for in that pass, and its answer was dropped'] = bool(asked) and asked[-1][0] == named and asked[-1][1] != 'answered'
            res['after it the witness did not answer the next request'] = bool(src_pass['after_last_run']) and src_pass['after_last_run'][0][1].startswith('no answer')
            res['the runs asked for before it in that pass were answered'] = all(x[1].startswith('answered') for x in asked[:-1])
            res['no run was asked for after it in that pass'] = asked[-1][0] == named
            say.append(f"    run named {named!r}; asked in that pass: {asked}; after it: {src_pass['after_last_run']}")
        if 'has not been able to read the witness' in text:
            src_pass = the_pass
            res['in that pass the witness answered nothing'] = not src_pass['asked']
            res['provenance: the courier had read something of this budget before (decision > 0)'] = n['seq'] > 0
            say.append(f"    in that pass: runs asked {src_pass['asked']}; how it ended: {src_pass['how']}")
        last = lines[-1]
        seq = int(re.search(r'read to decision (\d+)', last).group(1))
        res['provenance: "read to decision N" is the decision the courier had read'] = seq == n['seq']
        res['provenance: in the pass that made the alarm the witness gave the courier something'] = bool(the_pass['asked'])
        say.append(f"    last line: {last[:150]}...")
    # ---- coverage statements
    say.append(f"  statements of coverage (WATCHING) held: {[secs(x['notice']['time']) for x in watching]}; passes that completed: {[int(r['clock']) for r in P if r['ended'] == 'read']}")
    res['no statement of coverage was made in a pass that did not complete'] = all(any(r['ended'] == 'read' and r['clock'] <= secs(x['notice']['time']) < r['clock'] + EVERY for r in P) for x in watching)
    # ---- the failure notices
    fails = {x['notice']['aid']: secs(x['notice']['time']) for x in box if x['notice']['outcome'] == 'FAIL'}
    for aid in ('z-old-fail', 'y-old-fail', 'n-01-fail', 'n-new-fail', 'h-old-fail'):
        if any(aid in str(r['asked']) or aid in str(r['made']) for r in P) or aid in fails:
            t = fails.get(aid); when = [r['clock'] for r in P if r['clock'] <= t][-1] if t else None
            say.append(f"  failure notice of {aid}: {'made at pass t=%d (%d s after it could first be read, t=100)' % (when, when - 100) if t else 'NOT MADE within the passes run'}")
    kinds = {}
    for x in box:
        kinds[x['notice']['outcome']] = kinds.get(x['notice']['outcome'], 0) + 1
    say.append(f"  every notice signed and held: {kinds}")
    un = [x for x in box if x['notice']['outcome'] == 'UNREADABLE']
    if un:
        say.append('  one UNREADABLE notice, whole:'); say += ['    | ' + l[:260] for l in un[0]['notice']['text'].split('\n')]
    return res, say


overall = {}
for scen in sys.argv[3:]:
    res, say = check(scen)
    print('\n'.join(say))
    for k, v in res.items():
        print(f"  [{'ok' if v else 'NOT SO'}] {k}")
    overall[scen] = res
    print()
(OUT / 'check.json').write_text(json.dumps(overall, indent=1))
