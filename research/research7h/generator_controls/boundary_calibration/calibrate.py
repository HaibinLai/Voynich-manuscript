"""Frozen synthetic-control calibration; never loads manuscript transcriptions."""
from pathlib import Path
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse, datetime, hashlib, importlib.util, json, math, os, sys, time
import numpy as np

HERE = Path(__file__).resolve().parent
GENERATOR_ROOT = HERE.parent
RESEARCH_ROOT = GENERATOR_ROOT.parent
sys.path.insert(0, str(RESEARCH_ROOT))
import corpus

def forbidden(*args, **kwargs):
    raise RuntimeError('Manuscript loading/root writing forbidden in synthetic calibration')

corpus.load = corpus.all_pages = corpus.parse = corpus.save = forbidden
spec = importlib.util.spec_from_file_location('calibration_reference_boundary', HERE/'reference_boundary.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
b.ROOT = HERE
b.load = b.save = forbidden
from analyze import plain_words

SPLITS = {'train': (0,4000), 'dev': (4000,6000), 'test': (6000,8000)}
EXPECTED = {'train': 1665, 'dev': 830, 'test': 830}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text_sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def stream_seed(*parts):
    return int.from_bytes(hashlib.sha256('|'.join(map(str, parts)).encode()).digest()[:8], 'little')


def verify_receipt():
    receipt = json.loads((HERE/'protocol_receipt.json').read_text())
    for item in receipt['files']:
        assert sha(HERE/item['path']) == item['sha256'], item['path']
    assert 'weights@' not in (HERE/'reference_boundary.py').read_text()
    return {'files_checked': len(receipt['files']), 'protocol_receipt_sha256': sha(HERE/'protocol_receipt.json')}


def task_id(task):
    return '{generator}_{seed}_{order}_{representation}'.format(**task)


def prepare(task):
    generator, seed, order = (task[k] for k in ('generator','seed','order'))
    if generator == 'latin':
        path = RESEARCH_ROOT.parent/'study20/controls/latin_caesar.xml'
        words = plain_words('latin_caesar.xml')
    else:
        path = GENERATOR_ROOT/'data'/f'seed_{seed}'/('naibbe_strict_unique.txt' if generator=='naibbe_strict' else 'timm.txt')
        words = path.read_text().split()
    assert len(words) >= 8000
    words = words[:8000]
    source = {'path': os.path.relpath(path, HERE), 'sha256': sha(path),
              'first8000_tokens_sha256': text_sha('\n'.join(words)), 'logical_tokens':8000}
    truth = None
    if generator == 'naibbe_strict':
        tp = path.with_name('naibbe_strict_unique_truth.txt')
        truth = tp.read_text().split()[:8000]
        assert len(truth)==len(words)
        lp = GENERATOR_ROOT/'data/latin_normalized.txt'
        normalized = ''.join(lp.read_text().split()).lower()
        assert ''.join(truth)==normalized[:len(''.join(truth))]
        source['truth_path'] = os.path.relpath(tp,HERE)
        source['truth_sha256'] = sha(tp)
        source['normalized_latin_sha256'] = sha(lp)
    pages, meta, offset = {}, {}, 0
    for split,(start,stop) in SPLITS.items():
        selected = words[start:stop]
        positions = np.arange(start,stop)
        if order == 'shuffled':
            rng = np.random.default_rng(stream_seed('whole-word-control-v1',generator,seed,split))
            indices = rng.permutation(len(selected))
            positions = positions[indices]
            selected = [selected[i] for i in indices]
        else:
            assert order=='original'
        n = len(selected)//12*12
        included = selected[:n]
        label = task_id(task)+'_'+split
        pages[split] = {'folio':label, 'leaf':label, 'metadata':{'H':'control','I':'control'},
                        'lines':[{'tokens':included[i:i+12], 'paragraph_start':False} for i in range(0,n,12)]}
        meta[split] = {'logical_range':[start,stop], 'logical_tokens':stop-start,
                       'used_tokens':n, 'discarded_tokens':len(selected)-n,
                       'discarded_original_token_positions':positions[n:].tolist(),
                       'ordered_used_tokens_sha256':text_sha('\n'.join(included)),
                       'permutation_positions_sha256':text_sha(','.join(map(str,positions))),
                       'artificial_lines':n//12}
        assert set(positions)==set(range(start,stop))
        if truth is not None:
            fragment = ''.join(truth[start:stop])
            assert fragment == normalized[offset:offset+len(fragment)]
            meta[split]['plaintext_character_range'] = [offset,offset+len(fragment)]
            meta[split]['plaintext_span_sha256'] = text_sha(fragment)
            offset += len(fragment)
    # Logical ranges and plaintext spans are mutually disjoint; shuffling stays inside each.
    assert all(SPLITS[a][1]==SPLITS[c][0] for a,c in [('train','dev'),('dev','test')])
    return pages, {'source':source,'splits':meta}


def checked_records(page, representation, alphabet, split):
    rows = b.records([page], representation, alphabet)
    assert len(rows)==EXPECTED[split]
    seen = set()
    for row in rows:
        assert row['slot'] in (2,4,6,8,10) and row['previous_slot']==row['slot']-1
        assert row['line_slots']==12
        for slot in (row['slot'],row['previous_slot']):
            key=(row['folio'],row['line'],slot)
            assert key not in seen
            seen.add(key)
    return rows


def run_task(task):
    started=time.monotonic()
    b.Conditional.distribution.cache_clear()
    name=task_id(task)
    final_path=HERE/'runs'/f'{name}.json'
    if final_path.exists():
        existing=json.loads(final_path.read_text())
        assert existing['protocol_receipt_sha256']==sha(HERE/'protocol_receipt.json')
        assert existing['code_sha256']==sha(HERE/'calibrate.py')
        return {'name':name,'cached':True}
    pages, metadata=prepare(task)
    alphabet={u for line in pages['train']['lines'] for token in line['tokens'] for u in b.units(token,task['representation'])}
    train=checked_records(pages['train'],task['representation'],alphabet,'train')
    dev=checked_records(pages['dev'],task['representation'],alphabet,'dev')
    base,models,grid=b.tuning(train,dev,alphabet)
    selected={'base_alpha':base.alpha,'features':{key:{'alpha':model.alpha,'weight':weight} for key,(model,weight) in models.items()}}
    config={'task':task,'selected':selected,'tuning':grid,'alphabet':sorted(alphabet),
            'train_pairs':len(train),'dev_pairs':len(dev),'train_dev_metadata':{k:metadata['splits'][k] for k in ('train','dev')},
            'frozen_utc':now(),'protocol_receipt_sha256':sha(HERE/'protocol_receipt.json'),
            'code_sha256':sha(HERE/'calibrate.py'),'reference_sha256':sha(HERE/'reference_boundary.py')}
    cp=HERE/'configs'/f'{name}.json'
    if cp.exists():
        prior=json.loads(cp.read_text())
        for k in ('task','selected','tuning','alphabet','train_dev_metadata','code_sha256','reference_sha256'):
            assert prior[k]==config[k], ('changed frozen config',name,k)
    else:
        dump(cp,config)
    # Test scoring starts only after complete development selection is saved.
    test_started=now()
    rows=checked_records(pages['test'],task['representation'],alphabet,'test')
    bp=np.array([base.prob(r) for r in rows]);blp=np.log2(bp)
    scores={'base':{'bits_per_target':float(-blp.mean())}}
    for key,(model,weight) in models.items():
        lp=np.log2([(1-weight)*bp[i]+weight*model.prob(r) for i,r in enumerate(rows)])
        gain=lp-blp
        independent=math.fsum(math.log2((1-weight)+weight*model.prob(r)/bp[i]) for i,r in enumerate(rows))/len(rows)
        assert abs(float(gain.mean())-independent)<1e-12
        scores[key]={'bits_per_target':float(-lp.mean()),'bits_saved':float(gain.mean())}
        for row in rows[:20]:
            assert abs(model.distribution(b.contexts(row,key)).sum()-1)<1e-12
    permutation_seed=stream_seed('conditional-reassignment-v1',task['generator'],task['seed'],task['representation'])
    permutation=b.permute(rows,base,models,name,replicates=1999,broad=False,seed=permutation_seed)
    for key in models:
        assert abs(permutation['tests'][key]['observed_leaf_bits_saved']-scores[key]['bits_saved'])<1e-12
    result={'task':task,'name':name,'scores':scores,
            'last_minus_first_bits':scores['last']['bits_saved']-scores['first']['bits_saved'],
            'selected':selected,'targets':{k:EXPECTED[k] for k in SPLITS},'metadata':metadata,
            'unknown_units':{'train':sum(r['unknown'] for r in train),'dev':sum(r['unknown'] for r in dev),'test':sum(r['unknown'] for r in rows)},
            'test_target_unknowns':sum(r['target']==b.UNK for r in rows),
            'permutation':permutation,'config_path':str(cp.relative_to(HERE)), 'config_sha256':sha(cp),
            'test_scoring_started_utc':test_started,'completed_utc':now(),
            'protocol_receipt_sha256':sha(HERE/'protocol_receipt.json'),'code_sha256':sha(HERE/'calibrate.py'),
            'elapsed_seconds':time.monotonic()-started,
            'interpretation':'Conditional first-unit score with both word lengths known; artificial geometry; no semantic or manuscript confidence claim.'}
    dump(final_path,result)
    b.Conditional.distribution.cache_clear()
    return {'name':name,'seconds':round(result['elapsed_seconds'],2),'gains':{k:scores[k]['bits_saved'] for k in models}}


def all_tasks():
    tasks=[]
    for generator in ('naibbe_strict','timm'):
        for seed in range(19,39):
            for order in ('original','shuffled'):
                for representation in ('eva','merged'):
                    tasks.append(dict(generator=generator,seed=seed,order=order,representation=representation))
    tasks.append(dict(generator='latin',seed=19,order='original',representation='eva'))
    tasks.extend(dict(generator='latin',seed=seed,order='shuffled',representation='eva') for seed in range(19,39))
    assert len(tasks)==181
    return tasks


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=2);parser.add_argument('--smoke',action='store_true');args=parser.parse_args()
    for folder in ('results','runs','configs'):(HERE/folder).mkdir(exist_ok=True)
    receipt=verify_receipt()
    verification=b.verify();b.Conditional.distribution.cache_clear()
    verification.update(receipt)
    verification['transcript_loaders_disabled']=True
    dump(HERE/'verification.json',verification)
    tasks=all_tasks()
    execution={'frozen_utc':now(),'code_sha256':sha(HERE/'calibrate.py'),'protocol_receipt_sha256':sha(HERE/'protocol_receipt.json'),
               'tasks':tasks,'task_count':len(tasks),'workers':args.workers,'numpy_version':np.__version__,'python_version':sys.version,
               'python_implementation':sys.implementation.name}
    ep=HERE/'execution_receipt.json'
    if ep.exists():
        old=json.loads(ep.read_text());assert old['code_sha256']==execution['code_sha256'];assert old['tasks']==tasks
    else:dump(ep,execution)
    if args.smoke:
        print(json.dumps(run_task(tasks[0])),flush=True)
        return
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures={executor.submit(run_task,t):t for t in tasks}
        for index,future in enumerate(as_completed(futures),1):
            item=future.result();item['completed']=index;item['total']=len(tasks)
            print(json.dumps(item),flush=True)
    verify_receipt()
    print('ALL 181 FROZEN TASKS COMPLETE',flush=True)


if __name__=='__main__':main()
