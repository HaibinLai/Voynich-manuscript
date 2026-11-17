"""Additional archived-confirm probability and row-field equality checks."""
from pathlib import Path
import datetime,gzip,hashlib,json
import numpy as np
P=Path(__file__).resolve().parent;R=P/'preflight_v1';ROOT=P.parent

def read(p):
 if p.exists():b=p.read_bytes();b=gzip.decompress(b) if p.suffix=='.gz' else b
 else:b=gzip.decompress(Path(str(p)+'.gz').read_bytes())
 return json.loads(b)
def coord(r):return r['folio'],r['line'],r['slot']
checks=[]
for name in ['ZL_EVA','ZL_merged','IT_EVA']:
 new=read(R/('allograph_'+name+'_rows.json.gz'));old=read(ROOT/'allograph_factor/targets'/(name+'.json'));assert [coord(r) for r in new]==[coord(r) for r in old]
 for x,y in zip(new,old):
  for k in ['word','leaf','hand','position']:assert x[k]==y[k]
 actual=np.load(R/('allograph_'+name+'.npz'))
 for merge in ['FP','KT','both']:
  expected=np.load(ROOT/'allograph_factor/scores'/(name+'_'+merge+'.npz'));errors={}
  for k in ['base','base_escape','quotient','restoration','restoration_global','complete','complete_global','quotient_escape']:
   key=k if k in ('base','base_escape') else merge+'_'+k;errors[k]=float(np.max(np.abs(actual[key]-expected[k])));assert errors[k]<1e-11
  checks.append(dict(name=name,family='allograph',merge=merge,max_probability_cost_difference=max(errors.values()),all_shared_metadata_equal=True))
 new=read(R/('paragraph_'+name+'_rows.json.gz'));path=ROOT/'paragraph_factor'/name/'confirm_word_scores.jsonl.gz';old=[json.loads(s) for s in gzip.decompress(path.read_bytes()).splitlines()];old=[r for r in old if r['position']=='paragraph_first'];assert [coord(r) for r in new]==[coord(r) for r in old]
 for x,y in zip(new,old):
  for k in ['word','leaf','hand','position']:assert x[k]==y[k]
 actual=np.load(R/('paragraph_'+name+'.npz'));errors={}
 for k in actual.files:errors[k]=float(np.max(np.abs(actual[k]-np.asarray([r['bits'][k] for r in old]))));assert errors[k]<1e-11
 checks.append(dict(name=name,family='paragraph',max_probability_cost_difference=max(errors.values()),all_shared_metadata_equal=True))
 suffix={'ZL_EVA':'','ZL_merged':'_merged','IT_EVA':'_IT'}[name];old=read(ROOT/'results'/('boundary_word_confirm'+suffix+'_pairs.json'));new=read(R/('boundary_'+name+'_rows.json.gz'));assert [coord(r) for r in new]==[coord(r) for r in old]
 for x,y in zip(new,old):
  for k,v in y.items():assert x['mapped_word' if k=='word' else k]==v,(name,k)
 checks.append(dict(name=name,family='boundary',all_original_context_fields_equal=True))
report=dict(checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,checks=checks,source='Only saved confirm/preflight records and archived confirm arrays; no corpus import, reserve or training load.',reserve_read=False,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
out=P/'preflight_reference_audit.json';assert not out.exists();out.write_text(json.dumps(report,indent=2)+'\n');print('All nine allograph, three paragraph and three boundary field checks passed')
