"""Two tools with real side effects, for the double-charge demonstration.

Each call appends a line to a ledger file named by PLEA_LEDGER, so executions are visible across processes.
`charge` returns a receipt string; `refund` of a zero amount raises NoEffect, which under the governor earns a
replacement and without it is just an error.
"""
import json
import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from plea_gateway import NoEffect   # noqa: E402

LEDGER = pathlib.Path(os.environ.get('PLEA_LEDGER', str(pathlib.Path(__file__).resolve().parent / 'ledger.jsonl')))


def _record(kind: str, **fields) -> None:
    with LEDGER.open('a') as f:
        f.write(json.dumps({'kind': kind, 'pid': os.getpid(), 't': time.time(), **fields}) + '\n')


def charge(order_id: str, amount: int) -> str:
    _record('charge', order_id=order_id, amount=amount)
    return f'charged {amount} for order {order_id}'


def refund(order_id: str, amount: int) -> str:
    if amount == 0:
        raise NoEffect()
    _record('refund', order_id=order_id, amount=amount)
    return f'refunded {amount} for order {order_id}'


TOOLS = {
    'charge': ('Charge a customer for an order.',
               {'type': 'object', 'properties': {'order_id': {'type': 'string'}, 'amount': {'type': 'integer'}}, 'required': ['order_id', 'amount']},
               charge),
    'refund': ('Refund a customer for an order.',
               {'type': 'object', 'properties': {'order_id': {'type': 'string'}, 'amount': {'type': 'integer'}}, 'required': ['order_id', 'amount']},
               refund),
}
