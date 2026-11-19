#!/usr/bin/env python3
"""Draft-only viewer projection of three original codings and two corrections.
No cross-review/root verdict read or inferred. No scientific aggregates produced.
"""
import argparse,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
BASE=ROOT/'research/research_next/astronomical7h_20261118/zodiac_object_relations'
LEDGER=BASE/'block_role_ledger';SITE=ROOT/'site'
FILES={
 'astronomical_site/report_v1.json':'70312181bf701daf39e5da44bd1b4c7a7003a06ec201dd2023bc05e139b80db0',
 'circle_spatial_observer/report_v1.json':'cdde5039303e732bd5e5677722d9ec2153f6aad04fec6bfcafcd52f7d57db2cb',
 'literature/report_v1.json':'ce79e4de8cbfabaa36ad1c54f7c31b434523b89507812efe4d0fcb56d3b8a174',
 'circle_spatial_observer/report_v2.json':'dfb38c10d340751fd7e40d0e273640561310ff0d3346d8b525fc7d9b360edb27',
 'literature/report_v2.json':'66b906836b55e8a98a5702365867a5e3b1b6f3c074d3d372c44ec2d4b96d436b',
 'circle_spatial_observer/correction_v2.json':'501813e3ecb0e0af0fa1623acc5adb432a176ce4dbfce1ced8f9a11ca9fdf79d',
 'literature/correction_v2.json':'a2a831cc4e1f59951b4542ff0eb35b98b9e6e529e37b3dee0fa7011ab742f2bf',
 'execution_protocol_v1.txt':'46b7ee998fad8fca078e4a88bdc003a5f13edc84d4755359514b43b5f0c46149'}
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__);mode=ap.add_mutually_exclusive_group(required=True);mode.add_argument('--draft',action='store_true');mode.add_argument('--reviewed-draft',action='store_true');mode.add_argument('--release-approval');args=ap.parse_args()
 raw={n:(LEDGER/n).read_bytes() for n in FILES}
 for n,b in raw.items():assert sha(b)==FILES[n],n
 docs={n:json.loads(b) for n,b in raw.items() if n.endswith('.json')}
 agg_bytes=(BASE/'aggregation_v1.json').read_bytes();assert sha(agg_bytes)=='098146849c43435b1d612185b46b6068638e374681bce1e1f3fa1571c681b2a4'
 agg=json.loads(agg_bytes);originals={};versions={};corrections={}
 for observer in ['astronomical_site','circle_spatial_observer','literature']:
  for ver in ['v1','v2']:
   name=f'{observer}/report_{ver}.json'
   if name not in docs:continue
   for i,row in enumerate(docs[name]['rows']):
    uid=row['region_uid'];entry={'version_id':observer+':'+ver,'observer_id':observer,'source':{'file':str((LEDGER/name).relative_to(ROOT)),'sha256':FILES[name],'json_pointer':f'/rows/{i}'},'record':row}
    versions.setdefault(uid,[]).append(entry)
    if ver=='v1':assert uid not in originals;originals[uid]=row
 for observer in ['circle_spatial_observer','literature']:
  name=f'{observer}/correction_v2.json';c=docs[name]
  assert c['old_report_sha256']==FILES[f'{observer}/report_v1.json'] and c['new_report_sha256']==FILES[f'{observer}/report_v2.json']
  key='changes' if 'changes' in c else 'exact_row_field_changes'
  for i,change in enumerate(c[key]):corrections.setdefault(change['region_uid'],[]).append({'source':{'file':str((LEDGER/name).relative_to(ROOT)),'sha256':FILES[name],'json_pointer':f'/{key}/{i}'},'change_record':change})
 panels=[];rows=[];fine_count=0
 for p in agg['panels']:
  im=p['original_image'];s=p['full_original_seed'];assert im['official_url']==f"https://collections.library.yale.edu/iiif/2/{im['canvas_id']}/full/full/0/default.jpg"
  panels.append({'panel':p['panel'],'canvas_id':im['canvas_id'],'official_url':im['official_url'],'dimensions_px':im['dimensions_px'],'original_panel_box_xyxy':s['original_panel_box_xyxy'],'original_image_sha256':im['sha256']})
  fine_count+=len(s['fine_alternatives_original'])
  for seed in s['text_records']:
   uid=seed['region_uid'];r=originals[uid];assert r['original_box_xyxy']==seed['original_box_xyxy'] and r['original_band']==seed['ring_assignment_original']
   for v in versions[uid]:assert v['record']['original_box_xyxy']==seed['original_box_xyxy'] and v['record']['candidate_object_ids_context_only']==r['candidate_object_ids_context_only']
   rows.append({'region_uid':uid,'panel':p['panel'],'original':{'box_xyxy':seed['original_box_xyxy'],'band_metadata_only':seed['ring_assignment_original'],'roster_class':seed['roster_class'],'full_seed_record':seed,'all_fine_alternatives':[f for f in s['fine_alternatives_original'] if f['coarse_parent_id']==seed['original_id']]},'coding_versions':versions[uid],'corrections':corrections.get(uid,[]),'cross_reviews':[],'cross_review_import_state':'NOT_IMPORTED','root_adjudication':None,'root_import_state':'NOT_IMPORTED'})
 assert len(rows)==len(originals)==322 and fine_count==358 and len({r['region_uid'] for r in rows})==322
 assert sum(len(r['original']['all_fine_alternatives']) for r in rows)==358
 downloads=[]
 for n,b in raw.items():downloads.append({'label':n,'url':'downloads/block-roles/'+n.replace('/','-'),'sha256':sha(b)})
 payload={'schema':'block_roles_viewer_v1','publication':{'state':'DRAFT_UNAPPROVED','notice':'展示草稿：原判断与表示更正可查；交叉复核及根最终裁定尚未接入，不显示未审定科学汇总。','approval':None},'fixed_universe':{'total':322,'region_ids':[r['region_uid'] for r in rows],'sequence_gate_changed':False},'panels':panels,'rows':rows,'downloads':downloads,'source_aggregation':{'file':str((BASE/'aggregation_v1.json').relative_to(ROOT)),'sha256':sha(agg_bytes)},'scientific_aggregates':None}
 extra_downloads={}
 if args.reviewed_draft or args.release_approval:
  from block_roles_reviewed_adapter import augment
  extra_downloads=augment(payload,args.release_approval)
 content=(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n').encode()
 assert not any(token in content for token in [b'/Users/',b'/private/var/',b'/home/'])
 (SITE/'data').mkdir(exist_ok=True);(SITE/'data/block-roles.json').write_bytes(content)
 out=SITE/'downloads/block-roles';out.mkdir(exist_ok=True,parents=True)
 for n,b in raw.items():(out/n.replace('/','-')).write_bytes(b)
 for url,b in extra_downloads.items():(SITE/url).write_bytes(b)
 html=SITE/'block-roles.html';text=html.read_text();text=re.sub(r'(<meta name="block-roles-snapshot" content=")[^"]*',r'\g<1>'+sha(content)[:16],text)
 for ext in ['js','css']:text=re.sub(r'block-roles\.'+ext+r'\?v=[a-zA-Z0-9_-]+','block-roles.'+ext+'?v='+sha((SITE/f'block-roles.{ext}').read_bytes())[:16],text)
 html.write_text(text)
 print(json.dumps({'state':payload['publication']['state'],'fixed_IDs_retained':322,'fine_records_retained':358,'cross_reviews_imported':bool(extra_downloads),'root_adjudications_imported':bool(extra_downloads),'scientific_aggregates_produced':False,'data_sha256':sha(content)},ensure_ascii=False))
if __name__=='__main__':main()
