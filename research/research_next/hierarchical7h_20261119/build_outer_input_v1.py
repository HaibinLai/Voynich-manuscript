"""Condition frozen record cases on one shared interpretation; no name scoring."""
import argparse
import copy
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'method_engine'))
from project import project_entry
from run import H, H4, IDS


def build(observation_path):
    raw = observation_path.read_bytes()
    observation = json.loads(raw)
    assert tuple(entry['id'] for entry in observation['entries']) == IDS
    assert all(entry['unit_defined'] is True for entry in observation['entries'])
    constraints = observation['cross_entry_constraints']
    assert len(constraints) == 1
    constraint = constraints[0]
    assert constraint['id'] == 'G_terminal_boundary_interpretation'
    assert constraint['potential_global_variable']['id'] == 'g_terminal_boundary'
    mapping = constraint['explicit_local_mapping']['F03']['case_map']
    expected = {'terminal_region_reading': ['F03_C1'], 'opaque_boundary_reading': ['F03_C2']}
    assert mapping == expected
    assert {state['id'] for state in constraint['potential_global_variable']['candidate_states']} == set(expected)
    branches = {name: [{'a': a, 'b': b, 'weight': str(Fraction(weight, 4))}
                       for (a, b), weight in weights.items()]
                for name, weights in [('H', H), ('H4', H4)]}
    states = []
    for state_id in expected:
        selected_entries = []
        for entry in observation['entries']:
            selected = copy.deepcopy(entry)
            if entry['id'] == 'F03':
                selected['cases'] = [case for case in selected['cases'] if case['id'] in mapping[state_id]]
                assert [case['id'] for case in selected['cases']] == mapping[state_id]
            selected_entries.append(selected)
        projections = [project_entry(entry) for entry in selected_entries]
        states.append({'id': state_id,
                       'entries': {row['id']: row['domain'] for row in projections},
                       'source_case_ids': {row['id']: [case['id'] for case in row['cases']] for row in selected_entries},
                       'entry_projections': projections})
    return {'schema': 'state_tagged_outer_signature_domains_v1',
            'input_kind': 'FROZEN_F_RECORD_CONDITIONAL_OUTER_ALLOWANCE',
            'observation_sha256': sha256(raw).hexdigest(),
            'builder_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'projector_sha256': sha256((HERE / 'method_engine/project.py').read_bytes()).hexdigest(),
            'global_model': {'kind': 'union_of_state_tagged_cartesian_outer_domains',
                             'variable_id': 'g_terminal_boundary',
                             'constraints_retained': constraints,
                             'conditional_product_is_outer_relaxation_not_real_independence': True},
            'states': states, 'branches': branches,
            'assumptions': ['Accept the frozen definite local facts and canonical identities.',
                            'The two g states only cover the existing upstream opaque-cap T ambiguity; they do not redefine C/Z/J.',
                            'Unknown state-conditioned remainder relations are conservatively enclosed, not certified independent or fully mapped.'],
            'provenance_scope': 'Every signature retains actual source case/extra indices from the original record. Algebraic preimages are not literal geometric realizations.',
            'pair_or_name_scores_computed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--observation', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.observation)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print(json.dumps({state['id']: [len(v) for v in state['entries'].values()] for state in result['states']}))
