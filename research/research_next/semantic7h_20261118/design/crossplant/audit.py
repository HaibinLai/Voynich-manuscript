#!/usr/bin/env python3
"""Independent crossplant audit: protocol-derived scoring; never imports primary scorer.
Original transcription extraction is accepted as input; boundaries, units, models,
page positions, opportunities and weighted summaries are independently rebuilt.
"""
from pathlib import Path
import argparse, collections, datetime, gzip, hashlib, json, re, math
from fractions import Fraction as F
from functools import lru_cache
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[4]
INPUT=REPO/'research/research_next/label_body/saved_v1/input.json.gz'
LABELS=HERE.parents[1]/'literature/label_support.json'
PAIRS=('fk','fp','ft','kp','kt','pt')
MODELS=('exact',)+PAIRS+('davis','davis_swapped','davis_sham')
MAPS={'davis':{'f':'te','p':'ke'},'davis_swapped':{'f':'ke','p':'te'},'davis_sham':{'f':'ta','p':'ka'}}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
@lru_cache(maxsize=None)
def units(w):
 u=re.findall(r'@\d{3};|[a-z\']',w)
 if not u or ''.join(u)!=w:raise ValueError(('invalid retained word',w))
 return u
@lru_cache(maxsize=None)
def bare(w):
 # Atomic extended codes cannot expose their internal characters. Protect the
 # middle gallows of every original c[gallows]h sequence, without rewriting.
 u=units(w)
 return [(i,ch) for i,ch in enumerate(u) if ch in 'fkpt' and not (i>0 and i+1<len(u) and u[i-1]=='c' and u[i+1]=='h')]
@lru_cache(maxsize=None)
def canonical(w,m):
 if m not in MAPS:return w
 u=list(units(w))
 for i,ch in bare(w):u[i]=MAPS[m].get(ch,ch)
 return ''.join(u)
@lru_cache(maxsize=None)
def query(w,m):
 if m in MAPS:return {canonical(w,m)}
 out={w}
 if m in PAIRS:
  for i,ch in bare(w):
   if ch in m:
    u=list(units(w));u[i]=m[1] if ch==m[0] else m[0];out.add(''.join(u))
 return out
def average(v):return sum(v,F(0))/len(v) if v else None
def inventory(pages,boundary):
 inv={};excluded={}
 for p in pages:
  arr=[];stats=collections.Counter()
  for line in p['body']:
   if boundary=='strict_space' and line['uncertain_space']:
    stats['uncertain_lines']+=1;stats['uncertain_slots']+=len(line['tokens']);stats['uncertain_nonnull']+=sum(t is not None for t in line['tokens']);continue
   for slot,w in enumerate(line['tokens']):
    if w is None:stats['null_slots']+=1;continue
    arr.append({'folio':p['folio'],'locator':line['locator'],'slot':slot,'source_line':line['source_line'],'raw':w,'units':units(w),'length':len(units(w))})
  inv[p['folio']]=arr;excluded[p['folio']]=dict(stats)
 return inv,excluded
def label_words(r,v):
 return [w for loc in r['label_records'][v] for w in re.split(r'[.,]',re.sub(r'<[^>]*>','',loc['raw'])) if w]
def control_set(pages,src,tgt,mode):
 meta={p['folio']:p for p in pages};s,t=meta[src],meta[tgt]
 if t['I']!='H' or t['H'] in (None,'','?'):raise ValueError(('target metadata',tgt))
 leafhi=collections.defaultdict(set)
 for p in pages:leafhi[p['leaf']].add((p['H'],p['I']))
 groups=collections.defaultdict(list);reason={}
 for p in pages:
  why=[]
  if p['leaf']==s['leaf']:why.append('source_leaf')
  if p['leaf']==t['leaf']:why.append('target_leaf')
  if (p['H'],p['I'])!=(t['H'],t['I']):why.append('page_HI')
  if not p['body']:why.append('no_body')
  if mode=='wholeleaf_HI' and leafhi[p['leaf']]!={(t['H'],t['I'])}:why.append('wholeleaf_HI')
  if why:reason[p['folio']]=why
  else:groups[p['leaf']].append(p['folio'])
 return dict(groups),reason

