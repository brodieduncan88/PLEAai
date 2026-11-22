#!/bin/bash
cd "$(dirname "$0")"; E=evidence; TS(){ date -u +%Y%m%dT%H%M%SZ; }
run(){ id=$1; shift; f="$E/$id.$(TS).txt"; { echo "# $id"; echo "# started $(date -u +%FT%TZ)"; echo "# cmd: $*"; "$@"; rc=$?; echo "# exit code: $rc"; echo "# finished $(date -u +%FT%TZ)"; } >"$f" 2>&1; echo "$id -> $f"; }
V=v1.12.1   # UNVERIFIED candidate, not a pin
run T3b_syntax bash -c 'rc=0; for f in *.py harness/*.py guest_image/jobs/*.py; do python3 -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" $f && echo "py ok $f" || rc=1; done
for f in guest_image/*.sh host_config/*.sh run_declared.sh run_declared_2.sh; do bash -n $f && echo "sh ok $f" || rc=1; done; exit $rc'
mkdir -p downloads/fc-candidate; D=downloads/fc-candidate
B=https://github.com/firecracker-microvm/firecracker/releases/download/$V; T=firecracker-$V-x86_64.tgz
run T5b_download bash -c "cd $D && curl -sS -L --max-redirs 3 -m 120 -o $T -w 'tgz http_code=%{http_code} size=%{size_download} url_effective=%{url_effective}\n' $B/$T; curl -sS -L --max-redirs 3 -m 60 -o $T.sha256.txt -w 'sha http_code=%{http_code} size=%{size_download}\n' $B/$T.sha256.txt; ls -la; echo '--- published checksum file:'; cat $T.sha256.txt | head -5; echo '--- verify:'; sha256sum -c $T.sha256.txt; echo '--- local sha256:'; sha256sum $T"
if [ -s $D/$T ] && (cd $D && sha256sum -c $T.sha256.txt >/dev/null 2>&1); then
  mkdir -p $D/x && tar -xzf $D/$T -C $D/x
  BIN=$(ls $D/x/release-*/firecracker-$V-x86_64 2>/dev/null | head -1)
  run T6b_fc_version bash -c "ls -la $BIN; sha256sum $BIN; $BIN --version"
  run T7b_vmm_socket_no_kvm python3 -I - "$BIN" <<'PY'
import sys, os, subprocess, time, socket, http.client, json, tempfile
binp = os.path.abspath(sys.argv[1]); d = tempfile.mkdtemp(prefix="fcprobe-"); sock = os.path.join(d, "api.sock")
for n in ("kernel", "rootfs"): open(os.path.join(d, n), "wb").write(b"\0" * (1 << 20))
p = subprocess.Popen([binp, "--api-sock", sock], stdout=open(os.path.join(d, "out"), "wb"), stderr=subprocess.STDOUT)
for _ in range(100):
    if os.path.exists(sock): break
    time.sleep(0.05)
print("socket exists:", os.path.exists(sock), "process alive:", p.poll() is None)
class C(http.client.HTTPConnection):
    def connect(self): self.sock = socket.socket(socket.AF_UNIX); self.sock.settimeout(10); self.sock.connect(sock)
def call(m, path, body=None):
    c = C("localhost"); c.request(m, path, json.dumps(body) if body is not None else None, {"Content-Type": "application/json"}); r = c.getresponse(); print(m, path, "->", r.status, r.read().decode()[:400]); c.close()
try:
    if os.path.exists(sock):
        call("GET", "/")
        call("PUT", "/boot-source", {"kernel_image_path": os.path.join(d, "kernel"), "boot_args": "console=ttyS0"})
        call("PUT", "/drives/rootfs", {"drive_id": "rootfs", "path_on_host": os.path.join(d, "rootfs"), "is_root_device": True, "is_read_only": True})
        call("PUT", "/machine-config", {"vcpu_count": 1, "mem_size_mib": 128})
        call("PUT", "/actions", {"action_type": "InstanceStart"})
except Exception as e: print("api exception:", type(e).__name__, e)
time.sleep(1); print("process alive after:", p.poll() is None, "returncode:", p.poll())
p.kill(); p.wait(); print("--- VMM stdout/stderr:"); print(open(os.path.join(d, "out"), errors="replace").read()[:1500])
import shutil; shutil.rmtree(d)
PY
else
  echo "T6b/T7b NOT RUN: T5b did not produce a checksum-verified tgz" | tee "$E/T6b_T7b_not_run.$(TS).txt"
fi
