# Amendment 12: declaration before the official test runs

19 November 2026. Private working material.

This file is committed before the official runs of `tests/verify_tests.py` and `tests/verify_front_tests.py` on the branch
`verification-amendment-12`. It fixes the changed code, states what each test is expected to show, and records what was done
in development. Each official run is made once after this commit and its first result is kept, pass or fail. A later
correction would be a separate, dated amendment. Times are UTC.

## Why declared files are changed

A declared check is code the customer supplies, and the service ran it as a separate process in an empty folder, under the
service's own account, with the service's network, its files and its processes in reach. A check that meant harm could read
the engineer's key, the ledger or the witness's TLS key, reach the database, or leave a process running. This is D19 in the
defect register, and release gate G2, "strong disposable sandbox for customer-supplied checks", of 19 November. On 19
November the owner asked for G2 to be built, by the same process as Amendments 10 and 11.

## What is changed

**Each run of a check gets a sandbox of its own.** `verify/sandbox.py` is new. `baseline.evaluate` hands it the verified
bytes of the check and its data files, the design on standard input, and the time allowed, and reads back what the check
printed. For each run, the service, as root:

- chooses two host user ids for that run alone, from a range of 2^25 ids above 2,000,400,000, named by no account and used
  by no process at that moment: one is the run's root inside its namespaces, the other its unprivileged user;
- makes memory, process and freezer control groups (cgroup v1) for the run, within the service's own: at most 1 GiB of
  memory, swap included where there is swap, and 64 processes, for the run's processes together;
- starts a launcher in those groups. The launcher takes the first of the run's ids and, as that id, not as root, makes new
  user, mount, process, network, IPC and host-name namespaces. So what the kernel counts for each user (inotify and
  fanotify use, message queues, pending signals) is counted against the run's own id, not against root's, which the
  machine's other processes share. The service writes the run's two ids into the new user namespace's maps.

The launcher dies with the service, and keeps the run's time itself, five seconds beyond the service's own. Its child, the
first process of the new process namespace, is the sandbox's own and never the check: it refuses to go on unless every
namespace is new, none of them the service's, the only network is a loopback, and only the run's two ids are mapped. It
dies with the launcher, and when it ends, the kernel ends every other process of the namespace. It builds a root of its own
in memory:

- /usr, read-only throughout: the Python installation and the machine's other programs, with /usr/local, /usr/src and the
  site and dist packages hidden;
- /work, in memory, at most 64 MiB and 1024 files, holding copies of the bytes that were hashed; and /tmp, another 64 MiB
  and 1024 files;
- /dev/null, /dev/zero and /dev/urandom; nothing else of the machine: not /etc, not /proc, not the service's home.

It names the host "sandbox", and starts the check as its own child. It then reaps every process the check leaves, and ends
when the check's own process ends, with its status. The check runs as the run's unprivileged id, so it can neither trace nor
signal the first process. In the check's process, the sandbox sets limits on each process (CPU time, memory, file size, 64
open file descriptors, 64 pending signals, no message-queue bytes, no core dumps); joins a session keyring of its own;
empties its capability bounding set; takes the unprivileged id with no other group; sets no new privileges; and installs a
small system-call filter:

- no sockets of any family: so no vsock, which a network namespace does not close, and no Unix sockets, whose queued data
  the memory group does not count;
