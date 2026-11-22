#!/usr/bin/env python3
"""Stage 2 host setup (idempotent). CHANGES THE HOST:
  - creates /srv/plea-jailer (root 0755) and /run/plea-fc/leases (root 0700)
  - enables +cpu +memory +pids in /sys/fs/cgroup/cgroup.subtree_control if missing
  - creates the parent cgroup /sys/fs/cgroup/plea-spike and enables the same controllers for its children
  - runs `swapoff -a` if any swap is active (not persisted; /etc/fstab is not edited)
Then runs the full prerequisite check (hashing images) and the jailer/firecracker flag check.
Writes <evidence>/stage2_setup.json; exit 0 only if every prerequisite and flag check is MET.
Cgroups and /run do not survive a reboot: rerun this stage after any reboot or stop/start.
"""
import json
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402
import fclib  # noqa: E402
import prereq  # noqa: E402
import util  # noqa: E402


def main():
    if config.overrides_active():
        print("refusing: PLEA_* overrides set", config.overrides_active())
        return 2
    p, acts = config.paths(), []
    for d, mode in ((p["chroot_base"], 0o755), (p["run"], 0o700), (os.path.join(p["run"], "leases"), 0o700)):
        if not os.path.isdir(d):
            os.makedirs(d, mode=mode)
            acts.append(f"mkdir {d} {oct(mode)}")
        os.chown(d, 0, 0)
        os.chmod(d, mode)
    sub = os.path.join(p["cg_root"], "cgroup.subtree_control")
    have = util.read_bounded(sub, 4096).split()
    for c in config.CONTROLLERS:
        if c not in have:
            with open(sub, "w") as f:
                f.write(f"+{c}")
            acts.append(f"enable +{c} in {sub}")
    if not os.path.isdir(p["cg_parent"]):
        os.mkdir(p["cg_parent"])
        acts.append(f"mkdir {p['cg_parent']}")
    psub = os.path.join(p["cg_parent"], "cgroup.subtree_control")
    have = util.read_bounded(psub, 4096).split()
    for c in config.CONTROLLERS:
        if c not in have:
            with open(psub, "w") as f:
                f.write(f"+{c}")
            acts.append(f"enable +{c} in {psub}")
    swaps = util.read_bounded(p["swaps"], 65536).strip().splitlines()
    if len(swaps) > 1:
        r = util.run(["swapoff", "-a"], timeout=300)
        acts.append(f"swapoff -a rc={r['rc']} {r['stderr'][:200]}")
    pr = prereq.check_all(hash_images=True)
    fl = fclib.flag_check()
    out = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "actions": acts, "prereq": pr,
           "flags": fl, "met": pr["all_met"] and fl["met"]}
    ev = os.environ.get("PLEA_EVIDENCE", ".")
    with open(os.path.join(ev, "stage2_setup.json"), "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps({"met": out["met"], "actions": acts, "not_met": pr["not_met"],
                      "flags_missing": fl["missing"], "version_ok": fl["version_ok"]}, indent=1))
    return 0 if out["met"] else 1


if __name__ == "__main__":
    sys.exit(main())
