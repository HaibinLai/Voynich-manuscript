"""Freeze development choices, calibrate, then score manuscript confirm once."""
from pathlib import Path
from collections import defaultdict,Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
import argparse,copy,datetime,hashlib,itertools,json,math,os,sys,time
import numpy as np
HERE=Path(__file__).resolve().parent
RESEARCH=HERE.parent
sys.path.insert(0,str(RESEARCH))
import corpus
from copy_models import Baseline,CONTEXTS,RHOS,UNK,copy_arrays,kernel,make_records,path_masses,score_selected,tune_copy,verify_kernel
from reference_models import BodyLM,universe

PRIMARY=[('base','edit_HV'),('exact_HV_matched','edit_HV'),('edit_H_matched','edit_HV')]
SECONDARY=[('edit_H_independent','edit_HV'),('exact_HV_independent','edit_HV'),('base','edit_H_matched'),('base','edit_V_matched')]

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(path,data):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def seed_for(*parts):return int.from_bytes(hashlib.sha256('|'.join(map(str,parts)).encode()).digest()[:8],'little')
def receipt_check():
 r=json.loads((HERE/'protocol_receipt.json').read_text())
 for f in r['files']:assert sha(HERE/f['path'])==f['sha256'],f['path']
 assert sha(RESEARCH/'corpus.py')==sha(HERE/'reference_corpus.py')
 return sha(HERE/'protocol_receipt.json')
def freeze_execution():
 files=['run.py','copy_models.py','prepare_timm.py','reference_models.py','protocol.txt','protocol_receipt.json']
 data=dict(frozen_utc=now(),files=[dict(path=p,sha256=sha(HERE/p)) for p in files],numpy_version=np.__version__,python_version=sys.version)
 p=HERE/'execution_receipt.json'
 if p.exists():
  old=json.loads(p.read_text());assert old['files']==data['files'],'Code changed after execution freeze'
 else:dump(p,data)
 return sha(p)

def allowed_load(source,representation,splits):
 assert set(splits)<=set(['train','legacy','dev','confirm']) and 'reserve' not in splits
 # The shared parser reads the common transcription file; only requested split pages
 # are returned to model code. Reserve is never returned, fitted or scored.
 pages=corpus.load(source,splits=splits)
 assert all(p['split'] in splits and p['split']!='reserve' for p in pages)
 return pages

def input_fingerprint(pages):
 payload=[dict(folio=p['folio'],leaf=p['leaf'],metadata=p['metadata'],lines=p['lines']) for p in pages]
 return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def fit(trainp,devp,representation,name,task):
 started=time.monotonic()
 alphabet={c for p in trainp for line in p['lines'] for t in line['tokens'] if t for c in corpus.units(t,representation)}
 assert alphabet<=universe(representation)
 train=make_records(trainp,corpus.units,representation,alphabet);dev=make_records(devp,corpus.units,representation,alphabet)
 base=Baseline(train,alphabet,representation);base_dev=base.tune(dev)
 arrays,available,hits=copy_arrays(dev,base,base_dev)
 selected,grid=tune_copy(base_dev,arrays)
 config=dict(name=name,task=task,representation=representation,frozen_utc=now(),alphabet=sorted(alphabet),
  universe_size=len(universe(representation)),escape_size=base.escape_size,train_tokens=len(train),dev_tokens=len(dev),
  baseline_order=4,baseline_alpha=100,baseline_weights=list(base.weights),baseline_tuning=base.tuning,
  selected=selected,copy_tuning=grid,train_input_sha256=input_fingerprint(trainp),dev_input_sha256=input_fingerprint(devp),
  protocol_receipt_sha256=sha(HERE/'protocol_receipt.json'),execution_receipt_sha256=sha(HERE/'execution_receipt.json'),
  fit_seconds=time.monotonic()-started)
 cp=HERE/'configs'/f'{name}.json'
 if cp.exists():
  old=json.loads(cp.read_text())
  for k in ('selected','copy_tuning','baseline_weights','baseline_tuning','alphabet','train_input_sha256','dev_input_sha256','execution_receipt_sha256'):
   assert old[k]==config[k],('changed frozen config',name,k)
 else:dump(cp,config)
 path_masses.cache_clear()
 return dict(base=base,selected=selected,alphabet=alphabet,config_path=cp,task=task,name=name,representation=representation)

