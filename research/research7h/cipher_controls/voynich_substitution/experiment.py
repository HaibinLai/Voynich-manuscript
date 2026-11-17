# -*- coding: utf-8 -*-
"""Frozen fixed-key transfer experiment. No reserved pages are scored or exposed."""
from pathlib import Path
from collections import Counter,defaultdict
import json,sys,hashlib,subprocess,datetime,time,random,argparse,math
import numpy as np
ROOT=Path(__file__).resolve().parent
CONTROL=ROOT.parent
RESEARCH=CONTROL.parent
sys.path.insert(0,str(CONTROL))
from benchmark import key_for,encode,plain_words,SOURCES
sys.path.insert(0,str(RESEARCH))
from corpus import load,units
SEED=2026111704
LANGS=['english','latin'];MODES=['ordered','bag'];REPS=['eva','merged'];NULL_N={'eva':199,'merged':39}
LETTERS='abcdefghijklmnopqrstuvwxyz'

def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n');tmp.replace(path)
def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def safe_load(splits):
    assert splits and set(splits)<={'train','legacy','dev','confirm'}
    return load(splits=list(splits))
def impl():
    model_hashes={f'model_{la}_{mo}':sha(CONTROL/'models'/f'{la}_{mo}.bin') for la in LANGS for mo in MODES}
    return {**model_hashes,'experiment.py':sha(ROOT/'experiment.py'),'solver_normalized.cpp':sha(ROOT/'solver_normalized.cpp'),'protocol.txt':sha(ROOT/'protocol.txt'),'corpus.py':sha(RESEARCH/'corpus.py'),'split_manifest.json':sha(RESEARCH/'split_manifest.json'),'ZL3b-n.txt':sha(RESEARCH.parent/'sources/ZL3b-n.txt')}

def normalize(pages,rep,inventory):
    table={u:LETTERS[i] for i,u in enumerate(inventory)};out=[];totals=Counter()
    for p in pages:
        lines=[];counts=Counter()
        for line in p['lines']:
            toks=[]
            for w in line['tokens']:
                counts['all_slots']+=1
                if w is None:counts['source_missing_slots']+=1;toks.append(None);continue
                uu=units(w,rep);counts['source_known_tokens']+=1;counts['source_known_units']+=len(uu)
                if any(u not in table for u in uu):counts['inventory_excluded_tokens']+=1;counts['inventory_excluded_units']+=len(uu);toks.append(None)
                else:
                    toks.append(''.join(table[u] for u in uu));counts['retained_tokens']+=1;counts['retained_units']+=len(uu)
            lines.append({**line,'tokens':toks})
        out.append({**p,'lines':lines,'coverage':dict(counts)});totals.update(counts)
    return out,dict(totals)
def words(pages):return [w for p in pages for l in p['lines'] for w in l['tokens'] if w]
def prepare():
    pages=safe_load(['train','legacy']);allinfo={}
    for rep in REPS:
        count=Counter(u for p in pages for l in p['lines'] for w in l['tokens'] if w for u in units(w,rep))
        eligible={u:n for u,n in count.items() if '@' not in u and "'" not in u}
        inventory=list(LETTERS) if rep=='eva' else sorted(sorted(eligible,key=lambda u:(-eligible[u],u))[:26])
        normalized,coverage=normalize(pages,rep,inventory)
        assert len(inventory)<=26
        allinfo[rep]={'inventory':inventory,'unit_to_solver_code':{u:LETTERS[i] for i,u in enumerate(inventory)},'train_unit_counts':dict(count),'coverage':coverage,'training_pages':len(pages)}
        save(ROOT/'data'/f'train_{rep}.json',normalized)
    save(ROOT/'inventory.json',allinfo);save(ROOT/'implementation_receipt.json',{'created_utc':utc(),'hashes':impl(),'reference_models':{f'{la}_{mo}':sha(CONTROL/'models'/f'{la}_{mo}.bin') for la in LANGS for mo in MODES}})
    print(json.dumps({'prepared':True,'coverage':{r:allinfo[r]['coverage'] for r in REPS}},ensure_ascii=False),flush=True)
def role(line,i):
    if i==0:return 'paragraph_first' if line['paragraph_start'] else 'line_first'
    if i==len(line['tokens'])-1:return 'line_last'
    return 'interior'
