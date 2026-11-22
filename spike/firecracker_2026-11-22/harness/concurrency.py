#!/usr/bin/env python3
"""K VMs at once: per-VM timings and host totals. KVM host only. NOT RUN here."""
import argparse, json, threading, time
import fc_lib as L

p = argparse.ArgumentParser(); p.add_argument("-k", type=int, default=8); p.add_argument("--mem", type=int, default=128)
p.add_argument("--out", default="concurrency.json"); a = p.parse_args()
L.require_prereqs(); parent = L.prepare_parent(); before = L.host_sample(); res = []; vms = []; lock = threading.Lock()
def one(i):
    vm = L.VM(parent, job="workload", mem_mib=a.mem)
    with lock: vms.append(vm)
    try:
        vm.start(); tb = vm.wait_marker("SPIKE_BEGIN"); ok = vm.wait_exit(120); r = vm.result() or {}
        with lock: res.append({"i": i, "ok": bool(ok and r), "cold_start_s": (tb - vm.t["t0"]) if tb else None,
                               "total_s": vm.t.get("exit", float("nan")) - vm.t["t0"]})
    except Exception as e:  # noqa: BLE001
        with lock: res.append({"i": i, "ok": False, "error": repr(e)})
t0 = time.monotonic(); th = [threading.Thread(target=one, args=(i,)) for i in range(a.k)]
[t.start() for t in th]; peak = []
while any(t.is_alive() for t in th):
    peak.append(L.host_sample([v.proc.pid for v in vms if v.proc and v.proc.poll() is None])); time.sleep(0.1)
[t.join() for t in th]; wall = time.monotonic() - t0
clean = [v.cleanup() for v in vms]; time.sleep(0.5); after = L.host_sample()
out = {"k": a.k, "wall_s": wall, "ok": sum(r["ok"] for r in res), "results": res,
       "peak_file_nr_delta": max([s["file_nr_allocated"] - before["file_nr_allocated"] for s in peak] or [0]),
       "peak_total_vmm_fds": max([sum(v.get("fds", 0) for v in s["vmm"].values()) for s in peak] or [0]),
       "peak_total_vmm_rss_kib": max([sum(v.get("rss_kib", 0) for v in s["vmm"].values()) for s in peak] or [0]),
       "min_mem_available_delta_kib": min([s["mem_available_kib"] - before["mem_available_kib"] for s in peak] or [0]),
       "all_cleaned": all(clean), "file_nr_after_minus_before": after["file_nr_allocated"] - before["file_nr_allocated"]}
json.dump(out, open(a.out, "w"), indent=2); print(json.dumps({k: v for k, v in out.items() if k != "results"}, indent=2))
