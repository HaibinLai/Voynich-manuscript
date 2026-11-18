"""Bookkeeping helpers; observations are explicitly authored after actual displays."""
from pathlib import Path
import json,hashlib
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent;SOURCE=HERE.parent
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(panel,d): (HERE/f'{panel}_review_working_v1.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def load(panel):return read(HERE/f'{panel}_review_working_v1.json')
def seed(panel):return next(p for p in read(SOURCE/'seed_roster_v1.json')['panels'] if p['panel']==panel)
def initialize():
 inputs=read(SOURCE/'inputs_v1.json');panels=inputs['assignments_fixed_order']['astronomical_site'];seeds=[seed(p) for p in panels]
 (HERE/'assigned_seed_records_v1.json').write_text(json.dumps({'schema':'unaltered_assigned_seed_copy_v1','seed_sha256':sha(SOURCE/'seed_roster_v1.json'),'panels':seeds},ensure_ascii=False,indent=2)+'\n')
 for s in seeds:
  p=s['panel'];path=HERE/f'{p}_review_working_v1.json'
  if path.exists():continue
  image=next(i for i in inputs['allowed_original_images'] if i['canvas_id']==s['canvas_id'])
  d={'schema':'zodiac_object_relations_observer_panel_v1','panel':p,'observer_id':'astronomical_site','input_freeze_sha256':sha(SOURCE/'execution_freeze_v1.json'),'seed_roster_sha256':sha(SOURCE/'seed_roster_v1.json'),'original_sha256':image['sha256'],'panel_status':'not_reviewed','started_utc':None,'stopped_utc':None,'exposure_statement':'Original guided observer for several remaining panels and implementer of public comparison viewers; prior source and image reports exposed. This is background-informed relation review, not blind visual replication. No new peer relationship reports read before this panel freeze.','text_records':[],'object_component_reviews':[],'relation_edges':[],'line_segments':[],'view_receipts':[],'context_reviews':[],'discovered_supplements':[],'open_arc_notes':[],'remaining_not_reviewed_ids':[],'limitations':['No EVA transcription, word matching, semantic score or inferred historical reading direction. Original seeds remain unchanged in assigned_seed_records_v1.json.'],'no_text_matching_or_semantic_score':True}
  for r in s['text_records']:
   d['text_records'].append({'region_uid':r['region_uid'],'review_status':'not_reviewed','viewed_view_ids':[],'text_status':None,'candidate_object_ids':None,'no_candidate_reason':None,'relation_edge_ids':None,'observation_facts':None,'candidate_constraints':None,'layout_association':None,'subgroup_candidates':None,'damage_refs':[],'line_visibility_state':'not_reviewed','reviewed_context_extent_xyxy':None,'unassessed_scope':None,'completion_or_NA_reason':None,'limitations':[]})
  for r in s['object_components']:
   d['object_component_reviews'].append({'component_uid':r['component_uid'],'review_status':'not_reviewed','viewed_view_ids':[],'reviewed_component_box_xyxy':None,'component_type_observed':None,'related_edge_ids':None,'missing_component_state':None,'competing_component_ids':None,'observation_facts':None,'completion_or_NA_reason':None})
  d['remaining_not_reviewed_ids']=[r['region_uid'] for r in d['text_records']]+[r['component_uid'] for r in d['object_component_reviews']]
  save(p,d)
def add_receipts(panel,ids,displayed_at,note):
 d=load(panel);prepared=read(HERE/f'{panel}_prepared_views_v1.json')['views']
 for vid in ids:
  assert vid not in [v['view_id'] for v in d['view_receipts']]
  p=next(v for v in prepared if v['view_id']==vid)
  r={k:p[k] for k in ['view_id','plan_view_id','original_sha256','crop_xyxy_original','rotation_degrees','native_dimensions_px','view_file_sha256','display_mode']}
  r.update(displayed_at_utc=displayed_at,covered_text_uids=[x for x in p['planned_region_uids'] if '/body' not in x and '/pointed_shape' not in x],covered_component_uids=[x for x in p['planned_region_uids'] if '/body' in x or '/pointed_shape' in x],actual_coverage_note=note)
  d['view_receipts'].append(r)
 d['panel_status']='in_progress';d['started_utc']=d['started_utc'] or displayed_at;save(panel,d)
if __name__=='__main__':initialize()
