#!/usr/bin/env python3
"""Contract v3.1's declared reference tests as executable vectors, copied unchanged from the v3.1 oracle bundle so this
bundle can run them against the store (conform_store) on its own: PYTHONPATH=. python3 -B vectors.py conform_store

v3.1 (errata E1-E11): B14 now runs at k = 3 as v3.1 section 10 fixes it (E11); B18b (E1, E10) and B25-B28 (E6, E7,
E5, E3) are new.  Every other vector is unchanged from v3.

v2's B01-B16 and B18 are unchanged; X01-X02 (restored, AC1), B07b (AC3) and B09b (AC2) were added for the v2 review and
are now declared by v3; B10b, B16b and B19-B24 are new in v3 and test decisions D2-D9.  Expectations come from the
contract v3 text (sections 2-6), never from running an implementation.

Each vector is a list of steps: an event and the expected decision kind (APPLIED, NOOP, DUPLICATE, DENIED), plus
expected observations after chosen steps.  Expectations come from the contract text and ALPHABET.md, never from
running an implementation.  X01-X02 restore two tests that contract v1 declared and v2 dropped; B09b is a reviewer
addition.  Run against the oracle by default, or against another implementation exposing the same interface
(initial, step, observe; World/world_step and Root/Attempt/root_from_facts for the few vectors that need them).

usage: vectors.py [module]
"""
import importlib, json, sys

A, N, D, U = 'APPLIED', 'NOOP', 'DENIED', 'DUPLICATE'
# helper prefixes ---------------------------------------------------------------------------------------------
def reserved(a, q):  return [(('RESERVE', a, q), A), (('ACCEPT_RESERVATION', a), A)]
def tokened(a, q):   return reserved(a, q) + [(('TOKEN', a), A)]
def pending(a, q, n): return tokened(a, q) + [(('START', a, n), A)]
def consumed(a, q, n): return pending(a, q, n) + [(('ACCEPT_INTENT', a), A)]
def no_effect(a, q, n): return consumed(a, q, n) + [(('RECONCILE', a, 'NO_EFFECT', 'AUTHORISED'), A)]
def live(r, c, n=None, credit=None):
    want = {'live_R': r, 'live_C': c}
    if n is not None: want['N'] = n
    if credit is not None: want['credit'] = credit
    return ('EXPECT', want)

