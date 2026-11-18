"""Compare saved independent expectations with frozen root output; no imports of either implementation.
Only reads explicit saved inputs/results. Writes stdout or a newly requested output file.
"""
import argparse,collections,datetime,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;BASE=HERE.parent
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path);a=ap.parse_args()
 if a.output:assert not a.output.exists(),'Refuse overwrite'
 independent=read(HERE/'complete_v1/expected_records.json');sel=read(HERE/'complete_v1/input_selection.json');calc=read(HERE/'complete_v1/calculation_freeze.json')
 for z in calc['files']:assert sha(HERE/'complete_v1'/z['path'])==z['sha256']
 for z in sel['files']:assert sha(BASE/z['path'])==z['sha256']
 assert sha(BASE/'aggregation_input_freeze_v1.json')=='94a3a65082621c51fa81eec5850acb5689b16e324ed433019b76d2be463a0d41'
 assert sha(BASE/'aggregation_output_freeze_v1.json')=='aa454ec718520c739864d44a913c794e1f2a89614e9d4267c512c34247c43f7e'
 outer=read(BASE/'aggregation_output_freeze_v1.json')
 assert sha(BASE/'aggregation_v1.json')==next(x['sha256'] for x in outer['files'] if x['path']=='aggregation_v1.json')
 root=read(BASE/'aggregation_v1.json');seed={p['panel']:p for p in read(BASE/'seed_roster_v1.json')['panels']}
 assert not independent['pending_panels']
 stats=collections.Counter();diff=[]
 def same(expected,actual,path,family):
  stats[family+'_comparisons']+=1
  if type(expected) is not type(actual):diff.append({'path':path,'expected':expected,'actual':actual,'reason':'type'});return
  if isinstance(expected,dict):
   if set(expected)!=set(actual):diff.append({'path':path,'missing_keys':sorted(set(expected)-set(actual)),'extra_keys':sorted(set(actual)-set(expected))})
   for k in expected:
    if k in actual:same(expected[k],actual[k],path+'/'+str(k),family)
  elif isinstance(expected,list):
   if len(expected)!=len(actual):diff.append({'path':path,'expected_length':len(expected),'actual_length':len(actual)})
   for j,(x,y) in enumerate(zip(expected,actual)):same(x,y,path+'/'+str(j),family)
  elif expected!=actual:diff.append({'path':path,'expected':expected,'actual':actual})
 def edge_nested(flat):
  x={k:{} for k in ['text_to_object','body_to_pointed','other_graphic_connection']}
  for key,v in flat.items():k,l=key.split('|');x[k][l]=v
  return x
 fixed=independent['fixed_population'];obs=independent['observed_totals_only']
 exp_totals={'fixed_text_records':fixed['text_regions'],'text_records_retained':obs['text_regions'],'original_components':fixed['original_components'],'original_components_retained':obs['original_components_retained'],'additional_component_reviews':obs['additional_components'],'original_fine_alternative_units_retained':fixed['fine_alternative_records'],'declared_supplement_aliases':obs['separate_supplement_component_declarations'],'view_receipts':obs['actual_view_receipts'],'not_reviewed_or_in_progress':obs['unfinished_records']}
 same(exp_totals,root['totals'],'totals','prefrozen_counts')
 same(independent['ready_panels'],root['fixed_panel_order'],'fixed_panel_order','prefrozen_counts')
 same([],root['pending_panels'],'pending','prefrozen_counts')
 same(True,root['all_twelve_frozen_inputs_present'],'all_twelve','prefrozen_counts')
 same([],root['structural_issues'],'structural_issues','prefrozen_counts')
 same(True,root['all_structural_checks_passed'],'all_structural_checks_passed','prefrozen_counts')
 grouped={key:{} for key in ['text_review_status','text_status','layout_association','line_visibility_state']}
 for key in grouped:
  c=collections.Counter()
  for p in independent['panels']:c.update(p['observed_counts'][key])
  grouped[key]=dict(c)
 grouped['edges_by_kind_and_grade']=edge_nested(independent['global_edges_by_kind_and_level'])
 same(grouped,root['grouped_counts'],'grouped_counts','prefrozen_counts')
 rootpanels={p['panel']:p for p in root['panels']};same(len(rootpanels),len(root['panels']),'unique_root_panels','prefrozen_ids')
 all_text={t['record']['region_uid']:t for t in independent['all_ready_text_records']}
 for p,m in zip(independent['panels'],sel['panels']):
  f=p['panel'];r=rootpanels[f];o=p['observed_counts'];fix=p['fixed_counts'];orig=read(BASE/m['report_path'])
  exp={'fixed_text_records':fix['text_regions'],'text_records_retained':o['text_regions'],'original_components':fix['original_components'],'original_components_retained':o['original_components_retained'],'original_fine_alternative_units_retained':fix['fine_alternative_records'],'additional_component_reviews':o['additional_components'],'declared_supplement_aliases':o['separate_supplement_component_declarations'],'view_receipts':o['actual_view_receipts'],'not_reviewed_or_in_progress':o['unfinished_records']}
  exp.update({k:o[k] for k in ['text_review_status','text_status','layout_association','line_visibility_state']});exp['edges_by_kind_and_grade']=edge_nested(o['edge_kind_and_level'])
  same(exp,r['counts'],f+'/counts','prefrozen_counts')
  for k in ['report_path','freeze_path','report_sha256','freeze_sha256','observer']:same(m[k],r[k],f+'/'+k,'source_identity')
  rows={x['region_uid']:x for x in r['text_rows']};same(len(rows),len(r['text_rows']),f+'/unique_text_rows','prefrozen_ids');same(p['fixed_text_ids'],list(rows),f+'/text_id_order','prefrozen_ids')
  for tid in p['fixed_text_ids']:
   ex=all_text[tid];rr=rows[tid]
   same(ex['seed'],rr['original_seed_record'],tid+'/seed','prefrozen_record_preservation')
   same(ex['record'],rr['observation'],tid+'/observation','prefrozen_record_preservation')
   same(ex['actual_text_edge_level_set'],rr['text_edge_level_set'],tid+'/edge_level_set','prefrozen_counts')
   edges=[e for e in orig['relation_edges'] if e['edge_kind']=='text_to_object' and e['source_uid']==tid]
   same(edges,rr['text_edges'],tid+'/text_edges','deterministic_source_preservation')
  # These extra raw-embed checks were specified after seeing root output's schema;
  # they are exact source conservation, not another post-hoc scientific measure.
  same(seed[f],r['full_original_seed'],f+'/full_original_seed','deterministic_source_preservation')
  same(orig,r['full_frozen_report'],f+'/full_frozen_report','deterministic_source_preservation')
  image=next(z for z in read(BASE/'inputs_v1.json')['allowed_original_images'] if z['canvas_id']==seed[f]['canvas_id'])
  same({k:image[k] for k in ['canvas_id','official_url','sha256','dimensions_px']},r['original_image'],f+'/original_image','source_identity')
 same('not_evaluated_by_record_aggregation',root['semantic_qualification'],'semantic_qualification','interpretation_scope')
 out={'schema':'independent_full_aggregation_comparison_v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'all_compared_fields_equal':not diff,'difference_count':len(diff),'differences':diff,'comparison_operations':dict(stats),'prefrozen_expected_calculation':{'path':'complete_v1/calculation_freeze.json','sha256':sha(HERE/'complete_v1/calculation_freeze.json'),'created_utc':calc['created_utc']},'root_output':{'path':'../aggregation_v1.json','sha256':sha(BASE/'aggregation_v1.json'),'freeze_sha256':sha(BASE/'aggregation_output_freeze_v1.json'),'frozen_utc':outer['utc']},'all_twelve_original_reports_verified_against_pinned_selection':True,'fixed_denominators':fixed,'observed_counts':obs,'root_implementation_opened_or_imported':False,'own_expectations_frozen_before_root_results_read':True,'scope':['Prefrozen independent counts/statuses/ID and text-level-set expectations compared first.','Raw full_original_seed/full_frozen_report/text_edges/source-image embeds checked deterministically against frozen inputs after root result schema was read; not a new scientific measurement.','Other-observer image judgments are not revalidated; receipts remain reported display evidence.','E/P body-to-pointed counts do not certify text ownership; no names, readings, or text scores were computed.']}
 if a.output:write_text=json.dumps(out,ensure_ascii=False,indent=2)+'\n';a.output.write_text(write_text)
 else:print(json.dumps(out,ensure_ascii=False,indent=2))
 print(json.dumps({'all_equal':not diff,'differences':len(diff),'checks':dict(stats)},ensure_ascii=False))
if __name__=='__main__':main()
