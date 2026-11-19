#!/usr/bin/env python3
import hashlib
import json
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

W = Path(__file__).resolve().parent
q = lambda r: Fraction(r['numerator'], r['denominator'])
files = [W / 'results_v1.json', W / 'independent_v1/results_v1.json']
p, r = [json.loads(f.read_text()) for f in files]
for metric in ['C', 'C11', 'C00']:
    for side in ['lower', 'upper']:
        assert q(p['bounds'][metric][side]) == q(r['bounds'][metric][side]['value'])
for feature in p['features']:
    for metric in ['C', 'C11', 'C00']:
        for side in ['lower', 'upper']:
            assert q(feature['bounds'][metric][side]) == q(r['features'][feature['feature']][metric][side]['value'])
assert len(p['pairs']) == len(r['all_six_pairs']) == 6
for pair in p['pairs']:
    other = next(x for x in r['all_six_pairs'] if (x['left'], x['right']) == (pair['left'], pair['right']))
    for side in ['lower', 'upper']:
        assert q(pair[side]) == q(other['similarity_' + side])
    assert pair['same_name'] == other['same_name']
    assert pair['cross_manuscript'] == other['cross_manuscript']
result = {'status': 'EXACT_FRACTIONS_MATCH',
          'checked_utc': datetime.now(timezone.utc).isoformat(),
          'checks': ['All three total contrasts C/C11/C00 lower and upper',
                     'All four features times three contrasts lower and upper',
                     'All six pair intervals and relation metadata'],
          'scope': 'Separate numerical implementations of one frozen observation, not independent image evidence.',
          'inputs': [{'path': str(f.relative_to(W)), 'sha256': hashlib.sha256(f.read_bytes()).hexdigest()} for f in files]}
(W / 'replay_comparison_v1.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(result['status'])
