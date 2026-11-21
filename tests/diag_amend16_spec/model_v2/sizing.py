"""Sizing only: prints the number of states and time for a configuration (with overrides);
prints NO property verdicts. Used to choose bounds; see REPORT.md."""
import sys, json, time
import configs, model
name = sys.argv[1]
over = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
cap = int(sys.argv[3]) if len(sys.argv) > 3 else 400000
cfg = dict(configs.CONFIGS[name]); cfg.update(over); cfg['MAX_STATES'] = cap
for k in ('VALUES', 'MUTANTS'):
    if k in cfg and isinstance(cfg[k], list): cfg[k] = tuple(cfg[k])
m = model.Model(cfg)
t = time.time(); r = model.bfs(m, cap)
print(name, over, 'states', r['states'], 'complete', r['complete'], 'depth', r['maxdepth'], 'secs %.1f' % (time.time() - t))
