#!/usr/bin/env python3
"""T03: standard-library Python verification workload in the guest; result hash checked on the host."""
import hashlib
import os
import sys
import tempfile

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import fclib, main, payload, util  # noqa: E402


def t03(t):
    t.gate()
    pl = payload("w_verify")
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "w_verify.py")
        with open(f, "wb") as fh:
            fh.write(pl)
        host = util.run([sys.executable, "-I", "-S", f], timeout=120)
    host_sha = hashlib.sha256(host["stdout"].encode()).hexdigest()
    t.data["host_reference"] = {"rc": host["rc"], "stdout": host["stdout"], "sha256": host_sha,
                                "host_python": sys.version.split()[0]}
    r = fclib.run_vm(pl, label="T03", guest_timeout=60, host_timeout=120)
    t.data["run"] = r
    hdr = r.get("result_parsed") or {}
    t.pred("T03.P1", "run ok, guest exit 0, stdout not truncated", r["ok"] and hdr.get("exit") == 0
           and hdr.get("stdout_truncated") is False, {"exit": hdr.get("exit"), "status": hdr.get("status")})
    t.pred("T03.P2", "sha256(guest stdout) == sha256(host reference stdout)",
           host["rc"] == 0 and r.get("stdout_sha256") == host_sha, {"guest": r.get("stdout_sha256"), "host": host_sha})
    t.pred("T03.P3", "guest echoed payload sha256 == host payload sha256",
           hdr.get("payload_sha256") == hashlib.sha256(pl).hexdigest(), hdr.get("payload_sha256"))
    t.data["guest_python"] = (r.get("stderr") or "").strip()[:200]


if __name__ == "__main__":
    sys.exit(main(t03, "T03", "Standard-library Python verification workload"))
