"""Read-only post-run verification. No policy, sample, or matching rule modification."""
from pathlib import Path
from collections import defaultdict
from fractions import Fraction
import gzip, hashlib, json, re

HERE=Path(__file__).resolve().parent
OUT=HERE/'run_v2'
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def value(x):return Fraction(x['num'],x['den']) if x is not None else None
def uu(w):return re.findall(r"@\d{3};|[a-z']",w)
def expand(w,model):
    mm={'davis':{'f':'te','p':'ke'},'davis_swapped':{'f':'ke','p':'te'},'davis_sham':{'f':'ta','p':'ka'}}[model]
    # Separate independent implementation: regex chunks consume protected benches first.
    return ''.join(mm.get(chunk,chunk) for chunk in re.findall(r"c[tfkp]h|@\d{3};|[a-z']",w))
def matches(query,word,model):
    if model.startswith('davis'):return expand(query,model)==expand(word,model)
    if query==word:return True
    if model=='exact':return False
    a,b=uu(query),uu(word)
    if len(a)!=len(b):return False
    changed=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
    if len(changed)!=1:return False
    i=changed[0]
    if set((a[i],b[i]))!=set(model):return False
    return not (i>0 and i+1<len(a) and a[i-1]=='c' and a[i+1]=='h')
def main():
    receipt=read(OUT/'complete.json');assert receipt['status']=='complete'
    for name,digest in receipt['files'].items():assert sha(OUT/name)==digest,name
    target_checks=donor_page_checks=0;conditions=[]
    for f in sorted(OUT.glob('*__*__*.json.gz')):
        if f.name.startswith(('inventory','collisions')):continue
        result=read(f);inventory=read(OUT/('inventory__'+result['version']+'__'+result['boundary']+'.json.gz'))['pages']
        assert len(result['candidates'])==11
        for c in result['candidates']:
            q=c['loci'][0]['words'][0]
            for model,m in c['models'].items():
                rr=inventory[c['target_folio']]
                hit=[i for i,w in enumerate(rr) if matches(q,w['word'],model)]
                transformed=expand(q,model) if model.startswith('davis') else q
                length=len(uu(transformed))
                opportunities=[i for i,w in enumerate(rr) if len(uu(expand(w['word'],model) if model.startswith('davis') else w['word']))==length]
                assert hit==m['target']['match_indices']
                assert opportunities==m['target']['opportunity_indices']
                assert m['target']['binary']==int(bool(hit))
                assert value(m['target']['rate'])==(Fraction(len(hit),len(opportunities)) if opportunities else None)
                target_checks+=1
                donors=defaultdict(list)
                for dp in m['donor_pages']:
                    inv=inventory[dp['folio']]
                    hh=[i for i,w in enumerate(inv) if matches(q,w['word'],model)]
                    assert hh==dp['score']['match_indices']
                    donors[dp['leaf']].append(int(bool(hh)))
                    donor_page_checks+=1
                donor_mean=sum((sum(map(Fraction,v))/len(v) for v in donors.values()),Fraction())/len(donors)
                delta=Fraction(bool(hit))-donor_mean
                assert delta==value(m['endpoints']['min1']['binary_delta'])
        for model,a in result['aggregate'].items():
            leaf=defaultdict(list)
            for c in result['candidates']:leaf[c['source_leaf']].append(value(c['models'][model]['endpoints']['min1']['binary_delta']))
            assert len(leaf)==4
            overall=sum((sum(v,Fraction())/len(v) for v in leaf.values()),Fraction())/4
            assert overall==value(a['primary_source_leaf']['binary']['value'])
        conditions.append(f.name)
    assert len(conditions)==8 and target_checks==880
    result=dict(status='passed',checks='Independent regex whole-word matcher verified target and donor match positions; target length opportunities/rates and donor/page/source-leaf binary aggregation verified.',
        receipt_sha256=sha(OUT/'complete.json'),script_sha256=sha(Path(__file__)),verified_run_files=len(receipt['files']),
        target_condition_model_checks=target_checks,donor_page_checks=donor_page_checks,
        independence_warning='These are consistency checks of the frozen analysis, not independent manuscript observations or validation of image identity.',conditions=conditions)
    (HERE/'audit_run_v2.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
