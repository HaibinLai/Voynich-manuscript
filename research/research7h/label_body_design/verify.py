"""Independent allowed-page count/length checks, never lexical matching."""
from pathlib import Path
from collections import Counter
import json,re,hashlib
P=Path(__file__).resolve().parent;BASE=P.parents[1]
load=lambda n:json.loads((P/n).read_text())
allowed={r['folio']:r for r in load('allowed_pages.json')}
records=load('locus_lengths.json');pages=load('page_counts.json');inv=load('inventory.json')
assert all(r['split'] in {'train','legacy','dev'} for r in allowed.values())
def independent_length(word,merged):
    i=n=0
    while i<len(word):
        if word[i]=='@':
            assert re.fullmatch(r'@\d{3};',word[i:i+5]);i+=5
        elif merged and any(word.startswith(s,i) for s in ['cth','ckh','cph','cfh','ch','sh']):
            i+=next(len(s) for s in ['cth','ckh','cph','cfh','ch','sh'] if word.startswith(s,i))
        else:
            assert word[i] in "abcdefghijklmnopqrstuvwxyz'";i+=1
        n+=1
    return n
def independent_slots(payload):
    text=payload.replace('<->','.').replace('<~>','.')
    text=re.sub('<[^>]*>','',text).replace('{','').replace('}','').lower().replace(',','.')
    result=[]
    for slot in text.split('.'):
        slot=''.join(slot.split())
        if not slot:continue
        if re.fullmatch(r"(?:[a-z']|@[0-9]{3};)+",slot):
            result.append(dict(eva=independent_length(slot,False),merged=independent_length(slot,True)))
        else:result.append(None)
    return result
checks=[]
for source,rr in records.items():
    saved={r['locator']:r for r in rr};current=None;checked=0
    with (BASE/'sources'/source).open() as stream:
        for line in stream:
            if not line.startswith('<'):continue
            end=line.find('>');tag=line[1:end]
            if '.' not in tag:current=tag;continue
            if current not in allowed:continue
            loc,kind=tag.split(',',1);assert loc.split('.')[0]==current
            actual=independent_slots(line[end+1:])
            assert actual==saved[loc]['slots'] and kind==saved[loc]['kind'],loc
            checked+=1
    assert checked==len(saved)
    checks.append(dict(source=source,allowed_loci_checked=checked,all_slot_lengths_and_missingness_match=True))
    # A second existing inventory provides independent frozen body denominators.
    coverage=json.loads((P.parent/'anchor_audit/coverage_results.json').read_text())
    version='ZL_EVA' if source.startswith('ZL') else 'IT_EVA'
    for pool in ['train_legacy','dev']:
        actual=sum(p['body']['retained'] for p in pages if p['source']==source and p['pool']==pool)
        expected=next(g['tokens'] for g in coverage['groups'] if g['representation']==version and g['split_group']==pool)
        assert actual==expected,(version,pool,actual,expected)
support=load('control_support_details.json')
for r in support:
    a=allowed[r['folio']];assert a['leaf']==r['leaf']
    for f in r['donor_pages']:
        b=allowed[f];assert a['leaf']!=b['leaf']
        assert a['metadata'].get('H') in {'1','2','3','4','5'}
        assert all(a['metadata'].get(k)==b['metadata'].get(k) for k in ['H','I'])
        assert (a['split']=='dev')==(b['split']=='dev')
        if r['conditioning']=='HIQ_length':assert a['metadata'].get('Q')==b['metadata'].get('Q')
    assert set(r['donor_leaves'])=={allowed[f]['leaf'] for f in r['donor_pages']}
for source,rr in records.items():assert all(r['folio'] in allowed for r in rr)
assert independent_slots("<%>a.[b:c].d?.@162;hy,cth.<$>")==[
    {'eva':1,'merged':1},None,None,{'eva':3,'merged':3},{'eva':3,'merged':1}]
result=dict(passed=True,method='Second streaming parser and scalar unit scanner; frozen body-denominator crosscheck',
    source_checks=checks,control_rows_checked=len(support),
    same_leaf_donors=0,disallowed_payload_parsed=False,lexical_hits_computed=False,new_images_read=False,
    denominator_checks=4,toy_extended_unit_alternative_spacing_check=True,
    inventory_sha256=hashlib.sha256((P/'inventory.json').read_bytes()).hexdigest(),
    verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(P/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
