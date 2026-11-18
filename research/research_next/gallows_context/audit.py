# -*- coding: utf-8 -*-
"""Independent CPU NumPy event/word replay. No production model/analysis imports."""
from pathlib import Path
import argparse, collections, datetime, gzip, hashlib, json, math, re, sys, traceback
import numpy as np

ROOT = Path(__file__).resolve().parent
PRIOR = ROOT.parent / 'parameter_sharing'
EVENT_ATOL = 1e-10
WORD_ATOL = 1e-8
CORE_AXES = ('history','position','event','history_event','history_nearest','target')
PAIRS = ('f/k','f/p','f/t','k/p','k/t','p/t')
CASES = ('true_alias','non_alias','position_confound','frequency_confound','iid')


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    return h.hexdigest()


def write(path, data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


class Reader:
    def __init__(self):self.hashes={}
    def track(self,path):
        path=path.resolve();value=sha(path);old=self.hashes.get(str(path))
        if old is not None and old!=value:raise RuntimeError('File changed during audit: '+str(path))
        self.hashes[str(path)]=value
        return value
    def json(self,path):
        self.track(path)
        if path.suffix=='.gz':
            with gzip.open(path,'rt',encoding='utf-8') as f:
                return [json.loads(line) for line in f] if path.name.endswith('.jsonl.gz') else json.load(f)
        return json.loads(path.read_text(encoding='utf-8'))
    def npz(self,path):
        self.track(path)
        with np.load(path,allow_pickle=False) as archive:return {k:archive[k].copy() for k in archive.files}


def original_units(word, universe):
    if isinstance(word,list) and all(isinstance(s,str) for s in word):units=list(word)
    elif isinstance(word,str):
        units=[];position=0
        while position<len(word):
            token=re.match(r"@[0-9]{3};|[a-z']",word[position:])
            if token is None:raise ValueError('Unrecognized unit at original-string offset '+str(position))
            units.append(token.group());position+=len(token.group())
    else:raise TypeError('Expected original-unit list or exact original-unit string')
    if not units or any(s not in universe for s in units):raise ValueError('Empty word or unit outside original universe')
    return units


def expected_tasks():
    reused={'f/p':'FP','f/t':'FP_control1','k/t':'KT'}
    rows=[]
    for version in ('ZL','IT'):
        for pair in PAIRS:
            rows.append(dict(kind='manuscript',scope=version,pair=pair,version=version,
                             base=version+'_base',reused=version+'_'+reused[pair] if pair in reused else None))
    for seed in (2026111700,2026111701):
        for case in CASES:
            scope='s'+str(seed)+'_'+case
            for pair,label in [('a/b','AB'),('c/d','CD')]:
                rows.append(dict(kind='synthetic',scope=scope,pair=pair,seed=seed,case=case,
                                 base=scope+'_base',reused=scope+'_'+label))
    return rows


def task_name(task):return task['scope']+'_'+task['pair'].replace('/','')


def inputs(prior,task,reader):
    if task['kind']=='manuscript':
        universe=list("abcdefghijklmnopqrstuvwxyz'")+['@%03d;'%i for i in range(1000)]
        train_path=prior/'inputs'/(task['version']+'_train_dev.json.gz')
        source=reader.json(train_path)
        train=source['train']
        confirm=reader.json(prior/'inputs'/(task['version']+'_confirm.json.gz'))
        reserve=reader.json(prior/'inputs'/(task['version']+'_reserve.json.gz'))
        splits={'confirm':confirm,'reserve':reserve,'dev':source['dev'],'confirm_reserve':confirm+reserve}
    else:
        universe=list('abcdefgh')
        folder=prior/'synthetic_data'/('seed'+str(task['seed']))/task['case']
        train_path=folder/'train.jsonl.gz';train=reader.json(train_path)
        splits={'test':reader.json(folder/'test.jsonl.gz')}
    counts=collections.Counter(s for row in train for s in original_units(row['word'],set(universe)))
    common=sorted(s for s,n in counts.items() if n>=20)
    return train,common,universe,splits,train_path


class Events:
    """Exact ordered events with independent sparse feature construction."""
    def __init__(self, records, common, universe):
        self.records=records;self.common=tuple(common);self.universe=tuple(universe)
        if not records or len(set(common))!=len(common) or not set(common)<=set(universe):raise ValueError('Invalid dataset/alphabet')
        self.outputs=list(common)+(['<OTHER>'] if len(common)<len(universe) else [])
        self.hist=self.outputs+['<BOS>'];self.K=len(self.outputs);self.F=1+3*len(self.hist)+17
        output_ids={s:i for i,s in enumerate(self.outputs)};hist_ids={s:i for i,s in enumerate(self.hist)}
        self.rare_fee=math.log2(len(universe)-len(common)) if '<OTHER>' in output_ids else 0.
        self.words=[];self.contexts=[];context_id={};self.event_context=[];self.target=[]
        self.word_index=[];self.position=[];self.event_kind=[];self.target_group=[];self.identity=[]
        self.raw_histories=[];self.word_offsets=[0];common_set=set(common);universe_set=set(universe)
        for wi,row in enumerate(records):
            word=original_units(row['word'],universe_set);self.words.append(word)
            history=['<BOS>']*3
            for j in range(len(word)+1):
                key=(min(j,16),tuple(history))
                if key not in context_id:
                    context_id[key]=len(self.contexts);self.contexts.append(key)
                self.event_context.append(context_id[key]);self.word_index.append(wi);self.position.append(j)
                self.raw_histories.append(tuple(word[max(0,j-3):j]))
                if j==len(word):
                    self.target.append(-1);self.target_group.append('<EOS>');self.identity.append(0.0);self.event_kind.append('eos')
                else:
                    symbol=word[j] if word[j] in common_set else '<OTHER>'
                    self.target.append(output_ids[symbol]);self.target_group.append(symbol)
                    self.identity.append(self.rare_fee if symbol=='<OTHER>' else 0.)
                    self.event_kind.append('first' if j==0 else 'continuation')
                    history=history[1:]+[symbol]
            self.word_offsets.append(len(self.target))
        self.word_offsets=np.asarray(self.word_offsets,dtype=np.int64)
        self.event_context=np.asarray(self.event_context,dtype=np.int64)
        self.target=np.asarray(self.target,dtype=np.int64);self.word_index=np.asarray(self.word_index,dtype=np.int64)
        self.identity=np.asarray(self.identity,dtype=np.float64)
        sparse=[];first=[]
        for position,history in self.contexts:
            sparse.append([0,1+3*len(self.hist)+position]+[1+lag*len(self.hist)+hist_ids[s] for lag,s in enumerate(history)])
            first.append(position==0)
        self.features=np.asarray(sparse,dtype=np.int64);self.first=np.asarray(first,dtype=bool)
        assert np.array_equal(np.diff(self.word_offsets),np.asarray([len(w)+1 for w in self.words]))
        assert sum(s=='eos' for s in self.event_kind)==len(records)
        assert sum(s=='first' for s in self.event_kind)==len(records)

    def score(self,b):
        b=np.asarray(b)
        if b.dtype!=np.dtype('float64') or b.shape!=(self.F*self.K,) or not np.isfinite(b).all():raise ValueError('Weight dtype/dimension/finiteness mismatch')
        coef=b.reshape(self.F,self.K)
        logits=np.sum(coef[self.features],axis=1,dtype=np.float64)
        maximum=np.max(logits,axis=1);maximum[~self.first]=np.maximum(maximum[~self.first],0.)
        denom=np.exp(logits-maximum[:,None]).sum(axis=1,dtype=np.float64)
        denom[~self.first]+=np.exp(-maximum[~self.first])
        normalizer=maximum+np.log(denom)
        selected=np.zeros(len(self.target),dtype=np.float64);non_eos=self.target>=0
        selected[non_eos]=logits[self.event_context[non_eos],self.target[non_eos]]
        event_bits=(normalizer[self.event_context]-selected)/math.log(2)+self.identity
        if not np.isfinite(event_bits).all():raise ValueError('Nonfinite original-event cost')
        return event_bits

    def words_from_events(self,values):
        return np.asarray([math.fsum(float(v) for v in values[a:b]) for a,b in zip(self.word_offsets,self.word_offsets[1:])],dtype=np.float64)

    def axes(self,pair):
        members=set(pair.split('/'));nearest=[]
        for history in self.raw_histories:
            nearest.append(next((str(distance) for distance,symbol in enumerate(reversed(history),1) if symbol in members),'absent'))
        contains=['absent' if n=='absent' else 'contains' for n in nearest]
        result={'history':contains,'history_nearest':nearest,
                'position':[str(j) if j<16 else '16+' for j in self.position],
                'event':self.event_kind,'target':self.target_group,
                'history_event':[a+'|'+b for a,b in zip(contains,self.event_kind)]}
        assert 'contains|first' not in result['history_event']
        return {key:np.asarray(values) for key,values in result.items()}

    def aggregate(self,costs,mask=None):
        if mask is None:mask=np.ones(len(self.target),dtype=bool)
        ids=np.flatnonzero(mask);word_ids=np.unique(self.word_index[ids]);events=len(ids)
        sums={name:math.fsum(float(costs[name][i]) for i in ids) for name in ('base','fixed','matched')}
        gains={name:math.fsum(float(costs[a][i]-costs[b][i]) for i in ids) for name,a,b in
               [('total','base','matched'),('fixed','base','fixed'),('retune','fixed','matched')]}
        pages={self.records[int(i)].get('folio') for i in word_ids}-{None,''}
        leaves={self.records[int(i)].get('leaf') for i in word_ids}-{None,''}
        return dict(events=events,words=len(word_ids),pages=len(pages),leaves=len(leaves),cost_sums=sums,gain_sums=gains,
                    gain_per_event={k:v/events if events else None for k,v in gains.items()},
                    gain_per_word={k:v/len(word_ids) if len(word_ids) else None for k,v in gains.items()})


def assert_close(actual,expected,tolerance,label):
    a=np.asarray(actual);b=np.asarray(expected)
    if a.shape!=b.shape:raise AssertionError(label+': shape '+str(a.shape)+' != '+str(b.shape))
    if not np.isfinite(a).all() or not np.isfinite(b).all():raise AssertionError(label+': nonfinite')
    delta=float(np.max(np.abs(a-b))) if a.size else 0.
    if delta>tolerance:raise AssertionError(label+': max difference '+str(delta))
    return delta


# The results.json adapter and command entry point are added after its exact schema
# is supplied. No production imports, fitting or evaluation has run from this file.


def selftest():
    """Fixed artificial words only; does not read source packages or fitted results."""
    rows=[dict(word=w,folio='toy'+str(i//2),leaf='toy_leaf') for i,w in enumerate(
        [['a'],['x','b'],['a','b','a','x'],['a']*17+['y']])]
    dataset=Events(rows,['a','b'],['a','b','x','y'])
    values={};maximum=0.
    for name,constant in [('base',0.),('fixed',.1),('matched',-.05)]:
        values[name]=dataset.score(np.full(dataset.F*dataset.K,constant,dtype=np.float64))
        logits=5*constant;normalizer=math.log(1+3*math.exp(logits))
        analytic=[]
        for row in rows:
            word=row['word']
            for j in range(len(word)+1):
                if j==len(word):cost=normalizer/math.log(2)
                elif j==0:cost=math.log2(3)+(word[j] not in ['a','b'])
                else:cost=(normalizer-logits)/math.log(2)+(word[j] not in ['a','b'])
                analytic.append(cost)
        maximum=max(maximum,assert_close(values[name],analytic,1e-12,'constant-logit toy'))
    axes=dataset.axes('a/b')
    assert 'contains|first' not in set(axes['history_event'])
    assert all(axes['history'][i]=='absent' for i in range(len(dataset.target)) if dataset.event_kind[i]=='first')
    assert axes['history_nearest'][dataset.word_offsets[3]-1]=='2'
    assert '16+' in axes['position']
    whole=dataset.aggregate(values)
    for axis,labels in axes.items():
        grouped=[dataset.aggregate(values,labels==label) for label in sorted(set(labels))]
        assert sum(row['events'] for row in grouped)==whole['events']
        for term in ('total','fixed','retune'):
            assert abs(math.fsum(row['gain_sums'][term] for row in grouped)-whole['gain_sums'][term])<1e-12
    identity_error=float(np.max(np.abs((values['base']-values['fixed'])+(values['fixed']-values['matched'])-(values['base']-values['matched']))))
    assert identity_error<1e-12
    return dict(passed=True,scope='artificial scalar-cost and context partition checks only',
                words=len(rows),events=len(dataset.target),core_axes=len(axes),
                max_event_error=maximum,max_decomposition_error=identity_error)


class Checks:
    def __init__(self):
        self.errors=[];self.max_errors=collections.defaultdict(float)
        self.counts=collections.Counter();self.comparisons=[]
    def require(self,condition,label):
        if not condition:self.errors.append(dict(check=label,error='requirement failed'))
    def compare(self,actual,expected,tolerance,category,label):
        self.counts[category+'_arrays']+=1
        self.counts[category+'_values']+=np.asarray(expected).size
        try:
            error=assert_close(actual,expected,tolerance,label)
            self.max_errors[category]=max(self.max_errors[category],error)
            return error
        except Exception as exc:
            self.errors.append(dict(check=label,error=str(exc)));return None
    def exact(self,actual,expected,label):
        self.require(actual==expected,label)


def row_key(row,synthetic=False):
    fields=('seed','case','df','pair','split') if synthetic else ('version','df','pair','split')
    return tuple(row[k] for k in fields)


def index_rows(rows,synthetic,context,check):
    result={}
    for row in rows:
        key=row_key(row,synthetic)+(tuple(row[k] for k in ('axis','group')) if context else ())
        check.require(key not in result,'duplicate results row '+str(key))
        result[key]=row
    return result


def compare_metrics(row,stats,word_mean,check,label):
    for field in ('events','words','pages','leaves'):
        check.exact(row[field],stats[field],label+' '+field)
    for public,internal in [('matched','total'),('fixed','fixed'),('retune','retune')]:
        check.compare(row[public+'_total'],stats['gain_sums'][internal],
                      EVENT_ATOL*max(1,stats['events']),'group_sum',label+' '+public+'_total')
        expected=stats['gain_per_word' if word_mean else 'gain_per_event'][internal]
        if expected is None:check.require(row[public] is None,label+' empty mean must be null')
        else:check.compare(row[public],expected,WORD_ATOL if word_mean else EVENT_ATOL,
                           'word_mean' if word_mean else 'event_mean',label+' '+public)
    check.compare(row['matched_total'],row['fixed_total']+row['retune_total'],
                  EVENT_ATOL*max(1,stats['events']),'reported_decomposition',label+' reported decomposition')


def check_freeze(root,reader,check):
    receipts={}
    research=root.parent.parent.resolve()
    for name in ('freeze.json','scoring_freeze.json'):
        receipt=reader.json(root/name);receipts[name]=receipt
        for relative,expected in receipt['files'].items():
            target=(root/relative).resolve()
            check.require(target==research or research in target.parents,'freeze path inside research '+relative)
            actual=reader.track(target)
            check.exact(actual,expected,name+' sha '+relative)
    check.exact(receipts['freeze.json']['tasks'],expected_tasks(),'32 predeclared task definitions')
    return receipts


def source_selected(prior,job,df,reader):
    audit=reader.json(prior/'results'/job/'audit.json')
    targets=[row for row in audit['targets'] if row['target']==df]
    if len(targets)!=1 or not targets[0]['matched']:raise ValueError('Old fit missing selected target')
    weights=reader.npz(prior/'results'/job/'weights.npz')['df'+str(df)]
    return targets[0]['selected'],weights


def receipt_check(task,receipt,weights,train,common,universe,train_path,prior,reader,check):
    label=task_name(task)
    check.exact(receipt['task'],task,label+' task')
    check.exact(receipt['train_words'],len(train),label+' training words')
    check.exact(receipt['common'],common,label+' training-only COMMON>=20')
    check.exact(receipt['universe_size'],len(universe),label+' original universe')
    check.exact(receipt['train_sha256'],reader.track(train_path),label+' training hash')
    check.exact([fit['df'] for fit in receipt['fits']],[50,150],label+' DF targets')
    check.exact(set(weights),{name+str(df) for name in ('base','fixed','matched') for df in (50,150)},label+' weight keys')
    for fit in receipt['fits']:
        df=fit['df'];prefix=label+' df'+str(df)
        for name in ('base','fixed','matched'):
            info=fit[name]
            check.require(info is not None and info['status']=='converged',prefix+' '+name+' convergence')
            if info is None:continue
            check.require(info['lambda']>0 and math.isfinite(info['df']),prefix+' '+name+' finite lambda/DF')
            check.require(info['gradient_inf']<=1e-8 and info['objective_gap_upper_bound']<=1e-8,
                          prefix+' '+name+' both convergence criteria')
        check.exact(fit['fixed']['lambda'],fit['base']['lambda'],prefix+' fixed uses ordinary lambda')
        for name in ('base','matched'):
            check.require(abs(fit[name]['df']-df)<=max(.1,.002*df),prefix+' '+name+' DF tolerance')
        for name,job in [('base',task['base']),('matched',task['reused'])]:
            if job is None:continue
            old_info,old_weight=source_selected(prior,job,df,reader)
            check.exact(fit[name],old_info,prefix+' '+name+' exact prior selected receipt')
            check.require(np.array_equal(weights[name+str(df)],old_weight),prefix+' '+name+' bitwise source weights')
            check.counts['exact_reused_weight_arrays']+=1


def prior_scores(prior,task,df,split,field,reader):
    job=task['base'] if field=='base' else task['reused']
    if job is None:return None
    archive=reader.npz(prior/'results'/job/'scores.npz')
    if split=='confirm_reserve':
        return np.concatenate([archive['df'+str(df)+'_confirm'],archive['df'+str(df)+'_reserve']])
    return archive['df'+str(df)+'_'+split]


def verify_sources(root,run,results,reader,check):
    research=root.parent.parent
    mappings={'freeze.json':root/'freeze.json','score.py':root/'score.py','metadata.py':root/'metadata.py',
              'ZL3b-n.txt':research/'sources/ZL3b-n.txt','IT2a-n.txt':research/'sources/IT2a-n.txt',
              'synthetic oracle':root.parent/'parameter_sharing/synthetic_data/validation.json'}
    check.exact(set(results['source_hashes']),set(mappings),'result source hash keys')
    for key,path in mappings.items():check.exact(results['source_hashes'][key],reader.track(path),'result source hash '+key)
    attempts=[]
    for path in sorted((root/'attempts').rglob('*')):
        if path.is_file():
            reader.track(path)
            if path.suffix=='.json':
                data=reader.json(path)
                attempts.append(dict(path=str(path.relative_to(root)),sha256=reader.hashes[str(path.resolve())],
                                     fits=[dict(df=f['df'],matched_available=f.get('matched') is not None,
                                                fixed_status=f.get('fixed',{}).get('status')) for f in data.get('fits',[])]))
    return attempts


def replay(root,prior,run,reader,check):
    check_freeze(root,reader,check)
    results=reader.json(run/'results.json')
    check.exact(results['schema_version'],1,'results schema')
    check.exact(results['status'],'complete','results complete')
    attempts=verify_sources(root,run,results,reader,check)
    tables={};seen={};skipped_metadata=collections.Counter()
    for name,synthetic,context in [('pairs',False,False),('context',False,True),('synthetic',True,False),('synthetic_context',True,True)]:
        tables[name]=index_rows(results[name],synthetic,context,check);seen[name]=set()
        if context:
            for row in results[name]:
                if row['axis'] not in CORE_AXES:skipped_metadata[row['axis']]+=1
    old_check_index={}
    for row in results['replay_check']:
        key=row_key(row,'seed' in row)+(row['model'],)
        check.require(key not in old_check_index,'duplicate old-score replay receipt '+str(key))
        old_check_index[key]=row
    seen_old=set();summaries=[];oracle=reader.json(prior/'synthetic_data/validation.json')
    hard_oracles={(r['seed'],r['case']):r['expected']['hard_extra_bits_per_word'] for r in oracle['results']}
    for task in expected_tasks():
        stem=task_name(task)
        try:
            train,common,universe,splits,train_path=inputs(prior,task,reader)
            receipt=reader.json(root/'fits'/(stem+'.json'));weights=reader.npz(root/'fits'/(stem+'.npz'))
            receipt_check(task,receipt,weights,train,common,universe,train_path,prior,reader,check)
            synthetic=task['kind']=='synthetic';main_name='synthetic' if synthetic else 'pairs';context_name='synthetic_context' if synthetic else 'context'
            designs={name:Events(rows,common,universe) for name,rows in splits.items()}
            stored={}
            for fit in receipt['fits']:
                df=fit['df']
                for split,dataset in designs.items():
                    identity=dict(df=df,pair=task['pair'],split=split)
                    identity.update({k:task[k] for k in (('seed','case') if synthetic else ('version',))})
                    key=row_key(identity,synthetic);label=stem+' df'+str(df)+' '+split
                    costs={name:dataset.score(weights[name+str(df)]) for name in ('base','fixed','matched')}
                    check.counts['reconstructed_event_arrays']+=3
                    check.counts['reconstructed_event_costs']+=3*len(dataset.target)
                    words={name:dataset.words_from_events(value) for name,value in costs.items()}
                    check.counts['reconstructed_word_arrays']+=3
                    check.counts['reconstructed_word_costs']+=3*len(dataset.records)
                    check.compare(costs['base']-costs['matched'],(costs['base']-costs['fixed'])+(costs['fixed']-costs['matched']),
                                  EVENT_ATOL,'event_decomposition',label+' event decomposition')
                    if synthetic:
                        saved=reader.npz(run/'word_costs'/(stem+'_df'+str(df)+'.npz'))
                        check.exact(set(saved),{'base','fixed','matched'},label+' saved word keys')
                        for name in costs:check.compare(saved[name],words[name],WORD_ATOL,'saved_word',label+' '+name+' word array')
                    elif split!='confirm_reserve':
                        saved=reader.npz(run/'events'/(stem+'_df'+str(df)+'_'+split+'.npz'))
                        check.exact(set(saved),{'word_offsets','base','fixed','matched'},label+' saved event keys')
                        check.require(np.issubdtype(saved['word_offsets'].dtype,np.integer),label+' integer offsets')
                        check.require(np.array_equal(saved['word_offsets'],dataset.word_offsets),label+' exact original-event offsets')
                        for name in costs:check.compare(saved[name],costs[name],EVENT_ATOL,'saved_event',label+' '+name+' event array')
                        stored[df,split]=saved
                    else:
                        first,second=stored[df,'confirm'],stored[df,'reserve']
                        joined=np.concatenate([first['word_offsets'],second['word_offsets'][1:]+first['word_offsets'][-1]])
                        check.require(np.array_equal(joined,dataset.word_offsets),label+' confirm then reserve offsets')
                        for name in costs:
                            check.compare(np.concatenate([first[name],second[name]]),costs[name],EVENT_ATOL,
                                          'combined_event',label+' '+name+' confirm then reserve')
                    for field in ('base','matched'):
                        old=prior_scores(prior,task,df,split,field,reader)
                        if old is None:continue
                        error=check.compare(words[field],old,WORD_ATOL,'prior_word',label+' '+field+' prior word array')
                        if split!='confirm_reserve':
                            rk=key+(field,);seen_old.add(rk)
                            check.require(rk in old_check_index,label+' producer old-score receipt exists')
                            if rk in old_check_index:
                                check.require(0<=old_check_index[rk]['max_error']<1e-10,label+' producer old-score tolerance')
                                # Independent floating-point summation can give a different last-bit maximum.
                                check.compare(old_check_index[rk]['max_error'],error,WORD_ATOL,
                                              'old_receipt_error',label+' producer vs independent old-score max')
                    stats=dataset.aggregate(costs)
                    row=tables[main_name].get(key);check.require(row is not None,label+' main row present')
                    if row is not None:
                        seen[main_name].add(key);compare_metrics(row,stats,True,check,label)
                        fit_fields={'base_lambda':fit['base']['lambda'],'fused_lambda':fit['matched']['lambda'],
                                    'base_df':fit['base']['df'],'fixed_df':fit['fixed']['df'],'matched_df':fit['matched']['df']}
                        for field,value in fit_fields.items():check.exact(row[field],value,label+' '+field)
                        if synthetic:
                            check.exact(row['oracle_hard_penalty'],hard_oracles[task['seed'],task['case']][task['pair'].replace('/','')],label+' saved hard-oracle scalar')
                        if split=='confirm_reserve':
                            remaining=[]
                            leaf_by_word=np.asarray([r['leaf'] for r in dataset.records])
                            gains=words['base']-words['matched']
                            for leaf in sorted(set(leaf_by_word)):
                                kept=gains[leaf_by_word!=leaf]
                                remaining.append(math.fsum(float(g) for g in kept)/len(kept))
                            check.compare(row['matched_drop_one_leaf_range'],[min(remaining),max(remaining)],WORD_ATOL,
                                          'drop_one_leaf',label+' fixed-model remaining-word means')
                    axes=dataset.axes(task['pair'])
                    for axis,labels in axes.items():
                        parts=[]
                        for group in sorted(set(labels)):
                            group_stats=dataset.aggregate(costs,labels==group);parts.append(group_stats)
                            if synthetic and axis!='history':continue
                            gkey=key+(axis,group);grow=tables[context_name].get(gkey)
                            check.require(grow is not None,label+' context '+axis+' '+group+' present')
                            if grow is not None:
                                seen[context_name].add(gkey)
                                compare_metrics(grow,group_stats,False,check,label+' '+axis+' '+group)
                        check.exact(sum(part['events'] for part in parts),stats['events'],label+' '+axis+' event partition')
                        for term in ('total','fixed','retune'):
                            check.compare(math.fsum(part['gain_sums'][term] for part in parts),stats['gain_sums'][term],
                                          EVENT_ATOL*stats['events'],'axis_partition',label+' '+axis+' '+term)
                        check.counts['core_axis_partitions']+=1
                    summaries.append(dict(identity,events=stats['events'],words=stats['words'],pages=stats['pages'],leaves=stats['leaves'],
                                          cost_sums=stats['cost_sums'],gain_sums=stats['gain_sums'],gain_per_word=stats['gain_per_word']))
                check.counts['task_df_comparisons']+=1
            check.counts['tasks']+=1
            print(stem+' audited',flush=True)
        except Exception as exc:
            check.errors.append(dict(check=stem,error=str(exc),traceback=traceback.format_exc()))
    for name,table in tables.items():
        expected={key for key,row in table.items() if name not in ('context','synthetic_context') or row['axis'] in CORE_AXES}
        check.exact(seen[name],expected,'all saved '+name+' rows accounted for')
    check.exact(seen_old,set(old_check_index),'all producer old-score replay receipts accounted for')
    check.exact(check.counts['tasks'],32,'all 32 tasks completed')
    check.exact(check.counts['task_df_comparisons'],64,'all 64 task DF comparisons completed')
    check.exact(len(tables['pairs']),96,'96 manuscript comparison rows')
    check.exact(len(tables['synthetic']),40,'40 synthetic comparison rows')
    return dict(row_counts={name:len(table) for name,table in tables.items()},
                audited_row_counts={name:len(value) for name,value in seen.items()},
                metadata_rows_not_independently_annotated=dict(skipped_metadata),attempts=attempts,summaries=summaries)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--prior',type=Path,default=PRIOR)
    parser.add_argument('--run',type=Path,help='Saved score output, containing results.json/events/word_costs')
    parser.add_argument('--output',type=Path,help='New audit output directory; existing paths are rejected')
    parser.add_argument('--selftest',action='store_true',help='Run artificial checks without reading fitted data')
    args=parser.parse_args()
    if args.selftest:
        print(json.dumps(selftest(),indent=2));return 0
    if args.run is None or args.output is None:parser.error('--run and --output are required except with --selftest')
    args.output.mkdir(parents=True,exist_ok=False)
    reader=Reader();check=Checks();body={};started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    reader.track(Path(__file__).resolve())
    try:
        toy=selftest()
        body=replay(args.root.resolve(),args.prior.resolve(),args.run.resolve(),reader,check)
    except Exception as exc:
        toy=None;check.errors.append(dict(check='top-level replay',error=str(exc),traceback=traceback.format_exc()))
    # Verify that even already-read source files did not change during the pass.
    for name,expected in list(reader.hashes.items()):
        try:check.exact(sha(Path(name)),expected,'input stable throughout audit '+name)
        except Exception as exc:check.errors.append(dict(check='input final hash '+name,error=str(exc)))
    report=dict(passed=not check.errors,started_utc=started,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                python=sys.version,numpy=np.__version__,command=sys.argv,toy=toy,counts=dict(check.counts),
                max_errors=dict(check.max_errors),tolerances=dict(event_absolute=EVENT_ATOL,word_absolute=WORD_ATOL,
                sum_absolute='event_absolute * event_count'),**body)
    report['scope']=[
        'Independent CPU NumPy evaluation of fixed stored weights; no fit/model/score imports and no new training.',
        'Original-unit plus EOS probabilities, first-step EOS mask, 3 history slots, absolute position, OTHER identity fees.',
        'Manuscript 6 core context axes; synthetic published history axis and internal six-axis partitions.',
        'Saved event and full-word arrays, exact reused weights, fixed lambda, selected receipts, source hashes, prior saved word costs.',
        'Fixed-model leave-one-evaluation-leaf-out remaining-word mean range; not refit, confidence interval, or causal estimate.',
        'Extra metadata annotations are not independently reassigned by this auditor. No post-result fourth model is included.',
        'Convergence and DF values are checked against receipts; Hessians/optimization are not recomputed by this score audit.',
        'Arithmetic agreement does not show identifiability, language, glyph equivalence, semantic content, or decipherment.']
    write(args.output/'audit_report.json',report);write(args.output/'errors.json',check.errors)
    input_hashes=[]
    for filename,value in sorted(reader.hashes.items()):
        path=Path(filename)
        if args.run.resolve() in path.parents:label='run/'+str(path.relative_to(args.run.resolve()))
        elif args.root.resolve().parent.parent in path.parents:label='research/'+str(path.relative_to(args.root.resolve().parent.parent))
        else:label=str(path)
        input_hashes.append(dict(path=label,sha256=value,bytes=path.stat().st_size))
    write(args.output/'inputs.json',input_hashes)
    text='独立逐事件数值审核：'+('通过' if not check.errors else '未通过')+'。\n'
    text+='只用 CPU NumPy 和保存权重，不重训、不导入原模型或评分函数。完整词包括原单位、EOS 及 OTHER 身份费。\n'
    text+='主表按完整词次；上下文按预测事件。每轴事件互斥，涉及词数可跨组重复。合成公开分组只核对 history 轴。\n'
    text+='数值一致不代表别名、语言或语义鉴定；固定 λ 与调 λ 的分解依赖比较路径，非因果归因。\n'
    text+='未独立重赋书手等辅助标注，未复算 Hessian/优化过程；结果后新增 D 模型不在本次范围。\n'
    text+='统计：'+json.dumps(dict(check.counts),ensure_ascii=False)+'\n最大绝对误差：'+json.dumps(dict(check.max_errors),ensure_ascii=False)+'\n'
    text+='失败数：'+str(len(check.errors))+'；详见 errors.json。\n'
    (args.output/'audit_report.txt').write_text(text,encoding='utf-8')
    manifest=[dict(path=path.name,sha256=sha(path),bytes=path.stat().st_size) for path in sorted(args.output.iterdir()) if path.is_file()]
    manifest.append(dict(path='audit.py',sha256=sha(Path(__file__).resolve()),bytes=Path(__file__).stat().st_size))
    write(args.output/'artifact_manifest.json',dict(files=manifest))
    print(json.dumps(dict(passed=report['passed'],errors=len(check.errors),counts=report['counts'],max_errors=report['max_errors']),indent=2))
    return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
