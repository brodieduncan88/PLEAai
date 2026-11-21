"""Targeted adversarial test of the courier at commit e25a297 (Amendment 16, eighth form), asked for by the owner on
21 November 2026.  Development evidence only; not a declared test.

    python adv.py SRC SCENARIO OUTDIR

The real courier (SRC/verify/courier.py) is driven in process against the stand-in witness and the real mailbox class
(SRC/tests/notify_standin.py).  The pass clock is simulated: a pass every 100 seconds, the waiting time (stall_after) 900
seconds, the courier's default.  "The witness stops responding and then resumes" is the stand-in's 'knocks': the answer
for one run is dropped while it is read, the next request (the courier's question whether the witness is up) is refused,
and from the request after that the witness answers again.

Scenarios:
  T1a  the witness stops and resumes in the middle of every pass, at a run of the old line; an older failed run and a new
       failed run at every pass wait behind it.
  T1b  the witness stops and resumes at a newly arrived run in every pass; an older failed run, after which it once
       stopped and which is readable again, waits behind them.
  T1c  as T1a from the very first pass: no pass has ever completed, no statement of coverage exists.
  T1d  the witness answers nothing at all for twelve passes, then answers again.
  T1e  as T1a, with the mailbox not answering when the alarm falls due.
  T1f  the witness answers nothing from the first pass the courier ever makes: nothing of the budget has ever been read.
  T2   adaptive: the witness stops and resumes in the middle of eight passes, then answers one whole pass slowly, and
       so on; an older failed run and a new failed run wait behind slow runs.  This one runs in real time, with the
       deadline of a request and the time of a pass scaled down (0.5 s and 4 s for 60 s and 600 s: the same floor of 2).
  Ka   as T1a, the courier process killed (os._exit in a forked child, no clean-up) before the state holding the alarm
       is saved.
  Kb   as T1a, killed after that save and before the alarm is sent.

Every request the stand-in receives, and what came of it, is appended to a file as it happens, so that what a killed
process asked for is not lost with it.  check.py and check_t2.py read the results in a process of their own.
"""
import json, os, pathlib, re, sys, time, urllib.error, urllib.parse

SRC, SCEN, OUT = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
sys.path[:0] = [SRC + '/tests', SRC, SRC + '/verify']
import notify_standin as S                                  # noqa: E402
import courier                                              # noqa: E402
import check_record as C                                    # noqa: E402

STALL, EVERY = 900.0, 100.0


