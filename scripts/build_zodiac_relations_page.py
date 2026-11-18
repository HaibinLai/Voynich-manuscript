#!/usr/bin/env python3
"""Rebuild the local relations viewer from an explicit frozen public allowlist.
No new image observations or relationship calculations. Release requires a
root approval bound to the real audit and qualification reports.
"""
import argparse, hashlib, json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
SOURCE=ROOT/'research/research_next/astronomical7h_20261118/zodiac_object_relations'
SITE=ROOT/'site'
FILES=('aggregation_v1.json','aggregation_input_freeze_v1.json','aggregation_output_freeze_v1.json')
PUBLIC_NAMES=dict(zip(FILES,('aggregation.json','input-freeze.json','output-freeze.json')))
OUTPUT_SHA='aa454ec718520c739864d44a913c794e1f2a89614e9d4267c512c34247c43f7e'
INPUT_SHA='94a3a65082621c51fa81eec5850acb5689b16e324ed433019b76d2be463a0d41'
ORDER=['f70v1','f70v2','f71r','f71v','f72r1','f72r2','f72r3','f72v3','f72v2','f72v1','f73r','f73v']
def sha(b):return hashlib.sha256(b).hexdigest()
APPROVAL_SHA='995387c0146708ae8d785b4ddb016d1ad04cde006b5180df0073ba0051b7f8aa'
def release_inputs(path,raw):
 assert path.resolve()==(SOURCE/'publication_approval_v1.json').resolve()
 approval_bytes=path.read_bytes();assert sha(approval_bytes)==APPROVAL_SHA
 approval=json.loads(approval_bytes)
 assert approval['schema']=='zodiac_relations_release_approval_v1'
 assert approval['approved_by']=='root' and approval['release_approved'] is True
 assert approval['aggregation_path']=='aggregation_v1.json' and approval['aggregation_sha256']==sha(raw['aggregation_v1.json'])
 assert approval['input_freeze_sha256']==INPUT_SHA and approval['output_freeze_sha256']==OUTPUT_SHA
 required={
  'independent_audit':('record_aggregation_verified','independent_aggregation_audit/audit_report_v1.json'),
  'sequence_qualification':('complete_target_sequence_insufficient','sequence_qualification/qualification_ledger_v1.json')}
 reports={};out={'publication-approval.json':approval_bytes};dependencies=[]
 def read_source(relative):
  file=SOURCE/relative;assert file.resolve().is_relative_to(SOURCE.resolve())
  b=file.read_bytes();dependencies.append({'path':str(file.relative_to(ROOT)),'sha256':sha(b)});return b
 for key,(state,relative) in required.items():
  ref=approval[key];assert ref['state']==state and ref['report_path']==relative
  b=read_source(relative);assert sha(b)==ref['report_sha256'];reports[key]=json.loads(b)
  out[('independent-audit' if key=='independent_audit' else 'sequence-qualification')+'.json']=b
 audit=reports['independent_audit'];qual=reports['sequence_qualification']
 assert audit['schema']=='independent_aggregation_audit_report_v1' and audit['status']=='record_aggregation_verified'
 assert audit['all_passed_for_declared_scope'] is True and audit['differences']==0
 assert audit['comparison_operations']==196532 and audit['root_implementation_opened_or_imported'] is False
 assert audit['expectation_frozen_before_root_results_read'] is True and audit['visual_judgments_independently_revalidated'] is False
 assert audit['fixed_denominators']==dict(panels=12,text_regions=322,original_components=606,fine_alternative_records=358)
 assert qual['schema']=='all12_sequence_qualification_ledger_v1'
 assert qual['full_fixed_scope']['panels']==ORDER
 assert qual['cross_panel_complete_target_sequence']['status']=='insufficient'
 assert qual['cross_panel_complete_target_sequence']['new_prediction_or_matching_performed'] is False
 assert qual['whole_window_completed'] is False
 role=qual['single_layout_candidate_role_check']
 assert len(role['rows'])==9 and role['all_are_central_ordinary_annotation_candidates'] is True and role['no_peripheral_or_ZC02_members'] is True
 review_b=read_source('publication_input_review_v1.json');assert sha(review_b)==approval['root_input_review_sha256']
 review=json.loads(review_b);assert review['schema']=='root_full12_publication_input_review_v1' and review['all_checks_passed'] is True
 out['root-input-review.json']=review_b
 audit_text=read_source('independent_aggregation_audit/audit_report_v1.txt');assert sha(audit_text)==audit['notes_sha256']
 qual_text=read_source('sequence_qualification/qualification_ledger_v1.txt')
 assert sha(qual_text)==review['file_hashes_verified'][str((SOURCE/'sequence_qualification/qualification_ledger_v1.txt').relative_to(ROOT))]
 out['independent-audit.txt']=audit_text;out['sequence-qualification.txt']=qual_text
 qfreeze_b=read_source('sequence_qualification/output_freeze_v1.json');qfreeze=json.loads(qfreeze_b)
 for name in ['qualification_ledger_v1.json','qualification_ledger_v1.txt']:
  content=out['sequence-qualification.'+name.rsplit('.',1)[1]]
  assert sha(content)==next(x['sha256'] for x in qfreeze['files'] if x['path']==name)
 out['qualification-output-freeze.json']=qfreeze_b
 followup=read_source('root_f72v2_zi01_followup/root_observation_v1.json');ffreeze=read_source('root_f72v2_zi01_followup/output_freeze_v1.json')
 assert sha(followup)==json.loads(ffreeze)['files']['root_observation_v1.json']=='f1adc1c50f7d0d714d63eaed5743380ecfe76670e7a02b3843f1f258c331d055'
 out['f72v2-zi01-followup.json']=followup;out['f72v2-zi01-followup-freeze.json']=ffreeze
 # These root-authored publication files are required; never create substitutes.
 out['report.txt']=read_source('aggregation_report_v1.txt')
 out['public-manifest.json']=read_source('public_manifest_v1.json')
 manifest=json.loads(out['public-manifest.json'])
 assert manifest['schema']=='zodiac_full12_public_source_manifest_v1'
 assert manifest['paths_relative_to']=='repository_root'
 assert manifest['file_count']==len(manifest['files'])==200
 for item in manifest['files']:
  file=ROOT/item['path'];assert file.resolve().is_relative_to(ROOT.resolve())
  content=file.read_bytes();assert sha(content)==item['sha256'] and len(content)==item['bytes'],item['path']
 listed={x['path']:x['sha256'] for x in manifest['files']}
 for item in dependencies:
  if item['path']!=str((SOURCE/'public_manifest_v1.json').relative_to(ROOT)):
   assert listed[item['path']]==item['sha256'],item['path']
 summary={'scientific_status':approval['scientific_status'],'record_audit':{'status':audit['status'],'operations':audit['comparison_operations'],'differences':audit['differences'],'visual_revalidation':False},'sequence_qualification':qual['cross_panel_complete_target_sequence'],'single_layout_candidate_role_check':role,'scope':approval['scope']}
 summary['public_sources']={'files':manifest['files'],'paths_relative_to':'repository_root','rebuild_command':manifest['rebuild_command']}
 return approval,out,summary,dependencies

