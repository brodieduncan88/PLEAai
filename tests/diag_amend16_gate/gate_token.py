"""Design gate, part A (21 November 2026): a 32-byte token, as a mailbox would issue it, through the witness's real
checkpoint reading.  What the reading accepts, what it signs, and whether what it signs ties the token to one budget.
No code is changed.  DIAG_DB=<fresh database> python gate_token.py SRC OUT"""
import base64, copy, json, secrets, urllib.parse
from gate_common import *                                      # noqa: F401,F403

b = Bench('GT')
try:
    s, root, q = b.s, b.root, b.q
    b.r.submit({'material': 'PA66-GF30', 'wall_mm': 2.5, 'mode': 'normal'})          # one run, so the chain has decisions
    raw = secrets.token_bytes(32)
    forms = {'url-safe base64, no padding': base64.urlsafe_b64encode(raw).rstrip(b'=').decode(),
             'lower-case hexadecimal': raw.hex(),
             'url-safe base64 with its padding': base64.urlsafe_b64encode(raw).decode(),
             'standard base64 with its padding': base64.b64encode(b'\xfb\xff' + raw[2:]).decode()}

    def cp(nonce=None, root_=None, cert=None, extra=''):
        path = '/checkpoint?root=' + urllib.parse.quote(root if root_ is None else root_, safe='') + ('' if nonce is None else '&nonce=' + urllib.parse.quote(nonce, safe='')) + extra
        return b.call(path, cert or b.cour)

    out = {}
    for name, text in forms.items():
        st, ans = cp(text)
        out[name] = {'characters': len(text), 'has + / or =': any(c in text for c in '+/='), 'status': st,
                     'nonce signed back, exactly as sent': (ans or {}).get('nonce') == text if st == 200 else None,
                     'checkpoint verifies for this budget (check_record.checkpoint_problems)': C.checkpoint_problems(ans, [b.WIT], root) if st == 200 else None,
                     'bytes of the checkpoint as JSON': len(json.dumps(ans)) if st == 200 else None, 'error': (ans or {}).get('error') if st != 200 else None}
    note('A1. 32 random bytes, four ways of writing them', token_bytes=len(raw), forms=out)

    limits = {}
    for n in (1, 43, 63, 64, 65, 128):
        st, ans = cp('A' * n); limits[f'{n} characters'] = st
    st_empty, _ = cp(''); st_none, ans_none = cp(None)
    odd = {name: cp(text)[0] for name, text in {'a space inside': 'ab cd', 'a dot': 'ab.cd', 'a tilde': 'ab~cd', 'a NUL': 'ab\x00cd', 'non-ASCII letter': 'abécd', 'a newline': 'ab\ncd'}.items()}
    note('A2. the limit on length and the letters allowed', statuses=limits, empty_nonce=st_empty, no_nonce={'status': st_none, 'nonce in the checkpoint': (ans_none or {}).get('nonce')}, other_characters=odd)

    tok = forms['url-safe base64, no padding']
    st, good = cp(tok)
    signed_fields = list(C.CHECKPOINT_FIELDS)
    def problems(c, for_root=root):
        return C.checkpoint_problems(c, [b.WIT], for_root)
    t_nonce = dict(good, nonce=forms['lower-case hexadecimal'][:43]); t_root = dict(good, root=root + 'x'); t_seq = dict(good, seq=good['seq'] + 1); t_time = dict(good, time='2026-11-21T00:00:00Z')
    note('A3. what the witness signs, and what a change to it does', checkpoint=good, fields_under_the_signature=signed_fields,
         unchanged=problems(good), nonce_changed=problems(t_nonce), budget_changed=problems(t_root), number_changed=problems(t_seq), time_changed=problems(t_time),
         checked_against_another_budget=problems(good, 'some-other-budget'))

    # a second budget at the same witness
    second = None
    try:
        card2 = VT.draft(); card2['title'] = str(card2.get('title', 'baseline')) + ' (second budget, design gate)'
        env2 = s.baseline(VT.CASE, card2, alongside_reason='design gate: a second budget at one witness')
        second = VT.B.root_for(env2['card'])
    except Exception as exc:
        note('A4. a second budget could not be made', error=f'{type(exc).__name__}: {str(exc)[:300]}')
    if second and second != root:
        st1, c1 = cp(tok); st2, c2 = cp(tok, root_=second)
        note('A4. one token asked for two budgets at one witness', budgets_differ=second != root, statuses=[st1, st2],
             both_sign_the_same_token=[c1.get('nonce') == tok, c2.get('nonce') == tok],
             each_names_its_own_budget=[c1.get('root') == root, c2.get('root') == second],
             first_checked_for_first=problems(c1, root), first_checked_for_second=problems(c1, second), second_checked_for_first=problems(c2, root), second_checked_for_second=problems(c2, second),
             second_relabelled_as_first=problems(dict(c2, root=root), root),
             the_witness_refused_the_second_use=False)

    st_a, a1 = cp(tok); time.sleep(1.1); st_b, a2 = cp(tok)
    note('A5. the same token asked twice for one budget', statuses=[st_a, st_b], identical_answers=a1 == a2, both_verify=[problems(a1), problems(a2)], times=[a1.get('time'), a2.get('time')],
         meaning='the witness keeps no memory of a nonce: single use is not enforced by it')

    st, twice = b.call(f'/checkpoint?root={q}&nonce=FIRSTTOKEN&nonce={tok}', b.cour); st2, twice2 = b.call(f'/checkpoint?root={q}&nonce={tok}&nonce=SECONDTOKEN', b.cour)
    note('A6. the nonce given twice in one request', first=[st, twice.get('nonce')], second=[st2, twice2.get('nonce')], meaning='the last one is signed; a reader must compare the signed field, never the request')

    seq = good['seq']; st, at_cp = cp(tok, extra=f'&at={seq}'); st0, at0 = cp(tok, extra='&at=1'); st9, at9 = cp(tok, extra=f'&at={seq + 50}')
    note('A7. the checkpoint naming a decision', at_head={'status': st, 'at': at_cp.get('at'), 'head_at equals head': at_cp.get('head_at') == at_cp.get('head'), 'problems': problems(at_cp)},
         at_one={'status': st0, 'at': at0.get('at'), 'head_at differs from head': at0.get('head_at') != at0.get('head'), 'problems': problems(at0)}, beyond={'status': st9, 'error': (at9 or {}).get('error')})

    who = {}
    for name in ('courier', 'keeper', 'governor', 'mailbox', 'host'):
        cert = s.pki.get(name)
        if cert:
            try:
                who[name] = cp(tok, cert=cert)[0]
            except Exception as exc:                     # a server's certificate is refused as a client's by TLS itself
                who[name] = f'no answer: {type(exc).__name__}: {str(exc)[:80]}'
    note('A8. who is given a checkpoint', statuses_by_client_certificate=who)

    long_root_cp = dict(good, root='r' * 512, nonce='N' * 64, at=10**11, head_at='f' * 64)
    chal = {'statement': 'CHALLENGE', 'token': tok, 'budget': root, 'mailbox': 'engineer-mailbox', 'epoch': secrets.token_hex(16), 'issued_tick': 123456789012, 'limit_s': 900, 'time': '2026-11-21T18:30:00Z', 'signer': 'f' * 64, 'signature': 'f' * 128}
    note('A9. sizes', checkpoint_with_this_token=len(json.dumps(good)), checkpoint_at_the_largest_names=len(json.dumps(long_root_cp)),
         a_challenge_of_the_proposed_shape=len(json.dumps(chal)), a_challenge_with_a_512_character_budget_name=len(json.dumps(dict(chal, budget='r' * 512))))
finally:
    save('gate_token.json'); b.stop()
