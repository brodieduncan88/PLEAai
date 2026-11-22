#!/usr/bin/env python3
"""T01: start one microVM under the jailer; record jailer --help, argv, uid/gid, chroot, cgroup."""
import json
import os
import secrets
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import config, fclib, main, payload, clean_state_check  # noqa: E402


def t01(t):
    t.gate()
    fl = fclib.flag_check()
    t.data["jailer_help"] = fl["raw"]["jailer_help"]
    t.data["firecracker_help"] = fl["raw"]["fc_help"]
    t.data["versions"] = {"jailer": fl["jailer_version"], "firecracker": fl["firecracker_version"]}
    t.pred("T01.P1", "jailer --help lists every required flag; both binaries report 1.18.0",
           fl["met"], {"missing": fl["missing"], "mode": fl["mode"]})
    nonce = secrets.token_hex(8)
    r = fclib.run_vm(payload("w_echo", nonce=nonce), label="T01")
    t.data["run"] = r
    p, lo_hi = config.paths(), config.uid_range()
    argv = r.get("argv", [])
    a = lambda f: argv[argv.index(f) + 1] if f in argv else None
    t.pred("T01.P2", "argv: --cgroup-version 2, --parent-cgroup, --uid/--gid in range and equal, --chroot-base-dir; no --no-seccomp",
           a("--cgroup-version") == "2" and a("--parent-cgroup") == config.PARENT_CGROUP
           and a("--uid") == a("--gid") and a("--uid") is not None and lo_hi[0] <= int(a("--uid")) <= lo_hi[1]
           and a("--chroot-base-dir") == p["chroot_base"] and "--no-seccomp" not in argv, argv)
    vid = r.get("vm_id")
    exp_root = os.path.join(p["chroot_base"], "firecracker", str(vid), "root")
    cgl = (r.get("vmm_at_ready") or {}).get("cgroup", "")
    t.pred("T01.P3", "VMM cgroup at READY is 0::/plea-spike/<vm_id>; chroot is <base>/firecracker/<vm_id>/root",
           cgl == f"0::/{config.PARENT_CGROUP}/{vid}" and r.get("chroot") == exp_root,
           {"proc_cgroup": cgl, "chroot": r.get("chroot"), "expected_chroot": exp_root})
    out = {}
    try:
        out = json.loads(r.get("stdout") or "{}")
    except ValueError:
        pass
    t.pred("T01.P4", "PLEA_READY/PLEA_DONE seen with one nonce, result parsed, guest status OK, workload echoed the nonce",
           r["ok"] and out.get("nonce") == nonce,
           {"ok": r["ok"], "echo": out, "timings_s": r.get("timings_s"), "result_status": r.get("result_status")})
    clean, scan = clean_state_check()
    t.pred("T01.P5", "cleanup left nothing (no chroot, cgroup, lease or uid-range process)", r["clean"] and clean,
           {"cleanup": r.get("cleanup"), "scan": scan})


if __name__ == "__main__":
    sys.exit(main(t01, "T01", "Start a microVM under the jailer"))
