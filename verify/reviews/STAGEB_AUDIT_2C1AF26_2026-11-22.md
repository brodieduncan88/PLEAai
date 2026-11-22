# Stage B bundle, static security audit of commit 2c1af26 (22 November 2026)

This is the report as the reviewing agent returned it, unedited below the rule. It is a read-only internal review by a separate AI
agent instructed by the author, not independent validation. Nothing was run on KVM. The agent's scratch evidence (the expected
declaration file, the symlink demonstration and its output, and the network fetches) is kept in `stageb_audit_2c1af26/`.

The author recomputed the declaration hash separately, from `git archive 2c1af26` and the bundle's own `bundle_files` rule: 52
files, `3218f01da274ae470b5f02e217861fdead6ab8d1686a0567578a144daff08d44`, the same bytes as the agent's file. That hash is of
the bundle at 2c1af26 only. The later `RELEASE_RESEARCH.md` update (CVE-2026-122192) changes the bundle, so it does not hold for
any later commit.

---

## Stage B Firecracker bundle (commit 2c1af26): static security audit

**Recommendation:**
- **`sudo ./declare.sh`: GO.** It is safe for the host.
- **Stage 0: GO.** It only reads.
- **Stage 1 and later on this commit: NO-GO.** One HIGH and three MEDIUM corrections come first, then a new commit, a re-review and a new declaration.

**Nature of this review.** I am an internal reviewer working at the author's instruction, reading the code without running it on a host. This is not independent validation. Nothing ran on KVM. I did not run the jailer, Firecracker, stage 0–2 or any test against real cgroups.

### What I ran
All of it ran in the scratch folder `/tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad/stageb_audit/`.
- `git archive 2c1af26 spike/stage_b_2026-11-22 | tar -x` into `.../stageb_audit/src/`. The repository and the main checkout were not modified, and nothing was committed.
- `bash -n` on the 8 `.sh` files and `guest/plea-init`: all ok.
- `py_compile` on all 36 `.py` files, with bytecode written to the scratch `pyc/` folder: all ok.
- shellcheck is not installed, so it was not run.
- `selftest.py`, after reading it and confirming it writes only under `tempfile.mkdtemp`. I set `TMPDIR` to the scratch `tmp/` folder and ran `python3 -I -B` from outside the bundle. Result: 24/24 PASS on Python 3.11, as root, with no `/dev/kvm`. Afterwards `/opt/plea-fc`, `/srv/plea-jailer` and `/run/plea-fc` did not exist.
- `.../stageb_audit/expected_SHA256SUMS`: the declaration file computed from the commit. I copied `bundle_files` and `sha256sum` by hand; I did not run `declare.sh`.
  - 52 files.
  - The `sha256sum` of the SHA256SUMS file is `3218f01da274ae470b5f02e217861fdead6ab8d1686a0567578a144daff08d44`.
  - This matches only if the host tree holds exactly the commit's 52 files.
- `.../stageb_audit/scripts/symlink_demo.py`, run against scratch paths only. It demonstrates finding H1.
- Network, all through this environment's agent proxy:
  - WebSearch and WebFetch: the AWS bulletins and `cveawg.mitre.org`.
  - curl of the v1.18.0 `.sha256.txt`, `RELEASE_POLICY.md`, the v1.18.0 `CHANGELOG.md` and the S3 listing of the CI prefix.
  - The GitHub advisory page and `api.github.com` returned 403 because this session is bound to its own repositories. I could not read GHSA-48ww-rqpp-2mgm.

### Findings

**HIGH**

**H1. `fetch.py:228-238` (`build_rootfs`) follows symlinks inside the unauthenticated squashfs tree while running as root.**
- The squashfs is trust-on-first-use (TOFU). After `unsquashfs` as root into `/opt/plea-fc/work/tree`, these calls all follow symlinks:
  - `shutil.copyfile(init_src, tree/plea-init)` (l.230)
  - `os.chmod(tree/plea-init, 0o755)` (l.231)
  - `read_bounded(tree/etc/passwd)` (l.233)
  - `open(tree/etc/passwd|group, "a")` (l.235-238)
  - `os.makedirs(tree/{proc,...})` (l.228)
