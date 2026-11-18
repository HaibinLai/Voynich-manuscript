"""Publish an explicit whitelist after checking the independent audit bindings."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parent.parent
BASE=ROOT/'research/research_next/label_body'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
audit=json.loads((BASE/'audit_v1.json').read_text())
assert audit['passed'] and not audit['errors']
assert sha(BASE/'audit.py')==audit['code_sha256']
for name,digest in audit['input_hashes'].items():assert sha(BASE/'saved_v1'/name)==digest,name
for name,digest in audit['supplement_hashes'].items():assert sha(BASE/name)==digest,name
for entry in json.loads((BASE/'saved_v1/freeze.json').read_text())['files']:
    assert sha(ROOT/entry['path'])==entry['sha256'],entry['path']
exports={
    'report.txt':'report.txt','protocol.txt':'protocol.txt','plan.txt':'plan.txt',
    'literature_review.txt':'literature-review.txt','REPRODUCE.txt':'reproduce.txt',
    'audit_v1.txt':'audit.txt','audit_v1.json':'audit.json',
    'supplement.json':'supplement.json','supplement_protocol.txt':'supplement-protocol.txt',
    **{'saved_v1/'+name:name for name in ['results.json','candidates.json','trials.json.gz','calibration.json.gz','input.json.gz','freeze.json','complete.json']},
}
dest=ROOT/'site/downloads/label-body';dest.mkdir(parents=True,exist_ok=True)
for source,target in exports.items():shutil.copyfile(BASE/source,dest/target)
names=list(exports)+['run.py','audit.py','supplement.py','make_report.py']
manifest={'files':[{'path':name,'sha256':sha(BASE/name),'bytes':(BASE/name).stat().st_size} for name in sorted(names)]}
(BASE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Exported',len(exports),'explicit public files; bound',len(names),'research files.')
