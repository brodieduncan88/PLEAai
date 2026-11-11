# Front door and MCP server: declaration before the official test run

11 November 2026. Private working material.

This file is committed before the official run of `tests/verify_front_tests.py`. It fixes the code, states what each test
is expected to show, and records what was done in development. The official run is made once after this commit and
its first result is kept, pass or fail. A later correction would be a separate, dated amendment.

## What is fixed

Base: `verification-record-demo` at `757a757`, the verification record plug-in as reported, on `main` at `b4503ba` (PLEA
gateway v1.2.1). No file of either is changed on this branch: every file listed in `DECLARED_VERIFY.md` still has the
hash given there, and `git diff 757a757` is empty for the gateway, the first plug-in and its tests. The files below are new.

| file | sha256 |
| --- | --- |
| `verify/front_door.py` | `a9db5e29c08d6e76933506b1e1e77a1b6f7c6f8517c59f84dcff75f464c031fd` |
| `verify/front_ctl.py` | `d0d0ab91c78974cbdff59562f5d27f371a1dd61ac76d50ac3ab19164d397b0c9` |
| `verify/front_client.py` | `06fc9e7ac701e09d0fe7d132cc633f402999dda6ce39002c2a1bbd6a228b2c78` |
| `verify/plea_verify_mcp.py` | `43d1b37cd079291bb1ba31b76bc4687eed32341cd01771b394a3d3de2ba3941a` |
| `verify/deploy_front.py` | `7df5a15149240275a513e9ed9b6e73e4b4717f75a3820827dc6b09afaa2a35a7` |
| `verify/demo_front.py` | `bf2ab2810b666a55addd5bc6209485ece796ec59f6e8ae270c3dff74d10b7bbd` |
| `tests/verify_front_tests.py` | `ddcd6bd853fcb58f5d398904690b4b7652abb6c369b516048f8efd01eb3710d6` |
| `verify/dev_front_mutants.json` | `1271eacb01b756dfc51362cf7c41e08251f99af91bf797c8ad00c859f1940cfa` |

Environment: Python 3.11, cryptography 50.0.2, psycopg 3.3.8, PostgreSQL 16, one machine, all services on 127.0.0.1.

## What each test is expected to show

F1 and F2 run the first plug-in as released, with no front door. They pass when the two defects they describe are
present, which is what is expected: the defects are in files this branch does not change. They are recorded in
`AMENDMENT_2026-11-11.md`, which is committed with the results.