- the keyring, io_uring, native asynchronous I/O (whose limit is the machine's), bpf, perf and userfaultfd calls refused;
- the calls of any other architecture, and the x32 calls, end the process.

It says on a pipe the check does not inherit that the sandbox is ready, then starts the check with the standard library
alone (`python -I -S`). If the check cannot be started, it says that too.

The service writes the design without blocking, reads at most 1 MiB of each of the check's two outputs, and keeps the
time; output still waiting may hold its clock for at most half a second. When the run ends, it freezes the run's groups,
kills every process in them, frees what the kernel keeps charged to the run's memory group, removes the groups, and removes
the run's folder. A service killed during a run leaves groups and folders that a later run of a service in the same groups
removes, once they are ten minutes old, thawed first if they were left frozen. At most four runs are made at once by one
service; a run that waits longer than its own time for its turn is not made, and the check is not run.

**A sandbox that cannot be made means the check is not run.** Without root; on another architecture than x86-64; on a
machine whose file table (`fs.file-max`) is below 2^40, since a run can keep files open through memory mappings beyond its
limit on descriptors, and only its memory bounds how many; without the control groups; or if the launcher refuses or never
says it is ready: the outcome is SANDBOX_UNAVAILABLE. `baseline.evaluate` then gives UNKNOWN, CHECK_ERROR, "the check was
not run: ...", and the service writes the engineer its notice as for any UNKNOWN. Nothing falls back to running a check
outside a sandbox. A run still going at its time gives "the check did not finish within 30 s"; one that printed more than
1 MiB says so.

**The deployment can start a gate host with a changed environment** (`deploy.Services.start_host(extra_env=...)`), so that a
test can point the sandbox at control groups that do not exist (`VERIFY_SANDBOX_CGROUP_ROOT`).

The verdict's format, the record, its checker, the front door, the MCP server and the courier are unchanged. A check that
uses only the Python standard library and its own files, and stays within the limits above, runs as before. A check that
imports a package installed on the machine, which the old runner allowed, or that needs /proc, /dev/shm or multiprocessing,
no longer runs, and gives UNKNOWN. No check in the repository does either.

## The changed files

Base: `verification-amendment-11` at `f8d2931`. Five files change, one of them new.
The hashes are of the files as they stand at this commit.

| file | sha256 at f8d2931 | sha256 now |
| --- | --- | --- |
| `verify/sandbox.py` | new | `2c0d4a8b8606a109b640ae923ea45c540599d858d8b7135183023558f63fa7a7` |
| `verify/baseline.py` | `075df944071a38e0672136cd26e49eac74a47c6b627f13a5b19c06ff6ea2c737` | `1860168c223ce7db8ae912ff6986b38149a180de17eaaade4944da1bb2a0bdc5` |
| `verify/deploy.py` | `1f2de10c92bac233c58789b664ba8081c9bb68b4d0ef9b4f8b0f2b0edb619f23` | `c3653a493f4bd39e0394587d7dcce651a1dea386aa186b5e0c252f550e16f21b` |
| `tests/verify_tests.py` | `829334f4c056f6893edd2254cefa6bb2f00a2db110a36d708f1c574bda515334` | `e7354ab3e4e89e04bbe9719bf706dbf37426ffe851a174403e8197c50bfba72d` |
| `verify/README.md` | `b3b434e8dddc541fa2010be9ac1e322980b04ad1a7886b9cce28b154183af0fb` | `6d192a0b05463367c4d69c88c55eb668c4bb207cca97746501a9b69daef37cca` |

`verify/sandbox.py` is new. One file is new as a development record: `verify/dev_amend12_mutants.json`, the pass of
deliberate defects on this code.

Every other file in the repository at `f8d2931` is unchanged, among them the gate host, the governor, the gate's tool, the
witness, the courier, the mailbox, the front door, the MCP server and the first client.

## What each test is expected to show

**R1 to R26** are as declared before: the same functions, each expected true. Every check they run is now run in a sandbox.
The test harness (`Run`) now stops the services it started when its own baselining fails, so that a failure does not leave
them holding their ports; this changes nothing when baselining succeeds.

**R27 is new** (15 checks). On a deployment of its own, it baselines a hostile check that tries to read the service's
keys, ledger, baselines, /etc, /proc and code, and to reach the witness, the gate host, the database and an address outside,
and reports what it found. It runs probe checks straight through `sandbox.run` for the limits on processes, memory, output,
time and file size, for what the check can see and call, and for what runs share. It kills a service during a run. It makes
the sandbox fail to be made, in the launcher, in a service and in a gate host. And it runs a well-behaved check:

1. a check runs as nobody (user and group 65534, no other group, even where the service holds one), in /work, which holds only
   its own files, under a root that holds only /usr (and links into it), /work, /tmp and /dev.
2. none of the service's files is there to read: not the engineer's or the courier's key, the witness's TLS key, the ledger,
   the baselines, /etc/passwd, /proc or the code.
3. it has no network: the witness, the gate host, the database and an address outside cannot be reached.
4. it can write only in /work and /tmp, not in the root, /usr or /dev; and the next run starts in an empty /work, with nothing
   kept from the one before.
5. a fork bomb stops at the process limit; asking for 2 GiB of memory fails; more than 1 MiB of output ends the run; a loop is
   stopped at the time allowed; a file of 100 MiB cannot be written.
6. a process the check leaves behind ends with the run, and so does a check that leaves its process group and outlives the
   time allowed, with its children, at its time, not later at the launcher's; no process of any run's identities is left; the
   check sees no process of the machine, and cannot signal the namespace's first process, which is the sandbox's own.
7. what a run uses is limited for the run as a whole: of seven processes that each take 900 MiB, at most one lives, ten-MiB
   files stop before 7 of them, and a design larger than a pipe holds, of which the check reads a little and then no more,
   does not stop the clock: that run ends at its own time, not later at the launcher's.
8. runs keep nothing for one another: the kernel's keyrings cannot be used (refused, ENOSYS), so nothing is kept in them from
   one run to the next; the host name is the sandbox's; /usr/local is hidden; and the check has no site packages, not even by
   adding their folder, and is run without them (python -I -S).
9. the check can make no socket of any family: vsock (which no network namespace closes), packet, netlink, internet and Unix
   sockets, and socket pairs, are refused; nor can it set up native asynchronous I/O (ENOSYS); its capability bounding set is
   empty; it may queue 64 signals and no message-queue bytes; /work is in memory, at most 64 MiB.
10. what the kernel counts for each user is counted against a user of the run's own, not root: a check takes inotify instances
    until refused, and gets exactly 128, the limit for one user, while root, outside, can still make one.
11. two runs have different host identities, and a run whose service is killed ends with it, within two seconds, with every
    process it started, though the check had tried to clear its death signal, and had run itself again from a second thread,
    which starts without one.
12. where the sandbox cannot be made, the check is not run and the outcome says why: a launcher outside new namespaces
    refuses, and so does a service that cannot make the run's control groups, or whose machine has a file table one run could
    fill.
13. a hostile check that probes the service while it works is baselined with its controls as declared, gives a failing design
    its FAIL, and its own words in the signed verdict say it reached nothing; the record verifies.
14. a gate host whose sandbox cannot be made answers UNKNOWN, says the check was not run, and sends the engineer the notice;
    started again as it should be, it runs checks again.
15. a check that keeps to the standard library and its own files runs as before: a design that meets the declared check passes
    and one that does not fails, and the record verifies.

Expected for the gate: 27 of 27 tests, 211 of 211 checks: the 196 of Amendment 11 and the 15 of R27.

**F1 to F35** are as declared before, each expected true. Their checks are now run in a sandbox. F17 needs two failing runs
to end within one second of each other; each run now also makes and throws away a sandbox, about a tenth of a second. In two
development runs, each begun within minutes of a pass of deliberate defects, F17 failed for want of that, for a cause not
found; in the six full runs before them, and in five runs made to look for the cause, it passed (see below). It is still
expected true. The official runs are made with no run of the sandbox's left on the machine.

Expected for the front door: 35 of 35 tests, 189 of 189 checks, as for Amendment 11.

## What was done before this declaration

All of this was on the branch, before this declaration, on 19 November.

- **The first form** (`398f29d`): the check run under `unshare(1)` as nobody, with R27 at 10 checks. Its full runs, 04:16:46
  to 04:26:14: the gate's suite, 27 of 27 tests and 206 of 206 checks; the front door's, 15 of 35. The front door's failures
  were not the code's. A reviewer's probes, run at the same time against copies, had left processes running as nobody, and
  these used up nobody's process limit, so the front door's checks could not start. One front door test left its services
  running after it failed, holding their ports for the tests after it. The four whole-gate tests each exited 0.
- **An independent review** of `f8d2931` to `398f29d`, by a separate agent that ran probes of its own against copies. It
  reported four findings of high weight, five of medium weight and five of low weight. The high ones:
  1. *A check could leave its process group (setsid) and outlive the run*, still running as nobody.
  2. *Every run, and every process of the machine run as nobody, shared one process limit*: one check, or anything else run
     as nobody, could stop every other check from starting.
  3. *Memory was limited only for each process*, so many processes could take the machine's memory.
  4. */work was a folder on the host's disk*, so a check could fill the disk.

  The medium ones: the design was written to the check in one blocking write, so a check that read nothing held the clock,
  and a run cut off was reported as one never made; the launcher did not check that its mount namespace was new; the kernel
  keyring was shared between runs; any process of the machine run as nobody could trace or signal a check; and a check could
  import the machine's site packages, which the old runner (`python -I`) also allowed but should not have. The low ones: a
  check that could not be started counted as a run; the run's folders could be read by anyone; /usr/local and the host's
  name were shown; and a failure to take nobody's identity fell through.

  All were fixed by rewriting the sandbox: the namespaces are made by the launcher itself, as `unshare(1)` here cannot map
  more than one id without `newuidmap`, which is not installed; each run gets two host ids of its own and memory and process
  control groups; /work and /tmp are in memory; the design is written without blocking; the launcher refuses unless every
  namespace is new; /usr/local and the site packages are hidden, and the host is named "sandbox". R27 was rewritten, at 12
  checks, and while it was written some of its own steps were wrong at first and were corrected: it read the parent of the
  first process of a process namespace, which is always 0; it named `/usr/bin/python3`, a link into /etc, which the sandbox
  does not show; and it counted dead processes as left behind.
- **The second form** (`397acca`). Its full runs, 04:37:41 to 04:44:50: the gate's suite, 27 of 27 tests and 208 of 208
  checks; the front door's, 35 of 35 tests and 189 of 189 checks; the four whole-gate tests each exited 0. Its pass of
  deliberate defects was begun and stopped: the test harness, when its own baselining failed, left its services running, and
  the defects after the first all stopped with errors, not failed checks. The harness now stops them, and R27 makes a
  deployment of its own.
- **A second independent review**, of the first review's fixes alone (`398f29d` to `397acca`). It reported two findings of
  high weight, one of medium weight and seven of low weight:
  1. *The check inherited the service's session keyring*, and could read what the service kept there.
  2. *A vsock socket reached the hypervisor*: a network namespace does not close vsock.
  3. *(Medium.) A run outlived a service killed during it*: nothing ended the launcher.

  The low ones: the capability bounding set was never emptied; a process number could be reused between being read and
  killed; the run's host ids could fall in a range other software uses; a check named "-" would be read as standard input;
  `run()` raised on some failures instead of saying the sandbox was unavailable; a mount under /usr stayed writable; and the
  dist packages were not hidden.

  Each was addressed: a session keyring of its own and a system-call filter that refuses the keyring calls and every socket
  family but the local and internet ones; a death signal for the launcher, a clock of its own, and the run's processes made
  the kernel's first choice when it must kill to free memory (the third review found that the death signal did not yet
  work); a sweep of what a killed service leaves; the bounding set emptied; a freezer group around each kill;
  ids from a range above 2,000,400,000, checked against the accounts and processes of the machine; the check run as
  `/work/<name>`, with names checked; every failure returned as SANDBOX_UNAVAILABLE; every mount under /usr made read-only;
  the dist packages hidden; and swap counted where there is swap. R27 grew to 14 checks.
