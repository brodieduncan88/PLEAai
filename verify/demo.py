#!/usr/bin/env python3
"""Seven ways to make a failing design "pass" by changing the question, tried without the service and with it.

    python verify/demo.py        needs PostgreSQL with the PLEA schema and roles (top-level README.md, "Reproduce")

The job is the pump-station sub-main (verify/cases/pump-station-submain): no allowed cable meets the 5 % voltage-drop
limit; the best reaches 5.74 %.  This script is not an AI assistant.  It makes, on purpose, each of the seven changes
a hurried person or an assistant might make, one at a time:

  1  use 120 mm2, the next size up, which the requirement does not allow (it does not fit the terminals)
  2  relax the limit from 5 % to 7 %
  3  leave out the 1.2 % of drop already used elsewhere
  4  use the 330 m map distance instead of the 400 m surveyed route
  5  drop the 20 % spare allowance and fit a 100 A breaker
  6  read the 120 mm2 resistance for the 95 mm2 cable
  7  compare the phase-to-neutral drop, leaving out the square root of three

Part 1, an ordinary job folder: after each change the folder's own check prints PASS, and nothing records that the
question was changed.
Part 2, the same folder under the verification service: the same changes are made to the folder, and then to the
service's own stored files.  No change produces a pass, every result goes to the engineer, and the record checks offline.
Part 3, the legitimate way: the engineer issues a revised baseline that allows 120 mm2, with a reason.  The design
then meets the check, and the record says in its first lines that the requirement was changed after a failure.

It leaves a transcript and the records in outputs/verify_demo/.
"""
import json
import pathlib
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / 'experiment'))
import check_record      # noqa: E402
import deploy            # noqa: E402
import verify_ctl        # noqa: E402
import workspace         # noqa: E402

CASE = HERE / 'cases' / 'pump-station-submain'
OUT = HERE.parent / 'outputs' / 'verify_demo'
BEST = {'size_mm2': 95, 'install': 'buried', 'breaker_A': 125}


def edit(path, old, new):
    p = pathlib.Path(path); s = p.read_text(); assert old in s, (path, old); p.write_text(s.replace(old, new))


def change(folder, n):
    """Make change n in a job folder (or in a directory laid out like one).  Returns the design to put forward."""
    f = pathlib.Path(folder)
    calc = f / 'calc' if (f / 'calc').exists() else f
    if n == 1:
        return dict(BEST, size_mm2=120)
    if n == 2 and (f / 'requirements').exists():
        edit(f / 'requirements' / 'limits.json', '"limit": "5.0"', '"limit": "7.0"')
    if n == 3:
        edit(calc / 'site.json', '"drop_used_elsewhere_pct": 1.2', '"drop_used_elsewhere_pct": 0')
    if n == 4:
        edit(calc / 'site.json', '"route_length_m": 400', '"route_length_m": 330')
    if n == 5:
        edit(calc / 'site.json', '"spare_factor": 1.20', '"spare_factor": 1.00'); return dict(BEST, breaker_A=100)
    if n == 6:
        edit(calc / 'cables.csv', '95,0.193,', '95,0.153,')
    if n == 7:
        edit(calc / 'check.py', 'vd = math.sqrt(3.0) * i_b', 'vd = i_b')
    return dict(BEST)


NAMES = {1: '120 mm2 instead of an allowed size', 2: 'limit relaxed from 5 % to 7 %', 3: 'the 1.2 % used elsewhere left out', 4: '330 m instead of the 400 m route',
         5: 'no 20 % spare, 100 A breaker', 6: '120 mm2 resistance read for 95 mm2', 7: 'square root of three left out'}


def own_check(folder) -> str:
    out = subprocess.run([sys.executable, 'run_check.py'], cwd=str(folder), capture_output=True, text=True)
    return (out.stdout.strip().splitlines() or ['error'])[-1].replace('RESULT: ', '')


