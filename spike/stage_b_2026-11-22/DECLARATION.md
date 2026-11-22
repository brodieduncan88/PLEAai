# Stage B declaration: predicates fixed before execution

These predicates are written before any run. `declare.sh` hashes every bundle file, this one included,
into `declared/SHA256SUMS`, and `run_stage.sh` refuses to run if any file differs (VP rule). A test's
verdict is **MET** only if every predicate below is met. It is **BLOCKED** if the prerequisite gate
(`prereq.check_all(hash_images=True)` plus the jailer/firecracker flag check) is NOT MET, and **ERROR**
on an unexpected exception. Every test also records a `recover.py` dry-run, a `journalctl -k`
excerpt and a dmesg tail (done by `run_stage.sh`).

Scope note: microVM isolation does **not** remove host-wide limits. Host memory, `fs.file-max`,
`kernel.pid_max`, disk and CPU are still shared. Each VMM consumes host memory, threads and file
descriptors. T05–T07 measure how guest activity maps onto host resources. They do not claim the host
is untouched.

Common caps for every microVM: guest `timeout` (default 20 s), a host wall-clock watchdog that
SIGKILLs the process group (default 90 s), console 16 KiB head + 16 KiB tail (T08: 64 KiB each),
payload ≤ 1 MiB, result stdout ≤ 64 KiB, stderr ≤ 4 KiB. VMM limits: `memory.max` = guest + 192 MiB,
`memory.swap.max` 0, `pids.max` 64, `cpu.max` 1 CPU, RLIMIT_FSIZE 16 MiB, RLIMIT_NOFILE 1024.
Every subprocess has a timeout.

## T01: start a microVM under the jailer
- **T01.P1** `jailer --help` lists `--id --exec-file --uid --gid --chroot-base-dir --cgroup --cgroup-version --parent-cgroup --resource-limit`; firecracker lists `--config-file` (and `--no-api` or `--api-sock`); both `--version` outputs contain 1.18.0.
- **T01.P2** The argv contains `--cgroup-version 2`, `--parent-cgroup plea-spike`, `--uid` = `--gid` within 64000–64999, and `--chroot-base-dir /srv/plea-jailer`. It never contains `--no-seccomp`.
- **T01.P3** `/proc/<pid>/cgroup` at READY is `0::/plea-spike/<vm_id>`, and the chroot is `/srv/plea-jailer/firecracker/<vm_id>/root`.
- **T01.P4** PLEA_READY and PLEA_DONE were seen with one nonce, the result parsed, the guest status is OK, and the workload echoed the host nonce.
- **T01.P5** Cleanup and a recover scan show no chroot, cgroup, lease or uid-range process.
- Measured: full `jailer --help`/`firecracker --help`, versions, argv, uid/gid, chroot path, cgroup path, timings.

## T02: unprivileged execution and constraints
- **T02.P1** All four `Uid:` fields and all four `Gid:` fields of the VMM equal the allocated non-zero id. `Groups:` is empty.
- **T02.P2** Every VMM thread (`/proc/<pid>/task/*/status`) has `Seccomp: 2`.
- **T02.P3** `CapEff` and `CapPrm` are 0.
- **T02.P4** The VMM pid is in `cgroup.procs` of `plea-spike/<vm_id>`.
- **T02.P5** `cpu.max` = `100000 100000`, `memory.max` = (128+192) MiB in bytes, `memory.swap.max` = 0, `pids.max` = 64.
- **T02.P6** In `/proc/<pid>/limits`, Max file size = 16777216 and Max open files = 1024 (soft and hard).
- **T02.P7** The sha256 of `/proc/<pid>/exe` at READY equals the pinned firecracker hash.
- **T02.P8** The run is ok and cleanup is clean.
- Measured: status fields, per-thread seccomp, NoNewPrivs, CapBnd, cgroup files, limits, exe path.

