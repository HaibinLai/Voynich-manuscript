from pathlib import Path
import gzip,hashlib,json
P=Path(__file__).resolve().parent
for f in json.loads((P/'input_archives.json').read_text())['files']:
 archive=P/f['archive'];assert hashlib.sha256(archive.read_bytes()).hexdigest()==f['archive_sha256']
 raw=gzip.decompress(archive.read_bytes());assert hashlib.sha256(raw).hexdigest()==f['original_sha256']
 p=P/f['original']
 if p.exists():assert hashlib.sha256(p.read_bytes()).hexdigest()==f['original_sha256']
 else:p.write_bytes(raw)
print('60 generated input files restored/verified; original outputs untouched')
