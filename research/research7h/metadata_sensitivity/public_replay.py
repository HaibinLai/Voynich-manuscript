"""Validate the public saved packet and independently replay in a fresh directory."""
from pathlib import Path
import argparse
import datetime
import subprocess
import sys
from metadata import HERE,ROOT,read,write,sha


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,default=HERE/'confirm_v1')
    ap.add_argument('--out-dir',type=Path,required=True)
    args=ap.parse_args();assert not args.out_dir.exists(),'Fresh output directory required.'
    freeze=read(HERE/'freeze.json');checked=[];not_needed=[]
    for e in freeze['files']:
        if e['path'].startswith('../sources/'):
            not_needed.append(e['path']);continue
        assert sha(ROOT/e['path'])==e['sha256'],e['path'];checked.append(e['path'])
    original=read(HERE/'replay_verification.json')
    assert sha(HERE/'replay.py')==original['source_replay_sha256']
    assert sha(ROOT/'allograph_factor/replay.py')==original['scalar_reference_sha256']
    complete=read(args.run/'complete.json');assert complete['all_passed'] and complete['freeze_sha256']==sha(HERE/'freeze.json')
    for job in complete['jobs']:
        prefix=job['family']+'_'+job['name'];receipt=read(args.run/(prefix+'.json'))
        assert sha(args.run/(prefix+'.npz'))==receipt['scores_sha256']
        assert sha(args.run/(prefix+'_rows.json.gz'))==receipt['rows_sha256']
        assert receipt['freeze_sha256']==sha(HERE/'freeze.json')
    args.out_dir.mkdir(parents=True)
    write(args.out_dir/'execution_receipt.json',dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        freeze_sha256=sha(HERE/'freeze.json'),saved_complete_sha256=sha(args.run/'complete.json'),
        verified_package_relative_dependencies=checked,raw_transcription_files_not_reopened=not_needed,
        no_new_corpus_page_loading=True,no_new_target_scoring=True,saved_probability_arrays_recomputed=True))
    command=[sys.executable,str(HERE/'replay.py'),'--run',str(args.run),'--out',str(args.out_dir/'verification.json')]
    with (args.out_dir/'replay.log').open('w') as stream:result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
    assert result.returncode==0,'Replay failed; retain the fresh directory and inspect its log.'
    print('Saved corrected models independently reproduced; raw transcriptions not reopened.')


if __name__=='__main__':main()
