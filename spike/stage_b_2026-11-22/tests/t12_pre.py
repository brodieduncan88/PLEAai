#!/usr/bin/env python3
"""T12 (pre-reboot): leave deliberate orphan state and record prerequisites. Then the owner runs `sudo reboot`
and, after reconnecting, `sudo ./run_stage.sh T12post`."""
import os
import secrets
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import config, fclib, main, payload, slim  # noqa: E402
import recover  # noqa: E402


def t12pre(t):
    t.gate()
    p = config.paths()
    r = fclib.run_vm(payload("w_sleep", seconds=30), label="T12-pre-orphan", kill_after_ready=2.0, guest_timeout=60,
                     host_timeout=90, skip_cleanup=True)
    extra = "plea-orphan-" + secrets.token_hex(4)
    d = os.path.join(p["chroot_base"], "firecracker", extra, "root")
    os.makedirs(d, mode=0o755)
    with open(os.path.join(d, "marker"), "w") as f:
        f.write("deliberate orphan for T12\n")
    vid = r.get("vm_id")
    scan = recover.scan(p)
    paths = [c["path"] for c in scan["chroot_dirs"]]
    t.data.update(run=slim(r), scan=scan, for_post={"vm_id": vid, "uid": r.get("uid"), "extra_orphan": extra,
                                                   "boot_id": t.data["host_boot_id"]})
    t.pred("T12pre.P1", "orphan VM state present: chroot dir, cgroup dir, uid lease",
           bool(vid) and any(x.endswith(vid) for x in paths) and any(c["path"].endswith(vid) for c in scan["cgroups"])
           and str(r.get("uid")) in scan["leases"], {"vm_id": vid, "uid": r.get("uid")})
    t.pred("T12pre.P2", "extra orphan chroot dir present", any(x.endswith(extra) for x in paths), extra)


if __name__ == "__main__":
    sys.exit(main(t12pre, "T12_pre", "Reboot persistence: pre-reboot orphan state"))
