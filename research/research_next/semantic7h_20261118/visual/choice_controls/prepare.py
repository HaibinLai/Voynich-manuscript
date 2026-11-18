"""Freeze visual-only three-candidate questions; fetch unchanged official IIIF crops."""
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import argparse, hashlib, json, random, re, urllib.request

HERE = Path(__file__).resolve().parent
BASE = HERE.parent.parent

def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p, d): p.write_text(json.dumps(d, ensure_ascii=False, indent=2)+'\n')
def leaf(f): return re.match(r'f\d+', f).group()

def image_spec(row, side, first):
    obj = row[side]
    if first:
        return dict(folio=row[side+'_folio'], url=obj['source_url'],
                    box=obj['object_region_xywh'], size=obj['full_image_size'])
    return dict(folio=row[side+'_folio'], url=obj['official_image_url'],
                box=obj['object_reading_bbox_xywh'], size=obj['full_size'])

def crop_url(spec):
    x,y,w,h = spec['box']; width,height = spec['size']
    assert min(x,y) >= 0 and min(w,h) > 0 and x+w <= width and y+h <= height
    return spec['url'].replace('/full/full/', '/'+','.join(map(str,[x,y,w,h]))+'/'+str(min(700,w))+',/')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--anonymous-output',type=Path,required=True)
    args=ap.parse_args()
    if (HERE/'selection_v1.json').exists() or args.anonymous_output.exists():
        raise SystemExit('Use a fresh study and output directory; never replace a frozen question set.')
    a=BASE/'visual/crossplant/crossplant_visual_review_v1.json'
    b=BASE/'visual/order_targets/review_v1.json'
    first=read(a)['records'];second=read(b)['records']
    pool={}
    for row,isfirst in sorted([(r,True) for r in first]+[(r,False) for r in second],key=lambda x:x[0]['fragment_id']):
        pool.setdefault(row['target_folio'],image_spec(row,'target',isfirst))
    rng=random.Random(2026111801); questions=[];jobs=[];anonymous=[]
    for i,row in enumerate(sorted(first,key=lambda r:r['fragment_id']),1):
        qid='Q%02d'%i;source=image_spec(row,'source',True);target=pool[row['target_folio']]
        controls=[s for f,s in pool.items() if leaf(f) not in {leaf(row['source_folio']),leaf(row['target_folio'])}]
        choices=[target]+rng.sample(controls,2);rng.shuffle(choices)
        candidates=[]
        for letter,spec in zip('ABC',choices):
            fn=qid+'_'+letter+'.jpg';url=crop_url(spec)
            candidates.append(dict(code=letter,file=fn,**spec,crop_url=url,
                                   prior_hypothesis=(spec['folio']==row['target_folio'])))
            jobs.append((fn,url))
        srcfile=qid+'_source.jpg';jobs.append((srcfile,crop_url(source)))
        questions.append(dict(question_id=qid,pair_id=row['pair_id'],fragment_id=row['fragment_id'],
                              source=dict(file=srcfile,**source,crop_url=crop_url(source)),candidates=candidates))
        anonymous.append(dict(question_id=qid,source_file=srcfile,
                              candidates=[{'code':c['code'],'file':c['file']} for c in candidates]))
    write(HERE/'selection_v1.json',dict(seed=2026111801,question_count=12,
          unique_target_pool_count=len(pool),pool=list(pool.values()),questions=questions))
    write(HERE/'freeze_v1.json',dict(utc=datetime.now(timezone.utc).isoformat(),
          before_candidate_review=True,post_previous_experiments=True,
          inputs={str(p.relative_to(BASE)):sha(p) for p in [a,b]},
          files={n:sha(HERE/n) for n in ['protocol_v1.txt','prepare.py','selection_v1.json']}))
    args.anonymous_output.mkdir(parents=True)
    def fetch(job):
        fn,url=job
        req=urllib.request.Request(url,headers={'User-Agent':'VoynichResearch/1.0'})
        data=urllib.request.urlopen(req,timeout=60).read()
        assert data[:2]==b'\xff\xd8', 'Expected original JPEG response'
        (args.anonymous_output/fn).write_bytes(data)
        return dict(file=fn,url=url,bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    with ThreadPoolExecutor(max_workers=4) as pool_executor:
        receipts=list(pool_executor.map(fetch,jobs))
    write(HERE/'acquisition_v1.json',dict(utc=datetime.now(timezone.utc).isoformat(),
          files=receipts,transform='Official IIIF crop/resizing response, unchanged bytes.'))
    write(args.anonymous_output/'questions.json',dict(questions=anonymous))
    write(args.anonymous_output/'image_hashes.json',{'files':[{k:r[k] for k in ['file','bytes','sha256']} for r in receipts]})
    print('Frozen and acquired',len(questions),'questions;',len(jobs),'image files;',len(pool),'unique target pages')

if __name__=='__main__':main()
