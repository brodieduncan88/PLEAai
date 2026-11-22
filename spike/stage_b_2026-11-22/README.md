# PLEA Stage B: Firecracker-only isolation spike (owner run sheet)

**Status: nothing in this bundle that needs KVM has been executed.** The author had no KVM, no network
path to the target and no SSH access. Every result below must come from your run. The only things run
so far are listed in "What has and has not been executed" below (`selftest.out`, `checks.out`).

The spike uses Firecracker **v1.18.0** with its jailer, and nothing else: no gVisor, no fallback, no
second sandbox. Every unexpected state ends as NOT MET or BLOCKED. Synthetic data only.

## 0. Before you start

* **Instance.** EC2 c7i-flex.xlarge (4 vCPU, 8 GiB), Ubuntu 24.04 x86_64, NestedVirtualization enabled,
  SSH restricted to your IP.
* **Disk.** Use a gp3 root volume of **at least 30 GiB**. The default 8 GiB is too small, because T10
  runs 8 concurrent chroot copies of the rootfs.
* **What the bundle does not touch.** No IAM role is needed, and the bundle never queries the instance
  metadata service.
* **Budget.** Per-hour cost is small next to the US$100 / 5-day budget. Check current on-demand
  pricing and terminate as soon as you are done (section 5).

Copy the bundle to the host and make it root-owned. Prerequisite P13 refuses to run if the bundle path
is writable by non-root users.

```bash
scp stage_b.tar ubuntu@HOST:                       # from your machine
ssh ubuntu@HOST
sudo install -d -o root -g root -m 0755 /opt/plea-stage-b
sudo tar -C /opt/plea-stage-b --no-same-owner -xf ~/stage_b.tar   # add --strip-components=1 if the tar has a stage_b/ prefix
sudo chown -R root:root /opt/plea-stage-b && sudo chmod -R go-w /opt/plea-stage-b
cd /opt/plea-stage-b
sudo ./declare.sh          # writes declared/SHA256SUMS; prints its sha256
```

**Send `declared/SHA256SUMS` and the printed hash back to the author (or commit them) before running
stage 0.** This fixes the predicates in `DECLARATION.md` before execution. From then on,
`run_stage.sh` refuses to run if any bundle file changes or a file is added. Do not edit anything on
the host. If something must change, ask the author for a new bundle and declaration.

## 1. Run sheet (in order, all as root via sudo, from /opt/plea-stage-b)

Durations are rough estimates (never measured). Nested virtualisation makes everything slower.

| # | Command | Est. time | What it changes on the host |
|---|---|---|---|
| 1 | `sudo ./run_stage.sh stage0` | < 1 min | Nothing. Read-only facts: kernel, vmx, /dev/kvm plus KVM ioctls, cgroup v2, swap, limits, memory, disk, DMI product name. **If /dev/kvm is missing or not functional it writes `state/BLOCKED` and every later stage refuses.** Go to section 5. |
| 2 | `sudo ./run_stage.sh stage1` | 5–20 min | `apt-get install` of e2fsprogs, squashfs-tools, curl, ca-certificates, git and jq. Downloads about 0.5 GB from github.com and s3.amazonaws.com. Writes `/opt/plea-fc/{bin,images,share,work,pins.json}`. Verifies the release tarball (size + sha256 + published .sha256.txt) and the inner SHA256SUMS. Records whether git tag v1.18.0 is signed (never fails on this). Pins the kernel and rootfs on first download (trust on first use). Builds the read-only ext4 guest image with `/plea-init`. Python 3 missing from the guest gives BLOCKED. Option: `sudo ./run_stage.sh stage1 --kernel 6.18` uses vmlinux-6.18.62 instead of 6.1.188. |
| 3 | `sudo ./run_stage.sh stage2` | < 2 min | Creates `/srv/plea-jailer` (root 0755) and `/run/plea-fc` (root 0700). Creates cgroup `/sys/fs/cgroup/plea-spike` with +cpu +memory +pids for its children. Enables those controllers in the root `cgroup.subtree_control` if missing. Runs `swapoff -a` if swap is active (fstab is not edited). Runs every prerequisite check and the jailer/firecracker `--help` flag check. **Rerun after any reboot or stop/start.** |
| 4 | `sudo ./run_stage.sh T01` … `T11` | 1–15 min each | Each launches microVMs as an unprivileged uid/gid from 64000–64999 under the jailer. It creates and then removes `/srv/plea-jailer/firecracker/<id>/`, `/sys/fs/cgroup/plea-spike/<id>` and `/run/plea-fc/leases/<uid>`. T05–T07 deliberately exhaust **guest** CPU, memory, processes and fds within the caps in `DECLARATION.md`. T11 SIGKILLs VMMs and runs `recover.py --apply`. |
| 5 | `sudo ./run_stage.sh T12pre`, then `sudo reboot`, reconnect, `cd /opt/plea-stage-b && sudo ./run_stage.sh T12post` | 5 min + reboot | Pre deliberately leaves orphan chroot/cgroup/lease state. Post records prerequisites, reruns the stage-2 setup itself, runs `recover.py --apply`, then runs one microVM. |
| 6 | `sudo ./run_stage.sh T13`, `T14`, `T15` | 3–10 min each | Create and delete `/opt/plea-fc/sim` (simulated missing prerequisites, a budget file, a copy of the rootfs). Nothing real is removed. |

