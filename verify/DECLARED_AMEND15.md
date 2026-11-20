# Amendment 15: declaration before the official test runs

20 November 2026. Private working material.

This file is committed before the official runs of `tests/verify_tests.py` and `tests/verify_front_tests.py` on the branch
`verification-amendment-15`. It fixes the changed code, states what each test is expected to show, and records what was done
in development. Each official run is made once after this commit and its first result is kept, pass or fail. A later
correction would be a separate, dated amendment. Times are UTC.

This is internal work by the author of the code, under the owner's direction. It is not an independent validation.

## Why declared files are changed

The sandbox of Amendment 12 refuses to run a check on a machine whose file table (`fs.file-max`) is below 2^40. That figure
was chosen to be beyond anything a run's memory could fill; it was never measured, and to meet it the machine's table
was raised, at each start of the machine, to the largest number the kernel takes
(`sysctl -w fs.file-max=9223372036854775807`). On 19 November the owner asked that so high a limit not be applied for good
unless it is shown to be needed, and that a lower, justified limit or an explicit refusal be preferred; and asked what
happens to the sandbox when the machine is started again, and on a machine with cgroup v2.

What was found:

- **A limit above the machine's own is needed; 2^40 is not.** A run can keep a file open with no descriptor, by mapping it
  into memory and closing it. Its limit on descriptors (64 for each process) does not count those. One run, made to do
  only this, kept about 2.6 million files open at once, until its memory ran out. This machine starts with a table of
  1,644,500. So on the machine as it starts, one run could fill the table, and every other process on the machine
  would be refused files until the run ended.
- **What a run can keep open has a bound, and it can be worked out.** For each of its processes: a file for each
  descriptor (64); a file for each mapping; and its own program. A process may have `vm.max_map_count` mappings and one
  more, and never more than it has pages of memory to put them in, which its limit on memory sets at 262,144. A run may
  have 64 processes. And the run may make 4,096 segments of shared memory, each a file with neither descriptor nor
  mapping. On this machine, where a process may have 65,530 mappings, that is 64 x (65,531 + 64 + 1) + 4,096: 4,202,240
  files for one run.
- **The limit on mappings is not the same everywhere.** 65,530 is the kernel's default. Ubuntu 24.04, started in the usual
  way, sets 1,048,576 (`/etc/sysctl.d/10-map-count.conf`); this machine, a container, does not apply that file. There
  the pages are the smaller number, and one run can keep open 64 x (262,144 + 65) + 4,096: 16,785,472.
- **The file table is the machine's, so the runs must be counted for the machine.** The service made at most four runs at
  once in each of its processes. Two processes that run checks, the gate host and the engineer's console when it
  baselines, could make eight between them.
- **The setting is lost when the machine is started again.** The machine was started again several times during this
  work, not by request. Each time the table was back at 1,644,500 and every run was UNKNOWN, "the check was not run",
  until it was raised: the sandbox failed closed. It said that the table was below 2^40, and not what to do about it.
- **On a machine with cgroup v2 only the sandbox does not run,** and said so only as a failure to make its control
  groups. This machine has cgroup v1; no machine with cgroup v2 only was at hand.

## What is changed

**The floor is worked out, not fixed.** `verify/sandbox.py` now requires a file table of at least twice what four runs
can keep open, each counted as above (`files_one_run_can_hold`, `file_table_floor`). On this machine that is 33,617,920,
where it was 1,099,511,627,776. On Ubuntu 24.04 started in the usual way it would be 134,283,776. The limit on mappings
is read from the machine before every run, and a run given other limits is held to a floor worked out from them.

**Four runs at once is now the machine's count.** Before a run the service takes one of four locks, on files of root's in
`/run/verify-sandbox`, and holds it until the run is over; the kernel lets it go if the service dies. Every process that
runs checks, and sees that folder, takes its place there, so a fifth run waits, and is not made if no place comes free
in the time the run is allowed; it is then UNKNOWN, "too many checks are running at once on this machine". The folder
must be root's alone, and each place a file of root's. The limit of four that each process kept for itself is taken
out: the places do its work, and a run now waits once, not twice.

**What the machine must give is one list, looked at before every run, and said.** `prerequisites()` gives six things, each
met or not, with the words for what was found: the service runs as root; the machine is x86-64; cgroup v1 memory, pids
and freezer control groups are there, and where the sandbox makes its own; the machine's limit on user namespaces allows some; the
folder of places is root's alone, or can be made; the file table is at or above the floor. What cannot be read, or read as a number above nothing, is not met; and if the
looking itself fails, that is one thing not met, and nothing is raised. Where one is not met the check is not run, and the run's detail gives those words: for the file
table, the table, the floor and how the floor is come by; for a machine with cgroup v2 only, that it is that. Before
this, root, x86-64 and the file table were looked at before every run, the control groups were found missing only when
making them failed, and user namespaces only when the launcher failed.

