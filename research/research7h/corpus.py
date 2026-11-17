"""Full-corpus normalization with immutable leaf splits and source provenance."""
from pathlib import Path
from collections import Counter, defaultdict
import sys, re, json, hashlib, datetime
import numpy as np

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent
sys.path.insert(0,str(BASE))
from build_corpus import parse
sys.path.insert(0,str(BASE/'study20'))
from analyze import tokenize,units,edit_le_one

def save(name,obj):
    p=ROOT/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False))

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def leaf(f):
    if f=='fRos' or re.match(r'f8[56][rv]',f):return 'f85_86'
    m=re.match(r'f\d+',f)
    return m[0] if m else f

def all_pages(source='ZL3b-n.txt',spaces='split',alternatives='exclude'):
    records,metadata=parse(source)
    pages={f:dict(folio=f,leaf=leaf(f),metadata=m,lines=[]) for f,m in metadata.items()}
    states={f:dict(paragraph=-1,known=False,block=-1) for f in pages}
    skipped=Counter()
    for ri,r in enumerate(records):
        kind=r['locus_type'];f=r['folio'];raw=r['text_ivtff'];state=states[f];page=pages[f]
        if kind[1:] not in ['P0','P1','Pc','Pr','Pt'] or kind[0]=='!':
            skipped[kind]+=1;continue
        start='<%>' in raw;end='<$>' in raw
        previous=records[ri-1] if ri else None
        # '=' is relative to the immediately preceding *source* locus. It may
        # align prose to a margin label, not continue the prior prose line.
        joins_previous=(kind[0]=='=' and previous is not None and previous['folio']==f
                        and page['lines'] and previous['locator']==page['lines'][-1]['loci'][-1])
        if joins_previous or kind[1:]=='Pt':
            if not page['lines']:raise ValueError(('orphan continuation',r['locator']))
            if start:raise ValueError(('paragraph starts in continuation',r['locator']))
            line=page['lines'][-1]
            line['tokens'].extend(tokenize(raw,spaces,alternatives));line['loci'].append(r['locator'])
            line['source_lines'].append(r['source_line']);line['paragraph_end']|=end
            line['drawing_interruptions']+=len(re.findall(r'<[-~]>',raw))
            if end:state['known']=False
            continue
        if kind[0]=='@':
            state['block']+=1;state['known']=False
        if start:
            state['paragraph']+=1;state['known']=True
        page['lines'].append(dict(tokens=tokenize(raw,spaces,alternatives),loci=[r['locator']],
            source_lines=[r['source_line']],locus_type=kind,paragraph_start=start,
            paragraph_end=end,paragraph_known=state['known'],paragraph=state['paragraph'],
            block=state['block'],aligned_to_excluded_locus=kind[0]=='=',
            drawing_interruptions=len(re.findall(r'<[-~]>',raw))))
        if end:state['known']=False
    return [p for p in pages.values() if p['lines']],dict(skipped)

def freeze_split():
    pages,skipped=all_pages()
    original=json.loads((BASE/'study20/selection.json').read_text())
    legacy={leaf(x['folio']) for x in original}|{'f1','f3'}
    groups=defaultdict(list)
    for p in pages:groups[p['leaf']].append(p)
    strata=defaultdict(list);mapping={}
    for key,pp in groups.items():
        attrs=[(p['metadata'].get('I','?'),p['metadata'].get('H','?'),p['metadata'].get('L','?')) for p in pp]
        stratum=Counter(attrs).most_common(1)[0][0]
        if key in legacy:mapping[key]='legacy'
        else:strata[stratum].append(key)
    rng=np.random.default_rng(2026111701)
    pattern=['train','dev','train','confirm','reserve']
    for stratum,keys in sorted(strata.items()):
        keys=sorted(keys);rng.shuffle(keys)
        for i,key in enumerate(keys):mapping[key]=pattern[i%5]
    manifest=[]
    for p in pages:
        manifest.append(dict(folio=p['folio'],leaf=p['leaf'],split=mapping[p['leaf']],metadata=p['metadata']))
    existing=ROOT/'split_manifest.json'
    if existing.exists():assert json.loads(existing.read_text())==manifest,'Never silently change a frozen split'
    else:save('split_manifest.json',manifest)
    receipt=dict(frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
         manifest_sha256=sha(existing),protocol_sha256=sha(ROOT/'stage1_protocol.txt'),
         source_sha256=sha(BASE/'sources/ZL3b-n.txt'),
         page_counts=dict(Counter(x['split'] for x in manifest)),
         leaf_counts=dict(Counter(mapping.values())),
         skipped_loci_by_type=skipped,
         caution='Split frozen before stage-specific outcome statistics; public corpus and prior extraction are not fully blind.')
    if (ROOT/'split_receipt.json').exists():
        old=json.loads((ROOT/'split_receipt.json').read_text())
        for k in ['manifest_sha256','protocol_sha256','source_sha256']:assert old[k]==receipt[k]
    else:save('split_receipt.json',receipt)
    return manifest

def load(source='ZL3b-n.txt',spaces='split',alternatives='exclude',splits=None):
    manifest={x['folio']:x for x in json.loads((ROOT/'split_manifest.json').read_text())}
    pages,_=all_pages(source,spaces,alternatives)
    for p in pages:p['split']=manifest[p['folio']]['split']
    return [p for p in pages if splits is None or p['split'] in splits]

def verify():
    p=load();assert len({x['folio'] for x in p})==len(p)
    ls=defaultdict(set)
    for x in p:ls[x['leaf']].add(x['split'])
    assert all(len(v)==1 for v in ls.values())
    f25=next(x for x in p if x['folio']=='f25r')
    assert len(f25['lines'])==6 and f25['lines'][-1]['loci']==['f25r.6','f25r.7']
    f49=next(x for x in p if x['folio']=='f49v')
    assert len(f49['lines'])==26 and len(f49['lines'][0]['loci'])==1
    assert tokenize('a<->b<~>c')==['a','b','c']
    assert tokenize('a.[b:c].d?')==['a',None,None]
    assert units('@177;ch','merged')==('@177;','ch')
    for x in p:
        for l in x['lines']:
            assert len(l['loci'])==len(l['source_lines'])
            for t in l['tokens']:
                if t is not None:units(t)
    return dict(pages=len(p),leaves=len(ls),tests='leaf separation, unique pages, original20 physical-line join, token and unit parsing')

if __name__=='__main__':
    freeze_split();save('corpus_verification.json',verify())
    train=load(splits=['legacy','train','dev','confirm'])
    save('stage1_corpus.json',train)
    print(json.dumps(json.loads((ROOT/'split_receipt.json').read_text()),indent=2))
