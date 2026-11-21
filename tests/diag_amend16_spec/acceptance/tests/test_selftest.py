"""Self-tests of the suite's own fixtures and runner (no system under test).  These must PASS under every adapter."""
import json
import os
import subprocess
import sys

from acc import AccTest, acc, ACC2
import sut as SUT

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SelfTest(AccTest):
    @acc(id='SELF-GATE-01', rules=['K-CAP-1'], cap='NONE',
         catches='an honest gate fixture that lives in this process, exposes its key, or signs what an honest host does not')
    def test_honest_gate(self):
        from fixtures.honest_gate import GateRefused
        from fixtures.crypto import report_message, verify_sig, well_formed_digest
        g = self.gate()
        self.assertNotEqual(g.pid, os.getpid(), 'the gate host runs in another process')
        self.assertFalse([k for k in vars(g) if 'priv' in k.lower() or k == '_k' or k == '_key'], 'the client holds no key')
        root = self.new_root('gate')
        with self.assertRaises(GateRefused):
            g.run(root, 'a1', 'n1', 'EFFECT', {})                               # intent not accepted
        g.intent_accepted(root, 'a1', 'n1')
        r1 = g.run(root, 'a1', 'n1', 'EFFECT', {'v': 1})
        self.assertTrue(verify_sig(g.public_key, r1['signature'], report_message(r1)) and well_formed_digest(r1['result_digest']))
        self.assertEqual(g.run(root, 'a1', 'n1', 'NO_EFFECT', {'v': 2}), r1, 'asked again: the same report, byte for byte')
        g.intent_accepted(root, 'a1', 'n2')
        for bad in (lambda: g.run(root, 'a1', 'n2', 'EFFECT', {}), lambda: g.fence(root, 'a1'),
                    lambda: g.run(root, 'a2', 'n1', 'PASS', {})):
            with self.assertRaises(GateRefused):
                bad()
        f = g.fence(root, 'a3')
        self.assertEqual((f['nonce'], f['result_digest'], f['claim']), (None, None, 'FENCED_NO_START'))
        g.intent_accepted(root, 'a3', 'n3')
        with self.assertRaises(GateRefused):
            g.run(root, 'a3', 'n3', 'EFFECT', {})                               # never both

    @acc(id='SELF-CAP-01', rules=['K-CAP-1', 'ACC-5'], cap='NONE',
         catches='a runner that runs a CAP-DB (or NONE) test touching the CAP-KEY signer, statically or through a helper')
    def test_runner_refuses(self):
        import run_acceptance as RA
        d = os.path.join(HERE, 'selftest_fixtures')
        rows = {r['id']: r for r in RA.run(RA.load_tests(d))}
        self.assertEqual(rows['PLANT-CAPDB-STATIC']['outcome'], 'ERROR'); self.assertIn('refused to run', rows['PLANT-CAPDB-STATIC']['detail'])
        self.assertEqual(rows['PLANT-CAPDB-DYNAMIC']['outcome'], 'ERROR'); self.assertIn('CapabilityViolation', rows['PLANT-CAPDB-DYNAMIC']['detail'])
        self.assertEqual(rows['PLANT-NONE-DYNAMIC']['outcome'], 'ERROR')
        self.assertEqual(rows['PLANT-CAPKEY-OK']['outcome'], 'PASS', 'a CAP-KEY test may sign')
        self.assertEqual(rows['Planted.test_unlabelled']['outcome'], 'ERROR', 'an unlabelled test is refused')
        self.assertEqual(rows['PLANT-REUSE']['outcome'], 'ERROR', 'a budget reused is ERROR (ACC-5)')

    @acc(id='SELF-NI-01', rules=['K-CAP-1'], cap='NONE',
         catches='a default adapter that does anything but raise the NOT IMPLEMENTED signal')
    def test_default_adapter(self):
        a = SUT.DefaultAdapter()
        for call in (lambda: a.judge_run(None), lambda: a.judge_unborne_names(None), lambda: a.record_judge_runs(None),
                     lambda: a.verify_record(None, None), lambda: a.notice_problems(None, None), lambda: a.receipt_problems(None, None, None),
                     lambda: a.start_mailbox(None, None, None), lambda: a.start_courier(None, None, None, None, None)):
            with self.assertRaises(SUT.SutNotImplemented):
                call()

    @acc(id='SELF-CHAIN-01', rules=['FIXTURE'], cap='NONE',
         catches='a scripted chain whose hashes, checkpoints or derived labels are not the witness\'s')
    def test_chain_fixture(self):
        from fixtures.chain import chain_hash
        from fixtures.crypto import canonical, verify_sig
        b = self.new_budget()
        aid, nonce = b.new_run(upto='CONSUMED')
        rep = self.gate().run(b.root, aid, nonce, 'EFFECT', {'verdict': 'PASS'})
        b.reconcile(aid, rep)
        self.assertEqual(b.decisions[-1]['op'], ['RECONCILE', aid, 'EFFECT', 'AUTHORISED'])
        self.assertEqual((b.decisions[-1]['kind'], b.decisions[-1]['code'], b.phase(aid)), ('APPLIED', 'VERDICT_RECORDED', 'EFFECT'))
        b.reconcile(aid, dict(rep, aid='other'))
        self.assertEqual(b.decisions[-1]['op'][3], 'NONE', 'a report whose signed fields were altered is not genuine')
        prev = b.prov_hash
        for d in b.decisions:
            self.assertEqual(d['hash'], chain_hash(prev, d['seq'], d['op'], d['kind'], d['code'], d['observation'])); prev = d['hash']
        cp = b.checkpoint(nonce='x', at=0)
        body = {k: v for k, v in cp.items() if k not in ('signer', 'signature')}
        self.assertTrue(verify_sig(self.wkey.public_hex, cp['signature'], canonical(body).encode()))
        self.assertEqual(cp['head_at'], b.prov_hash)

    @acc(id='SELF-ACC2-01', rules=['ACC-2', 'N-5'], cap='NONE',
         catches='a runner whose printed results or result files lack the ACC-2 statement or the specification\'s version and hash')
    def test_acc2_printed(self):
        name = 'selftest-acc2-probe'
        p = subprocess.run([sys.executable, os.path.join(HERE, 'run_acceptance.py'), '--dir', 'selftest_fixtures', '--filter', 'PLANT-CAPKEY-OK', '--name', name],
                           capture_output=True, text=True, cwd=HERE, env=dict(os.environ, ACC_SUT=''))
        lines = [l for l in p.stdout.splitlines() if l.strip()]
        self.assertTrue(lines[0].startswith('ACC-2'), 'ACC-2 at the head'); self.assertIn(ACC2, lines[-2:], 'and at the foot')
        self.assertIn('8eb8fe4b7ecb869670bba85a359093ee2817cf02fc77a8a150a4667c2509f836', p.stdout, 'version 6\'s SHA-256')
        jp = lines[-1].split('written ', 1)[1]
        data = json.load(open(jp))
        self.assertEqual(data['spec']['version'], 6)
        self.assertTrue(all(r['acc2'] == ACC2 for r in data['results']))
        os.remove(jp); os.remove(jp[:-5] + '.console.txt')

    @acc(id='SELF-LIMITS-01', rules=['11-LIMITS', 'ACC-5'], cap='NONE',
         catches='a suite that hard-codes L, R or a limit instead of taking every one as a parameter (section 11)')
    def test_limits_are_parameters(self):
        import dataclasses
        mb = {f.name for f in dataclasses.fields(SUT.MailboxConfig)}
        for name in ('L', 'R', 'TOKENS_MAX', 'ITEM_MAX', 'OBJ_MAX', 'EVID_BUDGET_QUOTA', 'EVID_GLOBAL_QUOTA', 'NOTICE_QUOTA', 'OBS_QUOTA',
                     'ALARM_RESERVE', 'ALARMS_KEEP', 'INDEX_QUOTA', 'INDEX_RESERVE', 'T_ORPHAN', 'CLOCK_TOLERANCE', 'witness_keys', 'writers', 'readers', 'budgets'):
            self.assertIn(name, mb, f'the mailbox configuration takes {name}')
        cc = {f.name for f in dataclasses.fields(SUT.CourierConfig)}
        for name in ('RUN_ANSWER_MAX', 'INLINE_TOTAL_MAX', 'NOTICES_PER_RUN_MAX'):
            self.assertIn(name, cc, f'the courier configuration takes {name}')
        self.assertEqual([f.name for f in dataclasses.fields(SUT.MailboxConfig) if f.name in ('L', 'R') and f.default is not dataclasses.MISSING], [],
                         'L and R have no default: the specification proposes none (section 11)')

    @acc(id='SELF-FIX-01', rules=['FIXTURE'], cap='NONE',
         catches='test fixtures (item builder, statement builder, scripted witness, proxy) that crash or build items the text does not define')
    def test_fixtures_against_a_stub(self):
        import json as _j, urllib.request
        from fixtures.form3 import Driver, Codec, A0, A_next, id_epochal, id_notice
        from fixtures.crypto import verify_object, Hb, H
        from fixtures.netfix import EventLog, ScriptedWitness, MailboxProxy
        b = self.new_budget()
        aid, nonce = b.new_run(upto='CONSUMED')
        seen = []

        class Stub:
            public_key = 'stub'
            def request(self, method, path, body, client):
                seen.append((method, path, client))
                return 200, _j.dumps({'statement': 'CHALLENGE', 'token': 'T' * 43, 'mailbox_epoch': 'E', 'anchor': {'n': 0, 'head': None}}).encode()
        self.mb_config = SUT.MailboxConfig(writers=['courier'], readers=['reader'], budgets={b.root: self.ckey.public_hex}, witness_keys=[], L=60.0, R=30.0)
        d = Driver(self, Stub(), Codec(), b.root, self.ckey, self.wkey, budget=b)
        it, st, ans = d.open_epoch()
        self.assertTrue(verify_object(it, [self.ckey.public_hex]))
        self.assertEqual(set(it), {'statement', 'form', 'kind', 'root', 'chain_epoch', 'k', 'prev', 'identity', 'body', 'time', 'courier', 'signer', 'signature'})
        self.assertEqual((it['k'], it['prev'], it['identity']), (1, A0(b.root, it['chain_epoch']), id_epochal(b.root, 'EPOCH_OPEN', it['chain_epoch'], it['body'])))
        self.assertEqual(it['body']['commit'], Hb(d.secret)); self.assertIsNone(it['body']['closes'])
        n = d.notice('FAIL', name='x', basis=['FAIL', 3, None]); self.assertEqual(n['identity'], id_notice(b.root, 'FAIL', 'x', ['FAIL', 3, None]))
        self.assertEqual((n['k'], n['prev']), (2, A_next(A0(b.root, it['chain_epoch']), it['identity'])))
        ch = d.challenge()
        s = d.statement(ch)
        self.assertEqual(s['body']['checkpoint']['nonce'], 'T' * 43); self.assertEqual(s['body']['reveal'], d.secret.hex())
        self.assertEqual(s['body']['checkpoint']['at'], 0); self.assertEqual(s['body']['checkpoint']['head_at'], b.prov_hash)
        log = EventLog(); w = ScriptedWitness(log, self.wkey); self.later(w.close); w.budgets[b.root] = b
        import urllib.parse as up
        get = lambda p: _j.loads(urllib.request.urlopen(w.url + p, timeout=5).read())
        cp = get('/checkpoint?' + up.urlencode({'root': b.root, 'nonce': 'abc', 'at': 0}))
        self.assertEqual((cp['seq'], cp['head'], cp['head_at'], cp['nonce']), (b.n, b.head, b.prov_hash, 'abc'))
        self.assertEqual(len(get('/chain?' + up.urlencode({'root': b.root, 'after': 0}))['rows']), b.n)
        self.assertEqual(get('/run?' + up.urlencode({'root': b.root, 'aid': aid}))['aid'], aid)
        px = MailboxProxy(log, Stub()); self.later(px.close)
        req = urllib.request.Request(px.url + '/deliver', data=_j.dumps(n).encode(), headers={'X-Acc-Client': 'courier', 'Content-Type': 'application/json'})
        self.assertEqual(urllib.request.urlopen(req, timeout=5).status, 200)
        self.assertEqual(px.delivered()[0]['body'], n); self.assertEqual(seen[-1], ('POST', '/deliver', 'courier'))
