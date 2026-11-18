from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import json,urllib.request,hashlib,datetime
P=Path(__file__).resolve().parent;queue=json.loads((P/'queue_v1.json').read_text())
def fetch(task):
 oid,size=task;name=oid+('_overview' if size!='full' else '')+'.jpg';url=f'https://collections.library.yale.edu/iiif/2/{oid}/full/{size}/0/default.jpg';f=P/'assets'/name
 if not f.exists():
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=90) as r:f.write_bytes(r.read())
 return {'oid':oid,'url':url,'file':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'size':list(Image.open(f).size),'kind':'official_full' if size=='full' else 'official_overview','viewed':False,'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
tasks=[(r['target_canvas']['oid'],size) for r in queue for size in ('full','1200,')]
with ThreadPoolExecutor(max_workers=4) as ex:assets=list(ex.map(fetch,tasks))
(P/'assets_manifest.json').write_text(json.dumps(assets,indent=2)+'\n');print('Downloaded',len(assets),'official target assets.')
