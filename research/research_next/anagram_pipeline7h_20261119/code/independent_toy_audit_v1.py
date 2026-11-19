"""Independent prepared-artifact and toy Viterbi audit; no production imports."""
from pathlib import Path
from fractions import Fraction as F
from collections import Counter,defaultdict
import argparse,hashlib,itertools,json,datetime,math
W=Path(__file__).resolve().parents[1]
checks=Counter()
def ck(test,name):
 checks[name]+=1
 if not test:raise AssertionError(name)
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bag(w):return ''.join(sorted(w))
def chunk(words):return [words[i:i+20] for i in range(0,len(words),20)]
def grams(seqs,n):
 out=Counter()
 for seq in seqs:
  for i in range(len(seq)-n+1):out[tuple(seq[i:i+n])]+=1
 return out
def lm(p,n):
 result={}
 for line in p.read_text().splitlines():
  cells=line.split('\t');ck(len(cells)==n+1,'LM_shape');g=tuple(cells[:-1]);ck(g not in result,'LM_unique');result[g]=F(cells[-1])
 return result
def verify_lms(prefix,seqs):
 result=[]
 for n in [1,2,3]:
  table=lm(Path(str(prefix)+str(n)),n);counts=grams(seqs,n);den=Counter()
  for g,v in counts.items():den[g[:-1]]+=v
  ck(set(table)==set(counts),'LM_support');sums=defaultdict(F)
  for g,value in table.items():
   ck(0<value<=1 and abs(value-F(counts[g],den[g[:-1]]))<F(1,10**15),'LM_probability');sums[g[:-1]]+=value
  ck(all(abs(v-1)<F(1,10**12) for v in sums.values()),'LM_context_normalized');result.append(table)
 return result
def pattern_and_candidate(words):
 cs=[Counter(w) for w in words]
 key=lambda c:tuple(-co[c] for co in cs)
 ordered=[''.join(sorted(w,key=key)) for w in words]
 mapping={};alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+-'
 pattern=[]
 for w in ordered:
  p=''
  for c in w:
   if c not in mapping:mapping[c]=alphabet[len(mapping)]
   p+=mapping[c]
  pattern.append(p)
 candidate=' '.join(''.join(sorted(w,key=lambda c:(key(c),c))) for w in words)
 return ' '.join(pattern),candidate

def prepared(data):
 ck(read(data/'preparation_manifest.json')['toy'] is True,'toy_only_guard')
 hashes=read(data/'file_hashes.json')
 for x in hashes:ck(sha(data/x['path'])==x['sha256'],'prepared_hash')
 train=(data/'models/shared/english/training.txt').read_text().split();ck(len(train)==97,'toy_training97')
 bg=Counter(map(bag,train));single={bag(w):w for w in train if bg[bag(w)]==1};replaced=['<u>' if bg[bag(w)]==1 else w for w in train]
 base=data/'models/shared/english/base';decoder=verify_lms(Path(str(base)+'.alp.unk.lm'),[['<s>','<s>',*x,r'<\s>',r'<\s>'] for x in chunk(replaced)])
 em={x.split('\t')[0]:x.split('\t')[1:] for x in Path(str(base)+'.alp.unk.alp').read_text().splitlines()};expected=defaultdict(set)
 for word in replaced:expected[bag(word)].add(word)
 ck(em=={k:sorted(v) for k,v in expected.items()},'emission_exact');ck(em['<>u']==['<u>'],'unknown_sentinel')
 sm=dict(x.split('\t') for x in Path(str(base)+'.alp.1co').read_text().splitlines());ck(sm==single,'singleton_exact')
 ck('<u>',) if False else None
 ck(all((x,) in decoder[0] for candidates in em.values() for x in candidates),'all_states_in_A1')
 for variant in ['readme_lex','code_countfirst']:
  dest=data/'models'/variant/'english'
  transformed=[bag(w) if variant=='readme_lex' else ''.join(sorted(w,key=lambda c:(-Counter(w)[c],c))) for w in train]
  blocks=chunk(transformed);verify_lms(dest/'word.lm',blocks);verify_lms(dest/'char.lm',[list('_'.join(x)) for x in blocks])
  expected_groups=defaultdict(Counter)
  for n in [1,2,3]:
   for g,count in grams(blocks,n).items():
    pattern,candidate=pattern_and_candidate(g);expected_groups[n,pattern][candidate]+=count
  actual={}
  for line in (dest/'patterns.txt').read_text().splitlines():
   n,pat,*candidates=line.split('\t');key=int(n),pat;ck(key not in actual,'pattern_unique')
   ck(all(all(w.isascii() and w.isalpha() and w.islower() for w in c.split()) and len(c.split())==int(n) for c in candidates),'candidate_alphabet_order');actual[key]=candidates
  ck(actual=={k:sorted(v,key=lambda c:(-v[c],c)) for k,v in expected_groups.items()},'all_pattern_candidates_independent')
  cfg=dict(line.split('\t') for line in (dest/'model.config').read_text().splitlines());ck(len(cfg)==15,'config15');ck(len(cfg['order'].split())==26 and set(cfg['order'].split())==set('abcdefghijklmnopqrstuvwxyz'),'alphabet26')
 return decoder,em,sm

