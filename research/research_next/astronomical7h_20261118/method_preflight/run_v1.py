"""Fixed artificial circular-control checks; never reads manuscript data."""
from fractions import Fraction
from itertools import product
from pathlib import Path
import datetime as dt
import hashlib
import json

HERE=Path(__file__).resolve().parent

def serial(value):
    if isinstance(value,Fraction):return {'numerator':value.numerator,'denominator':value.denominator}
    if isinstance(value,dict):return {k:serial(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [serial(v) for v in value]
    return value

def shifts(matrix):
    n=len(matrix)
    assert n>0 and all(len(row)==n for row in matrix)
    assert all(x in (0,1) for row in matrix for x in row)
    return [Fraction(sum(matrix[i][(i+s)%n] for i in range(n)),n) for s in range(n)]

def summarize(matrix):
    n=len(matrix);scores=shifts(matrix);avg=sum(scores,Fraction())/n
    return {'n':n,'matrix':matrix,'phase_scores':scores,'cycle_mean':avg,
            'own_minus_cycle_mean':scores[0]-avg,
            'all_maximizing_shifts':[s for s,t in enumerate(scores) if t==max(scores)],
            'phases_at_least_own':[s for s,t in enumerate(scores) if t>=scores[0]],
            'descriptive_own_upper_rank_fraction':Fraction(sum(t>=scores[0] for t in scores),n),
            'rank_is_p_value':False,'reason':'No exchangeability assumption supplied for any manuscript.'}

def phrase_in_region(phrase,region):
    assert phrase
    return any(tuple(region[j:j+len(phrase)])==tuple(phrase) for j in range(len(region)-len(phrase)+1))

def exact_unknown_delta_bounds(matrix):
    n=len(matrix);lo=hi=Fraction()
    for i,row in enumerate(matrix):
        for j,value in enumerate(row):
            weight=Fraction(n-1 if i==j else -1,n*n)
            if value is None:
                lo+=min(Fraction(),weight);hi+=max(Fraction(),weight)
            else:
                lo+=weight*value;hi+=weight*value
    return lo,hi

def main():
    freeze=json.loads((HERE/'input_freeze_v1.json').read_text())
    assert hashlib.sha256((HERE/'protocol_v1.txt').read_bytes()).hexdigest()==freeze['files'][0]['sha256']
    n=12
    matrices={
        'unique_alignment':[[int(i==j) for j in range(n)] for i in range(n)],
        'ubiquitous':[[1 for j in range(n)] for i in range(n)],
        'periodic_two':[[int(i%2==j%2) for j in range(n)] for i in range(n)],
        'reversed_order':[[int(j==(-i)%n) for j in range(n)] for i in range(n)],
    }
    labels=[['d'+str(i).zfill(2)] for i in range(n)]
    regions=[label+['separator']+label for label in labels]
    matrices['independent_copy_tokens']=[[int(phrase_in_region(label,region)) for region in regions] for label in labels]
    results={name:summarize(matrix) for name,matrix in matrices.items()}
    assert results['unique_alignment']['all_maximizing_shifts']==[0]
    assert results['ubiquitous']['own_minus_cycle_mean']==0
    assert results['periodic_two']['all_maximizing_shifts']==list(range(0,12,2))
    assert matrices['independent_copy_tokens']==matrices['unique_alignment']
    assert results['reversed_order']['phase_scores']==[Fraction(1,6) if s%2==0 else Fraction() for s in range(12)]
    results['independent_copy_tokens']['semantic_limit']='Markers are copied artificial identifiers with no supplied meanings. A perfect positional pattern cannot determine language, phonetics or referents.'
    boundaries=[
        {'name':'not_substring','phrase':['a'],'regions':[['aa']],'expected':False},
        {'name':'not_noncontiguous','phrase':['a','b'],'regions':[['a','x','b']],'expected':False},
        {'name':'not_cross_region','phrase':['a','b'],'regions':[['a'],['b']],'expected':False},
        {'name':'same_region_adjacent','phrase':['a','b'],'regions':[['x','a','b','z']],'expected':True},
    ]
    for b in boundaries:
        b['actual']=any(phrase_in_region(b['phrase'],r) for r in b['regions'])
        assert b['actual']==b['expected'],b
    # Exhaustive counts use integer numerators, independently of Fraction summaries.
    exhaustive=[]
    for n in range(1,5):
        count=0
        for flat in product((0,1),repeat=n*n):
            totals=[sum(flat[i*n+(i+s)%n] for i in range(n)) for s in range(n)]
            all_sum=sum(flat)
            diagonal=sum(flat[i*n+i] for i in range(n))
            assert sum(totals)==all_sum
            assert n*totals[0]-sum(totals)==(n-1)*diagonal-(all_sum-diagonal)
            count+=1
        exhaustive.append({'n':n,'all_binary_matrices':count,'identities_passed':True})
    missing=[[1,None,0],[0,None,0],[None,0,1]]
    unknown_positions=[(i,j) for i,row in enumerate(missing) for j,x in enumerate(row) if x is None]
    completions=[]
    for values in product((0,1),repeat=len(unknown_positions)):
        matrix=[row[:] for row in missing]
        for (i,j),x in zip(unknown_positions,values):matrix[i][j]=x
        result=summarize(matrix)
        completions.append({'unknown_values':list(values),**result})
    bounds=exact_unknown_delta_bounds(missing)
    deltas=[v['own_minus_cycle_mean'] for v in completions]
    assert bounds==(min(deltas),max(deltas))
    per_phase_bounds=[(min(v['phase_scores'][s] for v in completions),max(v['phase_scores'][s] for v in completions)) for s in range(3)]
    zero_filled=[[0 if x is None else x for x in row] for row in missing]
    missing_result={'n':3,'matrix_with_null':missing,'unknown_positions':unknown_positions,
                    'complete_enumeration_count':len(completions),'all_completions':completions,
                    'phase_score_bounds':per_phase_bounds,'exact_delta_bounds':bounds,
                    'naively_zero_filled':summarize(zero_filled),
                    'own_is_unique_maximum_for_all_completions':all(v['all_maximizing_shifts']==[0] for v in completions),
                    'scope':'Cell roles and token boundaries defined by construction. Undefined manuscript object/word roles are not binary missing cells and cannot be rescued by these bounds.'}
    assert missing_result['own_is_unique_maximum_for_all_completions'] is False
    out={'utc':dt.datetime.now(dt.timezone.utc).isoformat(),'status':'PASS_FIXED_ARTIFICIAL_CHECKS',
         'protocol_sha256':hashlib.sha256((HERE/'protocol_v1.txt').read_bytes()).hexdigest(),
         'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
         'data_origin':'Only fixed artificial symbols and matrices. No manuscript data read.',
         'real_manuscript_scores_computed':False,
         'fixed_twelve_cases':results,'phrase_boundary_cases':boundaries,
         'exhaustive_identity_checks':exhaustive,'fixed_unknown_case':missing_result,
         'global_limit':'Method preflight does not authorize real scoring or establish meaning.'}
    (HERE/'results_v1.json').write_text(json.dumps(serial(out),ensure_ascii=False,indent=2)+'\n')
    print('artificial cases',len(results),'boundary cases',len(boundaries),'exhaustive matrices',sum(x['all_binary_matrices'] for x in exhaustive))
    print('unknown delta bounds',bounds,'unique own across completions',missing_result['own_is_unique_maximum_for_all_completions'])

if __name__=='__main__':main()
