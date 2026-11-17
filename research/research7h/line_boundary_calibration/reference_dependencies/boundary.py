"""Conditional first-unit prediction across word boundaries; no decipherment."""
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
import datetime, itertools, json, math, time
import numpy as np
from corpus import ROOT, load, units, save, sha

UNK = '<UNK>'
ALPHAS = [1, 5, 20, 100, 500]
WEIGHTS = [0, .25, .5, .75, 1]
FEATURES = ['last', 'first']


def records(pages, representation='eva', alphabet=None, overlapping=False):
    rows = []
    for page in pages:
        for li, line in enumerate(page['lines']):
            words = [units(t, representation) if t else None for t in line['tokens']]
            for j in range(2, len(words)-1, 1 if overlapping else 2):
                a, b = words[j-1:j+1]
                if a is None or b is None:
                    continue
                unknown = 0
                if alphabet is not None:
                    unknown = sum(c not in alphabet for c in a+b)
                    a = tuple(c if c in alphabet else UNK for c in a)
                    b = tuple(c if c in alphabet else UNK for c in b)
                rows.append(dict(folio=page['folio'], leaf=page['leaf'], line=li,
                                 slot=j, previous_slot=j-1, line_slots=len(words),
                                 hand=page['metadata'].get('H', '?'),
                                 section=page['metadata'].get('I', '?'),
                                 previous_length=len(a), length=len(b),
                                 position_bin=min(2, 3*j//(len(words)-1)),
                                 paragraph_line=int(line['paragraph_start']),
                                 first=a[0], last=a[-1], target=b[0], unknown=unknown))
    return rows


def contexts(row, feature=None, value=None):
    h, s = row['hand'], row['section']
    tl, pl = min(row['length'], 10), min(row['previous_length'], 10)
    keys = [(), ('hs', h, s), ('tl', h, s, tl), ('pl', h, s, tl, pl),
            ('position', h, s, tl, pl, row['position_bin'], row['paragraph_line'])]
    if feature:
        v = row[feature] if value is None else value
        keys = [()] + [('context', v)] + [key+(v,) for key in keys[1:]]
    return tuple(keys)


class Conditional:
    def __init__(self, rows, alphabet, alpha, feature=None):
        self.vocab = tuple(sorted(set(alphabet)|{UNK}))
        self.lookup = {c:i for i,c in enumerate(self.vocab)}
        self.alpha = alpha
        self.feature = feature
        self.counts = defaultdict(Counter)
        self.totals = Counter()
        for row in rows:
            for key in contexts(row, feature):
                self.counts[key][row['target']] += 1
                self.totals[key] += 1

    @lru_cache(maxsize=200000)
    def distribution(self, keys):
        out = np.full(len(self.vocab), 1/len(self.vocab))
        for key in keys:
            count = self.counts.get(key, {})
            if not count:
                continue
            arr = np.array([count.get(c, 0) for c in self.vocab], dtype=float)
            out = (arr+self.alpha*out)/(self.totals[key]+self.alpha)
        out.flags.writeable = False
        return out

    def prob(self, row, value=None):
        return self.distribution(contexts(row, self.feature, value))[self.lookup[row['target']]]

    def scores(self, rows):
        return np.log2(np.array([self.prob(row) for row in rows]))


def tuning(train, dev, alphabet):
    base_options = []
    for alpha in ALPHAS:
        model = Conditional(train, alphabet, alpha)
        loss = float(-model.scores(dev).mean())
        base_options.append((loss, -alpha, model))
    _, _, base = min(base_options, key=lambda item: item[:2])
    base_probs = np.array([base.prob(r) for r in dev])
    models = {}
    grid = {'base': [[loss, -negative] for loss, negative, _ in base_options]}
    for feature in FEATURES:
        options = []
        for alpha in ALPHAS:
            model = Conditional(train, alphabet, alpha, feature)
            child_probs = np.array([model.prob(r) for r in dev])
            for weight in WEIGHTS:
                loss = float(-np.log2((1-weight)*base_probs+weight*child_probs).mean())
                options.append((loss, weight, -alpha, model))
        loss, weight, _, model = min(options, key=lambda item: item[:3])
        models[feature] = (model, weight)
        grid[feature] = [[a,b,-c] for a,b,c,_ in options]
    return base, models, grid


def leaf_weights(rows):
    per_page = Counter(r['folio'] for r in rows)
    per_leaf = defaultdict(set)
    for row in rows:
        per_leaf[row['leaf']].add(row['folio'])
    return np.array([1/(len(per_leaf)*len(per_leaf[r['leaf']])*per_page[r['folio']]) for r in rows])


def summary(rows, logprob, base_logprob=None):
    per_page = defaultdict(list)
    leafmap = {}
    for row, lp in zip(rows, logprob):
        per_page[row['folio']].append(-float(lp))
        leafmap[row['folio']] = row['leaf']
    result = dict(bits_per_target=float(-logprob.mean()), targets=len(rows),
                  pages=len(per_page), leaves=len(set(leafmap.values())),
                  page_results={f:dict(targets=len(v), bits_per_target=float(np.mean(v)))
                                for f,v in per_page.items()})
    if base_logprob is not None:
        page_gain = defaultdict(list)
        for row, gain in zip(rows, logprob-base_logprob):
            page_gain[row['folio']].append(float(gain))
        leaf_gain = defaultdict(list)
        for f,v in page_gain.items():
            leaf_gain[leafmap[f]].append(float(np.mean(v)))
        values = np.array([np.mean(v) for v in leaf_gain.values()])
        rng = np.random.default_rng(2026111722)
        boot = rng.choice(values, (1999, len(values)), replace=True).mean(axis=1)
        result['improvement'] = dict(pooled_bits_saved=float((logprob-base_logprob).mean()),
            mean_leaf_bits_saved=float(values.mean()), bootstrap95=np.quantile(boot, [.025,.975]).tolist(),
            bootstrap_replicates=1999, per_leaf={k:float(np.mean(v)) for k,v in leaf_gain.items()})
    return result


def permutation_buckets(rows, broad=False):
    buckets = defaultdict(list)
    for i,r in enumerate(rows):
        key = (r['folio'], r['previous_length'], r['length'])
        if not broad:
            key += (r['position_bin'], r['paragraph_line'])
        buckets[key].append(i)
    return [np.array(v, dtype=int) for v in buckets.values()]


def holm(values):
    ordered = sorted(values, key=values.get)
    out = {}; bound = 0.
    for i,key in enumerate(ordered):
        bound = max(bound, min(1., (len(ordered)-i)*values[key]))
        out[key] = bound
    return out


def permute(rows, base, models, name, replicates=1999, broad=False, seed=2026111721):
    rng = np.random.default_rng(seed)
    bp = np.array([base.prob(r) for r in rows])
    weights = leaf_weights(rows)
    assert abs(weights.sum()-1) < 1e-12
    buckets = permutation_buckets(rows, broad)
    movable = np.array([i for b in buckets if len(b)>1 for i in b])
    matrices = {}; ids = {}; observed = {}; direct = {}
    for feature,(model,weight) in models.items():
        alphabet = sorted({r[feature] for r in rows})
        lookup = {c:i for i,c in enumerate(alphabet)}
        ids[feature] = np.array([lookup[r[feature]] for r in rows])
        prob = np.array([[(1-weight)*bp[i]+weight*model.prob(r,c) for c in alphabet]
                         for i,r in enumerate(rows)])
        matrices[feature] = np.log2(prob)-np.log2(bp[:,None])
        direct[feature] = np.array([math.log2((1-weight)*bp[i]+weight*model.prob(r))-math.log2(bp[i])
                                   for i,r in enumerate(rows)])
        assert np.allclose(direct[feature], matrices[feature][np.arange(len(rows)), ids[feature]], atol=1e-14)
        observed[feature] = float(np.sum(weights*direct[feature]))
    nulls = {k:np.empty(replicates) for k in models}
    changes = {k:0 for k in models}; joint_changed = 0
    for b in range(replicates):
        perm = np.arange(len(rows))
        for bucket in buckets:
            if len(bucket)>1:
                perm[bucket] = rng.permutation(bucket)
        if b==0:
            for i,j in enumerate(perm):
                for field in ['folio','previous_length','length'] + ([] if broad else ['position_bin','paragraph_line']):
                    assert rows[i][field] == rows[j][field]
        changed = np.zeros(len(rows), dtype=bool)
        for feature in models:
            c = ids[feature] != ids[feature][perm]
            changes[feature] += int(c.sum()); changed |= c
            nulls[feature][b] = np.sum(weights*matrices[feature][np.arange(len(rows)), ids[feature][perm]])
        joint_changed += int(changed.sum())
    pvalues = {k:(1+int((arr>=observed[k]-1e-14).sum()))/(replicates+1) for k,arr in nulls.items()}
    adjusted = holm(pvalues)
    path = ROOT/'results'/f'{name}_nulls.npz'
    np.savez_compressed(path, **nulls)
    results = {k:dict(observed_leaf_bits_saved=observed[k], null_mean=float(arr.mean()),
                     null95=np.quantile(arr,[.025,.975]).tolist(), raw_p=pvalues[k], holm_p=adjusted[k],
                     actual_context_changed_fraction=changes[k]/(replicates*len(rows)))
               for k,arr in nulls.items()}
    count = Counter(rows[i]['folio'] for i in movable)
    page_n = Counter(r['folio'] for r in rows)
    return dict(replicates=replicates, seed=seed, broad=broad, targets=len(rows),
                bucket_count=len(buckets), singleton_buckets=sum(len(b)==1 for b in buckets),
                non_singleton_target_fraction=len(movable)/len(rows),
                joint_actual_changed_fraction=joint_changed/(replicates*len(rows)),
                per_page_movable_fraction={f:count[f]/n for f,n in page_n.items()},
                null_array=str(path.relative_to(ROOT)), null_sha256=sha(path), tests=results)


def verify():
    # A deliberately small normalized model with both observed and unseen contexts.
    rows = []
    rng = np.random.default_rng(81)
    for i in range(3000):
        first = str(rng.integers(0,4))
        rows.append(dict(folio='f1r',leaf='f1',line=i,slot=2,previous_slot=1,line_slots=4,
                         hand='1',section='H',previous_length=3,length=3,position_bin=1,
                         paragraph_line=0,first=first,last=first,target=first,unknown=0))
    alphabet = set('0123')
    base, models, _ = tuning(rows[:1800], rows[1800:2400], alphabet)
    test = rows[2400:]
    for model in [base]+[m for m,w in models.values()]:
        for r in test[:20]:
            for c in ['0','3',UNK]:
                assert abs(model.distribution(contexts(r,model.feature,c)).sum()-1)<1e-12
    bp = np.array([base.prob(r) for r in test])
    gains = {}
    for key,(model,w) in models.items():
        for r in test[:20]:
            mix=(1-w)*base.distribution(contexts(r))+w*model.distribution(contexts(r,key))
            assert abs(mix.sum()-1)<1e-12
        gains[key]=float(np.log2([(1-w)+w*model.prob(r)/bp[i] for i,r in enumerate(test)]).mean())
        assert gains[key]>1.8
    # Independent targets, independently selected dev tuning, must have no large gain.
    independent=[]
    for r in rows:
        r=dict(r);r['target']=str(rng.integers(0,4));independent.append(r)
    ib, im, _ = tuning(independent[:1800],independent[1800:2400],alphabet)
    independent_gains={}
    for k,(m,w) in im.items():
        independent_gains[k]=float(np.mean([math.log2((1-w)+w*m.prob(r)/ib.prob(r)) for r in independent[2400:]]))
        assert independent_gains[k]<.05
    # Independent enumeration of all 4! source-target assignments.
    target=np.array([0,0,1,1]);context=np.array([0,0,1,1])
    table=np.where(target[:,None]==np.arange(2)[None,:],.9,.1)
    enumerated=[];direct=[]
    for perm in itertools.permutations(range(4)):
        enumerated.append(float(np.log2(table[np.arange(4),context[list(perm)]]).mean()))
        direct.append(sum(math.log2(.9 if target[i]==context[j] else .1) for i,j in enumerate(perm))/4)
    assert np.allclose(enumerated,direct,atol=1e-14)
    assert sum(x>=enumerated[0]-1e-14 for x in enumerated)==4
    # Synthetic physical line checks missing slots and independent pairs.
    page=dict(folio='f2r',leaf='f2',metadata={},lines=[dict(tokens=['a','b','c',None,'d','e','f','g'],paragraph_start=False)])
    pairs=records([page]);assert [(r['previous_slot'],r['slot']) for r in pairs]==[(1,2),(5,6)]
    return dict(distributions_normalize=True,known_dependency_bits_saved=gains,
                independent_control_bits_saved=independent_gains,permutation_exhaustive_24=True,
                missing_slots_not_bridged=True,nonoverlapping_pairs=True)


def run(source='ZL3b-n.txt', representation='eva', name='boundary_confirm'):
    start=time.time()
    receipt=json.loads((ROOT/'boundary_receipt.json').read_text())
    assert receipt['protocol_sha256']==sha(ROOT/'boundary_protocol.txt')
    assert receipt['split_sha256']==sha(ROOT/'split_manifest.json')
    trainp=load(source,splits=['legacy','train']);devp=load(source,splits=['dev'])
    alphabet={c for p in trainp for line in p['lines'] for t in line['tokens'] if t for c in units(t,representation)}
    train=records(trainp,representation,alphabet);dev=records(devp,representation,alphabet)
    for rows in [train,dev]:
        slots=set()
        for r in rows:
            for slot in [r['previous_slot'],r['slot']]:
                key=(r['folio'],r['line'],slot);assert key not in slots;slots.add(key)
    base,models,grid=tuning(train,dev,alphabet)
    selected=dict(base_alpha=base.alpha,features={k:dict(alpha=m.alpha,weight=w) for k,(m,w) in models.items()})
    config=dict(source=source,representation=representation,selected=selected,tuning=grid,
                train_pairs=len(train),dev_pairs=len(dev),alphabet=sorted(alphabet),
                frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                protocol_sha256=sha(ROOT/'boundary_protocol.txt'),split_sha256=sha(ROOT/'split_manifest.json'))
    configpath=ROOT/'results'/f'{name}_frozen_config.json'
    if configpath.exists():
        existing=json.loads(configpath.read_text())
        assert existing['selected']==selected and existing['tuning']==grid,'Changed frozen selected configuration'
    else:
        save(configpath.relative_to(ROOT),config)
    # Only now load confirm. Reserve is never requested.
    testp=load(source,splits=['confirm']);rows=records(testp,representation,alphabet)
    bp=np.array([base.prob(r) for r in rows]);blp=np.log2(bp)
    results={'base':summary(rows,blp)}
    for key,(model,w) in models.items():
        lp=np.log2([(1-w)*bp[i]+w*model.prob(r) for i,r in enumerate(rows)])
        results[key]=summary(rows,lp,blp)
    primary=permute(rows,base,models,name)
    broad=permute(rows,base,models,name+'_broad',399,True,2026111723)
    overlap=records(testp,representation,alphabet,True)
    overlap_permutation=permute(overlap,base,models,name+'_overlap',399,False,2026111723)
    out=dict(source=source,representation=representation,selected=selected,
             train_pairs=len(train),dev_pairs=len(dev),confirm_pairs=len(rows),
             mapped_unknown_units=sum(r['unknown'] for r in rows),
             config_sha256=sha(configpath),results=results,primary=primary,
             auxiliary_broad=broad,auxiliary_overlap=overlap_permutation,
             elapsed_seconds=time.time()-start,
             interpretation='Conditional first-unit prediction only; target length is known side information. No word meaning, grammar or plaintext established.')
    save('results/'+name+'.json',out)
    print(json.dumps(dict(name=name,selected=selected,pairs=len(rows),
                         scores={k:v['bits_per_target'] for k,v in results.items()},
                         improvements={k:v['improvement'] for k,v in results.items() if k!='base'},
                         primary=primary['tests'],movable=primary['non_singleton_target_fraction'],
                         seconds=out['elapsed_seconds']),indent=2),flush=True)


if __name__=='__main__':
    (ROOT/'results').mkdir(exist_ok=True)
    save('results/boundary_verification.json',verify())
    run()
    run('ZL3b-n.txt','merged','boundary_confirm_merged')
    run('IT2a-n.txt','eva','boundary_confirm_IT')
