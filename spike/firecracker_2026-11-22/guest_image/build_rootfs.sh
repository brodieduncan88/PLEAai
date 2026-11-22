#!/bin/bash
# Build a minimal READ-ONLY ext4 rootfs with Python 3 standard library on an Ubuntu 24.04 build host.
# Run as root. Tools: debootstrap e2fsprogs (install on the BUILD host; not the verification host if avoidable).
#   apt-get install -y debootstrap e2fsprogs
# Reproducibility knobs: pinned snapshot mirror date, SOURCE_DATE_EPOCH, fixed UUID/hash seed, normalised mtimes.
# Bit-for-bit reproducibility is a GOAL: build twice and compare sha256 (step 8 of the run sheet); not yet verified.
set -euo pipefail
: "${SNAPSHOT:?set SNAPSHOT=YYYYMMDDTHHMMSSZ (a snapshot.ubuntu.com timestamp, pinned in REPORT)}"
HERE=$(cd "$(dirname "$0")" && pwd); OUT="$HERE/out"; T=$(mktemp -d /var/tmp/plea-rootfs.XXXXXX)
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(date -u -d "${SNAPSHOT:0:8}" +%s)}"
export E2FSPROGS_FAKE_TIME="$SOURCE_DATE_EPOCH"
mkdir -p "$OUT"
debootstrap --variant=minbase --arch=amd64 --include=python3 noble "$T/root" "https://snapshot.ubuntu.com/ubuntu/$SNAPSHOT"
install -D -m 0755 "$HERE/init.sh" "$T/root/sbin/init"
mkdir -p "$T/root/opt/spike/jobs"; cp "$HERE"/jobs/*.py "$T/root/opt/spike/jobs/"
rm -rf "$T/root"/var/lib/apt/lists/* "$T/root"/var/cache/apt/* "$T/root"/var/log/* "$T/root"/usr/share/doc/* \
       "$T/root"/usr/share/man/* "$T/root"/usr/share/locale/* "$T/root"/etc/machine-id "$T/root"/var/lib/dpkg/info/*.md5sums
find "$T/root" -xdev -name __pycache__ -prune -exec rm -rf {} +
find "$T/root" -xdev -exec touch -h -d "@$SOURCE_DATE_EPOCH" {} +
truncate -s 256M "$OUT/rootfs.ext4"
mke2fs -q -t ext4 -F -L plea-spike -U 11111111-2222-3333-4444-555555555555 \
  -E hash_seed=11111111-2222-3333-4444-555555555555,root_owner=0:0 -O ^has_journal -d "$T/root" "$OUT/rootfs.ext4"
sha256sum "$OUT/rootfs.ext4" | tee "$OUT/rootfs.ext4.sha256"
rm -rf "$T"
echo "Record this hash in pins.json as rootfs_sha256 only after step 8 (two-build comparison)."
