#!/usr/bin/env python3
"""Planted defects for Amendment 17 (22 November 2026), development only.  Each removes or weakens one rule of the amendment, in
a copy of the tree made from a commit, and runs the tests that should catch it.  A defect is caught when one of those tests
fails.  Nothing in the branch is changed.

An entry is (name, file, text, replacement, tests), or (name, [(file, text, replacement), ...], None, tests) for a defect of
several edits.  After the third review (M-c, L-c): the loop takes both forms (it once raised ValueError at the first of the
second); the results are written after each defect, not only at the end; and the record of bindings' SQL function is
installed again from the commit at the end, since one defect changes it in the database the tests use.  The two entries
whose text the second review's corrections rewrote, and the one whose text the third review's rewrote, are kept, and are NOT
PLANTED; each has a restated entry after them.

After the fourth review: the realm is gone (a job is named in the record by its certificate's hash and its name), so the three
entries about the realm are kept and are NOT PLANTED, with no restatement; 'a revocation not written when it cannot be
recorded' is restated; six are added; and the SQL function is installed again however the run ends (L-c).  The runner uses
the database the tests use (PLEA_ADMIN_DSN, else `plea`): nothing else may run on it at the same time.

After the fifth review: a job is named in the record by the engineer's key and the job's name.  'the record keyed by the job
name alone' and 'jobs.json written without a lock' are restated (their earlier entries are kept, NOT PLANTED), and five are
added.  The fifth review's corrections also rewrote the text of 'a revocation not written when it cannot be recorded
(restated)', 'the front door records no revocation at its start' and 'a move not written when it cannot be recorded'; each is
kept and restated.

After the sixth review: four are added, for a job revoked by name, the temporary file, the log, and the message of a
revocation neither recorded nor written.

After the seventh review: 'a job with no usable entry not revoked by name' is restated (its earlier entry is kept, NOT
PLANTED), and three are added: revocation by name done without being asked for, a name not checked whole, and the mode of
jobs.json not kept.

Amendment 18 (22 November 2026, the single engineer key): three are added.  They are named in the declaration of
Amendment 18 and run alone (by name) against its candidate; the 51 earlier entries were run against 203bdca.

Amendment 19 (22 November 2026, D20-F): five are added.  With the owner's direction that the planted-defect checks be run
against the exact final candidate, the whole runner is run against Amendment 19's candidate.

Amendment 19, R15 correction (23 November 2026): two are added.

Amendment 20 (23 November 2026): fifteen are added, against Amendment 20's candidate.

    amend17_mutants.py COMMIT WORKDIR PYTHON OUT.json [NAME ...]
"""
import json, pathlib, shutil, subprocess, sys, time

COMMIT, WORK, PY, OUT = sys.argv[1], pathlib.Path(sys.argv[2]), sys.argv[3], pathlib.Path(sys.argv[4])
ONLY = set(sys.argv[5:])
REPO = pathlib.Path(__file__).resolve().parent.parent

