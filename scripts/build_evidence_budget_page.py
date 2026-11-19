#!/usr/bin/env python3
# coding: utf-8
"""Copy explicit frozen records and decompress verified table shards; never run scientific engines."""
import argparse,gzip,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
W=Path('research/research_next/evidence_budget7h_20261119');P=W/'publication'
PHASE_SHA256='cbea7367b58dc409f3e6aee1b2a07e70daf52cb21b64445bcc40fd917f4667aa'
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads((ROOT/p).read_text())
def approved_draft_sources():
 names=[('session_v1.json','session.json'),('plan_v1.txt','plan.txt'),('method_proposal_v1.json','method-proposal.json'),('method_proposal_v1.txt','method-proposal.txt'),('method_review_v1.json','method-review.json'),('method_review_v1.txt','method-review.txt'),('root_information_numeric_approval_v1.json','numeric-approval.json'),('model_input_v1.json','model-input.json'),('input_comparison_v1.json','input-comparison.json'),('root_actual_v1/manifest.json','root-manifest.json'),('root_actual_v1/summary.json','root-summary.json'),('independent_actual_v1/manifest_v1.json','independent-manifest.json'),('independent_actual_v1/summary_v1.json','independent-summary.json'),('independent_actual_v1/execution_receipt_v1.json','independent-execution.json'),('root_actual_comparison_v1.json','complete-comparison.json'),('independent_actual_audit_v1.json','independent-audit.json'),('independent_actual_audit_v1.txt','independent-audit.txt'),('compare_actual_v1.py','compare-actual.py'),('independent_engine/audit_actual_v1.py','independent-audit.py'),('interpretation_report_v1.json','interpretation.json'),('interpretation_report_v1.txt','interpretation.txt')]
 names += [('REPRODUCE_v1.txt','reproduce.txt'),('public_replay_v1.py','public-replay.py'),('public_replay_inventory_v1.json','public-replay-inventory.json'),('public_replay_paths_v1.txt','public-replay-paths.txt'),('public_replay_acceptance_v1.json','public-replay-acceptance.json'),('public_replay_acceptance_v1.txt','public-replay-acceptance.txt'),('outcome_limits_v1.json','outcome-limits.json'),('outcome_limits_v1.txt','outcome-limits.txt'),('scientific_scope_review_v1.json','scientific-scope-review.json'),('scientific_scope_review_v1.txt','scientific-scope-review.txt')]
 paths={str(W/p):n for p,n in names}
 inventory=read(W/'public_replay_inventory_v1.json')
 for ref in inventory['runtime_files']+inventory['documentation_files']:
  assert sha((ROOT/ref['path']).read_bytes())==ref['sha256'];paths.setdefault(ref['path'],'reproduce-dependency-'+Path(ref['path']).relative_to(Path('research/research_next')).as_posix().replace('/','--'))
 for p in read(W/'root_information_numeric_approval_v1.json')['bound_paths'].values():paths.setdefault(str(W/p),'dependency-'+p.replace('/','--'))
 manifest=read(W/'root_actual_v1/manifest.json')
 for key,ref in manifest['sources'].items():paths[ref['path']]='prior-'+key+Path(ref['path']).suffix
 for table in manifest['tables']:paths[str(W/'root_actual_v1'/table['path'])]='original-'+Path(table['path']).name
 return [{'path':p,'sha256':sha((ROOT/p).read_bytes()),'bytes':(ROOT/p).stat().st_size,'download_name':n} for p,n in paths.items()]
