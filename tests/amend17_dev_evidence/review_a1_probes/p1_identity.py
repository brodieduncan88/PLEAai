# Probe P1 (expectation written before running):
#  E1: sample legacy record verifies, identities == 'legacy'
#  E2: R31-style mutation (aid -> 'a-'+sha(key)[:16]) on a record fails check 5 EVEN IF identity_form is neutralised
#      (i.e. R31's 'mixed' check is not sensitive to the identity_form rule)
#  E3: identity_form([legacy-with-args, current-with-args]) is None  -> any genuine straddling record fails check 5
#  E4: identity_form of an attempt with aid a2-<64> and key verify:<24> is None
import sys, json, copy, hashlib, re
T='/tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad/review_a1/tree'
sys.path[:0]=[T+'/verify', T]
import check_record as C
sha=lambda x: hashlib.sha256(x.encode()).hexdigest()
rec=json.load(open(T+'/verify/sample/record_revA.json')); keys=json.load(open(T+'/verify/sample/keys.json'))
ok,checks,s=C.verify(rec,keys)
print('E1 sample verifies', ok, 'identities', s.get('identities'), 'n attempts', len(rec['attempts']))
def fails5(r):
    ok,ch,_=C.verify(r,keys); return ok, [d for n,t,good,d in ch if n==5 and not good] if False else [ (n,good,d) for (n,t,good,d) in ch if not good]
m=copy.deepcopy(rec); a=m['attempts'][0]; print('orig aid/key', a['aid'], a['request_key'])
a['aid']='a-'+sha(a['request_key'])[:16]+'0'   # any different aid, as R31 does (R31 changes a current aid to legacy shape)
print('E2 mutated:', fails5(m))
orig=C.identity_form
C.identity_form=lambda atts: 'legacy'   # rule neutralised
print('E2 mutated, identity_form neutralised:', fails5(m))
C.identity_form=orig
L={'aid':'a-'+'0'*16,'request_key':'verify:'+'0'*24,'arguments':{'baseline_sha256':'x','design':{}}}
Cu={'aid':'a2-'+'0'*64,'request_key':'verify:'+'0'*64,'arguments':{'baseline_sha256':'x','design':{}}}
H={'aid':'a2-'+'0'*64,'request_key':'verify:'+'0'*24,'arguments':{'baseline_sha256':'x','design':{}}}
print('E3 straddle', C.identity_form([L,Cu]))
print('E4 hybrid', C.identity_form([H]), ' empty', C.identity_form([]), ' noargs-only', C.identity_form([{'aid':'!x','request_key':'?'}]))
print('upper-case hex aid', C.identity_form([{'aid':'a2-'+'A'*64,'request_key':'verify:'+'A'*64,'arguments':{}}]))
