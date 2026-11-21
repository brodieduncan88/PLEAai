"""REVIEWER COPY (phase 1): only change is VT.OUT redirected out of the pinned source.
Shared setup for the design-gate diagnostics of 21 November 2026 (Amendment 16).  Development evidence only: no code
of e25a297 is changed, nothing here is proposed code, and the predicates are this harness's own.

    DIAG_DB=<fresh database> python <script>.py SRC OUT
"""
import copy, json, os, pathlib, sys, time, urllib.error, urllib.parse, urllib.request

SRC, OUT = sys.argv[1], pathlib.Path(sys.argv[2]); DB = os.environ['DIAG_DB']
for role, pw, var in (('plea_local', 'local', 'PLEA_LOCAL_DSN'), ('plea_witness', 'witness', 'PLEA_WITNESS_DSN'), ('plea_control', 'control', 'PLEA_CONTROL_DSN')):
    os.environ[var] = f'postgresql://{role}:{pw}@127.0.0.1:5432/{DB}'
sys.path[:0] = [SRC + '/tests', SRC, SRC + '/verify']
import verify_tests as VT                                   # noqa: E402
VT.OUT = OUT / 'deploy'                                     # review: never write under the pinned source
import check_record as C                                    # noqa: E402
import verify_client                                        # noqa: E402
from plea_gateway import Store, tls as TLS                  # noqa: E402

LOG = {'when': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'database': DB, 'source': SRC, 'steps': []}


def stamp():
    return time.strftime('%H:%M:%SZ', time.gmtime())


def note(name, **kw):
    LOG['steps'].append(dict(step=name, at=stamp(), **kw)); print(f'--- {name}  [{stamp()}]')
    for k, v in kw.items():
        print(f'    {k}: {json.dumps(v, default=str)[:1500]}')
    sys.stdout.flush()


def save(name):
    LOG['finished'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    (OUT / name).write_text(json.dumps(LOG, indent=1, default=str) + '\n')


class Bench:
    """One deployment (witness, gate host, mailbox) and the calls a diagnostic makes to it."""

    def __init__(self, tag, crash_at=None):
        self.r = VT.Run(tag, crash_at=crash_at) if crash_at else VT.Run(tag); self.s = self.r.s
        self.root = VT.B.root_for(self.r.env['card']); self.local = Store(os.environ['PLEA_LOCAL_DSN'])
        self.url = f"https://127.0.0.1:{self.s.ports['witness']}"; self.q = urllib.parse.quote(self.root, safe='')
        self.gov, self.cour, self.keeper = self.s.pki['governor'], self.s.pki['courier'], self.s.pki['keeper']
        self.GATE = self.s.keys['gate']; self.WIT = self.s.keys['witness']

    def call(self, path, cert, method='GET', body=None, base=None, timeout=70):
        ctx = TLS.TLSClient(self.s.pki['ca'], *cert).context()
        req = urllib.request.Request((base or self.url) + path, data=None if body is None else json.dumps(body).encode(), method=method, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return resp.status, json.loads(resp.read() or b'null')
        except urllib.error.HTTPError as exc:
            try:
                return exc.code, json.loads(exc.read() or b'null')
            except ValueError:
                return exc.code, None

    def attempts(self):
        with self.local.connect() as conn:
            return [dict(aid=a, phase=p, nonce=n) for a, p, n in conn.execute('SELECT aid, phase, nonce FROM attempts WHERE root_id = %s', (self.root,)).fetchall()]

    def phase(self, aid):
        return next((a['phase'] for a in self.attempts() if a['aid'] == aid), None)

    def newest(self, before):
        new = [a for a in self.attempts() if a['aid'] not in {b['aid'] for b in before}]; assert len(new) == 1, new; return new[0]

    def chain(self, after=0):
        rows = []
        while True:
            st, page = self.call(f'/chain?root={self.q}&after={after}&limit=200', self.cour); got = page['rows']
            if not got:
                return rows
            rows += got; after = got[-1]['seq']

    def run_reading(self, aid):
        return self.call(f'/run?root={self.q}&aid={urllib.parse.quote(aid, safe="")}', self.cour)

    def accept(self, op, evidence=None):
        body = {'root': self.root, 'op': list(op)}
        if evidence is not None:
            body['evidence'] = evidence
        st, ans = self.call('/accept', self.gov, 'POST', body)
        return {'status': st, 'kind': (ans or {}).get('kind'), 'code': (ans or {}).get('code'), 'seq': (ans or {}).get('seq'), 'applied': (ans or {}).get('applied'), 'error': (ans or {}).get('error')}

    def report(self, aid, nonce, claim, result):
        return self.s.gate.effect_report(self.root, aid, nonce, claim, result).to_json()

    def authentic(self, e, aid, nonce):
        return bool(isinstance(e, dict) and e.get('kind') == 'EFFECT_REPORT' and e.get('signer') == self.GATE and C.signed_by(self.GATE, e.get('signature', ''), C.evidence_message(e))
                    and (e.get('root'), e.get('aid'), e.get('nonce')) == (self.root, aid, nonce))

    def synthetic(self, name, upto='CONSUMED'):
        """An attempt taken, with the service's own credentials and no tool run, to a phase before its verdict.  The gate
        host is not asked.  Returns the attempt and each decision's answer."""
        aid = name; nonce = 'n-' + name; steps = []
        d, _ = self.local.apply(self.root, ('RESERVE', aid, 'key-' + name)); steps.append(('RESERVE', d.kind, d.code))
        if upto == 'RESERVING':
            return dict(aid=aid, nonce=nonce), steps
        a = self.accept(('ACCEPT_RESERVATION', aid)); steps.append(('ACCEPT_RESERVATION', a['kind'], a['code']))
        if upto == 'RESERVED':
            return dict(aid=aid, nonce=nonce), steps
        d, _ = self.local.apply(self.root, ('TOKEN', aid)); steps.append(('TOKEN', d.kind, d.code))
        if upto == 'TOKEN':
            return dict(aid=aid, nonce=nonce), steps
        d, _ = self.local.apply(self.root, ('START', aid, nonce)); steps.append(('START', d.kind, d.code))
        if upto == 'INTENT_PENDING':
            return dict(aid=aid, nonce=nonce), steps
        a = self.accept(('ACCEPT_INTENT', aid)); steps.append(('ACCEPT_INTENT', a['kind'], a['code']))
        return dict(aid=aid, nonce=nonce), steps

    def reports_of(self, a):
        """The reports the witness's reading gives for a run, as the courier is given them."""
        st, ans = self.run_reading(a['aid']); out = []
        for item in (ans or {}).get('evidence') or []:
            e = item['evidence']
            out.append({'seq': item['seq'], 'kind': e.get('kind') if isinstance(e, dict) else type(e).__name__, 'claim': e.get('claim') if isinstance(e, dict) else None,
                        'digest': ((e.get('result_digest') or '')[:16]) if isinstance(e, dict) else None, 'authentic': self.authentic(e, a['aid'], a['nonce']), 'derived': item.get('derived')})
        return st, ans, out

    def stop(self):
        self.r.stop()


def verdict_pairs(reports):
    """The set D of the Step 2 note, section 6 step 3: distinct (claim, digest) among authentic reports that claim a verdict."""
    return sorted({(x['claim'], x['digest']) for x in reports if x['authentic'] and x['claim'] in ('EFFECT', 'NO_EFFECT')})
