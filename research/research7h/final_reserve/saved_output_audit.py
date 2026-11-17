"""Independent eligibility, past-source, aggregation and interval audit of saved runs.
No corpus loader, fitting or new target extraction. Original preflight reference
comparisons apply only in preflight mode; reserve is read only from a completed
saved packet. Prepared and checked on preflight before reserve was opened.
"""
from pathlib import Path
from collections import defaultdict
import argparse,datetime,gzip,hashlib,json,math,re
import numpy as np
P=Path(__file__).resolve().parent;ROOT=P.parent;BASE=ROOT.parent
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,required=True);ap.add_argument('--mode',choices=['preflight','reserve'],required=True);ap.add_argument('--output',type=Path,required=True)
args=ap.parse_args();R=args.run.resolve();out=args.output.resolve();assert not out.exists();MODE=args.mode;SPLIT='confirm' if MODE=='preflight' else 'reserve'
assert (R/'complete.json').is_file(), 'Only completed saved packets may be audited'
NAMES=('ZL_EVA','ZL_merged','IT_EVA');FAMS=('copy','allograph','paragraph','boundary')
CONTRASTS=[('style','copy','global','base'),('boundary_last','boundary','base','last'),('gallows_vs_position','paragraph','position_full','gallows_selected'),('gallows_vs_any_first','paragraph','any_first_selected','gallows_selected'),('copy_total','copy','base','edit_HV'),('copy_edit_vs_exact','copy','exact_HV_matched','edit_HV'),('copy_vertical','copy','edit_H_matched','edit_HV'),('allograph_FP','allograph','base','FP_complete'),('allograph_KT','allograph','base','KT_complete'),('allograph_both','allograph','base','both_complete')]
def bytes_(p):
 if p.exists():return p.read_bytes()
 return gzip.decompress(Path(str(p)+'.gz').read_bytes())
def sha(p):return hashlib.sha256(bytes_(p)).hexdigest()
def read(p):
 b=bytes_(p);return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)
def units(t,rep):
 if t is None:return None
 pat=r"cth|ckh|cph|cfh|ch|sh|@\d{3};|[a-z']" if rep=='merged' else r"@\d{3};|[a-z']"
 u=tuple(re.findall(pat,t));assert ''.join(u)==t;return u
def coord(r):return (r['folio'],r['line'],r['slot'])
def near(a,b,tol=1e-11):assert abs(float(a)-float(b))<tol,(a,b)
def quantile(values,p):
 v=np.sort(values);x=(len(v)-1)*p;i=int(math.floor(x));j=min(i+1,len(v)-1);return float(v[i]+(x-i)*(v[j]-v[i]))
def aggregate(rows,gain):
 assert len(rows)==len(gain);page=defaultdict(list);leaf={}
 for r,v in zip(rows,gain):page[r['folio']].append(float(v));leaf[r['folio']]=r['leaf']
 pp={k:math.fsum(v)/len(v) for k,v in page.items()};ll=defaultdict(list)
 for f,v in pp.items():ll[leaf[f]].append(v)
 return pp,{k:math.fsum(v)/len(v) for k,v in ll.items()}
freeze=read(P/'freeze.json');fh=sha(P/'freeze.json');assert sha(P/'review.txt')==freeze['review_sha256']
checked=[];not_opened=[]
for f in freeze['files']:
 if f['path'] in ('sources/ZL3b-n.txt','sources/IT2a-n.txt'):
  # Frozen original source checks were done by the scoring parent. Avoid even
  # reopening full transcription files in this saved-record-only audit.
  not_opened.append(f);continue
 assert sha(BASE/f['path'])==f['sha256'],f['path'];checked.append(f['path'])
