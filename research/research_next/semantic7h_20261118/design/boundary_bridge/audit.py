#!/usr/bin/env python3
"""Independent protocol-derived boundary bridge audit; no primary scorer imports.
Uses preserved extraction as input, rebuilding units, cuts, all positions, weights,
and leakage-purged four-fold selection. This observer is not blind to prior studies.
"""
from pathlib import Path
from fractions import Fraction as F
from functools import lru_cache
from collections import Counter,defaultdict
import json,gzip,re,hashlib,datetime,argparse,math
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[4]
INPUT=REPO/'research/research_next/label_body/saved_v1/input.json.gz'
LABELS=HERE.parents[1]/'literature/label_support.json'
CUTS=((0,0),(0,1),(1,0),(0,2),(1,1),(2,0))
RULES=[(a,b,c,d) for a,b in CUTS for c,d in CUTS]
def ruleid(t):return 'qL%dR%d_bL%dR%d'%t
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def avg(xs):return sum(xs,F(0))/len(xs) if xs else None
@lru_cache(None)
def units(s):
 a=tuple(re.findall(r'@\d{3};|[a-z\']',s))
 if not a or ''.join(a)!=s:raise ValueError(('invalid retained token',s))
 return a
@lru_cache(None)
def cut(s,left,right):
 u=units(s);end=len(u)-right;n=end-left
 if n<4:return {'valid':False,'reason':'core_shorter_than_four','core':None,'length':n}
 for k in range(len(u)-2):
  if u[k]=='c' and u[k+1] in ('t','k','f','p') and u[k+2]=='h':
   if k<left<k+3 or k<end<k+3:return {'valid':False,'reason':'boundary_inside_bench','core':None,'length':n}
 return {'valid':True,'reason':None,'core':''.join(u[left:end]),'length':n}
def words(r,v):return [w for loc in r['label_records'][v] for w in re.split(r'[.,]',re.sub(r'<[^>]*>','',loc['raw'])) if w]
def inventories(pages):
 out={};ex={}
 for p in pages:
  arr=[];cnt=Counter()
  for line in p['body']:
   if line['uncertain_space']:
    cnt['uncertain_lines']+=1;cnt['uncertain_slots']+=len(line['tokens']);continue
   for slot,s in enumerate(line['tokens']):
    if s is None:cnt['unresolved_tokens']+=1;continue
    arr.append({'folio':p['folio'],'locator':line['locator'],'source_line':line['source_line'],'slot':slot,'raw':s,'units':list(units(s)),'raw_length':len(units(s)),'cuts':{'L%dR%d'%c:cut(s,*c) for c in CUTS}})
  out[p['folio']]=arr;ex[p['folio']]=dict(cnt)
 return out,ex

def score(arr,query,bc):
 cs=[t['cuts']['L%dR%d'%bc] for t in arr];valid=[i for i,a in enumerate(cs) if a['valid']]
 opp=[i for i in valid if cs[i]['length']==query['length']] if query['valid'] else []
 hit=[i for i in opp if cs[i]['core']==query['core']]
 return {'total':len(arr),'valid_body':len(valid),'body_invalid':dict(Counter(a['reason'] for a in cs if not a['valid'])),'opportunity_indices':opp,'hit_indices':hit,'N':len(opp),'matches':len(hit),'binary':int(bool(hit)),'rate':F(len(hit),len(opp)) if opp else None,'query_valid':query['valid']}

def summarize_one(r,groups=None):
 groups=r['donors'] if groups is None else groups;ss=r['pages'];target=ss[r['target_folio']];leaves={}
 for leaf,fs in groups.items():
  rates=[ss[f]['rate'] for f in fs if ss[f]['N']>0]
  leaves[leaf]={'pages':fs,'binary':avg([ss[f]['binary'] for f in fs]),'N':sum(ss[f]['N'] for f in fs),'rate':avg(rates),'rate_pages':[f for f in fs if ss[f]['N']>0]}
 control=avg([d['binary'] for d in leaves.values()]);rate=avg([d['rate'] for d in leaves.values() if d['rate'] is not None]);nrate=sum(d['rate'] is not None for d in leaves.values())
 eligible=r['query']['valid'] and target['N']>=1 and nrate>=2
 reason=('invalid_query' if not r['query']['valid'] else ('target_zero_opportunities' if target['N']==0 else ('fewer_than_two_supported_control_leaves' if nrate<2 else 'supported')))
 return {'pair_id':r['pair_id'],'source_leaf':r['source_leaf'],'target_leaf':r['target_leaf'],'query_valid':r['query']['valid'],'target':F(target['binary']),'control':control,'delta':F(target['binary'])-control if control is not None else None,'target_rate':target['rate'],'control_rate':rate,'conditional_delta':target['rate']-rate if eligible else None,'conditional_status':reason,'conditional_leaf_count':nrate,'leaves':leaves}

