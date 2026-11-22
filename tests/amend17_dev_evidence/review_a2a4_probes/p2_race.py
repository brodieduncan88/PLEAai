"""P2 (review A2). Expectation before the run: 30 rounds; each round a new job, 20 threads observe seq 1 (CURRENT digest),
one thread observes seq 2 revoked, all released at once. PREDICTION: every round ends with the row revoked and a later
observe of seq 1 or 2 answers REVOKED; no exception; no thread that ran after the revocation answered CURRENT for seq 2."""
import sys, threading, uuid, json
W = sys.argv[1]; sys.path.insert(0, W); sys.path.insert(0, W + '/verify')
from plea_gateway import Store
import front_state
DSN = 'postgresql://plea_local:local@127.0.0.1:5432/plea_rv2'
bad, errs = [], []
for rnd in range(30):
    job = 'race-' + uuid.uuid4().hex[:8]; go = threading.Barrier(21); ans = []
    def obs(seq, rev, sha):
        go.wait()
        try:
            ans.append((seq, front_state.observe(Store(DSN), job, seq, sha, rev)))
        except Exception as exc:
            errs.append(repr(exc))
    ts = [threading.Thread(target=obs, args=(1, False, 'a' * 64)) for _ in range(20)] + [threading.Thread(target=obs, args=(2, True, 'b' * 64))]
    [t.start() for t in ts]; [t.join() for t in ts]
    after = [front_state.observe(Store(DSN), job, s, x, False) for s, x in ((1, 'a' * 64), (2, 'b' * 64), (3, 'c' * 64))]
    if after != ['REVOKED'] * 3 or (2, 'REVOKED') not in ans:
        bad.append((job, ans, after))
print(json.dumps({'rounds': 30, 'bad': bad, 'errors': errs[:5]}, indent=1))
