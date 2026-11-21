"""Design gate, part B (21 November 2026): the UNKNOWN report and the verdict transitions.
B1  does an honest gate host sign an UNKNOWN report, and what does the witness record?  (a run cut off; the host restarted)
B2  can an honest gate sign UNKNOWN and then a verdict for one run?  (a host stalled, not dead; a second host takes its state over)
B3  every sequence of up to three gate-signed reports for one run, through the real witness: what is recorded, what is
    kept, and what the Step 2 rule and e25a297 make of it.
No code is changed.  DIAG_DB=<fresh database> python gate_unknown.py SRC OUT [B1,B2,B3]"""
import itertools, signal, sqlite3, subprocess, threading
from gate_common import *                                      # noqa: F401,F403
from plea_gateway import GateHostClient, Governor              # noqa: E402
import deploy                                                  # noqa: E402

PARTS = (sys.argv[3] if len(sys.argv) > 3 else 'B1,B2,B3').split(',')


def view(b, a, stored_value=None):
    st, ans, reports = b.reports_of(a); chain = b.chain(); ops = {d['seq']: d for d in chain}; phase = b.phase(a['aid'])
    D = verdict_pairs(reports)
    return {'phase': phase, 'reports the reading gives': [(x['seq'], x['claim'], x['digest'][:8], 'authentic' if x['authentic'] else 'NOT authentic', ops[x['seq']]['op'][2:] + [ops[x['seq']]['kind'], ops[x['seq']]['code']]) for x in reports],
            'e25a297 run_outcome': C.run_outcome(phase, (ans or {}).get('evidence') or [], stored_value, [b.GATE], b.root, a['aid'], a['nonce']),
            'set D of distinct verdict pairs': D, 'conflict': len(D) > 1, 'an UNKNOWN report beside a verdict report': any(x['claim'] == 'UNKNOWN' and x['authentic'] for x in reports) and bool(D)}


def courier(b, name):
    code, summary = b.s.courier([b.root], 900, name)
    return {'exit': code, 'made': [(m.get('aid', '')[:12], m.get('outcome')) for m in summary.get('made', [])] if isinstance(summary, dict) and 'made' in summary else summary}


def record_view(b, a):
    try:
        rec = b.r.record(); ok, checks, summary = C.verify(rec, b.s.keys)
    except Exception as exc:
        return {'record could not be made or checked': f'{type(exc).__name__}: {str(exc)[:200]}'}
    att = next((x for x in rec.get('attempts', []) if x.get('aid') == a['aid']), None) or {}
    return {'record verifies at e25a297': ok, 'checks that fail': [f'{n} {t}: {d}'[:260] for n, t, good, d in checks if not good], 'outcome the record gives the run': att.get('outcome'),
            'reports the record carries for the run': [(i['seq'], i['evidence'].get('claim'), (i['evidence'].get('result_digest') or '')[:8]) for i in att.get('evidence') or []]}


def stored(b, aid):
    got = b.local.get_result(b.root, aid)
    return None if got is None else {k: (v if k != 'value' else {'verdict': v.get('verdict')}) for k, v in got.items() if k != 'report'}


# ============================================================================ B1
if 'B1' in PARTS:
    b = Bench('GU', crash_at='verify_running')
    try:
        s = b.s; GOOD = {'material': 'PPS-GF40', 'wall_mm': 2.5, 'mode': 'normal'}
        before = b.attempts(); cut = b.r.submit(GOOD); time.sleep(0.3); a = b.newest(before)
        note('B1a. a run is cut off: the gate host process ends while the check is running', client_was_told=VT.head(cut[1]) if isinstance(cut, tuple) else str(cut)[:200], gate_host_exit_status=s.procs['host'].poll(),
             view=view(b, a), stored_result=stored(b, a['aid']), courier=courier(b, 'b1'))
        s.stop_host(); s.start_host(); again = b.r.submit(GOOD)
        note('B1b. the gate host is started again and the same design is sent again', client_was_told=VT.head(again[1]), view=view(b, a), stored_result=stored(b, a['aid']), courier=courier(b, 'b1'))
        third = b.r.submit(GOOD)
        note('B1c. the same design a third time', client_was_told=VT.head(third[1]), view=view(b, a), stored_result=stored(b, a['aid']), courier=courier(b, 'b1'), record=record_view(b, a))
        with sqlite3.connect(str(s.dir / 'gate_host.sqlite')) as db:
            row = db.execute('SELECT status, report IS NOT NULL, prior_report IS NOT NULL FROM crossings WHERE aid = ?', (a['aid'],)).fetchone()
        note('B1d. the gate host\'s own row for the run', status=row[0], has_a_report=bool(row[1]), has_a_prior_report=bool(row[2]))
        before = b.attempts(); crash = b.r.submit({'material': 'PPS-GF40', 'wall_mm': 3, 'mode': 'crash'}); c = b.newest(before)
        note('B1e. a check that fails by itself (mode crash) while the gate host stays up', client_was_told=VT.head(crash[1]), view=view(b, c, (b.local.get_result(b.root, c['aid']) or {}).get('value')), stored_result=stored(b, c['aid']))
    finally:
        save('gate_unknown_B1.json'); b.stop()
    LOG['steps'] = []