- **The third form** (`927a5b5`). Its full runs were begun and stopped when the third review reported, as the code was to
  change; the gate's suite had passed its first 25 tests.
- **A third independent review**, of the second review's fixes alone (`397acca` to `927a5b5`), asked for findings of medium
  weight or more. It checked the filter's jumps by hand and found them right, and reported two:
  1. *Data queued on Unix sockets is not counted by the memory group*, so one run could hold several gigabytes beyond its
     1 GiB, and push the machine out of memory; the kernel would then kill runs, any run, before the service. Fixed: the
     filter refuses every socket, of every family. A check has no network, so it loses only what it could do with a
     socket to itself.
  2. *The launcher did not die with the service*, as the docstring said: its change to the run's root identity cleared the
     death signal it had set, and R27 passed only because the launcher's own clock, three seconds there, ended the run.
     Fixed: the signal is set again after the change, and the launcher stops if the service has already gone. R27 now gives
     the run 30 seconds, waits until it is running, kills the service, and requires every process of the run to be gone
     within two.

  Of its findings of lower weight, these were fixed: the README said a dead service's run was cleaned up at once; two
  docstrings named the wrong groups and the wrong process; a kill did not wait for the group to be frozen; and a file name
  that cannot be encoded made `run()` raise. R27 has 14 checks.
