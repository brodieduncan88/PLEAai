#!/usr/bin/env python3
"""The disposable sandbox a declared check runs in (Amendment 12, release gate G2).

    run(files, script, stdin, ...) -> Outcome      used by baseline.evaluate() for every run of a check

A check is code the customer supplies, so it is run as if it were hostile.  Each run gets a sandbox of its own, made for it
and thrown away after it:

  - a fresh empty work folder holding only the check and its data files, the bytes that were hashed;
  - new mount, process, network, IPC and host-name namespaces (unshare(1)): the check sees no other process, has no network
    at all (not even loopback), and its mounts are its own;
  - a root of its own: an empty, read-only file system holding the Python installation (/usr, read-only), the work folder at
    /work, a small /tmp, and /dev/null, /dev/zero and /dev/urandom.  Nothing else of the machine is there: not the service's
    home, its keys, its database credentials, its journals or its inbox, not /etc, not /proc;
  - an identity of nobody's: user and group 65534 with no other groups and no capabilities, and no way to gain any (no new
    privileges);
  - limits: CPU time, memory, processes, file size, open files, no core dumps, the size of what it prints, and the wall-clock
    time of the whole run.  When the run ends, every process it started ends with it.

The check is run by the Python standard library alone (python -I -S): no site packages, no environment from the service.

If the sandbox cannot be made, the check is not run, and the run says why: the outcome is SANDBOX_UNAVAILABLE.  Nothing ever
falls back to running a check outside it.  The launcher does nothing unless it is the first process of a new process
namespace with no network, and it signals that the sandbox is ready on a pipe the check cannot inherit, so a check cannot
pretend that it was or was not made.  VERIFY_SANDBOX_UNSHARE names another unshare(1); it is for a test, which points it at
a program that makes no namespaces, to show that the check is then not run.

What it does not do.  It does not filter system calls (no seccomp), so the check can reach the whole of the kernel's
interface as an unprivileged user in its own namespaces; a kernel flaw would be a way out.  It needs the service to run as
root, or user namespaces to be enabled.  The limits are per run; many runs at once share the machine.  In the demonstration
the service itself runs as root on the same machine.

    sandbox.py --inside JAIL WORK READY_FD -- PROGRAM ARGS...    (the launcher, run by run() inside the new namespaces)

Standard library only.
"""
import ctypes
import ctypes.util
import os
import pathlib
import resource
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass

UNSHARE = os.environ.get('VERIFY_SANDBOX_UNSHARE', '/usr/bin/unshare')    # a test may point this elsewhere to show the run fails closed
NOBODY = 65534
LIMITS = {'cpu_seconds': 30, 'memory_bytes': 1 << 30, 'processes': 64, 'file_bytes': 64 << 20, 'open_files': 64, 'tmp_bytes': 64 << 20}
MAX_OUTPUT = 1 << 20                                                    # bytes of standard output, and of standard error, kept
READY = b'SANDBOX-READY\n'

MS_RDONLY, MS_NOSUID, MS_NODEV, MS_NOEXEC, MS_REMOUNT, MS_BIND, MS_REC, MS_PRIVATE = 1, 2, 4, 8, 32, 4096, 16384, 1 << 18
PR_SET_NO_NEW_PRIVS, PR_CAPBSET_DROP, PR_SET_DUMPABLE = 38, 24, 4


@dataclass
class Outcome:
    state: str              # RAN, TIMEOUT, OUTPUT_TOO_LONG or SANDBOX_UNAVAILABLE
    returncode: int | None
    stdout: bytes
    stderr: bytes
    detail: str = ''


def python_for_checks() -> str:
    """The interpreter a check is run by: the service's own Python, if it lives under /usr, which the sandbox carries."""
    real = os.path.realpath(sys.executable)
    return real if real.startswith('/usr/') else '/usr/bin/python3'