# ============================================================================ B2
if 'B2' in PARTS:
    b = Bench('GV')
    host2 = None
    try:
        s = b.s; statefile = str(s.dir / 'gate_host.sqlite'); cap = {}
        orig = Governor._call_host
        def capturing(self, aid, nonce, receipt, admission, tool, arguments):
            cap.update(aid=aid, nonce=nonce, receipt=receipt, admission=admission, tool=tool, arguments=arguments, called=time.time()); return orig(self, aid, nonce, receipt, admission, tool, arguments)
        Governor._call_host = capturing
        result = {}
        def first_client():
            try:
                result['submit'] = b.r.s.submit(b.r.cfg, {'material': 'PA66-GF30', 'wall_mm': 2.5, 'mode': 'normal'}) if False else verify_client.Client(b.r.cfg).submit({'material': 'PA66-GF30', 'wall_mm': 2.5, 'mode': 'normal'})
            except Exception as exc:
                result['submit'] = ('RAISED', f'{type(exc).__name__}: {str(exc)[:200]}')
            result['ended'] = time.time()
        pid = s.procs['host'].pid; t = threading.Thread(target=first_client); t0 = time.time(); t.start()
        stopped_at = None
        while time.time() - t0 < 20 and stopped_at is None:
            try:
                with sqlite3.connect(statefile, timeout=0.2) as db:
                    row = db.execute("SELECT aid FROM crossings WHERE status = 'running'").fetchone()
            except sqlite3.OperationalError:
                row = None
            if row:
                os.kill(pid, signal.SIGSTOP); stopped_at = time.time()
            else:
                time.sleep(0.002)
        if stopped_at is None:
            note('B2. NOT STAGED: the run was never seen running at the gate host', waited=round(time.time() - t0, 2), result=result)
            raise SystemExit(0)
        a = {'aid': cap['aid'], 'nonce': cap['nonce']}
        with sqlite3.connect(statefile) as db:
            row1 = db.execute('SELECT status, owner, report IS NOT NULL FROM crossings WHERE aid = ?', (a['aid'],)).fetchone(); own1 = db.execute('SELECT instance, generation FROM owner').fetchone()
        note('B2a. the first gate host is stalled (SIGSTOP) while the check is running', seconds_from_the_call_to_the_stall=round(stopped_at - cap['called'], 3), host_row=row1, state_owner=own1, view=view(b, a))
        time.sleep(1.7)                                              # the lease is 1.0 s
        port2 = deploy.free_port() if hasattr(deploy, 'free_port') else None
        if port2 is None:
            import socket
            sk = socket.socket(); sk.bind(('127.0.0.1', 0)); port2 = sk.getsockname()[1]; sk.close()
        env = dict(os.environ, VERIFY_HOME=str(s.home), VERIFY_ENGINEER_KEYS=s.engineer.public_hex); env.pop('PLEA_CRASH_AT', None)
        cmd = [sys.executable, '-B', SRC + '/plea_gateway/gate_host.py', '--port', str(port2), '--tools', 'verify_tools', '--key', s.gate.private_hex, '--state', statefile, '--lease', '1.0',
               '--witness-key', s.witness.public_hex] + s._tls('host')
        host2 = subprocess.Popen(cmd, cwd=SRC + '/verify', stdout=open(s.dir / 'host2.log', 'a'), stderr=subprocess.STDOUT, env=env)
        import socket
        for _ in range(200):
            if host2.poll() is not None:
                break
            try:
                socket.create_connection(('127.0.0.1', port2), timeout=0.5).close(); break
            except OSError:
                time.sleep(0.05)
        with sqlite3.connect(statefile) as db:
            row2 = db.execute('SELECT status, owner, report IS NOT NULL FROM crossings WHERE aid = ?', (a['aid'],)).fetchone(); own2 = db.execute('SELECT instance, generation FROM owner').fetchone()
        note('B2b. a second gate host, same key and same state file, is started on another port after the lease has run out', second_host_exit_status=host2.poll(), host_row=row2, state_owner=own2,
             log_tail=(s.dir / 'host2.log').read_text()[-300:])
        if host2.poll() is not None:
            raise SystemExit(0)
        tls = TLS.TLSClient(s.pki['ca'], *s.pki['governor']); h2 = GateHostClient(f'https://127.0.0.1:{port2}', tls=tls, public_key=b.GATE)
        out = h2.run(b.root, a['aid'], a['nonce'], cap['receipt'], cap['tool'], cap['arguments'], admission=cap['admission'])
        rep_u = out['report']; acc_u = b.accept(('RECONCILE', a['aid']), rep_u)
        note('B2c. the second host is asked for the run, as a governor that tries again would ask; its report is sent to the witness', second_host_answered={'verdict': out.get('verdict'), 'repeat': out.get('repeat'), 'result': out.get('result'), 'report claim': rep_u.get('claim'), 'report digest': (rep_u.get('result_digest') or '')[:8],
             'signed by the gate key for this run': b.authentic(rep_u, a['aid'], a['nonce'])}, the_witness_answered=acc_u, view=view(b, a), stored_result=stored(b, a['aid']), courier=courier(b, 'b2'))
        os.kill(pid, signal.SIGCONT); resumed = time.time(); t.join(60)
        with sqlite3.connect(statefile) as db:
            row3 = db.execute('SELECT status, owner, report, prior_report FROM crossings WHERE aid = ?', (a['aid'],)).fetchone()
        rep_now, prior_now = (json.loads(row3[2]) if row3[2] else None), (json.loads(row3[3]) if row3[3] else None)
        note('B2d. the first host is let go on (SIGCONT), ' + f'{resumed - stopped_at:.1f} s after it was stalled', first_client_thread_ended=not t.is_alive(), first_client_was_told=VT.head(result['submit'][1]) if isinstance(result.get('submit'), tuple) else result,
             host_row={'status': row3[0], 'report claim': (rep_now or {}).get('claim'), 'report digest': ((rep_now or {}).get('result_digest') or '')[:8], 'prior report claim': (prior_now or {}).get('claim'), 'prior report digest': ((prior_now or {}).get('result_digest') or '')[:8]},
             view=view(b, a, (b.local.get_result(b.root, a['aid']) or {}).get('value')), stored_result=stored(b, a['aid']))
        out2 = h2.run(b.root, a['aid'], a['nonce'], cap['receipt'], cap['tool'], cap['arguments'], admission=cap['admission'])
        note('B2e. the second host asked again for the run', answered={'verdict': out2.get('verdict'), 'repeat': out2.get('repeat'), 'report claim': out2['report'].get('claim'), 'report digest': (out2['report'].get('result_digest') or '')[:8],
             'prior report claim': (out2.get('prior_report') or {}).get('claim')})
        acc_late = b.accept(('RECONCILE', a['aid']), rep_u)
        note('B2f. the UNKNOWN report arrives at the witness once more, after the verdict (a late copy)', the_witness_answered=acc_late, view=view(b, a, (b.local.get_result(b.root, a['aid']) or {}).get('value')),
             courier=courier(b, 'b2'), record=record_view(b, a))
    finally:
        Governor._call_host = orig
        try:
            os.kill(s.procs['host'].pid, signal.SIGCONT)
        except Exception:
            pass
        if host2 is not None and host2.poll() is None:
            host2.kill(); host2.wait(timeout=5)
        save('gate_unknown_B2.json'); b.stop()
    LOG['steps'] = []

