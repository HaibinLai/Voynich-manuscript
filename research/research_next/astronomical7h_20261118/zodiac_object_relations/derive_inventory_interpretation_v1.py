"""Join frozen region IDs; do not infer names, words, ownership, or image truth."""
from pathlib import Path
from collections import Counter
import hashlib
import json

HERE = Path(__file__).resolve().parent
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def derive():
    inputs = read(HERE / 'inventory_interpretation_input_freeze_v1.json')
    for row in inputs['files']:
        assert sha(HERE / row['path']) == row['sha256']
    aggregate = read(HERE / 'aggregation_v1.json')
    crosswalk = read(HERE.parent / 'central_annotation_sources/crosswalk_observations_v1.json')
    assert aggregate['all_twelve_frozen_inputs_present'] and not aggregate['structural_issues']
    annotations = {r['region_uid']: r for r in crosswalk['observations'] if r['match_status'] == 'located_candidate'}
    singles, partials, rows = [], [], []
    views = Counter()
    for panel in aggregate['panels']:
        view_modes = Counter(v['display_mode'] for v in panel['full_frozen_report']['view_receipts'])
        views.update(view_modes)
        rows.append({'panel': panel['panel'], 'counts': panel['counts'], 'view_modes': dict(sorted(view_modes.items()))})
        for row in panel['text_rows']:
            if row['observation']['layout_association'] == 'single_layout_candidate':
                uid = row['region_uid']
                singles.append({'region_uid': uid, 'panel': panel['panel'],
                                'candidate_object_ids': row['observation']['candidate_object_ids'],
                                'also_external_annotation_location_candidate': uid in annotations,
                                'original_seed_box_xyxy': row['original_seed_record']['original_box_xyxy'],
                                'not_a_semantic_ownership_certificate': True})
        for edge in panel['full_frozen_report']['relation_edges']:
            if edge['edge_kind'] == 'text_to_object' and edge['evidence_level'] == 'P':
                partials.append({'panel': panel['panel'], 'edge_uid': edge['edge_uid'],
                                 'source_uid': edge['source_uid'], 'target_uid': edge['target_uid'],
                                 'source_also_external_annotation_location_candidate': edge['source_uid'] in annotations,
                                 'original_edge': edge})
    return {'schema': 'zodiac_inventory_interpretation_v1',
            'input_freeze_sha256': sha(HERE / 'inventory_interpretation_input_freeze_v1.json'),
            'panels': rows, 'view_modes': dict(sorted(views.items())),
            'single_layout_regions': singles,
            'single_layout_count': len(singles),
            'single_layout_annotation_candidate_overlap_count': sum(r['also_external_annotation_location_candidate'] for r in singles),
            'other_single_layout_count': sum(not r['also_external_annotation_location_candidate'] for r in singles),
            'partial_text_edges': partials,
            'partial_text_edges_from_annotation_candidates': sum(r['source_also_external_annotation_location_candidate'] for r in partials),
            'limits': ['This is a post-observation exact-ID join, not a preregistered unknown-result test.',
                       'Annotation candidates come from source-informed visual location, not independently certified transcriptions.',
                       'All single-layout categories are original observer labels; different target granularity remains possible.',
                       'No single-layout entries outside these candidates does not prove absence of historical text-object references.',
                       'Recorded body-star edges do not establish word meanings or text leaders.',
                       'Receipt counts include repeated overlapping views of8 canvases from4 physical leaves, not independent historical samples.']}


if __name__ == '__main__':
    print(json.dumps(derive(), ensure_ascii=False, indent=2))