F3 to F16 each make a fresh deployment (new keys; the released witness service and gate host, unchanged, admitting only
the front door's certificate; `front_door.py`; the gate host loading `verify_tools`), baseline the self-test fixture in
`tests/verify_case/` as the responsible engineer, enrol a job, and act as an assistant's host application through
`plea_verify_mcp.py`, or as a caller that holds the job's certificate and writes its own requests. The host application
is a small harness in `deploy_front.py`; no host product is run. The fixture is a toy (a material's rated temperature
against a 200 C limit); it tests the plug-in, not engineering. A test passes only if every check listed is true.

**F1. The first plug-in, with no front door: a caller holding the workspace's credentials can run a design against another baseline and be told PASS.**
- sent honestly, the design fails against A (exit status 2)
- naming baseline B on A's budget, the same design is told PASS
- the run is charged to A, B shows no run, and nobody is sent a notice for it
- the record of A no longer verifies, at checks 5 and 6 only

**F2. The first plug-in, with no front door: one design the database cannot store leaves the record of its baseline unable to verify.**
- the client stops with a traceback (exit status 1), both times
- a run is left with a signed verdict and no stored result
- a good design sent afterwards meets the check (exit status 0)
- but the record of that baseline no longer verifies, at check 6 only, and its status is NOT VERIFIED

**F3. Through the MCP server, a design that does not meet the requirement gets a signed FAIL with the reason, kept on the record and sent to the engineer.**
- the tool result leads with FAIL and the required and achieved values, and is not marked as a tool error
- the same verdict is given as fields: outcome FAIL, not met, for this job's baseline
- the record holds the FAIL with reason LIMIT_NOT_MET, 180 against 200, margin -20
- the record verifies offline and its status is NOT VERIFIED
- one notice is in the engineer's inbox, from the service, naming the failure

**F4. The same design sent again, by tool call or by command line, returns the same verdict: one run, one notice.**
- all four answers are the same FAIL (the command line exits with status 2)
- they name one run
- the check ran once and one notice was sent
- the record shows one official run

**F5. The server offers exactly three tools, and a call that is not exactly a design goes no further.**
- the tools are plea_show_requirement, plea_submit_design and plea_status, and no other
- plea_submit_design takes `design` and nothing else; the other two take nothing
- the relay refuses each malformed call itself and says nothing was sent
- asked directly, the front door refuses the same shapes (400)
- nothing was run or recorded: no run of the check, no audit row, no journal line, no notice

**F6. Through the front door a caller cannot choose the baseline: the defect of F1 is closed.**
- a baseline named as a tool argument or as a field of the request is refused and nothing is run
- a baseline named in a header changes nothing: the design is decided against the job's own baseline and fails
- a baseline named inside the design is a design outside the baseline: FAIL, on the record
- every verdict returned names the job's own baseline
- the relaxed baseline has no run and no audit row; the job's record verifies with two failures, NOT VERIFIED
- both failures were sent to the engineer of the job's baseline

**F7. A request that is not a design is refused before anything happens: the defect of F2 is closed.**
- each of fourteen malformed requests is refused (400, or 411 with no length)
- through the tool and the command line the same input is refused, and the answer says nothing was recorded
- nothing happened: no run of the check, no audit row, no notice, no journal line
- a good design sent afterwards meets the check, and the record verifies: one run, DECLARED CHECK MET

**F8. What the assistant's side holds cannot reach the store, the witness or the gate, and cannot sign anything.**
- the job folder holds the service address, the authority's certificate and the job's certificate and key, and nothing else
- the job's certificate is refused by the witness service and by the gate host (403)
- so is any other certificate of the authority that is not the front door's
- the MCP server and its client import the standard library only
- started with an empty environment and that folder alone, the server still gets a design verified

**F9. Nothing the engineer does is offered to the assistant's side, by tool or by address.**
- a call to any other tool name is an unknown tool (-32602)
- the server answers no other kind of request, and serves no resource but the signed baseline
- the front door answers 404 to every other address and method
- nothing changed: the bindings, the baselines, the budget, the audit rows, the ledger, the inbox

**F10. Only the certificate the engineer enrolled, for a job the engineer has not revoked, under a binding the engineer signed, is answered.**
- a certificate from another authority gets no answer at all
- a certificate of this authority that was not enrolled is refused (403), whatever its name
- a binding pointed at another baseline, or re-signed by another key, or unreadable, admits nobody
- after the engineer revokes the job its own certificate is refused, and the tool says so as an error
- putting the earlier signed binding back in the file does not undo the revocation
- nothing was run in any of this

**F11. A job moves to another baseline only when that baseline is a signed revision of its own, which says what it replaced and what had failed.**
- moving the job to a baseline that is merely different is refused, and so is a second job for the same requirement with no reason
- once the engineer revises, the old baseline takes no further runs: the tool reports the refusal as an error, nothing is run, and the requirement shown says so
- after the move the requirement shown says what it replaced, what had failed and why
- the design that failed on A meets the check on B, and B's record is headed CHANGED AFTER THE EVENT
- the old record still verifies and still shows the failure
- the service's log holds the enrolment and the move, each signed by the engineer, the move naming what it replaced

**F12. The service dying part-way through a run leaves it counted, without a verdict, and never run again.**
- the host died during the run (exit 137) and the tool did not say it passed
- asked again, twice, the answer is UNKNOWN: interrupted, not met
- the check was started once for that design and never produced a verdict
- the record shows it INTERRUPTED and counted, and that design is not verified
- a different design can still be verified
- an error that is not the gate's signed "unknown" is reported as no verdict, not as an interrupted run (the front door's own code, called directly)

**F13. Two jobs on one service each see and charge only their own baseline.**
- the same design fails for one job and meets the check for the other, each against its own baseline
- each job's status shows its own run only
- each record verifies with one run, and only the failing job's engineer notice was sent
- a second job for a requirement already under another baseline needs the engineer's reason, which is kept in the signed log
- a job that asks too often is refused (429) without slowing the other

**F14. The MCP server speaks both forms of the protocol, says nothing but protocol on its output, and makes one request per call.**
- opened with the handshake, each earlier revision is agreed as asked, and an unknown one is answered with the latest of them
- a revision without those fields is not sent them: no annotations or structured content in 2024-11-05, structured content from 2025-06-18
- with the version on each request (2026-07-28) the same three tools are served, complete, and server/discover lists the versions
- an unsupported version, a request with no capabilities, and a tool call before any opening are refused with their codes and nothing is run
- a line that is not JSON and a batch each get an error reply, a notification gets none, and closing the input ends the server (exit 0)
- with the service unreachable a call reports that as an error after one connection, not more, and runs nothing
- when the service is back the same call gets its verdict, from one run

**F15. A stored baseline changed after it was signed is not shown, and a design sent against it is decided UNKNOWN by the gate, counted, and sent to the engineer.**
- the changed baseline is not shown, by address or by tool
- a design that the relaxed card would pass is decided UNKNOWN by the gate, not a pass
- so is one sent against a relaxed card properly signed by another key, and the runs are counted
- with the file restored the requirement is shown again and still fails
- all three results were sent to the engineer
- known gap, not closed here: a stored card that is no longer a card gives a counted run with no verdict, not a pass, and no notice
- no run met the check, the record verifies and the status is NOT VERIFIED

**F16. One run at a time for a job: a second design sent while the first is being checked is refused and not run.**
- while the first design is being checked, a second is refused (409), by address and by tool, and is not run
- the status can still be read meanwhile
- the check that did not finish is stopped and is UNKNOWN, never a pass
- afterwards the second design is verified, and each design was run once
- the record verifies: one unknown, one met

