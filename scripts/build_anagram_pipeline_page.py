#!/usr/bin/env python3
"""Read-only W10 page projection from an external, explicit hash-bound phase. No scientific engine imports."""
import argparse,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
W=Path('research/research_next/anagram_pipeline7h_20261119')
GROUPS={('primary','readme_lex'),('primary','code_countfirst'),('oracle_language','readme_lex'),('oracle_language','code_countfirst'),('oracle_truekey','shared')}
EMBED={'source_registry','source_scope_review','qualification','scores','report','score_audit','session','prior_inventory'}
def sha(b):return hashlib.sha256(b).hexdigest()
def encode(d):return (json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode()
def validate_scores(s):
 assert s['schema']=='tenth_known_answer_scores_v1' and s['primary_method']=='pattern' and s['primary_variant']=='readme_lex'
 assert len(s['groups'])==5 and {(g['condition'],g['variant']) for g in s['groups']}==GROUPS
 assert len(s['rows'])==30 and len({(r['truth_id'],r['condition'],r['variant']) for r in s['rows']})==30
 for condition,variant in GROUPS:
  rows=[r for r in s['rows'] if (r['condition'],r['variant'])==(condition,variant)]
  assert len(rows)==6 and sum(r['positive'] is True for r in rows)==4 and sum(r['positive'] is False for r in rows)==2
  group=next(g for g in s['groups'] if (g['condition'],g['variant'])==(condition,variant));assert group['planned_cases']==4 and group['planned_words']==320
 assert len(s['language_rows'])==10 and len({(r['id'],r['method']) for r in s['language_rows']})==10
 assert {r['method'] for r in s['language_rows']}=={'pattern','unigram'}
 return s

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--phase-input',required=True);ap.add_argument('--receipt-name',default='build_receipt_v1.json');a=ap.parse_args()
 phase_path=Path(a.phase_input);assert not phase_path.is_absolute() and phase_path.parent==W/'publication';assert Path(a.receipt_name).name==a.receipt_name
 phase_bytes=(ROOT/phase_path).read_bytes();phase=json.loads(phase_bytes);assert phase['schema']=='anagram_pipeline_publication_phase_v1';assert type(phase['scores_connected']) is bool and phase['state'];assert isinstance(phase['sources'],list) and phase['sources']
 outputs=[];sources=[];records={};allhashes={};roles=set()
 def write(path,b):
  p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);outputs.append({'path':str(path),'bytes':len(b),'sha256':sha(b)})
 # Validate every explicitly declared input before publishing any output.
 raw=[]
 for item in phase['sources']:
  role=item['role'];assert role not in roles;roles.add(role);path=Path(item['path']);assert not path.is_absolute() and '..' not in path.parts and path.is_relative_to('research');assert not path.is_relative_to(W/'publication'),'Scientific phase must not recursively ingest publication receipts'
  b=(ROOT/path).read_bytes();assert sha(b)==item['sha256'] and len(b)==item['bytes'];allhashes[str(path)]=sha(b)
  distribution=item.get('distribution','site_download');assert distribution in ['site_download','repository_reference']
  if distribution=='site_download':assert path.suffix.lower() not in ['.png','.jpg','.jpeg','.webp','.pdf'],'No manuscript pixels or full modern paper export'
  if distribution=='site_download' and path.suffix in ['.txt','.json','.py','.pl','.pm','.svg','.md']:assert not any(x in b for x in [b'/Users/',b'/home/',b'/var/folders/',b'/private/var/',b'/opt/miniconda',b'ghp_',b'github_pat_']),str(path)
  if role in EMBED or role.startswith('method_review_'):
   assert path.suffix=='.json';records[role]=json.loads(b)
  if role=='scores':assert path==W/'calibration/scores_v1.json','Toy scores must never become formal scores'
  raw.append((item,path,b,distribution))
 assert {'source_registry','source_scope_review','qualification','protocol'}<=roles
 assert records['source_registry']['schema_version']=='anagram_pipeline_source_registry_v1'
 assert records['qualification']['schema']=='tenth_author_core_eligibility_v1'
 assert ('scores' in roles)==phase['scores_connected']
 if phase['scores_connected']:
  validate_scores(records['scores'])
  for h in records['scores']['bindings'].values():assert h in allhashes.values(),'Score input/code hash missing from explicit source inventory'
 for item,path,b,distribution in raw:
  role=item['role'];url='https://github.com/HaibinLai/Voynich-manuscript/blob/main/'+str(path)
  if distribution=='site_download':
   name=item['download_name'];assert Path(name).name==name and name not in ['publication-manifest.json',phase_path.name];url='downloads/anagram-pipeline7h/'+name;assert not any(r['url']==url for r in sources);write(Path('site')/url,b)
  sources.append({**item,'url':url})
 payload={'schema':'anagram_pipeline_page_v1','state':phase['state'],'scores_connected':phase['scores_connected'],'sources':sources,'records':records,'private_images_exported':False,'scientific_code_executed_by_builder':False,'goal_complete_claimed':False,'toy_values_as_formal_scores':False}
 b=encode(payload);write(Path('site/data/anagram-pipeline7h.json'),b);write(Path('site/downloads/anagram-pipeline7h')/phase_path.name,phase_bytes)
 html=ROOT/'site/anagram-pipeline7h.html';text=html.read_text();text=re.sub(r'(<meta name="anagram-pipeline-snapshot" content=")[^"]*',lambda m:m[1]+sha(b)[:16],text)
 for name in ['anagram-pipeline7h.js','anagram-pipeline7h.css']:text=re.sub(re.escape(name)+r'(?:\?v=[A-Za-z0-9_-]+)?',name+'?v='+sha((ROOT/'site'/name).read_bytes())[:16],text)
 write(Path('site/anagram-pipeline7h.html'),text.encode())
 for name in ['anagram-pipeline7h.js','anagram-pipeline7h.css','style.css','favicon.svg']:
  path=Path('site')/name;outputs.append({'path':str(path),'bytes':(ROOT/path).stat().st_size,'sha256':sha((ROOT/path).read_bytes())})
 manifest={'schema':'anagram_pipeline_publication_manifest_v1','phase_path':str(phase_path),'phase_sha256':sha(phase_bytes),'state':phase['state'],'sources':sources,'outputs':outputs.copy(),'builder_sha256':sha(Path(__file__).read_bytes()),'test_sha256':sha((ROOT/'scripts/test_anagram_pipeline_viewer.cjs').read_bytes()),'private_images_exported':False,'scientific_code_executed':False,'self_excluded':True};write(Path('site/downloads/anagram-pipeline7h/publication-manifest.json'),encode(manifest))
 receipt={**manifest,'outputs':outputs,'data_sha256':sha(b)};(ROOT/W/'publication'/a.receipt_name).write_bytes(encode(receipt));print(json.dumps({'sources':len(sources),'outputs':len(outputs),'data_bytes':len(b),'scores_connected':phase['scores_connected']}))
if __name__=='__main__':main()
