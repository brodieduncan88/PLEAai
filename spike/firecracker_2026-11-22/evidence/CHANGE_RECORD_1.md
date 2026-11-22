# Change record 1 (VP-4)
Failing results (run 1, declaration SHA-256 6a1897231413f141d3b6045543352494ce927eaae0ff38c273abbb0e28f7a9f5):
- T3: expected "all py_compile and bash -n pass". Observed: the Python half crashed with FileExistsError
  (`py_compile.compile(cfile="/dev/null")` refuses a non-regular file) before printing any "py ok" line; the bash -n half passed.
  The command's exit code was 0 anyway, which hid the crash. Cause: defect in MY TEST CODE, not in the files under test.
- T5: expected HTTP 403 (refused). Observed: HTTP 302 for both URLs, 0-byte output file. Cause: my command did not follow
  redirects (-L), so it never reached the download host. The expectation was also wrong: github.com release URLs are not blocked,
  while api.github.com and releases/latest were (HTTP 403 earlier).
Source and outputs preserved (VP-2/VP-3): evidence/failed_run1_source/ and evidence/failed_run1_SHA256SUMS.
Original run_declared.sh is NOT edited. Changes are in a new runner run_declared_2.sh judged against declared/DECLARATION_2.md (VP-5):
- T3b: syntax check with ast.parse (no file writes), and the script now fails if any file fails (set -e semantics, exit code recorded).
- T5b: curl -L --max-redirs 3, checksum compared with the published .sha256.txt; downloaded into its own empty dir downloads/fc-candidate/.
- T6b/T7b: conditional on T5b succeeding.
No source file of the product (prereq.py, admission_demo.py, harness) was changed. Results of run 1 stand and are reported alongside run 2.
