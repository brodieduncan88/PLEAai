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
| `verify_client.py` | Retired by Amendment 17 (22 November 2026): it refuses to run. It was the first plug-in's assistant-side command, and it held the gateway's database credential in the assistant's workspace. The assistant's route is the front door (`front_client.py`, `plea_verify_mcp.py`; see `README_FRONT.md`). |
| `service_client.py` | Amendment 17: the service's own reading of one baseline's runs and words, moved here from the first client; used by the front door and the console, never given to an assistant. |
| `verify_ctl.py` | The engineer's console: baseline, revise, acknowledge, record. A second baseline for a requirement it already holds is a revision, or needs a reason that goes into the signed card. |
| `verify_record.py` | The signed baseline envelope and the signed record. |
| `check_record.py` | Checks a record offline. Stands alone: standard library and `cryptography` only. With `--checkpoint`, says whether the record is current against a checkpoint the witness signed. |
| `checkpoints.py` | A second party's log of the witness's checkpoints: refuses a rollback or a fork, and keeps the evidence. Standard library and `cryptography` only. |
| `courier.py` | Notices to the engineer that the service does not write: reads only the witness, signs each notice with its own key, delivers it to the engineer's mailbox. |
| `mailbox_service.py` | The engineer's mailbox: keeps each notice a courier delivers and signs a receipt for it. |
| `sandbox.py` | The disposable sandbox each run of a check is made in, and thrown away after. |
| `deploy.py` | One service on one machine, for the demo, the tests and the trials. Since Amendment 17 it writes no assistant workspace. |
| `cases/pump-station-submain/` | The worked case: a 400 V sub-main that no allowed cable can make comply. |
| `experiment/` | The trial of what assistants do with that job, with and without the service. It was run with the first client, which is retired; its results are kept as they were, and it cannot be run again as it stands. |
| `../tests/verify_tests.py` | Tests R1 to R34 of the gate and the service (R1 to R13 as declared first, R14 to R29 by Amendments 2 to 15, R30 to R34 by Amendment 17). Since Amendment 17 the tests act as the assistant through the front door, not the first client, except R14, R17, R18, R25 and R26, which test the gate under the plain deployment and reach it as the service's own caller (`../tests/service_route.py`, a test harness only). `demo.py` used the first client and is not runnable as it stands. |

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

## Notices the service does not write (Amendment 11, 19 November 2026)

The service writes its own notice of a failing run into an inbox it controls, and whoever can write that inbox can remove
or change it. A courier (`courier.py`) is a second path. It has its own key and certificate, and reads only the witness:
the decisions since it last looked, checked against a checkpoint it asked for with its own nonce, and each run's gate
reports and stored result, believed only if the gate signed them. For each run that failed, did not decide, was
interrupted, was made indeterminate by the control plane, or has had no outcome for 15 minutes, it signs a notice and
delivers it to the engineer's mailbox (`mailbox_service.py`), which keeps it and signs a receipt. If the courier stops
believing the witness, or cannot reach it, it tells the mailbox that too. A record can carry the notices and receipts:

    python3 courier.py run --config courier.json
    python3 verify_ctl.py record HOME HASH ... --deliveries STATE_DIR/deliveries.jsonl --courier-key HEX --mailbox-key HEX
    python3 check_record.py record.json --keys keys.json --require-delivery     (keys.json with "courier" and "mailbox")

The checker's tenth check verifies each notice and receipt against the record, and it prints which runs that call for a
notice have one delivered and which have none. A receipt says the mailbox holds the notice, not that the engineer read it.
The courier sees what the witness records; a witness that tells it one consistent false chain is believed. A courier that
is not running tells no one: nothing yet notices its silence.

## The check's sandbox (Amendment 12, 19 November 2026)

A check is code the customer supplies, and each run of it gets a sandbox of its own (`sandbox.py`): two host user ids
chosen for that run alone, the first of which makes its new user, mount, process, network, IPC and host-name namespaces; a
read-only root holding /usr (the Python installation and the machine's other programs, without /usr/local, /usr/src or the
site packages), with the check and its data copied into a /work in memory; no network, no other process, none of
the service's files; memory, process and freezer control groups (1 GiB and 64 processes for the run), and limits on
time, file size and output. The check runs as an unprivileged id with no capabilities and a session keyring of its own. A
small system-call filter refuses every socket (vsock, which a network namespace does not close, and Unix sockets, whose
queued data the memory group does not count), the keyring, io_uring, native asynchronous I/O, bpf, perf and userfaultfd
calls. When the run ends,
everything it started is killed and the sandbox is thrown away. The first process of the run's process namespace is the
sandbox's own, not the check, and the run ends with it. If the service dies during a run, the run's processes die with it,
unless it dies while they are frozen for their kill; what the run leaves, those included, is removed by a later run once
ten minutes old. If it cannot be made, the check is not
run and the verdict is UNKNOWN. The check gets the Python standard library only. The service must run as root on x86-64,
with cgroup v1 memory, pids and freezer controllers (a machine with cgroup v2 only is refused), on a machine whose file
table (fs.file-max) is at least twice what the four runs a machine makes at once can keep open (Amendment 15). That floor
is worked out from the machine's limit on mappings: about 33.6 million where a process may have 65,530, the kernel's
default, and about 134 million where it may have 1,048,576, as Ubuntu 24.04 sets it when started in the usual way. A run
can hold files open through memory mappings; one was measured holding 2.6 million, more than this machine's own table of
1.6 million. `python3 sandbox.py --prerequisites` says what is met and what is not, and gives the floor; it makes no run.
The setting is not kept when the machine is started again, unless the operator makes it so (`fs.file-max` in
`/etc/sysctl.d`, at the number that command gives). The
filter narrows the calls a check can make; it does not close
them: a flaw in the kernel's other calls would still be a way out. The sandbox is no virtual machine.

`DECLARED_VERIFY.md` states what the tests were expected to show before the official run; `REPORT_VERIFY.md` gives
the results of the tests and of the trial. `experiment/PROTOCOL.md` is the trial's protocol, frozen before it ran.

## One machine does not show separation

In this demo the service, the database, the engineer's key and the assistant all run under one account on one
machine. An assistant with a shell there could read the keys. A real deployment keeps the service, the keys and the
control credential where the assistant cannot reach them.
