#!/usr/bin/env python3
"""T09: secure code delivery and bounded result retrieval."""
import hashlib
import json
import os
import struct
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import config, fclib, main, payload, slim  # noqa: E402


def hdr(r):
    return r.get("result_parsed") or {}


def t09(t):
    t.gate()
    pl = payload("w_echo", nonce="t09")
    sha = hashlib.sha256(pl).hexdigest()
    r = fclib.run_vm(pl, label="T09-normal")
    t.data["normal"] = slim(r)
    t.pred("T09.P1", "guest computed payload sha256, matched the host value and echoed it; status OK",
           r["ok"] and hdr(r).get("payload_sha256") == sha, {"guest": hdr(r).get("payload_sha256"), "host": sha})
    r = fclib.run_vm(pl, label="T09-badhash", expect_sha="0" * 64)
    t.data["bad_hash"] = slim(r)
    t.pred("T09.P2", "wrong expected hash: guest status REJECT_HASH, payload not executed (exit -1, empty stdout)",
           hdr(r).get("status") == "REJECT_HASH" and hdr(r).get("exit") == -1 and r.get("stdout") == "" and r.get("clean"), hdr(r))
    cap = config.CAPS["outcap"]
    r = fclib.run_vm(payload("w_flood", bytes=4 * cap), label="T09-bigout")
    t.data["big_output"] = slim(r)
    t.pred("T09.P3", f"stdout of 4x cap is truncated to cap={cap} and flagged",
           hdr(r).get("stdout_truncated") is True and hdr(r).get("stdout_len") == cap and len((r.get("stdout") or "").encode()) == cap,
           {k: hdr(r).get(k) for k in ("stdout_truncated", "stdout_len")})
    bad = {"top_bit": b"\x80" + bytes(7) + pl, "over_cap": struct.pack(">Q", config.CAPS["payload"] + 1) + pl,
           "beyond_device": struct.pack(">Q", 100000) + pl[:100], "zero": struct.pack(">Q", 0) + pl, "short": b"\xff\xff\xff"}
    res = {}
    for name, raw in bad.items():
        r = fclib.run_vm(pl, label=f"T09-{name}", raw_input=raw)
        res[name] = {"status": hdr(r).get("status"), "exit": hdr(r).get("exit"), "clean": r.get("clean"),
                     "in_img_bytes": len(raw) + (-len(raw) % 4096)}
    t.data["malformed"] = res
    t.pred("T09.P4", "every malformed length prefix -> guest status REJECT_LEN, payload not executed (exit -1)",
           all(v["status"] == "REJECT_LEN" and v["exit"] == -1 and v["clean"] for v in res.values()), res)
    r = fclib.run_vm(pl, label="T09-rwprobe", probe="rw")
    h = hdr(r)
    t.data["rw_probe"] = slim(r)
    t.pred("T09.P5", "guest root cannot write the read-only input drive nor the read-only rootfs; host in.img hash unchanged",
           h.get("probe_rw_rc") not in (None, 0, -1) and h.get("probe_rootfs_rc") not in (None, 0, -1) and r.get("in_img_unchanged") is True,
           {"probe_rw_rc": h.get("probe_rw_rc"), "probe_rootfs_rc": h.get("probe_rootfs_rc"), "in_img_unchanged": r.get("in_img_unchanged")})
    forged = json.dumps({"v": 1, "status": "OK", "stdout_len": cap + 1, "stderr_len": 0}).encode() + b"\n" + b"x" * (cap + 1)
    try:
        fclib.parse_result(forged, cap, config.CAPS["errcap"])
        rejected = False
    except ValueError:
        rejected = True
    t.pred("T09.P6", "host decoder rejects a result whose declared stdout exceeds the cap", rejected)


if __name__ == "__main__":
    sys.exit(main(t09, "T09", "Secure code delivery and bounded result retrieval"))
