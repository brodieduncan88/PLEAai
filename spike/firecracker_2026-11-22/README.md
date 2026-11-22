# PLEA Firecracker spike (internal engineering; not independent validation)

Firecracker is the only candidate engine. Every harness script calls `fc_lib.require_prereqs()` and exits 2 (REFUSED) if any
prerequisite fails. There is no fallback. Scripts marked WRITTEN, NOT RUN have never been executed on a KVM host.

Pinned versions: `pins.json` is EMPTY by design. Candidate release v1.12.1 (UNVERIFIED as "current": api.github.com and
/releases/latest returned HTTP 403 in the authoring session). Its tgz SHA-256 observed here, matching the same-origin checksum file:
`0a75e67ef6e4c540a2cf248b06822b0be9820cbba9fe19f9e0321200fe76ff6b`; extracted binary SHA-256 `b99ea49b8d8b7bfa307d3845585d6a97f7642aa17a985749900370070d8ca930`.
Checksum URL pattern: `https://github.com/firecracker-microvm/firecracker/releases/download/<vX.Y.Z>/firecracker-<vX.Y.Z>-x86_64.tgz.sha256.txt`.
The owner confirms the release on the KVM host, then fills pins.json from `guest_image/fetch_artifacts.sh` output.

| Script | Purpose | Status |
|---|---|---|
| `prereq.py` | Prerequisite checker (stdlib; JSON + human lines; exit 1 if any NOT MET) | RUN here (all NOT MET, as expected) |
| `admission_demo.py` | PROTOTYPE admission rule + counting-stub tests | RUN here (5 tests pass) |
| `harness/fc_lib.py` | VMM start via API socket, per-VM cgroup v2 limits, sampling, cleanup | NOT RUN (refusal path only) |
| `harness/bench_latency.py -n N` | Cold start = Popen to guest SPIKE_BEGIN; total = Popen to VMM exit; overhead = total minus guest job time; native baseline. Writes bench_latency.json | NOT RUN |
| guest `jobs/workload.py` | json + decimal + hashlib stdlib workload, deterministic digest | RUN natively only |
| `harness/limits_test.py` | Reads back guest memory/vCPU (GET /machine-config), cgroup memory.max/pids.max/cpu.max on the VMM, guest `ulimit -n` (cmdline `spike.nofile=256`); runs fork bomb (bounded 20000), memory balloon, fd and mmap exhaustion in the guest | NOT RUN |
| `harness/host_exhaustion.py` | `/proc/sys/fs/file-nr` and MemAvailable before/during/after guest fd/mmap exhaustion; the VMM's own host fds, threads, RSS per VM. Measures only; no claim that host file-table limits vanish | NOT RUN |
| `harness/crash_cleanup.py` | kill -9 the VMM mid-run; reports cgroup populated/procs, vm dir, socket, `fcspike*` taps; runs recovery; reports clean or not | NOT RUN |
| `harness/recover_orphans.py [--apply]` | Finds/removes `spike-*` cgroups (via cgroup.kill), per-VM dirs, `fcspike*` taps. Dry run default. Needs no KVM | file logic RUN here (temp dir); cgroup/tap paths NOT RUN |
| `harness/concurrency.py -k K` | K VMs at once; per-VM timings; peak host fds/RSS/file-nr totals; cleanup check | NOT RUN |
| `host_config/` | udev rule (kvm group 0660), `plea-spike-run@.service` (Delegate=yes), `install.sh`, `check_after_reboot.sh` | syntax only |
| `guest_image/` | `fetch_artifacts.sh`, `build_rootfs.sh` (debootstrap minbase + python3, ext4, read-only), `init.sh`, `jobs/` | syntax only |

Design notes. The guest has no network device (no tap is created by the harness). Rootfs is attached read-only and shared; the job is
chosen by kernel cmdline `spike.job=`; output returns on the serial console (stdout of the VMM, captured to `console.log`). The VMM is
born inside its cgroup (`preexec_fn` writes the pid to cgroup.procs before exec). Seccomp is left at Firecracker's default (never pass
`--no-seccomp`). The jailer is NOT used in this spike (see REPORT limitations). `pids.max` bounds VMM threads, not guest processes;
guest fork bombs are bounded by the guest kernel and guest memory.

Image build (Ubuntu 24.04 build host, root): `apt-get install -y debootstrap e2fsprogs`, then
`SNAPSHOT=<YYYYMMDDTHHMMSSZ> sudo -E guest_image/build_rootfs.sh` twice and compare the two `rootfs.ext4` SHA-256 values.
Kernel: `FC_VERSION=<vX.Y.Z> KERNEL_URL=<Firecracker CI kernel URL> guest_image/fetch_artifacts.sh` (CI kernel hash is trust-on-first-use).

Changing anything in this directory after a failed result is governed by VP-1 to VP-6; see `declared/` and `evidence/`.
