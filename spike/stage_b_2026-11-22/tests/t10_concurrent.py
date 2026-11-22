#!/usr/bin/env python3
"""T10: concurrent microVMs K=2,4,8 (each 128 MiB guest). Each gets a distinct nonce and must return only its own.
While all K are alive (barrier), the host checks: each VMM's open regular files are inside its own chroot and
disjoint from every other VMM's; a process with VM i's uid/gid cannot open VM j's input/output images."""
import json
import os
import secrets
import stat
import subprocess
import sys
import threading

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import fclib, main, payload, slim, util  # noqa: E402

PROBE = ("import sys,json\nr={}\nfor p in sys.argv[1:]:\n try:\n  open(p,'rb').close(); r[p]='OPENED'\n"
         " except OSError as e:\n  r[p]=e.errno\nprint(json.dumps(r))")


def chroot_inodes(root):
    out = set()
    for dp, dn, fn in os.walk(root):
        for n in fn:
            st = os.lstat(os.path.join(dp, n))
            if stat.S_ISREG(st.st_mode):
                out.add((st.st_dev, st.st_ino))
    return out


def round_k(t, k):
    nonces = [secrets.token_hex(8) for _ in range(k)]
    seen, results = {}, [None] * k
    lock = threading.Lock()

    def cross_check():
        ids = sorted(seen)
        info = {"pairs_disjoint": True, "own_subset": {}, "cross_uid": {}}
        for i in ids:
            info["own_subset"][i] = seen[i]["fds"] <= seen[i]["chroot_inodes"]
            for j in ids:
                if i < j and seen[i]["fds"] & seen[j]["fds"]:
                    info["pairs_disjoint"] = False
        for i in ids:
            others = [os.path.join(seen[j]["chroot"], f) for j in ids if j != i for f in ("in.img", "out.img", "vm.json")]
            r = subprocess.run([sys.executable, "-I", "-c", PROBE] + others, user=seen[i]["uid"], group=seen[i]["uid"],
                               extra_groups=[], capture_output=True, timeout=30)
            try:
                info["cross_uid"][i] = json.loads(r.stdout[:65536] or b"{}")
            except ValueError:
                info["cross_uid"][i] = {"error": r.stderr[:500].decode("utf-8", "replace")}
        seen["_check"] = info

    barrier = threading.Barrier(k, action=cross_check, timeout=120)

    def on_ready(ctx):
        with lock:
            seen[ctx["id"]] = {"uid": ctx["uid"], "chroot": ctx["chroot"], "fds": fclib.fd_inodes(ctx["pid"]),
                               "chroot_inodes": chroot_inodes(ctx["chroot"])}
        try:
            barrier.wait()
        except threading.BrokenBarrierError:
            seen.setdefault("_broken", True)

    def worker(i):
        results[i] = fclib.run_vm(payload("w_echo", nonce=nonces[i], sleep=30), label=f"T10-k{k}-{i}",
                                  on_ready=on_ready, guest_timeout=60, host_timeout=180)

    ths = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(k)]
    for th in ths:
        th.start()
    for th in ths:
        th.join(timeout=320)
    outs = []
    for r in results:
        try:
            outs.append(json.loads((r or {}).get("stdout") or "{}"))
        except ValueError:
            outs.append({})
    own = all(o.get("nonce") == nonces[i] for i, o in enumerate(outs))
    foreign = any(n in ((results[i] or {}).get("stdout") or "") for i in range(k) for j, n in enumerate(nonces) if j != i)
    chk = seen.get("_check") or {}
    denied = all(isinstance(v, int) for d in chk.get("cross_uid", {}).values() for v in d.values()) and bool(chk.get("cross_uid"))
    t.data[f"k{k}"] = {"runs": [slim(r or {}, 512) for r in results], "echo": outs,
                       "check": {"pairs_disjoint": chk.get("pairs_disjoint"), "own_subset": chk.get("own_subset"),
                                 "cross_uid": chk.get("cross_uid"), "barrier_broken": seen.get("_broken", False)}}
    t.pred(f"T10.k{k}.P1", f"all {k} concurrent VMs ok", all(r and r["ok"] for r in results), [bool(r and r["ok"]) for r in results])
    t.pred(f"T10.k{k}.P2", "each VM returned its own nonce and no other VM's nonce", own and not foreign, {"own": own, "foreign": foreign})
    t.pred(f"T10.k{k}.P3", "while all were alive: each VMM's open regular files lie inside its own chroot; sets pairwise disjoint",
           bool(chk) and chk.get("pairs_disjoint") is True and all(chk.get("own_subset", {}).values()) and len(chk.get("own_subset", {})) == k,
           {"own_subset": chk.get("own_subset"), "disjoint": chk.get("pairs_disjoint")})
    t.pred(f"T10.k{k}.P4", "a process with VM i's uid/gid cannot open VM j's in.img, out.img or vm.json (every open fails)",
           denied, chk.get("cross_uid"))
    t.pred(f"T10.k{k}.P5", "all VMs cleaned", all(r and r["clean"] for r in results))


def t10(t):
    t.gate()
    for k in (2, 4, 8):
        need = k * (128 + 192) + 1024
        avail = util.meminfo().get("MemAvailable", 0) >> 10
        t.data[f"k{k}_mem"] = {"need_mib": need, "avail_mib": avail}
        if avail < need:
            t.pred(f"T10.k{k}.P0", f"MemAvailable >= {need} MiB before starting K={k}", False, avail)
            continue
        round_k(t, k)


if __name__ == "__main__":
    sys.exit(main(t10, "T10", "Concurrent workloads K=2,4,8"))
