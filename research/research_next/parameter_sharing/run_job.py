import os,json,gzip,argparse,time,traceback,pathlib,hashlib,sys
import numpy as np,torch
from model import Corpus,common_units,match_df
ROOT=pathlib.Path(__file__).resolve().parent

def read(path):
 with gzip.open(path,'rt') as f:
  if str(path).endswith('.jsonl.gz'):return [json.loads(l) for l in f]
  return json.load(f)

def load(job):
 if job['kind']=='synthetic':
  folder=ROOT/'synthetic_data'/f"seed{job['seed']}"/job['case']
  data={s:read(folder/(s+'.jsonl.gz')) for s in ['train','dev','test']};universe=list('abcdefgh')
 else:
  v=job['version'];src=read(ROOT/'inputs'/(v+'_train_dev.json.gz'))
  data={'train':src['train'],'dev':src['dev'],'confirm':read(ROOT/'inputs'/(v+'_confirm.json.gz')),
   'reserve':read(ROOT/'inputs'/(v+'_reserve.json.gz'))}
  universe=list('abcdefghijklmnopqrstuvwxyz')+["'"]+[f'@{i:03d};' for i in range(1000)]
 for rows in data.values():
  for x in rows:x['word']=list(x['word'])
 return data,universe

def run(job):
 out=ROOT/'results'/job['id'];out.mkdir(parents=True,exist_ok=False)
 (out/'job.json').write_text(json.dumps(job,indent=2)+'\n')
 torch.set_num_threads(2);torch.backends.cuda.matmul.allow_tf32=False
 data,universe=load(job);common=common_units(data['train']);train=Corpus(data['train'],common,universe,'cuda:0')
 started=time.time();solutions,audit=match_df(train,job['pairs'])
 audit.update({'job':job,'common':common,'universe_size':len(universe),'dimension':train.F*train.K,
 'feature_count':train.F,'nonreference_outputs':train.K,'train_contexts':len(train.keys),
 'torch':torch.__version__,'numpy':np.__version__,'python':sys.version.split()[0],
 'gpu':torch.cuda.get_device_name(),'seconds_fit':time.time()-started})
 # Evaluations are diagnostic only and are not consulted by matching or fitting.
 arrays={};weights={};summary={}
 for target,(b,info) in solutions.items():
  weights['df'+str(int(target))]=b.detach().cpu().numpy()
  summary[str(int(target))]={}
  for split,rows in data.items():
   c=train if split=='train' else Corpus(rows,common,universe,'cuda:0')
   costs=c.costs(b);assert np.isfinite(costs).all()
   arrays[f'df{int(target)}_{split}']=costs
   summary[str(int(target))][split]={'words':len(rows),'mean_bits_per_word':float(costs.mean()),'sum_bits':float(costs.sum())}
 np.savez_compressed(out/'weights.npz',**weights);np.savez_compressed(out/'scores.npz',**arrays)
 audit['seconds_total']=time.time()-started;audit['summary']=summary
 (out/'audit.json').write_text(json.dumps(audit,indent=2)+'\n')
 (out/'DONE').write_text('completed\n')
 return len(solutions)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('index',type=int);ap.add_argument('--jobs',default='jobs.json');args=ap.parse_args()
 job=json.loads((ROOT/args.jobs).read_text())[args.index]
 try: print(json.dumps({'id':job['id'],'matched':run(job)}),flush=True)
 except Exception:
  p=ROOT/'results'/job['id'];p.mkdir(parents=True,exist_ok=True);(p/'ERROR.txt').write_text(traceback.format_exc());raise
