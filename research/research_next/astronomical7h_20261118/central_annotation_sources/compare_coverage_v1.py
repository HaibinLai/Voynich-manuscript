"""Compare two frozen observation records, not the correctness of their image judgments."""
from pathlib import Path
from collections import Counter
import hashlib
import json

HERE = Path(__file__).resolve().parent
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text())


def compare():
    manifest = read(HERE / 'coverage_comparison_input_freeze_v1.json')
    for item in manifest['files']:
        assert sha(HERE / item['path']) == item['sha256']
    root = read(HERE / 'crosswalk_observations_v1.json')
    peer = read(HERE / 'independent_coverage_review/observer_report_v1.json')
    a = {r['region_uid']: r for r in root['observations']}
    b = {r['region_uid']: r for r in peer['records']}
    assert len(a) == len(b) == 13 and a.keys() == b.keys()
    rows = []
    for uid, r in a.items():
        s = b[uid]
        assert r['original_seed_box_xyxy'] == s['original_box_xyxy']
        coverage_a = {True: 'yes', False: 'no', None: 'uncertain'}[r['original_box_covers_candidate']]
        # Root's frozen notes explicitly distinguish this one pale central run.
        appearance_a = 'voynich_like' if uid == 'f70v2:ZC02' else 'ordinary_alphabet_like'
        rows.append({'region_uid': uid, 'panel': r['panel'],
                     'original_box_xyxy': r['original_seed_box_xyxy'],
                     'root_original_coverage': coverage_a,
                     'independent_coverage': s['coverage_yes_no_uncertain'],
                     'coverage_agrees': coverage_a == s['coverage_yes_no_uncertain'],
                     'root_appearance_from_explicit_frozen_notes': appearance_a,
                     'independent_appearance': s['visible_type'],
                     'appearance_agrees': appearance_a == s['visible_type'],
                     'root_observation_facts': r['observed_fact'],
                     'root_coverage_fact': r.get('coverage_observed_fact'),
                     'independent_stroke_evidence': s['stroke_evidence'],
                     'independent_clipped_directions': s['clipped_stroke_directions'],
                     'independent_uncertainties': s['uncertainties'],
                     'adjudicated_truth': None})
    return {'schema': 'central_annotation_coverage_comparison_v1',
            'input_freeze_sha256': sha(HERE / 'coverage_comparison_input_freeze_v1.json'),
            'rows': rows,
            'root_coverage_counts': dict(sorted(Counter(r['root_original_coverage'] for r in rows).items())),
            'independent_coverage_counts': dict(sorted(Counter(r['independent_coverage'] for r in rows).items())),
            'coverage_disagreement_ids': [r['region_uid'] for r in rows if not r['coverage_agrees']],
            'appearance_disagreement_ids': [r['region_uid'] for r in rows if not r['appearance_agrees']],
            'same_no_ids': [r['region_uid'] for r in rows if r['root_original_coverage'] == r['independent_coverage'] == 'no'],
            'same_yes_ids': [r['region_uid'] for r in rows if r['root_original_coverage'] == r['independent_coverage'] == 'yes'],
            'root_view_count': len(root['view_receipts']),
            'independent_view_count': len(peer['view_receipts']),
            'root_exact_seed_crops_viewed': 4, 'independent_exact_seed_crops_viewed': 13,
            'limits': ['Root viewed 13 padded details and 12 contexts before selecting 4 exact-seed crops; peer viewed all13 exact-seed crops.',
                       'Both are exposed same-AI observations, not blind independent historical evidence.',
                       'Equal coverage category can still hide disagreements about particular directions or stroke identities.',
                       'No vote resolves image truth; all original observations are retained.',
                       'Cropped stroke does not establish a missing whole letter or a word meaning.']}


if __name__ == '__main__':
    print(json.dumps(compare(), ensure_ascii=False, indent=2))
