#!/usr/bin/env python3
"""Find and remove orphaned spike VMs: cgroups spike-*, per-VM dirs, leftover API sockets, fcspike* tap devices.
Dry run by default; --apply to remove. Needs no KVM (cleanup must work even when prerequisites fail).
Never touches anything not named with the spike- / fcspike prefixes."""
import argparse, os, shutil, subprocess, sys, time
from pathlib import Path

PFX = "spike-"; TAP = "fcspike"
p = argparse.ArgumentParser(); p.add_argument("--workdir", default=os.environ.get("PLEA_SPIKE_WORKDIR", "/run/plea-spike"))
p.add_argument("--cgroup-parent", default=None); p.add_argument("--apply", action="store_true"); a = p.parse_args()
found = 0
def act(msg, fn):
    global found; found += 1
    print(("REMOVE " if a.apply else "WOULD REMOVE ") + msg)
    if a.apply:
        try: fn()
        except Exception as e: print("  FAILED: %s: %s" % (type(e).__name__, e)); return False  # noqa: E701
    return True
if a.cgroup_parent and Path(a.cgroup_parent).is_dir():
    for cg in sorted(Path(a.cgroup_parent).glob(PFX + "*")):
        def rm(cg=cg):
            try: (cg / "cgroup.kill").write_text("1")
            except OSError: pass
            t = time.monotonic()
            while "populated 1" in (cg / "cgroup.events").read_text() and time.monotonic() - t < 5: time.sleep(0.01)
            cg.rmdir()
        act("cgroup %s (procs: %s)" % (cg, (cg / "cgroup.procs").read_text().split()), rm)
elif a.cgroup_parent:
    print("note: cgroup parent %s not present; skipping cgroup scan" % a.cgroup_parent)
w = Path(a.workdir)
if w.is_dir():
    for d in sorted(w.glob(PFX + "*")):
        pidf = d / "pid"; alive = False
        try:
            pid = int(pidf.read_text()); alive = Path("/proc/%d/cmdline" % pid).exists() and "firecracker" in Path("/proc/%d/cmdline" % pid).read_text()
        except Exception: pass  # noqa: E701
        if alive:
            print("SKIP live VMM in %s (kill it or use cgroup scan)" % d); continue
        act("vm dir %s (%s)" % (d, ",".join(sorted(os.listdir(d)))), lambda d=d: shutil.rmtree(d))
net = Path("/sys/class/net")
if net.is_dir():
    for n in sorted(os.listdir(net)):
        if n.startswith(TAP):
            act("tap %s" % n, lambda n=n: subprocess.run(["ip", "link", "del", n], check=True))
print("found %d orphan item(s); apply=%s" % (found, a.apply)); sys.exit(0)
