"""Where the verification service writes a notice for an engineer, and how it keeps every notice it writes.  (Amendment 7.)

Who gets a notice (Amendment 6).  A notice about a baseline goes to the engineer's inbox, inbox/<first 16 digits of the hash>/,
when the service holds that baseline's folder, or when the inbox holds the baseline's full hash in the file baseline_sha256.
A notice about a hash the service holds nothing for goes to inbox/unclaimed/<full hash>/, addressed to no engineer.

What happens when the inbox cannot be written (Amendment 7).  A full disk, a changed permission, a file in place of the
folder, and an inbox made by another account each stop the write.  The notice then goes to undelivered/<full hash>/ in the
service's own home, where the engineer's console lists it.  If that cannot be written either, the answer says so.  The
caller always gets the state back and never an error: a verdict is decided before its notice is written, and a notice that
cannot be written does not undo it.

How a notice is written.  Whole or not at all.  It is first written under a temporary name in the same folder and then
linked to its name, so a failure part-way leaves no partial notice; the temporary name is removed in every case.  Where the
file system makes no hard links, the text is written under its name in one piece, and taken away again if that fails
part-way.  A notice is never replaced.  A notice that must have one copy per name (a run cut off, asked for again) is
reported where its first copy is.

Whether the gate can write an inbox at all: the inbox-writability check (Amendment 8; named so by Amendment 9, which found
that "proof of delivery" claimed more than it shows).  The gate's tool writes a test file in an engineer's inbox and removes
it, and records what it found, with the time, in inbox_checks/<full hash>.json in the service's own home.  It does this when
it starts, on every run, and on a look of its own every second for a baseline with no good check yet or whose inbox it could
not write, and again for each good check well inside the time for which it stays good.  The engineer's console, enrolment and
the front door read that record.  A check that is missing, too old, or says the inbox could not be written means a failure
might not reach the engineer, so a job is not enrolled and a new run is not admitted at the front door until the check is
good.  The check shows that a test file could be written there, recently.  It does not show that a notice was delivered,
read or acknowledged.  It is a plain file, like a notice: it shows that the service is set up and working, and it is not a
defence against someone who can write the service's home.

Nothing here decides a verdict.  The gate's tool and the front door write what they have already decided.
"""
import json
import math
import os
import pathlib
import re
import stat
import time

CLAIM = 'baseline_sha256'           # Amendment 6: in an engineer's inbox, the full hash of the baseline the inbox belongs to
HEX = set('0123456789abcdef')
DELIVERY_MAX_AGE = 120.0            # Amendment 8: seconds for which the gate's inbox-writability check stays good
PROBE_BYTES = 4096                  # Amendment 8: the size of the file the gate writes to show it can write a notice
CHECKS = 'inbox_checks'              # Amendment 9: the folder of inbox-writability checks (Amendment 8 called it delivery/)
DELIVERY_WORDS = {                  # Amendment 8: what each state of the check means, in the service's own words
    'UNCHECKED': 'the verification service has not shown that it can write a notice to the inbox of this baseline',
    'STALE': 'the verification service has not shown lately that it can write a notice to the inbox of this baseline',
    'NOT_WRITABLE': 'the verification service cannot write a notice to the inbox of this baseline',
}


class NameTaken(FileExistsError):
    """A notice of this name is already in the folder, and the caller asked for one copy per name."""


def held(home, baseline_sha256: str) -> bool:
    """Whether the service holds a baseline folder for this exact hash.  An error in looking, such as a folder that cannot be
    searched, counts as not held, so that the inbox's claim decides and the notice is not lost.  (Amendment 6.)"""
    try:
        return (pathlib.Path(home) / 'baselines' / baseline_sha256).is_dir()
    except OSError:
        return False


def claimed(box: pathlib.Path):
    """The full hash an inbox holds, or None if it holds none that can be read: no file, an empty one, or one that is not a
    hash.  (Amendment 6.)"""
    try:
        text = (box / CLAIM).read_text(encoding='utf-8').strip()
    except (OSError, UnicodeError):
        return None
    return text if len(text) == 64 and set(text) <= HEX else None


def inbox_for(home, baseline_sha256: str):
    """Where a notice about this hash goes, and whether that is an engineer's inbox.  (Amendment 6.)  An inbox is named by the
    first 64 bits of the hash, so a notice goes to it only when the service holds this exact baseline or the inbox holds this
    exact full hash.  Any other notice is kept in inbox/unclaimed/<the full hash>/, which is no engineer's inbox."""
    home = pathlib.Path(home)
    box = home / 'inbox' / baseline_sha256[:16]
    if held(home, baseline_sha256) or claimed(box) == baseline_sha256:
        return box, True
    return home / 'inbox' / 'unclaimed' / baseline_sha256, False