**An operator can ask.** `python3 verify/sandbox.py --prerequisites` prints the six, each "met" or "NOT MET", and ends with
status 0 only if all are met. It changes nothing on the machine and makes no run, and says so: that the six are met
for the process that asked does not show that a run can be made.

**Nothing raises the table.** The service does not, and neither does the command. To keep the setting when the machine
is started again is the operator's step, a line for `fs.file-max` in a file under `/etc/sysctl.d`, with the number the
command gives for that machine; it has not been made on this machine, whose table is raised by hand at each start. A machine started again without it runs no check, and
says why.

**The file the table is read from can be named by the service's environment** (`VERIFY_SANDBOX_FILE_MAX`), so that a test can
show a whole service refusing on a small table without making the machine's table small. The table is then taken as
the smaller of the kernel's and the file's, so the file can lower it and cannot raise it; the words of a refusal name
the file.

`verify/README.md` says the same. Nothing else is changed: not the gateway, the front door, the gate's tool, the record or
its checker, nor anything else of the sandbox: its namespaces, limits, filter and control groups are as Amendment 12
declared them.

## The changed files

Base: `verification-amendment-14` at `979683a`. Three files change, none of them new.
The hashes are of the files as they stand at this commit.

| file | sha256 at 979683a | sha256 now |
| --- | --- | --- |
| `verify/sandbox.py` | `2c0d4a8b8606a109b640ae923ea45c540599d858d8b7135183023558f63fa7a7` | `dfc745434ab45e2ab3810e98a4a9eeff5be6d480b6e0af158acff57183d05f6b` |
| `verify/README.md` | `6d192a0b05463367c4d69c88c55eb668c4bb207cca97746501a9b69daef37cca` | `0b057a14b1cad1e6aac573df355f9c0e5072ad267780dab00e289923b828f32d` |
| `tests/verify_tests.py` | `44ad84d7cc906e9621132dd655d73aa7cc5000023302252889670e8e1fd43f99` | `5cdb61f8bf9b58ce00fbd9c7305bfd1c5c2c652e42997eeae8750d7ef46bfd1f` |

One file is new as a development record: `verify/dev_amend15_mutants.json`, the pass of deliberate defects.
Every other file in the repository at `979683a` is unchanged.

## What each test is expected to show

**R1 to R28** are as declared before: the same functions, each expected true. R27, the sandbox's own test, is not changed.
Two things in it touch this change, and both are now refused by the list where they were refused later: a service whose
control groups are not where it is told to make them, and a machine whose file table is the 1,644,500 this one starts
with, which is below the new floor as it was below the old.

**R29 is new** (9 checks). It works the count and the floor out by itself from the machine's limits. It makes runs
with the sandbox pointed at files in place of the machine's own: a table one below the floor, and at it; half the
mappings; 1,048,576 mappings; a run allowed twice the processes, and one allowed half; a limit on mappings, a table and a
limit on user namespaces that cannot be read; a file named in place of the kernel's that says more than the kernel
does; a machine with cgroup v2 only; one with no freezer group; one whose freezer group is elsewhere; one whose control
groups cannot be read at all; one that allows no user namespaces; a folder of places that others can write to, and one
that cannot be made. It gives the operator's command on the machine as it is, and with the table the machine starts
with. It starts a whole service with that table, sends it a design, and starts it again without. It makes two slow runs
itself and two from another process, and asks for a fifth. It runs a check that asks for namespaces of its own. Last, it
makes one run that keeps open every file it can, and counts the machine's open files from outside while it does.

1. as this machine is set up for the runs, every one of the six is met, and the command an operator gives says so, says that
   it made no run, and ends with status 0.
2. the file table must hold twice what four runs can keep open, worked out from the machine's own limit on mappings: one below
   that the check is not run, and the words give both numbers; at it, the check is run; with half the mappings a smaller table
   is enough; a run allowed twice the processes is not made on this table, and one allowed half is held to its own, smaller
   floor.
3. where a process may have more mappings than it has pages of memory to put them in (1,048,576, as Ubuntu 24.04 sets it), the
   floor counts the pages, and says the number; a file named in place of the kernel's can make the table smaller and cannot
   make it larger.
4. where the machine's limit on mappings, or its file table, cannot be read as a number above nothing, it cannot be shown that
   the table is large enough, and the check is not run.
