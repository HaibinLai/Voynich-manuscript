"""Frozen, local, open-vocabulary prediction models. No semantic mapping."""
from collections import Counter,defaultdict
from functools import lru_cache
import json,math,time,datetime
import numpy as np
from corpus import ROOT,load,save,units,sha

EOS='<EOS>';UNK='<UNK>';BOS='<BOS>'

def records(pages,representation,alphabet=None):
    result=[]
    for p in pages:
        for li,line in enumerate(p['lines']):
            for j,t in enumerate(line['tokens']):
                u=units(t,representation) if t else None
                unknown=0
                if u and alphabet is not None:
                    unknown=sum(c not in alphabet for c in u);u=tuple(c if c in alphabet else UNK for c in u)
                pos='paragraph_first' if j==0 and line['paragraph_start'] else ('line_first' if j==0 else 'other')
                result.append(dict(folio=p['folio'],leaf=p['leaf'],line=li,slot=j,word=u,
                                   raw=t,unknown=unknown,position=pos,hand=p['metadata'].get('H','?')))
    return result

class CharLM:
    def __init__(self,words,alphabet,order,alpha):
        self.order=order;self.alpha=alpha;self.vocab=set(alphabet)|{EOS,UNK}
        self.counts=defaultdict(Counter);self.totals=Counter()
        for word in words:
            history=(BOS,)*(order-1)
            for c in word+(EOS,):
                for n in range(order):
                    h=history[-n:] if n else ()
                    self.counts[h][c]+=1;self.totals[h]+=1
                history=(history+(c,))[-(order-1):] if order>1 else ()

    @lru_cache(maxsize=500000)
    def prob(self,h,c):
        lower=self.prob(h[1:],c) if h else 1/len(self.vocab)
        return (self.counts.get(h,{}).get(c,0)+self.alpha*lower)/(self.totals.get(h,0)+self.alpha)

    @lru_cache(maxsize=50000)
    def logp(self,word):
        h=(BOS,)*(self.order-1);s=0.
        for c in word+(EOS,):
            s+=math.log2(self.prob(h,c))
            h=(h+(c,))[-(self.order-1):] if self.order>1 else ()
        return s

def mixture_log2(loga,logb,weight):
    if weight==0:return loga
    if weight==1:return logb
    return float(np.logaddexp2(math.log2(1-weight)+loga,math.log2(weight)+logb))

def model_score(rr,score):
    bits=events=tokens=unknown=0;pages=defaultdict(lambda:[0.,0,0])
    for r in rr:
        if r['word'] is None:continue
        b=-score(r);n=len(r['word'])+1
        bits+=b;events+=n;tokens+=1;unknown+=r['unknown']
        pages[r['folio']][0]+=b;pages[r['folio']][1]+=n;pages[r['folio']][2]+=1
    return dict(bits_per_token=bits/tokens,bits_per_event=bits/events,tokens=tokens,events=events,
                unknown_units=unknown,page_mean_bits_per_token=float(np.mean([v[0]/v[2] for v in pages.values()])),
                per_page={k:dict(bits=v[0],events=v[1],tokens=v[2],bits_per_token=v[0]/v[2]) for k,v in pages.items()})

def cache_scores(rr,base,window,weight,mode='forward'):
    groups=defaultdict(list)
    for r in rr:groups[(r['folio'],r['line'])].append(r)
    output={};rng=np.random.default_rng(2026111707)
    for rows in groups.values():
        context_rows=list(rows)
        if mode=='reverse':context_rows=context_rows[::-1]
        elif mode=='shuffled':
            valid=[i for i,r in enumerate(context_rows) if r['word'] is not None]
            perm=rng.permutation(valid)
            # Evaluate the same multiset of target words, reordering intact row
            # objects; page totals comparable, positions not used in this model.
            for i,j in zip(valid,perm):context_rows[i]=rows[j]
        history=[]
        for r in context_rows:
            w=r['word'];key=(r['folio'],r['line'],r['slot'])
            if w is None:history=[];continue
            lp=base(w)
            if history and weight:
                cache=history[-window:];n=cache.count(w)
                if n:lp=mixture_log2(lp,math.log2(n/len(cache)),weight)
                else:lp+=math.log2(1-weight)
            output[key]=lp;history.append(w)
    return model_score(rr,lambda r:output[(r['folio'],r['line'],r['slot'])])

