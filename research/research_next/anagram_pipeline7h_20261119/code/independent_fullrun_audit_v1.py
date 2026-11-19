"""Read-only completed-run completeness audit. Never executes author solvers."""
from pathlib import Path
from collections import Counter
import argparse,datetime,hashlib,json,subprocess
W=Path(__file__).resolve().parents[1];REPO=W.parents[2]
checks=Counter()
def ck(v,k):
 checks[k]+=1
 if not v:raise AssertionError(k)
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def utc(s):return datetime.datetime.fromisoformat(s.replace('Z','+00:00'))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=W/'calibration/fullrun_independent_audit_v1.json');args=ap.parse_args();ck(not args.output.exists(),'new_output')
 freeze=read(W/'calibration/formal_freeze_v1.json');frozen={x['path']:x['sha256'] for x in freeze['files']}
 for x in freeze['files']:ck(sha(REPO/x['path'])==x['sha256'],'formal_frozen_file')
 acq=read(W/'upstream/acquisition_v1.json')
 for x in acq['files']:
  ck(sha(REPO/x['path'])==x['sha256'],'vendored_core_hash')
  raw=subprocess.check_output(['git','-C','/tmp/voynich-w10-upstream/hk-langid','show',acq['commit']+':'+x['upstream_path']])
  ck(hashlib.sha256(raw).hexdigest()==x['sha256'],'author_git_blob_identical')
 data=W/'calibration/data_v1';datahash=sha(data/'file_hashes.json');inputs=read(data/'execution_inputs.json');ids=['P01','P02','P03','P04','C01'];variants=['readme_lex','code_countfirst']
 ck([x['id'] for x in inputs['cases']]==freeze['cases']==ids and inputs['variants']==freeze['primary_variants']==variants,'frozen_cases_and_variants')
 for x in read(data/'file_hashes.json'):ck(sha(data/x['path'])==x['sha256'],'prepared_file_unchanged')
 results={};manifests={};actual_logs={};run_rows=[];expected={}
 for phase in ['primary','oracle']:
  folder=W/f'calibration/{phase}_v1';m=read(folder/'run_manifest.json');r=read(folder/'results.json');results[phase]=r;manifests[phase]=m
  ck(m['phase']==r['phase']==phase,'phase');ck(m['runner_sha256']==sha(W/'code/run_author_pipeline.py'),'frozen_runner_used');ck(m['data_manifest_sha256']==datahash,'same_data_manifest');ck(m['results_sha256']==sha(folder/'results.json'),'results_manifest_binding');ck([x['id'] for x in r['rows']]==ids,'all_five_cases')
  for x in m['files']:ck(sha(folder/x['path'])==x['sha256'],'run_full_file_hash')
  actual_logs[phase]={x.name for x in (folder/'logs').iterdir() if x.is_dir()}
  for folderlog in sorted((folder/'logs').iterdir()):
   receipt=read(folderlog/'receipt.json');script=receipt['script'];cmd=receipt['command'];start=utc(receipt['start_utc'])
   ck(receipt['id']==folderlog.name,'log_id');ck(receipt['script_sha256']==sha(W/'upstream/hk-langid'/script),'executed_script_hash');ck(cmd[:4]==['perl','-I','../../upstream/hk-langid','../../upstream/hk-langid/'+script],'module_source_path')
   ck(receipt['environment']=={'PERL_HASH_SEED':'0','PERL_PERTURB_KEYS':'0'},'frozen_hash_environment')
   ck(receipt['status']=='COMPLETED' and receipt['exit_code']==0,'process_completed')
   ck(start>=utc(freeze['created_utc']) and start<=utc(m['completed_utc']),'freeze_before_run')
   if phase=='oracle':ck(start>=utc(manifests['primary']['completed_utc']),'all_primary_before_oracle')
   for name in ['stdin','stdout','stderr']:ck(sha(folderlog/(name+'.txt'))==receipt[name+'_sha256'],'stream_hash')
   ck((folderlog/'stderr.txt').read_text()=='','no_stderr')
   timeout=180 if script=='maspa_solver.pl' else 60;ck(receipt['timeout_seconds']==timeout,'fixed_timeout');ck(0<=receipt['elapsed_seconds']<timeout,'within_budget')
   run_rows.append({'phase':phase,'id':receipt['id'],'script':script,'command_arguments':cmd[4:],'timeout_seconds':timeout,'elapsed_seconds':receipt['elapsed_seconds'],'status':'COMPLETED_EXIT0','stderr_empty':True})
 def add(phase,rid,script,args,stdin):
  expected[phase,rid]=(script,args,stdin)
 def decoder(phase,entry,language):
  words=entry['input_words'];stdin=''.join(' '.join(words[i:i+20])+'\n' for i in range(0,len(words),20));add(phase,entry['run_id'],'alphagram_solver.pl',[f'models/shared/{language}/base'],stdin)
  ck(entry['status']=='PASS' and len(entry['output_words'])==len(words),'decoder_interface_only_pass')
  ck(entry['input_blocks']==(len(words)+19)//20,'decoder_fixed_blocks')
 def pipeline(phase,p,cipher):
  rid=p['maspa_run_id'];lang=p['language'];variant=p['variant'];add(phase,rid,'maspa_solver.pl',['-c',f'models/{variant}/{lang}/model.config','-m','10','-b','10','-p','20'],cipher+'\n')
  ck(p['mapping_status']=='PASS','mapping_interface_only_pass');decoder(phase,p['decoder'],lang)
  ck(p['decoder']['input_words']==p['author_solution_words'],'actual_maspa_decoder_handoff')
 for row in results['primary']['rows']:
  cid=row['id'];cipher=(data/f'cipher/{cid}.txt').read_text().strip();ck(len(cipher.split())==(7 if cid=='C01' else 80),'frozen_cipher_lengths')
  ck(set(row['routes'])=={'pattern','unigram'},'all_language_diagnostics')
  for method,route in row['routes'].items():
   ck(route['status']=='PASS' and set(route['scores'])=={'english','latin'},'language_interface_only_pass')
   add('primary',route['run_id'],'langid_probdist.pl',['-c',f'cipher/{cid}.txt','-p','train/*.tra','-d',method,'-v'],'')
  ck([p['variant'] for p in row['pipelines']]==variants,'primary_two_variants')
  for p in row['pipelines']:ck(p['language']==row['routes']['pattern']['language'],'actual_pattern_routing');pipeline('primary',p,cipher)
 ck(results['oracle']['primary_results_sha256']==sha(W/'calibration/primary_v1/results.json'),'oracle_primary_binding')
 reused=0
 for row in results['oracle']['rows']:
  cid=row['id'];cipher=(data/f'cipher/{cid}.txt').read_text().strip();prior=next(x for x in results['primary']['rows'] if x['id']==cid);truth=read(data/'truth'/f"{cid if cid!='C01' else 'C01A'}.json");lang=truth['language'];ck(row['oracle_language']==lang,'oracle_language_explicit');ck([x['variant'] for x in row['pipelines']]==variants,'oracle_two_variants')
  for p in row['pipelines']:
   old=next(x for x in prior['pipelines'] if x['variant']==p['variant'])
   if old['language']==lang:
    ck(p.get('reused_primary_result') is True,'required_reuse');reused+=1
    ck({k:v for k,v in p.items() if k not in ['reused_primary_result','original_primary_case','label']}=={k:v for k,v in old.items() if k!='label'},'reuse_exact_fields')
   else:ck(not p.get('reused_primary_result',False) and p['language']==lang,'oracle_rerun_only_wrong_route');pipeline('oracle',p,cipher)
  mapped=''.join(truth['decryption'].get(c,c) for c in cipher).split();ck(mapped==row['oracle_truekey_decoder']['input_words'],'truekey_condition_input');decoder('oracle',row['oracle_truekey_decoder'],lang)
 for phase in ['primary','oracle']:ck(actual_logs[phase]=={rid for ph,rid in expected if ph==phase},'exact_log_coverage_no_extra')
 for (phase,rid),(script,args0,stdin) in expected.items():
  folder=W/f'calibration/{phase}_v1/logs'/rid;receipt=read(folder/'receipt.json');ck(receipt['script']==script and receipt['command'][4:]==args0,'exact_stage_command');ck((folder/'stdin.txt').read_text()==stdin,'exact_stage_input')
 score=read(W/'calibration/scores_v1.json');ck(score['bindings']['data_sha256']==datahash and score['bindings']['primary_sha256']==manifests['primary']['results_sha256'] and score['bindings']['oracle_sha256']==manifests['oracle']['results_sha256'] and score['bindings']['scorer_sha256']==sha(W/'code/score_calibration.py'),'scoring_source_bindings')
 ck(len(score['rows'])==30 and len(score['language_rows'])==10 and len(score['groups'])==5,'saved_score_coverage')
 diagnostics=[]
 for g in score['groups']:diagnostics.append({'condition':g['condition'],'variant':g['variant'],'planned_cases':g['planned_cases'],'planned_words':g['planned_words'],'mapping_weighted_correct_total':[g['mapping_weighted']['correct'],g['mapping_weighted']['total']],'bag_correct_total':[g['word_bags']['correct'],g['word_bags']['total']],'exact_word_correct_total':[g['exact_words']['correct'],g['exact_words']['total']]})
 selected=[x for x in score['language_rows'] if x['positive'] and x['method']=='pattern'];ck(sum(x['correct'] for x in selected)==3 and len(selected)==4,'reported_route3of4')
 ck(reused==8 and len(run_rows)==39,'physical_runs_and_reuse')
 counts=Counter(x['script'] for x in run_rows)
 result={'schema':'tenth_independent_fullrun_integrity_audit_v1','status':'PASS_RUN_INTEGRITY','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'code_sha256':sha(Path(__file__)),'bindings':{str(p.relative_to(W)):sha(p) for p in [W/'calibration/formal_freeze_v1.json',W/'calibration/primary_v1/run_manifest.json',W/'calibration/oracle_v1/run_manifest.json',W/'calibration/scores_v1.json',W/'calibration/independent_score_audit_v1.json',W/'calibration/viterbi_finite_bound_v1.json']},'scope':{'actual_author_processes':len(run_rows),'processes_by_script':dict(counts),'oracle_reused_primary_pipeline_results':reused,'cases':ids,'variants':variants,'new_author_solver_runs_executed_by_audit':0,'independent_accuracy_recomputation':'Not repeated: separate literature-agent score audit handles30rows/10language diagnostics/5groups. Saved aggregates below are attributed to those bound scores.'},'checks':dict(checks),'actual_runs':run_rows,'bound_score_summary':diagnostics,'reported_primary_language_correct_total':[3,4],'report_interpretation':['All39 processes exited0 with empty stderr and expected frozen arguments; stagePASS means valid execution/interface, not correct language/key/words.','Main pattern+README result remains193/320 exact words60.3125%, with3/4 correct language routes. Do not select the unigram diagnostic or oracle path as replacement primary.','Providing correct language raises README to246/320; countfirst oracle recovers1477/1477 observed character positions and320/320 word bags but only249/320 original words. Correct-key decoder also249/320.','The latter equality is aggregate stage evidence; it does not prove every missing word is inherently unidentifiable or that another context model could not recover it. OOV, language-model preference and bag ambiguity must remain separate.','Countfirst is a preregistered code-aligned diagnostic under new training construction, not an established recovery of the authors2016 training method.','Four80word snippets from two already exposed books, held out only from this8000word training; not independent blind, cross-author, all-language, manuscript or original-paper result replication.','C01 has one ciphertext and two generation histories; count its two7word truths separately and outside320 main words.','Oracle true-key mapping accuracy is not applicable; its100% bag preservation is supplied information, not recovered-key success.','Truth isolation is supported by frozen code/control flow and recorded invocation inputs, not a new operating-system file-access trace.'], 'failures':[]}
 args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');args.output.with_suffix('.txt').write_text('正式完整运行只读审计PASS。39次原作者进程（语言识别10、MASPA12、Viterbi17）全部exit0/stderr空，8个oracle管线复用保持逐字段一致；五输入/两表示/固定参数/每次stdin与冻结代码及数据hash全部匹配。全部primary完成后才有oracle运行，未发现缺漏或额外择优重跑。\n主pattern3/4与README整词193/320=60.3125%保持主结论；真语言README246/320，countfirst真语言1477/1477字母位置与320/320袋仍只249/320词，真key同为249/320。阶段PASS不等于内容正确，oracle和诊断不可替主成绩。\n四段来自两本已曝光原文、仅对本次8000训练留出；不推手稿、语种总体或原论文成绩。C01双真值在320之外。249词相同不证明全部错误都是理论不可辨识，更不能给其他模型上限。计分由另独立审计负责，本次不重复求解或准确率重算。真值隔离是代码/接口证据，不是OS访问轨迹证明。\n');print(json.dumps({'status':result['status'],'runs':len(run_rows),'by_script':dict(counts),'checks':dict(checks),'receipt_sha256':sha(args.output)}))
if __name__=='__main__':main()