def null_pages(pages,rep,replicate):
    output=[];stats=Counter()
    for page in pages:
        groups=defaultdict(list);newlines=[{**l,'tokens':list(l['tokens'])} for l in page['lines']]
        for li,line in enumerate(page['lines']):
            for ti,w in enumerate(line['tokens']):
                if w:groups[(len(w),role(line,ti))].append((li,ti,w))
        seed=int.from_bytes(hashlib.sha256(f'{SEED}|{rep}|{replicate}|{page["folio"]}'.encode()).digest()[:8],'big');rng=np.random.default_rng(seed)
        before=Counter();after=Counter()
        for key,group in sorted(groups.items()):
            n=len(group);length=key[0];original=[x[2] for x in group];rewritten=['']*n
            stats['buckets']+=1;stats['tokens']+=n;stats['units']+=n*length
            if n==1:stats['singleton_buckets']+=1;stats['tokens_in_singleton_buckets']+=1
            else:stats['tokens_in_multi_token_buckets']+=n
            if length<=2:stats['tokens_with_only_one_block']+=n
            for start in range(0,length,2):
                blocks=[w[start:start+2] for w in original];perm=rng.permutation(n)
                newblocks=[blocks[int(i)] for i in perm]
                assert Counter(blocks)==Counter(newblocks)
                for i,b in enumerate(newblocks):rewritten[i]+=b
            for (li,ti,w),v in zip(group,rewritten):
                before.update(w);after.update(v)
                stats['changed_tokens']+=int(w!=v);stats['changed_units']+=sum(a!=b for a,b in zip(w,v));newlines[li]['tokens'][ti]=v
        assert before==after
        assert [[w is None for w in l['tokens']] for l in newlines]==[[w is None for w in l['tokens']] for l in page['lines']]
        output.append({**page,'lines':newlines})
    for name,num,den in [('changed_token_fraction','changed_tokens','tokens'),('changed_unit_fraction','changed_units','units'),('singleton_token_fraction','tokens_in_singleton_buckets','tokens'),('single_block_token_fraction','tokens_with_only_one_block','tokens')]:stats[name]=stats[num]/stats[den] if stats[den] else 0.
    return output,dict(stats)

def model(lang,mode):return np.fromfile(CONTROL/'models'/f'{lang}_{mode}.bin',dtype=np.float64).reshape((27,)*4)
def raw_score(ww,key,lm,bag=False):
    out=0.;keyints=[ord(x)-97 for x in key]
    for w,count in Counter(ww).items():
        vals=[keyints[ord(c)-97] for c in w]
        if bag:vals.sort()
        s=[26]*3+vals+[26]
        out+=count*sum(lm[tuple(s[i-3:i+1])] for i in range(3,len(s)))
    return float(out)
def run_search(ww,lang,mode,seed):
    work=ROOT/'work';work.mkdir(exist_ok=True);inp=work/'solver_input.txt';inp.write_text(' '.join(ww)+'\n')
    cmd=[str(ROOT/'solver_normalized'),str(CONTROL/'models'/f'{lang}_{mode}.bin'),str(inp),str(CONTROL/'models'/f'{lang}_frequency.txt'),mode,'8','20000',str(seed)]
    run=json.loads(subprocess.check_output(cmd,text=True));scale=400/len(ww);actual=raw_score(ww,run['mapping'],model(lang,mode),mode=='bag')
    assert abs(actual*scale-run['score'])<1e-6,(actual*scale,run['score'])
    return {**run,'word_weight_scale':scale,'unnormalized_training_score':actual,'training_tokens':len(ww),'training_units':sum(map(len,ww)),'input_sha256':sha(inp),'solver_inputs_have_truth':False}
def calibrate():
    assert impl()==read(ROOT/'implementation_receipt.json')['hashes']
    n=max(x['coverage']['retained_tokens'] for x in read(ROOT/'inventory.json').values());result=[]
    for i,lang in enumerate(LANGS):
        allw=plain_words(SOURCES[lang]);start={'english':8000,'latin':6000}[lang];plaintext=allw[start:start+n]
        assert len(plaintext)==n
        enc,truth=key_for(SEED+500+i);cipher=encode(plaintext,enc)
        for mode in MODES:
            run=run_search(cipher,lang,mode,SEED+600+i)
            c=Counter(''.join(cipher));acc=sum(n for ch,n in c.items() if run['mapping'][ord(ch)-97]==truth[ord(ch)-97])/sum(c.values())
            result.append({**run,'language':lang,'mode':mode,'known_key_character_accuracy':acc,'truth_decryption':truth,'source_token_range':[start,start+n],'criterion_passed':acc>=.99})
            print(json.dumps({'calibration':lang,'mode':mode,'tokens':n,'accuracy':acc,'seconds':run['seconds']},ensure_ascii=False),flush=True)
    save(ROOT/'scale_calibration.json',{'created_utc':utc(),'results':result,'passed':all(x['criterion_passed'] for x in result),'purpose':'Search-scale check, not new cross-book language validation.'})

def case_path(rep,lang,mode,kind,replicate=0,search_index=0):
    suffix=f'real_s{search_index}' if kind=='real' else f'null_{replicate:03d}'
    return ROOT/'keys'/f'{rep}_{lang}_{mode}_{suffix}.json'
