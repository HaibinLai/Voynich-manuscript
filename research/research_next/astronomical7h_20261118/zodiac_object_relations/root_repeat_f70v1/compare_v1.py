"""Compare frozen observations, not the truth of their image interpretations."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OTHER = HERE.parent / 'circle_spatial_observer' / 'f70v1'


def read_verified(path, expected):
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected, str(path)
    return json.loads(raw)


def main():
    own_freeze = json.loads((HERE / 'own_output_freeze_v1.json').read_text())
    for name, digest in own_freeze['files'].items():
        assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest
    other_freeze = json.loads((OTHER / 'output_freeze_v1.json').read_text())
    for entry in other_freeze['files']:
        assert hashlib.sha256((OTHER / entry['path']).read_bytes()).hexdigest() == entry['sha256']
    own = read_verified(HERE / 'root_observations_v1.json',
                        '33ac84aa8105a746ab083e78c441f33df62a24efc456d3f2f3d54680f9dff0d6')
    other = read_verified(OTHER / 'observer_report_v1.json',
                          '92a373b4b941c63b09134818d27257c02b73cb08c24d3270ffcedfcd8047eb73')
    own_body = {x['id']: x for x in own['observations'] if x['kind'] == 'body_to_pointed'}
    other_body = {x['edge_uid'].split(':')[1]: x for x in other['relation_edges']
                  if x['edge_kind'] == 'body_to_pointed'}
    assert own_body.keys() == other_body.keys()
    body_rows = []
    for ident, row in own_body.items():
        peer = other_body[ident]
        body_rows.append({'id': ident, 'root_grade': row['evidence_grade'],
                          'observer_grade': peer['evidence_level'],
                          'same_grade': row['evidence_grade'] == peer['evidence_level'],
                          'root_fact': row['visible_fact'],
                          'root_followup': row.get('followup'),
                          'observer_facts': peer['observed_endpoint_facts']})
    own_text = {x['id']: x for x in own['observations'] if x['kind'] == 'text'}
    other_text = {x['region_uid'].split(':')[-1]: x for x in other['text_records']}
    assert own_text.keys() == other_text.keys()
    text_rows = [{'id': ident, 'root_layout': row['layout'],
                  'observer_layout': other_text[ident]['layout_association'],
                  'same_layout_category': row['layout'] == other_text[ident]['layout_association']}
                 for ident, row in own_text.items()]
    result = {
        'scope': 'Complete first-delivered panel f70v1 repeat; no new image observation in this comparison.',
        'root_own_freeze_utc': own_freeze['utc'],
        'root_actual_display_count': len(own['receipts']) + len(own['supplemental_receipts']),
        'observer_actual_display_count': len(other['view_receipts']),
        'body_comparison': body_rows,
        'text_layout_category_comparison': text_rows,
        'body_grade_disagreements': [x['id'] for x in body_rows if not x['same_grade']],
        'same_aggregate_counts_do_not_prove_same_edges': True,
        'interpretation_notes': [
            'O04: root E refers to body/shoulder-to-star contact; observer P requires a more specifically resolved hand endpoint. Preserve both and clarify endpoint-type granularity before reuse.',
            'I04: root P retains uncertainty at overlapping star-side contour; observer E reports a traceable arc unaffected by nearby brown damage. No consensus or correction is imposed.',
            'O02: both P, but root rotated follow-up moved concern from body endpoint to faint stem continuity. Same grade does not mean identical observation facts.',
            'I05: both E, but root calls the striped extension head/hair-adjacent and observer calls it a limb. Only graphic continuity is shared; anatomy is not resolved.',
            'Central short writing: both single_layout_candidate categories, but root restricts this to the animal scene; observer names a central-figure component. Identical category does not establish identical target granularity.',
            'All17 layout categories agree, but the root record does not enumerate the same46 component-level text edges. Those edge sets have not been independently reproduced.',
        ],
        'decision': 'Retain both frozen reports and the two E/P disagreements. Neither report certifies short text as an object name; no text-function gate or scoring is unlocked.',
        'limitations': [
            'Root knew aggregate counts and brief ZI02/I03 hints before viewing; not blind.',
            'Same AI family and same source photograph; not independent expert replication.',
            'Agreement measures record consistency, not accuracy or a probability of meaning.',
            'No detailed-report-driven revision to the frozen root observations.',
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
