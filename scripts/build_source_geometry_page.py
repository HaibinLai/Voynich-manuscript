#!/usr/bin/env python3
"""Explicit frozen text records to W7 viewer; no private pixels, network or scientific recalculation."""
import argparse,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;W=Path('research/research_next/source_geometry7h_20261119');P=W/'publication'
PHASE_HASHES={'phase_input_v1.json': '2bd6940cc29be01bc5ebf60a58a416fb69bb1f0d119e57a0b578088c93480300', 'phase_input_v2.json': 'e8e1f73f702c8a8c889aa847dc82a8727ee9c5e3c267b3acbdee9588d2be6e2f'}
BASE=[('session','session_v1.json'),('plan','plan_v1.txt'),('protocol','source_observation_protocol_v1.json'),('protocol_text','source_observation_protocol_v1.txt'),('protocol_review','protocol_review_v1.json'),('protocol_review_text','protocol_review_v1.txt'),('inherited_sources','inherited_sources_v1.json'),('inherited_sources_text','inherited_sources_v1.txt'),('inherited_scope','operational_scope_inventory_v1.json'),('inherited_scope_text','operational_scope_inventory_v1.txt'),('source_qualification','source_qualification_v1.json'),('source_qualification_text','source_qualification_v1.txt'),('source_review','source_qualification/source_review_v1.json'),('source_review_text','source_qualification/source_review_v1.txt'),('root_observation','observation/root_observation_v1.json'),('display_receipts','observation/display_receipts_v1.json'),('view_plan','observation/view_plan_v1.json'),('native_addendum','observation/native_view_addendum_v1.json'),('native_crops','observation/native_crop_receipts_v1.json'),('native_identity','observation/F03_native_identity_v1.json'),('method_matrix_draft','method_application_matrix_v1.json'),('method_matrix_draft_text','method_application_matrix_v1.txt'),('availability_and_next_evidence','availability_and_next_evidence_v1.json'),('availability_text','availability_and_next_evidence_v1.txt'),('record_integrity','observation/root_record_integrity_v1.json')]+[(f'request_{kind}_{i:02}',f'source_qualification/request_{kind}_{i:02}.json') for i in range(1,5) for kind in ['plan','receipt']]
BASE.append(('record_integrity_code','../../../scripts/verify_source_geometry_records.py'))
BASE += [('independent_text_review','observation/independent_text_review_v1.json'),('independent_text_review_text','observation/independent_text_review_v1.txt'),('shared_g_mapping','comparison/shared_g_mapping_v1.json'),('shared_g_mapping_text','comparison/shared_g_mapping_v1.txt')]
BASE += [('research_report','research_report_v1.json'),('research_report_text','research_report_v1.txt')]
FINAL=[] # Explicit allowlist only; no directory scan.
def sha(b):return hashlib.sha256(b).hexdigest()
def explicit_inputs(final=False):
 return [{'key':key,'path':(str(W/name) if not name.startswith('../../../') else name.removeprefix('../../../')),'sha256':sha((ROOT/(W/name if not name.startswith('../../../') else Path(name.removeprefix('../../../')))).read_bytes()),'bytes':(ROOT/(W/name if not name.startswith('../../../') else Path(name.removeprefix('../../../')))).stat().st_size,'download_name':key.replace('_','-')+Path(name).suffix} for key,name in BASE+(FINAL if final else [])]
