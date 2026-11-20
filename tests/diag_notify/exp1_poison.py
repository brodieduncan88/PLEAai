"""E1: one run whose /run answer the courier cannot take (too long / connection dropped) hides every run sorted after it."""
import sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import harness, courier
from harness import World, verdict

def scenario(poison):
    w = World()
    fail = verdict('FAIL', 'LIMIT_NOT_MET')
    atts = [['a-fail1', 'r1', 'EFFECT', 'n1', True, True]]
    if poison:
        atts.append(['!x', 'r0', 'CONSUMED', 'n0', True, True])            # a run the service names so it sorts first
        # what courier._https raises for an answer over 32 MiB (courier.py:150-151); the service stored a 33 MiB 'unknown' result
        w.special['!x'] = lambda: (_ for _ in ()).throw(courier.Unreachable('the answer is too long'))
    w.decide(atts); w.report('a-fail1', 'n1', 'EFFECT', fail); w.store('a-fail1', fail)
    t0 = 1_000_000.0
    out = []
    for i, dt in enumerate([0, 1000, 2000]):
        s = w.run(t0 + dt); out.append(('pass', i, [m['outcome'] + ':' + m['aid'] for m in s['made']], len(s['unreachable'])))
    # a second failing run, later
    atts.append(['a-fail2', 'r2', 'EFFECT', 'n2', True, True]); w.decide(atts); w.report('a-fail2', 'n2', 'EFFECT', fail); w.store('a-fail2', fail)
    for i, dt in enumerate([3000, 4000, 99000]):
        s = w.run(t0 + dt); out.append(('pass', 3 + i, [m['outcome'] + ':' + m['aid'] for m in s['made']], len(s['unreachable'])))
    return out, w.held()

for p in (False, True):
    out, held = scenario(p)
    print('POISON' if p else 'CONTROL')
    for o in out: print('  ', o)
    print('   mailbox holds:', held)
