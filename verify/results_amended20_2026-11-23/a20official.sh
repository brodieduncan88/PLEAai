set -u
S=/tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad; W=$S/wt_a20; PY=$S/venv/bin/python; O=$S/a20official; mkdir -p $O
cd $W/tests; find .. -name __pycache__ -prune -exec rm -rf {} +; rm -f ../outputs/verify_tests.json ../outputs/verify_front_tests.json
echo "official runs at $(git -C $W rev-parse HEAD)"
$PY -B verify_tests.py > $O/gate.txt 2>&1; echo "gate exit $?"; cp ../outputs/verify_tests.json $O/gate.json
$PY -B verify_front_tests.py > $O/front.txt 2>&1; echo "front exit $?"; cp ../outputs/verify_front_tests.json $O/front.json
echo done
