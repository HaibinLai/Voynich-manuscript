#!/usr/bin/env python3
"""Read-only projection of the fourth-window initial freeze. No scientific measurements.
Reads eleven initial inputs, ten v2 sources, and optional eight v3 sources plus view bytes.
Only explicit frozen paths are read; ongoing matrices, inventories and numeric outputs are excluded.
"""
import argparse,hashlib,json,re
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parent.parent
W=Path('research/research_next/repeated_labels7h_20261119')
OLD=Path('research/research_next/semantic7h_20261118')
FREEZE_HASH='4a79cd855b69bd2eecca116a1d01d44426aa3f91b857bc1727ef832b4352a015'
INPUTS=[
 (OLD/'design/repeated_label_feasibility/fixed_nine_roster_v1.json','fixed-nine-roster.json','既有固定九处名册'),
 (OLD/'design/repeated_label_feasibility/report_v1.txt','prior-feasibility-report.txt','既有固定范围与可行性记录'),
 (OLD/'design/repeated_label_comparison_support/report_v1.txt','prior-comparison-support.txt','既有比较设计支持记录'),
 (OLD/'visual/repeated_label_localization/comparison_gate_v1.json','prior-comparison-gate.json','旧比较门槛完整记录'),
 (OLD/'visual/repeated_label_localization/comparison_gate_v1.txt','prior-comparison-gate.txt','旧比较门槛说明'),
 (OLD/'visual/repeated_label_localization/review_v1.json','prior-first-localization.json','旧第一轮知情定位'),
 (OLD/'visual/repeated_label_localization/guided_second_review_v1.json','prior-second-localization.json','旧第二轮知情定位'),
 (OLD/'visual/repeated_label_localization/guided_second_root_geometry_check_v1.json','prior-geometry-check.json','旧矩形交集复算（不是墨迹认证）'),
 (W/'plan_v1.txt','plan.txt','本轮冻结计划'),
 (W/'session_v1.json','session.json','本轮时间与授权范围')]
PHASE_PATH=W/'publication/phase_input_v2.json'
PHASE_HASH='2e42f0da290487fbb923a966dca65a79b54d9f58cc6bddfb13518bd727fd1fe8'
PHASE_INPUTS=[
 ('qualification_contract_v1.txt','qualification-contract.txt','本轮资格观察执行合同'),
 ('qualification_approval_v1.json','qualification-approval.json','资格观察批准（不批准评分）'),
 ('method_review/protocol_proposal_v1.txt','method-proposal.txt','方法合同建议（仍在审查）'),
 ('method_review/protocol_proposal_v1.json','method-proposal.json','方法建议完整字段与范围'),
 ('method_review/input_output_hashes_v1.json','method-source-hashes.json','方法建议输入输出哈希'),
 ('literature/evidence_table_v1.txt','literature-evidence.txt','六条原始文献证据说明'),
 ('literature/evidence_table_v1.json','literature-evidence.json','六条文献完整证据表'),
 ('literature/method_recommendations_v1.txt','literature-method-recommendations.txt','文献支持的方法建议'),
 ('literature/scope_and_sources_v1.json','literature-scope-and-sources.json','文献阅读范围与来源'),
 ('literature/manifest_v1.json','literature-manifest.json','文献交付清单')]
