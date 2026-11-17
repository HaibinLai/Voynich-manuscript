"""Fixed-seed conditional randomization study; no semantic decoding."""
from pathlib import Path
from collections import Counter, defaultdict
import json, re, sys, hashlib, unicodedata, xml.etree.ElementTree as ET
import numpy as np

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from build_corpus import parse
SEED=20261117

def units(token, representation='eva'):
    pattern=(r'cth|ckh|cph|cfh|ch|sh|@\d{3};|[a-z\']' if representation=='merged'
             else r'@\d{3};|[a-z\']')
    result=re.findall(pattern,token)
    assert ''.join(result)==token,repr(token)
    return tuple(result)

def tokenize(raw, spaces='split', alternatives='exclude'):
    raw=re.sub(r'<[-~]>', '.', raw)
    raw=re.sub(r'<[^>]*>', '', raw)
    raw=raw.replace('{','').replace('}','').lower()
    if alternatives=='first':raw=re.sub(r'\[([^\]]+)\]',lambda m:m[1].split(':')[0],raw)
    raw=raw.replace(',', '.' if spaces=='split' else '')
    result=[]
    for text in raw.split('.'):
        text=re.sub(r'\s','',text)
        if not text:continue
        if any(c in text for c in '[]?*') or not re.fullmatch(r"(?:[a-z']|@\d{3};)+",text):
            result.append(None)
        else:result.append(text)
    return result

def build_pages(source='ZL3b-n.txt', spaces='split', alternatives='exclude'):
    records,_=parse(source)
    selection=json.loads((ROOT/'selection.json').read_text());chosen={x['folio']:x for x in selection}
    pages={f:{**x,'lines':[]} for f,x in chosen.items()}
    for r in records:
        if r['folio'] not in pages or r['locus_type'][1]!='P' or r['locus_type'][0]=='!':continue
        page=pages[r['folio']];raw=r['text_ivtff']
        toks=tokenize(raw,spaces,alternatives)
        if (r['locus_type'][0]=='=' or r['locus_type'][1:]=='Pt') and page['lines']:
            previous=page['lines'][-1];previous['tokens'].extend(toks)
            previous['loci'].append(r['locator']);previous['paragraph_end']|=('<$>' in raw)
        else:
            page['lines'].append(dict(tokens=toks,loci=[r['locator']],
                paragraph_start='<%>' in raw,paragraph_end='<$>' in raw))
    return [p for p in pages.values() if p['lines']]

def entropy_counts(counts):
    a=np.asarray(list(counts),dtype=float);a=a[a>0]
    if not len(a):return float('nan')
    p=a/a.sum();return float(-(p*np.log2(p)).sum())

def entropy_summary(words):
    edges=Counter((a,b) for w in words for a,b in zip(w,w[1:]))
    prev=Counter();nxt=Counter()
    for (a,b),n in edges.items():prev[a]+=n;nxt[b]+=n
    conditional=entropy_counts(edges.values())-entropy_counts(prev.values())
    hn=entropy_counts(nxt.values())
    return dict(h_next=hn,h_conditional=conditional,ratio=conditional/hn if hn else None,edges=sum(edges.values()))

def edit_le_one(a,b):
    if abs(len(a)-len(b))>1:return False
    if len(a)==len(b):return sum(x!=y for x,y in zip(a,b))<=1
    if len(a)>len(b):a,b=b,a
    i=j=miss=0
    while i<len(a) and j<len(b):
        if a[i]==b[j]:i+=1;j+=1
        else:
            miss+=1;j+=1
            if miss>1:return False
    return True

def prepare(pages,representation):
    vocab=sorted({t for p in pages for l in p['lines'] for t in l['tokens'] if t is not None})
    ids={w:i for i,w in enumerate(vocab)};uu=[units(w,representation) for w in vocab]
    near=np.zeros((len(vocab),len(vocab)),dtype=bool)
    for i,a in enumerate(uu):
        for j in range(i,len(uu)):
            if edit_le_one(a,uu[j]):near[i,j]=near[j,i]=True
    lengths=np.array([len(x) for x in uu]);gallows=np.array([x[0] in 'ktpf' for x in vocab],dtype=float)
    arr=[]
    for p in pages:
        lines=[]
        for l in p['lines']:
            lines.append({**l,'ids':np.array([ids[t] if t else -1 for t in l['tokens']],dtype=int)})
        arr.append({**p,'lines':lines})
    return vocab,uu,near,lengths,gallows,arr

