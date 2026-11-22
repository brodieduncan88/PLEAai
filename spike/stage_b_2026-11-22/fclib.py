"""Launch exactly one Firecracker microVM under the jailer, bounded and always cleaned up.

run_vm(payload, **opts) -> dict. Fail closed: any unexpected state => refused / not ok.
Stdlib only. Requires root on the owner's host; nothing here was executed against KVM by the author.
"""
import errno
import fcntl
import hashlib
import json
import os
import pwd
import re
import secrets
import selectors
import shutil
import signal
import stat
import struct
import subprocess
import threading
import time

import config
import prereq
import util


class Refused(Exception):
    pass


# ---------------------------------------------------------------- wire format
def lp_encode(body, cap):
    if len(body) > cap:
        raise ValueError(f"body {len(body)} > cap {cap}")
    return struct.pack(">Q", len(body)) + body


def lp_decode(buf, cap):
    """8-byte big-endian length + bytes. Rejects short buffers, lengths above cap or beyond the buffer."""
    if len(buf) < 8:
        raise ValueError("short length prefix")
    (n,) = struct.unpack(">Q", buf[:8])
    if n > cap:
        raise ValueError(f"length {n} > cap {cap}")
    if n > len(buf) - 8:
        raise ValueError(f"length {n} exceeds available {len(buf) - 8}")
    return buf[8:8 + n]


_STATUS_RE = re.compile(r"^[A-Z_]{1,32}$")


def parse_result(body, outcap, errcap, hdrcap=config.CAPS["hdrcap"]):
    """body = JSON header line + '\\n' + stdout + stderr. Guest output is untrusted: validate everything."""
    nl = body.find(b"\n", 0, hdrcap + 1)
    if nl < 0:
        raise ValueError("no header line within hdrcap")
    hdr = json.loads(body[:nl].decode("ascii"))
    if not isinstance(hdr, dict) or hdr.get("v") != 1:
        raise ValueError("bad header version")
    if not isinstance(hdr.get("status"), str) or not _STATUS_RE.match(hdr["status"]):
        raise ValueError("bad status")
    so, se = hdr.get("stdout_len"), hdr.get("stderr_len")
    if not (isinstance(so, int) and 0 <= so <= outcap and isinstance(se, int) and 0 <= se <= errcap):
        raise ValueError("bad lengths")
    if len(body) != nl + 1 + so + se:
        raise ValueError(f"length mismatch: body {len(body)} != {nl + 1 + so + se}")
    return {"header": hdr, "stdout": body[nl + 1:nl + 1 + so], "stderr": body[nl + 1 + so:]}


def read_result(path, outcap, errcap):
    hdrcap = config.CAPS["hdrcap"]
    cap = hdrcap + 1 + outcap + errcap
    with open(path, "rb") as f:
        size = os.fstat(f.fileno()).st_size
        pre = f.read(8)
        if len(pre) < 8:
            raise ValueError("short output image")
        (n,) = struct.unpack(">Q", pre)
        if n == 0:
            raise ValueError("empty result (guest wrote nothing)")
        if n > cap or n > size - 8:
            raise ValueError(f"result length {n} exceeds cap {cap} or image {size - 8}")
        body = f.read(n)
    return parse_result(lp_decode(pre + body, cap), outcap, errcap, hdrcap)


