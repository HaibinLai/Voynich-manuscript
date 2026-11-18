#!/usr/bin/env python3
"""Compare frozen independent arithmetic with primary v2, without executing it."""
from pathlib import Path
from fractions import Fraction
from collections import Counter
from datetime import datetime,timezone
import argparse,ast,gzip,hashlib,json
HERE=Path(__file__).resolve().parent;BASE=HERE.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
FAMILIES={'coarse':'short_coarse','fine':'short_fine','ring_outer':'continuous_ring_outer_envelopes',
          'ring_inner':'continuous_ring_inner_envelopes','alternative_coarse':'guided_alternative_coarse',
          'alternative_fine':'guided_alternative_fine'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--calculation',type=Path,default=HERE/'calculation_v1/independent_expected_v1.json.gz')
    args=ap.parse_args()
    if args.output.exists():raise RuntimeError('Refuse to overwrite audit output.')
    frozen=read(HERE/'independent_calculation_freeze_v1.json')
    own_expected=next(x for x in frozen['files'] if x['path'].endswith('.json.gz'))
    assert sha(args.calculation)==own_expected['sha256']
    assert sha(HERE/'rebuild_v1.py')==next(x['sha256'] for x in frozen['files'] if x['path']=='rebuild_v1.py')
    second=read(BASE/'second_output_freeze_v1.json')
    for row in second['files']:assert sha(BASE/row['path'])==row['sha256']
    final=read(BASE/'output_freeze_v1.json')
    for row in final['files']:assert sha(BASE/row['path'])==row['sha256']
    own=json.loads(gzip.decompress(args.calculation.read_bytes()))
    main_result=read(BASE/'comparison_v2.json')
    guided=read(BASE/'guided_observation_v1.json');image=read(BASE/'image_observation_v1.json')
    crosswalk=read(BASE/'band_crosswalk_v1.json')
    discrepancy=[];checks=0
    def check(actual,expected,path):
        nonlocal checks
        checks+=1
        if actual!=expected:discrepancy.append({'path':path,'actual':actual,'expected':expected})
    def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    def gid(x):
        if '::candidate:' in x:
            parent,num=x.split('::candidate:');return parent+'#candidate'+str(int(num)+1)
        return x
    def qdict(q):
        q=Fraction(q);return {'n':q.numerator,'d':q.denominator}
    def rect(vals):return None if vals is None else [Fraction(str(x)) for x in vals]
    check(main_result['fixed_order'],[p['folio'] for p in own['panels']],'fixed_order')
    check(main_result['input_freeze_sha256'],sha(BASE/'comparison_input_freeze_v1.json'),'input_freeze_sha256')
    all_tables=[];inventory_totals=Counter();table_totals={name:Counter() for name in FAMILIES.values()}
    cycles_checked=0;coordinate_rows_checked=0;source_rows_checked=0
    assert len(main_result['panels'])==len(own['panels'])==8
    for expected,actual in zip(own['panels'],main_result['panels']):
        folio=expected['folio'];tag=folio+'/';check(actual['panel'],folio,tag+'panel')
        original_image=next(x for x in image['all_eight_full_reports'] if x['panel']==folio)
        rs=[x for x in guided['records'] if x['folio']==folio];by_locator={x['locator']:x for x in rs}
        check(actual['canvas_id'],expected['canvas_id'],tag+'canvas');check(actual['dimensions_px'],expected['dimensions'],tag+'dimensions')
        check(actual['image_sha256'],original_image['original_sha256'],tag+'original_image_sha');check(actual['identity_agrees'],True,tag+'identity')
        check(hashlib.sha256(canonical(rs)).hexdigest(),expected['guided_records_sha256'],tag+'all_guided_fields_preserved')
        image_objects=original_image['human_pointed_shape_complexes']
        check(hashlib.sha256(canonical(image_objects)).hexdigest(),expected['image_objects_payload_sha256'],tag+'all_image_object_fields_preserved')
        vals=[]
        for family,main_key in FAMILIES.items():
            t=expected['tables'][family];u=actual[main_key];where=tag+main_key+'/'
            check([x['id'] for x in u['guided_regions']],[gid(x['id']) for x in t['guided']],where+'guided_roster')
            check([x['id'] for x in u['image_regions']],[x['id'] for x in t['image']],where+'image_roster')
            for supplied,ref in zip(u['guided_regions'],t['guided']):
                check(rect(supplied['box_xyxy']),rect(ref['rect']),where+supplied['id']+'/box')
                check(supplied['band'],ref['band'],where+supplied['id']+'/band')
                if 'source_locator' in ref:
                    source=by_locator[ref['source_locator']];c=source['candidate_regions'][ref['candidate_index']]
                    check(supplied['parent_locator'],ref['source_locator'],where+supplied['id']+'/parent')
                    check(supplied['candidate_index'],ref['candidate_index'],where+supplied['id']+'/candidate_index')
                    check(supplied['box_xywh_original'],c['bbox_xywh'],where+supplied['id']+'/original_box')
                    check(supplied['basis'],c['basis'],where+supplied['id']+'/basis')
                else:
                    source=by_locator[ref['id']];check(supplied['box_xywh_original'],source['working_bbox_xywh'],where+supplied['id']+'/original_box')
            for supplied,ref in zip(u['image_regions'],t['image']):
                check(rect(supplied['box_xyxy']),rect(ref['rect']),where+supplied['id']+'/box')
                check(supplied.get('band'),ref['band'],where+supplied['id']+'/band')
            expected_pairs={(gid(x['guided_id']),x['image_id']):x['metrics'] for x in t['pairs']}
            actual_pairs={(x['guided_id'],x['image_id']):x for x in u['all_pairs']}
            check(len(actual_pairs),len(u['all_pairs']),where+'no_duplicate_pairs')
            check(set(actual_pairs),set(expected_pairs),where+'complete_cartesian_keys')
            for key,metrics in expected_pairs.items():
                if key not in actual_pairs:continue
                row=actual_pairs[key];at=where+'pair/'+key[0]+'/'+key[1]
                check(row['status'],'NA_missing_box' if metrics is None else 'measured',at+'/status')
                for src,dest in [('intersection','intersection_area'),('union','union_area')]:
                    check(None if row[dest] is None else Fraction(str(row[dest])),None if metrics is None else Fraction(metrics[src]),at+'/'+dest)
                for src,dest in [('iou','iou'),('guided_coverage','coverage_guided'),('image_coverage','coverage_image')]:
                    check(row[dest],None if metrics is None else qdict(metrics[src]),at+'/'+dest)
                check(row['positive'],None if metrics is None else Fraction(metrics['intersection'])>0,at+'/positive')
            counts={'guided_records':len(t['guided']),'image_records':len(t['image']),'cartesian_pairs':t['pair_count'],
                    'measured_pairs':t['pair_count']-t['NA_pair_count'],'NA_pairs':t['NA_pair_count'],
                    'positive_pairs':t['positive_pair_count'],'zero_pairs':t['pair_count']-t['NA_pair_count']-t['positive_pair_count'],
                    'mutual_single_positive_pairs':len(t['mutual_single_pairs'])}
            check(u['counts'],counts,where+'counts');table_totals[main_key].update(counts)
            check(u['guided_positive_candidates'],{gid(k):v for k,v in t['guided_positive_candidates'].items()},where+'guided_neighbors')
            check(u['image_positive_candidates_among_located_guided'],{k:[gid(x) for x in v] for k,v in t['image_positive_candidates'].items()},where+'image_neighbors')
            for src,dest in [('unlocated_guided','guided_unlocated_ids'),('located_guided_zero','guided_zero_positive_ids'),('located_guided_multiple','guided_multiple_positive_ids')]:
                check(u[dest],[gid(x) for x in t[src]],where+dest)
            for src,dest in [('image_zero_known_overlap','image_zero_positive_among_located_guided_ids'),('image_multiple_known_overlap','image_multiple_positive_ids')]:check(u[dest],t[src],where+dest)
            check(u['image_unlocated_ids'],[x['id'] for x in t['image'] if x['rect'] is None],where+'image_missing')
            check(u['mutual_single_positive_pairs'],[{'guided_id':gid(a),'image_id':b} for a,b in t['mutual_single_pairs']],where+'mutual_single')
            all_tables.append({'folio':folio,'family':main_key,**counts})
        t=expected['tables']
        inventory={'guided_Lz':len(t['coarse']['guided']),'guided_Cc':len(t['ring_outer']['guided']),
                   'raw_source_rows':sum(len(x['sources']) for x in rs),'image_coarse':len(t['coarse']['image']),
                   'image_fine_alternative_units':len(t['fine']['image']),'image_ring_courses':len(t['ring_outer']['image']),
                   'image_figure_compounds':len(image_objects),'guided_unlocated_Lz':len(t['coarse']['unlocated_guided']),
                   'guided_candidate_rectangles':len(t['alternative_coarse']['guided'])}
        check(actual['inventory'],inventory,tag+'inventory');inventory_totals.update(inventory)
        objects=actual['object_comparison']
        check(objects['image_regions'],[{'id':x['id'],'band':x['ring'],'box_xyxy':x['complex_envelope_xyxy']} for x in image_objects],tag+'objects_preserved')
        for k in ['guided_regions','all_pairs','guided_object_count']:check(objects[k],None,tag+'objects/'+k)
        check(objects['status'],'not_computed_missing_guided_box_roster',tag+'objects_status')
        # Coordinates are checked directly from the independent frozen boxes.
        kinds=[('guided_Lz',t['coarse']['guided']),('guided_Cc',t['ring_outer']['guided']),('image_coarse',t['coarse']['image']),
               ('image_fine',t['fine']['image']),('ring_outer',t['ring_outer']['image']),('ring_inner',t['ring_inner']['image'])]
        kinds+=[('image_object',[{'id':x['id'],'rect':x['complex_envelope_xyxy']} for x in image_objects]),('guided_alternative',t['alternative_coarse']['guided'])]
        coord=[]
        for kind,rows in kinds:
            for r in rows:
                b=rect(r['rect']);inside=None if b is None else 0<=b[0]<b[2]<=expected['dimensions'][0] and 0<=b[1]<b[3]<=expected['dimensions'][1]
                coord.append({'kind':kind,'id':gid(r['id']),'status':'NA' if b is None else 'positive_extent','in_full_canvas':inside})
        check(actual['coordinate_validation'],coord,tag+'coordinate_validation');coordinate_rows_checked+=len(coord)
        cycle=actual['cycle_diagnostics'];cw=next(x for x in crosswalk['panels'] if x['panel']==folio)['guided_to_image_band']
        bandset=set(cw.values())|{x['band'] for x in t['coarse']['image']}
        check([b['image_band'] for b in cycle['coarse_bands']],sorted(bandset),tag+'cycle_roster')
        for b in cycle['coarse_bands']:
            band=b['image_band'];cycles_checked+=1
            check(b['status'],'not_computed_missing_independently_declared_guided_cycle',tag+'cycle/'+band+'/status')
            for k in ['guided_independently_declared_geometric_order','rotation_equivalent','qualifying_rotation_offsets']:check(b[k],None,tag+'cycle/'+band+'/'+k)
            check(b['guided_ids'],[x['id'] for x in t['coarse']['guided'] if cw[x['band']]==band],tag+'cycle/'+band+'/guided_roster')
            check(b['image_ids'],[x['id'] for x in t['coarse']['image'] if x['band']==band],tag+'cycle/'+band+'/image_roster')
            check(b['image_supplied_order'],original_image['geometric_traversals'].get(band,{}).get('short_zone_clockwise_order_from_upward_ray'),tag+'cycle/'+band+'/source_order_retained_only')
        for k in ['fine_alternative_cycles','object_cycles']:check(cycle[k]['status'],'not_computed',tag+k)
        for k in ['historical_reading_order','textual_phase_score']:check(cycle[k],None,tag+k)
        context=actual['preserved_context']
        check(context['guided_all_original_records_retained'],True,tag+'source_preservation_claim')
        check(context['NA_working_boxes_not_replaced_by_alternatives'],True,tag+'NA_preservation_claim')
    for r in own['source_rows']:
        supplied=next(x for x in guided['records'] if x['locator']==r['locator'])
        check(hashlib.sha256(canonical(supplied['sources'])).hexdigest(),r['source_payload_sha256'],'source/'+r['locator']);source_rows_checked+=len(supplied['sources'])
    check(main_result['totals'],dict(inventory_totals),'totals')
    check(main_result['table_totals'],{k:dict(v) for k,v in table_totals.items()},'table_totals')
    check(main_result['gates'],{'complete_text_sequence':'NOT_READY','label_specific_body':'NOT_READY','word_identity':'NOT_CERTIFIED','object_ownership':'NOT_CERTIFIED'},'gates')
    # Static guard review only: the primary module is never imported or run.
    code=(BASE/'compare_v2.py').read_text();tree=ast.parse(code)
    forbidden={'raw_line','raw_body','source_clock_guidance','source_ordinal'}
    accesses=[n.slice.value for n in ast.walk(tree) if isinstance(n,ast.Subscript) and isinstance(n.slice,ast.Constant) and n.slice.value in forbidden]
    check(accesses,[],'static/no_transcription_or_source_order_access')
    trig=[n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute) and n.attr in ['atan','atan2','sin','cos']]
    check(trig,[],'static/no_derived_angles')
    correction=read(BASE/'cycle_scope_correction_v2.json')
    check(correction['authoritative_interpretation'],True,'scope_correction_authoritative')
    check(correction['no_scientific_inputs_changed'],True,'scope_correction_inputs_unchanged')
    result={'schema':'independent_v2_geometry_audit_v1','completed_utc':datetime.now(timezone.utc).isoformat(),
            'all_passed':not discrepancy,'exact_checks':checks,'differences':discrepancy,
            'tables_checked':all_tables,'totals':dict(inventory_totals),'table_totals':{k:dict(v) for k,v in table_totals.items()},
            'cycle_band_entries_confirmed_uncomputed':cycles_checked,'coordinate_records_checked':coordinate_rows_checked,
            'original_source_rows_preserved':source_rows_checked,'primary_implementation_imported_or_executed':False,
            'scope':'Exact rectangle arithmetic and preservation audit; no independent visual, glyph, semantic or historical-order certification.',
            'independent_calculation_frozen_before_v2_read':True,
            'dependencies':{n:sha(BASE/n) for n in ['comparison_v2.json','compare_v2.py','second_output_freeze_v1.json','output_freeze_v1.json','cycle_scope_correction_v2.json']},
            'script_sha256':sha(Path(__file__))}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    def json_default(x):
        if isinstance(x,Fraction):return str(x)
        if isinstance(x,set):return sorted(x)
        raise TypeError(type(x))
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=json_default)+'\n')
    print(json.dumps({'all_passed':not discrepancy,'checks':checks,'differences':len(discrepancy),'source_rows':source_rows_checked},ensure_ascii=False))

if __name__=='__main__':main()
