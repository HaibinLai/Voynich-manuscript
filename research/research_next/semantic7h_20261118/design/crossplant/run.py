"""Frozen crossplant pilot. Import is inert; real scoring requires --execute and image freeze."""
from pathlib import Path
from collections import Counter, defaultdict
from fractions import Fraction
import argparse, datetime, gzip, hashlib, json, re, traceback

HERE=Path(__file__).resolve().parent
RUN=HERE.parents[1]
REPO=HERE.parents[4]
INPUT=RUN.parent/'label_body/saved_v1/input.json.gz'
LABELS=RUN/'literature/label_support.json'
MODELS=['exact','fk','fp','ft','kp','kt','pt','davis','davis_swapped','davis_sham']
MAPS={'davis':{'f':'te','p':'ke'},'davis_swapped':{'f':'ke','p':'te'},'davis_sham':{'f':'ta','p':'ka'}}
EXPECTED=[61,80,94,95,110,116,133,136,212,213,225,240]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_text())
def dump(p,x):
    def encode(v):
        if isinstance(v,Fraction):return {'num':v.numerator,'den':v.denominator,'value':float(v)}
        raise TypeError(type(v))
    b=(json.dumps(x,ensure_ascii=False,allow_nan=False,separators=(',',':'),default=encode)+'\n').encode()
    p.write_bytes(gzip.compress(b,mtime=0) if p.suffix=='.gz' else b)
def units(w):
    u=tuple(re.findall(r"@\d{3};|[a-z']",w))
    if ''.join(u)!=w:raise ValueError('Unrecognized complete-word syntax: '+repr(w))
    return u
def protected(u):
    out=set()
    for i in range(len(u)-2):
        if u[i]=='c' and u[i+1] in 'fkpt' and u[i+2]=='h':out.update(range(i,i+3))
    return out
def canonical(u,model):
    if model not in MAPS:return u
    shield=protected(u);mapping=MAPS[model];out=[]
    for i,c in enumerate(u):out.extend(tuple(mapping[c]) if i not in shield and c in mapping else (c,))
    return tuple(out)
def accepted(u,model):
    """Unique candidates. For pair models, zero or EXACTLY one original-position change."""
    if model in MAPS:return {canonical(u,model)}
    out={u}
    if model!='exact':
        a,b=model;shield=protected(u)
        for i,c in enumerate(u):
            if i not in shield and c in (a,b):out.add(u[:i]+(b if c==a else a,)+u[i+1:])
    return out
def words(page,strict):
    out=[];excluded=Counter()
    for row in page['body']:
        if strict and row['uncertain_space']:
            excluded['uncertain_space_lines']+=1
            excluded['tokens_on_uncertain_space_lines']+=len(row['tokens']);continue
        for slot,w in enumerate(row['tokens']):
            if w is None:excluded['unresolved_tokens']+=1;continue
            u=units(w)
            out.append(dict(word=w,units=list(u),folio=page['folio'],locator=row['locator'],slot=slot,
                source_line=row.get('source_line'),raw_length=len(u)))
    return out,dict(excluded)
def page_score(query,inventory,model):
    candidates=accepted(query,model);lengths={len(u) for u in candidates}
    assert len(lengths)==1
    length=next(iter(lengths));matches=[];exact=[];opportunities=[]
    for i,r in enumerate(inventory):
        raw=tuple(r['units']);form=canonical(raw,model)
        if len(form)==length:opportunities.append(i)
        if raw==query:exact.append(i)
        if form in candidates:matches.append(i)
    if model not in MAPS:assert set(exact)<=set(matches)
    extra=sorted(set(matches)-set(exact))
    n=len(opportunities);m=len(matches)
    return dict(total_words=len(inventory),query_length=length,opportunities=n,matches=m,binary=int(m>0),
        exact_matches=len(exact),exact_binary=int(bool(exact)),additional_matches=len(extra),
        additional_occurrence_binary=int(bool(extra)),binary_gain=int(m>0)-int(bool(exact)),
        rate=Fraction(m,n) if n else None,
        match_indices=matches,exact_match_indices=exact,additional_match_indices=extra,
        opportunity_indices=opportunities)
def avg(values):
    values=list(values)
    return sum(values,Fraction())/len(values) if values else None
