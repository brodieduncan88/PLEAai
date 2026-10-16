#!/bin/bash
# v1.1 full regression chain: u_tests, s_tests, q_tests, then every earlier test; both G01 isolation modes.
set -o pipefail
cd "$(dirname "$0")/tests"
DB=${PLEA_DB:-plea11}
export PLEA_ADMIN_DSN=postgresql://plea:plea@127.0.0.1:5432/$DB
export PLEA_LOCAL_DSN=postgresql://plea_local:local@127.0.0.1:5432/$DB
export PLEA_WITNESS_DSN=postgresql://plea_witness:witness@127.0.0.1:5432/$DB
export PLEA_CONTROL_DSN=postgresql://plea_control:control@127.0.0.1:5432/$DB
PY=../../venv/bin/python
run(){ name=$1; shift; ( time $PY -B "$@" ) > ../outputs/$name.txt 2>&1; rc=$?; echo "exit=$rc" >> ../outputs/$name.txt; echo "$name exit=$rc"; }
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
( time env PYTHONPATH=. $PY -B vectors.py conform_store ) > ../outputs/conform_store.txt 2>&1; rc=$?; echo "exit=$rc" >> ../outputs/conform_store.txt; echo "conform_store exit=$rc"
run chaos chaos.py
run g02b g02b.py --rounds 200
run g01_lock g01_race.py --rounds 300 --workers 16 --k 3 --mode lock
run g01_serializable g01_race.py --rounds 300 --workers 16 --k 3 --mode serializable
echo DONE > ../outputs/rerun.done
