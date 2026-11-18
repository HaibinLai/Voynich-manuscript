# -*- coding: utf-8 -*-
"""Independent exact-arithmetic replay for fixed gallows windows and strata.

No production analysis, model, parser or earlier audit is imported.  The core
uses one target site per saved word occurrence and original EVA unit sequences.
"""
from pathlib import Path
from fractions import Fraction
import argparse
import collections
import datetime
import gzip
import hashlib
import json
import re
import sys
import traceback

PAIRS=(('f','k'),('f','p'),('f','t'),('k','p'),('k','t'),('p','t'))
WINDOWS=((4,1,'l','a'),(5,1,'c','h'))  # j is zero based here.
TOKEN=re.compile(r"@[0-9]{3};|[a-z']")


def original_units(value):
    if isinstance(value,(list,tuple)):
        result=tuple(value)
        if any(not isinstance(v,str) or TOKEN.fullmatch(v) is None for v in result):
            raise ValueError('Invalid original unit')
    elif isinstance(value,str):
        result=[];offset=0
        while offset<len(value):
            match=TOKEN.match(value,offset)
            if match is None:raise ValueError('Invalid original string at '+str(offset))
            result.append(match.group());offset=match.end()
        result=tuple(result)
    else:raise TypeError('Expected unit list or original string')
    if not result:raise ValueError('Empty word')
    return result


def observations(records,pair,window,axes=()):
    pair=tuple(pair);length,j,left,right=window
    if len(pair)!=2 or pair[0]==pair[1] or not 0<=j<length:raise ValueError('Invalid pair/window')
    result=[]
    for i,record in enumerate(records):
        word=original_units(record['word'])
        if len(word)!=length or word[j] not in pair:continue
        flank_left=word[j-1] if j else '<BOS>'
        flank_right=word[j+1] if j+1<length else '<EOS>'
        result.append(dict(record_index=i,word=word,position=j,symbol=word[j],
                           leaf=record['leaf'],folio=record.get('folio'),
                           focal=(flank_left==left and flank_right==right),
                           labels={axis:record.get(axis,'<missing>') for axis in axes}))
    return result


def exact_match(events,pair):
    """Rebuild matching and eligibility after every filtering/deletion step."""
    first,second=pair
    block=collections.defaultdict(collections.Counter)
    center=collections.defaultdict(collections.Counter)
    focal=[]
    for event in events:
        block[event['leaf']][event['symbol']]+=1
        if event['focal']:
            center[event['leaf']][event['symbol']]+=1;focal.append(event)
    references={};leaf_rows=[]
    for leaf,counts in sorted(center.items()):
        total=block[leaf];a,b=counts[first],counts[second]
        ra,rb=total[first]-a,total[second]-b
        if ra+rb<3 or total[first]==0 or total[second]==0:continue
        p=Fraction(ra,ra+rb);references[leaf]=p
        leaf_rows.append(dict(leaf=leaf,counts={first:a,second:b},rest={first:ra,second:rb},
                              n=a+b,reference=p,expected_first=(a+b)*p,
                              residual=Fraction(a)-(a+b)*p))
    eligible=[]
    for event in focal:
        if event['leaf'] in references:
            residual=Fraction(event['symbol']==first)-references[event['leaf']]
            eligible.append(dict(event,residual=residual,reference=references[event['leaf']]))
    n=len(eligible);a=sum(event['symbol']==first for event in eligible)
    residual=sum((event['residual'] for event in eligible),Fraction(0))
    delta=residual/n if n else None
    direction=0 if delta is None or delta==0 else 1 if delta>0 else -1
    agreement=sum(row['residual']*direction>0 for row in leaf_rows) if direction else 0
    omitted=[(residual-row['residual'])/(n-row['n']) for row in leaf_rows if n>row['n']]
    return dict(total_focal=len(focal),eligible=n,counts={first:a,second:n-a},
                counts_all={g:sum(e['symbol']==g for e in focal) for g in pair},
                leaves=len(leaf_rows),observed_first=Fraction(a,n) if n else None,
                expected_first=(Fraction(a)-residual)/n if n else None,
                residual=residual,difference=delta,consistent_leaves=agreement,
                loo_min=min(omitted) if omitted else None,loo_max=max(omitted) if omitted else None,
                by_leaf=leaf_rows,eligible_events=eligible)


