"""Synthetic-only gated calibration. No manuscript source or split loader."""
from collections import Counter, defaultdict
from pathlib import Path
import argparse, datetime, gzip, hashlib, json, math, sys, time
import numpy as np
from observer import select, evaluate, truth

HERE = Path(__file__).resolve().parent
SEEDS = tuple(range(2026111700, 2026111720))
RHOS = (0., .15, .5)
PERMUTATIONS = {'identity': (0, 1, 2, 3), 'shift': (2, 3, 0, 1)}
P = np.array([.55, .25, .15, .05])


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False); f.write('\n')


def weight_vector(rows):
    per_page = Counter(r['folio'] for r in rows); per_leaf = defaultdict(set)
    for r in rows:
        per_leaf[r['leaf']].add(r['folio'])
    weights = np.array([1/(len(per_leaf)*len(per_leaf[r['leaf']])*per_page[r['folio']]) for r in rows])
    assert abs(math.fsum(weights)-1) < 1e-12
    return weights


def random_stream(seed, stream, n):
    rng = np.random.default_rng(np.random.SeedSequence([seed, stream]))
    return rng.choice(4, n, p=P), rng.choice(4, n, p=P), rng.random(n)


def decorate(skeleton, x, y):
    assert len(skeleton) == len(x) == len(y)
    return [dict(r, x=int(a), y=int(b)) for r,a,b in zip(skeleton,x,y)]


def weighted(values, weights):
    return math.fsum(float(a)*float(b) for a,b in zip(values,weights))


