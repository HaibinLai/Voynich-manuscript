#!/usr/bin/env python3
"""Validate frozen, state-tagged outer results for publication; no optimization."""
from copy import deepcopy
from itertools import combinations
from hierarchical_k_projection import require, safe_public

IDS = tuple(f'F{i:02}' for i in range(1, 7))
STATES = ('terminal_region_reading', 'opaque_boundary_reading')


def validate_root_outer(docs, hashes, base):
    approval = docs['outer-numeric-approval.json']
    inputs = docs['outer-input.json']
    result = docs['outer-root-results.json']
    observation = docs['f-observation.json']
    require(approval['schema'] == 'root_outer_numeric_approval_v1' and approval['allow_real_outer_numeric'] is True, 'Outer computation not authorized')
    require(approval['scientific_rule_changes'] == 0 and approval['real_S_H_H4_seen_before_this_approval'] is False, 'Outer approval scope changed')
    require(approval['return_to_voynich_authorized'] is False and approval['historical_outcome_v1_preserved'] is True, 'Approval boundary changed')
    for field, path in approval['bound_paths'].items():
        require(hashes[base + '/' + path] == approval[field], 'Approval dependency hash mismatch: ' + path)
    require(result['schema'] == 'root_state_tagged_outer_bounds_v1' and inputs['schema'] == 'state_tagged_outer_signature_domains_v1', 'Outer schema mismatch')
    require(result['input_sha256'] == hashes[base + '/outer_calibration_v1/input_v1.json'] and result['runner_sha256'] == hashes[base + '/run_outer_v1.py'], 'Outer input or runner mismatch')
    require(result['observation_sha256'] == inputs['observation_sha256'] == hashes[base + '/F_observation_v1/observation_v1.json'], 'Outer observation mismatch')
    require(result['global_model'] == inputs['global_model'] and result['global_model']['constraints_retained'] == observation['cross_entry_constraints'], 'Global constraint changed')
    require(result['global_model']['conditional_product_is_outer_relaxation_not_real_independence'] is True, 'Outer relaxation disclaimer absent')
    require([s['id'] for s in inputs['states']] == list(STATES) and [s['id'] for s in result['per_state']] == list(STATES), 'Global states changed')
    require(result['pair_count'] == 15 and result['primary_same_count'] == 2 and result['primary_different_count'] == 4, 'Pair scope changed')
    require(result['conditional_double_positive_numerical_gate'] is False and result['return_to_voynich_authorized'] is False, 'Gate state changed')
    require(result['strict_literal_H'] == {'status': 'MATHEMATICALLY_UNDEFINED_NAME_COVERAGE', 'value': None}, 'Strict literal branch changed')
    observations = {e['id']: e for e in observation['entries']}
    states = {s['id']: s for s in inputs['states']}
    for state in states.values():
        require(list(state['entries']) == list(IDS), 'Outer entry coverage changed')
        for entry_id, case_ids in state['source_case_ids'].items():
            expected = [c['id'] for c in observations[entry_id]['cases']]
            if entry_id == 'F03':
                expected = ['F03_C1' if state['id'] == STATES[0] else 'F03_C2']
            require(case_ids == expected, 'Global state to case mapping changed')
    checked = 0
    for result_set in [result] + [s['result'] for s in result['per_state']]:
        require({(p['a'], p['b']) for p in result_set['pairs']} == set(combinations(IDS, 2)), 'All 15 pairs required')
        for bound in list(result_set['objectives'].values()) + result_set['pairs']:
            for side in ('lower', 'upper'):
                endpoint = bound.get('endpoints', bound.get('complete_endpoint_witnesses'))[side]
                state_id = endpoint['global_state']
                require(state_id in states and list(endpoint['assignment']) == list(IDS), 'Endpoint global assignment incomplete')
                state = states[state_id]
                require(endpoint['same_state_difference_identity_checked'] is True, 'Endpoint difference identity unverified')
                for entry_id, vector in endpoint['assignment'].items():
                    source = endpoint['source_bindings'][entry_id]
                    require(vector in state['entries'][entry_id] and source['signature'] == vector, 'Endpoint signature not in declared state domain')
                    require(source['case_id'] in state['source_case_ids'][entry_id], 'Endpoint case incompatible with global state')
                    case = next(c for c in observations[entry_id]['cases'] if c['id'] == source['case_id'])
                    require(source['extra_vector'] == case['residual']['vectors'][source['extra_index']], 'Endpoint remainder reference changed')
                    require(source['selected_unit_classes'] == case['unit_classes'] and source['selected_join_ids'] == case['join_ids'], 'Endpoint selected IDs changed')
                    require(source['algebraic_preimage_not_certified_geometric_remainder'] is True, 'Endpoint promoted to geometry')
                checked += 1
    require(checked == 108, 'Expected 3 ranges times 18 targets times 2 endpoints')
    view = deepcopy(result)
    safe_public(view)
    return view, {'root_input_and_approval_bound': True, 'global_states': 2, 'endpoint_source_bindings_checked': checked, 'scope': 'Frozen output and source-reference verification; no new optimization or image certification.'}


