"""Assemble explicit manual review notes and verify preserved references.
This program does not assign role or sufficiency verdicts from source content.
"""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import hashlib,json
from manual_reviews_v1 import REVIEWS
HERE=Path(__file__).resolve().parent
BASE=HERE.parents[2]
ROOT=BASE.parents[3]
SOURCE=BASE/'block_role_ledger/circle_spatial_observer/report_v1.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def resolve(d,ptr):
 for k in ptr.strip('/').split('/'):
  k=k.replace('~1','/').replace('~0','~');d=d[int(k)] if isinstance(d,list) else d[k]
 return d

def main():
 assert not (HERE/'output_freeze_v1.json').exists(),'Frozen output exists'
 inf=read(HERE/'input_freeze_v1.json')
 for r in inf['files']:assert sha(ROOT/r['file'])==r['sha256'],r['file']
 addendum=read(HERE/'source_reference_addendum_v1.json');assert sha(ROOT/addendum['file'])==addendum['sha256']
 source=read(SOURCE);assert sha(SOURCE)=='cdde5039303e732bd5e5677722d9ec2153f6aad04fec6bfcafcd52f7d57db2cb'
 original_ids=[r['region_uid'] for r in source['rows']];assert len(original_ids)==112 and set(original_ids)==set(REVIEWS)
 sourcecache={};checks=0;rows=[]
 frozen_paths={r['file'] for r in inf['files']}|{addendum['file']}
 for i,orig in enumerate(source['rows']):
  uid=orig['region_uid'];decision,role_reason,scope_reason=REVIEWS[uid]
  assert decision in ['A','U','T','E']
  # Original source references are retained verbatim. Their first-coder scope
  # annotations are not silently promoted to this reviewer's endorsements.
  for ref in orig['source_refs']:
   assert ref['file'] in frozen_paths,ref['file']
   path=ROOT/ref['file'];assert sha(path)==ref['sha256']
   if ref['file'] not in sourcecache:sourcecache[ref['file']]=read(path)
   assert resolve(sourcecache[ref['file']],ref['json_pointer'])==ref['original_field_value'];checks+=1
  fields=['role_observed_present','role_candidates','writing_presence','whole_window_evidence_scope','primary_hypothesis_assessment','scope_justification','field_boundary_basis','NA_reasons','inscription_complete_in_window','conflicting_sources']
  coding_refs=[{'file':str(SOURCE.relative_to(ROOT)),'sha256':sha(SOURCE),'json_pointer':f'/rows/{i}/{key}','original_field_value':orig[key],'evidence_scope':'context_only','interpretive_use':'首稿具体断言，作为审查对象保留，不当作原图证据。'} for key in fields]
  role_verdict='uncertainty_handling_justified' if decision=='U' else 'supported_for_stated_broad_scope'
  extent_verdict='potentially_too_strict' if decision in ['T','E'] else 'justified_for_recorded_scope'
  h_verdict='potentially_too_strict_requires_adjudication' if decision=='T' else 'justified_for_recorded_scope'
  concerns=[]
  if decision in ['T','E']:concerns.append({'type':'possible_overrestriction','reason':scope_reason,'no_automatic_recoding':True})
  rows.append({'region_uid':uid,'panel':orig['panel'],'review_status':'reviewed','reviewer':'astronomical_site','first_observer':'circle_spatial_observer','original_coding_preserved':{key:orig[key] for key in fields},'original_box_xyxy':orig['original_box_xyxy'],'primary_proposition_domain':orig['primary_proposition_domain'],'role_review':{'verdict':role_verdict,'reason':role_reason,'operative_source_ref_indices':[0],'context_source_ref_indices':list(range(8,len(orig['source_refs'])))},'writing_presence_review':{'verdict':'uncertainty_correctly_not_treated_as_empty_truth' if decision=='U' else 'consistent_with_concrete_record_description','reason':role_reason,'operative_source_ref_indices':[0,1]},'whole_window_review':{'verdict':extent_verdict,'reason':scope_reason,'operative_source_ref_indices':[0],'context_source_ref_indices':list(range(8,len(orig['source_refs'])))},'H_review':{'verdict':h_verdict,'original_assessment':orig['primary_hypothesis_assessment'],'recommended_action':'retain_original_pending_root_extent_adjudication' if decision=='T' else 'retain_original_assessment','reason':scope_reason,'does_not_establish_complete_inscription_or_sequence':True},'potentially_too_strong':False,'potentially_too_strict':decision in ['T','E'],'unresolved_review_question':scope_reason if decision in ['T','E'] else None,'concerns':concerns,'source_refs':orig['source_refs'],'first_coding_source_refs':coding_refs,'source_scope_note':'source_refs retain first-coder evidence_scope/interpretive_use exactly for provenance. Review sufficiency is separately stated above; original annotations are not independent evidence.','no_new_image_or_text_matching':True})
 assert len(rows)==112 and [r['region_uid'] for r in rows]==original_ids
 for row in rows:
  for ref in row['first_coding_source_refs']:assert resolve(source,ref['json_pointer'])==ref['original_field_value'];checks+=1
 summary={'reviewed_rows':len(rows),'by_panel':dict(Counter(r['panel'] for r in rows)),'role_verdicts':dict(Counter(r['role_review']['verdict'] for r in rows)),'whole_window_verdicts':dict(Counter(r['whole_window_review']['verdict'] for r in rows)),'H_verdicts':dict(Counter(r['H_review']['verdict'] for r in rows)),'possible_overrestriction_ids':[r['region_uid'] for r in rows if r['potentially_too_strict']],'not_evaluated_ids':[],'exact_reference_checks':checks,'these_are_review_states_not_success_counts':True}
 result={'schema':'all_block_role_second_record_review_v1','reviewer':'astronomical_site','reviewed_observer':'circle_spatial_observer','utc':datetime.now(timezone.utc).isoformat(),'input_freeze_sha256':sha(HERE/'input_freeze_v1.json'),'source_reference_addendum_sha256':sha(HERE/'source_reference_addendum_v1.json'),'reviewed_report_file':str(SOURCE.relative_to(ROOT)),'reviewed_report_sha256':sha(SOURCE),'fixed_panels':inf['fixed_panels'],'rows':rows,'summary':summary,'review_interpretation':['All 112 IDs received manual role and scope/H review using their exact operative original fields. Hash checks are additional integrity checks, not scientific judgments.','Same AI and already exposed to own 97 codes and prior research material; not independent blind image rereading or external expert agreement.','Broad shared scene role does not require unique referent, complete inscription, resolved hand/glyph boundary, visible leader or historical common start.','Unresolved endpoint attribution alone is not an unresolved spatial field. Conversely an unobserved subregion cannot be filled from the clear center or surrounding rectangle.','Possible overrestriction flags on f72r2 ZO10/ZO11/ZO14 do not auto-upgrade NA: root should decide whether outward damage actually leaves a writing component outside recorded field scope.','f72r2 ZE04 flag concerns partial-window justification only; fixed-domain exclusion remains unchanged.','Source field weak contrast is not automatically uncertainty about spatial role; exact wording and stated extent were reviewed separately.','No other group new coding or root unfinalized reviews read; no new image, text matching, scores, web or Git work.','First report remains unchanged. This is not a vote or an adjudicated replacement; original sequence gate is unchanged.']}
 dump(HERE/'report_v1.json',result)
 lines=['circle组112项空间角色编码：第二记录审查 v1','审查者：astronomical_site；同AI且已知自身97项编码，非盲图像复读。','全部112项逐ID阅读具体原事实后手工审查；哈希核验不充当科学判断。','首稿原判断不覆盖；本审查不是投票。','清单：'+json.dumps(summary,ensure_ascii=False),'']
 for r in rows:
  lines += [r['region_uid'],'宽角色：'+r['role_review']['verdict']+'；'+r['role_review']['reason'],'全框：'+r['whole_window_review']['verdict']+'；'+r['whole_window_review']['reason'],'H：原值 '+r['H_review']['original_assessment']+'；复核 '+r['H_review']['verdict'],'原字段依据：'+json.dumps(r['source_refs'][0]['original_field_value'],ensure_ascii=False),'精确文件/SHA/指针与上下文原值见JSON source_refs；首稿断言见first_coding_source_refs。','']
 (HERE/'report_v1.txt').write_text('\n'.join(lines)+'\n')
 files=[HERE/n for n in ['input_freeze_v1.json','source_reference_addendum_v1.json','manual_reviews_v1.py','assemble_review_v1.py','report_v1.json','report_v1.txt']]
 out={'schema':'all_block_role_second_record_review_output_freeze_v1','reviewer':'astronomical_site','reviewed_observer':'circle_spatial_observer','utc':datetime.now(timezone.utc).isoformat(),'input_freeze_sha256':sha(HERE/'input_freeze_v1.json'),'reviewed_report_sha256':sha(SOURCE),'files':[{'path':p.name,'sha256':sha(p),'bytes':p.stat().st_size} for p in files],'fixed_rows':112,'all_reviewed':True,'source_report_modified':False,'new_image_observation':False,'independent_blind_review':False,'root_adjudication_required':True,'old_sequence_gate_changed':False}
 dump(HERE/'output_freeze_v1.json',out)
 print(json.dumps(summary,ensure_ascii=False));print('report SHA',sha(HERE/'report_v1.json'));print('freeze SHA',sha(HERE/'output_freeze_v1.json'))
if __name__=='__main__':main()
