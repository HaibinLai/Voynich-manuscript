"""Exact same estimands as run.py; factorized joint distribution storage."""
from pathlib import Path
from collections import Counter
from fractions import Fraction
from itertools import permutations, product
from bisect import bisect_left, bisect_right
import argparse, datetime, math
import run as original

HERE=Path(__file__).resolve().parent
SEMANTIC=HERE.parents[1]
MODELS=original.MODELS
sha=original.sha
dump=original.dump

def scalar_reference(arrays,denominator):
    """Exact finite Cartesian product using at most product of smaller arrays."""
    assert arrays and all(arrays)
    observed=sum(a[0] for a in arrays)
    ordered=sorted(arrays,key=len)
    last=sorted(ordered[-1])
    prefix=[sum(x) for x in product(*ordered[:-1])] if len(ordered)>1 else [0]
    total=math.prod(len(a) for a in arrays)
    ge=gt=ties=0
    for p in prefix:
        target=observed-p
        lo=bisect_left(last,target);hi=bisect_right(last,target)
        ge+=len(last)-lo;gt+=len(last)-hi;ties+=hi-lo
    mu=sum((Fraction(sum(a),len(a)) for a in arrays),Fraction(0))
    variance=sum((Fraction(sum(x*x for x in a),len(a))-Fraction(sum(a),len(a))**2 for a in arrays),Fraction(0))
    return dict(assignments=total,observed=Fraction(observed,denominator),mean=mu/denominator,
        variance=variance/(denominator*denominator),
        min=Fraction(sum(min(a) for a in arrays),denominator),max=Fraction(sum(max(a) for a in arrays),denominator),
        excess_over_mean=(observed-mu)/denominator,
        tail_ge=ge,tail_gt=gt,ties=ties,p_upper=Fraction(ge,total),
        observed_integer=str(observed),score_denominator=str(denominator),
        distribution_representation='Lossless factorization in complete group integer-score arrays; Cartesian product in group order.')

def max_reference(groups,denominator):
    counters=[]
    for g in groups:
        c=Counter(tuple(g['increments'][m][i] for m in MODELS[1:]) for i in range(len(g['permutations'])))
        counters.append(c)
    counters.sort(key=len)
    prior=Counter({(0,)*6:1})
    for c in counters[:-1]:
        nxt=Counter()
        for a,an in prior.items():
            for b,bn in c.items():nxt[tuple(x+y for x,y in zip(a,b))]+=an*bn
        prior=nxt
    observed=max(sum(g['increments'][m][0] for g in groups) for m in MODELS[1:])
    total=s=ss=ge=gt=ties=0;minimum=maximum=None
    for a,an in prior.items():
        for b,bn in counters[-1].items():
            x=max(i+j for i,j in zip(a,b));n=an*bn
            total+=n;s+=x*n;ss+=x*x*n
            if x>=observed:ge+=n
            if x>observed:gt+=n
            if x==observed:ties+=n
            if minimum is None or x<minimum:minimum=x
            if maximum is None or x>maximum:maximum=x
    mu=Fraction(s,total*denominator)
    return dict(assignments=total,observed=Fraction(observed,denominator),mean=mu,
        variance=Fraction(ss,total*denominator*denominator)-mu*mu,
        min=Fraction(minimum,denominator),max=Fraction(maximum,denominator),
        excess_over_mean=Fraction(observed,denominator)-mu,
        tail_ge=ge,tail_gt=gt,ties=ties,p_upper=Fraction(ge,total),
        observed_integer=str(observed),score_denominator=str(denominator),
        distribution_representation='Lossless factorization in six synchronized increment arrays per group; Cartesian product, then max across six.')

def analyse(bags,selection):
    groups=[original.matrix_group(bags,g) for g in selection]
    if not groups:return dict(status='no_supported_groups'),{}
    n=sum(len(g['leaves']) for g in groups);denominator=1
    for g in groups:
        for rows in g['matrices'].values():
            for row in rows:
                for x in row:denominator=math.lcm(denominator,x.denominator)
    saved=[];numerical=[]
    for g in groups:
        size=len(g['leaves']);assert size<=7
        perms=list(permutations(range(size)));assert perms[0]==tuple(range(size))
        arrays={}
        for model,rows in g['matrices'].items():
            integer=[[int(x*denominator) for x in row] for row in rows]
            arrays[model]=[sum(integer[i][p[i]] for i in range(size)) for p in perms]
        increments={m:[a-b for a,b in zip(arrays[m],arrays['exact'])] for m in MODELS[1:]}
        numerical.append(dict(permutations=perms,scores=arrays,increments=increments))
        saved.append(dict(**g,permutations=perms,permutation_order='lexicographic permutations(range(n)); identity index 0',
            integer_scale=str(denominator),scores={m:[str(x) for x in a] for m,a in arrays.items()},
            increments={m:[str(x) for x in a] for m,a in increments.items()},
            summaries={m:scalar_reference([a],size*denominator) for m,a in arrays.items()},
            increment_summaries={m:scalar_reference([a],size*denominator) for m,a in increments.items()}))
    joint={m:scalar_reference([g['scores'][m] for g in numerical],n*denominator) for m in MODELS}
    incjoint={m:scalar_reference([g['increments'][m] for g in numerical],n*denominator) for m in MODELS[1:]}
    result=dict(status='complete_exact',leaf_count=n,group_count=len(groups),
        labels=sum(len(bags[l]['labels'][L]) for g in selection for l in g['leaves'] for L in g['lengths']),
        body_opportunities=sum(len(bags[l]['body'][L]) for g in selection for l in g['leaves'] for L in g['lengths']),
        assignments=math.prod(len(g['permutations']) for g in numerical),integer_scale=str(denominator),
        models=joint,increments=incjoint,max_increment_global_null=max_reference(numerical,n*denominator))
    return result,dict(groups=saved,joint=result)

