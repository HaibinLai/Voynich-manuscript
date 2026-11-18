"""Four fixed space mechanisms, with preserved raw-tag barriers and original slots."""
from pathlib import Path
from collections import defaultdict
from fractions import Fraction as F
import argparse,datetime,gzip,hashlib,json,re,traceback
import support as parser
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
REPO=HERE.parents[4]
INPUT=parser.INPUT
LABELS=parser.LABELS
GATE=ROOT/'visual/crossplant/completed_image_freeze_v1.json'
MODELS=['exact','adjacent_forward','adjacent_reverse','gap2_forward']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_text())
def dump(p,x):
    def enc(v):
        if isinstance(v,F):return dict(num=v.numerator,den=v.denominator,value=float(v))
        raise TypeError(type(v))
    b=(json.dumps(x,ensure_ascii=False,allow_nan=False,separators=(',',':'),default=enc)+'\n').encode()
    p.write_bytes(gzip.compress(b,mtime=0) if p.suffix=='.gz' else b)
def mean(v):
    v=list(v);return sum(v,F())/len(v) if v else None
def build_inventory(pages,strict):
    output={}
    for p in pages:
        rows=[];excluded=[]
        for row in p['body']:
            recovered=parser.recover(row)
            if strict and row['uncertain_space']:
                excluded.append(dict(locator=row['locator'],reason='uncertain_space_line'));continue
            if not recovered['packet_reproduced']:
                excluded.append(dict(locator=row['locator'],reason='packet_reconstruction_mismatch'));continue
            rows.append(recovered)
        output[p['folio']]=dict(rows=rows,excluded=excluded)
    return output
def opportunity_id(locator,slots):return locator+':'+','.join(map(str,slots))
def page_score(query,inventory):
    length=len(parser.units(query));forbidden=parser.bench_seams(query)
    out={m:dict(opportunities=[],hits=[]) for m in MODELS}
    for row in inventory['rows']:
        assert row['packet_reproduced']
        for t in row['tokens']:
            if not t['comparable'] or t['length']!=length:continue
            occurrence=dict(id=opportunity_id(row['locator'],[t['slot']]),locator=row['locator'],source_line=row['source_line'],slots=[t['slot']],ordered_slots=[t['slot']],words=[t['word']],joined=t['word'])
            out['exact']['opportunities'].append(occurrence)
            if t['word']==query:out['exact']['hits'].append(occurrence)
        for model,gap in [('adjacent_forward',1),('adjacent_reverse',1),('gap2_forward',2)]:
            ww,_=parser.windows(row,gap)
            for w in ww:
                if w['total_length']!=length or w['left_length'] in forbidden or w['right_length'] in forbidden:continue
                slots=w['slots'];order=list(reversed(slots)) if model=='adjacent_reverse' else slots
                words=[row['tokens'][i]['word'] for i in order];joined=''.join(words)
                occurrence=dict(id=opportunity_id(row['locator'],slots),locator=row['locator'],source_line=row['source_line'],slots=slots,ordered_slots=order,
                    span_slots=w['span_slots'],words=words,joined=joined,component_lengths=[row['tokens'][i]['length'] for i in order],uncertain_space=row['uncertain_space'])
                out[model]['opportunities'].append(occurrence)
                if joined==query:out[model]['hits'].append(occurrence)
    baseline=int(bool(out['exact']['hits']))
    for m,s in out.items():
        n=len(s['opportunities']);hits=len(s['hits']);binary=int(bool(hits));union=int(bool(binary or baseline))
        s.update(n=n,m=hits,binary=binary,rate=F(hits,n) if n else None,exact_binary=baseline,union_binary=union,coverage_gain=union-baseline,
            join_occurrence_present=binary if m!='exact' else 0)
    assert [x['id'] for x in out['adjacent_forward']['opportunities']]==[x['id'] for x in out['adjacent_reverse']['opportunities']]
    return out
def donor_stats(donors,model):
    grouped=defaultdict(list)
    for r in donors:grouped[r['leaf']].append(r)
    leaves=[]
    for leaf,rr in sorted(grouped.items()):
        scores=[r['models'][model] for r in rr]
        leaves.append(dict(leaf=leaf,pages=[r['folio'] for r in rr],n=sum(s['n'] for s in scores),
            binary=mean(F(s['binary']) for s in scores),exact_binary=mean(F(s['exact_binary']) for s in scores),
            union_binary=mean(F(s['union_binary']) for s in scores),coverage_gain=mean(F(s['coverage_gain']) for s in scores),
            join_occurrence_present=mean(F(s['join_occurrence_present']) for s in scores),rate=mean(s['rate'] for s in scores if s['rate'] is not None)))
    return dict(leaves=leaves,leaf_count=len(leaves),supported_leaves=sum(l['rate'] is not None for l in leaves),
        **{f:mean(l[f] for l in leaves) for f in ['binary','exact_binary','union_binary','coverage_gain','join_occurrence_present']},
        rate=mean(l['rate'] for l in leaves if l['rate'] is not None))
def contrast(target,donors,model):
    s=target[model];d=donor_stats(donors,model);assert d['leaf_count']>0
    conditional=s['n']>=1 and d['supported_leaves']>=2
    return dict(donor=d,**{f+'_delta':F(s[f])-d[f] for f in ['binary','exact_binary','union_binary','coverage_gain','join_occurrence_present']},
        conditional_delta=s['rate']-d['rate'] if conditional else None,
        conditional_status='supported' if conditional else ('target_zero_opportunity' if s['n']==0 else 'fewer_than_two_control_leaves'))
