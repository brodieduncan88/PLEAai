"""Version 6: the courier's own anchor (I-O-4, rewritten), the mailbox's loss of state (I-O-4a, new), I-E-4 (the own
anchor kept through a new epoch), I-O-2 (one item at a time), SAF-10 and L-10.  Specification version 6
(SHA-256 8eb8fe4b7ecb869670bba85a359093ee2817cf02fc77a8a150a4667c2509f836); M30, M31, F35, F36, M27, M32."""
import json

from acc import CourierTest, acc
from s3util import honest_run


def accepted_statements(tc, e, since):
    return [x for x in e.log.of('mailbox', 'POST /deliver')[since:] if isinstance(x['body'], dict)
            and x['body'].get('kind') == 'COVERAGE' and x['status'] == 200]


class OwnAnchor(CourierTest):
    def _lost_answer_then_record_lost(self, e):
        """A statement accepted with its answer lost; at that moment the mailbox loses its record of the budget (restored
        from an empty copy); the courier sends the statement again and is refused.  This is the trace that broke version 5."""
        e.h.stop(); empty = self.optional(e.h, 'snapshot')(); e.h.start()
        honest_run(self, e.b, 'PASS'); e.read()                                    # accepted, answered: COVERED at N1
        honest_run(self, e.b, 'FAIL')
        n_stmt = e.b.n
        done = {'n': 0}
        def lose(method, path, body):
            if isinstance(body, dict) and body.get('kind') == 'COVERAGE' and done['n'] == 0:
                done['n'] += 1
                e.h.request(method, path, json.dumps(body).encode(), 'courier')   # the mailbox accepts it ...
                e.h.stop(); e.h.restore(empty); e.h.start()                       # ... then loses its record of the budget
                return 'DROP_NO_FORWARD'                                           # and the answer is lost
        e.px.script.append(lose)
        e.read()
        e.px.script.clear()
        resent = [x for x in e.log.of('mailbox', 'POST /deliver') if isinstance(x['body'], dict) and x['body'].get('kind') == 'COVERAGE']
        self.assertGreaterEqual(len(resent), 2, 'precondition: the statement with no answer was sent again (I-O-2)')
        self.assertNotEqual(resent[1]['status'], 200, 'precondition: the mailbox that lost its record refused it')
        return n_stmt

    @acc(id='C5-V6-ANCHOR-01', rules=['I-O-4', 'SAF-10', 'L-10', 'O-3', 'I-O-2'], cap='CAP-OWNER',
         catches='(version 6, M30) a courier whose own anchor is lowered by a refusal: a witness rolled back below the lost statement passes')
    def test_v5_trace_rollback(self):
        e = self.courier_env()
        n_stmt = self._lost_answer_then_record_lost(e)
        e.w.faults[e.b.root] = {'rollback_to': n_stmt - 2}                          # the witness rolled back below that N
        mark = self.n_deliveries(e); e.read(); e.read()
        self.assertFalse(accepted_statements(self, e, mark), 'no statement over a chain that does not contain the own anchor (I-O-4)')
        self.assertIn('ROLLBACK', self.alarm_reasons(e, since=mark), 'a witness chain shorter than the own anchor is a ROLLBACK (F36)')
        e.d.epoch_seen = None; e.d.assert_not_covered()

    @acc(id='C5-V6-ANCHOR-02', rules=['I-O-4', 'SAF-10', 'L-10', 'O-3'], cap='CAP-OWNER',
         catches='(version 6, M30) the same trace with the witness forked below the lost statement\'s N')
    def test_v5_trace_fork(self):
        e = self.courier_env()
        n_stmt = self._lost_answer_then_record_lost(e)
        e.b.rewrite_below(n_stmt - 2)
        mark = self.n_deliveries(e); e.read(); e.read()
        self.assertFalse(accepted_statements(self, e, mark))
        self.assertIn('FORK', self.alarm_reasons(e, since=mark), 'the hash at the own anchor differs: FORK')
        e.d.epoch_seen = None; e.d.assert_not_covered()

    @acc(id='C5-V6-ANCHOR-03', rules=['I-O-4a', 'I-O-4', 'O-W-2'], cap='CAP-OS',
         catches='(version 6, F35) a courier that takes a refusal alone as the mailbox\'s loss of state (a false MAILBOX_ROLLBACK)')
    def test_refusal_is_not_rollback(self):
        e = self.courier_env(); honest_run(self, e.b, 'PASS'); e.read()
        honest_run(self, e.b, 'FAIL')
        once = {'n': 0}
        def refuse(m, p, b):
            if isinstance(b, dict) and b.get('kind') == 'COVERAGE' and once['n'] == 0:
                once['n'] += 1; return (422, {'error': 'STATEMENT_REFUSED', 'failed': ['ST-3']})
        e.px.script.append(refuse)
        mark = self.n_deliveries(e); e.read(); e.read(); e.read()
        self.assertNotIn('MAILBOX_ROLLBACK', self.alarm_reasons(e, since=mark), 'a refused statement holds no receipt: no loss of state')
        self.assertFalse([i for i in self.items(e, 'EPOCH_OPEN', since=mark) if i['body'].get('reason') == 'MAILBOX_STATE_LOST'])
        e.d.assert_covered('the next honest statement is taken')

    @acc(id='C5-V6-ANCHOR-04', rules=['I-O-4', 'O-R-3', 'O-3'], cap='CAP-OWNER',
         catches='(version 6) a courier that checks its own anchor only in a reading from 0, not in an INCREMENTAL reading')
    def test_own_anchor_incremental(self):
        for fault in ('rollback', 'fork'):
            e = self.courier_env(mb={'R': 3600.0, 'L': 7200.0})
            honest_run(self, e.b, 'PASS'); e.read(); e.read()                   # COVERED; the mailbox's anchor is N1
            n1 = e.b.n
            honest_run(self, e.b, 'PASS'); honest_run(self, e.b, 'PASS')
            e.px.script.append(lambda m, p, b: (422, {'error': 'STATEMENT_REFUSED', 'failed': ['ST-3']})
                               if isinstance(b, dict) and b.get('kind') == 'COVERAGE' else None)
            e.read()                                                              # the courier verified a checkpoint at N2 > N1
            e.px.script.clear()
            if fault == 'rollback':
                e.w.faults[e.b.root] = {'rollback_to': n1 + 1}                   # above the mailbox's anchor, below the own anchor
            else:
                e.b.rewrite_below(n1 + 1)
            mark = self.n_deliveries(e); e.read()
            self.assertFalse(accepted_statements(self, e, mark), f'{fault}: no statement')
            self.assertIn('ROLLBACK' if fault == 'rollback' else 'FORK', self.alarm_reasons(e, since=mark),
                          f'{fault}: the own anchor (N2) rests on what the witness signed; the refusal did not move it')

    @acc(id='C5-V6-ANCHOR-05', rules=['I-O-4', 'I-E-4'], cap='CAP-OWNER',
         catches='(version 6, M31) a courier that drops its own anchor when it opens a new chain epoch (COURIER_STATE_LOST)')
    def test_own_anchor_kept_through_epoch(self):
        e = self.courier_env(); honest_run(self, e.b, 'PASS'); e.read()
        honest_run(self, e.b, 'FAIL'); e.read()
        n = e.b.n
        once = {'n': 0}
        def st5(m, p, b):                                                          # a refusal at ST-5: a loss of state (I-E-4)
            if isinstance(b, dict) and b.get('kind') == 'COVERAGE' and once['n'] == 0:
                once['n'] += 1; return (422, {'error': 'STATEMENT_REFUSED', 'failed': ['ST-5']})
        honest_run(self, e.b, 'PASS')
        e.px.script.append(st5); e.read(); e.px.script.clear()
        e.w.faults[e.b.root] = {'rollback_to': n - 1}
        mark = self.n_deliveries(e); e.read(); e.read()
        self.assertFalse(accepted_statements(self, e, mark), 'the new epoch\'s FROM_ZERO reading is checked against the own anchor kept')
        self.assertIn('ROLLBACK', self.alarm_reasons(e, since=mark))

    @acc(id='C5-V6-ONE-01', rules=['I-O-2'], cap='NONE',
         catches='(version 6, M32) a courier that sends the next item before the one before has an answer')
    def test_one_item_at_a_time(self):
        e = self.courier_env()
        for _ in range(4):
            honest_run(self, e.b, 'FAIL')
        e.read(); e.read()
        seq = [x for x in e.log.events if x['what'] == 'POST /deliver' and x['party'] in ('mailbox_begin', 'mailbox')]
        self.assertTrue(len(seq) >= 8)
        for i, x in enumerate(seq):
            self.assertEqual(x['party'], 'mailbox_begin' if i % 2 == 0 else 'mailbox',
                             f'event {i}: a delivery began before the one before was answered (I-O-2)')
