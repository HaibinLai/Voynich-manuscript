#!/usr/bin/env python3
"""Independent numerical reconstruction. Uses only our independently written parser.
Never imports or reads the primary scorer. Root authorization: 2026-11-18.
"""
from pathlib import Path
from fractions import Fraction as F
from collections import defaultdict,Counter
import json,gzip,re,hashlib,datetime,argparse
import audit_structure_core_frozen_v1 as structural
P=Path(__file__).resolve().parent;REPO=P.parents[4]
INPUT=REPO/'research/research_next/label_body/saved_v1/input.json.gz'
LABELS=P.parents[1]/'literature/label_support.json'
METHODS=('exact','adjacent_forward','adjacent_reverse','gap2_forward')

def read(p):
 p=Path(p);return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def average(xs):return sum(xs,F(0))/len(xs) if xs else None
def pack(x):
 if isinstance(x,F):return {'numerator':x.numerator,'denominator':x.denominator}
 if isinstance(x,dict):return {k:pack(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [pack(v) for v in x]
 return x

def rebuild_inventory(pages,boundary):
 result={};exclusions={}
 for pg in pages:
  lines=[];counts=Counter();tokens=[]
  for loc in pg['body']:
   if boundary=='strict_space' and loc['uncertain_space']:
    counts['uncertain_loci']+=1;counts['uncertain_slots']+=len(loc['tokens']);continue
   parsed=structural.parse_raw(loc['raw'])
   if [t['raw'] for t in parsed['tokens']]!=loc['tokens']:
    counts['slot_mismatch_loci']+=1;continue
   line=dict(parsed,locator=loc['locator'],source_line=loc['source_line'],uncertain_space=loc['uncertain_space'])
   for token in line['tokens']:
    if token['raw'] is None:counts['unknown_slots']+=1
    elif not token['comparable']:counts['internally_marked_slots']+=1
    token['inventory_index']=len(tokens)
    tokens.append(dict(token,locator=loc['locator'],source_line=loc['source_line'],uncertain_space=loc['uncertain_space']))
   lines.append(line)
  result[pg['folio']]={'lines':lines,'tokens':tokens};exclusions[pg['folio']]=dict(counts)
 return result,exclusions

def windows(inv,query,method):
 result=[];length=len(structural.units(query));bad=structural.forbidden_seams(query)
 for line in inv['lines']:
  ts=line['tokens']
  if method=='exact':
   for t in ts:
    if t['comparable'] and len(t['units'])==length:
     result.append({'locator':line['locator'],'source_line':line['source_line'],'slots':[t['slot']],'raw_words':[t['raw']],'joined':t['raw'],'unit_lengths':[len(t['units'])],'uncertain_space':line['uncertain_space']})
  else:
   distance=2 if method=='gap2_forward' else 1
   for i in range(len(ts)-distance):
    if not structural.valid_window(line,i,distance):continue
    a,b=ts[i],ts[i+distance];la,lb=len(a['units']),len(b['units'])
    if la+lb!=length or la in bad or lb in bad:continue
    pair=[b,a] if method=='adjacent_reverse' else [a,b]
    result.append({'locator':line['locator'],'source_line':line['source_line'],'slots':[i,i+distance],'raw_words':[a['raw'],b['raw']],'joined':''.join(t['raw'] for t in pair),'unit_lengths':[la,lb],'uncertain_space':line['uncertain_space'],'middle_raw':ts[i+1]['raw'] if distance==2 else None})
 return result

def score(inv,query,method):
 w=windows(inv,query,method);hit=[i for i,x in enumerate(w) if x['joined']==query]
 return {'opportunities':w,'hit_indices':hit,'N':len(w),'matches':len(hit),'binary':int(bool(hit)),'rate':F(len(hit),len(w)) if w else None}

def row_summary(pages,target,donors,method):
 targetscore=pages[target][method];leaves={}
 for leaf,fs in donors.items():
  supported=[pages[f][method]['rate'] for f in fs if pages[f][method]['N']]
  leaves[leaf]={'pages':fs,'binary':average([F(pages[f][method]['binary']) for f in fs]),'rate':average(supported),'N':sum(pages[f][method]['N'] for f in fs)}
 binary=average([x['binary'] for x in leaves.values()]);rates=[x['rate'] for x in leaves.values() if x['rate'] is not None];conditional=targetscore['N']>0 and len(rates)>=2
 return {'target':F(targetscore['binary']),'control':binary,'delta':F(targetscore['binary'])-binary if binary is not None else None,'target_rate':targetscore['rate'],'control_rate':average(rates),'conditional_delta':targetscore['rate']-average(rates) if conditional else None,'conditional_status':'supported' if conditional else ('target_zero_opportunities' if not targetscore['N'] else 'fewer_than_two_supported_control_leaves'),'conditional_leaf_count':len(rates),'leaves':leaves}

def union_summary(pages,target,donors,method):
 def page(f):
  a,b=pages[f]['exact']['binary'],pages[f][method]['binary'];return {'union':max(a,b),'gain':max(a,b)-a,'additional_occurrence':b}
 vals={f:page(f) for f in [target]+[f for fs in donors.values() for f in fs]};out={}
 for k in ('union','gain','additional_occurrence'):
  leaves={leaf:average([F(vals[f][k]) for f in fs]) for leaf,fs in donors.items()};control=average(list(leaves.values()));out[k]={'target':F(vals[target][k]),'control':control,'delta':F(vals[target][k])-control if control is not None else None,'leaves':leaves}
 return {'pages':vals,'summary':out}

def aggregate(rows,method,endpoint,group='source_leaf',union=False,unionendpoint=None):
 def value(r):return r['unions'][method]['summary'][unionendpoint][endpoint] if union else r['results'][method][endpoint]
 valid=[r for r in rows if value(r) is not None];groups=defaultdict(list)
 for r in valid:groups[r[group]].append(r)
 weights={r['pair_id']:F(1,len(groups)*len(rs)) for rs in groups.values() for r in rs}
 return {'value':average([average([value(r) for r in rs]) for rs in groups.values()]),'groups':{g:average([value(r) for r in rs]) for g,rs in groups.items()},'weights':weights,'included':[r['pair_id'] for r in valid],'excluded':[r['pair_id'] for r in rows if value(r) is None]}

def rebuild(raw,labels):
 queue=[r for r in labels['records'] if r['status']=='source_numbered_locator' and r['fragment_id']!=110];assert len(queue)==11
 out={}
 for version in ('ZL','IT'):
  pgs=raw[version]['pages'];meta={p['folio']:p for p in pgs}
  for boundary in ('strict_space','packet_tokens'):
   inventory,excluded=rebuild_inventory(pgs,boundary);rows=[]
   for q in queue:
    tokens=[w for loc in q['label_records'][version] for w in re.split('[.,]',re.sub('<[^>]*>','',loc['raw'])) if w];assert len(tokens)==1 and structural.units(tokens[0]);query=tokens[0]
    source,target=meta[q['pharma_folio']],meta[q['herbal_folio']];assert target['I']=='H' and target['H'] not in (None,'','?')
    donors=defaultdict(list)
    for pg in pgs:
     if pg['body'] and (pg['H'],pg['I'])==(target['H'],target['I']) and pg['leaf'] not in (source['leaf'],target['leaf']):donors[pg['leaf']].append(pg['folio'])
    fs=[target['folio']]+[f for bucket in donors.values() for f in bucket]
    scores={f:{m:score(inventory[f],query,m) for m in METHODS} for f in fs}
    for scorepage in scores.values():assert scorepage['adjacent_forward']['N']==scorepage['adjacent_reverse']['N']
    row={'pair_id':q['pair_id'],'fragment_id':q['fragment_id'],'query':query,'source_folio':source['folio'],'source_leaf':source['leaf'],'target_folio':target['folio'],'target_leaf':target['leaf'],'target_HI':[target['H'],target['I']],'donors':dict(donors),'pages':scores}
    row['results']={m:row_summary(scores,target['folio'],donors,m) for m in METHODS};row['unions']={m:union_summary(scores,target['folio'],donors,m) for m in METHODS};rows.append(row)
   summaries={m:{e:aggregate(rows,m,e) for e in ('target','control','delta','conditional_delta')} for m in METHODS}
   unions={m:{u:{e:aggregate(rows,m,e,union=True,unionendpoint=u) for e in ('target','control','delta')} for u in ('union','gain','additional_occurrence')} for m in METHODS}
   sensitivities={m:{group:{e:aggregate(rows,m,e,group=group) for e in ('target','control','delta','conditional_delta')} for group in ('pair_id','target_leaf')} for m in METHODS}
   out[version+'_'+boundary]={'rows':rows,'summary':summaries,'unions':unions,'sensitivities':sensitivities,'exclusions':excluded}
 return out

def numerical_toys():
 inv={'lines':[dict(structural.parse_raw('ab.cd.abcd.?.ab.cd'),locator='toy.1',source_line=1,uncertain_space=False)]}
 s={m:score(inv,'abcd',m) for m in METHODS}
 assert (s['exact']['N'],s['exact']['matches'])==(1,1)
 assert (s['adjacent_forward']['N'],s['adjacent_forward']['matches'])==(2,2)
 assert (s['adjacent_reverse']['N'],s['adjacent_reverse']['matches'])==(2,0)
 u=union_summary({'a':s},'a',{},'adjacent_forward')
 assert u['pages']['a']=={'union':1,'gain':0,'additional_occurrence':1}
 assert average([F(1,2),F(1,4)])==F(3,8)
 return ['complete_word_and_two_distinct_join_hits','reverse_same_opportunities','union_gain_distinct_from_additional_occurrence','exact_rational_mean']

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--execute-independent',action='store_true');args=a.parse_args()
 numerical_toys()
 if not args.execute_independent:print('Synthetic numerical tests passed; no real scoring.');raise SystemExit
 protocol=P/'protocol_v1.txt';assert protocol.exists(),'Final protocol required'
 output=P/'audit_rebuilt_v1.json.gz';assert not output.exists(),'Do not overwrite audit output'
 freeze={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'independent_implementation':'No primary scorer imported or read; prior studies and design motivation known.','files':{str(f):sha(f) for f in [Path(__file__),P/'audit_structure_core_frozen_v1.py',protocol,INPUT,LABELS]},'synthetic_tests':numerical_toys()}
 (P/'audit_numeric_freeze_v1.json').write_text(json.dumps(freeze,ensure_ascii=False,indent=2)+'\n')
 rebuilt=rebuild(read(INPUT),read(LABELS));output.write_bytes(gzip.compress(json.dumps(pack(rebuilt),ensure_ascii=False,separators=(',',':')).encode()))
 for f,h in freeze['files'].items():assert sha(f)==h
 print('Independent reconstruction saved',output)
