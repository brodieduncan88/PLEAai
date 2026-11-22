"""Shared set-up for review4 probes: in process only, database plea_rv4, no ports bound."""
import hashlib, json, os, pathlib, shutil, sys, uuid

R = pathlib.Path('/tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad/review4')
TREE = R / 'tree'
DB = 'plea_rv4'
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


def enrol(h, key, job, baseline='ab' * 32):
    """A signed ENROL binding with a made-up certificate, written as the console writes one."""
    der = os.urandom(64)
    b = {'event': 'ENROL', 'seq': 1, 'job': job, 'baseline_sha256': baseline, 'root': 'budget/' + baseline[:32],
         'cert_sha256': hashlib.sha256(der).hexdigest(), 'previous': None, 'time': now(), 'note': None}
    b = dict(b, signer=key.public_hex, signature=key.sign(front_door.binding_message(b)))
    front_ctl._write(h, b)
    return der, b


def front(h, key, realm):
    return front_door.Front(h, Store(LOCAL), {'realm': realm} if realm is not None else {}, [key.public_hex])


def admitted(fr, job, der):
    try:
        return fr.admit(job, der) is not None
    except front_state.StateUnavailable as exc:
        return f'StateUnavailable({exc})'


def rows(prefix_job):
    with Store(OWNER).connect() as c:
        return [tuple(r) for r in c.execute("SELECT job, seq, revoked FROM public.verify_front_binding WHERE job LIKE %s ORDER BY job", ('%:' + prefix_job,)).fetchall()]