Shortcut: `sudo ./run_stage.sh all-tests` runs T01–T11 and T13–T15 one after another (roughly 1–2 h).
T12 is always run by hand because it needs a reboot.

Useful commands:

* `sudo ./run_stage.sh prereq` runs all prerequisite checks.
* `sudo ./run_stage.sh recover` is a dry-run orphan scan.
* `sudo ./run_stage.sh recover-apply` cleans orphans. It refuses while a VM is running.
* `sudo ./run_stage.sh selftest` runs the no-KVM unit tests.

Each run prints `[Txx] verdict MET|NOT MET|BLOCKED|ERROR` and writes
`evidence/<UTC>-<stage>/`. That folder holds `<test>.json`, `stage.log`, `journal_k.txt`,
`dmesg_tail.txt`, a recover dry-run, `boot_id` and `SHA256SUMS`. Quick summary:
`sudo grep -h '"verdict"' evidence/*/T*.json`. A NOT MET is a valid result: **do not retry until it passes**.

## 2. If something goes wrong

* **BLOCKED at stage 0 or 1.** Stop. Do not try a weaker sandbox. Collect (section 4) and tear down (section 5).
* **After a reboot or a stop/start,** cgroups and `/run` are gone, so prerequisites fail closed. Run `sudo ./run_stage.sh stage2`.
* **Leftover state.** `sudo ./run_stage.sh recover` lists it. `sudo ./run_stage.sh recover-apply` removes it. Only processes in uid range 64000–64999 are ever killed.
* **Timeouts.** Every stage has an outer timeout, and `exit_code` 124 means it fired. Every microVM has a guest timeout and a host watchdog that SIGKILLs its process group.
* **Host unresponsive.** The caps are chosen to keep the host usable, but that has not been verified. If it happens, stop/start the instance from the console, then run `stage2` and `recover-apply`, and report it. It is itself a result.

## 3. What the tests are (predicates are in DECLARATION.md; the TOCTOU analysis is in TOCTOU.md)

| Test | What it covers |
|---|---|
| T01 | Jailer start: `--help`, argv, uid/gid, chroot, cgroup |
| T02 | Unprivileged VMM, seccomp mode 2 on all threads, CapEff 0, cgroup membership and limit files, rlimits, exe hash |
| T03 | Deterministic stdlib workload; hash compared with a host reference |
| T04 | N=20 latency distribution |
| T05 | CPU, memory, process and fd limits |
| T06 | Host responsiveness and a second VM during each exhaustion |
| T07 | D37: a million descriptors in the guest vs host `file-nr` (ratio reported; host usage is **not** claimed unchanged) |
| T08 | Console bounding, disk bound, fsize |
| T09 | Payload hash, truncation, malformed length prefixes, read-only input |
| T10 | K=2/4/8 concurrency and cross-VM separation |
| T11 | SIGKILL of the VMM and the jailer, plus recover |
| T12 | Reboot |
| T13 | Simulated missing prerequisites |
| T14 | Admission 503 / budget |
| T15 | TOCTOU demonstration |

MicroVM isolation does not remove host-wide resource limits. Host memory, `fs.file-max`, `pid_max`,
disk and CPU stay shared, and the tests measure the host impact rather than assume it away.

## 4. Copy back

```bash
sudo ./collect.sh                 # prints /tmp/plea-stage-b-evidence-<UTC>.tar.gz and its sha256
scp ubuntu@HOST:/tmp/plea-stage-b-evidence-*.tar.gz .      # from your machine; check the sha256
```

Send the tarball, its sha256 and the `declared/SHA256SUMS` hash from step 0.

## 5. Teardown (do this even if everything was BLOCKED)

