"""Apply one operation to one root in a fresh process (the chaos runner's child).  usage: apply_once.py ROOT OP_JSON"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import store_for, _tuple_op   # noqa: E402

root, op = sys.argv[1], _tuple_op(json.loads(sys.argv[2]))
decision, _ = store_for(op).apply(root, op)          # the witness credential for acceptances, local otherwise
print(decision.kind, decision.code)
