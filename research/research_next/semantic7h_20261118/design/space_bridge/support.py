"""Input and length support only. Never compares a query to a body word or concatenation."""
from pathlib import Path
from collections import Counter,defaultdict
import gzip,hashlib,json,re
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
REPO=HERE.parents[4]
INPUT=ROOT.parent/'label_body/saved_v1/input.json.gz'
LABELS=ROOT/'literature/label_support.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def units(w):
    u=tuple(re.findall(r"@\d{3};|[a-z']",w));assert ''.join(u)==w
    return u
def recover(row):
    """Restore old token slots and overlay all raw tags as barrier coordinates."""
    raw=row['raw'];chars=[];barriers=[];separators=[];cursor=0
    def add(text,start):
        for i,ch in enumerate(text):
            if ch in '{}' or ch.isspace():continue
            if ch in '.,':
                separators.append(dict(position=len(chars),kind='uncertain_comma' if ch==',' else 'dot',raw_position=start+i));chars.append('.')
            else:chars.extend(ch.lower())
    for m in re.finditer(r'<[^>]*>',raw):
        add(raw[cursor:m.start()],cursor);tag=m.group();position=len(chars)
        barriers.append(dict(position=position,raw_start=m.start(),raw_end=m.end(),tag=tag))
        if tag in ('<->','<~>'):
            separators.append(dict(position=position,kind='graphic_tag',raw_position=m.start()));chars.append('.')
        cursor=m.end()
    add(raw[cursor:],cursor);stream=''.join(chars);tokens=[]
    for m in re.finditer(r'[^.]+',stream):
        word=m.group();valid=bool(re.fullmatch(r"(?:[a-z']|@\d{3};)+",word))
        internal=[b for b in barriers if m.start()<b['position']<m.end()]
        tokens.append(dict(slot=len(tokens),word=word if valid else None,start=m.start(),end=m.end(),
            comparable=valid and not internal,reason='unknown_or_alternative' if not valid else 'tag_inside_old_token' if internal else None,
            length=len(units(word)) if valid else None,internal_tags=internal))
    equivalent=[t['word'] for t in tokens]==row['tokens']
    return dict(locator=row['locator'],source_line=row['source_line'],uncertain_space=row['uncertain_space'],tokens=tokens,barriers=barriers,separators=separators,
        packet_reproduced=equivalent,raw=raw)
def windows(recovered,gap):
    """Only slot/length metadata; never constructs a concatenated word."""
    if not recovered['packet_reproduced']:return [],{'packet_reconstruction_mismatch':1}
    tokens=recovered['tokens'];out=[];excluded=Counter()
    for i in range(len(tokens)-gap):
        j=i+gap;span=tokens[i:j+1]
        if not all(t['comparable'] for t in span):excluded['unknown_or_incomparable_slot']+=1;continue
        if any(tokens[i]['end']<=b['position']<=tokens[j]['start'] for b in recovered['barriers']):excluded['raw_tag_barrier']+=1;continue
        out.append(dict(slots=[i,j],span_slots=list(range(i,j+1)),left_length=tokens[i]['length'],right_length=tokens[j]['length'],total_length=tokens[i]['length']+tokens[j]['length']))
    return out,dict(excluded)
def bench_seams(query):
    u=units(query)
    return sorted({b for i in range(len(u)-2) if u[i]=='c' and u[i+1] in 'fkpt' and u[i+2]=='h' for b in [i+1,i+2]})
def page_counts(rows,strict,query_length,forbidden):
    counts=Counter();rejections=Counter()
    for row in rows:
        if strict and row['uncertain_space']:rejections['uncertain_space_lines']+=1;continue
        if not row['packet_reproduced']:rejections['unreproduced_loci']+=1;continue
        counts['old_exact_length_opportunities']+=sum(t['word'] is not None and t['length']==query_length for t in row['tokens'])
        counts['exact']+=sum(t['comparable'] and t['length']==query_length for t in row['tokens'])
        for model,gap in [('adjacent_forward',1),('gap2_forward',2)]:
            ww,rr=windows(row,gap)
            rejections.update({model+'__'+k:v for k,v in rr.items()})
            for w in ww:
                if w['total_length']!=query_length:continue
                if w['left_length'] in forbidden or w['right_length'] in forbidden:
                    rejections[model+'__query_bench_common_support']+=1;continue
                counts[model]+=1
    counts['adjacent_reverse']=counts['adjacent_forward']
    return dict(opportunities={m:counts[m] for m in ['exact','adjacent_forward','adjacent_reverse','gap2_forward']},
        old_exact_length_opportunities=counts['old_exact_length_opportunities'],new_exact_interior_tag_exclusions=counts['old_exact_length_opportunities']-counts['exact'],rejections=dict(rejections))
