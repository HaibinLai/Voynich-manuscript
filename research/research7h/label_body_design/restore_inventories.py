"""Restore exact, length-only audit inputs; never overwrite a differing file."""
from pathlib import Path
import gzip,hashlib,json
P=Path(__file__).resolve().parent
for item in json.loads((P/'inventory_archives.json').read_text()):
    compressed=(P/item['archive']).read_bytes()
    assert hashlib.sha256(compressed).hexdigest()==item['archive_sha256']
    raw=gzip.decompress(compressed)
    assert hashlib.sha256(raw).hexdigest()==item['raw_sha256']
    target=P/item['path']
    if target.exists():assert target.read_bytes()==raw, 'Refusing to overwrite differing inventory'
    else:target.write_bytes(raw)
print('Exact audit inventories restored or confirmed.')
