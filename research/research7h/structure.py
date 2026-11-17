"""Page-weighted positional and repeat tests, preserving physical-line masks."""
from collections import defaultdict,Counter
import json, time
import numpy as np
from corpus import ROOT,load,save,units,edit_le_one,sha

KEYS=['G1_paragraph_first_gallows','G2_other_line_first_gallows',
      'R1_exact_interior_adjacency','R2_distinct_edit1_interior_adjacency']

def neighbor_matrix(words,representation):
    uu=[units(w,representation) for w in words];ids={u:i for i,u in enumerate(uu)}
    matrix=np.eye(len(words),dtype=bool);sub=defaultdict(list)
    for i,u in enumerate(uu):
        for j in range(len(u)):
            shorter=u[:j]+u[j+1:]
            if shorter in ids:matrix[i,ids[shorter]]=matrix[ids[shorter],i]=True
            sub[(len(u),j,u[:j],u[j+1:])].append(i)
    for bucket in sub.values():matrix[np.ix_(bucket,bucket)]=True
    return uu,matrix

def permutations(a,B,rng,lengths=None):
    arr=np.tile(a,(B,1));slots=np.flatnonzero(a>=0)
    if lengths is None:groups=[slots]
    else:groups=[slots[lengths[a[slots]]==n] for n in sorted(set(lengths[a[slots]]))]
    for group in groups:
        if len(group)>1:
            order=np.argsort(rng.random((B,len(group))),axis=1)
            arr[:,group]=a[group][order]
    return arr

def page_run(p,representation,B,seed):
    words=sorted({t for l in p['lines'] for t in l['tokens'] if t})
    ids={t:i for i,t in enumerate(words)};uu,near=neighbor_matrix(words,representation)
    lengths=np.array([len(u) for u in uu]);g=np.array([w[0] in 'ktpf' for w in words],dtype=float)
    rng=np.random.default_rng(seed);obs=np.zeros(4);null=np.zeros((B,4));den=np.zeros(4,dtype=int)
    length_null=np.zeros((B,2));lag={str(k):[0,0,0] for k in range(1,6)}
    line_details=[]
    for line in p['lines']:
        a=np.array([ids.get(t,-1) for t in line['tokens']],dtype=int)
        if len(a)>=2 and a[0]>=0 and (a[1:]>=0).any() and line['paragraph_known']:
            k=0 if line['paragraph_start'] else 1
            valid=a[1:]>=0
            effect=g[a[0]]-g[a[1:][valid]].mean()
            sh=permutations(a,B,rng)
            null[:,k]+=g[sh[:,0]]-g[sh[:,1:][:,valid]].mean(axis=1)
            obs[k]+=effect;den[k]+=1
            line_details.append(dict(loci=line['loci'],paragraph_first=line['paragraph_start'],
                                     first_word=words[a[0]],gallows_effect=float(effect)))
        interior=a[1:-1]
        if len(interior)>=2:
            mask=(interior[:-1]>=0)&(interior[1:]>=0);n=int(mask.sum())
            if n:
                left,right=interior[:-1][mask],interior[1:][mask]
                exact=left==right;similar=near[left,right]&~exact
                obs[2:]+=np.array([exact.sum(),similar.sum()]);den[2:]+=n
                sh=permutations(interior,B,rng)
                for dest,arr in [(null[:,2:],sh),(length_null,permutations(interior,B,rng,lengths))]:
                    x,y=arr[:,:-1][:,mask],arr[:,1:][:,mask];eq=x==y
                    dest[:,0]+=eq.sum(axis=1);dest[:,1]+=(near[x,y]&~eq).sum(axis=1)
        for k in range(1,6):
            if len(a)<=k:continue
            mask=(a[:-k]>=0)&(a[k:]>=0);x,y=a[:-k][mask],a[k:][mask]
            lag[str(k)][0]+=int(mask.sum());lag[str(k)][1]+=int((x==y).sum())
            lag[str(k)][2]+=int((near[x,y]&(x!=y)).sum())
    values=np.divide(obs,den,out=np.full(4,np.nan),where=den>0)
    null=np.divide(null,den[None,:],out=np.full_like(null,np.nan),where=den[None,:]>0)
    length_null=np.divide(length_null,den[None,2:],out=np.full_like(length_null,np.nan),where=den[None,2:]>0)
    details=dict(folio=p['folio'],leaf=p['leaf'],split=p['split'],metadata=p['metadata'],
                 physical_lines=len(p['lines']),tokens=sum(t is not None for l in p['lines'] for t in l['tokens']),
                 denominators=dict(zip(KEYS,den.tolist())),
                 observed={k:float(v) if np.isfinite(v) else None for k,v in zip(KEYS,values)},
                 expected={k:float(np.mean(null[:,i])) if den[i] else None for i,k in enumerate(KEYS)},
                 lag_counts=lag,line_details=line_details)
    return values,null,length_null,details