def weighted(rows,key,group='source_leaf'):
 valid=[r for r in rows if r[key] is not None];bucket=defaultdict(list)
 for r in valid:bucket[r[group]].append(r)
 weights={r['pair_id']:F(1,len(bucket)*len(rs)) for rs in bucket.values() for r in rs}
 groups={g:avg([r[key] for r in rs]) for g,rs in bucket.items()}
 return {'value':avg(list(groups.values())),'groups':groups,'weights':weights,'candidate_count':len(valid),'included':[r['pair_id'] for r in valid],'excluded':[r['pair_id'] for r in rows if r[key] is None]}
def summary(rows):
 return {'source':{k:weighted(rows,k) for k in ('target','control','delta','conditional_delta')},'target_leaf_delta':weighted(rows,'delta','target_leaf'),'covered_candidates':[r['pair_id'] for r in rows if r['target']>0],'covered_source_leaves':sorted({r['source_leaf'] for r in rows if r['target']>0}),'covered_target_leaves':sorted({r['target_leaf'] for r in rows if r['target']>0}),'valid_queries':sum(r['query_valid'] for r in rows),'conditional_NA':sum(r['conditional_delta'] is None for r in rows)}

def rebuild(raw,labels):
 selected=[r for r in labels['records'] if r['status']=='source_numbered_locator'];candidates=[r for r in selected if r['fragment_id']!=110];out={}
 for version in ('ZL','IT'):
  pp=raw[version]['pages'];meta={p['folio']:p for p in pp};inv,exc=inventories(pp);base={};rules={}
  for r in candidates:
   w,=words(r,version);s,t=meta[r['pharma_folio']],meta[r['herbal_folio']]
   assert t['I']=='H' and t['H'] not in (None,'','?')
   donors=defaultdict(list)
   for p in pp:
    if p['body'] and (p['H'],p['I'])==(t['H'],t['I']) and p['leaf'] not in (s['leaf'],t['leaf']):donors[p['leaf']].append(p['folio'])
   base[r['pair_id']]={'pair_id':r['pair_id'],'fragment_id':r['fragment_id'],'source_leaf':s['leaf'],'source_folio':s['folio'],'target_leaf':t['leaf'],'target_folio':t['folio'],'raw':w,'donors':dict(donors),'target_HI':[t['H'],t['I']]}
  for rule in RULES:
   rows=[]
   for b in base.values():
    row=dict(b);row['query']=cut(b['raw'],*rule[:2]);row['pages']={f:score(inv[f],row['query'],rule[2:]) for f in [b['target_folio']]+[f for fs in b['donors'].values() for f in fs]};row['result']=summarize_one(row);rows.append(row)
   rules[ruleid(rule)]={'tuple':rule,'rows':rows,'summary':summary([r['result'] for r in rows])}
  baseline=rules[ruleid((0,0,0,0))]['summary']
  for r in rules.values():r['delta_vs_baseline']=r['summary']['source']['delta']['value']-baseline['source']['delta']['value']
  folds={};sourceleaves=sorted({r['source_leaf'] for r in base.values()})
  for held in sourceleaves:
   testids=[b['pair_id'] for b in base.values() if b['source_leaf']==held];heldtargets={b['target_leaf'] for b in base.values() if b['pair_id'] in testids}
   purged=[b['pair_id'] for b in base.values() if b['source_leaf']!=held and b['target_leaf'] in heldtargets]
   trainids=[b['pair_id'] for b in base.values() if b['source_leaf']!=held and b['target_leaf'] not in heldtargets]
   donors={b['pair_id']:{leaf:fs for leaf,fs in b['donors'].items() if leaf not in heldtargets} for b in base.values() if b['pair_id'] in trainids}
   excluded={b['pair_id']:{leaf:fs for leaf,fs in b['donors'].items() if leaf in heldtargets} for b in base.values() if b['pair_id'] in trainids}
   failure='insufficient_training_source_leaves' if len({base[i]['source_leaf'] for i in trainids})<2 else ('training_candidate_without_donor_leaf' if any(not d for d in donors.values()) else None)
   fold={'held_source':held,'held_target_leaves':sorted(heldtargets),'testids':testids,'trainids':trainids,'purged_candidates':purged,'training_donors':donors,'excluded_training_donors':excluded,'NA_reason':failure,'rules':{}}
   for rid,rr in rules.items():
    train=[summarize_one(r,donors[r['pair_id']]) for r in rr['rows'] if r['pair_id'] in trainids]
    test=[r['result'] for r in rr['rows'] if r['pair_id'] in testids]
    fold['rules'][rid]={'train_rows':train,'train_summary':summary(train),'test_rows':test,'test_summary':summary(test)}
   if failure is None:
    ranked=sorted(RULES,key=lambda rule:(-fold['rules'][ruleid(rule)]['train_summary']['source']['delta']['value'],sum(rule),rule))
    chosen=ruleid(ranked[0]);best=fold['rules'][chosen]['train_summary']['source']['delta']['value']
    fold.update(selected=chosen,ranking=[ruleid(r) for r in ranked],maximizers=[ruleid(r) for r in ranked if fold['rules'][ruleid(r)]['train_summary']['source']['delta']['value']==best],train=fold['rules'][chosen]['train_summary'],test=fold['rules'][chosen]['test_summary'],baseline=fold['rules'][ruleid((0,0,0,0))]['test_summary'])
   folds[held]=fold
  validfolds=[f for f in folds.values() if f['NA_reason'] is None]
  cv={'fold_count':len(validfolds),'test_delta':avg([f['test']['source']['delta']['value'] for f in validfolds]),'baseline_delta':avg([f['baseline']['source']['delta']['value'] for f in validfolds])}
  cv['change']=cv['test_delta']-cv['baseline_delta'] if validfolds else None
  out[version]={'inventory':inv,'excluded':exc,'base':base,'rules':rules,'folds':folds,'cv':cv,'excluded110':words(next(r for r in selected if r['fragment_id']==110),version)}
 return out

