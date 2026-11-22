#!/usr/bin/env python3
"""Run one prereq check / launch attempt / admission under the PLEA_* overrides set by T13/T14.
Usage: sim_helper.py check | launch | admit <budget_file>"""
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import fclib, payload, prereq  # noqa: E402
import admission  # noqa: E402

mode = sys.argv[1]
if mode == "check":
    out = prereq.check_all(hash_images=True)
elif mode == "launch":
    r = fclib.run_vm(payload("w_echo", nonce="sim"), label="sim-launch")
    out = {k: r.get(k) for k in ("refused", "spawned", "error", "ok", "vm_id", "cleanup", "overrides_active")}
elif mode == "admit":
    code, body = admission.admit(sys.argv[2], hash_images=True)
    out = {"http_status": code, "body": body}
else:
    sys.exit(2)
print(json.dumps(out))
