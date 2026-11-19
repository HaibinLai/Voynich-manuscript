"""Artificial-only end-to-end checks using explicit Fraction state enumeration."""
import argparse
from collections import defaultdict
from fractions import Fraction as F
from hashlib import sha256
from itertools import product, combinations
import json
from pathlib import Path
import random
import numpy as np
from core_v1 import IDS, ROW_FIELDS, CLASS_NAMES, build_tensor, table, subsets, logical_row, decode_witness, joint_flags
from summaries_v1 import summarize, inclusion_minimal, mask_of, local_certificates


def targets(assignment):
    s = {}
    for a,b in combinations(IDS,2):
        s[a,b] = 1-F(sum(abs(x-y) for x,y in zip(assignment[a],assignment[b])),8)
    h=(s['F03','F04']+s['F05','F06'])/2-(s['F01','F04']+s['F01','F06']+s['F03','F06']+s['F04','F05'])/4
    h4=(s['F03','F04']+s['F05','F06']-s['F03','F06']-s['F04','F05'])/2
    return (h,h4,h-h4)


def enumerate_states(raw):
    result = []
    for state in raw:
        domains = [sorted(set(map(tuple,state['entries'][e]))) for e in IDS]
        for values in product(*domains):
            assignment=dict(zip(IDS,values))
            result.append((state['id'],values,targets(assignment)))
    return result


