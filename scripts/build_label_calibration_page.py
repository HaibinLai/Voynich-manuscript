#!/usr/bin/env python3
"""Project frozen W8 summaries into lazy display chunks. No scientific scoring or simulations."""
import argparse,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;W=Path('research/research_next/label_exchange7h_20261119');P=W/'publication'
PHASE_SHA256='a3475f27c34a1a31532dbbe4b08977012f4cbacb1cb2e43c6fb520257e734c3c'
SUMMARY_SHA='19333b55e765f6f0adb8a47b71974c7576e5ebc29af31eb6a7f72046f651c8d5'
VERSIONS=['ZL','IT'];MODES=['main_HI','strict_HIQ5','cross_version_lengths'];MODELS=['exact','fk','fp','ft','kp','kt','pt'];PAIRS=MODELS[1:];DOSES=['0','1','2','4','8','16','32','64']
NAMES=[('session','session_v1.json'),('plan','plan_v1.txt'),('protocol','protocol_v1.txt'),('protocol_approval','protocol_approval_v1.json'),('protocol_review','protocol_review_v2.json'),('protocol_review_text','protocol_review_v2.txt'),('input_freeze','input_freeze_v1.json'),('prior_inventory','prior_work_inventory_v1.json'),('prior_inventory_text','prior_work_inventory_v1.txt'),('summary','summary_v1/summary.json'),('summary_text','summary_v1/summary.txt'),('summary_manifest','summary_v1/source_manifest.json'),('summary_complete','summary_v1/complete.json'),('per_seed_metrics','summary_v1/per_seed_metrics.jsonl.gz'),('audit_A','audit_A_v1.json'),('audit_A_text','audit_A_v1.txt'),('audit_B','audit_B_v1.json'),('audit_B_text','audit_B_v1.txt'),('audit_D','audit_D_v1.json'),('audit_D_text','audit_D_v1.txt'),('equivalence','runs/observational_equivalence_copy_v1.json'),('toy_equivalence','runs/observational_equivalence_toy_v1.json'),('toy','runs/toy.json'),('figure_values','figures_v2/values.json'),('figure_review','figures_v2/visual_review_v1.json')]+[(f'{name}_{ext}',f'figures_v2/{name}.{ext}') for name in ['exact_detection','six_pair_increments','achieved_effect'] for ext in ['png','svg']]+[(f'candidates_{v}',f'runs/copy/{v}/candidate_registry.json.gz') for v in VERSIONS]
FINAL=[('reproduce','REPRODUCE_v1.txt'),('audit_summary','audit_summary_v1.json'),('audit_summary_text','audit_summary_v1.txt'),('research_report','research_report_v2.json'),('research_report_text','research_report_v2.txt')]+[(n,n+'.json') for n in ['copy_code_freeze_v1','reference_code_freeze_v1','summary_code_freeze_v1']]+[('code_'+n,'code/'+n+'.py') for n in ['exact_reference','matrix_support','run_reference_checks','copy_generator','run_copy_calibration','summarize_calibration','independent_audit','independent_audit_B','independent_summary_audit','write_research_report','plot_calibration']]
REPOSITORY_ONLY={'summary','per_seed_metrics'}
def sha(b):return hashlib.sha256(b).hexdigest()
def dump(d):return (json.dumps(d,ensure_ascii=False,separators=(',',':'))+'\n').encode()
def explicit_inputs():
 return [{'key':k,'path':str(W/n),'sha256':sha((ROOT/W/n).read_bytes()),'bytes':(ROOT/W/n).stat().st_size,'distribution':'repository_only' if k in REPOSITORY_ONLY else 'site_download','download_name':k.replace('_','-')+''.join(Path(n).suffixes)} for k,n in NAMES+FINAL]
def project_series(x):
 return {**{k:v for k,v in x.items() if k!='statistics'},'statistics':{k:x['statistics'][k] for k in ['delta_pp','effect_relative_to_K0_pp','p_upper']},'projection_note':'Other precise statistics remain in the original summary at the supplied pointer.'}
