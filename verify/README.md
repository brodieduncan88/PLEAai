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
| `check_record.py` | Checks a record offline. Stands alone: standard library and `cryptography` only. With `--checkpoint`, says whether the record is current against a checkpoint the witness signed. |
| `checkpoints.py` | A second party's log of the witness's checkpoints: refuses a rollback or a fork, and keeps the evidence. Standard library and `cryptography` only. |
| `deploy.py` | One service on one machine, for the demo, the tests and the trials. |
| `cases/pump-station-submain/` | The worked case: a 400 V sub-main that no allowed cable can make comply. |
| `experiment/` | The trial of what assistants do with that job, with and without the service. |
| `../tests/verify_tests.py` | Tests R1 to R13 of the plug-in itself. |

## Is this the latest record? (Amendment 10, 19 November 2026)

A record is a statement as of its own last decision, and an older record still verifies. The witness service now signs a
checkpoint of a baseline's chain on request (`GET /checkpoint?root=...`): how many decisions it holds, the hash of the
last, the budget's state and the witness's clock, with a nonce of the asker's signed back. A record built with
`--witness-url` carries one, and the checker's ninth check requires it to be the witness's and to name the record's own
head. To ask whether a record is the latest, fetch a checkpoint yourself, with a nonce of your own, and give it to the
checker:

    python3 checkpoints.py fetch --witness-url URL --ca CA --cert CERT --key KEY --root ROOT --witness-key HEX --out cp.json --log log.jsonl
    python3 check_record.py record.json --keys keys.json --checkpoint cp.json --nonce NONCE --max-age 600

`fetch` makes its own nonce and writes it in `cp.json`. The checker prints CURRENT, SUPERSEDED, SUPERSEDED_UNPROVEN,
FORKED, OLDER, STALE or INVALID, and exits 0 only for CURRENT. With no age given it allows an hour. CURRENT says only that the checkpoint was made within the age allowed and ends where the
record does: a checkpoint handed over by someone else, not fetched with your own nonce, may be an old one replayed.
The witness is still one party: a witness that lies the same way to everyone is not caught.

`DECLARED_VERIFY.md` states what the tests were expected to show before the official run; `REPORT_VERIFY.md` gives
the results of the tests and of the trial. `experiment/PROTOCOL.md` is the trial's protocol, frozen before it ran.

## One machine does not show separation

In this demo the service, the database, the engineer's key and the assistant all run under one account on one
machine. An assistant with a shell there could read the keys. A real deployment keeps the service, the keys and the
control credential where the assistant cannot reach them.
