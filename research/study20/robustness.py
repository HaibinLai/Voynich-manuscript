"""Post-primary descriptive checks. No additional confirmatory claims."""
from pathlib import Path
from collections import Counter
import json, sys
import numpy as np
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from analyze import build_pages, plain_words, external_pages, units, entropy_summary, edit_le_one, prepare, metrics, SEED

def direct_summary(pages):
    word_units=[units(t) for p in pages for l in p['lines'] for t in l['tokens'] if t]
    rates=[]
    for p in pages:
        matches=[]
        for l in p['lines']:
            for a,b in zip(l['tokens'],l['tokens'][1:]):
                if a and b:matches.append(edit_le_one(units(a),units(b)))
        rates.append(float(np.mean(matches)))
    return dict(entropy_ratio=entropy_summary(word_units)['ratio'],near_rate=float(np.mean(rates)))

def main():
    pages=build_pages();val=[p for p in pages if p['split']=='validation']
    report={'status':'Post-primary descriptive robustness; no new confirmatory p-values','reference_windows':{}}
    for language,filename in [('English','english_alice.txt'),('Latin','latin_caesar.xml')]:
        words=plain_words(filename);values=[]
        for i in range(100):
            ep,selection=external_pages(val,words,SEED+i)
            values.append({**direct_summary(ep),**selection})
        report['reference_windows'][language]={'n_windows':100,'windows_may_overlap':True,
            'word_units':'26-letter Latin-script tokens; no claim of matched Voynich glyph alphabet',
            'quantiles':{k:np.quantile([v[k] for v in values],[.025,.5,.975]).tolist() for k in ['entropy_ratio','near_rate']},
            'values':values}
    for split in ['discovery','validation']:
        subset=[p for p in pages if p['split']==split]
        vocab,uu,near,lengths,gallows,arr=prepare(subset,'eva');obs,detail=metrics(arr,near,lengths,gallows)
        effects=[]
        for p,d in zip(arr,detail):
            counts=Counter(i for l in p['lines'] for i in l['ids'] if i>=0)
            ns=np.array([counts[i] for i in range(len(vocab))]);N=int(ns.sum())
            pair_total=int(np.sum(near*np.multiply.outer(ns,ns),dtype=np.int64))
            expected=(pair_total-N)/(N*(N-1))
            effects.append({'folio':p['folio'],'observed_near':d['near_rate'],'expected_page_shuffle_near':expected,
                            'effect':d['near_rate']-expected})
        loo=[float(np.mean([x['effect'] for j,x in enumerate(effects) if j!=i])) for i in range(len(effects))]
        report['H2_'+split]={'per_page':effects,'leave_one_page_out_effects':loo,
            'leave_one_page_out_range':[min(loo),max(loo)],'not_a_confidence_interval':True}
    (ROOT/'results'/'descriptive_robustness.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:({x:y for x,y in v.items() if x!='per_page'} if k.startswith('H2') else v) for k,v in report.items() if k!='reference_windows'},indent=2))
    for lang,v in report['reference_windows'].items():print(lang,v['quantiles'])

if __name__=='__main__':main()
