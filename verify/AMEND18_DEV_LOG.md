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

## Entry 2. The planted-defect run and the review, declared before either is made

**The planted-defect run.**
- `tests/amend17_mutants.py 8c4762f WORKDIR PYTHON OUT.json`, run on the three defects of this amendment, by name:
  - 'more than one engineer key accepted';
  - 'an engineer key of another form accepted';
  - "the front door's start does not check its keys".
- The runner's file at `8c4762f` has SHA-256 `d721199afdc9f80ce4475892483c636e04055529b0c5e3e84520aaf1cfd39e21`.
- Expected: 3 planted, 3 caught by F39.
- The 51 earlier entries are not run again. Their pass at `203bdca` covers every file this amendment does not change,
  and `verify/front_door.py`'s other text, which their search texts name, is unchanged.

**The review.** One review, by a separate AI agent instructed by the author, read-only.
- Scope: `git diff ba82e66 8c4762f`.
- Questions:
  - does the change do what point 1 of the owner's decision asks;
  - does it weaken an earlier property (enrolment, revocation, replay, the record of bindings, R1 to R13);
  - are F39's checks and the three defects discriminating;
  - is anything at any severity brought in?
- Under the owner's point 8 there is no open-ended cycle. If the review finds something critical, high or medium in
  this change, it is either corrected once, with that correction's own record, or reported to the owner as it stands.
  No second review follows.

**The planted-defect run (entry 2's declaration).**
- At `8c4762f`: 3 planted, 3 caught by F39, as declared. Each defect, alone in a copy of the tree, made F39 fail.
- Kept in `tests/amend18_dev_evidence/mutants/`.

## Entry 3. D20: can the rounding change a PASS or a FAIL? (the owner's point 3)

Two in-process probes of the gate's own decision path, `verify_tools._decide`. Only the sandbox is replaced, by a stand-in
that returns the bytes a check prints. Each probe's expectations were written in its text and committed before it ran
(`f840daf`, `e0dce97`). Both are in `tests/amend18_dev_evidence/d20/`.

- **First probe, run 1:** it stopped before testing anything, because `verify_tools` needs `VERIFY_HOME`. That was a
  fault of the probe's setup. The output is kept (`d20_rounding_probe_run1_PROBE_ERROR.out`).
- **First probe, run 2** (unchanged, with `VERIFY_HOME` set): **its predictions failed** (P1 a, P2 a, P2 b, P1 f, P2 f).
  - A check printing `199.99999999999999999999999999999` (a JSON number, below the limit of 200) was signed **PASS**,
    with achieved written as `200`.
  - So was `199.9999999999999999999999999`, which has 28 significant digits and is not rounded by the decimal
    context at all.
  - `check_record.rederive` accepted both.
  - The predictions were wrong about the mechanism, as the second probe shows. They are not changed.
- **Second probe** (`d20_float_probe.py`, declared after the first and before it ran): **all predictions held.**
  - **A JSON number is read by `json.loads` as a binary float** before it is turned into a decimal.
    - A value 1e-13 below the limit stays below and is FAIL.
    - Values 1e-14 below or closer become 200.0 and are signed **PASS**, with achieved `200`.
    - The same happens mirrored for a `<=` criterion: 200.00000000000001 is PASS.
    - Each such verdict is accepted by the record's checker, so the record verifies. The false PASS cannot be seen
      from the record.
  - **A JSON string is decided on the exact decimal.**
    - Every value below 200 with at most 28 significant digits is FAIL.
    - A value with more than 28 significant digits is UNKNOWN (CHECK_OUTPUT_INVALID), never PASS.
- **Assessment.**
  - **The rounding case of the register (more than 28 significant digits, written rounded) cannot change a PASS or a
    FAIL.** Where rounding would cross the limit, or the margin would not recompute, the record's checker refuses
    the verdict, and the gate answers UNKNOWN. That fails closed.
  - **A different loss of precision, on the way in, can change a FAIL into a PASS.** This is a security-relevant
    false PASS: the checker passes a design whose check printed a value on the wrong side of the limit. It needs:
    - a check that prints, as a JSON number, a value closer to the limit than a binary float can resolve (about
      1e-14 of 200 here, relative about 5e-17);
    - and a check that computes more precisely than a float, for instance with `decimal` or `fractions`.
    - A check that computes in floats prints values that read back as the same float, and is decided as it computed
      (ARGUED from how Python prints floats; not probed).
  - Recorded in the register as a new finding, D20-F, apart from D20's rounding. The likely correction reads JSON
    numbers as decimals (`json.loads(..., parse_float=decimal.Decimal)` in `baseline.evaluate`). It is not made here:
    it changes behaviour, so it needs its own amendment and the owner's approval. The owner asked that this exercise
    not be broadened into a numerical redesign.
