"""Assemble the frozen conditional input; no label/body matching or scoring.

Only stdout is written. Editorial unknowns are barriers, and the extra physical
f2r.P07 block is retained. Catalogue IDs are never treated as image IDs.
"""
from pathlib import Path
import hashlib
import json
import re
import unicodedata

HERE = Path(__file__).resolve().parent
WINDOW = HERE.parent
ROOT = WINDOW.parents[2]
EXPECTED_UNKNOWN = {'f1v.description.C11', 'f2r.description.C01', 'f2r.description.C06', 'f2r.description.C12'}

def load(path):
    return json.loads(path.read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def normalize(text):
    value = unicodedata.normalize('NFC', text).translate(str.maketrans('ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'))
    tokens = [s for s in re.split(r'''[\s.,;:!?"'‘’“”]+''', value) if s]
    assert all(all(c.isalpha() for c in token) for token in tokens), ('Unclassified character in retained segment', text)
    return tokens

def main():
    dependencies = [
        'wind_calibration_editorial/editorial_ledger_v2.json',
        'wind_calibration_editorial/id_crosswalk_v2.json',
        'wind_calibration_alignment/alignment_v1.json',
        'wind_calibration_p07/observation_v1.json',
        'wind_calibration_p07/report_v1.txt',
    ]
    for directory, freeze_name in [
        ('wind_calibration_editorial', 'output_freeze_v2.json'),
        ('wind_calibration_alignment', 'report_freeze_v1.json'),
        ('wind_calibration_p07', 'report_freeze_v1.json'),
    ]:
        frozen = load(WINDOW / directory / freeze_name)
        rows = frozen.get('files', frozen.get('outputs'))
        for relative in [p for p in dependencies if p.startswith(directory + '/')]:
            path = WINDOW / relative
            match = [r for r in rows if r['path'] in {path.name, str(path.relative_to(ROOT))}]
            assert len(match) == 1 and sha(path) == match[0]['sha256'], relative
    assert sha(HERE / 'input_contract_v1.txt') == load(HERE / 'contract_freeze_v1.json')['sha256']
    editorial = load(WINDOW / dependencies[0])
    mapping = load(WINDOW / dependencies[1])
    rows = {r['id']: r for r in editorial['rows']}
    assert len(rows) == 48
    unknown_rows = {r['id'] for r in rows.values() if r['field_role'] == 'description' and r['E0']['text'] is None}
    assert unknown_rows == EXPECTED_UNKNOWN
    changed_names = {r['id'] for r in rows.values() if r['field_role'] == 'outer_latin_name' and r['S1'].get('text') != r['E0'].get('text')}
    assert changed_names == {'f1v.outer_latin_name.C08'}
    regimes = []
    for regime in ['E0', 'S1']:
        leaves = []
        for folio in ['f1v', 'f2r']:
            crosswalk = sorted([r for r in mapping['records'] if r['folio'] == folio], key=lambda r: r['catalogue_ordinal'])
            assert [r['catalogue_ordinal'] for r in crosswalk] == list(range(1, 13))
            assert len({r['qualified_visual_position_id'] for r in crosswalk}) == 12
            labels, groups = [], []
            for index, link in enumerate(crosswalk):
                name, description = rows[link['name_field_id']], rows[link['description_field_id']]
                assert name['catalogue_ordinal'] == description['catalogue_ordinal'] == link['catalogue_ordinal']
                assert name['qualified_visual_position_id'] == description['qualified_visual_position_id'] == link['qualified_visual_position_id']
                label_text = name['S1']['text'] if regime == 'S1' else name['E0']['text']
                assert label_text is not None
                labels.append({'id': name['id'], 'index': index, 'catalogue_id': link['catalogue_position_id'],
                               'visual_id': link['qualified_visual_position_id'], 'definition': 'given_catalogue_outer_component',
                               'given_text': label_text, 'tokens': normalize(label_text), 'source_field': name,
                               'image_complete_name_certified': False})
                evidence = description['E0'].get('character_evidence_segments') if description['E0']['text'] is None else None
                if evidence is None:
                    assert description['E0']['text'] == description['raw_catalogue_field']
                    evidence = [{'display_interval': [0, len(description['raw_catalogue_field'])],
                                 'raw_text': description['raw_catalogue_field'], 'state': 'retained_catalogue_characters'}]
                segments = []
                last = 0
                for ordinal, segment in enumerate(evidence):
                    a, b = segment['display_interval']
                    assert a == last and a < b <= len(description['raw_catalogue_field'])
                    assert description['raw_catalogue_field'][a:b] == segment['raw_text']
                    last = b
                    item = {'id': description['id'] + '.segment' + str(ordinal), 'source_interval': [a, b], 'source_text': segment['raw_text']}
                    if segment['state'] == 'retained_catalogue_characters':
                        item.update(state='known_conditional_text', tokens=normalize(segment['raw_text']))
                    else:
                        assert segment['state'] == 'unknown'
                        item.update(state='unknown_content', unknown_id=description['id'] + '.editorial', tokens=None,
                                    uncertainty='Shared source uncertainty; never concatenate through this barrier.')
                    segments.append(item)
                assert last == len(description['raw_catalogue_field'])
                blocks = [{'id': link['qualified_visual_position_id'] + '.main', 'content_basis': 'given_catalogue_quotation_conditional_on_source_mapping',
                           'segments': segments, 'image_full_text_certified': False}]
                if link['qualified_visual_position_id'] == 'f2r.P07':
                    assert link['catalogue_position_id'] == 'C10'
                    blocks.append({'id': 'f2r.P07.inner', 'content_basis': 'observed_extra_block_without_complete_reading',
                                   'segments': [{'id': 'f2r.P07.inner.unknown', 'state': 'unknown_content', 'tokens': None,
                                                 'unknown_id': 'f2r.P07.inner.content', 'uncertainty': 'No tentative letter fragment admitted as a scoring token.'}],
                                   'image_full_text_certified': False})
                assert len(blocks) == link['frozen_description_block_count']
                groups.append({'id': description['id'], 'index': index, 'catalogue_id': link['catalogue_position_id'],
                               'visual_id': link['qualified_visual_position_id'], 'blocks': blocks, 'source_field': description,
                               'group_definition': 'fixed_geometric_position; no claim that all blocks form one sentence'})
            assert len(labels) == len(groups) == 12
            leaves.append({'folio': folio, 'labels': labels, 'groups': groups, 'crosswalk': crosswalk,
                           'source_catalogue_direction': 'clockwise' if folio == 'f1v' else None,
                           'order_basis': 'frozen catalogue ordinal with explicit observed relative-position crosswalk',
                           'image_full_transcription_gate': 'NOT_READY'})
        assert sum(len(g['blocks']) for leaf in leaves for g in leaf['groups']) == 25
        regimes.append({'id': regime, 'leaves': leaves})
    result = {'schema': 'wind_conditional_input_v1', 'contract_sha256': sha(HERE / 'input_contract_v1.txt'),
              'inputs': [{'path': p, 'sha256': sha(WINDOW / p)} for p in dependencies],
              'source_fields': 48, 'names_per_regime': 24, 'groups_per_regime': 24, 'blocks_per_regime': 25,
              'editorial_unknown_fields': sorted(EXPECTED_UNKNOWN), 'additional_unknown_block': 'f2r.P07.inner',
              'S1_only_changed_name': 'f1v.outer_latin_name.C08', 'regimes': regimes,
              'scoring_executed': False, 'execution_authorized': False,
              'scope': 'Conditional catalogue representation with explicit measurement unknowns; not a complete image transcription.'}
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))

if __name__ == '__main__':
    main()