def donor_summary(page_rows,threshold):
    """Threshold is LEAF TOTAL N; eligible page rates averaged only for page N>0."""
    grouped=defaultdict(list)
    for r in page_rows:grouped[r['leaf']].append(r)
    leafrows=[]
    for leaf,rr in sorted(grouped.items()):
        total=sum(r['score']['opportunities'] for r in rr)
        rate=avg(r['score']['rate'] for r in rr if r['score']['rate'] is not None) if total>=threshold else None
        leafrows.append(dict(leaf=leaf,pages=[r['folio'] for r in rr],opportunities=total,
            binary=avg(Fraction(r['score']['binary']) for r in rr),
            binary_gain=avg(Fraction(r['score']['binary_gain']) for r in rr),
            additional_occurrence_binary=avg(Fraction(r['score']['additional_occurrence_binary']) for r in rr),
            conditional_rate=rate,conditional_pages=[r['folio'] for r in rr if r['score']['opportunities']>0] if rate is not None else []))
    rates=[r['conditional_rate'] for r in leafrows if r['conditional_rate'] is not None]
    return dict(leaves=leafrows,leaf_count=len(leafrows),
        binary=avg(r['binary'] for r in leafrows),binary_gain=avg(r['binary_gain'] for r in leafrows),
        additional_occurrence_binary=avg(r['additional_occurrence_binary'] for r in leafrows),
        conditional_rate=avg(rates),conditional_leaf_count=len(rates))
def paired_result(query,target,donors,model):
    active=(len(accepted(query,model))>1 if model not in MAPS else canonical(query,model)!=query)
    result=dict(model=model,mechanism_active=active,target=target,donor_pages=donors,
        query_original=''.join(query),query_canonical=''.join(canonical(query,model)),
        accepted_forms=sorted(''.join(u) for u in accepted(query,model)),
        candidate_count=len(accepted(query,model)),endpoints={})
    for threshold in [1,5]:
        ds=donor_summary(donors,threshold)
        conditional_ok=target['opportunities']>=threshold and ds['conditional_leaf_count']>=2
        result['endpoints']['min'+str(threshold)]=dict(donor=ds,
            binary_delta=Fraction(target['binary'])-ds['binary'] if ds['binary'] is not None else None,
            binary_gain_delta=Fraction(target['binary_gain'])-ds['binary_gain'] if ds['binary_gain'] is not None else None,
            additional_binary_delta=Fraction(target['additional_occurrence_binary'])-ds['additional_occurrence_binary'] if ds['additional_occurrence_binary'] is not None else None,
            conditional_delta=target['rate']-ds['conditional_rate'] if conditional_ok else None,
            conditional_status='supported' if conditional_ok else ('target_below_threshold' if target['opportunities']<threshold else 'fewer_than_two_supported_control_leaves'))
    return result
def grouped_mean(rows,field,group):
    """Equal within group, then equal groups. None values excluded ONLY for conditional diagnostics."""
    gg=defaultdict(list)
    for r in rows:
        value=r[field]
        if value is not None:gg[r[group]].append(value)
    means={g:avg(v) for g,v in sorted(gg.items())}
    return dict(value=avg(means.values()),groups=means,group_count=len(means),
        candidate_count=sum(len(x) for x in gg.values()),
        weights={r['pair_id']:Fraction(1,len(gg)*len(gg[r[group]])) for r in rows if r[field] is not None})
def aggregate(candidate_rows,model):
    rr=[]
    for c in candidate_rows:
        p=c['models'][model];e=p['endpoints']
        rr.append(dict(pair_id=c['pair_id'],source_leaf=c['source_leaf'],target_leaf=c['target_leaf'],active=p['mechanism_active'],
            binary=e['min1']['binary_delta'],gain=e['min1']['binary_gain_delta'],additional=e['min1']['additional_binary_delta'],
            conditional1=e['min1']['conditional_delta'],conditional5=e['min5']['conditional_delta']))
    assert all(r['binary'] is not None for r in rr),'Missing donor support cannot silently change main weights'
    fields=['binary','gain','additional','conditional1','conditional5']
    out={'fixed_all_candidate_count':len(rr),'candidate_rows':rr,'primary_source_leaf':{},'diagnostics':{}}
    for field in fields:
        out['primary_source_leaf'][field]=grouped_mean(rr,field,'source_leaf')
    out['diagnostics']['target_leaf_equal']={f:grouped_mean(rr,f,'target_leaf') for f in fields}
    out['diagnostics']['candidate_equal']={f:avg(r[f] for r in rr if r[f] is not None) for f in fields}
    active=[r for r in rr if r['active']]
    out['diagnostics']['active_only']={f:grouped_mean(active,f,'source_leaf') for f in fields}
    for group in ['source_leaf','target_leaf']:
        out['diagnostics']['leave_one_'+group+'_out']={g:{f:grouped_mean([r for r in rr if r[group]!=g],f,'source_leaf') for f in fields} for g in sorted({r[group] for r in rr})}
    return out
