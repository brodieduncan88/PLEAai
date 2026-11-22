#!/usr/bin/env python3
"""The responsible engineer's console for the front door: who may ask, and against which baseline.

    front_ctl.py enrol  HOME JOB HASH --key ENGINEER.key --ca CA.crt --ca-key CA.key --url https://HOST:PORT --out DIR [--reason "..."]
    front_ctl.py rebind HOME JOB NEWHASH --key ENGINEER.key
    front_ctl.py revoke HOME JOB --key ENGINEER.key
    front_ctl.py jobs   HOME
    front_ctl.py record HOME HASH --key ENGINEER.key --witness-key HEX --gate-key HEX --out RECORD.json

Everything here needs the engineer's key, and enrol also needs the certificate authority's key.  The assistant holds
neither.

enrol binds a job name to one baseline and issues the job's client certificate.  It writes DIR for the assistant's
side: the front door's address, the authority's certificate, and the job's certificate and key.  Nothing else is in
it: no database credential, no signing key, no copy of the check.  A job name is used once, and its certificate lasts
--days (90 unless given); renewing one is not built, so a job that outlives its certificate is enrolled again under a
new name, with a reason.

A job has one baseline in force.  rebind moves it, and only to a baseline that says it supersedes the one in force,
which means it was made with `verify_ctl.py revise`: the old budget is stopped first, the new card carries what was
run and what failed on the old one with the engineer's reason, and the new record is headed "changed after the
event".  A baseline that is merely different is refused.

enrol also refuses to open a second job for a requirement id that another job already holds under a different
baseline, unless the new baseline supersedes that one or the engineer gives --reason.  The reason is written into the
signed binding and the log.  This does not reach inside the record: the record's format is the first plug-in's,
unchanged, so a reader of one record sees a change of requirement only when it was made by revision.  The log
(HOME/front/enrolment.jsonl) is the service's own signed list of every binding, in order.

enrol and rebind also wait, for --wait seconds (15 unless given), until the gate's tool has shown that it can write a notice
to the inbox of the baseline the job is to be bound to, and refuse if it has not: a job is not opened on a baseline whose
failures might not reach its engineer (Amendment 8).  The gate shows it within a second or so of the baseline being made,
if it is running and its account can write the inbox.

revoke ends a job: its certificate is refused from the next request.

Amendment 17 (D16, after the third and fourth reviews).  rebind and revoke also put the new binding to the database's record
of bindings (through PLEA_CONTROL_DSN), where a job is named by what the engineer signs: the engineer's key and the job's name.
An entry of jobs.json for another job than the one named is refused (after the fifth review, N-H1).
No realm, file or setting is needed for that.  A revocation is recorded first if it can be, and is always written to
jobs.json unless the entry changed while it ran or the lock is held by another, which is said.  A job with no usable entry
(none, one not this engineer's, or one for another job) has its name revoked in the database, and the console ends with
status 4, saying nothing was written (after the sixth review, M-2).  If it was not recorded, the console says so and ends with status 3; revoke given again for that job records the
same revocation (it is not refused as already revoked), and the front door records it when it next reads the file (at its
start, and on its look every 30 seconds).  If it was recorded and could not be written, the console says so and ends with
status 4: the front door refuses the job already, and revoke given again writes it.  A move is written to jobs.json first,
then recorded; a failure to record it, or an answer other than CURRENT, is said, with status 3.  jobs.json is changed under
a lock (HOME/front/jobs.lock), so two consoles at once lose neither's binding; a write is refused if the job's entry changed
while the command ran, and a lock held by another for 30 seconds, or one that is not a plain file, is reported, not waited on.

record builds the verification record exactly as verify_ctl.py does, adding the front door's own journal of what was
sent, so a run interrupted before the gate wrote anything down can still be tied to its design.
"""
import argparse
import hashlib
import json
import os
import pathlib
import sys
import time

