"""P5 (review A1). Expectation written before the run: in mcp/plea_mcp.py, a store that cannot be read when a tool is called
now raises out of handle() (identity_form is outside call_tool's try), where at 1b132e2 the same failure inside attempt()
was answered as a tool error. PREDICTION: new -> exception escapes handle(); old (request_key without the form) -> handle returns isError."""
import sys, types, json, importlib.util
W, OLD = sys.argv[1], sys.argv[2]
def load(path, name):
    sys.path.insert(0, path)
    spec = importlib.util.spec_from_file_location(name, path + '/mcp/plea_mcp.py'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); sys.path.pop(0); return m
class DeadStore:
    def observe(self, root): raise ConnectionError('database unreachable (stub)')
class Gov:
    store, root, host = DeadStore(), 'r', None
    def attempt(self, key, run): self.store.observe(self.root)
out = {}
for tag, path in (('new', W), ('old', OLD)):
    m = load(path, 'plea_mcp_' + tag)
    srv = m.GovernedServer(Gov(), {'t': ('d', {'type': 'object'}, lambda **k: 1)})
    try:
        r = srv.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 't', 'arguments': {}}})
        out[tag] = ('answered', r['result'].get('isError'), r['result']['content'][0]['text'][:80])
    except Exception as exc:
        out[tag] = ('raised out of handle()', type(exc).__name__, str(exc)[:80])
    for k in [k for k in sys.modules if k.startswith('plea_gateway')]: del sys.modules[k]
print(json.dumps(out, indent=1))
