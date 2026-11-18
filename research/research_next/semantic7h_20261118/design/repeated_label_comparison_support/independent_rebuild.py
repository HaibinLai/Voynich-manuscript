#!/usr/bin/env python3
"""Independent metadata reconstruction. Does not read primary output or code."""
import collections, datetime, hashlib, itertools, json, math
from pathlib import Path
HERE=Path(__file__).resolve().parent
SOURCE=HERE.parent/'repeated_label_feasibility/fixed_nine_roster_v1.json'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def multiset_sequences(words):
    counts=collections.Counter(words)
    def walk(prefix):
        if len(prefix)==len(words):
            yield tuple(prefix); return
        for w in sorted(counts):
            if counts[w]:
                counts[w]-=1
                yield from walk(prefix+[w])
                counts[w]+=1
    return list(walk([]))
def rebuild():
    raw=json.loads(SOURCE.read_text())['records']
    nodes=sorted([dict(locator=r['locator'],folio=r['folio'],leaf=r['physical_leaf'],label=r['cluster_word']) for r in raw],key=lambda r:r['locator'])
    assert len({r['locator'] for r in nodes})==len(nodes)
    byleaf={leaf:[r for r in nodes if r['leaf']==leaf] for leaf in sorted({r['leaf'] for r in nodes})}
    original={r['locator']:r['label'] for r in nodes}
    pairs=[]
    for i,a in enumerate(nodes):
        for b in nodes[i+1:]:
            pairs.append(dict(locators=[a['locator'],b['locator']],leaves=sorted([a['leaf'],b['leaf']]),cross_leaf=a['leaf']!=b['leaf'],same_label=a['label']==b['label']))
    def strata(labels):
        out={}
        for e in pairs:
            key='|'.join(e['leaves'])
            d=out.setdefault(key,dict(leaves=e['leaves'],same=0,different=0,total=0,cross_leaf=e['cross_leaf']))
            d['same' if labels[e['locators'][0]]==labels[e['locators'][1]] else 'different']+=1;d['total']+=1
        return out
    perm={leaf:multiset_sequences([r['label'] for r in ns]) for leaf,ns in byleaf.items()}
    formula={leaf:math.factorial(len(ns))//math.prod(math.factorial(n) for n in collections.Counter(r['label'] for r in ns).values()) for leaf,ns in byleaf.items()}
    assert {k:len(v) for k,v in perm.items()}==formula
    assignments=[]
    for choice in itertools.product(*(perm[k] for k in byleaf)):
        labels={r['locator']:w for ns,ws in zip(byleaf.values(),choice) for r,w in zip(ns,ws)}
        flags=[labels[e['locators'][0]]==labels[e['locators'][1]] for e in pairs]
        assignments.append(dict(label_vector=[labels[r['locator']] for r in nodes],labels=labels,same_label_flags=flags,strata=strata(labels)))
    assert len(assignments)==math.prod(formula.values())
    assert len({tuple(a['label_vector']) for a in assignments})==len(assignments)
    for a in assignments:
        for leaf,ns in byleaf.items():assert collections.Counter(a['labels'][r['locator']] for r in ns)==collections.Counter(r['label'] for r in ns)
        assert a['strata']==strata(original)
    degrees={r['locator']:sum(e['cross_leaf'] and r['locator'] in e['locators'] for e in pairs) for r in nodes}
    shared=[dict(edges=[i,j],locators=sorted(set(a['locators'])&set(b['locators']))) for i,a in enumerate(pairs) for j,b in enumerate(pairs) if i<j and set(a['locators'])&set(b['locators'])]
    assert len(pairs)==math.comb(len(nodes),2)
    assert sum(not e['cross_leaf'] for e in pairs)==sum(math.comb(len(ns),2) for ns in byleaf.values())
    return dict(nodes=nodes,edges=pairs,strata=strata(original),leaf_multiset_permutation_counts=formula,assignments=assignments,cross_leaf_degrees=degrees,shared_endpoint_pairs=shared,summary=dict(objects=len(nodes),all_pairs=len(pairs),within_leaf=sum(not e['cross_leaf'] for e in pairs),cross_leaf=sum(e['cross_leaf'] for e in pairs),assignments=len(assignments),same_label_cross=sum(e['cross_leaf'] and e['same_label'] for e in pairs),different_label_cross=sum(e['cross_leaf'] and not e['same_label'] for e in pairs)))
if __name__=='__main__':
    out=HERE/'independent_rebuilt_v1.json'
    if out.exists():raise SystemExit('Refusing overwrite')
    data=rebuild();out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    freeze=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='INDEPENDENT_REBUILD_SAVED_BEFORE_PRIMARY_RESULT_READ',scope='Protocol and fixed_nine_roster only. Counts already exposed; not blind. No image scoring/probability.',files={str(p.relative_to(HERE.parent)):sha(p) for p in [SOURCE,HERE/'protocol_v1.txt',Path(__file__),out]})
    (HERE/'independent_core_freeze_v1.json').write_text(json.dumps(freeze,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(data['summary']))