def decompose_original(events,pair,axis):
    """Partition the original matched residual without changing its reference."""
    matched=exact_match(events,pair);groups={}
    labels=sorted({e['labels'][axis] for e in events if e['focal']})
    for value in labels:
        all_focal=[e for e in events if e['focal'] and e['labels'][axis]==value]
        kept=[e for e in matched['eligible_events'] if e['labels'][axis]==value]
        n=len(kept);residual=sum((e['residual'] for e in kept),Fraction(0))
        groups[value]=dict(total_focal=len(all_focal),eligible=n,
                           counts={g:sum(e['symbol']==g for e in kept) for g in pair},
                           leaves=len({e['leaf'] for e in kept}),residual=residual,
                           difference=residual/n if n else None,
                           contribution=residual/matched['eligible'] if matched['eligible'] else None)
    assert sum(g['eligible'] for g in groups.values())==matched['eligible']
    assert sum((g['residual'] for g in groups.values()),Fraction(0))==matched['residual']
    return matched,groups


def rematch_by_layer(events,pair,axis):
    """References and eligibility are rebuilt within each leaf/layer block."""
    groups={}
    for label in sorted({e['labels'][axis] for e in events}):
        groups[label]=exact_match([e for e in events if e['labels'][axis]==label],pair)
    n=sum(group['eligible'] for group in groups.values())
    residual=sum((group['residual'] for group in groups.values()),Fraction(0))
    return dict(eligible=n,residual=residual,difference=residual/n if n else None,groups=groups)


def wordtype_contributions(events,pair):
    matched=exact_match(events,pair);types={}
    for event in matched['eligible_events']:
        key=event['word']
        if key not in types:types[key]=dict(events=0,residual=Fraction(0),leaves=set())
        types[key]['events']+=1;types[key]['residual']+=event['residual'];types[key]['leaves'].add(event['leaf'])
    return types


def delete_types(events,removed):
    removed=set(removed)
    return [event for event in events if event['word'] not in removed]


def deduplicate(events):
    """Leaf/complete-word/site dedup; no unique layer/page label is inferred."""
    used=set();result=[];labels=collections.defaultdict(lambda:collections.defaultdict(set))
    for event in events:
        key=event['leaf'],event['word'],event['position']
        for axis,value in event['labels'].items():labels[key][axis].add(value)
        if key not in used:result.append(event);used.add(key)
    ambiguity=collections.Counter(axis for axes in labels.values() for axis,values in axes.items() if len(values)>1)
    return result,dict(ambiguity)


def summarize_blocks(blocks,pair,original_reference=None):
    """Independent four-count sufficient statistics; collapse blocks by leaf for LOO."""
    first,second=pair;raw=[0,0];kept=[0,0];contribution=Fraction(0)
    per_leaf={};accepted=[]
    for key,values in sorted(blocks.items()):
        a,b,ra,rb=values;leaf=key[0]
        if min(values)<0:raise ValueError('Deletion produced negative support')
        raw[0]+=a;raw[1]+=b
        if a+b==0 or ra+rb<3 or a+ra==0 or b+rb==0:continue
        reference=Fraction(ra,ra+rb) if original_reference is None else original_reference[leaf]
        residual=Fraction(a)-(a+b)*reference
        kept[0]+=a;kept[1]+=b;contribution+=residual
        if leaf not in per_leaf:per_leaf[leaf]=[0,Fraction(0)]
        per_leaf[leaf][0]+=a+b;per_leaf[leaf][1]+=residual
        accepted.append(dict(key=key,counts=[a,b],rest=[ra,rb],reference=reference))
    n=sum(kept);difference=contribution/n if n else None
    sign=0 if difference is None or difference==0 else 1 if difference>0 else -1
    omitted=[(contribution-r)/(n-k) for k,r in per_leaf.values() if n>k]
    return dict(total_focal=sum(raw),eligible=n,counts=dict(zip(pair,kept)),counts_all=dict(zip(pair,raw)),
                leaves=len(per_leaf),observed_first=Fraction(kept[0],n) if n else None,
                expected_first=(Fraction(kept[0])-contribution)/n if n else None,
                residual=contribution,difference=difference,
                consistent_leaves=sum(sign*r>0 for k,r in per_leaf.values()) if sign else 0,
                loo_min=min(omitted) if omitted else None,loo_max=max(omitted) if omitted else None,
                accepted_blocks=accepted,leaf_contributions=per_leaf)


