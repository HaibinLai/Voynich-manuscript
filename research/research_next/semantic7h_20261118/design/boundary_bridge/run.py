"""Fixed 36 boundary rules. Real run only after explicit execution flag and frozen toys."""
from pathlib import Path
from collections import defaultdict,Counter
from fractions import Fraction as F
import argparse,datetime,gzip,hashlib,itertools,json,re,traceback
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
REPO=HERE.parents[4]
INPUT=ROOT.parent/'label_body/saved_v1/input.json.gz'
LABELS=ROOT/'literature/label_support.json'
GATE=ROOT/'visual/crossplant/completed_image_freeze_v1.json'
CUTS=((0,0),(0,1),(1,0),(0,2),(1,1),(2,0))
def cutname(c):return f'L{c[0]}R{c[1]}'
RULES=[dict(id='q'+cutname(a)+'_b'+cutname(b),label_cut=a,body_cut=b,total_cut=sum(a)+sum(b)) for a,b in itertools.product(CUTS,repeat=2)]
BASE=RULES[0]['id']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_text())
def dump(p,x):
    def enc(x):
        if isinstance(x,F):return dict(num=x.numerator,den=x.denominator,value=float(x))
        raise TypeError(type(x))
    b=(json.dumps(x,ensure_ascii=False,allow_nan=False,separators=(',',':'),default=enc)+'\n').encode()
    p.write_bytes(gzip.compress(b,mtime=0) if p.suffix=='.gz' else b)
def units(w):
    u=tuple(re.findall(r"@\d{3};|[a-z']",w));assert ''.join(u)==w,w
    return u
def crop(u,cut):
    left,right=cut;end=len(u)-right
    if end-left<4:return None,'core_shorter_than_four'
    for i in range(len(u)-2):
        if u[i]=='c' and u[i+1] in 'fkpt' and u[i+2]=='h':
            if i<left<i+3 or i<end<i+3:return None,'boundary_inside_bench'
    return u[left:end],None
def mean(xx):
    xx=list(xx);return sum(xx,F())/len(xx) if xx else None
def build_inventory(pages):
    bank={}
    for p in pages:
        words=[];excluded=Counter()
        for row in p['body']:
            if row['uncertain_space']:excluded['uncertain_space_lines']+=1;continue
            for slot,w in enumerate(row['tokens']):
                if w is None:excluded['unresolved_tokens']+=1;continue
                words.append(dict(word=w,units=units(w),folio=p['folio'],locator=row['locator'],source_line=row.get('source_line'),slot=slot))
        variants={}
        for cut in CUTS:
            forms=[];reasons=[]
            for w in words:
                form,reason=crop(w['units'],cut);forms.append(form);reasons.append(reason)
            variants[cutname(cut)]=dict(forms=forms,invalid_reasons=reasons)
        bank[p['folio']]=dict(words=words,cuts=variants,excluded=dict(excluded))
    return bank
def page_score(core,inv,cut):
    forms=inv['cuts'][cutname(cut)]['forms']
    hits=[];opportunities=[]
    if core is not None:
        opportunities=[i for i,x in enumerate(forms) if x is not None and len(x)==len(core)]
        hits=[i for i in opportunities if forms[i]==core]
    n=len(opportunities);m=len(hits)
    return dict(body_words=len(inv['words']),valid_body_cores=sum(x is not None for x in forms),label_valid=core is not None,
        n=n,m=m,binary=int(bool(hits)),rate=F(m,n) if n else None,opportunity_indices=opportunities,hit_indices=hits)
def donor_stats(rows):
    byleaf=defaultdict(list)
    for row in rows:byleaf[row['leaf']].append(row)
    ll=[]
    for leaf,rr in sorted(byleaf.items()):
        ll.append(dict(leaf=leaf,pages=[r['folio'] for r in rr],binary=mean(F(r['score']['binary']) for r in rr),
            n=sum(r['score']['n'] for r in rr),rate=mean(r['score']['rate'] for r in rr if r['score']['rate'] is not None)))
    return dict(leaves=ll,count=len(ll),binary=mean(l['binary'] for l in ll),
        rate=mean(l['rate'] for l in ll if l['rate'] is not None),supported_leaf_count=sum(l['rate'] is not None for l in ll))
def contrast(target,donors):
    ds=donor_stats(donors);valid=target['label_valid']
    conditional=valid and target['n']>=1 and ds['supported_leaf_count']>=2
    return dict(donor=ds,target_binary=target['binary'],delta=F(target['binary'])-ds['binary'] if ds['binary'] is not None else None,
        conditional_delta=target['rate']-ds['rate'] if conditional else None,
        conditional_status='supported' if conditional else ('invalid_label' if not valid else 'target_zero_opportunity' if target['n']==0 else 'fewer_than_two_control_leaves'))
