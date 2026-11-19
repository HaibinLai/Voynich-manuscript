#!/usr/bin/env python3
"""Post-result diagnostic: resolve each uncertainty in both possible ways.

This is planning information, not a new observation or a new hypothesis test.
All 21 unknown cells and all four candidate ambiguities are evaluated, with
all nine loci and the fixed four-feature statistic retained. The original
observation is never changed. Ranking uses worst-outcome interval width,
not a favorable sign or a selected completion.
"""
import copy
import hashlib
import json
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

from binary_bounds import analyze, fraction_record

W = Path(__file__).resolve().parent.parent
FEATURES = ['G1', 'G2', 'G3', 'G4']


def frac(record):
    return Fraction(record['numerator'], record['denominator'])


def bounds(groups, candidates, nodes):
    scenarios = [{'id': c['id'], 'nodes': {
        locus: {'unit_status': 'defined', 'features': {
            f: {'variable': group, 'allowed': groups[group][f]} for f in FEATURES}}
        for locus, group in c['assignment'].items()}} for c in candidates]
    result = analyze(nodes, FEATURES, scenarios, feature_domains_separable=True)
    lo, hi = frac(result['lower']), frac(result['upper'])
    return {'lower': result['lower'], 'upper': result['upper'],
            'width': fraction_record(hi - lo), 'contains_zero': lo <= 0 <= hi,
            'candidate_count': len(candidates)}


def main():
    source = W / 'primary_results_v1/canonical_domains_v1.json'
    domains = json.loads(source.read_text())['groups']
    approval = json.loads((W / 'measurement_approval_v1.json').read_text())
    nodes = json.loads((W / 'feature_codebook_v1.json').read_text())['nodes']
    candidates = approval['global_candidate_scenarios']
    base = bounds(domains, candidates, nodes)
    records = []
    for group, features in domains.items():
        for feature, allowed in features.items():
            if allowed != [0, 1]:
                continue
            outcomes = []
            for value in [0, 1]:
                proposed = copy.deepcopy(domains)
                proposed[group][feature] = [value]
                outcomes.append({'assumed_value': value,
                                 **bounds(proposed, candidates, nodes)})
            records.append({'kind': 'unknown_feature', 'group': group,
                            'feature': feature, 'outcomes': outcomes})
    feature_count = len(records)
    assert feature_count == 21
    for node in nodes:
        locus = node['id']
        choices = sorted({c['assignment'][locus] for c in candidates})
        if len(choices) <= 1:
            continue
        outcomes = []
        for group in choices:
            retained = [c for c in candidates if c['assignment'][locus] == group]
            outcomes.append({'assumed_group': group,
                             **bounds(domains, retained, nodes)})
        records.append({'kind': 'candidate_assignment', 'locus': locus,
                        'outcomes': outcomes})
    assert len(records) == 25
    for r in records:
        widths = [frac(x['width']) for x in r['outcomes']]
        r['worst_outcome_width'] = fraction_record(max(widths))
        r['best_outcome_width'] = fraction_record(min(widths))
        r['guaranteed_width_reduction'] = fraction_record(frac(base['width']) - max(widths))
        r['all_outcomes_still_contain_zero'] = all(x['contains_zero'] for x in r['outcomes'])
    records.sort(key=lambda r: (frac(r['worst_outcome_width']), r['kind'],
                               r.get('group', r.get('locus', '')), r.get('feature', '')))
    output = {
        'schema': 'post_result_uncertainty_priority_v1',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'design': __doc__, 'baseline': base, 'records': records,
        'all_single_resolution_outcomes_contain_zero': all(
            r['all_outcomes_still_contain_zero'] for r in records),
        'interpretation': 'Counterfactual algebraic outer bounds only. No new visual readings, '
                          'no favorable completion selected, no probability assigned to outcomes. '
                          'Resolving a feature here means fully and correctly resolving that cell; '
                          'the current evidence does not supply that answer.',
        'inputs': [{'path': str(p.relative_to(W)),
                    'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in
                   [source, W / 'measurement_approval_v1.json', W / 'feature_codebook_v1.json',
                    Path(__file__), W / 'method_engine/binary_bounds.py']]}
    path = W / 'primary_results_v1/uncertainty_priority_v1.json'
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'tested_questions': len(records),
                      'all_single_resolution_outcomes_contain_zero': output['all_single_resolution_outcomes_contain_zero'],
                      'first_three': records[:3]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
