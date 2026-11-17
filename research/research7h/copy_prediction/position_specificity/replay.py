"""Replay V perturbations solely from previously saved copy-model artifacts.
No corpus parser import; no confirm/reserve reload. Independently enumerated edits.
"""
from pathlib import Path
from collections import defaultdict,Counter
from functools import lru_cache
import datetime,hashlib,json,math
import numpy as np
P=Path(__file__).resolve().parent;C=P.parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def replay(name):
 result=json.loads((P/'runs'/('confirm_'+name+'.json')).read_text())
 old=json.loads((C/'runs'/(name+'.json')).read_text());cfg=json.loads((C/old['config_path']).read_text())
 assert sha(C/old['targets_path'])==old['targets_sha256'] and sha(C/old['scores_path'])==old['scores_sha256']
 rows=json.loads((C/old['targets_path']).read_text());scores=np.load(C/old['scores_path']);A=set(cfg['alphabet']);M=cfg['escape_size'];classes=tuple(sorted(A|({'<UNK>'} if M else set())))
 hv=cfg['selected']['edit_HV'];hm=cfg['selected']['edit_H_matched'];N=len(rows);bp=np.exp2(scores['base']);hscore=scores['edit_H_matched']
 lookup={(r['folio'],r['line'],r['slot']):tuple(r['word']) for r in rows};rowwidth={(r['folio'],r['line']):r['line_slots'] for r in rows}
 @lru_cache(maxsize=30000)
 def edits(src,rho):
  d=defaultdict(float);L=len(src);d[src]+=rho
  for j in range(L):d[src[:j]+src[j+1:]]+=(1-rho)/(3*L)
  for j in range(L+1):
   for c in classes:d[src[:j]+(c,)+src[j:]]+=(1-rho)/(3*(L+1)*len(classes))
  for j in range(L):
   for c in classes:
    if c!=src[j]:d[src[:j]+(c,)+src[j+1:]]+=(1-rho)/(3*L*(len(classes)-1))
  d.pop((),None);z=math.fsum(d.values());assert abs(z-(1-(1-rho)/3 if L==1 else 1))<1e-12
  return {w:q/z for w,q in d.items()}
 def q(src,target,rho):return float(src==target) if rho==1 else edits(src,rho).get(target,0.)
 lines=[];lineids={};lid=[];vslots=[];hp=[];hav=[];vav=[]
 for i,r in enumerate(rows):
  w=tuple(c if c in A else '<UNK>' for c in r['word']);escape=M**(-r['unknown_units']) if M else 1.;H=r['H'][-hv['k']:];V=r['V'][str(hv['r'])]
  hav.append(bool(H));vav.append(bool(V));hp.append(escape*math.fsum(q(tuple(s['word']),w,hv['rho']) for s in H)/len(H) if H else 0.)
  if V:
   key=(r['folio'],r['line']-1)
   if key not in lineids:
    lineids[key]=len(lines);ws=[lookup.get((*key,j)) for j in range(rowwidth[key])];lines.append([x if x and set(x)<=A else None for x in ws])
   lid.append(lineids[key]);vslots.append([s['coord'][2] for s in V])
  else:lid.append(0);vslots.append([])
 L=len(lines);W=max(map(len,lines));matrix=np.zeros((N,W));baseperm=np.tile(np.arange(W),(L,1));valid=np.zeros((L,W),bool);ids=np.full((L,W),-1,int);identities={}
 for j,ws in enumerate(lines):
  for k,w in enumerate(ws):
   if w:
    valid[j,k]=True
    if w not in identities:identities[w]=len(identities)
    ids[j,k]=identities[w]
 for i,r in enumerate(rows):
  if vav[i]:
   target=tuple(c if c in A else '<UNK>' for c in r['word']);escape=M**(-r['unknown_units']) if M else 1.
   for j,w in enumerate(lines[lid[i]]):
    if w:matrix[i,j]=escape*q(w,target,hv['rho'])
 ix=np.arange(N)[:,None];lid=np.asarray(lid);slots=np.zeros((N,hv['r']),int);mask=np.zeros_like(slots,bool)
 for i,vs in enumerate(vslots):slots[i,:len(vs)]=vs;mask[i,:len(vs)]=True
 count=np.maximum(mask.sum(axis=1),1);hav=np.asarray(hav);vav=np.asarray(vav);hp=np.asarray(hp);channels=hav.astype(int)+vav.astype(int)
 perpage=Counter(r['folio'] for r in rows);perleaf=defaultdict(set)
 for r in rows:perleaf[r['leaf']].add(r['folio'])
 weights=np.asarray([1/(len(perleaf)*len(perleaf[r['leaf']])*perpage[r['folio']]) for r in rows]);origids=np.where(mask,ids[lid[:,None],slots],-1)
 def score(perm,scalar=False):
  cols=perm[lid[:,None],slots];vp=(matrix[ix,cols]*mask).sum(axis=1)/count;cp=(hp+vp)/np.maximum(channels,1);cp[channels==0]=bp[channels==0]
  gain=np.log2((1-hv['weight'])*bp+hv['weight']*cp)-hscore
  return math.fsum(float(a)*float(b) for a,b in zip(weights,gain)) if scalar else float(np.sum(weights*gain))
 obs=score(baseperm,True);assert abs(obs-result['results']['exact']['observed_V_gain'])<1e-12
 findings=[]
 for label in ('exact','coarse'):
  saved=result['results'][label];p=P/saved['null_array'];assert sha(p)==saved['null_sha256'];null=np.load(p);rng=np.random.default_rng(saved['seed']);groups=[]
  for li,ws in enumerate(lines):
   bucket=defaultdict(list)
   for j,w in enumerate(ws):
    if w:bucket[min((len(w)-1)//3,3) if label=='coarse' else len(w)].append(j)
   groups.extend((li,np.asarray(v)) for v in bucket.values() if len(v)>1)
  worst=movement=0.
  for b in range(saved['replicates']):
   perm=baseperm.copy()
   for li,g in groups:perm[li,g]=rng.permutation(g)
   val=score(perm,b<20);worst=max(worst,abs(val-null['gain'][b]))
   ii=np.where(mask,ids[lid[:,None],perm[lid[:,None],slots]],-1)
   checks={'source_identity_moved_fraction':float(((ids[np.arange(L)[:,None],perm]!=ids)&valid).sum()/valid.sum()),'target_assignment_changed_fraction':float(np.any(ii!=origids,axis=1).mean()),'target_multiset_changed_fraction':float(np.any(np.sort(ii,axis=1)!=np.sort(origids,axis=1),axis=1).mean())}
   movement=max(movement,max(abs(v-null[k][b]) for k,v in checks.items()))
  assert worst<1e-12 and movement<1e-15,(name,label,worst,movement)
  assert abs(saved['alignment_specificity_D']-(obs-float(null['gain'].mean())))<1e-12
  findings.append(dict(strata=label,all_permutations=saved['replicates'],max_gain_difference=worst,max_movement_difference=movement,original_gain=obs,independent_edit_enumeration=True))
 return dict(name=name,findings=findings,source_rows=L,valid_slots=int(valid.sum()))

if __name__=='__main__':
 out=dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),runs=[replay(n) for n in ('ZL_EVA','ZL_merged','IT_EVA')],all_passed=True,
  method='Saved baseline/H probabilities independently verified by prior copy replay; current replay reconstructs source rows from saved targets, independently enumerates normalized edit paths and all 11994 source-line permutations. No manuscript corpus opened.',confirm_reloaded=False,reserve_requested=False)
 (P/'replay_verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False))
