#!/usr/bin/env python3
"""Build fixed contact diagnostics. Preview contains no judgments. Release mode
validates the frozen comparison, source reports and bounded root approval. No
working drafts are read and no image or semantic judgments are calculated.
"""
import argparse,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
SOURCE=ROOT/'research/research_next/astronomical7h_20261118/zodiac_object_relations/f73r_contact_followup'
SITE=ROOT/'site'
INPUTS={
 'protocol_v1.txt':'7c4c604ee46bdc9546798ff0f18b4ceffb93a915bd4e7d02f43b5a18da65ba73',
 'input_freeze_v1.json':'f41ac673b607f2e6938530dac265d4349b2550aae7fd4a7e6b06b6c295be8aa0',
 'prepared_views_v1.json':'3027ed76f07f9ef3f8a63b3c6be4ac6731b61e6bbc384f58322c74d2383f418e',
 'root_repeat/output_freeze_v1.json':'474608fe1e7ee2241b8d0624f3dd60472f5caef4ab303c2efbe244b8fde1061e'}
NAMES=dict(zip(INPUTS,('protocol.txt','input-freeze.json','prepared-views.json','root-output-freeze.json')))
MODES=['original','expanded80','candidate_context']
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__);g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--preview',action='store_true');g.add_argument('--release-approval',type=Path);args=ap.parse_args()
 raw={n:(SOURCE/n).read_bytes() for n in INPUTS}
 for n,b in raw.items():assert sha(b)==INPUTS[n],n
 fixed=json.loads(raw['input_freeze_v1.json']);views=json.loads(raw['prepared_views_v1.json'])
 assert views['input_freeze_sha256']==INPUTS['input_freeze_v1.json']
 assert len(fixed['fixed_region_ids'])==9 and len(views['views'])==27
 assert len({v['view_id'] for v in views['views']})==27
 im=fixed['original_image'];w,h=im['dimensions_px']
 assert im['official_url']==f"https://collections.library.yale.edu/iiif/2/{im['canvas_id']}/full/full/0/default.jpg"
 candidates={p['candidate']:p for p in fixed['pairs']};controls={p['control']:p for p in fixed['pairs'] if p['control'] is not None}
 assert len(candidates)==5 and len(controls)==4
 records=[]
 for uid in fixed['fixed_region_ids']:
  vv=[v for v in views['views'] if v['region_uid']==uid];assert [v['mode'] for v in vv]==MODES
  for v in vv:
   x0,y0,x1,y1=v['crop_xyxy_original'];assert 0<=x0<x1<=w and 0<=y0<y1<=h
   assert v['dimensions_px']==[x1-x0,y1-y0] and v['prepared_only_not_viewed'] is True
  a=vv[0]['crop_xyxy_original'];assert vv[1]['crop_xyxy_original']==[max(0,a[0]-80),max(0,a[1]-80),min(w,a[2]+80),min(h,a[3]+80)]
  pairing=candidates.get(uid) or controls[uid]
  records.append({'region_uid':uid,'fixed_role':'P_source' if uid in candidates else 'same_band_N_control','pairing':pairing,'views':vv,'original_record':None,'root_repeat':None,'other_repeat':None,'comparison':None,'content_state':'NOT_IMPORTED_AWAITING_FROZEN_COMPARISON_AND_RELEASE_APPROVAL'})
 payload={'schema':'f73r_contact_site_preview_v1','publication_status':'UNAPPROVED_PREVIEW','original_image':im,'protocol':raw['protocol_v1.txt'].decode(),'fixed_input':fixed,'root_output_freeze':json.loads(raw['root_repeat/output_freeze_v1.json']),'records':records,'downloads':[{'name':NAMES[n],'url':'downloads/f73r-contacts/'+NAMES[n],'sha256':INPUTS[n]} for n in INPUTS],'limits':['Only fixed scope and prepared crop metadata imported. Neither observer result imported.','Prepared views do not establish actual viewing; root output freeze is distinct from result content.','No comparison conclusion, success rate, original aggregate replacement or sequence qualification.']}
 if args.release_approval:
  approval_path=(ROOT/args.release_approval).resolve();assert approval_path==SOURCE/'publication_approval_v1.json'
  approval=json.loads(approval_path.read_bytes());assert approval['release_approved'] and approval['approved_by']=='root'
  compraw=(SOURCE/'comparison_v1.json').read_bytes();assert sha(compraw)==approval['comparison_sha256']
  freeze_path=SOURCE/'comparison_output_freeze_v1.json';assert sha(freeze_path.read_bytes())==approval['comparison_output_freeze_sha256']
  for x in json.loads(freeze_path.read_bytes())['files']:assert sha((SOURCE/x['path']).read_bytes())==x['sha256']
  for side,key in [('root_repeat','root_observation_sha256'),('literature_repeat','peer_observation_sha256')]:
   assert sha((SOURCE/side/'observation_v1.json').read_bytes())==approval[key]
   for x in json.loads((SOURCE/side/'output_freeze_v1.json').read_bytes())['files']:assert sha((SOURCE/side/x['path']).read_bytes())==x['sha256']
  import subprocess
  replay=subprocess.run(['python3','-B',str(SOURCE/'compare_v1.py')],cwd=ROOT,capture_output=True,check=True);assert replay.stdout==compraw
  comp=json.loads(compraw);lookup={r['region_uid']:r for r in comp['rows']};assert set(lookup)==set(fixed['fixed_region_ids'])
  for r in records:
   for k in ['original_record','root_repeat','other_repeat','comparison']:r[k]=lookup[r['region_uid']][k]
   r['content_state']='FROZEN_INFORMED_DIAGNOSTIC'
  payload['schema']='f73r_contact_site_v1';payload['publication_status']='APPROVED_INFORMED_DIAGNOSTIC';payload['comparison_summary']=comp['summary'];payload['limits']=comp['limits'];payload['publication_approval']=approval
  extras={'comparison_v1.json':'comparison.json','comparison_output_freeze_v1.json':'comparison-freeze.json','comparison_mapping_v1.json':'comparison-mapping.json','root_repeat/observation_v1.json':'root-observation.json','root_repeat/observation_v1.txt':'root-observation.txt','literature_repeat/observation_v1.json':'peer-observation.json','literature_repeat/observation_v1.txt':'peer-observation.txt','literature_repeat/output_freeze_v1.json':'peer-output-freeze.json','report_v1.txt':'report.txt','publication_approval_v1.json':'publication-approval.json'}
  audit_release=json.loads((SOURCE/'audit_release_receipt_v1.json').read_bytes());assert audit_release['publish_independent_record_audit'] and audit_release['comparison_sha256']==sha(compraw)
  for x in audit_release['files']:assert sha((SOURCE/x['path']).read_bytes())==x['sha256']
  payload['independent_record_audit']=json.loads((SOURCE/'independent_comparison_audit/audit_report_v1.json').read_bytes())
  extras.update({'independent_comparison_audit/audit_report_v1.json':'independent-audit.json','independent_comparison_audit/audit_report_v1.txt':'independent-audit.txt','independent_comparison_audit/public_replay_manifest_v1.json':'audit-replay-manifest.json','audit_release_receipt_v1.json':'audit-release.json'})
  for src,name in extras.items():
   raw[src]=(SOURCE/src).read_bytes();NAMES[src]=name;payload['downloads'].append({'name':name,'url':'downloads/f73r-contacts/'+name,'sha256':sha(raw[src])})
 content=(json.dumps(payload,ensure_ascii=False,indent=2)+'\n').encode();version=sha(content)[:16]
 (SITE/'data').mkdir(exist_ok=True);(SITE/'data/f73r-contacts.json').write_bytes(content)
 out=SITE/'downloads/f73r-contacts';out.mkdir(parents=True,exist_ok=True)
 for n,b in raw.items():(out/NAMES[n]).write_bytes(b)
 p=SITE/'f73r-contacts.html';html=p.read_text();html=re.sub(r'(<meta name="f73r-contacts-snapshot" content=")[^"]*',r'\g<1>'+version,html)
 for ext in ['js','css']:html=re.sub(r'f73r-contacts\.'+ext+r'\?v=[a-zA-Z0-9_-]+','f73r-contacts.'+ext+'?v='+sha((SITE/f'f73r-contacts.{ext}').read_bytes())[:16],html)
 notice=('固定诊断补查已公开。两路知情观察与原记录分别保留；没有确认完整文字引线，细节未决仍在。' if args.release_approval else '未批准预览：仅固定范围与裁图，尚未接入正式比较。')
 html=re.sub(r'<p class="fc-notice">.*?</p>','<p class="fc-notice">'+notice+'</p>',html,count=1,flags=re.S)
 html=re.sub(r'(<footer class="site-footer"><span>).*?(</span>)',lambda m:m[1]+('固定诊断样本 · 两路知情补查 · 原记录保留' if args.release_approval else '未批准预览')+m[2],html,flags=re.S)
 p.write_text(html)
 print(json.dumps({'status':payload['publication_status'],'fixed_regions':len(records),'fixed_crop_metadata':len(views['views']),'observer_results_read':bool(args.release_approval),'version':version}))
if __name__=='__main__':main()