def serial(x):
 if isinstance(x,F):return {'num':x.numerator,'den':x.denominator,'value':float(x)}
 if isinstance(x,set):return sorted(x)
 raise TypeError(type(x).__name__)


def pack(x):
 if x is None:return None
 x=F(x);return {'num':x.numerator,'den':x.denominator,'value':float(x)}
class Checks:
 def __init__(self):self.counts=Counter();self.failure_count=0;self.errors=[]
 def eq(self,a,b,path,category):
  self.counts[category]+=1
  good=math.isclose(a,b,abs_tol=1e-15,rel_tol=0) if isinstance(b,float) and isinstance(a,(int,float)) else a==b
  if not good:
   self.failure_count+=1
   if len(self.errors)<100:self.errors.append({'path':path,'actual':a,'expected':b})
 def tree(self,a,b,path,category):
  if isinstance(b,dict) and isinstance(a,dict):
   self.eq(set(a),set(b),path+'/keys',category)
   for k,v in b.items():
    if k in a:self.tree(a[k],v,path+'/'+str(k),category)
  elif isinstance(b,list) and isinstance(a,list):
   self.eq(len(a),len(b),path+'/length',category)
   for i,(x,y) in enumerate(zip(a,b)):self.tree(x,y,path+'/'+str(i),category)
  else:self.eq(a,b,path,category)

