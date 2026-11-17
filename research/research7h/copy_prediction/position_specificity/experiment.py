"""Shared source-line channel permutations, with frozen full-word predictors."""
from pathlib import Path
from collections import defaultdict,Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
import argparse,datetime,hashlib,json,math,sys,time
import numpy as np
P=Path(__file__).resolve().parent;COPY=P.parent;RESEARCH=COPY.parent
sys.path.insert(0,str(COPY));sys.path.insert(0,str(RESEARCH))
import corpus
from copy_models import Baseline,make_records,kernel,path_masses
from reference_models import universe,UNK

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def seed_for(*parts):return int.from_bytes(hashlib.sha256('|'.join(map(str,parts)).encode()).digest()[:8],'little')
def verify_receipt():
 d=json.loads((P/'protocol_receipt.json').read_text())
 for f in d['files']:assert sha(P/f['path'])==f['sha256'],f['path']
def execution_freeze():
 names=['experiment.py','prepare.py','protocol.txt','protocol_receipt.json','observational_audit_addendum.txt']
 d=dict(frozen_utc=now(),files=[dict(path=n,sha256=sha(P/n)) for n in names],numpy=np.__version__)
 f=P/'execution_receipt.json'
 if f.exists():assert json.loads(f.read_text())['files']==d['files'],'Code changed after execution freeze'
 else:dump(f,d)

def fit_fixed(trainp,rep,prior,name):
 A={c for p in trainp for line in p['lines'] for token in line['tokens'] if token for c in corpus.units(token,rep)}
 rows=make_records(trainp,corpus.units,rep,A);base=Baseline(rows,A,rep);base.weights=tuple(prior['baseline_weights'])
 choice={k:prior['selected'][k] for k in ('edit_HV','edit_H_matched')}
 f=P/'configs'/f'{name}.json'
 cfg=dict(frozen_utc=now(),representation=rep,train_tokens=len(rows),alphabet=sorted(A),escape_size=base.escape_size,
  baseline_weights=list(base.weights),selected=choice,source_prior_config=prior['name'],no_dev_search=True,
  execution_receipt_sha256=sha(P/'execution_receipt.json'))
 if f.exists():
  old=json.loads(f.read_text())
  for k in ('alphabet','baseline_weights','selected','execution_receipt_sha256'):assert old[k]==cfg[k]
 else:dump(f,cfg)
 return base,choice,f

