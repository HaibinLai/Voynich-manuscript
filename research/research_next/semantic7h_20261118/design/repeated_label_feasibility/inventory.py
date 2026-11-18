"""Metadata-only label feasibility; no image or body-text score access."""
from pathlib import Path
import collections, datetime, hashlib, json, re

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[4]
ROOT=HERE.parents[1]
inputs={}
def read(p):
    inputs[str(p.relative_to(REPO))]=hashlib.sha256(p.read_bytes()).hexdigest()
    return json.loads(p.read_text())
def save(name,data):
    (HERE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def parse(raw):
    reasons=[]
    if '<->' in raw or '<~>' in raw:reasons.append('graphic_interruption')
    for m in re.finditer(r'<[^>]*>',raw):
        before=re.sub(r'<[^>]*>','',raw[:m.start()])
        after=re.sub(r'<[^>]*>','',raw[m.end():])
        if before and after and before[-1] not in '.,' and after[0] not in '.,':
            reasons.append('internal_annotation')
    plain=re.sub(r'<[^>]*>','',raw).strip()
    if ',' in plain:reasons.append('uncertain_word_boundary')
    if '.' in plain:reasons.append('multiple_words')
    if any(c in plain for c in '?*'):reasons.append('unknown_character')
    if '[' in plain or ']' in plain:reasons.append('alternate_reading')
    if not re.fullmatch(r'(?:[a-z]|@[0-9]{3};)+',plain):reasons.append('not_one_supported_complete_word')
    return {'plain':plain,'reasons':sorted(set(reasons)),'word':plain if not reasons else None}
def main():
    versions={};type_counts={}
    for version,name in [('ZL','ZL3b-n.txt'),('IT','IT2a-n.txt')]:
        p=REPO/'research/sources'/name;inputs[str(p.relative_to(REPO))]=hashlib.sha256(p.read_bytes()).hexdigest()
        d={};counts=collections.Counter()
        for number,line in enumerate(p.read_text().splitlines(),1):
            m=re.match(r'<(f[^.>]+\.\d+),([^>]+)>\s*(.*)',line)
            if not m or len(m[2])!=3 or m[2][1]!='L':continue
            assert m[1] not in d
            counts[m[2][1:]]+=1
            d[m[1]]={'locator':m[1],'layout':m[2],'subtype':m[2][1:],'raw':m[3],
                'line_number':number,'source_url':'https://voynich.nu/data/'+name,
                'number_annotations':re.findall(r'<!([0-9]+[^>]*)>',m[3]),**parse(m[3])}
        versions[version]=d;type_counts[version]=dict(counts)
    boxes=collections.defaultdict(list)
    p=ROOT/'visual/crossplant/crossplant_visual_review_v1.json'
    for r in read(p)['records']:
        s=r['source']
        for loc in r['candidate_locators']:
            boxes[loc].append({'source_object_id':r['source_folio']+'_'+str(r['fragment_id']),
                'source_record':str(p.relative_to(REPO)),'source_record_key':r['pair_id'],
                'bbox_xywh':s['object_region_xywh'],'image_id':s['oid'],'image_url':s['source_url'],
                'evidence':'prior source-numbered candidate, coarse object box; not independently proven semantic attachment',
                'attachment_ambiguous':len(r['candidate_locators'])!=1,'locator_count_for_object':len(r['candidate_locators'])})
    p=ROOT/'visual/order_candidates/review.json'
    for r in read(p)['records']:
        for loc in r['reviewed_label_locators']:
            boxes[loc].append({'source_object_id':r['source_folio']+'_'+str(r['fragment_id']),
                'source_record':str(p.relative_to(REPO)),'source_record_key':r['pair_id'],
                'bbox_xywh':r['approximate_native_object_bbox_xywh'],'image_id':r['image']['image_id'],
                'image_url':r['image']['source']['url'],'evidence':'prior source-layout localization; approximate native object box',
                'attachment_ambiguous':r['object_attachment_status']!='clear','attachment_status':r['object_attachment_status'],
                'locator_count_for_object':len(r['reviewed_label_locators'])})
    p=ROOT/'visual/unresolved_sources/review.json'
    for r in read(p)['objects']:
        candidate=r.get('new_candidate')
        if not candidate:continue
        boxes[candidate['locator']].append({'source_object_id':r['source_object_id'],
            'source_record':str(p.relative_to(REPO)),'source_record_key':r['source_object_id'],
            'bbox_xywh':r['object_approx_bbox_xywh'],'image_id':r['image_id'],
            'image_url':'https://collections.library.yale.edu/iiif/2/'+r['image_id']+'/full/full/0/default.jpg',
            'evidence':candidate['classification'],'attachment_ambiguous':r['label_observation']=='unresolved',
            'attachment_status':candidate['attachment'],'locator_count_for_object':1})
    manifest=read(REPO/'research/research7h/visual_audit/yale_manifest.json')
    canvases=[]
    for c in manifest['items']:
        label=' | '.join(v for vs in c['label'].values() for v in vs)
        body=c['items'][0]['items'][0]['body']
        canvases.append({'canvas_label':label,'canvas_id':c['id'],'image_id':c['id'].rsplit('/',1)[-1],
            'image_url':body['id'],'width':body['width'],'height':body['height']})
    records=[]
    for loc in sorted(set(versions['ZL'])|set(versions['IT'])):
        v={k:d.get(loc) for k,d in versions.items()};reasons=[];folio=loc.split('.')[0]
        for k,r in v.items():
            if r is None:reasons.append(k+':missing_label_locus')
            else:reasons += [k+':'+x for x in r['reasons']]
        if all(v.values()):
            if v['ZL']['subtype']!=v['IT']['subtype']:reasons.append('subtype_disagreement')
            if v['ZL']['plain']!=v['IT']['plain']:reasons.append('complete_reading_or_boundary_disagreement')
        eligible=not reasons
        subtype=v['ZL']['subtype'] if v['ZL'] else v['IT']['subtype']
        side_match=re.match(r'f([0-9]+[rv])',folio)
        side=side_match[1] if side_match else None
        leaf_match=re.match(r'f[0-9]+',folio)
        cs=[c for c in canvases if side and re.search(r'(?<![0-9])'+re.escape(side)+r'(?![a-z])',c['canvas_label'])]
        bb=boxes.get(loc,[])
        records.append({'locator':loc,'folio':folio,'physical_leaf':leaf_match[0] if leaf_match else None,
            'subtype':subtype,'versions':v,'strict_reading_eligible':eligible,'exclusion_reasons':sorted(set(reasons)),
            'agreed_word':v['ZL']['word'] if eligible else None,
            'plant_stratum':subtype if subtype in ('Lp','Lf') else None,
            'selection_status':('eligible_'+subtype if eligible and subtype in ('Lp','Lf') else 'excluded_nonplant_type' if subtype not in ('Lp','Lf') else 'ineligible_reading'),
            'existing_object_boxes':bb,'has_existing_object_box':bool(bb),
            'has_unambiguous_single_locator_box':any(not b['attachment_ambiguous'] and b['locator_count_for_object']==1 for b in bb),
            'official_canvas_candidates':cs,'canvas_scope':'folio-side label candidates only; foldout panels unresolved unless an existing box supplies image_id'})
    clusters=[]
    for subtype in ('Lp','Lf'):
        grouped=collections.defaultdict(list)
        for r in records:
            if r['strict_reading_eligible'] and r['subtype']==subtype:grouped[r['agreed_word']].append(r)
        for word,rs in sorted(grouped.items()):
            leaves=sorted({r['physical_leaf'] for r in rs})
            if len(leaves)<2:continue
            b=[r for r in rs if r['has_existing_object_box']]
            u=[r for r in rs if r['has_unambiguous_single_locator_box']]
            clusters.append({'subtype':subtype,'agreed_word':word,'locators':[r['locator'] for r in rs],
                'physical_leaves':leaves,'physical_leaf_count':len(leaves),'occurrences':len(rs),
                'boxed_locators':[r['locator'] for r in b],'boxed_physical_leaves':sorted({r['physical_leaf'] for r in b}),
                'unambiguous_box_locators':[r['locator'] for r in u],
                'unambiguous_box_physical_leaves':sorted({r['physical_leaf'] for r in u})})
    summary={}
    for subtype in sorted({r['subtype'] for r in records}):
        rr=[r for r in records if r['subtype']==subtype];ee=[r for r in rr if r['strict_reading_eligible']];cc=[c for c in clusters if c['subtype']==subtype]
        summary[subtype]={'union_loci':len(rr),'strict_agreed_single_word_loci':len(ee),
            'eligible_physical_leaves':len({r['physical_leaf'] for r in ee if r['physical_leaf']}),
            'eligible_unknown_physical_leaf_loci':sum(r['physical_leaf'] is None for r in ee),
            'cross_leaf_clusters':len(cc),'cross_leaf_cluster_loci':sum(c['occurrences'] for c in cc),
            'cross_leaf_clusters_with_boxes_on_two_leaves':sum(len(c['boxed_physical_leaves'])>=2 for c in cc),
            'cross_leaf_clusters_with_unambiguous_boxes_on_two_leaves':sum(len(c['unambiguous_box_physical_leaves'])>=2 for c in cc)}
    out={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Metadata-only feasibility, already exposed corpus; no new image or lexical-body scoring',
        'inputs':inputs,'source_label_counts':type_counts,'summary_by_subtype':summary,'records':records,'cross_leaf_plant_clusters':clusters}
    save('inventory_v1.json',out);save('clusters_v1.json',clusters)
    save('input_receipt_v1.json',{'inputs':inputs,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'protocol_sha256':hashlib.sha256((HERE/'protocol_v1.txt').read_bytes()).hexdigest(),
        'new_images_viewed':False,'lexical_body_scores_read_for_selection':False,'morphological_scores_computed':False})
    print(json.dumps({'summary':{k:summary[k] for k in ('Lp','Lf','Lc','L0')},'clusters':clusters},indent=2))
if __name__=='__main__':main()