def summarize_scores(rows,scores,seed):
 page_indices=defaultdict(list);leafmap={}
 for i,row in enumerate(rows):page_indices[row['folio']].append(i);leafmap[row['folio']]=row['leaf']
 results={};per_pages={}
 for name,lp in scores.items():
  pp={f:float(-lp[idx].mean()) for f,idx in page_indices.items()};per_pages[name]=pp
  results[name]=dict(bits_per_word=float(-lp.mean()),per_page_bits=pp,tokens=len(rows),pages=len(pp),
   bits_per_unit_plus_eos=float(-lp.sum()/sum(len(r['word'])+1 for r in rows)))
 contrasts={};rng=np.random.default_rng(seed)
 leaves=sorted(set(leafmap.values()));boots=rng.integers(0,len(leaves),size=(1999,len(leaves)))
 for a,c in PRIMARY+SECONDARY:
  leafvalues=defaultdict(list)
  for f in page_indices:leafvalues[leafmap[f]].append(per_pages[a][f]-per_pages[c][f])
  vals=np.asarray([np.mean(leafvalues[l]) for l in leaves]);boot=vals[boots].mean(axis=1)
  contrasts[a+'__minus__'+c]=dict(mean_leaf_bits_saved=float(vals.mean()),pooled_bits_saved=float((scores[c]-scores[a]).mean()),
   bootstrap95=np.quantile(boot,[.025,.975]).tolist(),bootstrap_98_333=np.quantile(boot,[1/120,119/120]).tolist() if (a,c) in PRIMARY else None,
   primary=(a,c) in PRIMARY,leaves=len(leaves),replicates=1999,per_leaf={l:float(v) for l,v in zip(leaves,vals)})
 return results,contrasts

def evaluate(state,testp):
 started=time.monotonic();name=state['name'];base=state['base']
 assert state['config_path'].exists()
 test_started=now();rows=make_records(testp,corpus.units,state['representation'],state['alphabet'])
 base_scores=base.scores(rows);arrays,available,hits=copy_arrays(rows,base,base_scores)
 scores=score_selected(base_scores,arrays,state['selected'])
 results,contrasts=summarize_scores(rows,scores,seed_for('leaf-bootstrap-copy-v1',name))
 source_info={}
 for name_model,cfg in state['selected'].items():
  key=(cfg['family'],cfg['k'],cfg['r']);av=available[key];hit=hits[key+(cfg['rho'],)]
  source_info[name_model]=dict(available_targets=int(av.sum()),available_fraction=float(av.mean()),
      positive_kernel_targets=int((av&hit).sum()),positive_kernel_fraction_of_available=float((av&hit).sum()/av.sum()) if av.any() else None)
 target_path=HERE/'targets'/f'{name}.json';rows_public=[]
 for r in rows:
  escape=r['unknown']*math.log2(base.escape_size) if base.escape_size else 0.
  rows_public.append(dict(folio=r['folio'],leaf=r['leaf'],line=r['line'],slot=r['slot'],word=list(r['word']),position=r['position'],hand=r['hand'],
   unknown_units=r['unknown'],escape_bits=escape,H=[dict(word=list(s['word']),coord=list(s['coord'])) for s in r['H']],
   V={str(k):[dict(word=list(s['word']),coord=list(s['coord'])) for s in v] for k,v in r['V'].items()},line_slots=r['line_slots']))
 dump(target_path,rows_public)
 scorepath=HERE/'scores'/f'{name}.npz';scorepath.parent.mkdir(exist_ok=True);np.savez_compressed(scorepath,**scores)
 cfg=json.loads(state['config_path'].read_text())
 out=dict(name=name,task=state['task'],representation=state['representation'],selected=state['selected'],baseline_weights=list(base.weights),
   test_scoring_started_utc=test_started,config_frozen_utc=cfg['frozen_utc'],completed_utc=now(),
   train_tokens=cfg['train_tokens'],dev_tokens=cfg['dev_tokens'],test_tokens=len(rows),unknown_units=sum(r['unknown'] for r in rows),
   escape_bits_total=sum(r['escape_bits'] for r in rows_public),escape_size=base.escape_size,
   source_availability=source_info,results=results,contrasts=contrasts,test_input_sha256=input_fingerprint(testp),
   config_path=str(state['config_path'].relative_to(HERE)),config_sha256=sha(state['config_path']),scores_path=str(scorepath.relative_to(HERE)),scores_sha256=sha(scorepath),
   targets_path=str(target_path.relative_to(HERE)),targets_sha256=sha(target_path),score_seconds=time.monotonic()-started,
   interpretation='Complete nonempty explicit-unit word probabilities, including EOS and finite-universe escape. Known layout/hand conditions; legal observed past words only. Finite copy approximation, not author-generator likelihood or decipherment.')
 assert out['config_frozen_utc']<out['test_scoring_started_utc']
 dump(HERE/'runs'/f'{name}.json',out)
 path_masses.cache_clear()
 return dict(name=name,tokens=len(rows),base_bits=results['base']['bits_per_word'],gain=contrasts['base__minus__edit_HV']['mean_leaf_bits_saved'],vertical=contrasts['edit_H_matched__minus__edit_HV']['mean_leaf_bits_saved'],seconds=out['score_seconds'])