- **Scenario:** a tampered `ubuntu-24.04.squashfs` contains `/plea-init -> /etc/shadow` and `/etc -> /etc`. Root then:
  - overwrites host `/etc/shadow` with the init script and chmods it 0755 (world-readable; sudo and logins break);
  - appends a `plea:x:10001` line to host `/etc/passwd` and `/etc/group`.
- **Shown in scratch:** the victim file became 0755 with plea-init content, and the passwd victim gained the `plea` line.
- **Impact:** arbitrary host file overwrite and permission change from unauthenticated input. Likelihood is low (it needs control of the AWS-operated S3 object or of TLS). Impact is high. This is the same class as CVE-2026-1386.
- **Fix:**
  - Before touching the tree, `lstat` each of: `tree/etc` must be a real directory; `etc/passwd` and `etc/group` must be regular, not symlinks, with `st_nlink == 1`; `tree/plea-init` must not exist; each of proc/sys/dev/run/tmp must be absent or a real directory.
  - Create plea-init with `os.open(O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW)` and set its mode with `fchmod`.
  - Open passwd and group with `O_NOFOLLOW`, using `dir_fd` on an `O_DIRECTORY|O_NOFOLLOW` fd of `tree/etc`.
  - Refuse (NOT MET) on any violation.

**MEDIUM**

**M1. Orphaned VMMs when the harness dies on a signal.** (`fclib.py:539-541` `start_new_session=True`; `run_stage.sh:60` `timeout --kill-after=30`; `tests/common.py:133-142`)
- **Scenario:** a stage hits its outer timeout (SIGTERM, then SIGKILL), or the SSH session drops (SIGHUP).
- **What happens:**
  - Python's default action exits without running `finally`, so `cleanup()` never runs.
  - The VMM is in its own session and survives `timeout`'s process-group kill.
  - It then runs until the guest reboots. A hostile guest could keep it running indefinitely, inside cgroup limits.
  - `run_stage.sh` only records a recover dry-run.
- **Fix:**
  - Install SIGTERM/SIGHUP handlers that raise `SystemExit` in `common.main`, `setup_host` and `fetch`.
  - In `cleanup()` and `recover --apply`, write `1` to `<cg>/cgroup.kill` (cgroup v2, kernel 5.14 or later) before waiting.
  - In `run_stage.sh`, when the exit code is 124 or above 128, run `recover.py --apply`. It already refuses while a launch holds the lock.
  - README: run stages inside `tmux` or `screen`.

**M2. The CI kernel and rootfs have no pinned hash or size, and the first download is accepted on magic bytes alone.** (`config.py:26-33`, `fetch.py:153-172`)
- This feeds root-side processing (`unsquashfs`, then H1).
- Sizes I observed via the S3 listing today, through the proxy:

| object | bytes |
| --- | --- |
| `vmlinux-6.1.188` | 45,188,080 |
| `ubuntu-24.04.squashfs` | 98,885,632 |
| `vmlinux-6.18.62` | 27,942,928 |

- The ETags are multipart, so they cannot serve as MD5 checks.
- **Fix:** pin the sizes, and preferably SHA-256 values measured from a second vantage point, in `config.CI`. Refuse on mismatch.

**M3. Nothing on the host ties the declaration to commit 2c1af26.** (`declare.sh:13`)
- `declare.sh` hashes whatever is on disk, so the "send back" step is the only binding.
- **Fix:** add a README step before stage 0. The owner compares the printed hash with a value the author publishes outside the bundle: `3218f01d…8d44` for the current commit, recomputed after the corrections. If they differ, stop.

**LOW**
- **L1. `guest/plea-init:100,118` and `48`:** the backstop that kills leftover payload processes is cancelled when the payload exits normally. A payload child that escaped via `setsid` survives into result writing.
  - It can read the nonce from `/run/plea/body`, which is 0644 because of `umask 022`.
  - In console mode (T08) it can then forge `PLEA_DONE`. This affects only test integrity: `ok` still needs the root-written `out.img`.
  - Fix: run `kill -KILL -1; sleep 0.2` from PID 1 after `run_job`, and use `umask 077` for the files in `/run/plea`.
