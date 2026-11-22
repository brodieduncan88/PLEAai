#!/usr/bin/env python3
"""T07 (D37): bounded high-descriptor workload in the guest (up to 1,000,000 opens of /dev/null after
raising the guest's limits). Host /proc/sys/fs/file-nr (all three fields), fs.file-max and the fd counts of
the VMM process are sampled every 200 ms before, during and after. Predicate: host file-table usage does not
rise in proportion to guest descriptors (ratio stated). Host usage is NOT claimed to be unchanged."""
import json
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import Sampler, fclib, main, payload, slim, util  # noqa: E402

TARGET, RATIO_MAX = 1000000, 0.01
CTX = {}


def extra():
    out = {"file_max": int(util.read_bounded("/proc/sys/fs/file-max", 64))}
    pid = CTX.get("pid")
    if pid:
        try:
            out["vmm_fds"] = len(os.listdir(f"/proc/{pid}/fd"))
        except OSError:
            out["vmm_fds"] = None
    return out


def t07(t):
    t.gate()
    pre = Sampler(0.2, extra)
    pre.start()
    time.sleep(2)
    before = pre.stop()
    smp = Sampler(0.2, extra)
    marks = {}
    smp.start()
    r = fclib.run_vm(payload("w_fd", target=TARGET, hold=3, seconds=150), label="T07", mem_mib=1024,
                     guest_nofile=1048576, guest_filemax=1100000, guest_timeout=180, host_timeout=260,
                     on_spawn=lambda ctx: CTX.update(pid=ctx["pid"]),
                     on_ready=lambda ctx: marks.update(ready=time.time()),
                     after_exit=lambda ctx: (marks.update(exit=time.time()), CTX.pop("pid", None)))
    during = smp.stop()
    post = Sampler(0.2, extra)
    post.start()
    time.sleep(2)
    after = post.stop()
    out = {}
    try:
        out = json.loads((r.get("stdout") or "").strip().splitlines()[-1])
    except (ValueError, IndexError):
        pass
    opened = out.get("opened", 0)
    base = util.pctl([s["file_nr"][0] for s in before])
    ready_pts = [s for s in during if marks.get("ready") and marks["ready"] <= s["t"] <= marks["ready"] + 0.6]
    at_ready = ready_pts[0]["file_nr"][0] if ready_pts else None
    peak = max([s["file_nr"][0] for s in during] or [0])
    vfds = [s.get("vmm_fds") for s in during if s.get("vmm_fds") is not None]
    vmm_at_ready = (r.get("vmm_at_ready") or {}).get("fd_count")
    delta_ready = peak - at_ready if at_ready is not None else None
    ratio = delta_ready / opened if opened and delta_ready is not None else None
    fmax = {s["file_max"] for s in before + during + after}
    t.data.update(run=slim(r), guest=out, samples_before=before, samples_during=during[::2][:1500], samples_after=after,
                  summary={"guest_descriptors_opened": opened, "host_file_nr0_baseline_median": base and base["median"],
                           "host_file_nr0_at_ready": at_ready, "host_file_nr0_peak": peak,
                           "peak_delta_vs_ready": delta_ready,
                           "peak_delta_vs_baseline": (peak - base["median"]) if base else None,
                           "ratio_host_delta_per_guest_fd": ratio, "file_max_values": sorted(fmax),
                           "vmm_fds_at_ready": vmm_at_ready, "vmm_fds_max": max(vfds or [0]),
                           "jailer_pid_note": "without --daemonize/--new-pid-ns the jailer execs firecracker in place: "
                                              "jailer pid == VMM pid, so one fd count covers both",
                           "host_file_nr0_after_median": util.pctl([s["file_nr"][0] for s in after])})
    t.pred("T07.P1", "guest opened >= 900,000 descriptors (otherwise the measurement is not meaningful)", opened >= 900000, out)
    t.pred("T07.P2", f"(host file-nr[0] peak - value at READY) / guest descriptors < {RATIO_MAX}",
           ratio is not None and ratio < RATIO_MAX, {"ratio": ratio, "delta": delta_ready, "opened": opened})
    t.pred("T07.P3", "VMM fd count max during the run - fd count at READY <= 2",
           vmm_at_ready is not None and bool(vfds) and max(vfds) - vmm_at_ready <= 2,
           {"at_ready": vmm_at_ready, "max": max(vfds or [0])})
    t.pred("T07.P4", "host fs.file-max unchanged across the test", len(fmax) == 1, sorted(fmax))
    t.pred("T07.P5", "run completed (PLEA_DONE, result parsed) and cleanup left nothing", r["ok"], {"cleanup": r.get("cleanup")})


if __name__ == "__main__":
    sys.exit(main(t07, "T07", "D37 bounded high-file-descriptor workload"))