def main():
    assert not (HERE/'support_v1.json').exists()
    data=json.loads(gzip.decompress(INPUT.read_bytes()));labels=json.loads(LABELS.read_text())
    candidates=[r for r in labels['records'] if r['status']=='source_numbered_locator' and r['fragment_id']!=110]
    result=dict(status='support_only_no_query_body_comparison',proposed_seam_rule='Both possible joins must avoid query bench interior; identical adjacent forward/reverse support.',
        inputs={str(p.relative_to(REPO)):sha(p) for p in [INPUT,LABELS,Path(__file__)]},parser_audit={},conditions={})
    for version,d in data.items():
        pages={p['folio']:p for p in d['pages']};recoveries={f:[recover(r) for r in p['body']] for f,p in pages.items()}
        audit=Counter();internal=[];mismatches=[];tags=Counter();examples={}
        for f,rr in recoveries.items():
            for r in rr:
                audit['loci']+=1;audit['tokens']+=len(r['tokens']);audit['uncertain_space_loci']+=r['uncertain_space']
                if not r['packet_reproduced']:mismatches.append(r)
                for b in r['barriers']:
                    tags[b['tag']]+=1
                    if b['tag'] in ['<!gap>','<!tear>','<!through plant>','<->','<~>','<!next line intrudes>'] and b['tag'] not in examples:examples[b['tag']]=r
                for t in r['tokens']:
                    if t['reason']=='tag_inside_old_token':internal.append(dict(folio=f,locator=r['locator'],raw=r['raw'],token=t))
                for gap in [1,2]:
                    ww,rej=windows(r,gap);audit[f'gap{gap}_eligible_windows_before_query_lengths']+=len(ww)
                    for k,v in rej.items():audit[f'gap{gap}__'+k]+=v
        result['parser_audit'][version]=dict(counts=dict(audit),reconstruction_mismatches=mismatches,interior_tag_tokens=internal,tag_counts=dict(tags),barrier_examples=examples)
        for boundary in ['strict_space','packet_tokens']:
            output=[]
            for c in candidates:
                lr=c['label_records'][version];assert len(lr)==1
                word=re.sub('<[^>]*>','',lr[0]['raw']);assert '.' not in word
                length=len(units(word));forbidden=bench_seams(word);target=pages[c['herbal_folio']];source=pages[c['pharma_folio']]
                donors=[p for p in pages.values() if (p['H'],p['I'])==(target['H'],target['I']) and p['leaf'] not in {source['leaf'],target['leaf']}]
                tc=page_counts(recoveries[target['folio']],boundary=='strict_space',length,forbidden)
                dc=[dict(folio=p['folio'],leaf=p['leaf'],counts=page_counts(recoveries[p['folio']],boundary=='strict_space',length,forbidden)) for p in donors]
                support={}
                for m in ['exact','adjacent_forward','adjacent_reverse','gap2_forward']:
                    ll=defaultdict(int)
                    for dp in dc:ll[dp['leaf']]+=dp['counts']['opportunities'][m]
                    support[m]=dict(target_n=tc['opportunities'][m],control_leaf_n=dict(ll),control_leaves_min1=sum(n>=1 for n in ll.values()),
                        conditional_supported=tc['opportunities'][m]>0 and sum(n>=1 for n in ll.values())>=2)
                output.append(dict(pair_id=c['pair_id'],fragment_id=c['fragment_id'],source_leaf=source['leaf'],target_leaf=target['leaf'],target_folio=target['folio'],
                    label=word,length=length,forbidden_query_seams=forbidden,target=tc,donors=dc,support=support))
            result['conditions'][version+'__'+boundary]=output
    (HERE/'support_v1.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    for v,a in result['parser_audit'].items():print(v,a['counts'],'mismatches',len(a['reconstruction_mismatches']),'interior_tag_tokens',len(a['interior_tag_tokens']))
    for condition,rr in result['conditions'].items():
        print(condition,[(r['fragment_id'],r['target']['opportunities']) for r in rr])
if __name__=='__main__':main()