- **L2. `fclib.py:75` `read_result`:** it opens `out.img` with `open()`, which follows symlinks. Whether the jailer makes the chroot root writable by the VM uid is unverified.
  - Fix: open with `O_NOFOLLOW`, then check with `fstat` that it is a regular file, owned by the VM uid, with `nlink == 1` and size equal to `out_size`.
- **L3. The VMM runs in the host network namespace** (no `--netns`; a known gap in the README), so defence in depth rests on seccomp alone.
  - Optional fix: create an empty netns and pass `--netns`.
- **L4. T02 checks only `Seccomp: 2`.** It does not assert `NoNewPrivs == 1` or the filter count.
  - An "FC-03 io_uring seccomp bypass" appears only on a secondary blog with an untraceable citation. It is unverified.
- **L5. `setup_host.py:36-50`:** if enabling a controller fails, the `OSError` is uncaught and no `stage2_setup.json` is written. This fails closed, but leaves no evidence.
- **L6. `fetch.py:283`:** `--kernel` given without a value raises `IndexError` before the `try`, so no evidence is written.
- **L7. P13 (`prereq.py:162`)** checks only the directories on the bundle path, not the files or subdirectories inside it. The README's `chown -R` / `chmod -R go-w` covers this if followed.
- **L8. `collect.sh:8-11`:** root writes a predictable name in `/tmp`. `protected_symlinks` and a single-user host mitigate it.
- **L9. README §1 accuracy:**
  - The real download is about 0.16 GB plus a depth-1 git fetch, not about 0.5 GB.
  - The listed hosts omit the GitHub release-asset redirect host and the Ubuntu apt mirrors.
  - Host agents still use the network (SSM, `unattended-upgrades`, snapd, chrony, IMDS via cloud-init).
  - Recommend requiring IMDSv2 at launch, and deciding whether to pause `apt-daily` and `unattended-upgrades` during the spike: they can lock apt or change the kernel before the T12 reboot.
- **L10. `stage1_fetch.sh:8-9`:** apt can lose the lock to cloud-init or apt-daily at first boot. Fix: `-o DPkg::Lock::Timeout=600`, or `cloud-init status --wait` first.
- **L11. `recover.py:51-60`:** `--apply` removes every directory two levels under `/srv/plea-jailer`, whatever its name. Restrict it to `plea-*`.
- **L12. `unsquashfs` parses unauthenticated input as root.** squashfs-tools 4.6.1 on Ubuntu 24.04 includes the 2021 traversal fixes. M2 reduces the exposure.
- **L13. `fclib.py:633`:** a deeply nested JSON header from a hostile guest raises `RecursionError`, which the `(OSError, ValueError)` handler misses. The generic handler still fails closed and cleanup still runs. Catch it explicitly.
- **L14. Git tag check:** even "signed, verified" would not authenticate CI-built release binaries. Without imported keys it will report "signed, NOT verified". The README wording ("only recorded") is accurate.

### Review areas 1–13
1. **declare.sh** invokes `readlink`, `dirname`, `mkdir -p declared`, `find`, `sort`, `xargs sha256sum`, `mv`, `wc`, and `verify_declared` (`sha256sum -c`, `diff`, `awk`, `sed`).
   - It writes only `declared/SHA256SUMS{.tmp}` and uses no network.
   - On a re-run it only verifies. `--force` re-declares.
   - `run_stage.sh` checks the root uid, verifies every hash and that no file is extra or missing, unsets `PLEA_*`, checks `state/BLOCKED` and the stage gating, then runs under `timeout`.
   - `find -type f` ignores symlinks, so an added symlink would go undetected. Only root can add one.
