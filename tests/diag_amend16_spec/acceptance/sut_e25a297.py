"""Adapter binding the seam onto the EXISTING, unchanged code at e25a297 (pinned copy: S/amend16/diag2/src), to show the
suite goes red against code that does not implement the specification.  Nothing in the pinned source is changed; no
bytecode is written there (sys.dont_write_bytecode).

Bound:
  judge_run           the courier's per-run judgement at e25a297: verify/courier.py run_outcome's filtering (reports up to
                      N; a stored result read as its 'value' when its outcome is 'value' or absent) and
                      check_record.run_outcome; the notice as courier.py calls it (DUE at once; UNVERIFIED and NO_OUTCOME
                      after stall_after).  The code has no findings: findings are always empty, no EQUIVOCATION.
  judge_unborne_names the code does not judge names no attempt bears: no finding, no notice (faithful to it).
  verify_record       check_record.verify.
  notice_problems, receipt_problems   check_record's, unchanged.
  start_mailbox       verify/mailbox_service.Mailbox, in process, without TLS: POST /deliver (Mailbox.take) and GET /pubkey;
                      every other path 404 as its handler answers.  The clock is ignored (the code reads time.time()).
                      restart/stop/start re-create the object on the same folder; snapshot/restore copy the folder;
                      run_maintenance is a no-op (the code removes nothing); source_files are the two files it runs.
Not bound (NOT IMPLEMENTED):
  record_judge_runs   check_record.verify judges only whole signed records (baseline, engineer's signature); its check 6
                      cannot be called alone without changing it.
  start_courier       verify/courier.py has no challenge, no form-3 items and no chain epochs; it speaks only HTTPS to a
                      real witness and mailbox.  No section 4/5 test can be driven through it.
  remove_evidence, corrupt_record   the mailbox has no evidence store and no per-budget record.
"""
import json
import os
import shutil
import sys
import threading

sys.dont_write_bytecode = True
PINNED = '/tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad/amend16/diag2/src'
sys.path.insert(0, os.path.join(PINNED, 'verify'))
import check_record as C          # noqa: E402
import mailbox_service as MS      # noqa: E402

import sut as SUT                 # noqa: E402

DUE = ('FAIL', 'UNKNOWN', 'INTERRUPTED', 'INDETERMINATE', 'INVALID', 'REFUNDED')


class _Mailbox:
    def __init__(self, cfg, clock, store):
        self.cfg, self.store = cfg, store
        self.key = MS.MailboxKey()
        self.public_key = self.key.public_hex
        self.allow = set(cfg.writers) | set(cfg.readers)
        self.up = False
        self.start()

    def start(self):
        self.box = MS.Mailbox(self.store, self.key, 'acc-mailbox', list(self.cfg.budgets.values()))
        self.up = True

    def stop(self):
        self.up = False

    def restart(self):
        self.stop(); self.start()

    def request(self, method, path, body, client):
        if not self.up:
            raise ConnectionError('the mailbox is down')
        if client not in self.allow:
            return 403, json.dumps({'error': 'client not admitted'}).encode()
        if method == 'GET' and path == '/pubkey':
            return 200, json.dumps({'public_key': self.public_key, 'name': 'acc-mailbox'}).encode()
        if method == 'POST' and path == '/deliver':
            if not body or len(body) > MS.MAX_NOTICE:
                return 400, json.dumps({'error': 'a notice is 1 byte to 64 KiB of JSON'}).encode()
            try:
                notice = json.loads(body)
            except ValueError:
                return 400, json.dumps({'error': 'malformed request'}).encode()
            st, ans = self.box.take(notice)
            return st, json.dumps(ans).encode()
        return 404, json.dumps({'error': 'not found'}).encode()

    def snapshot(self):
        snap = self.store + '.snap-' + os.urandom(4).hex()
        shutil.copytree(self.store, snap)
        return snap

    def restore(self, snap):
        shutil.rmtree(self.store); shutil.copytree(snap, self.store)

    def run_maintenance(self):
        pass

    def source_files(self):
        return [os.path.join(PINNED, 'verify', 'mailbox_service.py'), os.path.join(PINNED, 'verify', 'check_record.py')]

    def close(self):
        self.up = False


class E25a297(SUT.Adapter):
    name = 'e25a297'

    def judge_run(self, inp):
        ev = [e for e in inp.evidence or [] if isinstance(e, dict) and type(e.get('seq')) is int and e['seq'] <= inp.n]
        stored = inp.result
        result = stored.get('value') if inp.phase == 'EFFECT' and isinstance(stored, dict) and stored.get('outcome', 'value') == 'value' else None
        if inp.phase not in ('EFFECT', 'CONSUMED'):
            ev, result = [], None
        try:
            out = C.run_outcome(inp.phase, ev, result, inp.gate_keys, inp.root, inp.aid, inp.chain_nonce)
        except Exception as exc:                                        # noqa: BLE001 - courier.handled() turns these into a fault
            out = 'COURIER_FAILED:' + type(exc).__name__
        believed = inp.phase == 'EFFECT' and out in ('PASS', 'FAIL', 'UNKNOWN', 'INVALID')
        notice = out if out in DUE else (out if out in ('UNVERIFIED', 'NO_OUTCOME') else None)
        return SUT.RunJudgement(frozenset(), out, believed, notice, out in ('UNVERIFIED', 'NO_OUTCOME'), (), None, True)

    def judge_unborne_names(self, inp):
        return SUT.NamesJudgement(frozenset(), None, ())

    def verify_record(self, record, keys):
        ok, checks, _ = C.verify(record, keys)
        return ok, [c[0] for c in checks if not c[2]]

    def notice_problems(self, notice, courier_keys):
        return C.notice_problems(notice, courier_keys)

    def receipt_problems(self, receipt, mailbox_keys, notice):
        return C.receipt_problems(receipt, mailbox_keys, notice)

    def start_mailbox(self, config, clock, store_dir):
        return _Mailbox(config, clock, store_dir)


ADAPTER = E25a297()