def page_score(arr,w,m):
 accept=query(w,m);q=canonical(w,m);L=len(units(q))
 vals=[canonical(x['raw'],m) for x in arr]
 opp=[i for i,x in enumerate(vals) if len(units(x))==L]
 hit=[i for i,x in enumerate(vals) if x in accept]
 exact=[i for i,x in enumerate(arr) if x['raw']==w]
 extra=[i for i in hit if i not in set(exact)]
 return {'N':len(opp),'total':len(arr),'opportunity_indices':opp,'hit_indices':hit,'exact_indices':exact,'additional_indices':extra,'binary':int(bool(hit)),'gain':int(bool(hit))-int(bool(exact)),'additional_binary':int(bool(extra)),'rate':F(len(hit),len(opp)) if opp else None,'count':len(hit)}

def endpoint(target,pages,groups,key):
 leaves=[average([pages[f][key] for f in fs]) for fs in groups.values()]
 c=average(leaves);return {'target':target[key],'control':c,'difference':target[key]-c if c is not None else None}
def rate_endpoint(target,pages,groups,n):
 active={leaf:[f for f in fs if pages[f]['N']>0] for leaf,fs in groups.items() if sum(pages[f]['N'] for f in fs)>=n}
 means={leaf:average([pages[f]['rate'] for f in fs]) for leaf,fs in active.items()}
 eligible=target['N']>=n and len(active)>=2
 c=average(list(means.values()))
 return {'eligible':eligible,'target':target['rate'],'control':c,'difference':target['rate']-c if eligible else None,'control_leaves':list(active),'leaf_rates':means,'target_N':target['N']}

def weights(rows,mode):
 if not rows:return {}
 if mode=='candidate':return {r['pair_id']:F(1,len(rows)) for r in rows}
 key='source_leaf' if mode=='source_leaf' else 'target_leaf'
 counts=collections.Counter(r[key] for r in rows)
 return {r['pair_id']:F(1,len(counts)*counts[r[key]]) for r in rows}
def aggregate(rows,path,mode='source_leaf'):
 def val(r):
  a=r
  for k in path:a=a[k]
  return a
 valid=[r for r in rows if val(r) is not None];ww=weights(valid,mode)
 return {'value':sum((ww[r['pair_id']]*val(r) for r in valid),F(0)) if valid else None,'weights':ww,'included':[r['pair_id'] for r in valid],'excluded':[r['pair_id'] for r in rows if val(r) is None]}

def rebuild(raw,labels):
 selected=[r for r in labels['records'] if r['status']=='source_numbered_locator']
 allout={};inventories={};collisions={};excluded={}
 for v in ('ZL','IT'):
  pages=raw[v]['pages'];meta={p['folio']:p for p in pages}
  for boundary in ('strict_space','packet_tokens'):
   inv,ex=inventory(pages,boundary);key=v+'__'+boundary;inventories[key]=inv;excluded[key]=ex
   collisions[key]={}
   for m in MODELS:
    buckets=collections.defaultdict(lambda:collections.Counter())
    for arr in inv.values():
     for t in arr:buckets[canonical(t['raw'],m)][t['raw']]+=1
    labelsbucket=collections.defaultdict(list)
    for r in selected:
     if r['fragment_id']==110:continue
     w,=label_words(r,v);labelsbucket[canonical(w,m)].append({'pair_id':r['pair_id'],'raw':w})
    collisions[key][m]={'body':{c:dict(ct) for c,ct in buckets.items() if len(ct)>1},'labels':{c:vv for c,vv in labelsbucket.items() if len({t['raw'] for t in vv})>1},'combined':{}}
    for c in set(buckets)|set(labelsbucket):
     body=buckets.get(c,{});ll=labelsbucket.get(c,[])
     if len(set(body)|{x['raw'] for x in ll})>1:collisions[key][m]['combined'][c]={'body':dict(body),'labels':ll}
   for cmode in ('page_HI','wholeleaf_HI'):
    condition=key+'__'+cmode;rows=[]
    for r in selected:
     if r['fragment_id']==110:continue
     w,=label_words(r,v);src,tgt=r['pharma_folio'],r['herbal_folio'];groups,reasons=control_set(pages,src,tgt,cmode)
     rr={'pair_id':r['pair_id'],'source_leaf':meta[src]['leaf'],'target_leaf':meta[tgt]['leaf'],'target_folio':tgt,'query_raw':w,'control_groups':groups,'excluded_control_reasons':reasons,'models':{}}
     for m in MODELS:
      scores={f:page_score(inv[f],w,m) for f in [tgt]+[f for fs in groups.values() for f in fs]}
      mm={'accepted':sorted(query(w,m)),'canonical':canonical(w,m),'mechanism_active':len(query(w,m))>1 if m in PAIRS else canonical(w,m)!=w,'pages':scores}
      for endpoint_key in ('binary','gain','additional_binary'):mm[endpoint_key]=endpoint(scores[tgt],scores,groups,endpoint_key)
      for minimum in (1,5):mm['min'+str(minimum)]=rate_endpoint(scores[tgt],scores,groups,minimum)
      rr['models'][m]=mm
     rows.append(rr)
    aggs={}
    for m in MODELS:
     aggs[m]={}
     for ep in ('binary','gain','additional_binary','min1','min5'):
      path=('models',m,ep,'difference');aa={mode:aggregate(rows,path,mode) for mode in ('source_leaf','candidate','target_leaf')}
      aa['active_only']=aggregate([r for r in rows if r['models'][m]['mechanism_active']],path)
      aa['leave_source']={leaf:aggregate([r for r in rows if r['source_leaf']!=leaf],path) for leaf in sorted({r['source_leaf'] for r in rows})}
      aa['leave_target']={leaf:aggregate([r for r in rows if r['target_leaf']!=leaf],path) for leaf in sorted({r['target_leaf'] for r in rows})}
      aggs[m][ep]=aa
    allout[condition]={'records':rows,'aggregates':aggs}
 return {'conditions':allout,'inventories':inventories,'collisions':collisions,'excluded_boundary':excluded,'group110':{v:label_words(next(r for r in selected if r['fragment_id']==110),v) for v in ('ZL','IT')}}

