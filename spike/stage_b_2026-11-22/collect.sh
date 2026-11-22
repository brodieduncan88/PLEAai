#!/bin/bash
# Tar evidence/, state/ and declared/ for the owner to copy back. Writes one file in /tmp owned by the sudo user.
set -euo pipefail
B=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 2; }
SZ=$(du -sb "$B/evidence" 2>/dev/null | cut -f1 || echo 0)
[ "${SZ:-0}" -le $((1024 * 1024 * 1024)) ] || { echo "evidence is ${SZ} bytes (> 1 GiB): inspect before collecting" >&2; exit 1; }
OUT=/tmp/plea-stage-b-evidence-$(date -u +%Y%m%dT%H%M%SZ).tar.gz
umask 077
tar -C "$B" -czf "$OUT" evidence state declared
[ -n "${SUDO_UID:-}" ] && chown "$SUDO_UID:${SUDO_GID:-$SUDO_UID}" "$OUT"
sha256sum "$OUT"
echo "copy back with: scp <host>:$OUT ."
