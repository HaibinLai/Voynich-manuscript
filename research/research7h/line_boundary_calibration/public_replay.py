"""Replay saved synthetic evidence in a fresh portable layout; never fit a grid."""
from pathlib import Path
import argparse,datetime,hashlib,json,shutil,subprocess,sys

HERE=Path(__file__).resolve().parent
EXTERNAL={
    '../boundary.py':'reference_dependencies/boundary.py',
    '../line_boundary_design/population.json':'reference_dependencies/population.json',
    '../../study20/analyze.py':'reference_dependencies/analyze.py',
}


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def safe(relative):
    p=Path(relative)
    if p.is_absolute() or '..' in p.parts:raise ValueError('Unsafe publication member')
    return HERE/p


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();out=args.output.resolve()
    assert not out.exists() and out!=HERE and HERE not in out.parents
    manifest=json.loads((HERE/'artifact_manifest.json').read_text());checked=[]
    for item in manifest['files']:
        if not item['publish']:continue
        p=safe(item['path']);assert p.is_file() and digest(p)==item['sha256'] and p.stat().st_size==item['bytes']
        checked.append(item['path'])
    freeze=json.loads((HERE/'freeze.json').read_text())
    for item in freeze['files']:
        source=safe(EXTERNAL.get(item['path'],item['path']))
        assert digest(source)==item['sha256']
    out.mkdir(parents=True)
    workspace=out/'workspace';target=workspace/'research7h/line_boundary_calibration';target.mkdir(parents=True)
    for item in freeze['files']:
        source=safe(EXTERNAL.get(item['path'],item['path']))
        destination=(target/item['path']).resolve()
        assert workspace in destination.parents
        destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination)
    shutil.copyfile(HERE/'freeze.json',target/'freeze.json')
    receipt=dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        mode='saved_synthetic_replay',publication_manifest_sha256=digest(HERE/'artifact_manifest.json'),
        publication_files_checked=len(checked),frozen_dependencies_checked=len(freeze['files']),
        freeze_sha256=digest(HERE/'freeze.json'),external_dependency_mapping=EXTERNAL,
        original_frozen_bytes_preserved=True,independent_cv_grid_rerun=False,
        manuscript_input_loaded=False,reserve_loaded=False)
    (out/'execution_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    with (out/'replay.log').open('w') as log:
        p=subprocess.run([sys.executable,str(target/'independent_replay.py'),'--run',str(HERE/'run_v1'),
                          '--output',str(out/'verification.json')],stdout=log,stderr=subprocess.STDOUT)
    receipt.update(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),returncode=p.returncode,passed=p.returncode==0)
    (out/'complete.json').write_text(json.dumps(receipt,indent=2)+'\n')
    if p.returncode:raise SystemExit('Replay failed; fresh workspace and log preserved.')
    print(json.dumps(dict(passed=True,publication_files_checked=len(checked),frozen_dependencies_checked=len(freeze['files']))))


if __name__=='__main__':main()