def check_support(c,out):
 support=read(HERE/'support_primary_v1.json')
 c.tree(support['rules'],[{'id':ruleid(t),'label_cut':list(t[:2]),'body_cut':list(t[2:]),'total_cut':sum(t)} for t in RULES],'rules','support')
 for v,oo in out.items():
  for pid,b in oo['base'].items():
   q=support['query_support'][v][pid]
   for cuttuple in CUTS:
    x=cut(b['raw'],*cuttuple);expected={k:x[k] for k in ('valid','reason')};expected['core_length']=x['length']
    c.tree(q['cuts']['L%dR%d'%cuttuple],expected,v+'/'+pid+'/cuts/'+str(cuttuple),'support')
  for rid,rr in oo['rules'].items():
   rows=rr['rows'];opp=[r for r in rows if r['pages'][r['target_folio']]['N']>0]
   expected={'valid_labels':sum(r['query']['valid'] for r in rows),'target_opportunity_candidates':len(opp),'source_leaves_with_target_opportunity':len({r['source_leaf'] for r in opp}),'target_leaves_with_target_opportunity':len({r['target_leaf'] for r in opp}),'conditional_min1_supported':sum(r['result']['conditional_delta'] is not None for r in rows)}
   actual=support['conditions'][v+'__strict_space__page_HI'][rid]
   for k,val in expected.items():c.eq(actual[k],val,v+'/'+rid+'/'+k,'support')
  for fold in support['leave_source_leaf_out_training_plan']:
   ours=oo['folds'][fold['held_source_leaf']]
   c.eq(fold['test_pair_ids'],ours['testids'],v+'/fold/test','support')
   c.eq(fold['training_pair_ids'],ours['trainids'],v+'/fold/train','support')
   c.eq(fold['shared_target_leaf_purged_pair_ids'],ours['purged_candidates'],v+'/fold/purge','support')

def check_toys(c):
 for word,l,r,reason in [('sochorcfhy',0,2,'boundary_inside_bench'),('oaro',1,0,'core_shorter_than_four'),('cfhaaaa',1,0,'boundary_inside_bench'),('aaaaacfha',0,2,'boundary_inside_bench')]:c.eq(cut(word,l,r)['reason'],reason,'toy/'+word,'synthetic')
 for word,l,r,core in [('@123;abcd',1,0,'abcd'),('cfhabcd',3,0,'abcd'),('xabcdy',1,1,'abcd')]:c.eq(cut(word,l,r)['core'],core,'toy/'+word,'synthetic')
 arr=[{'cuts':{'L0R0':cut('zzabcd',0,0)}},{'cuts':{'L0R0':cut('abcd',0,0)}}]
 x=score(arr,cut('abcd',0,0),(0,0));c.eq(x['hit_indices'],[1],'toy/nonsliding','synthetic')
 x=score(arr,cut('abc',0,0),(0,0));c.eq((x['binary'],x['rate'],x['query_valid']),(0,None,False),'toy/invalid','synthetic')
 c.eq(len(set(RULES)),36,'toy/rules','synthetic')
 # Deliberately unequal page and source counts reveal token/page/group mixing.
 rows=[{'pair_id':'a','source_leaf':'s1','target_leaf':'t','delta':F(1)}, {'pair_id':'b','source_leaf':'s1','target_leaf':'u','delta':F(0)}, {'pair_id':'c','source_leaf':'s2','target_leaf':'v','delta':F(0)}]
 c.eq(weighted(rows,'delta')['value'],F(1,4),'toy/source_weight','synthetic')
 c.eq(weighted(rows,'delta')['weights'],{'a':F(1,4),'b':F(1,4),'c':F(1,2)},'toy/weights','synthetic')
 ranking=sorted([(1,0,0,0),(0,1,0,0),(0,0,2,0),(0,0,0,1)],key=lambda t:(F(0),sum(t),t))
 c.eq(ranking[0],(0,0,0,1),'toy/tie_cut_lex','synthetic')

def rule_object(t):return {'id':ruleid(t),'label_cut':list(t[:2]),'body_cut':list(t[2:]),'total_cut':sum(t)}
def stored_score(s):return {'body_words':s['total'],'valid_body_cores':s['valid_body'],'label_valid':s['query_valid'],'n':s['N'],'m':s['matches'],'binary':s['binary'],'rate':pack(s['rate']),'opportunity_indices':s['opportunity_indices'],'hit_indices':s['hit_indices']}
def stored_contrast(x):
 leaves=[{'leaf':leaf,'pages':d['pages'],'binary':pack(d['binary']),'n':d['N'],'rate':pack(d['rate'])} for leaf,d in sorted(x['leaves'].items())]
 status={'invalid_query':'invalid_label','target_zero_opportunities':'target_zero_opportunity','fewer_than_two_supported_control_leaves':'fewer_than_two_control_leaves','supported':'supported'}[x['conditional_status']]
 return {'donor':{'leaves':leaves,'count':len(leaves),'binary':pack(x['control']),'rate':pack(x['control_rate']),'supported_leaf_count':x['conditional_leaf_count']},'target_binary':int(x['target']),'delta':pack(x['delta']),'conditional_delta':pack(x['conditional_delta']),'conditional_status':status}