def summarize(records):
    result = []
    for rho in RHOS:
        for shift in PERMUTATIONS:
            for mode in ('source_transport', 'target_refit'):
                rr = [r for r in records if r['rho']==rho and r['shift']==shift and r['mode']==mode]
                assert len(rr)==20
                def distribution(field):
                    a = np.array([r[field] for r in rr])
                    return dict(mean=float(a.mean()), median=float(np.median(a)), minimum=float(a.min()),
                                maximum=float(a.max()), nonpositive_seeds=int((a<=0).sum()))
                result.append(dict(rho=rho, shift=shift, mode=mode, seeds=20,
                    oracle_mutual_information_bits=rr[0]['oracle_mutual_information_bits'],
                    empirical_gain=distribution('mean_leaf_gain'),
                    exact_expected_gain=distribution('mean_leaf_expected_gain'),
                    selected_zero_weight_seeds=sum(r['config']['weight']==0 for r in rr)))
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--gate',required=True,type=Path); ap.add_argument('--output',required=True,type=Path)
    args=ap.parse_args(); out=args.output.resolve()
    assert not out.exists()
    freeze=HERE/'freeze.json'; gate=json.loads(args.gate.read_text()); receipt=json.loads(freeze.read_text())
    assert gate['approved'] is True and gate['scope']=='synthetic_only' and gate['freeze_sha256']==digest(freeze)
    for item in receipt['files']:
        assert digest(HERE/item['path'])==item['sha256'],item['path']
    skeleton=json.loads(gzip.decompress((HERE/'skeleton.json.gz').read_bytes()))
    train=skeleton['train_legacy']['rows']; target=skeleton['dev']['rows']; folds=skeleton['inner_leaf_fold']
    assert len(train)==1548 and len(target)==647
    out.mkdir(parents=True); (out/'cases').mkdir()
    start=time.process_time()
    write(out/'execution_receipt.json',dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        mode='synthetic_only', freeze_sha256=digest(freeze), gate_sha256=digest(args.gate),
        seeds=list(SEEDS), rhos=list(RHOS), permutations=PERMUTATIONS,
        python=sys.version, numpy=np.__version__,
        real_endpoint_glyphs_used=False, new_manuscript_targets_scored=False, reserve_loaded=False))
    records=[]; case_index=[]
    try:
        for seed in SEEDS:
            streams={k:random_stream(seed,i,n) for k,i,n in [('A',1,len(train)),('B',2,len(train)),('T',3,len(target))]}
            for ri,rho in enumerate(RHOS):
                if datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime(2026,11,17,16,50,25,tzinfo=datetime.timezone.utc):
                    raise RuntimeError('Original research deadline reached; preserve incomplete outputs.')
                if time.process_time()-start>1200:
                    raise RuntimeError('Fixed 1200-second CPU budget exceeded; preserve incomplete outputs, do not reduce design silently.')
                key=f'seed{seed}_rho{ri}'; arrays={}; models={}; configs={}
                for k,(x,noise,u) in streams.items():
                    arrays[k+'_x']=x; arrays[k+'_y']=np.where(u<rho,x,noise)
                for fit,domain,perm in [('source','A',PERMUTATIONS['identity']),
                                        ('target_identity','B',PERMUTATIONS['identity']),
                                        ('target_shift','B',PERMUTATIONS['shift'])]:
                    yy=np.asarray(perm)[arrays[domain+'_y']]
                    cfg,base,child=select(decorate(train,arrays[domain+'_x'],yy),folds)
                    configs[fit]=cfg; models[fit]=(base,child,cfg['weight'])
                costs={}; row_records=[]
                for shift,perm in PERMUTATIONS.items():
                    rows=decorate(target,arrays['T_x'],np.asarray(perm)[arrays['T_y']])
                    joint,marginal,mi=truth(rho,perm)
                    for mode,fit in [('source_transport','source'),('target_refit','target_'+shift)]:
                        prefix=shift+'__'+mode
                        values=evaluate(rows,*models[fit],joint); weights=weight_vector(rows)
                        for name,a in values.items():costs[prefix+'__'+name]=a
                        gain=values['base_bits']-values['model_bits']
                        expected=values['expected_base_bits']-values['expected_model_bits']
                        record=dict(seed=seed,rho=rho,shift=shift,mode=mode,targets=len(rows),
                            oracle_mutual_information_bits=mi,config={k:configs[fit][k] for k in ('base_alpha','alpha','weight')},
                            mean_leaf_gain=weighted(gain,weights),pooled_gain=float(gain.mean()),
                            mean_leaf_expected_gain=weighted(expected,weights),pooled_expected_gain=float(expected.mean()),
                            mean_leaf_base_bits=weighted(values['base_bits'],weights),
                            mean_leaf_model_bits=weighted(values['model_bits'],weights),
                            mean_leaf_expected_base_bits=weighted(values['expected_base_bits'],weights),
                            mean_leaf_expected_model_bits=weighted(values['expected_model_bits'],weights))
                        records.append(record);row_records.append(record)
                # Target training/evaluation are paired label permutations. This
                # exact equivariance is a sanity check, not independent evidence.
                equiv=max(float(np.max(np.abs(costs['identity__target_refit__'+n]-costs['shift__target_refit__'+n])))
                          for n in ('base_bits','model_bits','expected_base_bits','expected_model_bits'))
                assert equiv<1e-11
                datafile=out/'cases'/f'{key}_synthetic.npz';scorefile=out/'cases'/f'{key}_scores.npz'
                np.savez_compressed(datafile,**arrays);np.savez_compressed(scorefile,**costs)
                case=dict(seed=seed,rho=rho,configs=configs,results=row_records,
                    target_label_equivariance_max_error=equiv,
                    synthetic_path=str(datafile.relative_to(out)),synthetic_sha256=digest(datafile),
                    score_path=str(scorefile.relative_to(out)),scores_sha256=digest(scorefile))
                casefile=out/'cases'/f'{key}.json';write(casefile,case)
                case_index.append(dict(path=str(casefile.relative_to(out)),sha256=digest(casefile)))
                print(json.dumps(dict(seed=seed,rho=rho,completed_cases=len(case_index),cpu_seconds=time.process_time()-start)),flush=True)
        assert len(case_index)==60 and len(records)==240
        write(out/'summary.json',dict(complete=True,case_count=60,condition_rows=240,
            groups=summarize(records),records=records,
            seed_distribution_is_not_manuscript_confidence_interval=True,
            refit_identity_shift_equivariance_is_by_design=True,
            true_information_invariant_to_target_bijection=True))
        write(out/'complete.json',dict(all_passed=True,completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            cases=case_index,cpu_seconds=time.process_time()-start,summary_sha256=digest(out/'summary.json')))
    except Exception as exc:
        write(out/'incomplete.json',dict(error=str(exc),completed_cases=case_index,cpu_seconds=time.process_time()-start))
        raise


if __name__=='__main__':main()
