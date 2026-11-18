"""Native crop preparation and post-display receipts. Preparation does not mark views."""
from pathlib import Path
import json,hashlib,datetime,sys
from PIL import Image
BASE=Path(__file__).resolve().parent.parent
WORK=BASE.parents[4]
OUT=WORK/'output/voynich/research_next/astronomical7h_20261118/zodiac_object_relations/literature'
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
load=lambda p:json.loads(Path(p).read_text())
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def seed(f):return next(x for x in load(BASE/'seed_roster_v1.json')['panels'] if x['panel']==f)
def plan(f):return next(x for x in load(BASE/'view_plan_v1.json')['panels'] if x['panel']==f)
def init(f):
 s=seed(f); p=plan(f); out=HERE/(f+'_working.json')
 if out.exists():return
 r=dict(schema='zodiac_object_relations_observer_panel_v1',panel=f,observer_id='literature',input_freeze_sha256=sha(BASE/'execution_freeze_v1.json'),seed_roster_sha256=sha(BASE/'seed_roster_v1.json'),original_sha256=p['original_sha256'],panel_status='not_reviewed',started_utc=None,stopped_utc=None,exposure_statement='同一AI此前参与旧 guided f73r/f73v 定位及两路坐标算术审查，接触旧图面和几何名册；本次不是盲集。仅使用冻结旧图像名册和官方原像素，不使用本轮同行新判断、转写词串或文字得分。',text_records=[],object_component_reviews=[],relation_edges=[],line_segments=[],view_receipts=[],context_reviews=[],discovered_supplements=[],open_arc_notes=[],remaining_not_reviewed_ids=[],limitations=['矩形与原组件父级只提供检查范围，不预先认证归属。','未逐一检查所有跨图对象对；无局部可见连接不表示不存在语义关系。'],no_text_matching_or_semantic_score=True)
 for t in s['text_records']:
  r['text_records'].append(dict(region_uid=t['region_uid'],review_status='not_reviewed',viewed_view_ids=[],text_status=None,candidate_object_ids=None,no_candidate_reason=None,relation_edge_ids=None,observation_facts=None,candidate_constraints=None,layout_association=None,subgroup_candidates=None,damage_refs=[],line_visibility_state='not_reviewed',reviewed_context_extent_xyxy=None,unassessed_scope='not_individually_assessed',completion_or_NA_reason=None,limitations=[]))
 for c in s['object_components']:
  r['object_component_reviews'].append(dict(component_uid=c['component_uid'],review_status='not_reviewed',viewed_view_ids=[],reviewed_component_box_xyxy=None,component_type_observed=None,related_edge_ids=None,missing_component_state=None,competing_component_ids=None,observation_facts=None,completion_or_NA_reason=None))
 r['remaining_not_reviewed_ids']=[t['region_uid'] for t in r['text_records']]+[c['component_uid'] for c in r['object_component_reviews']]
 save(out,r)
def prepare(f):
 p=plan(f); d=OUT/f;d.mkdir(parents=True,exist_ok=True)
 src=WORK/'output/voynich/research_next/astronomical7h_20261118/zodiac_visual'/str(p['canvas_id']+'.jpg')
 assert sha(src)==p['original_sha256'];im=Image.open(src);index={}
 for v in p['view_plans']:
  box=v['crop_xyxy_original'];view=im.crop(box);vid=v['plan_view_id'];name=vid.replace(':','_')+'.png'
  if v['intended_display_mode']=='overview_navigation_only':view.thumbnail((1400,1400))
  view.save(d/name)
  index[vid]={'file':name,'sha256':sha(d/name),'box':box,'native_dimensions_px':[box[2]-box[0],box[3]-box[1]],'stored_dimensions_px':list(view.size),'display_mode':v['intended_display_mode'],'plan_view_id':vid,'planned_region_uids':v['planned_region_uids']}
 save(d/'prepared_index.json',index)
 return str(d)
def mark(f,ids,note='原生局部实际由 view_image 显示；登记时间在显示返回之后，不以生成时间代替。'):
 r=load(HERE/(f+'_working.json')); idx=load(OUT/f/'prepared_index.json');s=seed(f)
 if r['started_utc'] is None:r['started_utc']=now()
 r['panel_status']='in_progress'
 for vid in ids:
  assert not any(x['view_id']==vid for x in r['view_receipts'])
  v=idx[vid];b=v['box']
  contained=lambda z:z is not None and b[0]<=z[0] and b[1]<=z[1] and b[2]>=z[2] and b[3]>=z[3]
  r['view_receipts'].append(dict(view_id=vid,plan_view_id=v['plan_view_id'],original_sha256=r['original_sha256'],crop_xyxy_original=b,rotation_degrees=0,native_dimensions_px=v['native_dimensions_px'],view_file_sha256=v['sha256'],displayed_at_utc=now(),display_mode=v['display_mode'],covered_text_uids=[t['region_uid'] for t in s['text_records'] if contained(t['original_box_xyxy'])],covered_component_uids=[c['component_uid'] for c in s['object_components'] if contained(c['original_box_xyxy'])],actual_coverage_note=note))
 save(HERE/(f+'_working.json'),r)
if __name__=='__main__':
 if sys.argv[1]=='init':
  for f in ['f70v2','f71r','f72v3','f73v']:init(f)
 elif sys.argv[1]=='prepare':print(prepare(sys.argv[2]))
 elif sys.argv[1]=='mark':mark(sys.argv[2],sys.argv[3:])
