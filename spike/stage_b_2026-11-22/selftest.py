#!/usr/bin/env python3
"""Unit self-tests that need no KVM: bounded reader, length-prefix codec and result parser, the guest init's
shell wire-format functions (run with bash on regular files), prereq on fake paths (env overrides), the
admission 503 rule, recover.py on a temp tree, the post-copy hash refusal, flag evaluation, argv building.
Usage: python3 -I -B selftest.py   (exit 0 only if every case passes)"""
import contextlib
import hashlib
import io
import json
import os
import random
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import traceback

BUNDLE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BUNDLE)
sys.path.append(os.path.join(BUNDLE, "tests"))
import admission  # noqa: E402
import config  # noqa: E402
import fclib  # noqa: E402
import prereq  # noqa: E402
import recover  # noqa: E402
import util  # noqa: E402

RESULTS = []
TMP = tempfile.mkdtemp(prefix="plea-selftest-")


def case(fn):
    try:
        note = fn()
        RESULTS.append((fn.__name__, "PASS", note or ""))
    except Exception as e:  # noqa: BLE001
        RESULTS.append((fn.__name__, "FAIL", f"{type(e).__name__}: {e} | {traceback.format_exc(limit=3)[-600:]}"))
    return fn


@contextlib.contextmanager
def env(**kv):
    old = {k: os.environ.get(k) for k in kv}
    os.environ.update({k: str(v) for k, v in kv.items()})
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def write(path, data, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data if isinstance(data, bytes) else data.encode())
    os.chmod(path, mode)
    return path


# ------------------------------------------------------------------ bounded reader
@case
def bounded_reader_head_tail_dropped():
    data = random.Random(1).randbytes(1 << 20)
    br, i, rnd = fclib.BoundedReader(65536, 65536), 0, random.Random(2)
    while i < len(data):
        n = rnd.randint(1, 70000)
        br.feed(data[i:i + n])
        i += n
    assert bytes(br.head) == data[:65536] and bytes(br.tail) == data[-65536:]
    assert br.total == len(data) and br.dropped == len(data) - 131072
    small = fclib.BoundedReader(100, 100)
    small.feed(b"x" * 150)
    assert len(small.head) == 100 and len(small.tail) == 50 and small.dropped == 0
    return f"1 MiB in random chunks: kept {len(br.head)}+{len(br.tail)}, dropped {br.dropped}"


@case
def bounded_reader_markers_and_forgery():
    n = b"0123456789abcdef"
    stream = (b"PLEA_DONE " + n + b" OK\n" + b"k" * 10000 + b"\n[ 0.1] x PLEA_READY " + n + b"\r\n"
              + b"PLEA_READY ffffffffffffffff\n" + b"PLEA_DONE ffffffffffffffff OK\n" + b"y" * 5000
              + b"PLEA_DONE " + n + b" OK\n")
    br = fclib.BoundedReader(16, 16, markers=True)
    for i in range(len(stream)):
        br.feed(stream[i:i + 1])  # one byte at a time: markers split across reads
    assert br.nonce == n.decode() and br.done_status == "OK", (br.nonce, br.done_status)
    assert br.ignored_markers == 3, br.ignored_markers
    assert len(br.head) == 16 and len(br.tail) == 16
    return "pre-READY DONE, second READY and wrong-nonce DONE ignored; DONE after a 5000-byte unterminated line found"


# ------------------------------------------------------------------ codec / parser
@case
def lp_codec():
    for body in (b"", b"a", os.urandom(5000)):
        assert fclib.lp_decode(fclib.lp_encode(body, 10000), 10000) == body
    bad = [(b"\x00" * 7, "short"), (struct.pack(">Q", 11) + b"x" * 11, "over cap"),
           (struct.pack(">Q", 5) + b"abc", "beyond buffer"), (b"\x80" + bytes(7) + b"x", "top bit / huge")]
    for buf, why in bad:
        try:
            fclib.lp_decode(buf, 10)
            raise AssertionError(f"accepted {why}")
        except ValueError:
            pass
    try:
        fclib.lp_encode(b"x" * 11, 10)
        raise AssertionError("encoded over cap")
    except ValueError:
        pass
    return "round trip ok; short/over-cap/beyond-buffer/top-bit rejected"


def _body(hdr, so=b"", se=b""):
    return json.dumps(hdr).encode() + b"\n" + so + se


