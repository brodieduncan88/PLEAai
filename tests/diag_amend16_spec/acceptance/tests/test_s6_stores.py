"""Section 6 at the mailbox: evidence objects, quotas and rooms, retirement, orphans and E-Q-6, reading back (E-R-2),
binding and gaps (E-B-1 to E-B-6).  Specification version 5 (E-Q-4 as changed for F34)."""
import json
import os
import threading

from acc import AccTest, acc
from mbutil import error
from fixtures.crypto import Hb, H, canonical, verify_object
from fixtures.form3 import A0, A_next, id_notice, id_alarm, id_epochal, basis_equivocation


def report_bytes(root, tag='r'):
    rep = {'kind': 'EFFECT_REPORT', 'root': root, 'aid': tag, 'nonce': 'n-' + os.urandom(8).hex(), 'claim': 'EFFECT',
           'result_digest': os.urandom(32).hex(), 'signer': '2' * 64, 'signature': '3' * 128}
    return rep, canonical(rep).encode()


class Evidence(AccTest):
    @acc(id='S6-OBJ-01', rules=['E-1', 'E-2', '11-INTERFACE'], cap='NONE',
         catches='a mailbox whose evidence id is not Hb(bytes), that does not sign HELD, or that does not give the bytes back')
    def test_store_and_read(self):
        d, h, clock = self.mailbox()
        rep, data = report_bytes(d.root)
        st, held = d.store_evidence(data)
        self.assertEqual(st, 200)
        self.assertTrue(d.verify_mb(held), 'HELD is signed by the mailbox')
        self.assertIn(Hb(data), canonical(held), 'HELD names the id Hb(bytes)')
        st, raw = d.get_evidence(Hb(data))
        self.assertEqual((st, raw), (200, data), 'GET /evidence gives the bytes')
        st2, held2 = d.store_evidence(data)
        self.assertEqual(st2, 200, 'storing an id already held answers as before (E-2)')
        st, raw = d.get_evidence('0' * 64)
        self.assertEqual(st, 404)

    @acc(id='S6-OBJ-02', rules=['E-3', 'E-B-5'], cap='CAP-KEY',
         catches='a mailbox that keeps (part of) an object larger than OBJ_MAX')
    def test_obj_max(self):
        d, h, clock = self.mailbox(OBJ_MAX=4096)
        data = b'{"x":"' + b'y' * 5000 + b'"}'
        st, body = d.store_evidence(data)
        self.assertEqual(st, 413, 'larger than OBJ_MAX: 413')
        self.assertEqual(d.get_evidence(Hb(data))[0], 404, 'nothing is kept')

    @acc(id='S6-QUOTA-EVID-01', rules=['E-Q-1', 'E-Q-3'], cap='CAP-KEY',
         catches='a mailbox without a per-budget evidence quota, or one that lets one budget use another\'s')
    def test_evid_budget_quota(self):
        d, h, clock = self.mailbox(n_budgets=2, EVID_BUDGET_QUOTA=20000, OBJ_MAX=8000)
        d2 = self.extra_drivers[0]
        refusedq = None
        for i in range(10):
            st, body = d.store_evidence(report_bytes(d.root, 'p' * 5000 + str(i))[1])
            if st != 200:
                refusedq = (st, body); break
        self.assertIsNotNone(refusedq, 'the budget\'s evidence quota was never reached')
        self.assertEqual(refusedq[0], 507); self.assertIn('EVID_BUDGET_QUOTA', canonical(refusedq[1]), '507 naming the quota')
        self.assertEqual(d2.store_evidence(report_bytes(d2.root)[1])[0], 200, 'another budget still has its room')

    @acc(id='S6-QUOTA-GLOBAL-01', rules=['E-Q-1', '8.2', 'E-B-4'], cap='CAP-KEY',
         catches='a mailbox that does not say GLOBAL_QUOTA when another budget used up the global room and so made a gap')
    def test_global_quota(self):
        d, h, clock = self.mailbox(n_budgets=2, EVID_BUDGET_QUOTA=40000, EVID_GLOBAL_QUOTA=30000, OBJ_MAX=8000)
        d2 = self.extra_drivers[0]
        for i in range(10):
            if d.store_evidence(report_bytes(d.root, 'p' * 5000 + str(i))[1])[0] != 200:
                break
        rep, data = report_bytes(d2.root, 'q' * 5000)
        st, body = d2.store_evidence(data)
        self.assertEqual(st, 507, 'the mailbox\'s global evidence room is used up')
        self.assertIn('EVID_GLOBAL_QUOTA', canonical(body))
        d2.budget.new_run(); d2.open_epoch()
        e = d2.equivocation('r', {'K-CONFLICT'}, [{'evidence_id': Hb(data), 'size': len(data), 'where': 'NOT_HELD', 'reason': 'QUOTA'}])
        self.assertEqual(d2.deliver(e)[0], 200)
        s = d2.assert_not_covered('EVIDENCE_GAP', msg='budget 2 has a gap')
        self.assertIn('GLOBAL_QUOTA', d2.c.st_text(s), 'and its status says GLOBAL_QUOTA is why (E-Q-1, 8.2)')


