#!/usr/bin/env python3
"""Isolation prerequisites. Each check is MET or NOT MET with evidence.
Exit 0 only if every check is MET. Fail closed: any exception => NOT MET.

Usage: python3 -I -B prereq.py [--no-hash-images]
"""
import fcntl
import json
import os
import stat
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402
import util  # noqa: E402

KVM_GET_API_VERSION, KVM_CREATE_VM, KVM_CHECK_EXTENSION = 0xAE00, 0xAE01, 0xAE03
# Capability numbers from linux/include/uapi/linux/kvm.h (stage0 cross-checks the header if present).
KVM_CAPS = {"KVM_CAP_IRQCHIP": 0, "KVM_CAP_USER_MEMORY": 3, "KVM_CAP_SET_TSS_ADDR": 4,
            "KVM_CAP_EXT_CPUID": 7, "KVM_CAP_NR_VCPUS": 9, "KVM_CAP_NR_MEMSLOTS": 10,
            "KVM_CAP_MP_STATE": 14, "KVM_CAP_IRQFD": 32, "KVM_CAP_PIT2": 33, "KVM_CAP_IOEVENTFD": 36}
CGROUP2_REQUIRED = config.CONTROLLERS


def _check(cid, name, fn):
    try:
        met, ev = fn()
    except Exception as e:  # fail closed
        met, ev = False, {"exception": f"{type(e).__name__}: {e}"}
    return {"id": cid, "name": name, "met": bool(met), "status": "MET" if met else "NOT MET", "evidence": ev}


def kvm_device(p):
    st = os.stat(p["kvm"])
    ev = {"path": p["kvm"], "is_char": stat.S_ISCHR(st.st_mode),
          "major_minor": [os.major(st.st_rdev), os.minor(st.st_rdev)] if stat.S_ISCHR(st.st_mode) else None,
          "mode": oct(st.st_mode & 0o7777), "uid": st.st_uid, "gid": st.st_gid}
    return ev["is_char"] and ev["major_minor"] == [10, 232], ev


def kvm_ioctl(p):
    fd = os.open(p["kvm"], os.O_RDWR | os.O_CLOEXEC)
    try:
        api = fcntl.ioctl(fd, KVM_GET_API_VERSION, 0)
        caps = {k: fcntl.ioctl(fd, KVM_CHECK_EXTENSION, v) for k, v in KVM_CAPS.items()}
        vmfd = fcntl.ioctl(fd, KVM_CREATE_VM, 0)
        os.close(vmfd)
    finally:
        os.close(fd)
    need = [k for k in KVM_CAPS if k not in ("KVM_CAP_NR_VCPUS", "KVM_CAP_NR_MEMSLOTS")]
    missing = [k for k in need if caps[k] <= 0]
    return api == 12 and not missing, {"api_version": api, "caps": caps, "missing_caps": missing,
                                       "create_vm": "ok", "vm_fd_closed": True}


def cgroup_v2(p):
    mi = [m for m in util.mountinfo() if m["mount_point"] == p["cg_root"]]
    fstypes = [m["fstype"] for m in mi]
    ctl = util.read_bounded(os.path.join(p["cg_root"], "cgroup.controllers"), 4096).split()
    sub = util.read_bounded(os.path.join(p["cg_root"], "cgroup.subtree_control"), 4096).split()
    miss = [c for c in CGROUP2_REQUIRED if c not in ctl or c not in sub]
    return fstypes[-1:] == ["cgroup2"] and not miss, {"cg_root": p["cg_root"], "fstype": fstypes,
                                                      "root_controllers": ctl, "root_subtree_control": sub,
                                                      "missing_in_root": miss}


def cgroup_parent(p):
    par = p["cg_parent"]
    inside = os.path.realpath(par).startswith(os.path.realpath(p["cg_root"]) + "/")
    ctl = util.read_bounded(os.path.join(par, "cgroup.controllers"), 4096).split()
    sub = util.read_bounded(os.path.join(par, "cgroup.subtree_control"), 4096).split()
    procs = util.read_bounded(os.path.join(par, "cgroup.procs"), 65536).split()
    miss = [c for c in CGROUP2_REQUIRED if c not in ctl or c not in sub]
    st = os.lstat(par)
    return (inside and not miss and not procs and st.st_uid == 0 and stat.S_ISDIR(st.st_mode)), {
        "parent": par, "inside_cgroup_root": inside, "controllers": ctl, "subtree_control": sub,
        "missing": miss, "parent_has_procs": len(procs), "uid": st.st_uid}


def _pins(p):
    probs = util.path_problems(p["pins"])
    st = os.lstat(p["pins"])
    if not stat.S_ISREG(st.st_mode):
        probs.append("pins: not a regular file")
    return util.load_json(p["pins"]), probs


