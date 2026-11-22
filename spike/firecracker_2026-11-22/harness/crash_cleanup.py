#!/usr/bin/env python3
"""kill -9 the VMM mid-run, then show what is (and is not) left behind, run recovery, show clean. KVM host only. NOT RUN here.
Expectation to be tested, not assumed: cgroup becomes empty (populated 0); the API socket and VM dir are NOT removed by
SIGKILL (Firecracker cannot clean up after itself), so recover_orphans.py must remove them."""
import json, os, signal, subprocess, sys, time
from pathlib import Path
import fc_lib as L

L.require_prereqs(); parent = L.prepare_parent()
vm = L.VM(parent, job="sleep"); vm.start(); vm.wait_marker("SPIKE_BEGIN"); time.sleep(1)
pid = vm.proc.pid; rep = {"pid": pid, "cgroup": str(vm.cg), "populated_before": L.cg_populated(vm.cg)}
os.kill(pid, signal.SIGKILL); vm.proc.wait(); time.sleep(0.2)
rep["after_kill"] = {"cgroup_populated": L.cg_populated(vm.cg) if vm.cg.exists() else None,
                     "cgroup_exists": vm.cg.exists(), "cgroup_procs": L.cg_read(vm.cg, "cgroup.procs") if vm.cg.exists() else None,
                     "vm_dir_exists": vm.dir.exists(), "socket_exists": vm.sock.exists(),
                     "taps": sorted(n for n in os.listdir("/sys/class/net") if n.startswith("fcspike")),
                     "proc_alive": Path("/proc/%d" % pid).exists()}
r = subprocess.run([sys.executable, str(L.HERE / "recover_orphans.py"), "--cgroup-parent", str(parent), "--apply"], capture_output=True, text=True)
rep["recovery_stdout"] = r.stdout; rep["recovery_rc"] = r.returncode
rep["after_recovery"] = {"cgroup_exists": vm.cg.exists(), "vm_dir_exists": vm.dir.exists(), "socket_exists": vm.sock.exists(),
                         "taps": sorted(n for n in os.listdir("/sys/class/net") if n.startswith("fcspike"))}
rep["clean"] = not any([rep["after_recovery"]["cgroup_exists"], rep["after_recovery"]["vm_dir_exists"], rep["after_recovery"]["taps"]])
print(json.dumps(rep, indent=2)); sys.exit(0 if rep["clean"] else 1)
