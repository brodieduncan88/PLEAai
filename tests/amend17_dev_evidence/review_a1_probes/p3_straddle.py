# Probe P3 (expectations before running):
#  E1: for one design D on one baseline, a run made before A1 (legacy key/aid) and the run the front door makes for D after A1
#      have different request keys and attempt ids (so the second is a new attempt: charged and run again).
#  E2: verify_record.attempts_of gives both runs their design (journal holds D once).
#  E3: check_record.identity_form over those attempts is None (check 5 fails for the straddling record).
#  E4: a legacy record whose runs have no design found reads 'current'.
import sys, hashlib, contextlib
T='/tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad/review_a1/tree'
sys.path[:0]=[T+'/verify', T]
import verify_record as VR, check_record as C
from plea_gateway.governor import attempt_id as gov_aid
h=hashlib.sha256(b'baseline').hexdigest(); D={'material':'PA66','wall_mm':3,'mode':'normal'}
args=VR.arguments_for(h,D)
old_key=VR.request_key(args,legacy=True); old_aid=C.attempt_id(old_key,legacy=True)
new_key=VR.request_key(args); new_aid=gov_aid(new_key)
print('E1', old_key, old_aid, '|', new_key[:20]+'...', new_aid[:12]+'...', 'same attempt?', old_aid==new_aid)
class Conn:
    def execute(self,*a): return self
    def fetchall(self): return []
    def rollback(self): pass
class Store:
    @contextlib.contextmanager
    def connect(self): yield Conn()
    def audit_snapshot(self, root):
        return [], {'attempts':[(old_aid,old_key,'CONSUMED','n1',None,True),(new_aid,new_key,'EFFECT','n2',None,True)]}
atts,_=VR.attempts_of(Store(),'R/A/'+h[:32],[args])
print('E2', [(a['aid'][:6], a['arguments'] is not None, a['outcome']) for a in atts])
print('E3 identity_form', C.identity_form(atts))
print('E4', C.identity_form([{'aid':old_aid,'request_key':old_key,'arguments':None}]))