class Rooms(AccTest):
    def _fill(self, d, make, limit=200):
        for i in range(limit):
            st, body = d.deliver(make(i))
            if st != 200:
                return st, body
        self.fail('the room was never filled')

    @acc(id='S6-ROOM-NOTICE-01', rules=['E-Q-2', 'E-Q-3', 'E-X-4', 'C-1.6', '8.2', 'N-6', 'SAF-7'], cap='CAP-KEY',
         catches='a mailbox whose notice room shares space with alarms or observation parts, or that stays COVERED after refusing a notice')
    def test_notice_quota(self):
        d, h, clock = self.covered_driver(NOTICE_QUOTA=3000, ITEM_MAX=4096)
        st, body = self._fill(d, lambda i: d.notice(extra={'pad': 'n' * 600}))
        error(self, st, body, d, 507, None, msg='notices fill NOTICE_QUOTA')
        self.assertIn('NOTICE_QUOTA', canonical(body), '507 names the room')
        s = d.assert_not_covered('NOTICES_REFUSED', msg='at once after a notice is refused for room (C-1.6)')
        self.assertEqual(d.deliver(d.alarm(d.token(d.challenge())))[0], 200, 'an alarm still has its room (ALARM_RESERVE)')
        self.assertEqual(d.deliver(d.part(d.token(d.challenge()), d.budget.n))[0], 200, 'an observation part still has its room (OBS_QUOTA)')
        self.assertEqual(d.deliver(d.notice(extra={'pad': 'n' * 600}))[0], 507, 'notices are still refused')
        self.assertIn('NOTICE', d.c.st_text(d.status()), 'the status says which room')

    @acc(id='S6-ROOM-OBS-01', rules=['E-Q-2', 'E-Q-3', 'E-Q-3a', 'C-1.6', '8.2'], cap='NONE',
         catches='a mailbox that refuses notices or alarms when OBS_QUOTA is full, or does not say ITEMS_REFUSED')
    def test_obs_quota(self):
        d, h, clock = self.covered_driver(OBS_QUOTA=6000, ITEM_MAX=4096)
        st, body = self._fill(d, lambda i: d.part(d.token(d.challenge()), d.budget.n, pad=900))
        self.assertEqual(st, 507); self.assertIn('OBS_QUOTA', canonical(body))
        d.assert_not_covered('ITEMS_REFUSED', msg='an observation part refused for room')
        self.assertEqual(d.deliver(d.notice())[0], 200, 'notices are still taken (E-Q-3a)')
        self.assertEqual(d.deliver(d.alarm(d.token(d.challenge())))[0], 200, 'alarms are still taken')
        ch = d.challenge()
        st, body = d.send_statement(d.statement(ch, reading='REFRESH'))
        self.assertEqual(st, 507, 'a statement is refused for room when OBS_QUOTA is full')

    @acc(id='S6-ROOM-INDEX-01', rules=['E-Q-2', 'E-Q-3', 'E-Q-3a', 'E-X-4', '8.2'], cap='CAP-DB',
         catches='a mailbox that lets observation parts take INDEX_RESERVE, or refuses notices, alarms or EPOCH_OPEN there')
    def test_index_reserve(self):
        d, h, clock = self.covered_driver(INDEX_QUOTA=12000, INDEX_RESERVE=3000, ITEM_MAX=4096)
        st, body = self._fill(d, lambda i: d.part(d.token(d.challenge()), d.budget.n), limit=400)
        self.assertEqual(st, 507); self.assertIn('INDEX_QUOTA', canonical(body), 'down to the reserve: a part is refused naming INDEX_QUOTA')
        self.assertEqual(d.deliver(d.notice())[0], 200, 'a notice about a run may use the reserve')
        self.assertEqual(d.deliver(d.alarm(d.token(d.challenge())))[0], 200, 'an alarm may use the reserve')
        d.open_epoch('COURIER_STATE_LOST')                                   # expects 200: an EPOCH_OPEN may use the reserve
        d.assert_not_covered('ITEMS_REFUSED')
        st, body = self._fill(d, lambda i: d.notice(), limit=400)
        self.assertEqual(st, 507, 'when INDEX_QUOTA is full nothing is taken')
        st, body = d.deliver(d.alarm(d.token(d.challenge())))
        self.assertEqual(st, 507, 'not even an alarm (E-X-4: ITEMS_REFUSED)')

    @acc(id='S6-RETIRE-ALARM-01', rules=['E-Q-4', 'E-Q-6', 'E-Q-3a', 'I-ID-2'], cap='CAP-DB',
         catches='(version 5, F34) a mailbox that stores an alarm body before dropping the oldest, so a full ALARM_RESERVE refuses alarms')
    def test_alarm_drop_before_store(self):
        IM = 4096
        d, h, clock = self.covered_driver(ITEM_MAX=IM, ALARMS_KEEP=2, ALARM_RESERVE=2 * IM)
        bodies = []
        for i in range(5):
            a = d.alarm(d.token(d.challenge()), reasons=[('WITNESS_UNREACHABLE', {'sha256': '0' * 64, 'length': 3, 'pad': 'a' * (IM - 900)})])
            st, body = d.deliver(a)
            self.assertEqual(st, 200, f'alarm {i}: an alarm body always has room (E-X-4): {st} {str(body)[:200]}')
            bodies.append(a)
        st, ans = d.items()
        pos = d.c.items_positions(ans)
        alarm_k = [p.get('k') for p in pos if (p.get('item') or {}).get('kind') == 'OBSERVATION_INCOMPLETE']
        self.assertLessEqual(len(alarm_k), 2, 'at most ALARMS_KEEP alarm bodies are held')
        self.assertEqual(sorted(alarm_k), sorted(x['k'] for x in bodies[-2:]), 'the oldest were dropped, the newest kept')
        self.assertEqual(len([p for p in pos if p.get('k') in [x['k'] for x in bodies]]), 5, 'every alarm\'s index entry is kept')

    @acc(id='S6-RETIRE-ALARM-02', rules=['E-Q-4', 'DL-1', 'DL-3'], cap='CAP-DB',
         catches='(version 6, F37) a mailbox that drops the oldest alarm bodies for an alarm it then refuses')
    def test_alarm_drop_only_when_stored(self):
        d, h, clock = self.covered_driver(ALARMS_KEEP=2)
        held = []
        for _ in range(2):
            a = d.alarm(d.token(d.challenge())); self.assertEqual(d.deliver(a)[0], 200); held.append(a['k'])
        far = d.alarm(d.token(d.challenge())); far = d.resign(far, k=d.k + 5)
        self.assertEqual(d.deliver(far, advance=False)[0], 409, 'an alarm at a wrong position is refused (DL-3)')
        bad = dict(d.alarm(d.token(d.challenge())), signature='00' * 64)
        self.assertIn(d.deliver(bad, advance=False)[0], (400, 403), 'an alarm not signed by the courier is refused (DL-1)')
        st, ans = d.items()
        kept = sorted(p.get('k') for p in d.c.items_positions(ans) if (p.get('item') or {}).get('kind') == 'OBSERVATION_INCOMPLETE')
        self.assertEqual(kept, held, 'the refused alarms dropped no body: bodies are dropped only when the new alarm will be stored')

    @acc(id='S6-RETIRE-NEVER-01', rules=['E-Q-4', 'E-2', 'SAF-6'], cap='NONE',
         catches='a mailbox whose retirement drops a notice, its receipt or evidence a held notice binds')
    def test_retirement_never(self):
        d, h, clock = self.covered_driver()
        rep, data = report_bytes(d.root)
        d.store_evidence(data)
        n = d.equivocation('r', {'K-CONFLICT'}, [{'evidence_id': Hb(data), 'size': len(data), 'where': 'HELD'}])
        st, b1 = d.deliver(n); self.assertEqual(st, 200)
        for _ in range(3):
            d.deliver(d.part(d.token(d.challenge()), d.budget.n)); d.cover('REFRESH')
        d.open_epoch('COURIER_STATE_LOST'); d.cover('FROM_ZERO')
        clock.advance(10 ** 6)
        self.optional(h, 'run_maintenance')()
        self.assertEqual(d.get_evidence(Hb(data))[0], 200, 'evidence a held notice binds is never removed')
        st, ans = d.items(chain_epoch=n['chain_epoch'])
        held = [p for p in d.c.items_positions(ans) if p.get('k') == n['k']]
        self.assertTrue(held and held[0].get('item') == n, 'the notice body is never dropped')
        self.assertTrue(held and held[0].get('receipt') == d.c.receipt_of(b1), 'nor its receipt')


