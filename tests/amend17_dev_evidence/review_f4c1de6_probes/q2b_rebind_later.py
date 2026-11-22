"""Q2b. See q2_CHANGE.txt for the expectation (written before this ran)."""
import sys, json, hashlib, pathlib, tempfile
W = sys.argv[1]; sys.path.insert(0, W); sys.path.insert(0, W + '/verify')
from plea_gateway import Store
import front_door, front_state, front_ctl
from verify_record import Key
LOCAL = 'postgresql://plea_local:local@127.0.0.1:5432/plea_rv3'; CTL = 'postgresql://plea_control:control@127.0.0.1:5432/plea_rv3'
eng = Key(); der = b'job-cert-der'; h = hashlib.sha256(b'baseline').hexdigest(); h2 = hashlib.sha256(b'baseline-rev').hexdigest()
home = pathlib.Path(tempfile.mkdtemp(dir=sys.argv[2])); (home / 'front').mkdir()
b = {'event': 'ENROL', 'seq': 1, 'job': 'job-q2b', 'baseline_sha256': h, 'root': f'REQ-1/A/{h[:32]}', 'cert_sha256': hashlib.sha256(der).hexdigest(),
     'previous': None, 'time': '2026-11-22T00:00:00Z', 'note': None}
front_ctl._write(home, dict(b, signer=eng.public_hex, signature=eng.sign(front_door.binding_message(b))))
f = front_door.Front(home, Store(LOCAL), {'tls': {}, 'journal': str(home / 'j.jsonl'), 'realm': 'realm-one-1'}, (eng.public_hex,))
out = {'first': f.admit('job-q2b', der) is not None}
front_ctl._envelope = lambda home, nh, key: {'baseline_sha256': nh, 'card': {'supersedes': {'baseline_sha256': h}}}
front_ctl._deliverable = lambda home, nh, wait: None
front_ctl.root_for = lambda card: f'REQ-1/B/{h2[:32]}'
real_write = front_ctl._write
front_ctl._write = lambda home, b: (_ for _ in ()).throw(OSError(28, 'No space left on device'))
try: front_ctl.rebind(home, 'job-q2b', h2, eng, realm='realm-one-1', control_dsn=CTL); out['rebind1'] = 'ok'
except Exception as exc: out['rebind1'] = repr(exc)
front_ctl._write = real_write
out['after_fail_admitted'] = f.admit('job-q2b', der) is not None
for i, k in enumerate(('retry_later', 'retry_later2')):
    front_ctl.now = (lambda t: (lambda: t))(f'2026-11-22T0{i+1}:00:00Z')
    try: front_ctl.rebind(home, 'job-q2b', h2, eng, realm='realm-one-1', control_dsn=CTL); out[k] = 'ok'
    except Exception as exc: out[k] = repr(exc)
out['jobs_seq'] = front_door.read_jobs(home)['job-q2b']['seq']
try: front_ctl.revoke(home, 'job-q2b', eng, realm='realm-one-1', control_dsn=CTL); out['revoke'] = 'ok'
except Exception as exc: out['revoke'] = repr(exc)
out['after_revoke_admitted'] = f.admit('job-q2b', der) is not None
print(json.dumps(out, indent=1))
