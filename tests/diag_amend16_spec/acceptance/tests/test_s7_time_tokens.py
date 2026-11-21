"""Section 7.1 (time and epochs) and 7.2 (tokens), at the mailbox's interface (section 11).  Seam: sut.start_mailbox
with an injected clock (TR-CLOCK).  L and R and every limit are parameters (section 11).  Specification version 5."""
import base64
import os
import re

from acc import AccTest, acc
from mbutil import refused, error, head_k
from fixtures.crypto import TestKey


class Time(AccTest):
    @acc(id='S7-TIME-SUSPEND-01', rules=['M-T-1', 'M-K-4', 'C-1.2', 'SAF-3', 'N-4'], cap='NONE',
         catches='a mailbox that counts age with CLOCK_MONOTONIC (a suspension does not count, so an old token stays fresh)')
    def test_suspension_counts(self):
        d, h, clock = self.covered_driver(L=60.0)
        clock.suspend(61)                                           # BOOTTIME and wall move; MONOTONIC does not
        d.assert_not_covered('EXPIRED', msg='after a suspension longer than L')
        ch = d.challenge(); it = d.statement(ch, reading='REFRESH')
        clock.suspend(61)
        st, body = d.send_statement(it)
        refused(self, st, body, d, 'ST-2', 'ST-3', msg='a token older than L by BOOTTIME')

    @acc(id='S7-TIME-STATIC-01', rules=['M-T-1'], cap='NONE',
         catches='an implementation whose source reads time.monotonic() or CLOCK_MONOTONIC for elapsed time')
    def test_source_uses_boottime(self):
        d, h, clock = self.mailbox()
        files = self.optional(h, 'source_files')()
        text = '\n'.join(open(f, encoding='utf-8', errors='replace').read() for f in files)
        self.assertTrue(files, 'the adapter gave no source files')
        self.assertNotRegex(text, r'time\.monotonic(_ns)?\s*\(|CLOCK_MONOTONIC\b(?!_RAW)', 'M-T-1: time.monotonic() MUST NOT be used')
        self.assertRegex(text, r'CLOCK_BOOTTIME', 'M-T-1: elapsed time is clock_gettime_ns(CLOCK_BOOTTIME)')

    @acc(id='S7-TIME-REBOOT-01', rules=['M-T-2', 'M-T-3', 'M-K-5', 'C-1.1', '8.2', 'SAF-3'], cap='NONE',
         catches='a mailbox that compares a tick of before a reboot with BOOTTIME after it (near zero: the token looks young)')
    def test_reboot_new_epoch(self):
        d, h, clock = self.covered_driver()
        ep1 = d.epoch_seen
        ch_old = d.challenge()
        clock.reboot(down=5); h.restart()
        s = d.assert_not_covered('MAILBOX_RESTARTED', msg='after a reboot')
        self.assertNotEqual(d.c.st_field(s, 'mailbox_epoch'), ep1, 'a reboot makes a new mailbox epoch (M-T-2)')
        it = d.statement(ch_old, reading='REFRESH')
        st, body = d.send_statement(it)
        refused(self, st, body, d, 'ST-1', 'ST-2', msg='a token of the earlier mailbox epoch (VOID; another epoch)')

    @acc(id='S7-TIME-RESTART-01', rules=['M-T-2', 'M-K-5', 'C-1.1', '8.2', 'C-S-2'], cap='NONE',
         catches='a mailbox that keeps a budget COVERED, or its tokens ISSUED, across a restart without a reboot')
    def test_restart_without_reboot(self):
        d, h, clock = self.covered_driver()
        ep1 = d.epoch_seen
        ch_old = d.challenge()
        h.restart()
        s = d.assert_not_covered('MAILBOX_RESTARTED', msg='after a restart (no reboot)')
        self.assertNotEqual(d.c.st_field(s, 'mailbox_epoch'), ep1, 'every start makes a new mailbox epoch (M-T-2)')
        st, body = d.send_statement(d.statement(ch_old, reading='REFRESH'))
        refused(self, st, body, d, 'ST-2', msg='a token issued before the restart is VOID (M-K-5)')
        d.epoch_seen = None
        d.cover('REFRESH')                                          # the first statement of a mailbox epoch may be REFRESH (ST-7)
        d.assert_covered('a REFRESH statement after the restart')

    @acc(id='S7-TIME-WALLBACK-01', rules=['M-T-5', '8.2'], cap='CAP-OS',
         catches='a mailbox that does not record a clock anomaly when the wall clock is set back')
    def test_wall_clock_back(self):
        d, h, clock = self.mailbox(L=60.0)
        d.budget.new_run(); d.open_epoch()
        ch = d.challenge(); it = d.statement(ch)
        clock.set_wall(-3600); clock.advance(1)
        st, body = d.send_statement(it)
        self.assertEqual(st, 200, 'the age by BOOTTIME (1 s) is within L; the larger of the two ages is used')
        s = d.status()
        self.assertIn('CLOCK_ANOMALY', d.c.st_text(s), 'a clock anomaly is shown in every status (M-T-5, 8.2)')
        clock.advance(1); h.restart(); d.epoch_seen = None
        self.assertIn('CLOCK_ANOMALY', d.c.st_text(d.status()), 'recorded durably, until the operator clears it')

    @acc(id='S7-TIME-WALLFWD-01', rules=['M-T-5', 'ST-3', 'SAF-1'], cap='CAP-OS',
         catches='a mailbox that takes the BOOTTIME age alone when the wall clock moved further (a pause a corrected wall clock shows)')
    def test_wall_clock_forward(self):
        d, h, clock = self.mailbox(L=60.0, CLOCK_TOLERANCE=5.0)
        d.budget.new_run(); d.open_epoch()
        ch = d.challenge(); it = d.statement(ch)
        clock.set_wall(120); clock.advance(1)                      # BOOTTIME: 1 s, wall: 121 s
        st, body = d.send_statement(it)
        refused(self, st, body, d, 'ST-3', msg='the larger age (121 s) is more than L')
        self.assertIn('CLOCK_ANOMALY', d.c.st_text(d.status()))

    @acc(id='S7-TIME-NOTIME-01', rules=['M-T-6', 'M-T-4'], cap='CAP-DB',
         catches='a mailbox that takes time from an item, a checkpoint or the courier')
    def test_no_time_from_items(self):
        d, h, clock = self.mailbox(L=60.0)
        b = d.budget; b.new_run(); d.open_epoch()
        ch = d.challenge()
        cp = b.checkpoint(nonce=d.token(ch), at=0, seq=b.n, head=b.head, head_at=b.head_at(0), time_='2099-01-01T00:00:00Z')
        it = d.statement(ch, cp=cp)
        it = d.key.sign_object(dict({k: v for k, v in it.items() if k not in ('signer', 'signature')}, time='2099-01-01T00:00:00Z'))
        st, body = d.send_statement(it)
        self.assertEqual(st, 200, f'times in an item or checkpoint are for people: {st} {str(body)[:200]}')
        clock.advance(61)
        d.assert_not_covered('EXPIRED', msg='the item said 2099; the mailbox\'s own clock says the token is older than L')


