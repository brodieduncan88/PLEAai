#!/bin/bash
# Static checks (no KVM, no root needed): py_compile every Python file (bytecode to a temp dir, never into the
# bundle), bash -n every shell script, and a declare -> verify -> tamper -> refuse cycle in a temporary copy.
set -uo pipefail
B=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
rc=0
echo "== py_compile"
while IFS= read -r f; do
	if python3 -I -c 'import py_compile,sys; py_compile.compile(sys.argv[1], cfile=sys.argv[2], doraise=True)' "$f" "$T/x.pyc"; then
		echo "ok   ${f#$B/}"; else echo "FAIL ${f#$B/}"; rc=1; fi
done < <(find "$B" -name '*.py' -not -path '*/evidence/*' | LC_ALL=C sort)
echo "== bash -n"
while IFS= read -r f; do
	if bash -n "$f"; then echo "ok   ${f#$B/}"; else echo "FAIL ${f#$B/}"; rc=1; fi
done < <( (find "$B" -name '*.sh' -not -path '*/evidence/*'; echo "$B/guest/plea-init") | LC_ALL=C sort)
echo "== declare/verify cycle in a temp copy"
C="$T/copy"; mkdir "$C"; (cd "$B" && tar --exclude=./evidence --exclude=./state --exclude=./declared --exclude='__pycache__' -cf - .) | tar -C "$C" -xf -
source "$B/lib.sh"
bash "$C/declare.sh" > "$T/d.out" 2>&1 && echo "ok   declare.sh wrote $(wc -l < "$C/declared/SHA256SUMS") hashes" || { echo "FAIL declare"; rc=1; }
verify_declared "$C" 2>/dev/null && echo "ok   verify_declared passes on the untouched copy" || { echo "FAIL verify untouched"; rc=1; }
bash "$C/declare.sh" > /dev/null 2>&1 && echo "ok   declare.sh re-run on unchanged bundle just verifies" || { echo "FAIL re-declare"; rc=1; }
echo "# tamper" >> "$C/DECLARATION.md"
verify_declared "$C" 2>/dev/null && { echo "FAIL tampered file accepted"; rc=1; } || echo "ok   tampered DECLARATION.md -> verify refuses"
bash "$C/declare.sh" > /dev/null 2>&1 && { echo "FAIL declare overwrote a differing declaration"; rc=1; } || echo "ok   declare.sh refuses to overwrite a differing declaration"
sed -i '$ d' "$C/DECLARATION.md"; echo "x=1" > "$C/json.py"
verify_declared "$C" 2>/dev/null && { echo "FAIL undeclared file accepted"; rc=1; } || echo "ok   undeclared extra file (json.py) -> verify refuses"
rm "$C/json.py"
verify_declared "$C" 2>/dev/null && echo "ok   restored copy verifies again" || { echo "FAIL restore"; rc=1; }
if [ "$(id -u)" = 0 ]; then
	out=$(bash "$C/run_stage.sh" T01 2>&1); r=$?
	echo "$out" | grep -q "run stage2 first" && [ $r -ne 0 ] && echo "ok   run_stage.sh T01 refuses before stage2 (state gating), exit $r" || { echo "FAIL gating: $out"; rc=1; }
	echo "# tamper" >> "$C/README.md"
	out=$(bash "$C/run_stage.sh" stage0 2>&1); r=$?
	echo "$out" | grep -q "REFUSED: bundle differs" && echo "ok   run_stage.sh stage0 refuses on a tampered bundle, exit $r" || { echo "FAIL tamper: $out"; rc=1; }
fi
echo "== KVM ioctl/capability numbers in prereq.py vs /usr/include/linux/kvm.h (if installed)"
if [ -r /usr/include/linux/kvm.h ]; then
	python3 -I -B - "$B" <<'PY' || rc=1
import re, sys
sys.path.append(sys.argv[1])
import prereq
h = open("/usr/include/linux/kvm.h").read()
ok = True
for name, val in list(prereq.KVM_CAPS.items()) + [("KVM_GET_API_VERSION", prereq.KVM_GET_API_VERSION & 0xFF),
                                                  ("KVM_CREATE_VM", prereq.KVM_CREATE_VM & 0xFF), ("KVM_CHECK_EXTENSION", prereq.KVM_CHECK_EXTENSION & 0xFF)]:
    m = re.search(rf"#define {name}\s+(?:_IO\(KVMIO,\s*)?(0x[0-9a-fA-F]+|\d+)", h)
    good = bool(m) and int(m.group(1), 0) == val
    ok &= good
    print(("ok  " if good else "FAIL"), name, val, "header:", m.group(1) if m else None)
ok &= bool(re.search(r"#define KVMIO 0xAE\b", h))
sys.exit(0 if ok else 1)
PY
else echo "skipped: header not installed"; fi
echo "== result: $([ $rc = 0 ] && echo ALL OK || echo FAILURES)"
exit $rc