class Sufficient:
    def __init__(self,events,pair,axis=None):
        self.pair=tuple(pair);self.blocks={};self.words={};self.frames={}
        for event in events:
            key=(event['leaf'],) if axis is None else (event['leaf'],event['labels'][axis])
            column=(0 if event['symbol']==pair[0] else 1)+(0 if event['focal'] else 2)
            word=event['word'];j=event['position'];frame=word[:j]+word[j+1:]
            for table,item in [(self.blocks,None),(self.words,word),(self.frames,frame)]:
                target=table if item is None else table.setdefault(item,{})
                target.setdefault(key,[0,0,0,0])[column]+=1

    def evaluate(self,remove_words=(),remove_frames=(),original_reference=None):
        if remove_words and remove_frames:raise ValueError('Choose one deletion family per replay')
        blocks={key:list(values) for key,values in self.blocks.items()}
        source=self.words if remove_words else self.frames
        for item in set(remove_words or remove_frames):
            for key,values in source[item].items():
                blocks[key]=[a-b for a,b in zip(blocks[key],values)]
        return summarize_blocks(blocks,self.pair,original_reference)


def scalar_view(result):
    return {k:(float(v) if isinstance(v,Fraction) else v) for k,v in result.items()
            if k not in ('by_leaf','eligible_events','groups','accepted_blocks','leaf_contributions')}


def selftest():
    records=[]
    def add(word,n,leaf,role,hand):
        records.extend(dict(word=word,leaf=leaf,folio=leaf+'r',role=role,hand=hand) for _ in range(n))
    add('lkay',2,'A','first','H1');add('ltay',1,'A','body','H1')
    add('akay',1,'A','first','H1');add('atay',3,'A','body','H1')
    add('lkay',1,'B','body','H2');add('ltay',1,'B','body','H2')
    add('bkay',3,'B','body','H2');add('btay',1,'B','body','H2')
    events=observations(records,('k','t'),WINDOWS[0],('hand','role'))
    base=exact_match(events,('k','t'))
    assert base['eligible']==5 and base['leaves']==2 and base['difference']==Fraction(3,20)
    assert [r['residual'] for r in base['by_leaf']]==[Fraction(5,4),Fraction(-1,2)]
    _,decomposition=decompose_original(events,('k','t'),'hand')
    assert decomposition['H1']['difference']==Fraction(5,12)
    assert decomposition['H1']['contribution']==Fraction(1,4)
    assert decomposition['H2']['contribution']==Fraction(-1,10)
    within_hand=rematch_by_layer(events,('k','t'),'hand')
    assert within_hand['difference']==base['difference'] and within_hand['eligible']==5
    within_role=rematch_by_layer(events,('k','t'),'role')
    assert within_role['eligible']==2 and within_role['difference']==Fraction(-1,4)
    assert within_role['groups']['first']['eligible']==0 and within_role['groups']['first']['difference'] is None
    deleted_focal=exact_match(delete_types(events,{tuple('lkay')}),('k','t'))
    assert deleted_focal['eligible']==2 and deleted_focal['difference']==Fraction(-1,2)
    deleted_reference=exact_match(delete_types(events,{tuple('atay')}),('k','t'))
    assert deleted_reference['eligible']==2 and deleted_reference['difference']==Fraction(-1,4)
    unique,ambiguity=deduplicate(events)
    unique_result=exact_match(unique,('k','t'))
    assert unique_result['eligible']==0 and unique_result['difference'] is None
    contributions=wordtype_contributions(events,('k','t'))
    assert sum((row['residual'] for row in contributions.values()),Fraction(0))==base['residual']
    sufficient=Sufficient(events,('k','t'))
    for direct,rebuilt in [(base,sufficient.evaluate()),
                           (deleted_focal,sufficient.evaluate(remove_words=(tuple('lkay'),))),
                           (deleted_reference,sufficient.evaluate(remove_words=(tuple('atay'),)))]:
        assert scalar_view(direct)==scalar_view(rebuilt)
    layer_sufficient=Sufficient(events,('k','t'),'role')
    assert layer_sufficient.evaluate()['eligible']==2
    assert layer_sufficient.evaluate()['difference']==Fraction(-1,4)
    reference={row['leaf']:row['reference'] for row in base['by_leaf']}
    same_cohort=layer_sufficient.evaluate(original_reference=reference)
    assert same_cohort['eligible']==2 and same_cohort['difference']==Fraction(-1,4)
    assert sufficient.evaluate(remove_frames=(tuple('lay'),))['eligible']==0
    # Same leaf/type/site across roles has no single deduplicated role label.
    mixed=observations([dict(word='lkay',leaf='A',role='first'),dict(word='lkay',leaf='A',role='body')],
                       ('k','t'),WINDOWS[0],('role',))
    dedup_mixed,mixed_flags=deduplicate(mixed)
    assert len(dedup_mixed)==1 and mixed_flags=={'role':1}
    # The same code handles every pair and both fixed windows. An extra target
    # elsewhere in the word is an original context unit, not another focal site.
    for pair in PAIRS:
        for window in WINDOWS:
            length,j,left,right=window
            suffix='y' if length==4 else 'ay'
            first=left+pair[0]+right+suffix;second=left+pair[1]+right+suffix
            rows=[dict(word=first,leaf='A'),dict(word=second,leaf='A')]
            rows += [dict(word='b'+pair[0]+right+suffix,leaf='A')]*3
            selected=observations(rows,pair,window)
            answer=exact_match(selected,pair)
            assert answer['eligible']==2 and answer['difference']==Fraction(-1,2)
    extra=observations([dict(word='lkat',leaf='A')],('k','t'),WINDOWS[0])
    assert len(extra)==1 and extra[0]['symbol']=='k' and extra[0]['word'][-1]=='t'
    return dict(passed=True,base=scalar_view(base),within_role=scalar_view(within_role),
                deleted_focal=scalar_view(deleted_focal),deleted_reference=scalar_view(deleted_reference),
                deduplicated=scalar_view(unique_result),mixed_label_units=mixed_flags,
                pair_window_cases=12,
                scope='Artificial inputs only. No manuscript data, production output or statistical claim evaluated.')