5. a machine that gives cgroup v2 only is refused in those words; one without a freezer control group is told which is
   missing, as is one whose freezer group is not where the sandbox makes its own; one that allows no user namespaces is told
   so, and so is one where that cannot be read; one whose control groups cannot be read at all is refused and nothing raises;
   and on none of them is the check run.
6. with the file table this machine starts with (1,644,500), the operator's command says the file table is NOT MET and ends
   with status 1; a service there answers UNKNOWN, says the check was not run and why, and sends the engineer the notice;
   started again on the machine as set up, it runs checks.
7. the floor counts four runs at once on the machine, and no more are made, whichever process asks: two runs of five seconds
   by this process and two by another are made together, a fifth asked for meanwhile is not made and says why, and one asked
   for after them is made; where the places are a folder others can write to, or cannot be made, no run is made.
8. a check that asks, by unshare, for a user namespace of its own, an IPC namespace, or both, is refused each (EPERM): the
   count of what one run can keep open has one IPC namespace in it.
9. a measurement, not a proof of the floor: one run that keeps open every file it can keeps more than a million, which is more
   than half the table this machine starts with, and fewer than the count worked out for one run; and after it has ended the
   machine has within 2,000 of the files open that it had before.

Expected for the gate: 29 of 29 tests, 226 of 226 checks: the 217 of Amendment 14 and the 9 of R29.

R29 needs the machine's table to be at the floor or above and below 67,235,840, twice the floor: two of its cases are
runs that the machine's own table must refuse. The commands below set it at the floor.

**F1 to F36** are as declared before, each expected true. Expected for the front door: 36 of 36 tests, 193 of 193 checks.

## What was done before this declaration

All of this was on the branch, before this declaration, on 20 November. Three forms of the code were made. Two reviews
were made by separate agents that read the code, ran no test and made no run; each was told to challenge the change.

- **The measurement first.** One run was made to open a file, map it and close it, over and over, in every process it
  could start. The machine's count of open files rose by about 2.6 million while it ran and fell back when it ended.
  The machine's own table is 1,644,500.
- **The first form** (`6a6ad5d`, and R29 widened in `e89cde5`): a floor of twice four
  runs' processes times the mappings and descriptors of each, 33,584,128; five things looked at before every run; the
  operator's command; R29, with six checks, then seven. Its full runs, with R29 at six checks: the gate's suite, 29 of 29
  tests and 223 of 223 checks; the front door's, 36 of 36 and 193 of 193. Of the four whole-gate tests three exited 0 and
  **one failed**: `w4_service_crash`, in one of its 18 cases, where a retry after the service was killed timed out. That
  test runs none of the code changed here. Run five times more at once, it passed five times; it passed again with the
  third form. One failure in seven runs, the cause not found; the machine was loaded by a reviewer starting at the time.
- **Its pass of deliberate defects**, 02:23:25 to 02:30:52: 21 defects and a control. 20 were caught by a check of R29 and
  the control passed. With the other, a table exactly at the floor refused, R29 stopped with an error and failed no
  check: the machine's table being at the floor, nothing ran, and R29 could not make its baseline.
- **The first review** made sixteen findings, none of high weight. Three of medium weight:
  1. *The four runs were counted for each process, and the file table is the machine's.* The gate host and the engineer's
     console, baselining, each make four.
  2. *The limit on mappings is not 65,530 on the system the amendments name.* Ubuntu 24.04 sets 1,048,576 when started in
     the usual way, which this machine is not. The floor there would have been 536,903,680, and an operator who set the
     33.6 million the readme gave would have had every run refused.
  3. *R29 worked the floor out as the code does*, so it could not see a term left out; and the name of its measurement
     said more than the measurement shows.

  And of lower weight: shared-memory segments, a process's own program, and one mapping more than the limit are files
  the count left out (the first shown by trial: a thousand segments, a thousand files); the count rests on a check being
  unable to make namespaces of its own, which nothing tested; a limit on user namespaces that could not be read counted
  as met; the looking could raise where it should refuse; a limit on mappings below nothing gave a floor below nothing; the
  file named by the environment could raise the table as well as lower it; the operator's command said the sandbox "can
  run checks" having made none; R27's two refusals now come from the list, so the code that makes the control groups,
  failing, is reached by no test; and two things about the control groups that are not new, which stay open.
- **The second form** (`f9cd1e6`): the runs counted for the machine, by locks, beside the count each process kept; the
  count of files with the pages a process has, its program, the one mapping more and the shared-memory segments in it;
  what cannot be read not met; the looking never raising; the named file only lowering; the command's last line. R29 at
  nine checks. Run by itself, R29 passed, and R27. Its pass of deliberate defects was stopped part-way, 16 of them tried
  and 15 caught with the same one stopping R29, when the second review came in; its full runs were not made.