2. **Downloads and provenance.**
   - The release `.tgz` is checked against a pinned size and SHA-256 before extraction. Extraction uses `tar filter="data"`. The inner SHA256SUMS and the installed binaries are checked against pinned constants. That is sound.
   - I fetched `.sha256.txt` today and it reads `1ac8eec866dd5eea14efecf6323e22b23eea24054545338a5b34bc5bca6623cd  firecracker-v1.18.0-x86_64.tgz`, matching the pin. I fetched it through the same kind of TLS-intercepting proxy the author used, so it is not an independent vantage point. I did not download the `.tgz` or check the inner hashes.
   - On the host, a match against the pin is a second, direct vantage point: it protects against network tampering, not against a compromised GitHub release.
   - The kernel and rootfs are TOFU. The README and TOCTOU.md say so accurately, and no claim is overstated.
   - `RELEASE_RESEARCH.md` is accurate. I verified the release-policy table and the "last two minor releases, up to 1 year / at least 6 months" wording.
   - Its line "security advisories: not determined" is now out of date (see the CVE section).
3. **Installation.** `/opt/plea-fc{,/bin,/images,/share}` is root 0755. firecracker and jailer are `root:root 0755`, not setuid. The seccomp JSON is 0644, the images 0444, `pins.json` 0644, and `work/` 0700. P05/P06 re-check root ownership, mode ≤ 0755 and the hash.
4. **Network.** Stage 1 only:
   - apt mirrors, over HTTP with signed metadata;
   - github.com and its release-asset redirect host, HTTPS only via `--proto =https`;
   - `git ls-remote` and fetch to github.com;
   - s3.amazonaws.com.

   Nothing in the bundle uses the network after stage 1. The guests have no network devices. The bundle never touches IMDS.
5. **Filesystem impact.** See the table below.
   - Every target is a constant path. `PLEA_*` overrides are stripped by `run_stage` and refused by the non-simulation tests.
   - `safe_rmtree` refuses symlinks and paths outside the base, and needs the fd-based `rmtree`.
   - `place_file` and `_write_new` use `O_EXCL|O_NOFOLLOW`.
   - The exception is H1.
6. **Privilege and jailer configuration.**
   - The jailer starts as root with `setgroups([])` (`extra_groups=[]`), a minimal `PATH`, `close_fds` and a new session.
   - The jailer gets `--uid`/`--gid` from 64000–64999 (checked against passwd, with a lease), `--chroot-base-dir /srv/plea-jailer` (root 0755), and cgroup v2 `--parent-cgroup plea-spike`.
   - Limits: `cpu.max`, `memory.max` (guest + 192 MiB), `memory.swap.max=0`, `pids.max=64`, and `--resource-limit` `fsize` 16 MiB and `no-file` 1024.
   - The default seccomp is kept (`--no-seccomp` is refused). `--no-api` is used.
   - Not used: `--netns` (L3), `--new-pid-ns`, `--daemonize`.
   - T02 verifies the uid/gid fields, empty groups, CapEff/CapPrm 0, Seccomp 2, the cgroup files and limits, and the exe hash. NoNewPrivs is recorded but not asserted.
7. **cgroups.**
   - Set: cpu, memory and pids in the root and parent `subtree_control`, and the per-VM files via the jailer.
   - Verified: P03/P04 at every gate; the values read back at READY (T02.P5); the VMM's membership (T01.P3/T02.P4).
   - If a controller is absent: NOT MET and refusal. Stage 2 can traceback (L5).
   - The io controller is not used.
   - The parent cgroup sits outside systemd's delegation (a known gap).
8. **T07 (D37 host file-table test).** It is bounded: guest timeout 180 s, host watchdog 260 s, `memory.max` 1216 MiB, 1 CPU, and a bounded host sampler. It changes no host sysctl.
   - Its predicate measures host `file-nr[0]` from READY to peak, divided by the descriptors the guest opened, with a threshold of 0.01. Guest descriptors are guest-kernel objects, so this is expected to pass. That is a valid but weak signal; T07.P3 (VMM fd count change ≤ 2) is the more meaningful check.
   - Host noise from other processes is well under the 10,000-descriptor tolerance this implies.
   - It cannot endanger an 8 GiB host.
