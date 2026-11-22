# Amendment 17: eighth internal review, narrowed to fb544a0..203bdca (corrections after the seventh review)

22 November 2026. Kept as returned by the reviewing agent, unedited, below the line. The reviewer is a separate AI agent
working at the author's instruction, read-only on the worktree, with its own database (plea_rv8). Its scope was the one
diff, as the stopping rule of `verify/AMEND17_DEV_LOG.md` entry 18 set it. This is an internal review, not an independent
validation. Its probes and their outputs are kept in `tests/amend17_dev_evidence/review_203bdca_probes/`.

---

[tier: opus] **Review of `git diff fb544a0 203bdca` (entry 18: corrections for N7-M1 and N7-M2).** This is an internal review done at the author's instruction. It is not independent validation.

**Answer to the stopping rule:** this diff brings in no CRITICAL, HIGH or MEDIUM defect, and it corrects N7-M1 and N7-M2 for the cases the seventh review named. Everything I found is LOW.

**How I worked**
- **Worktree:** read only. HEAD is still 203bdca7…. The only untracked items there are the author's own (`predecl_run5_fb544a0/`, `review7_run1_front.json`), and I did not touch them.
- **Copies:** `git archive 203bdca` is in `review8/tree/`.
- **Database:** I used `plea_rv8` (`init_schema`, `init_authority`, `front_state.install`) and dropped it at the end.
- **Limits kept:** no ports bound, no suite run, no service started.
- **Probes:** in process, plus CLI subprocesses. Each expectation was written in the probe's docstring before it ran.
- **Two probe runs died on errors in my probes, not in the code.** Both outputs are kept as `*_run1_PROBE_ERROR.out`:
  - psycopg cannot send a NUL byte in a row lookup;
  - `mkstemp` makes the path absolute, so the `nobody` account could not pass the scratchpad's 0700 parent folders. I re-ran those cases as uid 0 with every capability dropped (`setpriv`) instead.
- **Predictions:** none failed after those two fixes.
- **Hashes:** the three test files match entry 18's declared SHA-256s. The committed review7 probes are byte-identical to the originals in `scratchpad/review7`. `reconstructed_run2` hashes to 74638b00….

== CRITICAL ==
None.

== HIGH ==
None.

== MEDIUM ==
None.

== LOW ==

**R8-L1. `jobs.json` takes whatever mode the file already there has, including one the D16 adversary planted, and keeps it on every later write.** RUN. Brought in by this diff (`front_ctl.py:200-206`).
- **What is copied:** `S_IMODE` is taken from any regular file at `jobs.json`, whoever owns it.
- **Copied as found (P2b/P2c):**
  - 0o600 stays 0o600;
  - 0o666 stays world-writable;
  - 0o6755 keeps its set-id bits (as root).
- **Scenario (P2i, `p2b_nocaps.out`):**
  1. Another account plants `jobs.json` with mode 0o044 and one entry.
  2. The console's first write reads it and leaves a console-owned 0o044 file.
  3. The console then cannot read its own file. `read_jobs` (unchanged) turns `EACCES` into `{}`.
  4. Every later enrol silently writes only its own job and drops all the others. `revoke` and `rebind` answer "not enrolled", and the `jobs` listing would show nothing.