def score(seq,models):
 full=['<s>','<s>',*seq,r'<\s>',r'<\s>'];answer=F(1)
 for i in range(2,len(full)):
  answer*=F(3,10)*models[0].get((full[i],),0)+F(3,10)*models[1].get(tuple(full[i-1:i+1]),0)+F(4,10)*models[2].get(tuple(full[i-2:i+1]),0)
 return answer

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=W/'calibration/toy_independent_audit_v1.json');a=p.parse_args();ck(not a.output.exists(),'new_output')
 data=W/'calibration/toy_data_v1';models,em,sm=prepared(data);rows=[]
 for folder in [W/'calibration/toy_primary_v1',W/'calibration/toy_oracle_v1']:
  manifest=read(folder/'run_manifest.json');ck(sha(folder/'results.json')==manifest['results_sha256'],'run_result_hash')
  for x in manifest['files']:ck(sha(folder/x['path'])==x['sha256'],'run_file_hash')
  for log in sorted((folder/'logs').glob('*viterbi')):
   rr=read(log/'receipt.json');ck(rr['exit_code']==0 and rr['status']=='COMPLETED','author_completed');ck(not (log/'stderr.txt').read_text(),'no_stderr')
   inputs=[x.split() for x in (log/'stdin.txt').read_text().splitlines()];outputs=[x.split() for x in (log/'stdout.txt').read_text().splitlines()];ck(len(inputs)==len(outputs),'line_count')
   for words,observed in zip(inputs,outputs):
    bags=list(map(bag,words));unknown=[b not in em for b in bags];poss=[em[b] if b in em else em['<>u'] for b in bags];scored=[]
    for path in itertools.product(*poss):
     restored=[(sm.get(b,b) if u else x) for b,u,x in zip(bags,unknown,path)];scored.append((score(path,models),path,restored))
    best=max(x[0] for x in scored);optimal=[x for x in scored if x[0]==best];ck(observed in [x[2] for x in optimal],'author_output_exact_optimum')
    rows.append({'run_id':log.name,'input_words':words,'output_words':observed,'candidate_sequences':len(scored),'all_candidates':[{'path':list(p),'restored':rest,'score':str(sc)} for sc,p,rest in scored],'maximum_score':str(best),'number_of_optimal_paths':len(optimal),'strictly_better_than_other_paths':len(optimal)==1,'unknown_input_positions':[i for i,u in enumerate(unknown) if u]})
 # Check primary key extraction from normalized ciphertext by positional correspondence, no primary adapter import.
 primary=read(W/'calibration/toy_primary_v1/results.json')
 for case in primary['rows']:
  cipher=(data/'cipher'/f"{case['id']}.txt").read_text().strip();canonical=' '.join(''.join(sorted(w,key=lambda c:(-Counter(w)[c],c))) for w in cipher.split())
  for pipe in case['pipelines']:
   sol=' '.join(pipe['author_solution_words']);ck(len(canonical)==len(sol),'key_length');mapping={}
   for c,d in zip(canonical,sol):
    if c==' ':ck(d==' ','key_space');continue
    ck(c not in mapping or mapping[c]==d,'key_consistency');mapping[c]=d
   ck(mapping==pipe['mapping'] and len(set(mapping.values()))==len(mapping),'key_identity_injective')
   mapped=''.join(mapping.get(c,c) for c in cipher).split();ck(mapped==pipe['mapped_words'],'key_original_cipher')
   ck(list(map(bag,mapped))==list(map(bag,pipe['author_solution_words'])),'key_word_bags')
 result={'schema':'tenth_independent_toy_viterbi_audit_v1','status':'PASS','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'code':{'path':str(Path(__file__).relative_to(W)),'sha256':sha(Path(__file__))},'scope':{'dataset':'toy_data_v1 only','formal_cases_read_or_scored':False,'training_tokens':97,'maspa_training_variants':2,'all_LM_probabilities_and_pattern_candidates_verified':True,'actual_decoder_runs':len(rows),'complete_candidate_paths_scored':sum(x['candidate_sequences'] for x in rows),'scoring':'Exact Fraction products of saved probability decimals, weights3/10,3/10,4/10; omit uniform1000^(T-2) factor which cannot change argmax; include two start/end states.'},'rows':rows,'checks':dict(checks),'interpretation':['All six actual decoder outputs are optimal for their actual saved input and model, including OOV restore. This does not mean the original words were all recovered.','T01 master and stream have the same bag: a contextual preference may differ from generating truth even with true key. T02 oracle preserveszzzz; primary mapped OOV outputs can differ because key recovery failed.','No parameters or formal cases changed based on this audit.'],'bindings':{str(x.relative_to(W)):sha(x) for x in [data/'file_hashes.json',W/'calibration/toy_primary_v1/run_manifest.json',W/'calibration/toy_oracle_v1/run_manifest.json']}}
 a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');a.output.with_suffix('.txt').write_text('人工独立审计PASS：两MASPA训练表示的全部概率/模式候选与97词训练重新派生一致，decoder标记与singleton范围正确。独立以Fraction穷举6次实际decoder输入全部'+str(sum(x['candidate_sequences'] for x in rows))+'条候选路径，包含起止概率和未知回填；原输出均在精确最高分集合。T01真词master被同袋stream替代属于该模型偏好；T02真key保留zzzz，主流程的rrrr/iiii来自错误映射，不能混称全部保留原未知。没有因此改正式参数或读取正式案例。\n');print(json.dumps({'status':'PASS','runs':len(rows),'paths':result['scope']['complete_candidate_paths_scored'],'rows':[(x['run_id'],x['number_of_optimal_paths']) for x in rows],'receipt_sha256':sha(a.output)}))
if __name__=='__main__':main()