## T03: standard-library Python workload
- **T03.P1** The run is ok, the guest exit is 0, and stdout is not truncated.
- **T03.P2** sha256(guest stdout) = sha256(stdout of the same payload run by host python3 `-I -S`).
- **T03.P3** The guest-echoed payload sha256 equals the host payload sha256.
- Measured: guest Python version (from stderr), host reference output.

## T04: latency, N = 20 sequential runs
- **T04.P1** All 20 runs are ok. **T04.P2** All 20 are clean.
- **T04.P3** p95 of spawn→clean ≤ 30 s. This is a sanity bound only; the latencies are measurements, not targets.
- Measured (min/median/p95/max): prep (copy + hash), cold start (spawn→READY), execution (READY→DONE), VMM shutdown (DONE→exit), teardown (exit→clean), total.

## T05: CPU, memory, process and file-descriptor limits
Caps: CPU job is 2 procs × 8 s at `cpu.max` 50000 (0.5 CPU). Memory job is a 512 MiB balloon in a 256 MiB guest. Fork job is ≤ 20000 children / 10 s. fd job is ≤ 100000 opens.
- **T05.P1** VM cgroup `usage_usec` delta ÷ wall time between READY and DONE ≤ 0.5 × 1.15.
- **T05.P2** `cpu.stat nr_throttled` increased.
- **T05.P3** The host VM cgroup `memory.events oom_kill` = 0, PLEA_DONE was seen, and the VMM exit code is 0.
- **T05.P4** VM cgroup `memory.peak` (or the max sampled `memory.current`) ≤ `memory.max`.
- **T05.P5** The guest status is OK and the workload did not reach 512 MiB (exit ≠ 0 or the outcome is not `target_reached`).
- **T05.P6** With guest RLIMIT_NPROC 512, the fork bomb stops with EAGAIN (11) below 20000.
- **T05.P7** The VMM thread count is constant across the samples, and VM `pids.current` ≤ 64.
- **T05.P8** With guest RLIMIT_NPROC 100000, the job still ends (PLEA_DONE or watchdog) and cleanup is clean.
- **T05.P9** Same as P7, for the unlimited case.
- **T05.P10** With guest RLIMIT_NOFILE 1024, the guest stops with EMFILE at ≤ 1024 opens.
- **T05.P11** Max VMM fd count during the run − fd count at READY ≤ 2.
- Measured: cpu.stat series, memory.events, peak, guest console OOM lines, VMM threads, pids.current/events, VMM fds.

## T06: guest exhaustion vs host availability
Jobs: `cpu` (2 vCPU spin 20 s, `cpu.max` 2 CPUs of 4), `mem` (1024 MiB guest asks for 2048 MiB), `fork` (guest NPROC 100000, ≤ 20000 / 15 s), `fd` (≤ 1,000,000 opens, 1024 MiB guest). The host sampler runs every 200 ms. A second microVM is started once the exhausting VM is READY.
- **T06.\<job\>.P1** Host probe latency (spawn of `/bin/true`) has p95 ≤ 250 ms and max ≤ 2000 ms during the job.
- **T06.\<job\>.P2** Host MemAvailable never drops below 512 MiB.
- **T06.\<job\>.P3** The second microVM is ok and returned its own nonce.
- **T06.\<job\>.P4** The exhausting VM ended (PLEA_DONE or watchdog) and both VMs are clean.
- IDs: T06.cpu.P1, T06.cpu.P2, T06.cpu.P3, T06.cpu.P4, T06.mem.P1, T06.mem.P2, T06.mem.P3, T06.mem.P4, T06.fork.P1, T06.fork.P2, T06.fork.P3, T06.fork.P4, T06.fd.P1, T06.fd.P2, T06.fd.P3, T06.fd.P4.
- Measured: probe latency distribution, max load1, min MemAvailable, file-nr, every 5th sample.

