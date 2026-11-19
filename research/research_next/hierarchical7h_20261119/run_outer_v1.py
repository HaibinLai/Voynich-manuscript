"""Exact union of state-tagged conditional outer domains; no image inference."""
import argparse
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'method_engine'))
from run import IDS, OBJECTIVES, run, serialize, state_details
from build_outer_input_v1 import build


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def source_bindings(state, assignment, observation):
    if observation is None:
        return {name: {'kind': 'ARTIFICIAL_ONLY', 'signature': list(vector)}
                for name, vector in assignment.items()}
    originals = {entry['id']: entry for entry in observation['entries']}
    projections = {entry['id']: entry for entry in state['entry_projections']}
    result = {}
    for name in IDS:
        vector = list(assignment[name])
        projected = projections[name]
        origins = next(p['origins'] for p in projected['preimages'] if p['signature'] == vector)
        origin = origins[0]
        case = next(c for c in originals[name]['cases'] if c['id'] == origin['case_id'])
        assert case['id'] in state['source_case_ids'][name]
        base = next(c['base_counts'] for c in projected['case_records'] if c['case_id'] == case['id'])
        extra = case['residual']['vectors'][origin['extra_index']]
        assert [min(2, a + b) for a, b in zip(base, extra)] == vector
        result[name] = {'signature': vector, 'case_id': case['id'],
                        'extra_index': origin['extra_index'], 'base_counts': base,
                        'extra_vector': extra, 'selected_unit_classes': case['unit_classes'],
                        'selected_join_ids': case['join_ids'],
                        'case_metadata_source': f"entries/{name}/cases/{case['id']} in frozen observation",
                        'algebraic_preimage_not_certified_geometric_remainder': True}
    return result