def fit_one(pages,rep,lang,mode,kind,replicate=0,search_index=0,nullstats=None):
    path=case_path(rep,lang,mode,kind,replicate,search_index)
    signature=read(ROOT/'implementation_receipt.json')['hashes']
    if path.exists():
        old=read(path);assert old['implementation_hashes']==signature;return old,False
    ci=REPS.index(rep)*4+LANGS.index(lang)*2+MODES.index(mode);seed=SEED+10000+ci*100+search_index
    run=run_search(words(pages),lang,mode,seed)
    value={**run,'representation':rep,'language':lang,'mode':mode,'kind':kind,'replicate':replicate if kind=='null' else None,'search_index':search_index,'null_stats':nullstats,'created_utc':utc(),'implementation_hashes':signature}
    save(path,value);return value,True

def fit():
    assert impl()==read(ROOT/'implementation_receipt.json')['hashes'];assert read(ROOT/'scale_calibration.json')['passed']
    inv=read(ROOT/'inventory.json');start=time.time();total=24+sum(4*n for n in NULL_N.values());completed=0
    for rep in REPS:
        train=read(ROOT/'data'/f'train_{rep}.json')
        for lang in LANGS:
            for mode in MODES:
                for si in range(3):
                    value,new=fit_one(train,rep,lang,mode,'real',search_index=si);completed+=1
                    if new:print(json.dumps({'completed':completed,'total':total,'rep':rep,'model':lang+'_'+mode,'case':'real','seed_index':si,'seconds':value['seconds'],'score':value['unnormalized_training_score']/value['training_units']},ensure_ascii=False),flush=True)
                    save(ROOT/'progress.json',{'status':'fitting','completed':completed,'total':total,'updated_utc':utc(),'elapsed_this_invocation_seconds':time.time()-start})
        for b in range(NULL_N[rep]):
            pages,ns=null_pages(train,rep,b)
            for lang in LANGS:
                for mode in MODES:
                    if datetime.datetime.now(datetime.timezone.utc).isoformat()[:19]>='2026-11-17T16:40:25':
                        save(ROOT/'progress.json',{'status':'incomplete_at_deadline','completed':completed,'total':total,'updated_utc':utc()});return
                    value,new=fit_one(pages,rep,lang,mode,'null',replicate=b,nullstats=ns);completed+=1
                    if new and (b%5==0 or mode=='bag' and lang=='latin'):
                        print(json.dumps({'completed':completed,'total':total,'rep':rep,'model':lang+'_'+mode,'null':b,'seconds':value['seconds'],'changed_token_fraction':ns['changed_token_fraction']},ensure_ascii=False),flush=True)
                    save(ROOT/'progress.json',{'status':'fitting','completed':completed,'total':total,'updated_utc':utc(),'elapsed_this_invocation_seconds':time.time()-start})
    keypaths=sorted((ROOT/'keys').glob('*.json'));assert len(keypaths)==total
    save(ROOT/'keys_frozen.json',{'created_utc':utc(),'completed':completed,'total':total,'implementation_hashes':impl(),'key_files':{p.name:sha(p) for p in keypaths},'inventory_sha256':sha(ROOT/'inventory.json'),'confirm_scored':False,'reserve_scored':False})
    save(ROOT/'progress.json',{'status':'keys_frozen','completed':completed,'total':total,'updated_utc':utc()});print('All keys frozen; confirm has not been scored.',flush=True)

def page_scores(pages,key,lang,mode):
    lm=model(lang,mode);lex=read(CONTROL/'models'/f'{lang}_lexicon.json');vocab=set(lex);bagvocab={''.join(sorted(w)) for w in vocab};out=[]
    for p in pages:
        ww=words([p]);nu=sum(map(len,ww))
        if not nu:continue
        ss=raw_score(ww,key,lm,mode=='bag');decoded=encode(ww,key)
        hits=sum((''.join(sorted(w)) in bagvocab) if mode=='bag' else (w in vocab) for w in decoded)
        out.append({'folio':p['folio'],'leaf':p['leaf'],'metadata':p['metadata'],'units':nu,'tokens':len(ww),'log_score_sum':ss,'log_score_per_unit':ss/nu,'lexicon_hit_rate':hits/len(ww)})
    return {'pages':len(out),'page_mean_score':float(np.mean([p['log_score_per_unit'] for p in out])),'page_mean_lexicon_hit':float(np.mean([p['lexicon_hit_rate'] for p in out])),'per_page':out}
def holm(rows):
    order=sorted(range(len(rows)),key=lambda i:rows[i]['p_value']);cur=0.
    for rank,i in enumerate(order):cur=max(cur,min(1.,(len(rows)-rank)*rows[i]['p_value']));rows[i]['holm_p']=cur

