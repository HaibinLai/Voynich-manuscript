"""Public reruns in fresh directories; no fresh manuscript confirm/reserve mode."""
from pathlib import Path
import argparse,datetime,gzip,hashlib,importlib.util,json,shutil,sys
P=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def loadmod(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def preflight():
 checked=[]
 for name in ('protocol_receipt.json','execution_receipt.json'):
  for row in json.loads((P/name).read_text())['files']:
   assert sha(P/row['path'])==row['sha256'],row['path'];checked.append(dict(receipt=name,**row))
 assert sha(P.parent/'corpus.py')==sha(P/'reference_corpus.py')
 return dict(all_passed=True,files=checked,checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())

def newout(out,mode,check):
 out=Path(out).resolve();assert out!=P and P not in out.parents;assert not out.exists(),'Output must be a new nonexistent directory';out.mkdir(parents=True)
 shutil.copy2(P/'protocol_receipt.json',out/'protocol_receipt.json')
 receipt=dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),mode=mode,driver_sha256=sha(Path(__file__)),original_execution_receipt_sha256=sha(P/'execution_receipt.json'),preflight=check,confirm_reload_allowed=False,reserve_allowed=False)
 (out/'execution_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');return out

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['preflight','calibrate','replay']);p.add_argument('--output',type=Path);p.add_argument('--seeds',type=int,nargs='+',default=list(range(2026111741,2026111746)));p.add_argument('--scope',choices=['all','synthetic','manuscript'],default='all');a=p.parse_args();check=preflight()
 if a.mode=='preflight':print(json.dumps(check,indent=2));return
 assert a.output is not None;out=newout(a.output,a.mode,check);sys.path.insert(0,str(P))
 if a.mode=='calibrate':
  assert set(a.seeds)<=set(range(2026111741,2026111746));run=loadmod('allograph_public_frozen_run',P/'run.py');run.P=out;results=[]
  for mechanism in ('iid','position','correlated'):
   for seed in a.seeds:
    result=run.toy_task((mechanism,seed))
    for r in result:
     original=json.loads((P/'runs'/(r['name']+'_'+r['merge']+'.json')).read_text());assert abs(original['selected_gain']['mean_leaf_bits_saved']-r['gain'])<1e-11
    results.extend(result)
  (out/'public_calibration_verification.json').write_text(json.dumps(dict(all_passed=True,runs=results),indent=2)+'\n')
 else:
  archives=json.loads((P/'data_archives.json').read_text())['files'];byoriginal={r['original']:r for r in archives};copied=set()
  def transfer(rel,expected=None):
   if rel in copied:return
   dest=out/rel;dest.parent.mkdir(parents=True,exist_ok=True)
   if rel in byoriginal:
    ar=byoriginal[rel];assert sha(P/ar['archive'])==ar['archive_sha256'];raw=gzip.decompress((P/ar['archive']).read_bytes());assert hashlib.sha256(raw).hexdigest()==ar['original_sha256'];dest.write_bytes(raw)
   else:shutil.copy2(P/rel,dest)
   if expected:assert sha(dest)==expected
   copied.add(rel)
  for f in sorted((P/'runs').glob('*.json')):
   if a.scope=='synthetic' and not f.name.startswith('toy_'):continue
   if a.scope=='manuscript' and f.name.startswith('toy_'):continue
   r=json.loads(f.read_text());transfer(str(f.relative_to(P)));transfer(r['config_path'],r['config_sha256']);cfg=json.loads((P/r['config_path']).read_text());transfer(cfg['input_path'],cfg['input_sha256']);transfer(r['target_path'],r['target_sha256']);transfer(r['score_path'],r['score_sha256'])
  replay=loadmod('allograph_public_independent_replay',P/'replay.py');replay.P=out;replay.main(a.scope)
 (out/'public_complete.json').write_text(json.dumps(dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),mode=a.mode,confirm_reloaded=False,reserve_requested=False))+'\n')
if __name__=='__main__':main()
