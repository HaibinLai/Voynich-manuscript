#!/usr/bin/env python3
"""Validate frozen F bookkeeping for display only; never form joint scoring input."""
from copy import deepcopy
from hierarchical_k_projection import check_projection, require, safe_public, FEATURES

IDS = tuple(f'F{i:02}' for i in range(1, 7))
SIZES = (3, 9, 9, 9, 3, 81)


def make_f_view(docs, hashes, base_path):
    observation = docs['f-observation.json']
    primary = docs['f-root-projection.json']
    independent = docs['f-independent-projection.json']
    comparison = docs['f-projection-comparison.json']
    # This original decision is retained as history, not promoted to the current release state.
    outcome = docs['calibration-outcome-v1.json']
    digest = hashes[base_path + '/F_observation_v1/observation_v1.json']
    require(observation['schema'] == 'local_hierarchy_cases_v1', 'Unexpected F observation schema')
    require(primary['schema'] == 'projected_local_hierarchy_v1', 'Unexpected F primary schema')
    require(independent['schema'] == 'independent_local_hierarchy_projection_v1', 'Unexpected F independent schema')
    require(primary['input_sha256'] == independent['input_sha256'] == digest, 'F input bindings differ')
    require(independent['engine_sha256'] == hashes[base_path + '/independent_engine/independent_projection_v1.py'], 'F independent engine differs')
    require(comparison['schema'] == 'per_entry_projection_comparison_v1' and comparison['all_match'] is True, 'F comparison not verified')
    require(comparison['checked_origin_count'] == 810 and comparison['cross_entry_constraint_count'] == 1, 'F comparison scope differs')
    require(comparison['primary_retains_constraints_verbatim'] is True and comparison['joint_scoring_authorized'] is False and comparison['pair_or_name_scores_computed'] is False, 'F comparison crosses permitted boundary')
    bindings = {r['role']: r['sha256'] for r in comparison['inputs']}
    require(bindings == {'observation': digest, 'primary': hashes[base_path + '/F_observation_v1/root_projection_v1.json'], 'independent': hashes[base_path + '/F_observation_v1/independent_projection_v1/projection.json']}, 'F comparison bindings differ')
    require(comparison['script_sha256'] == hashes[base_path + '/compare_projections_v1.py'], 'F comparison implementation binding differs')
    require(primary['pair_scores_computed'] is False and primary['cross_entry_constraints'] == observation['cross_entry_constraints'] and len(observation['cross_entry_constraints']) == 1, 'F global constraint lost')
    require(observation['cross_entry_constraints'][0]['safe_to_pass_as_empty_cross_entry_constraints'] is False, 'F unresolved constraint relaxed')
    for rows in (observation['entries'], primary['entries'], independent['entries'], comparison['entries'], outcome['entries']):
        require([e['id'] for e in rows] == list(IDS), 'All six ordered rows required')
    require(outcome['schema'] == 'fixed_six_calibration_outcome_v1' and outcome['decision'] == 'OPERATIONAL_CALIBRATION_NOT_ESTABLISHED_STOP_NEW_VOYNICH_SCORING', 'Unexpected scientific decision')
    require(outcome['all_six_scoring_qualification_established'] is False and outcome['actual_pair_or_name_scores_computed'] is False, 'Unexpected F score state')
    for ref in outcome['inputs']:
        require(hashes[base_path + '/' + ref['path']] == ref['sha256'], 'Outcome source binding differs')
    for key in ('conditional_H', 'conditional_H4', 'H_minus_H4'):
        require(outcome[key]['status'] == 'NOT_EXECUTED_MEASUREMENT_NOT_QUALIFIED' and outcome[key]['lower'] is None and outcome[key]['upper'] is None, 'Not-executed result must remain null')
    require(outcome['strict_literal_H']['status'] == 'MATHEMATICALLY_UNDEFINED_NAME_COVERAGE' and outcome['strict_literal_H']['value'] is None, 'Literal name branch differs')
    require(len(outcome['pairs']) == 15 and all(p['morphology_status'] == 'NOT_EXECUTED_JOINT_MEASUREMENT_NOT_QUALIFIED' and p['S_lower'] is None and p['S_upper'] is None for p in outcome['pairs']), 'All fifteen unexecuted pairs required')
    rows, total = [], 0
    for entry, a, b, compared, summary, size in zip(observation['entries'], primary['entries'], independent['entries'], comparison['entries'], outcome['entries'], SIZES):
        check_projection(entry, a)
        require(a['domain'] == b['domain'] and len(a['domain']) == b['domain_size'] == compared['domain_size'] == summary['marginal_record_domain_size'] == size, 'F complete marginal domains differ')
        require(all(compared[k] is True for k in ('complete_domain_matches', 'all_case_extra_origins_match', 'all_case_base_counts_match')), 'F per-row comparison failed')
        expected = {tuple(p['signature']): p['origins'] for p in a['preimages']}
        found, count = {}, 0
        cases = {c['id']: c for c in entry['cases']}
        for item in b['preimages']:
            sig = tuple(item['signature'])
            require(sig not in found, 'Duplicate F provenance')
            found[sig] = []
            for witness in item['witnesses']:
                case = cases[witness['case_id']]
                extra = case['residual']['vectors'][witness['extra_index']]
                base = [sum(v == f for v in case['unit_classes'].values()) for f in FEATURES[:3]] + [len(case['join_ids'])]
                require(witness['selected_unit_classes'] == case['unit_classes'] and witness['selected_join_ids'] == case['join_ids'], 'F selected IDs differ')
                require(witness['counted_vector'] == base and witness['extra_vector'] == extra and tuple(witness['signature']) == sig, 'F origin counts differ')
                require(witness['coverage_refs'] == case['residual']['coverage_refs'], 'F origin coverage differs')
                found[sig].append({k: witness[k] for k in ('case_id', 'extra_index')})
                count += 1
        require(found == expected and count == compared['origin_count'], 'F complete provenance differs')
        total += count
        rows.append({'id': entry['id'], 'observation_record': deepcopy(entry), 'projection_record': deepcopy(a), 'summary': deepcopy(summary),
                     'coordinate_values': {f: sorted({v[i] for v in a['domain']}) for i, f in enumerate(FEATURES)},
                     'view_receipts': [deepcopy(v) for v in observation['actual_view_receipts'] if v['entry'] == entry['id']]})
    require(total == 810, 'F origin coverage incomplete')
    diagnostic = docs['f-independent-diagnostics.json']
    require(diagnostic['input_sha256'] == digest and diagnostic['projection_sha256'] == bindings['independent'], 'F diagnostic binding differs')
    require(diagnostic['diagnostic_code_sha256'] == hashes[base_path + '/F_observation_v1/independent_projection_v1/diagnose_v1.py'], 'F diagnostic code differs')
    require(diagnostic['all_case_extra_preimages_verified'] == 810 and diagnostic['all_six_same_granularity_conditioning_complete'] is False and diagnostic['cartesian_guard_rejects_retained_nonempty_constraints'] is True, 'F diagnostic boundary differs')
    result = {'schema': 'hierarchical_F_record_view_v1', 'features': list(FEATURES), 'rows': rows,
              'state': 'PER_ENTRY_RECORD_ALGEBRA_ONLY_NOT_A_JOINT_SCORING_INPUT', 'verified_origin_count': total,
              'cross_entry_constraints': deepcopy(observation['cross_entry_constraints']),
              'cross_entry_constraint_scope': observation['cross_entry_constraint_scope'],
              'joint_scoring_input_established': False, 'name_scores_computed': False,
              'historical_outcome_v1': deepcopy(outcome),
              'scope_note': 'Original marginal record package only; a later global model must be separately frozen and verified.',
              'warning': 'Marginal unions and their intersection do not establish a common global state; no claim H=0.'}
    safe_public(result)
    return result
