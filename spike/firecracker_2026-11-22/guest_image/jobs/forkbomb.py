import json, os, signal, time
kids, err = [], None
for _ in range(20000):                      # bounded "fork bomb": children just sleep
    try:
        pid = os.fork()
    except OSError as e:
        err = repr(e); break
    if pid == 0:
        time.sleep(30); os._exit(0)
    kids.append(pid)
n = len(kids)
for k in kids:
    try: os.kill(k, signal.SIGKILL)
    except OSError: pass
print("SPIKE_RESULT " + json.dumps({"job": "forkbomb", "forked": n, "stopped_by": err or "loop bound 20000"}))
