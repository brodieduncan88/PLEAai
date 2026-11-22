#!/bin/bash
# Stage 2 (idempotent; rerun after every reboot or stop/start). See setup_host.py for exactly what changes.
set -euo pipefail
B=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
exec timeout 900 python3 -I -B "$B/setup_host.py"
