"""Cross-line model functions without data-loading side effects."""
from collections import Counter,defaultdict
import hashlib,math
import numpy as np
from reference_conditional import Conditional,contexts
from reference_charlm import CharLM,BOS,EOS,UNK
from data import all_words,mapped,universe

ALPHAS=(1,5,20,100,500);WEIGHTS=(0,.25,.5,.75,1)


def folds_for(rows):
    leaves=sorted({r['leaf'] for r in rows},key=lambda leaf:hashlib.sha256(('line-calibration-fold-v1|'+leaf).encode()).digest())
    return {leaf:i%3 for i,leaf in enumerate(leaves)}


def first_identity_cost(row,alphabet,omega):
    return math.log2(len(omega-set(alphabet))) if row['word'][0] not in alphabet else 0.


def select(pages,raw_rows,representation):
    fold=folds_for(raw_rows);n=len(raw_rows);omega=universe(representation)
    bp={a:np.empty(n) for a in ALPHAS};cp={a:np.empty(n) for a in ALPHAS};escape=np.empty(n);audits=[]
    for k in range(3):
        fit_pages=[p for p in pages if p['leaf'] in fold and fold[p['leaf']]!=k]
        alpha_set={c for w in all_words(fit_pages,representation) for c in w}
        assert alpha_set<omega
        fit=mapped([r for r in raw_rows if fold[r['leaf']]!=k],alpha_set)
        ids=[i for i,r in enumerate(raw_rows) if fold[r['leaf']]==k]
        held=mapped([raw_rows[i] for i in ids],alpha_set)
        assert fit and held
        assert {r['leaf'] for r in fit}.isdisjoint(r['leaf'] for r in held)
        escape[ids]=[first_identity_cost(raw_rows[i],alpha_set,omega) for i in ids]
        for a in ALPHAS:
            base=Conditional(fit,alpha_set,a);child=Conditional(fit,alpha_set,a,'last')
            bp[a][ids]=[base.prob(r) for r in held];cp[a][ids]=[child.prob(r) for r in held]
            # Clear the exact reference's shared method cache between discarded fits.
            Conditional.distribution.cache_clear()
        audits.append(dict(fold=k,fit_rows=len(fit),held_rows=len(held),fit_leaves=sorted({r['leaf'] for r in fit}),
            held_leaves=sorted({r['leaf'] for r in held}),alphabet=sorted(alpha_set),
            held_first_unknown=sum(raw_rows[i]['word'][0] not in alpha_set for i in ids)))
    base_grid=[dict(alpha=a,loss=float((-np.log2(bp[a])+escape).mean())) for a in ALPHAS]
    ba=min(base_grid,key=lambda r:(r['loss'],-r['alpha']))['alpha']
    grid=[dict(alpha=a,weight=w,loss=float((-np.log2((1-w)*bp[ba]+w*cp[a])+escape).mean())) for a in ALPHAS for w in WEIGHTS]
    best=min(grid,key=lambda r:(r['loss'],r['weight'],-r['alpha']))
    return dict(base_alpha=ba,alpha=best['alpha'],weight=best['weight'],base_grid=base_grid,feature_grid=grid,
        folds=audits,leaf_fold=fold,selection='pooled out-of-fold actual first-unit NLL including first-unit escape; shared continuation cancels',
        training_only_alphabet_per_inner_fold=True)


def continuation(lm,word):
    assert word
    h=(BOS,)*(lm.order-1)
    return lm.logp(tuple(word))-math.log2(lm.prob(h,word[0]))


def complete_cost(lm,q,row,alphabet,omega):
    original=row['original_word'];assert original and set(original)<=omega and set(alphabet)<omega
    unknown=sum(c not in alphabet for c in original)
    escape=unknown*math.log2(len(omega-set(alphabet)))
    tail=-continuation(lm,row['word'])
    return -math.log2(q)+tail+escape,tail,escape


def first_costs(q,row,alphabet,omega):
    """Class probability and actual first identity are separate, explicit costs."""
    first=row['original_word'][0]
    extra=math.log2(len(omega-set(alphabet))) if first not in alphabet else 0.
    class_bits=-math.log2(q)
    return class_bits,extra,class_bits+extra


def support(model,rows):
    levels=[Counter() for _ in contexts(rows[0],model.feature)] if rows else []
    deepest=Counter();details=[]
    for r in rows:
        totals=[model.totals.get(k,0) for k in contexts(r,model.feature)]
        for counter,n in zip(levels,totals):counter[str(n)]+=1
        observed=[i for i,n in enumerate(totals) if n]
        depth=max(observed) if observed else -1;deepest[str(depth)]+=1
        details.append(dict(counts=totals,deepest_observed_level=depth,final_level_unseen=totals[-1]==0))
    return dict(exact_training_count_histogram_by_level=[dict(c) for c in levels],deepest_observed_level_counts=dict(deepest),
        meaning='Zero-count levels are skipped; all observed levels are still smoothed. Depth is not proof of sufficient support.',rows=details)


def page_leaf(rows,values):
    pp=defaultdict(list);leafmap={}
    for r,v in zip(rows,values):pp[r['folio']].append(float(v));leafmap[r['folio']]=r['leaf']
    pages={p:math.fsum(v)/len(v) for p,v in pp.items()};ll=defaultdict(list)
    for p,v in pages.items():ll[leafmap[p]].append(v)
    leaves={l:math.fsum(v)/len(v) for l,v in ll.items()}
    vals=list(leaves.values());mean=math.fsum(vals)/len(vals) if vals else None
    loo={l:(math.fsum(vals)-v)/(len(vals)-1) for l,v in leaves.items()} if len(vals)>1 else {}
    return dict(mean_leaf=mean,pooled=math.fsum(values)/len(values) if len(values) else None,per_page=pages,per_leaf=leaves,
        leave_one_leaf_out_range=[min(loo.values()),max(loo.values())] if loo else None,leave_one_leaf_out=loo)
