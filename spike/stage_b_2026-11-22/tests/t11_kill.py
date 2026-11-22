#!/usr/bin/env python3
"""T11: SIGKILL of the VMM during execution, SIGKILL of the jailer at spawn, and an orchestrator-crash case
(cleanup skipped + a stray uid-range process) cleaned by recover.py. After each: process gone, cgroup.procs empty,
cgroup and chroot removed, no mounts or fds left, and a new microVM runs."""
import json
import os
import secrets
import subprocess
import sys
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import BUNDLE, clean_state_check, config, fclib, main, payload, slim  # noqa: E402


def fds_referencing(vm_id):
    hits = []
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            for fd in os.listdir(f"/proc/{d}/fd"):
                try:
                    if vm_id in os.readlink(f"/proc/{d}/fd/{fd}"):
                        hits.append([int(d), fd])
                except OSError:
                    pass
        except OSError:
            pass
    return hits[:50]


def post_checks(r, ex):
    vid = r.get("vm_id") or "none"
    p = config.paths()
    return {"process_gone": not os.path.exists(f"/proc/{r.get('pid')}") if r.get("pid") else None,
            "cgroup_procs_after_exit": ex.get("procs"),
            "cgroup_exists": os.path.exists(os.path.join(p["cg_parent"], vid)),
            "chroot_exists": os.path.exists(os.path.join(p["chroot_base"], "firecracker", vid)),
            "mounts": fclib.mounts_under(p["chroot_base"]), "fds_referencing": fds_referencing(vid)}


def after_exit_rec(ex):
    def f(ctx):
        cg = ctx.get("cgroup")
        try:
            ex["procs"] = open(os.path.join(cg, "cgroup.procs")).read().split() if cg and os.path.isdir(cg) else "no-cgroup"
        except OSError as e:
            ex["procs"] = str(e)
    return f


def fresh_vm(t, tag):
    n = secrets.token_hex(8)
    r = fclib.run_vm(payload("w_echo", nonce=n), label=f"T11-{tag}-after")
    try:
        ok = r["ok"] and json.loads(r.get("stdout") or "{}").get("nonce") == n
    except ValueError:
        ok = False
    return ok, slim(r, 512)


def preds(t, case, r, pc, new_ok, cgroup_note):
    t.pred(f"T11.{case}.P1", "killed process (group) is gone", pc["process_gone"] is True, pc["process_gone"])
    t.pred(f"T11.{case}.P2", "cgroup.procs empty after the VMM exit (or no cgroup created yet)",
           pc["cgroup_procs_after_exit"] in ([], "no-cgroup"), pc["cgroup_procs_after_exit"])
    t.pred(f"T11.{case}.P3", f"cgroup removed ({cgroup_note})", not pc["cgroup_exists"])
    t.pred(f"T11.{case}.P4", "chroot removed", not pc["chroot_exists"])
    t.pred(f"T11.{case}.P5", "no mounts under the chroot base and no host fds referencing the VM", not pc["mounts"] and not pc["fds_referencing"],
           {"mounts": pc["mounts"], "fds": pc["fds_referencing"]})
    t.pred(f"T11.{case}.P6", "a new microVM then runs ok", new_ok)


def t11(t):
    t.gate()
    # A: SIGKILL the VMM 2 s after PLEA_READY while the guest is executing
    ex = {}
    r = fclib.run_vm(payload("w_sleep", seconds=30), label="T11-A", kill_after_ready=2.0, guest_timeout=60,
                     host_timeout=90, after_exit=after_exit_rec(ex))
    pc = post_checks(r, ex)
    ok, nr = fresh_vm(t, "A")
    t.data["A_vmm_kill"] = {"run": slim(r), "post": pc, "new_vm": nr}
    preds(t, "A", r, pc, ok, "by fclib cleanup")
    # B: SIGKILL the jailer immediately after spawn (before or while it execs firecracker)
    ex = {}
    r = fclib.run_vm(payload("w_sleep", seconds=30), label="T11-B", kill_at_spawn=True, host_timeout=60,
                     after_exit=after_exit_rec(ex))
    pc = post_checks(r, ex)
    ok, nr = fresh_vm(t, "B")
    t.data["B_jailer_kill"] = {"run": slim(r), "post": pc, "new_vm": nr,
                               "exe_at_kill": (r.get("killed_at_spawn") or {}).get("exe")}
    preds(t, "B", r, pc, ok, "by fclib cleanup")
    # C: orchestrator crash: kill the VMM, skip cleanup, leave a stray process with the VM's uid; recover.py cleans
    ex = {}
    r = fclib.run_vm(payload("w_sleep", seconds=30), label="T11-C", kill_after_ready=2.0, guest_timeout=60,
                     host_timeout=90, skip_cleanup=True, after_exit=after_exit_rec(ex))
    uid = r.get("uid")
    if uid:
        subprocess.run(["/bin/sh", "-c", "sleep 120 >/dev/null 2>&1 &"], user=uid, group=uid, extra_groups=[], timeout=10)
    time.sleep(0.5)
    rec = [sys.executable, "-I", "-B", os.path.join(BUNDLE, "recover.py")]
    dry = subprocess.run(rec, capture_output=True, timeout=120)
    app = subprocess.run(rec + ["--apply"], capture_output=True, timeout=180)
    pc = post_checks(r, ex)
    clean, scan = clean_state_check()
    ok, nr = fresh_vm(t, "C")
    try:
        dj, aj = json.loads(dry.stdout[:4 << 20]), json.loads(app.stdout[:4 << 20])
    except ValueError:
        dj, aj = {"raw": dry.stdout[:2000].decode("utf-8", "replace")}, {"raw": app.stdout[:2000].decode("utf-8", "replace")}
    t.data["C_recover"] = {"run": slim(r), "recover_dry_run": dj, "recover_apply": aj, "post": pc, "scan_after": scan, "new_vm": nr}
    t.pred("T11.C.P0", "recover.py dry-run found the orphan chroot, cgroup, lease and stray process and changed nothing",
           dj.get("found_count", 0) >= 4 and dj.get("actions") == [], {"found_count": dj.get("found_count")})
    preds(t, "C", r, pc, ok and clean and aj.get("remaining_count") == 0, "by recover.py --apply")


if __name__ == "__main__":
    sys.exit(main(t11, "T11", "SIGKILL of the VMM and of the jailer during execution"))