9. **Input and output drives.**
   - Input `in.img` is `root:uid 0440`, configured read-only, checked read-only by the guest, and its hash is re-checked after the run.
   - The rootfs is 0444. Output `out.img` is `uid 0600`, of fixed size.
   - The guest parser checks the top bit, cap, device bound and zero length. The host parser checks the header cap, version, status regex, lengths and exact size.
   - Every process with the VM uid is killed before the host reads the result.
   - Concerns: L1, L2 and L13.
10. **Crash cleanup.**
    - Kills go through a pidfd with a uid check.
    - Cleanup does `killpg` only on an unreaped child, kills uid-range processes, removes the cgroup only when empty, then `safe_rmtree`, then releases the lease.
    - `recover --apply` takes the lock exclusively before rescanning, and kills only uid-range processes.
    - After a reboot, `/run` and the cgroups are gone and the chroots remain. T12 covers this.
    - The gap is M1.
11. **Teardown (README §5)** is adequate: terminate rather than stop, then delete volumes, snapshots and AMIs, security groups, key pair and Elastic IPs, and check billing.
    - Add: confirm `DeleteOnTermination` on the root volume, check EC2 Global View for other regions, and set an AWS Budgets alert at the US$100 ceiling.
    - Left on the host if it is not terminated: `/opt/plea-stage-b`, `/opt/plea-fc`, `/srv/plea-jailer`, `/run/plea-fc`, the cgroup `plea-spike`, the apt packages, swap off (not persisted), and `/tmp/plea-stage-b-evidence-*.tar.gz`.
12. **CVE** (next section).
13. **Other:** the selftest reproduces 24/24. The KVM ioctl and capability numbers look correct from memory.

### Privileged commands and filesystem impact
| Where | Operation (as root) | Target | Can it be redirected? |
|---|---|---|---|
| `declare.sh` | `mkdir`, write, `mv` | `<bundle>/declared/` | no |
| `run_stage.sh` | `mkdir`, write, `rm -f state/<stage>.ok`, `journalctl`, `dmesg` | `<bundle>/evidence`, `<bundle>/state` | no |
| `stage0` | reads; `KVM_CREATE_VM` (fd closed) | `state/BLOCKED` | no |
| `stage1` | `apt-get install` | the 6 listed packages | no |
| `fetch.py` | `rmtree` | fixed paths under `/opt/plea-fc/work` | no |
| `fetch.py` | `chown`/`chmod` | `/opt/plea-fc` dirs, binaries, images, pins | no |
| `fetch.py` | `unsquashfs` | `work/tree` | no |
| `fetch.py` | `mkfs.ext4` | a regular `.build` file (not a block device) | no |
| `fetch.py` | copy, chmod, append into the tree | `tree/plea-init`, `tree/etc/passwd`, `tree/etc/group` | **yes, via H1** |
| `setup_host` | `makedirs`, `chown`, `chmod` | `/srv/plea-jailer`, `/run/plea-fc{,/leases}` | no |
| `setup_host` | `+cpu +memory +pids` | root and `plea-spike` `subtree_control` | no |
| `setup_host` | `mkdir` | `/sys/fs/cgroup/plea-spike` | no |
| `setup_host` | `swapoff -a` (only if swap is active; not persisted) | swap | no |
| `fclib` | `mkdir`; `O_EXCL` writes; `fchown` to the VM uid | chroot dirs and files | no |
| `fclib` | `rmdir` | the VM cgroup | no |
| `fclib` | `safe_rmtree` | `<base>/firecracker/<id>` | no |
| `fclib` | `unlink` | the lease | no |
| `fclib` | SIGKILL | its own pgid / uid-range pids | no |
| `recover --apply` | SIGKILL (uid range only) | processes | no |
| `recover --apply` | `umount -l` | under the chroot base | no |
| `recover --apply` | `rmdir` cgroups, `rmtree` chroots, `unlink` leases | the above | no; L11 |
| T11 | spawns `sleep` as the VM uid | — | no |
| T12pre | creates an orphan dir | under the chroot base | no |
| T13/T14/T15 | create and `rmtree` | `/opt/plea-fc/sim` | no |
| `collect.sh` | `tar`, `chown` to the sudo user | `/tmp/plea-stage-b-evidence-*` | L8 |

