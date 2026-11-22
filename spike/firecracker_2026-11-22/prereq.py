#!/usr/bin/env python3
"""PLEA Firecracker spike: prerequisite checker (standard library only).

Every check returns (met: bool, reason: str). Any exception becomes NOT MET.
Exit status: 0 only if every check is met, 1 otherwise.
Prints one JSON document, then human-readable lines.  Non-mutating: never writes
to cgroup files and never starts a VM.
"""
import argparse, fcntl, hashlib, json, os, stat, sys, time

KVM_GET_API_VERSION = 0xAE00
KVM_EXPECTED_API = 12
CONTROLLERS = ("memory", "pids", "cpu")
HERE = os.path.dirname(os.path.abspath(__file__))
MANDATORY_IDS = (
    "kvm_device", "kvm_api_version", "cgroup_v2", "cgroup_controllers",
    "firecracker_binary", "guest_kernel", "guest_rootfs",
)


def _read(path, limit=1 << 16):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read(limit)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_pins(path):
    """Returns (pins_dict, error_or_None). Never raises."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d, dict):
            return {}, "pins file is not a JSON object"
        return d, None
    except Exception as e:  # noqa: BLE001
        return {}, "cannot read pins file: %s: %s" % (type(e).__name__, e)


def check_kvm_device(path="/dev/kvm"):
    st = os.stat(path)
    if not stat.S_ISCHR(st.st_mode):
        return False, "%s exists but is not a character device (mode %o)" % (path, st.st_mode)
    fd = os.open(path, os.O_RDWR)
    os.close(fd)
    return True, "%s is a character device and opens read-write as uid %d" % (path, os.geteuid())


def check_kvm_api(path="/dev/kvm"):
    fd = os.open(path, os.O_RDWR)
    try:
        ver = fcntl.ioctl(fd, KVM_GET_API_VERSION, 0)
    finally:
        os.close(fd)
    if ver != KVM_EXPECTED_API:
        return False, "KVM_GET_API_VERSION returned %r, expected %d" % (ver, KVM_EXPECTED_API)
    return True, "KVM_GET_API_VERSION == %d" % ver


def _mount_fstype(mountpoint):
    best = None
    for line in _read("/proc/self/mountinfo", 1 << 22).splitlines():
        left, sep, right = line.partition(" - ")
        if not sep:
            continue
        lf, rf = left.split(), right.split()
        if len(lf) > 4 and lf[4] == mountpoint and rf:
            best = rf[0]  # later entries shadow earlier ones
    return best


def check_cgroup_v2(root="/sys/fs/cgroup"):
    fstype = _mount_fstype(root)
    if fstype != "cgroup2":
        return False, "%s filesystem type is %r, not cgroup2 (unified hierarchy required)" % (root, fstype)
    if not os.path.exists(os.path.join(root, "cgroup.controllers")):
        return False, "%s/cgroup.controllers missing" % root
    return True, "%s is cgroup2 with cgroup.controllers present" % root


def default_parent(root="/sys/fs/cgroup"):
    """The calling process's own cgroup under v2, else the root."""
    try:
        for line in _read("/proc/self/cgroup").splitlines():
            if line.startswith("0::"):
                rel = line[3:].strip().lstrip("/")
                p = os.path.join(root, rel) if rel else root
                if os.path.isdir(p):
                    return p
    except Exception:  # noqa: BLE001
        pass
    return root


def check_controllers(parent):
    avail = set(_read(os.path.join(parent, "cgroup.controllers")).split())
    sub_path = os.path.join(parent, "cgroup.subtree_control")
    sub = set(_read(sub_path).split())
    problems, notes = [], []
    for c in CONTROLLERS:
        if c in sub:
            notes.append("%s delegated" % c)
        elif c in avail and os.access(sub_path, os.W_OK):
            notes.append("%s enable-able (not yet in subtree_control; needs a leaf manager "
                         "cgroup, not verified by this non-mutating check)" % c)
        elif c in avail:
            problems.append("%s available but %s is not writable by uid %d" % (c, sub_path, os.geteuid()))
        else:
            problems.append("%s not in cgroup.controllers of %s" % (c, parent))
    if problems:
        return False, "; ".join(problems)
    return True, "parent %s: %s" % (parent, "; ".join(notes))


