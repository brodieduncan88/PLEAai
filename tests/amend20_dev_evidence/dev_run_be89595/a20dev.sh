set -u
S=/tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad; W=$S/wt_a20; PY=$S/venv/bin/python; C=be89595; O=$S/a20dev; mkdir -p $O
cd $W/tests; find .. -name __pycache__ -prune -exec rm -rf {} +; rm -f ../outputs/verify_tests.json ../outputs/verify_front_tests.json
echo "commit $C, tree $(git -C $W rev-parse --short HEAD)"
$PY -B verify_tests.py > $O/gate.txt 2>&1; echo "gate exit $?"; cp ../outputs/verify_tests.json $O/gate.json
$PY -B verify_front_tests.py > $O/front.txt 2>&1; echo "front exit $?"; cp ../outputs/verify_front_tests.json $O/front.json
rm -rf $S/mutants_a20; $PY -B amend17_mutants.py $C $S/mutants_a19 $PY $O/mutants.json > $O/mutants.txt 2>&1; echo "mutants exit $?"
echo done
