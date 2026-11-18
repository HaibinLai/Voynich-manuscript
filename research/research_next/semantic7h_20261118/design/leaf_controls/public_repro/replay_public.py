#!/usr/bin/env python3
"""Safely replay the archived independent leaf audit without modifying its code."""
import argparse,datetime,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
REL=Path('research/research_next/semantic7h_20261118/design/leaf_controls')
EXCLUDED={str(REL/'leaf_audit_v1.json'),str(REL/'leaf_audit_v1.txt')}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inside(a,b):return a==b or b in a.parents
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path(__file__).resolve().parents[6],help='Root of the public repository or explicit allowlist export')
    parser.add_argument('--output',type=Path,required=True,help='New directory outside the source repository')
    args=parser.parse_args();source=args.source.resolve();out=args.output.resolve()
    if args.output.exists() or args.output.is_symlink():parser.error('Output already exists; refusing overwrite')
    if inside(out,source) or inside(source,out):parser.error('Output must be outside the source repository and cannot contain it')
    manifest=json.loads((Path(__file__).parent/'payload_manifest_v1.json').read_text())
    entries=manifest['files'];before={}
    for rel,expected in entries.items():
        r=Path(rel)
        if r.is_absolute() or '..' in r.parts:raise ValueError('Unsafe manifest path')
        path=(source/r).resolve()
        if not inside(path,source) or not path.is_file():raise ValueError('Missing or external source file: '+rel)
        before[rel]=sha(path)
        if before[rel]!=expected:raise ValueError('Source hash differs from frozen public payload: '+rel)
    out.mkdir(parents=True,exist_ok=False)
    try:
        work=out/'working_tree'
        for rel in entries:
            if rel in EXCLUDED:continue
            target=work/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/rel,target)
        env=os.environ.copy();env.pop('PYTHONPATH',None);env['PYTHONDONTWRITEBYTECODE']='1';env.pop('PYTHONNOUSERSITE',None)
        with (out/'audit_stdout.txt').open('w') as log:
            result=subprocess.run([sys.executable,str(work/REL/'audit_leaf.py')],cwd=work,env=env,stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:raise RuntimeError('Archived independent audit exited with code '+str(result.returncode))
        original=json.loads((source/REL/'leaf_audit_v1.json').read_text());new=json.loads((work/REL/'leaf_audit_v1.json').read_text())
        left={k:v for k,v in original.items() if k!='elapsed_seconds'};right={k:v for k,v in new.items() if k!='elapsed_seconds'}
        if left!=right:raise RuntimeError('Fresh independent report differs from archived report outside elapsed_seconds')
        if new['status']!='PASS' or new['failures']:raise RuntimeError('Fresh independent audit did not pass')
        if (source/REL/'leaf_audit_v1.txt').read_bytes()!=(work/REL/'leaf_audit_v1.txt').read_bytes():raise RuntimeError('Fresh text report differs')
        after={rel:sha(source/rel) for rel in entries}
        if before!=after:raise RuntimeError('Source input changed during replay')
        for rel in entries:
            if rel not in EXCLUDED and sha(work/rel)!=before[rel]:raise RuntimeError('Copied input changed during audit: '+rel)
        shutil.copyfile(work/REL/'leaf_audit_v1.json',out/'leaf_audit_replayed.json')
        shutil.copyfile(work/REL/'leaf_audit_v1.txt',out/'leaf_audit_replayed.txt')
        receipt=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='PASS_PUBLIC_INDEPENDENT_REPLAY',scope='Re-execution of the unchanged archived independent implementation, not a new independent method or experiment.',input_files=len(entries),copied_working_input_files=len(entries)-len(EXCLUDED),source_unchanged=True,working_inputs_unchanged=True,archived_report_preserved=True,json_comparison='All fields exact except elapsed_seconds; no numerical fields excluded',text_report_byte_identical=True,checks=sum(new['checks'].values()),packages=len(new['packages']),failures=new['failures'],elapsed_seconds=new['elapsed_seconds'],payload_manifest_sha256=sha(Path(__file__).parent/'payload_manifest_v1.json'),wrapper_sha256=sha(Path(__file__)),archived_audit_script_sha256=sha(source/REL/'audit_leaf.py'),archived_receipt_sha256=sha(source/REL/'leaf_audit_v1.json'),replayed_receipt_sha256=sha(out/'leaf_audit_replayed.json'),source_hashes_before=before,source_hashes_after=after)
        (out/'complete.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({k:receipt[k] for k in ['status','checks','packages','elapsed_seconds','source_unchanged']}))
    except BaseException as error:
        (out/'failure.json').write_text(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='FAILED_PRESERVED',error_type=type(error).__name__,error=str(error)),ensure_ascii=False,indent=2)+'\n')
        raise
if __name__=='__main__':main()