MUTANTS = [
    ('binder removed', 'verify/verify_tools.py', "               verify, bound),", "               verify),", ['R30']),
    ('binder always binds', 'verify/verify_tools.py', "    return root.rsplit('/', 1)[1] == h[:32]", "    return True", ['R30']),
    ('identity back to 64 bits', 'plea_gateway/governor.py', "return 'a-' + h[:16] if legacy else 'a2-' + h\n", "return 'a-' + h[:16] if legacy else 'a2-' + h[:16]\n", ['R31']),
    ('request key back to 96 bits', 'verify/verify_record.py', "return f'{TOOL}:' + (h[:24] if legacy else h)", "return f'{TOOL}:' + (h[:24] if legacy else h[:24])", ['R31']),
    ('front door does not check the design of a verdict', 'verify/front_door.py', "        if verdict.get('design_sha256') != design_hash(design):", "        if False:", ['R31']),
    ('checker allows mixed forms', 'verify/check_record.py', "    if ident is None:\n        bad(5,", "    if False:\n        bad(5,", ['R31']),
    ('no form kept per budget', 'plea_gateway/governor.py', "    return 'legacy' if any(LEGACY_AID.fullmatch(str(a[0])) for a in obs.get('attempts', ())) else 'current'", "    return 'current'", ['R33']),
    ('front door ignores the budget\'s form', 'verify/front_door.py', "        key = request_key(args, legacy=legacy)", "        key = request_key(args)", ['R33']),
    ('record of bindings not consulted', 'verify/front_door.py', "        if answer != 'CURRENT' or b['cert_sha256']", "        if b['cert_sha256']", ['F37']),
    ('revocation not absorbing', 'verify/front_state.py', "    IF r.revoked THEN\n        RETURN 'REVOKED';", "    IF false THEN\n        RETURN 'REVOKED';", ['F37']),
    ('a stale binding accepted', 'verify/front_state.py', "    IF p_seq < r.seq THEN\n        RETURN 'STALE';", "    IF false THEN\n        RETURN 'STALE';", ['F37']),
    ('a binding for another budget admitted', 'verify/front_door.py', "        if b['root'].rsplit('/', 1)[-1] != b['baseline_sha256'][:32] or '/' not in b['root']:", "        if False:", ['F37']),
    ('controls not put to the checker', 'verify/verify_ctl.py', "    problems = check_record.control_problems(card, controls_run)", "    problems = []", ['R32']),
    ('the first client not retired', 'verify/verify_client.py', None, 'git:1b132e2:verify/verify_client.py', ['R34']),
    # after the second review
    ('revocations recorded only when the job calls', [('verify/front_door.py', "                self.observe(name, b); n += 1", "                n += 1"),
                                                       ('verify/front_ctl.py', "    if realm is None:\n        return None\n    import front_state", "    if True:\n        return None\n    import front_state")], None, ['F37']),
    ('realm from the authority\'s file', 'verify/front_door.py', "        realm = self.cfg.get('realm')", "        realm = hashlib.sha256(pathlib.Path(self.cfg['tls']['ca']).read_bytes()).hexdigest()[:32]", ['F37']),
    ('a revocation at a number already seen not kept', 'verify/front_state.py', "    IF p_revoked THEN", "    IF false THEN", ['F37']),
    ('mixed forms not refused', 'plea_gateway/governor.py', "    if len(forms) > 1:", "    if False:", ['R33']),
    ('controls not put to rederive', 'verify/verify_ctl.py', "control_problems(card, controls_run) + rederived", "control_problems(card, controls_run) + []", ['R32']),
    # after the third review: the two entries above whose text was rewritten, restated; and the third review's corrections
    ('no form kept per budget (restated)', 'plea_gateway/governor.py', "    return 'legacy' if forms == {'legacy'} else 'current'", "    return 'current'", ['R33']),
    ('a binding for another budget admitted (restated)', 'verify/front_door.py', "                and b['root'].rsplit('/', 1)[-1] == b['baseline_sha256'][:32])", "                and True)", ['F37']),
    ('revocations recorded only when the job calls (restated)', [('verify/front_door.py', "                self.observe(name, b); n += 1", "                n += 1"),
                                                                  ('verify/front_ctl.py', "    import front_state\n    from plea_gateway import Store\n    return front_state.observe(",
                                                                   "    return 'REVOKED' if binding['event'] == 'REVOKE' else 'CURRENT'\n    import front_state\n    from plea_gateway import Store\n    return front_state.observe(")], None, ['F37', 'F38']),
    ('the console does not read the front door\'s realm', 'verify/front_ctl.py', "        stored = front_state.read_realm(home)\n", "        stored = given\n", ['F38']),
    ('the front door started under another realm', 'verify/front_state.py', "    if realm is not None and realm != stored:", "    if False:", ['F38']),
    ('a revocation not written when it cannot be recorded', 'verify/front_ctl.py', "    _write(home, binding)\n    if problem or why:", "    if problem or why:\n        raise Refused(why or problem)\n    _write(home, binding)\n    if problem or why:", ['F38']),
    # after the fourth review
    ('a revocation not written when it cannot be recorded (restated)', 'verify/front_ctl.py', "    try:\n        _write(home, binding)\n    except OSError as exc:\n        if why is None:",
     "    if why:\n        raise Refused(why)\n    try:\n        _write(home, binding)\n    except OSError as exc:\n        if why is None:", ['F38']),
    ('a binding for another budget admitted (restated again)', 'verify/front_door.py', "                and b['root'].rsplit('/', 1)[-1] == b['baseline_sha256'][:32]\n", "                and True\n", ['F37']),
    ('the record keyed by the job name alone', 'verify/front_state.py', "    return f'{cert}:{job}'", "    return job", ['F38']),
    ('an unrecorded revocation not recorded again', 'verify/front_ctl.py', "    if cur['event'] == 'REVOKE':\n        try:\n            answer = _record(cur, control_dsn)",
     "    if cur['event'] == 'REVOKE':\n        raise Refused(f'{job} is already revoked')\n        try:\n            answer = _record(cur, control_dsn)", ['F38']),
    ('the front door records no revocation at its start', 'verify/front_door.py', "        front.record_revocations()\n    except front_state.StateUnavailable", "        pass\n    except front_state.StateUnavailable", ['F38']),
    ('the look records no revocation', [('verify/front_door.py', "            self.record_revocations()\n        except Exception:\n            pass", "            pass\n        except Exception:\n            pass"),
                                        ('verify/front_door.py', "                if self.observe(name, b) != 'CURRENT':", "                if b['event'] == 'REVOKE' or self.observe(name, b) != 'CURRENT':")], None, ['F38']),
    ('a revocation recorded and not written said to be refused', 'verify/front_ctl.py', "            raise Unwritten(binding, f'the revocation is recorded", "            raise Refused(f'the revocation is recorded", ['F38']),
    ('jobs.json written without a lock', 'verify/front_ctl.py', "        fcntl.flock(lock, fcntl.LOCK_EX)", "        pass", ['F38']),
    # after the fifth review
    ('the record keyed by the job name alone (restated)', 'verify/front_state.py', "    return f\"{binding['signer']}:{binding['job']}\"", "    return binding['job']", ['F38']),
    ('the record keyed by the certificate\'s hash', 'verify/front_state.py', "    return f\"{binding['signer']}:{binding['job']}\"", "    return f\"{binding.get('cert_sha256')}:{binding['job']}\"", ['F38']),
    ('the console does not match the entry to its job', 'verify/front_ctl.py', "    if b.get('job') != job:                              # after the fifth review (N-H1)", "    if False:                              # after the fifth review (N-H1)", ['F38']),
    ('a changed entry written over', 'verify/front_ctl.py', "        if jobs.get(binding['job']) != start:", "        if False:", ['F38']),
    ('the lock followed through a link, and a pipe taken', 'verify/front_ctl.py', "    fd = os.open(p, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, 0o600)\n    try:\n        if not stat.S_ISREG(os.fstat(fd).st_mode):",
     "    fd = os.open(p, os.O_RDWR | os.O_CREAT | os.O_NONBLOCK | os.O_CLOEXEC, 0o600)\n    try:\n        if False:", ['F38']),
    ('a revocation not written when it cannot be recorded (restated again)', 'verify/front_ctl.py', "    try:\n        _write(home, binding, cur)\n    except OSError as exc:\n        if why is None:",
     "    if why:\n        raise Refused(why)\n    try:\n        _write(home, binding, cur)\n    except OSError as exc:\n        if why is None:", ['F38']),
    ('the front door records no revocation at its start (restated)', 'verify/front_door.py', "        front.record_revocations()\n    except (front_state.StateUnavailable, ValueError)", "        pass\n    except (front_state.StateUnavailable, ValueError)", ['F38']),
    ('a move not written when it cannot be recorded (restated)', 'verify/front_ctl.py', "    _write(home, binding, cur)                           # written first", "    raise Unrecorded(binding, 'could not be recorded')\n    _write(home, binding, cur)                           # written first", ['F38']),
    ('jobs.json written without a lock (restated)', 'verify/front_ctl.py', "                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)\n                return fd", "                return fd", ['F38']),
    # after the sixth review
    ('a job with no usable entry not revoked by name', 'verify/front_ctl.py', "    except Refused as no_entry:\n        if not isinstance(job, str)", "    except Refused as no_entry:\n        raise\n        if not isinstance(job, str)", ['F38']),
    ('the temporary file opened by name', 'verify/front_ctl.py', "            tfd, tname = tempfile.mkstemp(dir=path.parent, prefix='.jobs-', suffix='.tmp')",
     "            tname = str(path.with_suffix('.tmp')); tfd = os.open(tname, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)", ['F38']),
    ('the log opened through a link or a pipe', 'verify/front_ctl.py', "    fd = os.open(p, flags | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, 0o644)\n    if not stat.S_ISREG(os.fstat(fd).st_mode):",
     "    fd = os.open(p, flags | os.O_NONBLOCK | os.O_CLOEXEC, 0o644)\n    if False:", ['F38']),
    ('a revocation neither recorded nor written not said', 'verify/front_ctl.py', "        raise Refused(f'{why}, and it could not be written to jobs.json ({exc}): {job} is NOT revoked; give revoke again') from None", "        raise", ['F38']),
    # after the seventh review
    ('a job with no usable entry not revoked by name (restated)', 'verify/front_ctl.py', "        if not isinstance(job, str) or not JOB_NAME.fullmatch(job) or job in RESERVED:\n            raise Refused(f'{job!r} is not a job name; nothing was revoked') from None",
     "        raise\n        if not isinstance(job, str) or not JOB_NAME.fullmatch(job) or job in RESERVED:\n            raise Refused(f'{job!r} is not a job name; nothing was revoked') from None", ['F38']),
    ('revocation by name done without being asked for', 'verify/front_ctl.py', "    except Refused as no_entry:\n        if not by_name:", "    except Refused as no_entry:\n        if False:", ['F38']),
    ('a name revoked by name not checked whole', 'verify/front_ctl.py', "not JOB_NAME.fullmatch(job) or job in RESERVED:\n            raise Refused(f'{job!r} is not a job name", "not JOB_NAME.match(job) or job in RESERVED:\n            raise Refused(f'{job!r} is not a job name", ['F38']),
    ('the mode of jobs.json not kept', 'verify/front_ctl.py', "                os.fchmod(tfd, mode)", "                pass", ['F38']),
    # Amendment 18
    ('more than one engineer key accepted', 'verify/front_door.py', "    if len(keys) != 1:\n        raise EngineerKeys(", "    if len(keys) < 1:\n        raise EngineerKeys(", ['F39']),
    ('an engineer key of another form accepted', 'verify/front_door.py', "    if not isinstance(keys[0], str) or not HEX64.fullmatch(keys[0]):", "    if not isinstance(keys[0], str):", ['F39']),
    ('the front door\'s start does not check its keys', 'verify/front_door.py', "    try:\n        single_engineer_key(a.engineer_key)              # Amendment 18", "    try:\n        pass              # Amendment 18", ['F39']),
    # Amendment 19
    ('JSON numbers read as binary floats again', 'verify/baseline.py', "        out = json.loads(run.stdout.decode('utf-8'), parse_float=decimal.Decimal)", "        out = json.loads(run.stdout.decode('utf-8'))", ['R35']),
    ('a decimal read from a JSON number refused', 'verify/baseline.py', "    if isinstance(value, bool) or not isinstance(value, (int, float, str, decimal.Decimal)):", "    if isinstance(value, bool) or not isinstance(value, (int, float, str)):", ['R35']),
    ('a tolerance at the limit', 'verify/baseline.py', "    if criterion['comparison'] == '<=':\n        return achieved <= limit, text(limit - achieved)\n    return achieved >= limit, text(achieved - limit)",
     "    if criterion['comparison'] == '<=':\n        return achieved <= limit + D('1e-12'), text(limit - achieved)\n    return achieved >= limit - D('1e-12'), text(achieved - limit)", ['R35']),
    ('the record checker\'s refusal not asked', 'verify/verify_tools.py', "        if not rederive(card, result, design):\n            return result", "        if True:\n            return result", ['R35']),
    ('the implausible reason writes the number in full', 'verify/baseline.py', "{c[\"id\"]} = {_shown(value)} {c[\"units\"]}", "{c[\"id\"]} = {text(value)} {c[\"units\"]}", ['R35']),
    # Amendment 19, R15 correction (23 November 2026)
    ('exponent beyond the context limit not answered as an error', 'verify/baseline.py', "        if value != 0 and value.adjusted() > decimal.DefaultContext.Emax:", "        if False:", ['R15', 'R35']),
    ('exponent guard one too early', 'verify/baseline.py', "        if value != 0 and value.adjusted() > decimal.DefaultContext.Emax:", "        if value != 0 and value.adjusted() >= decimal.DefaultContext.Emax:", ['R35']),
    # Amendment 20 (23 November 2026)
    ('a plausible bound read as a binary float again (service)', 'verify/baseline.py', "        lo, hi = dec(c['plausible'].get('min')), dec(c['plausible'].get('max'))          # Amendment 20 (F-1)", "        lo, hi = D(c['plausible']['min']), D(c['plausible']['max'])", ['R36']),
    ('a plausible bound read as a binary float again (checker)', 'verify/check_record.py', "        lo, hi = dec((base.get('plausible') or {}).get('min')), dec((base.get('plausible') or {}).get('max'))          # Amendment 20 (F-1)", "        lo, hi = D(base['plausible']['min']), D(base['plausible']['max'])", ['R36']),
    ('a design-space bound read as a binary float again (service)', 'verify/baseline.py', "            lo, hi = dec(rule.get('min')), dec(rule.get('max'))          # Amendment 20 (F-1): a bound is read by dec(), as a decimal, never D(float)", "            lo, hi = D(rule['min']), D(rule['max'])", ['R36']),
    ('a design-space bound read as a binary float again (checker)', 'verify/check_record.py', "            lo, hi = dec(rule.get('min')), dec(rule.get('max'))          # Amendment 20 (F-1)\n            if d is None or isinstance(v, str) or lo is None", "            lo, hi = D(rule['min']), D(rule['max'])\n            if d is None or isinstance(v, str) or lo is None", ['R36']),
    ('a plausible range need not be text', 'verify/baseline.py', "        need(isinstance(p.get('min'), str) and isinstance(p.get('max'), str) and lo is not None", '        need(lo is not None', ['R36']),
    ('a design-space range need not be text', 'verify/baseline.py', "            need(isinstance(rule.get('min'), str) and isinstance(rule.get('max'), str) and lo is not None", '            need(lo is not None', ['R36']),
    ("a value that underflows written '-0' (service)", 'verify/baseline.py', "    return '0' if n == 0 else format(n, 'f')        # Amendment 20 (F-4): a non-zero", "    return format(n, 'f')        # Amendment 20 (F-4): a non-zero", ['R36']),
    ("a value that underflows written '-0' (checker)", 'verify/check_record.py', "    return '0' if n == 0 else format(n, 'f')        # Amendment 20 (F-4), as baseline.text", "    return format(n, 'f')        # Amendment 20 (F-4), as baseline.text", ['R36']),
    ('a reason quotes the value whole again', 'verify/baseline.py', '(got {sent(achieved.get(c["id"]))})\')', '(got {achieved.get(c["id"])!r})\')', ['R36']),
    ('a repeated key accepted in a released design', 'verify/check_record.py', "            if k in out:\n                raise ValueError('a key is repeated')", "            if False:\n                raise ValueError('a key is repeated')", ['R36']),
    ('a number a binary float rounds accepted in a released design', 'verify/check_record.py', '        if not d.is_finite() or D(repr(v)) != d:', '        if not d.is_finite():', ['R36']),
    ('a released design read as plain JSON again', 'verify/check_record.py', '                design = load_design(f.read())                    # Amendment 20 (F-2)', '                design = json.loads(f.read())', ['R36']),
    ('Check 6 compares designs as Python values again', 'verify/check_record.py', "canonical(result['design']) != canonical(args['design']) or result.get('design_sha256') != sha(canonical(args['design']))", "result['design'] != args['design'] or result.get('design_sha256') != sha(canonical(args['design']))", ['R36']),
    ('the front door accepts a number a binary float rounds', 'verify/front_door.py', '        if not d.is_finite() or decimal.Decimal(repr(v)) != d:', '        if not d.is_finite():', ['F40']),
    ('the command line reads a design file as JSON and sends it again', 'verify/front_client.py', '            status, out = client.submit_raw(raw.strip())', "            status, out = client.submit(json.loads(raw.decode('utf-8')))", ['F40']),
    ('a move not written when it cannot be recorded', 'verify/front_ctl.py', "    _write(home, binding)                                # written first", "    raise Unrecorded(binding, 'could not be recorded')\n    _write(home, binding)                                # written first", ['F38']),
]


