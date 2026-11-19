#!/usr/bin/env python3
"""Compare exact fractions from the two separately written implementations."""
import hashlib
import json
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

W = Path(__file__).resolve().parent.parent


def q(x):
    return Fraction(x['numerator'], x['denominator'])


def main():
    paths = [W / 'primary_results_v1/primary_bounds_v1.json',
             W / 'numeric_replay/actual_v1/replay_results_v1.json',
             W / 'primary_results_v1/canonical_domains_v1.json',
             W / 'numeric_replay/actual_v1/domains_v1.json']
    primary, replay, pdomains, rdomains = [json.loads(p.read_text()) for p in paths]
    assert pdomains['groups'] == rdomains['groups']
    assert primary['observation_source']['sha256'] == replay['observation_sha256']
    for side in ['lower', 'upper']:
        assert q(primary[side]) == q(replay['global_bounds']['T'][side]['value'])
    assert len(primary['scenarios']) == len(replay['scenarios']) == 16
    for ps, rs in zip(primary['scenarios'], replay['scenarios']):
        assert ps['id'] == rs['id']
        for side in ['lower', 'upper']:
            assert q(ps[side]) == q(rs['bounds']['T'][side]['value'])
        for f in ps['features']:
            rf = rs['features'][f['feature']]
            assert f['legal_assignments'] == rf['enumerated_assignments']
            for side in ['lower', 'upper']:
                assert q(f[side]) == q(rf['extrema']['T'][side]['value'])
        assert len(rs['all_pairs']) == 36
    for p in primary['pairs']:
        rp = [next(x for x in s['all_pairs'] if (x['left'], x['right']) == (p['left'], p['right']))
              for s in replay['scenarios']]
        assert q(p['lower']) == min(q(x['similarity_lower']) for x in rp)
        assert q(p['upper']) == max(q(x['similarity_upper']) for x in rp)
        assert all(x['same_label'] == p['same_label'] and x['cross_leaf'] == p['cross_leaf'] for x in rp)
    result = {'schema': 'primary_replay_comparison_v1',
              'checked_utc': datetime.now(timezone.utc).isoformat(),
              'status': 'EXACT_FRACTIONS_MATCH',
              'checks': ['48 independently projected canonical domains match',
                         'Global T lower and upper match',
                         'All16 candidate T intervals match',
                         'All64 feature T intervals and enumeration counts match',
                         'All36 pair envelope intervals and metadata match'],
              'not_checked_by_this_script': 'Visual truth and extra independently optimized T11/T00/layer outputs; '
                                            'those are in source records and the independent endpoint audit.',
              'interpretation': 'Separate code, common frozen observations; not an independent historical replication.',
              'inputs': [{'path': str(p.relative_to(W)),
                          'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths],
              'comparison_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (W / 'primary_results_v1/replay_comparison_v1.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(result['status'])


if __name__ == '__main__':
    main()
