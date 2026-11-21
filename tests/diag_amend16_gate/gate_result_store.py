"""Design gate, part E (21 November 2026): can the service's database role change or remove a run's stored result after
it is stored, and does storing one leave a decision in the chain?  Direct calls with the role's own password; no service
is started and no code is changed.   python gate_result_store.py SRC OUT DATABASE"""
import json, pathlib, sys, time
SRC, OUT, DB = sys.argv[1], pathlib.Path(sys.argv[2]), sys.argv[3]
sys.path[:0] = [SRC]
import psycopg
from plea_gateway import Store
local = Store(f'postgresql://plea_local:local@127.0.0.1:5432/{DB}')
LOG = {'when': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'database': DB, 'steps': []}
def first(exc): return f'{type(exc).__name__}: {str(exc).splitlines()[0][:170]}'
def q(sql, params=(), role='plea_local', pw='local'):
    try:
        with psycopg.connect(f'postgresql://{role}:{pw}@127.0.0.1:5432/{DB}') as conn:
            cur = conn.execute(sql, params); out = cur.fetchall() if cur.description else cur.rowcount; conn.commit(); return out
    except Exception as exc:
        return 'REFUSED: ' + first(exc)
rows = q("SELECT a.root_id, a.aid, a.phase, r.result->>'outcome', (SELECT max(seq) FROM decisions d WHERE d.root_id = a.root_id) FROM attempts a LEFT JOIN results r ON r.root_id = a.root_id AND r.aid = a.aid WHERE a.phase IN ('EFFECT','CONSUMED') AND a.crossed ORDER BY a.root_id, a.aid")
pick = lambda phase, outcome: next(((r, a, s) for r, a, p, o, s in rows if p == phase and o == outcome), None)
def stored(root, aid):
    got = local.get_result(root, aid); return None if got is None else {'outcome': got.get('outcome'), 'verdict': (got.get('value') or {}).get('verdict') if isinstance(got.get('value'), dict) else None, 'marker': got.get('marker')}
def put(root, aid, result):
    try:
        local.put_result(root, aid, result); return 'accepted'
    except Exception as exc:
        return 'REFUSED: ' + first(exc)
def seq(root): return q('SELECT max(seq) FROM decisions WHERE root_id = %s', (root,))[0][0]
for label, phase, outcome in (('a final run whose result is stored as a value', 'EFFECT', 'value'), ('a run whose stored outcome is "unknown"', 'CONSUMED', 'unknown'), ('a final run with no stored result', 'EFFECT', None)):
    got = pick(phase, outcome)
    if not got:
        LOG['steps'].append({'case': label, 'found': False}); print('---', label, ': no such run in this database'); continue
    root, aid, s0 = got; step = {'case': label, 'run': aid[:14], 'before': stored(root, aid), 'decisions before': seq(root)}
    step['store a different value (marker 1)'] = put(root, aid, {'outcome': 'value', 'value': {'verdict': 'PASS'}, 'marker': 1}); step['after 1'] = stored(root, aid)
    step['store another value (marker 2)'] = put(root, aid, {'outcome': 'value', 'value': {'verdict': 'FAIL'}, 'marker': 2}); step['after 2'] = stored(root, aid)
    step['store "unknown" over it (marker 3)'] = put(root, aid, {'outcome': 'unknown', 'marker': 3}); step['after 3'] = stored(root, aid)
    step['DELETE the row, as the service role'] = q('DELETE FROM results WHERE root_id = %s AND aid = %s', (root, aid)); step['UPDATE the row, as the service role'] = q("UPDATE results SET result = '{}' WHERE root_id = %s AND aid = %s", (root, aid))
    step['decisions after'] = seq(root); step['storing a result added a decision to the chain'] = step['decisions after'] != step['decisions before']
    LOG['steps'].append(step); print('---', label); [print('   ', k, ':', json.dumps(v)) for k, v in step.items() if k != 'case']
(OUT / 'gate_result_store.json').write_text(json.dumps(LOG, indent=1) + '\n')
