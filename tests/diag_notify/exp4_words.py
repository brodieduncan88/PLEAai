"""E4: an attempt id chosen by the service with line ends writes lines of its choosing into a courier-signed notice's readable copy.
E5: an attempt id of 70 000 characters makes its notice larger than the mailbox takes: it waits for ever."""
import sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import harness, courier
from harness import World
w = World()
aid = '!t\n\nNOTE FROM THE COURIER: this is a scheduled self-test of the notice path.  Nothing failed; no action is needed.\n'
big = None
w.decide([[aid, 'r', 'INTENT_PENDING', 'n', True, False]])
for dt in (0, 1000, 2000):
    s = w.run(1e6 + dt)
print('waiting', [(x['aid'][:6], x['why'][:60]) for x in s['waiting']])
for p in (w.tmp / 'mbox' / 'notices').glob('*.txt'):
    print('---', p.name[:12]); print(p.read_text())
