"""Compare all declared rectangles; never compare transcription strings.

Reads explicit public copies and verifies their hashes. Emits JSON to stdout.
Positive intersection is only a geometric candidate, not a matching decision.
"""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
PANELS = ['f70v1', 'f71r', 'f71v', 'f72r1']

def area(b):
    return (b[2]-b[0])*(b[3]-b[1])

def xyxy(b):
    x,y,w,h=b
    return [x,y,x+w,y+h]

def overlap(a,b):
    intersection=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    return {'intersection_px2':intersection,
            'iou':intersection/(area(a)+area(b)-intersection),
            'fraction_guided_rectangle':intersection/area(a),
            'fraction_image_rectangle':intersection/area(b)}

def candidates(left,right):
    return [dict(guided_id=a['id'],image_id=b['id'],
                 guided_box_xyxy=a['box'],image_box_xyxy=b['box'],
                 guided_ring=a.get('ring'),image_ring=b.get('ring'),
                 **overlap(a['box'],b['box'])) for a in left for b in right]

def degree_table(left,right,pairs):
    return {'guided':[{'id':a['id'],'positive_candidates':[r['image_id'] for r in pairs if r['guided_id']==a['id'] and r['intersection_px2']>0]} for a in left],
            'image':[{'id':b['id'],'positive_candidates':[r['guided_id'] for r in pairs if r['image_id']==b['id'] and r['intersection_px2']>0]} for b in right]}

