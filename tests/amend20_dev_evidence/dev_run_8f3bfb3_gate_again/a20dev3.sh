set -u
S=/tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad; W=$S/wt_a20; PY=$S/venv/bin/python; O=$S/a20dev3; mkdir -p $O
cd $W/tests; find .. -name __pycache__ -prune -exec rm -rf {} +; rm -f ../outputs/verify_tests.json
echo "commit 8f3bfb3, tree $(git -C $W rev-parse --short HEAD); the gate only, again"
$PY -B verify_tests.py > $O/gate.txt 2>&1; echo "gate exit $?"; cp ../outputs/verify_tests.json $O/gate.json
echo done
