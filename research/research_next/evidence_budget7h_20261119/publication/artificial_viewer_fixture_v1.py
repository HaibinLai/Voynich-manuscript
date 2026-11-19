# coding: utf-8
"""UI-only artificial states. Never imports scientific engines or reads real records."""
from itertools import product
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
IDS=['F01','F02','F03','F04','F05','F06'];CORE=[x for x in IDS if x!='F02'];STATES=['terminal_region_reading','opaque_boundary_reading']
FIELDS=['class','unique_count','tagged_count','positive_unique_count','positive_tagged_count','compatible_g_bits','H_min32','H_max32','H4_min32','H4_max32','difference_min32','difference_max32','H_min_witness','H_max_witness','H4_min_witness','H4_max_witness','difference_min_witness','difference_max_witness','positive_witness','nonpositive_witness']
# All slots, signatures, scores, IDs, case metadata and coverage below are invented UI fixtures.
ALPHABET={e:[[0,0,0,0],[1,1,1,1]] for e in IDS}
assignments=[dict(zip(CORE,combo)) for combo in product(range(2),repeat=5)]
def compatible(a,g):return g==STATES[0] or a['F03']==0
def scores(a):
 h=8 if a['F01'] else -8;h4=8 if a['F03'] else -8
 return [h,h4,h-h4]
def row(observed,selection,regime):
 active=STATES if regime=='unknown' else [regime]
 valid=[(i,a,[g for g in active if compatible(a,g)]) for i,a in enumerate(assignments) if all(a[e]==selection[e] for e in observed)]
 valid=[x for x in valid if x[2]]
 if not valid:return [0,0,0,0,0,0]+[None]*14
 pos=[x for x in valid if scores(x[1])[0]>0 and scores(x[1])[1]>0];neg=[x for x in valid if x not in pos]
 cls=1 if not pos else 3 if not neg else 2
 bits=sum(1<<i for i,g in enumerate(STATES) if any(g in x[2] for x in valid))
 bounds=[];witnesses=[]
 for coordinate in range(3):
  for upper in [False,True]:
   best=(max if upper else min)(scores(a)[coordinate] for _,a,_ in valid);bounds.append(best);witnesses.append(next(i for i,a,_ in valid if scores(a)[coordinate]==best))
 return [cls,len(valid),sum(len(gs) for _,_,gs in valid),len(pos),sum(len(gs) for _,_,gs in pos),bits,*bounds,*witnesses,pos[0][0] if pos else None,neg[0][0] if neg else None]
def build():
 tables={}
 for mask in range(32):
  observed=[e for i,e in enumerate(CORE) if mask&(1<<i)]
  for regime in ['unknown',*STATES]:
   tables[regime+'/'+str(mask)]={'observed':observed,'regime':regime,'shape':[2]*len(observed),'rows':[row(observed,dict(zip(observed,combo)),regime) for combo in product(range(2),repeat=len(observed))]}
 observation={'schema':'ARTIFICIAL_OBSERVATION_FIXTURE_NOT_A_MANUSCRIPT','entries':[]}
 states=[]
 for e in IDS:
  observation['entries'].append({'id':e,'original_unit':'纯人工界面槽位；不是本轮图像单位','coverage':{'DEMO_COVERAGE':'人工覆盖说明，不代表看过任何图'},'units':{'DEMO_UNIT':{'scope':'人工来源占位，无原图坐标'}},'joins':{},'cases':[{'id':e+'_DEMO_CASE_'+str(i),'unit_classes':{},'join_ids':[],'residual':{'vectors':[s],'coverage_refs':['DEMO_COVERAGE']},'note':'四元组仅用于交互测试，不是图像编码'} for i,s in enumerate(ALPHABET[e])]})
 for g in STATES:
  domains={e:ALPHABET[e] if not(e=='F03' and g==STATES[1]) else ALPHABET[e][:1] for e in IDS}
  projections=[]
  for e in IDS:
   projections.append({'id':e,'domain':domains[e],'preimages':[{'signature':s,'origins':[{'case_id':e+'_DEMO_CASE_'+str(ALPHABET[e].index(s)),'extra_index':0}]} for s in domains[e]]})
  states.append({'id':g,'entries':domains,'entry_projections':projections})
 return {'schema':'evidence_budget_viewer_fixture_v1','mode':'ARTIFICIAL_FIXTURE_ONLY','research_result':False,'title':'纯人工交互检查，不是第六轮结果','fixture_score_rule':'H_demo=±8/32 from invented F01 index; H4_demo=±8/32 from invented F03 index. No real formula or records used.','entry_ids':IDS,'core_ids':CORE,'features':['Q0','Q1','Q2','QJ'],'states':STATES,'regimes':['unknown',*STATES],'alphabet':ALPHABET,'row_fields':FIELDS,'classes':['CONFLICT','NONE_JOINT_POSITIVE','MIXED','ALL_JOINT_POSITIVE'],'denominator':32,'factorization':{'entry_id':'F02','applies_to':['H_demo','H4_demo','difference_demo'],'domain_identical_across_g':True,'fixture_constructed_not_scientific_proof':True},'logical_subsets':[{'mask':m,'observed_ids':[e for i,e in enumerate(IDS) if m&(1<<i)],'core_mask':sum(1<<j for j,e in enumerate(CORE) if m&(1<<IDS.index(e))),'f02_observed':bool(m&2)} for m in range(64)],'tables':tables,'provenance_input':{'states':states},'observation':observation,'source_notice':'All fixture provenance invented. A real adapter must bind both original W5 input and observation hashes; none loaded here.','real_results':None,'minimal_information_results':None,'historical_pair_reference':'hierarchical7h.html'}
if __name__=='__main__':
 data=build();path=ROOT/'site/data/evidence-budget7h-fixture.json';path.parent.mkdir(exist_ok=True);b=(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n').encode();path.write_bytes(b);print(json.dumps({'artificial_only':True,'logical_subsets':64,'tables':len(data['tables']),'sha256':hashlib.sha256(b).hexdigest(),'path':str(path.relative_to(ROOT))}))
