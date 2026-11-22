# Probe P2 (expectations before running):
#  E1: bound() True only for root '<...>/<h[:32]>' with h 64 lowercase hex; False for upper case, 32-hex h, non-str, missing, unicode digits,
#      root without '/', trailing '/', root suffix in upper case.
#  E2: plea_mcp.GovernedServer(tools=verify_tools.TOOLS).list_tools() raises ValueError (3-tuple unpack of a 4-tuple)
import sys, hashlib
T='/tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad/review_a1/tree'
sys.path[:0]=[T+'/verify', T, T+'/mcp']
import verify_tools as V
h=hashlib.sha256(b'x').hexdigest()
cases={'ok':('REQ-1/A/'+h[:32],{'baseline_sha256':h}),
 'req id with slash':('REQ/1/A/'+h[:32],{'baseline_sha256':h}),
 'upper h':('R/A/'+h[:32].upper(),{'baseline_sha256':h.upper()}),
 'upper root only':('R/A/'+h[:32].upper(),{'baseline_sha256':h}),
 '32-hex h':('R/A/'+h[:32],{'baseline_sha256':h[:32]}),
 'missing':('R/A/'+h[:32],{}),
 'non-str':('R/A/'+h[:32],{'baseline_sha256':int(h,16)}),
 'fullwidth digits':('R/A/'+h[:32],{'baseline_sha256':h.replace('0','０')}),
 'no slash':(h[:32],{'baseline_sha256':h}),
 'trailing slash':('R/A/'+h[:32]+'/',{'baseline_sha256':h}),
 'root full hash':('R/A/'+h,{'baseline_sha256':h}),
 'root None':(None,{'baseline_sha256':h}),
 'args list':('R/A/'+h[:32],[h]),
 'other baseline same root':('R/A/'+h[:32],{'baseline_sha256':hashlib.sha256(b'y').hexdigest()}),
}
for n,(r,a) in cases.items(): print(f'E1 {n:28} -> {V.bound(r,a)}')
import plea_mcp
class G: host=None
try:
    print('E2', plea_mcp.GovernedServer(G(), V.TOOLS).list_tools()[:1])
except Exception as exc:
    print('E2 list_tools raised', type(exc).__name__, exc)
