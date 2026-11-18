"""Read-only independent replay of fixed artificial checks.

Run: python3 -B audit_replay_v1.py
Reads only the eight explicitly named sibling inputs; emits JSON to stdout.
Never imports author modules or writes files. Original audit artifacts stay intact.
Adaptation: relative input root; removed artifact-writing/report-text tail only.
Original executed audit script SHA256: 140ea9c3cc06417865eaff126b7265e3cb017a4bf39e20a5a7542eef5dde44c8
"""
from pathlib import Path
import hashlib,json,datetime,itertools,time
from fractions import Fraction as Q
P=Path(__file__).resolve().parent
names=['protocol_v1.txt','run_v1.py','results_v1.json','report_v1.txt','invariance_protocol_v1.txt','invariance_v1.py','invariance_results_v1.json','invariance_report_v1.txt']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
inputs={n:sha(P/n) for n in names};started=datetime.datetime.now(datetime.timezone.utc).isoformat();clock=time.process_time()
r=json.loads((P/'results_v1.json').read_text());v=json.loads((P/'invariance_results_v1.json').read_text())
assert r['protocol_sha256']==inputs['protocol_v1.txt'] and r['code_sha256']==inputs['run_v1.py'] and v['code_sha256']==inputs['invariance_v1.py']
def q(x):return Q(x['numerator'],x['denominator'])
def bucket(mat):
 n=len(mat);b=[0]*n
 # Assign each matrix cell once to its displacement bucket, rather than loop through diagonals.
 for i,row in enumerate(mat):
  for j,value in enumerate(row):b[(j-i)%n]+=value
 return b
def verify_summary(s):
 mat=s['matrix'];n=len(mat);b=bucket(mat);score=[Q(x,n) for x in b];avg=Q(sum(map(sum,mat)),n*n)
 assert score==list(map(q,s['phase_scores']))
 assert avg==q(s['cycle_mean']) and score[0]-avg==q(s['own_minus_cycle_mean'])
 assert s['all_maximizing_shifts']==[k for k,x in enumerate(b) if x==max(b)]
 assert s['phases_at_least_own']==[k for k,x in enumerate(b) if x>=b[0]]
 assert q(s['descriptive_own_upper_rank_fraction'])==Q(sum(x>=b[0] for x in b),n)
 return score,score[0]-avg
artificial={}
for name,s in r['fixed_twelve_cases'].items():
 scores,delta=verify_summary(s);artificial[name]={'scores':[str(x) for x in scores],'delta':str(delta),'maximizing_phases':s['all_maximizing_shifts']}
assert r['fixed_twelve_cases']['unique_alignment']['matrix']==r['fixed_twelve_cases']['independent_copy_tokens']['matrix']
for b in r['phrase_boundary_cases']:
 ph=tuple(b['phrase']);present=False
 for reg in b['regions']:
  for start in range(len(reg)):
   if start+len(ph)<=len(reg) and all(reg[start+j]==ph[j] for j in range(len(ph))):present=True
 assert present==b['expected']==b['actual']
missing=r['fixed_unknown_case'];mat=missing['matrix_with_null'];positions=[(i,j) for i in range(3) for j in range(3) if mat[i][j] is None]
assert positions==list(map(tuple,missing['unknown_positions']))
all_scores=[];all_delta=[];tie_cases=[];unique=0
for values,save in zip(itertools.product((0,1),repeat=3),missing['all_completions']):
 m=[row[:] for row in mat]
 for pos,x in zip(positions,values):m[pos[0]][pos[1]]=x
 assert list(values)==save['unknown_values'] and m==save['matrix'];scores,delta=verify_summary(save);all_scores.append(scores);all_delta.append(delta)
 if len(save['all_maximizing_shifts'])>1:tie_cases.append({'values':list(values),'max_phases':save['all_maximizing_shifts'],'scores':[str(x) for x in scores]})
 else:unique+=1
assert len(missing['all_completions'])==8
phasebounds=[(min(x[k] for x in all_scores),max(x[k] for x in all_scores)) for k in range(3)]
assert phasebounds==[tuple(map(q,x)) for x in missing['phase_score_bounds']]
assert (min(all_delta),max(all_delta))==tuple(map(q,missing['exact_delta_bounds']))
verify_summary(missing['naively_zero_filled'])
assert missing['own_is_unique_maximum_for_all_completions']==(unique==8)
# Independent full binary small-N checks via relocation of each active cell.
checks=[]
for n in range(1,5):
 cnt=paired=single=0
 for mask in range(1<<(n*n)):
  active=[divmod(k,n) for k in range(n*n) if mask&(1<<k)]
  b=[0]*n
  for i,j in active:b[(j-i)%n]+=1
  assert sum(b)==len(active)
  diag=sum(i==j for i,j in active)
  assert n*b[0]-len(active)==(n-1)*diag-(len(active)-diag)
  for shift in range(n):
   for direction in (1,-1):
    after=[0]*n
    for oldi,oldj in active:
     newi=direction*(oldi-shift)%n;newj=direction*(oldj-shift)%n;after[(newj-newi)%n]+=1
    assert after==[b[direction*k%n] for k in range(n)]
    assert after[0]==b[0] and sorted(after)==sorted(b)
    assert sum(x>=after[0] for x in after)==sum(x>=b[0] for x in b)
    paired+=1
   after=[0]*n
   for i,j in active:after[((j-shift)%n-i)%n]+=1
   assert after==[b[(k+shift)%n] for k in range(n)];single+=1
  cnt+=1
 checks.append({'n':n,'all_binary_matrices':cnt,'common_relabelings':paired,'single_body_rotations':single,'passed':True})
