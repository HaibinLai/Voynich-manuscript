"""Fixed known-answer calibration. Solver never receives plaintext/true mapping."""
from pathlib import Path
from collections import Counter
import json,hashlib,sys,subprocess,random,time,argparse,platform
import numpy as np
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent.parent/'study20'))
from analyze import plain_words
SEED=20261117
LETTERS='abcdefghijklmnopqrstuvwxyz'
SOURCES={'english':'english_alice.txt','latin':'latin_caesar.xml'}
def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def training_words(words,letters=30000):
    out=[];remaining=letters
    for i,w in enumerate(words):
        if remaining<=0:break
        out.append(w[:remaining]);remaining-=len(out[-1])
    return out,i

def train(words,bag=False):
    counts=[np.zeros((27,)*(k+1),dtype=np.int64) for k in range(4)]
    for word in words:
        u=[ord(c)-97 for c in (''.join(sorted(word)) if bag else word)]
        s=[26]*3+u+[26]
        for i in range(3,len(s)):
            for k in range(4):counts[k][tuple(s[i-k:i+1])]+=1
    p=(counts[0]+.5)/(counts[0].sum()+.5*27)
    for k in range(1,4):p=(counts[k]+5*p[None,...])/(counts[k].sum(axis=-1,keepdims=True)+5)
    assert np.max(abs(p.sum(axis=-1)-1))<1e-12
    return np.log(p)

def score(words,mapping,model,bag=False):
    out=0.
    for w in words:
        v=[ord(mapping[ord(c)-97])-97 for c in w]
        if bag:v.sort()
        seq=[26]*3+v+[26]
        for i in range(3,len(seq)):out+=model[tuple(seq[i-3:i+1])]
    return out

def encode(words,key):return [''.join(key[ord(c)-97] for c in w) for w in words]
def decode(words,key):return encode(words,key)
def key_for(seed):
    x=list(LETTERS);random.Random(seed).shuffle(x);enc=''.join(x);dec=''.join(LETTERS[enc.index(c)] for c in LETTERS);return enc,dec

def prepare():
    for d in ['data','models','runs','reports']: (ROOT/d).mkdir(exist_ok=True)
    meta={'seed':SEED,'datasets':{},'protocol_sha256':digest(ROOT/'protocol.txt'),'created_unix':time.time()}
    for li,(lang,filename) in enumerate(SOURCES.items()):
        allwords=plain_words(filename);trainwords,stop=training_words(allwords)
        assert stop<10000
        meta['datasets'][lang]={'source':filename,'source_sha256':digest(ROOT.parent.parent/'study20'/'controls'/filename),'total_words':len(allwords),'training_letters':sum(map(len,trainwords)),'training_words':len(trainwords),'training_last_token_index':len(trainwords)-1,'training_last_word_truncated':trainwords[-1]!=allwords[len(trainwords)-1],'dev_token_range':[10000,10400],'test_token_ranges':[[i,i+400] for i in [14000,18000,22000]]}
        (ROOT/'data'/f'{lang}_train.txt').write_text(' '.join(trainwords)+'\n')
        counts=Counter(''.join(trainwords));(ROOT/'models'/f'{lang}_frequency.txt').write_text(' '.join(str(counts[c]) for c in LETTERS))
        save(ROOT/'models'/f'{lang}_lexicon.json',dict(Counter(trainwords)))
        for mode in ['ordered','bag']:
            model=train(trainwords,mode=='bag');model.tofile(ROOT/'models'/f'{lang}_{mode}.bin')
        for split,starts in [('dev',[10000]),('test',[14000,18000,22000])]:
            for j,start in enumerate(starts):
                words=allwords[start:start+400];case=f'{split}_{lang}_{j}';seed=SEED+li*100000+j*1000+(0 if split=='dev' else 500)
                enc,dec=key_for(seed);cipher=encode(words,enc);sortedcipher=[''.join(sorted(w)) for w in cipher]
                rng=random.Random(seed+1);shuffled=[]
                for w in cipher:
                    a=list(w);rng.shuffle(a);shuffled.append(''.join(a))
                allchars=list(''.join(cipher));rng=random.Random(seed+2);rng.shuffle(allchars);flat=iter(allchars);globalshuffle=[''.join(next(flat) for _ in w) for w in cipher]
                treatments={'P1_mono':cipher,'A1_sorted':sortedcipher,'A2_shuffled':shuffled,'N1_global':globalshuffle}
                for name,ww in treatments.items():(ROOT/'data'/f'{case}_{name}.txt').write_text(' '.join(ww)+'\n')
                save(ROOT/'data'/f'{case}_truth.json',{'id':case,'language':lang,'split':split,'token_range':[start,start+400],'words':words,'letters':sum(map(len,words)),'encryption':enc,'decryption':dec,'seed':seed})
                assert decode(cipher,dec)==words
                assert [sorted(w) for w in cipher]==[sorted(w) for w in sortedcipher]==[sorted(w) for w in shuffled]
                assert Counter(''.join(cipher))==Counter(''.join(globalshuffle))
                assert list(map(len,cipher))==list(map(len,globalshuffle))
    save(ROOT/'manifest_preparation.json',meta)

