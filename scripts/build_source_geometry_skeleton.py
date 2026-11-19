#!/usr/bin/env python3
"""Local text-only inherited-data preview. No current observations or release snapshot."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
W=Path('research/research_next/source_geometry7h_20261119')
FILES=['session_v1.json','plan_v1.txt','source_observation_protocol_v1.json','source_observation_protocol_v1.txt','inherited_sources_v1.json','inherited_sources_v1.txt','operational_scope_inventory_v1.json','operational_scope_inventory_v1.txt']
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 sources=[];raw={}
 for name in FILES:
  p=ROOT/W/name;b=p.read_bytes();assert not any(x in b for x in [b'/Users/',b'/var/folders/',b'/opt/miniconda',b'ghp_',b'github_pat_'])
  raw[name]=b;sources.append({'path':str(W/name),'sha256':sha(b),'bytes':len(b),'url':'https://github.com/HaibinLai/Voynich-manuscript/blob/main/'+str(W/name)})
 contract=json.loads(raw['source_observation_protocol_v1.json']);by_path={s['path']:s['sha256'] for s in sources}
 assert contract['protocol_sha256']==by_path[str(W/'source_observation_protocol_v1.txt')]
 for ref in contract['input_bindings']:
  if ref['path'] in by_path:assert by_path[ref['path']]==ref['sha256']
 old_sources=json.loads(raw['inherited_sources_v1.json']);old_scope=json.loads(raw['operational_scope_inventory_v1.json'])
 assert [x['id'] for x in old_sources['rows']]==['F03','F04','F06']
 assert [x['entry_id'] for x in old_scope['entries']]==['F01','F02','F03','F04','F05','F06']
 assert sum(len(e['existing_units']) for e in old_scope['entries'])==18 and sum(len(e['joins_verbatim']) for e in old_scope['entries'])==14
 assert len(old_sources['old_morgan_detail_attempts'])==6 and len(old_sources['unrequested_literal_image_sources'])==12
 outputs=[]
 def write(path,b):
  p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);outputs.append({'path':str(path),'sha256':sha(b),'bytes':len(b)})
 refs={}
 for key,name in [('inherited_sources','inherited_sources_v1.json'),('inherited_scope','operational_scope_inventory_v1.json')]:
  rel=Path('site/data/source-geometry7h')/name;write(rel,raw[name]);refs[key]={'url':str(rel.relative_to('site')),'sha256':sha(raw[name]),'source_path':str(W/name)}
 d={'schema':'source_geometry_viewer_preview_v1','display_mode':'LOCAL_INHERITED_RECORD_PREVIEW','current_records_connected':False,'session':json.loads(raw['session_v1.json']),'fixed_entry_order':['F01','F02','F03','F04','F05','F06'],'priority_source_entries':['F03','F04','F06'],'inherited_payloads':refs,'current_source_qualification':None,'current_observation_records':None,'current_comparison':None,'common_g_mapping':None,'new_H_H4_results':None,'private_images_exported':False,'sources':sources,'limitations':['只接入继承库存；库存不是本轮新观察。','未接入不是未查看或资格失败的结论，真实执行以冻结记录为准。','两份记录均须注明实际查看或仅文字审查；同AI、已曝光，不称独立历史证据。','未决、像素不足、未查看、不适用、缺单位账本分别保留。']}
 b=(json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode();write(Path('site/data/source-geometry7h.json'),b)
 html=ROOT/'site/source-geometry7h.html';text=html.read_text();text=re.sub(r'(<meta name="source-geometry-snapshot" content=")[^"]*',lambda m:m[1]+sha(b)[:16],text)
 for name in ['source-geometry7h.js','source-geometry7h.css']:text=re.sub(re.escape(name)+r'\?v=[A-Za-z0-9_-]+',name+'?v='+sha((ROOT/'site'/name).read_bytes())[:16],text)
 write(Path('site/source-geometry7h.html'),text.encode())
 for name in ['source-geometry7h.js','source-geometry7h.css']:
  p=Path('site')/name;outputs.append({'path':str(p),'sha256':sha((ROOT/p).read_bytes()),'bytes':(ROOT/p).stat().st_size})
 receipt={'schema':'source_geometry_skeleton_build_v1','state':'LOCAL_PREVIEW_NOT_A_RELEASE_SNAPSHOT','sources':sources,'outputs':outputs,'source_inventory_only':True,'new_observations_read':False,'new_scientific_calculation':False,'private_images_exported':False,'inherited_counts':{'entries':6,'units':18,'joins_including_candidates':14,'old_failed_or_wrong_target_attempts':6,'unverified_placeholder_links':12},'count_scope':'Existing registry entries, not morphology counts, completeness or new observations.'}
 (ROOT/W/'publication/skeleton_build_v1.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'inputs':len(sources),'outputs':len(outputs),'state':receipt['state']}))
if __name__=='__main__':main()
