"""Run a root-gated sensitivity only on explicit saved page files."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse
import datetime
import subprocess
import sys
from metadata import HERE,ROOT,read,write,sha,source_sidecar


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pages-zl',type=Path,required=True)
    ap.add_argument('--pages-it',type=Path,required=True)
    ap.add_argument('--gate',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--old-reference',type=Path,required=True)
    args=ap.parse_args()
    assert not args.output.exists(),'Fresh run directory required; no automatic resume.'
    freeze=read(HERE/'freeze.json');fhash=sha(HERE/'freeze.json')
    for e in freeze['files']:assert sha(ROOT/e['path'])==e['sha256'],e['path']
    gate=read(args.gate)
    assert gate['allow_fixed_metadata_sensitivity'] is True and gate['freeze_sha256']==fhash
    files={'ZL3b-n.txt':args.pages_zl.resolve(),'IT2a-n.txt':args.pages_it.resolve()}
    assert gate['page_file_sha256']=={s:sha(p) for s,p in files.items()}
    reference_relative=Path(gate['old_reference_directory'])
    assert not reference_relative.is_absolute() and '..' not in reference_relative.parts
    assert (ROOT/reference_relative).resolve()==args.old_reference.resolve()
    assert args.old_reference.resolve().is_relative_to(ROOT.resolve())
    args.output.mkdir(parents=True)
    receipt=dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        freeze_sha256=fhash,gate_sha256=sha(args.gate),page_file_sha256={s:sha(p) for s,p in files.items()},
        requested_split=gate['split'],old_reference_directory=reference_relative.as_posix(),
        no_parameter_search=True,no_split_selected_by_runner=True)
    write(args.output/'execution_receipt.json',receipt)
    for source,path in files.items():
        pages=read(path);assert pages and all(p['split']==gate['split'] for p in pages)
        expected=next(e['sha256'] for e in freeze['files'] if e['path']=='../sources/'+source)
        side=source_sidecar(source,pages,expected)
        side.update(input_pages_sha256=sha(path),freeze_sha256=fhash)
        write(args.output/(source[:-4]+'_metadata.json'),side)
    tasks=[(family,name) for family in ('copy','allograph','boundary','paragraph') for name in ('ZL_EVA','ZL_merged','IT_EVA')]
    def one(task):
        family,name=task;source='IT2a-n.txt' if name=='IT_EVA' else 'ZL3b-n.txt'
        command=[sys.executable,str(HERE/'worker.py'),family,'--name',name,'--pages',str(files[source]),
            '--sidecar',str(args.output/(source[:-4]+'_metadata.json')),'--output',str(args.output),
            '--old-reference',str(args.old_reference)]
        with (args.output/(family+'_'+name+'.log')).open('w') as log:
            proc=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
        return dict(family=family,name=name,returncode=proc.returncode)
    with ThreadPoolExecutor(max_workers=2) as pool:jobs=list(pool.map(one,tasks))
    write(args.output/'complete.json',dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        freeze_sha256=fhash,all_passed=all(j['returncode']==0 for j in jobs),jobs=jobs,
        execution_receipt_sha256=sha(args.output/'execution_receipt.json')))
    assert all(j['returncode']==0 for j in jobs),jobs
    print('12 fixed-parameter jobs passed; no search or significance tests.')


if __name__=='__main__':main()
