"""Root-owned explicit-page metadata extraction; no split selection or scoring."""
from pathlib import Path
import argparse
import datetime
from metadata import HERE,ROOT,read,write,sha,source_sidecar


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pages',type=Path,required=True)
    ap.add_argument('--source',choices=['ZL3b-n.txt','IT2a-n.txt'],required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    assert not args.out.exists()
    freeze=read(HERE/'freeze.json')
    for row in freeze['files']:
        assert sha(ROOT/row['path'])==row['sha256'],row['path']
    source=next(r for r in freeze['files'] if r['path']=='../sources/'+args.source)
    pages=read(args.pages)
    value=source_sidecar(args.source,pages,source['sha256'])
    value.update(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        input_pages_sha256=sha(args.pages),freeze_sha256=sha(HERE/'freeze.json'))
    write(args.out,value)
    print('Explicit supplied pages verified and metadata sidecar written; no model fit or score.')


if __name__=='__main__':main()
