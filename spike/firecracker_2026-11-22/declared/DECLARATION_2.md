# DECLARATION 2 (written before run 2; supersedes nothing: run 1 results are kept and reported)
Run 1 declaration SHA-256: 6a1897231413f141d3b6045543352494ce927eaae0ff38c273abbb0e28f7a9f5. See evidence/CHANGE_RECORD_1.md.
Only tests whose run-1 result deviated are re-run.

| ID | Test | Expected outcome on THIS machine |
|----|------|----------------------------------|
| T3b | ast.parse of all 16 .py files (2 top-level, 7 harness, 7 guest jobs); `bash -n` of every .sh | 16 "py ok" lines and 7 "sh ok" lines (guest_image x3, host_config x2 (install.sh, check_after_reboot.sh), run_declared.sh, run_declared_2.sh); exit code 0. Syntax only. |
| T5b | Follow redirects (-L, max 3) for firecracker-v1.12.1-x86_64.tgz and its .sha256.txt (v1.12.1 is an UNVERIFIED candidate; "latest" cannot be checked because api.github.com and /releases/latest return 403) | Prediction, uncertain: the 302 shows the first hop is allowed; the redirect target may be allowed (download succeeds, sha256 compared with the .sha256.txt, which comes from the same origin so it shows transport integrity, not authenticity) or refused by the proxy with 403. Either result is recorded verbatim. pins.json stays EMPTY regardless, because the current release was not verified. |
| T6b | If T5b downloaded and verified: extract into its own dir and run `<bin> --version` | Prints a line beginning "Firecracker v1.12.1". If T5b failed: NOT RUN. |
| T7b | If a binary exists: start `<bin> --api-sock S` with no KVM, GET `/`, then configure with dummy zero-filled kernel and rootfs files (NOT real images) and send InstanceStart | Prediction, uncertain: API socket appears and GET / answers; InstanceStart is rejected or the VMM exits with an error about the dummy boot source or about /dev/kvm. The exact message is recorded; I do not predict which. This test runs Firecracker directly, outside the prereq-gated harness, because showing the failure mode is its purpose. If no binary: NOT RUN. |
