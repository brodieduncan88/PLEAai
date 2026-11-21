# Final specification round of Amendment 16, 21 November 2026: tests, model and prewritten acceptance tests

Development evidence and separately authored verification only. Nothing here is a declaration, an official run, an
acceptance or proposed production code. No code of `e25a297` is changed. Everything was run on one machine under one
account, where preconditions DP1 and DP2 do not hold: by rule ACC-2 of the specification, nothing here establishes
acceptance of the production contract.

| Path | What | By whom |
|---|---|---|
| `gate_s5_capability.py`, `gate_common.py`, `results_2026-11-21/` | which capability S-5 and S-1 need: a dishonest database role replaying genuine reports (CAP-DB) against a compromised gate key (CAP-KEY). Run 1 lacks the last step (a courier pass with no waiting time); run 2 has it | the specification's author |
| `review/` | the reviewer's own probes on the unchanged `e25a297` (Q1 to Q4), an offline test of a fence report with its null fields deleted, its own diffs of the versions, and their outputs | a separate agent (internal review) |
| `model_v1/` | a bounded model of sections 5 to 8 of specification version 1: `model.py`, `configs.py`, the declarations written before the runs (`declared/`, and the first declarations `declared_v1/`), 60 configurations with results and consoles (`results/run1/`), a first run kept INCOMPLETE (`results/run0_first_attempt/`), sizing logs, and one undeclared diagnostic (`diag_age.py`). Preserved exactly as the agent left it | a separate agent (separately authored verification) |
| `model_v2/` | the same agent's bounded model of specification version 2: a fresh `model.py`, declarations written before the runs, 60 configurations with results and consoles (`results/run1/`), sizing logs. Preserved exactly as the agent left it | a separate agent (separately authored verification) |
| `model_v5/` | the same agent's bounded model of specification version 5: 74 configurations with declarations, results and consoles. Its fixed design violates SAF-10 where the mailbox loses its record and the witness is rolled back (finding M30), which version 6 corrects. Preserved exactly as the agent left it | a separate agent (separately authored verification) |