class Perturbation:
 def __init__(self,pages,base,choice,rep):
  self.base,self.choice=base,choice;self.rows=make_records(pages,corpus.units,rep,base.alphabet);rows=self.rows;N=len(rows)
  self.bp=2**base.scores(rows);self.N=N;self.rep=rep
  self.escape=np.asarray([base.escape_size**(-r['unknown']) if base.escape_size else 1. for r in rows]);self.size=len(base.alphabet)+(base.escape_size>0)
  self.page_map={p['folio']:p for p in pages};self.lines=[];line_lookup={};line_ids=np.zeros(N,dtype=int)
  hv=choice['edit_HV'];self.hv=hv;hm=choice['edit_H_matched'];self.hm=hm
  self.hav=np.zeros(N,dtype=bool);self.vav=np.zeros(N,dtype=bool);self.hp=np.zeros(N);hmp=np.zeros(N)
  candidates=[]
  for i,row in enumerate(rows):
   H=row['H'][-hv['k']:];V=row['V'][hv['r']];self.hav[i]=bool(H);self.vav[i]=bool(V)
   if H:
    self.hp[i]=self.escape[i]*sum(kernel(tuple(s['word']),row['mapped'],self.size,hv['rho']) for s in H)/len(H)
   HH=row['H'][-hm['k']:]
   if HH:hmp[i]=self.escape[i]*sum(kernel(tuple(s['word']),row['mapped'],self.size,hm['rho']) for s in HH)/len(HH)
   else:hmp[i]=self.bp[i]
   if V:
    key=(row['folio'],row['line']-1)
    if key not in line_lookup:
     line_lookup[key]=len(self.lines);line=self.page_map[key[0]]['lines'][key[1]];words=[]
     for token in line['tokens']:
      w=tuple(corpus.units(token,rep)) if token else None
      words.append(w if w is not None and set(w)<=base.alphabet else None)
     self.lines.append(dict(key=key,words=words))
    line_ids[i]=line_lookup[key];candidates.append([s['coord'][2] for s in V])
   else:candidates.append([])
  self.hscore=np.log2((1-hm['weight'])*self.bp+hm['weight']*hmp)
  self.line_ids=line_ids;self.L=len(self.lines);self.width=max((len(l['words']) for l in self.lines),default=1)
  self.base_perm=np.tile(np.arange(self.width),(max(self.L,1),1));self.valid=np.zeros((max(self.L,1),self.width),dtype=bool)
  self.identities=np.full_like(self.base_perm,-1);self.lengths=np.zeros_like(self.base_perm);word_ids={}
  for li,line in enumerate(self.lines):
   for j,w in enumerate(line['words']):
    if w is not None:
     self.valid[li,j]=True;self.lengths[li,j]=len(w)
     if w not in word_ids:word_ids[w]=len(word_ids)
     self.identities[li,j]=word_ids[w]
  self.candidates=np.zeros((N,hv['r']),dtype=int);self.mask=np.zeros_like(self.candidates,dtype=bool)
  for i,cc in enumerate(candidates):
   self.candidates[i,:len(cc)]=cc;self.mask[i,:len(cc)]=True
  self.vcounts=np.maximum(self.mask.sum(axis=1),1)
  self.matrix=np.zeros((N,self.width))
  for i,row in enumerate(rows):
   if self.vav[i]:
    for j,word in enumerate(self.lines[self.line_ids[i]]['words']):
     if word is not None:self.matrix[i,j]=self.escape[i]*kernel(word,row['mapped'],self.size,hv['rho'])
  self.target_indices=np.arange(N)[:,None];self.line_indices=np.arange(max(self.L,1))[:,None]
  perpage=Counter(r['folio'] for r in rows);perleaf=defaultdict(set)
  for r in rows:perleaf[r['leaf']].add(r['folio'])
  self.weights=np.asarray([1/(len(perleaf)*len(perleaf[r['leaf']])*perpage[r['folio']]) for r in rows]);assert abs(self.weights.sum()-1)<1e-12
  self.leaves=len(perleaf);self.pages=len(perpage)
  original_local=self.base_perm[self.line_ids[:,None],self.candidates]
  self.original_ids=np.where(self.mask,self.identities[self.line_ids[:,None],original_local],-1)
  self.original_sorted=np.sort(self.original_ids,axis=1)
  self.observed,self.observed_vector=self.score(self.base_perm)
  self.fixed_h_sha=hashlib.sha256(self.hscore.tobytes()).hexdigest()
 def score(self,perm):
  cols=perm[self.line_ids[:,None],self.candidates]
  vp=(self.matrix[self.target_indices,cols]*self.mask).sum(axis=1)/self.vcounts
  count=self.hav.astype(int)+self.vav.astype(int)
  C=(self.hp+vp)/np.maximum(count,1);C[count==0]=self.bp[count==0]
  hvscore=np.log2((1-self.hv['weight'])*self.bp+self.hv['weight']*C)
  gains=hvscore-self.hscore
  return float(np.sum(self.weights*gains)),gains
 def scalar(self,perm):
  values=[]
  for i,row in enumerate(self.rows):
   channels=[]
   if self.hav[i]:channels.append(self.hp[i])
   if self.vav[i]:
    li=self.line_ids[i];qq=[]
    for j in self.candidates[i,self.mask[i]]:
     w=self.lines[li]['words'][int(perm[li,j])];assert w is not None
     qq.append(self.escape[i]*kernel(w,row['mapped'],self.size,self.hv['rho']))
    channels.append(math.fsum(qq)/len(qq))
   C=math.fsum(channels)/len(channels) if channels else self.bp[i]
   value=math.log2((1-self.hv['weight'])*self.bp[i]+self.hv['weight']*C)-self.hscore[i]
   values.append(value)
  return math.fsum(float(w)*x for w,x in zip(self.weights,values))
 def strata(self,coarse):
  groups=[]
  for li,line in enumerate(self.lines):
   buckets=defaultdict(list)
   for j,word in enumerate(line['words']):
    if word is not None:
     length=len(word);key=min((length-1)//3,3) if coarse else length;buckets[key].append(j)
   groups.extend((li,np.asarray(v,dtype=int)) for v in buckets.values())
  return groups
 def run(self,coarse,reps,seed,name,deep_check=False):
  rng=np.random.default_rng(seed);groups=self.strata(coarse);valid_count=int(self.valid.sum());singleton=sum(len(v) for li,v in groups if len(v)==1)
  values=np.zeros(reps);moved=np.zeros(reps);assignment=np.zeros(reps);multiset=np.zeros(reps);worst=0.
  mutable=[(li,ii) for li,ii in groups if len(ii)>1]
  for bi in range(reps):
   perm=self.base_perm.copy()
   for li,indices in mutable:perm[li,indices]=rng.permutation(indices)
   if bi==0:
    assert np.array_equal(perm[~self.valid],self.base_perm[~self.valid])
    assert np.array_equal(self.valid[self.line_indices,perm],self.valid)
    if not coarse:assert np.array_equal(self.lengths[self.line_indices,perm],self.lengths)
   values[bi],_=self.score(perm)
   if bi==0 or (deep_check and bi<20):
    error=abs(values[bi]-self.scalar(perm));worst=max(worst,error);assert error<1e-12
   changed=(self.identities[self.line_indices,perm]!=self.identities)&self.valid
   moved[bi]=changed.sum()/valid_count if valid_count else 0.
   cols=perm[self.line_ids[:,None],self.candidates]
   ids=np.where(self.mask,self.identities[self.line_ids[:,None],cols],-1)
   assignment[bi]=np.any(ids!=self.original_ids,axis=1).sum()/self.N
   multiset[bi]=np.any(np.sort(ids,axis=1)!=self.original_sorted,axis=1).sum()/self.N
  assert hashlib.sha256(self.hscore.tobytes()).hexdigest()==self.fixed_h_sha
  array_path=P/'nulls'/f'{name}.npz';array_path.parent.mkdir(exist_ok=True)
  np.savez_compressed(array_path,gain=values,source_identity_moved_fraction=moved,target_assignment_changed_fraction=assignment,target_multiset_changed_fraction=multiset)
  return dict(stratum='coarse_1_3_4_6_7_9_10plus' if coarse else 'exact_unit_length',replicates=reps,seed=seed,
   observed_V_gain=self.observed,null_mean=float(values.mean()),null95=np.quantile(values,[.025,.975]).tolist(),
   alignment_specificity_D=float(self.observed-values.mean()),monte_carlo_reference_p=(1+int(np.sum(values>=self.observed-1e-14)))/(reps+1),
   source_rows=self.L,source_valid_slots=valid_count,source_actual_slots=sum(len(line['words']) for line in self.lines),
   source_fixed_invalid_slots=sum(len(line['words']) for line in self.lines)-valid_count,
   internal_array_padding_slots=self.valid.size-sum(len(line['words']) for line in self.lines),
   source_strata=len(groups),singleton_strata=sum(len(g)==1 for li,g in groups),singleton_slot_fraction=singleton/valid_count if valid_count else 0.,
   movable_slot_fraction=(valid_count-singleton)/valid_count if valid_count else 0.,source_identity_moved_mean=float(moved.mean()),
   V_available_targets=int(self.vav.sum()),V_available_fraction=float(self.vav.mean()),
   target_assignment_changed_mean_all_targets=float(assignment.mean()),target_multiset_changed_mean_all_targets=float(multiset.mean()),
   target_multiset_changed_mean_given_V=float(multiset.mean()/self.vav.mean()) if self.vav.any() else 0.,
   H_channel_bitwise_unchanged=True,shared_single_source_line_permutation=True,scalar_max_log2_error=worst,
   null_array=str(array_path.relative_to(P)),null_sha256=sha(array_path))

def run_condition(task):
 config,seed,rep=task['config'],task['seed'],task['representation'];name=f'p{config}_s{seed}_{rep}'
 existing=P/'runs'/f'{name}.json'
 if existing.exists():
  old=json.loads(existing.read_text());assert old['execution_receipt_sha256']==sha(P/'execution_receipt.json');return dict(name=name,cached=True)
 started=time.monotonic();data=json.loads((P/'inputs'/f'p{config}_s{seed}.json').read_text());pp=data['pages']
 train=[p for p in pp if p['split']=='train'];test=[p for p in pp if p['split']=='test']
 prior=json.loads((COPY/'configs'/f'timm_{seed}_original_{rep}.json').read_text())
 base,choice,config_path=fit_fixed(train,rep,prior,name)
 test_started=now();state=Perturbation(test,base,choice,rep)
 outputs={}
 for coarse in (False,True):
  label='coarse' if coarse else 'exact';outputs[label]=state.run(coarse,399,seed_for('position-specificity-v1',seed,rep,label),name+'_'+label,deep_check=(config==28 and seed==19 and rep=='eva'))
 words=[r['word'] for r in state.rows];lengths=[len(w) for w in words]
 out=dict(name=name,task=task,completed_utc=now(),test_scoring_started_utc=test_started,
  config_path=str(config_path.relative_to(P)),config_sha256=sha(config_path),execution_receipt_sha256=sha(P/'execution_receipt.json'),
  selected=choice,baseline_weights=list(base.weights),results=outputs,
  test_words=len(words),test_vocabulary=len(set(words)),test_mean_unit_length=float(np.mean(lengths)),test_length_histogram=dict(Counter(lengths)),
  test_unknown_units=sum(r['unknown'] for r in state.rows),test_source_events=data['event_statistics']['test'],
  actual_branch_probability_given_LOCALY=data['actual_branch_probability_given_LOCALY'],
  elapsed_seconds=time.monotonic()-started,
  interpretation='V-source channel perturbation only; H and targets fixed. Author parameter intervention changes later RNG trajectory; 0 is not off. No manuscript reserve or new dev tuning.')
 dump(existing,out);path_masses.cache_clear()
 return dict(name=name,D_exact=outputs['exact']['alignment_specificity_D'],D_coarse=outputs['coarse']['alignment_specificity_D'],moved=outputs['exact']['source_identity_moved_mean'],seconds=out['elapsed_seconds'])

def verify_toys():
 # Reuse prior fixed, known-position-copy and independent synthetic targets only
 # through deterministic regeneration; no manuscript pages are opened.
 import importlib.util
 spec=importlib.util.spec_from_file_location('frozen_copy_run',COPY/'run.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 result=[]
 for copying,seed in ((True,2026111731),(False,2026111732)):
  pp=module.toy_pages(copying,seed);name='toy_copy' if copying else 'toy_independent';prior=json.loads((COPY/'configs'/f'{name}.json').read_text())
  base,choice,cp=fit_fixed(pp['train'],'eva',prior,name);state=Perturbation(pp['test'],base,choice,'eva')
  out=state.run(False,399,seed_for('position-toy-v1',seed),name+'_exact',True)
  if copying:assert out['alignment_specificity_D']>.5
  else:assert out['alignment_specificity_D']<.25
  result.append(dict(name=name,**out))
 dump(P/'toy_verification.json',result);return result

def main():
 parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['verify','calibrate']);parser.add_argument('--workers',type=int,default=2);parser.add_argument('--smoke',action='store_true');args=parser.parse_args()
 verify_receipt();execution_freeze()
 if args.mode=='verify':print(json.dumps(verify_toys(),indent=2),flush=True);return
 assert json.loads((P/'generation_audit.json').read_text())['all_logging_outputs_identical']
 assert (P/'toy_verification.json').exists()
 tasks=[dict(config=c,seed=s,representation=r) for c in (0,28,100) for s in range(19,39) for r in ('eva','merged')]
 if args.smoke:print(json.dumps(run_condition(tasks[0])),flush=True);return
 with ProcessPoolExecutor(max_workers=args.workers) as pool:
  futures=[pool.submit(run_condition,t) for t in tasks]
  for i,future in enumerate(as_completed(futures),1):
   out=future.result();out.update(completed=i,total=len(tasks));print(json.dumps(out),flush=True)
 dump(P/'calibration_complete.json',dict(completed_utc=now(),conditions=120,confirm_scored=False,reserve_used=False))
 verify_receipt()

if __name__=='__main__':main()