def evaluate():
    frozen=read(ROOT/'keys_frozen.json');assert impl()==frozen['implementation_hashes']
    assert all(sha(ROOT/'keys'/p)==h for p,h in frozen['key_files'].items());assert sha(ROOT/'inventory.json')==frozen['inventory_sha256']
    if (ROOT/'evaluation.json').exists():print('Completed evaluation already exists; not changing frozen keys or rescoring.');return
    save(ROOT/'evaluation_started.json',{'utc':utc(),'keys_frozen_sha256':sha(ROOT/'keys_frozen.json'),'allowed_splits':['dev','confirm'],'reserve_scored':False})
    inventory=read(ROOT/'inventory.json');dataset={};coverage={};allresults=[];stability=[]
    for rep in REPS:
        dataset[rep]={};coverage[rep]={}
        for split in ['dev','confirm']:
            dataset[rep][split],coverage[rep][split]=normalize(safe_load([split]),rep,inventory[rep]['inventory'])
        train=read(ROOT/'data'/f'train_{rep}.json');freq=Counter(''.join(words(train)))
        for lang in LANGS:
            for mode in MODES:
                keys=[read(case_path(rep,lang,mode,'real',search_index=s)) for s in range(3)]
                agreements=[]
                for a,b in [(0,1),(0,2),(1,2)]:
                    agreement=sum(n for c,n in freq.items() if keys[a]['mapping'][ord(c)-97]==keys[b]['mapping'][ord(c)-97])/sum(freq.values());agreements.append({'seeds':[a,b],'weighted_agreement':agreement})
                stability.append({'representation':rep,'language':lang,'mode':mode,'pairwise':agreements,'three_keys':[k['mapping'] for k in keys]})
                real=keys[0];real_eval={s:page_scores(dataset[rep][s],real['mapping'],lang,mode) for s in ['dev','confirm']}
                nulls=[]
                for b in range(NULL_N[rep]):
                    key=read(case_path(rep,lang,mode,'null',replicate=b));npages,ns=null_pages(dataset[rep]['confirm'],rep,b)
                    val=page_scores(npages,key['mapping'],lang,mode);nulls.append({'replicate':b,'page_mean_score':val['page_mean_score'],'page_mean_lexicon_hit':val['page_mean_lexicon_hit'],'null_stats':ns})
                nullvals=np.array([x['page_mean_score'] for x in nulls]);observed=real_eval['confirm']['page_mean_score']
                row={'representation':rep,'language':lang,'mode':mode,'primary':rep=='eva','observed':observed,'null_mean':float(nullvals.mean()),'effect':float(observed-nullvals.mean()),'null_95_reference':np.quantile(nullvals,[.025,.975]).tolist(),'p_value':float((1+np.sum(nullvals>=observed-1e-12))/(len(nullvals)+1)),'replicates':len(nullvals),'real':real_eval,'nulls':nulls,'main_mapping':{u:real['mapping'][i] for i,u in enumerate(inventory[rep]['inventory'])}}
                allresults.append(row);save(ROOT/'evaluation_partial.json',{'completed':len(allresults),'results':allresults,'coverage':coverage});print(json.dumps({k:row[k] for k in ['representation','language','mode','observed','null_mean','effect','p_value']},ensure_ascii=False),flush=True)
    holm([x for x in allresults if x['primary']])
    # Numeric invariance demonstrations on training words, not an extra selection.
    checks=[]
    for rep in REPS:
        ww=words(read(ROOT/'data'/f'train_{rep}.json'));reordered=list(reversed(ww));inner=[''.join(reversed(w)) for w in ww]
        for lang in LANGS:
            for mode in MODES:
                key=read(case_path(rep,lang,mode,'real'))['mapping'];lm=model(lang,mode);s=raw_score(ww,key,lm,mode=='bag');t=raw_score(reordered,key,lm,mode=='bag');assert abs(s-t)<1e-6
                item={'representation':rep,'language':lang,'mode':mode,'word_order_score_delta':t-s}
                if mode=='bag':u=raw_score(inner,key,lm,True);assert abs(u-s)<1e-6;item['within_word_order_score_delta']=u-s
                checks.append(item)
    save(ROOT/'evaluation.json',{'created_utc':utc(),'keys_frozen_sha256':sha(ROOT/'keys_frozen.json'),'results':allresults,'coverage':coverage,'stability':stability,'invariance_checks':checks,'reserve_scored':False,'interpretation':'Word-shape compatibility only. Neither scoring model uses sentence order or meaning.'})
    save(ROOT/'progress.json',{'status':'evaluated','updated_utc':utc(),'reserve_scored':False,'configurations':len(allresults)})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','calibrate','fit','evaluate']);a=p.parse_args();globals()[a.action]()
