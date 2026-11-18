#!/usr/bin/env python3
"""Build the four-panel page from explicitly approved public projections and the completed audit only."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'research/research_next/astronomical7h_20261118/four_panel_comparison'
SITE = ROOT / 'site'
FILES = ('image_observation_v1.json', 'guided_observation_v1.json', 'projection_receipt_v1.json', 'comparison_v1.json', 'report_v1.txt', 'audit_v1.txt', 'audit_v1.json', 'audit_addendum_v1.txt')
LAYERS = [
    ('coarse','图像观察 · 粗文字区'), ('fine','图像观察 · 细分备选'),
    ('lz','来源定位 · Lz 阅读框'), ('cc','来源定位 · Cc 包络'),
    ('ring','图像观察 · 连续环文包络'), ('damage','图像观察 · 损伤与缺口'),
    ('other','图像观察 · 中央与边注'), ('objects','图像观察 · 复合邻域'),
    ('guided_objects','来源定位 · 复合邻域'),
]
def digest(data): return hashlib.sha256(data).hexdigest()
def xyxy(box):
    x,y,w,h=box
    return [x,y,x+w,y+h]
def main():
    raw={name:(SOURCE/name).read_bytes() for name in FILES}
    data={name:json.loads(value) if name.endswith('.json') else value.decode('utf-8') for name,value in raw.items()}
    for row in data['projection_receipt_v1.json']['files']:
        assert row['output'] in raw and digest(raw[row['output']])==row['output_sha256']
    assert data['audit_v1.json']['errors']==[]
    image=data['image_observation_v1.json'];guided=data['guided_observation_v1.json'];comparison=data['comparison_v1.json']
    fixed=['f70v1','f71r','f71v','f72r1']
    assert [p['panel'] for p in image['panels']]==fixed
    assert [p['folio'] for p in guided['panels']]==fixed
    assert [p['folio'] for p in comparison['panels']]==fixed
    assert sum(r['role']=='Lz' for r in guided['records'])==60
    assert sum(r['role']=='Cc' for r in guided['records'])==11
    assert sum(len(r['sources']) for r in guided['records'])==142
    panels=[]
    for im,gu,co in zip(image['panels'],guided['panels'],comparison['panels']):
        width,height=im['dimensions_px'];url=gu['full_url']
        assert gu['canvas_dimensions']==[width,height]
        assert url==f"https://collections.library.yale.edu/iiif/2/{im['canvas_id']}/full/full/0/default.jpg"
        records=[]
        def add(layer,entry,bbox,record_id):
            assert len(bbox)==4 and all(type(n) is int for n in bbox)
            x1,y1,x2,y2=bbox
            assert 0<=x1<x2<=width and 0<=y1<y2<=height,(im['panel'],record_id,bbox)
            records.append({'key':layer+':'+record_id,'layer':layer,'id':record_id,'bbox':bbox,'raw':entry})
        for layer,field,boxfield in [
            ('coarse','coarse_short_writing_areas','box_xyxy'),
            ('fine','finer_short_area_roster_under_recorded_split_options','box_xyxy'),
            ('ring','continuous_ring_writing','box_xyxy'),
            ('damage','gaps_and_damage','box_xyxy'),
            ('other','other_regions','box_xyxy'),
            ('objects','human_pointed_shape_complexes','complex_envelope_xyxy')]:
            for entry in im[field]:add(layer,entry,entry[boxfield],entry['id'])
        for entry in guided['records']:
            if entry['folio']==im['panel']:add(entry['role'].lower(),entry,xyxy(entry['working_bbox_xywh']),entry['locator'])
        for entry in gu['compounds']:add('guided_objects',entry,xyxy(entry['compound_bbox_xywh']),entry['id'])
        assert len({r['key'] for r in records})==len(records)
        panels.append({'id':im['panel'],'canvas':im['canvas_id'],'dimensions':[width,height],
          'url':url,'image_sha256':gu['full_sha256'],'viewport':im['observed_panel_box_xyxy'],
          'records':records,'comparison':co,'image_observation':im,'guided_panel':gu})
    payload={'schema':1,'snapshot_utc':datetime.now(timezone.utc).isoformat(),
      'status':'坐标协调记录；全部矩形对已由另一实现复算，未认证字形、词界或词义。审核者也是原图像侧观察者。',
      'layers':[{'id':key,'label':label} for key,label in LAYERS],'panels':panels,
      'report':data['report_v1.txt']+'\n\n'+data['audit_addendum_v1.txt'],'source_receipt':data['projection_receipt_v1.json'],
      'sources':[{'name':name,'sha256':digest(value)} for name,value in raw.items()]}
    content=json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    assert '/Users/' not in content
    target=SITE/'downloads/zodiac-four';target.mkdir(parents=True,exist_ok=True)
    for name,value in raw.items():(target/name).write_bytes(value)
    (SITE/'data/zodiac-four.json').write_text(content,encoding='utf-8')
    path=SITE/'zodiac-four.html';html=path.read_text()
    version=digest(content.encode())[:16]
    html=re.sub(r'(<meta name="zodiac-four-snapshot" content=")[^"]*(">)',lambda m:m[1]+version+m[2],html)
    for asset in ['zodiac-four.js','zodiac-four.css']:
        version_asset=digest((SITE/asset).read_bytes())[:16]
        html=re.sub(r'(["\'])'+re.escape(asset)+r'(?:\?[^"\']*)?(["\'])',lambda m:m[1]+asset+'?v='+version_asset+m[2],html)
    path.write_text(html)
    print(f'Built zodiac-four {version}; 4 panels, 60 Lz, 11 Cc, 142 original lines; eight explicit source files.')
if __name__=='__main__': main()