def verify_outer_comparison(docs, hashes, base):
    root = docs['outer-root-results.json']; independent = docs['outer-independent-results.json']
    comparison = docs['outer-comparison.json']; outcome = docs['calibration-outcome.json']
    require(comparison['schema'] == 'outer_actual_comparison_v1' and comparison['all_pass'] is True, 'Independent outer comparison failed')
    expected = {'root': 'outer_calibration_v1/root_actual_v1/results.json', 'independent': 'independent_outer_v1/actual_v1/results_v1.json', 'input': 'outer_calibration_v1/input_v1.json', 'observation': 'F_observation_v1/observation_v1.json'}
    require(comparison['source_hashes'] == {k: hashes[base + '/' + p] for k, p in expected.items()}, 'Comparison source bindings mismatch')
    require(comparison['checker_sha256'] == hashes[base + '/compare_outer_v1.py'], 'Comparison code mismatch')
    require(comparison['endpoint_witnesses_checked'] == 216 and comparison['source_bindings_checked'] == 1296 and comparison['gate'] is False, 'Comparison scope changed')
    require(comparison['primary_denominators'] == {'same': 2, 'different': 4} and comparison['H4_denominators'] == {'same': 2, 'different': 2}, 'Denominator mismatch')
    require(independent['schema'] == 'independent_shared_g_outer_results_v1' and independent['cross_entry_constraints'] == root['global_model']['constraints_retained'], 'Independent global constraint lost')
    for key, path in [('input_sha256', 'independent_outer_v1/prepared_actual_v1/input_v1.json'), ('runner_sha256', 'independent_outer_v1/outer_runner_v1.py'), ('engine_sha256', 'independent_engine/replay.py'), ('guard_sha256', 'independent_engine/guarded_replay_v1.py'), ('approval_sha256', 'root_outer_numeric_approval_v1.json')]:
        require(independent[key] == hashes[base + '/' + path], 'Independent implementation binding mismatch')
    levels = [('union', root, independent)] + [(s['id'], s['result'], next(x['result'] for x in independent['state_results'] if x['global_state'] == s['id'])) for s in root['per_state']]
    require([r['level'] for r in comparison['levels']] == [r[0] for r in levels], 'Comparison levels incomplete')
    for (level, a, b), checked in zip(levels, comparison['levels']):
        require(checked['all_15_pair_bounds_match'] is True, 'Pair comparison incomplete')
        for key in ('H', 'H4', 'H_minus_H4'):
            for side in ('lower', 'upper'):
                require(a['objectives'][key][side] == b['objectives'][key][side]['value'] == checked['objectives'][key][side], 'Exact objective bound differs')
        bp = {(p['a'], p['b']): p for p in b['all15_pair_bounds']}
        require(len(bp) == 15, 'Independent pair coverage incomplete')
        for pair in a['pairs']:
            require(all(pair[side] == bp[(pair['a'],pair['b'])][side]['value'] for side in ('lower','upper')), 'Exact pair bound differs')
    require(outcome['schema'] == 'fixed_six_calibration_outcome_v2' and outcome['decision'] == 'CONDITIONAL_OUTER_NUMERICAL_GATE_NOT_MET_STOP_NEW_VOYNICH_SCORING', 'Final decision version mismatch')
    require(outcome['actual_pair_or_name_scores_computed'] is True and outcome['scientific_rules_revised_after_F_freeze'] == 0, 'Final computation scope mismatch')
    require(outcome['independent_numerical_review'] == comparison and outcome['double_positive_gate']['passed'] is False, 'Final review state differs')
    for ref in outcome['evidence'] + [outcome['historical_outcome_v1']]:
        require(hashes[base + '/' + ref['path']] == ref['sha256'], 'Final outcome evidence binding mismatch')
    for a,b in [('conditional_H','H'),('conditional_H4','H4'),('H_minus_H4','H_minus_H4')]:
        require(outcome[a] == {k:root['objectives'][b][k] for k in ('lower','upper')}, 'Final displayed interval differs')
    require(outcome['fixed_name_design_preserved'] == docs['method-proposal.json']['fixed_naming_branches'], 'Fixed name design changed')
    require(outcome['Voynich_return']['authorized'] is False and outcome['Voynich_return']['new_scores_computed'] is False, 'Voynich return scope changed')
    return deepcopy(comparison)