def metrics(pages,near,lengths,gallows, subgroup='all'):
    page_values=[];details=[]
    for p in pages:
        a=b=n=0;starts=[];others=[];ends=[];otherlens=[]
        for line in p['lines']:
            ids=line['ids'];valid=ids>=0
            if len(ids)>=2:
                pairs=valid[:-1]&valid[1:]
                a+=near[ids[:-1][pairs],ids[1:][pairs]].sum();n+=pairs.sum()
                b+=np.equal(ids[:-1][pairs],ids[1:][pairs]).sum()
                if ids[0]>=0 and valid[1:].any() and (subgroup!='nonparagraph' or not line['paragraph_start']):
                    starts.append(gallows[ids[0]]);others.extend(gallows[ids[1:][valid[1:]]])
                if ids[-1]>=0 and valid[:-1].any() and (subgroup!='nonparagraph' or not line['paragraph_end']):
                    ends.append(lengths[ids[-1]]);otherlens.extend(lengths[ids[:-1][valid[:-1]]])
        # Equal page weights, not treating tokens as independent observations.
        vals=[float(a/n) if n else np.nan,
              float(np.mean(starts)-np.mean(others)) if starts and others else np.nan,
              float(np.mean(ends)-np.mean(otherlens)) if ends and otherlens else np.nan]
        page_values.append(vals)
        details.append(dict(folio=p['folio'],physical_lines=len(p['lines']),adjacent_pairs=int(n),
                            near_pairs=int(a),exact_pairs=int(b),near_rate=vals[0],
                            start_gallows_rate=float(np.mean(starts)) if starts else None,
                            other_gallows_rate=float(np.mean(others)) if others else None,
                            start_gallows_delta=vals[1],end_length_delta=vals[2],
                            tokens=int(sum(np.sum(l['ids']>=0) for l in p['lines']))))
    return np.nanmean(page_values,axis=0),details

def shuffled(pages,rng,mode):
    result=[]
    for p in pages:
        lines=[{**l,'ids':l['ids'].copy()} for l in p['lines']]
        if mode=='line':
            for l in lines:
                mask=l['ids']>=0;l['ids'][mask]=rng.permutation(l['ids'][mask])
        else:
            values=np.concatenate([l['ids'][l['ids']>=0] for l in lines]);values=rng.permutation(values);offset=0
            for l in lines:
                mask=l['ids']>=0;n=mask.sum();l['ids'][mask]=values[offset:offset+n];offset+=n
        result.append({**p,'lines':lines})
    return result

def randomization(observed,values):
    values=np.asarray(values,dtype=float);center=float(np.median(values))
    extreme=np.count_nonzero(np.abs(values-center)>=abs(observed-center)-1e-12)
    return dict(observed=float(observed),null_median=center,
                effect_vs_null=float(observed-center),null_95_interval=np.quantile(values,[.025,.975]).tolist(),
                monte_carlo_p=float((extreme+1)/(len(values)+1)),replicates=len(values))

def run_test(pages,representation='eva',B=1999,seed=SEED):
    vocab,uu,near,lengths,gallows,arr=prepare(pages,representation)
    rng=np.random.default_rng(seed)
    words=[uu[i] for p in arr for l in p['lines'] for i in l['ids'] if i>=0]
    original=entropy_summary(words);observed,details=metrics(arr,near,lengths,gallows)
    nonpara,_=metrics(arr,near,lengths,gallows,'nonparagraph')
    null_h=[];null_page=[];null_line=[];null_nonpara=[]
    for b in range(B):
        null_h.append(entropy_summary([rng.permutation(w).tolist() for w in words])['ratio'])
        null_page.append(metrics(shuffled(arr,rng,'page'),near,lengths,gallows)[0][0])
        sl=shuffled(arr,rng,'line')
        null_line.append(metrics(sl,near,lengths,gallows)[0])
        null_nonpara.append(metrics(sl,near,lengths,gallows,'nonparagraph')[0])
    nl=np.array(null_line);nn=np.array(null_nonpara)
    tests={
        'H1_conditional_entropy_ratio':randomization(original['ratio'],null_h),
        'H2_adjacent_edit_le1_rate':randomization(observed[0],null_page),
        'H3_line_start_gallows_delta':randomization(observed[1],nl[:,1]),
        'H4_line_end_length_delta':randomization(observed[2],nl[:,2]),
    }
    return dict(pages=len(pages),tokens=len(words),vocabulary=len(vocab),representation=representation,
        entropy=original,tests=tests,per_page=details,
        supplemental={
          'H2_line_shuffle':randomization(observed[0],nl[:,0]),
          'H3_excluding_paragraph_starts':randomization(nonpara[1],nn[:,1]),
          'H4_excluding_paragraph_ends':randomization(nonpara[2],nn[:,2])},
        raw_nulls=dict(H1=null_h,H2=null_page,H3=nl[:,1].tolist(),H4=nl[:,2].tolist()))

