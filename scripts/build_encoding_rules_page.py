#!/usr/bin/env python3
"""Read-only projection of explicitly frozen W9 sources. Never evaluates manuscript constraints."""
import argparse,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
W=Path('research/research_next/encoding_constraints7h_20261119');P=W/'publication'
PHASE_SHA256='fc9f44eff60645686c6bd817895a84acd302a7e6402e02d54f4b3c0183481b3d'
INPUTS=[('final_scope_review','root_report_review_v1.json'),('final_scope_review_text','root_report_review_v1.txt'),('plan','plan_v1.txt'),('session','session_v1.json'),('direction','next_direction_preflight_v1.txt'),('source_review','source_rule_eligibility_v1.json'),('source_review_text','source_rule_eligibility_v1.txt'),('rule_review','rule_eligibility_review_v1.json'),('rule_review_text','rule_eligibility_review_v1.txt'),('qualification','qualification_decision_v1.json'),('report','research_report_v1.json'),('report_text','research_report_v1.txt'),('prior_inventory','prior_work_inventory_v1.json'),('demo','artificial_demo_v1.json'),('demo_protocol','artificial_protocol_v1.txt'),('demo_code','code/artificial_order_demo.py'),('demo_code_freeze','artificial_code_freeze_v1.json'),('demo_audit','artificial_demo_audit_v1.json'),('demo_audit_text','artificial_demo_audit_v1.txt'),('independent_code','code/independent_artificial_audit_v1.py'),('earlier_seven_code','independent_preflight/artificial_order_check_v1.py'),('earlier_seven_receipt','independent_preflight/artificial_order_receipt_v1.json'),('clean_replay','clean_public_replay_v1.json'),('reproduce','REPRODUCE_v1.txt')]
PRIOR=[('prior_candidate_claims','research/research7h/literature/candidate_claims.json'),('prior_literature','research/research7h/literature/literature.json'),('prior_anchor_report','research/research7h/anchor_audit/研究说明.txt'),('prior_cipher_report','research/research7h/cipher_controls/voynich_substitution/研究报告.txt')]
def sha(b):return hashlib.sha256(b).hexdigest()
def encoded(x):return (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode()
def explicit_inputs():
 out=[]
 for key,path,copy in [(k,str(W/n),True) for k,n in INPUTS]+[(k,n,False) for k,n in PRIOR]:
  b=(ROOT/path).read_bytes();out.append({'key':key,'path':path,'sha256':sha(b),'bytes':len(b),'distribution':'site_download' if copy else 'repository_reference','download_name':key.replace('_','-')+''.join(Path(path).suffixes)})
 return out
def project_demo(d):
 assert d['schema']=='ninth_artificial_order_demo_v1' and d['manuscript_input'] is False
 assert [x['id'] for x in d['cases']]==['T%02d'%i for i in range(1,10)]
 for x in d['cases']+[d['free_reordering_witness']['strict_joint']]:
  assert x['artificial'] is True and x['semantic_claim'] is False and len(x['at_most_two_orders_of_known_subset'])<=2
  assert x['full_input_compatibility'] is None or type(x['full_input_compatibility']) is bool
 return d

def main():
 ap=argparse.ArgumentParser(description=__doc__);g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--reviewed-draft',action='store_true');g.add_argument('--phase-input');ap.add_argument('--receipt-name',default='draft_build_v1.json');a=ap.parse_args();assert Path(a.receipt_name).name==a.receipt_name
 if a.phase_input:
  phase_path=Path(a.phase_input);assert phase_path.parent==P;pb=(ROOT/phase_path).read_bytes();assert PHASE_SHA256 and sha(pb)==PHASE_SHA256;phase=json.loads(pb);assert phase['schema']=='encoding_rules_publication_phase_v1'
 else:phase_path=None;phase={'schema':'encoding_rules_draft_phase','state':'LOCAL_REVIEWED_DRAFT','sources':explicit_inputs()}
 docs={};sources=[];outputs=[];hashes={}
 def write(path,b):
  p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);outputs.append({'path':str(path),'sha256':sha(b),'bytes':len(b)})
 for item in phase['sources']:
  key=item['key'];path=Path(item['path']);assert not path.is_absolute() and '..' not in path.parts and path.is_relative_to('research');b=(ROOT/path).read_bytes();assert sha(b)==item['sha256'] and len(b)==item['bytes'];hashes[str(path)]=sha(b)
  url='https://github.com/HaibinLai/Voynich-manuscript/blob/main/'+str(path)
  if item['distribution']=='site_download':
   assert not any(x in b for x in [b'/Users/',b'/home/',b'/var/folders/',b'/private/var/',b'/opt/miniconda',b'github_pat_',b'ghp_']);assert Path(item['download_name']).name==item['download_name'];url='downloads/encoding-rules7h/'+item['download_name'];write(Path('site')/url,b)
  sources.append({**item,'url':url})
  if path.suffix=='.json':docs[key]=json.loads(b)
 assert len(sources)==len({r['key'] for r in sources})
 def bound(items,relative=False):
  for r in items:
   path=str(W/r['path']) if relative else r['path'];assert hashes[path]==r['sha256'],path
 bykey={r['key']:r for r in sources};demo=project_demo(docs['demo']);review=docs['rule_review'];source=docs['source_review'];audit=docs['demo_audit'];decision=docs['qualification'];report=docs['report'];replay=docs['clean_replay']
 assert demo['freeze_sha256']==bykey['demo_code_freeze']['sha256'];bound(docs['demo_code_freeze']['files'],True)
 assert review['schema']=='ninth_rule_eligibility_independent_review_v1' and len(review['eligibility_matrix'])==6
 assert source['schema_version']=='source_rule_eligibility_v1' and len(source['source_rule_matrix'])==8 and source['historical_fixed_order_conjecture_present'] is True
 bound(source['input_bindings']);bound(review['prior_work_read']);bound(docs['prior_inventory']['prior_sources'])
 assert decision['schema']=='ninth_root_qualification_decision_v1' and decision['eligibility']=='NOT_APPLICABLE' and decision['new_manuscript_computation_allowed'] is False;bound(decision['evidence'])
 correction=decision['metadata_correction'];assert correction['historical_value']==review['primary_source']['total_verbatim_English_words']==18;assert correction['actual_whitespace_word_count']==sum(len(x['text'].split()) for x in review['primary_source']['short_quotations'])==16
 assert audit['schema']=='ninth_independent_artificial_demo_audit_v1' and audit['status']=='PASS' and audit['failures']==[];bound(audit['sources'],True);assert audit['scope']['protocol_cases']==9 and audit['scope']['free_reordering_cases']==1 and len(audit['cases'])==10
 for x,y in zip(demo['cases']+[demo['free_reordering_witness']['strict_joint']],audit['cases']):assert x['id']==y['id'] and x['status']==y['expected_status'] and y['status']=='PASS'
 assert report['schema']=='ninth_research_report_v1' and report['manuscript_scoring_executed'] is False and report['author_broad_model_refuted'] is False and report['goal_complete_claimed'] is False;bound(report['files'])
 assert replay['status']=='PASS' and replay['primary_output_equal_except_created_utc'] is True and replay['independent_audit_cases_checks_equal'] is True;bound(replay['copied_public_files'],True)
 assert docs['final_scope_review']['status']=='PASS' and docs['final_scope_review']['blocking_issues']==[];bound(docs['final_scope_review']['bindings'])
 payload={'final_scope_review':docs['final_scope_review'],'schema':'encoding_rules_page_v1','state':phase['state'],'sources':sources,'artificial_demo':demo,'artificial_audit':audit,'rule_review':review,'source_rule_eligibility':source,'qualification_decision':decision,'research_report':report,'prior_inventory':docs['prior_inventory'],'clean_public_replay':replay,'session_times':{k:docs['session'][k] for k in ['planned_start_utc','deadline_utc','actual_goal_creation_utc']},'private_images_exported':False,'new_manuscript_scoring':False,'goal_complete_claimed':False,'independent_seven_case_set_included_in_nine':False}
 b=encoded(payload);write(Path('site/data/encoding-rules7h.json'),b)
 if phase_path:write(Path('site/downloads/encoding-rules7h')/phase_path.name,pb)
 html=ROOT/'site/encoding-rules7h.html';s=html.read_text();s=re.sub(r'(<meta name="encoding-rules-snapshot" content=")[^"]*',lambda m:m[1]+sha(b)[:16],s)
 for name in ['encoding-rules7h.js','encoding-rules7h.css']:s=re.sub(re.escape(name)+r'(?:\?v=[A-Za-z0-9_-]+)?',name+'?v='+sha((ROOT/'site'/name).read_bytes())[:16],s)
 write(Path('site/encoding-rules7h.html'),s.encode())
 for name in ['encoding-rules7h.js','encoding-rules7h.css','style.css','favicon.svg']:
  path=Path('site')/name;outputs.append({'path':str(path),'sha256':sha((ROOT/path).read_bytes()),'bytes':(ROOT/path).stat().st_size})
 manifest={'schema':'encoding_rules_publication_manifest_v1','phase_path':str(phase_path) if phase_path else None,'state':phase['state'],'inputs':sources,'outputs':outputs.copy(),'builder_sha256':sha(Path(__file__).read_bytes()),'viewer_test_sha256':sha((ROOT/'scripts/test_encoding_rules_viewer.cjs').read_bytes()),'new_scientific_computation':False,'private_images_exported':False,'self_excluded':True}
 write(Path('site/downloads/encoding-rules7h/publication-manifest.json'),encoded(manifest));receipt={**manifest,'outputs':outputs,'data_sha256':sha(b)}
 (ROOT/P/a.receipt_name).write_bytes(encoded(receipt));print(json.dumps({'sources':len(sources),'outputs':len(outputs),'data_bytes':len(b),'data_sha256':sha(b)}))
if __name__=='__main__':main()
