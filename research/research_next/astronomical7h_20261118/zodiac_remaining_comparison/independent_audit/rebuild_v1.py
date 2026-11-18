#!/usr/bin/env python3
"""Independent exact rectangle arithmetic. Never loads primary comparison code/results.

Only fixed input projections, their freezes and schema metadata are read.
Output must be a new directory. No text matching, angle or cycle computation.
"""
from pathlib import Path
from fractions import Fraction
from datetime import datetime,timezone
from collections import Counter
import argparse,hashlib,json,gzip

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
INPUTS=['protocol_v1.txt','comparison_input_freeze_v1.json','image_observation_v1.json',
        'guided_observation_v1.json','image_source_freeze_v1.json','guided_source_freeze_v1.json',
        'projection_receipt_v1.json','band_crosswalk_v1.json']
ORDER=['f70v2','f72r2','f72r3','f72v3','f72v2','f72v1','f73r','f73v']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())

def packed(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()

def rat(x):
    q=Fraction(x);return str(q.numerator)+'/'+str(q.denominator)

def box(values,xywh=False):
    if values is None:return None
    a,b,c,d=[Fraction(str(x)) for x in values]
    result=(a,b,a+c,b+d) if xywh else (a,b,c,d)
    assert result[0]<result[2] and result[1]<result[3]
    return result

def bounds_ok(rect,dimensions):
    if rect is not None:
        assert 0<=rect[0]<rect[2]<=dimensions[0] and 0<=rect[1]<rect[3]<=dimensions[1]

def pair_metrics(a,b):
    if a is None or b is None:return None
    area_a=(a[2]-a[0])*(a[3]-a[1]);area_b=(b[2]-b[0])*(b[3]-b[1])
    spans=[]
    for lo,hi in [(0,2),(1,3)]:
        left=sorted((a[lo],b[lo]))[1];right=sorted((a[hi],b[hi]))[0]
        spans.append(max(Fraction(0),right-left))
    intersection=spans[0]*spans[1];union=area_a+area_b-intersection
    return {'guided_area':rat(area_a),'image_area':rat(area_b),'intersection':rat(intersection),
            'union':rat(union),'iou':rat(intersection/union),
            'guided_coverage':rat(intersection/area_a),'image_coverage':rat(intersection/area_b)}

def table(left,right):
    assert len({x['id'] for x in left})==len(left) and len({x['id'] for x in right})==len(right)
    pairs=[];neighbors={x['id']:[] if x['rect'] is not None else None for x in left};reverse={x['id']:[] for x in right}
    for a in left:
        for b in right:
            metrics=pair_metrics(a['rect'],b['rect'])
            pairs.append({'guided_id':a['id'],'image_id':b['id'],'metrics':metrics})
            if metrics is not None and Fraction(metrics['intersection'])>0:
                neighbors[a['id']].append(b['id']);reverse[b['id']].append(a['id'])
    mutual=[]
    for aid,bs in neighbors.items():
        if bs is not None and len(bs)==1 and len(reverse[bs[0]])==1:mutual.append([aid,bs[0]])
    def serialize(rows):return [{**{k:v for k,v in x.items() if k!='rect'},'rect':[rat(v) for v in x['rect']] if x['rect'] is not None else None} for x in rows]
    return {'guided':serialize(left),'image':serialize(right),'pairs':pairs,
            'guided_positive_candidates':neighbors,'image_positive_candidates':reverse,
            'unlocated_guided':[x['id'] for x in left if x['rect'] is None],
            'located_guided_zero':[a for a,b in neighbors.items() if b==[]],
            'located_guided_multiple':[a for a,b in neighbors.items() if b is not None and len(b)>1],
            'image_zero_known_overlap':[a for a,b in reverse.items() if not b],
            'image_multiple_known_overlap':[a for a,b in reverse.items() if len(b)>1],
            'mutual_single_pairs':mutual,
            'pair_count':len(pairs),'NA_pair_count':sum(x['metrics'] is None for x in pairs),
            'positive_pair_count':sum(x['metrics'] is not None and Fraction(x['metrics']['intersection'])>0 for x in pairs)}

def differences(a,b,path=''):
    if type(a)!=type(b):return [(path,a,b)]
    if isinstance(a,dict):
        assert set(a)==set(b)
        return [z for k in a for z in differences(a[k],b[k],path+'/'+k.replace('~','~0').replace('/','~1'))]
    if isinstance(a,list):
        assert len(a)==len(b)
        return [z for i,(x,y) in enumerate(zip(a,b)) for z in differences(x,y,path+'/'+str(i))]
    return [] if a==b else [(path,a,b)]

def self_checks():
    a=box([0,0,2,2]);b=box([1,1,3,3]);m=pair_metrics(a,b)
    assert m['intersection']=='1/1' and m['union']=='7/1' and m['iou']=='1/7' and m['guided_coverage']=='1/4'
    assert pair_metrics(a,box([2,0,4,2]))['intersection']=='0/1'
    assert pair_metrics(None,b) is None
    assert box([1,2,3,4],True)==box([1,2,4,6])
    assert pair_metrics(a,a)['iou']=='1/1'
    assert pair_metrics(box([0,0,0.5,0.5]),box([0,0,1,1]))['image_coverage']=='1/4'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--original-window',type=Path,help='Optional local provenance comparison; never needed for rectangle replay.')
    args=ap.parse_args()
    if args.output.exists():raise RuntimeError('Refuse to overwrite audit output.')
    self_checks();started=datetime.now(timezone.utc).isoformat()
    input_hashes={n:sha(BASE/n) for n in INPUTS}
    frozen=read(BASE/'comparison_input_freeze_v1.json');recorded={r['path']:r['sha256'] for r in frozen['files']}
    for n,h in input_hashes.items():
        if n!='comparison_input_freeze_v1.json':assert recorded[n]==h,n
    projections=read(BASE/'projection_receipt_v1.json')['projections']
    provenance=[]
    for row in projections:
        assert sha(BASE/row['projection_path'])==row['projection_sha256']
        if args.original_window:
            original=args.original_window/row['source_report'];assert sha(original)==row['source_sha256']
            diff=differences(read(original),read(BASE/row['projection_path']))
            by_pointer={x['json_pointer']:x for x in row['field_changes']}
            assert len(diff)==len(by_pointer)
            for pointer,old,new in diff:
                change=by_pointer[pointer]
                assert pointer.endswith('/path') and '/views_used/' in pointer
                assert isinstance(old,str) and isinstance(new,str) and new.startswith('private-output/')
                assert hashlib.sha256(old.encode()).hexdigest()==change['old_utf8_sha256']
                assert len(old.encode())==change['old_utf8_bytes']
                assert new==change['new_value'] and hashlib.sha256(new.encode()).hexdigest()==change['new_utf8_sha256']
            provenance.append({'branch':row['branch'],'original_sha_checked':True,'path_only_changes_checked':len(diff),'all_other_values_identical':True})
        else:provenance.append({'branch':row['branch'],'original_sha_checked':False,'scope':'Frozen public projection checked; original path-only provenance replay not requested.'})
    g=read(BASE/'guided_observation_v1.json');im=read(BASE/'image_observation_v1.json')
    assert [r['panel'] for r in im['all_eight_full_reports']]==ORDER
    gp={r['folio']:r for r in g['panels']};assert set(gp)==set(ORDER)
    assert Counter(r['role'] for r in g['records'])=={'Lz':239,'Cc':25}
    assert sum(len(r['sources']) for r in g['records'])==528
    assert len({r['locator'] for r in g['records']})==264
    source_rows=[{'locator':r['locator'],'folio':r['folio'],'role':r['role'],
                  'source_payload_sha256':hashlib.sha256(packed(r['sources'])).hexdigest(),
                  'versions':{v:{'source_line':x['source_line'],'raw_line_sha256':hashlib.sha256(x['raw_line'].encode()).hexdigest()} for v,x in r['sources'].items()}}
                 for r in g['records']]
    panels=[]
    for image in im['all_eight_full_reports']:
        folio=image['panel'];meta=gp[folio];dims=image['dimensions_px']
        assert dims==meta['canvas_dimensions'] and image['canvas_id']==meta['canvas_id'] and image['original_sha256']==meta['full_sha256']
        rs=[r for r in g['records'] if r['folio']==folio]
        def guided(role):return [{'id':r['locator'],'rect':box(r['working_bbox_xywh'],True),'band':r['band']} for r in rs if r['role']==role]
        def image_rows(key,rectkey='box_xyxy'):return [{'id':r['id'],'rect':box(r.get(rectkey)),'band':r.get('ring_assignment')} for r in image[key]]
        short=guided('Lz');ring=guided('Cc');coarse=image_rows('coarse_short_writing_areas');fine=image_rows('finer_short_area_roster_under_recorded_split_options')
        alts=[]
        for r in rs:
            for index,c in enumerate(r.get('candidate_regions',[])):
                alts.append({'id':r['locator']+'::candidate:'+str(index),'source_locator':r['locator'],'candidate_index':index,'rect':box(c['bbox_xywh'],True),'band':r['band'],'candidate_payload_sha256':hashlib.sha256(packed(c)).hexdigest()})
        sets={'coarse':(short,coarse),'fine':(short,fine),
              'ring_outer':(ring,image_rows('continuous_ring_writing')),
              'ring_inner':(ring,image_rows('continuous_ring_writing','inner_envelope_xyxy')),
              'alternative_coarse':(alts,coarse),'alternative_fine':(alts,fine)}
        for left,right in sets.values():
            for item in left+right:bounds_ok(item['rect'],dims)
        assert all(all(isinstance(x,str) for x in r.get('object_candidates',[])) for r in rs)
        tables={name:table(*sides) for name,sides in sets.items()}
        panels.append({'folio':folio,'canvas_id':image['canvas_id'],'dimensions':dims,'tables':tables,
                       'guided_records_sha256':hashlib.sha256(packed(rs)).hexdigest(),
                       'image_objects_payload_sha256':hashlib.sha256(packed(image['human_pointed_shape_complexes'])).hexdigest(),
                       'object_comparison':'NOT_COMPUTED_NO_GUIDED_OBJECT_RECTANGLE_ROSTER',
                       'cycle_comparison':'NOT_COMPUTED_NO_GUIDED_INDEPENDENT_DECLARED_CYCLE',
                       'angles_derived':False})
    result={'schema':'independent_zodiac_rectangles_v1','input_hashes':input_hashes,'panels':panels,
            'source_rows':source_rows,'original_counts':{'Lz':239,'Cc':25,'raw_source_lines':528},
            'no_primary_implementation_or_results_read':True,'no_text_matching_or_cycle_computation':True}
    assert input_hashes=={n:sha(BASE/n) for n in INPUTS}
    raw=packed(result);compressed=gzip.compress(raw,mtime=0)
    args.output.mkdir(parents=True)
    (args.output/'independent_expected_v1.json.gz').write_bytes(compressed)
    receipt={'started_utc':started,'completed_utc':datetime.now(timezone.utc).isoformat(),
             'script_sha256':sha(Path(__file__)),'input_hashes':input_hashes,'original_provenance':provenance,
             'computed_output_sha256':hashlib.sha256(compressed).hexdigest(),'uncompressed_payload_sha256':hashlib.sha256(raw).hexdigest(),
             'table_counts':{p['folio']:{k:{z:t[z] for z in ['pair_count','NA_pair_count','positive_pair_count']} for k,t in p['tables'].items()} for p in panels},
             'primary_results_read':False,'primary_code_imported_or_read':False,'text_matching':False,'cycle_computation':False,'self_checks_passed':True}
    (args.output/'calculation_receipt_v1.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'completed':True,'output_sha256':receipt['computed_output_sha256'],'primary_results_read':False},ensure_ascii=False))

if __name__=='__main__':main()