- **The second review**, of what the second form changed, made seventeen findings and notes, none of high weight. It
  confirmed by reading that a check's limit on memory is a hard one it cannot raise, and from its knowledge of the kernel
  that every mapping counts against it; it named no other way to keep a file open. Of medium weight:
  1. *A place is let go when the service dies, and the run's files may not be* (open, below).
  2. *Services that do not share /run are not counted together* (open, below).
  3. *The floor moved*, from 33,584,128 to 33,617,920: a machine set to the first is refused.
  4. *R29's count of four used the machine's own places*, so another user of them could make it pass or fail.

  And of lower weight: the folder of places was not looked at with the rest; a run could wait twice, once for each
  count, and the first count was no longer tested; the wait used the wall clock; any failure to lock was taken as "taken";
  the folder was looked at and then opened by name; R29's namespaces case did not look at the error.
- **The third form** (`c62a3dc`), the code this declaration carries: one count, the machine's, the other taken out; the
  folder of places opened once and looked at through what was opened, each place required to be a file of root's, and
  only "taken" read as taken; a sixth thing in the list, the folder; the wait on a clock that does not jump; R29 with
  places of its own for the count, two cases of a folder that will not do, and the error looked at. Its pass of
  deliberate defects, 02:45:34 to 02:57:49: 34 defects and a control. 33 were caught by a check of R29 and the control
  passed, R27 with it; the 34th is the same one, which stops R29 with an error. Its full runs, 02:57:49 to 03:06:27: the
  gate's suite, 29 of 29 tests and 226 of 226 checks; the front door's, 36 of 36 tests and 193 of 193 checks, F17 saying
  COLLISION_HANDLED; the four whole-gate tests each exited 0.
- The defects are kept in `verify/dev_amend15_mutants.json`, which names, for each, the checks that caught it.
- **What no reviewer has read.** The third form's changes were read only by their author. Each of the two reviews found
  things of medium weight in the form before it; that a third would find none is not claimed.
- **What was not done to this machine.** Its table was set by hand, for this start, to 33,584,128 and then to 33,617,920.
  Nothing was written under `/etc`. The folder `/run/verify-sandbox` was made by the first run of the second form.

## What stays open

- **Runs are counted together only by services that share one /run.** Services in containers of their own on one kernel
  share the kernel's file table and not the folder of places, and each would make four. An older copy of the service,
  which takes no place, is not counted either.
- **A place is let go when its service dies; the run's files may not be.** If the service is killed while a run is frozen
  for its kill, the run's processes stay, with whatever they hold, until a later run sweeps them, ten minutes on or more
  (Amendment 12 left this open). The service's place is free at once, so a fifth run can begin beside them. The margin
  of two is what covers this, and repeated kills would use it up. Found by the second review; not repaired here.
- **The margin of two is a judgement.** The floor is twice what four runs could keep open, so that the rest of the machine
  has as much again. Nothing measures what the rest of a busy machine needs; this one had a few thousand files open.
- **The count of what one run can hold is an argument, not a measurement.** One run was measured keeping 2.6 million
  files open, and its memory stopped it; the count allows 4.2 million. Two reviewers looked for a way to keep a file open
  that the count leaves out and named none beyond those now in it (the shared-memory segments, the program, the one
  mapping more). What they said of the kernel is from their knowledge of it and was not checked against the source of
  this kernel. That a process has no more mappings than pages rests on the kernel counting every mapping against its
  address space; that the run has one IPC namespace rests on the chroot, in which the kernel lets no user namespace be
  made. If the sandbox were entered another way, that would have to be shown again.
- **Where many mappings are allowed the floor is high.** On Ubuntu 24.04 started in the usual way it is 134,283,776, four
  times this machine's. It could be lowered by allowing a run fewer processes or less memory, which would be a change to
  the sandbox's limits.
- **A table at the floor removes a guard the kernel sets for itself.** The kernel's own table, about a tenth of memory,
  keeps open files from using all of it. A run cannot reach the new table, its memory being limited; other processes of
  the machine, outside any such limit, could.
- **The setting is still made by hand, and lost at each start of the machine.** This amendment makes the loss plain and
  the refusal exact. It does not make the setting. A machine set to the number an earlier form of this work gave
  (33,584,128), or to a round "33.6 million", is below the floor and runs nothing: the number to set is the one the
  command gives.
