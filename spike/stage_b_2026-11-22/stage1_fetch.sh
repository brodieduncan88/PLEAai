#!/bin/bash
# Stage 1. CHANGES THE HOST: apt installs e2fsprogs squashfs-tools curl ca-certificates git jq;
# downloads ~0.5 GB; writes /opt/plea-fc/{bin,images,share,work,pins.json}. Args pass through to fetch.py.
set -euo pipefail
B=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
EV=${PLEA_EVIDENCE:?run via run_stage.sh}
export DEBIAN_FRONTEND=noninteractive
timeout 900 apt-get update -q
timeout 1800 apt-get install -y -q --no-install-recommends e2fsprogs squashfs-tools curl ca-certificates git jq
dpkg-query -W e2fsprogs squashfs-tools curl ca-certificates git jq > "$EV/apt_versions.txt"
exec timeout 5400 python3 -I -B "$B/fetch.py" "$@"