def claim(home, baseline_sha256: str) -> None:
    """For a baseline folder the service holds: make its engineer's inbox, and write the inbox's claim if it holds none that can
    be read.  (Amendment 6.)  A claim naming another full hash is left as it is.  The claim is written whole or not at all, by a
    link or, where the file system makes none, a rename.  Nothing here stops a run."""
    home = pathlib.Path(home)
    box = home / 'inbox' / baseline_sha256[:16]
    try:
        box.mkdir(parents=True, exist_ok=True)
        if claimed(box) is not None:
            return
        part = box / f'.{CLAIM}.{os.getpid()}.{os.urandom(6).hex()}'          # its own name in every thread and process
        try:
            part.write_text(baseline_sha256 + '\n', encoding='utf-8')
            try:
                os.link(part, box / CLAIM)
            except OSError:                                    # one is there already, or the file system makes no hard links
                if claimed(box) is None:
                    os.replace(part, box / CLAIM)
        finally:
            part.unlink(missing_ok=True)
    except OSError:
        pass


def claim_all(home) -> None:
    """When the gate's tool starts: every baseline folder the service holds gets its inbox's claim, as baselines made before
    Amendment 6 have none.  (Amendment 6.)"""
    home = pathlib.Path(home)
    try:
        names = [p.name for p in (home / 'baselines').iterdir()]
    except OSError:
        return
    for name in names:
        if len(name) == 64 and set(name) <= HEX and held(home, name):
            claim(home, name)


def _write_whole(target: pathlib.Path, text: str) -> None:
    """The text under the name, in one piece.  FileExistsError if the name is taken.  A name made here and part-written is
    taken away again before the error is raised.  (Amendment 7.)"""
    f = target.open('x', encoding='utf-8')
    try:
        with f:
            f.write(text)
    except BaseException:                  # a stop part-way (an error, or an interrupt) takes the name away too (Amendment 7)
        target.unlink(missing_ok=True)
        raise


def publish(folder: pathlib.Path, stem: str, body: str, numbered: bool) -> str:
    """Write one notice in this folder, whole or not at all, and return its file name.  Numbered: a name already taken gets the
    next number after it.  Not numbered: a name already taken raises NameTaken.  Raises OSError if it cannot be written.
    (Amendment 7.)"""
    folder.mkdir(parents=True, exist_ok=True)
    text = body.encode('utf-8', 'backslashreplace').decode('utf-8') + '\n'     # a text that cannot be encoded is written escaped
    part = folder / f'.notice.{os.getpid()}.{os.urandom(6).hex()}.part'
    try:
        part.write_text(text, encoding='utf-8')
        for n in (range(1, 100000) if numbered else (1,)):
            name = f'{stem}.txt' if n == 1 else f'{stem}_{n}.txt'
            target = folder / name
            try:
                os.link(part, target)
                return name
            except FileExistsError:
                pass
            except OSError:                                    # a file system that makes no hard links
                try:
                    _write_whole(target, text)
                    return name
                except FileExistsError:
                    pass
            if not numbered:
                raise NameTaken(str(target))
        raise OSError(f'no free name for a notice beginning {stem}')
    finally:
        part.unlink(missing_ok=True)


def deliver(home, baseline_sha256: str, stem: str, make_body, numbered: bool = True, inbox_again: bool = False):
    """Write one notice for this hash, where it can be written: in the engineer's inbox (or inbox/unclaimed/ for a hash nobody
    holds); failing that, in undelivered/<hash>/ in the service's own home; failing that, nowhere.  make_body(engineer) gives the
    text and must not raise.  Returns (state, file name or None), the state being INBOX, UNCLAIMED, UNDELIVERED or NOT_WRITTEN.
    (Amendment 7.)

    Not numbered: one copy per name, in either place.  With inbox_again, one copy per name in each place: a copy kept in the
    store while the inbox could not take it does not stop the inbox getting its own copy once it can.  (Amendment 8.)"""
    home = pathlib.Path(home)
    box, engineer = inbox_for(home, baseline_sha256)
    places = ((box, 'INBOX' if engineer else 'UNCLAIMED'), (home / 'undelivered' / baseline_sha256, 'UNDELIVERED'))
    if not numbered:                       # one copy per name, in either place: a copy already there is reported where it is (Amendment 7)
        for folder, state in places[:1] if inbox_again else places:
            try:
                if (folder / f'{stem}.txt').is_file():
                    return state, f'{stem}.txt'
            except OSError:
                continue
    body = make_body(engineer)
    for folder, state in places:
        try:
            return state, publish(folder, stem, body, numbered)
        except NameTaken:
            return state, f'{stem}.txt'                       # one copy for this name, written before: reported where it is
        except OSError:
            continue
    return 'NOT_WRITTEN', None


