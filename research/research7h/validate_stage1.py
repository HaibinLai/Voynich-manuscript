"""Independent analytic checks and reproducibility checks for stage 1."""
from itertools import permutations
from collections import Counter
import json, numpy as np
from corpus import ROOT,load,save,sha
from structure import page_run,neighbor_matrix,KEYS
from predictive import CharLM,EOS,UNK,records

out={}
for representation in ['eva','merged']:
    total=0
    for page in load(splits=['confirm']):
        words=sorted({t for l in page['lines'] for t in l['tokens'] if t})
        uu,near=neighbor_matrix(words,representation);wi={w:i for i,w in enumerate(words)}
        for l in page['lines']:
            inside=l['tokens'][1:-1];valid=[wi[t] for t in inside if t]
            if len(valid)<2:continue
            c=Counter(valid);n=len(valid)
            exact=sum(v*(v-1) for v in c.values())/(n*(n-1))
            one=sum(c[a]*c[b] for a in c for b in c if a!=b and near[a,b])/(n*(n-1))
            assert 0<=exact<=1 and 0<=one<=1 and exact+one<=1+1e-12
            total+=1
    out[representation+'_analytic_bounds_checked_lines']=total

# Enumerate the complete permutation distribution for an artificial 5-slot
# physical line, with three interior tokens. This is independent of shuffle.
mock=dict(folio='mock',leaf='mock',split='unit',metadata={},lines=[dict(
    tokens=['k','a','a','b','y'],paragraph_start=True,paragraph_known=True,loci=['mock.1'])])
v,n,ln,details=page_run(mock,'eva',19999,81)
enum=[]
for p in permutations(['a','a','b']):
    enum.append(sum(p[i]==p[i+1] for i in range(2))/2)
assert abs(v[2]-.5)<1e-12
assert abs(n[:,2].mean()-np.mean(enum))<.01
assert abs(n[:,0].mean())<.01
out['full_enumeration_artificial_line']=True

# Reconstruct every primary page's randomization arrays using the exact seed.
old=np.load(ROOT/'results/structure_confirm_nulls.npz')
pages=load(splits=['confirm'])
replay=[page_run(p,'eva',1999,2026111701+i*101) for i,p in enumerate(pages)]
for key,values in [('observed',[r[0] for r in replay]),('within_line',[r[1] for r in replay]),('length_matched',[r[2] for r in replay])]:
    assert np.allclose(old[key],np.array(values),rtol=0,atol=0,equal_nan=True)
out['primary_structure_all_random_arrays_exact_replay']=True

# Rebuild the chosen primary character model independently of the tuning loop.
train=records(load(splits=['legacy','train']),'eva');alphabet={c for r in train if r['word'] for c in r['word']}
train=records(load(splits=['legacy','train']),'eva',alphabet)
conf=json.loads((ROOT/'results/predictive_confirm_frozen_config.json').read_text())['selected']
lm=CharLM([r['word'] for r in train if r['word']],alphabet,conf['char_order'],conf['char_alpha'])
test=records(load(splits=['confirm']),'eva',alphabet)
score=-sum(lm.logp(r['word']) for r in test if r['word'])/sum(r['word'] is not None for r in test)
oldscore=json.loads((ROOT/'results/predictive_confirm.json').read_text())['results']['char_selected']['bits_per_token']
assert abs(score-oldscore)<1e-12
out['chosen_char_model_exact_replay']=True
receipt=json.loads((ROOT/'split_receipt.json').read_text())
assert sha(ROOT/'split_manifest.json')==receipt['manifest_sha256']
assert sha(ROOT/'stage1_protocol.txt')==receipt['protocol_sha256']
out['frozen_manifest_and_protocol_unchanged']=True
save('results/stage1_verification.json',out);print(json.dumps(out,indent=2))