from cryptography import x509
from cryptography.hazmat.primitives import serialization

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from plea_gateway import tls as TLS                                   # noqa: E402
from baseline import BaselineInvalid, canonical, root_for             # noqa: E402  (canonical: Amendment 17)
from front_door import JOB_NAME, RESERVED, binding_message, binding_valid, jobs_path, read_jobs   # noqa: E402
from verify_record import Key, load_envelope, now                     # noqa: E402
import verify_ctl                                                     # noqa: E402
import notices                                                        # noqa: E402  (Amendment 8: the gate's inbox-writability check)


class Refused(Exception):
    pass


class Unrecorded(Exception):
    """The binding was written to jobs.json, and was not recorded in the database's record of bindings, or was answered other
    than expected (Amendment 17, after the third review, M-a and M-b).  Carries the binding."""
    def __init__(self, binding: dict, why: str):
        super().__init__(why); self.binding = binding


class Unwritten(Exception):
    """The revocation was recorded in the database, and could not be written to jobs.json (Amendment 17, after the fourth review,
    L6).  The front door refuses the job already.  Carries the binding."""
    def __init__(self, binding: dict, why: str):
        super().__init__(why); self.binding = binding


def _envelope(home, baseline_hash: str, key: Key) -> dict:
    try:
        env = load_envelope(pathlib.Path(home) / 'baselines' / baseline_hash / 'baseline.json', key.public_hex)
    except (OSError, ValueError, KeyError, TypeError, BaselineInvalid) as exc:
        raise Refused(f'no baseline {baseline_hash[:16]}… signed by this engineer is held: {exc}')
    if env['baseline_sha256'] != baseline_hash:
        raise Refused('the directory holds another baseline')
    return env


def _supersedes(home, env: dict, key: Key, target: str) -> bool:
    """True if this baseline replaced `target`, directly or through earlier revisions."""
    seen = set()
    while env is not None:
        sup = env['card'].get('supersedes')
        if not sup or sup['baseline_sha256'] in seen:
            return False
        if sup['baseline_sha256'] == target:
            return True
        seen.add(sup['baseline_sha256'])
        try:
            env = _envelope(home, sup['baseline_sha256'], key)
        except Refused:
            return False
    return False


def _deliverable(home, baseline_hash: str, wait: float) -> None:
    """Amendment 8 (D3).  Wait until the gate's tool has shown that it can write a notice to this baseline's inbox, and refuse if it
    has not within `wait` seconds.  With the console and the gate under two accounts, an inbox the gate cannot write is found
    here, before a job is opened, and not at the first failure."""
    deadline = time.time() + max(0.0, wait)
    while True:
        state, _ = notices.delivery_state(home, baseline_hash)
        if state == 'WRITABLE':
            return
        if time.time() >= deadline:
            break
        time.sleep(0.1)
    raise Refused(f'{notices.DELIVERY_WORDS[state]} ({baseline_hash[:16]}…), so a failure might not reach its engineer.  Start the gate if it is not '
                  f'running, make the inbox writable by the gate\'s account, and try again.  Nothing was changed.')


def _record(binding: dict, control_dsn) -> str:
    """Amendment 17 (after the second review, H1): put the binding to the database's record of bindings, so that a revocation
    is recorded whether or not the front door, or the revoked job, ever reads it.  The job is named there by its certificate's
    hash and its name, as the engineer signed them (after the fourth review, H1'').  Returns the record's answer."""
    import front_state
    from plea_gateway import Store
    return front_state.observe(Store(control_dsn), front_state.state_name(binding), binding['seq'],
                               hashlib.sha256(canonical(binding).encode()).hexdigest(), binding['event'] == 'REVOKE')


LOCK_WAIT = 30.0       # seconds the console waits for HOME/front/jobs.lock before it gives up and says so (fifth review, N-L1)


class Changed(OSError):
    """jobs.json's entry for the job is not the one this command started from: another console changed it meanwhile, or it was
    changed by hand.  Nothing is written (Amendment 17, after the fifth review, N-L2)."""


