from pathlib import Path
import gzip,hashlib,json
P=Path(__file__).resolve().parent
for r in json.loads((P/'data_archives.json').read_text())['files']:
 packed=(P/r['archive']).read_bytes();assert hashlib.sha256(packed).hexdigest()==r['archive_sha256'];raw=gzip.decompress(packed);assert hashlib.sha256(raw).hexdigest()==r['original_sha256'];p=P/r['original']
 if p.exists():assert hashlib.sha256(p.read_bytes()).hexdigest()==r['original_sha256']
 else:p.parent.mkdir(exist_ok=True);p.write_bytes(raw)
print('All saved inputs and targets restored or verified; no scoring performed')
