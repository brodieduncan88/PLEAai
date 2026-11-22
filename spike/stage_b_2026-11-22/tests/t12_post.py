#!/usr/bin/env python3
"""T12 (post-reboot): re-check prerequisites (before and after stage-2 setup), run recover.py, run one microVM."""
import glob
import json
import os
import secrets
import subprocess
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import BUNDLE, clean_state_check, fclib, main, payload, prereq, slim, util  # noqa: E402


def t12post(t):
    pres = sorted(glob.glob(os.path.join(BUNDLE, "evidence", "*", "T12_pre.json")), key=os.path.getmtime)
    if not pres:
        t.data["blocked_reason"] = "no T12_pre.json found: run T12pre before rebooting"
        sys.exit(t.write("BLOCKED"))
    pre = util.load_json(pres[-1], 16 << 20)
    fp = pre.get("data", pre).get("for_post") or pre.get("for_post") or {}
    t.data["pre_evidence"] = {"path": pres[-1], "for_post": fp, "pre_verdict": pre.get("verdict")}
    t.pred("T12post.P1", "host boot_id differs from the pre-reboot boot_id (a reboot happened)",
           fp.get("boot_id") and fp["boot_id"] != t.data["host_boot_id"], {"pre": fp.get("boot_id"), "now": t.data["host_boot_id"]})
    pr0 = prereq.check_all(hash_images=True)
    r0 = fclib.run_vm(payload("w_echo", nonce="pre-setup"), label="T12-post-before-setup")
    t.data.update(prereq_before_setup=pr0, launch_before_setup=slim(r0, 512))
    t.pred("T12post.P2", "before setup: a launch is refused exactly when prerequisites are NOT MET (fail closed after reboot)",
           (not pr0["all_met"] and not r0["spawned"] and bool(r0["refused"])) or (pr0["all_met"] and r0["spawned"]),
           {"not_met": pr0["not_met"], "spawned": r0["spawned"], "refused": r0["refused"]})
    s = subprocess.run([sys.executable, "-I", "-B", os.path.join(BUNDLE, "setup_host.py")], capture_output=True, timeout=600)
    pr1 = prereq.check_all(hash_images=True)
    t.data.update(setup_rc=s.returncode, setup_stdout=s.stdout[-4000:].decode("utf-8", "replace"), prereq_after_setup=pr1)
    t.pred("T12post.P3", "after re-running stage-2 setup every prerequisite is MET", pr1["all_met"], pr1["not_met"])
    rec = [sys.executable, "-I", "-B", os.path.join(BUNDLE, "recover.py")]
    dry = json.loads(subprocess.run(rec, capture_output=True, timeout=120).stdout[:4 << 20] or b"{}")
    paths = [c["path"] for c in dry.get("found", {}).get("chroot_dirs", [])]
    cgs = [c["path"] for c in dry.get("found", {}).get("cgroups", [])]
    vid, extra = fp.get("vm_id") or "?", fp.get("extra_orphan") or "?"
    t.data["recover_dry_run"] = dry
    t.pred("T12post.P4", "recover.py dry-run finds both pre-reboot chroot dirs; their cgroup did not survive the reboot",
           any(x.endswith(vid) for x in paths) and any(x.endswith(extra) for x in paths) and not any(x.endswith(vid) for x in cgs),
           {"chroot_dirs": paths, "cgroups": cgs})
    app = json.loads(subprocess.run(rec + ["--apply"], capture_output=True, timeout=180).stdout[:4 << 20] or b"{}")
    clean, scan = clean_state_check()
    t.data.update(recover_apply=app, scan_after=scan)
    t.pred("T12post.P5", "recover.py --apply leaves nothing", app.get("remaining_count") == 0 and clean, app.get("errors"))
    n = secrets.token_hex(8)
    r = fclib.run_vm(payload("w_echo", nonce=n), label="T12-post-run")
    t.data["run"] = slim(r)
    try:
        echoed = json.loads(r.get("stdout") or "{}").get("nonce") == n
    except ValueError:
        echoed = False
    t.pred("T12post.P6", "one microVM runs ok after the reboot", r["ok"] and echoed, r.get("timings_s"))


if __name__ == "__main__":
    sys.exit(main(t12post, "T12_post", "Reboot persistence: post-reboot recovery"))