def collisions(inventories,labels,model):
    forms=defaultdict(Counter)
    for inv in inventories.values():
        for r in inv:forms[''.join(canonical(tuple(r['units']),model))][r['word']]+=1
    for word in labels:forms[''.join(canonical(units(word),model))][word]+=1
    merged=[dict(canonical=k,canonical_length=len(units(k)),raw_types=dict(sorted(c.items()))) for k,c in sorted(forms.items()) if len(c)>1]
    return dict(model=model,scope='All parsed manuscript body words retained in this boundary condition, plus 11 source labels; occurrence counts combine these populations.',
        canonical_type_count=len(forms),collision_group_count=len(merged),collision_groups=merged)
def labels_for(records,version):
    main=[];excluded=[]
    for r in records:
        loci=[]
        for l in r['label_records'][version]:
            raw=re.sub(r'<[^>]*>','',l['raw'])
            ws=raw.split('.')
            for w in ws:units(w)
            loci.append(dict(locator=l['locator'],raw=l['raw'],words=ws))
        count=sum(len(l['words']) for l in loci)
        if r['fragment_id']==110:
            assert len(loci)==2 and count==3
            excluded.append(dict(pair_id=r['pair_id'],reason='multi_locus_three_word_group_not_executed',loci=loci));continue
        assert len(loci)==1 and count==1
        main.append(dict(record=r,word=loci[0]['words'][0],loci=loci))
    assert len(main)==11 and len(excluded)==1
    return main,excluded
def select_donors(pages,source,target,control):
    leaf_hi=defaultdict(set)
    for p in pages:leaf_hi[p['leaf']].add((p['H'],p['I']))
    donors=[];reject=[]
    for p in pages:
        if (p['H'],p['I'])!=(target['H'],target['I']):continue
        reason=None
        if p['leaf'] in {source['leaf'],target['leaf']}:reason='source_or_target_physical_leaf'
        elif control=='wholeleaf_HI' and len(leaf_hi[p['leaf']])!=1:reason='mixed_HI_donor_leaf'
        if reason:reject.append(dict(folio=p['folio'],leaf=p['leaf'],reason=reason))
        else:donors.append(p)
    return donors,reject
