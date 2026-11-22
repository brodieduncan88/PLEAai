import json, os, resource
soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
fds, err = [], None
try:
    for _ in range(2000000):
        fds.append(os.open("/dev/null", os.O_RDONLY))
except OSError as e:
    err = repr(e)
print("SPIKE_RESULT " + json.dumps({"job": "fdexhaust", "ulimit_n_soft": soft, "ulimit_n_hard": hard, "opened": len(fds), "stopped_by": err}))
