#!/bin/bash
# Executes the tests listed in declared/DECLARATION.md on THIS machine; each output goes to evidence/ with a UTC timestamp.
cd "$(dirname "$0")"; E=evidence; TS(){ date -u +%Y%m%dT%H%M%SZ; }
run(){ id=$1; shift; f="$E/$id.$(TS).txt"; { echo "# $id"; echo "# started $(date -u +%FT%TZ)"; echo "# cmd: $*"; "$@"; rc=$?; echo "# exit code: $rc"; echo "# finished $(date -u +%FT%TZ)"; } >"$f" 2>&1; echo "$id -> $f"; }
FC_CAND=v1.12.1   # UNVERIFIED candidate used only to exercise the download path; it is NOT a pin
run T1_prereq python3 -I prereq.py
run T2_admission python3 -I admission_demo.py
run T3_syntax bash -c 'python3 - <<PY
import py_compile,glob
for f in glob.glob("*.py")+glob.glob("harness/*.py")+glob.glob("guest_image/jobs/*.py"): py_compile.compile(f,cfile="/dev/null",doraise=True); print("py ok",f)
PY
for f in guest_image/*.sh host_config/*.sh run_declared.sh; do bash -n $f && echo "sh ok $f"; done'
run T4_workload_native python3 -I -B guest_image/jobs/workload.py
run T5_download bash -c "cd downloads && curl -sS -m 60 -o fc.tgz -w 'http_code=%{http_code}\n' https://github.com/firecracker-microvm/firecracker/releases/download/$FC_CAND/firecracker-$FC_CAND-x86_64.tgz; ls -la; curl -sS -m 60 -w '\nhttp_code=%{http_code}\n' https://github.com/firecracker-microvm/firecracker/releases/download/$FC_CAND/firecracker-$FC_CAND-x86_64.tgz.sha256.txt"
run T6_fc_version bash -c 'ls downloads/firecracker && downloads/firecracker --version || echo "NOT RUN: no firecracker binary"'
run T7_vmm_socket_no_kvm bash -c 'test -x downloads/firecracker && { timeout 10 downloads/firecracker --api-sock /tmp/spike_fc_probe.sock & sleep 2; ls -la /tmp/spike_fc_probe.sock; wait; } || echo "NOT RUN: no firecracker binary"'
for s in bench_latency limits_test host_exhaustion concurrency crash_cleanup; do run T8_refuse_$s python3 harness/$s.py; done
run T8b_no_side_effects bash -c 'ls -d /run/plea-spike 2>&1; ls /sys/fs/cgroup | head'
run T9_recover bash -c 'W=$(mktemp -d); mkdir -p $W/spike-deadbeef $W/keepme; touch $W/spike-deadbeef/api.sock $W/keepme/f; echo 999999 >$W/spike-deadbeef/pid
python3 harness/recover_orphans.py --workdir $W; echo "--- after dry run:"; ls $W
python3 harness/recover_orphans.py --workdir $W --apply; echo "--- after apply:"; ls $W; rm -rf $W'
echo '{ not json' >/tmp/spike_bad_pins.json
run T10a_bad_pins python3 -I prereq.py --pins /tmp/spike_bad_pins.json
run T10b_kvm_regular_file python3 -I prereq.py --kvm /etc/hostname
run T10c_kvm_devnull python3 -I prereq.py --kvm /dev/null
run T10d_missing_pins python3 -I prereq.py --pins /nonexistent --firecracker /etc
rm -f /tmp/spike_bad_pins.json