def written(home, baseline_sha256: str, stem: str) -> bool:
    """Whether a notice of this name is already in the engineer's inbox or in the service's own store.  (Amendment 7.)"""
    home = pathlib.Path(home)
    box, _ = inbox_for(home, baseline_sha256)
    for folder in (box, home / 'undelivered' / baseline_sha256):
        try:
            if (folder / f'{stem}.txt').is_file():
                return True
        except OSError:
            continue
    return False


def undelivered(home, baseline_sha256: str) -> list:
    """The notices the service kept in its own store because the engineer's inbox could not be written.  (Amendment 7.)"""
    try:
        return sorted(p.name for p in (pathlib.Path(home) / 'undelivered' / baseline_sha256).glob('*.txt'))
    except OSError:
        return []


# ---------------------------------------------------------------------------------------------------- Amendment 8: the inbox-writability check
# The exact names this service gives its own temporary files: a probe, a part-written claim and a part-written notice in an
# inbox or its store, and a part-written check in the folder of checks.  Each carries the process's number and twelve hex digits.
LEFT_BEHIND = re.compile(r'\.(?:probe|%s)\.[0-9]+\.[0-9a-f]{12}|\.notice\.[0-9]+\.[0-9a-f]{12}\.part' % re.escape(CLAIM))
LEFT_PROOF = re.compile(r'\.[0-9a-f]{64}\.json\.[0-9]+\.[0-9a-f]{12}')


def sweep(folder, names=LEFT_BEHIND, older_than: float = 60.0) -> int:
    """Take away this service's own temporary files that a process killed part-way left in a folder: a probe, a part-written
    notice, claim or check, each more than a minute old.  Only a plain file whose whole name is one this service gives is taken:
    not a folder or a link, and not a file of anyone else's that begins the same way.  Returns how many.  Nothing is raised.
    (Amendment 8.)"""
    taken = 0
    try:
        found = os.listdir(folder)
    except OSError:
        return 0
    for name in found:
        if names.fullmatch(name):
            try:
                path = os.path.join(folder, name); st = os.lstat(path)
                if stat.S_ISREG(st.st_mode) and time.time() - st.st_mtime > older_than:
                    os.unlink(path); taken += 1
            except OSError:
                pass
    return taken


def sweep_all(home) -> int:
    """The same for every inbox, every folder of notices that are no engineer's, the service's own store and its folder of
    checks, as the gate's tool starts.  (Amendment 8.)"""
    home = pathlib.Path(home); taken = 0
    for parent in (home / 'inbox', home / 'inbox' / 'unclaimed', home / 'undelivered'):
        taken += sweep(parent)                             # the store is probed in its own folder
        try:
            subs = os.listdir(parent)
        except OSError:
            subs = []
        for sub in subs:
            taken += sweep(parent / sub)
    return taken + sweep(home / CHECKS, LEFT_PROOF)


def can_write(folder, make: bool = True) -> bool:
    """Whether this process can write a file the size of a notice in the folder now.  It writes a file under a name of its own,
    has it put on the disk, and removes it.  Nothing is left behind.  With make, it makes the folder first if it can; without,
    a folder that is not there cannot be written.  (Amendment 8.)"""
    folder = pathlib.Path(folder); name = None
    try:
        if make:
            folder.mkdir(parents=True, exist_ok=True)
        elif not folder.is_dir():
            return False
        name = folder / f'.probe.{os.getpid()}.{os.urandom(6).hex()}'
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, b'\n' * PROBE_BYTES)
            os.fsync(fd)
        finally:
            os.close(fd)
        return True
    except OSError:
        return False
    finally:
        if name is not None:
            try:
                os.unlink(name)
            except OSError:
                pass


def proof_path(home, baseline_sha256: str) -> pathlib.Path:
    return pathlib.Path(home) / CHECKS / f'{baseline_sha256}.json'