def group_mean(rows,field,group):
    gg=defaultdict(list)
    for r in rows:
        if r[field] is not None:gg[r[group]].append(r[field])
    means={k:mean(v) for k,v in sorted(gg.items())}
    return dict(value=mean(means.values()),groups=means,weights={r['pair_id']:F(1,len(gg)*len(gg[r[group]])) for r in rows if r[field] is not None},candidates=sum(len(v) for v in gg.values()))
def summary(candidates):
    contributions=[]
    for c in candidates:
        z=c['contrast']
        contributions.append(dict(pair_id=c['pair_id'],source_leaf=c['source_leaf'],target_leaf=c['target_leaf'],target=F(c['target']['binary']),
            control=z['donor']['binary'],delta=z['delta'],conditional_delta=z['conditional_delta']))
    hits=[c for c in candidates if c['target']['binary']]
    return dict(candidate_count=len(candidates),valid_labels=sum(c['label_valid'] for c in candidates),
        target_hit_candidates=len(hits),target_hit_source_leaves=sorted({c['source_leaf'] for c in hits}),target_hit_target_leaves=sorted({c['target_leaf'] for c in hits}),
        source_leaf={f:group_mean(contributions,f,'source_leaf') for f in ['target','control','delta','conditional_delta']},
        target_leaf={f:group_mean(contributions,f,'target_leaf') for f in ['target','control','delta','conditional_delta']},contributions=contributions)
def main_rules(data,records):
    pages={p['folio']:p for p in data['pages']};bank=build_inventory(data['pages'])
    labels=[];excluded=[]
    for r in records:
        raw=[dict(locator=l['locator'],raw=l['raw'],words=re.sub(r'<[^>]*>','',l['raw']).split('.')) for l in r['labels']]
        if r['fragment_id']==110:
            assert len(raw)==2 and sum(len(x['words']) for x in raw)==3
            excluded.append(dict(pair_id=r['pair_id'],reason='multi_locus_three_word_group_not_executed',loci=raw));continue
        assert len(raw)==1 and len(raw[0]['words'])==1
        labels.append((r,raw,units(raw[0]['words'][0])))
    assert len(labels)==11
    output={}
    for rule in RULES:
        candidates=[]
        for r,loci,label in labels:
            source=pages[r['pharma_folio']];target=pages[r['herbal_folio']]
            assert target['H'] in '12345' and target['I']=='H'
            core,reason=crop(label,rule['label_cut'])
            ts=page_score(core,bank[target['folio']],rule['body_cut'])
            dp=[p for p in pages.values() if (p['H'],p['I'])==(target['H'],target['I']) and p['leaf'] not in {source['leaf'],target['leaf']}]
            donors=[dict(folio=p['folio'],leaf=p['leaf'],score=page_score(core,bank[p['folio']],rule['body_cut'])) for p in dp]
            assert donors,'Fixed primary donor pool cannot be empty'
            candidates.append(dict(pair_id=r['pair_id'],fragment_id=r['fragment_id'],source_leaf=source['leaf'],target_leaf=target['leaf'],target_folio=target['folio'],source_folio=source['folio'],
                label_loci=loci,label_valid=core is not None,label_invalid_reason=reason,core=core,target=ts,donor_pages=donors,contrast=contrast(ts,donors)))
        output[rule['id']]=dict(rule=rule,candidates=candidates,summary=summary(candidates))
    return output,bank,excluded
def selection_key(rule,score):
    return (-score,rule['total_cut'],*rule['label_cut'],*rule['body_cut'])
def split_for_fold(candidates,held):
    test=[c for c in candidates if c['source_leaf']==held]
    held_targets={c['target_leaf'] for c in test}
    purge=[c for c in candidates if c['source_leaf']!=held and c['target_leaf'] in held_targets]
    train=[];cleared=[]
    for c in candidates:
        if c['source_leaf']==held or c['target_leaf'] in held_targets:continue
        removed=[r for r in c['donor_pages'] if r['leaf'] in held_targets]
        donors=[r for r in c['donor_pages'] if r['leaf'] not in held_targets]
        cc=dict(c,donor_pages=donors,contrast=contrast(c['target'],donors));train.append(cc)
        cleared.append(dict(pair_id=c['pair_id'],removed_pages=[r['folio'] for r in removed],removed_leaf_ids=sorted({r['leaf'] for r in removed}),
            removed_page_count=len(removed),removed_leaf_count=len({r['leaf'] for r in removed}),remaining_leaf_count=len({r['leaf'] for r in donors})))
    reason='fewer_than_two_training_source_leaves' if len({c['source_leaf'] for c in train})<2 else 'training_candidate_without_donor' if any(not c['donor_pages'] for c in train) else None
    return dict(train=train,test=test,purged_pair_ids=[c['pair_id'] for c in purge],held_target_leaves=sorted(held_targets),donor_clearance=cleared,status=reason or 'supported')
