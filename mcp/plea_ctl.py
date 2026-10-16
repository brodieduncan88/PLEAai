#!/usr/bin/env python3
"""Operator control of a governed run, outside the agent's reach.

    plea_ctl.py ROOT provision --budget K [--replacement M]
    plea_ctl.py ROOT status | hold | stop | recover [--incomplete] | terminalise | terminal | reregister | audit | provenance

provision (v1.1) creates the root with its immutable budget k and replacement allowance m: a gateway runs only
against a root provisioned here, and cannot create one itself.  v1.2: provisioning appends a record to the database's
provisioning log and prints its hash, the anchor the root's audit chain starts from.  provenance prints that record
(root, k, m, issuer, contract, release, time) and verifies the root's chain from it and the whole provisioning log.
audit lists every decision recorded for the root: sequence number, kind, code and the operation, in order.

These are the contract's control-plane operations.  v0.9: they change a mode, so they are applied through the
control credential (plea_control), which the gateway credential does not hold.  The agent, which only sees the
governed tools, cannot issue them, and a compromised gateway cannot either.
"""
import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from plea_gateway import Store, RootExists   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root'); ap.add_argument('action', choices=['provision', 'status', 'hold', 'stop', 'recover', 'terminalise', 'terminal', 'reregister', 'audit', 'provenance'])
    ap.add_argument('--budget', type=int, help='provision: the attempt budget k'); ap.add_argument('--replacement', type=int, default=0, help='provision: the replacement allowance m')
    ap.add_argument('--incomplete', action='store_true', help='recover with complete = false (the run stays held)')
    ap.add_argument('--control-dsn', default=os.environ.get('PLEA_CONTROL_DSN', 'postgresql://plea_control:control@127.0.0.1:5432/plea'))
    a = ap.parse_args()
    store = Store(a.control_dsn)
    if a.action == 'provision':
        if a.budget is None: ap.error('provision needs --budget K')
        try:
            rec = store.new_root(a.root, a.budget, a.replacement)
            print('PROVISIONED', a.root, '| k', a.budget, '| m', a.replacement, '| record', rec['seq'], '| anchor', rec['hash'])
        except RootExists:
            print('EXISTS', a.root, '| the root already carries its immutable budget:', json.dumps(store.observe(a.root)['k']))
        return
    if a.action == 'status':
        print(json.dumps(store.observe(a.root), indent=1)); return
    if a.action == 'provenance':              # v1.2: where the budget came from, and whether the chain still starts there
        rec = store.provisioning(a.root)
        if rec is None:
            print('NO PROVISIONING RECORD for', a.root); sys.exit(1)
        print(json.dumps(rec, indent=1, sort_keys=True))
        ok, detail = store.verify_chain(a.root)
        print('chain ok' if ok else f'chain FAILED: {detail}')
        lok, ldetail, n = store.verify_provisioning()
        print(f'provisioning log ok ({n} records)' if lok else f'provisioning log FAILED: {ldetail}')
        if not (ok and lok):
            sys.exit(1)
        return
    if a.action == 'audit':                   # every decision, in the store's order (a stranger found the early return here)
        for d in store.audit(a.root):
            print(d['seq'], d['kind'], d['code'], json.dumps(d['op']))
        return
    op = {'hold': ('HOLD',), 'stop': ('STOP',), 'terminalise': ('TERMINALISE',), 'terminal': ('TERMINAL',), 'reregister': ('REREGISTER',),
          'recover': ('RECOVER', True, not a.incomplete)}[a.action]
    d, obs = store.apply(a.root, op)
    print(d.kind, d.code, '| witness', obs['witness'], '| business', obs['business'], '| live', obs['live'])


if __name__ == '__main__':
    main()
