"""Whole-leaf permutation reference, exact integer arithmetic throughout."""
from pathlib import Path
from collections import Counter, defaultdict
from fractions import Fraction
from itertools import permutations, product
import argparse, datetime, gzip, hashlib, json, math, re

HERE=Path(__file__).resolve().parent
SEMANTIC=HERE.parents[1]
INPUT=SEMANTIC.parent/'label_body/saved_v1/input.json.gz'
MODELS=['exact','fk','fp','ft','kp','kt','pt']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_text())
def dump(p,value):
    assert not p.exists(),p
    def encode(x):
        if isinstance(x,Fraction):return dict(numerator=str(x.numerator),denominator=str(x.denominator),decimal=float(x))
        raise TypeError(type(x))
    b=(json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':'),default=encode)+'\n').encode()
    assert b'/Users/' not in b
    p.write_bytes(gzip.compress(b,mtime=0) if p.suffix=='.gz' else b)
def units(w):
    result=tuple(re.findall(r"@\d{3};|[a-z']",w));assert ''.join(result)==w
    return result

def build_leaf_bags(data):
    grouped=defaultdict(list)
    for p in data['pages']:grouped[p['leaf']].append(p)
    bags={};excluded=[]
    for leaf,pp in sorted(grouped.items()):
        hi={(p['H'],p['I']) for p in pp};qs={p['Q'] for p in pp}
        reason=None
        if len(hi)!=1:reason='mixed_HI_physical_leaf'
        elif any(h not in set('12345') or i not in set('ABCHPSTZ') for h,i in hi):reason='unknown_HI'
        labels=defaultdict(list);body=defaultdict(list)
        for p in pp:
            for r in p['labels']:
                labels[len(r['units'])].append(dict(**r,folio=p['folio']))
            for r in p['body']:
                for slot,w in enumerate(r['tokens']):
                    if w is not None:
                        body[len(units(w))].append(dict(word=w,units=list(units(w)),folio=p['folio'],locator=r['locator'],slot=slot))
        if reason is None and not labels:reason='no_complete_singleword_image_label'
        if reason is None and not body:reason='no_retained_prose_word'
        if reason:
            excluded.append(dict(leaf=leaf,reason=reason,labels=sum(map(len,labels.values())),body=sum(map(len,body.values()))));continue
        h,i=next(iter(hi))
        bags[leaf]=dict(leaf=leaf,H=h,I=i,Q=next(iter(qs)) if len(qs)==1 else None,
            pages=[p['folio'] for p in pp],labels=dict(labels),body=dict(body),
            label_types=dict(Counter(r['type'] for ll in labels.values() for r in ll)))
    return bags,excluded

def group_selection(bags):
    hh=defaultdict(list)
    for leaf,b in bags.items():hh[b['H']+'/'+b['I']].append(leaf)
    main=[];excluded=[]
    for key,ll in sorted(hh.items()):
        shared=set.intersection(*[set(bags[l]['labels']) & set(bags[l]['body']) for l in ll])
        if len(ll)<2 or not shared:
            excluded.append(dict(stratum=key,leaves=ll,reason='one_leaf' if len(ll)<2 else 'no_common_length'));continue
        main.append(dict(stratum=key,leaves=sorted(ll),lengths=sorted(shared)))
    strict=[]
    for g in main:
        qq=defaultdict(list)
        for l in g['leaves']:
            if bags[l]['Q'] is not None:qq[bags[l]['Q']].append(l)
        for q,ll in sorted(qq.items()):
            shared=[L for L in g['lengths'] if all(len(bags[l]['body'].get(L,[]))>=5 and bags[l]['labels'].get(L) for l in ll)]
            if len(ll)>=2 and shared:strict.append(dict(stratum=g['stratum']+'/'+q,leaves=sorted(ll),lengths=shared))
    return dict(main_HI=main,strict_HIQ5=strict),excluded

def accepted(w,model):
    a=units(w);out={a}
    if model!='exact':
        x,y=model
        for j,c in enumerate(a):
            if c==x:out.add(a[:j]+(y,)+a[j+1:])
            elif c==y:out.add(a[:j]+(x,)+a[j+1:])
    return out

