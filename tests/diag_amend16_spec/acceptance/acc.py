"""The acceptance-test framework: labels, capability separation (K-CAP-1), a budget per test (ACC-5), the ACC-2
statement, and the helpers every test uses.

Every test method carries @acc(id=..., rules=[...], cap=..., decisions=[...], catches='...').  `cap` is exactly one of
CAP-DB, CAP-KEY, CAP-OS, CAP-OWNER, NONE (honest operation).  `catches` is the one line saying what wrong implementation
the test would catch (requirement: every test must be able to fail).  `open_finding` marks a test that rests on an open
finding of the specification's review (F33, F34) or on one of this suite's findings (T-numbers).

Capability separation by construction:
  - the honest gate host runs in another process (fixtures/honest_gate.py) and only its public key is in this process;
  - the CAP-KEY signer (fixtures/capkey.py) refuses to exist or sign unless the current test is labelled CAP-KEY;
  - the runner statically refuses a non-CAP-KEY test whose source or module touches the signer (ERROR).
"""
import atexit
import os
import shutil
import tempfile
import threading
import unittest

import rules as R
import sut as SUT

ACC2 = ('ACC-2: No test run on a single host, or on any deployment where DP1 or DP2 does not hold, establishes acceptance '
        'of the production contract. Every result of this suite is diagnostic evidence about the code\'s behaviour: '
        'separately authored verification (internal), not independent validation.')
CAPS = ('CAP-DB', 'CAP-KEY', 'CAP-OS', 'CAP-OWNER', 'NONE')
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, '.work')


class CapabilityViolation(Exception):
    """A test touched a capability its label does not grant (K-CAP-1).  Reported as ERROR."""


class BudgetReuse(Exception):
    """A budget was used by two tests (ACC-5).  Reported as ERROR."""


_cur = threading.local()
_cur_global = {'cap': None, 'id': None}


def current_capability():
    return _cur_global['cap']


def current_test():
    return _cur_global['id']


def set_current(cap, tid):
    _cur_global['cap'], _cur_global['id'] = cap, tid


def acc(id, rules, cap, catches, decisions=None, open_finding=None):
    if cap not in CAPS:
        raise ValueError(f'{id}: capability {cap!r} is not one of {CAPS}')
    if not rules:
        raise ValueError(f'{id}: a test must name the rule(s) it tests')

    def wrap(fn):
        fn._acc = {'id': id, 'rules': list(rules), 'cap': cap, 'catches': catches,
                   'decisions': sorted(set(decisions or R.decisions_for(rules))), 'open_finding': open_finding}
        return fn
    return wrap


_OWNERS = {}
_GATE = None
_LOCK = threading.Lock()


def honest_gate():
    global _GATE
    with _LOCK:
        if _GATE is None:
            from fixtures.honest_gate import HonestGate
            _GATE = HonestGate()
            atexit.register(_GATE.close)
        return _GATE


