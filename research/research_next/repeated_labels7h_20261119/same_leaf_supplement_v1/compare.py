#!/usr/bin/env python3
import hashlib
import json
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

W = Path(__file__).resolve().parent
paths = [W / 'results_v1.json', W / 'independent/results_v1.json']
p, r = [json.loads(x.read_text()) for x in paths]
q = lambda v: Fraction(v['numerator'], v['denominator'])
mapping = {'f88_different_mean': 'f88_different_S', 'f99_same_mean': 'f99_same_S',
           'f99_different_mean': 'f99_different_S', 'D99': 'f99_D',
           'D99_11': 'f99_D11', 'D99_00': 'f99_D00'}
for a, b in mapping.items():
    for side in ['lower', 'upper']:
        assert q(p['global_bounds'][a][side]['value']) == q(r['global_bounds'][b][side]['value'])
assert len(p['scenarios']) == len(r['scenarios']) == 16
for ps, rs in zip(p['scenarios'], r['scenarios']):
    assert ps['id'] == rs['id'] and ps['assignment'] == rs['assignment']
    for a, b in mapping.items():
        for side in ['lower', 'upper']:
            assert q(ps['metrics'][a][side]) == q(rs['bounds'][b][side]['value'])
            for feature in ['G1', 'G2', 'G3', 'G4']:
                assert q(ps['feature_metrics'][feature][a][side]['value']) == q(rs['features'][feature]['extrema'][b][side]['value'])
assert {(x['left'], x['right']) for x in p['all_nine_same_leaf_pairs']} == {(x['left'], x['right']) for x in r['all_nine_pairs']}
result = {'status': 'EXACT_FRACTIONS_MATCH', 'checked_utc': datetime.now(timezone.utc).isoformat(),
          'checks': ['All six global objective ranges', 'All16 candidate ranges for each objective',
                     'All four feature ranges for every candidate and objective', 'All nine same-leaf pair identities'],
          'scope': 'Post-primary descriptive supplement. Numerical agreement is not additional image evidence.',
          'inputs': [{'path': str(x.relative_to(W)), 'sha256': hashlib.sha256(x.read_bytes()).hexdigest()} for x in paths]}
(W / 'replay_comparison_v1.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(result['status'])
