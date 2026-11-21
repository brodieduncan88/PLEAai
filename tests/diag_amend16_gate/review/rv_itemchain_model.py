"""Reviewer's small exhaustive enumerator (phase 2): the per-budget chain of items (gate note 4.3; Step 2 note 15) with a
courier that may lose its state and begin a new chain, and condition C-3 of the gate note (2.3).  Written by the reviewer
from the note's words; it is the reviewer's reading, not the author's model, and it is bounded, not a proof.

World (fixed bounds): run A has an UNKNOWN report from the start and may later get a verdict PASS (one event); run B may
get a recorded FAIL (one event).  Courier: a reading appends the notices it computes as due to its chain (k, A(k)) and
outbox; it may deliver the head of its outbox (the mailbox takes only the next item of a chain), lose its state (new chain
id, no memory, empty outbox), or make a statement for its chain at its current k.  Mailbox: holds items per chain in order;
COVERED holds when the last accepted statement's chain items 1..k are all held (no clock: freshness is out of scope here).
Notices due at a reading: FAIL_B if B failed; INTERRUPTED_A if A has no verdict; and VERDICT_A under one of two rules:
  'as_written'  C-3 as worded: only if this courier remembers having made INTERRUPTED_A
  'from_witness' derived from the witness's data alone: A has an UNKNOWN report and a verdict
Invariant SOUND: whenever COVERED, (B failed at the statement's reading -> FAIL_B held) and (INTERRUPTED_A held and A had
its verdict at the statement's reading -> VERDICT_A held).
    python rv_itemchain_model.py
"""
import collections, json, sys

MAX_CHAINS, MAX_READS = 2, 3


def due(world, mem, rule):
    a_verdict, b_failed = world
    out = []
    if b_failed: out.append('FAIL_B')
    if not a_verdict: out.append('INTERRUPTED_A')
    if a_verdict and (('INTERRUPTED_A' in mem) if rule == 'as_written' else True): out.append('VERDICT_A')
    return tuple(n for n in out if n not in mem)


def explore(rule):
    # state: world(a_verdict, b_failed), courier(chain, k, mem(frozenset of notice names made), outbox(tuple of (chain,k,name)), reads, chains_used,
    #        last_read_world), mailbox(held: frozenset of (chain,k,name), stmt: None|(chain,k,world_at_reading))
    init = ((False, False), (0, 0, frozenset(), (), 0, 1, None), (frozenset(), None))
    seen, q, parent = {init: None}, collections.deque([init]), {}
    bad = None
    while q:
        st = q.popleft(); world, cour, box = st
        chain, k, mem, outbox, reads, used, rworld = cour; held, stmt = box
        # invariant
        if stmt is not None:
            c, kk, w = stmt
            if all(any(h[0] == c and h[1] == i for h in held) for i in range(1, kk + 1)):
                names = {h[2] for h in held}
                if (w[1] and 'FAIL_B' not in names) or ('INTERRUPTED_A' in names and w[0] and 'VERDICT_A' not in names):
                    bad = st; break
        nxt = []
        if not world[0]: nxt.append(('witness: run A gets its verdict', ((True, world[1]), cour, box)))
        if not world[1]: nxt.append(('witness: run B FAIL recorded', ((world[0], True), cour, box)))
        if reads < MAX_READS:
            d = due(world, mem, rule); ob, kk = list(outbox), k
            for n in d:
                kk += 1; ob.append((chain, kk, n))
            nxt.append((f'courier: reading, makes {list(d)}', (world, (chain, kk, mem | set(d), tuple(ob), reads + 1, used, world), box)))
        if outbox:
            item = outbox[0]
            ok = item[1] == 1 + max([h[1] for h in held if h[0] == item[0]], default=0)
            nb = (held | {item}, stmt) if ok else box
            nxt.append((f'courier: delivers {item}' + ('' if ok else ' (refused: not next)'), (world, (chain, k, mem, outbox[1:] if ok else outbox, reads, used, rworld), nb)))
        if rworld is not None:
            nxt.append((f'courier: statement for chain {chain} at k={k}', (world, cour, (held, (chain, k, rworld)))))
        if used < MAX_CHAINS:
            nxt.append(('courier: loses its state; new chain', (world, (used, 0, frozenset(), (), reads, used + 1, None), box)))
        for label, s2 in nxt:
            if s2 not in seen:
                seen[s2] = (st, label); q.append(s2)
    trace = []
    if bad is not None:
        s = bad
        while seen[s] is not None:
            p, label = seen[s]; trace.append(label); s = p
        trace.reverse()
    return {'rule': rule, 'states': len(seen), 'SOUND broken': bad is not None, 'shortest trace': trace}


if __name__ == '__main__':
    res = [explore(r) for r in ('as_written', 'from_witness')]
    for r in res:
        print(json.dumps(r, indent=1))
    json.dump(res, open(sys.argv[1] if len(sys.argv) > 1 else 'rv_itemchain_model.json', 'w'), indent=1)