def loo(results):
    folds=[]
    for held in sorted({c['source_leaf'] for c in results[BASE]['candidates']}):
        all_rules=[]
        for rule in RULES:
            split=split_for_fold(results[rule['id']]['candidates'],held)
            train_summary=summary(split['train']) if split['status']=='supported' else None
            all_rules.append(dict(rule=rule,status=split['status'],training_pair_ids=[c['pair_id'] for c in split['train']],
                purged_pair_ids=split['purged_pair_ids'],held_target_leaves=split['held_target_leaves'],donor_clearance=split['donor_clearance'],training=train_summary))
        if any(r['status']!='supported' for r in all_rules):
            folds.append(dict(held_source_leaf=held,status='NA_training_support',all_rules=all_rules));continue
        chosen=min(all_rules,key=lambda x:selection_key(x['rule'],x['training']['source_leaf']['delta']['value']))
        selected=chosen['rule']['id'];sp=split_for_fold(results[selected]['candidates'],held)
        test=summary(sp['test']);base_test=summary(split_for_fold(results[BASE]['candidates'],held)['test'])
        folds.append(dict(held_source_leaf=held,status='complete',selected_rule=chosen['rule'],selected_training=chosen['training'],
            test=test,baseline_test=base_test,test_gain_vs_baseline=test['source_leaf']['delta']['value']-base_test['source_leaf']['delta']['value'],
            all_rules=all_rules,test_pair_ids=[c['pair_id'] for c in sp['test']]))
    good=[f for f in folds if f['status']=='complete']
    return dict(status='complete' if len(good)==4 else 'partial_NA',folds=folds,
        source_leaf_equal_test_delta=mean(f['test']['source_leaf']['delta']['value'] for f in good),
        source_leaf_equal_baseline_delta=mean(f['baseline_test']['source_leaf']['delta']['value'] for f in good),
        completed_folds=len(good),warning='Internal post-result selection; all materials exposed; four dependent-source folds are not blind confirmation or significance.')
def validate_gate():
    g=read(GATE);assert g['status']=='complete_image_review'
    for rel,h in g['files'].items():assert sha((GATE.parent/rel).resolve())==h
    return g
def main(args):
    if not args.execute:raise SystemExit('No real scoring without explicit --execute after toy freeze.')
    out=args.output.resolve();assert not out.exists(),'Never overwrite prior output'
    out.mkdir(parents=True)
    try:
        toys=read(HERE/'toy_receipt_v1.json');assert toys['status']=='passed'
        for rel,h in toys['files'].items():assert sha(HERE/rel)==h
        gate=validate_gate();prior=read(HERE.parent/'crossplant/run_v2/freeze.json')
        for p in [INPUT,LABELS]:assert sha(p)==prior['inputs'][str(p.relative_to(REPO))]
        inputs=[Path(__file__),HERE/'protocol_v1.txt',HERE/'test_run.py',HERE/'toy_receipt_v1.json',HERE/'support_primary_v1.json',INPUT,LABELS,GATE]
        hashes={str(p.relative_to(REPO)):sha(p) for p in inputs}
        dump(out/'freeze.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),inputs=hashes,rules=RULES,image_gate=gate,status='post_result_exploratory'))
        data=read(INPUT);raw=[r for r in read(LABELS)['records'] if r['status']=='source_numbered_locator'];table=[]
        for version in ['ZL','IT']:
            records=[dict(r,labels=r['label_records'][version]) for r in raw]
            rr,bank,excluded=main_rules(data[version],records)
            dump(out/(version+'_inventory.json.gz'),bank)
            dump(out/(version+'_main.json.gz'),dict(version=version,condition='strict_space/page_HI',rules=rr,excluded_group=excluded))
            table.extend(dict(version=version,rule=x['rule'],summary=x['summary']) for x in rr.values())
            dump(out/'main_table_partial.json',table)
            print(version,'36 primary rules saved',flush=True)
            diagnostics=loo(rr);dump(out/(version+'_loo.json.gz'),diagnostics)
            print(version,'4-fold internal selection saved',flush=True)
        dump(out/'main_table_72.json',table)
        assert len(table)==72
        assert all(sha(p)==hashes[str(p.relative_to(REPO))] for p in inputs)
        dump(out/'complete.json',dict(status='complete',main_rows=72,versions=2,rules=36,candidates=11,folds_per_version=4,
            files={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()}))
    except BaseException as e:
        dump(out/'failure.json',dict(status='failed_preserved',error=repr(e),traceback=traceback.format_exc()))
        raise
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');parser.add_argument('--output',type=Path,default=HERE/'run_v1');main(parser.parse_args())
