"""Combine observed image reviews, preserving both original transliterations."""
from pathlib import Path
from collections import Counter
import datetime, hashlib, json
ROOT=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    root_path=ROOT/'high_resolution_review.json'
    root=json.loads(root_path.read_text())
    check=json.loads((ROOT/'root_review_spotcheck.json').read_text())
    by_id={r['locator']:r for r in root['records']}
    applied=[]
    for c in check['records']:
        if c['status']!='needs_revision':continue
        r=by_id[c['locator']]
        r['approximate_regions_normalized']=c['suggested_regions_normalized']
        r.pop('approximate_region_normalized',None)
        r['coordinate_revision']={'reason':c['observation'],
            'independent_check':'root_review_spotcheck.json',
            'original_regions_normalized':c['original_regions_normalized']}
        applied.append(c['locator'])
    root['updated_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    root_path.write_text(json.dumps(root,ensure_ascii=False,indent=2)+'\n')
    agent_path=ROOT/'review_agent.json';agent=json.loads(agent_path.read_text())
    records=root['records']+agent['records']
    for r in records:
        if 'approximate_region_normalized' in r:
            r['approximate_regions_normalized']=[r.pop('approximate_region_normalized')]
    inventory=json.loads((ROOT/'locus_inventory.json').read_text())
    index={r['locator']:r for r in inventory};seen=set()
    receipt=json.loads((ROOT/'yale_image_receipt.json').read_text())
    images=receipt['images']
    # Image receipt is an ordered list of records from the official manifest.
    image_index={i['folio']:i for i in images}
    for r in records:
        key=r['locator'];assert key not in seen;seen.add(key)
        assert all(r[k]==index[key][k] for k in ['folio','locus_type','zl','it','category'])
        assert all(r[k] is False for k in ['independent_blind_transcription','authoritative_glyph_correction','all_glyphs_certified'])
        assert r['observation'].strip()
        assert r['approximate_regions_normalized']
        for x0,y0,x1,y1 in r['approximate_regions_normalized']:
            assert 0<=x0<x1<=1 and 0<=y0<y1<=1,(key,[x0,y0,x1,y1])
        image_path=ROOT/r['source_image'];assert image_path.exists()
    assert seen==set(index),sorted(set(index)-seen)
    for f,i in image_index.items():
        # Key name is fixed by download_yale.py and retained in publication.
        expected=i.get('sha256') or i.get('image_sha256')
        assert expected and sha(ROOT/'images'/f'{f}.jpg')==expected,f
    order={r['locator']:i for i,r in enumerate(inventory)}
    records.sort(key=lambda r:order[r['locator']])
    result={'schema_version':1,'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'scope':'20-page high-resolution visual correspondence review against two published transliterations; unresolved readings retained.',
        'not_claimed':['independent blind transcription','authoritative glyph correction','all glyphs certified','decipherment or translation'],
        'region_convention':'Normalized x0,y0,x1,y1 on unmodified Yale JPEG; approximate whole-locus reading areas, sometimes including adjacent strokes. Not precise glyph or word boxes.',
        'pages':len({r['folio'] for r in records}),'loci':len(records),
        'categories':dict(Counter(r['category'] for r in records)),
        'source_files':{p.name:sha(p) for p in [root_path,agent_path,ROOT/'root_review_spotcheck.json',ROOT/'locus_inventory.json']},
        'coordinate_revisions_applied':applied,
        'additional_visible_text_not_in_inventory':root.get('additional_visible_text_not_in_inventory',[]),
        'records':records}
    dest=ROOT/'review_combined.json';dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    verification={'all_passed':True,'pages':result['pages'],'loci':len(records),'unique_locator_coverage':True,
        'source_transliterations_unchanged':True,'all_rectangles_valid':True,'official_image_hashes_verified':len(image_index),
        'independent_spotcheck_loci':len(check['records']),'coordinate_revisions_applied':applied,
        'no_glyph_certification_or_translation_claim':True,'combined_sha256':sha(dest)}
    (ROOT/'review_verification.json').write_text(json.dumps(verification,indent=2)+'\n')
    print(json.dumps(verification,indent=2))
if __name__=='__main__':main()