def run(files: dict, script: str, stdin: bytes, timeout: float = 30.0, limits: dict | None = None) -> Outcome:
    """Run `script` (one of `files`, name -> bytes) in a new sandbox, with `stdin`, and throw the sandbox away."""
    limits = dict(LIMITS, **(limits or {}))
    base = pathlib.Path(tempfile.mkdtemp(prefix='verify-sandbox-'))
    try:
        work, jail = base / 'work', base / 'jail'
        work.mkdir(); jail.mkdir()
        for name, data in files.items():
            if '/' in name or name in ('', '.', '..'):
                return Outcome('SANDBOX_UNAVAILABLE', None, b'', b'', f'a file name the sandbox does not take: {name!r}')
            (work / name).write_bytes(data); (work / name).chmod(0o644)
        os.chmod(base, 0o755); os.chmod(jail, 0o755); os.chmod(work, 0o755)
        if os.geteuid() == 0:
            os.chown(work, NOBODY, NOBODY)                               # the work folder is the check's; nothing else is
        rfd, wfd = os.pipe()
        cmd = [UNSHARE, '--mount', '--pid', '--net', '--ipc', '--uts', '--fork', '--kill-child'] + ([] if os.geteuid() == 0 else ['--map-root-user']) + \
              [python_for_checks(), '-I', '-S', os.path.abspath(__file__), '--inside', str(jail), str(work), str(wfd),
               f"--limits={limits['cpu_seconds']},{limits['memory_bytes']},{limits['processes']},{limits['file_bytes']},{limits['open_files']},{limits['tmp_bytes']}",
               '--', python_for_checks(), '-I', '-S', script]
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, pass_fds=(wfd,),
                                    start_new_session=True, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        except OSError as exc:
            os.close(rfd); os.close(wfd)
            return Outcome('SANDBOX_UNAVAILABLE', None, b'', b'', f'the sandbox could not be started: {exc}'[:200])
        os.close(wfd)
        return _supervise(proc, rfd, stdin, timeout)
    finally:
        shutil.rmtree(base, ignore_errors=True)                          # the sandbox is thrown away; its mounts went with its namespace


def _supervise(proc, rfd, stdin: bytes, timeout: float) -> Outcome:
    out, err, ready, state, deadline = bytearray(), bytearray(), bytearray(), 'RAN', time.monotonic() + timeout
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ, out); sel.register(proc.stderr, selectors.EVENT_READ, err)
    sel.register(rfd, selectors.EVENT_READ, ready)
    try:
        proc.stdin.write(stdin); proc.stdin.close()
    except (BrokenPipeError, OSError):
        pass
    open_streams = 3
    while open_streams:
        left = deadline - time.monotonic()
        if left <= 0:
            state = 'TIMEOUT'; break
        for key, _ in sel.select(timeout=min(left, 1.0)):
            fd = key.fileobj if isinstance(key.fileobj, int) else key.fileobj.fileno()
            chunk = os.read(fd, 65536)
            if not chunk:
                sel.unregister(key.fileobj); open_streams -= 1; continue
            key.data.extend(chunk)
            if len(key.data) > MAX_OUTPUT:
                state = 'OUTPUT_TOO_LONG'; open_streams = 0; break
    _kill(proc)
    for f in (proc.stdout, proc.stderr):
        f.close()
    os.close(rfd)
    code = proc.wait()
    if not bytes(ready).startswith(READY):
        return Outcome('SANDBOX_UNAVAILABLE', code, b'', bytes(err[:4096]),
                       'the sandbox could not be made: ' + (bytes(err).decode(errors='replace').strip().splitlines() or ['no message'])[-1][:200])
    return Outcome(state, code if state == 'RAN' else None, bytes(out[:MAX_OUTPUT]), bytes(err[:MAX_OUTPUT]))


