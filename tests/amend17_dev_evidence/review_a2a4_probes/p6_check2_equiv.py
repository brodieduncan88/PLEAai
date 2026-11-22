"""P6 (review A3). Expectation before the run: check 2's verdicts and words on the shipped sample record, and on copies whose
controls_run is edited in 8 ways, are identical between check_record.py at 1b132e2 and at abe044d (signature failures aside,
which both report). PREDICTION: all 9 cases give the same (ok, check-2 words) in both trees."""
import sys, json, copy, importlib.util
NEW, OLD, SAMPLE = sys.argv[1], sys.argv[2], sys.argv[3]
def load(p, n):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
new, old = load(NEW + '/verify/check_record.py', 'cr_new'), load(OLD + '/verify/check_record.py', 'cr_old')
rec = json.load(open(SAMPLE + '/record_revA.json')); keys = json.load(open(SAMPLE + '/keys.json'))
def env(r): return r['baseline']
edits = {'as shipped': lambda r: None,
         'controls dropped': lambda r: env(r).__setitem__('controls_run', []),
         'controls None': lambda r: env(r).__setitem__('controls_run', None),
         'verdict flipped': lambda r: env(r)['controls_run'][0].__setitem__('verdict', 'PASS'),
         'met flipped': lambda r: env(r)['controls_run'][0]['criteria'][0].__setitem__('met', True),
         'achieved None': lambda r: env(r)['controls_run'][0]['criteria'][0].__setitem__('achieved', None),
         'limit changed': lambda r: env(r)['controls_run'][0]['criteria'][0].__setitem__('limit', '1'),
         'criteria empty': lambda r: env(r)['controls_run'][0].__setitem__('criteria', []),
         'reason code': lambda r: env(r)['controls_run'][1].__setitem__('reason_code', 'MET_X')}
out, same = {}, True
for name, f in edits.items():
    r = copy.deepcopy(rec)
    try:
        f(r)
    except Exception as exc:
        out[name] = f'edit failed: {exc!r}'; continue
    a = old.verify(copy.deepcopy(r), keys); b = new.verify(copy.deepcopy(r), keys)
    w = lambda res: (res[0], [d for n, t, g, d in res[1] if n == 2 and not g])
    out[name] = {'old': w(a), 'new': w(b), 'same': w(a) == w(b)}; same = same and w(a) == w(b)
print(json.dumps({'all_same': same, 'cases': out}, indent=1))