def delta_bootstrap(a,b,rr,seed=2026111708):
    leafmap={r['folio']:r['leaf'] for r in rr};group=defaultdict(list)
    for f in a['per_page']:
        group[leafmap[f]].append(a['per_page'][f]['bits_per_token']-b['per_page'][f]['bits_per_token'])
    vals=np.array([np.mean(v) for v in group.values()]);rng=np.random.default_rng(seed)
    boot=rng.choice(vals,(1999,len(vals)),replace=True).mean(axis=1)
    return dict(mean_leaf_bits_saved=float(vals.mean()),bootstrap95=np.quantile(boot,[.025,.975]).tolist(),
                leaves=len(vals),replicates=1999,per_leaf={k:float(np.mean(v)) for k,v in group.items()})

def verify():
    words=[tuple('aba'),tuple('aa'),tuple('bbb')];alphabet={'a','b'}
    for n in [1,2,3,4]:
        lm=CharLM(words,alphabet,n,5)
        for h in [(),(BOS,),('a',),('a','b'),('x','x','x')]:
            assert abs(sum(lm.prob(h,c) for c in lm.vocab)-1)<1e-12
        assert lm.logp(tuple('aba'))<0
    rr=[dict(folio='f1r',leaf='f1',line=0,slot=i,word=w,raw=None,unknown=0,position='other',hand='1')
        for i,w in enumerate([('a',),('a',),None,('a',),('b',)])]
    base=lambda w:math.log2(.5)
    v=cache_scores(rr,base,4,.4)
    # probabilities: .5, .7, reset, .5, .3
    expected=-sum(math.log2(x) for x in [.5,.7,.5,.3])/4
    assert abs(v['bits_per_token']-expected)<1e-12
    return dict(conditional_distributions_normalize=True,cache_no_future=True,missing_slot_resets=True)

