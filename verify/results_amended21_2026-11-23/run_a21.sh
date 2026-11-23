set -u
W=/tmp/plea-verify/a21; PY=/tmp/plea-verify/venv/bin/python; O=/tmp/plea-verify/official; C=$(git -C $W rev-parse --short HEAD)
cd $W/tests; find .. -name __pycache__ -prune -exec rm -rf {} +; rm -f ../outputs/verify_tests.json ../outputs/verify_front_tests.json
echo "official runs at $(git -C $W rev-parse HEAD)"
$PY -B verify_tests.py > $O/gate.txt 2>&1; echo "gate exit $?"; cp ../outputs/verify_tests.json $O/gate.json
$PY -B verify_front_tests.py > $O/front.txt 2>&1; echo "front exit $?"; cp ../outputs/verify_front_tests.json $O/front.json
rm -rf /tmp/plea-verify/mut; $PY -B amend17_mutants.py $C /tmp/plea-verify/mut $PY $O/mutants.json > $O/mutants.txt 2>&1; echo "mutants exit $?"
echo done
