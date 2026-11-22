#!/usr/bin/env python3
"""Stage 1: download + verify Firecracker v1.18.0, fetch the CI guest kernel/rootfs (TOFU pins),
build the read-only guest image. CHANGES THE HOST: writes /opt/plea-fc/{bin,images,share,work,pins.json}.

Usage: python3 -I -B fetch.py [--kernel 6.1|6.18] [--rebuild-rootfs]
Exit 0 = all verified; 1 = verification NOT MET; 3 = BLOCKED (state/BLOCKED written).
"""
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tarfile
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402
import util  # noqa: E402

OPT = "/opt/plea-fc"
WORK = f"{OPT}/work"
GUEST_TOOLS = ("bash", "mount", "dd", "od", "sha256sum", "head", "timeout", "setpriv", "stat", "cut",
               "sync", "cat", "tr", "blockdev", "mkdir", "chmod", "sleep", "mkfifo", "ls", "mv")
EV = {"utc_start": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "steps": []}


class NotMet(Exception):
    pass


class Blocked(Exception):
    pass


def step(name, **kv):
    EV["steps"].append(dict(step=name, t=round(time.time(), 3), **kv))
    print(f"[stage1] {name} {json.dumps(kv)[:300]}", flush=True)


def fresh_dir(path):
    if os.path.lexists(path):
        shutil.rmtree(path)
    os.makedirs(path, mode=0o700)
    return path


def curl(url, dest, max_bytes, max_time=1800):
    r = util.run(["curl", "-fsSL", "--proto", "=https", "--tlsv1.2", "--retry", "3", "--connect-timeout", "20",
                  "--max-time", str(max_time), "--max-filesize", str(max_bytes), "-o", dest, url],
                 timeout=max_time + 60)
    if r["rc"] != 0:
        raise NotMet(f"download failed {url}: rc={r['rc']} {r['stderr'][:300]}")
    size = os.lstat(dest).st_size
    if size > max_bytes:
        raise NotMet(f"{url}: {size} bytes > cap {max_bytes}")
    return size


def install(src, dst, mode):
    tmp = dst + ".tmp"
    if os.path.lexists(tmp):
        os.unlink(tmp)
    shutil.copyfile(src, tmp, follow_symlinks=False)
    os.chown(tmp, 0, 0)
    os.chmod(tmp, mode)
    os.replace(tmp, dst)
    return util.sha256_file(dst)


def release():
    R = config.RELEASE
    d = fresh_dir(f"{WORK}/release")
    tgz = f"{d}/fc.tgz"
    size = curl(R["tgz_url"], tgz, R["tgz_size"] + 1)
    sha, _ = util.sha256_file(tgz)
    step("release_tgz", size=size, sha256=sha, expected_size=R["tgz_size"], expected_sha256=R["tgz_sha256"])
    if size != R["tgz_size"] or sha != R["tgz_sha256"]:
        raise NotMet("release tarball size/sha256 mismatch")
    side = f"{d}/sha256.txt"
    try:
        curl(R["tgz_url"] + ".sha256.txt", side, 4096)
        txt = util.read_bounded(side, 4096)
        step("release_sha256_txt", content=txt.strip(), lists_expected=R["tgz_sha256"] in txt)
        if R["tgz_sha256"] not in txt:
            raise NotMet("published .sha256.txt does not list the expected hash")
    except NotMet as e:
        raise NotMet(f"sha256.txt check: {e}")
    x = fresh_dir(f"{d}/x")
    with tarfile.open(tgz, "r:gz") as tf:
        names = tf.getnames()
        tf.extractall(x, filter="data")  # rejects absolute paths, '..', links escaping, device nodes
    inner = f"{x}/{R['inner_dir']}"
    sums = util.read_bounded(f"{inner}/SHA256SUMS", 65536)
    listed = {}
    for line in sums.splitlines():
        m = re.match(r"^([0-9a-f]{64})\s+\*?(\S+)$", line.strip())
        if m:
            listed[m.group(2)] = m.group(1)
    res = {}
    for name, want in R["inner"].items():
        got, n = util.sha256_file(f"{inner}/{name}")
        res[name] = {"expected": want, "listed_in_SHA256SUMS": listed.get(name), "actual": got, "size": n}
        if not (got == want == listed.get(name)):
            step("inner_sha256", files=res, members=len(names))
            raise NotMet(f"inner checksum mismatch for {name}")
    step("inner_sha256", files=res, members=len(names), sha256sums=sums[:4000])
    for sub in ("bin", "images", "share"):
        os.makedirs(f"{OPT}/{sub}", mode=0o755, exist_ok=True)
    for dd in (OPT, f"{OPT}/bin", f"{OPT}/images", f"{OPT}/share"):
        os.chown(dd, 0, 0)
        os.chmod(dd, 0o755)
    fc = install(f"{inner}/firecracker-v1.18.0-x86_64", f"{OPT}/bin/firecracker", 0o755)
    jl = install(f"{inner}/jailer-v1.18.0-x86_64", f"{OPT}/bin/jailer", 0o755)
    sc = install(f"{inner}/seccomp-filter-v1.18.0-x86_64.json", f"{OPT}/share/seccomp-filter-v1.18.0-x86_64.json", 0o644)
    if fc[0] != R["inner"]["firecracker-v1.18.0-x86_64"] or jl[0] != R["inner"]["jailer-v1.18.0-x86_64"]:
        raise NotMet("installed binary hash differs")
    step("installed", firecracker=fc, jailer=jl, seccomp_json=sc)
    return {"firecracker": {"path": f"{OPT}/bin/firecracker", "sha256": fc[0], "size": fc[1]},
            "jailer": {"path": f"{OPT}/bin/jailer", "sha256": jl[0], "size": jl[1]},
            "seccomp_json": {"path": f"{OPT}/share/seccomp-filter-v1.18.0-x86_64.json",
                             "sha256": sc[0], "size": sc[1]}}