1. Collect and copy back the evidence first (section 4), and verify the sha256 locally.
2. **Terminate the instance** (EC2 → Instances → Terminate). Stopping it is not enough.
3. Delete everything created for it:
   * EBS volumes that did not auto-delete (Volumes → state "available")
   * any snapshots or AMIs
   * the security group(s)
   * the key pair, and the local private key file
   * any Elastic IP
4. A day later, check Billing → Cost Explorer for leftovers.

## 6. What has and has not been executed

**Executed by the author** on a build host with no KVM (Linux 6.18, Python 3.11, running as root; the
target is Python 3.12):

* `selftest.py`: the bounded reader, the length-prefix codec and result parser, and the guest init's
  bash wire functions run against regular files. Also prereq on fake paths, the admission 503 rule,
  recover.py on a temp tree, the post-copy hash refusal, flag evaluation, argv/boot-args, the
  declaration-ID coverage check and pidfd-guarded kills.
* `py_compile` on all Python, `bash -n` on all shell scripts, and a declare → verify → tamper → refuse
  cycle of `declare.sh`/`run_stage.sh` in a temporary copy.
* Output is in `selftest.out` and `checks.out`.

**Never executed:**

* stage0–stage2 on the target, apt, every download, `fetch.py`, and `setup_host.py`
* the jailer, firecracker, the guest kernel and rootfs, and `/plea-init` as PID 1
* every test T01–T15, and `recover.py` against real cgroups and jails

No isolation result is claimed.

## 7. Assumptions checked at run time (fail closed if wrong)

* The jailer accepts `--id --exec-file --uid --gid --chroot-base-dir --cgroup-version 2
  --parent-cgroup <name> --cgroup <file>=<value>` (repeatable) and `--resource-limit fsize=…` /
  `no-file=…` (repeatable), followed by `--` and the firecracker args. It names the chroot
  `<base>/<basename of exec-file>/<id>/root`. It creates the cgroup `/sys/fs/cgroup/<parent>/<id>`.
  It tolerates a pre-created chroot dir with the kernel, rootfs, drives and `vm.json` placed in it
  (Firecracker's own test framework does this). Without `--daemonize`/`--new-pid-ns` it execs
  firecracker in place, so the jailer pid is the VMM pid. Checked by: T01, T02 and the `--help` parse
  (stage2, every test gate).
* Firecracker accepts `--config-file /vm.json --no-api`; if `--no-api` is absent, `--api-sock` inside
  the chroot is used instead, though that path is untested. The `vm.json` keys are `boot-source`,
  `drives`, `machine-config`. It applies seccomp filters by default (T02.P2). It exits with code 0 on
  a guest reboot (T05.P3). It orders the drives rootfs=vda, input=vdb, output=vdc (`/plea-init`
  verifies vdb is read-only and vdc read-write, else REJECT_DEV). It turns a write past RLIMIT_FSIZE
  into an error or exit, not a host-side write (T08.P6).
* `cpu.max=<quota>` without a period keeps the default 100000 µs period (T02.P5).
  `memory.swap.max` exists (swap accounting).
* The KVM capability numbers in `prereq.py` come from `linux/kvm.h`. Stage 0 cross-checks them if the
  header is installed.
* The CI rootfs contains python3 with its stdlib, bash, coreutils, util-linux `setpriv`/`blockdev`, and
  mount (stage 1 checks this; otherwise BLOCKED). The guest kernel has devtmpfs, tmpfs and serial
  console support.

## 8. Known gaps

* **Authenticity.** Only transfer integrity is verified. The release checksum comes from the same
  origin, the git tag signature is only recorded, and the CI kernel/rootfs are trust-on-first-use.
* **Jailer isolation options.** `--new-pid-ns`, `--netns` and `--daemonize` are not used (the VM has no
  network device). "Killing the jailer" therefore means killing it before or while it execs (T11.B).
* **Cgroup placement.** The parent cgroup is created directly under the root cgroup, outside systemd's
  delegation. systemd normally leaves foreign cgroups alone, but this is unverified.
* **Probes and thresholds.** The host probe measures process-spawn latency, not SSH or network. The
  thresholds (250 ms p95, 512 MiB free, ratio < 0.01) are declared judgments, not derived limits.
* **T10 barrier.** The barrier holds each VM's monitoring loop until all K are READY, which can delay
  that VM's watchdog by up to 120 s.
* **T15.** The demonstration covers the source-changed-before-copy window only. The copy-to-open window
  and root-level races are residual (TOCTOU.md).
* **admission.py** is a model of the rule, not PLEA's service code.