- **Same mechanism, other cases:**
  - P2h: a 0o000 file stays 0o000, and other entries are lost with no error.
  - A planted 0o600 file shuts out a front door under another account (N7-M2's effect) for good (ARGUED from P2b).
- **Why only LOW:**
  - D16 is not broken: nothing is admitted, and `--by-name` still revokes.
  - A writer of HOME/front can already delete or spoil `jobs.json`.
  - What is new is persistence after the adversary loses write access, and the console doing the deleting.
- **Possible fix:** copy the mode only when `st.st_uid == os.geteuid()`, else use 0o644. Mask it to `(m & 0o644) | 0o600`.

**R8-L2. Exception path in `_write`.** RUN P2f/P2g.
- If `os.stat` (other than `FileNotFoundError`) or `os.fchmod` raises, the temporary file is removed and `jobs.json` is unchanged. The temporary file's descriptor is leaked, though, because it is never closed before `fdopen`.
- On a filesystem that refuses chmod, every console write would now fail (ARGUED). For `revoke` that ends with status 4 or 1, which is said.
- Brought in by this diff; trivial.

**R8-L3. A new `jobs.json` is 0o644 whatever the umask** (P2a: umask 077 and 000 both give 0o644). Brought in by this diff.
- It is stated in the dev log, not in the README. A file left at 0600 by 7b2066a or fb544a0 stays 0600 (P2b) and needs a one-time chmod, which the README does not mention.

**R8-L4. `fullmatch` was applied only to `revoke --by-name`.** ARGUED, with P1e for the regex.
- `enrol` (`front_ctl.py:255`), `binding_valid` (`front_door.py:117`) and the certificate name check (`front_door.py:437`) still use `JOB_NAME.match`.
- **Scenario:** `enrol` accepts `'job-n\n'`. If such a job's entry is later removed, `--by-name` refuses it as "not a job name", so it cannot be revoked by name.
- It needs an engineer to enrol a name ending in a newline, which is implausible. The inconsistency is new in this diff.

**R8-L5. Documentation and argument handling.**
- The usage line `front_ctl.py:6` does not show `[--by-name]`.
- `RevokedByName` inherits `Unwritten`'s docstring ("revoke given again writes it"), which is false for it. No caller is misled: the grep finds only `main()`, which catches it first (P1i), and the tests.
- `--by-name` is silently accepted for `rebind` and `enrol` (P1j).
- A name that is not a job name, given without `--by-name`, is told to retry with `--by-name`, which then refuses it.

**R8-L6. Test gaps.**
- Check 15 does not cover `follow_symlinks=False` or the fallback for a file that is not regular. A defect that drops `follow_symlinks=False` would not be caught. The real code does the right thing (P2d: link replaced, outside file's content and mode untouched).
- In check 9, the "--by-name, another REVOKE" case runs after the row is already (1, True). This was the same before the diff.

**R8-L7. Record-keeping.**
- The dev log states the fb544a0 full runs ("gate 34 of 34, front 36 of 36") but their evidence (`predecl_run5_fb544a0/`) is not committed. It is untracked in the worktree. Its `main.txt` and `mutants.txt` show exit 0 for each part and 34 of 34 caught, with 13 not planted.
- `review7_run1_front.json` (untracked) shows F38 at 15 of 15 checks and 5 of 5 tests. I did not make that run and cannot vouch for which tree it came from.

== Checked and sound ==
- **Statuses (P1, `p1_status.out`):**
  - Plain `revoke` of a mistyped name: status 1, names `--by-name` and the key, no row made.
  - `--by-name` with the entry removed: status 5, row (1, True), file unchanged, the entry put back is refused.
  - `--by-name` with a usable entry: the ordinary path, status 0, (2, True).
  - `--by-name` with the database unreachable: status 1, "NOT revoked".
  - Status 4 only on the ordinary path when the write fails (log made a directory).
  - Status 3 when the database is unreachable on the ordinary path.
- **Wrong key with both keys pinned:** plain is status 1. `--by-name` is status 5 and names key B and "not covered". A's job is still admitted, which is now asked for and documented.
- **`fullmatch`:** it refuses `'job-n\n'`, NUL, uppercase, full-width letters, too short, too long, a leading hyphen and RESERVED names. `.match` accepted `'job-n\n'`.
- **`except front_ctl.Unwritten`:** it catches `RevokedByName` only where intended (`main()` orders it first, and in the F38 cases).
- **README and docstrings:** the statuses and the key-change rule are now accurate. I confirmed that the front door takes `--engineer-key` repeatedly with no warning.
- **F38 checks 9, 12 and 15:** honest restatements that follow the change, not weakenings. Check 15 discriminates each of the three new planted defects (ARGUED by code trace).
- **Runner (`q1_count.out`):** replaying its own `count == 1` rule gives 51 entries, 37 planted and 14 not planted, as declared. The 14 are fb544a0's 13 plus the sixth review's 'not revoked by name' entry. All four new entries are planted, and each would fail F38 (ARGUED).

== N7-M1 ==
**Corrected** (RUN P1a, P1e, P1h).
- Revocation by name happens only with `--by-name`.
- A mistyped name, or the wrong key, without the flag is refused with status 1.
- A name with a newline is refused.
- Status 4 again means only "recorded, not written".
- Left over: `--by-name` with the wrong key still revokes under that key, but only when asked, and the message says so.

== N7-M2 ==
**Corrected for the case named** (RUN P2a, P2b).
- Files the console writes are 0o644, or keep the earlier owner's mode (0o640 is kept).
- That a front door under another account can then read the file is ARGUED from the mode, not run.
- Left over: R8-L1 (an inherited planted or odd mode) and R8-L3 (files left at 0600 stay 0600).

== Could not check ==
- Any suite, F38 against real services, or the runner's actual catching: planting was replayed only, and catching was argued.
- Real enrol, which needs the CA and the gate: simulated with `_write(..., None)`.
- A real deployment with the console and the front door under separate accounts.
- Behaviour on filesystems that refuse chmod.

Files are in /tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad/review8/ and are listed with hashes in its `SHA256SUMS`:
- `common.py`
- `q1_count.py`, `q1_count.out`
- `p1_status.py`, `p1_status.out`, `p1_status_run1_PROBE_ERROR.out`
- `p2_mode.py`, `p2_mode.out`, `p2_mode_run1_PROBE_ERROR.out`
- `p2b_nocaps.py`, `p2b_nocaps.out`
- `tree/` (the archive of 203bdca)
