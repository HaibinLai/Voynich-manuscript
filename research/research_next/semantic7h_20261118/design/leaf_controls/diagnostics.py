"""Reproduce metadata diagnostics, without comparing any word strings."""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,datetime,gzip,hashlib,json,re

HERE=Path(__file__).resolve().parent

def main(output):
    assert not output.exists()
    run=HERE/'run_v2'
    sel=json.loads((run/'selection.json').read_text())
    data=json.loads(gzip.decompress((run/'input.json.gz').read_bytes()))
    report={}
    for v,modes in sel['versions'].items():
        leaves=defaultdict(list)
        for p in data[v]['pages']:leaves[p['leaf']].append(p)
        report[v]={}
        for mode,groups in modes.items():
            entries=[]
            for g in groups:
                rows=[]
                for leaf in g['leaves']:
                    pp=leaves[leaf]
                    counts=Counter(r['type'] for p in pp for r in p['labels'] if len(r['units']) in g['lengths'])
                    rows.append(dict(leaf=leaf,Q=sorted({p['Q'] for p in pp}),label_types=dict(counts),retained_labels=sum(counts.values())))
                pairs=[]
                for a in rows:
                    for b in rows:
                        if a['leaf']==b['leaf']:continue
                        d=abs(int(re.findall(r'\d+',a['leaf'])[0])-int(re.findall(r'\d+',b['leaf'])[0]))
                        keys=set(a['label_types'])|set(b['label_types'])
                        tv=sum(abs(a['label_types'].get(k,0)/a['retained_labels']-b['label_types'].get(k,0)/b['retained_labels']) for k in keys)/2
                        pairs.append(dict(source=a['leaf'],target=b['leaf'],same_Q=a['Q']==b['Q'],folio_number_distance=d,label_type_total_variation=tv))
                entries.append(dict(**g,leaf_metadata=rows,ordered_off_diagonal_pairs=pairs))
            report[v][mode]=entries
    result=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        selection_sha256=hashlib.sha256((run/'selection.json').read_bytes()).hexdigest(),versions=report,
        scope='Metadata/label-type/folio-number diagnostics only. Does not compare word strings or test exchangeability. Folio-number distance is an ordinal proxy, not measured physical adjacency.',
        limitations=['HI may contain different quires; HIQ restricts that mixing but still cannot randomize historical leaves.',
                    'Label subtype mixtures differ across leaves even on shared lengths.',
                    'Adjacent or same-quire leaves can share topics, scribal production or copying.',
                    'No empirical guarantee of exchangeability; conditional tails are not semantic probabilities.'])
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
