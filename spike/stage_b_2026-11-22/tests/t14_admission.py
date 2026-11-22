#!/usr/bin/env python3
"""T14: admission model. Each T13 condition -> HTTP 503 ISOLATION_UNAVAILABLE with the budget counter unchanged;
all prerequisites MET -> admitted, budget debited exactly once; budget 0 -> 429, unchanged."""
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import config, main  # noqa: E402
import scenarios  # noqa: E402
from t13_missing_prereq import helper  # noqa: E402


def snap(path):
    st = os.stat(path)
    with open(path, "rb") as f:
        return {"bytes": f.read(64).decode(), "mtime_ns": st.st_mtime_ns, "ino": st.st_ino, "size": st.st_size}


def t14(t):
    t.gate()
    sc = scenarios.make(config.paths())
    budget = os.path.join(scenarios.SIM, "budget")
    try:
        with open(budget, "w") as f:
            f.write("100\n")
        for i, (name, (env, _)) in enumerate(sc.items(), 1):
            b0 = snap(budget)
            out = helper(env, "admit", budget)
            b1 = snap(budget)
            t.data[name] = {"response": out, "budget_before": b0, "budget_after": b1}
            t.pred(f"T14.P{i}", f"{name}: HTTP 503 ISOLATION_UNAVAILABLE and budget file byte-identical with same mtime",
                   out.get("http_status") == 503 and (out.get("body") or {}).get("error") == "ISOLATION_UNAVAILABLE" and b0 == b1,
                   {"status": out.get("http_status"), "before": b0["bytes"], "after": b1["bytes"]})
        b0 = snap(budget)
        out = helper({}, "admit", budget)
        b1 = snap(budget)
        t.data["all_met"] = {"response": out, "budget_before": b0, "budget_after": b1}
        t.pred("T14.P6", "all prerequisites MET: HTTP 200 admitted and budget 100 -> 99 (debited exactly once)",
               out.get("http_status") == 200 and b0["bytes"].strip() == "100" and b1["bytes"].strip() == "99", out)
        with open(budget, "w") as f:
            f.write("0\n")
        b0 = snap(budget)
        out = helper({}, "admit", budget)
        b1 = snap(budget)
        t.data["exhausted"] = {"response": out, "budget_before": b0, "budget_after": b1}
        t.pred("T14.P7", "budget 0: HTTP 429 BUDGET_EXHAUSTED and budget file unchanged", out.get("http_status") == 429 and b0 == b1, out)
    finally:
        scenarios.remove()


if __name__ == "__main__":
    sys.exit(main(t14, "T14", "Admission: 503 ISOLATION_UNAVAILABLE without touching the budget"))
