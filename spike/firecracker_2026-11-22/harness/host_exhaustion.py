#!/usr/bin/env python3
"""Host-side cost while a guest tries to exhaust ITS OWN files and mappings. KVM host only. NOT RUN here.
Records /proc/sys/fs/file-nr and MemAvailable before / during / after, and the VMM's own host fds,
threads and RSS per VM. This measures; it does not assume Firecracker removes host file-table limits."""
import argparse, json, time
import fc_lib as L

p = argparse.ArgumentParser(); p.add_argument("--mem", type=int, default=128); p.add_argument("--out", default="host_exhaustion.json")
a = p.parse_args(); L.require_prereqs(); parent = L.prepare_parent(); out = []
for job, extra in (("fdexhaust", ""), ("mmapexhaust", ""), ("fdmmap", "")):
    before = L.host_sample(); vm = L.VM(parent, job=job, mem_mib=a.mem)
    try:
        vm.start(); vm.wait_marker("SPIKE_BEGIN"); during = []
        while vm.proc.poll() is None and len(during) < 600:
            during.append(L.host_sample([vm.proc.pid])); time.sleep(0.1)
        vm.wait_exit(60)
        peak = {"max_vmm_fds": max([v.get("fds", 0) for s in during for v in s["vmm"].values()] or [0]),
                "max_vmm_rss_kib": max([v.get("rss_kib", 0) for s in during for v in s["vmm"].values()] or [0]),
                "max_file_nr_delta": max([s["file_nr_allocated"] - before["file_nr_allocated"] for s in during] or [0]),
                "min_mem_available_delta_kib": min([s["mem_available_kib"] - before["mem_available_kib"] for s in during] or [0])}
        res = vm.result()
    finally:
        vm.cleanup()
    time.sleep(0.5); after = L.host_sample()
    out.append({"job": job, "guest_result": res, "before": before, "samples_during": len(during), "peak": peak, "after": after,
                "file_nr_after_minus_before": after["file_nr_allocated"] - before["file_nr_allocated"],
                "mem_available_after_minus_before_kib": after["mem_available_kib"] - before["mem_available_kib"]})
json.dump(out, open(a.out, "w"), indent=2); print(json.dumps([{k: v for k, v in o.items() if k in ("job", "peak", "file_nr_after_minus_before", "mem_available_after_minus_before_kib")} for o in out], indent=2))