@case
def result_parser_validation():
    good = {"v": 1, "status": "OK", "stdout_len": 3, "stderr_len": 2}
    r = fclib.parse_result(_body(good, b"abc", b"de"), 10, 10)
    assert r["stdout"] == b"abc" and r["stderr"] == b"de"
    cases = {"length mismatch": _body(good, b"abcX", b"de"), "over outcap": _body(dict(good, stdout_len=11), b"a" * 11, b"de"),
             "bad status": _body(dict(good, status="ok; rm"), b"abc", b"de"), "bad version": _body(dict(good, v=2), b"abc", b"de"),
             "no header": b"x" * 5000, "non-json": b"{nope\nabc"}
    for why, b in cases.items():
        try:
            fclib.parse_result(b, 10, 10)
            raise AssertionError(f"accepted: {why}")
        except (ValueError, UnicodeDecodeError):
            pass
    return f"{len(cases)} malformed results rejected"


# ------------------------------------------------------------------ guest init shell functions
def _lib():
    src = open(os.path.join(BUNDLE, "guest", "plea-init")).read()
    m = re.search(r"^# BEGIN-LIB.*?$(.*)^# END-LIB", src, re.S | re.M)
    return write(os.path.join(TMP, "initlib.sh"), m.group(1))


def _bash(script, timeout=60):
    p = subprocess.run(["bash", "-c", f"source {_lib()}\n{script}"], capture_output=True, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


@case
def guest_init_extract_payload():
    payload = os.urandom(70000)
    img = fclib.lp_encode(payload, 1 << 20)
    img += bytes(-len(img) % 4096)
    f = write(os.path.join(TMP, "in_ok.img"), img)
    rc, out, err = _bash(f'extract_payload {f} {len(img)} 1048576 {TMP}/job.out; echo "rc=$? plen=$PLEN"')
    assert out.strip() == "rc=0 plen=70000", (out, err)
    assert open(f"{TMP}/job.out", "rb").read() == payload
    bad = {"top_bit": b"\x80" + bytes(7) + payload, "over_cap": struct.pack(">Q", (1 << 20) + 1) + payload,
           "beyond_device": struct.pack(">Q", 100000) + payload[:100], "zero": struct.pack(">Q", 0) + payload,
           "short": b"\x00\x00\x01"}
    for name, raw in bad.items():
        raw2 = raw + (bytes(-len(raw) % 4096) if name != "short" else b"")
        g = write(os.path.join(TMP, f"in_{name}.img"), raw2)
        rc, out, err = _bash(f'extract_payload {g} {len(raw2)} 1048576 {TMP}/bad.out; echo "rc=$?"')
        assert out.strip() == "rc=2", (name, out, err)
    return "valid 70000-byte payload extracted byte-exact; 5 malformed prefixes -> rc=2 (REJECT_LEN)"


@case
def guest_init_write_result_roundtrip():
    so, se = os.urandom(3000), b"guest_python 3.12.3\n"
    write(f"{TMP}/so", so)
    write(f"{TMP}/se", se)
    hdr_cmd = (f'H=$(mkhdr 0123456789abcdef OK 0 77 {"a" * 64} {len(so)} false {len(se)} none -1 -1 vda,vdb,vdc 10001 1234)')
    out_img = f"{TMP}/out.img"
    with open(out_img, "wb") as fh:
        fh.truncate(16384)
    rc, out, err = _bash(f'{hdr_cmd}\nwrite_result {out_img} 16384 "$H" {TMP}/so {TMP}/se {TMP}; echo "rc=$?"')
    assert out.strip().endswith("rc=0"), (out, err)
    r = fclib.read_result(out_img, 4096, 4096)
    assert r["stdout"] == so and r["stderr"] == se and r["header"]["payload_len"] == 77
    assert r["header"]["stdout_truncated"] is False and r["header"]["devs"] == "vda,vdb,vdc"
    with open(f"{TMP}/small.img", "wb") as fh:
        fh.truncate(1024)
    rc, out, err = _bash(f'{hdr_cmd}\nwrite_result {TMP}/small.img 1024 "$H" {TMP}/so {TMP}/se {TMP}; echo "rc=$?"')
    assert out.strip().endswith("rc=1"), out
    rc, out, err = _bash("be64 1099511627781 | od -An -tx1")
    assert out.split() == ["00", "00", "01", "00", "00", "00", "00", "05"], out
    return "bash write_result -> Python read_result round trip exact; oversize result refused; be64 correct"


@case
def guest_init_syntax():
    p = subprocess.run(["bash", "-n", os.path.join(BUNDLE, "guest", "plea-init")], capture_output=True, timeout=30)
    assert p.returncode == 0, p.stderr
    return "bash -n ok"


# ------------------------------------------------------------------ prereq on fake paths
def _fake_host():
    d = os.path.join(TMP, "fake")
    elf = b"\x7fELF" + os.urandom(4000)
    fc, jl = write(f"{d}/bin/firecracker", elf, 0o755), write(f"{d}/bin/jailer", elf + b"j", 0o755)
    kern, rootfs = write(f"{d}/img/vmlinux", b"\x7fELF" + os.urandom(9000), 0o444), write(f"{d}/img/rootfs.ext4", os.urandom(8192), 0o444)
    sc = write(f"{d}/share/seccomp.json", b"{}", 0o644)
    files = {}
    for k, pth in (("firecracker", fc), ("jailer", jl), ("seccomp_json", sc), ("kernel", kern), ("squashfs", sc), ("rootfs", rootfs)):
        h, n = util.sha256_file(pth)
        files[k] = {"path": pth, "sha256": h, "size": n}
    pins = write(f"{d}/pins.json", json.dumps({"version": 1, "files": files}))
    cg = f"{d}/cg"
    for n, v in (("cgroup.controllers", "cpu memory pids io\n"), ("cgroup.subtree_control", "cpu memory pids\n")):
        write(f"{cg}/{n}", v)
    for n, v in (("cgroup.controllers", "cpu memory\n"), ("cgroup.subtree_control", "cpu memory\n"), ("cgroup.procs", "")):
        write(f"{cg}/plea-spike/{n}", v)
    os.makedirs(f"{d}/chroot", exist_ok=True)
    write(f"{d}/swaps", "Filename\tType\tSize\tUsed\tPriority\n")
    write(f"{d}/meminfo", "MemTotal: 8000000 kB\nMemAvailable: 6000000 kB\n")
    write(f"{d}/kvm", b"")
    e = dict(PLEA_KVM_PATH=f"{d}/kvm", PLEA_FC_BIN=fc, PLEA_JAILER_BIN=jl, PLEA_KERNEL_PATH=kern, PLEA_ROOTFS_PATH=rootfs,
             PLEA_PINS_PATH=pins, PLEA_CGROUP_ROOT=cg, PLEA_CGROUP_PARENT=f"{cg}/plea-spike", PLEA_CHROOT_BASE=f"{d}/chroot",
             PLEA_SWAPS=f"{d}/swaps", PLEA_MEMINFO=f"{d}/meminfo", PLEA_MIN_DISK_MIB=1, PLEA_BUNDLE_DIR=f"{d}/bin")
    return d, e, files


def _status(r):
    return {c["id"]: c["met"] for c in r["checks"]}


@case
def prereq_on_fake_paths():
    d, e, files = _fake_host()
    real_pp, real_rel = util.path_problems, dict(config.RELEASE["inner"])
    anchor = d.rstrip("/") + "/"
    # Treat the temp dir as the trusted anchor (its /tmp parents are 1777 and would rightly fail).
    prereq.util.path_problems = lambda p: [x for x in real_pp(p) if x.startswith(anchor)] if p.startswith(anchor) else real_pp(p)
    config.RELEASE["inner"].update({"firecracker-v1.18.0-x86_64": files["firecracker"]["sha256"],
                                    "jailer-v1.18.0-x86_64": files["jailer"]["sha256"],
                                    "seccomp-filter-v1.18.0-x86_64.json": files["seccomp_json"]["sha256"]})
    try:
        with env(**e):
            s = _status(prereq.check_all(True))
            want = {"P01": False, "P02": False, "P03": False, "P04": False, "P05": True, "P06": True, "P07": True,
                    "P08": True, "P09": True, "P10": True, "P11": True, "P12": True, "P13": True}
            assert s == want, s
            with open(e["PLEA_KERNEL_PATH"], "r+b") as f:  # tamper (same size)
                f.seek(100)
                f.write(b"\x00")
            assert _status(prereq.check_all(True))["P07"] is False
            assert _status(prereq.check_all(False))["P07"] is True  # size-only check; fclib's post-copy hash is binding
            with env(PLEA_JAILER_BIN=f"{d}/bin/missing", PLEA_MIN_MEM_MIB=100000):
                s2 = _status(prereq.check_all(True))
                assert s2["P06"] is False and s2["P11"] is False
            write(e["PLEA_SWAPS"], "Filename\tType\n/swapfile file 1 0 -2\n")
            assert _status(prereq.check_all(True))["P10"] is False
            os.chmod(e["PLEA_PINS_PATH"], 0o666)
            assert _status(prereq.check_all(True))["P05"] is False
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                assert prereq.main() == 1
    finally:
        prereq.util.path_problems = real_pp
        config.RELEASE["inner"].clear()
        config.RELEASE["inner"].update(real_rel)
    assert util.path_problems("/usr/bin") == []
    pp = util.path_problems(TMP)
    assert any("/tmp" in x and "writable" in x for x in pp), pp
    return ("fake host: KVM(regular file)/cgroup(not cgroup2)/parent(no pids) NOT MET, pinned files MET; tamper, "
            "missing jailer, low memory, swap on, writable pins each flip their check to NOT MET; prereq.main exit 1")


@case
def prereq_on_this_build_host():
    if os.path.exists("/dev/kvm"):
        return "skipped: /dev/kvm exists here"
    r = prereq.check_all(True)
    s = _status(r)
    assert r["all_met"] is False and s["P01"] is False and s["P02"] is False
    return "real prereq here (no /dev/kvm): NOT MET -> " + ", ".join(r["not_met"])


@case
def run_vm_refuses_when_prereq_not_met():
    if os.path.exists("/dev/kvm") or prereq.check_all(False)["all_met"]:
        return "skipped: prerequisites could be MET here; selftest never launches a VM"
    r = fclib.run_vm(b"print(1)", label="selftest")
    assert r["spawned"] is False and r["refused"] and "NOT MET" in r["refused"] and r["ok"] is False
    assert r.get("vm_id") is None and "cleanup" not in r
    return "run_vm refused before allocating a uid or chroot: " + r["refused"][:120]


# ------------------------------------------------------------------ admission
def _snap(p):
    st = os.stat(p)
    return open(p, "rb").read(), st.st_mtime_ns, st.st_ino


@case
def admission_503_rule():
    b = write(os.path.join(TMP, "budget"), "5\n")
    real = admission.check
    try:
        admission.check = lambda hash_images=False: {"all_met": False, "not_met": ["P01:kvm_char_device"]}
        s0 = _snap(b)
        code, body = admission.admit(b)
        assert code == 503 and body["error"] == "ISOLATION_UNAVAILABLE" and _snap(b) == s0
        admission.check = lambda hash_images=False: {"all_met": True, "not_met": []}
        code, body = admission.admit(b)
        assert code == 200 and open(b).read() == "4\n" and body["budget_after"] == 4
        write(b, "0\n")
        s0 = _snap(b)
        assert admission.admit(b)[0] == 429 and _snap(b) == s0
        write(b, "abc\n")
        s0 = _snap(b)
        assert admission.admit(b)[0] == 500 and _snap(b) == s0
    finally:
        admission.check = real
    write(b, "7\n")
    if not os.path.exists("/dev/kvm"):
        s0 = _snap(b)
        assert admission.admit(b)[0] == 503 and _snap(b) == s0
    return "NOT MET -> 503 with budget bytes/mtime/inode unchanged; MET -> 200 and 5->4; 0 -> 429 unchanged; corrupt -> 500 unchanged"


# ------------------------------------------------------------------ recover on a temp tree
@case
def recover_temp_tree():
    d = os.path.join(TMP, "rec")
    base, cgp, run = f"{d}/chroot", f"{d}/cg/plea-spike", f"{d}/run"
    write(f"{base}/firecracker/plea-aaa/root/rootfs.ext4", b"x" * 100)
    write(f"{base}/firecracker/plea-aaa/root/dev/kvm", b"")
    os.makedirs(f"{base}/firecracker/plea-bbb/root")
    precious = write(f"{d}/outside/precious", b"keep me")
    os.symlink(f"{d}/outside", f"{base}/firecracker/plea-link")
    write(f"{cgp}/plea-aaa/cgroup.procs", "")
    write(f"{run}/leases/3999990001", "plea-aaa")
    e = dict(PLEA_CHROOT_BASE=base, PLEA_CGROUP_PARENT=cgp, PLEA_RUN_DIR=run, PLEA_UID_MIN=3999990000, PLEA_UID_MAX=3999990010)
    real = recover.rmdir_cgroup

    def fake_rmdir(p):  # real cgroup dirs hold only virtual files; the fake one holds a regular file
        os.unlink(os.path.join(p, "cgroup.procs"))
        os.rmdir(p)
    try:
        with env(**e):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = recover.main([])
            dry = json.loads(buf.getvalue())
            assert rc == 1 and dry["actions"] == [] and dry["found_count"] >= 5, dry["found_count"]
            assert os.path.exists(f"{base}/firecracker/plea-aaa/root/rootfs.ext4") and os.path.isdir(f"{cgp}/plea-aaa")
            recover.rmdir_cgroup = fake_rmdir
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = recover.main(["--apply"])
            app = json.loads(buf.getvalue())
    finally:
        recover.rmdir_cgroup = real
    assert rc == 0 and app["remaining_count"] == 0, app
    assert not os.listdir(f"{base}/firecracker") and not os.listdir(cgp) and not os.listdir(f"{run}/leases")
    assert open(precious, "rb").read() == b"keep me", "symlink target was touched"
    return f"dry-run found {dry['found_count']} items and changed nothing; --apply removed all; symlink target intact"


# ------------------------------------------------------------------ TOCTOU copy, rmtree safety
@case
def place_file_post_copy_hash():
    src = os.path.join(TMP, "src.img")
    data = os.urandom(4096) + bytes(3 << 20) + os.urandom(4096)
    write(src, data)
    pin = hashlib.sha256(data).hexdigest()
    os.makedirs(f"{TMP}/chroot1", exist_ok=True)
    rep = fclib.place_file(src, f"{TMP}/chroot1/a", pin, 0o444)
    st = os.stat(f"{TMP}/chroot1/a")
    assert rep["copy_sha256"] == pin and oct(st.st_mode & 0o777) == "0o444" and st.st_blocks * 512 < len(data)
    with open(src, "r+b") as f:
        f.seek(len(data) - 1)
        f.write(b"\x00" if data[-1] else b"\x01")
    try:
        fclib.place_file(src, f"{TMP}/chroot1/b", pin, 0o444)
        raise AssertionError("tampered source accepted")
    except fclib.Refused as e:
        assert "post-copy hash differs from pin" in str(e)
    try:
        fclib.place_file(src, f"{TMP}/chroot1/a", pin, 0o444)
        raise AssertionError("overwrote an existing file")
    except FileExistsError:
        pass
    return f"sparse copy ok ({st.st_blocks * 512} of {len(data)} bytes allocated); tampered source refused; O_EXCL enforced"


@case
def safe_rmtree_refusals():
    base = os.path.join(TMP, "rmbase")
    os.makedirs(f"{base}/x/y")
    os.makedirs(f"{TMP}/rmoutside")
    os.symlink(f"{TMP}/rmoutside", f"{base}/link")
    for bad in (f"{TMP}/rmoutside", f"{base}/link", base):
        try:
            fclib.safe_rmtree(bad, base)
            raise AssertionError(f"removed {bad}")
        except fclib.Refused:
            pass
    fclib.safe_rmtree(f"{base}/x", base)
    assert not os.path.exists(f"{base}/x") and os.path.isdir(f"{TMP}/rmoutside")
    return "outside path, symlink and the base itself refused; inner dir removed"


@case
def pidfd_guarded_kill():
    me = os.getuid()
    proc = subprocess.Popen(["sleep", "30"])
    try:
        assert fclib.kill_if_uid_in(proc.pid, me + 1, me + 1) == "uid not in range: not killed"
        assert proc.poll() is None
        assert fclib.kill_if_uid_in(proc.pid, me, me) == "killed"
        proc.wait(timeout=10)
        assert proc.returncode == -9
        assert fclib.kill_if_uid_in(proc.pid, me, me) == "gone"
    finally:
        if proc.poll() is None:
            proc.kill()
    return "pid outside the uid range untouched; in range killed via pidfd; reaped pid -> gone"


# ------------------------------------------------------------------ flags / argv / boot args
JH = ("Usage: jailer --id <id> --exec-file <exec-file> --uid <uid> --gid <gid>\n  --chroot-base-dir <dir>\n"
      "  --cgroup <cgroup>\n  --cgroup-version <v>\n  --parent-cgroup <p>\n  --resource-limit <r>\n")
FH = "  --config-file <f>\n  --no-api\n  --api-sock <s>\n"


@case
def flag_evaluation():
    assert fclib.evaluate_flags(JH, "Jailer v1.18.0", FH, "Firecracker v1.18.0")["met"]
    r = fclib.evaluate_flags(JH.replace("  --cgroup <cgroup>\n", ""), "Jailer v1.18.0", FH, "Firecracker v1.18.0")
    assert not r["met"] and r["missing"] == ["--cgroup"], r
    r = fclib.evaluate_flags(JH.replace("--parent-cgroup", "--parent"), "v1.18.0", FH, "v1.18.0")
    assert not r["met"] and "--parent-cgroup" in r["missing"]
    assert not fclib.evaluate_flags(JH, "Jailer v1.12.1", FH, "Firecracker v1.18.0")["met"]
    r = fclib.evaluate_flags(JH, "v1.18.0", "  --config-file <f>\n  --api-sock <s>\n", "v1.18.0")
    assert r["met"] and r["mode"] == "api-sock-in-chroot"
    assert not fclib.evaluate_flags(JH, "v1.18.0", "  --no-api\n", "v1.18.0")["met"]
    return "missing --cgroup (with --cgroup-version present), missing --parent-cgroup, wrong version, no --config-file -> NOT MET"


@case
def jailer_argv_and_boot_args():
    o = fclib.opts_defaults()
    p = config.paths()
    argv = fclib.jailer_argv(p, o, "plea-0123456789ab", 64001, {"mode": "no-api"})
    s = " ".join(argv)
    for frag in ("--id plea-0123456789ab", "--uid 64001", "--gid 64001", "--chroot-base-dir /srv/plea-jailer",
                 "--cgroup-version 2", "--parent-cgroup plea-spike", "--cgroup cpu.max=100000",
                 f"--cgroup memory.max={(128 + 192) << 20}", "--cgroup memory.swap.max=0", "--cgroup pids.max=64",
                 f"--resource-limit fsize={16 << 20}", "--resource-limit no-file=1024", "-- --config-file /vm.json --no-api"):
        assert frag in s, frag
    assert "--no-seccomp" not in argv and argv[0] == "/opt/plea-fc/bin/jailer"
    ba = fclib.boot_args(o, "a" * 64)
    assert len(ba) < 2048 and "init=/plea-init" in ba and "reboot=k panic=1 pci=off" in ba and "console=ttyS0" in ba
    return f"argv has every declared flag; boot args {len(ba)} chars"


# ------------------------------------------------------------------ workloads, declaration, misc
@case
def workloads_compile_and_verify_is_deterministic():
    import py_compile
    for f in sorted(os.listdir(os.path.join(BUNDLE, "workloads"))):
        py_compile.compile(os.path.join(BUNDLE, "workloads", f), cfile=os.path.join(TMP, f + "c"), doraise=True)
    import common
    pl = common.payload("w_verify")
    f = write(os.path.join(TMP, "wv.py"), pl)
    outs = {subprocess.run([sys.executable, "-I", "-S", f], capture_output=True, timeout=120).stdout for _ in range(2)}
    assert len(outs) == 1 and json.loads(outs.pop())["json_roundtrip_ok"] is True
    return "all workloads compile; w_verify stdout identical across runs"


@case
def declaration_covers_every_predicate_id():
    decl = open(os.path.join(BUNDLE, "DECLARATION.md")).read()
    used = set()
    for f in os.listdir(os.path.join(BUNDLE, "tests")):
        if f.endswith(".py"):
            used |= set(re.findall(r'"(T\d\d(?:pre|post)?(?:\.[A-Za-z0-9_]+)?\.P\d+)"', open(os.path.join(BUNDLE, "tests", f)).read()))
    used |= {f"T06.{j}.P{n}" for j in ("cpu", "mem", "fork", "fd") for n in range(1, 5)}
    used |= {f"T10.k{k}.P{n}" for k in (2, 4, 8) for n in range(0, 6)}
    used |= {f"T11.{c}.P{n}" for c in "ABC" for n in range(1, 7)} | {"T11.C.P0"}
    used |= {f"T13.P{n}" for n in range(0, 7)} | {f"T14.P{n}" for n in range(1, 8)}
    missing = sorted(i for i in used if i not in decl)
    assert not missing, missing
    return f"{len(used)} predicate ids, all present in DECLARATION.md"


@case
def tar_data_filter_rejects_traversal():
    t = os.path.join(TMP, "evil.tgz")
    with tarfile.open(t, "w:gz") as tf:
        ti = tarfile.TarInfo("../evil")
        ti.size = 1
        tf.addfile(ti, io.BytesIO(b"x"))
    os.makedirs(f"{TMP}/tx")
    try:
        with tarfile.open(t) as tf:
            tf.extractall(f"{TMP}/tx", filter="data")
        raise AssertionError("traversal extracted")
    except tarfile.FilterError:
        pass
    assert not os.path.exists(os.path.join(TMP, "evil"))
    return "tarfile filter='data' (used by fetch.py) rejects '../' members"


@case
def resolve_in_tree_no_escape():
    import fetch
    tree = os.path.join(TMP, "tree")
    write(f"{tree}/usr/bin/python3.12", b"\x7fELF")
    os.symlink("python3.12", f"{tree}/usr/bin/python3")
    os.symlink("/usr/bin/python3", f"{tree}/usr/bin/abs")
    os.symlink("../../../../../../etc/passwd", f"{tree}/usr/bin/escape")
    assert fetch.resolve_in_tree(tree, "usr/bin/python3") == f"{tree}/usr/bin/python3.12"
    assert fetch.resolve_in_tree(tree, "usr/bin/abs") == f"{tree}/usr/bin/python3.12"
    assert fetch.resolve_in_tree(tree, "usr/bin/escape") is None
    return "relative and absolute symlinks resolved inside the tree; escaping link -> None"


@case
def fetch_offline_pipeline():
    """fetch.py with downloads replaced by local files: release verify/extract/install, TOFU pins, and a real
    mkfs.ext4 -d + e2fsck image build from a fake guest tree (unsquashfs replaced by a copy)."""
    if not shutil.which("mkfs.ext4") or not shutil.which("e2fsck") or os.getuid() != 0:
        return "skipped: needs root and e2fsprogs"
    import fetch
    d = os.path.join(TMP, "fetch")
    rel = f"{d}/src/release-v1.18.0-x86_64"
    blobs = {"firecracker-v1.18.0-x86_64": b"\x7fELF-fc", "jailer-v1.18.0-x86_64": b"\x7fELF-jl",
             "seccomp-filter-v1.18.0-x86_64.json": b"{}"}
    for n, b in blobs.items():
        write(f"{rel}/{n}", b, 0o755)
    sums = "".join(f"{hashlib.sha256(b).hexdigest()}  {n}\n" for n, b in blobs.items())
    write(f"{rel}/SHA256SUMS", sums)
    tgz = f"{d}/fc.tgz"
    with tarfile.open(tgz, "w:gz") as tf:
        tf.add(rel, arcname="release-v1.18.0-x86_64")
    tsha = hashlib.sha256(open(tgz, "rb").read()).hexdigest()
    write(f"{d}/side.txt", f"{tsha}  firecracker-v1.18.0-x86_64.tgz\n")
    kern = write(f"{d}/vmlinux", b"\x7fELF" + os.urandom(5000))
    tree = f"{d}/tree-src"
    for t in fetch.GUEST_TOOLS:
        write(f"{tree}/usr/bin/{t}", b"#!", 0o755)
    write(f"{tree}/usr/bin/python3.12", b"\x7fELF", 0o755)
    os.symlink("python3.12", f"{tree}/usr/bin/python3")
    for x in ("json/__init__.py", "hashlib.py", "os.py"):
        write(f"{tree}/usr/lib/python3.12/{x}", b"")
    write(f"{tree}/etc/passwd", "root:x:0:0:root:/root:/bin/bash\nubuntu:x:1000:1000::/home/ubuntu:/bin/bash\n")
    write(f"{tree}/etc/group", "root:x:0:\n")
    saved = (fetch.OPT, fetch.WORK, fetch.curl, dict(config.RELEASE), dict(config.RELEASE["inner"]), fetch.util.run)
    urls = {config.RELEASE["tgz_url"]: tgz, config.RELEASE["tgz_url"] + ".sha256.txt": f"{d}/side.txt", "K": kern}
    real_run = util.run

    def fake_run(cmd, *a, **kw):
        if cmd[0] == "unsquashfs":
            shutil.copytree(tree, cmd[cmd.index("-d") + 1], symlinks=True)
            return {"cmd": cmd, "rc": 0, "stdout": "", "stderr": ""}
        return real_run(cmd, *a, **kw)
    try:
        fetch.OPT, fetch.WORK = f"{d}/opt", f"{d}/opt/work"
        os.makedirs(fetch.WORK)
        fetch.curl = lambda url, dest, cap, max_time=0: (shutil.copyfile(urls[url], dest), os.path.getsize(dest))[1]
        fetch.util.run = fake_run
        config.RELEASE.update(tgz_size=os.path.getsize(tgz), tgz_sha256=tsha)
        config.RELEASE["inner"].update({n: hashlib.sha256(b).hexdigest() for n, b in blobs.items()})
        with contextlib.redirect_stdout(io.StringIO()):
            files = fetch.release()
            st = os.stat(f"{d}/opt/bin/jailer")
            assert files["jailer"]["sha256"] == hashlib.sha256(blobs["jailer-v1.18.0-x86_64"]).hexdigest()
            assert st.st_uid == 0 and oct(st.st_mode & 0o777) == "0o755"
            k = fetch.tofu("kernel", "K", "vmlinux-x", 1 << 20, b"\x7fELF", {})
            try:
                fetch.tofu("kernel", "K", "vmlinux-x", 1 << 20, b"\x7fELF", {"kernel": {"sha256": "0" * 64}})
                raise AssertionError("TOFU pin mismatch accepted")
            except fetch.NotMet:
                pass
            rp = fetch.build_rootfs(f"{d}/dummy.squashfs", {}, False)
            img = f"{d}/opt/images/rootfs.ext4"
            assert util.sha256_file(img)[0] == rp["sha256"] and oct(os.stat(img).st_mode & 0o777) == "0o444"
            assert fetch.build_rootfs(f"{d}/dummy.squashfs", {"rootfs": rp}, False) == rp  # existing, verified
            with open(img, "r+b") as f:
                f.seek(5000)
                f.write(b"\x01")
            try:
                fetch.build_rootfs(f"{d}/dummy.squashfs", {"rootfs": rp}, False)
                raise AssertionError("tampered rootfs accepted")
            except fetch.NotMet:
                pass
            os.unlink(f"{tree}/usr/lib/python3.12/json/__init__.py")
            try:
                fetch.build_rootfs(f"{d}/dummy.squashfs", {}, True)
                raise AssertionError("missing guest stdlib not BLOCKED")
            except fetch.Blocked:
                pass
            with open(f"{rel}/jailer-v1.18.0-x86_64", "ab") as f:
                f.write(b"x")
            os.unlink(tgz)
            with tarfile.open(tgz, "w:gz") as tf:
                tf.add(rel, arcname="release-v1.18.0-x86_64")
            config.RELEASE.update(tgz_size=os.path.getsize(tgz), tgz_sha256=hashlib.sha256(open(tgz, "rb").read()).hexdigest())
            write(f"{d}/side.txt", config.RELEASE["tgz_sha256"] + "\n")
            try:
                fetch.release()
                raise AssertionError("inner checksum mismatch accepted")
            except fetch.NotMet:
                pass
    finally:
        fetch.OPT, fetch.WORK, fetch.curl = saved[0], saved[1], saved[2]
        fetch.util.run = saved[5]
        config.RELEASE.clear()
        config.RELEASE.update(saved[3])
        config.RELEASE["inner"] = saved[4]
    return (f"release verify+extract+install ok; TOFU mismatch NOT MET; real mkfs.ext4 -d image {rp['size']} bytes "
            "+ e2fsck clean, pinned 0444; tampered image NOT MET; missing guest stdlib BLOCKED; inner mismatch NOT MET")


@case
def pctl_nearest_rank():
    r = util.pctl(list(range(1, 21)))
    assert r == {"n": 20, "min": 1, "median": 10.5, "p95": 19, "max": 20}, r
    return str(r)


@case
def evidence_writer_bounds():
    import common
    with env(PLEA_EVIDENCE=os.path.join(TMP, "ev")):
        t = common.Test("TXX", "selftest", allow_overrides=True)
        t.data["big"] = "x" * (common.EVIDENCE_MAX + 10)
        with contextlib.redirect_stdout(io.StringIO()):
            t.pred("TXX.P1", "dummy", True)
            rc = t.write()
    size = os.path.getsize(os.path.join(TMP, "ev", "TXX.json"))
    d = json.load(open(os.path.join(TMP, "ev", "TXX.json")))
    assert rc == 0 and size < 1 << 20 and "truncated" in d["note"] and d["verdict"] == "MET"
    return f"oversized evidence truncated to {size} bytes, predicates kept"


def main():
    print(f"selftest on {os.uname().sysname} {os.uname().release}, python {sys.version.split()[0]}, uid {os.getuid()}, "
          f"/dev/kvm present: {os.path.exists('/dev/kvm')}")
    for name, st, note in RESULTS:
        print(f"{st} {name}: {note}")
    fails = sum(1 for _, st, _ in RESULTS if st != "PASS")
    print(f"{len(RESULTS) - fails}/{len(RESULTS)} passed")
    shutil.rmtree(TMP, ignore_errors=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
