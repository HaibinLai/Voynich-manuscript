"""Copy the complete frozen nine-location history; do not classify image content."""
import hashlib
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PREVIOUS = 'research/research_next/semantic7h_20261118/'


def main():
    freeze = json.loads((HERE / 'input_freeze_v1.json').read_text())
    expected = {item['path']: item['sha256'] for item in freeze['sources']}
    paths = {
        'roster': PREVIOUS + 'design/repeated_label_feasibility/fixed_nine_roster_v1.json',
        'first_guided_observation': PREVIOUS + 'visual/repeated_label_localization/review_v1.json',
        'second_guided_observation': PREVIOUS + 'visual/repeated_label_localization/guided_second_review_v1.json',
        'prior_rectangle_check': PREVIOUS + 'visual/repeated_label_localization/guided_second_root_geometry_check_v1.json',
    }
    documents = {}
    indexed = {}
    for name, path in paths.items():
        raw = (ROOT / path).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected[path], path
        documents[name] = json.loads(raw)
        key = 'rectangles' if name == 'prior_rectangle_check' else 'records'
        records = documents[name][key]
        assert len(records) == 9
        assert len({row['locator'] for row in records}) == 9
        indexed[name] = {row['locator']: (index, row) for index, row in enumerate(records)}
    session = json.loads((HERE / 'session_v1.json').read_text())
    locators = session['fixed_nine_loci']
    assert len(locators) == len(set(locators)) == 9
    assert all(set(rows) == set(locators) for rows in indexed.values())
    rows = []
    for locator in locators:
        source_records = {}
        for name, entries in indexed.items():
            index, original = entries[locator]
            key = 'rectangles' if name == 'prior_rectangle_check' else 'records'
            source_records[name] = {
                'source': paths[name],
                'sha256': expected[paths[name]],
                'json_pointer': f'/{key}/{index}',
                'original_record': original,
            }
        roster = indexed['roster'][locator][1]
        rows.append({
            'locator': locator,
            'known_transcription_label': roster['cluster_word'],
            'physical_leaf': roster['physical_leaf'],
            'historical_sources': source_records,
            'current_window_measurement_qualification': 'NOT_YET_ASSESSED',
            'current_window_morphology_score': None,
            'scope': 'Full old records copied verbatim as JSON values; no new image reading or automatic scientific judgment.',
        })
    pairs = []
    for left, right in itertools.combinations(rows, 2):
        pairs.append({
            'left': left['locator'], 'right': right['locator'],
            'leaf_pair': sorted([left['physical_leaf'], right['physical_leaf']]),
            'cross_physical_leaf': left['physical_leaf'] != right['physical_leaf'],
            'same_source_transcription_label': left['known_transcription_label'] == right['known_transcription_label'],
            'current_window_morphology_score': None,
        })
    cross = [pair for pair in pairs if pair['cross_physical_leaf']]
    assert len(pairs) == 36 and len(cross) == 27
    assert sum(pair['same_source_transcription_label'] for pair in cross) == 5
    result = {
        'schema': 'complete_nine_location_history_snapshot_v1',
        'scope': 'Historical evidence and fixed pair opportunities only; not a new scientific result.',
        'source_exposure': 'All label identities and both previous guided reports are already known to root and collaborating AI agents.',
        'rows': rows, 'all_pairs': pairs,
        'pair_dependence': 'Pairs share locations and four physical leaves. f99r/f99v are one leaf. Counts are not independent sample sizes.',
        'prior_text_image_geometry_note': 'Old rectangle intersections are copied, not interpreted as intersections of actual ink. Prior claims and later corrections are both retained.',
        'new_image_observations': 0, 'new_morphology_scores': 0,
        'new_semantic_claims': False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
