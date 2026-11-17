"""Summarize saved length-only inventory; no manuscript word strings are read."""
from pathlib import Path
from collections import defaultdict,Counter
import json,hashlib
P=Path(__file__).resolve().parent
read=lambda n:json.loads((P/n).read_text())
def save(n,x):
    text=json.dumps(x,ensure_ascii=False,indent=2)+'\n';assert '/Users/' not in text
    (P/n).write_text(text)

inventory=read('inventory.json');pages=read('page_counts.json');loci=read('locus_lengths.json')
strata=[]
for source in loci:
    grouped=defaultdict(list)
    for p in pages:
        if p['source']==source and p['pairable']:
            grouped[(p['pool'],p['metadata'].get('H','?'),p['metadata'].get('I','?'))].append(p)
    for (pool,H,I),v in grouped.items():
        strata.append(dict(source=source,pool=pool,H=H,I=I,pages=len(v),leaves=len({p['leaf'] for p in v}),
            folios=[p['folio'] for p in v],leaf_ids=sorted({p['leaf'] for p in v}),
            quires=sorted({p['metadata'].get('Q','?') for p in v}),
            labels_retained=sum(p['image_labels']['retained'] for p in v),body_retained=sum(p['body']['retained'] for p in v)))
alternative=[]
for source,rr in loci.items():
    pp={p['folio']:p for p in pages if p['source']==source}
    body=defaultdict(list);labels=[]
    for r in rr:
        if r['kind'][0]=='!':continue
        if r['type'] in inventory['body_types']:body[r['folio']]+=[s for s in r['slots'] if s is not None]
        if r['type'] in inventory['image_types'] and pp[r['folio']]['pairable']:
            labels += [(r['folio'],s) for s in r['slots'] if s is not None]
    for pool in ['train_legacy','dev']:
        for rep in ['eva','merged']:
            hist={f:Counter(s[rep] for s in values) for f,values in body.items()}
            entries=[]
            for folio,lengths in labels:
                target=pp[folio]
                if target['pool']!=pool:continue
                length=lengths[rep];n=hist[folio][length];m=target['metadata']
                donors=[p for p in pp.values() if p['pool']==pool and p['leaf']!=target['leaf'] and
                    p['body']['retained'] and m.get('H') in {'1','2','3','4','5'} and
                    all(p['metadata'].get(k)==m.get(k) for k in ['H','I'])]
                positive=[p for p in donors if hist[p['folio']][length]>0]
                equal=[p for p in positive if hist[p['folio']][length]==n and n>0]
                entries.append(dict(folio=folio,leaf=target['leaf'],unit_length=length,own_length_opportunities=n,
                    any_body_donor_leaves=sorted({p['leaf'] for p in donors}),
                    positive_length_donor_leaves=sorted({p['leaf'] for p in positive}),
                    equal_length_opportunity_donor_leaves=sorted({p['leaf'] for p in equal})))
            conditions={k:dict(slots=sum(bool(e[k]) for e in entries),
                pages=len({e['folio'] for e in entries if e[k]}),leaves=len({e['leaf'] for e in entries if e[k]}))
                for k in ['any_body_donor_leaves','positive_length_donor_leaves','equal_length_opportunity_donor_leaves']}
            alternative.append(dict(source=source,pool=pool,representation=rep,label_slots=len(entries),
                own_length_opportunity_zero_slots=sum(e['own_length_opportunities']==0 for e in entries),
                conditions=conditions))
dual=inventory['dual_version'];both=set(dual['paired_page_intersection'])
save('design_summary.json',dict(scope='Support counts only; no observed exact/near label-body hits',
    strata=strata,dual_version_paired_pages=len(both),
    dual_version_paired_leaves=len({p['leaf'] for p in pages if p['folio'] in both}),
    wrong_body_alternative=alternative,
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
print(json.dumps(alternative,ensure_ascii=False,indent=2))
