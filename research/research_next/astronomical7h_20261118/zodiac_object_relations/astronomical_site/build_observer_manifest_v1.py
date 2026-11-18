"""Explicit own-panel manifest; integrity checks only, no new image judgments."""
from record_helpers import *
from collections import Counter
import jsonschema
PANELS=['f71v','f72r1','f72r3','f72v1']
EXTRA=['assigned_seed_records_v1.json','prepare_views.py','record_helpers.py','freeze_panel.py','author_text_records_v1.py','f71v_text_notes_v1.py','f71v_inner_notes_v1.py','f71v_component_notes_v1.py','f72r1_text_notes_v1.py','f72r1_component_notes_v1.py','f72r1_context_notes_v1.py','f72r3_outer_notes_v1.py','f72r3_middle_notes_v1.py','f72r3_inner_notes_v1.py','f72r3_component_notes_v1.py','f72r3_unresolved_components_v1.py','f72r3_auxiliary_paths_v1.py','f72r3_context_notes_v1.py','f72r3_extra_views_v1.py','f72r3_view_plan_addendum_v1.json','f72v1_outer_notes_v1.py','f72v1_inner_notes_v1.py','f72v1_component_notes_v1.py','f72v1_competition_notes_v1.py','f72v1_context_notes_v1.py','f72v1_extra_views_v1.py','f72v1_view_plan_addendum_v1.json','build_observer_manifest_v1.py']
repo=SOURCE.parents[3]
def file_record(p):return {'path':str(p.relative_to(repo)),'sha256':sha(p),'bytes':p.stat().st_size}
def counts(rs,k):return dict(sorted(Counter(r.get(k) for r in rs).items(),key=lambda x:str(x[0])))
manifest=HERE/'observer_manifest_v1.json';assert not manifest.exists(),'Frozen manifest exists; do not overwrite.'
records=[];files=[]
for panel in PANELS:
 d=read(HERE/f'{panel}_relations_v1.json');s=seed(panel);f=read(HERE/f'{panel}_freeze_v1.json');v=read(HERE/f'{panel}_verification_v1.json')
 jsonschema.validate(d,read(SOURCE/'schema_v1.json'))
 assert d['input_freeze_sha256']=='71e3d951eb9ec6117bf679dab20f0500e48ad0a0eacaf6fd39365a45f071ed5d'
 for r in f['files']:
  p=HERE/r['path'];assert sha(p)==r['sha256'] and p.stat().st_size==r['bytes'],p
 views={r['view_id'] for r in d['view_receipts']};segments={r['segment_uid'] for r in d['line_segments']};components={r['component_uid'] for r in d['object_component_reviews']};text={r['region_uid'] for r in d['text_records']}
 assert len(segments)==len(d['line_segments']);assert len({r['edge_uid'] for r in d['relation_edges']})==len(d['relation_edges'])
 for r in d['context_reviews']:
  assert set(r.get('view_ids',[]))<=views
 for r in d['relation_edges']:
  assert set(r['segment_ids'])<=segments
  assert r['source_uid'] in text|components and r['target_uid'] in components
  assert set(r['competing_object_ids'])<=components
 for r in d['line_segments']:assert set(r['view_ids'])<=views
 for category in ['continuous_ring_writing_original','context_regions_original','gaps_and_damage_original']:
  for original in s[category]:
   found=[r for r in d['context_reviews'] if r.get('original_category')==category and r.get('original_id')==original['id']]
   assert len(found)==1 and found[0]['original_record']==original
 original_text=[r['region_uid'] for r in s['text_records']];original_components=[r['component_uid'] for r in s['object_components']]
 assert set(original_text)==text and set(original_components)<=components
 not_reviewed=[r.get('region_uid',r.get('component_uid')) for r in d['text_records']+d['object_component_reviews'] if r['review_status']=='not_reviewed']
 assert not not_reviewed and not d['remaining_not_reviewed_ids']
 local_files=[HERE/f'{panel}_{suffix}' for suffix in ['relations_v1.json','relations_v1.txt','verification_v1.json','freeze_v1.json','prepared_views_v1.json']];files.extend(local_files)
 records.append({'panel':panel,'observer_id':'astronomical_site','panel_status':d['panel_status'],'files':[file_record(p) for p in local_files],'actual_view_count':len(d['view_receipts']),'actual_view_modes':counts(d['view_receipts'],'display_mode'),'actual_display_first_utc':min(r['displayed_at_utc'] for r in d['view_receipts']),'actual_display_last_utc':max(r['displayed_at_utc'] for r in d['view_receipts']),'original_text_ids':original_text,'original_component_ids':original_components,'all_original_ids_retained':True,'fixed_text_region_count':len(original_text),'fixed_component_count':len(original_components),'supplementary_component_ids':sorted(components-set(original_components)),'text_review_status_counts':counts(d['text_records'],'review_status'),'text_layout_state_counts':counts(d['text_records'],'layout_association'),'text_visual_status_counts':counts(d['text_records'],'text_status'),'component_review_status_counts':counts(d['object_component_reviews'],'review_status'),'component_NA_after_review_ids':[r['component_uid'] for r in d['object_component_reviews'] if r['review_status']=='NA_after_review'],'edge_evidence_counts':{kind:counts([e for e in d['relation_edges'] if e['edge_kind']==kind],'evidence_level') for kind in ['text_to_object','body_to_pointed']},'incomplete_line_segment_count':sum(not r['trace_complete'] for r in d['line_segments']),'not_reviewed_count':len(not_reviewed),'not_reviewed_ids':not_reviewed,'per_panel_integrity_checks_passed':v['checks_passed'],'context_original_records_equal':True,'frozen_file_hashes_reverified':True})
