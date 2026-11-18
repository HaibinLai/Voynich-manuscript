#!/usr/bin/env python3
"""Compare primary saved schemas against independently frozen reconstruction.
Does not import/read primary scoring source. Exact rational comparison; float
projections checked at 1e-12. Schema projection only, no tuning of scorer.
"""
import json,gzip,hashlib,datetime,re
from pathlib import Path
from collections import Counter,defaultdict
from fractions import Fraction as F
import audit_numeric as independent
import audit_structure_core_frozen_v1 as parser
P=Path(__file__).resolve().parent;REPO=P.parents[4];RUN=P/'run_v1'
counts=Counter();diff=[]
def read(p):return independent.read(p)
def sha(p):return independent.sha(p)
def canon(x):
 if isinstance(x,dict):
  if set(x)=={'numerator','denominator'}:return F(x['numerator'],x['denominator'])
  if set(x)=={'num','den','value'}:
   q=F(x['num'],x['den']);check('rational_float',float(q),x['value']);return q
  return {k:canon(v) for k,v in x.items()}
 if isinstance(x,list):return [canon(v) for v in x]
 return x

def check(path,a,b):
 if isinstance(a,dict) and isinstance(b,dict):
  if set(a)!=set(b):record(path+'.keys',sorted(a),sorted(b))
  for k in a.keys()&b.keys():check(path+'.'+k,a[k],b[k])
 elif isinstance(a,list) and isinstance(b,list):
  check(path+'.length',len(a),len(b))
  for i,(x,y) in enumerate(zip(a,b)):check(path+'[%d]'%i,x,y)
 else:
  counts['scalar_checks']+=1
  okay=abs(a-b)<=1e-12 if isinstance(a,float) and isinstance(b,(float,int)) else a==b
  if not okay:record(path,a,b)
def record(path,a,b):
 counts['differences']+=1
 if len(diff)<100:diff.append({'path':path,'independent':str(a)[:500],'primary':str(b)[:500]})
def window(w,m):
 rev=m=='adjacent_reverse';ss=w['slots'];ordered=ss[::-1] if rev else ss
 r={'id':w['locator']+':'+','.join(map(str,ss)),'locator':w['locator'],'source_line':w['source_line'],'slots':ss,'ordered_slots':ordered,'words':w['raw_words'][::-1] if rev else w['raw_words'],'joined':w['joined']}
 if m!='exact':r.update(span_slots=list(range(ss[0],ss[-1]+1)),component_lengths=w['unit_lengths'][::-1] if rev else w['unit_lengths'],uncertain_space=w['uncertain_space'])
 return r

def expected_page(r,f,m):
 s=r['pages'][f][m];u=r['unions'][m]['pages'][f];e=r['pages'][f]['exact']['binary'];op=[window(w,m) for w in s['opportunities']]
 return {'opportunities':op,'hits':[op[i] for i in s['hit_indices']],'n':s['N'],'m':s['matches'],'binary':s['binary'],'rate':s['rate'],'exact_binary':e,'union_binary':u['union'],'coverage_gain':u['gain'],'join_occurrence_present':0 if m=='exact' else u['additional_occurrence']}

def endpoint(r,m,key):
 if key=='binary':return {e:r['results'][m][e] for e in ('target','control','delta')}
 if key=='exact_binary':return {e:r['results']['exact'][e] for e in ('target','control','delta')}
 if key=='join_occurrence_present' and m=='exact':return {e:F(0) for e in ('target','control','delta')}
 u={'union_binary':'union','coverage_gain':'gain','join_occurrence_present':'additional_occurrence'}[key]
 return {e:r['unions'][m]['summary'][u][e] for e in ('target','control','delta')}

def contrast(r,m):
 rr=r['results'][m];leaves=[]
 for leaf,fs in sorted(r['donors'].items()):
  row={'leaf':leaf,'pages':fs,'n':rr['leaves'][leaf]['N'],'rate':rr['leaves'][leaf]['rate']}
  for k in ('binary','exact_binary','union_binary','coverage_gain','join_occurrence_present'):
   row[k]=independent.average([F(expected_page(r,f,m)[k]) for f in fs])
  leaves.append(row)
 donor={'leaves':leaves,'leaf_count':len(leaves),'supported_leaves':rr['conditional_leaf_count'],'rate':rr['control_rate']}
 for k in ('binary','exact_binary','union_binary','coverage_gain','join_occurrence_present'):donor[k]=endpoint(r,m,k)['control']
 out={'donor':donor,**{k+'_delta':endpoint(r,m,k)['delta'] for k in ('binary','exact_binary','union_binary','coverage_gain','join_occurrence_present')},'conditional_delta':rr['conditional_delta'],'conditional_status':{'supported':'supported','target_zero_opportunities':'target_zero_opportunity','fewer_than_two_supported_control_leaves':'fewer_than_two_control_leaves'}[rr['conditional_status']]}
 return out

