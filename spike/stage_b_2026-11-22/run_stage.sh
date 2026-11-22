#!/bin/bash
# Run one stage or test as root. Refuses if any bundle file differs from declared/SHA256SUMS (predicates are
# fixed before execution), if state/BLOCKED exists, or if the previous stage has not succeeded.
# Evidence: evidence/<UTC>-<stage>/ (+ journalctl -k excerpt, dmesg tail, recover.py dry-run, SHA256SUMS).
set -euo pipefail
B=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
source "$B/lib.sh"
usage() {
	echo "usage: sudo $0 <stage0|stage1|stage2|T01..T11|T12pre|T12post|T13|T14|T15|all-tests|prereq|recover|recover-apply|selftest> [args]" >&2
	exit 2
}
[ "$(id -u)" = 0 ] || die "run as root (sudo)"
STAGE=${1:-}; [ -n "$STAGE" ] || usage; shift
verify_declared "$B" || die "bundle differs from declared/SHA256SUMS"
for v in $(compgen -e); do case $v in PLEA_*) unset "$v" ;; esac; done
if [ -e "$B/state/BLOCKED" ] && [ "$STAGE" != stage0 ]; then die "$(cat "$B/state/BLOCKED")"; fi
PY=(python3 -I -B)
T="$B/tests"
req=stage2 tmo=1800
case $STAGE in
	stage0) req= tmo=300 cmd=(bash "$B/stage0_host.sh") ;;
	stage1) req=stage0 tmo=5700 cmd=(bash "$B/stage1_fetch.sh" "$@") ;;
	stage2) req=stage1 tmo=900 cmd=(bash "$B/stage2_setup.sh") ;;
	T01) cmd=("${PY[@]}" "$T/t01_start.py") tmo=600 ;;
	T02) cmd=("${PY[@]}" "$T/t02_unpriv.py") tmo=600 ;;
	T03) cmd=("${PY[@]}" "$T/t03_workload.py") tmo=600 ;;
	T04) cmd=("${PY[@]}" "$T/t04_latency.py") tmo=3600 ;;
	T05) cmd=("${PY[@]}" "$T/t05_limits.py") tmo=1800 ;;
	T06) cmd=("${PY[@]}" "$T/t06_host_avail.py") tmo=3000 ;;
	T07) cmd=("${PY[@]}" "$T/t07_high_fd.py") tmo=900 ;;
	T08) cmd=("${PY[@]}" "$T/t08_console.py") tmo=900 ;;
	T09) cmd=("${PY[@]}" "$T/t09_delivery.py") tmo=1800 ;;
	T10) cmd=("${PY[@]}" "$T/t10_concurrent.py") tmo=2400 ;;
	T11) cmd=("${PY[@]}" "$T/t11_kill.py") tmo=1800 ;;
	T12pre) cmd=("${PY[@]}" "$T/t12_pre.py") tmo=600 ;;
	T12post) cmd=("${PY[@]}" "$T/t12_post.py") tmo=1200 ;;
	T13) cmd=("${PY[@]}" "$T/t13_missing_prereq.py") tmo=1800 ;;
	T14) cmd=("${PY[@]}" "$T/t14_admission.py") tmo=1800 ;;
	T15) cmd=("${PY[@]}" "$T/t15_toctou.py") tmo=1800 ;;
	prereq) req=stage1 tmo=300 cmd=("${PY[@]}" "$B/prereq.py") ;;
	recover) req= tmo=300 cmd=("${PY[@]}" "$B/recover.py") ;;
	recover-apply) req= tmo=600 cmd=("${PY[@]}" "$B/recover.py" --apply) ;;
	selftest) req= tmo=600 cmd=("${PY[@]}" "$B/selftest.py") ;;
	all-tests)
		rc=0
		for s in T01 T02 T03 T04 T05 T06 T07 T08 T09 T10 T11 T13 T14 T15; do "$0" "$s" || rc=1; done
		echo "all-tests finished (exit $rc). T12 is separate: T12pre, sudo reboot, T12post."; exit "$rc" ;;
	*) usage ;;
esac
if [ -n "$req" ] && [ ! -e "$B/state/$req.ok" ]; then die "run $req first (state/$req.ok missing)"; fi
TS=$(date -u +%Y%m%dT%H%M%SZ)
EV="$B/evidence/$TS-$STAGE"
mkdir -p "$EV" "$B/state"
export PLEA_EVIDENCE=$EV
START=$(date '+%Y-%m-%d %H:%M:%S')
echo "$STAGE $*" > "$EV/STAGE"
cp "$B/declared/SHA256SUMS" "$EV/declared_SHA256SUMS"
cat /proc/sys/kernel/random/boot_id > "$EV/boot_id"
set +e
timeout --kill-after=30 "$tmo" "${cmd[@]}" 2>&1 | tee --output-error=warn-nopipe >(head -c 16777216 > "$EV/stage.log")
rc=${PIPESTATUS[0]}
set -e
echo "$rc" > "$EV/exit_code"
timeout 60 journalctl -k --since "$START" --no-pager -o short-iso 2>&1 | tail -c 1048576 > "$EV/journal_k.txt" || true
timeout 30 dmesg -T 2>&1 | tail -n 300 > "$EV/dmesg_tail.txt" || true
timeout 120 "${PY[@]}" "$B/recover.py" > "$EV/recover_dryrun_after.json" 2>&1 || true
case $STAGE in stage0 | stage1 | stage2) if [ "$rc" -eq 0 ]; then touch "$B/state/$STAGE.ok"; else rm -f "$B/state/$STAGE.ok"; fi ;; esac
sleep 1  # let the bounded log writer finish
(cd "$EV" && find . -type f ! -name SHA256SUMS -print0 | LC_ALL=C sort -z | xargs -0 -r sha256sum) > "$EV/SHA256SUMS"
echo "[$STAGE] exit $rc; evidence in $EV"
exit "$rc"