def stored_weight(rows,key,group):
 w=weighted(rows,key,group)
 return {'value':pack(w['value']),'groups':{g:pack(x) for g,x in w['groups'].items()},'weights':{i:pack(x) for i,x in w['weights'].items()},'candidates':w['candidate_count']}
def stored_summary(rows):
 ss=summary(rows);out={'candidate_count':len(rows),'valid_labels':ss['valid_queries'],'target_hit_candidates':len(ss['covered_candidates']),'target_hit_source_leaves':ss['covered_source_leaves'],'target_hit_target_leaves':ss['covered_target_leaves']}
 for group in ('source_leaf','target_leaf'):out[group]={key:stored_weight(rows,key,group) for key in ('target','control','delta','conditional_delta')}
 out['contributions']=[dict({k:r[k] for k in ('pair_id','source_leaf','target_leaf')},**{k:pack(r[k]) for k in ('target','control','delta','conditional_delta')}) for r in rows]
 return out

def audit(out,raw,labels,run):
 c=Checks();check_toys(c);check_support(c,out);complete=read(run/'complete.json');freeze=read(run/'freeze.json');files={}
 c.tree({k:v for k,v in complete.items() if k!='files'},{'status':'complete','main_rows':72,'versions':2,'rules':36,'candidates':11,'folds_per_version':4},'complete','freeze')
 expected_files={v+'_'+kind+'.json.gz' for v in ('ZL','IT') for kind in ('inventory','main','loo')}|{'freeze.json','main_table_72.json','main_table_partial.json'}
 c.eq(set(complete['files']),expected_files,'complete/file_set','freeze')
 for f,h in complete['files'].items():c.eq(sha(run/f),h,'complete/'+f,'freeze')
 for f,h in freeze['inputs'].items():c.eq(sha(REPO/f),h,'inputs/'+f,'freeze')
 cross=read(HERE.parent/'crossplant/run_v2/freeze.json')
 for f in (INPUT,LABELS):
  rp=str(f.relative_to(REPO));c.eq(freeze['inputs'][rp],cross['inputs'][rp],'same_original/'+rp,'freeze')
 c.tree(freeze['rules'],[rule_object(t) for t in RULES],'frozen/rules','freeze')
 gatepath=next(REPO/f for f in freeze['inputs'] if 'completed_image_freeze' in f);gate=read(gatepath);c.tree(freeze['image_gate'],gate,'image_gate','freeze')
 for f,h in gate['files'].items():c.eq(sha(gatepath.parent/f),h,'image_gate/'+f,'freeze')
 impl=read(HERE/'audit_implementation_freeze_v1.json');c.eq(sha(HERE/impl['frozen_implementation']),impl['frozen_sha256'],'independent_core_frozen','freeze')
 coreprefix=(HERE/impl['frozen_implementation']).read_text().split("if __name__=='__main__':")[0];c.eq(Path(__file__).read_text().startswith(coreprefix),True,'independent_scorer_unchanged','freeze')
 c.eq(sha(HERE/'protocol_v1.txt'),impl['files']['protocol_v1.txt'],'same_protocol_as_independent_implementation','freeze')
 # Primary source is hashed, not executed or read. Its original toy receipt is
 # a provenance check; synthetic tests above belong to this independent audit.
 toy=read(HERE/'toy_receipt_v1.json');files['primary_toy_receipt_sha256']=sha(HERE/'toy_receipt_v1.json')
 selected={r['pair_id']:r for r in labels['records'] if r['status']=='source_numbered_locator'}
 table=[];positive=[];version_summaries={};page_blocks=0;training_rows=0;token_count=0;cut_count=0
 for v,oo in out.items():
  invactual=read(run/(v+'_inventory.json.gz'));invexpected={};meta={p['folio']:p for p in raw[v]['pages']}
  for f,arr in oo['inventory'].items():
   token_count+=len(arr);cut_count+=6*len(arr)
   wd=[{'word':t['raw'],'units':t['units'],'folio':t['folio'],'locator':t['locator'],'source_line':t['source_line'],'slot':t['slot']} for t in arr]
   cuts={ck:{'forms':[list(units(t['cuts'][ck]['core'])) if t['cuts'][ck]['valid'] else None for t in arr],'invalid_reasons':[t['cuts'][ck]['reason'] for t in arr]} for ck in ['L%dR%d'%cc for cc in CUTS]}
   ex=oo['excluded'][f];exc={dest:ex[src] for src,dest in [('unresolved_tokens','unresolved_tokens'),('uncertain_lines','uncertain_space_lines')] if src in ex}
   invexpected[f]={'words':wd,'cuts':cuts,'excluded':exc}
  c.tree(invactual,invexpected,v+'/inventory','inventory')
  actual=read(run/(v+'_main.json.gz'));c.eq(actual['version'],v,v+'/version','main');c.eq(actual['condition'],'strict_space/page_HI',v+'/condition','main')
  c.eq(list(actual['rules']),list(oo['rules']),v+'/rule_order','main')
  excluded=next(r for r in selected.values() if r['fragment_id']==110)
  loci=lambda rr:[{'locator':l['locator'],'raw':l['raw'],'words':[w for w in re.split(r'[.,]',re.sub(r'<[^>]*>','',l['raw'])) if w]} for l in rr['label_records'][v]]
  c.tree(actual['excluded_group'],[{'pair_id':excluded['pair_id'],'reason':'multi_locus_three_word_group_not_executed','loci':loci(excluded)}],v+'/excluded110','main')
  for rid,rr in oo['rules'].items():
   ar=actual['rules'][rid];c.tree(ar['rule'],rule_object(rr['tuple']),v+'/'+rid+'/rule','main');expected=[]
   for r in rr['rows']:
    row={k:r[k] for k in ('pair_id','fragment_id','source_leaf','target_leaf','target_folio','source_folio')};row.update(label_loci=loci(selected[r['pair_id']]),label_valid=r['query']['valid'],label_invalid_reason=r['query']['reason'],core=list(units(r['query']['core'])) if r['query']['valid'] else None,target=stored_score(r['pages'][r['target_folio']]))
    fs=[p['folio'] for p in raw[v]['pages'] if p['folio'] in r['pages'] and p['folio']!=r['target_folio']]
    row['donor_pages']=[{'folio':f,'leaf':meta[f]['leaf'],'score':stored_score(r['pages'][f])} for f in fs];row['contrast']=stored_contrast(r['result']);expected.append(row);page_blocks+=len(fs)+1
    if not r['query']['valid']:
     c.eq(all(s['binary']==0 and s['rate'] is None and not s['hit_indices'] for s in r['pages'].values()),True,v+'/'+rid+'/'+r['pair_id']+'/invalid','invariant')
    for idx in r['pages'][r['target_folio']]['hit_indices']:
     token=oo['inventory'][r['target_folio']][idx];positive.append({'version':v,'rule':rid,'pair_id':r['pair_id'],'query_original':r['raw'],'query_core':r['query']['core'],'body_original':token['raw'],'body_core':token['cuts']['L%dR%d'%rr['tuple'][2:]]['core'],'folio':token['folio'],'locator':token['locator'],'slot':token['slot'],'source_line':token['source_line'],'inventory_index':idx})
   c.tree(ar['candidates'],expected,v+'/'+rid+'/candidates','main_pages_and_contrasts')
   ssum=stored_summary([r['result'] for r in rr['rows']]);c.tree(ar['summary'],ssum,v+'/'+rid+'/summary','main_summary');table.append({'version':v,'rule':rule_object(rr['tuple']),'summary':ssum})
   c.eq(ssum['source_leaf']['delta']['weights'],stored_summary([r['result'] for r in oo['rules'][ruleid((0,0,0,0))]['rows']])['source_leaf']['delta']['weights'],v+'/'+rid+'/fixed_main_weights','invariant')
  aloo=read(run/(v+'_loo.json.gz'));c.eq(aloo['status'],'complete',v+'/loo/status','loo');c.eq(aloo['completed_folds'],len(oo['folds']),v+'/loo/fold_count','loo');c.eq([f['held_source_leaf'] for f in aloo['folds']],list(oo['folds']),v+'/loo/fold_order','loo')
  c.tree(aloo['source_leaf_equal_test_delta'],pack(oo['cv']['test_delta']),v+'/loo/test_delta','loo');c.tree(aloo['source_leaf_equal_baseline_delta'],pack(oo['cv']['baseline_delta']),v+'/loo/baseline_delta','loo')
  for af in aloo['folds']:
   held=af['held_source_leaf'];ff=oo['folds'][held];fp=v+'/loo/'+held
   c.eq(ff['NA_reason'],None,fp+'/supported_fold','invariant')
   c.eq(af['status'],'complete',fp+'/status','loo');c.eq(af['test_pair_ids'],ff['testids'],fp+'/testids','loo')
   clearance=[]
   for pid in ff['trainids']:
    removed=ff['excluded_training_donors'][pid];rmset={f for fs in removed.values() for f in fs};ordered=[p['folio'] for p in raw[v]['pages'] if p['folio'] in rmset]
    clearance.append({'pair_id':pid,'removed_pages':ordered,'removed_leaf_ids':sorted(removed),'removed_page_count':len(ordered),'removed_leaf_count':len(removed),'remaining_leaf_count':len(ff['training_donors'][pid])})
    c.eq(set(ff['training_donors'][pid])&set(ff['held_target_leaves']),set(),fp+'/'+pid+'/no_held_target_in_training_donor','invariant')
   expected_rules=[]
   for t in RULES:
    rid=ruleid(t);train=ff['rules'][rid]['train_rows'];training_rows+=len(train)
    expected_rules.append({'rule':rule_object(t),'status':'supported','training_pair_ids':ff['trainids'],'purged_pair_ids':ff['purged_candidates'],'held_target_leaves':ff['held_target_leaves'],'donor_clearance':clearance,'training':stored_summary(train)})
   c.tree(af['all_rules'],expected_rules,fp+'/all_rules','loo_all_training_rules')
   chosen=ff['selected'];t=oo['rules'][chosen]['tuple'];c.tree(af['selected_rule'],rule_object(t),fp+'/selected_exact_fraction_min_cut_lex','loo_selection')
   c.tree(af['selected_training'],stored_summary(ff['rules'][chosen]['train_rows']),fp+'/selected_train','loo_selection')
   c.tree(af['test'],stored_summary(ff['rules'][chosen]['test_rows']),fp+'/held_test_original_donors','loo_test')
   c.tree(af['baseline_test'],stored_summary(ff['rules'][ruleid((0,0,0,0))]['test_rows']),fp+'/baseline_test','loo_test')
   delta=ff['test']['source']['delta']['value']-ff['baseline']['source']['delta']['value'];c.tree(af['test_gain_vs_baseline'],pack(delta),fp+'/test_gain','loo_test')
  best=max(rr['summary']['source']['delta']['value'] for rr in oo['rules'].values())
  version_summaries[v]={'rule_count':36,'target_positive_rule_count':sum(bool(rr['summary']['covered_candidates']) for rr in oo['rules'].values()),'max_main_delta':pack(best),'main_maximizers':[rid for rid,rr in oo['rules'].items() if rr['summary']['source']['delta']['value']==best],'main_min_delta':pack(min(rr['summary']['source']['delta']['value'] for rr in oo['rules'].values())),'all_rule_summary':[{'rule':rid,'label_valid':rr['summary']['valid_queries'],'target_hit_candidates':len(rr['summary']['covered_candidates']),'source_leaf_target':pack(rr['summary']['source']['target']['value']),'source_leaf_control':pack(rr['summary']['source']['control']['value']),'source_leaf_delta':pack(rr['summary']['source']['delta']['value']),'delta_vs_baseline':pack(rr['delta_vs_baseline']),'conditional_NA':rr['summary']['conditional_NA']} for rid,rr in oo['rules'].items()],'folds':{h:{'selected_rule':f['selected'],'selected_train_delta':pack(f['train']['source']['delta']['value']),'held_test_delta':pack(f['test']['source']['delta']['value']),'held_baseline_delta':pack(f['baseline']['source']['delta']['value']),'training_maximizers':f['maximizers'],'all_rule_ranking':f['ranking'],'purged_candidate_ids':f['purged_candidates'],'held_target_leaves':f['held_target_leaves']} for h,f in oo['folds'].items()},'cv':{k:pack(x) if k!='fold_count' else x for k,x in oo['cv'].items()}}
 c.tree(read(run/'main_table_72.json'),table,'main_table_72','main_table');c.tree(read(run/'main_table_partial.json'),table,'main_table_partial_retained','main_table')
 failures=[{'file':str(p.relative_to(REPO)),'sha256':sha(p),'receipt':read(p)} for p in sorted(HERE.glob('run*/failure.json'))]
 return {'status':'PASS' if c.failure_count==0 else 'FAIL','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Independent protocol-derived rebuild. Primary run.py/support.py were not read or imported. Scoring core frozen before primary results/schema inspection; only representation adapters added afterward. Raw transcription extraction accepted as supplied. Prior hypotheses and earlier crossplant results known: not a blind audit.','numeric_comparison':'Integer counts, indices, cuts and rational num/den exact; display float absolute tolerance 1e-15. Check counts include scalar/schema comparisons, not independent scientific observations.','failure_count':c.failure_count,'errors_first_100':c.errors,'checks_by_category':dict(c.counts),'coverage':{'versions':2,'rules_per_version':36,'main_candidate_rule_rows':792,'main_page_score_blocks':page_blocks,'raw_retained_tokens':token_count,'body_cut_token_records':cut_count,'folds':8,'training_rule_folds':288,'training_candidate_rule_rows':training_rows},'version_summaries':version_summaries,'all_positive_target_positions':positive,'failed_primary_runs_preserved':failures,'complete_sha256':sha(run/'complete.json'),'audit_script_sha256':sha(__file__),'independent_core_freeze_sha256':sha(HERE/'audit_implementation_freeze_v1.json'),'run_path':str(run.relative_to(REPO)),'limitations':['Post-result exploratory rule family; no calibrated p-value, external validation or decipherment claim.','Invalid label-core zero is not an observed linguistic absence; valid zero opportunities has conditional rate NA.','Historical object hypotheses, text attachment and original transcription extraction are not validated by this numerical audit.','Source-leaf fixed weights and four internal folds do not create independent experts or independent target objects.']}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run',default='run_v1');args=p.parse_args();run=HERE/args.run
 if not (run/'complete.json').exists():raise SystemExit('Await complete.json; no audit success claimed.')
 raw,labels=read(INPUT),read(LABELS);out=rebuild(raw,labels)
 (HERE/'audit_rebuilt_v1.json.gz').write_bytes(gzip.compress(json.dumps(out,default=serial,separators=(',',':')).encode(),mtime=0))
 result=audit(out,raw,labels,run);(HERE/'audit_v1.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=serial)+'\n')
 lines=['Boundary bridge independent audit: '+result['status'],result['scope'],result['numeric_comparison'],'Failures: '+str(result['failure_count']),'Check categories: '+json.dumps(result['checks_by_category']),'Coverage: '+json.dumps(result['coverage']),'Positive target positions: '+json.dumps(result['all_positive_target_positions'],ensure_ascii=False)]
 for v,s in result['version_summaries'].items():
  lines+=['',v+': '+str(s['target_positive_rule_count'])+' / 36 rules with target hits; maximum main delta '+str(s['max_main_delta']),'Four-fold selected test delta '+str(s['cv']['test_delta'])+'; baseline '+str(s['cv']['baseline_delta'])+'; change '+str(s['cv']['change'])]
  for held,f in s['folds'].items():lines.append('  held '+held+' selected '+f['selected_rule']+'; train '+str(f['selected_train_delta'])+'; test '+str(f['held_test_delta']))
  for rr in s['all_rule_summary']:lines.append(json.dumps(rr,ensure_ascii=False))
 if result['failure_count']:lines+=['ERRORS',json.dumps(result['errors_first_100'],ensure_ascii=False,default=serial)]
 lines+=['LIMITATIONS']+result['limitations'];(HERE/'audit_v1.txt').write_text('\n'.join(lines)+'\n')
 print(result['status'],result['failure_count'],'failures;',sum(result['checks_by_category'].values()),'scalar/schema checks;',json.dumps(result['coverage']))
 if result['failure_count']:print(json.dumps(result['errors_first_100'][:5],ensure_ascii=False,default=serial,indent=2))