files.extend(HERE/name for name in EXTRA)
assert len(set(files))==len(files)
result={'schema':'zodiac_object_relations_observer_manifest_v1','observer_id':'astronomical_site','created_utc':datetime.now(timezone.utc).isoformat(),'scope':'Only this observer assigned panels, in fixed authorized order. No peer new relation judgments read.','input_freeze_sha256':sha(SOURCE/'execution_freeze_v1.json'),'fixed_panel_order':PANELS,'panels':records,'totals':{'actual_view_receipts':sum(r['actual_view_count'] for r in records),'fixed_text_regions':sum(r['fixed_text_region_count'] for r in records),'fixed_object_components':sum(r['fixed_component_count'] for r in records),'supplementary_components':sum(len(r['supplementary_component_ids']) for r in records),'not_reviewed_count':sum(r['not_reviewed_count'] for r in records)},'explicit_artifact_allowlist':[file_record(p) for p in files],'private_images_included':False,'working_drafts_included':False,'interpretation_limits':['Counts are review states and edge states, never naming passes or word/object identities.','All text-to-object N remains layout evidence only. Body-to-pointed E does not propagate to text ownership.','P and NA remain unresolved; N does not establish absence beyond reviewed context.','Single layout candidate is not semantic certification; no_local_layout_candidate is an actually reviewed absence of resolved local association, not an unviewed NA.','Line evidence rectangles bound manually inspected sections, not exact ink masks or interpolated centerlines.','This manifest checks schemas, references, original IDs/context equality and immutable hashes; it is not an independent visual audit.','Prior page/research exposure is disclosed in each panel; this is not blind image review.','No EVA strings, cross-page text matching or semantic scores were produced.']}
manifest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
report=HERE/'observer_manifest_v1.txt'
lines=['本代理四图关系复核清单 v1','固定顺序：f71v → f72r1 → f72r3 → f72v1。','仅汇总 astronomical_site 自己的冻结记录；未读取其他代理新关系判断。','实际查看数包含单独标记的导航总览与原生细节。未决边、组件 NA 与未复核是不同状态，不合并为命名成功数。','']
for r in records:
 lines.extend([r['panel']+f"：实际查看 {r['actual_view_count']}；固定文字 {r['fixed_text_region_count']}；原组件 {r['fixed_component_count']}；另拆 {len(r['supplementary_component_ids'])}；未复核 {r['not_reviewed_count']}。",'  文字布局状态：'+json.dumps(r['text_layout_state_counts'],ensure_ascii=False),'  组件状态：'+json.dumps(r['component_review_status_counts'],ensure_ascii=False),'  文字/身体边状态：'+json.dumps(r['edge_evidence_counts'],ensure_ascii=False),'  原始 ID 全保留；源上下文逐字段相等；原冻结文件哈希重核一致。'])
lines+=['','总计：'+json.dumps(result['totals'],ensure_ascii=False),'','精确路径/哈希/字节、原 ID、实际查看时间和未决细项见同名 JSON。','完整性核查不等于独立图像审核；没有识字、历史对象身份或词义结论。']
report.write_text('\n'.join(lines)+'\n')
freeze={'schema':'zodiac_object_relations_observer_manifest_freeze_v1','observer_id':'astronomical_site','freeze_utc':datetime.now(timezone.utc).isoformat(),'files':[file_record(manifest),file_record(report)],'input_freeze_sha256':result['input_freeze_sha256'],'immutable_original_panel_freezes_preserved':True}
(HERE/'observer_manifest_freeze_v1.json').write_text(json.dumps(freeze,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'totals':result['totals'],'manifest_sha256':sha(manifest),'manifest_freeze_sha256':sha(HERE/'observer_manifest_freeze_v1.json'),'explicit_artifact_count':len(files)},ensure_ascii=False))
