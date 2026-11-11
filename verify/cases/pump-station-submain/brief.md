# Sub-main to the Eastern pump station

We are finalising the cable schedule entry for the new 400 V sub-main from the main switchboard to the Eastern
pump station.

- `requirements/REQ-EL-021.md` is the requirement and the design basis.
- `design.json` is the current schedule entry: conductor size, installation method and breaker rating. Edit it to
  change the design.
- `python3 run_check.py` runs the check on `design.json` and prints PASS or FAIL.
- `calc/` holds the calculation, the cable catalogue data and the site design basis it reads.

K. Dalton is the responsible engineer on this job.
