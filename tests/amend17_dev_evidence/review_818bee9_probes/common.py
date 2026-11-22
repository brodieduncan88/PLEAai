"""Shared set-up for review5 probes (of 818bee9): in process only, database plea_rv5, no ports bound, no suite run."""
import hashlib, json, os, pathlib, shutil, sys, uuid

R = pathlib.Path('/tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad/review5')
TREE = R / 'tree'
DB = 'plea_rv5'
OWNER = f'postgresql://plea:plea@127.0.0.1:5432/{DB}'
LOCAL = f'postgresql://plea_local:local@127.0.0.1:5432/{DB}'
CONTROL = f'postgresql://plea_control:control@127.0.0.1:5432/{DB}'
BAD = f'postgresql://plea_control:control@127.0.0.1:1/{DB}'
os.environ['PLEA_CONTROL_DSN'] = CONTROL; os.environ['PLEA_LOCAL_DSN'] = LOCAL; os.environ['PLEA_ADMIN_DSN'] = OWNER
sys.path[:0] = [str(TREE / 'verify'), str(TREE)]

from plea_gateway import Store            # noqa: E402
import front_state, front_door, front_ctl  # noqa: E402
from verify_record import Key, now         # noqa: E402

assert front_ctl.verify_ctl.CONTROL_DSN == CONTROL


def home(tag):
    h = R / 'homes' / f'{tag}-{uuid.uuid4().hex[:6]}'
    if h.exists():
        shutil.rmtree(h)
    (h / 'front').mkdir(parents=True)
    return h


def signed(key, **fields):
    b = {'event': 'ENROL', 'seq': 1, 'job': None, 'baseline_sha256': 'ab' * 32, 'root': 'budget/' + 'ab' * 16,
         'cert_sha256': None, 'previous': None, 'time': now(), 'note': None}
    b.update(fields)
    return dict(b, signer=key.public_hex, signature=key.sign(front_door.binding_message(b)))


def enrol(h, key, job, baseline='ab' * 32, write=True):
    """A signed ENROL binding with a made-up certificate, written as the console's enrol writes one (its last step, _write)."""
    der = os.urandom(64)
    b = signed(key, job=job, baseline_sha256=baseline, root='budget/' + baseline[:32], cert_sha256=hashlib.sha256(der).hexdigest())
    if write:
        front_ctl._write(h, b)
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


def front(h, key):
    return front_door.Front(h, Store(LOCAL), {}, [key.public_hex])


def admitted(fr, job, der):
    try:
        return fr.admit(job, der) is not None
    except front_state.StateUnavailable as exc:
        return f'StateUnavailable({exc})'
    except Exception as exc:
        return f'{type(exc).__name__}({exc})'


def row(b):
    with Store(OWNER).connect() as c:
        r = c.execute('SELECT seq, revoked FROM public.verify_front_binding WHERE job = %s', (front_state.state_name(b),)).fetchone()
        return tuple(r) if r else None


def rows_for(job):
    with Store(OWNER).connect() as c:
        return [tuple(r) for r in c.execute("SELECT job, seq, revoked FROM public.verify_front_binding WHERE job LIKE %s ORDER BY job", ('%:' + job,)).fetchall()]