# ---------------------------------------------------------------- bounded console reader
class BoundedReader:
    """Keeps the first head_cap and last tail_cap bytes; counts the rest as dropped.
    Scans for PLEA markers line by line with a bounded partial-line window."""
    READY = re.compile(rb"PLEA_READY ([0-9a-f]{16})")
    DONE = re.compile(rb"PLEA_DONE ([0-9a-f]{16}) ([A-Z_]{1,32})")
    WINDOW = 512

    def __init__(self, head_cap, tail_cap, markers=False):
        self.head_cap, self.tail_cap, self.markers = head_cap, tail_cap, markers
        self.head, self.tail, self.total = bytearray(), bytearray(), 0
        self._partial = b""
        self.nonce = self.t_ready = self.t_done = self.done_status = None
        self.ignored_markers = 0

    def feed(self, data, t=None):
        self.total += len(data)
        room = self.head_cap - len(self.head)
        if room > 0:
            self.head += data[:room]
            rest = data[room:]
        else:
            rest = data
        if rest and self.tail_cap:
            self.tail += rest[-self.tail_cap:]
            if len(self.tail) > self.tail_cap:
                del self.tail[:len(self.tail) - self.tail_cap]
        if self.markers:
            self._scan(data, time.monotonic() if t is None else t)

    def _scan(self, data, t):
        lines = (self._partial + data).split(b"\n")
        self._partial = lines.pop()[-self.WINDOW:]
        for line in lines:
            line = line[-self.WINDOW:]
            m = self.READY.search(line)
            if m:
                if self.nonce is None:
                    self.nonce, self.t_ready = m.group(1).decode(), t
                else:
                    self.ignored_markers += 1
            m = self.DONE.search(line)
            if m:
                if self.nonce is not None and m.group(1).decode() == self.nonce and self.t_done is None:
                    self.t_done, self.done_status = t, m.group(2).decode()
                else:
                    self.ignored_markers += 1

    @property
    def dropped(self):
        return self.total - len(self.head) - len(self.tail)

    def summary(self):
        return {"total_bytes": self.total, "kept_head": len(self.head), "kept_tail": len(self.tail),
                "dropped_bytes": self.dropped, "head_cap": self.head_cap, "tail_cap": self.tail_cap,
                "head": bytes(self.head).decode("utf-8", "replace"),
                "tail": bytes(self.tail).decode("utf-8", "replace"),
                "ignored_markers": self.ignored_markers}


# ---------------------------------------------------------------- binary / flag verification
JAILER_FLAGS = ("--id", "--exec-file", "--uid", "--gid", "--chroot-base-dir", "--cgroup",
                "--cgroup-version", "--parent-cgroup", "--resource-limit")
_flags_cache, _flags_lock = None, threading.Lock()


def has_flag(text, flag):
    return re.search(r"(?<![\w-])" + re.escape(flag) + r"(?![\w-])", text) is not None


def evaluate_flags(jhelp, jver, fhelp, fver):
    missing = [f for f in JAILER_FLAGS if not has_flag(jhelp, f)]
    no_api, api_sock = has_flag(fhelp, "--no-api"), has_flag(fhelp, "--api-sock")
    if not has_flag(fhelp, "--config-file"):
        missing.append("firecracker --config-file")
    if not no_api and not api_sock:
        missing.append("firecracker --no-api or --api-sock")
    ver_ok = "1.18.0" in jver and "1.18.0" in fver
    return {"met": not missing and ver_ok, "missing": missing, "version_ok": ver_ok,
            "jailer_version": jver.strip()[:200], "firecracker_version": fver.strip()[:200],
            "mode": "no-api" if no_api else "api-sock-in-chroot"}


def flag_check():
    global _flags_cache
    with _flags_lock:
        if _flags_cache is None:
            p = config.paths()
            out = {k: util.run([p[b], a], timeout=15) for k, b, a in (
                ("jailer_help", "jailer", "--help"), ("jailer_version", "jailer", "--version"),
                ("fc_help", "fc", "--help"), ("fc_version", "fc", "--version"))}
            txt = {k: v["stdout"] + v["stderr"] for k, v in out.items()}
            r = evaluate_flags(txt["jailer_help"], txt["jailer_version"], txt["fc_help"], txt["fc_version"])
            r["raw"] = txt
            _flags_cache = r
        return _flags_cache


# ---------------------------------------------------------------- host helpers
def procs_with_uids(lo, hi):
    """[(pid, uid, comm)] for processes whose real or effective uid is in [lo, hi]."""
    out = []
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            st = util.read_bounded(f"/proc/{d}/status", 8192)
        except OSError:
            continue
        m = re.search(r"^Uid:\s+(\d+)\s+(\d+)", st, re.M)
        c = re.search(r"^Name:\s+(.*)$", st, re.M)
        if m and (lo <= int(m.group(1)) <= hi or lo <= int(m.group(2)) <= hi):
            out.append((int(d), int(m.group(1)), c.group(1) if c else "?"))
    return out