complete=read(R/'complete.json');execution=read(R/'execution_receipt.json');summary=read(R/'summary.json')
assert complete['mode']==MODE and complete['all_passed'] and not complete['failures']
assert len(complete['completed'])==12 and {(x['family'],x['name']) for x in complete['completed']}=={(f,n) for f in FAMS for n in NAMES} and all(x['passed'] for x in complete['completed'])
assert complete['freeze_sha256']==execution['freeze_sha256']==summary['freeze_sha256']==fh
assert execution['mode']==summary['mode']==MODE and summary['split']==SPLIT
assert summary['execution_receipt_sha256']==sha(R/'execution_receipt.json')
for f in execution['input_pages']:assert sha(R/f['path'])==f['sha256']
rows_summary=summary['results']+summary['global_restoration_sensitivity'];assert len(summary['results'])==30 and len(summary['global_restoration_sensitivity'])==9
assert len({(x['representation'],x['id']) for x in rows_summary})==39
old_draws=np.load(R/'bootstrap_draws.npz');old_boot=np.load(R/'bootstrap_means.npz');draw_cache={};audits=[];family_checks=[];poschecks={};arrays_read=[];past_references=0
for name in NAMES:
 rep='merged' if name=='ZL_merged' else 'eva';source='IT2a-n' if name=='IT_EVA' else 'ZL3b-n';pages=read(R/(source+'_pages.json.gz'));assert pages and all(p['split']==SPLIT for p in pages)
 page_by={p['folio']:p for p in pages};allpages=set(page_by);allleaves={p['leaf'] for p in pages};slots=sum(len(l['tokens']) for p in pages for l in p['lines']);missing=sum(t is None for p in pages for l in p['lines'] for t in l['tokens']);expected={f:[] for f in FAMS};lookup={}
 for page in pages:
  for li,line in enumerate(page['lines']):
   words=[units(t,rep) for t in line['tokens']]
   for j,w in enumerate(words):
    if w is None:continue
    c=(page['folio'],li,j);lookup[c]=w;expected['copy'].append(c);expected['allograph'].append(c)
    if j==0 and line['paragraph_start']:expected['paragraph'].append(c)
   expected['boundary'].extend((page['folio'],li,j) for j in range(2,len(words)-1,2) if words[j-1] is not None and words[j] is not None)
 data={}
 for fam in FAMS:
  meta=read(R/(fam+'_'+name+'.json'));rp=R/meta['rows_path'];sp=R/meta['scores_path'];assert sha(rp)==meta['rows_sha256'] and sha(sp)==meta['scores_sha256'];rows=read(rp);scores=np.load(sp);data[fam]=(rows,scores)
  assert [coord(r) for r in rows]==expected[fam];assert all(tuple(r['word'])==lookup[coord(r)] for r in rows)
  assert len(rows)==meta['targets'] and all(len(scores[k])==len(rows) and np.isfinite(scores[k]).all() for k in scores.files)
  e=meta['eligibility'];assert (e['parsed_prose_slots'],e['missing_or_ambiguous_slots'],e['retained_known_slots'],e['scored_target_slots'],e['known_slots_excluded_by_population_rule'])==(slots,missing,slots-missing,len(rows),slots-missing-len(rows))
  for origin in meta['model_origins']:assert sha(BASE/origin['path'])==origin['sha256']
  arrays_read.append(dict(path=sp.name,sha256=sha(sp)));family_checks.append(dict(name=name,family=fam,targets=len(rows),missing_slots=missing,eligibility_reconstructed=True))
 # Check every copy-source reference by independently rebuilding H and V from
 # the saved page's fixed slots, paragraphs, unknowns and blocks.
 A=set(read(ROOT/'copy_prediction/configs'/(name+'.json'))['alphabet']);copyrows,copyarr=data['copy'];by={coord(r):r for r in copyrows}
 for page in pages:
  ww=[[units(t,rep) for t in l['tokens']] for l in page['lines']]
  for li,(line,words) in enumerate(zip(page['lines'],ww)):
   history=[];ok=False
   if li:
    prev=page['lines'][li-1];ok=line.get('paragraph_known',False) and prev.get('paragraph_known',False) and line.get('block')==prev.get('block') and line.get('paragraph')==prev.get('paragraph') and not line['paragraph_start'] and not prev.get('paragraph_end',False)
   for j,w in enumerate(words):
    if w is None:history=[];continue
    row=by[(page['folio'],li,j)];u=sum(c not in A for c in w);assert u==row['unknown'];h=history[-8:];assert [(tuple(s['word']),tuple(s['coord'])) for s in row['H']]==h
    for radius in (1,3):
     sources=[]
     if ok and ww[li-1]:
      prevwords=ww[li-1];x=j/(len(words)-1) if len(words)>1 else 0.;center=math.floor(x*(len(prevwords)-1)+.5)
      for k in range(center-radius//2,center+radius//2+1):
       if 0<=k<len(prevwords) and prevwords[k] is not None and set(prevwords[k])<=A:sources.append((prevwords[k],(page['folio'],li-1,k)))
     actual=[(tuple(s['word']),tuple(s['coord'])) for s in row['V'][str(radius)]];assert actual==sources;past_references+=len(actual)
    past_references+=len(h)
    if u:history=[]
    else:history.append((w,(page['folio'],li,j)))
 assert [coord(r) for r in data['allograph'][0]]==[coord(r) for r in copyrows]
 near(np.max(np.abs(copyarr['base']-data['allograph'][1]['base'])),0)
 # Historical numeric arrays are frozen preflight dependencies; boundary pays
 # target-only identity fees on top of the historical class-word costs.
 if MODE=='preflight':
  old=np.load(ROOT/'copy_prediction/scores'/(name+'.npz'))
  for k in old.files:near(np.max(np.abs(copyarr[k]+old[k])),0)
 suffix={'ZL_EVA':'','ZL_merged':'_merged','IT_EVA':'_IT'}[name];brows,barr=data['boundary'];bcfg=read(ROOT/'results'/('boundary_word_confirm'+suffix+'_frozen_config.json'));ba=set(bcfg['alphabet']);omega=set("abcdefghijklmnopqrstuvwxyz'")|{'@%03d;'%i for i in range(1000)}
 if rep=='merged':omega|={'ch','sh','cth','ckh','cph','cfh'}
 M=len(omega-ba);n=[sum(c not in ba for c in r['word']) for r in brows];cost=np.asarray(n)*math.log2(M);near(np.max(abs(cost-barr['target_escape'])),0);assert n==[r['target_unknown_units'] for r in brows]
 if MODE=='preflight':
  old=np.load(ROOT/'results'/('boundary_word_confirm'+suffix+'_scores.npz'))
  for k in ('base','last'):near(np.max(abs(barr[k]-cost+old[k])),0)
 for cid,fam,a,b in CONTRASTS+[(f'allograph_{m}_global_restore','allograph','base',m+'_complete_global') for m in ('FP','KT','both')]:
  rr,aa=data[fam];gain=aa[a]-aa[b];pp,ll=aggregate(rr,gain);leaves=sorted(ll);values=np.asarray([ll[l] for l in leaves]);obj=next(x for x in rows_summary if x['representation']==name and x['id']==cid)
  assert (obj['words'],obj['eligible_pages'],obj['eligible_leaves'])==(len(rr),len(pp),len(ll))
  assert obj['population']=={'copy':'all_words','allograph':'all_words','boundary':'nonoverlapping_interior_pairs','paragraph':'paragraph_first_words'}[fam]
  assert (obj['model_before'],obj['model_after'],obj['family'])==(a,b,fam)
  near(obj['pooled_before_bits'],math.fsum(float(v) for v in aa[a])/len(rr));near(obj['pooled_after_bits'],math.fsum(float(v) for v in aa[b])/len(rr))
  assert set(obj['per_page_gain'])==set(pp) and set(obj['per_leaf_gain'])==set(ll)
  for k,v in pp.items():near(v,obj['per_page_gain'][k])
  for k,v in ll.items():near(v,obj['per_leaf_gain'][k])
  near(math.fsum(ll.values())/len(ll),obj['mean_leaf_bits_saved']);near(float(gain.mean()),obj['pooled_bits_saved']);assert obj['ineligible']=={'pages':sorted(allpages-set(pp)),'leaves':sorted(allleaves-set(leaves))}
  key=name+'_'+hashlib.sha256(','.join(leaves).encode()).hexdigest()[:12];seed=int.from_bytes(hashlib.sha256(('final-reserve-bootstrap-v1|'+name+'|'+','.join(leaves)).encode()).digest()[:8],'little')
  assert obj['bootstrap_draw_key']==key and obj['bootstrap_seed']==seed and obj['bootstrap_replicates']==99999
  if key not in draw_cache:
   draws=np.random.default_rng(seed).integers(0,len(leaves),size=(99999,len(leaves)));assert np.array_equal(draws,old_draws[key]);draw_cache[key]=draws
  draws=draw_cache[key];means=np.zeros(99999)
  # Frequency-weighted reconstruction, not values[draws].mean(axis=1).
  for i,v in enumerate(values):means+=(draws==i).sum(axis=1)*(v/len(values))
  near(np.max(abs(means-old_boot[name+'__'+cid])),0)
  levels=[('bootstrap95',(.025,.975)),('bootstrap99_5_primary10',(.0025,.9975)),('bootstrap99_833_all30',(.05/60,1-.05/60))]
  for field,ps in levels:
   should=field=='bootstrap95' or (not cid.endswith('_global_restore') and (field!='bootstrap99_5_primary10' or name=='ZL_EVA'))
   if should:
    assert obj[field] is not None
    for actual,p in zip(obj[field],ps):near(actual,quantile(means,p))
   else:assert obj[field] is None
  loo={l:math.fsum(v for k,v in ll.items() if k!=l)/(len(ll)-1) for l in leaves}
  for k,v in loo.items():near(v,obj['leave_one_leaf_out'][k])
  sens={k:v for k,v in ll.items() if k not in ('f15','f103')};assert obj['exposure_sensitivity']['per_leaf'].keys()==sens.keys();near(obj['exposure_sensitivity']['mean_leaf_bits_saved'],math.fsum(sens.values())/len(sens))
  audits.append(dict(name=name,contrast=cid,leaf_mean=math.fsum(ll.values())/len(ll),leaves=len(ll),bootstrap_draw_key=key,quantile_and_loo_verified=True))
 pos=read(R/('position_'+name+'.json'))
 for label,result in pos['conditions'].items():
  arrp=R/'position'/result['null_array'];assert sha(arrp)==result['null_sha256'];arr=np.load(arrp)
  if MODE=='preflight':
   old=np.load(ROOT/'copy_prediction/position_specificity/nulls'/('confirm_'+name+'_'+label+'.npz'))
   assert set(arr.files)==set(old.files)
   for k in arr.files:near(np.max(abs(arr[k]-old[k])),0)
  obs=next(x['leaf_mean'] for x in audits if x['name']==name and x['contrast']=='copy_vertical');near(obs,result['observed_V_gain']);near(float(arr['gain'].mean()),result['null_mean']);near(obs-float(arr['gain'].mean()),result['alignment_specificity_D']);tail=(1+int(np.count_nonzero(arr['gain']>=obs-1e-14)))/2000;near(tail,result['monte_carlo_reference_p'])
  poschecks[name+'_'+label]=tail
# Independently form ordered Holm products followed by cumulative maximum.
ordered=sorted(poschecks,key=lambda k:(poschecks[k],k));adjusted={};acc=0.
for rank,key in enumerate(ordered):acc=max(acc,min(1.,(6-rank)*poschecks[key]));adjusted[key]=acc
for name,entry in summary['position_specificity'].items():
 for label,row in entry['conditions'].items():near(row['holm_reference_p_family6'],adjusted[name+'_'+label])
assert len(audits)==39 and set(old_draws.files)==set(draw_cache) and set(old_boot.files)=={x['name']+'__'+x['contrast'] for x in audits}
report=dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,mode=MODE,split=SPLIT,recommendation='Saved eligibility and aggregate audit passed; independent probability and permutation replay is a separate check.',freeze_sha256=fh,source_complete_sha256=sha(R/'complete.json'),summary_sha256=sha(R/'summary.json'),script_sha256=sha(Path(__file__)),frozen_dependencies_rehashed=len(checked),full_transcription_files_not_reopened=not_opened,
 completed_family_jobs=12,primary_contrasts=30,supplementary_contrasts=9,position_conditions=6,bootstrap_replicates=99999,shared_bootstrap_groups=len(draw_cache),independent_tail_interpolation=True,copy_past_source_references_checked=past_references,core_score_arrays=arrays_read,family_eligibility=family_checks,contrasts=audits,position_tail_holm=adjusted,
 no_corpus_loader_imported=True,raw_corpus_loaded=False,new_target_pages_loaded=False,saved_reserve_packet_read=(MODE=='reserve'),scope='Saved complete packet eligibility, legal past sources, all 39 aggregate contrasts, bootstrap draws/tails, leave-one-leaf, exposure omission and six stored position null summaries/Holm. Full transcription files deliberately not reopened. Does not independently reconstruct probability models or permutation scores; those require separate replays.')
out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['passed','completed_family_jobs','primary_contrasts','supplementary_contrasts','position_conditions','shared_bootstrap_groups','copy_past_source_references_checked']}))