- **The fourth form** (`2722a6e`). Its full runs, 05:09:18 to 05:16:43: the gate's suite, 27 of 27 tests and 210 of 210
  checks; the front door's, 35 of 35 tests and 189 of 189 checks; the four whole-gate tests each exited 0.
- **Its first pass of deliberate defects**, 05:17:40 to 05:28:51, caught 17 of 26, with the control passing. Six more broke
  the sandbox so far that R27 stopped with an error instead of failing its checks: a step of R27 that could not baseline
  the hostile check passed what it got back to a function that takes only text. Three were missed, and each showed a check
  that could not see its defect on this machine:
  - S5, the check keeping the launcher's groups: the service here holds no supplementary group, so there were none to keep;
  - S14, the check run with the site packages: they are hidden as well, so the check could not tell;
  - S20, the design written to the check in blocking writes of up to 64 KiB: the launcher's own clock still ended the run,
    five seconds late, and R27 asked only that it ended.
- **R27 was then changed, and nothing else** (`0f2b37b`). A failed step's answer is reported as it is; R27 gives its checks
  as true or false; one run is started from a service that holds a group of its own, and the check must hold none; the
  check prints whether it was run without the site packages; and the run with a large design must end within two seconds of
  its time. Its full runs, 05:32:28 to 05:39:46: the gate's suite, 27 of 27 tests and 210 of 210 checks; the front door's,
  35 of 35 tests and 189 of 189 checks; the four whole-gate tests each exited 0.
