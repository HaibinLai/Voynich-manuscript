#!/usr/bin/env python3
"""Small artificial full-six direct oracle; never reads real F domains."""
import argparse
import copy
from fractions import Fraction
import itertools
import json
from pathlib import Path
import grouped_v1 as eng

U=(0,0,0,0); V=(2,0,0,0); W=(0,2,0,0)


def packet(domains):
    states=[]
    for g,dom in zip(eng.GS,domains):
        states.append({'id':g,'entries':{e:[list(v) for v in dom[e]] for e in eng.IDS},
          'preimages':{e:[{'signature':list(v),'witnesses':[{'case_id':e+'_ARTIFICIAL_'+str(i),
             'extra_index':0,'counted_vector':list(v),'extra_vector':[0,0,0,0],
             'signature':list(v),'scope':'ARTIFICIAL ONLY'}]} for i,v in enumerate(dom[e])] for e in eng.IDS}})
    branches={k:[{'a':a,'b':b,'weight':v} for (a,b),v in values.items()] for k,values in eng.expected_branches().items()}
    return {'states':states,'branches':branches,'conditional_product_declared':True,
            'cross_entry_constraints':[{'id':'ARTIFICIAL_SHARED_G'}]}


def value(z):
    """Fraction-based original formula, separate from engine's integer formula."""
    def s(a,b):return 1-Fraction(sum(abs(x-y) for x,y in zip(z[a],z[b])),8)
    h=(s('F03','F04')+s('F05','F06'))/2-(s('F01','F04')+s('F01','F06')+s('F03','F06')+s('F05','F04'))/4
    h4=(s('F03','F04')+s('F05','F06')-s('F03','F06')-s('F05','F04'))/2
    return tuple(int(x*32) for x in (h,h4,h-h4))


def full_states(p):
    out=[]
    for gi,st in enumerate(p['states']):
        for vals in itertools.product(*(st['entries'][e] for e in eng.IDS)):
            z=tuple(map(tuple,vals));v=value(dict(zip(eng.IDS,z)))
            out.append((gi,z,v))
    return out


def oracle_row(states,regime,obs):
    selected=[s for s in states if (regime=='unknown' or eng.GS[s[0]]==regime) and all(s[1][eng.IDS.index(e)]==tuple(v) for e,v in obs.items())]
    if not selected:return [0,0,0,0,0,0]+[None]*6
    unique={s[1] for s in selected}; positive=[s for s in selected if s[2][0]>0 and s[2][1]>0]
    puniq={s[1] for s in positive}
    cls=1 if not positive else 3 if len(positive)==len(selected) else 2
    mask=sum(1<<g for g in {s[0] for s in selected})
    bounds=[f(s[2][i] for s in selected) for i in range(3) for f in (min,max)]
    return [cls,len(unique),len(selected),len(puniq),len(positive),mask]+bounds


def min_brute(masks):
    values=set(masks)
    return sorted(m for m in values if all(t not in values for t in range(64) if t!=m and t&m==t))