def run(source='ZL3b-n.txt',representation='eva',name='predictive_confirm'):
    start=time.time();trainp=load(source,splits=['train','legacy']);devp=load(source,splits=['dev'])
    rawtrain=records(trainp,representation);alphabet={c for r in rawtrain if r['word'] for c in r['word']}
    train=records(trainp,representation,alphabet);dev=records(devp,representation,alphabet)
    words=[r['word'] for r in train if r['word']];scores={};models={};tuning={}
    for order in [1,2,3,4]:
        candidates=[]
        for alpha in [1,5,20,100]:
            lm=CharLM(words,alphabet,order,alpha)
            s=model_score(dev,lambda r:lm.logp(r['word']))
            candidates.append((s['bits_per_event'],alpha,lm))
            tuning[f'char_order{order}_alpha{alpha}']=s['bits_per_event']
        _,alpha,lm=min(candidates,key=lambda x:(x[0],x[1]))
        models[order]=lm;scores[order]=min(candidates,key=lambda x:(x[0],x[1]))[0]
    order=min(scores,key=lambda x:(scores[x],x));global_lm=models[order]
    conditioned={};selected_weights={};weight_tuning={}
    for feature in ['position','hand']:
        conditioned[feature]={}
        for group in sorted({r[feature] for r in train}):
            ww=[r['word'] for r in train if r[feature]==group and r['word']]
            conditioned[feature][group]=CharLM(ww,alphabet,order,global_lm.alpha)
        candidates=[]
        for weight in [0,.25,.5,.75,1]:
            def lp(r):
                child=conditioned[feature].get(r[feature],global_lm)
                return mixture_log2(global_lm.logp(r['word']),child.logp(r['word']),weight)
            s=model_score(dev,lp)['bits_per_event'];candidates.append((s,weight))
        selected_weights[feature]=min(candidates)[1];weight_tuning[feature]=candidates
    counts=Counter(words);N=len(words)
    def wordmodel(beta):
        def f(w):
            char=global_lm.logp(w);n=counts[w]
            return float(np.logaddexp2(math.log2(n) if n else -np.inf,math.log2(beta)+char)-math.log2(N+beta))
        return f
    beta_scores=[(model_score(dev,lambda r:wordmodel(b)(r['word']))['bits_per_token'],b) for b in [10,100,1000,10000]]
    beta=min(beta_scores)[1];base=wordmodel(beta);cache_tuning=[]
    for window in [1,4,8,16]:
        for weight in [0,.05,.1,.2,.4]:
            s=cache_scores(dev,base,window,weight)
            cache_tuning.append((s['bits_per_token'],window,weight))
    _,window,cache_weight=min(cache_tuning,key=lambda x:(x[0],x[2],x[1]))
    selected=dict(char_order=order,char_alpha=global_lm.alpha,order_alphas={str(k):m.alpha for k,m in models.items()},
                  conditioned_weights=selected_weights,word_beta=beta,cache_window=window,cache_weight=cache_weight)
    # Persist the entire selected configuration before opening confirm pages.
    save('results/'+name+'_frozen_config.json',dict(selected=selected,source=source,representation=representation,
         frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),char_tuning=tuning,
         conditioned_tuning=weight_tuning,word_tuning=beta_scores,cache_tuning=cache_tuning,
         split_sha256=sha(ROOT/'split_manifest.json'),protocol_sha256=sha(ROOT/'predictive_protocol.txt')))
    testp=load(source,splits=['confirm']);test=records(testp,representation,alphabet)
    results={f'char_order{k}':model_score(test,lambda r,m=m:m.logp(r['word'])) for k,m in models.items()}
    results['char_selected']=results[f'char_order{order}']
    for feature in ['position','hand']:
        weight=selected_weights[feature]
        results['char_'+feature]=model_score(test,lambda r:mixture_log2(global_lm.logp(r['word']),
            conditioned[feature].get(r[feature],global_lm).logp(r['word']),weight))
    results['word_unigram']=model_score(test,lambda r:base(r['word']))
    for mode in ['forward','reverse','shuffled']:
        results['word_cache_'+mode]=cache_scores(test,base,window,cache_weight,mode)
    comparisons={}
    for a,b in [('char_order1','char_selected'),('char_selected','char_position'),('char_selected','char_hand'),
                ('char_selected','word_unigram'),('word_unigram','word_cache_forward'),
                ('word_cache_shuffled','word_cache_forward'),('word_cache_reverse','word_cache_forward')]:
        comparisons[a+'__minus__'+b]=delta_bootstrap(results[a],results[b],test)
    out=dict(source=source,representation=representation,selected=selected,
             train_pages=len(trainp),dev_pages=len(devp),test_pages=len(testp),train_tokens=N,
             dev_tokens=sum(r['word'] is not None for r in dev),
             results=results,comparisons=comparisons,elapsed_seconds=time.time()-start,
             interpretation='Predictive compression only; no plaintext, language identification, or causal mechanism recovered.')
    save('results/'+name+'.json',out)
    print(json.dumps(dict(name=name,selected=selected,scores={k:v['bits_per_token'] for k,v in results.items()},
                         comparisons=comparisons,elapsed_seconds=out['elapsed_seconds']),indent=2),flush=True)
    return out

if __name__=='__main__':
    (ROOT/'results').mkdir(exist_ok=True);save('results/predictive_verification.json',verify())
    run();run('IT2a-n.txt','eva','predictive_confirm_IT');run('ZL3b-n.txt','merged','predictive_confirm_merged')