VECTORS = {
  'B01 zero budget admits nothing (m = 0, 1, 2)': [
      (k, m, [(('RESERVE', 'a1', 'q1'), D), live(0, 0)]) for k, m in ((0, 0), (0, 1), (0, 2))],
  'B02 admission boundary': [
      (2, 0, [(('RESERVE', 'a1', 'q1'), A), live(1, 0), (('RESERVE', 'a2', 'q2'), A), live(2, 0),
              (('RESERVE', 'a3', 'q3'), D), live(2, 0)]),
      (1, 1, no_effect('a1', 'q1', 'n1') + [live(0, 1, 1, 1), (('RESERVE', 'a2', 'q2'), A), live(1, 1),
              (('RESERVE', 'a3', 'q3'), D)])],
  'B03 reservation to intent opens no slot': [
      (1, 0, tokened('a1', 'q1') + [live(1, 0), (('START', 'a1', 'n1'), A), live(0, 1), (('RESERVE', 'a2', 'q2'), D)])],
  'B04 finality and receipts': [
      (1, 0, pending('a1', 'q1', 'n1') + [('EXPECT', {'live_C': 1, 'accepted_C': 0, 'accepted_R': 1}),
              (('CROSS', 'a1'), D), (('ACCEPT_INTENT', 'a1'), A), ('EXPECT', {'accepted_C': 1}),
              (('MISSING_RECEIPT', 'a1'), N), (('TIMEOUT', 'a1'), N), (('CROSS', 'a1'), D),
              (('RECEIPT', 'a1'), A), (('CROSS', 'a1'), A), (('CROSS', 'a1'), D), live(0, 1)])],
  'B05 never-accepted suffix only through verified recovery': [
      (1, 0, pending('a1', 'q1', 'n1') + [(('TIMEOUT', 'a1'), N), (('MISSING_RECEIPT', 'a1'), N), (('CRASH',), N),
              live(0, 1), (('RESERVE', 'a2', 'q2'), D), (('HOLD',), A), (('RECOVER', False, True), D),
              (('RECOVER', True, True), A), live(1, 0), ('EXPECT', {'witness': 'ACTIVE', 'attempt a1': ('TOKEN', None)}),
              (('START', 'a1', 'n1'), A), live(0, 1)])],
  'B06 accepted consumption persists': [
      (1, 0, consumed('a1', 'q1', 'n1') + [(('CRASH',), N), (('RECONCILE', 'a1', 'UNKNOWN', 'AUTHORISED'), N),
              (('RECONCILE', 'a1', 'EFFECT', 'AUTHORISED'), A), (('STOP',), A), live(0, 1),
              ('EXPECT', {'accepted_C': 1})]),
      (1, 0, consumed('a1', 'q1', 'n1') + [(('RECONCILE', 'a1', 'NO_EFFECT', 'AUTHORISED'), A), live(0, 1, 1, 0),
              (('RESERVE', 'a2', 'q2'), D)]),
      (1, 1, consumed('a1', 'q1', 'n1') + [(('RECONCILE', 'a1', 'NO_EFFECT', 'AUTHORISED'), A), live(0, 1, 1, 1),
              (('RESERVE', 'a2', 'q2'), A)])],
  'B07 bounded replacement credit': [
      (1, 1, no_effect('a1', 'q1', 'n1') + [(('RECONCILE', 'a1', 'NO_EFFECT', 'AUTHORISED'), U), live(0, 1, 1, 1)]
             + no_effect('a2', 'q2', 'n2') + [live(0, 2, 2, 1), (('RESERVE', 'a3', 'q3'), D), (('RESERVE', 'a2', 'q2'), U),
              live(0, 2, 2, 1)])],
  'B07b an EFFECT verdict earns no replacement credit (reviewer addition)': [
      (1, 1, consumed('a1', 'q1', 'n1') + [(('RECONCILE', 'a1', 'EFFECT', 'AUTHORISED'), A), live(0, 1, 0, 0),
              (('RESERVE', 'a2', 'q2'), D)])],
  'B08 evidence boundary': [
      (1, 1, consumed('a1', 'q1', 'n1') + [(('RECONCILE', 'a1', 'NO_EFFECT', 'NONE'), D),
              (('RECONCILE', 'a1', 'NO_EFFECT', 'WRONG_BINDING'), D), (('RECONCILE', 'a9', 'NO_EFFECT', 'AUTHORISED'), D),
              live(0, 1, 0, 0)]),
      (1, 1, pending('a1', 'q1', 'n1') + [(('RECONCILE', 'a1', 'NO_EFFECT', 'AUTHORISED'), D), live(0, 1, 0, 0)]),
      (1, 1, tokened('a1', 'q1') + [(('RECONCILE', 'a1', 'NO_EFFECT', 'AUTHORISED'), D)])],
  'B09 reservation release': [
      (1, 0, tokened('a1', 'q1') + [(('RELEASE', 'a1', 'NONE'), D), (('RELEASE', 'a1', 'WRONG_BINDING'), D),
              (('RELEASE', 'a1', 'BOUND_FENCE'), A), (('RELEASE', 'a1', 'BOUND_FENCE'), U), live(0, 0),
              (('RESERVE', 'a2', 'q2'), A)]),
      (1, 0, consumed('a1', 'q1', 'n1') + [(('RELEASE', 'a1', 'BOUND_FENCE'), D), live(0, 1)])],
  'B09b release after a pending local intent is refused (reviewer addition)': [
      (1, 0, pending('a1', 'q1', 'n1') + [(('RELEASE', 'a1', 'BOUND_FENCE'), D), live(0, 1)])],
  'B11 held operations (v3 wording: a stop is accepted while held and the run stays HELD)': [
      (2, 0, tokened('a1', 'q1') + [(('HOLD',), A), (('RESERVE', 'a2', 'q2'), D), (('START', 'a1', 'n1'), D),
              (('RELEASE', 'a1', 'BOUND_FENCE'), D), (('TERMINALISE',), D), (('STOP',), A),
              ('EXPECT', {'witness': 'HELD', 'business': 'STOPPING'}), (('RECOVER', True, True), A),
              ('EXPECT', {'witness': 'ACTIVE', 'business': 'STOPPING'}), (('RESERVE', 'a2', 'q2'), D),
              (('START', 'a1', 'n1'), D)])],
  'B12 recovery does not mint capacity': [
      (1, 0, consumed('a1', 'q1', 'n1') + [(('HOLD',), A), (('RECOVER', True, True), A), live(0, 1),
              ('EXPECT', {'k': 1, 'accepted_C': 1, 'attempt a1': ('CONSUMED', 'n1')}), (('RESERVE', 'a2', 'q2'), D),
              (('START', 'a1', 'n2'), D), (('REREGISTER',), A), ('EXPECT', {'k': 1, 'live_C': 1}),
              (('RESERVE', 'a3', 'q3'), D)])],
  'B13 conservative reconstruction': [
      (3, 0, tokened('a1', 'q1') + [(('RELEASE', 'a1', 'BOUND_FENCE'), A), (('RESERVE', 'a2', 'q2'), A)]
             + tokened('a3', 'q3') + pending('a4', 'q4', 'n4') + [live(2, 1),
              (('REREGISTER',), A), live(0, 3), ('EXPECT', {'attempt a1': ('RELEASED', None),
              'attempt a2': ('INDETERMINATE', None), 'attempt a4': ('INDETERMINATE', 'n4'), 'business': 'STOPPING'}),
              (('ACCEPT_INTENT', 'a4'), D), (('RELEASE', 'a3', 'BOUND_FENCE'), D), (('TIMEOUT', 'a4'), N)])],
  'B14 re-registration lifecycle (v3.1: k = 3, so only the reduced state can deny)': [
      (3, 0, consumed('a1', 'q1', 'n1') + tokened('a2', 'q2') + [(('REREGISTER',), A),
              ('EXPECT', {'business': 'STOPPING', 'reregistered': True}), live(0, 2), (('RESERVE', 'a3', 'q3'), D),
              (('START', 'a2', 'n2'), D), (('REREGISTER',), D), (('TERMINALISE',), A), (('TERMINAL',), A),
              ('EXPECT', {'business': 'TERMINAL'}), (('REREGISTER',), D)])],
  'B15 dependent phases': [
      (1, 0, [(('RESERVE', 'a1', 'q1'), A), (('START', 'a1', 'n1'), D), (('ACCEPT_RESERVATION', 'a1'), A),
              (('START', 'a1', 'n1'), D), (('TOKEN', 'a1'), A), (('START', 'a1', 'n1'), A)])],
  'B16 replay and nonce': [
      (3, 0, [(('RESERVE', 'a1', 'q1'), A), (('RESERVE', 'a1', 'q1'), U), live(1, 0), (('RESERVE', 'a1', 'q2'), D),
              (('RESERVE', 'a2', 'q1'), D), (('ACCEPT_RESERVATION', 'a1'), A),
              (('TOKEN', 'a1'), A), (('START', 'a1', 'n1'), A), (('START', 'a1', 'n1'), U), (('START', 'a1', 'n2'), D),
              live(0, 1)] + tokened('a2', 'q2') + [(('START', 'a2', 'n1'), D), (('START', 'a2', 'n2'), A), live(0, 2)])],
  'B16b identical retries are DUPLICATE in any mode': [
      (2, 0, reserved('a1', 'q1') + [(('HOLD',), A), (('RESERVE', 'a1', 'q1'), U), (('ACCEPT_RESERVATION', 'a1'), U),
              (('RESERVE', 'a2', 'q2'), D), (('STOP',), A), ('EXPECT', {'witness': 'HELD', 'business': 'STOPPING'}),
              (('RESERVE', 'a1', 'q1'), U), (('RESERVE', 'a2', 'q2'), D), live(1, 0)])],
  'B19 a reservation is released only after acceptance (D3)': [
      (1, 0, [(('RESERVE', 'a1', 'q1'), A), (('RELEASE', 'a1', 'BOUND_FENCE'), D), live(1, 0),
              (('ACCEPT_RESERVATION', 'a1'), A), (('RELEASE', 'a1', 'BOUND_FENCE'), A), live(0, 0)])],
  'B20 TERMINAL preconditions (D5)': [
      (5, 0, [(('RESERVE', 'a1', 'q1'), A)] + reserved('a2', 'q2') + tokened('a3', 'q3') + pending('a4', 'q4', 'n4')
             + consumed('a5', 'q5', 'n5') + [(('STOP',), A), (('TERMINALISE',), A), (('TERMINAL',), D),
              (('RELEASE', 'a2', 'BOUND_FENCE'), A), (('TERMINAL',), D), (('RELEASE', 'a3', 'BOUND_FENCE'), A),
              (('TERMINAL',), D), (('RECONCILE', 'a5', 'EFFECT', 'AUTHORISED'), A), (('TERMINAL',), D),
              (('ACCEPT_INTENT', 'a4'), A), (('TERMINAL',), D), (('RECONCILE', 'a4', 'NO_EFFECT', 'AUTHORISED'), A),
              (('TERMINAL',), D), (('ACCEPT_RESERVATION', 'a1'), A), (('TERMINAL',), D),
              (('RELEASE', 'a1', 'BOUND_FENCE'), A), (('TERMINAL',), A), ('EXPECT', {'business': 'TERMINAL'})]),
      (2, 0, [(('RESERVE', 'a1', 'q1'), A), (('HOLD',), A), (('STOP',), A), (('RECOVER', True, True), A),
              ('EXPECT', {'attempt a1': ('DISCARDED', None)}), (('TERMINALISE',), A), (('TERMINAL',), A)]),
      (2, 0, consumed('a1', 'q1', 'n1') + [(('REREGISTER',), A), (('TERMINALISE',), A), (('TERMINAL',), A)])],
  'B21 a discarded request is not retried under its key (D7)': [
      (1, 0, [(('RESERVE', 'a1', 'q1'), A), (('HOLD',), A), (('RECOVER', True, True), A),
              ('EXPECT', {'attempt a1': ('DISCARDED', None)}), live(0, 0), (('RESERVE', 'a1', 'q1'), D),
              (('RESERVE', 'a2', 'q1'), D), (('RESERVE', 'a2', 'q2'), A), live(1, 0)])],
  'B22 an EFFECT verdict needs authorised evidence (D8)': [
      (1, 1, consumed('a1', 'q1', 'n1') + [(('RECONCILE', 'a1', 'EFFECT', 'NONE'), D),
              (('RECONCILE', 'a1', 'EFFECT', 'WRONG_BINDING'), D), ('EXPECT', {'attempt a1': ('CONSUMED', 'n1')}),
              (('RECONCILE', 'a1', 'EFFECT', 'AUTHORISED'), A), (('RECONCILE', 'a1', 'EFFECT', 'AUTHORISED'), U),
              (('RECONCILE', 'a1', 'NO_EFFECT', 'AUTHORISED'), D), live(0, 1, 0, 0)])],
  'B23 an INDETERMINATE attempt is frozen (D9)': [
      (2, 0, consumed('a1', 'q1', 'n1') + [(('REREGISTER',), A), (('RESERVE', 'a1', 'q1'), D),
              (('ACCEPT_RESERVATION', 'a1'), D), (('TOKEN', 'a1'), D), (('START', 'a1', 'n1'), D),
              (('ACCEPT_INTENT', 'a1'), D), (('RECEIPT', 'a1'), D), (('CROSS', 'a1'), D),
              (('RELEASE', 'a1', 'BOUND_FENCE'), D), (('RECONCILE', 'a1', 'NO_EFFECT', 'AUTHORISED'), D),
              (('TIMEOUT', 'a1'), N), (('MISSING_RECEIPT', 'a1'), N),
              ('EXPECT', {'attempt a1': ('INDETERMINATE', 'n1')}), live(0, 1)])],
  'B24 releases and verdicts are accepted facts, applied only while ACTIVE (D4)': [
      (1, 1, tokened('a1', 'q1') + [(('HOLD',), A), (('RELEASE', 'a1', 'BOUND_FENCE'), D), live(1, 0),
              (('RECOVER', True, True), A), (('RELEASE', 'a1', 'BOUND_FENCE'), A), live(0, 0)]),
      (1, 1, consumed('a1', 'q1', 'n1') + [(('HOLD',), A), (('RECONCILE', 'a1', 'NO_EFFECT', 'AUTHORISED'), D),
              live(0, 1, 0, 0), (('RESERVE', 'a2', 'q2'), D), (('RECOVER', True, True), A),
              (('RECONCILE', 'a1', 'NO_EFFECT', 'AUTHORISED'), A), live(0, 1, 1, 1), (('RESERVE', 'a2', 'q2'), A)])],
  'B25 re-registration from TERMINALISING restarts in STOPPING (E6)': [
      (2, 0, reserved('a1', 'q1') + [(('STOP',), A), (('TERMINALISE',), A), (('REREGISTER',), A),
              ('EXPECT', {'business': 'STOPPING', 'reregistered': True, 'attempt a1': ('INDETERMINATE', None)}),
              (('TERMINALISE',), A), (('TERMINAL',), A), ('EXPECT', {'business': 'TERMINAL'})])],
  'B26 an incomplete recovery that returns an intent is APPLIED; its repeat is a NOOP (E7)': [
      (1, 0, pending('a1', 'q1', 'n1') + [(('HOLD',), A), (('RECOVER', True, False), A),
              ('EXPECT', {'witness': 'HELD', 'attempt a1': ('TOKEN', None), 'live_C': 0}),
              (('RECOVER', True, False), N), (('RECOVER', True, True), A), ('EXPECT', {'witness': 'ACTIVE'})])],
  'B27 a nonce freed by recovery may be bound to another attempt (E5)': [
      (2, 0, pending('a1', 'q1', 'n1') + [(('HOLD',), A), (('RECOVER', True, True), A)] + tokened('a2', 'q2')
             + [(('START', 'a2', 'n1'), A), ('EXPECT', {'attempt a2': ('INTENT_PENDING', 'n1'),
                                                         'attempt a1': ('TOKEN', None)})])],
  'B28 re-registration moves a never-accepted reservation into accepted C (E3)': [
      (1, 0, [(('RESERVE', 'a1', 'q1'), A), ('EXPECT', {'attempt a1': ('RESERVING', None), 'accepted_C': 0}),
              (('REREGISTER',), A), ('EXPECT', {'attempt a1': ('INDETERMINATE', None), 'accepted_C': 1,
                                                  'accepted_R': 0, 'live_R': 0, 'live_C': 1, 'N': 0})])],
}