def _locked(home):
    """HOME/front/jobs.lock, opened without following a link, made if it is not there, and locked; a lock that is not a plain
    file, or one held by another for LOCK_WAIT seconds, raises OSError, which the command reports (after the fifth review,
    N-L1: it was opened by name and waited for without end)."""
    import fcntl
    import stat
    p = jobs_path(home).parent / 'jobs.lock'
    fd = os.open(p, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError(f'{p} is not a plain file')
        deadline = time.monotonic() + LOCK_WAIT
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return fd
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise OSError(f'{p} is held by another process; nothing was written') from None
                time.sleep(0.05)
    except BaseException:
        os.close(fd); raise


def _write(home, binding: dict, start) -> None:
    """The signed binding becomes the job's current one, and is added to the log.  The file is replaced whole, under a lock that
    every console takes (after the fourth review, L5: two at once could each read the file and the second's write lose the
    first's binding).  `start` is the job's entry this command started from (None for an enrolment); if the entry is not that
    one any more, nothing is written and Changed is raised (after the fifth review, N-L2)."""
    path = jobs_path(home); path.parent.mkdir(parents=True, exist_ok=True)
    fd = _locked(home)
    try:
        jobs = read_jobs(home)
        if jobs.get(binding['job']) != start:
            raise Changed(f'the entry of {binding["job"]} in jobs.json changed while this command ran; nothing was written to it')
        jobs[binding['job']] = binding
        log_fd = _plain(path.parent / 'enrolment.jsonl', os.O_WRONLY | os.O_APPEND | os.O_CREAT)   # looked at before anything is replaced
        try:
            import tempfile                              # a name of its own, made new (after the sixth review, M-3: jobs.tmp was opened by name)
            tfd, tname = tempfile.mkstemp(dir=path.parent, prefix='.jobs-', suffix='.tmp')
            try:
                with os.fdopen(tfd, 'w') as f:
                    f.write(json.dumps({'jobs': jobs}, indent=1) + '\n')
                os.replace(tname, path)                  # rename: a link at jobs.json is replaced, not followed
            except BaseException:
                try:
                    os.unlink(tname)
                except OSError:
                    pass
                raise
            os.write(log_fd, (json.dumps(binding) + '\n').encode())
        finally:
            os.close(log_fd)
    finally:
        os.close(fd)


def _plain(p, flags: int) -> int:
    """Open a file of HOME/front without following a link and without waiting on a pipe, and refuse one that is not a plain
    file (after the sixth review, M-3).  Returns the descriptor."""
    import stat
    fd = os.open(p, flags | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, 0o644)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd); raise OSError(f'{p} is not a plain file; nothing was written')
    return fd


def _signed(event: str, seq: int, job: str, env: dict, cert_sha256: str, previous, note, key: Key) -> dict:
    """A binding names the baseline by its hash and the budget by its name, both taken from the baseline the engineer
    signed, and carries a number that only goes up, so an earlier binding cannot stand in for a later one."""
    b = {'event': event, 'seq': seq, 'job': job, 'baseline_sha256': env['baseline_sha256'], 'root': root_for(env['card']), 'cert_sha256': cert_sha256,
         'previous': previous, 'time': now(), 'note': note}
    return dict(b, signer=key.public_hex, signature=key.sign(binding_message(b)))


def _current(home, job: str, key: Key) -> dict:
    b = read_jobs(home).get(job)
    if b is None:
        raise Refused(f'{job} is not enrolled')
    if not binding_valid(b, (key.public_hex,)):
        raise Refused(f'the stored binding of {job} is not signed by this engineer; it is not used')
    if b.get('job') != job:                              # after the fifth review (N-H1): an entry for another job is not this job's
        raise Refused(f'the stored binding of {job} is one signed for another job ({b.get("job")}); it is not used.  Nothing was changed.')
    return b


