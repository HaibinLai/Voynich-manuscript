"""POST-RESULT design support only: lengths/counts, never compares label/body cores."""
from pathlib import Path
from collections import Counter,defaultdict
import gzip,hashlib,itertools,json,re
HERE=Path(__file__).resolve().parent
RUN=HERE.parents[1]
REPO=HERE.parents[4]
INPUT=RUN.parent/'label_body/saved_v1/input.json.gz'
LABELS=RUN/'literature/label_support.json'
CUTS=[(0,0),(0,1),(1,0),(0,2),(1,1),(2,0)]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def uu(w):
    tokens=re.findall(r"@\d{3};|[a-z']",w)
    assert ''.join(tokens)==w
    return tokens
def eligibility(word,left,right):
    """Returns ONLY eligibility/reason/length. It never emits a core string."""
    tokens=uu(word);n=len(tokens);stop=n-right
    if n-left-right<4:return False,'core_shorter_than_four',n-left-right
    spans=[(i,i+3) for i in range(n-2) if tokens[i]=='c' and tokens[i+1] in 'tfkp' and tokens[i+2]=='h']
    if any(a<left<b or a<stop<b for a,b in spans):return False,'boundary_inside_bench',n-left-right
    return True,None,n-left-right
def name(c):return f'L{c[0]}R{c[1]}'
def histogram(page,strict,cut):
    hist=Counter();reject=Counter();count=0
    for row in page['body']:
        if strict and row['uncertain_space']:
            reject['uncertain_space_lines']+=1;continue
        for word in row['tokens']:
            if word is None:reject['unresolved_tokens']+=1;continue
            count+=1;valid,reason,n=eligibility(word,*cut)
            if valid:hist[n]+=1
            else:reject[reason]+=1
    return dict(body_word_count_before_cut=count,core_length_counts=dict(sorted(hist.items())),exclusions=dict(reject))