def main():
    receipt=json.loads((HERE/'projection_receipt_v1.json').read_text())
    for r in receipt['files']:
        assert hashlib.sha256((HERE/r['output']).read_bytes()).hexdigest()==r['output_sha256']
    image=json.loads((HERE/'image_observation_v1.json').read_text())
    guided=json.loads((HERE/'guided_observation_v1.json').read_text())
    assert [p['panel'] for p in image['panels']]==PANELS
    assert [p['folio'] for p in guided['panels']]==PANELS
    out=[]
    for folio in PANELS:
        ip=next(p for p in image['panels'] if p['panel']==folio)
        gp=next(p for p in guided['panels'] if p['folio']==folio)
        assert str(ip['canvas_id'])==str(gp['canvas'])
        assert ip['dimensions_px']==gp['canvas_dimensions']
        records=[r for r in guided['records'] if r['folio']==folio]
        labels=[r for r in records if r['role']=='Lz'];rings=[r for r in records if r['role']=='Cc']
        assert len(labels)==15
        left=[{'id':r['locator'],'box':xyxy(r['working_bbox_xywh']),'ring':r['band']} for r in labels]
        coarse=[{'id':r['id'],'box':r['box_xyxy'],'ring':r['ring_assignment']} for r in ip['coarse_short_writing_areas']]
        fine=[{'id':r['id'],'box':r['box_xyxy'],'ring':r['ring_assignment']} for r in ip['finer_short_area_roster_under_recorded_split_options']]
        coarse_pairs=candidates(left,coarse);fine_pairs=candidates(left,fine)
        degrees=degree_table(left,coarse,coarse_pairs)
        fine_degrees=degree_table(left,fine,fine_pairs)
        rd={r['id']:r['positive_candidates'] for r in degrees['image']}
        mutual={r['id']:r['positive_candidates'][0] for r in degrees['guided'] if len(r['positive_candidates'])==1 and len(rd[r['positive_candidates'][0]])==1}
        cycles=[]
        for band in ['inner','outer']:
            gc=gp[band+'_geometry_clockwise_cycle']
            ic=ip['geometric_traversals'][band]['short_zone_clockwise_order_from_upward_ray']
            mapped=[mutual.get(x) for x in gc]
            complete=all(x is not None for x in mapped) and len(set(mapped))==len(ic) and set(mapped)==set(ic)
            offsets=[r for r in range(len(ic)) if mapped==ic[r:]+ic[:r]] if complete else []
            reverse=ic[::-1]
            reverse_offsets=[r for r in range(len(ic)) if mapped==reverse[r:]+reverse[:r]] if complete else []
            cycles.append({'ring':band,'guided_geometry_cycle':gc,'image_geometry_cycle':ic,
                           'mutual_single_candidate_projection':mapped,'complete_at_coarse_rectangle_level':complete,
                           'common_clockwise_order_equal_up_to_cut':bool(offsets) if complete else None,
                           'display_cut_offsets_if_equal':offsets,'reverse_cut_offsets_if_equal':reverse_offsets,
                           'limit':'Geometric diagnostic only, no word scoring or historical reading order. Full fine grouping and object ownership remain separate.'})
        # Nested ring envelopes all overlap by construction: no assignment selected.
        ring_left=[{'id':r['locator'],'box':xyxy(r['working_bbox_xywh'])} for r in rings]
        ring_right=[{'id':r['id'],'box':r['box_xyxy']} for r in ip['continuous_ring_writing']]
        object_left=[{'id':r['id'],'box':xyxy(r['compound_bbox_xywh'])} for r in gp['compounds']]
        object_right=[{'id':r['id'],'box':r['complex_envelope_xyxy'],'ring':r['ring']} for r in ip['human_pointed_shape_complexes']]
        object_pairs=candidates(object_left,object_right)
        object_degrees=degree_table(object_left,object_right,object_pairs)
        summary={'guided_source_labels':len(left),'image_coarse_areas':len(coarse),'image_fine_alternative_units':len(fine),
                 'positive_coarse_pairs':sum(r['intersection_px2']>0 for r in coarse_pairs),
                 'mutual_single_coarse_candidates':len(mutual),
                 'guided_zero_coarse_candidates':sum(not r['positive_candidates'] for r in degrees['guided']),
                 'guided_multiple_coarse_candidates':sum(len(r['positive_candidates'])>1 for r in degrees['guided']),
                 'image_zero_coarse_candidates':sum(not r['positive_candidates'] for r in degrees['image']),
                 'positive_fine_pairs':sum(r['intersection_px2']>0 for r in fine_pairs),
                 'image_zero_fine_candidates':sum(not r['positive_candidates'] for r in fine_degrees['image']),
                 'guided_ring_records':len(rings),'image_ring_courses':len(ring_right),
                 'explicit_split_areas':sum(len(r['grouping_count_options'])>1 for r in ip['coarse_short_writing_areas'])}
        out.append({'folio':folio,'canvas':str(gp['canvas']),'dimensions_px':gp['canvas_dimensions'],'summary':summary,
                    'all_coarse_rectangle_pairs':coarse_pairs,'coarse_candidate_degrees':degrees,
                    'all_fine_alternative_rectangle_pairs':fine_pairs,'fine_candidate_degrees':fine_degrees,
                    'mutual_single_coarse_candidates':mutual,'geometric_cycle_diagnostics':cycles,
                    'all_ring_envelope_pairs':candidates(ring_left,ring_right),
                    'ring_comparison_limit':'Rectangles include the whole enclosed disk; intersection does not locate ring ink or determine exact ring correspondence.',
                    'all_object_envelope_pairs':object_pairs,'object_candidate_degrees':object_degrees,
                    'image_damage_records':ip['gaps_and_damage'],
                    'image_other_regions':ip['other_regions'],
                    'label_specific_body_established':False,'historical_inter_ring_connection':None})
    result={'schema':'four_panel_geometric_comparison_v1','scope':'All fixed four panels, all 60 Lz and 11 Cc retained in source projection; no manuscript text scores.',
            'inputs':receipt['files'],'panels':out,
            'coarse_correspondence_is_not_word_certification':True,
            'new_manuscript_word_matching_computed':False,
            'gate':'NOT_READY_FOR_FULL_TEXT_SEQUENCE_OR_LABEL_SPECIFIC_BODY_TEST',
            'selection_limit':'Four selected panels out of twelve, from three physical leaves; two panels share a canvas. Same AI system and prior exposure, not four independent experimental samples.'}
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
