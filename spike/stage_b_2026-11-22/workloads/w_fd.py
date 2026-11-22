# T05/T07: open /dev/null until `target` descriptors or an error; hold `hold` seconds; then exit.
import errno, json, os, resource, time
P = globals().get("PARAMS", {})
target, hold, secs = int(P.get("target", 1000000)), float(P.get("hold", 3)), float(P.get("seconds", 90))
t0, fds, err, prog = time.monotonic(), [], None, []
end = t0 + secs
try:
    while len(fds) < target and time.monotonic() < end:
        fds.append(os.open("/dev/null", os.O_RDONLY))
        if len(fds) % 100000 == 0:
            prog.append([len(fds), round(time.monotonic() - t0, 3)])
except OSError as e:
    err = errno.errorcode.get(e.errno, e.errno)
fnr = open("/proc/sys/fs/file-nr").read().split()
t_peak = round(time.monotonic() - t0, 3)
time.sleep(hold)
print(json.dumps({"opened": len(fds), "target": target, "stopped_by": err, "t_peak_s": t_peak,
                  "rlimit_nofile": resource.getrlimit(resource.RLIMIT_NOFILE), "guest_file_nr_at_peak": fnr,
                  "guest_file_max": open("/proc/sys/fs/file-max").read().strip(), "progress": prog}))