class Tokens(AccTest):
    @acc(id='S7-TOK-SIGNED-01', rules=['M-K-1', '11-CLIENTS', '11-INTERFACE'], cap='CAP-DB',
         catches='a mailbox that issues a token to an unsigned request, another key\'s request, or a non-writing client')
    def test_signed_request(self):
        d, h, clock = self.mailbox()
        ch = d.challenge()                                           # learn the epoch
        st, body, r = d.request_challenge(key=TestKey())
        self.assertIn(st, (403, 400), 'a request signed by another key is refused')
        req = d.c.challenge_request(d.key, d.root, d.epoch_seen, os.urandom(16).hex()); req['signature'] = '00' * 64
        st2, _ = d.req('POST', '/challenge', req)
        self.assertIn(st2, (403, 400), 'a request whose signature fails is refused')
        req = d.c.challenge_request(d.key, d.root, d.epoch_seen, os.urandom(16).hex())
        st3, _ = d.req('POST', '/challenge', req, client='reader')
        self.assertEqual(st3, 403, 'a reading name may not ask for a challenge (11)')
        st4, _ = d.req('POST', '/challenge', req, client='stranger')
        self.assertEqual(st4, 403, 'a client name the mailbox was not started with is refused (11)')

    @acc(id='S7-TOK-EPOCH-01', rules=['M-K-1'], cap='CAP-DB',
         catches='a mailbox that issues a token to a request naming another mailbox epoch')
    def test_other_epoch(self):
        d, h, clock = self.mailbox()
        d.challenge()
        st, body, r = d.request_challenge(epoch='not-this-epoch-' + os.urandom(4).hex())
        error(self, st, body, d, 409, 'EPOCH', msg='a request for another mailbox epoch')
        self.assertEqual(d.c.epoch_in_error(body), d.epoch_seen, '409 EPOCH carries the current epoch')

    @acc(id='S7-TOK-REPLAY-01', rules=['M-K-1', 'M-K-2'], cap='CAP-OS',
         catches='a mailbox that answers a replayed request again (issuing a token, or voiding the oldest)')
    def test_replay(self):
        d, h, clock = self.mailbox(TOKENS_MAX=2)
        d.budget.new_run(); d.open_epoch()
        ch1 = d.challenge()
        st, body, r = d.request_challenge()
        self.assertEqual(st, 200)
        for _ in range(3):
            st2, body2 = d.req('POST', '/challenge', r)               # the same request, byte for byte
            error(self, st2, body2, d, 409, 'REPLAY', msg='a request already answered in this mailbox epoch')
        st3, b3 = d.send_statement(d.statement(ch1))
        self.assertEqual(st3, 200, 'the replays did not make the oldest token VOID (M-K-1: "cannot issue a token or make one VOID")')

    @acc(id='S7-TOK-MAX-01', rules=['M-K-2', 'M-K-3', 'ST-2', 'M-S-1'], cap='CAP-DB',
         catches='a mailbox without TOKENS_MAX, or that voids the newest rather than the oldest ISSUED token')
    def test_tokens_max(self):
        d, h, clock = self.mailbox(TOKENS_MAX=3)
        d.budget.new_run(); d.open_epoch()
        chs = [d.challenge() for _ in range(4)]
        st, body = d.send_statement(d.statement(chs[0]))
        refused(self, st, body, d, 'ST-2', msg='the oldest ISSUED token was made VOID by the fourth issue')
        st, body = d.send_statement(d.statement(chs[1]))
        self.assertEqual(st, 200, 'the second token is still ISSUED')

    @acc(id='S7-TOK-FORM-01', rules=['M-K-1'], cap='NONE',
         catches='a mailbox whose token is not 32 random bytes as 43 URL-safe base64 characters, or repeats')
    def test_token_form(self):
        d, h, clock = self.mailbox(TOKENS_MAX=50)
        toks = [d.token(d.challenge()) for _ in range(20)]
        for t in toks:
            self.assertRegex(t, r'^[A-Za-z0-9_-]{43}$')
            self.assertEqual(len(base64.urlsafe_b64decode(t + '=')), 32)
        self.assertEqual(len(set(toks)), len(toks))

    @acc(id='S7-TOK-USED-01', rules=['M-K-3', 'ST-2', 'SAF-1'], cap='CAP-OS',
         catches='a mailbox that counts a second statement on a USED token')
    def test_used_once(self):
        d, h, clock = self.mailbox()
        d.budget.new_run(); d.open_epoch()
        ch, it, _ = d.cover()
        d.budget.new_run()
        st, body = d.send_statement(d.statement(ch, reading='REFRESH'))
        refused(self, st, body, d, 'ST-2', msg='the token is USED')

    @acc(id='S7-TOK-SPENT-01', rules=['M-K-3', '7.4', 'ST-2'], cap='NONE',
         catches='a mailbox that leaves the token ISSUED after a statement is refused (a token can be tried again and again)')
    def test_spent(self):
        d, h, clock = self.mailbox()
        d.budget.new_run(); d.open_epoch()
        ch = d.challenge()
        st, body = d.send_statement(d.statement(ch, limits={'L': 1, 'R': 1, 'RUN_ANSWER_MAX': 1}))
        refused(self, st, body, d, 'ST-9')
        st, body = d.send_statement(d.statement(ch))
        refused(self, st, body, d, 'ST-2', msg='the refused statement made its token SPENT')

    @acc(id='S7-TOK-DURABLE-01', rules=['M-K-6', '11-INTERFACE', 'DL-2'], cap='NONE',
         catches='a mailbox that answers a statement before writing it durably (lost at a restart)')
    def test_durable(self):
        d, h, clock = self.mailbox()
        d.budget.new_run(); d.open_epoch()
        ch, it, body = d.cover()
        h.restart(); d.epoch_seen = None
        st, body2 = d.deliver(it, advance=False)
        self.assertEqual(st, 200, 'the accepted statement is held after a restart; sent again, it is answered as the first time')
        self.assertEqual(d.c.receipt_of(body2), d.c.receipt_of(body), 'with the first receipt (DL-2)')
