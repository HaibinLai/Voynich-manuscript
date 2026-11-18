"""Read-only comparison with independent saved expectation; no scientific recomputation."""
import argparse,datetime,hashlib,json
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[1];A=R.parent
rd=lambda p:json.loads(p.read_text());sh=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path);args=ap.parse_args()
 if args.output:assert not args.output.exists()
 ef=rd(H/'expected_v1/calculation_freeze.json')
 for z in ef['files']:assert sh(H/'expected_v1'/z['path'])==z['sha256']
 e=rd(H/'expected_v1/expected.json');s=rd(H/'expected_v1/inputs.json')
 for z in s['files']:assert sh(A/z['path'])==z['sha256']
 inf=rd(R/'inventory_interpretation_input_freeze_v1.json');outf=rd(R/'inventory_interpretation_output_freeze_v1.json')
 assert sh(R/'inventory_interpretation_input_freeze_v1.json')==outf['input_freeze_sha256']
 for z in inf['files']:assert sh(R/z['path'])==z['sha256']
 for z in outf['files']:assert sh(R/z['path'])==z['sha256']
 p=rd(R/'inventory_interpretation_v1.json');agg=rd(R/'aggregation_v1.json');apanel={z['panel']:z for z in agg['panels']}
 diff=[];checks=[]
 def ck(label,x,y):
  checks.append(label)
  if x!=y:diff.append({'check':label,'expected':x,'actual':y})
 ck('global_view_modes',e['view_counts_by_display_mode'],p['view_modes'])
 ck('single_count',e['single_layout_candidate_count'],p['single_layout_count'])
 ck('single_located_count',e['single_layout_inside_located_count'],p['single_layout_annotation_candidate_overlap_count'])
 ck('single_outside_count',len(e['single_layout_outside_located_ids']),p['other_single_layout_count'])
 ck('all_single_ids',[z['region_uid'] for z in e['all_single_layout_candidates']],[z['region_uid'] for z in p['single_layout_regions']])
 for x,y in zip(e['all_single_layout_candidates'],p['single_layout_regions']):
  tid=x['region_uid'];seed=next(t['original_seed_record'] for t in apanel[x['panel']]['text_rows'] if t['region_uid']==tid)
  ck(tid+'/panel',x['panel'],y['panel']);ck(tid+'/targets',x['candidate_target_ids'],y['candidate_object_ids']);ck(tid+'/join',x['is_located_annotation_candidate'],y['also_external_annotation_location_candidate']);ck(tid+'/source_box',seed['original_box_xyxy'],y['original_seed_box_xyxy']);ck(tid+'/scope_flag',True,y['not_a_semantic_ownership_certificate'])
 ck('all_panel_ids',[z['panel'] for z in e['view_counts_by_panel']],[z['panel'] for z in p['panels']])
 for x,y in zip(e['view_counts_by_panel'],p['panels']):
  ck(x['panel']+'/view_modes',x['display_modes'],y['view_modes']);ck(x['panel']+'/unchanged_counts',apanel[x['panel']]['counts'],y['counts'])
 ck('all_P_edge_ids',[z['edge_uid'] for z in e['all_text_to_object_partial_edges']],[z['edge_uid'] for z in p['partial_text_edges']])
 for x,y in zip(e['all_text_to_object_partial_edges'],p['partial_text_edges']):
  for k in ['panel','edge_uid','source_uid','target_uid']:ck(x['edge_uid']+'/'+k,x[k],y[k])
  ck(x['edge_uid']+'/join',x['is_located_annotation_candidate'],y['source_also_external_annotation_location_candidate']);ck(x['edge_uid']+'/raw_edge',x['edge_record'],y['original_edge'])
 ck('P_annotation_count',len(e['partial_edges_from_located_annotations']),p['partial_text_edges_from_annotation_candidates'])
 o={'schema':'inventory_interpretation_independent_comparison_v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'all_passed':not diff,'difference_count':len(diff),'differences':diff,'named_comparisons':len(checks),'checks':checks,'expected_freeze_sha256':sh(H/'expected_v1/calculation_freeze.json'),'primary_output_sha256':sh(R/'inventory_interpretation_v1.json'),'root_source_read_after_expected_freeze':True,'root_source_imported_or_executed':False,'scope':'Only saved record ID joins/display-mode partitions/partial-edge provenance; no additional observation, recognition or semantics.'}
 t=json.dumps(o,ensure_ascii=False,indent=2)+'\n'
 if args.output:args.output.write_text(t)
 else:print(t)
 print(json.dumps({'all_passed':not diff,'differences':len(diff),'named_checks':len(checks)}))
if __name__=='__main__':main()
