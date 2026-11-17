"""Freeze, calibrate, fit dev; confirm is a separate reviewed once-only action."""
from pathlib import Path
from collections import Counter,defaultdict
from concurrent.futures import ProcessPoolExecutor,as_completed
import argparse,datetime,gzip,hashlib,itertools,json,math,sys,time
import numpy as np
P=Path(__file__).resolve().parent;ROOT=P.parent;sys.path.insert(0,str(ROOT))
import corpus
from models import StyleLM,Restore,MERGES,mapping,quotient,transform,verify,universe

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def seed_for(*p):return int.from_bytes(hashlib.sha256('|'.join(map(str,p)).encode()).digest()[:8],'little')
def receipt_check():
 r=json.loads((P/'protocol_receipt.json').read_text())
 for f in r['files']:assert sha(P/f['path'])==f['sha256'],f['path']
 assert sha(ROOT/'corpus.py')==sha(P/'reference_corpus.py')
def freeze():
 r=dict(frozen_utc=now(),files=[dict(path=n,sha256=sha(P/n)) for n in ['models.py','run.py','protocol.txt','protocol_receipt.json','reference_models.py','reference_corpus.py']],python=sys.version,numpy=np.__version__)
 p=P/'execution_receipt.json'
 if p.exists():assert json.loads(p.read_text())['files']==r['files'],'Implementation changed after freeze'
 else:dump(p,r)
def records(pages,rep):
 rows=[]
 for p in pages:
  assert p['split']!='reserve'
  for li,line in enumerate(p['lines']):
   for j,t in enumerate(line['tokens']):
    if t:
     w=tuple(corpus.units(t,rep));assert set(w)<=universe(rep)
     rows.append(dict(folio=p['folio'],leaf=p['leaf'],line=li,slot=j,word=w,hand=p['metadata'].get('H','?'),position='paragraph_first' if j==0 and line['paragraph_start'] else 'line_first' if j==0 else 'other'))
 return rows