assert checks==v['exhaustive_small_n_checks']
assert [dict(n=x['n'],all_binary_matrices=x['all_binary_matrices'],identities_passed=True) for x in checks]==r['exhaustive_identity_checks']
for ex in v['twelve_item_fixed_examples']:
 shift=ex['body_only_rotation'];base=[12]+[0]*11
 assert ex['original_match_counts']==base and ex['common_rotation_counts']==base and ex['common_reflection_counts']==base
 expected=[0]*12;expected[-shift%12]=12;assert ex['body_only_rotation_counts']==expected
assert len(v['twelve_item_fixed_examples'])==12
# Extension toy: coefficients and reindexing work on signed rational values as claimed.
real=[[Q(-2,3),Q(4,5),Q(7,2)],[Q(0),Q(-1,7),Q(1,11)],[Q(9,4),Q(-5,8),Q(3)]]
b=bucket(real);mean=Q(sum(b),9);assert mean==sum(map(sum,real))/9
for shift in range(3):
 for d in (1,-1):
  transformed=[[real[(d*i+shift)%3][(d*j+shift)%3] for j in range(3)] for i in range(3)]
  assert bucket(transformed)==[b[d*s%3] for s in range(3)]
assert all(sha(P/n)==h for n,h in inputs.items())
receipt={'schema_version':1,'audit_status':'PASS_MATH_AND_SAVED_ARTIFICIAL_RESULTS_WITH_SCOPE_NOTES','started_utc':started,'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cpu_seconds':time.process_time()-clock,'input_files':[{'path':n,'sha256':h} for n,h in inputs.items()],'input_hashes_unchanged':True,'author_modules_imported_or_executed':False,'independent_method':'Matrix cells placed in displacement buckets; active cell coordinates relocated by inverse bijection. No import ofrun_v1.py/invariance_v1.py, no original main invocation or results overwrite.','independent_check_program_sha256':sha(Path(__file__)),'read_scope':'Only8requested files; no zodiac_four reports/images/observations, manuscript strings or new targets. Existing contextual claims in reports were read but not independently re-certified.','mathematical_proof_review':{'cycle_mean':'PASS: for everyi, s↦j=i+s is a bijection moduloN.','delta_weights':'PASS: diagonal coefficient(N-1)/N²; offdiagonal−1/N².','common_rotation':'PASS: k=i+r givesTprime_s=T_s.','common_reflection':'PASS: k=−i+r givesTprime_s=T_(−s).','body_only_rotation':'PASS: Tprime_s=T_(s+r).','allN_status':'Symbolic change-of-variable proof reviewed; finite enumerations are separate implementation checks.'},'fixed_twelve_cases_recomputed':artificial,'phrase_boundary_cases_passed':4,'unknown_case':{'all_completions_recomputed':8,'phase_bounds':[[str(x) for x in a] for a in phasebounds],'delta_bounds':[str(min(all_delta)),str(max(all_delta))],'unique_own_cases':unique,'tied_own_cases':tie_cases,'own_is_among_maxima_for_all_completions':all(x[0]>=max(x) for x in all_scores),'zero_fill_delta':str(q(missing['naively_zero_filled']['own_minus_cycle_mean']))},'exhaustive_recomputed':checks,'total_binary_matrices':sum(x['all_binary_matrices'] for x in checks),'total_common_relabelings':sum(x['common_relabelings'] for x in checks),'total_body_only_rotations':sum(x['single_body_rotations'] for x in checks),'twelve_identity_rotation_examples_passed':12,'signed_rational_extension_toy_passed':True,'numerical_or_proof_errors_found':[],'scope_notes':[{'priority':'interpretation','topic':'common_direction','note':'Jointly reversing diagram index order is not reversing glyph order inside a label or word order inside body text; the latter changesX itself and is not covered.'},{'priority':'interpretation','topic':'exact_unknown_bounds','note':'Independently assignable means all0/1 completions are admissible, not probabilistic independence. Logical constraints from duplicate labels/body shared tokenization can make these bounds conservative rather than sharp. Undefined roles are not simply missing cells.'},{'priority':'interpretation','topic':'NA_example','note':'Own remains at least tied maximum in all8completions;7unique and1tie. The example demonstrates loss of guaranteed uniqueness, not thatanotherphasebeatsown.'},{'priority':'interpretation','topic':'independent_copy_tokens','note':'Artifact name does not mean label andbody are statistically independent; construction copies identifiers exactly. Reports correctly describe this as a semantics-free counterexample.'},{'priority':'scope','topic':'real_evidence','note':'No newmanuscript data or empirical test; artificial pass does not establish realrole coverage, measurement validity, exchangeability, semantics or language.'},{'priority':'scope','topic':'reproducibility_gate','note':'Source scripts were read, notrerun: theirmain overwrites saved results; run_v1 checks onlyfirst frozen protocol entry. This limited audit validates saved code/protocol hashes and exact results, not allhistorical freeze dependencies.'}],'new_manuscript_test':False,'scoring_gate_changed':False}
print(json.dumps(receipt, ensure_ascii=False, indent=2))
