"""Tools for the review reproductions (v0.6): a charge that appends to a ledger, a slow one, and a no-effect refund."""
import json
import os
import time

from plea_gateway.governor import NoEffect


def _append(record):
    path = os.environ.get('PLEA_LEDGER', 'review_ledger.jsonl')
    with open(path, 'a') as f:
        f.write(json.dumps(record) + '\n'); f.flush(); os.fsync(f.fileno())


def charge(order_id, amount):
    _append({'charge': order_id, 'amount': amount}); return {'charged': amount, 'order': order_id}


def slow_charge(order_id, amount, delay=3.0):
    time.sleep(delay); _append({'charge': order_id, 'amount': amount}); return {'charged': amount, 'order': order_id}


def refund(order_id, amount):
    if amount == 0:
        raise NoEffect()
    _append({'refund': order_id, 'amount': amount}); return {'refunded': amount}


S = {'type': 'object', 'properties': {'order_id': {'type': 'string'}, 'amount': {'type': 'number'}}, 'required': ['order_id', 'amount']}
def fail(order_id, amount):
    raise RuntimeError('the tool failed before any effect')


TOOLS = {'charge': ('append a charge', S, charge), 'slow_charge': ('append a charge after a delay', S, slow_charge),
         'refund': ('refund; 0 is a no-effect', S, refund), 'fail': ('raise: an UNKNOWN verdict', S, fail)}
