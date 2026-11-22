#!/bin/bash
# Fetch pinned Firecracker release and the guest kernel; verify; print the hashes to put in pins.json.
# FC_VERSION (e.g. vX.Y.Z) and KERNEL_URL must be set deliberately; both are empty in the shipped config.
# Firecracker release assets (as recalled, VERIFY on the host): firecracker-${FC_VERSION}-x86_64.tgz and
# firecracker-${FC_VERSION}-x86_64.tgz.sha256.txt at
#   https://github.com/firecracker-microvm/firecracker/releases/download/${FC_VERSION}/
# Kernel: Firecracker's published CI kernel in s3://spec.ccfc.min/firecracker-ci/<ci-version>/x86_64/vmlinux-<ver>.
# List it with:  curl -s 'https://spec.ccfc.min.s3.amazonaws.com/?prefix=firecracker-ci/&list-type=2'   (or aws s3 ls --no-sign-request)
# No published checksum is known for the CI kernel: the hash below is trust-on-first-use, then pinned.
set -euo pipefail
: "${FC_VERSION:?set FC_VERSION}"; : "${KERNEL_URL:?set KERNEL_URL}"
ROOT=$(cd "$(dirname "$0")/.." && pwd); D="$ROOT/downloads"; mkdir -p "$D" "$ROOT/guest_image/out"; cd "$D"
B="https://github.com/firecracker-microvm/firecracker/releases/download/${FC_VERSION}"
T="firecracker-${FC_VERSION}-x86_64.tgz"
curl -fsSL -o "$T" "$B/$T"; curl -fsSL -o "$T.sha256.txt" "$B/$T.sha256.txt"
sha256sum -c "$T.sha256.txt"                       # fails closed (set -e) on mismatch
mkdir -p x && tar -xzf "$T" -C x
cp "x/release-${FC_VERSION}-x86_64/firecracker-${FC_VERSION}-x86_64" firecracker && chmod 0755 firecracker
curl -fsSL -o "$ROOT/guest_image/out/vmlinux" "$KERNEL_URL"
echo "firecracker_release_tgz_sha256: $(sha256sum "$T" | cut -d' ' -f1)"
echo "firecracker_sha256:             $(sha256sum firecracker | cut -d' ' -f1)"
echo "kernel_sha256 (TOFU):           $(sha256sum "$ROOT/guest_image/out/vmlinux" | cut -d' ' -f1)"
./firecracker --version
