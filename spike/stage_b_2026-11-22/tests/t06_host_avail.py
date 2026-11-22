#!/usr/bin/env python3
"""T06: guest resource exhaustion must not compromise host availability.
For each exhaustion job a host sampler runs every 200 ms (probe latency of spawning /bin/true, load, MemAvailable)
and, once the exhausting VM is READY, a second microVM must start and finish.
Caps: cpu 2 vCPU spin 20 s (cpu.max 2 CPUs of 4); mem 1024 MiB guest asked for 2048 MiB; fork <= 20000 / 15 s;
fd <= 1,000,000 opens in a 1024 MiB guest. Every VM has guest and host timeouts."""
import json
import os
import secrets
import sys
import threading

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import Sampler, fclib, main, payload, slim, util  # noqa: E402

P95_MS, MAX_MS, MIN_FREE_MIB = 250, 2000, 512
JOBS = {
    "cpu": (payload("w_cpu", procs=2, seconds=20), dict(vcpus=2, cpu_max="200000", mem_mib=256, guest_timeout=60, host_timeout=150)),
    "mem": (payload("w_mem", target_mib=2048, chunk_mib=16), dict(mem_mib=1024, guest_timeout=90, host_timeout=180)),
    "fork": (payload("w_fork", max=20000, seconds=15), dict(mem_mib=256, guest_nproc=100000, guest_timeout=60, host_timeout=150)),
    "fd": (payload("w_fd", target=1000000, hold=3, seconds=90), dict(mem_mib=1024, guest_nofile=1048576,
                                                                       guest_filemax=1100000, guest_timeout=150, host_timeout=240)),
}


def t06(t):
    t.gate()
    for job, (pl, kw) in JOBS.items():
        ready = threading.Event()
        res = {}
        smp = Sampler(0.2)
        smp.start()
        th = threading.Thread(target=lambda: res.__setitem__("primary", fclib.run_vm(
            pl, label=f"T06-{job}", on_ready=lambda ctx: ready.set(), **kw)), daemon=True)
        th.start()
        second = None
        if ready.wait(timeout=kw["host_timeout"]):
            nonce = secrets.token_hex(8)
            second = fclib.run_vm(payload("w_echo", nonce=nonce), label=f"T06-{job}-second")
            try:
                second_ok = second["ok"] and json.loads(second.get("stdout") or "{}").get("nonce") == nonce
            except ValueError:
                second_ok = False
        else:
            second_ok = False
        th.join(timeout=kw["host_timeout"] + 60)
        samples = smp.stop()
        prim = res.get("primary", {})
        lat = util.pctl([s["probe_ms"] for s in samples])
        mem_min = min([s["mem_avail_mib"] for s in samples] or [0])
        t.data[job] = {"primary": slim(prim), "second": slim(second) if second else None, "probe_ms": lat,
                       "load1_max": max([s["load1"] for s in samples] or [0]), "mem_avail_min_mib": mem_min,
                       "samples": samples[::5][:400]}
        t.pred(f"T06.{job}.P1", f"host probe latency p95 <= {P95_MS} ms and max <= {MAX_MS} ms while the job ran",
               bool(lat) and lat["p95"] <= P95_MS and lat["max"] <= MAX_MS, lat)
        t.pred(f"T06.{job}.P2", f"host MemAvailable never below {MIN_FREE_MIB} MiB", mem_min >= MIN_FREE_MIB, mem_min)
        t.pred(f"T06.{job}.P3", "a second microVM started during the exhaustion and returned its own nonce", second_ok,
               {"second_ok": second and second.get("ok"), "timings": second and second.get("timings_s")})
        t.pred(f"T06.{job}.P4", "the exhausting VM ended (PLEA_DONE or watchdog) and both VMs cleaned up",
               bool(prim) and prim.get("clean") and (prim.get("done") or prim.get("watchdog_fired"))
               and bool(second) and second.get("clean"),
               {"primary_done": prim.get("done"), "watchdog": prim.get("watchdog_fired"), "primary_clean": prim.get("clean")})


if __name__ == "__main__":
    sys.exit(main(t06, "T06", "Guest exhaustion without compromising host availability"))
