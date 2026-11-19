"""Explicit frozen-source adapter. Integrity checks never infer scientific judgments."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
MANIFEST=Path('scripts/block_roles_reviewed_manifest_v1.json')
LEDGER='research/research_next/astronomical7h_20261118/zodiac_object_relations/block_role_ledger/'
def sha(data):return hashlib.sha256(data).hexdigest()
def safe_path(name):
 p=Path(name)
 if p.is_absolute() or '..' in p.parts:raise ValueError('Repository-relative path required: '+str(name))
 return ROOT/p

def augment(payload,approval_path=None):
 manifest_bytes=safe_path(MANIFEST).read_bytes();manifest=json.loads(manifest_bytes)
 deps={d['file']:d['sha256'] for d in manifest['dependencies']};assert len(deps)==len(manifest['dependencies'])
 blobs={};docs={}
 for name,digest in deps.items():
  b=safe_path(name).read_bytes();assert sha(b)==digest,('dependency hash',name);blobs[name]=b
  if name.endswith('.json'):docs[name]=json.loads(b)
 def ref_value(ref):
  name=ref['file'];assert name in deps and deps[name]==ref['sha256'],('unbound reference',name)
  value=docs[name]
  pointer=ref.get('json_pointer','');assert not pointer or pointer.startswith('/')
  for k in pointer.split('/')[1:]:
   k=k.replace('~1','/').replace('~0','~');value=value[int(k)] if isinstance(value,list) else value[k]
  if 'original_field_value' in ref:assert value==ref['original_field_value'],('reference value',name,pointer)
  return value
 def validate_refs(value):
  if isinstance(value,dict):
   if isinstance(value.get('file'),str) and re.fullmatch('[0-9a-f]{64}',str(value.get('sha256',''))) and 'json_pointer' in value:ref_value(value)
   for item in value.values():validate_refs(item)
  elif isinstance(value,list):
   for item in value:validate_refs(item)
 root_file=manifest['root_report_path'];assert deps[root_file]==manifest['root_report_sha256'];root=docs[root_file]
 assert root['schema']=='all322_root_role_adjudication_v1' and len(root['rows'])==322
 indexed={r['region_uid']:r for r in payload['rows']};assert len(indexed)==322
 root_ids=[r['region_uid'] for r in root['rows']];assert len(set(root_ids))==322 and set(root_ids)==set(indexed)
 groups=[('site_reviews_circle','astronomical_site','circle_spatial_observer'),('literature_reviews_site','literature','astronomical_site'),('root_reviews_literature','root','literature')]
 reviews={}
 for group,reviewer,subject in groups:
  name=LEDGER+'cross_reviews/'+group+'/report_v1.json';doc=docs[name];key='reviewed_rows' if group=='root_reviews_literature' else 'rows'
  validate_refs(doc)
  for i,r in enumerate(doc[key]):
   uid=r['region_uid'];assert uid not in reviews
   src={'file':name,'sha256':deps[name],'json_pointer':f'/{key}/{i}'}
   # The original reviewers explicitly reviewed v1, even where root selected a representation-only v2.
   binding=subject+':v1';assert binding in [v['version_id'] for v in indexed[uid]['coding_versions']]
   if group=='site_reviews_circle':role,whole,H=r['role_review'],r['whole_window_review'],r['H_review']
   elif group=='literature_reviews_site':
    role={'verdict':'原文角色意见','reason':r['role_judgment']}
    whole={'verdict':r['verdict'],'reason':r['whole_window_and_H_judgment'],'combined_scope_and_H_in_source':True};H=whole
   else:
    role={'verdict':r['role_verdict'],'reason':r['reason']}
    whole={'verdict':r['whole_window_H_verdict'],'reason':r['reason'],'combined_scope_and_H_in_source':True};H=whole
   reviews[uid]={'review_id':group+':'+uid,'reviewer':reviewer,'coding_version_id':binding,'source':src,'role_review':role,'whole_window_review':whole,'H_review':H,'raw_record':r}
 assert set(reviews)==set(indexed)
 validate_refs(root)
 for i,r in enumerate(root['rows']):
  row=indexed[r['region_uid']];assert row['original']['box_xyxy']==r['original_box_xyxy']
  selected=next(v for v in row['coding_versions'] if v['version_id']==r['selected_coding_version'])
  assert selected['source']==r['selected_coding_source'] and ref_value(r['selected_coding_source'])==selected['record']
  assert all(selected['record'].get(k)==v for k,v in r['original_scientific_record'].items())
  rev=reviews[r['region_uid']];assert r['review_id']==rev['review_id'] and r['review_source']==rev['source']
  assert ref_value(r['review_source'])==rev['raw_record'];ref_value(r['root_review_source'])
  # Context fields are explicitly inherited from selected coding; all scientific decision fields remain exact.
  display=dict(selected['record']);display.update(r['decision_record']);display['source_refs']=r['source_refs']
  assert all(display[k]==v for k,v in r['decision_record'].items())
  row['cross_reviews']=[rev];row['cross_review_import_state']='IMPORTED';row['root_import_state']='IMPORTED'
  row['root_adjudication']={'state':'adjudicated','source':{'file':root_file,'sha256':deps[root_file],'json_pointer':f'/rows/{i}'},'reviewed_version_ids':[r['selected_coding_version']],'review_ids':[r['review_id']],'decision_record':r['decision_record'],'display_record':display,'display_context_source':r['selected_coding_source'],'reason':r['reason'],'raw_record':r,'unresolved_cross_review_difference':r['unresolved_cross_review_difference']}
 challenge_file=LEDGER+'cross_reviews/literature_challenges_root_scope/report_v1.json';challenge=docs[challenge_file]
 assert deps[challenge_file]=='09765395547bebfae0ea29511147118e2f917274bd93840e70a7f42f4bc5ef5d'
 assert challenge['schema']=='literature_eight_scope_adversarial_review_v1' and len(challenge['rows'])==8
 validate_refs(challenge)
 acceptance_file=LEDGER+'scientific_acceptance_v1.json';acceptance=docs[acceptance_file]
 assert deps[acceptance_file]=='fd8c2fd7e2e4425b5ded8ac2e9683464557dcdda49e327d5ed4cf6fd67502e2c'
 assert acceptance['root_report']=={'file':root_file,'sha256':deps[root_file]} and acceptance['challenge_report']=={'file':challenge_file,'sha256':deps[challenge_file]}
 assert acceptance['full_sequence_gate_unchanged'] is True and acceptance['new_word_meaning_or_decipherment'] is False
 accepted={r['region_uid']:r for r in acceptance['manual_scope_cases']}
 assert set(accepted)=={r['region_uid'] for r in challenge['rows']} and len(accepted)==8
 for i,r in enumerate(challenge['rows']):
  indexed[r['region_uid']]['root_adjudication']['targeted_challenge_review']={'source':{'file':challenge_file,'sha256':deps[challenge_file],'json_pointer':f'/rows/{i}'},'raw_record':r,'exposure':challenge['exposure'],'scope':'知情且有既往参与的针对性反证审查，不是第二次独立复核或多数投票。','root_acceptance':accepted[r['region_uid']]}
 payload['scientific_acceptance']={'source':{'file':acceptance_file,'sha256':deps[acceptance_file]},'raw_record':acceptance}
 assert sum(len(r['original']['all_fine_alternatives']) for r in payload['rows'])==358
 publication={'state':'REVIEWED_DRAFT_PENDING_APPROVAL','notice':'已接入完整原判断、表示更正、第二复核与根裁定。当前为待发布批准的本地展示稿；针对性反证审查及其限度已附对应条目；完整序列资格不变，不计算成功率。','approval':None}
 downloads={}
 for d in manifest['additional_downloads']:
  name=d['file'];url='downloads/block-roles/'+d['name'];downloads[url]=blobs[name]
  payload['downloads'].append({'label':name.removeprefix(LEDGER),'url':url,'sha256':deps[name]})
 manifest_url='downloads/block-roles/reviewed-source-manifest.json';downloads[manifest_url]=manifest_bytes
 payload['downloads'].append({'label':'公开构建依赖清单（仓库相对路径）','url':manifest_url,'sha256':sha(manifest_bytes)})
 if approval_path:
  ap=Path(approval_path)
  if ap.is_absolute():ap=ap.resolve().relative_to(ROOT)
  ab=safe_path(ap).read_bytes();a=json.loads(ab)
  assert a['schema']=='block_roles_release_approval_v1' and a['approved_by']=='root' and a['release_approved'] is True
  assert a['root_report_path']==root_file and a['root_report_sha256']==deps[root_file]
  assert a['reviewed_manifest_path']==str(MANIFEST) and a['reviewed_manifest_sha256']==sha(manifest_bytes)
  assert isinstance(a.get('scientific_status'),str) and a['scientific_status'].strip()
  publication={'state':'APPROVED_BOUNDED_FINDINGS','notice':a['scientific_status'],'approval':{'file':str(ap),'sha256':sha(ab)}}
  url='downloads/block-roles/publication-approval.json';downloads[url]=ab;payload['downloads'].append({'label':'发布批准及限制','url':url,'sha256':sha(ab)})
 payload['publication']=publication;payload['default_stage']='root';payload['reviewed_source_manifest']={'file':str(MANIFEST),'sha256':sha(manifest_bytes)}
 payload['scientific_aggregates']=None
 return downloads
