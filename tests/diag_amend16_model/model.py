"""A small explicit model of the proposed COVERED / NOT COVERED guarantee of Amendment 16, explored exhaustively.

Design and verification only (21 November 2026).  It is not the courier, the mailbox or the witness, and nothing here is
code for them.  It states the proposed rules as a state machine with the service's powers as moves, and checks invariants
in every reachable state up to small bounds.  Variants weaken one rule at a time; each must yield a counterexample, which
shows both why the rule is needed and that the invariants can fail.

    python model.py [variant ...]        with no argument: every variant, results printed and written to out/

THREE GUARANTEES, KEPT APART (none is derived from another anywhere in this file)
  record consistency    more than one distinct signed result for one run is observed and said         (CONFLICT)
  verdict authenticity  a report was signed by a gate key given, for this budget, run and nonce       (all a signature shows)
  verdict correctness   the result agrees with what an authorised check would give                    (NOT modelled as known:
                        the model carries the truth only as a ghost, to exhibit that nothing observable depends on it)

THE WORLD, AT ITS BOUNDS
  Two runs, both truly FAIL (the worst case for notification).  The honest result has digest 'f'; a forged PASS has 'p'.
  Run 0 may carry two reports of either digest; run 1 one honest report (it is "the other run" of a reading).
  The witness records reports, each at a decision (seq).  A result is stored once as a value ('f' or 'p'); a stored value
  is never replaced (shown by test on the deployment, under DP1 and DP3).  A result marked unknown can be replaced and so
  is the same, for everything modelled here, as no result yet: it is not a separate state.
  The mailbox has a clock, t.  The waiting limit is L ticks.

LEFT OUT BECAUSE THEY ADD NO REACHABLE STATE: the courier killed in the middle of a reading (it leaves exactly what not
  having begun leaves); a reading made with no token from the mailbox (it leaves what a reading with one unanswered run
  and a later reading of that run leave).  LEFT OUT AND NOT COVERED BY THE MODEL: a courier that loses its own state; a
  mailbox that loses what it holds; more than two runs; clocks other than the mailbox's.

THE SERVICE'S MOVES (the locked table of the addendum)
  report(r, d)    have a report with digest d recorded for run r: the first is the reconcile, later ones are recorded as
                  duplicates WITH their report (shown by test).  d = 'p' first is the forgery before the witness sees anything.
  store(r, x)     store a value, or not yet.  The first value stored stays.
  no answer       any reading of the witness may go unanswered, as often as the service likes (residual risks R1, R2).
OUTSIDE THE CONTRACT (only in the variant 'owner'): delete a recorded report; replace a stored value.
THE ENVIRONMENT: the mailbox's clock ticks; a notice or statement may wait in the courier's outbox for any time before
it is delivered (a mailbox that is down, or a delivery that fails).

THE PROPOSED RULES (variant 'spec')
  begin    the courier takes a token from the mailbox (the mailbox's clock at that moment) and a checkpoint at decision N
           that signs the token back.
  ask(r)   for every run not final, AND every final run for which the chain to N holds more reconcile decisions than the
           courier saw when it finalised it (the re-read rule).  An answer is used only if it carries one report for each
           reconcile decision of the chain to N (the count rule); reports after N are left out.
           Observation of one run: digests D among its reports to N; conflict iff |D| > 1; the outcome is final (F or P)
           iff a value is stored whose digest is in D; otherwise not final (N).
  end      FAIL notice for a final F; CONFLICT notice for a conflict.  The reading is WHOLE iff every run was observed in
           this reading or was final already with nothing new in the chain; unanswered ('X') and count-mismatch ('M')
           observations make it not whole.  If whole and a token is held: a coverage statement naming the token, N, and
           EVERY notice made so far.
  COVERED  at mailbox time t: the mailbox holds a coverage statement with t - token <= L and holds every notice it names.
           Anything else is NOT COVERED.

GHOSTS (never visible to the courier, the mailbox or a reader; used only by the invariants)
  when each FAIL became committed (report 'f' recorded and value 'f' stored), when each conflict came to exist, on the
  mailbox's clock; whether a coverage statement was made without the observations the definition requires.
"""
import collections, itertools, json, pathlib, sys

