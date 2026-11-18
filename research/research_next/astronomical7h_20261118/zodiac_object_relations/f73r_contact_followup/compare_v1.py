"""Compare frozen informed diagnostics without taking a maximum over candidate-edge grades."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 fixed=read(P/'input_freeze_v1.json');prep=read(P/'prepared_views_v1.json');root=read(P/'root_repeat/observation_v1.json');peer=read(P/'literature_repeat/observation_v1.json');mapping=read(P/'comparison_mapping_v1.json');source=read(P.parent/'circle_spatial_observer/f73r/observer_report_v1.json')
 for f in ['comparison_input_freeze_v1.json','comparison_mapping_freeze_v1.json']:
  for x in read(P/f)['files']:assert sha(P/x['path'])==x['sha256']
 for sub in ['root_repeat','literature_repeat']:
  for x in read(P/sub/'output_freeze_v1.json')['files']:assert sha(P/sub/x['path'])==x['sha256']
 rr={x['region_uid']:x for x in root['records']};pr={x['region_uid']:x for x in peer['records']};sr={x['region_uid']:x for x in source['text_records']}
 assert set(rr)==set(pr)==set(fixed['fixed_region_ids']) and len(rr)==9
 pv={x['view_id']:x for x in prep['views']};view_checks=[]
 for who,receipts in [('root',root['actual_view_receipts']),('peer',peer['view_receipts'])]:
  assert len(receipts)==len(pv)==27 and {x['view_id'] for x in receipts}==set(pv)
  for x in receipts:
   for k in ['region_uid','mode','crop_xyxy_original','dimensions_px','filename','sha256']:assert x[k]==pv[x['view_id']][k]
   view_checks.append({'observer':who,'view_id':x['view_id'],'sha256':x['sha256']})
 rows=[];edge_count=0
 for uid in fixed['fixed_region_ids']:
  a=rr[uid];b=pr[uid];original=[e for e in source['relation_edges'] if e['edge_kind']=='text_to_object' and e['source_uid']==uid]
  assert a['original_candidate_edges_preserved']==original==b['all_original_candidate_edges'];assert b['original_text_record']==sr[uid];assert a['original_candidate_ids_preserved']==sr[uid]['candidate_object_ids'];edge_count+=len(original)
  peredge={e['edge_uid']:e for e in b['edge_grade_comparison']};assert set(peredge)=={e['edge_uid'] for e in original}
  for e in original:
   x=peredge[e['edge_uid']];assert x['original_grade']==e['evidence_level'] and x['target_uid']==e['target_uid']
  contact=b['observation']['contact'];mapped=mapping['peer_contact_to_region_diagnostic'][contact]
  ptargets=[e for e in original if e['evidence_level']=='P'];target_comparison=[]
  for e in ptargets:
   assert e['target_uid'] in a['root_contact_target_uids']
   target_comparison.append({'original_edge_uid':e['edge_uid'],'target_uid':e['target_uid'],'root_selected_contact_region_level':a['root_region_contact_level'],'peer_that_exact_edge_level':peredge[e['edge_uid']]['followup_grade'],'levels_equal':a['root_region_contact_level']==peredge[e['edge_uid']]['followup_grade'],'scope':'Root region-level assessment of the preselected P target only; not root independent rating of every original edge.'})
  line_status=mapping['peer_line_status_to_confirmation'][b['observation']['independent_text_origin_line']]
  rows.append({'region_uid':uid,'original_record':{'text':sr[uid],'edges':original},'root_repeat':a,'other_repeat':b,'comparison':{'root_region_level':a['root_region_contact_level'],'peer_literal_contact':contact,'peer_mapped_region_level':mapped,'region_categories_compatible':a['root_region_contact_level']==mapped,'mapping_scope':'Declared literal-contact description normalization, not identical original fields or a max over edge levels.','selected_P_target_comparison':target_comparison,'root_complete_leader_confirmed':a['complete_independent_writing_leader_confirmed'],'peer_complete_leader_confirmed':line_status,'leader_confirmation_compatible':a['complete_independent_writing_leader_confirmed']==line_status,'no_historical_absence_inferred':True,'detail_scope_notes':mapping['detail_scope_notes'][uid],'original_edges_preserved':True,'root_independent_all_edges_rated':False}})
 assert edge_count==24
 out={'schema':'f73r_contact_frozen_comparison_v1','comparison_mapping_sha256':sha(P/'comparison_mapping_v1.json'),'input_freeze_sha256':sha(P/'comparison_input_freeze_v1.json'),'source_paths':{'root':'root_repeat/observation_v1.json','peer':'literature_repeat/observation_v1.json','original':'../circle_spatial_observer/f73r/observer_report_v1.json'},'fixed_pairs':fixed['pairs'],'rows':rows,'view_integrity_checks':view_checks,'summary':{'fixed_regions':len(rows),'original_candidate_edges_preserved':edge_count,'native_views_per_repeat':27,'same_original_image_not_independent_samples':True,'mapped_region_category_compatible':sum(r['comparison']['region_categories_compatible'] for r in rows),'selected_original_P_targets_compared':sum(len(r['comparison']['selected_P_target_comparison']) for r in rows),'selected_P_target_level_differences':sum(not x['levels_equal'] for r in rows for x in r['comparison']['selected_P_target_comparison']),'root_complete_leader_confirmations':sum(r['comparison']['root_complete_leader_confirmed'] is True for r in rows),'peer_complete_leader_confirmations':sum(r['comparison']['peer_complete_leader_confirmed'] is True for r in rows),'central_same_band_control':None},'limits':mapping['limits'],'no_new_text_score_or_sequence_qualification':True}
 print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
