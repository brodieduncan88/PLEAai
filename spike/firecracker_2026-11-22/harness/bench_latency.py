#!/usr/bin/env python3
"""Cold-start latency and total execution overhead over N runs. KVM host only. NOT RUN here.
cold_start = Popen -> first guest marker SPIKE_BEGIN on serial console.
total      = Popen -> VMM exit (guest reboots itself after the job).
overhead   = total - guest-reported job time. Baseline = same workload run natively (host python3)."""
import argparse, json, statistics as S, subprocess, sys, time
import fc_lib as L

p = argparse.ArgumentParser(); p.add_argument("-n", type=int, default=30)
p.add_argument("--mem", type=int, default=128); p.add_argument("--vcpus", type=int, default=1)
p.add_argument("--out", default="bench_latency.json"); a = p.parse_args()
L.require_prereqs()
parent = L.prepare_parent()
runs = []
for i in range(a.n):
    vm = L.VM(parent, job="workload", mem_mib=a.mem, vcpus=a.vcpus)
    try:
        vm.start()
        tb = vm.wait_marker("SPIKE_BEGIN")
        ok = vm.wait_exit()
        r = vm.result() or {}
        runs.append({"i": i, "ok": bool(ok and r), "api_ready_s": vm.t["api_ready"] - vm.t["t0"],
                     "cold_start_s": (tb - vm.t["t0"]) if tb else None,
                     "total_s": vm.t.get("exit", float("nan")) - vm.t["t0"],
                     "guest_job_s": r.get("elapsed_s"), "digest": r.get("digest")})
    finally:
        vm.cleanup()
# native baseline (workload script is shared with the guest image)
base = []
for _ in range(a.n):
    t = time.monotonic()
    out = subprocess.run([sys.executable, "-I", "-B", str(L.ROOT / "guest_image" / "jobs" / "workload.py")],
                         capture_output=True, text=True).stdout
    base.append(time.monotonic() - t)
def stats(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs: return None
    return {"n": len(xs), "min": xs[0], "median": S.median(xs), "p95": xs[min(len(xs) - 1, int(0.95 * len(xs)))], "max": xs[-1]}
good = [r for r in runs if r["ok"]]
summary = {"runs": a.n, "ok": len(good), "digests_identical": len({r["digest"] for r in good}) == 1,
           "cold_start_s": stats([r["cold_start_s"] for r in good]), "total_s": stats([r["total_s"] for r in good]),
           "overhead_s": stats([r["total_s"] - r["guest_job_s"] for r in good if r["guest_job_s"] is not None]),
           "native_baseline_s": stats(base)}
json.dump({"summary": summary, "runs": runs}, open(a.out, "w"), indent=2)
print(json.dumps(summary, indent=2))