def calculate(packet, observation=None):
    if packet['schema'] != 'state_tagged_outer_signature_domains_v1':
        raise ValueError('Unsupported outer input')
    model = packet['global_model']
    if model['kind'] != 'union_of_state_tagged_cartesian_outer_domains':
        raise ValueError('State-tagged union required')
    if model.get('conditional_product_is_outer_relaxation_not_real_independence') is not True:
        raise ValueError('Outer relaxation must be explicit')
    states = packet['states']
    if not states or len({state['id'] for state in states}) != len(states):
        raise ValueError('Nonempty unique global states required')
    if packet['input_kind'] != 'ARTIFICIAL_ONLY' and observation is None:
        raise ValueError('Real source observation required for all endpoint bindings')
    per_state = []
    for state in states:
        conditional = {'schema': 'joint_signature_domains_v1',
                       'input_kind': packet['input_kind'], 'entries': state['entries'],
                       'branches': packet['branches'],
                       'cross_entry_model': {'kind': 'cartesian_entry_domains', 'constraints': [],
                                            'justification': 'Shared global state ' + state['id'] +
                                            ' is fixed by the outer wrapper. This conditional product is an explicitly reviewed outer relaxation; original constraints remain in the outer packet.'}}
        result = run(conditional)
        for objective in result['objectives'].values():
            for endpoint in objective['endpoints'].values():
                endpoint['global_state'] = state['id']
                endpoint['source_bindings'] = source_bindings(state, endpoint['assignment'], observation)
        for pair in result['pairs']:
            pair['complete_endpoint_witnesses'] = {}
            for side in ('lower', 'upper'):
                assignment = {name: values[0] for name, values in state['entries'].items()}
                assignment.update(pair['endpoint_witnesses'][side])
                witness = state_details(assignment)
                assert witness['pair_similarities'][pair['a'] + '--' + pair['b']] == pair[side]
                witness['global_state'] = state['id']
                witness['source_bindings'] = source_bindings(state, assignment, observation)
                pair['complete_endpoint_witnesses'][side] = witness
        per_state.append({'id': state['id'], 'result': result})
    objectives = {}
    for name in OBJECTIVES:
        row = {'endpoints': {}, 'attaining_global_states': {}}
        for side, operation in [('lower', min), ('upper', max)]:
            value = operation(state['result']['objectives'][name][side] for state in per_state)
            choices = [state for state in per_state if state['result']['objectives'][name][side] == value]
            row[side] = value
            row['attaining_global_states'][side] = [state['id'] for state in choices]
            row['endpoints'][side] = choices[0]['result']['objectives'][name]['endpoints'][side]
        objectives[name] = row
    pairs = []
    for index, original_pair in enumerate(per_state[0]['result']['pairs']):
        row = {key: original_pair[key] for key in ('a', 'b', 'name_relation', 'scope')}
        row['endpoints'], row['attaining_global_states'] = {}, {}
        for side, operation in [('lower', min), ('upper', max)]:
            value = operation(state['result']['pairs'][index][side] for state in per_state)
            choices = [state for state in per_state if state['result']['pairs'][index][side] == value]
            row[side] = value
            row['attaining_global_states'][side] = [state['id'] for state in choices]
            row['endpoints'][side] = choices[0]['result']['pairs'][index]['complete_endpoint_witnesses'][side]
        pairs.append(row)
    return {'schema': 'root_state_tagged_outer_bounds_v1', 'input_kind': packet['input_kind'],
            'global_model': model, 'per_state': per_state, 'objectives': objectives,
            'pairs': pairs, 'pair_count': 15, 'primary_same_count': 2, 'primary_different_count': 4,
            'strict_literal_H': {'status': 'MATHEMATICALLY_UNDEFINED_NAME_COVERAGE', 'value': None},
            'conditional_double_positive_numerical_gate': objectives['H']['lower'] > 0 and objectives['H4']['lower'] > 0,
            'return_to_voynich_authorized': False,
            'limits': ['Exact bounds of the declared conditional algebraic outer union; not confidence intervals or a precise image measurement.',
                       'Each endpoint has one shared g and one compatible case/extra preimage per entry, reused across every pair.',
                       'An algebraic source binding does not certify the literal remainder or attainability in an actual drawing.',
                       'Accepting frozen definite local facts and limiting g to the original T-cap ambiguity are necessary assumptions.',
                       'Different objective or pair endpoints need not occur in one common assignment.']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--observation', type=Path)
    parser.add_argument('--approval', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    packet = json.loads(raw)
    observation = None
    if packet['input_kind'] != 'ARTIFICIAL_ONLY':
        if args.observation is None or args.approval is None:
            raise ValueError('Frozen observation and numerical approval required')
        if packet != build(args.observation):
            raise ValueError('Input differs from source-derived g/case/provenance model')
        approval = json.loads(args.approval.read_text())
        expected = {'root_input_sha256': digest(args.input),
                    'root_outer_runner_sha256': digest(Path(__file__)),
                    'root_original_runner_sha256': digest(HERE / 'method_engine/run.py'),
                    'root_bounds_sha256': digest(HERE / 'method_engine/bounds.py'),
                    'root_builder_sha256': digest(HERE / 'build_outer_input_v1.py'),
                    'observation_sha256': digest(args.observation)}
        if approval.get('allow_real_outer_numeric') is not True or any(approval.get(k) != v for k, v in expected.items()):
            raise ValueError('Approval/source/code binding mismatch')
        observation = json.loads(args.observation.read_text())
    if args.output_dir.exists():
        raise FileExistsError('Refusing to overwrite outputs')
    result = calculate(packet, observation)
    result['input_sha256'] = sha256(raw).hexdigest()
    result['runner_sha256'] = digest(Path(__file__))
    result['observation_sha256'] = None if args.observation is None else digest(args.observation)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, default=serialize) + '\n')
    print(json.dumps({name: {side: str(row[side]) for side in ('lower', 'upper')}
                      for name, row in result['objectives'].items()}))


if __name__ == '__main__':
    main()
