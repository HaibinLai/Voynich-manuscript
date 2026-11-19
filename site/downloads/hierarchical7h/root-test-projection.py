"""Synthetic checks of shared witnesses, joint alternatives, and saturation."""
from copy import deepcopy
from project import project_entry

entry = {'id': 'toy', 'unit_defined': True,
         'units': {'u': {'allowed_classes': ['Q0', 'Q2']}, 'alias': {'allowed_classes': ['Q0']}},
         'joins': {'j': {}}, 'at_most_one': [{'ids': ['u', 'alias'], 'reason': 'same trace'}],
         'cases': [
             {'id': 'a', 'unit_classes': {'u': 'Q0'}, 'join_ids': [],
              'residual': {'vectors': [[0, 0, 0, 0], [2, 0, 0, 0]], 'coverage_refs': ['toy'], 'disjoint_from_counted_witnesses': True}},
             {'id': 'b', 'unit_classes': {'u': 'Q2'}, 'join_ids': ['j'],
              'residual': {'vectors': [[0, 0, 0, 0]], 'coverage_refs': ['toy'], 'disjoint_from_counted_witnesses': True}}
         ]}
r = project_entry(entry)
assert r['domain'] == [[0, 0, 1, 1], [1, 0, 0, 0], [2, 0, 0, 0]]
assert [1, 0, 1, 1] not in r['domain']  # No recombination of mutually exclusive features.
assert r['constant_coordinates'] == {'Q1': 0}
bad = deepcopy(entry)
bad['cases'][0]['unit_classes']['alias'] = 'Q0'
try:
    project_entry(bad)
except ValueError:
    pass
else:
    raise AssertionError('Alias double counting was accepted')
bad = deepcopy(entry)
bad['cases'][0]['residual']['disjoint_from_counted_witnesses'] = False
try:
    project_entry(bad)
except ValueError:
    pass
else:
    raise AssertionError('Undeclared residual overlap was accepted')
undefined = project_entry({'id': 'not-defined', 'unit_defined': False})
assert undefined['domain'] is None
print('Synthetic projection preserves joint alternatives, IDs, saturation and undefined units; no manuscript values used.')
