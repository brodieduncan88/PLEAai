"""Reproduce D20 before any change (VP rules): a check whose achieved values need more than 28 significant digits.
    python repro_d20.py TREE OUT"""
import json, pathlib, sys, uuid
TREE, OUT = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
sys.path[:0] = [str(TREE), str(TREE / 'verify'), str(TREE / 'tests')]
import deploy_front, check_record, baseline as B
CASE = TREE / 'tests' / 'verify_case'
src = OUT / 'case'; src.mkdir(parents=True, exist_ok=True)
check = (CASE / 'check.py').read_text().replace("value = float(rows[design['material']]['max_service_c'])", "value = rows[design['material']]['max_service_c']")
check = check.replace("{value:g} C", "{value} C")
(src / 'check.py').write_text(check)
results = {}
for name, fail_v, pass_v in (('rounds_across_limit', '199.99999999999999999999999999999', '250'), ('over_28_digits_not_across', '180.000000000000000000000000000001', '220.000000000000000000000000000001')):
    (src / 'materials.csv').write_text(f'material,max_service_c\nPA66-GF30,{fail_v}\nPPS-GF40,{pass_v}\nPEEK,{pass_v}\n')
    card = json.loads((CASE / 'card.json').read_text()); card['job'] = uuid.uuid4().hex
    s = deploy_front.FrontServices(OUT / name).start(); got = {}
    try:
        try:
            env = s.baseline(src, card); got['baselined'] = True; h = env['baseline_sha256']
            got['controls_run'] = env['controls_run']
        except Exception as exc:
            got['baselined'] = f'refused: {type(exc).__name__}: {str(exc)[:200]}'; h = None
        if h:
            job = s.enrol('job-d20', h)
            for d in ({'material': 'PA66-GF30', 'wall_mm': 3, 'mode': 'normal'}, {'material': 'PPS-GF40', 'wall_mm': 3, 'mode': 'normal'}):
                code, out = s.cli(job, 'submit', d); got.setdefault('runs', []).append((d['material'], code, out.strip().splitlines()[:1]))
            ok, checks, summ = check_record.verify(s.record(h), s.keys)
            got['record_verifies'] = ok; got['failed'] = [f'{n} {t}: {d}' for n, t, g, d in checks if not g]
            got['outcomes'] = [(r['outcome'], r['reason_code'], [c.get('achieved') for c in r.get('criteria', [])]) for r in summ.get('runs', [])]
    finally:
        s.stop()
    results[name] = got
print(json.dumps(results, indent=1, default=str))
(OUT / 'repro_d20.json').write_text(json.dumps(results, indent=1, default=str))