def main():
 ap=argparse.ArgumentParser(description=__doc__);g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--phase-input');g.add_argument('--reviewed-draft',action='store_true');ap.add_argument('--receipt-name',default='build_receipt_v1.json',choices=['build_receipt_v1.json','build_receipt_v2.json']);args=ap.parse_args()
 if args.reviewed_draft:phase={'schema':'evidence_budget_reviewed_draft_v1','release_state':'LOCAL_REVIEWED_DRAFT_NOT_PUBLISHED','sources':approved_draft_sources()};phase_path=None
 else:
  phase_path=Path(args.phase_input);assert not phase_path.is_absolute() and phase_path.is_relative_to(P);assert phase_path==P/'phase_input_v1.json' and sha((ROOT/phase_path).read_bytes())==PHASE_SHA256;phase=read(phase_path);assert phase['schema']=='evidence_budget_publication_phase_v1' and phase['release_state']=='FROZEN_SCIENTIFIC_RESULTS_FINAL_PUBLICATION_PENDING'
 hashes={};docs={};blobs={};sources=[]
 for src in phase['sources']:
  path=Path(src['path']);assert not path.is_absolute() and '..' not in path.parts and str(path).startswith('research/research_next/')
  b=(ROOT/path).read_bytes();assert sha(b)==src['sha256'] and len(b)==src['bytes'];assert str(path) not in hashes;hashes[str(path)]=src['sha256']
  if path.suffix!='.gz':assert not any(s in b for s in [b'/Users/',b'/home/',b'/var/folders/',b'/private/var/',b'/opt/miniconda',b'ghp_',b'github_pat_']),str(path)
  name=src['download_name'];assert Path(name).name==name and name not in blobs;blobs[name]=b
  if name.endswith('.json'):docs[name]=json.loads(b)
  sources.append({'path':str(path),'sha256':sha(b),'url':'downloads/evidence-budget7h/'+name,'repository_url':'https://github.com/HaibinLai/Voynich-manuscript/blob/main/'+str(path)})
 m=docs['root-manifest.json'];summary=docs['root-summary.json'];approval=docs['numeric-approval.json'];c=docs['complete-comparison.json']
 assert m['schema']=='whole_entry_information_manifest_v1' and m['table_count']==96 and m['denominator']==32 and m['factor_f02'] is True
 assert approval['allow_real_information_analysis'] is True and approval['scientific_metric_or_name_changes']==0 and approval['new_image_coding_authorized'] is False and approval['new_Voynich_scoring_authorized'] is False
 for field,path in approval['bound_paths'].items():assert hashes[str(W/path)]==approval[field]
 assert m['approval_sha256']==hashes[str(W/'root_information_numeric_approval_v1.json')] and m['input_sha256']==hashes[str(W/'model_input_v1.json')]
 assert m['contract_sha256']==hashes[str(W/'method_proposal_v1.json')] and m['review_sha256']==hashes[str(W/'method_review_v1.json')]
 assert c['schema']=='root_complete_information_comparison_v1' and c['all_pass'] is True and c['canonical_tables_compared']==96 and c['rows_compared']==393600 and c['fields_per_row_compared']==20 and c['logical_subset_summary_records_compared']==192
 assert c['endpoint_and_predicate_witness_ids_identical'] is True and c['all_existence_guarantee_singleton_and_both_known_minima_compared'] is True
 bindings={'root_manifest_sha256':'root_actual_v1/manifest.json','independent_manifest_sha256':'independent_actual_v1/manifest_v1.json','root_summary_sha256':'root_actual_v1/summary.json','independent_summary_sha256':'independent_actual_v1/summary_v1.json','source_comparison_sha256':'input_comparison_v1.json','comparison_code_sha256':'compare_actual_v1.py','independent_audit_sha256':'independent_actual_audit_v1.json'}
 for field,path in bindings.items():assert c[field]==hashes[str(W/path)]
 assert sha(blobs['root-summary.json'])==m['summary']['sha256']
 for ref in m['sources'].values():assert hashes[ref['path']]==ref['sha256']
 ids=m['entry_order'];core=m['core_order'];assert ids==['F01','F02','F03','F04','F05','F06'] and core==['F01','F03','F04','F05','F06']
 assert m['class_code_order']==['CONFLICT','NONE_JOINT_POSITIVE','MIXED','ALL_JOINT_POSITIVE']
 replay=docs['public-replay-acceptance.json'];assert replay['schema']=='sixth_public_minimal_replay_acceptance_v1' and replay['status']=='PASS_FULL_BYTE_REPLAY' and replay['command_exit_code']==0
 assert replay['byte_differences']==replay['semantic_differences']==[] and replay['generated_table_files_compared']==192 and len(replay['full_file_comparisons'])==199
 assert replay['private_pixels_or_unlisted_working_tree_files_in_export'] is False and replay['source_runtime_files_unchanged_after_execution'] is True and replay['scientific_inputs_code_results_modified'] is False
 for field,file in [('committed_inventory_sha256','public_replay_inventory_v1.json'),('committed_paths_sha256','public_replay_paths_v1.txt'),('instruction_sha256','REPRODUCE_v1.txt')]:assert replay[field]==hashes[str(W/file)]
 assert all(x['bytes_equal'] is True and x['actual_sha256']==x['reference_sha256'] and x['fields_ignored']==[] for x in replay['full_file_comparisons'])
 old_input=docs['prior-prior_model.json'];observation=docs['prior-observation.json'];assert old_input['global_model']['variable_id']=='g_terminal_boundary'
 assert all(s['entries']['F02']==m['alphabet']['F02'] for s in old_input['states']) and m['F02_domain_size']==len(m['alphabet']['F02'])==9
 logical=[]
 for mask in range(64):
  observed=[e for i,e in enumerate(ids) if mask&(1<<i)];cm=sum(1<<i for i,e in enumerate(core) if e in observed)
  logical.append({'mask':mask,'observed_ids':observed,'core_mask':cm,'f02_observed':'F02' in observed})
 for regime in m['regimes']:
  rows=summary['regimes'][regime]['subsets'];assert [r['mask'] for r in rows]==list(range(64))
  for row,logical_row in zip(rows,logical):assert row['observed']==logical_row['observed_ids'] and row['canonical_core_mask']==logical_row['core_mask']
 outputs=[];site=ROOT/'site';dest=site/'data/evidence-budget7h';dest.mkdir(parents=True,exist_ok=True);downloads=site/'downloads/evidence-budget7h';downloads.mkdir(parents=True,exist_ok=True)
 def write(path,b):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b);outputs.append(path)
 table_manifest={};total=0
 for t in m['tables']:
  source=W/'root_actual_v1'/t['path'];compressed=blobs['original-'+Path(t['path']).name];assert hashes[str(source)]==t['sha256'] and len(compressed)==t['compressed_bytes'];b=gzip.decompress(compressed);assert sha(b)==t['uncompressed_sha256'] and len(b)==t['uncompressed_bytes'];table=json.loads(b)
  assert len(table['rows'])==t['rows'] and table['shape']==t['shape'] and table['regime']==t['regime'];assert all(len(row)==20 for row in table['rows']);total+=len(table['rows'])
  name=Path(t['path']).name.removesuffix('.gz');write(dest/'tables'/name,b)
  key=t['regime']+'/'+str(t['core_mask']);assert key not in table_manifest;table_manifest[key]={'url':'data/evidence-budget7h/tables/'+name,'sha256':sha(b),'rows':len(table['rows']),'shape':table['shape'],'observed':table['observed'],'original_gzip_path':str(source),'original_gzip_sha256':t['sha256']}
 assert total==393600 and len(table_manifest)==96
 provenance={'source_hashes':{k:m['sources'][k]['sha256'] for k in ['prior_model','observation']},'provenance_input':old_input,'observation':observation};pb=(json.dumps(provenance,ensure_ascii=False,separators=(',',':'))+'\n').encode();write(dest/'provenance.json',pb)
 data={'schema':'evidence_budget_page_v1','mode':'FROZEN_CONDITIONAL_MODEL_INFORMATION','release_state':phase['release_state'],'numeric_approval_verified':True,'research_result':True,'new_observations':False,'entry_ids':ids,'core_ids':core,'features':['Q0','Q1','Q2','QJ'],'states':[s['id'] for s in old_input['states']],'regimes':m['regimes'],'alphabet':m['alphabet'],'row_fields':m['row_fields'],'classes':m['class_code_order'],'denominator':32,'factorization':{'entry_id':'F02','domain_identical_across_g':True,'scope':m['count_decoding']},'logical_subsets':logical,'table_manifest':table_manifest,'summary':summary,'comparison':c,'interpretation':docs['interpretation.json'],'interpretation_text':blobs['interpretation.txt'].decode(),'outcome_limits_text':blobs['outcome-limits.txt'].decode(),'scientific_scope_review':docs['scientific-scope-review.json'],'public_replay_summary':{k:replay[k] for k in ['schema','status','source_commit','runtime_file_count','initial_export_file_count','generated_table_files_compared','byte_differences','independent_full_audit_rerun','limitations']},'provenance':{'url':'data/evidence-budget7h/provenance.json','sha256':sha(pb),'source_hashes':provenance['source_hashes']},'sources':sources,'session':docs['session.json'],'historical_pair_reference':'hierarchical7h.html','private_images_exported':False}
 b=(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n').encode();write(site/'data/evidence-budget7h.json',b)
 for name,blob in blobs.items():write(downloads/name,blob)
 if phase_path:write(downloads/'phase-input-v1.json',(ROOT/phase_path).read_bytes())
 html=site/'evidence-budget7h.html';text=html.read_text();text=re.sub(r'(<meta name="evidence-budget-snapshot" content=")[^"]*',lambda z:z[1]+sha(b)[:16],text)
 for name in ['evidence-budget7h.js','evidence-budget7h.css','evidence-budget-adapter.js']:text=re.sub(re.escape(name)+r'\?v=[a-zA-Z0-9_-]+',name+'?v='+sha((site/name).read_bytes())[:16],text)
 write(html,text.encode());outputs.extend(site/name for name in ['evidence-budget7h.js','evidence-budget7h.css','evidence-budget-adapter.js','index.html','homepage.js','style.css','favicon.svg'])
 manifest={'schema':'evidence_budget_site_output_manifest_v1','release_state':phase['release_state'],'explicit_sources':phase['sources'],'phase_path':str(phase_path) if phase_path else None,'outputs':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size} for p in outputs],'private_images_exported':False,'scientific_engine_run':False,'table_encoding':'Exact decompressed source JSON,96lazy chunks; no browser gzip capability required.','self_and_receipt_excluded':True,'implementation':[{'path':str(p),'sha256':sha((ROOT/p).read_bytes())} for p in [Path('scripts/build_evidence_budget_page.py'),Path('scripts/test_evidence_budget_real_viewer.cjs'),Path('scripts/test_evidence_budget_page_dom.cjs')]]}
 write(downloads/'publication-manifest.json',(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode())
 receipt={'schema':'evidence_budget_page_build_receipt_v1','release_state':phase['release_state'],'phase_path':str(phase_path) if phase_path else None,'source_count':len(phase['sources']),'tables':96,'rows':total,'data_sha256':sha(b),'private_images_exported':False,'new_scores_computed':False,'all96_table_gzip_and_plaintext_hashes_verified':True,'outputs':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size} for p in outputs]}
 out=ROOT/P/('build_reviewed_draft_receipt.json' if args.reviewed_draft else args.receipt_name);out.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:receipt[k] for k in ['source_count','tables','rows','data_sha256','release_state']}))
if __name__=='__main__':main()
