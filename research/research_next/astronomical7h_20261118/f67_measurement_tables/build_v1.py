"""Read frozen published observations; emit three evidence tables, no text scores."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FIXED = ['f67r2.' + str(i) for i in range(52, 64)]

def load(path):
    return json.loads(path.read_text())

def main():
    frozen = load(HERE / 'input_freeze_v1.json')
    inputs = {}
    for row in frozen['files']:
        p = ROOT / row['path']
        assert hashlib.sha256(p.read_bytes()).hexdigest() == row['sha256'], row['path']
        inputs[row['role']] = load(p)
    guided, inventory, geometry = (inputs[k] for k in ['guided', 'inventory', 'geometry'])
    spacing, source = (inputs[k] for k in ['spacing', 'source_followup'])
    assert [r['locator'] for r in guided['targets']] == FIXED
    assert [r['locator'] for r in spacing['records']] == FIXED
    assert len(inventory['records']) == 74
    assert sum(len(r['versions']) for r in inventory['records']) == 148
    sector = {r['sector_id']: r for r in guided['sectors']}
    records = {r['locator']: r for r in inventory['records']}
    space = {r['locator']: r for r in spacing['records']}
    cross = {r['locus']: r for r in geometry['face_and_short_zone_crosswalk']}
    body = {r['guided_sector']: r for r in geometry['body_region_crosswalk']}
    follow = {r['id']: r for r in source['boundary_findings']}
    image = inputs['image']
    image_sectors = {r['id']: r for r in image['sectors']}
    assert set(follow) == {'B07', 'B08', 'B09'}
    role_rows, transcription_rows, order_rows = [], [], []
    bysector = {r['sector_id']: r['locator'] for r in guided['targets']}
    order = geometry['cycle']['guided_order']
    assert [bysector[s] for s in order] == guided['cycle']['working_order']
    for target in guided['targets']:
        loc, sid = target['locator'], target['sector_id']
        rec, sr, sec = records[loc], space[loc], sector[sid]
        assert sr['versions'] == rec['versions']
        assert {v: rec['versions'][v]['raw_transcription'] for v in ['ZL', 'IT']} == target['raw_versions']
        role_rows.append({'locator': loc, 'guided_target_original': target,
                          'image_sector_original': image_sectors[cross[loc]['shared_unique_geometric_candidate']],
                          'guided_sector_original': sec, 'face_and_label_crosswalk_original': cross[loc],
                          'body_region_crosswalk_original': body[sid],
                          'status': 'working_spatial_candidates_only',
                          'label_specific_body_definition': 'not_fixed',
                          'semantic_role': None})
        transcription_rows.append({'locator': loc, 'source_versions': rec['versions'],
                                   'source_definition_category': target['word_definition'],
                                   'spacing_review_original': sr,
                                   'source_string_available': True,
                                   'image_word_boundary_certified': sr['word_boundary_certified'],
                                   'image_character_identity_certified': sr['character_identity_certified'],
                                   'full_primary_test_eligible': False})
        successor = order[(order.index(sid) + 1) % 12]
        boundary = next(r for r in geometry['boundary_crosswalk'] if r['guided_between'] == [sid, successor])
        candidates = boundary['fresh_shared_boundary_candidates']
        later = [follow[c['id']] for c in candidates if c['id'] in follow]
        order_rows.append({'from_locator': loc, 'to_locator': bysector[successor],
                           'geometric_neighborhood_adjacency_reported': True,
                           'boundary_crosswalk_original': boundary, 'later_boundary_followup': later,
                           'complete_radial_divider_certified_by_this_consolidation': False,
                           'boundary_note': 'Later follow-up retains NA for full divider continuity.' if later else 'Original observations retained; this consolidation adds no independent ink-trace certification.',
                           'historical_reading_order': None})
    assert [r['locator'] for r in role_rows] == FIXED
    assert len(order_rows) == 12 and order_rows[-1]['to_locator'] == FIXED[0]
    assert sum(bool(r['later_boundary_followup']) for r in order_rows) == 3
    assert all(r['image_word_boundary_certified'] is False and r['image_character_identity_certified'] is False for r in transcription_rows)
    result = {'schema': 'f67_three_measurement_tables_v1',
              'scope': 'Already published observations consolidated; no new image reading or scoring',
              'inputs': frozen['files'], 'fixed_targets': FIXED,
              'A_working_graphical_roles': role_rows,
              'B_transcription_eligibility': transcription_rows,
              'C_geometric_order_and_boundary_evidence': order_rows,
              'all_74_context_loci_original': inventory['records'],
              'context_counts_original': inventory['counts'],
              'central_ring_guided_original': guided['central_ring'],
              'central_crosswalk_original': geometry['central_crosswalk'],
              'central_image_original': image['central_writing'],
              'image_ambiguity_inventory_original': image['ambiguity_and_crossing_inventory'],
              'outer_red_crosswalk_original': geometry['outer_red_crosswalk'],
              'O06_followup_original': source['O06_findings'],
              'cycle_original': geometry['cycle'],
              'gate': geometry['gate'], 'gate_reasons_original': geometry['gate_reasons'],
              'new_image_observations': False, 'new_text_matches_computed': False,
              'new_cyclic_scores_computed': False,
              'limits': ['Source agreement is not independent paleographic certification.',
                         'Geometric traversal is not historical text order or complete sector partition.',
                         'No per-target semantic name or uniquely defined label-specific body follows from these tables.',
                         'The six-source public record is a documentation synthesis, not another independent observer.']}
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))

if __name__ == '__main__':
    main()
