"""Project finite, joint local interpretation cases into capped signatures.

This validates bookkeeping, not the visual truth or completeness of a case list.
Residual vectors are explicit conservative additions, never hidden anatomy.
"""
import argparse
import hashlib
import json
from pathlib import Path

FEATURES = ('Q0', 'Q1', 'Q2', 'QJ')


def vector(value):
    if not isinstance(value, list) or len(value) != 4 or any(type(x) is not int or x not in (0, 1, 2) for x in value):
        raise ValueError('Residual vectors must be four ternary integers')
    return tuple(value)


def project_entry(entry):
    if entry.get('unit_defined') is not True:
        return {'id': entry['id'], 'status': 'UNIT_UNDEFINED', 'domain': None}
    units = entry['units']
    joins = entry['joins']
    if set(units) & set(joins):
        raise ValueError('Unit and join IDs must be disjoint')
    if not entry['cases']:
        raise ValueError('Empty interpretation set is an input contradiction')
    seen_cases, provenance, case_records = set(), {}, []
    for case in entry['cases']:
        case_id = case['id']
        if case_id in seen_cases:
            raise ValueError('Duplicate case ID')
        seen_cases.add(case_id)
        selected_units = case['unit_classes']
        selected_joins = case['join_ids']
        if len(set(selected_joins)) != len(selected_joins):
            raise ValueError('Duplicate join in one interpretation')
        if not set(selected_units) <= set(units) or not set(selected_joins) <= set(joins):
            raise ValueError('Unknown witness ID')
        for uid, feature in selected_units.items():
            if feature not in FEATURES[:3] or feature not in units[uid]['allowed_classes']:
                raise ValueError('Unsupported unit class: ' + uid)
        active = set(selected_units) | set(selected_joins)
        for group in entry.get('at_most_one', []):
            if len(set(group['ids']) & active) > 1:
                raise ValueError('Alias/exclusion/ownership conflict: ' + group['reason'])
        base = [sum(c == feature for c in selected_units.values()) for feature in FEATURES[:3]] + [len(selected_joins)]
        residual = case['residual']
        if residual.get('disjoint_from_counted_witnesses') is not True or not residual['coverage_refs']:
            raise ValueError('Residual must have coverage and no duplicate counted trace')
        if not residual['vectors']:
            raise ValueError('Residual set must include an explicit completion')
        extras = [vector(v) for v in residual['vectors']]
        if len(set(extras)) != len(extras):
            raise ValueError('Duplicate residual vector')
        for extra_id, extra in enumerate(extras):
            signature = tuple(min(2, a + b) for a, b in zip(base, extra))
            provenance.setdefault(signature, []).append({'case_id': case_id, 'extra_index': extra_id})
        case_records.append({'case_id': case_id, 'base_counts': base, 'residual_count': len(extras)})
    domain = sorted(provenance)
    return {'id': entry['id'], 'status': 'PROJECTED_ALGEBRAIC_ALLOWANCE',
            'domain': [list(v) for v in domain], 'case_records': case_records,
            'preimages': [{'signature': list(v), 'origins': provenance[v]} for v in domain],
            'constant_coordinates': {feature: domain[0][k] for k, feature in enumerate(FEATURES)
                                     if len({v[k] for v in domain}) == 1},
            'limits': 'Projection verifies listed IDs/counts only; visual evidence and completeness require separate review.'}


def project(data):
    if data['schema'] != 'local_hierarchy_cases_v1':
        raise ValueError('Unsupported observation schema')
    rows = data['entries']
    ids = [e['id'] for e in rows]
    if len(ids) != len(set(ids)) or not ids:
        raise ValueError('Nonempty unique entries required')
    result = [project_entry(e) for e in rows]
    common = None
    if all(e['domain'] is not None for e in result):
        common = set.intersection(*(set(map(tuple, e['domain'])) for e in result))
    return {'schema': 'projected_local_hierarchy_v1', 'entries': result,
            'all_entry_common_signatures': None if common is None else [list(v) for v in sorted(common)],
            'pair_scores_computed': False,
            'cross_entry_constraints': data['cross_entry_constraints'],
            'interpretation': 'Joint cases are preserved within entries. Common signatures diagnose zero contrast possibility, not name recognition.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    result = project(json.loads(raw))
    result['input_sha256'] = hashlib.sha256(raw).hexdigest()
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
