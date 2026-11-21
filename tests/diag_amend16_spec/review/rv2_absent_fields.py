"""Review 2, round 2 (offline, no deployment, no database): a genuine-form FENCE_REPORT with its null-valued keys
`nonce` and `result_digest` deleted.  Does it still verify, as the witness and the record checker verify it?
The gate key here is a fresh local key standing in for an honest host's signature (the honest host's code signs this
exact message); deleting keys needs no key (CAP-DB).   python rv2_absent_fields.py SRC"""
import json, sys
SRC = sys.argv[1]; sys.path[:0] = [SRC, SRC + '/verify']
from plea_gateway.evidence import GateSigner, derive_release_label, _parse, _genuine
import check_record as C
g = GateSigner(); rep = g.fence_report('ROOT-1', 'a-1').to_json()
cut = {k: v for k, v in rep.items() if k not in ('nonce', 'result_digest')}
proj = lambda r: {k: r.get(k) for k in ('kind', 'root', 'aid', 'nonce', 'claim', 'result_digest', 'signer', 'signature')}
for name, r in (('as signed', rep), ('null keys deleted', cut)):
    print(name, json.dumps({'keys': sorted(r), 'witness label': derive_release_label(r, (g.public_hex,), 'ROOT-1', 'a-1'),
          'record checker signature ok': C.signed_by(r['signer'], r['signature'], C.evidence_message(r)),
          'H(object)': C.sha(C.canonical(r))[:16], 'H(projection, absent read as null)': C.sha(C.canonical(proj(r)))[:16]}))
