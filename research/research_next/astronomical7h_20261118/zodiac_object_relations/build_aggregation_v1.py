"""Aggregate explicit frozen reports. Record checks do not certify visual truth."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text())


def unique_map(rows, key, issues, label):
    out = {}
    for row in rows:
        ident = row[key]
        if ident in out:
            issues.append({'check': 'duplicate_id', 'location': label, 'id': ident})
        out[ident] = row
    return out


def aggregate(allow_pending=False):
    plan = read(HERE / 'aggregation_plan_freeze_v1.json')
    assert sha(HERE / 'aggregation_protocol_v1.txt') == plan['protocol_sha256']
    assert sha(HERE / 'execution_freeze_v1.json') == plan['execution_freeze_sha256']
    full_input_path = HERE / 'aggregation_input_freeze_v1.json'
    if not allow_pending:
        full_inputs = read(full_input_path)
        assert full_inputs['method_freeze_sha256'] == sha(HERE / 'aggregation_plan_freeze_v1.json')
        assert len(full_inputs['fixed_report_mapping']) == 12
        assert full_inputs['fixed_report_mapping'] == plan['fixed_report_mapping']
        for entry in full_inputs['files']:
            assert sha(HERE / entry['path']) == entry['sha256'], entry['path']
    seed = read(HERE / 'seed_roster_v1.json')
    schema = read(HERE / 'schema_v1.json')
    inputs = read(HERE / 'inputs_v1.json')
    seeds = {p['panel']: p for p in seed['panels']}
    originals = {p['canvas_id']: p for p in inputs['allowed_original_images']}
    assert [p['panel'] for p in plan['fixed_report_mapping']] == inputs['fixed_panel_order']
    issues, panels, pending, dependencies = [], [], [], []
    validator = jsonschema.Draft202012Validator(schema)

    def require(condition, check, panel, **extra):
        if not condition:
            issues.append({'check': check, 'panel': panel, **extra})

    def bind(path):
        dependencies.append({'path': str(path.relative_to(HERE)), 'sha256': sha(path)})

    for name in ['aggregation_protocol_v1.txt', 'aggregation_plan_freeze_v1.json',
                 'execution_freeze_v1.json', 'seed_roster_v1.json', 'schema_v1.json', 'inputs_v1.json']:
        bind(HERE / name)
    if not allow_pending:
        bind(full_input_path)
    for item in plan['fixed_report_mapping']:
        panel = item['panel']
        fp, rp = HERE / item['freeze_path'], HERE / item['report_path']
        if not fp.is_file() or not rp.is_file():
            pending.append(panel)
            continue
        frozen = read(fp)
        bound_report = False
        for entry in frozen['files']:
            path = fp.parent / entry['path']
            require(path.is_file(), 'frozen_file_exists', panel, file=str(path.relative_to(HERE)))
            if path.is_file():
                require(sha(path) == entry['sha256'], 'frozen_file_hash', panel,
                        file=str(path.relative_to(HERE)))
                bind(path)
                if path.resolve() == rp.resolve():
                    bound_report = sha(path) == entry['sha256']
        require(bound_report, 'report_bound_by_output_freeze', panel)
        bind(fp)
        report = read(rp)
        for error in validator.iter_errors(report):
            issues.append({'check': 'schema', 'panel': panel,
                           'path': '/'.join(map(str, error.absolute_path)), 'message': error.message})
        sp = seeds[panel]
        require(report['panel'] == panel and report['observer_id'] == item['observer'], 'panel_owner', panel)
        require(report['seed_roster_sha256'] == sha(HERE / 'seed_roster_v1.json'), 'seed_hash', panel)
        require(report['input_freeze_sha256'] == plan['execution_freeze_sha256'], 'execution_hash', panel)
        original = originals[sp['canvas_id']]
        require(report['original_sha256'] == original['sha256'], 'original_hash', panel)
        text = unique_map(report['text_records'], 'region_uid', issues, panel + '/text')
        components = unique_map(report['object_component_reviews'], 'component_uid', issues, panel + '/components')
        edges = unique_map(report['relation_edges'], 'edge_uid', issues, panel + '/edges')
        segments = unique_map(report['line_segments'], 'segment_uid', issues, panel + '/segments')
        views = unique_map(report['view_receipts'], 'view_id', issues, panel + '/views')
        seed_text = {r['region_uid']: r for r in sp['text_records']}
        seed_components = {r['component_uid']: r for r in sp['object_components']}
        require(text.keys() == seed_text.keys(), 'exact_text_id_set', panel,
                missing=sorted(seed_text.keys() - text.keys()), extra=sorted(text.keys() - seed_text.keys()))
        require(seed_components.keys() <= components.keys(), 'all_original_component_ids', panel,
                missing=sorted(seed_components.keys() - components.keys()))
        aliases = {x['component_uid'] for x in report['discovered_supplements'] if 'component_uid' in x}
        object_ids = set(components) | aliases
        for ident, row in text.items():
            require(set(row['viewed_view_ids']) <= views.keys(), 'text_view_refs', panel, id=ident)
            require(set(row.get('relation_edge_ids') or []) <= edges.keys(), 'text_edge_refs', panel, id=ident)
            require(set(row.get('candidate_object_ids') or []) <= object_ids, 'text_candidate_refs', panel, id=ident)
            if row['review_status'] in ('reviewed', 'NA_after_review'):
                require(bool(row['viewed_view_ids']) and bool(row['completion_or_NA_reason']), 'reviewed_text_has_receipt_reason', panel, id=ident)
        for ident, row in components.items():
            require(set(row['viewed_view_ids']) <= views.keys(), 'component_view_refs', panel, id=ident)
            require(set(row.get('related_edge_ids') or []) <= edges.keys(), 'component_edge_refs', panel, id=ident)
            if row['review_status'] in ('reviewed', 'NA_after_review'):
                require(bool(row['viewed_view_ids']) and bool(row['completion_or_NA_reason']), 'reviewed_component_has_receipt_reason', panel, id=ident)
        for ident, row in edges.items():
            require(row['source_uid'] in (set(text) | object_ids), 'edge_source_ref', panel, id=ident)
            require(row['target_uid'] in object_ids, 'edge_target_ref', panel, id=ident)
            require(set(row['segment_ids']) <= segments.keys(), 'edge_segment_refs', panel, id=ident)
            require(set(row['view_ids']) <= views.keys(), 'edge_view_refs', panel, id=ident)
        for ident, row in segments.items():
            require(set(row['view_ids']) <= views.keys(), 'segment_view_refs', panel, id=ident)
        width, height = original['dimensions_px']
        for ident, row in views.items():
            require(row['original_sha256'] == original['sha256'], 'view_original_hash', panel, id=ident)
            box = row['crop_xyxy_original']
            if box is not None:
                x1, y1, x2, y2 = box
                require(0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height, 'view_bounds', panel, id=ident)
                size = [x2 - x1, y2 - y1]
                if row['rotation_degrees'] in (90, 270):
                    size.reverse()
                require(row['native_dimensions_px'] == size, 'view_native_dimensions', panel, id=ident)
        missing_review = sorted([ident for ident, row in {**text, **components}.items()
                                 if row['review_status'] in ('not_reviewed', 'in_progress')])
        require(missing_review == sorted(report['remaining_not_reviewed_ids']), 'unreviewed_id_declaration', panel)
        by_kind = {}
        for kind in ['text_to_object', 'body_to_pointed', 'other_graphic_connection']:
            by_kind[kind] = dict(sorted(Counter(e['evidence_level'] for e in edges.values() if e['edge_kind'] == kind).items()))
        counts = {
            'fixed_text_records': len(seed_text), 'text_records_retained': len(text),
            'original_components': len(seed_components),
            'original_components_retained': len(seed_components.keys() & components.keys()),
            'original_fine_alternative_units_retained': len(sp['fine_alternatives_original']),
            'additional_component_reviews': len(components.keys() - seed_components.keys()),
            'declared_supplement_aliases': len(aliases),
            'view_receipts': len(views), 'not_reviewed_or_in_progress': len(missing_review),
            'text_review_status': dict(sorted(Counter(x['review_status'] for x in text.values()).items())),
            'text_status': dict(sorted(Counter(str(x['text_status']) for x in text.values()).items())),
            'layout_association': dict(sorted(Counter(str(x['layout_association']) for x in text.values()).items())),
            'line_visibility_state': dict(sorted(Counter(x['line_visibility_state'] for x in text.values()).items())),
            'edges_by_kind_and_grade': by_kind,
        }
        rows = []
        for ident, source in seed_text.items():
            observed = text.get(ident)
            related = [e for e in edges.values() if e['edge_kind'] == 'text_to_object' and e['source_uid'] == ident]
            rows.append({'region_uid': ident, 'original_seed_record': source,
                         'observation': observed, 'text_edge_level_set': sorted({e['evidence_level'] for e in related}),
                         'text_edges': related})
        panels.append({'panel': panel, 'observer': item['observer'], 'counts': counts,
                       'original_image': {k: original[k] for k in ['canvas_id', 'official_url', 'sha256', 'dimensions_px']},
                       'report_path': item['report_path'], 'report_sha256': sha(rp),
                       'freeze_path': item['freeze_path'], 'freeze_sha256': sha(fp),
                       'text_rows': rows, 'full_original_seed': sp, 'full_frozen_report': report})
    if pending and not allow_pending:
        raise RuntimeError('Full twelve frozen reports not yet available: ' + ', '.join(pending))
    totals = {key: sum(p['counts'][key] for p in panels) for key in
              ['fixed_text_records', 'text_records_retained', 'original_components',
               'original_components_retained', 'additional_component_reviews',
               'original_fine_alternative_units_retained', 'declared_supplement_aliases',
               'view_receipts', 'not_reviewed_or_in_progress']}
    if not pending:
        require(totals['fixed_text_records'] == 322, 'full_text_denominator', 'all_twelve')
        require(totals['original_components'] == 606, 'full_component_denominator', 'all_twelve')
        require(totals['original_fine_alternative_units_retained'] == 358,
                'full_fine_alternative_denominator', 'all_twelve')
    grouped = {}
    for key in ['text_review_status', 'text_status', 'layout_association', 'line_visibility_state']:
        c = Counter()
        for panel in panels:
            c.update(panel['counts'][key])
        grouped[key] = dict(sorted(c.items()))
    grouped['edges_by_kind_and_grade'] = {}
    for kind in ['text_to_object', 'body_to_pointed', 'other_graphic_connection']:
        c = Counter()
        for panel in panels:
            c.update(panel['counts']['edges_by_kind_and_grade'][kind])
        grouped['edges_by_kind_and_grade'][kind] = dict(sorted(c.items()))
    return {'schema': 'zodiac_object_relations_aggregation_v1',
            'method_freeze_sha256': sha(HERE / 'aggregation_plan_freeze_v1.json'),
            'fixed_panel_order': inputs['fixed_panel_order'], 'pending_panels': pending,
            'all_twelve_frozen_inputs_present': not pending, 'structural_issues': issues,
            'all_structural_checks_passed': not issues, 'totals': totals, 'grouped_counts': grouped,
            'panels': panels, 'dependencies': list({x['path']: x for x in dependencies}.values()),
            'semantic_qualification': 'not_evaluated_by_record_aggregation',
            'limits': ['A complete checklist is not a confirmed text role or a decipherment.',
                       'Edge counts are candidate relations, not word counts or independent observations.',
                       'Source reports and root repeated observations remain separate; disagreements are not voted away.',
                       'View receipts report tool displays; schema and hash checks alone do not prove visual correctness.',
                       'No text strings, matching scores, phonetic values or names were inferred.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--allow-pending', action='store_true')
    args = parser.parse_args()
    print(json.dumps(aggregate(args.allow_pending), ensure_ascii=False, indent=2))