def serial(x):
 if isinstance(x,F):return {'numerator':x.numerator,'denominator':x.denominator,'float':float(x)}
 raise TypeError(type(x).__name__)


def pack(x):
 if x is None:return None
 x=F(x);return {'num':x.numerator,'den':x.denominator,'value':float(x)}
class Checks:
 def __init__(self):self.counts=collections.Counter();self.errors=[];self.failures=0
 def equal(self,got,want,path,category):
  self.counts[category]+=1
  good=(math.isclose(got,want,rel_tol=0,abs_tol=1e-15) if isinstance(want,float) and isinstance(got,(int,float)) else got==want)
  if not good:
   self.failures+=1
   if len(self.errors)<100:self.errors.append({'path':path,'actual':got,'expected':want})
 def tree(self,got,want,path,category):
  if isinstance(want,dict):
   if not isinstance(got,dict):return self.equal(got,want,path,category)
   self.equal(set(got),set(want),path+'/keys',category)
   for k,v in want.items():
    if k in got:self.tree(got[k],v,path+'/'+str(k),category)
  elif isinstance(want,list):
   if not isinstance(got,list):return self.equal(got,want,path,category)
   self.equal(len(got),len(want),path+'/length',category)
   for i,(a,b) in enumerate(zip(got,want)):self.tree(a,b,path+'/'+str(i),category)
  else:self.equal(got,want,path,category)

def stored_page(s,q):
 return {'total_words':s['total'],'query_length':len(units(q)),'opportunities':s['N'],'matches':s['count'],'binary':s['binary'],'exact_matches':len(s['exact_indices']),'exact_binary':int(bool(s['exact_indices'])),'additional_matches':len(s['additional_indices']),'additional_occurrence_binary':s['additional_binary'],'binary_gain':s['gain'],'rate':pack(s['rate']),'match_indices':s['hit_indices'],'exact_match_indices':s['exact_indices'],'additional_match_indices':s['additional_indices'],'opportunity_indices':s['opportunity_indices']}

