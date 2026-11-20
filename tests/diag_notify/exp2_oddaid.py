"""E2: a run named so the witness's /run refuses it (aid > 512 chars, or with DEL) is never read; one COURIER_BLOCKED, then silence.
E3: a gate-signed result whose verdict field says PASS against its own reason code: courier sends nothing, marks it final."""
import sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import harness, courier, json
from harness import World, verdict
w = World(); fail = verdict('FAIL', 'LIMIT_NOT_MET')
odd1 = 'a-' + 'z' * 520
atts = [[odd1, 'r1', 'EFFECT', 'n1', True, True]]
w.decide(atts); w.report(odd1, 'n1', 'EFFECT', fail); w.store(odd1, fail)
t0 = 1e6
for dt in (0, 1000, 2000):
    s = w.run(t0 + dt); print('pass', dt, [m['outcome'] for m in s['made']], [u['why'][:90] for u in s['unreachable']])
odd2 = 'a-bad\x7f'
atts.append([odd2, 'r2', 'EFFECT', 'n2', True, True]); w.decide(atts); w.report(odd2, 'n2', 'EFFECT', fail); w.store(odd2, fail)
atts.append(['a-ok', 'r3', 'EFFECT', 'n3', True, True]); w.decide(atts); w.report('a-ok', 'n3', 'EFFECT', fail); w.store('a-ok', fail)
for dt in (3000, 9000, 90000):
    s = w.run(t0 + dt); print('pass', dt, [m['outcome'] + ':' + m['aid'][:8] for m in s['made']], len(s['unreachable']))
print('mailbox:', [(a[:8], o) for a, o in w.held()])
print('BLOCKED words:', [x['notice']['text'] for x in w.box.held() if x['notice']['outcome'] == 'COURIER_BLOCKED'][0][:400])

print('--- E3')
w = World()
bad = {'format': 'verification-verdict/1', 'verdict': 'PASS', 'reason_code': 'LIMIT_NOT_MET', 'criteria': [{'id': 'c', 'achieved': 9, 'limit': 1, 'comparison': '<=', 'met': False}], 'detail': ''}
w.decide([['a-x', 'r', 'EFFECT', 'n', True, True]]); w.report('a-x', 'n', 'EFFECT', bad); w.store('a-x', bad)
s = w.run(t0); print('made', s['made'], 'final', json.load(open(w.tmp / 'state' / 'state.json'))['roots'][harness.ROOT]['final'])
