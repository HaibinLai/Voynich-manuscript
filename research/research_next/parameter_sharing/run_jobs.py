"""Bounded queue: one independent job per GPU, two CPU threads each."""
import concurrent.futures,subprocess,pathlib,json,os,sys,time,hashlib
ROOT=pathlib.Path(__file__).resolve().parent
freeze=json.loads((ROOT/'freeze.json').read_text())
for item in freeze['files']:
 assert hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()==item['sha256'],item['path']
kind=sys.argv[1];jobs=json.loads((ROOT/'jobs.json').read_text())
indices=[i for i,x in enumerate(jobs) if x['kind']==kind]
# Deterministic assignment; no selection based on an observed score.
def worker(gpu):
 for index in indices[gpu::8]:
  job=jobs[index];log=ROOT/'logs'/(job['id']+'.log');log.parent.mkdir(exist_ok=True)
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(gpu),OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
  with log.open('w') as f:r=subprocess.run([sys.executable,str(ROOT/'run_job.py'),str(index)],env=env,stdout=f,stderr=subprocess.STDOUT)
  print(json.dumps({'id':job['id'],'exit':r.returncode,'time':time.time()}),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(worker,range(8)))
