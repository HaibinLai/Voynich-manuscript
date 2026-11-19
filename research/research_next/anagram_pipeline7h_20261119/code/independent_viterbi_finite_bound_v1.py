"""Sufficient range bound from frozen new-data LMs; no decoder execution."""
from pathlib import Path
from fractions import Fraction as F
import datetime,hashlib,json,subprocess
W=Path(__file__).resolve().parents[1];D=W/'calibration/data_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def readlm(p,n):
 d={}
 for line in p.read_text().splitlines():
  row=line.split('\t');assert len(row)==n+1;d[tuple(row[:-1])]=F(row[-1])
 return d
rows=[]
for lang in ['english','latin']:
 base=D/f'models/shared/{lang}/base';lm=[readlm(Path(str(base)+'.alp.unk.lm'+str(n)),n) for n in [1,2,3]]
 assert all(0<p<=1 for table in lm for p in table.values())
 emissions={r.split('\t')[0]:r.split('\t')[1:] for r in Path(str(base)+'.alp.unk.alp').read_text().splitlines()}
 assert emissions['<>u']==['<u>'] and all(emissions.values())
 targets={x for vv in emissions.values() for x in vv}|{r'<\s>'}
 assert all((x,) in lm[0] and lm[0][x,]>0 for x in targets|{'<s>'})
 minimal=min(lm[0][x,] for x in targets);allmin=min(lm[0].values());transition_floor=F(3,10)*minimal;prob_lower=transition_floor**22
 assert prob_lower/2>F(1,2**1022) and 2*10**54<float.fromhex('0x1.fffffffffffffp+1023')
 rows.append({'language':lang,'nonempty_emission_bags':len(emissions),'possible_target_states_including_EOS':len(targets),'minimum_positive_unigram_all_table':str(allmin),'minimum_target_unigram':str(minimal),'minimum_target_unigram_decimal':float(minimal),'transition_lower':str(transition_floor),'transition_lower_decimal':float(transition_floor),'twenty_token_unscaled_product_lower':str(prob_lower),'twenty_token_unscaled_product_lower_decimal':float(prob_lower),'rounding_conservative_lower_decimal':float(prob_lower/2),'rounding_conservative_upper':str(2*10**54),'lower_exceeds_minimum_normal_binary64':True,'upper_below_maximum_binary64':True,'all_candidates_and_markers_present':True})
config=subprocess.check_output(['perl','-V:nvtype','-V:nvsize'],text=True)
assert "nvtype='double'" in config and "nvsize='8'" in config
result={'schema':'tenth_independent_viterbi_finite_sufficient_bound_v1','status':'PASS_SUFFICIENT_RANGE_BOUND','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'code_sha256':sha(Path(__file__)),'input_manifest_sha256':sha(D/'file_hashes.json'),'prepared_audit_sha256':sha(W/'calibration/prepared_independent_audit_v1.json'),'perl_numeric_config':config.strip().splitlines(),'scope':'Only unchanged trigram Viterbi on the frozen decoder model and predeclared nonempty7 or20token blocks. No author decoder executed; no accuracy computation.','derivation':['Every emission candidate and termination marker has positive unigram probability; missing bigram/trigram contributes zero, so transition probability >=0.3*minimum_target_unigram.','All stored conditional probabilities are <=1 and positive fixed interpolation weights sum to1, so mathematical transition probability <=1.','For T<=20 and T>=2 there are T+2<=22 transition factors including two termination factors. Each positive full path product is >=q^22. The forward recursion only adds a uniform positive1000^(T-2) scaling, at most1000^18=1e54.','Every candidate list nonempty and all transitions positive means each initialized/recurrent pair has a finite positive predecessor; negative-infinity max sentinels are replaced.','IEEE binary64 rounding allowance factor2 yields conservative product interval[q^22/2,2e54], far inside normal finite range; this is an arithmetic range bound, not an exact floating-point rounding proof or runtime/memory guarantee.'],'languages':rows,'limitations':['Does not cover longer lines, different models, zero unigram candidates, empty emissions, or single-token alternative decoder branch.','Does not prove correctness of recovered text, uniqueness, timeout behavior or absence of unrelated implementation faults.']}
p=W/'calibration/viterbi_finite_bound_v1.json';assert not p.exists();p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');p.with_suffix('.txt').write_text('Viterbi有限性充分界PASS，仅限本冻结模型与7/20词块。全部候选及句尾标记有正unigram，转移下界为0.3×最小目标unigram，上界1；20词最多22个因子与18次×1000。数学上界1e54，保守浮点范围取[q^22/2,2e54]，两语言均远离binary64上下溢。实际Perl nvtype=double/nvsize=8。此为输入条件下算术范围证明，不是恢复正确率或长句安全保证，未运行作者解码。\n');print(json.dumps({'status':result['status'],'languages':[{k:r[k] for k in ['language','minimum_target_unigram_decimal','twenty_token_unscaled_product_lower_decimal']} for r in rows],'sha256':sha(p)}))
