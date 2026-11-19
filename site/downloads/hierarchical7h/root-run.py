"""Frozen-design exact bounds runner; no image inference or name completion."""
import argparse
from fractions import Fraction
import hashlib
from itertools import combinations
import json
from pathlib import Path
from bounds import checked_domains, contribution_at, evaluate8, optimize, score8

IDS = tuple(f'F{i:02d}' for i in range(1, 7))
LEFT, RIGHT = ('F01', 'F03', 'F05'), ('F04', 'F06')
H = {('F01', 'F04'): -1, ('F01', 'F06'): -1,
     ('F03', 'F04'): 2, ('F03', 'F06'): -1,
     ('F05', 'F04'): -1, ('F05', 'F06'): 2}
H4 = {('F03', 'F04'): 2, ('F03', 'F06'): -2,
      ('F05', 'F04'): -2, ('F05', 'F06'): 2}
DIFF = {key: H.get(key, 0) - H4.get(key, 0) for key in H}
OBJECTIVES = {'H': H, 'H4': H4, 'H_minus_H4': DIFF}


def validate(packet):
    if packet['schema'] != 'joint_signature_domains_v1' or set(packet['entries']) != set(IDS):
        raise ValueError('All six fixed entries required')
    model = packet.get('cross_entry_model', {})
    if model.get('kind') != 'cartesian_entry_domains' or model.get('constraints') != [] or not model.get('justification'):
        raise ValueError('Unsupported or unreviewed cross-entry constraints; no silent relaxation')
    domains = checked_domains(packet['entries'])
    if any(len(domains[k]) != len(packet['entries'][k]) for k in IDS):
        raise ValueError('Duplicate input signatures')
    if set(packet['branches']) != {'H', 'H4'}:
        raise ValueError('Both frozen branches required')
    for key in ('H', 'H4'):
        actual = {}
        for edge in packet['branches'][key]:
            pair = tuple(sorted((edge['a'], edge['b'])))
            if pair in actual:
                raise ValueError('Duplicate pair')
            actual[pair] = Fraction(edge['weight'])
        expected = {tuple(sorted(pair)): Fraction(weight, 4) for pair, weight in OBJECTIVES[key].items()}
        if actual != expected:
            raise ValueError('Changed frozen pairs or weights')
    return domains


def state_details(state):
    values = {name: Fraction(evaluate8(state, weights), 32) for name, weights in OBJECTIVES.items()}
    assert values['H'] - values['H4'] == values['H_minus_H4']
    identity = Fraction(score8(state['F03'], state['F06']) + score8(state['F05'], state['F04'])
                        - score8(state['F01'], state['F04']) - score8(state['F01'], state['F06']), 32)
    assert identity == values['H_minus_H4']
    return {'assignment': state, 'values': values,
            'feature_contributions': {name: contribution_at(state, weights, 4) for name, weights in OBJECTIVES.items()},
            'pair_similarities': {a + '--' + b: Fraction(score8(state[a], state[b]), 8) for a, b in combinations(IDS, 2)},
            'same_state_difference_identity_checked': True}


def run(packet):
    domains = validate(packet)
    objectives = {}
    for name, weights in OBJECTIVES.items():
        result = optimize(domains, LEFT, RIGHT, weights, 4)
        objectives[name] = {'lower': result['bounds']['lower']['value'], 'upper': result['bounds']['upper']['value'],
                            'endpoints': {side: state_details(ep['assignment']) for side, ep in result['bounds'].items()},
                            'right_assignments_enumerated': result['right_assignments_enumerated']}
    pairs = []
    same = {('F03', 'F04'), ('F05', 'F06')}
    primary = {tuple(sorted(k)) for k in H}
    for a, b in combinations(IDS, 2):
        candidates = [(score8(x, y), x, y) for x in domains[a] for y in domains[b]]
        lo, hi = min(v for v, _, _ in candidates), max(v for v, _, _ in candidates)
        if 'F02' in (a, b):
            relation, scope = 'unknown', 'name_relation_unqualified'
        else:
            relation = 'same_conditional' if (a, b) in same else 'different_conditional'
            scope = 'primary_cross_manuscript' if (a, b) in primary else 'within_manuscript_description'
        pairs.append({'a': a, 'b': b, 'name_relation': relation, 'scope': scope,
                      'lower': Fraction(lo, 8), 'upper': Fraction(hi, 8),
                      'endpoint_witnesses': {side: {a: next(x for v, x, y in candidates if v == target),
                                                    b: next(y for v, x, y in candidates if v == target)}
                                             for side, target in [('lower', lo), ('upper', hi)]}})
    common = set.intersection(*(set(domains[i]) for i in LEFT + RIGHT))
    if common:
        assert objectives['H']['lower'] <= 0 <= objectives['H']['upper']
        assert objectives['H4']['lower'] <= 0 <= objectives['H4']['upper']
    return {'schema': 'root_joint_signature_bounds_v1', 'input_kind': packet.get('input_kind'),
            'objectives': objectives, 'pairs': pairs, 'pair_count': 15,
            'primary_same_count': 2, 'primary_different_count': 4,
            'strict_unexpanded_visual_name_H': None,
            'strict_branch_reason': 'Only F01 has an eligible complete visual string: no mixed-name comparison.',
            'conditional_branch_common_signatures': sorted(common),
            'constant_coordinates': {i: {str(k): domains[i][0][k] for k in range(4) if len({v[k] for v in domains[i]}) == 1} for i in IDS},
            'numerical_double_positive_condition': objectives['H']['lower'] > 0 and objectives['H4']['lower'] > 0,
            'return_to_voynich_authorized': False,
            'limits': ['Exact extrema of supplied algebraic domains, not statistical intervals or certified geometric attainability.',
                       'Shared entry signatures used across pairs; within-entry dependencies retained.',
                       'Conditional catalogue and abbreviation names; informed small sample, no general recognition accuracy.']}


def serialize(value):
    if isinstance(value, Fraction):
        return str(value)
    raise TypeError(type(value).__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError('Refusing to overwrite an existing result directory')
    raw = args.input.read_bytes()
    result = run(json.loads(raw))
    result['input_sha256'] = hashlib.sha256(raw).hexdigest()
    result['source_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in (Path(__file__), Path(__file__).with_name('bounds.py'))}
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, default=serialize) + '\n')


if __name__ == '__main__':
    main()