def matrix_group(bags,g):
    ll=g['leaves'];lengths=g['lengths'];counts={l:{L:Counter(tuple(r['units']) for r in bags[l]['body'][L]) for L in lengths} for l in ll}
    matrices={};components={}
    for model in MODELS:
        rows=[];detail=[]
        for l in ll:
            row=[];dr=[]
            for target in ll:
                perlength=[]
                for L in lengths:
                    labels=bags[l]['labels'][L];n=len(bags[target]['body'][L]);matched=[]
                    for r in labels:
                        m=sum(counts[target][L][u] for u in accepted(r['word'],model))
                        matched.append(dict(locator=r['locator'],word=r['word'],m=m))
                    rate=Fraction(sum(x['m'] for x in matched),len(labels)*n)
                    perlength.append(dict(length=L,query_labels=len(labels),body_opportunities=n,rate=rate,queries=matched))
                row.append(sum((d['rate'] for d in perlength),Fraction(0))/len(lengths));dr.append(perlength)
            rows.append(row);detail.append(dr)
        matrices[model]=rows;components[model]=detail
    return dict(**g,matrices=matrices,components=components)

def convolution(counters):
    current=Counter({0:1})
    for counts in counters:
        nxt=Counter()
        for a,an in current.items():
            for b,bn in counts.items():nxt[a+b]+=an*bn
        current=nxt
    return current

def distribution(counts,observed,denominator):
    total=sum(counts.values());s=sum(k*n for k,n in counts.items());ss=sum(k*k*n for k,n in counts.items())
    mu=Fraction(s,total*denominator);var=Fraction(ss,total*denominator*denominator)-mu*mu
    ge=sum(n for k,n in counts.items() if k>=observed);gt=sum(n for k,n in counts.items() if k>observed);eq=counts[observed]
    return dict(assignments=total,observed=Fraction(observed,denominator),mean=mu,variance=var,
        min=Fraction(min(counts),denominator),max=Fraction(max(counts),denominator),
        excess_over_mean=Fraction(observed,denominator)-mu,
        tail_ge=ge,tail_gt=gt,ties=eq,p_upper=Fraction(ge,total),
        observed_integer=str(observed),score_denominator=str(denominator),
        histogram=[dict(integer_sum=str(k),multiplicity=v) for k,v in sorted(counts.items())])

def max_distribution(groups):
    """Stream the final Cartesian product; do not materialize joint tuples."""
    cc=[]
    for g in groups:
        arrays=g['increments']
        cc.append(Counter(tuple(arrays[m][i] for m in MODELS[1:]) for i in range(len(g['permutations']))))
    prior=Counter({(0,)*6:1})
    for c in cc[:-1]:
        nxt=Counter()
        for a,an in prior.items():
            for b,bn in c.items():nxt[tuple(x+y for x,y in zip(a,b))]+=an*bn
        prior=nxt
    result=Counter()
    for a,an in prior.items():
        for b,bn in cc[-1].items():result[max(x+y for x,y in zip(a,b))]+=an*bn
    return result