class AccTest(unittest.TestCase):
    """Base class.  Helpers create a fresh budget for every test (ACC-5)."""

    mb_config = None

    def setUp(self):
        self._cleanups_acc = []
        self.sut = SUT.get_adapter()
        from fixtures.crypto import TestKey
        self.wkey = TestKey()                 # the (trusted) witness of this test's budgets
        self.ckey = TestKey()                 # the (trusted) courier of this test's budgets

    def tearDown(self):
        for fn in reversed(self._cleanups_acc):
            try:
                fn()
            except Exception:                 # noqa: BLE001
                pass

    def later(self, fn):
        self._cleanups_acc.append(fn)

    def optional(self, h, name):
        """An optional seam method of a handle; NOT IMPLEMENTED when the adapter does not provide it."""
        fn = getattr(h, name, None)
        if fn is None:
            raise SUT.SutNotImplemented(f'the adapter\'s handle has no {name}() (optional seam)')
        return fn

    # ------------------------------------------------------------------ ACC-5
    def new_root(self, tag='b'):
        root = f'ACC/{current_test() or self.id()}/{tag}/{os.urandom(6).hex()}'
        with _LOCK:
            if root in _OWNERS and _OWNERS[root] != current_test():
                raise BudgetReuse(f'budget {root} is used by {_OWNERS[root]} and {current_test()} (ACC-5)')
            _OWNERS[root] = current_test()
        return root

    # ------------------------------------------------------------------ capabilities
    def gate(self):
        """The honest gate host (another process).  Every capability may use it."""
        return honest_gate()

    def capkey_signer(self):
        """CAP-KEY only (K-CAP-1): a signer holding a gate key in this process."""
        from fixtures import capkey
        return capkey.CapKeySigner()

    # ------------------------------------------------------------------ section 3
    def new_budget(self, gate_keys=None, honest=True, tag='b'):
        from fixtures.chain import Budget
        g = self.gate() if honest else None
        keys = gate_keys if gate_keys is not None else ([g.public_key] if g else [])
        return Budget(self.new_root(tag), self.wkey, keys, gate=g)

    def run_input(self, b, aid, n=None, keys=None, result='STORED'):
        n = b.n if n is None else n
        phase, nonce = b.phase_at(aid, n)
        decs = b.decisions_naming(aid, n)
        intent = next((d['seq'] for d in decs if d['op'][0] == 'ACCEPT_INTENT' and d['kind'] == 'APPLIED'), None)
        ans = b.run_answer(aid)
        return SUT.RunInput(root=b.root, aid=aid, n=n, phase=phase, chain_nonce=nonce, decisions=decs,
                            evidence=ans['evidence'], result=ans['result'] if result == 'STORED' else result,
                            gate_keys=list(keys if keys is not None else b.wgk), intent_seq=intent)

    def judge(self, b, aid, **kw):
        return self.sut.judge_run(self.run_input(b, aid, **kw))

    def assertFindings(self, j, expected, msg=''):
        self.assertEqual(set(j.findings), set(expected), f'{msg}: findings {sorted(j.findings)} != {sorted(expected)}')

    # ------------------------------------------------------------------ mailbox
    def workdir(self, tag):
        os.makedirs(WORK, exist_ok=True)
        d = tempfile.mkdtemp(prefix=tag + '-', dir=WORK)
        self.later(lambda: shutil.rmtree(d, ignore_errors=True))
        return d

    def mailbox(self, n_budgets=1, clock=None, same_key=False, budget_keys=None, **cfg):
        """Start a mailbox for fresh budget(s); returns (driver, handle, clock).  driver.budget is a scripted Budget whose
        witness key the mailbox pins.  Extra budgets: self.extra_drivers."""
        from fixtures.clock import TestClock
        from fixtures.form3 import Driver
        from fixtures.crypto import TestKey
        clock = clock or TestClock()
        budgets = [self.new_budget(tag=f'm{i}', gate_keys=budget_keys, honest=budget_keys is None) for i in range(n_budgets)]
        keys = [self.ckey] * n_budgets if same_key else [self.ckey] + [TestKey() for _ in range(n_budgets - 1)]
        base = dict(writers=['courier'], readers=['reader'], budgets={b.root: k.public_hex for b, k in zip(budgets, keys)},
                    witness_keys=[self.wkey.public_hex], L=60.0, R=30.0)
        base.update(cfg)
        conf = SUT.MailboxConfig(**base)
        self.mb_config = conf
        self.mb_store = self.workdir('mb')
        h = self.sut.start_mailbox(conf, clock, self.mb_store)
        self.later(h.close)
        codec = self.sut.codec()
        drivers = [Driver(self, h, codec, b.root, k, self.wkey, budget=b) for b, k in zip(budgets, keys)]
        self.extra_drivers = drivers[1:]
        self.clock = clock
        return drivers[0], h, clock

    def covered_driver(self, **cfg):
        """A mailbox and a budget that is COVERED after an honest EPOCH_OPEN and FROM_ZERO statement."""
        d, h, clock = self.mailbox(**cfg)
        d.budget.new_run(upto='CONSUMED')
        d.open_epoch()
        d.cover('FROM_ZERO')
        return d, h, clock


class Env:
    """A courier under test, the scripted witness, the mailbox under test behind a logging proxy, and two clocks."""
    pass


class CourierTest(AccTest):
    def courier_env(self, mb=None, cc=None, budget_keys=None):
        from fixtures.clock import TestClock
        from fixtures.netfix import EventLog, ScriptedWitness, MailboxProxy
        e = Env()
        e.d, e.h, e.mclock = self.mailbox(budget_keys=budget_keys, **(mb or {}))
        e.b = e.d.budget
        e.log = EventLog()
        e.w = ScriptedWitness(e.log, self.wkey); self.later(e.w.close)
        e.w.budgets[e.b.root] = e.b
        e.px = MailboxProxy(e.log, e.h); self.later(e.px.close)
        e.cclock = TestClock(wall_start=e.mclock.wall())
        cfg = SUT.CourierConfig(name='acc-courier', client='courier', courier_key_hex=self.ckey.private_hex,
                                budgets=[{'root': e.b.root, 'provisioning_hash': e.b.prov_hash}],
                                witness_keys=[self.wkey.public_hex], gate_keys=list(e.b.wgk), mailbox_keys=[e.h.public_key],
                                **(cc or {}))
        e.cfg = cfg
        e.c = self.sut.start_courier(cfg, e.w.url, e.px.url, e.cclock, self.workdir('courier'))
        self.later(e.c.close)
        e.read = lambda: e.c.read(e.b.root)
        return e

    # what the courier delivered, as the proxy saw it
    def items(self, e, kind=None, ok=True, since=0):
        out = []
        for ev in e.log.of('mailbox', 'POST /deliver')[since:]:
            it = ev['body']
            if not isinstance(it, dict) or (ok and ev['status'] != 200) or ev.get('dropped') and ok:
                continue
            if kind is None or it.get('kind') == kind:
                out.append(it)
        return out

    def n_deliveries(self, e):
        return len(e.log.of('mailbox', 'POST /deliver'))

    def witness_runs(self, e, since=0):
        return [ev['query'].get('aid') for ev in e.log.events[since:] if ev['party'] == 'witness' and ev['what'] == '/run']

    def alarm_reasons(self, e, since=0):
        out = set()
        for it in self.items(e, 'OBSERVATION_INCOMPLETE', since=since):
            out |= e.d.c.alarm_reasons(it['body'])
        return out
