"""Frozen, descriptive label/body comparison. Does not infer plaintext."""
from pathlib import Path
from collections import Counter, defaultdict
import argparse, datetime, gzip, hashlib, json, random, re, sys

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parents[1]
sys.path.insert(0, str(RESEARCH))
from build_corpus import parse
sys.path.insert(0, str(RESEARCH/'study20'))
from analyze import tokenize, units

IMAGE = {'La','Lc','Lf','Ln','Lp','Ls','Lt','Lz'}
BODY = {'P0','P1','Pc','Pr','Pt'}
MODELS = ['exact','fk','fp','ft','kp','kt','pt']

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def mean(x): return sum(x)/len(x) if x else None
def leaf(f):
    if f == 'fRos' or re.match(r'f8[56][rv]', f): return 'f85_86'
    m = re.match(r'f\d+', f)
    return m[0] if m else f

def write(path, obj):
    b = (json.dumps(obj, ensure_ascii=False, allow_nan=False, separators=(',',':'))+'\n').encode()
    assert b'/Users/' not in b
    path.write_bytes(gzip.compress(b, mtime=0) if path.suffix == '.gz' else b)

def packet(source):
    records, meta = parse(source)
    pages = {f:dict(folio=f, leaf=leaf(f), H=m.get('H'), I=m.get('I'), Q=m.get('Q'), body=[], labels=[]) for f,m in meta.items()}
    exclusions=Counter()
    for r in records:
        kind=r['locus_type']; typ=kind[1:]; raw=r['text_ivtff']
        if kind[0]=='!':
            exclusions['nonexistent_loci']+=1; continue
        if typ not in IMAGE|BODY: continue
        tokens=tokenize(raw, spaces='split', alternatives='exclude')
        base=dict(locator=r['locator'],source_line=r['source_line'],kind=kind,type=typ,uncertain_space=',' in raw,raw=raw)
        if typ in BODY:
            pages[r['folio']]['body'].append(dict(**base, tokens=tokens))
        else:
            exclusions['image_loci_total']+=1
            if len(tokens)!=1 or tokens[0] is None:
                exclusions['excluded_empty_multiword_or_uncertain_label']+=1
            else:
                pages[r['folio']]['labels'].append(dict(**base,word=tokens[0],units=list(units(tokens[0],'eva'))))
    exclusions['complete_singleword_labels']=sum(len(p['labels']) for p in pages.values())
    exclusions['pages']=len(pages)
    return dict(source=source,sha256=sha(RESEARCH/'sources'/source),pages=list(pages.values()),inventory=dict(exclusions))

def body_index(p, certain=False):
    out=defaultdict(list)
    for r in p['body']:
        if certain and r['uncertain_space']: continue
        for slot,w in enumerate(r['tokens']):
            if w is not None:
                u=units(w,'eva')
                out[len(u)].append(dict(word=w,units=u,locator=r['locator'],slot=slot))
    return out

def matched(a,b,model):
    if a==b:return True
    if model=='exact' or len(a)!=len(b):return False
    diffs=[(x,y) for x,y in zip(a,b) if x!=y]
    return len(diffs)==1 and set(diffs[0])==set(model)

def summarize(rows):
    if not rows:return dict(labels=0,pages=0,leaves=0,own=None,control=None,delta=None,by_leaf=[],by_page=[])
    pg=defaultdict(list)
    for r in rows:pg[r['folio']].append(r)
    page_rows=[]
    for f,rr in sorted(pg.items()):
        page_rows.append(dict(folio=f,leaf=rr[0]['leaf'],H=rr[0]['H'],I=rr[0]['I'],labels=len(rr),
                              **{k:mean([r[k] for r in rr]) for k in ['own','control','delta']}))
    ll=defaultdict(list)
    for r in page_rows:ll[r['leaf']].append(r)
    leaf_rows=[dict(leaf=l,pages=len(rr),labels=sum(r['labels'] for r in rr),
                   **{k:mean([r[k] for r in rr]) for k in ['own','control','delta']}) for l,rr in sorted(ll.items())]
    return dict(labels=len(rows),pages=len(pg),leaves=len(ll),
                **{k:mean([r[k] for r in leaf_rows]) for k in ['own','control','delta']},
                labels_with_own_match=sum(r['own_m']>0 for r in rows),by_leaf=leaf_rows,by_page=page_rows)

