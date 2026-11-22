"""Simulated missing prerequisites for T13/T14 (env overrides only; nothing real is removed or modified).
Simulation files live in /opt/plea-fc/sim (root 0700) and are removed afterwards."""
import os
import shutil

SIM = "/opt/plea-fc/sim"


def make(paths):
    if os.path.lexists(SIM):
        shutil.rmtree(SIM)
    os.makedirs(SIM, mode=0o700)
    cg = os.path.join(SIM, "cg", "plea-spike")
    os.makedirs(cg, mode=0o755)
    for n, v in (("cgroup.controllers", "cpu memory\n"), ("cgroup.subtree_control", "cpu memory\n"), ("cgroup.procs", "")):
        with open(os.path.join(cg, n), "w") as f:
            f.write(v)
    kern = os.path.join(SIM, "vmlinux-tampered")
    shutil.copyfile(paths["kernel"], kern)
    with open(kern, "r+b") as f:  # flip one byte in the middle; size unchanged
        f.seek(os.path.getsize(kern) // 2)
        b = f.read(1)
        f.seek(-1, 1)
        f.write(bytes([b[0] ^ 0xFF]))
    os.chmod(kern, 0o444)
    return {
        "no_kvm": ({"PLEA_KVM_PATH": "/nonexistent/kvm"}, "P01"),
        "missing_jailer": ({"PLEA_JAILER_BIN": "/nonexistent/jailer"}, "P06"),
        "missing_cgroup_controller": ({"PLEA_CGROUP_PARENT": cg}, "P04"),
        "insufficient_memory_threshold": ({"PLEA_MIN_MEM_MIB": "100000000"}, "P11"),
        "tampered_kernel_hash": ({"PLEA_KERNEL_PATH": kern}, "P07"),
    }


def remove():
    if os.path.lexists(SIM):
        shutil.rmtree(SIM)
