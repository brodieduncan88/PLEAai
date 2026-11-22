# Shared shell helpers for declare.sh / run_stage.sh (sourced, not executed).
# Declared set = every regular file in the bundle except declared/, evidence/, state/, __pycache__/.
bundle_files() {  # $1 = bundle dir; prints ./relative paths, C-sorted
	(cd "$1" && find . -type f ! -path './declared/*' ! -path './evidence/*' ! -path './state/*' \
		! -path '*/__pycache__/*' -print | LC_ALL=C sort)
}
verify_declared() {  # $1 = bundle dir; 0 only if every declared hash matches and no file is undeclared/missing
	local b=$1 s="$1/declared/SHA256SUMS"
	[ -f "$s" ] || { echo "missing $s: run ./declare.sh first" >&2; return 1; }
	if ! (cd "$b" && sha256sum --strict --quiet -c declared/SHA256SUMS); then
		echo "a declared file's hash differs" >&2; return 1
	fi
	if ! diff <(awk '{print $2}' "$s" | sed 's/^\*//' | LC_ALL=C sort) <(bundle_files "$b") >&2; then
		echo "undeclared or missing files (diff above: < declared only, > present only)" >&2; return 1
	fi
}
die() { echo "REFUSED: $*" >&2; exit 2; }