R, MAXREP, DIGESTS, N_MAX, T_MAX, L = 2, (2, 1), ('fp', 'f'), 3, 2, 1   # run 0: up to two reports, either digest; run 1: one honest report; the mailbox's clock 0..2; the limit one tick
VARIANTS = {
    'spec': 'the proposed rules',
    'no_detection': 'the eighth form\'s reading of reports: any recorded digest is believed and two digests are not remarked on (S-1)',
    'no_reread': 'conflicts looked for only when a run is read for its outcome: a final run is never asked for again',
    'asked_is_enough': 'a reading counts as whole when every run was asked for, answered or not (the eighth form, D-d)',
    'no_lapse': 'a coverage statement never lapses (the eighth form\'s WATCHING)',
    'receipt_time': 'freshness counted from the mailbox\'s receipt of the statement, as the addendum\'s section 7 words it, not from a token taken before the reading',
    'carry_over': 'the outcome of a run that is not final is carried over from an earlier reading instead of being observed again',
    'names_new_only': 'a coverage statement names only the notices of its own reading, not every notice made so far',
    'no_count_rule': 'the proposed rules without the count rule, with the owner\'s powers (a precondition broken)',
    'owner': 'the proposed rules, with the owner\'s powers (precondition DP1 broken)',
}

# ---- state: a tuple, so that it can be a dictionary key
#   t, n,
#   runs[r]   = (reports, stored, recon, t_fail, t_conf)      reports: tuple of (seq, digest); recon: reconcile decisions in the chain (seqs)
#   cour      = (final, made, reading, outbox, carried)
#     final[r]   = (verdict or '', reports seen when finalised)
#     reading    = None or (token or -1, N, index, obs)        obs[r] in (None, 'X', 'M', (verdict, conflict), 'S' skipped as final)
#     outbox     = frozenset of items;  item = ('FAIL', r) | ('CONFLICT', r) | ('COV', token, N, names)
#     carried[r] = last observation of a run not final (kept only in the variant carry_over)
#   box       = frozenset of (item, t_receipt)        the receipt's time is kept only where a variant uses it
#   bad       = a coverage statement was made that the definition's observations do not support (ghost)
Init = (0, 0, tuple(((), '', (), -1, -1) for _ in range(R)), (tuple(('', 0) for _ in range(R)), frozenset(), None, frozenset(), tuple(None for _ in range(R))), frozenset(), False)


def ghost(reports, stored, t, t_fail, t_conf):
    digs = {d for _, d in reports}
    if t_fail < 0 and stored == 'f' and 'f' in digs:
        t_fail = t
    if t_conf < 0 and len(digs) > 1:
        t_conf = t
    return t_fail, t_conf


def observe(run, N, variant):
    """What the courier concludes from the witness's answer for one run, at checkpoint N."""
    reports, stored, recon, _, _ = run
    upto = [(s, d) for s, d in reports if s <= N]
    if variant not in ('no_count_rule',) and len(upto) != sum(1 for s in recon if s <= N):
        return 'M'                                                    # the answer lacks a report the chain says was recorded
    D = {d for _, d in upto}
    verdict = {'f': 'F', 'p': 'P'}[stored] if stored in D else 'N'
    return (verdict, len(D) > 1, len(upto))


def needs(run, fin, N, variant):
    if not fin[0]:
        return True
    if variant in ('no_reread', 'no_detection'):
        return False
    return sum(1 for s in run[2] if s <= N) > fin[1]                  # the chain holds a reconcile decision the courier has not seen for this run


