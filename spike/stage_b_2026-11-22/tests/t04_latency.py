#!/usr/bin/env python3
"""T04: cold start, execution and teardown latency over N=20 sequential runs."""
import os
import secrets
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import fclib, main, payload, slim, util  # noqa: E402

N = 20


def t04(t):
    t.gate()
    runs = []
    for i in range(N):
        r = fclib.run_vm(payload("w_echo", nonce=secrets.token_hex(8)), label=f"T04-{i}")
        runs.append(slim(r, 512))
        print(f"[T04] run {i} ok={r['ok']} timings={r.get('timings_s')}", flush=True)
    t.data["runs"] = runs
    ts = [r.get("timings_s") or {} for r in runs]
    d = lambda a, b: [x[b] - x[a] if x.get(a) is not None and x.get(b) is not None else None for x in ts]
    stats = {"prep_s (prep_start->spawn, negative)": util.pctl([-x["prep_start"] for x in ts if x.get("prep_start") is not None]),
             "cold_start_s (spawn->PLEA_READY)": util.pctl([x.get("ready") for x in ts]),
             "execution_s (READY->DONE)": util.pctl(d("ready", "done")),
             "vmm_shutdown_s (DONE->VMM exit)": util.pctl(d("done", "exit")),
             "teardown_s (VMM exit->clean)": util.pctl(d("exit", "clean")),
             "total_s (spawn->clean)": util.pctl([x.get("clean") for x in ts])}
    t.data["stats"] = stats
    t.pred("T04.P1", f"all {N} runs ok", all(r["ok"] for r in runs), sum(r["ok"] for r in runs))
    t.pred("T04.P2", f"all {N} runs cleaned (no leftovers)", all(r["clean"] for r in runs), sum(r["clean"] for r in runs))
    tot = stats["total_s (spawn->clean)"]
    t.pred("T04.P3", "p95 of spawn->clean <= 30 s (sanity bound; latencies are measurements, not a target)",
           bool(tot) and tot["p95"] <= 30, tot)


if __name__ == "__main__":
    sys.exit(main(t04, "T04", "Cold-start, execution and teardown latency (N=20)"))
