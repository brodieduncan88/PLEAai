#!/bin/bash
# Stage 0: read-only host facts. Changes nothing on the host except writing evidence and state/ in the bundle.
# If /dev/kvm is missing or not functional, or cgroup v2 is not mounted, writes state/BLOCKED and every later
# stage refuses to run. There is no weaker-isolation fallback.
set -uo pipefail
B=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
EV=${PLEA_EVIDENCE:?run via run_stage.sh}
F="$EV/stage0"; mkdir -p "$F"
cap() { timeout 30 "$@" 2>&1 | head -c 262144; }
cap uname -a                                  > "$F/uname.txt"
cap cat /etc/os-release                       > "$F/os-release.txt"
grep -m1 '^flags' /proc/cpuinfo | head -c 8192 > "$F/cpu_flags.txt"
echo "vmx_cpus=$(grep -c -w vmx /proc/cpuinfo) svm_cpus=$(grep -c -w svm /proc/cpuinfo) nproc=$(nproc)" > "$F/virt_flags.txt"
cap lscpu                                     > "$F/lscpu.txt"
cap ls -l /dev/kvm                            > "$F/dev_kvm.txt"
cap stat -f -c %T /sys/fs/cgroup              > "$F/cgroup_fstype.txt"
cap cat /sys/fs/cgroup/cgroup.controllers     > "$F/cgroup_controllers.txt"
cap cat /sys/fs/cgroup/cgroup.subtree_control > "$F/cgroup_subtree_control.txt"
cap cat /proc/swaps                           > "$F/swaps.txt"
cap swapon --show                             > "$F/swapon.txt"
cap sysctl fs.file-max fs.nr_open fs.file-nr kernel.pid_max vm.overcommit_memory > "$F/sysctl.txt"
bash -c 'ulimit -a' 2>&1 | head -c 8192       > "$F/ulimits.txt"
cap free -m                                   > "$F/memory.txt"
cap df -h /                                   > "$F/disk.txt"
cap df -h /opt /srv /var /tmp                >> "$F/disk.txt"
for x in product_name sys_vendor bios_vendor; do
	printf '%s=%s\n' "$x" "$(cat /sys/class/dmi/id/$x 2>/dev/null)"; done > "$F/dmi.txt"
cap cat /sys/module/kvm_intel/parameters/nested > "$F/kvm_intel_nested.txt"
cap lsmod                                     > "$F/lsmod.txt"
cap python3 --version                         > "$F/python.txt"
cap systemctl --version                       > "$F/systemd.txt"
if [ -r /usr/include/linux/kvm.h ]; then
	grep -E '#define KVM_(GET_API_VERSION|CREATE_VM|CHECK_EXTENSION|CAP_(IRQCHIP|USER_MEMORY|SET_TSS_ADDR|EXT_CPUID|NR_VCPUS|NR_MEMSLOTS|MP_STATE|IRQFD|PIT2|IOEVENTFD))\b' \
		/usr/include/linux/kvm.h > "$F/kvm_h_crosscheck.txt"
else
	echo "linux/kvm.h not installed; capability numbers in prereq.py are not cross-checked on this host" > "$F/kvm_h_crosscheck.txt"
fi
timeout 60 python3 -I -B - "$B" "$EV/stage0_host.json" <<'PY'
import json, os, sys, time
sys.path.append(sys.argv[1])
import config, prereq
p = config.paths()
c = [prereq._check("P01", "kvm_char_device", lambda: prereq.kvm_device(p)),
     prereq._check("P02", "kvm_ioctl_api12_caps_create_vm", lambda: prereq.kvm_ioctl(p)),
     prereq._check("P03", "cgroup_v2_root_controllers", lambda: prereq.cgroup_v2(p)),
     prereq._check("P10", "swap_off", lambda: prereq.swap_off(p)),
     prereq._check("P11", "memory_above_minimum", lambda: prereq.memory(p))]
fstype = open("/proc/self/mountinfo").read()
cg2 = any(l.split(" - ")[1].split()[0] == "cgroup2" and l.split()[4] == "/sys/fs/cgroup" for l in fstype.splitlines() if " - " in l)
blocked = [x["id"] + ":" + x["name"] for x in c[:2] if not x["met"]] + ([] if cg2 else ["cgroup2 not mounted at /sys/fs/cgroup"])
out = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "checks": c, "cgroup2_mounted": cg2,
       "verdict": "BLOCKED" if blocked else "OK", "blocked_by": blocked,
       "note": "P03 (root subtree_control) and P10/P11 are informational here; stage2 fixes P03/P10."}
json.dump(out, open(sys.argv[2], "w"), indent=1)
for x in c:
    print(f"{x['id']} {x['status']:8} {x['name']}")
print("verdict:", out["verdict"], blocked)
sys.exit(3 if blocked else 0)
PY
rc=$?
mkdir -p "$B/state"
if [ "$rc" -eq 3 ] || [ "$rc" -gt 128 ] || [ "$rc" -eq 124 ]; then
	echo "stage0 BLOCKED: /dev/kvm missing/non-functional or cgroup v2 absent (see $EV/stage0_host.json)" > "$B/state/BLOCKED"
	echo "BLOCKED - all later stages will refuse. Terminate the instance (see README teardown)."
	exit 3
fi
exit "$rc"