def project_dose(d):
 x={k:v for k,v in d.items() if k not in ['joint','groups','local_repetition']};x['joint']={f:{m:project_series(v) for m,v in d['joint'][f].items()} for f in ['models','increments']};x['groups']=[{**{k:v for k,v in g.items() if k not in ['models','increments']},**{f:{m:project_series(v) for m,v in g[f].items()} for f in ['models','increments']}} for g in d['groups']];x['local_repetition']={'definition':d['local_repetition']['definition'],'note':'Full per-page repetition diagnostics retained in source summary and complete per-seed source files.'};return x
def main():
 ap=argparse.ArgumentParser(description=__doc__);g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--reviewed-draft',action='store_true');g.add_argument('--phase-input');ap.add_argument('--receipt-name',default='draft_build_v1.json');a=ap.parse_args();phase_path=None
 if a.reviewed_draft:phase={'schema':'label_calibration_page_draft_v1','state':'LOCAL_RESULTS_DRAFT_SUMMARY_AUDIT_REPORT_PENDING','sources':explicit_inputs()}
 else:
  phase_path=Path(a.phase_input);assert phase_path.parent==P;assert sha((ROOT/phase_path).read_bytes())==PHASE_SHA256;phase=json.loads((ROOT/phase_path).read_text());assert phase['schema']=='label_calibration_publication_phase_v1' and phase['final_report_and_summary_audit_connected'] is True
 assert Path(a.receipt_name).name==a.receipt_name
 raw={};docs={};refs={};outputs=[];inputs={}
 def write(path,b):
  p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);outputs.append({'path':str(path),'sha256':sha(b),'bytes':len(b)})
 for r in phase['sources']:
  p=Path(r['path']);assert not p.is_absolute() and '..' not in p.parts and p.is_relative_to(Path('research/research_next'));b=(ROOT/p).read_bytes();assert sha(b)==r['sha256'] and len(b)==r['bytes'];assert r['key'] not in raw;raw[r['key']]=b;inputs[str(p)]=r['sha256']
  if p.suffix in ['.json','.txt','.svg','.py']:assert not any(x in b for x in [b'/Users/',b'/home/',b'/var/folders/',b'/private/var/',b'/opt/miniconda',b'ghp_',b'github_pat_']),str(p)
  if p.suffix=='.json':docs[r['key']]=json.loads(b)
  url='https://github.com/HaibinLai/Voynich-manuscript/blob/main/'+str(p)
  ref={'path':str(p),'sha256':r['sha256'],'bytes':len(b),'repository_url':url,'url':('https://raw.githubusercontent.com/HaibinLai/Voynich-manuscript/main/'+str(p) if r['distribution']=='repository_only' else url),'distribution':r['distribution']}
  if r['distribution']=='site_download':assert Path(r['download_name']).name==r['download_name'];ref['url']='downloads/label-calibration7h/'+r['download_name'];write(Path('site')/ref['url'],b)
  refs[r['key']]=ref
 s=docs['summary'];assert refs['summary']['sha256']==SUMMARY_SHA and s['schema_version']=='eighth_saved_calibration_summary_v1' and s['status']=='COMPLETE';assert len(s['A']['rows'])==len(s['old_references'])==6 and len(s['D']['rows'])==78
 assert s['protocol']['sha256']==refs['protocol']['sha256'];assert docs['protocol_approval']['protocol']['sha256']==refs['protocol']['sha256']
 for r in docs['summary_complete']['files']:
  path=str(W/'summary_v1'/r['path']);assert path in inputs and inputs[path]==r['sha256']
 for key in ['audit_A','audit_B','audit_D']:assert docs[key]['status']=='PASS' and docs[key]['failures']==[] and docs[key]['primary_functions_imported'] is False
 assert docs['audit_B']['complete_256_seed_audit'] is True and docs['audit_B']['checks']['B_sample_N13']==54
 assert docs['audit_A']['checks']['A_all_114_thresholds']==1 and docs['audit_D']['checks']['D_all78']==1
 eq=docs['equivalence'];assert eq['seed_count']==256 and eq['prefix_bindings']==2048 and all(r['semantic_world_observation_binding_sha256']==r['mechanical_copy_world_observation_binding_sha256'] for r in eq['rows'])
 def chunk(name,value,pointer):
  b=dump(value);path=Path('site/data/label-calibration7h')/(name+'.json');write(path,b);return {'url':str(path.relative_to('site')),'sha256':sha(b),'bytes':len(b),'summary_pointer':pointer,'source_summary_sha256':SUMMARY_SHA}
 payload={'schema':'label_calibration_page_v1','state':phase['state'],'versions':VERSIONS,'conditions':MODES,'models':MODELS,'pairs':PAIRS,'doses':DOSES,'sources':refs,'summary_original':refs['summary'],'B':{},'A':{},'D':{},'old':{},'private_images_exported':False,'scientific_figures_exported':True,'new_statistical_calculation':False,'goal_complete_claimed':False,'summary_audit_connected':'audit_summary' in docs,'research_report_connected':'research_report' in docs,'source_manifest':refs['summary_manifest'],'CP_scope':s['CP_scope'],'session_times':{k:docs['session'][k] for k in ['planned_start_utc','deadline_utc','actual_goal_creation_utc']},'audits':{k:{x:docs[k][x] for x in ['schema','status','scope','limits']} for k in ['audit_A','audit_B','audit_D']},'equivalence':{k:eq[k] for k in ['seed_count','prefix_bindings','construction','proof','limitations']},'equivalence_examples':[next(r for r in eq['rows'] if r['version']==v and r['K']==64) for v in VERSIONS]}
 for v in VERSIONS:
  version=s['B']['versions'][v];assert version['status']=='COMPLETE' and version['completed_seed_tasks']==version['expected_seed_tasks']==128
  payload['B'][v]={'status':version['status'],'expected_seed_tasks':128,'completed_seed_tasks':128,'candidate_metadata':version['candidate_metadata'],'candidate_registry':version['candidate_registry'],'seed_sources':version['seed_sources'],'conditions':{}}
  for mode in MODES:
   payload['B'][v]['conditions'][mode]={}
   for k in DOSES:
    d=version['conditions'][mode]['doses'][k];assert set(d['joint']['models'])==set(MODELS) and set(d['joint']['increments'])==set(PAIRS)
    for g in d['groups']:assert set(g['models'])==set(MODELS) and set(g['increments'])==set(PAIRS)
    assert d['observed_seed_count']==128 and len(d['exact_realized_effect_bins'])==6 and sum(b['count'] for b in d['exact_realized_effect_bins'])==128
    if k=='0':assert d['fixed_background'] is True and all(x['CP95'] is None for z in [d['joint'],*d['groups']] for f in ['models','increments'] for ser in z[f].values() for x in ser['rejection'].values())
    pointer=f'/B/versions/{v}/conditions/{mode}/doses/{k}';payload['B'][v]['conditions'][mode][k]=chunk(f'B-{v}-{mode}-{k}',project_dose(d),pointer)
   A=next(x for x in s['A']['rows'] if x['version']==v and x['mode']==mode);payload['A'][v+'/'+mode]=chunk('A-'+v+'-'+mode,A,f'/A/rows/{s["A"]["rows"].index(A)}')
   rows=[x for x in s['D']['rows'] if x['version']==v and x['mode']==mode];assert len(rows)==13
   ranges=next(x for x in s['D']['ranges'] if x['version']==v and x['mode']==mode);payload['D'][v+'/'+mode]=chunk('D-'+v+'-'+mode,{'rows':rows,'ranges':ranges},'/D')
   old=next(x for x in s['old_references'] if x['version']==v and x['mode']==mode);payload['old'][v+'/'+mode]=chunk('old-'+v+'-'+mode,old,'/old_references/'+str(s['old_references'].index(old)))
 if 'research_report' in docs:
  report=docs['research_report'];assert report['schema']=='eighth_research_report_v2' and report['goal_complete_claimed'] is False and report['semantic_decipherment'] is False and report['report_txt_sha256']==refs['research_report_text']['sha256']
  for r in report['selected_main_condition_rows']:
   for v in VERSIONS:
    ser=s['B']['versions'][v]['conditions']['main_HI']['doses'][str(r['K_attempts'])]['joint']['models']['exact'];assert r[v]['mean_increase_pp']==ser['statistics']['effect_relative_to_K0_pp']['mean'];assert r[v]['rejections']==ser['rejection']['alpha_1_20']['rejections'] and r[v]['CP95']==ser['rejection']['alpha_1_20']['CP95']
  payload['research_report']=report
 
 if 'audit_summary' in docs:
  audit=docs['audit_summary'];assert audit['schema']=='eighth_independent_summary_audit_v1' and audit['status']=='PASS' and audit['failures']==[];assert audit['scope']['metric_rows_full_source_and_pointer_checked']==266240 and audit['scope']['joint_and_group_series']==2080 and audit['scope']['figure_cells']==42
  for path,expected in audit['inputs'].items():assert inputs[path]==expected,path
  for field in ['implementation','independent_decimal_helper']:assert inputs[audit[field]['path']]==audit[field]['sha256']
  payload['audit_summary']=audit
 
 b=dump(payload);write(Path('site/data/label-calibration7h.json'),b)
 initial=len(b)+sum(payload['B'][v]['conditions']['main_HI']['1']['bytes'] for v in VERSIONS);assert initial<1000000,initial
 if phase_path:write(Path('site/downloads/label-calibration7h')/phase_path.name,(ROOT/phase_path).read_bytes())
 html=ROOT/'site/label-calibration7h.html';text=html.read_text();text=re.sub(r'(<meta name="label-calibration-snapshot" content=")[^"]*',lambda m:m[1]+sha(b)[:16],text)
 for n in ['label-calibration7h.js','label-calibration7h.css']:text=re.sub(re.escape(n)+r'\?v=[A-Za-z0-9_-]+',n+'?v='+sha((ROOT/'site'/n).read_bytes())[:16],text)
 write(Path('site/label-calibration7h.html'),text.encode())
 for n in ['label-calibration7h.js','label-calibration7h.css','style.css','favicon.svg']:
  p=Path('site')/n;outputs.append({'path':str(p),'sha256':sha((ROOT/p).read_bytes()),'bytes':(ROOT/p).stat().st_size})
 manifest={'schema':'label_calibration_site_manifest_v1','phase_path':str(phase_path) if phase_path else None,'sources':phase['sources'],'outputs':outputs.copy(),'builder_sha256':sha(Path(__file__).read_bytes()),'viewer_test':{'path':'scripts/test_label_calibration_viewer.cjs','sha256':sha((ROOT/'scripts/test_label_calibration_viewer.cjs').read_bytes())},'default_initial_JSON_bytes':initial,'private_images_exported':False,'scientific_figures_exported':True,'no_scoring':True,'projection_rule':'All48 B dose chunks retain complete joint/group13 series with upstream delta/effect/p statistics, rejection fractions/CP and6 bins. Full source summary remains exact and unchanged. A, all78D and historical6packages lazy.','referenced_raw_sources':docs['summary_manifest']['files'],'self_excluded':True};write(Path('site/downloads/label-calibration7h/publication-manifest.json'),(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode())
 receipt={**manifest,'outputs':outputs,'data_sha256':sha(b)};(ROOT/P/a.receipt_name).write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'sources':len(raw),'outputs':len(outputs),'initial_JSON_bytes':initial,'data_sha256':sha(b)}))
if __name__=='__main__':main()
