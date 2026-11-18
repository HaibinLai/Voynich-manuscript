#!/usr/bin/env python3
"""Explicit frozen-input builder. Preview is always labelled pending; release needs a root receipt."""
import argparse
import hashlib
from html import escape
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'research/research_next/astronomical7h_20261118/zodiac_remaining_comparison'
SITE = ROOT / 'site'
FILES = ('image_observation_v1.json', 'guided_observation_v1.json', 'comparison_v2.json',
         'cycle_scope_correction_v2.json', 'report_v2.txt', 'public_manifest_v1.json', 'output_freeze_v1.json')
FREEZE_SHA = 'cacec2fab29e6a6c329b7450af969908d2b57d35a7a1e5fbc672318a1a787d99'
AUDIT_RELATIVE = 'research/research_next/astronomical7h_20261118/zodiac_remaining_comparison/independent_audit/audit_report_v1.json'
AUDIT_TEXT_SHA = '2fcd42ab146f33e9083c9e32f53bdf2eeb34960e221e3e64f1a888ec0a61ce20'
ORDER = ['f70v2','f72r2','f72r3','f72v3','f72v2','f72v1','f73r','f73v']
LAYERS = [('coarse','图像观察 · 粗文字区'),('fine','图像观察 · 细分备选'),
          ('lz','来源定位 · Lz 工作框（含 NA）'),('alternative','来源定位 · 额外候选（不回填 NA）'),
          ('cc','来源定位 · Cc 包络'),('ring','图像观察 · 环文外包络'),
          ('ring_inner','图像观察 · 环文内包络'),('damage','图像观察 · 损伤与缺口'),
          ('other','图像观察 · 中央与边注'),('objects','图像观察 · 人物复合邻域')]
TABLES = ['short_coarse','short_fine','guided_alternative_coarse','guided_alternative_fine',
          'continuous_ring_outer_envelopes','continuous_ring_inner_envelopes']
