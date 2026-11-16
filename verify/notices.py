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

Nothing here decides a verdict.  The gate's tool and the front door write what they have already decided.
"""
import os
import pathlib
import time

CLAIM = 'baseline_sha256'           # Amendment 6: in an engineer's inbox, the full hash of the baseline the inbox belongs to
HEX = set('0123456789abcdef')


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


def deliver(home, baseline_sha256: str, stem: str, make_body, numbered: bool = True):
    """Write one notice for this hash, where it can be written: in the engineer's inbox (or inbox/unclaimed/ for a hash nobody
    holds); failing that, in undelivered/<hash>/ in the service's own home; failing that, nowhere.  make_body(engineer) gives the
    text and must not raise.  Returns (state, file name or None), the state being INBOX, UNCLAIMED, UNDELIVERED or NOT_WRITTEN.
    (Amendment 7.)"""
    home = pathlib.Path(home)
    box, engineer = inbox_for(home, baseline_sha256)
    places = ((box, 'INBOX' if engineer else 'UNCLAIMED'), (home / 'undelivered' / baseline_sha256, 'UNDELIVERED'))
    if not numbered:                       # one copy per name, in either place: a copy already there is reported where it is (Amendment 7)
        for folder, state in places:
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
