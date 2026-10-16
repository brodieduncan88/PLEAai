# PLEA attempt-budget contract v3.1

11 October 2026 · errata release · supersedes attempt-budget contract v3 (11 October 2026, sha256 af3590f0…0c1c6b)

**Status.** v3 with errata E1–E11 applied. The owner adopted the errata as proposed in the v3 report. No accounting rule, invariant or decision D1–D9 changes. The errata pin down input validation, wording, test parameters, and readings that v3 left implicit. Tests new or changed in v3.1 (marked in section 10) were NOT RUN when this text was frozen. The decisions in section 12 are unchanged from v3: proposals the owner may revisit in a later revision.

**Sources.** Rev 2.3 consolidated changes, parts 2, 4, 5, 6, 7 and 12; rev 2.2 §3.4 (admission equation and replacement allowance); attempt-budget contract v2 and its review; contract v3 and its report (the reference author's notes on 15 ambiguities, the malformed-input differential and the B14 strength check).

## 0. What changed

**From v3 to v3.1 (errata).**

| erratum | v3 | v3.1 |
| --- | --- | --- |
| E1 | malformed input named only as unknown names, unknown labels and invalid budgets | a complete list, checked at evaluation step 1 (section 5); new test B18b |
| E2 | B11 said "only the stop and approved-recovery paths operate while held", which contradicted 5.6, 5.10, 5.13 and the DUPLICATE rule | B11 states exactly which operations can be APPLIED while held, and B17 checks it on every held state |
| E3 | accepted *C* counting INDETERMINATE after re-registration left implicit | stated in section 4; new test B28 |
| E4 | silent on whether `Root` and `Attempt` accept unreachable states | they check structure only (section 8) |
| E5 | T6 ("never moves") read against the free pool of section 2 | T6 is per transition; a freed nonce may be bound again (section 6); new test B27 |
| E6 | REREGISTER from TERMINALISING unstated | it goes to STOPPING (5.13); new test B25 |
| E7 | RECOVER's NOOP said "nothing changed" | NOOP means the state is unchanged; returning an intent to TOKEN is a change (5.12); new test B26 |
| E8 | "any later phase" in 5.2 and 5.3, with no phase order defined | the phases are listed (5.2, 5.3) |
| E9 | the oracle's mutant harness declared I1 alone for NEW-UNBOUNDED-REPLACEMENT | harness only: section 11 already says "I1 or I2"; the harness now accepts either |
| E10 | NEW\_ROOT's order and the type of root and caller identities unstated | identities are non-empty strings, checked at step 1; existence is checked before the budget (5.14) |
| E11 | B14 inherited from v2 without parameters; at *k* = 2 the budget alone denies the probe | B14 runs with free budget after re-registration (*k* = 3), so only the reduced state can deny |

Three mutants are added for the new tests (section 11).

**From v2 to v3.**

| item | v2 | v3 |
| --- | --- | --- |
| AC1 | cross-root isolation and delegated-caller tests, and the root-scope mutant, dropped from v1 | restored: X01, X02 and NEW-ROOT-SCOPE-LEAK (sections 2, 10, 11) |
| AC2 | release of a pending local intent untested | B09b |
| AC3 | no test that an EFFECT verdict earns no replacement credit | B07b |
| AC4 | B11 said "a stop leaves HELD" | reworded: a stop is accepted while held, and the run stays HELD |
| AC5 | live view silent on pending releases and pending verdicts | D4: neither creates capacity until the witness accepts it |
| AC6 | nine points left open | decisions D1–D9 (section 12); D2 tightens token release |
| AC7 | replacement-gate epoch rule attributed to a supplied review | it is G1-3 of the witness white paper, normative in Part 5 v4 |
| new | operation semantics described informally | sections 5 to 9 make each operation's decision, the observation and the test alphabet normative, so that independent implementations can be compared mechanically |
| new | — | gateway test G02b: a release of a pending intent followed by its acceptance |

## 1. Scope

The budget reference computes deterministic decisions and state transitions over trusted facts, for root runs and their delegated callers. It does not authenticate evidence, provide transactional storage, fence sandboxes, issue receipts or operate gates. Those are gateway and adapter obligations (section 10, G01–G06).

Passing this contract's reference tests does not establish authenticated evidence, atomic admission under concurrency, gate safety, full rev 2.3 conformance or unbounded correctness.

## 2. Identities, roots and delegation

- A **root run** has an immutable budget *k* and replacement allowance *m*: non-negative integers. Booleans and other types are invalid.
- **Attempt identities, request keys and nonces** are opaque, non-empty strings compared only for equality. So are **root identities and caller identities** (E10). Within a root, each attempt identity and each request key is bound to exactly one attempt and is never reused.
- A **nonce** is bound to an attempt by its START\_INTENT. It returns to the free pool only when verified recovery proves that START\_INTENT was never accepted (5.12). A nonce bound by an accepted START\_INTENT is never freed. A freed nonce is free: a later START\_INTENT may bind it to the same attempt or to another one (E5).
- **Callers and delegation (AC1).** Every caller is bound to exactly one root. A delegated caller is bound to its parent's root and gains no capacity: delegation never creates a root, a budget or an allowance. Attempts, request keys and nonces are scoped to their root; the same strings in two roots are unrelated.

## 3. Modes

- **Witness mode:** ACTIVE or HELD. **Business state:** OPEN, STOPPING, TERMINALISING or TERMINAL. The two are independent; all eight combinations can occur.
- Once the business state leaves OPEN it never returns to OPEN. Recovery never reopens a reduced run (rev 2.3 part 6, no authority resurrection).
- A re-registered run is never OPEN (part 5).

## 4. Attempts, phases and views

Each attempt is in exactly one phase:

| phase | meaning |
| --- | --- |
| RESERVING | reservation committed locally, not yet accepted by the witness |
| RESERVED | reservation accepted by the witness; token not yet released |
| TOKEN | reservation accepted, and its token released through the receipt barrier |
| INTENT\_PENDING | START\_INTENT committed locally, not yet accepted: charged, and not executable |
| CONSUMED | START\_INTENT accepted by the witness: consumption is final |
| NO\_EFFECT | consumed, then reconciled with an authorised no-effect verdict: still consumed, eligible for replacement credit |
| EFFECT | consumed, then reconciled with an authorised effect verdict |
| INDETERMINATE | left unresolved by re-registration: counts as started |
| RELEASED | reservation released before any START\_INTENT, on bound fencing or destruction evidence |
| DISCARDED | locally committed reservation that verified recovery proved was never accepted |

**Per-attempt facts.**

- *Nonce:* INTENT\_PENDING, CONSUMED, NO\_EFFECT and EFFECT hold exactly one nonce. INDETERMINATE keeps the nonce it had, if any. Every other phase holds none.
- *Receipt:* a covering receipt for the accepted START\_INTENT has been delivered. Possible only in CONSUMED, NO\_EFFECT, EFFECT and INDETERMINATE.
- *Crossed:* the attempt executed (its gate released) once. Crossed implies receipt.

**Views.** Every counting function computes exactly one view; no function mixes counters from different views.

| counter | phases counted |
| --- | --- |
| live *R* | RESERVING, RESERVED, TOKEN |
| live *C* | INTENT\_PENDING, CONSUMED, NO\_EFFECT, EFFECT, INDETERMINATE |
| accepted *R* | RESERVED, TOKEN, INTENT\_PENDING |
| accepted *C* | CONSUMED, NO\_EFFECT, EFFECT, INDETERMINATE |
| *N* (both views) | NO\_EFFECT (distinct attempts) |

credit = min(*N*, *m*).

Accepted *C* counts INDETERMINATE by rule (E3). Re-registration therefore moves an attempt that was still RESERVING, which the witness never accepted, into accepted *C*. After re-registration, accepted *C* is a conservative count of what may have started (D6), not strictly what the witness accepted.

- The **live local view** charges a locally committed START\_INTENT at once: its consumption must not disappear because receipt delivery is uncertain.
- The **accepted view** replays what the witness has accepted, so a pending intent still counts there as its accepted reservation. Accepted *C* never decreases.
- The **recovery view** (5.12) is the verified reconstruction of the accepted target. It may discard a proven never-accepted suffix.

**Admission** uses the live view. Admit a reservation iff the witness is ACTIVE, the business state is OPEN, and live *R* + live *C* − credit < *k*. Moving a reservation to an intent exchanges one *R* for one *C* and opens no slot. Credit is bounded credit, not a decrement of accepted *C*. Budget zero admits nothing from the empty state, whatever *m* is.

**D4 (AC5).** The reference receives releases and reconciliation verdicts only as facts the witness has accepted. A release or verdict that the witness has not accepted creates no capacity: until then the reservation stays in *R*, and the attempt stays charged without credit.

## 5. Operations

Each operation returns a **decision**: one of four kinds, with a reason code. Conformance compares the kinds; the codes are explanatory.

- **APPLIED:** the state changed.
- **NOOP:** a valid fact with no accounting effect. The state is unchanged.
- **DUPLICATE:** an identical retry of something already applied. The state is unchanged.
- **DENIED:** refused. The state is unchanged.

Malformed input is rejected with `InvalidInput` and never clamped. The list is complete (E1). An operation is malformed when:

- it is not a tuple whose first element is an operation name of section 9 for the function it is given to. `step` takes the single-root operations, and `world_step` takes the world operations;
- its number of arguments differs from section 9;
- an attempt identity, request key, nonce, root identity or caller identity is not a non-empty string;
- a label is outside its own operation's set. RELEASE takes BOUND\_FENCE, NONE or WRONG\_BINDING. RECONCILE takes a verdict NO\_EFFECT, EFFECT or UNKNOWN, and evidence AUTHORISED, NONE or WRONG\_BINDING. So AUTHORISED given to RELEASE, or BOUND\_FENCE given to RECONCILE, is malformed;
- an argument of RECOVER is not a boolean. The integers 0 and 1 are not booleans;
- CALL carries an operation that is malformed, or that is not a single-root operation;
- a budget or allowance is invalid (section 2). For NEW\_ROOT this is checked by its rule 2, after its rule 1 (E10).

Every other check is a rule of section 5, decided by APPLIED, NOOP, DUPLICATE or DENIED.

**Evaluation order (normative).**

1. Validate the whole operation against the list above, nested operations included (`InvalidInput`). No rule of section 5 is consulted first, so malformed input raises `InvalidInput` whatever the state. The one exception is NEW\_ROOT's budget and allowance, which its rule 2 checks after its rule 1 (E10).
2. If the operation names an attempt that is INDETERMINATE, the decision is DENIED (D9). TIMEOUT and MISSING\_RECEIPT are the exceptions: they are NOOP.
3. Apply the operation's own rules below, in the order listed. The first rule that matches decides.

The contract defines no order on phases. Where a rule names phases, it lists them (E8).

### 5.1 RESERVE(a, q): reserve a slot for attempt a under request key q

1. If a exists and is DISCARDED: DENIED (D7).
2. If a exists and is bound to q: DUPLICATE, in any phase and any mode.
3. If a exists, bound to another key: DENIED.
4. If q is bound to another attempt: DENIED.
5. If the witness is HELD or the business state is not OPEN: DENIED.
6. If live *R* + live *C* − credit ≥ *k*: DENIED.
7. Otherwise APPLIED: a new attempt a, in RESERVING, bound to q.

### 5.2 ACCEPT\_RESERVATION(a): the witness accepted a's reservation

1. If a is unknown or DISCARDED: DENIED.
2. If a is RESERVED, TOKEN, INTENT\_PENDING, CONSUMED, NO\_EFFECT, EFFECT or RELEASED: DUPLICATE (E8). INDETERMINATE was decided at step 2 of the evaluation order, so a is RESERVING below.
3. If the witness is HELD: DENIED.
4. Otherwise APPLIED: RESERVED.

### 5.3 TOKEN(a): a's token is released through the receipt barrier

1. If a is unknown, RELEASED or DISCARDED: DENIED.
2. If a is RESERVING: DENIED.
3. If a is TOKEN, INTENT\_PENDING, CONSUMED, NO\_EFFECT or EFFECT: DUPLICATE (E8). INDETERMINATE was decided at step 2 of the evaluation order.
4. If the witness is HELD or the business state is not OPEN: DENIED (**D2, new in v3**).
5. Otherwise (a is RESERVED) APPLIED: TOKEN.

### 5.4 START(a, n): a START\_INTENT binding nonce n is committed locally

1. If a is unknown: DENIED.
2. If a already holds a nonce: DUPLICATE when it is n, otherwise DENIED.
3. If n is held by another attempt: DENIED.
4. If the witness is HELD or the business state is not OPEN: DENIED.
5. If a is not TOKEN: DENIED. START\_INTENT needs an accepted reservation whose token was released; the two never share a batch.
6. Otherwise APPLIED: INTENT\_PENDING, with n bound. One live *R* becomes one live *C*.

### 5.5 ACCEPT\_INTENT(a): the witness accepted a's START\_INTENT

1. If a is unknown: DENIED.
2. If a is CONSUMED, NO\_EFFECT or EFFECT: DUPLICATE.
3. If a is not INTENT\_PENDING: DENIED.
4. If the witness is HELD: DENIED.
5. Otherwise APPLIED: CONSUMED. Consumption is final.

### 5.6 RECEIPT(a): a covering receipt for a's accepted START\_INTENT is delivered

1. If a is unknown, or not CONSUMED, NO\_EFFECT or EFFECT: DENIED.
2. If a's receipt was already delivered: DUPLICATE.
3. Otherwise APPLIED: receipt recorded. This applies in any mode, because receipts are historical facts.

### 5.7 CROSS(a): a's gate releases its sandbox, once

1. If a is unknown or not CONSUMED: DENIED.
2. If a has already crossed: DENIED. Crossing is one-shot, so a repeat is not a duplicate.
3. If a's receipt has not been delivered: DENIED.
4. If the witness is HELD or the business state is not OPEN: DENIED.
5. Otherwise APPLIED: crossed.

### 5.8 RELEASE(a, e): the witness accepted the release of a's reservation

e is the fencing evidence label: BOUND\_FENCE, NONE or WRONG\_BINDING.

1. If a is unknown or DISCARDED: DENIED.
2. If a is RELEASED: DUPLICATE, whatever e is.
3. If a is INTENT\_PENDING: DENIED. A never-accepted intent is resolved only by verified recovery (AC2).
4. If a is CONSUMED, NO\_EFFECT or EFFECT: DENIED. Consumption is final.
5. If a is RESERVING: DENIED (D3).
6. If e is not BOUND\_FENCE: DENIED.
7. If the witness is HELD: DENIED (D4).
8. Otherwise (a is RESERVED or TOKEN) APPLIED: RELEASED, in any business state.

### 5.9 RECONCILE(a, v, e): the witness accepted a reconciliation verdict for a

v is NO\_EFFECT, EFFECT or UNKNOWN; e is AUTHORISED, NONE or WRONG\_BINDING.

1. If a is unknown: DENIED.
2. If a is NO\_EFFECT or EFFECT: DUPLICATE when v names that phase and e is AUTHORISED, otherwise DENIED. Verdicts are final.
3. If a is not CONSUMED: DENIED.
4. If e is not AUTHORISED: DENIED (D8). This holds for both verdicts.
5. If the witness is HELD: DENIED (D4).
6. If v is UNKNOWN: NOOP. The attempt stays charged.
7. Otherwise APPLIED: the phase becomes v. The receipt and crossed facts are kept.

### 5.10 TIMEOUT(a), MISSING\_RECEIPT(a), CRASH(): facts that never refund

1. TIMEOUT or MISSING\_RECEIPT for an unknown a: DENIED.
2. Any other TIMEOUT or MISSING\_RECEIPT: NOOP. This includes INDETERMINATE attempts.
3. CRASH: NOOP.

### 5.11 HOLD(), STOP(), TERMINALISE(), TERMINAL()

**HOLD**

1. If the witness is HELD: DENIED. This slice has no incidents; replacing an open incident is the hold model's concern (G2-3).
2. Otherwise APPLIED: HELD, in any business state.

**STOP** (BREAK\_GLASS)

1. If the business state is not OPEN: DENIED.
2. Otherwise APPLIED: STOPPING. The witness mode is unchanged, so a held run stays HELD (AC4).

**TERMINALISE**

1. If the business state is not STOPPING: DENIED.
2. If the witness is HELD: DENIED.
3. Otherwise APPLIED: TERMINALISING.

**TERMINAL**

1. If the business state is not TERMINALISING: DENIED.
2. If the witness is HELD: DENIED.
3. If any attempt is RESERVING, RESERVED, TOKEN, INTENT\_PENDING or CONSUMED: DENIED (D5).
4. Otherwise APPLIED: TERMINAL.

### 5.12 RECOVER(approved, complete): an approved recovery batch is accepted on a held run

approved and complete are booleans.

1. If the witness is not HELD: DENIED.
2. If approved is not true: DENIED.
3. Otherwise compute the recovery view:
   - every RESERVING attempt becomes DISCARDED, because it was proven never accepted;
   - every INTENT\_PENDING attempt returns to TOKEN and its nonce is freed, because the accepted chain holds its reservation and released token but not its intent.

   Accepted consumption, nonces bound by accepted intents, *k*, *m* and the business state are unchanged. The witness becomes ACTIVE if complete is true, and otherwise stays HELD.
4. If the resulting state equals the input state: NOOP. Otherwise APPLIED (E7). Returning an INTENT\_PENDING attempt to TOKEN is a change. So RECOVER(true, false) with a pending intent is APPLIED, and the run stays HELD. Repeating it then finds nothing to change, and is a NOOP.

### 5.13 REREGISTER(): the run is re-registered under a new continuity as a reduced run

1. If the business state is TERMINAL: DENIED.
2. If the run is already re-registered: DENIED.
3. Otherwise APPLIED:
   - every RESERVING, RESERVED, TOKEN, INTENT\_PENDING and CONSUMED attempt becomes INDETERMINATE, keeping its nonce, receipt and crossed facts (D6);
   - RELEASED, DISCARDED, NO\_EFFECT and EFFECT attempts are unchanged;
   - the witness becomes ACTIVE, the business state STOPPING, and the run is marked re-registered.

   This holds from any business state other than TERMINAL. A TERMINALISING run returns to STOPPING (E6), as rev 2.3 part 5 says: the re-registered run restarts in STOPPING. T4 is not affected, because STOPPING is not OPEN. REREGISTER has no precondition on the witness mode.

### 5.14 World operations: several roots and delegated callers

Step 1 of the evaluation order checks root and caller identities as non-empty strings. It checks the operation inside CALL as a whole single-root operation, before CALL's rule 1 (E1, E10).

**NEW\_ROOT(r, k, m, c)**

1. If root r or caller c already exists: DENIED. This comes before the budget check, so NEW\_ROOT of an existing root with an invalid budget is DENIED (E10).
2. If *k* or *m* is invalid: `InvalidInput`.
3. Otherwise APPLIED: root r is created with budget *k* and allowance *m*, and caller c is bound to it.

**DELEGATE(p, c)**

1. If caller p is unknown or caller c is already bound: DENIED.
2. Otherwise APPLIED: c is bound to p's root. No capacity is created.

**CALL(c, op)**

1. If caller c is unknown: DENIED.
2. Otherwise op is applied to c's root, and the decision is op's decision.

## 6. Invariants

These must hold in every reachable state and on every transition.

**State invariants.**

- **I1.** live *C* ≤ *k* + *m*.
- **I2.** live *R* + live *C* − credit ≤ *k*.
- **I3.** accepted *C* ≤ live *C*, and accepted *R* + accepted *C* ≤ live *R* + live *C*.
- **I4.** No nonce is held by two attempts.
- **I5.** Crossed implies receipt.
- **I6.** A re-registered run is not OPEN.

**Transition invariants.**

- **T1.** Accepted *C* never decreases.
- **T2.** Live *C* decreases only through RECOVER.
- **T3.** *k* and *m* never change.
- **T4.** The business state never returns to OPEN.
- **T5.** RESERVE, TOKEN and START apply only in ACTIVE and OPEN.
- **T6.** On every transition, a nonce held by an attempt stays with that attempt. The one exception is RECOVER of a never-accepted intent, which frees it. T6 constrains single transitions (E5). A freed nonce returns to the pool of section 2, and a later START\_INTENT may bind it to another attempt.
- **T7.** Crossed never resets, and an attempt crosses at most once.
- **T8.** DENIED, DUPLICATE and NOOP never change the state; APPLIED always does.

**Reachability.** The largest live *C* reached equals *k* + *m* for *k* ≥ 1, and 0 for *k* = 0, in both views.

## 7. Observation (normative for conformance)

`observe(state)` returns exactly this dictionary:

| key | value |
| --- | --- |
| `k`, `m` | the budget and allowance |
| `witness` | ACTIVE or HELD |
| `business` | OPEN, STOPPING, TERMINALISING or TERMINAL |
| `reregistered` | boolean |
| `live` | the tuple (live *R*, live *C*, *N*) |
| `accepted` | the tuple (accepted *R*, accepted *C*, *N*) |
| `credit` | min(*N*, *m*) |
| `attempts` | a sorted list of tuples (attempt identity, request key, phase, nonce or None, receipt, crossed) |

## 8. Conformance interface

An implementation exposes a module with the following:

- `initial(k, m)`: the state of a new root, ACTIVE and OPEN, with no attempts.
- `step(state, op)`: returns `(decision, new_state)`. `op` is a tuple from the alphabet in section 9, and the input state is left unchanged. `decision.kind` is one of APPLIED, NOOP, DUPLICATE or DENIED, and `decision.code` is a string.
- `observe(state)`: the dictionary of section 7.
- `Root(k, m, witness='ACTIVE', business='OPEN', attempts=(), reregistered=False)` and `Attempt(aid, req, phase, nonce=None, receipt=False, crossed=False)`: constructors that build a state from facts. They raise `InvalidInput` on any of these:
  - a budget or allowance that is not a non-negative integer, or is a boolean;
  - an unknown mode or phase;
  - an empty or non-string identity;
  - a nonce missing where section 4 requires one, or present where it forbids one;
  - a receipt outside the phases that allow it, or a crossing without a receipt;
  - non-boolean flags;
  - two attempts with one identity or one request key;
  - one nonce on two attempts;
  - a re-registered OPEN run.
- `Root` and `Attempt` check structure only, and the list above is exhaustive (E4). They accept structurally valid states that no sequence of operations reaches. Examples are a run over its budget, TERMINAL with unresolved attempts, or a RESERVED attempt in a TERMINAL run. B10 and B10b need such states. I1 and I2 are therefore checked over transitions from reachable states. The constructors do not enforce them.
- `root_from_facts(k, m, attempts=(), claimed_no_effect=None, **modes)`: as `Root`, but also rejects a claimed *N* that differs from the number of distinct NO\_EFFECT attempts. Its `modes` are witness, business and reregistered, and any other keyword is `InvalidInput`. `claimed_no_effect` is `None` (no claim) or a non-negative integer that is not a boolean.
- `InvalidInput`: the exception class.
- `World()` (an empty world) and `world_step(world, op)` for the operations in 5.14.

This module may be a thin layer over the implementation's own API. It must contain no accounting logic of its own.

## 9. Operation alphabet (frozen for B17)

**Single root:**

```
('RESERVE', a, q)        ('ACCEPT_RESERVATION', a)   ('TOKEN', a)          ('START', a, n)
('ACCEPT_INTENT', a)     ('RECEIPT', a)              ('CROSS', a)          ('RELEASE', a, e)
('RECONCILE', a, v, e)   ('TIMEOUT', a)              ('MISSING_RECEIPT', a)
('CRASH',)  ('HOLD',)  ('STOP',)  ('TERMINALISE',)  ('TERMINAL',)  ('RECOVER', approved, complete)  ('REREGISTER',)
```

**World:** `('NEW_ROOT', r, k, m, c)`, `('DELEGATE', p, c)`, `('CALL', c, op)`.

**Labels:**

- e for RELEASE: BOUND\_FENCE, NONE, WRONG\_BINDING;
- v: NO\_EFFECT, EFFECT, UNKNOWN;
- e for RECONCILE: AUTHORISED, NONE, WRONG\_BINDING;
- approved and complete: true or false.

**B17 bound:**

- *k*, *m* ∈ {0, 1, 2};
- attempt identities a1–a5, request keys q1–q5, nonces n1–n5;
- every label value;
- 155 single-root operations at every state;
- no attempt-identity reuse.

## 10. Declared tests

All reference tests are NOT RUN at declaration. Expected behaviour follows from sections 2 to 6. Tests new or changed in v3.1 are marked.

**Carried from v2, with changes.**

- **B01–B10, B12, B13, B15, B16 and B18** as declared in v2.
- **B11 (reworded in v3, made exact in v3.1, E2).** While the witness is HELD, only STOP, RECOVER, RECEIPT and REREGISTER can be APPLIED. Every other operation is DENIED, DUPLICATE or NOOP by its own rules in section 5. A stop is accepted while held, and the run stays HELD. Recovery to ACTIVE never reopens a reduced business state. B17 checks the first sentence on every transition from a reachable held state.
- **B14 (parameters fixed in v3.1, E11).** Re-registration lifecycle, run with free budget after re-registration so that only the reduced state can deny. With *k* = 3 and *m* = 0: a1 consumed and a2 with its token released, then REREGISTER is APPLIED and the run is STOPPING and re-registered. Live *R* + live *C* − credit is then 2 < 3, and these follow in order:
    1. RESERVE of a new attempt a3 is DENIED.
    2. START(a2, n2) is DENIED.
    3. REREGISTER is DENIED.
    4. TERMINALISE is APPLIED, then TERMINAL is APPLIED.
    5. REREGISTER is DENIED.

    Run at *k* = 2, the RESERVE is denied by the budget whatever the business state, so the test could not fail for the defect it is declared against.
- **B17 (with v3 bounds).** Explore the frozen bound of section 9 to exhaustion. Compare every reachable transition and its decision kind, and the observation after it, against an independently written oracle amended to this contract. Enforce I1–I6 and T1–T8, the reachability statement and B11's held rule.

**Restored and added for the AC findings.**

- **B07b (AC3).** An authorised EFFECT verdict earns no replacement credit. With *k* = 1 and *m* = 1, a reconciled-EFFECT attempt leaves no room for a reservation.
- **B09b (AC2).** RELEASE of an INTENT\_PENDING attempt is DENIED even with BOUND\_FENCE evidence. Live *C* is unchanged.
- **X01 (AC1).** Cross-root isolation. The same attempt and request strings in two roots are independent. A start in one root cannot use a token released in the other. An unknown caller is DENIED.
- **X02 (AC1).** Delegated callers share one root. A parent and its delegate chain consume one budget. A delegate's reservation beyond *k* is DENIED. Delegating an already bound caller is DENIED. A delegate's identical retry of the parent's reservation is a DUPLICATE.

**New for the v3 decisions.**

- **B10b (D2).** For every witness and business combination, TOKEN on a RESERVED attempt is APPLIED only in ACTIVE and OPEN, and DENIED otherwise. TOKEN on a TOKEN attempt is a DUPLICATE in every combination.
- **B16b.** Identical retries are answered DUPLICATE in any mode. A reservation's retry is a DUPLICATE while held and after a stop, and so is its acceptance's retry while held. A new reservation in those modes is DENIED.
- **B19 (D3).** RELEASE of a RESERVING reservation is DENIED. The same RELEASE after the reservation is accepted is APPLIED.
- **B20 (D5).** TERMINAL is DENIED while any attempt is RESERVING, RESERVED, TOKEN, INTENT\_PENDING or CONSUMED, and APPLIED once every attempt is RELEASED, DISCARDED, NO\_EFFECT, EFFECT or INDETERMINATE.
- **B21 (D7).** After verified recovery discards a reservation, retrying the same request is DENIED, under its old attempt identity or a new one. A new request key is admitted when the budget allows.
- **B22 (D8).** An EFFECT verdict with evidence NONE or WRONG\_BINDING is DENIED. With AUTHORISED it is APPLIED, and its repeat is a DUPLICATE. A later NO\_EFFECT verdict for the same attempt is DENIED.
- **B23 (D9).** On an INDETERMINATE attempt, every operation that names it is DENIED, identical retries included. TIMEOUT and MISSING\_RECEIPT are NOOP.
- **B24 (D4).** RELEASE and RECONCILE are DENIED while held, and no capacity appears. After a completed recovery, the same facts are APPLIED and the capacity follows.

**New in v3.1, for the errata.**

- **B18b (E1, E10).** Each input below raises `InvalidInput` and returns no state.
    - **Single-root operations,** given to a new root with *k* = 1 and *m* = 0:
        - a list instead of a tuple, and an empty tuple;
        - ('TOKEN',), ('RESERVE', 'a1') and ('HOLD', 'x');
        - ('TOKEN', 5), ('START', 'a1', '') and ('RESERVE', 'a1', '');
        - ('RECOVER', 1, True), ('RECOVER', True, 'yes') and ('RECOVER', 0, False);
        - ('RELEASE', 'a1', 'AUTHORISED'), ('RECONCILE', 'a1', 'NO\_EFFECT', 'BOUND\_FENCE') and ('RECONCILE', 'a1', 'MAYBE', 'AUTHORISED');
        - a world operation, ('NEW\_ROOT', 'r1', 1, 0, 'c1').
    - **On a new root with *k* = 0:** ('RESERVE', '', 'q1'). The budget rule would deny it, but validation comes first.
    - **World operations:**
        - on an empty world: ('NEW\_ROOT', '', 1, 0, 'c1'), ('NEW\_ROOT', 'r1', True, 0, 'c1'), ('CALL', 'nobody', ('TOKEN',)) and a single-root operation, ('RESERVE', 'a1', 'q1');
        - on a world with root r1 and caller c1: ('DELEGATE', 'c1', ''), and ('CALL', 'c1', ('NEW\_ROOT', 'r2', 1, 0, 'c2')).
    - **These are DENIED, not malformed,** on a world with root r1 and caller c1:
        - ('CALL', 'nobody', ('TOKEN', 'a1'));
        - ('NEW\_ROOT', 'r1', -1, 0, 'c9'), whose existence check comes first (E10).
- **B25 (E6).** With *k* = 2: a1 reserved and accepted, then STOP and TERMINALISE are APPLIED. REREGISTER is APPLIED, and the run is STOPPING and re-registered, with a1 INDETERMINATE. TERMINALISE is APPLIED again, and then TERMINAL is APPLIED.
- **B26 (E7).** With *k* = 1: a1 with an intent pending under n1, then HOLD. RECOVER(true, false) is APPLIED: the witness stays HELD, a1 is TOKEN without a nonce, and live *C* is 0. Repeating RECOVER(true, false) is a NOOP. RECOVER(true, true) is then APPLIED, and the witness is ACTIVE.
- **B27 (E5).** With *k* = 2: a1 with an intent pending under n1, then HOLD and RECOVER(true, true). Then a2 is reserved, accepted and given its token, and START(a2, n1) is APPLIED. a2 holds n1, and a1 is TOKEN without a nonce.
- **B28 (E3).** With *k* = 1: RESERVE(a1, q1) is APPLIED and a1 stays RESERVING; accepted *C* is 0. REREGISTER is then APPLIED: a1 is INDETERMINATE, and accepted *C* is 1. The live and accepted tuples (*R*, *C*, *N*) are both (0, 1, 0).

**Gateway tests (NOT RUN; need the gateway).**

- **G01–G06** as declared in v2:
  - G01: last-slot race in a real transactional store;
  - G02: crash and receipt barriers;
  - G03: authenticated release reports;
  - G04: timed holder and nonce races;
  - G05: a replacement gate at the current stop epoch, including stop-installation races;
  - G06: witness-profile defects.
- **G02b (new).** Release-then-accept.
  1. A START\_INTENT is committed locally, and its submission to the witness is in flight.
  2. A release of that attempt is requested. The gateway must refuse it.
  3. The witness then accepts the START\_INTENT.
  4. Assert that no slot was freed in between, and that accepted *C* counts the attempt.

  This is the real-world consequence that the pure reference cannot express: once released, a pure reference never sees its intent accepted.

## 11. Mutation obligations

Each defect is planted one at a time. The reference's tests must detect it, with the detecting test declared before execution.

| mutant | must be detected by |
| --- | --- |
| A\_REFUND: budget returned after START\_INTENT through reconciliation (its original meaning) | B06, T1 |
| NEW-STALE-ADMISSION-READ: admission blind to in-flight reservations (a stand-in for G01) | B02, I2 |
| NEW-NO-PERMANENT-CONSUMPTION | B09, T1 |
| NEW-UNBOUNDED-REPLACEMENT | B06, and I1 or I2 |
| NEW-EFFECT-EARNS-CREDIT | B07b |
| NEW-HELD-ADMISSION | B10, B11 |
| NEW-REDUCED-ADMISSION | B10, B11, B14 |
| NEW-RELEASE-WITHOUT-EVIDENCE | B09 |
| NEW-RECOVERY-REFUNDS-ACCEPTED | B12, T1 |
| NEW-TIMEOUT-REFUND | B05, T2 |
| NEW-NONCE-REUSE | B16 |
| NEW-ROOT-SCOPE-LEAK: delegation hands out a fresh budget | X02 |
| NEW-REREGISTER-RELEASES | B13 |
| NEW-START-WITHOUT-TOKEN | B15 |
| NEW-RECOVERY-REOPENS | B11, T4 |
| NEW-CROSS-WITHOUT-RECEIPT | B04 |
| NEW-PENDING-RELEASE | B09b, T2 |
| NEW-TOKEN-OUTSIDE-ACTIVE-OPEN (new in v3) | B10b, T5 |
| NEW-LAX-INPUT: RECOVER takes any value as a flag, by truthiness (new in v3.1) | B18b |
| NEW-INCOMPLETE-RECOVERY-KEEPS-INTENT: an incomplete recovery batch leaves never-accepted intents pending (new in v3.1) | B26 |
| NEW-REREGISTER-KEEPS-TERMINALISING: REREGISTER leaves a TERMINALISING run TERMINALISING (new in v3.1) | B25 |

A mutant's patch must not build a state that the contract forbids on the way, such as a re-registered OPEN run. If it does, an implementation that refuses such states detects the patch, not the defect. A detection counts only when the declared test fails on a decision or an observation. An exception raised by the patch does not count.

B\_TIMED and C\_NONCE need their original paused-holder and late-nonce schedules, so they belong to G04. DEV, CTRL\_20 and CTRL\_21 are witness-integration defects (G06). Pure-function approximations of them are not claimed.

## 12. Decisions on the points v2 left open

| | decision | why | source |
| --- | --- | --- | --- |
| D1 | Each acceptance is a fact about one event. The reference does not order acceptances of different attempts against each other, or against a stop | accounting does not depend on it; ordering a crossing against a stop is the gate's job (S2b, S2c) | part 7 |
| D2 | **Token release needs witness ACTIVE and business OPEN.** v2 was silent, and the earlier oracle allowed it in any mode | the receipt gate requires the event's epoch to still bind, and after BREAK\_GLASS it does not (S6: stale-epoch tokens start nothing); admission reductions stop new work at once; a hold keeps gates closed while integrity is in question. The tightening costs no liveness: a reserved slot can still be released, and the token can be released after recovery | parts 2, 3, 6 |
| D3 | A reservation can be released only after the witness accepted it, never while RESERVING | a locally committed reservation may still be accepted; releasing it locally would free a slot twice. It is resolved by acceptance or by verified recovery | parts 2, 6 |
| D4 | RELEASE and RECONCILE are accepted facts. The reference applies them only while the witness is ACTIVE. A verdict carried in a recovery batch takes effect once the run is ACTIVE again. Nothing unaccepted creates capacity | a held run accepts only a stop or an approved recovery batch; capacity follows the accepted chain | parts 2, 6 |
| D5 | TERMINAL needs every attempt RELEASED, DISCARDED, NO\_EFFECT, EFFECT or INDETERMINATE | TERMINAL needs the terminalising barrier and reconciliation, and waits until no lease remains | parts 4, 7 |
| D6 | Re-registration has no anchor position in the reference. Accepted events count as at or before the anchor, pending ones as beyond it. Every non-final attempt becomes INDETERMINATE | beyond the anchor, consumption and reductions apply and releases do not; non-final attempts count as started | part 5 |
| D7 | A DISCARDED attempt keeps its identity and request key. Retrying that request is DENIED; the caller submits a new request key | a discarded request never happened in the accepted chain. Re-using its key would make an idempotency key mean two different requests | parts 2, 6 |
| D8 | Every reconciliation verdict, effect or no-effect, needs authorised evidence bound to the attempt | v2 stated it for no-effect only. An unauthenticated verdict must not change the record either way | part 1 (forged NO\_EFFECT\_PROVED), contract v2 |
| D9 | An INDETERMINATE attempt is frozen. Every operation naming it is DENIED, identical retries included. TIMEOUT and MISSING\_RECEIPT are NOOP | it counts as started and cannot be resolved inside the re-registered run. Continuing the work needs a new run whose budget counts it | part 5 |

## 13. What passing does not establish

- The reference decides over trusted facts. It does not authenticate evidence, and its labels (BOUND\_FENCE, AUTHORISED) stand for checks the gateway must make (G03).
- Atomic admission under concurrent callers needs a real store (G01). A pure function can only show the sequential rule.
- Epochs, stop completion and replacement gates belong to the gate (G05, and the witness white paper's G1-1 and G1-3).
- B17 is bounded by section 9. Lockstep compares one concrete representative per state class, so hidden state outside `observe` could differ on another path to the same class.
- Malformed input lies outside the B17 alphabet. B18b samples it, and section 5's list defines it.
