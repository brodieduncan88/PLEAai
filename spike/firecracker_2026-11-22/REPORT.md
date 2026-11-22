# PLEA Firecracker spike: preparation report (2026-11-21 container clock)
Internal engineering work by an AI subagent. It is NOT independent validation of Firecracker or of PLEA's isolation. Firecracker is the
only candidate; no other engine was touched. Nothing was installed system-wide; no git repository was touched; nothing committed.
Directory: /tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad/spike_fc/

## 1. What was run on this machine (no /dev/kvm, no vmx/svm, cgroup v1 hybrid, root, 4 CPU)
Declared first: declared/DECLARATION.md (SHA-256 6a189723...a7f9f5) with declared/SHA256SUMS for all code. Outputs: evidence/*.txt (UTC-stamped).
| Test | Result | vs declaration |
|---|---|---|
| T1 prereq.py | exit 1; all 7 checks NOT MET (no /dev/kvm; /sys/fs/cgroup is tmpfs; no cgroup.controllers; empty pins). Valid JSON, no traceback | as declared |
| T2 admission_demo.py | 5/5 tests pass: 503 ISOLATION_UNAVAILABLE with 0 budget ops (also for each single failure and 9 malformed inputs); control case admits with exactly 1 op; real prereq output on this host gives 503, 0 ops | as declared |
| T3 syntax check | bash -n all OK; Python half CRASHED in my test code (py_compile to /dev/null) and exit code hid it | DEVIATION (my test defect) |
| T4 workload.py natively | prints SPIKE_RESULT with digest (runs on host python only) | as declared |
| T5 download | HTTP 302, 0-byte file; command did not follow redirects; I had predicted 403 | DEVIATION (my test defect and wrong prediction) |
| T6 / T7 | NOT RUN in run 1 (no binary) | as declared |
| T8 five harness scripts | each exit 2 with REFUSED + NOT MET list; no /run/plea-spike created, no cgroup change | as declared |
| T9 recover_orphans.py on temp dir | dry run removes nothing; --apply removes `spike-deadbeef`, keeps `keepme` | as declared |
| T10a-d odd input (bad/missing pins, regular file as /dev/kvm, /dev/null as /dev/kvm, directory as binary) | exit 1, no traceback, every failure a NOT MET line; /dev/null counts as a char device (MET) and fails the ioctl (ENOTTY), as declared | as declared |
VP process for the two deviations: failing runner and declaration copied to evidence/failed_run1_source/ with SHA-256 (evidence/failed_run1_SHA256SUMS);
change record evidence/CHANGE_RECORD_1.md; new declaration declared/DECLARATION_2.md (hashes in declared/SHA256SUMS.run2) written before run 2;
original run_declared.sh left unedited, new runner run_declared_2.sh. One process note: I corrected a vague sentence in DECLARATION_2.md
(count of sh files) before running run 2, and re-hashed it; no result had been seen. No product code (prereq, admission, harness) was changed after any result.
Run 2 results (both runs are reported; neither replaces the other):
- T3b: 16 py ok (ast.parse), 7 sh ok, exit 0. Syntax only; says nothing about behaviour on KVM.
- T5b: with redirects followed, tgz firecracker-v1.12.1-x86_64.tgz (7,311,887 bytes) and its .sha256.txt downloaded; `sha256sum -c` OK;
  tgz SHA-256 0a75e67ef6e4c540a2cf248b06822b0be9820cbba9fe19f9e0321200fe76ff6b. The checksum file comes from the same origin as the tarball, so this
  shows transfer integrity, not authenticity. I did NOT verify any signature. I predicted either outcome; it succeeded.
- T6b: binary runs without KVM: `Firecracker v1.12.1`; binary SHA-256 b99ea49b8d8b7bfa307d3845585d6a97f7642aa17a985749900370070d8ca930.
- T7b (Firecracker run directly, seccomp default, dummy zero-filled kernel/rootfs, not real images): API socket created, `GET /` answered
  `state: Not started`; PUT boot-source, drives, machine-config returned 204; PUT /actions InstanceStart returned 400:
  "Start microvm error: Internal error while starting microVM: Kvm error: Error creating KVM object: No such file or directory (os error 2)
  Make sure the user launching the firecracker process is configured on the /dev/kvm file's ACL." The VMM stayed alive afterwards (it
  does not exit on this error), so a harness must treat InstanceStart failure as fatal and kill the VMM.
Release currency NOT verified: api.github.com and github.com/.../releases/latest returned HTTP 403 ("GitHub access to this repository is not enabled
for this session"); I did not use add_repo (outside my brief). So v1.12.1 is only a candidate; pins.json is left EMPTY (checker reports NOT MET).

## 2. Written but NOT RUN (never executed on KVM; expect bugs)
fc_lib.py (VM start/cgroup/sampling), bench_latency.py, limits_test.py, host_exhaustion.py, crash_cleanup.py, concurrency.py, the cgroup and tap
paths of recover_orphans.py, guest jobs other than workload.py (fork bomb, balloon, fd, mmap), guest init.sh, build_rootfs.sh, fetch_artifacts.sh,
host_config/install.sh, check_after_reboot.sh and plea-spike-run@.service. Only syntax (T3b) and, for harness scripts, the refusal path (T8) were exercised.
README.md has one row per script. Claims such as "cgroup empty after kill -9" or "no leftover socket" are hypotheses to test, not results.

## 3. KVM host requirements
- Hardware: x86_64 with VT-x/AMD-V exposed and /dev/kvm. Either (a) a bare-metal instance (AWS *.metal, GCP/Azure bare metal), or (b) a VM with nested
  virtualisation enabled (GCP: Intel Haswell or later with --enable-nested-virtualization; Azure: nested-capable Dv3/Ev3 or newer series). I did not verify current
  AWS/GCP/Azure support lists; check provider docs on the day. Nested results are not representative of bare-metal latency or isolation.
- OS: Ubuntu 24.04 LTS, kernel 6.8 (distro), cgroup v2 unified (default on 24.04), systemd 255, 4+ vCPU, 16 GiB RAM, 30 GiB disk.
- Packages: python3 (3.12), curl, ca-certificates, tar, coreutils, util-linux (systemd-run), iproute2 (recovery tap removal). Build host only: debootstrap, e2fsprogs.
- Accounts: system user `plea-spike` in group `kvm`; /dev/kvm group kvm mode 0660 via udev rule; no root needed to run VMs. Root only for install and image build.
- cgroup: service with Delegate=yes (unit provided); the harness moves itself to a `mgr` leaf and enables +memory +pids +cpu.
- Network: outbound HTTPS to github.com, release-assets.githubusercontent.com, snapshot.ubuntu.com, and the Firecracker CI kernel bucket (s3.amazonaws.com spec.ccfc.min).

## 4. Run sheet for the owner's KVM host
1. Provision the host; `ls -l /dev/kvm; stat -f -c %T /sys/fs/cgroup` must show a char device and `cgroup2fs`. If not, stop (fail closed).
2. Copy this directory to the host. `sudo apt-get install -y python3 curl ca-certificates tar e2fsprogs debootstrap iproute2`.
3. Confirm the current Firecracker release on GitHub and its checksum file. `FC_VERSION=vX.Y.Z KERNEL_URL=<CI kernel URL> guest_image/fetch_artifacts.sh`
   (fails on checksum mismatch). Put the printed hashes in pins.json (firecracker_sha256, firecracker_release_tgz_sha256, kernel_sha256).
4. `sudo -E SNAPSHOT=<YYYYMMDDTHHMMSSZ> guest_image/build_rootfs.sh`; run it twice and compare hashes; if equal pin rootfs_sha256, else record the difference.
5. `sudo host_config/install.sh` (copies to /opt/plea-spike, installs udev rule and unit). Then `sudo host_config/check_after_reboot.sh`; it must exit 0.
6. Latency: `sudo systemctl start plea-spike-run@bench_latency.py` (journalctl -u plea-spike-run@bench_latency.py; JSON in /var/lib/plea-spike). For other N/K use
   `sudo systemd-run --wait --pipe -p User=plea-spike -p SupplementaryGroups=kvm -p Delegate=yes -E PLEA_SPIKE_HOME=/opt/plea-spike python3 /opt/plea-spike/harness/bench_latency.py -n 100`.
7. Same for limits_test.py, host_exhaustion.py, concurrency.py (-k 4, 8, 16, 32), crash_cleanup.py. Before and after each, run `recover_orphans.py` (dry run) and record output.
8. `sudo reboot`; run check_after_reboot.sh; then rerun bench_latency once. Record whether anything needed manual repair.
9. Before changing any test predicate after a failure follow VP-1 to VP-6 (write a declaration for the host first, hash it, then run).

## 5. Cost estimate (rough; labelled estimate, not a quote; prices change)
- Nested-virt VM, 4 vCPU/16 GiB, about $0.15 to $0.30 per hour: 3 to 5 days continuous roughly $11 to $36; with stop/start outside working hours roughly $5 to $15.
- Bare-metal (e.g. AWS c5.metal class, about $4 to $6 per hour on-demand): 3 to 5 days continuous roughly $290 to $720; about 8 active hours a day with stop/start roughly $100 to $240.
- Add disk and egress, about $3 to $10. A cheap nested VM for development plus a bare-metal day for final measurements is the likely sweet spot (about $40 to $120 total).

## 6. Security limitations already visible
1. No jailer: the VMM runs as an ordinary user with Firecracker's seccomp filter and a cgroup, but no chroot, no PID/mount/net namespaces, no uid drop per VM.
   A VMM escape lands as `plea-spike` on the host. A production design should use the jailer, one uid per VM.
2. No input channel: the job is selected via kernel cmdline from a fixed list. Delivering untrusted user code and returning output (vsock or a second drive) is
   not designed or tested. Serial console output is unbounded and goes to a host file (disk/CPU exhaustion); no RLIMIT_FSIZE is set. Not implemented.
3. No host wall-clock watchdog beyond the harness's wait timeout; in-guest `timeout 120` is trusted only if the guest is not compromised. cpu.max throttles, it does not kill.
4. `pids.max` limits VMM threads only; guest process limits are the guest kernel's. Host fd cost per VM is unmeasured (the harness measures it; no claim that Firecracker removes host file-table limits).
5. Check-then-use gap: prereq.py hashes kernel/rootfs/binary at check time; files could change before use unless root-owned and read-only. No re-check at launch beyond require_prereqs.
6. Pins: Firecracker CI kernel has no published checksum known to me (trust on first use). Release signature not verified. Release currency and security advisories for v1.12.1 not checked.
7. prereq.py "enable-able" controller result is optimistic (it is non-mutating); only fc_lib.prepare_parent proves delegation. On this host /sys/fs/cgroup/unified is a cgroup2 mount (hybrid);
   the checker tests /sys/fs/cgroup as specified and reports NOT MET.
8. Hardware side channels (Spectre-class, SMT sibling sharing) and the KVM kernel attack surface are outside this spike; `smt:false` only changes guest topology. Nested virtualisation weakens the
   measured isolation story further.
9. Admission prototype checks a result passed in; it does not say when to check (startup versus per request) or how to handle a prerequisite failing mid-flight. Not PLEA code.
10. The 503 rule only helps if every code path that starts a VM goes through admit(); that coupling lives in PLEA and was not examined.
Files not to commit: downloads/ (binary and tgz; .gitignore provided). Evidence and declared/ should be committed with the code.