def moves(st, variant):
    t, n, runs, cour, box, bad = st
    final, made, reading, outbox, carried = cour
    out = []
    # ---------------------------------------------------------------- the service
    for r in range(R):
        reports, stored, recon, tf, tc = runs[r]
        if n < N_MAX and len(reports) < MAXREP[r]:
            for d in DIGESTS[r]:
                rep = reports + ((n + 1, d),); g = ghost(rep, stored, t, tf, tc)
                out.append((f"service: report for run {r} with digest '{d}' recorded at decision {n + 1}" + (' (a duplicate, kept with its report)' if reports else ''),
                            (t, n + 1, runs[:r] + ((rep, stored, recon + (n + 1,), *g),) + runs[r + 1:], cour, box, bad)))
        if stored == '':
            for x in DIGESTS[r]:
                g = ghost(reports, x, t, tf, tc)
                out.append((f"service: stores the value {x!r} for run {r}", (t, n, runs[:r] + ((reports, x, recon, *g),) + runs[r + 1:], cour, box, bad)))
        if variant in ('owner', 'no_count_rule'):
            for i in range(len(reports)):
                rep = reports[:i] + reports[i + 1:]
                out.append((f'OWNER (outside the contract): deletes the report of run {r} at decision {reports[i][0]}', (t, n, runs[:r] + ((rep, stored, recon, tf, tc),) + runs[r + 1:], cour, box, bad)))
            if stored in 'fp' and stored:
                x = 'p' if stored == 'f' else 'f'
                out.append((f'OWNER (outside the contract): replaces the stored value of run {r} by {x!r}', (t, n, runs[:r] + ((reports, x, recon, tf, tc),) + runs[r + 1:], cour, box, bad)))
    # ---------------------------------------------------------------- the environment
    if t < T_MAX:
        out.append((f'the mailbox\'s clock: {t + 1}', (t + 1, n, runs, cour, box, bad)))
    # ---------------------------------------------------------------- the courier
    if reading is None:
        out.append((f"courier: begins a reading; token t={t} from the mailbox; checkpoint at decision {n}",
                    (t, n, runs, (final, made, (t, n, 0, tuple(None for _ in range(R))), outbox, carried), box, bad)))
    if reading is not None:
        token, N, i, obs = reading
        if i < R:
            if not needs(runs[i], final[i], N, variant):
                tries = [('S', f'courier: run {i} is final already and the chain holds nothing new for it; not asked')]
            else:
                o = observe(runs[i], N, variant)
                tries = [('X', f'courier: asks for run {i}; NO ANSWER'),
                         (o, f'courier: asks for run {i}; ' + ('the answer lacks a report the chain says was recorded' if o == 'M' else
                              f"observes outcome {o[0]}{' and two different signed digests' if o[1] else ''}{' (the same digest twice)' if o[2] > 1 and not o[1] else ''}"))]
            for o, label in tries:
                out.append((label, (t, n, runs, (final, made, (token, N, i + 1, obs[:i] + (o,) + obs[i + 1:]), outbox, carried), box, bad)))
        else:
            nf, nm, no, nc = list(final), set(made), set(outbox), list(carried); new = set()
            used = list(obs)
            for r in range(R):
                o = obs[r]
                if variant == 'carry_over' and o == 'X' and carried[r] is not None:
                    used[r] = carried[r]                                # an earlier reading's observation stands in
                o = used[r]
                if isinstance(o, tuple):
                    verdict, conflict, seen = o
                    if verdict in 'FP':
                        nf[r] = (verdict, seen)
                        if verdict == 'F' and ('FAIL', r) not in nm:
                            new.add(('FAIL', r))
                    elif variant == 'carry_over':
                        nc[r] = o
                    if conflict and variant != 'no_detection' and ('CONFLICT', r) not in nm:
                        new.add(('CONFLICT', r))
            nm |= new; no |= new
            whole_spec = all(o == 'S' or isinstance(o, tuple) for o in obs)                      # the definition: observed in THIS reading, or final with nothing new
            whole_var = all(o == 'S' or isinstance(o, tuple) for o in used) if variant != 'asked_is_enough' else all(o in ('S', 'X') or isinstance(o, tuple) for o in obs)
            nb = bad; label = 'courier: ends the reading' + (f"; makes {sorted(new)}" if new else '')
            if whole_var and token >= 0:
                names = frozenset(new) if variant == 'names_new_only' else frozenset(nm)
                no = {x for x in no if x[0] != 'COV'} | {('COV', token, N, names)}
                label += f'; WHOLE: coverage statement to decision {N} with token t={token}, naming {sorted(names)}'
                if not whole_spec:
                    nb = True
            else:
                label += '; not whole, no coverage statement' if not whole_var else '; whole, but no token: no coverage statement'
            out.append((label, (t, n, runs, (tuple(nf), frozenset(nm), None, frozenset(no), tuple(nc)), box, nb)))
    for item in outbox:
        rt = t if (item[0] == 'COV' and variant == 'receipt_time') else 0
        nbx = {x for x in box if not (item[0] == 'COV' and x[0][0] == 'COV')} | {(item, rt)}            # the mailbox's latest statement is the one that counts
        out.append((f'courier: delivers {item}; the mailbox receipts it at t={t}', (t, n, runs, (final, made, reading, outbox - {item}, carried), frozenset(nbx), bad)))
    return out