class W(S.World):
    """The stand-in world, with what came of every request written down."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k); self.log = []; self.logfile = self.tmp / 'requests.jsonl'

    def note(self, row):
        self.log.append(row)
        with open(self.logfile, 'a') as f:
            f.write(json.dumps(row) + '\n'); f.flush(); os.fsync(f.fileno())

    def urlopen(self, req, timeout=None, context=None):
        u = urllib.parse.urlsplit(req.full_url); q = dict(urllib.parse.parse_qsl(u.query, keep_blank_values=True))
        who, aid = ('mailbox' if u.netloc == 'm' else 'witness'), q.get('aid')
        mode = self.trouble.get(aid) if u.path == '/run' else None
        try:
            ans = super().urlopen(req, timeout, context)
        except urllib.error.HTTPError as e:
            self.note([who, u.path, aid, f'answered {e.code}']); raise
        except Exception as e:
            self.note([who, u.path, aid, f'no answer ({type(e).__name__})']); raise
        self.note([who, u.path, aid, 'dropped while read' if mode in ('knocks', 'dies', 'dropped') else 'answered slowly' if mode == 'hangs' else 'answered'])
        return ans


def one(w, p, clock, note=''):
    """One pass; what happened in it."""
    n0 = len(w.log); t0 = time.monotonic()
    summary = w.run(clock)
    st = w.state(); b = w.status()['budgets'][S.ROOT]
    reqs = w.log[n0:]
    runs = [r for r in reqs if r[0] == 'witness' and r[1] == '/run']
    rec = {'pass': p, 'clock': clock, 'note': note, 'ended': (st.get('last_pass') or {}).get('ended'), 'how': (st.get('last_pass') or {}).get('why'),
           'exit': 1 if courier.failed(summary) else 0, 'asked': [[r[2], r[3]] for r in runs],
           'after_last_run': [[r[1], r[3]] for r in reqs[(max(i for i, r in enumerate(reqs) if r[0] == 'witness' and r[1] == '/run') + 1) if runs else 0:] if r[0] == 'witness'],
           'made': [[x['aid'], x['outcome']] for x in summary['made']], 'delivered': [[x['aid'], x['outcome']] for x in summary['delivered']],
           'coverage_events': [[c.get('state'), c.get('seq')] for c in summary.get('coverage', [])],
           'put_off': sum(x.get('runs', 0) for x in summary.get('put_off', [])),
           'unfinished_since': st.get('unfinished_since'), 'blocked_sent': bool(st.get('blocked_sent')), 'outbox': [[r['notice']['aid'], r['notice']['outcome'], r.get('last')] for r in st.get('outbox', [])],
           'witness_answers_again': (w.refuse_next == 0 and not w.down), 'status_coverage': b.get('coverage'), 'status_courier': b.get('courier'),
           'status_bound': ((b.get('lines') or {}).get('a run of the old line is asked for at least once in every')), 'real_seconds': round(time.monotonic() - t0, 3)}
    return rec


def held(w):
    return [{'aid': x['notice']['aid'], 'outcome': x['notice']['outcome'], 'made': x['notice']['time'], 'received': x['receipt']['time'], 'text': x['notice']['text'],
             'notice_ok': C.notice_problems(x['notice'], [w.ckey.public_hex]), 'receipt_ok': C.receipt_problems(x['receipt'], [w.mkey.public_hex], x['notice']),
             'seq': x['notice']['seq'], 'form': x['notice'].get('form')} for x in w.box.held()]


def base(w, n_knockers, old_fail=True):
    """The chain before the trouble: runs in flight (the ones that will stop the witness), an older run whose effect the gate
    has signed and whose result is not yet stored, and an older run in flight that will come to say FAIL."""
    att = [[f'a-{i:02d}', f'verify:a{i}', 'CONSUMED', f'n-a{i}', True, True] for i in range(n_knockers)]
    if old_fail:
        att.append(['y-old-fail', 'verify:y', 'CONSUMED', 'n-y', True, True])
        att.append(['z-old-fail', 'verify:z', 'EFFECT', 'n-z', True, True])
    w.decide(att, ('CROSS', 'z'))
    if old_fail:
        w.report('z-old-fail', 'n-z', 'EFFECT', S.FAIL); w.runs['z-old-fail']['request_key'] = 'verify:z'
    return att


def fail_old(w, att):
    """The older runs fail: z-old-fail's stored result appears (its entry in the chain does not change); y-old-fail's entry comes to say an effect, FAIL."""
    w.store('z-old-fail', S.FAIL)
    for a in att:
        if a[0] == 'y-old-fail':
            a[2] = 'EFFECT'
    w.decide(att, ('RECONCILE', 'y-old-fail')); w.report('y-old-fail', 'n-y', 'EFFECT', S.FAIL); w.store('y-old-fail', S.FAIL); w.runs['y-old-fail']['request_key'] = 'verify:y'


def finish(w, recs, extra=None):
    OUT.mkdir(parents=True, exist_ok=True)
    out = {'scenario': SCEN, 'commit_src': SRC, 'stall_after': STALL, 'pass_every': EVERY, 'passes': recs, 'mailbox': held(w),
           'keys': {'courier': w.ckey.public_hex, 'mailbox': w.mkey.public_hex, 'witness': w.wkey.public_hex}, 'dirs': {'state': str(w.tmp / 'state'), 'mailbox': str(w.box.dir)}}
    out.update(extra or {})
    (OUT / f'{SCEN}.json').write_text(json.dumps(out, indent=1))
    for r in recs:
        asked = ' '.join(f"{a}{'' if res == 'answered' else '[' + res + ']'}" for a, res in r['asked'])
        print(f"p{r['pass']:>2} t={int(r['clock']):>5} {r['ended']:<8} exit {r['exit']} since={r['unfinished_since']} sent={int(r['blocked_sent'])} "
              f"made={r['made']} delivered={r['delivered']} put_off={r['put_off']} {r['note']}\n      asked: {asked[:230]}")
    print('MAILBOX:'); [print('  ', m['made'], m['received'], repr(m['aid']), m['outcome'], 'sig', not m['notice_ok'], 'receipt', not m['receipt_ok']) for m in out['mailbox']]
    return out


def t1a(first_pass_ever=False, mailbox_down=(), kill=None):
    w = W(stall_after=STALL); recs = []
    att = base(w, 12)
    if not first_pass_ever:
        recs.append(one(w, 0, 0.0, 'before the trouble: the witness answers'))
    for p in range(1, 16):
        clock = EVERY * p
        if p == 1:
            fail_old(w, att)
        w.effect(att, f'n-{p:02d}-fail', S.FAIL)                       # a new failed run arrives at every pass
        for i in range(12):
            w.trouble[f'a-{i:02d}'] = 'knocks'                         # asked for one of these, the witness stops, then resumes
        w.down_for = 1
        w.mailbox_up = p not in mailbox_down
        if kill and p == kill[0]:
            recs.append(killed_pass(w, p, clock, kill[1])); continue
        recs.append(one(w, p, clock, 'mailbox not answering' if p in mailbox_down else ''))
    return w, recs


def killed_pass(w, p, clock, point):
    """The pass run in a forked child that dies with os._exit (no finally, no clean-up) at `point`."""
    n_before = len(w.logfile.read_text().splitlines()) if w.logfile.exists() else 0
    pid = os.fork()
    if pid == 0:
        try:
            if point == 'before the state holding the alarm is saved':
                orig = courier.alarm
                def alarm(*a, **k):
                    orig(*a, **k); os._exit(137)                       # the alarm is in memory only
                courier.alarm = alarm
            else:                                                      # after the save that holds the alarm and its mark, before anything is sent
                orig = courier.end_blocked
                def end_blocked(*a, **k):
                    r = orig(*a, **k)
                    st = a[3]
                    if st.get('blocked_sent'):
                        os._exit(137)
                    return r
                courier.END['blocked'] = end_blocked
            w.run(clock)
        finally:
            os._exit(0)
    _, status = os.waitpid(pid, 0)
    st = w.state()
    reqs = [json.loads(l) for l in w.logfile.read_text().splitlines()[n_before:]]
    runs = [r for r in reqs if r[0] == 'witness' and r[1] == '/run']
    last = max((i for i, r in enumerate(reqs) if r[0] == 'witness' and r[1] == '/run'), default=-1)
    return {'pass': p, 'clock': clock, 'note': f'KILLED {point}: child exit {os.waitstatus_to_exitcode(status)}', 'ended': 'killed', 'how': None, 'exit': None,
            'asked': [[r[2], r[3]] for r in runs], 'after_last_run': [[r[1], r[3]] for r in reqs[last + 1:] if r[0] == 'witness'], 'taken_by_mailbox_in_child': [r for r in reqs if r[0] == 'mailbox'],
            'made': [], 'delivered': [], 'coverage_events': [], 'put_off': 0, 'unfinished_since': st.get('unfinished_since'), 'blocked_sent': bool(st.get('blocked_sent')),
            'outbox': [[r['notice']['aid'], r['notice']['outcome'], r.get('last')] for r in st.get('outbox', [])], 'witness_answers_again': True,
            'status_coverage': None, 'status_courier': None, 'status_bound': None, 'real_seconds': None}


def t1b():
    w = W(stall_after=STALL); recs = []
    att = [[f'o-{i}', f'verify:o{i}', 'CONSUMED', f'n-o{i}', True, True] for i in range(4)]
    w.decide(att, ('CROSS', 'o')); recs.append(one(w, 0, 0.0, 'before the trouble'))
    for p in range(1, 17):
        clock = EVERY * p
        name = 'h-old-fail' if p == 1 else f'f-{p:02d}-fail'
        w.effect(att, name, S.FAIL)                                    # a failed run arrives; asked for it, the witness stops, then resumes
        for k in list(w.trouble):
            w.trouble[k] = None                                        # every run that stopped the witness before is readable again
        w.trouble[name] = 'knocks'; w.down_for = 1
        recs.append(one(w, p, clock))
    return w, recs


def t1d():
    w = W(stall_after=STALL); recs = []
    att = base(w, 2); recs.append(one(w, 0, 0.0, 'before the trouble'))
    for p in range(1, 16):
        clock = EVERY * p
        if p == 1:
            fail_old(w, att)
        w.effect(att, f'n-{p:02d}-fail', S.FAIL)
        w.down = 1 <= p <= 12
        recs.append(one(w, p, clock, 'the witness answers nothing' if w.down else 'the witness answers again'))
    return w, recs


def t1f():
    """The witness answers nothing from the first pass the courier ever makes: nothing of this budget has ever been read."""
    w = W(stall_after=STALL); recs = []
    att = base(w, 2); fail_old(w, att)
    for p in range(0, 13):
        w.down = True
        recs.append(one(w, p, EVERY * p, 'the witness answers nothing'))
    return w, recs


def t2():
    """Adaptive.  Eight passes in which the witness stops and resumes at the first run asked of the old line; then one pass
    in which it answers everything, slowly; and so on.  Times of asking are scaled: a request's deadline 0.5 s and the
    pass's time for asking 4 s stand for the courier's 60 s and 600 s (the same ratio, so the same floor of 2 runs)."""
    courier.DEADLINE = 0.5
    w = W(stall_after=STALL); w.cfg['pass_seconds'] = 4.0; w.hang = 0.2; recs = []
    att = base(w, 70)
    recs.append(one(w, 0, 0.0, 'before the trouble'))
    slow_new = [f's-{i:02d}' for i in range(20)]
    for p in range(1, 46):
        clock = EVERY * p
        if p == 1:
            fail_old(w, att)
            for s in slow_new:
                w.effect(att, s, S.PASS)                               # twenty new runs that answer slowly (they pass), named in the chain before the new failed run
            w.effect(att, 'n-new-fail', S.FAIL)                        # then a new failed run
        whole = p % 9 == 0                                             # every ninth pass the witness answers the whole pass, slowly
        for a in att:
            aid = a[0]
            if aid.startswith('a-'):
                w.trouble[aid] = 'hangs' if whole else 'knocks'
            elif aid.startswith('s-'):
                w.trouble[aid] = 'hangs'
        w.down_for = 1
        recs.append(one(w, p, clock, 'the witness answers the whole pass, slowly' if whole else ''))
        if any(m == ['n-new-fail', 'FAIL'] for m in recs[-1]['made']) and any(x['aid'] == 'z-old-fail' and x['outcome'] == 'FAIL' for x in held(w)):
            break
    return w, recs


if SCEN == 'T1a':
    w, recs = t1a()
elif SCEN == 'T1c':
    w, recs = t1a(first_pass_ever=True)
elif SCEN == 'T1e':
    w, recs = t1a(mailbox_down=(9, 10, 11, 12))
elif SCEN == 'T1b':
    w, recs = t1b()
elif SCEN == 'T1d':
    w, recs = t1d()
elif SCEN == 'T1f':
    w, recs = t1f()
elif SCEN == 'T2':
    w, recs = t2()
elif SCEN == 'Ka':
    w, recs = t1a(kill=(10, 'before the state holding the alarm is saved'))
elif SCEN == 'Kb':
    w, recs = t1a(kill=(10, 'after the state holding the alarm and its mark is saved, before anything is sent'))
else:
    raise SystemExit('unknown scenario')
finish(w, recs)