def main():
    shutil.rmtree(OUT, ignore_errors=True); OUT.mkdir(parents=True)
    lines = []
    def say(text=''):
        print(text, flush=True); lines.append(text)

    say('PART 1  An ordinary job folder.  The requirement cannot be met: the best allowed design gives 5.74 % against 5 %.')
    base = OUT / 'plain' / 'start'; workspace.make(CASE, base)
    (base / 'design.json').write_text(json.dumps(BEST)); say(f'  as issued, best allowed design (95 mm2 buried, 125 A):      the folder\'s own check prints {own_check(base)}')
    passes = 0
    for n in range(1, 8):
        f = OUT / 'plain' / f'change{n}'; workspace.make(CASE, f)
        (f / 'design.json').write_text(json.dumps(change(f, n)))
        result = own_check(f); passes += result == 'PASS'
        say(f'  change {n}: {NAMES[n]:<38} the folder\'s own check prints {result}')
    say(f'  {passes} of 7 changes turn FAIL into PASS.  Nothing in the folder records that the question was changed.')

    say(); say('PART 2  The same job under the verification service.  K. Dalton baselined the requirement before work started.')
    s = deploy.Services(OUT / 'service').start()
    try:
        env = s.baseline(CASE, json.loads((CASE / 'card.json').read_text())); h = env['baseline_sha256']
        say(f'  baseline {h[:16]}…; control cases at baselining: ' + ', '.join(f"{c['expect'].lower()} as expected" for c in env['controls_run']))
        folder = OUT / 'governed'; workspace.make(CASE, folder, lambda f: s.client_config(f, h), 'K. Dalton')
        cfg = folder / '.verify' / 'config.json'
        say('  a) the seven changes made in the job folder, then the design submitted:')
        for n in range(1, 8):
            code, out = s.submit(cfg, change(folder, n))
            say(f'     change {n}: {NAMES[n]:<38} service says: {out.splitlines()[0]}')
        say('  b) the same changes made to the service\'s own stored files, by someone with access to that machine:')
        store = s.home / 'baselines' / h
        for n in (3, 6, 7):
            keep = {p.name: p.read_bytes() for p in store.iterdir() if p.is_file()}
            change(store, n)
            code, out = s.submit(cfg, dict(BEST, breaker_A={3: 160, 6: 200, 7: 250}[n]))        # a fresh design each time, so it is a fresh run
            for name, data in keep.items():
                (store / name).write_bytes(data)
            say(f'     change {n}: {NAMES[n]:<38} service says: {out.splitlines()[0]}')
        record = s.record(h, [folder / '.verify' / 'submissions.jsonl'])
        ok, checks, summary = check_record.verify(record, s.keys)
        (OUT / 'record_revA.json').write_text(json.dumps(record, indent=1) + '\n'); (OUT / 'keys.json').write_text(json.dumps(s.keys, indent=1) + '\n')
        say(f"  official runs {summary['official_runs']}: met {summary['met']}, not met {summary['not_met']}, unknown {summary['unknown']}.  "
            f"Notices in K. Dalton's inbox: {len(s.inbox(h))}.  Record verifies offline: {ok}.  Status: {summary['status']}.")

        say(); say('PART 3  The legitimate way.  K. Dalton decides to change the terminals and issues revision B allowing 120 mm2.')
        draft = json.loads((CASE / 'card.json').read_text())
        draft['requirement'] = dict(draft['requirement'], revision='B'); draft['design_space']['size_mm2']['choice'] = [25, 35, 50, 70, 95, 120]
        reason = 'Terminals at both ends to be replaced to accept 120 mm2 (change request CR-112, approved by the asset owner).'
        env_b = verify_ctl.revise(s.home, CASE, draft, s.engineer, h, reason); hb = env_b['baseline_sha256']
        code, out = s.submit(cfg, dict(BEST, size_mm2=70)); say(f'  a further run on revision A: {out.splitlines()[0][:76]}')
        folder_b = OUT / 'governed_revB'; workspace.make(CASE, folder_b, lambda f: s.client_config(f, hb), 'K. Dalton')
        code, out = s.submit(folder_b / '.verify' / 'config.json', dict(BEST, size_mm2=120)); say(f'  120 mm2 buried, 125 A on revision B: {out.splitlines()[0]}')
        record_b = s.record(hb, [folder_b / '.verify' / 'submissions.jsonl'])
        (OUT / 'record_revB.json').write_text(json.dumps(record_b, indent=1) + '\n')
        ok_b, checks_b, summary_b = check_record.verify(record_b, s.keys)
        say('  the offline check of revision B\'s record says:')
        for line in check_record.render(ok_b, checks_b, summary_b).splitlines():
            if line.strip().startswith(('CHANGED AFTER', 'RECORD', 'STATUS')):
                say('    ' + line.strip())
        say(); say('One machine does not show separation: here the service, its keys and this script share one account.')
        say(f'Left in {OUT.relative_to(HERE.parent)}/: record_revA.json, record_revB.json, keys.json, transcript.txt')
    finally:
        s.stop()
    (OUT / 'transcript.txt').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
