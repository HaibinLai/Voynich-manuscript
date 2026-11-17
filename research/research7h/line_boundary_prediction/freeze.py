"""Future preparation freeze, not an execution permission or a scoring command."""
from pathlib import Path
import datetime,hashlib,json
from data import SOURCES
HERE=Path(__file__).resolve().parent
def main():
    target=HERE/'freeze.json';assert not target.exists()
    names=['protocol.txt','data.py','models.py','run.py','freeze.py','verify_toy.py','toy_verification.json',
           'reference_conditional.py','reference_charlm.py','reference_provenance.json','pre_run_review.json']
    names += [f'../metadata_sensitivity/inputs/{source}_{split}.json.gz' for source,split in SOURCES]
    entries=[dict(path=n,sha256=hashlib.sha256((HERE/n).read_bytes()).hexdigest()) for n in names]
    with target.open('x') as f:json.dump(dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=entries,
        scope='future_crossline_trainlegacy_dev_only',execution_gate_not_created_by_freeze=True),f,indent=2);f.write('\n')
if __name__=='__main__':main()
