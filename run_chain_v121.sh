#!/bin/bash
# v1.2.1 full regression chain: x_tests, u_tests, s_tests, q_tests, then every earlier test; both G01 isolation modes.
#
# Exit status: 0 only if the interpreter and the database are usable, all 22 stages ran and every stage exited 0.
#              1 if any stage failed (all stages still run, so the evidence is complete; the failed ones are listed).
#              2 if the check could not start (no usable Python with psycopg and cryptography, or no reachable database).
# Python:      $PLEA_PYTHON, else ./venv/bin/python in this directory (what the README creates), else python3 on PATH.
# Database:    $PLEA_DB (default plea12) on 127.0.0.1:5432, with the four roles of the README.
set -o pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/tests" || exit 2
DB=${PLEA_DB:-plea12}
export PLEA_ADMIN_DSN=postgresql://plea:plea@127.0.0.1:5432/$DB
export PLEA_LOCAL_DSN=postgresql://plea_local:local@127.0.0.1:5432/$DB
export PLEA_WITNESS_DSN=postgresql://plea_witness:witness@127.0.0.1:5432/$DB
export PLEA_CONTROL_DSN=postgresql://plea_control:control@127.0.0.1:5432/$DB
if [ -n "$PLEA_PYTHON" ]; then PY="$PLEA_PYTHON"
elif [ -x "$ROOT/venv/bin/python" ]; then PY="$ROOT/venv/bin/python"
else PY="$(command -v python3)"; fi
rm -f ../outputs/rerun.done ../outputs/rerun.failed
if [ -z "$PLEA_SKIP_PREFLIGHT" ]; then
  "$PY" -c "import psycopg, cryptography" >/dev/null 2>&1 || { echo "preflight: '$PY' cannot import psycopg and cryptography (README: python3 -m venv venv && . venv/bin/activate && pip install 'psycopg[binary]' cryptography; or set PLEA_PYTHON)" >&2; exit 2; }
  "$PY" -c "import os, psycopg; psycopg.connect(os.environ['PLEA_ADMIN_DSN'], connect_timeout=10).close()" >/dev/null 2>&1 || { echo "preflight: cannot connect to database '$DB' as the owner role (README: create the roles and the database, then init the schema)" >&2; exit 2; }
fi
FAILED=(); STAGES=0
run(){ name=$1; shift; ( time "$PY" -B "$@" ) > ../outputs/$name.txt 2>&1; rc=$?; echo "exit=$rc" >> ../outputs/$name.txt; echo "$name exit=$rc"; STAGES=$((STAGES+1)); [ $rc -eq 0 ] || FAILED+=("$name"); }
run x_tests x_tests.py
run u_tests u_tests.py
run s_tests s_tests.py
run q_tests q_tests.py
run p_tests p_tests.py
run v_tests v_tests.py
run r_tests r_tests.py
run h_tests h_tests.py
run t_tests t_tests.py
run mcp_tests mcp_tests.py
run e1_release_evidence e1_release_evidence.py; run e2_reconcile_evidence e2_reconcile_evidence.py; run e3_lifecycle_evidence e3_lifecycle_evidence.py
run w1_authority w1_authority.py; run w2_receipts w2_receipts.py; run w3_service_lockstep w3_service_lockstep.py; run w4_service_crash w4_service_crash.py
( time env PYTHONPATH=. "$PY" -B vectors.py conform_store ) > ../outputs/conform_store.txt 2>&1; rc=$?; echo "exit=$rc" >> ../outputs/conform_store.txt; echo "conform_store exit=$rc"; STAGES=$((STAGES+1)); [ $rc -eq 0 ] || FAILED+=("conform_store")
run chaos chaos.py
run g02b g02b.py --rounds 200
run g01_lock g01_race.py --rounds 300 --workers 16 --k 3 --mode lock
run g01_serializable g01_race.py --rounds 300 --workers 16 --k 3 --mode serializable
if [ ${#FAILED[@]} -ne 0 ] || [ $STAGES -ne 22 ]; then
  echo "CHAIN FAILED: $STAGES of 22 stages ran; failed: ${FAILED[*]:-none}" | tee ../outputs/rerun.failed >&2
  exit 1
fi
echo "CHAIN PASSED: 22 of 22 stages exit 0" | tee ../outputs/rerun.done