def score(data,model='exact',variant='main',drop=None):
    certain=variant=='certain_loci'; min_n=5 if variant=='min5' else 1
    min_leaves=2 if variant=='min5' else 1
    pages=[p for p in data['pages'] if p['leaf']!=drop]
    valid=[p for p in pages if p['H'] in list('12345') and p['I'] in list('ABCHPSTZ')]
    idx={p['folio']:body_index(p,certain) for p in valid}
    rows=[]; rejected=Counter(); label_total=0
    for p in pages:
        seen=set()
        for label in p['labels']:
            label_total+=1
            if p not in valid: rejected['unknown_or_mixed_metadata']+=1;continue
            if certain and label['uncertain_space']: rejected['uncertain_label_boundary']+=1;continue
            if variant=='dedup_labels' and label['word'] in seen: rejected['repeated_label_on_page']+=1;continue
            seen.add(label['word'])
            w=tuple(label['units']); L=len(w); own=idx[p['folio']].get(L,[])
            if len(own)<min_n: rejected['insufficient_own_length_opportunities']+=1;continue
            donors=[q for q in valid if q['leaf']!=p['leaf'] and q['H']==p['H'] and q['I']==p['I']
                    and (variant!='HIQ' or q['Q']==p['Q']) and len(idx[q['folio']].get(L,[]))>=min_n]
            if len({q['leaf'] for q in donors})<min_leaves: rejected['insufficient_other_leaf_controls']+=1;continue
            hits=[b for b in own if matched(w,b['units'],model)]
            dd=[]
            for q in donors:
                bb=idx[q['folio']][L]; m=sum(matched(w,b['units'],model) for b in bb)
                dd.append(dict(folio=q['folio'],leaf=q['leaf'],n=len(bb),m=m,rate=m/len(bb)))
            byleaf=defaultdict(list)
            for d in dd:byleaf[d['leaf']].append(d['rate'])
            ref=mean([mean(x) for x in byleaf.values()]); rate=len(hits)/len(own)
            rows.append(dict(folio=p['folio'],leaf=p['leaf'],H=p['H'],I=p['I'],Q=p['Q'],
                locator=label['locator'],type=label['type'],word=label['word'],length=L,own_n=len(own),own_m=len(hits),
                own=rate,control=ref,delta=rate-ref,control_leaves=len(byleaf),donors=dd,
                body_hits=[{k:b[k] for k in ['word','locator','slot']} for b in hits]))
    return dict(model=model,variant=variant,dropped_leaf=drop,labels_considered=label_total,excluded=dict(rejected),
                summary=summarize(rows),rows=rows)

def subgroup(rows,key):
    groups=defaultdict(list)
    for r in rows:groups[r[key]].append(r)
    return {k:summarize(v) for k,v in sorted(groups.items())}

