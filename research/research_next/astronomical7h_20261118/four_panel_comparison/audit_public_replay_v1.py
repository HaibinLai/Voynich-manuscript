#!/usr/bin/env python3
"""Public-only read-only replay of the fixed four-panel coordinate comparison.

Run from any working directory:
  python3 research/research_next/astronomical7h_20261118/four_panel_comparison/audit_public_replay_v1.py

Python standard library only. JSON result goes to stdout; exit 0 means all
checks pass, exit 1 means recorded differences. No input or existing audit is
written. Only PUBLIC_JSON and SOURCE_FILES below are read, plus this script's
own bytes for its identity hash. JSON paths are provenance, never extra reads.

Adapted from the separately implemented audit_replay_v1.py; it never imports,
executes or calls compare_v1.py. This is a public subset of that audit, not a
new independent observer or an equal-scope replacement. It does NOT inspect
private original images, verify their bytes/dimensions, compare raw observer
files with public projections, or verify the private source-inventory object.
It checks declared image dimensions/identities for consistency and preserves
all 142 raw transcription lines exactly against the two repository sources.
"""
import json, hashlib, math, datetime, re, sys
from pathlib import Path
from fractions import Fraction
from collections import Counter
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[3]
PANELS=['f70v1','f71r','f71v','f72r1']
PUBLIC_JSON=('image_observation_v1.json','guided_observation_v1.json','projection_receipt_v1.json','comparison_v1.json')
SOURCE_FILES={'ZL':'research/sources/ZL3b-n.txt','IT':'research/sources/IT2a-n.txt'}
def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(x): return hashlib.sha256(x.encode()).hexdigest()
errors=[]
checks=[]
def check(ok,where,detail=None):
    checks.append({'check':where,'pass':bool(ok)})
    if not ok: errors.append({'where':where,'detail':detail})
def corner(b): return (b[0],b[1],b[0]+b[2],b[1]+b[3])
def center(b): return ((b[0]+b[2])/2,(b[1]+b[3])/2)
def clockwise(rows,origin):
    return [r[0] for r in sorted(rows,key=lambda r:math.atan2(center(r[1])[0]-origin[0],origin[1]-center(r[1])[1])%(2*math.pi))]
def cyclic(a,b):
    # Compare directed adjacency including closing edge; no best-fit score.
    return len(a)==len(b) and len(set(a))==len(a) and set(a)==set(b) and dict(zip(a,a[1:]+a[:1]))==dict(zip(b,b[1:]+b[:1]))
def measure(a,b):
    left=max(a[0],b[0]);right=min(a[2],b[2]);top=max(a[1],b[1]);bottom=min(a[3],b[3])
    ix=(right-left)*(bottom-top) if right>left and bottom>top else 0
    aa=(a[2]-a[0])*(a[3]-a[1]);bb=(b[2]-b[0])*(b[3]-b[1])
    return ix,[Fraction(ix,aa+bb-ix),Fraction(ix,aa),Fraction(ix,bb)]
def replay(left,right,saved,dims,where):
    check(len({x[0] for x in left})==len(left) and len({x[0] for x in right})==len(right),where+'/unique_ids')
    for side,rr in [('guided',left),('image',right)]:
        for name,b in rr:
            check(len(b)==4 and 0<=b[0]<b[2]<=dims[0] and 0<=b[1]<b[3]<=dims[1],where+'/valid_box/'+side+'/'+name)
    got={(r['guided_id'],r['image_id']):r for r in saved}
    expected={(a[0],b[0]) for a in left for b in right}
    check(len(saved)==len(got)==len(expected) and set(got)==expected,where+'/all_cartesian_pairs')
    gd={a[0]:[] for a in left};im={b[0]:[] for b in right};positive=[]
    for gn,gb in left:
        for inn,ib in right:
            area,ratios=measure(gb,ib);z=got.get((gn,inn),{})
            check(tuple(z.get('guided_box_xyxy',[]))==tuple(gb) and tuple(z.get('image_box_xyxy',[]))==tuple(ib),where+'/boxes/'+gn+'/'+inn)
            check(z.get('intersection_px2')==area and all(math.isclose(z.get(k,-1),float(v),rel_tol=1e-14,abs_tol=1e-15) for k,v in zip(['iou','fraction_guided_rectangle','fraction_image_rectangle'],ratios)),where+'/metrics/'+gn+'/'+inn)
            if area:
                gd[gn].append(inn);im[inn].append(gn)
                positive.append({'guided_id':gn,'image_id':inn,'intersection_px2':area,'exact_ratios':[str(x) for x in ratios]})
    mutual={g:q[0] for g,q in gd.items() if len(q)==1 and len(im[q[0]])==1}
    return {'cartesian_pair_count':len(expected),'positive_pair_count':len(positive),'positive_pairs':positive,'guided_candidates':gd,'image_candidates':im,'mutual_single_candidates':mutual,'mutual_single_count':len(mutual),'guided_zero':[k for k,v in gd.items() if not v],'image_zero':[k for k,v in im.items() if not v],'guided_multiple':{k:v for k,v in gd.items() if len(v)>1},'image_multiple':{k:v for k,v in im.items() if len(v)>1}}
