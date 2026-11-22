#!/usr/bin/env python3
"""T13: simulated missing prerequisites (env overrides): no /dev/kvm path, missing jailer, missing cgroup
controller, insufficient memory threshold, tampered kernel hash. Each must be NOT MET and refuse to start a VM."""
import json
import os
import subprocess
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import clean_state_check, config, main  # noqa: E402
import scenarios  # noqa: E402

HELPER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sim_helper.py")


def helper(env, *args):
    e = {k: v for k, v in os.environ.items() if k not in config.OVERRIDES}
    e.update(env)
    p = subprocess.run([sys.executable, "-I", "-B", HELPER, *args], env=e, capture_output=True, timeout=600)
    try:
        return json.loads(p.stdout[-(4 << 20):] or b"{}")
    except ValueError:
        return {"parse_error": p.stdout[-2000:].decode("utf-8", "replace"), "stderr": p.stderr[-2000:].decode("utf-8", "replace")}


def t13(t):
    t.gate()  # control: with no overrides every prerequisite is MET
    t.pred("T13.P0", "control: without overrides every prerequisite is MET", t.data["prereq"]["all_met"])
    sc = scenarios.make(config.paths())
    try:
        for i, (name, (env, target)) in enumerate(sc.items(), 1):
            chk, lau = helper(env, "check"), helper(env, "launch")
            tc = next((c for c in chk.get("checks", []) if c["id"] == target), {})
            t.data[name] = {"env": env, "target_check": tc, "not_met": chk.get("not_met"), "launch": lau}
            t.pred(f"T13.P{i}", f"{name}: {target} NOT MET, overall NOT MET, launch refused and nothing spawned",
                   tc.get("met") is False and chk.get("all_met") is False and lau.get("spawned") is False and bool(lau.get("refused")),
                   {"target_met": tc.get("met"), "not_met": chk.get("not_met"), "refused": (lau.get("refused") or "")[:300]})
    finally:
        scenarios.remove()
    clean, scan = clean_state_check()
    t.pred("T13.P6", "no chroot, cgroup, lease or process left by the refused launches", clean, scan)


if __name__ == "__main__":
    sys.exit(main(t13, "T13", "Missing prerequisites simulated"))
