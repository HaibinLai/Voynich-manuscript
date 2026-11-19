#!/usr/bin/env python3
"""Read-only projection of the fourth-window initial freeze. No scientific measurements.
Reads eleven initial inputs; the pinned phase input adds ten explicit sources.
Never discovers ongoing qualification or measurement outputs.
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
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--phase-input',required=True,help='Explicit frozen phase_input_v2.json. Rebuild the initial snapshot using its historical Git commit.');args=ap.parse_args()
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
  assert requested==PHASE_PATH,'Only the explicit frozen phase input is permitted'
  phase_bytes=(ROOT/requested).read_bytes();assert sha(phase_bytes)==PHASE_HASH
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
 data=(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n').encode();assert not any(v in data for v in [b'/Users/',b'/private/var/',b'/home/'])
 site=ROOT/'site';out=site/'downloads/repeated-labels7h';out.mkdir(parents=True,exist_ok=True)
 for name,b in blobs.items():(out/name).write_bytes(b)
 (site/'data/repeated-labels7h.json').write_bytes(data)
 p=site/'repeated-labels7h.html';html=p.read_text();html=re.sub(r'(<meta name="repeated-labels-snapshot" content=")[^"]*',r'\g<1>'+sha(data)[:16],html)
 for ext in ['js','css']:html=re.sub(r'repeated-labels7h\.'+ext+r'\?v=[a-zA-Z0-9_-]+','repeated-labels7h.'+ext+'?v='+sha((site/f'repeated-labels7h.{ext}').read_bytes())[:16],html)
 html=re.sub(r'(<strong id="r4-stage">)[^<]*',lambda m:m.group(1)+payload['publication']['stage_zh'],html)
 p.write_text(html)
 print(json.dumps({'stage':payload['publication']['stage_zh'],'fixed_loci_preserved':len(rows),'inputs_verified':len(sources),'new_observations':False,'scores_computed':False,'data_sha256':sha(data)},ensure_ascii=False))
if __name__=='__main__':main()
