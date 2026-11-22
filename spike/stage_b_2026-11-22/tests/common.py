"""Shared helpers for the T01-T15 scripts. Each test writes <evidence>/<TID>.json with its predicates
(IDs match DECLARATION.md), the measurements, and a verdict: MET / NOT MET / BLOCKED / ERROR."""
import json
import os
import subprocess
import sys
import threading
import time
import traceback

BUNDLE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BUNDLE)
import config  # noqa: E402
import fclib  # noqa: E402
import prereq  # noqa: E402
import util  # noqa: E402

EVIDENCE_MAX = 8 << 20


def evidence_dir():
    d = os.environ.get("PLEA_EVIDENCE")
    if not d:
        d = os.path.join(BUNDLE, "evidence", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-adhoc")
    os.makedirs(d, exist_ok=True)
    return d


def payload(name, **params):
    with open(os.path.join(BUNDLE, "workloads", name + ".py"), "rb") as f:
        body = f.read()
    return f"PARAMS = {json.dumps(params, sort_keys=True)}\n".encode() + body


def slim(r, keep=2048):
    """Drop bulky fields from a run_vm result for multi-run tests (console head/tail cut to `keep`)."""
    r = dict(r)
    for k in ("console", "vmm_stderr"):
        if isinstance(r.get(k), dict):
            c = dict(r[k])
            c["head"], c["tail"] = c.get("head", "")[:keep], c.get("tail", "")[-keep:]
            r[k] = c
    for k in ("vm_config", "flags", "placed"):
        r.pop(k, None)
    if isinstance(r.get("stdout"), str) and len(r["stdout"]) > keep:
        r["stdout"] = r["stdout"][:keep] + f"...<{len(r['stdout'])} chars>"
    return r


def host_probe():
    """One host responsiveness sample: loadavg, MemAvailable, file-nr, latency of spawning /bin/true."""
    t = time.monotonic()
    try:
        subprocess.run(["/bin/true"], timeout=10, check=False)
        lat = round((time.monotonic() - t) * 1000, 2)
    except subprocess.TimeoutExpired:
        lat = 10000.0
    la = util.read_bounded("/proc/loadavg", 256).split()
    return {"t": round(time.time(), 3), "probe_ms": lat, "load1": float(la[0]),
            "mem_avail_mib": util.meminfo().get("MemAvailable", 0) >> 10,
            "file_nr": [int(x) for x in util.read_bounded("/proc/sys/fs/file-nr", 256).split()]}


class Sampler(threading.Thread):
    """Background host sampler (bounded: at most max_samples kept)."""

    def __init__(self, interval=0.2, extra=None, max_samples=20000):
        super().__init__(daemon=True)
        self.interval, self.extra, self.max = interval, extra, max_samples
        self.samples, self._stop = [], threading.Event()

    def run(self):
        while not self._stop.is_set():
            s = host_probe()
            if self.extra:
                try:
                    s.update(self.extra())
                except Exception as e:
                    s["extra_error"] = str(e)
            if len(self.samples) < self.max:
                self.samples.append(s)
            self._stop.wait(self.interval)

    def stop(self):
        self._stop.set()
        self.join(timeout=15)
        return self.samples


class Test:
    def __init__(self, tid, title, allow_overrides=False):
        self.tid, self.title, self.preds = tid, title, []
        self.data = {"test": tid, "title": title, "utc_start": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                     "host_boot_id": util.read_bounded("/proc/sys/kernel/random/boot_id", 64).strip()}
        self.ev = evidence_dir()
        if not allow_overrides and config.overrides_active():
            self.data["refused"] = f"PLEA_* overrides set: {config.overrides_active()}"
            sys.exit(self.write("ERROR"))

    def gate(self, hash_images=True):
        pr = prereq.check_all(hash_images=hash_images)
        self.data["prereq"] = pr
        if not pr["all_met"]:
            self.data["blocked_reason"] = "prerequisites NOT MET: " + ", ".join(pr["not_met"])
            sys.exit(self.write("BLOCKED"))
        fl = fclib.flag_check()
        self.data["flag_check"] = {k: v for k, v in fl.items() if k != "raw"}
        if not fl["met"]:
            self.data["blocked_reason"] = f"jailer/firecracker flags NOT MET: {fl['missing']}"
            sys.exit(self.write("BLOCKED"))

    def pred(self, pid, text, met, measured=None):
        self.preds.append({"id": pid, "predicate": text, "met": bool(met), "measured": measured})
        print(f"[{self.tid}] {pid} {'MET' if met else 'NOT MET'}: {text}", flush=True)
        return bool(met)

    def write(self, verdict=None):
        if verdict is None:
            verdict = "MET" if self.preds and all(p["met"] for p in self.preds) else "NOT MET"
        self.data.update(predicates=self.preds, verdict=verdict,
                         utc_end=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        blob = json.dumps(self.data, indent=1, default=str)
        if len(blob) > EVIDENCE_MAX:
            self.data = {k: self.data[k] for k in ("test", "title", "predicates", "verdict", "utc_start", "utc_end")}
            self.data["note"] = f"evidence truncated: {len(blob)} bytes > {EVIDENCE_MAX}"
            blob = json.dumps(self.data, indent=1, default=str)
        with open(os.path.join(self.ev, f"{self.tid}.json"), "w") as f:
            f.write(blob)
        print(f"[{self.tid}] verdict {verdict} -> {self.ev}/{self.tid}.json", flush=True)
        return 0 if verdict == "MET" else 1


def main(test_fn, tid, title, **kw):
    t = Test(tid, title, **kw)
    try:
        test_fn(t)
        return t.write()
    except SystemExit:
        raise
    except Exception:
        t.data["exception"] = traceback.format_exc()[-8000:]
        return t.write("ERROR")


def clean_state_check():
    """No chroot dirs, child cgroups or uid-range processes left (recover.py scan, read-only)."""
    import recover
    f = recover.scan(config.paths())
    return recover.orphan_count(f) == 0, f
