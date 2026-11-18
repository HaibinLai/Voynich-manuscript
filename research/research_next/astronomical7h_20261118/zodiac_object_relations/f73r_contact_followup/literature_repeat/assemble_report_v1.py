#!/usr/bin/env python3
"""Assemble saved observations; does not create or imply new image observations."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,collections
HERE=Path(__file__).resolve().parent
BASE=HERE.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
now=lambda:datetime.now(timezone.utc).isoformat()
def write(name,value):
 p=HERE/name
 if p.exists():raise FileExistsError(p.name)
 p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n' if not isinstance(value,str) else value)
def main():
 own=read(HERE/'input_freeze_v1.json')
 for f in own['parent_files']+own['own_files']:
  assert sha(HERE/f['path'])==f['sha256'],f['path']
 inp=read(BASE/'input_freeze_v1.json'); prep=read(BASE/'prepared_views_v1.json')
 raw=read(HERE/'observed_notes_v1.json'); prior=read(HERE/'prior_exposure_snapshot_v1.json')
 fixed=inp['fixed_region_ids']; notes={x['region_uid']:x for x in raw['observations']}
 assert list(notes)==fixed and len(notes)==9
 events={x['filename']:x for x in raw['view_events']};assert len(events)==27
 assert set(events)=={x['filename'] for x in prep['views']}
 pairs=inp['pairs']; roles={p['candidate']:'prior_P_candidate' for p in pairs}
 roles.update({p['control']:'fixed_same_band_N_control' for p in pairs if p['control']})
 records=[];receipts=[]
 for uid in fixed:
  note=notes[uid]; oldedges=[e for e in prior['all_existing_text_edges'] if e['source_uid']==uid]
  oldtext=next(t for t in prior['text_records'] if t['region_uid']==uid)
  assert set(note['followup_edge_levels'])=={e['edge_uid'] for e in oldedges}
  regviews=[]
  for v in prep['views']:
   if v['region_uid']!=uid:continue
   e=events[v['filename']]
   assert e['tool']=='view_image'
   assert e['displayed_utc']<=note['review_completed_utc']
   regviews.append(v['view_id'])
   receipts.append({**v,'prepared_only_not_viewed':False,'actually_displayed_with_view_image':True,'displayed_utc':e['displayed_utc'],'regional_review_completed_utc':note['review_completed_utc'],'display_mode':'native_detail','image_transform':'none; fixed native PNG crop','file_location':'private-output/zodiac_object_relations/f73r_contact_followup/'+v['filename']})
  comps=[]
  for e in oldedges:
   comps.append({'edge_uid':e['edge_uid'],'source_uid':e['source_uid'],'target_uid':e['target_uid'],'original_grade':e['evidence_level'],'followup_grade':note['followup_edge_levels'][e['edge_uid']],'candidate_retained':True,'semantic_ownership_certified':False})
  records.append({'region_uid':uid,'selection_role':roles[uid],'scope_class':'central_source_informed_annotation' if uid=='f73r:ZC01' else 'peripheral_writing_region','review_status':'reviewed','view_ids':regviews,'original_text_record':oldtext,'all_original_candidate_edges':oldedges,'edge_grade_comparison':comps,'observation':note,'readings_or_transcription':None,'semantic_identity':None})
 oldn=sum(len(x['all_original_candidate_edges']) for x in records)
 assert oldn==len(prior['all_existing_text_edges'])==24
 assert all(v['displayed_utc']<'2026-11-18 22:40:00 UTC' for v in receipts)
 report={'schema':'f73r_contact_literature_repeat_observation_v1','observer_id':'literature','created_utc':now(),'input_freeze_sha256':sha(HERE/'input_freeze_v1.json'),'parent_input_freeze_sha256':sha(BASE/'input_freeze_v1.json'),'original_image':inp['original_image'],'observation_status':'all_fixed_views_reviewed','prior_exposure':{'original_report_and_prior_P_candidates_known':True,'full_12_aggregation_and_posthoc_ID_join_known':True,'central_annotation_source_context_known':True,'prior_guided_f73r_image_exposure':True,'root_current_visual_judgments_read_before_own_freeze':False,'root_freeze_existence_notification_received':True,'blind':False,'same_AI_observer_not_external_independent_expert':True},'fixed_selection_pairs':pairs,'fixed_region_ids':fixed,'records':records,'view_receipts':receipts,'target_component_reviews_preserved':prior['target_component_reviews'],'target_supplement_declarations_preserved':prior['target_supplement_declarations'],'coverage':{'regions':9,'prior_P_regions':5,'fixed_N_control_regions':4,'actual_native_views':27,'preserved_original_candidate_edges':oldn,'not_reviewed_regions':0,'central_same_band_N_control':None},'qualitative_scope':['中央一例与外围八例分别保留，不计算成功率、显著性或代表性发生率。','E/P/N/NA为本次可见连接证据分类，不是文字指代或语义真值。','P保留接触/端点角色未解；未见独立引线不能推出没有历史关系。','固定框/对照均在已知原判断后确定；本次不是新盲证据或高分辨率新摄影。','未增强、补笔、重采样或猜读；旧报告和12图汇编未替换。'],'new_image_selection':False,'no_text_matching_or_semantic_score':True}
 write('observation_v1.json',report)
 lines=['f73r 接触候选知情复核：literature 一路','', '本次实际看完固定9区、27个原生视图，完整保留24条既存文字侧候选边。原报告和汇编不改。已知原P候选、旧guided图面、全12汇编与中央注记来源背景；另一同AI代理本次新判断在冻结前未读取。不称盲读或外部专家认证。','中央无同带N对照，保持NA。下列N/P只描述图形连接证据，不认证命名；所有候选继续保留。','']
 for r in records:
  n=r['observation'];lines += [r['region_uid']+' — '+r['selection_role']]
  lines += ['可见：'+s for s in n['visible_facts']]
  lines += ['独立文字侧引线：未观察到。','接触：'+n['contact'],'空隙：'+n['gap'],'叠压：'+n['overprint'],'替代：'+'；'.join(n['alternatives'])]
  lines += ['候选 '+x['target_uid']+'：原 '+x['original_grade']+' → 本次 '+x['followup_grade']+'；保留。' for x in r['edge_grade_comparison']]
  lines += ['限制：'+n['limitation'],'实际查看完成：'+n['review_completed_utc'],'']
 lines += ['记录边界','这9区不是32区全覆盖，4个N对照也不是语义阴性真值；选择是知情事后设计。中央普通注记与外围短串不同类，不合成命名成功率。','文字接触人体轮廓不等于文字引线；人体至尖形的画线不替代文字至尖形。浅墨接触处未确定落笔先后。','所有原图视图哈希、原画布框及实际view_image显示时间见observation_v1.json。prepared_only_not_viewed被本路查看收据覆盖，不改原prepared_views。','']
 write('observation_v1.txt','\n'.join(lines))
 write('integrity_v1.json',{'created_utc':now(),'all_passed':True,'input_hashes_unchanged':True,'all_fixed_9_regions_preserved':True,'all_fixed_27_actual_view_events_matched':True,'all_24_original_candidate_edges_preserved':True,'own_new_views_only_fixed':True,'no_root_current_judgments_read':True,'observation_json_sha256':sha(HERE/'observation_v1.json'),'checks_are_record_consistency_not_independent_visual_confirmation':True})
 names=['protocol_v1.txt','prior_exposure_snapshot_v1.json','input_validation_v1.json','input_freeze_v1.json','observed_notes_v1.json','assemble_report_v1.py','observation_v1.json','observation_v1.txt','integrity_v1.json']
 write('output_freeze_v1.json',{'schema':'f73r_literature_repeat_output_freeze_v1','created_utc':now(),'input_freeze_sha256':sha(HERE/'input_freeze_v1.json'),'files':[{'path':n,'sha256':sha(HERE/n)} for n in names],'all_fixed_views_observed':True,'root_new_observation_not_read_before_this_freeze':True,'no_old_record_replaced':True})
 print(json.dumps({'output_freeze_sha256':sha(HERE/'output_freeze_v1.json'),'observation_sha256':sha(HERE/'observation_v1.json'),'files':len(names),'regions':9,'view_count':27}))
if __name__=='__main__':main()