def run_case(name, raw, factor=False):
    model=build_tensor(raw,factor)
    states=enumerate_states(raw)
    regimes=['unknown']+[s['id'] for s in model['states']]
    tables={(g,mask_of(s,model['core'])):table(model,s,g) for g in regimes for s in subsets(model['core'])}
    checked=witnesses=conflicts=0
    ref_summaries={}
    for g in regimes:
        permitted=[s for s in states if g=='unknown' or s[0]==g]
        ref_summaries[g]=[]
        for selected in subsets(IDS):
            groups=defaultdict(list)
            positions=[IDS.index(e) for e in selected]
            for state in permitted:
                groups[tuple(state[1][i] for i in positions)].append(state)
            class_counts=[0]*4
            for observation in product(*(model['alphabet'][e] for e in selected)):
                assignment=dict(zip(selected,observation))
                row=logical_row(model,tables[g,mask_of(selected,model['core'])],selected,assignment)
                compatible=groups.get(observation,[])
                unique={s[1]:s[2] for s in compatible}
                good={v for v,score in unique.items() if score[0]>0 and score[1]>0}
                cls=0 if not unique else 1 if not good else 3 if len(good)==len(unique) else 2
                bits=sum(1<<i for i,s in enumerate(model['states']) if any(c[0]==s['id'] for c in compatible))
                expected=[cls,len(unique),len(compatible),len(good),sum(s[1] in good for s in compatible),bits]
                for d in range(3):
                    expected.extend([int(min(v[d] for v in unique.values())*32),int(max(v[d] for v in unique.values())*32)] if unique else [None,None])
                assert row[:12]==expected,(name,g,selected,observation,row,expected)
                class_counts[cls]+=1;checked+=1
                if not unique:
                    conflicts+=1;assert all(x is None for x in row[6:]);continue
                for slot in range(12,20):
                    if row[slot] is None:
                        assert (slot==18 and not good) or (slot==19 and len(good)==len(unique))
                        continue
                    w=decode_witness(model,row[slot],g,assignment.get('F02'))
                    wt=tuple(tuple(w['assignment'][e]) for e in IDS)
                    assert any(s[0]==w['global_state'] and s[1]==wt for s in compatible)
                    values=targets(w['assignment'])
                    assert list(w['numerators_over_32'].values())==[int(v*32) for v in values]
                    if slot<18:assert int(values[(slot-12)//2]*32)==row[slot-6]
                    elif slot==18:assert values[0]>0 and values[1]>0
                    else:assert not(values[0]>0 and values[1]>0)
                    witnesses+=1
                if len(selected)==6:assert cls in (1,3)
                for removed in selected:
                    parent=tuple(e for e in selected if e!=removed)
                    parent_assignment={e:assignment[e] for e in parent}
                    pr=logical_row(model,tables[g,mask_of(parent,model['core'])],parent,parent_assignment)
                    assert pr[0]!=0 and row[1]<=pr[1] and row[2]<=pr[2]
                    for d in (6,8,10):assert row[d]>=pr[d] and row[d+1]<=pr[d+1]
                    assert row[5] & pr[5] == row[5]
                    if pr[0] in (1,3):assert row[0]==pr[0]
            ref_summaries[g].append(class_counts)
    summary=summarize(model,tables)
    for g in regimes:
        for row,counts in zip(summary['regimes'][g]['subsets'],ref_summaries[g]):
            assert list(row['class_counts'].values())==counts
            assert row['feasible_outcome_count']==sum(counts[1:])
        for flag in ('some_all_joint_positive','some_none_joint_positive','some_decisive','every_feasible_outcome_decisive'):
            masks=[r['mask'] for r in summary['regimes'][g]['subsets'] if r[flag]]
            wanted=[m for m in masks if all(t==m or (t&m)!=t for t in masks)]
            assert summary['regimes'][g]['minimal_sets'][flag]['inclusion_minimal_masks']==wanted
    # Test local certificates for every feasible complete assignment, then deletion minimality.
    certificates=0
    for g in regimes:
        for values in sorted({s[1] for s in states if g=='unknown' or s[0]==g}):
            a=dict(zip(IDS,values));target=3 if targets(a)[0]>0 and targets(a)[1]>0 else 1
            candidates=[]
            for selected in subsets(IDS):
                row=logical_row(model,tables[g,mask_of(selected,model['core'])],selected,{e:a[e] for e in selected})
                if row[0]==target:candidates.append(mask_of(selected))
            expected=[m for m in candidates if not any(t!=m and (t&m)==t for t in candidates)]
            assert local_certificates(model,tables,g,IDS,a)['inclusion_minimal_masks']==expected
            certificates+=1
    return {'id':name,'factor_f02':factor,'raw_tagged_states':len(states),'logical_fibres_checked':checked,
            'conflict_fibres_checked':conflicts,'complete_witnesses_checked':witnesses,
            'full_observation_local_certificates_checked':certificates,'all_pass':True}


def singleton(g,assignment):
    return {'id':g,'entries':{e:[list(assignment[e])] for e in IDS}}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output-dir',type=Path,required=True);args=ap.parse_args()
    if args.output_dir.exists():raise FileExistsError('New output directory required')
    rng=random.Random(72119);zero={e:(0,0,0,0) for e in IDS};two={e:(2,2,2,2) for e in IDS}
    fixtures=[('shared_g_no_pool',[singleton('a',zero),singleton('b',two)],False),
              ('overlap_g_not_frequency',[singleton('a',zero),singleton('b',zero)],True)]
    found={}
    for _ in range(10000):
        a={e:tuple(rng.randrange(3) for _ in range(4)) for e in IDS};h,h4,_=targets(a)
        if h>0 and h4<=0:found.setdefault('only_h',a)
        if h<=0 and h4>0:found.setdefault('only_h4',a)
        if h>0 and h4>0:found.setdefault('both',a)
        if len(found)==3:break
    assert len(found)==3
    fixtures.append(('formula_marginal_positive_no_joint',[singleton('a',found['only_h']),singleton('b',found['only_h4'])],False))
    fixtures.append(('formula_positive_and_nonpositive',[singleton('a',found['both']),singleton('b',zero)],False))
    for case in range(4):
        alphabet={e:sorted({tuple(rng.randrange(3) for _ in range(4)) for j in range(2)}) for e in IDS}
        raw=[]
        for g in ('a','b'):
            entries={e:[list(v) for v in (alphabet[e] if rng.randrange(2) else [rng.choice(alphabet[e])])] for e in IDS}
            if case%2==0:entries['F02']=[list(v) for v in alphabet['F02']]
            raw.append({'id':g,'entries':entries})
        fixtures.append((f'random_whole_signature_{case}',raw,case%2==0))
    # Redundant domain instances are algebraic provenance, not new numerical states.
    redundant=[singleton('a',zero),singleton('b',zero)]
    for state in redundant:
        for e in IDS:state['entries'][e]*=3
    fixtures.append(('duplicate_signature_instances',[*redundant],True))
    receipts=[run_case(*case) for case in fixtures]
    # Abstract V02: these target pairs are not claimed to come from four-dimensional drawings.
    flags=joint_flags(np.asarray([8,-8]),np.asarray([-8,8]),np.asarray([True,True]))
    assert not flags.any()
    # Abstract V07: same target category, different global-existence and local minima.
    abstract=[((a,b),a==0 or (a==1 and b==1)) for a in range(3) for b in range(2)]
    exists_all=[];local=[];observed=(1,1)
    for mask in range(4):
        groups=defaultdict(list)
        for v,p in abstract:groups[tuple(v[d] for d in range(2) if mask&(1<<d))].append(p)
        if any(all(v) for v in groups.values()):exists_all.append(mask)
        ys=tuple(observed[d] for d in range(2) if mask&(1<<d))
        if all(groups[ys]):local.append(mask)
    assert inclusion_minimal(exists_all)==[1] and inclusion_minimal(local)==[3]
    rejected=[]
    try:build_tensor(fixtures[0][1],True)
    except ValueError:rejected.append('F02_domains_differ_despite_zero_target_coefficient')
    else:raise AssertionError('Unsafe F02 factorization accepted')
    m=build_tensor([singleton('a',zero)],True);t=table(m,('F01',),'unknown')
    for vector in ([0,0,0],[True,0,0,0],[3,0,0,0],['0',0,0,0]):
        try:logical_row(m,t,('F01',),{'F01':vector})
        except ValueError:rejected.append('malformed_observation_'+repr(vector))
        else:raise AssertionError('Malformed observation accepted')
    outside=logical_row(m,t,('F01',),{'F01':[1,1,1,1]});assert outside==[0]*6+[None]*14
    args.output_dir.mkdir(parents=True)
    fixture_json={'input_kind':'ARTIFICIAL_ONLY','fixtures':[{'id':n,'states':s,'factor_f02':f} for n,s,f in fixtures]}
    (args.output_dir/'fixtures.json').write_text(json.dumps(fixture_json,indent=2)+'\n')
    here=Path(__file__).parent
    report={'schema':'root_information_artificial_validation_v1','input_kind':'ARTIFICIAL_ONLY','all_pass':True,
            'cases':receipts,'abstract_V02_not_signature_realization':{'target_numerators_over32':[[8,-8],[-8,8]],'joint_positive_count':0},
            'abstract_V07_not_signature_realization':{'exists_all_minimal_masks':[1],'fixed_positive_observation_local_minimal_masks':[3]},
            'rejected_inputs':rejected,'outside_alphabet_conflict_has_null_bounds':True,
            'code_sha256':{n:sha256((here/n).read_bytes()).hexdigest() for n in ('core_v1.py','summaries_v1.py','test_artificial_v1.py')},
            'numpy_version':np.__version__,'new_real_inputs_or_results_read':False}
    (args.output_dir/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'all_pass':True,'cases':len(receipts),'fibres':sum(r['logical_fibres_checked'] for r in receipts),'witnesses':sum(r['complete_witnesses_checked'] for r in receipts)}))


if __name__=='__main__':main()
