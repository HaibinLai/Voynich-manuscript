#!/usr/bin/env python3
"""Read-only, standard-library rectangle replay. JSON stdout only.
All scientific inputs are frozen sibling public projections. Source strings,
source clocks and source sequence are never used for matching or ordering.
"""
from pathlib import Path
from fractions import Fraction
from collections import Counter
import hashlib
import json
import math

HERE = Path(__file__).resolve().parent
EXPECTED_FREEZE = '7cf76d2ec0c12f337a56bd8ab9534fdba785d3dacd7029e9ad01462bae03d87f'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def read(name):
    return json.loads((HERE / name).read_text())

def ratio(a, b):
    f = Fraction(a, b)
    return {'n': f.numerator, 'd': f.denominator}

def xyxy(box):
    if box is None:
        return None
    x, y, w, h = box
    assert w > 0 and h > 0
    return [x, y, x + w, y + h]

def validate(box, dimensions):
    if box is None:
        return {'status': 'NA', 'in_full_canvas': None}
    assert len(box) == 4 and all(isinstance(x, (int, float)) and math.isfinite(x) for x in box)
    x1, y1, x2, y2 = box
    assert x2 > x1 and y2 > y1
    return {'status': 'positive_extent', 'in_full_canvas': 0 <= x1 < x2 <= dimensions[0] and 0 <= y1 < y2 <= dimensions[1]}

def area(box):
    return (box[2] - box[0]) * (box[3] - box[1])

def compare(guided, image):
    """Complete Cartesian table, including explicit NA and zero rows."""
    table = []
    gd = {r['id']: [] for r in guided}
    idg = {r['id']: [] for r in image}
    assert len(gd) == len(guided) and len(idg) == len(image)
    for g in guided:
        for i in image:
            gb, ib = g['box_xyxy'], i['box_xyxy']
            row = {'guided_id': g['id'], 'image_id': i['id']}
            if gb is None or ib is None:
                row.update(status='NA_missing_box', intersection_area=None, union_area=None,
                           iou=None, coverage_guided=None, coverage_image=None, positive=None)
            else:
                inter = max(0, min(gb[2], ib[2]) - max(gb[0], ib[0])) * max(0, min(gb[3], ib[3]) - max(gb[1], ib[1]))
                ga, ia = area(gb), area(ib)
                union = ga + ia - inter
                row.update(status='measured', intersection_area=inter, union_area=union,
                           iou=ratio(inter, union), coverage_guided=ratio(inter, ga), coverage_image=ratio(inter, ia), positive=inter > 0)
                if inter > 0:
                    gd[g['id']].append(i['id'])
                    idg[i['id']].append(g['id'])
            table.append(row)
    assert len(table) == len(guided) * len(image)
    gmissing = [r['id'] for r in guided if r['box_xyxy'] is None]
    imissing = [r['id'] for r in image if r['box_xyxy'] is None]
    mutual = [{'guided_id': k, 'image_id': v[0]} for k, v in gd.items() if len(v) == 1 and len(idg[v[0]]) == 1]
    return {'guided_regions': guided, 'image_regions': image, 'all_pairs': table,
            'counts': {'guided_records': len(guided), 'image_records': len(image),
                       'cartesian_pairs': len(table), 'measured_pairs': sum(r['positive'] is not None for r in table),
                       'NA_pairs': sum(r['positive'] is None for r in table), 'positive_pairs': sum(r['positive'] is True for r in table),
                       'zero_pairs': sum(r['positive'] is False for r in table), 'mutual_single_positive_pairs': len(mutual)},
            'guided_positive_candidates': {k: None if k in gmissing else v for k, v in gd.items()},
            'image_positive_candidates_among_located_guided': idg,
            'guided_unlocated_ids': gmissing, 'image_unlocated_ids': imissing,
            'guided_zero_positive_ids': [k for k, v in gd.items() if not v and k not in gmissing],
            'guided_multiple_positive_ids': [k for k, v in gd.items() if len(v) > 1],
            'image_zero_positive_among_located_guided_ids': [k for k, v in idg.items() if not v and k not in imissing],
            'image_multiple_positive_ids': [k for k, v in idg.items() if len(v) > 1],
            'mutual_single_positive_pairs': mutual,
            'interpretation': 'Positive rectangle area only. No shared-ink, word, source-locus identity or object ownership assertion. Image zero candidates means no overlap with located guided rectangles; unresolved guided NA may still concern that region.'}

