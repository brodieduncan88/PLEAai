#!/usr/bin/env python3
"""T05: CPU, memory, process and file-descriptor limits.
Caps: cpu 2 procs x 8 s at cpu.max 0.5 CPU; memory 512 MiB balloon in a 256 MiB guest;
fork <= 20000 children / 10 s; fds <= 100000 opens. All jobs have guest and host timeouts."""
import json
import os
import re
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import fclib, main, payload, slim  # noqa: E402

QUOTA, TOL = 0.5, 1.15


def series(key_fn):
    """fclib sampler that appends (t, value) to ctx['series'] (bounded)."""
    def f(ctx, now):
        s = ctx.setdefault("series", [])
        if len(s) < 5000 and ctx.get("pid"):
            try:
                s.append((now, key_fn(ctx)))
            except OSError:
                pass
    return f


def cg_sample(ctx):
    cg, pid = ctx.get("cgroup"), ctx["pid"]
    st = open(f"/proc/{pid}/status").read()
    out = {"threads": int(re.search(r"^Threads:\s+(\d+)", st, re.M).group(1)),
           "fds": len(os.listdir(f"/proc/{pid}/fd"))}
    if cg and os.path.isdir(cg):
        out.update(fclib.kv(open(f"{cg}/cpu.stat").read()))
        out["memory.current"] = int(open(f"{cg}/memory.current").read())
        out["pids.current"] = int(open(f"{cg}/pids.current").read())
    return out


def run(label, pl, **kw):
    holder = {}
    def keep(ctx):
        holder["series"] = ctx.get("series", [])
    r = fclib.run_vm(pl, label=label, sampler=series(cg_sample), after_exit=keep, **kw)
    return r, holder.get("series", [])


def holder_t(r):
    return r.get("t_spawn_monotonic")


def window(series, t_ready, t_done):
    pts = [(t, v) for t, v in series if "usage_usec" in v]
    a = min(pts, key=lambda p: abs(p[0] - t_ready), default=None)
    b = min(pts, key=lambda p: abs(p[0] - t_done), default=None)
    return a, b


