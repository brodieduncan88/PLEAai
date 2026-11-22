"""Shared library for the KVM-host harness. WRITTEN, NOT RUN on the authoring machine.
Standard library only. Every entry point calls require_prereqs() first and
exits 2 (refuse) if any prerequisite fails. There is no fallback engine."""
import http.client, json, os, shutil, signal, socket, subprocess, sys, time, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import prereq  # noqa: E402

HOME = Path(os.environ.get("PLEA_SPIKE_HOME", ROOT))
FC_BIN = os.environ.get("FC_BIN", str(HOME / "downloads" / "firecracker"))
KERNEL = os.environ.get("FC_KERNEL", str(HOME / "guest_image" / "out" / "vmlinux"))
ROOTFS = os.environ.get("FC_ROOTFS", str(HOME / "guest_image" / "out" / "rootfs.ext4"))
WORKDIR = Path(os.environ.get("PLEA_SPIKE_WORKDIR", "/run/plea-spike"))   # per-VM dirs
CG_ROOT = Path("/sys/fs/cgroup")
VM_PREFIX = "spike-"
CTRL = ("memory", "pids", "cpu")


def require_prereqs(cgroup_parent=None):
    argv = ["--firecracker", FC_BIN, "--kernel", KERNEL, "--rootfs", ROOTFS]
    if cgroup_parent:
        argv += ["--cgroup-parent", str(cgroup_parent)]
    args = _Args(argv)
    res = prereq.run_checks(args)
    if not res["all_met"]:
        print("REFUSED: isolation unavailable (fail closed, no fallback):", file=sys.stderr)
        for c in res["checks"]:
            if not c["met"]:
                print("  NOT MET %s: %s" % (c["id"], c["reason"]), file=sys.stderr)
        sys.exit(2)
    return res


class _Args:
    def __init__(self, argv):
        import argparse
        p = argparse.ArgumentParser()
        p.add_argument("--kvm", default="/dev/kvm"); p.add_argument("--cgroup-root", default=str(CG_ROOT))
        p.add_argument("--cgroup-parent", default=None)
        p.add_argument("--pins", default=str(ROOT / "pins.json"))
        p.add_argument("--firecracker"); p.add_argument("--kernel"); p.add_argument("--rootfs")
        self.__dict__.update(vars(p.parse_args(argv)))


# ---- cgroup v2 -------------------------------------------------------------
def prepare_parent():
    """Under a Delegate=yes service: move this process to <own>/mgr, then enable
    controllers on the own cgroup so children can have limits. Returns parent Path."""
    own = Path(prereq.default_parent(str(CG_ROOT)))
    mgr = own / "mgr"
    mgr.mkdir(exist_ok=True)
    (mgr / "cgroup.procs").write_text(str(os.getpid()))
    sub = (own / "cgroup.subtree_control").read_text().split()
    need = [c for c in CTRL if c not in sub]
    if need:
        (own / "cgroup.subtree_control").write_text(" ".join("+" + c for c in need))
    return own


def cg_read(cg, name):
    return (Path(cg) / name).read_text().strip()


def cg_populated(cg):
    return "populated 1" in cg_read(cg, "cgroup.events")


def cg_kill_and_remove(cg, timeout=5.0):
    cg = Path(cg)
    if not cg.exists():
        return True
    try:
        (cg / "cgroup.kill").write_text("1")
    except OSError:
        pass
    t0 = time.monotonic()
    while cg_populated(cg) and time.monotonic() - t0 < timeout:
        time.sleep(0.01)
    try:
        cg.rmdir()
        return True
    except OSError:
        return False


