"""Design gate, part F (21 November 2026): every report row in the store against the chain, read with the SERVICE's own
database role (plea_local) and no other.  Parts C4 and C8 read the same table with the owner's password, which is
outside the service's stated powers; this repeats the check without it, over every budget of the databases named.
Reads only.  No service is started.   python gate_rows_as_service.py OUT DATABASE [DATABASE ...]"""
import json, pathlib, sys, time
import psycopg
OUT = pathlib.Path(sys.argv[1]); LOG = {'when': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'role': 'plea_local', 'databases': {}}
for db in sys.argv[2:]:
    with psycopg.connect(f'postgresql://plea_local:local@127.0.0.1:5432/{db}') as conn:
        who = conn.execute('SELECT session_user').fetchone()[0]
        rows = conn.execute("""SELECT e.root_id, e.aid, e.seq, e.derived, d.op->>0, d.op->>1, d.kind, d.code,
                                      d.op->>(jsonb_array_length(d.op) - 1)
                               FROM evidence e LEFT JOIN decisions d ON d.root_id = e.root_id AND d.seq = e.seq""").fetchall()
        bad = [r for r in rows if r[4] not in ('RELEASE', 'RECONCILE') or r[5] != r[1] or r[8] != r[3]]
        without = conn.execute("""SELECT d.op->>0, d.op->>(jsonb_array_length(d.op) - 1), count(*) FROM decisions d
                                  WHERE d.op->>0 IN ('RELEASE', 'RECONCILE') AND NOT EXISTS (SELECT 1 FROM evidence e WHERE e.root_id = d.root_id AND e.seq = d.seq)
                                  GROUP BY 1, 2 ORDER BY 1, 2""").fetchall()
        withrow = conn.execute("""SELECT d.op->>0, d.op->>(jsonb_array_length(d.op) - 1), d.kind, count(*) FROM decisions d JOIN evidence e ON e.root_id = d.root_id AND e.seq = d.seq
                                  GROUP BY 1, 2, 3 ORDER BY 1, 2, 3""").fetchall()
        budgets = conn.execute('SELECT count(*) FROM roots').fetchone()[0]; decisions = conn.execute('SELECT count(*) FROM decisions').fetchone()[0]
    LOG['databases'][db] = {'read as': who, 'budgets': budgets, 'decisions': decisions, 'report rows': len(rows),
                            'rows NOT at a RELEASE or RECONCILE decision naming their run, with the row\'s label': len(bad), 'those': bad[:5],
                            'report rows by operation, label and kind of decision': [list(x) for x in withrow],
                            'RELEASE or RECONCILE decisions with no report row, by operation and label': [list(x) for x in without]}
    print('---', db); [print('   ', k, ':', json.dumps(v)) for k, v in LOG['databases'][db].items()]
(OUT / 'gate_rows_as_service.json').write_text(json.dumps(LOG, indent=1) + '\n')