def test(observed,null):
    center=float(np.mean(null));sd=float(np.std(null))
    return dict(observed=float(observed),null_mean=center,effect=float(observed-center),
                null95=np.quantile(null,[.025,.975]).tolist(),
                p=float((1+np.count_nonzero(np.abs(null-center)>=abs(observed-center)-1e-12))/(1+len(null))),
                replicates=len(null),null_sd=sd,degenerate=sd<1e-12)

def aggregate(outputs):
    observed=np.array([o[0] for o in outputs]);null=np.array([o[1] for o in outputs])
    ln=np.array([o[2] for o in outputs]);tests={}
    for j,k in enumerate(KEYS):
        eligible=np.isfinite(observed[:,j])
        if not eligible.any():tests[k]=None;continue
        tests[k]={**test(observed[eligible,j].mean(),null[eligible,:,j].mean(axis=0)),
                  'pages':int(eligible.sum())}
    order=sorted([k for k in KEYS if tests[k]],key=lambda k:tests[k]['p']);current=0
    for j,k in enumerate(order):
        current=max(current,min(1,tests[k]['p']*(len(order)-j)));tests[k]['holm_p']=current
    supplemental={}
    for j,k in enumerate(KEYS[2:]):
        eligible=np.isfinite(observed[:,j+2])
        if eligible.any():supplemental[k]=test(observed[eligible,j+2].mean(),ln[eligible,:,j].mean(axis=0))
    return dict(tests=tests,length_preserving_interior_null=supplemental)

def verify():
    # Compare graph construction against independent edit-distance code.
    words=['a','b','aa','ab','bb','aba','abb','bab','@177;a','ch','sh','cth','cph','qotchey','qotchdy']
    for repr_ in ['eva','merged']:
        uu,m=neighbor_matrix(words,repr_)
        for i,a in enumerate(uu):
            for j,b in enumerate(uu):assert m[i,j]==edit_le_one(a,b),(a,b)
    rng=np.random.default_rng(3);a=np.array([1,2,-1,3,2]);lengths=np.array([0,1,2,1])
    for lens in [None,lengths]:
        arr=permutations(a,100,rng,lens)
        for row in arr:
            assert Counter(row)==Counter(a)
            assert np.array_equal(row<0,a<0)
            if lens is not None:assert np.array_equal(lens[row[row>=0]],lens[a[a>=0]])
    # Null mean of same-line paired first-minus-others is zero analytically.
    from itertools import permutations as allperm
    a=np.array([0,0,1,1,1])
    e=[x[0]-np.mean(x[1:]) for x in allperm(a)]
    assert abs(np.mean(e))<1e-12
    return dict(neighbor_graph_bruteforce=True,shuffle_bags_and_missing_masks=True,length_invariance=True,
                paired_gallows_analytic_expectation_zero=True)

def run(name,source,repr_,B,seed,splits,spaces='split',alternatives='exclude'):
    pages=load(source,spaces,alternatives,splits);outputs=[];start=time.time()
    for i,p in enumerate(pages):outputs.append(page_run(p,repr_,B,seed+i*101))
    result=dict(name=name,source=source,representation=repr_,replicates=B,seed=seed,
                splits=splits,source_sha256=sha(ROOT.parent/'sources'/source),
                split_sha256=sha(ROOT/'split_manifest.json'),
                pages=len(pages),leaves=len({p['leaf'] for p in pages}),
                tokens=sum(o[3]['tokens'] for o in outputs),**aggregate(outputs),
                per_page=[o[3] for o in outputs],groups={},elapsed_seconds=time.time()-start)
    for field in ['I','H','L']:
        for value in sorted({p['metadata'].get(field,'?') for p in pages}):
            group=[o for p,o in zip(pages,outputs) if p['metadata'].get(field,'?')==value]
            result['groups'][field+'='+value]=dict(pages=len(group),**aggregate(group))
    save('results/'+name+'.json',result)
    np.savez_compressed(ROOT/'results'/f'{name}_nulls.npz',
        observed=np.array([o[0] for o in outputs]),within_line=np.array([o[1] for o in outputs]),
        length_matched=np.array([o[2] for o in outputs]))
    print(json.dumps({k:result[k] for k in ['name','pages','leaves','tokens','tests','length_preserving_interior_null','elapsed_seconds']},indent=2),flush=True)
    return result

if __name__=='__main__':
    (ROOT/'results').mkdir(exist_ok=True);save('results/structure_verification.json',verify())
    specs=[('structure_development','ZL3b-n.txt','eva',399,2026111701,['legacy','train','dev']),
           ('structure_confirm','ZL3b-n.txt','eva',1999,2026111701,['confirm']),
           ('structure_confirm_IT','IT2a-n.txt','eva',399,2026111703,['confirm']),
           ('structure_confirm_merged','ZL3b-n.txt','merged',399,2026111704,['confirm'])]
    for s in specs:run(*s)
    run('structure_confirm_joinspaces','ZL3b-n.txt','eva',399,2026111705,['confirm'],spaces='join')
    run('structure_confirm_firstalternatives','ZL3b-n.txt','eva',399,2026111706,['confirm'],alternatives='first')
