#!/usr/bin/env python3
"""Run the adversarial acceptance tests of the Amendment 16 specification, version 6.

    run_acceptance.py [--adapter MODULE] [--name NAME] [--filter TEXT] [--dir tests]

Prints, for each test, its id, rule ids, capability, the owner's decision number(s) and its outcome:
PASS / FAIL / NOT IMPLEMENTED / ERROR.  Writes results/<NAME>.json and results/<NAME>.console.txt (never overwriting
an earlier run: a suffix is added).  Prints the ACC-2 statement at the head and the foot.  Exits 0 only if every
test passed.

Outcomes:  PASS             the test's assertions held
           FAIL             an assertion did not hold: the system under test does not meet the rule as tested
           NOT IMPLEMENTED  the adapter does not bind what the test needs (sut.SutNotImplemented)
           ERROR            the test could not be judged: an unexpected exception, an unlabelled test, a test that
                            breaks capability separation (K-CAP-1) or reuses a budget (ACC-5)
"""
import argparse
import ast
import importlib.util
import inspect
import json
import os
import sys
import textwrap
import time
import traceback
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import acc  # noqa: E402
import rules  # noqa: E402
import sut  # noqa: E402

FORBIDDEN = {'capkey_signer', 'capkey', 'CapKeySigner'}


def capability_violation(fn, module):
    """Why a test may not run under its label (K-CAP-1), or None.  Only a CAP-KEY test may touch the CAP-KEY signer:
    its source must not name it, and its module must not hold it at module level."""
    meta = getattr(fn, '_acc', None)
    if meta is None:
        return 'the test carries no @acc label (id, rules, capability, decisions)'
    if meta['cap'] == 'CAP-KEY':
        return None
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    except (OSError, TypeError, SyntaxError) as exc:
        return f'its source cannot be inspected for capability separation: {exc}'
    for node in ast.walk(tree):
        name = node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else \
            (node.module or '') if isinstance(node, ast.ImportFrom) else None
        if isinstance(node, ast.Import):
            name = ' '.join(a.name for a in node.names)
        if name and any(f in name for f in FORBIDDEN):
            return f'a test labelled {meta["cap"]} names the CAP-KEY signer ({name}) (K-CAP-1)'
    for k, v in vars(module).items():
        if k in FORBIDDEN or getattr(v, '__name__', '') in ('fixtures.capkey', 'CapKeySigner'):
            return f'a test labelled {meta["cap"]} sits in a module that imports the CAP-KEY signer ({k}) (K-CAP-1)'
    return None