- **Its second pass of deliberate defects**, 05:40:44 to 05:51:41, caught 25 of 26, with the control passing, and none
  stopped with an error. S20 was still missed. The large design's check read nothing, and the service writes only when the
  pipe has room: its first write, into an empty pipe, never blocks, and no second write is tried. A blocking write is held
  up only once the check has read a little and the pipe has some room again, but not enough.
- **R27 was changed once more, and nothing else** (`426aac9`): the large design's check reads 8 KiB, then no more. Tried by
  hand before the change, with S20 that run ended after 8.1 seconds, at the launcher's clock, and was taken for a check
  that ran and exited (status 137); without it, after 3.1 seconds, as TIMEOUT. Its full runs, 05:53:39 to 06:00:55: the
  gate's suite, 27 of 27 tests and 210 of 210 checks; the front door's, 35 of 35 tests and 189 of 189 checks; the four
  whole-gate tests each exited 0. Its third pass of deliberate defects, 06:01:52 to 06:12:53, caught 26 of 26, with the
  control passing.
- **A fourth independent review**, of the whole of the fourth form as it stood at `426aac9`, made by five reviewers, each
  with one concern (escape, resources, the end of a run, what the outcome says, and whether what the documents and R27's
  checks say is true), and each finding then put to two others asked to refute it. It reported 35 findings, several of
  them made by more than one reviewer; one was refuted by both. The rest come to seven problems in the code and fifteen
  untrue statements. The problems, all reported as of medium weight:
  1. *The run's user namespace was made by root*, so what the kernel counts per user was counted against root's, which
     every run and the machine share: one check could take every inotify instance root may have, or fanotify groups,
     message queues or pending signals, and root's other processes, and other runs, would be refused them while it ran.
     Fixed: the launcher takes the run's first id before it makes the namespaces, and the check may queue 64 signals and
     no message-queue bytes. R27 has a check that takes every inotify instance it may, while root, outside, makes one.
  2. *The check could clear its own death signal* (a call to prctl), and so outlive a service killed during its run.
     Fixed: the filter refuses that call (EPERM). R27's check that the run ends with its service now tries it first.
  3. *One run could fill the machine's file table* (`fs.file-max`, 1,644,500 here), by keeping files open through memory
     mappings: about 630 MB pays for that many. Every other run, and every process not root, the database among them,
     would then be refused new files. Fixed: the sandbox refuses to run unless the file table is at least 2^40, as systemd
     sets it, and the table on this machine was raised so (`sysctl -w fs.file-max=9223372036854775807`). R27 shows a run
     refused when the table seems small.
  4. *Kernel memory a run left in its memory group* (the names it looked up, its page cache) passed to the service's group
     when the run's group was removed, and grew from run to run. Fixed: it is freed first (`memory.force_empty`).
  5. *A service killed while a run's processes were frozen* left them frozen for good, where no sweep could kill them. Fixed:
     the sweep thaws what it kills, and sweeps the freezer first. Weighed low by both who tried to refute it.
  6. *Native asynchronous I/O* has one limit for the whole machine, which one call could take. Fixed: refused (ENOSYS).
     Weighed low by both.
  7. *The service's clock was not looked at while output was waiting*, so a check that printed steadily past its time was
     ended later, by the launcher's clock. Fixed: waiting output holds the clock for at most half a second. Weighed low by
     one of the two.

  The fifteen statements, in the docstrings, the README, R27's names and this declaration's drafts, were untrue or said
  more than the code or the test does: among them that the root holds only the Python installation (it holds all
  of /usr, less what is hidden); that each run has 30 seconds of CPU time (each process does); that a check cannot read its
  bounding set (it can, with prctl, and R27 now reads it); that checks run as before (not one that imports an installed
  package); that runs share nothing (they shared root's counts); and three errors in this record. Each was corrected.
- **The fifth form** (`2b5b52b`). R27 has 15 checks. Its full runs, 08:06:31 to 08:13:50: the gate's suite, 27 of 27 tests
  and 211 of 211 checks; the front door's, 35 of 35 tests and 189 of 189 checks; the four whole-gate tests each exited 0.
  Its pass of deliberate defects, 08:14:47 to 08:30:40, with six defects added for the fourth review's fixes, caught 31 of
  32, with the control passing. S5 was missed, because of a fix: the launcher now gives up the service's groups when it
  takes the run's id, so a first process that did not give them up too held none. S5 was made to take out both, and run
  again with the control, 08:31:00 to 08:31:58: caught, and the control passed.
- **A fifth independent review**, of the fourth review's fixes alone (`426aac9` to `2b5b52b`), by three reviewers, each
  with one concern, and each finding put to two others asked to refute it. It reported eight findings; one was refuted by
  both. The others:
  1. *(High.) The fix for the death signal did not hold.* A thread starts with no death signal, and when a thread other
     than the first runs a program, it takes the process's place, with its own. A check that ran itself again from a second
     thread therefore outlived a service killed during its run, for ten minutes or for good. The reviewer showed the kernel
     does this on this machine, outside a sandbox. Fixed: the check is no longer the first process of its namespace. That
     process is the sandbox's own: it makes the jail, starts the check as its child, reaps what the check leaves, and ends
     when the check ends; its end, or the launcher's, ends every process of the namespace, whatever the check does. The
     filter's rule against changing the death signal was taken out, as nothing now relies on it. R27's check that a run
     ends with its service now has the check clear its death signal and run itself again from a second thread first, and
     waits until it has.
  2. *(Weighed low by both.) The sweep read a group's age from its time of change*, which the kernel need not keep for a
     control group. Fixed: a group's name says when it was made.
  3. *Five untrue statements:* the README and the docstring said a run's processes die with a killed service, which was not
     so of one killed while the run was frozen for its kill; R27's inotify check accepted any number up to 128 and showed
     only that root was not charged; and its service-death check could kill the service before the check had tried to clear
     its death signal. Each was corrected; the inotify check now requires exactly 128.
- **The sixth form** (`cc507ad`). Its full runs, 09:04:07 to 09:11:40: the gate's suite, 27 of 27 tests and 211 of 211
  checks; the front door's, 35 of 35 tests and 189 of 189 checks; the four whole-gate tests each exited 0. Its pass of
  deliberate defects, 09:12:38 to 09:28:27, caught 31 of 32, with the control passing, S34 among them: with the check made the
  first process again, the check of R27 that runs itself again from a second thread was left running, as the fifth review
  said. S10 was missed: with the launcher's end now ending the first process, the service's kill of the launcher's process
  group was enough without the kill of the run's groups, and with neither, the launcher's own clock ends the run five
  seconds late, a delay R27 did not measure. S10 was made to take out every kill the service makes, and R27 to time the
  run that leaves its process group: it must end within four seconds, at a time of two.
- **A sixth review**, of the fifth review's fixes alone (`2b5b52b` to `cc507ad`), was begun as before, with two reviewers
  and two others for each finding, and was cut short: the agents' usage limit for the week was reached. One reviewer, on
  R27 and the statements, finished, and reported six findings; the reviewer on the first process, and every refutation,
  did not run. Its findings were weighed by the author of the code alone:
  1. *The sweep read a group named before this change as made in 2033*, from the run's id in its name, and so never swept
     it. Agreed; fixed: only a name of four parts gives a time; others are judged by their time of change.
  2. *If the service died between the launcher's fork and its child's setting of its death signal*, the child would go on.
     Agreed; fixed: the launcher holds a pipe open, and the child, once its signal is set, stops if it reads the pipe's end.
     A first try at this asked the child for its parent, which a process namespace's first process cannot see; R27 failed,
     with every run refused, and it was corrected before any record was made.
  3. *Three untrue statements*: that the check sees no other process (it sees the first process); that it cannot signal the
     first process (it may send it SIGCONT, which does nothing); and R27's name, which said the check had cleared its death
     signal where it only tried. Each was corrected.
  4. *That a stopped check would be taken for one that ended*: not agreed, as the first process does not ask to be told of
     a child that stops.
- **The seventh form** (`f901679`). Its full runs, 09:31:11 to 09:38:55: the gate's suite, 27 of 27 tests and 211 of 211
  checks; the four whole-gate tests each exited 0; but the front door's, 34 of 35 tests and 187 of 189 checks. F17 failed:
  it needs two failing runs to end in the same second, and in every one of its six tries each run took about a second,
  where in every earlier run the two had ended in the same second at the first try. Run again by itself, and then the
  whole suite again, F17 passed at its first try, and the slowness was not seen again. Its cause was not found. The
  likeliest is the sweep, which since the fifth form waited up to a second for each stale group it could not yet remove;
  groups left by the pass of deliberate defects before were stale by then. Its pass of deliberate defects, 09:39:53 to
  09:55:43, caught 32 of 32, with the control passing.
- **The eighth form** (`9aed125`), which is the code this declaration carries: the sweep tries each stale group once, and
  a later run tries again, so that no run waits for another's leftovers. Its full runs, 10:03:55 to 10:11:38: the gate's
  suite, 27 of 27 tests and 211 of 211 checks; the four whole-gate tests each exited 0; the front door's, 34 of 35 tests
  and 187 of 189 checks, F17 failing again in the same way. So the sweep was not the cause, or not the only one. F17 was
  then run, and passed at its first try, three more times on this code: after R27 by itself; with F1 to F16 before it;
  and in the front door's whole suite after the gate's whole suite, as in the official runs. Both runs in which
  it failed began within minutes of a pass of deliberate defects; none in which it passed did. That is all that is known
  of the cause. Its pass of deliberate defects, 10:12:36 to 10:28:31, caught 32 of 32, with the control passing, and left
  no process running.
- **Then two of R27's check names were corrected, and nothing else**: the first said the root holds only the Python
  installation, where it holds /usr; the last said checks that keep to their own work run as before, where only a check
  that keeps to the standard library and its own files does. What each check tests is unchanged, and the runs above were
  not made again.
- The defects are kept in `verify/dev_amend12_mutants.json`, which names, for each, the checks that caught it. They cover:
  - the namespaces, the root and the identity (S1 to S5, S16, S17, S21, S28);
  - the limits (S6 to S9, S20, S27, S31, S33);
  - the end of a run, and the service's death (S10, S26, S34);
  - saying whether the sandbox was made, and the check run (S11 to S13);
  - what the check is shown and keeps (S14, S18, S19, S25, S32);
  - the system-call filter (S22 to S24, S30).

  S15 and S29 are not among them. S15, /work kept from one run to the next, was taken off the list during development,
  before any pass recorded here. S29 tested the rule against changing the death signal, which the sixth form took out.
- **What no reviewer has read.** The first process, as the sixth form made it, was read by no reviewer to the end: the
  reviewer meant for it did not run. The fixes of the sixth review, which make the seventh form, and the eighth form's
  change, were read only by their author. Every earlier form's fixes were read by the review after it.

## What stays open

- **The sandbox is the kernel's, not a machine's.** The check runs on the same kernel as the service. The filter narrows the
  calls it can make; every other call is still open to it, as an unprivileged user in namespaces of its own, and a flaw in the
  kernel there would be a way out. A virtual machine, or a second machine, would close more; neither is used.
- **The memory group counts most of what a run uses, not all.** Memory the kernel allocates for a run without charging it to
  the run's group is not limited by it. Sockets, the largest such use found, are refused; others may remain. What is charged
  to the group is freed before the group is removed, as far as the kernel can free it; what it cannot free passes to the
  service's group.
- **Some of the kernel's limits are the machine's, not the user's.** Those found are dealt with: the file table must be at
  least 2^40 (a run can keep about as many files open, through memory mappings, as its 1 GiB pays for), and native
  asynchronous I/O is refused. Others may remain.
- **The service runs as root.** It needs root to give each run its own ids and control groups. A flaw in the service is then
  a flaw in root. In the demonstration the service, the witness, the courier and the mailbox share that one machine and that
  account; the database runs on the same machine under its own account.
- **What a check may use is limited, not reserved.** Each run has 1 GiB of memory and 64 processes; each process has 30
  seconds of CPU time and 64 open file descriptors; /work and /tmp hold 64 MiB each. One service makes four runs at once, and
  several services on one machine each make four. Nothing limits a run's share of the CPU while it runs, its disk reads, or
  the machine's other work. Runs that wait too long for their turn are not made (UNKNOWN).
- **The Python installation is shown as it is.** A check sees /usr, read-only, without the site and dist packages: the
  standard library and the programs installed there. It learns which versions are installed.
- **x86-64 only, cgroup v1 only.** The filter is written for x86-64, and the control groups for cgroup v1 (memory, pids and
  freezer). On another architecture, or a machine with only cgroup v2, every run is SANDBOX_UNAVAILABLE: the service then
  gives UNKNOWN for every run, which is safe but stops the work. So does a machine whose file table is below 2^40.
- **A killed service leaves the run's groups and folder for ten minutes.** The run's processes die with the service, but
  what they leave is removed only by a later run of a service in the same control groups, once ten minutes old.
- **The end of a run rests on two processes of the sandbox's own.** The launcher dies with the service, and the namespace's
  first process with the launcher; the kernel then ends the rest. Nothing the check does to its own death signal matters.
  If the service dies while a run is frozen for its kill, the run's processes stay frozen until a later sweep.
- **The sandbox keeps the check from the service; it does not make the check right.** A verdict still says only that the
  declared check returned numbers that do or do not meet the baselined limits.
- **The assistant is not sandboxed.** This amendment confines the customer's check. The assistant that sends designs is still
  kept from the service only by the front door and the separation the demonstration does not have (G3).

## What is not tested

- A kernel flaw. R27 tries the ways out named in its checks; it does not try known kernel exploits.
- Some of the filter's refusals: io_uring, bpf, perf_event_open and userfaultfd are refused, and R27 calls none of them. Nor
  does it make a call of another architecture, or an x32 call, which end the process.
- The session keyring of its own: the filter refuses the keyring calls first, and no check shows the join alone.
- Some limits: R27 does not open more than 64 files, use 30 seconds of CPU time, make more than 1024 files, fill /tmp, or
  make a core dump.
- The read-only remount of mounts under /usr: this machine has none. R27 shows /usr read-only, not a mount within it.
- The freezer: R27 shows that nothing of a run is left, not that a process number was never reused while it was killed.
- The sweep of groups and folders ten minutes old, left by a service killed during a run, and its thawing of a group left
  frozen.
- The freeing of a run's memory group before it is removed: R27 does not measure what the service's group holds after it.
- The half-second for which waiting output may hold the service's clock: no R27 check sends output past its time.
- The launcher's own clock: R27 kills the service and sees the run end within two seconds, by the launcher's death; the
  clock, at 35 seconds, is not reached. Nor does R27 kill the service in the moment before the launcher's death signal is set.
- Other machine-wide limits a run might reach, and memory the kernel does not charge to a run's group. R27 shows one
  per-user count, inotify instances, charged to the run's own id; it does not look for others.
- Four runs at once, and a fifth that waits longer than its time for its turn.
- The service dying in the moment between the launcher's fork and its child's setting of its death signal, which the child
  then sees by the end of a pipe.
- The sweep of a group named before groups carried their time.
- A machine without root, without cgroup v1, with swap (memsw), or another architecture than x86-64. R27 makes the control
  groups unreachable and the file table seem small; it does not take root away.
- File names the sandbox refuses (a slash, a leading dash, more than 200 bytes, one that cannot be encoded): a card is not
  made to give one.
- A check that imports an installed package or uses /proc, /dev/shm or multiprocessing: none in the repository does.
- What the courier, the mailbox and the witness do: unchanged and not read again by R27.

## Commands and results

The official runs are these, each once, from the tree at the commit that carries this declaration, as root, with the services
on 127.0.0.1 and PostgreSQL 16, on a machine whose file table has been raised as the sandbox requires
(`sysctl -w fs.file-max=9223372036854775807`, the value systemd sets):

    cd tests && python3 -B verify_tests.py
    cd tests && python3 -B verify_front_tests.py

Each output file is copied to `verify/results_verify_tests_amended12_2026-11-19.json` and
`verify/results_front_tests_amended12_2026-11-19.json`. The outputs folder is not committed.

Expected: for the gate, 27 of 27 tests and 211 of 211 checks; for the front door, 35 of 35 tests and 189 of 189 checks.
A check that comes out other than expected is reported as it came out, in the amendment that follows the runs, and is not run
again under this declaration.