B10_COMBOS = [(w, b) for w in ('ACTIVE', 'HELD') for b in ('OPEN', 'STOPPING', 'TERMINALISING', 'TERMINAL')]


def check_expect(impl, state, want):
    obs = impl.observe(state)
    got = {'live_R': obs['live'][0], 'live_C': obs['live'][1], 'N': obs['live'][2], 'credit': obs['credit'],
           'accepted_R': obs['accepted'][0], 'accepted_C': obs['accepted'][1], 'k': obs['k'],
           'witness': obs['witness'], 'business': obs['business'], 'reregistered': obs['reregistered']}
    for aid, req, phase, nonce, *_ in obs['attempts']:
        got['attempt ' + aid] = (phase, nonce)
    bad = {k: (v, got.get(k)) for k, v in want.items() if got.get(k) != v}
    return bad


def run_case(impl, k, m, steps):
    state = impl.initial(k, m)
    for i, (event, expected) in enumerate(steps):
        if event == 'EXPECT':
            bad = check_expect(impl, state, expected)
            if bad: return f'step {i}: observation mismatch {bad}'
            continue
        decision, state = impl.step(state, event)
        if decision.kind != expected:
            return f'step {i} {event}: expected {expected}, got {decision.kind} ({decision.code})'
    return None


def b10(impl):
    """Every witness x business combination: RESERVE and START admitted only in ACTIVE + OPEN.
    A TOKEN attempt cannot coexist with TERMINAL by events (A5), so those states are constructed directly."""
    failures = []
    for w, b in B10_COMBOS:
        state = impl.Root(2, 0, witness=w, business=b, attempts=(impl.Attempt('a1', 'q1', 'TOKEN'),))
        for event in (('RESERVE', 'a2', 'q2'), ('START', 'a1', 'n1')):
            want = A if (w, b) == ('ACTIVE', 'OPEN') else D
            got = impl.step(state, event)[0].kind
            if got != want: failures.append(f'{w}/{b} {event[0]}: expected {want}, got {got}')
    return failures