def main():
 ap=argparse.ArgumentParser(description=__doc__);g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--reviewed-draft',action='store_true');g.add_argument('--phase-input');ap.add_argument('--receipt-name',default='reviewed_draft_build_v1.json');a=ap.parse_args();phase_path=None
 if a.reviewed_draft:phase={'schema':'source_geometry_reviewed_draft_v1','state':'FROZEN_ROOT_RECORD_TEXT_REVIEW_NOT_CONNECTED','sources':explicit_inputs()}
 else:
  phase_path=Path(a.phase_input);assert phase_path.parent==P and phase_path.name in PHASE_HASHES and sha((ROOT/phase_path).read_bytes())==PHASE_HASHES[phase_path.name];phase=json.loads((ROOT/phase_path).read_text());assert phase['schema']=='source_geometry_publication_phase_v1';assert phase['final_reports_connected'] is True
 assert Path(a.receipt_name).name==a.receipt_name and a.receipt_name.endswith('.json')
 raw={};docs={};refs={};by_path={};outputs=[]
 for s in phase['sources']:
  p=Path(s['path']);assert not p.is_absolute() and '..' not in p.parts and (p.is_relative_to(Path('research/research_next')) or str(p)=='scripts/verify_source_geometry_records.py');b=(ROOT/p).read_bytes();assert sha(b)==s['sha256'] and len(b)==s['bytes'];assert p.suffix in ['.json','.txt','.py'];assert not any(x in b for x in [b'/Users/',b'/home/',b'/var/folders/',b'/private/var/',b'/opt/miniconda',b'ghp_',b'github_pat_']);assert s['key'] not in raw;raw[s['key']]=b;by_path[str(p)]=s['sha256'];assert Path(s['download_name']).name==s['download_name'];refs[s['key']]={'url':'downloads/source-geometry7h/'+s['download_name'],'sha256':s['sha256'],'source_path':str(p),'repository_url':'https://github.com/HaibinLai/Voynich-manuscript/blob/main/'+str(p)}
  if p.suffix=='.json':docs[s['key']]=json.loads(b)
 obs=docs['root_observation'];views=docs['display_receipts'];old=docs['inherited_scope'];sources=docs['inherited_sources'];q=docs['source_qualification'];review=docs['source_review'];plan=docs['view_plan'];add=docs['native_addendum'];crops=docs['native_crops'];identity=docs['native_identity'];matrix=docs['method_matrix_draft']
 assert refs['root_observation']['sha256']=='ed16491f244e3a77832e751a05099d879d85fe2d22f015329c9ef9de517fe569'
 assert obs['schema']=='seventh_root_image_observation_v1' and obs['scoring_performed'] is False and obs['whole_signature_or_g_resolved'] is False
 ids=['F01','F02','F03','F04','F05','F06'];assert [e['entry'] for e in obs['entries']]==[e['entry_id'] for e in old['entries']]==ids
 assert [e['id'] for e in q['rows']]==[e['id'] for e in sources['rows']]==['F03','F04','F06'];assert q['original_inventory_sha256']==refs['inherited_sources']['sha256'];assert len(q['requests'])==10 and review['all_ten_requests_equal_final_root_qualification'] is True
 assert len(views['records'])==29 and len({v['id'] for v in views['records']})==29
 vp={v['id']:v for v in plan['views']};vp.update({v['id']:v for v in add['new_views']});display={v['id']:v for v in views['records']};assert set(vp)==set(display)
 cropmap={v['id']:v for v in crops['records']};assert crops['addendum_sha256']==refs['native_addendum']['sha256'];assert identity['source_qualification_parent_sha256']==refs['source_qualification']['sha256'];assert plan['source_qualification_sha256']==refs['source_qualification']['sha256'];assert obs['protocol_sha256']==plan['protocol_sha256']==refs['protocol']['sha256']
 for v in views['records']:
  p=vp[v['id']];assert v['entry']==p['entry'] and v['successful_display_confirmed_utc'];assert v['file_sha256']==(cropmap[v['id']]['sha256'] if v['id'] in cropmap else p['sha256']);assert v['original_xywh']==p.get('official_native_xywh',p.get('original_xywh'))
 for e,prior in zip(obs['entries'],old['entries']):
  assert all(x in display for x in e['view_refs']);assert [u['id'] for u in e['units']]==[u['existing_id'] for u in prior['existing_units']]
  assert len(e['joins'])==len(prior['joins_verbatim']) and len(e['bodies'])==len(prior['bodies_verbatim']) and len(e['coverage_review'])==len(prior['coverage_verbatim']);assert e['complete_signature_certified'] is False and e['new_Q_or_H_values_computed'] is False
 assert len(matrix['record_rows'])==69 and len(matrix['complete_case_rows'])==10 and len(matrix['coverage_rows'])==19
 if 'independent_text_review' in docs:
  tr=docs['independent_text_review'];gm=docs['shared_g_mapping'];assert tr['schema']=='seventh_independent_text_review_v1' and tr['reviewer_viewed_images'] is False and tr['second_independent_image_observation'] is False
  assert tr['required_frozen_record_corrections']==tr['material_text_or_reference_contradictions_found']==[] and all(x['pass'] is True for x in tr['checks'])
  assert gm['schema']=='seventh_shared_g_mapping_text_review_v1' and gm['review_binding']['sha256']==refs['independent_text_review']['sha256'];assert gm['global_rule']['selected_g'] is None and all(x is False for x in gm['whole_entry_mapping_qualified'].values())
  key=lambda r:(r['entry'],r['record_kind'],r['existing_id'])
  assert list(map(key,matrix['record_rows']))==list(map(key,tr['record_reviews']))==list(map(key,gm['record_mappings'])) and len(tr['record_reviews'])==69
  def pointer(doc,p):
   for part in p.lstrip('/').split('/'):
    part=part.replace('~1','/').replace('~0','~');doc=doc[int(part)] if isinstance(doc,list) else doc[part]
   return doc
  for r in tr['record_reviews']:
   rr=pointer(obs,r['root_observation_pointer']);assert rr.get('original',rr)['id']==r['existing_id'];assert r['reviewer_pixel_certification'] is False and r['new_Q_assignment'] is None
  for report in [tr,gm,docs['availability_and_next_evidence']]:
   for ref in report.get('source_bindings',report.get('sources',[])):
    if ref['path'] in by_path:assert by_path[ref['path']]==ref['sha256'],ref['path']
  if a.reviewed_draft:phase['state']='LOCAL_REVIEWED_DRAFT_ALL_FROZEN_REPORTS_CONNECTED'
 report=docs['research_report'];assert report['goal_complete_claimed'] is False and report['old_results_changed'] is False and report['report_txt_sha256']==refs['research_report_text']['sha256']
 integrity=docs['record_integrity'];assert integrity['root_observation_sha256']==refs['root_observation']['sha256'] and integrity['display_receipts_sha256']==refs['display_receipts']['sha256'] and integrity['failures']==[] and integrity['script_sha256']==refs['record_integrity_code']['sha256']

 def write(path,b):p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);outputs.append({'path':str(path),'sha256':sha(b),'bytes':len(b)})
 for s in phase['sources']:write(Path('site')/refs[s['key']]['url'],raw[s['key']])
 repository_references=[];seen_refs=set()
 for document in docs.values():
  if not isinstance(document,dict):continue
  for field in ['source_bindings','sources','input_bindings','inputs']:
   for ref in document.get(field,[]) if isinstance(document.get(field,[]),list) else []:
    if not isinstance(ref,dict) or not isinstance(ref.get('path'),str) or not ref['path'].startswith(('research/','scripts/')) or not isinstance(ref.get('sha256'),str):continue
    pair=(ref['path'],ref['sha256'])
    if pair in seen_refs:continue
    seen_refs.add(pair);repository_references.append({'path':ref['path'],'sha256':ref['sha256'],'pointer':ref.get('pointer'),'copied_in_this_snapshot':ref['path'] in by_path,'repository_url':'https://github.com/HaibinLai/Voynich-manuscript/blob/main/'+ref['path'],'scope':'Reference recorded by the frozen source; not an additional recursive download or a fresh pixel check.'})
 data={'schema':'source_geometry_viewer_v1','display_mode':'FROZEN_RECORDS_EXPLICIT_STATE','state':phase['state'],'session':docs['session'],'fixed_entry_order':ids,'priority_source_entries':['F03','F04','F06'],'payloads':refs,'connected':{'source_qualification':True,'image_observation':True,'independent_text_review':'independent_text_review' in refs,'shared_g_mapping':'shared_g_mapping' in refs,'availability_and_next_evidence':'availability_and_next_evidence' in refs},'scope':{'registered_old_records':69,'old_units':18,'old_joins_including_candidate':14,'old_bodies':2,'old_unresolved_regions':15,'old_coverage':19,'old_cases':10,'actual_display_receipts':29,'source_requests':10,'old_source_failures':6,'unknown_placeholder_links':12},'private_pixels_exported':False,'new_H_H4_scores':None,'goal_completion_claimed':False,'source_refs':list(refs.values()),'referenced_repository_dependencies':repository_references,'method_matrix_scope':'Historical old-rule draft; its current_application pending fields are not the latest observation/review state.','observer_design':'One actual image observer and separate text review, same informed AI; not two independent image observations.'}
 b=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode();write(Path('site/data/source-geometry7h.json'),b)
 if phase_path:write(Path('site/downloads/source-geometry7h')/phase_path.name,(ROOT/phase_path).read_bytes())
 html=ROOT/'site/source-geometry7h.html';text=html.read_text();text=re.sub(r'(<meta name="source-geometry-snapshot" content=")[^"]*',lambda m:m[1]+sha(b)[:16],text)
 for n in ['source-geometry7h.js','source-geometry7h.css']:text=re.sub(re.escape(n)+r'\?v=[A-Za-z0-9_-]+',n+'?v='+sha((ROOT/'site'/n).read_bytes())[:16],text)
 write(Path('site/source-geometry7h.html'),text.encode())
 for n in ['source-geometry7h.js','source-geometry7h.css','style.css','favicon.svg']:
  p=Path('site')/n;outputs.append({'path':str(p),'sha256':sha((ROOT/p).read_bytes()),'bytes':(ROOT/p).stat().st_size})
 manifest={'schema':'source_geometry_site_manifest_v1','phase_path':str(phase_path) if phase_path else None,'state':phase['state'],'sources':phase['sources'],'referenced_repository_dependencies':repository_references,'outputs':outputs.copy(),'private_pixels_exported':False,'scientific_calculation':False,'builder_sha256':sha(Path(__file__).read_bytes()),'self_excluded':True};write(Path('site/downloads/source-geometry7h/publication-manifest.json'),(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode())
 receipt={'schema':'source_geometry_page_build_v1','state':phase['state'],'phase_path':str(phase_path) if phase_path else None,'sources':phase['sources'],'outputs':outputs,'source_count':len(raw),'all29_display_references_bound':True,'six_original_entry_ids_preserved':True,'private_pixels_exported':False,'scientific_calculation':False,'data_sha256':sha(b)};out=ROOT/P/a.receipt_name;out.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'sources':len(raw),'outputs':len(outputs),'data_sha256':sha(b),'state':phase['state']}))
if __name__=='__main__':main()
