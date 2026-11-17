"""One deterministic resource retry only; scientific code/configuration unchanged."""
import concurrent.futures,subprocess,pathlib,json,os,sys,time,hashlib,shutil,datetime
ROOT=pathlib.Path(__file__).resolve().parent
freeze=json.loads((ROOT/'freeze.json').read_text())
for item in freeze['files']:assert hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest()==item['sha256'],item['path']
kind=sys.argv[1];jobs=json.loads((ROOT/'jobs.json').read_text());indices=[i for i,x in enumerate(jobs) if x['kind']==kind]
if kind=='synthetic':
 indices=indices[1::8] # Every original device-1 assignment, independently of its outcomes.
 for i in indices:
  name=jobs[i]['id'];archive=ROOT/'runtime_attempt1'/name;archive.mkdir(parents=True,exist_ok=False)
  if (ROOT/'results'/name).exists():
   shutil.move(str(ROOT/'results'/name),str(archive/'result'))
   if not (archive/'result'/'DONE').exists() and not (archive/'result'/'ERROR.txt').exists():(archive/'ABORTED_RUNTIME.txt').write_text('Stopped stalled device-1 job after all seven other queues finished.\n')
  else:(archive/'NOT_STARTED.txt').write_text('Original queue stopped before this device-1 assignment.\n')
  if (ROOT/'logs'/(name+'.log')).exists():shutil.move(str(ROOT/'logs'/(name+'.log')),str(archive/'job.log'))
healthy=[0,2,3,4,5,6,7]
receipt={'kind':kind,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'assignments':[],
 'reason':'All original device-1 assignments rerun once after repeated CUDA illegal instruction/address failures; no outcome-based selection or model changes.' if kind=='synthetic' else 'First manuscript run uses seven devices; repeated runtime-error device excluded before any manuscript fit.',
 'frozen_sha256':hashlib.sha256((ROOT/'freeze.json').read_bytes()).hexdigest()}
for n,i in enumerate(indices):receipt['assignments'].append({'index':i,'id':jobs[i]['id'],'device':healthy[n%7]})
path=ROOT/(kind+'_execution.json');assert not path.exists();path.write_text(json.dumps(receipt,indent=2)+'\n')
def worker(slot):
 for task in receipt['assignments'][slot::7]:
  env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(task['device']),OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
  with (ROOT/'logs'/(task['id']+'.log')).open('w') as f:
   r=subprocess.run([sys.executable,str(ROOT/'run_job.py'),str(task['index'])],env=env,stdout=f,stderr=subprocess.STDOUT)
  task['exit']=r.returncode;task['ended_epoch']=time.time();print(json.dumps(task),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=7) as pool:list(pool.map(worker,range(7)))
receipt['completed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();path.write_text(json.dumps(receipt,indent=2)+'\n')