def cycles(panel, guided, image, primary, cross):
    mapping = cross['guided_to_image_band']
    gby = {r['id']: r for r in guided}
    iby = {r['id']: r for r in image}
    mutual = {r['guided_id']: r['image_id'] for r in primary['mutual_single_positive_pairs']}
    result = []
    allbands = sorted(set(mapping.values()) | {r['band'] for r in image})
    for band in allbands:
        gs = [r for r in guided if mapping[r['band']] == band]
        ims = [r for r in image if r['band'] == band]
        reasons = []
        if band not in ('outer', 'middle', 'inner'):
            reasons.append('not_a_supplied_same_circular_label_band')
        if not gs or not ims:
            reasons.append('one_branch_has_no_records_for_band')
        if len(gs) != len(ims):
            reasons.append('unequal_declared_band_counts')
        if any(r['box_xyxy'] is None for r in gs + ims):
            reasons.append('NA_bearing_band')
        if any(r['id'] not in mutual or iby[mutual[r['id']]]['band'] != band for r in gs):
            reasons.append('not_complete_globally_mutual_single_same_band_mapping')
        supplied = panel['geometric_traversals'].get(band, {}).get('short_zone_clockwise_order_from_upward_ray')
        if supplied is None or len(supplied) != len(ims) or set(supplied) != {r['id'] for r in ims}:
            reasons.append('image_geometric_order_does_not_enumerate_complete_band')
        base = {'image_band': band, 'guided_bands': [k for k,v in mapping.items() if v == band],
                'guided_ids': [r['id'] for r in gs], 'image_ids': [r['id'] for r in ims],
                'image_supplied_order': supplied, 'status': 'not_computed', 'reasons': reasons,
                'rotation_equivalent': None, 'qualifying_rotation_offsets': None}
        if not reasons:
            cx, cy = panel['working_center_xy']
            dirs = []
            for r in gs:
                x1, y1, x2, y2 = r['box_xyxy']
                dx, dy = x1 + x2 - 2 * cx, y1 + y2 - 2 * cy
                dirs.append((r['id'], dx, dy))
            tied = any(x == y == 0 for _, x, y in dirs)
            tied |= any(x*v == y*u and x*u+y*v > 0 for n,(_,x,y) in enumerate(dirs) for _,u,v in dirs[n+1:])
            if tied:
                base['reasons'].append('undefined_or_tied_guided_center_angle')
            else:
                order = [r[0] for r in sorted(dirs, key=lambda r: math.atan2(r[1], -r[2]) % (2*math.pi))]
                mapped = [mutual[k] for k in order]
                shifts = [s for s in range(len(supplied)) if mapped == supplied[s:] + supplied[:s]]
                base.update(status='computed_geometric_diagnostic', guided_center_clockwise_order=order,
                            mapped_image_order=mapped, rotation_equivalent=bool(shifts), qualifying_rotation_offsets=shifts)
        result.append(base)
    return {'coarse_bands': result, 'fine_alternative_cycles': {'status': 'not_computed', 'reason': 'Alternative split roster is not selected as a certified cyclic unit system; every fine box is retained in Cartesian comparisons.'},
            'object_cycles': {'status': 'not_computed', 'reason': 'Guided object rectangles absent.'},
            'historical_reading_order': None, 'textual_phase_score': None}

