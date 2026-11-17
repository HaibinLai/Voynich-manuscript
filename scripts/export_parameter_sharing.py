"""Export the new research package and disclose path-only audit redactions."""
import argparse,pathlib,shutil,hashlib,json,datetime,re
REPO=pathlib.Path(__file__).resolve().parent.parent
ap=argparse.ArgumentParser();ap.add_argument('--source',required=True,type=pathlib.Path);args=ap.parse_args()
src=args.source.resolve();dst=REPO/'research/research_next/parameter_sharing';dst.mkdir(parents=True,exist_ok=True)
def sha(b):return hashlib.sha256(b).hexdigest()
ALLOWED_TOP_LEVEL=set(['REPRODUCE.txt', 'audit_interpretation.txt', 'audit_synthetic_saved.py', 'benchmark.py', 'check_aggregation.py', 'check_aggregation_v2.py', 'controls.py', 'design_review.txt', 'freeze.json', 'freeze.py', 'independent_gpu_v1', 'independent_manuscript_replay', 'independent_model_check.py', 'independent_scalar_v1', 'independent_score_replay.py', 'independent_synthetic_replay', 'input_provenance.json', 'inputs', 'jobs.json', 'literature_review.json', 'literature_review.txt', 'manuscript_execution.json', 'model.py', 'prepare.py', 'protocol.txt', 'report_claim_review.json', 'report_claim_review.txt', 'results', 'run_job.py', 'run_jobs.py', 'runtime_amendment.txt', 'runtime_attempt1', 'runtime_recovery.py', 'score_replay_delivery_manifest.json', 'score_replay_interpretation.json', 'score_replay_interpretation.txt', 'smoke_v1', 'smoke_v2', 'summarize.py', 'summary_v1', 'summary_v2', 'synthetic.py', 'synthetic_data', 'synthetic_data_audit', 'synthetic_design.txt', 'synthetic_execution.json', 'synthetic_revision_notes.json', 'synthetic_revision_notes.txt', 'validation_v1', 'validation_v2', 'verify.py', '生成器结果解释模板.txt', '研究报告.txt'])
original={};changed={}
for path in sorted(src.rglob('*')):
 if path.relative_to(src).parts[0] not in ALLOWED_TOP_LEVEL:continue
 if not path.is_file() or '__pycache__' in path.parts or path.name in ['manifest.json','publication_transformations.json']:continue
 rel=path.relative_to(src);data=path.read_bytes();original[str(rel)]=sha(data)
 if path.suffix in ['.txt','.json','.log','.py']:
  s=data.decode('utf-8');s=s.replace(str(src)+'/', '').replace(str(src),'.')
  s=re.sub(r'/home/[^/]+/voynich_compute/parameter_sharing_v1/', '<project>/',s)
  s=re.sub(r'/home/[^/]+/formal-precision-crossstack/\.venv-cuda/', '<environment>/',s)
  if str(rel)=='design_review.txt':s=s.replace('s82','计算节点')
  data=s.encode('utf-8')
 target=dst/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
 if sha(data)!=original[str(rel)]:changed[str(rel)]={'source_sha256':original[str(rel)],'public_sha256':sha(data),'transformation':'Remove local/remote account path prefixes only; scientific numeric contents unchanged.'}
# Audit manifests hash their reports. Update those references after path-only
# normalization and record every derived receipt change, never the frozen inputs.
for _ in range(8):
 substitutions={v['source_sha256']:v['public_sha256'] for v in changed.values()}
 any_change=False
 for path in sorted(dst.rglob('*.json')):
  if path.name in ['freeze.json','manifest.json','publication_transformations.json']:continue
  rel=str(path.relative_to(dst));text=path.read_text();new=text
  for a,b in substitutions.items():new=new.replace(a,b)
  if new!=text:
   path.write_text(new);changed[rel]={'source_sha256':original[rel],'public_sha256':sha(path.read_bytes()),'transformation':'Update hash references to disclosed path-normalized public audit files.'};any_change=True
 if not any_change:break
else:raise RuntimeError('Audit hash dependencies did not settle')
freeze=json.loads((dst/'freeze.json').read_text())
for item in freeze['files']:assert sha((dst/item['path']).read_bytes())==item['sha256'],item['path']
receipt={'scope':'Public path normalization only. All freeze.json entries retain their original bytes and hashes. Original local receipts are retained by the operator.',
 'files':[dict(path=k,**v) for k,v in sorted(changed.items())]}
(dst/'publication_transformations.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
files=[]
for p in sorted(dst.rglob('*')):
 if p.is_file() and p.name!='manifest.json' and '__pycache__' not in p.parts:files.append({'path':str(p.relative_to(dst)),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())})
(dst/'manifest.json').write_text(json.dumps({'schema_version':1,'files':files,'frozen_files':len(freeze['files']),'scope':'New parameter-sharing research only; old seven-hour records untouched.'},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'files':len(files),'bytes':sum(x['bytes'] for x in files),'path_normalized_files':len(changed),'frozen_files_unchanged':len(freeze['files'])}))
