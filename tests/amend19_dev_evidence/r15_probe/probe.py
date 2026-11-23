"""Expectation (written before running): at 2c1af26, text(dec('1e1000000')) raises or produces >1e6 chars (so evaluate's path ends in CHECK_ERROR); at 3d6598f, _shown bounds it, so RESULT_IMPLAUSIBLE is built with a short detail."""
import sys, time
sys.path.insert(0, sys.argv[1] + '/verify')
import baseline as B
d = B.dec('1e1000000'); print('dec', repr(d)[:40])
t=time.time()
try:
    s = B.text(d); print('text len', len(s), round(time.time()-t,2))
except Exception as e: print('text raised', type(e).__name__, str(e)[:100])
if hasattr(B, '_shown'): print('shown', B._shown(d))