No `mkfs` touches a device. Nothing is written to `/etc`, `fstab` or sysctls.

### CVE-2026-122192
**Verified from primary sources:**
- AWS bulletin 2026-169-AWS, read in summarised form (the fetch tool would not reproduce the full text): https://aws.amazon.com/security/security-bulletins/2026-169-aws/
- The CVE record, quoted from https://cveawg.mitre.org/api/cve/CVE-2026-122192: "Improper handling of a failed memory remap in Firecracker versions 0.23.0 through 1.16.1 … might allow a guest user with root privileges to read or modify Firecracker VMM process memory … via balloon or virtio-mem discard requests on microVMs restored from a snapshot with the File memory backend … if the host fails to create the replacement mapping. … users should upgrade to Firecracker 1.16.2 or 1.17.0 and later."
- Other record details: affected 0.23.0 up to but not including 1.16.2; CVSS 3.1 7.5; CWE-390 and CWE-825; published 2026-11-04; assigner AMZN.
- The bulletin adds: AWS services, including Lambda, are not affected. Workarounds are the Uffd backend, overcommit and discard-size limits, and keeping the memcg OOM killer enabled.

The owner's statement is accurate. The v1.17.0 CHANGELOG entry #6174 ("virtio-mem leaving unplugged memory writable by the VMM … aborts if the re-map fails") is consistent with it.

**Not verified:** GHSA-48ww-rqpp-2mgm (403 from here), and the "FC-03" seccomp-bypass chain, which appears only on a secondary blog.

**Relevance to this bundle: none.**
- v1.18.0 is outside the affected range.
- Each prerequisite is absent from `vm.json`: no snapshot restore, no File memory backend, no balloon, no virtio-mem.
- Also absent: network devices, vsock, MMDS, and the API socket (`--no-api`).

**Two other 2026 Firecracker advisories found incidentally.** Neither covers v1.18.0 by its stated range.
- CVE-2026-1386 (jailer symlink file overwrite): fixed in 1.14.1 and 1.13.2. The AWS bulletin 2026-003-AWS was read.
- CVE-2026-5747 (virtio PCI out-of-bounds write): fixed in 1.14.4 and 1.15.1. Known from search results only.

The GitHub advisories list was unreachable, so I cannot confirm there are no others.

### Corrections required before stage 1
1. Fix H1 in `fetch.py`, as described under H1.
2. Fix M1: signal handlers, `cgroup.kill` in cleanup and recover, auto-recover after a timeout or signal exit, and a `tmux` note in the README.
3. Fix M2: pin the sizes, and preferably hashes, of the CI kernel and squashfs in `config.CI`.
4. Fix M3: add the README step to compare the declared hash with an author-published value.

Recommended, not blocking: L1, L2, L5, L6, L10, IMDSv2, and updating the advisories section of `RELEASE_RESEARCH.md`.

After the corrections: a new commit, a re-review, then a new expected declaration hash.

### GO / NO-GO
- **`sudo ./declare.sh` on the proposed EC2 host: GO.** It reads bundle files and writes only `declared/` in the root-owned bundle. It uses no network and makes no system changes.
  - Procedurally, declare the corrected bundle. Declaring 2c1af26 is harmless but freezes a bundle that needs fixing.
  - If it is run on 2c1af26, the printed hash must equal `3218f01da274ae470b5f02e217861fdead6ab8d1686a0567578a144daff08d44`.
- **Stage 0: GO.** It is a read-only host-facts check and a useful early test of whether nested KVM works on c7i-flex; I have not verified that it does. Its only writes are `evidence/` and `state/` inside the bundle.
- **Stage 1 and later on commit 2c1af26: NO-GO** until corrections 1–4 are made. H1 is a root-level host-file overwrite reachable from unauthenticated downloaded content, and M1 can leave VMMs running unsupervised.

Task size note: Opus-level review was enough; Fable is not needed.
