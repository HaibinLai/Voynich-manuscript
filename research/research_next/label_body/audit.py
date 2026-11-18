"""Independent standard-library replay; never imports the primary scorer.

Reconstructs packet from source, enumerates accepted word variants rather than
using pairwise Hamming tests, and aggregates exact rational rates.
"""
from pathlib import Path
from collections import Counter, defaultdict
from fractions import Fraction as F
import argparse, datetime, gzip, hashlib, json, random, re

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
ERRORS=[]
COUNTS=Counter()
MAX_ERROR=0.0

def read(p):
    return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_text())

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def compare(actual,expected,path):
    global MAX_ERROR
    if isinstance(actual,dict):
        if not isinstance(expected,dict) or set(actual)!=set(expected):
            ERRORS.append([path,'keys',str(set(actual)),str(set(expected))]);return
        for k,v in actual.items():compare(v,expected[k],path+'/'+k)
    elif isinstance(actual,list):
        if not isinstance(expected,list) or len(actual)!=len(expected):
            ERRORS.append([path,'length',len(actual),len(expected)]);return
        for i,(a,b) in enumerate(zip(actual,expected)):compare(a,b,path+'/'+str(i))
    elif isinstance(actual,(F,float)):
        if not isinstance(expected,(int,float)):
            ERRORS.append([path,'number type',str(actual),expected]);return
        error=abs(float(actual)-expected);MAX_ERROR=max(MAX_ERROR,error)
        COUNTS['floating_values']+=1
        if error>2e-12:ERRORS.append([path,'numeric',float(actual),expected])
    elif actual!=expected:
        ERRORS.append([path,'exact',actual,expected])
    else: COUNTS['exact_values']+=1

def u(w):
    out=re.findall(r"@\d{3};|[a-z']",w)
    assert ''.join(out)==w
    return tuple(out)

def physical(f):
    if f=='fRos' or f.startswith(('f85r','f85v','f86r','f86v')):return 'f85_86'
    match=re.match(r'f[0-9]+',f)
    return match.group() if match else f

def tokens(raw):
    raw=raw.replace('<->','.').replace('<~>','.')
    raw=re.sub('<[^>]*>','',raw).replace('{','').replace('}','').lower().replace(',','.')
    out=[]
    for w in raw.split('.'):
        w=''.join(w.split())
        if w:out.append(w if re.fullmatch(r"(?:[a-z']|@[0-9]{3};)+",w) else None)
    return out

def rebuild(source):
    pp={};c=Counter()
    for number,line in enumerate((REPO/'research/sources'/source).read_text().splitlines(),1):
        if not line.startswith('<'):continue
        stop=line.index('>');tag=line[1:stop];raw=line[stop+1:].strip()
        if '.' not in tag:
            m=dict(re.findall(r'\$([A-Za-z0-9_])=([A-Za-z0-9@])',raw))
            current=tag
            pp[tag]=dict(folio=tag,leaf=physical(tag),H=m.get('H'),I=m.get('I'),Q=m.get('Q'),body=[],labels=[])
            continue
        loc,kind=tag.split(',');typ=kind[1:]
        assert loc.split('.')[0]==current
        if kind.startswith('!'):c['nonexistent_loci']+=1;continue
        if typ not in {'La','Lc','Lf','Ln','Lp','Ls','Lt','Lz','P0','P1','Pc','Pr','Pt'}:continue
        base=dict(locator=loc,source_line=number,kind=kind,type=typ,uncertain_space=',' in raw,raw=raw)
        tt=tokens(raw)
        if typ.startswith('P'):pp[current]['body'].append(dict(**base,tokens=tt))
        else:
            c['image_loci_total']+=1
            if len(tt)!=1 or tt[0] is None:c['excluded_empty_multiword_or_uncertain_label']+=1
            else:pp[current]['labels'].append(dict(**base,word=tt[0],units=list(u(tt[0]))))
    c['complete_singleword_labels']=sum(len(p['labels']) for p in pp.values());c['pages']=len(pp)
    return dict(source=source,sha256=digest(REPO/'research/sources'/source),pages=list(pp.values()),inventory=dict(c))

def avg(values):return sum(values,F(0))/len(values) if values else None

