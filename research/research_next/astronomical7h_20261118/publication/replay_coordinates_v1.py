"""V2: face-anchored coordinate crosswalk, with all label overlaps retained.
V1 demanded exclusive label rectangles; v2 does not treat incidental box overlap as a competing face.
This post-observation diagnostic refinement is not a pre-registered inference or scoring rule.
"""
from pathlib import Path
import datetime as dt
import hashlib
import json
import math

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def xyxy(b):
    x,y,w,h = b
    return [x,y,x+w,y+h]

def area(b):
    return max(0,b[2]-b[0])*max(0,b[3]-b[1])

def intersection(a,b):
    c=[max(a[0],b[0]),max(a[1],b[1]),min(a[2],b[2]),min(a[3],b[3])]
    return c if area(c)>0 else None

def candidates(a, options):
    rows=[]
    for identifier,b in options:
        c=intersection(a,b)
        if c:
            rows.append({'id':identifier,'bbox_xyxy':b,'intersection_xyxy':c,
                         'intersection_px2':area(c),'box_iou':area(c)/(area(a)+area(b)-area(c))})
    return rows

def main():
    receipts = json.loads((HERE/'projection_receipt_v1.json').read_text())['files']
    for name in ['image-only-observation.json', 'guided-observation.json']:
        record = next(r for r in receipts if r['output']==name)
        assert sha(HERE/name)==record['output_sha256'], name
    fresh=json.loads((HERE/'image-only-observation.json').read_text())
    guided=json.loads((HERE/'guided-observation.json').read_text())
    assert fresh['input']['dimensions_px']==[guided['coordinate_system']['width'],guided['coordinate_system']['height']]
    targets=[]
    face_options=[(s['id'],s['face']['box_xyxy']) for s in fresh['sectors']]
    label_options=[(s['id'],s['inner_short_writing']['box_xyxy']) for s in fresh['sectors']]
    for t in guided['targets']:
        a,b=xyxy(t['face_bbox_xywh']),xyxy(t['label_bbox_xywh'])
        fc,lc=candidates(a,face_options),candidates(b,label_options)
        targets.append({'locus':t['locator'],'guided_sector':t['sector_id'],
                        'guided_face_xyxy':a,'guided_label_xyxy':b,
                        'face_box_intersections':fc,'label_box_intersections':lc,
                        'shared_unique_geometric_candidate': fc[0]['id'] if len(fc)==1 and any(c['id']==fc[0]['id'] for c in lc) else None,
                        'raw_versions':t['raw_versions'],'word_definition':t['word_definition'],
                        'limits':'Box overlap establishes working spatial alignment only; neither reading nor reference is certified.'})
    mapping={t['shared_unique_geometric_candidate']:t['guided_sector'] for t in targets if t['shared_unique_geometric_candidate']}
    guided_order=[t['guided_sector'] for t in targets]
    fresh_order=[mapping.get(s['id']) for s in fresh['sectors']]
    edges=lambda seq: {(seq[k],seq[(k+1)%len(seq)]) for k in range(len(seq))}
    body=[]
    for s in guided['sectors']:
        body.append({'guided_sector':s['sector_id'],'paragraph_loci':s['paragraph_loci'],
                     'paragraph_box_candidates':candidates(xyxy(s['paragraph_reading_bbox_xywh']),[(f['id'],f['outer_sector_writing']['box_xyxy']) for f in fresh['sectors']]),
                     'separated_loci':s['separated_line_loci'],
                     'separated_box_candidates':candidates(xyxy(s['separated_line_reading_bbox_xywh']),[(f['id'],f['additional_short_group_outside_face']['box_xyxy']) for f in fresh['sectors'] if f['additional_short_group_outside_face']]) if s['separated_line_reading_bbox_xywh'] else []})
    central=[{'guided_locus':c['locator'],'guided_box_xyxy':xyxy(c['bbox_xywh']),
              'fresh_zone_candidates':candidates(xyxy(c['bbox_xywh']),[(x['id'],x['box_xyxy']) for x in fresh['central_writing']['zones']])} for c in guided['central_ring']]
    outer=[{'fresh_zone':x['id'],'fresh_box_xyxy':x['box_xyxy'],
            'guided_locus_candidates':candidates(x['box_xyxy'],[(x['locator'],xyxy(x['bbox_xywh'])) for x in guided['outer_red_groups']])} for x in fresh['outer_red_writing']['zones']]
    boundaries=[]
    by_sector={s['id']:s for s in fresh['sectors']}
    boundary_by_id={b['id']:b for b in fresh['right_diagram_geometry']['radial_boundaries']}
    reverse={v:k for k,v in mapping.items()}
    for b in guided['sector_boundaries']:
        a,z=b['between']; fa,fz=reverse.get(a),reverse.get(z)
        common=set(by_sector[fa]['clockwise_boundaries'])&set(by_sector[fz]['clockwise_boundaries']) if fa and fz else set()
        boundaries.append({'guided_between':b['between'],'guided_endpoints':b['approx_endpoints_xy'],
                           'guided_continuous':b['certain_continuous_trace'],'guided_observation':b['observation'],
                           'fresh_shared_boundary_candidates':[boundary_by_id[k] for k in sorted(common)],
                           'root_status':'Read both original observations; a shared ID candidate does not reconcile visibility or endpoint disagreement.'})
    report={'utc':dt.datetime.now(dt.timezone.utc).isoformat(),'scope':'Frozen coordinate comparison; not text scoring',
            'inputs':{'fresh':sha(HERE/'image-only-observation.json'),'guided':sha(HERE/'guided-observation.json')},
            'coordinate_conversion':'fresh xyxy; guided xywh converted to xyxy without image modification',
            'face_and_short_zone_crosswalk':targets,'body_region_crosswalk':body,'central_crosswalk':central,'outer_red_crosswalk':outer,
            'boundary_crosswalk':boundaries,
            'cycle':{'guided_order':guided_order,'fresh_order_in_guided_ids':fresh_order,
                     'same_directed_adjacency_edges':edges(guided_order)==edges(fresh_order) if None not in fresh_order else None,
                     'historical_text_start':None,'historical_reading_order':None,
                     'limit':'Geometrical clockwise traversal only; does not certify complete partitions or semantics.'},
            'comparison_revision':'V1 required an exclusive label rectangle intersection. V2 uses a unique face-box intersection whose sector also intersects the label box, retaining all incidental label-box overlaps. Geometric diagnostic only; not an independently specified hypothesis test.',
            'summary':{'nonexclusive_label_rectangles':sum(len(t['label_box_intersections'])>1 for t in targets),'fixed_targets':len(targets),'unique_face_and_zone_intersections':sum(bool(x['shared_unique_geometric_candidate']) for x in targets),
                       'central_guided_loci':len(central),'central_fresh_coarse_zones':len(fresh['central_writing']['zones']),
                       'outer_guided_loci':len(guided['outer_red_groups']),'outer_fresh_coarse_zones':len(outer),
                       'fresh_additional_short_zones':sum(bool(s['additional_short_group_outside_face']) for s in fresh['sectors']),
                       'guided_separated_lines':sum(len(s['separated_line_loci']) for s in guided['sectors'])},
            'gate':'NOT_READY_FOR_COMPLETE_TWELVE_TEXT_SCORING',
            'gate_reasons':['Weak/contested radial boundaries remain; first reports are not forced into agreement.',
                            'Three short-string boundary differences and incomplete body-token eligibility remain.',
                            'Separated-line role and central/outer segmentation differences are preserved.'],
            'new_text_matches_computed':False,'new_cyclic_scores_computed':False}
    expected=json.loads((HERE.parent/'reconciliation_geometry_v2.json').read_text())
    keys=['coordinate_conversion','face_and_short_zone_crosswalk','body_region_crosswalk',
          'central_crosswalk','outer_red_crosswalk','boundary_crosswalk','cycle','summary',
          'gate','gate_reasons','new_text_matches_computed','new_cyclic_scores_computed']
    for key in keys:
        assert report[key]==expected[key], key
    print(json.dumps({'status':'PASS_PUBLIC_COORDINATE_REPLAY',
                      'compared_full_tables':keys,'summary':report['summary'],
                      'limitations':'Public copies replace private path prefixes only. This replays coordinate tables, not text scores or meaning.'},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