def git_tag():
    """Records whether tag v1.18.0 is signed. Never fails the stage."""
    out = {}
    R = config.RELEASE
    out["ls_remote"] = util.run(["git", "ls-remote", R["git_url"], "refs/tags/v1.18.0", "refs/tags/v1.18.0^{}"],
                                timeout=120, cap=4096)
    g = fresh_dir(f"{WORK}/gittag")
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    out["init"] = util.run(["git", "init", "-q", g], timeout=30, cap=2048)
    out["fetch"] = util.run(["git", "-C", g, "fetch", "--depth", "1", "--no-tags", R["git_url"],
                             "refs/tags/v1.18.0:refs/tags/v1.18.0"], timeout=300, cap=4096, env=env)
    out["cat_file_type"] = util.run(["git", "-C", g, "cat-file", "-t", "v1.18.0"], timeout=30, cap=256)
    obj = util.run(["git", "-C", g, "cat-file", "-p", "v1.18.0"], timeout=30, cap=16384)
    out["tag_object"] = obj
    body = obj["stdout"]
    out["annotated"] = out["cat_file_type"]["stdout"].strip() == "tag"
    out["signature_block_present"] = ("-----BEGIN PGP SIGNATURE-----" in body or "-----BEGIN SSH SIGNATURE-----" in body)
    out["verify_tag"] = util.run(["git", "-C", g, "verify-tag", "--raw", "v1.18.0"], timeout=60, cap=8192)
    v = out["verify_tag"]
    out["summary"] = ("unreachable" if out["fetch"]["rc"] != 0 else
                      "unsigned" if not out["signature_block_present"] else
                      "signed, verified" if v["rc"] == 0 else
                      "signed, NOT verified (e.g. no public key in keyring) - see verify_tag.stderr")
    step("git_tag", summary=out["summary"])
    return out


def tofu(name, url, dest_name, cap, magic, pins_old):
    d = fresh_dir(f"{WORK}/{name}")
    f = f"{d}/{dest_name}"
    size = curl(url, f, cap)
    with open(f, "rb") as fh:
        mg = fh.read(len(magic))
    if mg != magic:
        raise NotMet(f"{name}: bad magic {mg!r}")
    sha, _ = util.sha256_file(f)
    old = pins_old.get(name, {}).get("sha256")
    step(f"tofu_{name}", url=url, size=size, sha256=sha, previous_pin=old,
         note="no published checksum exists: trust on first use; pinned for every later stage")
    if old and old != sha:
        raise NotMet(f"{name}: download hash {sha} differs from existing pin {old}")
    dst = f"{OPT}/images/{'vmlinux' if name == 'kernel' else dest_name}"
    isha, isize = install(f, dst, 0o444)
    if isha != sha:
        raise NotMet(f"{name}: installed copy differs")
    return {"path": dst, "sha256": sha, "size": isize, "source_url": url, "tofu": True,
            "first_seen_utc": pins_old.get(name, {}).get("first_seen_utc") or EV["utc_start"]}


