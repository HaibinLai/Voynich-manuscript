"""Serialization and exact-source checks only. All scientific choices are the
explicit per-ID tuples in manual_coding_v1.NOTES; no text/band classifier.
"""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import hashlib,json
from manual_coding_v1 import NOTES
HERE=Path(__file__).resolve().parent
BASE=HERE.parent.parent
ROOT=BASE.parents[3]
PANELS=['f71v','f72r1','f72r3','f72v1']
ROLE={'A':'annular_figure_field_short_writing','C':'central_scene_annotation_field','M':'page_margin_writing_field','U':None}
UNCERTAIN_CANDIDATES={'f72r3:ZU01':['annular_figure_field_short_writing','unresolved_writing_or_graphic'],'f72v1:ZE02':['page_margin_writing_field','unresolved_writing_or_graphic']}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def pointer(d,p):
 for bit in p.strip('/').split('/'):
  bit=bit.replace('~1','/').replace('~0','~');d=d[int(bit)] if isinstance(d,list) else d[bit]
 return d

def main():
 assert not (HERE/'output_freeze_v1.json').exists(),'Already frozen'
 freeze=read(HERE/'input_freeze_v1.json')
 for ref in freeze['files']:assert sha(ROOT/ref['file'])==ref['sha256'],ref['file']
 clarification=HERE.parent/'empty_or_uncertain_window_clarification_v1.txt';cf=HERE.parent/'clarification_freeze_v1.json'
 assert sha(clarification)==read(cf)['files'][0]['sha256']
 aggregation_path=BASE/'aggregation_v1.json';a=read(aggregation_path);schema=read(BASE/'role_contract_review/record_schema_proposal_v1.json')
 template=read(BASE/'role_contract_review/all322_contract_roster_template_v1.json');templates={r['region_uid']:r for r in template['rows'] if r['panel'] in PANELS}
 assert len(NOTES)==len(templates)==97 and set(NOTES)==set(templates)
 rows=[];contexts=[];source_cache={str(aggregation_path.relative_to(ROOT)):a};checks=0
 def ref(path,ptr,scope,use):
  nonlocal checks
  relative=str(path.relative_to(ROOT))
  if relative not in source_cache:source_cache[relative]=read(path)
  value=pointer(source_cache[relative],ptr);checks+=1
  return {'file':relative,'sha256':sha(path),'json_pointer':ptr,'original_field_value':value,'evidence_scope':scope,'interpretive_use':use}
 for panel in PANELS:
  pi=next(i for i,p in enumerate(a['panels']) if p['panel']==panel);ap=a['panels'][pi];seed=ap['full_original_seed'];rp=BASE/ap['report_path'];report=read(rp)
  assert sha(rp)==ap['report_sha256'] and report==ap['full_frozen_report']
  assert len(report['text_records']) in [16,32,33]
  contexts.append({'panel':panel,'original_object_components_context_only':seed['object_components'],'original_fine_alternatives_context_only':seed['fine_alternatives_original'],'original_ring_context':seed['continuous_ring_writing_original'],'source_file':str(aggregation_path.relative_to(ROOT)),'source_sha256':sha(aggregation_path),'source_json_pointer':f'/panels/{pi}/full_original_seed','limits':'Context only; not extra opportunities and not a role classifier. No new geometry or overlap calculation.'})
  for i,obs in enumerate(report['text_records']):
   uid=obs['region_uid'];code,scope,hyp,basis,justification=NOTES[uid];t=templates[uid]
   si=next(i for i,s in enumerate(seed['text_records']) if s['region_uid']==uid);original=seed['text_records'][si]
   assert t['original_box_xyxy']==original['original_box_xyxy'] and t['original_band']==original['ring_assignment_original']
   assert (hyp=='not_in_predeclared_domain')==(t['primary_proposition_domain'] is False)
   uncertain=code=='U';partial=scope!='full_window'
   refs=[ref(rp,f'/text_records/{i}/observation_facts',scope,basis),ref(rp,f'/text_records/{i}/candidate_constraints','context_only','保留局部边界及对象解释限制；其中无引线/多候选本身不作为NA原因。'),ref(rp,f'/text_records/{i}/subgroup_candidates','context_only','完整保留原分组备选，不取最佳子组也不增加机会数。'),ref(rp,f'/text_records/{i}/candidate_object_ids','context_only','原冻结候选列表仅作上下文，不按数量/距离生成角色。'),ref(aggregation_path,f'/panels/{pi}/full_original_seed/text_records/{si}','context_only','精确保留原编号、原框、band和来源记录；这些元数据不充当角色结论。')]
   fine=[f for f in seed['fine_alternatives_original'] if f.get('coarse_parent_id')==original['original_id']]
   for fi,f in enumerate(seed['fine_alternatives_original']):
    if f.get('coarse_parent_id')==original['original_id']:refs.append(ref(aggregation_path,f'/panels/{pi}/full_original_seed/fine_alternatives_original/{fi}','context_only','原父ID对应的细分备选完整保留，不替换固定父窗。'))
   row={
    'region_uid':uid,'panel':panel,'canvas_id':t['canvas_id'],'roster_class':t['roster_class'],'primary_proposition_domain':t['primary_proposition_domain'],
    'original_box_xyxy':original['original_box_xyxy'],'original_band':original['ring_assignment_original'],
    'assessment_status':'record_reviewed_NA' if uncertain or hyp=='NA' else 'record_reviewed',
    'whole_window_evidence_scope':scope,'writing_presence':'uncertain' if uncertain else 'writing_like_supported',
    'role_observed_present':[] if uncertain else [ROLE[code]],
    'role_candidates':UNCERTAIN_CANDIDATES[uid] if uncertain else (['unresolved_writing_or_graphic'] if partial else []),
    'mixed_roles_observed':None if uncertain or partial else False,
    'field_boundary_basis':[{'description':basis,'source_ref_indices':[0,1]}],
    'inscription_complete_in_window':'not_assessed','clipped_or_continuing_sides':'unknown',
    'full_block_grouping_notes':{'original_fine_alternatives':fine,'frozen_report_subgroup_candidates':obs['subgroup_candidates'],'retention':'All original alternatives retained; none selected as parent replacement. Full window is a sampling unit, not a certified complete inscription.'},
    'candidate_object_ids_context_only':obs['candidate_object_ids'],
    'original_seed_record_context_only':original,
    'source_refs':refs,'conflicting_sources':[],
    'primary_hypothesis_assessment':hyp,
    'NA_reasons':['writing_graphic_uncertain'] if uncertain else (['partial_window_record','field_boundary_unresolved'] if partial else []),
    'scope_justification':justification,
    'shared_ink_or_overlap_dependency':{'status':'not_assessed','known_other_original_ids':[],'limits':'No new geometric intersection or shared-ink inference. Shared physical leaf and original windows are not independent word/object trials.'},
    'source_conflict_review_scope':'Only listed frozen observation and context fields used for this record-level interpretation. Different candidate objects are preserved alternatives, not a source vote. No new image or peer-role judgment consulted.'}
   for field,allowed in schema['required_fields'].items():
    assert field in row,(uid,field)
    if isinstance(allowed,list) and field!='NA_reasons':assert row[field] in allowed,(uid,field)
   assert set(row['NA_reasons'])<=set(schema['required_fields']['NA_reasons'])
   assert row['candidate_object_ids_context_only']==obs['candidate_object_ids']
   if hyp=='supported_for_stated_scope':assert scope=='full_window' and row['writing_presence']=='writing_like_supported' and row['role_observed_present']==[ROLE['A']]
   if uncertain:assert not row['role_observed_present'] and hyp!='supported_for_stated_scope'
   if partial:assert hyp=='NA'
   rows.append(row)
 assert [r['region_uid'] for r in rows]==[r['region_uid'] for r in template['rows'] if r['panel'] in PANELS]
 for row in rows:
  for r in row['source_refs']:
   assert sha(ROOT/r['file'])==r['sha256'];assert pointer(source_cache[r['file']],r['json_pointer'])==r['original_field_value'];checks+=1
 result={'schema':'block_role_observer_report_v1','observer_id':'astronomical_site','created_utc':datetime.now(timezone.utc).isoformat(),'input_freeze_sha256':sha(HERE/'input_freeze_v1.json'),'fixed_panel_order':PANELS,'rows':rows,'panel_contexts':contexts,'execution_clarifications':[{'file':str(p.relative_to(ROOT)),'sha256':sha(p),'timing':'Received during manual coding; original input freeze not overwritten.'} for p in [clarification,cf]],'summary':{'fixed_rows':len(rows),'by_panel':dict(Counter(r['panel'] for r in rows)),'assessment_status':dict(Counter(r['assessment_status'] for r in rows)),'whole_window_scope':dict(Counter(r['whole_window_evidence_scope'] for r in rows)),'primary_hypothesis_assessment':dict(Counter(r['primary_hypothesis_assessment'] for r in rows)),'exact_source_reference_checks':checks},'limits':['Manual second coding of already exposed records, not blind image review; no new images viewed.','Only these four assigned panels. Other observers new block-role codes were not read.','Program only assembled manual per-ID choices and validated sources/retention; no keyword, band, distance, count or text classifier.','Original band determines fixed proposition domain only, never role observed.','The complete sampling window is not a complete inscription; inscription completeness not assessed.','Broad role support and whole-window hypothesis NA are separate. Unresolved writing/graphic is a placeholder, not a positive writing-role success.','No ratios, p-values, textual matching, phase matching, naming, historical identity or sequence qualification produced.','All original sequence gates unchanged; root review required before aggregation/release.']}
 dump(HERE/'report_v1.json',result)
 lines=['本代理四图固定块空间角色登记 v1','范围：f71v / f72r1 / f72r3 / f72v1，全部97原ID。','这是已曝光旧观察记录的二次手工编码；没有新看图、文本匹配或完整序列资格变更。','执行中收到空窗/未定口径澄清，另列哈希，原输入冻结不改。','完整固定窗口不等于完整铭文；铭文完整性本组均not_assessed。','汇总仅用于清单完整性，不是成功率：'+json.dumps(result['summary'],ensure_ascii=False),'']
 for r in rows:
  lines.extend([r['region_uid']+' | '+r['assessment_status']+' | '+','.join(r['role_observed_present'] or ['未建立确定书写角色'])+' | H='+r['primary_hypothesis_assessment'],'范围：'+r['whole_window_evidence_scope']+'；'+r['scope_justification'],'具体场界：'+r['field_boundary_basis'][0]['description'],'NA依据：'+(','.join(r['NA_reasons']) or '无；域外项不是伪造阴性'),'原事实：'+json.dumps(r['source_refs'][0]['original_field_value'],ensure_ascii=False),'原限制：'+json.dumps(r['source_refs'][1]['original_field_value'],ensure_ascii=False),'精确文件/SHA/指针/原值及完整细分见JSON source_refs。',''])
 (HERE/'report_v1.txt').write_text('\n'.join(lines)+'\n')
 files=[HERE/n for n in ['input_freeze_v1.json','manual_coding_v1.py','assemble_report_v1.py','report_v1.json','report_v1.txt']]
 out={'schema':'block_role_observer_output_freeze_v1','observer_id':'astronomical_site','utc':datetime.now(timezone.utc).isoformat(),'input_freeze_sha256':sha(HERE/'input_freeze_v1.json'),'files':[{'path':p.name,'sha256':sha(p),'bytes':p.stat().st_size} for p in files],'rows':97,'all_fixed_ids_retained':True,'manual_per_ID_coding':True,'new_image_observations':False,'peer_new_codings_read':False,'root_review_required':True,'original_sequence_gate_unchanged':True}
 dump(HERE/'output_freeze_v1.json',out);print(json.dumps(result['summary'],ensure_ascii=False));print('report',sha(HERE/'report_v1.json'));print('freeze',sha(HERE/'output_freeze_v1.json'))
if __name__=='__main__':main()
