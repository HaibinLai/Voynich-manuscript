"""Serialize already observed manual notes; does not infer observations from geometry."""
from review_tools import *
import collections

def assemble(f):
 r=load(HERE/(f+'_working.json'));s=seed(f);notes=load(HERE/(f+'_manual_notes.json'))
 seen={v['view_id']:v for v in r['view_receipts']};p={v['plan_view_id']:v for v in plan(f)['view_plans']}
 def support(uid,kind):
  primary=uid+':'+kind
  assert primary in seen,(uid,'NOT ACTUALLY VIEWED')
  vv=[primary]+[v['view_id'] for v in r['view_receipts'] if v['display_mode']=='native_detail' and uid in v['covered_text_uids'] and v['view_id']!=primary]
  return vv
 def edge(uid,kind,source,target,lev,facts,views,segids=[],extent=None,visibility=None):
  v=visibility or ('explicit_connection_seen' if lev=='E' else 'partial_connection_seen' if lev=='P' else 'no_explicit_connection_observed_in_reviewed_views')
  e=dict(edge_uid=uid,edge_kind=kind,source_uid=source,target_uid=target,endpoint_type_pair=['writing_region' if kind=='text_to_object' else 'body_or_other_graphic',target.rsplit('/',1)[-1]],evidence_level=lev,observed_endpoint_facts=facts,segment_ids=segids,competing_object_ids=[],crossing_resolution='未将相邻字笔、纸褶或环线当作连接；无自动补线。',line_visibility_state=v,view_ids=views,reviewed_context_extent_xyxy=extent,limitations=['N仅是已查看邻域中的空间候选；E也仅认证图示墨线，不认证文字意义或命名。','坐标为原像素上手工近似采样/包络，不是逐像素墨迹分割。'],semantic_identity=None,semantic_ownership_certified=False)
  r['relation_edges'].append(e);return uid
 for t in r['text_records']:
  key=t['region_uid'].split(':',1)[1];n=notes['text'][key];vv=support(t['region_uid'],'V3');ids=[f+':'+z for z in n['candidates']]
  t.update(review_status='reviewed',viewed_view_ids=vv,text_status=n.get('text_status','writing_like'),candidate_object_ids=ids,no_candidate_reason=None if ids else '已查看局部不含可指定的本图人物/星形；不凭远距离或边页痕迹指定归属。',relation_edge_ids=[],observation_facts=[n['fact']],candidate_constraints=['只有整个环带的共同边界或邻近空白；未据来源角序或最近距离认证唯一归属。'] if ids else ['本图目标范围以外的邻页/边缘不能自动作为本图标签。'],layout_association=n.get('layout','multiple_layout_candidates' if len(ids)>1 else 'single_layout_candidate' if len(ids)==1 else 'no_local_layout_candidate'),subgroup_candidates=[{'source_alternative':a,'status':'原细分备选保留；本次不认证为语言词或唯一分组。'} for a in s['fine_alternatives_original'] if a.get('coarse_parent_id')==key],damage_refs=n.get('damage',[]),line_visibility_state=n.get('visibility','no_explicit_connection_observed_in_reviewed_views'),reviewed_context_extent_xyxy=seen[vv[0]]['crop_xyxy_original'],unassessed_scope='所有未列对象对 not_individually_assessed；局部负记录不外推为全图不存在关系。',completion_or_NA_reason='完成固定局部及整体邻域查看，保留空间候选/细分和文字身份限度；未做词义/转写比较。',limitations=['同框或同环不等于同语义角色；未认证词界。'])
  for j,z in enumerate(ids):t['relation_edge_ids'].append(edge(t['region_uid']+':layout'+str(j+1),'text_to_object',t['region_uid'],z,'N',[n['fact']],vv,extent=t['reviewed_context_extent_xyxy'],visibility=t['line_visibility_state']))
  t['damage_refs']=['vertical_line_center' if z=='central_vertical_crease' else z for z in t['damage_refs']]
 for c in r['object_component_reviews']:
  k=c['component_uid'].split(':',1)[1].split('/')[0];n=notes['objects'][k];v=f+':'+k+':V4';assert v in seen
  orig=next(q for q in s['object_components'] if q['component_uid']==c['component_uid'])
  c.update(review_status='reviewed',viewed_view_ids=[v],reviewed_component_box_xyxy=orig['original_box_xyxy'],component_type_observed=orig['component_type'],related_edge_ids=[f+':'+k+':body_pointed'],missing_component_state='not_missing_in_this_local_view' if orig['original_box_xyxy'] else 'source_box_missing_not_repaired',competing_component_ids=[],observation_facts=[n['fact']],completion_or_NA_reason='本体及邻接星形原生局部均实际查看；原父组不单独作为连接证据。')
 for k,n in notes['objects'].items():
  v=f+':'+k+':V4';sid=f+':'+k+':stroke1';pts=n['points']
  # P paths stop on the observed stroke; they never bridge the recorded gap.
  r['line_segments'].append(dict(segment_uid=sid,type_candidates=['drawn_arm_or_hand','thin_graphic_connector'],visible_polyline_original_xy=pts,endpoint_boxes_xyxy=[[a-12,b-12,a+12,b+12] for a,b in [pts[0],pts[-1]]],breaks_or_occlusions=[] if n['level']=='E' else [{'status':'unresolved_transition_or_gap','description':n['fact'],'interpolated':False}],crossings=[],branch_candidates=[],view_ids=[v],trace_complete=n['level']=='E',trace_stop_reason=None if n['level']=='E' else n['fact']))
  edge(f+':'+k+':body_pointed','body_to_pointed',f+':'+k+'/body',f+':'+k+'/pointed_shape',n['level'],[n['fact']],[v],[sid],seen[v]['crop_xyxy_original'])
 r['context_reviews']=notes['context'];r['open_arc_notes']=notes.get('open_arc_notes',[])
 r['object_component_reviews']+=notes.get('additional_components',[])
 r['relation_edges']+=notes.get('additional_edges',[]);r['line_segments']+=notes.get('additional_segments',[])
 r['discovered_supplements']=notes.get('discovered_supplements',[])
 r['remaining_not_reviewed_ids']=[x['region_uid'] for x in r['text_records'] if x['review_status']=='not_reviewed']+[x['component_uid'] for x in r['object_component_reviews'] if x['review_status']=='not_reviewed']
 assert not r['remaining_not_reviewed_ids'];r['panel_status']='reviewed';r['stopped_utc']=now()
 assert set(x['region_uid'] for x in r['text_records'])==set(x['region_uid'] for x in s['text_records'])
 assert set(x['component_uid'] for x in r['object_component_reviews'])>=set(x['component_uid'] for x in s['object_components'])
 import schema_check
 schema_check.validate(r,load(BASE/'schema_v1.json'))
 out=HERE/(f+'_report_v1.json');assert not out.exists();save(out,r)
 print(f,'text',len(r['text_records']),'seedcomponents',len(s['object_components']),'views',len(seen),'edges',collections.Counter((e['edge_kind'],e['evidence_level']) for e in r['relation_edges']))
 return r
if __name__=='__main__':assemble(sys.argv[1])
