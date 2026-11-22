"""Q3 (review 3).  Expectations written before the run.
a) empty budget -> 'current'; one a2- attempt -> 'current'; plea_local then reserves 'a-'+16 hex -> identity_form raises
   IdentityFormsMixed, and Governor.attempt on it raises IdentityFormsMixed with no new attempt added.
b) legacy budget (one a- attempt) plus an attempt named in neither form ('zz-odd') -> still 'legacy'.
c) mcp/plea_mcp.py: a store that cannot be read, and a mixed budget, are each answered as a tool error (isError True), not raised.
PREDICTION: a = ('current','current','IdentityFormsMixed','IdentityFormsMixed', attempts unchanged = True); b = 'legacy';
c = (isError True, isError True)."""
import sys, json, uuid, importlib.util
W = sys.argv[1]; sys.path.insert(0, W)
from plea_gateway import Store
from plea_gateway import governor as G
db = 'plea_rv3'
control = Store(f'postgresql://plea_control:control@127.0.0.1:5432/{db}'); local = Store(f'postgresql://plea_local:local@127.0.0.1:5432/{db}')
out = {}
def form(root):
    try: return G.identity_form(local, root)
    except Exception as exc: return type(exc).__name__
root = 'REQ-RV3/A/' + uuid.uuid4().hex; control.new_root(root, 10, 0)
a = [form(root)]
local.apply(root, ('RESERVE', G.attempt_id('verify:' + 'c' * 64), 'verify:' + 'c' * 64)); a.append(form(root))
local.apply(root, ('RESERVE', 'a-' + '0' * 16, 'verify:' + '0' * 24)); a.append(form(root))
n0 = len(local.observe(root)['attempts'])
gov = G.Governor.__new__(G.Governor); gov.store, gov.root = local, root
try: gov.attempt('verify:' + 'd' * 64, 'verify'); a.append('no raise')
except Exception as exc: a.append(type(exc).__name__)
a.append(len(local.observe(root)['attempts']) == n0)
out['a'] = a
root2 = 'REQ-RV3/B/' + uuid.uuid4().hex; control.new_root(root2, 10, 0)
local.apply(root2, ('RESERVE', 'a-' + '1' * 16, 'verify:' + '1' * 24)); local.apply(root2, ('RESERVE', 'zz-odd', 'verify:odd'))
out['b'] = form(root2)
spec = importlib.util.spec_from_file_location('plea_mcp_new', W + '/mcp/plea_mcp.py'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class DeadStore:
    def observe(self, r): raise ConnectionError('database unreachable (stub)')
class Gov:
    host = None
    def __init__(self, store, root): self.store, self.root = store, root
    def attempt(self, key, run): return G.Governor.attempt(self_gov(self.store, self.root), key, run)
def self_gov(store, root):
    g = G.Governor.__new__(G.Governor); g.store, g.root = store, root; return g
c = []
for store, r in ((DeadStore(), 'r'), (local, root)):
    srv = m.GovernedServer(Gov(store, r), {'t': ('d', {'type': 'object'}, lambda **k: 1)})
    try:
        res = srv.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 't', 'arguments': {}}})
        c.append(('answered', res['result'].get('isError'), res['result']['content'][0]['text'][:90]))
    except Exception as exc:
        c.append(('raised', type(exc).__name__))
out['c'] = c
print(json.dumps(out, indent=1))
