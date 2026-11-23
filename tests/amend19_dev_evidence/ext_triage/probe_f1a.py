"""F-1a retry. Expectation: with the format field set (the first run's refusal was the missing format field of a case card, not the bounds), validate_card accepts float plausible and design_space bounds."""
import json, sys
sys.path.insert(0, sys.argv[1] + '/verify')
import baseline as B
card = json.loads(open(sys.argv[1] + '/verify/cases/pump-station-submain/card.json').read())
card['format'] = 'verification-baseline/1'; card['inputs'] = [dict(i, sha256='0'*64) for i in card['inputs']]; card['baselined_at'] = '2026-11-23T00:00:00Z'; card['responsible_engineer']['key'] = 'ab'*32; card['check']['sha256'] = '0' * 64
card['criteria'][1]['plausible']['min'] = 0.3; card['design_space'] = {'x': {'min': 1e23, 'max': 2e23}}
for _ in range(10):
    try: B.validate_card(card); print('accepted with float bounds'); break
    except Exception as e:
        msg = str(e); print('refused:', msg)
        if 'bound' in msg or 'plausible' in msg or 'design_space' in msg: break
        break