def calibration_pages(seed,order):
 data=json.loads((HERE/'calibration_inputs'/f'timm_{seed}.json').read_text())
 pages=data['pages'];splits={s:[p for p in pages if p['split']==s] for s in ('train','dev','test')}
 if order=='shuffled':
  for split,pp in splits.items():
   slots=[(line,j) for p in pp for line in p['lines'] for j in range(len(line['tokens']))]
   words=[line['tokens'][j] for line,j in slots]
   rng=np.random.default_rng(seed_for('native-whole-word-shuffle-copy-v1',seed,split));perm=rng.permutation(len(words))
   for (line,j),i in zip(slots,perm):line['tokens'][j]=words[int(i)]
 else:assert order=='original'
 return splits

def calibrate_one(task):
 name=f"timm_{task['seed']}_{task['order']}_{task['representation']}"
 result_path=HERE/'runs'/f'{name}.json'
 if result_path.exists():
  old=json.loads(result_path.read_text());cfg=json.loads((HERE/old['config_path']).read_text())
  assert cfg['execution_receipt_sha256']==sha(HERE/'execution_receipt.json')
  return dict(name=name,cached=True)
 pages=calibration_pages(task['seed'],task['order'])
 state=fit(pages['train'],pages['dev'],task['representation'],name,task)
 return evaluate(state,pages['test'])

def verify():
 checks=verify_kernel()
 lm=BodyLM([tuple('ab'),tuple('aab'),tuple('b')],set('ab'),set('abx'),4,100)
 total=remaining=0.
 for L in range(1,7):
  for word in itertools.product('abx',repeat=L):
   total+=2**lm.logp_full(word)
   if L==6:
    h=lm.initial_history;prefix=1/lm.nonempty_mass
    for c in word:prefix*=lm.actual_prob(h,c);h=lm.advance(h,lm.mapped(c))
    remaining+=prefix*(1-lm.prob(h,'<EOS>'))
 assert abs(total+remaining-1)<1e-12
 checks['nonempty_char_plus_remaining_mass']=total+remaining
 line=lambda tokens,start=False,end=False,paragraph=0:dict(tokens=tokens,paragraph_start=start,paragraph_end=end,paragraph_known=True,paragraph=paragraph,block=0)
 p=dict(folio='toy',leaf='toy',metadata={'H':'toy'},lines=[line(['aa','ab','ba'],True),line(['bb',None,'aa','ab']),line(['aa','ab','ba'],True,paragraph=1)])
 units=lambda t,r:tuple(t)
 rows=make_records([p],units,'eva',set('ab'));target=next(r for r in rows if r['line']==1 and r['slot']==2)
 assert target['H']==[] and target['V'][3]
 assert all(not r['V'][3] for r in rows if r['line']==2)
 future=copy.deepcopy(p);future['lines'][1]['tokens'][3]='bbbb'
 target2=next(r for r in make_records([future],units,'eva',set('ab')) if r['line']==1 and r['slot']==2)
 assert target['H']==target2['H'] and target['V']==target2['V']
 alternate=copy.deepcopy(p);alternate['lines'][1]['tokens'][2]='bbbbbb'
 target3=next(r for r in make_records([alternate],units,'eva',set('ab')) if r['line']==1 and r['slot']==2)
 assert target['H']==target3['H'] and target['V']==target3['V']
 unknown=copy.deepcopy(p);unknown['lines'][1]['tokens']=['aa','x','ab']
 rr=make_records([unknown],units,'eva',set('ab'));assert next(r for r in rr if r['line']==1 and r['slot']==2)['H']==[]
 checks.update(future_content_cannot_change_context=True,target_content_cannot_change_context=True,missing_and_unknown_reset=True,new_paragraph_blocks_vertical=True,all_source_coordinates_past=True)
 dump(HERE/'verification.json',checks)
 return checks