def calibrate(data,rows):
    """Same page/length opportunity geometry, abstract uniform vocabulary."""
    page_by={p['folio']:p for p in data['pages']}
    geometry={}
    for r in rows:
        geometry[(r['folio'],r['length'])]=r['own_n']
        for d in r['donors']:geometry[(d['folio'],r['length'])]=d['n']
    output=[];first=[]
    for seed in range(2026111800,2026111900):
        rng=random.Random(seed)
        body={k:[rng.randrange(100) for _ in range(n)] for k,n in sorted(geometry.items())}
        counts={k:Counter(v) for k,v in body.items()}
        scored={'independent':[],'copy_from_own':[]}
        for r in rows:
            ownkey=(r['folio'],r['length'])
            for mode,query in [('independent',rng.randrange(100)),('copy_from_own',rng.choice(body[ownkey]))]:
                own=counts[ownkey][query]/r['own_n']; group=defaultdict(list); dd=[]
                for d in r['donors']:
                    m=counts[(d['folio'],r['length'])][query]
                    group[d['leaf']].append(m/d['n'])
                    if seed==2026111800:dd.append(dict(**d,sim_m=m))
                control=mean([mean(v) for v in group.values()])
                rr={k:r[k] for k in ['folio','leaf','H','I','locator']}
                rr.update(own=own,control=control,delta=own-control,own_m=counts[ownkey][query])
                scored[mode].append(rr)
                if seed==2026111800:first.append(dict(**rr,mode=mode,query=query,n=r['own_n'],donors=dd))
        output.append(dict(seed=seed,**{mode:{k:summarize(rr)[k] for k in ['own','control','delta','labels','pages','leaves']} for mode,rr in scored.items()}))
    return dict(vocabulary_size=100,seeds=output,first_seed_rows=first,
                mean_delta={mode:mean([r[mode]['delta'] for r in output]) for mode in scored},
                caution='Synthetic copy mechanism diagnostic only; neither manuscript p-values nor semantic power estimates.')

def main(out):
    out.mkdir(parents=True,exist_ok=False)
    dependencies=[HERE/'protocol.txt',Path(__file__),RESEARCH/'build_corpus.py',RESEARCH/'study20/analyze.py',RESEARCH/'sources/ZL3b-n.txt',RESEARCH/'sources/IT2a-n.txt']
    write(out/'freeze.json',dict(frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
         files=[dict(path=str(p.relative_to(RESEARCH.parent)),sha256=sha(p)) for p in dependencies],
         scope='Protocol and code hashed before this run computes label/body hits. Historical corpus is exposed.'))
    packets={v:packet(n) for v,n in [('ZL','ZL3b-n.txt'),('IT','IT2a-n.txt')]}
    write(out/'input.json.gz',packets)
    results={};trials={};calibration={}
    for version,data in packets.items():
        trials[version]={}; rr={}
        for model in MODELS:
            s=score(data,model);trials[version][model]=s.pop('rows');rr[model]=s
        mainrows=trials[version]['exact']
        sensitivity={}
        for variant in ['HIQ','min5','certain_loci','dedup_labels']:
            s=score(data,variant=variant);trials[version]['sensitivity_'+variant]=s.pop('rows');sensitivity[variant]=s
        leave=[]
        for l in sorted({r['leaf'] for r in mainrows}):
            s=score(data,drop=l);s.pop('rows');leave.append(s)
        results[version]=dict(inventory=data['inventory'],main=rr,sensitivity=sensitivity,leave_one_leaf_out=leave,
                             by_hand=subgroup(mainrows,'H'),by_illustration=subgroup(mainrows,'I'),by_type=subgroup(mainrows,'type'))
        calibration[version]=calibrate(data,mainrows)
        print(version, json.dumps({m:rr[m]['summary']['delta'] for m in MODELS}),flush=True)
    maps={v:{r['locator']:r for r in trials[v]['exact']} for v in packets}
    common=[]
    for loc in sorted(set(maps['ZL']) & set(maps['IT']),key=lambda s:[int(t) if t.isdigit() else t for t in re.split('(\d+)',s)]):
        a,b=maps['ZL'][loc],maps['IT'][loc]
        if a['word']!=b['word']:continue
        common.append(dict(locator=loc,word=a['word'],ZL=a,IT=b))
    candidates=dict(shared_identical_eligible_labels=len(common),
        both_hit=[r for r in common if r['ZL']['own_m'] and r['IT']['own_m']],
        both_no_hit=[r for r in common if not r['ZL']['own_m'] and not r['IT']['own_m']],
        note='Output-dependent reading queue, not independently verified image objects or names.')
    write(out/'results.json',results);write(out/'trials.json.gz',trials)
    write(out/'calibration.json.gz',calibration);write(out/'candidates.json',candidates)
    write(out/'complete.json',dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
         files=[dict(path=p.name,sha256=sha(p),bytes=p.stat().st_size) for p in sorted(out.iterdir()) if p.is_file()]))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    main(ap.parse_args().output)