def b10b(impl):
    """D2: TOKEN on a RESERVED attempt applies only in ACTIVE + OPEN; on a TOKEN attempt it is a DUPLICATE everywhere."""
    failures = []
    for w, b in B10_COMBOS:
        for phase, want_open, want_other in (('RESERVED', A, D), ('TOKEN', U, U)):
            state = impl.Root(2, 0, witness=w, business=b, attempts=(impl.Attempt('a1', 'q1', phase),))
            want = want_open if (w, b) == ('ACTIVE', 'OPEN') else want_other
            got = impl.step(state, ('TOKEN', 'a1'))[0].kind
            if got != want: failures.append(f'{w}/{b} TOKEN on {phase}: expected {want}, got {got}')
    return failures


def x_vectors(impl):
    """X01 cross-root isolation and X02 delegated callers share one root (contract v1; dropped in v2)."""
    out = {}
    w = impl.World()
    script = [(('NEW_ROOT', 'r1', 1, 0, 'c1'), A), (('NEW_ROOT', 'r2', 1, 0, 'c2'), A),
              (('CALL', 'c1', ('RESERVE', 'a1', 'q1')), A), (('CALL', 'c2', ('RESERVE', 'a1', 'q1')), A),
              (('CALL', 'c2', ('ACCEPT_RESERVATION', 'a1')), A), (('CALL', 'c2', ('TOKEN', 'a1')), A),
              (('CALL', 'c1', ('START', 'a1', 'n1')), D),                  # r1's a1 has no released token
              (('CALL', 'c2', ('START', 'a1', 'n1')), A), (('CALL', 'c1', ('RESERVE', 'a2', 'q2')), D),
              (('CALL', 'c9', ('RESERVE', 'a3', 'q3')), D)]
    out['X01 cross-root isolation (contract v1)'] = run_world(impl, w, script)
    w = impl.World()
    script = [(('NEW_ROOT', 'r1', 2, 0, 'parent'), A), (('DELEGATE', 'parent', 'child'), A),
              (('DELEGATE', 'child', 'grandchild'), A), (('CALL', 'parent', ('RESERVE', 'a1', 'q1')), A),
              (('CALL', 'child', ('RESERVE', 'a2', 'q2')), A), (('CALL', 'grandchild', ('RESERVE', 'a3', 'q3')), D),
              (('DELEGATE', 'parent', 'child'), D), (('CALL', 'grandchild', ('RESERVE', 'a1', 'q1')), U)]
    out['X02 delegated callers share one root (contract v1)'] = run_world(impl, w, script)
    return out