## T07 (D37): bounded high-descriptor workload
The guest raises its own limits (RLIMIT_NOFILE 1048576, `fs.file-max` 1100000, 1024 MiB guest) and opens up to 1,000,000 descriptors on `/dev/null`, holding them for 3 s. The host samples every 200 ms: `/proc/sys/fs/file-nr` (all three fields), `fs.file-max`, and the VMM fd count. Sampling runs 2 s before, throughout, and 2 s after the run.
- **T07.P1** The guest opened ≥ 900,000 descriptors. Otherwise the measurement is not meaningful and the predicate is NOT MET.
- **T07.P2** (host `file-nr[0]` peak − value at READY) ÷ guest descriptors opened < 0.01. The measured ratio is reported, and host usage is not claimed to be unchanged.
- **T07.P3** Max VMM fd count − fd count at READY ≤ 2. Without `--daemonize`/`--new-pid-ns`, the jailer execs firecracker in place, so the jailer pid is the VMM pid.
- **T07.P4** Host `fs.file-max` is unchanged throughout.
- **T07.P5** The run is ok and clean.
- Measured: baseline/at-READY/peak/after file-nr, deltas vs READY and vs baseline, ratio, VMM fds, guest progress timestamps.

## T08: console bounding, log retention, fsize
- **T08.P1** The host kept ≤ 64 KiB head and ≤ 64 KiB tail of an 8 MiB console flood.
- **T08.P2** dropped = total − kept, and total ≥ 1 MiB (the flood reached the host).
- **T08.P3** Chroot disk usage before cleanup ≤ placed files (kernel, rootfs, in.img, vm.json) + output image + the jailer's copy of the firecracker binary (pinned size) + 1 MiB.
- **T08.P4** PLEA_DONE was still detected and cleanup is clean.
- **T08.P5** The serialised run result is ≤ 1 MiB.
- **T08.P6** With RLIMIT_FSIZE 16 MiB on the VMM and a 32 MiB sparse output image that the guest (root) fills with random data, no non-zero byte exists at offset ≥ 16 MiB, and allocated ≤ 16 MiB + 1 MiB.
- **T08.P7** Cleanup is clean after the fsize event. The VMM exit code, guest probe rc and VMM stderr tail are recorded.

## T09: code delivery and bounded result retrieval
- **T09.P1** The guest hashed the payload, matched the host value from the cmdline, and echoed it. Status is OK.
- **T09.P2** With a wrong expected hash, the status is REJECT_HASH, exit is −1 (not run), and stdout is empty.
- **T09.P3** Stdout of 4 × 64 KiB is truncated to exactly 64 KiB and `stdout_truncated` is true.
- **T09.P4** These length prefixes each give REJECT_LEN with exit −1: top bit set, cap+1, beyond device, zero, short.
- **T09.P5** With `plea.probe=rw`, guest root's write to the read-only input drive fails (rc ∉ {0, −1}), so does a write to the read-only rootfs, and the host `in.img` hash is unchanged.
- **T09.P6** The host decoder rejects a forged result whose stdout_len exceeds the cap.

## T10: concurrent workloads K = 2, 4, 8 (128 MiB guests)
- **T10.k\<K\>.P0** (only if it fails) MemAvailable ≥ K × 320 + 1024 MiB before the round.
- **T10.k\<K\>.P1** All K VMs are ok.
- **T10.k\<K\>.P2** Each VM returned its own nonce and no other VM's nonce.
- **T10.k\<K\>.P3** While all were alive (barrier), each VMM's open regular files ⊆ its own chroot's files, and the sets are pairwise disjoint.
- **T10.k\<K\>.P4** A process with VM i's uid/gid fails to open VM j's `in.img`, `out.img` and `vm.json` (every j ≠ i).
- **T10.k\<K\>.P5** All VMs are clean.
- IDs: T10.k2.P0, T10.k2.P1, T10.k2.P2, T10.k2.P3, T10.k2.P4, T10.k2.P5, T10.k4.P0, T10.k4.P1, T10.k4.P2, T10.k4.P3, T10.k4.P4, T10.k4.P5, T10.k8.P0, T10.k8.P1, T10.k8.P2, T10.k8.P3, T10.k8.P4, T10.k8.P5.

