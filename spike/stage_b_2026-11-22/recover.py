#!/usr/bin/env python3
"""Find and clean orphaned microVM state. Dry-run by default; --apply to clean.

Looks for: processes in the spike uid range, firecracker/jailer processes, child cgroups under
the parent cgroup, jailer chroot dirs, mounts under the chroot base, uid leases.
--apply refuses while any fclib launch holds the run lock (a VM is legitimately running).
Prints a JSON report; exit 0 if nothing is (or remains) orphaned, 1 otherwise.
"""
import errno
import fcntl
import json
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402
import fclib  # noqa: E402
import util  # noqa: E402


def rmdir_cgroup(path):  # replaced in selftest (fake cgroup dirs contain regular files)
    os.rmdir(path)


def scan(p):
    lo, hi = config.uid_range()
    f = {"uid_range": [lo, hi], "procs_in_uid_range": [list(x) for x in fclib.procs_with_uids(lo, hi)]}
    named = []
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                comm = util.read_bounded(f"/proc/{d}/comm", 64).strip()
            except OSError:
                continue
            if comm in ("firecracker", "jailer") or comm.startswith("fc_"):
                named.append([int(d), comm])
    f["firecracker_or_jailer_procs"] = named
    cgs = []
    if os.path.isdir(p["cg_parent"]):
        for name in sorted(os.listdir(p["cg_parent"])):
            path = os.path.join(p["cg_parent"], name)
            if os.path.isdir(path) and not os.path.islink(path):
                try:
                    procs = util.read_bounded(os.path.join(path, "cgroup.procs"), 65536).split()
                except OSError:
                    procs = ["<unreadable>"]
                cgs.append({"path": path, "procs": procs[:50]})
    f["cgroups"] = cgs
    chroots = []
    if os.path.isdir(p["chroot_base"]):
        for exe in sorted(os.listdir(p["chroot_base"])):
            ed = os.path.join(p["chroot_base"], exe)
            if os.path.islink(ed):
                chroots.append({"path": ed, "symlink": True})
                continue
            if os.path.isdir(ed):
                for vid in sorted(os.listdir(ed)):
                    path = os.path.join(ed, vid)
                    chroots.append({"path": path, "symlink": os.path.islink(path)})
    f["chroot_dirs"] = chroots
    f["mounts_under_chroot_base"] = fclib.mounts_under(p["chroot_base"]) if os.path.isdir(p["chroot_base"]) else []
    ld = os.path.join(p["run"], "leases")
    f["leases"] = sorted(os.listdir(ld)) if os.path.isdir(ld) else []
    return f


def orphan_count(f):
    return sum(len(f[k]) for k in ("procs_in_uid_range", "firecracker_or_jailer_procs", "cgroups",
                                   "chroot_dirs", "mounts_under_chroot_base", "leases"))


def apply(p):
    """Take the run lock FIRST, then rescan, then act on that scan (no stale check-then-use)."""
    done, errs = [], []
    os.makedirs(p["run"], mode=0o700, exist_ok=True)
    lockf = open(os.path.join(p["run"], "run.lock"), "a")
    try:
        fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lockf.close()
        return None, done, ["a launch holds the run lock (VM running); refusing --apply"]
    try:
        f = scan(p)
        # Only processes in the spike uid range are killed. firecracker/jailer processes outside the
        # range (e.g. a root jailer stuck before exec) are reported and left for the owner to inspect.
        pids = {x[0] for x in f["procs_in_uid_range"]}
        for x in f["firecracker_or_jailer_procs"]:
            if x[0] not in pids:
                errs.append(f"pid {x[0]} ({x[1]}) is outside the uid range: reported, not killed")
        lo, hi = config.uid_range()
        for pid in sorted(pids):
            done.append(f"pid {pid}: {fclib.kill_if_uid_in(pid, lo, hi)}")
        for _ in range(50):
            if not any(os.path.exists(f"/proc/{x}") for x in pids):
                break
            time.sleep(0.1)
        for m in sorted(f["mounts_under_chroot_base"], key=len, reverse=True):
            r = util.run(["umount", "--lazy", m], timeout=20)
            (done if r["rc"] == 0 else errs).append(f"umount -l {m}: rc={r['rc']} {r['stderr'][:200]}")
        for cg in f["cgroups"]:
            path = cg["path"]
            if not os.path.realpath(path).startswith(os.path.realpath(p["cg_parent"]) + "/"):
                errs.append(f"{path}: outside parent, skipped")
                continue
            for _ in range(50):
                try:
                    if not util.read_bounded(os.path.join(path, "cgroup.procs"), 65536).split():
                        break
                except OSError:
                    break
                time.sleep(0.1)
            try:
                rmdir_cgroup(path)
                done.append(f"rmdir cgroup {path}")
            except OSError as e:
                errs.append(f"rmdir cgroup {path}: {errno.errorcode.get(e.errno, e.errno)}")
        for c in f["chroot_dirs"]:
            try:
                if c["symlink"]:
                    os.unlink(c["path"])  # remove the link itself, never its target
                    done.append(f"unlink symlink {c['path']}")
                elif fclib.mounts_under(c["path"]):
                    errs.append(f"{c['path']}: mounts remain, not removed")
                else:
                    fclib.safe_rmtree(c["path"], p["chroot_base"])
                    done.append(f"rmtree {c['path']}")
            except (OSError, fclib.Refused) as e:
                errs.append(f"{c['path']}: {e}")
        lo, hi = config.uid_range()
        for lease in f["leases"]:
            path = os.path.join(p["run"], "leases", lease)
            if lease.isdigit() and not fclib.procs_with_uids(int(lease), int(lease)):
                os.unlink(path)
                done.append(f"release lease {lease}")
            else:
                errs.append(f"lease {lease}: process alive or bad name, kept")
    finally:
        lockf.close()
    return f, done, errs


def main(argv):
    p = config.paths()
    do_apply = "--apply" in argv
    before = scan(p)
    rep = {"mode": "apply" if do_apply else "dry-run", "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "overrides_active": config.overrides_active(), "found": before, "found_count": orphan_count(before)}
    if do_apply:
        locked, rep["actions"], rep["errors"] = apply(p)
        if locked is not None:
            rep["found_under_lock"], rep["found_count"] = locked, orphan_count(locked)
        rep["after"] = scan(p)
        rep["remaining_count"] = orphan_count(rep["after"])
    else:
        rep["actions"], rep["note"] = [], "dry-run: nothing changed; rerun with --apply to clean"
        rep["remaining_count"] = rep["found_count"]
    print(json.dumps(rep, indent=1))
    return 0 if rep["remaining_count"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