def resolve_in_tree(tree, rel):
    """Resolve a path inside an unpacked tree without leaving it (symlinks mapped into the tree)."""
    cur = tree
    parts = [x for x in rel.split("/") if x]
    hops = 0
    while parts:
        cur = os.path.join(cur, parts.pop(0))
        if os.path.islink(cur):
            hops += 1
            if hops > 20:
                return None
            tgt = os.readlink(cur)
            base = tree if tgt.startswith("/") else os.path.dirname(cur)
            rest = os.path.relpath(os.path.normpath(os.path.join(base, tgt.lstrip("/") if tgt.startswith("/") else tgt)), tree)
            if rest.startswith(".."):
                return None
            parts = [x for x in rest.split("/") if x] + parts
            cur = tree
    return cur if os.path.lexists(cur) else None


def build_rootfs(squashfs, pins_old, rebuild):
    img = f"{OPT}/images/rootfs.ext4"
    old = pins_old.get("rootfs")
    if old and os.path.exists(img) and not rebuild:
        sha, size = util.sha256_file(img)
        step("rootfs_existing", sha256=sha, pinned=old["sha256"])
        if sha != old["sha256"]:
            raise NotMet("existing rootfs.ext4 differs from its pin (use --rebuild-rootfs to rebuild and re-pin)")
        return old
    tree = f"{WORK}/tree"
    if os.path.lexists(tree):
        shutil.rmtree(tree)
    r = util.run(["unsquashfs", "-no-xattrs", "-no-progress", "-d", tree, squashfs], timeout=1800, cap=4096)
    step("unsquashfs", rc=r["rc"], stderr=r["stderr"][-1000:])
    if r["rc"] != 0:
        raise NotMet("unsquashfs failed")
    py = resolve_in_tree(tree, "usr/bin/python3")
    link = os.readlink(f"{tree}/usr/bin/python3") if os.path.islink(f"{tree}/usr/bin/python3") else None
    m = re.search(r"python3\.(\d+)$", py or "")
    ver = f"3.{m.group(1)}" if m else None
    stdlib_ok = bool(ver) and all(os.path.isfile(f"{tree}/usr/lib/python{ver}/{x}")
                                  for x in ("json/__init__.py", "hashlib.py", "os.py"))
    tools = {t: bool(resolve_in_tree(tree, f"usr/bin/{t}") or resolve_in_tree(tree, f"usr/sbin/{t}")) for t in GUEST_TOOLS}
    step("guest_python", python3=py and os.path.relpath(py, tree), symlink=link, version_from_filename=ver,
         stdlib_ok=stdlib_ok, tools=tools,
         note="guest binaries are never executed on the host; the version is read from file names")
    if not (py and os.path.isfile(py) and stdlib_ok):
        raise Blocked("python3 (with json/hashlib/os stdlib) absent from the guest rootfs")
    missing = [t for t, ok in tools.items() if not ok]
    if missing:
        raise Blocked(f"guest rootfs lacks tools needed by /plea-init: {missing}")
    for dd in ("proc", "sys", "dev", "run", "tmp"):
        os.makedirs(f"{tree}/{dd}", exist_ok=True)
    init_src = os.path.join(config.BUNDLE, "guest", "plea-init")
    shutil.copyfile(init_src, f"{tree}/plea-init")
    os.chmod(f"{tree}/plea-init", 0o755)
    u = config.GUEST_UID
    pw = util.read_bounded(f"{tree}/etc/passwd", 1 << 20)
    if not any(line.split(":")[2:3] == [str(u)] for line in pw.splitlines() if line.count(":") >= 6):
        with open(f"{tree}/etc/passwd", "a") as f:
            f.write(f"plea:x:{u}:{u}:plea guest workload:/nonexistent:/usr/sbin/nologin\n")
        with open(f"{tree}/etc/group", "a") as f:
            f.write(f"plea:x:{u}:\n")
    total = 0
    for dp, dn, fn in os.walk(tree):
        for n in fn + dn:
            st = os.lstat(os.path.join(dp, n))
            total += (st.st_size if stat.S_ISREG(st.st_mode) else 0) + 4096
    size_mib = int(total * 1.2) // (1 << 20) + 128
    tmp = img + ".build"
    if os.path.lexists(tmp):
        os.unlink(tmp)
    with open(tmp, "wb") as f:
        f.truncate(size_mib << 20)
    r = util.run(["mkfs.ext4", "-q", "-F", "-b", "4096", "-m", "0", "-O", "^has_journal", "-E", "root_owner=0:0",
                  "-L", "plea-root", "-d", tree, tmp, f"{size_mib}M"], timeout=1800, cap=4096)
    fsck = util.run(["e2fsck", "-fn", tmp], timeout=600, cap=4096)
    step("mkfs", rc=r["rc"], stderr=r["stderr"][-1000:], size_mib=size_mib, content_bytes=total,
         e2fsck_rc=fsck["rc"], e2fsck_tail=fsck["stdout"][-500:])
    if r["rc"] != 0 or fsck["rc"] != 0:
        raise NotMet("mkfs.ext4 or e2fsck failed")
    init_sha, _ = util.sha256_file(init_src)
    os.chown(tmp, 0, 0)
    os.chmod(tmp, 0o444)
    os.replace(tmp, img)
    sha, size = util.sha256_file(img)
    shutil.rmtree(tree)
    step("rootfs_built", sha256=sha, size=size, plea_init_sha256=init_sha, guest_python=ver)
    return {"path": img, "sha256": sha, "size": size, "built_utc": EV["utc_start"], "plea_init_sha256": init_sha,
            "guest_python_from_filename": ver, "from_squashfs_sha256": pins_old.get("squashfs", {}).get("sha256")}


