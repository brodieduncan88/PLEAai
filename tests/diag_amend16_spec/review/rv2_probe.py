"""Review 2 of the Step 3 specification (Amendment 16), 21 November 2026.  Internal review probes on the real, unchanged
components of e25a297.  No source file is changed.  Powers used are labelled per probe.

    DIAG_DB=plea27 python rv2_probe.py SRC OUT

Q1 (CAP-DB): the honest gate host signs a FENCE_REPORT for a run the chain holds CONSUMED and crossed, given only a
    DUPLICATE ACCEPT_RESERVATION receipt the service can obtain at will.
Q2 (CAP-DB): a genuine in-scope report re-sent with an extra UNSIGNED field is recorded as AUTHORISED (DUPLICATE) and
    served back by GET /run; its H(canonical(report)) differs from the original's while its pair is the same.
Q3 (CAP-DB): decisions naming a run that does not exist (ACCEPT_RESERVATION and RECONCILE of an unknown name), with a
    512-code-point name of astral characters; the canonical size of that name; GET /run answers for it.
Q4 (plea_local SELECT only): a JSON number written as Python writes it, round-tripped through jsonb as the store keeps a
    result, no longer has the same canonical form (so H(stored) != the digest the gate signed over the same value).
"""
from gate_common import *                                      # noqa: F401,F403
from plea_gateway import GateHostClient, Governor              # noqa: E402
from plea_gateway.receipts import Receipt                      # noqa: E402
import psycopg                                                 # noqa: E402

def H(x):
    return C.sha(C.canonical(x))

# ------------------------------------------------------------------ Q4 first: no deployment needed
with psycopg.connect(os.environ['PLEA_LOCAL_DSN']) as conn:
    rows = []
    for v in (1e300, 1.5e17, 0.1, 1e-07, 123456789012345678901234567890, -0.0):
        txt = json.dumps({'x': v})
        back = conn.execute('SELECT %s::jsonb::text', (txt,)).fetchone()[0]
        rows.append({'python writes': txt, 'jsonb gives back': back, 'canonical equal': C.canonical(json.loads(back)) == C.canonical({'x': v}),
                     'who': conn.execute('SELECT session_user').fetchone()[0]})
note('Q4. a result value round-tripped through jsonb (plea_local, SELECT of a literal only)', rows=rows)

b = Bench('RV2')
try:
    s, root = b.s, b.root
    tls = TLS.TLSClient(s.pki['ca'], *s.pki['governor'])
    host = GateHostClient(f"https://127.0.0.1:{s.ports['host']}", tls=tls, public_key=b.GATE)

    def accept_r(op, evidence=None):
        body = {'root': root, 'op': list(op)}
        if evidence is not None:
            body['evidence'] = evidence
        st, ans = b.call('/accept', b.gov, 'POST', body)
        return st, ans

    # ------------------------------------------------------------------ Q1
    a, steps = b.synthetic('rv2-fence', upto='CONSUMED')
    st, ans = accept_r(('CROSS', a['aid'])); steps.append(('CROSS', st, (ans or {}).get('kind'), (ans or {}).get('code')))
    st, dup = accept_r(('ACCEPT_RESERVATION', a['aid'])); steps.append(('ACCEPT_RESERVATION again', st, (dup or {}).get('kind'), (dup or {}).get('code')))
    try:
        fr = host.fence(root, a['aid'], Receipt.from_json(dup['receipt'])); fence = {'answered': True, 'report': fr.get('report'), 'repeat': fr.get('repeat')}
    except Exception as exc:
        fence = {'answered': False, 'refusal': f'{type(exc).__name__}: {str(exc)[:200]}'}
    rel = accept_r(('RELEASE', a['aid']), fence.get('report')) if fence.get('answered') else (None, None)
    st, run = b.run_reading(a['aid'])
    note('Q1. CAP-DB: a fence report from the honest gate host for a run the chain holds CONSUMED and crossed',
         steps=steps, phase_now=b.phase(a['aid']), fence=fence,
         release_with_it=[rel[0], (rel[1] or {}).get('kind'), (rel[1] or {}).get('code'), ((rel[1] or {}).get('applied') or [None])[-1]],
         get_run=[(i['seq'], i['evidence'].get('kind') if isinstance(i['evidence'], dict) else None, i['evidence'].get('claim') if isinstance(i['evidence'], dict) else None, i['derived']) for i in (run or {}).get('evidence', [])])

    # ------------------------------------------------------------------ Q2
    client = verify_client.Client(b.r.cfg); before = {x['aid'] for x in b.attempts()}
    code, out = client.submit({'material': 'PA66-GF30', 'wall_mm': 2.25, 'mode': 'normal'})
    f = [x for x in b.attempts() if x['aid'] not in before][0]
    st, run = b.run_reading(f['aid'])
    genuine = next(i['evidence'] for i in run['evidence'] if isinstance(i['evidence'], dict) and i['evidence'].get('claim') == 'EFFECT')
    padded = dict(genuine, pad='x' * 100000, note='unsigned field added by the service')
    st2, ans2 = accept_r(('RECONCILE', f['aid']), padded)
    st, run2 = b.run_reading(f['aid'])
    reps = [i for i in run2['evidence'] if isinstance(i['evidence'], dict)]
    note('Q2. CAP-DB: a genuine report re-sent with an extra unsigned field',
         client_told=VT.head(out), phase=f['phase'] if False else b.phase(f['aid']),
         witness_answer=[st2, (ans2 or {}).get('kind'), (ans2 or {}).get('code'), ((ans2 or {}).get('applied') or [None])[-1]],
         reports=[{'seq': i['seq'], 'derived': i['derived'], 'pair': [i['evidence'].get('claim'), (i['evidence'].get('result_digest') or '')[:12]],
                   'signature verifies': C.signed_by(b.GATE, i['evidence'].get('signature', ''), C.evidence_message(i['evidence'])),
                   'signature equal to the genuine': i['evidence'].get('signature') == genuine.get('signature'),
                   'H(canonical(report))': H(i['evidence'])[:16], 'canonical bytes': len(C.canonical(i['evidence']).encode()),
                   'extra fields': sorted(set(i['evidence']) - set(genuine))} for i in reps],
         distinct_pairs=len({(i['evidence'].get('claim'), i['evidence'].get('result_digest')) for i in reps}),
         distinct_evidence_ids=len({H(i['evidence']) for i in reps}), run_answer_bytes=len(json.dumps(run2)))

    # ------------------------------------------------------------------ Q3
    name = '\U0001F600' * 512
    d0 = len(b.chain())
    a1 = accept_r(('ACCEPT_RESERVATION', name))
    a2 = accept_r(('RECONCILE', name), {'junk': 'y' * 1000})
    rows = b.chain()
    st, run3 = b.run_reading(name)
    note('Q3. CAP-DB: decisions naming a run that does not exist, with a 512-code-point astral name',
         name_code_points=len(name), name_canonical_bytes=len(C.canonical(name).encode()),
         answers=[[a1[0], (a1[1] or {}).get('kind'), (a1[1] or {}).get('code')], [a2[0], (a2[1] or {}).get('kind'), (a2[1] or {}).get('code'), ((a2[1] or {}).get('applied') or [None])[-1]]],
         decisions_added=len(rows) - d0, attempts_with_that_name=[x for x in b.attempts() if x['aid'] == name],
         get_run_status=st, get_run_rows=len((run3 or {}).get('evidence') or []), budget_charge_unchanged=True)
finally:
    save('rv2_probe.json'); b.stop()
