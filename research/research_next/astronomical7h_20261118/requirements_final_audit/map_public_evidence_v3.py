#!/usr/bin/env python3
"""Read-only Git-tree and declared-mirror coverage; no filesystem publication."""
from pathlib import Path
import hashlib,json,subprocess,sys
D=Path(__file__).resolve().parent;R=D.parents[3];B=D.parent
COMMIT='81d5ef27dfe14aa774707345ea8b77e96ce00959'
def load(p):return json.loads(p.read_text())
def sha(b):return hashlib.sha256(b).hexdigest()
def git(*a):return subprocess.check_output(['git',*a],cwd=R)
index=set(git('ls-files','-z').decode().split('\0'));tree=set(git('ls-tree','-r','--name-only','-z',COMMIT).decode().split('\0'));index.discard('');tree.discard('')
cache={}
def committed_hash(p):
 if p not in tree:return None
 if p not in cache:cache[p]=sha(git('show',COMMIT+':'+p))
 return cache[p]
report=load(D/'requirements_final_audit_v2.json');refs={}
for row in report['requirements']+report['later_explicit_requirements']:
 for e in row['actual_evidence']:
  p=e['path'];refs.setdefault(p,{'sha256':e['sha256'],'requirements':[]});assert refs[p]['sha256']==e['sha256'];refs[p]['requirements'].append(row['id'])
# Audit dependency closure is explicit and bounded to audit input manifests; it
# does not recursively include historical image/acquisition caches.
if '--audit-dependencies' in sys.argv:
 for rel in [
  'requirements_audit_preclose/input_freeze_v1.json',
  'requirements_audit_preclose/evidence_input_freeze_v1.json',
  'requirements_audit_preclose/evidence_addendum_freeze_v1.json',
  'requirements_final_audit/input_freeze_v1.json',
  'requirements_final_audit/evidence_addendum_v1.json',
  'requirements_final_audit/timing_input_addendum_v1.json',
  'requirements_final_audit/online_input_freeze_v2.json']:
  m=B/rel
  refs.setdefault(str(m.relative_to(R)),{'sha256':sha(m.read_bytes()),'requirements':[]})
  for e in load(m)['files']:
   p=e.get('path',e.get('file'));h=e['sha256'];refs.setdefault(p,{'sha256':h,'requirements':[]});assert refs[p]['sha256']==h
   refs[p]['requirements'].append('audit_input:'+rel)
 for p in [B/'requirements_audit_preclose/output_freeze_v1.json',B/'requirements_final_audit/output_freeze_v2.json',B/'closure/research_delivery_report_v1.txt']:
  refs.setdefault(str(p.relative_to(R)),{'sha256':sha(p.read_bytes()),'requirements':['audit_provenance']})

# Discover only possible equal-byte published download mirrors; verify actual commit bytes for matches.
mirrors={}
for p in sorted(tree):
 if p.startswith('site/downloads/') and (R/p).is_file():
  h=sha((R/p).read_bytes());mirrors.setdefault(h,[]).append(p)
projection={}
fidelity=B/'publication/evidence_coverage_review/projection_field_fidelity_v1.json'
for x in load(fidelity)['pairs']:
 if not x['byte_identical']:projection[x['source']]={'public_path':x['public_copy'],'public_sha256':x['public_sha256'],'original_sha256':x['source_sha256'],'receipt':str(fidelity.relative_to(R)),'receipt_sha256':sha(fidelity.read_bytes()),'scope':'Only explicitly declared path-prefix leaf changes; scientific fields retained according to full field-fidelity receipt.'}
newf=B/'publication/evidence_coverage_review/new_projection_field_fidelity_receipt_v1.json'
for x in load(newf)['files']:projection[x['original_source']]={'public_path':x['public_projection'],'public_sha256':x['projection_sha256'],'original_sha256':x['original_source_sha256'],'receipt':str(newf.relative_to(R)),'receipt_sha256':sha(newf.read_bytes()),'scope':'Explicitly enumerated path fields changed; original hash remains the original byte identity, not projection identity.'}
rows=[]
for p,e in sorted(refs.items()):
 h=e['sha256'];original=committed_hash(p);equal=[q for q in mirrors.get(h,[]) if q!=p and committed_hash(q)==h]
 pr=projection.get(p)
 if pr:
  pr=dict(pr);pr['original_hash_binding_matches']=pr['original_sha256']==h;pr['projection_bytes_in_commit_match']=committed_hash(pr['public_path'])==pr['public_sha256'];pr['receipt_bytes_in_commit_match']=committed_hash(pr['receipt'])==pr['receipt_sha256']
 if original==h:status='ORIGINAL_EXACT_BYTES_IN_DEPLOYED_COMMIT'
 elif equal:status='EXACT_PUBLIC_DOWNLOAD_MIRROR_ORIGINAL_NOT_PUBLISHED_AT_THAT_PATH'
 elif pr and all(pr[k] for k in ['original_hash_binding_matches','projection_bytes_in_commit_match','receipt_bytes_in_commit_match']):status='DECLARED_PATH_PROJECTION_PUBLIC_ORIGINAL_BYTES_NOT_PUBLIC'
 else:status='NO_PUBLIC_COUNTERPART_VERIFIED_AT_PINNED_COMMIT'
 rows.append({'local_original_path':p,'local_original_sha256':h,'requirements':sorted(set(e['requirements'])),'tracked_in_current_index':p in index,'original_path_in_pinned_commit':p in tree,'original_bytes_equal_pinned_commit':original==h,'equal_byte_public_download_mirrors':[{'path':q,'sha256':h} for q in equal],'declared_projection':pr,'coverage':status,'current_local_bytes_match':(R/p).is_file() and sha((R/p).read_bytes())==h})
result={'schema':'final_requirement_public_evidence_mapping_v3','pinned_deployed_commit':COMMIT,'tree_checked_read_only':True,'current_index_tracking_not_equated_to_publication':True,'source_audit_sha256':sha((D/'requirements_final_audit_v2.json').read_bytes()),'cited_unique_sources':len(rows),'rows':rows,'counts':{s:sum(x['coverage']==s for x in rows) for s in sorted({x['coverage'] for x in rows})},'limits':['Pinned Git commit identified by root deployed receipt; no independent network fetch of every repository path.','Exact mirror is a public byte copy, not publication of the original path.','Path projection has a different SHA and is not an exact original; field-fidelity receipt supplies declared transformation.','NO_PUBLIC_COUNTERPART is a current coverage gap, including new final receipts/audit artifacts intended for v14.','No private raw images or acquisition caches are required or proposed for public release.']}
print(json.dumps(result,ensure_ascii=False,indent=2))