def covered(st, variant):
    """The coverage statements by which the budget reads COVERED now (an empty list: NOT COVERED)."""
    t, box = st[0], st[4]
    held = {item for item, _ in box if item[0] != 'COV'}
    good = []
    for item, rcpt in box:
        if item[0] == 'COV' and item[3] <= held:
            fresh = True if variant == 'no_lapse' else (t - rcpt <= L) if variant == 'receipt_time' else (t - item[1] <= L)
            if fresh:
                good.append(item)
    return good


def violations(st, variant):
    t, n, runs, cour, box, bad = st
    held = {item for item, _ in box if item[0] != 'COV'}
    out = []
    if bad:
        out.append('OBSERVED: a coverage statement was made without the observations the definition requires')
    for item in cour[1]:                                                   # every notice ever signed is true of the run
        r = item[1]; digs = {d for _, d in runs[r][0]}
        if variant not in ('owner', 'no_count_rule'):                      # (the owner can make a true notice describe a record that no longer shows it)
            if item[0] == 'FAIL' and not (runs[r][3] >= 0):
                out.append(f'TRUE: a FAIL notice for run {r} that was never committed as FAIL')
            if item[0] == 'CONFLICT' and len(digs) < 2:
                out.append(f'TRUE: a CONFLICT notice for run {r}, which does not carry two different digests')
    if covered(st, variant):
        for r in range(R):
            if 0 <= runs[r][3] < t - L and ('FAIL', r) not in held:
                out.append(f'NOTICED: COVERED at t={t}, yet the FAIL of run {r}, committed at t={runs[r][3]}, has no notice in the mailbox')
            if 0 <= runs[r][4] < t - L and ('CONFLICT', r) not in held:
                out.append(f'CONSISTENT: COVERED at t={t}, yet run {r} has carried two different signed digests since t={runs[r][4]} and the mailbox holds no notice of it')
    return out


