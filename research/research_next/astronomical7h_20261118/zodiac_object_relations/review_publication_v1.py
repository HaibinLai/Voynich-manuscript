"""Verify frozen publication inputs and every cited qualification field, not image truth."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
checked={};refs=[]
def verify(p,h):
 p=p.resolve();assert p.is_relative_to(ROOT),p
 assert sha(p)==h,(p,h)
 checked[str(p.relative_to(ROOT))]=h
for fname in ['aggregation_input_freeze_v1.json','aggregation_output_freeze_v1.json']:
 for x in read(P/fname)['files']:verify(P/x['path'],x['sha256'])
Q=P/'sequence_qualification'
for x in read(Q/'output_freeze_v1.json')['files']:verify(Q/x['path'],x['sha256'])
for x in read(Q/'inputs_v3.json')['files'].values():verify(ROOT/x['path'],x['sha256'])
ledger=read(Q/'qualification_ledger_v1.json')
def walk(d):
 if isinstance(d,dict):
  if all(k in d for k in ['file','sha256','json_pointer','original_field_value']):
   p=ROOT/d['file'];verify(p,d['sha256']);v=read(p)
   for bit in d['json_pointer'].split('/')[1:]:
    bit=bit.replace('~1','/').replace('~0','~');v=v[int(bit)] if isinstance(v,list) else v[bit]
   assert v==d['original_field_value'],(p,d['json_pointer'])
   refs.append({'file':d['file'],'json_pointer':d['json_pointer']})
  for v in d.values():walk(v)
 elif isinstance(d,list):
  for v in d:walk(v)
walk(ledger)
A=P/'independent_aggregation_audit'
for x in read(A/'artifact_manifest_v1.json')['files']:verify(A/x['path'],x['sha256'])
audit=read(A/'audit_report_v1.json')
assert audit['all_passed_for_declared_scope'] and audit['differences']==0
assert ledger['cross_panel_complete_target_sequence']['status']=='insufficient'
assert len(ledger['structural_scope_validation'])==12
for p in ledger['structural_scope_validation']:
 assert p['all_original_text_ids_exact'] and p['all_original_component_ids_retained']
 assert p['all_report_and_seed_fields_equal_formal_aggregate'] and not p['remaining_not_reviewed_ids']
receipt={'schema':'root_full12_publication_input_review_v1','utc':datetime.now(timezone.utc).isoformat(),'file_hashes_verified':checked,'qualification_field_references_verified':len(refs),'all_checks_passed':True,'scope':'Frozen source integrity, referenced original field fidelity, and structural completeness. Scientific qualification prose reviewed separately; no independent pixel or meaning certification.'}
dump(P/'publication_input_review_v1.json',receipt)
approval={'schema':'zodiac_relations_release_approval_v1','approved_by':'root','release_approved':True,'utc':datetime.now(timezone.utc).isoformat(),'aggregation_path':'aggregation_v1.json','aggregation_sha256':sha(P/'aggregation_v1.json'),'input_freeze_sha256':sha(P/'aggregation_input_freeze_v1.json'),'output_freeze_sha256':sha(P/'aggregation_output_freeze_v1.json'),'independent_audit':{'state':'record_aggregation_verified','report_path':'independent_aggregation_audit/audit_report_v1.json','report_sha256':sha(A/'audit_report_v1.json')},'sequence_qualification':{'state':'complete_target_sequence_insufficient','report_path':'sequence_qualification/qualification_ledger_v1.json','report_sha256':sha(Q/'qualification_ledger_v1.json')},'scientific_status':'全12图固定观察名册交付完整，汇编复算一致；完整同角色目标文字序列证据仍不足。粗几何顺序与中央注记的位置角色保留为正面支持，未运行词义预测。','qualification_review':'Read full per-panel Q1–Q5 prose and source references. Insufficiency tied to unit grouping, competing roles, and sequence gaps, not unknown meaning, schema booleans, missing leader lines alone, or unknown starting index. Central annotation evidence is source-informed, not decipherment.','root_input_review_sha256':sha(P/'publication_input_review_v1.json'),'scope':'Approval to publish these bounded findings; browser and live deployment validation remain separate; not end-of-window completion.'}
dump(P/'publication_approval_v1.json',approval)
print(json.dumps({'verified_files':len(checked),'verified_qualification_field_references':len(refs),'approval_sha256':sha(P/'publication_approval_v1.json')}))