class Orphans(AccTest):
    @acc(id='S6-ORPHAN-EPOCH-01', rules=['E-Q-5', 'M-T-2'], cap='NONE',
         catches='a mailbox that counts an orphan\'s age across a mailbox epoch')
    def test_orphan_counted_inside_epoch(self):
        d, h, clock = self.mailbox(T_ORPHAN=100.0)
        rep, data = report_bytes(d.root)
        d.store_evidence(data)
        clock.advance(90); h.restart(); clock.advance(20)
        self.optional(h, 'run_maintenance')()
        self.assertEqual(d.get_evidence(Hb(data))[0], 200, 'only 20 s of this mailbox epoch: not yet an orphan for T_ORPHAN')

    @acc(id='S6-ORPHAN-RACE-01', rules=['E-Q-6', 'SAF-11', 'E-2'], cap='CAP-DB',
         catches='a mailbox where an orphan removal races a delivery: the notice is taken and its object removed')
    def test_orphan_race(self):
        d, h, clock = self.mailbox(T_ORPHAN=1.0)
        d.open_epoch()
        maint = self.optional(h, 'run_maintenance')
        for trial in range(25):
            rep, data = report_bytes(d.root, f't{trial}')
            d.store_evidence(data)
            clock.advance(5)                                                   # an orphan, removable
            n = d.equivocation(f'run{trial}', {'K-CONFLICT'}, [{'evidence_id': Hb(data), 'size': len(data), 'where': 'HELD'}])
            out = {}
            t1 = threading.Thread(target=lambda: out.setdefault('d', d.deliver(n)))
            t2 = threading.Thread(target=maint)
            t2.start(); t1.start(); t1.join(); t2.join()
            st = out['d'][0]
            if st == 200:
                self.assertEqual(d.get_evidence(Hb(data))[0], 200, f'trial {trial}: the notice was taken and the object it names removed (SAF-11)')
                state, reasons, s = d.state()
                self.assertNotIn('EVIDENCE_GAP', reasons, f'trial {trial}: a gap after a HELD notice was taken')
            else:
                self.assertEqual(st, 409, f'trial {trial}: refused only as EVIDENCE_MISSING')
                d.store_evidence(data); self.assertEqual(d.deliver(n)[0], 200)


