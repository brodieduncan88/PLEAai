#!/usr/bin/env python3
"""Resource-limit verification. KVM host only. NOT RUN here.
Checks (1) configured guest memory/vCPU via GET /machine-config, (2) cgroup v2 memory.max / pids.max / cpu.max
read back on the VMM, (3) guest ulimit -n, and runs in-guest fork bomb, memory balloon, fd and mmap exhaustion.
NOTE: guest processes are bounded by the GUEST kernel; host pids.max bounds only VMM threads."""
import argparse, json
import fc_lib as L

JOBS = [("forkbomb", ""), ("membloat", ""), ("fdexhaust", "spike.nofile=256"), ("mmapexhaust", "")]
p = argparse.ArgumentParser(); p.add_argument("--mem", type=int, default=128); p.add_argument("--vcpus", type=int, default=2)
p.add_argument("--out", default="limits_test.json"); a = p.parse_args()
L.require_prereqs(); parent = L.prepare_parent(); report = []
for job, extra in JOBS:
    vm = L.VM(parent, job=job, mem_mib=a.mem, vcpus=a.vcpus, cmdline_extra=extra)
    entry = {"job": job}
    try:
        vm.start(); vm.wait_marker("SPIKE_BEGIN")
        _, mc = L.api(str(vm.sock), "GET", "/machine-config")
        entry["machine_config"] = json.loads(mc)
        entry["cgroup"] = {k: L.cg_read(vm.cg, k) for k in ("memory.max", "pids.max", "cpu.max")}
        entry["exited"] = vm.wait_exit(90)
        entry["guest_result"] = vm.result()
        for k in ("memory.events", "pids.events"):
            try: entry["cgroup"][k] = L.cg_read(vm.cg, k).replace("\n", ";")
            except OSError: pass
        entry["vmm_returncode"] = vm.proc.returncode
        mc = entry["machine_config"]
        entry["checks"] = {"mem_size_matches": mc.get("mem_size_mib") == a.mem, "vcpus_match": mc.get("vcpu_count") == a.vcpus,
                           "cgroup_limits_match_config": all(entry["cgroup"][k] == v for k, v in vm.limits.items())}
    finally:
        entry["cleanup_ok"] = vm.cleanup(); report.append(entry)
json.dump(report, open(a.out, "w"), indent=2); print(json.dumps(report, indent=2))
