"""Portable public entry point. Never modifies frozen evidence or reloads confirm.
Modes: preflight; rerun generator calibration; independently replay saved results.
The original run.py remains byte-exact and its strict receipt check intentionally
rejects the path-redacted generator receipt. This wrapper verifies that one,
manifest-declared transformation, then calls the frozen implementation functions.
"""
from pathlib import Path
import argparse,datetime,gzip,hashlib,importlib.util,json,shutil,sys
P=Path(__file__).resolve().parent;ROOT=P.parent
TRANSFORM='absolute source paths -> package-relative; source hash recorded'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def preflight(manifest=None):
 manifest=Path(manifest) if manifest else ROOT/'stage2_publication_manifest.json'
 pub=json.loads(manifest.read_text()) if manifest.is_file() else None
 checks=[]
 for receipt in ('execution_receipt.json','protocol_receipt.json'):
  data=json.loads((P/receipt).read_text())
  for f in data['files']:
   path=P/f['path'];actual=sha(path)
   if actual==f['sha256']:checks.append(dict(receipt=receipt,path=f['path'],sha256=actual,status='original bytes'));continue
   assert receipt=='protocol_receipt.json' and f['path']=='../generator_controls/protocol_receipt.json','Unapproved hash mismatch: '+f['path']
   assert pub is not None,'Path-redacted receipt requires publication manifest'
   matches=[x for x in pub['files'] if x['path']=='generator_controls/protocol_receipt.json'];assert len(matches)==1
   entry=matches[0]
   assert entry['source_sha256']==f['sha256'] and entry['public_sha256']==actual and entry['transformation']==TRANSFORM
   redacted=json.loads(path.read_text());assert redacted['original_receipt_sha256']==f['sha256']
   assert redacted['stage']=='before_generator_and_manuscript_outcome_statistics'
   for item in redacted['files']:
    assert not Path(item['path']).is_absolute(),'Public receipt still absolute'
    assert sha(path.parent/item['path'])==item['sha256'],'Changed referenced generator input'
   checks.append(dict(receipt=receipt,path=f['path'],original_sha256=f['sha256'],public_sha256=actual,status='manifest-declared path-only transform'))
 assert sha(ROOT/'corpus.py')==sha(P/'reference_corpus.py')
 return dict(checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),all_passed=True,files=checks,
  publication_manifest_sha256=sha(manifest) if pub is not None else None,original_run_py_modified=False,
  allowed_exception='Only the explicitly recorded generator receipt path-only publication transformation; all other frozen hashes exact.')

def prepare(out,report,mode):
 out=Path(out).resolve();assert out!=P and P not in out.parents,'Use a new output directory outside the frozen package'
 assert not out.exists(),'Output directory must not already exist'
 out.mkdir(parents=True);shutil.copy2(P/'protocol_receipt.json',out/'protocol_receipt.json')
 receipt=dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),mode=mode,driver_sha256=sha(Path(__file__)),
  original_execution_receipt_sha256=sha(P/'execution_receipt.json'),preflight=report,
  source_files=[dict(path=n,sha256=sha(P/n)) for n in ['run.py','copy_models.py','reference_models.py','reference_corpus.py','replay.py']],
  confirm_reload_allowed=False,reserve_allowed=False,original_evidence_overwritten=False,python=sys.version)
 dump(out/'execution_receipt.json',receipt);return out

def calibrate(out,seeds,reps,orders):
 sys.path.insert(0,str(P));run=module('public_frozen_copy_run',P/'run.py');run.HERE=out
 results=[]
 for seed in seeds:
  f=P/'calibration_inputs'/f'timm_{seed}.json';target=out/'calibration_inputs'/f.name;target.parent.mkdir(exist_ok=True);shutil.copy2(f,target)
  # Inputs are checked against the published artifact manifest when available.
  original_manifest=json.loads((P/'artifact_manifest.json').read_text())
  entries=original_manifest['files'] if isinstance(original_manifest,dict) else original_manifest
  found=[x for x in entries if x.get('path')==str(f.relative_to(P))]
  assert len(found)==1 and found[0]['sha256']==sha(f),'Calibration input not in original manifest'
  for rep in reps:
   for order in orders:
    task=dict(seed=seed,order=order,representation=rep);result=run.calibrate_one(task)
    original=P/'runs'/(result['name']+'.json');new=json.loads((out/'runs'/(result['name']+'.json')).read_text())
    if original.exists():
     old=json.loads(original.read_text());assert new['selected']==old['selected'] and new['baseline_weights']==old['baseline_weights']
     error=max(abs(new['contrasts'][k]['mean_leaf_bits_saved']-v['mean_leaf_bits_saved']) for k,v in old['contrasts'].items());assert error<1e-11
     result['max_gain_difference_from_original']=error
    results.append(result);print(json.dumps(result),flush=True)
 dump(out/'public_calibration_verification.json',dict(all_passed=True,runs=results,confirm_reloaded=False,reserve_requested=False))

def replay(out):
 archives=json.loads((P/'target_archives.json').read_text())['files']
 for name in ('ZL_EVA','ZL_merged','IT_EVA'):
  r=json.loads((P/'runs'/(name+'.json')).read_text())
  for rel,expected in [(r['config_path'],r['config_sha256']),(r['scores_path'],r['scores_sha256'])]:
   assert sha(P/rel)==expected;dest=out/rel;dest.parent.mkdir(exist_ok=True);shutil.copy2(P/rel,dest)
  rel=r['targets_path'];record=next(x for x in archives if x['original']==rel)
  assert record['original_sha256']==r['targets_sha256'];archive=P/record['archive'];assert sha(archive)==record['archive_sha256']
  data=gzip.decompress(archive.read_bytes());assert hashlib.sha256(data).hexdigest()==record['original_sha256']
  dest=out/rel;dest.parent.mkdir(exist_ok=True);dest.write_bytes(data)
  dest=out/'runs'/(name+'.json');dest.parent.mkdir(exist_ok=True);shutil.copy2(P/'runs'/(name+'.json'),dest)
 sys.path.insert(0,str(P));m=module('public_independent_replay',P/'replay.py');m.P=out;m.main()

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['preflight','calibrate','replay']);p.add_argument('--output',type=Path);p.add_argument('--publication-manifest',type=Path);p.add_argument('--seeds',type=int,nargs='+',default=list(range(19,39)));p.add_argument('--representation',choices=['eva','merged','both'],default='both');p.add_argument('--order',choices=['original','shuffled','both'],default='both');a=p.parse_args()
 report=preflight(a.publication_manifest)
 if a.mode=='preflight':print(json.dumps(report,indent=2));return
 assert a.output is not None,'--output NEW_DIRECTORY is required'
 assert set(a.seeds)<=set(range(19,39))
 out=prepare(a.output,report,a.mode)
 if a.mode=='replay':replay(out)
 else:calibrate(out,a.seeds,['eva','merged'] if a.representation=='both' else [a.representation],['original','shuffled'] if a.order=='both' else [a.order])
 dump(out/'public_reproduction_complete.json',dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),mode=a.mode,all_passed=True,confirm_reloaded=False,reserve_requested=False))

if __name__=='__main__':main()