def analyse(bags,selection):
    groups=[matrix_group(bags,g) for g in selection]
    if not groups:return dict(status='no_supported_groups'),{}
    n=sum(len(g['leaves']) for g in groups)
    denominator=1
    for g in groups:
        for rows in g['matrices'].values():
            for row in rows:
                for x in row:denominator=math.lcm(denominator,x.denominator)
    saved=[];numerical=[]
    for g in groups:
        size=len(g['leaves']);assert size<=7,'Protocol permits exact enumeration only through seven leaves'
        perms=list(permutations(range(size)));assert perms[0]==tuple(range(size))
        arrays={}
        for model,rows in g['matrices'].items():
            integer=[[int(x*denominator) for x in row] for row in rows]
            arrays[model]=[sum(integer[i][p[i]] for i in range(size)) for p in perms]
        increments={m:[a-b for a,b in zip(arrays[m],arrays['exact'])] for m in MODELS[1:]}
        numerical.append(dict(permutations=perms,scores=arrays,increments=increments))
        groupstats={m:distribution(Counter(a),a[0],size*denominator) for m,a in arrays.items()}
        incstats={m:distribution(Counter(a),a[0],size*denominator) for m,a in increments.items()}
        saved.append(dict(**g,permutations=perms,permutation_order='lexicographic permutations(range(n)); identity index 0',
            integer_scale=str(denominator),scores={m:[str(x) for x in a] for m,a in arrays.items()},
            increments={m:[str(x) for x in a] for m,a in increments.items()},
            summaries=groupstats,increment_summaries=incstats))
    joint={};incjoint={}
    for m in MODELS:
        arrays=[g['scores'][m] for g in numerical]
        joint[m]=distribution(convolution([Counter(a) for a in arrays]),sum(a[0] for a in arrays),n*denominator)
    for m in MODELS[1:]:
        arrays=[g['increments'][m] for g in numerical]
        incjoint[m]=distribution(convolution([Counter(a) for a in arrays]),sum(a[0] for a in arrays),n*denominator)
    observed_max=max(sum(g['increments'][m][0] for g in numerical) for m in MODELS[1:])
    maxresult=distribution(max_distribution(numerical),observed_max,n*denominator)
    result=dict(status='complete_exact',leaf_count=n,group_count=len(groups),
        labels=sum(len(bags[l]['labels'][L]) for g in selection for l in g['leaves'] for L in g['lengths']),
        body_opportunities=sum(len(bags[l]['body'][L]) for g in selection for l in g['leaves'] for L in g['lengths']),
        assignments=math.prod(len(g['permutations']) for g in numerical),integer_scale=str(denominator),
        models=joint,increments=incjoint,max_increment_global_null=maxresult)
    # Compact reader summary; full histograms remain in exact reference artifact.
    brief={**result,'models':{m:{k:v for k,v in r.items() if k!='histogram'} for m,r in joint.items()},
        'increments':{m:{k:v for k,v in r.items() if k!='histogram'} for m,r in incjoint.items()},
        'max_increment_global_null':{k:v for k,v in maxresult.items() if k!='histogram'}}
    return brief,dict(groups=saved,joint=result)

def main(output):
    output.mkdir(parents=True,exist_ok=False)
    dependencies=[HERE/'protocol.txt',Path(__file__),INPUT,HERE/'support.py',HERE/'support_v1.json']
    dump(output/'freeze.json',dict(frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        files=[dict(path=str(p.relative_to(SEMANTIC.parent)),sha256=sha(p)) for p in dependencies],
        scope='Hashes written before constructing any new label/body score matrix. Support-only inventory previously seen.'))
    data=read(INPUT);bags={};selection={};excluded={}
    for v,dd in data.items():
        bags[v],leafexcluded=build_leaf_bags(dd);selection[v],groupexcluded=group_selection(bags[v])
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
    dump(output/'selection.json',dict(versions=selection,excluded=excluded,cross_version_excluded=cross_excluded,
        body_bag_unit='physical leaf; all constituent page prose tokens pooled by length',
        frozen_length_strict_support=True))
    # Preserve the entire previously frozen input, including raw locus strings.
    (output/'input.json.gz').write_bytes(INPUT.read_bytes())
    summaries={}
    for v,ss in selection.items():
        summaries[v]={}
        for mode,groups in ss.items():
            print('SCORING',v,mode,flush=True)
            brief,full=analyse(bags[v],groups)
            summaries[v][mode]=brief
            dump(output/(v+'_'+mode+'.json.gz'),full)
            if brief.get('status')=='complete_exact':
                print(v,mode,'exact',brief['models']['exact']['observed'],brief['models']['exact']['p_upper'],flush=True)
    dump(output/'summary.json',summaries)
    dump(output/'complete.json',dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        scope='All six version/support conditions, seven total models and six increments, exact finite permutations.',
        files=[dict(path=p.name,sha256=sha(p),bytes=p.stat().st_size) for p in sorted(output.iterdir()) if p.is_file()]))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.output)