def main():
    assert sha(HERE / 'comparison_input_freeze_v1.json') == EXPECTED_FREEZE
    freeze = read('comparison_input_freeze_v1.json')
    for item in freeze['files']:
        assert sha(HERE / item['path']) == item['sha256'], item['path']
    a, g = read('image_observation_v1.json'), read('guided_observation_v1.json')
    crosswalk = read('band_crosswalk_v1.json')
    assert a['fixed_order'] == g['scope']['fixed_panels']
    output = []
    for p in a['all_eight_full_reports']:
        folio = p['panel']; q = next(x for x in g['panels'] if x['folio'] == folio)
        assert str(p['canvas_id']) == str(q['canvas_id']) and p['dimensions_px'] == q['canvas_dimensions']
        assert p['original_sha256'] == q['full_sha256'] and p['official_full_url'] == q['official_full_url']
        rs = [r for r in g['records'] if r['folio'] == folio]
        assert all(str(r['canvas']) == str(p['canvas_id']) for r in rs)
        assert all(set(r['sources']) == {'ZL','IT'} for r in rs)
        # Only geometry and identifiers read from source-guided records below.
        labels = [{'id': r['locator'], 'band': r['band'], 'box_xywh_original': r['working_bbox_xywh'],
                   'box_xyxy': xyxy(r['working_bbox_xywh']), 'status': r['working_region_status']} for r in rs if r['role'] == 'Lz']
        cc = [{'id': r['locator'], 'band': r['band'], 'box_xywh_original': r['working_bbox_xywh'],
               'box_xyxy': xyxy(r['working_bbox_xywh']), 'status': r['working_region_status']} for r in rs if r['role'] == 'Cc']
        assert len(labels) + len(cc) == len(rs)
        coarse = [{'id': r['id'], 'band': r['ring_assignment'], 'box_xyxy': r['box_xyxy'], 'grouping_count_options': r['grouping_count_options']} for r in p['coarse_short_writing_areas']]
        fine = [{'id': r['id'], 'band': r['ring_assignment'], 'box_xyxy': r['box_xyxy'], 'coarse_parent_id': r['coarse_parent_id'], 'status': r['status']} for r in p['finer_short_area_roster_under_recorded_split_options']]
        rings = [{'id': r['id'], 'box_xyxy': r['box_xyxy']} for r in p['continuous_ring_writing']]
        inner = [{'id': r['id'], 'box_xyxy': r['inner_envelope_xyxy']} for r in p['continuous_ring_writing']]
        objects = [{'id': r['id'], 'band': r['ring'], 'box_xyxy': r['complex_envelope_xyxy']} for r in p['human_pointed_shape_complexes']]
        alternatives = []
        for r in rs:
            for index, region in enumerate(r['candidate_regions']):
                assert r['role'] == 'Lz'
                alternatives.append({'id': r['locator'] + '#candidate' + str(index+1), 'parent_locator': r['locator'], 'candidate_index': index,
                                     'band': r['band'], 'box_xywh_original': region['bbox_xywh'], 'box_xyxy': xyxy(region['bbox_xywh']),
                                     'basis': region['basis'], 'parent_working_box_status': r['working_region_status']})
        assert all(isinstance(x,str) for r in rs for x in r['object_candidates'])
        validations = [{'kind': kind, 'id': r['id'], **validate(r['box_xyxy'], p['dimensions_px'])}
                       for kind, regions in [('guided_Lz',labels),('guided_Cc',cc),('image_coarse',coarse),('image_fine',fine),('ring_outer',rings),('ring_inner',inner),('image_object',objects),('guided_alternative',alternatives)] for r in regions]
        primary = compare(labels, coarse)
        cw = next(x for x in crosswalk['panels'] if x['panel'] == folio)
        row = {'panel': folio, 'canvas_id': p['canvas_id'], 'dimensions_px': p['dimensions_px'], 'image_sha256': p['original_sha256'],
               'identity_agrees': True, 'coordinate_validation': validations,
               'inventory': {'guided_Lz': len(labels), 'guided_Cc': len(cc), 'raw_source_rows': sum(len(r['sources']) for r in rs),
                             'image_coarse': len(coarse), 'image_fine_alternative_units': len(fine), 'image_ring_courses': len(rings), 'image_figure_compounds': len(objects),
                             'guided_unlocated_Lz': sum(r['box_xyxy'] is None for r in labels), 'guided_candidate_rectangles': len(alternatives)},
               'short_coarse': primary, 'short_fine': compare(labels, fine),
               'guided_alternative_coarse': compare(alternatives, coarse), 'guided_alternative_fine': compare(alternatives, fine),
               'continuous_ring_outer_envelopes': compare(cc, rings), 'continuous_ring_inner_envelopes': compare(cc, inner),
               'ring_caution': 'Both tables compare enclosing rectangles only, including interiors and other rings; inner envelopes are boundary enclosures, not masks of annular ink. No ring identity follows from intersection.',
               'object_comparison': {'status': 'not_computed_missing_guided_box_roster', 'image_regions': objects, 'guided_regions': None, 'all_pairs': None, 'guided_object_count': None,
                                     'reason': 'Source-guided object_candidates are descriptive strings, not individual figure/compound rectangle records. Image objects and their full component boxes remain preserved in image projection.'},
               'cycle_diagnostics': cycles(p,labels,coarse,primary,cw),
               'preserved_context': {'image_report_pointer': '/all_eight_full_reports/'+str(a['fixed_order'].index(folio)),
                                     'fields_retained_in_full_projection': ['human_pointed_shape_complexes','coarse_short_writing_areas','finer_short_area_roster_under_recorded_split_options','continuous_ring_writing','other_regions','gaps_and_damage','unfilled_or_uncertain_areas','geometric_traversals','grouping_caveat','coverage_note','views_used'],
                                     'guided_all_original_records_retained': True, 'NA_working_boxes_not_replaced_by_alternatives': True}}
        output.append(row)
    total = {key: sum(p['inventory'][key] for p in output) for key in output[0]['inventory']}
    tablenames = ['short_coarse','short_fine','guided_alternative_coarse','guided_alternative_fine','continuous_ring_outer_envelopes','continuous_ring_inner_envelopes']
    totals = {k: {key: sum(p[k]['counts'][key] for p in output) for key in output[0][k]['counts']} for k in tablenames}
    report = {'schema': 'remaining_eight_full_cartesian_geometry_comparison_v1', 'input_freeze_sha256': EXPECTED_FREEZE,
              'fixed_order': a['fixed_order'], 'method': 'Original pixels; exact xywh to xyxy; positive area strict >0; complete Cartesian pairs including zeros and explicit NA; exact rational IoU and two coverages.',
              'observer_role': 'Implementation by the original image-side observer after both branches froze; not a third blind expert or independent historical replication.',
              'panels': output, 'totals': total, 'table_totals': totals,
              'gates': {'complete_text_sequence': 'NOT_READY', 'label_specific_body': 'NOT_READY', 'word_identity': 'NOT_CERTIFIED', 'object_ownership': 'NOT_CERTIFIED'},
              'limitations': ['No transcription strings, source clock positions or source order were compared or scored.',
                             'No coordinate adjustment, best assignment, ring-size matching or elimination of NA/extra candidates.',
                             'Coarse and finer alternative tables are separate; neither selects a preferred linguistic grouping.',
                             'Source rows and full image uncertainty/damage/other-region fields are retained in the public projections.',
                             'Geometric diagnostic only. Shared canvases and physical leaves are not independent samples; no pooling with the earlier four-panel experiment in this computation.',
                             'Independent implementation arithmetic audit is pending; first output is to be frozen before summary interpretation.']}
    print(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))

if __name__ == '__main__':
    main()
