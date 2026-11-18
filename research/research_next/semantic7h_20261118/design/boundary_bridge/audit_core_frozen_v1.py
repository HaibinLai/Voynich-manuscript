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

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--rebuild-only',action='store_true');p.add_argument('--run',default='run_v1');args=p.parse_args()
 if not args.rebuild_only and not (HERE/args.run/'complete.json').exists():raise SystemExit('Await complete.json; no audit success claimed.')
 out=rebuild(read(INPUT),read(LABELS));(HERE/'audit_rebuilt_v1.json.gz').write_bytes(gzip.compress(json.dumps(out,default=serial,separators=(',',':')).encode(),mtime=0))
 print('Rebuilt 72 rules, 8 folds and all original-page positions independently.')
