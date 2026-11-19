#!/usr/bin/env python3
"""Read-only preclose document/source checks; not scientific or final acceptance."""
from pathlib import Path
import hashlib,json,sys
D=Path(__file__).resolve().parent;R=D.parents[3];B=D.parent
checks=0;errors=[]
def get(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def check(ok,label):
 global checks
 checks+=1
 if not ok:errors.append(label)
def exact(a,b):return json.dumps(a,ensure_ascii=False,sort_keys=True)==json.dumps(b,ensure_ascii=False,sort_keys=True)
r=get(D/'requirements_preclose_v1.json');old=get(B/'requirements_audit_draft/requirements_audit_draft_v1.json')
check(len(r['requirements'])==37,'all37-original-requirements');check([x['id'] for x in r['requirements']]==[x['id'] for x in old['requirements']],'original-ID-order')
for x,y in zip(r['requirements'],old['requirements']):
 for k in ['complete_requirement','expected_evidence','source_requirement_sections']:
  check(exact(x[k],y[k]),x['id']+':unchanged-'+k)
for x in r['requirements']+r['later_explicit_requirements']:
 check(bool(x['actual_evidence']),x['id']+':has-evidence')
 for e in x['actual_evidence']:
  check(sha(R/e['path'])==e['sha256'],x['id']+':hash:'+e['path'])
for fn in ['input_freeze_v1.json','evidence_input_freeze_v1.json','evidence_addendum_freeze_v1.json']:
 for e in get(D/fn)['files']:
  path=e.get('path',e.get('file'));check(sha(R/path)==e['sha256'],fn+':'+path)
for id in ['R07','R08','R09','R14','R24']:
 x=next(x for x in r['requirements'] if x['id']==id)
 check(x['status']=='过弱',id+':scientific-gate-not-promoted')
 check(bool(x['stop_branch_assessment']),id+':separate-stop-branch')
check(r['final_acceptance'] is False and r['overall_goal_complete'] is False,'not-final-or-goal-complete')
check(r['window_endpoint_utc']=='2026-11-18T23:14:17Z','exact-authoritative-endpoint')
f=get(B/'f67_measurement_tables/tables_v1.json')
for k in ['fixed_targets','A_working_graphical_roles','B_transcription_eligibility','C_geometric_order_and_boundary_evidence']:check(len(f[k])==12,'f67-full12:'+k)
check(len(f['all_74_context_loci_original'])==74,'f67-full74-context')
check(f['gate']=='NOT_READY_FOR_COMPLETE_TWELVE_TEXT_SCORING','f67-original-gate')
a=get(B/'zodiac_object_relations/aggregation_v1.json')
for k,n in [('text_records_retained',322),('original_components_retained',606),('original_fine_alternative_units_retained',358),('not_reviewed_or_in_progress',0)]:check(a['totals'][k]==n,'all12-record-coverage:'+k)
check(len(a['panels'])==12 and not a['pending_panels'],'all12-formal-panels')
# Saved live receipts establish only their historical recorded versions.
live=get(B/'publication/live_acceptance_v10.json');ap=B/'zodiac_object_relations/aggregation_v1.json'
check(any(x['url'].endswith('/downloads/zodiac-relations/aggregation.json') and x['sha256']==sha(ap) and x['status']==200 for x in live['checked_files']),'v10-saved-online-exact-aggregate')
ids=[]
L=B/'zodiac_object_relations/block_role_ledger'
for g,n in [('circle_spatial_observer',112),('literature',113),('astronomical_site',97)]:
 d=get(L/g/'report_v1.json');check(len(d['rows'])==n,g+':original-rows');ids += [x['region_uid'] for x in d['rows']]
check(len(ids)==len(set(ids))==322,'role-original322-unique')
challenge=get(L/'cross_reviews/literature_challenges_root_scope/report_v1.json');check(len(challenge['rows'])==8 and len({x['region_uid'] for x in challenge['rows']})==8,'eight-challenge-records')
result={'schema':'preclose_source_validation_v1','checks':checks,'errors':errors,'all_pass':not errors,'original_requirements_unchanged':True,'saved_file_checks_not_live_browser':True,'new_scientific_judgment_or_old_scores_reperformed':False,'final_acceptance':False,'original_evidence_sha_drift':get(D/'evidence_input_freeze_v1.json')['old_reference_hash_changes']}
print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(1 if errors else 0)
