#!/usr/bin/env python3
# coding: utf-8
"""Project only explicit frozen publication inputs. No image access or scientific computation."""
import argparse,hashlib,json,re,itertools
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from hierarchical_k_projection import make_k_view, verify_frozen_k_comparison
from hierarchical_f_projection import make_f_view
from hierarchical_outer_projection import validate_root_outer, verify_outer_comparison
ROOT=Path(__file__).resolve().parent.parent
W=Path('research/research_next/hierarchical7h_20261119')
PHASE=W/'publication/phase_input_v1.json'
PHASE3_SHA='205cdcb3c05976c9e2c747685329d61969a81d63fc4e7ae9abd073e299fa497e'
PHASE_SHA='a9e07c17c98181c5e8790e75c8adc81b5ba03371ad3e5cfffb8a1d0c8506ad49'
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--phase-input',required=True);args=ap.parse_args();p=Path(args.phase_input)
 if p.is_absolute():p=p.resolve().relative_to(ROOT)
 versions={PHASE:(1,PHASE_SHA),W/'publication/phase_input_v2.json':(2,'1f8f3cd1d5cd986062b575aabef23dbe12e1166b7eaa8644bdcfcedb49172002')}
 versions[W/'publication/phase_input_v3.json']=(3,PHASE3_SHA)
 assert p in versions
 version,phase_sha=versions[p];phase_bytes=(ROOT/p).read_bytes();assert sha(phase_bytes)==phase_sha;phase=json.loads(phase_bytes)
 assert phase['schema']=={1:'hierarchical_initial_publication_phase_v1',2:'hierarchical_K_publication_phase_v2',3:'hierarchical_F_outer_publication_phase_v3'}[version] and phase['K_results_included'] is (version>=2)
 sources=[];docs={};blobs={};hashes={s['path']:s['sha256'] for s in phase['sources']};assert len(hashes)==len(phase['sources'])==({1:14,2:42}.get(version,phase.get('explicit_source_count')))
 for src in phase['sources']:
  path=Path(src['path']);assert path.is_relative_to(W) and '..' not in path.parts and not path.is_absolute()
  b=(ROOT/path).read_bytes();assert sha(b)==src['sha256'] and len(b)==src['bytes']
  if path.suffix.lower() in {'.png','.svg','.jpg','.jpeg','.webp','.tif','.tiff'}:
   assert version==3 and str(path.relative_to(W)) in {'artificial_collision_figure_v1/artificial-local-count-collision.svg','artificial_collision_figure_v1/artificial-local-count-collision.png'}
  assert not any(s in b for s in [b'/Users/',b'/home/',b'/private/var/',b'/var/folders/',b'/opt/miniconda',b'ghp_',b'github_pat_'])
  name=src['download_name'];assert Path(name).name==name and name not in blobs;blobs[name]=b
  if name.endswith('.json'):docs[name]=json.loads(b)
  sources.append({'file':str(path),'sha256':sha(b),'label':src['label'],'url':'downloads/hierarchical7h/'+name,'repository_url':'https://github.com/HaibinLai/Voynich-manuscript/blob/main/'+str(path)})
 session=docs['session.json'];start=datetime.fromisoformat(session['start_utc'].replace('Z','+00:00'));end=datetime.fromisoformat(session['planned_deadline_utc'].replace('Z','+00:00'));assert end-start==timedelta(hours=7)
 assert session['development_ids']==['K01','K02','K03','K04'] and session['followup_ids']==['F01','F02','F03','F04','F05','F06']
 approval=docs['k-approval.json'];assert approval['status']=='APPROVED_K_DEVELOPMENT_ONLY' and approval['scope']==session['development_ids']
 assert approval['F_image_coding_authorized'] is approval['actual_name_scores_authorized'] is approval['Voynich_new_scoring_authorized'] is False
 for ref in approval['inputs']:assert hashes[str(W/ref['path'])]==ref['sha256']
 q=docs['source-qualification.json'];assert [r['id'] for r in q['rows']]==session['followup_ids'] and q['all_six_preserved'] is True and q['replacements']==[]
 assert q['image_availability_result']['better_morgan_source_obtained'] is False and q['image_availability_result']['new_image_views']==0
 for ref in docs['source-qualification-receipt.json']['files']:assert hashes[str(W/ref['path'])]==ref['sha256']
 correction=docs['source-wording-correction.json'];assert correction['source_sha256']==hashes[str(W/'source_qualification_v1.json')] and correction['pointer']=='/dependency_and_exposure/2' and q['dependency_and_exposure'][2]==correction['old_value']
 dependencies=q['dependency_and_exposure'][:];dependencies[2]=correction['corrected_value']
 proposal=docs['method-proposal.json'];review=docs['method-review.json'];assert review['proposal_sha256']==hashes[str(W/'method_proposal_v1.json')]
 naming=proposal['fixed_naming_branches'];pairs=naming['all_pairs'];assert len(pairs)==15 and {tuple(x['ids']) for x in pairs}==set(itertools.combinations(session['followup_ids'],2))
 primary=[r for r in pairs if r['role']=='conditional_primary'];assert len(primary)==6 and sum(r['conditional_name_relation']=='same' for r in primary)==2
 assert naming['conditional_primary']['same_denominator']==2 and naming['conditional_primary']['different_denominator']==4 and naming['strict_complete_visual_name']['H'] is None
 assert len(docs['prior-art.json']['entries'])==3
 rows=[]
 for r in q['rows']:
  assert r['morphology_coded'] is False and r['fifth_window_qualification']['new_morphology_coding'] is False
  rows.append({k:r[k] for k in ['id','manuscript','folio','raw_visible_name','raw_notation','expanded_candidate','catalogue_name','complete_name_support','text_role','unit_description','unit_approx_xywh','source_image_sha256','source_dimensions','official_image_url','limitations','fifth_window_qualification'] if k in r}|{'catalogue_url':r.get('catalogue_url'),'current_morphology':None,'current_score':None})
 blobs[f'phase-input-v{version}.json']=phase_bytes;sources.append({'file':str(p),'sha256':phase_sha,'label':f'本页第{version}版冻结输入','url':f'downloads/hierarchical7h/phase-input-v{version}.json','repository_url':'https://github.com/HaibinLai/Voynich-manuscript/blob/main/'+str(p)})
 payload={'schema':'hierarchical_window_page_v1','phase':phase,'session':session,'window':{'start_utc':session['start_utc'],'deadline_utc':session['planned_deadline_utc'],'start_chicago':start.astimezone(ZoneInfo('America/Chicago')).isoformat(),'deadline_chicago':end.astimezone(ZoneInfo('America/Chicago')).isoformat()},'approval':approval,'rows':rows,'source_dependencies_corrected':dependencies,'wording_correction':correction,'source_availability':q['image_availability_result'],'naming':naming,'method':{'representation':proposal['minimal_representation'],'signature':proposal['primary_signature'],'dependencies':proposal['candidate_dependencies'],'primary_quantity':proposal['one_primary_quantity'],'gate':proposal['development_and_gate'],'diagnostics':proposal['information_loss_and_pre_score_diagnostics']},'method_review':review,'execution_addendum_text':blobs['execution-addendum.txt'].decode(),'prior_art':docs['prior-art.json']['entries'],'plan_text':blobs['plan.txt'].decode(),'results':{'state':'NOT_INCLUDED_NOT_COMPUTED_BY_PAGE','K_development':None,'F_observability':None,'H':None,'H4':None,'return_to_voynich':None,'reason':'Only K development is approved; ongoing observations are excluded. No new scores or translations.'},'sources':sources}
 if version>=2:
  verified=verify_frozen_k_comparison(docs,hashes,str(W))
  f=docs['f-approval.json'];decision=docs['k-development-decision.json']
  assert f['schema']=='root_F_observation_approval_v1' and f['status']=='APPROVED_ALL_SIX_OBSERVATION_ONLY_FINAL_METHOD_FROZEN'
  assert f['fixed_order']==session['followup_ids'] and f['actual_name_scores_authorized'] is False and f['Voynich_new_encoding_or_scores_authorized'] is False
  for ref in f['frozen_inputs']+decision['evidence']:assert hashes[str(W/ref['path'])]==ref['sha256']
  assert decision['decision']=='RETAIN_ORIGINAL_SCIENTIFIC_RULES_FOR_FIXED_SIX_F' and decision['scientific_development_revisions_used']==0 and decision['K_name_scores_computed'] is False
  observation_hash=hashes[str(W/'K_development_v1/observation_v1.json')]
  for name in ['k-root-visual-review.json','k-root-source-audit.json']:assert docs[name]['observation_sha256']==observation_hash
  assert docs['k-root-source-audit.json']['all_checks_pass'] is True and docs['k-root-visual-review.json']['recode_required_by_identified_counterexample'] is False
  assert docs['k-root-source-audit.json']['script_sha256']==hashes[str(W/'K_development_v1/audit_records_v1.py')]
  payload['k_view']=make_k_view(docs['k-observation.json'],docs['k-root-projection.json'],docs['k-projection-comparison.json'],sources)
  payload['k_view']['independent_review_state']=verified['state'];payload['k_view']['verified_comparison']=verified
  payload['k_clarifications_text']=blobs['k-record-clarifications.txt'].decode()
  payload['k_review_summary']={k:docs[k] for k in ['k-development-decision.json','k-root-source-audit.json','k-root-visual-review.json']}
  payload['f_approval']=f;payload['f_final_contract_text']=blobs['f-final-contract.txt'].decode()
  payload['results'].update(state='K_FROZEN_PROJECTED_F_RESULTS_NOT_INCLUDED',K_development={'domain_sizes':[1,27,9,2],'all_entry_constant_coordinates':{'Q0':2},'common_signatures':[],'name_scores':None},reason='K records and joint domains frozen and reviewed. All six F observations approved; this snapshot includes no frozen F morphology or name scores.')
 if version==3:
  payload['f_view']=make_f_view(docs,hashes,str(W))
  payload['outer_results'],outer_source_check=validate_root_outer(docs,hashes,str(W))
  outer_comparison=verify_outer_comparison(docs,hashes,str(W))
  privacy=docs['f-public-replay-privacy-correction.json']
  assert privacy['schema']=='F_public_replay_privacy_correction_v1' and privacy['scientific_values_source_and_result_hashes_unchanged'] is True and privacy['frozen_scientific_files_modified'] is False
  assert privacy['current_redacted_receipt_sha256']==hashes[privacy['public_receipt_path']] and privacy['txt_sha256_unchanged']==hashes[privacy['txt_path']]
  replay=docs['outer-public-replay-acceptance.json']
  assert replay['schema']=='outer_public_replay_acceptance_v1' and replay['status']=='PASS_MINIMAL_GIT_EXPORT_FULL_BYTE_REPLAY' and replay['command_exit_code']==0
  assert replay['private_pixels_accessed'] is False and replay['science_or_approval_or_input_or_result_modified'] is False and replay['all15_pairs_and_both_states_and_union_reproduced'] is True
  assert replay['runtime_file_count']==14 and len(replay['runtime_inventory'])==14 and replay['comparator_receipt']==outer_comparison
  for item in replay['runtime_inventory']:assert hashes[item['path']]==item['sha256']
  assert hashes[replay['instruction']['path']]==replay['instruction']['sha256']
  assert len(replay['full_reference_comparisons'])==3
  for item in replay['full_reference_comparisons']:
   assert item['bytes_equal'] is item['full_json_equal'] is True and item['differences']==[] and item['fields_ignored']==[]
   assert item['actual_sha256']==item['reference_sha256']==hashes[item['reference_git_path']]
  payload['public_replay_summary']={k:replay[k] for k in ['schema','status','export_commit','interpreter','runtime_file_count','full_reference_comparisons','boundaries','privacy_redaction']}
  outcome=docs['calibration-outcome.json'];payload['calibration_outcome']=outcome
  payload['historical_outcome_v1']=docs['calibration-outcome-v1.json']
  correction=docs['calibration-count-erratum.json']
  assert correction['source_sha256']==hashes[str(W/'calibration_outcome_v2.json')]
  assert correction['pointer']=='/pair_counts/actually_scored' and correction['old_value']==outcome['pair_counts']['actually_scored']==0 and correction['corrected_value']==15 and correction['scientific_results_or_rules_changed'] is False
  payload['calibration_count_erratum']=correction
  payload['computed_pair_interval_count_display']=15
  for row,summary in zip(payload['f_view']['rows'],outcome['entries']):
   assert row['id']==summary['id'];row['summary']=summary
  for row in payload['rows']:
   row['current_morphology']={'status':'FROZEN_LOCAL_RECORD_AND_CONDITIONAL_OUTER','entry_id':row['id']}
  payload['f_review_summary']={k:docs[k] for k in ['f-root-source-audit.json','f-root-scope-timing.json','f-root-visual-review.json','f-projection-comparison.json','outer-comparison.json','outer-independent-receipt.json']}
  figure=docs['artificial-figure-receipt.json'];assert figure['manuscript_reconstruction'] is False and figure['source_sha256']==hashes[str(W/'metric_information_loss_v1.json')]
  assert figure['renderer_sha256']==hashes[str(W/'render_artificial_collision_v1.py')]
  for output in figure['outputs']:
   assert output['sha256']==sha(blobs[Path(output['path']).name])
  payload['artificial_figure']={'svg_url':'downloads/hierarchical7h/artificial-local-count-collision.svg','png_url':'downloads/hierarchical7h/artificial-local-count-collision.png','receipt':figure,'artificial_only':True}
  payload['metric_information_loss']=docs['metric-information-loss.json'];payload['metric_information_loss_text']=blobs['metric-information-loss.txt'].decode()
  preservation=docs['prior-window-preservation.json'];assert preservation['all_immutable_fourth_payload_unchanged'] is True
  payload['prior_preservation_summary']={k:preservation[k] for k in ['schema','status','baseline_commit','scope_counts','scientific_scope_from_unchanged_records','all_immutable_fourth_payload_unchanged','all_recorded_final_hashes_match','all_phase_source_hashes_match','all_pinned_pngs_match','interpretation']}
  payload['publication_manifest_url']='downloads/hierarchical7h/publication-manifest-v3.json'
  payload['results'].update(state=outcome['decision'],F_observability=outcome['entries'],H=outcome['conditional_H'],H4=outcome['conditional_H4'],H_minus_H4=outcome['H_minus_H4'],strict_literal_H=outcome['strict_literal_H'],return_to_voynich=outcome['Voynich_return'],reason='Conditional outer bounds computed under retained shared g; necessary numerical gate fails. No new Voynich score or translation.')
 b=(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n').encode();assert not any(s in b for s in [b'/Users/',b'/home/',b'/private/var/',b'/var/folders/',b'/opt/miniconda'])
 site=ROOT/'site';dest=site/'downloads/hierarchical7h';dest.mkdir(parents=True,exist_ok=True);(site/'data').mkdir(exist_ok=True)
 outputs=[]
 for name,blob in blobs.items():target=dest/name;target.write_bytes(blob);outputs.append(target)
 target=site/'data/hierarchical7h.json';target.write_bytes(b);outputs.append(target)
 html_path=site/'hierarchical7h.html';html=html_path.read_text();html=re.sub(r'(<meta name="hierarchical-snapshot" content=")[^"]*',r'\g<1>'+sha(b)[:16],html)
 display=phase.get('display',{'hero':'第五轮进行中：四个已曝光的 K 条目用于方法开发，六个 F 条目固定为后续范围。当前只批准一次 K 开发试记；尚无本轮新评分或译文。','stage_note':'本页是冻结资料快照，不是后台运行监控。K 试记结果尚未接入；F 编码、名称评分与返回伏尼契新评分均未批准。','F_note':'本快照尚未批准 F01–F06 的新图形编码。它们没有参与新方法开发，但图像和名称已经曝光，不能称为盲测试集。','result_title':'本轮结果：尚未接入','result_note':'K 开发记录尚未接入；本页没有六例F冻结形态结果或名称分数。','footer':'第五轮进行中 · 无新评分或译文 · 静态冻结快照'})
 from html import escape
 for key,element in [('hero','hero-note'),('stage_note','stage-note'),('F_note','F-note'),('result_title','result-title'),('result_note','result-note'),('footer','footer')]:html=re.sub(r'(<[^>]+id="h5-'+element+r'"[^>]*>).*?(</[^>]+>)',lambda m:m[1]+escape(display[key])+m[2],html,flags=re.S)
 html=re.sub(r'(<h1 id="h5-hero-title">).*?(</h1>)',lambda m:m[1]+escape(display.get('hero_title','先看清能记录什么，再检验名称关系。'))+m[2],html)
 for key,element in [('F_decision','f-decision'),('delivery_note','delivery-note')]:html=re.sub(r'(<p id="h5-'+element+r'">).*?(</p>)',lambda m:m[1]+escape(display.get(key,''))+m[2],html,flags=re.S)
 html=re.sub(r'(<strong id="h5-stage">).*?(</strong>)',lambda m:m[1]+escape(phase['phase_zh'])+m[2],html)
 html=re.sub(r'<section id="h5-k-results"[^>]*>', '<section id="h5-k-results"'+(' hidden' if version==1 else '')+'>',html)
 for section in ['h5-f-results','h5-artificial-section']:html=re.sub(r'<section id="'+section+r'"[^>]*>', '<section id="'+section+'"'+(' hidden' if version<3 else '')+'>',html)
 html=re.sub(r'<div id="h5-final-delivery"[^>]*>', '<div id="h5-final-delivery"'+(' hidden' if version<3 else '')+'>',html)
 for module in ['hierarchical-f-view','hierarchical-outer-view']:html=re.sub(module+r'.js\?v=[a-zA-Z0-9_-]+',module+'.js?v='+sha((site/(module+'.js')).read_bytes())[:16],html)
 html=re.sub(r'hierarchical-k-view.js\?v=[a-zA-Z0-9_-]+','hierarchical-k-view.js?v='+sha((site/'hierarchical-k-view.js').read_bytes())[:16],html)
 for ext in ['js','css']:html=re.sub(r'hierarchical7h\.'+ext+r'\?v=[a-zA-Z0-9_-]+','hierarchical7h.'+ext+'?v='+sha((site/f'hierarchical7h.{ext}').read_bytes())[:16],html)
 html=re.sub(r'(<a id="h5-publication-manifest" href=")[^"]*',lambda m:m[1]+('downloads/hierarchical7h/publication-manifest-v3.json' if version==3 else '#'),html)
 html_path.write_text(html);outputs.extend([html_path,site/'hierarchical7h.js',site/'hierarchical7h.css',site/'hierarchical-k-view.js',site/'hierarchical-f-view.js',site/'hierarchical-outer-view.js'])
 if version==3:
  implementation=[ROOT/'scripts'/name for name in ['build_hierarchical7h_page.py','hierarchical_k_projection.py','hierarchical_f_projection.py','hierarchical_outer_projection.py']]
  manifest={'schema':'hierarchical_publication_manifest_v3','phase_path':str(p),'phase_sha256':phase_sha,'inputs':phase['sources'],'implementation':[{'path':str(f.relative_to(ROOT)),'sha256':sha(f.read_bytes())} for f in implementation],'outputs':[{'path':str(f.relative_to(ROOT)),'sha256':sha(f.read_bytes()),'bytes':f.stat().st_size} for f in outputs],'private_images_exported':False,'artificial_diagram_exported':True,'self_and_build_receipt_excluded_to_avoid_recursive_hashes':True}
  mf=dest/'publication-manifest-v3.json';mf.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');outputs.append(mf)
 receipt={'schema':'hierarchical_page_build_receipt_v1','phase_path':str(p),'phase_sha256':phase_sha,'explicit_inputs_verified':len(phase['sources']),'download_count':len(blobs),'fixed_followup_rows':len(rows),'fixed_pair_count':len(pairs),'unfinished_observation_paths_read':False,'private_images_read':False,'private_images_exported':False,'artificial_diagram_exported':version==3,'new_scientific_computation':False,'K_bookkeeping_comparison':verified if version>=2 else None,'F_record_origins_verified':810 if version==3 else None,'outer_result_source_check':outer_source_check if version==3 else None,'outer_independent_comparison':outer_comparison if version==3 else None,'outputs':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size} for p in outputs]}
 (ROOT/W/f'publication/build_receipt_v{version}.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'data_sha256':sha(b),'rows':6,'pairs':15,'source_files':len(phase['sources']),'downloads':len(blobs),'K_results_included':version>=2,'F_results_included':version==3}))
if __name__=='__main__':main()
