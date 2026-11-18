"""Fetch official images for the already fixed 12-locus reading queue."""
from pathlib import Path
from urllib.request import urlopen,Request
from concurrent.futures import ThreadPoolExecutor
import argparse,json,hashlib,datetime

HERE=Path(__file__).resolve().parent
RESEARCH=HERE.parents[2]
def sha(b):return hashlib.sha256(b).hexdigest()
def main(out):
    out.mkdir(parents=True,exist_ok=True)
    candpath=RESEARCH/'research_next/label_body/saved_v1/candidates.json'
    candidates=json.loads(candpath.read_text())
    manifest_path=RESEARCH/'research7h/visual_audit/yale_manifest.json'
    manifest=json.loads(manifest_path.read_text())
    canvases={c['label']['none'][0]:c for c in manifest['items']}
    names={'f67r2':'67r','f68r1':'68r','f75v':'75v'}
    selected=[dict(group=group,locator=r['locator'],word=r['word'],ZL=r['ZL'],IT=r['IT']) for group in ['both_hit','both_no_hit'] for r in candidates[group][:6]]
    folios=sorted({r['ZL']['folio'] for r in selected})
    def acquire(args):
        number,f=args; canvas=canvases[names[f]];body=canvas['items'][0]['items'][0]['body'];url=body['id']
        assert url.startswith('https://collections.library.yale.edu/iiif/2/')
        name=f'page_{number:02d}.jpg';p=out/name
        if not p.exists():p.write_bytes(urlopen(Request(url,headers={'User-Agent':'VoynichResearch/1.0'}),timeout=60).read())
        b=p.read_bytes()
        return dict(anonymous_id=f'page_{number:02d}',file=name,folio=f,physical_label=names[f],canvas_id=canvas['id'],source_url=url,width=body['width'],height=body['height'],sha256=sha(b),bytes=len(b),attribution='Yale University Library, Beinecke MS 408')
    with ThreadPoolExecutor(max_workers=3) as ex: images=list(ex.map(acquire,enumerate(folios,1)))
    queue=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),prior_candidate_sha256=sha(candpath.read_bytes()),manifest_sha256=sha(manifest_path.read_bytes()),protocol_sha256=sha((HERE/'protocol_v1.txt').read_bytes()),selected=selected,images=images)
    assert not (HERE/'queue_v1.json').exists()
    (HERE/'queue_v1.json').write_text(json.dumps(queue,ensure_ascii=False,indent=2)+'\n')
    blind=[{k:r[k] for k in ['anonymous_id','file','source_url','width','height','sha256','attribution']} for r in images]
    (HERE/'image_only_roster.json').write_text(json.dumps(blind,indent=2)+'\n')
    print(json.dumps(blind,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
