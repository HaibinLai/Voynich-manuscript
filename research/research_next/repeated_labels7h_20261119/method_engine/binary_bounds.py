"""Exact descriptive bounds for shared binary features; no image inference.

This is a generic method prototype. It is not authorization to score the fixed
manuscript sample. Every candidate scenario and allowed state needs a separate
measurement contract. It computes feasible-set bounds, never p-values.
"""
from collections import defaultdict
from fractions import Fraction
from itertools import combinations, product


def topology(nodes):
    """Nodes have id, leaf, label. Preserve all pairs, including same-leaf ones."""
    ids = [n['id'] for n in nodes]
    if len(set(ids)) != len(ids) or len(nodes) < 2:
        raise ValueError('Expected unique node ids and at least two nodes')
    pairs = []
    strata = defaultdict(list)
    for a, b in combinations(nodes, 2):
        p = {'left': a['id'], 'right': b['id'],
             'leaf_pair': tuple(sorted((a['leaf'], b['leaf']))),
             'cross_leaf': a['leaf'] != b['leaf'],
             'same_label': a['label'] == b['label']}
        pairs.append(p)
        if p['cross_leaf']:
            strata[p['leaf_pair']].append(p)
    mixed = {key: ps for key, ps in strata.items()
             if {p['same_label'] for p in ps} == {True, False}}
    if not mixed:
        raise ValueError('No leaf-pair stratum contains both label relations')
    weights = {}
    for ps in mixed.values():
        counts = {same: sum(p['same_label'] == same for p in ps)
                  for same in (True, False)}
        for p in ps:
            weights[(p['left'], p['right'])] = Fraction(
                1 if p['same_label'] else -1,
                len(mixed) * counts[p['same_label']])
    assert sum(weights.values()) == 0
    return pairs, mixed, weights


def legal_assignments(ids, feature, scenario):
    """A variable names one shared object-feature value across all its pairs.

    Same variable at two nodes forces equal values. Intersect their supported
    value sets. Candidates which only overlap in some ink must not be assigned
    one variable unless the measurement contract justifies equal feature values.
    """
    members = {}
    domains = {}
    for uid in ids:
        node = scenario['nodes'][uid]
        if node.get('unit_status') != 'defined':
            raise ValueError(f'Undefined measurement unit: {uid}')
        spec = node['features'][feature]
        var = spec['variable']
        vals = set(spec['allowed'])
        if not vals or not vals <= {0, 1} or any(type(v) is not int for v in spec['allowed']):
            raise ValueError(f'Invalid binary allowed set: {uid}/{feature}')
        if not isinstance(var, str) or not var:
            raise ValueError('Shared variable id must be a nonempty string')
        members[uid] = var
        domains[var] = domains.get(var, {0, 1}) & vals
    if any(not vals for vals in domains.values()):
        raise ValueError('Inconsistent value sets for a shared variable')
    variables = sorted(domains)
    # Deliberately bounded. Larger data needs a different qualified solver.
    if len(variables) > 12:
        raise ValueError('Prototype supports at most 12 variables per feature')
    for bits in product(*(sorted(domains[v]) for v in variables)):
        values = dict(zip(variables, bits))
        yield {uid: values[members[uid]] for uid in ids}


def fraction_record(value):
    return {'numerator': value.numerator, 'denominator': value.denominator,
            'decimal': float(value)}


def decomposition(values, weights):
    present = sum((w for (left, right), w in weights.items()
                   if values[left] == values[right] == 1), Fraction(0))
    absent = sum((w for (left, right), w in weights.items()
                  if values[left] == values[right] == 0), Fraction(0))
    return {'weighted_present_present': fraction_record(present),
            'weighted_absent_absent': fraction_record(absent),
            'contrast': fraction_record(present + absent)}


def analyze(nodes, features, scenarios, *, feature_domains_separable=False):
    """Bound the equally weighted, mixed-leaf-stratum similarity contrast.

    The explicit flag means the caller has declared the per-feature feasible
    sets independent within each fixed global candidate scenario. These bounds
    describe that relaxed set; they are not biological feasibility claims.
    """
    if not feature_domains_separable:
        raise ValueError('Must explicitly declare feature-domain separability')
    if not features or len(set(features)) != len(features) or not scenarios:
        raise ValueError('Need distinct features and at least one full scenario')
    ids = [n['id'] for n in nodes]
    pairs, mixed, weights = topology(nodes)
    scenario_records = []
    pair_envelope = {(p['left'], p['right']): [] for p in pairs}
    for scenario in scenarios:
        if set(scenario['nodes']) != set(ids):
            raise ValueError('Each global scenario must retain every node')
        for node in scenario['nodes'].values():
            if set(node['features']) != set(features):
                raise ValueError('Each node must retain every feature opportunity')
        feature_records = []
        pair_sums = {key: [0, 0] for key in pair_envelope}
        lower = upper = Fraction(0)
        for feature in features:
            values = list(legal_assignments(ids, feature, scenario))
            contrasts = [sum(w * (a[left] == a[right])
                             for (left, right), w in weights.items()) for a in values]
            lo, hi = min(contrasts), max(contrasts)
            lower += lo / len(features)
            upper += hi / len(features)
            feature_records.append({
                'feature': feature, 'legal_assignments': len(values),
                'lower': fraction_record(lo), 'upper': fraction_record(hi),
                'lower_witness': values[contrasts.index(lo)],
                'upper_witness': values[contrasts.index(hi)],
                'lower_witness_decomposition': decomposition(values[contrasts.index(lo)], weights),
                'upper_witness_decomposition': decomposition(values[contrasts.index(hi)], weights)})
            for key in pair_sums:
                left, right = key
                equality = [int(a[left] == a[right]) for a in values]
                pair_sums[key][0] += min(equality)
                pair_sums[key][1] += max(equality)
        scenario_records.append({'id': scenario['id'],
                                 'lower': fraction_record(lower),
                                 'upper': fraction_record(upper),
                                 'features': feature_records})
        for key, (lo, hi) in pair_sums.items():
            pair_envelope[key].append((Fraction(lo, len(features)), Fraction(hi, len(features))))
    lower = min(Fraction(s['lower']['numerator'], s['lower']['denominator']) for s in scenario_records)
    upper = max(Fraction(s['upper']['numerator'], s['upper']['denominator']) for s in scenario_records)
    pair_records = []
    for p in pairs:
        key = (p['left'], p['right'])
        pair_records.append({**p, 'contrast_weight': fraction_record(weights.get(key, Fraction(0))),
                             'lower': fraction_record(min(v[0] for v in pair_envelope[key])),
                             'upper': fraction_record(max(v[1] for v in pair_envelope[key]))})
    return {'schema': 'shared_binary_feature_bounds_prototype_v1',
            'feature_count': len(features), 'node_count': len(nodes),
            'feature_opportunities': len(features) * len(nodes),
            'mixed_leaf_strata': [list(k) for k in mixed],
            'lower': fraction_record(lower), 'upper': fraction_record(upper),
            'scenarios': scenario_records, 'pairs': pair_records,
            'limits': ['Descriptive feasible-set bounds, not confidence intervals or a null test.',
                       'Each scenario is a joint global candidate assignment.',
                       'Unknown values are shared across all incident pairs.',
                       'Feature-domain separability is an explicit relaxation, not biological truth.',
                       'Different pairs may attain their displayed extrema in different assignments.',
                       'The contrast bounds are optimized globally; never average marginal pair extrema.']}
