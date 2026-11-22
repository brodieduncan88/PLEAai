# T05/T06: fork until the guest refuses (RLIMIT_NPROC / pid_max / memory) or `max` children (bounded).
import json, os, signal, time
P = globals().get("PARAMS", {})
cap, secs = int(P.get("max", 20000)), float(P.get("seconds", 10))
kids, err, end = [], None, time.monotonic() + secs
while len(kids) < cap and time.monotonic() < end:
    try:
        pid = os.fork()
    except OSError as e:
        err = e.errno
        break
    if pid == 0:
        os.closerange(0, 3)  # never hold the result pipe
        time.sleep(secs + 30)
        os._exit(0)
    kids.append(pid)
for pid in kids:
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
print(json.dumps({"forked": len(kids), "stopped_by_errno": err, "cap": cap}))