def load_tests(directory, flt=None):
    out = []
    if directory not in sys.path:
        sys.path.insert(0, directory)
    for fname in sorted(os.listdir(directory)):
        if not (fname.startswith('test_') or fname.startswith('bad_')) or not fname.endswith('.py'):
            continue
        path = os.path.join(directory, fname)
        spec = importlib.util.spec_from_file_location(f'acc_{os.path.basename(directory)}_{fname[:-3]}', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for cname, cls in sorted(vars(mod).items()):
            if not (isinstance(cls, type) and issubclass(cls, unittest.TestCase) and cls.__module__ == mod.__name__):
                continue
            for mname in sorted(n for n in dir(cls) if n.startswith('test')):
                fn = getattr(cls, mname)
                meta = getattr(fn, '_acc', None)
                tid = meta['id'] if meta else f'{cname}.{mname}'
                if flt and flt not in tid and flt not in fname:
                    continue
                out.append((tid, cls, mname, fn, mod, fname))
    return out


class _Collect(unittest.TestResult):
    def __init__(self):
        super().__init__(); self.outcome, self.detail = 'PASS', ''

    def _exc(self, err, kind):
        et, ev, tb = err
        if issubclass(et, sut.SutNotImplemented):
            self.outcome, self.detail = 'NOT IMPLEMENTED', str(ev)
        elif issubclass(et, (acc.CapabilityViolation, acc.BudgetReuse)):
            self.outcome, self.detail = 'ERROR', f'{et.__name__}: {ev}'
        elif kind == 'fail':
            self.outcome, self.detail = 'FAIL', str(ev)[:2000]
        else:
            self.outcome, self.detail = 'ERROR', ''.join(traceback.format_exception(et, ev, tb))[-2500:]

    def addFailure(self, test, err):
        self._exc(err, 'fail')

    def addError(self, test, err):
        self._exc(err, 'error')

    def addSkip(self, test, reason):
        self.outcome, self.detail = 'ERROR', f'skipped: {reason}'


def run_one(tid, cls, mname, fn, mod):
    meta = getattr(fn, '_acc', None)
    why = capability_violation(fn, mod)
    if why:
        return {'outcome': 'ERROR', 'detail': 'refused to run: ' + why}
    acc.set_current(meta['cap'], tid)
    res = _Collect()
    t0 = time.time()
    try:
        cls(mname).run(res)
    finally:
        acc.set_current(None, None)
    return {'outcome': res.outcome, 'detail': res.detail, 'seconds': round(time.time() - t0, 3)}


def run(tests):
    rows = []
    for tid, cls, mname, fn, mod, fname in tests:
        meta = getattr(fn, '_acc', None) or {'rules': [], 'cap': '?', 'decisions': [], 'catches': '', 'open_finding': None}
        r = run_one(tid, cls, mname, fn, mod)
        rows.append(dict(id=tid, file=fname, method=f'{cls.__name__}.{mname}', rules=meta['rules'], capability=meta['cap'],
                         decisions=meta['decisions'], catches=meta['catches'], open_finding=meta.get('open_finding'), **r))
    return rows


def _unique(path):
    base, ext = os.path.splitext(path); i = 1
    while os.path.exists(path):
        i += 1; path = f'{base}-{i}{ext}'
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--adapter'); ap.add_argument('--name'); ap.add_argument('--filter'); ap.add_argument('--dir', default='tests')
    a = ap.parse_args()
    if a.adapter:
        os.environ['ACC_SUT'] = a.adapter
    adapter = sut.get_adapter()
    name = a.name or adapter.name
    head = [acc.ACC2,
            f'Specification: Amendment 16, version {rules.SPEC["version"]}, {rules.SPEC["file"]} ({rules.SPEC["lines"]} lines), SHA-256 {rules.SPEC["sha256"]}',
            f'Adapter: {adapter.name}   started {time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}', '']
    lines = list(head)
    for l in head:
        print(l, flush=True)
    tests = load_tests(os.path.join(HERE, a.dir), a.filter)
    rows = []
    for t in tests:
        r = run([t])[0]; rows.append(r)
        line = f"{r['outcome']:<16} {r['id']:<34} cap={r['capability']:<9} dec={','.join(map(str, r['decisions'])):<5} rules={','.join(r['rules'])}"
        print(line, flush=True); lines.append(line)
        if r['outcome'] in ('FAIL', 'ERROR'):
            d = '      ' + r['detail'].strip().replace('\n', '\n      ')[:1500]
            print(d, flush=True); lines.append(d)
    counts = {}
    for r in rows:
        counts[r['outcome']] = counts.get(r['outcome'], 0) + 1
    foot = ['', 'Totals: ' + ', '.join(f'{k} {v}' for k, v in sorted(counts.items())) + f' (of {len(rows)})', acc.ACC2]
    for l in foot:
        print(l, flush=True)
    lines += foot
    os.makedirs(os.path.join(HERE, 'results'), exist_ok=True)
    jp = _unique(os.path.join(HERE, 'results', f'{name}.json'))
    with open(jp, 'w') as f:
        json.dump({'acc2': acc.ACC2, 'spec': rules.SPEC, 'adapter': adapter.name, 'counts': counts,
                   'when': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                   'results': [dict(r, acc2=acc.ACC2) for r in rows]}, f, indent=1)
    with open(jp[:-5] + '.console.txt', 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'written {jp}')
    sys.exit(0 if rows and all(r['outcome'] == 'PASS' for r in rows) else 1)


if __name__ == '__main__':
    main()
