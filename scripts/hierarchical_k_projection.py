#!/usr/bin/env python3
"""Read-only adapter for a future explicit, frozen K publication input.

No auto-discovery, output writes, image access, actual scores, or current-page mutation.
load_k_view(root, inputs) accepts role -> {path, sha256} for observation,
projection, independent_receipt. Missing projection is explicitly unestablished.
make_k_view(...) is a pure function, also suitable for artificial fixtures.
The receipt is displayed verbatim; its presence is not interpreted as a PASS.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

IDS = ('K01', 'K02', 'K03', 'K04')
FEATURES = ('Q0', 'Q1', 'Q2', 'QJ')
ROLES = {'observation', 'projection', 'independent_receipt'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def vector(value):
    require(isinstance(value, list) and len(value) == 4 and
            all(type(x) is int and x in (0, 1, 2) for x in value),
            'Expected a complete four-coordinate ternary vector')
    return tuple(value)


def safe_public(value):
    if isinstance(value, str):
        require(not any(s in value for s in ('/Users/', '/home/', '/private/var/', 'ghp_', 'github_pat_')),
                'Machine path or credential-like text cannot enter the public view')
    elif isinstance(value, dict):
        for key, item in value.items():
            safe_public(key)
            safe_public(item)
    elif isinstance(value, list):
        for item in value:
            safe_public(item)


def check_projection(entry, projected):
    """Check recorded case/count provenance, not visual correctness or completeness."""
    domain = projected.get('domain')
    if entry.get('unit_defined') is not True:
        require(domain is None and projected.get('status') == 'UNIT_UNDEFINED',
                'Undefined unit must retain a null domain')
        return
    require(projected.get('status') == 'PROJECTED_ALGEBRAIC_ALLOWANCE', 'Unexpected projection state')
    require(isinstance(domain, list) and len(domain) > 0, 'Defined domain must not be empty')
    actual = [vector(v) for v in domain]
    require(len(set(actual)) == len(actual), 'Duplicate signature')
    require(entry.get('cases'), 'Empty cases are an input contradiction')
    expected, records, seen = {}, [], set()
    units, joins = entry['units'], entry['joins']
    require(not set(units) & set(joins), 'Unit/join IDs overlap')
    for case in entry['cases']:
        cid = case['id']
        require(cid not in seen, 'Duplicate case ID')
        seen.add(cid)
        selected, selected_joins = case['unit_classes'], case['join_ids']
        require(set(selected) <= set(units) and set(selected_joins) <= set(joins), 'Unknown witness ID')
        require(len(selected_joins) == len(set(selected_joins)), 'Repeated join')
        for uid, feature in selected.items():
            require(feature in FEATURES[:3] and feature in units[uid]['allowed_classes'], 'Unsupported class')
        active = set(selected) | set(selected_joins)
        for group in entry.get('at_most_one', []):
            require(len(set(group['ids']) & active) <= 1, 'Alias or exclusion violated')
        base = [sum(v == feature for v in selected.values()) for feature in FEATURES[:3]] + [len(selected_joins)]
        residual = case['residual']
        require(residual.get('coverage_refs') and residual.get('disjoint_from_counted_witnesses') is True,
                'Residual must reference coverage and declare no duplicate counted witnesses')
        extras = [vector(v) for v in residual['vectors']]
        require(extras and len(set(extras)) == len(extras), 'Empty/duplicate residual vectors')
        records.append({'case_id': cid, 'base_counts': base, 'residual_count': len(extras)})
        for index, extra in enumerate(extras):
            sig = tuple(min(2, a + b) for a, b in zip(base, extra))
            expected.setdefault(sig, []).append({'case_id': cid, 'extra_index': index})
    require(set(actual) == set(expected), 'Projection domain differs from complete cases and residuals')
    require(projected.get('case_records') == records, 'Recorded case counts differ')
    preimages = projected.get('preimages', [])
    require(len(preimages) == len(expected), 'Missing/duplicate signature provenance')
    seen_preimages = set()
    for item in preimages:
        sig = vector(item['signature'])
        require(sig not in seen_preimages and sig in expected, 'Unknown/duplicate provenance signature')
        seen_preimages.add(sig)
        require(item['origins'] == expected[sig], 'Projection origin differs from original case/extra')
    constants = {f: actual[0][i] for i, f in enumerate(FEATURES) if len({v[i] for v in actual}) == 1}
    require(projected.get('constant_coordinates') == constants, 'Constant-coordinate summary differs')


def make_k_view(observation=None, projection=None, independent_receipt=None, source_refs=None):
    """Return a detached view model; all unknown values remain None, never zero."""
    require(observation is not None or projection is None, 'Projection requires its observation')
    require(projection is not None or independent_receipt is None, 'Receipt requires its projection')
    originals = {i: None for i in IDS}
    if observation is not None:
        require(observation.get('schema') == 'local_hierarchy_cases_v1', 'Unsupported observation schema')
        require([e['id'] for e in observation['entries']] == list(IDS), 'All four K entries required in order')
        originals = {e['id']: e for e in observation['entries']}
    projections = {}
    common = None
    if projection is not None:
        require(projection.get('schema') == 'projected_local_hierarchy_v1', 'Unsupported projection schema')
        require(projection.get('pair_scores_computed') is False, 'K module must not include name-pair scores')
        require([e['id'] for e in projection['entries']] == list(IDS), 'Projection must retain all four K entries')
        require(projection['cross_entry_constraints'] == observation['cross_entry_constraints'], 'Cross-entry constraints changed')
        projections = {e['id']: e for e in projection['entries']}
        for uid in IDS:
            check_projection(originals[uid], projections[uid])
        if all(p['domain'] is not None for p in projections.values()):
            common = sorted(set.intersection(*(set(map(tuple, p['domain'])) for p in projections.values())))
            common = [list(v) for v in common]
        require(projection.get('all_entry_common_signatures') == common, 'Common-signature summary differs')
    rows = []
    for uid in IDS:
        p = projections.get(uid)
        domain = None if p is None else p['domain']
        rows.append({'id': uid, 'state': 'PROJECTION_NOT_ESTABLISHED' if p is None else p['status'],
                     'original_record': deepcopy(originals[uid]), 'projection_record': deepcopy(p),
                     'domain': deepcopy(domain), 'signature_count': None if domain is None else len(domain),
                     'coordinate_values': None if domain is None else {f: sorted({v[k] for v in domain}) for k, f in enumerate(FEATURES)},
                     'constant_coordinates': None if domain is None else deepcopy(p['constant_coordinates'])})
    constants = {}
    if all(r['domain'] is not None for r in rows):
        for feature in FEATURES:
            values = {v for r in rows for v in r['coordinate_values'][feature]}
            if len(values) == 1:
                constants[feature] = next(iter(values))
    result = {'schema': 'hierarchical_k_joint_domain_view_v1',
              'state': 'PROJECTED_WITH_RECORD_CHECK' if projection is not None else 'PROJECTION_NOT_ESTABLISHED',
              'features': list(FEATURES), 'rows': rows,
              'all_entry_common_signatures': common,
              'all_entry_constant_coordinates': constants if common is not None else None,
              'cross_entry_constraints': deepcopy(observation.get('cross_entry_constraints')) if observation else None,
              'independent_receipt': deepcopy(independent_receipt),
              'independent_review_state': 'RECORD_ATTACHED_NOT_INTERPRETED' if independent_receipt is not None else 'NOT_INCLUDED',
              'sources': deepcopy(source_refs or []), 'pair_scores_computed': False,
              'limits': 'Complete recorded signatures only. Per-coordinate sets must not be recombined. Bookkeeping validation is not visual authentication. Common set intersection alone does not prove cross-entry feasibility.'}
    safe_public(result)
    return result


def load_k_view(repository_root, inputs):
    """Read only named path/hash pairs. Does not write or scan any directory.

    Example roles: observation, projection, independent_receipt. Pass an empty
    mapping for an unestablished module. A supplied projection must bind the
    exact observation bytes through input_sha256. Receipt schema is intentionally
    not interpreted until a later publication adapter specifies it.
    """
    require(isinstance(inputs, dict) and set(inputs) <= ROLES, 'Unknown input role')
    root = Path(repository_root).resolve()
    docs, sources = {}, []
    for role, ref in inputs.items():
        path = Path(ref['path'])
        require(not path.is_absolute() and '..' not in path.parts, 'Repository-relative input paths required')
        resolved = (root / path).resolve()
        require(resolved.is_relative_to(root), 'Input resolves outside repository')
        raw = resolved.read_bytes()
        digest = sha256(raw).hexdigest()
        require(digest == ref['sha256'], 'Input hash mismatch: ' + role)
        docs[role] = json.loads(raw)
        sources.append({'role': role, 'path': str(path), 'sha256': digest})
    if 'projection' in docs:
        require('observation' in inputs, 'Projection has no frozen observation input')
        require(docs['projection'].get('input_sha256') == inputs['observation']['sha256'], 'Projection observation binding mismatch')
    return make_k_view(docs.get('observation'), docs.get('projection'), docs.get('independent_receipt'), sources)


def verify_frozen_k_comparison(docs, hashes, base_path):
    """Validate this phase's precise comparison schema, bindings and all origins.

    Input is already hash-verified bytes parsed by the caller. This function does
    bookkeeping comparison only; it does not read files or calculate name scores.
    """
    comparison = docs['k-projection-comparison.json']
    require(comparison.get('schema') == 'K_joint_projection_comparison_v1', 'Wrong comparison schema')
    require(comparison.get('all_match') is True and comparison.get('no_K_name_scores_computed') is True,
            'Comparison does not certify this permitted scope')
    require(comparison.get('checked_preimage_count') == 327, 'Expected all 327 recorded origins')
    require(set(comparison['hashes']) == {'observation_v1.json', 'root_projection_v1.json', 'independent_projection_v1/projection.json', 'independent_projection_v1/diagnostics_v1.json'}, 'Incomplete comparison bindings')
    for name, digest in comparison['hashes'].items():
        require(hashes.get(base_path + '/K_development_v1/' + name) == digest, 'Comparison binding mismatch')
    observation, primary, independent = (docs[k] for k in
        ('k-observation.json', 'k-root-projection.json', 'k-independent-projection.json'))
    digest = hashes[base_path + '/K_development_v1/observation_v1.json']
    require(primary.get('input_sha256') == independent.get('input_sha256') == digest, 'Observation binding mismatch')
    require(independent.get('schema') == 'independent_local_hierarchy_projection_v1', 'Independent schema mismatch')
    require(independent.get('coordinate_order') == list(FEATURES), 'Coordinate order differs')
    require(independent['engine_sha256'] == hashes[base_path + '/independent_engine/independent_projection_v1.py'], 'Independent engine binding mismatch')
    require([e['id'] for e in independent['entries']] == list(IDS), 'Independent entries differ')
    require([e['id'] for e in comparison['checked_entries']] == list(IDS), 'Comparison entries differ')
    count = 0
    for original, a, b, c, size in zip(observation['entries'], primary['entries'], independent['entries'], comparison['checked_entries'], (1, 27, 9, 2)):
        check_projection(original, a)
        require(a['domain'] == b['domain'] and len(a['domain']) == b['domain_size'] == c['domain_size'] == size, 'Complete domains differ')
        require(c['exact_joint_domain_matches'] is c['all_case_extra_preimages_match'] is True, 'Entry comparison not passed')
        require(c['constant_coordinates'] == a['constant_coordinates'], 'Comparison constants differ')
        expected = {tuple(x['signature']): x['origins'] for x in a['preimages']}
        found = {}
        cases = {x['id']: x for x in original['cases']}
        for image in b['preimages']:
            signature = vector(image['signature'])
            require(signature not in found, 'Duplicate independent signature provenance')
            found[signature] = []
            for witness in image['witnesses']:
                case = cases[witness['case_id']]
                extra = case['residual']['vectors'][witness['extra_index']]
                base = [sum(v == f for v in case['unit_classes'].values()) for f in FEATURES[:3]] + [len(case['join_ids'])]
                require(witness['selected_unit_classes'] == case['unit_classes'] and witness['selected_join_ids'] == case['join_ids'], 'Independent selected identities differ')
                require(witness['counted_vector'] == base and witness['extra_vector'] == extra, 'Independent count source differs')
                require(witness['coverage_refs'] == case['residual']['coverage_refs'], 'Independent coverage reference differs')
                require(vector(witness['signature']) == signature, 'Independent witness signature differs')
                found[signature].append({k: witness[k] for k in ('case_id', 'extra_index')})
                count += 1
        require(found == expected, 'Independent complete preimages differ')
    require(count == 327, 'Origin coverage differs')
    diagnostic = docs['k-independent-diagnostics.json']
    require(diagnostic['input_sha256'] == digest and diagnostic['projection_sha256'] == hashes[base_path + '/K_development_v1/independent_projection_v1/projection.json'], 'Diagnostic binding mismatch')
    require(diagnostic['engine_sha256'] == independent['engine_sha256'] and diagnostic['diagnostic_code_sha256'] == hashes[base_path + '/K_development_v1/independent_projection_v1/diagnose_v1.py'], 'Diagnostic implementation mismatch')
    require(diagnostic['all_preimages_replayed'] == 327 and diagnostic['domain_sizes'] == dict(zip(IDS, (1, 27, 9, 2))), 'Diagnostic scope differs')
    require(diagnostic['fixed_constant_coordinates_across_all_entries'] == {'Q0': 2}, 'Global constant summary differs')
    require(comparison['common_signatures'] == primary['all_entry_common_signatures'] == diagnostic['all_four_common_signatures'] == [], 'Common set summary differs')
    return {'state': 'EXACT_FROZEN_COMPARISON_VERIFIED', 'entry_count': 4, 'origin_count': count,
            'domain_sizes': [1, 27, 9, 2], 'scope': 'Two implementations of the same informed record; not independent expert image evidence.'}