def accepted(word,model):
    base=u(word);res={base}
    if model!='exact':
        a,b=model
        for j,x in enumerate(base):
            if x==a:res.add(base[:j]+(b,)+base[j+1:])
            if x==b:res.add(base[:j]+(a,)+base[j+1:])
    return res

def aggregation(rows):
    if not rows:return dict(labels=0,pages=0,leaves=0,own=None,control=None,delta=None,by_leaf=[],by_page=[])
    groups=defaultdict(list)
    for r in rows:groups[r['folio']].append(r)
    page=[]
    for f,rr in sorted(groups.items()):
        p=dict(folio=f,leaf=rr[0]['leaf'],H=rr[0]['H'],I=rr[0]['I'],labels=len(rr))
        for k in ['own','control','delta']:p[k]=avg([x[k] for x in rr])
        page.append(p)
    leaves=defaultdict(list)
    for p in page:leaves[p['leaf']].append(p)
    ll=[]
    for l,pp in sorted(leaves.items()):
        r=dict(leaf=l,pages=len(pp),labels=sum(p['labels'] for p in pp))
        for k in ['own','control','delta']:r[k]=avg([p[k] for p in pp])
        ll.append(r)
    return dict(labels=len(rows),pages=len(page),leaves=len(ll),
        **{k:avg([r[k] for r in ll]) for k in ['own','control','delta']},
        labels_with_own_match=sum(r['own_m']!=0 for r in rows),by_leaf=ll,by_page=page)

def recount(packet,model='exact',variant='main',drop=None):
    pages=[p for p in packet['pages'] if p['leaf']!=drop]
    valid={p['folio']:p for p in pages if p['H'] in ['1','2','3','4','5'] and p['I'] in set('ABCHPSTZ')}
    words={};freq={}
    for folio,p in valid.items():
        lengths=defaultdict(list)
        for loc in p['body']:
            if variant=='certain_loci' and loc['uncertain_space']:continue
            for slot,w in enumerate(loc['tokens']):
                if w is not None:lengths[len(u(w))].append((w,loc['locator'],slot))
        words[folio]=lengths
        freq[folio]={L:Counter(u(w) for w,loc,slot in vv) for L,vv in lengths.items()}
    threshold=5 if variant=='min5' else 1
    leaf_threshold=2 if variant=='min5' else 1
    errors=Counter();all_labels=0;out=[]
    for page in pages:
        seen=set();folio=page['folio']
        for label in page['labels']:
            all_labels+=1;word=label['word'];L=len(u(word))
            if folio not in valid:errors['unknown_or_mixed_metadata']+=1;continue
            if variant=='certain_loci' and label['uncertain_space']:errors['uncertain_label_boundary']+=1;continue
            if variant=='dedup_labels' and word in seen:errors['repeated_label_on_page']+=1;continue
            seen.add(word)
            n=len(words[folio].get(L,[]))
            if n<threshold:errors['insufficient_own_length_opportunities']+=1;continue
            donor=[]
            for f,q in valid.items():
                if q['leaf']==page['leaf'] or (q['H'],q['I'])!=(page['H'],page['I']):continue
                if variant=='HIQ' and q['Q']!=page['Q']:continue
                if len(words[f].get(L,[]))>=threshold:donor.append(f)
            if len({valid[f]['leaf'] for f in donor})<leaf_threshold:
                errors['insufficient_other_leaf_controls']+=1;continue
            options=accepted(word,model)
            hit=[dict(word=w,locator=loc,slot=slot) for w,loc,slot in words[folio][L] if u(w) in options]
            dd=[];by_leaf=defaultdict(list)
            for f in donor:
                dn=len(words[f][L]);dm=sum(freq[f][L][x] for x in options);rate=F(dm,dn)
                dd.append(dict(folio=f,leaf=valid[f]['leaf'],n=dn,m=dm,rate=rate));by_leaf[valid[f]['leaf']].append(rate)
            own=F(len(hit),n);control=avg([avg(xx) for xx in by_leaf.values()])
            row={k:page[k] for k in ['folio','leaf','H','I','Q']}
            row.update(locator=label['locator'],type=label['type'],word=word,length=L,own_n=n,own_m=len(hit),
                       own=own,control=control,delta=own-control,control_leaves=len(by_leaf),donors=dd,body_hits=hit)
            out.append(row)
    return dict(model=model,variant=variant,dropped_leaf=drop,labels_considered=all_labels,
                excluded=dict(errors),summary=aggregation(out)),out

