import json,math
from collections import defaultdict
import numpy as np
from corpus import ROOT,load,save,units,sha
from boundary import Conditional,leaf_weights,permutation_buckets
from boundary_word import pair_records
from predictive import CharLM,BOS,EOS
from validate_boundary import direct_prob


def main():
    results={}
    for name in ['boundary_word_confirm','boundary_word_confirm_merged','boundary_word_confirm_IT','boundary_word_confirm_join']:
        cfg=json.loads((ROOT/'results'/f'{name}_frozen_config.json').read_text())
        out=json.loads((ROOT/'results'/f'{name}.json').read_text())
        alphabet=set(cfg['alphabet']);rep=cfg['representation'];source=cfg['source'];spaces=cfg['spaces']
        trainp=load(source,spaces=spaces,splits=['train','legacy'])
        words=[units(t,rep) for p in trainp for line in p['lines'] for t in line['tokens'] if t]
        lm=CharLM(words,alphabet,4,100)
        train=pair_records(trainp,rep,alphabet)
        rows=pair_records(load(source,spaces=spaces,splits=['confirm']),rep,alphabet)
        assert all(r['length']==0 for r in train+rows)
        base=Conditional(train,alphabet,cfg['selected']['base_alpha'])
        models={f:(Conditional(train,alphabet,v['alpha'],f),v['weight']) for f,v in cfg['selected']['features'].items()}
        cached=np.load(ROOT/'results'/f'{name}_scores.npz')
        replay={f:[] for f in ['base']+list(models)}
        for row in rows:
            word=row['word'];h=(BOS,)*(lm.order-1)
            h=(h+(word[0],))[-(lm.order-1):];tail=0.
            for c in word[1:]+(EOS,):
                tail+=math.log2(lm.prob(h,c));h=(h+(c,))[-(lm.order-1):]
            b=base.prob(row);replay['base'].append(math.log2(b)+tail)
            for f,(model,w) in models.items():replay[f].append(math.log2((1-w)*b+w*model.prob(row))+tail)
        errors={f:float(np.max(np.abs(cached[f]-replay[f]))) for f in replay}
        assert all(e<1e-12 for e in errors.values())
        formula_error=0.
        for row in rows[::max(1,len(rows)//4)]:
            formula_error=max(formula_error,abs(base.prob(row)-direct_prob(train,row,alphabet,base.alpha)))
            for f,(m,w) in models.items():formula_error=max(formula_error,abs(m.prob(row)-direct_prob(train,row,alphabet,m.alpha,f)))
        assert formula_error<1e-13
        entry=dict(all_target_length_inputs_zero=True,direct_complete_word_scores_max_abs_error=errors,
                   scanned_training_probability_max_abs_error=formula_error,
                   frozen_config_hash_verified=sha(ROOT/'results'/f'{name}_frozen_config.json')==out['config_sha256'])
        assert entry['frozen_config_hash_verified']
        if name=='boundary_word_confirm':
            weights=leaf_weights(rows);bp=np.array([base.prob(r) for r in rows]);matrices={};ids={}
            for f,(m,w) in models.items():
                values=sorted({r[f] for r in rows});index={v:i for i,v in enumerate(values)}
                ids[f]=np.array([index[r[f]] for r in rows])
                matrices[f]=np.array([[math.log2((1-w)+w*m.prob(r,v)/bp[i]) for v in values] for i,r in enumerate(rows)])
            null=np.load(ROOT/out['primary']['null_array']);calc={f:[] for f in models}
            rng=np.random.default_rng(2026111721);buckets=permutation_buckets(rows)
            for b in range(1999):
                perm=np.arange(len(rows))
                for bucket in buckets:
                    if len(bucket)>1:perm[bucket]=rng.permutation(bucket)
                for f in models:calc[f].append(math.fsum(float(a*b) for a,b in zip(weights,matrices[f][np.arange(len(rows)),ids[f][perm]])))
            errors={f:float(np.max(np.abs(null[f]-calc[f]))) for f in models}
            assert all(e<1e-13 for e in errors.values());entry['all_1999_primary_null_replay_error']=errors
        results[name]=entry
    save('results/boundary_word_independent_verification.json',dict(all_pass=True,variants=results,reserve_scored=False))
    print(json.dumps(results,indent=2))


if __name__=='__main__':main()