# ============================================================================ B3
if 'B3' in PARTS:
    MAXLEN = int(os.environ.get('GATE_MAXLEN', '3'))
    b = Bench('GW')
    try:
        root = b.root
        VALUES = {'Ua': ('UNKNOWN', {'error': 'interrupted: the host stopped while this attempt was running; its effect is unknown'}), 'Ub': ('UNKNOWN', {'error': 'RuntimeError(\'x\')'}),
                  'E1': ('EFFECT', {'verdict': 'FAIL', 'n': 1}), 'E2': ('EFFECT', {'verdict': 'PASS', 'n': 2}), 'N': ('NO_EFFECT', None)}
        seqs = [list(p) for n in range(1, MAXLEN + 1) for p in itertools.product(VALUES, repeat=n)]
        rows, transitions, mismatches, t0 = [], {}, [], time.time()
        for i, seq in enumerate(seqs):
            a, _ = b.synthetic(f's{i}-' + '-'.join(seq)); state = 'none'; answers = []
            sent = []
            for letter in seq:
                claim, value = VALUES[letter]; rep = b.report(a['aid'], a['nonce'], claim, value); acc = b.accept(('RECONCILE', a['aid']), rep)
                kind_of = 'UNKNOWN' if claim == 'UNKNOWN' else ('the recorded verdict again' if state == letter else 'the first verdict' if state in ('none', 'unknown') else 'another verdict')
                transitions.setdefault((('no report yet' if state == 'none' else 'UNKNOWN only' if state == 'unknown' else 'a verdict recorded'), kind_of), set()).add((acc['kind'], acc['code']))
                if claim != 'UNKNOWN' and state in ('none', 'unknown'):
                    state = letter
                elif claim == 'UNKNOWN' and state == 'none':
                    state = 'unknown'
                answers.append((letter, acc['kind'], acc['code'])); sent.append((claim, rep['result_digest'][:16]))
            st, ans, reports = b.reports_of(a); phase = b.phase(a['aid'])
            expect_D = sorted({(c, d) for c, d in sent if c != 'UNKNOWN'}); got_D = verdict_pairs(reports)
            first_verdict = next((l for l in seq if not l.startswith('U')), None)
            kept = [(x['claim'], x['digest']) for x in reports] == sent and all(x['authentic'] for x in reports)
            outcome = lambda v: C.run_outcome(phase, (ans or {}).get('evidence') or [], v, [b.GATE], root, a['aid'], a['nonce'])
            row = {'sequence': ' '.join(seq), 'answers': answers, 'phase': phase, 'every report kept, in order, authentic': kept, 'D as sent': len(expect_D), 'D as read': len(got_D), 'conflict': len(got_D) > 1,
                   'UNKNOWN beside a verdict': any(l.startswith('U') for l in seq) and bool(got_D),
                   'phase is the first verdict sent': phase == ({'E1': 'EFFECT', 'E2': 'EFFECT', 'N': 'NO_EFFECT'}.get(first_verdict, 'CONSUMED')),
                   'e25a297 with the FAIL result': outcome(VALUES['E1'][1]), 'e25a297 with the PASS result': outcome(VALUES['E2'][1])}
            rows.append(row)
            if not kept or expect_D != got_D or not row['phase is the first verdict sent']:
                mismatches.append(row)
        conflicts = [r_ for r_ in rows if r_['conflict']]
        silent_today = [r_['sequence'] for r_ in rows if r_['conflict'] and 'E1' in r_['sequence'].split() and 'E2' in r_['sequence'].split() and r_['e25a297 with the PASS result'] == 'PASS']
        fail_then_pass_first = [r_['sequence'] for r_ in rows if r_['phase'] == 'EFFECT' and next(l for l in r_['sequence'].split() if not l.startswith('U')) == 'E1' and r_['e25a297 with the PASS result'] == 'PASS']
        note(f'B3. every sequence of 1 to {MAXLEN} gate-signed reports for one run, from two UNKNOWN reports (Ua, Ub), two EFFECT reports (E1 a FAIL result, E2 a PASS result) and a NO_EFFECT report (N)',
             sequences=len(rows), seconds=round(time.time() - t0, 1), decisions_in_the_chain=len(b.chain()),
             sequences_where_a_report_was_lost_reordered_or_the_phase_was_not_the_first_verdict=len(mismatches), those=mismatches[:5],
             sequences_with_more_than_one_distinct_verdict_pair_sent=sum(1 for r_ in rows if r_['D as sent'] > 1), of_which_the_rule_finds_a_conflict=sum(1 for r_ in rows if r_['D as sent'] > 1 and r_['conflict']),
             sequences_with_at_most_one_verdict_pair_sent=sum(1 for r_ in rows if r_['D as sent'] <= 1), of_which_the_rule_finds_a_conflict_falsely=sum(1 for r_ in rows if r_['D as sent'] <= 1 and r_['conflict']),
             sequences_with_UNKNOWN_beside_exactly_one_verdict_pair=sum(1 for r_ in rows if r_['UNKNOWN beside a verdict'] and r_['D as read'] == 1),
             sequences_with_UNKNOWN_beside_a_conflict=sum(1 for r_ in rows if r_['UNKNOWN beside a verdict'] and r_['conflict']),
             transitions_seen={f'{k[0]} + {k[1]}': sorted(v) for k, v in sorted(transitions.items())},
             recorded_FAIL_first_yet_e25a297_reads_PASS_when_the_PASS_result_is_stored=len(fail_then_pass_first), examples=fail_then_pass_first[:8])
        LOG['all_sequences'] = rows
    finally:
        save(f'gate_unknown_B3_len{MAXLEN}.json'); b.stop()