def t05(t):
    t.gate()
    # (a) CPU
    r, s = run("T05-cpu", payload("w_cpu", procs=2, seconds=8), vcpus=2, cpu_max=str(int(QUOTA * 100000)),
               guest_timeout=40, host_timeout=120)
    ts = r.get("timings_s") or {}
    ratio = thr = None
    if s and holder_t(r) and ts.get("ready") is not None and ts.get("done") is not None:
        a, b = window(s, holder_t(r) + ts["ready"], holder_t(r) + ts["done"])
        if a and b and b[0] > a[0]:
            ratio = (b[1]["usage_usec"] - a[1]["usage_usec"]) / ((b[0] - a[0]) * 1e6)
            thr = b[1].get("nr_throttled", 0) - a[1].get("nr_throttled", 0)
    t.data["cpu"] = {"run": slim(r), "usage_ratio": ratio, "nr_throttled_delta": thr, "samples": len(s)}
    t.pred("T05.P1", f"VM cgroup CPU usage / wall time during the spin <= {QUOTA} x {TOL}",
           r["ok"] and ratio is not None and ratio <= QUOTA * TOL, ratio)
    t.pred("T05.P2", "cpu.stat nr_throttled increased during the spin", bool(thr and thr > 0), thr)
    # (b) memory
    MEM = 256
    r, s = run("T05-mem", payload("w_mem", target_mib=512, chunk_mib=8), mem_mib=MEM, guest_timeout=60, host_timeout=150)
    ce = r.get("cgroup_after_exit") or {}
    ev = fclib.kv(ce.get("memory.events", ""))
    mmax = int(ce.get("memory.max", "0") or 0) if ce.get("memory.max", "").isdigit() else None
    peak = int(ce["memory.peak"]) if ce.get("memory.peak", "").isdigit() else max([v.get("memory.current", 0) for _, v in s] or [0])
    hdr = r.get("result_parsed") or {}
    last = (r.get("stdout") or "").strip().splitlines()[-1:] or [""]
    t.data["memory"] = {"run": slim(r), "memory.events": ev, "memory.max": mmax, "peak": peak, "guest_last_line": last[0],
                        "guest_console_oom": "Out of memory" in (r.get("console", {}).get("head", "") + r.get("console", {}).get("tail", ""))}
    t.pred("T05.P3", "host cgroup memory.events oom_kill == 0 and the VMM exited after PLEA_DONE (guest-initiated reboot)",
           ev.get("oom_kill", 1) == 0 and r.get("done") and r.get("vmm_exit_code") == 0,
           {"oom_kill": ev.get("oom_kill"), "exit": r.get("vmm_exit_code"), "done": r.get("done")})
    t.pred("T05.P4", "VM cgroup memory peak <= memory.max", mmax is not None and peak <= mmax, {"peak": peak, "max": mmax})
    t.pred("T05.P5", "guest did not obtain the 512 MiB it asked for (guest OOM / MemoryError, exit != 0 or outcome != target_reached)",
           hdr.get("status") == "OK" and (hdr.get("exit") != 0 or "target_reached" not in last[0]),
           {"exit": hdr.get("exit"), "last": last[0]})
    # (c) fork, limited by guest RLIMIT_NPROC, then (c2) effectively unlimited inside the guest
    for tag, nproc, pid_a, pid_b in (("fork", 512, "T05.P6", "T05.P7"), ("fork_unlimited", 100000, "T05.P8", "T05.P9")):
        r, s = run(f"T05-{tag}", payload("w_fork", max=20000, seconds=10), mem_mib=256, guest_nproc=nproc,
                   guest_timeout=40, host_timeout=120)
        out = {}
        try:
            out = json.loads((r.get("stdout") or "").strip().splitlines()[-1])
        except (ValueError, IndexError):
            pass
        thr_vals = [v["threads"] for _, v in s if "threads" in v]
        pmax = max([v.get("pids.current", 0) for _, v in s] or [0])
        t.data[tag] = {"run": slim(r), "guest": out, "vmm_threads_min_max": [min(thr_vals or [0]), max(thr_vals or [0])],
                       "pids_current_max": pmax, "pids.events": (r.get("cgroup_after_exit") or {}).get("pids.events")}
        if tag == "fork":
            t.pred(pid_a, "guest fork bomb stopped by the guest (EAGAIN) below 20000 with RLIMIT_NPROC=512",
                   out.get("stopped_by_errno") == 11 and out.get("forked", 99999) < 20000, out)
        else:
            t.pred(pid_a, "with guest RLIMIT_NPROC unlimited the job still terminated (guest result or host watchdog) and cleanup was clean",
                   r["clean"] and (r.get("done") or r.get("watchdog_fired")), {"guest": out, "watchdog": r.get("watchdog_fired")})
        t.pred(pid_b, "host VMM thread count constant during the guest fork bomb and VM pids.current <= pids.max",
               bool(thr_vals) and min(thr_vals) == max(thr_vals) and pmax <= 64,
               {"threads": [min(thr_vals or [0]), max(thr_vals or [0])], "pids_current_max": pmax})
    # (d) file descriptors
    r, s = run("T05-fd", payload("w_fd", target=100000, hold=1, seconds=30), guest_nofile=1024, guest_timeout=40, host_timeout=120)
    out = {}
    try:
        out = json.loads((r.get("stdout") or "").strip().splitlines()[-1])
    except (ValueError, IndexError):
        pass
    fds = [v["fds"] for _, v in s if "fds" in v]
    at_ready = (r.get("vmm_at_ready") or {}).get("fd_count")
    t.data["fd"] = {"run": slim(r), "guest": out, "vmm_fds_at_ready": at_ready, "vmm_fds_max": max(fds or [0])}
    t.pred("T05.P10", "guest stopped at its own RLIMIT_NOFILE (<= 1024 opened, EMFILE)",
           out.get("stopped_by") == "EMFILE" and out.get("opened", 99999) <= 1024, out)
    t.pred("T05.P11", "host VMM fd count max during the run - fd count at READY <= 2",
           at_ready is not None and fds and max(fds) - at_ready <= 2, {"at_ready": at_ready, "max": max(fds or [0])})


if __name__ == "__main__":
    sys.exit(main(t05, "T05", "CPU, memory, process and file-descriptor limits"))
