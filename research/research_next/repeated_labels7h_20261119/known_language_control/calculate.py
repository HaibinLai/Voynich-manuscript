#!/usr/bin/env python3
"""Exact four-entry control calculation; manuscript, not leaf-pair, blocking.

Input is a separately verified frozen projection: groups K01..K04, G1..G4,
allowed binary domains. This does not transcribe names or judge images.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from fractions import Fraction
from itertools import combinations, product
from pathlib import Path

IDS = ['K01', 'K02', 'K03', 'K04']
FEATURES = ['G1', 'G2', 'G3', 'G4']
PAIRS = list(combinations(IDS, 2))
WEIGHTS = {('K01', 'K02'): Fraction(1, 2),
           ('K03', 'K04'): Fraction(1, 2),
           ('K01', 'K04'): Fraction(-1, 2),
           ('K02', 'K03'): Fraction(-1, 2)}


def rec(x):
    x = Fraction(x)
    return {'numerator': x.numerator, 'denominator': x.denominator, 'decimal': float(x)}


def calculate(groups):
    if set(groups) != set(IDS):
        raise ValueError('Exactly K01 through K04 required')
    for row in groups.values():
        if set(row) != set(FEATURES):
            raise ValueError('All four features required')
        for domain in row.values():
            if (not isinstance(domain, list) or not domain or
                    any(type(v) is not int or v not in (0, 1) for v in domain) or
                    domain != sorted(set(domain))):
                raise ValueError('Expected sorted nonempty binary integer domain')
    feature_rows = []
    totals = {metric: [Fraction(), Fraction()] for metric in ['C', 'C11', 'C00']}
    pair_totals = {pair: [Fraction(), Fraction()] for pair in PAIRS}
    for feature in FEATURES:
        states = []
        for bits in product(*(groups[x][feature] for x in IDS)):
            values = dict(zip(IDS, bits))
            c11 = sum((weight for (a, b), weight in WEIGHTS.items()
                       if values[a] == values[b] == 1), Fraction())
            c00 = sum((weight for (a, b), weight in WEIGHTS.items()
                       if values[a] == values[b] == 0), Fraction())
            states.append({'values': values, 'C': c11 + c00, 'C11': c11, 'C00': c00})
        row = {'feature': feature, 'legal_states': len(states), 'bounds': {}}
        for metric in totals:
            lo = min(states, key=lambda s: s[metric])
            hi = max(states, key=lambda s: s[metric])
            row['bounds'][metric] = {'lower': rec(lo[metric]), 'upper': rec(hi[metric]),
                                    'lower_witness': lo['values'], 'upper_witness': hi['values']}
            if metric == 'C':
                row['C_endpoint_decomposition'] = {
                    end: {m: rec(s[m]) for m in ['C', 'C11', 'C00']}
                    for end, s in [('lower', lo), ('upper', hi)]}
            totals[metric][0] += lo[metric] / 4
            totals[metric][1] += hi[metric] / 4
        for pair in PAIRS:
            equal = [int(s['values'][pair[0]] == s['values'][pair[1]]) for s in states]
            pair_totals[pair][0] += Fraction(min(equal), 4)
            pair_totals[pair][1] += Fraction(max(equal), 4)
        feature_rows.append(row)
    return {
        'schema': 'four_named_entry_control_result_v1',
        'blocking': 'One manuscript-pair layer, not physical-leaf-pair layers; do not pool with main study.',
        'bounds': {m: {'lower': rec(lo), 'upper': rec(hi)} for m, (lo, hi) in totals.items()},
        'features': feature_rows,
        'pairs': [{'left': a, 'right': b, 'cross_manuscript': (a, b) in WEIGHTS,
                   'same_name': WEIGHTS.get((a, b), 0) > 0,
                   'weight': rec(WEIGHTS.get((a, b), 0)),
                   'lower': rec(lo), 'upper': rec(hi)}
                  for (a, b), (lo, hi) in pair_totals.items()],
        'limits': ['These are conservative algebraic outer bounds, not confidence intervals.',
                   'Separate C11 and C00 extrema cannot be added; use C endpoint decompositions.',
                   'Unknown entry-feature values are shared across every pair.',
                   'Four selected named historical entries do not estimate general sensitivity or specificity.',
                   'Names and illustration units are conditional informed readings; shared copying tradition remains.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domains', type=Path)
    parser.add_argument('--expected-sha')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--synthetic-check', action='store_true')
    args = parser.parse_args()
    if args.synthetic_check:
        common = {x: {f: [1] for f in FEATURES} for x in IDS}
        split = {x: {f: [int(x in ['K01', 'K02'])] for f in FEATURES} for x in IDS}
        first, second = calculate(common), calculate(split)
        assert first['bounds']['C']['lower']['decimal'] == first['bounds']['C']['upper']['decimal'] == 0
        assert second['bounds']['C']['lower']['decimal'] == second['bounds']['C']['upper']['decimal'] == 1
        result = {'synthetic_only': True, 'common_presence_C': 0, 'name_split_C': 1,
                  'interpretation': 'Artificial code checks, not historical observations.'}
    else:
        if not args.domains or not args.expected_sha:
            raise ValueError('Explicit frozen input and SHA required')
        data = args.domains.read_bytes()
        if hashlib.sha256(data).hexdigest() != args.expected_sha:
            raise ValueError('Input hash mismatch')
        domains = json.loads(data)
        if domains.get('frozen') is not True:
            raise ValueError('Input projection must be frozen')
        result = calculate(domains['groups'])
        result['input_sha256'] = args.expected_sha
        result['observation_source'] = domains['observation_source']
    result['created_utc'] = datetime.now(timezone.utc).isoformat()
    result['implementation_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result.get('bounds', result), ensure_ascii=False))


if __name__ == '__main__':
    main()
