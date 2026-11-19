"""Assemble explicitly reviewed per-ID decisions; no role classifier or vote."""
import copy,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[5]
B=HERE.parent

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ref(p,pointer=''):return {'file':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'json_pointer':pointer}
def main():
 frozen=read(HERE/'input_freeze_v1.json')
 for x in frozen['files']:assert sha(ROOT/x['file'])==x['sha256'],x['file']
 manual=read(HERE/'manual_scope_decisions_v1.json'); mf=read(HERE/'manual_scope_decisions_freeze_v1.json')
 assert sha(HERE/'manual_scope_decisions_v1.json')==mf['sha256']
 special={r['region_uid']:r for r in manual['decisions']};assert len(special)==8
 selected=read(B/'structural_audit/selected_structural_versions_v1.json')
 reviews={};rfiles={'circle_spatial_observer':('site_reviews_circle','rows'),'astronomical_site':('literature_reviews_site','rows'),'literature':('root_reviews_literature','reviewed_rows')}
 for observer,(folder,key) in rfiles.items():
  p=B/'cross_reviews'/folder/'report_v1.json';d=read(p)
  for i,r in enumerate(d[key]):
   uid=r['region_uid'];assert uid not in reviews
   reviews[uid]={'review_id':folder+':'+uid,'source':ref(p,f'/{key}/{i}'),'record':r,'observer':observer}
 assert len(reviews)==322
 work=read(HERE/'working_decisions_v1.json');assert work['remaining_209']==0
 batches={}
 for i,batch in enumerate(work['reviewed_batches']):
  p=ROOT/batch['source_review_file'];assert sha(p)==batch['source_review_sha256']
  for uid in batch['explicitly_reviewed_ids']:assert uid not in batches;batches[uid]=i
 assert len(batches)==209
 lit=read(B/'cross_reviews/root_reviews_literature/report_v1.json')
 assert len(lit['reviewed_rows'])==113 and lit['remaining_not_reviewed']==0
 assert set(batches).isdisjoint({r['region_uid'] for r in lit['reviewed_rows']})
 fields=['assessment_status','whole_window_evidence_scope','writing_presence','role_observed_present','role_candidates','mixed_roles_observed','field_boundary_basis','scope_justification','inscription_complete_in_window','clipped_or_continuing_sides','conflicting_sources','primary_hypothesis_assessment','NA_reasons','uncertainty_placeholders']
 rows=[]
 for s in selected['selected_reports']:
  p=ROOT/s['path'];assert sha(p)==s['sha256'];version=s['group']+':'+p.stem.removeprefix('report_')
  for i,r in enumerate(read(p)['rows']):
   uid=r['region_uid'];review=reviews[uid];assert review['observer']==s['group']
   decision={k:copy.deepcopy(r[k]) for k in fields if k in r};chg=special.get(uid)
   source=ref(p,f'/rows/{i}');basis=[source,review['source']]
   rootreview=ref(HERE/'working_decisions_v1.json',f"/reviewed_batches/{batches[uid]}") if uid in batches else review['source']
   action='retain_original_scientific_values_after_full_review'
   reason='根逐条阅读原具体空间事实与复核理由，接受其声明范围；见绑定的逐项/面板复核记录。'
   retained_limits=[]
   if chg:
    action=chg['decision'];reason=chg['reason'];retained_limits=[chg['unchanged_limit']]
    decision['whole_window_evidence_scope']=chg['final_scope'];decision['primary_hypothesis_assessment']=chg['final_H']
    if action=='revise_scope_for_recorded_group':
     decision.update(assessment_status='record_reviewed',NA_reasons=[],role_candidates=[],mixed_roles_observed=False,scope_justification=reason)
     decision['field_boundary_basis']=[{'description':reason,'source_ref_indices':[j for j,x in enumerate(r['source_refs']) if 'observation_facts' in x['json_pointer'] or 'candidate_constraints' in x['json_pointer']]}]
    basis.append(ref(HERE/'manual_scope_decisions_v1.json',f"/decisions/{manual['decisions'].index(chg)}"))
   changed=[k for k in fields if decision.get(k)!=r.get(k)]
   rows.append({'region_uid':uid,'panel':r['panel'],'canvas_id':r['canvas_id'],'original_box_xyxy':r['original_box_xyxy'],'original_band':r['original_band'],'primary_proposition_domain':r['primary_proposition_domain'],'selected_coding_version':version,'selected_coding_source':source,'original_scientific_record':{k:copy.deepcopy(r[k]) for k in fields if k in r},'review_id':review['review_id'],'review_source':review['source'],'root_review_source':rootreview,'decision':action,'decision_record':decision,'reason':reason,'changed_fields':changed,'source_basis':basis,'source_refs':r['source_refs'],'retained_limits':retained_limits,'unresolved_cross_review_difference':uid=='f72r2:ZE04'})
 assert len(rows)==322 and len({r['region_uid'] for r in rows})==322
 # Validate every exact source reference without treating that as scientific certification.
 checks=0;cache={}
 for r in rows:
  for s in r['source_refs']:
   path=ROOT/s['file']
   if path not in cache:cache[path]=(sha(path),read(path))
   digest,obj=cache[path];assert digest==s['sha256']
   v=obj
   for part in s['json_pointer'].strip('/').split('/'):
    part=part.replace('~1','/').replace('~0','~');v=v[int(part)] if isinstance(v,list) else v[part]
   assert v==s['original_field_value'];checks+=1
 assert checks==2726
 result={'schema':'all322_root_role_adjudication_v1','input_freeze':ref(HERE/'input_freeze_v1.json'),'manual_decisions_freeze':ref(HERE/'manual_scope_decisions_freeze_v1.json'),'fixed_scope':322,'root_review_coverage':{'direct_individual_literature':113,'remaining_original_facts_and_cross_reviews':209,'missing':0},'selected_structural_versions':ref(B/'structural_audit/selected_structural_versions_v1.json'),'rows':rows,'inventory_only':{'retained_scientific_values':sum(not x['changed_fields'] for x in rows),'scope_revisions':sum(bool(x['changed_fields']) for x in rows),'unresolved_cross_review_differences':['f72r2:ZE04'],'exact_source_reference_checks':checks},'limits':['Informed same-AI record-level reinterpretation, not independent blind image replication.','All original v1 scientific judgments, representation-only corrections and cross-review disagreements remain separate.','Whole fixed window means recorded component scope, not complete inscription, exact ink segmentation or unique object ownership.','Known continuous-course counterexamples remain in the original fixed domain; broad spatial roles do not certify a complete cross-panel target sequence.','No semantic, language, decipherment, significance, matching-score or historical read-order claim.'],'publication_state':'PENDING_ADVERSARIAL_REVIEW_AND_PUBLICATION_APPROVAL'}
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
