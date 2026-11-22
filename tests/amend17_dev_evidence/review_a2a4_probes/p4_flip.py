"""P4 (review A1). Expectation written before the run: on a budget that already holds a current-form ('a2-') attempt, the
service's role (plea_local) alone reserves one attempt named in the 64-bit form; governor.identity_form then answers 'legacy'
for that budget, so every later request on it is keyed and identified in the 64-bit form.
PREDICTION: form_before == 'current', reserve APPLIED, form_after == 'legacy'."""
import sys, json, uuid, hashlib
W = sys.argv[1]; sys.path.insert(0, W)
from plea_gateway import Store
from plea_gateway.governor import identity_form, attempt_id
db = 'plea_rv2'
control = Store(f'postgresql://plea_control:control@127.0.0.1:5432/{db}'); local = Store(f'postgresql://plea_local:local@127.0.0.1:5432/{db}')
root = 'REQ-RV/A/' + uuid.uuid4().hex
control.new_root(root, 10, 0)
cur = attempt_id('verify:' + 'c' * 64)
d1, _ = local.apply(root, ('RESERVE', cur, 'verify:' + 'c' * 64))
before = identity_form(local, root)
d2, _ = local.apply(root, ('RESERVE', 'a-' + '0' * 16, 'verify:planted'))
after = identity_form(local, root)
print(json.dumps({'reserve_current': [d1.kind, d1.code], 'form_before': before, 'reserve_planted': [d2.kind, d2.code], 'form_after': after,
                  'attempts': [a[0] for a in local.observe(root)['attempts']]}, indent=1))
