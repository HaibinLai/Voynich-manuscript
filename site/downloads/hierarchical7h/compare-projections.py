"""Compare full per-entry projections without constructing a cross-entry domain."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path


def compare(observation_path, primary_path, independent_path):
    paths = [observation_path, primary_path, independent_path]
    records = [json.loads(path.read_text()) for path in paths]
    observation, primary, independent = records
    source_hash = sha256(observation_path.read_bytes()).hexdigest()
    assert primary['input_sha256'] == independent['input_sha256'] == source_hash
    assert primary['cross_entry_constraints'] == observation['cross_entry_constraints']
    expected_ids = [entry['id'] for entry in observation['entries']]
    assert [entry['id'] for entry in primary['entries']] == expected_ids
    assert [entry['id'] for entry in independent['entries']] == expected_ids
    rows, total = [], 0
    for original, left, right in zip(observation['entries'], primary['entries'], independent['entries']):
        assert left['domain'] == right['domain']
        if left['domain'] is None:
            rows.append({'id': left['id'], 'domain_size': None, 'unit_defined': False,
                         'complete_domain_matches': True, 'origin_count': 0})
            continue
        lp = {tuple(p['signature']): sorted((o['case_id'], o['extra_index']) for o in p['origins'])
              for p in left['preimages']}
        rp = {tuple(p['signature']): sorted((o['case_id'], o['extra_index']) for o in p['witnesses'])
              for p in right['preimages']}
        assert lp == rp
        left_bases = {row['case_id']: row['base_counts'] for row in left['case_records']}
        for preimage in right['preimages']:
            for witness in preimage['witnesses']:
                assert witness['counted_vector'] == left_bases[witness['case_id']]
                assert witness['duplicate_join_references_removed'] == 0
        origins = sum(len(items) for items in lp.values())
        assert origins == sum(len(case['residual']['vectors']) for case in original['cases'])
        total += origins
        rows.append({'id': left['id'], 'domain_size': len(left['domain']), 'unit_defined': True,
                     'complete_domain_matches': True, 'all_case_extra_origins_match': True,
                     'all_case_base_counts_match': True, 'case_count': len(original['cases']),
                     'origin_count': origins})
    return {'schema': 'per_entry_projection_comparison_v1',
            'checked_utc': datetime.now(timezone.utc).isoformat(),
            'all_match': True, 'entries': rows, 'checked_origin_count': total,
            'cross_entry_constraint_count': len(observation['cross_entry_constraints']),
            'primary_retains_constraints_verbatim': True,
            'joint_scoring_authorized': False, 'pair_or_name_scores_computed': False,
            'scope': 'Complete marginal bookkeeping only; no Cartesian product or feasible common assignment asserted.',
            'limitations': ['Matching projections use the same informed observation and do not validate image interpretation.',
                           'Global interpretation constraints and incomplete mapping cannot be erased by arithmetic agreement.'],
            'inputs': [{'role': role, 'sha256': sha256(path.read_bytes()).hexdigest()}
                       for role, path in zip(['observation', 'primary', 'independent'], paths)],
            'script_sha256': sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ['observation', 'primary', 'independent', 'output']:
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    result = compare(args.observation, args.primary, args.independent)
    with args.output.open('x') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print(json.dumps({'all_match': result['all_match'], 'origins': result['checked_origin_count']}))
