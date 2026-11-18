"""Serialize explicitly supplied manual judgments; no inference from geometry or seed descriptions."""
from record_helpers import *
def apply_notes(panel, notes):
 d=load(panel);s=seed(panel);prepared=read(HERE/f'{panel}_prepared_views_v1.json')['views']
 for ident,(candidates,facts,constraints) in notes.items():
  uid=panel+':'+ident;record=next(r for r in d['text_records'] if r['region_uid']==uid);original=next(r for r in s['text_records'] if r['region_uid']==uid)
  vids=[uid+':V3']+[panel+':V2:'+a for a in ['1:1','1:2','2:1','2:2']]
  assert all(v in [r['view_id'] for r in d['view_receipts']] for v in vids)
  candidate_ids=[panel+':'+c for c in candidates]
  edges=[]
  for j,target in enumerate(candidate_ids,1):
   eid=uid+f':localN{j}';edges.append(eid)
   d['relation_edges'].append({'edge_uid':eid,'edge_kind':'text_to_object','source_uid':uid,'target_uid':target,'endpoint_type_pair':['writing_region','pointed_shape' if target.endswith('pointed_shape') else 'body_or_container'],'evidence_level':'N','observed_endpoint_facts':facts,'segment_ids':[],'competing_object_ids':[c for c in candidate_ids if c!=target],'crossing_resolution':None,'line_visibility_state':'no_explicit_connection_observed_in_reviewed_views','view_ids':vids,'reviewed_context_extent_xyxy':next(v['crop_xyxy_original'] for v in prepared if v['view_id']==uid+':V3'),'limitations':['Spatial organization candidate only. No glyph identity, textual anchor or semantic ownership is certified. Other objects outside reviewed context are not individually assessed.'],'semantic_identity':None,'semantic_ownership_certified':False})
  children=[r for r in s['fine_alternatives_original'] if r['coarse_parent_id']==ident]
  record.update(review_status='reviewed',viewed_view_ids=vids,text_status='writing_like',candidate_object_ids=candidate_ids,relation_edge_ids=edges,observation_facts=facts,candidate_constraints=constraints,layout_association='multiple_layout_candidates',subgroup_candidates=[{'child_id':c['id'],'original_box_xyxy':c['box_xyxy'],'original_record':c,'candidate_object_ids':candidate_ids,'assessment':'All retained split alternatives inspected in the parent local crop; no subgroup is selected as the sole parent identity. See parent facts for spatial differences; no subgroup-specific textual leader certified.'} for c in children],line_visibility_state='no_explicit_connection_observed_in_reviewed_views',reviewed_context_extent_xyxy=next(v['crop_xyxy_original'] for v in prepared if v['view_id']==uid+':V3'),unassessed_scope='Native overlapping full-panel grids provide the broader context; all other objects are reviewed_context_no_positive_evidence where visible but are not exhaustively pairwise negated. Objects outside these contexts are not_individually_assessed.',completion_or_NA_reason='Fixed text region and its retained grouping options inspected in local original-pixel crop plus wider native panel grids; no explicit text leader observed.',limitations=['N does not mean a naming relation. Lack of a leader is not lack of historical association.'])
 save(panel,d)