AXES=('hand','section','role','hand_section')
ROLES=('paragraph_first','paragraph_first_line_other','line_first','other')
NAMES={'l_a':WINDOWS[0],'c_h':WINDOWS[1]}
ZERO=Fraction(1,10**12)


def roll_reference(events,pair,references):
    """Reweight a cohort using explicit independent reference probabilities."""
    raw=collections.Counter();eligible=collections.Counter();by_leaf={}
    for event in events:
        if not event['focal']:continue
        raw[event['symbol']]+=1
        if event['record_index'] not in references:continue
        eligible[event['symbol']]+=1
        p=references[event['record_index']]
        leaf=event['leaf'];residual=Fraction(event['symbol']==pair[0])-p
        if leaf not in by_leaf:by_leaf[leaf]=[0,Fraction(0)]
        by_leaf[leaf][0]+=1;by_leaf[leaf][1]+=residual
    n=sum(eligible.values());r=sum((v[1] for v in by_leaf.values()),Fraction(0))
    omitted=[(r-c)/(n-k) for k,c in by_leaf.values() if n>k]
    return dict(counts_all={g:raw[g] for g in pair},counts={g:eligible[g] for g in pair},
                eligible=n,leaves=len(by_leaf),observed_first=Fraction(eligible[pair[0]],n) if n else None,
                expected_first=(Fraction(eligible[pair[0]])-r)/n if n else None,
                difference=r/n if n else None,residual=r,
                loo_min=min(omitted) if omitted else None,loo_max=max(omitted) if omitted else None,
                leaf_contributions=by_leaf)


def exported_stat(stat):
    if 'leaf_contributions' in stat:leaves=stat['leaf_contributions']
    else:leaves={r['leaf']:(r['n'],r['residual']) for r in stat['by_leaf']}
    sign=1 if stat['residual']>ZERO else -1 if stat['residual']<-ZERO else 0
    return dict(raw=stat['counts_all'],eligible=stat['counts'],n=stat['eligible'],leaves=stat['leaves'],
                observed=stat['observed_first'],expected=stat['expected_first'],difference=stat['difference'],
                residual=stat['residual'],consistent_leaves=sum(sign*r>ZERO for n,r in leaves.values()),
                loo_min=stat['loo_min'],loo_max=stat['loo_max'])


