"""Shared constants for the Stage B Firecracker spike. Standard library only.

Every path can be overridden by a PLEA_* environment variable, but ONLY the
simulation tests (T13, T14, T15 demo) and selftest.py may do so; every other
test refuses to run while an override is set (see overrides_active()).
"""
import os

BUNDLE = os.path.dirname(os.path.abspath(__file__))

RELEASE = {
    "version": "v1.18.0",
    "tgz_url": "https://github.com/firecracker-microvm/firecracker/releases/download/"
               "v1.18.0/firecracker-v1.18.0-x86_64.tgz",
    "tgz_size": 7606252,
    "tgz_sha256": "1ac8eec866dd5eea14efecf6323e22b23eea24054545338a5b34bc5bca6623cd",
    "inner_dir": "release-v1.18.0-x86_64",
    "inner": {
        "firecracker-v1.18.0-x86_64": "b33f46cd6d88834cf6a4f8d184f08f219809c636236bffd286d233a60602a2ba",
        "jailer-v1.18.0-x86_64": "ddadbaa15b5c942271a83b7040ca7259c8ccf92a9e08d44cce0b86fa407ba460",
        "seccomp-filter-v1.18.0-x86_64.json": "e165d4a31f03c7e8398622fe11078f506f7e0191b7f9272c2d583274f3f51656",
    },
    "git_url": "https://github.com/firecracker-microvm/firecracker",
}

CI = {
    "base": "https://s3.amazonaws.com/spec.ccfc.min/firecracker-ci/20261118-6d7cfa9c6b53-0/x86_64/",
    "kernel": "vmlinux-6.1.188",          # preferred (docs/kernel-policy.md: 5.10, 6.1, 6.18)
    "kernel_alt": "vmlinux-6.18.62",      # used only if the owner passes --kernel 6.18
    "squashfs": "ubuntu-24.04.squashfs",
    "kernel_max": 256 << 20,              # download caps (bytes)
    "squashfs_max": 2 << 30,
}

# Unprivileged host uid/gid range for jailed VMMs (uid == gid, one per microVM).
UID_MIN, UID_MAX = 64000, 64999
GUEST_UID = 10001                          # unprivileged user inside the guest
PARENT_CGROUP = "plea-spike"
CONTROLLERS = ("cpu", "memory", "pids")

CAPS = {
    "payload": 1 << 20,        # max payload bytes on /dev/vdb
    "outcap": 64 << 10,        # max workload stdout kept by the guest
    "errcap": 4 << 10,         # max workload stderr kept by the guest
    "hdrcap": 4096,            # max result header line
    "console_head": 16 << 10,  # host keeps first N bytes of the serial console
    "console_tail": 16 << 10,  # ... and the last N bytes; the rest is counted, not stored
    "stderr_head": 8 << 10,
    "stderr_tail": 8 << 10,
}

DEFAULTS = {
    "vcpus": 1, "mem_mib": 128,
    "cpu_max": "100000",       # cgroup v2 cpu.max quota (us) with the default 100000us period = 1 CPU
    "mem_overhead_mib": 192,   # memory.max = guest memory + this
    "pids_max": 64,
    "fsize": 16 << 20,         # RLIMIT_FSIZE for the jailed VMM (must exceed the firecracker binary)
    "nofile": 1024,            # RLIMIT_NOFILE for the jailed VMM
    "guest_timeout": 20, "host_timeout": 90,
    "guest_nofile": 1024, "guest_nproc": 256, "guest_filemax": 0, "guest_tmp_mib": 16,
}

MIN_MEM_MIB = 1024             # prereq: MemAvailable floor
MIN_DISK_MIB = 6144            # prereq: free space on the chroot base filesystem
LAUNCH_RESERVE_MIB = 512       # fclib: MemAvailable must exceed guest mem + overhead + this

OVERRIDES = ("PLEA_KVM_PATH", "PLEA_FC_BIN", "PLEA_JAILER_BIN", "PLEA_KERNEL_PATH",
             "PLEA_ROOTFS_PATH", "PLEA_PINS_PATH", "PLEA_CGROUP_ROOT", "PLEA_CGROUP_PARENT",
             "PLEA_CHROOT_BASE", "PLEA_RUN_DIR", "PLEA_MIN_MEM_MIB", "PLEA_MIN_DISK_MIB",
             "PLEA_UID_MIN", "PLEA_UID_MAX", "PLEA_SWAPS", "PLEA_MEMINFO", "PLEA_BUNDLE_DIR")


def _e(key, default):
    return os.environ.get(key, default)


def paths():
    """Resolved at call time so a test can set overrides in-process."""
    root = _e("PLEA_CGROUP_ROOT", "/sys/fs/cgroup")
    return {
        "kvm": _e("PLEA_KVM_PATH", "/dev/kvm"),
        "opt": "/opt/plea-fc",
        "fc": _e("PLEA_FC_BIN", "/opt/plea-fc/bin/firecracker"),
        "jailer": _e("PLEA_JAILER_BIN", "/opt/plea-fc/bin/jailer"),
        "kernel": _e("PLEA_KERNEL_PATH", "/opt/plea-fc/images/vmlinux"),
        "rootfs": _e("PLEA_ROOTFS_PATH", "/opt/plea-fc/images/rootfs.ext4"),
        "pins": _e("PLEA_PINS_PATH", "/opt/plea-fc/pins.json"),
        "cg_root": root,
        "cg_parent": _e("PLEA_CGROUP_PARENT", os.path.join(root, PARENT_CGROUP)),
        "chroot_base": _e("PLEA_CHROOT_BASE", "/srv/plea-jailer"),
        "run": _e("PLEA_RUN_DIR", "/run/plea-fc"),
        "swaps": _e("PLEA_SWAPS", "/proc/swaps"),
        "meminfo": _e("PLEA_MEMINFO", "/proc/meminfo"),
        "bundle": _e("PLEA_BUNDLE_DIR", BUNDLE),
    }


def uid_range():
    return int(_e("PLEA_UID_MIN", UID_MIN)), int(_e("PLEA_UID_MAX", UID_MAX))


def minima():
    return int(_e("PLEA_MIN_MEM_MIB", MIN_MEM_MIB)), int(_e("PLEA_MIN_DISK_MIB", MIN_DISK_MIB))


def overrides_active():
    return sorted(k for k in OVERRIDES if k in os.environ)