def degree_check(replayed,saved,where):
    for side in ['guided','image']:
        check(len(saved[side])==len(replayed[side+'_candidates']) and {x['id']:x['positive_candidates'] for x in saved[side]}==replayed[side+'_candidates'],where+'/'+side+'_degrees')
# All science inputs are named here. No directory scans or JSON-directed reads.
public_raw={name:(HERE/name).read_bytes() for name in PUBLIC_JSON}
public={name:json.loads(content) for name,content in public_raw.items()}
image=public['image_observation_v1.json'];guided=public['guided_observation_v1.json'];saved=public['comparison_v1.json']
receipt=public['projection_receipt_v1.json']
check(len(receipt['files'])==2 and {r['output'] for r in receipt['files']}=={'image_observation_v1.json','guided_observation_v1.json'},'projection/explicit_output_allowlist')
for row in receipt['files']:
    name=row['output']
    check(name in public_raw and hashlib.sha256(public_raw[name]).hexdigest()==row['output_sha256'],'projection/public_output_hash/'+name)
check(saved['inputs']==receipt['files'],'comparison/input_receipt_exact')
check([p['panel'] for p in image['panels']]==PANELS,'image/fixed_four_panel_order')
check([p['folio'] for p in guided['panels']]==PANELS,'guided/fixed_four_panel_order')
check([p['folio'] for p in saved['panels']]==PANELS,'comparison/fixed_four_panel_order')
# Parse only source record headers. Text content is compared as opaque strings.
source_bytes={version:(REPO/name).read_bytes() for version,name in SOURCE_FILES.items()}
source_lines={version:content.decode('utf-8').splitlines() for version,content in source_bytes.items()}
source_inventory={}
for version,lines in source_lines.items():
    inventory={}
    for number,line in enumerate(lines,1):
        match=re.match(r'^<([^,>]+),([^>]+)>',line)
        if not match: continue
        locator,role_raw=match.groups();folio=locator.rsplit('.',1)[0];role=role_raw[-2:]
        if folio not in PANELS or role not in {'Lz','Cc'}: continue
        check(locator not in inventory,'source/unique_original_locator/'+version+'/'+locator)
        inventory[locator]={'line':line,'number':number,'role':role,'role_raw':role_raw,'folio':folio}
    source_inventory[version]=inventory
records={r['locator']:r for r in guided['records']}
check(len(records)==len(guided['records'])==71,'all_71_unique_source_locators')
counts=Counter(r['role'] for r in guided['records'])
check(counts=={'Lz':60,'Cc':11},'source_role_counts',dict(counts))
for version,inventory in source_inventory.items():
    check(set(records)==set(inventory),'original_complete_locator_inventory/'+version)
    check(Counter(r['role'] for r in inventory.values())=={'Lz':60,'Cc':11},'original_role_counts/'+version)