## T11: SIGKILL during execution
Cases: **A**, SIGKILL the VMM pid 2 s after READY (cleanup by fclib). **B**, SIGKILL the jailer immediately after spawn (cleanup by fclib; the exe at kill time is recorded). **C**, SIGKILL the VMM with cleanup skipped and a stray `sleep` left running under the VM uid (cleanup by `recover.py --apply`).
- **T11.\<case\>.P1** The killed process is gone.
- **T11.\<case\>.P2** `cgroup.procs` is empty after the VMM exit (or no cgroup was created yet).
- **T11.\<case\>.P3** The cgroup is removed. **T11.\<case\>.P4** The chroot is removed.
- **T11.\<case\>.P5** No mounts remain under the chroot base and no host fd references the VM id.
- **T11.\<case\>.P6** A new microVM then runs ok. For C, the recover remaining count is also 0 and the recover scan is empty.
- **T11.C.P0** The recover dry-run found ≥ 4 orphan items (chroot, cgroup, lease, stray process) and took no action.
- IDs: T11.C.P0, T11.A.P1, T11.A.P2, T11.A.P3, T11.A.P4, T11.A.P5, T11.A.P6, T11.B.P1, T11.B.P2, T11.B.P3, T11.B.P4, T11.B.P5, T11.B.P6, T11.C.P1, T11.C.P2, T11.C.P3, T11.C.P4, T11.C.P5, T11.C.P6.

## T12: reboot persistence (T12pre, `sudo reboot`, T12post)
- **T12pre.P1** Orphan VM state is present: chroot dir, cgroup dir, uid lease (VMM killed, cleanup skipped).
- **T12pre.P2** An extra orphan chroot dir is present.
- **T12post.P1** The host boot_id differs from the pre-reboot boot_id.
- **T12post.P2** Before setup, a launch is refused exactly when the prerequisites are NOT MET (expected: P04, because cgroups do not survive a reboot).
- **T12post.P3** After rerunning stage-2 setup, every prerequisite is MET.
- **T12post.P4** The recover dry-run finds both pre-reboot chroot dirs, and the orphan VM's cgroup no longer exists.
- **T12post.P5** `recover.py --apply` leaves nothing.
- **T12post.P6** One microVM runs ok.

## T13: missing prerequisites (simulated with env overrides only)
- **T13.P0** Control: with no overrides, every prerequisite is MET.
- **T13.P1, T13.P2, T13.P3, T13.P4, T13.P5** (in this order) Each of `no_kvm` (P01), `missing_jailer` (P06), `missing_cgroup_controller` (P04), `insufficient_memory_threshold` (P11) and `tampered_kernel_hash` (P07, a one-byte flip in a copy) has: target check NOT MET, overall NOT MET, launch refused and nothing spawned.
- **T13.P6** No chroot, cgroup, lease or process is left.

## T14: admission model
- **T14.P1, T14.P2, T14.P3, T14.P4, T14.P5** For each T13 condition (same order), the response is HTTP 503 `ISOLATION_UNAVAILABLE` and the budget file is byte-identical with the same mtime and inode.
- **T14.P6** With all prerequisites MET, the response is HTTP 200 and the budget goes 100 → 99.
- **T14.P7** With budget 0, the response is HTTP 429 and the file is unchanged.

## T15: TOCTOU review and demonstration
- Written analysis: `TOCTOU.md` (its sha256 is recorded in the evidence).
- **T15.P1** At time of check, prereq P08 is MET on a verified copy of the pinned rootfs.
- **T15.P2** After that copy is modified between the check and fclib's copy into the chroot, the run is refused with "post-copy hash differs from pin" and nothing is spawned.
- **T15.P3** The refused attempt is cleaned up. **T15.P4** No orphan state remains.
