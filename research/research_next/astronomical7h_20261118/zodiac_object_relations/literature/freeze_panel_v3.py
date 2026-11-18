from review_tools import *
from schema_check import validate
from collections import Counter
f=sys.argv[1];r=load(HERE/(f+'_report_v1.json'));s=seed(f);ix=load(OUT/f/'prepared_index.json');validate(r,load(BASE/'schema_v1.json'))
assert len({x['view_id'] for x in r['view_receipts']})==len(r['view_receipts'])
for v in r['view_receipts']:
 z=ix[v['view_id']];assert sha(OUT/f/z['file'])==v['view_file_sha256'];assert z['box']==v['crop_xyxy_original'];assert z['native_dimensions_px']==v['native_dimensions_px']
views={v['view_id'] for v in r['view_receipts']};components={c['component_uid'] for c in r['object_component_reviews']};texts={t['region_uid'] for t in r['text_records']}
assert texts==set(t['region_uid'] for t in s['text_records'])
assert set(c['component_uid'] for c in s['object_components'])<=components
for t in r['text_records']:
 assert set(t['viewed_view_ids'])<=views;assert set(t['candidate_object_ids'] or [])<=components
for e in r['relation_edges']:assert set(e['view_ids'])<=views;assert e['source_uid'] in texts|components;assert e['target_uid'] in components
for c in r['object_component_reviews']:assert set(c['viewed_view_ids'])<=views
p=plan(f);src=WORK/'output/voynich/research_next/astronomical7h_20261118/zodiac_visual'/(p['canvas_id']+'.jpg');assert sha(src)==r['original_sha256']
counts={'text_records':len(texts),'coarse_primary':sum(t['roster_class']=='coarse_primary' for t in s['text_records']),'fixed_supplements':sum(t['roster_class']=='fixed_supplement' for t in s['text_records']),'seed_complexes':len(s['object_complexes']),'seed_components':len(s['object_components']),'added_context_components':len(components)-len(s['object_components']),'actual_view_receipts':len(views),'text_relation_levels':dict(Counter(e['evidence_level'] for e in r['relation_edges'] if e['edge_kind']=='text_to_object')),'body_relation_levels':dict(Counter(e['evidence_level'] for e in r['relation_edges'] if e['edge_kind']=='body_to_pointed')),'remaining_not_reviewed':len(r['remaining_not_reviewed_ids']),'text_NA_after_review':sum(t['review_status']=='NA_after_review' for t in r['text_records']),'components_NA_after_review':sum(c['review_status']=='NA_after_review' for c in r['object_component_reviews'])}
check={'created_utc':now(),'all_record_integrity_checks_passed':True,'counts':counts,'original_sha_after_review':sha(src),'schema_validation':'Standard-library exact schema keyword subset; installed jsonschema was absent. No visual claims are created by this check.','all_receipt_image_hashes_rechecked':True,'actual_view_evidence_scope':'view_image tool displays followed by receipt registration. This is an observation trace, not an independent second observer.','missing_or_unreviewed_as_negative':False}
checkpath=HERE/(f+'_integrity_v1.json');assert not checkpath.exists();save(checkpath,check)
txt=f'''{f} 文字区—对象关系复核\n\n本图按原固定名册和官方原像素完成。{counts['text_records']} 个文字/疑似文字区（{counts['coarse_primary']} 个粗区及 {counts['fixed_supplements']} 个补充区）、{counts['seed_complexes']} 个人物—尖形父组的 {counts['seed_components']} 个原组件均保留；另把已登记中央背景拆为 {counts['added_context_components']} 个可引用组件，不增加文字分母。实际显示查看收据 {len(views)} 条；未复核项 {counts['remaining_not_reviewed']}。\n\n文字边登记的是未排序空间候选 N，不是词语归属命中：{counts['text_relation_levels']}。多项文字位于相邻人体/星形之间，没有独立的文字引线或逐项封闭格；纸褶、长字笔、环带边界分别保留。边缘疑似文字不强指派给本图人物。人物/手—尖形的图示连接单独记录：{counts['body_relation_levels']}；E 只表示实际可追踪墨线，P 保留淡化/间断/端点歧义，不把二者传递成文字—星形认证。实际查看后仍未知的 NA 分别保留，未画虚拟线段；它与尚未查看的 not_reviewed 不同。\n\n逐项事实、竞争候选、文字细分备选、部分线段原坐标、上下文、损伤与查看收据详见 {f}_report_v1.json。手工路径是可见笔段的近似采样，不是自动像素追踪；P 的采样不跨缺口插值。中央图案及额外图形保留为独立背景组件；具体空间限制以逐项事实为准。\n\n这是同一 AI 在已有图面/旧几何记录曝光后的指导性复核，不是新的盲观察。未使用 EVA 词串、命中/相似度或跨图语义分数；未根据邻近角度制造一一对应，未认证名称、读向、词界或意义。字段校验和文件哈希复查只证明记录完整性，不是第二观察者复认。\n'''
txtpath=HERE/(f+'_report_v1.txt');assert not txtpath.exists();txtpath.write_text(txt)
files=[f+'_report_v1.json',f+'_report_v1.txt',f+'_manual_notes.json',f+'_integrity_v1.json','input_receipt_v1.json','review_tools.py','assemble_panel_v3.py','schema_check.py','freeze_panel_v3.py','prepare_external_tiles.py']
freeze=HERE/(f+'_freeze_v1.json');assert not freeze.exists();save(freeze,{'schema':'observer_panel_output_freeze_v1','created_utc':now(),'panel':f,'observer':'literature','input_freeze_sha256':r['input_freeze_sha256'],'files':[{'path':q,'sha256':sha(HERE/q)} for q in files],'counts':counts,'other_observers_new_panel_judgments_read_before_freeze':False,'public_paths_are_relative':True})
print(f,sha(freeze),counts)