def pins_file(p):
    pins, probs = _pins(p)
    files = pins.get("files", {})
    need = ("firecracker", "jailer", "seccomp_json", "kernel", "squashfs", "rootfs")
    missing = [k for k in need if not files.get(k, {}).get("sha256")]
    rel = config.RELEASE["inner"]
    release_match = {
        "firecracker": files.get("firecracker", {}).get("sha256") == rel["firecracker-v1.18.0-x86_64"],
        "jailer": files.get("jailer", {}).get("sha256") == rel["jailer-v1.18.0-x86_64"],
        "seccomp_json": files.get("seccomp_json", {}).get("sha256") == rel["seccomp-filter-v1.18.0-x86_64.json"],
    }
    return not probs and not missing and all(release_match.values()), {
        "path": p["pins"], "path_problems": probs, "missing": missing, "release_constants_match": release_match}


def _pinned_file(p, key, path, hash_it=True, magic=None, mode_max=0o755):
    pins, _ = _pins(p)
    pin = pins["files"][key]
    st = os.lstat(path)
    ev = {"path": path, "uid": st.st_uid, "gid": st.st_gid, "mode": oct(st.st_mode & 0o7777),
          "size": st.st_size, "pinned_size": pin.get("size"), "pinned_sha256": pin["sha256"],
          "path_problems": util.path_problems(path)}
    ok = (stat.S_ISREG(st.st_mode) and st.st_uid == 0 and not (st.st_mode & 0o022)
          and not (st.st_mode & ~mode_max & 0o7777) and not ev["path_problems"]
          and st.st_size == pin.get("size"))
    if magic is not None:
        with open(path, "rb") as f:
            ev["magic_ok"] = f.read(len(magic)) == magic
        ok = ok and ev["magic_ok"]
    if hash_it:
        ev["sha256"], _ = util.sha256_file(path)
        ok = ok and ev["sha256"] == pin["sha256"]
    else:
        ev["sha256"] = "not hashed here (fclib re-hashes the chroot copy before use)"
    return ok, ev


def binaries(p):
    a, ea = _pinned_file(p, "firecracker", p["fc"], magic=b"\x7fELF")
    b, eb = _pinned_file(p, "jailer", p["jailer"], magic=b"\x7fELF")
    return a and b, {"firecracker": ea, "jailer": eb}


def chroot_base(p):
    base = p["chroot_base"]
    st = os.lstat(base)
    probs = util.path_problems(base)
    return stat.S_ISDIR(st.st_mode) and not probs, {"path": base, "path_problems": probs,
                                                    "mode": oct(st.st_mode & 0o7777)}


def swap_off(p):
    lines = util.read_bounded(p["swaps"], 65536).strip().splitlines()
    return len(lines) <= 1, {"swaps": lines[:20]}


def memory(p):
    mi = util.meminfo(p["meminfo"])
    avail = mi.get("MemAvailable", 0) // 1024
    need, _ = config.minima()
    return avail >= need, {"MemAvailable_MiB": avail, "MemTotal_MiB": mi.get("MemTotal", 0) // 1024,
                           "declared_min_MiB": need}


def disk(p):
    path = p["chroot_base"]
    while not os.path.exists(path):
        path = os.path.dirname(path)
    sv = os.statvfs(path)
    free = sv.f_bavail * sv.f_frsize >> 20
    _, need = config.minima()
    return free >= need, {"statvfs_path": path, "free_MiB": free, "declared_min_MiB": need}


def bundle_dir(p):
    probs = util.path_problems(p["bundle"])
    return not probs, {"path": p["bundle"], "path_problems": probs}


def check_all(hash_images=True):
    p = config.paths()
    checks = [
        _check("P01", "kvm_char_device", lambda: kvm_device(p)),
        _check("P02", "kvm_ioctl_api12_caps_create_vm", lambda: kvm_ioctl(p)),
        _check("P03", "cgroup_v2_root_controllers", lambda: cgroup_v2(p)),
        _check("P04", "cgroup_parent_cpu_memory_pids_enableable", lambda: cgroup_parent(p)),
        _check("P05", "pins_file_and_release_constants", lambda: pins_file(p)),
        _check("P06", "firecracker_jailer_pinned", lambda: binaries(p)),
        _check("P07", "kernel_pinned", lambda: _pinned_file(p, "kernel", p["kernel"], hash_images,
                                                           magic=b"\x7fELF", mode_max=0o644)),
        _check("P08", "rootfs_pinned", lambda: _pinned_file(p, "rootfs", p["rootfs"], hash_images,
                                                           mode_max=0o644)),
        _check("P09", "chroot_base_root_owned_path", lambda: chroot_base(p)),
        _check("P10", "swap_off", lambda: swap_off(p)),
        _check("P11", "memory_above_minimum", lambda: memory(p)),
        _check("P12", "disk_above_minimum", lambda: disk(p)),
        _check("P13", "bundle_dir_root_owned_path", lambda: bundle_dir(p)),
    ]
    return {"all_met": all(c["met"] for c in checks), "hash_images": hash_images,
            "overrides_active": config.overrides_active(), "checks": checks,
            "not_met": [c["id"] + ":" + c["name"] for c in checks if not c["met"]]}


def main():
    r = check_all(hash_images="--no-hash-images" not in sys.argv)
    json.dump(r, sys.stdout, indent=1)
    print()
    for c in r["checks"]:
        print(f"{c['id']} {c['status']:8} {c['name']}", file=sys.stderr)
    return 0 if r["all_met"] else 1


if __name__ == "__main__":
    sys.exit(main())