def calibration_replay(rows,saved):
    shape={}
    for r in rows:
        shape[r['folio'],r['length']]=r['own_n']
        for d in r['donors']:shape[d['folio'],r['length']]=d['n']
    summaries=[];first=[]
    for seed in range(2026111800,2026111900):
        rng=random.Random(seed)
        corpus={key:[rng.randrange(100) for _ in range(n)] for key,n in sorted(shape.items())}
        histogram={k:Counter(v) for k,v in corpus.items()}
        rr={'independent':[],'copy_from_own':[]}
        for row in rows:
            ownkey=(row['folio'],row['length'])
            queries=[rng.randrange(100),rng.choice(corpus[ownkey])]
            for mode,query in zip(['independent','copy_from_own'],queries):
                count=histogram[ownkey][query];own=F(count,row['own_n']);by_leaf=defaultdict(list);dd=[]
                for d in row['donors']:
                    m=histogram[d['folio'],row['length']][query]
                    by_leaf[d['leaf']].append(F(m,d['n']))
                    if seed==2026111800:dd.append(dict(**d,sim_m=m))
                ref=avg([avg(vv) for vv in by_leaf.values()])
                r={k:row[k] for k in ['folio','leaf','H','I','locator']}
                r.update(own=own,control=ref,delta=own-ref,own_m=count)
                rr[mode].append(r)
                if seed==2026111800:first.append(dict(**r,mode=mode,query=query,n=row['own_n'],donors=dd))
        summaries.append(dict(seed=seed,**{mode:{k:aggregation(vv)[k] for k in ['own','control','delta','labels','pages','leaves']} for mode,vv in rr.items()}))
    replay=dict(vocabulary_size=100,seeds=summaries,first_seed_rows=first,
        mean_delta={mode:avg([s[mode]['delta'] for s in summaries]) for mode in rr},caution=saved['caution'])
    compare(replay,saved,'calibration')
    COUNTS['synthetic_seed_models']+=200