def synthetic(kind,seed):
 rng=np.random.default_rng(seed);lexicon=sorted(itertools.product('abcd',repeat=4));rng.shuffle(lexicon);lexicon=lexicon[:128];rows=[]
 for i in range(8000):
  page=i//200;hand='H'+str(page%2);position='paragraph_first' if i%10==0 else 'line_first' if i%5==0 else 'other';a,b,c,d=lexicon[int(rng.integers(128))]
  word=['f',a,b,'f','k',c,d,'k'];prob=.85 if ((hand=='H0') != (position=='paragraph_first')) else .15
  if kind!='position':prob=.5
  labels=rng.random(4)<prob
  if kind=='correlated':labels[1]=labels[0];labels[3]=labels[2]
  for j,lab in zip((0,3,4,7),labels):
   if lab:word[j]='p' if word[j]=='f' else 't'
  truth=-sum(math.log2(prob if lab else 1-prob) for lab in (labels if kind!='correlated' else labels[[0,2]]))
  rows.append(dict(folio=f'{kind}_{seed}_{page:02}',leaf=f'{kind}_{seed}_{page:02}',line=i%200//5,slot=i%5,word=tuple(word),hand=hand,position=position,known_joint_alias_bits=truth,alias_probability=prob))
 return dict(train=rows[:4000],dev=rows[4000:6000],test=rows[6000:])

def fit_dataset(name,rep,data,source):
 started=time.monotonic();train,dev=data['train'],data['dev'];inputpath=P/'inputs'/(name+'_train_dev.json')
 dump(inputpath,dict(train=train,dev=dev,source=source,representation=rep))
 raw=StyleLM(train,universe(rep));rawbest=raw.tune(dev)
 states={};configs={}
 for kind in MERGES:
  mp=mapping(kind,rep);lm=StyleLM(transform(train,mp),quotient(universe(rep),mp));lm.tune(transform(dev,mp));restore=Restore(train,mp);selected,glob=restore.tune(dev)
  cfg=dict(name=name,merge=kind,representation=rep,source=source,frozen_utc=now(),train_words=len(train),dev_words=len(dev),map=mp,
   original_omega=len(universe(rep)),quotient_omega=len(lm.omega),original_alphabet=sorted(raw.alphabet),quotient_alphabet=sorted(lm.alphabet),raw_escape_size=raw.escape_size,quotient_escape_size=lm.escape_size,
   raw_weights=list(raw.weights),quotient_weights=list(lm.weights),raw_dev_grid=raw.grid,quotient_dev_grid=lm.grid,restore_selected=selected,restore_global=glob,restore_dev_grid=restore.grid,
   input_path=str(inputpath.relative_to(P)),input_sha256=sha(inputpath),execution_receipt_sha256=sha(P/'execution_receipt.json'),protocol_receipt_sha256=sha(P/'protocol_receipt.json'))
  cp=P/'configs'/(name+'_'+kind+'.json');assert not cp.exists(),'No overwrite of frozen dev configuration';dump(cp,cfg);configs[kind]=cp;states[kind]=(lm,restore)
 print(json.dumps(dict(fitted=name,seconds=time.monotonic()-started,selected={k:states[k][1].selected for k in MERGES})),flush=True)
 return raw,states,configs

def reconstruct(name,rep,data):
 raw=StyleLM(data['train'],universe(rep));states={};configs={}
 for kind in MERGES:
  cp=P/'configs'/(name+'_'+kind+'.json');cfg=json.loads(cp.read_text());assert sha(P/cfg['input_path'])==cfg['input_sha256'];assert cfg['execution_receipt_sha256']==sha(P/'execution_receipt.json')
  raw.weights=tuple(cfg['raw_weights']);mp=mapping(kind,rep);lm=StyleLM(transform(data['train'],mp),quotient(universe(rep),mp));lm.weights=tuple(cfg['quotient_weights']);rr=Restore(data['train'],mp);rr.selected=cfg['restore_selected'];rr.global_selected=cfg['restore_global'];states[kind]=(lm,rr);configs[kind]=cp
 return raw,states,configs

def summarize(rows,base,cost,rep):
 pp=defaultdict(list);leaves={}
 for i,r in enumerate(rows):pp[r['folio']].append(i);leaves[r['folio']]=r['leaf']
 perleaf=defaultdict(list)
 for f,ii in pp.items():perleaf[leaves[f]].append(float(np.mean(base[ii]-cost[ii])))
 vals=np.asarray([np.mean(perleaf[l]) for l in sorted(perleaf)]);rng=np.random.default_rng(seed_for('allograph-factor-leaf-v1',rep));indices=rng.integers(len(vals),size=(1999,len(vals)));boot=vals[indices].mean(axis=1)
 return dict(mean_leaf_bits_saved=float(vals.mean()),pooled_bits_saved=float(np.mean(base-cost)),ci95=np.quantile(boot,[.025,.975]).tolist(),ci98_333=np.quantile(boot,[1/120,119/120]).tolist(),leaves=len(vals),pages=len(pp),per_leaf=dict(zip(sorted(perleaf),map(float,vals))))

def evaluate(name,rep,test,raw,states,configs):
 target=P/'targets'/(name+'.json');assert not target.exists();dump(target,test);base=-raw.scores(test);bn,be=raw.escape(test);outputs=[]
 for kind in MERGES:
  lm,restore=states[kind];yr=transform(test,restore.mp);q=-lm.scores(yr);rr=-restore.scores(test,**{k:restore.selected[k] for k in ('depth','alpha')});rg=-restore.scores(test,**{k:restore.global_selected[k] for k in ('depth','alpha')});yn,ye=lm.escape(yr);cost=q+rr
  for r in test:assert restore.decode(*restore.encode(r['word']))==tuple(r['word'])
  score=P/'scores'/(name+'_'+kind+'.npz');score.parent.mkdir(exist_ok=True);np.savez_compressed(score,base=base,quotient=q,restoration=rr,restoration_global=rg,complete=cost,complete_global=q+rg,base_escape=be,quotient_escape=ye,raw_unknown=bn,quotient_unknown=yn)
  cfg=json.loads(configs[kind].read_text());out=dict(name=name,merge=kind,representation=rep,completed_utc=now(),config_path=str(configs[kind].relative_to(P)),config_sha256=sha(configs[kind]),target_path=str(target.relative_to(P)),target_sha256=sha(target),score_path=str(score.relative_to(P)),score_sha256=sha(score),tokens=len(test),
   original_units=sum(len(r['word']) for r in test),restored_branches=sum(sum(1 for _ in restore.events(r)) for r in test),raw_bits_per_word=float(base.mean()),quotient_bits_per_word=float(q.mean()),restoration_bits_per_word=float(rr.mean()),complete_bits_per_word=float(cost.mean()),global_restoration_bits_per_word=float(rg.mean()),raw_escape_bits_total=float(be.sum()),quotient_escape_bits_total=float(ye.sum()),raw_unknown_units=int(bn.sum()),quotient_unknown_units=int(yn.sum()),
   selected_gain=summarize(test,base,cost,rep),global_restore_gain=summarize(test,base,q+rg,rep),restore_selected=restore.selected,restore_global=restore.global_selected,raw_weights=list(raw.weights),quotient_weights=list(lm.weights),roundtrip_all=True,reserve_used=False)
  if 'known_joint_alias_bits' in test[0]:
   out['known_joint_alias_bits_per_word']=float(np.mean([r['known_joint_alias_bits'] for r in test]))*(1 if kind=='both' else .5)
   out['restoration_excess_over_known_joint']=out['restoration_bits_per_word']-out['known_joint_alias_bits_per_word']
  else:out['confirm_exploratory']=True
  dump(P/'runs'/(name+'_'+kind+'.json'),out);outputs.append(out)
 return outputs

def toy_task(task):
 kind,seed=task;name=f'toy_{kind}_{seed}';data=synthetic(kind,seed);raw,states,configs=fit_dataset(name,'eva',data,dict(kind='synthetic',mechanism=kind,seed=seed));return [dict(name=o['name'],merge=o['merge'],gain=o['selected_gain']['mean_leaf_bits_saved'],restoration=o['restoration_bits_per_word'],truth=o['known_joint_alias_bits_per_word']) for o in evaluate(name,'eva',data['test'],raw,states,configs)]

def calibrate(workers):
 assert not (P/'calibration_complete.json').exists();tasks=list(itertools.product(['iid','position','correlated'],range(2026111741,2026111746)));results=[]
 with ProcessPoolExecutor(max_workers=workers) as pool:
  for r in pool.map(toy_task,tasks):results.extend(r);print(json.dumps(r),flush=True)
 dump(P/'calibration_complete.json',dict(completed_utc=now(),runs=results,all_runs=45,reserve_used=False))

def fit_manuscript():
 assert (P/'calibration_complete.json').exists();assert not (P/'all_dev_configs_frozen.json').exists();files=[]
 for name,source,rep in [('ZL_EVA','ZL3b-n.txt','eva'),('ZL_merged','ZL3b-n.txt','merged'),('IT_EVA','IT2a-n.txt','eva')]:
  data={s:records(corpus.load(source,splits=ss),rep) for s,ss in [('train',['train','legacy']),('dev',['dev'])]}
  raw,states,configs=fit_dataset(name,rep,data,dict(kind='manuscript',source=source));files.extend(dict(path=str(p.relative_to(P)),sha256=sha(p)) for p in configs.values())
 dump(P/'all_dev_configs_frozen.json',dict(frozen_utc=now(),configs=files,confirm_opened=False,reserve_used=False))

def confirm():
 assert (P/'all_dev_configs_frozen.json').exists() and not (P/'confirm_started.json').exists();gate=json.loads((P/'confirm_gate.json').read_text());assert gate['allow_confirm'] and not gate['reserve_allowed']
 dump(P/'confirm_started.json',dict(started_utc=now(),gate_sha256=sha(P/'confirm_gate.json'),dev_receipt_sha256=sha(P/'all_dev_configs_frozen.json'),reserve_used=False))
 for name,source,rep in [('ZL_EVA','ZL3b-n.txt','eva'),('ZL_merged','ZL3b-n.txt','merged'),('IT_EVA','IT2a-n.txt','eva')]:
  data=json.loads((P/'inputs'/(name+'_train_dev.json')).read_text());raw,states,configs=reconstruct(name,rep,data);test=records(corpus.load(source,splits=['confirm']),rep)
  result=evaluate(name,rep,test,raw,states,configs);print(json.dumps([dict(name=name,merge=r['merge'],gain=r['selected_gain'],cost=r['complete_bits_per_word']) for r in result]),flush=True)
 dump(P/'confirm_complete.json',dict(completed_utc=now(),conditions=9,reserve_used=False))

def main():
 a=argparse.ArgumentParser();a.add_argument('mode',choices=['verify','calibrate','fit','confirm']);a.add_argument('--workers',type=int,default=2);args=a.parse_args();receipt_check();freeze()
 if args.mode=='verify':dump(P/'normalization_verification.json',dict(completed_utc=now(),checks=verify(),passed=True));print('normalization passed')
 elif args.mode=='calibrate':assert (P/'normalization_verification.json').exists();calibrate(args.workers)
 elif args.mode=='fit':fit_manuscript()
 else:confirm()
 receipt_check()
if __name__=='__main__':main()
