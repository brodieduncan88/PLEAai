"""Reviewer's experiments, phase 1 (21 November 2026).  Independent of the author's predicates: every predicate here is
the reviewer's and is named REVIEWER_*.  No code of e25a297 is changed.  Powers used: plea_local, the governor's client
certificate (POST /accept), the gate key (as the threat model grants), the courier certificate for readings.
The courier's key is used ONLY in R5 to stand in for an honest courier whose notice was delayed (labelled).
    DIAG_DB=plea25 python -B rv_conflict.py SRC OUT
"""
import hashlib, secrets, shutil, base64
from rv_common import *                                        # noqa: F401,F403
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
import courier as COURIER                                      # noqa: E402  (verify/courier.py, for make_notice only)
from mailbox_service import MailboxKey                         # noqa: E402

# ---------------------------------------------------------------- Ed25519 with a chosen r (RFC 8032 arithmetic)
P_ = 2**255 - 19; L_ = 2**252 + 27742317777372353535851937790883648493; D_ = -121665 * pow(121666, P_ - 2, P_) % P_; I_ = pow(2, (P_ - 1) // 4, P_)
def _xr(y):
    xx = (y * y - 1) * pow(D_ * y * y + 1, P_ - 2, P_); x = pow(xx, (P_ + 3) // 8, P_)
    if (x * x - xx) % P_: x = x * I_ % P_
    return P_ - x if x % 2 else x
_By = 4 * pow(5, P_ - 2, P_) % P_; _Bx = _xr(_By); BASE = (_Bx, _By, 1, _Bx * _By % P_)
def _add(p, q):
    (X1, Y1, Z1, T1), (X2, Y2, Z2, T2) = p, q
    A = (Y1 - X1) * (Y2 - X2) % P_; B = (Y1 + X1) * (Y2 + X2) % P_; Cc = T1 * 2 * D_ * T2 % P_; Dd = Z1 * 2 * Z2 % P_
    E, F, G, H = B - A, Dd - Cc, Dd + Cc, B + A
    return (E * F % P_, G * H % P_, F * G % P_, E * H % P_)
def _mul(s, p):
    q = (0, 1, 1, 0)
    while s:
        if s & 1: q = _add(q, p)
        p = _add(p, p); s >>= 1
    return q
def _enc(p):
    X, Y, Z, T = p; zi = pow(Z, P_ - 2, P_); x, y = X * zi % P_, Y * zi % P_
    return (y | ((x & 1) << 255)).to_bytes(32, 'little')
def sign_with_r(sk_hex, msg, r):
    h = hashlib.sha512(bytes.fromhex(sk_hex)).digest(); a = int.from_bytes(h[:32], 'little'); a &= (1 << 254) - 8; a |= 1 << 254
    A = _enc(_mul(a, BASE)); R = _enc(_mul(r, BASE)); k = int.from_bytes(hashlib.sha512(R + A + msg).digest(), 'little') % L_
    return (R + ((r + k * a) % L_).to_bytes(32, 'little')).hex()

def resigned(rep, sk_hex):
    sig = sign_with_r(sk_hex, C.evidence_message(rep), secrets.randbelow(L_ - 1) + 1); return dict(rep, signature=sig)

# ---------------------------------------------------------------- the reviewer's own predicates
def genuine_in_scope(b, item, aid, nonce):
    e = item.get('evidence') if isinstance(item, dict) else None
    return isinstance(e, dict) and e.get('kind') == 'EFFECT_REPORT' and e.get('signer') == b.GATE and C.signed_by(b.GATE, e.get('signature', ''), C.evidence_message(e)) \
        and (e.get('root'), e.get('aid'), e.get('nonce')) == (b.root, aid, nonce)

def REVIEWER_pairs(b, items, aid, nonce):
    """distinct (claim, result_digest) over genuine in-scope reports whose claim is a final verdict, any decision kind."""
    return sorted({(i['evidence']['claim'], i['evidence'].get('result_digest')) for i in items if genuine_in_scope(b, i, aid, nonce) and i['evidence']['claim'] in ('EFFECT', 'NO_EFFECT')})

def REVIEWER_bytes(b, items, aid, nonce):
    """distinct whole-report hashes (what a rule keyed on report bytes would compare)."""
    return sorted({C.sha(C.canonical(i['evidence'])) for i in items if genuine_in_scope(b, i, aid, nonce) and i['evidence']['claim'] in ('EFFECT', 'NO_EFFECT')})

def REVIEWER_authorised_rows_carried(chain, items, aid):
    """every chain decision ['RECONCILE', aid, v, 'AUTHORISED'] (any kind) has an item at its seq claiming v."""
    by = {i.get('seq'): i for i in items}
    missing = [d['seq'] for d in chain if d['op'][:2] == ['RECONCILE', aid] and d['op'][-1] == 'AUTHORISED'
               and not (d['seq'] in by and isinstance(by[d['seq']].get('evidence'), dict) and by[d['seq']]['evidence'].get('claim') == d['op'][2])]
    return missing

def short(items):
    return [(i['seq'], (i.get('evidence') or {}).get('claim') if isinstance(i.get('evidence'), dict) else type(i.get('evidence')).__name__,
             ((i.get('evidence') or {}).get('result_digest') or '')[:12] if isinstance(i.get('evidence'), dict) else None,
             ((i.get('evidence') or {}).get('signature') or '')[:12] if isinstance(i.get('evidence'), dict) else None, i.get('derived')) for i in items]

def courier(b, name):
    code, summary = b.s.courier([b.root], 900, name)
    return {'exit': code, 'made': [(m.get('aid', '')[:14], m.get('outcome')) for m in summary.get('made', [])] if isinstance(summary, dict) and 'made' in summary else summary}

def courier_state(b, name):
    try:
        st = json.loads((b.s.dir / name / 'state.json').read_text())
    except Exception as exc:
        return {'unreadable': str(exc)}
    w = (st.get('roots') or {}).get(b.root)
    return {'seq': w.get('seq'), 'final': w.get('final'), 'sent': w.get('sent')} if isinstance(w, dict) else {'raw keys': list(st)[:10]}

def forge(value):
    f = copy.deepcopy(value); f.update(verdict='PASS', reason_code='MET')
    for c in f.get('criteria') or []:
        c.update(met=True, achieved='220', margin='20')
    return f

def record_check(b, mutate=None):
    rec = b.r.record()
    if mutate:
        rec = mutate(copy.deepcopy(rec))
    ok, checks, summary = C.verify(rec, b.s.keys)
    return ok, [f'{n} {t}: {d}'[:240] for n, t, good, d in checks if not good], rec

def att_of(rec, aid):
    return next((x for x in rec.get('attempts', []) if x.get('aid') == aid), None) or {}

BADD = {'material': 'PA66-GF30', 'wall_mm': 3, 'mode': 'normal'}

b = Bench('RV1')
try:
    s, root = b.s, b.root
    def withheld_submit(design):
        client = verify_client.Client(b.r.cfg); held = []; client.store.put_result = lambda root_, aid_, stored: held.append(stored)
        before = b.attempts(); code, out = client.submit(design); return b.newest(before), VT.head(out), held[0]

    # ============ R1: post-final conflicting reports, after the courier has taken the run as final
    before = b.attempts(); code, out = b.r.submit(BADD); x = b.newest(before)
    stored_x = b.local.get_result(root, x['aid'])
    c1 = courier(b, 'cA'); st1 = courier_state(b, 'cA'); cur = b.chain()[-1]['seq']
    honest_rep = (stored_x or {}).get('report'); forged = forge(stored_x['value'])
    sends = []
    sends.append(('forged PASS EFFECT via RECONCILE', b.accept(('RECONCILE', x['aid']), b.report(x['aid'], x['nonce'], 'EFFECT', forged))))
    forged2 = dict(forged, note='second forgery'); sends.append(('another forged EFFECT via RELEASE', b.accept(('RELEASE', x['aid']), b.report(x['aid'], x['nonce'], 'EFFECT', forged2))))
    sends.append(('NO_EFFECT via RECONCILE', b.accept(('RECONCILE', x['aid']), b.report(x['aid'], x['nonce'], 'NO_EFFECT', None))))
    rs = resigned(honest_rep, s.gate.private_hex)
    sends.append(('the honest FAIL report re-signed with another r (same claim, same digest, other signature bytes)', b.accept(('RECONCILE', x['aid']), rs)))
    sig_ok = True
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(b.GATE)).verify(bytes.fromhex(rs['signature']), C.evidence_message(rs))
    except Exception:
        sig_ok = False
    sends.append(('UNKNOWN via RECONCILE after the verdict', b.accept(('RECONCILE', x['aid']), b.report(x['aid'], x['nonce'], 'UNKNOWN', {'error': 'late'}))))
    st_, ans = b.run_reading(x['aid']); items = ans['evidence']; chain = b.chain()
    c2 = courier(b, 'cA'); st2 = courier_state(b, 'cA')
    ok_rec, fails_rec, rec = record_check(b)
    note('R1. a FAIL committed (stored as a value) and noticed; then four more gate-signed reports for the run, and a late UNKNOWN',
         first_courier_pass=c1, courier_state_after_first=st1, re_signed_signature_verifies=sig_ok, re_signed_differs_in_bytes=rs['signature'] != honest_rep['signature'],
         sends=[(n, [a['status'], a['kind'], a['code'], (a['applied'] or [None])[-1]]) for n, a in sends],
         reading_after=short(items), chain_rows_after_courier_cursor_naming_run=[[d['seq']] + d['op'][:1] + d['op'][2:] + [d['kind'], d['code']] for d in chain if d['seq'] > cur and len(d['op']) > 1 and d['op'][1] == x['aid']],
         chain_observation_entry_changed_after_cursor=len({C.canonical([a for a in d['observation']['attempts'] if a[0] == x['aid']]) for d in chain if d['seq'] >= cur}) > 1,
         second_courier_pass=c2, courier_state_after_second=st2,
         e25a297_run_outcome_now=C.run_outcome('EFFECT', items, stored_x['value'], [b.GATE], root, x['aid'], x['nonce']),
         REVIEWER_pairs=REVIEWER_pairs(b, items, x['aid'], x['nonce']), REVIEWER_bytes_count=len(REVIEWER_bytes(b, items, x['aid'], x['nonce'])),
         record_verifies_e25a297=ok_rec, record_failures=fails_rec)

    # ============ R2: replacement before commitment (S-1), then the service omits the honest report from the record it assembles
    y, line_y, held_y = withheld_submit({'material': 'PA66-GF30', 'wall_mm': 3.5, 'mode': 'normal'})
    rep_p = b.report(y['aid'], y['nonce'], 'EFFECT', forge(held_y['value'])); acc_p = b.accept(('RECONCILE', y['aid']), rep_p)
    b.local.put_result(root, y['aid'], {'outcome': 'value', 'value': forge(held_y['value']), 'nonce': y['nonce'], 'report': rep_p})
    ok_a, fails_a, rec_a = record_check(b)
    def drop_honest(rec):
        a = att_of(rec, y['aid']); a['evidence'] = [i for i in a.get('evidence', []) if i['evidence'].get('result_digest') == rep_p['result_digest']]; return rec
    ok_b, fails_b, rec_b = record_check(b, drop_honest)
    chain = b.chain()
    note('R2. S-1 replacement; the record as assembled, and the record with the honest FAIL report left out',
         client_was_told=line_y, forged_report_answer=[acc_p['kind'], acc_p['code']], courier=courier(b, 'cA'),
         full_record={'verifies_e25a297': ok_a, 'failures_for_this_run': [f for f in fails_a if y['aid'] in f], 'outcome': att_of(rec_a, y['aid']).get('outcome'),
                      'reports': short(att_of(rec_a, y['aid']).get('evidence', [])), 'REVIEWER_pairs': REVIEWER_pairs(b, att_of(rec_a, y['aid']).get('evidence', []), y['aid'], y['nonce'])},
         record_with_honest_report_omitted={'verifies_e25a297': ok_b, 'failures_for_this_run': [f for f in fails_b if y['aid'] in f], 'outcome': att_of(rec_b, y['aid']).get('outcome'),
                      'reports': short(att_of(rec_b, y['aid']).get('evidence', [])), 'REVIEWER_pairs': REVIEWER_pairs(b, att_of(rec_b, y['aid']).get('evidence', []), y['aid'], y['nonce']),
                      'REVIEWER_authorised_rows_without_their_report': REVIEWER_authorised_rows_carried(chain, att_of(rec_b, y['aid']).get('evidence', []), y['aid'])},
         record_top_level_keys=sorted(rec_a.keys()))

    # ============ R3: planted before START with RECONCILE (label WRONG_BINDING), honest FAIL APPLIED, forged PASS stored
    planted = {}; orig_apply = Store.apply
    def planting_apply(self, root_, op):
        if op[0] == 'START' and 'aid' not in planted:
            planted.update(aid=op[1], nonce=op[2]); planted['report'] = b.report(op[1], op[2], 'EFFECT', {'verdict': 'PASS', 'planted': True})
            planted['answer'] = b.accept(('RECONCILE', op[1]), planted['report'])
        return orig_apply(self, root_, op)
    Store.apply = planting_apply
    try:
        z, line_z, held_z = withheld_submit({'material': 'PA66-GF30', 'wall_mm': 2.5, 'mode': 'normal'})
    finally:
        Store.apply = orig_apply
    b.local.put_result(root, z['aid'], {'outcome': 'value', 'value': {'verdict': 'PASS', 'planted': True}, 'nonce': z['nonce'], 'report': planted['report']})
    st_, ansz = b.run_reading(z['aid']); chain = b.chain()
    ok_c, fails_c, rec_c = record_check(b)
    def drop_honest_z(rec):
        a = att_of(rec, z['aid']); a['evidence'] = [i for i in a.get('evidence', []) if i['evidence'].get('result_digest') == planted['report']['result_digest']]; return rec
    ok_d, fails_d, rec_d = record_check(b, drop_honest_z)
    note('R3. a report planted with RECONCILE before START (nonce not yet in the chain), the run then honest (FAIL), the planted PASS stored',
         planted_answer=[planted['answer']['kind'], planted['answer']['code'], planted['answer']['applied']], client_was_told=line_z,
         reading=short(ansz['evidence']), e25a297_run_outcome_with_stored=C.run_outcome('EFFECT', ansz['evidence'], {'verdict': 'PASS', 'planted': True}, [b.GATE], root, z['aid'], z['nonce']),
         courier=courier(b, 'cA'), REVIEWER_pairs=REVIEWER_pairs(b, ansz['evidence'], z['aid'], z['nonce']),
         full_record={'verifies_e25a297': ok_c, 'failures_for_this_run': [f for f in fails_c if z['aid'] in f], 'outcome': att_of(rec_c, z['aid']).get('outcome')},
         record_with_honest_omitted={'verifies_e25a297': ok_d, 'failures_for_this_run': [f for f in fails_d if z['aid'] in f], 'outcome': att_of(rec_d, z['aid']).get('outcome'),
                                     'REVIEWER_authorised_rows_without_their_report': REVIEWER_authorised_rows_carried(chain, att_of(rec_d, z['aid']).get('evidence', []), z['aid'])},
         failures_from_other_runs_in_full_record=[f for f in fails_c if z['aid'] not in f][:6])

    # ============ R4: the 32-byte token through the real checkpoint (reproduction of the author's A1/A2, A4 not repeated)
    raw = secrets.token_bytes(32); forms = {'b64url43': base64.urlsafe_b64encode(raw).rstrip(b'=').decode(), 'hex64': raw.hex(), 'hex64+1': raw.hex() + 'a', 'b64pad44': base64.urlsafe_b64encode(raw).decode()}
    tok = {}
    for k, v in forms.items():
        stt, cp = b.call(f'/checkpoint?root={b.q}&nonce={urllib.parse.quote(v, safe="")}', b.cour)
        tok[k] = {'len': len(v), 'status': stt, 'signed_back': (cp or {}).get('nonce') == v if stt == 200 else None, 'problems': C.checkpoint_problems(cp, [b.WIT], root) if stt == 200 else (cp or {}).get('error'),
                  'fields': sorted(cp) if stt == 200 else None}
    stt, cp1 = b.call(f'/checkpoint?root={b.q}&nonce={forms["hex64"]}', b.cour); stt2, cp2 = b.call(f'/checkpoint?root={b.q}&nonce={forms["hex64"]}', b.cour)
    note('R4. a 32-byte token through GET /checkpoint', forms=tok, same_token_twice_both_valid=[C.checkpoint_problems(cp1, [b.WIT], root), C.checkpoint_problems(cp2, [b.WIT], root)],
         witness_time_field=[cp1.get('time'), cp2.get('time')])

    # ============ R5: the mailbox and an old statement (delayed delivery; restart; lost storage)
    ck = MailboxKey((s.dir / 'courier.key').read_text().strip()); cfg = {'name': 'courier'}
    cpn = b.call(f'/checkpoint?root={b.q}', b.cour)[1]
    n = COURIER.make_notice(cfg, ck, root, None, C.WATCHING, None, cpn['seq'], cpn['head'])
    old = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() - 3 * 3600)); n = dict(n, time=old); n.pop('signature'); n.pop('signer')
    n = dict(n, signer=ck.public_hex, signature=ck.sign(C.canonical({k: n[k] for k in C.NOTICE_FIELDS_2}).encode()))
    mb = f"https://127.0.0.1:{s.ports['mailbox']}"
    def deliver(nn):
        stt, ans = b.call('/deliver', b.cour, 'POST', nn, base=mb); return stt, ans
    d1 = deliver(n); time.sleep(1.2)
    s.stop_mailbox(); s.start_mailbox(); d2 = deliver(n)
    s.stop_mailbox(); shutil.move(str(s.dir / 'mailbox'), str(s.dir / 'mailbox.lost')); s.start_mailbox(); time.sleep(1.2); d3 = deliver(n)
    note('R5. a WATCHING statement signed with a time 3 h old (an honest courier\'s notice delivered late, as its outbox would), then after a mailbox restart, then after the mailbox lost its folder',
         notice_time=old, problems_in_notice=C.notice_problems(n, [ck.public_hex]),
         first=[d1[0], (d1[1] or {}).get('time'), (d1[1] or {}).get('error')], after_restart=[d2[0], (d2[1] or {}).get('time'), 'same receipt' if d1[1] == d2[1] else 'different receipt'],
         after_lost_folder=[d3[0], (d3[1] or {}).get('time'), 'same receipt' if d1[1] == d3[1] else 'different receipt'],
         mailbox_paths=['POST /deliver', 'GET /pubkey'])
finally:
    save('rv_conflict.json'); b.stop()