def grouped(rows,field,group):
    gg=defaultdict(list)
    for r in rows:
        if r[field] is not None:gg[r[group]].append(r[field])
    values={g:mean(v) for g,v in sorted(gg.items())}
    return dict(value=mean(values.values()),groups=values,candidates=sum(len(v) for v in gg.values()),
        weights={r['pair_id']:F(1,len(gg)*len(gg[r[group]])) for r in rows if r[field] is not None})
def summarize(candidates,model):
    fields=['binary','exact_binary','union_binary','coverage_gain','join_occurrence_present'];rr=[]
    for c in candidates:
        t=c['target'][model];z=c['contrasts'][model]
        row=dict(pair_id=c['pair_id'],source_leaf=c['source_leaf'],target_leaf=c['target_leaf'],conditional_delta=z['conditional_delta'])
        for f in fields:row.update({f+'_target':F(t[f]),f+'_control':z['donor'][f],f+'_delta':z[f+'_delta']})
        rr.append(row)
    metrics=[f+s for f in fields for s in ['_target','_control','_delta']]+['conditional_delta']
    hit=[c for c in candidates if c['target'][model]['binary']]
    gain=[c for c in candidates if c['target'][model]['coverage_gain']]
    return dict(candidate_count=len(candidates),target_hit_candidates=len(hit),target_hit_source_leaves=sorted({c['source_leaf'] for c in hit}),
        target_hit_target_leaves=sorted({c['target_leaf'] for c in hit}),target_newly_covered_candidates=len(gain),
        source_leaf={f:grouped(rr,f,'source_leaf') for f in metrics},target_leaf={f:grouped(rr,f,'target_leaf') for f in metrics},contributions=rr)
def analyze(data,records,boundary):
    pages={p['folio']:p for p in data['pages']};inventory=build_inventory(data['pages'],boundary=='strict_space');candidates=[];excluded=[]
    for r in records:
        labels=[dict(locator=l['locator'],raw=l['raw'],words=re.sub('<[^>]*>','',l['raw']).split('.')) for l in r['labels']]
        if r['fragment_id']==110:
            assert len(labels)==2 and sum(len(l['words']) for l in labels)==3
            excluded.append(dict(pair_id=r['pair_id'],reason='two_locus_three_word_group_not_executed',loci=labels));continue
        assert len(labels)==1 and len(labels[0]['words'])==1
        query=labels[0]['words'][0];source=pages[r['pharma_folio']];target=pages[r['herbal_folio']]
        assert target['H'] in '12345' and target['I']=='H'
        ts=page_score(query,inventory[target['folio']])
        dp=[p for p in pages.values() if (p['H'],p['I'])==(target['H'],target['I']) and p['leaf'] not in {source['leaf'],target['leaf']}]
        ds=[dict(folio=p['folio'],leaf=p['leaf'],models=page_score(query,inventory[p['folio']])) for p in dp]
        candidates.append(dict(pair_id=r['pair_id'],fragment_id=r['fragment_id'],query=query,label_loci=labels,source_leaf=source['leaf'],source_folio=source['folio'],
            target_leaf=target['leaf'],target_folio=target['folio'],target=ts,donor_pages=ds,contrasts={m:contrast(ts,ds,m) for m in MODELS}))
    assert len(candidates)==11
    return dict(condition=boundary+'/page_HI',candidates=candidates,excluded_group=excluded,models={m:summarize(candidates,m) for m in MODELS}),inventory
def main(args):
    if not args.execute:raise SystemExit('No real matching without explicit --execute after toy freeze.')
    out=args.output.resolve();assert not out.exists(),'Preserve old run'
    out.mkdir(parents=True)
    try:
        toy=read(HERE/'toy_receipt_v1.json');assert toy['status']=='passed'
        for n,h in toy['files'].items():assert sha(HERE/n)==h
        gate=read(GATE);assert gate['status']=='complete_image_review'
        for n,h in gate['files'].items():assert sha((GATE.parent/n).resolve())==h
        inputs=[Path(__file__),HERE/'support.py',HERE/'protocol_v1.txt',HERE/'test_run.py',HERE/'toy_receipt_v1.json',HERE/'support_v1.json',INPUT,LABELS,GATE]
        hashes={str(p.relative_to(REPO)):sha(p) for p in inputs}
        dump(out/'freeze.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),inputs=hashes,models=MODELS,status='post_result_exploratory',image_gate=gate))
        data=read(INPUT);raw=[r for r in read(LABELS)['records'] if r['status']=='source_numbered_locator'];table=[]
        for version in ['ZL','IT']:
            records=[dict(r,labels=r['label_records'][version]) for r in raw]
            for boundary in ['strict_space','packet_tokens']:
                result,inventory=analyze(data[version],records,boundary);result['version']=version
                key=version+'__'+boundary
                dump(out/(key+'.json.gz'),result);dump(out/('inventory__'+key+'.json.gz'),inventory)
                table.extend(dict(version=version,boundary=boundary,model=m,summary=result['models'][m]) for m in MODELS)
                dump(out/'summary_partial.json',table);print(key,'completed',flush=True)
        dump(out/'summary_16.json',table);assert len(table)==16
        assert all(sha(p)==hashes[str(p.relative_to(REPO))] for p in inputs)
        dump(out/'complete.json',dict(status='complete',conditions=4,models=4,candidates=11,files={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()}))
    except BaseException as e:
        dump(out/'failure.json',dict(status='failed_preserved',error=repr(e),traceback=traceback.format_exc()));raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--output',type=Path,default=HERE/'run_v1');main(p.parse_args())
