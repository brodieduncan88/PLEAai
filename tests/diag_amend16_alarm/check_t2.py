"""The adaptive scenario's signed statements, each tested against what the stand-in witness recorded (read from disk)."""
import json, pathlib, re, sys, calendar, time, textwrap
SRC, OUT, SCEN = sys.argv[1], pathlib.Path(sys.argv[2]), sys.argv[3]
sys.path[:0] = [SRC, SRC + '/verify']
import check_record as C
secs = lambda t: calendar.timegm(time.strptime(t, '%Y-%m-%dT%H:%M:%SZ'))
d = json.loads((OUT / f'{SCEN}.json').read_text()); P = d['passes']
box = [json.loads(p.read_text()) for p in sorted(pathlib.Path(d['dirs']['mailbox']).glob('*.json'))]
box.sort(key=lambda x: secs(x['notice']['time']))
bad = sum(bool(C.notice_problems(x['notice'], [d['keys']['courier']])) or bool(C.receipt_problems(x['receipt'], [d['keys']['mailbox']], x['notice'])) for x in box)
print(f"{SCEN}: {len(box)} notices held by the mailbox; signature or receipt failures: {bad}")
def pass_at(t):
    return [r for r in P if r['clock'] <= t][-1]
# ---- 1. every UNREADABLE notice
un = [x['notice'] for x in box if x['notice']['outcome'] == 'UNREADABLE']
print(f"\nUNREADABLE notices: {len(un)}.  One, whole:")
for l in un[0]['text'].split('\n'):
    print(textwrap.fill(l, 150, initial_indent='  | ', subsequent_indent='  |   '))
ok_last = ok_between = ok_since = 0; notes = []
for n in un:
    aid, made = n['aid'], secs(n['time'])
    m = re.search(r'When the courier last asked for this run, at (\S+Z) by its clock, the witness stopped answering', n['text'])
    if not m:
        notes.append(f"  {aid}: no 'last asked' sentence: {n['text'].splitlines()[2][:200]}"); continue
    t_last = secs(m.group(1)); r = pass_at(t_last)
    asked = r['asked']
    a = bool(asked) and asked[-1][0] == aid and not asked[-1][1].startswith('answered')
    b = not any(aid == x[0] for q in P if t_last + 99 < q['clock'] <= made and q is not r for x in q['asked'])
    ok_last += a; ok_between += b
    if not (a and b):
        notes.append(f"  {aid}: made t={made}, says last asked t={t_last}; that pass asked {asked[-3:]}; asked again before the notice: {not b}")
    s = re.search(r'has not been able to read this run since (\S+Z)', n['text'])
    if s:
        t_since = secs(s.group(1))
        # true if no reading of this run succeeded from t_since to the notice
        read_ok = [q['clock'] for q in P if t_since <= q['clock'] <= made for x in q['asked'] if x[0] == aid and x[1].startswith('answered')]
        ok_since += not read_ok
        if read_ok: notes.append(f"  {aid}: says not read since t={t_since}, but the stand-in answered it whole at {read_ok}")
print(f"  'when last asked, the witness stopped answering' true of the stand-in's record: {ok_last} of {len(un)}")
print(f"  not asked again between that and the notice: {ok_between} of {len(un)}")
print(f"  'not been able to read this run since T': no whole answer between T and the notice: {ok_since} of {sum('has not been able to read this run since' in n['text'] for n in un)}")
print('\n'.join(notes) if notes else '  (no exceptions)')
# ---- 2. what was signed during the delays, and what was not
fails = {x['notice']['aid']: secs(x['notice']['time']) for x in box if x['notice']['outcome'] == 'FAIL'}
print(f"\nFAIL notices: {dict((k, pass_at(v)['clock']) for k, v in fails.items())}")
for aid in ('n-new-fail', 'z-old-fail', 'y-old-fail'):
    t = pass_at(fails[aid])['clock']
    asks = [(q['clock'], x[1]) for q in P for x in q['asked'] if x[0] == aid]
    print(f"  {aid}: stand-in was asked for it at {asks}; FAIL made t={t}")
    between = [x['notice'] for x in box if 100 <= secs(x['notice']['time']) < t]
    kinds = {}
    for n in between: kinds[n['outcome']] = kinds.get(n['outcome'], 0) + 1
    names = any(aid in n['text'] for n in between)
    general = [n['outcome'] for n in between if n['outcome'].startswith('COURIER_') or n['outcome'] == 'WATCHING']
    print(f"    signed and held by the mailbox from t=100 until then: {kinds}; any of them names {aid}: {names}; any that speaks of the budget or the passes as a whole: {general or 'none'}")
print(f"\nWATCHING (coverage) statements: {[secs(x['notice']['time']) for x in box if x['notice']['outcome'] == 'WATCHING']}; passes that read every run not done (exit 0): {[r['clock'] for r in P if r['exit'] == 0]}")
DEC = re.compile(r'read to decision (\d+)')
same = all(int(DEC.search(x['notice']['text']).group(1)) == x['notice']['seq'] for x in box)
print("decision named in each notice's last line is the decision recorded in the notice:", same)
# ---- 3. the status (local, not signed) at four passes
print("\nStatus (local, not signed):")
for t in (800, 900, 1700, 2600, 3500):
    r = pass_at(t)
    print(f"  t={t}: ended {r['ended']} / exit {r['exit']} / unfinished_since {r['unfinished_since']}")
    for k in ('status_coverage', 'status_bound', 'status_courier'):
        v = r.get(k)
        for l in (v if isinstance(v, list) else [v]):
            print(textwrap.fill(str(l), 160, initial_indent=f'      {k[7:]}: ', subsequent_indent='          '))