# ---- API over unix socket ----------------------------------------------------
class _UnixConn(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__("localhost"); self._p = path
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(10); self.sock.connect(self._p)


def api(sock_path, method, path, body=None):
    c = _UnixConn(sock_path)
    try:
        data = json.dumps(body) if body is not None else None
        c.request(method, path, body=data, headers={"Content-Type": "application/json", "Accept": "application/json"})
        r = c.getresponse()
        return r.status, r.read().decode()
    finally:
        c.close()


# ---- host sampling -------------------------------------------------------------
def host_sample(pids=()):
    fn = [int(x) for x in Path("/proc/sys/fs/file-nr").read_text().split()]
    mem = {l.split(":")[0]: int(l.split()[1]) for l in Path("/proc/meminfo").read_text().splitlines()}
    s = {"t": time.monotonic(), "file_nr_allocated": fn[0], "file_max": fn[2],
         "mem_available_kib": mem["MemAvailable"], "mem_free_kib": mem["MemFree"], "vmm": {}}
    for pid in pids:
        try:
            st = {l.split(":")[0]: l.split(":")[1].strip() for l in Path("/proc/%d/status" % pid).read_text().splitlines()}
            s["vmm"][pid] = {"fds": len(os.listdir("/proc/%d/fd" % pid)), "threads": int(st["Threads"]),
                             "rss_kib": int(st["VmRSS"].split()[0])}
        except Exception as e:  # noqa: BLE001
            s["vmm"][pid] = {"error": "%s: %s" % (type(e).__name__, e)}
    return s


class VM:
    def __init__(self, parent, job="workload", mem_mib=128, vcpus=1, cmdline_extra="",
                 mem_overhead_mib=96, pids_max=64, cpu_quota_us=None, vm_id=None):
        self.id = vm_id or uuid.uuid4().hex[:8]
        self.parent, self.job, self.mem_mib, self.vcpus = Path(parent), job, mem_mib, vcpus
        self.cmdline_extra = cmdline_extra
        self.limits = {"memory.max": str((mem_mib + mem_overhead_mib) * 1024 * 1024),
                       "pids.max": str(pids_max),
                       "cpu.max": "%d 100000" % (cpu_quota_us or vcpus * 100000)}
        self.dir = WORKDIR / (VM_PREFIX + self.id)
        self.cg = self.parent / (VM_PREFIX + self.id)
        self.sock = self.dir / "api.sock"
        self.console = self.dir / "console.log"
        self.proc = None
        self.t = {}

    def start(self):
        self.dir.mkdir(parents=True, mode=0o700)
        self.cg.mkdir()
        for k, v in self.limits.items():
            (self.cg / k).write_text(v)
        cgprocs = str(self.cg / "cgroup.procs")
        def _enter():  # runs in the child before exec: VMM is born inside its cgroup
            with open(cgprocs, "w") as f:
                f.write(str(os.getpid()))
            os.setsid()
        self.t["t0"] = time.monotonic()
        out = open(self.console, "wb")
        # seccomp is left at Firecracker's default (enabled). Do NOT add --no-seccomp.
        self.proc = subprocess.Popen([FC_BIN, "--api-sock", str(self.sock), "--level", "Warning",
                                      "--log-path", str(self.dir / "fc.log")],
                                     stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                     preexec_fn=_enter, close_fds=True)
        (self.dir / "pid").write_text(str(self.proc.pid))
        while not self.sock.exists():
            if self.proc.poll() is not None:
                raise RuntimeError("firecracker exited early rc=%s: %s" % (self.proc.returncode, self.console_text()[-500:]))
            time.sleep(0.001)
        self.t["api_ready"] = time.monotonic()
        boot = "console=ttyS0 reboot=k panic=1 pci=off ro root=/dev/vda init=/sbin/init spike.job=%s %s" % (self.job, self.cmdline_extra)
        for path, body in (
            ("/boot-source", {"kernel_image_path": KERNEL, "boot_args": boot}),
            ("/drives/rootfs", {"drive_id": "rootfs", "path_on_host": ROOTFS, "is_root_device": True, "is_read_only": True}),
            ("/machine-config", {"vcpu_count": self.vcpus, "mem_size_mib": self.mem_mib, "smt": False}),
        ):
            st, txt = api(str(self.sock), "PUT", path, body)
            if st >= 300:
                raise RuntimeError("PUT %s -> %s %s" % (path, st, txt))
        self.t["configured"] = time.monotonic()
        st, txt = api(str(self.sock), "PUT", "/actions", {"action_type": "InstanceStart"})
        if st >= 300:
            raise RuntimeError("InstanceStart -> %s %s" % (st, txt))
        self.t["start_sent"] = time.monotonic()
        return self

    def console_text(self):
        try:
            return self.console.read_text(errors="replace")
        except OSError:
            return ""

    def wait_marker(self, marker, timeout=60):
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            if marker in self.console_text():
                return time.monotonic()
            if self.proc.poll() is not None:
                return time.monotonic() if marker in self.console_text() else None
            time.sleep(0.001)
        return None

    def wait_exit(self, timeout=120):
        try:
            self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return False
        self.t["exit"] = time.monotonic()
        return True

    def result(self):
        for line in self.console_text().splitlines():
            if "SPIKE_RESULT " in line:
                try:
                    return json.loads(line.split("SPIKE_RESULT ", 1)[1])
                except ValueError:
                    pass
        return None

    def cleanup(self):
        ok = cg_kill_and_remove(self.cg)
        if self.proc:
            try: self.proc.wait(timeout=2)
            except Exception: pass  # noqa: BLE001
        shutil.rmtree(self.dir, ignore_errors=True)
        return ok and not self.dir.exists()
