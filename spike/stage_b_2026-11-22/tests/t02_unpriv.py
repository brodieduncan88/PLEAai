#!/usr/bin/env python3
"""T02: the VMM runs unprivileged, seccomp-filtered, inside its cgroup, with the declared limits."""
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import config, fclib, main, payload  # noqa: E402

CPU_MAX, PIDS, FSIZE, NOFILE, MEM = "100000", 64, 16 << 20, 1024, 128


def t02(t):
    t.gate()
    r = fclib.run_vm(payload("w_sleep", seconds=3), label="T02", cpu_max=CPU_MAX, pids_max=PIDS,
                     fsize=FSIZE, nofile=NOFILE, mem_mib=MEM)
    t.data["run"] = r
    s, cg = r.get("vmm_at_ready") or {}, r.get("cgroup_at_ready") or {}
    uid = r.get("uid")
    ids = lambda k: (s.get(k) or "").split()
    t.pred("T02.P1", "VMM real/effective/saved/fs uid and gid all equal the allocated non-zero id; no supplementary groups",
           uid not in (None, 0) and ids("Uid") == [str(uid)] * 4 and ids("Gid") == [str(uid)] * 4 and ids("Groups") == [],
           {k: s.get(k) for k in ("Uid", "Gid", "Groups")})
    th = s.get("threads_seccomp") or {}
    t.pred("T02.P2", "every VMM thread has Seccomp: 2 (filter mode)", bool(th) and all(v == 2 for v in th.values()),
           {"threads": th, "Seccomp_filters": s.get("Seccomp_filters"), "NoNewPrivs": s.get("NoNewPrivs")})
    t.pred("T02.P3", "CapEff, CapPrm are zero", s.get("CapEff") == "0000000000000000" and s.get("CapPrm") == "0000000000000000",
           {k: s.get(k) for k in ("CapEff", "CapPrm", "CapBnd")})
    vid = r.get("vm_id")
    t.pred("T02.P4", "VMM pid is in cgroup.procs of <parent>/<vm_id>",
           s.get("cgroup") == f"0::/{config.PARENT_CGROUP}/{vid}" and str(r.get("pid")) in cg.get("cgroup.procs", "").split(),
           {"proc_cgroup": s.get("cgroup"), "cgroup.procs": cg.get("cgroup.procs")})
    mem_max = (MEM + config.DEFAULTS["mem_overhead_mib"]) << 20
    want = {"cpu.max": f"{CPU_MAX} 100000", "memory.max": str(mem_max), "memory.swap.max": "0", "pids.max": str(PIDS)}
    got = {k: cg.get(k) for k in want}
    t.pred("T02.P5", "cgroup limit files hold the declared values", got == want, {"want": want, "got": got})
    lim = " | ".join(s.get("limits") or [])
    fs_ok = any(ln.split()[3:5] == [str(FSIZE), str(FSIZE)] for ln in s.get("limits") or [] if ln.startswith("Max file size"))
    nf_ok = any(ln.split()[3:5] == [str(NOFILE), str(NOFILE)] for ln in s.get("limits") or [] if ln.startswith("Max open files"))
    t.pred("T02.P6", "/proc/<pid>/limits: Max file size == fsize and Max open files == no-file (soft and hard)",
           fs_ok and nf_ok, lim)
    t.data["exe_and_threads"] = {"exe": s.get("exe"), "Threads": s.get("Threads"), "Name": s.get("Name")}
    t.pred("T02.P7", "sha256 of /proc/<pid>/exe at READY equals the pinned firecracker hash", r.get("vmm_exe_matches_pin") is True,
           r.get("vmm_exe_sha256_at_ready"))
    t.pred("T02.P8", "run completed and cleanup left nothing", r["ok"], {"cleanup": r.get("cleanup")})


if __name__ == "__main__":
    sys.exit(main(t02, "T02", "Unprivileged execution and constraints"))