class Reader:
    def __init__(self):self.hashes={}
    def track(self,path):
        path=Path(path).resolve();digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if str(path) in self.hashes and self.hashes[str(path)]!=digest:raise RuntimeError('Input changed: '+str(path))
        self.hashes[str(path)]=digest;return digest
    def load(self,path):
        self.track(path)
        if path.suffix=='.gz':
            with gzip.open(path,'rt',encoding='utf-8') as f:return json.load(f)
        return json.loads(path.read_text(encoding='utf-8'))


class Checks:
    def __init__(self):self.errors=[];self.counts=collections.Counter();self.maximum=0.
    def equal(self,a,b,label):
        self.counts['exact_checks']+=1
        if a!=b:self.errors.append(dict(check=label,actual=a,expected=b))
    def close(self,a,b,label):
        self.counts['numerical_checks']+=1
        if b is None:
            if a is not None:self.errors.append(dict(check=label,actual=a,expected=None))
            return
        if a is None or not isinstance(a,(float,int)) or not abs(a-float(b))<=1e-11:
            self.errors.append(dict(check=label,actual=a,expected=float(b)));return
        self.maximum=max(self.maximum,abs(a-float(b)))
    def stat(self,a,b,label):
        expected=exported_stat(b)
        self.equal(set(a),set(expected),label+' stat fields')
        for key in ('raw','eligible','n','leaves','consistent_leaves'):self.equal(a[key],expected[key],label+' '+key)
        for key in ('observed','expected','difference','residual','loo_min','loo_max'):self.close(a[key],expected[key],label+' '+key)
        self.counts['statistics']+=1


def tag(row):return row['version'],row['pair'],row['window'],row['scope']


def original_records(root,version,reader):
    folder=root.parent/'parameter_sharing/inputs';td=reader.load(folder/(version+'_train_dev.json.gz'))
    result=[]
    for split,rows in [('train',td['train']),('dev',td['dev'])]+[(s,reader.load(folder/(version+'_'+s+'.json.gz'))) for s in ('confirm','reserve')]:
        result.extend(dict(row,split=split) for row in rows)
    return result


def verify_labels(root,labeled,reader,check):
    summaries={}
    for version in ('ZL','IT'):
        old=original_records(root,version,reader);rows=labeled[version]
        check.equal(len(rows),len(old),version+' labeled record count')
        seen=set()
        for i,(row,source) in enumerate(zip(rows,old)):
            identity=(row['folio'],row['line'],row['slot'])
            check.equal(identity in seen,False,version+' unique source '+str(identity));seen.add(identity)
            for field in ('folio','leaf','line','slot','split','position'):
                check.equal(row[field],source[field],version+' source '+str(i)+' '+field)
            check.equal(original_units(row['word']),original_units(source['word']),version+' source original units '+str(i))
            old_role='other' if row['role']=='paragraph_first_line_other' else row['role']
            check.equal(old_role,source['position'],version+' original role relation '+str(i))
            check.equal(row['role'] in ROLES,True,version+' declared role '+str(i))
            check.equal(isinstance(row['paragraph_known'],bool),True,version+' known-paragraph boolean')
            check.equal(all(isinstance(row[field],str) and row[field] for field in ('hand','section')),True,version+' explicit strata labels')
        summaries[version]=dict(records=len(rows),leaves=len({r['leaf'] for r in rows}),pages=len({r['folio'] for r in rows}))
    return summaries


def rank_contributions(events,pair):
    values=wordtype_contributions(events,pair)
    return sorted([dict(word=word,count=v['events'],residual=v['residual']) for word,v in values.items()],
                  key=lambda v:(-abs(v['residual']),v['word']))


def compare_contributions(actual,expected,check,label):
    check.equal(len(actual),len(expected),label+' type count')
    for i,(a,b) in enumerate(zip(actual,expected)):
        check.equal(tuple(a['word']),b['word'],label+' rank '+str(i))
        check.equal(a['count'],b['count'],label+' count '+str(i))
        check.close(a['residual'],b['residual'],label+' contribution '+str(i))


