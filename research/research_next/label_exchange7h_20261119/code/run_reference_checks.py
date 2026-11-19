"""W8 staged toy, artificial uniform null sizes, and fixed-support deletion sensitivity."""
from pathlib import Path
from fractions import Fraction
from itertools import permutations
import argparse, datetime, json, platform
from exact_reference import MODELS, ScalarReference, fraction, permutation_scores
from matrix_support import W,ROOT,OLD,MODES,VERSIONS,read,dump,sha,verify_inputs,verify_code_freeze,packet,score_groups,remove_leaf

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def check_start():
    assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-11-19T21:09:19+00:00'),'No new long run after cutoff'

def toy():
    n=8;before=[[1]*n for _ in range(n)];after=[[8 if i==j else 0 for j in range(n)] for i in range(n)]
    a=ScalarReference([permutation_scores(before)],n*8).summary()
    b=ScalarReference([permutation_scores(after)],n*8).summary()
    assert fraction(a['observed'])==Fraction(1,8) and fraction(a['excess_over_mean'])==0 and a['tail_ge']==40320
    assert fraction(b['observed'])==1 and fraction(b['excess_over_mean'])==Fraction(7,8) and b['tail_ge']==1 and b['assignments']==40320
    # Literal token swaps witnessing the same fixed margins, no source manuscript involved.
    labels=[[chr(97+i)]*2 for i in range(n)];body=[[chr(97+j) for j in range(n)] for i in range(n)];events=[]
    from collections import Counter
    original=Counter(x for row in body for x in row)
    for i in range(n):
        want=chr(97+i)
        for j in range(i+1,n):
            # Previous row assignments already fixed. Swap one wrongly placed symbol in each pair.
            ai=body[i].index(chr(97+j));bj=body[j].index(want)
            events.append({'target_leaf':i,'target_slot':ai,'donor_leaf':j,'donor_slot':bj,'before':[body[i][ai],body[j][bj]]})
            body[i][ai],body[j][bj]=body[j][bj],body[i][ai]
    assert original==Counter(x for row in body for x in row)
    assert all(row==[chr(97+i)]*n for i,row in enumerate(body))
    # Exact cutoff/negative and constant strata boundary cases checked by independent explicit enumeration.
    fixtures=[([[0,1,1],[0,2]],6),([[-9,-4,-4],[3]],3),([[5],[7]],2)]
    from itertools import product
    for arrays,den in fixtures:
        ref=ScalarReference(arrays,den);flat=[sum(x) for x in product(*arrays)]
        for alpha in (2,20,120):
            result=ref.rejection_size(alpha)
            actual=sum(sum(y>=x for y in flat)*alpha<=len(flat) for x in flat)
            assert actual==result['rejected_assignments']
    return {'schema':'eighth_known_answer_toy_v1','completed_utc':utc(),'pass':True,'before':a,'after':b,'labels':labels,'final_body':body,'swaps':events,'null_boundary_fixtures':3,'scope':'Artificial token corpus only; no manuscript result or semantic gold standard.'}

def null_checks():
    outputs=[]
    for v in VERSIONS:
        for mode in MODES:
            old=read(OLD/'run_v2'/f'{v}_{mode}.json.gz');n=old['joint']['leaf_count'];D=int(old['joint']['integer_scale'])
            families={}
            for family in ('models','increments'):
                results={}
                for m in (MODELS if family=='models' else MODELS[1:]):
                    field='scores' if family=='models' else 'increments'
                    arrays=[[int(x) for x in g[field][m]] for g in old['groups']]
                    ref=ScalarReference(arrays,n*D);previous=old['joint'][family][m]
                    assert ref.observed==int(previous['observed_integer'])
                    assert ref.tail(ref.observed)==previous['tail_ge']
                    row={'alpha_1_20':ref.rejection_size(20)}
                    if family=='increments':row['alpha_1_120']=ref.rejection_size(120)
                    results[m]=row
                families[family]=results
            out={'version':v,'mode':mode,'artificial_uniform_pairing_only':True,'manuscript_exchangeability_verified':False,'families':families,'old_packet_sha256':sha(OLD/'run_v2'/f'{v}_{mode}.json.gz')}
            path=W/'runs/null'/f'{v}_{mode}.json';dump(path,out);outputs.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path)});print('NULL',v,mode,flush=True)
    dump(W/'runs/null/complete.json',{'completed_utc':utc(),'pass':True,'files':outputs,'scope':'Exact conditional sizes for artificial uniform whole-bag assignments; no rerun of old primary manuscript scoring.'})

def deletion_checks():
    assert read(W/'runs/toy.json')['pass'] and read(W/'runs/null/complete.json')['pass']
    outputs=[]
    for v in VERSIONS:
        for mode in MODES:
            p=packet(v,mode);leaves=[l for g in p['groups'] for l in g['leaves']]
            for leaf in leaves:
                target=W/'runs/deletion'/f'{v}_{mode}_{leaf}.json.gz'
                assert not target.exists(),'No silent resume: existing output needs a separately verified recovery record'
                groups=remove_leaf(p,leaf);summary,arrays=score_groups(groups,p['matrix_scale'])
                out={'version':v,'mode':mode,'deleted_leaf':leaf,'matrix_scale':p['matrix_scale'],'remaining_leaf_count':12,'groups':groups,'summary':summary,'old_packet_sha256':p['old_sha256'],'interpretation':'All original common lengths retained. Singleton stratum is a fixed non-informative constant, not missing/zero data.'}
                dump(target,out);outputs.append({'path':str(target.relative_to(ROOT)),'sha256':sha(target)})
            print('DELETION',v,mode,'13 cases',flush=True)
    assert len(outputs)==78
    dump(W/'runs/deletion/complete.json',{'completed_utc':utc(),'pass':True,'count':78,'files':outputs,'scope':'All fixed-support leave-one-physical-leaf scenarios; descriptive sensitivity, not independent replication.'})

def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['toy','null','deletion']);ap.add_argument('--code-freeze',type=Path,required=True);a=ap.parse_args()
    check_start();inp=verify_inputs();code=verify_code_freeze(a.code_freeze)
    dump(W/'runs'/f'{a.stage}_started.json',{'started_utc':utc(),'stage':a.stage,'input_freeze_sha256':inp,'code_freeze_sha256':code,'python':platform.python_version()})
    if a.stage=='toy':dump(W/'runs/toy.json',toy())
    elif a.stage=='null':
        assert read(W/'runs/toy.json')['pass'];null_checks()
    else:deletion_checks()
    print(json.dumps({'stage':a.stage,'status':'complete','completed_utc':utc()}),flush=True)
if __name__=='__main__':main()
