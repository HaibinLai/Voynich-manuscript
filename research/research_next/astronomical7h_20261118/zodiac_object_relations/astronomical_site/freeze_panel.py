"""Integrity checks and immutable per-panel output; never generates visual judgments."""
from record_helpers import *
import sys
import jsonschema
from collections import Counter

def freeze(panel):
 d=load(panel);s=seed(panel);prepared=read(HERE/f'{panel}_prepared_views_v1.json')
 assert not (HERE/f'{panel}_freeze_v1.json').exists(),'Already frozen; use an explicit later version.'
 jsonschema.validate(d,read(SOURCE/'schema_v1.json'))
 checks=[]
 def check(ok,name):
  assert ok,name;checks.append(name)
 check({r['region_uid'] for r in d['text_records']}=={r['region_uid'] for r in s['text_records']},'All fixed text IDs retained')
 comps={r['component_uid'] for r in d['object_component_reviews']}
 check({r['component_uid'] for r in s['object_components']}<=comps,'All fixed component IDs retained')
 check(len(comps)==len(d['object_component_reviews']),'Unique component IDs')
 views={r['view_id']:r for r in d['view_receipts']}
 check(len(views)==len(d['view_receipts']),'Unique actual view receipts')
 pviews={r['view_id']:r for r in prepared['views']}
 check(set(views)==set(pviews),'Every prepared required view actually displayed')
 workspace=SOURCE.parents[3].parent
 for vid,v in views.items():
  p=pviews[vid];check(v['view_file_sha256']==sha(workspace/p['private_file_workspace_relative']),vid+' displayed file SHA')
  check(v['crop_xyxy_original']==p['crop_xyxy_original'],vid+' original crop unchanged')
  check(v['displayed_at_utc']<'2026-11-18T22:40:00Z',vid+' before cutoff')
 for r in d['text_records']+d['object_component_reviews']:
  uid=r.get('region_uid',r.get('component_uid'));check(r['review_status'] in ['reviewed','NA_after_review'],uid+' reviewed status')
  check(bool(r['viewed_view_ids']) and all(v in views for v in r['viewed_view_ids']),uid+' actual viewed support')
 for e in d['relation_edges']:
  check(e['target_uid'] in comps,e['edge_uid']+' known target component')
  check(all(v in views for v in e['view_ids']),e['edge_uid']+' actual viewed support')
  if e['evidence_level']=='E':check(bool(e['segment_ids']),e['edge_uid']+' explicit line evidence')
 original_contexts=[]
 for category in ['continuous_ring_writing_original','context_regions_original','gaps_and_damage_original']:
  original_contexts.extend((category,x['id']) for x in s[category])
 for cat,ident in original_contexts:
  check(any(r.get('original_category')==cat and r.get('original_id')==ident for r in d['context_reviews']),cat+':'+ident+' context retained')
 d['remaining_not_reviewed_ids']=[];d['panel_status']='reviewed';d['stopped_utc']=datetime.now(timezone.utc).isoformat()
 jsonschema.validate(d,read(SOURCE/'schema_v1.json'))
 final=HERE/f'{panel}_relations_v1.json';final.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
 kinds={k:Counter(e['evidence_level'] for e in d['relation_edges'] if e['edge_kind']==k) for k in ['text_to_object','body_to_pointed']}
 lines=[f'{panel} 图像关系复核 v1','观察者：astronomical_site；有既往曝光，不是盲图像复读。',f"固定文字区：{len(d['text_records'])}；固定对象组件：{len(s['object_components'])}；另拆组件：{len(comps)-len(s['object_components'])}。",f"实际查看收据：{len(views)}（导航总览与原生细节分开）。",'文字到对象证据：'+json.dumps(dict(kinds['text_to_object']),ensure_ascii=False),'身体/手到星形证据：'+json.dumps(dict(kinds['body_to_pointed']),ensure_ascii=False),'以上是边的状态数量，不是对象数量、识字率或命名成功率。','E仅指所述可见图示连接；身体到星形的E没有复制成文字到对象E。','线段用原生像素局部框序列记录；visible_polyline保持空，不伪造像素级中心线。每段框见context_reviews的visible_line_segment_boxes。','全部固定文字区：']
 for r in d['text_records']:lines.append(r['region_uid']+' | '+r['review_status']+' | '+str(r['layout_association'])+' | '+'; '.join(r['observation_facts'] or []))
 lines+=['','全部身体/星形连接：']
 for e in d['relation_edges']:
  if e['edge_kind']=='body_to_pointed':lines.append(e['edge_uid']+' | '+e['evidence_level']+' | '+'; '.join(e['observed_endpoint_facts']))
 lines+=['','未完成 ID：无。完整字形/词义/标签专属正文资格未因此打开。']
 report=HERE/f'{panel}_relations_v1.txt';report.write_text('\n'.join(lines)+'\n')
 verification=HERE/f'{panel}_verification_v1.json';verification.write_text(json.dumps({'schema':'relation_panel_integrity_v1','panel':panel,'checks_passed':len(checks),'checks':checks,'validation_scope':'Schema, IDs, hashes, actual-receipt linkage, original context retention only. Not an independent visual verification.','all_seed_contexts_preserved':True},ensure_ascii=False,indent=2)+'\n')
 files=[final,report,verification,HERE/f'{panel}_prepared_views_v1.json',HERE/'assigned_seed_records_v1.json',HERE/'prepare_views.py',HERE/'record_helpers.py',Path(__file__).resolve()]
 frozen={'schema':'object_relations_panel_output_freeze_v1','panel':panel,'observer_id':'astronomical_site','freeze_utc':datetime.now(timezone.utc).isoformat(),'input_freeze_sha256':d['input_freeze_sha256'],'files':[{'path':str(p.relative_to(HERE)),'sha256':sha(p),'bytes':p.stat().st_size} for p in files],'private_image_files_published':False,'status':'reviewed','next_panel_order_fixed':['f71v','f72r1','f72r3','f72v1'],'limits':'No independent peer relation judgments read before this freeze; arithmetic integrity checks do not certify visual judgments.'}
 (HERE/f'{panel}_freeze_v1.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2)+'\n')
 print(panel,len(checks),'integrity checks; freeze',sha(HERE/f'{panel}_freeze_v1.json'))
if __name__=='__main__':freeze(sys.argv[1])