def run_world(impl, w, script):
    for i, (event, expected) in enumerate(script):
        decision, w = impl.world_step(w, event)
        if decision.kind != expected:
            return f'step {i} {event}: expected {expected}, got {decision.kind} ({decision.code})'
    return None


def b18(impl):
    """Invalid inputs are rejected, never clamped."""
    bad = []
    cases = {
        'negative budget': lambda: impl.Root(-1, 0), 'non-integer budget': lambda: impl.Root(1.5, 0),
        'boolean budget': lambda: impl.Root(True, 0), 'negative allowance': lambda: impl.Root(1, -2),
        'consumed attempt without nonce': lambda: impl.Attempt('a1', 'q1', 'CONSUMED'),
        'reservation holding a nonce': lambda: impl.Attempt('a1', 'q1', 'RESERVED', nonce='n1'),
        'crossed without receipt': lambda: impl.Attempt('a1', 'q1', 'CONSUMED', nonce='n1', crossed=True),
        'unknown phase': lambda: impl.Attempt('a1', 'q1', 'REFUNDED'),
        'duplicate attempt id, conflicting contents': lambda: impl.Root(2, 0, attempts=(
            impl.Attempt('a1', 'q1', 'RESERVED'), impl.Attempt('a1', 'q2', 'TOKEN'))),
        'one nonce on two attempts': lambda: impl.Root(2, 0, attempts=(
            impl.Attempt('a1', 'q1', 'CONSUMED', nonce='n1'), impl.Attempt('a2', 'q2', 'CONSUMED', nonce='n1'))),
        'N not justified by distinct eligible attempts': lambda: impl.root_from_facts(2, 2, attempts=(
            impl.Attempt('a1', 'q1', 'NO_EFFECT', nonce='n1'),), claimed_no_effect=2),
        're-registered yet OPEN': lambda: impl.Root(1, 0, reregistered=True),
        'unknown event': lambda: impl.step(impl.initial(1, 0), ('REFUND', 'a1')),
        'unknown evidence label': lambda: impl.step(impl.initial(1, 0), ('RELEASE', 'a1', 'TRUST_ME')),
    }
    for name, make in cases.items():
        try:
            make(); bad.append(f'{name}: accepted')
        except impl.InvalidInput:
            pass
    return bad