def contributions(rows,m):
 result=[]
 for r in rows:
  a={k:r[k] for k in ('pair_id','source_leaf','target_leaf')};a['conditional_delta']=r['results'][m]['conditional_delta']
  for k in ('binary','exact_binary','union_binary','coverage_gain','join_occurrence_present'):
   for e,v in endpoint(r,m,k).items():a[k+'_'+e]=v
  result.append(a)
 return result

def summarize(rows,m):
 cc=contributions(rows,m);out={'candidate_count':len(rows),'target_hit_candidates':sum(r['results'][m]['target']>0 for r in rows),'target_hit_source_leaves':sorted({r['source_leaf'] for r in rows if r['results'][m]['target']>0}),'target_hit_target_leaves':sorted({r['target_leaf'] for r in rows if r['results'][m]['target']>0}),'target_newly_covered_candidates':sum(endpoint(r,m,'coverage_gain')['target']>0 for r in rows),'contributions':cc}
 for grouping in ('source_leaf','target_leaf'):
  result={}
  for metric in (k for k in cc[0] if k not in ('pair_id','source_leaf','target_leaf')):
   valid=[r for r in cc if r[metric] is not None];groups=defaultdict(list)
   for r in valid:groups[r[grouping]].append(r)
   gs={g:independent.average([r[metric] for r in rr]) for g,rr in groups.items()};weights={r['pair_id']:F(1,len(groups)*len(rr)) for rr in groups.values() for r in rr}
   result[metric]={'value':independent.average(list(gs.values())),'groups':gs,'candidates':len(valid),'weights':weights}
  out[grouping]=result
 return out

def raw_extras(raw):
 # Extra provenance fields are recomputed by scanning original character indices.
 tags=[];seps=[];pos=0;i=0
 while i<len(raw):
  c=raw[i]
  if c=='<':
   j=raw.index('>',i)+1;tag=raw[i:j];tags.append({'position':pos,'raw_start':i,'raw_end':j,'tag':tag})
   if tag in ('<->','<~>'):
    # Primary records separators induced by graphic tags separately; inspected below.
    seps.append({'position':pos,'kind':'graphic_tag','raw_position':i});pos+=1
   i=j;continue
  if c.isspace() or c in '{}':i+=1;continue
  if c in '.,':seps.append({'position':pos,'kind':'uncertain_comma' if c==',' else 'dot','raw_position':i})
  pos+=1;i+=1
 return tags,seps

def inspect_inventory(primary,version,boundary,raw):
 pages=raw[version]['pages'];check('inventory.pages',list(primary),[p['folio'] for p in pages])
 for pg in pages:
  kept=[];excluded=[]
  for loc in pg['body']:
   if boundary=='strict_space' and loc['uncertain_space']:excluded.append({'locator':loc['locator'],'reason':'uncertain_space_line'});continue
   parsed=parser.parse_raw(loc['raw']);assert [t['raw'] for t in parsed['tokens']]==loc['tokens']
   toks=[]
   for t in parsed['tokens']:
    toks.append({'slot':t['slot'],'word':t['raw'],'start':t['start'],'end':t['end'],'comparable':t['comparable'],'reason':None if t['comparable'] else ('unknown_or_alternative' if t['raw'] is None else 'internal_tag'),'length':len(t['units']) if t['units'] else None,'internal_tags':[]})
   tags,seps=raw_extras(loc['raw']);kept.append({'locator':loc['locator'],'source_line':loc['source_line'],'uncertain_space':loc['uncertain_space'],'tokens':toks,'barriers':tags,'separators':seps,'packet_reproduced':True,'raw':loc['raw']})
   counts['inventory_loci']+=1;counts['inventory_tokens']+=len(toks);counts['inventory_tags']+=len(tags)
  check('inventory.'+version+'.'+boundary+'.'+pg['folio'],{'rows':kept,'excluded':excluded},primary[pg['folio']])

