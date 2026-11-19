#!/usr/bin/env python3
"""Strictly project a frozen observation matrix, then compute descriptive bounds.

This checks structure and provenance, not the truth of visual feature judgments.
The observation SHA must be explicitly supplied after the matrix is frozen.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from binary_bounds import analyze

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
ROOT = HERE.parents[3]


def require(test, message):
    if not test:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project(observation, approval, codebook):
    expected = {g['canonical_group_id']: g for g in approval['canonical_group_index']}
    features = [f['id'] for f in codebook['features']]
    rows = observation['groups']
    require(len(rows) == len(expected) == 12, 'All twelve candidate groups are required')
    require(len({r['canonical_group_id'] for r in rows}) == len(rows), 'Duplicate canonical group')
    require({r['canonical_group_id'] for r in rows} == set(expected), 'Canonical roster changed')
    require(features == ['G1', 'G2', 'G3', 'G4'], 'Frozen feature order changed')
    expected_loci = {g: set() for g in expected}
    for scenario in approval['global_candidate_scenarios']:
        for locus, group in scenario['assignment'].items():
            expected_loci[group].add(locus)
    groups = {}
    coverage = []
    for row in rows:
        uid = row['canonical_group_id']
        require(row['image_id'] == expected[uid]['image_id'], f'Image changed: {uid}')
        require(row['image_sha256'] == expected[uid]['image_sha256'], f'Image bytes changed: {uid}')
        require(set(row['referencing_loci']) == expected_loci[uid], f'Locus mapping changed: {uid}')
        require(set(row['features']) == set(features), f'Feature opportunities missing: {uid}')
        groups[uid] = {}
        for feature in features:
            record = row['features'][feature]
            value = record['value']
            require(value is None or (type(value) is int and value in (0, 1)),
                    f'Invalid value: {uid}/{feature}')
            allowed = [0, 1] if value is None else [value]
            require(isinstance(record['allowed'], list) and
                    all(type(v) is int for v in record['allowed']),
                    f'Non-integer domain: {uid}/{feature}')
            require(record['allowed'] == allowed, f'Value/domain inconsistency: {uid}/{feature}')
            require(bool(record['reason']), f'Missing reason: {uid}/{feature}')
            require(bool(record['view_ids']), f'Missing view reference: {uid}/{feature}')
            require(bool(record['evidence_regions_xywh']), f'Missing local evidence: {uid}/{feature}')
            if value == 0:
                require(bool(record['negative_coverage']), f'Zero without coverage: {uid}/{feature}')
            if value == 1 and feature in ('G1', 'G3'):
                require(bool(record['measurements']), f'Positive ratio/count without witnesses: {uid}/{feature}')
            groups[uid][feature] = allowed
            coverage.append({'group': uid, 'feature': feature, 'value': value,
                             'reason': record['reason'], 'referencing_loci': row['referencing_loci']})
    require(len(coverage) == 48, 'Fixed group-feature opportunities changed')
    return {'schema': 'canonical_allowed_domains_v1', 'frozen': True, 'groups': groups}, coverage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observation', required=True, type=Path)
    parser.add_argument('--expected-observation-sha', required=True)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    observation_path = args.observation.resolve()
    relative = observation_path.relative_to(ROOT)
    require(sha(observation_path) == args.expected_observation_sha, 'Frozen observation SHA mismatch')
    approval_path = WORK / 'measurement_approval_v1.json'
    codebook_path = WORK / 'feature_codebook_v1.json'
    approval = json.loads(approval_path.read_text())
    codebook = json.loads(codebook_path.read_text())
    for source in approval['source_hashes']:
        require(sha(ROOT / source['path']) == source['sha256'], f'Approved source changed: {source["path"]}')
    observation = json.loads(observation_path.read_text())
    domains, coverage = project(observation, approval, codebook)
    domains['observation_source'] = {'path': str(relative), 'sha256': sha(observation_path)}
    features = [f['id'] for f in codebook['features']]
    scenarios = []
    for candidate in approval['global_candidate_scenarios']:
        scenarios.append({'id': candidate['id'], 'nodes': {
            uid: {'unit_status': 'defined', 'features': {
                f: {'variable': group, 'allowed': domains['groups'][group][f]} for f in features}}
            for uid, group in candidate['assignment'].items()}})
    result = analyze(codebook['nodes'], features, scenarios, feature_domains_separable=True)
    result['bound_type'] = 'Conservative outer bounds in the stated binary-domain relaxation, not sharp geometry bounds.'
    result['observation_source'] = domains['observation_source']
    result['coverage'] = {'canonical_group_feature_opportunities': 48,
                          'node_feature_opportunities_per_scenario': 36,
                          'canonical_counts': dict(Counter('unknown' if r['value'] is None else str(r['value']) for r in coverage)),
                          'by_feature': {f: dict(Counter('unknown' if r['value'] is None else str(r['value']) for r in coverage if r['feature'] == f)) for f in features},
                          'records': coverage}
    result['visual_validation'] = 'This program verifies declared structure, not image evidence, plant identity or label meanings.'
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {'canonical_domains_v1.json': domains, 'primary_bounds_v1.json': result}
    for name, data in outputs.items():
        (args.output_dir / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    receipt = {'observation': domains['observation_source'],
               'inputs': [{'path': str(p.relative_to(ROOT)), 'sha256': sha(p)} for p in
                          [Path(__file__), HERE / 'binary_bounds.py', approval_path, codebook_path]],
               'outputs': [{'path': str((args.output_dir / name).resolve().relative_to(ROOT)),
                            'sha256': sha(args.output_dir / name)} for name in outputs],
               'scope': 'Primary numerical calculation only; independent replay and source-judgment review are separate.'}
    (args.output_dir / 'run_receipt_v1.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'bounds': [result['lower'], result['upper']],
                      'coverage': result['coverage']['canonical_counts'],
                      'scenarios': len(scenarios), 'pairs': len(result['pairs'])}, ensure_ascii=False))


if __name__ == '__main__':
    main()