def b18b(impl):
    """v3.1 E1, E10: the malformed inputs of section 10 raise InvalidInput, before any rule; two near misses are DENIED."""
    bad = []
    def invalid(label, make):
        try:
            make(); bad.append(f'{label}: accepted')
        except impl.InvalidInput:
            pass
        except Exception as exc:                       # malformed input must be InvalidInput, not another error
            bad.append(f'{label}: raised {type(exc).__name__}')
    root1, root0 = impl.initial(1, 0), impl.initial(0, 0)
    for op in (['RESERVE', 'a1', 'q1'], (), ('TOKEN',), ('RESERVE', 'a1'), ('HOLD', 'x'), ('TOKEN', 5),
               ('START', 'a1', ''), ('RESERVE', 'a1', ''), ('RECOVER', 1, True), ('RECOVER', True, 'yes'),
               ('RECOVER', 0, False), ('RELEASE', 'a1', 'AUTHORISED'), ('RECONCILE', 'a1', 'NO_EFFECT', 'BOUND_FENCE'),
               ('RECONCILE', 'a1', 'MAYBE', 'AUTHORISED'), ('NEW_ROOT', 'r1', 1, 0, 'c1')):
        invalid(f'step {op!r}', lambda op=op: impl.step(root1, op))
    invalid("step ('RESERVE', '', 'q1') at k = 0", lambda: impl.step(root0, ('RESERVE', '', 'q1')))
    for op in (('NEW_ROOT', '', 1, 0, 'c1'), ('NEW_ROOT', 'r1', True, 0, 'c1'), ('CALL', 'nobody', ('TOKEN',)),
               ('RESERVE', 'a1', 'q1')):
        invalid(f'world_step {op!r}', lambda op=op: impl.world_step(impl.World(), op))
    d, w1 = impl.world_step(impl.World(), ('NEW_ROOT', 'r1', 1, 0, 'c1'))
    if d.kind != A:
        return [f'setup NEW_ROOT r1: expected APPLIED, got {d.kind}']
    for op in (('DELEGATE', 'c1', ''), ('CALL', 'c1', ('NEW_ROOT', 'r2', 1, 0, 'c2'))):
        invalid(f'world_step {op!r}', lambda op=op: impl.world_step(w1, op))
    for op in (('CALL', 'nobody', ('TOKEN', 'a1')), ('NEW_ROOT', 'r1', -1, 0, 'c9')):
        try:
            kind = impl.world_step(w1, op)[0].kind
        except Exception as exc:
            kind = type(exc).__name__
        if kind != D: bad.append(f'world_step {op!r}: expected DENIED, got {kind}')
    return bad


