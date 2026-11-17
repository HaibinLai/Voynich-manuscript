"""Restore exact frozen JSON targets from public gzip archives, checking both hashes."""
from pathlib import Path
import argparse,gzip,hashlib,json
P=Path(__file__).resolve().parent
sha=lambda data:hashlib.sha256(data).hexdigest()

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--verify-only',action='store_true');args=parser.parse_args()
 items=json.loads((P/'target_archives.json').read_text())['files']
 for item in items:
  packed=(P/item['archive']).read_bytes();assert sha(packed)==item['archive_sha256']
  raw=gzip.decompress(packed);assert sha(raw)==item['original_sha256'] and len(raw)==item['original_bytes']
  target=P/item['original']
  if target.exists():assert sha(target.read_bytes())==item['original_sha256'],'Refusing to overwrite changed original'
  elif not args.verify_only:target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
 print(f'Checked {len(items)} archives; '+('verification only' if args.verify_only else 'all exact original targets present'))

if __name__=='__main__':main()
