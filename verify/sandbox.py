#!/usr/bin/env python3
"""The disposable sandbox a declared check runs in (Amendment 12, release gate G2).

    run(files, script, stdin, ...) -> Outcome      used by baseline.evaluate() for every run of a check

A check is code the customer supplies, so it is run as if it were hostile.  Each run gets a sandbox of its own, made for it
and thrown away after it:

  - identities of its own: a new user namespace whose root and whose unprivileged user are two host user ids chosen for this
    run alone, so that no other run, and no process of the machine, shares them: not their process count, not their kernel
    keyring, not the right to trace or signal them.  The namespace is made by the first of these ids, not by root, so what
    the kernel counts for each user (inotify and fanotify use, message queues, pending signals) is counted against the run's
    own id, not against root's, which the machine's other processes share;
  - new mount, process, network, IPC and host-name namespaces: the check sees no process of the machine (only the sandbox's
    own first process and its own), has no network at all (not
    even loopback), and its mounts are its own;
  - a root of its own: an empty, read-only file system holding the Python installation (/usr, read-only throughout, with
    /usr/local, /usr/src and the site and dist packages hidden), a work folder at /work and a /tmp, both in memory and limited in size and number of files, and
    /dev/null, /dev/zero and /dev/urandom.  /work holds copies of the check and its data files, the bytes that were hashed.
    Nothing else of the machine is there: not the service's home, its keys, its database credentials, its journals or its
    inbox, not /etc, not /proc.  The host name is "sandbox";
  - the check runs as the unprivileged user of that namespace, with no other group and no capabilities (its bounding set
    emptied), no way to gain any (no new privileges), and a session keyring of its own, not the service's; it cannot
    trace, stop or kill the namespace's first process, which runs as the namespace's root;
  - a small system-call filter (seccomp, x86-64 only): no sockets of any family, so no vsock, which a network namespace does
    not close, and no Unix sockets, whose queued data the memory group does not count; the keyring, io_uring, native
    asynchronous I/O (whose limit is the machine's), bpf, perf and userfaultfd calls are refused (ENOSYS); any other
    architecture's calls, or the x32 calls, end the process;
  - a memory, a process and a freezer control group of its own (cgroup v1): its processes, together, use at most 1 GiB of memory (its
    files in /work and /tmp included) and number at most 64; and limits on each process's CPU time, memory, file size and
    open file descriptors, pending signals and message-queue bytes, no core dumps, the size of what it prints, and the
    wall-clock time of the run.  When the run ends, every
    process in its control groups is frozen and killed, and the groups and the folder are removed.  The first process of
    the run's process namespace is the sandbox's own, not the check: it makes the jail, starts the check as its child,
    reaps what the check leaves, and ends when the check ends, and every process of the namespace ends with it.  If the
    service dies during a run, the launcher is killed with it, and that first process with the launcher, so the run ends
    whatever the check has done to its own threads or death signal; unless the service dies while the run is frozen for
    its kill: then its processes stay frozen until the sweep below.  The launcher also keeps its own clock.  The groups and folders a killed service leaves are removed by a later
    run of the same service, once ten minutes old, thawed first if the service died while they were frozen.  Before a run's memory group is removed, what
    the kernel keeps charged to it (its page cache, its file names looked up) is freed, not handed on to the service's group.

The check is run by the Python standard library alone (python -I -S): no site packages, no environment from the service.

If the sandbox cannot be made, the check is not run, and the run says why: the outcome is SANDBOX_UNAVAILABLE.  Nothing ever
falls back to running a check outside it.  The sandbox needs the service to run as root (to choose the run's identities and
make its control groups); otherwise every run is SANDBOX_UNAVAILABLE.  What the machine must give is looked at before
every run (prerequisites(), and for an operator `sandbox.py --prerequisites`): root; x86-64; cgroup v1 memory, pids and
freezer control groups (a machine with cgroup v2 only is refused in those words); user namespaces; and a file table
(fs.file-max) of at least twice what the four runs the machine makes at once can keep open.  A run can keep files open
through memory mappings, beyond its limit on descriptors: one run was measured keeping 2.6 million open.  The floor is
worked out from the machine's own limit on mappings and the run's limits: about 33.6 million where a process may have
65,530 mappings, the kernel's own default, and about 134 million where it may have 1,048,576, as Ubuntu 24.04 sets it.
The four are counted for the machine, by locks every service takes (in /run/verify-sandbox), not for each service;
services that do not share one /run are not counted together.  A
machine started again with a smaller table runs no check until the table is raised.  Nothing is mounted, and nothing run, unless
the process doing it is the first of new user, mount, process, network, IPC and host-name namespaces, none of them the
service's, with no network but a loopback, and with the run's own two ids mapped.  It says that the sandbox is ready on a
pipe the check does not inherit, and, if the check cannot be started, says that too, so a check cannot pretend that it was
or was not run.

What it does not do.  Its filter narrows the kernel's interface; it does not close it: the check can still make every
other call as an unprivileged user in its own namespaces, and a kernel flaw there would be a way out.  It is no virtual
machine.  It has no limit on the check's
share of the CPU beyond its time limit, nor on its disk reads; many runs at once share the machine.  The Python installation
under /usr is visible as it is.  Programs that need /proc or /dev/shm (multiprocessing) do not work.  In the demonstration
the service itself runs as root on the same machine.

    sandbox.py --prerequisites
        for an operator: what the machine must give, each said to be met or not; exit status 0 only if all are

    sandbox.py --inside JAIL WORK FD_READY FD_SYNC_OUT FD_SYNC_IN NS_INODES LIMITS ALLOWED_SECONDS OWNER_UID [--no-unshare] -- PROGRAM ARGS...
        the launcher, run by run(); --no-unshare is for a test, to show that a launcher outside new namespaces refuses

Standard library only.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import fcntl
import glob
import os
import platform
import pwd
import stat
import threading
import pathlib
import random
import resource
import select
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass

NOBODY = 65534
LIMITS = {'cpu_seconds': 30, 'memory_bytes': 1 << 30, 'processes': 64, 'file_bytes': 64 << 20, 'open_files': 64, 'tmp_bytes': 64 << 20, 'tmp_files': 1024}
MAX_OUTPUT = 1 << 20                                                    # bytes of standard output, and of standard error, kept
READY, EXEC_FAILED = b'SANDBOX-READY\n', b'SANDBOX-EXEC-FAILED\n'
UID_BASE, UID_SPAN = 2_000_400_000, 1 << 25                           # host ids for runs, above the usual directory-service and container ranges: two each, at random
GRACE = 5.0                                                             # seconds the launcher allows past the run's own time before it ends the run itself
STALE = 600.0                                                           # a run's leftovers older than this are swept away
FILE_MAX_PATH = os.environ.get('VERIFY_SANDBOX_FILE_MAX', '/proc/sys/fs/file-max')        # the machine's file table; a test may point this elsewhere, to show the run fails closed
MAP_COUNT_PATH = '/proc/sys/vm/max_map_count'                           # the mappings one process may have: each can keep a file open
USERNS_PATH = '/proc/sys/user/max_user_namespaces'
SELF_CGROUP = '/proc/self/cgroup'
RUNS_AT_ONCE, FILE_MAX_MARGIN = 4, 2                                    # runs at once on the machine; the file table must hold this many times what they can keep open
REAL_FILE_MAX = '/proc/sys/fs/file-max'                                 # the kernel's own: a file named by the environment can make the table smaller, never larger
SLOTS_DIR = '/run/verify-sandbox'                                       # one lock for each run that may be made at once, held by every service on the machine
SHM_SEGMENTS = 4096                                                     # kernel.shmmni in a new IPC namespace: each segment is a file with no descriptor and no mapping
PAGE = os.sysconf('SC_PAGE_SIZE')
LATE = 0.5                                                              # seconds past the run's time that output still waiting may hold the clock
CGROUP_ROOT = os.environ.get('VERIFY_SANDBOX_CGROUP_ROOT', '/sys/fs/cgroup')   # a test may point this elsewhere, to show the run fails closed
NAMESPACES = ('user', 'mnt', 'pid', 'net', 'ipc', 'uts')

CLONE_NEWNS, CLONE_NEWUTS, CLONE_NEWIPC, CLONE_NEWUSER, CLONE_NEWPID, CLONE_NEWNET = 0x20000, 0x4000000, 0x8000000, 0x10000000, 0x20000000, 0x40000000
MS_RDONLY, MS_NOSUID, MS_NODEV, MS_NOEXEC, MS_REMOUNT, MS_BIND, MS_REC, MS_PRIVATE = 1, 2, 4, 8, 32, 4096, 16384, 1 << 18
PR_SET_PDEATHSIG, PR_SET_NO_NEW_PRIVS, PR_CAPBSET_DROP, PR_SET_SECCOMP, PR_SET_DUMPABLE = 1, 38, 24, 22, 4
SYS_KEYCTL, KEYCTL_JOIN_SESSION_KEYRING = 250, 1


@dataclass
class Outcome:
    state: str              # RAN, TIMEOUT, OUTPUT_TOO_LONG or SANDBOX_UNAVAILABLE
    returncode: int | None
    stdout: bytes
    stderr: bytes
    detail: str = ''


def python_for_checks() -> str:
    """The interpreter a check is run by: the service's own Python, if it lives under /usr (not /usr/local), which the sandbox carries."""
    for candidate in (sys.executable, '/usr/bin/python3'):
        real = os.path.realpath(candidate)                              # resolved here: the links (/etc/alternatives, /usr/local) are not in the sandbox
        if real.startswith('/usr/') and not real.startswith(('/usr/local/', '/usr/src/')) and os.access(real, os.X_OK):
            return real
    return '/usr/bin/python3'


