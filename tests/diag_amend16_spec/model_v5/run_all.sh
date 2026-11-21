#!/usr/bin/env bash
# Runs every configuration (or those named as arguments), one process each, at most JOBS at once.
# Declarations must already exist in declared/ (written by declare.py before any run); their
# SHA-256 is checked against declared/SHA256SUMS before each run and recorded in each result.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PY:-$HERE/../../../venv/bin/python}"
JOBS="${JOBS:-3}"
OUT="${OUT:-$HERE/results}"
mkdir -p "$OUT"
cd "$HERE"
( cd declared && sha256sum -c --quiet SHA256SUMS ) || { echo "declarations do not match SHA256SUMS"; exit 2; }
if [ $# -gt 0 ]; then NAMES="$*"; else NAMES=$("$PY" -c 'import configs; print(" ".join(configs.ORDER))'); fi
run_one() {
  n="$1"
  # memory cap per process (GiB): keeps one configuration from taking the machine
  ( ulimit -v $((5*1024*1024)); "$PY" model.py --config "$n" --declared "declared/$n.json" --out "$OUT/$n.json" ) \
     > "$OUT/$n.console.txt" 2>&1
  echo "$(date -u +%T) done $n: $(head -1 "$OUT/$n.console.txt")"
}
export -f run_one; export PY OUT
printf '%s\n' $NAMES | xargs -P "$JOBS" -I{} bash -c 'run_one {}'
"$PY" summarize.py "$OUT"