class Gaps(AccTest):
    @acc(id='S6-GAP-01', rules=['E-B-3', 'E-B-4', 'C-1.3', '8.2', 'O-1', 'SAF-7'], cap='CAP-KEY',
         catches='a mailbox that treats NOT_HELD as an event (gap never shown, or not closed by storing the object)')
    def test_gap_state(self):
        d, h, clock = self.covered_driver()
        rep, data = report_bytes(d.root)
        n = d.equivocation('r', {'K-CONFLICT'}, [{'evidence_id': Hb(data), 'size': len(data), 'where': 'NOT_HELD', 'reason': 'UNAVAILABLE'}])
        self.assertEqual(d.deliver(n)[0], 200, 'a notice saying NOT_HELD is taken (E-B-3)')
        s = d.assert_not_covered('EVIDENCE_GAP', msg='an evidence gap')
        self.assertIn(Hb(data), d.c.st_text(s), 'the status names the ids')
        ids, more = d.c.ch_gaps(d.challenge())
        self.assertIn(Hb(data), ids, 'the challenge lists the gap (O-1)')
        d.cover('REFRESH')
        d.assert_not_covered('EVIDENCE_GAP', msg='whatever statements it holds (E-B-4)')
        self.assertEqual(d.store_evidence(data)[0], 200)
        d.assert_covered('the gap ended when the object was stored')

    @acc(id='S6-GAP-02', rules=['E-B-3', 'E-B-4', 'E-2'], cap='CAP-OS',
         catches='a mailbox that closes a gap for good once stored (it must begin again if the object is ever absent)')
    def test_gap_begins_again(self):
        d, h, clock = self.covered_driver()
        rep, data = report_bytes(d.root)
        d.store_evidence(data)
        n = d.equivocation('r', {'K-CONFLICT'}, [{'evidence_id': Hb(data), 'size': len(data), 'where': 'HELD'}])
        self.assertEqual(d.deliver(n)[0], 200)
        d.assert_covered('the object is held')
        self.optional(h, 'remove_evidence')(d.root, Hb(data))
        d.assert_not_covered('EVIDENCE_GAP', msg='the object a held notice binds is absent: the gap begins again')

    @acc(id='S6-GAP-03', rules=['E-B-5', 'E-3', 'E-X-3'], cap='CAP-KEY',
         catches='a mailbox that can be made COVERED while a notice binds an object larger than OBJ_MAX')
    def test_oversize_gap_stays(self):
        d, h, clock = self.covered_driver(OBJ_MAX=4096)
        big = b'{"r":"' + b'z' * 6000 + b'"}'
        n = d.equivocation('r', {'K-NONCE'}, [{'evidence_id': Hb(big), 'size': len(big), 'where': 'NOT_HELD', 'reason': 'OVERSIZE'}])
        self.assertEqual(d.deliver(n)[0], 200)
        self.assertEqual(d.store_evidence(big)[0], 413)
        d.cover('REFRESH')
        d.assert_not_covered('EVIDENCE_GAP', msg='an oversize report keeps the budget NOT COVERED (E-B-5)')


