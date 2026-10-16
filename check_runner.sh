#!/bin/bash
# Self-test of run_chain_v121.sh's exit status, in seconds, in a throwaway copy (the bundle's outputs/ is never touched):
#   1. no usable Python                                                          -> exit 2, no rerun.done
#   2. every stage failing (/bin/false as the interpreter, preflight skipped)     -> exit 1, rerun.failed written, no rerun.done
# Run from the bundle root:  bash check_runner.sh
HERE="$(cd "$(dirname "$0")" && pwd)"; fail=0
T="$(mktemp -d)" || exit 2
mkdir "$T/tests" "$T/outputs" && cp "$HERE/run_chain_v121.sh" "$T/" || exit 2
PLEA_PYTHON=/nonexistent/python bash "$T/run_chain_v121.sh" >/dev/null 2>&1; rc=$?
if [ $rc -eq 2 ] && [ ! -e "$T/outputs/rerun.done" ]; then echo "ok   unusable interpreter: exit $rc, no rerun.done"; else echo "FAIL unusable interpreter: exit $rc"; fail=1; fi
PLEA_PYTHON=/bin/false PLEA_SKIP_PREFLIGHT=1 bash "$T/run_chain_v121.sh" >/dev/null 2>&1; rc=$?
if [ $rc -eq 1 ] && [ ! -e "$T/outputs/rerun.done" ] && [ -e "$T/outputs/rerun.failed" ]; then echo "ok   every stage failing: exit $rc, rerun.failed written, no rerun.done"; else echo "FAIL every stage failing: exit $rc"; fail=1; fi
[ -n "$T" ] && [ -d "$T/outputs" ] && rm -r "$T"
exit $fail