def audit(root,run,label_path,reader,check):
    frozen=reader.load(root/'freeze.json')
    for relative,digest in frozen['files'].items():check.equal(reader.track(root/relative),digest,'freeze '+relative)
    check.equal(reader.track(label_path),frozen['labeled_sha256'],'frozen labeled data')
    reader.track(root/'analyze_strata.py');reader.track(Path(__file__).resolve())
    data=reader.load(label_path);corpus=verify_labels(root,data,reader,check)
    main=reader.load(run/'results.json');details=reader.load(run/'lexical_trials.json.gz')
    check.equal(main['schema_version'],1,'schema');check.equal(main['status'],'complete','producer status')
    main_index={tag(row):row for row in main['results']};detail_index={tag(row):row for row in details}
    check.equal(len(main_index),len(main['results']),'unique main tags');check.equal(len(detail_index),len(details),'unique detailed tags')
    expected_tags=[(v,'/'.join(p),w,s) for v in ('ZL','IT') for p in PAIRS for w in NAMES for s in ('all','confirm_reserve')]
    check.equal(set(main_index),set(expected_tags),'48 main combinations');check.equal(set(detail_index),set(expected_tags),'48 detailed combinations')
    prior_rows=reader.load(root.parent/'gallows_pairs/saved/local.json.gz')
    prior={(r['version'],r['pair'],r['scope'],r['length'],r['position'],r['left'],r['right']):r for r in prior_rows}
    completed=[];ambiguity=[]
    for identity in expected_tags:
        version,pair_name,window_name,scope=identity;pair=tuple(pair_name.split('/'));window=NAMES[window_name]
        label=' '.join(identity)
        try:
            output=main_index[identity];detail=detail_index[identity]
            for field,value in [('length',window[0]),('position',window[1]+1)]:
                check.equal(output[field],value,label+' '+field);check.equal(detail[field],value,label+' detail '+field)
            rows=[dict(row,hand_section=row['hand']+' × '+row['section']) for row in data[version]
                  if scope=='all' or row['split'] in ('confirm','reserve')]
            events=observations(rows,pair,window,AXES)
            base=exact_match(events,pair);sufficient=Sufficient(events,pair)
            check.stat(output['original'],base,label+' original event computation')
            check.stat(output['original'],sufficient.evaluate(),label+' original four-count computation')
            check.equal(output['strata_coverage'],dict(words=len(events),known_paragraph=sum(rows[e['record_index']]['paragraph_known'] for e in events)),label+' selected-site coverage')
            unique,mixed=deduplicate(events)
            check.stat(output['dedup'],Sufficient(unique,pair).evaluate(),label+' leaf-word-site dedup')
            ambiguity.append(dict(version=version,pair=pair_name,window=window_name,scope=scope,units_with_multiple_labels=mixed))
            known=[e for e in events if rows[e['record_index']]['paragraph_known']]
            check.stat(output['paragraph_known'],Sufficient(known,pair).evaluate(),label+' paragraph known only')
            previous=prior.get((version,pair_name,scope,window[0],2,window[2],window[3]))
            if previous is None:check.equal(sum(base['counts_all'].values()),0,label+' absent prior cell has zero focal')
            else:
                check.equal(previous['counts'],base['counts'],label+' previous eligible')
                check.equal(previous['counts_all'],base['counts_all'],label+' previous raw')
                check.close(previous['difference'],base['difference'],label+' previous difference')
            base_refs={e['record_index']:e['reference'] for e in base['eligible_events']}
            check.equal(set(output['axes']),set(AXES),label+' axes')
            check.equal(set(output['drop_groups']),set(AXES),label+' drop axes')
            for axis in AXES:
                axis_output=output['axes'][axis]
                layer=Sufficient(events,pair,axis).evaluate()
                refs_by_block={r['key']:r['reference'] for r in layer['accepted_blocks']}
                matched_refs={e['record_index']:refs_by_block[e['leaf'],e['labels'][axis]] for e in events
                              if e['focal'] and (e['leaf'],e['labels'][axis]) in refs_by_block}
                check.equal(set(matched_refs)<=set(base_refs),True,label+' '+axis+' matched subset')
                same_refs={i:base_refs[i] for i in matched_refs}
                pooled_match=roll_reference(events,pair,matched_refs);pooled_same=roll_reference(events,pair,same_refs)
                check.stat(axis_output['pooled_matched'],pooled_match,label+' '+axis+' pooled matched')
                check.stat(axis_output['pooled_matched'],layer,label+' '+axis+' pooled four-count/leaf LOO')
                check.stat(axis_output['pooled_same_sample'],pooled_same,label+' '+axis+' pooled original reference on same cohort')
                groups=sorted({e['labels'][axis] for e in events})
                if axis=='role':groups=list(ROLES)+[g for g in groups if g not in ROLES]
                check.equal([r['group'] for r in axis_output['rows']],groups,label+' '+axis+' all groups')
                n_partition=0;r_partition=Fraction(0)
                for saved,group in zip(axis_output['rows'],groups):
                    selected=[e for e in events if e['labels'][axis]==group]
                    for field,refs in [('original',base_refs),('matched',matched_refs),('same_sample',same_refs)]:
                        computed=roll_reference(selected,pair,refs)
                        check.stat(saved[field],computed,label+' '+axis+' '+group+' '+field)
                        if field=='original':n_partition+=computed['eligible'];r_partition+=computed['residual']
                    check.counts['stratum_rows']+=1
                check.equal(n_partition,base['eligible'],label+' '+axis+' original eligible partition')
                check.equal(r_partition,base['residual'],label+' '+axis+' original residual partition')
                drops=output['drop_groups'][axis]
                drop_labels=sorted({e['labels'][axis] for e in events})
                check.equal([r['group'] for r in drops],drop_labels,label+' '+axis+' all delete-group trials')
                for saved,group in zip(drops,drop_labels):
                    after=Sufficient([e for e in events if e['labels'][axis]!=group],pair).evaluate()
                    check.stat(saved['after'],after,label+' delete '+axis+' '+group)
                    check.counts['delete_group_trials']+=1
            top=rank_contributions(events,pair)
            compare_contributions(detail['full_type_contributions'],top,check,label+' full type contributions')
            compare_contributions(output['lexical']['top'],top[:12],check,label+' displayed type contributions')
            check.equal(len(output['lexical']['peel']),3,label+' three cumulative fixed-rank deletions')
            for requested,saved in zip((1,3,5),output['lexical']['peel']):
                words=[row['word'] for row in top[:requested]]
                check.equal(saved['n'],len(words),label+' peel number '+str(requested))
                check.equal([tuple(w) for w in saved['words']],words,label+' peel original ranking '+str(requested))
                after=sufficient.evaluate(remove_words=words)
                check.stat(saved['after'],after,label+' peel '+str(requested)+' rematch')
                check.counts['peel_trials']+=1
            for family,field,source in [('leave_one_word','word',sufficient.words),('leave_one_frame','frame',sufficient.frames)]:
                trials=detail[family];keys=sorted(source)
                check.equal([tuple(t[field]) for t in trials],keys,label+' all '+family+' keys')
                independent=[]
                for saved,key in zip(trials,keys):
                    after=sufficient.evaluate(remove_words=(key,)) if field=='word' else sufficient.evaluate(remove_frames=(key,))
                    check.stat(saved['after'],after,label+' '+family+' '+repr(key))
                    independent.append((key,after));check.counts[family+'_trials']+=1
                valid=[(key,stat) for key,stat in independent if stat['difference'] is not None]
                overview=output['lexical'][family]
                check.equal(overview['tested'],len(keys),label+' '+family+' tested')
                check.equal(overview['missing'],len(keys)-len(valid),label+' '+family+' unsupported')
                for name,select in [('lowest',min),('highest',max)]:
                    selected=select(valid,key=lambda item:item[1]['difference']) if valid else None
                    if selected is None:check.equal(overview[name],None,label+' '+family+' '+name)
                    else:
                        check.equal(tuple(overview[name][field]),selected[0],label+' '+family+' '+name+' identity')
                        check.stat(overview[name]['after'],selected[1],label+' '+family+' '+name+' statistic')
            completed.append(identity);print(label+' audited',flush=True)
        except Exception as exc:
            check.errors.append(dict(check=label,error=str(exc),traceback=traceback.format_exc()))
    check.equal(len(completed),48,'all comparisons completed')
    return dict(comparisons=len(completed),corpus=corpus,deduplicated_label_ambiguity=ambiguity)


