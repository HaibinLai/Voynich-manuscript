#!/usr/bin/env python3
"""Assemble explicit manual per-ID decisions and unchanged source citations.
No role is inferred from words, band labels, object counts, or coordinates.
"""
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

R = Path(__file__).resolve().parents[6]
B = R / 'research/research_next/astronomical7h_20261118/zodiac_object_relations'
O = B / 'block_role_ledger/circle_spatial_observer'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text())
def dump(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
def main():
    assert not (O / 'output_freeze_v1.json').exists(), 'Frozen output must not be overwritten'
    inp = read(O / 'input_exposure_v1.json')
    for x in inp['files']:
        assert sha(R / x['path']) == x['sha256']
    add = read(O / 'exchange_input_addendum_v1.json')['extra_input']
    assert sha(R / add['path']) == add['sha256']
    clarification = read(O / 'clarification_input_addendum_v1.json')
    for item in clarification['files']:
        assert sha(R / item['path']) == item['sha256']
    seed_path = B / 'seed_roster_v1.json'
    seed = read(seed_path)
    panels = {p['panel']: p for p in seed['panels']}
    decisions = read(O / 'manual_decisions_v1.json')['decisions']
    role_map = {'P': 'annular_figure_field_short_writing', 'A': 'continuous_annular_writing_course', 'C': 'central_scene_annotation_field', 'X': 'external_upper_open_arc_field', 'M': 'page_margin_writing_field'}
    status_map = {'S': 'supported_for_stated_scope', 'N': 'NA', 'C': 'contradicted_for_stated_scope', 'O': 'not_in_predeclared_domain'}
    scope_map = {'F': 'full_window', 'P': 'partial_window'}
    # Explicitly selected contextual record pointers, read with each panel.
    # These only assemble evidence references for manual decisions.
    contexts = {
        'f70v1': {'P': [7, 8], 'C': [0, 1], 'M': [3]},
        'f72r2': {'P': [8, 9, 10], 'U': [4, 9], 'X': [0, 8], 'C': [1, 10]},
        'f72v2': {'P': [6, 7, 8], 'U': [7], 'A': [7], 'C': [0, 8], 'M': [1]},
        'f73r': {'P': [7, 8, 9], 'X': [1, 7], 'C': [0, 9], 'M': [2]},
    }
    # These are explicit per-ID, source-supported extent notes, not rules.
    incomplete = {
        'f72r2:ZI08': {'state': 'no', 'sides': ['unknown_direction'], 'detail': 'The fixed box samples part of a longer oblique cluster; original source gives no exact clipped side. Outside continuation is not inserted into the unit.'},
        'f72v2:ZO13': {'state': 'no', 'sides': ['top', 'bottom'], 'detail': 'Original fact explicitly describes circumferential continuation above and below; this is a sampled course, not a whole inscription.'},
        'f72v2:ZO14': {'state': 'no', 'sides': ['unknown_direction'], 'detail': 'Original fact identifies a section of the annular course; exact crossed sides are not specified.'},
    }
    ink_uncertain = {'f72v2:ZI01', 'f73r:ZO01', 'f73r:ZO02', 'f73r:ZI08', 'f73r:ZE01', 'f73r:ZC01'}
    field_boundary_NA = {'f72r2:ZO10', 'f72r2:ZO11', 'f72r2:ZO14'}
    rows = []
    for dec in decisions:
        panel = dec['panel']; uid = dec['region_uid']; role = dec['role_code']
        report_path = B / 'circle_spatial_observer' / panel / 'observer_report_v1.json'
        report = read(report_path)
        ti, source = next((i, t) for i, t in enumerate(report['text_records']) if t['region_uid'] == uid)
        si, original = next((i, t) for i, t in enumerate(panels[panel]['text_records']) if t['region_uid'] == uid)
        pi = next(i for i, p in enumerate(seed['panels']) if p['panel'] == panel)
        scope = scope_map[dec['scope_code']]
        refs = []
        def addref(path, pointer, evidence_scope, use):
            obj = read(path)
            for token in pointer.strip('/').split('/'):
                token = token.replace('~1', '/').replace('~0', '~')
                obj = obj[int(token)] if isinstance(obj, list) else obj[token]
            refs.append({'file': str(path.relative_to(R)), 'sha256': sha(path), 'json_pointer': pointer, 'original_field_value': obj, 'evidence_scope': evidence_scope, 'interpretive_use': use})
            return len(refs) - 1
        addref(report_path, f'/text_records/{ti}/observation_facts', scope, dec['manual_scope_and_role_reason'])
        addref(report_path, f'/text_records/{ti}/text_status', scope, 'Retain the original writing/graphic status. The spatial decision uses the concrete facts at reference 0, not this enum alone.')
        addref(report_path, f'/text_records/{ti}/subgroup_candidates', 'context_only', 'All original split alternatives retained; no child replaces the fixed parent window or adds opportunities.')
        addref(report_path, f'/text_records/{ti}/candidate_object_ids', 'context_only', 'Original candidate list retained exactly; not used as a classifier or required to be singleton.')
        addref(report_path, f'/text_records/{ti}/candidate_constraints', 'context_only', 'Original evidential limits retained; neither angular proximity nor overlap is promoted to role evidence.')
        addref(report_path, f'/text_records/{ti}/limitations', 'context_only', 'Original window/ink-contour and no-leader limitations remain.')
        addref(report_path, f'/text_records/{ti}/viewed_view_ids', 'context_only', 'Source view IDs only; this coding performs no new image viewing and does not infer attention from rectangle enclosure.')
        addref(seed_path, f'/panels/{pi}/text_records/{si}', 'context_only', 'Immutable original identity, box, band and retained grouping metadata. The band defines the predeclared domain only.')
        context_ref_indices = []
        for ci in contexts[panel][role]:
            context_ref_indices.append(addref(report_path, f'/context_reviews/{ci}', 'context_only', 'Frozen panel-level field/circle/scene/margin context supporting interpretation of the specific local facts, not a rectangular ink mask or automatic per-row classification.'))
        if uid == 'f72r2:ZE04':
            context_ref_indices.append(addref(report_path, '/context_reviews/2', 'context_only', 'The fold-obscured endpoint limits recovered external context; no missing pointed outline is restored.'))
        domain = original['ring_assignment_original'] in ['outer', 'inner', 'middle']
        hypothesis = status_map[dec['hypothesis_code']]
        assert (hypothesis == 'not_in_predeclared_domain') == (not domain)
        if role == 'U':
            assert source['text_status'] == 'uncertain_or_graphic' and hypothesis == 'NA'
            presence = 'uncertain'; observed = []; candidates = ['unresolved_writing_or_graphic']
            assessment = 'record_reviewed_NA'; na = ['writing_graphic_uncertain']; mixed = None
            broad = 'NA'
        else:
            presence = 'writing_like_supported'; observed = [role_map[role]]; candidates = []
            assessment = 'record_reviewed'; na = ['field_boundary_unresolved'] if uid in field_boundary_NA else []
            mixed = False if scope == 'full_window' else None
            broad = 'supported_for_stated_scope'
        inscription = incomplete.get(uid, {'state': 'uncertain' if uid in ink_uncertain else 'not_assessed', 'sides': [], 'detail': 'Writing/graphic contact limits exact ink or inscription boundary; it is not alone a failure of the shared spatial field.' if uid in ink_uncertain else 'No complete-inscription or clipped-side assertion is imported from mere rectangle coverage.'})
        if role == 'A':
            overlap = {'confirmed_same_ink_ids': [], 'same_course_context_ids': ['f72v2:ZO14' if uid == 'f72v2:ZO13' else 'f72v2:ZO13'], 'scope': 'Two original samples are described as belonging to the middle annular course; identical ink or independent words are not asserted.'}
        else:
            overlap = {'confirmed_same_ink_ids': [], 'scope': 'No source-certified same-ink identity added. Original windows may overlap; no statistical independence inferred.'}
        conflicts = []
        if uid == 'f72v2:ZI01':
            conflicts = [{'source_ref_indices': [0], 'description': 'The same original field describes broad group separation and a possibly overlapping terminal junction. Both clauses are retained with their different extents; no vote or silent deletion resolves the terminal ink attribution.'}]
        rows.append({
            'region_uid': uid, 'panel': panel, 'canvas_id': panels[panel]['canvas_id'],
            'roster_class': original['roster_class'], 'original_box_xyxy': original['original_box_xyxy'],
            'original_band': original['ring_assignment_original'], 'primary_proposition_domain': domain,
            'assessment_status': assessment, 'whole_window_evidence_scope': scope,
            'writing_presence': presence, 'role_observed_present': observed, 'role_candidates': candidates,
            'broad_spatial_role_assessment': broad, 'mixed_roles_observed': mixed,
            'mixed_roles_limit': 'False means the observed writing group is reported in one field for this stated scope, not proof that no unobserved mark or historic function exists. Graphic contact alone is not two textual roles.',
            'field_boundary_basis': [
                {'description': dec['manual_scope_and_role_reason'], 'source_ref_indices': [0]},
                {'description': 'Frozen wider field context is retained separately from the local whole-group/partial-group claim; course envelopes do not supply exact ink masks.', 'source_ref_indices': context_ref_indices},
            ],
            'inscription_complete_in_window': inscription['state'],
            'clipped_or_continuing_sides': {'directions': inscription['sides'], 'reason': inscription['detail'], 'source_ref_indices': [0]},
            'full_block_grouping_notes': {'all_original_subgroup_alternatives': source['subgroup_candidates'], 'selected_as_replacement': None, 'scope_note': 'Fixed parent rectangle retained; all children remain contextual alternatives and are not counted as additional units.', 'source_ref_indices': [2, 7]},
            'candidate_object_ids_context_only': source['candidate_object_ids'],
            'source_refs': refs, 'conflicting_sources': conflicts,
            'primary_hypothesis_assessment': hypothesis, 'NA_reasons': na,
            'NA_explanation': dec['manual_scope_and_role_reason'] if hypothesis == 'NA' else None,
            'shared_ink_or_overlap_dependency': overlap,
            'scope_justification': dec['manual_scope_and_role_reason'],
            'source_report_record_index': ti,
        })
    expected = [t['region_uid'] for p in inp['fixed_order'] for t in panels[p]['text_records']]
    assert [r['region_uid'] for r in rows] == expected and len(rows) == 112
    required = set(read(B / 'role_contract_review/record_schema_proposal_v1.json')['required_fields'])
    ref_count = 0
    for row in rows:
        assert required <= set(row)
        for ref in row['source_refs']:
            assert sha(R / ref['file']) == ref['sha256']
            obj = read(R / ref['file'])
            for tok in ref['json_pointer'].strip('/').split('/'):
                tok = tok.replace('~1', '/').replace('~0', '~')
                obj = obj[int(tok)] if isinstance(obj, list) else obj[tok]
            assert obj == ref['original_field_value']; ref_count += 1
        assert row['original_box_xyxy'] == row['source_refs'][7]['original_field_value']['original_box_xyxy']
        assert row['candidate_object_ids_context_only'] == row['source_refs'][3]['original_field_value']
        assert row['full_block_grouping_notes']['all_original_subgroup_alternatives'] == row['source_refs'][2]['original_field_value']
        for basis in row['field_boundary_basis']:
            assert basis['source_ref_indices'] and all(0 <= i < len(row['source_refs']) for i in basis['source_ref_indices'])
        if row['writing_presence'] == 'uncertain':
            assert not row['role_observed_present'] and row['primary_hypothesis_assessment'] == 'NA'
    report = {
        'schema': 'all322_record_level_block_role_group_report_v1',
        'observer_id': 'circle_spatial_observer',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'input_freeze_sha256': sha(O / 'input_freeze_v1.json'),
        'exchange_input_addendum_sha256': sha(O / 'exchange_input_addendum_v1.json'),
        'manual_decisions_sha256': sha(O / 'manual_decisions_v1.json'),
        'execution_time_method_clarification': clarification,
        'clarification_input_addendum_sha256': sha(O / 'clarification_input_addendum_v1.json'),
        'fixed_panel_order': inp['fixed_order'], 'rows': rows,
        'summary': {'total_rows': len(rows), 'per_panel_rows': dict(Counter(r['panel'] for r in rows)), 'primary_hypothesis_status_inventory': dict(Counter(r['primary_hypothesis_assessment'] for r in rows)), 'remaining_not_evaluated_ids': [], 'status_counts_not_word_or_semantic_scores': True},
        'limits': [
            'Manual per-ID secondary coding of already exposed frozen source prose; original observer and same AI, not new image reading or blind/expert replication.',
            'No other group new classifications or new root f73r contact followup read.',
            'Complete original image windows are measurement units, not certified complete words or inscriptions.',
            'Broad spatial roles do not certify naming or unique object attachment, historical reading order, or original complete-sequence gate.',
            'Unknown writing/graphic slots remain NA, never vacuous all-components success or zero observations.',
            'A graphical contact may leave ink identity uncertain while the whole observed group still lies in one shared spatial field. This does not certify a leader.',
            'NA for field boundary uncertainty does not erase broad field support; per-row reasons specify the missing extent.',
            'All 112 IDs, boxes, candidates and subgroup alternatives retained; no outcome-based selection or changed rectangle.',
            'No scores, percentages, p-values, phase matching, transcription or language/name guesses.',
            'Root scientific review required before group aggregation/release; this is not final window acceptance.',
        ],
    }
    dump(O / 'report_v1.json', report)
    lines = ['四图112固定窗口：记录级空间角色登记 v1', '冻结输入后逐ID手工读取原事实/上下文；代码只组装引用与校验。没有新看图、其他组新编码或root新f73r补查。', '完整固定窗口不等于完整铭文；宽场角色、全框H、文字/图形性质分别记录。', '原完整标签—对象序列gate不变；以下为状态库存，不是词义分数。', '']
    for panel in inp['fixed_order']:
        lines.append(panel)
        for row in rows:
            if row['panel'] == panel:
                lines.append(row['region_uid'] + ' | ' + ','.join(row['role_observed_present'] or ['未定占位']) + ' | ' + row['whole_window_evidence_scope'] + ' | H=' + row['primary_hypothesis_assessment'] + ' | ' + row['scope_justification'])
        lines.append('')
    lines += ['112项全部保留，无not_evaluated。具体原字段、SHA、指针、证据范围、全细分与原候选见JSON。', '根须继续复核所有确定支持/反例及NA依据；本组冻结不代表发布或终点验收。']
    (O / 'report_v1.txt').write_text('\n'.join(lines) + '\n')
    dump(O / 'validation_v1.json', {'utc': datetime.now(timezone.utc).isoformat(), 'all_112_IDs_in_fixed_order': True, 'source_reference_checks': ref_count, 'all_source_hashes_and_exact_field_values_match': True, 'all_boxes_candidates_and_subgroup_alternatives_exact': True, 'all_required_schema_fields_present': True, 'uncertain_writing_not_promoted_to_supported_role_or_H': True, 'no_not_evaluated_records': True, 'validation_scope': 'Structural/source integrity checks, not automated scientific correctness or replacement for root review.'})
    print(json.dumps({'rows': len(rows), 'references': ref_count, 'statuses': report['summary']['primary_hypothesis_status_inventory']}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