def _kill(proc) -> None:
    """End the run and everything it started: the launcher's process group, and so (by --kill-child) the namespace's first process."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


# ---------------------------------------------------------------------------------------------------- inside the namespaces
def _libc():
    libc = ctypes.CDLL(ctypes.util.find_library('c') or 'libc.so.6', use_errno=True)
    libc.mount.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p]
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    return libc


def _mount(libc, source, target, fstype, flags, data=None) -> None:
    enc = lambda s: None if s is None else str(s).encode()
    if libc.mount(enc(source), enc(target), enc(fstype), flags, enc(data)) != 0:
        e = ctypes.get_errno()
        raise OSError(e, f'mount {source} on {target}: {os.strerror(e)}')


def _drop_capabilities(libc) -> None:
    """Empty the bounding set and every capability set of this process."""
    for cap in range(64):
        libc.prctl(PR_CAPBSET_DROP, cap, 0, 0, 0)                      # beyond the last capability it fails harmlessly
    class Header(ctypes.Structure):
        _fields_ = [('version', ctypes.c_uint32), ('pid', ctypes.c_int)]
    class Data(ctypes.Structure):
        _fields_ = [('effective', ctypes.c_uint32), ('permitted', ctypes.c_uint32), ('inheritable', ctypes.c_uint32)]
    header, data = Header(0x20080522, 0), (Data * 2)()
    if libc.capset(ctypes.byref(header), data) != 0:
        e = ctypes.get_errno(); raise OSError(e, f'capset: {os.strerror(e)}')


def _in_new_namespaces() -> str:
    """'' if this process is the first of a new process namespace with no network but loopback; else what is wrong."""
    if os.getpid() != 1:
        return 'not the first process of a new process namespace'
    try:
        names = [l.split(':')[0].strip() for l in open('/proc/self/net/dev').read().splitlines()[2:]]
    except OSError as exc:
        return f'the network namespace cannot be read ({exc})'
    return '' if names in ([], ['lo']) else f'a network namespace with interfaces {names}'


def inside(jail: str, work: str, ready_fd: int, limits: list, program: list) -> None:
    why = _in_new_namespaces()                                          # nothing is mounted, and nothing run, outside a namespace of its own
    if why:
        raise OSError(f'refused to make a sandbox: {why}')
    libc = _libc()
    cpu, mem, nproc, fsize, nofile, tmpb = limits
    _mount(libc, None, '/', None, MS_REC | MS_PRIVATE)                  # nothing done here is seen outside
    _mount(libc, 'tmpfs', jail, 'tmpfs', MS_NOSUID | MS_NODEV, 'size=1m,mode=0755')
    root = pathlib.Path(jail)
    for d in ('usr', 'work', 'tmp', 'dev'):
        (root / d).mkdir()
    for link, target in (('bin', 'usr/bin'), ('lib', 'usr/lib'), ('lib64', 'usr/lib64'), ('sbin', 'usr/sbin')):
        os.symlink(target, root / link)
    _mount(libc, '/usr', root / 'usr', None, MS_BIND | MS_REC)
    _mount(libc, None, root / 'usr', None, MS_BIND | MS_REMOUNT | MS_RDONLY | MS_NOSUID | MS_NODEV)
    _mount(libc, work, root / 'work', None, MS_BIND)
    _mount(libc, None, root / 'work', None, MS_BIND | MS_REMOUNT | MS_NOSUID | MS_NODEV | MS_NOEXEC)
    _mount(libc, 'tmpfs', root / 'tmp', 'tmpfs', MS_NOSUID | MS_NODEV | MS_NOEXEC, f'size={tmpb},mode=1777')
    for dev in ('null', 'zero', 'urandom'):
        (root / 'dev' / dev).touch()
        _mount(libc, f'/dev/{dev}', root / 'dev' / dev, None, MS_BIND)
    _mount(libc, None, jail, None, MS_REMOUNT | MS_RDONLY | MS_NOSUID | MS_NODEV)    # the root itself cannot be written
    os.chroot(jail); os.chdir('/work')
    for res, value in ((resource.RLIMIT_CPU, cpu), (resource.RLIMIT_AS, mem), (resource.RLIMIT_FSIZE, fsize), (resource.RLIMIT_NOFILE, nofile),
                       (resource.RLIMIT_CORE, 0), (resource.RLIMIT_NPROC, nproc), (resource.RLIMIT_MEMLOCK, 0)):
        resource.setrlimit(res, (value, value))
    if os.getuid() == 0:
        try:
            os.setgroups([]); os.setgid(NOBODY); os.setuid(NOBODY)      # nobody's identity: the service's files are not its own
        except OSError:
            pass                                                       # in a user namespace with only root mapped, stay that root and drop every capability
    _drop_capabilities(libc) if os.getuid() == 0 else None
    if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'no_new_privs')
    libc.prctl(PR_SET_DUMPABLE, 0, 0, 0, 0)
    os.write(ready_fd, READY); os.close(ready_fd)                       # made; the check does not inherit this pipe
    os.execve(program[0], program, {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': '/work', 'TMPDIR': '/tmp'})


def main():
    a = sys.argv[1:]
    if not a or a[0] != '--inside' or '--' not in a:
        raise SystemExit(__doc__)
    sep = a.index('--')
    jail, work, fd = a[1], a[2], int(a[3])
    limits = [int(x) for x in a[4].split('=', 1)[1].split(',')]
    os.set_inheritable(fd, False)
    try:
        inside(jail, work, fd, limits, a[sep + 1:])
    except Exception as exc:
        sys.stderr.write(f'sandbox: {exc}\n'); sys.stderr.flush()
        os._exit(125)


if __name__ == '__main__':
    main()