PHASE_V3_PATH=W/'publication/phase_input_v3.json'
PHASE_V3_HASH='beae977d88ce7539eed31a075a307897e33dbad05fb38bea352781582bd15c84'
VIEW_COMMIT='acbdb5d54cd282737a2d3b629243df46c9e040b5'
V3_INPUTS=[
 ('qualification/qualification_v1.json','current-qualification.json','本轮九处资格观察完整记录'),
 ('qualification/qualification_v1.txt','current-qualification.txt','本轮九处资格观察说明'),
 ('qualification/hash_record_v1.json','current-qualification-hashes.json','原图、实际阅读视口与输出哈希'),
 ('measurement_approval_v1.json','measurement-approval.json','四项编码与后续条件评分批准'),
 ('feature_codebook_v1.json','feature-codebook.json','四项正式纸面特征定义'),
 ('feature_definition_ambiguity_v1.json','feature-definition-ambiguity.json','G1 定义歧义的未知处理'),
 ('measurement_review/review_v1.txt','measurement-method-review.txt','冻结测量定义与方法审查'),
 ('measurement_review/review_v1.json','measurement-method-review.json','冻结方法审查完整字段')]
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--phase-input',required=True,help='Explicit frozen phase_input_v2.json or phase_input_v3.json; never infer live research state.');args=ap.parse_args()
 freeze_bytes=(ROOT/W/'input_freeze_v1.json').read_bytes();assert sha(freeze_bytes)==FREEZE_HASH
 freeze=json.loads(freeze_bytes);expected={s['path']:s['sha256'] for s in freeze['sources']}
 assert set(expected)=={str(p) for p,_,_ in INPUTS}
 blobs={};docs={};sources=[]
 for path,name,label in INPUTS:
  b=(ROOT/path).read_bytes();assert sha(b)==expected[str(path)],str(path)
  assert not any(v in b for v in [b'/Users/',b'/private/var/',b'/home/'])
  blobs[name]=b
  if path.suffix=='.json':docs[name]=json.loads(b)
  sources.append({'file':str(path),'sha256':sha(b),'label':label,'url':'downloads/repeated-labels7h/'+name,'repository_url':'https://github.com/HaibinLai/Voynich-manuscript/blob/main/'+str(path)})
 blobs['input-freeze.json']=freeze_bytes;sources.append({'file':str(W/'input_freeze_v1.json'),'sha256':FREEZE_HASH,'label':'本轮输入冻结与来源哈希','url':'downloads/repeated-labels7h/input-freeze.json','repository_url':'https://github.com/HaibinLai/Voynich-manuscript/blob/main/'+str(W/'input_freeze_v1.json')})
 session=docs['session.json'];start=datetime.fromisoformat(session['start_utc'].replace('Z','+00:00'));end=datetime.fromisoformat(session['end_utc'].replace('Z','+00:00'))
 assert end-start==timedelta(hours=7)
 assert start.astimezone(ZoneInfo(session['timezone'])).isoformat()==session['start_local']
 assert end.astimezone(ZoneInfo(session['timezone'])).isoformat()==session['end_local']
 assert session['morphology_scoring_authorized'] is False and session['new_blind_dataset_claimed'] is False
 roster=docs['fixed-nine-roster.json']['records'];first=docs['prior-first-localization.json'];second=docs['prior-second-localization.json'];geometry=docs['prior-geometry-check.json']
 assert [r['locator'] for r in roster]==session['fixed_nine_loci'] and len(roster)==9
 assert len({r['physical_leaf'] for r in roster})==4
 def indexed(rows):
  out={r['locator']:r for r in rows};assert set(out)==set(session['fixed_nine_loci']) and len(out)==9;return out
 f=indexed(first['records']);q=indexed(second['records']);g=indexed(geometry['rectangles']);rows=[]
 for original in roster:
  uid=original['locator'];a=f[uid];b=q[uid]
  assert a['query_from_frozen_roster']==b['known_query']==original['cluster_word']
  assert a['physical_leaf']==original['physical_leaf'] and a['image']['url']==b['image_url']
  for canvas in original['official_canvas_candidates']:assert canvas['image_url']==f"https://collections.library.yale.edu/iiif/2/{canvas['image_id']}/full/full/0/default.jpg"
  assert a['image']['url']==f"https://collections.library.yale.edu/iiif/2/{a['image']['image_id']}/full/full/0/default.jpg"
  rows.append({'locator':uid,'label':original['cluster_word'],'physical_leaf':original['physical_leaf'],'current_window_measurement_qualification':'NOT_YET_ASSESSED','qualification':{'state':'NOT_YET_ASSESSED','decision':None,'candidate_unit':None,'visible_boundary':None,'neighbor_crossing':None,'text_occlusion':None,'part_granularity':None,'feature_observability':None},'morphology_result':None,'prior_roster_record':original,'prior_first_localization':a,'prior_second_localization':b,'prior_geometry_record':g[uid],'prior_review_page':'semantic7h.html#s7-repeated'})
 payload={'schema':'repeated_labels_fourth_window_page_v1','publication':{'state':'INITIAL_QUALIFICATION_SNAPSHOT','stage_zh':'资格审查中；形态评分未批准','status_basis':'本轮冻结启动计划与session；不读取后台状态、不自动判断进度。','new_observations_in_this_page':False,'blind_claim':False},'session':session,'rows':rows,'prior_comparison_gate':docs['prior-comparison-gate.json'],'prior_observation_times':{'first':first['utc'],'second':second['completed_utc']},'plan_text':blobs['plan.txt'].decode(),'results':{'state':'NOT_EXECUTED','values':None,'reason':'冻结计划仅批准输入盘点、文献与方案设计；形态编码与评分需后续测量合同及根批准。'},'sources':sources}
 if args.phase_input:
  requested=Path(args.phase_input)
  if requested.is_absolute():requested=requested.resolve().relative_to(ROOT)
  assert requested in [PHASE_PATH,PHASE_V3_PATH],'Only explicit frozen phase inputs are permitted'
  phase_bytes=(ROOT/PHASE_PATH).read_bytes();assert sha(phase_bytes)==PHASE_HASH
  phase=json.loads(phase_bytes);assert phase['schema']=='fourth_qualification_phase_publication_input_v2'
  assert phase['observation_scope_approved'] is True and phase['feature_coding_approved'] is False and phase['pair_scoring_approved'] is False
  assert phase['new_locus_results_in_this_snapshot'] is False
  phase_expected={x['path']:x['sha256'] for x in phase['sources']}
  assert set(phase_expected)=={str(W/name) for name,_,_ in PHASE_INPUTS}
  for name,download,label in PHASE_INPUTS:
   path=W/name;b=(ROOT/path).read_bytes();assert sha(b)==phase_expected[str(path)],str(path)
   assert not any(v in b for v in [b'/Users/',b'/private/var/',b'/home/'])
   blobs[download]=b
   if name.endswith('.json'):docs[download]=json.loads(b)
   sources.append({'file':str(path),'sha256':sha(b),'label':label,'url':'downloads/repeated-labels7h/'+download,'repository_url':'https://github.com/HaibinLai/Voynich-manuscript/blob/main/'+str(path)})
  assert docs['qualification-approval.json']['approved_by']=='root'
  entries=docs['literature-evidence.json']['entries'];assert len(entries)==phase['literature_entries']==6
  assert [x['id'] for x in entries]==['L01','L02','L03','L04','L05','L06']
  blobs['phase-input-v2.json']=phase_bytes;sources.append({'file':str(PHASE_PATH),'sha256':PHASE_HASH,'label':'本页阶段与授权快照 v2','url':'downloads/repeated-labels7h/phase-input-v2.json','repository_url':'https://github.com/HaibinLai/Voynich-manuscript/blob/main/'+str(PHASE_PATH)})
  payload['phase_input']=phase
  payload['publication'].update({'state':phase['phase'],'stage_zh':phase['phase_zh'],'status_basis':'本轮已冻结 phase_input_v2；只更新观察授权与文献，没有接入本轮九处观察结果。'})
  payload['literature']={'state':'FROZEN_PRIMARY_SOURCE_NOTES','entries':entries,'source':{'file':str(W/'literature/evidence_table_v1.json'),'sha256':phase_expected[str(W/'literature/evidence_table_v1.json')]}}
  payload['results']['reason']='本轮只批准全九处知情资格观察；具体特征方案仍在审查，特征编码与对象对评分均未批准。'
 if requested==PHASE_V3_PATH:
  v3_bytes=(ROOT/PHASE_V3_PATH).read_bytes();assert sha(v3_bytes)==PHASE_V3_HASH
  v3=json.loads(v3_bytes);assert v3['schema']=='fourth_feature_coding_phase_input_v3'
  assert v3['feature_coding_approved'] is True and v3['pair_scoring_approved_after_complete_matrix_freeze'] is True
  assert v3['feature_matrix_in_this_snapshot'] is False and v3['scores_in_this_snapshot'] is False
  required={x['path']:x['sha256'] for x in v3['sources']};assert set(required)=={str(W/n) for n,_,_ in V3_INPUTS}
  for name,download,label in V3_INPUTS:
   path=W/name;b=(ROOT/path).read_bytes();assert sha(b)==required[str(path)]
   assert not any(t in b for t in [b'/Users/',b'/private/var/',b'/home/'])
   blobs[download]=b
   if name.endswith('.json'):docs[download]=json.loads(b)
   sources.append({'file':str(path),'sha256':sha(b),'label':label,'url':'downloads/repeated-labels7h/'+download,'repository_url':'https://github.com/HaibinLai/Voynich-manuscript/blob/main/'+str(path)})
  qualification=docs['current-qualification.json'];new_rows=indexed(qualification['rows']);approval=docs['measurement-approval.json'];receipts=docs['current-qualification-hashes.json'];book=docs['feature-codebook.json']
  assert approval['approved_by']=='root' and approval['features']==['G1','G2','G3','G4']
  assert approval['canonical_group_index']==qualification['canonical_group_index']
  assert [x['id'] for x in book['nodes']]==session['fixed_nine_loci']
  assert len(qualification['canonical_group_index'])==v3['canonical_group_count']==12
  assert len(approval['global_candidate_scenarios'])==v3['candidate_scenario_count']==16
  assert len({x['id'] for x in approval['global_candidate_scenarios']})==16
  receipt_map={x['view_id']:x for x in receipts['views']};image_map={x['image_id']:x for x in receipts['original_images']};views={}
  for view in v3['native_views']:
   name=view['path'];assert Path(name).parent==W/'qualification/views' and Path(name).suffix=='.png'
   b=(ROOT/name).read_bytes();assert sha(b)==view['sha256'] and b[:8]==b'\x89PNG\r\n\x1a\n'
   import struct
   assert list(struct.unpack('>II',b[16:24]))==view['xywh'][2:]
   receipt=receipt_map[view['view_id']];assert receipt['actually_viewed'] is True
   assert all(receipt[k]==view[k] for k in ['path','sha256','image_id','xywh'])
   source=image_map[view['image_id']];assert source['sha256']==receipt['source_sha256']
   x,y,width,height=view['xywh'];assert x>=0 and y>=0 and width>0 and height>0 and x+width<=source['width'] and y+height<=source['height']
   views[view['view_id']]={**view,'pinned_commit':VIEW_COMMIT,'url':'https://raw.githubusercontent.com/HaibinLai/Voynich-manuscript/'+VIEW_COMMIT+'/'+name,'official_full_url':source['official_url'],'source_sha256':source['sha256'],'source_dimensions':[source['width'],source['height']],'receipt':receipt}
  assert len(views)==10
  for i,row in enumerate(rows):
   new=new_rows[row['locator']];old=row['prior_first_localization']
   assert new['original_label_bbox_xywh']==old['label_approx_bbox_xywh'] and new['original_object_candidates']==old['object_candidates']
   assert new['image_sha256']==old['image']['sha256'] and new['image_id']==old['image']['image_id']
   assert new['image_dimensions']==[old['image']['width'],old['image']['height']]
   assert new['quantitative_features_or_pair_scores'] is None and new['actually_viewed'] is True
   selected=[views[vid] for vid in new['view_ids'] if vid in views];assert selected
   row['current_window_measurement_qualification']=new['unit_definition_state']
   row['qualification']={'state':new['unit_definition_state'],'record':new,'source':{'file':str(W/'qualification/qualification_v1.json'),'sha256':required[str(W/'qualification/qualification_v1.json')],'json_pointer':'/rows/'+str(new['fixed_index'])}}
   row['native_views']=selected;row['feature_values']=None
  alternatives={r['locator'] for r in rows if len(r['qualification']['record']['candidate_groups'])==2};assert alternatives=={'f88r.5','f99v.6','f89r1.4','f99r.14'}
  groups=[]
  for item in qualification['canonical_group_index']:
   value=qualification
   for k in item['definition_pointer'].split('/')[1:]:value=value[int(k)] if isinstance(value,list) else value[k]
   assert value['group_id']==item['canonical_group_id']
   groups.append({'index_record':item,'definition_record':value,'feature_values':None})
  for scenario in approval['global_candidate_scenarios']:
   assert set(scenario['assignment'])==set(session['fixed_nine_loci'])
   for uid,gid in scenario['assignment'].items():assert gid in [g['group_id'] for g in new_rows[uid]['candidate_groups']]
  payload['candidate_inventory']={'canonical_groups':groups,'global_scenarios':approval['global_candidate_scenarios'],'joint_dependency_rules':qualification['joint_dependency_rules'],'approval_dependencies':approval['dependencies'],'counts_are_design_inventory_not_success':True}
  payload['feature_definitions']={'records':book['features'],'ambiguity_record':docs['feature-definition-ambiguity.json'],'coding_rules':book['coding_rules'],'matrix':None}
  payload['current_observation']={'completed_utc':qualification['completed_utc'],'exposure':qualification['exposure'],'view_summary':qualification['view_summary'],'qualification_outcome':qualification['qualification_outcome'],'old_gate_unchanged':qualification['old_gate_unchanged']}
  payload['native_view_inventory']=list(views.values());payload['phase_history']=[payload['phase_input']];payload['phase_input']=v3
  for source in sources:
   if source['url'].endswith('/method-proposal.txt'):source['label']='此前方法合同建议（保留历史待批准状态）'
   if source['url'].endswith('/qualification-approval.json'):source['label']='此前资格观察批准（另见当前测量批准）'
  payload['publication'].update({'state':v3['phase'],'stage_zh':v3['phase_zh'],'status_basis':'显式 phase_input_v3，接入冻结九处资格与候选合同；不读取进行中特征矩阵。','new_observations_in_this_page':True})
  payload['results']={'state':'NOT_IN_THIS_SNAPSHOT','values':None,'reason':'四项纸面特征编码已获批准，矩阵仍在进行且未接入本页；须完整矩阵冻结后才可按合同评分。本页没有形态值、对象对分数或比较结论。'}
  blobs['phase-input-v3.json']=v3_bytes;sources.append({'file':str(PHASE_V3_PATH),'sha256':PHASE_V3_HASH,'label':'本页候选与编码阶段快照 v3','url':'downloads/repeated-labels7h/phase-input-v3.json','repository_url':'https://github.com/HaibinLai/Voynich-manuscript/blob/main/'+str(PHASE_V3_PATH)})
 data=(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n').encode();assert not any(v in data for v in [b'/Users/',b'/private/var/',b'/home/'])
 site=ROOT/'site';out=site/'downloads/repeated-labels7h';out.mkdir(parents=True,exist_ok=True)
 for name,b in blobs.items():(out/name).write_bytes(b)
 (site/'data/repeated-labels7h.json').write_bytes(data)
 p=site/'repeated-labels7h.html';html=p.read_text();html=re.sub(r'(<meta name="repeated-labels-snapshot" content=")[^"]*',r'\g<1>'+sha(data)[:16],html)
 for ext in ['js','css']:html=re.sub(r'repeated-labels7h\.'+ext+r'\?v=[a-zA-Z0-9_-]+','repeated-labels7h.'+ext+'?v='+sha((site/f'repeated-labels7h.{ext}').read_bytes())[:16],html)
 html=re.sub(r'(<strong id="r4-stage">)[^<]*',lambda m:m.group(1)+payload['publication']['stage_zh'],html)
 is_v3=requested==PHASE_V3_PATH
 static_text={
  'r4-footer-stage':'固定九处 · 四项编码已批准 · 矩阵与分数未接入' if is_v3 else '固定九处 · 原图资格核对进行中 · 编码与评分未批准',
  'r4-result-heading':'特征矩阵与比较结果尚未接入。' if is_v3 else '形态比较未执行。',
  'r4-not-approved-title':'尚未到达的结果阶段' if is_v3 else '仍需另行批准',
  'r4-qualification-note':'本轮九处已完成候选范围核对；四处保留两个候选。条件单位资格不是唯一对象认证；形态值与分数尚未接入，不填零。' if is_v3 else '本轮逐位置结论尚未接入；待审查不是没有部件、NA 或零分，旧定位不能替代新测量资格。',
  'r4-approved-work':'九处局部候选范围已完成核对，正式批准十二个可复用图形组的四项纸面特征编码，保留全部十六种联合候选情形。特征矩阵仍在进行，本页没有形态值。' if is_v3 else '已批准全九处知情原图资格观察；逐处结论尚未接入本页。',
  'r4-not-approved':'完整矩阵冻结后才可按已批准合同计算描述量与条件范围；本页没有分数。像素相似度、物种、词义及显著性检验不在批准范围内。' if is_v3 else '形态特征编码、对象对相似度和显著性检验均未批准。'}
 for element,value in static_text.items():html=re.sub(r'(<[^>]+id="'+element+r'"[^>]*>)[^<]*',lambda m:m.group(1)+value,html)
 p.write_text(html)
 print(json.dumps({'stage':payload['publication']['stage_zh'],'fixed_loci_preserved':len(rows),'inputs_verified':len(sources),'new_observations':payload['publication']['new_observations_in_this_page'],'scores_computed':False,'data_sha256':sha(data)},ensure_ascii=False))
if __name__=='__main__':main()