def toy_check():
    bags={}
    for leaf,words in [('f1',['k','k']),('f2',['t','k']),('f3',['f','p','f']),('f4',['p','p'])]:
        bags[leaf]=dict(labels={1:[dict(word=w,locator=leaf+'.'+str(j)) for j,w in enumerate(words)]},
                        body={1:[dict(units=[w]) for w in words]})
    selection=[dict(stratum='toy1',leaves=['f1','f2'],lengths=[1]),dict(stratum='toy2',leaves=['f3','f4'],lengths=[1])]
    old,_=original.analyse(bags,selection);new,_=analyse(bags,selection)
    checks=0
    for family in ['models','increments']:
        for model in old[family]:
            for key,value in old[family][model].items():
                assert new[family][model][key]==value,(family,model,key);checks+=1
    for key,value in old['max_increment_global_null'].items():
        assert new['max_increment_global_null'][key]==value,('max',key);checks+=1
    assert original.accepted('kkt','kt')=={('k','k','t'),('t','k','t'),('k','t','t'),('k','k','k')}
    assert original.accepted('@123;k','kt')=={('@123;','k'),('@123;','t')}
    return dict(passed=True,comparisons=checks,scope='Two-stratum, two-leaf-per-stratum rational toy; original expanded versus compact exact tails, moments, extrema and synchronized maximum. Plus one-change and extended-unit checks.')

def main(output):
    checks=toy_check()
    output.mkdir(parents=True,exist_ok=False)
    dependencies=[HERE/'protocol.txt',HERE/'representation_change.txt',Path(__file__),HERE/'run.py',original.INPUT,HERE/'support.py',HERE/'support_v1.json']
    dump(output/'freeze.json',dict(frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        files=[dict(path=str(p.relative_to(SEMANTIC.parent)),sha256=sha(p)) for p in dependencies],
        scope='Same protocol estimands and permutations; lossless factorized joint distribution storage. Before new matrix construction.',toy_checks=checks))
    data=original.read(original.INPUT);bags={};selection={};excluded={}
    for v,dd in data.items():
        bags[v],leafexcluded=original.build_leaf_bags(dd);selection[v],groupexcluded=original.group_selection(bags[v])
        excluded[v]=dict(leaves=leafexcluded,groups=groupexcluded)
    lookup={v:{g['stratum']:g for g in ss['main_HI']} for v,ss in selection.items()};cross_excluded=[]
    for v in selection:selection[v]['cross_version_lengths']=[]
    for key in sorted(set(lookup['ZL']) | set(lookup['IT'])):
        a=lookup['ZL'].get(key);b=lookup['IT'].get(key)
        if not a or not b or a['leaves']!=b['leaves']:
            cross_excluded.append(dict(stratum=key,reason='unequal_leaf_identity_sets'));continue
        common=sorted(set(a['lengths']) & set(b['lengths']))
        if not common:cross_excluded.append(dict(stratum=key,reason='no_common_length'));continue
        for v in selection:selection[v]['cross_version_lengths'].append(dict(stratum=key,leaves=a['leaves'],lengths=common))
    selected=dict(versions=selection,excluded=excluded,cross_version_excluded=cross_excluded,
        body_bag_unit='physical leaf; all constituent page prose tokens pooled by length',frozen_length_strict_support=True)
    # The interrupted version had already saved support, never completed scores.
    previous=HERE/'run_v1/selection.json'
    if previous.exists():assert selected==original.read(previous),'Representation-only change must not change support'
    dump(output/'selection.json',selected)
    (output/'input.json.gz').write_bytes(original.INPUT.read_bytes())
    summaries={}
    for v,ss in selection.items():
        summaries[v]={}
        for mode,groups in ss.items():
            print('SCORING',v,mode,flush=True)
            brief,full=analyse(bags[v],groups);summaries[v][mode]=brief
            dump(output/(v+'_'+mode+'.json.gz'),full)
            if brief.get('status')=='complete_exact':
                print(v,mode,'exact_excess',float(brief['models']['exact']['excess_over_mean']),
                    'exact_upper',str(brief['models']['exact']['p_upper']),'max_increment_upper',str(brief['max_increment_global_null']['p_upper']),flush=True)
    dump(output/'summary.json',summaries)
    dump(output/'complete.json',dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        scope='All six version/support conditions, seven total models and six increments; exact finite permutations in lossless factorized form.',
        files=[dict(path=p.name,sha256=sha(p),bytes=p.stat().st_size) for p in sorted(output.iterdir()) if p.is_file()]))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.output)
