"""Acquire only the existing 20 selected manuscript canvases from Yale's manifest."""
from pathlib import Path
from urllib.request import Request,urlopen
from concurrent.futures import ThreadPoolExecutor
import datetime,hashlib,io,json
from PIL import Image

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent.parent
URL='https://collections.library.yale.edu/manifests/2002046'

def sha(data):return hashlib.sha256(data).hexdigest()

def main():
    manifest=ROOT/'yale_manifest.json'
    if not manifest.exists():manifest.write_bytes(urlopen(Request(URL,headers={'User-Agent':'VoynichResearch/1.0'}),timeout=30).read())
    doc=json.loads(manifest.read_text())
    canvases={c['id'].split('/')[-1]:c for c in doc['items']}
    selection=json.loads((BASE/'study20/selection.json').read_text())
    (ROOT/'images').mkdir(exist_ok=True)
    def acquire(item):
        canvas=canvases[item['image_id']]
        body=canvas['items'][0]['items'][0]['body'];url=body['id']
        assert url.startswith('https://collections.library.yale.edu/iiif/2/')
        path=ROOT/'images'/f'{item["folio"]}.jpg'
        if not path.exists():
            data=urlopen(Request(url,headers={'User-Agent':'VoynichResearch/1.0'}),timeout=60).read()
            im=Image.open(io.BytesIO(data));assert im.size==(body['width'],body['height'])
            path.write_bytes(data)
        data=path.read_bytes();im=Image.open(io.BytesIO(data))
        assert im.size==(body['width'],body['height'])
        pdf=(BASE/'study20/images'/path.name).read_bytes()
        return dict(folio=item['folio'],image_id=item['image_id'],canvas_id=canvas['id'],
                    canvas_label=canvas['label'],source_url=url,local_path=str(path.relative_to(ROOT)),
                    image_sha256=sha(data),bytes=len(data),width=im.width,height=im.height,
                    pdf_image_sha256=sha(pdf),pdf_dimensions=[item['image_width'],item['image_height']],
                    attribution='Cipher manuscript (Voynich manuscript). General Collection, Beinecke Rare Book and Manuscript Library, Yale University.')
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows=list(pool.map(acquire,selection))
    receipt=dict(retrieved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 manifest_url=URL,manifest_sha256=sha(manifest.read_bytes()),selected_pages=len(rows),images=rows,
                 rights_note='The manifest has no machine-readable rights URI. Its generic Rights statement is preserved in the full manifest; manuscript predates modern copyright. Use Yale attribution. No modern PDF frontmatter included.')
    (ROOT/'yale_image_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps([dict(folio=r['folio'],dimensions=[r['width'],r['height']],bytes=r['bytes']) for r in rows],indent=2))

if __name__=='__main__':main()
