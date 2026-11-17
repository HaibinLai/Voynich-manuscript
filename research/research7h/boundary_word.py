"""Normalized complete-word model with no target-length side information."""
import datetime, itertools, json, math, time
import numpy as np
from corpus import ROOT,load,save,sha,units
from boundary import records,tuning,summary,permute,Conditional,UNK
from predictive import CharLM,BOS,EOS


def pair_records(pages,representation,alphabet):
    rows=records(pages,representation,alphabet)
    lookup={p['folio']:p for p in pages}
    for row in rows:
        raw=lookup[row['folio']]['lines'][row['line']]['tokens'][row['slot']]
        row['word']=tuple(c if c in alphabet else UNK for c in units(raw,representation))
        row['length']=0  # Never expose target length to Q or its permutation buckets.
    return rows


def continuation_logp(lm,word):
    initial=(BOS,)*(lm.order-1)
    return lm.logp(word)-math.log2(lm.prob(initial,word[0]))


def verify():
    lm=CharLM([tuple('aba'),tuple('abb'),tuple('aa'),tuple('b')],set('ab'),4,5)
    alphabet=['a','b',UNK];q={'a':.5,'b':.3,UNK:.2}
    total=0.;remaining=0.;max_error=0.
    for length in range(1,7):
        for word in itertools.product(alphabet,repeat=length):
            h=(BOS,)*(lm.order-1)
            h=(h+(word[0],))[-(lm.order-1):]
            product=q[word[0]]
            direct=math.log2(product)
            for c in word[1:]:
                product*=lm.prob(h,c);direct+=math.log2(lm.prob(h,c))
                h=(h+(c,))[-(lm.order-1):]
            complete=product*lm.prob(h,EOS)
            direct+=math.log2(lm.prob(h,EOS))
            factored=math.log2(q[word[0]])+continuation_logp(lm,word)
            max_error=max(max_error,abs(direct-factored));total+=complete
            if length==6:remaining+=product*(1-lm.prob(h,EOS))
    assert abs(total+remaining-1)<1e-12 and max_error<1e-12
    return dict(enumerated_nonempty_words_through_length=6,complete_mass=total,
                longer_word_mass=remaining,total_probability=total+remaining,
                max_direct_factorization_log2_error=max_error,empty_word_excluded=True)


def run(source='ZL3b-n.txt',representation='eva',spaces='split',name='boundary_word_confirm'):
    start=time.time();receipt=json.loads((ROOT/'boundary_word_receipt.json').read_text())
    assert receipt['protocol_sha256']==sha(ROOT/'boundary_word_protocol.txt')
    assert receipt['split_sha256']==sha(ROOT/'split_manifest.json')
    trainp=load(source,spaces=spaces,splits=['train','legacy']);devp=load(source,spaces=spaces,splits=['dev'])
    words=[units(t,representation) for p in trainp for line in p['lines'] for t in line['tokens'] if t]
    alphabet={c for w in words for c in w}
    lm=CharLM(words,alphabet,4,100)
    train=pair_records(trainp,representation,alphabet);dev=pair_records(devp,representation,alphabet)
    assert all(r['length']==0 for r in train+dev)
    base,models,grid=tuning(train,dev,alphabet)
    selected=dict(char_order=4,char_alpha=100,base_alpha=base.alpha,
                  features={k:dict(alpha=m.alpha,weight=w) for k,(m,w) in models.items()})
    cfg=dict(source=source,representation=representation,spaces=spaces,selected=selected,tuning=grid,
             alphabet=sorted(alphabet),train_pairs=len(train),dev_pairs=len(dev),target_length_input=False,
             frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
             protocol_sha256=sha(ROOT/'boundary_word_protocol.txt'),split_sha256=sha(ROOT/'split_manifest.json'))
    path=ROOT/'results'/f'{name}_frozen_config.json'
    if path.exists():
        old=json.loads(path.read_text());assert old['selected']==selected and old['tuning']==grid
    else:save(path.relative_to(ROOT),cfg)
    testp=load(source,spaces=spaces,splits=['confirm']);rows=pair_records(testp,representation,alphabet)
    assert all(r['length']==0 for r in rows)
    tail=np.array([continuation_logp(lm,r['word']) for r in rows])
    bp=np.array([base.prob(r) for r in rows]);blp=np.log2(bp)
    results={'base':summary(rows,blp+tail)};first_only={'base':summary(rows,blp)}
    scores={'base':blp+tail}
    for f,(model,w) in models.items():
        lp=np.log2([(1-w)*bp[i]+w*model.prob(r) for i,r in enumerate(rows)])
        scores[f]=lp+tail;results[f]=summary(rows,lp+tail,blp+tail)
        first_only[f]=summary(rows,lp,blp)
        assert np.allclose((lp+tail)-(blp+tail),lp-blp,atol=1e-13)
    primary=permute(rows,base,models,name)
    scorepath=ROOT/'results'/f'{name}_scores.npz';np.savez_compressed(scorepath,**scores)
    recordpath=ROOT/'results'/f'{name}_pairs.json';save(recordpath.relative_to(ROOT),rows)
    out=dict(source=source,representation=representation,spaces=spaces,selected=selected,
             train_pairs=len(train),dev_pairs=len(dev),confirm_pairs=len(rows),
             train_words=len(words),target_length_input=False,normalized_nonempty_word_model=True,
             mapped_unknown_units=sum(r['unknown'] for r in rows),results=results,first_only=first_only,primary=primary,
             config_sha256=sha(path),scores_sha256=sha(scorepath),pairs_sha256=sha(recordpath),
             elapsed_seconds=time.time()-start,
             interpretation='Layout-conditional probability of complete normalized word forms. UNK collapses unknown units; no plaintext or semantic decoding.')
    save('results/'+name+'.json',out)
    print(json.dumps(dict(name=name,selected=selected,targets=len(rows),
                         bits_per_word={f:v['bits_per_target'] for f,v in results.items()},
                         improvements={f:v['improvement'] for f,v in results.items() if f!='base'},
                         primary=primary['tests']),indent=2),flush=True)


if __name__=='__main__':
    save('results/boundary_word_verification.json',verify())
    run()
    run('ZL3b-n.txt','merged','split','boundary_word_confirm_merged')
    run('IT2a-n.txt','eva','split','boundary_word_confirm_IT')
    run('ZL3b-n.txt','eva','join','boundary_word_confirm_join')
