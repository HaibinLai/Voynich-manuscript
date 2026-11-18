"""Read-only adapter for a separately approved conditional wind experiment.

--validate-only assembles input objects without constructing any match matrix.
Default execution requires a frozen approval binding input, engine and adapter.
No network, input mutation, normalization or editorial decision occurs here.
"""
from pathlib import Path
from fractions import Fraction
from dataclasses import asdict, is_dataclass
import argparse
import hashlib
import json
import sys

HERE = Path(__file__).resolve().parent
WINDOW = HERE.parent
ENGINE = WINDOW / 'wind_calibration_engine/engine_v1.py'
sys.path.insert(0, str(ENGINE.parent))
from engine_v1 import Name, Unknown, Block, BodyGroup, evaluate_twelve

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text())

def serial(value):
    if isinstance(value, Fraction):
        return {'numerator': value.numerator, 'denominator': value.denominator, 'exact': str(value)}
    if is_dataclass(value):
        return serial(asdict(value))
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    return value

def assemble(leaf):
    assert [r['index'] for r in leaf['labels']] == list(range(12))
    assert [r['index'] for r in leaf['groups']] == list(range(12))
    names = {r['id']: Name(tuple(r['tokens'])) for r in leaf['labels']}
    group_by_catalogue = {r['catalogue_id']: r for r in leaf['groups']}
    assert len(names) == len(group_by_catalogue) == 12
    pairing = {}
    for label in leaf['labels']:
        group = group_by_catalogue[label['catalogue_id']]
        assert label['visual_id'] == group['visual_id']
        link = next(r for r in leaf['crosswalk'] if r['catalogue_position_id'] == label['catalogue_id'])
        assert link['name_field_id'] == label['id'] and link['description_field_id'] == group['id']
        assert link['qualified_visual_position_id'] == label['visual_id']
        pairing[label['id']] = group['id']
    groups, item_maps = {}, {}
    for group in leaf['groups']:
        blocks, block_maps = [], []
        for block in group['blocks']:
            items, item_map = [], []
            for segment in block['segments']:
                if segment['state'] == 'known_conditional_text':
                    assert isinstance(segment['tokens'], list)
                    for offset, token in enumerate(segment['tokens']):
                        items.append(token)
                        item_map.append({'kind': 'known_conditional_token', 'segment_id': segment['id'],
                                         'segment_token_index': offset, 'token': token,
                                         'source_interval': segment['source_interval'], 'source_field_id': group['id']})
                else:
                    assert segment['state'] == 'unknown_content' and segment['tokens'] is None
                    items.append(Unknown(segment['unknown_id']))
                    item_map.append({'kind': 'unknown_barrier', 'segment_id': segment['id'], 'unknown_id': segment['unknown_id']})
            blocks.append(Block(tuple(items)))
            block_maps.append({'block_id': block['id'], 'items': item_map})
        groups[group['id']] = BodyGroup(tuple(blocks))
        item_maps[group['id']] = block_maps
    cycle = tuple(r['id'] for r in leaf['labels'])
    return names, groups, cycle, pairing, item_maps

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    frozen = read(HERE / 'input_freeze_v1.json')
    for row in frozen['files']:
        assert sha(HERE / row['path']) == row['sha256']
    data = read(HERE / 'input_v1.json')
    engine_frozen = read(ENGINE.parent / 'output_freeze_v1.json')
    engine_rows = engine_frozen.get('files', engine_frozen.get('outputs'))
    engine_row = next(r for r in engine_rows if Path(r['path']).name == ENGINE.name)
    assert sha(ENGINE) == engine_row['sha256']
    assembled = [(regime['id'], leaf['folio'], assemble(leaf)) for regime in data['regimes'] for leaf in regime['leaves']]
    if args.validate_only:
        print(json.dumps({'scope': 'adapter assembly only; no matrix or score constructed', 'input_sha256': sha(HERE / 'input_v1.json'),
                          'cases': [{'regime': regime, 'folio': folio, 'names': len(parts[0]), 'groups': len(parts[1]),
                                     'blocks': sum(len(g.blocks) for g in parts[1].values()),
                                     'unknown_barriers': sum(isinstance(x, Unknown) for g in parts[1].values() for b in g.blocks for x in b.items)}
                                    for regime, folio, parts in assembled]}, ensure_ascii=False, indent=2))
        return
    approval = read(HERE / 'execution_approval_v1.json')
    assert approval['authorized'] is True and approval['scope'] == 'conditional_catalogue_with_measurement_unknowns_only'
    for key, path in [('input_sha256', HERE / 'input_v1.json'), ('engine_sha256', ENGINE), ('adapter_sha256', Path(__file__)),
                      ('contract_sha256', HERE / 'input_contract_v1.txt')]:
        assert approval[key] == sha(path), key
    assert sha(HERE / approval['review_file']) == approval['review_sha256']
    results = []
    for regime, folio, (names, groups, cycle, pairing, item_maps) in assembled:
        evaluated = evaluate_twelve(names, groups, cycle, pairing)
        matrix = evaluated['matrix']
        cells, unknown_cells = [], {}
        for i, row in enumerate(matrix.cells):
            for j, cell in enumerate(row):
                body_id = matrix.self_paired_body_ids_in_cycle[j]
                witnesses = []
                for block_index, start, end in cell.known_occurrences:
                    block_map = item_maps[body_id][block_index]
                    tokens = block_map['items'][start:end]
                    assert all(t['kind'] == 'known_conditional_token' for t in tokens)
                    witnesses.append({'block_id': block_map['block_id'], 'item_interval': [start, end], 'source_items': tokens})
                if cell.value is None:
                    for identity in cell.unknown_identities:
                        unknown_cells.setdefault(identity, []).append([i, j])
                cells.append({'row': i, 'column': j, 'name_id': matrix.name_ids_in_cycle[i], 'body_id': body_id,
                              'value': cell.value, 'reason': cell.reason, 'unknown_identities': cell.unknown_identities,
                              'witnesses': witnesses})
        results.append({'regime': regime, 'folio': folio, 'engine_output': evaluated, 'cell_evidence': cells,
                        'engine_item_to_source_map': item_maps, 'unknown_to_unresolved_matrix_cells': unknown_cells,
                        'unknown_dependency_note': 'One source unknown can affect several different name cells. The engine shared_unknown_identities field counts repeated placeholders in body inputs only; it does not enumerate all matrix dependencies.',
                        'image_full_transcription_gate': 'NOT_READY'})
    print(json.dumps(serial({'schema': 'wind_conditional_results_v1', 'input_sha256': sha(HERE / 'input_v1.json'),
                             'execution_approval_sha256': sha(HERE / 'execution_approval_v1.json'),
                             'scope': approval['scope'], 'results': results,
                             'voynich_text_scoring_executed': False, 'glyph_or_semantic_certification': False}), ensure_ascii=False, indent=2, allow_nan=False))

if __name__ == '__main__':
    main()
