"""Evidence linkage and measurement-record checks only; no pair/statistical result input."""
import json,hashlib
from pathlib import Path
from datetime import datetime,timezone
W=Path('research/research_next/repeated_labels7h_20261119');D=W/'feature_review_v1'
if (D/'freeze_v1.json').exists():raise SystemExit('Frozen review; no overwrite')
def rd(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
C=[]
def ck(k,b):C.append({'check':k,'pass':bool(b)})
I=rd(D/'input_scope_v1.json');O=rd(W/'feature_observation/observation_v1.json');A=rd(D/'audit_v1.json');V={v['view_id']:v for v in rd(D/'view_receipt_v1.json')['native_views']}
for i in I['inputs']:ck('unchanged input '+i['path'],sha(Path(i['path']))==i['sha256'])
ck('expected original matrix hash',sha(W/'feature_observation/observation_v1.json')=='ddf09acc3050cc218cf08e357b0a77722e83c3f777782ff5ef86ce31ec214872')
for v in V.values():ck('view hash '+v['view_id'],sha(Path(v['path']))==v['sha256'])
expected=[]
for g in O['groups']:
 for fid,c in g['features'].items():
  key=g['canonical_group_id']+'/'+fid
  if c['value'] is None:continue
  expected.append((g['canonical_group_id'],fid,c['value']))
  ck(key+' all views resolved and seen',all(n in V and V[n]['actually_viewed_this_review'] for n in c['view_ids']))
  ck(key+' original image ID/SHA linkage',all(V[n]['source_image_id']==g['image_id'] and V[n]['source_sha256']==g['image_sha256'] for n in c['view_ids']))
  def contains(box,p):x,y,w,h=box;return x<=p[0]<=x+w and y<=p[1]<=y+h
  def seen(p):return any(contains(V[n]['xywh'],p) for n in c['view_ids'])
  m=c['measurements']
  if c['value']==0:ck(key+' negative coverage supplied',bool(c['negative_coverage']))
  if c['value']==1 and fid=='G1':
   ck(key+' required connector declared',m['connector_definition_unambiguous'] is True)
   ck(key+' conservative threshold arithmetic',m['wide_width_interval_px'][0]>=3*m['connector_width_interval_px'][1])
   ck(key+' both section endpoint witnesses in cited views',all(seen(p) for k in ['wide_section_endpoints_xy','connector_section_endpoints_xy'] for p in m[k]))
  if c['value']==1 and fid=='G2':
   ck(key+' three separate stored arm witnesses',len(m['arm_center_path_witnesses_xy'])>=3)
   ck(key+' arm witnesses in cited views',all(seen(p) for path in m['arm_center_path_witnesses_xy'] for p in path))
  if c['value']==1 and fid=='G3':
   ck(key+' three stored distinct ends',len({tuple(e['visible_end_xy']) for e in m['ends']})>=3)
   for e in m['ends']:
    ck(key+'/'+e['end_id']+' owned and maximum-width threshold',e['membership']=='owned' and e['length_interval_px'][0]>=3*e['maximum_transverse_width_interval_px'][1])
    ck(key+'/'+e['end_id']+' complete path in cited views',all(seen(p) for p in e['center_path_witness_xy']))
  if c['value']==1 and fid=='G4':
   ck(key+' two stored crossline witnesses',len(m['lines'])>=2)
   ck(key+' crossline witnesses in cited views',all(seen(p) for line in m['lines'] for p in line['path_xy']))
actual=[(r['canonical_group_id'],r['feature'],r['frozen_value']) for r in A['cells']]
ck('all and only 27 fixed cells reviewed',sorted(expected)==sorted(actual))
ck('20 positive and 7 zero',sum(v==1 for _,_,v in expected)==20 and sum(v==0 for _,_,v in expected)==7)
ck('21 null cells untouched',sum(c['value'] is None for g in O['groups'] for c in g['features'].values())==21)
ck('all 48 matrix cells retained',sum(len(g['features']) for g in O['groups'])==48)
R={'utc':datetime.now(timezone.utc).isoformat(),'scope':'Input/crop SHA, source-image linkage, complete 27-cell review roster and required measurement-record witnesses. Threshold arithmetic only; no visual truth or numerical research-result certification.','checks':len(C),'failed':[c for c in C if not c['pass']],'all_checks':C}
(D/'verification_v1.json').write_text(json.dumps(R,indent=2)+'\n');print('checks',len(C),'failed',len(R['failed']));print(R['failed'])
