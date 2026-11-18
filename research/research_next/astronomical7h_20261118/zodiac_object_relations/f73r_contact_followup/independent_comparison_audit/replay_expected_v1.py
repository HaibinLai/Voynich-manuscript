#!/usr/bin/env python3
"""Independent read-only expected comparison. Does not import root comparison.
Prints JSON to stdout; no images, network, source mutation or private files.
"""
import json
from pathlib import Path
from collections import Counter
B = Path(__file__).resolve().parents[1]
def read(rel):
    return json.loads((B / rel).read_text())
def unique(rows, key):
    d = {r[key]: r for r in rows}
    assert len(d) == len(rows)
    return d

def calculate():
    fixed = read('input_freeze_v1.json')
    prepared = read('prepared_views_v1.json')
    root = read('root_repeat/observation_v1.json')
    peer = read('literature_repeat/observation_v1.json')
    mapping = read('comparison_mapping_v1.json')
    original = read('../circle_spatial_observer/f73r/observer_report_v1.json')
    ids = fixed['fixed_region_ids']
    assert len(ids) == len(set(ids)) == 9
    rr = unique(root['records'], 'region_uid'); pp = unique(peer['records'], 'region_uid')
    assert list(rr) == list(pp) == ids == peer['fixed_region_ids']
    assert peer['fixed_selection_pairs'] == fixed['pairs']
    orig_text = unique(original['text_records'], 'region_uid')
    original_edges = [e for e in original['relation_edges'] if e['edge_kind'] == 'text_to_object' and e['source_uid'] in ids]
    oe = unique(original_edges, 'edge_uid')
    assert len(oe) == 24
    pv = unique(prepared['views'], 'view_id')
    rv = unique(root['actual_view_receipts'], 'view_id'); qv = unique(peer['view_receipts'], 'view_id')
    assert len(pv) == len(rv) == len(qv) == 27
    assert set(pv) == set(rv) == set(qv)
    view_fields = ['view_id', 'region_uid', 'mode', 'crop_xyxy_original', 'dimensions_px', 'filename', 'sha256']
    view_rows = []
    for vid, expected in pv.items():
        assert all(rv[vid][k] == qv[vid][k] == expected[k] for k in view_fields)
        x0,y0,x1,y1 = expected['crop_xyxy_original']
        assert expected['dimensions_px'] == [x1-x0,y1-y0]
        assert 0 <= x0 < x1 <= fixed['original_image']['dimensions_px'][0]
        assert 0 <= y0 < y1 <= fixed['original_image']['dimensions_px'][1]
        assert rv[vid].get('actually_displayed_with') and qv[vid].get('actually_displayed_with_view_image') is True
        view_rows.append({'view': {k: expected[k] for k in view_fields}, 'root_receipt': rv[vid], 'peer_receipt': qv[vid], 'same_prepared_identity': True})
    rows = []; edges = []; ptargets = []
    for uid in ids:
        r = rr[uid]; p = pp[uid]; obs = p['observation']
        selected_edges = [e for e in original_edges if e['source_uid'] == uid]
        assert r['original_candidate_edges_preserved'] == selected_edges
        assert p['all_original_candidate_edges'] == selected_edges
        assert p['original_text_record'] == orig_text[uid]
        assert r['original_candidate_ids_preserved'] == orig_text[uid]['candidate_object_ids']
        assert r['original_edges_are_not_new_independent_edge_ratings'] is True
        assert p['view_ids'] == r['view_ids'] == [vid for vid in pv if pv[vid]['region_uid'] == uid]
        assert len(r['view_ids']) == 3
        assert {pv[v]['mode'] for v in r['view_ids']} == {'original','expanded80','candidate_context'}
        pg = unique(p['edge_grade_comparison'], 'edge_uid')
        assert set(pg) == {e['edge_uid'] for e in selected_edges} == set(obs['followup_edge_levels'])
        for e in selected_edges:
            follow = pg[e['edge_uid']]
            assert follow['source_uid'] == e['source_uid'] and follow['target_uid'] == e['target_uid']
            assert follow['original_grade'] == e['evidence_level']
            assert follow['followup_grade'] == obs['followup_edge_levels'][e['edge_uid']]
            assert follow['candidate_retained'] is True
            er = {'region_uid': uid, 'edge_uid': e['edge_uid'], 'target_uid': e['target_uid'], 'original_grade': e['evidence_level'], 'peer_followup_grade': follow['followup_grade'], 'root_new_edge_grade': None, 'original_record': e, 'peer_edge_record': follow}
            edges.append(er)
            if e['evidence_level'] == 'P':
                # Only the predetermined original P target can be compared to
                # the root's explicit region target, never the highest peer edge.
                root_target_grade = r.get('root_region_contact_level') if e['target_uid'] in r.get('root_contact_target_uids',[]) else None
                ptargets.append({'region_uid': uid, 'edge_uid': e['edge_uid'], 'target_uid': e['target_uid'], 'original_grade': 'P', 'root_explicit_target_region_grade': root_target_grade, 'peer_exact_edge_grade': follow['followup_grade'], 'compatible_at_mapped_scope': None if root_target_grade is None else root_target_grade == follow['followup_grade']})
        contact = obs.get('contact')
        peer_norm = mapping['peer_contact_to_region_diagnostic'].get(contact)
        leader = obs.get('independent_text_origin_line')
        peer_leader = mapping['peer_line_status_to_confirmation'].get(leader)
        root_contact = r.get(mapping['root_region_field'])
        root_leader = r.get(mapping['root_line_field'])
        rows.append({'region_uid': uid, 'original_band': r['original_band'], 'root_region_contact': root_contact, 'peer_contact_raw': contact, 'peer_contact_normalized': peer_norm, 'contact_compatible': None if peer_norm is None or root_contact is None else peer_norm == root_contact, 'root_complete_leader_confirmed': root_leader, 'peer_line_raw': leader, 'peer_complete_leader_confirmed': peer_leader, 'complete_leader_compatible': None if peer_leader is None or root_leader is None else peer_leader == root_leader, 'original_candidate_ids': r['original_candidate_ids_preserved'], 'root_target_ids': r['root_contact_target_uids'], 'root_facts': r['observed_facts'], 'peer_observation_complete': obs, 'detail_scope_notes': mapping['detail_scope_notes'][uid], 'root_record_complete': r, 'peer_record_complete': p})
    assert len(ptargets) == 5
    central = next(x for x in fixed['pairs'] if x['candidate'] == 'f73r:ZC01')
    assert central['control'] is None
    return {'schema': 'independent_f73r_contact_expected_v1', 'fixed_region_ids': ids, 'fixed_pairs': fixed['pairs'], 'original_image': fixed['original_image'], 'regions': rows, 'original_and_peer_edges': edges, 'five_original_P_exact_target_comparisons': ptargets, 'views': view_rows, 'summary': {'regions': len(rows), 'root_views': len(rv), 'peer_views': len(qv), 'preserved_original_edges': len(edges), 'original_P_targets': len(ptargets), 'normalized_region_compatible_count': sum(r['contact_compatible'] is True for r in rows), 'complete_leader_field_compatible_count': sum(r['complete_leader_compatible'] is True for r in rows), 'root_confirmed_leaders': sum(r['root_complete_leader_confirmed'] is True for r in rows), 'peer_confirmed_leaders': sum(r['peer_complete_leader_confirmed'] is True for r in rows), 'peer_edge_grades': dict(Counter(e['peer_followup_grade'] for e in edges)), 'peer_edge_changes_from_original': sum(e['peer_followup_grade'] != e['original_grade'] for e in edges), 'root_new_24_edge_ratings_count': None, 'central_control': None}, 'limits': mapping['limits'], 'receipt_checks_do_not_reobserve_images': True}
if __name__ == '__main__':
    print(json.dumps(calculate(), ensure_ascii=False, sort_keys=True, indent=2))