def kill_if_uid_in(pid, lo, hi):
    """Race-free SIGKILL of a pid only while its uid is in [lo, hi]: pin the process with a pidfd first,
    then check its uid, then signal through the pidfd (a recycled pid can never be hit)."""
    try:
        pfd = os.pidfd_open(pid)
    except ProcessLookupError:
        return "gone"
    try:
        st = util.read_bounded(f"/proc/{pid}/status", 8192)
        m = re.search(r"^Uid:\s+(\d+)\s+(\d+)", st, re.M)
        if not m or not (lo <= int(m.group(1)) <= hi or lo <= int(m.group(2)) <= hi):
            return "uid not in range: not killed"
        signal.pidfd_send_signal(pfd, signal.SIGKILL)
        return "killed"
    except (ProcessLookupError, FileNotFoundError):
        return "gone"
    finally:
        os.close(pfd)


def lease_uid(run_dir, vm_id):
    lo, hi = config.uid_range()
    leases = os.path.join(run_dir, "leases")
    os.makedirs(leases, mode=0o700, exist_ok=True)
    busy = {u for _, u, _ in procs_with_uids(lo, hi)}
    start = secrets.randbelow(hi - lo + 1)
    for i in range(hi - lo + 1):
        uid = lo + (start + i) % (hi - lo + 1)
        if uid in busy:
            continue
        try:
            pwd.getpwuid(uid)
            continue  # exists in passwd: not unique to us
        except KeyError:
            pass
        try:
            fd = os.open(os.path.join(leases, str(uid)), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue
        os.write(fd, vm_id.encode())
        os.close(fd)
        return uid
    raise Refused("no free uid in range")


def place_file(src, dst, pin_sha, mode, uid=0, gid=0):
    """Copy src -> dst (new file, sparse-aware), then re-read dst and compare with pin.
    The post-copy hash is the binding check (TOCTOU: the source may change after prereq)."""
    t = time.monotonic()
    zero = bytes(1 << 20)
    sfd = os.open(src, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    dfd = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(sfd).st_mode):
            raise Refused(f"{src}: not a regular file")
        src_h, n = hashlib.sha256(), 0
        while True:
            b = os.read(sfd, 1 << 20)
            if not b:
                break
            src_h.update(b)
            if b == zero[:len(b)]:
                os.lseek(dfd, len(b), os.SEEK_CUR)
            else:
                os.write(dfd, b)
            n += len(b)
        os.ftruncate(dfd, n)
        os.fsync(dfd)
        os.fchown(dfd, uid, gid)
        os.fchmod(dfd, mode)
    finally:
        os.close(sfd)
        os.close(dfd)
    copy_sha, size = util.sha256_file(dst)
    rep = {"src": src, "dst": dst, "size": size, "pinned_sha256": pin_sha, "copy_sha256": copy_sha,
           "source_bytes_sha256": src_h.hexdigest(), "secs": round(time.monotonic() - t, 3)}
    if copy_sha != pin_sha:
        rep["refused"] = "post-copy hash differs from pin"
        raise Refused(json.dumps(rep))
    return rep


def safe_rmtree(path, base):
    rb, rp = os.path.realpath(base), os.path.realpath(path)
    if not rp.startswith(rb + "/") or rp != os.path.abspath(path):
        raise Refused(f"refusing to remove {path}: outside {base} or via symlink")
    if not shutil.rmtree.avoids_symlink_attacks:
        raise Refused("shutil.rmtree is not symlink-attack safe on this platform")
    st = os.lstat(path)
    if not stat.S_ISDIR(st.st_mode):
        raise Refused(f"{path}: not a directory")
    shutil.rmtree(path)


def mounts_under(prefix):
    pre = os.path.realpath(prefix).rstrip("/") + "/"
    return [m["mount_point"] for m in util.mountinfo() if (m["mount_point"] + "/").startswith(pre)]


def cg_read(cg, names=("cgroup.procs", "cpu.max", "cpu.stat", "memory.max", "memory.swap.max",
                       "memory.current", "memory.peak", "memory.events", "pids.max", "pids.current",
                       "pids.events")):
    out = {}
    for n in names:
        try:
            out[n] = util.read_bounded(os.path.join(cg, n), 8192).strip()
        except OSError as e:
            out[n] = f"<{e.strerror}>"
    return out


def kv(text):
    d = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("-").isdigit():
            d[parts[0]] = int(parts[1])
    return d


def vmm_snapshot(pid):
    s = {"pid": pid}
    try:
        st = util.read_bounded(f"/proc/{pid}/status", 16384)
        for k in ("Name", "Uid", "Gid", "Groups", "Seccomp", "Seccomp_filters", "NoNewPrivs", "CapEff",
                  "CapPrm", "CapBnd", "Threads", "VmRSS", "VmHWM"):
            m = re.search(rf"^{k}:\s*(.*)$", st, re.M)
            s[k] = m.group(1).strip() if m else None
        s["threads_seccomp"] = {}
        for tid in os.listdir(f"/proc/{pid}/task")[:256]:
            tst = util.read_bounded(f"/proc/{pid}/task/{tid}/status", 16384)
            comm = util.read_bounded(f"/proc/{pid}/task/{tid}/comm", 64).strip()
            m = re.search(r"^Seccomp:\s*(\d+)", tst, re.M)
            s["threads_seccomp"][f"{tid}:{comm}"] = int(m.group(1)) if m else None
        s["fd_count"] = len(os.listdir(f"/proc/{pid}/fd"))
        s["cgroup"] = util.read_bounded(f"/proc/{pid}/cgroup", 4096).strip()
        s["limits"] = [ln for ln in util.read_bounded(f"/proc/{pid}/limits", 8192).splitlines()
                       if ln.startswith(("Max file size", "Max open files", "Max processes"))]
        s["exe"] = os.readlink(f"/proc/{pid}/exe")
    except OSError as e:
        s["error"] = str(e)
    return s


def exe_sha256(pid, cap=64 << 20):
    """Hash the executable the VMM actually runs (/proc/<pid>/exe opens the mapped inode)."""
    try:
        h = hashlib.sha256()
        with open(f"/proc/{pid}/exe", "rb") as f:
            n = 0
            while n <= cap:
                b = f.read(1 << 20)
                if not b:
                    break
                h.update(b)
                n += len(b)
        return h.hexdigest()
    except OSError as e:
        return f"<{e.strerror}>"


def fd_inodes(pid):
    """{(dev, ino)} of regular files a process holds open (stat follows the magic link)."""
    out = set()
    try:
        for fd in os.listdir(f"/proc/{pid}/fd"):
            try:
                st = os.stat(f"/proc/{pid}/fd/{fd}")
            except OSError:
                continue
            if stat.S_ISREG(st.st_mode):
                out.add((st.st_dev, st.st_ino))
    except OSError:
        pass
    return out


# ---------------------------------------------------------------- launch
def opts_defaults():
    d = dict(config.DEFAULTS)
    d.update(mode="normal", probe="none", outcap=config.CAPS["outcap"], errcap=config.CAPS["errcap"],
             expect_sha=None, raw_input=None, out_size=None, console_head=config.CAPS["console_head"],
             console_tail=config.CAPS["console_tail"], sampler=None, sample_interval=0.2, on_spawn=None,
             on_ready=None, before_copy=None, before_cleanup=None, after_exit=None, kill_after_ready=None,
             kill_at_spawn=False, kill_signal_target="pid", skip_cleanup=False, check_prereq=True,
             hash_images=False, label="")
    return d


def boot_args(o, sha):
    return (f"console=ttyS0 reboot=k panic=1 pci=off quiet root=/dev/vda ro init=/plea-init "
            f"plea.mode={o['mode']} plea.probe={o['probe']} plea.sha256={sha} "
            f"plea.timeout={int(o['guest_timeout'])} plea.pcap={config.CAPS['payload']} "
            f"plea.outcap={int(o['outcap'])} plea.errcap={int(o['errcap'])} "
            f"plea.nofile={int(o['guest_nofile'])} plea.nproc={int(o['guest_nproc'])} "
            f"plea.filemax={int(o['guest_filemax'])} plea.tmpmib={int(o['guest_tmp_mib'])}")


def jailer_argv(p, o, vm_id, uid, flags):
    mem_max = (int(o["mem_mib"]) + int(o["mem_overhead_mib"])) << 20
    argv = [p["jailer"], "--id", vm_id, "--exec-file", p["fc"], "--uid", str(uid), "--gid", str(uid),
            "--chroot-base-dir", p["chroot_base"], "--cgroup-version", "2",
            "--parent-cgroup", os.path.basename(p["cg_parent"]),
            "--cgroup", f"cpu.max={o['cpu_max']}", "--cgroup", f"memory.max={mem_max}",
            "--cgroup", "memory.swap.max=0", "--cgroup", f"pids.max={int(o['pids_max'])}",
            "--resource-limit", f"fsize={int(o['fsize'])}", "--resource-limit", f"no-file={int(o['nofile'])}",
            "--", "--config-file", "/vm.json"]
    argv += ["--no-api"] if flags["mode"] == "no-api" else ["--api-sock", "/run/firecracker.socket"]
    if "--no-seccomp" in argv:
        raise Refused("--no-seccomp is forbidden")
    return argv


def run_vm(payload, **kw):
    o = opts_defaults()
    unknown = set(kw) - set(o)
    if unknown:
        raise ValueError(f"unknown options {sorted(unknown)}")
    o.update(kw)
    p = config.paths()
    r = {"label": o["label"], "ok": False, "refused": None, "spawned": False, "overrides_active": config.overrides_active(),
         "opts": {k: v for k, v in o.items() if not callable(v) and k != "raw_input"},
         "utc_start": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    T = {"prep_start": time.monotonic()}
    ctx = {"id": None, "uid": None, "pid": None, "chroot": None, "cgroup": None, "result": r}
    lockf = None
    try:
        if o["check_prereq"]:
            pr = prereq.check_all(hash_images=o["hash_images"])
            r["prereq_not_met"] = pr["not_met"]
            if not pr["all_met"]:
                raise Refused("prerequisites NOT MET: " + ", ".join(pr["not_met"]))
        flags = flag_check()
        r["flags"] = {k: v for k, v in flags.items() if k != "raw"}
        if not flags["met"]:
            raise Refused(f"jailer/firecracker flags NOT MET: {flags['missing']} version_ok={flags['version_ok']}")
        avail = util.meminfo().get("MemAvailable", 0) >> 10
        need = int(o["mem_mib"]) + int(o["mem_overhead_mib"]) + config.LAUNCH_RESERVE_MIB
        if avail < need:
            raise Refused(f"MemAvailable {avail} MiB < {need} MiB needed")
        pins = ctx["pins"] = util.load_json(p["pins"])["files"]
        sv = os.statvfs(p["chroot_base"])
        need_disk = pins["rootfs"]["size"] + pins["kernel"]["size"] + (256 << 20)
        if sv.f_bavail * sv.f_frsize < need_disk:
            raise Refused("insufficient free disk for chroot copies")
        os.makedirs(p["run"], mode=0o700, exist_ok=True)
        lockf = open(os.path.join(p["run"], "run.lock"), "a")
        fcntl.flock(lockf, fcntl.LOCK_SH)

        vm_id = "plea-" + secrets.token_hex(6)
        ctx["id"] = r["vm_id"] = vm_id
        uid = ctx["uid"] = r["uid"] = r["gid"] = lease_uid(p["run"], vm_id)
        exec_dir = os.path.join(p["chroot_base"], os.path.basename(p["fc"]))
        os.makedirs(exec_dir, mode=0o755, exist_ok=True)
        if util.path_problems(exec_dir):
            raise Refused(f"unsafe chroot path: {util.path_problems(exec_dir)}")
        id_dir = os.path.join(exec_dir, vm_id)
        os.mkdir(id_dir, 0o755)  # FileExistsError => refuse (unique id)
        root = ctx["chroot"] = r["chroot"] = os.path.join(id_dir, "root")
        os.mkdir(root, 0o755)
        ctx["cgroup"] = r["cgroup_expected"] = os.path.join(p["cg_parent"], vm_id)
        if o["before_copy"]:
            o["before_copy"](ctx)
        r["placed"] = [place_file(p["kernel"], f"{root}/vmlinux", pins["kernel"]["sha256"], 0o444),
                       place_file(p["rootfs"], f"{root}/rootfs.ext4", pins["rootfs"]["sha256"], 0o444)]
        sha = o["expect_sha"] or hashlib.sha256(payload).hexdigest()
        r["payload_sha256"], r["payload_len"] = hashlib.sha256(payload).hexdigest(), len(payload)
        img = o["raw_input"] if o["raw_input"] is not None else lp_encode(payload, config.CAPS["payload"])
        img += bytes(-len(img) % 4096 or (4096 if not img else 0))
        _write_new(f"{root}/in.img", img, 0o440, 0, uid)
        r["in_img_sha256"] = hashlib.sha256(img).hexdigest()
        out_size = o["out_size"] or (8 + config.CAPS["hdrcap"] + o["outcap"] + o["errcap"] + 8191) // 4096 * 4096
        fd = os.open(f"{root}/out.img", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        os.ftruncate(fd, out_size)
        os.fchown(fd, uid, uid)
        os.close(fd)
        r["out_size"] = out_size
        if flags["mode"] != "no-api":
            os.mkdir(f"{root}/run", 0o700)
            os.chown(f"{root}/run", uid, uid)
        vmcfg = {"boot-source": {"kernel_image_path": "/vmlinux", "boot_args": boot_args(o, sha)},
                 "drives": [{"drive_id": "rootfs", "path_on_host": "/rootfs.ext4", "is_root_device": True, "is_read_only": True},
                            {"drive_id": "input", "path_on_host": "/in.img", "is_root_device": False, "is_read_only": True},
                            {"drive_id": "output", "path_on_host": "/out.img", "is_root_device": False, "is_read_only": False}],
                 "machine-config": {"vcpu_count": int(o["vcpus"]), "mem_size_mib": int(o["mem_mib"])}}
        _write_new(f"{root}/vm.json", json.dumps(vmcfg, indent=1).encode(), 0o440, 0, uid)
        r["vm_config"] = vmcfg
        argv = r["argv"] = jailer_argv(p, o, vm_id, uid, flags)
        _spawn_and_watch(argv, o, r, ctx, T)
    except Refused as e:
        r["refused"] = str(e)[:4000]
    except Exception as e:  # fail closed
        r["error"] = f"{type(e).__name__}: {e}"[:4000]
    finally:
        if o["before_cleanup"] and ctx.get("chroot"):
            try:
                o["before_cleanup"](ctx)
            except Exception as e:
                r["hook_error"] = str(e)
        if ctx.get("id") and not o["skip_cleanup"]:
            r["cleanup"] = cleanup(ctx, p)
        elif ctx.get("id"):
            r["cleanup"] = {"skipped": True}
        T["clean"] = time.monotonic()
        if lockf:
            lockf.close()
    t0 = T.get("spawn")
    r["timings_s"] = {k: (round(v - t0, 4) if t0 else None) for k, v in T.items() if k != "spawn"}
    if t0:
        r["timings_s"]["prep_start"] = round(T["prep_start"] - t0, 4)
    cl = r.get("cleanup", {})
    r["clean"] = bool(cl) and not cl.get("skipped") and not cl.get("leftovers")
    res = r.get("result_parsed") or {}
    r["ok"] = bool(r["spawned"] and r.get("ready") and r.get("done") and r.get("result_status") == "OK"
                   and res.get("status") == "OK" and not r.get("watchdog_fired") and r["clean"]
                   and r.get("in_img_unchanged") and r.get("vmm_exe_matches_pin"))
    return r


def _write_new(path, data, mode, uid, gid):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
        os.fchown(fd, uid, gid)
        os.fchmod(fd, mode)
    finally:
        os.close(fd)


def _spawn_and_watch(argv, o, r, ctx, T):
    con = BoundedReader(o["console_head"], o["console_tail"], markers=True)
    err = BoundedReader(config.CAPS["stderr_head"], config.CAPS["stderr_tail"])
    T["spawn"] = time.monotonic()
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True, close_fds=True, env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin"},
                            extra_groups=[])  # setgroups([]) before exec: the jailer/VMM never inherit root's groups
    r["spawned"], ctx["pid"], ctx["proc"] = True, proc.pid, proc
    ctx["t_spawn"] = r["t_spawn_monotonic"] = T["spawn"]
    r["pid"] = proc.pid
    if o["on_spawn"]:
        o["on_spawn"](ctx)
    if o["kill_at_spawn"]:
        r["killed_at_spawn"] = {"exe": _readlink(f"/proc/{proc.pid}/exe"), "t": time.monotonic() - T["spawn"]}
        _kill(proc.pid, group=False)
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ, con)
    sel.register(proc.stderr, selectors.EVENT_READ, err)
    deadline, kill_at, hard_stop, open_streams = T["spawn"] + o["host_timeout"], None, None, 2
    next_sample, seen_ready = 0.0, False
    while open_streams:
        now = time.monotonic()
        if now >= deadline and not r.get("watchdog_fired"):
            r["watchdog_fired"] = round(now - T["spawn"], 3)
            _kill(proc.pid, group=True)
            hard_stop = now + 10
        if kill_at and now >= kill_at and not r.get("killed_after_ready"):
            r["killed_after_ready"] = {"exe": _readlink(f"/proc/{proc.pid}/exe"), "t": round(now - T["spawn"], 3),
                                       "target": o["kill_signal_target"]}
            _kill(proc.pid, group=o["kill_signal_target"] == "group")
            hard_stop = now + 10
        if hard_stop and now >= hard_stop:
            r["streams_abandoned"] = True
            break
        wait = min(o["sample_interval"], max(0.0, deadline - now))
        if kill_at:
            wait = min(wait, max(0.0, kill_at - now))
        for key, _ in sel.select(max(wait, 0.01)):
            data = os.read(key.fd, 65536)
            if not data:
                sel.unregister(key.fileobj)
                open_streams -= 1
            else:
                key.data.feed(data)
        if con.t_ready and not seen_ready:
            seen_ready, T["ready"] = True, con.t_ready
            r["vmm_at_ready"] = vmm_snapshot(proc.pid)
            cgl = r["vmm_at_ready"].get("cgroup", "")
            if cgl.startswith("0::/"):
                ctx["cgroup"] = os.path.join(config.paths()["cg_root"], cgl[4:])
            r["cgroup"] = ctx["cgroup"]
            r["cgroup_at_ready"] = cg_read(ctx["cgroup"])
            r["vmm_exe_sha256_at_ready"] = exe_sha256(proc.pid)
            r["vmm_exe_matches_pin"] = r["vmm_exe_sha256_at_ready"] == ctx["pins"]["firecracker"]["sha256"]
            if o["on_ready"]:
                o["on_ready"](ctx)
            if o["kill_after_ready"] is not None:
                kill_at = time.monotonic() + o["kill_after_ready"]
        if con.t_done and "done" not in T:
            T["done"] = con.t_done
        if o["sampler"] and time.monotonic() >= next_sample:
            next_sample = time.monotonic() + o["sample_interval"]
            o["sampler"](ctx, time.monotonic())
    sel.close()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        _kill(proc.pid, group=True)
        proc.wait(timeout=10)
    T["exit"] = time.monotonic()
    proc.stdout.close()
    proc.stderr.close()
    r["vmm_exit_code"] = proc.returncode
    r["ready"], r["done"], r["nonce"], r["guest_done_status"] = bool(con.t_ready), bool(con.t_done), con.nonce, con.done_status
    r["console"], r["vmm_stderr"] = con.summary(), err.summary()
    if ctx.get("cgroup"):
        r["cgroup_after_exit"] = cg_read(ctx["cgroup"])
    if o["after_exit"]:
        o["after_exit"](ctx)
    root = ctx["chroot"]
    # TOCTOU: out.img is owned by the VM uid; make sure nothing with that uid can still write it while we read.
    for _ in range(50):
        stray = procs_with_uids(ctx["uid"], ctx["uid"])
        if not stray:
            break
        r.setdefault("stray_before_result", [list(x) for x in stray])
        for pid, _, _ in stray:
            kill_if_uid_in(pid, ctx["uid"], ctx["uid"])
        time.sleep(0.1)
    try:
        if procs_with_uids(ctx["uid"], ctx["uid"]):
            raise ValueError("processes with the VM uid still alive; result not read")
        res = read_result(f"{root}/out.img", o["outcap"], o["errcap"])
        r["result_status"] = "OK"
        r["result_parsed"] = res["header"]
        r["stdout"] = res["stdout"].decode("utf-8", "replace")
        r["stdout_sha256"] = hashlib.sha256(res["stdout"]).hexdigest()
        r["stderr"] = res["stderr"].decode("utf-8", "replace")
    except (OSError, ValueError) as e:
        r["result_status"] = f"MALFORMED_OR_ABSENT: {e}"[:500]
    try:
        r["in_img_unchanged"] = util.sha256_file(f"{root}/in.img")[0] == r["in_img_sha256"]
    except OSError as e:
        r["in_img_unchanged"] = False
        r["in_img_error"] = str(e)


def _readlink(p):
    try:
        return os.readlink(p)
    except OSError as e:
        return f"<{e.strerror}>"


def _kill(pid, group):
    try:
        if group:
            os.killpg(pid, signal.SIGKILL)  # pgid == pid (start_new_session)
        else:
            os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def cleanup(ctx, p=None):
    """Always runs. Kill, wait, remove cgroup (only once cgroup.procs is empty), remove chroot,
    release the uid lease; report anything left."""
    p = p or config.paths()
    rep, left = {}, []
    proc = ctx.get("proc")
    if proc and proc.poll() is None:  # never signal a pid/pgid that was already reaped (could be recycled)
        _kill(proc.pid, group=True)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            left.append(f"pid {proc.pid} did not exit after SIGKILL")
    uid = ctx.get("uid")
    if uid is not None:
        for _ in range(50):
            stray = procs_with_uids(uid, uid)
            if not stray:
                break
            for pid, _, _ in stray:
                kill_if_uid_in(pid, uid, uid)
            time.sleep(0.1)
        rep["stray_procs_killed"] = [list(s) for s in stray] if stray else []
        if procs_with_uids(uid, uid):
            left.append(f"processes with uid {uid} remain")
    cg = ctx.get("cgroup")
    if cg and os.path.isdir(cg):
        if not os.path.realpath(cg).startswith(os.path.realpath(p["cg_parent"]) + "/"):
            left.append(f"cgroup {cg} outside parent; not removed")
        else:
            empty = False
            for _ in range(100):
                if not util.read_bounded(os.path.join(cg, "cgroup.procs"), 65536).split():
                    empty = True
                    break
                time.sleep(0.05)
            rep["cgroup_procs_empty"] = empty
            if empty:
                for _ in range(20):
                    try:
                        os.rmdir(cg)
                        break
                    except OSError as e:
                        if e.errno != errno.EBUSY:
                            left.append(f"rmdir {cg}: {e.strerror}")
                            break
                        time.sleep(0.05)
            if os.path.isdir(cg):
                left.append(f"cgroup {cg} still present")
    rep["cgroup_removed"] = bool(cg) and not os.path.exists(cg)
    if ctx.get("id"):
        id_dir = os.path.join(p["chroot_base"], os.path.basename(p["fc"]), ctx["id"])
        mnts = mounts_under(id_dir)
        rep["mounts_under_chroot"] = mnts
        if mnts:
            left.append(f"mounts remain under {id_dir}: {mnts[:5]}")
        elif os.path.lexists(id_dir):
            try:
                safe_rmtree(id_dir, p["chroot_base"])
            except (OSError, Refused) as e:
                left.append(f"chroot removal failed: {e}")
        rep["chroot_removed"] = not os.path.lexists(id_dir)
        if not rep["chroot_removed"]:
            left.append(f"chroot {id_dir} still present")
    if uid is not None and not left:
        try:
            os.unlink(os.path.join(p["run"], "leases", str(uid)))
            rep["lease_released"] = True
        except FileNotFoundError:
            rep["lease_released"] = False
    rep["leftovers"] = left
    return rep