def main():
    assert not (HERE/'support_v1.json').exists(),'Do not overwrite a design support snapshot'
    data=json.loads(gzip.decompress(INPUT.read_bytes()));ls=json.loads(LABELS.read_text())
    records=[r for r in ls['records'] if r['status']=='source_numbered_locator' and r['fragment_id']!=110]
    assert len(records)==11
    rules=[dict(id='q'+name(a)+'_b'+name(b),label_cut=list(a),body_cut=list(b),total_cut=sum(a)+sum(b)) for a,b in itertools.product(CUTS,repeat=2)]
    output=dict(status='post_result_exploratory_support_only_not_frozen',no_core_identity_comparison=True,
        source_hashes={str(p.relative_to(REPO)):sha(p) for p in [INPUT,LABELS,Path(__file__)]},cuts=CUTS,rules=rules,conditions={},body_histograms={},query_support={})
    for version,d in data.items():
        pages={p['folio']:p for p in d['pages']};leafhi=defaultdict(set)
        for p in d['pages']:leafhi[p['leaf']].add((p['H'],p['I']))
        qq={}
        for r in records:
            lr=r['label_records'][version];assert len(lr)==1
            word=re.sub(r'<[^>]*>','',lr[0]['raw']);assert '.' not in word
            qq[r['pair_id']]=dict(fragment_id=r['fragment_id'],label_raw=word,source_folio=r['pharma_folio'],target_folio=r['herbal_folio'],
                source_leaf=pages[r['pharma_folio']]['leaf'],target_leaf=pages[r['herbal_folio']]['leaf'],raw_length=len(uu(word)),
                cuts={name(c):dict(zip(['valid','reason','core_length'],eligibility(word,*c))) for c in CUTS})
        output['query_support'][version]=qq
        for boundary in ['strict_space','packet_tokens']:
            hh={folio:{name(c):histogram(p,boundary=='strict_space',c) for c in CUTS} for folio,p in pages.items()}
            output['body_histograms'][version+'__'+boundary]=hh
            for control in ['page_HI','wholeleaf_HI']:
                rows=[]
                for r in records:
                    q=qq[r['pair_id']];t=pages[r['herbal_folio']]
                    donors=[p for p in pages.values() if (p['H'],p['I'])==(t['H'],t['I']) and p['leaf'] not in {q['source_leaf'],q['target_leaf']} and (control=='page_HI' or len(leafhi[p['leaf']])==1)]
                    for rule in rules:
                        query=q['cuts'][name(rule['label_cut'])];length=query['core_length'];bc=name(rule['body_cut'])
                        n=hh[t['folio']][bc]['core_length_counts'].get(length,0) if query['valid'] else 0
                        donors_by_leaf=defaultdict(dict)
                        for p in donors:donors_by_leaf[p['leaf']][p['folio']]=hh[p['folio']][bc]['core_length_counts'].get(length,0) if query['valid'] else 0
                        leafn={leaf:sum(pp.values()) for leaf,pp in donors_by_leaf.items()}
                        rows.append(dict(pair_id=r['pair_id'],fragment_id=r['fragment_id'],source_leaf=q['source_leaf'],target_leaf=q['target_leaf'],rule=rule['id'],
                            label_valid=query['valid'],label_invalid_reason=query['reason'],core_length=length,target_opportunities=n,
                            control_leaf_count=len(donors_by_leaf),control_pages_by_leaf=donors_by_leaf,
                            control_leaf_opportunity_sums=leafn,control_leaf_min1=sum(x>=1 for x in leafn.values()),control_leaf_min5=sum(x>=5 for x in leafn.values()),
                            conditional_min1_supported=query['valid'] and n>=1 and sum(x>=1 for x in leafn.values())>=2,
                            conditional_min5_supported=query['valid'] and n>=5 and sum(x>=5 for x in leafn.values())>=2))
                summary={}
                for rule in rules:
                    rr=[r for r in rows if r['rule']==rule['id']]
                    summary[rule['id']]=dict(valid_labels=sum(r['label_valid'] for r in rr),target_opportunity_candidates=sum(r['target_opportunities']>0 for r in rr),
                        source_leaves_with_target_opportunity=len({r['source_leaf'] for r in rr if r['target_opportunities']>0}),
                        target_leaves_with_target_opportunity=len({r['target_leaf'] for r in rr if r['target_opportunities']>0}),
                        conditional_min1_supported=sum(r['conditional_min1_supported'] for r in rr),conditional_min5_supported=sum(r['conditional_min5_supported'] for r in rr))
                output['conditions']['__'.join([version,boundary,control])]=dict(rows=rows,summary=summary)
    output['leave_source_leaf_out_training_plan']=[]
    qq=output['query_support']['ZL']
    for held in sorted({x['source_leaf'] for x in qq.values()}):
        test=[k for k,x in qq.items() if x['source_leaf']==held];targets={qq[k]['target_leaf'] for k in test}
        train=[k for k,x in qq.items() if x['source_leaf']!=held and x['target_leaf'] not in targets]
        purged=[k for k,x in qq.items() if x['source_leaf']!=held and x['target_leaf'] in targets]
        output['leave_source_leaf_out_training_plan'].append(dict(held_source_leaf=held,test_pair_ids=test,training_pair_ids=train,shared_target_leaf_purged_pair_ids=purged))
    (HERE/'support_v1.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print('Rules',len(rules),'candidates',len(records),'conditions',len(output['conditions']))
    for version,qq in output['query_support'].items():
        print(version,[(x['fragment_id'],x['raw_length'],[k for k,c in x['cuts'].items() if not c['valid']]) for x in qq.values()])
    for condition,d in output['conditions'].items():
        print(condition,'target_opportunity_candidates range',min(x['target_opportunity_candidates'] for x in d['summary'].values()),max(x['target_opportunity_candidates'] for x in d['summary'].values()),'conditional1 range',min(x['conditional_min1_supported'] for x in d['summary'].values()),max(x['conditional_min1_supported'] for x in d['summary'].values()))
if __name__=='__main__':main()
