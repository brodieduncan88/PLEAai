# Verification record plug-in: demo

11 November 2026. Private working material. Branch `verification-record-demo`; not merged, not released.

An engineering team gives an AI assistant a requirement. If no design meets it, the assistant must not quietly
change the part, relax the limit, narrow the load case or weaken the check. This plug-in sits between the assistant
and the verdict:

1. **The requirement is baselined first** by a named engineer: the limits, the load case, what may be varied, the
   check and its data. The assistant cannot edit it.
2. **The check runs on the service's side**, once per design, and the service, not the assistant and not the check,
   compares the result with the baselined limits.
3. **A failure is a signed result with its reason**, kept on the record and sent straight to the engineer.
4. **Only the engineer can change the requirement**, as a new signed baseline that says what it replaced and what
   had failed on it.

It records what the declared check returned. It does not know whether the check is right, and it sees only work
that goes through it. The rule that follows is: no record, not verified.

It reuses the PLEA gateway v1.2.1 unchanged (witness service, gate host, governor, store). This is internal
evidence: nobody outside has reviewed or attacked it.

## The pieces

| file | what it does |
| --- | --- |
| `baseline.py` | The requirement card, the design space, and the decision: PASS, FAIL or UNKNOWN with a reason. A pass is signed as PASS and shown to people as the declared check met. |
| `verify_tools.py` | The one tool the gate host runs. Never refunds a failure. Writes the engineer's notice. |
| `verify_client.py` | The assistant's command: `show`, `submit`, `status`. Holds no signing key. |
| `verify_ctl.py` | The engineer's console: baseline, revise, acknowledge, record. A second baseline for a requirement it already holds is a revision, or needs a reason that goes into the signed card. |
| `verify_record.py` | The signed baseline envelope and the signed record. |
| `check_record.py` | Checks a record offline. Stands alone: standard library and `cryptography` only. |
| `deploy.py` | One service on one machine, for the demo, the tests and the trials. |
| `cases/pump-station-submain/` | The worked case: a 400 V sub-main that no allowed cable can make comply. |
| `experiment/` | The trial of what assistants do with that job, with and without the service. |
| `../tests/verify_tests.py` | Tests R1 to R13 of the plug-in itself. |

`DECLARED_VERIFY.md` states what the tests were expected to show before the official run; `REPORT_VERIFY.md` gives
the results of the tests and of the trial. `experiment/PROTOCOL.md` is the trial's protocol, frozen before it ran.

## One machine does not show separation

In this demo the service, the database, the engineer's key and the assistant all run under one account on one
machine. An assistant with a shell there could read the keys. A real deployment keeps the service, the keys and the
control credential where the assistant cannot reach them.
