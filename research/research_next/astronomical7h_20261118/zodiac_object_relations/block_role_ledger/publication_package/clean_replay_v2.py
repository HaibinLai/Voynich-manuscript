#!/usr/bin/env python3
"""Copy an explicit allowlist into a temporary checkout and replay read-only audits."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,tempfile
D=Path(__file__).resolve().parent; R=D.parents[5]; L=D.parent; A=L/'structural_audit'
def sha(b):return hashlib.sha256(b).hexdigest()
manifest=json.loads((D/'allowlist_v2.json').read_text())
controls=['protocol_v2.txt','input_freeze_v2.json','allowlist_v2.json','verify_adjudication_sources_v2.py','adjudication_source_result_v2.json','clean_replay_v2.py','README_v2.txt']
files={x['path']:x['sha256'] for x in manifest['files']}
for n in controls:
 p=D/n;files[str(p.relative_to(R))]=sha(p.read_bytes())
issues=[]
private_markers=['/'+x+'/' for x in ['Users','home']]+['C:'+chr(92)+'Users'+chr(92)]
for rel,h in files.items():
 b=(R/rel).read_bytes()
 if sha(b)!=h:issues.append({'file':rel,'issue':'declared hash differs'})
 if any(x.encode() in b for x in private_markers):issues.append({'file':rel,'issue':'private absolute path marker; projection required; original unchanged'})
if issues:
 print(json.dumps({'schema':'block_role_clean_replay_v2','all_pass':False,'issues':issues},indent=2));sys.exit(1)
jobs=[(D/'clean_replay_v1.py',0,D/'clean_replay_receipt_v1.json'),(L/'root_adjudication/build_v1.py',0,L/'root_adjudication/report_v1.json'),(D/'verify_adjudication_sources_v2.py',0,D/'adjudication_source_result_v2.json')]
results=[]
with tempfile.TemporaryDirectory(prefix='block-role-public-') as temp:
 target=Path(temp)
 for rel in files:
  dst=target/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(R/rel,dst);dst.chmod(0o444)
 env=dict(os.environ);env['PYTHONDONTWRITEBYTECODE']='1'
 for script,expected_exit,frozen in jobs:
  rel=str(script.relative_to(R));p=subprocess.run([sys.executable,'-B',rel],cwd=target,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  expected=(R/frozen.relative_to(R)).read_bytes()
  results.append({'command':['python3','-B',rel],'expected_exit_code':expected_exit,'actual_exit_code':p.returncode,'matches_expected_exit':p.returncode==expected_exit,'stdout_byte_identical':p.stdout==expected,'stdout_sha256':sha(p.stdout),'frozen_stdout':str(frozen.relative_to(R)),'frozen_stdout_sha256':sha(expected),'stderr_bytes':len(p.stderr),'stderr_sha256':sha(p.stderr),'pass':p.returncode==expected_exit and p.stdout==expected and not p.stderr})
 mutations=[rel for rel,h in files.items() if not (target/rel).is_file() or sha((target/rel).read_bytes())!=h]
 source_mutations=[rel for rel,h in files.items() if sha((R/rel).read_bytes())!=h]
result={'schema':'block_role_clean_replay_v2','source_allowlist_count':len(manifest['files']),'package_control_files':controls,'total_copied_files':len(files),'explicit_allowlist_only':True,'private_absolute_path_scan_clear':True,'projection_needed':[],'read_only_source_checks':True,'copied_input_mutations':mutations,'original_input_mutations':source_mutations,'jobs':results,'all_pass':all(x['pass'] for x in results) and not mutations and not source_mutations,'scope_limit':'Replays prior v1 clean package plus frozen root stdout builder and source checks only. No image reacquisition, image examination, scientific adjudication, or final merged judgment is reproduced. Original v1 exit 1 is the preserved finding, not a package failure.'}
print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(0 if result['all_pass'] else 1)
