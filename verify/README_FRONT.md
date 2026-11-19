# Front door and MCP server for the verification record

11 November 2026. Private working material. Branch `verification-mcp-front-door`; not merged, not released.

An assistant's host application talks to the verification service through three MCP tools: show the requirement,
submit a design, read the status. Behind the tools is one HTTPS address, the front door, which is the only part of
the service the assistant's side can reach. The assistant's side holds a certificate for its job and nothing else.

It adds files beside the first plug-in and changes none of them. The witness service, the gate host, the governor
and the store are PLEA gateway v1.2.1, unchanged. This is internal evidence: nobody outside has reviewed or attacked
it.

## Why it exists

Two defects were found in the first plug-in after its results were reported. `AMENDMENT_2026-11-11.md` records them.

1. **The caller chose the baseline.** The assistant-side command held the gateway's database credential and sent
   the baseline's hash itself. The gate's tool cannot see which budget a run was admitted under, so a design could
   be run against a relaxed baseline while another baseline's budget was charged, and the caller was told PASS.
   The offline check of the record catches it afterwards, but the wrong answer had been given.
2. **One malformed design broke a record.** A design holding a character or a number the database cannot store
   was run and signed, could not be saved, and left the record of its baseline unable to verify.

The front door closes both. No request names a baseline: the service knows the job from the caller's certificate
and the baseline from a binding the engineer signed. A request that is not a design is refused before anything
happens. A third, smaller defect is recorded in the amendment and is not closed here.

**Note of 12 November 2026.** `AMENDMENT_2026-11-12.md` repairs that third defect and three more found while looking: a notice
that could be written over another, a number in a design that could leave a record unable to verify, and a check
that prints something unreadable. The second of these means "the front door closes both" was too strong for the second
defect: until that amendment, a design holding one kind of number got through the front door and spoiled its record.
`DECLARED_AMEND2.md` lists what is still open.

**Second note of 12 November 2026.** `AMENDMENT_3_2026-11-12.md` repairs the first thing that list held: a design's own names
and text could be read, in a notice and in a printed record, as words of the service. `DECLARED_AMEND3.md` has the list
as it now stands.

**Third note of 12 November 2026.** `AMENDMENT_4_2026-11-12.md` repairs the record's eighth defect: a notice said that
nothing was changed whatever the reason, so the notice of a changed check said the opposite of its reason. It also
repairs the Verdict row and the banner of a revised baseline. `DECLARED_AMEND4.md` has the list as it now stands.

**Note of 13 November 2026.** `AMENDMENT_5_2026-11-13.md` repairs what Amendment 4 left of the eighth defect: the
requirement line of a notice no longer calls the baseline "unchanged", the Check line says "Baselined hash", a pass
says what is so of the card, and the front door's own text, when it cannot read the card, names the gate's reason and
sets the design out as sent. `DECLARED_AMEND5.md` has the list as it now stands.

**Note of 15 November 2026.** `AMENDMENT_6_2026-11-15.md` keeps a notice about a hash the service holds no
baseline for out of a real engineer's inbox: the inbox now holds the full hash of its baseline, and any other notice is
kept in `inbox/unclaimed/`. The front door was not open to this. `DECLARED_AMEND6.md` has the list as it now stands.

**Note of 16 November 2026.** `AMENDMENT_7_2026-11-16.md` repairs five defects of the register (D1, D2, D3, D4 and D11).
A notice the inbox cannot take is kept in the service's own `undelivered/` store, and the verdict is returned with its state.
A card whose stated limits are not text is refused. The journal has a size limit, and the disk keeps room for notices, for every
submission: the door refuses a new run with 507 `STORAGE_FULL` when either would be exceeded. A cut-off run is noticed once, at the
ask that the gate answers as interrupted. `DECLARED_AMEND7.md` has the list, and the open items.

**Note of 17 November 2026.** `AMENDMENT_8_2026-11-17.md` closes what Amendment 7 left silent in D3 and D1. The gate proves that it
can write each baseline's inbox, and keeps a dated proof. A job is enrolled or moved, and a new run admitted, only on a good
proof: without one the door refuses with 503 `DELIVERY_UNPROVEN`. Each baseline has its own share of the journal. A refusal for an
unproven inbox, or for want of room, writes one notice to the engineer for each reason on the day. `DECLARED_AMEND8.md` has the
list, and the open items.

**Note of 17 November 2026.** `AMENDMENT_9_2026-11-17.md` takes up three of a reviewer's points. What a person or an assistant
reads of a pass calls it the declared check met, with what the check does not cover under the headline; the signed verdict stays
PASS. A second baseline for a requirement the service holds is a revision, or needs the engineer's reason, which goes into the
signed card with the baselines held. What Amendment 8 called a proof of delivery is an inbox-writability check, kept in
`inbox_checks/`; the door's refusal without one is 503 `INBOX_UNCHECKED`. The door looks for runs left pending and asks for them
itself, so that a run cut off gets its notice with no one sending its design again. `DECLARED_AMEND9.md` has the list, and the
open items.

**Note of 19 November 2026.** `AMENDMENT_10_2026-11-19.md` lets a reader ask whether a record is the latest. The witness signs
a checkpoint of a baseline's chain on request, and every record the front door's deployment builds carries one, checked by the
record's ninth check. `check_record.py --checkpoint` says whether a record is current against a checkpoint fetched separately,
and `checkpoints.py` keeps the witness's checkpoints apart from the service, refusing a rollback or a fork. The front door
itself is unchanged. `DECLARED_AMEND10.md` has the list, and the open items.

