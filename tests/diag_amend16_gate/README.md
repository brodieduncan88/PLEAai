# Diagnostics for the design gate of Amendment 16, 21 November 2026

Development evidence only. Nothing here is a declaration, an official run or proposed code. No code of `e25a297` is
changed: every script drives the unchanged witness, gate host, mailbox, courier and store of a pinned copy of that
commit, with the roles and keys a test deployment gives. The predicates in the scripts are the harness's own.

Run as `DIAG_DB=<fresh database> python <script>.py SRC OUT`, where SRC is an archive of `e25a297`. The test
deployment's ports are fixed: one script at a time.

| Script | Part | Output in `results_2026-11-21/` |
|---|---|---|
| `gate_common.py` | shared setup | — |
| `gate_token.py` | A: a 32-byte token through the witness's checkpoint reading | `gate_token.json`; console `gate_token_run1.txt` (stopped by a harness fault), `_run2.txt` |
| `gate_release.py` | C: reports recorded with a RELEASE, early, and of every kind | `gate_release.json`; `gate_release_run1.txt` (phase read from the wrong place), `_run2.txt` |
| `gate_unknown.py` | B1 to B3: the UNKNOWN report and the verdict transitions | `gate_unknown_B1.json`, `_B2.json`, `_B3_len3.json`, `_B3_len4.json`; consoles `*_run*.txt` |
| `gate_sizes.py` | D: report sizes; the mailbox at its limit | `gate_sizes.json`; `gate_sizes_run1.txt` (void: started while B3 held the fixed ports), `_run2.txt` |
| `gate_result_store.py` | E: can a stored result be changed; is storing one in the chain | `gate_result_store.json`, `gate_result_store_run1.txt` |
| `gate_rows_as_service.py` | F: every report row against the chain, read with the service's own database role | `gate_rows_as_service.json`, `gate_rows_as_service_run1.txt` |
| — | the host's clocks | `clocks.txt` |

Each JSON file is the last run's; the console files keep every run, the failed ones included. Databases: `plea23`
(A, C, D) and `plea24` (B, E), each made new for these tests and shared by the parts named; part F reads both.
Parts C4 and C8 read the store's table of reports with the database owner's password, which is outside the service's
stated powers; part F repeats that check with the service's own role. The harness writes each test deployment's own
files under `outputs/verify_tests/` of the pinned copy; no source file of it is changed.

`review/` holds the independent reviewer's own scripts (`rv_*.py`), its outputs (`out/`), its checksum list of the
pinned copy before its runs, and the output of its re-run of the author's model (`authormodel/run.txt`). The reviewer
used the database `plea25`.