def prove(home, baseline_sha256: str, make: bool = True) -> dict:
    """The gate's tool shows whether it can write this baseline's inbox and the service's own store, and records what it found
    with the time at which it had tried.  The record replaces the last one whole, and can be read by any account.  If it cannot
    be recorded, the record left from before is taken away, so that it is not read as good.  Returns what it found, and whether
    it could be recorded.  Nothing is raised.  (Amendment 8.)"""
    home = pathlib.Path(home)
    inbox, store = can_write(home / 'inbox' / baseline_sha256[:16], make), can_write(home / 'undelivered')
    found = {'baseline_sha256': baseline_sha256, 'checked_at': time.time(), 'pid': os.getpid(), 'inbox': inbox, 'store': store}
    path = proof_path(home, baseline_sha256)
    part = path.with_name(f'.{path.name}.{os.getpid()}.{os.urandom(6).hex()}')
    recorded = False
    try:
        if not path.parent.is_dir():
            path.parent.mkdir(parents=True, exist_ok=True)
            os.chmod(path.parent, 0o755)           # whatever this process's mask: the console and the front door read the checks
        fd = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            os.write(fd, (json.dumps(found) + '\n').encode('utf-8'))
            os.fchmod(fd, 0o644)
        finally:
            os.close(fd)
        os.replace(part, path)
        recorded = True
    except OSError:
        for stale in (part, path):                 # the check left from before is not kept as good when a new one cannot be recorded
            try:
                os.unlink(stale)
            except OSError:
                pass
    return dict(found, recorded=recorded)


def prove_due(home, seen: dict, refresh: float, grace: float = 0.0) -> list:
    """Check again that the inbox can be written, for every baseline whose notices would go to an engineer's inbox: each baseline folder the service
    holds, and each baseline whose folder is gone and whose inbox still holds its hash.  One is left alone only if the last
    check this process made for it was good and is less than `refresh` seconds from now, either way, so that a clock put back
    does not put a check off.  `seen` is this process's memory of its own checks.

    Who makes an inbox.  The console makes it, a moment after the baseline's folder.  So a held baseline with no inbox yet is
    left for the next look while its folder is dated less than `grace` seconds from now, either way; after that the inbox is
    made here, as for a baseline made before Amendment 6.  Returns the checks it made.  (Amendment 8.)"""
    home = pathlib.Path(home)

    def due(h: str) -> bool:
        last = seen.get(h)
        return not (last is not None and last[1] and abs(time.time() - last[0]) < refresh)

    def note(found: dict) -> None:
        seen[found['baseline_sha256']] = (found['checked_at'], bool(found['inbox'] and found['recorded']))
        made.append(found)

    try:
        names = [n for n in os.listdir(home / 'baselines') if len(n) == 64 and set(n) <= HEX and held(home, n)]
    except OSError:
        names = []
    made = []
    for name in names:
        if not due(name):
            continue
        try:
            if not (home / 'inbox' / name[:16]).is_dir() and abs(time.time() - os.stat(home / 'baselines' / name).st_mtime) < grace:
                continue                                   # the console is still making this baseline; its inbox is the console's to make
        except OSError:
            pass
        claim(home, name)
        note(prove(home, name))
    ours = {n[:16] for n in names}
    try:
        boxes = [b for b in os.listdir(home / 'inbox') if len(b) == 16 and set(b) <= HEX and b not in ours]
    except OSError:
        boxes = []
    for b in boxes:                                        # an inbox left with its hash after its baseline's folder was taken away
        h = claimed(home / 'inbox' / b)
        if h is not None and h[:16] == b and due(h):
            note(prove(home, h, make=False))
    return made


def delivery_state(home, baseline_sha256: str, max_age: float = DELIVERY_MAX_AGE, now=None):
    """What the gate's last inbox-writability check for this baseline says: (state, the time of the check or None).  WRITABLE: it
    wrote a test file in the inbox, no longer than max_age seconds ago.  NOT_WRITABLE: it could not write the inbox.  STALE: the
    check is older than max_age, or is dated further ahead than that.  UNCHECKED: there is no check that can be read for this
    exact hash, with a time that is a
    number.  (Amendment 8.)"""
    try:
        d = json.loads(proof_path(home, baseline_sha256).read_text(encoding='utf-8'))
        if not isinstance(d, dict) or d.get('baseline_sha256') != baseline_sha256:
            return 'UNCHECKED', None
        t = float(d['checked_at'])
        if isinstance(d['checked_at'], bool) or not math.isfinite(t):
            return 'UNCHECKED', None
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError, RecursionError):
        return 'UNCHECKED', None
    if d.get('inbox') is not True:
        return 'NOT_WRITABLE', t
    if abs((time.time() if now is None else now) - t) > max_age:
        return 'STALE', t
    return 'WRITABLE', t
