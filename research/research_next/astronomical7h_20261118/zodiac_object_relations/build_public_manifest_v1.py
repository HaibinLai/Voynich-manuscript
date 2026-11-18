"""Explicit source package for full12 record analysis; no working drafts or private pixels."""
from pathlib import Path
import hashlib,json,re
P=Path(__file__).resolve().parent;ROOT=P.parents[3];items={}
def read(p):return json.loads(p.read_text())
def add(p,h=None):
 p=p.resolve();assert p.is_relative_to(ROOT),p
 b=p.read_bytes();digest=hashlib.sha256(b).hexdigest()
 if h:assert h==digest,(p,h)
 s=b.decode('utf-8');assert not re.search(r'/(?:Users|private|tmp)/',s),p
 items[str(p.relative_to(ROOT))]={'sha256':digest,'bytes':len(b)}
def entries(base,es):
 for x in es:add(base/x['path'],x.get('sha256'))
def filelist(base,name,key='files',entrybase=None):
 path=base/name;add(path);v=read(path)[key]
 if isinstance(v,dict):v=[{'path':k,'sha256':x} if isinstance(x,str) else x for k,x in v.items()]
 entries(entrybase or base,v)
filelist(P,'aggregation_input_freeze_v1.json');filelist(P,'aggregation_output_freeze_v1.json')
Q=P/'sequence_qualification';filelist(Q,'output_freeze_v1.json');filelist(Q,'inputs_v3.json',entrybase=ROOT)
A=P/'independent_aggregation_audit';filelist(A,'artifact_manifest_v1.json');filelist(A,'minimum_replay_dependencies_v1.json',entrybase=P);add(A/'output_freeze_v1.json')
I=A/'interpretation_check';filelist(I,'artifact_manifest_v1.json');filelist(I,'minimum_dependencies_v1.json',entrybase=P.parent);add(I/'output_freeze_v1.json')
filelist(P/'circle_spatial_observer','completion_manifest_v1.json','exact_frozen_panel_file_list',ROOT)
filelist(P/'literature','delivery_manifest_v1.json',entrybase=ROOT)
filelist(P/'astronomical_site','observer_manifest_v1.json','explicit_artifact_allowlist',ROOT)
for n in ['inventory_interpretation_input_freeze_v1.json','inventory_interpretation_output_freeze_v1.json']:
 filelist(P,n)
filelist(P/'root_f72v2_zi01_followup','output_freeze_v1.json')
for n in ['aggregation_report_v1.txt','publication_approval_v1.json','publication_input_review_v1.json','review_publication_v1.py','build_public_manifest_v1.py','public_replay_receipt_v1.json','sequence_qualification_protocol_v1.txt','sequence_qualification_clarification_v1.txt','sequence_qualification_method_freeze_v1.json','sequence_qualification_clarification_freeze_v1.json','circle_spatial_observer/completion_manifest_v1.txt','circle_spatial_observer/completion_manifest_freeze_v1.json','astronomical_site/observer_manifest_v1.txt']:
 add(P/n)
manifest={'schema':'zodiac_full12_public_source_manifest_v1','paths_relative_to':'repository_root','selection':'Explicit frozen inputs, formal output manifests, current qualification dependencies, independent replay dependencies and root release review. No recursive directory inclusion.','files':[{'path':p,**v} for p,v in sorted(items.items())],'file_count':len(items),'scientific_status':'Observation inventory complete; complete same-role target sequences insufficient; no semantic prediction performed.','private_pixel_files_included':False,'working_drafts_included':False,'machine_absolute_paths_found':False,'rebuild_command':'python3 -B research/research_next/astronomical7h_20261118/zodiac_object_relations/build_aggregation_v1.py','manifest_self_included':False}
(P/'public_manifest_v1.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'file_count':len(items),'bytes':sum(v['bytes'] for v in items.values())}))
