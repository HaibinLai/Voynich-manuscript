"""Verify the published package without fitting or rescoring."""
import pathlib,json,hashlib,sys
root=pathlib.Path(__file__).resolve().parent
manifest=json.loads((root/'manifest.json').read_text()); errors=[]
for entry in manifest['files']:
 p=root/entry['path']
 if not p.is_file():errors.append({'path':entry['path'],'error':'missing'});continue
 if p.stat().st_size!=entry['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=entry['sha256']:
  errors.append({'path':entry['path'],'error':'content_mismatch'})
for entry in json.loads((root/'freeze.json').read_text())['files']:
 p=root/entry['path']
 if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=entry['sha256']:
  errors.append({'path':entry['path'],'error':'frozen_content_mismatch'})
print(json.dumps({'passed':not errors,'files':len(manifest['files']),'errors':errors},indent=2))
raise SystemExit(bool(errors))