**Second note of 19 November 2026.** `AMENDMENT_11_2026-11-19.md` adds a second path for notices to the engineer. A courier
that reads only the witness signs a notice of each run that calls for one and delivers it to the engineer's own mailbox,
which signs a receipt; a record can carry both, checked by its tenth check. The front door's deployment also starts the
mailbox. The front door itself is unchanged, and so are the service's own notices. `DECLARED_AMEND11.md` has the list, and
the open items.

## The pieces

| file | what it does |
| --- | --- |
| `front_door.py` | The service's one address for callers, over mutual TLS. Holds the gateway's database credential and no signing key. Runs the governor. |
| `front_ctl.py` | The engineer's console for it: enrol a job, move it to a revision, revoke it, build the record. Needs the engineer's key. |
| `front_client.py` | The assistant's side as a command: `show`, `submit`, `status`. Standard library only. |
| `plea_verify_mcp.py` | The same three as MCP tools over stdio, and the signed baseline as a read-only resource. Standard library only. |
| `deploy_front.py` | One service with a front door on one machine, for the tests and the demonstration. |
| `../tests/verify_front_tests.py` | Tests F1 to F16. |

`DECLARED_FRONT.md` states what the tests were expected to show before the official run; `REPORT_FRONT.md` gives
the results.

## Who holds what

| party | holds | cannot |
| --- | --- | --- |
| Assistant's side (MCP server, or the command) | the service's address, the authority's certificate, the job's certificate and key | reach the database, the witness or the gate; name a baseline, a limit, a check or a run; sign anything |
| Front door | the gateway's database credential, a certificate the witness and the gate admit, three public keys | provision, stop or rewrite a budget; sign a receipt, a verdict, a baseline or a record |
| Witness service, gate host | their signing keys (as in v1.2.1) | be reached by any certificate but the front door's |
| Responsible engineer | the engineer's key, the control credential, the authority's key | (this is the trusted party for the requirement) |

## Setting it up

The service side, once (the witness service and the gate host as in `deploy.py`, each started with
`--tls-allow frontdoor`):

    python verify/front_door.py --home HOME --port 8973 --witness-url https://... --witness-key HEX \
        --gate-host https://... --gate-key HEX --engineer-key HEX \
        --tls-cert front.crt --tls-key front.key --tls-ca ca.crt --upstream-cert frontdoor.crt --upstream-key frontdoor.key

The engineer, for each job, after baselining with `verify_ctl.py baseline`:

    python verify/front_ctl.py enrol HOME pump-station-17 BASELINE_HASH --key engineer.key \
        --ca ca.crt --ca-key ca.key --url https://verify.example:8973 --out job-folder

`job-folder` then holds `job.json`, `ca.crt`, `job.crt` and `job.key`. Give that folder, `front_client.py` and
`plea_verify_mcp.py` to the assistant's machine. In the host application's MCP settings:

    {"mcpServers": {"plea-verification": {"command": "python3",
        "args": ["/path/to/plea_verify_mcp.py", "--job-dir", "/path/to/job-folder"]}}}

After a revision (`verify_ctl.py revise`), move the job: `front_ctl.py rebind HOME pump-station-17 NEW_HASH --key
engineer.key`. The record is built with `front_ctl.py record` and checked with `check_record.py`, as before.

## What the tools return

`plea_submit_design` returns the verdict first, in words, and the same verdict as fields. A pass is given as the
declared check met, with what the check does not cover; it is signed as PASS, and the field `outcome` still says PASS.
It is not a statement that the check is correct. PASS, FAIL and UNKNOWN are all results: `isError` is false. `isError` is true only when nothing was decided: the call was malformed, the
service refused (stopped, held, used up, not enrolled, another run in progress) or could not be reached. One tool
call is one request and nothing retries. Sending the same design again returns the verdict already held.

## What it does not do

- **It cannot make a host show a result, or an assistant repeat it truthfully.** MCP delivers a tool's result to the
  host application and stops there. The failure does not depend on it: the service keeps the signed verdict and
  sends a FAIL or UNKNOWN to the engineer itself. The rule is unchanged: no record, not verified.
- **The record's format is the first plug-in's**, with one field of the card added by Amendment 9. A reader of one
  record sees a change of requirement when it was made by revision, and a second baseline made as new at the same
  service for the same requirement id names, in its signed card, the baselines held and the engineer's reason. A
  relaxed requirement given a new id, or baselined at another service, is not linked. Opening a second job for the
  same requirement under another baseline still needs the engineer's reason, which is kept in the service's signed log
  (`HOME/front/enrolment.jsonl`).
- **A party who can write the service's files** can put an earlier signed binding back. The front door refuses one
  older than it has seen since it started; a restart forgets that.
- **A job certificate is a bearer of the job.** Whoever holds the folder can spend the job's runs and cause notices.
  It cannot change what is verified against.
- **One machine does not show separation.** In the tests every party runs under one account. An assistant with a
  shell on that machine could read the keys.
- Everything the first plug-in's README says it does not do still holds: it does not know whether the check is
  right, and it sees only work that goes through it.