def run_all(impl):
    results = {}
    def guarded(fn, *args):
        try:
            return fn(*args)
        except Exception as exc:                       # an implementation that crashes fails the vector
            return f'EXCEPTION {type(exc).__name__}: {exc}'
    for name, cases in VECTORS.items():
        errors = [e for e in (guarded(run_case, impl, k, m, steps) for k, m, steps in cases) if e]
        results[name] = errors[0] if errors else 'PASS'
    b10_result = guarded(b10, impl)
    results['B10 orthogonal modes'] = b10_result if isinstance(b10_result, str) else ('; '.join(b10_result) or 'PASS')
    b10b_result = guarded(b10b, impl)
    results['B10b token release only in ACTIVE + OPEN (D2)'] = (b10b_result if isinstance(b10b_result, str)
                                                                 else ('; '.join(b10b_result) or 'PASS'))
    xs = guarded(x_vectors, impl)
    if isinstance(xs, str):
        results['X01/X02 roots and delegation (contract v1)'] = xs
    else:
        for name, err in xs.items():
            results[name] = err or 'PASS'
    b18_result = guarded(b18, impl)
    results['B18 invalid inputs'] = b18_result if isinstance(b18_result, str) else ('; '.join(b18_result) or 'PASS')
    b18b_result = guarded(b18b, impl)
    results['B18b malformed input is InvalidInput before any rule (v3.1 E1, E10)'] = (
        b18b_result if isinstance(b18b_result, str) else ('; '.join(b18b_result) or 'PASS'))
    return results


if __name__ == '__main__':
    impl = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else 'budget_oracle')
    results = run_all(impl)
    width = max(map(len, results))
    for name in sorted(results, key=lambda s: (s.split()[0][0], int(''.join(c for c in s.split()[0][1:] if c.isdigit()) or 0), s)):
        print(f'{name:{width}s}  {results[name]}')
    failed = [n for n, r in results.items() if r != 'PASS']
    print(f'\n{len(results) - len(failed)}/{len(results)} vector groups pass against {impl.__name__}')
    sys.exit(1 if failed else 0)
