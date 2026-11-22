"""P1 (review A2). Expectation written before the run: if a REVOKE written to jobs.json is never seen by admit()
(the revoked job does not call; the sweep runs), and the earlier signed binding is then put back, admit() admits again.
PREDICTION: sweep leaves the DB row unrevoked; put-back ENROL -> admitted (binding returned).
P1b: CA file re-encoded (one trailing newline) -> a new realm -> after an OBSERVED revocation, the put-back binding admits.
PREDICTION: admitted.
P1c: a REVOKE with the same seq as the binding already seen -> CONFLICT (refused) and not recorded; put back -> admitted.
PREDICTION: admitted."""
import sys, json, hashlib, pathlib, tempfile
W = sys.argv[1]; sys.path.insert(0, W); sys.path.insert(0, W + '/verify')
from plea_gateway import Store
import front_door, front_state
from verify_record import Key
from baseline import canonical
DSN = 'postgresql://plea_local:local@127.0.0.1:5432/plea_rv2'
eng = Key()
home = pathlib.Path(tempfile.mkdtemp(dir=sys.argv[2])); (home / 'front').mkdir()
ca = home / 'ca.crt'; ca.write_bytes(b'-----BEGIN CERTIFICATE-----\nFAKE' + home.name.encode() + b'\n-----END CERTIFICATE-----\n')
der = b'job-cert-der'; h = hashlib.sha256(b'baseline').hexdigest()
def signed(event, seq, job):
    b = {'event': event, 'seq': seq, 'job': job, 'baseline_sha256': h, 'root': f'REQ-1/A/{h[:32]}', 'cert_sha256': hashlib.sha256(der).hexdigest(),
         'previous': None, 'time': '2026-11-22T00:00:00Z', 'note': None}
    return dict(b, signer=eng.public_hex, signature=eng.sign(front_door.binding_message(b)))
def put(job, b):
    p = front_door.jobs_path(home); jobs = front_door.read_jobs(home); jobs[job] = b; p.write_text(json.dumps({'jobs': jobs}))
def front():
    return front_door.Front(home, Store(DSN), {'tls': {'ca': str(ca)}, 'journal': str(home / 'j.jsonl')}, (eng.public_hex,))
out = {}
# P1
f = front(); enrol = signed('ENROL', 1, 'job-p1'); put('job-p1', enrol)
out['p1_admit_enrol'] = f.admit('job-p1', der) is not None
put('job-p1', signed('REVOKE', 2, 'job-p1'))
out['p1_sweep'] = f.sweep()
f = front()                                    # a restart
out['p1_revoked_refused_if_asked_now'] = None   # not asked: the revoked job does not call
put('job-p1', enrol)
out['p1_put_back_admitted'] = front().admit('job-p1', der) is not None
# P1b
f = front(); e2 = signed('ENROL', 1, 'job-p1b'); put('job-p1b', e2); out['p1b_admit'] = f.admit('job-p1b', der) is not None
put('job-p1b', signed('REVOKE', 2, 'job-p1b')); out['p1b_revoked_seen'] = f.admit('job-p1b', der) is None
ca.write_bytes(ca.read_bytes() + b'\n')        # the same certificate, re-encoded
put('job-p1b', e2); out['p1b_put_back_after_ca_reencoded_admitted'] = front().admit('job-p1b', der) is not None
# P1c
f = front(); e3 = signed('ENROL', 1, 'job-p1c'); put('job-p1c', e3); out['p1c_admit'] = f.admit('job-p1c', der) is not None
put('job-p1c', signed('REVOKE', 1, 'job-p1c')); out['p1c_revoke_same_seq_refused'] = f.admit('job-p1c', der) is None
put('job-p1c', e3); out['p1c_put_back_admitted'] = front().admit('job-p1c', der) is not None
print(json.dumps(out, indent=1))