def main(run,output):
    inputs=read(run/'input.json.gz');trials=read(run/'trials.json.gz');results=read(run/'results.json');cal=read(run/'calibration.json.gz')
    for item in read(run/'freeze.json')['files']:
        compare(digest(REPO/item['path']),item['sha256'],'frozen/'+item['path'])
    for item in read(run/'complete.json')['files']:
        compare(digest(run/item['path']),item['sha256'],'saved/'+item['path'])
    independent_rows={};independent_models={}
    for version,data in inputs.items():
        independent_models[version]={}
        compare(rebuild(data['source']),data,'source_packet/'+version)
        COUNTS['source_loci_rebuilt']+=sum(len(p['body'])+len(p['labels']) for p in data['pages'])
        for model in ['exact','fk','fp','ft','kp','kt','pt']:
            summary,rows=recount(data,model)
            compare(summary,results[version]['main'][model],version+'/'+model+'/summary')
            compare(rows,trials[version][model],version+'/'+model+'/rows')
            COUNTS['main_models']+=1;COUNTS['main_label_rows']+=len(rows)
            independent_models[version][model]=rows
            if model=='exact':independent_rows[version]=rows
        for variant in ['HIQ','min5','certain_loci','dedup_labels']:
            summary,rows=recount(data,variant=variant)
            compare(summary,results[version]['sensitivity'][variant],version+'/'+variant+'/summary')
            compare(rows,trials[version]['sensitivity_'+variant],version+'/'+variant+'/rows')
            COUNTS['sensitivity_models']+=1
        for saved in results[version]['leave_one_leaf_out']:
            summary,rows=recount(data,drop=saved['dropped_leaf'])
            compare(summary,saved,version+'/drop/'+saved['dropped_leaf']);COUNTS['leave_leaf_models']+=1
        for field,name in [('H','by_hand'),('I','by_illustration'),('type','by_type')]:
            group=defaultdict(list)
            for row in independent_rows[version]:group[row[field]].append(row)
            compare({k:aggregation(v) for k,v in group.items()},results[version][name],version+'/'+name)
            COUNTS['subgroup_summaries']+=len(group)
        calibration_replay(independent_rows[version],cal[version])
    # Independently validate all output-dependent candidate lists and their order.
    z={r['locator']:r for r in independent_rows['ZL']};i={r['locator']:r for r in independent_rows['IT']}
    common=[]
    for loc in sorted(z.keys() & i.keys(),key=lambda s:[int(x) if x.isdigit() else x for x in re.split(r'(\d+)',s)]):
        if z[loc]['word']==i[loc]['word']:common.append(dict(locator=loc,word=z[loc]['word'],ZL=z[loc],IT=i[loc]))
    cc=read(run/'candidates.json')
    compare(len(common),cc['shared_identical_eligible_labels'],'candidate_count')
    compare([r for r in common if r['ZL']['own_m'] and r['IT']['own_m']],cc['both_hit'],'candidates_hit')
    compare([r for r in common if not r['ZL']['own_m'] and not r['IT']['own_m']],cc['both_no_hit'],'candidates_zero')
    supplement_path=HERE/'supplement.json'
    if supplement_path.exists():
        supplement=read(supplement_path)
        compare(True,supplement['post_result'],'supplement/post_result')
        compare(digest(run/'trials.json.gz'),supplement['input_sha256'],'supplement/input_hash')
        compare(digest(HERE/'supplement.py'),supplement['script_sha256'],'supplement/script_hash')
        compare(digest(HERE/'supplement_protocol.txt'),supplement['protocol_sha256'],'supplement/protocol_hash')
        locs={r['locator'] for r in common}
        compare(len(locs),supplement['common_labels'],'supplement/common_labels')
        for version,models in independent_models.items():
            target=supplement['results'][version];exact=models['exact']
            same={m:aggregation([r for r in rows if r['locator'] in locs]) for m,rows in models.items()}
            compare(same,target['common_support'],'supplement/'+version+'/common_support')
            words=sorted({r['word'] for r in exact})
            removed=[dict(word=w,summary=aggregation([r for r in exact if r['word']!=w])) for w in words]
            compare(removed,target['drop_label_type'],'supplement/'+version+'/drop_label_type')
            sections=sorted({r['I'] for r in exact})
            deleted=[dict(removed_I=i,summary=aggregation([r for r in exact if r['I']!=i])) for i in sections]
            compare(deleted,target['drop_illustration'],'supplement/'+version+'/drop_illustration')
            for mode in ['independent','copy_from_own']:
                xx=[F(s[mode]['delta']) for s in cal[version]['seeds']]
                center=avg(xx)
                sd=float(sum(((x-center)**2 for x in xx),F(0))/(len(xx)-1))**0.5
                stats=dict(n=len(xx),mean=center,sample_sd=sd,min=min(xx),max=max(xx))
                compare(stats,target['calibration'][mode],'supplement/'+version+'/calibration/'+mode)
            COUNTS['supplement_common_models']+=len(models)
            COUNTS['supplement_label_deletions']+=len(words)
            COUNTS['supplement_illustration_deletions']+=len(sections)
            COUNTS['supplement_calibration_summaries']+=2
    report=dict(passed=not ERRORS,checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        counts=dict(COUNTS),max_absolute_float_difference=MAX_ERROR,errors=ERRORS,
        code_sha256=digest(Path(__file__)),input_hashes={p.name:digest(p) for p in sorted(run.iterdir()) if p.is_file()},
        scope='Independent source parsing, full primary/sensitivity/deletion/subgroup scoring using exact fractions, all 100 synthetic seeds per version and all saved first-seed rows. Includes post-result common-label support, label-type and illustration target deletions, and calibration descriptive statistics. No primary scoring imports.',
        limitations=['Same exposed manuscript and labels, not an independent data replication.','No object-level image verification or plaintext validation.','Arithmetic agreement does not establish semantic interpretation.'])
    if supplement_path.exists():
        report['supplement_hashes']={p.name:digest(p) for p in [supplement_path,HERE/'supplement.py',HERE/'supplement_protocol.txt']}
    output.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    output.with_suffix('.txt').write_text('标签—正文独立计算复核\n\n'+('通过' if not ERRORS else '失败')+'\n'+json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if ERRORS:raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,default=HERE/'saved_v1');p.add_argument('--output',type=Path,default=HERE/'audit_v1')
    a=p.parse_args();main(a.run,a.output)
