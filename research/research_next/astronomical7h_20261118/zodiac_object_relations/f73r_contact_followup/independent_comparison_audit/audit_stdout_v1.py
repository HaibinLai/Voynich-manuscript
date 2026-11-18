#!/usr/bin/env python3
"""Read-only comparison to the already frozen independent expected result."""
import json
import hashlib
import subprocess
import sys
from pathlib import Path
B = Path(__file__).resolve().parents[1]
A = Path(__file__).resolve().parent

def main():
    expected = json.loads((A / 'independent_expected_v1.json').read_text())
    actual_bytes = (B / 'comparison_v1.json').read_bytes()
    actual = json.loads(actual_bytes)
    checks = 0; mismatches = []
    def equal(path, a, b):
        nonlocal checks
        checks += 1
        if type(a) is not type(b):
            mismatches.append({'path': path, 'kind': 'type', 'expected': a, 'actual': b}); return
        if isinstance(a, dict):
            if a.keys() != b.keys():
                mismatches.append({'path': path, 'kind': 'keys', 'expected': sorted(a), 'actual': sorted(b)}); return
            for k in a: equal(path + '/' + k, a[k], b[k])
        elif isinstance(a, list):
            if len(a) != len(b):
                mismatches.append({'path': path, 'kind': 'length', 'expected': len(a), 'actual': len(b)}); return
            for i,(x,y) in enumerate(zip(a,b)): equal(path + '/' + str(i), x, y)
        elif a != b:
            mismatches.append({'path': path, 'kind': 'value', 'expected': a, 'actual': b})
    equal('/fixed_pairs', expected['fixed_pairs'], actual['fixed_pairs'])
    equal('/region_order', expected['fixed_region_ids'], [x['region_uid'] for x in actual['rows']])
    assert len({x['region_uid'] for x in actual['rows']}) == 9
    edge_rows = expected['original_and_peer_edges']
    ptargets = expected['five_original_P_exact_target_comparisons']
    for er, ar in zip(expected['regions'], actual['rows']):
        uid = er['region_uid']; co = ar['comparison']
        equal(uid + '/root_full_record', er['root_record_complete'], ar['root_repeat'])
        equal(uid + '/peer_full_record', er['peer_record_complete'], ar['other_repeat'])
        equal(uid + '/original_text', er['peer_record_complete']['original_text_record'], ar['original_record']['text'])
        equal(uid + '/original_edges', [x['original_record'] for x in edge_rows if x['region_uid']==uid], ar['original_record']['edges'])
        fields = {'root_region_level':'root_region_contact','peer_literal_contact':'peer_contact_raw','peer_mapped_region_level':'peer_contact_normalized','region_categories_compatible':'contact_compatible','root_complete_leader_confirmed':'root_complete_leader_confirmed','peer_complete_leader_confirmed':'peer_complete_leader_confirmed','leader_confirmation_compatible':'complete_leader_compatible','detail_scope_notes':'detail_scope_notes'}
        for target, source in fields.items():equal(uid + '/' + target, er[source], co[target])
        equal(uid + '/root_not_24_ratings', False, co['root_independent_all_edges_rated'])
        equal(uid + '/original_preserved', True, co['original_edges_preserved'])
        equal(uid + '/historical_absence_not_inferred', True, co['no_historical_absence_inferred'])
        pt = [x for x in ptargets if x['region_uid']==uid]
        equal(uid + '/selected_count', len(pt), len(co['selected_P_target_comparison']))
        for x,y in zip(pt,co['selected_P_target_comparison']):
            for target, source in {'original_edge_uid':'edge_uid','target_uid':'target_uid','root_selected_contact_region_level':'root_explicit_target_region_grade','peer_that_exact_edge_level':'peer_exact_edge_grade','levels_equal':'compatible_at_mapped_scope'}.items():
                equal(uid + '/target/' + target, x[source], y[target])
    ev = []
    for observer in ['root','peer']:
        for v in expected['views']:
            ev.append({'observer':observer,'view_id':v['view']['view_id'],'sha256':v['view']['sha256']})
    equal('/all54_view_checks',ev,actual['view_integrity_checks'])
    es = expected['summary']
    wanted = {'fixed_regions': es['regions'], 'original_candidate_edges_preserved':es['preserved_original_edges'], 'native_views_per_repeat':es['root_views'], 'same_original_image_not_independent_samples':True, 'mapped_region_category_compatible':es['normalized_region_compatible_count'], 'selected_original_P_targets_compared':es['original_P_targets'], 'selected_P_target_level_differences':sum(x['compatible_at_mapped_scope'] is False for x in ptargets), 'root_complete_leader_confirmations':es['root_confirmed_leaders'], 'peer_complete_leader_confirmations':es['peer_confirmed_leaders'], 'central_same_band_control':None}
    equal('/summary',wanted,actual['summary'])
    equal('/all_mapping_limits',expected['limits'],actual['limits'])
    equal('/no_new_score_or_gate',True,actual['no_new_text_score_or_sequence_qualification'])
    replay = subprocess.run([sys.executable,str(B/'compare_v1.py')],capture_output=True,check=True)
    equal('/root_stdout_byte_identical',True,replay.stdout==actual_bytes)
    independent_replay = subprocess.run([sys.executable,str(A/'replay_expected_v1.py')],capture_output=True,check=True)
    equal('/independent_stdout_byte_identical',True,independent_replay.stdout==(A/'independent_expected_v1.json').read_bytes())
    result = {'schema':'f73r_independent_comparison_audit_stdout_v1','checks':checks,'mismatches':mismatches,'mismatch_count':len(mismatches),'root_public_stdout_byte_identical':replay.stdout==actual_bytes,'independent_stdout_byte_identical':independent_replay.stdout==(A/'independent_expected_v1.json').read_bytes(),'independent_expected_sha256':hashlib.sha256((A/'independent_expected_v1.json').read_bytes()).hexdigest(),'root_comparison_sha256':hashlib.sha256(actual_bytes).hexdigest(),'fixed_regions':9,'saved_view_receipts_per_repeat':27,'preserved_original_edges':24,'original_P_exact_targets':5,'root_new_all24_edge_ratings':None,'central_control':None,'normalized_compatibility_is_not_identical_original_enum_or_expert_consensus':True,'detailed_observation_fields_preserved':True,'code_scope_note':'The root implementation uses direct mapping-key indexing and assumes these immutable complete schemas. For unseen/unmapped or absent future fields it raises rather than emitting null; no such field is missing in these frozen inputs. This audit does not certify a general missing-data parser.'}
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))
    if mismatches:raise SystemExit(1)
if __name__=='__main__':main()
