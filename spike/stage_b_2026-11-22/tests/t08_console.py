#!/usr/bin/env python3
"""T08: bounded console output and log retention; fsize enforced for files the VMM writes.
Caps: guest prints 8 MiB to the serial console; the host keeps 64 KiB head + 64 KiB tail.
fsize case: RLIMIT_FSIZE 16 MiB on the VMM, sparse 32 MiB output image, guest (root) fills the drive."""
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import config, fclib, main, payload, util  # noqa: E402

HEAD = TAIL = 64 << 10
FLOOD = 8 << 20
FSIZE, OUT = 16 << 20, 32 << 20


def du(path):
    tot = 0
    for dp, dn, fn in os.walk(path):
        for n in fn:
            tot += os.lstat(os.path.join(dp, n)).st_blocks * 512
    return tot


def t08(t):
    t.gate()
    m = {}
    r = fclib.run_vm(payload("w_flood", bytes=FLOOD), label="T08-console", mode="console", console_head=HEAD,
                     console_tail=TAIL, guest_timeout=150, host_timeout=240,
                     before_cleanup=lambda ctx: m.update(du=du(ctx["chroot"])))
    c = r.get("console") or {}
    fc_size = util.load_json(config.paths()["pins"])["files"]["firecracker"]["size"]  # the jailer's copy
    placed = sum(p["size"] for p in r.get("placed", [])) + r.get("out_size", 0) + 3 * 4096
    bound = placed + fc_size + (1 << 20)
    t.data["console_run"] = r
    t.data["chroot_du_bytes"], t.data["du_bound"] = m.get("du"), bound
    t.pred("T08.P1", f"host kept <= {HEAD} head + {TAIL} tail bytes of console", c.get("kept_head", 1 << 30) <= HEAD
           and c.get("kept_tail", 1 << 30) <= TAIL, {k: c.get(k) for k in ("kept_head", "kept_tail", "total_bytes")})
    t.pred("T08.P2", "dropped == total - kept and total >= 1 MiB (flood reached the host)",
           c.get("dropped_bytes") == c.get("total_bytes", 0) - c.get("kept_head", 0) - c.get("kept_tail", 0)
           and c.get("total_bytes", 0) >= (1 << 20), {"total": c.get("total_bytes"), "dropped": c.get("dropped_bytes")})
    t.pred("T08.P3", "run directory (chroot) disk usage <= placed files + output image + firecracker copy + 1 MiB",
           m.get("du") is not None and m["du"] <= bound,
           {"du": m.get("du"), "bound": bound})
    t.pred("T08.P4", "PLEA_DONE still detected after the flood; cleanup clean", r.get("done") and r.get("clean"),
           {"done": r.get("done"), "ignored_markers": c.get("ignored_markers"), "ok": r["ok"]})
    t.pred("T08.P5", "serialised result for this run <= 1 MiB (nothing unbounded retained)",
           len(json.dumps(r, default=str)) <= (1 << 20), len(json.dumps(r, default=str)))
    # fsize
    f = {}

    def inspect(ctx):
        path = os.path.join(ctx["chroot"], "out.img")
        st = os.lstat(path)
        nz = None
        with open(path, "rb") as fh:
            fh.seek(FSIZE)
            off = FSIZE
            while True:
                b = fh.read(1 << 20)
                if not b:
                    break
                if b.strip(b"\x00"):
                    nz = off + (len(b) - len(b.lstrip(b"\x00")))
                    break
                off += len(b)
        f.update(size=st.st_size, allocated=st.st_blocks * 512, first_nonzero_at_or_after_fsize=nz)

    r2 = fclib.run_vm(payload("w_echo", nonce="fsize"), label="T08-fsize", probe="fill", fsize=FSIZE, out_size=OUT,
                      guest_timeout=60, host_timeout=120, after_exit=inspect)
    t.data["fsize_run"] = r2
    t.data["fsize_out_img"] = f
    t.pred("T08.P6", "no byte at or beyond offset fsize in the VMM-written output image is non-zero; allocated <= fsize + 1 MiB",
           f.get("first_nonzero_at_or_after_fsize", 0) is None and f.get("allocated", 1 << 40) <= FSIZE + (1 << 20), f)
    t.pred("T08.P7", "VMM outcome recorded and cleanup clean after the fsize event", r2.get("clean"),
           {"vmm_exit_code": r2.get("vmm_exit_code"), "done": r2.get("done"),
            "probe_rc": (r2.get("result_parsed") or {}).get("probe_rw_rc"), "stderr_tail": (r2.get("vmm_stderr") or {}).get("tail", "")[-800:]})


if __name__ == "__main__":
    sys.exit(main(t08, "T08", "Bounded console output, log retention and fsize"))