Expected overall: 16 of 16 pass (83 checks).

One check in F15 states a gap that is known and not closed here. It is listed so that the run shows the behaviour as it
is, not as it should be.

## What was done before this declaration

- A first call through the front door and the MCP server, end to end, worked before any test was written (a scratch
  script).
- The test file was run in full four times and in part twice. The first full run, of 14 tests, passed 12. Both failures
  were mistakes in the tests: an evidence line was cut short, so the reason it looked for was not in it; and a count of
  runs was read after the next step had run. No code changed for them.
- Before the second full run I read the new front door as an attacker would and found three weaknesses in it. Each was
  repaired and given a test:
  - an earlier signed binding could be put back in the service's file, undoing a revocation or a move. Bindings now carry
    a number that only rises, and the front door refuses one lower than it has seen (F10);
  - with the stored baseline changed, the front door refused before the gate was asked, so the engineer was not told.
    The budget's name now comes from the signed binding, and the gate decides (F15);
  - pacing per job, and the rule of one run at a time, had no test (F13, F16).

  The second, third and fourth full runs, of 16 tests, passed 16.
- Smaller changes before the third full run: the client bounds the size of an answer it will read; the requirement
  shown says when its baseline takes no more runs; a revoked job still counts when a second baseline is opened for its
  requirement.
- Findings 2 and 3 of `AMENDMENT_2026-11-11.md` came from probes of the first plug-in, made with scratch scripts while
  deciding what the front door must refuse. F2 and one check of F15 reproduce them.
- To check that the tests can fail, 24 deliberate defects were applied one at a time to a scratch copy of the code.
  23 were caught at first. One was missed: M22, a front door that reports any error from the governor as an
  interrupted run. No test reached that guard, because in practice the only such error the governor raises is the
  gate's signed "unknown". The last check of F12 was added for it: it calls the front door's own code with a governor
  that fails in another way. With that check M22 is caught, and the fourth full run was made. The other 23 defects were
  not run again after the check was added; the code they were run against is the code declared here.
  `dev_front_mutants.json` holds the first pass. An earlier pass was stopped after four defects, all caught, because
  the code was still changing.

| | deliberate defect | caught by, at first |
| --- | --- | --- |
| M1 | the front door honours a baseline named in the request | F5, F6 |
| M2 | the front door admits any certificate with the job's name (fingerprint not checked) | F10 |
| M3 | the front door does not check the engineer's signature on a binding | F10 |
| M4 | the front door ignores a revocation | F10 |
| M5 | the front door accepts an earlier binding put back | F10 |
| M6 | a job can be moved to any baseline (no revision needed) | F11 |
| M7 | a second job for the same requirement needs no reason | F10, F11, F13 |
| M8 | the front door does not check the characters of a design | F7 |
| M9 | the front door accepts a repeated name | F7 |
| M10 | the front door accepts a number that is not finite | F7 |
| M11 | the witness service and the gate host admit every certificate of the authority | F8 |
| M12 | the MCP relay tries a second time when the service cannot be reached | F14 |
| M13 | the MCP server offers a fourth tool | F5, F9, F14 |
| M14 | the MCP relay lets extra arguments through | F5, F6 |
| M15 | the MCP relay does not mark a refusal as an error | F7, F10, F11, F15, F16 |
| M16 | the front door lets a job run two designs at once | F16 |
| M17 | the MCP server sends structured content to a revision that has none | F14 |
| M18 | the front door does not pace a job | F13 |
| M19 | the front door runs a design sent to any address | F6, F9 |
| M20 | enrolment leaves the engineer's key in the job folder | F8 |
| M21 | the front door refuses before the gate is asked when the stored baseline was changed | F15 |
| M22 | the front door reports any error from the governor as an interrupted run | **not caught**; after the added check, F12 |
| M23 | a revoked job is ignored when a second baseline is opened for its requirement | F10 |
| M24 | the requirement shown does not say its baseline was stopped | F11 |

- No load or stress test was made.

## What is not tested

- **An assistant, or a host product.** The host application is played by a small harness. Whether a real host shows a
  FAIL as the service returns it, and whether an assistant reports it truthfully, is not tested and cannot be enforced
  from here.
- **Separation by machine.** Every party runs under one operating-system account. An assistant with a shell on this
  machine could read the keys. The tests show separation by process, credential and certificate only.
- **Repairs to the first plug-in.** Its two defects are shown (F1, F2), not repaired, and the third is shown (F15), not
  repaired. The first client must not be what an assistant is given.
- **A restart of the front door** between a revocation and an older binding being put back. The front door keeps the
  latest binding it has seen in memory.
- **Expiry or renewal of a job's certificate; sign-in by OAuth; any transport but stdio for MCP.**
- **More than two requests at once.**
- **The last check of F12 is from the inside:** it calls the front door's code directly with a stand-in for the governor.
- **The engineering.** The fixture is a toy.
- **The owner.** One party holds the witness, gate and engineer keys and the certificate authority.
- **Any independent review.**
