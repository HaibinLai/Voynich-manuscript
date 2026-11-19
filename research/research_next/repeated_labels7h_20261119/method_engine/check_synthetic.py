"""Method counterexamples only. No manuscript observations are read."""
import json
from fractions import Fraction
from itertools import product
from binary_bounds import analyze


def rational(record):
    return Fraction(record['numerator'], record['denominator'])


nodes = [{'id': f'{leaf}{label}', 'leaf': leaf, 'label': label}
         for leaf in ('U', 'V') for label in ('a', 'b', 'c')]
ids = [n['id'] for n in nodes]


def scenario(allowed):
    return {'id': 'synthetic', 'nodes': {
        uid: {'unit_status': 'defined', 'features': {
            'shape': {'variable': uid, 'allowed': allowed[uid]}}}
        for uid in ids}}


unknown = scenario({uid: [0, 1] for uid in ids})
result = analyze(nodes, ['shape'], [unknown], feature_domains_separable=True)
# Independent direct arithmetic: three positive edges, six negative edges.
direct = []
for bits in product((0, 1), repeat=6):
    u, v = bits[:3], bits[3:]
    same = Fraction(sum(u[i] == v[i] for i in range(3)), 3)
    different = Fraction(sum(u[i] == v[j] for i in range(3) for j in range(3) if i != j), 6)
    direct.append(same - different)
assert rational(result['lower']) == min(direct) == Fraction(-2, 3)
assert rational(result['upper']) == max(direct) == Fraction(2, 3)
assert len(result['pairs']) == 15
assert len([p for p in result['pairs'] if p['cross_leaf']]) == 9
# Marginal edge ranges falsely suggest +/-1. No shared binary assignment realizes it.
assert all(rational(p['lower']) == 0 and rational(p['upper']) == 1 for p in result['pairs'])

zeros = scenario({uid: [0] for uid in ids})
zero_result = analyze(nodes, ['shape'], [zeros], feature_domains_separable=True)
assert rational(zero_result['lower']) == rational(zero_result['upper']) == 0
assert all(rational(p['lower']) == 1 for p in zero_result['pairs'])

# A positive contrast can come wholly from shared absence in an unbalanced layer.
small_nodes = [{'id': 'anchor', 'leaf': 'P', 'label': 'a'},
               {'id': 'same', 'leaf': 'Q', 'label': 'a'},
               {'id': 'different', 'leaf': 'Q', 'label': 'b'}]
absence_only = {'id': 'absence_only', 'nodes': {
    uid: {'unit_status': 'defined', 'features': {
        'shape': {'variable': uid, 'allowed': [bit]}}}
    for uid, bit in [('anchor', 0), ('same', 0), ('different', 1)]}}
absence_result = analyze(small_nodes, ['shape'], [absence_only], feature_domains_separable=True)
decomp = absence_result['scenarios'][0]['features'][0]['lower_witness_decomposition']
assert rational(absence_result['lower']) == 1
assert rational(decomp['weighted_present_present']) == 0
assert rational(decomp['weighted_absent_absent']) == 1

shared = scenario({uid: [0, 1] for uid in ids})
shared['nodes']['Va']['features']['shape']['variable'] = 'Ua'
shared_result = analyze(nodes, ['shape'], [shared], feature_domains_separable=True)
pair = next(p for p in shared_result['pairs'] if p['left'] == 'Ua' and p['right'] == 'Va')
assert rational(pair['lower']) == rational(pair['upper']) == 1

invalid = scenario({uid: [0] for uid in ids})
invalid['nodes']['Va']['features']['shape'] = {'variable': 'Ua', 'allowed': [1]}
try:
    analyze(nodes, ['shape'], [invalid], feature_domains_separable=True)
except ValueError as error:
    assert 'Inconsistent' in str(error)
else:
    raise AssertionError('Contradictory shared-object codes must fail')

undefined = scenario({uid: [0, 1] for uid in ids})
undefined['nodes']['Ua']['unit_status'] = 'undefined'
try:
    analyze(nodes, ['shape'], [undefined], feature_domains_separable=True)
except ValueError as error:
    assert 'Undefined' in str(error)
else:
    raise AssertionError('An undefined object is not ordinary missing data')

print(json.dumps({
    'scope': 'Artificial six-node method check; no Voynich images or feature values.',
    'synthetic_graph': 'Two leaves, three repeated labels, one shared binary feature.',
    'joint_completions_checked': 64,
    'coherent_contrast_bounds': ['-2/3', '2/3'],
    'invalid_pairwise_optimization_would_report': [-1, 1],
    'all_absent_similarity': 1, 'all_absent_label_contrast': 0,
    'unbalanced_layer_positive_contrast_from_shared_absence_only': {
        'contrast': 1, 'present_present': 0, 'absent_absent': 1},
    'same_canonical_object_forces_equal_feature': True,
    'contradictory_shared_codes_rejected': True,
    'undefined_unit_rejected': True,
    'status': 'PASS',
    'limits': 'Internal method check, not independent external replication or manuscript evidence.'
}, ensure_ascii=False, indent=2))
