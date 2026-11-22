# Amendment 18: development log

22 November 2026. Private working material. Branch `hardening/prepentest-2026-11-22`, from `ba82e66`. Times are UTC.

This is internal work by the author, under the owner's decisions of 22 November 2026 ("Amendment 17 Owner Decisions and
Stage B Authorisation", point 1). It is not an independent validation. The verification-process rules VP-1 to VP-6
apply: a failing run is kept with its source; a predicate is not changed after a failure without the record; expectations
are declared, with the hash of the test file, before a run.

Amendment 17's declaration, its official results and its log are not changed by anything here.

## Entry 1. The change

**What it does.** A front door pins exactly one responsible engineer's key. `front_door.single_engineer_key` refuses
(`EngineerKeys`):
- no key;
- more than one key, the same key twice included;
- a key that is not 64 lower-case hex digits.

**Where it is checked.**
- `Front.__init__`, so no front door is made in process with another number of keys.
- The front door's start, before anything is opened or bound, which ends with "front door: not started: …".

**What is not changed.**
- The configuration is the existing repeated `--engineer-key` option. No new mechanism is added.
- Bindings and baselines signed by any other key are refused as before.
- The realm mechanism of Amendment 17's development is not brought back. Key-independent revocation across several
  keys is not built.

**Rotation of the key is not supported in this assessment profile.** `verify/README_FRONT.md` says so, with what to do
should a key have to be replaced.

**Files changed:**
- `verify/front_door.py`;
- `verify/README_FRONT.md`;
- `tests/verify_front_tests.py` (F39 is added; nothing else is changed);
- `tests/amend17_mutants.py` (three defects are added).

**Planted-defect coverage of Amendment 17 (the owner's question).** The final pass ran against `203bdca`
(`203bdca7bf4fb846b512e5853e43682b16201fc6`), not `818bee9`. It had 51 entries: 37 planted and 37 caught, 14 NOT
PLANTED, with the runner's exit 0. The evidence is in `tests/amend17_dev_evidence/predecl_run6_203bdca/`, whose
SHA256SUMS check.
- The passes before it were at `3473478` (23 of 23), `818bee9` (26 of 26), `c5c9832` (30 of 30) and `fb544a0` (34 of 34).
- The pass at `f4c1de6` stopped on a fault of the runner and left no result file.
- So there is no gap for `203bdca`. The gap is for the change of this amendment, which no pass has yet covered.

**Declared before the first run (VP-5).** SHA-256 of the files:
- `tests/verify_front_tests.py`: `0921fd87f2c3c0fac5d50736c541c4ca349be1c5495ed05896649f0b7a1b9dd9`;
- `tests/verify_tests.py` (not changed): `c4ab616416c4a85405bb4ebd1a4e079ccbf3f7da9c009979222a1932ba473cb1`;
- `verify/front_door.py`: `8c1336e0de528567436f4616fd99624ab08a065e84bdc5150734756c42ac5494`.

Expected:
- F39: 3 of 3 checks;
- F10, F12, F37 and F38 pass, with 6, 6, 11 and 15 checks.

**Run 1.** F39, F10, F12, F37 and F38 passed, 5 of 5, as declared: F39 3 of 3 checks, F10 6, F12 6, F37 11, F38 15.
Kept in `tests/amend18_dev_evidence/run1_front.*`.
