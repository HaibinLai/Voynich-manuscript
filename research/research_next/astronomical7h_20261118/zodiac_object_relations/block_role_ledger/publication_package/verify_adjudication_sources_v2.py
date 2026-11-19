#!/usr/bin/env python3
"""Read-only fixed-scope and exact citation checks; no scientific judgment."""
from pathlib import Path
import hashlib,json,sys
D=Path(__file__).resolve().parent;R=D.parents[5];L=D.parent;A=L/'root_adjudication'
cache={};checks=0;errors=[];refs_count=0;exact_count=0

def read(p):
 p=p.resolve()
 if p not in cache:
  b=p.read_bytes();cache[p]=(json.loads(b),hashlib.sha256(b).hexdigest())
 return cache[p]
def canon(o):return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def check(ok,label):
 global checks
 checks+=1
 if not ok:errors.append(label)
def ptr(o,s):
 if s=='':return o
 if not s.startswith('/'):raise ValueError('non-JSON pointer')
 for t in s[1:].split('/'):
  t=t.replace('~1','/').replace('~0','~');o=o[int(t)] if isinstance(o,list) else o[t]
 return o

def walk(o,label):
 global refs_count,exact_count
 if isinstance(o,dict):
  if all(k in o for k in ['file','sha256','json_pointer']):
   refs_count+=1
   try:
    data,h=read(R/o['file']);check(h==o['sha256'],label+':hash')
    value=ptr(data,o['json_pointer']);check(True,label+':pointer')
    if 'original_field_value' in o:
     exact_count+=1;check(canon(value)==canon(o['original_field_value']),label+':value')
   except Exception as e:check(False,label+':'+type(e).__name__)
  for k,v in o.items():walk(v,label+'/'+k)
 elif isinstance(o,list):
  for i,v in enumerate(o):walk(v,label+'/'+str(i))

report,h=read(A/'report_v1.json');check(h=='5ec01d6e00362fcf2d7e61a72c8b7362c0a7968835b9f536c809678b3e477a2c','frozen-target-hash')
selected,_=read(L/'structural_audit/selected_structural_versions_v1.json');original={}
for f in selected['selected_reports']:
 data,h=read(R/f['path']);check(h==f['sha256'],'selected-report-hash:'+f['group'])
 for row in data['rows']:
  check(row['region_uid'] not in original,'unique-original:'+row['region_uid']);original[row['region_uid']]=row
ids=[r['region_uid'] for r in report['rows']];check(len(ids)==322,'322-rows');check(len(set(ids))==322,'322-unique');check(set(ids)==set(original),'fixed-full-ID-coverage')
for row in report['rows']:
 uid=row['region_uid'];old=original[uid]
 for k in ['panel','canvas_id','original_box_xyxy','original_band','primary_proposition_domain','source_refs']:
  check(canon(row[k])==canon(old[k]),uid+':preserved-'+k)
 for k,v in row['original_scientific_record'].items():check(k in old and canon(v)==canon(old[k]),uid+':original-record-'+k)
 s=row['selected_coding_source'];obj,_=read(R/s['file']);check(canon(ptr(obj,s['json_pointer']))==canon(old),uid+':selected-full-row')
 for s in [row['review_source']]:
  obj,_=read(R/s['file']);check(ptr(obj,s['json_pointer'])['region_uid']==uid,uid+':cross-review-ID')
 # Do not validate the reason as a scientific proposition or replace decision_record.
walk(report,'report')
work,_=read(A/'working_decisions_v1.json');batchids=[u for b in work['reviewed_batches'] for u in b['explicitly_reviewed_ids']]
rootreview,_=read(L/'cross_reviews/root_reviews_literature/report_v1.json');rootids=[r['region_uid'] for r in rootreview['reviewed_rows']]
check(len(batchids)==209 and len(set(batchids))==209,'209-recorded-batch-ID-coverage');check(len(rootids)==113 and len(set(rootids))==113,'113-recorded-review-ID-coverage');check(not set(batchids)&set(rootids),'coverage-disjoint');check(set(batchids)|set(rootids)==set(ids),'coverage-union')
for b in work['reviewed_batches']:
 obj,h=read(R/b['source_review_file']);check(h==b['source_review_sha256'],'batch-source-hash')
 check(set(b['explicitly_reviewed_ids'])<=set(r['region_uid'] for r in obj['rows']),'batch-IDs-in-source')
for fn,field in [('input_freeze_v1.json','files'),('output_freeze_v1.json','outputs')]:
 f,_=read(A/fn)
 for x in f[field]:
  p=R/x['file'];check(hashlib.sha256(p.read_bytes()).hexdigest()==x['sha256'],fn+':'+x['file'])
result={'schema':'root_adjudication_source_check_v2','all_pass':not errors,'checks':checks,'errors':errors,'reference_records_checked':refs_count,'exact_values_checked':exact_count,'fixed_unique_IDs':len(set(ids)),'recorded_review_coverage_only':{'batch_IDs':len(set(batchids)),'root_individual_IDs':len(set(rootids))},'sources':[{'file':str(p.relative_to(R)),'sha256':x[1]} for p,x in sorted(cache.items())],'scope':'Exact records, IDs, references and freeze bindings only. Does not independently establish actual review attention or scientific validity. Author is an original coder. All judgments/disagreements remain frozen and unaltered.','publication_state_preserved':report['publication_state']}
print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(1 if errors else 0)
