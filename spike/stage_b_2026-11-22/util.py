"""Small shared helpers (stdlib only). No function here reads or writes unboundedly."""
import hashlib
import json
import math
import os
import stat
import subprocess
import time


def sha256_file(path, max_bytes=None):
    """Hash a regular file without following a final symlink. Returns (hex, size)."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise ValueError(f"{path}: not a regular file")
        if max_bytes is not None and st.st_size > max_bytes:
            raise ValueError(f"{path}: {st.st_size} bytes exceeds cap {max_bytes}")
        h, n = hashlib.sha256(), 0
        while True:
            b = os.read(fd, 1 << 20)
            if not b:
                break
            h.update(b)
            n += len(b)
        return h.hexdigest(), n
    finally:
        os.close(fd)


def read_bounded(path, cap=65536, binary=False):
    with open(path, "rb") as f:
        data = f.read(cap)
    return data if binary else data.decode("utf-8", "replace")


def path_problems(path):
    """Every component of path must exist, not be a symlink, be root-owned and not
    group/other-writable. Returns a list of problems (empty == safe)."""
    probs, cur = [], "/"
    parts = [p for p in os.path.abspath(path).split("/") if p]
    for comp in [""] + parts:
        cur = os.path.join(cur, comp) if comp else "/"
        try:
            st = os.lstat(cur)
        except OSError as e:
            probs.append(f"{cur}: {e.strerror}")
            break
        if stat.S_ISLNK(st.st_mode):
            probs.append(f"{cur}: is a symlink")
        if st.st_uid != 0:
            probs.append(f"{cur}: owner uid {st.st_uid} != 0")
        if st.st_mode & 0o022:
            probs.append(f"{cur}: mode {oct(st.st_mode & 0o7777)} is group/other-writable")
    return probs


def mountinfo(path="/proc/self/mountinfo", cap=1 << 20):
    out = []
    for line in read_bounded(path, cap).splitlines():
        left, _, right = line.partition(" - ")
        f, r = left.split(), right.split()
        if len(f) < 5 or len(r) < 1:
            continue
        mp = f[4].encode().decode("unicode_escape") if "\\" in f[4] else f[4]
        out.append({"mount_point": mp, "fstype": r[0], "source": r[1] if len(r) > 1 else ""})
    return out


def meminfo(path="/proc/meminfo"):
    d = {}
    for line in read_bounded(path, 16384).splitlines():
        k, _, v = line.partition(":")
        if v.strip().split():
            d[k] = int(v.strip().split()[0])
    return d


def run(cmd, timeout=30, cap=65536, **kw):
    """subprocess.run with a mandatory timeout and bounded captured output."""
    t = time.monotonic()
    try:
        p = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout, **kw)
        return {"cmd": cmd, "rc": p.returncode, "secs": round(time.monotonic() - t, 3),
                "stdout": p.stdout[:cap].decode("utf-8", "replace"),
                "stderr": p.stderr[:cap].decode("utf-8", "replace"),
                "stdout_truncated": len(p.stdout) > cap}
    except subprocess.TimeoutExpired:
        return {"cmd": cmd, "rc": None, "timeout": True, "secs": timeout, "stdout": "", "stderr": ""}
    except OSError as e:
        return {"cmd": cmd, "rc": None, "error": str(e), "stdout": "", "stderr": ""}


def load_json(path, cap=1 << 20):
    return json.loads(read_bounded(path, cap))


def pctl(values):
    """min/median/p95/max (nearest-rank)."""
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    rank = lambda q: v[min(len(v) - 1, max(0, math.ceil(round(q * len(v), 9)) - 1))]
    med = v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2
    return {"n": len(v), "min": v[0], "median": med, "p95": rank(0.95), "max": v[-1]}
