# -*- coding: utf-8 -*-
"""CPU NumPy-only replay of saved selected weights and complete original-word scores.

No imports from model.py, run_job.py, or any fitting/selection implementation.
This program does not fit parameters, choose pairs, or generate new evaluation data.
Run only after results are explicitly released for independent audit.
"""
from pathlib import Path
import argparse, collections, datetime, gzip, hashlib, json, math, re, sys, traceback
import numpy as np

ATOL_BITS_PER_WORD = 1e-8
BOS = '<BOS>'
OTHER = '<OTHER>'
CASES = {'true_alias','non_alias','position_confound','frequency_confound','iid'}

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''): h.update(block)
    return h.hexdigest()

def write(path, obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def decode_word(word, universe):
    if isinstance(word,str):
        # Exact entire-string tokenization; never strip punctuation or salvage a substring.
        tokens=[];pos=0
        while pos<len(word):
            found=re.match(r"@[0-9]{3};|[a-z']",word[pos:])
            if not found: raise ValueError('Invalid original unit encoding at offset '+str(pos))
            tokens.append(found.group());pos+=len(found.group())
    elif isinstance(word,list) and all(isinstance(x,str) for x in word):tokens=list(word)
    else:raise TypeError('word must be a unit list or an exact encoded original-unit string')
    if not tokens or any(x not in universe for x in tokens):raise ValueError('Empty word or unit outside fixed universe')
    return tokens

class Dataset:
    """Independent sparse prefix features and targets, cached without model objects."""
    def __init__(self, records, common, universe):
        if not isinstance(records,list) or not records:raise ValueError('Expected nonempty ordered record list')
        self.records=records;self.common=tuple(common);self.universe=tuple(universe)
        if len(set(universe))!=len(universe) or len(set(common))!=len(common):raise ValueError('Duplicate alphabet entry')
        if not set(common)<=set(universe):raise ValueError('COMMON outside universe')
        self.has_other=len(common)<len(universe)
        self.outputs=list(common)+([OTHER] if self.has_other else [])
        self.hist=self.outputs+[BOS]
        self.output_id={s:i for i,s in enumerate(self.outputs)}
        self.history_id={s:i for i,s in enumerate(self.hist)}
        self.C=len(self.outputs);self.F=1+3*len(self.hist)+17
        self.identity_bits=math.log2(len(universe)-len(common)) if self.has_other else 0.0
        self.contexts=[];self.context_id={};self.word_events=[];self.rare_counts=[]
        self.words=[]
        common_set=set(common);universe_set=set(universe)
        for record in records:
            units=decode_word(record['word'],universe_set);self.words.append(units)
            history=[BOS,BOS,BOS];events=[];rare=0
            for j in range(len(units)+1):
                # j counts already generated original units. EOS uses the same j.
                key=(min(j,16),tuple(history))
                if key not in self.context_id:
                    self.context_id[key]=len(self.contexts);self.contexts.append(key)
                context=self.context_id[key]
                if j==len(units):target=-1  # EOS reference logit zero, never an input.
                else:
                    unit=units[j]
                    symbol=unit if unit in common_set else OTHER
                    target=self.output_id[symbol]
                    rare+=int(symbol==OTHER)
                    history=history[1:]+[symbol]
                events.append((context,target))
            self.word_events.append(events);self.rare_counts.append(rare)
        sparse=[];first=[]
        for position,history in self.contexts:
            sparse.append([0,1+3*len(self.hist)+position]+[1+lag*len(self.hist)+self.history_id[s] for lag,s in enumerate(history)])
            first.append(position==0)
        self.features=np.asarray(sparse,dtype=np.int64)
        self.first=np.asarray(first,dtype=bool)
        self.identity_fees=np.asarray(self.rare_counts,dtype=np.float64)*self.identity_bits

    def score(self, weights):
        weights=np.asarray(weights)
        if weights.dtype!=np.dtype('float64') or weights.ndim!=1 or len(weights)!=self.F*self.C:
            raise ValueError('Saved weights must be flat float64 with exactly F*C entries')
        if not np.isfinite(weights).all():raise ValueError('Nonfinite weights')
        coefficients=weights.reshape(self.F,self.C)
        # Each context has five active additive features; no production design matrix used.
        logits=np.sum(coefficients[self.features],axis=1,dtype=np.float64)
        maximum=np.max(logits,axis=1)
        maximum=np.where(self.first,maximum,np.maximum(0.0,maximum))
        shifted=np.exp(logits-maximum[:,None]).sum(axis=1,dtype=np.float64)
        # The reference EOS contributes exp(0-max) only after at least one original unit.
        eos_term=np.zeros_like(maximum)
        eos_term[~self.first]=np.exp(-maximum[~self.first])
        shifted+=eos_term
        normalizers=maximum+np.log(shifted)
        costs=[]
        for index,events in enumerate(self.word_events):
            terms=[]
            for context,target in events:
                if target==-1:
                    if self.first[context]:raise AssertionError('Empty-word EOS was scored')
                    terms.append(float(normalizers[context]))
                else:terms.append(float(normalizers[context]-logits[context,target]))
            costs.append(math.fsum(terms)/math.log(2)+float(self.identity_fees[index]))
        result=np.asarray(costs,dtype=np.float64)
        if not np.isfinite(result).all():raise ValueError('Nonfinite independent scores')
        return result

class Reader:
    def __init__(self):self.hashes={}
    def read(self,path):
        key=str(path.resolve());current=digest(path)
        if key in self.hashes and self.hashes[key]!=current:raise RuntimeError('Input changed between reads: '+key)
        self.hashes[key]=current
        if path.suffix=='.gz':
            with gzip.open(path,'rt',encoding='utf-8') as f:
                return [json.loads(line) for line in f if line.strip()] if path.name.endswith('.jsonl.gz') else json.load(f)
        return json.loads(path.read_text(encoding='utf-8'))

def load_inputs(root, job, reader):
    if job['kind']=='synthetic':
        if job['case'] not in CASES or not isinstance(job['seed'],int):raise ValueError('Invalid synthetic job identity')
        folder=root/'synthetic_data'/('seed'+str(job['seed']))/job['case']
        data={split:reader.read(folder/(split+'.jsonl.gz')) for split in ['train','dev','test']}
        universe=list('abcdefgh')
    elif job['kind']=='manuscript':
        version=job['version']
        if version not in ['ZL','IT']:raise ValueError('Unknown transcription version')
        train_dev=reader.read(root/'inputs'/(version+'_train_dev.json.gz'))
        data={'train':train_dev['train'],'dev':train_dev['dev'],
              'confirm':reader.read(root/'inputs'/(version+'_confirm.json.gz')),
              'reserve':reader.read(root/'inputs'/(version+'_reserve.json.gz'))}
        universe=list('abcdefghijklmnopqrstuvwxyz')+["'"]+['@%03d;'%i for i in range(1000)]
    else:raise ValueError('Unknown job kind')
    counts=collections.Counter(s for record in data['train'] for s in decode_word(record['word'],set(universe)))
    common=sorted(s for s,n in counts.items() if n>=20)
    return data,common,universe

def check_job(root, results, job, out, reader, cache):
    job_id=job['id']
    if not re.fullmatch(r'[A-Za-z0-9_-]+',job_id):raise ValueError('Unsafe job identifier')
    folder=results/job_id
    if (folder/'ERROR.txt').exists() and not (folder/'DONE').exists():
        reader.hashes[str((folder/'ERROR.txt').resolve())]=digest(folder/'ERROR.txt')
        return dict(id=job_id,author_status='error_preserved',scores_replayed=False,passed=True,
                    note='Original job failed; not counted as a successful selected model.')
    if not (folder/'DONE').is_file():raise FileNotFoundError('Missing completed result marker for '+job_id)
    saved_job=reader.read(folder/'job.json');audit=reader.read(folder/'audit.json')
    if saved_job!=job or audit['job']!=job or audit['pairs']!=job['pairs']:raise ValueError('Job identity/pairs mismatch')
    reader.hashes[str((folder/'DONE').resolve())]=digest(folder/'DONE')
    identity=(job['kind'],job.get('version'),job.get('seed'),job.get('case'))
    if cache.get('identity')!=identity:
        data,common,universe=load_inputs(root,job,reader)
        datasets={split:Dataset(rows,common,universe) for split,rows in data.items()}
        cache.clear();cache.update(identity=identity,datasets=datasets,common=common,universe=universe)
    datasets=cache['datasets'];common=cache['common'];universe=cache['universe'];train=datasets['train']
    for field,value in [('common',common),('universe_size',len(universe)),('feature_count',train.F),('nonreference_outputs',train.C),('dimension',train.F*train.C),('train_contexts',len(train.contexts))]:
        if audit[field]!=value:raise ValueError('Recorded '+field+' differs from independent training reconstruction')
    expected_targets={}
    failed=[]
    for target in audit['targets']:
        value=float(target['target'])
        if value not in (50.,150.):raise ValueError('Unexpected target DF')
        key='df'+str(int(value))
        if target['matched']:
            if target['selected']['status']!='converged':raise ValueError('Selected failed optimizer state')
            if abs(target['selected']['df']-value)>max(.1,.002*value):raise ValueError('Selected DF outside frozen tolerance')
            expected_targets[key]=target
        else:failed.append(dict(target=value,reason='unmatched',refinement_statuses=[x['status'] for x in target['refinements']]))
    if len(audit['targets'])!=2 or {float(x['target']) for x in audit['targets']}!={50.,150.}:raise ValueError('Expected both frozen DF targets exactly once')
    for name in ['weights.npz','scores.npz']:reader.hashes[str((folder/name).resolve())]=digest(folder/name)
    metrics=[];replayed={}
    with np.load(folder/'weights.npz',allow_pickle=False) as weights,np.load(folder/'scores.npz',allow_pickle=False) as saved:
        if set(weights.files)!=set(expected_targets):raise ValueError('Weight keys differ from successful selected targets')
        expected_keys={target+'_'+split for target in expected_targets for split in datasets}
        if set(saved.files)!=expected_keys:raise ValueError('Saved score arrays missing or unexpectedly added')
        if set(audit['summary'])!={target[2:] for target in expected_targets}:raise ValueError('Summary target keys mismatch')
        for target,receipt in expected_targets.items():
            for split,dataset in datasets.items():
                key=target+'_'+split;original=np.asarray(saved[key]);independent=dataset.score(weights[target])
                if original.dtype!=np.dtype('float64') or original.shape!=independent.shape or not np.isfinite(original).all():raise ValueError('Saved score dtype/shape/finiteness mismatch')
                difference=np.abs(independent-original);worst=int(np.argmax(difference))
                max_error=float(difference[worst])
                if max_error>ATOL_BITS_PER_WORD:raise AssertionError('Score difference exceeds tolerance: '+key+' '+str(max_error))
                stored=audit['summary'][target[2:]][split]
                total=math.fsum(float(x) for x in independent);mean=total/len(independent)
                if stored['words']!=len(independent):raise ValueError('Summary word count mismatch')
                if abs(mean-stored['mean_bits_per_word'])>ATOL_BITS_PER_WORD:raise AssertionError('Summary mean differs')
                if abs(total-stored['sum_bits'])>ATOL_BITS_PER_WORD*len(independent):raise AssertionError('Summary total differs')
                if split=='train':
                    excluding=mean-float(np.mean(dataset.identity_fees))
                    if abs(excluding-receipt['selected']['train_nll_bits_per_word_excluding_identity'])>ATOL_BITS_PER_WORD:raise AssertionError('Training NLL/identity fee accounting differs')
                metrics.append(dict(target_df=float(target[2:]),split=split,words=len(independent),
                                    prediction_events=sum(map(len,dataset.word_events)),unique_contexts=len(dataset.contexts),
                                    rare_identity_events=sum(dataset.rare_counts),identity_bits_per_event=dataset.identity_bits,
                                    max_absolute_error_bits=max_error,mean_absolute_error_bits=float(difference.mean()),
                                    worst_row_index=worst,replayed_mean_bits=mean,saved_mean_bits=stored['mean_bits_per_word'],
                                    replayed_sum_bits=total,saved_sum_bits=stored['sum_bits']))
                replayed[key]=independent
    np.savez_compressed(out/(job_id+'_replayed_scores.npz'),**replayed)
    return dict(id=job_id,author_status='completed',scores_replayed=True,passed=True,
                common=common,universe_size=len(universe),feature_count=train.F,nonreference_outputs=train.C,
                matched_targets=sorted(expected_targets),unmatched_targets=failed,arrays=metrics,
                replayed_array_count=len(metrics),replayed_score_count=sum(m['words'] for m in metrics))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--jobs',type=Path)
    parser.add_argument('--results',type=Path)
    parser.add_argument('--kind',choices=['all','synthetic','manuscript'],default='all')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=args.root.resolve();out=args.output.resolve()
    if out.exists():parser.error('Output must be a new directory. Preserve previous audits and failures.')
    out.mkdir(parents=True);reader=Reader();cache={};items=[];errors=[]
    report=dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=False,
                checker_sha256=digest(Path(__file__)),python_version=sys.version,numpy_version=np.__version__,
                absolute_tolerance_bits_per_word=ATOL_BITS_PER_WORD,relative_tolerance=0.0,requested_kind=args.kind,
                no_model_import=True,no_fitting_or_selection=True,scope='Saved selected-weight score replay only, CPU NumPy. No new samples or parameter choices. Existing manuscript evaluation splits are already exposed, not new blind data.')
    try:
        freeze_path=root/'freeze.json'
        if freeze_path.exists():
            freeze=reader.read(freeze_path)
            frozen_errors=[]
            for entry in freeze['files']:
                path=(root/entry['path']).resolve()
                if not path.is_relative_to(root):raise ValueError('Frozen path outside supplied root')
                actual=digest(path);reader.hashes[str(path)]=actual
                if actual!=entry['sha256']:frozen_errors.append(entry['path'])
            report['freeze_receipt_sha256']=digest(freeze_path)
            report['frozen_file_count']=len(freeze['files'])
            report['frozen_file_hash_mismatches']=frozen_errors
            if frozen_errors:raise ValueError('Frozen input/code hash mismatch: '+repr(frozen_errors))
        else:report['freeze_receipt_missing']=True
        jobs_path=(args.jobs or root/'jobs.json').resolve();results=(args.results or root/'results').resolve()
        jobs=reader.read(jobs_path)
        if len({j['id'] for j in jobs})!=len(jobs):raise ValueError('Duplicate job IDs')
        jobs=[j for j in jobs if args.kind=='all' or j['kind']==args.kind]
        if not jobs:raise ValueError('No selected jobs')
        report.update(jobs_path=str(jobs_path),results_path=str(results),selected_job_count=len(jobs))
        for job in jobs:
            try:item=check_job(root,results,job,out,reader,cache)
            except Exception as exc:
                item=dict(id=job['id'],passed=False,exception_type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
                errors.append(item)
            items.append(item);write(out/(job['id']+'_audit.json'),item)
        provenance=root/'input_provenance.json'
        if provenance.exists():
            p=reader.read(provenance)
            for entry in p['sources']:
                source=(root/entry['path']).resolve()
                if str(source) in reader.hashes and reader.hashes[str(source)]!=entry['sha256']:
                    errors.append(dict(input_hash_mismatch=entry['path']))
        changed=[path for path,expected in reader.hashes.items() if digest(Path(path))!=expected]
        if changed:errors.append(dict(files_changed_during_audit=changed))
        report.update(passed=not errors,jobs=items,input_and_result_sha256=reader.hashes,
                      all_read_files_unchanged=not changed,
                      verified_completed_jobs=sum(x.get('scores_replayed',False) and x['passed'] for x in items),
                      original_job_failures_preserved=[x['id'] for x in items if x.get('author_status')=='error_preserved'],
                      verified_arrays=sum(x.get('replayed_array_count',0) for x in items),
                      verified_word_scores=sum(x.get('replayed_score_count',0) for x in items),
                      max_absolute_error_bits=max([m['max_absolute_error_bits'] for x in items for m in x.get('arrays',[])]+[0.0]))
    except Exception as exc:errors.append(dict(exception_type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()))
    report['completed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();report['errors']=errors
    write(out/'errors.json',errors);write(out/'audit_report.json',report)
    write(out/'artifact_manifest.json',{str(p.relative_to(out)):digest(p) for p in sorted(out.iterdir()) if p.is_file()})
    print(json.dumps(dict(passed=report['passed'],output=str(out),verified_arrays=report.get('verified_arrays',0),errors=len(errors)),ensure_ascii=False))
    return 0 if report['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
