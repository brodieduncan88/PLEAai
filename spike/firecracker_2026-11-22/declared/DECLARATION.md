# DECLARATION (written before any test was run)

Author: Claude (Sonnet 5.5) subagent. Machine: cloud container, no /dev/kvm, no vmx/svm flags, cgroup v1
(/sys/fs/cgroup is tmpfs), root, 4 CPU, x86_64, Python 3.11. Tests are executed by `run_declared.sh`; outputs go to `evidence/`.
These are internal engineering checks, not independent validation. Firecracker is the only candidate; nothing here tests another engine.

| ID | Test | Expected outcome on THIS machine |
|----|------|----------------------------------|
| T1 | `python3 -I prereq.py` | Exit 1. All seven checks NOT MET: kvm_device (no /dev/kvm), kvm_api_version (no device), cgroup_v2 (tmpfs, not cgroup2), cgroup_controllers (no cgroup.controllers), firecracker_binary (no binary; empty pin), guest_kernel and guest_rootfs (no files; empty pins). Valid JSON followed by human lines; no traceback. |
| T2 | `python3 -I admission_demo.py` | 5 unittest tests, all pass; the 503 cases show zero counted budget operations; control case shows exactly 1. The test that feeds real prereq.py output yields 503 with 0 budget calls. |
| T3 | py_compile of every .py; `bash -n` of every .sh | All pass. This is a syntax check only; it says nothing about behaviour on a KVM host. |
| T4 | `python3 -I -B guest_image/jobs/workload.py` natively | Prints one SPIKE_RESULT JSON line with a sha256 digest. Checks only that the workload script runs; says nothing about the guest. |
| T5 | Download of an UNVERIFIED candidate release tgz and its .sha256.txt from github.com (candidate v1.12.1 is not a pin; the release could not be checked because GitHub API access was refused earlier: HTTP 403 from the session proxy "GitHub access to this repository is not enabled for this session") | Refused by the proxy with HTTP 403; no file saved; checksum NOT verified. If it unexpectedly succeeds, I will report that and the checksum comparison honestly. |
| T6 | `firecracker --version` | NOT RUN (no binary, expected consequence of T5). |
| T7 | Start VMM API socket without KVM | NOT RUN (no binary). Expected failure mode on a binary-bearing machine is not predicted here. |
| T8 | Each of the five harness scripts (bench_latency, limits_test, host_exhaustion, concurrency, crash_cleanup) run on this machine | Each exits 2 printing `REFUSED: isolation unavailable` with the NOT MET list; no traceback; no VM started. |
| T8b | After T8 | No /run/plea-spike directory created; no cgroup changes (fail closed before side effects). |
| T9 | recover_orphans.py on a temp dir holding `spike-deadbeef/` (stale socket, dead pid) and an unrelated `keepme/` | Dry run lists the spike dir and removes nothing; `--apply` removes `spike-deadbeef` only; `keepme` survives. Tests file-removal logic only; the cgroup and tap paths are NOT exercised here. |
| T10a | prereq.py with a malformed pins file | Exit 1, no traceback; pin-dependent checks NOT MET with the parse error as reason. |
| T10b | prereq.py `--kvm /etc/hostname` (regular file) | Exit 1; kvm_device NOT MET "not a character device"; kvm_api_version NOT MET. |
| T10c | prereq.py `--kvm /dev/null` (a char device that is not KVM) | Exit 1; kvm_device MET (it is a char device and opens rw as root); kvm_api_version NOT MET (ioctl ENOTTY or similar), no traceback. This is a robustness probe and is not evidence of KVM. |
| T10d | prereq.py `--pins /nonexistent --firecracker /etc` (directory) | Exit 1; binary/kernel/rootfs NOT MET; no traceback. |

Not testable here (will be reported "NOT RUN"): cold start, overhead, limits, host exhaustion, crash cleanup with a live VMM,
concurrency, reboot persistence, image build, kernel download.

Acceptance rule: a test passes only if its observed result equals the expected outcome above. Any deviation is reported as a deviation.
Per VP-1 to VP-6, no expectation or code will be changed after seeing a result without first copying the failing source to `evidence/`
with SHA-256, recording the output and this declaration's hash, writing a change record, and writing a new declaration.
