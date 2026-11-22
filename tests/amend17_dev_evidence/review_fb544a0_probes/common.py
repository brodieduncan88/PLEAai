"""Shared set-up for review7 probes (of fb544a0): in process only, database plea_rv7, no ports bound, no suite run."""
import hashlib, json, os, pathlib, shutil, sys, uuid

R = pathlib.Path('/tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad/review7')
TREE = R / 'tree'
DB = 'plea_rv7'
OWNER = f'postgresql://plea:plea@127.0.0.1:5432/{DB}'
LOCAL = f'postgresql://plea_local:local@127.0.0.1:5432/{DB}'
CONTROL = f'postgresql://plea_control:control@127.0.0.1:5432/{DB}'
BAD = f'postgresql://plea_control:control@127.0.0.1:1/{DB}'
os.environ['PLEA_CONTROL_DSN'] = CONTROL; os.environ['PLEA_LOCAL_DSN'] = LOCAL; os.environ['PLEA_ADMIN_DSN'] = OWNER
sys.path[:0] = [str(TREE / 'verify'), str(TREE)]

from plea_gateway import Store            # noqa: E402
import front_state, front_door, front_ctl  # noqa: E402
from verify_record import Key, now         # noqa: E402

assert front_ctl.verify_ctl.CONTROL_DSN == CONTROL, front_ctl.verify_ctl.CONTROL_DSN


def home(tag):
    h = R / 'homes' / f'{tag}-{uuid.uuid4().hex[:6]}'
    (h / 'front').mkdir(parents=True)
    return h


def signed(key, **fields):
    b = {'event': 'ENROL', 'seq': 1, 'job': None, 'baseline_sha256': 'ab' * 32, 'root': 'budget/' + 'ab' * 16,
         'cert_sha256': None, 'previous': None, 'time': now(), 'note': None}
    b.update(fields)
    return dict(b, signer=key.public_hex, signature=key.sign(front_door.binding_message(b)))


def enrol(h, key, job, baseline='ab' * 32):
    """A signed ENROL binding with a made-up certificate, written as the console's enrol writes it (its last step, _write(.., None)).
    The console's enrol refuses a name only if jobs.json holds it (front_ctl.py:219), which this mirrors."""
    if job in front_door.read_jobs(h):
        raise front_ctl.Refused('already enrolled')
    der = os.urandom(64)
    b = signed(key, job=job, baseline_sha256=baseline, root='budget/' + baseline[:32], cert_sha256=hashlib.sha256(der).hexdigest())
    front_ctl._write(h, b, None)
    return der, b


def put(h, job, b):
    """The adversary (a writer of HOME/front) sets jobs.json's entry for `job` to `b` (None deletes it)."""
    p = front_door.jobs_path(h)
    jobs = json.loads(p.read_text())['jobs'] if p.exists() else {}
    if b is None:
        jobs.pop(job, None)
    else:
        jobs[job] = b
    p.write_text(json.dumps({'jobs': jobs}, indent=1) + '\n')


def front(h, *keys):
    return front_door.Front(h, Store(LOCAL), {}, list(keys))


def admitted(fr, job, der):
    try:
        return fr.admit(job, der) is not None
    except front_state.StateUnavailable as exc:
        return f'StateUnavailable({exc})'
    except Exception as exc:
        return f'{type(exc).__name__}({exc})'


def attempt(fn):
    try:
        r = fn(); return ('ok', r.get('event') if isinstance(r, dict) else r)
    except Exception as exc:
        return (type(exc).__name__, str(exc)[:160])


def row_named(name):
    with Store(OWNER).connect() as c:
        r = c.execute('SELECT seq, revoked FROM public.verify_front_binding WHERE job = %s', (name,)).fetchone()
        return tuple(r) if r else None


def row(b):
    return row_named(front_state.state_name(b))


def jobs_raw(h):
    p = front_door.jobs_path(h)
    return p.read_text() if p.exists() else None


class Exits(Exception):
    pass


def cli(h, keyfile, *args, timeout=60, env=None):
    import subprocess
    e = dict(os.environ); e.update(env or {})
    try:
        r = subprocess.run([sys.executable, '-B', str(TREE / 'verify' / 'front_ctl.py'), *args[:1], str(h), *args[1:], '--key', str(keyfile)],
                           capture_output=True, text=True, timeout=timeout, env=e)
        return (r.returncode, r.stdout.strip()[-400:], r.stderr.strip()[-500:])
    except subprocess.TimeoutExpired:
        return ('TIMEOUT', '', '')


def keyfile(key, tag):
    """Write an engineer key file in the form verify_ctl.load_key reads."""
    p = R / 'keys' / f'{tag}-{uuid.uuid4().hex[:6]}.key'; p.parent.mkdir(exist_ok=True)
    p.write_text(key.private_hex + '\n'); p.chmod(0o600)
    return p