def compare_complete(p, label):
    alph,core,tables,summ=eng.analyze(p)
    states=full_states(p); checked=0; witness_count=0; certificate_count=0
    oracle_summary={}
    for regime in eng.REGIMES:
        rows=[]
        for mask in range(64):
            observed=[e for i,e in enumerate(eng.IDS) if mask&(1<<i)]
            counts=[0]*4
            for vals in itertools.product(*(alph[e] for e in observed)):
                obs=dict(zip(observed,vals));expected=oracle_row(states,regime,obs)
                actual=eng.row_query(tables,alph,regime,obs)
                assert actual[:12]==expected,(label,regime,mask,obs,actual,expected)
                counts[expected[0]]+=1;checked+=1
                for k,sid in enumerate(actual[12:]):
                    if sid is None:continue
                    w=eng.witness(p,alph,regime,obs,sid);z=w['assignment'];scores=value(z)
                    assert list(scores)==w['score_numerators32']
                    assert all(tuple(z[e])==tuple(v) for e,v in obs.items())
                    assert all(w['all_compatible_local_origins'][e] for e in eng.IDS)
                    if k<6:assert scores[k//2]==actual[6+k]
                    elif k==6:assert scores[0]>0 and scores[1]>0
                    else:assert not(scores[0]>0 and scores[1]>0)
                    witness_count+=1
                if expected[0] in (1,3):
                    good=[]
                    for sub in range(64):
                        if sub&mask!=sub:continue
                        subobs={e:v for e,v in obs.items() if sub&(1<<eng.IDS.index(e))}
                        if oracle_row(states,regime,subobs)[0]==expected[0]:good.append(sub)
                    assert eng.certificates(tables,alph,regime,obs)==min_brute(good)
                    certificate_count+=1
            declared=summ['logical64'][regime][mask]
            assert declared['class_counts']==counts
            assert declared['feasible_observations']==sum(counts[1:])
            rows.append(counts)
        oracle_summary[regime]=rows
        for name,cs in [('ALL_JOINT_POSITIVE',[3]),('NONE_JOINT_POSITIVE',[1]),('DECISIVE_EITHER',[1,3])]:
            candidates=[i for i,r in enumerate(rows) if sum(r[c] for c in cs)]
            assert summ['minima'][regime]['existence'][name]['inclusion_minimal_masks']==min_brute(candidates)
        guarantee=min_brute([i for i,r in enumerate(rows) if sum(r[1:]) and r[2]==0])
        assert summ['minima'][regime]['guarantee_inclusion_minimal_masks']==guarantee
    both=min_brute([m for m in range(64) if all(oracle_summary[g][m][2]==0 and sum(oracle_summary[g][m][1:]) for g in eng.GS)])
    assert summ['both_known_g_guarantee_minimal_masks']==both
    # Refinement on each exact full signature; each coarser row contains the same full state.
    for regime in eng.REGIMES:
        for gi,z,v in states:
            if regime!='unknown' and eng.GS[gi]!=regime:continue
            for mask in range(64):
                obs={e:z[i] for i,e in enumerate(eng.IDS) if mask&(1<<i)}
                row=eng.row_query(tables,alph,regime,obs)
                assert row[0]!=0
                for i in range(3):assert row[6+2*i]<=v[i]<=row[7+2*i]
                for i,e in enumerate(eng.IDS):
                    refined=eng.row_query(tables,alph,regime,{**obs,e:z[i]})
                    for j in range(3):assert refined[6+2*j]>=row[6+2*j] and refined[7+2*j]<=row[7+2*j]
                    if row[0] in (1,3):assert refined[0]==row[0]
            assert eng.row_query(tables,alph,regime,dict(zip(eng.IDS,z)))[0]!=2
    return {'fixture':label,'full_tagged_states':len(states),'all64_and_three_regimes':True,
            'ambient_queries_checked':checked,'complete_witnesses_checked':witness_count,
            'outcome_certificates_checked':certificate_count,'all_pass':True},(alph,core,tables,summ)


def expect_error(fn):
    try:fn()
    except ValueError:return
    raise AssertionError('Expected rejection')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,required=True);args=parser.parse_args()
    if args.output_dir.exists():raise ValueError('New output directory required')
    base={'F01':[U], 'F02':[U,V], 'F03':[U], 'F04':[U,V], 'F05':[W], 'F06':[U,W]}
    other=copy.deepcopy(base);other['F01']=[V];other['F03']=[V]
    p=packet([base,other]); receipts=[]
    r,analysis=compare_complete(p,'V05_ORIGINAL_FORMULA_SHARED_G');receipts.append(r)
    alph,core,tables,summ=analysis
    assert eng.row_query(tables,alph,'unknown',{'F01':U,'F03':V})[0]==0
    assert eng.row_query(tables,alph,eng.GS[0],{'F01':V})[0]==0
    assert eng.row_query(tables,alph,'unknown',{'F02':W})[0]==0
    for obs in [{'F01':[0,0]}, {'F01':[True,0,0,0]}, {'F01':[3,0,0,0]}, {'F07':U}]:
        expect_error(lambda:eng.row_query(tables,alph,'unknown',obs))
    expect_error(lambda:eng.row_query(tables,alph,'wrong-g',{}))
    bad=copy.deepcopy(p);bad['states'][1]['entries']['F02']=[list(V)];bad['states'][1]['preimages']['F02']=bad['states'][1]['preimages']['F02'][1:]
    expect_error(lambda:eng.validate(bad))
    # V03 exact g duplicate plus repeated origins; only g tagging changes the two count columns.
    overlap=packet([base,base]);r,old=compare_complete(overlap,'V03_DUPLICATE_G');receipts.append(r)
    dupe=copy.deepcopy(overlap)
    for state in dupe['states']:
        for records in state['preimages'].values():
            for rec in records:rec['witnesses']*=3
    assert eng.analyze(dupe)[2:]==old[2:]
    empty=old[2][('unknown',0)]['rows'][0]
    assert empty[2]==2*empty[1] and empty[4]==2*empty[3]
    # V01/V02 are abstract classifier records, not asserted signature realizations.
    assert eng.classify(0,0)==0 and eng.classify(1,0)==1 and eng.classify(1,1)==3
    pairs=[(Fraction(1,4),-Fraction(1,4)),(-Fraction(1,4),Fraction(1,4))]
    assert max(x for x,y in pairs)>0 and max(y for x,y in pairs)>0
    assert eng.classify(len(pairs),sum(x>0 and y>0 for x,y in pairs))==1
    # A separate actual-formula artificial fixture with two singleton core assignments.
    a={e:U for e in eng.IDS}; a['F01']=V
    b={'F01':U, 'F02':U, 'F03':W, 'F04':U, 'F05':(1,2,0,0), 'F06':(1,0,0,0)}
    assert value(a)[0]>0 and value(a)[1]<=0
    assert value(b)[0]<=0 and value(b)[1]>0
    domains=[{e:[z[e]] for e in eng.IDS} for z in (a,b)]
    nojoint=packet(domains);r,nj=compare_complete(nojoint,'FORMULA_DERIVED_NO_JOINT_POSITIVE');receipts.append(r)
    nr=nj[2][('unknown',0)]['rows'][0]
    assert nr[0]==1 and nr[7]>0 and nr[9]>0 and nr[3]==0
    # V07 abstract decision logic: P = A and B. Not a six-entry signature claim.
    abstract=list(itertools.product([0,1],repeat=2))
    def decision(mask,obs):
        ps={bool(a and b) for a,b in abstract if all((a,b)[i]==obs[i] for i in range(2) if mask&(1<<i))}
        return 'MIXED' if len(ps)>1 else 'ALL' if True in ps else 'NONE'
    assert decision(3,(1,1))=='ALL' and decision(1,(1,1))=='MIXED' and decision(2,(1,1))=='MIXED'
    assert decision(1,(0,1))=='NONE'
    # CLI gate must reject a real wrapper before score enumeration without approval.
    class Args:approval=None
    expect_error(lambda:eng.verify_approval(Args(),{'input_kind':'REAL_F_IDEAL_INFORMATION'}))
    args.output_dir.mkdir(parents=True)
    eng.dump(args.output_dir/'input_v1.json',{'schema':'independent_ideal_information_input_v1','input_kind':'ARTIFICIAL','outer_packet':p})
    eng.dump(args.output_dir/'receipt_v1.json',{'schema':'independent_information_artificial_receipt_v1','all_pass':True,
        'engine_sha256':eng.sha(eng.__file__),'test_sha256':eng.sha(__file__),'fixtures':receipts,
        'V01_V02_scope':'Abstract classifier objective records; no geometry attainability claim.',
        'V07_scope':'Abstract binary predicate certificates; not original-formula signature geometry.',
        'formula_derived_no_joint_objective_numerators32':[list(value(a)),list(value(b))],
        'formula_derived_assignments':[a,b],
        'F02_unequal_domain_rejected':True,'missing_real_approval_rejected':True,'wrong_input_and_conflict_distinguished':True,
        'redundant_origins_leave_all_tables_unchanged':True,'real_data_read':False,'real_conditioned_analysis_run':False})
    print(json.dumps({'all_pass':True,'fixtures':receipts}))

if __name__=='__main__':main()
