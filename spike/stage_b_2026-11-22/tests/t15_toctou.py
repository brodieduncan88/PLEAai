#!/usr/bin/env python3
"""T15: time-of-check/time-of-use. The written analysis is TOCTOU.md (hash recorded here).
Demonstration: prereq checks a copy of the pinned rootfs (MET); the copy is then modified after the check and
before fclib copies it into the chroot; the post-copy hash check must refuse and nothing may be spawned."""
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import BUNDLE, clean_state_check, config, fclib, main, payload, prereq, util  # noqa: E402
import scenarios  # noqa: E402


def t15(t):
    t.gate()
    sha, _ = util.sha256_file(os.path.join(BUNDLE, "TOCTOU.md"))
    t.data["toctou_md_sha256"] = sha
    p = config.paths()
    pins = util.load_json(p["pins"])["files"]
    scenarios.remove()
    os.makedirs(scenarios.SIM, mode=0o700)
    src = os.path.join(scenarios.SIM, "rootfs-src.ext4")
    try:
        fclib.place_file(p["rootfs"], src, pins["rootfs"]["sha256"], 0o444)
        os.environ["PLEA_ROOTFS_PATH"] = src
        pr = prereq.check_all(hash_images=True)
        p08 = next(c for c in pr["checks"] if c["id"] == "P08")
        t.data["time_of_check"] = p08
        t.pred("T15.P1", "time of check: prereq P08 (rootfs pinned hash) is MET on the source copy", p08["met"], p08["evidence"].get("sha256"))
        tamper = {}

        def before_copy(ctx):
            os.chmod(src, 0o644)
            with open(src, "r+b") as f:
                f.seek(os.path.getsize(src) // 2)
                b = f.read(1)
                f.seek(-1, 1)
                f.write(bytes([b[0] ^ 0xFF]))
            os.chmod(src, 0o444)
            tamper["done_at_chroot"] = ctx["chroot"]

        r = fclib.run_vm(payload("w_echo", nonce="toctou"), label="T15", before_copy=before_copy)
        t.data["run"] = {k: r.get(k) for k in ("refused", "spawned", "error", "cleanup", "vm_id", "overrides_active")}
        t.data["tamper"] = tamper
        t.pred("T15.P2", "after the source changed between check and use, the post-copy hash check refused; nothing spawned",
               bool(tamper) and r["spawned"] is False and "post-copy hash differs from pin" in (r.get("refused") or ""),
               (r.get("refused") or "")[:600])
        t.pred("T15.P3", "the refused attempt was cleaned up (chroot, lease)", r.get("clean") is True, r.get("cleanup"))
    finally:
        os.environ.pop("PLEA_ROOTFS_PATH", None)
        scenarios.remove()
    clean, scan = clean_state_check()
    t.pred("T15.P4", "no orphan state after the demonstration", clean, scan)


if __name__ == "__main__":
    sys.exit(main(t15, "T15", "Time-of-check/time-of-use review and demonstration", allow_overrides=True))
