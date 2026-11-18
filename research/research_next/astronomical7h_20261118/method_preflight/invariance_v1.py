"""Exhaustive finite checks supplement the all-N algebra in the report."""
from itertools import product
from pathlib import Path
import datetime as dt
import hashlib
import json

HERE=Path(__file__).resolve().parent

def totals(flat,n):
    return [sum(flat[i*n+(i+s)%n] for i in range(n)) for s in range(n)]

def common_reindex(flat,n,r,direction):
    return tuple(flat[((direction*i+r)%n)*n+(direction*j+r)%n]
                 for i in range(n) for j in range(n))

def body_only_reindex(flat,n,r):
    return tuple(flat[i*n+(j+r)%n] for i in range(n) for j in range(n))

def main():
    frozen=json.loads((HERE/'invariance_input_freeze_v1.json').read_text())
    for f in frozen['files']:
        assert hashlib.sha256((HERE/f['path']).read_bytes()).hexdigest()==f['sha256'],f['path']
    checks=[]
    for n in range(1,5):
        matrices=paired=single=0
        for flat in product((0,1),repeat=n*n):
            original=totals(flat,n)
            for r in range(n):
                for direction in [1,-1]:
                    new=totals(common_reindex(flat,n,r,direction),n)
                    expected=[original[(direction*s)%n] for s in range(n)]
                    assert new==expected
                    assert new[0]==original[0]
                    assert sorted(new)==sorted(original)
                    assert sum(x>=new[0] for x in new)==sum(x>=original[0] for x in original)
                    paired+=1
                one=totals(body_only_reindex(flat,n,r),n)
                assert one==[original[(s+r)%n] for s in range(n)]
                single+=1
            matrices+=1
        checks.append({'n':n,'all_binary_matrices':matrices,'common_relabelings':paired,'single_body_rotations':single,'passed':True})
    n=12;identity=tuple(int(i==j) for i in range(n) for j in range(n))
    examples=[]
    for r in range(n):
        examples.append({'body_only_rotation':r,'original_match_counts':totals(identity,n),
                         'common_rotation_counts':totals(common_reindex(identity,n,r,1),n),
                         'common_reflection_counts':totals(common_reindex(identity,n,r,-1),n),
                         'body_only_rotation_counts':totals(body_only_reindex(identity,n,r),n)})
    out={'utc':dt.datetime.now(dt.timezone.utc).isoformat(),'status':'PASS_ARTIFICIAL_COORDINATE_INVARIANCE',
         'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
         'exhaustive_small_n_checks':checks,'twelve_item_fixed_examples':examples,
         'general_proof_status':'Explicit all-N change-of-index proof in invariance_report_v1.txt, not implied by finite enumeration alone.',
         'real_manuscript_data_read':False,'real_manuscript_scores_computed':False,
         'measurement_gate_changed':False,
         'interpretation':'A common arbitrary origin or geometric direction is harmless; unanchored relative correspondence is not.'}
    (HERE/'invariance_results_v1.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print('matrices',sum(x['all_binary_matrices'] for x in checks),'paired relabelings',sum(x['common_relabelings'] for x in checks),'body-only shifts',sum(x['single_body_rotations'] for x in checks))

if __name__=='__main__':main()
