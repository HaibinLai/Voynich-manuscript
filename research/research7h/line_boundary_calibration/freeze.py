"""Freeze only this synthetic design; does not start or authorize any run."""
from pathlib import Path
import datetime,hashlib,json
HERE=Path(__file__).resolve().parent
FILES=('protocol.txt','prepare_skeleton.py','skeleton.json.gz','skeleton_receipt.json',
       'observer.py','run.py','independent_replay.py','verify_toy.py','toy_verification.json','freeze.py','pre_run_review.json',
       '../boundary.py','../line_boundary_design/population.json','../../study20/analyze.py')
def main():
    out=HERE/'freeze.json';assert not out.exists()
    files=[dict(path=f,sha256=hashlib.sha256((HERE/f).read_bytes()).hexdigest()) for f in FILES]
    with out.open('x') as stream:
        json.dump(dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            scope='synthetic_only',files=files,manuscript_target_scoring_allowed=False,reserve_allowed=False),stream,indent=2);stream.write('\n')
if __name__=='__main__':main()