def tree(dest):
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    arc = subprocess.run(['git', '-C', str(REPO), 'archive', COMMIT], capture_output=True, check=True).stdout
    subprocess.run(['tar', 'xf', '-', '-C', str(dest)], input=arc, check=True)


def write_out():
    OUT.write_text(json.dumps({'commit': COMMIT, 'results': results, 'caught': sum(1 for r in results.values() if r.get('caught')),
                               'planted': sum(1 for r in results.values() if r.get('planted')), 'of': len(results)}, indent=1) + '\n')


results = {}
try:
  for entry in MUTANTS:
      name, tests = entry[0], entry[-1]
      if ONLY and name not in ONLY:
          continue
      dest = WORK / 'tree'; tree(dest)
      path = entry[1]
      edits = path if isinstance(path, list) else [(path, entry[2], entry[3])]
      planted = True
      for pth, o, n in edits:
          f = dest / pth
          if n is not None and n.startswith('git:'):
              _, rev, src = n.split(':', 2)
              f.write_bytes(subprocess.run(['git', '-C', str(REPO), 'show', f'{rev}:{src}'], capture_output=True, check=True).stdout)
          else:
              text = f.read_text(); planted = planted and text.count(o) == 1
              f.write_text(text.replace(o, n))
      path = path if isinstance(path, str) else ', '.join(p for p, _, _ in path)
      if not planted:
          results[name] = {'planted': False, 'caught': None}; print(f'{name}: NOT PLANTED (the text was not found once)', flush=True); write_out(); continue
      got = {}
      for t in tests:
          suite = 'verify_front_tests.py' if t.startswith('F') else 'verify_tests.py'
          t0 = time.time()
          run = subprocess.run([PY, '-B', suite, t], cwd=dest / 'tests', capture_output=True, text=True, timeout=1800)
          out = json.loads((dest / 'outputs' / ('verify_front_tests.json' if t.startswith('F') else 'verify_tests.json')).read_text()) if run.returncode in (0, 1) else {}
          res = (out.get('tests') or {}).get(t, {})
          got[t] = {'ok': res.get('ok'), 'failed_checks': [k for k, v in (res.get('checks') or {}).items() if not v], 'error': res.get('error'), 'seconds': round(time.time() - t0, 1)}
      caught = any(v['ok'] is False for v in got.values())
      results[name] = {'planted': True, 'file': path, 'tests': got, 'caught': caught}
      print(f"{name}: {'CAUGHT' if caught else 'NOT CAUGHT'} by {tests}", flush=True)
      write_out()
finally:
  dest = WORK / 'tree'; tree(dest)                         # the commit's own SQL function, installed again (third review, L-c), however the run ends
  subprocess.run([PY, '-B', '-c', 'import os, sys; sys.path[:0] = ["verify", "."]; import front_state; from plea_gateway import Store; '
                 'front_state.install(Store(os.environ.get("PLEA_ADMIN_DSN", "postgresql://plea:plea@127.0.0.1:5432/plea")))'], cwd=dest, check=True)
  write_out()
print(f"caught {sum(1 for r in results.values() if r.get('caught'))} of {sum(1 for r in results.values() if r.get('planted'))} planted; "
      f"{sum(1 for r in results.values() if not r.get('planted'))} not planted; {len(results)} in all")