rowchecks=[]
for loc,row in records.items():
    check(set(row['sources'])=={'ZL','IT'},'exact_two_source_versions/'+loc)
    for version in ['ZL','IT']:
        sr=row['sources'][version];expected=source_inventory[version].get(loc,{})
        raw_equal=sr['raw_line']==expected.get('line')
        position_equal=sr['source_line']==expected.get('number')
        metadata_equal=(sr['source_file']==SOURCE_FILES[version] and sr['locator']==loc and sr['folio']==row['folio']==expected.get('folio') and sr['role']==row['role']==expected.get('role') and sr['role_raw']==expected.get('role_raw'))
        check(raw_equal,'original_raw_line_exact/'+loc+'/'+version)
        check(position_equal,'original_source_line_number/'+loc+'/'+version)
        check(metadata_equal,'original_source_metadata/'+loc+'/'+version)
        rowchecks.append({'locator':loc,'role':row['role'],'version':version,'source_line':sr['source_line'],'raw_line_sha256':digest(sr['raw_line']),'preserved_exactly':raw_equal and position_equal and metadata_equal})
check(len(rowchecks)==142,'all_142_original_lines_checked')
results=[]
for folio in PANELS:
    ip=next(p for p in image['panels'] if p['panel']==folio);gp=next(p for p in guided['panels'] if p['folio']==folio);cp=next(p for p in saved['panels'] if p['folio']==folio)
    dims=ip['dimensions_px'];cid=str(ip['canvas_id'])
    check(cid==str(gp['canvas'])==cp['canvas'] and dims==gp['canvas_dimensions']==cp['dimensions_px'],folio+'/canvas_identity_dimensions')
    declared_original=next(r for r in image['original_images'] if '/'+cid+'/' in r['official_url'])
    check(declared_original['dimensions_px']==dims and declared_original['sha256']==gp['full_sha256'],'declared_image_metadata_consistency/'+folio)
    check(declared_original['official_url']==gp['full_url']==f'https://collections.library.yale.edu/iiif/2/{cid}/full/full/0/default.jpg','declared_official_canvas_url/'+folio)
    rr=[r for r in guided['records'] if r['folio']==folio];labels=[r for r in rr if r['role']=='Lz'];rings=[r for r in rr if r['role']=='Cc']
    check(all(str(r['canvas'])==cid for r in rr),folio+'/record_canvas_ids')
    left=[(r['locator'],corner(r['working_bbox_xywh'])) for r in labels]
    coarse=[(r['id'],r['box_xyxy']) for r in ip['coarse_short_writing_areas']]
    fine=[(r['id'],r['box_xyxy']) for r in ip['finer_short_area_roster_under_recorded_split_options']]
    ol=[(r['id'],corner(r['compound_bbox_xywh'])) for r in gp['compounds']]
    oi=[(r['id'],r['complex_envelope_xyxy']) for r in ip['human_pointed_shape_complexes']]
    rl=[(r['locator'],corner(r['working_bbox_xywh'])) for r in rings];ri=[(r['id'],r['box_xyxy']) for r in ip['continuous_ring_writing']]
    out={'folio':folio,'canvas':cid,'dimensions':dims}
    for name,a,b,field,df in [('coarse',left,coarse,'all_coarse_rectangle_pairs','coarse_candidate_degrees'),('fine',left,fine,'all_fine_alternative_rectangle_pairs','fine_candidate_degrees'),('objects',ol,oi,'all_object_envelope_pairs','object_candidate_degrees'),('rings',rl,ri,'all_ring_envelope_pairs',None)]:
        out[name]=replay(a,b,cp[field],dims,folio+'/'+name)
        if df: degree_check(out[name],cp[df],folio+'/'+name)
    # Preserve ring metadata even for cross-ring intersections; no filtering by band.
    for field,gr,ir in [
        ('all_coarse_rectangle_pairs',{r['locator']:r['band'] for r in labels},{r['id']:r['ring_assignment'] for r in ip['coarse_short_writing_areas']}),
        ('all_fine_alternative_rectangle_pairs',{r['locator']:r['band'] for r in labels},{r['id']:r['ring_assignment'] for r in ip['finer_short_area_roster_under_recorded_split_options']}),
        ('all_object_envelope_pairs',{r['id']:None for r in gp['compounds']},{r['id']:r['ring'] for r in ip['human_pointed_shape_complexes']}),
        ('all_ring_envelope_pairs',{r['locator']:None for r in rings},{r['id']:None for r in ip['continuous_ring_writing']})]:
        check(all(z['guided_ring']==gr[z['guided_id']] and z['image_ring']==ir[z['image_id']] for z in cp[field]),folio+'/'+field+'/ring_metadata')
    check(out['coarse']['mutual_single_candidates']==cp['mutual_single_coarse_candidates'],folio+'/mutual_coarse')
    # Every finer alternative is a retained child or unchanged coarse zone.
    fine_dict=dict(fine)
    for z in ip['coarse_short_writing_areas']:
        children=[r for r in ip['finer_short_area_roster_under_recorded_split_options'] if r['coarse_parent_id']==z['id']]
        expected=z['finer_visible_subcluster_alternative_boxes_xyxy'] or [z['box_xyxy']]
        check([r['box_xyxy'] for r in children]==expected,folio+'/all_split_children/'+z['id'])
    out['cycles']=[]
    for band in ['inner','outer']:
        gc=gp[band+'_geometry_clockwise_cycle'];ic=ip['geometric_traversals'][band]['short_zone_clockwise_order_from_upward_ray'];origin=ip['working_center_xy']
        gg=clockwise([(r['locator'],corner(r['working_bbox_xywh'])) for r in labels if r['band']==band],origin)
        ii=clockwise([(r['id'],r['box_xyxy']) for r in ip['coarse_short_writing_areas'] if r['ring_assignment']==band],origin)
        check(cyclic(gc,gg),folio+'/'+band+'/guided_declared_clockwise_from_actual_boxes')
        check(cyclic(ic,ii),folio+'/'+band+'/image_declared_clockwise_from_actual_boxes')
        mapping=out['coarse']['mutual_single_candidates'];mapped=[mapping.get(x) for x in gc]
        complete=None not in mapped and len(mapped)==len(ic) and len(set(mapped))==len(mapped) and set(mapped)==set(ic)
        same=cyclic(mapped,ic) if complete else None
        offsets=[ic.index(mapped[0])] if same else []
        rev=ic[::-1];reverse=[rev.index(mapped[0])] if complete and cyclic(mapped,rev) else []
        got=next(x for x in cp['geometric_cycle_diagnostics'] if x['ring']==band)
        expected={'guided_geometry_cycle':gc,'image_geometry_cycle':ic,'mutual_single_candidate_projection':mapped,'complete_at_coarse_rectangle_level':complete,'common_clockwise_order_equal_up_to_cut':same,'display_cut_offsets_if_equal':offsets,'reverse_cut_offsets_if_equal':reverse}
        for k,val in expected.items():check(got[k]==val,folio+'/'+band+'/cycle/'+k)
        fine_ids=[r['id'] for r in ip['finer_short_area_roster_under_recorded_split_options'] if r['ring_assignment']==band]
        fm=[out['fine']['mutual_single_candidates'].get(x) for x in gc]
        fcomplete=None not in fm and len(fm)==len(fine_ids) and set(fm)==set(fine_ids)
        fine_order=clockwise([(r['id'],r['box_xyxy']) for r in ip['finer_short_area_roster_under_recorded_split_options'] if r['ring_assignment']==band],origin)
        out['cycles'].append({'ring':band,'fine_geometry_clockwise_order':fine_order,'fine_mutual_projection':fm,'fine_common_clockwise_cycle':cyclic(fm,fine_order) if fcomplete else None,**expected,'guided_center_derived_order':gg,'image_center_derived_order':ii,'complete_at_fine_mutual_candidate_level':fcomplete,'fine_unmapped_guided':[x for x in gc if x not in out['fine']['mutual_single_candidates']]})
    # Supplementary object-envelope cycle diagnostic. Uses only geometry and
    # declared ring membership; guided locator association is not ownership.
    out['object_cycle_supplement']=[]
    label_bands={r['locator']:r['band'] for r in labels}
    for band in ['inner','outer']:
        gb=[(r['id'],corner(r['compound_bbox_xywh'])) for r in gp['compounds'] if label_bands[r['associated_source_locator_for_guidance']]==band]
        ib=[(r['id'],r['complex_envelope_xyxy']) for r in ip['human_pointed_shape_complexes'] if r['ring']==band]
        gc=clockwise(gb,ip['working_center_xy']);ic=clockwise(ib,ip['working_center_xy'])
        mapped=[out['objects']['mutual_single_candidates'].get(x) for x in gc]
        complete=None not in mapped and len(mapped)==len(ic) and len(set(mapped))==len(mapped) and set(mapped)==set(ic)
        out['object_cycle_supplement'].append({'ring':band,'guided_geometry_clockwise_cycle':gc,'image_geometry_clockwise_cycle':ic,'mutual_single_candidate_projection':mapped,'complete':complete,'same_clockwise_cycle':cyclic(mapped,ic) if complete else None,'limit':'Supplement, not a claim made by original compare_v1.py; ring membership exposed through guided record metadata. No text-object ownership inferred.'})
    s=cp['summary'];expected_summary={'guided_source_labels':len(left),'image_coarse_areas':len(coarse),'image_fine_alternative_units':len(fine),'positive_coarse_pairs':out['coarse']['positive_pair_count'],'mutual_single_coarse_candidates':out['coarse']['mutual_single_count'],'guided_zero_coarse_candidates':len(out['coarse']['guided_zero']),'guided_multiple_coarse_candidates':len(out['coarse']['guided_multiple']),'image_zero_coarse_candidates':len(out['coarse']['image_zero']),'positive_fine_pairs':out['fine']['positive_pair_count'],'image_zero_fine_candidates':len(out['fine']['image_zero']),'guided_ring_records':len(rl),'image_ring_courses':len(ri),'explicit_split_areas':sum(len(z['grouping_count_options'])>1 for z in ip['coarse_short_writing_areas'])}
    check(s==expected_summary,folio+'/summary_exact')
    check(cp['image_damage_records']==ip['gaps_and_damage'] and cp['image_other_regions']==ip['other_regions'],folio+'/nonmatched_regions_retained')
    results.append(out)
