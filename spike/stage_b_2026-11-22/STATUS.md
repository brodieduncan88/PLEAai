# Stage B bundle: status

22 November 2026. **Preparation only. Nothing in this folder has been run on a KVM host, so no isolation result exists.**
It is not evidence for a permanent Firecracker integration, which the owner has not approved.

- **Written by:** an AI agent at the author's instruction, for the owner to run on the owner's EC2 host. It is to be
  reviewed before it runs. `declared/SHA256SUMS` is not yet made: `sudo ./declare.sh` makes it after review and before
  stage 0, and `run_stage.sh` refuses any file whose hash has changed since.
- **Self-tested here** (no KVM; Python 3.11 as root; the host will have 3.12). `selftest.py` passed 24 of 24
  (`selftest.out`), and `checks.sh` was all OK (`checks.out`). On this machine stage 0 and T01 correctly answer
  BLOCKED.
- **The release chosen:** Firecracker v1.18.0, supported under the project's release policy as of 22 November 2026.
  v1.12.1 is not used. The research behind it is in `RELEASE_RESEARCH.md`.
- **Assumptions about the jailer and Firecracker** that must be confirmed on the host, and the known gaps, are in
  README.md. Each is checked at run time and fails closed.
- **The author cannot reach the host** (this environment allows no outbound SSH). The owner runs the stages and brings
  the evidence folder back.
