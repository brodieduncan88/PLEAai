# Final specification round of Amendment 16, 21 November 2026: tests, model and prewritten acceptance tests

Development evidence and separately authored verification only. Nothing here is a declaration, an official run, an
acceptance or proposed production code. No code of `e25a297` is changed. Everything was run on one machine under one
account, where preconditions DP1 and DP2 do not hold: by rule ACC-2 of the specification, nothing here establishes
acceptance of the production contract.

| Path | What | By whom |
|---|---|---|
| `gate_s5_capability.py`, `gate_common.py`, `results_2026-11-21/` | which capability S-5 and S-1 need: a dishonest database role replaying genuine reports (CAP-DB) against a compromised gate key (CAP-KEY). Run 1 lacks the last step (a courier pass with no waiting time); run 2 has it | the specification's author |
