# T05/T06: spin `procs` processes for `seconds` seconds (bounded).
import json, os, time
P = globals().get("PARAMS", {})
n, secs = int(P.get("procs", 2)), float(P.get("seconds", 5))
pids = []
for _ in range(n):
    pid = os.fork()
    if pid == 0:
        end, i = time.monotonic() + secs, 0
        while time.monotonic() < end:
            i += 1
        os._exit(0)
    pids.append(pid)
for pid in pids:
    os.waitpid(pid, 0)
print(json.dumps({"procs": n, "seconds": secs, "cpu_times": os.times()[2:4]}))