def write_pins(files):
    pins = {"version": 1, "updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "files": files}
    tmp = f"{OPT}/pins.json.tmp"
    with open(tmp, "w") as f:
        json.dump(pins, f, indent=1)
    os.chown(tmp, 0, 0)
    os.chmod(tmp, 0o644)
    os.replace(tmp, f"{OPT}/pins.json")
    return pins


def main(argv):
    if config.overrides_active():
        print("refusing: PLEA_* overrides set")
        return 2
    kern = config.CI["kernel_alt"] if "--kernel" in argv and argv[argv.index("--kernel") + 1] == "6.18" else config.CI["kernel"]
    os.makedirs(WORK, mode=0o700, exist_ok=True)
    pins_old = {}
    if os.path.exists(f"{OPT}/pins.json"):
        pins_old = util.load_json(f"{OPT}/pins.json").get("files", {})
    rc = 0
    try:
        files = release()
        EV["git_tag"] = git_tag()
        files["kernel"] = tofu("kernel", config.CI["base"] + kern, kern, config.CI["kernel_max"], b"\x7fELF", pins_old)
        files["squashfs"] = tofu("squashfs", config.CI["base"] + config.CI["squashfs"], config.CI["squashfs"],
                                 config.CI["squashfs_max"], b"hsqs", pins_old)
        pins_old["squashfs"] = files["squashfs"]
        files["rootfs"] = build_rootfs(files["squashfs"]["path"], pins_old, "--rebuild-rootfs" in argv)
        EV["pins"] = write_pins(files)
        EV["verdict"] = "MET"
    except Blocked as e:
        EV["verdict"], EV["reason"], rc = "BLOCKED", str(e), 3
        os.makedirs(os.path.join(config.BUNDLE, "state"), exist_ok=True)
        with open(os.path.join(config.BUNDLE, "state", "BLOCKED"), "w") as f:
            f.write(f"stage1 BLOCKED: {e}\n")
    except (NotMet, OSError, ValueError, tarfile.TarError) as e:
        EV["verdict"], EV["reason"], rc = "NOT MET", f"{type(e).__name__}: {e}", 1
    EV["utc_end"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(os.path.join(os.environ.get("PLEA_EVIDENCE", "."), "stage1_fetch.json"), "w") as f:
        json.dump(EV, f, indent=1)
    print(f"[stage1] verdict {EV['verdict']} {EV.get('reason', '')}")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
