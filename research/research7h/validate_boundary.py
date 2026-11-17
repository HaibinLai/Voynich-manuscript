"""Independent probability formula and full-array replay of boundary findings."""
import json, math
from collections import Counter,defaultdict
import numpy as np
from corpus import ROOT,load,units,save,sha
from boundary import records,contexts,Conditional,leaf_weights,permutation_buckets


def direct_prob(train,row,alphabet,alpha,feature=None,value=None):
    # Deliberately scans training rows instead of using model's count cache.
    levels=contexts(row,feature,value)
    prob=1/(len(alphabet)+1)
    for depth,key in enumerate(levels):
        matched=[x for x in train if contexts(x,feature)[depth]==key]
        if matched:
            hits=sum(x['target']==row['target'] for x in matched)
            prob=(hits+alpha*prob)/(len(matched)+alpha)
    return prob


def main():
    results={}
    for name in ['boundary_confirm','boundary_confirm_merged','boundary_confirm_IT']:
        cfg=json.loads((ROOT/'results'/f'{name}_frozen_config.json').read_text())
        stored=json.loads((ROOT/'results'/f'{name}.json').read_text())
        alphabet=set(cfg['alphabet']);rep=cfg['representation'];source=cfg['source']
        train=records(load(source,splits=['train','legacy']),rep,alphabet)
        test=records(load(source,splits=['confirm']),rep,alphabet)
        base=Conditional(train,alphabet,cfg['selected']['base_alpha'])
        models={f:(Conditional(train,alphabet,v['alpha'],f),v['weight']) for f,v in cfg['selected']['features'].items()}
        max_diff=0.
        for row in test[::max(1,len(test)//11)]:
            expected=direct_prob(train,row,alphabet,base.alpha)
            max_diff=max(max_diff,abs(expected-base.prob(row)))
            for f,(model,w) in models.items():
                expected=direct_prob(train,row,alphabet,model.alpha,f)
                max_diff=max(max_diff,abs(expected-model.prob(row)))
        assert max_diff<1e-13
        # Recompute using the frozen model, separately reproducing all random assignments.
        bp=np.array([base.prob(r) for r in test]);weights=leaf_weights(test)
        per_feature={};identifiers={};observed={}
        for f,(model,w) in models.items():
            possible=sorted({r[f] for r in test});lookup={v:i for i,v in enumerate(possible)}
            identifiers[f]=np.array([lookup[r[f]] for r in test])
            per_feature[f]=np.array([[math.log2((1-w)+w*model.prob(r,v)/bp[i]) for v in possible] for i,r in enumerate(test)])
            observed[f]=math.fsum(float(w*x) for w,x in zip(weights,per_feature[f][np.arange(len(test)),identifiers[f]]))
            assert abs(observed[f]-stored['primary']['tests'][f]['observed_leaf_bits_saved'])<1e-13
        saved=np.load(ROOT/stored['primary']['null_array']);rng=np.random.default_rng(2026111721)
        buckets=permutation_buckets(test)
        replay={f:[] for f in models}
        for b in range(1999):
            perm=np.arange(len(test))
            for bucket in buckets:
                if len(bucket)>1:perm[bucket]=rng.permutation(bucket)
            for f in models:
                replay[f].append(math.fsum(float(w*x) for w,x in zip(weights,per_feature[f][np.arange(len(test)),identifiers[f][perm]])))
        error={f:float(np.max(np.abs(saved[f]-replay[f]))) for f in models}
        assert all(v<1e-13 for v in error.values())
        results[name]=dict(independent_direct_probability_max_abs_error=max_diff,
                           all_1999_null_replay_max_abs_error=error,
                           config_hash_verified=sha(ROOT/'results'/f'{name}_frozen_config.json')==stored['config_sha256'])
        assert results[name]['config_hash_verified']
    receipt=json.loads((ROOT/'boundary_receipt.json').read_text())
    assert receipt['protocol_sha256']==sha(ROOT/'boundary_protocol.txt')
    assert receipt['split_sha256']==sha(ROOT/'split_manifest.json')
    save('results/boundary_independent_verification.json',dict(all_pass=True,variants=results,
         protocol_unchanged=True,split_unchanged=True,reserve_scored=False))
    print(json.dumps(results,indent=2))


if __name__=='__main__':main()
