#!/bin/bash
# Fix the predicates before execution (VP rule): write declared/SHA256SUMS over every bundle file.
# Hand back / commit declared/SHA256SUMS (and the hash printed below) BEFORE running any stage.
# Changes nothing outside the bundle directory.
set -euo pipefail
B=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
source "$B/lib.sh"
mkdir -p "$B/declared"
if [ -f "$B/declared/SHA256SUMS" ] && [ "${1:-}" != --force ]; then
	if verify_declared "$B"; then echo "already declared; every hash matches"; sha256sum "$B/declared/SHA256SUMS"; exit 0; fi
	echo "declared/SHA256SUMS exists and differs: refusing to overwrite (--force only before any run)" >&2; exit 1
fi
(cd "$B" && bundle_files . | xargs -d '\n' sha256sum) > "$B/declared/SHA256SUMS.tmp"
mv "$B/declared/SHA256SUMS.tmp" "$B/declared/SHA256SUMS"
echo "declared $(wc -l < "$B/declared/SHA256SUMS") files"
sha256sum "$B/declared/SHA256SUMS"