- **A service that cannot run checks still starts, and still takes designs.** It answers each UNKNOWN and sends the
  engineer the notice. It does not refuse to start. Each such design is used up: it is on the record as UNKNOWN and is
  not run again.
- **The operator's command speaks for the process that asks.** Root, and the control groups, are those of the command, not
  of a service started another way. It does not try a user namespace, so a machine that forbids them to unprivileged
  users by another setting (as Ubuntu's AppArmor does) is said to meet that one, and every run then fails, closed, in
  the launcher. It makes no run, and says so.
- **Waiting for a place has no queue.** A run that has waited long has no claim over one that has just come, and under
  load can wait out its time and be answered UNKNOWN.
- **cgroup v2 is not supported.** On a machine with cgroup v2 only the sandbox runs nothing and says so. A machine with
  its controllers on cgroup v2 and a named cgroup v1 hierarchy left over is refused too, in the words for missing groups.
  Making the sandbox use cgroup v2 would be a change to it, and a separate amendment.
- **Two things about the control groups, not new and not repaired.** If the service is told to make its groups under
  a folder that is not the kernel's (`VERIFY_SANDBOX_CGROUP_ROOT`), the list sees only that the folders are there, and a
  run would be made with no memory or process group, only its per-process limits. And the code that makes the groups
  reads `/proc/self/cgroup` in its own way, and a line it cannot read would raise there, not refuse; the gate's tool takes
  that as UNKNOWN. Both need whoever starts the service to set its environment, or a kernel that writes such a line.
- **What is read is read when the run begins.** A setting changed during a run is not seen until the next.
- **Everything Amendment 12 left open about the sandbox stays open**: it is the kernel's, not a machine's; the service
  runs as root; other limits of the machine's are shared.

## What is not tested

- **A machine with cgroup v2 only.** R29 gives the sandbox a file that reads as such a machine's `/proc/self/cgroup`. No run
  was made on a real one.
- **A start of the machine made on purpose.** The machine was started again several times by its host, and each time the
  sandbox refused until the table was raised; that was seen, and is not a test. R29 shows a service with the table a start
  leaves, by naming a file; it does not start the machine again.
- **The operator's line in `/etc/sysctl.d`.** Not made, so not shown to keep the setting.
- **A limit on mappings of 1,048,576 on the machine itself.** R29 names a file that says so and reads the refusal; no run
  was made on a machine set that way, and no run was measured there.
- **That the count is a bound.** R29 works the count out by itself, in the same way the code does, so it shows that the
  code computes what was meant, not that what was meant is enough. The one run measured stopped at its memory, well below
  the count.
- **The service's place let go when it is killed,** and a run left frozen beside a fifth.
- **Services that do not share /run.**
- **The places under attack**: a place that is a link, a pipe or another's file; the folder changed between being looked
  at and being used. The code refuses these by reading; R29 gives it a folder others can write to, and one that cannot
  be made.
- **The real folder of places, in R29's own count.** The count of four is shown with places in a folder of the test's own,
  so that nothing else on the machine disturbs it; the services R29 starts use the real one.
- **A check asking for namespaces by clone or clone3, or joining one by setns.** R29 asks by unshare.
- **The name given to the service's environment, raising the table.** R29 shows that a named file cannot raise the table
  by changing the module's own names; the environment is used only to lower it.
- **The code that makes the control groups, failing.** R27's case of a service that cannot make them is now refused by
  the list, before that code is reached, so no test reaches it.
- **The service not running as root, and a machine that is not x86-64**, by this test. R27 covers the launcher outside
  new namespaces; no other architecture was at hand.
- **Four runs each keeping open every file they can, at once.** R29 measures one.
- **Kernels other than this one** (6.18).

## Commands and results

The official runs are these, each once, from the tree at the commit that carries this declaration, as root, with the services
on 127.0.0.1 and PostgreSQL 16, with the interpreter of the project's virtual environment, on a machine whose file table has
been set for this start of the machine to the floor and no higher (`sysctl -w fs.file-max=33617920`), whose
`sandbox.py --prerequisites` ends with status 0, and with no run of the sandbox's left on it:

    cd tests && <venv>/bin/python -B verify_tests.py
    cd tests && <venv>/bin/python -B verify_front_tests.py

Before each command the output file it will write is removed. Each output file is copied to
`verify/results_verify_tests_amended15_2026-11-20.json` and `verify/results_front_tests_amended15_2026-11-20.json`. The outputs
folder is not committed.

Expected: for the gate, 29 of 29 tests and 226 of 226 checks; for the front door, 36 of 36 tests and 193 of 193
checks. A check that comes out other than expected is reported as it came out, in the amendment that follows the runs,
and is not run again under this declaration.