check(saved['coarse_correspondence_is_not_word_certification'] and not saved['new_manuscript_word_matching_computed'] and saved['gate']=='NOT_READY_FOR_FULL_TEXT_SEQUENCE_OR_LABEL_SPECIFIC_BODY_TEST','interpretation_gates')
pair_counts={name:sum(panel[name]['cartesian_pair_count'] for panel in results) for name in ['coarse','fine','objects','rings']}
check(pair_counts=={'coarse':900,'fine':1125,'objects':900,'rings':31},'all_2956_rectangle_pairs',pair_counts)
inputs=[{'path':name,'sha256':hashlib.sha256(content).hexdigest()} for name,content in public_raw.items()]
inputs.extend({'path':SOURCE_FILES[version],'sha256':hashlib.sha256(content).hexdigest()} for version,content in source_bytes.items())
report={
 'schema':'public_four_panel_independent_implementation_replay_v1',
 'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'status':'PASS' if not errors else 'FAIL',
 'method':'Independent implementation adapted from audit_replay_v1.py; compare_v1.py never imported or executed. Exact Fraction rectangle measures, complete Cartesian pairs, all positive candidates without winner selection, directed cyclic adjacency, original-line equality.',
 'scope':'Public subset of the full audit. Source raw strings are used only for exact preservation checks, not geometry or linguistic matching.',
 'omitted_checks':['No private original-image byte hashes or actual decoded dimensions checked.','No original-observer-to-public-projection field-by-field comparison; only public projection output hashes checked.','No private source-inventory object or private frozen input files read; raw lines and source location metadata are independently checked against the two public repository transcriptions.','No new visual reobservation, glyph/spacing/word-boundary certification, word similarity, semantic identity or historical reading-order inference.'],
 'inputs':inputs,'script_sha256':sha(Path(__file__)),
 'checks_total':len(checks),'checks_passed':sum(c['pass'] for c in checks),'errors':errors,'checks':checks,
 'source_preservation':{'counts':dict(counts),'versions':2,'rows_checked':len(rowchecks),'row_checks':rowchecks},
 'rectangle_pair_counts':pair_counts,'rectangle_pairs_total':sum(pair_counts.values()),'panels':results,
 'interpretation':'Rectangle intersections and coarse-cycle agreement do not certify words or referents. Full text-sequence / label-specific-body gate remains NOT_READY.'}
print(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))
sys.exit(1 if errors else 0)