def build():
 ap=argparse.ArgumentParser(description=__doc__);mode=ap.add_mutually_exclusive_group(required=True);mode.add_argument('--preview',action='store_true');mode.add_argument('--release-approval',type=Path);args=ap.parse_args()
 raw={n:(SOURCE/n).read_bytes() for n in FILES};f=json.loads(raw['aggregation_output_freeze_v1.json']);a=json.loads(raw['aggregation_v1.json'])
 assert sha(raw[FILES[2]])==OUTPUT_SHA and sha(raw[FILES[1]])==INPUT_SHA
 assert f['input_freeze_sha256']==INPUT_SHA
 assert next(x['sha256'] for x in f['files'] if x['path']==FILES[0])==sha(raw[FILES[0]])
 assert a['fixed_panel_order']==ORDER==[p['panel'] for p in a['panels']]
 assert a['pending_panels']==[] and a['all_twelve_frozen_inputs_present']
 totals={'text':0,'original_components':0,'additional_components':0,'fine':0,'aliases':0,'body_edges':0,'receipts':0}
 for p in a['panels']:
  s=p['full_original_seed'];r=p['full_frozen_report'];im=p['original_image']
  assert im['official_url']==f"https://collections.library.yale.edu/iiif/2/{im['canvas_id']}/full/full/0/default.jpg"
  assert len(im['dimensions_px'])==2 and all(isinstance(n,int) and n>0 for n in im['dimensions_px'])
  original={x['component_uid'] for x in s['object_components']};components={x['component_uid'] for x in r['object_component_reviews']};aliases={x['component_uid'] for x in r['discovered_supplements']}
  texts={x['region_uid'] for x in s['text_records']};assert original<=components
  assert texts=={x['region_uid'] for x in r['text_records']}=={x['region_uid'] for x in p['text_rows']}
  assert len(components)==len(r['object_component_reviews']) and len(texts)==len(p['text_rows'])
  for row in p['text_rows']:
   assert row['original_seed_record']==next(x for x in s['text_records'] if x['region_uid']==row['region_uid'])
   assert row['observation']==next(x for x in r['text_records'] if x['region_uid']==row['region_uid'])
   assert set(row['observation']['candidate_object_ids'] or [])<=components|aliases
  totals['text']+=len(texts);totals['original_components']+=len(original);totals['additional_components']+=len(components-original)
  totals['fine']+=len(s['fine_alternatives_original']);totals['aliases']+=len(r['discovered_supplements']);totals['body_edges']+=sum(x['edge_kind']=='body_to_pointed' for x in r['relation_edges']);totals['receipts']+=len(r['view_receipts'])
 assert totals==dict(text=322,original_components=606,additional_components=40,fine=358,aliases=5,body_edges=307,receipts=797),totals
 assert len({p['original_image']['canvas_id'] for p in a['panels']})==8
 payload={'schema':'zodiac_relations_site_v1','publication_status':'PREVIEW_AUDIT_AND_QUALIFICATION_PENDING','status_note':'独立算术审核与科学资格账本仍在进行。当前为本地可检查版本；记录完整不代表命名或词义资格通过。','source_sha256':sha(raw[FILES[0]]),'output_freeze_sha256':OUTPUT_SHA,'input_freeze_sha256':INPUT_SHA,'consistency_counts':totals,'downloads':[{'name':n,'url':'downloads/zodiac-relations/'+PUBLIC_NAMES[n],'sha256':sha(raw[n])} for n in FILES],'aggregation':a}
 release_downloads={}
 if args.release_approval:
  approval,release_downloads,assessment,deps=release_inputs(args.release_approval,raw)
  payload.update(publication_status='APPROVED_BOUNDED_FINDINGS',status_note='可公开：记录汇编已独立复算一致；完整同角色目标文字序列证据仍不足。未运行词义预测，也不是研究成功或窗口终点验收。',assessment=assessment,release_dependencies=deps,approval_sha256=APPROVAL_SHA)
  payload['downloads'] += [{'name':name,'url':'downloads/zodiac-relations/'+name,'sha256':sha(b)} for name,b in release_downloads.items()]
 content=(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n').encode();version=sha(content)[:16]
 (SITE/'data').mkdir(exist_ok=True);(SITE/'data/zodiac-relations.json').write_bytes(content)
 out=SITE/'downloads/zodiac-relations';out.mkdir(parents=True,exist_ok=True)
 for n,b in raw.items():(out/PUBLIC_NAMES[n]).write_bytes(b)
 for n,b in release_downloads.items():(out/n).write_bytes(b)
 html=SITE/'zodiac-relations.html';text=html.read_text()
 text=re.sub(r'(<meta name="zodiac-relations-snapshot" content=")[^"]*',r'\g<1>'+version,text)
 for ext in ('js','css'):
  digest=sha((SITE/f'zodiac-relations.{ext}').read_bytes())[:16]
  text=re.sub(r'zodiac-relations\.'+ext+r'\?v=[a-zA-Z0-9_-]+',f'zodiac-relations.{ext}?v={digest}',text)
 text=re.sub(r'(<p class="zr-notice" id="zr-audit">).*?(</p>)',lambda m:m[1]+payload['status_note']+m[2],text,flags=re.S)
 html.write_text(text)
 print(json.dumps({'mode':payload['publication_status'],'version':version,'verified_counts':totals,'download_files':list(FILES),'data_bytes':len(content)},ensure_ascii=False))
if __name__=='__main__':build()