def holm(tests):
    order=sorted(tests,key=lambda k:tests[k]['monte_carlo_p']);current=0
    for i,key in enumerate(order):
        current=max(current,min(1.,(len(order)-i)*tests[key]['monte_carlo_p']))
        tests[key]['holm_adjusted_p']=current

def plain_words(name):
    p=ROOT/'controls'/name
    if p.suffix=='.xml':
        tree=ET.parse(p);body=next(el for el in tree.iter() if el.tag.split('}')[-1]=='body')
        # Editorial notes are excluded. Keep text node spacing explicit.
        for parent in body.iter():
            for child in list(parent):
                if child.tag.split('}')[-1] in ('note','head','speaker'):parent.remove(child)
        s=' '.join(body.itertext())
    else:
        s=p.read_text(encoding='utf-8-sig')
        if '*** START OF' in s:s=s.split('*** START OF',1)[1].split('\n',1)[1]
        if '*** END OF' in s:s=s.split('*** END OF',1)[0]
        marker="Alice was beginning to get very tired"
        if marker in s:s=s[s.index(marker):]
    s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()
    return re.findall('[a-z]+',s)

def external_pages(template,words,seed,length_match=False):
    rng=np.random.default_rng(seed);count=sum(t is not None for p in template for l in p['lines'] for t in l['tokens'])
    assert len(words)>count+100
    start=int(rng.integers(0,len(words)-count));stream=iter(words[start:start+count])
    buckets=defaultdict(list)
    for w in words:buckets[len(w)].append(w)
    result=[];unmatched=0
    for p in template:
        lines=[]
        for l in p['lines']:
            toks=[]
            for t in l['tokens']:
                if t is None:toks.append(None)
                elif length_match:
                    bucket=buckets[len(units(t))]
                    if not bucket:raise ValueError(('missing_length_bucket',len(units(t))))
                    toks.append(str(rng.choice(bucket)))
                else:toks.append(next(stream))
            lines.append({**l,'tokens':toks})
        result.append({**p,'lines':lines})
    return result,dict(start_token=start,valid_tokens=count,length_match=length_match)

def copy_mutate_pages(template,training,seed):
    rng=np.random.default_rng(seed)
    train=[t for p in training for l in p['lines'] for t in l['tokens'] if t]
    char_list=[c for t in train for c in units(t)]
    lengths=np.array([len(units(t)) for t in train]);result=[]
    # Fixed toy mechanism: 70% copy a previous word, optionally substitute one
    # unit with probability .6; otherwise draw fresh iid units. Not historically fitted.
    for p in template:
        lines=[];history=[]
        for l in p['lines']:
            toks=[]
            for t in l['tokens']:
                if t is None:toks.append(None);continue
                if history and rng.random()<.7:
                    w=list(history[int(rng.integers(max(0,len(history)-8),len(history)))])
                    if rng.random()<.6:w[int(rng.integers(len(w)))]=char_list[int(rng.integers(len(char_list)))]
                else:
                    n=int(rng.choice(lengths));w=[char_list[int(i)] for i in rng.integers(len(char_list),size=n)]
                history.append(tuple(w));toks.append(''.join(w))
            lines.append({**l,'tokens':toks})
        result.append({**p,'lines':lines})
    return result