def save(path,data):
    def convert(v):
        if isinstance(v,Fraction):return float(v)
        if isinstance(v,(set,tuple)):return sorted(v)
        raise TypeError(type(v).__name__)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False,default=convert)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selftest',action='store_true')
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--run',type=Path)
    parser.add_argument('--labels',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.selftest:print(json.dumps(selftest(),ensure_ascii=False,indent=2));return 0
    if args.run is None or args.labels is None or args.output is None:parser.error('--run, --labels and --output are required')
    args.output.mkdir(parents=True,exist_ok=False);toy=selftest();reader=Reader();check=Checks();body={}
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:body=audit(args.root.resolve(),args.run.resolve(),args.labels.resolve(),reader,check)
    except Exception as exc:check.errors.append(dict(check='top-level',error=str(exc),traceback=traceback.format_exc()))
    for path,digest in list(reader.hashes.items()):check.equal(hashlib.sha256(Path(path).read_bytes()).hexdigest(),digest,'stable source '+path)
    report=dict(passed=not check.errors,started_utc=started,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                python=sys.version,command=sys.argv,counts=dict(check.counts),max_absolute_error=check.maximum,
                absolute_tolerance=1e-11,directional_numerical_zero=1e-12,**body)
    report['scope']=[
        'Independent Python standard-library/Fraction replay; no production preparation/analysis functions imported.',
        'All six pairs, both fixed windows, both all/old-50-page scopes; base, deduplication and paragraph-known subset.',
        'Four strata axes: original cohort decomposition, leaf/layer rematching, and same rematched cohort with original reference.',
        'LOO first combines all included blocks from the same leaf. Raw counts remain full focal support, distinct from eligible n.',
        'Every deletion of a full layer, original word type or complete target-deleted word frame rematches support; top 1/3/5 use original ranking.',
        'Enriched words/coordinates/leaf/splits/old roles verified against saved original inputs. New paleographic/section/paragraph annotations not independently reclassified.',
        'No visual glyph judgments, image crops, browser tests, new hypotheses or model fitting are audited here.',
        'Non-independent repeated words/leaves/editions, selected windows and changed comparable cohorts prevent causal or semantic identification.']
    save(args.output/'audit_report.json',report);save(args.output/'errors.json',check.errors);save(args.output/'manual_examples.json',toy)
    research=args.root.resolve().parent.parent;bindings=[]
    for name,digest in sorted(reader.hashes.items()):
        path=Path(name)
        if args.run.resolve() in path.parents:label='run/'+str(path.relative_to(args.run.resolve()))
        elif path==args.labels.resolve():label='labels.json.gz'
        elif research in path.parents:label='research/'+str(path.relative_to(research))
        else:label=name
        bindings.append(dict(path=label,sha256=digest,bytes=path.stat().st_size))
    save(args.output/'inputs.json',bindings)
    text='固定窗口分层与删词型独立审核：'+('通过' if report['passed'] else '未通过')+'。\n'
    text+='独立标准库与有理数复算；原参照分解、同层重新匹配、保留相同站位沿用原参照三列分别核对。\n'
    text+='每次删层、词型或完整框均重建参照和支持；不足支持保留空值。去重仅总量，不赋唯一层标签。\n'
    text+='新增标签的古文字学判断、图像和浏览器不属于此次审核；统计一致不意味着语义等价或因果归因。\n'
    text+='比较数：'+str(body.get('comparisons',0))+'；最大绝对误差：'+str(check.maximum)+'；错误数：'+str(len(check.errors))+'。\n'
    text+=json.dumps(dict(check.counts),ensure_ascii=False)+'\n'
    (args.output/'audit_report.txt').write_text(text,encoding='utf-8')
    files=[dict(path=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size) for p in sorted(args.output.iterdir()) if p.is_file()]
    source=Path(__file__).resolve();files.append(dict(path='audit.py',sha256=hashlib.sha256(source.read_bytes()).hexdigest(),bytes=source.stat().st_size))
    save(args.output/'artifact_manifest.json',dict(files=files))
    print(json.dumps(dict(passed=report['passed'],errors=len(check.errors),counts=report['counts'],max_error=check.maximum,comparisons=body.get('comparisons',0)),indent=2))
    return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
