#!/usr/bin/env python3
"""Offline public replay of the audited independent XML calibration.
Requires only this bundle and Python's standard library. Never executes historical
primary entry points or writes into the bundle. Existing output paths are refused.
"""
import argparse,datetime,gzip,hashlib,json,sys,traceback
from pathlib import Path
from fractions import Fraction as F
sys.dont_write_bytecode=True

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):
 p=Path(p);return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def save(p,obj,pack):
 data=json.dumps(pack(obj),ensure_ascii=False,separators=(',',':')).encode()
 if p.suffix=='.gz':data=gzip.compress(data,mtime=0)
 p.write_bytes(data)

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bundle',type=Path,default=Path(__file__).resolve().parent);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 bundle=args.bundle.resolve();output=args.output.resolve()
 if output.exists():parser.error('Output path already exists; it will not be overwritten.')
 if output==bundle or bundle in output.parents:parser.error('Output must be outside the immutable input bundle.')
 manifest_path=bundle/'public_payload_manifest.json'
 if not manifest_path.is_file():parser.error('Bundle lacks public_payload_manifest.json; point --bundle to public_replay.')
 manifest=load(manifest_path)
 for rel,expected in manifest['files'].items():
  path=(bundle/rel).resolve()
  if bundle not in path.parents or digest(path)!=expected:raise RuntimeError('Bundle path/hash mismatch: '+rel)
 output.mkdir(parents=True,exist_ok=False)
 try:
  base=bundle/'design/space_bridge_herbal';oldbase=bundle/'design/known_herbal';sys.path.insert(0,str(base))
  import audit_core as core
  import audit_compare as compare
  # These are archived independent implementations, not the primary scorer.
  if core.HERE.resolve()!=base.resolve():raise RuntimeError('Unexpected independent core import')
  core.SOURCE=oldbase/'A35365.xml.gz';core.OLD=oldbase
  source=gzip.decompress(core.SOURCE.read_bytes());source_hash=hashlib.sha256(source).hexdigest()
  if source_hash!='bff4bd8569c5417e1fead6cc4c06b6e0be5b27eaf93295481feccaf524ee9acb':raise RuntimeError('Unexpected source XML')
  frozen={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'mode':'offline_public_independent_replay','payload_manifest_sha256':digest(manifest_path),'source_xml_sha256':source_hash,'input_files':{rel:h for rel,h in manifest['files'].items()},'output_policy':'new directory outside input bundle; no overwrite','toy_checks':core.toys(),'context_review_scope':'Historical post-result qualitative interpretation artifacts are included for transparency, not certified by numerical replay.'}
  save(output/'freeze.json',frozen,core.pack)
  previous=load(oldbase/'run_v1/sections.json.gz');packet,identity,removed=core.extract(source,previous);matrix=core.matrices(packet,identity);summary=core.summarize(matrix)
  for name,obj in [('packet',packet),('identity',identity),('removed',removed),('matrix',matrix),('summary',summary)]:save(output/(name+'.json.gz'),obj,core.pack)
  # Resolve historical frozen hashes through the dual-hash projection receipt.
  projection=load(bundle/'public_projection_receipt.json');archived={e['public_path']:e['archived_sha256'] for e in projection['files']}
  for directory in ('run_v1','audit_run_v2'):
   receipt=load(base/directory/'complete.json')
   for name,h in receipt['files'].items():compare.ck('historical.'+directory+'.'+name,h,archived['design/space_bridge_herbal/'+directory+'/'+name])
  mainfreeze=load(base/'run_v1/freeze.json')
  for name,h in mainfreeze['files'].items():compare.ck('historical.main.freeze.'+name,h,archived['design/space_bridge_herbal/'+name])
  projected=compare.project_packet(packet,previous,compare.event_path_maps())
  compare.ck('packet',projected,load(base/'run_v1/packet.json.gz'))
  compare.ck('identity',[{k:s[k] for k in ('id','raw_title','title_tokens','primary')} for s in previous if s['primary']],load(base/'run_v1/identity.json'))
  support=compare.support_fields(projected,previous);saved_support=load(base/'support_v1.json');compare.ck('support',support,{k:saved_support[k] for k in support})
  changes=compare.changes(projected);compare.ck('input_changes',changes,load(base/'run_v1/input_changes.json.gz'))
  rows=compare.matrix_rows(matrix,packet);compare.ck('matrix',rows,compare.cv(load(base/'run_v1/matrix.json.gz')))
  oldrows=compare.cv(load(oldbase/'run_v1/rows.json.gz'))
  for r,oldr in zip(rows,oldrows):
   compare.ck('old.id',r['id'],oldr['id']);compare.ck('old.label',r['label'],oldr['label'])
   for c,oc in zip(r['matrix'],oldr['matrix']):
    v=c['mechanisms']['O'];count=previous[c['section']-1]['body_words']
    compare.ck('old.cell',{'section':c['section'],'matches':v['m'],'binary':v['binary'],'same_length_n':v['N'],'conditional_rate':v['rate'],'body_words':count,'per_thousand':F(v['m']*1000,count) if count else None},oc)
  aggregates=compare.aggregates(rows);transitions=compare.transitions(rows);compare.ck('transitions',transitions,compare.cv(load(base/'run_v1/transitions.json.gz')))
  primary_summary=compare.cv(load(base/'run_v1/summary.json'));compare.ck('aggregates',aggregates,primary_summary['aggregates'])
  compact={k:{name:v for name,v in t.items() if name not in ('title_contributions','changed_cells')} for k,t in transitions.items()}
  compare.ck('summary.transitions',compact,primary_summary['transitions']);compare.ck('summary.input_changes',{'removed_words':changes['removed_word_count'],'sections':changes['affected_section_count'],'cause_occurrences':changes['cause_occurrences']},primary_summary['input_change'])
  compare.ck('summary.exposed',[{'id':r['id'],'label':r['label'],'own':r['own']} for r in rows if r['id']==12],primary_summary['exposed_case'])
  adjacent=compare.adjacent_matches(rows,projected);compare.ck('five_adjacent_matches',adjacent,load(base/'all_adjacent_matches.json'))
  report={'status':'PASS' if not compare.counts['differences'] else 'FAIL','scalar_checks':compare.counts['scalar_checks'],'difference_count':compare.counts['differences'],'differences':compare.diffs,'matrix_cells':119*282*8,'sections':282,'titles':119,'paragraphs':1317,'removed_words':len(removed),'affected_sections':len({r['section'] for r in removed}),'aggregates':aggregates,'transitions':compact,'all_adjacent_matches':adjacent,'read_scope':'Only allowlisted bundle data and Python standard library; primary scorer/support were not imported.','context_interpretation_audited':False,'source_xml_sha256':source_hash,'payload_manifest_sha256':digest(manifest_path)}
  save(output/'verification.json',report,core.pack)
  if report['status']!='PASS':raise RuntimeError('Numerical replay differs; see verification.json')
  for rel,h in manifest['files'].items():
   if digest(bundle/rel)!=h:raise RuntimeError('Bundle changed during replay: '+rel)
  receipt={'status':'complete','verification':'PASS','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'payload_manifest_sha256':digest(manifest_path),'files':{p.name:digest(p) for p in output.iterdir() if p.is_file()}}
  save(output/'complete.json',receipt,core.pack)
  print(json.dumps({'status':'PASS','matrix_cells':report['matrix_cells'],'scalar_checks':report['scalar_checks'],'difference_count':0,'source_xml_sha256':source_hash},indent=2))
 except Exception as error:
  save(output/'failure.json',{'error':str(error),'traceback':traceback.format_exc()},lambda x:x)
  raise
if __name__=='__main__':main()