def sha(b): return hashlib.sha256(b).hexdigest()
def xyxy(b): return None if b is None else [b[0],b[1],b[0]+b[2],b[1]+b[3]]
def verified_audit(approval, raw):
    # The approval binds the real report; its own declared PASS string is insufficient.
    assert approval['audit_report_path']==AUDIT_RELATIVE
    path=ROOT/AUDIT_RELATIVE
    audit_bytes=path.read_bytes()
    assert sha(audit_bytes)==approval['audit_report_sha256']
    audit=json.loads(audit_bytes)
    assert audit['schema']=='independent_v2_geometry_audit_v1'
    assert audit['all_passed'] is True and audit['differences']==[]
    assert type(audit['exact_checks']) is int and audit['exact_checks']>0
    assert audit['primary_implementation_imported_or_executed'] is False
    assert audit['independent_calculation_frozen_before_v2_read'] is True
    assert audit['original_source_rows_preserved']==528
    assert {(t['folio'],t['family']) for t in audit['tables_checked']}=={(p,t) for p in ORDER for t in TABLES}
    assert len(audit['tables_checked'])==48
    for name in ['comparison_v2.json','output_freeze_v1.json','cycle_scope_correction_v2.json']:
        assert audit['dependencies'][name]==sha(raw[name])
    assert approval['audit_text_path']==str(Path(AUDIT_RELATIVE).with_suffix('.txt'))
    text_bytes=(ROOT/approval['audit_text_path']).read_bytes()
    assert sha(text_bytes)==approval['audit_text_sha256']==AUDIT_TEXT_SHA
    return audit, {'independent-audit-report.json':audit_bytes,'independent-audit-report.txt':text_bytes}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    mode=ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preview',action='store_true')
    mode.add_argument('--release-approval',type=Path,help='Root-authored receipt binding comparison and freeze SHA; never inferred from audit files.')
    args=ap.parse_args()
    raw={n:(SOURCE/n).read_bytes() for n in FILES}
    assert sha(raw['output_freeze_v1.json'])==FREEZE_SHA
    d={n:json.loads(b) if n.endswith('.json') else b.decode('utf-8') for n,b in raw.items()}
    frozen={r['path']:r['sha256'] for r in d['output_freeze_v1.json']['files']}
    for n,b in raw.items():
        if n!='output_freeze_v1.json': assert sha(b)==frozen[n],n
    approval=None
    audit=None
    if args.release_approval:
        approval=json.loads(args.release_approval.read_text())
        assert approval['schema']=='zodiac_eight_release_approval_v1'
        assert approval['approved_by']=='root' and approval['release_approved'] is True
        assert approval['independent_arithmetic_audit']=='COMPLETE'
        assert approval['comparison_sha256']==sha(raw['comparison_v2.json'])
        assert approval['output_freeze_sha256']==FREEZE_SHA
        assert isinstance(approval['public_audit_note'],str) and approval['public_audit_note'].strip()
        audit, audit_downloads=verified_audit(approval,raw)
        raw.update(audit_downloads)
    image=d['image_observation_v1.json']['all_eight_full_reports'];guided=d['guided_observation_v1.json'];comparison=d['comparison_v2.json']
    assert [p['panel'] for p in image]==[p['folio'] for p in guided['panels']]==[p['panel'] for p in comparison['panels']]==ORDER
    panels=[]
    for im,gu,co in zip(image,guided['panels'],comparison['panels']):
        w,h=im['dimensions_px'];url=im['official_full_url']
        assert gu['canvas_dimensions']==[w,h] and gu['official_full_url']==url
        assert url==f"https://collections.library.yale.edu/iiif/2/{im['canvas_id']}/full/full/0/default.jpg"
        assert im['original_sha256']==gu['full_sha256']==co['image_sha256']
        for band in co['cycle_diagnostics']['coarse_bands']:
            assert band['rotation_equivalent'] is None
        records=[]
        def add(layer,entry,box,ident,parent=None):
            if box is not None:
                assert len(box)==4 and all(type(x) is int for x in box)
                x1,y1,x2,y2=box;assert 0<=x1<x2<=w and 0<=y1<y2<=h,(im['panel'],ident)
            records.append({'key':layer+':'+ident,'layer':layer,'id':ident,'bbox':box,'parent':parent,'raw':entry})
        for layer,field,bf in [('coarse','coarse_short_writing_areas','box_xyxy'),('fine','finer_short_area_roster_under_recorded_split_options','box_xyxy'),('ring','continuous_ring_writing','box_xyxy'),('ring_inner','continuous_ring_writing','inner_envelope_xyxy'),('damage','gaps_and_damage','box_xyxy'),('other','other_regions','box_xyxy'),('objects','human_pointed_shape_complexes','complex_envelope_xyxy')]:
            for entry in im[field]: add(layer,entry,entry.get(bf),entry['id'])
        for entry in guided['records']:
            if entry['folio']!=im['panel']: continue
            add(entry['role'].lower(),entry,xyxy(entry['working_bbox_xywh']),entry['locator'])
            for index,candidate in enumerate(entry['candidate_regions'],1):
                add('alternative',candidate,xyxy(candidate['bbox_xywh']),entry['locator']+f'#candidate{index}',entry['locator'])
        assert len({r['key'] for r in records})==len(records)
        panels.append({'id':im['panel'],'canvas':im['canvas_id'],'dimensions':[w,h],'url':url,
                       'image_sha256':im['original_sha256'],'viewport':im['observed_panel_box_xyxy'],
                       'records':records,'comparison':{k:co[k] for k in TABLES},
                       'guided_panel':gu,'unfilled_or_uncertain_areas':im['unfilled_or_uncertain_areas']})
    source_rows=[r for p in panels for r in p['records'] if r['layer'] in ('lz','cc')]
    assert len(source_rows)==264 and sum(len(r['raw']['sources']) for r in source_rows)==528
    assert sum(r['bbox'] is None for r in source_rows)==8
    payload={'schema':'zodiac_eight_page_v1','preview':not bool(approval),
             'status':('本地预览 · 独立算术审核待完成 · 未获正式发布批准。' if not approval else approval['public_audit_note']),
             'independent_audit':audit,'release_approval':approval,'release_approval_sha256':sha(args.release_approval.read_bytes()) if approval else None,'frozen_utc':d['output_freeze_v1.json']['frozen_utc'],
             'layers':[{'id':i,'label':l} for i,l in LAYERS], 'panels':panels,
             'report':d['report_v2.txt'],'cycle_correction':d['cycle_scope_correction_v2.json'],
             'sources':[{'name':n,'sha256':sha(b)} for n,b in raw.items()]}
    content=json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n'
    assert '/Users/' not in content
    target=SITE/'downloads/zodiac-eight';target.mkdir(parents=True,exist_ok=True)
    for n,b in raw.items():(target/n).write_bytes(b)
    (SITE/'data/zodiac-eight.json').write_text(content,encoding='utf-8')
    htmlpath=SITE/'zodiac-eight.html';html=htmlpath.read_text();version=sha(content.encode())[:16]
    html=re.sub(r'(<strong id="z8-audit-state">).*?(</strong>)',lambda m:m[1]+escape(payload['status'])+m[2],html)
    html=re.sub(r'(<meta name="zodiac-eight-snapshot" content=")[^"]*(">)',lambda m:m[1]+version+m[2],html)
    for asset in ['zodiac-eight.js','zodiac-eight.css']:
        html=re.sub(r'(["\'])'+re.escape(asset)+r'(?:\?[^"\']*)?(["\'])',lambda m:m[1]+asset+'?v='+sha((SITE/asset).read_bytes())[:16]+m[2],html)
    htmlpath.write_text(html)
    print(json.dumps({'version':version,'preview':not bool(approval),'panels':len(panels),'source_records':len(source_rows),'original_lines':528,'downloads':list(raw)},ensure_ascii=False))
if __name__=='__main__':main()
