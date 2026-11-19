"""Artificial state-union checks against direct complete-state enumeration."""
import argparse
import copy
from fractions import Fraction
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
import random

from run_outer_v1 import calculate, IDS, HERE
from run import H, H4, run


def reference(assignment):
    similarity = lambda a, b: Fraction(8 - sum(abs(x-y) for x,y in zip(assignment[a], assignment[b])), 8)
    h = (similarity('F03','F04') + similarity('F05','F06'))/2 - (similarity('F01','F04') + similarity('F01','F06') + similarity('F03','F06') + similarity('F05','F04'))/4
    h4 = (similarity('F03','F04') + similarity('F05','F06') - similarity('F03','F06') - similarity('F05','F04'))/2
    return {'H':h, 'H4':h4, 'H_minus_H4':h-h4}, {(a,b):similarity(a,b) for a,b in combinations(IDS,2)}


def packet(states):
    return {'schema':'state_tagged_outer_signature_domains_v1', 'input_kind':'ARTIFICIAL_ONLY',
            'global_model':{'kind':'union_of_state_tagged_cartesian_outer_domains',
                            'variable_id':'ARTIFICIAL_SHARED_STATE',
                            'constraints_retained':[{'id':'ARTIFICIAL_SAME_STATE_FOR_ALL_ENTRIES'}],
                            'conditional_product_is_outer_relaxation_not_real_independence':True},
            'states':states, 'branches':{name:[{'a':a,'b':b,'weight':str(Fraction(w,4))} for (a,b),w in weights.items()] for name,weights in [('H',H),('H4',H4)]}}


def check(data):
    actual = calculate(data)
    values, pair_values, count = {name:[] for name in ('H','H4','H_minus_H4')}, {pair:[] for pair in combinations(IDS,2)}, 0
    states = {state['id']:state for state in data['states']}
    for state in data['states']:
        for chosen in product(*(state['entries'][name] for name in IDS)):
            count += 1
            objectives, pairs = reference(dict(zip(IDS,chosen)))
            for name,value in objectives.items(): values[name].append(value)
            for pair,value in pairs.items(): pair_values[pair].append(value)
    for name,row in actual['objectives'].items():
        assert (row['lower'],row['upper']) == (min(values[name]),max(values[name]))
    for row in actual['pairs']:
        expected = pair_values[(row['a'],row['b'])]
        assert (row['lower'],row['upper']) == (min(expected),max(expected))
    endpoints = [ep for row in actual['objectives'].values() for ep in row['endpoints'].values()]
    endpoints += [ep for row in actual['pairs'] for ep in row['endpoints'].values()]
    for endpoint in endpoints:
        state = states[endpoint['global_state']]
        assignment = endpoint['assignment']
        assert all(list(assignment[name]) in state['entries'][name] for name in IDS)
        expected,pairs = reference(assignment)
        assert expected == endpoint['values']
        assert all(sum(endpoint['feature_contributions'][name]) == value for name,value in expected.items())
        assert all(endpoint['pair_similarities'][a+'--'+b] == value for (a,b),value in pairs.items())
    return count


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    rng=random.Random(1937);cases=[];total=0
    coupled=packet([{'id':'s0','entries':{name:[[0,0,0,0]] for name in IDS}},
                    {'id':'s1','entries':{name:[[2,2,2,2]] for name in IDS}}])
    total += check(coupled)
    exact=calculate(coupled)
    assert all(row['lower']==row['upper']==0 for row in exact['objectives'].values())
    pooled={'schema':'joint_signature_domains_v1','input_kind':'ARTIFICIAL_ONLY',
            'entries':{name:[[0,0,0,0],[2,2,2,2]] for name in IDS},'branches':coupled['branches'],
            'cross_entry_model':{'kind':'cartesian_entry_domains','constraints':[],'justification':'Deliberately pooled artificial contrast to test loss of shared state.'}}
    wrong=run(pooled)
    assert wrong['objectives']['H']['lower'] < 0 < wrong['objectives']['H']['upper']
    cases.append({'id':'shared_state_must_not_be_pooled','complete_states':2,'passed':True})
    for index in range(12):
        states=[]
        for state_index in range(1+index%3):
            domains={}
            for name in IDS:
                vectors=set()
                for _ in range(1+(index+state_index)%2): vectors.add(tuple(rng.randrange(3) for _ in range(4)))
                domains[name]=[list(v) for v in sorted(vectors)]
            states.append({'id':str(state_index),'entries':domains})
        count=check(packet(states));total+=count
        cases.append({'id':'random_'+str(index),'complete_states':count,'passed':True})
    bads=[]
    for label,mutate in [('duplicate-global-state',lambda x:x['states'].append(copy.deepcopy(x['states'][0]))),
                         ('wrong-model',lambda x:x['global_model'].update(kind='pooled')),
                         ('undeclared-relaxation',lambda x:x['global_model'].update(conditional_product_is_outer_relaxation_not_real_independence=False)),
                         ('real-without-source',lambda x:x.update(input_kind='FROZEN_F_RECORD_CONDITIONAL_OUTER_ALLOWANCE'))]:
        bad=copy.deepcopy(coupled);mutate(bad)
        try:calculate(bad)
        except ValueError:bads.append(label)
        else:raise AssertionError(label)
    out={'schema':'root_outer_artificial_validation_v1','input_kind':'ARTIFICIAL_ONLY',
         'all_pass':True,'cases':cases,'complete_states_checked':total,'six_objective_endpoints_and_all_15_pairs_checked':True,
         'all_endpoint_global_state_and_full_assignment_checked':True,'rejected_inputs':bads,
         'source_sha256':{p.name:sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),HERE/'run_outer_v1.py',HERE/'method_engine/run.py',HERE/'method_engine/bounds.py']},
         'real_F_observation_or_scores_read':False}
    with args.output.open('x') as handle:json.dump(out,handle,indent=2);handle.write('\n')
    print(json.dumps({'cases':len(cases),'states':total,'all_pass':True}))


if __name__=='__main__':main()
