#!/usr/bin/env python3
"""Read-only publication projection for explicit frozen fourth-window phases v2-v5.
Verifies named inputs, historical phases, native view hashes and recorded numerical audits.
Does not observe images, infer live progress, or compute new scientific scores.
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
PHASE_V4_PATH=W/'publication/phase_input_v4.json'
PHASE_V4_HASH='1f0b948636bfb144e988b84f7b53908e0d64416ac60d422ad78b86ec6c8ff50d'
PHASE_V4_FINAL_PATH=W/'publication/phase_input_v4_final.json'
PHASE_V4_FINAL_HASH='db1dcb858ea15832b249bb5ad1cd365322067a8ade97cd098ee9818e115765d5'
PHASE_V5_PATH=W/'publication/phase_input_v5.json'
PHASE_V5_HASH='8d719ca6b8d5792607fba5649c544289791d9190995ff0584f989cc76b040b14'
def sha(b):return hashlib.sha256(b).hexdigest()
def project_same_leaf_supplement(result,contract,payload,review=None):
 """Validate frozen ledger against the displayed matrix; never calculate new bounds.

 Called only when a future explicit publication phase includes the final sources.
 A missing review stays pending; it cannot imply numerical verification.
 """
 assert result['schema']=='within_leaf_supplement_and_missingness_v1'
 assert contract['schema']=='same_leaf_descriptive_supplement_contract_v1'
 assert result['strata']==contract['strata']
 assert [(s['leaf'],s['same'],s['different']) for s in result['strata']]==[('f101',0,0),('f88',0,3),('f89',0,0),('f99',1,5)]
 groups={g['canonical_group_id']:g for g in payload['feature_definitions']['matrix']}
 assignments={s['id']:s['assignment'] for s in payload['candidate_inventory']['global_scenarios']}
 assert len(result['scenarios'])==16 and {s['id'] for s in result['scenarios']}==set(assignments)
 loci=[r['locator'] for r in payload['rows']];compact=[]
 for scenario in result['scenarios']:
  assert scenario['assignment']==assignments[scenario['id']]
  assert [r['locus'] for r in scenario['per_node_missingness']]==loci
  selected=set(scenario['assignment'].values())
  assert set(scenario['unique_selected_canonical_groups'])==selected
  assert scenario['unique_group_count']==len(selected) and len(selected) in [8,9]
  for row in scenario['per_node_missingness']:
   gid=scenario['assignment'][row['locus']];assert row['canonical_group']==gid
   values={fid:f['value'] for fid,f in groups[gid]['features'].items()}
   assert row['values']==values
   assert row['counts']=={'1':list(values.values()).count(1),'0':list(values.values()).count(0),'unknown':list(values.values()).count(None)}
  assert scenario['unknown_canonical_variables_by_feature']=={fid:sum(groups[g]['features'][fid]['value'] is None for g in selected) for fid in ['G1','G2','G3','G4']}
  compact.append({k:scenario[k] for k in ['id','assignment','metrics','per_node_missingness','unique_selected_canonical_groups','unique_group_count','unknown_canonical_variables_by_feature']})
 assert len(result['all_nine_same_leaf_pairs'])==9
 actual_pairs={(p['left'],p['right'],p['same_label']) for p in payload['actual_results']['pairs'] if not p['cross_leaf']}
 assert {(p['left'],p['right'],p['same_label']) for p in result['all_nine_same_leaf_pairs']}==actual_pairs
 return {'state':'POST_PRIMARY_DESCRIPTIVE_SUPPLEMENT','scope':result['scope'],'strata':result['strata'],'global_bounds':result['global_bounds'],'scenarios':compact,'interpretation':result['interpretation'],'review':review or {'state':'PENDING_FINAL_RECORD'},'source_url':'downloads/repeated-labels7h/same-leaf-results.json','contract_url':'downloads/repeated-labels7h/same-leaf-contract.json'}
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--phase-input',required=True,help='Explicit frozen phase_input_v2.json, phase_input_v3.json phase_input_v4_final.json or phase_input_v5.json; never infer live research state.');args=ap.parse_args()
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
  assert requested in [PHASE_PATH,PHASE_V3_PATH,PHASE_V4_PATH,PHASE_V4_FINAL_PATH,PHASE_V5_PATH],'Only explicit frozen phase inputs are permitted'
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
 if requested in [PHASE_V3_PATH,PHASE_V4_PATH,PHASE_V4_FINAL_PATH,PHASE_V5_PATH]:
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
 if requested in [PHASE_V4_PATH,PHASE_V4_FINAL_PATH,PHASE_V5_PATH]:
  from fractions import Fraction
  v4_bytes=(ROOT/PHASE_V4_PATH).read_bytes();assert sha(v4_bytes)==PHASE_V4_HASH;v4=json.loads(v4_bytes)
  assert v4['schema']=='fourth_primary_results_phase_input_v4'
  for inherited in v4['preserved_phase_inputs']:assert sha((ROOT/inherited['path']).read_bytes())==inherited['sha256']
  for source in v4['sources']:
   path=Path(source['path']);assert path.is_relative_to(W) and '..' not in path.parts
   b=(ROOT/path).read_bytes();assert sha(b)==source['sha256']
   assert not any(t in b for t in [b'/Users/',b'/private/var/',b'/home/'])
   name=source['download_name'];assert Path(name).name==name;blobs[name]=b
   if name.endswith('.json'):docs[name]=json.loads(b)
   sources.append({'file':str(path),'sha256':sha(b),'label':source['label'],'url':'downloads/repeated-labels7h/'+name,'repository_url':'https://github.com/HaibinLai/Voynich-manuscript/blob/main/'+str(path),'bytes':len(b)})
  observation=docs['feature-observation.json'];primary=docs['primary-bounds.json'];replay=docs['independent-replay-full.json'];receipt=docs['independent-replay-receipt.json'];comparison=docs['replay-comparison.json'];priority=docs['uncertainty-priority.json']
  assert sha(blobs['feature-observation.json'])==v4['observation_sha256']=='ddf09acc3050cc218cf08e357b0a77722e83c3f777782ff5ef86ce31ec214872'
  assert observation['status']=='FROZEN' and receipt['all_checks_passed'] is True and receipt['discrepancies']==[] and comparison['status']=='EXACT_FRACTIONS_MATCH'
  for ref in comparison['inputs']:assert sha((ROOT/W/ref['path']).read_bytes())==ref['sha256']
  assert primary['observation_source']['sha256']==replay['observation_sha256']==receipt['observation_unchanged_sha256']==v4['observation_sha256']
  frac=lambda x:Fraction(x['numerator'],x['denominator'])
  assert frac(primary['lower'])==Fraction(-5,12) and frac(primary['upper'])==Fraction(53,120)
  replay_by_id={x['id']:x for x in replay['scenarios']};assert len(replay_by_id)==16
  for sc in primary['scenarios']:
   assert frac(sc['lower'])==frac(replay_by_id[sc['id']]['bounds']['T']['lower']['value'])
   assert frac(sc['upper'])==frac(replay_by_id[sc['id']]['bounds']['T']['upper']['value'])
   assert frac(sc['lower'])<0<frac(sc['upper'])
  endpoints={}
  for side in ['lower','upper']:
   r=replay['global_bounds']['T'][side];decomp=r['decomposition_at_this_endpoint'];assert frac(decomp['T11'])+frac(decomp['T00'])==frac(decomp['T'])==frac(primary[side])
   endpoints[side]={'scenario_id':r['scenario_id'],'decomposition':decomp}
  groups={g['canonical_group_id']:g for g in observation['groups']};assert len(groups)==12 and observation['global_candidate_scenarios']==payload['candidate_inventory']['global_scenarios']
  values=[f['value'] for g in groups.values() for f in g['features'].values()];assert len(values)==48 and values.count(1)==20 and values.count(0)==7 and values.count(None)==21
  feature_receipts=docs['feature-observation-hashes.json'];feature_view_map={v['view_id']:v for v in feature_receipts['actual_native_views']}
  all_views={v['view_id']:v for v in payload['native_view_inventory']}
  for frozen in v4['native_views']:
   b=(ROOT/frozen['path']).read_bytes();assert sha(b)==frozen['sha256']
   import struct
   assert list(struct.unpack('>II',b[16:24]))==frozen['xywh'][2:]
   if frozen['view_id'] in all_views:view=all_views[frozen['view_id']]
   else:
    r=feature_view_map[frozen['view_id']];assert r['path']==frozen['path'] and r['sha256']==frozen['sha256'] and r['xywh']==frozen['xywh']
    view={**frozen,'official_full_url':'https://collections.library.yale.edu/iiif/2/'+frozen['image_id']+'/full/full/0/default.jpg','source_sha256':r['source_sha256'],'source_dimensions':r['source_dimensions'],'receipt':r}
   view['feature_observation_receipt']=feature_view_map.get(frozen['view_id'])
   view['pinned_commit']=v4['image_commit'];view['url']='https://raw.githubusercontent.com/HaibinLai/Voynich-manuscript/'+v4['image_commit']+'/'+frozen['path'];all_views[frozen['view_id']]=view
  assert len(all_views)==21
  for g in groups.values():
   assert set(g['features'])=={'G1','G2','G3','G4'}
   for f in g['features'].values():
    assert f['value'] in [0,1,None] and f['allowed']==([0,1] if f['value'] is None else [f['value']])
    for vid in f['view_ids']:assert vid in all_views
  for group in payload['candidate_inventory']['canonical_groups']:group['feature_values']=groups[group['index_record']['canonical_group_id']]['features']
  for row in rows:
   ids=[g['group_id'] for g in row['qualification']['record']['candidate_groups']]
   row['feature_values']={gid:groups[gid]['features'] for gid in ids}
   visible_ids=list(dict.fromkeys([v['view_id'] for v in row['native_views']]+[vid for gid in ids for f in groups[gid]['features'].values() for vid in f['view_ids']]))
   row['native_views']=[all_views[vid] for vid in visible_ids]
  assert len(priority['records'])==25 and all(len(r['outcomes'])==2 for r in priority['records'])
  assert priority['all_single_resolution_outcomes_contain_zero'] is True
  assert all(frac(o['lower'])<=0<=frac(o['upper']) for r in priority['records'] for o in r['outcomes'])
  payload['feature_definitions']['matrix']=observation['groups']
  payload['actual_results']={'lower':primary['lower'],'upper':primary['upper'],'scenarios':[{'id':x['id'],'lower':x['lower'],'upper':x['upper'],'features':[{'feature':f['feature'],'lower':f['lower'],'upper':f['upper']} for f in x['features']]} for x in primary['scenarios']],'pairs':primary['pairs'],'coverage':observation['availability_only_counts'],'endpoints':endpoints,'bound_type':primary['bound_type'],'limits':primary['limits'],'observation_exposure':observation['exposure'],'measurement_method':observation['measurement_method'],'numerical_review':{'comparison':comparison,'receipt':receipt,'full_replay_url':'downloads/repeated-labels7h/independent-replay-full.json','full_replay_sha256':sha(blobs['independent-replay-full.json'])},'visual_evidence_review':v4['visual_evidence_review'],'known_language_control':v4['known_language_control'],'uncertainty_planning':{'question_count':25,'outcome_count':50,'all_outcomes_still_span_zero':True,'interpretation':priority['interpretation'],'source_url':'downloads/repeated-labels7h/uncertainty-priority.json'}}
  assert len(payload['actual_results']['pairs'])==36
  payload['native_view_inventory']=list(all_views.values());payload['phase_history'].append(payload['phase_input']);payload['phase_input']=v4
  payload['publication'].update({'state':v4['phase'],'stage_zh':v4['phase_zh'],'status_basis':'冻结观察与主结果，独立数值复算最终收据；视觉证据复核另行等待。'})
  payload['results']={'state':'COMPUTED_NUMERICALLY_REPLAYED','values':{'lower':primary['lower'],'upper':primary['upper']},'reason':'主量在固定候选与未知值的代数放宽中可正可负，全部十六候选情形均跨零。不是统计置信区间，也不证明图文关系不存在。'}
  blobs['phase-input-v4.json']=v4_bytes;sources.append({'file':str(PHASE_V4_PATH),'sha256':PHASE_V4_HASH,'label':'实际结果展示冻结输入 v4','url':'downloads/repeated-labels7h/phase-input-v4.json','repository_url':'https://github.com/HaibinLai/Voynich-manuscript/blob/main/'+str(PHASE_V4_PATH)})
 if requested in [PHASE_V4_FINAL_PATH,PHASE_V5_PATH]:
  final_bytes=(ROOT/PHASE_V4_FINAL_PATH).read_bytes();assert sha(final_bytes)==PHASE_V4_FINAL_HASH;final=json.loads(final_bytes)
  assert final['base_phase']=={'path':str(PHASE_V4_PATH),'sha256':PHASE_V4_HASH}
  for source in final['sources']:
   path=Path(source['path']);assert path.is_relative_to(W) and '..' not in path.parts;b=(ROOT/path).read_bytes();assert sha(b)==source['sha256']
   assert not any(t in b for t in [b'/Users/',b'/private/var/',b'/home/'])
   name=source['download_name'];assert Path(name).name==name;blobs[name]=b
   if name.endswith('.json'):docs[name]=json.loads(b)
   sources.append({'file':str(path),'sha256':sha(b),'label':name,'url':'downloads/repeated-labels7h/'+name,'repository_url':'https://github.com/HaibinLai/Voynich-manuscript/blob/main/'+str(path)})
  audit=docs['visual-evidence-review.json'];assert audit['input_sha256']==v4['observation_sha256'] and audit['concrete_disagreements']==[]
  assert audit['scope']['positive_cells_reviewed']==20 and audit['scope']['zero_cells_reviewed']==7 and audit['scope']['null_cells_not_recoded']==21
  for cell in audit['cells']:assert groups[cell['canonical_group_id']]['features'][cell['feature']]['value']==cell['frozen_value']
  payload['actual_results']['visual_evidence_review']={'state':'COMPLETE_WITH_LIMITS','summary_zh':audit['conclusion'],'record':audit,'source_url':'downloads/repeated-labels7h/visual-evidence-review.json'}
  control=docs['control-observation.json'];cr=docs['control-results.json'];ci=docs['control-independent-results.json'];cc=docs['control-replay-comparison.json'];creceipt=docs['control-independent-receipt.json']
  assert sha(blobs['control-observation.json'])=='0e5b9a0f22f5777d7b05749460e869aab5b13908c938f708b0e4e2c9d2d0e202'
  assert cc['status']=='EXACT_FRACTIONS_MATCH' and creceipt['discrepancies']==[] and creceipt['pooled_with_voynich'] is False
  assert len(control['rows'])==4 and len(cr['features'])==4 and len(cr['pairs'])==6
  cv=[f['value'] for row in control['rows'] for f in row['features'].values()];assert len(cv)==16 and cv.count(1)==11 and cv.count(0)==1 and cv.count(None)==4
  for key in ['C','C11','C00']:
   for side in ['lower','upper']:assert frac(cr['bounds'][key][side])==frac(ci['bounds'][key][side]['value'])
  assert frac(cr['bounds']['C']['lower'])==Fraction(-1,4) and frac(cr['bounds']['C']['upper'])==0
  for f in cr['features'][:3]:assert frac(f['bounds']['C']['lower'])==frac(f['bounds']['C']['upper'])==0
  payload['actual_results']['known_language_control']={'state':'FROZEN_REPLAY_MATCHED','bounds':cr['bounds'],'features':[{'feature':f['feature'],'lower':f['bounds']['C']['lower'],'upper':f['bounds']['C']['upper']} for f in cr['features']],'coverage':{'opportunities':16,'one':11,'zero':1,'unknown':4},'blocking':cr['blocking'],'limits':cr['limits'],'exposure':control['exposure'],'rows':[{'id':row['id'],'historical_name':row['historical_name'],'name_status':row['name_status'],'unit_definition':row['unit_definition'],'source_image_url':row['source_image_url'],'source_image_sha256':row['source_image_sha256'],'features':row['features']} for row in control['rows']],'replay_comparison':cc,'replay_receipt':creceipt}
  payload['plan_update_text']=blobs['plan-update.txt'].decode()
  payload['phase_history'].append(payload['phase_input']);payload['phase_input']=final
  payload['publication'].update({'state':final['phase'],'stage_zh':final['phase_zh'],'status_basis':'冻结主结果、独立数值复算、有限视觉复核与单独报告的条件对照；原观察未改。'})
  blobs['phase-input-v4-final.json']=final_bytes;sources.append({'file':str(PHASE_V4_FINAL_PATH),'sha256':PHASE_V4_FINAL_HASH,'label':'v4 最终展示冻结输入','url':'downloads/repeated-labels7h/phase-input-v4-final.json','repository_url':'https://github.com/HaibinLai/Voynich-manuscript/blob/main/'+str(PHASE_V4_FINAL_PATH)})
 if requested==PHASE_V5_PATH:
  v5_bytes=(ROOT/PHASE_V5_PATH).read_bytes();assert sha(v5_bytes)==PHASE_V5_HASH;v5=json.loads(v5_bytes)
  assert v5['schema']=='fourth_same_leaf_and_followup_publication_input_v5'
  assert v5['base_phase']=={'path':str(PHASE_V4_FINAL_PATH),'sha256':PHASE_V4_FINAL_HASH}
  assert v5['old_primary_and_control_unchanged'] is True
  v5_paths={s['path']:s['sha256'] for s in v5['sources']};assert len(v5_paths)==len(v5['sources'])==28
  for source in v5['sources']:
   path=Path(source['path']);assert path.is_relative_to(W) and '..' not in path.parts
   b=(ROOT/path).read_bytes();assert sha(b)==source['sha256'] and len(b)==source['bytes']
   assert not any(t in b for t in [b'/Users/',b'/private/var/',b'/home/'])
   name=source['download_name'];repo_url='https://github.com/HaibinLai/Voynich-manuscript/blob/main/'+str(path)
   if name:
    assert Path(name).name==name and name not in blobs;blobs[name]=b
    if name.endswith('.json'):docs[name]=json.loads(b)
   sources.append({'file':str(path),'sha256':sha(b),'label':source['label'],'url':'downloads/repeated-labels7h/'+name if name else repo_url,'repository_url':repo_url,'bytes':len(b),'delivery':'download' if name else 'repository_only'})
  supplement=docs['same-leaf-results.json'];contract=docs['same-leaf-contract.json'];comparison=docs['same-leaf-comparison.json'];missingness=docs['same-leaf-missingness-comparison.json'];receipt=docs['same-leaf-independent-receipt.json']
  assert supplement['contract_sha256']==receipt['contract_sha256']==sha(blobs['same-leaf-contract.json'])
  assert supplement['implementation_sha256']==v5_paths[str(W/'same_leaf_supplement_v1/calculate.py')]
  assert comparison['status']=='EXACT_FRACTIONS_MATCH' and missingness['status']=='EXACT_MATCH' and missingness['discrepancies']==receipt['discrepancies']==[]
  for ref in comparison['inputs']:assert v5_paths[str(W/'same_leaf_supplement_v1'/ref['path'])]==ref['sha256']
  for ref in missingness['inputs']:assert v5_paths[str(W/ref['path'])]==ref['sha256']
  assert all(receipt['supplemental_direct_weight_checks'][k] is True for k in ['all_feature_endpoint_assignments_legal','direct_pair_weight_scores_match','all_candidate_feature_averages_match','global_full_candidate_envelope_matches'])
  for ref in receipt['files']:assert v5_paths[str(W/ref['path'])]==ref['sha256']
  for manifest,key in [('reproduction-manifest.json','inputs'),('same-leaf-reproduction-manifest.json','files')]:
   for ref in docs[manifest][key]:
    path=W/ref['path'];assert '..' not in path.parts and path.is_relative_to(W)
    assert sha((ROOT/path).read_bytes())==ref['sha256']
  assert docs['public-replay-receipt.json']['status']=='REPLAY_MATCHES_SAVED_RESULTS'
  assert docs['public-replay-receipt.json']['inputs_unchanged'] is True
  assert docs['public-replay-receipt.json']['manifest_sha256']==sha(blobs['reproduction-manifest.json'])
  assert docs['same-leaf-public-replay-receipt.json']['status']=='CLEAN_COPY_REPLAY_MATCHES_SAVED_RESULTS'
  assert docs['same-leaf-public-replay-receipt.json']['manifest_sha256']==sha(blobs['same-leaf-reproduction-manifest.json'])
  assert docs['same-leaf-public-replay-receipt.json']['original_files_unchanged'] is True
  assert all(c['exact_bytes_match'] is True for c in docs['same-leaf-public-replay-receipt.json']['checks'])
  payload['same_leaf_supplement']=project_same_leaf_supplement(supplement,contract,payload,{'state':'EXACT_FRACTIONS_MATCH','numerical_comparison':comparison,'missingness_comparison':missingness,'independent_receipt':receipt,'public_replay_receipt':docs['same-leaf-public-replay-receipt.json']})
  assert frac(supplement['global_bounds']['D99']['lower']['value'])==Fraction(-11,20) and frac(supplement['global_bounds']['D99']['upper']['value'])==Fraction(7,10)
  followup=docs['followup-eligibility.json'];ff=docs['followup-output-freeze.json']
  assert sha(blobs['followup-output-freeze.json'])=='483f7f2816f70a4d03294c15100104f9bb29a22072000179a1b210ef525a9daf'
  for packet in [ff,docs['followup-input-freeze.json']]:
   for ref in packet['files']:assert v5_paths[str(W/'known_language_followup_v1'/ref['path'])]==ref['sha256']
  assert followup['input_freeze_sha256']==sha(blobs['followup-input-freeze.json']) and followup['candidate_roster_sha256']==sha(blobs['followup-candidate-roster.json'])
  assert followup['status']=='bounded_eligibility_completed_no_scoring' and followup['all_candidates_retained'] is True and followup['replacements']==[]
  assert [r['id'] for r in followup['rows']]==['F01','F02','F03','F04','F05','F06'] and all(r['morphology_coded'] is False for r in followup['rows'])
  assert followup['old_control_unchanged']['sha256']==sha(blobs['control-observation.json']) and followup['old_control_unchanged']['matches_prior_freeze'] is True
  payload['known_language_followup']={'state':'ELIGIBILITY_ONLY_NO_SCORING','record':followup,'source_url':'downloads/repeated-labels7h/followup-eligibility.json','report_url':'downloads/repeated-labels7h/followup-eligibility.txt'}
  payload['public_replay']={'receipt':docs['public-replay-receipt.json'],'manifest':docs['reproduction-manifest.json'],'same_leaf_receipt':docs['same-leaf-public-replay-receipt.json'],'sources':[s for s in sources if s['file'] in [str(W/'REPRODUCE_PUBLIC.txt'),str(W/'same_leaf_supplement_v1/REPRODUCE_PUBLIC.txt'),str(W/'reproduce_public.py'),str(W/'same_leaf_supplement_v1/reproduce_public.py')]]}
  payload['phase_history'].append(payload['phase_input']);payload['phase_input']=v5
  payload['publication'].update({'state':v5['phase'],'stage_zh':v5['phase_zh'],'status_basis':'原主结果和四例对照保持不变；另列冻结的事后同叶描述及六例资格记录，后者没有形态评分。'})
  blobs['phase-input-v5.json']=v5_bytes;sources.append({'file':str(PHASE_V5_PATH),'sha256':PHASE_V5_HASH,'label':'v5 最终增量冻结输入','url':'downloads/repeated-labels7h/phase-input-v5.json','repository_url':'https://github.com/HaibinLai/Voynich-manuscript/blob/main/'+str(PHASE_V5_PATH)})
 data=(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n').encode();assert not any(v in data for v in [b'/Users/',b'/private/var/',b'/home/'])
 site=ROOT/'site';out=site/'downloads/repeated-labels7h';out.mkdir(parents=True,exist_ok=True)
 for name,b in blobs.items():(out/name).write_bytes(b)
 (site/'data/repeated-labels7h.json').write_bytes(data)
 p=site/'repeated-labels7h.html';html=p.read_text();html=re.sub(r'(<meta name="repeated-labels-snapshot" content=")[^"]*',r'\g<1>'+sha(data)[:16],html)
 for ext in ['js','css']:html=re.sub(r'repeated-labels7h\.'+ext+r'\?v=[a-zA-Z0-9_-]+','repeated-labels7h.'+ext+'?v='+sha((site/f'repeated-labels7h.{ext}').read_bytes())[:16],html)
 html=re.sub(r'(<strong id="r4-stage">)[^<]*',lambda m:m.group(1)+payload['publication']['stage_zh'],html)
 is_v3=requested in [PHASE_V3_PATH,PHASE_V4_PATH,PHASE_V4_FINAL_PATH,PHASE_V5_PATH]
 static_text={
  'r4-footer-stage':'固定九处 · 四项编码已批准 · 矩阵与分数未接入' if is_v3 else '固定九处 · 原图资格核对进行中 · 编码与评分未批准',
  'r4-result-heading':'特征矩阵与比较结果尚未接入。' if is_v3 else '形态比较未执行。',
  'r4-not-approved-title':'尚未到达的结果阶段' if is_v3 else '仍需另行批准',
  'r4-qualification-note':'本轮九处已完成候选范围核对；四处保留两个候选。条件单位资格不是唯一对象认证；形态值与分数尚未接入，不填零。' if is_v3 else '本轮逐位置结论尚未接入；待审查不是没有部件、NA 或零分，旧定位不能替代新测量资格。',
  'r4-approved-work':'九处局部候选范围已完成核对，正式批准十二个可复用图形组的四项纸面特征编码，保留全部十六种联合候选情形。特征矩阵仍在进行，本页没有形态值。' if is_v3 else '已批准全九处知情原图资格观察；逐处结论尚未接入本页。',
  'r4-not-approved':'完整矩阵冻结后才可按已批准合同计算描述量与条件范围；本页没有分数。像素相似度、物种、词义及显著性检验不在批准范围内。' if is_v3 else '形态特征编码、对象对相似度和显著性检验均未批准。'}
 if requested in [PHASE_V4_PATH,PHASE_V4_FINAL_PATH,PHASE_V5_PATH]:
  static_text.update({'r4-footer-stage':'固定九处 · 数值已精确复算 · 视觉证据复核待完成','r4-result-heading':'主范围 −5/12 至 53/120，全部候选情形跨零。','r4-approved-work':'已完成十二组四项特征记录，并计算全部十六候选情形及三十六对象对。独立实现已精确复算；未知值与既有候选全部保留。','r4-not-approved-title':'仍不能推出什么','r4-not-approved':'结果不是物种、词义或破译认证；代数外界不是置信区间或 p 值。视觉证据复核仍待正式记录。','r4-qualification-note':'局部候选范围有条件成立，不是唯一文字归属。九处全部保留；未知特征以未知显示，不填零。'})
 if requested in [PHASE_V4_FINAL_PATH,PHASE_V5_PATH]:
  static_text.update({'r4-footer-stage':'主结果与条件对照已复算 · 视觉复核保留测量限度','r4-not-approved':'视觉复核未提出明确改码反例，但G3缺最大宽度截线坐标；只支持图像相容，不是独立精密测量认证。结果不认证物种或词义。'})
 for element,value in static_text.items():html=re.sub(r'(<[^>]+id="'+element+r'"[^>]*>)[^<]*',lambda m:m.group(1)+value,html)
 p.write_text(html)
 print(json.dumps({'stage':payload['publication']['stage_zh'],'fixed_loci_preserved':len(rows),'inputs_verified':len(sources),'new_observations':payload['publication']['new_observations_in_this_page'],'scores_in_snapshot':bool(payload.get('actual_results')), 'builder_computes_new_scores':False,'data_sha256':sha(data)},ensure_ascii=False))
if __name__=='__main__':main()