class ReadBack(AccTest):
    @acc(id='S6-READ-01', rules=['E-R-2', 'I-3', 'I-ID-3', 'I-E-6', 'E-Q-4', '11-INTERFACE'], cap='NONE',
         catches='a mailbox whose GET /items does not let a reader verify a chain epoch: links, retired positions and the head')
    def test_reader_verifies(self):
        d, h, clock = self.mailbox(ALARMS_KEEP=1)
        d.budget.new_run(); d.open_epoch()
        first = d.notice('FAIL', name='run-a', basis=['FAIL', 3, None])
        d.deliver(first)
        for _ in range(2):
            d.deliver(d.alarm(d.token(d.challenge())))                     # the first alarm's body is retired
        d.cover()
        e1 = d.chain_epoch
        d.open_epoch('COURIER_STATE_LOST')
        again = d.notice('FAIL', name='run-a', basis=['FAIL', 3, None])     # the same identity in the new epoch: linked
        st, body = d.deliver(again)
        self.assertEqual(st, 200)
        for ce in (e1, d.chain_epoch):
            st, ans = d.items(chain_epoch=ce)
            self.assertEqual(st, 200)
            A, k, retired = A0(d.root, ce), 0, 0
            for p in d.c.items_positions(ans):
                k += 1
                self.assertEqual(p.get('k'), k, 'positions in order')
                it = p.get('item')
                ident = (p.get('index') or {}).get('identity')
                if it is not None:
                    self.assertTrue(verify_object(it, [d.key.public_hex]), 'the courier\'s signature on each item')
                    self.assertEqual(it['prev'], A, 'prev is A(k-1)')
                    ident = it['identity']
                    if it['kind'] == 'OBSERVATION_INCOMPLETE':
                        self.assertEqual(ident, id_alarm(d.root, it['body']['token']), 'identity recomputed (I-ID-2)')
                    elif it['kind'] in ('EPOCH_OPEN', 'COVERAGE', 'OBSERVATION_PART'):
                        self.assertEqual(ident, id_epochal(d.root, it['kind'], ce, it['body']), 'identity recomputed (I-ID-3)')
                elif p.get('linked'):
                    self.assertEqual(ident, first['identity'], 'a link names the identity of the first item')
                else:
                    retired += 1
                    self.assertTrue(ident, 'a retired position keeps its index entry (identity)')
                A = A_next(A, ident)
            head = d.c.items_head(ans)
            self.assertTrue(d.verify_mb(head), 'the head is signed by the mailbox')
            self.assertEqual(d.c.head_tuple(head)[1:], (k, A), 'A(k) recomputed by the reader equals the mailbox\'s signed head')
            if ce == e1:
                self.assertGreaterEqual(retired, 1, 'a retired alarm is reported as retired')