def _ns_inodes() -> str:
    return ','.join(str(os.stat(f'/proc/self/ns/{n}').st_ino) for n in NAMESPACES)


# ---------------------------------------------------------------------------------------------------- control groups
class Cgroups:
    """A memory, a process and a freezer control group of this run's own, within the service's (cgroup v1)."""

    def __init__(self, name: str, memory: int, processes: int):
        self.dirs = []
        mine = {}
        for line in open('/proc/self/cgroup').read().splitlines():
            _, ctrls, path = line.split(':', 2)
            for c in ctrls.split(','):
                mine[c] = path
        self.freezer = None
        try:
            parents = {}
            for ctrl in ('memory', 'pids', 'freezer'):
                if ctrl not in mine:
                    raise OSError(f'no {ctrl} control group')
                parents[ctrl] = pathlib.Path(CGROUP_ROOT) / ctrl / mine[ctrl].lstrip('/')
            for ctrl in ('freezer', 'memory', 'pids'):                    # thawed first, so that the others empty in the same sweep
                sweep(parents[ctrl])
            for ctrl, settings in (('memory', {'memory.limit_in_bytes': memory}), ('pids', {'pids.max': processes}), ('freezer', {})):
                parent = parents[ctrl]
                d = parent / name
                d.mkdir()
                self.dirs.append(d)
                for f, v in settings.items():
                    (d / f).write_text(str(v))
                if ctrl == 'memory' and (d / 'memory.memsw.limit_in_bytes').exists():
                    (d / 'memory.memsw.limit_in_bytes').write_text(str(memory))   # swap counts too, where there is swap
                if ctrl == 'freezer':
                    self.freezer = d
        except OSError:
            self.kill_all(); raise

    def add(self, pid: int) -> None:
        for d in self.dirs:
            (d / 'cgroup.procs').write_text(str(pid))

    def kill_all(self) -> None:
        """Kill every process in the run's groups, until none is left; then remove the groups.  The group is frozen (as far as
        the kernel freezes it within a second) while its processes are named and killed, so that none can fork or exit and
        no number read is another process's by the time it is used."""
        for _ in range(500):
            if self.freezer is not None:
                _write(self.freezer / 'freezer.state', 'FROZEN')
                for _ in range(1000):                                   # freezing is not immediate: wait until it is done
                    try:
                        if (self.freezer / 'freezer.state').read_text().strip() == 'FROZEN':
                            break
                    except OSError:
                        break
                    time.sleep(0.001)
            pids = set()
            for d in self.dirs:
                try:
                    pids |= {int(p) for p in (d / 'cgroup.procs').read_text().split()}
                except OSError:
                    pass
            for p in pids:
                try:
                    os.kill(p, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if self.freezer is not None:
                _write(self.freezer / 'freezer.state', 'THAWED')        # thawed, the killed die
            if not pids:
                break
            time.sleep(0.01)
        for d in self.dirs:
            _write(d / 'memory.force_empty', '0') if (d / 'memory.force_empty').exists() else None   # what the kernel keeps charged to the run is freed, not handed to the service's group
            for _ in range(200):
                try:
                    d.rmdir(); break
                except FileNotFoundError:
                    break
                except OSError:
                    time.sleep(0.01)
        self.dirs = []


def _write(path, text: str) -> None:
    try:
        pathlib.Path(path).write_text(text)
    except OSError:
        pass


def sweep(parent: pathlib.Path) -> None:
    """Remove what runs older than STALE left behind (a service that died during a run): their groups, after killing anything
    still in them, and thawing them if they were left frozen; and their folders."""
    now = time.time()
    for d in parent.glob('verify-sandbox-*'):
        try:
            parts = d.name.split('-')                                  # verify-sandbox-UID-TIME; a name without its time is older than this rule
            made = int(parts[3]) if len(parts) == 4 and parts[3].isdigit() else d.stat().st_mtime
            if now - made < STALE:                                      # the time in its name: the kernel does not keep a group's mtime
                continue
            for p in (d / 'cgroup.procs').read_text().split():
                try:
                    os.kill(int(p), signal.SIGKILL)
                except (ProcessLookupError, ValueError):
                    pass
            if (d / 'freezer.state').exists():
                _write(d / 'freezer.state', 'THAWED')                   # a service killed while the run was frozen: thawed, the killed die
            if (d / 'memory.force_empty').exists():
                _write(d / 'memory.force_empty', '0')
            d.rmdir()                                                   # once: a group not yet empty is tried again by a later run, which does not wait for it
        except OSError:
            pass
    for f in glob.glob(os.path.join(tempfile.gettempdir(), 'verify-sandbox-*')):
        try:
            if now - os.stat(f).st_mtime >= STALE:
                shutil.rmtree(f, ignore_errors=True)
        except OSError:
            pass


def _free_ids() -> int:
    """Two host ids for a run: in the run range, named by no account here and used by no process."""
    used = set()
    for st in glob.glob('/proc/[0-9]*/status'):
        try:
            used |= {int(x) for line in open(st) if line.startswith('Uid:') for x in line.split()[1:]}
        except (OSError, ValueError):
            pass
    for _ in range(100):
        uid = UID_BASE + 2 * random.randrange(UID_SPAN // 2)
        if uid in used or uid + 1 in used:
            continue
        try:
            pwd.getpwuid(uid); continue
        except KeyError:
            pass
        try:
            pwd.getpwuid(uid + 1); continue
        except KeyError:
            return uid
    raise OSError('no free pair of ids for the run')


# ---------------------------------------------------------------------------------------------------- what the machine must give
def _number(path: str):
    try:
        return int(open(path).read().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def files_one_run_can_hold(limits: dict | None = None):
    """The most files one run can keep open at once, or None if it cannot be worked out.  For each of its processes: a file for
    each descriptor; a file for each mapping, which stays open after its descriptor is closed; and its own program.  A process
    may have vm.max_map_count mappings and one more, and no more than there are pages in the address space it is allowed, since
    each takes a page.  For the run: a file for each shared-memory segment of its own IPC namespace.  A process of the run cannot
    make namespaces of its own, having no user namespaces to make them in (it is in a chroot), so there is one such count."""
    limits = dict(LIMITS, **(limits or {}))
    mappings = _number(MAP_COUNT_PATH)
    if mappings is None or mappings < 1:
        return None
    return limits['processes'] * (min(mappings + 1, limits['memory_bytes'] // PAGE) + limits['open_files'] + 1) + SHM_SEGMENTS


def file_table_floor(limits: dict | None = None):
    """The smallest file table (fs.file-max) the sandbox runs on, or None if it cannot be worked out: FILE_MAX_MARGIN times what
    the RUNS_AT_ONCE runs the machine makes at once can keep open, so that they cannot fill it.  Measured on the machine this was
    written on: one run kept 2.6 million files open before its memory ran out, where the machine's own table was 1.6 million
    (Amendment 15)."""
    one = files_one_run_can_hold(limits)
    return None if one is None else FILE_MAX_MARGIN * RUNS_AT_ONCE * one


def prerequisites(limits: dict | None = None) -> list:
    """What the machine must give for a check to be run at all: [(name, met, words)], the words saying what was found.  The
    service looks at these before every run, and an operator can ask for them: python3 sandbox.py --prerequisites.  Nothing here
    changes the machine, and no run is made: that these are met does not show that a run can be.  What cannot be found out is
    not met.  (Amendment 15.)"""
    try:
        return _prerequisites(limits)
    except Exception as exc:
        return [('the machine', False, f'what the machine gives could not be found out ({type(exc).__name__}: {exc})'[:300])]


def _prerequisites(limits):
    out = [('root', os.geteuid() == 0,
            'the service runs as root' if os.geteuid() == 0 else
            'the sandbox needs the service to run as root, to give each run identities and control groups of its own'),
           ('x86-64', platform.machine() == 'x86_64',
            'the machine is x86-64' if platform.machine() == 'x86_64' else
            f'the sandbox\'s system-call filter is written for x86-64 only, and this machine is {platform.machine()}')]
    try:
        lines = [l.split(':', 2) for l in open(SELF_CGROUP).read().splitlines() if l.count(':') >= 2]
    except OSError as exc:
        lines = None; why = f'the sandbox\'s control groups cannot be made: {SELF_CGROUP} cannot be read ({type(exc).__name__})'
    if lines is not None:
        mine = {c: path for _, ctrls, path in lines for c in ctrls.split(',') if c}
        missing = [c for c in ('memory', 'pids', 'freezer') if c not in mine]
        absent = [c for c in ('memory', 'pids', 'freezer') if c in mine and not (pathlib.Path(CGROUP_ROOT) / c / mine[c].lstrip('/')).is_dir()]
        if missing and not mine and any(ctrls == '' for _, ctrls, _ in lines):
            why = ('the sandbox\'s control groups cannot be made: this machine gives its processes cgroup v2 only, and the sandbox uses cgroup v1 '
                   '(memory, pids and freezer); it does not run here')
        elif missing:
            why = f'the sandbox\'s control groups cannot be made: this process has no cgroup v1 {", ".join(missing)} control group'
        elif absent:
            why = f'the sandbox\'s control groups cannot be made: the {", ".join(absent)} control group of this process is not under {CGROUP_ROOT}'
        else:
            why = None
    out.append(('control groups', why is None, why or 'cgroup v1 memory, pids and freezer control groups are there'))
    spaces = _number(USERNS_PATH)
    out.append(('user namespaces', spaces is not None and spaces > 0,
                'the machine\'s limit on user namespaces allows some' if spaces is not None and spaces > 0 else
                'the sandbox needs user namespaces, and this machine allows none (user.max_user_namespaces is 0)' if spaces == 0 else
                'the sandbox needs user namespaces, and how many this machine allows (user.max_user_namespaces) cannot be read'))
    try:                                                                 # looked at, not made: the first run makes it
        st = os.lstat(SLOTS_DIR); there = stat.S_ISDIR(st.st_mode) and st.st_uid == 0 and not st.st_mode & 0o022
        why = f'the runs made at once are counted in {SLOTS_DIR}' if there else f'the runs made at once cannot be counted: {SLOTS_DIR} is not a folder of root\'s alone'
    except FileNotFoundError:
        up = os.path.dirname(SLOTS_DIR); there = os.path.isdir(up) and os.access(up, os.W_OK)
        why = f'the runs made at once can be counted in {SLOTS_DIR}, which the first run makes' if there else f'the runs made at once cannot be counted: {SLOTS_DIR} cannot be made'
    except OSError as exc:
        there = False; why = f'the runs made at once cannot be counted: {SLOTS_DIR} cannot be looked at ({type(exc).__name__})'
    out.append(('places for runs', there, why))
    table, floor = _number(FILE_MAX_PATH), file_table_floor(limits)
    named = ''
    if FILE_MAX_PATH != REAL_FILE_MAX:                                   # a file named in place of the kernel's can lower the table, for a test; it cannot raise it
        real = _number(REAL_FILE_MAX); named = f', the smaller of the kernel\'s and {FILE_MAX_PATH}'
        table = None if table is None or real is None else min(table, real)
    if table is not None and table < 1:
        table = None
    lim = dict(LIMITS, **(limits or {}))
    if table is None or floor is None:
        out.append(('file table', False, 'the machine\'s file table (fs.file-max) or the mappings a process may have (vm.max_map_count) cannot be read, '
                                         'so it cannot be shown that a run could not fill the file table'))
    else:
        held = floor // FILE_MAX_MARGIN
        out.append(('file table', table >= floor,
                    (f'the machine\'s file table (fs.file-max, {table}{named}) holds at least {floor}' if table >= floor else
                     f'the machine\'s file table (fs.file-max, {table}{named}) is below {floor}, {FILE_MAX_MARGIN} times the {held} files that {RUNS_AT_ONCE} runs at once can '
                     f'keep open through memory mappings ({lim["processes"]} processes each); runs could fill it, so the sandbox does not run')))
    return out


# ---------------------------------------------------------------------------------------------------- the service's side
def run(files: dict, script: str, stdin: bytes, timeout: float = 30.0, limits: dict | None = None, _no_unshare: bool = False) -> Outcome:
    """Run `script` (one of `files`, name -> bytes) in a new sandbox, with `stdin`, and throw the sandbox away."""
    limits = dict(LIMITS, **(limits or {}))
    for _name, met, words in prerequisites(limits):                      # each is looked at before every run: a machine that stops meeting one stops running checks
        if not met:
            return Outcome('SANDBOX_UNAVAILABLE', None, b'', b'', words[:300])
    try:
        place = _place(time.monotonic() + timeout)                       # the file table is the machine's, so the count of runs is the machine's too
    except OSError as exc:
        return Outcome('SANDBOX_UNAVAILABLE', None, b'', b'', f'the machine\'s count of runs at once could not be kept: {exc}'[:300])
    if place is None:
        return Outcome('SANDBOX_UNAVAILABLE', None, b'', b'', 'too many checks are running at once on this machine')
    try:
        return _run(files, script, stdin, timeout, limits, _no_unshare)
    finally:
        os.close(place)


def _place(deadline: float):
    """One of the machine's RUNS_AT_ONCE places for a run: a lock on a file of root's, held until the run is over and let go by
    the kernel if the service dies.  None if none comes free in time.  Every service that sees this folder takes its places
    here, so the runs the floor counts are all of theirs, whichever makes them.  Services that do not see one /run (in
    containers of their own, on one kernel) are not counted together; nor is a run whose service died while it was frozen for
    its kill, which keeps its files until a later run sweeps it."""
    os.makedirs(SLOTS_DIR, mode=0o700, exist_ok=True)
    folder = os.open(SLOTS_DIR, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        st = os.fstat(folder)
        if st.st_uid != 0 or st.st_mode & 0o022:
            raise OSError(f'{SLOTS_DIR} is not a folder of root\'s alone')
        while True:
            for i in range(RUNS_AT_ONCE):
                fd = os.open(f'place-{i}', os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=folder)
                try:
                    st = os.fstat(fd)
                    if not stat.S_ISREG(st.st_mode) or st.st_uid != 0:
                        raise OSError(f'{SLOTS_DIR}/place-{i} is not a file of root\'s')
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return fd
                except BlockingIOError:                                  # taken: by another run, here or in another service
                    os.close(fd)
                except BaseException:
                    os.close(fd)
                    raise
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.05)
    finally:
        os.close(folder)


def _run(files: dict, script: str, stdin: bytes, timeout: float, limits: dict, _no_unshare: bool) -> Outcome:
    def fit(name) -> bool:
        try:
            return isinstance(name, str) and '/' not in name and '\0' not in name and name not in ('', '.', '..') and not name.startswith('-') and len(name.encode()) <= 200
        except UnicodeError:
            return False
    for name in files:
        if not fit(name):
            return Outcome('SANDBOX_UNAVAILABLE', None, b'', b'', f'a file name the sandbox does not take: {name!r}'[:200])
    if script not in files:
        return Outcome('SANDBOX_UNAVAILABLE', None, b'', b'', 'the check is not among its files')
    try:
        uid = _free_ids()                                               # the run's root is uid, its user uid + 1
    except OSError as exc:
        return Outcome('SANDBOX_UNAVAILABLE', None, b'', b'', str(exc))
    base = pathlib.Path(tempfile.mkdtemp(prefix='verify-sandbox-'))      # 0700: the customer's files are no one else's to read
    groups, proc = None, None
    try:
        work, jail = base / 'work', base / 'jail'
        work.mkdir(mode=0o700); jail.mkdir(mode=0o700)
        try:
            for name, data in files.items():
                (work / name).write_bytes(data); (work / name).chmod(0o600); os.chown(work / name, uid, uid)
        except (OSError, ValueError, TypeError) as exc:
            return Outcome('SANDBOX_UNAVAILABLE', None, b'', b'', f'the check\'s files could not be put in the sandbox: {exc}'[:200])
        for d in (base, work, jail):
            os.chown(d, uid, uid)                                       # the run's root reads them; nobody else can
        try:
            groups = Cgroups(f'verify-sandbox-{uid}-{int(time.time())}', limits['memory_bytes'], limits['processes'])   # its name says when it was made
        except OSError as exc:
            return Outcome('SANDBOX_UNAVAILABLE', None, b'', b'', f'the sandbox\'s control groups could not be made: {exc}'[:200])
        ready_r, ready_w = os.pipe(); out_r, out_w = os.pipe(); in_r, in_w = os.pipe()
        cmd = [python_for_checks(), '-I', '-S', os.path.abspath(__file__), '--inside', str(jail), str(work), str(ready_w), str(out_w), str(in_r), _ns_inodes(),
               ','.join(str(limits[k]) for k in ('cpu_seconds', 'memory_bytes', 'processes', 'file_bytes', 'open_files', 'tmp_bytes', 'tmp_files')), str(timeout + GRACE), str(uid)] \
              + (['--no-unshare'] if _no_unshare else []) + ['--', python_for_checks(), '-I', '-S', f'/work/{script}']
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, pass_fds=(ready_w, out_w, in_r),
                                    start_new_session=True, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        except OSError as exc:
            for fd in (ready_r, ready_w, out_r, out_w, in_r, in_w):
                os.close(fd)
            return Outcome('SANDBOX_UNAVAILABLE', None, b'', b'', f'the sandbox could not be started: {exc}'[:200])
        for fd in (ready_w, out_w, in_r):
            os.close(fd)
        try:
            groups.add(proc.pid)                                        # before it can start anything: all it starts is in the groups
            if _read_line(out_r, 10.0) == b'UNSHARED\n' and not _no_unshare:
                for f in ('uid_map', 'gid_map'):                         # the run's two ids, and no other
                    with open(f'/proc/{proc.pid}/{f}', 'w') as m:
                        m.write(f'0 {uid} 1\n{NOBODY} {uid + 1} 1\n')
            os.write(in_w, b'GO\n')
        except OSError:
            pass                                                        # the launcher will find its maps missing, and refuse
        finally:
            os.close(out_r); os.close(in_w)
        return _supervise(proc, ready_r, stdin, timeout, groups)
    finally:
        if groups is not None:
            groups.kill_all()
        if proc is not None and proc.poll() is None:
            proc.kill(); proc.wait()
        shutil.rmtree(base, ignore_errors=True)                          # the sandbox is thrown away; its mounts went with its namespaces


def _read_line(fd: int, timeout: float) -> bytes:
    sel = selectors.DefaultSelector(); sel.register(fd, selectors.EVENT_READ)
    data, end = b'', time.monotonic() + timeout
    while not data.endswith(b'\n') and time.monotonic() < end:
        if sel.select(timeout=max(0.0, end - time.monotonic())):
            chunk = os.read(fd, 64)
            if not chunk:
                break
            data += chunk
    sel.close()
    return data


def _supervise(proc, ready_fd, stdin: bytes, timeout: float, groups) -> Outcome:
    out, err, ready, state, deadline = bytearray(), bytearray(), bytearray(), 'RAN', time.monotonic() + timeout
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ, out); sel.register(proc.stderr, selectors.EVENT_READ, err)
    sel.register(ready_fd, selectors.EVENT_READ, ready)
    pending = memoryview(stdin)
    os.set_blocking(proc.stdin.fileno(), False)
    if pending:
        sel.register(proc.stdin, selectors.EVENT_WRITE, None)
    else:
        proc.stdin.close()
    reading = 3
    while reading:
        events = sel.select(timeout=max(0.0, min(deadline - time.monotonic(), 1.0)))
        for key, _ in events:
            if key.data is None:                                         # the design goes in as the check reads it, never holding up the clock
                try:
                    n = os.write(proc.stdin.fileno(), pending[:65536]); pending = pending[n:]
                except BlockingIOError:
                    continue
                except OSError:
                    pending = pending[:0]
                if not pending:
                    sel.unregister(proc.stdin); proc.stdin.close()
                continue
            fd = key.fileobj if isinstance(key.fileobj, int) else key.fileobj.fileno()
            chunk = os.read(fd, 65536)
            if not chunk:
                sel.unregister(key.fileobj); reading -= 1; continue
            key.data.extend(chunk)
            if len(key.data) > MAX_OUTPUT:
                state = 'OUTPUT_TOO_LONG'; reading = 0; break
        if reading and deadline - time.monotonic() <= (0 if not events else -LATE):   # what is already in is read first, for at most LATE seconds
            state = 'TIMEOUT'; break
    sel.close()
    groups.kill_all()
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    for f in (proc.stdout, proc.stderr):
        f.close()
    if not proc.stdin.closed:
        try:
            proc.stdin.close()
        except OSError:
            pass
    while True:                                                          # what the launcher said last, after the check was gone
        try:
            more = os.read(ready_fd, 64)
        except OSError:
            break
        if not more:
            break
        ready.extend(more)
    os.close(ready_fd)
    code = proc.wait()
    said, why = bytes(ready), (bytes(err).decode(errors='replace').strip().splitlines() or ['no message'])[-1][:200]
    if not said.startswith(READY):
        return Outcome('SANDBOX_UNAVAILABLE', code, b'', bytes(err[:4096]), 'the sandbox could not be made: ' + why)
    if EXEC_FAILED in said:
        return Outcome('SANDBOX_UNAVAILABLE', code, b'', bytes(err[:4096]), 'the check could not be started in the sandbox: ' + why)
    return Outcome(state, code if state == 'RAN' else None, bytes(out[:MAX_OUTPUT]), bytes(err[:MAX_OUTPUT]))


# ---------------------------------------------------------------------------------------------------- inside the namespaces
def _libc():
    libc = ctypes.CDLL(ctypes.util.find_library('c') or 'libc.so.6', use_errno=True)
    libc.mount.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p]
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    libc.unshare.argtypes = [ctypes.c_int]
    libc.sethostname.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
    return libc


def _check(rc: int, what: str) -> None:
    if rc != 0:
        e = ctypes.get_errno(); raise OSError(e, f'{what}: {os.strerror(e)}')


def _mount(libc, source, target, fstype, flags, data=None) -> None:
    enc = lambda s: None if s is None else str(s).encode()
    _check(libc.mount(enc(source), enc(target), enc(fstype), flags, enc(data)), f'mount {source} on {target}')


def _seccomp_program() -> bytes:
    """A small system-call filter, for x86-64: no sockets of any family (socket and socketpair refused, EAFNOSUPPORT), so no
    vsock, which a network namespace does not close, and no Unix sockets, whose queued data the memory group does not count;
    and no keyring, io_uring, native asynchronous I/O, bpf, perf or userfaultfd calls (ENOSYS).  Any other architecture, or
    the x32 calls, end the process.  Everything else is allowed: this narrows the way out, it does not close it."""
    LD, JEQ, JGE, RET = 0x20, 0x15, 0x35, 0x06
    ALLOW, KILL = 0x7fff0000, 0x80000000
    errno = lambda e: 0x00050000 | e
    denied = (248, 249, 250, 298, 321, 323, 425, 426, 427,               # add_key, request_key, keyctl, perf_event_open, bpf, userfaultfd, io_uring_*
              206, 207, 208, 209, 210, 333)                              # io_setup, io_destroy, io_getevents, io_submit, io_cancel, io_pgetevents: one machine-wide limit
    prog = [(LD, 0, 0, 4), (JEQ, 1, 0, 0xc000003e), (RET, 0, 0, KILL), (LD, 0, 0, 0), (JGE, 0, 1, 0x40000000), (RET, 0, 0, KILL)]
    for nr in denied:
        prog += [(JEQ, 0, 1, nr), (RET, 0, 0, errno(38))]                # ENOSYS
    for nr in (41, 53):                                                 # socket, socketpair: refused for every family
        prog += [(JEQ, 0, 1, nr), (RET, 0, 0, errno(97))]               # EAFNOSUPPORT
    prog += [(RET, 0, 0, ALLOW)]
    return b''.join(code.to_bytes(2, 'little') + bytes([jt, jf]) + k.to_bytes(4, 'little') for code, jt, jf, k in prog)


def _install_seccomp(libc) -> None:
    raw = _seccomp_program()
    buf = ctypes.create_string_buffer(raw, len(raw))
    class Prog(ctypes.Structure):
        _fields_ = [('len', ctypes.c_ushort), ('filter', ctypes.c_void_p)]
    prog = Prog(len(raw) // 8, ctypes.cast(buf, ctypes.c_void_p))
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong]
    rc = libc.prctl(PR_SET_SECCOMP, 2, ctypes.byref(prog), 0, 0)        # SECCOMP_MODE_FILTER
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    _check(rc, 'seccomp')


def _refusal(parent_ns: str) -> str:
    """'' if this process is the first of new namespaces of every kind, none of them its parent's, with no network but a
    loopback and only the run's own two ids mapped; otherwise what is wrong."""
    if os.getpid() != 1:
        return 'not the first process of a new process namespace'
    for name, mine, theirs in zip(NAMESPACES, _ns_inodes().split(','), parent_ns.split(',')):
        if mine == theirs:
            return f'the {name} namespace is the service\'s own'
    try:
        names = [l.split(':')[0].strip() for l in open('/proc/self/net/dev').read().splitlines()[2:]]
    except OSError as exc:
        return f'the network namespace cannot be read ({exc})'
    if names not in ([], ['lo']):
        return f'a network namespace with interfaces {names}'
    m = open('/proc/self/uid_map').read().split()
    if len(m) != 6 or m[0] != '0' or m[2] != '1' or m[3] != str(NOBODY) or m[5] != '1' or not m[1].isdigit() or int(m[1]) < UID_BASE or m[4] != str(int(m[1]) + 1):
        return 'the user namespace does not map the run\'s own two ids'
    return ''


def jail_and_exec(libc, jail: str, work: str, ready_fd: int, parent_ns: str, limits: list, program: list) -> None:
    cpu, mem, nproc, fsize, nofile, tmpb, tmpn = limits
    why = _refusal(parent_ns)                                            # nothing is mounted, and nothing run, outside namespaces of its own
    if why:
        raise OSError(f'refused to make a sandbox: {why}')
    _mount(libc, None, '/', None, MS_REC | MS_PRIVATE)                  # nothing done here is seen outside
    _mount(libc, 'tmpfs', jail, 'tmpfs', MS_NOSUID | MS_NODEV, 'size=1m,nr_inodes=64,mode=0755')
    root = pathlib.Path(jail)
    for d in ('usr', 'work', 'tmp', 'dev'):
        (root / d).mkdir()
    for link, target in (('bin', 'usr/bin'), ('lib', 'usr/lib'), ('lib64', 'usr/lib64'), ('sbin', 'usr/sbin')):
        os.symlink(target, root / link)
    _mount(libc, '/usr', root / 'usr', None, MS_BIND | MS_REC)
    under = sorted({l.split()[4] for l in open('/proc/self/mountinfo') if l.split()[4] == str(root / 'usr') or l.split()[4].startswith(str(root / 'usr') + '/')})
    for m in under:                                                     # every mount under /usr read-only, not only the first
        _mount(libc, None, m, None, MS_BIND | MS_REMOUNT | MS_RDONLY | MS_NOSUID | MS_NODEV)
    hidden = ['local', 'src'] + [os.path.relpath(d, '/usr') for d in glob.glob('/usr/lib/python3*/*-packages')]
    for h in hidden:                                                     # what is installed beside the standard library is not the check's to see
        if (root / 'usr' / h).is_dir():
            _mount(libc, 'tmpfs', root / 'usr' / h, 'tmpfs', MS_RDONLY | MS_NOSUID | MS_NODEV | MS_NOEXEC, 'size=4k,nr_inodes=4,mode=0755')
    _mount(libc, 'tmpfs', root / 'work', 'tmpfs', MS_NOSUID | MS_NODEV | MS_NOEXEC, f'size={tmpb},nr_inodes={tmpn},mode=0700,uid={NOBODY},gid={NOBODY}')
    for f in os.listdir(work):                                           # copies of the hashed bytes, in memory, the check's own
        shutil.copyfile(os.path.join(work, f), root / 'work' / f)
        os.chown(root / 'work' / f, NOBODY, NOBODY); os.chmod(root / 'work' / f, 0o600)
    _mount(libc, 'tmpfs', root / 'tmp', 'tmpfs', MS_NOSUID | MS_NODEV | MS_NOEXEC, f'size={tmpb},nr_inodes={tmpn},mode=1777')
    for dev in ('null', 'zero', 'urandom'):
        (root / 'dev' / dev).touch()
        _mount(libc, f'/dev/{dev}', root / 'dev' / dev, None, MS_BIND)
    _mount(libc, None, jail, None, MS_REMOUNT | MS_RDONLY | MS_NOSUID | MS_NODEV)    # the root itself cannot be written
    _check(libc.sethostname(b'sandbox', 7), 'sethostname')
    os.chroot(jail); os.chdir('/work')
    check = os.fork()                                                   # the check is not the first process of the namespace: this stays, and is the sandbox's own
    if check == 0:
        try:
            _start_check(libc, ready_fd, limits, program)
        except BaseException as exc:
            sys.stderr.write(f'sandbox: {exc}\n'); sys.stderr.flush()
        os._exit(125)
    os.close(ready_fd)
    _check(libc.prctl(PR_SET_DUMPABLE, 0, 0, 0, 0), 'dumpable')
    while True:                                                         # it reaps what the check leaves; when the check ends, it ends, and the namespace with it
        try:
            pid, status = os.waitpid(-1, 0)
        except ChildProcessError:
            os._exit(125)
        if pid == check:
            os._exit(os.waitstatus_to_exitcode(status) & 0xff if os.WIFEXITED(status) else 128 + os.WTERMSIG(status))


def _start_check(libc, ready_fd: int, limits: list, program: list) -> None:
    """In the jail, as the check's own process: its limits, its keyring, no capabilities, the unprivileged id, the filter, and
    the check.  Its death signal is not relied on: the end of the namespace's first process ends it, whatever it does."""
    cpu, mem, nproc, fsize, nofile, tmpb, tmpn = limits
    for res, value in ((resource.RLIMIT_CPU, cpu), (resource.RLIMIT_AS, mem), (resource.RLIMIT_FSIZE, fsize), (resource.RLIMIT_NOFILE, nofile),
                       (resource.RLIMIT_CORE, 0), (resource.RLIMIT_NPROC, nproc), (resource.RLIMIT_MEMLOCK, 0),
                       (resource.RLIMIT_SIGPENDING, 64), (resource.RLIMIT_MSGQUEUE, 0)):
        resource.setrlimit(res, (value, value))
    libc.syscall.restype = ctypes.c_long
    if libc.syscall(SYS_KEYCTL, KEYCTL_JOIN_SESSION_KEYRING, None, 0, 0, 0) < 0:   # a new session keyring: not the service's
        e = ctypes.get_errno(); raise OSError(e, f'join session keyring: {os.strerror(e)}')
    for cap in range(64):                                               # while it may: the run's root holds the capabilities of its namespace
        if libc.prctl(PR_CAPBSET_DROP, cap, 0, 0, 0) != 0:
            if ctypes.get_errno() == 22:                                 # EINVAL: past the kernel's last capability
                break
            _check(-1, f'drop capability {cap}')
    os.setgroups([]); os.setresgid(NOBODY, NOBODY, NOBODY); os.setresuid(NOBODY, NOBODY, NOBODY)   # the run's unprivileged user; a failure stops here
    if os.getresuid() != (NOBODY,) * 3 or os.getresgid() != (NOBODY,) * 3 or os.getgroups():
        raise OSError('the run\'s unprivileged identity could not be taken')
    _check(libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0), 'no_new_privs')
    _check(libc.prctl(PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0), 'pdeathsig')   # cleared by the change of identity, so set again
    _install_seccomp(libc)
    os.write(ready_fd, READY)                                            # made; the check does not inherit this pipe
    try:
        os.execve(program[0], program, {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': '/work', 'TMPDIR': '/tmp'})
    except OSError as exc:
        os.write(ready_fd, EXEC_FAILED)                                  # said, so that a run that never started is not taken for one
        raise OSError(f'the check could not be started: {exc}')


def launcher(a: list) -> None:
    sep = a.index('--')
    jail, work, ready_fd, out_fd, in_fd, parent_ns, limits, allowed, owner = a[1], a[2], int(a[3]), int(a[4]), int(a[5]), a[6], [int(x) for x in a[7].split(',')], float(a[8]), int(a[9])
    program, no_unshare = a[sep + 1:], '--no-unshare' in a[:sep]
    for fd in (ready_fd, out_fd, in_fd):
        os.set_inheritable(fd, False)
    libc = _libc()
    parent = os.getppid()
    _check(libc.prctl(PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0), 'pdeathsig')   # if the service dies, so does the run
    if os.getppid() != parent:
        raise OSError('the service ended before the sandbox was made')
    _write('/proc/self/oom_score_adj', '1000')                          # the kernel's first choice when it must kill to free memory: the run, not the service
    os.setgroups([]); os.setresgid(owner, owner, owner); os.setresuid(owner, owner, owner)   # the run's own id makes its namespaces: what the kernel counts per user is the run's
    if os.getresuid() != (owner,) * 3 or os.getresgid() != (owner,) * 3:
        raise OSError('the run\'s own identity could not be taken')
    _check(libc.prctl(PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0), 'pdeathsig')   # cleared by taking the run's id, so set again
    if os.getppid() != parent:
        raise OSError('the service ended before the sandbox was made')
    if not no_unshare:
        _check(libc.unshare(CLONE_NEWUSER | CLONE_NEWNS | CLONE_NEWPID | CLONE_NEWNET | CLONE_NEWIPC | CLONE_NEWUTS), 'unshare')
    os.write(out_fd, b'UNSHARED\n')                                      # the service writes this run's two ids into the new user namespace
    os.close(out_fd)
    if os.read(in_fd, 8) != b'GO\n':
        raise OSError('the service did not finish making the namespaces')
    os.close(in_fd)
    if not no_unshare:
        os.setresgid(0, 0, 0); os.setresuid(0, 0, 0)                     # the run's root: its own host id, not the service's
    _check(libc.prctl(PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0), 'pdeathsig')   # cleared by the change of identity, so set again
    if os.getppid() != parent:                                          # the service died before it was set again
        raise OSError('the service ended before the sandbox was made')
    alive_r, alive_w = os.pipe()                                        # held open by the launcher: at its end, the child reads end-of-file
    child = os.fork()                                                   # the first process of the new process namespace
    if child == 0:
        try:
            os.close(alive_w)
            _check(libc.prctl(PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0), 'pdeathsig')
            if select.select([alive_r], [], [], 0)[0]:                    # the launcher died before the signal was set (its parent is not seen from here)
                raise OSError('the launcher ended before the sandbox was made')
            os.close(alive_r)
            jail_and_exec(libc, jail, work, ready_fd, parent_ns, limits, program)
        except BaseException as exc:
            sys.stderr.write(f'sandbox: {exc}\n'); sys.stderr.flush()
        os._exit(125)
    os.close(ready_fd); os.close(alive_r)
    end = time.monotonic() + allowed                                     # the run's time is kept here too, if the service cannot keep it
    while True:
        done, status = os.waitpid(child, os.WNOHANG)
        if done:
            break
        if time.monotonic() > end:
            os.kill(child, signal.SIGKILL)                               # the first process: its namespace goes with it
            _, status = os.waitpid(child, 0)
            break
        time.sleep(0.05)
    os._exit(os.waitstatus_to_exitcode(status) & 0xff if os.WIFEXITED(status) else 128 + os.WTERMSIG(status))


def main():
    a = sys.argv[1:]
    if a == ['--prerequisites']:                                         # for an operator, after a machine is set up or started again: what is met, and what is not
        found = prerequisites()
        for name, met, words in found:
            print(f'{"met    " if met else "NOT MET"}  {name}: {words}')
        print('Each of these is met, for this process, as it was started. No run was made: this does not show that one can be.' if all(met for _, met, _ in found) else
              'The sandbox cannot run checks on this machine: every run would be UNKNOWN, "the check was not run".')
        raise SystemExit(0 if all(met for _, met, _ in found) else 1)
    if not a or a[0] != '--inside' or '--' not in a:
        raise SystemExit(__doc__)
    try:
        launcher(a)
    except Exception as exc:
        sys.stderr.write(f'sandbox: {exc}\n'); sys.stderr.flush()
        os._exit(125)


if __name__ == '__main__':
    main()