def stored_endpoint(r,m,n):
 mm=r['models'][m];pages=mm['pages'];leaves=[]
 for leaf,fs in sorted(r['control_groups'].items()):
  eligible=sum(pages[f]['N'] for f in fs)>=n
  rf=[f for f in fs if pages[f]['N']>0] if eligible else []
  d={'leaf':leaf,'pages':fs,'opportunities':sum(pages[f]['N'] for f in fs),'conditional_rate':pack(average([pages[f]['rate'] for f in rf])),'conditional_pages':rf}
  for orig,dest in [('binary','binary'),('gain','binary_gain'),('additional_binary','additional_occurrence_binary')]:d[dest]=pack(average([pages[f][orig] for f in fs]))
  leaves.append(d)
 z=mm['min'+str(n)];donor={'leaves':leaves,'leaf_count':len(leaves),'conditional_rate':pack(z['control']),'conditional_leaf_count':len(z['control_leaves'])}
 for orig,dest in [('binary','binary'),('gain','binary_gain'),('additional_binary','additional_occurrence_binary')]:donor[dest]=pack(mm[orig]['control'])
 status='target_below_threshold' if z['target_N']<n else ('fewer_than_two_supported_control_leaves' if len(z['control_leaves'])<2 else 'supported')
 return {'donor':donor,'binary_delta':pack(mm['binary']['difference']),'binary_gain_delta':pack(mm['gain']['difference']),'additional_binary_delta':pack(mm['additional_binary']['difference']),'conditional_delta':pack(z['difference']),'conditional_status':status}

EP={'binary':'binary','gain':'gain','additional':'additional_binary','conditional1':'min1','conditional5':'min5'}
def grouped_output(rows,m,ep,mode='source_leaf'):
 path=('models',m,ep,'difference');aa=aggregate(rows,path,mode)
 values={r['pair_id']:r['models'][m][ep]['difference'] for r in rows if r['models'][m][ep]['difference'] is not None}
 gs=collections.defaultdict(list)
 for r in rows:
  if r['pair_id'] in values:gs[r[mode]].append(values[r['pair_id']])
 return {'value':pack(aa['value']),'groups':{k:pack(average(v)) for k,v in gs.items()},'group_count':len(gs),'candidate_count':len(values),'weights':{k:pack(v) for k,v in aa['weights'].items()}}
def stored_aggregate(rows,m):
 result={'fixed_all_candidate_count':len(rows),'candidate_rows':[],'primary_source_leaf':{},'diagnostics':{'target_leaf_equal':{},'candidate_equal':{},'active_only':{},'leave_one_source_leaf_out':{},'leave_one_target_leaf_out':{}}}
 for r in rows:
  d={k:r[k] for k in ('pair_id','source_leaf','target_leaf')};d['active']=r['models'][m]['mechanism_active']
  for name,ep in EP.items():d[name]=pack(r['models'][m][ep]['difference'])
  result['candidate_rows'].append(d)
 for name,ep in EP.items():
  result['primary_source_leaf'][name]=grouped_output(rows,m,ep)
  result['diagnostics']['target_leaf_equal'][name]=grouped_output(rows,m,ep,'target_leaf')
  result['diagnostics']['candidate_equal'][name]=pack(aggregate(rows,('models',m,ep,'difference'),'candidate')['value'])
  result['diagnostics']['active_only'][name]=grouped_output([r for r in rows if r['models'][m]['mechanism_active']],m,ep)
 for mode in ('source_leaf','target_leaf'):
  for leaf in sorted({r[mode] for r in rows}):result['diagnostics']['leave_one_'+mode+'_out'][leaf]={name:grouped_output([r for r in rows if r[mode]!=leaf],m,ep) for name,ep in EP.items()}
 return result

def synthetic_checks(c):
 c.equal(query('cfhpf','fp'),{'cfhpf','cfhff','cfhpp'},'bench/single_position','synthetic')
 c.equal(query('ff','fk'),{'ff','kf','fk'},'no_closure','synthetic')
 c.equal(canonical('cfhpf','davis'),'cfhkete','double_sided_nonrecursive','synthetic')
 c.equal(canonical('te','davis'),canonical('f','davis'),'canonical_collision','synthetic')
 c.equal(len(units('@123;f')),2,'extended_atomic','synthetic')
 s=page_score([{'raw':'f'},{'raw':'k'},{'raw':'k'}],'f','fk')
 c.equal((s['count'],s['gain'],s['additional_binary']),(3,0,1),'additional_vs_gain','synthetic')
 z=page_score([{'raw':'a'}],'ff','exact');c.equal((z['N'],z['binary'],z['rate']),(0,0,None),'zero_opportunity','synthetic')
 dummy={'x':{'N':2,'rate':F(1,2)},'y':{'N':3,'rate':F(1,3)},'z':{'N':5,'rate':F(1,5)}}
 rr=rate_endpoint({'N':5,'rate':F(1,5)},dummy,{'a':['x','y'],'b':['z']},5)
 c.equal((rr['eligible'],rr['leaf_rates']['a']),(True,F(5,12)),'leaf_total_min5','synthetic')