def enrol(home, job: str, baseline_hash: str, key: Key, ca_cert_pem: bytes, ca_key_pem: bytes, url: str, out, reason: str | None = None, days: int = 90,
          wait: float = 15.0) -> dict:
    """Bind a new job to a baseline, issue its certificate and write its folder.  Returns the signed binding."""
    if not isinstance(job, str) or not JOB_NAME.match(job) or job in RESERVED:
        raise Refused('a job name is 2 to 41 lower-case letters, digits or hyphens, and not a service\'s own name')
    if job in read_jobs(home):
        raise Refused(f'{job} is already enrolled; a job name is used once')
    env = _envelope(home, baseline_hash, key)
    rid = env['card']['requirement']['id']
    for other, b in sorted(read_jobs(home).items()):
        if b.get('baseline_sha256') == baseline_hash or not binding_valid(b, (key.public_hex,)):
            continue                                     # a revoked job still counts: its requirement was under that baseline
        try:
            held = _envelope(home, b['baseline_sha256'], key)
        except Refused:
            continue
        if held['card']['requirement']['id'] == rid and not _supersedes(home, env, key, b['baseline_sha256']) and not (reason and reason.strip()):
            raise Refused(f'{rid} is already under baseline {b["baseline_sha256"][:16]}… on job {other}.  A change to a requirement is a revision '
                          f'(verify_ctl.py revise, then front_ctl.py rebind).  To open a separate job on purpose, give a reason.')
    out = pathlib.Path(out)
    if out.exists() and any(out.iterdir()):
        raise Refused(f'{out} is not empty')
    _deliverable(home, baseline_hash, wait)              # Amendment 8 (D3): no job on a baseline whose failures might not reach its engineer
    key_pem, cert_pem = TLS.issue(ca_key_pem, ca_cert_pem, job, 'client', (), days)
    der = x509.load_pem_x509_certificate(cert_pem).public_bytes(serialization.Encoding.DER)
    binding = _signed('ENROL', 1, job, env, hashlib.sha256(der).hexdigest(), None, reason.strip() if reason and reason.strip() else None, key)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'ca.crt').write_bytes(ca_cert_pem); (out / 'job.crt').write_bytes(cert_pem)
    fd = os.open(out / 'job.key', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(key_pem)
    (out / 'job.json').write_text(json.dumps({'job': job, 'url': url.rstrip('/'), 'ca': 'ca.crt', 'cert': 'job.crt', 'key': 'job.key'}, indent=1) + '\n')
    _write(home, binding, None)
    return binding


def rebind(home, job: str, new_hash: str, key: Key, wait: float = 15.0, control_dsn: str = verify_ctl.CONTROL_DSN) -> dict:
    """Move a job to a revision of its baseline.  Refused unless the new baseline says it supersedes the one in force."""
    cur = _current(home, job, key)
    if cur['event'] == 'REVOKE':
        raise Refused(f'{job} was revoked')
    if new_hash == cur['baseline_sha256']:
        raise Refused(f'{job} is already bound to this baseline')
    env = _envelope(home, new_hash, key)
    sup = env['card'].get('supersedes') or {}
    if sup.get('baseline_sha256') != cur['baseline_sha256']:
        raise Refused(f'{job} is bound to {cur["baseline_sha256"][:16]}… and this baseline does not supersede it.  A job moves only to a revision of its '
                      f'own baseline (verify_ctl.py revise), so that the change and what had failed are on the record.')
    _deliverable(home, new_hash, wait)                   # Amendment 8 (D3): the same check is needed for the revision
    binding = _signed('REBIND', cur['seq'] + 1, job, env, cur['cert_sha256'], cur['baseline_sha256'], None, key)
    _write(home, binding, cur)                           # written first (after the third review, M-b): a failure after it loses nothing
    try:
        answer = _record(binding, control_dsn)
    except Exception as exc:
        raise Unrecorded(binding, f'the move is written to jobs.json and could not be recorded in the database ({type(exc).__name__}); the front door records '
                                  f'it when it reads the file') from None
    if answer != 'CURRENT':
        raise Unrecorded(binding, f'the move is written to jobs.json, and the database\'s record of bindings answers {answer}: the front door will refuse {job}')
    return binding


def revoke(home, job: str, key: Key, control_dsn: str = verify_ctl.CONTROL_DSN) -> dict:
    """Revoke a job.  Amendment 17: the revocation is recorded in the database if it can be, and is always written to jobs.json
    (after the third review, M-a: it was once refused when it could not be recorded, and so left a leaked job admitted).  If it
    was not recorded, Unrecorded is raised after the write.  A job whose binding in jobs.json is already its revocation has that
    revocation recorded again (after the fourth review, M1: it was refused as already revoked, so one that could not be recorded
    could never be).  If it was recorded and cannot be written, Unwritten is raised (after the fourth review, L6).

    With no usable entry for the job in jobs.json (none, one not signed by this engineer, or one signed for another job), the
    job's name is revoked in the database all the same, and Unwritten is raised: the record names a job by the engineer's key
    and its name, which the console knows without the entry (after the sixth review, M-2: such a job could not be revoked at
    all, and the entry put back was admitted).  A revocation neither recorded nor written raises Refused, saying the job is
    not revoked (after the sixth review, L-1)."""
    try:
        cur = _current(home, job, key)
    except Refused as no_entry:
        if not isinstance(job, str) or not JOB_NAME.match(job) or job in RESERVED:
            raise
        b = {'event': 'REVOKE', 'seq': 1, 'job': job, 'baseline_sha256': None, 'root': None, 'cert_sha256': None, 'previous': None, 'time': now(),
             'note': f'revoked by name: {no_entry}'}
        stmt = dict(b, signer=key.public_hex, signature=key.sign(binding_message(b)))
        try:
            answer = _record(stmt, control_dsn)
        except Exception as exc:
            raise Refused(f'{no_entry}  The job\'s name could not be revoked in the database either ({type(exc).__name__}): {job} is NOT revoked.') from None
        if answer != 'REVOKED':
            raise Refused(f'{no_entry}  The database\'s record of bindings answers {answer}: {job} is NOT revoked.')
        raise Unwritten(stmt, f'{no_entry}  The job\'s name is revoked in the database, so the front door refuses {job} under any binding of this '
                              f'engineer\'s; nothing was written to jobs.json.')
    if cur['event'] == 'REVOKE':
        try:
            answer = _record(cur, control_dsn)
        except Exception as exc:
            raise Unrecorded(cur, f'{job} is revoked in jobs.json, and the revocation could not be recorded in the database ({type(exc).__name__}); '
                                  f'the front door records it when it next reads the file') from None
        if answer != 'REVOKED':
            raise Unrecorded(cur, f'{job} is revoked in jobs.json, and the database\'s record of bindings answers {answer}')
        return cur
    b = {'event': 'REVOKE', 'seq': cur['seq'] + 1, 'job': job, 'baseline_sha256': cur['baseline_sha256'], 'root': cur['root'], 'cert_sha256': cur['cert_sha256'],
         'previous': cur['baseline_sha256'], 'time': now(), 'note': None}
    binding = dict(b, signer=key.public_hex, signature=key.sign(binding_message(b)))
    why = None
    try:
        answer = _record(binding, control_dsn)
        if answer != 'REVOKED':
            why = f'the database\'s record of bindings answers {answer}'
    except Exception as exc:
        why = f'it could not be recorded in the database ({type(exc).__name__})'
    try:
        _write(home, binding, cur)
    except OSError as exc:
        if why is None:
            raise Unwritten(binding, f'the revocation is recorded in the database, so the front door refuses {job}; it could not be written to jobs.json '
                                     f'({type(exc).__name__}): give revoke again to write it') from None
        raise Refused(f'{why}, and it could not be written to jobs.json ({exc}): {job} is NOT revoked; give revoke again') from None
    if why:
        raise Unrecorded(binding, f'{why}: the revocation is written to jobs.json; give revoke again to record it, and the front door records it when it next reads the file')
    return binding


def log(home) -> list:
    p = jobs_path(home).parent / 'enrolment.jsonl'
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def journal(home) -> pathlib.Path:
    return jobs_path(home).parent / 'submissions.jsonl'


def record(home, baseline_hash: str, key: Key, witness_key, gate_key, journals=(), checkpointer=None) -> dict:
    """The verification record, built as verify_ctl.record builds it, with the front door's journal among the candidates."""
    return verify_ctl.record(home, baseline_hash, key, witness_key, gate_key, [journal(home), *journals], checkpointer=checkpointer)


def main():
    ap = argparse.ArgumentParser(description='The responsible engineer\'s console for the front door.')
    ap.add_argument('action', choices=['enrol', 'rebind', 'revoke', 'jobs', 'record']); ap.add_argument('home'); ap.add_argument('rest', nargs='*')
    ap.add_argument('--key'); ap.add_argument('--ca'); ap.add_argument('--ca-key'); ap.add_argument('--url'); ap.add_argument('--out'); ap.add_argument('--reason')
    ap.add_argument('--days', type=int, default=90); ap.add_argument('--witness-key'); ap.add_argument('--gate-key')
    ap.add_argument('--witness-url', help='record: ask the witness for a checkpoint and put it in the record (Amendment 10)')
    ap.add_argument('--tls-ca'); ap.add_argument('--tls-cert'); ap.add_argument('--tls-key')
    ap.add_argument('--wait', type=float, default=15.0, help='seconds enrol and rebind wait for the gate to show it can write the inbox (Amendment 8)')
    a = ap.parse_args()
    try:
        if a.action == 'jobs':
            for job, b in sorted(read_jobs(a.home).items()):
                print(f"{job:<24} {b.get('event'):<7} {str(b.get('baseline_sha256'))[:16]}…  {b.get('time')}  signer {str(b.get('signer'))[:16]}…"   # signer: sixth review, L-3
                      + (f"  note: {b['note']}" if b.get('note') else ''))
            return
        key = verify_ctl.load_key(a.key)
        if a.action == 'enrol':
            b = enrol(a.home, a.rest[0], a.rest[1], key, pathlib.Path(a.ca).read_bytes(), pathlib.Path(a.ca_key).read_bytes(), a.url, a.out, a.reason, a.days, a.wait)
        elif a.action == 'rebind':
            b = rebind(a.home, a.rest[0], a.rest[1], key, a.wait)
        elif a.action == 'revoke':
            b = revoke(a.home, a.rest[0], key)
        else:
            rec = record(a.home, a.rest[0], key, a.witness_key, a.gate_key,
                         checkpointer=verify_ctl.witness_checkpointer(a.witness_url, a.tls_ca, a.tls_cert, a.tls_key) if a.witness_url else None)
            pathlib.Path(a.out).write_text(json.dumps(rec, indent=1) + '\n'); print(json.dumps({'record': a.out, 'attempts': len(rec['attempts']), 'as_of': rec['as_of']})); return
        print(json.dumps({k: b[k] for k in ('event', 'seq', 'job', 'baseline_sha256', 'root', 'previous', 'time', 'note')}))
    except Unrecorded as exc:                            # written, and not recorded (Amendment 17, after the third review)
        print(json.dumps({k: exc.binding[k] for k in ('event', 'seq', 'job', 'baseline_sha256', 'root', 'previous', 'time', 'note')}))
        print(f'written, not recorded: {exc}', file=sys.stderr); sys.exit(3)
    except Unwritten as exc:                             # recorded, and not written (Amendment 17, after the fourth review, L6)
        print(json.dumps({k: exc.binding.get(k) for k in ('event', 'seq', 'job', 'baseline_sha256', 'root', 'previous', 'time', 'note', 'signer')}))
        print(f'recorded, not written: {exc}', file=sys.stderr); sys.exit(4)
    except (Refused, BaselineInvalid, ValueError, OSError, IndexError, TypeError) as exc:
        print(f'refused: {exc}', file=sys.stderr); sys.exit(1)


if __name__ == '__main__':
    main()