def toy_pages(copying,seed):
 rng=np.random.default_rng(seed);pages=[];alphabet=tuple('abcde')
 for pi in range(40):
  lines=[];previous=None
  for li in range(10):
   words=[]
   for slot in range(12):
    if copying and previous and rng.random()<.8:
     source=tuple(previous[slot]);rho=.5
     outcomes={}
     for L in (len(source)-1,len(source),len(source)+1):
      # Generate candidate edit outputs directly, no large alphabet enumeration.
      pass
     candidates={source}
     for j in range(len(source)):candidates.add(source[:j]+source[j+1:])
     for j in range(len(source)+1):
      for c in alphabet:candidates.add(source[:j]+(c,)+source[j:])
     for j in range(len(source)):
      for c in alphabet:candidates.add(source[:j]+(c,)+source[j+1:])
     candidates=sorted(w for w in candidates if w)
     weights=np.asarray([kernel(source,w,len(alphabet),rho) for w in candidates]);assert abs(weights.sum()-1)<1e-12
     word=''.join(candidates[int(rng.choice(len(candidates),p=weights))])
    else:word=''.join(rng.choice(alphabet,size=5))
    words.append(word)
   lines.append(dict(tokens=words,paragraph_start=li==0,paragraph_end=li==9,paragraph_known=True,paragraph=0,block=0));previous=words
  f=f'toy_{pi}'
  pages.append(dict(folio=f,leaf=f,metadata={'H':'toy','I':'toy'},lines=lines,split='train' if pi<20 else 'dev' if pi<30 else 'test'))
 return {s:[p for p in pages if p['split']==s] for s in ('train','dev','test')}

def toy_check():
 output=[]
 for copying,seed in ((True,2026111731),(False,2026111732)):
  pp=toy_pages(copying,seed);name='toy_copy' if copying else 'toy_independent'
  state=fit(pp['train'],pp['dev'],'eva',name,dict(kind='synthetic_verification',copying=copying,seed=seed))
  r=evaluate(state,pp['test']);output.append(r)
  assert r['gain']>.5 if copying else r['gain']<.25,r
 dump(HERE/'toy_verification.json',output)
 return output

def main():
 parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['verify','calibrate','manuscript']);parser.add_argument('--workers',type=int,default=2);parser.add_argument('--smoke',action='store_true');args=parser.parse_args()
 receipt_check();freeze_execution();print(json.dumps(verify()),flush=True)
 if args.mode=='verify':
  print(json.dumps(toy_check()),flush=True);return
 if args.mode=='calibrate':
  assert json.loads((HERE/'layout_verification.json').read_text())['all_seeds_identical']
  assert (HERE/'toy_verification.json').exists()
  tasks=[dict(kind='generator_calibration',seed=seed,order=order,representation=rep) for seed in range(19,39) for order in ('original','shuffled') for rep in ('eva','merged')]
  if args.smoke:print(json.dumps(calibrate_one(tasks[0])),flush=True);return
  with ProcessPoolExecutor(max_workers=args.workers) as pool:
   futures=[pool.submit(calibrate_one,t) for t in tasks]
   for index,future in enumerate(as_completed(futures),1):
    out=future.result();out.update(completed=index,total=len(tasks));print(json.dumps(out),flush=True)
  dump(HERE/'calibration_complete.json',dict(completed_utc=now(),tasks=80,execution_receipt_sha256=sha(HERE/'execution_receipt.json')))
 else:
  assert (HERE/'calibration_complete.json').exists(),'Calibrate before manuscript confirm'
  names=[('ZL3b-n.txt','eva','ZL_EVA'),('ZL3b-n.txt','merged','ZL_merged'),('IT2a-n.txt','eva','IT_EVA')]
  marker=HERE/'confirm_scoring_started.json'
  assert not marker.exists(),'Do not silently rescore confirm; explicit audit/amendment required'
  states=[]
  for source,rep,name in names:
   train=allowed_load(source,rep,['train','legacy']);dev=allowed_load(source,rep,['dev'])
   state=fit(train,dev,rep,name,dict(kind='manuscript',source=source,representation=rep))
   states.append((source,rep,state))
  dump(HERE/'all_manuscript_configs_frozen.json',dict(frozen_utc=now(),configs=[dict(path=str(s['config_path'].relative_to(HERE)),sha256=sha(s['config_path'])) for _,_,s in states]))
  dump(marker,dict(started_utc=now(),all_configs_sha256=sha(HERE/'all_manuscript_configs_frozen.json'),reserve_requested=False))
  for source,rep,state in states:
   test=allowed_load(source,rep,['confirm']);print(json.dumps(evaluate(state,test)),flush=True)
  dump(HERE/'manuscript_complete.json',dict(completed_utc=now(),representations=3,reserve_used=False))
 receipt_check()

if __name__=='__main__':main()