def _pin_check(label, path, pin):
    if not pin:
        return False, "%s pin is empty in pins file (empty pin means NOT MET)" % label
    if not path:
        return False, "%s path not given" % label
    actual = sha256_file(path)
    if actual != pin.lower():
        return False, "%s SHA-256 mismatch: actual %s, pinned %s" % (label, actual, pin)
    return True, "%s SHA-256 matches pin (%s)" % (label, actual)


def run_checks(args):
    pins, pin_err = load_pins(args.pins)
    pins = pins if isinstance(pins, dict) else {}
    parent = args.cgroup_parent or default_parent(args.cgroup_root)
    plan = [
        ("kvm_device", lambda: check_kvm_device(args.kvm)),
        ("kvm_api_version", lambda: check_kvm_api(args.kvm)),
        ("cgroup_v2", lambda: check_cgroup_v2(args.cgroup_root)),
        ("cgroup_controllers", lambda: check_controllers(parent)),
        ("firecracker_binary", lambda: _pin_check("firecracker binary", args.firecracker, pins.get("firecracker_sha256", ""))),
        ("guest_kernel", lambda: _pin_check("guest kernel", args.kernel, pins.get("kernel_sha256", ""))),
        ("guest_rootfs", lambda: _pin_check("guest rootfs", args.rootfs, pins.get("rootfs_sha256", ""))),
    ]
    checks = []
    for cid, fn in plan:
        try:
            met, reason = fn()
            met = bool(met)
        except BaseException as e:  # noqa: BLE001 - every failure is NOT MET
            if isinstance(e, KeyboardInterrupt):
                raise
            met, reason = False, "%s: %s" % (type(e).__name__, e)
        if pin_err and cid in ("firecracker_binary", "guest_kernel", "guest_rootfs"):
            met, reason = False, pin_err
        checks.append({"id": cid, "met": met, "reason": reason})
    return {
        "tool": "prereq.py",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "all_met": all(c["met"] for c in checks),
        "checks": checks,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kvm", default="/dev/kvm")
    p.add_argument("--cgroup-root", default="/sys/fs/cgroup")
    p.add_argument("--cgroup-parent", default=None, help="default: own cgroup under v2")
    p.add_argument("--pins", default=os.path.join(HERE, "pins.json"))
    p.add_argument("--firecracker", default=os.environ.get("FC_BIN", os.path.join(HERE, "downloads", "firecracker")))
    p.add_argument("--kernel", default=os.environ.get("FC_KERNEL", os.path.join(HERE, "guest_image", "out", "vmlinux")))
    p.add_argument("--rootfs", default=os.environ.get("FC_ROOTFS", os.path.join(HERE, "guest_image", "out", "rootfs.ext4")))
    args = p.parse_args(argv)
    try:
        result = run_checks(args)
    except BaseException as e:  # noqa: BLE001
        if isinstance(e, KeyboardInterrupt):
            raise
        result = {"tool": "prereq.py", "all_met": False,
                  "checks": [{"id": "checker", "met": False, "reason": "%s: %s" % (type(e).__name__, e)}]}
    print(json.dumps(result, indent=2))
    for c in result["checks"]:
        print("%-9s %-20s %s" % ("MET" if c["met"] else "NOT MET", c["id"], c["reason"]))
    print("RESULT: %s" % ("ALL PREREQUISITES MET" if result["all_met"] else "NOT MET - isolation unavailable, refuse"))
    return 0 if result["all_met"] else 1


if __name__ == "__main__":
    sys.exit(main())
