# Amendment 21: development log (23 November 2026)

Private working material. Internal work by the author under the owner's decision of 23 November 2026 ("repair T-1"). Not an
independent validation. Branch `amend21-t1-clean-2026-11-23`, on `59de0dc`.

## Entry 1. T-1 and its repair

**T-1** (register G17): R25's last check handed the witness's random nonce to `check_record.py` as two arguments, `--nonce VALUE`. A
base64url nonce begins with `-` about once in 64, and `argparse` then took it for an option: status 2, a false failure of R25. It is a
fault in the test, not in the code under test. It was seen once in a development run and reproduced by hand with that nonce.

**The repair (tests and the operator readme only).**
- `tests/verify_tests.py`, R25: a helper hands a nonce as `--nonce=VALUE`; the closed-budget check uses it. R25 gains one
  **deterministic** check: a fixed nonce that begins with a dash (`-FixedLeadingDash0123456`) given the same way; expected status 1
  and one CURRENCY line, never status 2.
- `tests/amend17_mutants.py`: one planted defect, the helper handing the nonce as two arguments again (expected caught by R25).
- `verify/README.md`: the example is `--nonce=NONCE`, with the reason.
- Not changed: R25's other checks, word for word; any other test; any code under `verify/`, `plea_gateway/`, `mcp/` or `spike/`.

## Entry 2. This record is the clean rebuild

An earlier attempt at the same repair was made on branches that have since been withdrawn from the public repository for hygiene
reasons (identifiers and local paths in commit messages and recorded outputs). Nothing here cites it. This record rests only on the
declaration and the runs named in `verify/DECLARED_AMEND21.md` and `verify/AMENDMENT_21_2026-11-23.md`, which were made from commits
on this branch, in a neutral working directory.
