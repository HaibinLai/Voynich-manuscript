#!/usr/bin/env python3
"""Read-only source/coverage verification, not scientific adjudication."""
from pathlib import Path
import hashlib,json,sys
D=Path(__file__).resolve().parent
R=D.parents[5]
L=D.parent
checks=[]; errors=[]; used={}; ref_count=0; exact_count=0

def canon(o):return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def check(ok,label):
 checks.append(label)
 if not ok:errors.append(label)
def read(p):
 p=p.resolve();rel=str(p.relative_to(R));data=p.read_bytes();h=hashlib.sha256(data).hexdigest();used[rel]=h
 return json.loads(data),h

def pointer(o,s):
 if s=='':return o
 if not s.startswith('/'):raise ValueError('bad pointer')
 for a in s[1:].split('/'):
  a=a.replace('~1','/').replace('~0','~');o=o[int(a)] if isinstance(o,list) else o[a]
 return o

def refs(o,label):
 global ref_count,exact_count
 if isinstance(o,dict):
  if all(k in o for k in ['file','sha256','json_pointer']):
   ref_count+=1
   try:
    p=R/o['file'];value,h=read(p)
    check(h==o['sha256'],label+':hash')
    v=pointer(value,o['json_pointer']);check(True,label+':pointer')
    if 'original_field_value' in o:
     exact_count+=1;check(canon(v)==canon(o['original_field_value']),label+':exact-value')
   except Exception as e:check(False,label+':source-error:'+type(e).__name__)
  for k,v in o.items():refs(v,label+'/'+k)
 elif isinstance(o,list):
  for i,v in enumerate(o):refs(v,label+'/'+str(i))

summary=[]
for group,subject,key,n in [('root_reviews_literature','literature','reviewed_rows',113),('site_reviews_circle','circle_spatial_observer','rows',112),('literature_reviews_site','astronomical_site','rows',97)]:
 report,h=read(L/'cross_reviews'/group/'report_v1.json')
 original,_=read(L/subject/'report_v1.json')
 rows=report[key];originals={r['region_uid']:r for r in original['rows']};ids=[r['region_uid'] for r in rows]
 check(len(rows)==n,group+':count');check(len(set(ids))==n,group+':unique');check(set(ids)==set(originals),group+':all-original-IDs')
 before=ref_count
 for row in rows:
  uid=row['region_uid'];old=originals[uid]
  if group=='root_reviews_literature':
   check(canon(row['original_coding_role'])==canon(old['role_observed_present']),uid+':original-role')
   check(canon(row['original_H'])==canon(old['primary_hypothesis_assessment']),uid+':original-H')
  refs(row,group+'/'+uid)
 g=L/'cross_reviews'/group
 for fn in ['input_freeze_v1.json','output_freeze_v1.json']:
  f,fh=read(g/fn)
  if fn=='input_freeze_v1.json':check(report['input_freeze_sha256']==fh,group+':input-freeze-binding')
  for x in f.get('files',f.get('outputs',f.get('source_files',[]))):
   s=x.get('path',x.get('file'));p=R/s if s.startswith(('research/','site/')) else g/s
   data=p.read_bytes();rel=str(p.resolve().relative_to(R));actual=hashlib.sha256(data).hexdigest();used[rel]=actual
   check(actual==x['sha256'],group+':freeze-file:'+rel)
 summary.append({'review':group,'subject_original_version':'v1','unique_IDs':len(set(ids)),'reference_records_checked':ref_count-before,'scientific_verdicts_reassessed':False})
result={'schema':'cross_review_source_package_check_v1','participant_disclosure':'Author is circle original coder; this is implementation/source/coverage checking only, not a new scientific review or independent expert consensus.','checks':len(checks),'errors':errors,'all_pass':not errors,'reference_records_checked':ref_count,'exact_original_field_values_checked':exact_count,'groups':summary,'sources':[{'file':k,'sha256':v} for k,v in sorted(used.items())],'root_113_scientific_disputes':'Preserved verbatim in original report; not resolved by this check.','no_final_merged_totals':True}
print(json.dumps(result,ensure_ascii=False,indent=2))
sys.exit(1 if errors else 0)
