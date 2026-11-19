"""Prepare a source-bound inherited model; never calculate new conditioned scores."""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PRIOR=Path('research/research_next/hierarchical7h_20261119')


def digest(path):return sha256(path.read_bytes()).hexdigest()


def build():
    freeze=json.loads((HERE/'prior_input_freeze_v1.json').read_text())
    expected={r['path']:r['sha256'] for r in freeze['inputs']}
    paths={'prior_model':PRIOR/'outer_calibration_v1/input_v1.json',
           'observation':PRIOR/'F_observation_v1/observation_v1.json',
           'prior_outcome':PRIOR/'calibration_outcome_v2.json',
           'prior_count_erratum':PRIOR/'calibration_outcome_v2_count_erratum_v1.json'}
    sources={}
    for name,path in paths.items():
        assert digest(ROOT/path)==expected[str(path)]
        sources[name]={'path':str(path),'sha256':expected[str(path)]}
    prior=json.loads((ROOT/paths['prior_model']).read_text())
    model=prior['global_model'];assert model['kind']=='union_of_state_tagged_cartesian_outer_domains'
    assert model['conditional_product_is_outer_relaxation_not_real_independence'] is True
    assert len(model['constraints_retained'])==1 and model['constraints_retained'][0]['id']=='G_terminal_boundary_interpretation'
    labels=['terminal_region_reading','opaque_boundary_reading']
    assert [s['id'] for s in prior['states']]==labels
    assert prior['states'][0]['entries']['F02']==prior['states'][1]['entries']['F02']
    assert prior['states'][0]['entries']['F02']
    assert all(r['a']!='F02' and r['b']!='F02' for rows in prior['branches'].values() for r in rows)
    outcome=json.loads((ROOT/paths['prior_outcome']).read_text())
    return {'schema':'whole_entry_information_input_v1','input_kind':'INHERITED_REAL_ALGEBRA_NO_NEW_OBSERVATION',
            'states':[{'id':s['id'],'entries':deepcopy(s['entries'])} for s in prior['states']],
            'global_model':deepcopy(model),'branches':deepcopy(prior['branches']),
            'factor_f02':True,'factorization_preconditions':{'zero_target_coefficients':True,'same_nonempty_domain_every_g':True,
              'conditional_product_scope':'Only the reviewed declared fifth-window outer model, not actual image independence.'},
            'sources':sources,'original_name_design':outcome['fixed_name_design_preserved'],
            'strict_literal_H':outcome['strict_literal_H'],
            'contract_sha256':digest(HERE/'method_proposal_v1.json'),
            'review_sha256':digest(HERE/'method_review_v1.json'),
            'builder_sha256':digest(Path(__file__)),
            'scope':'Ideal whole-signature information on the frozen conservative model. No new image fact, probability or semantic translation.'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    with a.output.open('x') as f:json.dump(build(),f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'output':str(a.output),'sha256':digest(a.output),'new_conditioned_results_computed':False}))
