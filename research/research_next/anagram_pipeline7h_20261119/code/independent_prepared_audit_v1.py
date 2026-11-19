"""Audit new prepared inputs only; does not execute or score author decoders."""
from pathlib import Path
from collections import Counter,defaultdict
from fractions import Fraction
import argparse,datetime,hashlib,json,random,re,unicodedata,xml.etree.ElementTree as ET
import independent_toy_audit_v1 as own
W=Path(__file__).resolve().parents[1];REPO=W.parents[2]

def source_words(p):
 if p.suffix=='.xml':
  tree=ET.parse(p);body=next(e for e in tree.iter() if e.tag.rsplit('}',1)[-1]=='body')
  for parent in body.iter():
   for child in list(parent):
    if child.tag.rsplit('}',1)[-1] in ['note','head','speaker']:parent.remove(child)
  text=' '.join(body.itertext())
 else:
  text=p.read_text(encoding='utf-8-sig')
  if '*** START OF' in text:text=text.split('*** START OF',1)[1].split('\n',1)[1]
  if '*** END OF' in text:text=text.split('*** END OF',1)[0]
  marker='Alice was beginning to get very tired'
  if marker in text:text=text[text.index(marker):]
 return re.findall('[a-z]+',unicodedata.normalize('NFKD',text).encode('ascii','ignore').decode().lower())
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=W/'calibration/prepared_independent_audit_v1.json');args=ap.parse_args();own.ck(not args.output.exists(),'new_output')
 data=W/'calibration/data_v1';manifest=own.read(data/'preparation_manifest.json');own.ck(manifest['toy'] is False,'formal_prepared_not_run')
 for ref in own.read(data/'file_hashes.json'):own.ck(own.sha(data/ref['path'])==ref['sha256'],'all_prepared_file_hash')
 datasets={};modelcounts=[]
 for src in manifest['sources']:
  lang=src['language'];p=REPO/src['path'];own.ck(own.sha(p)==src['sha256'],'source_hash');words=source_words(p);datasets[lang]=words
  own.ck(len(words)==src['total_tokens'] and src['training_range']==[0,8000],'source_inventory')
  train=(data/f'train/udhr-{lang}.txt.tra').read_text().split();own.ck(train==words[:8000] and len(train)==8000,'training8000_exact')
  base=data/f'models/shared/{lang}/base';own.ck((base.parent/'training.txt').read_text().split()==train,'decoder_train_same')
  bags=Counter(map(own.bag,train));singleton={own.bag(w):w for w in train if bags[own.bag(w)]==1};replaced=['<u>' if bags[own.bag(w)]==1 else w for w in train]
  decoder=own.verify_lms(Path(str(base)+'.alp.unk.lm'),[['<s>','<s>',*b,r'<\s>',r'<\s>'] for b in own.chunk(replaced)])
  expected=defaultdict(set)
  for x in replaced:expected[own.bag(x)].add(x)
  actual={line.split('\t')[0]:line.split('\t')[1:] for line in Path(str(base)+'.alp.unk.alp').read_text().splitlines()}
  own.ck(actual=={k:sorted(v) for k,v in expected.items()} and actual['<>u']==['<u>'],'decoder_emissions')
  own.ck(dict(line.split('\t') for line in Path(str(base)+'.alp.1co').read_text().splitlines())==singleton,'decoder_singletons')
  own.ck(all((v,) in decoder[0] for vv in actual.values() for v in vv),'decoder_candidate_states')
  for variant in ['readme_lex','code_countfirst']:
   dest=data/'models'/variant/lang;tw=[own.bag(x) if variant=='readme_lex' else ''.join(sorted(x,key=lambda c:(-Counter(x)[c],c))) for x in train];blocks=own.chunk(tw)
   wordlm=own.verify_lms(dest/'word.lm',blocks);charlm=own.verify_lms(dest/'char.lm',[list('_'.join(x)) for x in blocks]);expected_groups=defaultdict(Counter)
   for n in [1,2,3]:
    for g,count in own.grams(blocks,n).items():
     signature,candidate=own.pattern_and_candidate(g);expected_groups[n,signature][candidate]+=count
   actualgroups={}
   for line in (dest/'patterns.txt').read_text().splitlines():
    n,pat,*candidates=line.split('\t');key=int(n),pat;own.ck(key not in actualgroups,'unique_pattern');actualgroups[key]=candidates
    own.ck(all(len(x.split())==int(n) and all(re.fullmatch('[a-z]+',y) for y in x.split()) for x in candidates),'candidate_scope')
   own.ck(actualgroups=={key:sorted(counts,key=lambda c:(-counts[c],c)) for key,counts in expected_groups.items()},'all_candidates_and_order')
   cfg=dict(line.split('\t') for line in (dest/'model.config').read_text().splitlines());freq=Counter(''.join(train));own.ck(cfg['order'].split()==sorted('abcdefghijklmnopqrstuvwxyz',key=lambda x:(-freq[x],x)),'alphabet26_order')
   own.ck(len(cfg)==15 and all(Fraction(cfg[f'{prefix}lambda{n}'])==value for prefix in ['w','c'] for n,value in [(1,Fraction(3,10)),(2,Fraction(3,10)),(3,Fraction(4,10))]) and Fraction(cfg['charcoeff'])==Fraction(1,2),'config_frozen_parameters')
   modelcounts.append({'language':lang,'variant':variant,'word_lm_entries':list(map(len,wordlm)),'char_lm_entries':list(map(len,charlm)),'pattern_groups':len(actualgroups),'candidate_entries':sum(map(len,actualgroups.values()))})
  print('prepared-checked',lang,flush=True)
 inputs=own.read(data/'execution_inputs.json');own.ck([x['id'] for x in inputs['cases']]==['P01','P02','P03','P04','C01'],'fixed_cases')
 for i,cid in enumerate(['P01','P02','P03','P04','C01A','C01B']):
  t=own.read(data/'truth'/f'{cid}.json');cipherid=cid if cid.startswith('P') else 'C01';cipher=(data/'cipher'/f'{cipherid}.txt').read_text().split();plain=t['words'];enc=t['encryption'];seed=t['seed']
  alphabet=list('abcdefghijklmnopqrstuvwxyz');random.Random(seed).shuffle(alphabet);own.ck(enc==dict(zip('abcdefghijklmnopqrstuvwxyz',alphabet)),'seeded_bijection');own.ck(t['decryption']=={v:k for k,v in enc.items()},'inverse_key')
  own.ck(len(plain)==len(cipher)==len(t['permutations'])==(80 if cid.startswith('P') else 7),'80_7_length')
  if cid.startswith('P'):
   lang='english' if i<2 else 'latin';start=[12000,16000][i%2];own.ck(plain==datasets[lang][start:start+80] and t['token_range']==[start,start+80] and seed==2026111901+i,'formal_source_interval')
  else:own.ck(plain==('the master was silent in the room' if cid=='C01A' else 'the stream was silent in the room').split() and seed==2026111999,'twin_fixture')
  rng=random.Random(seed+100)
  for word,observed,perm in zip(plain,cipher,t['permutations']):
   own.ck(sorted(perm)==list(range(len(word))) and ''.join(enc[word[j]] for j in perm)==observed,'permutation_provenance')
   indices=list(range(len(word)));rng.shuffle(indices);coded=''.join(enc[x] for x in word)
   if cid.startswith('C'):coded=''.join(sorted(coded))
   own.ck(''.join(coded[j] for j in indices)==observed,'seeded_cipher_generation')
 result={'schema':'tenth_prepared_inputs_independent_audit_v1','status':'PASS','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Prepared data_v1 only; no author execution, no formal calibration output/accuracy read or computed.','models':modelcounts,'fixed_input_scope':{'languages':2,'training_words_each':8000,'positive_cases':4,'positive_words_each':80,'twin_shared_input_words':7,'twin_distinct_histories':2},'checks':dict(own.checks),'bindings':{'data_file_hashes':own.sha(data/'file_hashes.json'),'prepare_code':own.sha(W/'code/prepare_calibration.py'),'audit_code':own.sha(Path(__file__)),'own_independent_helper':own.sha(W/'code/independent_toy_audit_v1.py')},'limits':['Only intended finite training artifact and generation history verified; no claim of original2016 data/results reproduction.','Four positive snippets were exposed in older scale control; this audit does not restore blindness.','Probability text checked against exact relative frequency within1e-15; every conditional sum within1e-12.']}
 args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');args.output.with_suffix('.txt').write_text('正式准备产物独立审计PASS：两语言各8000训练词、4段各80词、twin7词双生成史一致；全部LM条件概率/标记/单例、两表示patlst签名/候选/顺序/字母域、全部输入SHA和固定随机生成史通过。没有运行作者解码、没有读取或计算正式准确率；四段旧规模曝光仍保留。\n');print(json.dumps({'status':'PASS','receipt_sha256':own.sha(args.output),'checks':dict(own.checks)}))
if __name__=='__main__':main()