def evaluate(truth,cipher,run,model_lang,mode,treatment):
    mapping=run['mapping'];decoded=decode(cipher,mapping);correct=truth['decryption'];counts=Counter(''.join(cipher));observed=sorted(counts)
    weighted=sum(counts[c] for c in observed if mapping[ord(c)-97]==correct[ord(c)-97])/sum(counts.values())
    types=sum(mapping[ord(c)-97]==correct[ord(c)-97] for c in observed)/len(observed)
    bagaccuracy=float(np.mean([sorted(a)==sorted(b) for a,b in zip(decoded,truth['words'])])) if treatment!='N1_global' else None
    letteraccuracy=sum(a==b for a,b in zip(''.join(decoded),''.join(truth['words'])))/truth['letters'] if treatment=='P1_mono' else None
    wordaccuracy=float(np.mean([a==b for a,b in zip(decoded,truth['words'])])) if treatment=='P1_mono' else None
    lexicon=json.loads((ROOT/'models'/f'{model_lang}_lexicon.json').read_text());baglex={''.join(sorted(w)) for w in lexicon}
    model=np.fromfile(ROOT/'models'/f'{model_lang}_{mode}.bin',dtype=np.float64).reshape((27,)*4)
    true_score=score(cipher,correct,model,mode=='bag');independent_score=score(cipher,mapping,model,mode=='bag')
    assert abs(independent_score-run['score'])<1e-6
    return {**run,'case':truth['id'],'plaintext_language':truth['language'],'model_language':model_lang,'treatment':treatment,'letters':truth['letters'],'words':len(cipher),'observed_letter_types':len(observed),'key_character_accuracy':weighted,'key_type_accuracy':types,'plaintext_character_accuracy':letteraccuracy,'plaintext_word_accuracy':wordaccuracy,'plaintext_wordbag_accuracy':bagaccuracy,'training_dictionary_word_hit_rate':float(np.mean([w in lexicon for w in decoded])),'training_dictionary_bag_hit_rate':float(np.mean([''.join(sorted(w)) in baglex for w in decoded])),'true_key_score':true_score,'recovered_minus_true_score':run['score']-true_score,'score_per_letter':run['score']/truth['letters'],'decoded_sample':' '.join(decoded[:60]),'truth_sample':' '.join(truth['words'][:60]),'scope':'Key accuracy uses synthetic truth. No claim about Voynich language or decipherment.'}

def run_case(case,model_lang,mode,treatment,restarts,steps,seed):
    truth=json.loads((ROOT/'data'/f'{case}_truth.json').read_text());cipher=(ROOT/'data'/f'{case}_{treatment}.txt').read_text().split()
    output=ROOT/'runs'/f'{case}_{model_lang}_{mode}_{treatment}_r{restarts}_s{steps}.json'
    if output.exists():return json.loads(output.read_text())
    command=[str(ROOT/'solver'),str(ROOT/'models'/f'{model_lang}_{mode}.bin'),str(ROOT/'data'/f'{case}_{treatment}.txt'),str(ROOT/'models'/f'{model_lang}_frequency.txt'),mode,str(restarts),str(steps),str(seed)]
    run=json.loads(subprocess.check_output(command,text=True));result=evaluate(truth,cipher,run,model_lang,mode,treatment)
    result['solver_inputs']=[str(Path(x).relative_to(ROOT)) for x in command[1:4]]
    save(output,result);print(json.dumps({'case':case,'model':model_lang,'mode':mode,'treatment':treatment,'accuracy':result['key_character_accuracy'],'seconds':result['seconds'],'true_key_score_gap':result['recovered_minus_true_score']},ensure_ascii=False),flush=True)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','dev','test']);p.add_argument('--restarts',type=int,default=8);p.add_argument('--steps',type=int,default=20000);a=p.parse_args()
    if a.action=='prepare':prepare();return
    if a.action=='dev':
        for i,lang in enumerate(SOURCES):
            for mode in ['ordered','bag']:
                run_case(f'dev_{lang}_0',lang,mode,'P1_mono',a.restarts,a.steps,SEED+100+i)
        return
    frozen=json.loads((ROOT/'search_budget.json').read_text());assert a.restarts==frozen['restarts'] and a.steps==frozen['steps']
    results=[]
    for i,lang in enumerate(SOURCES):
        for j in range(3):
            case=f'test_{lang}_{j}'
            for m,model_lang in enumerate(SOURCES):
                for t,treatment in enumerate(['P1_mono','A1_sorted','A2_shuffled','N1_global']):
                    results.append(run_case(case,model_lang,'ordered',treatment,a.restarts,a.steps,SEED+10000+i*1000+j*100+m*10+t))
                for t,treatment in enumerate(['P1_mono','N1_global']):
                    results.append(run_case(case,model_lang,'bag',treatment,a.restarts,a.steps,SEED+20000+i*1000+j*100+m*10+t))
    save(ROOT/'results.json',results)

if __name__=='__main__':main()
