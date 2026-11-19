#!/usr/bin/env python3
"""Post-primary within-leaf description and explicit per-node missingness."""
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction as Q
from pathlib import Path

HERE = Path(__file__).resolve().parent
W = HERE.parent
sys.path.insert(0, str(W / 'method_engine'))
from binary_bounds import legal_assignments, fraction_record as rec


def q(x):
    return Q(x['numerator'], x['denominator'])


def main():
    contract = json.loads((HERE / 'contract_v1.json').read_text())
    for r in contract['inputs']:
        assert hashlib.sha256((W / r['path']).read_bytes()).hexdigest() == r['sha256']
    book = json.loads((W / 'feature_codebook_v1.json').read_text())
    approval = json.loads((W / 'measurement_approval_v1.json').read_text())
    domains = json.loads((W / 'primary_results_v1/canonical_domains_v1.json').read_text())['groups']
    ids = [n['id'] for n in book['nodes']]
    features = ['G1', 'G2', 'G3', 'G4']
    pairs = [p for p in book['all_pairs'] if not p['cross_leaf']]
    classes = {}
    for leaf in ['f101', 'f88', 'f89', 'f99']:
        for relation, flag in [('same', True), ('different', False)]:
            classes[(leaf, relation)] = [p for p in pairs if p['leaf_pair'][0] == leaf and p['same_label'] == flag]
    assert len(pairs) == 9
    assert [len(classes[(l, r)]) for l in ['f101', 'f88', 'f89', 'f99'] for r in ['same', 'different']] == [0,0,0,3,0,0,1,5]
    objectives = {}
    for (leaf, relation), ps in classes.items():
        if ps:
            objectives[leaf + '_' + relation + '_mean'] = ([(p, Q(1, len(ps))) for p in ps], 'equal')
    contrast_weights = [(p, Q(1)) for p in classes[('f99', 'same')]] + [(p, Q(-1,5)) for p in classes[('f99', 'different')]]
    for key, indicator in [('D99', 'equal'), ('D99_11', 'present'), ('D99_00', 'absent')]:
        objectives[key] = (contrast_weights, indicator)

    def score(values, objective):
        weights, mode = objectives[objective]
        return sum((weight for p, weight in weights
                    if values[p['left']] == values[p['right']] and
                    (mode == 'equal' or values[p['left']] == (1 if mode == 'present' else 0))), Q())

    scenarios = []
    for candidate in approval['global_candidate_scenarios']:
        assignment = candidate['assignment']
        definition = {'nodes': {uid: {'unit_status': 'defined', 'features': {
            f: {'variable': gid, 'allowed': domains[gid][f]} for f in features}}
            for uid, gid in assignment.items()}}
        per_feature = {}
        metrics = {m: {'lower': Q(), 'upper': Q()} for m in objectives}
        for feature in features:
            values = list(legal_assignments(ids, feature, definition))
            per_feature[feature] = {}
            for objective in objectives:
                scores = [(score(v, objective), v) for v in values]
                entry = {}
                for side, chooser in [('lower', min), ('upper', max)]:
                    value, witness = chooser(scores, key=lambda x: x[0])
                    entry[side] = {'value': rec(value), 'node_witness': witness}
                    if objective == 'D99':
                        entry[side]['decomposition'] = {m: rec(score(witness, m)) for m in ['D99', 'D99_11', 'D99_00']}
                    metrics[objective][side] += value / 4
                per_feature[feature][objective] = entry
        counts = []
        for uid, gid in assignment.items():
            vals = {f: domains[gid][f][0] if len(domains[gid][f]) == 1 else None for f in features}
            counts.append({'locus': uid, 'canonical_group': gid, 'values': vals,
                           'counts': {key: sum(('unknown' if v is None else str(v)) == key for v in vals.values())
                                      for key in ['1', '0', 'unknown']}})
        unique = sorted(set(assignment.values()))
        scenarios.append({'id': candidate['id'], 'assignment': assignment,
                          'metrics': {m: {s: rec(v) for s, v in b.items()} for m,b in metrics.items()},
                          'feature_metrics': per_feature, 'per_node_missingness': counts,
                          'unique_selected_canonical_groups': unique,
                          'unique_group_count': len(unique),
                          'unknown_canonical_variables_by_feature': {
                              f: sum(len(domains[g][f]) == 2 for g in unique) for f in features}})
    envelope = {}
    for objective in objectives:
        envelope[objective] = {}
        for side, chooser in [('lower', min), ('upper', max)]:
            s = chooser(scenarios, key=lambda x: q(x['metrics'][objective][side]))
            entry = {'value': s['metrics'][objective][side], 'scenario_id': s['id']}
            if objective == 'D99':
                entry['same_witness_decomposition'] = {
                    m: rec(sum((q(s['feature_metrics'][f]['D99'][side]['decomposition'][m]) / 4 for f in features), Q()))
                    for m in ['D99', 'D99_11', 'D99_00']}
            envelope[objective][side] = entry
    result = {'schema': 'within_leaf_supplement_and_missingness_v1',
              'completed_utc': datetime.now(timezone.utc).isoformat(),
              'scope': contract['scope'], 'strata': contract['strata'], 'all_nine_same_leaf_pairs': pairs,
              'global_bounds': envelope, 'scenarios': scenarios,
              'interpretation': 'Only f99 has both same and different labels. Other leaf contrasts are undefined, not zero. '
                                'Conservative binary-domain outer bounds; not p-values or confidence intervals. '
                                'This supplementary statistic does not replace or get pooled with the primary T.',
              'contract_sha256': hashlib.sha256((HERE / 'contract_v1.json').read_bytes()).hexdigest(),
              'implementation_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (HERE / 'results_v1.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(envelope, ensure_ascii=False))


if __name__ == '__main__':
    main()