def audit(outdir,rebuilt,raw,labels):
 c=Checks();synthetic_checks(c);complete=read(outdir/'complete.json');freeze=read(outdir/'freeze.json')
 c.equal(complete['status'],'complete','complete/status','hash_gate')
 for k,v in {'conditions':8,'models':10,'candidates_per_condition':11,'excluded_group_words':3}.items():c.equal(complete[k],v,'complete/'+k,'hash_gate')
 expected_files={'freeze.json'}|{key+'.json.gz' for key in rebuilt['conditions']}|{prefix+key+'.json.gz' for key in rebuilt['inventories'] for prefix in ('inventory__','collisions__')}
 c.equal(set(complete['files']),expected_files,'complete/files','hash_gate')
 for path,h in complete['files'].items():c.equal(sha(outdir/path),h,path,'hash_gate')
 for path,h in freeze['inputs'].items():c.equal(sha(REPO/path),h,path,'hash_gate')
 gatepath=next(REPO/path for path in freeze['inputs'] if 'completed_image_freeze' in path);gate=read(gatepath)
 c.tree(freeze['image_gate'],gate,'image_gate','hash_gate');c.equal(gate['status'],'complete_image_review','image_gate/status','hash_gate');c.equal(gate['no_crossplant_lexical_results_read'],True,'image_gate/exposure','hash_gate')
 selected=[r for r in labels['records'] if r['status']=='source_numbered_locator'];byid={r['pair_id']:r for r in selected}
 c.equal(set(gate['pair_ids']),set(byid),'image_gate/sample','hash_gate')
 for f,h in gate['files'].items():c.equal(sha(gatepath.parent/f),h,'image_gate/'+f,'hash_gate')
 c.equal(freeze['models'],list(MODELS),'freeze/models','hash_gate')
 for key,inv in rebuilt['inventories'].items():
  actual=read(outdir/('inventory__'+key+'.json.gz'))
  want={f:[dict(word=t['raw'],units=t['units'],folio=t['folio'],locator=t['locator'],slot=t['slot'],source_line=t['source_line'],raw_length=t['length']) for t in arr] for f,arr in inv.items()}
  c.tree(actual['pages'],want,key+'/inventory','inventory')
  excl={f:{dest:st[src] for src,dest in [('uncertain_lines','uncertain_space_lines'),('uncertain_slots','tokens_on_uncertain_space_lines'),('null_slots','unresolved_tokens')] if src in st} for f,st in rebuilt['excluded_boundary'][key].items()}
  c.tree(actual['excluded'],excl,key+'/excluded','boundary')
  collision=read(outdir/('collisions__'+key+'.json.gz'));v=key.split('__')[0]
  for m in MODELS:
   buckets=collections.defaultdict(collections.Counter)
   for arr in inv.values():
    for t in arr:buckets[canonical(t['raw'],m)][t['raw']]+=1
   for r in selected:
    if r['fragment_id']!=110:
     w,=label_words(r,v);buckets[canonical(w,m)][w]+=1
   groups=[{'canonical':k,'canonical_length':len(units(k)),'raw_types':dict(ct)} for k,ct in sorted(buckets.items()) if len(ct)>1]
   c.equal(collision[m]['model'],m,key+'/'+m+'/model','collision')
   c.equal(collision[m]['canonical_type_count'],len(buckets),key+'/'+m+'/types','collision')
   c.equal(collision[m]['collision_group_count'],len(groups),key+'/'+m+'/group_count','collision')
   c.tree(collision[m]['collision_groups'],groups,key+'/'+m+'/groups','collision')
 condition_summary={};score_count=0;non_equivalence_examples=[]
 for key,data in rebuilt['conditions'].items():
  v,boundary,cmode=key.split('__');actual=read(outdir/(key+'.json.gz'));rows=data['records'];pages=raw[v]['pages'];meta={p['folio']:p for p in pages}
  for k,val in [('version',v),('boundary',boundary),('control',cmode)]:c.equal(actual[k],val,key+'/'+k,'condition')
  c.equal([r['pair_id'] for r in actual['candidates']],[r['pair_id'] for r in rows],key+'/sample','condition')
  excluded=next(r for r in selected if r['fragment_id']==110)
  expected_group=[{'pair_id':excluded['pair_id'],'reason':'multi_locus_three_word_group_not_executed','loci':[{'locator':loc['locator'],'raw':loc['raw'],'words':[w for w in re.split(r'[.,]',re.sub(r'<[^>]*>','',loc['raw'])) if w]} for loc in excluded['label_records'][v]]}]
  c.tree(actual['excluded_three_word_group'],expected_group,key+'/110','condition')
  for r,ar in zip(rows,actual['candidates']):
   pth=key+'/'+r['pair_id'];prior=byid[r['pair_id']];t=meta[r['target_folio']];s=meta[prior['pharma_folio']]
   expectedmeta={'pair_id':r['pair_id'],'fragment_id':prior['fragment_id'],'source_leaf':r['source_leaf'],'target_leaf':r['target_leaf'],'source_folio':prior['pharma_folio'],'target_folio':r['target_folio'],'source_grade':prior['source_grade'],'target_H':t['H'],'target_I':t['I'],'target_leaf_mixed_HI':len({(p['H'],p['I']) for p in pages if p['leaf']==t['leaf']})>1,'loci':[{'locator':loc['locator'],'raw':loc['raw'],'words':[re.sub(r'<[^>]*>','',loc['raw'])]} for loc in prior['label_records'][v]]}
   for k,val in expectedmeta.items():c.tree(ar[k],val,pth+'/'+k,'metadata')
   rejected=[]
   for p in pages:
    if not p['body'] or (p['H'],p['I'])!=(t['H'],t['I']):continue
    reason='source_or_target_physical_leaf' if p['leaf'] in (s['leaf'],t['leaf']) else ('mixed_HI_donor_leaf' if cmode=='wholeleaf_HI' and any((q['H'],q['I'])!=(t['H'],t['I']) for q in pages if q['leaf']==p['leaf']) else None)
    if reason:rejected.append({'folio':p['folio'],'leaf':p['leaf'],'reason':reason})
   c.tree(ar['rejected_same_HI_donor_pages'],rejected,pth+'/rejected','control_exclusion')
   for m,mm in r['models'].items():
    am=ar['models'][m];mp=pth+'/'+m;c.equal(am['model'],m,mp+'/model','query')
    for k,val in [('mechanism_active',mm['mechanism_active']),('query_original',r['query_raw']),('query_canonical',mm['canonical']),('accepted_forms',mm['accepted']),('candidate_count',len(mm['accepted']))]:c.equal(am[k],val,mp+'/'+k,'query')
    c.tree(am['target'],stored_page(mm['pages'][r['target_folio']],mm['canonical']),mp+'/target','page_score');score_count+=1
    folios=[p['folio'] for p in pages if any(p['folio'] in fs for fs in r['control_groups'].values())]
    expected_donors=[{'folio':f,'leaf':meta[f]['leaf'],'score':stored_page(mm['pages'][f],mm['canonical'])} for f in folios]
    c.tree(am['donor_pages'],expected_donors,mp+'/donors','page_score');score_count+=len(folios)
    for n in (1,5):c.tree(am['endpoints']['min'+str(n)],stored_endpoint(r,m,n),mp+'/min'+str(n),'leaf_endpoint')
    if m in PAIRS and not mm['mechanism_active']:
     c.equal([x['gain'] for x in mm['pages'].values()],[0]*len(mm['pages']),mp+'/inactive_gain','invariant')
     c.equal([x['additional_binary'] for x in mm['pages'].values()],[0]*len(mm['pages']),mp+'/inactive_additional','invariant')
    for f,sc in mm['pages'].items():
     if sc['additional_binary']!=sc['gain'] and len(non_equivalence_examples)<12:non_equivalence_examples.append({'condition':key,'pair':r['pair_id'],'model':m,'folio':f,'gain':sc['gain'],'additional_binary':sc['additional_binary']})
   for f in r['models']['davis']['pages']:
    c.equal(r['models']['davis']['pages'][f]['opportunity_indices'],r['models']['davis_swapped']['pages'][f]['opportunity_indices'],pth+'/'+f+'/common_length_swapped','invariant')
    c.equal(r['models']['davis']['pages'][f]['opportunity_indices'],r['models']['davis_sham']['pages'][f]['opportunity_indices'],pth+'/'+f+'/common_length_sham','invariant')
  for m in MODELS:c.tree(actual['aggregate'][m],stored_aggregate(rows,m),key+'/aggregate/'+m,'aggregate')
  condition_summary[key]={m:{'target_positive_count':sum(r['models'][m]['pages'][r['target_folio']]['binary'] for r in rows),'target_additional_count':sum(r['models'][m]['pages'][r['target_folio']]['additional_binary'] for r in rows),'source_leaf_binary_difference':pack(data['aggregates'][m]['binary']['source_leaf']['value']),'source_leaf_binary_gain_difference':pack(data['aggregates'][m]['gain']['source_leaf']['value']),'min1_included':data['aggregates'][m]['min1']['source_leaf']['included'],'min5_included':data['aggregates'][m]['min5']['source_leaf']['included']} for m in MODELS}
 return {'status':'PASS' if c.failures==0 else 'FAIL','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'run':str(outdir.relative_to(REPO)),'scope':'Independent protocol-derived numerical rebuild from preserved input packet; primary run.py and support.py scoring functions were neither imported nor read. Output schema inspected only after independent scoring implementation was written. Original transcription extraction not independently redone. Prior image hypotheses were known; this is not a blind audit.','exactness':'All integer counts, indices and rational numerator/denominator pairs compared exactly; float rendering tolerance absolute 1e-15.','checks_by_category':dict(c.counts),'failure_count':c.failures,'errors_first_100':c.errors,'page_model_score_count':score_count,'conditions':8,'models':10,'single_candidates':11,'source_physical_leaves':4,'unique_target_physical_leaves':10,'excluded_110_words':rebuilt['group110'],'condition_summary':condition_summary,'additional_is_not_gain_examples':non_equivalence_examples,'audit_source_sha256':sha(__file__),'complete_sha256':sha(outdir/'complete.json'),'primary_failure_preserved':read(HERE/'run_v1/failure.json'),'limitations':['Numerical agreement does not validate the historical image pairings, text attachment or semantic readings.','No independent raw transcription extraction or expert paleographic identification was performed.','No IID significance claim is supplied.']}

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--run',default='run_v2');args=parser.parse_args();outdir=HERE/args.run
 if not (outdir/'complete.json').exists():raise SystemExit('Awaiting complete.json; no audit success claimed.')
 raw,labels=read(INPUT),read(LABELS);rebuilt=rebuild(raw,labels)
 (HERE/'audit_rebuilt_v1.json.gz').write_bytes(gzip.compress(json.dumps(rebuilt,default=serial,separators=(',',':')).encode(),mtime=0))
 result=audit(outdir,rebuilt,raw,labels)
 def robust(x):
  if isinstance(x,set):return sorted(x)
  if isinstance(x,F):return pack(x)
  raise TypeError(type(x).__name__)
 (HERE/'audit_v1.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=robust)+'\n')
 lines=['Crossplant independent numerical audit '+result['status'],result['scope'],result['exactness'],'Checks: '+str(sum(result['checks_by_category'].values())),'Failures: '+str(result['failure_count']),'Page-model score blocks: '+str(result['page_model_score_count']),json.dumps(result['checks_by_category'],indent=2),'Eight conditions x 11 candidates x 10 models; all saved inventory positions, opportunities, counts, complete hits, collisions, leaf summaries and aggregation weights reconstructed.','Original failed run_v1 preserved; successful run_v2 uses the same frozen primary source with an absolute image-freeze argument.']
 for key,ss in result['condition_summary'].items():
  lines.append(key)
  for m,d in ss.items():lines.append('  '+m+': target positives='+str(d['target_positive_count'])+', target additional='+str(d['target_additional_count'])+', primary binary delta='+str(d['source_leaf_binary_difference'])+', min1/min5 candidates='+str(len(d['min1_included']))+'/'+str(len(d['min5_included'])))
 if result['failure_count']:lines+=['ERRORS',json.dumps(result['errors_first_100'],default=robust,ensure_ascii=False,indent=2)]
 lines+=['LIMITATIONS']+result['limitations']
 (HERE/'audit_v1.txt').write_text('\n'.join(lines)+'\n')
 print(result['status'],result['failure_count'],'failures;',sum(result['checks_by_category'].values()),'checks; page scores',result['page_model_score_count'])
 if result['errors_first_100']:print(json.dumps(result['errors_first_100'][:5],default=robust,ensure_ascii=False,indent=2))