def explore(variant, limit=14_000_000):
    seen = {Init: None}; queue = collections.deque([Init]); found = {}; witnesses = {}
    while queue:
        st = queue.popleft()
        for v in violations(st, variant):
            found.setdefault(v.split(':')[0], (v, st))
        cov = covered(st, variant)
        if cov and not violations(st, variant):
            runs, final = st[2], st[3][0]
            for r in range(R):
                digs = [d for _, d in runs[r][0]]
                if final[r][0] == 'P' and digs == ['p']:
                    witnesses.setdefault('COVERED while a truly failed run stands as PASS on one authentic report (the forgery before the witness): correctness is not guaranteed', st)
                if len(digs) == 2 and len(set(digs)) == 1 and ('CONFLICT', r) not in st[3][1] and final[r][0]:
                    witnesses.setdefault('COVERED with a run that carries the same digest twice and no CONFLICT notice: a repeat is not a conflict', st)
                if len(set(digs)) == 2 and ('CONFLICT', r) in {i for i, _ in st[4]}:
                    witnesses.setdefault('COVERED with a CONFLICT notice held for a run with two different digests: the conflict is said, which result is true is not', st)
        if not cov and st[0] >= 2 and any(x[0][0] == 'COV' for x in st[4]) and all(r_[3] < 0 for r_ in st[2]):
            witnesses.setdefault('NOT COVERED with no run failed: a statement has lapsed, and nothing says or implies a FAIL', st)
        for label, nx in moves(st, variant):
            if nx not in seen:
                seen[nx] = st; queue.append(nx)                     # the state it was reached from; the step's words are found again when a trace is printed
                if len(seen) > limit:
                    return {'variant': variant, 'states': len(seen), 'complete': False, 'violations': found, 'witnesses': witnesses, 'seen': seen}
    return {'variant': variant, 'states': len(seen), 'complete': True, 'violations': found, 'witnesses': witnesses, 'seen': seen}


def trace(seen, st, variant):
    steps = []
    while seen[st] is not None:
        prev = seen[st]
        steps.append(next(label for label, nx in moves(prev, variant) if nx == st)); st = prev
    return steps[::-1]


def never_covered_again(variant='spec'):
    """Liveness is not promised: if the service lets no reading of a run be answered, is COVERED ever reached?"""
    seen = {Init}; queue = collections.deque([Init])
    while queue:
        st = queue.popleft()
        if covered(st, variant):
            return {'states': len(seen), 'COVERED ever reached while no reading of a run is answered': True}
        for label, nx in moves(st, variant):
            if 'asks for run' in label and 'NO ANSWER' not in label:
                continue                                                   # the service lets no reading of a run be answered
            if nx not in seen:
                seen.add(nx); queue.append(nx)
    return {'states': len(seen), 'COVERED ever reached while no reading of a run is answered': False}


if __name__ == '__main__':
    names = sys.argv[1:] or list(VARIANTS)
    outdir = pathlib.Path(__file__).resolve().parent / 'out'; outdir.mkdir(exist_ok=True); path = outdir / 'model_results.json'
    report = json.loads(path.read_text()) if path.exists() else {}
    report['bounds'] = {'runs': R, 'reports per run': list(MAXREP), 'decisions': N_MAX, 'ticks of the mailbox clock': T_MAX, 'waiting limit L': L}
    report.setdefault('variants', {})
    for v in names:                                                         # one variant for each process is kinder to memory: see run_all.sh
        res = explore(v)
        entry = {'what': VARIANTS[v], 'states': res['states'], 'explored to the end': res['complete'], 'invariants broken': {}, 'witnesses': {}}
        print(f"\n=== {v}: {VARIANTS[v]}\n    states {res['states']}{'' if res['complete'] else ' (STOPPED AT THE LIMIT: not exhaustive)'}; invariants broken: {sorted(res['violations']) or 'none'}")
        for k, (msg, st) in sorted(res['violations'].items()):
            tr = trace(res['seen'], st, v); entry['invariants broken'][k] = {'what': msg, 'shortest trace': tr}
            print(f'  -- {msg}\n     shortest trace ({len(tr)} steps):'); [print(f'       {i + 1:2d}. {s_}') for i, s_ in enumerate(tr)]
        if v == 'spec':
            for k, st in res['witnesses'].items():
                tr = trace(res['seen'], st, v); entry['witnesses'][k] = tr
                print(f'  .. reachable, with every invariant holding: {k}\n     trace ({len(tr)} steps):'); [print(f'       {i + 1:2d}. {s_}') for i, s_ in enumerate(tr)]
            del res
            entry['liveness'] = never_covered_again(); print('  .. liveness:', entry['liveness'])
        report['variants'][v] = entry
        path.write_text(json.dumps(report, indent=1)); sys.stdout.flush()
