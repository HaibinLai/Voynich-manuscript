"""Post-hoc ID joins and display-mode bookkeeping only; no image or word scoring."""
import argparse,collections,datetime,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;REL=HERE.parents[1];ASTRO=REL.parent
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
FILES=['zodiac_object_relations/aggregation_v1.json','zodiac_object_relations/aggregation_output_freeze_v1.json','central_annotation_sources/crosswalk_observations_v1.json','central_annotation_sources/crosswalk_output_freeze_v1.json','central_annotation_sources/crosswalk_protocol_v1.txt']

def compute():
 a=read(ASTRO/FILES[0]);cw=read(ASTRO/FILES[2])
 assert sha(ASTRO/FILES[0])=='098146849c43435b1d612185b46b6068638e374681bce1e1f3fa1571c681b2a4'
 assert sha(ASTRO/FILES[2])=='4865fe5d0bc681a757f62cd101ddf875f856620c2c5b061b847f5887c6ddb764'
 for folder,freeze,filename in [('zodiac_object_relations',FILES[1],'aggregation_v1.json'),('central_annotation_sources',FILES[3],'crosswalk_observations_v1.json')]:
  fr=read(ASTRO/freeze);assert sha(ASTRO/folder/filename)==next(x['sha256'] for x in fr['files'] if x['path']==filename)
 annotations={r['region_uid']:r for r in cw['observations']};assert len(annotations)==len(cw['observations'])
 located={k for k,v in annotations.items() if v['match_status']=='located_candidate'}
 singles=[];partial=[];views=[];allids=[];allmodes=collections.Counter()
 for panel in a['panels']:
  f=panel['panel'];r=panel['full_frozen_report'];s=panel['full_original_seed']
  rawcomponents={v['component_uid']:('object_component_reviews',v) for v in r['object_component_reviews']}
  for v in r['discovered_supplements']:
   if 'component_uid' in v:assert v['component_uid'] not in rawcomponents;rawcomponents[v['component_uid']]=('discovered_supplements',v)
  origcomponents={v['component_uid']:v for v in s['object_components']}
  for t in r['text_records']:
   tid=t['region_uid'];allids.append(tid)
   if t['layout_association']=='single_layout_candidate':
    targets=[]
    for uid in t.get('candidate_object_ids') or []:
     src,v=rawcomponents[uid]
     targets.append({'target_uid':uid,'declared_in':src,'declared_type':v.get('component_type_observed',v.get('component_type')),'reviewed_or_declared_box_xyxy':v.get('reviewed_component_box_xyxy',v.get('box_xyxy')),'original_seed_component':origcomponents.get(uid),'target_record':v})
    singles.append({'panel':f,'region_uid':tid,'candidate_target_ids':t['candidate_object_ids'],'target_granularity_as_recorded':targets,'source_layout_association':t['layout_association'],'text_status':t['text_status'],'review_status':t['review_status'],'text_edge_level_set':sorted({e['evidence_level'] for e in r['relation_edges'] if e['edge_kind']=='text_to_object' and e['source_uid']==tid}),'annotation_crosswalk_status':annotations.get(tid,{}).get('match_status'),'is_located_annotation_candidate':tid in located,'independent_complete_annotation_reading_confirmed':annotations.get(tid,{}).get('independent_complete_reading_confirmed'),'layout_candidate_constraints':t['candidate_constraints'],'observation_facts':t['observation_facts']})
  modes=dict(sorted(collections.Counter(v['display_mode'] for v in r['view_receipts']).items()));allmodes.update(modes)
  views.append({'panel':f,'total_receipts':len(r['view_receipts']),'display_modes':modes,'view_ids_by_mode':{mode:[v['view_id'] for v in r['view_receipts'] if v['display_mode']==mode] for mode in modes}})
  for e in r['relation_edges']:
   if e['edge_kind']=='text_to_object' and e['evidence_level']=='P':
    partial.append({'panel':f,'edge_uid':e['edge_uid'],'source_uid':e['source_uid'],'target_uid':e['target_uid'],'is_located_annotation_candidate':e['source_uid'] in located,'annotation_crosswalk_status':annotations.get(e['source_uid'],{}).get('match_status'),'edge_record':e})
 assert len(allids)==len(set(allids))==322;assert set(annotations)<=set(allids)
 return {'schema':'independent_inventory_interpretation_expected_v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'method':'Exact region_uid join of two already frozen, exposed sources; post-hoc record interpretation audit, not independent annotation recognition.','fixed_regions':322,'central_crosswalk_regions':len(annotations),'located_annotation_candidate_ids':sorted(located),'all_single_layout_candidates':singles,'single_layout_candidate_count':len(singles),'single_layout_inside_located_count':sum(x['is_located_annotation_candidate'] for x in singles),'single_layout_outside_located_ids':[x['region_uid'] for x in singles if not x['is_located_annotation_candidate']],'view_counts_by_panel':views,'total_view_receipts':sum(allmodes.values()),'view_counts_by_display_mode':dict(sorted(allmodes.items())),'all_text_to_object_partial_edges':partial,'partial_edge_count':len(partial),'partial_edges_from_located_annotations':[x['edge_uid'] for x in partial if x['is_located_annotation_candidate']],'partial_edges_outside_located_annotations':[x['edge_uid'] for x in partial if not x['is_located_annotation_candidate']],'root_derivation_implementation_or_results_read_before_freeze':False,'scope':['Only the 797 object-relation view receipts are split by their explicit display_mode; the separate 29 crosswalk views are not added or relabeled.','located_candidate is source-informed localization of an annotation candidate; it does not certify a complete reading, month, date, or hand.','Target IDs/types/boxes quote source granularity; whole scenes, figures, animals and assemblies do not become equivalent roles.','Zero single_layout_candidate outside this joined set is a property of these frozen classifications, not proof of no historical text-image relation.','Partial graphic connection is not a semantic/linguistic link; no text score, image review or new translation.']}

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();assert not a.output.exists(),'Refuse overwrite'
 x=compute();a.output.mkdir(parents=True)
 inputs={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'paths_relative_to':'astronomical7h_20261118/','files':[{'path':f,'sha256':sha(ASTRO/f)} for f in FILES]}
 for n,v in [('inputs.json',inputs),('expected.json',x)]: (a.output/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
 (a.output/'calculation_freeze.json').write_text(json.dumps({'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'script_sha256':sha(Path(__file__)),'files':[{'path':n,'sha256':sha(a.output/n)} for n in ['inputs.json','expected.json']],'root_derivation_results_read':False},ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'single':x['single_layout_candidate_count'],'inside':x['single_layout_inside_located_count'],'outside':x['single_layout_outside_located_ids'],'view_modes':x['view_counts_by_display_mode'],'P_edges':x['partial_edge_count'],'P_from_annotation':x['partial_edges_from_located_annotations'],'freeze_sha256':sha(a.output/'calculation_freeze.json')},ensure_ascii=False))
if __name__=='__main__':main()