def analyze(data,records):
    """Called only after image gate in main; toys can use isolated low-level functions."""
    results={};inventories_out={};collision_out={}
    for version,d in data.items():
        pages={p['folio']:p for p in d['pages']};leaf_hi=defaultdict(set)
        for p in d['pages']:leaf_hi[p['leaf']].add((p['H'],p['I']))
        labels,excluded=labels_for(records,version)
        for boundary in ['strict_space','packet_tokens']:
            inv={};receipts={}
            for f,p in pages.items():inv[f],receipts[f]=words(p,boundary=='strict_space')
            inventories_out[version+'__'+boundary]=dict(pages=inv,excluded=receipts)
            collision_out[version+'__'+boundary]={m:collisions(inv,[l['word'] for l in labels],m) for m in MODELS}
            for control in ['page_HI','wholeleaf_HI']:
                candidates=[]
                for lab in labels:
                    r=lab['record'];source=pages[r['pharma_folio']];target=pages[r['herbal_folio']]
                    assert target['H'] in set('12345') and target['I']=='H'
                    donors,reject=select_donors(list(pages.values()),source,target,control)
                    row=dict(pair_id=r['pair_id'],fragment_id=r['fragment_id'],source_leaf=source['leaf'],target_leaf=target['leaf'],
                        source_folio=source['folio'],target_folio=target['folio'],source_grade=r['source_grade'],loci=lab['loci'],
                        target_H=target['H'],target_I=target['I'],target_leaf_mixed_HI=len(leaf_hi[target['leaf']])>1,
                        rejected_same_HI_donor_pages=reject,models={})
                    query=units(lab['word'])
                    for model in MODELS:
                        ts=page_score(query,inv[target['folio']],model)
                        ds=[dict(folio=p['folio'],leaf=p['leaf'],score=page_score(query,inv[p['folio']],model)) for p in donors]
                        row['models'][model]=paired_result(query,ts,ds,model)
                    for model in MODELS[1:7]:
                        mm=row['models'][model]
                        assert mm['target']['opportunities']==row['models']['exact']['target']['opportunities']
                        if not mm['mechanism_active']:
                            assert mm['target']['additional_matches']==0
                            assert all(p['score']['additional_matches']==0 for p in mm['donor_pages'])
                    expansion_support=[(row['models'][m]['target']['opportunities'],tuple(p['score']['opportunities'] for p in row['models'][m]['donor_pages'])) for m in MAPS]
                    assert len(set(expansion_support))==1,'Equal-length expansion controls lost identical opportunities'
                    candidates.append(row)
                key='__'.join([version,boundary,control])
                results[key]=dict(version=version,boundary=boundary,control=control,candidates=candidates,
                    excluded_three_word_group=excluded,aggregate={m:aggregate(candidates,m) for m in MODELS})
    return results,inventories_out,collision_out
def verify_image_gate(path,records):
    """A completed image-only review freeze, not merely a pre-review protocol freeze."""
    gate=read(path)
    assert gate['status']=='complete_image_review'
    assert gate['no_crossplant_lexical_results_read'] is True
    assert set(gate['pair_ids'])=={r['pair_id'] for r in records}
    assert gate['files'],'Image freeze must identify review artifacts'
    base=path.resolve().parent
    for rel,digest in gate['files'].items():
        f=(base/rel).resolve()
        assert f.is_relative_to(RUN.resolve()),'Image gate artifact outside current research window'
        assert sha(f)==digest,('Image review hash mismatch',rel)
    return gate
def main(args):
    if not args.execute:raise SystemExit('No real scoring. Supply --execute only after parent approval and completed image review freeze.')
    if args.output.exists():raise SystemExit('Output already exists; preserve every prior failure/result: '+str(args.output))
    args.output.mkdir(parents=True)
    try:
        records=[r for r in read(LABELS)['records'] if r['status']=='source_numbered_locator']
        assert [r['fragment_id'] for r in records]==EXPECTED
        assert args.image_review_freeze is not None
        gate=verify_image_gate(args.image_review_freeze,records)
        sources=[Path(__file__),HERE/'protocol_v1.txt',HERE/'test_run.py',INPUT,LABELS,HERE/'support_v1.json',args.image_review_freeze]
        frozen={str(p.relative_to(REPO)):sha(p) for p in sources}
        dump(args.output/'freeze.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),inputs=frozen,image_gate=gate,
            models=MODELS,scope='Exploratory preselected image-hypothesis pilot; no claim of independent semantic ground truth'))
        result,inventories,collision=analyze(read(INPUT),records)
        for name,x in inventories.items():dump(args.output/('inventory__'+name+'.json.gz'),x)
        for name,x in collision.items():dump(args.output/('collisions__'+name+'.json.gz'),x)
        for name,x in result.items():dump(args.output/(name+'.json.gz'),x)
        assert all(sha(p)==frozen[str(p.relative_to(REPO))] for p in sources),'An input changed during execution'
        dump(args.output/'complete.json',dict(status='complete',conditions=len(result),models=len(MODELS),
            candidates_per_condition=11,excluded_group_words=3,
            files={p.name:sha(p) for p in sorted(args.output.iterdir()) if p.is_file()}))
    except BaseException as exc:
        dump(args.output/'failure.json',dict(status='failed_preserved',exception=repr(exc),traceback=traceback.format_exc(),utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
        raise

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--image-review-freeze',type=Path)
    parser.add_argument('--output',type=Path,default=HERE/'run_v1')
    main(parser.parse_args())