def verify():
    assert tokenize('a<->b<~>c')==['a','b','c']
    assert tokenize('a,b.c',spaces='join')==['ab','c']
    assert tokenize('a.[b:c].d?')==['a',None,None]
    assert tokenize('a.[b:c].d?',alternatives='first')==['a','b',None]
    assert units('qotchey','merged')==('q','o','t','ch','e','y')
    for a,b,val in [('abc','abc',True),('ab','abc',True),('abc','axc',True),('abc','ac',True),('abc','ax',False)]:
        assert edit_le_one(tuple(a),tuple(b))==val
    p=build_pages();f25=next(x for x in p if x['folio']=='f25r')
    assert len(f25['lines'])==6 and f25['lines'][-1]['loci']==['f25r.6','f25r.7']
    rng=np.random.default_rng(SEED)
    vocab,uu,near,lengths,gallows,arr=prepare(p,'eva')
    for mode in ['page','line']:
        sh=shuffled(arr,rng,mode)
        for a,b in zip(arr,sh):
            assert Counter(i for l in a['lines'] for i in l['ids'])==Counter(i for l in b['lines'] for i in l['ids'])
            assert [len(l['ids']) for l in a['lines']]==[len(l['ids']) for l in b['lines']]
            for la,lb in zip(a['lines'],b['lines']):
                assert np.array_equal(la['ids']<0,lb['ids']<0)
                if mode=='line':assert Counter(la['ids'])==Counter(lb['ids'])
    # Bijection invariance uses abstract units; does not redo greedy EVA merges.
    all_units=sorted({x for w in uu for x in w});mapping={x:str(i) for i,x in enumerate(all_units)}
    words=uu[:100];mapped=[tuple(mapping[c] for c in w) for w in words]
    assert abs(entropy_summary(words)['ratio']-entropy_summary(mapped)['ratio'])<1e-12
    for a,b in zip(words,words[1:]):
        assert edit_le_one(a,b)==edit_le_one(tuple(mapping[c] for c in a),tuple(mapping[c] for c in b))
    return dict(parser_boundary_tests=True,physical_line_reconstruction=True,shuffle_invariants=True,
                abstract_bijection_invariance=True)

def main():
    out=ROOT/'results';out.mkdir(exist_ok=True)
    checked=verify();(out/'verification.json').write_text(json.dumps(checked,indent=2))
    result=dict(seed=SEED,protocol_sha256=hashlib.sha256((ROOT/'protocol_v1.txt').read_bytes()).hexdigest(),runs={})
    if '--resume' in sys.argv and (out/'statistics.json').exists():
        saved=json.loads((out/'statistics.json').read_text())
        assert saved['seed']==SEED and saved['protocol_sha256']==result['protocol_sha256']
        result=saved
    configs=[('primary','ZL3b-n.txt','split','exclude','eva',1999),
             ('merged_units','ZL3b-n.txt','split','exclude','merged',399),
             ('join_uncertain_spaces','ZL3b-n.txt','join','exclude','eva',399),
             ('first_alternatives','ZL3b-n.txt','split','first','eva',399),
             ('IT_version','IT2a-n.txt','split','exclude','eva',399)]
    for label,source,spaces,alts,representation,B in configs:
        pages=build_pages(source,spaces,alts)
        for split in ['discovery','validation']:
            if label+'_'+split in result['runs']:continue
            subset=[p for p in pages if p['split']==split]
            res=run_test(subset,representation,B,SEED+(0 if split=='discovery' else 10000))
            if label=='primary' and split=='validation':holm(res['tests'])
            key=label+'_'+split;result['runs'][key]=res
            (out/'statistics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
            print(key,res['tokens'],{k:round(v['observed'],4) for k,v in res['tests'].items()},flush=True)
    mainpages=build_pages();discovery=[p for p in mainpages if p['split']=='discovery'];validation=[p for p in mainpages if p['split']=='validation']
    (out/'normalized_primary_pages.json').write_text(json.dumps(mainpages,ensure_ascii=False,indent=2))
    for lang,name in [('English','english_alice.txt'),('Latin','latin_caesar.xml')]:
        words=plain_words(name)
        for lengthmatch in [False,True]:
            external,selection=external_pages(validation,words,SEED,lengthmatch)
            key=lang+('_length_matched' if lengthmatch else '_contiguous')
            res=run_test(external,'eva',399,SEED+20000);res['selection']=selection
            res['limitation']='Artificial reflow; length-matched sampling destroys syntax; not a language identification test.'
            result['runs'][key]=res
            (out/'statistics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
            print(key,res['tokens'],{k:round(v['observed'],4) for k,v in res['tests'].items()},flush=True)
    toy=copy_mutate_pages(validation,discovery,SEED)
    (out/'toy_copy_mutate.json').write_text(json.dumps(toy,ensure_ascii=False,indent=2))
    result['runs']['toy_copy_mutate']=run_test(toy,'eva',399,SEED+30000)
    (out/'statistics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    print('Complete',flush=True)

if __name__=='__main__':main()