def main():
 start=datetime.datetime.now(datetime.timezone.utc).isoformat();complete=read(RUN/'complete.json');check('complete.status','complete',complete['status'])
 for f,h in complete['files'].items():check('complete.hash.'+f,h,sha(RUN/f));counts['output_hashes']+=1
 freeze=read(RUN/'freeze.json')
 for f,h in freeze['inputs'].items():check('freeze.hash.'+f,h,sha(REPO/f));counts['input_hashes']+=1
 for f,h in read(P/'audit_numeric_freeze_v1.json')['files'].items():check('independent.freeze.'+f,h,sha(f))
 image=freeze['image_gate'];ip=P.parents[1]/'visual/crossplant'
 for f,h in image['files'].items():check('image.freeze.'+f,h,sha(ip/f));counts['image_hashes']+=1
 own=canon(read(P/'audit_rebuilt_v1.json.gz'));raw=read(independent.INPUT);labels=read(independent.LABELS);labelmap={r['pair_id']:r for r in labels['records']};summary16=[];compact=[];alltarget=[]
 for version in ('ZL','IT'):
  for boundary in ('strict_space','packet_tokens'):
   key=version+'_'+boundary;primary=canon(read(RUN/(version+'__'+boundary+'.json.gz')));o=own[key];rows=o['rows'];check(key+'.ids',[r['pair_id'] for r in rows],[r['pair_id'] for r in primary['candidates']]);check(key+'.condition',boundary+'/page_HI',primary['condition']);check(key+'.version',version,primary['version'])
   for r,c in zip(rows,primary['candidates']):
    for field in ('pair_id','fragment_id','query','source_leaf','source_folio','target_leaf','target_folio'):check(key+'.candidate.'+field,r[field],c[field])
    locs=[]
    for loc in labelmap[r['pair_id']]['label_records'][version]:locs.append({'locator':loc['locator'],'raw':loc['raw'],'words':[w for w in re.split('[.,]',re.sub('<[^>]*>','',loc['raw'])) if w]})
    check(key+'.label_loci',locs,c['label_loci'])
    expectedfs=[f for fs in r['donors'].values() for f in fs];check(key+'.donor_set',sorted(expectedfs),sorted(d['folio'] for d in c['donor_pages']))
    pgmap={r['target_folio']:c['target'],**{d['folio']:d['models'] for d in c['donor_pages']}}
    for d in c['donor_pages']:check(key+'.donor_leaf',next(l for l,fs in r['donors'].items() if d['folio'] in fs),d['leaf'])
    for f,ss in pgmap.items():
     for m in independent.METHODS:
      expected=expected_page(r,f,m);check(key+'.'+r['pair_id']+'.'+f+'.'+m,expected,ss[m]);counts['page_model_blocks']+=1;counts['opportunity_windows']+=expected['n'];counts['hit_windows']+=expected['m']
      if f==r['target_folio'] and expected['hits']:alltarget.append({'condition':key,'pair_id':r['pair_id'],'model':m,'hits':expected['hits']})
    for m in independent.METHODS:check(key+'.contrast.'+m,contrast(r,m),c['contrasts'][m])
   for m in independent.METHODS:
    expected=summarize(rows,m);check(key+'.summary.'+m,expected,primary['models'][m]);summary16.append({'version':version,'boundary':boundary,'model':m,'summary':expected});counts['condition_model_summaries']+=1
    compact.append({'condition':key,'model':m,'target_hit_candidates':expected['target_hit_candidates'],'source_binary_delta':expected['source_leaf']['binary_delta']['value'],'source_union_delta':expected['source_leaf']['union_binary_delta']['value'],'source_gain_delta':expected['source_leaf']['coverage_gain_delta']['value'],'conditional_included':expected['source_leaf']['conditional_delta']['candidates']})
   excluded=[r for r in labels['records'] if r['status']=='source_numbered_locator' and r['fragment_id']==110];e=[]
   for r in excluded:e.append({'pair_id':r['pair_id'],'reason':'two_locus_three_word_group_not_executed','loci':[{'locator':l['locator'],'raw':l['raw'],'words':[w for w in re.split('[.,]',re.sub('<[^>]*>','',l['raw'])) if w]} for l in r['label_records'][version]]})
   check(key+'.excluded_group',e,primary['excluded_group'])
   inspect_inventory(read(RUN/('inventory__'+version+'__'+boundary+'.json.gz')),version,boundary,raw)
 check('summary_16',summary16,canon(read(RUN/'summary_16.json')));check('summary_partial',summary16,canon(read(RUN/'summary_partial.json')))
 out={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'started':start,'status':'PASS' if not counts['differences'] else 'FAIL','scope':'4 conditions x 4 mechanisms; every target/donor opportunity and hit, inventories, counts/rates/NA, rational leaf and source/target weights, all unions/gains, contributions, summary copies, freezes and completion hashes.','independence':'Numerical core frozen and executed before primary result read. No primary scorer or support implementation read/imported; known prior studies/design motivation, not a blind review.','counts':dict(counts),'differences':diff,'summary':compact,'target_hits':alltarget,'failed_primary_runs':[str(p.relative_to(P)) for p in P.glob('run*/failure.json')],'limitations':['Original transcription extraction accepted; no new image/text annotation.','Only encoded interruptions can be screened.','H grouping inherited, not independent historical ground truth.','Post-result exploratory rule with known English motivation; no significance or semantic identification claim.','IT strict_space and packet_tokens inputs coincide and are not independent replications.'],'schema_projection_notes':['Two initial comparison attempts retained: only adapter naming/shape corrections (condition suffix, excluded list wrapper, graphic_tag and uncertain_comma names). Frozen numerical core and reconstructed results unchanged.','Exact join_occurrence_present is zero by definition; independent generic exact additional_occurrence field is a redundant exact indicator and is not projected as a join.','Rational values exact; redundant float fields checked at absolute tolerance 1e-12.'],'files':{f:sha(P/f) for f in ['audit_numeric.py','audit_structure_core_frozen_v1.py','audit_numeric_freeze_v1.json','audit_rebuilt_v1.json.gz','audit_compare.py']},'primary_complete_sha256':sha(RUN/'complete.json')}
 (P/'audit_v1.json').write_text(json.dumps(independent.pack(out),ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':out['status'],'counts':dict(counts),'first_differences':diff[:8]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
